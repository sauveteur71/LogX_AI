# -*- coding: utf-8 -*-
"""Band map : un champ numérique valant `null` dans le fichier (JSON VALIDE) ne
doit pas faire planter la lecture/l'ajout.

`s.get('ts', 0)` ne protège QUE contre l'ABSENCE de clé, pas contre une valeur
présente valant null : `{"ts": null}` -> `s.get('ts', 0)` renvoie None ->
`float(None)` lève TypeError, non rattrapée (le try/except de
_charger_si_besoin n'entoure que l'ouverture/parse du fichier). Un seul
enregistrement malformé empoisonnait alors _purger_locked (appelé par TOUTES
les entrées publiques) -> 500 sur /bandmap/local et échec de bm.ajouter().
Le test test_un_fichier_illisible_ne_fait_pas_planter ne couvrait QUE du JSON
syntaxiquement invalide, jamais un JSON valide à champ null.
"""
import json
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_bandmap as bm  # noqa: E402


@pytest.fixture(autouse=True)
def dossier_isole(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bm, '_spots', [])
    monkeypatch.setattr(bm, '_charge', False)
    return tmp_path


def test_champ_numerique_null_ne_fait_pas_planter():
    # JSON VALIDE mais ts=null (exerce _purger_locked) et freq_khz=null (exerce spots()).
    recs = [{"call": "A", "freq_khz": 14000, "ts": None},
            {"call": "B", "freq_khz": None, "ts": 1e12}]
    with open(bm._chemin(), 'w', encoding='utf-8') as f:
        json.dump(recs, f)
    bm._charge = False
    out = bm.spots()          # avant correctif : float(None) -> TypeError -> 500
    assert isinstance(out, list)


def test_ajouter_survit_a_un_fichier_a_champ_null():
    with open(bm._chemin(), 'w', encoding='utf-8') as f:
        json.dump([{"call": "X", "freq_khz": 14000, "ts": None}], f)
    bm._charge = False
    # ajouter() passe par _purger_locked : ne doit pas planter à cause du null.
    assert bm.ajouter('F6BC', 14025.3, '14', 'CW')['ok']
