# -*- coding: utf-8 -*-
"""Tests de l'archivage des logs de concours (dossiers permanents)."""
import os
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_archive as arch

QSOS = [
    {'call': 'DL1ABC', 'band': '14', 'mode': 'CW', 'date': '20260801',
     'time': '12:03', 'points': 1, 'num_rcvd': '05', 'contest': 'REF_160M'},
    {'call': 'F5XYZ', 'band': '7', 'mode': 'CW', 'date': '20260801',
     'time': '12:10', 'points': 1, 'num_rcvd': '33', 'contest': 'REF_160M'},
]
CFG = {'callsign': 'F6KQJ', 'locator': 'JN15XC', 'contest': 'REF_160M'}


def test_archive_cree_dossier_et_fichiers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = arch.archive_log(QSOS, 'REF_160M', CFG)
    assert r['ok'] and r['qso_count'] == 2
    folder = r['folder']
    assert os.path.isdir(folder)
    # log.json rechargeable
    with open(os.path.join(folder, 'log.json'), encoding='utf-8') as f:
        assert len(json.load(f)) == 2
    # Cabrillo, ADIF, résumé présents
    files = set(os.listdir(folder))
    assert 'log.json' in files and 'resume.txt' in files
    assert any(f.endswith('.cbr') for f in files)
    assert any(f.endswith('.adi') for f in files)
    # Résumé contient le score et le concours
    with open(os.path.join(folder, 'resume.txt'), encoding='utf-8') as f:
        txt = f.read()
    assert 'REF_160M' in txt and 'QSO totaux : 2' in txt


def test_archive_log_vide(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = arch.archive_log([], 'REF_160M', CFG)
    assert not r['ok'] and 'Aucun QSO' in r['error']


def test_liste_archives(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    arch.archive_log(QSOS, 'REF_160M', CFG)
    arch.archive_log(QSOS[:1], 'EU_HF_CHAMP', CFG)
    lst = arch.list_archives()
    assert len(lst) == 2
    names = [a['name'] for a in lst]
    assert any(n.startswith('REF_160M_') for n in names)
    assert any(n.startswith('EU_HF_CHAMP_') for n in names)
    # qso_count relu depuis log.json
    ref = next(a for a in lst if a['name'].startswith('REF_160M'))
    assert ref['qso_count'] == 2


def test_archives_persistent_apres_reset(tmp_path, monkeypatch):
    """L'archive reste sur le disque indépendamment du log actif."""
    monkeypatch.chdir(tmp_path)
    arch.archive_log(QSOS, 'REF_160M', CFG)
    # Simule un changement de concours / reset : le dossier archives/ demeure
    assert os.path.isdir('archives')
    assert len(arch.list_archives()) == 1
