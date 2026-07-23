# -*- coding: utf-8 -*-
"""Mise à jour automatique de LogX AI — vérifie la dernière release GitHub,
propose le téléchargement + l'installation à l'utilisateur (jamais silencieux :
c'est un clic de l'opérateur qui déclenche le téléchargement ET l'installation),
et relance l'exécutable une fois remplacé.

Ne touche JAMAIS au dossier de données utilisateur (logx_bootstrap.user_data_dir()) :
seul l'exécutable lui-même est remplacé, exactement comme une réinstallation
manuelle — aucune perte de log, config, ou cache.

Toute la partie "remplacer l'exe en cours d'exécution" ne s'applique qu'en
mode figé (PyInstaller) : en développement (`python logx_serveur.py`),
sys.executable est l'interpréteur Python lui-même, rien à remplacer.
"""
import os
import sys
import stat
import json
import time
import threading
import subprocess
import urllib.request

from logx_utils import SSL_CTX
from logx_version import APP_VERSION
from logx_bootstrap import is_frozen, user_data_dir

GITHUB_REPO = 'sauveteur71/radioaamateur-program-Contest'
# /releases/latest (PAS utilisé ici) exclut par définition tout release
# marqué "prerelease" — or CHAQUE release LogX AI l'est tant qu'on reste en
# beta (v0.9-beta1...), ce qui le ferait toujours répondre 404. On prend donc
# la liste complète (déjà triée du plus récent au plus ancien par l'API) et
# on garde son 1er élément — vérifié en direct : /latest -> 404, /releases[0] -> v0.9-beta1.
RELEASES_API = f'https://api.github.com/repos/{GITHUB_REPO}/releases'
CHECK_TTL = 6 * 3600  # 6h : une nouvelle release n'apparaît pas seconde par seconde

# Nom de l'artefact attaché à la release, par plateforme — doit correspondre
# EXACTEMENT aux noms produits par .github/workflows/build-release.yml.
_ASSET_BY_PLATFORM = {
    'win': 'LogXAI.exe',
    'darwin': 'LogXAI-macos',
    'linux': 'LogXAI-linux',
}

_lock = threading.Lock()
_cache = {'ts': 0, 'result': None}
_checking = False
_download = {'status': 'idle', 'pct': 0, 'error': '', 'path': ''}


def _platform_key():
    if sys.platform.startswith('win'):
        return 'win'
    if sys.platform == 'darwin':
        return 'darwin'
    return 'linux'


def _fetch_latest_release():
    """Appel réseau RÉEL et bloquant — uniquement depuis un thread
    d'arrière-plan (voir get_cached_check), jamais depuis le thread HTTP.
    Renvoie None si le dépôt n'a encore aucune release publiée (liste vide),
    plutôt que de planter sur un accès data[0] hors limites."""
    req = urllib.request.Request(RELEASES_API, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)',
        'Accept': 'application/vnd.github+json',
    })
    with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
        releases = json.loads(resp.read().decode('utf-8', errors='replace'))
    return releases[0] if releases else None


def _build_result(data):
    tag = str(data.get('tag_name', '') or '').strip()
    latest = tag[1:] if tag[:1].lower() == 'v' else tag
    asset_name = _ASSET_BY_PLATFORM[_platform_key()]
    asset_url = ''
    for a in (data.get('assets') or []):
        if a.get('name') == asset_name:
            asset_url = a.get('browser_download_url', '')
            break
    return {
        'available': bool(latest) and latest != APP_VERSION,
        'current': APP_VERSION,
        'latest': latest or APP_VERSION,
        'release_url': data.get('html_url', ''),
        'notes': str(data.get('body', '') or '')[:2000],
        'asset_url': asset_url,
        # Le téléchargement+remplacement automatique n'a de sens qu'en exe
        # figé ET si l'artefact de cette plateforme existe sur la release.
        'installable': bool(asset_url) and is_frozen(),
        'checking': False,
    }


def _refresh(force=False):
    global _checking
    with _lock:
        if _checking:
            return
        if not force and _cache['result'] and (time.time() - _cache['ts']) < CHECK_TTL:
            return
        _checking = True
    result = None
    try:
        data = _fetch_latest_release()
        if data:
            result = _build_result(data)
    except Exception as e:
        print(f"[UPDATE] Vérification impossible : {e}")
    with _lock:
        if result:
            _cache['result'] = result
            _cache['ts'] = time.time()
        _checking = False


def get_cached_check(force=False):
    """Ne bloque JAMAIS sur le réseau : renvoie le dernier résultat connu et
    déclenche un rafraîchissement en tâche de fond si le cache est absent ou
    périmé (le tout premier appel après démarrage renvoie donc 'checking',
    rattrapé par le client au prochain sondage)."""
    stale = force or not _cache['result'] or (time.time() - _cache['ts']) >= CHECK_TTL
    if stale and not _checking:
        threading.Thread(target=_refresh, args=(force,), daemon=True).start()
    if _cache['result']:
        return _cache['result']
    return {'available': False, 'current': APP_VERSION, 'latest': APP_VERSION,
            'release_url': '', 'notes': '', 'asset_url': '', 'installable': False,
            'checking': True}


# ─── TÉLÉCHARGEMENT ──────────────────────────────────────────────────────────

def start_download(asset_url):
    """Démarre le téléchargement en tâche de fond (jamais dans le thread
    HTTP — un exécutable fait plusieurs dizaines de Mo). Idempotent : un
    téléchargement déjà en cours n'en relance pas un second."""
    with _lock:
        if _download['status'] == 'downloading':
            return
        _download.update(status='downloading', pct=0, error='', path='')
    threading.Thread(target=_do_download, args=(asset_url,), daemon=True).start()


def _do_download(asset_url):
    dest_dir = os.path.join(user_data_dir(), 'update')
    try:
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, os.path.basename(asset_url) or 'LogXAI_new.exe')
        tmp = dest + '.part'
        req = urllib.request.Request(asset_url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)'})
        with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as resp:
            total = int(resp.headers.get('Content-Length', 0) or 0)
            got = 0
            with open(tmp, 'wb') as f:
                while True:
                    chunk = resp.read(262144)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    pct = int(got * 100 / total) if total else 0
                    with _lock:
                        _download['pct'] = pct
        os.replace(tmp, dest)
        with _lock:
            _download.update(status='done', pct=100, path=dest)
    except Exception as e:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        with _lock:
            _download.update(status='error', error=str(e))


def get_download_status():
    with _lock:
        return dict(_download)


# ─── INSTALLATION (remplacement de l'exécutable + relance) ──────────────────

def apply_update_and_relaunch(new_exe_path):
    """Lance un script auxiliaire détaché qui attend la fin du processus
    courant, remplace l'exécutable, puis le relance — puis retourne
    immédiatement (l'appelant doit arrêter le serveur juste après, sinon le
    script auxiliaire attendra indéfiniment que ce processus se termine)."""
    if not is_frozen():
        return False, "Pas d'exécutable à remplacer en mode développement"
    if not os.path.exists(new_exe_path):
        return False, "Fichier téléchargé introuvable"

    current_exe = sys.executable
    pid = os.getpid()
    update_dir = os.path.join(user_data_dir(), 'update')
    os.makedirs(update_dir, exist_ok=True)

    if sys.platform.startswith('win'):
        helper = os.path.join(update_dir, '_apply_update.bat')
        script = f'''@echo off
set count=0
timeout /t 2 /nobreak >NUL
:retry
move /Y "{new_exe_path}" "{current_exe}" >NUL 2>&1
if not errorlevel 1 goto launch
set /a count+=1
if %count% GEQ 30 goto giveup
timeout /t 1 /nobreak >NUL
goto retry
:launch
start "" "{current_exe}"
del "%~f0"
goto :eof
:giveup
echo Echec du remplacement — fermez LogXAI.exe puis relancez-le manuellement. > "{current_exe}.update_failed.txt"
'''
        with open(helper, 'w', encoding='utf-8') as f:
            f.write(script)
        subprocess.Popen(
            ['cmd', '/c', helper],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    else:
        helper = os.path.join(update_dir, '_apply_update.sh')
        script = f'''#!/bin/sh
sleep 2
i=0
while ! mv -f "{new_exe_path}" "{current_exe}" 2>/dev/null; do
  i=$((i+1))
  if [ "$i" -ge 30 ]; then
    echo "Echec du remplacement - fermez LogXAI puis relancez-le manuellement." > "{current_exe}.update_failed.txt"
    exit 1
  fi
  sleep 1
done
chmod +x "{current_exe}"
nohup "{current_exe}" >/dev/null 2>&1 &
rm -f "$0"
'''
        with open(helper, 'w', encoding='utf-8') as f:
            f.write(script)
        os.chmod(helper, os.stat(helper).st_mode | stat.S_IEXEC)
        subprocess.Popen(['/bin/sh', helper], start_new_session=True, close_fds=True)

    return True, ''
