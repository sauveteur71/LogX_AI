# -*- coding: utf-8 -*-
"""Test HTTP de bout en bout (vrai serveur sur port éphémère, même motif que
tests/test_callhistory_http.py) pour /autostart/launch : le bouton « Lancer »
par ligne du panneau AUTO-LANCEMENT (CONFIG). La logique de lancement elle-
même (subprocess, détection « déjà lancé ») est déjà exhaustivement testée
dans tests/test_autostart.py, jamais de vrai subprocess ici non plus —
logx_autostart.lancer() est mocké, on vérifie seulement le CÂBLAGE HTTP
(auth, lecture du corps JSON, code de statut)."""
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
import logx_autostart as autostart


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
        srv.server_close()
        t.join(timeout=5)
        srv.server_close()


def _post(base, path, payload, token=True):
    body = json.dumps(payload).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['X-RC-Token'] = httpmod.AUTH_TOKEN
    req = urllib.request.Request(base + path, data=body, method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_autostart_launch_succes(server, monkeypatch):
    monkeypatch.setattr(autostart, 'lancer', lambda entree: {'ok': True, 'skipped': False})
    status, res = _post(server, '/autostart/launch', {'path': 'C:\\WSJT-X\\wsjtx.exe', 'args': ''})
    assert status == 200 and res == {'ok': True, 'skipped': False}


def test_autostart_launch_echec(server, monkeypatch):
    monkeypatch.setattr(autostart, 'lancer', lambda entree: {'ok': False, 'error': 'introuvable'})
    status, res = _post(server, '/autostart/launch', {'path': 'C:\\absent.exe', 'args': ''})
    assert status == 400 and res['ok'] is False


def test_autostart_launch_sans_token_refuse(server, monkeypatch):
    called = []
    monkeypatch.setattr(autostart, 'lancer', lambda entree: called.append(1) or {'ok': True})
    status, res = _post(server, '/autostart/launch', {'path': 'C:\\WSJT-X\\wsjtx.exe'}, token=False)
    assert status == 403
    assert not called   # aucun lancement ne doit avoir eu lieu sans jeton valide
