# -*- coding: utf-8 -*-
"""Tests du scope CI-V 0x27 (panadapter natif Icom, chantier scope-civ-icom).

Trames SYNTHÉTIQUES construites à la main d'après la spec du chantier (issue
des guides CI-V officiels IC-7300MK2/IC-705) — aucun accès matériel, donc
aucune capture réelle : la fidélité à la spec documentée est ce qui compte
ici, pas une comparaison à un enregistrement.

Fichier séparé de tests/test_cat.py (comme demandé) plutôt que d'y ajouter
ces tests — celui-ci grossit vite avec le découpage en paquets. Les doubles
de test (QueuedCivTransport, _reponse_civ, _swap_addr_for_test) sont
REDÉFINIS localement plutôt qu'importés depuis test_cat.py : aucun autre
fichier de ce dépôt ne pratique l'import croisé entre modules de test (vérifié
avant d'écrire ce fichier), donc pas de précédent à suivre pour ça."""
import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_cat as cat


# ─── DOUBLES DE TEST : mêmes principes que tests/test_cat.py ───────────────

def _swap_addr_for_test(frame, addr_dest, addr_src):
    """Réémet une trame comme si elle venait de la radio — TO=addr_dest
    (0xE0/PC), FROM=addr_src (adresse radio) — inverse de civ_build_frame()
    qui construit toujours des requêtes PC->radio."""
    if len(frame) < 4:
        return frame
    return frame[:2] + bytes([addr_dest, addr_src]) + frame[4:]


def _reponse_civ(addr, cmd, sub=None, data=b''):
    """Trame de RÉPONSE radio->PC (TO=E0/PC, FROM=addr)."""
    return _swap_addr_for_test(cat.civ_build_frame(0xE0, cmd, sub, data), 0xE0, addr)


def _civ_ack(addr, ok=True):
    """Accusé CI-V générique (FB FD positif / FA FD négatif) — ne porte PAS
    l'écho de cmd/sub, comme documenté dans civ_is_ok()."""
    return cat.CIV_PREAMBLE + bytes([0xE0, addr]) + (b'\xFB\xFD' if ok else b'\xFA\xFD')


class QueuedCivTransport:
    """Sert une liste de trames PRÉ-CONSTRUITES, une par read_until() — même
    contrat que le double de tests/test_cat.py : jamais plus d'une trame à
    la fois, write() ignoré (peu importe ce qu'on envoie)."""

    def __init__(self, frames):
        self._queue = list(frames)

    def write(self, data):
        pass

    def read_until(self, terminator, timeout=1.0):
        if not self._queue:
            return b''
        return self._queue.pop(0)

    def close(self):
        pass


def _bcd(n):
    """BCD sur 1 octet : chaque CHIFFRE décimal de n devient un nibble —
    n=11 -> 0x11, PAS 0x0B. Même trucage que _civ_scope_bcd_order() à
    l'envers, utilisé ici côté construction de trame de test."""
    return int(str(n), 16)


def _pkt1_frame(addr, scope_mode, field1_hz, field2_hz, out_of_range=False):
    """Construit le paquet n°1 (le seul avec ④⑤⑥) — 15 octets de corps
    après ①VFO/②order/③division : ④mode, ⑤2×5 octets BCD, ⑥hors-plage."""
    body = (bytes([0x00, _bcd(1), 0x11, scope_mode])
            + cat.civ_encode_freq(field1_hz)
            + cat.civ_encode_freq(field2_hz)
            + bytes([1 if out_of_range else 0]))
    assert len(body) == 15
    return _reponse_civ(addr, 0x27, sub=0x00, data=body)


def _waveform_pkt_frame(addr, order, chunk):
    """Paquets 2-11 : ①VFO/②order/③division + chunk de waveform (50 octets
    pour 2-10, 25 pour 11 — la taille du chunk fait foi, pas une constante)."""
    body = bytes([0x00, _bcd(order), 0x11]) + bytes(chunk)
    return _reponse_civ(addr, 0x27, sub=0x00, data=body)


def _ligne_complete_frames(addr, scope_mode, field1_hz, field2_hz, waveform):
    """Assemble les 11 trames (paquet 1 + 9 chunks de 50 + 1 chunk de 25)
    d'une ligne scope complète, dans l'ordre — `waveform` doit faire 475
    octets, valeurs 0-160 (échelle Icom, PAS 0-255)."""
    assert len(waveform) == 475
    frames = [_pkt1_frame(addr, scope_mode, field1_hz, field2_hz, out_of_range=False)]
    for order in range(2, 11):
        start = (order - 2) * 50
        frames.append(_waveform_pkt_frame(addr, order, waveform[start:start + 50]))
    frames.append(_waveform_pkt_frame(addr, 11, waveform[450:475]))
    return frames


# ─── has_sub : le prérequis absolu de la spec ───────────────────────────────

def test_parse_frame_extrait_le_sub_de_la_commande_27():
    """SANS l'ajout de 0x27 au tuple has_sub de civ_parse_frame(), ce test
    échoue : `sub` resterait None et l'octet 0x00 (sous-commande "scope
    waveform") resterait collé en tête de `data` au lieu d'en être extrait."""
    addr = cat.CIV_ADDRESSES['IC-7300']
    body = (bytes([0x00, _bcd(1), 0x11, 0x00])
            + cat.civ_encode_freq(14200000) + cat.civ_encode_freq(25000)
            + bytes([0]))
    frame = cat.civ_build_frame(addr, 0x27, sub=0x00, data=body)
    parsed = cat.civ_parse_frame(frame)
    assert parsed is not None
    _, _, cmd, sub, data = parsed
    assert cmd == 0x27
    assert sub == 0x00          # None sans le correctif
    assert data == body         # b'\x00' + body sans le correctif


def test_parse_frame_extrait_le_sub_des_commandes_config_27_14_et_27_15():
    addr = cat.CIV_ADDRESSES['IC-9700']
    frame_mode = cat.civ_build_frame(addr, 0x27, sub=0x14, data=bytes([0x00]))
    parsed_mode = cat.civ_parse_frame(frame_mode)
    assert parsed_mode[2:] == (0x27, 0x14, bytes([0x00]))

    frame_span = cat.civ_build_frame(addr, 0x27, sub=0x15, data=cat.civ_encode_freq(10000))
    parsed_span = cat.civ_parse_frame(frame_span)
    assert parsed_span[2] == 0x27 and parsed_span[3] == 0x15
    assert cat.civ_decode_freq(parsed_span[4]) == 10000


# ─── civ_parse_scope_packet : décodage d'UN paquet ──────────────────────────

def test_parse_scope_packet_paquet1_center():
    body = (bytes([0x00, _bcd(1), 0x11, 0x00])
            + cat.civ_encode_freq(14200000) + cat.civ_encode_freq(25000)
            + bytes([0]))
    pkt = cat.civ_parse_scope_packet(0x00, body)
    assert pkt == {'order': 1, 'division': 11, 'scope_mode': 0x00,
                   'field1_hz': 14200000, 'field2_hz': 25000, 'out_of_range': False}


def test_parse_scope_packet_paquet1_hors_plage():
    body = (bytes([0x00, _bcd(1), 0x11, 0x01])
            + cat.civ_encode_freq(7000000) + cat.civ_encode_freq(7100000)
            + bytes([1]))
    pkt = cat.civ_parse_scope_packet(0x00, body)
    assert pkt['out_of_range'] is True
    assert pkt['scope_mode'] == 0x01


def test_parse_scope_packet_paquet_waveform_ordre_10_bcd_pas_hexa():
    """Piège explicite de la spec : le paquet n°10 porte l'octet BCD 0x10
    (PAS 0x0A, qui vaudrait 10 en hexa brut mais pas en BCD)."""
    body = bytes([0x00, 0x10, 0x11]) + bytes(range(50))
    pkt = cat.civ_parse_scope_packet(0x00, body)
    assert pkt['order'] == 10
    assert pkt['waveform'] == bytes(range(50))


def test_parse_scope_packet_ordre_11_bcd_pas_dix_sept():
    body = bytes([0x00, 0x11, 0x11]) + bytes(range(25))
    pkt = cat.civ_parse_scope_packet(0x00, body)
    assert pkt['order'] == 11   # PAS 17 (0x11 en hexa brut)


def test_parse_scope_packet_bcd_invalide_retourne_none():
    """Nibble > 9 dans l'octet order : trame corrompue, jamais d'exception."""
    body = bytes([0x00, 0xAB, 0x11]) + bytes(50)
    assert cat.civ_parse_scope_packet(0x00, body) is None


def test_parse_scope_packet_trop_court_retourne_none():
    assert cat.civ_parse_scope_packet(0x00, bytes([0x00, 0x01])) is None
    # paquet 1 déclaré (order=1) mais moins de 15 octets au total
    assert cat.civ_parse_scope_packet(0x00, bytes([0x00, 0x01, 0x11, 0x00]) + bytes(5)) is None


def test_parse_scope_packet_mauvais_sub_retourne_none():
    """27 14/27 15 (config) ne passent pas par civ_parse_scope_packet."""
    assert cat.civ_parse_scope_packet(0x14, bytes([0x00, 0x01, 0x11]) + bytes(12)) is None


# ─── civ_reassemble_scope_line : reconstruction de la ligne complète ───────

def test_reassemble_mode_center_ok():
    waveform = bytes([(i * 3) % 161 for i in range(475)])
    pkt1 = cat.civ_parse_scope_packet(0x00, (bytes([0x00, _bcd(1), 0x11, 0x00])
              + cat.civ_encode_freq(14200000) + cat.civ_encode_freq(25000) + bytes([0])))
    packets = [pkt1]
    for order in range(2, 11):
        start = (order - 2) * 50
        body = bytes([0x00, _bcd(order), 0x11]) + waveform[start:start + 50]
        packets.append(cat.civ_parse_scope_packet(0x00, body))
    body11 = bytes([0x00, _bcd(11), 0x11]) + waveform[450:475]
    packets.append(cat.civ_parse_scope_packet(0x00, body11))
    # Ordre volontairement mélangé : la reconstruction doit se faire par le
    # champ ②/order, pas par l'ordre de la liste passée en argument.
    import random
    random.Random(42).shuffle(packets)

    result = cat.civ_reassemble_scope_line(packets)
    assert result['ok'] is True
    assert result['mode'] == 'center'
    assert result['center_freq_hz'] == 14200000
    assert result['span_hz'] == 25000
    assert result['out_of_range'] is False
    assert result['data'] == list(waveform)
    assert len(result['data']) == 475


def test_reassemble_mode_fixed_bord_bas_haut_ok():
    waveform = bytes([(i * 7 + 3) % 161 for i in range(475)])
    packets = [cat.civ_parse_scope_packet(0x00, (bytes([0x00, _bcd(1), 0x11, 0x01])
                + cat.civ_encode_freq(7000000) + cat.civ_encode_freq(7100000) + bytes([0])))]
    for order in range(2, 11):
        start = (order - 2) * 50
        body = bytes([0x00, _bcd(order), 0x11]) + waveform[start:start + 50]
        packets.append(cat.civ_parse_scope_packet(0x00, body))
    body11 = bytes([0x00, _bcd(11), 0x11]) + waveform[450:475]
    packets.append(cat.civ_parse_scope_packet(0x00, body11))

    result = cat.civ_reassemble_scope_line(packets)
    assert result['ok'] is True
    assert result['mode'] == 'fixed'
    assert result['edge_lo_hz'] == 7000000
    assert result['edge_hi_hz'] == 7100000
    assert 'center_freq_hz' not in result
    assert result['data'] == list(waveform)


def test_reassemble_hors_plage_un_seul_paquet_data_vide():
    pkt1 = cat.civ_parse_scope_packet(0x00, (bytes([0x00, _bcd(1), 0x11, 0x00])
              + cat.civ_encode_freq(14200000) + cat.civ_encode_freq(25000) + bytes([1])))
    result = cat.civ_reassemble_scope_line([pkt1])
    assert result == {'ok': True, 'mode': 'center', 'out_of_range': True,
                       'center_freq_hz': 14200000, 'span_hz': 25000, 'data': []}


def test_reassemble_paquets_manquants_echoue_proprement():
    """Ligne interrompue (paquets 6-11 jamais arrivés) : erreur explicite,
    jamais d'exception ni de données partielles présentées comme complètes."""
    pkt1 = cat.civ_parse_scope_packet(0x00, (bytes([0x00, _bcd(1), 0x11, 0x00])
              + cat.civ_encode_freq(14200000) + cat.civ_encode_freq(25000) + bytes([0])))
    packets = [pkt1]
    for order in range(2, 6):
        body = bytes([0x00, _bcd(order), 0x11]) + bytes(50)
        packets.append(cat.civ_parse_scope_packet(0x00, body))
    result = cat.civ_reassemble_scope_line(packets)
    assert result['ok'] is False
    assert 'manquant' in result['error']


def test_reassemble_sans_paquet1_echoue_proprement():
    body = bytes([0x00, _bcd(2), 0x11]) + bytes(50)
    pkt2 = cat.civ_parse_scope_packet(0x00, body)
    result = cat.civ_reassemble_scope_line([pkt2])
    assert result['ok'] is False
    assert 'n°1' in result['error']


def test_reassemble_ignore_les_none_dans_la_liste():
    """civ_parse_scope_packet() peut renvoyer None (trame corrompue) — la
    reconstruction ne doit pas planter si la liste en contient."""
    result = cat.civ_reassemble_scope_line([None, None])
    assert result['ok'] is False


# ─── CivRadio.read_scope_line : boucle d'écoute bout en bout ───────────────

def test_civradio_read_scope_line_center_reassemble_bout_en_bout():
    addr = cat.CIV_ADDRESSES['IC-7300']
    waveform = bytes([(i * 5) % 161 for i in range(475)])
    frames = _ligne_complete_frames(addr, 0x00, 14200000, 25000, waveform)
    transport = QueuedCivTransport(frames)
    radio = cat.CivRadio(transport, addr)

    result = radio.read_scope_line(timeout=1.0)
    assert result['ok'] is True
    assert result['mode'] == 'center'
    assert result['center_freq_hz'] == 14200000
    assert result['span_hz'] == 25000
    assert result['data'] == list(waveform)


def test_civradio_read_scope_line_fixed_reassemble_bout_en_bout():
    addr = cat.CIV_ADDRESSES['IC-9700']
    waveform = bytes([(i * 11 + 1) % 161 for i in range(475)])
    frames = _ligne_complete_frames(addr, 0x01, 432000000, 432100000, waveform)
    transport = QueuedCivTransport(frames)
    radio = cat.CivRadio(transport, addr)

    result = radio.read_scope_line(timeout=1.0)
    assert result['ok'] is True
    assert result['mode'] == 'fixed'
    assert result['edge_lo_hz'] == 432000000
    assert result['edge_hi_hz'] == 432100000
    assert result['data'] == list(waveform)


def test_civradio_read_scope_line_hors_plage_un_seul_paquet():
    addr = cat.CIV_ADDRESSES['IC-705']
    frame = _pkt1_frame(addr, 0x00, 14200000, 25000, out_of_range=True)
    transport = QueuedCivTransport([frame])
    radio = cat.CivRadio(transport, addr)

    result = radio.read_scope_line(timeout=1.0)
    assert result == {'ok': True, 'mode': 'center', 'out_of_range': True,
                       'center_freq_hz': 14200000, 'span_hz': 25000, 'data': []}


def test_civradio_read_scope_line_paquets_manquants_echoue_proprement():
    addr = cat.CIV_ADDRESSES['IC-7851']
    frames = [_pkt1_frame(addr, 0x00, 14200000, 25000, out_of_range=False)]
    frames.append(_waveform_pkt_frame(addr, 2, bytes(50)))
    # Rien après : la radio "s'est tue" avant la fin de la ligne (QSY en
    # cours de balayage, par exemple) — read_until() renvoie b'' une fois la
    # file épuisée, comme le ferait un vrai port série arrivé en timeout.
    transport = QueuedCivTransport(frames)
    radio = cat.CivRadio(transport, addr)

    result = radio.read_scope_line(timeout=0.2)
    assert result['ok'] is False
    assert 'manquant' in result['error'] or 'reçue' in result['error']


def test_civradio_read_scope_line_rien_ne_repond():
    """Aucune trame scope (radio pas en écran SCOPE) : erreur qui nomme
    explicitement la limite documentée, pas une exception ni un faux succès."""
    addr = cat.CIV_ADDRESSES['IC-7300']
    transport = QueuedCivTransport([])
    radio = cat.CivRadio(transport, addr)
    result = radio.read_scope_line(timeout=0.2)
    assert result['ok'] is False
    assert 'error' in result


def test_civradio_read_scope_line_ignore_trame_mal_adressee():
    """Une trame 27 00 qui vient d'une AUTRE adresse (bus CI-V partagé) ne
    doit pas être prise pour un paquet de CETTE radio."""
    addr = cat.CIV_ADDRESSES['IC-7300']
    autre_addr = cat.CIV_ADDRESSES['IC-9700']
    parasite = _pkt1_frame(autre_addr, 0x00, 999999, 1000, out_of_range=True)
    vraie = _pkt1_frame(addr, 0x00, 14200000, 25000, out_of_range=True)
    transport = QueuedCivTransport([parasite, vraie])
    radio = cat.CivRadio(transport, addr)
    result = radio.read_scope_line(timeout=1.0)
    assert result['ok'] is True
    assert result['center_freq_hz'] == 14200000


# ─── Configuration 27 14 (mode) / 27 15 (span) ──────────────────────────────

def test_civ_scope_configure_frames_center_avec_span():
    frames = cat.civ_scope_configure_frames(0x94, 'center', 25000)
    assert len(frames) == 2
    p0 = cat.civ_parse_frame(frames[0])
    assert p0[2:] == (0x27, 0x14, bytes([0x00]))
    p1 = cat.civ_parse_frame(frames[1])
    assert p1[2] == 0x27 and p1[3] == 0x15
    assert cat.civ_decode_freq(p1[4]) == 25000


def test_civ_scope_configure_frames_fixed_sans_span():
    frames = cat.civ_scope_configure_frames(0x94, 'fixed')
    assert len(frames) == 1
    p0 = cat.civ_parse_frame(frames[0])
    assert p0[2:] == (0x27, 0x14, bytes([0x01]))


def test_civ_scope_configure_frames_center_sans_span_pas_de_27_15():
    """span_hz omis en mode Center : seule 27 14 part, pas de 27 15 avec une
    valeur inventée."""
    frames = cat.civ_scope_configure_frames(0x94, 'center')
    assert len(frames) == 1


def test_civ_scope_configure_frames_mode_invalide_leve():
    with pytest.raises(ValueError):
        cat.civ_scope_configure_frames(0x94, 'scroll')


def test_civradio_configure_scope_center_deux_accuses_positifs():
    addr = cat.CIV_ADDRESSES['IC-7300']
    transport = QueuedCivTransport([_civ_ack(addr), _civ_ack(addr)])
    radio = cat.CivRadio(transport, addr)
    assert radio.configure_scope('center', 10000) == {'ok': True}


def test_civradio_configure_scope_fixed_un_seul_accuse():
    addr = cat.CIV_ADDRESSES['IC-705']
    transport = QueuedCivTransport([_civ_ack(addr)])
    radio = cat.CivRadio(transport, addr)
    assert radio.configure_scope('fixed') == {'ok': True}


def test_civradio_configure_scope_accuse_negatif_signale_erreur():
    addr = cat.CIV_ADDRESSES['IC-7610']
    transport = QueuedCivTransport([_civ_ack(addr, ok=False)])
    radio = cat.CivRadio(transport, addr)
    res = radio.configure_scope('fixed')
    assert res['ok'] is False
    assert 'error' in res


def test_civradio_configure_scope_second_accuse_negatif_signale_erreur():
    """Le mode passe (27 14 OK) mais le span est refusé (27 15 NG) : l'échec
    doit être rapporté, pas avalé silencieusement."""
    addr = cat.CIV_ADDRESSES['IC-9700']
    transport = QueuedCivTransport([_civ_ack(addr, ok=True), _civ_ack(addr, ok=False)])
    radio = cat.CivRadio(transport, addr)
    res = radio.configure_scope('center', 500000)
    assert res['ok'] is False


def test_civradio_configure_scope_mode_invalide():
    addr = cat.CIV_ADDRESSES['IC-7300']
    radio = cat.CivRadio(QueuedCivTransport([]), addr)
    res = radio.configure_scope('scroll-c')
    assert res['ok'] is False
    assert 'error' in res


# ─── scope_civ_available / scope_configure / scope_line (niveau module) ────

def test_scope_civ_available_ok_modele_supporte():
    cfg = {'cat_enabled': True, 'cat_mode': 'native', 'cat_brand': 'icom', 'cat_model': 'IC-7300'}
    assert cat.scope_civ_available(cfg) == {'available': True, 'reason': ''}


def test_scope_civ_available_cat_desactive():
    res = cat.scope_civ_available({'cat_enabled': False})
    assert res['available'] is False
    assert res['reason']


def test_scope_civ_available_mode_non_natif():
    cfg = {'cat_enabled': True, 'cat_mode': 'tci', 'cat_model': 'IC-7300'}
    res = cat.scope_civ_available(cfg)
    assert res['available'] is False


def test_scope_civ_available_modele_non_supporte():
    cfg = {'cat_enabled': True, 'cat_mode': 'native', 'cat_brand': 'yaesu', 'cat_model': 'FT-991A'}
    res = cat.scope_civ_available(cfg)
    assert res['available'] is False


def test_scope_civ_available_tous_les_modeles_de_la_spec():
    """IC-7300/IC-7610/IC-9700/IC-705/IC-7851 — les 5 modèles nommés dans la
    spec du chantier doivent tous ressortir disponibles."""
    for model in ('IC-7300', 'IC-7610', 'IC-9700', 'IC-705', 'IC-7851'):
        cfg = {'cat_enabled': True, 'cat_mode': 'native', 'cat_brand': 'icom', 'cat_model': model}
        assert cat.scope_civ_available(cfg)['available'] is True, model


def test_scope_configure_refuse_hors_mode_natif():
    res = cat.scope_configure({'cat_enabled': True, 'cat_mode': 'tci'}, 'center', 10000)
    assert res['ok'] is False


def test_scope_line_refuse_hors_mode_natif():
    res = cat.scope_line({'cat_enabled': False})
    assert res['ok'] is False


# ─── HTTP : câblage des 3 endpoints (même harnais que
#     tests/test_cat_detection_http.py — vrai serveur, port éphémère) ───────

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


def test_http_scope_available_wire(server, monkeypatch):
    monkeypatch.setattr(cat, 'scope_civ_available', lambda cfg: {'available': True, 'reason': ''})
    status, d = _get(server, '/rig/scope_available')
    assert status == 200 and d == {'available': True, 'reason': ''}


def test_http_scope_line_wire(server, monkeypatch):
    monkeypatch.setattr(cat, 'scope_line', lambda cfg: {'ok': True, 'mode': 'center', 'data': [1, 2, 3]})
    status, d = _get(server, '/rig/scope_line')
    assert status == 200
    assert d['ok'] is True and d['data'] == [1, 2, 3]


def test_http_scope_line_erreur_status_200(server, monkeypatch):
    """ok=False est un état de polling normal (radio pas prête) — pas une
    erreur serveur, même convention que /rig/state : le code HTTP reste 200."""
    monkeypatch.setattr(cat, 'scope_line', lambda cfg: {'ok': False, 'error': 'radio muette'})
    status, d = _get(server, '/rig/scope_line')
    assert status == 200
    assert d['ok'] is False


def test_http_scope_configure_transmet_le_payload(server, monkeypatch):
    captured = {}

    def fake_configure(cfg, mode, span_hz=None):
        captured['mode'] = mode
        captured['span_hz'] = span_hz
        return {'ok': True}

    monkeypatch.setattr(cat, 'scope_configure', fake_configure)
    status, d = _post(server, '/rig/scope_configure', {'mode': 'center', 'span_hz': 25000})
    assert status == 200 and d == {'ok': True}
    assert captured == {'mode': 'center', 'span_hz': 25000}


def test_http_scope_configure_echec_renvoie_400(server, monkeypatch):
    monkeypatch.setattr(cat, 'scope_configure',
                         lambda cfg, mode, span_hz=None: {'ok': False, 'error': 'refus radio'})
    status, d = _post(server, '/rig/scope_configure', {'mode': 'fixed'})
    assert status == 400 and d['ok'] is False


def test_http_scope_configure_sans_token_refuse(server):
    body = json.dumps({'mode': 'center'}).encode('utf-8')
    req = urllib.request.Request(server + '/rig/scope_configure', data=body, method='POST',
                                 headers={'Content-Type': 'application/json'})
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code in (401, 403)
