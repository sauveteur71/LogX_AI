# -*- coding: utf-8 -*-
"""Tests du coach : rate meter (A3) et recommandation Run vs S&P (C1)."""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radiocontest_coach import log_stats, run_sp_recommendation

NOW = datetime.datetime(2026, 8, 1, 15, 0)


def _log(minutes_ago_list):
    return [{'date': (NOW - datetime.timedelta(minutes=m)).strftime('%Y%m%d'),
             'time': (NOW - datetime.timedelta(minutes=m)).strftime('%H:%M'),
             'band': '14', 'points': 1, 'contest': 'EU_HF_CHAMP'}
            for m in minutes_ago_list]


def test_rate_10min_extrapole():
    """5 QSO dans les 10 dernières minutes → 30/h extrapolé."""
    stats = log_stats(_log([1, 3, 5, 7, 9, 25, 45]), 'EU_HF_CHAMP', now=NOW)
    assert stats['qso_last_10min'] == 5
    assert stats['rate_10min'] == 30
    assert stats['rate_60min'] == 7            # tous dans l'heure


def test_run_quand_ca_tourne():
    clock = {'status': 'en_cours'}
    stats = {'qso_total': 50, 'rate_10min': 36, 'rate_60min': 20}
    reco = run_sp_recommendation(clock, stats, mult_spots_count=5)
    assert reco['mode'] == 'RUN'


def test_sp_quand_rate_chute_et_mults_dispo():
    clock = {'status': 'en_cours'}
    stats = {'qso_total': 50, 'rate_10min': 6, 'rate_60min': 20}
    reco = run_sp_recommendation(clock, stats, mult_spots_count=4)
    assert reco['mode'] == 'S&P'
    assert '4' in reco['reason']


def test_change_bande_si_mort_et_rien_a_chasser():
    clock = {'status': 'en_cours'}
    stats = {'qso_total': 50, 'rate_10min': 0, 'rate_60min': 12}
    reco = run_sp_recommendation(clock, stats, mult_spots_count=0)
    assert reco['mode'] == 'CHANGE'


def test_pas_de_reco_hors_concours():
    assert run_sp_recommendation({'status': 'avant'}, {}, 0) is None
