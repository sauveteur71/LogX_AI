# -*- coding: utf-8 -*-
"""Tests du dé-encadrement KISS (SSDV Phase 2, transport).

Format vérifié contre la spec KISS (ax25.net) le 11/09/2026 -- voir
docs/superpowers/specs/2026-09-11-ssdv-phase2-transport-cadrage.md, §4bis.
Aucun matériel requis : tout est vérifiable sur des trames synthétiques,
même raisonnement que la Phase 1 SSDV sans le binaire réel."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import logx_kiss as k  # noqa: E402


def test_echapper_fend():
    assert k.echapper(bytes([0xC0])) == bytes([0xDB, 0xDC])


def test_echapper_fesc():
    assert k.echapper(bytes([0xDB])) == bytes([0xDB, 0xDD])


def test_echapper_octets_normaux_inchanges():
    assert k.echapper(bytes([0x01, 0x02, 0xFF])) == bytes([0x01, 0x02, 0xFF])


def test_desechapper_est_l_inverse_d_echapper():
    for donnees in [bytes([0xC0, 0x01, 0xDB, 0xFF]), bytes(range(256)), b'']:
        assert k.desechapper(k.echapper(donnees)) == donnees


def test_encadrer_pose_fend_au_debut_et_a_la_fin():
    trame = k.encadrer(b'ABC')
    assert trame[0] == k.FEND
    assert trame[-1] == k.FEND


def test_encadrer_echappe_le_contenu():
    trame = k.encadrer(bytes([0xC0]))   # un FEND DANS la charge
    # ne doit pas se lire comme une fin de trame prématurée
    assert trame == bytes([k.FEND, 0x00, k.FESC, k.TFEND, k.FEND])


def test_extraire_trames_une_trame_complete():
    brut = k.encadrer(b'HELLO')
    trames, reliquat = k.extraire_trames(brut)
    assert trames == [b'\x00HELLO']
    assert reliquat == b''


def test_extraire_trames_plusieurs_trames_concatenees():
    brut = k.encadrer(b'AAA') + k.encadrer(b'BBB')
    trames, reliquat = k.extraire_trames(brut)
    assert trames == [b'\x00AAA', b'\x00BBB']
    assert reliquat == b''


def test_extraire_trames_reliquat_recompose_au_prochain_appel():
    """Une trame coupée en plein milieu (lecture socket partielle) ne doit
    pas être perdue -- le reliquat, concaténé au prochain morceau reçu, doit
    reconstituer la trame complète."""
    complet = k.encadrer(b'PAQUETSSDV')
    coupe = len(complet) - 3
    morceau1, morceau2 = complet[:coupe], complet[coupe:]
    trames1, reliquat = k.extraire_trames(morceau1)
    assert trames1 == []          # rien de complet encore
    trames2, reliquat2 = k.extraire_trames(reliquat + morceau2)
    assert trames2 == [b'\x00PAQUETSSDV']
    assert reliquat2 == b''


def test_extraire_trames_fend_consecutifs_ignores():
    # bourrage classique KISS : plusieurs FEND d'affilée entre deux trames
    brut = bytes([k.FEND, k.FEND, k.FEND]) + k.encadrer(b'X')
    trames, reliquat = k.extraire_trames(brut)
    assert trames == [b'\x00X']


def test_extraire_trames_tampon_vide():
    assert k.extraire_trames(b'') == ([], b'')


def test_extraire_trames_charge_utile_echappee_correctement_recomposee():
    charge = bytes([0x00, 0xC0, 0xDB, 0x42])   # commande=0 + FEND + FESC + octet normal
    trame = k.encadrer(charge[1:], commande=charge[0])
    trames, _ = k.extraire_trames(trame)
    assert trames == [charge]
