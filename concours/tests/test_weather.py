# -*- coding: utf-8 -*-
"""Tests météo — codes WMO, seuils d'alerte matériel (sans réseau)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import radiocontest_weather as weather


def test_codes_wmo():
    assert weather.WMO[0][0] == 'Ciel clair'
    assert weather.WMO[95][0] == 'Orage'


def test_pas_de_coords():
    r = weather.get_weather(None, None)
    assert not r['ok']


def test_seuils_alerte(monkeypatch):
    """Rafales fortes / orage / gel → alerte matériel."""
    def fake_fetch(url, timeout=15):
        import json
        return json.dumps({'current': {'temperature_2m': 18, 'wind_speed_10m': 20,
                           'wind_gusts_10m': 65, 'precipitation': 0, 'weather_code': 3}})
    import radiocontest_utils
    monkeypatch.setattr(radiocontest_utils, 'fetch_url', fake_fetch)
    weather._cache.update(ts=0, data=None, key='')
    r = weather.get_weather(45.1, 3.9)
    assert r['ok'] and 'RAFALES' in r['warn'] and r['gust'] == 65


def test_orage_alerte(monkeypatch):
    def fake_fetch(url, timeout=15):
        import json
        return json.dumps({'current': {'temperature_2m': 20, 'wind_speed_10m': 10,
                           'wind_gusts_10m': 15, 'precipitation': 5, 'weather_code': 95}})
    import radiocontest_utils
    monkeypatch.setattr(radiocontest_utils, 'fetch_url', fake_fetch)
    weather._cache.update(ts=0, data=None, key='')
    r = weather.get_weather(45.1, 3.9)
    assert 'ORAGE' in r['warn']


def test_orage_pas_masque_par_rafales(monkeypatch):
    """Bug revue : un orage avec rafales 45 km/h doit garder l'alerte foudre."""
    def fake_fetch(url, timeout=15):
        import json
        return json.dumps({'current': {'temperature_2m': 18, 'wind_speed_10m': 30,
                           'wind_gusts_10m': 45, 'precipitation': 8, 'weather_code': 95}})
    import radiocontest_utils
    monkeypatch.setattr(radiocontest_utils, 'fetch_url', fake_fetch)
    weather._cache.update(ts=0, data=None, key='')
    r = weather.get_weather(45.1, 3.9)
    assert 'ORAGE' in r['warn'] and '45' in r['warn']


def test_valeur_null_ne_plante_pas(monkeypatch):
    """Bug revue : un champ présent mais null ne doit pas planter (round(None))."""
    def fake_fetch(url, timeout=15):
        import json
        return json.dumps({'current': {'temperature_2m': None, 'wind_speed_10m': None,
                           'wind_gusts_10m': None, 'precipitation': None, 'weather_code': None}})
    import radiocontest_utils
    monkeypatch.setattr(radiocontest_utils, 'fetch_url', fake_fetch)
    weather._cache.update(ts=0, data=None, key='')
    r = weather.get_weather(45.1, 3.9)
    assert r['ok'] and r['temp'] == 0 and r['gust'] == 0
