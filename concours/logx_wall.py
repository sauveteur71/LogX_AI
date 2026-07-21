# -*- coding: utf-8 -*-
"""Écran mural d'expédition — agrégation du log commun en temps réel.

Pour une expédition / multi-station (5-10 postes sur le même site, un par bande,
parfois trois par bande en CW/SSB/FT8), tout le monde logge dans le MÊME log
partagé (shared_log, multi-opérateur). Ce module en tire un état compact,
lisible sur un grand écran externe (projecteur/TV) : flux des derniers QSO,
compteur total, rythme, répartition par bande / mode / opérateur, ODX.

Déterministe (aucun réseau) ; alimente GET /data/wall (poll ~3 s).
"""
import datetime
import json
import os

from logx_utils import locator_to_latlon, haversine

# Champs affichables sur l'écran mural + valeurs par défaut (cochés ou non).
# L'indicatif (call) est TOUJOURS affiché ; les autres sont pilotés par la
# config `wall_fields` (menu dans la page CONFIG, section MODE EXPÉDITION).
WALL_FIELD_KEYS = ['time', 'flag', 'country', 'name', 'band', 'freq', 'mode', 'rst', 'op']
WALL_FIELDS_DEFAULT = {
    'time': True, 'flag': True, 'country': True, 'name': False,
    'band': True, 'freq': False, 'mode': True, 'rst': False, 'op': True,
}

_calldb_cache = {'mtime': None, 'calls': {}}


def _load_calldb():
    """Charge calldb.json (indicatif -> {dept, locator, country, name}) avec un
    cache par mtime : on relit seulement si le fichier change. Sert à retrouver
    le PRÉNOM d'un correspondant déjà vu (best-effort, hors-ligne)."""
    path = 'calldb.json'
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    if _calldb_cache['mtime'] != mtime:
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            _calldb_cache['calls'] = data.get('calls', {}) if isinstance(data, dict) else {}
            _calldb_cache['mtime'] = mtime
        except (OSError, ValueError):
            return _calldb_cache['calls']
    return _calldb_cache['calls']


def _wall_fields(cfg):
    """Fusionne la config wall_fields avec les défauts (tolère l'absence)."""
    out = dict(WALL_FIELDS_DEFAULT)
    wf = (cfg or {}).get('wall_fields')
    if isinstance(wf, dict):
        for k in WALL_FIELD_KEYS:
            if k in wf:
                out[k] = bool(wf[k]) if not isinstance(wf[k], str) \
                    else wf[k] not in ('', '0', 'false', 'False')
    return out


def _enrich_recent(recents):
    """Ajoute drapeau + pays (FR) + prénom (si connu) à chaque QSO récent."""
    try:
        import logx_flags as flags
    except Exception:
        flags = None
    calldb = _load_calldb()
    for r in recents:
        call = r.get('call', '')
        if flags:
            fc = flags.flag_and_country(call)
            r['flag'] = fc.get('flag', '')
            r['country'] = fc.get('country', '')
        else:
            r['flag'] = r.get('flag', '')
            r['country'] = r.get('country', '')
        entry = calldb.get(call) or calldb.get(call.upper()) or {}
        r['name'] = (entry.get('name', '') if isinstance(entry, dict) else '') or ''
    return recents


def _entry_dt(e):
    d = (e.get('date', '') or '').replace('-', '').strip()
    t = (e.get('time', '') or '').replace(':', '').strip() or '0000'
    try:
        return datetime.datetime.strptime(f"{d}{t[:4]}", '%Y%m%d%H%M')
    except (ValueError, TypeError):
        return None


def wall_state(shared_log, cfg=None, contest_id=None, recent=25, now=None):
    """État pour l'écran mural. Retourne totaux, rythme, répartitions et les
    `recent` derniers QSO (plus récents d'abord).

    Par défaut on montre TOUS les QSO du log commun (contest_id=None) : sur une
    expédition, l'écran mural doit afficher tout ce qui est loggé, sans dépendre
    du « concours actif » côté serveur (sinon un simple décalage de config masque
    tout). Un contest_id explicite (non None) réactive le filtrage — par PORTÉE
    (contest+année, voir logx_storage.active_scope_id) : un QSO non tagué ne
    compte alors jamais pour un concours précis."""
    cfg = cfg or {}
    now = now or datetime.datetime.utcnow()
    if contest_id:
        from logx_storage import qso_scope_id, active_scope_id
        scope_id = active_scope_id({**cfg, 'contest': contest_id})
        entries = [e for e in (shared_log or [])
                   if qso_scope_id(e) == scope_id]
    else:
        entries = list(shared_log or [])

    my_ll = locator_to_latlon(cfg.get('locator', '') or 'JN15XC')

    per_band, per_mode, per_op = {}, {}, {}
    calls = set()
    score = 0
    last_hour = last_10 = 0
    odx = {'km': 0, 'call': '', 'band': ''}
    dated = []
    for e in entries:
        b = str(e.get('band', '?'))
        m = str(e.get('mode', '?')).upper()
        op = str(e.get('operator', '') or e.get('my_call', '') or '—')
        per_band[b] = per_band.get(b, 0) + 1
        per_mode[m] = per_mode.get(m, 0) + 1
        per_op[op] = per_op.get(op, 0) + 1
        calls.add(str(e.get('call', '')).upper())
        score += e.get('points', 0) or 0
        dt = _entry_dt(e)
        if dt:
            age = (now - dt).total_seconds()
            if age <= 3600:
                last_hour += 1
            if age <= 600:
                last_10 += 1
            dated.append((dt, e))
        # ODX
        loc = str(e.get('locator', '')).strip().upper()
        if my_ll[0] is not None and len(loc) >= 4:
            ll = locator_to_latlon((loc + 'MM')[:6])
            if ll[0] is not None:
                km = haversine(my_ll[0], my_ll[1], ll[0], ll[1])
                if km > odx['km']:
                    odx = {'km': km, 'call': str(e.get('call', '')), 'band': b}

    dated.sort(key=lambda x: x[0], reverse=True)
    recents = []
    for dt, e in dated[:recent]:
        recents.append({
            'call': str(e.get('call', '')).upper(),
            'band': str(e.get('band', '')), 'mode': str(e.get('mode', '')).upper(),
            'op': str(e.get('operator', '') or e.get('my_call', '') or ''),
            'time': e.get('time', ''), 'date': e.get('date', ''),
            'locator': e.get('locator', ''), 'points': e.get('points', 0) or 0,
            'freq': str(e.get('freq', '') or ''),
            'rst_sent': str(e.get('rst_sent', '') or ''),
            'rst_rcvd': str(e.get('rst_rcvd', '') or ''),
        })
    # Si des QSO n'ont pas de date exploitable, compléter la liste récente
    if len(recents) < recent:
        seen = {id(e) for _, e in dated[:recent]}
        for e in reversed(entries):
            if id(e) in seen:
                continue
            recents.append({
                'call': str(e.get('call', '')).upper(),
                'band': str(e.get('band', '')), 'mode': str(e.get('mode', '')).upper(),
                'op': str(e.get('operator', '') or ''), 'time': e.get('time', ''),
                'date': e.get('date', ''), 'locator': e.get('locator', ''),
                'points': e.get('points', 0) or 0,
                'freq': str(e.get('freq', '') or ''),
                'rst_sent': str(e.get('rst_sent', '') or ''),
                'rst_rcvd': str(e.get('rst_rcvd', '') or '')})
            if len(recents) >= recent:
                break

    _enrich_recent(recents)   # drapeau + pays + prénom par QSO

    return {
        'callsign': (cfg.get('callsign_contest') or cfg.get('callsign') or '').upper(),
        'contest': contest_id,
        'wall_fields': _wall_fields(cfg),
        'qso_total': len(entries),
        'unique_calls': len(calls),
        'score': score,
        'rate_hour': last_hour,
        'rate_10min_x6': last_10 * 6,
        'per_band': dict(sorted(per_band.items(), key=lambda kv: -kv[1])),
        'per_mode': dict(sorted(per_mode.items(), key=lambda kv: -kv[1])),
        'per_op': dict(sorted(per_op.items(), key=lambda kv: -kv[1])),
        'odx': odx,
        'recent': recents,
        'now_utc': now.strftime('%H:%M:%S'),
    }
