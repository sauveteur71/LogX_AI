# -*- coding: utf-8 -*-
"""La date limite de dépôt, en vraie date.

LE DÉFAUT : le champ `log_deadline` des définitions porte des CODES
(« wednesday_after », « second_monday_after », « 7_days_after »…) et ils
étaient affichés TELS QUELS. Le coach annonçait à l'opérateur, en fin
d'épreuve : « deadline : wednesday_after ». Cela ne lui dit ni le jour, ni s'il
lui reste quatre jours, ni s'il est déjà en retard — pour la seule échéance du
concours qui, une fois manquée, annule toute la participation.

RÈGLE TENUE ICI : on résout quand le code est interprétable, et on laisse le
texte brut intact sinon. Une date fausse au jour près sur une échéance de dépôt
serait pire que pas de date du tout — cinq définitions portent un délai en
texte libre (« 14 jours », « 30 jours »), il ne faut RIEN inventer dessus.
"""
import datetime
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

from logx_coach import _deadline_lisible          # noqa: E402
from logx_definitions import CONTEST_DEFINITIONS  # noqa: E402
from logx_utils import date_limite_depot          # noqa: E402

# Dimanche 5 juillet 2026 — fin typique d'un concours de week-end.
DIMANCHE = datetime.date(2026, 7, 5)


@pytest.mark.parametrize('code, attendu', [
    ('wednesday_after',     datetime.date(2026, 7, 8)),
    ('second_monday_after', datetime.date(2026, 7, 13)),
    ('7_days_after',        datetime.date(2026, 7, 12)),
    ('5_days_after',        datetime.date(2026, 7, 10)),
    ('8_days_after',        datetime.date(2026, 7, 13)),
    ('48_hours_after',      datetime.date(2026, 7, 7)),
])
def test_les_codes_de_la_base_se_resolvent_en_date(code, attendu):
    assert date_limite_depot(code, DIMANCHE)[0] == attendu


def test_le_jour_de_semaine_vise_est_STRICTEMENT_apres_la_fin():
    """Un concours qui finit un mercredi doit viser le mercredi SUIVANT, pas
    le jour même : sinon l'échéance serait déjà passée à l'affichage."""
    mercredi = datetime.date(2026, 7, 1)
    assert date_limite_depot('wednesday_after', mercredi)[0] == \
        datetime.date(2026, 7, 8)


@pytest.mark.parametrize('libre', ['14 jours', '30 jours',
                                   'Mardi 28 juillet (28 days after)',
                                   'à confirmer', ''])
def test_un_delai_en_TEXTE_LIBRE_n_est_jamais_transforme_en_date(libre):
    d, brut = date_limite_depot(libre, DIMANCHE)
    assert d is None
    assert brut == libre.strip()


def test_sans_date_de_fin_on_n_invente_rien():
    assert date_limite_depot('wednesday_after', None) == (None, 'wednesday_after')


# ─── Le texte lu par l'opérateur ────────────────────────────────────────────

def test_le_coach_annonce_un_jour_et_un_compte_a_rebours():
    txt = _deadline_lisible('wednesday_after', '2026-07-05 14:00',
                            datetime.date(2026, 7, 4))
    assert txt == 'mercredi 8 juillet, dans 4 jours'
    assert 'wednesday_after' not in txt


@pytest.mark.parametrize('jour, marqueur', [
    (datetime.date(2026, 7, 7), 'demain'),
    (datetime.date(2026, 7, 8), "AUJOURD'HUI"),
    (datetime.date(2026, 7, 20), 'DÉPASSÉE'),
])
def test_l_urgence_est_dite_en_clair(jour, marqueur):
    """« DÉPASSÉE » doit être dit franchement : certains organisateurs
    acceptent encore un log en retard, mais l'opérateur doit le savoir."""
    assert marqueur in _deadline_lisible('wednesday_after',
                                         '2026-07-05 14:00', jour)


def test_le_texte_brut_survit_quand_la_fin_est_inconnue():
    assert _deadline_lisible('wednesday_after', None) == 'wednesday_after'
    assert _deadline_lisible('wednesday_after', 'pas une date') == 'wednesday_after'


# ─── Sur la base réelle ─────────────────────────────────────────────────────

def test_la_majorite_des_delais_de_la_base_sont_resolus():
    """Si ce compte s'effondre, c'est qu'un nouveau code est apparu dans les
    définitions sans être reconnu — et l'opérateur reverrait du jargon."""
    codes = [d.get('log_deadline', '') for d in CONTEST_DEFINITIONS.values()]
    codes = [c for c in codes if str(c).strip()]
    resolus = [c for c in codes if date_limite_depot(c, DIMANCHE)[0] is not None]
    assert len(resolus) >= 30, (
        '%d délais résolus sur %d — un code non reconnu est apparu'
        % (len(resolus), len(codes)))


def test_aucun_delai_resolu_ne_tombe_AVANT_la_fin_du_concours():
    """Une échéance antérieure à la fin de l'épreuve serait absurde et ferait
    afficher « DÉPASSÉE » à un opérateur parfaitement dans les temps."""
    for cid, d in CONTEST_DEFINITIONS.items():
        code = d.get('log_deadline', '')
        if not str(code).strip():
            continue
        date, _ = date_limite_depot(code, DIMANCHE)
        if date is not None:
            assert date > DIMANCHE, '%s : échéance %s avant la fin' % (cid, date)
