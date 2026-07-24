# -*- coding: utf-8 -*-
"""Tests HTTP de bout en bout pour GET /shortcut/status, POST
/shortcut/create_desktop et POST /shortcut/dismiss (bannière "Créer un
raccourci sur le bureau ?", premier lancement de l'exécutable figé — voir
logx_shortcut.py). Même harnais que tests/test_backup_pick_folder_http.py
(vrai serveur sur port éphémère). logx_shortcut est monkeypatché : ces tests
couvrent le CÂBLAGE du handler (jeton, code HTTP selon le résultat), pas la
vraie création de raccourci Windows (voir tests/test_winshell.py) ni la
logique de marqueur (voir tests/test_shortcut.py)."""
import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod
import logx_shortcut as shortcut


@pytest.fixture
def server():
    srv = http.server.HTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        t.join(timeout=5)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def _post(base, path, with_token=True):
    headers = {'Content-Type': 'application/json'}
    if with_token:
        headers['X-RC-Token'] = httpmod.AUTH_TOKEN
    req = urllib.request.Request(base + path, data=b'', method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


# ── GET /shortcut/status ──────────────────────────────────────────────────

def test_status_sans_jeton_fonctionne(server, monkeypatch):
    """Comme /app/update_check : pas de jeton exigé pour un simple booléen
    d'affichage, lu au tout premier chargement de la page."""
    monkeypatch.setattr(shortcut, 'should_offer', lambda: True)
    status, d = _get(server, '/shortcut/status')
    assert status == 200
    assert d == {'show': True}


def test_status_false_en_mode_developpement(server, monkeypatch):
    monkeypatch.setattr(shortcut, 'should_offer', lambda: False)
    status, d = _get(server, '/shortcut/status')
    assert status == 200
    assert d == {'show': False}


# ── POST /shortcut/create_desktop ─────────────────────────────────────────

def test_create_desktop_sans_jeton_refuse(server):
    """Comme toute autre route POST (hors /auth/login) : jeton exigé, même
    pour une action purement locale — sinon un autre appareil du LAN
    pourrait déclencher la création d'un raccourci sur ce poste."""
    status, d = _post(server, '/shortcut/create_desktop', with_token=False)
    assert status in (401, 403)


def test_create_desktop_succes_renvoie_200_et_le_chemin(server, monkeypatch):
    monkeypatch.setattr(shortcut, 'create_and_mark',
                         lambda: {'ok': True, 'path': 'C:\\Users\\test\\Desktop\\LogX AI.lnk'})
    status, d = _post(server, '/shortcut/create_desktop')
    assert status == 200
    assert d == {'ok': True, 'path': 'C:\\Users\\test\\Desktop\\LogX AI.lnk'}


def test_create_desktop_echec_remonte_400_sans_lever(server, monkeypatch):
    """Un échec de création (ex. plateforme non supportée, PowerShell cassé)
    doit rester une réponse propre — jamais une exception qui casserait la
    bannière côté navigateur."""
    monkeypatch.setattr(shortcut, 'create_and_mark',
                         lambda: {'ok': False, 'error': 'plateforme non supportee'})
    status, d = _post(server, '/shortcut/create_desktop')
    assert status == 400
    assert d['ok'] is False


def test_create_desktop_exception_remonte_500(server, monkeypatch):
    def _boom():
        raise RuntimeError('powershell introuvable')
    monkeypatch.setattr(shortcut, 'create_and_mark', _boom)
    status, d = _post(server, '/shortcut/create_desktop')
    assert status == 500 and d['ok'] is False


# ── POST /shortcut/dismiss ────────────────────────────────────────────────

def test_dismiss_sans_jeton_refuse(server):
    status, d = _post(server, '/shortcut/dismiss', with_token=False)
    assert status in (401, 403)


def test_dismiss_pose_le_marqueur_et_renvoie_ok(server, monkeypatch):
    called = {}
    def fake_mark():
        called['done'] = True
    monkeypatch.setattr(shortcut, 'mark_offered', fake_mark)

    status, d = _post(server, '/shortcut/dismiss')
    assert status == 200
    assert d == {'ok': True}
    assert called.get('done') is True


def test_dismiss_exception_remonte_500(server, monkeypatch):
    def _boom():
        raise RuntimeError('disque plein')
    monkeypatch.setattr(shortcut, 'mark_offered', _boom)
    status, d = _post(server, '/shortcut/dismiss')
    assert status == 500 and d['ok'] is False
