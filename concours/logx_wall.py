# -*- coding: utf-8 -*-
"""Écran mural d'expédition — agrégation du log commun en temps réel.

Pour une expédition / multi-station (5-10 postes sur le même site, un par bande,
parfois trois par bande en CW/SSB/FT8), tout le monde logge dans le MÊME log
partagé (shared_log, multi-opérateur). Ce module en tire un état compact,
lisible sur un grand écran externe (projecteur/TV) : flux des derniers QSO,
compteur total, rythme, répartition par bande / mode / opérateur, ODX.

Déterministe (aucun réseau) ; alimente GET /data/wall (poll ~3 s). Le champ
`vhf_active` renseigne en plus le mur sur le panneau EME optionnel (jamais
affiché sur un poste HF pur) — les indices solaires et la météo locale sont
consommés par le mur directement via /data/propagation et /data/weather
(déjà servis ailleurs, aucune donnée dupliquée ici).

Chaque QSO de `recent` porte aussi `lat`/`lon` (calculés ici depuis le
locator) et l'état expose `my_lat`/`my_lon` (position de la station) : la
carte Leaflet de logx_wall.html s'en sert pour tracer les rayons QSO, sans
recalcul côté client ni endpoint réseau supplémentaire.

`active_ops` (voir _active_operators()) liste les opérateurs ayant loggué
récemment (proxy « qui est au poste maintenant »), avec leurs qualifications
SSB/CW/DIGI — panneau roulement du mur. Le planning à VENIR (créneaux
horaires) n'est PAS dans cet état : logx_wall.html le récupère séparément
via GET /shifts/list (logx_storage.shifts_sorted), rafraîchi à un rythme
plus lent puisqu'il change rarement.
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


def _qso_goal(cfg):
    """Objectif de QSO TOTAL pour la session/l'événement (config `wall_qso_goal`,
    champ CONFIG section MODE EXPÉDITION) — DISTINCT de rc_rate_goal (objectif
    QSO/HEURE, stocké côté navigateur dans localStorage, affiché dans la barre
    de statut). 0/absent/invalide = pas d'objectif : le mur n'affiche alors pas
    le panneau plutôt qu'une barre bloquée à 0 %."""
    try:
        goal = int((cfg or {}).get('wall_qso_goal', 0) or 0)
    except (TypeError, ValueError):
        goal = 0
    return max(0, goal)


def _enrich_recent(recents):
    """Ajoute drapeau + pays (FR) + prénom (si connu) + lat/lon à chaque QSO
    récent. Le lat/lon (calculé ici depuis le locator, via locator_to_latlon —
    qui accepte 4 ou 6 caractères) alimente les rayons de la carte de l'écran
    mural : plus simple et plus fiable que de refaire ce calcul en JS avec un
    champ locator potentiellement à 4 caractères (locLL() de logx_carte.html
    exige 6 caractères)."""
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
        lat, lon = locator_to_latlon(r.get('locator', ''))
        r['lat'] = round(lat, 4) if lat is not None else None
        r['lon'] = round(lon, 4) if lon is not None else None
    return recents


_HF_BAND_TOKENS = {'1.8', '3.5', '7', '10.1', '14', '18', '21', '24', '28'}
_VHF_UP_TOGGLES = ('band_2m', 'band_70cm', 'band_23cm', 'band_13cm',
                    'band_9cm', 'band_6cm', 'band_3cm', 'band_6mm', 'band_4mm')


def _vhf_active(cfg):
    """True si la station est CONFIGURÉE pour émettre en VHF/UHF et au-delà
    (144 MHz et plus — le 6 m/50 MHz est volontairement exclu, l'EME y est
    hors de portée en pratique). Pilote l'affichage du panneau EME du mur :
    jamais pertinent pour un poste HF pur (encart mort/hors-sujet).

    Même logique que la détection `is_vhf` de do_refresh() (logx_http.py) :
    bandes du concours actif en premier, repli sur les toggles manuels de
    bande (CONFIG) si le concours ne tranche pas (bandes 'all'/inconnues)."""
    cfg = cfg or {}
    from logx_definitions import CONTEST_DEFINITIONS
    contest = cfg.get('contest', '')
    cdef_bands = [str(b) for b in CONTEST_DEFINITIONS.get(contest, {}).get('bands', [])]
    if any(b not in _HF_BAND_TOKENS and b not in ('50', 'all') for b in cdef_bands):
        return True   # une bande >= 144 MHz est explicitement dans la définition
    has_hf_bands = any(b in _HF_BAND_TOKENS for b in cdef_bands)
    is_hf_contest = has_hf_bands and 'all' not in cdef_bands
    if is_hf_contest:
        return False   # concours HF pur défini : les toggles ne doivent pas le contredire
    toggles = cfg.get('toggles', {}) or {}
    return any(toggles.get(k, False) for k in _VHF_UP_TOGGLES)


def _entry_dt(e):
    d = (e.get('date', '') or '').replace('-', '').strip()
    t = (e.get('time', '') or '').replace(':', '').strip() or '0000'
    try:
        return datetime.datetime.strptime(f"{d}{t[:4]}", '%Y%m%d%H%M')
    except (ValueError, TypeError):
        return None


# Fenêtre de récence pour considérer un opérateur "actuellement actif" sur le
# panneau roulement du mur — voir _active_operators().
ACTIVE_OP_WINDOW_MIN = 15


def _active_operators(entries, cfg, now, window_min=ACTIVE_OP_WINDOW_MIN):
    """Opérateur(s) « actuellement actifs » : aucun mécanisme de présence
    dédié n'existe dans l'appli (pas de heartbeat/chat), donc on se sert du
    log commun lui-même comme source de vérité — un opérateur ayant loggué un
    QSO dans les `window_min` dernières minutes est considéré actif. Chaque
    entrée est enrichie avec les qualifications déclarées en CONFIG
    (operators[].modes, voir logx_configuration.html popup OPÉRATEURS) pour
    le badge SSB/CW/DIGI du mur — qualification absente de la config -> True
    par défaut (même convention que /shifts/add et collectConfig() côté
    client : jamais un opérateur silencieusement privé d'un mode)."""
    operators_cfg = {str(o.get('call', '')).upper().strip(): o
                      for o in (cfg.get('operators') or []) if o.get('call')}
    last_seen = {}   # indicatif opérateur -> (dt le plus récent, bande, mode)
    for e in entries:
        op = str(e.get('operator', '') or e.get('my_call', '') or '').strip()
        if not op:
            continue
        dt = _entry_dt(e)
        if not dt:
            continue
        prev = last_seen.get(op)
        if prev is None or dt > prev[0]:
            last_seen[op] = (dt, str(e.get('band', '')), str(e.get('mode', '')).upper())

    active = []
    for op, (dt, band, mode) in last_seen.items():
        age = max(0, (now - dt).total_seconds())   # clamp : horloge légèrement en avance sur le log
        if age > window_min * 60:
            continue
        opcfg = operators_cfg.get(op.upper())
        modes = (opcfg.get('modes') if opcfg else None) or {}
        active.append({
            'call': op,
            'name': (opcfg.get('name') if opcfg else '') or '',
            'modes': {m: bool(modes.get(m, True)) for m in ('ssb', 'cw', 'digi')},
            'band': band,
            'mode': mode,
            'secs_ago': int(age),
        })
    active.sort(key=lambda a: a['secs_ago'])
    return active


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
    active_ops = _active_operators(entries, cfg, now)

    return {
        'callsign': (cfg.get('callsign_contest') or cfg.get('callsign') or '').upper(),
        'contest': contest_id,
        # Position de la station (calculée depuis cfg.locator) — pour planter
        # le marqueur central et l'origine des rayons sur la carte du mur.
        'my_lat': round(my_ll[0], 4) if my_ll[0] is not None else None,
        'my_lon': round(my_ll[1], 4) if my_ll[1] is not None else None,
        'vhf_active': _vhf_active(cfg),
        'wall_fields': _wall_fields(cfg),
        'qso_total': len(entries),
        'qso_goal': _qso_goal(cfg),
        'unique_calls': len(calls),
        'score': score,
        'rate_hour': last_hour,
        'rate_10min_x6': last_10 * 6,
        'per_band': dict(sorted(per_band.items(), key=lambda kv: -kv[1])),
        'per_mode': dict(sorted(per_mode.items(), key=lambda kv: -kv[1])),
        'per_op': dict(sorted(per_op.items(), key=lambda kv: -kv[1])),
        'odx': odx,
        'recent': recents,
        'active_ops': active_ops,
        'now_utc': now.strftime('%H:%M:%S'),
    }
