import base64
import html
import json
import re
from pathlib import Path

# temps_label Météociel -> emoji.
_EMOJI_RULES = [
    ("orage", "⛈️"),
    ("averse", "🌧️"),
    ("pluie", "🌧️"),
    ("neige", "❄️"),
    ("granule", "🌨️"),
    ("grêle", "🌨️"),
    ("brouillard", "🌫️"),
    ("brume", "🌫️"),
    ("couvert", "☁️"),
    ("nuageux", "☁️"),
    ("peu nuageux", "🌤️"),
    ("ciel clair", "☀️"),
    ("dégagé", "☀️"),
    ("soleil", "☀️"),
]
_FALLBACK = "🌡️"

# --- Images de fond par temps (8 catégories regroupées) ---------------------
# Mapping temps_label Météociel -> clé d'image. L'image s'affiche en bandeau
# (~45% haut) dans la case, fondue vers la couleur thermique en dessous.
# Ordre important : les orages/grêle sont testés avant pluie/neige car un
# "averse de grêle" contient à la fois "averse" et "grêle".
_WEATHER_BG_RULES = [
    ("grele",      ["grêle", "grele", "verglas"]),
    ("orage",      ["orage"]),
    ("neige",      ["neige", "granule"]),
    ("pluie",      ["averse", "pluie"]),
    ("brouillard", ["brouillard", "brume"]),
    # ensoleille AVANT couvert : "peu nuageux" contient "nuageux" et doit
    # matcher ensoleille, pas couvert.
    ("ensoleille", ["ciel clair", "peu nuageux", "dégagé", "soleil"]),
    ("couvert",    ["couvert", "nuageux"]),
    ("mitige",     ["mitigé", "mitige", "voilé", "voile"]),
]


def _weather_bg_key(label: str) -> str:
    """Retourne la clé d'image de fond pour un temps_label, ou '' si aucun."""
    low = (label or "").lower()
    for key, words in _WEATHER_BG_RULES:
        if any(w in low for w in words):
            return key
    return ""


def _load_weather_imgs() -> dict:
    """Précharge les 8 images en data URI base64 au démarrage du module.
    Retourne {clé: 'data:image/jpeg;base64,...'}."""
    img_dir = Path(__file__).resolve().parent / "web" / "img" / "weather"
    out = {}
    for key in ("ensoleille", "mitige", "couvert", "brouillard",
                "pluie", "neige", "orage", "grele"):
        p = img_dir / f"{key}.jpg"
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            out[key] = f"data:image/jpeg;base64,{b64}"
    return out


_WEATHER_BG_IMGS = _load_weather_imgs()


# Échelle continue de température -> teinte (hue HSL).
_T_LO, _T_HI = -10, 45          # plage perceptuelle
_T_NEUTRAL = 18                  # température "neutre" (saturation minimale)


def weather_emoji(label: str) -> str:
    low = (label or "").lower()
    for key, emo in _EMOJI_RULES:
        if key in low:
            return emo
    return _FALLBACK


def _esc(s) -> str:
    return html.escape("" if s is None else str(s))


def temp_color(temp) -> str:
    """Couleur HSL continue selon la température.
    Hue : bleu (froid) -> rouge (chaud). Saturation : plus vive aux extrêmes
    (intensité = écart à la neutralité). Retourne la couleur 'texte' vive."""
    if temp is None:
        return "hsl(210,8%,45%)"
    x = max(0.0, min(1.0, (temp - _T_LO) / (_T_HI - _T_LO)))
    hue = (1 - x) * 240            # 240 (bleu) -> 0 (rouge)
    intensity = abs(temp - _T_NEUTRAL) / 30.0
    sat = round(min(100, 60 + max(0.0, min(1.0, intensity)) * 40), 1)  # 60 .. 100
    light = 32
    return f"hsl({hue:.0f},{sat}%,{light}%)"


def temp_bg(temp) -> str:
    """Fond translucide dérivé de la teinte (pour le verre dépoli de la cellule)."""
    if temp is None:
        return "hsla(210,20%,94%,0.5)"
    x = max(0.0, min(1.0, (temp - _T_LO) / (_T_HI - _T_LO)))
    hue = (1 - x) * 240
    intensity = abs(temp - _T_NEUTRAL) / 30.0
    sat = round(min(100, 80 + max(0.0, min(1.0, intensity)) * 20), 1)
    light = round(78 - max(0.0, min(1.0, intensity)) * 12, 1)
    return f"hsla({hue:.0f},{sat}%,{light}%,0.6)"


def temp_border(temp) -> str:
    """Couleur de bordure opaque dérivée de la température (hue thermique).
    Plus saturée et profonde que le fond, pour un contour visible."""
    if temp is None:
        return "hsl(210,20%,60%)"
    x = max(0.0, min(1.0, (temp - _T_LO) / (_T_HI - _T_LO)))
    hue = (1 - x) * 240
    return f"hsl({hue:.0f},75%,50%)"


def day_summary(slots: list) -> dict:
    """Synthétise une journée : temp max/min, emoji (créneau après-midi),
    pluie cumulée, vent (rafale max), humidité (min). Gère les slots absents."""
    if not slots:
        return None
    temps = [s["temp"] for s in slots if isinstance(s.get("temp"), (int, float))]
    rains = [s["pluie"] for s in slots if isinstance(s.get("pluie"), (int, float))]
    rafales = [s["vent_raf"] for s in slots if isinstance(s.get("vent_raf"), (int, float))]
    hums = [s["humidite"] for s in slots if isinstance(s.get("humidite"), (int, float))]
    rep = None
    for pref in ("14:00", "13:00", "15:00", "12:00", "11:00"):
        for s in slots:
            if s.get("heure") == pref:
                rep = s
                break
        if rep:
            break
    if not rep:
        rep = slots[len(slots) // 2]
    return {
        "tmax": max(temps) if temps else None,
        "tmin": min(temps) if temps else None,
        "emoji": weather_emoji(rep.get("temps_label")),
        "rain": round(sum(rains), 1) if rains else 0,
        "vent": max(rafales) if rafales else None,
        "humid": min(hums) if hums else None,
        "label": rep.get("temps_label", ""),
    }


def _city_days(city: dict) -> list:
    """Merge prévisions puis tendances. Pour un même date_label, FUSIONNE les
    créneaux (déduction des doublons par heure) — corrige le bug du jour
    'à cheval' entre les deux pages (ex. Lun 06 partiel en prévisions)."""
    merged = {}      # date_label -> {heure: slot}
    order = []       # ordre d'apparition des date_label
    for section in ("previsions", "tendances"):
        data = city.get(section)
        if not data:
            continue
        for d in data["days"]:
            lbl = d["date_label"]
            if lbl not in merged:
                merged[lbl] = {}
                order.append(lbl)
            for s in d["slots"]:
                h = s.get("heure")
                if h not in merged[lbl]:   # pas de doublon d'heure
                    merged[lbl][h] = s
    return [(lbl, list(merged[lbl].values())) for lbl in order]


def _has_model_data(city: dict, model: str) -> bool:
    data = city.get(model)
    return bool(data and data.get("days"))


def gfs_run_label(cities: list) -> str:
    """Renvoie l'info de run GFS (ex. « 17:59 (run GFS de 12Z) ») extraite en
    scrapant les pages previsions/tendances. La grille principale est alimentée
    par GFS mais n'a pas de modale — on remonte donc le champ updated_at jusqu'au
    header pour indiquer la fraîcheur des données. Vide si indisponible."""
    for c in cities:
        for section in ("previsions", "tendances"):
            data = c.get(section)
            if data and data.get("updated_at"):
                return data["updated_at"]
    return ""


def _city_modal_btns(city: dict) -> str:
    """Petits boutons A (AROME) / P (ARPEGE) / D (ICON-D2) pour ouvrir la
    modale horaire, + ❌ supprimer la ville. Désactivés (disabled, grisés) si
    le modèle n'a pas de donnée pour la ville."""
    btns = []
    for model, label, full in (
        ("arome", "A", "AROME"),
        ("arpege", "P", "ARPEGE"),
        ("icond2", "D", "ICON-D2"),
    ):
        if _has_model_data(city, model):
            btns.append(
                f"<button class='mdl-btn' data-city='{_esc(city['slug'])}' "
                f"data-model='{model}' title='{full} heure par heure'>{label}</button>"
            )
        else:
            btns.append(
                f"<button class='mdl-btn' disabled title='{full} indisponible'>{label}</button>"
            )
    # Bouton supprimer la ville (communique avec l'app shell via postMessage).
    btns.append(
        f"<button class='mdl-btn del' data-del='{_esc(city['slug'])}' "
        f"data-name='{_esc(city['name'])}' title=\"Supprimer {_esc(city['name'])}\">×</button>"
    )
    return f"<span class='mdl-btns'>{''.join(btns)}</span>"


def _all_day_labels(cities: list) -> list:
    seen = set()
    labels = []
    for c in cities:
        for lbl, _ in _city_days(c):
            if lbl not in seen:
                seen.add(lbl)
                labels.append(lbl)
    return labels


def _grid_cell(summary, col: int = 0) -> str:
    if not summary:
        return "<td class='cell empty'>—</td>"
    tmax, tmin = summary["tmax"], summary["tmin"]
    bg = temp_bg(tmax)
    fg = temp_color(tmax)
    border = temp_border(tmax)
    delay = round(col * 0.035, 3)  # cascade d'apparition gauche -> droite

    meta = []
    if summary.get("vent") is not None:
        meta.append(f"<span title='Rafales max (km/h)'>💨{_esc(summary['vent'])}</span>")
    if summary["rain"] > 0:
        meta.append(f"<span class='r' title='Pluie cumulée (mm)'>🌧{_esc(summary['rain'])}</span>")
    if summary.get("humid") is not None:
        meta.append(f"<span title='Humidité min (%)'>{_esc(summary['humid'])}%</span>")
    meta_html = f"<div class='meta'>{''.join(meta)}</div>" if meta else ""

    # Bandeau image de temps (~45% haut) si une image correspond au temps.
    bg_key = _weather_bg_key(summary.get("label", ""))
    img_uri = _WEATHER_BG_IMGS.get(bg_key, "")
    # Hue thermique pour le fondu bas de l'image (cohérence avec la case).
    m = re.search(r"hsla\((\d+),", bg)
    hue = m.group(1) if m else "210"
    img_band = ""
    if img_uri:
        img_band = (
            f"<div class='wband' style='background-image:url(\"{img_uri}\")'>"
            f"<div class='wfade' style='background:linear-gradient(180deg,"
            f"transparent 55%,hsla({hue},80%,77%,0.95) 100%)'></div></div>"
        )

    return (
        f"<div class='cell' style='background:{bg};border-color:{border};animation-delay:{delay}s' title='{_esc(summary['label'])}'>"
        f"{img_band}"
        f"<span class='sheen'></span>"
        f"<span class='emoji'>{summary['emoji']}</span>"
        f"<span class='tmax' style='color:{fg}'>{_esc(tmax)}°</span>"
        f"<span class='tmin'>{_esc(tmin)}°</span>"
        f"{meta_html}</div>"
    )


def _render_overview(cities: list, labels: list) -> str:
    n_cities = len(cities)
    n_days = len(labels)
    items = ['<div class="cell corner"></div>']
    for lbl in labels:
        parts = lbl.split()
        items.append(
            f"<div class='cell dhead'><span class='dnum'>{_esc(parts[-1])}</span>"
            f"<span class='dname'>{_esc(parts[0])}</span></div>"
        )
    for c in cities:
        err = c.get("error")
        days = _city_days(c)
        if err and not days:
            items.append(
                f"<div class='cell name errored'>📍 {_esc(c['name'])}"
                f"<span class='errmsg'>⚠️ {_esc(err)}</span></div>"
            )
            items.extend("<div class='cell empty'>—</div>" for _ in labels)
            continue
        items.append(
            f"<div class='cell name'>📍 {_esc(c['name'])}{_city_modal_btns(c)}</div>"
        )
        by_lbl = dict(days)
        for i, lbl in enumerate(labels):
            items.append(_grid_cell(day_summary(by_lbl.get(lbl)), col=i))
    return (
        "<div class='overview'>"
        f"<div class='grid' style='"
        f"grid-template-columns:var(--name-w,150px) repeat({n_days},minmax(0,1fr));"
        f"grid-template-rows:auto repeat({n_cities},minmax(0,1fr))'>"
        + "".join(items) + "</div></div>"
    )


_CSS = """
:root{
  --ink:#0d2438;--ink-soft:#3a5470;
  --accent:#1e40af;--accent-light:#3b82f6;
  --danger:#dc2626;--danger-soft:rgba(220,38,38,.3);
  --namebg:linear-gradient(135deg,rgba(13,34,54,.9),rgba(28,72,108,.9));
  --hdrbg:linear-gradient(135deg,rgba(16,42,67,.88),rgba(33,80,111,.88));
  --radius:14px;--radius-sm:10px;
}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{font-family:'Segoe UI','Inter',system-ui,-apple-system,sans-serif;color:var(--ink);
  -webkit-font-smoothing:antialiased;overflow:hidden;position:relative;
  background:linear-gradient(160deg,#cfe7fb 0%,#9fc6e4 55%,#bcdcf2 100%)}
/* Blobs animés derrière le verre dépoli */
body::before{content:"";position:fixed;inset:-25%;z-index:0;pointer-events:none;
  background:
    radial-gradient(38% 32% at 18% 22%,#c9f4ff 0%,transparent 60%),
    radial-gradient(42% 38% at 86% 78%,#ffe2bd 0%,transparent 60%),
    radial-gradient(34% 30% at 72% 12%,#d8f7e4 0%,transparent 60%),
    radial-gradient(30% 28% at 12% 88%,#cdddff 0%,transparent 60%);
  filter:blur(14px);animation:drift 28s ease-in-out infinite alternate}
@keyframes drift{0%{transform:translate3d(-3%,-2%,0) scale(1) rotate(0deg)}
  100%{transform:translate3d(4%,3%,0) scale(1.1) rotate(6deg)}}
.wrap{position:relative;z-index:1;height:100vh;display:flex;flex-direction:column}

header.hero{display:flex;align-items:center;gap:16px;padding:12px 20px;flex:0 0 auto;
  background:rgba(255,255,255,.26);backdrop-filter:blur(14px) saturate(1.25);
  -webkit-backdrop-filter:blur(14px) saturate(1.25);
  border-bottom:1px solid #ffffff77;box-shadow:0 4px 20px #0001}
header.hero .logo{font-size:1.8rem;filter:drop-shadow(0 2px 3px #0002);animation:floaty 6s ease-in-out infinite}
@keyframes floaty{50%{transform:translateY(-4px)}}
header.hero h1{margin:0;font-size:1.45rem;font-weight:800;letter-spacing:-.02em;color:#fff;
  text-shadow:0 2px 8px #0004}
header.hero .sub{margin:4px 0 0;font-size:.8rem;opacity:.9;font-weight:500;color:#eaf6ff}
.legend{margin-left:auto;display:flex;align-items:center;gap:10px;font-size:.68rem;
  font-weight:700;color:#0d2438;background:rgba(255,255,255,.45);padding:6px 14px;border-radius:999px;
  border:1px solid #ffffff55}
.legend .bar{width:160px;height:10px;border-radius:6px;
  background:linear-gradient(90deg,hsl(240,80%,55%),hsl(180,75%,50%),hsl(120,60%,48%),
    hsl(55,85%,52%),hsl(25,90%,53%),hsl(0,88%,55%));box-shadow:inset 0 0 0 1px #00000018}

/* Grille plein écran auto-adaptive */
.overview{flex:1;min-height:0;background:transparent;padding:8px}
.grid{display:grid;width:100%;height:100%;gap:6px}
.grid .corner{grid-column:1;grid-row:1;position:sticky;top:0;left:0;z-index:5;
  background:var(--namebg)}
.grid .dhead{background:var(--hdrbg);backdrop-filter:blur(10px);
  -webkit-backdrop-filter:blur(10px);color:#fff;padding:8px 4px;text-align:center;
  font-weight:700;position:sticky;top:0;z-index:4;border-radius:var(--radius-sm);
  border:1px solid #ffffff40;box-shadow:0 4px 14px #0002;display:flex;
  flex-direction:column;justify-content:center;align-items:center;min-height:0}
.grid .dhead .dnum{font-size:1.1rem;font-weight:800;line-height:1.1}
.grid .dhead .dname{font-size:.64rem;opacity:.82;text-transform:uppercase;letter-spacing:.7px;margin-top:1px}
.grid .name{background:var(--namebg);backdrop-filter:blur(10px);
  -webkit-backdrop-filter:blur(10px);color:#fff;text-align:center;padding:0 16px;
  font-size:clamp(.9rem,1.4vw,1.12rem);font-weight:800;letter-spacing:-.01em;
  position:sticky;left:0;z-index:3;white-space:nowrap;border-radius:var(--radius);
  border:1px solid #ffffff30;box-shadow:4px 0 16px #0003;
  display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:0;gap:6px}
/* Override : la case ville ne suit PAS le layout 45-55 des cases température.
   Contenu centré verticalement, pas poussé vers le bas. */
.grid .cell.name{justify-content:center !important}
.grid .name .errmsg{display:block;flex:1 1 100%;font-size:.68rem;font-weight:500;color:#ffcccc;margin-top:2px}

/* Cartes en verre dépoli */
.grid .cell{text-align:center;padding:6px 4px;position:relative;
  border-radius:var(--radius);border:1px solid #ffffff66;
  backdrop-filter:blur(8px) saturate(1.15);-webkit-backdrop-filter:blur(8px) saturate(1.15);
  box-shadow:inset 0 1px 0 #ffffffcc, inset 0 -8px 16px #ffffff22, 0 6px 14px #0002;
  animation:cellIn .55s both;overflow:hidden;transition:transform .16s ease-out, box-shadow .16s ease-out, filter .16s ease-out;
  display:flex;flex-direction:column;justify-content:flex-end;align-items:center;min-width:0;min-height:0}
@keyframes cellIn{from{opacity:0;transform:translateY(14px) scale(.92)}
  to{opacity:1;transform:none}}
.grid .cell .sheen{position:absolute;inset:0;border-radius:var(--radius);pointer-events:none;
  background:linear-gradient(135deg,rgba(255,255,255,.5) 0%,rgba(255,255,255,.05) 38%,transparent 60%)}
.grid .cell:hover{transform:translateY(-2px) scale(1.04);z-index:6;
  filter:brightness(1.05);box-shadow:inset 0 1px 0 #fff,0 12px 24px #0003}
.grid .cell .tmax{display:block;font-size:clamp(1.2rem,2.6vw,2.4rem);font-weight:900;
  line-height:1;letter-spacing:-.03em;text-shadow:0 1px 0 #fff9;position:relative}
.grid .cell .tmin{display:block;font-size:clamp(.64rem,1vw,.82rem);opacity:.62;font-weight:700;margin-top:2px;position:relative}
.grid .cell .emoji{display:none}  /* masqué : remplacé par l'image de fond */
.grid .cell .meta{display:flex;gap:7px;justify-content:center;margin-top:4px;
  font-size:clamp(.52rem,.8vw,.66rem);font-weight:700;opacity:.78;position:relative}
/* Bandeau image de temps (~45% haut) + fondu vertical vers la couleur thermique */
.grid .cell .wband{position:absolute;top:0;left:0;right:0;height:45%;
  background-size:cover;background-position:center;z-index:0}
.grid .cell .wfade{position:absolute;inset:0}
.grid .cell .meta .r{color:#0d4a6b;opacity:1}
.grid .cell.empty{opacity:.28}
.grid .cell.errored,.grid .name.errored{color:#ffcccc}

/* Boutons AROME/ARPEGE/ICON-D2/Supprimer dans la cellule de nom */
.mdl-btns{display:inline-flex;gap:5px;flex:0 0 auto}
.mdl-btn{width:28px;height:28px;border-radius:8px;border:1px solid #ffffff55;
  background:rgba(255,255,255,.2);color:#fff;font-size:.72rem;font-weight:800;
  cursor:pointer;line-height:1;padding:0;display:inline-flex;align-items:center;
  justify-content:center;transition:transform .14s ease-out,background .14s ease-out,box-shadow .14s ease-out}
.mdl-btn:hover:not(:disabled){background:rgba(255,255,255,.4);transform:scale(1.1);box-shadow:0 2px 8px #0003}
.mdl-btn:active:not(:disabled){transform:scale(.95)}
.mdl-btn:focus-visible{outline:2px solid var(--accent-light);outline-offset:2px}
.mdl-btn:disabled{opacity:.25;cursor:not-allowed}
.mdl-btn.del{border-color:rgba(255,160,160,.5);background:var(--danger-soft);font-size:.86rem}
.mdl-btn.del:hover{background:rgba(220,38,38,.72)}

/* Modale horaire plein écran */
.modal-overlay{position:fixed;inset:0;z-index:200;background:rgba(5,18,35,.58);
  backdrop-filter:blur(8px) saturate(1.1);-webkit-backdrop-filter:blur(8px) saturate(1.1);
  display:flex;align-items:center;justify-content:center;padding:12px}
.modal-overlay[hidden]{display:none}
.modal{width:98vw;max-width:1600px;height:96vh;display:flex;flex-direction:column;
  background:linear-gradient(160deg,rgba(255,255,255,.94),rgba(232,242,252,.92));
  border:1px solid #ffffffbb;border-radius:22px;overflow:hidden;
  box-shadow:0 24px 64px #0007;animation:modalIn .3s both}
.modal-overlay[hidden] .modal{animation:none}
@keyframes modalIn{from{opacity:0;transform:translateY(20px) scale(.96)}
  to{opacity:1;transform:none}}
.modal-head{display:flex;align-items:center;gap:14px;padding:14px 20px;flex:0 0 auto;
  background:var(--hdrbg);color:#fff}
.modal-head .mt-model{font-size:.7rem;font-weight:700;opacity:.9;text-transform:uppercase;
  letter-spacing:.7px;background:rgba(255,255,255,.2);padding:4px 12px;border-radius:999px}
.modal-head .mt-run{font-size:.74rem;opacity:.72;font-weight:500;margin-left:6px}
.modal-close{margin-left:auto;width:36px;height:36px;flex:0 0 auto;border-radius:10px;
  border:1px solid #ffffff55;background:rgba(255,255,255,.2);color:#fff;font-size:1.1rem;
  cursor:pointer;line-height:1;display:inline-flex;align-items:center;justify-content:center;
  transition:background .14s,transform .14s}
.modal-close:hover{background:rgba(255,255,255,.4);transform:scale(1.05)}
.modal-close:focus-visible{outline:2px solid var(--accent-light);outline-offset:2px}
.modal-body{overflow:auto;padding:16px 20px 24px;flex:1;min-height:0}
.modal-day{margin-bottom:18px}
.modal-day:last-child{margin-bottom:0}
.modal-day .md-label{position:sticky;left:0;font-size:.92rem;font-weight:800;
  color:var(--ink);margin:0 0 8px;letter-spacing:-.01em;
  padding-bottom:4px;border-bottom:2px solid rgba(30,64,175,.15)}
/* Grille horaire auto-adaptative : cellules réparties sur toute la largeur. */
.modal-hgrid{display:grid;grid-auto-flow:column;
  grid-auto-columns:minmax(0,1fr);gap:5px}
.hcell{text-align:center;padding:8px 3px;border-radius:12px;
  border:1px solid #ffffff66;position:relative;min-width:0;
  box-shadow:inset 0 1px 0 #ffffffcc,0 3px 8px #0001;
  transition:transform .14s ease-out,box-shadow .14s ease-out}
.hcell:hover{transform:translateY(-2px);box-shadow:inset 0 1px 0 #fff,0 8px 16px #0002}
.hcell .h-hr{display:block;font-size:.7rem;font-weight:700;color:#0d2438;opacity:.88}
.hcell .h-emoji{display:block;font-size:1.2rem;line-height:1.1;margin:3px 0}
.hcell .h-temp{display:block;font-size:1.2rem;font-weight:900;line-height:1;letter-spacing:-.02em}
.hcell .h-meta{display:flex;flex-direction:column;gap:1px;margin-top:4px;
  font-size:.58rem;font-weight:700;opacity:.78;color:#0d2438}
.hcell .h-meta .rain{color:#0d4a6b;opacity:1;font-weight:800}
.modal-empty{padding:40px;text-align:center;color:var(--ink);opacity:.6;font-weight:600}

@media(max-width:760px){
  .grid{grid-template-columns:96px repeat(var(--days,11),minmax(0,1fr));gap:4px}
  header.hero .sub{display:none}
}
@media(prefers-reduced-motion:reduce){
  body::before,header.hero .logo,.grid .cell{animation:none}
}
"""

_JS = r"""
(function(){
  var DATA = window.__HORAIRES__ || {};
  var NAMES = window.__CITY_NAMES__ || {};
  var MODEL_LABEL = {arome:'AROME', arpege:'ARPEGE', icond2:'ICON-D2'};
  var overlay = document.getElementById('modal-overlay');
  var modal = document.getElementById('modal');
  var titleEl = document.getElementById('modal-title');
  var bodyEl = document.getElementById('modal-body');

  // Port JS de temp_color / temp_bg (renderer.py) : hue bleu->rouge.
  function tempColor(t){
    if(t===null||t===undefined||isNaN(t)) return 'hsl(210,8%,45%)';
    var x = Math.max(0,Math.min(1,(t+10)/55));
    var hue=(1-x)*240, intensity=Math.abs(t-18)/30;
    var sat=Math.round(42+Math.max(0,Math.min(1,intensity))*50*10)/10;
    return 'hsl('+Math.round(hue)+','+sat+'%,38%)';
  }
  function tempBg(t){
    if(t===null||t===undefined||isNaN(t)) return 'hsla(210,20%,94%,0.5)';
    var x=Math.max(0,Math.min(1,(t+10)/55));
    var hue=(1-x)*240, intensity=Math.abs(t-18)/30;
    var sat=Math.round(70+Math.max(0,Math.min(1,intensity))*25*10)/10;
    var light=82-Math.max(0,Math.min(1,intensity))*10;
    return 'hsla('+Math.round(hue)+','+sat+'%,'+light+'%,0.55)';
  }

  function esc(s){var d=document.createElement('div');d.textContent=s==null?'':s;return d.innerHTML;}

  function buildHourCell(s){
    var parts=[];
    parts.push('<span class="h-hr">'+esc(s.heure)+'</span>');
    parts.push('<span class="h-emoji">'+s.emoji+'</span>');
    parts.push('<span class="h-temp" style="color:'+tempColor(s.temp)+'">'+esc(s.temp)+'°</span>');
    var meta=[];
    if(s.vent_raf!=null) meta.push('<span>💨'+esc(s.vent_raf)+'</span>');
    if(s.pluie!=null) meta.push('<span class="rain">🌧'+esc(s.pluie)+'</span>');
    if(s.humidite!=null) meta.push('<span>'+esc(s.humidite)+'%</span>');
    parts.push('<div class="h-meta">'+meta.join('')+'</div>');
    return '<div class="hcell" style="background:'+tempBg(s.temp)+'">'+parts.join('')+'</div>';
  }

  function modelSlots(day, model){
    // day.slots viennent du scraper ; on ajoute l'emoji via temps_label.
    return day.slots.map(function(s){
      return {heure:s.heure, temp:s.temp, emoji:emojiFor(s.temps_label),
              vent_raf:s.vent_raf, pluie:s.pluie, humidite:s.humidite,
              temps_label:s.temps_label};
    });
  }
  function emojiFor(label){
    var low=(label|| '').toLowerCase(), rules=[
      ['orage','⛈️'],['averse','🌧️'],['pluie','🌧️'],['neige','❄️'],
      ['granule','🌨️'],['grêle','🌨️'],['brouillard','🌫️'],['brume','🌫️'],
      ['couvert','☁️'],['nuageux','☁️'],['peu nuageux','🌤️'],
      ['ciel clair','☀️'],['dégagé','☀️'],['soleil','☀️']];
    for(var i=0;i<rules.length;i++){if(low.indexOf(rules[i][0])>=0) return rules[i][1];}
    return '🌡️';
  }

  function openModal(slug, model){
    var rec = DATA[slug] && DATA[slug][model];
    var name = NAMES[slug] || slug;
    if(!rec || !rec.days || !rec.days.length){
      titleEl.innerHTML='<span class="mt-model">'+MODEL_LABEL[model]+'</span> '+esc(name);
      bodyEl.innerHTML='<div class="modal-empty">Aucune donnée '+MODEL_LABEL[model]+' pour cette ville.</div>';
    } else {
      var run = rec.updated_at ? '<span class="mt-run">'+esc(rec.updated_at)+'</span>' : '';
      titleEl.innerHTML='<span class="mt-model">'+MODEL_LABEL[model]+'</span> '
        +esc(name)+run;
      var html='';
      for(var d=0; d<rec.days.length; d++){
        var day=rec.days[d];
        var cells=modelSlots(day, model).map(buildHourCell).join('');
        html+='<div class="modal-day"><div class="md-label">'+esc(day.date_label)+'</div>'
          +'<div class="modal-hgrid">'+cells+'</div></div>';
      }
      bodyEl.innerHTML=html;
    }
    overlay.hidden=false; modal.hidden=false;
    document.body.style.overflow='hidden';
    modal.querySelector('.modal-body').scrollTop=0;
  }
  function closeModal(){overlay.hidden=true; modal.hidden=true; document.body.style.overflow='';}

  document.addEventListener('click', function(e){
    var btn=e.target.closest && e.target.closest('.mdl-btn');
    if(btn && !btn.disabled){
      // Bouton supprimer la ville : prévient l'app shell (parent) via postMessage.
      if(btn.hasAttribute('data-del')){
        if(window.parent && window.parent!==window){
          window.parent.postMessage(
            {source:'meteo', action:'remove',
             slug:btn.getAttribute('data-del'),
             name:btn.getAttribute('data-name')}, '*');
        }
        return;
      }
      openModal(btn.getAttribute('data-city'), btn.getAttribute('data-model'));
      return;
    }
    if(e.target===overlay || (e.target.closest && e.target.closest('.modal-close'))){
      closeModal();
    }
  });
  document.addEventListener('keydown', function(e){
    if(e.key==='Escape' && !overlay.hidden) closeModal();
  });
})();
"""


def _horaires_payload(cities: list) -> dict:
    """Extrait les données horaires arome/arpege par ville pour le JS inline.
    On ne garde que les champs utiles (allège le payload embarqué)."""
    out = {}
    for c in cities:
        slug = c["slug"]
        rec = {}
        for model in ("arome", "arpege", "icond2"):
            data = c.get(model)
            if data and data.get("days"):
                rec[model] = {
                    "updated_at": data.get("updated_at", ""),
                    "days": [
                        {"date_label": d["date_label"], "slots": d["slots"]}
                        for d in data["days"]
                    ],
                }
        if rec:
            out[slug] = rec
    return out


def _city_names(cities: list) -> dict:
    return {c["slug"]: c["name"] for c in cities}


def _modal_html() -> str:
    return (
        "<div class='modal-overlay' id='modal-overlay' hidden>"
        "<div class='modal' id='modal' hidden>"
        "<div class='modal-head'>"
        "<span class='modal-title' id='modal-title'></span>"
        "<button class='modal-close' id='modal-close' title='Fermer (Échap)'>✕</button>"
        "</div>"
        "<div class='modal-body' id='modal-body'></div>"
        "</div></div>"
    )


def render_index(cities: list) -> str:
    labels = _all_day_labels(cities)
    overview = _render_overview(cities, labels)
    horaires_json = json.dumps(_horaires_payload(cities), ensure_ascii=False)
    names_json = json.dumps(_city_names(cities), ensure_ascii=False)
    # Les espaces dans <script> sont neutres ; on échappe </ pour la sécurité.
    horaires_json = horaires_json.replace("</", "<\\/")
    names_json = names_json.replace("</", "<\\/")
    return (
        "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Météo de mes villes</title>"
        f"<style>{_CSS}</style></head><body>"
        "<div class='wrap'>"
        f"{overview}"
        "</div>"
        f"{_modal_html()}"
        "<script>window.__HORAIRES__="
        f"{horaires_json};window.__CITY_NAMES__={names_json};</script>"
        f"<script>{_JS}</script>"
        "</body></html>"
    )
