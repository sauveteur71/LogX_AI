# -*- coding: utf-8 -*-
"""Ventilation SAISI / IMPORTÉ du badge « à vérifier » (logx_validator).

Un log importé (source == 'adif_import') peut apporter des milliers de constats
légitimes mais non actionnables « ici et maintenant ». validate_log sépare donc
le compte pour que le badge n'alarme que sur les QSO saisis dans LogX, sans
cacher l'historique importé (toujours dans findings). Cas réel : F5SDD, 19650
« à vérifier » d'un coup après import.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_validator as v   # noqa: E402

# usage_mode simple : pas de contrainte concours, doublon ignoré -> un QSO à
# indicatif vide donne EXACTEMENT une 'erreur' (indicatif_vide), déterministe.
_CFG = {'usage_mode': 'simple'}


def _vide(qid, source=None):
    q = {'id': qid, 'call': '', 'band': '20m', 'date': '20260101', 'time': '1200'}
    if source:
        q['source'] = source
    return q


def test_compte_ventile_saisi_vs_importe():
    log = [
        _vide(1),                          # saisi -> 1 erreur
        _vide(2, source='adif_import'),    # importé
        _vide(3, source='adif_import'),    # importé
    ]
    res = v.validate_log(log, '', _CFG)
    assert res['qso_a_verifier_saisi'] == 1
    assert res['qso_a_verifier_importe'] == 2
    assert res['qso_a_verifier'] == 3          # total inchangé (rétro-compat)
    assert res['counts_saisi']['erreur'] == 1
    assert res['counts_importe']['erreur'] == 2
    # Le compte global reste la somme (les 2 ensembles sont disjoints par QSO).
    assert res['qso_a_verifier'] == res['qso_a_verifier_saisi'] + res['qso_a_verifier_importe']


def test_log_tout_importe_ne_charge_pas_le_saisi():
    log = [_vide(i, source='adif_import') for i in range(1, 6)]
    res = v.validate_log(log, '', _CFG)
    assert res['qso_a_verifier_saisi'] == 0
    assert res['qso_a_verifier_importe'] == 5
    assert res['counts_saisi'] == {'erreur': 0, 'attention': 0, 'info': 0}


def test_log_tout_saisi_rien_en_importe():
    log = [_vide(1), _vide(2)]
    res = v.validate_log(log, '', _CFG)
    assert res['qso_a_verifier_saisi'] == 2
    assert res['qso_a_verifier_importe'] == 0
    assert res['counts_importe'] == {'erreur': 0, 'attention': 0, 'info': 0}


def test_pas_de_collision_id_index_mixtes():
    # Cas mixte : un QSO saisi SANS id (repéré par index 0) et un QSO importé
    # AVEC id == 0. Sans clé namespacée, l'index 0 du saisi entrerait en
    # collision avec l'id 0 de l'importé -> le saisi serait classé importé à tort.
    log = [
        {'call': '', 'band': '20m', 'date': '20260101', 'time': '1200'},        # saisi, index 0
        {'id': 0, 'call': '', 'band': '20m', 'date': '20260101', 'time': '1200',
         'source': 'adif_import'},                                              # importé, id 0
    ]
    res = v.validate_log(log, '', _CFG)
    assert res['qso_a_verifier_saisi'] == 1     # le QSO sans id reste SAISI
    assert res['qso_a_verifier_importe'] == 1


def test_retrocompat_les_cles_historiques_restent():
    res = v.validate_log([_vide(1)], '', _CFG)
    for k in ('counts', 'qso_a_verifier', 'findings', 'ok'):
        assert k in res
