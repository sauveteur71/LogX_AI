# -*- coding: utf-8 -*-
"""Chasse assistée — l'agent qui AGIT (évolution IA #7, 01/08/2026).

L'agent PROPOSE une action physique (pointer le rotor / QSY) via tool-use ; le
serveur ne l'exécute JAMAIS — il renvoie l'action, le client la confirme, et
c'est le clic qui appelle l'endpoint existant. Ces tests figent la validation de
l'action (jamais une valeur aberrante), le parsing tool-use, et le job asynchrone.
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


# ─── Validation de l'action proposée ────────────────────────────────────────

def test_rotor_valide():
    a = h.pending_action_from_tool({'tool': 'pointer_rotor', 'input': {'azimut': 45.4, 'cible': 'JA1XYZ'}})
    assert a == {'type': 'rotor', 'azimut': 45, 'cible': 'JA1XYZ'}


def test_rotor_azimut_hors_bornes_refuse():
    assert h.pending_action_from_tool({'tool': 'pointer_rotor', 'input': {'azimut': 400, 'cible': 'X'}}) is None
    assert h.pending_action_from_tool({'tool': 'pointer_rotor', 'input': {'azimut': -5, 'cible': 'X'}}) is None


def test_rotor_azimut_non_numerique_refuse():
    assert h.pending_action_from_tool({'tool': 'pointer_rotor', 'input': {'azimut': 'nord', 'cible': 'X'}}) is None


def test_qsy_valide():
    a = h.pending_action_from_tool({'tool': 'qsy_radio', 'input': {'freq_khz': 14025.5, 'mode': 'CW', 'cible': 'VK9'}})
    assert a['type'] == 'qsy' and a['freq_khz'] == 14025.5 and a['mode'] == 'CW' and a['cible'] == 'VK9'


def test_qsy_frequence_absurde_refuse():
    assert h.pending_action_from_tool({'tool': 'qsy_radio', 'input': {'freq_khz': 0, 'cible': 'X'}}) is None
    assert h.pending_action_from_tool({'tool': 'qsy_radio', 'input': {'freq_khz': -1, 'cible': 'X'}}) is None


def test_outil_inconnu_ou_vide_refuse():
    assert h.pending_action_from_tool(None) is None
    assert h.pending_action_from_tool({'tool': 'lancer_missile', 'input': {}}) is None


# ─── call_llm_actions : tool-use Anthropic, texte pour les autres ───────────

class _FakeResp:
    def __init__(self, obj):
        self._b = json.dumps(obj).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._b


def test_call_llm_actions_anthropic_extrait_le_tool_use(monkeypatch):
    cap = {}

    def fake(req, timeout=None, context=None):
        cap['data'] = req.data
        return _FakeResp({'content': [
            {'type': 'text', 'text': 'Je te propose de viser le Japon.'},
            {'type': 'tool_use', 'name': 'pointer_rotor', 'input': {'azimut': 45, 'cible': 'JA1XYZ'}},
        ]})
    monkeypatch.setattr(h.urllib.request, 'urlopen', fake)
    r = h.call_llm_actions({'api_provider': 'anthropic', 'api_key': 'x', 'ai_model': 'claude-sonnet-4-6'},
                           'sys', [{'role': 'user', 'content': 'chasse'}])
    assert 'Japon' in r['text']
    assert r['action']['tool'] == 'pointer_rotor'
    assert json.loads(cap['data']).get('tools')      # les outils ont bien été envoyés


def test_call_llm_actions_autre_fournisseur_texte_seul(monkeypatch):
    monkeypatch.setattr(h, 'call_llm', lambda *a, **k: 'Conseil en texte simple.')
    r = h.call_llm_actions({'api_provider': 'openai', 'api_key': 'x'}, 's', [{'role': 'user', 'content': 'x'}])
    assert r['text'] == 'Conseil en texte simple.' and r['action'] is None


# ─── Endpoint asynchrone /agent/act + /agent/act/state ──────────────────────

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


def test_agent_act_propose_une_action(serveur, monkeypatch):
    monkeypatch.setattr(h, 'call_llm_actions', lambda *a, **k: {
        'text': 'Le meilleur spot est JA1XYZ, vise-le.',
        'action': {'tool': 'pointer_rotor', 'input': {'azimut': 45, 'cible': 'JA1XYZ'}}})
    saved = _seed_cfg({'api_key': 'x', 'api_provider': 'anthropic'})
    try:
        # needs_context=false + system fourni -> pas de do_refresh ni build_system_prompt
        code, j = _post(serveur, '/agent/act', {'needs_context': False, 'system': 's', 'message': 'chasse'})
        assert code == 200 and j.get('id')
        aid = j['id']
        state = None
        for _ in range(50):
            with urllib.request.urlopen(serveur + '/agent/act/state?id=' + aid, timeout=5) as r:
                state = json.loads(r.read())
            if state['status'] != 'running':
                break
            time.sleep(0.1)
        assert state['status'] == 'done'
        assert 'JA1XYZ' in state['reply']
        assert state['action'] == {'type': 'rotor', 'azimut': 45, 'cible': 'JA1XYZ'}
    finally:
        _restore_cfg(saved)


def test_agent_act_sans_cle_refuse(serveur):
    saved = _seed_cfg({'api_key': ''})
    try:
        code, j = _post(serveur, '/agent/act', {'needs_context': False, 'system': 's'})
        assert code == 400 and 'error' in j
    finally:
        _restore_cfg(saved)


def test_agent_act_exige_le_token(serveur):
    saved = _seed_cfg({'api_key': 'x'})
    try:
        code, _ = _post(serveur, '/agent/act', {'needs_context': False}, token=False)
        assert code in (401, 403)
    finally:
        _restore_cfg(saved)
