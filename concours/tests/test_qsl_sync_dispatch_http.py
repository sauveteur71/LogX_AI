# -*- coding: utf-8 -*-
"""Lot 4 — /qsl/sync dispatche le service : 'eqsl' -> sync_eqsl, défaut -> sync_lotw
(rétro-compatible). Harnais serveur réel, sync_* injectés (aucun réseau)."""
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
import logx_qsl as qsl


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


def _post(base, path, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=data, method='POST',
        headers={'X-RC-Token': httpmod.AUTH_TOKEN, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def _sentinels(monkeypatch):
    monkeypatch.setattr(qsl, 'sync_eqsl', lambda cfg, since=None: {'ok': True, 'marqueur': 'EQSL', 'since': since})
    monkeypatch.setattr(qsl, 'sync_lotw', lambda cfg, since=None: {'ok': True, 'marqueur': 'LOTW', 'since': since})


def test_service_eqsl_appelle_sync_eqsl(server, monkeypatch):
    _sentinels(monkeypatch)
    status, data = _post(server, '/qsl/sync', {'service': 'eqsl', 'since': '202601010000'})
    assert status == 200 and data['marqueur'] == 'EQSL'
    assert data['since'] == '202601010000'


def test_defaut_appelle_sync_lotw(server, monkeypatch):
    _sentinels(monkeypatch)
    status, data = _post(server, '/qsl/sync', {})
    assert status == 200 and data['marqueur'] == 'LOTW'
