"""MeteoVilles — application desktop autonome.

Un seul exe qui fait tout :
- Ouvre une fenêtre native plein écran (pywebview / Edge WebView2).
- Au chargement de l'UI, scrape TOUTES les villes (zéro cache : à chaque
  lancement, tout est re-téléchargé depuis Météociel).
- Gestion des villes (ajout via URL Météociel / suppression) dans l'UI.
- Villes persistées dans %APPDATA%\\MeteoVilles\\villes.json (caché).

Aucun fichier n'est écrit à côté de l'exe. Tout est dans l'exe + AppData.

Usage :
    MeteoVilles.exe              Lance l'app (plein écran)
    MeteoVilles.exe --help       Affiche l'aide
    MeteoVilles.exe --version    Affiche la version
"""
import argparse
import sys
import time
import urllib.request

from server import start_server

VERSION = "2.0.0"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="MeteoVilles",
        description="Météo de mes villes — app desktop autonome (Météociel). "
                    "Scrap les prévisions de tes villes et les affiche dans "
                    "une fenêtre native avec prévisions horaires AROME, ARPEGE "
                    "et ICON-D2.",
        epilog="Les villes sont sauvegardées dans %APPDATA%/MeteoVilles/villes.json. "
               "Au démarrage, l'app re-télécharge toujours toutes les données (zéro cache). "
               "Usage : double-cliquer l'exe pour lancer l'app en plein écran.",
    )
    parser.add_argument(
        "--version", action="version", version=f"MeteoVilles {VERSION}",
    )
    return parser.parse_args(argv)


def _wait_ready(base: str, tries: int = 50):
    for _ in range(tries):
        try:
            urllib.request.urlopen(base, timeout=1)
            return True
        except Exception:
            time.sleep(0.1)
    return False


def main(argv: list[str] | None = None) -> int:
    _parse_args(argv if argv is not None else sys.argv[1:])

    port, srv = start_server(port=0)
    base = f"http://127.0.0.1:{port}/"
    _wait_ready(base)
    try:
        import webview
        webview.create_window("Météo de mes villes", base,
                              width=1280, height=820, min_size=(800, 500),
                              maximized=True)
        webview.start()
    except ImportError:
        # pywebview absent : fallback navigateur (ne devrait pas arriver,
        # pywebview est embarqué dans l'exe).
        import webbrowser
        webbrowser.open(base)
        print(f"App en mode navigateur : {base} (Ctrl+C pour quitter)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    finally:
        srv.shutdown()
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
