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


# ─── DIAGNOSTIC RÉSEAU LOCAL ──────────────────────────────────────────────────
# Certains antivirus (Avast Web Shield confirmé en usage réel, potentiellement
# d'autres selon leur "inspection HTTP") interceptent CHAQUE connexion HTTP
# locale, ajoutant jusqu'à plusieurs secondes de latence. Ce comportement peut
# être ASYMÉTRIQUE : une exception ajoutée par l'utilisateur pour une adresse
# IP littérale (127.0.0.1) ne couvre pas forcément "localhost", ou l'inverse
# selon le logiciel de sécurité. Comme ce programme est destiné à être diffusé
# à des inconnus (chacun avec un antivirus différent, ou aucun), on ne peut PAS
# figer un choix a priori — on mesure les deux adresses en direct à chaque
# démarrage et on retient celle qui répond le plus vite, sans configuration
# manuelle requise de l'utilisateur.
_LOCAL_HOSTS = ('127.0.0.1', 'localhost')
_SLOW_THRESHOLD_MS = 400  # au-delà, la latence n'est plus de la variance normale


def _measure_latency(host, port, path='/log/status', timeout=2.0):
    """Latence (ms) d'un aller-retour HTTP vers host:port+path, None si
    échec/timeout (serveur pas encore prêt, port bloqué...)."""
    import time
    import urllib.request
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(f'http://{host}:{port}{path}', timeout=timeout) as r:
            r.read()
        return (time.perf_counter() - t0) * 1000
    except Exception:
        return None


def pick_fastest_host(port):
    """Teste 127.0.0.1 et localhost, retourne (meilleure_adresse, latence_ms
    ou None, latence_elevee_partout: bool)."""
    results = {h: _measure_latency(h, port) for h in _LOCAL_HOSTS}
    valid = {h: v for h, v in results.items() if v is not None}
    if not valid:
        return '127.0.0.1', None, False
    best = min(valid, key=valid.get)
    best_ms = valid[best]
    return best, best_ms, best_ms > _SLOW_THRESHOLD_MS


def _report_slow_network(host, ms):
    print(f"[RÉSEAU] ⚠ Latence locale élevée détectée ({ms:.0f} ms sur {host}) — "
          f"probablement un antivirus qui inspecte le trafic réseau local "
          f"(« Web Shield » ou équivalent). Le logiciel reste utilisable mais "
          f"chaque action sera ralentie. Voir docs/GUIDE_UTILISATEUR.md, "
          f"section Dépannage, pour ajouter une exception dans ton antivirus.")


# Config persistée du poste : c'est ce fichier qui dit si la station a déjà été
# renseignée une fois (même nom que logx_http.SERVER_CONFIG_FILE — on ne
# l'importe pas pour ne pas faire dépendre l'amorçage du serveur HTTP).
SERVER_CONFIG_FILE = '.server_config.json'


def station_deja_configuree(dossier=None):
    """La station a-t-elle déjà un indicatif enregistré ?

    L'indicatif est le seul réglage sans lequel RIEN ne fonctionne : pas de
    log, pas de score, pas d'export. Sa présence est donc le meilleur signe
    que le premier lancement a déjà eu lieu. On ne teste pas la simple
    existence du fichier : il est créé dès la première sauvegarde, même
    partielle (thème, langue…), et suffirait alors à faire croire à une
    station configurée.
    """
    import json
    chemin = os.path.join(dossier or os.getcwd(), SERVER_CONFIG_FILE)
    try:
        with open(chemin, encoding='utf-8') as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return False
    if not isinstance(cfg, dict):
        return False
    return bool(str(cfg.get('callsign', '') or '').strip())


def page_de_demarrage(dossier=None):
    """Sur quelle page ouvrir le navigateur au lancement ?

    DEMANDE UTILISATEUR : « à chaque ouverture la page configuration s'ouvre
    inutilement, la configuration se fait à la première utilisation ». C'était
    exact : le navigateur était envoyé sur CONFIG À CHAQUE DÉMARRAGE, sans
    jamais regarder si la station était déjà réglée. Une fois l'indicatif
    saisi, la page utile est le LOGBOOK — celle où l'on trafique.
    """
    return ('/logx_logbook.html' if station_deja_configuree(dossier)
            else '/logx_configuration.html')


def start_network_diagnosis(port, delay=1.5, then_open_browser=False):
    """Lance le diagnostic réseau en tâche de fond (laisse le serveur
    démarrer avant de le sonder). Si then_open_browser, ouvre le navigateur
    sur l'adresse la plus rapide une fois le diagnostic terminé — sinon
    (mode développeur) se contente d'afficher une recommandation en console."""
    import threading

    def _run():
        host, ms, slow = pick_fastest_host(port)
        if slow:
            _report_slow_network(host, ms)
        elif host != '127.0.0.1':
            print(f"[RÉSEAU] {host} répond plus vite que l'autre adresse locale "
                  f"sur ce poste ({ms:.0f} ms) — utilisé de préférence.")
        if then_open_browser:
            import webbrowser
            webbrowser.open(f'http://{host}:{port}{page_de_demarrage()}')

    threading.Timer(delay, _run).start()


def open_browser(port, delay=1.5):
    """Ouvre le navigateur sur l'application, sur l'adresse locale la plus
    rapide (voir start_network_diagnosis) — jamais figée en dur, puisque le
    comportement de l'antivirus de l'utilisateur est imprévisible."""
    start_network_diagnosis(port, delay=delay, then_open_browser=True)
