# -*- coding: utf-8 -*-
"""Résolution batch indicatif → position (pour la carte de sortie XOTA).

Le lookup client (logx_dxcc_lookup.js) ne porte PAS de lat/lon ; seul le
serveur, via logx_dxcc.lookup (cty.dat AD1C), sait géolocaliser un indicatif.
Cet endpoint expose cette résolution en lot pour les QSO sans locator.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as H   # noqa: E402


def _mock_lookup(monkeypatch, table):
    """Remplace logx_dxcc.lookup par une table {call_prefixe: dict|None}."""
    import logx_dxcc
    def fake(call):
        return table.get((call or '').upper())
    monkeypatch.setattr(logx_dxcc, 'lookup', fake)


def test_resout_les_indicatifs_connus(monkeypatch):
    _mock_lookup(monkeypatch, {
        'F4ABC': {'country': 'France', 'lat': 46.0, 'lon': 2.0,
                  'continent': 'EU', 'cq_zone': 14, 'itu_zone': 27, 'prefix': 'F'},
        'W1AW': {'country': 'United States', 'lat': 41.7, 'lon': -72.7,
                 'continent': 'NA', 'cq_zone': 5, 'itu_zone': 8, 'prefix': 'K'},
    })
    d = H._dxcc_positions_dict(['F4ABC', 'W1AW'])
    assert d['positions']['F4ABC'] == {'lat': 46.0, 'lon': 2.0, 'country': 'France'}
    assert d['positions']['W1AW']['country'] == 'United States'
    assert d['unresolved'] == []


def test_signale_les_indicatifs_non_resolus(monkeypatch):
    _mock_lookup(monkeypatch, {'F4ABC': {'country': 'France', 'lat': 46.0, 'lon': 2.0}})
    d = H._dxcc_positions_dict(['F4ABC', 'XYZ123ZZ'])
    assert 'F4ABC' in d['positions']
    assert d['unresolved'] == ['XYZ123ZZ']
    assert 'XYZ123ZZ' not in d['positions']


def test_dedoublonne_et_ignore_le_vide(monkeypatch):
    calls_vus = []
    import logx_dxcc
    def fake(call):
        calls_vus.append(call)
        return {'country': 'France', 'lat': 46.0, 'lon': 2.0}
    monkeypatch.setattr(logx_dxcc, 'lookup', fake)
    d = H._dxcc_positions_dict(['F4ABC', 'F4ABC', '', None, '  '])
    # Un seul appel réel (dédoublonné), vide/None ignorés.
    assert calls_vus == ['F4ABC']
    assert list(d['positions'].keys()) == ['F4ABC']


def test_lat_lon_none_compte_comme_non_resolu(monkeypatch):
    # cty.dat peut rendre une entrée sans coordonnées (lat/lon None).
    _mock_lookup(monkeypatch, {'F4ABC': {'country': 'X', 'lat': None, 'lon': None}})
    d = H._dxcc_positions_dict(['F4ABC'])
    assert d['positions'] == {}
    assert d['unresolved'] == ['F4ABC']


def test_json_safe(monkeypatch):
    import json
    _mock_lookup(monkeypatch, {'F4ABC': {'country': 'France', 'lat': 46.0, 'lon': 2.0}})
    json.dumps(H._dxcc_positions_dict(['F4ABC']), allow_nan=False)
