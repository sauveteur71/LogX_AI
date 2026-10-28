# -*- coding: utf-8 -*-
"""Band Map détachée : suit la bande de la radio (F4GLD 24/10/2026).

Défaut : ouverte depuis le menu DISPOSITION (sans ?band), logx_panel.html
retombait sur '144' codé en dur -> « Aucun spot sur 144 MHz » en plein
CQ WW SSB sur 7 MHz. Vérifié en navigateur (radio simulée) : menu -> « 7 MHz ·
suit la radio » ; QSY radio 14195 kHz -> la fenêtre passe sur 14 MHz ; une
band map ouverte exprès sur ?band=14 reste fixe."""
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
PANEL = open(os.path.join(BASE, 'logx_panel.html'), encoding='utf-8').read()
SB = open(os.path.join(BASE, 'logx_statusbar.js'), encoding='utf-8').read()


def _code(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'(?m)^\s*//.*$', '', s)


def test_plus_de_144_code_en_dur():
    corps = _code(PANEL)
    tick = corps[corps.index('async function tickBandMap'):]
    tick = tick[:tick.index('// ─── WORKED MATRIX') if '// ─── WORKED MATRIX' in tick else 2000]
    assert "'144'" not in tick and '"144"' not in tick


def test_suit_la_radio_via_hardware_state():
    corps = _code(PANEL)
    f = corps[corps.index('async function _bandeBandMap'):corps.index('async function tickBandMap')]
    assert "fetch('/hardware/state')" in f and 'rig.band' in f
    assert "params.get('suivre') !== '1'" in f      # ?band seul = band map FIXE


def test_ouverture_depuis_le_menu_demande_le_suivi():
    corps = _code(SB)
    f = corps[corps.index('function openPanel'):corps.index('function closePanel')]
    assert re.search(r"else if \(id === 'bandmap'\)\s*\{[^}]*suivre=1", f, re.S)
    assert 'currentBand' in f


def test_serveur_publie_la_bande_de_la_radio(monkeypatch):
    import logx_http
    monkeypatch.setattr(logx_http, '_rig_state_dict_impl',
                        lambda cfg: {'ok': True, 'enabled': True, 'freq_hz': 7061500,
                                     'freq_khz': 7061.5, 'mode': 'LSB'})
    st = logx_http._rig_state_dict({})
    assert st['band'] == '7'
    monkeypatch.setattr(logx_http, '_rig_state_dict_impl',
                        lambda cfg: {'ok': True, 'enabled': True, 'freq_hz': 14195000,
                                     'freq_khz': 14195.0})
    assert logx_http._rig_state_dict({})['band'] == '14'
    monkeypatch.setattr(logx_http, '_rig_state_dict_impl',
                        lambda cfg: {'ok': False, 'enabled': True, 'error': 'muette'})
    assert 'band' not in logx_http._rig_state_dict({})
