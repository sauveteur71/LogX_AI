# -*- coding: utf-8 -*-
"""GET /app/update_check expose la version installée (APP_VERSION) et le repo
GitHub (logx_update.GITHUB_REPO) — consommés par la barre de statut
(logx_statusbar.js) pour afficher "vX.Y" et construire le lien du bouton
"signaler un problème". Sans ce test, un renommage silencieux des champs
'current'/'repo' ne casserait rien côté serveur (toujours 200 OK) mais
laisserait la version affichée bloquée sur '—' et le lien GitHub sur le
repli codé en dur côté JS — voir tests/test_log_version.py pour le pendant
sur le compteur de fraîcheur du log."""
import http.server
import json
import os
import sys
import threading
import time
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod
import logx_update as upd
from logx_version import APP_VERSION


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()   # libere la socket d ecoute
        t.join(timeout=5)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def test_update_check_cache_frais_expose_version_et_repo(server, monkeypatch):
    """Cache déjà frais (pas de thread réseau déclenché) : le JSON renvoyé
    contient 'current' == APP_VERSION et 'repo' == GITHUB_REPO."""
    fake_result = {'available': False, 'current': APP_VERSION, 'latest': APP_VERSION,
                   'release_url': '', 'notes': '', 'asset_url': '', 'installable': False,
                   'checking': False, 'repo': upd.GITHUB_REPO}
    monkeypatch.setattr(upd, '_cache', {'ts': time.time(), 'result': fake_result})
    d = _get(server, '/app/update_check')
    assert d['current'] == APP_VERSION
    assert d['repo'] == upd.GITHUB_REPO


def test_update_check_sans_cache_expose_quand_meme_version_et_repo(server, monkeypatch):
    """Tout premier appel après démarrage (aucun cache) : la version et le
    repo doivent être présents immédiatement dans le repli 'checking',
    avant même que la release GitHub ait été récupérée — c'est ce que lit
    la barre de statut au tout premier chargement de page. _checking=True
    empêche ici le thread de vérification réseau réel de démarrer pendant
    le test."""
    monkeypatch.setattr(upd, '_cache', {'ts': 0, 'result': None})
    monkeypatch.setattr(upd, '_checking', True)
    d = _get(server, '/app/update_check')
    assert d['current'] == APP_VERSION
    assert d['repo'] == upd.GITHUB_REPO
    assert d['checking'] is True


def test_build_result_inclut_le_repo():
    """Unitaire, sans HTTP : _build_result (appelé après une vraie récupération
    de release) doit lui aussi porter 'repo', pas seulement le repli."""
    data = {'tag_name': 'v99.0', 'html_url': 'https://example.invalid/release',
            'body': 'notes', 'assets': []}
    result = upd._build_result(data)
    assert result['repo'] == upd.GITHUB_REPO
    assert result['current'] == APP_VERSION


# ── Nom d'artefact versionné (voir .github/workflows/build-release.yml) ─────
# Depuis que ce workflow embarque le tag dans le nom de l'artefact attaché à
# la release (LogXAI-v0.9-beta2.exe et non plus LogXAI.exe fixe), _build_result
# doit reconstruire EXACTEMENT ce nom pour retrouver l'URL de téléchargement —
# un décalage silencieux ici laisserait 'asset_url' vide pour toujours,
# désactivant la mise à jour automatique sans qu'aucune requête ne le signale
# (fetch + parsing JSON réussissent, seule la recherche par nom échoue).

def test_build_result_trouve_asset_windows_avec_tag(monkeypatch):
    monkeypatch.setattr(upd, '_platform_key', lambda: 'win')
    data = {'tag_name': 'v0.9-beta2', 'html_url': '', 'body': '', 'assets': [
        {'name': 'LogXAI-v0.9-beta2.exe', 'browser_download_url': 'https://x/win.exe'},
        {'name': 'LogXAI-v0.9-beta2-macos', 'browser_download_url': 'https://x/mac'},
    ]}
    result = upd._build_result(data)
    assert result['asset_url'] == 'https://x/win.exe'


def test_build_result_trouve_asset_macos_avec_tag(monkeypatch):
    monkeypatch.setattr(upd, '_platform_key', lambda: 'darwin')
    data = {'tag_name': 'v0.9-beta2', 'html_url': '', 'body': '', 'assets': [
        {'name': 'LogXAI-v0.9-beta2.exe', 'browser_download_url': 'https://x/win.exe'},
        {'name': 'LogXAI-v0.9-beta2-macos', 'browser_download_url': 'https://x/mac'},
    ]}
    result = upd._build_result(data)
    assert result['asset_url'] == 'https://x/mac'


def test_build_result_trouve_asset_linux_avec_tag(monkeypatch):
    monkeypatch.setattr(upd, '_platform_key', lambda: 'linux')
    data = {'tag_name': 'v0.9-beta2', 'html_url': '', 'body': '', 'assets': [
        {'name': 'LogXAI-v0.9-beta2-linux', 'browser_download_url': 'https://x/linux'},
    ]}
    result = upd._build_result(data)
    assert result['asset_url'] == 'https://x/linux'


def test_build_result_ancien_nom_fixe_ne_matche_plus():
    """Non-régression volontaire : un ancien artefact nommé LogXAI.exe (sans
    tag, produit par l'ancienne version du workflow) ne doit PAS matcher —
    sinon on proposerait de télécharger une release qui n'a pas cet asset."""
    data = {'tag_name': 'v0.9-beta2', 'html_url': '', 'body': '',
            'assets': [{'name': 'LogXAI.exe', 'browser_download_url': 'https://x/old.exe'}]}
    result = upd._build_result(data)
    assert result['asset_url'] == ''
    assert result['installable'] is False


def test_build_result_asset_absent_installable_false():
    data = {'tag_name': 'v0.9-beta2', 'html_url': '', 'body': '', 'assets': []}
    result = upd._build_result(data)
    assert result['asset_url'] == ''
    assert result['installable'] is False
