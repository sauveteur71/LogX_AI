# -*- coding: utf-8 -*-
"""Hygiène mémoire — les caches d'indicatifs (callbook, qrz) croissaient sans
borne : un serveur station laissé tourner des jours (scénario zone blanche)
accumule une entrée par indicatif jamais purgée. On plafonne + évince les plus
anciennes."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_callbook as cb
import logx_qrz as qrz


def test_callbook_cache_est_borne():
    cb._cache.clear()
    for i in range(cb.CACHE_MAX + 500):
        cb._mettre_en_cache('CALL%d' % i, {'x': i})
    assert len(cb._cache) <= cb.CACHE_MAX, \
        f"_cache non borné ({len(cb._cache)} > {cb.CACHE_MAX})"


def test_qrz_lookup_cache_est_borne():
    qrz._lookup_cache.clear()
    for i in range(qrz.LOOKUP_MAX + 500):
        qrz._mettre_en_cache('CALL%d' % i, {'x': i})
    assert len(qrz._lookup_cache) <= qrz.LOOKUP_MAX, \
        f"_lookup_cache non borné ({len(qrz._lookup_cache)} > {qrz.LOOKUP_MAX})"
