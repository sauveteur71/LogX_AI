# -*- coding: utf-8 -*-
"""Tests du module Icom remote-internet (logx_icomremote) — protocole de
pairing NON confirmé (voir docstring du module), donc le module refuse
proprement PARTOUT sans jamais toucher le réseau. Ces tests vérifient
justement ça : aucun socket n'est ouvert, quel que soit cfg."""
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_icomremote as icomremote


class _SocketGuard:
    """Fait échouer le test si le module tente d'ouvrir un socket — la
    garantie centrale de ce module (aucune E/S réseau tant que le protocole
    de pairing n'est pas confirmé)."""

    def __call__(self, *args, **kwargs):
        raise AssertionError('logx_icomremote a tenté d\'ouvrir un socket réseau '
                              '— interdit tant que le protocole n\'est pas confirmé')


def _guard_sockets(monkeypatch):
    monkeypatch.setattr(socket, 'socket', _SocketGuard())
    monkeypatch.setattr(socket, 'create_connection', _SocketGuard())


# ─── icomremote_settings() : fonction pure ──────────────────────────────────

def test_settings_defaults_sur_cfg_vide():
    s = icomremote.icomremote_settings({})
    assert s['enabled'] is False
    assert s['host'] == icomremote.DEFAULT_HOST
    assert s['control_port'] == icomremote.DEFAULT_CONTROL_PORT
    assert s['civ_port'] == icomremote.DEFAULT_CIV_PORT
    assert s['civ_addr'] is None
    assert s['username'] == ''
    assert s['password'] == ''


def test_settings_defaults_sur_cfg_none():
    s = icomremote.icomremote_settings(None)
    assert s['enabled'] is False
    assert s['civ_addr'] is None


def test_settings_lit_les_champs_configures():
    cfg = {
        'icomremote_enabled': True,
        'icomremote_host': ' 192.168.1.50 ',
        'icomremote_control_port': '50001',
        'icomremote_civ_port': '50002',
        'icomremote_civ_addr': '0xA4',
        'icomremote_username': ' F4GLD ',
        'icomremote_password': 'secret',
    }
    s = icomremote.icomremote_settings(cfg)
    assert s['enabled'] is True
    assert s['host'] == '192.168.1.50'
    assert s['control_port'] == 50001
    assert s['civ_port'] == 50002
    assert s['civ_addr'] == 0xA4
    assert s['username'] == 'F4GLD'
    assert s['password'] == 'secret'


def test_settings_port_invalide_retombe_sur_defaut():
    s = icomremote.icomremote_settings({'icomremote_control_port': 'pas-un-port',
                                         'icomremote_civ_port': None})
    assert s['control_port'] == icomremote.DEFAULT_CONTROL_PORT
    assert s['civ_port'] == icomremote.DEFAULT_CIV_PORT


def test_settings_ne_leve_jamais_sur_entree_farfelue():
    # Robustesse : aucune exception, quelle que soit la forme de cfg.
    icomremote.icomremote_settings({'icomremote_civ_addr': object()})
    icomremote.icomremote_settings({'icomremote_civ_addr': ''})
    icomremote.icomremote_settings({'icomremote_civ_addr': 164})


def test_parse_civ_addr_formes_acceptees():
    assert icomremote._parse_civ_addr(None) is None
    assert icomremote._parse_civ_addr('') is None
    assert icomremote._parse_civ_addr(164) == 164
    assert icomremote._parse_civ_addr('164') == 164
    assert icomremote._parse_civ_addr('0xA4') == 0xA4
    assert icomremote._parse_civ_addr('A4') == 0xA4
    assert icomremote._parse_civ_addr('pas-hex') is None


# ─── get_state()/set_freq()/set_ptt()/test_connection() : refus honnête ────

def test_get_state_refuse_sans_toucher_le_reseau(monkeypatch):
    _guard_sockets(monkeypatch)
    r = icomremote.get_state({'icomremote_enabled': True, 'icomremote_host': '192.168.1.50'})
    assert r['ok'] is False
    assert 'non implémenté' in r['error']


def test_get_state_refuse_meme_cfg_vide(monkeypatch):
    _guard_sockets(monkeypatch)
    r = icomremote.get_state({})
    assert r['ok'] is False
    assert r['enabled'] is False


def test_set_freq_refuse_sans_toucher_le_reseau(monkeypatch):
    _guard_sockets(monkeypatch)
    r = icomremote.set_freq({'icomremote_enabled': True}, 14074000, mode='USB')
    assert r['ok'] is False
    assert 'non implémenté' in r['error']


def test_set_ptt_refuse_sans_toucher_le_reseau(monkeypatch):
    _guard_sockets(monkeypatch)
    for on in (True, False):
        r = icomremote.set_ptt({'icomremote_enabled': True}, on)
        assert r['ok'] is False
        assert 'non implémenté' in r['error']


def test_test_connection_refuse_sans_toucher_le_reseau(monkeypatch):
    _guard_sockets(monkeypatch)
    r = icomremote.test_connection('192.168.1.50', 50001)
    assert r['ok'] is False
    assert 'non implémenté' in r['error']


def test_test_connection_refuse_meme_sans_argument(monkeypatch):
    _guard_sockets(monkeypatch)
    r = icomremote.test_connection(None)
    assert r['ok'] is False
