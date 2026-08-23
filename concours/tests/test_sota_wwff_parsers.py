# -*- coding: utf-8 -*-
"""Parseurs CSV purs de SOTA et WWFF (annuaires de sommets / parcs).

Ces fonctions transforment un export CSV externe (~25 Mo) en liste de dicts, et
un garde-fou `_looks_valid_*` refuse d'écraser le cache avec un fichier tronqué
ou une page d'erreur. Elles sont PURES (aucun réseau) — un vrai risque de casse
SILENCIEUSE si le format externe change. Données de test SYNTHÉTIQUES et
structurelles (en-têtes réels, mais aucun sommet/parc réel inventé).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_sota as sota
import logx_wwff as wwff


# ─── SOTA ──────────────────────────────────────────────────────────────────
def test_sota_strip_accents():
    assert sota._strip_accents('Café') == 'Cafe'
    assert sota._strip_accents('Åström') == 'Astrom'
    assert sota._strip_accents('ABC-123') == 'ABC-123'   # ASCII inchangé


def test_sota_looks_valid_csv_refuse_les_mauvais():
    assert sota._looks_valid_csv(None) is False
    assert sota._looks_valid_csv('') is False
    assert sota._looks_valid_csv('SummitCode,' * 10) is False        # trop court
    assert sota._looks_valid_csv('x' * 1_100_000) is False           # gros mais sans marqueurs


def test_sota_looks_valid_csv_accepte_un_vrai_export():
    # > 1 Mo, contient 'SummitCode' et > 100 000 virgules
    content = 'SummitCode' + (',' * 100_001) + ('x' * 1_000_000)
    assert sota._looks_valid_csv(content) is True


def test_sota_parse_summits_csv():
    # 1re ligne = titre (sautée), 2e = vrai en-tête, puis données.
    content = '\n'.join([
        'SOTA Summits List (Date=2026/08/23)',
        'SummitCode,AssociationName,RegionName,SummitName,AltM,AltFt,GridRef1,'
        'GridRef2,Longitude,Latitude,Points,BonusPoints,ValidFrom,ValidTo,'
        'ActivationCount,ActivationDate,ActivationCall',
        'xx/ab-001,TestAssoc,TestRegion,Mont Test,1200,3937,,,6.5,45.2,4,0,'
        '01/01/2020,31/12/2099,7,,',
        # code vide -> ignoré :
        ',TestAssoc,TestRegion,Sans Code,100,,,, ,,,,,,,,',
        # AltM non numérique -> 0 ; lat/lon absents -> None :
        'xx/cd-002,A,R,Bad Alt,not_a_number,,,,,,,,,,,,',
    ])
    out = sota._parse_summits_csv(content)
    assert len(out) == 2                                  # la ligne sans code est ignorée
    s0 = out[0]
    assert s0['code'] == 'XX/AB-001'                      # mis en majuscules
    assert s0['alt_m'] == 1200 and s0['points'] == 4
    assert s0['lat'] == 45.2 and s0['lon'] == 6.5
    s1 = out[1]
    assert s1['code'] == 'XX/CD-002'
    assert s1['alt_m'] == 0                               # 'not_a_number' -> 0
    assert s1['lat'] is None and s1['lon'] is None        # lat/lon absents -> None


def test_sota_parse_summits_csv_trop_court():
    assert sota._parse_summits_csv('') == []
    assert sota._parse_summits_csv('une seule ligne') == []


# ─── WWFF ──────────────────────────────────────────────────────────────────
def test_wwff_looks_valid_directory_csv_refuse_les_mauvais():
    assert wwff._looks_valid_directory_csv(None) is False
    assert wwff._looks_valid_directory_csv('') is False
    assert wwff._looks_valid_directory_csv('reference,status,name\n') is False   # trop court
    assert wwff._looks_valid_directory_csv('y' * 5_100_000) is False             # gros sans marqueur


def test_wwff_looks_valid_directory_csv_accepte_un_vrai_export():
    # >= 5 Mo, contient 'reference,status,name' et > 500 000 virgules
    content = 'reference,status,name\n' + (',' * 500_001) + ('y' * 5_000_000)
    assert wwff._looks_valid_directory_csv(content) is True


def test_wwff_parse_directory_csv():
    content = '\n'.join([
        'reference,status,name,program,dxcc,state,county,continent,iota,'
        'iaruLocator,latitude,longitude,IUCNcat,validFrom,validTo,notes',
        'ff-0001,active,Parc Test,WWFF,227,IDF,,EU,,JN18,48.8,2.3,II,,,',
        # reference vide -> ignoré :
        ',active,Sans Ref,WWFF,227,,,EU,,,,,,,,',
        # lat/lon non numériques -> None :
        'ff-0002,active,Bad Coord,WWFF,227,BZH,,EU,EU-064,IN99,x,y,,,,',
    ])
    out = wwff._parse_directory_csv(content)
    assert len(out) == 2                                  # la ligne sans reference est ignorée
    p0 = out[0]
    assert p0['code'] == 'FF-0001'                        # majuscules
    assert p0['region'] == 'IDF' and p0['continent'] == 'EU'
    assert p0['lat'] == 48.8 and p0['lon'] == 2.3
    p1 = out[1]
    assert p1['code'] == 'FF-0002'
    assert p1['iota'] == 'EU-064'
    assert p1['lat'] is None and p1['lon'] is None        # 'x'/'y' -> None
