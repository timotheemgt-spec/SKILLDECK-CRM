"""
SkillDeck CRM — serveur sécurisé (FastAPI), compatible Vercel (serverless) + local.

Sécurité :
- Mots de passe chiffrés (bcrypt)
- Connexion par jeton signé (itsdangerous), expirant (14 j)
- /api/data et la gestion des comptes exigent un jeton valide

Stockage :
- En PROD serverless (Vercel) : Vercel KV / Upstash Redis (variables KV_REST_API_URL + KV_REST_API_TOKEN,
  ou UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN) — persistant.
- En LOCAL (pas de KV) : fichiers data.json / users.json dans DATA_DIR.

Variables d'env recommandées :
  SECRET_KEY      = longue chaîne secrète (garde les sessions valides)
  ADMIN_PASSWORD  = mot de passe initial des comptes Tim/Romain (défaut "skilldeck")
"""
import os
import json
import secrets
import pathlib
import urllib.request
import urllib.parse

from fastapi import FastAPI, Request, HTTPException, Header, Depends
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

BASE = pathlib.Path(__file__).resolve().parent
DATA_DIR = pathlib.Path(os.getenv("DATA_DIR", "/tmp"))
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    DATA_DIR = pathlib.Path("/tmp")
DATA_FILE = DATA_DIR / "data.json"
USERS_FILE = DATA_DIR / "users.json"

SECRET = os.getenv("SECRET_KEY") or secrets.token_hex(32)
serializer = URLSafeTimedSerializer(SECRET, salt="skilldeck-auth")
TOKEN_TTL = 60 * 60 * 24 * 14  # 14 jours

# ── Stockage : Vercel KV / Upstash Redis si dispo, sinon fichiers ───────────
KV_URL = (os.getenv("KV_REST_API_URL") or os.getenv("UPSTASH_REDIS_REST_URL") or "").rstrip("/")
KV_TOKEN = os.getenv("KV_REST_API_TOKEN") or os.getenv("UPSTASH_REDIS_REST_TOKEN") or ""
USE_KV = bool(KV_URL and KV_TOKEN)


def _kv_call(path, body=None):
    req = urllib.request.Request(KV_URL + path, data=body,
                                 headers={"Authorization": "Bearer " + KV_TOKEN})
    if body is not None:
        req.method = "POST"
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def _kv_get(key):
    try:
        return _kv_call("/get/" + urllib.parse.quote(key, safe="")).get("result")
    except Exception:
        return None


def _kv_set(key, value):
    _kv_call("/set/" + urllib.parse.quote(key, safe=""), body=value.encode("utf-8"))


def read_store(key, fpath, default):
    if USE_KV:
        v = _kv_get(key)
        if v:
            try:
                return json.loads(v)
            except Exception:
                return default
        return default
    if fpath.exists():
        try:
            return json.loads(fpath.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def write_store(key, fpath, obj):
    s = json.dumps(obj, ensure_ascii=False)
    if USE_KV:
        _kv_set(key, s)
    else:
        tmp = fpath.with_suffix(".tmp")
        tmp.write_text(s, encoding="utf-8")
        tmp.replace(fpath)


def load_users():
    return read_store("skilldeck:users", USERS_FILE, {})


def save_users(u):
    write_store("skilldeck:users", USERS_FILE, u)


def get_data():
    return read_store("skilldeck:data", DATA_FILE, {"prospects": []})


def set_data(obj):
    write_store("skilldeck:data", DATA_FILE, obj)


def _hash(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()


def seed_users():
    u = load_users()
    if not u:
        pwd = os.getenv("ADMIN_PASSWORD", "skilldeck")
        for name in ("Tim", "Romain"):
            u[name] = {"hash": _hash(pwd), "email": ""}
        save_users(u)
    return u


def make_token(name: str) -> str:
    return serializer.dumps({"u": name})


def verify_token(token: str):
    try:
        data = serializer.loads(token, max_age=TOKEN_TTL)
    except (BadSignature, SignatureExpired):
        return None
    name = data.get("u")
    return name if name in load_users() else None


def auth(authorization: str = Header(default="")) -> str:
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    name = verify_token(token)
    if not name:
        raise HTTPException(status_code=401, detail="Non authentifié")
    return name


app = FastAPI(title="SkillDeck CRM")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def _startup():
    try:
        seed_users()
    except Exception:
        pass


# ── Auth ──
@app.post("/api/login")
async def login(req: Request):
    b = await req.json()
    name = (b.get("name") or "").strip()
    pwd = b.get("password") or ""
    u = load_users().get(name)
    if not u or not bcrypt.checkpw(pwd.encode(), u["hash"].encode()):
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    return {"token": make_token(name), "name": name}


@app.get("/api/me")
def me(name: str = Depends(auth)):
    return {"name": name}


# ── Commerciaux (auth requise) ──
@app.get("/api/users")
def list_users(name: str = Depends(auth)):
    return [{"name": n, "email": d.get("email", "")} for n, d in load_users().items()]


@app.post("/api/users")
async def add_user(req: Request, name: str = Depends(auth)):
    b = await req.json()
    nm = (b.get("name") or "").strip()
    pwd = b.get("password") or ""
    em = (b.get("email") or "").strip()
    if not nm or not pwd:
        raise HTTPException(status_code=400, detail="Nom et mot de passe requis")
    u = load_users()
    u[nm] = {"hash": _hash(pwd), "email": em}
    save_users(u)
    return {"ok": True}


@app.delete("/api/users/{nm}")
def del_user(nm: str, name: str = Depends(auth)):
    u = load_users()
    if nm in u and len(u) > 1:
        del u[nm]
        save_users(u)
    return {"ok": True}


# ── Données (auth requise) ──
@app.get("/api/data")
def api_get_data(name: str = Depends(auth)):
    return get_data()


@app.post("/api/data")
async def api_post_data(req: Request, name: str = Depends(auth)):
    body = await req.json()
    set_data(body)
    return {"ok": True, "count": len(body.get("prospects", []))}


# ── App / PWA ──
@app.get("/manifest.webmanifest")
def manifest():
    return JSONResponse({
        "name": "SkillDeck CRM", "short_name": "SkillDeck", "start_url": "/",
        "display": "standalone", "background_color": "#0d0a1f", "theme_color": "#6c47ff",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}],
    })


@app.get("/icon.svg")
def icon():
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
           "<rect width='100' height='100' rx='22' fill='#6c47ff'/>"
           "<text x='50' y='68' font-family='Arial' font-size='60' font-weight='800' "
           "fill='#fff' text-anchor='middle'>S</text></svg>")
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/")
def index():
    return FileResponse(BASE / "index.html")
