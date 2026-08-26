# -*- coding: utf-8 -*-
"""Maillon copilote 4 — résumé À VIE des activations/chasses par programme
(POTA/SOTA/IOTA/WWFF...). Agrégation pure du log : my_sig_info = activé (ma réf),
sig_info = chassé (la réf de l'activateur d'en face). Références UNIQUES."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_activation as activation


def test_compte_references_uniques_activees_et_chassees():
    log = [
        {'my_sig': 'POTA', 'my_sig_info': 'FR-0123'},
        {'my_sig': 'POTA', 'my_sig_info': 'FR-0123'},   # doublon -> 1 unique
        {'my_sig': 'pota', 'my_sig_info': 'FR-0456'},   # casse tolérée
        {'sig': 'POTA', 'sig_info': 'US-1111'},          # chassé
        {'sig': 'SOTA', 'sig_info': 'F/AB-001'},         # chassé SOTA
        {'call': 'X'},                                    # QSO ordinaire
    ]
    s = activation.activation_summary(log)
    assert s['POTA']['activated'] == 2 and s['POTA']['hunted'] == 1
    assert s['POTA']['activated_refs'] == ['FR-0123', 'FR-0456']   # triées, uniques
    assert s['POTA']['hunted_refs'] == ['US-1111']
    assert s['SOTA'] == {'activated': 0, 'hunted': 1,
                         'activated_refs': [], 'hunted_refs': ['F/AB-001']}
    assert 'IOTA' not in s   # aucun programme sans activité


def test_log_vide_ou_none():
    assert activation.activation_summary([]) == {}
    assert activation.activation_summary(None) == {}


def test_ref_vide_ignoree():
    # my_sig présent mais my_sig_info vide (hors activation) -> pas compté.
    s = activation.activation_summary([{'my_sig': 'POTA', 'my_sig_info': ''}])
    assert s == {}
