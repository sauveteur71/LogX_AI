# -*- coding: utf-8 -*-
"""Matrice d'accréditation (diplôme × source de confirmation).

Une confirmation (LoTW/eQSL/papier…) est une chose ; le CRÉDIT qu'elle donne à
un diplôme donné en est une autre — chaque organisation a ses règles. Ce module
répond à « la source S crédite-t-elle le diplôme D ? » via une matrice de règles
SOURCÉES (URL + date de vérification + version du règlement).

Décision F4GLD (26/08/2026) :
  - JAMAIS de règle globale « eQSL crédite tout sauf X » ;
  - une règle ABSENTE ⇒ UNKNOWN ⇒ aucun crédit automatique ;
  - une confirmation eQSL reste affichée « confirmée eQSL » même sans crédit.

eQSL n'est accepté par AUCUN diplôme ARRL (DXCC, DXCC Challenge, WAS, VUCC,
WAC) — source ARRL vérifiée : « electronically transmitted confirmations ...
are not currently acceptable for DXCC purposes. Exception: ... Logbook of the
World ... are acceptable. » (arrl.org/e-qsl-policy, vérifié 2026-08-26).
"""
from dataclasses import dataclass, field
from enum import Enum


class CreditStatus(Enum):
    ALLOWED = 'allowed'          # la source crédite ce diplôme
    DENIED = 'denied'            # explicitement refusée par le règlement
    CONDITIONAL = 'conditional'  # acceptée sous conditions (non auto-créditée ici)
    UNKNOWN = 'unknown'          # aucune règle sourcée ⇒ pas de crédit auto


@dataclass(frozen=True)
class AwardCreditRule:
    award_id: str
    source: str                  # 'LOTW', 'EQSL', 'PAPER'… (comparé sans casse)
    status: CreditStatus
    source_url: str = ''
    verified_at_utc: str = ''
    rules_version: str = 'current'
    conditions: tuple = field(default_factory=tuple)


_ARRL_EQSL = 'https://www.arrl.org/e-qsl-policy'
_VERIF = '2026-08-26'

# Diplômes ARRL suivis par logx_awards (mapping utilisé au lot 3).
_ARRL_AWARDS = ('ARRL_DXCC', 'ARRL_DXCC_CHALLENGE', 'ARRL_WAS', 'ARRL_VUCC', 'ARRL_WAC')

AWARD_RULES = []
# LoTW crédite les diplômes ARRL (comportement historique : la seule
# confirmation électronique acceptée par l'ARRL).
for _aid in _ARRL_AWARDS:
    AWARD_RULES.append(AwardCreditRule(_aid, 'LOTW', CreditStatus.ALLOWED,
                                       _ARRL_EQSL, _VERIF))
# eQSL : REFUSÉE par tous les diplômes ARRL (sourcé).
for _aid in _ARRL_AWARDS:
    AWARD_RULES.append(AwardCreditRule(_aid, 'EQSL', CreditStatus.DENIED,
                                       _ARRL_EQSL, _VERIF))
# QSL papier : acceptée par les diplômes ARRL (règle classique DXCC/WAS…).
for _aid in _ARRL_AWARDS:
    AWARD_RULES.append(AwardCreditRule(_aid, 'PAPER', CreditStatus.ALLOWED,
                                       _ARRL_EQSL, _VERIF))
# CQ WAZ / autres programmes CQ, DX-Field, départements : règles eQSL NON
# encore sourcées -> volontairement ABSENTES -> UNKNOWN -> aucun crédit auto.
# Ajouter ici une AwardCreditRule dès qu'une source officielle est vérifiée.

_INDEX = {(r.award_id, r.source.upper()): r for r in AWARD_RULES}


def evaluer_credit(award_id, source):
    """{status, reason, source_url} pour (diplôme × source). Règle absente ⇒
    UNKNOWN (jamais de crédit automatique)."""
    r = _INDEX.get((award_id, (source or '').upper()))
    if r is None:
        return {'status': CreditStatus.UNKNOWN,
                'reason': 'Aucune règle d’accréditation sourcée', 'source_url': ''}
    if r.status == CreditStatus.CONDITIONAL:
        return {'status': CreditStatus.CONDITIONAL,
                'reason': 'Acceptée sous conditions du programme (à vérifier)',
                'source_url': r.source_url}
    reason = ('Source acceptée par le règlement' if r.status == CreditStatus.ALLOWED
              else 'Source non acceptée par le règlement')
    return {'status': r.status, 'reason': reason, 'source_url': r.source_url}


def credite(award_id, source):
    """True SEULEMENT si la source crédite ce diplôme sans condition (ALLOWED).
    DENIED / CONDITIONAL / UNKNOWN ⇒ False (aucun crédit automatique)."""
    return evaluer_credit(award_id, source)['status'] == CreditStatus.ALLOWED
