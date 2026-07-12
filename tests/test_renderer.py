from renderer import (render_index, weather_emoji, day_summary, temp_color,
                      _city_days, _all_day_labels, gfs_run_label)
import re

SAMPLE_PREV = {
    "updated_at": "17:59 (run GFS de 12Z)",
    "days": [
        {"date_label": "Jeu 02", "slots": [
            {"heure": "02:00", "temp": 17, "ressenti": 17, "vent_dir": "N",
             "vent_moy": 10, "vent_raf": 20, "pluie": None, "humidite": 60,
             "pression": 1021, "temps_label": "Ciel clair"},
            {"heure": "14:00", "temp": 30, "ressenti": 30, "vent_dir": "N",
             "vent_moy": 25, "vent_raf": 35, "pluie": None, "humidite": 21,
             "pression": 1017, "temps_label": "Ciel clair"},
        ]},
        {"date_label": "Ven 03", "slots": [
            {"heure": "14:00", "temp": 28, "ressenti": 28, "vent_dir": "NO",
             "vent_moy": 20, "vent_raf": 40, "pluie": 2, "humidite": 50,
             "pression": 1018, "temps_label": "Averses"},
        ]},
    ],
}
SAMPLE_TEND = {
    "updated_at": "18:39 (run GFS de 12Z)",
    "days": [
        {"date_label": "Lun 06", "slots": [
            {"heure": "14:00", "temp": 36, "ressenti": 36, "vent_dir": "NO",
             "vent_moy": 5, "vent_raf": 10, "pluie": None, "humidite": 15,
             "pression": 1016, "temps_label": "Ciel clair"},
        ]},
    ],
}


def _slot(heure, temp, **kw):
    base = {"heure": heure, "temp": temp, "ressenti": temp, "vent_dir": "N",
            "vent_moy": 10, "vent_raf": 20, "pluie": None, "humidite": 50,
            "pression": 1018, "temps_label": "Ciel clair"}
    base.update(kw)
    return base


def cities_sample():
    return [
        {"name": "Le Vigan", "slug": "le_vigan",
         "previsions": SAMPLE_PREV, "tendances": SAMPLE_TEND, "error": None},
        {"name": "Rouen", "slug": "rouen",
         "previsions": SAMPLE_PREV, "tendances": None, "error": None},
    ]


def test_day_summary_min_max_emoji_rain():
    s = day_summary(SAMPLE_PREV["days"][0]["slots"])
    assert s["tmax"] == 30
    assert s["tmin"] == 17
    assert s["emoji"] == "☀️"
    assert s["rain"] == 0


def test_day_summary_rain_cumulates():
    s = day_summary(SAMPLE_PREV["days"][1]["slots"])
    assert s["rain"] == 2
    assert s["emoji"] == "🌧️"


def test_day_summary_includes_wind_and_humidity():
    s = day_summary(SAMPLE_PREV["days"][0]["slots"])
    assert s["vent"] == 35   # rafale max
    assert s["humid"] == 21  # humidité min


def test_day_summary_none_for_empty():
    assert day_summary([]) is None


def test_overlapping_day_merges_slots_regression():
    """Bug 'jour 6' : Lun 06 apparaît partiellement en prévisions (02:00/20°)
    et complètement en tendances (14:00/36°). Les créneaux doivent fusionner
    et la synthèse refléter l'ensemble (tmax=36, tmin=20)."""
    city = {"name": "X", "slug": "x", "error": None,
            "previsions": {"days": [{"date_label": "Lun 06",
                                     "slots": [_slot("02:00", 20)]}]},
            "tendances": {"days": [{"date_label": "Lun 06",
                                    "slots": [_slot("14:00", 36, vent_raf=12)]}]}}
    by = dict(_city_days(city))
    s = day_summary(by["Lun 06"])
    assert s["tmax"] == 36
    assert s["tmin"] == 20
    assert s["vent"] == 20  # max des rafales (20 du slot 02:00)


def test_city_days_dedupes_by_heure():
    city = {"name": "X", "slug": "x", "error": None,
            "previsions": {"days": [{"date_label": "Jeu 02",
                                     "slots": [_slot("14:00", 30)]}]},
            "tendances": {"days": [{"date_label": "Jeu 02",
                                    "slots": [_slot("14:00", 99)]}]}}  # même heure
    by = dict(_city_days(city))
    assert len(by["Jeu 02"]) == 1  # pas de doublon d'heure


def test_temp_color_is_hsl_string():
    c = temp_color(35)
    assert c.startswith("hsl")


def _hsl(s):
    """Extrait (hue, sat) depuis une chaîne hsl(h,s%,l%)."""
    body = s[s.index("(") + 1:s.index(")")]
    h, sat, _l = [p.strip() for p in body.split(",")]
    return float(h), float(sat.rstrip("%"))


def test_temp_color_colder_than_warmer():
    """Couleur continue : une température froide est plus bleue (hue haute)
    qu'une température chaude (hue basse)."""
    assert _hsl(temp_color(2))[0] > _hsl(temp_color(35))[0]


def test_temp_color_more_vivid_at_extremes():
    """L'intensité (saturation) augmente quand on s'éloigne de la neutralité."""
    mild = _hsl(temp_color(18))[1]
    extreme = _hsl(temp_color(42))[1]
    assert extreme > mild


def test_render_grid_has_cities_and_days():
    from bs4 import BeautifulSoup
    html_out = render_index(cities_sample())
    for city in ("Le Vigan", "Rouen"):
        assert city in html_out
    soup = BeautifulSoup(html_out, "lxml")
    head_text = " ".join(d.get_text(" ", strip=True)
                         for d in soup.select(".grid .dhead"))
    for dname, dnum in (("Jeu", "02"), ("Ven", "03"), ("Lun", "06")):
        assert dname in head_text and dnum in head_text


def test_render_grid_adapts_to_city_count():
    """La grille doit embarquer un grid-template dimensionné au nombre de villes
    et de jours, pour auto-adapter la taille des cases."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(render_index(cities_sample()), "lxml")
    style = soup.select_one(".grid").get("style", "").replace(" ", "")
    assert "repeat(3,minmax(0,1fr))" in style   # 3 jours (Jeu02,Ven03,Lun06)
    assert "repeat(2,minmax(0,1fr))" in style   # 2 villes


def test_render_shows_secondary_info():
    """Le 'reste' (vent/pluie/humidité) reste visible en secondaire."""
    html_out = render_index(cities_sample())
    # la journée pluvieuse (Ven 03, 2mm) doit montrer la pluie
    assert "🌧" in html_out or "💧" in html_out
    # vent présent
    assert "💨" in html_out


def test_render_no_hourly_detail():
    html_out = render_index(cities_sample())
    assert "data-toggle" not in html_out
    assert "detail-le_vigan" not in html_out


def test_render_is_well_formed():
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(render_index(cities_sample()), "lxml")
    assert soup.find()
    assert soup.find("div", class_="grid")


def test_render_handles_error_city():
    cities = [{"name": "Bordeaux", "slug": "bordeaux",
               "previsions": None, "tendances": None, "error": "timeout"}]
    html_out = render_index(cities)
    assert "Bordeaux" in html_out
    assert "timeout" in html_out


def test_weather_emoji_mapping():
    assert weather_emoji("Ciel clair") != weather_emoji("Pluie")
    assert weather_emoji("inconnu")


def test_gfs_run_label_from_previsions():
    """L'info de run GFS vient en priorité des prévisions."""
    assert gfs_run_label(cities_sample()) == "17:59 (run GFS de 12Z)"


def test_gfs_run_label_fallback_tendances():
    """Si previsions n'a pas d'updated_at, on retombe sur tendances."""
    cities = [{"name": "X", "slug": "x",
               "previsions": {"days": [], "updated_at": ""},
               "tendances": {"days": [], "updated_at": "18:39 (run GFS de 12Z)"}}]
    assert gfs_run_label(cities) == "18:39 (run GFS de 12Z)"


def test_gfs_run_label_empty_when_no_data():
    """Aucune donnée -> chaîne vide (badge masqué côté UI)."""
    assert gfs_run_label([]) == ""
    assert gfs_run_label([{"name": "X", "slug": "x",
                           "previsions": None, "tendances": None}]) == ""
