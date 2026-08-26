# -*- coding: utf-8 -*-
"""Audit : where_heard renvoyait le dict mutable PARTAGÉ du cache — un appelant
qui le mute corrompait le cache pour les appels suivants. On renvoie une copie."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_rbn as rbn


def test_where_heard_renvoie_une_copie_du_cache():
    rbn._cache['data'] = {'ok': True, 'call': 'F4TEST', 'spots': [{'snr': 10}]}
    rbn._cache['call'] = 'F4TEST'
    rbn._cache['ts'] = time.time()
    r1 = rbn.where_heard('F4TEST')      # cache hit (pas de réseau)
    r1['ok'] = False
    r1['spots'].append({'snr': 999})    # l'appelant mute son résultat
    r2 = rbn.where_heard('F4TEST')      # cache hit à nouveau
    assert r2['ok'] is True, "le cache a été corrompu par la mutation de l'appelant"
    assert len(r2['spots']) == 1
