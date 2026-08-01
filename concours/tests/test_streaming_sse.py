# -*- coding: utf-8 -*-
"""Streaming SSE du chat IA (évolution #1 de l'étude IA, 01/08/2026).

Avant : call_llm/proxy/call_ai_structured faisaient tous urlopen()+read()
complet (timeout 120-180 s) — le chat, le coach et le débrief étaient un mur
figé, donc toute l'IA était inexploitable en trafic. On streame désormais la
réponse token par token via un endpoint SSE qui TAILE le buffer de l'analyse
serveur (laquelle tourne dans un thread de fond et survit au changement d'onglet).

Ces tests figent DEUX choses :
  1. call_llm_stream parse correctement le SSE de chaque famille de fournisseur
     (Anthropic, OpenAI-compatible) et retombe en non-streamé pour Gemini.
  2. Le flux SSE /agent/analyze/stream se termine TOUJOURS de lui-même — c'est
     LA garantie anti-fuite de threads sur 360 h d'expédition (un thread OS par
     connexion sur ThreadingHTTPServer) : fin d'analyse, id introuvable, ET
     surtout la deadline dure quand rien ne finit.
"""
import http.server
import json
import os
import sys
import threading
import time
import urllib.request

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as h   # noqa: E402


# ─── Faux flux amont pour call_llm_stream ───────────────────────────────────

class _FakeResp:
    """Imite juste ce que call_llm_stream utilise d'une réponse urlopen :
    itération ligne à ligne (readline) sous context manager."""
    def __init__(self, lines):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self._lines)


def _patch_urlopen(monkeypatch, lines, captured=None):
    def fake(req, timeout=None, context=None):
        if captured is not None:
            captured['data'] = req.data
            captured['url'] = req.full_url
        return _FakeResp(list(lines))
    monkeypatch.setattr(h.urllib.request, 'urlopen', fake)


def test_call_llm_stream_anthropic_parse_et_delta(monkeypatch):
    lignes = [
        b'event: message_start\n',
        b'data: {"type":"message_start"}\n',
        b'\n',
        b'event: content_block_delta\n',
        b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Bon"}}\n',
        b'\n',
        b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"jour"}}\n',
        b'data: {"type":"message_stop"}\n',
    ]
    cap = {}
    _patch_urlopen(monkeypatch, lignes, cap)
    cfg = {'api_provider': 'anthropic', 'api_key': 'x', 'ai_model': 'claude-sonnet-4-6'}
    recu = []
    full = h.call_llm_stream(cfg, 'sys', [{'role': 'user', 'content': 'hi'}], on_delta=recu.append)
    assert recu == ['Bon', 'jour']            # streamé fragment par fragment
    assert full == 'Bonjour'                  # texte complet reconstitué
    assert json.loads(cap['data'])['stream'] is True   # a bien demandé le flux
    assert 'api.anthropic.com' in cap['url']


def test_call_llm_stream_openai_compatible_parse(monkeypatch):
    lignes = [
        b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n',
        b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n',
        b'data: {"choices":[{"delta":{"content":"lo"}}]}\n',
        b'data: [DONE]\n',
    ]
    cap = {}
    _patch_urlopen(monkeypatch, lignes, cap)
    cfg = {'api_provider': 'openai', 'api_key': 'x'}
    recu = []
    full = h.call_llm_stream(cfg, '', [{'role': 'user', 'content': 'hi'}], on_delta=recu.append)
    assert recu == ['Hel', 'lo']
    assert full == 'Hello'
    assert json.loads(cap['data'])['stream'] is True


def test_call_llm_stream_gemini_retombe_en_non_streame(monkeypatch):
    """Gemini a un format SSE distinct : on retombe sur call_llm (un bloc)."""
    appels = []

    def faux_call_llm(cfg, sysp, msgs, model=None, max_tokens=4096):
        appels.append(True)
        return 'REPONSE GEMINI'
    monkeypatch.setattr(h, 'call_llm', faux_call_llm)
    recu = []
    full = h.call_llm_stream({'api_provider': 'gemini', 'api_key': 'x'}, 's',
                             [{'role': 'user', 'content': 'hi'}], on_delta=recu.append)
    assert full == 'REPONSE GEMINI'
    assert recu == ['REPONSE GEMINI']         # un seul delta = tout le texte
    assert len(appels) == 1                    # a bien pris le repli call_llm


def test_call_llm_stream_sans_cle_leve(monkeypatch):
    with pytest.raises(RuntimeError):
        h.call_llm_stream({'api_provider': 'anthropic', 'api_key': ''}, '', [],
                          on_delta=lambda p: None)


# ─── Endpoint SSE : streamer + TOUJOURS se terminer (anti-fuite 360 h) ──────

@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield 'http://127.0.0.1:%d' % port
    srv.shutdown()


def _consume_sse(base, aid, timeout=20):
    """Lit le flux SSE jusqu'à sa fermeture par le serveur, puis le découpe en
    événements. Le fait que urlopen().read() RETOURNE (sans blocage) DANS le
    timeout est en soi la preuve que le flux se termine — donc que le thread se
    libère."""
    url = base + '/agent/analyze/stream?id=' + urllib.request.quote(aid)
    with urllib.request.urlopen(url, timeout=timeout) as r:
        raw = r.read().decode('utf-8', 'replace')
    events, cur = [], {'event': 'message', 'data': ''}
    for line in raw.split('\n'):
        if line.startswith(':') or line.startswith('retry:'):
            continue
        if line == '':
            if cur['data']:
                events.append(cur)
            cur = {'event': 'message', 'data': ''}
        elif line.startswith('event:'):
            cur['event'] = line[6:].strip()
        elif line.startswith('data:'):
            cur['data'] += line[5:].strip()
    if cur['data']:
        events.append(cur)
    return events


def _seed(aid, **fields):
    with h._agent_lock:
        h._agent_analyses[aid] = {'ts': time.time(), 'status': 'running',
                                  'reply': '', 'error': ''}
        h._agent_analyses[aid].update(fields)


def _drop(aid):
    with h._agent_lock:
        h._agent_analyses.pop(aid, None)


def test_sse_streame_le_buffer_puis_done_et_se_termine(serveur):
    """Un thread de fond remplit le buffer par morceaux ; le flux SSE pousse les
    fragments AU FIL DE L'EAU puis un 'done' avec la réponse complète, et se
    termine (read() retourne)."""
    aid = 'test-stream-1'
    _seed(aid)

    def producteur():
        for frag in ['Salut ', 'le ', 'pile-up']:
            time.sleep(0.15)
            with h._agent_lock:
                a = h._agent_analyses[aid]
                a['reply'] = (a['reply'] or '') + frag
        with h._agent_lock:
            h._agent_analyses[aid].update(status='done', reply='Salut le pile-up')
    threading.Thread(target=producteur, daemon=True).start()
    try:
        events = _consume_sse(serveur, aid)
    finally:
        _drop(aid)
    deltas = [json.loads(e['data'])['t'] for e in events if e['event'] == 'message']
    assert ''.join(deltas) == 'Salut le pile-up'
    assert len(deltas) >= 2                    # bien reçu EN PLUSIEURS morceaux
    done = [e for e in events if e['event'] == 'done']
    assert done and json.loads(done[0]['data'])['reply'] == 'Salut le pile-up'


def test_sse_id_introuvable_echoue_proprement_et_se_termine(serveur):
    events = _consume_sse(serveur, 'jamais-vu', timeout=10)
    failed = [e for e in events if e['event'] == 'failed']
    assert failed and json.loads(failed[0]['data'])['error'] == 'introuvable'


def test_sse_statut_erreur_donne_un_failed(serveur):
    aid = 'test-erreur'
    _seed(aid, status='error', error='clé invalide', reply='')
    try:
        events = _consume_sse(serveur, aid, timeout=10)
    finally:
        _drop(aid)
    failed = [e for e in events if e['event'] == 'failed']
    assert failed and 'clé' in json.loads(failed[0]['data'])['error']


def test_sse_deadline_dure_termine_un_flux_qui_ne_finit_jamais(serveur, monkeypatch):
    """LA garantie anti-fuite : une analyse coincée en 'running' pour toujours
    ne doit PAS tenir le thread indéfiniment. Deadline courte → 'failed délai'
    et read() retourne bien (sinon le test dépasse son propre timeout)."""
    monkeypatch.setattr(h, 'SSE_DEADLINE_S', 0.4)
    monkeypatch.setattr(h, 'SSE_HEARTBEAT_S', 0.1)
    aid = 'test-coince'
    _seed(aid, status='running', reply='début…')   # ne passera JAMAIS à done
    t0 = time.time()
    try:
        events = _consume_sse(serveur, aid, timeout=10)
    finally:
        _drop(aid)
    assert time.time() - t0 < 5                 # s'est terminé vite (pas de fuite)
    failed = [e for e in events if e['event'] == 'failed']
    assert failed and json.loads(failed[0]['data'])['error'] == 'délai dépassé'
    # Le partiel déjà présent a quand même été poussé avant l'abandon.
    deltas = [json.loads(e['data'])['t'] for e in events if e['event'] == 'message']
    assert ''.join(deltas) == 'début…'
