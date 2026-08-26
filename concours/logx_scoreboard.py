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

from logx_storage import qso_scope_id, cfg_scope_id, qtc_total
from logx_utils import utcnow, post_url_form
from logx_scoring import calc_total_score, count_mults
from logx_definitions import CONTEST_DEFINITIONS

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
    # Portée QSO (contest+année, voir logx_storage.active_scope_id) : réutilise
    # l'année de cfg même si contest_id est explicitement surchargé. Un QSO non
    # tagué (contest == '') ne compte jamais pour une portée précise — sans ça,
    # un log perso/importé jamais nettoyé gonflait le score publié.
    scope_id = cfg_scope_id({**cfg, 'contest': contest_id})
    entries = [q for q in (shared_log or [])
               if not scope_id or qso_scope_id(q) == scope_id]
    per_band = {}
    for q in entries:
        pts = q.get('points', 0) or 0
        b = str(q.get('band', '?'))
        pb = per_band.setdefault(b, {'qso': 0, 'points': 0})
        pb['qso'] += 1
        pb['points'] += pts

    # SCORE FINAL RÉCLAMÉ, source CANONIQUE unique. Avant ce correctif, le score
    # publié = somme des points QSO seuls (jamais × multiplicateurs, audit
    # 22/08 :58) et le compte de mults venait d'un moteur DUPLIQUÉ (:33) qui
    # divergeait du score — deux vérités incohérentes envoyées au tableau de
    # bord externe. Désormais <score> et <mult> sortent tous deux de
    # calc_total_score / count_mults (le MÊME moteur que Cabrillo CLAIMED-SCORE,
    # /log/list, archive). QTC (WAE) : (points QSO + QTC) × mults — les QTC
    # vivent dans un journal séparé, ajoutés AVANT multiplication via
    # extra_points. No-op hors WAE (qtc_total renvoie 0).
    cdef = CONTEST_DEFINITIONS.get(contest_id, {})
    score = calc_total_score(entries, cdef, extra_points=qtc_total(scope_id))
    mults = count_mults(entries, cdef)

    return {'contest': contest_id, 'score': score, 'qso': len(entries),
            'mults': mults, 'per_band': per_band}


def build_n1mm_xml(snapshot, cfg, klass='SO'):
    """XML « dynamic score » compatible contestonlinescore.com (format N1MM+)."""
    cfg = cfg or {}
    call = (cfg.get('callsign_contest') or cfg.get('callsign') or 'STATION').upper()
    ops = call
    now = utcnow().strftime('%Y-%m-%d %H:%M:%S')
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
    # post_url_form() soumet la requête au pool _FETCH_EXECUTOR et borne
    # l'ATTENTE du résultat — urlopen(timeout=...) seul ne couvre pas la
    # résolution DNS (getaddrinfo bloquant), qui gèlerait sinon ce thread
    # pour de bon : le thread HTTP servant /scoreboard/push, ou pire,
    # l'unique thread de fond _scoreboard_loop pour le reste de l'expédition
    # (voir logx_utils.fetch_url pour le détail du piège).
    status, resp = post_url_form(s['url'], {'xml': xml}, timeout=20,
                                 headers={'User-Agent': 'LogXAI'})
    if status is None:
        return {'ok': False, 'error': 'Scoreboard injoignable'}
    if status >= 400:
        return {'ok': False,
                'error': f'Scoreboard a répondu HTTP {status} : {(resp or "")[:200].strip()}'}
    _stamp(snap)
    return {'ok': True, 'score': snap['score'], 'qso': snap['qso'],
            'mults': snap['mults'], 'response': (resp or '')[:200].strip()}


def _stamp(snap):
    try:
        data = {'last': utcnow().strftime('%Y-%m-%d %H:%M'),
                'score': snap.get('score'), 'qso': snap.get('qso')}
        tmp = _STAMP_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        os.replace(tmp, _STAMP_FILE)
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
