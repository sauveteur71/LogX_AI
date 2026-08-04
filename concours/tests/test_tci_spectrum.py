# -*- coding: utf-8 -*-
"""Tests du panadapter TCI (chantier feat/panadapter-tci) : parsing du header
binaire `struct Stream`, décodage des 4 formats d'échantillon, FFT radix-2
PURE PYTHON vérifiée contre un signal de référence connu, distinction texte/
binaire dans WebSocketClient.recv_message() (le bug corrigé par ce chantier),
câblage TciClient <-> buffer IQ, et câblage des 3 endpoints HTTP.

Trames SYNTHÉTIQUES construites à la main d'après la spec du chantier (TCI
Protocol v2.0, Expert Electronics/Expert Group) — aucun accès à un vrai
serveur TCI, donc aucune capture réelle : la fidélité à la spec documentée
et la preuve mathématique (FFT contre un signal connu) sont ce qui compte
ici, pas une comparaison à un enregistrement.

Fichier séparé de tests/test_tci.py (comme demandé) — celui-ci couvre le
canal spectre (flux IQ binaire), pas le canal CAT (commandes texte) déjà
couvert là-bas. Les doubles de test (FakeWs, helpers de construction de
trames) sont REDÉFINIS localement plutôt qu'importés d'aucun autre fichier
de test — même principe que tests/test_cat_scope_civ.py (pas de précédent
d'import croisé entre modules de test dans ce dépôt)."""
import cmath
import http.server
import json
import math
import os
import struct
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_tci as tci


# ─── Helpers de construction de trames (frames WS + struct Stream) ─────────

def _ws_frame(opcode, payload, fin=True):
    """Construit une frame WebSocket SERVEUR->client (non masquée, comme
    l'exige RFC 6455) prête à être injectée directement dans
    WebSocketClient._buf — recv_message() ne touche au socket QUE si son
    buffer interne est insuffisant (voir _recv_exact), donc fournir la
    trame complète à l'avance permet de tester sans vrai réseau."""
    header = bytearray()
    header.append((0x80 if fin else 0x00) | opcode)
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header += struct.pack('>H', length)
    else:
        header.append(127)
        header += struct.pack('>Q', length)
    return bytes(header) + payload


def _stream_header(receiver=0, sample_rate=48000, fmt=tci.TCI_SAMPLE_FORMAT_FLOAT32,
                    length=0, stype=tci.TCI_STREAM_TYPE_IQ, channels=1):
    """Header struct Stream (64 octets) — reserv[8] laissé à zéro par
    struct.pack ('32x' n'accepte pas d'argument, remplit de zéros)."""
    return struct.pack('<8I32x', receiver, sample_rate, fmt, 0, 0, length, stype, channels)


def _iq_binary_payload(receiver, sample_rate, iq_samples, fmt=tci.TCI_SAMPLE_FORMAT_FLOAT32):
    """Un bloc struct Stream IQ_STREAM complet (header + échantillons
    I,Q,I,Q,... entrelacés) — FLOAT32 uniquement ici (le décodage des 3
    autres formats est testé séparément et isolément plus bas, inutile de
    dupliquer l'encodage pour cette partie d'intégration)."""
    if fmt != tci.TCI_SAMPLE_FORMAT_FLOAT32:
        raise NotImplementedError('helper de test FLOAT32 seulement')
    values = []
    for c in iq_samples:
        values.append(c.real)
        values.append(c.imag)
    body = struct.pack('<%df' % len(values), *values)
    header = _stream_header(receiver=receiver, sample_rate=sample_rate, fmt=fmt,
                             length=len(values), stype=tci.TCI_STREAM_TYPE_IQ, channels=1)
    return header + body


def _wait_until(predicate, timeout=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


# ─── WebSocketClient.recv_message() : distinction texte/binaire ────────────
# C'EST le bug corrigé par ce chantier — voir logx_tci.WebSocketClient.
# recv_message() : avant le correctif, une frame binaire (opcode 0x2) était
# reçue (les octets étaient bien lus du socket) mais SILENCIEUSEMENT jetée
# (jamais ajoutée à `parts`, jamais retournée) — la boucle `break`-ait quand
# même sur `fin`, produisant un message texte vide plutôt que les données
# IQ. Le buffer IQ serait alors resté vide EN PERMANENCE, aucune ligne de
# spectre n'aurait jamais pu être calculée, sans qu'aucune exception ne
# signale le problème.

def test_recv_message_distingue_binaire_et_texte():
    client_bin = tci.WebSocketClient('127.0.0.1', 0)
    payload = b'\x01\x02\x03\x04\xff\x00'
    client_bin._buf = _ws_frame(0x2, payload)
    is_binary, data = client_bin.recv_message()
    assert is_binary is True
    assert data == payload   # AVANT le correctif : data == '' (chaîne vide)

    client_txt = tci.WebSocketClient('127.0.0.1', 0)
    client_txt._buf = _ws_frame(0x1, 'ready;device:SunSDR2DX;'.encode('utf-8'))
    is_binary2, data2 = client_txt.recv_message()
    assert is_binary2 is False
    assert data2 == 'ready;device:SunSDR2DX;'


def test_recv_message_binaire_recolle_les_frames_de_continuation():
    """Une frame binaire découpée en continuation (fin=False puis opcode 0x0
    fin=True) doit être recollée comme le texte l'est déjà."""
    client = tci.WebSocketClient('127.0.0.1', 0)
    part1, part2 = b'\x11\x22\x33', b'\x44\x55'
    client._buf = _ws_frame(0x2, part1, fin=False) + _ws_frame(0x0, part2, fin=True)
    is_binary, data = client.recv_message()
    assert is_binary is True
    assert data == part1 + part2


def test_recv_message_binaire_vide_reste_distingue_du_texte_vide():
    """Frame binaire de longueur nulle : is_binary doit rester True (pas
    confondu avec le repli texte vide du double de test)."""
    client = tci.WebSocketClient('127.0.0.1', 0)
    client._buf = _ws_frame(0x2, b'')
    is_binary, data = client.recv_message()
    assert is_binary is True
    assert data == b''


# ─── tci_parse_stream_header : parsing du header 64 octets ─────────────────

def test_tci_parse_stream_header_valide():
    header = _stream_header(receiver=1, sample_rate=192000,
                             fmt=tci.TCI_SAMPLE_FORMAT_INT16, length=256,
                             stype=tci.TCI_STREAM_TYPE_IQ, channels=1)
    h = tci.tci_parse_stream_header(header)
    assert h == {'receiver': 1, 'sample_rate': 192000, 'format': 0, 'codec': 0,
                 'crc': 0, 'length': 256, 'type': 0, 'channels': 1}


def test_tci_parse_stream_header_ignore_le_contenu_de_reserv():
    """Les 32 derniers octets (reserv[8]) ne doivent influer sur RIEN, quel
    que soit leur contenu — construits ici à la main (pas via _stream_header,
    qui les met à zéro) avec des octets non nuls."""
    base = struct.pack('<8I', 3, 384000, 2, 0, 0, 128, 0, 1)
    reserv_non_nul = bytes(range(32))
    h = tci.tci_parse_stream_header(base + reserv_non_nul)
    assert h == {'receiver': 3, 'sample_rate': 384000, 'format': 2, 'codec': 0,
                 'crc': 0, 'length': 128, 'type': 0, 'channels': 1}


def test_tci_parse_stream_header_trop_court_retourne_none():
    """Trame malformée/tronquée : jamais d'exception, un None explicite."""
    assert tci.tci_parse_stream_header(b'') is None
    assert tci.tci_parse_stream_header(bytes(63)) is None
    assert tci.tci_parse_stream_header(bytes(10)) is None


def test_tci_parse_stream_header_exactement_64_octets_ok():
    assert tci.tci_parse_stream_header(bytes(64)) is not None


# ─── tci_decode_samples : les 4 formats d'échantillon ───────────────────────

def test_tci_decode_samples_int16_valeurs_connues():
    raw = struct.pack('<4h', 32767, -32768, 0, 16384)
    vals = tci.tci_decode_samples(tci.TCI_SAMPLE_FORMAT_INT16, raw)
    assert vals[0] == pytest.approx(32767 / 32768)
    assert vals[1] == pytest.approx(-1.0)
    assert vals[2] == 0.0
    assert vals[3] == pytest.approx(0.5)


def test_tci_decode_samples_int24_positif_negatif_et_max():
    """0x400000 = 4194304 -> /8388608 = 0.5 ; en 24 bits signé, 0xC00000 =
    -4194304 -> -0.5 ; 0x7FFFFF = valeur positive max."""
    raw = (bytes([0x00, 0x00, 0x40]) + bytes([0x00, 0x00, 0xC0])
           + bytes([0xFF, 0xFF, 0x7F]))
    vals = tci.tci_decode_samples(tci.TCI_SAMPLE_FORMAT_INT24, raw)
    assert vals[0] == pytest.approx(0.5)
    assert vals[1] == pytest.approx(-0.5)
    assert vals[2] == pytest.approx(8388607 / 8388608)


def test_tci_decode_samples_int32_valeurs_connues():
    raw = struct.pack('<2i', 1073741824, -2147483648)
    vals = tci.tci_decode_samples(tci.TCI_SAMPLE_FORMAT_INT32, raw)
    assert vals[0] == pytest.approx(0.5)
    assert vals[1] == pytest.approx(-1.0)


def test_tci_decode_samples_float32_deja_normalise():
    raw = struct.pack('<2f', 0.25, -0.75)
    vals = tci.tci_decode_samples(tci.TCI_SAMPLE_FORMAT_FLOAT32, raw)
    assert vals[0] == pytest.approx(0.25)
    assert vals[1] == pytest.approx(-0.75)


def test_tci_decode_samples_format_inconnu_retourne_none():
    assert tci.tci_decode_samples(99, b'\x00\x00\x00\x00') is None


def test_tci_decode_samples_longueur_incompatible_retourne_none():
    """Trame tronquée en plein milieu d'un échantillon — jamais d'exception."""
    assert tci.tci_decode_samples(tci.TCI_SAMPLE_FORMAT_INT16, b'\x00') is None
    assert tci.tci_decode_samples(tci.TCI_SAMPLE_FORMAT_INT24, b'\x00\x00') is None
    assert tci.tci_decode_samples(tci.TCI_SAMPLE_FORMAT_INT32, b'\x00\x00\x00') is None
    assert tci.tci_decode_samples(tci.TCI_SAMPLE_FORMAT_FLOAT32, b'\x00\x00\x00') is None


def test_tci_decode_samples_vide_retourne_liste_vide():
    assert tci.tci_decode_samples(tci.TCI_SAMPLE_FORMAT_INT16, b'') == []


# ─── tci_iq_samples_from_values : entrelacement I,Q ─────────────────────────

def test_tci_iq_samples_from_values_paires():
    vals = [1.0, 2.0, 3.0, 4.0]
    out = tci.tci_iq_samples_from_values(vals)
    assert out == [complex(1.0, 2.0), complex(3.0, 4.0)]


def test_tci_iq_samples_from_values_valeur_orpheline_ignoree():
    """Nombre impair de valeurs (trame tronquée en plein milieu d'une
    paire) : la dernière valeur orpheline est ignorée, pas devinée."""
    vals = [1.0, 2.0, 3.0]
    out = tci.tci_iq_samples_from_values(vals)
    assert out == [complex(1.0, 2.0)]


def test_tci_iq_samples_from_values_vide():
    assert tci.tci_iq_samples_from_values([]) == []


# ─── FFT radix-2 pure Python : preuve contre un signal de référence connu ──
# Amplitude volontairement FAIBLE (2e-5) : avec la fenêtre de Hann et
# TCI_FFT_SIZE=4096, un signal d'amplitude 1 sature une bonne partie de la
# plage dB [-100,-20] (magnitude ~ amp*N/2, largement > 0 dB) — la
# quantification 0-255 produit alors un large PLATEAU de bins à 255 (fuite
# spectrale de la fenêtre de Hann au-dessus du seuil de clipping), rendant
# la position du "pic" ambiguë de +/-18 bins. Une amplitude qui reste sous
# le seuil de clipping restitue un pic NET et sans ambiguïté — trouvé en
# vérifiant numériquement avant d'écrire ces assertions (voir commentaire
# tci_compute_fft_line dans logx_tci.py pour la formule de mise à l'échelle).

def test_fft_pic_frequence_positive_bin_attendu():
    fs, n, f, amp = 48000, tci.TCI_FFT_SIZE, 5000.0, 2e-5
    samples = [amp * cmath.exp(2j * math.pi * f * k / fs) for k in range(n)]
    data = tci.tci_compute_fft_line(samples)
    assert data is not None and len(data) == n
    # fftshift : bin = round(f*N/fs) + N/2 (voir tci_compute_fft_line)
    bin_attendu = round(f * n / fs) + n // 2
    bin_trouve = max(range(n), key=lambda k: data[k])
    assert abs(bin_trouve - bin_attendu) <= 1


def test_fft_pic_frequence_negative_bin_attendu():
    fs, n, f, amp = 96000, tci.TCI_FFT_SIZE, -12000.0, 2e-5
    samples = [amp * cmath.exp(2j * math.pi * f * k / fs) for k in range(n)]
    data = tci.tci_compute_fft_line(samples)
    bin_attendu = round(f * n / fs) + n // 2
    bin_trouve = max(range(n), key=lambda k: data[k])
    assert abs(bin_trouve - bin_attendu) <= 1


def test_fft_signal_continu_dc_pic_au_centre():
    """Une porteuse IQ constante (fréquence nulle) doit produire son pic
    exactement au bin central (DC recentré par le fftshift-like)."""
    n = tci.TCI_FFT_SIZE
    samples = [complex(2e-5, 0.0)] * n
    data = tci.tci_compute_fft_line(samples)
    bin_trouve = max(range(n), key=lambda k: data[k])
    assert abs(bin_trouve - n // 2) <= 1


def test_fft_longueur_incorrecte_retourne_none():
    assert tci.tci_compute_fft_line([0j] * 10) is None
    assert tci.tci_compute_fft_line([0j] * (tci.TCI_FFT_SIZE + 1)) is None


def test_fft_sortie_toujours_dans_0_255():
    n = tci.TCI_FFT_SIZE
    samples = [cmath.exp(2j * math.pi * 1000.0 * k / 48000) for k in range(n)]  # amplitude 1 : sature volontairement
    data = tci.tci_compute_fft_line(samples)
    assert all(0 <= v <= 255 for v in data)
    assert len(data) == n


def test_hann_window_bornes_et_maximum():
    # n IMPAIR : l'échantillon central tombe exactement sur le maximum de la
    # fenêtre (cos(pi)=-1) — avec n PAIR (ex. 8), aucun échantillon ne tombe
    # exactement sur le sommet (vérifié : max(w) ~ 0.9505, pas 1.0).
    w = tci._hann_window(9)
    assert w[0] == pytest.approx(0.0)
    assert w[-1] == pytest.approx(0.0)
    assert max(w) == pytest.approx(1.0)
    assert len(w) == 9
    assert all(0.0 <= v <= 1.0 for v in w)


# ─── TciClient._handle_binary_frame : câblage buffer IQ ─────────────────────

def test_handle_binary_frame_remplit_le_buffer_iq_jusqu_a_fft_size():
    client = tci.TciClient(_FakeWs())
    n_par_bloc = 512
    total = 0
    while total < tci.TCI_FFT_SIZE:
        samples = [complex(0.001, 0.0) for _ in range(n_par_bloc)]
        client._handle_binary_frame(_iq_binary_payload(0, 48000, samples))
        total += n_par_bloc
    assert len(client._iq_buffer) == tci.TCI_FFT_SIZE   # deque(maxlen=...) plafonne
    assert client._iq_meta['sample_rate_hz'] == 48000
    assert client._iq_meta['receiver'] == 0


def test_handle_binary_frame_ignore_type_non_iq():
    client = tci.TciClient(_FakeWs())
    header = _stream_header(sample_rate=48000, fmt=tci.TCI_SAMPLE_FORMAT_FLOAT32,
                             length=2, stype=tci.TCI_STREAM_TYPE_RX_AUDIO, channels=1)
    body = struct.pack('<2f', 0.1, 0.2)
    client._handle_binary_frame(header + body)
    assert len(client._iq_buffer) == 0


def test_handle_binary_frame_ignore_multi_canal():
    """channels > 1 = multi-récepteur multiplexé, HORS PÉRIMÈTRE documenté
    (ordre d'entrelacement non spécifié) — ignoré plutôt que mal interprété."""
    client = tci.TciClient(_FakeWs())
    header = _stream_header(sample_rate=48000, fmt=tci.TCI_SAMPLE_FORMAT_FLOAT32,
                             length=4, stype=tci.TCI_STREAM_TYPE_IQ, channels=2)
    body = struct.pack('<4f', 0.1, 0.2, 0.3, 0.4)
    client._handle_binary_frame(header + body)
    assert len(client._iq_buffer) == 0


def test_handle_binary_frame_header_malforme_ignore_sans_exception():
    client = tci.TciClient(_FakeWs())
    client._handle_binary_frame(b'trop court')   # ne doit pas lever
    assert len(client._iq_buffer) == 0


def test_handle_binary_frame_length_menteur_ne_provoque_pas_indexerror():
    """Header annonçant plus d'échantillons que le corps n'en contient
    réellement (frame tronquée en transit) : jamais d'IndexError, `length`
    est borné par ce qui a RÉELLEMENT été décodé."""
    client = tci.TciClient(_FakeWs())
    header = _stream_header(sample_rate=48000, fmt=tci.TCI_SAMPLE_FORMAT_FLOAT32,
                             length=1000, stype=tci.TCI_STREAM_TYPE_IQ, channels=1)
    body = struct.pack('<4f', 0.1, 0.2, 0.3, 0.4)   # seulement 4 valeurs réelles, pas 1000
    client._handle_binary_frame(header + body)   # ne doit pas lever
    assert len(client._iq_buffer) == 2   # 4 valeurs réelles -> 2 complexes


# ─── Double en mémoire (texte ET binaire) — voir tests/test_tci.py pour
#     l'équivalent texte seul, redéfini ici sans import croisé ────────────

class _FakeWs:
    """Double en mémoire livrant une file de messages (is_binary, payload)
    — même contrat que le vrai WebSocketClient.recv_message() depuis le
    correctif de ce chantier. `sent` capture les commandes texte émises."""

    def __init__(self, messages=None):
        self._queue = list(messages or [])
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
        return False, ''

    def close(self):
        self.closed = True


def test_read_loop_route_binaire_et_texte_sans_se_bloquer_mutuellement():
    """Bout en bout via connect_and_start()/_read_loop() : démontre le
    câblage complet du correctif recv_message (texte -> _handle_line, binaire
    -> _handle_binary_frame), pas seulement l'appel direct à
    _handle_binary_frame() testé ci-dessus."""
    samples = [complex(0.001, 0.0) for _ in range(tci.TCI_FFT_SIZE)]
    payload = _iq_binary_payload(0, 48000, samples)
    ws = _FakeWs([(False, 'ready;vfo:0,0,14074000;'), (True, payload)])
    client = tci.TciClient(ws)
    client.connect_and_start()
    assert _wait_until(lambda: len(client._iq_buffer) == tci.TCI_FFT_SIZE)
    assert client.state['ready'] is True
    assert _wait_until(lambda: client.get_state()['freq_hz'] == 14074000)
    client.close()


# ─── Commandes de contrôle IQ (IQ_START/IQ_STOP/IQ_SAMPLERATE/DDS) ─────────

def test_set_iq_samplerate_envoie_la_commande_globale():
    client = tci.TciClient(_FakeWs([(False, 'ready;')]))
    client.connect_and_start()
    client.set_iq_samplerate(192000)
    assert 'IQ_SAMPLERATE:192000;' in client.ws.sent   # pas d'argument récepteur
    client.close()


def test_start_iq_envoie_iq_start_recepteur_0():
    client = tci.TciClient(_FakeWs([(False, 'ready;')]))
    client.connect_and_start()
    client.start_iq()
    assert 'IQ_START:0;' in client.ws.sent
    client.close()


def test_stop_iq_envoie_iq_stop_recepteur_0():
    client = tci.TciClient(_FakeWs([(False, 'ready;')]))
    client.connect_and_start()
    client.stop_iq()
    assert 'IQ_STOP:0;' in client.ws.sent
    client.close()


def test_set_dds_envoie_dds_et_memorise_le_centre_localement():
    """Le protocole n'a pas de lecture retour dédiée pour DDS — la mémoire
    côté client (sous verrou) est la SEULE source pour center_freq_hz."""
    client = tci.TciClient(_FakeWs([(False, 'ready;')]))
    client.connect_and_start()
    client.set_dds(14195000)
    assert 'DDS:0,14195000;' in client.ws.sent
    assert client._iq_meta['center_freq_hz'] == 14195000
    client.close()


# ─── TciClient.get_iq_spectrum_line : les 3 conditions d'échec + succès ────

def test_get_iq_spectrum_line_buffer_pas_plein():
    client = tci.TciClient(_FakeWs([(False, 'ready;')]))
    client.connect_and_start()
    res = client.get_iq_spectrum_line()
    assert res['ok'] is False
    client.close()


def test_get_iq_spectrum_line_sans_dds_jamais_envoye():
    """Buffer plein mais DDS jamais appelé : centre inconnu, refus explicite
    plutôt qu'un center_freq_hz devinée à 0."""
    client = tci.TciClient(_FakeWs())
    samples = [complex(0.0005, 0.0) for _ in range(tci.TCI_FFT_SIZE)]
    client._handle_binary_frame(_iq_binary_payload(0, 48000, samples))
    res = client.get_iq_spectrum_line()
    assert res['ok'] is False
    assert 'centrale' in res['error'] or 'DDS' in res['error']


def test_get_iq_spectrum_line_succes_complet():
    client = tci.TciClient(_FakeWs())
    samples = [complex(0.0005, 0.0) for _ in range(tci.TCI_FFT_SIZE)]
    client._handle_binary_frame(_iq_binary_payload(0, 192000, samples))
    client.set_dds(21300000)
    res = client.get_iq_spectrum_line()
    assert res['ok'] is True
    assert res['center_freq_hz'] == 21300000
    assert res['span_hz'] == 192000
    assert len(res['data']) == tci.TCI_FFT_SIZE
    assert all(0 <= v <= 255 for v in res['data'])


# ─── Thread-safety basique : écriture/lecture concurrentes sans exception ──
# Un vrai test de course est difficile à garantir de façon déterministe,
# mais ce test basique (aucune exception levée ni côté écrivain ni côté
# lecteur pendant un accès concurrent soutenu) reste utile pour vérifier que
# le verrou protège bien le buffer/les métadonnées partagés — voir le
# commentaire de TciClient.__init__ sur `self._lock`.

def test_buffer_iq_accede_concurremment_sans_exception():
    client = tci.TciClient(_FakeWs())
    client.set_dds(14200000)
    stop = threading.Event()
    errors = []
    payload = _iq_binary_payload(0, 48000, [complex(0.0003, 0.0) for _ in range(256)])

    def writer():
        while not stop.is_set():
            try:
                client._handle_binary_frame(payload)
            except Exception as e:
                errors.append(e)

    def reader():
        while not stop.is_set():
            try:
                client.get_iq_spectrum_line()
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for t in threads:
        t.start()
    time.sleep(0.3)
    stop.set()
    for t in threads:
        t.join(timeout=2)
    assert not errors


# ─── tci_spectrum_available / tci_spectrum_configure / tci_spectrum_line
#     (niveau module, pilotés par la config) ────────────────────────────────

def test_tci_spectrum_available_ok_mode_tci(monkeypatch):
    import logx_cat as cat
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'tci'})
    assert tci.tci_spectrum_available({}) == {'available': True, 'reason': ''}


def test_tci_spectrum_available_cat_desactive(monkeypatch):
    import logx_cat as cat
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': False, 'mode': 'tci'})
    res = tci.tci_spectrum_available({})
    assert res['available'] is False and res['reason']


def test_tci_spectrum_available_mode_non_tci(monkeypatch):
    import logx_cat as cat
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'native'})
    res = tci.tci_spectrum_available({})
    assert res['available'] is False


def _fake_open_ws_factory(script):
    def _factory(host, port, timeout=3.0):
        return _FakeWs(list(script))
    return _factory


def test_tci_spectrum_configure_enabled_envoie_samplerate_dds_start(monkeypatch):
    monkeypatch.setattr(tci, '_open_ws', _fake_open_ws_factory([(False, 'ready;vfo:0,0,14074000;')]))
    tci.disconnect_persistent()
    cfg = {'tci_host': '127.0.0.1', 'tci_port': '50001'}
    assert _wait_until(lambda: tci.get_state(cfg).get('freq_hz') == 14074000)
    res = tci.tci_spectrum_configure(cfg, True, 192000)
    assert res['ok'] is True
    entry = tci._persistent['default']['client']
    assert 'IQ_SAMPLERATE:192000;' in entry.ws.sent
    assert 'DDS:0,14074000;' in entry.ws.sent
    assert 'IQ_START:0;' in entry.ws.sent
    tci.disconnect_persistent()


def test_tci_spectrum_configure_disabled_envoie_iq_stop(monkeypatch):
    monkeypatch.setattr(tci, '_open_ws', _fake_open_ws_factory([(False, 'ready;')]))
    tci.disconnect_persistent()
    cfg = {'tci_host': '127.0.0.1', 'tci_port': '50001'}
    res = tci.tci_spectrum_configure(cfg, False)
    assert res['ok'] is True
    entry = tci._persistent['default']['client']
    assert 'IQ_STOP:0;' in entry.ws.sent
    tci.disconnect_persistent()


def test_tci_spectrum_configure_refuse_sample_rate_invalide(monkeypatch):
    monkeypatch.setattr(tci, '_open_ws', _fake_open_ws_factory([(False, 'ready;vfo:0,0,14074000;')]))
    tci.disconnect_persistent()
    cfg = {'tci_host': '127.0.0.1', 'tci_port': '50001'}
    assert _wait_until(lambda: tci.get_state(cfg).get('freq_hz') == 14074000)
    res = tci.tci_spectrum_configure(cfg, True, 44100)
    assert res['ok'] is False
    tci.disconnect_persistent()


def test_tci_spectrum_configure_refuse_sans_vfo_connu(monkeypatch):
    monkeypatch.setattr(tci, '_open_ws', _fake_open_ws_factory([(False, 'ready;')]))
    tci.disconnect_persistent()
    cfg = {'tci_host': '127.0.0.1', 'tci_port': '50001'}
    res = tci.tci_spectrum_configure(cfg, True, 192000)
    assert res['ok'] is False
    tci.disconnect_persistent()


def test_tci_spectrum_line_erreur_connexion_ne_leve_jamais(monkeypatch):
    def _boom(host, port, timeout=3.0):
        raise OSError('connexion refusée')
    monkeypatch.setattr(tci, '_open_ws', _boom)
    tci.disconnect_persistent()
    res = tci.tci_spectrum_line({'tci_host': '127.0.0.1', 'tci_port': '50001'})
    assert res['ok'] is False and 'error' in res
    tci.disconnect_persistent()


def test_tci_spectrum_line_bout_en_bout(monkeypatch):
    """La trame IQ n'est mise dans la file du faux transport qu'APRÈS
    tci_spectrum_configure() — pas au moment de la connexion — pour
    refléter la causalité RÉELLE du protocole (un serveur TCI ne pousse des
    blocs IQ_STREAM qu'une fois IQ_START reçu, jamais avant). La mettre dans
    la file dès la connexion (comme avant ce correctif) la faisait consommer
    par le fil de lecture AVANT l'appel à configure(), qui vide désormais le
    buffer IQ (set_iq_samplerate() — voir la revue adversariale : sans ce
    vidage, un changement de débit en cours de flux mélangeait deux débits
    d'échantillonnage différents dans une même fenêtre FFT), faisant échouer
    ce test sur un ordre d'événements qui n'arrive jamais en vrai."""
    samples = [complex(0.0008, 0.0) for _ in range(tci.TCI_FFT_SIZE)]
    iq_payload = _iq_binary_payload(0, 192000, samples)
    monkeypatch.setattr(tci, '_open_ws', _fake_open_ws_factory([
        (False, 'ready;vfo:0,0,14074000;'),
    ]))
    tci.disconnect_persistent()
    cfg = {'tci_host': '127.0.0.1', 'tci_port': '50001'}
    assert _wait_until(lambda: tci.get_state(cfg).get('freq_hz') == 14074000)
    cfg_res = tci.tci_spectrum_configure(cfg, True, 192000)
    assert cfg_res['ok'] is True
    entry = tci._persistent['default']['client']
    entry.ws._queue.append((True, iq_payload))
    assert _wait_until(lambda: len(entry._iq_buffer) == tci.TCI_FFT_SIZE)
    line = tci.tci_spectrum_line(cfg)
    assert line['ok'] is True
    assert line['center_freq_hz'] == 14074000
    assert line['span_hz'] == 192000
    assert len(line['data']) == tci.TCI_FFT_SIZE
    tci.disconnect_persistent()


# ─── HTTP : câblage des 3 endpoints (même harnais que
#     tests/test_cat_scope_civ.py — vrai serveur, port éphémère) ───────────

import logx_http as httpmod


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def _post(base, path, payload):
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json',
                 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_http_tci_spectrum_available_wire(server, monkeypatch):
    monkeypatch.setattr(tci, 'tci_spectrum_available', lambda cfg: {'available': True, 'reason': ''})
    status, d = _get(server, '/rig/tci_spectrum_available')
    assert status == 200 and d == {'available': True, 'reason': ''}


def test_http_tci_spectrum_line_wire(server, monkeypatch):
    monkeypatch.setattr(tci, 'tci_spectrum_line',
                         lambda cfg: {'ok': True, 'center_freq_hz': 14074000,
                                      'span_hz': 192000, 'data': [1, 2, 3]})
    status, d = _get(server, '/rig/tci_spectrum_line')
    assert status == 200
    assert d['ok'] is True and d['data'] == [1, 2, 3]


def test_http_tci_spectrum_line_erreur_status_200(server, monkeypatch):
    """ok=False est un état de polling normal (buffer pas plein, flux pas
    démarré) — pas une erreur serveur, même convention que /rig/scope_line
    et /rig/state : le code HTTP reste 200."""
    monkeypatch.setattr(tci, 'tci_spectrum_line', lambda cfg: {'ok': False, 'error': 'buffer pas plein'})
    status, d = _get(server, '/rig/tci_spectrum_line')
    assert status == 200
    assert d['ok'] is False


def test_http_tci_spectrum_configure_transmet_le_payload(server, monkeypatch):
    captured = {}

    def fake_configure(cfg, enabled, sample_rate_hz=None):
        captured['enabled'] = enabled
        captured['sample_rate_hz'] = sample_rate_hz
        return {'ok': True}

    monkeypatch.setattr(tci, 'tci_spectrum_configure', fake_configure)
    status, d = _post(server, '/rig/tci_spectrum_configure', {'enabled': True, 'sample_rate_hz': 192000})
    assert status == 200 and d == {'ok': True}
    assert captured == {'enabled': True, 'sample_rate_hz': 192000}


def test_http_tci_spectrum_configure_refuse_sample_rate_invalide_avant_reseau(server, monkeypatch):
    """Le garde-fou HTTP doit refuser AVANT d'appeler tci_spectrum_configure
    (évite un aller-retour réseau TCI pour une erreur détectable sans lui) —
    la fonction monkeypatchée ne doit donc jamais être invoquée."""
    called = []

    def fake_configure(cfg, enabled, sample_rate_hz=None):
        called.append(1)
        return {'ok': True}

    monkeypatch.setattr(tci, 'tci_spectrum_configure', fake_configure)
    status, d = _post(server, '/rig/tci_spectrum_configure', {'enabled': True, 'sample_rate_hz': 44100})
    assert status == 400 and d['ok'] is False
    assert not called


def test_http_tci_spectrum_configure_disabled_sans_sample_rate_valide(server, monkeypatch):
    """enabled=false (IQ_STOP) ne dépend pas d'un sample_rate_hz valide —
    le garde-fou HTTP ne doit PAS le refuser dans ce cas."""
    captured = {}

    def fake_configure(cfg, enabled, sample_rate_hz=None):
        captured['enabled'] = enabled
        return {'ok': True}

    monkeypatch.setattr(tci, 'tci_spectrum_configure', fake_configure)
    status, d = _post(server, '/rig/tci_spectrum_configure', {'enabled': False})
    assert status == 200 and d['ok'] is True
    assert captured['enabled'] is False


def test_http_tci_spectrum_configure_echec_renvoie_400(server, monkeypatch):
    monkeypatch.setattr(tci, 'tci_spectrum_configure',
                         lambda cfg, enabled, sample_rate_hz=None: {'ok': False, 'error': 'refus radio'})
    status, d = _post(server, '/rig/tci_spectrum_configure', {'enabled': True, 'sample_rate_hz': 192000})
    assert status == 400 and d['ok'] is False


def test_http_tci_spectrum_configure_sans_token_refuse(server):
    body = json.dumps({'enabled': True, 'sample_rate_hz': 192000}).encode('utf-8')
    req = urllib.request.Request(server + '/rig/tci_spectrum_configure', data=body, method='POST',
                                  headers={'Content-Type': 'application/json'})
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code in (401, 403)
