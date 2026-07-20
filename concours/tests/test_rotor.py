# -*- coding: utf-8 -*-
"""Tests du pilotage rotor (logx_rotor) contre un FAUX rotctld."""
import os
import socket
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_rotor as rotor


class FakeRotctld:
    """Simule rotctld : p lit az/el, P règle, S stoppe."""

    def __init__(self):
        self.az = 90.0
        self.el = 0.0
        self.stopped = False
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
                    data = conn.recv(256).decode()
                except OSError:
                    continue
                for line in data.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if line == 'p':
                        conn.sendall(f'{self.az}\n{self.el}\n'.encode())
                    elif line.startswith('P '):
                        _, a, e = line.split()
                        self.az, self.el = float(a), float(e)
                        conn.sendall(b'RPRT 0\n')
                    elif line == 'S':
                        self.stopped = True
                        conn.sendall(b'RPRT 0\n')
                    else:
                        conn.sendall(b'RPRT -1\n')

    def close(self):
        self._stop = True
        self.srv.close()


def test_get_position():
    fake = FakeRotctld()
    try:
        p = rotor.get_position('127.0.0.1', fake.port)
        assert p['ok'] and p['azimuth'] == 90.0 and p['elevation'] == 0.0
    finally:
        fake.close()


def test_point_antenna():
    fake = FakeRotctld()
    try:
        r = rotor.set_position('127.0.0.1', fake.port, 235)
        assert r['ok'] and r['azimuth'] == 235.0
        assert fake.az == 235.0
    finally:
        fake.close()


def test_azimut_borne():
    """Azimut hors plage ramené dans [0,360] avant l'envoi."""
    fake = FakeRotctld()
    try:
        rotor.set_position('127.0.0.1', fake.port, 400)
        assert fake.az == 360.0
        rotor.set_position('127.0.0.1', fake.port, -10)
        assert fake.az == 0.0
    finally:
        fake.close()


def test_stop():
    fake = FakeRotctld()
    try:
        assert rotor.stop('127.0.0.1', fake.port)['ok']
        # laisse le thread traiter
        import time
        time.sleep(0.05)
        assert fake.stopped
    finally:
        fake.close()


def test_rotor_injoignable_erreur_propre():
    r = rotor.get_position('127.0.0.1', 1)
    assert not r['ok'] and 'injoignable' in r['error']


def test_settings_desactive_par_defaut():
    assert rotor.rotor_settings({})['enabled'] is False
    s = rotor.rotor_settings({'rotor_enabled': True, 'rotor_host': '192.168.1.60',
                              'rotor_port': '4533'})
    assert s == {'enabled': True, 'host': '192.168.1.60', 'port': 4533}
