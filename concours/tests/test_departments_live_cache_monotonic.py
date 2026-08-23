# -*- coding: utf-8 -*-
"""Le cache d'échecs de lookup en direct (_live_fail_cache) doit être horodaté
avec time.monotonic(), pas time.time().

time.time() est l'horloge murale : sur un portable d'expédition (pas d'Internet
puis resync NTP/GPS), un PAS ARRIÈRE de l'horloge rend `now - last_fail`
négatif, donc `< LIVE_FAIL_RETRY_S` reste vrai et l'indicatif fautif est sauté
bien au-delà des 15 min prévues — la résolution en direct est silencieusement
désactivée. Le reste du module (_dept_polys_last_try) utilise déjà monotonic
avec un commentaire qui bannit précisément l'horloge murale.
"""
import os
import sys
import time

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_departments as dep  # noqa: E402


def test_live_fail_cache_utilise_monotonic_pas_wall_clock(monkeypatch):
    used = {'time': 0, 'monotonic': 0}
    monkeypatch.setattr(time, 'time',
                        lambda: (used.__setitem__('time', used['time'] + 1) or 9.99e11))
    monkeypatch.setattr(time, 'monotonic',
                        lambda: (used.__setitem__('monotonic', used['monotonic'] + 1) or 1000.0))
    # lookup qui échoue -> branche else -> écriture du cache avec `now`
    import logx_callbook
    monkeypatch.setattr(logx_callbook, 'lookup', lambda call, cfg: {'ok': False})
    monkeypatch.setattr(dep, '_live_fail_cache', {})

    dep._resolve_spotted_live(['F5XYZ'], set(), cfg={})

    assert used['monotonic'] > 0, "la fonction doit lire time.monotonic()"
    assert used['time'] == 0, "la fonction ne doit PAS lire l'horloge murale time.time()"
