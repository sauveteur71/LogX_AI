# -*- coding: utf-8 -*-
"""Le contexte de l'IA (Carte IA) et son bandeau de score portent sur le log DU CONCOURS.

Défaut F4GLD (24/10/2026, CQ WW SSB) : « l'IA me propose des mults basés sur
mon log général ». Mesuré sur une COPIE de son carnet réel : avant, l'IA
recevait « LOG PARTAGÉ MULTI-OPÉRATEUR (9912 QSO) » et « SCORE TOTAL : 0 pts |
0 QSO » ; après, « LOG LOGX AI (41 QSO) » et « SCORE TOTAL : 1891 pts | 41 QSO »."""
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_storage  # noqa: E402
import logx_prompts  # noqa: E402

AUJ = datetime.datetime.utcnow()
VIDE = {'Log': {'qsos': [], 'score': 0, 'total_qso': 0, 'error': 'URL log non configurée'}}


def _q(call, contest=None, date=None, pts=1):
    q = {'call': call, 'band': '7', 'mode': 'SSB', 'date': date or AUJ.strftime('%Y%m%d'),
         'time': '0400', 'points': pts}
    if contest:
        q['contest'] = contest
    return q


def _cfg():
    return {'contest': 'CQ_WW_SSB', 'usage_mode': 'contest', 'callsign': 'F4GLD', 'locator': 'JN15WD',
            'contest_start_date': (AUJ - datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
            'contest_end_date': (AUJ + datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
            'contest_end_utc': '23:59'}


def _contexte(log, cfg):
    sauve = list(logx_storage.shared_log)
    logx_storage.shared_log[:] = log
    try:
        return logx_prompts.build_terrain_context(VIDE, {}, cfg)
    finally:
        logx_storage.shared_log[:] = sauve


CARNET = ([_q('W%dAW' % i) for i in range(30)]                      # carnet général
          + [_q('UZ7C', 'CQ_WW_SSB', pts=3), _q('JA1ABC', 'CQ_WW_SSB', pts=3)]
          + [_q('K1ZZ', 'CQ_WW_SSB', date='20251025', pts=3)])      # CQ WW de l'an dernier


def test_en_concours_l_ia_ne_voit_que_le_log_du_concours():
    ctx = _contexte(CARNET, _cfg())
    assert re.search(r'LOG LOGX AI \(2 QSO\)', ctx), ctx[:600]
    assert 'UZ7C' in ctx and 'JA1ABC' in ctx
    assert 'W5AW' not in ctx and 'K1ZZ' not in ctx               # carnet général, autre année
    m = re.search(r'SCORE TOTAL : (\d+) pts \| (\d+) QSO', ctx)
    assert m and int(m.group(2)) == 2 and int(m.group(1)) > 0


def test_mode_simple_carnet_complet_inchange():
    cfg = dict(_cfg(), usage_mode='simple')
    ctx = _contexte(CARNET, cfg)
    assert re.search(r'\(33 QSO\)', ctx)


def test_bandeau_carte_score_du_concours():
    src = open('logx_http.py', encoding='utf-8').read()
    f = src[src.index('def do_refresh'):]
    f = f[:f.index('context = build_terrain_context')]
    assert re.search(r"if not total_qso and cfg_scope_id\(cfg\):", f)
    assert '_scope_filtered(list(shared_log), cfg)' in f and 'calc_total_score(_log_conc' in f
