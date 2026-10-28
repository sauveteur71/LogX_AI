# -*- coding: utf-8 -*-
"""/data/spots_ranked?band=X : les spots d'UNE bande, filtrés AVANT la coupe à 40.

Défaut F4GLD (24/10/2026, CQ WW SSB, capture Bandscope 40 m « Aucun spot sur
40m » alors que la bande était pleine) : l'endpoint ne renvoyait que les 40
spots les mieux classés TOUTES BANDES confondues, et le Bandscope / la Band Map
triaient ensuite cette liste par bande. En concours, les 40 places partaient
aux multiplicateurs 14/21/28 MHz : le 40 m n'apparaissait jamais.
Harnais serveur réel (port éphémère), cache de spots simulé."""
import http.server
import json
import os
import sys
import threading
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod  # noqa: E402

PREFIXES_DX = ['JA1', 'W1', 'VK2', 'ZS6', 'PY1', 'LU1', 'BA3', 'VU2', 'YB0', 'ZL1',
               'KH6', 'VE3', 'XE1', 'CE3', 'HK3', 'OA4', 'TA1', 'UA9', '4X1', 'A71']


def _spots():
    hf = []
    for i in range(45):     # beaucoup de spots DX 14 MHz, bien classés
        hf.append({'dx': '%sA%s' % (PREFIXES_DX[i % len(PREFIXES_DX)], chr(65 + i % 26) * 2 + str(i)),
                   'freq': '%.1f' % (14150 + i), 'spotter': 'F5XX', 'time': '0400Z', 'info': ''})
    for i in range(5):      # quelques spots 40 m
        hf.append({'dx': 'F%dABC' % (i + 1), 'freq': '%.1f' % (7120 + 10 * i),
                   'spotter': 'F5XX', 'time': '0400Z', 'info': ''})
    return {'HF': hf}


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(httpmod, '_spots_from_caches', _spots)
    monkeypatch.setattr(httpmod, '_warm_band_spots', lambda *a, **k: None)
    cfg = {'contest': 'CQ_WW_SSB', 'usage_mode': 'contest', 'callsign': 'F4GLD',
           'callsign_contest': 'F4GLD', 'locator': 'JN15WD'}
    monkeypatch.setattr(httpmod.Handler, '_cfg_snapshot', lambda self: dict(cfg))
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield 'http://127.0.0.1:%d' % srv.server_address[1]
    finally:
        srv.shutdown(); srv.server_close(); t.join(timeout=5)


def _get(base, path):
    req = urllib.request.Request(base + path, headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode('utf-8'))


def test_sans_bande_la_liste_reste_coupee_a_40(server):
    d = _get(server, '/data/spots_ranked')
    assert len(d['spots']) == 40          # comportement inchangé pour les autres écrans


def test_avec_bande_tous_les_spots_de_la_bande(server):
    d = _get(server, '/data/spots_ranked?band=7')
    calls = sorted(s['call'] for s in d['spots'])
    assert calls == ['F1ABC', 'F2ABC', 'F3ABC', 'F4ABC', 'F5ABC']
    assert all(7000 <= float(s['freq']) <= 7300 for s in d['spots'])


def test_avec_bande_14_plus_de_40_possible(server):
    d = _get(server, '/data/spots_ranked?band=14')
    assert len(d['spots']) == 45 and all(str(s['band']) == '14' for s in d['spots'])


def test_les_ecrans_d_une_bande_demandent_leur_bande():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scope = open(os.path.join(base, 'logx_scope.html'), encoding='utf-8').read()
    panel = open(os.path.join(base, 'logx_panel.html'), encoding='utf-8').read()
    assert "fetch('/data/spots_ranked?band='+encodeURIComponent(band))" in scope
    tick = panel[panel.index('async function tickBandMap'):]
    assert "fetch('/data/spots_ranked?band=' + encodeURIComponent(band))" in tick[:3000]


def test_band_map_du_logbook_et_fenetre_par_bande_demandent_leur_bande():
    """Signalé par F4GLD (24/10/2026) juste après le correctif de la Band Map
    détachée : « la band map attachée n'affiche rien ». Même défaut, autres écrans."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fs = open(os.path.join(base, 'logx_filtre_spots.js'), encoding='utf-8').read()
    f = fs[fs.index('async function refreshBandMap'):]
    assert "fetch('/data/spots_ranked?band=' + encodeURIComponent(currentBand || ''))" in f[:2500]
    bande = open(os.path.join(base, 'logx_bande.html'), encoding='utf-8').read()
    assert "fetch('/data/spots_ranked?band=' + encodeURIComponent(bande))" in bande

