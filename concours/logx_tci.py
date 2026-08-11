# -*- coding: utf-8 -*-
"""Pilotage TCI (Transceiver Control Interface) — protocole réseau WebSocket
pour transceivers SDR (Expert Electronics SunSDR/ExpertSDR3 et compatibles).

Troisième mode radio aux côtés de logx_cat (série natif) et
logx_rig (Hamlib rigctld) : contrairement aux deux autres, TCI est un
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
hashlib + base64), dans le même esprit que logx_rig.py qui parle
rigctld en TCP brut — ni 'websockets' ni 'websocket-client' ne sont installés
dans l'environnement du projet, et TCI ne justifie pas d'en ajouter une pour
ces usages (commandes texte courtes uniquement ; pas de flux audio/IQ ici).
"""
import base64
import cmath
import collections
import hashlib
import math
import os
import select
import socket
import struct
import threading
import time

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 50001
_WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
MAX_FRAME_LEN = 1 << 20      # 1 Mo : très au-dessus de toute trame TCI légitime
MAX_MESSAGE_LEN = 4 * MAX_FRAME_LEN  # borne cumulée toutes frames de continuation confondues
READ_IDLE_TIMEOUT_S = 30.0   # au-delà de ce silence, la connexion est jugée morte

# ═══════════════════════════════════════════════════════════════════════════
#  Flux IQ brut (frames WebSocket BINAIRES, struct Stream 64 octets d'en-tête)
#  — voir le gros bloc de fonctions pures après _cw_escape() pour le parsing/
#  décodage/FFT. Constantes du protocole regroupées ici avec le reste des
#  constantes du module.
# ═══════════════════════════════════════════════════════════════════════════

TCI_STREAM_HEADER_LEN = 64   # 8 x uint32_t (32o) + reserv[8] uint32_t (32o)

# enum StreamType (struct Stream.type)
TCI_STREAM_TYPE_IQ = 0
TCI_STREAM_TYPE_RX_AUDIO = 1
TCI_STREAM_TYPE_TX_AUDIO = 2
TCI_STREAM_TYPE_TX_CHRONO = 3
TCI_STREAM_TYPE_LINEOUT = 4

# enum SampleType (struct Stream.format)
TCI_SAMPLE_FORMAT_INT16 = 0
TCI_SAMPLE_FORMAT_INT24 = 1
TCI_SAMPLE_FORMAT_INT32 = 2
TCI_SAMPLE_FORMAT_FLOAT32 = 3

# IQ_SAMPLERATE: n'accepte QUE ces 4 valeurs discrètes d'après la spec — pas
# une plage arbitraire, contrairement à ce qu'on pourrait supposer par
# analogie avec une carte son classique.
TCI_IQ_SAMPLE_RATES_HZ = (48000, 96000, 192000, 384000)

# Taille de FFT fixe (puissance de 2, pas besoin de gérer une taille variable
# pour ce chantier) et plage dB de mise à l'échelle vers 0-255 — plage assez
# large pour ne pas saturer un signal fort ni noyer un signal faible dans le
# plancher de bruit (mêmes bornes que le AnalyserNode audio du panadapter,
# voir logx_panadapter.html demarrerAudio()).
TCI_FFT_SIZE = 4096
TCI_FFT_DB_MIN = -100.0
TCI_FFT_DB_MAX = -20.0
_TCI_MAG_EPS = 1e-12   # évite log10(0) sur un bin exactement nul


# ═══════════════════════════════════════════════════════════════════════════
#  Client WebSocket minimal (RFC 6455) — texte uniquement, pas de flux binaire
# ═══════════════════════════════════════════════════════════════════════════

class WebSocketClient:
    """Assez de RFC 6455 pour parler TCI : handshake HTTP Upgrade, frames texte
    masquées en émission (obligatoire côté client), non masquées en réception
    (le serveur ne masque jamais ses frames). Les commandes TCI tiennent dans
    une frame ; en réception, les frames de continuation sont recollées par
    sécurité (rafale d'initialisation notamment)."""

    WRITE_TIMEOUT_S = 5.0

    def __init__(self, host, port, timeout=3.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock = None
        self._buf = b''
        self._write_lock = threading.Lock()

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
        # Handshake terminé : TCI est un protocole push — au repos le serveur
        # n'envoie plus rien, donc le timeout de 3 s du handshake serait resté
        # inadapté (socket.timeout au bout de 3 s d'inactivité, fil de lecture
        # tué, état de fréquence figé). On borne plutôt le SILENCE à
        # READ_IDLE_TIMEOUT_S : au-delà, _recv_exact lève ConnectionError (pas
        # de perte du buffer déjà accumulé), le fil de lecture se termine
        # proprement et _ensure_connected() peut reconnecter — au lieu de
        # bloquer pour toujours sur un réseau coupé sans FIN/RST.
        self._sock.settimeout(READ_IDLE_TIMEOUT_S)

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
        # Le socket est en lecture bloquante bornée (voir connect()) mais sans
        # borne d'écriture explicite ici : sans select(), un pair mort sans
        # FIN/RST ferait attendre sendall() jusqu'à READ_IDLE_TIMEOUT_S — ou
        # indéfiniment si le timeout socket ne s'applique pas à l'écriture —
        # et donc geler l'appelant (thread HTTP).
        with self._write_lock:
            _, writable, _ = select.select([], [self._sock], [], self.WRITE_TIMEOUT_S)
            if not writable:
                raise TimeoutError('TCI : le pair ne répond plus (écriture bloquée)')
            self._sock.sendall(bytes(header) + mask_key + masked)

    def _recv_exact(self, n):
        while len(self._buf) < n:
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                raise ConnectionError(
                    'TCI : aucune donnée reçue depuis %ds - connexion jugée morte'
                    % READ_IDLE_TIMEOUT_S)
            if not chunk:
                raise ConnectionError('Connexion WebSocket fermée par le serveur')
            self._buf += chunk
        data, self._buf = self._buf[:n], self._buf[n:]
        return data

    def recv_message(self):
        """Retourne (is_binary, payload) d'UN message WebSocket complet
        (frames de continuation recollées) : payload est un `str` décodé
        UTF-8 pour un message TEXTE (les commandes ASCII TCI), des `bytes`
        bruts pour un message BINAIRE (un bloc `struct Stream` du flux IQ).
        La distinction se fait sur l'OPCODE de la PREMIÈRE frame du message
        (0x1=texte/0x2=binaire) — les frames de continuation suivantes
        portent l'opcode 0x0 et héritent du type du message.

        AVANT ce correctif, les frames BINAIRES (opcode 0x2) étaient
        SILENCIEUSEMENT ignorées : ni ajoutées à `parts`, ni retournées —
        la boucle `break`-ait quand même sur `fin`, produisant un message
        texte vide plutôt que les données IQ (voir tests/test_tci_spectrum.py
        pour un test qui aurait échoué sans ce correctif : le buffer IQ
        resterait vide en permanence, aucune ligne de spectre ne serait
        jamais calculable).

        Lève ConnectionError si le serveur ferme, répond automatiquement
        aux pings (obligatoire pour rester connecté)."""
        parts = []
        msg_is_binary = False
        total_len = 0
        while True:
            header = self._recv_exact(2)
            fin = header[0] & 0x80
            opcode = header[0] & 0x0F
            length = header[1] & 0x7F
            if length == 126:
                length = struct.unpack('>H', self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack('>Q', self._recv_exact(8))[0]
            if length > MAX_FRAME_LEN:
                raise ConnectionError('TCI : trame de %d octets refusée (> %d)'
                                       % (length, MAX_FRAME_LEN))
            total_len += length
            if total_len > MAX_MESSAGE_LEN:
                raise ConnectionError(
                    'TCI : message de %d octets refusé (cumulé sur plusieurs frames, > %d)'
                    % (total_len, MAX_MESSAGE_LEN))
            payload = self._recv_exact(length) if length else b''
            if opcode == 0x8:  # close
                raise ConnectionError('Serveur TCI : fermeture de connexion')
            if opcode == 0x9:  # ping -> pong obligatoire
                self._send_pong(payload)
                continue
            if opcode == 0x2:      # binaire, première frame du message
                msg_is_binary = True
                parts.append(payload)
            elif opcode in (0x1, 0x0):  # texte, ou continuation (0x0 hérite du type déjà fixé)
                parts.append(payload)
            if fin:
                break
        combined = b''.join(parts)
        if msg_is_binary:
            return True, combined
        return False, combined.decode('utf-8', errors='replace')

    def _send_pong(self, payload):
        header = bytearray([0x80 | 0xA, 0x80 | len(payload)])
        mask_key = os.urandom(4)
        masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        with self._write_lock:
            _, writable, _ = select.select([], [self._sock], [], self.WRITE_TIMEOUT_S)
            if not writable:
                raise TimeoutError('TCI : le pair ne répond plus (pong bloqué)')
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
#  Flux IQ brut -> spectre : parsing du header binaire, décodage des 4
#  formats d'échantillon, FFT radix-2 PURE PYTHON (aucune dépendance numpy,
#  voir requirements.txt/CLAUDE.md), tout en fonctions PURES (aucune E/S) —
#  même discipline que civ_parse_scope_packet/civ_reassemble_scope_line dans
#  logx_cat.py, testées isolément dans tests/test_tci_spectrum.py.
# ═══════════════════════════════════════════════════════════════════════════

# Header C : 8 x uint32_t (32o) PUIS reserv[8] (uint32_t x 8 = 32o, ignoré)
# = 64o au total, TOUT en little-endian — hypothèse de travail assumée mais
# PAS vérifiée sur un vrai serveur TCI (l'app source ExpertSDR3 est un
# logiciel Windows x86/x64, faute de matériel pour confirmer). '32x' saute
# les 32 octets de reserv sans les inclure dans le résultat unpack.
_TCI_STREAM_HEADER_STRUCT = '<8I32x'
assert struct.calcsize(_TCI_STREAM_HEADER_STRUCT) == TCI_STREAM_HEADER_LEN


def tci_parse_stream_header(payload):
    """Décode le header 64 octets d'UN bloc `struct Stream` (début d'une
    frame WebSocket binaire TCI). Retourne un dict {'receiver',
    'sample_rate', 'format', 'codec', 'crc', 'length', 'type', 'channels'}
    ou None si `payload` fait moins de 64 octets — trame malformée/tronquée,
    jamais d'exception (même garantie que civ_parse_scope_packet)."""
    if len(payload) < TCI_STREAM_HEADER_LEN:
        return None
    (receiver, sample_rate, fmt, codec, crc, length, stype, channels) = \
        struct.unpack(_TCI_STREAM_HEADER_STRUCT, payload[:TCI_STREAM_HEADER_LEN])
    return {'receiver': receiver, 'sample_rate': sample_rate, 'format': fmt,
            'codec': codec, 'crc': crc, 'length': length, 'type': stype,
            'channels': channels}


def tci_decode_samples(fmt, raw):
    """Décode `raw` (les octets après le header) selon `format` (SampleType)
    en une liste de float normalisés dans [-1, 1] environ — INT16/24/32
    signés little-endian, FLOAT32 déjà normalisé. Retourne None si `fmt` est
    inconnu ou si `raw` n'est pas un multiple exact de la taille d'un
    échantillon pour ce format (trame tronquée) — jamais d'exception."""
    if fmt == TCI_SAMPLE_FORMAT_INT16:
        n, size = len(raw) // 2, 2
        if n * size != len(raw):
            return None
        return [v / 32768.0 for v in struct.unpack('<%dh' % n, raw[:n * size])]
    if fmt == TCI_SAMPLE_FORMAT_INT24:
        # Pas de type struct natif pour du 24 bits — décodage à la main,
        # 3 octets little-endian par échantillon, signé sur 24 bits.
        n, size = len(raw) // 3, 3
        if n * size != len(raw):
            return None
        out = []
        for i in range(n):
            b0, b1, b2 = raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2]
            v = b0 | (b1 << 8) | (b2 << 16)
            if v & 0x800000:
                v -= 0x1000000
            out.append(v / 8388608.0)
        return out
    if fmt == TCI_SAMPLE_FORMAT_INT32:
        n, size = len(raw) // 4, 4
        if n * size != len(raw):
            return None
        return [v / 2147483648.0 for v in struct.unpack('<%di' % n, raw[:n * size])]
    if fmt == TCI_SAMPLE_FORMAT_FLOAT32:
        n, size = len(raw) // 4, 4
        if n * size != len(raw):
            return None
        return list(struct.unpack('<%df' % n, raw[:n * size]))
    return None


def tci_iq_samples_from_values(values):
    """Regroupe une liste de valeurs réelles décodées I,Q,I,Q,... (le cas
    `channels == 1`, seul traité ici — voir limite documentée plus bas) en
    échantillons complexes I+jQ. Une valeur orpheline en fin de liste
    (nombre impair, trame tronquée en plein milieu d'une paire) est ignorée
    plutôt que de deviner sa contrepartie."""
    n = len(values) // 2
    return [complex(values[2 * i], values[2 * i + 1]) for i in range(n)]


def _fft_radix2(x):
    """FFT Cooley-Tukey itérative in-place (algorithme standard, pas
    d'invention ici — voir tests/test_tci_spectrum.py pour la preuve contre
    un signal de référence connu). `x` : liste de `complex`, de longueur une
    puissance de 2 (TCI_FFT_SIZE = 4096, jamais une autre taille dans ce
    module). Même convention de signe que numpy.fft.fft
    (X[k] = somme x[n] * exp(-2j*pi*k*n/N)) — c'est ce que suppose
    tci_compute_fft_line() pour le recentrage fftshift-like."""
    n = len(x)
    if n <= 1:
        return x
    # Permutation par inversion de bits (bit-reversal) avant le papillon.
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            x[i], x[j] = x[j], x[i]
    length = 2
    while length <= n:
        wlen = cmath.exp(-2j * math.pi / length)
        half = length // 2
        for i in range(0, n, length):
            w = 1 + 0j
            for k in range(half):
                u = x[i + k]
                v = x[i + k + half] * w
                x[i + k] = u + v
                x[i + k + half] = u - v
                w *= wlen
        length <<= 1
    return x


def _hann_window(n):
    """Fenêtre de Hann standard, longueur `n` — réduit les fuites spectrales
    avant la FFT. n=1 est un cas dégénéré (jamais atteint avec
    TCI_FFT_SIZE=4096) traité à part pour éviter une division par zéro."""
    if n <= 1:
        return [1.0] * n
    return [0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) for i in range(n)]


def tci_compute_fft_line(samples):
    """Calcule UNE ligne de spectre (liste d'entiers 0-255, longueur
    TCI_FFT_SIZE) à partir d'une liste d'échantillons IQ complexes déjà
    prélevés dans le buffer circulaire — `samples` doit faire EXACTEMENT
    TCI_FFT_SIZE éléments (l'appelant tranche le buffer, cette fonction ne
    devine jamais une longueur). Retourne None si la longueur ne correspond
    pas.

    Pipeline : fenêtre de Hann -> FFT radix-2 -> recentrage type fftshift
    (DC au centre, fréquences négatives à gauche/positives à droite — même
    disposition qu'un panadapter bande de base IQ classique) -> magnitude en
    dB -> mise à l'échelle linéaire de [TCI_FFT_DB_MIN, TCI_FFT_DB_MAX] vers
    [0, 255], plafonnée aux deux bornes.

    Échelle 0-255 calculée ICI côté PYTHON (pas côté JS comme pour le scope
    CI-V, qui renvoie une échelle Icom 0-160 rescalée en JS) : choix
    délibéré pour que logx_panadapter.html n'ait pas à connaître une
    troisième convention d'échelle en plus d'audio/CI-V — TOUTES les sources
    livrent déjà du 0-255 au JS, qui n'en sait rien de plus."""
    if len(samples) != TCI_FFT_SIZE:
        return None
    window = _hann_window(TCI_FFT_SIZE)
    windowed = [samples[i] * window[i] for i in range(TCI_FFT_SIZE)]
    spectrum = _fft_radix2(windowed)
    half = TCI_FFT_SIZE // 2
    reordered = spectrum[half:] + spectrum[:half]   # fftshift : DC au centre
    out = []
    span = TCI_FFT_DB_MAX - TCI_FFT_DB_MIN
    for c in reordered:
        db = 20.0 * math.log10(abs(c) + _TCI_MAG_EPS)
        scaled = (db - TCI_FFT_DB_MIN) / span * 255.0
        out.append(int(round(max(0.0, min(255.0, scaled)))))
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  Client TCI — lit en continu, maintient un cache d'état, envoie les commandes
# ═══════════════════════════════════════════════════════════════════════════

class TciClient:
    """Pilote TCI haut niveau. `ws` est injecté (WebSocketClient réel ou
    double de test) — même principe que CivRadio/AsciiRadio dans
    logx_cat.py : aucune E/S directe dans cette classe, tout passe
    par `ws`. Contrairement au CAT classique, l'état est alimenté en continu
    par le fil de lecture (protocole push) plutôt qu'interrogé à la demande."""

    def __init__(self, ws):
        self.ws = ws
        self.state = {'ready': False, 'freq_hz': {}, 'mode': {}, 'ptt': {},
                      'smeter_dbm': None, 'device': None, 'protocol': None}
        self._lock = threading.Lock()
        self._reader = None
        self._stop = False
        # Buffer circulaire d'échantillons IQ complexes récents (flux binaire
        # IQ_STREAM) + métadonnées du dernier bloc — protégés par le MÊME
        # `self._lock` que `self.state` : ce fil (_read_loop) écrit dedans en
        # continu pendant qu'un thread HTTP (serveur multi-thread) peut le
        # lire au même moment pour calculer une FFT (get_iq_spectrum_line).
        self._iq_buffer = collections.deque(maxlen=TCI_FFT_SIZE)
        self._iq_meta = {'sample_rate_hz': None, 'receiver': None, 'center_freq_hz': None}

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
                is_binary, payload = self.ws.recv_message()
            except Exception:
                break
            if is_binary:
                # Chaque frame WS binaire porte DÉJÀ un struct Stream complet
                # en un seul morceau (contrairement au texte, pas de
                # découpage/recollage sur un séparateur nécessaire ici).
                self._handle_binary_frame(payload)
                continue
            buf += payload
            while ';' in buf:
                line, buf = buf.split(';', 1)
                self._handle_line(line.strip())

    def _handle_binary_frame(self, payload):
        """Route une frame WS binaire vers le buffer IQ si c'est un bloc
        IQ_STREAM (type==0) d'un seul canal — les autres types (audio RX/TX,
        chrono, lineout) et le multi-canal (`channels>1`, multi-récepteur
        multiplexé, ordre d'entrelacement non spécifié) sont HORS PÉRIMÈTRE
        de ce chantier et simplement ignorés plutôt que mal interprétés."""
        header = tci_parse_stream_header(payload)
        if header is None:
            return
        if header['type'] != TCI_STREAM_TYPE_IQ or header['channels'] != 1:
            return
        body = payload[TCI_STREAM_HEADER_LEN:]
        values = tci_decode_samples(header['format'], body)
        if not values:
            return
        # `length` (échantillons réels annoncés par le header) fait foi pour
        # le nombre de valeurs à utiliser, mais borné par ce qui a
        # RÉELLEMENT été décodé — un header mensonger ou une frame tronquée
        # en cours de transit ne doit jamais provoquer un IndexError.
        n = max(0, min(header['length'], len(values)))
        complexes = tci_iq_samples_from_values(values[:n])
        if not complexes:
            return
        with self._lock:
            self._iq_buffer.extend(complexes)
            self._iq_meta['sample_rate_hz'] = header['sample_rate']
            self._iq_meta['receiver'] = header['receiver']

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

    # ── Flux IQ (panadapter TCI) ────────────────────────────────────────────

    def set_iq_samplerate(self, hz):
        """IQ_SAMPLERATE : commande GLOBALE (pas d'argument récepteur),
        contrairement à IQ_START/IQ_STOP/DDS. L'appelant (tci_spectrum_
        configure) est responsable de vérifier `hz` contre
        TCI_IQ_SAMPLE_RATES_HZ avant d'appeler — cette méthode se contente
        d'envoyer, comme set_freq/set_mode envoient sans revalider.

        Vide le buffer IQ AVANT d'envoyer la commande (revue adversariale) :
        sans ça, un changement de débit en cours de flux laisse jusqu'à
        TCI_FFT_SIZE-1 échantillons captés à l'ANCIEN débit dans le deque —
        get_iq_spectrum_line() calculerait alors une FFT sur un buffer qui
        mélange deux débits d'échantillonnage physiquement différents,
        pendant que span_hz (déjà mis à jour au bloc binaire suivant)
        annoncerait le NOUVEAU débit : un spectre qui ne correspond à aucun
        débit réel jusqu'à ce que le buffer se soit intégralement renouvelé."""
        with self._lock:
            self._iq_buffer.clear()
            self._iq_meta['sample_rate_hz'] = None
        self._send('IQ_SAMPLERATE', int(hz))

    def set_dds(self, freq_hz, receiver='0'):
        """DDS : fréquence centrale du récepteur = centre du panadapter.
        Mémorisée côté client (sous le même verrou que le buffer IQ) pour
        que get_iq_spectrum_line() puisse renvoyer center_freq_hz sans
        dépendre d'une notification retour du serveur — le protocole ne
        documente pas d'écho de confirmation pour cette commande."""
        with self._lock:
            self._iq_meta['center_freq_hz'] = int(freq_hz)
        self._send('DDS', receiver, int(freq_hz))

    def start_iq(self, receiver='0'):
        self._send('IQ_START', receiver)

    def stop_iq(self, receiver='0'):
        self._send('IQ_STOP', receiver)

    def get_iq_spectrum_line(self):
        """Calcule UNE ligne de spectre (FFT TCI_FFT_SIZE points) à partir
        des derniers échantillons IQ reçus. `span_hz` vient du sample_rate
        RÉELLEMENT vu dans le dernier header binaire reçu (source de
        vérité : ce que le serveur dit streamer, pas ce qu'on a demandé via
        IQ_SAMPLERATE) ; `center_freq_hz` vient du dernier set_dds() envoyé
        par ce client (le protocole n'a pas de lecture retour dédiée)."""
        with self._lock:
            samples = list(self._iq_buffer)
            sample_rate = self._iq_meta['sample_rate_hz']
            center_hz = self._iq_meta['center_freq_hz']
        if len(samples) < TCI_FFT_SIZE:
            return {'ok': False, 'error': 'Buffer IQ pas encore plein (%d/%d échantillons) '
                    '— le flux vient-il de démarrer ?' % (len(samples), TCI_FFT_SIZE)}
        if not sample_rate:
            return {'ok': False, 'error': "Aucun bloc IQ reçu du serveur TCI pour l'instant"}
        if not center_hz:
            return {'ok': False, 'error': 'Fréquence centrale IQ inconnue (DDS jamais envoyé)'}
        data = tci_compute_fft_line(samples[-TCI_FFT_SIZE:])
        if data is None:
            return {'ok': False, 'error': 'Calcul de la FFT impossible'}
        return {'ok': True, 'center_freq_hz': center_hz, 'span_hz': sample_rate, 'data': data}

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
    'rigctld' / 'tci') reste porté par cat_settings() de logx_cat —
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
    logx_cat._ensure_connected)."""
    key = (settings['host'], settings['port'])
    with _persistent_lock:
        entry = _persistent.get('default')
        # On ne réutilise l'entrée que si le fil de lecture est TOUJOURS vivant :
        # sans ça, une connexion morte (ExpertSDR3 fermé, réseau tombé) servait
        # indéfiniment le dernier cache d'état avec ok=True — le logbook affichait
        # et enregistrait une fréquence fausse présentée comme fraîche.
        reader = getattr(entry['client'], '_reader', None) if entry else None
        if entry and entry['key'] == key and reader is not None and reader.is_alive():
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
    """État courant (fréquence + mode) — même forme que logx_cat/
    logx_rig pour que le client HTTP reste inchangé quel que soit le
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
    """QSY — même signature que logx_cat.set_freq/logx_rig.set_freq."""
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
        disconnect_persistent()
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
        disconnect_persistent()
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
        disconnect_persistent()
        return {'ok': False, 'error': f'Serveur TCI injoignable ({e})'}


def set_ptt(cfg, on):
    """Bascule PTT — même signature que logx_cat.set_ptt/
    logx_rig.set_ptt, pour le keyer vocal (logx_voicekeyer.py)."""
    settings = tci_settings(cfg)
    client, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    try:
        client.set_ptt(bool(on))
        return {'ok': True}
    except Exception as e:
        disconnect_persistent()
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


# ═══════════════════════════════════════════════════════════════════════════
#  Panadapter TCI — 3e source (après audio universel et scope CI-V Icom) :
#  même convention de nom (préfixe tci_spectrum_) que scope_civ_available/
#  scope_configure/scope_line dans logx_cat.py, câblées côté HTTP dans
#  logx_http.py sur /rig/tci_spectrum_*.
# ═══════════════════════════════════════════════════════════════════════════

def tci_spectrum_available(cfg):
    """available=True seulement si le pilotage radio est actif ET configuré
    en mode 'tci' (cat_settings() de logx_cat — le mode TCI est un des 4
    modes CAT existants, PAS un réglage séparé). Import de logx_cat fait ICI
    (pas en tête de module) : logx_cat ne dépend pas de logx_tci aujourd'hui,
    mais un import différé reste la garantie la moins fragile contre un futur
    import circulaire si ça change."""
    import logx_cat as cat
    settings = cat.cat_settings(cfg)
    if not settings['enabled']:
        return {'available': False, 'reason': 'Pilotage CAT désactivé (CONFIG)'}
    if settings['mode'] != 'tci':
        return {'available': False,
                'reason': 'Le spectre TCI nécessite le mode « TCI » (CONFIG > Radio CAT)'}
    return {'available': True, 'reason': ''}


def tci_spectrum_configure(cfg, enabled, sample_rate_hz=None):
    """Démarre/arrête le flux IQ TCI (récepteur 0) sur LA CONNEXION
    PERSISTANTE déjà ouverte pour le CAT TCI — pas de connexion séparée.

    enabled=True : IQ_SAMPLERATE (valeur vérifiée contre
    TCI_IQ_SAMPLE_RATES_HZ) puis DDS (fréquence VFO courante, déjà connue du
    cache d'état alimenté en continu par le fil de lecture push) puis
    IQ_START.
    enabled=False : IQ_STOP — À FAIRE quand le panadapter change de source ou
    se ferme, sinon le flux IQ continue à consommer réseau/CPU pour rien,
    potentiellement à 384 kHz en continu."""
    settings = tci_settings(cfg)
    client, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    try:
        if not enabled:
            client.stop_iq()
            return {'ok': True}
        try:
            rate = int(sample_rate_hz)
        except (TypeError, ValueError):
            rate = None
        if rate not in TCI_IQ_SAMPLE_RATES_HZ:
            return {'ok': False, 'error': f"Fréquence d'échantillonnage IQ invalide "
                    f"({sample_rate_hz}) — valeurs acceptées : "
                    f"{', '.join(str(r) for r in TCI_IQ_SAMPLE_RATES_HZ)}"}
        st = client.get_state()
        center_hz = st.get('freq_hz')
        if not center_hz:
            return {'ok': False, 'error': "Fréquence radio pas encore connue (aucun VFO reçu "
                    "du serveur TCI) — impossible de centrer le flux IQ"}
        client.set_iq_samplerate(rate)
        client.set_dds(center_hz)
        client.start_iq()
        return {'ok': True}
    except Exception as e:
        disconnect_persistent()
        return {'ok': False, 'error': f'Serveur TCI injoignable ({e})'}


def tci_spectrum_line(cfg):
    """Une ligne de spectre déjà calculée (FFT TCI_FFT_SIZE points, échelle
    0-255) — pollée par logx_panadapter.html toutes les ~500 ms quand la
    source TCI est active. ok=False (buffer pas encore plein, flux jamais
    démarré...) reste un état de polling normal, pas une exception."""
    settings = tci_settings(cfg)
    client, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    try:
        return client.get_iq_spectrum_line()
    except Exception as e:
        disconnect_persistent()
        return {'ok': False, 'error': f'Serveur TCI injoignable ({e})'}
