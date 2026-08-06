# -*- coding: utf-8 -*-
"""Tests du pilotage FlexRadio SmartSDR (logx_flexradio) : le transport TCP
texte (FlexSocket) est testé au niveau octets contre un mini-serveur TCP réel
(thread local, pas de lib) ; FlexClient (état + xmit) est testé avec un
double en mémoire — mêmes principes que test_tci.py (WebSocketClient réel +
TciClient sur double)."""
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_flexradio as flex


# ─── Mini-serveur TCP (thread local) pour valider FlexSocket réel ──────────

class _MiniFlexServer:
    """Accepte UNE connexion et expose send_line()/recv_line() pour piloter
    l'échange depuis le test — envoie le handshake V/H attendu par
    FlexClient.connect_and_start() dès que demandé par le test."""

    def __init__(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.bind(('127.0.0.1', 0))
        self._srv.listen(1)
        self.port = self._srv.getsockname()[1]
        self.conn = None
        self._buf = b''

    def accept(self):
        self.conn, _ = self._srv.accept()
        self.conn.settimeout(2.0)

    def send_line(self, text):
        self.conn.sendall((text + '\n').encode('ascii'))

    def recv_line(self):
        while b'\n' not in self._buf:
            chunk = self.conn.recv(4096)
            if not chunk:
                raise ConnectionError('fermé')
            self._buf += chunk
        line, self._buf = self._buf.split(b'\n', 1)
        return line.rstrip(b'\r').decode('ascii')

    def close(self):
        try:
            if self.conn:
                self.conn.close()
            self._srv.close()
        except Exception:
            pass


def test_flexsocket_lit_les_lignes_du_handshake_reel():
    server = _MiniFlexServer()
    t = threading.Thread(target=server.accept, daemon=True)
    t.start()
    client = flex.FlexSocket('127.0.0.1', server.port, timeout=2.0)
    client.connect()
    t.join(timeout=2.0)
    server.send_line('V1.0.0.0')
    server.send_line('H6F4EC23D')
    assert client.recv_line() == 'V1.0.0.0'
    assert client.recv_line() == 'H6F4EC23D'
    client.close()
    server.close()


def test_flexsocket_send_line_est_recu_tel_quel():
    server = _MiniFlexServer()
    t = threading.Thread(target=server.accept, daemon=True)
    t.start()
    client = flex.FlexSocket('127.0.0.1', server.port, timeout=2.0)
    client.connect()
    t.join(timeout=2.0)
    client.send_line('C1|sub slice all')
    assert server.recv_line() == 'C1|sub slice all'
    client.close()
    server.close()


def test_flexsocket_recolle_deux_lignes_recues_dans_un_seul_paquet():
    server = _MiniFlexServer()
    t = threading.Thread(target=server.accept, daemon=True)
    t.start()
    client = flex.FlexSocket('127.0.0.1', server.port, timeout=2.0)
    client.connect()
    t.join(timeout=2.0)
    server.conn.sendall(b'V1.0.0.0\nH6F4EC23D\n')
    assert client.recv_line() == 'V1.0.0.0'
    assert client.recv_line() == 'H6F4EC23D'
    client.close()
    server.close()


def test_connect_and_start_echoue_vite_si_pair_silencieux_apres_tcp():
    """Correctif : un pair qui accepte la connexion TCP mais ne parle jamais
    (pas de lignes V/H) doit faire échouer connect_and_start() en un temps
    BORNÉ et COURT (proche du timeout de connexion), pas au bout de
    READ_IDLE_TIMEOUT_S (30s, potentiellement ~2x ça en cumulant la lecture
    de V puis de H) comme AVANT le correctif — sans quoi un thread HTTP
    appelant restait bloqué bien plus longtemps que ce que CONNECT_TIMEOUT_S
    laisse penser à la lecture du code."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', 0))
    server.listen(1)
    port = server.getsockname()[1]
    accepted = []

    def _accept_and_stay_silent():
        try:
            conn, _ = server.accept()
            accepted.append(conn)
            # N'envoie et ne lit jamais rien : pair TCP accepté puis muet.
        except Exception:
            pass

    t = threading.Thread(target=_accept_and_stay_silent, daemon=True)
    t.start()
    sock = flex.FlexSocket('127.0.0.1', port, timeout=0.3)
    client = flex.FlexClient(sock)
    t0 = time.time()
    raised = None
    try:
        client.connect_and_start()
    except Exception as e:
        raised = e
    elapsed = time.time() - t0
    server.close()
    for c in accepted:
        try:
            c.close()
        except Exception:
            pass
    assert raised is not None
    # Loin des ~30-80s d'avant le correctif (READ_IDLE_TIMEOUT_S posé trop
    # tôt, avant même la lecture du handshake V/H) : borné proche du
    # timeout de connexion (0.3s) utilisé ici.
    assert elapsed < 3.0


# ─── FlexClient : état alimenté par un double socket en mémoire ───────────

class FakeSock:
    """Double en mémoire : `to_deliver` est la file de lignes que recv_line()
    renvoie une par une (V, H puis les messages S poussés par la radio) ;
    `sent` capture toute commande émise par le client."""

    def __init__(self, to_deliver=None):
        self._queue = list(to_deliver or [])
        self.sent = []
        self.closed = False

    def connect(self):
        pass

    def mark_handshake_done(self):
        # No-op côté double : le vrai FlexSocket bascule ici de timeout
        # court -> READ_IDLE_TIMEOUT_S, sans objet sur un socket en mémoire.
        pass

    def send_line(self, text):
        self.sent.append(text)

    def recv_line(self):
        if self._queue:
            return self._queue.pop(0)
        time.sleep(0.01)
        if self.closed:
            raise ConnectionError('fermé')
        return ''

    def close(self):
        self.closed = True


def _fake_sock(handshake_and_status):
    """['V1.0.0.0', 'H6F4EC23D', 'Sxxx|slice 0 ...', ...]"""
    return FakeSock(list(handshake_and_status))


def _wait_until(predicate, timeout=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_handshake_lit_le_handle():
    sock = _fake_sock(['V1.0.0.0', 'H6F4EC23D'])
    client = flex.FlexClient(sock)
    client.connect_and_start()
    assert client.state['handle'] == '6F4EC23D'
    assert client.state['ready'] is True
    client.close()


def test_connect_envoie_les_deux_abonnements():
    sock = _fake_sock(['V1.0.0.0', 'H6F4EC23D'])
    client = flex.FlexClient(sock)
    client.connect_and_start()
    assert 'C1|sub slice all' in sock.sent
    assert 'C2|sub radio all' in sock.sent
    client.close()


def test_statut_slice_met_a_jour_freq_et_mode():
    sock = _fake_sock(['V1.0.0.0', 'H6F4EC23D',
                        'S6F4EC23D|slice 0 RF_frequency=14.195000 mode=USB'])
    client = flex.FlexClient(sock)
    client.connect_and_start()
    assert _wait_until(lambda: client.get_state()['freq_hz'] == 14195000)
    st = client.get_state()
    assert st['mode'] == 'USB'
    client.close()


def test_statut_slice_non_defaut_sert_de_repli():
    # Seul le slice '1' est actif : get_state('0') doit quand même trouver
    # une fréquence via le repli plutôt que renvoyer None.
    sock = _fake_sock(['V1.0.0.0', 'H6F4EC23D',
                        'S6F4EC23D|slice 1 RF_frequency=7.100000 mode=LSB'])
    client = flex.FlexClient(sock)
    client.connect_and_start()
    assert _wait_until(lambda: client.get_state()['freq_hz'] == 7100000)
    client.close()


def test_interlock_transmitting_met_ptt_a_true():
    sock = _fake_sock(['V1.0.0.0', 'H6F4EC23D',
                        'S0|interlock state=TRANSMITTING source=SW'])
    client = flex.FlexClient(sock)
    client.connect_and_start()
    assert _wait_until(lambda: client.get_state()['ptt'] is True)
    client.close()


def test_interlock_ready_met_ptt_a_false_apres_transmission():
    sock = _fake_sock(['V1.0.0.0', 'H6F4EC23D',
                        'S0|interlock state=TRANSMITTING source=SW',
                        'S0|interlock state=READY'])
    client = flex.FlexClient(sock)
    client.connect_and_start()
    assert _wait_until(lambda: client.get_state()['ptt'] is False)
    client.close()


def test_set_ptt_envoie_xmit_1_et_xmit_0():
    sock = _fake_sock(['V1.0.0.0', 'H6F4EC23D'])
    client = flex.FlexClient(sock)
    client.connect_and_start()
    client.set_ptt(True)
    client.set_ptt(False)
    assert any(cmd.endswith('|xmit 1') for cmd in sock.sent)
    assert any(cmd.endswith('|xmit 0') for cmd in sock.sent)
    client.close()


def test_get_state_sans_slice_connu_renvoie_freq_none():
    sock = _fake_sock(['V1.0.0.0', 'H6F4EC23D'])
    client = flex.FlexClient(sock)
    client.connect_and_start()
    st = client.get_state()
    assert st['freq_hz'] is None
    client.close()


def test_read_loop_survit_a_rf_frequency_non_finie():
    """Correctif : une valeur RF_frequency non finie (ex. 'inf', qu'une radio
    déraillée ou une trame corrompue pourrait envoyer) levait un
    OverflowError dans round()/int() jamais attrapé par le `except
    ValueError` d'origine — le fil de lecture mourait silencieusement
    dessus. Vérifie que le fil SURVIT et continue à traiter la ligne
    suivante."""
    sock = _fake_sock(['V1.0.0.0', 'H6F4EC23D',
                        'S6F4EC23D|slice 0 RF_frequency=inf mode=USB',
                        'S6F4EC23D|slice 0 RF_frequency=14.195000 mode=USB'])
    client = flex.FlexClient(sock)
    client.connect_and_start()
    assert _wait_until(lambda: client.get_state()['freq_hz'] == 14195000)
    assert client._reader.is_alive()
    client.close()


def test_read_loop_survit_a_une_erreur_inattendue_dans_handle_line():
    """Filet de sécurité GÉNÉRIQUE de _read_loop() (indépendant de la
    correction ciblée RF_frequency ci-dessus) : même une erreur totalement
    inattendue levée par _handle_line() ne doit tuer ni le fil de lecture,
    ni empêcher le traitement des lignes suivantes — seule la ligne fautive
    est perdue."""
    sock = _fake_sock(['V1.0.0.0', 'H6F4EC23D', 'BOOM',
                        'S6F4EC23D|slice 0 RF_frequency=14.195000 mode=USB'])
    client = flex.FlexClient(sock)
    orig_handle_line = client._handle_line

    def _boom_once(line):
        if line == 'BOOM':
            raise RuntimeError('erreur inattendue simulée')
        return orig_handle_line(line)

    client._handle_line = _boom_once
    client.connect_and_start()
    assert _wait_until(lambda: client.get_state()['freq_hz'] == 14195000)
    assert client._reader.is_alive()
    client.close()


# ─── Couche pilotée par la config (flexradio_settings / get_state / set_ptt) ──

def _fake_open_sock_factory(script):
    def _factory(host, port, timeout=flex.CONNECT_TIMEOUT_S):
        return FakeSock(list(script))
    return _factory


def test_flexradio_settings_defauts_si_config_vide():
    s = flex.flexradio_settings({})
    assert s == {'enabled': False, 'host': flex.DEFAULT_HOST, 'port': flex.DEFAULT_PORT}


def test_flexradio_settings_lit_la_config():
    s = flex.flexradio_settings({'flexradio_enabled': True, 'flexradio_host': '192.168.1.40',
                                  'flexradio_port': '4993'})
    assert s == {'enabled': True, 'host': '192.168.1.40', 'port': 4993}


def test_flexradio_settings_port_invalide_retombe_sur_defaut():
    s = flex.flexradio_settings({'flexradio_port': 'abc'})
    assert s['port'] == flex.DEFAULT_PORT


def test_flexradio_settings_ne_leve_jamais_sur_cfg_none():
    s = flex.flexradio_settings(None)
    assert s['enabled'] is False and s['port'] == flex.DEFAULT_PORT


def test_get_state_desactive_ne_declenche_aucune_connexion(monkeypatch):
    def _boom(host, port, timeout=flex.CONNECT_TIMEOUT_S):
        raise AssertionError('ne devrait jamais être appelé si désactivé')
    monkeypatch.setattr(flex, '_open_sock', _boom)
    flex.disconnect_persistent()
    res = flex.get_state({'flexradio_enabled': False})
    assert res['ok'] is False and res['enabled'] is False


def test_get_state_via_cfg_renvoie_freq_et_mode(monkeypatch):
    monkeypatch.setattr(flex, '_open_sock', _fake_open_sock_factory(
        ['V1.0.0.0', 'H6F4EC23D', 'S6F4EC23D|slice 0 RF_frequency=21.300000 mode=CW']))
    flex.disconnect_persistent()
    cfg = {'flexradio_enabled': True, 'flexradio_host': '127.0.0.1', 'flexradio_port': '4992'}
    assert _wait_until(lambda: flex.get_state(cfg).get('freq_hz') == 21300000)
    st = flex.get_state(cfg)
    assert st['ok'] is True and st['mode'] == 'CW'
    flex.disconnect_persistent()


def test_set_ptt_via_cfg(monkeypatch):
    monkeypatch.setattr(flex, '_open_sock', _fake_open_sock_factory(['V1.0.0.0', 'H6F4EC23D']))
    flex.disconnect_persistent()
    cfg = {'flexradio_enabled': True, 'flexradio_host': '127.0.0.1', 'flexradio_port': '4992'}
    res = flex.set_ptt(cfg, True)
    assert res['ok'] is True
    entry = flex._persistent['default']['client']
    assert any(cmd.endswith('|xmit 1') for cmd in entry.sock.sent)
    flex.disconnect_persistent()


def test_set_ptt_desactive_renvoie_erreur_sans_connexion(monkeypatch):
    def _boom(host, port, timeout=flex.CONNECT_TIMEOUT_S):
        raise AssertionError('ne devrait jamais être appelé si désactivé')
    monkeypatch.setattr(flex, '_open_sock', _boom)
    flex.disconnect_persistent()
    res = flex.set_ptt({'flexradio_enabled': False}, True)
    assert res['ok'] is False


def test_connexion_persistante_reutilisee_si_config_inchangee(monkeypatch):
    monkeypatch.setattr(flex, '_open_sock', _fake_open_sock_factory(['V1.0.0.0', 'H6F4EC23D']))
    flex.disconnect_persistent()
    cfg = {'flexradio_enabled': True, 'flexradio_host': '127.0.0.1', 'flexradio_port': '4992'}
    flex.get_state(cfg)
    client1 = flex._persistent['default']['client']
    flex.get_state(cfg)
    client2 = flex._persistent['default']['client']
    assert client1 is client2
    flex.disconnect_persistent()


def test_reconnexion_si_host_ou_port_change(monkeypatch):
    monkeypatch.setattr(flex, '_open_sock', _fake_open_sock_factory(['V1.0.0.0', 'H6F4EC23D']))
    flex.disconnect_persistent()
    cfg1 = {'flexradio_enabled': True, 'flexradio_host': '127.0.0.1', 'flexradio_port': '4992'}
    cfg2 = {'flexradio_enabled': True, 'flexradio_host': '127.0.0.1', 'flexradio_port': '4993'}
    flex.get_state(cfg1)
    client1 = flex._persistent['default']['client']
    flex.get_state(cfg2)
    client2 = flex._persistent['default']['client']
    assert client1 is not client2
    assert client1.sock.closed is True
    flex.disconnect_persistent()


def test_erreur_connexion_ne_leve_jamais(monkeypatch):
    def _boom(host, port, timeout=flex.CONNECT_TIMEOUT_S):
        raise OSError('connexion refusée')
    monkeypatch.setattr(flex, '_open_sock', _boom)
    flex.disconnect_persistent()
    cfg = {'flexradio_enabled': True, 'flexradio_host': '127.0.0.1', 'flexradio_port': '4992'}
    res = flex.get_state(cfg)
    assert res['ok'] is False and 'error' in res
    flex.disconnect_persistent()


def test_test_connection_ephemere_ferme_la_connexion(monkeypatch):
    monkeypatch.setattr(flex, '_open_sock', _fake_open_sock_factory(
        ['V1.0.0.0', 'H6F4EC23D', 'S6F4EC23D|slice 0 RF_frequency=7.100000 mode=USB']))
    flex.disconnect_persistent()
    res = flex.test_connection('127.0.0.1', '4992')
    assert res['ok'] is True and res['freq_hz'] == 7100000
    assert '127.0.0.1' not in str(flex._persistent)  # n'a pas touché la connexion persistante


def test_test_connection_sans_slice_actif_signale_une_erreur(monkeypatch):
    monkeypatch.setattr(flex, '_open_sock', _fake_open_sock_factory(['V1.0.0.0', 'H6F4EC23D']))
    res = flex.test_connection('127.0.0.1', '4992')
    assert res['ok'] is False and 'error' in res


def test_test_connection_echoue_proprement_si_injoignable(monkeypatch):
    def _boom(host, port, timeout=flex.CONNECT_TIMEOUT_S):
        raise OSError('connexion refusée')
    monkeypatch.setattr(flex, '_open_sock', _boom)
    res = flex.test_connection('127.0.0.1', '4992')
    assert res['ok'] is False and 'error' in res
