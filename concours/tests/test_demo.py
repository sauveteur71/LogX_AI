# -*- coding: utf-8 -*-
"""Mode démo : spots synthétiques (logx_demo) + garde /data/spots_ranked.

Isolé : le mode démo n'alimente que l'affichage (spots), jamais le log ni
l'émission. On vérifie la forme des spots synthétiques et que /data/spots_ranked
les renvoie (marqués demo:True) quand demo_mode est actif.
"""
import http.server
import json
import os
import sys
import threading
import urllib.request

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as h    # noqa: E402
import logx_demo as demo  # noqa: E402


def test_spots_demo_forme_et_marquage():
    spots = demo.spots_demo()
    assert len(spots) >= 4
    for s in spots:
        assert s['demo'] is True                     # chaque spot est marqué démo
        assert s['call'] and s['band'] and s['mode']
        assert 'credit_classe' in s and 'credit_score' in s   # même forme que les vrais
    # déterministe : deux appels donnent les mêmes indicatifs
    assert [s['call'] for s in demo.spots_demo()] == [s['call'] for s in demo.spots_demo()]


def test_demo_mode_tolere_la_chaine():
    assert h._demo_mode({'demo_mode': 'oui'}) is True
    assert h._demo_mode({'demo_mode': True}) is True
    assert h._demo_mode({'demo_mode': 'non'}) is False
    assert h._demo_mode({}) is False


@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % port
    srv.shutdown()


def _seed(cfg):
    with h.config_lock:
        saved = dict(h.current_config)
        h.current_config.clear()
        h.current_config.update(cfg)
    return saved


def _restore(saved):
    with h.config_lock:
        h.current_config.clear()
        h.current_config.update(saved)


def test_spots_ranked_renvoie_les_spots_demo(serveur):
    saved = _seed({'demo_mode': 'oui'})
    try:
        with urllib.request.urlopen(serveur + '/data/spots_ranked', timeout=10) as r:
            d = json.loads(r.read())
        assert d.get('demo') is True                          # réponse étiquetée démo
        calls = [s['call'] for s in d.get('spots', [])]
        assert 'JA1XYZ' in calls and len(calls) >= 4          # les spots synthétiques
        assert all(s.get('demo') for s in d['spots'])
    finally:
        _restore(saved)
