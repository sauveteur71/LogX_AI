# -*- coding: utf-8 -*-
"""Tests du coach : rate meter (A3) et recommandation Run vs S&P (C1)."""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logx_coach import log_stats, run_sp_recommendation

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


# ─── Multiplicateur par échange (EUHFC) ──────────────────────────────────────

def test_exchange_mults_euhfc():
    """EUHFC : mult = années de licence distinctes PAR BANDE (§6).
    92 sur 14 MHz deux fois = 1 mult ; 92 sur 7 MHz = 1 mult de plus."""
    from logx_coach import exchange_mult_stats
    cdef = {'scoring': {'bricks': {'multiplier': {'kind': 'exchange_distinct'}}}}
    log = [
        {'contest': 'EU_HF_CHAMP', 'band': '14', 'points': 1, 'num_rcvd': '92'},
        {'contest': 'EU_HF_CHAMP', 'band': '14', 'points': 1, 'num_rcvd': '92'},   # doublon d'année
        {'contest': 'EU_HF_CHAMP', 'band': '14', 'points': 1, 'num_rcvd': '05'},
        {'contest': 'EU_HF_CHAMP', 'band': '7',  'points': 1, 'num_rcvd': '92'},   # autre bande
        {'contest': 'EU_HF_CHAMP', 'band': '7',  'points': 1, 'num_rcvd': 'x'},    # échange invalide
    ]
    r = exchange_mult_stats(cdef, log, 'EU_HF_CHAMP')
    assert r['mults'] == 3                       # (14,92) (14,05) (7,92)
    assert r['score_est'] == 5 * 3               # 5 pts × 3 mults


def test_exchange_mults_non_applicable():
    from logx_coach import exchange_mult_stats
    assert exchange_mult_stats({'scoring': {'bricks': {}}}, [], '') is None


# ─── Prévision Es / aurora (B5) ──────────────────────────────────────────────

def test_es_probable_ete_pic():
    from logx_coach import es_aurora_forecast
    f = es_aurora_forecast({'bands': ['144']}, None, None,
                           datetime.datetime(2026, 7, 1, 9, 0))
    assert any(x['kind'] == 'es' and x['level'] == 'probable' for x in f)


def test_es_confirme_prioritaire():
    from logx_coach import es_aurora_forecast
    f = es_aurora_forecast({'bands': ['50']}, {'es_active': True}, None,
                           datetime.datetime(2026, 7, 1, 9, 0))
    assert f[0]['level'] == 'confirme'


def test_aurora_k_eleve():
    from logx_coach import es_aurora_forecast
    f = es_aurora_forecast({'bands': ['144']}, None, 7,
                           datetime.datetime(2026, 7, 1, 3, 0))
    assert any(x['kind'] == 'aurora' and x['level'] == 'fort' for x in f)


def test_pas_es_en_hiver():
    from logx_coach import es_aurora_forecast
    f = es_aurora_forecast({'bands': ['144']}, None, 2,
                           datetime.datetime(2026, 1, 1, 9, 0))
    assert not any(x['kind'] == 'es' for x in f)


def test_pas_es_sur_hf():
    from logx_coach import es_aurora_forecast
    f = es_aurora_forecast({'bands': ['14', '7']}, None, None,
                           datetime.datetime(2026, 7, 1, 9, 0))
    assert not any(x['kind'] == 'es' for x in f)
