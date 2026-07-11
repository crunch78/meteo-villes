import pytest
from pathlib import Path
from scraper import parse_forecast

FIX = Path(__file__).parent / "fixtures"


def _read(name):
    return (FIX / name).read_text(encoding="iso-8859-1")


def test_parse_previsions_has_days():
    data = parse_forecast(_read("vigan_previsions.htm"))
    assert "days" in data
    assert len(data["days"]) >= 3


def test_day_has_date_label_and_slots():
    data = parse_forecast(_read("vigan_previsions.htm"))
    day = data["days"][0]
    assert day["date_label"], "date_label vide"
    assert len(day["slots"]) >= 1


def test_slot_fields_types():
    data = parse_forecast(_read("vigan_previsions.htm"))
    slot = data["days"][0]["slots"][0]
    assert isinstance(slot["temp"], int)
    assert slot["heure"]
    assert slot["temps_label"]
    assert isinstance(slot["vent_moy"], int)
    assert isinstance(slot["humidite"], int)
    assert isinstance(slot["pression"], int)


def test_pluie_field_keeps_dash_or_number():
    data = parse_forecast(_read("vigan_previsions.htm"))
    slot = data["days"][0]["slots"][0]
    assert "pluie" in slot  # "--" -> None, ou int


def test_tendances_uses_same_parser():
    data = parse_forecast(_read("vigan_tendances.htm"))
    assert len(data["days"]) >= 3
    assert data["days"][0]["slots"][0]["temps_label"]


def test_updated_at_extracted():
    data = parse_forecast(_read("vigan_previsions.htm"))
    assert data.get("updated_at")
