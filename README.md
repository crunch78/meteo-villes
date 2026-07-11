# ☀️ Météo de mes villes

Application desktop autonome (Windows) qui affiche les prévisions météo de vos villes favorites dans une fenêtre native plein écran. Les données proviennent de [Météociel](https://www.meteociel.fr) et incluent les modèles **AROME**, **ARPEGE** et **ICON-D2** en prévisions heure par heure.

![Python](https://img.shields.io/badge/Python-3.13+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## ✨ Fonctionnalités

- **Grille comparative** : toutes vos villes côte à côte, 11 jours de prévisions (températures max/min, vent, pluie, humidité).
- **Prévisions horaires** : boutons **A** (AROME), **P** (ARPEGE) et **D** (ICON-D2) par ville → modale plein écran avec les prévisions heure par heure.
- **Gestion des villes** : ajoutez une ville en collant un lien Météociel, supprimez-la d'un clic.
- **Zéro cache** : à chaque lancement, l'app re-télécharge toutes les données (toujours à jour).
- **100% autonome** : un seul fichier `.exe`, rien d'autre à installer. Les villes sont sauvegardées dans `%APPDATA%\MeteoVilles\`.
- **Plein écran** au démarrage.

## 🚀 Utilisation

### L'exécutable (recommandé)

1. Téléchargez `MeteoVilles.exe`.
2. Double-clic → l'app s'ouvre en plein écran et télécharge les prévisions.

C'est tout. Aucune installation, aucune dépendance.

### Lancer depuis le source

```bash
git clone https://github.com/votre-user/meteo-villes.git
cd meteo-villes
pip install -r requirements.txt
python app.py
```

### Ajouter une ville

Collez n'importe quel lien Météociel dans la barre du haut, par exemple :

```
https://www.meteociel.fr/previsions/10232/lanuejols.htm
https://www.meteociel.fr/previsions-arome-1h/28366/rouen.htm
```

L'app extrait automatiquement l'identifiant et le nom de la ville.

## 🏗️ Architecture

```
app.py          Point d'entrée — fenêtre pywebview plein écran
server.py       Serveur HTTP local + API (scrap, add/remove villes)
scraper.py      Scraping Météociel (requests + BeautifulSoup)
renderer.py     Génération HTML de la grille + modales horaires
config.py       Persistance villes (%APPDATA%) + parsing URL
web/            UI shell (HTML/CSS/JS) — barre d'outils + injection grille
```

**Stack** : Python 3.13+, pywebview (Edge WebView2), requests, BeautifulSoup, lxml.

## 🔨 Compiler l'exécutable

```bash
pip install -r requirements.txt pyinstaller

python -m PyInstaller --noconfirm --onefile --windowed --name MeteoVilles \
  --add-data "web;web" \
  --collect-submodules lxml \
  --hidden-import=lxml --hidden-import=lxml.etree \
  --hidden-import=charset_normalizer \
  --collect-all webview \
  --collect-all proxy_tools \
  --hidden-import=clr_loader \
  --hidden-import=pythonnet \
  app.py
```

→ exécutable dans `dist/MeteoVilles.exe` (~62 Mo).

Voir [`BUILD.md`](BUILD.md) pour plus de détails.

## 🧪 Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

44 tests couvrent le scraping, le rendu, la persistance des villes et l'API serveur.

## 📊 Données

Les prévisions proviennent de [Météociel.fr](https://www.meteociel.fr), qui agrège les modèles météo :

| Modèle | Horizon | Résolution |
|--------|---------|------------|
| GFS (prévisions + tendances) | ~11 jours | Global |
| AROME (1h) | ~2-3 jours | Régional, haute résolution |
| ARPEGE (1h) | ~3-4 jours | Global, haute résolution |
| ICON-D2 | ~2-3 jours | Régional, haute résolution |

## 📄 Licence

Ce projet est sous licence **MIT** ([LICENSE](LICENSE)) — © 2026 Christophe Martinez.

Le **code source** est libre d'utilisation, modification et redistribution selon les termes de la licence MIT.

### ⚖️ Données et propriété intellectuelle

Les **données météo** affichées par cette application sont la propriété exclusive de [Météociel.fr](https://www.meteociel.fr) et de ses fournisseurs (Météo-France, ECMWF, DWD…). Cette application :

- **N'est pas affiliée** à Météociel.
- Ne redistribue **pas** les données — elle les affiche en temps réel pour un usage strictement **personnel et non commercial**.
- Conformément aux conditions de Météociel : **il est strictement interdit de faire un usage commercial des données** météo présentes sur leur site.

En utilisant cette application, vous acceptez les [conditions d'utilisation de Météociel](https://www.meteociel.fr/copyright/mentions.php).
