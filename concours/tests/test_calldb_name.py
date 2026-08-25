# -*- coding: utf-8 -*-
"""Base interne d'indicatifs (calldb) : enrichissement du PRÉNOM du correspondant
au fil des QSO. Source de prénom HORS QRZ (HamQTH n'en renvoie pas, QRZ = payant),
demandée par F4GLD. On teste la fusion PURE d'une entrée (merge_calldb_entry),
utilisée par POST /calldb/update — le round-trip HTTP est couvert par le harnais.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_departments as dep   # noqa: E402


def test_merge_ajoute_locator_dept_et_nom():
    entry, changed = dep.merge_calldb_entry({}, locator='JN18', dept='75', name='Jean')
    assert changed is True
    assert entry == {'locator': 'JN18', 'dept': '75', 'name': 'Jean'}


def test_merge_nom_seul_sur_entree_existante():
    # un correspondant déjà connu (locator) dont on apprend le prénom
    entry, changed = dep.merge_calldb_entry({'locator': 'JN18'}, name='Sophie')
    assert changed is True
    assert entry['locator'] == 'JN18' and entry['name'] == 'Sophie'


def test_merge_valeurs_vides_ne_changent_rien():
    src = {'locator': 'JN18', 'name': 'Jean'}
    entry, changed = dep.merge_calldb_entry(src, locator='', dept='', name='')
    assert changed is False
    assert entry == src


def test_merge_corrige_un_nom_existant():
    entry, changed = dep.merge_calldb_entry({'name': 'Jean'}, name='Jean-Marc')
    assert changed is True and entry['name'] == 'Jean-Marc'


def test_merge_ne_mute_pas_l_entree_source():
    src = {'locator': 'JN18'}
    entry, _ = dep.merge_calldb_entry(src, name='Léa')
    assert 'name' not in src            # pur : la source n'est pas modifiée
    assert entry['name'] == 'Léa'


def test_merge_nom_conserve_sa_casse():
    # le prénom est un nom PROPRE : jamais mis en majuscules (≠ indicatif/locator)
    entry, _ = dep.merge_calldb_entry({}, name='Éric')
    assert entry['name'] == 'Éric'


def test_load_calldb_porte_le_nom(tmp_path, monkeypatch):
    # _load_calldb lit l'entrée entière -> le prénom stocké est bien restitué.
    import json
    monkeypatch.chdir(tmp_path)
    with open('calldb.json', 'w', encoding='utf-8') as f:
        json.dump({'calls': {'F4ABC': {'locator': 'JN18', 'name': 'Paul'}}}, f)
    calls = dep._load_calldb()
    assert calls.get('F4ABC', {}).get('name') == 'Paul'
