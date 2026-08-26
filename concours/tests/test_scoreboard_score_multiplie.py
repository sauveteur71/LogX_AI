# -*- coding: utf-8 -*-
"""Scoreboard externe (contestonlinescore.com) — le score publié doit être le
score FINAL réclamé : (points QSO + QTC) × multiplicateurs, pas les points seuls
(audit 22/08 logx_scoreboard.py:58, re-vérifié vivant le 26/08). Le format
N1MM+ attend le score réclamé dans <score>. Le comptage des mults et le score
doivent venir de la MÊME source canonique (calc_total_score / count_mults) —
fin de la duplication du moteur (audit :33)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_dxcc
logx_dxcc.lookup('F5ABC')   # réchauffe le cache cty.dat (zones/pays) avant les tests

import logx_scoreboard as sb
from logx_definitions import CONTEST_DEFINITIONS as C


def _log():
    # K1ABC (USA, zone 5) + DL1ABC (Allemagne, zone 14) sur 20 m :
    # 2 zones + 2 pays = 4 multiplicateurs ; (3+2) × 4 = 20.
    return [
        {'contest': 'CQ_WW_SSB', 'call': 'K1ABC', 'band': '14', 'points': 3, 'date': '20261024'},
        {'contest': 'CQ_WW_SSB', 'call': 'DL1ABC', 'band': '14', 'points': 2, 'date': '20261024'},
    ]


_CFG = {'contest': 'CQ_WW_SSB', 'contest_start_date': '2026-10-24'}


def test_score_publie_est_multiplie_par_les_mults():
    snap = sb.build_score_snapshot(_log(), _CFG)
    assert snap['score'] == 20        # (3+2) × 4, PAS 5 (points seuls) avant le fix
    assert snap['mults'] == 4
    assert snap['qso'] == 2


def test_score_et_mults_viennent_de_la_meme_source():
    """Score et compte de mults cohérents avec calc_total_score (plus de moteur
    dupliqué) : le score doit être exactement raw_points × mults publiés."""
    import logx_scoring as sc
    snap = sb.build_score_snapshot(_log(), _CFG)
    raw = sum(q['points'] for q in _log())            # 5
    assert snap['score'] == raw * snap['mults']       # 5 × 4 = 20
    # et identique à l'appel direct du moteur autoritaire
    assert snap['score'] == sc.calc_total_score(_log(), C['CQ_WW_SSB'])


def test_xml_publie_le_score_multiplie():
    snap = sb.build_score_snapshot(_log(), _CFG)
    xml = sb.build_n1mm_xml(snap, _CFG)
    assert '<score>20</score>' in xml
    assert 'type="mult">4</mult>' in xml


def test_sans_multiplicateur_reste_les_points_bruts():
    """Non-régression : un concours sans multiplicateur publie toujours la
    somme des points (comportement historique)."""
    log = [{'contest': 'REF_QRP', 'call': 'B', 'band': '432', 'points': 30,
            'locator': 'JN33AA', 'date': '20270718'}]
    snap = sb.build_score_snapshot(log, {'contest': 'REF_QRP', 'contest_start_date': '2027-07-18'})
    assert snap['score'] == 30
