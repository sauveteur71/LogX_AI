# -*- coding: utf-8 -*-
"""Fausse alerte GEL quand la température est absente (logx_weather.py) — Strate 2, haute.

Le helper num() de get_weather() replie toute valeur absente ou null sur 0.
C'est correct pour le vent/les rafales/les précipitations (0 = défaut sûr) mais
FAUX pour la température : `if temp <= 0` déclenchait alors « ❄️ Gel » dès que
open-meteo ne renvoyait pas de température (champ absent ou null), une fausse
alerte matériel. Ce test exige qu'une température absente/null ne déclenche PAS
le gel, et qu'une vraie température négative le déclenche toujours.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_weather as w   # noqa: E402
import logx_utils         # noqa: E402


def _reset_cache():
    w._cache.update(data=None, key=None, ts=0)


def _patch(monkeypatch, payload):
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda url, timeout=15: payload)


def test_temperature_absente_pas_de_gel(monkeypatch):
    _reset_cache()
    _patch(monkeypatch, '{"current": {"weather_code": 3, "wind_speed_10m": 10}}')
    d = w.get_weather(45.00, 5.00)
    assert d.get('ok') is True
    assert 'Gel' not in d.get('warn', ''), d.get('warn')


def test_temperature_null_pas_de_gel(monkeypatch):
    _reset_cache()
    _patch(monkeypatch, '{"current": {"weather_code": 3, "temperature_2m": null, "wind_speed_10m": 10}}')
    d = w.get_weather(45.10, 5.10)
    assert 'Gel' not in d.get('warn', ''), d.get('warn')


def test_temperature_negative_declenche_le_gel(monkeypatch):
    _reset_cache()
    _patch(monkeypatch, '{"current": {"weather_code": 3, "temperature_2m": -3.2, "wind_speed_10m": 5}}')
    d = w.get_weather(45.20, 5.20)
    assert 'Gel' in d.get('warn', ''), d.get('warn')
