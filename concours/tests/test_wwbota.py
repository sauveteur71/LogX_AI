# -*- coding: utf-8 -*-
"""Parseur CSV pur de WWBOTA (base des bunkers) + garde-fou anti-cache-tronqué.

Fonctions PURES (aucun réseau) : un vrai risque de casse SILENCIEUSE si le
format de l'export api.wwbota.org change. Données SYNTHÉTIQUES et structurelles
(en-têtes RÉELS vérifiés en direct, mais aucun bunker réel inventé)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_wwbota as wwbota


def test_looks_valid_refuse_les_mauvais():
    assert wwbota._looks_valid_bunkers_csv(None) is False
    assert wwbota._looks_valid_bunkers_csv('') is False
    assert wwbota._looks_valid_bunkers_csv(wwbota._ENTETE + '\n') is False   # trop court
    assert wwbota._looks_valid_bunkers_csv('z' * 400_000) is False           # gros sans en-tête


def test_looks_valid_accepte_un_vrai_export():
    # en-tête réel + > 100 000 virgules + > 300 000 octets
    content = wwbota._ENTETE + '\n' + (',' * 100_001) + ('x' * 300_000)
    assert wwbota._looks_valid_bunkers_csv(content) is True


def test_parse_bunkers_csv():
    content = '\n'.join([
        wwbota._ENTETE,
        'FBOTA,227,B/F-9001,Fort Test,WW1,51.08,2.54,JO11GC',
        # Reference vide -> ignoré :
        'FBOTA,227,,Sans Ref,WW2,50.0,3.0,JN00',
        # Lat/Long non numériques -> None :
        'OKBOTA,503,b/ok-9002,Bunker Test,Cold War,x,y,JN79',
    ])
    out = wwbota._parse_bunkers_csv(content)
    assert len(out) == 2                                  # la ligne sans Reference est ignorée
    b0 = out[0]
    assert b0['code'] == 'B/F-9001'                       # majuscules
    assert b0['name'] == 'Fort Test' and b0['region'] == 'FBOTA'
    assert b0['type'] == 'WW1' and b0['locator'] == 'JO11GC' and b0['dxcc'] == '227'
    assert b0['lat'] == 51.08 and b0['lon'] == 2.54
    b1 = out[1]
    assert b1['code'] == 'B/OK-9002'                      # 'b/ok-9002' -> majuscules
    assert b1['lat'] is None and b1['lon'] is None         # 'x'/'y' -> None


def test_parse_bunkers_csv_vide():
    assert wwbota._parse_bunkers_csv('') == []
    assert wwbota._parse_bunkers_csv(wwbota._ENTETE) == []   # en-tête seul, pas de données


def test_wrappers_delegent_a_directory_db(monkeypatch):
    """search/get/nearby/status délèguent bien à l'instance ActivationDatabase."""
    appels = {}
    monkeypatch.setattr(wwbota.directory_db, 'search',
                        lambda q, limit=25: appels.setdefault('search', (q, limit)) or [])
    monkeypatch.setattr(wwbota.directory_db, 'get',
                        lambda c: appels.setdefault('get', c) or None)
    monkeypatch.setattr(wwbota.directory_db, 'nearby',
                        lambda lat, lon, max_km=100, limit=30: appels.setdefault('nearby', (lat, lon)) or [])
    monkeypatch.setattr(wwbota.directory_db, 'status', lambda: {'ready': True})
    wwbota.search('fort', limit=5)
    wwbota.get('B/F-9001')
    wwbota.nearby(48.8, 2.3)
    assert appels['search'] == ('fort', 5)
    assert appels['get'] == 'B/F-9001'
    assert appels['nearby'] == (48.8, 2.3)
    assert wwbota.status() == {'ready': True}
