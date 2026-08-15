# -*- coding: utf-8 -*-
"""Tests de fetch_noaa_kindex() (logx_clusters.py) — indice planétaire K
NOAA/SWPC (services.swpc.noaa.gov/products/noaa-planetary-k-index.json).

Format RÉEL vérifié en direct le 14/08/2026 (WebFetch de l'endpoint) : une
liste d'OBJETS {"time_tag": "...", "Kp": <float>, "a_running": <int>,
"station_count": <int>}. L'ancien code visait un format tableau
[[time_tag, Kp], ...] avec une ligne d'en-tête textuelle — NOAA l'a
abandonné. Sur le format actuel, `entry[1]` sur un dict lève un KeyError,
avalé par le `except: pass` interne : k_values restait TOUJOURS vide et la
fonction renvoyait None en silence, quel que soit l'indice K réel."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json

import logx_clusters as clusters


# ─── Échantillon réaliste (mêmes champs qu'une réponse réelle capturée) ──────
_SAMPLE_RESPONSE = json.dumps([
    {"time_tag": "2026-08-13T18:00:00", "Kp": 1.67, "a_running": 6, "station_count": 8},
    {"time_tag": "2026-08-13T21:00:00", "Kp": 2.33, "a_running": 9, "station_count": 8},
    {"time_tag": "2026-08-14T00:00:00", "Kp": 5.33, "a_running": 32, "station_count": 8},
])


def _stub_fetch_url(monkeypatch, content):
    monkeypatch.setattr(clusters, 'fetch_url', lambda *a, **k: content)


def test_fetch_noaa_kindex_parse_le_format_objet_actuel(monkeypatch):
    """Défaut réel : sur le nouveau format NOAA (liste d'objets), l'ancien
    parseur renvoyait toujours None. Ici la dernière valeur Kp=5.33 doit
    ressortir, et le max sur les 3 dernières entrées aussi."""
    _stub_fetch_url(monkeypatch, _SAMPLE_RESPONSE)
    r = clusters.fetch_noaa_kindex()
    assert r is not None
    assert r['k_index'] == 5.33
    assert r['k_max_3h'] == 5.33


def test_fetch_noaa_kindex_detecte_l_aurore(monkeypatch):
    _stub_fetch_url(monkeypatch, _SAMPLE_RESPONSE)
    r = clusters.fetch_noaa_kindex()
    assert r['aurora_possible'] is True  # K=5.33 >= 5


def test_fetch_noaa_kindex_calme_pas_d_aurore(monkeypatch):
    content = json.dumps([
        {"time_tag": "2026-08-14T00:00:00", "Kp": 1.0, "a_running": 4, "station_count": 8},
    ])
    _stub_fetch_url(monkeypatch, content)
    r = clusters.fetch_noaa_kindex()
    assert r['aurora_possible'] is False
    assert r['k_index'] == 1.0


def test_fetch_noaa_kindex_reseau_indisponible(monkeypatch):
    _stub_fetch_url(monkeypatch, None)
    assert clusters.fetch_noaa_kindex() is None


def test_fetch_noaa_kindex_reponse_vide_ne_plante_pas(monkeypatch):
    _stub_fetch_url(monkeypatch, "[]")
    assert clusters.fetch_noaa_kindex() is None


def test_fetch_noaa_kindex_ancien_format_tableau_ne_fait_plus_planter(monkeypatch):
    """Filet de sécurité : si NOAA revenait un jour à l'ancien format
    tableau (ou si un autre miroir le sert encore), le parseur ne doit ni
    planter ni faire remonter n'importe quoi -- juste ignorer ces entrées,
    puisqu'elles ne sont pas des dicts avec une clé 'Kp'."""
    content = json.dumps([["time_tag", "Kp"], ["2026-08-14 00:00:00", "3.33"]])
    _stub_fetch_url(monkeypatch, content)
    assert clusters.fetch_noaa_kindex() is None


def test_fetch_noaa_kindex_utilise_https():
    import inspect
    src = inspect.getsource(clusters.fetch_noaa_kindex)
    assert 'https://services.swpc.noaa.gov' in src
    assert 'http://services.swpc.noaa.gov' not in src
