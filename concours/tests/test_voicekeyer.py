# -*- coding: utf-8 -*-
"""Tests du keyer vocal dynamique (radiocontest_voicekeyer) : épellation
phonétique, expansion de macros, orchestration PTT+lecture. Jamais de vrai
TTS/audio/CAT dans ces tests — tout est mocké, seule la logique est testée."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import radiocontest_voicekeyer as vk


# ─── Épellation phonétique ────────────────────────────────────────────────────

def test_spell_callsign_simple():
    assert vk.spell_callsign('F4GLD') == 'Foxtrot Four Golf Lima Delta'


def test_spell_callsign_minuscules():
    assert vk.spell_callsign('f4gld') == 'Foxtrot Four Golf Lima Delta'


def test_spell_callsign_suffixe_connu():
    assert vk.spell_callsign('F4GLD/P') == 'Foxtrot Four Golf Lima Delta portable'
    assert vk.spell_callsign('F4GLD/QRP') == 'Foxtrot Four Golf Lima Delta Q R P'


def test_spell_callsign_suffixe_inconnu_epele():
    assert vk.spell_callsign('F4GLD/5') == 'Foxtrot Four Golf Lima Delta Five'


def test_spell_callsign_vide():
    assert vk.spell_callsign('') == ''
    assert vk.spell_callsign(None) == ''


def test_spell_digits_report():
    assert vk.spell_digits('59') == 'Five Nine'
    assert vk.spell_digits('599') == 'Five Nine Nine'


def test_spell_digits_serie_avec_zero():
    assert vk.spell_digits('042') == 'Zero Four Two'


def test_spell_digits_vide():
    assert vk.spell_digits('') == ''
    assert vk.spell_digits(None) == ''


# ─── Expansion des macros vocales ────────────────────────────────────────────

def test_expand_voice_text_call_et_mycall():
    ctx = {'call': 'DL1AA', 'mycall': 'F4GLD'}
    out = vk.expand_voice_text('{CALL} de {MYCALL}', ctx)
    assert out == 'Delta Lima One Alpha Alpha de Foxtrot Four Golf Lima Delta'


def test_expand_voice_text_report_et_serie():
    ctx = {'rst_sent': '59', 'nr': '001'}
    out = vk.expand_voice_text('{RST_SENT} {NR}', ctx)
    assert out == 'Five Nine Zero Zero One'


def test_expand_voice_text_placeholders_manquants_deviennent_vides():
    out = vk.expand_voice_text('CQ {MYCALL}', {})
    assert out == 'CQ '


def test_voice_macros_default_ont_les_champs_attendus():
    for m in vk.VOICE_MACROS_DEFAULT:
        assert {'key', 'label', 'text'} <= set(m)


# ─── Réglages ─────────────────────────────────────────────────────────────────

def test_voicekeyer_settings_defaut():
    s = vk.voicekeyer_settings({})
    assert s['enabled'] is False and s['rate'] == 175 and s['device'] == ''


def test_voicekeyer_settings_personnalises():
    s = vk.voicekeyer_settings({'voicekeyer_enabled': True, 'voicekeyer_device': '3',
                                 'voicekeyer_voice_id': 'xyz', 'voicekeyer_rate': '150'})
    assert s == {'enabled': True, 'device': '3', 'voice_id': 'xyz', 'rate': 150}


def test_voicekeyer_settings_rate_invalide_retombe_sur_defaut():
    assert vk.voicekeyer_settings({'voicekeyer_rate': 'abc'})['rate'] == 175


# ─── Listes (jamais d'exception si moteur/peripherique indisponible) ────────

def test_list_output_devices_ne_plante_pas():
    assert isinstance(vk.list_output_devices(), list)


def test_list_tts_voices_ne_plante_pas():
    assert isinstance(vk.list_tts_voices(), list)


# ─── Orchestration send_voice_message (PTT + synthèse + lecture, tout mocké) ──

def test_send_voice_message_desactive():
    r = vk.send_voice_message({}, 'CQ test')
    assert not r['ok'] and 'désactivé' in r['error'].lower()


def test_send_voice_message_texte_vide():
    r = vk.send_voice_message({'voicekeyer_enabled': True}, '  ')
    assert not r['ok'] and 'vide' in r['error'].lower()


def test_send_voice_message_synthese_indisponible(monkeypatch):
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: None)
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test')
    assert not r['ok'] and 'synthèse' in r['error'].lower()


def test_send_voice_message_ptt_refuse(monkeypatch, tmp_path):
    fake_wav = tmp_path / 'x.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: {'ok': False, 'error': 'radio injoignable'})
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test')
    assert not r['ok'] and 'PTT refusé' in r['error']
    assert not fake_wav.exists()   # le WAV temporaire est nettoyé même en échec


def test_send_voice_message_chemin_complet(monkeypatch, tmp_path):
    fake_wav = tmp_path / 'y.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    ptt_calls = []
    played = []
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: ptt_calls.append(on) or {'ok': True})
    monkeypatch.setattr(vk, 'play_wav', lambda path, device=None: played.append(path))
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test')
    assert r['ok'] and r['text'] == 'CQ test'
    assert ptt_calls == [True, False]     # PTT activé puis relâché, dans cet ordre
    assert played == [str(fake_wav)]
    assert not fake_wav.exists()           # nettoyage du WAV temporaire


def test_send_voice_message_erreur_lecture_relache_quand_meme_le_ptt(monkeypatch, tmp_path):
    fake_wav = tmp_path / 'z.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    ptt_calls = []
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: ptt_calls.append(on) or {'ok': True})
    def boom(path, device=None):
        raise RuntimeError('périphérique audio indisponible')
    monkeypatch.setattr(vk, 'play_wav', boom)
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test')
    assert not r['ok'] and 'Lecture audio' in r['error']
    assert ptt_calls == [True, False]      # le PTT est bien relâché même après l'erreur


# ─── Dispatch PTT selon le mode CAT actif ─────────────────────────────────────

def test_set_ptt_dispatch_natif(monkeypatch):
    import radiocontest_cat as cat
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'native'})
    monkeypatch.setattr(cat, 'set_ptt', lambda cfg, on: {'ok': True, 'via': 'native', 'on': on})
    r = vk._set_ptt({}, True)
    assert r == {'ok': True, 'via': 'native', 'on': True}


def test_set_ptt_dispatch_tci(monkeypatch):
    import radiocontest_cat as cat
    import radiocontest_tci as tci
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'tci'})
    monkeypatch.setattr(tci, 'set_ptt', lambda cfg, on: {'ok': True, 'via': 'tci', 'on': on})
    r = vk._set_ptt({}, False)
    assert r == {'ok': True, 'via': 'tci', 'on': False}


def test_set_ptt_dispatch_rigctld(monkeypatch):
    import radiocontest_cat as cat
    import radiocontest_rig as rig
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': False, 'mode': 'native'})
    monkeypatch.setattr(rig, 'rig_settings', lambda cfg: {'enabled': True, 'host': 'h', 'port': 1})
    monkeypatch.setattr(rig, 'set_ptt', lambda host, port, on: {'ok': True, 'via': 'rigctld', 'host': host})
    r = vk._set_ptt({}, True)
    assert r == {'ok': True, 'via': 'rigctld', 'host': 'h'}


def test_set_ptt_dispatch_rien_active(monkeypatch):
    import radiocontest_cat as cat
    import radiocontest_rig as rig
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': False, 'mode': 'native'})
    monkeypatch.setattr(rig, 'rig_settings', lambda cfg: {'enabled': False, 'host': '', 'port': 0})
    r = vk._set_ptt({}, True)
    assert not r['ok'] and 'désactivé' in r['error'].lower()
