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
    score = 0
    for q in entries:
        pts = q.get('points', 0) or 0
        score += pts
        b = str(q.get('band', '?'))
        pb = per_band.setdefault(b, {'qso': 0, 'points': 0})
        pb['qso'] += 1
        pb['points'] += pts
    # WAE : le score = (points QSO + points QTC) × mults — les QTC vivent
    # dans un journal séparé (qtc_log), jamais dans shared_log, donc jamais
    # comptés par la boucle ci-dessus. Sans ceci, le score publié au tableau
    # de bord externe omettait systématiquement les points QTC. No-op pour
    # tout concours non-WAE (aucun QTC n'y est jamais journalisé).
    score += qtc_total(scope_id)

    # Multiplicateurs selon le barème réel du concours (voir
    # logx_scoring.contest_geo_mode, qui lit le multiplicateur EFFECTIF —
    # briques explicites 'bricks' OU preset 'type' legacy). Avant ce
    # correctif, seul le 'type' legacy était consulté : tout concours dont le
    # barème est déclaré en 'bricks' (aucune clé 'type' de premier niveau)
    # retombait TOUJOURS sur le comptage de locators VHF, y compris pour un
    # multiplicateur DXCC/zone/préfixe (style CQ WW/WPX) — publié tel quel au
    # tableau de bord externe.
    mults = 0
    try:
        from logx_scoring import contest_geo_mode
        geo_mode = contest_geo_mode(contest_id)
        if geo_mode == 'dept_dxcc':
            from logx_departments import department_mult_count
            mults = len(department_mult_count(shared_log, scope_id))
        elif geo_mode == 'dxcc':
            import logx_dxcc as dxcc
            mults = len({dxcc.country_key(str(q.get('call', '')).split('/')[0].upper())
                         for q in entries if q.get('call')})
        else:
            # 'dept'/'other' (locator, large_square, na_state, na_section...) :
            # repli existant sur le carré locator 4 caractères -- correct pour
            # un multiplicateur locator/large_square, approximatif pour
            # na_state/na_section (pas de champ état/section fiable dans le
            # log partagé), inchangé par rapport au comportement précédent.
            mults = len({str(q.get('locator', ''))[:4] for q in entries
                         if q.get('locator') and len(str(q.get('locator'))) >= 4})
    except Exception:
        pass

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
