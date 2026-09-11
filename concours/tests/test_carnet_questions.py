# -*- coding: utf-8 -*-
"""Tests du module de questions déterministes sur le carnet (C1, incrément 1).

Cadrage : docs/superpowers/specs/2026-09-11-c1-requetes-langage-naturel-
carnet.md, validé par F4GLD (« logbook » = intégré au LOGBOOK) le 11/09/2026.

Portée volontairement étroite -- même raisonnement que le palier « Basique »
de Carte IA (logx_carte.html, AI_TIER_BASIQUE_TOPICS) : un jeu FIXE de
questions calculables directement en Python (0 jeton, 0 appel LLM), PAS une
tentative de comprendre du texte libre arbitraire sans modèle. Le seul
répertoire de texte libre accepté ici (extraire_indicatif_deja_travaille) est
un motif étroit documenté comme tel, jamais présenté comme une compréhension
générale du langage.

Invariant I2 (0 écriture QSO par le LLM, test_invariants_securite.py) :
aucune fonction de ce module ne modifie jamais `log` -- vérifié ci-dessous
par un test dédié qui compare le contenu du log avant/après chaque appel.
"""
import copy
import os
import sys

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import logx_carnet_questions as cq  # noqa: E402


def _log():
    return [
        {'id': 1, 'call': 'F4ABC', 'band': '20m', 'mode': 'SSB', 'date': '20260901', 'time': '10:00'},
        {'id': 2, 'call': 'W1AW', 'band': '40m', 'mode': 'CW', 'date': '20260902', 'time': '11:00'},
        {'id': 3, 'call': 'F4ABC', 'band': '20m', 'mode': 'FT8', 'date': '20260905', 'time': '09:00'},
        {'id': 4, 'call': 'DL1XYZ', 'band': '40m', 'mode': 'CW', 'date': '20260903', 'time': '12:00'},
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Agrégats purs
# ═══════════════════════════════════════════════════════════════════════════

def test_total_qso():
    assert cq.total_qso(_log()) == 4
    assert cq.total_qso([]) == 0


def test_par_bande_trie_par_nombre_decroissant():
    d = cq.par_bande(_log())
    assert d == {'20m': 2, '40m': 2}


def test_par_bande_log_vide():
    assert cq.par_bande([]) == {}


def test_par_bande_bande_absente_devient_point_interrogation():
    d = cq.par_bande([{'call': 'X'}])
    assert d == {'?': 1}


def test_par_mode_normalise_en_majuscules():
    d = cq.par_mode([{'mode': 'ssb'}, {'mode': 'SSB'}, {'mode': 'cw'}])
    assert d == {'SSB': 2, 'CW': 1}


def test_dernier_qso_prend_le_plus_recent_par_date_puis_heure():
    d = cq.dernier_qso(_log())
    assert d['id'] == 3   # 20260905, le plus récent


def test_dernier_qso_log_vide_rend_none():
    assert cq.dernier_qso([]) is None


def test_deja_travaille_insensible_casse_et_espaces():
    r = cq.deja_travaille(_log(), '  f4abc  ')
    assert len(r) == 2
    assert {q['id'] for q in r} == {1, 3}


def test_deja_travaille_trie_du_plus_recent():
    r = cq.deja_travaille(_log(), 'F4ABC')
    assert r[0]['id'] == 3   # 20260905 avant 20260901


def test_deja_travaille_aucun_resultat():
    assert cq.deja_travaille(_log(), 'ZZ9ZZZ') == []


def test_deja_travaille_indicatif_vide():
    assert cq.deja_travaille(_log(), '') == []
    assert cq.deja_travaille(_log(), None) == []


def test_qso_sur_periode_bornes_incluses():
    r = cq.qso_sur_periode(_log(), '20260902', '20260903')
    assert {q['id'] for q in r} == {2, 4}


# ═══════════════════════════════════════════════════════════════════════════
# repondre() -- dispatch question rapide -> texte français.
# ═══════════════════════════════════════════════════════════════════════════

def test_repondre_total():
    assert '4' in cq.repondre(_log(), 'total')


def test_repondre_total_carnet_vide():
    assert 'vide' in cq.repondre([], 'total').lower()


def test_repondre_par_bande_contient_chaque_bande():
    r = cq.repondre(_log(), 'par_bande')
    assert '20m' in r and '40m' in r


def test_repondre_par_mode_contient_chaque_mode():
    r = cq.repondre(_log(), 'par_mode')
    assert 'SSB' in r and 'CW' in r and 'FT8' in r


def test_repondre_dernier():
    r = cq.repondre(_log(), 'dernier')
    assert 'F4ABC' in r


def test_repondre_dernier_carnet_vide():
    assert 'Aucun QSO' in cq.repondre([], 'dernier')


def test_repondre_deja_travaille_trouve():
    r = cq.repondre(_log(), 'deja_travaille', {'indicatif': 'F4ABC'})
    assert 'F4ABC' in r and '2' in r


def test_repondre_deja_travaille_absent():
    r = cq.repondre(_log(), 'deja_travaille', {'indicatif': 'ZZ9ZZZ'})
    assert 'Aucun' in r


def test_repondre_question_inconnue_leve():
    with pytest.raises(ValueError):
        cq.repondre(_log(), 'question_qui_n_existe_pas')


@pytest.mark.parametrize('topic', list(cq.TOPICS))
def test_repondre_couvre_tous_les_topics_declares(topic):
    """Chaque topic de TOPICS doit être géré par repondre() -- sinon la liste
    affichée côté UI proposerait un bouton qui lève ValueError au clic."""
    cq.repondre(_log(), topic, {'indicatif': 'F4ABC'})


# ═══════════════════════════════════════════════════════════════════════════
# extraire_indicatif_deja_travaille() -- motif étroit, PAS un parseur NLP.
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('texte,attendu', [
    ("Ai-je déjà travaillé F4ABC ?", 'F4ABC'),
    ("j'ai déjà travaillé W1AW en CW ?", 'W1AW'),
    ("As-tu travaillé DL1XYZ cette année", 'DL1XYZ'),
    ("j'ai déjà travaillé F4ABC/P ?", 'F4ABC/P'),
])
def test_extraire_indicatif_motif_reconnu(texte, attendu):
    assert cq.extraire_indicatif_deja_travaille(texte) == attendu


@pytest.mark.parametrize('texte', [
    "",
    None,
    "combien de QSO en 20m ce mois-ci ?",
    "j'ai déjà travaillé le Japon ?",   # pas de token indicatif -- hors scope
    "quel est mon meilleur DX ?",
])
def test_extraire_indicatif_motif_non_reconnu_rend_none(texte):
    assert cq.extraire_indicatif_deja_travaille(texte) is None


# ═══════════════════════════════════════════════════════════════════════════
# Invariant I2 -- aucune fonction de ce module n'écrit jamais dans le log.
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('appel', [
    lambda log: cq.total_qso(log),
    lambda log: cq.par_bande(log),
    lambda log: cq.par_mode(log),
    lambda log: cq.dernier_qso(log),
    lambda log: cq.deja_travaille(log, 'F4ABC'),
    lambda log: cq.qso_sur_periode(log, '20260101', '20261231'),
    lambda log: cq.repondre(log, 'total'),
    lambda log: cq.repondre(log, 'deja_travaille', {'indicatif': 'F4ABC'}),
])
def test_aucune_fonction_ne_modifie_le_log(appel):
    log = _log()
    avant = copy.deepcopy(log)
    appel(log)
    assert log == avant, "une fonction de questions a modifié le log en place"
