# -*- coding: utf-8 -*-
"""Câblage serveur du profil d'objectifs (option b, F4GLD 26/08/2026) :
- GET/POST /data/operator_goals (endpoint DÉDIÉ, pas la page CONFIG) ;
- les 2 annoter_credit (/data/focus + /data/spots_ranked) lisent désormais le
  profil PERSISTÉ (logx_operator_goals.charger()), plus cfg_snap.
Asserts en grep sur tout le fichier (pas d'extraction de handler par regex —
une borne fausse rendrait l'assert vacant, cf. piège du 25/08)."""
import os

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8').read()


def test_module_importe():
    assert 'import logx_operator_goals' in SRC


def test_endpoint_get_et_post_declare():
    # apparaît au moins deux fois : le GET (lecture) et le POST (écriture)
    assert SRC.count("'/data/operator_goals'") >= 2


def test_get_renvoie_le_profil_persiste():
    import re
    # un chemin GET qui renvoie charger() (lecture du profil dédié)
    assert re.search(r"operator_goals'.*?charger\(\)", SRC, re.S), \
        'le GET ne renvoie pas operator_goals.charger()'


def test_post_enregistre():
    assert '.enregistrer(' in SRC, 'aucun POST ne persiste via enregistrer()'


def test_annoter_credit_lit_le_profil_persiste_pas_la_config():
    # plus AUCUN appel ne lit operator_goals depuis la config : la source de
    # vérité est le module dédié.
    assert "cfg_snap.get('operator_goals')" not in SRC, \
        'un annoter_credit lit encore le profil depuis la config au lieu du module dédié'
    # les deux sites passent objectifs=<module>.charger()
    assert SRC.count('.charger()') >= 2
