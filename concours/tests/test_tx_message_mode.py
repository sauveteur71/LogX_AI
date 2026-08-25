# -*- coding: utf-8 -*-
"""« Message par mode » : /tx/authorize envoie le CONTENU préparé (pas juste le
PTT). Dispatch par famille — CW -> keyer CW (texte), phonie -> voice keyer (slot
WAV). Les émetteurs réels (wk.envoyer / vk.envoyer_message) gèrent eux-mêmes le
PTT. On teste le DISPATCH pur (quel émetteur, avec quel message) — jamais le
matériel. Les modes data (FT8/RTTY) sont refusés en amont par le garde-fou et
n'atteignent jamais ce dispatch."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_tx_consent as txc   # noqa: E402


def _spies():
    calls = {}
    def cw(msg):
        calls['cw'] = msg
        return {'ok': True, 'backend': 'winkeyer'}
    def voice(msg):
        calls['voice'] = msg
        return {'ok': True, 'backend': 'voix'}
    return calls, cw, voice


def test_cw_envoie_le_texte_au_keyer_cw():
    calls, cw, voice = _spies()
    res = txc.emettre_message('cw', 'CQ TEST DE F4GLD', cw, voice)
    assert calls == {'cw': 'CQ TEST DE F4GLD'}      # seul le keyer CW appelé
    assert res['ok'] and res['backend'] == 'winkeyer'


def test_phonie_joue_le_slot_au_voice_keyer():
    calls, cw, voice = _spies()
    res = txc.emettre_message('phonie', 'cq_1', cw, voice)
    assert calls == {'voice': 'cq_1'}              # seul le voice keyer appelé
    assert res['ok'] and res['backend'] == 'voix'


def test_famille_inconnue_refuse_sans_rien_emettre():
    calls, cw, voice = _spies()
    res = txc.emettre_message(None, 'peu importe', cw, voice)
    assert res['ok'] is False
    assert calls == {}                             # AUCUN émetteur appelé (fail-closed)


def test_message_vide_refuse_sans_emettre():
    # une émission « unique » sans contenu n'a pas de sens : on refuse plutôt
    # que d'émettre un message vide.
    calls, cw, voice = _spies()
    res = txc.emettre_message('cw', '', cw, voice)
    assert res['ok'] is False
    assert calls == {}
