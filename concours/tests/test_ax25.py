# -*- coding: utf-8 -*-
"""Tests du parseur d'en-tête AX.25 (SSDV Phase 2, transport).

Format relu contre ax25_pad.h (wb2osz/direwolf) le 11/09/2026 -- voir
docs/superpowers/specs/2026-09-11-ssdv-phase2-transport-cadrage.md, §4bis.
Pas de matériel requis : trames construites à la main dans ce fichier,
avec le même codage que le ferait un vrai TNC/Direwolf."""
import os
import sys

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import logx_ax25 as ax  # noqa: E402


def _champ_adresse(indicatif, ssid=0, dernier=False):
    """Construit un champ d'adresse AX.25 de 7 octets : 6 octets d'indicatif
    (complété à droite par des espaces) décalés d'1 bit à gauche, + 1 octet
    SSID (bits 4-1) avec le bit d'extension (bit 0) posé si `dernier`."""
    indicatif = indicatif.upper().ljust(6)[:6]
    lettres = bytes((ord(c) << 1) & 0xFF for c in indicatif)
    ssid_octet = 0x60 | ((ssid & 0x0F) << 1) | (1 if dernier else 0)
    return lettres + bytes([ssid_octet])


def _trame(destination, source, info, repeteurs=(), controle=ax.CONTROLE_UI,
           pid=ax.PID_PAS_DE_COUCHE_3):
    champs = [_champ_adresse(destination[0], destination[1])]
    champs.append(_champ_adresse(source[0], source[1], dernier=not repeteurs))
    for i, (call, ssid) in enumerate(repeteurs):
        champs.append(_champ_adresse(call, ssid, dernier=(i == len(repeteurs) - 1)))
    corps = b''.join(champs) + bytes([controle])
    if controle == ax.CONTROLE_UI:
        corps += bytes([pid])
    return corps + info


def test_parser_entete_destination_source():
    trame = _trame(('APRS', 0), ('F4ABC', 3), b'donnee')
    e = ax.parser_entete(trame)
    assert e['destination'] == ('APRS', 0)
    assert e['source'] == ('F4ABC', 3)
    assert e['repeteurs'] == []
    assert e['info'] == b'donnee'


def test_parser_entete_avec_repeteurs():
    trame = _trame(('APRS', 0), ('F4ABC', 0), b'X', repeteurs=[('WIDE1', 1), ('WIDE2', 2)])
    e = ax.parser_entete(trame)
    assert e['repeteurs'] == [('WIDE1', 1), ('WIDE2', 2)]
    assert e['info'] == b'X'


def test_parser_entete_controle_ui_lit_le_pid():
    trame = _trame(('APRS', 0), ('F4ABC', 0), b'')
    e = ax.parser_entete(trame)
    assert e['controle'] == ax.CONTROLE_UI
    assert e['pid'] == ax.PID_PAS_DE_COUCHE_3


def test_parser_entete_controle_non_ui_pas_de_pid():
    trame = _trame(('APRS', 0), ('F4ABC', 0), b'suite', controle=0x13)
    e = ax.parser_entete(trame)
    assert e['controle'] == 0x13
    assert e['pid'] is None
    assert e['info'] == b'suite'   # aucun octet PID consommé par erreur


def test_parser_entete_indicatif_espaces_retires():
    trame = _trame(('F4A', 0), ('F4ABC', 0), b'')
    e = ax.parser_entete(trame)
    assert e['destination'] == ('F4A', 0)   # pas 'F4A   '


def test_parser_entete_ssid_extrait_correctement():
    for ssid in range(16):
        trame = _trame(('APRS', 0), ('F4ABC', ssid), b'')
        e = ax.parser_entete(trame)
        assert e['source'] == ('F4ABC', ssid), ssid


def test_parser_entete_info_contient_le_paquet_ssdv():
    charge = bytes(range(256))   # simule un paquet SSDV de 256 octets
    trame = _trame(('APRS', 0), ('F4ABC', 0), charge)
    e = ax.parser_entete(trame)
    assert e['info'] == charge
    assert len(e['info']) == 256


def test_parser_entete_trame_trop_courte_leve():
    with pytest.raises(ValueError):
        ax.parser_entete(bytes(5))


def test_parser_entete_champ_adresse_tronque_leve():
    # un seul champ de 7 octets sans bit d'extension posé, rien après
    champ = _champ_adresse('F4ABC', 0, dernier=False)
    with pytest.raises(ValueError):
        ax.parser_entete(champ)


def test_parser_entete_bit_extension_jamais_vu_leve():
    # 6 champs d'adresse, aucun avec le bit d'extension -- ne doit pas boucler
    champs = b''.join(_champ_adresse('R%d' % i, 0, dernier=False) for i in range(6))
    with pytest.raises(ValueError):
        ax.parser_entete(champs + bytes([ax.CONTROLE_UI, ax.PID_PAS_DE_COUCHE_3]))


def test_parser_entete_ui_sans_pid_leve():
    trame = _champ_adresse('APRS', 0) + _champ_adresse('F4ABC', 0, dernier=True) \
        + bytes([ax.CONTROLE_UI])   # UI mais rien après -- pas de PID
    with pytest.raises(ValueError):
        ax.parser_entete(trame)
