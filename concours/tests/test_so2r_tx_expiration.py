# -*- coding: utf-8 -*-
"""Cohérence de l'expiration du verrou TX (audit BASSE 765/766).

verrouiller_tx() traite un verrou PÉRIMÉ (âge >= TX_LOCK_TIMEOUT_S) comme LIBRE
et se laisse re-prendre par n'importe quelle radio. Mais tx_actif() rapportait
`_tx_radio` tel quel, SANS appliquer cette expiration : /so2r/state affichait une
radio « en émission » alors que le verrou était en réalité relâché, et surtout
logx_http /rig/stop lit `so2r.tx_actif()['radio']` pour CIBLER la radio du STOP
matériel — un verrou périmé détournait donc le STOP vers la mauvaise radio au
lieu du focus courant.

reinitialiser() remettait _tx_radio et _tx_armee_a à zéro mais laissait
_tx_source à son ancienne valeur (état incohérent : une source sans verrou).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_so2r as so2r


def _reset():
    so2r.reinitialiser()


def test_tx_actif_verrou_frais_rapporte_la_radio():
    _reset()
    assert so2r.verrouiller_tx(1, 'cw')['ok'] is True
    assert so2r.tx_actif()['radio'] == 1   # témoin : verrou frais = actif


def test_tx_actif_verrou_expire_rapporte_libre():
    _reset()
    assert so2r.verrouiller_tx(1, 'cw')['ok'] is True
    # Simule un verrou périmé : armé il y a plus de TX_LOCK_TIMEOUT_S.
    so2r._tx_armee_a = time.monotonic() - (so2r.TX_LOCK_TIMEOUT_S + 5)
    assert so2r.tx_actif()['radio'] is None, \
        "un verrou périmé doit être rapporté LIBRE (comme verrouiller_tx le traite)"


def test_reinitialiser_efface_tx_source():
    _reset()
    assert so2r.verrouiller_tx(1, 'cw')['ok'] is True
    so2r.reinitialiser()
    assert so2r._tx_source == '', "reinitialiser() doit remettre _tx_source à vide"
