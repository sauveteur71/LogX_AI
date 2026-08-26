# -*- coding: utf-8 -*-
"""Audit : un échec réseau de collecte Es'/VHF réservait le créneau de fetch et
supprimait TOUTE collecte pendant FETCH_CACHE_S (90 s) — blackout de propagation
sur un simple blip. Correctif : un échec autorise une re-tentative COURTE et
bornée (FETCH_RETRY_S), pas d'attente des 90 s, pas de storm."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_es_opening as es


def _failing(*a):
    _failing.calls += 1
    raise OSError('réseau coupé')


def test_echec_reseau_autorise_une_retentative_courte():
    es._last_fetch['50'] = 0.0
    _failing.calls = 0
    es.opening_index('50', now=1000.0, fetch_fn=_failing)      # fetch tenté -> échec
    assert _failing.calls == 1
    es.opening_index('50', now=1005.0, fetch_fn=_failing)      # +5 s : trop tôt
    assert _failing.calls == 1
    es.opening_index('50', now=1000.0 + es.FETCH_RETRY_S + 1, fetch_fn=_failing)  # re-tentative
    assert _failing.calls == 2, "un échec transitoire ne doit pas bloquer la collecte 90 s"
