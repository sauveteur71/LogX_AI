# -*- coding: utf-8 -*-
"""Tests du pilotage PowerGenius XL (logx_powergenius) — parsing pur +
faux serveur TCP local (jamais de vrai matériel/réseau)."""
import os
import socket
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_powergenius as pgxl


# ═══════════════════════════════════════════════════════════════════════════
#  Fonctions pures
# ═══════════════════════════════════════════════════════════════════════════

def test_build_command():
    assert pgxl.pgxl_build_command(3, 'status') == b'C3|status\r'


def test_parse_response_ok():
    r = pgxl.pgxl_parse_response('R3|0|state=STANDBY fwd=45.2')
    assert r == {'kind': 'R', 'seq': 3, 'ok': True, 'code': 0,
                 'message': 'state=STANDBY fwd=45.2'}


def test_parse_response_failure_code():
    r = pgxl.pgxl_parse_response('R7|1|erreur')
    assert r['kind'] == 'R' and r['ok'] is False and r['code'] == 1


def test_parse_response_hex_code():
    r = pgxl.pgxl_parse_response('R1|1a|panne')
    assert r['ok'] is False and r['code'] == 0x1a


def test_parse_response_async():
    r = pgxl.pgxl_parse_response('S0|state=REBOOT')
    assert r == {'kind': 'S', 'seq': 0, 'ok': True, 'code': None, 'message': 'state=REBOOT'}


def test_parse_response_illisible():
    assert pgxl.pgxl_parse_response('') is None
    assert pgxl.pgxl_parse_response('bruit_sans_pipe') is None
    assert pgxl.pgxl_parse_response('Xabc|0|msg') is None
    assert pgxl.pgxl_parse_response('Rabc|0|msg') is None   # seq non numérique
    assert pgxl.pgxl_parse_response('R1|zzz|msg') is None   # code non hexa


def test_parse_status_generique():
    d = pgxl.pgxl_parse_status('state=OPERATE fwd=45.20 rl=26.5 id=12.3 temp=38')
    assert d == {'state': 'OPERATE', 'fwd': '45.20', 'rl': '26.5',
                 'id': '12.3', 'temp': '38'}


def test_parse_status_tolere_bruit():
    # un token sans '=' est ignoré plutôt que de lever une exception
    assert pgxl.pgxl_parse_status('state=STANDBY blabla fwd=10') == \
        {'state': 'STANDBY', 'fwd': '10'}
    assert pgxl.pgxl_parse_status('') == {}
    assert pgxl.pgxl_parse_status(None) == {}


def test_rl_to_swr():
    # Return loss élevé -> ROS proche de 1 (bonne adaptation)
    assert pgxl.pgxl_rl_db_to_swr(26.5) is not None
    swr_bon = pgxl.pgxl_rl_db_to_swr(30.0)
    swr_moins_bon = pgxl.pgxl_rl_db_to_swr(10.0)
    assert 1.0 < swr_bon < swr_moins_bon
    assert pgxl.pgxl_rl_db_to_swr(None) is None
    assert pgxl.pgxl_rl_db_to_swr(0) is None
    assert pgxl.pgxl_rl_db_to_swr(-5) is None


def test_status_to_state_ne_fabrique_pas_power_w():
    out = pgxl._status_to_state(pgxl.pgxl_parse_status('state=OPERATE fwd=45.2 rl=26.5'))
    assert out['operate'] is True
    assert out['fwd_dbm'] == 45.2
    assert out['power_w'] is None       # jamais deviné
    assert out['swr'] is not None
    assert out['fault'] is None         # jamais fabriqué


def test_status_to_state_standby():
    out = pgxl._status_to_state(pgxl.pgxl_parse_status('state=STANDBY'))
    assert out['operate'] is False


def test_status_to_state_etat_inconnu():
    out = pgxl._status_to_state(pgxl.pgxl_parse_status('fwd=1.0'))
    assert out['operate'] is None       # ni OPERATE ni STANDBY reconnu -> incertain, pas fabriqué


# ═══════════════════════════════════════════════════════════════════════════
#  Faux serveur TCP PowerGenius (prologue + trames C/R/S)
# ═══════════════════════════════════════════════════════════════════════════

class FakePgxl:
    """Envoie le prologue à la connexion, répond 'status' avec un statut
    fabriqué, et NACK (code 1) pour toute autre commande (simule l'absence
    de commande OPERATE/STANDBY confirmée). Thread PAR connexion — le vrai
    PGXL accepte jusqu'à 10 connexions TCP concurrentes (doc officielle),
    et une connexion persistante (polling) + une connexion éphémère
    (test_connection) doivent pouvoir coexister comme sur un vrai ampli."""

    def __init__(self, status_message='state=OPERATE fwd=45.2 rl=26.5 id=12.3 temp=38'):
        self.status_message = status_message
        self.srv = socket.socket()
        self.srv.bind(('127.0.0.1', 0))
        self.port = self.srv.getsockname()[1]
        self.srv.listen(4)
        self._stop = False
        self.received = []
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while not self._stop:
            try:
                conn, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._handle_conn, args=(conn,), daemon=True).start()

    def _handle_conn(self, conn):
        with conn:
            try:
                conn.sendall(b'V2.1.5 \r')
                buf = b''
                while not self._stop:
                    conn.settimeout(5.0)
                    try:
                        chunk = conn.recv(256)
                    except socket.timeout:
                        continue
                    if not chunk:
                        break
                    buf += chunk
                    while b'\r' in buf:
                        line, buf = buf.split(b'\r', 1)
                        self._handle(conn, line.decode('ascii'))
            except OSError:
                pass

    def _handle(self, conn, line):
        self.received.append(line)
        # "C<seq>|<cmd>"
        if not line.startswith('C'):
            return
        seq, _, cmd = line[1:].partition('|')
        if cmd == 'status':
            conn.sendall(f'R{seq}|0|{self.status_message}\r'.encode('ascii'))
        else:
            conn.sendall(f'R{seq}|1|commande inconnue\r'.encode('ascii'))

    def close(self):
        self._stop = True
        self.srv.close()


def _fresh():
    """Réinitialise l'état persistant du module entre les tests."""
    pgxl.disconnect_persistent()


def test_get_state_disabled():
    _fresh()
    assert pgxl.get_state({}) == {'enabled': False}
    assert pgxl.get_state(None) == {'enabled': False}


def test_get_state_ok():
    _fresh()
    fake = FakePgxl()
    try:
        cfg = {'pgxl_enabled': True, 'pgxl_host': '127.0.0.1', 'pgxl_port': fake.port}
        st = pgxl.get_state(cfg)
        assert st['ok'] is True and st['enabled'] is True
        assert st['operate'] is True
        assert st['fwd_dbm'] == 45.2
        assert st['power_w'] is None
        assert st['id_amps'] == 12.3
        assert st['temp_c'] == 38.0
        assert fake.received[0] == 'C1|status'
    finally:
        _fresh()
        fake.close()


def test_get_state_host_manquant():
    _fresh()
    cfg = {'pgxl_enabled': True, 'pgxl_host': '', 'pgxl_port': 9008}
    st = pgxl.get_state(cfg)
    assert st['ok'] is False and 'hôte' in st['error'].lower() or 'ip' in st['error'].lower()


def test_get_state_injoignable():
    _fresh()
    # port fermé sur localhost -> connexion refusée immédiatement
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port_libre = s.getsockname()[1]
    s.close()
    cfg = {'pgxl_enabled': True, 'pgxl_host': '127.0.0.1', 'pgxl_port': port_libre}
    st = pgxl.get_state(cfg)
    assert st['ok'] is False
    assert st['enabled'] is True


def test_set_operate_refuse_toujours():
    """set_operate() n'envoie JAMAIS de commande — refus explicite documenté,
    même avec un ampli joignable (voir docstring de logx_powergenius.set_operate)."""
    _fresh()
    fake = FakePgxl()
    try:
        cfg = {'pgxl_enabled': True, 'pgxl_host': '127.0.0.1', 'pgxl_port': fake.port}
        r = pgxl.set_operate(cfg, True)
        assert r['ok'] is False
        assert 'confirm' in r['error'].lower()
        # aucune commande n'a jamais été envoyée au faux serveur pour ce test
        assert fake.received == []
    finally:
        _fresh()
        fake.close()


def test_set_operate_desactive():
    _fresh()
    r = pgxl.set_operate({}, True)
    assert r['ok'] is False and 'désactivé' in r['error']


def test_test_connection_ok():
    fake = FakePgxl()
    try:
        r = pgxl.test_connection('127.0.0.1', fake.port)
        assert r['ok'] is True
        assert r['firmware'].startswith('V2.1.5')
        assert r['status']['fwd_dbm'] == 45.2
    finally:
        fake.close()


def test_test_connection_hote_manquant():
    assert pgxl.test_connection('') == {'ok': False, 'error': 'Adresse IP/hôte manquante'}


def test_test_connection_injoignable():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port_libre = s.getsockname()[1]
    s.close()
    r = pgxl.test_connection('127.0.0.1', port_libre)
    assert r['ok'] is False


def test_test_connection_ne_touche_pas_la_persistante():
    """Le test éphémère ne doit jamais réutiliser/casser la connexion
    persistante utilisée par le polling logbook (même garantie que
    test_connection() dans logx_amp.py/logx_tci.py)."""
    _fresh()
    fake = FakePgxl()
    try:
        cfg = {'pgxl_enabled': True, 'pgxl_host': '127.0.0.1', 'pgxl_port': fake.port}
        st1 = pgxl.get_state(cfg)
        assert st1['ok'] is True
        r = pgxl.test_connection('127.0.0.1', fake.port)
        assert r['ok'] is True
        st2 = pgxl.get_state(cfg)
        assert st2['ok'] is True
    finally:
        _fresh()
        fake.close()


def test_reponse_async_ignoree_en_attendant_notre_seq():
    """Une trame S<0>|... intercalée avant notre R<seq> ne doit pas être
    confondue avec la réponse attendue."""
    _fresh()
    srv = socket.socket()
    srv.bind(('127.0.0.1', 0))
    port = srv.getsockname()[1]
    srv.listen(1)

    def _serve_once():
        conn, _ = srv.accept()
        with conn:
            conn.sendall(b'V1.0.0 \r')
            buf = b''
            conn.settimeout(2.0)
            while b'\r' not in buf:
                buf += conn.recv(256)
            # Répond d'abord par une trame async NON sollicitée, puis la vraie réponse
            conn.sendall(b'S0|state=REBOOT\r')
            conn.sendall(b'R1|0|state=OPERATE fwd=10.0\r')

    t = threading.Thread(target=_serve_once, daemon=True)
    t.start()
    try:
        transport = pgxl.PgxlPort('127.0.0.1', port, timeout=3.0)
        resp = transport.command('status', timeout=3.0)
        assert resp['ok'] is True
        assert 'OPERATE' in resp['message']
    finally:
        srv.close()
