# -*- coding: utf-8 -*-
"""Garde-fou « multiplicateur fantôme » (évolution IA #3, 01/08/2026).

En CQ WW, une zone CQ bustée compte comme multiplicateur puis est RETIRÉE au
checking : pénalité nette. On compare la zone SAISIE à ce que cty.dat attend
pour l'indicatif (déterministe, instantané, hors-ligne) ; l'IA ne tranche
l'ambigu (portable, /MM, pays à cheval) qu'à la demande. Ces tests figent la
comparaison et l'endpoint.
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

import logx_dxcc as dxcc   # noqa: E402
import logx_http as h      # noqa: E402


def _patch(monkeypatch, ret):
    monkeypatch.setattr(dxcc, 'lookup', lambda call: ret)


def test_zone_correcte_match_true(monkeypatch):
    _patch(monkeypatch, {'cq_zone': '14', 'country': 'France', 'continent': 'EU'})
    r = dxcc.verifier_zone_cq('F4GLD', '14')
    assert r['match'] is True and r['expected'] == '14'


def test_zone_fausse_match_false_avec_attendu(monkeypatch):
    _patch(monkeypatch, {'cq_zone': '14', 'country': 'France', 'continent': 'EU'})
    r = dxcc.verifier_zone_cq('F4GLD', '20')
    assert r['match'] is False
    assert r['expected'] == '14' and r['entity'] == 'France'
    assert r['entered'] == '20'


def test_zeros_de_tete_ne_comptent_pas(monkeypatch):
    _patch(monkeypatch, {'cq_zone': '14', 'country': 'France'})
    assert dxcc.verifier_zone_cq('F4GLD', '014')['match'] is True


def test_indicatif_inconnu_pas_d_alerte(monkeypatch):
    """cty.dat ne connaît pas l'indicatif → match=None : on ne CRIE jamais sur
    ce qu'on ne sait pas vérifier (sinon l'opérateur ignore la pastille)."""
    _patch(monkeypatch, None)
    assert dxcc.verifier_zone_cq('XYZ123', '14')['match'] is None


def test_valeur_vide_pas_d_alerte(monkeypatch):
    _patch(monkeypatch, {'cq_zone': '14', 'country': 'France'})
    assert dxcc.verifier_zone_cq('F4GLD', '')['match'] is None


def test_valeur_non_numerique_comparee(monkeypatch):
    _patch(monkeypatch, {'cq_zone': '14', 'country': 'France'})
    assert dxcc.verifier_zone_cq('F4GLD', 'AB')['match'] is False


# ─── Endpoint /exchange/check ───────────────────────────────────────────────

@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % port
    srv.shutdown()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return json.loads(r.read())


def test_endpoint_signale_la_zone_fausse(serveur, monkeypatch):
    _patch(monkeypatch, {'cq_zone': '14', 'country': 'France', 'continent': 'EU'})
    d = _get(serveur, '/exchange/check?kind=cq_zone&call=F4GLD&value=20')
    assert d['ok'] is True and d['match'] is False
    assert d['expected'] == '14' and d['kind'] == 'cq_zone'


def test_endpoint_zone_correcte(serveur, monkeypatch):
    _patch(monkeypatch, {'cq_zone': '14', 'country': 'France'})
    d = _get(serveur, '/exchange/check?kind=cq_zone&call=F4GLD&value=14')
    assert d['match'] is True


def test_endpoint_kind_non_supporte(serveur):
    d = _get(serveur, '/exchange/check?kind=itu_zone&call=F4GLD&value=27')
    assert d['ok'] is False and d['match'] is None
