# -*- coding: utf-8 -*-
"""Lot 2 — matrice d'accréditation (diplôme × source).

Une confirmation eQSL est une confirmation indépendante ; le CRÉDIT de diplôme
est évalué par une matrice SOURCÉE. Règle absente ⇒ UNKNOWN ⇒ aucun crédit
automatique. Jamais de règle globale « eQSL crédite tout sauf X »
(décision F4GLD 26/08/2026)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_award_credit as ac


def test_eqsl_ne_credite_jamais_les_diplomes_arrl():
    for aid in ('ARRL_DXCC', 'ARRL_DXCC_CHALLENGE', 'ARRL_WAS', 'ARRL_VUCC', 'ARRL_WAC'):
        r = ac.evaluer_credit(aid, 'eqsl')
        assert r['status'] == ac.CreditStatus.DENIED, aid
        assert ac.credite(aid, 'eqsl') is False, aid


def test_lotw_credite_les_diplomes_arrl():
    assert ac.credite('ARRL_DXCC', 'lotw') is True
    assert ac.evaluer_credit('ARRL_DXCC', 'lotw')['status'] == ac.CreditStatus.ALLOWED


def test_award_inconnu_est_unknown_sans_credit():
    r = ac.evaluer_credit('ZZ_AWARD_INEXISTANT', 'eqsl')
    assert r['status'] == ac.CreditStatus.UNKNOWN
    assert ac.credite('ZZ_AWARD_INEXISTANT', 'eqsl') is False


def test_cq_waz_eqsl_non_source_ne_credite_pas_auto():
    # Pas de règle sourcée pour CQ_WAZ/eQSL -> UNKNOWN -> aucun crédit auto.
    assert ac.credite('CQ_WAZ', 'eqsl') is False


def test_source_insensible_a_la_casse():
    assert ac.credite('ARRL_DXCC', 'LoTW') is True


def test_regles_arrl_portent_une_source():
    # Chaque règle DENIED eQSL doit citer une source (traçabilité).
    r = ac.evaluer_credit('ARRL_DXCC', 'eqsl')
    assert r.get('source_url')
