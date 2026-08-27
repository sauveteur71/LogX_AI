# -*- coding: utf-8 -*-
"""Suivi de consommation IA (logx_ai_usage) — des faits (tokens réels), jamais
de prix inventé. Coût estimé UNIQUEMENT si l'opérateur fournit ses tarifs.
Un test HTTP vérifie l'endpoint /ai/usage."""
import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.request

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_ai_usage as usage   # noqa: E402
import logx_http as h           # noqa: E402


def setup_function():
    usage._reset()


def test_enregistrer_agrege_les_faits():
    usage.enregistrer('anthropic', 'claude-x', 1000, 250)
    usage.enregistrer('anthropic', 'claude-x', 500, 100)
    usage.enregistrer('openai', 'gpt-x', 200, 50)
    r = usage.resume()
    assert r['calls'] == 3
    assert r['in_tokens'] == 1700 and r['out_tokens'] == 400
    assert r['par_fournisseur']['anthropic']['calls'] == 2
    assert r['par_fournisseur']['anthropic']['in'] == 1500
    assert r['par_fournisseur']['anthropic']['models']['claude-x']['out'] == 350
    assert 'cout_usd_estime' not in r          # aucun prix fourni -> aucun coût inventé


def test_entree_invalide_est_ignoree_sans_lever():
    usage.enregistrer('anthropic', 'm', 'pas-un-nombre', None)   # ne doit pas lever
    usage.enregistrer(None, None, -5, 10)                        # négatif ignoré
    assert usage.resume()['calls'] == 0


def test_cout_seulement_si_tarif_fourni():
    usage.enregistrer('anthropic', 'claude-x', 1_000_000, 1_000_000)
    usage.enregistrer('openai', 'gpt-x', 1_000_000, 0)
    # Tarif fourni pour anthropic SEULEMENT (3 $/Mtok in, 15 $/Mtok out).
    r = usage.resume({'anthropic': {'in': 3, 'out': 15}})
    assert r['par_fournisseur']['anthropic']['cout_usd_estime'] == 18.0   # 1*3 + 1*15
    assert 'cout_usd_estime' not in r['par_fournisseur']['openai']        # non tarifé -> pas de coût
    assert r['cout_usd_estime'] == 18.0


def test_resume_vide_par_defaut():
    r = usage.resume()
    assert r['calls'] == 0 and r['in_tokens'] == 0 and r['par_fournisseur'] == {}


# ── Endpoint HTTP /ai/usage ──────────────────────────────────────────────────

@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % port
    srv.shutdown()


def test_endpoint_ai_usage_rend_les_faits(serveur):
    usage.enregistrer('anthropic', 'claude-x', 1234, 567)
    with urllib.request.urlopen(serveur + '/ai/usage', timeout=10) as r:
        d = json.loads(r.read())
    assert d['calls'] == 1
    assert d['in_tokens'] == 1234 and d['out_tokens'] == 567
