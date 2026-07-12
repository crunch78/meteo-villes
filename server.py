"""Serveur HTTP local : API météo + assets web.

Endpoints :
  GET  /                          -> web/index.html (l'UI)
  GET  /api/cities                -> liste des villes
  POST /api/refresh               -> scrape TOUTES les villes (zéro cache), renvoie le HTML de la grille
  POST /api/cities/add {url}      -> ajoute une ville depuis une URL Météociel
  POST /api/cities/remove {slug}  -> supprime une ville
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import config
import renderer
import scraper


def _safe_relative(base_dir, filename: str):
    root = os.path.abspath(base_dir)
    target = os.path.abspath(os.path.join(root, filename))
    if not target.startswith(root + os.sep) and target != root:
        return None
    return target


# --- Scraping ---------------------------------------------------------------
def _scrape_city(city: dict) -> dict:
    """Scrape UNE ville : previsions + tendances + arome + arpege + icond2.
    Les sections horaires (arome/arpege/icond2) échouent silencieusement si
    indisponibles (bouton désactivé côté UI). Une erreur previsions+tendances
    marque la ville en erreur."""
    urls = config.city_urls(city["id"], city["slug"])
    entry = {
        "name": city["name"], "slug": city["slug"],
        "previsions": None, "tendances": None,
        "arome": None, "arpege": None, "icond2": None, "error": None,
    }
    try:
        entry["previsions"] = scraper.get_forecast(urls["previsions"])
    except Exception as e:
        entry["error"] = str(e)
    try:
        entry["tendances"] = scraper.get_forecast(urls["tendances"])
    except Exception as e:
        entry["error"] = entry["error"] or str(e)
    for model in ("arome", "arpege", "icond2"):
        try:
            entry[model] = scraper.get_forecast(urls[model])
        except Exception:
            pass  # échec isolé -> bouton désactivé, pas d'erreur globale
    return entry


def scrape_all() -> list[dict]:
    """Scrape TOUTES les villes. Pas de cache : toujours re-télécharge."""
    cities = config.load_cities()
    out = []
    for c in cities:
        entry = _scrape_city(c)
        ok = bool(entry["previsions"] or entry["tendances"])
        print(f"  - {c['name']}... {'ok' if ok else 'erreur'}")
        out.append(entry)
    return out


def render_grid(cities: list[dict]) -> str:
    """Génère uniquement le HTML de la grille (pour injection AJAX)."""
    return renderer._render_overview(cities, renderer._all_day_labels(cities))


def render_full_page(cities: list[dict]) -> str:
    """Génère la page HTML complète (premier chargement)."""
    return renderer.render_index(cities)


# --- Serveur ----------------------------------------------------------------
def make_handler():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, code, obj):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path, ctype):
            with open(path, "rb") as fh:
                data = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            p = url.path
            if p == "/" or p == "/index.html":
                # Au 1er chargement : scrape tout puis renvoie l'UI avec la grille
                self._send_file(str(config.WEB_DIR / "index.html"),
                                "text/html; charset=utf-8")
                return
            if p == "/api/cities":
                self._json(200, {"cities": config.load_cities()})
                return
            asset = _safe_relative(str(config.WEB_DIR), p.lstrip("/"))
            if asset and os.path.isfile(asset):
                self._send_file(asset, _content_type(asset))
                return
            self._json(404, {"error": "not found"})

        def do_POST(self):
            url = urlparse(self.path)
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "json invalide"})
                return

            if url.path == "/api/refresh":
                cities = scrape_all()
                self._json(200, {"ok": True, "full": render_full_page(cities),
                                 "n": len(cities),
                                 "gfs_run": renderer.gfs_run_label(cities)})
                return
            if url.path == "/api/cities/add":
                res = config.add_city(body.get("url", ""))
                self._json(200, res)
                return
            if url.path == "/api/cities/remove":
                res = config.remove_city(body.get("slug", ""))
                self._json(200, res)
                return
            self._json(404, {"error": "not found"})

    return Handler


def _content_type(path: str) -> str:
    if path.endswith(".css"):
        return "text/css; charset=utf-8"
    if path.endswith(".js"):
        return "application/javascript; charset=utf-8"
    if path.endswith(".html") or path.endswith(".htm"):
        return "text/html; charset=utf-8"
    return "application/octet-stream"


def start_server(port: int = 0):
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler())
    if port == 0:
        port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return port, srv
