# -*- coding: utf-8 -*-
"""Tests du palier IA de C1 (incrément 2, cadrage 12/09/2026 -- décisions
F4GLD par question à choix : palier IA complet activé, historique
multi-tour reporté).

Portée : le DIGEST d'agrégats (jamais le carnet brut, jamais un champ
libre) et le prompt utilisateur construit à partir de lui -- fonctions
pures, aucun appel réseau/LLM ici (voir test_invariants_securite.py pour le
câblage HTTP + garde I2, et test_carnet_questions_http.py pour l'endpoint
bout-en-bout)."""
import copy
import os
import sys

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import logx_carnet_questions as cq  # noqa: E402


def _log_enrichi():
    return [
        {'id': 1, 'call': 'F4ABC', 'band': '20m', 'mode': 'SSB', 'date': '20260901',
         'time': '10:00', 'locator': 'JN18', 'dxcc_country': 'France'},
        {'id': 2, 'call': 'W1AW', 'band': '40m', 'mode': 'CW', 'date': '20260902',
         'time': '11:00', 'locator': 'FN31', 'dxcc_country': 'United States'},
        {'id': 3, 'call': 'F4ABC', 'band': '20m', 'mode': 'FT8', 'date': '20260905',
         'time': '09:00', 'locator': 'JN18', 'dxcc_country': 'France'},
        {'id': 4, 'call': 'DL1XYZ', 'band': '40m', 'mode': 'CW', 'date': '20260903',
         'time': '12:00', 'locator': 'JO40', 'dxcc_country': 'Germany'},
    ]


def test_digest_total_et_agregats():
    d = cq.digest(_log_enrichi())
    assert d['total_qso'] == 4
    assert d['par_bande'] == {'20m': 2, '40m': 2}
    assert d['par_mode']['CW'] == 2


def test_digest_par_pays_ignore_les_qso_sans_dxcc_country():
    log = _log_enrichi() + [{'id': 5, 'call': 'XX1YY', 'band': '10m', 'mode': 'SSB'}]
    d = cq.digest(log)
    assert d['par_pays'] == {'France': 2, 'United States': 1, 'Germany': 1}


def test_digest_plus_travailles_trie_par_frequence():
    d = cq.digest(_log_enrichi())
    assert d['plus_travailles'][0] == {'indicatif': 'F4ABC', 'qso': 2}


def test_digest_premier_et_dernier_qso():
    d = cq.digest(_log_enrichi())
    assert d['dernier_qso']['indicatif'] == 'F4ABC'   # 20260905, le plus récent
    assert d['premier_qso']['indicatif'] == 'F4ABC'   # 20260901, le plus ancien


def test_digest_vide_ne_leve_pas():
    d = cq.digest([])
    assert d['total_qso'] == 0
    assert d['dernier_qso'] is None
    assert d['premier_qso'] is None
    assert d['meilleur_dx'] is None


def test_digest_sans_locator_pas_de_meilleur_dx():
    d = cq.digest(_log_enrichi(), my_locator=None)
    assert d['meilleur_dx'] is None


def test_digest_avec_locator_appelle_dx_records(monkeypatch):
    import logx_awards as awards
    appels = []

    def _faux_dx_records(my_locator, shared_log):
        appels.append((my_locator, shared_log))
        return {'overall': {'call': 'W1AW', 'band': '40m', 'mode': 'CW',
                             'date': '20260902', 'dist_km': 6011.4}}
    monkeypatch.setattr(awards, 'dx_records', _faux_dx_records)
    d = cq.digest(_log_enrichi(), my_locator='JN18')
    assert len(appels) == 1
    assert appels[0][0] == 'JN18'
    assert d['meilleur_dx'] == {'indicatif': 'W1AW', 'bande': '40m', 'mode': 'CW',
                                 'date': '02/09/2026', 'distance_km': 6011}


def test_digest_dx_records_sans_overall_reste_none(monkeypatch):
    import logx_awards as awards
    monkeypatch.setattr(awards, 'dx_records', lambda *a, **k: {'overall': None})
    d = cq.digest(_log_enrichi(), my_locator='JN18')
    assert d['meilleur_dx'] is None


def test_construire_prompt_utilisateur_contient_la_question_et_les_chiffres():
    d = cq.digest(_log_enrichi())
    p = cq.construire_prompt_utilisateur('quel est mon meilleur DX ?', d)
    assert 'QUESTION : quel est mon meilleur DX ?' in p
    assert 'Total QSO : 4' in p
    assert 'F4ABC' in p


def test_construire_prompt_utilisateur_tolere_digest_vide():
    p = cq.construire_prompt_utilisateur('bonjour', cq.digest([]))
    assert 'QUESTION : bonjour' in p
    assert 'Total QSO : 0' in p


def test_systeme_ia_interdit_explicitement_lecriture():
    # Le prompt système doit porter l'interdiction en toutes lettres --
    # c'est la seule barrière DANS le prompt (le vrai verrou est structurel :
    # ce chemin n'appelle jamais call_llm_actions, voir
    # test_invariants_securite.py::test_i2_log_question_palier_ia...).
    assert 'enregistrer' in cq.SYSTEME_IA or 'écrire' in cq.SYSTEME_IA.lower()
    assert 'QSO' in cq.SYSTEME_IA


# ═══════════════════════════════════════════════════════════════════════════
# Invariant I2 -- les nouvelles fonctions n'écrivent jamais dans le log.
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('appel', [
    lambda log: cq.digest(log),
    lambda log: cq.digest(log, my_locator='JN18'),
    lambda log: cq.construire_prompt_utilisateur('x', cq.digest(log)),
])
def test_aucune_fonction_ia_ne_modifie_le_log(appel, monkeypatch):
    import logx_awards as awards
    monkeypatch.setattr(awards, 'dx_records', lambda *a, **k: {'overall': None})
    log = _log_enrichi()
    avant = copy.deepcopy(log)
    appel(log)
    assert log == avant, "une fonction du palier IA a modifié le log en place"
