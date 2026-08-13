# -*- coding: utf-8 -*-
"""Tests de la mémoire inter-concours (digest DÉTERMINISTE agrégeant les
archives déjà stockées) -- logx_coach.build_memory_digest(). Aucun appel IA :
uniquement de l'agrégation sur des archives factices écrites via
logx_archive.archive_log(), même pattern que tests/test_archive.py."""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_archive as arch          # noqa: E402
from logx_coach import build_memory_digest  # noqa: E402

CFG = {'callsign': 'F6KQJ', 'locator': 'JN15XC', 'contest': 'REF_160M'}


def _qso(call='DL1ABC', band='14', date='20260801', time='12:00', points=1):
    return {'call': call, 'band': band, 'mode': 'CW', 'date': date,
            'time': time, 'points': points, 'contest': 'REF_160M'}


def test_digest_agrege_plusieurs_editions_par_heure_et_bande(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Édition 2025 : 2 QSO à 12h + 1 à 14h, tous en 14 MHz
    ed1 = [_qso(time='12:03'), _qso(call='F5XYZ', time='12:40'),
           _qso(call='DK2ZZ', time='14:10')]
    arch.archive_log(ed1, 'REF_160M', CFG, when=datetime.datetime(2025, 8, 2))
    # Édition 2026 : 3 QSO à 12h, tous en 7 MHz
    ed2 = [_qso(call='G4ABC', band='7', time='12:05'),
           _qso(call='ON4XYZ', band='7', time='12:15'),
           _qso(call='EA1ZZZ', band='7', time='12:50')]
    arch.archive_log(ed2, 'REF_160M', CFG, when=datetime.datetime(2026, 8, 1))

    d = build_memory_digest(CFG, contest_id='REF_160M')
    assert d['ok'] is True
    assert d['editions'] == 2
    # 12h cumule 2 (édition 1) + 3 (édition 2) = 5 QSO -> meilleure heure
    assert d['best_hours'][0] == ['12h', 5]
    assert d['per_band']['14'] == {'qso': 3, 'avg_per_edition': 3.0}
    assert d['per_band']['7'] == {'qso': 3, 'avg_per_edition': 3.0}


def test_digest_filtre_par_bande(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    arch.archive_log([_qso(band='14', time='10:00'), _qso(band='7', time='11:00')],
                     'REF_160M', CFG)
    d = build_memory_digest(CFG, contest_id='REF_160M', band='14')
    assert d['ok'] is True
    assert d['per_band'] == {'14': {'qso': 1, 'avg_per_edition': 1.0}}
    assert d['best_hours'] == [['10h', 1]]


def test_digest_limite_max_editions_aux_plus_recentes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for year in (2022, 2023, 2024, 2025, 2026):
        arch.archive_log([_qso(time='09:00')], 'REF_160M', CFG,
                         when=datetime.datetime(year, 8, 1))
    d = build_memory_digest(CFG, contest_id='REF_160M', max_editions=3)
    assert d['ok'] is True
    assert d['editions'] == 3


def test_digest_entite_toutes_archives_confondues_quel_que_soit_le_concours(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # DXpédition FT8WW travaillée dans DEUX concours différents, toujours ~6h UTC
    arch.archive_log([_qso(call='FT8WW', time='06:10'), _qso(call='F5XYZ', time='10:00')],
                     'REF_160M', CFG, when=datetime.datetime(2025, 8, 2))
    arch.archive_log([_qso(call='FT8WW', time='06:40')], 'CQWW_CW', CFG,
                     when=datetime.datetime(2025, 11, 1))
    d = build_memory_digest(CFG, contest_id='', entity='FT8WW')
    assert d['ok'] is True
    assert d['entity_qso'] == 2
    assert d['entity_hours'][0] == ['06h', 2]
    # Le digest par concours n'a pas été demandé (contest_id vide) : pas d'éditions comptées
    assert d['editions'] == 0


def test_digest_entite_jamais_travaillee(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    arch.archive_log([_qso(call='F5XYZ')], 'REF_160M', CFG)
    d = build_memory_digest(CFG, contest_id='', entity='ZL1ABC')
    assert d['ok'] is True
    assert d['entity_qso'] == 0
    assert d['entity_hours'] == []


def test_digest_aucune_archive_pour_ce_concours(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = build_memory_digest(CFG, contest_id='REF_160M')
    assert d['ok'] is False
    assert 'error' in d


def test_digest_sans_concours_ni_cible(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = build_memory_digest(CFG, contest_id='', entity='')
    assert d['ok'] is False
