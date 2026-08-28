# -*- coding: utf-8 -*-
"""Provenance par champ (logx_provenance.provenance)."""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_provenance as prov   # noqa: E402
import logx_dxcc as dxcc         # noqa: E402


def test_provenance_cty_dat_et_calcule(monkeypatch):
    monkeypatch.setattr(dxcc, 'lookup', lambda c: {
        'country': 'Japon', 'continent': 'AS', 'cq_zone': 25, 'itu_zone': 45,
        'lat': 36.0, 'lon': 138.0})
    rows = prov.provenance('JA1XYZ', {'locator': 'JN06'})
    d = {r['champ']: (r['valeur'], r['source']) for r in rows}
    assert d['Pays'] == ('Japon', 'cty.dat')
    assert d['Continent'][1] == 'cty.dat'
    assert d['Zone CQ'] == ('25', 'cty.dat')
    assert 'km' in d['Distance'][0] and 'calcul' in d['Distance'][1]
    assert '°' in d['Azimut'][0]


def test_sans_locator_pas_de_distance(monkeypatch):
    monkeypatch.setattr(dxcc, 'lookup', lambda c: {
        'country': 'Japon', 'continent': 'AS', 'cq_zone': 25, 'itu_zone': 45,
        'lat': 36.0, 'lon': 138.0})
    rows = prov.provenance('JA1XYZ', {})     # pas de mon locator
    champs = {r['champ'] for r in rows}
    assert 'Pays' in champs and 'Distance' not in champs   # cty.dat oui, calculé non


def test_indicatif_inconnu_ou_vide():
    import logx_dxcc as d
    d.lookup  # s'assure que le module existe
    assert prov.provenance('', {'locator': 'JN06'}) == []
