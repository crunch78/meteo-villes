# Compilation de l'exécutable

## Pré-requis

```bash
pip install -r requirements.txt pyinstaller
```

## Compiler l'exe

```bash
cd meteo-villes
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

## Lancer l'app

- **Double-clic** sur `MeteoVilles.exe` → fenêtre native plein écran.
- Au démarrage, l'app scrape toutes les villes (zéro cache : tout est
  re-téléchargé depuis Météociel à chaque lancement).
- Les villes sont persistées dans `%APPDATA%\MeteoVilles\villes.json`.

## Lancer en source (sans compiler)

```bash
python app.py
```

## Options en ligne de commande

```bash
MeteoVilles.exe --help       # affiche l'aide
MeteoVilles.exe --version    # affiche la version
```
