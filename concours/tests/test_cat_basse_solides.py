# -*- coding: utf-8 -*-
"""Deux vrais correctifs SOLIDES issus de l'audit BASSE (lignes 587 et 588).

1) logx_cat.py get_smeter (Icom) : `int(f'{b0:02x}{b1:02x}')` décode le S-mètre
   comme du BCD en base 10. Un octet NON-BCD (un quartet A-F, ex. 0x5A -> "5a")
   fait lever ValueError par int(), ce qui ROMPT le contrat « jamais
   d'exception, retourne {'ok': False} » que get_freq()/identify() respectent.
   Une trame parasite sur un bus CI-V partagé suffit à le déclencher.

2) logx_cat.py RigManager.add() : réenregistrer un radio_id déjà présent
   écrasait l'entrée sans fermer l'ancien transport -> fuite de port série
   (remove() ferme pourtant bien le transport).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_cat as cat


def _swap(frame, addr_dest, addr_src):
    if len(frame) < 4:
        return frame
    return frame[:2] + bytes([addr_dest, addr_src]) + frame[4:]


class _SmeterFake:
    """Radio Icom fictive dont la réponse S-mètre porte les octets DATA fournis
    (utile pour injecter un octet non-BCD)."""

    def __init__(self, addr, smeter_bytes):
        self.addr = addr
        self._smeter = bytes(smeter_bytes)
        self._pending = b''

    def write(self, data):
        parsed = cat.civ_parse_frame(data)
        if not parsed or parsed[0] != self.addr:
            self._pending = b''
            return
        _, _, cmd, sub, _ = parsed
        if cmd == 0x15 and sub == 0x02:
            self._pending = _swap(
                cat.civ_build_frame(0xE0, 0x15, sub=0x02, data=self._smeter), 0xE0, self.addr)
        else:
            self._pending = b''

    def read_until(self, terminator, timeout=1.0):
        r, self._pending = self._pending, b''
        return r

    def close(self):
        pass


def test_smeter_octet_non_bcd_ne_leve_pas_dexception():
    # 0x0A 0xB0 -> "0a" "b0" -> int("0ab0", base 10) lèverait ValueError.
    radio = cat.CivRadio(_SmeterFake(0x94, [0x0A, 0xB0]), 0x94)
    sm = radio.get_smeter()  # ne doit PAS lever
    assert sm['ok'] is False, "un octet non-BCD doit rendre ok:False, pas planter"


def test_smeter_bcd_valide_reste_correct():
    # 01 20 BCD -> "0120" -> 120 (garde le comportement nominal).
    radio = cat.CivRadio(_SmeterFake(0x94, [0x01, 0x20]), 0x94)
    sm = radio.get_smeter()
    assert sm['ok'] is True and sm['raw'] == 120


class _CloseTracker:
    """Transport fictif qui note s'il a été fermé."""

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_rigmanager_add_ferme_l_ancien_transport_sur_meme_id():
    mgr = cat.RigManager()
    t1 = _CloseTracker()
    t2 = _CloseTracker()
    mgr.add('rig1', t1, 'civ', addr=0x94)
    mgr.add('rig1', t2, 'civ', addr=0x94)   # réenregistrement du même id
    assert t1.closed is True, "l'ancien transport doit être fermé (sinon fuite de port série)"
    assert t2.closed is False, "le nouveau transport reste ouvert"
