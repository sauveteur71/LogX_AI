# -*- coding: utf-8 -*-
"""Balayage performance — hot paths (audit).

1. logx_tci._hann_window : la fenêtre de Hann (4096 pts) était RECALCULÉE à
   chaque tci_compute_fft_line (poll panadapter ~500 ms). Mémoïsée par n.
2. logx_lan_sync._my_iid : relisait l'identifiant machine sur DISQUE
   (cloudsync._instance_id) à CHAQUE paquet UDP reçu (note_beacon) — coût
   inutile + surface d'amplification sous flood broadcast. Mis en cache.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_tci as tci
import logx_lan_sync as lan
import logx_cloudsync as cs


def test_hann_window_est_memoise():
    assert tci._hann_window(64) is tci._hann_window(64), \
        "la fenêtre de Hann doit être mémoïsée (pas recalculée à chaque appel)"


def test_hann_window_valeurs_preservees():
    w = tci._hann_window(8)
    assert abs(w[0]) < 1e-9 and abs(w[-1]) < 1e-9   # extrémités nulles
    assert abs(w[len(w) // 2] - 1.0) < 0.2           # ~1 au centre


def test_my_iid_ne_lit_le_disque_qu_une_fois(monkeypatch):
    lan._MY_IID[0] = None   # réinitialise le cache pour ce test
    appels = []
    monkeypatch.setattr(cs, '_instance_id', lambda: appels.append(1) or 'IID-XYZ')
    a = lan._my_iid()
    b = lan._my_iid()
    assert a == b == 'IID-XYZ'
    assert len(appels) == 1, "_instance_id doit être lu une seule fois (pas par paquet)"
