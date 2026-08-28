# -*- coding: utf-8 -*-
"""Planificateur de session (logx_session + endpoint /session/plan).

La construction du message est DÉTERMINISTE (testée directement) ; l'appel LLM
est mocké pour l'endpoint. Le planificateur est CONSULTATIF : il ne déclenche
aucune action ni émission (garde-fou vérifié dans le prompt système)."""
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

import logx_http as h        # noqa: E402
import logx_session as session   # noqa: E402


# ── Construction du message (déterministe) ───────────────────────────────────

def test_build_message_inclut_les_contraintes():
    msg = session.build_session_message(
        {'duree_min': 30, 'objectif': '3 nouveaux DXCC', 'mode': 'FT8',
         'bandes': '20m', 'puissance_w': 20})
    for attendu in ('30 minutes', '3 nouveaux DXCC', 'FT8', '20m', '20 W'):
        assert attendu in msg
    assert 'consultatif' in msg.lower()


def test_build_message_accepte_une_liste_de_bandes():
    msg = session.build_session_message({'bandes': ['20m', '15m']})
    assert '20m, 15m' in msg


def test_build_message_tolere_les_champs_absents():
    msg = session.build_session_message({})   # ne doit pas lever
    assert 'Planifie ma session' in msg


def test_system_prompt_est_consultatif():
    s = session.SESSION_PLAN_SYSTEM
    assert 'CONSULTATIF' in s
    assert "Ne propose JAMAIS d'émettre automatiquement" in s
    assert 'critères' in s.lower() or "CRITÈRES D'ARRÊT" in s


# ── Endpoint /session/plan (LLM mocké) ───────────────────────────────────────

@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % port
    srv.shutdown()


def _post(base, path, obj, token=True):
    hdr = {'Content-Type': 'application/json'}
    if token:
        hdr['X-RC-Token'] = h.AUTH_TOKEN
    rq = urllib.request.Request(base + path, data=json.dumps(obj).encode(), headers=hdr, method='POST')
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _seed_cfg(cfg):
    with h.config_lock:
        saved = dict(h.current_config)
        h.current_config.clear()
        h.current_config.update(cfg)
    return saved


def _restore_cfg(saved):
    with h.config_lock:
        h.current_config.clear()
        h.current_config.update(saved)


def test_endpoint_rend_un_plan(serveur, monkeypatch):
    capte = {}

    def faux_llm(cfg, system, messages, *a, **k):
        capte['system'] = system
        capte['msg'] = messages[0]['content']
        return "0-10 min : 20m FT8 vers l'Europe.\nCritères d'arrêt : ..."
    monkeypatch.setattr(h, 'call_llm', faux_llm)
    saved = _seed_cfg({'api_key': 'x', 'api_provider': 'anthropic'})
    try:
        code, j = _post(serveur, '/session/plan',
                        {'duree_min': 30, 'objectif': 'DXCC', 'mode': 'FT8', 'bandes': '20m'})
        assert code == 200
        assert 'FT8' in j['plan']
        assert capte['system'] is session.SESSION_PLAN_SYSTEM   # bon prompt consultatif
        assert '30 minutes' in capte['msg']
    finally:
        _restore_cfg(saved)


def test_endpoint_sans_cle_refuse(serveur):
    saved = _seed_cfg({'api_key': ''})
    try:
        code, j = _post(serveur, '/session/plan', {'duree_min': 30})
        assert code == 400 and 'error' in j
    finally:
        _restore_cfg(saved)
