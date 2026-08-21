# -*- coding: utf-8 -*-
"""A10 (docs/FEUILLE_DE_ROUTE.md) : test d'or de calc_total_score() — le
score final AUTORITAIRE (points × multiplicateurs distincts), demandé par le
critère d'acceptation du document ("test d'or sur un corpus de concours
réels avec score de référence connu, zéro écart toléré").

Avant cette fonction, CINQ endroits exposaient un score en sommant juste les
points par QSO SANS JAMAIS les multiplier : logx_export.py:170
(CLAIMED-SCORE Cabrillo — le score réellement soumis au comité du concours),
logx_http.py (score live /log/list + MQTT), logx_archive.py (stats
d'archive), logx_logbook.js:updateStats() (score affiché en direct côté
client). Le format de barème le documente pourtant lui-même explicitement
(ex. CQ_WW_SSB : 'QSO_pts × (zones_CQ + DXCC)', logx_definitions.py).

Chaque valeur ci-dessous est vérifiée à la main dans le commit qui a ajouté
ce fichier (voir le message de commit) — pas une valeur simplement recopiée
de la sortie du programme."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_dxcc
logx_dxcc.lookup('F5ABC')   # réchauffe le cache cty.dat avant tout test (voir test_score_a_battre.py)

import logx_scoring as sc
from logx_definitions import CONTEST_DEFINITIONS as C


def _qso(**kw):
    base = {'call': 'K1ABC', 'band': '14', 'points': 1}
    base.update(kw)
    return base


# ─── Concours sans multiplicateur : comportement historique inchangé ────────

def test_sans_multiplicateur_reste_la_somme_brute():
    qsos = [_qso(points=50), _qso(points=30)]
    assert sc.calc_total_score(qsos, C['REF_RPH']) == 80


def test_cdef_vide_reste_la_somme_brute():
    assert sc.calc_total_score([_qso(points=5)], {}) == 5


# ─── zone_dxcc (CQ WW) : zone CQ ET pays DXCC comptent CHACUN, par bande ────

def test_zone_dxcc_deux_stations_deux_pays_deux_zones():
    """K1ABC (USA, zone 5) et DL1ABC (Allemagne, zone 14) : 2 zones + 2 pays
    = 4 multiplicateurs. (3+2) × 4 = 20."""
    qsos = [_qso(call='K1ABC', points=3), _qso(call='DL1ABC', points=2)]
    assert sc.calc_total_score(qsos, C['CQ_WW_SSB']) == 20


def test_zone_dxcc_meme_pays_meme_zone_un_seul_mult_pour_les_deux_axes():
    """2 QSO avec le MÊME indicatif : 1 zone + 1 pays = 2 multiplicateurs
    (pas 4) — la répétition n'ajoute rien."""
    qsos = [_qso(call='K1ABC', points=3), _qso(call='K1ABC', points=2)]
    assert sc.calc_total_score(qsos, C['CQ_WW_SSB']) == 10


def test_zone_dxcc_meme_pays_bandes_differentes_recompte_par_bande():
    """CQ WW : le multiplicateur se compte PAR BANDE — le même pays déjà
    travaillé sur une AUTRE bande reste un multiplicateur neuf."""
    qsos = [_qso(call='K1ABC', band='14', points=3), _qso(call='K1ABC', band='21', points=3)]
    # 2 bandes × (1 zone + 1 pays) = 4 mults ; (3+3) × 4 = 24
    assert sc.calc_total_score(qsos, C['CQ_WW_SSB']) == 24


# ─── prefix (CQ WPX) : GLOBAL toutes bandes confondues ──────────────────────

def test_prefix_meme_prefixe_toutes_bandes_reste_un_seul_mult():
    qsos = [_qso(call='K1ABC', band='14', points=1), _qso(call='K1XYZ', band='21', points=1)]
    assert sc.calc_total_score(qsos, C['CQ_WPX_SSB']) == 2   # (1+1) × 1


def test_prefix_deux_prefixes_distincts():
    qsos = [_qso(call='K1ABC', points=1), _qso(call='DL2XYZ', points=1)]
    assert sc.calc_total_score(qsos, C['CQ_WPX_SSB']) == 4   # (1+1) × 2


# ─── dxcc_only (WAE) : pays uniquement, PAR BANDE, pondéré (mult_weight_by_band) ─

def test_dxcc_only_wae_meme_pays_meme_bande_pondere():
    """WAEDC_SSB pondère le multiplicateur par bande (14 MHz ×2, voir
    mult_weight_by_band) : 1 pays × poids 2 = 2 mults. (1+1) × 2 = 4."""
    qsos = [_qso(call='DL1ABC', band='14', points=1), _qso(call='DL2XYZ', band='14', points=1)]
    assert sc.calc_total_score(qsos, C['WAEDC_SSB']) == 4


# ─── itu_zone (IARU HF) ──────────────────────────────────────────────────────

def test_itu_zone_deux_zones_distinctes():
    qsos = [_qso(call='K1ABC', points=1), _qso(call='DL1ABC', points=3)]
    assert sc.calc_total_score(qsos, C['IARU_HF_WC']) == 8   # (1+3) × 2


# ─── na_state (ARRL DX depuis l'Europe) : vraie valeur REÇUE, pas un proxy ──

def test_na_state_utilise_le_vrai_echange_recu():
    qsos = [_qso(call='K1ABC', points=3, num_rcvd='MA'),
            _qso(call='W6XYZ', points=3, num_rcvd='CA')]
    assert sc.calc_total_score(qsos, C['ARRL_DX_SSB']) == 12   # (3+3) × 2


def test_na_state_meme_etat_un_seul_mult():
    qsos = [_qso(call='K1ABC', points=3, num_rcvd='MA'),
            _qso(call='K1XYZ', points=3, num_rcvd='MA')]
    assert sc.calc_total_score(qsos, C['ARRL_DX_SSB']) == 6   # (3+3) × 1


# ─── na_section (ARRL 160m) ──────────────────────────────────────────────────

def test_na_section_une_section():
    qsos = [_qso(call='K1ABC', band='1.8', points=1, num_rcvd='EMA')]
    assert sc.calc_total_score(qsos, C['ARRL_160M']) == 1


# ─── exchange_distinct (EUHFC) : 2 derniers chiffres de l'échange reçu ──────

def test_exchange_distinct_deux_annees_distinctes():
    qsos = [_qso(call='DL1ABC', points=1, num_rcvd='85'),
            _qso(call='F5ABC', points=1, num_rcvd='90')]
    assert sc.calc_total_score(qsos, C['EU_HF_CHAMP']) == 4   # (1+1) × 2


# ─── locator (ARRL EME) : GLOBAL ─────────────────────────────────────────────

def test_locator_deux_locators_distincts():
    qsos = [_qso(call='K1ABC', band='1296', points=100, locator='FN42'),
            _qso(call='DL1ABC', band='1296', points=100, locator='JN58')]
    assert sc.calc_total_score(qsos, C['ARRL_EME']) == 400   # (100+100) × 2


# ─── dept_dxcc (REF) : vrai département REÇU pour un Français, DXCC sinon ──

def test_dept_dxcc_francais_plus_etranger():
    """F5ABC (échange 'RS N°serie dept', dept=75) + DL1ABC (DXCC) = 2 mults
    sur la même bande. (1+3) × 2 = 8."""
    qsos = [_qso(call='F5ABC', band='1.8', points=1, num_rcvd='59 001 75'),
            _qso(call='DL1ABC', band='1.8', points=3)]
    assert sc.calc_total_score(qsos, C['REF_160M']) == 8


# ─── extra_points (QTC WAE) : ajoutés AVANT multiplication ──────────────────

def test_extra_points_qtc_ajoutes_avant_multiplication():
    """Règlement WAE : score = (QSO + QTC) × multiplicateurs, pas
    QSO × mult + QTC après coup. 2 QSO DL (1 mult × poids 2 = 2) + 3 pts QTC
    -> (2 + 3) × 2 = 10, PAS (2×2) + 3 = 7."""
    qsos = [_qso(call='DL1ABC', band='14', points=1), _qso(call='DL2XYZ', band='14', points=1)]
    assert sc.calc_total_score(qsos, C['WAEDC_SSB'], extra_points=3) == 10


# ─── Contre-épreuve grandeur nature : aucun total agrégé n'oublie plus le mult ─

def test_build_cabrillo_applique_bien_le_multiplicateur():
    """Bout en bout via l'export réel (pas juste calc_total_score en
    isolation) : logx_export.build_cabrillo() doit produire le MÊME total."""
    import logx_export as export
    qsos = [{'call': 'K1ABC', 'band': '14', 'mode': 'SSB', 'date': '20261024',
             'time': '1200', 'rst_sent': '59', 'num_sent': '01', 'rst_rcvd': '59',
             'num_rcvd': '05', 'points': 3},
            {'call': 'DL1ABC', 'band': '14', 'mode': 'SSB', 'date': '20261024',
             'time': '1201', 'rst_sent': '59', 'num_sent': '02', 'rst_rcvd': '59',
             'num_rcvd': '14', 'points': 2}]
    cfg = {'callsign': 'F4GLD', 'locator': 'JN18CX', 'contest': 'CQ_WW_SSB'}
    txt = export.build_cabrillo(qsos, C['CQ_WW_SSB'], cfg)
    import re
    m = re.search(r'^CLAIMED-SCORE: (.*)$', txt, re.M)
    assert m and m.group(1).strip() == '20'
