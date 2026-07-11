"""Tests du module config (nouvelle architecture AppData).

Les villes sont maintenant persistées dans %APPDATA%/MeteoVilles/villes.json.
Pour éviter de polluer le vrai AppData pendant les tests, on redirige
config.DATA_DIR / CITIES_FILE vers un dossier temporaire.
"""
import json
from pathlib import Path

import pytest

import config


@pytest.fixture(autouse=True)
def _temp_appdata(tmp_path, monkeypatch):
    """Isole les tests du vrai AppData de Chris."""
    tmp_data = tmp_path / "MeteoVilles"
    monkeypatch.setattr(config, "DATA_DIR", tmp_data)
    monkeypatch.setattr(config, "CITIES_FILE", tmp_data / "villes.json")


# --- Persistance ------------------------------------------------------------
def test_load_cities_creates_file_on_first_run():
    cities = config.load_cities()
    assert config.CITIES_FILE.exists(), "villes.json doit être créé au 1er lancement"
    assert len(cities) == len(config.DEFAULT_CITIES)


def test_load_cities_returns_defaults_on_first_run():
    cities = config.load_cities()
    slugs = [c["slug"] for c in cities]
    assert "rouen" in slugs
    assert "lanuejols" in slugs


def test_each_city_has_required_fields():
    for c in config.load_cities():
        assert {"slug", "name", "id"} <= set(c.keys())
        assert c["slug"] and c["name"] and isinstance(c["id"], int)


# --- Parsing URL Météociel --------------------------------------------------
@pytest.mark.parametrize("url,expected_slug,expected_id", [
    ("https://www.meteociel.fr/previsions/10232/lanuejols.htm", "lanuejols", 10232),
    ("https://www.meteociel.fr/previsions-arome-1h/28366/rouen.htm", "rouen", 28366),
    ("https://www.meteociel.fr/tendances/10439/le_vigan.htm", "le_vigan", 10439),
    ("https://www.meteociel.fr/previsions-arpege-1h/10281/nimes.htm", "nimes", 10281),
    ("https://www.meteociel.fr/previsions-icond2/10232/lanuejols.htm", "lanuejols", 10232),
])
def test_parse_meteociel_url(url, expected_slug, expected_id):
    result = config.parse_meteociel_url(url)
    assert result is not None
    assert result["slug"] == expected_slug
    assert result["id"] == expected_id


def test_parse_meteociel_url_invalid():
    assert config.parse_meteociel_url("https://google.com") is None
    assert config.parse_meteociel_url("pas une url") is None
    assert config.parse_meteociel_url("") is None


def test_slug_to_name():
    assert config._slug_to_name("le_vigan") == "Le Vigan"
    assert config._slug_to_name("rouen") == "Rouen"


# --- Ajout / suppression ----------------------------------------------------
def test_add_city_success():
    config.load_cities()  # init
    res = config.add_city("https://www.meteociel.fr/previsions/25370/paris.htm")
    assert res["ok"] is True
    assert res["city"]["slug"] == "paris"
    assert res["city"]["id"] == 25370
    slugs = [c["slug"] for c in config.load_cities()]
    assert "paris" in slugs


def test_add_city_duplicate_rejected():
    config.load_cities()
    # rouen est dans les defaults
    res = config.add_city("https://www.meteociel.fr/previsions/28366/rouen.htm")
    assert res["ok"] is False
    assert "déjà" in res["error"]


def test_add_city_invalid_url():
    config.load_cities()
    res = config.add_city("https://google.com")
    assert res["ok"] is False


def test_remove_city_success():
    config.load_cities()
    res = config.remove_city("rouen")
    assert res["ok"] is True
    slugs = [c["slug"] for c in config.load_cities()]
    assert "rouen" not in slugs


def test_remove_city_not_found():
    config.load_cities()
    res = config.remove_city("ville_inexistante")
    assert res["ok"] is False


# --- URLs -------------------------------------------------------------------
def test_city_urls_has_all_models():
    urls = config.city_urls(10232, "lanuejols")
    for model in ("previsions", "tendances", "arome", "arpege", "icond2"):
        assert model in urls
        assert "10232" in urls[model]
        assert "lanuejols" in urls[model]
