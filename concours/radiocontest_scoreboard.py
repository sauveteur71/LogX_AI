# -*- coding: utf-8 -*-
"""Scoreboard en direct — publication du score pendant le concours.

Envoie périodiquement le score courant à un tableau de bord public
(contestonlinescore.com, format XML « N1MM dynamic score ») pour se comparer
aux rivaux en temps réel. Activé + intervalle réglés dans la config.

Le snapshot de score est DÉTERMINISTE (depuis shared_log + la définition) et
testable sans réseau ; seul le POST touche le réseau et dégrade proprement.
"""
import json
import os
import time
import datetime
import urllib.request
import urllib.parse

_STAMP_FILE = 'scoreboard_sync.json'


def scoreboard_settings(cfg):
    cfg = cfg or {}
    url = (cfg.get('scoreboard_url') or 'http://contestonlinescore.com/post/').strip()
    return {
        'enabled': str(cfg.get('scoreboard_enabled', '')) in ('1', 'true', 'True', 'on'),
        'url': url,
        'interval_min': int(cfg.get('scoreboard_interval', 5) or 5),
        'class': (cfg.get('scoreboard_class') or 'SO').strip(),
    }


# ─── SNAPSHOT DE SCORE (déterministe) ─────────────────────────────────────────

def build_score_snapshot(shared_log, cfg, contest_id=None):
    """{score, qso, per_band:{band:{qso,points}}, mults} pour le concours actif."""
    cfg = cfg or {}
    contest_id = contest_id if contest_id is not None else cfg.get('contest', '')
    entries = [q for q in (shared_log or [])
               if not contest_id or q.get('contest', '') in ('', contest_id)]
    per_band = {}
    score = 0
    for q in entries:
        pts = q.get('points', 0) or 0
        score += pts
        b = str(q.get('band', '?'))
        pb = per_band.setdefault(b, {'qso': 0, 'points': 0})
        pb['qso'] += 1
        pb['points'] += pts

    # Multiplicateurs selon le barème (départements REF ou locators VHF)
    mults = 0
    try:
        from radiocontest_definitions import CONTEST_DEFINITIONS
        cdef = CONTEST_DEFINITIONS.get(contest_id, {})
        stype = (cdef.get('scoring', {}) or {}).get('type', '')
        if stype == 'dept_dxcc':
            from radiocontest_departments import department_mult_count
            mults = len(department_mult_count(shared_log, contest_id))
        else:
            mults = len({str(q.get('locator', ''))[:4] for q in entries
                         if q.get('locator') and len(str(q.get('locator'))) >= 4})
    except Exception:
        pass

    return {'contest': contest_id, 'score': score, 'qso': len(entries),
            'mults': mults, 'per_band': per_band}


ADIF_MODE_CAT = {'CW': 'CW', 'SSB': 'PH', 'USB': 'PH', 'LSB': 'PH', 'FM': 'PH',
                 'FT8': 'DG', 'FT4': 'DG', 'RTTY': 'DG'}


def build_n1mm_xml(snapshot, cfg, klass='SO'):
    """XML « dynamic score » compatible contestonlinescore.com (format N1MM+)."""
    cfg = cfg or {}
    call = (cfg.get('callsign_contest') or cfg.get('callsign') or 'STATION').upper()
    ops = call
    now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<dynamicresults>',
             f'<contest>{_esc(snapshot.get("contest",""))}</contest>',
             f'<call>{_esc(call)}</call>', f'<ops>{_esc(ops)}</ops>',
             f'<class arrlsection="" assisted="" band="ALL" mode="MIXED" '
             f'overlay="" power="" transmitter="ONE">{_esc(klass)}</class>',
             f'<qsos>{snapshot.get("qso",0)}</qsos>',
             f'<score>{snapshot.get("score",0)}</score>',
             f'<timestamp>{now}</timestamp>', '<breakdown>']
    for band, v in sorted(snapshot.get('per_band', {}).items()):
        lines.append(f'<qso band="{_esc(band)}" mode="ALL">{v["qso"]}</qso>')
    lines.append(f'<mult band="ALL" mode="ALL" type="mult">{snapshot.get("mults",0)}</mult>')
    lines.append('</breakdown>')
    lines.append('</dynamicresults>')
    return '\n'.join(lines)


def _esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


# ─── POST ─────────────────────────────────────────────────────────────────────

def push(cfg, shared_log):
    """Construit et envoie le score. Retourne {ok, score, qso, ...}."""
    s = scoreboard_settings(cfg)
    if not s['enabled']:
        return {'ok': False, 'error': 'Scoreboard désactivé (CONFIG)'}
    snap = build_score_snapshot(shared_log, cfg)
    if not snap['qso']:
        return {'ok': False, 'error': 'Aucun QSO à publier'}
    xml = build_n1mm_xml(snap, cfg, s['class'])
    try:
        from radiocontest_utils import SSL_CTX
        ctx = SSL_CTX
    except Exception:
        ctx = None
    try:
        data = urllib.parse.urlencode({'xml': xml}).encode('utf-8')
        req = urllib.request.Request(s['url'], data=data, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'RadioContestAI'})
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            resp = r.read().decode('utf-8', 'replace')[:200]
    except Exception as e:
        return {'ok': False, 'error': f'Scoreboard injoignable : {e}'}
    _stamp(snap)
    return {'ok': True, 'score': snap['score'], 'qso': snap['qso'],
            'mults': snap['mults'], 'response': resp.strip()}


def _stamp(snap):
    try:
        data = {'last': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
                'score': snap.get('score'), 'qso': snap.get('qso')}
        with open(_STAMP_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception:
        pass


def status(cfg=None):
    s = scoreboard_settings(cfg) if cfg is not None else {}
    last = {}
    try:
        if os.path.exists(_STAMP_FILE):
            with open(_STAMP_FILE, encoding='utf-8') as f:
                last = json.load(f) or {}
    except Exception:
        pass
    return {'enabled': bool(s.get('enabled')), 'url': s.get('url', ''),
            'interval_min': s.get('interval_min', 5), 'last': last}
