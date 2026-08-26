# -*- coding: utf-8 -*-
"""coach_i18n.t() promet « ne lève jamais » (docstring) mais n'attrapait que
(KeyError, IndexError, ValueError) — un paramètre None passé à un spec de
format numérique (ex. '{n:d}') lève TypeError, non attrapé : t() levait alors,
en violation de son contrat (audit STRATE-3 logx_coach_i18n.py:440)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_coach_i18n as ci


def test_t_ne_leve_pas_sur_param_none_avec_spec_numerique(monkeypatch):
    # '{n:d}'.format(n=None) lève TypeError — t() ne doit PAS le laisser remonter.
    monkeypatch.setitem(ci._FR, 'test_typeerror', 'Score {n:d} pts')
    result = ci.t('fr', 'test_typeerror', n=None)
    assert isinstance(result, str)   # a renvoyé quelque chose au lieu de lever


def test_t_formate_normalement_quand_les_params_sont_bons(monkeypatch):
    monkeypatch.setitem(ci._FR, 'test_ok', 'Score {n:d} pts')
    assert ci.t('fr', 'test_ok', n=42) == 'Score 42 pts'
