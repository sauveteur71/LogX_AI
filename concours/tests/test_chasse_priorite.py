# -*- coding: utf-8 -*-
"""Détecteur de crédit + score de priorité CHASSE (logx_chasse_priorite).
Compose la grille bande×mode de logx_awards.lotw_grid ; ici on teste la
CLASSIFICATION et le SCORE (profil d'objectifs, malus doublon)."""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_chasse_priorite as cp  # noqa: E402


def _grille(cells):
    """cells: {(band, mode): statut}. Complète en 'none' les créneaux absents
    pour les bandes/modes cités."""
    bands = sorted({b for b, _ in cells})
    modes = ('CW', 'PHONE', 'DIGITAL')
    grid = {b: {m: 'none' for m in modes} for b in bands}
    for (b, m), st in cells.items():
        grid.setdefault(b, {m2: 'none' for m2 in modes})[m] = st
    return {'active': True, 'country': 'Japan', 'grid': grid}


# ─── classer_dxcc ──────────────────────────────────────────────────────────

def test_entite_inconnue():
    assert cp.classer_dxcc({'active': False}, '20M', 'CW') == cp.CLASSE_INCONNU
    assert cp.classer_dxcc(None, '20M', 'CW') == cp.CLASSE_INCONNU


def test_atno_jamais_travaille():
    g = _grille({('20M', 'CW'): 'none', ('40M', 'PHONE'): 'none'})
    assert cp.classer_dxcc(g, '20M', 'CW') == cp.CLASSE_ATNO


def test_creneau_confirme_est_doublon():
    g = _grille({('20M', 'DIGITAL'): 'confirmed'})
    assert cp.classer_dxcc(g, '20M', 'DIGITAL') == cp.CLASSE_CONFIRMED


def test_creneau_travaille_non_confirme():
    g = _grille({('20M', 'DIGITAL'): 'worked'})
    assert cp.classer_dxcc(g, '20M', 'DIGITAL') == cp.CLASSE_NEEDED_CONFIRM


def test_nouvelle_bande():
    # entité faite sur 20M, mais 40M jamais -> nouvelle bande sur 40M
    g = _grille({('20M', 'DIGITAL'): 'confirmed', ('40M', 'CW'): 'none'})
    assert cp.classer_dxcc(g, '40M', 'CW') == cp.CLASSE_NEW_BAND


def test_nouveau_mode():
    # 20M déjà faite en DIGITAL, mais jamais en CW sur 20M -> nouveau mode
    g = _grille({('20M', 'DIGITAL'): 'confirmed', ('20M', 'CW'): 'none'})
    assert cp.classer_dxcc(g, '20M', 'CW') == cp.CLASSE_NEW_MODE


def test_exemple_doc_japon_cw():
    """Doc F4GLD : Japon fait en 20m FT8 et 40m FT8, jamais en CW.
    Un Japonais en CW sur 20 m -> nouveau MODE (pas ATNO, pas nouvelle bande)."""
    g = _grille({('20M', 'DIGITAL'): 'confirmed', ('40M', 'DIGITAL'): 'confirmed',
                 ('20M', 'CW'): 'none'})
    assert cp.classer_dxcc(g, '20M', 'CW') == cp.CLASSE_NEW_MODE


# ─── score_classe ──────────────────────────────────────────────────────────

def test_score_defaut_doc():
    assert cp.score_classe(cp.CLASSE_ATNO) == 1000
    assert cp.score_classe(cp.CLASSE_NEW_BAND) == 600
    assert cp.score_classe(cp.CLASSE_NEW_MODE) == 500
    assert cp.score_classe(cp.CLASSE_NEEDED_CONFIRM) == 200
    assert cp.score_classe(cp.CLASSE_CONFIRMED) == -900


def test_objectif_desactive_annule_le_credit():
    off = {'dxcc': False}
    assert cp.score_classe(cp.CLASSE_ATNO, objectifs=off) == 0
    # un autre objectif reste actif par défaut
    assert cp.score_classe(cp.CLASSE_NEW_BAND, objectifs=off) == 600


def test_malus_doublon_toujours_applique():
    # même profil « tout coupé », le doublon confirmé garde son malus
    assert cp.score_classe(cp.CLASSE_CONFIRMED,
                           objectifs={'dxcc': False, 'lotw_confirmation_priority': False}) == -900


def test_poids_surchargeables():
    assert cp.score_classe(cp.CLASSE_ATNO, poids={'atno': 1234}) == 1234


# ─── evaluer (composite) ───────────────────────────────────────────────────

def test_evaluer_compose_classe_score_raison():
    g = _grille({('20M', 'DIGITAL'): 'confirmed', ('20M', 'CW'): 'none'})
    r = cp.evaluer(g, '20M', 'CW')
    assert r['classe'] == cp.CLASSE_NEW_MODE
    assert r['score'] == 500
    assert 'mode' in r['raison'].lower()


# ─── evaluer_grid (crédit carré VHF/UHF) ───────────────────────────────────

def test_grid_neuf_donne_credit_new_grid():
    r = cp.evaluer_grid(True)
    assert r is not None
    assert r['classe'] == cp.CLASSE_NEW_GRID
    assert r['score'] == 450
    assert r['raison']


def test_grid_deja_fait_ne_donne_aucun_credit():
    assert cp.evaluer_grid(False) is None


def test_grid_objectif_vucc_desactive_annule_le_credit():
    # Objectif désactivé -> AUCUN crédit (None). Renvoyer un dict à score 0
    # laisserait la fusion par max (annoter_credit) écraser une classification
    # DXCC légitime : 0 > -900 remplacerait un doublon CONFIRMÉ par un
    # « new_grid » neutre. Le contrat du module : « un objectif désactivé
    # annule le crédit correspondant » -> None, pas score 0.
    assert cp.evaluer_grid(True, objectifs={'vucc': False}) is None


def test_grid_poids_surchargeable():
    r = cp.evaluer_grid(True, poids={'new_grid': 777})
    assert r['score'] == 777
