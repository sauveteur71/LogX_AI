# -*- coding: utf-8 -*-
"""Tests du pilotage CAT via flrig (logx_flrig) contre un FAUX serveur
XML-RPC : mêmes principes que test_rig.py (faux rigctld) et test_tci.py
(faux serveur TCI), un vrai serveur réseau local plutôt qu'un mock, pour
valider le client XML-RPC réel (xmlrpc.client) de bout en bout."""
import os
import sys
import threading
import xmlrpc.server

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_flrig as flrig


class FakeFlrig:
    """Simule le serveur XML-RPC de flrig : juste les méthodes rig.* dont
    logx_flrig a besoin (voir la doc en tête de logx_flrig.py pour la
    provenance de ces noms)."""

    def __init__(self):
        self.freq = 14195000.0
        self.mode = 'USB'
        self.ptt = 0
        self.srv = xmlrpc.server.SimpleXMLRPCServer(
            ('127.0.0.1', 0), logRequests=False, allow_none=True)
        self.port = self.srv.server_address[1]
        self.srv.register_function(lambda: str(int(self.freq)), 'rig.get_vfo')
        self.srv.register_function(self._set_frequency, 'rig.set_frequency')
        self.srv.register_function(lambda: self.mode, 'rig.get_mode')
        self.srv.register_function(self._set_mode, 'rig.set_mode')
        self.srv.register_function(lambda: self.ptt, 'rig.get_ptt')
        self.srv.register_function(self._set_ptt, 'rig.set_ptt')
        self._thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self._thread.start()

    def _set_frequency(self, freq_hz):
        self.freq = freq_hz
        return 1

    def _set_mode(self, mode):
        self.mode = mode
        return 1

    def _set_ptt(self, on):
        self.ptt = on
        return 1

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


def test_get_state():
    fake = FakeFlrig()
    try:
        st = flrig.get_state('127.0.0.1', fake.port)
        assert st['ok'] and st['freq_hz'] == 14195000
        assert st['freq_khz'] == 14195.0 and st['mode'] == 'USB'
    finally:
        fake.close()


def test_qsy_avec_mode():
    fake = FakeFlrig()
    try:
        r = flrig.set_freq('127.0.0.1', fake.port, 3512000, mode='CW')
        assert r['ok']
        assert fake.freq == 3512000 and fake.mode == 'CW'
    finally:
        fake.close()


def test_qsy_sans_mode_ne_touche_pas_au_mode():
    fake = FakeFlrig()
    try:
        r = flrig.set_freq('127.0.0.1', fake.port, 7100000)
        assert r['ok']
        assert fake.freq == 7100000 and fake.mode == 'USB'   # inchangé
    finally:
        fake.close()


def test_set_ptt():
    fake = FakeFlrig()
    try:
        r_on = flrig.set_ptt('127.0.0.1', fake.port, True)
        assert r_on['ok'] and fake.ptt == 1
        r_off = flrig.set_ptt('127.0.0.1', fake.port, False)
        assert r_off['ok'] and fake.ptt == 0
    finally:
        fake.close()


def test_test_connection_reussie():
    fake = FakeFlrig()
    try:
        res = flrig.test_connection('127.0.0.1', fake.port)
        assert res['ok'] and res['freq_hz'] == 14195000 and res['mode'] == 'USB'
    finally:
        fake.close()


def test_radio_injoignable_erreur_propre():
    r = flrig.get_state('127.0.0.1', 1)      # port fermé
    assert not r['ok'] and 'injoignable' in r['error']
    r = flrig.set_freq('127.0.0.1', 1, 14000000)
    assert not r['ok']
    r = flrig.set_ptt('127.0.0.1', 1, True)
    assert not r['ok']


def test_test_connection_echoue_proprement():
    res = flrig.test_connection('127.0.0.1', 1)
    assert not res['ok'] and 'error' in res


def test_settings_par_defaut():
    s = flrig.flrig_settings({})
    assert s == {'host': flrig.DEFAULT_HOST, 'port': flrig.DEFAULT_PORT}


def test_settings_personnalises():
    s = flrig.flrig_settings({'flrig_host': '192.168.1.60', 'flrig_port': '12000'})
    assert s == {'host': '192.168.1.60', 'port': 12000}


def test_settings_port_invalide_retombe_sur_defaut():
    s = flrig.flrig_settings({'flrig_port': 'abc'})
    assert s['port'] == flrig.DEFAULT_PORT
