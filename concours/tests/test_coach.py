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
    # contest_id est une PORTÉE 'concours#année' (logx_storage.active_scope_id) —
    # les QSO de _log() sont datés 2026 (voir NOW), d'où le suffixe '#2026'.
    stats = log_stats(_log([1, 3, 5, 7, 9, 25, 45]), 'EU_HF_CHAMP#2026', now=NOW)
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


# ─── Règle des 10 minutes (multi-op M/S) ─────────────────────────────────────

def _band_log(entries):
    """entries : liste de (minutes_avant_NOW, bande) → QSO log partagé."""
    return [{'date': (NOW - datetime.timedelta(minutes=m)).strftime('%Y%m%d'),
             'time': (NOW - datetime.timedelta(minutes=m)).strftime('%H:%M'),
             'band': b, 'points': 1, 'contest': 'CQ_WW_CW'}
            for m, b in entries]


def test_band_change_pas_de_qso():
    from logx_coach import band_change_timer
    r = band_change_timer([], 'CQ_WW_CW#2026', now=NOW)
    assert r['ready'] is True
    assert r['changed_at'] is None
    assert r['current_band'] is None


def test_band_change_jamais_change_de_bande():
    """Toujours la même bande depuis le début : aucune contrainte encore, même
    des heures après le premier QSO (le tout premier QSO ne compte pas comme
    un « changement »)."""
    from logx_coach import band_change_timer
    log = _band_log([(300, '14'), (200, '14'), (100, '14')])
    r = band_change_timer(log, 'CQ_WW_CW#2026', now=NOW)
    assert r['ready'] is True
    assert r['changed_at'] is None
    assert r['current_band'] == '14'


def test_band_change_recent_encore_bloque():
    """Changement 14->7 il y a 4 min : encore 6 min à attendre (règle 10 min)."""
    from logx_coach import band_change_timer
    log = _band_log([(30, '14'), (20, '14'), (4, '7')])
    r = band_change_timer(log, 'CQ_WW_CW#2026', now=NOW)
    assert r['ready'] is False
    assert r['current_band'] == '7'
    assert r['remaining_s'] == 6 * 60


def test_band_change_delai_ecoule():
    """Changement il y a 15 min : la fenêtre de 10 min est passée, autorisé à nouveau."""
    from logx_coach import band_change_timer
    log = _band_log([(30, '14'), (15, '7')])
    r = band_change_timer(log, 'CQ_WW_CW#2026', now=NOW)
    assert r['ready'] is True
    assert r['remaining_s'] == 0


def test_band_change_ignore_hors_portee():
    """Un QSO d'une autre portée (autre concours/année) ne doit jamais compter."""
    from logx_coach import band_change_timer
    log = [{'date': NOW.strftime('%Y%m%d'), 'time': (NOW - datetime.timedelta(minutes=1)).strftime('%H:%M'),
            'band': '7', 'contest': 'AUTRE_CONCOURS'}]
    r = band_change_timer(log, 'CQ_WW_CW#2026', now=NOW)
    assert r['current_band'] is None


# ─── Gating du compte à rebours par la définition du concours actif ──────────
# (build_coach_state ne doit calculer/afficher band_change QUE si le concours
# porte explicitement 'band_change_rule_min' dans CONTEST_DEFINITIONS — avant
# le correctif, band_change_timer() était appelé pour n'importe quel concours,
# y compris ceux sans aucune contrainte de changement de bande.)

def test_build_coach_state_band_change_absent_sans_regle_definie():
    """REF_RPH (144/432 MHz, aucune règle de changement de bande dans sa
    définition) : même avec un vrai changement de bande récent dans le log
    (qui rendrait 'ready' False si la règle des 10 min s'appliquait), le coach
    ne doit afficher AUCUN compte à rebours — reproduit le bug : avant le
    correctif, band_change était calculé (et donc affichable) pour ce concours
    alors qu'aucune règle de ce type n'existe au REF."""
    from logx_coach import build_coach_state
    log = [{'date': (NOW - datetime.timedelta(minutes=m)).strftime('%Y%m%d'),
            'time': (NOW - datetime.timedelta(minutes=m)).strftime('%H:%M'),
            'band': b, 'points': 1, 'contest': 'REF_RPH'}
           for m, b in [(30, '144'), (20, '144'), (4, '432')]]
    cfg = {'contest': 'REF_RPH', 'contest_start_date': '20260704'}
    st = build_coach_state(cfg, log, now=NOW)
    assert st['band_change'] is None


def test_build_coach_state_band_change_present_avec_regle_definie():
    """CQ_WW_CW définit band_change_rule_min=10 (règle M/S réelle) : le compte
    à rebours doit être calculé, et cohérent avec un appel direct à
    band_change_timer() sur le même log/portée."""
    from logx_coach import build_coach_state, band_change_timer
    log = _band_log([(30, '14'), (20, '14'), (4, '7')])
    cfg = {'contest': 'CQ_WW_CW', 'contest_start_date': '20261128'}
    st = build_coach_state(cfg, log, now=NOW)
    expected = band_change_timer(log, 'CQ_WW_CW#2026', now=NOW)
    assert st['band_change'] == expected
    assert st['band_change']['ready'] is False
    assert st['band_change']['remaining_s'] == 6 * 60
