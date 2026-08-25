# -*- coding: utf-8 -*-
"""Câblage HTTP de l'enrichissement de la base interne depuis le journal
(POST /calldb/enrich_from_log). Vrai serveur, shared_log seedé, calldb.json
isolé en tmp. Prouve que le scan du journal grave bien les prénoms sur disque.
"""
import http.server
import json
import os
import sys
import threading
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


def _post(base, path, payload=None):
    body = json.dumps(payload).encode('utf-8') if payload is not None else b''
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json', 'X-RC-Token': httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def test_enrich_from_log_grave_les_prenoms(server, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    dep._calldb_cache['sig'] = None
    # journal serveur seedé : deux QSO avec prénom, un sans
    monkeypatch.setattr(httpmod, 'shared_log', [
        {'call': 'F4ABC', 'name': 'Camille', 'locator': 'JN18DT'},
        {'call': 'DL1XYZ', 'name': 'Hans'},
        {'call': 'G0ZZZ'},
    ])
    st, out = _post(server, '/calldb/enrich_from_log')
    assert st == 200 and out.get('ok') is True
    assert out.get('updated') == 2 and out.get('scanned') == 3
    # gravé sur disque, indexé sur la racine de l'indicatif
    with open(os.path.join(tmp_path, 'calldb.json'), encoding='utf-8') as f:
        saved = json.load(f)
    assert saved['calls']['F4ABC']['name'] == 'Camille'
    assert saved['calls']['DL1XYZ']['name'] == 'Hans'
    assert 'G0ZZZ' not in saved['calls']
