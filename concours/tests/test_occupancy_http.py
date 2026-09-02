# -*- coding: utf-8 -*-
"""Round-trip HTTP de l'occupation des bandes : POST /occupancy/heartbeat déclare
la bande/mode de CE poste, GET /data/occupancy renvoie la vue fusionnée. Vrai
serveur sur port éphémère (même harnais que test_calldb_name_http.py).
"""
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

import logx_http as httpmod   # noqa: E402
import logx_occupancy as occ   # noqa: E402


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
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json', 'X-RC-Token': httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def test_heartbeat_puis_occupancy(server):
    occ._reset_pour_test()
    st, resp = _post(server, '/occupancy/heartbeat', {'band': '20', 'mode': 'SSB'})
    assert st == 200 and resp.get('ok') is True

    st2, vue = _get(server, '/data/occupancy')
    assert st2 == 200
    stations = vue.get('stations', [])
    assert len(stations) == 1
    assert stations[0]['band'] == '20' and stations[0]['mode'] == 'SSB'
    assert 'station' in stations[0]                     # identifiant de poste présent


def test_occupancy_vide_au_depart(server):
    occ._reset_pour_test()
    st, vue = _get(server, '/data/occupancy')
    assert st == 200
    assert vue.get('stations') == [] and vue.get('conflits') == []


def test_heartbeat_exige_auth(server):
    """La déclaration de statut est une écriture -> jeton exigé (anti-usurpation
    LAN), comme toutes les routes POST sauf /auth/login."""
    occ._reset_pour_test()
    body = json.dumps({'band': '20', 'mode': 'SSB'}).encode('utf-8')
    req = urllib.request.Request(
        server + '/occupancy/heartbeat', data=body, method='POST',
        headers={'Content-Type': 'application/json'})   # PAS de X-RC-Token
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=5)
    assert e.value.code in (401, 403)
