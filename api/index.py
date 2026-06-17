import sys
import pathlib

# rend importable server.py (à la racine du projet)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from server import app  # noqa: E402  (FastAPI ASGI app, détectée par @vercel/python)
