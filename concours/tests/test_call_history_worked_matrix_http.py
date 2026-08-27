# -*- coding: utf-8 -*-
"""Câblage HTTP de la matrice bande×mode PAR INDICATIF
(logx_awards.worked_matrix_call) dans l'endpoint GET /call/history déjà
existant — même harnais que tests/test_call_history_lotw_grid_http.py (vrai
serveur sur port éphémère). Le calcul est couvert en profondeur par
tests/test_worked_matrix_call.py ; ce fichier vérifie seulement que la réponse
HTTP transporte bien le champ, pour le bon indicatif, sans casser les champs
déjà en place (new_one / lotw_need / lotw_grid)."""
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


def _get(base, path):
    req = urllib.request.Request(base + path, headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_worked_matrix_call_present_et_actif(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {'callsign': 'F4GLD', 'contest': ''})
    monkeypatch.setattr(httpmod, 'shared_log', [
        {'call': 'TX7X', 'band': '14', 'mode': 'CW', 'date': '20260101', 'time': '1200'},
    ])
    status, d = _get(server, '/call/history?call=TX7X&band=14&mode=CW')
    assert status == 200
    assert d['worked_matrix_call']['active'] is True
    assert d['worked_matrix_call']['grid']['14']['CW'] == 'worked'
    # Le câblage n'a pas cassé les champs déjà présents.
    assert 'new_one' in d and 'lotw_need' in d and 'lotw_grid' in d


def test_worked_matrix_call_inactif_indicatif_trop_court(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {'callsign': 'F4GLD', 'contest': ''})
    monkeypatch.setattr(httpmod, 'shared_log', [])
    status, d = _get(server, '/call/history?call=XX&band=14&mode=CW')
    assert status == 200
    assert d['worked_matrix_call'] == {'active': False}
