# -*- coding: utf-8 -*-
"""activation_state() comptait comme P2P (Park-to-Park…) TOUT QSO à sig_info non
vide, sans vérifier le champ ADIF 'sig' (programme du correspondant).

Un correspondant actif dans un AUTRE programme (un SOTA travaillé pendant une
activation POTA : sig='SOTA', sig_info='F/AB-001') était compté et étiqueté
'Park-to-Park', ce qui est faux : un P2P POTA exige que l'autre station soit
AUSSI en parc POTA. Correctif conservateur : P2P seulement si 'sig' est absent
(beaucoup d'ADIF ne remplissent que sig_info — cas courant, toléré) OU égal au
programme de l'activation. Un 'sig' présent et différent n'est pas un P2P.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_activation as act  # noqa: E402


def _log():
    # tous portent ma référence d'activation (my_sig_info) ; pas de champ 'date'
    # -> pas de filtrage jour. Le correspondant varie par 'sig'.
    return [
        {'call': 'A', 'my_sig_info': 'FR-0123', 'sig': 'POTA', 'sig_info': 'FR-0002'},
        {'call': 'B', 'my_sig_info': 'FR-0123', 'sig': 'SOTA', 'sig_info': 'F/AB-001'},
        {'call': 'C', 'my_sig_info': 'FR-0123', 'sig_info': 'FR-0003'},  # sig absent -> toléré
    ]


def test_p2p_exclut_un_correspondant_d_un_autre_programme():
    st = act.activation_state(_log(), 'POTA', 'FR-0123')
    refs = {p['ref'] for p in st['p2p']}
    assert st['p2p_count'] == 2, "le SOTA travaillé pendant l'activation POTA ne doit pas compter P2P"
    assert 'FR-0002' in refs          # même programme -> P2P
    assert 'FR-0003' in refs          # sig absent -> toléré
    assert 'F/AB-001' not in refs     # autre programme -> exclu
