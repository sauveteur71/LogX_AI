# -*- coding: utf-8 -*-
"""Nudges IA événementiels (évolution IA #5, 01/08/2026).

Le coach déterministe pousse UNE phrase d'action au bon moment (toast barre
d'état). Ces tests figent le choix de l'événement + sa signature de dédup, et
le fait que le serveur ne calcule le nudge QUE si la page le demande (?nudges=1).
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

import logx_coach as coach   # noqa: E402
import logx_http as h        # noqa: E402

RUN = {'status': 'en_cours', 'remaining_h': 3.0}


def test_hors_concours_aucun_nudge():
    assert coach.coach_nudge({'clock': {'status': 'avant'}}) is None
    assert coach.coach_nudge({'clock': {'status': 'termine'}}) is None


def test_cible_jamais_faite_spottee_est_prioritaire():
    """Une entité jamais faite ET spottée MAINTENANT : le spot prouve la bande
    ouverte — c'est le nudge le plus payant, avant rythme/silence."""
    state = {'clock': RUN,
             'stats': {'rate_avg': 40, 'qso_last_hour': 2, 'minutes_since_last': 40},
             'new_targets': [{'type': 'dxcc', 'label': 'Japon', 'call': 'JA1XYZ', 'freq': '14025'}]}
    n = coach.coach_nudge(state)
    assert n['sig'] == 'target:JA1XYZ' and n['level'] == 'action'
    assert 'Japon' in n['text'] and 'JA1XYZ' in n['text']


def test_effondrement_du_rythme():
    state = {'clock': RUN, 'stats': {'rate_avg': 40, 'qso_last_hour': 10}}
    n = coach.coach_nudge(state)
    assert n['sig'] == 'rate:10' and n['level'] == 'attention'
    assert '10' in n['text']


def test_rythme_ok_pas_de_nudge():
    state = {'clock': RUN, 'stats': {'rate_avg': 40, 'qso_last_hour': 35,
                                     'minutes_since_last': 2}}
    assert coach.coach_nudge(state) is None


def test_silence_radio():
    state = {'clock': RUN, 'stats': {'minutes_since_last': 22}}
    n = coach.coach_nudge(state)
    assert n['sig'] == 'silence:1' and '22' in n['text']


def test_signature_silence_change_par_tranche_de_15_min():
    a = coach.coach_nudge({'clock': RUN, 'stats': {'minutes_since_last': 16}})
    b = coach.coach_nudge({'clock': RUN, 'stats': {'minutes_since_last': 34}})
    assert a['sig'] != b['sig']       # une nouvelle tranche → un nouveau toast permis


# ─── Gating de l'endpoint (?nudges=1) ───────────────────────────────────────

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


def test_endpoint_ne_calcule_le_nudge_que_sur_demande(serveur):
    sans = _get(serveur, '/coach/state')
    assert 'nudge' not in sans           # aucune option → le serveur ne dépense rien
    avec = _get(serveur, '/coach/state?nudges=1')
    assert 'nudge' in avec               # clé présente (valeur null si rien d'actionnable)
