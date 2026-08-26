# -*- coding: utf-8 -*-
"""Audit : build_coach_state appelait department_mult_count SANS garde, alors
que build_debrief la garde -> un échec de cette fonction faisait tomber TOUT
l'état du coach (et /coach/state). Même garde ajoutée."""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_coach as coach
import logx_departments as departments

NOW = datetime.datetime(2026, 1, 10, 12, 0)


def test_build_coach_state_survit_a_department_mult_count_qui_leve(monkeypatch):
    monkeypatch.setattr(departments, 'department_mult_count',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom')))
    log = [{'date': '20260110', 'time': '11:00', 'band': '160', 'points': 1, 'contest': 'REF_160M'}]
    cfg = {'contest': 'REF_160M', 'contest_start_date': '20260110'}
    st = coach.build_coach_state(cfg, log, now=NOW)   # ne doit PAS lever
    assert isinstance(st, dict)
    assert 'departments' not in st.get('stats', {}) or st['stats'].get('departments') is None
