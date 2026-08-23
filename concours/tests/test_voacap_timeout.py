# -*- coding: utf-8 -*-
"""predict() doit transformer un timeout VOACAP en dict d'erreur propre.

Toutes les branches d'échec de predict() renvoient {'ok': False, 'error': ...}.
Mais subprocess.run() est appelé avec timeout=... (le paramètre existe
PRÉCISÉMENT pour un voacapl.exe bloqué), et le bloc est un `with _lock: try /
finally` SANS except : à l'échéance, subprocess.TimeoutExpired traverse predict()
et remonte à l'appelant (route/expédition 24h/24 qui plante) au lieu de produire
l'erreur propre attendue.

Correctif : except subprocess.TimeoutExpired -> {'ok': False, 'error': ...}.
"""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_voacap as vc  # noqa: E402


def test_timeout_devient_une_erreur_propre(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, 'voacap_available', lambda: True)
    monkeypatch.setattr(vc, '_RUN_DIR', str(tmp_path))

    def _run_qui_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd='voacapl', timeout=k.get('timeout', 60))
    monkeypatch.setattr(vc.subprocess, 'run', _run_qui_timeout)

    r = vc.predict(48.8, 2.3, 40.7, -74.0, month=1, year=2026, ssn=50,
                   freqs_mhz=[14.1], timeout=1)
    assert isinstance(r, dict) and r.get('ok') is False, r
    assert 'délai' in r['error'].lower() or 'delai' in r['error'].lower(), r
