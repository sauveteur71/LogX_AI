# -*- coding: utf-8 -*-
"""Stratégie pile-up FT8 (évolution IA #8, 01/08/2026).

L'IA lit la SÉRIE des décodages d'UNE station DX (freq Tx, qui elle répond, SNR)
et conseille où/quand appeler. _decodes ne gardait qu'un last_seen PLAT : on
ajoute un ring buffer borné par indicatif (mémoire tenue sur 360 h). Purement
consultatif ; jamais d'émission. Ces tests figent le ring buffer, le prompt et
l'endpoint asynchrone.
"""
import collections
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

import logx_wsjtx as w   # noqa: E402
import logx_http as h    # noqa: E402


def _clear():
    with w._decodes_lock:
        w._decodes.clear()
        w._decode_series.clear()


# ─── Ring buffer par indicatif ──────────────────────────────────────────────

def test_decode_history_bornee_et_ordonnee():
    _clear()
    dq = collections.deque(maxlen=w._DECODE_SERIE_MAX)
    for i in range(40):                    # plus que le max -> les plus anciens tombent
        dq.append({'t': time.time() - (40 - i), 'snr': -i, 'df': 1000 + i, 'msg': 'm%d' % i})
    with w._decodes_lock:
        w._decode_series['F4ABC'] = dq
    hist = w.decode_history('F4ABC')
    assert len(hist) == w._DECODE_SERIE_MAX          # borné (pas de fuite)
    assert hist[-1]['msg'] == 'm39'                  # le plus RÉCENT en dernier
    assert 'il_y_a_s' in hist[0]                     # heure relative fournie


def test_record_decode_alimente_la_serie():
    _clear()
    w.record_decode({'message': 'CQ F4ABC JN18', 'snr': -12, 'delta_hz': 1200, 'mode': 'FT8'})
    w.record_decode({'message': 'CQ F4ABC JN18', 'snr': -10, 'delta_hz': 1210, 'mode': 'FT8'})
    hist = w.decode_history('F4ABC')
    assert len(hist) >= 2
    assert hist[-1]['snr'] == -10
    _clear()


def test_purge_du_cache_purge_la_serie():
    """Une station évincée de _decodes (inactive) doit aussi disparaître de la
    série : sinon fuite mémoire sur 360 h."""
    _clear()
    with w._decodes_lock:
        w._decodes['OLD'] = {'band': '', 'freq_mhz': 0, 'mode': 'FT8', 'last_seen': 0}   # très vieux
        w._decode_series['OLD'] = collections.deque([{'t': 0, 'snr': -1, 'df': 1, 'msg': 'x'}])
    w.recent_decodes()                    # déclenche la purge
    assert w.decode_history('OLD') == []
    _clear()


def test_prompt_contient_lindicatif_et_les_lignes():
    p = h.build_ft8_strategy_prompt('VK9XY', [
        {'il_y_a_s': 12, 'snr': -8, 'df': 1500, 'msg': 'CQ VK9XY'},
        {'il_y_a_s': 0, 'snr': -14, 'df': 1500, 'msg': 'JA1X VK9XY -18'}])
    assert 'VK9XY' in p and '1500 Hz' in p and 'CQ VK9XY' in p


# ─── Endpoint asynchrone /wsjtx/strategy ────────────────────────────────────

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


def _wait_done(base, aid):
    for _ in range(50):
        with urllib.request.urlopen(base + '/wsjtx/strategy/state?id=' + aid, timeout=5) as r:
            s = json.loads(r.read())
        if s['status'] != 'running':
            return s
        time.sleep(0.1)
    return None


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


def test_strategy_donne_un_verdict(serveur, monkeypatch):
    monkeypatch.setattr(h, 'call_llm', lambda *a, **k: 'Cale-toi 200 Hz plus bas, elle travaille en split.')
    _clear()
    with w._decodes_lock:
        w._decode_series['F4ABC'] = collections.deque([
            {'t': time.time(), 'snr': -10, 'df': 1200, 'msg': 'CQ F4ABC'},
            {'t': time.time(), 'snr': -8, 'df': 1200, 'msg': 'JA1X F4ABC -12'}], maxlen=30)
    saved = _seed_cfg({'api_key': 'x', 'api_provider': 'anthropic'})
    try:
        code, j = _post(serveur, '/wsjtx/strategy', {'call': 'F4ABC'})
        assert code == 200 and j['id']
        s = _wait_done(serveur, j['id'])
        assert s and s['status'] == 'done' and 'split' in s['reply']
        assert len(s['decodes']) == 2         # les décodages utilisés sont renvoyés (transparence)
    finally:
        _restore_cfg(saved); _clear()


def test_strategy_pas_assez_de_decodes(serveur):
    _clear()
    saved = _seed_cfg({'api_key': 'x'})
    try:
        code, j = _post(serveur, '/wsjtx/strategy', {'call': 'JAMAIS_ENTENDU'})
        assert code == 200
        s = _wait_done(serveur, j['id'])
        assert s['status'] == 'done' and 'Pas assez' in s['reply']
    finally:
        _restore_cfg(saved)


def test_strategy_sans_indicatif_refuse(serveur):
    saved = _seed_cfg({'api_key': 'x'})
    try:
        code, j = _post(serveur, '/wsjtx/strategy', {'call': ''})
        assert code == 400
    finally:
        _restore_cfg(saved)


def test_strategy_sans_cle_refuse(serveur):
    saved = _seed_cfg({'api_key': ''})
    try:
        code, j = _post(serveur, '/wsjtx/strategy', {'call': 'F4ABC'})
        assert code == 400
    finally:
        _restore_cfg(saved)


def test_strategy_exige_le_token(serveur):
    saved = _seed_cfg({'api_key': 'x'})
    try:
        code, _ = _post(serveur, '/wsjtx/strategy', {'call': 'F4ABC'}, token=False)
        assert code in (401, 403)
    finally:
        _restore_cfg(saved)
