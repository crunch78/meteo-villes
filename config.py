"""Configuration & persistance des villes.

Les villes sont stockées dans %APPDATA%\\MeteoVilles\\villes.json (caché,
invisible depuis le bureau). L'exe est ainsi 100 % autonome : un seul fichier,
la liste des villes revient à chaque lancement sans rien voir à côté de l'exe.
"""
import json
import os
import re
import sys
from pathlib import Path

METEOCIEL_BASE = "https://www.meteociel.fr"

# --- Dossiers ---------------------------------------------------------------
# En mode compilé (exe), les assets web sont embarqués à côté de l'exe via
# PyInstaller (_MEIPASS en runtime). En source, on prend les fichiers du repo.
def _bundle_dir() -> Path:
    """Dossier des assets embarqués (web/index.html, web/app.js...)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent

WEB_DIR = _bundle_dir() / "web"

# Données persistées (villes) : %APPDATA%\MeteoVilles\
def _appdata_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "MeteoVilles"

DATA_DIR = _appdata_dir()
CITIES_FILE = DATA_DIR / "villes.json"


# --- Villes par défaut (1er lancement, AppData vide) ------------------------
DEFAULT_CITIES = [
    {"slug": "paris", "name": "Paris", "id": 27817},
    {"slug": "marseille", "name": "Marseille", "id": 3520},
    {"slug": "lyon", "name": "Lyon", "id": 25627},
    {"slug": "toulouse", "name": "Toulouse", "id": 10979},
    {"slug": "nice", "name": "Nice", "id": 2005},
    {"slug": "nantes", "name": "Nantes", "id": 15569},
]


def city_urls(meteociel_id: int, slug: str) -> dict:
    """Toutes les URLs Météociel pour une ville."""
    return {
        "previsions": f"{METEOCIEL_BASE}/previsions/{meteociel_id}/{slug}.htm",
        "tendances": f"{METEOCIEL_BASE}/tendances/{meteociel_id}/{slug}.htm",
        "arome": f"{METEOCIEL_BASE}/previsions-arome-1h/{meteociel_id}/{slug}.htm",
        "arpege": f"{METEOCIEL_BASE}/previsions-arpege-1h/{meteociel_id}/{slug}.htm",
        "icond2": f"{METEOCIEL_BASE}/previsions-icond2/{meteociel_id}/{slug}.htm",
    }


def _slug_to_name(slug: str) -> str:
    """Reconstitue un nom lisible depuis un slug (le_vigan -> Le Vigan)."""
    return " ".join(w.capitalize() for w in slug.split("_"))


# --- Persistance villes -----------------------------------------------------
def load_cities() -> list[dict]:
    """Lit villes.json depuis AppData. Crée le dossier + fichier par défaut
    au 1er lancement (fichier absent ou invalide)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CITIES_FILE.exists():
        try:
            data = json.loads(CITIES_FILE.read_text(encoding="utf-8"))
            cities = data.get("cities", [])
            if cities:
                return _normalize(cities)
        except (OSError, ValueError):
            pass
    save_cities(DEFAULT_CITIES)
    return list(DEFAULT_CITIES)


def save_cities(cities: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CITIES_FILE.write_text(
        json.dumps({"cities": _normalize(cities)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _normalize(cities: list[dict]) -> list[dict]:
    """Assure id entier + name présent + slug présent."""
    out = []
    for c in cities:
        slug = c.get("slug") or ""
        name = c.get("name") or _slug_to_name(slug)
        try:
            cid = int(c.get("id") or c.get("meteociel_id") or 0)
        except (TypeError, ValueError):
            cid = 0
        if slug and cid:
            out.append({"slug": slug, "name": name, "id": cid})
    return out


# --- Ajout / suppression de ville depuis une URL Météociel ------------------
# Une URL Météociel contient toujours /<id>/<slug>.htm quelque part, ex:
#   /previsions/10232/lanuejols.htm
#   /previsions-arome-1h/10232/lanuejols.htm
#   /tendances/10232/lanuejols.htm
_URL_RE = re.compile(r"/(\d+)/([a-z0-9_\-]+)\.htm", re.IGNORECASE)


def parse_meteociel_url(url: str) -> dict | None:
    """Extrait {slug, name, id} d'une URL Météociel. Retourne None si l'URL
    ne correspond pas au format attendu."""
    m = _URL_RE.search(url.strip())
    if not m:
        return None
    cid = int(m.group(1))
    slug = m.group(2).lower()
    return {"slug": slug, "name": _slug_to_name(slug), "id": cid}


def add_city(url: str) -> dict:
    """Ajoute une ville depuis une URL. Retourne
    {ok, city?, error?}. Refuse les doublons (même id)."""
    parsed = parse_meteociel_url(url)
    if not parsed:
        return {"ok": False, "error": "URL invalide. Colle un lien meteociel.fr contenant /<id>/<ville>.htm"}
    cities = load_cities()
    if any(c["id"] == parsed["id"] for c in cities):
        return {"ok": False, "error": f"{parsed['name']} est déjà dans ta liste."}
    cities.append(parsed)
    save_cities(cities)
    return {"ok": True, "city": parsed}


def remove_city(slug: str) -> dict:
    """Supprime une ville par son slug. Retourne {ok, removed?}."""
    cities = load_cities()
    remaining = [c for c in cities if c["slug"] != slug]
    if len(remaining) == len(cities):
        return {"ok": False, "error": "ville introuvable"}
    save_cities(remaining)
    return {"ok": True, "removed": slug}
