# -*- coding: utf-8 -*-
"""Tests HTTP de bout en bout pour GET /rig/pending_detections et
POST /rig/dismiss_detection (chantier CAT plug-and-play, 03/08/2026) — même
harnais que tests/test_pota_spot_http.py (vrai serveur sur port éphémère).
logx_cat est monkeypatché : ces tests couvrent le CÂBLAGE du handler
(routage, JSON), pas la logique de détection elle-même (déjà couverte par
tests/test_cat.py)."""
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

import logx_cat as cat
import logx_http as httpmod


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
        return r.status, json.loads(r.read().decode('utf-8'))


def _post(base, path, payload):
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json',
                 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_pending_detections_liste_vide_par_defaut(server, monkeypatch):
    monkeypatch.setattr(cat, '_pending_detections', {})
    status, d = _get(server, '/rig/pending_detections')
    assert status == 200 and d == {'detections': []}


def test_pending_detections_renvoie_les_detections_en_cours(server, monkeypatch):
    monkeypatch.setattr(cat, '_pending_detections', {
        'COM5': {'kind': 'radio', 'brand': 'icom', 'model': 'IC-7300',
                 'certain': False, 'device': 'COM5', 'description': ''}})
    status, d = _get(server, '/rig/pending_detections')
    assert status == 200
    assert d['detections'] == [{'kind': 'radio', 'brand': 'icom', 'model': 'IC-7300',
                               'certain': False, 'device': 'COM5', 'description': ''}]


def test_dismiss_detection_appelle_cat_avec_le_bon_device(server, monkeypatch):
    captured = {}
    monkeypatch.setattr(cat, 'dismiss_detection', lambda device: captured.setdefault('device', device))
    status, d = _post(server, '/rig/dismiss_detection', {'device': 'COM5'})
    assert status == 200 and d == {'ok': True}
    assert captured['device'] == 'COM5'


def test_dismiss_detection_sans_token_refuse(server):
    """Comme toutes les autres routes POST (hors /auth/login) : jeton exigé."""
    body = json.dumps({'device': 'COM5'}).encode('utf-8')
    req = urllib.request.Request(server + '/rig/dismiss_detection', data=body, method='POST',
                                 headers={'Content-Type': 'application/json'})
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code in (401, 403)
