# -*- coding: utf-8 -*-
"""_FETCH_PENDING ne doit pas être corrompu par les callbacks des futures de
l'ANCIEN pool après un swap.

Au swap de pool (8 workers bloqués), _FETCH_PENDING est remis à 0, mais les
futures encore en vol sur l'ancien pool portent un callback qui décrémente le
MÊME compteur global. En se terminant plus tard, elles décrémentent le compteur
du NOUVEAU pool -> il ne reflète plus les tâches réelles et un futur swap ne se
déclenche jamais (compteur coincé sous le seuil).

Correctif : une GÉNÉRATION de pool ; le callback ne décrémente que le compteur
de SA génération.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_utils as u  # noqa: E402


def test_callback_ancienne_generation_ne_decremente_pas():
    with u._FETCH_LOCK:
        u._FETCH_GEN = 5
        u._FETCH_PENDING = 1
    u._dec_fetch_pending(4)          # future de l'ancien pool (gén. 4) -> ignorée
    assert u._FETCH_PENDING == 1, "un callback d'ancienne génération a corrompu le compteur"
    u._dec_fetch_pending(5)          # génération courante -> décrémente
    assert u._FETCH_PENDING == 0
