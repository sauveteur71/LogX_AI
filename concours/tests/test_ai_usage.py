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


def test_tarif_malforme_est_ignore_sans_planter():
    usage.enregistrer('anthropic', 'claude-x', 1_000_000, 1_000_000)
    # Tarifs malformés (config opérateur douteuse) : ni exception, ni coût inventé.
    assert usage.resume({'anthropic': 'pas-un-dict'}).get('cout_usd_estime') is None
    assert usage.resume({'anthropic': {'in': 'x', 'out': 5}}).get('cout_usd_estime') is None
    assert usage.resume('pas-un-dict-du-tout')['calls'] == 1   # robuste même si l'arg est absurde


def test_enregistrer_reponse_par_forme_fournisseur():
    # Anthropic : usage.input_tokens / output_tokens
    usage.enregistrer_reponse('anthropic', 'claude-x', {'usage': {'input_tokens': 10, 'output_tokens': 3}})
    # OpenAI-compatible : usage.prompt_tokens / completion_tokens
    usage.enregistrer_reponse('openai', 'gpt-x', {'usage': {'prompt_tokens': 20, 'completion_tokens': 5}})
    # Gemini : usageMetadata.promptTokenCount / candidatesTokenCount
    usage.enregistrer_reponse('gemini', 'gem-x', {'usageMetadata': {'promptTokenCount': 7, 'candidatesTokenCount': 2}})
    r = usage.resume()
    assert r['calls'] == 3
    assert r['par_fournisseur']['anthropic']['in'] == 10 and r['par_fournisseur']['anthropic']['out'] == 3
    assert r['par_fournisseur']['openai']['in'] == 20 and r['par_fournisseur']['openai']['out'] == 5
    assert r['par_fournisseur']['gemini']['in'] == 7 and r['par_fournisseur']['gemini']['out'] == 2


def test_enregistrer_reponse_accepte_le_json_brut_et_ignore_le_bruit():
    usage.enregistrer_reponse('anthropic', 'claude-x', b'{"usage":{"input_tokens":4,"output_tokens":1}}')
    usage.enregistrer_reponse('anthropic', 'claude-x', b'pas du json')   # ignoré, ne lève pas
    usage.enregistrer_reponse('anthropic', 'claude-x', {'rien': 1})      # pas d'usage -> 0/0 enregistré
    r = usage.resume()
    assert r['par_fournisseur']['anthropic']['in'] == 4


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


class _FakeResp:
    def __init__(self, obj):
        self._b = json.dumps(obj).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._b


def test_call_llm_enregistre_openai_et_gemini(monkeypatch):
    # OpenAI-compatible : usage.prompt_tokens / completion_tokens
    monkeypatch.setattr(h.urllib.request, 'urlopen',
                        lambda *a, **k: _FakeResp({'choices': [{'message': {'content': 'ok'}}],
                                                   'usage': {'prompt_tokens': 11, 'completion_tokens': 4}}))
    h.call_llm({'api_provider': 'openai', 'api_key': 'x', 'ai_model': 'gpt-x'}, 's', [{'role': 'user', 'content': 'q'}])
    r = usage.resume()
    assert r['par_fournisseur']['openai']['in'] == 11 and r['par_fournisseur']['openai']['out'] == 4

    # Gemini : usageMetadata.promptTokenCount / candidatesTokenCount
    monkeypatch.setattr(h.urllib.request, 'urlopen',
                        lambda *a, **k: _FakeResp({'candidates': [{'content': {'parts': [{'text': 'ok'}]}}],
                                                   'usageMetadata': {'promptTokenCount': 6, 'candidatesTokenCount': 2}}))
    h.call_llm({'api_provider': 'gemini', 'api_key': 'x', 'ai_model': 'gem-x'}, 's', [{'role': 'user', 'content': 'q'}])
    r = usage.resume()
    assert r['par_fournisseur']['gemini']['in'] == 6 and r['par_fournisseur']['gemini']['out'] == 2


def test_endpoint_ai_usage_rend_les_faits(serveur):
    usage.enregistrer('anthropic', 'claude-x', 1234, 567)
    with urllib.request.urlopen(serveur + '/ai/usage', timeout=10) as r:
        d = json.loads(r.read())
    assert d['calls'] == 1
    assert d['in_tokens'] == 1234 and d['out_tokens'] == 567
