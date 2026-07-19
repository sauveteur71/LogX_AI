# -*- coding: utf-8 -*-
"""Tests de la carte monde par pays DXCC (radiocontest_worldmap) : GeoJSON
mis en cache disque (comme la carte des départements), association entité
DXCC -> polygone par point-dans-polygone (pas de table manuelle), et calcul
travaillé/non par pays."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import radiocontest_worldmap as wm

# Deux pays rectangulaires simples (pas de vraies frontières, juste pour tester
# la géométrie) : "Testland" (0,0)-(10,10) et "Otherland" (20,0)-(30,10).
FAKE_GEOJSON = json.dumps({
    'type': 'FeatureCollection',
    'features': [
        {'type': 'Feature',
         'properties': {'ISO_A3': 'TST', 'NAME': 'Testland', 'CONTINENT': 'Europe'},
         'geometry': {'type': 'Polygon',
                      'coordinates': [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]}},
        {'type': 'Feature',
         'properties': {'ISO_A3': 'OTH', 'NAME': 'Otherland', 'CONTINENT': 'Asia'},
         'geometry': {'type': 'MultiPolygon',
                      'coordinates': [[[[20, 0], [30, 0], [30, 10], [20, 10], [20, 0]]]]}},
    ],
})


def setup_function(_):
    wm.invalidate_cache()


# ─── point-dans-polygone ─────────────────────────────────────────────────────

def test_point_in_ring_dedans_et_dehors():
    ring = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    assert wm._point_in_ring(5, 5, ring) is True
    assert wm._point_in_ring(50, 50, ring) is False


def test_point_in_geometry_polygon():
    geom = {'type': 'Polygon', 'coordinates': [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]}
    assert wm._point_in_geometry(5, 5, geom) is True
    assert wm._point_in_geometry(-1, -1, geom) is False


def test_point_in_geometry_multipolygon():
    geom = {'type': 'MultiPolygon',
            'coordinates': [[[[20, 0], [30, 0], [30, 10], [20, 10], [20, 0]]]]}
    assert wm._point_in_geometry(25, 5, geom) is True
    assert wm._point_in_geometry(5, 5, geom) is False


def test_point_in_geometry_type_inconnu_ne_plante_pas():
    assert wm._point_in_geometry(5, 5, {'type': 'Point', 'coordinates': [5, 5]}) is False
    assert wm._point_in_geometry(5, 5, {}) is False


# ─── chargement des features (mocké, pas de réseau) ──────────────────────────

def test_load_features_parse_les_proprietes(monkeypatch):
    monkeypatch.setattr(wm, 'load_world_geojson', lambda: FAKE_GEOJSON)
    feats = wm._load_features()
    assert len(feats) == 2
    ids = {f['id'] for f in feats}
    assert ids == {'TST', 'OTH'}
    tst = next(f for f in feats if f['id'] == 'TST')
    assert tst['name'] == 'Testland' and tst['continent'] == 'Europe'


def test_load_features_geojson_indisponible_retourne_liste_vide(monkeypatch):
    monkeypatch.setattr(wm, 'load_world_geojson', lambda: '')
    assert wm._load_features() == []


def test_entity_to_feature_id(monkeypatch):
    monkeypatch.setattr(wm, 'load_world_geojson', lambda: FAKE_GEOJSON)
    feats = wm._load_features()
    assert wm.entity_to_feature_id(5, 5, feats) == 'TST'
    assert wm.entity_to_feature_id(5, 25, feats) == 'OTH'
    assert wm.entity_to_feature_id(90, 90, feats) is None
    assert wm.entity_to_feature_id(None, None, feats) is None


# ─── worked_by_country (integration avec les entités DXCC) ───────────────────

def test_worked_by_country(monkeypatch):
    monkeypatch.setattr(wm, 'load_world_geojson', lambda: FAKE_GEOJSON)

    class _FakeEntity(dict):
        pass

    fake_entities = [
        {'prefix': 'T1', 'country': 'Testland', 'continent': 'EU', 'lat': 5, 'lon': 5},
        {'prefix': 'O1', 'country': 'Otherland', 'continent': 'AS', 'lat': 5, 'lon': 25},
    ]
    import radiocontest_dxcc as dxcc
    monkeypatch.setattr(dxcc, 'list_entities', lambda: fake_entities)
    monkeypatch.setattr('radiocontest_countries._worked_keys', lambda log, cid='': {'T1'})

    out = wm.worked_by_country([{'call': 'FAKE'}], '')
    assert out['TST']['worked'] is True
    assert out['TST']['name'] == 'Testland'
    assert out['OTH']['worked'] is False


def test_worked_by_country_geojson_vide_ne_plante_pas(monkeypatch):
    monkeypatch.setattr(wm, 'load_world_geojson', lambda: '')
    import radiocontest_dxcc as dxcc
    monkeypatch.setattr(dxcc, 'list_entities', lambda: [])
    monkeypatch.setattr('radiocontest_countries._worked_keys', lambda log, cid='': set())
    assert wm.worked_by_country([], '') == {}


# ─── cache disque (comme load_france_geojson) ────────────────────────────────

def test_load_world_geojson_cache_disque(monkeypatch, tmp_path):
    cached = str(tmp_path / 'world_countries.geojson')
    monkeypatch.setattr(wm, 'WORLD_GEOJSON_FILE', cached)
    with open(cached, 'w', encoding='utf-8') as f:
        f.write(FAKE_GEOJSON)
    assert wm.load_world_geojson() == FAKE_GEOJSON


def test_load_world_geojson_telecharge_si_absent(monkeypatch, tmp_path):
    missing = str(tmp_path / 'ne_existe_pas.geojson')
    monkeypatch.setattr(wm, 'WORLD_GEOJSON_FILE', missing)
    import radiocontest_utils as utils
    big_valid = FAKE_GEOJSON + ' ' * 100001  # dépasse le seuil de taille mini
    monkeypatch.setattr(utils, 'fetch_url', lambda url, timeout=30: big_valid)
    result = wm.load_world_geojson()
    assert 'FeatureCollection' in result
    assert os.path.exists(missing)


def test_load_world_geojson_reseau_indisponible_retourne_vide(monkeypatch, tmp_path):
    missing = str(tmp_path / 'ne_existe_pas2.geojson')
    monkeypatch.setattr(wm, 'WORLD_GEOJSON_FILE', missing)
    import radiocontest_utils as utils
    monkeypatch.setattr(utils, 'fetch_url', lambda url, timeout=30: None)
    assert wm.load_world_geojson() == ''
