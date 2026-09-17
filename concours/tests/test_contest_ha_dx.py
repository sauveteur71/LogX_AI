# -*- coding: utf-8 -*-
"""HA-DX Contest (MRASZ Hongrie) — barème RÉEL vs placeholder « approximatif ».

SOURCE : règlement officiel lu intégralement le 16/09/2026, revérifié le
17/09/2026 (https://ha-dx.com/en/contest-rules) :
  - Points, indépendants de la bande et du mode : station HA/HG = 10 pts,
    même continent (non-HA) = 2 pts, autre continent (DX) = 5 pts.
  - Échange : stations HA -> RS(T) + comté (2 lettres) ; stations non-HA ->
    RS(T) + n° de série.
  - Multiplicateur PAR BANDE : DXCC + WAE (hors Hongrie elle-même) + les 20
    comtés hongrois (megyék) : BA BE BN BO BP CS FE GY HB HE KO NG PE SA SO
    SZ TO VA VE ZA.
  - Dépôt des logs : 5 jours après la fin du concours (pas 7).

CE QUE CE FICHIER REMPLACE : la définition CONTEST_DEFINITIONS['HA_DX']
portait la mention 'note': 'Barème approximatif' avec un multiplicateur
générique 'zone_dxcc' (zones CQ, aucune notion de comté hongrois) et un
barème inventé (6/1/3 pts) sans rapport avec le règlement réel. Le moteur
dédié (_mult_ha_county_dxcc, _ha_county_token, prédicat 'is_ha') existait
déjà dans logx_scoring.py mais n'était référencé par AUCUNE définition et
n'avait AUCUN test — trou comblé ici.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

from logx_definitions import CONTEST_DEFINITIONS   # noqa: E402
import logx_scoring as scoring                       # noqa: E402
import logx_validate as validate                     # noqa: E402

MY_CALL = 'F4GLD'      # France -> continent EU
MY_LOC = 'JN18DA'


def _score(dx_call, band='14', mode='CW'):
    """direct_pts réel d'un QSO déjà loggué (pipeline complet calc_qso_value,
    comme le ferait le serveur à l'insertion) -- pas un ctx reconstruit à la
    main, pour ne contraindre que le comportement observable de la page/du
    moteur, jamais un mannequin de test."""
    return scoring.score_new_qso({
        'contest': 'HA_DX', 'call': dx_call, 'band': band, 'mode': mode,
        'my_call': MY_CALL, 'my_locator': MY_LOC,
    })


def _coach(dx_call, band='14', done_dxcc=None, done_na_proxies=None, current_score=0):
    return scoring.calc_qso_value(
        'HA_DX', dx_call, '', MY_CALL, MY_LOC,
        {}, set(), set(), {}, done_dxcc or {}, current_score,
        band=band, dist_km=0, done_na_proxies=done_na_proxies,
    )


# ─── Définition : présente, conforme, métadonnées réglement ────────────────

def test_ha_dx_present_et_conforme():
    assert 'HA_DX' in CONTEST_DEFINITIONS
    erreurs = validate.validate_definition(CONTEST_DEFINITIONS['HA_DX'], 'HA_DX')
    assert erreurs == [], erreurs


def test_ha_dx_metadonnees_reglement():
    d = CONTEST_DEFINITIONS['HA_DX']
    assert d['bands'] == ['1.8', '3.5', '7', '14', '21', '28']
    assert d['modes'] == ['SSB', 'CW']
    assert d['date_rule'] == 'third_full_weekend_january'
    assert d['duration_h'] == 24
    assert d['start_utc'] == '12:00'
    assert d['cabrillo_name'] == 'HA-DX'


def test_ha_dx_deadline_5_jours_pas_7():
    # Règlement : « Logs must be uploaded ... within 5 days of the end of
    # the contest » -- l'ancien placeholder disait 7_days_after (copié
    # d'un autre concours SPDX voisin dans le fichier).
    assert CONTEST_DEFINITIONS['HA_DX']['log_deadline'] == '5_days_after'


def test_ha_dx_nutilise_plus_le_multiplicateur_generique_zone_dxcc():
    kind = CONTEST_DEFINITIONS['HA_DX']['scoring']['bricks']['multiplier']['kind']
    assert kind == 'ha_county_dxcc'


# ─── Barème de points réel (10 / 2 / 5, indépendant bande/mode) ────────────

def test_station_ha_vaut_10_points():
    assert _score('HA1AB') == 10


def test_station_hg_prefixe_special_vaut_aussi_10_points():
    # HG est un préfixe spécial hongrois de LA MÊME entité DXCC que HA
    # (contest callsigns) -- doit rendre exactement le même barème.
    assert _score('HG5A') == 10


def test_meme_continent_non_ha_vaut_2_points():
    assert _score('DL1ABC') == 2   # Allemagne, EU comme F4GLD


def test_autre_continent_vaut_5_points():
    assert _score('W1AW') == 5     # USA, NA


def test_bareme_independant_de_la_bande_et_du_mode():
    assert _score('HA1AB', band='1.8', mode='SSB') == 10
    assert _score('DL1ABC', band='28', mode='SSB') == 2
    assert _score('W1AW', band='3.5', mode='CW') == 5


def test_station_ha_prime_sur_meme_continent():
    # Une station HA est géographiquement en EU comme F4GLD : la règle
    # 'is_ha' doit être évaluée AVANT 'same_continent', sinon une station
    # hongroise ne rendrait que 2 pts au lieu de 10.
    bricks_points = CONTEST_DEFINITIONS['HA_DX']['scoring']['bricks']['points']
    assert [r['when'] for r in bricks_points] == [
        'is_ha', 'same_continent', 'different_continent',
    ]


# ─── Multiplicateur PAR BANDE : comtés HA + DXCC/WAE ───────────────────────

def test_score_autoritaire_comtes_et_dxcc_par_bande():
    qsos = [
        # 14 MHz : comté BP (HA1AB), comté BP à nouveau (autre station, même
        # comté -> pas de nouveau mult), comté SZ (nouveau), DL (DXCC), W1AW (DXCC)
        {'call': 'HA1AB', 'band': '14', 'num_rcvd': '599 BP', 'points': 10},
        {'call': 'HA2CD', 'band': '14', 'num_rcvd': '599 BP', 'points': 10},
        {'call': 'HA3EF', 'band': '14', 'num_rcvd': '599 SZ', 'points': 10},
        {'call': 'DL1XX', 'band': '14', 'num_rcvd': '123',    'points': 2},
        {'call': 'W1AW',  'band': '14', 'num_rcvd': '456',    'points': 5},
        # 7 MHz : le comté BP déjà vu sur 14 MHz redevient un mult NEUF
        # (comptage PAR BANDE, pas all-band).
        {'call': 'HA1AB', 'band': '7',  'num_rcvd': '599 BP', 'points': 10},
    ]
    # 14 MHz : {county BP, county SZ, dxcc DL, dxcc K} = 4 mults
    #  7 MHz : {county BP} = 1 mult
    # total mults = 5 ; points = 10+10+10+2+5+10 = 47 ; score = 47*5 = 235
    assert scoring.calc_total_score(qsos, CONTEST_DEFINITIONS['HA_DX']) == 235


def test_comte_invalide_ne_devient_jamais_un_multiplicateur_fantome():
    # 'XX' n'existe pas dans la liste officielle des 20 comtés -- un code
    # inventé/mal transcrit ne doit RIEN ajouter au compte de mults (mais
    # les points du QSO restent dus, seul le multiplicateur est affecté).
    qsos = [{'call': 'HA1AB', 'band': '14', 'num_rcvd': '599 XX', 'points': 10}]
    assert scoring.count_mults(qsos, CONTEST_DEFINITIONS['HA_DX']) == 0
    assert scoring.calc_total_score(qsos, CONTEST_DEFINITIONS['HA_DX']) == 10


def test_liste_officielle_compte_20_comtes():
    # Verrou de non-régression sur le RECENSEMENT (commentaire historique du
    # fichier affirmait à tort « 19 comtés » alors que le frozenset en
    # contenait déjà 20 -- corrigé le 17/09/2026, source ha-dx.com).
    assert len(scoring._HA_COUNTIES) == 20
    assert scoring._HA_COUNTIES == frozenset((
        'BA', 'BE', 'BN', 'BO', 'BP', 'CS', 'FE', 'GY', 'HB', 'HE',
        'KO', 'NG', 'PE', 'SA', 'SO', 'SZ', 'TO', 'VA', 'VE', 'ZA',
    ))


# ─── Coaching pré-QSO (calc_qso_value / MULT_EVALUATORS) ───────────────────

def test_ha_dx_a_un_evaluateur_de_multiplicateur_enregistre():
    assert scoring.MULT_EVALUATORS.get('ha_county_dxcc') is not None


def test_coach_station_ha_jamais_vue_est_priorite_max():
    r = _coach('HA1AB', done_na_proxies={})
    assert r['new_mult'] is True
    assert r['mult_type'] == 'comte_ha'
    assert r['priority'] == 1
    assert r['direct_pts'] == 10


def test_coach_station_ha_proxy_deja_vu_pas_de_nouveau_mult():
    # Proxy = 3 premiers caractères de l'indicatif (comté exact inconnu au
    # stade du spot) -- même technique que _mult_na_state.
    r = _coach('HA1AB', band='14', done_na_proxies={'14': {'HA1'}})
    assert r['new_mult'] is False
    assert r['priority'] == 3


def test_coach_dx_nouveau_dxcc_est_priorite_max():
    # W1AW (USA, NA) est un AUTRE continent que F4GLD (France, EU) -> 5 pts,
    # ET un DXCC jamais vu -> nouveau mult, priorité max.
    r = _coach('W1AW', done_dxcc={})
    assert r['new_mult'] is True
    assert r['mult_type'] == 'dxcc'
    assert r['priority'] == 1
    assert r['direct_pts'] == 5


def test_coach_dx_dxcc_deja_connu_pas_de_nouveau_mult():
    r = _coach('W1AW', band='14', done_dxcc={'14': {'K'}})
    assert r['new_mult'] is False
    assert r['priority'] == 3


# ─── Routage géographique (carte/carnet) ───────────────────────────────────

def test_contest_geo_mode_ha_dx_est_other_pas_departement_francais():
    # ha_county_dxcc n'a aucune notion de département français -- doit
    # rejoindre 'other' comme na_state/na_section, jamais le défaut 'dept'.
    assert scoring.contest_geo_mode('HA_DX') == 'other'
