# -*- coding: utf-8 -*-
"""Tests du pilotage CAT (radiocontest_rig) contre un FAUX rigctld :
un petit serveur TCP qui parle le protocole Hamlib, sans radio."""
import os
import socket
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import radiocontest_rig as rig


class FakeRigctld:
    """Simule rigctld : F/M règlent, f/m lisent, b enregistre le CW envoyé."""

    def __init__(self):
        self.freq = 14032000
        self.mode = 'CW'
        self.morse_sent = []
        self.srv = socket.socket()
        self.srv.bind(('127.0.0.1', 0))
        self.port = self.srv.getsockname()[1]
        self.srv.listen(4)
        self._stop = False
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self.srv.accept()
            except OSError:
                return
            with conn:
                try:
                    data = conn.recv(512).decode()
                except OSError:
                    continue
                for line in data.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if line == 'f':
                        conn.sendall(f'{self.freq}\n'.encode())
                    elif line == 'm':
                        conn.sendall(f'{self.mode}\n500\n'.encode())
                    elif line.startswith('F '):
                        self.freq = int(line.split()[1])
                        conn.sendall(b'RPRT 0\n')
                    elif line.startswith('M '):
                        self.mode = line.split()[1]
                        conn.sendall(b'RPRT 0\n')
                    elif line.startswith('b '):
                        self.morse_sent.append(line[2:])
                        conn.sendall(b'RPRT 0\n')
                    elif line.startswith('\\stop_morse'):
                        conn.sendall(b'RPRT 0\n')
                    else:
                        conn.sendall(b'RPRT -1\n')

    def close(self):
        self._stop = True
        self.srv.close()


def test_get_state():
    fake = FakeRigctld()
    try:
        st = rig.get_state('127.0.0.1', fake.port)
        assert st['ok'] and st['freq_hz'] == 14032000
        assert st['freq_khz'] == 14032.0 and st['mode'] == 'CW'
    finally:
        fake.close()


def test_qsy_avec_mode():
    fake = FakeRigctld()
    try:
        r = rig.set_freq('127.0.0.1', fake.port, 3512000, mode='LSB')
        assert r['ok']
        assert fake.freq == 3512000 and fake.mode == 'LSB'
    finally:
        fake.close()


def test_send_morse():
    fake = FakeRigctld()
    try:
        r = rig.send_morse('127.0.0.1', fake.port, 'TU 5NN F6KQJ')
        assert r['ok']
        assert fake.morse_sent == ['TU 5NN F6KQJ']
    finally:
        fake.close()


def test_radio_injoignable_erreur_propre():
    r = rig.get_state('127.0.0.1', 1)      # port fermé
    assert not r['ok'] and 'injoignable' in r['error']
    r = rig.set_freq('127.0.0.1', 1, 14000000)
    assert not r['ok']


def test_settings_par_defaut_desactive():
    s = rig.rig_settings({})
    assert s['enabled'] is False           # jamais actif sans opt-in explicite
    s2 = rig.rig_settings({'rig_enabled': True, 'rig_host': '192.168.1.50',
                           'rig_port': '4532'})
    assert s2 == {'enabled': True, 'host': '192.168.1.50', 'port': 4532}
