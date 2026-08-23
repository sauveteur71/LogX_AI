# -*- coding: utf-8 -*-
"""FT2 Phase 5 — garde TX (can_send_ft2_reply) + envoi Reply strictement gardé.

LogX pilote la TX FT2 via Reply UDP à Decodium (pas d'audio local). Barrière de
sûreté : TOUTES les conditions requises, jamais de Reply auto, envoi UNIQUEMENT
vers l'adresse émettrice. Halt TX = coupe-circuit jamais gardé. Fonctions pures
+ faux socket : aucune émission réelle.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_ft2 as ft2

_VALID = {
    'protocol_variant': 'FT2_DECODIUM',
    'decodium_udp_connected': True,
    'decodium_accept_commands': True,
    'tx_enabled_by_operator': True,
    'frequency_is_allowed': True,
    'user_confirmed_tx': True,
}
_DECODE = {'time_ms': 43200000, 'snr': -10, 'dt': 0.2, 'delta_hz': 1500,
           'mode': 'FT2', 'message': 'F4GLD F5ABC JN18'}


class FauxSock:
    def __init__(self):
        self.envois = []

    def sendto(self, data, addr):
        self.envois.append((bytes(data), addr))


def test_garde_ok_si_tout_est_vrai():
    assert ft2.can_send_ft2_reply(_VALID) == (True, '')


def test_garde_refuse_chaque_condition_manquante():
    motifs = {
        'protocol_variant': 'compatible',
        'decodium_udp_connected': 'indisponible',
        'decodium_accept_commands': 'commandes externes',
        'tx_enabled_by_operator': 'désactivée',
        'frequency_is_allowed': 'Fréquence',
        'user_confirmed_tx': 'Confirmation',
    }
    for cle, motif in motifs.items():
        ctx = dict(_VALID)
        ctx[cle] = '' if cle == 'protocol_variant' else False
        ok, raison = ft2.can_send_ft2_reply(ctx)
        assert ok is False and motif in raison, (cle, raison)


def test_garde_contexte_non_dict():
    assert ft2.can_send_ft2_reply(None)[0] is False


def test_reply_envoye_uniquement_si_garde_ok():
    s = FauxSock()
    ok, _ = ft2.envoyer_reply_decodium(s, _DECODE, 'Decodium', ('192.168.1.50', 2237), _VALID)
    assert ok is True and len(s.envois) == 1
    assert s.envois[0][1] == ('192.168.1.50', 2237)          # vers l'adresse émettrice


def test_reply_bloque_si_garde_echoue_rien_envoye():
    s = FauxSock()
    ctx = dict(_VALID, user_confirmed_tx=False)              # pas de confirmation
    ok, raison = ft2.envoyer_reply_decodium(s, _DECODE, 'Decodium', ('192.168.1.50', 2237), ctx)
    assert ok is False and 'Confirmation' in raison
    assert s.envois == []                                    # RIEN émis


def test_reply_bloque_sans_adresse():
    s = FauxSock()
    ok, _ = ft2.envoyer_reply_decodium(s, _DECODE, 'Decodium', None, _VALID)
    assert ok is False and not s.envois


def test_halt_tx_toujours_envoye_meme_sans_garde():
    s = FauxSock()
    ok, _ = ft2.envoyer_halt_tx_decodium(s, 'Decodium', ('192.168.1.50', 2237))
    assert ok is True and len(s.envois) == 1                 # coupe-circuit non gardé
