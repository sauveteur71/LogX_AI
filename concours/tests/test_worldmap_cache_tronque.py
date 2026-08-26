# -*- coding: utf-8 -*-
"""Carte monde — le cache disque doit subir la MÊME validation que le
téléchargement (audit STRATE-3 logx_worldmap.py:34). Avant : le chemin de
lecture disque rendait le fichier TEL QUEL, sans le contrôle
`len > 100000 and 'FeatureCollection'` appliqué au téléchargement -> un cache
TRONQUÉ (write partiel après un crash, vieux mauvais téléchargement) était servi
À VIE, sans jamais se revalider ni se re-télécharger."""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_worldmap as wm   # noqa: E402

_VALIDE = '{"type":"FeatureCollection","features":[]}' + ' ' * 100001  # > seuil


def test_cache_tronque_nest_pas_servi_et_est_re_telecharge(monkeypatch, tmp_path):
    cache = str(tmp_path / 'world_countries.geojson')
    monkeypatch.setattr(wm, 'WORLD_GEOJSON_FILE', cache)
    # cache TRONQUÉ (trop court pour être un vrai geojson mondial)
    with open(cache, 'w', encoding='utf-8') as f:
        f.write('{"type":"FeatureCollection","features":[')   # coupé net
    import logx_utils as utils
    monkeypatch.setattr(utils, 'fetch_url', lambda url, timeout=30: _VALIDE)
    res = wm.load_world_geojson()
    # On ne sert PAS le cache tronqué : on re-télécharge la version valide.
    assert res == _VALIDE


def test_cache_tronque_sans_reseau_ne_sert_pas_de_donnee_cassee(monkeypatch, tmp_path):
    cache = str(tmp_path / 'world_countries.geojson')
    monkeypatch.setattr(wm, 'WORLD_GEOJSON_FILE', cache)
    with open(cache, 'w', encoding='utf-8') as f:
        f.write('tronqué')
    import logx_utils as utils
    monkeypatch.setattr(utils, 'fetch_url', lambda url, timeout=30: '')  # hors ligne
    # Plutôt que de servir un cache cassé, on rend '' (indisponible) — l'appelant
    # dégrade proprement (carte vide) au lieu d'afficher une carte tronquée à vie.
    assert wm.load_world_geojson() == ''


def test_cache_valide_est_servi_directement(monkeypatch, tmp_path):
    cache = str(tmp_path / 'world_countries.geojson')
    monkeypatch.setattr(wm, 'WORLD_GEOJSON_FILE', cache)
    with open(cache, 'w', encoding='utf-8') as f:
        f.write(_VALIDE)
    import logx_utils as utils
    # fetch_url ne DOIT pas être appelé (cache valide) : on le fait exploser.
    monkeypatch.setattr(utils, 'fetch_url',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('ne pas télécharger')))
    assert wm.load_world_geojson() == _VALIDE
