# -*- coding: utf-8 -*-
"""Câblage du garde-fou TX unifié sur les endpoints VOIX (24/08/2026).

Avant ce lot, /rig/voice et /voice/play prenaient le verrou TX SO2R mais ne
passaient par AUCUN garde-fou (ni interrupteur maître `armed`, ni mode, ni
bande) — contrairement à /rig/cw. Ces tests vérifient que la voix est désormais
soumise au même garde-fou (famille 'phonie') : refus BLOQUANT (403) si désarmé,
en mode CW/data, ou hors bande — AVANT toute émission réelle.

Même harnais que test_rig_voice_http.py (vrai serveur sur port éphémère,
module d'émission monkeypatché : on couvre le CÂBLAGE, pas la synthèse/PTT)."""
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
        srv.server_close()
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


# ── /rig/voice (voix dynamique TTS) ─────────────────────────────────────────

def test_rig_voice_bloque_si_non_arme(server, monkeypatch):
    appels = []
    monkeypatch.setattr(vk, 'send_voice_message',
                        lambda *a, **k: appels.append(a) or {'ok': True})
    status, d = _post(server, '/rig/voice', {
        'template': 'CQ', 'call': 'F8TEST', 'mycall': 'F1TEST', 'mode': 'USB'})
    assert status == 403
    assert d.get('blocked') is True
    assert appels == []          # aucune émission réelle déclenchée


def test_rig_voice_bloque_si_mode_cw(server, monkeypatch):
    appels = []
    monkeypatch.setattr(vk, 'send_voice_message',
                        lambda *a, **k: appels.append(a) or {'ok': True})
    status, d = _post(server, '/rig/voice', {
        'template': 'CQ', 'call': 'F8TEST', 'mycall': 'F1TEST',
        'armed': True, 'mode': 'CW'})
    assert status == 403 and d.get('blocked') is True
    assert appels == []


def test_rig_voice_arme_et_ssb_passe(server, monkeypatch):
    appels = []
    monkeypatch.setattr(vk, 'send_voice_message',
                        lambda *a, **k: appels.append(a) or {'ok': True})
    status, d = _post(server, '/rig/voice', {
        'template': 'CQ', 'call': 'F8TEST', 'mycall': 'F1TEST',
        'armed': True, 'mode': 'USB'})
    assert status == 200 and d.get('ok') is True
    assert len(appels) == 1


def test_rig_voice_skip_ptt_exempt_du_garde_fou(server, monkeypatch):
    # Bouton « Tester » de CONFIG (indicatif fictif, aucune émission réelle) :
    # jamais soumis au garde-fou, même désarmé.
    monkeypatch.setattr(vk, 'send_voice_message', lambda *a, **k: {'ok': True})
    status, d = _post(server, '/rig/voice', {
        'template': 'CQ', 'call': 'F8TEST', 'mycall': 'F1TEST', 'skip_ptt': True})
    assert status == 200 and d.get('ok') is True


# ── /voice/play (DVK, message WAV enregistré) ───────────────────────────────

def test_voice_play_bloque_si_non_arme(server, monkeypatch):
    appels = []
    monkeypatch.setattr(vk, 'envoyer_message',
                        lambda *a, **k: appels.append(a) or {'ok': True})
    status, d = _post(server, '/voice/play', {'slot': 'V1', 'mode': 'USB'})
    assert status == 403 and d.get('blocked') is True
    assert appels == []


def test_voice_play_arme_et_ssb_passe(server, monkeypatch):
    appels = []
    monkeypatch.setattr(vk, 'envoyer_message',
                        lambda *a, **k: appels.append(a) or {'ok': True})
    status, d = _post(server, '/voice/play', {'slot': 'V1', 'armed': True, 'mode': 'USB'})
    assert status == 200 and d.get('ok') is True
    assert len(appels) == 1
