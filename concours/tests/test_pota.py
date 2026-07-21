# -*- coding: utf-8 -*-
"""Spots d'activateurs POTA (logx_pota) — sans réseau, fetch_url mocké."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_pota as pota

SAMPLE = [{
    'spotId': 53769145, 'activator': '9A/DF5WC', 'frequency': '10115', 'mode': 'CW',
    'reference': 'HR-0139', 'parkName': None, 'spotTime': '2026-07-21T05:50:58',
    'spotter': '9A/DF5WC', 'comments': 'QRT', 'source': 'Ham2K Portable Logger',
    'invalid': None, 'name': 'Otok Rab Natura 2000', 'locationDesc': 'HR-PG',
    'grid4': 'JN74', 'grid6': 'JN74js', 'latitude': 44.7772, 'longitude': 14.7569,
    'count': 5, 'expire': 343,
}]


def test_fetch_pota_spots_mappe_les_champs(monkeypatch):
    def fake_fetch(url, timeout=10):
        assert url == pota.POTA_SPOTS_URL
        return json.dumps(SAMPLE)
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)
    pota._cache.update(data=None, ts=0)

    spots = pota.fetch_pota_spots()
    assert len(spots) == 1
    s = spots[0]
    assert s['call'] == '9A/DF5WC'
    assert s['reference'] == 'HR-0139'
    assert s['mode'] == 'CW'
    assert s['freq'] == 10115.0
    assert s['band'] == '10.1'         # 10.115 MHz -> bande 30 m (WARC)
    assert s['grid'] == 'JN74js'
    assert s['park_name'] == 'Otok Rab Natura 2000'
    assert s['source'] == 'pota'


def test_cache_reutilise_sans_re_fetch(monkeypatch):
    calls = {'n': 0}
    def fake_fetch(url, timeout=10):
        calls['n'] += 1
        return json.dumps(SAMPLE)
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)
    pota._cache.update(data=None, ts=0)

    pota.fetch_pota_spots()
    pota.fetch_pota_spots()
    assert calls['n'] == 1   # 2e appel servi depuis le cache (TTL 90 s)


def test_reseau_indisponible_retombe_sur_liste_vide(monkeypatch):
    def fake_fetch(url, timeout=10):
        return None
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)
    pota._cache.update(data=None, ts=0)

    assert pota.fetch_pota_spots() == []


def test_json_invalide_ne_leve_jamais(monkeypatch):
    def fake_fetch(url, timeout=10):
        return 'pas du json'
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)
    pota._cache.update(data=None, ts=0)

    assert pota.fetch_pota_spots() == []
