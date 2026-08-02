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
    assert s == {'enabled': True, 'host': '192.168.1.60', 'port': 4533,
                 'proto': 'rotctld', 'brand': '', 'model': ''}


def test_settings_gs232_marque_modele():
    s = rotor.rotor_settings({'rotor_enabled': True, 'rotor_host': '10.0.0.5',
                              'rotor_port': '4001', 'rotor_proto': 'gs232',
                              'rotor_brand': 'Yaesu', 'rotor_model': 'G-5500 (Az + El)'})
    assert s['proto'] == 'gs232' and s['brand'] == 'Yaesu'
    assert s['model'] == 'G-5500 (Az + El)'


# ─── Catalogue des marques ───────────────────────────────────────────────────

def test_catalogue_marques():
    marques = [b['brand'] for b in rotor.catalog()]
    for attendu in ('Yaesu', 'Hy-Gain', 'SPID', 'Pro.Sis.Tel', 'M2 Antenna Systems',
                    'Alfa Radio', 'Kenpro'):
        assert attendu in marques


def test_model_info():
    assert rotor.model_info('Yaesu', 'G-5500 (Az + El)') == {'proto': 'gs232', 'elevation': True}
    assert rotor.model_info('Yaesu', 'G-800DXA / G-1000DXC') == {'proto': 'gs232', 'elevation': False}
    assert rotor.model_info('SPID', 'ROT2PROG (Az + El)') == {'proto': 'rotctld', 'elevation': True}
    # Marque connue mais modèle inconnu : proto de la marque, sans élévation.
    assert rotor.model_info('Yaesu', 'modèle bidon') == {'proto': 'gs232', 'elevation': False}
    assert rotor.model_info('Inconnu', 'X') is None


def test_norm_proto():
    assert rotor._norm_proto('GS232') == 'gs232'
    assert rotor._norm_proto('rotctld') == 'rotctld'
    assert rotor._norm_proto('n_importe_quoi') == 'rotctld'
    assert rotor._norm_proto(None) == 'rotctld'


# ─── GS-232 natif (Yaesu/Kenpro/PstRotator) contre un FAUX boîtier ───────────

class FakeGS232:
    """Simule un boîtier GS-232 : C2 lit az/el, M/W règlent, S stoppe.
    `fmt` = 'A' ('+0aaa+0eee') ou 'B' ('AZ=aaa EL=eee') pour tester les deux."""

    def __init__(self, fmt='B'):
        self.az = 90
        self.el = 0
        self.fmt = fmt
        self.last = ''
        self.stopped = False
        self.srv = socket.socket()
        self.srv.bind(('127.0.0.1', 0))
        self.port = self.srv.getsockname()[1]
        self.srv.listen(4)
        self._stop = False
        threading.Thread(target=self._serve, daemon=True).start()

    def _reply_pos(self):
        if self.fmt == 'A':
            return ('+0%03d+0%03d\r' % (self.az, self.el)).encode()
        return ('AZ=%03d EL=%03d\r' % (self.az, self.el)).encode()

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self.srv.accept()
            except OSError:
                return
            with conn:
                try:
                    data = conn.recv(64).decode()
                except OSError:
                    continue
                cmd = data.strip()
                self.last = cmd
                if cmd.startswith('C'):
                    conn.sendall(self._reply_pos())
                elif cmd.startswith('M'):
                    self.az = int(cmd[1:4])
                elif cmd.startswith('W'):
                    parts = cmd[1:].split()
                    self.az, self.el = int(parts[0]), int(parts[1])
                elif cmd == 'S':
                    self.stopped = True

    def close(self):
        self._stop = True
        self.srv.close()


def test_gs232_get_format_B():
    fake = FakeGS232('B')
    try:
        p = rotor.get_position('127.0.0.1', fake.port, 'gs232')
        assert p['ok'] and p['azimuth'] == 90.0 and p['elevation'] == 0.0
    finally:
        fake.close()


def test_gs232_get_format_A():
    fake = FakeGS232('A')
    fake.az, fake.el = 123, 45
    try:
        p = rotor.get_position('127.0.0.1', fake.port, 'gs232')
        assert p['ok'] and p['azimuth'] == 123.0 and p['elevation'] == 45.0
    finally:
        fake.close()


def test_gs232_point_azimut_seul():
    fake = FakeGS232('B')
    try:
        r = rotor.set_position('127.0.0.1', fake.port, 235, 0, 'gs232')
        assert r['ok']
        import time
        time.sleep(0.05)
        assert fake.last.startswith('M235')
        assert fake.az == 235
    finally:
        fake.close()


def test_gs232_point_avec_elevation():
    """Élévation demandée -> commande W (azimut + élévation)."""
    fake = FakeGS232('B')
    try:
        rotor.set_position('127.0.0.1', fake.port, 120, 30, 'gs232')
        import time
        time.sleep(0.05)
        assert fake.last.startswith('W120 030')
        assert fake.az == 120 and fake.el == 30
    finally:
        fake.close()


def test_gs232_stop():
    fake = FakeGS232('B')
    try:
        assert rotor.stop('127.0.0.1', fake.port, 'gs232')['ok']
        import time
        time.sleep(0.05)
        assert fake.stopped
    finally:
        fake.close()


def test_gs232_injoignable_erreur_propre():
    r = rotor.get_position('127.0.0.1', 1, 'gs232')
    assert not r['ok'] and 'injoignable' in r['error'] and 'GS-232' in r['error']
