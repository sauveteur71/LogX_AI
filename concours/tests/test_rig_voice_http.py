# -*- coding: utf-8 -*-
"""Test HTTP de bout en bout pour POST /rig/voice (chantier keyer vocal
skip_ptt, 04/08/2026) — même harnais que tests/test_pota_spot_http.py (vrai
serveur sur port éphémère). logx_voicekeyer.send_voice_message est
monkeypatché : ce test couvre le CÂBLAGE du handler (payload -> argument
skip_ptt), pas la logique PTT/synthèse elle-même (déjà couverte par
tests/test_voicekeyer.py)."""
import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod
import logx_voicekeyer as vk


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()   # libere la socket d ecoute
        t.join(timeout=5)


def _post(base, path, payload):
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json',
                 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_rig_voice_transmet_skip_ptt_au_module(server, monkeypatch):
    captured = {}
    def fake_send(cfg, text, lang='', skip_ptt=False, segments=None):
        captured['skip_ptt'] = skip_ptt
        captured['text'] = text
        return {'ok': True, 'text': text}
    monkeypatch.setattr(vk, 'send_voice_message', fake_send)

    status, d = _post(server, '/rig/voice', {
        'template': '{CALL} de {MYCALL}, {RST_SENT}',
        'call': 'F8TEST', 'mycall': 'F1TEST', 'rst_sent': '59',
        'skip_ptt': True,
    })
    assert status == 200 and d['ok'] is True
    assert captured['skip_ptt'] is True


def test_rig_voice_sans_skip_ptt_reste_false(server, monkeypatch):
    """Le déclenchement réel (logx_logbook.js) n'envoie jamais skip_ptt —
    absence de la clé doit se traduire par False, pas par une exception.

    Depuis le garde-fou TX unifié (24/08/2026), un déclenchement RÉEL doit être
    armé et en phonie pour aboutir : on fournit donc armed+mode, sinon la requête
    est bloquée (403) avant d'atteindre send_voice_message — c'est justement ce
    que couvre test_voice_tx_guard_http.py."""
    captured = {}
    def fake_send(cfg, text, lang='', skip_ptt=False, segments=None):
        captured['skip_ptt'] = skip_ptt
        return {'ok': True, 'text': text}
    monkeypatch.setattr(vk, 'send_voice_message', fake_send)

    status, d = _post(server, '/rig/voice', {
        'template': 'CQ CQ', 'call': 'F8TEST', 'mycall': 'F1TEST',
        'armed': True, 'mode': 'USB',
    })
    assert status == 200 and d['ok'] is True
    assert captured['skip_ptt'] is False
