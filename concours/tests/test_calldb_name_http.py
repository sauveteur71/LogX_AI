# -*- coding: utf-8 -*-
"""Round-trip HTTP du prénom dans la base interne (calldb) : POST /calldb/update
grave le prénom, GET /calldb/lookup/<call> le renvoie. Vrai serveur sur port
éphémère (même harnais que test_qrz_sota_http.py) ; calldb.json ISOLÉ dans un
tmp via monkeypatch.chdir — les endpoints le résolvent depuis os.getcwd().
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
import logx_departments as dep   # noqa: E402


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
    req = urllib.request.Request(base + path, headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def test_calldb_prenom_round_trip(server, monkeypatch, tmp_path):
    # calldb.json isolé : les endpoints le lisent/écrivent depuis os.getcwd().
    monkeypatch.chdir(tmp_path)
    with open('calldb.json', 'w', encoding='utf-8') as f:
        json.dump({'calls': {}}, f)
    dep._calldb_cache['sig'] = None   # invalide le cache mémoire (autre fichier)

    # 1) enrichissement : on grave le prénom + locator d'un correspondant
    st, out = _post(server, '/calldb/update',
                    {'call': 'F4TEST', 'locator': 'JN18DT', 'name': 'Camille'})
    assert st == 200 and out.get('ok') is True

    # 2) lookup : le prénom (et le locator) reviennent de la base interne
    st, res = _get(server, '/calldb/lookup/F4TEST')
    assert st == 200
    assert res.get('name') == 'Camille'
    assert res.get('locator') == 'JN18DT'
    assert res.get('source') == 'local'

    # 3) persistance réelle sur disque (pas seulement en mémoire)
    with open('calldb.json', encoding='utf-8') as f:
        saved = json.load(f)
    assert saved['calls']['F4TEST']['name'] == 'Camille'


def test_calldb_prenom_non_ecrase_par_vide(server, monkeypatch, tmp_path):
    # un update sans prénom ne doit pas effacer un prénom déjà appris.
    monkeypatch.chdir(tmp_path)
    with open('calldb.json', 'w', encoding='utf-8') as f:
        json.dump({'calls': {'F4TEST': {'locator': 'JN18DT', 'name': 'Camille'}}}, f)
    dep._calldb_cache['sig'] = None
    st, out = _post(server, '/calldb/update', {'call': 'F4TEST', 'locator': 'JN18DT'})
    assert st == 200
    st, res = _get(server, '/calldb/lookup/F4TEST')
    assert res.get('name') == 'Camille'   # prénom préservé
