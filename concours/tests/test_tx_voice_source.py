# -*- coding: utf-8 -*-
"""Choix de la source voix pour l'émission phonie (F4GLD 25/08) : WAV
pré-enregistré OU TTS, « selon ce que je dispose comme accès internet et IA ».

Principe LogX AI (offline-first) : le programme DOIT marcher sans aucun accès ;
si internet et/ou compte IA sont là, il peut s'en servir. La cascade
IA→Piper→voix locale est DÉJÀ dans logx_voicekeyer.synthesize_to_wav ; ici on ne
gère que le CHOIX de source, avec repli hors-ligne si aucun moteur TTS n'existe.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_tx_consent as txc   # noqa: E402


def test_wav_reste_wav_meme_si_tts_dispo():
    # 'wav' = l'opérateur veut SA voix enregistrée : jamais remplacée par du TTS.
    assert txc.voice_source_effectif('wav', tts_dispo=True) == 'wav'
    assert txc.voice_source_effectif('wav', tts_dispo=False) == 'wav'


def test_tts_utilise_si_dispo_sinon_repli_wav():
    assert txc.voice_source_effectif('tts', tts_dispo=True) == 'tts'
    # aucun moteur TTS (ni IA, ni Piper, ni voix locale) -> repli hors-ligne WAV
    assert txc.voice_source_effectif('tts', tts_dispo=False) == 'wav'


def test_auto_prefere_tts_si_dispo():
    assert txc.voice_source_effectif('auto', tts_dispo=True) == 'tts'
    assert txc.voice_source_effectif('auto', tts_dispo=False) == 'wav'


def test_defaut_est_auto():
    # source absente/vide -> comportement 'auto'
    assert txc.voice_source_effectif('', tts_dispo=True) == 'tts'
    assert txc.voice_source_effectif(None, tts_dispo=False) == 'wav'


def test_consent_porte_la_source_voix():
    c = txc.create_tx_consent('F4GLD', 'rig1', 14074000, 'USB', 50, 'CQ',
                              voice_source='tts')
    assert c.voice_source == 'tts'
    # défaut = 'auto'
    c2 = txc.create_tx_consent('F4GLD', 'rig1', 14074000, 'USB', 50, 'CQ')
    assert c2.voice_source == 'auto'
