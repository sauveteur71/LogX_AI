# -*- coding: utf-8 -*-
"""« Prochaines cibles recommandées » (logx_awards.prochaines_cibles).

Par entité entamée : « à confirmer LoTW » si jamais confirmée, sinon un mode
manquant sur une bande déjà travaillée (CW d'abord -> « CW · 15 m »). On isole
le log et les confirmations LoTW par monkeypatch pour couvrir les deux branches.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_awards as aw   # noqa: E402


def _setup(monkeypatch, qsos, confirmes):
    monkeypatch.setattr(aw, 'collect_all_qsos', lambda log=None: qsos)
    monkeypatch.setattr(aw, '_confirm_key', lambda q: q.get('call'))
    # confirmes = set des call confirmés LoTW
    monkeypatch.setattr(aw, '_load_confirmations',
                        lambda: {c: {'LOTW': True} for c in confirmes})


def test_deux_branches_lotw_et_mode(monkeypatch):
    qsos = [
        {'call': 'JA1A', 'dxcc_country': 'Japon', 'band': '20', 'mode': 'FT8'},
        {'call': 'JA1A', 'dxcc_country': 'Japon', 'band': '15', 'mode': 'FT8'},
        {'call': 'PY1A', 'dxcc_country': 'Brésil', 'band': '20', 'mode': 'SSB'},
    ]
    _setup(monkeypatch, qsos, confirmes={'JA1A'})   # Japon confirmé LoTW, Brésil non
    d = {x['entity']: x['slot'] for x in aw.prochaines_cibles(n=6)}
    assert d['Brésil'] == 'à confirmer LoTW'         # jamais confirmé -> confirmation d'abord
    assert d['Japon'] == 'CW · 15 m'                 # confirmé, DIGITAL sur 15/20 -> il manque CW (bande la plus basse)


def test_priorise_l_entite_la_plus_investie_et_plafonne(monkeypatch):
    qsos = []
    # 3 entités non confirmées, avec des volumes différents
    for i, (call, pays, k) in enumerate([('A1', 'PaysA', 1), ('B1', 'PaysB', 5), ('C1', 'PaysC', 3)]):
        for _ in range(k):
            qsos.append({'call': call, 'dxcc_country': pays, 'band': '20', 'mode': 'SSB'})
    _setup(monkeypatch, qsos, confirmes=set())
    r = aw.prochaines_cibles(n=2)
    assert len(r) == 2                                # plafonné
    assert [x['entity'] for x in r] == ['PaysB', 'PaysC']   # plus investi d'abord


def test_entite_complete_ne_propose_rien(monkeypatch):
    # Un pays confirmé LoTW ET travaillé dans les 3 modes sur sa seule bande :
    # aucune cible (rien à proposer).
    qsos = [
        {'call': 'X', 'dxcc_country': 'Complet', 'band': '20', 'mode': 'CW'},
        {'call': 'X', 'dxcc_country': 'Complet', 'band': '20', 'mode': 'SSB'},
        {'call': 'X', 'dxcc_country': 'Complet', 'band': '20', 'mode': 'FT8'},
    ]
    _setup(monkeypatch, qsos, confirmes={'X'})
    assert aw.prochaines_cibles() == []
