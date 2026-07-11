import re
import time

import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
ENCODING = "iso-8859-1"

_INT_RE = re.compile(r"-?\d+")


def _to_int(text: str):
    """Extrait le 1er entier d'un texte, ou None."""
    m = _INT_RE.search(text or "")
    return int(m.group()) if m else None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def fetch_html(url: str, retries: int = 1, timeout: int = 15) -> str:
    last = None
    for _ in range(retries + 1):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
            r.raise_for_status()
            r.encoding = ENCODING
            return r.text
        except requests.RequestException as e:
            last = e
            time.sleep(1)
    raise last


def _find_forecast_table(soup: BeautifulSoup):
    """La table de prévisions est une table 'feuille' (sans <table> imbriquée)
    contenant des pictos météo (/picto/). On évite ainsi la table de layout qui
    l'englobe et dont get_text() engloutit toute la page."""
    for table in soup.find_all("table"):
        if table.find("table"):  # table de layout avec tables imbriquées -> skip
            continue
        if table.find("img", src=re.compile("/picto/")):
            return table
    return None


def _find_updated_at(soup: BeautifulSoup) -> str:
    text = _clean(soup.get_text(" "))
    m = re.search(r"(\d{1,2}:\d{2}\s*\(run[^)]*\))", text)
    if m:
        return _clean(m.group(1))
    return ""


def _parse_slot(tds):
    """tds = liste de BeautifulSoup <td> d'une ligne de données (sans la cellule jour).
    Ordre attendu : Heure, Temp, Temp ressen., Vent(dir img), Vent moy, Vent raf,
                    Pluie, Humidité, Pression, Temps(img)."""
    texts = [_clean(td.get_text()) for td in tds]
    if len(texts) < 8:
        return None

    def _img_alt(td):
        img = td.find("img")
        return _clean(img.get("alt", "")) if img else ""

    heure = texts[0]
    temp = _to_int(texts[1])
    ressenti = _to_int(texts[2])
    vent_dir = _img_alt(tds[3])
    vent_moy = _to_int(texts[4])
    vent_raf = _to_int(texts[5])
    pluie_raw = texts[6]
    pluie = None if pluie_raw.strip() in ("--", "-", "") else _to_int(pluie_raw)
    humidite = _to_int(texts[7])
    pression = _to_int(texts[8]) if len(texts) > 8 else None
    temps_label = _img_alt(tds[-1]) if tds else ""

    return {
        "heure": heure,
        "temp": temp if temp is not None else 0,
        "ressenti": ressenti,
        "vent_dir": vent_dir,
        "vent_moy": vent_moy if vent_moy is not None else 0,
        "vent_raf": vent_raf,
        "pluie": pluie,
        "humidite": humidite if humidite is not None else 0,
        "pression": pression if pression is not None else 0,
        "temps_label": temps_label,
    }


def parse_forecast(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    table = _find_forecast_table(soup)
    flat = []  # liste de (date_label, slot)
    if table:
        current_day = ""
        for tr in table.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            if not tds:
                continue
            txts = [_clean(td.get_text()) for td in tds]
            # Ligne de header : contient 'Heure' ou 'dir.'/'moy.'/'raf.' -> skip
            if any(t in ("Heure", "dir.", "moy.", "raf.") for t in txts):
                continue
            idx = 0
            # Cellule jour : porte l'attribut rowspan (ex. "Jeu02" via <br>)
            first = tds[0]
            if first.has_attr("rowspan"):
                current_day = re.sub(
                    r"([A-Za-zÀ-ÿ])(\d)", r"\1 \2", _clean(first.get_text())
                )
                idx = 1
            if current_day and idx < len(tds):
                slot = _parse_slot(tds[idx:])
                if slot is not None:
                    flat.append((current_day, slot))

    # Regroupe par jour (préserve l'ordre)
    grouped = []
    by_label = {}
    for label, slot in flat:
        if label not in by_label:
            entry = {"date_label": label, "slots": []}
            by_label[label] = entry
            grouped.append(entry)
        by_label[label]["slots"].append(slot)

    return {
        "updated_at": _find_updated_at(soup),
        "days": grouped,
    }


def get_forecast(url: str) -> dict:
    return parse_forecast(fetch_html(url))
