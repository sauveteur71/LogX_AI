# -*- coding: utf-8 -*-
"""Challenge THF (REF, permanent) -- moteur de scoring dédié.

SOURCE : règlement PDF officiel REF lu intégralement le 13/09/2026 via
l'outil de lecture PDF (pas WebFetch, qui échoue sur ce PDF -- flux binaire
non décompressable par son résumé automatique) :
  reg_challengethf_fr_20251209.pdf (9 décembre 2025)

DÉCOUVERTE qui motive ce fichier : l'ancien CONTEST_SCORING affichait
'type':'km_x_loc', 'unit':'1pt/km x locators' -- AUCUNE notion de distance
dans le règlement. Le vrai barème (art. 9) :
  - 1 point par station NEUVE contactée, par MOIS et par BANDE (une même
    station ne compte qu'une fois par mois par bande -- art. 4) ;
  - multiplicateur = nombre de départements + nombre de grands carrés
    locator distincts, comptés PAR BANDE et PAR TRIMESTRE ;
  - coefficient par bande : 144 MHz=1, 432 MHz=3, 1296 MHz=5, 2320 MHz et
    au-delà=10 ;
  - score bande = points × (départements+locators) × coef ;
  - cumul annuel = somme des 4 scores trimestriels (art. 8).

Moteur délibérément SÉPARÉ du moteur générique bricks/count_mults/
calc_total_score : ce dernier ferait (somme des points toutes bandes) ×
(somme des mults pondérés toutes bandes), alors que le règlement exige un
coefficient propre à CHAQUE bande multiplié indépendamment avant de sommer.

MVP (décision F4GLD, 13/09/2026) : CONTEST_DEFINITIONS n'expose que 144/432
MHz -- le moteur (CHALLENGE_THF_COEF_BAND) connaît déjà tout le barème
officiel, prêt à étendre sans nouveau code de calcul.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

from logx_definitions import CONTEST_DEFINITIONS   # noqa: E402
import logx_scoring as scoring                       # noqa: E402
import logx_validate as validate                     # noqa: E402


def test_la_definition_est_presente_et_valide():
    assert 'REF_CHALLENGE_THF' in CONTEST_DEFINITIONS
    erreurs = validate.validate_definition(
        CONTEST_DEFINITIONS['REF_CHALLENGE_THF'], 'REF_CHALLENGE_THF')
    assert erreurs == []


def test_mvp_144_432_seulement():
    """Décision F4GLD 13/09/2026 : portée MVP, pas encore 1296/2320+."""
    assert CONTEST_DEFINITIONS['REF_CHALLENGE_THF']['bands'] == ['144', '432']


# ─── Coefficients sourcés (règlement, art. 9) ────────────────────────────────

def test_coefficients_par_bande_sont_ceux_du_reglement():
    assert scoring.CHALLENGE_THF_COEF_BAND['144'] == 1
    assert scoring.CHALLENGE_THF_COEF_BAND['432'] == 3
    assert scoring.CHALLENGE_THF_COEF_BAND['1296'] == 5
    assert scoring.CHALLENGE_THF_COEF_BAND['2320'] == 10


def test_bande_sans_coefficient_leve_valueerror():
    import pytest
    with pytest.raises(ValueError):
        scoring.calc_challenge_thf_band([], '50')   # 6m -- hors périmètre THF


# ─── L'exemple OFFICIEL du règlement (art. 9), reproduit tel quel ───────────

def _qso(call, band, date, dept, locator):
    return {'call': call, 'band': band, 'date': date, 'dept': dept, 'locator': locator}


def test_exemple_officiel_du_reglement_144mhz():
    """« ex: en 144MHz: 450 pts*(50 départements + 40 QTH)*1 = 40500 pts. »
    (règlement, art. 9) -- reproduit avec 450 stations distinctes, 50
    départements distincts et 40 grands carrés distincts, coefficient 1."""
    import logx_departments as departements
    # 50 codes VALIDES (départements réels) -- '20' n'existe pas tel quel
    # (scindé en '2A'/'2B'), l'exclure évite qu'un code invalide retombe sur
    # une estimation géographique et fausse le compte de départements.
    depts_valides = sorted(departements.DEPARTMENTS)[:50]
    qsos = [
        _qso('F%dABC' % i, '144', '20260115',
             depts_valides[i % 50], 'JN%02d' % (i % 40))
        for i in range(450)
    ]
    r = scoring.calc_challenge_thf_band(qsos, '144')
    assert r['points'] == 450
    assert len(r['departements']) == 50
    assert len(r['grands_carres']) == 40
    assert r['coef'] == 1
    assert r['score'] == 40500


# ─── Dédoublonnage mensuel (art. 4) ──────────────────────────────────────────

def test_meme_station_meme_mois_meme_bande_compte_une_fois():
    qsos = [
        _qso('F1ABC', '144', '20260105', '75', 'JN18'),
        _qso('F1ABC', '144', '20260120', '75', 'JN18'),   # même mois -- doublon
    ]
    r = scoring.calc_challenge_thf_band(qsos, '144')
    assert r['points'] == 1


def test_meme_station_deux_mois_distincts_compte_deux_fois():
    qsos = [
        _qso('F1ABC', '144', '20260105', '75', 'JN18'),
        _qso('F1ABC', '144', '20260210', '75', 'JN18'),   # mois suivant
    ]
    r = scoring.calc_challenge_thf_band(qsos, '144')
    assert r['points'] == 2


def test_meme_station_bandes_differentes_comptees_separement():
    qsos = [
        _qso('F1ABC', '144', '20260105', '75', 'JN18'),
        _qso('F1ABC', '432', '20260105', '75', 'JN18'),
    ]
    assert scoring.calc_challenge_thf_band(qsos, '144')['points'] == 1
    assert scoring.calc_challenge_thf_band(qsos, '432')['points'] == 1


# ─── Multiplicateur = départements + grands carrés (art. 9) ────────────────

def test_multiplicateur_cumule_departements_et_locators():
    qsos = [
        _qso('F1ABC', '144', '20260105', '75', 'JN18'),
        _qso('F2DEF', '144', '20260105', '69', 'JN18'),    # même locator, dept neuf
        _qso('F3GHI', '144', '20260105', '75', 'JN25'),    # même dept, locator neuf
    ]
    r = scoring.calc_challenge_thf_band(qsos, '144')
    assert r['departements'] == ['69', '75']
    assert r['grands_carres'] == ['JN18', 'JN25']
    assert r['multiplicateur'] == 4                        # 2 depts + 2 locators
    assert r['score'] == 3 * 4 * 1                          # 3 pts * 4 mult * coef 144


def test_score_zero_si_aucun_qso_sur_la_bande():
    r = scoring.calc_challenge_thf_band([], '432')
    assert (r['points'], r['multiplicateur'], r['score']) == (0, 0, 0)


# ─── Rapport trimestre → annuel (art. 8) ────────────────────────────────────

def test_report_regroupe_par_trimestre_calendaire():
    qsos = [
        _qso('F1ABC', '144', '20260215', '75', 'JN18'),   # Q1
        _qso('F2DEF', '144', '20260615', '69', 'JN25'),   # Q2
    ]
    rap = scoring.calc_challenge_thf_report(qsos, bands=['144'])
    assert set(rap['trimestres']) == {'2026Q1', '2026Q2'}
    assert rap['trimestres']['2026Q1']['bandes']['144']['points'] == 1
    assert rap['trimestres']['2026Q2']['bandes']['144']['points'] == 1


def test_cumul_annuel_est_la_somme_des_trimestres_pas_un_recalcul_global():
    """Piège structurel documenté (art. 8 vs art. 9) : si un même département
    est vu au Q1 ET au Q2, un recalcul sur l'année entière ne le compterait
    QU'UNE FOIS (sous-comptage) -- le règlement exige la somme des scores
    trimestriels, chaque trimestre repartant de zéro pour le multiplicateur."""
    qsos = [
        _qso('F1ABC', '144', '20260115', '75', 'JN18'),   # Q1 : 1 pt, dept 75
        _qso('F2DEF', '144', '20260415', '75', 'JN18'),   # Q2 : 1 pt, MÊME dept 75
    ]
    rap = scoring.calc_challenge_thf_report(qsos, bands=['144'])
    total_q1 = rap['trimestres']['2026Q1']['total']
    total_q2 = rap['trimestres']['2026Q2']['total']
    assert total_q1 == 1 * (1 + 1) * 1     # 1 pt * (1 dept + 1 locator) * coef 1
    assert total_q2 == 1 * (1 + 1) * 1     # dept 75 de nouveau compté : pas de mémoire inter-trimestre
    assert rap['total_annuel'] == total_q1 + total_q2 == 4


def test_qso_sans_date_exploitable_est_exclu_du_rapport():
    qsos = [_qso('F1ABC', '144', '', '75', 'JN18')]
    rap = scoring.calc_challenge_thf_report(qsos, bands=['144'])
    assert rap['trimestres'] == {}
    assert rap['total_annuel'] == 0


# ─── Preset de coaching (LEGACY_SCORING_PRESETS) ────────────────────────────

def test_preset_coaching_existe_et_ne_multiplie_pas():
    """Le preset de coaching pré-QSO donne un point de base, sans
    multiplicateur (inconnu avant que le QSO existe) -- comme SOTA/POTA."""
    bricks = scoring.LEGACY_SCORING_PRESETS['challenge_thf']
    assert bricks['multiplier'] is None
    assert bricks['points'][0]['points'] == 1
