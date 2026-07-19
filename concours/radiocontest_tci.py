# -*- coding: utf-8 -*-
"""Pilotage TCI (Transceiver Control Interface) — protocole réseau WebSocket
pour transceivers SDR (Expert Electronics SunSDR/ExpertSDR3 et compatibles).

Troisième mode radio aux côtés de radiocontest_cat (série natif) et
radiocontest_rig (Hamlib rigctld) : contrairement aux deux autres, TCI est un
protocole ASCII sur WebSocket (RFC 6455) — pas de port série, pas de démon
externe à lancer. Spec officielle vérifiée : "TCI Protocol" v2.0, Expert
Electronics, 12/01/2024 (repo GitHub ExpertSDR3/TCI). Port réseau par défaut
50001 pour ExpertSDR3 (40001 pour l'ancien ESDR2) — configurable dans tous
les cas, host/port sont des champs CONFIG comme pour rigctld.

Le protocole est fondamentalement PUSH : à la connexion le serveur envoie une
rafale de commandes d'initialisation puis l'état courant, et notifie ensuite
tout changement de lui-même — contrairement au CAT classique (CI-V/ASCII) où
chaque lecture d'état est une requête/réponse explicite. On exploite cette
particularité : un fil d'arrière-plan lit en continu et met à jour un cache
d'état ; get_state() renvoie ce cache sans aller-retour réseau à chaque appel
(le polling du logbook existant reste inchangé côté client).

Aucune lib externe : le client WebSocket est écrit à la main (socket +
hashlib + base64), dans le même esprit que radiocontest_rig.py qui parle
rigctld en TCP brut — ni 'websockets' ni 'websocket-client' ne sont installés
dans l'environnement du projet, et TCI ne justifie pas d'en ajouter une pour
ces usages (commandes texte courtes uniquement ; pas de flux audio/IQ ici).
"""
import base64
import hashlib
import os
import socket
import struct
import threading
import time

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 50001
_WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


# ═══════════════════════════════════════════════════════════════════════════
#  Client WebSocket minimal (RFC 6455) — texte uniquement, pas de flux binaire
# ═══════════════════════════════════════════════════════════════════════════

class WebSocketClient:
    """Assez de RFC 6455 pour parler TCI : handshake HTTP Upgrade, frames texte
    masquées en émission (obligatoire côté client), non masquées en réception
    (le serveur ne masque jamais ses frames). Les commandes TCI tiennent dans
    une frame ; en réception, les frames de continuation sont recollées par
    sécurité (rafale d'initialisation notamment)."""

    def __init__(self, host, port, timeout=3.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock = None
        self._buf = b''

    def connect(self, path='/'):
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        key = base64.b64encode(os.urandom(16)).decode('ascii')
        req = (f'GET {path} HTTP/1.1\r\n'
               f'Host: {self.host}:{self.port}\r\n'
               f'Upgrade: websocket\r\n'
               f'Connection: Upgrade\r\n'
               f'Sec-WebSocket-Key: {key}\r\n'
               f'Sec-WebSocket-Version: 13\r\n\r\n')
        self._sock.sendall(req.encode('ascii'))
        resp = self._read_http_response()
        expected = base64.b64encode(hashlib.sha1((key + _WS_GUID).encode('ascii')).digest()).decode('ascii')
        if '101' not in resp.split('\r\n', 1)[0] or expected not in resp:
            first_line = resp.splitlines()[0] if resp else 'pas de réponse'
            raise ConnectionError(f'Handshake WebSocket refusé : {first_line}')

    def _read_http_response(self):
        self._sock.settimeout(self.timeout)
        data = b''
        while b'\r\n\r\n' not in data:
            chunk = self._sock.recv(4096)
            if not chunk:
                break
            data += chunk
        head, _, rest = data.partition(b'\r\n\r\n')
        self._buf = rest  # ce qui suit l'en-tête HTTP est déjà du websocket
        return head.decode('ascii', errors='replace')

    def send_text(self, text):
        payload = text.encode('utf-8')
        length = len(payload)
        header = bytearray()
        header.append(0x80 | 0x1)  # FIN + opcode texte
        mask_bit = 0x80
        if length < 126:
            header.append(mask_bit | length)
        elif length < 65536:
            header.append(mask_bit | 126)
            header += struct.pack('>H', length)
        else:
            header.append(mask_bit | 127)
            header += struct.pack('>Q', length)
        mask_key = os.urandom(4)
        masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        self._sock.sendall(bytes(header) + mask_key + masked)

    def _recv_exact(self, n):
        while len(self._buf) < n:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError('Connexion WebSocket fermée par le serveur')
            self._buf += chunk
        data, self._buf = self._buf[:n], self._buf[n:]
        return data

    def recv_message(self):
        """Retourne le texte d'UN message WebSocket complet (frames de
        continuation recollées). Lève ConnectionError si le serveur ferme,
        répond automatiquement aux pings (obligatoire pour rester connecté)."""
        parts = []
        while True:
            header = self._recv_exact(2)
            fin = header[0] & 0x80
            opcode = header[0] & 0x0F
            length = header[1] & 0x7F
            if length == 126:
                length = struct.unpack('>H', self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack('>Q', self._recv_exact(8))[0]
            payload = self._recv_exact(length) if length else b''
            if opcode == 0x8:  # close
                raise ConnectionError('Serveur TCI : fermeture de connexion')
            if opcode == 0x9:  # ping -> pong obligatoire
                self._send_pong(payload)
                continue
            if opcode in (0x1, 0x0):  # texte ou continuation
                parts.append(payload)
            if fin:
                break
        return b''.join(parts).decode('utf-8', errors='replace')

    def _send_pong(self, payload):
        header = bytearray([0x80 | 0xA, 0x80 | len(payload)])
        mask_key = os.urandom(4)
        masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        self._sock.sendall(bytes(header) + mask_key + masked)

    def close(self):
        try:
            self._sock.close()
        except Exception:
            pass


def _cw_escape(text):
    """§3.2.1 de la doc : les caractères réservés du protocole sont remplacés
    dans le texte CW puis restitués par le serveur — sans ça un ':' ou ';'
    dans un message casserait le parsing de la commande elle-même."""
    return text.replace(':', '^').replace(',', '~').replace(';', '*')


# ═══════════════════════════════════════════════════════════════════════════
#  Client TCI — lit en continu, maintient un cache d'état, envoie les commandes
# ═══════════════════════════════════════════════════════════════════════════

class TciClient:
    """Pilote TCI haut niveau. `ws` est injecté (WebSocketClient réel ou
    double de test) — même principe que CivRadio/AsciiRadio dans
    radiocontest_cat.py : aucune E/S directe dans cette classe, tout passe
    par `ws`. Contrairement au CAT classique, l'état est alimenté en continu
    par le fil de lecture (protocole push) plutôt qu'interrogé à la demande."""

    def __init__(self, ws):
        self.ws = ws
        self.state = {'ready': False, 'freq_hz': {}, 'mode': {}, 'ptt': {},
                      'smeter_dbm': None, 'device': None, 'protocol': None}
        self._lock = threading.Lock()
        self._reader = None
        self._stop = False

    def connect_and_start(self):
        self.ws.connect()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        # Attend la rafale d'initialisation (READY;) avant de rendre la main,
        # sans bloquer indéfiniment si le serveur ne répond jamais.
        deadline = time.time() + 3.0
        while not self.state['ready'] and time.time() < deadline:
            time.sleep(0.05)

    def _read_loop(self):
        buf = ''
        while not self._stop:
            try:
                msg = self.ws.recv_message()
            except Exception:
                break
            buf += msg
            while ';' in buf:
                line, buf = buf.split(';', 1)
                self._handle_line(line.strip())

    def _handle_line(self, line):
        if not line:
            return
        name, _, rest = line.partition(':')
        name = name.strip().lower()
        args = rest.split(',') if rest else []
        with self._lock:
            if name == 'ready':
                self.state['ready'] = True
            elif name == 'device':
                self.state['device'] = args[0] if args else None
            elif name == 'protocol':
                self.state['protocol'] = args[0] if args else None
            elif name == 'vfo' and len(args) >= 3:
                try:
                    self.state['freq_hz'][(args[0], args[1])] = int(args[2])
                except ValueError:
                    pass
            elif name == 'modulation' and len(args) >= 2:
                self.state['mode'][args[0]] = args[1].upper()
            elif name == 'trx' and len(args) >= 2:
                self.state['ptt'][args[0]] = args[1].strip().lower() == 'true'
            elif name in ('rx_sensors', 'rx_channel_sensors') and args:
                try:
                    self.state['smeter_dbm'] = float(args[-1])
                except ValueError:
                    pass
            elif name == 'callsign_send':
                self.state['last_callsign_sent'] = args[0] if args else None

    def _send(self, name, *args):
        cmd = name + (':' + ','.join(str(a) for a in args) if args else '') + ';'
        self.ws.send_text(cmd)

    def get_state(self, receiver='0', channel='0'):
        with self._lock:
            return {'ready': self.state['ready'], 'device': self.state['device'],
                    'freq_hz': self.state['freq_hz'].get((receiver, channel)),
                    'mode': self.state['mode'].get(receiver),
                    'ptt': self.state['ptt'].get(receiver),
                    'smeter_dbm': self.state['smeter_dbm']}

    def set_freq(self, freq_hz, receiver='0', channel='0'):
        self._send('vfo', receiver, channel, int(freq_hz))

    def set_mode(self, mode, receiver='0'):
        self._send('modulation', receiver, mode.upper())

    def set_ptt(self, on, receiver='0', source='tci'):
        self._send('trx', receiver, 'true' if on else 'false', source)

    def set_power(self, percent, transceiver='0'):
        self._send('drive', transceiver, max(0, min(100, int(percent))))

    def send_cw_message(self, prefix, callsign, suffix, repeat=1, transceiver='0'):
        """cw_msg : conçu pour le contest (préfixe/indicatif/suffixe, indicatif
        éditable tant qu'il n'a pas fini d'être transmis) — meilleur choix que
        cw_macros quand on connaît la structure de l'échange."""
        cs = _cw_escape(callsign) + (f'${repeat}' if repeat and repeat > 1 else '')
        self._send('cw_msg', transceiver, _cw_escape(prefix), cs, _cw_escape(suffix))

    def send_cw_macro(self, text, transceiver='0'):
        self._send('cw_macros', transceiver, _cw_escape(text))

    def stop_cw(self):
        self._send('cw_macros_stop')

    def enable_rx_sensors(self, interval_ms=200):
        self._send('rx_sensors_enable', 'true', interval_ms)

    def close(self):
        self._stop = True
        self.ws.close()


# ═══════════════════════════════════════════════════════════════════════════
#  Couche pilotée par la config CLIENT — connexion persistante réutilisée
# ═══════════════════════════════════════════════════════════════════════════

# Point d'injection pour les tests : remplacer par un double qui ne touche
# pas un vrai socket (voir tests/test_tci.py). Par défaut, le vrai client WS.
_open_ws = WebSocketClient

_persistent = {}
_persistent_lock = threading.Lock()


def tci_settings(cfg):
    """Réglages TCI depuis la config CLIENT. Le choix du mode ('native' /
    'rigctld' / 'tci') reste porté par cat_settings() de radiocontest_cat —
    ce module ne gère que host/port, le dispatch se fait côté HTTP."""
    cfg = cfg or {}
    try:
        port = int(cfg.get('tci_port') or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return {'host': (cfg.get('tci_host') or '').strip() or DEFAULT_HOST, 'port': port}


def _ensure_connected(settings):
    """Retourne (client, erreur_ou_None). Connecte au premier appel, réutilise
    la connexion tant que host/port ne changent pas (même principe que
    radiocontest_cat._ensure_connected)."""
    key = (settings['host'], settings['port'])
    with _persistent_lock:
        entry = _persistent.get('default')
        if entry and entry['key'] == key:
            return entry['client'], None
        if entry:
            entry['client'].close()
            _persistent.pop('default', None)
        try:
            ws = _open_ws(settings['host'], settings['port'])
            client = TciClient(ws)
            client.connect_and_start()
        except Exception as e:
            return None, f"Impossible de joindre le serveur TCI {settings['host']}:{settings['port']} ({e})"
        _persistent['default'] = {'key': key, 'client': client}
        return client, None


def disconnect_persistent():
    """Ferme la connexion persistante (ex. avant de changer de config)."""
    with _persistent_lock:
        entry = _persistent.pop('default', None)
    if entry:
        entry['client'].close()


def get_state(cfg):
    """État courant (fréquence + mode) — même forme que radiocontest_cat/
    radiocontest_rig pour que le client HTTP reste inchangé quel que soit le
    mode radio actif."""
    settings = tci_settings(cfg)
    client, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err, 'enabled': True}
    st = client.get_state()
    if st['freq_hz'] is None:
        return {'ok': False, 'error': 'Pas encore reçu de fréquence du serveur TCI',
                'enabled': True}
    return {'ok': True, 'enabled': True, 'freq_hz': st['freq_hz'],
            'freq_khz': round(st['freq_hz'] / 1000.0, 2), 'mode': st['mode'] or '',
            'smeter_dbm': st['smeter_dbm'], 'device': st['device']}


def set_freq(cfg, freq_hz, mode=None):
    """QSY — même signature que radiocontest_cat.set_freq/radiocontest_rig.set_freq."""
    settings = tci_settings(cfg)
    client, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    try:
        client.set_freq(freq_hz)
        if mode:
            client.set_mode(mode)
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': f'Serveur TCI injoignable ({e})'}


def send_cw(cfg, text):
    """Texte CW libre via cw_macros (le bouton CW existant du logbook envoie
    du texte libre, pas une structure préfixe/indicatif/suffixe — cw_msg
    reste accessible via TciClient.send_cw_message pour un usage futur plus
    structuré)."""
    settings = tci_settings(cfg)
    client, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    text = (text or '').strip()
    if not text:
        return {'ok': False, 'error': 'Texte vide'}
    try:
        client.send_cw_macro(text[:120])
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': f'Serveur TCI injoignable ({e})'}


def stop_cw(cfg):
    settings = tci_settings(cfg)
    client, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    try:
        client.stop_cw()
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': f'Serveur TCI injoignable ({e})'}


def set_ptt(cfg, on):
    """Bascule PTT — même signature que radiocontest_cat.set_ptt/
    radiocontest_rig.set_ptt, pour le keyer vocal (radiocontest_voicekeyer.py)."""
    settings = tci_settings(cfg)
    client, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    try:
        client.set_ptt(bool(on))
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': f'Serveur TCI injoignable ({e})'}


def test_connection(host, port):
    """Test ÉPHÉMÈRE (bouton CONFIG) : connecte, attend l'état initial, ferme
    — ne touche jamais à la connexion persistante utilisée par le polling
    logbook."""
    host = (host or '').strip() or DEFAULT_HOST
    try:
        port = int(port or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    try:
        ws = _open_ws(host, port)
        client = TciClient(ws)
        client.connect_and_start()
    except Exception as e:
        return {'ok': False, 'error': f"Impossible de joindre {host}:{port} ({e})"}
    try:
        st = client.get_state()
        if not st['ready']:
            return {'ok': False, 'error': "Le serveur TCI n'a pas terminé son initialisation "
                                          "(pas de READY reçu) — vérifie qu'ExpertSDR3 (ou un "
                                          "logiciel compatible) tourne et que le serveur TCI est activé"}
        return {'ok': True, 'device': st['device'], 'freq_hz': st['freq_hz']}
    finally:
        client.close()
