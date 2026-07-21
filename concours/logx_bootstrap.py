# -*- coding: utf-8 -*-
"""Amorçage de l'application figée (PyInstaller) — Windows & macOS.

En mode « exécutable » (PyInstaller), les fichiers de référence sont EMBARQUÉS
en lecture seule dans le bundle (sys._MEIPASS) et NE sont pas modifiables. Les
données de l'utilisateur (log, config, base, caches) doivent aller dans un
dossier INSCRIPTIBLE de son profil. Ce module :
  - calcule ce dossier (APPDATA sous Windows, Application Support sous macOS),
  - y recopie au premier lancement les fichiers de référence embarqués,
  - fait de ce dossier le répertoire de travail (les chemins relatifs du reste
    du code y écrivent alors sans souci de permissions),
  - ouvre le navigateur sur l'application.

En mode développement (python logx_serveur.py), ne fait rien : le
répertoire de travail reste concours/ comme aujourd'hui.
"""
import os
import sys
import shutil


def is_frozen():
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def resource_dir():
    """Dossier des fichiers embarqués (bundle figé) ou du code source."""
    if is_frozen():
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def user_data_dir():
    """Dossier inscriptible des données utilisateur, par plateforme."""
    app = 'LogXAI'
    if sys.platform.startswith('win'):
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Application Support')
    else:
        base = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
    d = os.path.join(base, app)
    os.makedirs(d, exist_ok=True)
    return d


# Fichiers de référence à recopier au 1er lancement (lecture seule dans le
# bundle → copie inscriptible : cty.dat est mis à jour, les autres servent tels
# quels mais doivent être dans le cwd pour les open() relatifs).
_SEED_FILES = ['cty.dat', 'contest_schema.json', 'france_departements.geojson',
               'custom_contests.json']


def bootstrap():
    """Prépare l'environnement si figé. Retourne le dossier de données actif."""
    if not is_frozen():
        return os.getcwd()
    data = user_data_dir()
    res = resource_dir()
    for name in _SEED_FILES:
        dst = os.path.join(data, name)
        src = os.path.join(res, name)
        if not os.path.exists(dst) and os.path.exists(src):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass
    os.chdir(data)
    return data


def open_browser(port, delay=1.5):
    """Ouvre le navigateur sur l'application, après un court délai (laisse le
    serveur démarrer). En thread pour ne pas bloquer serve_forever()."""
    import threading
    import webbrowser

    def _open():
        # 127.0.0.1 plutôt que localhost : certains antivirus (Avast Web
        # Shield observé sur ce type de poste) filtrent les exceptions de
        # site par correspondance TEXTUELLE de l'URL — une exception posée
        # pour 127.0.0.1 ne couvre pas localhost même si les deux pointent
        # vers la même machine, ajoutant ~2 s d'inspection à chaque requête.
        webbrowser.open(f'http://127.0.0.1:{port}/logx_configuration.html')

    threading.Timer(delay, _open).start()
