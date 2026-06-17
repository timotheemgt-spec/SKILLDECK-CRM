# SkillDeck CRM — version sécurisée (équipe)

CRM web partagé avec **authentification serveur** : connexion par compte, **données accessibles uniquement après login**.

## Sécurité
- Mots de passe **chiffrés** (bcrypt), jamais en clair.
- Connexion par **jeton signé** (expire après 14 j).
- `/api/data` + gestion des comptes → **401 sans jeton valide**.
- HTTPS automatique (Vercel / Railway).

## Fichiers
- `server.py` — serveur FastAPI sécurisé (auth + données), stockage Vercel KV **ou** fichiers
- `api/index.py` + `vercel.json` — entrée et config pour Vercel
- `index.html` — l'application (login serveur, sync via jeton)
- `requirements.txt`, `Dockerfile` — pour Vercel et/ou Railway

---

## ☁️ Déployer sur Vercel (tu as déjà un compte)

> Important : Vercel est *serverless* → il ne stocke pas de fichiers. On ajoute un petit
> stockage **Vercel KV (Redis)** gratuit, sinon les données seraient perdues.

1. **Mets le dossier `crm-server` sur un repo GitHub** (Vercel déploie depuis GitHub).
2. Sur **vercel.com → Add New → Project**, importe ce repo.
   - Vercel lit `vercel.json` : runtime Python, et toutes les routes pointent vers l'API. Laisse les réglages par défaut.
3. **Ajoute le stockage** : onglet **Storage** du projet → **Create Database → KV (Upstash Redis)** → connecte-le au projet.
   - Vercel ajoute automatiquement les variables `KV_REST_API_URL` et `KV_REST_API_TOKEN`. Le serveur les détecte tout seul.
4. **Settings → Environment Variables**, ajoute :
   - `SECRET_KEY` = une longue chaîne secrète aléatoire (≈40 caractères).
   - `ADMIN_PASSWORD` = mot de passe initial des comptes **Tim** et **Romain**.
5. **Redeploy**. Tu obtiens une **URL HTTPS** (ex. `https://skilldeck-crm.vercel.app`).

> Si tu préfères sans GitHub : installe le CLI `npm i -g vercel`, puis dans le dossier `crm-server` lance `vercel` (suis les questions) et ajoute la base KV + variables depuis le dashboard.

---

## Alternative — Railway (sans base externe, volume disque)
Si tu ne veux pas de KV : sur **railway.app**, déploie `crm-server` (Dockerfile), ajoute un **volume sur `/data`**, et les variables `SECRET_KEY`, `ADMIN_PASSWORD`, `DATA_DIR=/data`. Le code marche tel quel (stockage fichiers).

---

## Première utilisation
1. Ouvre l'URL → connexion. Comptes initiaux : **Tim** / **Romain**, mot de passe = `ADMIN_PASSWORD`.
2. **⚙️ Réglages → 👥 Commerciaux** : ajoute ton collègue (nom + e-mail + mot de passe) → compte créé chiffré côté serveur.
3. Donne-lui l'**URL + son nom + mot de passe**. Il se connecte de partout, vous partagez la même base.
4. Chrome/Edge → « Installer SkillDeck CRM » pour l'avoir comme appli sur le bureau.

## Bon à savoir
- **Change les mots de passe par défaut** dès la 1re connexion.
- Révoquer un accès = supprimer le compte dans 👥 Commerciaux.
- RGPD : base de données personnelles → accès restreint (login), HTTPS, droit d'opposition/suppression des contacts à respecter.
