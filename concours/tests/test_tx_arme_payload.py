# -*- coding: utf-8 -*-
"""Interrupteur maître unifié côté client — `txArmePayload()`.

La voix (DVK WAV et voix dynamique) doit envoyer au serveur les mêmes champs de
sécurité que le CW — `armed` (interrupteur maître `cwTxArme`), `mode` (VFO TX) et
`freq_khz` — pour passer le garde-fou TX unifié. `txArmePayload()` centralise ces
trois champs (une seule source, pas de copie divergente entre CW et voix).

Vrai code extrait de logx_hardware_cat.js, exécuté en V8 (py_mini_racer)."""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer', reason='py_mini_racer absent')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_hardware_cat.js'), encoding='utf-8').read()


def _extract_function(src, name):
    m = re.search(r'^function %s\(' % re.escape(name), src, re.M)
    assert m, name
    depth = 0
    i = src.index('{', m.start())
    while True:
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[m.start():i + 1]
        i += 1


def _ctx(armed, mode, freq_khz):
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    c.eval('var cwTxArme = %s;' % ('true' if armed else 'false'))
    c.eval('function cwCurrentMode(){ return %s; }' % json.dumps(mode))
    c.eval('var rigState = {freq_khz: %s};' % json.dumps(freq_khz))
    c.eval(_extract_function(JS, 'txArmePayload'))
    return c


def test_payload_reflete_arme_mode_freq():
    c = _ctx(True, 'USB', 14200)
    p = json.loads(c.eval('JSON.stringify(txArmePayload())'))
    assert p['armed'] is True
    assert p['mode'] == 'USB'
    assert p['freq_khz'] == 14200


def test_payload_desarme():
    c = _ctx(False, 'USB', 14200)
    p = json.loads(c.eval('JSON.stringify(txArmePayload())'))
    assert p['armed'] is False


def test_payload_mode_cw_transmis_tel_quel():
    # Le helper ne juge pas le mode (c'est le rôle du garde-fou serveur) : il le
    # transmet fidèlement pour que le serveur puisse refuser une voix en CW.
    c = _ctx(True, 'CW', 7010)
    p = json.loads(c.eval('JSON.stringify(txArmePayload())'))
    assert p['mode'] == 'CW'


def test_voice_play_envoie_le_payload_arme():
    # Structurel : voicePlay() (logx_voice_keyer.js) doit inclure txArmePayload()
    # dans le corps POST /voice/play, sinon la voix est bloquée (403) par le
    # garde-fou serveur faute de champ `armed`.
    vk_js = open(os.path.join(BASE, 'logx_voice_keyer.js'), encoding='utf-8').read()
    i = vk_js.index('/voice/play')
    fenetre = vk_js[i:i + 300]
    assert 'txArmePayload()' in fenetre, "voicePlay n'envoie pas l'état d'armement"
