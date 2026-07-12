"""Tests du serveur HTTP (nouvelle architecture : app desktop autonome).

L'API testée :
  GET  /                  -> page UI (index.html)
  GET  /api/cities        -> liste des villes
  POST /api/cities/add    -> ajoute une ville (sans re-scrap)
  POST /api/cities/remove -> supprime une ville
  POST /api/refresh       -> scrape tout (non testé ici : trop lent / réseau)

On n'appelle PAS /api/refresh dans les tests (réseau + scraping réel).
Les tests ciblent les endpoints rapides et l'isolation AppData.
"""
import json
import urllib.request

import pytest

import config
from server import start_server


@pytest.fixture(autouse=True)
def _temp_appdata(tmp_path, monkeypatch):
    tmp_data = tmp_path / "MeteoVilles"
    monkeypatch.setattr(config, "DATA_DIR", tmp_data)
    monkeypatch.setattr(config, "CITIES_FILE", tmp_data / "villes.json")


@pytest.fixture(scope="module")
def base():
    port, srv = start_server(port=0)
    base = f"http://127.0.0.1:{port}"
    yield base
    srv.shutdown()
    srv.server_close()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.status, r.read().decode("utf-8")


def _post(base, path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def test_serves_app_index(base):
    status, body = _get(base, "/")
    assert status == 200
    assert "<html" in body.lower()


def test_api_cities(base):
    status, body = _get(base, "/api/cities")
    assert status == 200
    data = json.loads(body)
    slugs = [c["slug"] for c in data["cities"]]
    assert "paris" in slugs


def test_api_cities_add_then_present(base):
    _post(base, "/api/cities/add",
          {"url": "https://www.meteociel.fr/previsions/28366/rouen.htm"})
    _, body = _get(base, "/api/cities")
    slugs = [c["slug"] for c in json.loads(body)["cities"]]
    assert "rouen" in slugs


def test_api_cities_add_invalid_url(base):
    status, payload = _post(base, "/api/cities/add", {"url": "not-a-url"})
    assert payload["ok"] is False


def test_api_cities_remove(base):
    _post(base, "/api/cities/add",
          {"url": "https://www.meteociel.fr/previsions/28366/rouen.htm"})
    _, payload = _post(base, "/api/cities/remove", {"slug": "rouen"})
    assert payload["ok"] is True
    _, body = _get(base, "/api/cities")
    slugs = [c["slug"] for c in json.loads(body)["cities"]]
    assert "rouen" not in slugs


def test_404_unknown_endpoint(base):
    import urllib.error
    with pytest.raises(urllib.error.HTTPError):
        _get(base, "/api/unknown")
