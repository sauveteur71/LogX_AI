# -*- coding: utf-8 -*-
"""Coaching pré-QSO (calc_qso_value/MULT_EVALUATORS) pour le multiplicateur
'rtty_ru' (ARRL RTTY Roundup) -- trou trouvé le 12/09/2026 : le SCORE
autoritaire (calc_total_score, cf. test_mult_rtty.py, PR #254) tenait déjà
compte des états/provinces W/VE et des entités DXCC, mais AUCUN évaluateur
n'était enregistré dans MULT_EVALUATORS pour 'rtty_ru' -- un spot RTTY
Roundup tombait dans le repli « pas de multiplicateur », priorité par
palier de DISTANCE (`priority_thresholds`), non pertinent pour un concours
qui n'en tient aucun compte (1 pt/QSO × mult).

Portée volontairement étroite (décision F4GLD 12/09/2026, question à
choix) : uniquement ce trou-là. Le cas CQ WW RTTY ('zone_dxcc_state') reste
un choix délibéré et documenté (coaching = zone+DXCC seuls, l'état n'est
connaissable qu'à réception de l'échange) -- non touché ici.

Pour une station K/VE, l'état/province exact reste inconnaissable au stade
du spot (même limite que zone_dxcc_state) -- approximé par un PROXY
préfixe d'indicatif (3 premiers caractères), EXACTE même technique déjà
en production pour _mult_na_state (ARRL DX). Pour une station hors K/VE,
l'entité DXCC EST connaissable au stade du spot (déduite de l'indicatif) --
traité comme _mult_dxcc_only mais suivi GLOBALEMENT (all-band, comme
l'exige le règlement RTTY Roundup §5.3), jamais par bande."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_scoring as scoring        # noqa: E402
import logx_storage as st             # noqa: E402
from logx_scoring import calc_qso_value, build_ranked_spots  # noqa: E402


def _val(dx, done_dxcc_global=None, done_rtty_ru_proxies=None, current_score=0):
    return calc_qso_value(
        'ARRL_RTTY_ROUNDUP', dx, '', 'F6KQJ', 'JN15XC',
        {}, set(), set(), {}, {}, current_score,
        band='14', dist_km=0,
        done_dxcc_global=done_dxcc_global, done_rtty_ru_proxies=done_rtty_ru_proxies,
    )


# ─── Régression du trou lui-même : un évaluateur DOIT être enregistré ───────

def test_rtty_ru_a_un_evaluateur_enregistre():
    assert scoring.MULT_EVALUATORS.get('rtty_ru') is not None


def test_sans_evaluateur_le_repli_distance_est_absurde_pour_ce_concours():
    """Documente EXACTEMENT le symptôme du trou (pour qu'une régression future
    -- désenregistrement accidentel de 'rtty_ru' -- le fasse réapparaître de
    façon visible) : retirer temporairement l'évaluateur fait retomber sur
    priority_thresholds (repli 'pas de multiplicateur'), qui n'existe même
    pas pour ce barème (aucune brique 'priority_thresholds' dans le preset
    rtty_roundup) -- priority retombe alors sur priority_default=5 quel que
    soit le DX, un classement inutilisable."""
    original = scoring.MULT_EVALUATORS.pop('rtty_ru')
    try:
        r = _val('F6ABC')
        assert r['priority'] == 5   # aucune information de mult exploitée
    finally:
        scoring.MULT_EVALUATORS['rtty_ru'] = original


# ─── Station hors K/VE : DXCC connaissable au stade du spot ─────────────────

def test_dx_nouveau_dxcc_priorite_maximale():
    r = _val('F6ABC', done_dxcc_global=set())
    assert r['new_mult'] is True
    assert r['mult_type'] == 'dxcc'
    assert r['priority'] == 1


def test_dx_dxcc_deja_connu_pas_de_nouveau_mult():
    r = _val('F6ABC', done_dxcc_global={'F'})
    assert r['new_mult'] is False
    assert r['priority'] == 3


def test_dx_kl7_kh6_traites_comme_dxcc_jamais_comme_etat():
    """Alaska/Hawaii : entité DXCC distincte (KL/KH6), jamais suivie via
    done_rtty_ru_proxies -- même règle que le score autoritaire
    (test_mult_rtty.py::test_rtty_roundup_dxcc_exclut_pas_ak_hi_du_compte)."""
    r = _val('KL7RA', done_dxcc_global=set(), done_rtty_ru_proxies=set())
    assert r['new_mult'] is True
    assert r['mult_type'] == 'dxcc'


# ─── Station K/VE : état/province inconnaissable au spot -> proxy préfixe ───

def test_kve_prefixe_jamais_vu_reste_probable_nouveau_mult():
    r = _val('W1AAA', done_rtty_ru_proxies=set())
    assert r['new_mult'] is True
    assert r['mult_type'] == 'etat_province'
    assert 'probable' in r['explanation'].lower()
    assert r['priority'] == 1


def test_kve_meme_prefixe_deja_vu_pas_de_nouveau_mult():
    # 'W1A' = les 3 premiers caractères de W1AAA ET W1ABC (même proxy).
    r = _val('W1ABC', done_rtty_ru_proxies={'W1A'})
    assert r['new_mult'] is False
    assert r['priority'] == 3


def test_kve_ve_egalement_couvert():
    r = _val('VE3XYZ', done_rtty_ru_proxies=set())
    assert r['new_mult'] is True
    assert r['mult_type'] == 'etat_province'


# ─── Le mult est GLOBAL (all-band), pas par bande ───────────────────────────

def test_ctx_expose_bien_les_deux_sets_globaux_sans_notion_de_bande():
    """calc_qso_value ne reçoit aucun paramètre 'band' pour done_dxcc_global/
    done_rtty_ru_proxies (contrairement à done_dxcc/done_na_proxies, des
    dicts band->set) -- la signature elle-même impose le caractère
    all-band, pas seulement la logique de _mult_rtty_ru."""
    import inspect
    sig = inspect.signature(calc_qso_value)
    assert 'done_dxcc_global' in sig.parameters
    assert 'done_rtty_ru_proxies' in sig.parameters


# ─── Bout en bout : build_ranked_spots peuple et transmet les 2 sets ────────

def _isolated(fn):
    saved = list(st.shared_log)
    st.shared_log[:] = []
    try:
        return fn()
    finally:
        st.shared_log[:] = saved


def _cfg():
    return {'contest': 'ARRL_RTTY_ROUNDUP', 'callsign_contest': 'F6KQJ', 'locator': 'JN15XC'}


def test_build_ranked_spots_peuple_les_sets_globaux_depuis_le_log():
    """Un DXCC déjà travaillé sur 14 MHz doit rester 'déjà compté' pour un
    NOUVEAU spot du MÊME pays sur 7 MHz -- preuve que le suivi est bien
    GLOBAL (comme peuplé par _mark_country_zone) et pas remis à zéro par
    bande, contrairement à done_dxcc classique."""
    def _run():
        st.shared_log.append({'call': 'F5XX', 'band': '14', 'mode': 'RTTY',
                              'contest': 'ARRL_RTTY_ROUNDUP', 'date': '20260101',
                              'time': '1000', 'points': 1})
        spot = {'dx': 'F6ABC', 'locator': '', 'info': '', 'spotter': 'W1AW',
                'freq': 7040.0, 'mode': 'RTTY', 'source': 'cluster'}
        return build_ranked_spots({}, {'7': [spot]}, _cfg())
    ranked, meta = _isolated(_run)
    assert len(ranked) == 1
    assert ranked[0]['scoring']['new_mult'] is False   # DXCC 'F' déjà compté (globalement)


def test_build_ranked_spots_dxcc_neuf_priorite_haute():
    def _run():
        spot = {'dx': 'JA1XYZ', 'locator': '', 'info': '', 'spotter': 'W1AW',
                'freq': 14090.0, 'mode': 'RTTY', 'source': 'cluster'}
        return build_ranked_spots({}, {'14': [spot]}, _cfg())
    ranked, meta = _isolated(_run)
    assert ranked[0]['scoring']['new_mult'] is True
    assert ranked[0]['scoring']['mult_type'] == 'dxcc'
