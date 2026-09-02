# -*- coding: utf-8 -*-
"""User-Agent identifiable pour les requêtes vers l'infrastructure SOTA.

La doc SOTA (API ToS) recommande un « descriptive User-Agent including
callsign ». On vérifie le helper pur `sota_user_agent` ET le câblage réel :
`fetch_sota_spots(callsign=...)` doit transmettre ce User-Agent à `fetch_url`.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_sota as sota          # noqa: E402
import logx_utils                 # noqa: E402
from logx_version import APP_VERSION   # noqa: E402


def test_ua_avec_indicatif():
    assert sota.sota_user_agent('F4GLD') == 'LogX-AI/%s (F4GLD)' % APP_VERSION


def test_ua_normalise_maj_et_espaces():
    assert sota.sota_user_agent('  f4gld ') == 'LogX-AI/%s (F4GLD)' % APP_VERSION


def test_ua_sans_indicatif_pas_de_parentheses():
    attendu = 'LogX-AI/%s' % APP_VERSION
    assert sota.sota_user_agent('') == attendu
    assert sota.sota_user_agent(None) == attendu
    assert '(' not in sota.sota_user_agent('')


def test_ua_contient_marque_et_version():
    ua = sota.sota_user_agent('F4GLD')
    assert ua.startswith('LogX-AI/')
    assert APP_VERSION in ua


def test_fetch_spots_transmet_le_user_agent(monkeypatch):
    # Câblage : l'indicatif passé à fetch_sota_spots doit atterrir dans le
    # User-Agent remis à fetch_url (sinon le helper serait inerte).
    capte = {}

    def faux_fetch_url(url, timeout=10, log_url=True, user_agent=None):
        capte['ua'] = user_agent
        return None   # échec réseau simulé -> pas de parsing, on ne teste que l'appel

    monkeypatch.setattr(logx_utils, 'fetch_url', faux_fetch_url)
    # Cache vide pour forcer l'appel réseau.
    monkeypatch.setattr(sota, '_spots_cache', {'data': None, 'ts': 0})
    sota.fetch_sota_spots(callsign='F4GLD')
    assert capte['ua'] == 'LogX-AI/%s (F4GLD)' % APP_VERSION
