# -*- coding: utf-8 -*-
"""set_freq() ignore le RPRT de la commande de mode (logx_rig.py) — Strate 2, haute.

set_freq() vérifiait le RPRT de la commande de FRÉQUENCE (F ...) mais lançait la
commande de MODE (M {mode} 0) sans regarder son RPRT : un mode refusé par la
radio (M ... -> RPRT != 0) était rapporté comme succès. L'opérateur croyait
émettre dans le bon mode alors que le poste avait refusé le changement.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_rig as rig   # noqa: E402


def _fake(monkeypatch, mode_reply):
    def fake_command(host, port, cmd, _retry=True):
        if cmd.startswith('F '):
            return ['RPRT 0']              # fréquence acceptée
        if cmd.startswith('M '):
            return mode_reply              # réponse de la commande de mode
        return ['RPRT 0']
    monkeypatch.setattr(rig, '_command', fake_command)


def test_set_freq_signale_un_mode_refuse(monkeypatch):
    _fake(monkeypatch, ['RPRT -1'])        # mode refusé par la radio
    r = rig.set_freq('h', 1, 14074000, mode='USB')
    assert r.get('ok') is False, "un mode refusé (RPRT != 0) ne doit pas être rapporté comme succès"


def test_set_freq_ok_quand_mode_accepte(monkeypatch):
    _fake(monkeypatch, ['RPRT 0'])         # mode accepté
    r = rig.set_freq('h', 1, 14074000, mode='USB')
    assert r.get('ok') is True
