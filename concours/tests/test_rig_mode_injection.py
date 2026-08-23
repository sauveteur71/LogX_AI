# -*- coding: utf-8 -*-
"""Injection de commandes rigctld via set_freq(mode=...) — Strate 1, CRITIQUE.

Le protocole rigctld sépare les commandes par '\\n'. set_freq() interpolait
`mode` brut dans `M {mode} 0` : un mode contenant un saut de ligne
(ex. 'CW 500\\nT 1') faisait exécuter à la radio une commande supplémentaire —
'T 1' = PTT ON = ÉMISSION non demandée, ou 'F ...' = QSY. C'est exactement
l'injection que send_morse() neutralise déjà dans le même fichier (l.188-189).

Ce test capture les commandes réellement envoyées à _command et exige qu'aucune
ne contienne de séparateur '\\n' ni de commande PTT injectée. Il ne touche pas
à une vraie radio (rigctld mocké). ⚠️ L'essai réel sur l'air reste à faire par
F4GLD en supervisé — aucun test ne peut prouver le comportement d'une vraie
station.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_rig as rig  # noqa: E402


def _capture(monkeypatch):
    sent = []

    def fake_command(host, port, cmd, _retry=True):
        sent.append(cmd)
        return ['RPRT 0']

    monkeypatch.setattr(rig, '_command', fake_command)
    return sent


def test_set_freq_neutralise_l_injection_par_saut_de_ligne(monkeypatch):
    sent = _capture(monkeypatch)
    rig.set_freq('h', 1, 14000000, mode='CW 500\nT 1')
    assert all('\n' not in c and '\r' not in c for c in sent), (
        "injection : une commande envoyée à rigctld contient un séparateur : %r" % sent
    )
    assert not any(c.strip() == 'T 1' or c.strip() == 'T 0' for c in sent), (
        "injection : une commande PTT a été injectée via le mode : %r" % sent
    )


def test_set_freq_mode_normal_fonctionne(monkeypatch):
    sent = _capture(monkeypatch)
    r = rig.set_freq('h', 1, 14074000, mode='USB')
    assert r.get('ok') is True
    # la fréquence et le mode doivent bien être transmis
    assert any(c.startswith('F 14074000') for c in sent), sent
    assert any(c.startswith('M USB') for c in sent), sent
