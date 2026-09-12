# -*- coding: utf-8 -*-
"""Les 4 concours TVA (Télévision Amateur) du REF -- National TVA (mars +
décembre, même règlement), Championnat de France TVA, IARU TVA (Région 1).

SOURCE : 3 règlements PDF officiels REF lus intégralement le 12/09/2026 via
l'outil de lecture PDF (pas WebFetch, qui échoue sur ces PDF -- flux binaire
non décompressable par son résumé automatique) :
  - reg_nattva_fr_20260516.pdf  (National TVA -- sert aussi à NAT_TVA_DEC)
  - reg_cdftva_fr_20260516.pdf  (Championnat de France TVA)
  - reg_iarutva_fr_20251209.pdf (IARU TVA Région 1)

DÉCOUVERTE qui motive ce fichier : l'ancien CONTEST_SCORING affichait
'type':'tva', 'pts x relais TVA' -- AUCUNE notion de relais dans les 3
règlements. Le vrai barème est un scoring AU KILOMÈTRE, coefficient croissant
par bande, SANS multiplicateur (Section 1, émission-réception) :
  70 cm : 2 pts/km · 23 cm : 4 pts/km · bandes supérieures : 10 pts/km.
Modélisé via la nouvelle brique générique {'points': {'per_km_x': N}}
(schéma contest_schema.json v1.3.0), combinée au filtre 'bands' déjà existant
par règle -- pas de nouveau code de dispatch par concours.

Section 2 (réception seule/SWL, moitié points) : hors scope, décision F4GLD
12/09/2026 -- le carnet LogX AI n'a aucun champ pour distinguer un contact
bilatéral d'une réception unilatérale.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

from logx_definitions import CONTEST_DEFINITIONS   # noqa: E402
import logx_scoring as scoring                       # noqa: E402
import logx_validate as validate                     # noqa: E402

TVA_IDS = ('REF_NAT_TVA', 'REF_NAT_TVA_DEC', 'REF_CDF_TVA', 'REF_IARU_TVA')


def test_les_4_concours_tva_sont_presents():
    for cid in TVA_IDS:
        assert cid in CONTEST_DEFINITIONS, cid


def test_les_4_definitions_sont_valides():
    for cid in TVA_IDS:
        erreurs = validate.validate_definition(CONTEST_DEFINITIONS[cid], cid)
        assert erreurs == [], (cid, erreurs)


# ─── Trou trouvé au passage dans le validateur MINIMAL (secours sans
# jsonschema) : 'per_km_stew'/'per_grid_3000'/'per_km_x' n'étaient jamais
# acceptés dans une forme 'bricks' DIRECTE -- invisible jusqu'ici car
# FT_CHALLENGE (seul autre concours à utiliser 'per_grid_3000') passe par la
# forme raccourcie 'type', qui ne traverse pas cette branche de code. ───────

def _bricks_def(points_value):
    return {
        'name': 'x', 'organizer': 'x', 'date_rule': 'permanent',
        'bands': ['432'], 'modes': ['FM'], 'exchange': 'x', 'log_format': '',
        'scoring': {'bricks': {'points': [{'when': 'always', 'points': points_value}],
                                'multiplier': None}},
    }


def test_validateur_minimal_accepte_per_km_x_en_forme_bricks_directe():
    assert validate.validate_definition(_bricks_def({'per_km_x': 2}), 'x') == []


def test_validateur_minimal_accepte_per_km_stew_en_forme_bricks_directe():
    assert validate.validate_definition(_bricks_def('per_km_stew'), 'x') == []


def test_validateur_minimal_accepte_per_grid_3000_en_forme_bricks_directe():
    assert validate.validate_definition(_bricks_def('per_grid_3000'), 'x') == []


def test_validateur_minimal_rejette_toujours_une_forme_inconnue():
    erreurs = validate.validate_definition(_bricks_def('per_je_invente'), 'x')
    assert any('points invalide' in e for e in erreurs)


def test_validateur_minimal_rejette_per_km_x_non_numerique():
    erreurs = validate.validate_definition(_bricks_def({'per_km_x': 'deux'}), 'x')
    assert any('points invalide' in e for e in erreurs)


def test_aucun_multiplicateur():
    """Le vrai règlement n'a PAS de multiplicateur -- contrairement à
    l'ancien 'relais TVA' inventé."""
    for cid in TVA_IDS:
        assert CONTEST_DEFINITIONS[cid]['scoring']['bricks']['multiplier'] is None, cid


# ─── Brique générique {'points': {'per_km_x': N}} -- unitaire ───────────────

def test_per_km_x_multiplie_la_distance():
    assert scoring._points_value({'points': {'per_km_x': 2}}, {'dist_km': 100}, {}) == 200
    assert scoring._points_value({'points': {'per_km_x': 4}}, {'dist_km': 100}, {}) == 400
    assert scoring._points_value({'points': {'per_km_x': 10}}, {'dist_km': 100}, {}) == 1000


def test_per_km_x_zero_km():
    assert scoring._points_value({'points': {'per_km_x': 2}}, {'dist_km': 0}, {}) == 0


# ─── Barème réel par bande, les 4 concours ───────────────────────────────────

def test_national_tva_bareme_par_bande():
    cdef = CONTEST_DEFINITIONS['REF_NAT_TVA']
    r70 = scoring.calc_qso_value('REF_NAT_TVA', 'F1ABC', '', 'F6KQJ', '',
                                  {}, set(), set(), {}, {}, 0, band='432', dist_km=150)
    r23 = scoring.calc_qso_value('REF_NAT_TVA', 'F1ABC', '', 'F6KQJ', '',
                                  {}, set(), set(), {}, {}, 0, band='1296', dist_km=150)
    r_shf = scoring.calc_qso_value('REF_NAT_TVA', 'F1ABC', '', 'F6KQJ', '',
                                    {}, set(), set(), {}, {}, 0, band='5760', dist_km=150)
    assert (r70['direct_pts'], r70['total_impact']) == (300, 300)     # 150 * 2
    assert (r23['direct_pts'], r23['total_impact']) == (600, 600)     # 150 * 4
    assert (r_shf['direct_pts'], r_shf['total_impact']) == (1500, 1500)  # 150 * 10
    assert cdef['scoring']['bricks']['multiplier'] is None


def test_national_tva_dec_meme_bareme_que_mars():
    """REF_NAT_TVA_DEC = même règlement que REF_NAT_TVA, autre édition
    annuelle (décembre plutôt que mars) -- barème identique."""
    r_mars = scoring.calc_qso_value('REF_NAT_TVA', 'F1ABC', '', 'F6KQJ', '',
                                     {}, set(), set(), {}, {}, 0, band='1296', dist_km=200)
    r_dec = scoring.calc_qso_value('REF_NAT_TVA_DEC', 'F1ABC', '', 'F6KQJ', '',
                                    {}, set(), set(), {}, {}, 0, band='1296', dist_km=200)
    assert r_mars['direct_pts'] == r_dec['direct_pts'] == 800


def test_cdf_tva_bareme_par_bande():
    r70 = scoring.calc_qso_value('REF_CDF_TVA', 'F1ABC', '', 'F6KQJ', '',
                                  {}, set(), set(), {}, {}, 0, band='432', dist_km=50)
    r_shf = scoring.calc_qso_value('REF_CDF_TVA', 'F1ABC', '', 'F6KQJ', '',
                                    {}, set(), set(), {}, {}, 0, band='10368', dist_km=50)
    assert r70['direct_pts'] == 100     # 50 * 2
    assert r_shf['direct_pts'] == 500   # 50 * 10 (bande au-delà de 23cm, règle sans filtre)


def test_iaru_tva_bareme_par_bande():
    r70 = scoring.calc_qso_value('REF_IARU_TVA', 'F1ABC', '', 'F6KQJ', '',
                                  {}, set(), set(), {}, {}, 0, band='432', dist_km=80)
    r23 = scoring.calc_qso_value('REF_IARU_TVA', 'F1ABC', '', 'F6KQJ', '',
                                  {}, set(), set(), {}, {}, 0, band='1296', dist_km=80)
    r9 = scoring.calc_qso_value('REF_IARU_TVA', 'F1ABC', '', 'F6KQJ', '',
                                 {}, set(), set(), {}, {}, 0, band='3400', dist_km=80)
    assert r70['direct_pts'] == 160    # 80 * 2
    assert r23['direct_pts'] == 320    # 80 * 4
    assert r9['direct_pts'] == 800     # 80 * 10


def test_iaru_tva_bandes_restreintes_pas_et_au_dela():
    """Contrairement à National/CDF TVA (« et au-delà »), IARU TVA énumère
    explicitement ses bandes -- 10368/47088 absents, pas une omission."""
    assert CONTEST_DEFINITIONS['REF_IARU_TVA']['bands'] == \
        ['432', '1296', '2320', '3400', '5760', '24048']


# ─── calc_total_score bout-en-bout (log complet, comme un vrai concours) ────

def test_calc_total_score_national_tva_sans_multiplicateur():
    cdef = CONTEST_DEFINITIONS['REF_NAT_TVA']
    qsos = [
        {'call': 'F1ABC', 'band': '432', 'points': 200},   # 100km * 2
        {'call': 'F2DEF', 'band': '1296', 'points': 400},  # 100km * 4
    ]
    # Pas de multiplicateur -> score = somme brute des points, jamais multiplié.
    assert scoring.calc_total_score(qsos, cdef) == 600
