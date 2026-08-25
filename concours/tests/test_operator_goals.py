# -*- coding: utf-8 -*-
"""Profil d'objectifs opérateur (logx_operator_goals) : stockage DÉDIÉ, isolé de
.server_config.json. normaliser() ne garde que les 5 clés connues en booléens,
défaut = tout actif (comportement historique). charger()/enregistrer() font un
aller-retour atomique ; fichier absent/corrompu -> défauts (jamais d'erreur)."""
import json
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_operator_goals as og  # noqa: E402


def test_cles_alignees_sur_le_moteur():
    # Les 5 objectifs doivent correspondre EXACTEMENT aux clés que
    # logx_chasse_priorite associe à ses classes de crédit.
    import logx_chasse_priorite as cp
    attendues = set(cp._OBJECTIF_POUR_CLASSE.values())
    assert set(og.CLES) == attendues


def test_defauts_tout_actif():
    assert og.DEFAUTS == {k: True for k in og.CLES}
    assert all(og.DEFAUTS.values())


def test_normaliser_vide_donne_les_defauts():
    assert og.normaliser({}) == og.DEFAUTS


def test_normaliser_desactive_une_cle():
    r = og.normaliser({'dxcc': False})
    assert r['dxcc'] is False
    assert r['vucc'] is True                    # les autres restent au défaut


def test_normaliser_jette_les_cles_inconnues_et_coerce_en_bool():
    r = og.normaliser({'inconnue': True, 'dxcc': 0, 'vucc': 1})
    assert 'inconnue' not in r
    assert r['dxcc'] is False and r['vucc'] is True
    assert set(r) == set(og.CLES)


def test_normaliser_entree_non_dict_donne_defauts():
    assert og.normaliser("nawak") == og.DEFAUTS
    assert og.normaliser(None) == og.DEFAUTS


def test_charger_fichier_absent_donne_defauts(tmp_path, monkeypatch):
    monkeypatch.setattr(og, 'FICHIER', str(tmp_path / 'pas_la.json'))
    assert og.charger() == og.DEFAUTS


def test_aller_retour_enregistrer_puis_charger(tmp_path, monkeypatch):
    monkeypatch.setattr(og, 'FICHIER', str(tmp_path / 'g.json'))
    ecrit = og.enregistrer({'dxcc': False, 'dxcc_new_mode': False})
    assert ecrit['dxcc'] is False and ecrit['dxcc_new_mode'] is False
    assert og.charger() == ecrit                # persisté et relu à l'identique
    # le fichier ne contient QUE les clés connues (isolé, pas la config)
    disque = json.load(open(str(tmp_path / 'g.json'), encoding='utf-8'))
    assert set(disque) == set(og.CLES)


def test_charger_fichier_corrompu_donne_defauts(tmp_path, monkeypatch):
    p = tmp_path / 'g.json'
    p.write_text('{ ceci n est pas du json', encoding='utf-8')
    monkeypatch.setattr(og, 'FICHIER', str(p))
    assert og.charger() == og.DEFAUTS
