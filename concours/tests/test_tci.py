# -*- coding: utf-8 -*-
"""Tests du pilotage TCI (logx_tci) : le client WebSocket RFC 6455
est écrit à la main (aucune lib externe dispo) donc testé au niveau octets
contre un mini-serveur TCP réel (thread local) ; le reste (TciClient, couche
config) est testé avec un double en mémoire, comme logx_cat."""
import base64
import hashlib
import os
import socket
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_tci as tci

_WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


# ─── Mini-serveur WebSocket (thread local, pas de lib) pour valider le client réel ──

class _MiniWsServer:
    """Accepte UNE connexion, fait le handshake HTTP, puis expose
    send_frame()/recv_unmasked() pour piloter l'échange depuis le test."""

    def __init__(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.bind(('127.0.0.1', 0))
        self._srv.listen(1)
        self.port = self._srv.getsockname()[1]
        self.conn = None

    def accept_and_handshake(self):
        self.conn, _ = self._srv.accept()
        self.conn.settimeout(2.0)
        data = b''
        while b'\r\n\r\n' not in data:
            data += self.conn.recv(4096)
        head = data.decode('ascii')
        key = [l for l in head.splitlines() if l.lower().startswith('sec-websocket-key')][0].split(':', 1)[1].strip()
        accept = base64.b64encode(hashlib.sha1((key + _WS_GUID).encode('ascii')).digest()).decode('ascii')
        resp = ('HTTP/1.1 101 Switching Protocols\r\n'
                'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                f'Sec-WebSocket-Accept: {accept}\r\n\r\n')
        self.conn.sendall(resp.encode('ascii'))

    def send_text_frame(self, text):
        """Frame SERVEUR -> non masquée, comme l'exige RFC 6455."""
        payload = text.encode('utf-8')
        header = bytearray([0x80 | 0x1])
        if len(payload) < 126:
            header.append(len(payload))
        else:
            header.append(126)
            header += struct.pack('>H', len(payload))
        self.conn.sendall(bytes(header) + payload)

    def send_ping(self, payload=b'hi'):
        self.conn.sendall(bytes([0x80 | 0x9, len(payload)]) + payload)

    def recv_client_frame(self):
        """Lit UNE frame venant du client et la démasque (le client DOIT
        masquer, c'est ce qu'on vérifie ici)."""
        header = self.conn.recv(2)
        length = header[1] & 0x7F
        masked = bool(header[1] & 0x80)
        assert masked, 'le client DOIT masquer ses frames (RFC 6455)'
        if length == 126:
            length = struct.unpack('>H', self.conn.recv(2))[0]
        mask_key = self.conn.recv(4)
        payload = self.conn.recv(length)
        return bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

    def recv_pong(self):
        header = self.conn.recv(2)
        opcode = header[0] & 0x0F
        return opcode == 0xA

    def close(self):
        try:
            if self.conn:
                self.conn.close()
            self._srv.close()
        except Exception:
            pass


def test_websocketclient_handshake_reussit_contre_un_vrai_serveur():
    server = _MiniWsServer()
    t = threading.Thread(target=server.accept_and_handshake, daemon=True)
    t.start()
    client = tci.WebSocketClient('127.0.0.1', server.port, timeout=2.0)
    client.connect()
    t.join(timeout=2.0)
    client.close()
    server.close()


def test_websocketclient_send_text_est_masque_et_decodable():
    server = _MiniWsServer()
    t = threading.Thread(target=server.accept_and_handshake, daemon=True)
    t.start()
    client = tci.WebSocketClient('127.0.0.1', server.port, timeout=2.0)
    client.connect()
    t.join(timeout=2.0)
    client.send_text('vfo:0,0,14074000;')
    received = server.recv_client_frame()
    assert received == b'vfo:0,0,14074000;'
    client.close()
    server.close()


def test_websocketclient_recv_message_decode_une_frame_serveur():
    server = _MiniWsServer()
    t = threading.Thread(target=server.accept_and_handshake, daemon=True)
    t.start()
    client = tci.WebSocketClient('127.0.0.1', server.port, timeout=2.0)
    client.connect()
    t.join(timeout=2.0)
    server.send_text_frame('device:SunSDR2DX;ready;')
    msg = client.recv_message()
    assert msg == 'device:SunSDR2DX;ready;'
    client.close()
    server.close()


def test_websocketclient_repond_pong_a_un_ping():
    server = _MiniWsServer()
    t = threading.Thread(target=server.accept_and_handshake, daemon=True)
    t.start()
    client = tci.WebSocketClient('127.0.0.1', server.port, timeout=2.0)
    client.connect()
    t.join(timeout=2.0)
    server.send_ping()
    server.send_text_frame('ready;')  # pour débloquer recv_message après le ping
    msg = client.recv_message()
    assert msg == 'ready;'
    assert server.recv_pong()
    client.close()
    server.close()


# ─── TciClient : état alimenté par un double WebSocket en mémoire ──────────

class FakeWs:
    """Double en mémoire : `to_deliver` est une file de messages que
    recv_message() renvoie un par un (simule les notifications push du
    serveur TCI) ; `sent` capture tout ce que le client a émis."""

    def __init__(self, to_deliver=None):
        self._queue = list(to_deliver or [])
        self.sent = []
        self.closed = False

    def connect(self, path='/'):
        pass

    def send_text(self, s):
        self.sent.append(s)

    def recv_message(self):
        if self._queue:
            return self._queue.pop(0)
        time.sleep(0.01)
        if self.closed:
            raise ConnectionError('fermé')
        return ''

    def close(self):
        self.closed = True


def _wait_until(predicate, timeout=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_handshake_met_ready_et_device_a_jour():
    ws = FakeWs(['protocol:ExpertSDR3,1.9;device:SunSDR2DX;ready;'])
    client = tci.TciClient(ws)
    client.connect_and_start()
    assert client.state['ready'] is True
    assert client.state['device'] == 'SunSDR2DX'
    client.close()


def test_plusieurs_commandes_dans_une_seule_frame_sont_toutes_parsees():
    ws = FakeWs(['ready;vfo:0,0,7100000;modulation:0,USB;'])
    client = tci.TciClient(ws)
    client.connect_and_start()
    assert _wait_until(lambda: client.get_state()['freq_hz'] == 7100000)
    st = client.get_state()
    assert st['mode'] == 'USB'
    client.close()


def test_trx_notification_met_a_jour_ptt():
    ws = FakeWs(['ready;', 'trx:0,true;'])
    client = tci.TciClient(ws)
    client.connect_and_start()
    assert _wait_until(lambda: client.get_state()['ptt'] is True)
    client.close()


def test_rx_channel_sensors_met_a_jour_le_smetre():
    ws = FakeWs(['ready;', 'rx_channel_sensors:0,0,-71.5;'])
    client = tci.TciClient(ws)
    client.connect_and_start()
    assert _wait_until(lambda: client.get_state()['smeter_dbm'] == -71.5)
    client.close()


def test_set_freq_envoie_la_commande_vfo_attendue():
    ws = FakeWs(['ready;'])
    client = tci.TciClient(ws)
    client.connect_and_start()
    client.set_freq(14074000)
    assert 'vfo:0,0,14074000;' in ws.sent
    client.close()


def test_set_mode_envoie_modulation_en_majuscules():
    ws = FakeWs(['ready;'])
    client = tci.TciClient(ws)
    client.connect_and_start()
    client.set_mode('usb')
    assert 'modulation:0,USB;' in ws.sent
    client.close()


def test_set_ptt_ajoute_la_source_tci():
    ws = FakeWs(['ready;'])
    client = tci.TciClient(ws)
    client.connect_and_start()
    client.set_ptt(True)
    assert 'trx:0,true,tci;' in ws.sent
    client.close()


def test_cw_macro_simple():
    ws = FakeWs(['ready;'])
    client = tci.TciClient(ws)
    client.connect_and_start()
    client.send_cw_macro('TU 599')
    assert 'cw_macros:0,TU 599;' in ws.sent
    client.close()


def test_cw_message_echappe_les_caracteres_reserves():
    ws = FakeWs(['ready;'])
    client = tci.TciClient(ws)
    client.connect_and_start()
    client.send_cw_message('TU', 'RA6:LH', '599;004,x')
    # ':' -> '^', ',' -> '~', ';' -> '*' (§3.2.1 de la doc officielle)
    assert 'cw_msg:0,TU,RA6^LH,599*004~x;' in ws.sent
    client.close()


def test_cw_message_repete_ajoute_le_suffixe_dollar():
    ws = FakeWs(['ready;'])
    client = tci.TciClient(ws)
    client.connect_and_start()
    client.send_cw_message('TU', 'RA6LH', '599 004', repeat=2)
    assert 'cw_msg:0,TU,RA6LH$2,599 004;' in ws.sent
    client.close()


def test_stop_cw_sans_argument():
    ws = FakeWs(['ready;'])
    client = tci.TciClient(ws)
    client.connect_and_start()
    client.stop_cw()
    assert 'cw_macros_stop;' in ws.sent
    client.close()


def test_get_state_sans_connexion_prete_renvoie_des_valeurs_none():
    ws = FakeWs([])  # jamais de 'ready;' délivré
    client = tci.TciClient(ws)
    client.connect_and_start()
    st = client.get_state()
    assert st['ready'] is False and st['freq_hz'] is None
    client.close()


# ─── Couche pilotée par la config (tci_settings / get_state / set_freq) ────

def _fake_open_ws_factory(script):
    """Fabrique un remplaçant de logx_tci._open_ws qui ignore
    host/port et renvoie un FakeWs pré-scripté."""
    def _factory(host, port, timeout=3.0):
        return FakeWs(list(script))
    return _factory


def test_tci_settings_defauts_si_config_vide():
    s = tci.tci_settings({})
    assert s['host'] == tci.DEFAULT_HOST and s['port'] == tci.DEFAULT_PORT


def test_tci_settings_lit_host_et_port_de_la_config():
    s = tci.tci_settings({'tci_host': '192.168.1.50', 'tci_port': '50002'})
    assert s['host'] == '192.168.1.50' and s['port'] == 50002


def test_get_state_via_cfg_renvoie_freq_et_mode(monkeypatch):
    monkeypatch.setattr(tci, '_open_ws',
                        _fake_open_ws_factory(['ready;vfo:0,0,21300000;modulation:0,CW;']))
    tci.disconnect_persistent()
    cfg = {'tci_host': '127.0.0.1', 'tci_port': '50001'}
    assert _wait_until(lambda: tci.get_state(cfg).get('freq_hz') == 21300000)
    st = tci.get_state(cfg)
    assert st['ok'] is True and st['mode'] == 'CW'
    tci.disconnect_persistent()


def test_set_freq_via_cfg_envoie_vfo_et_modulation(monkeypatch):
    monkeypatch.setattr(tci, '_open_ws', _fake_open_ws_factory(['ready;']))
    tci.disconnect_persistent()
    cfg = {'tci_host': '127.0.0.1', 'tci_port': '50001'}
    res = tci.set_freq(cfg, 14195000, mode='LSB')
    assert res['ok'] is True
    entry = tci._persistent['default']['client']
    assert 'vfo:0,0,14195000;' in entry.ws.sent
    assert 'modulation:0,LSB;' in entry.ws.sent
    tci.disconnect_persistent()


def test_send_cw_via_cfg(monkeypatch):
    monkeypatch.setattr(tci, '_open_ws', _fake_open_ws_factory(['ready;']))
    tci.disconnect_persistent()
    cfg = {'tci_host': '127.0.0.1', 'tci_port': '50001'}
    res = tci.send_cw(cfg, 'TU 599')
    assert res['ok'] is True
    entry = tci._persistent['default']['client']
    assert 'cw_macros:0,TU 599;' in entry.ws.sent
    tci.disconnect_persistent()


def test_connexion_persistante_reutilisee_si_config_inchangee(monkeypatch):
    monkeypatch.setattr(tci, '_open_ws', _fake_open_ws_factory(['ready;']))
    tci.disconnect_persistent()
    cfg = {'tci_host': '127.0.0.1', 'tci_port': '50001'}
    tci.get_state(cfg)
    client1 = tci._persistent['default']['client']
    tci.get_state(cfg)
    client2 = tci._persistent['default']['client']
    assert client1 is client2
    tci.disconnect_persistent()


def test_reconnexion_si_host_ou_port_change(monkeypatch):
    monkeypatch.setattr(tci, '_open_ws', _fake_open_ws_factory(['ready;']))
    tci.disconnect_persistent()
    tci.get_state({'tci_host': '127.0.0.1', 'tci_port': '50001'})
    client1 = tci._persistent['default']['client']
    tci.get_state({'tci_host': '127.0.0.1', 'tci_port': '50002'})
    client2 = tci._persistent['default']['client']
    assert client1 is not client2
    assert client1.ws.closed is True
    tci.disconnect_persistent()


def test_erreur_connexion_ne_leve_jamais(monkeypatch):
    def _boom(host, port, timeout=3.0):
        raise OSError('connexion refusée')
    monkeypatch.setattr(tci, '_open_ws', _boom)
    tci.disconnect_persistent()
    res = tci.get_state({'tci_host': '127.0.0.1', 'tci_port': '50001'})
    assert res['ok'] is False and 'error' in res
    tci.disconnect_persistent()


def test_test_connection_ephemere_ferme_la_connexion(monkeypatch):
    monkeypatch.setattr(tci, '_open_ws',
                        _fake_open_ws_factory(['ready;vfo:0,0,7100000;device:SunSDR2DX;']))
    tci.disconnect_persistent()
    res = tci.test_connection('127.0.0.1', '50001')
    assert res['ok'] is True and res['device'] == 'SunSDR2DX'
    assert '127.0.0.1' not in str(tci._persistent)  # n'a pas touché la connexion persistante


def test_test_connection_signale_absence_de_ready(monkeypatch):
    monkeypatch.setattr(tci, '_open_ws', _fake_open_ws_factory([]))
    res = tci.test_connection('127.0.0.1', '50001')
    assert res['ok'] is False and 'error' in res
