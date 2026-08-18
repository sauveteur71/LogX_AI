# -*- coding: utf-8 -*-
"""Planification DXpédition sur CARTE IA (backlog #119) : /data/voacap
acceptait déjà tous les paramètres nécessaires côté logx_voacap.predict()
(month/year), mais l'endpoint HTTP ne les lisait jamais depuis la requête --
toute prédiction retombait silencieusement sur "maintenant", empêchant
toute comparaison de saisons pour choisir la meilleure période avant de
réserver une expédition.

Ce module teste UNIQUEMENT le passage des paramètres à travers l'endpoint
(via un predict() factice, sans le vrai binaire voacapl.exe -- voir
tests/test_voacap.py pour les tests du moteur lui-même)."""
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

import logx_http as h            # noqa: E402
import logx_voacap as voacap     # noqa: E402


@pytest.fixture
def serveur(monkeypatch):
    calls = []

    def fake_predict(**kwargs):
        calls.append(kwargs)
        return {'ok': True, 'distance_km': 1234.5, 'hours': []}

    monkeypatch.setattr(voacap, 'predict', fake_predict)
    # locator_to_latlon doit résoudre TX (station) et RX (dx) sans réseau.
    monkeypatch.setattr(h, 'locator_to_latlon', lambda s: (45.0, 3.0))

    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % port, calls
    srv.shutdown()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return json.loads(r.read())


def test_month_year_transmis_a_predict(serveur):
    base, calls = serveur
    d = _get(base, '/data/voacap?dx=VK2ABC&month=8&year=2027')
    assert d['ok'] is True
    assert len(calls) == 1
    assert calls[0]['month'] == 8
    assert calls[0]['year'] == 2027


def test_sans_month_year_reste_none_comportement_inchange(serveur):
    """Rétrocompatibilité : un appel SANS month/year (comme avant ce
    correctif, checkVoacapTarget() côté client) doit continuer à laisser
    predict() choisir "maintenant" lui-même -- jamais une valeur inventée."""
    base, calls = serveur
    d = _get(base, '/data/voacap?dx=VK2ABC')
    assert d['ok'] is True
    assert calls[0]['month'] is None
    assert calls[0]['year'] is None


def test_month_year_non_numerique_ignore_sans_planter(serveur):
    """Une valeur non numérique (manipulation d'URL, extension navigateur...)
    ne doit jamais faire planter l'endpoint -- repli sur None comme si le
    paramètre était absent."""
    base, calls = serveur
    d = _get(base, '/data/voacap?dx=VK2ABC&month=aout&year=2027')
    assert d['ok'] is True
    assert calls[0]['month'] is None
    # year, lui, est syntaxiquement valide : doit passer normalement.
    assert calls[0]['year'] == 2027
