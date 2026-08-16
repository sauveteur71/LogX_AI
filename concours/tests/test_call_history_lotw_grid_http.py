# -*- coding: utf-8 -*-
"""Câblage HTTP de la mini-grille LoTW (logx_awards.lotw_grid) dans l'endpoint
GET /call/history déjà existant — même harnais que tests/test_pota_spot_http.py
(vrai serveur sur port éphémère). Le calcul lui-même (statut par créneau
bande×mode, critère LoTW-et-rien-d'autre) est couvert en profondeur par
tests/test_besoin_lotw.py ; ce fichier vérifie seulement que la réponse HTTP
transporte bien le champ, pour le bon indicatif, sans casser le reste de la
réponse (new_one/besoin_lotw/state déjà en place)."""
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


def test_lotw_grid_present_et_actif_pour_un_indicatif_connu(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {'callsign': 'F4GLD', 'contest': ''})
    monkeypatch.setattr(httpmod, 'shared_log', [
        {'call': 'W1ABC', 'band': '14', 'mode': 'SSB', 'date': '20260101', 'time': '1200'},
    ])
    status, d = _get(server, '/call/history?call=W1ABC&band=14&mode=SSB')
    assert status == 200
    assert d['lotw_grid']['active'] is True
    assert d['lotw_grid']['grid']['14']['PHONE'] == 'worked'
    # Le câblage n'a pas cassé les champs déjà présents.
    assert 'new_one' in d and 'lotw_need' in d


def test_lotw_grid_inactif_pour_indicatif_sans_entite(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {'callsign': 'F4GLD', 'contest': ''})
    monkeypatch.setattr(httpmod, 'shared_log', [])
    status, d = _get(server, '/call/history?call=XX&band=14&mode=SSB')
    assert status == 200
    assert d['lotw_grid'] == {'active': False}
