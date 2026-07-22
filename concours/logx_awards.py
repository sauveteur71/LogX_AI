# -*- coding: utf-8 -*-
"""Suivi de diplômes & historique — le « carnet de trafic permanent ».

Contrairement au scoring (qui ne compte QUE le concours en cours), ce module
raisonne sur TOUTE la vie de la station : log actif + dossiers archives/ +
table SQLite qso_archive. Il fournit :

  - history(call)      : tous les QSO passés avec une station (panneau
                         « déjà contacté » à la frappe).
  - award_summary()    : tableau de bord travaillé / confirmé par diplôme
                         (DXCC pays, départements REF, continents, zones CQ).
  - new_one(call,band) : « nouveau pays / nouveau département » à VIE (pas
                         seulement dans le concours) — alerte pendant le trafic.

Le statut « confirmé » vient de qsl_confirmations.json (rempli par
logx_qsl à partir de LoTW / eQSL / ClubLog). Absent ⇒ 0 confirmé,
le reste fonctionne quand même (travaillé/manquant).
"""
import json
import os
import threading
import time

TTL = 120
_cache = {'qsos': None, 'at': 0.0}
_lock = threading.Lock()

CONFIRM_FILE = 'qsl_confirmations.json'


# ─── COLLECTE DE TOUS LES QSO (log + archives + qso_archive) ──────────────────

def _dedup_key(q):
    return (str(q.get('call', '')).upper().strip(), str(q.get('band', '')),
            str(q.get('mode', '')).upper(), str(q.get('date', '')),
            str(q.get('time', '')))


def _read_archives():
    out = []
    try:
        from logx_archive import ARCHIVE_DIR
        if os.path.isdir(ARCHIVE_DIR):
            for name in os.listdir(ARCHIVE_DIR):
                logp = os.path.join(ARCHIVE_DIR, name, 'log.json')
                if os.path.isfile(logp):
                    try:
                        with open(logp, encoding='utf-8') as f:
                            for q in json.load(f) or []:
                                q.setdefault('_src', name)
                                out.append(q)
                    except Exception:
                        continue
    except Exception:
        pass
    return out


def _read_qso_archive():
    out = []
    try:
        import sqlite3
        if not os.path.isfile('logx.db'):
            return out
        con = sqlite3.connect('logx.db')
        try:
            rows = con.execute('SELECT call, band, mode, contest, date, time, '
                               'locator, extra FROM qso_archive').fetchall()
        except Exception:
            rows = []
        finally:
            con.close()
        for call, band, mode, contest, date, tm, locator, extra in rows:
            q = {'call': call, 'band': band, 'mode': mode, 'contest': contest,
                 'date': date, 'time': tm, 'locator': locator, '_src': 'qso_archive'}
            try:
                q.update(json.loads(extra or '{}') or {})
            except Exception:
                pass
            out.append(q)
    except Exception:
        pass
    return out


def collect_all_qsos(shared_log=None, force=False):
    """Tous les QSO de la station, dédupliqués, enrichis (pays/continent/dept).
    Caché TTL secondes ; invalidé par invalidate()."""
    with _lock:
        if not force and _cache['qsos'] is not None and time.time() - _cache['at'] < TTL:
            base = _cache['qsos']
        else:
            raw = []
            raw.extend(_read_qso_archive())     # anciens (moins prioritaires)
            raw.extend(_read_archives())
            seen, base = set(), []
            for q in raw:
                k = _dedup_key(q)
                if k in seen:
                    continue
                seen.add(k)
                base.append(_enrich(dict(q)))
            _cache['qsos'] = base
            _cache['at'] = time.time()
        # Le log actif est TOUJOURS ajouté frais (jamais mis en cache figé)
        seen = {_dedup_key(q) for q in base}
        merged = list(base)
        for q in (shared_log or []):
            k = _dedup_key(q)
            if k not in seen:
                seen.add(k)
                merged.append(_enrich(dict(q)))
        return merged


def invalidate():
    with _lock:
        _cache['qsos'] = None


_calldb = None


def _enrich(q):
    """Ajoute dxcc_country / continent / cq_zone / dept à un QSO."""
    global _calldb
    call = str(q.get('call', '')).upper().strip()
    base = call.split('/')[0] if '/' in call else call
    try:
        import logx_dxcc as dxcc
        info = dxcc.lookup(base) or {}
        q['dxcc_country'] = info.get('country')
        q['continent'] = info.get('continent')
        q['cq_zone'] = info.get('cq_zone')
    except Exception:
        q.setdefault('dxcc_country', None)
    try:
        from logx_departments import dept_for_qso, _load_calldb
        if _calldb is None:
            _calldb = _load_calldb()
        q['dept'] = dept_for_qso(q, _calldb)
    except Exception:
        q.setdefault('dept', None)
    return q


# ─── CONFIRMATIONS (LoTW / eQSL / ClubLog) ───────────────────────────────────

def _load_confirmations():
    try:
        with open(CONFIRM_FILE, encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _confirm_key(q):
    return f"{str(q.get('call','')).upper().strip()}|{q.get('band','')}|{str(q.get('mode','')).upper()}"


# ─── HISTORIQUE D'UNE STATION (panneau « déjà contacté ») ─────────────────────

def history(call, shared_log=None, limit=15):
    """Tous les QSO passés avec `call` (plus récents d'abord), avec statut
    confirmé. Retourne {call, count, confirmed, qsos:[...], bands, first, last}."""
    call = str(call or '').upper().strip()
    if len(call) < 3:
        return {'call': call, 'count': 0, 'qsos': []}
    base_target = call.split('/')[0] if '/' in call else call
    conf = _load_confirmations()
    rows = []
    for q in collect_all_qsos(shared_log):
        c = str(q.get('call', '')).upper().strip()
        if c != call and c.split('/')[0] != base_target:
            continue
        is_conf = bool(conf.get(_confirm_key(q)))
        rows.append({
            'date': q.get('date', ''), 'time': q.get('time', ''),
            'band': str(q.get('band', '')), 'mode': str(q.get('mode', '')),
            'contest': q.get('contest', ''), 'locator': q.get('locator', ''),
            'dept': q.get('dept'), 'confirmed': is_conf,
        })
    rows.sort(key=lambda r: (r['date'], r['time']), reverse=True)
    bands = sorted({r['band'] for r in rows if r['band']})
    dates = sorted(r['date'] for r in rows if r['date'])
    country = None
    dept = None
    for q in collect_all_qsos(shared_log):
        if str(q.get('call', '')).upper().split('/')[0] == base_target:
            country = country or q.get('dxcc_country')
            dept = dept or q.get('dept')
    return {
        'call': call, 'count': len(rows),
        'confirmed': sum(1 for r in rows if r['confirmed']),
        'bands': bands, 'country': country, 'dept': dept,
        'first': dates[0] if dates else None,
        'last': dates[-1] if dates else None,
        'qsos': rows[:limit],
    }


# ─── DÉTECTION « NOUVEAU À VIE » (pays / département) ─────────────────────────

def new_one(call, band='', mode='', shared_log=None):
    """Un QSO avec `call` sur `band` apporterait-il un NOUVEAU pays ou
    département jamais contacté (à vie) ? Renvoie une liste de dicts
    {type, scope, label} — vide si rien de neuf."""
    call = str(call or '').upper().strip()
    if len(call) < 3:
        return []
    base = call.split('/')[0] if '/' in call else call
    try:
        import logx_dxcc as dxcc
        info = dxcc.lookup(base) or {}
    except Exception:
        info = {}
    country = info.get('country')

    worked_countries, worked_ctry_band = set(), set()
    worked_depts = set()
    q_dept = None
    for q in collect_all_qsos(shared_log):
        c = q.get('dxcc_country')
        if c:
            worked_countries.add(c)
            worked_ctry_band.add((c, str(q.get('band', ''))))
        if q.get('dept'):
            worked_depts.add(q['dept'])
        if str(q.get('call', '')).upper().split('/')[0] == base and q.get('dept'):
            q_dept = q_dept or q['dept']

    out = []
    if country and country not in worked_countries:
        out.append({'type': 'dxcc', 'scope': 'atlantic',
                    'label': f"NOUVEAU PAYS : {country} (jamais contacté)"})
    elif country and band and (country, str(band)) not in worked_ctry_band:
        out.append({'type': 'dxcc', 'scope': 'band',
                    'label': f"{country} nouveau sur {band} MHz"})
    # Département connu de la station (via calldb) et jamais contacté
    if not q_dept:
        try:
            from logx_departments import _load_calldb, DEPARTMENTS
            entry = (_load_calldb() or {}).get(base, {})
            d = entry.get('dept')
            if d in DEPARTMENTS:
                q_dept = d
        except Exception:
            pass
    if q_dept and q_dept not in worked_depts:
        try:
            from logx_departments import DEPARTMENTS
            nm = DEPARTMENTS.get(q_dept, '')
        except Exception:
            nm = ''
        out.append({'type': 'dept', 'scope': 'atlantic',
                    'label': f"NOUVEAU DÉPARTEMENT : {q_dept} {nm}"})
    return out


# ─── CIBLES PROACTIVES (jamais travaillées à VIE, spottées maintenant) ───────

def spotted_new_ones(shared_log, spots_by_label=None, max_n=8):
    """Parmi les stations actuellement SPOTTÉES sur le cluster, celles qui
    apporteraient un pays (DXCC) ou un département français JAMAIS travaillé
    À VIE (pas seulement dans le concours en cours — pour ça, voir
    logx_countries.country_targets/logx_departments.department_
    targets, qui restent scopés au concours actif). Suggestions poussées
    PROACTIVEMENT par le coach (/coach/state), sans action de l'utilisateur.
    Le pays se déduit directement du préfixe (cty.dat, aucun réseau) ; le
    département d'un correspondant français vient de calldb (déjà indexé par
    logx_callhistory.build_index), pas de lookup réseau non plus."""
    import logx_dxcc as dxcc
    qsos = collect_all_qsos(shared_log)
    worked_countries = {q['dxcc_country'] for q in qsos if q.get('dxcc_country')}
    worked_depts = {q['dept'] for q in qsos if q.get('dept')}

    from logx_callhistory import build_index
    idx = build_index(shared_log)

    spotted = {}
    for label, spots in (spots_by_label or {}).items():
        for sp in spots or []:
            if isinstance(sp, dict):
                c = str(sp.get('dx') or sp.get('call') or '')
                freq = sp.get('freq', '')
            else:
                c = str(sp[0]) if sp else ''
                freq = sp[1] if len(sp) > 1 else ''
            c = c.strip().upper()
            base = c.split('/')[0] if '/' in c and len(c.split('/')[0]) >= 3 else c
            if len(base) >= 3 and base not in spotted:
                spotted[base] = {'freq': freq, 'band': label}

    out = []
    for call, data in spotted.items():
        info = None
        try:
            info = dxcc.lookup(call)
        except Exception:
            pass
        country = (info or {}).get('country')
        if country and country not in worked_countries:
            out.append({'type': 'dxcc', 'call': call, 'label': country, **data})
            continue    # un seul type de nouveauté par spot (évite le bruit)
        dept = (idx.get(call) or {}).get('dept')
        if dept and dept not in worked_depts:
            try:
                from logx_departments import DEPARTMENTS
                name = DEPARTMENTS.get(dept, '')
            except Exception:
                name = ''
            out.append({'type': 'dept', 'call': call,
                       'label': f'{dept} {name}'.strip(), **data})
    out.sort(key=lambda t: t['call'])
    return out[:max_n]


# ─── TABLEAU DE BORD DIPLÔMES ─────────────────────────────────────────────────

def award_summary(shared_log=None):
    """Travaillé / confirmé par diplôme, sur toute la vie de la station."""
    conf = _load_confirmations()
    qsos = collect_all_qsos(shared_log)

    countries_w, countries_c = set(), set()
    depts_w, depts_c = set(), set()
    conts, zones = set(), set()
    per_band = {}          # bande -> {qso, dxcc:set}
    total_conf = 0
    for q in qsos:
        is_conf = bool(conf.get(_confirm_key(q)))
        total_conf += 1 if is_conf else 0
        c = q.get('dxcc_country')
        if c:
            countries_w.add(c)
            if is_conf:
                countries_c.add(c)
        d = q.get('dept')
        if d:
            depts_w.add(d)
            if is_conf:
                depts_c.add(d)
        if q.get('continent'):
            conts.add(q['continent'])
        if q.get('cq_zone'):
            zones.add(q['cq_zone'])
        b = str(q.get('band', '?'))
        pb = per_band.setdefault(b, {'qso': 0, 'dxcc': set()})
        pb['qso'] += 1
        if c:
            pb['dxcc'].add(c)

    try:
        from logx_departments import METRO, DOM, DEPARTMENTS
        metro_missing = [d for d in METRO if d not in depts_w]
        dom_missing = [d for d in DOM if d not in depts_w]
    except Exception:
        METRO, DOM, DEPARTMENTS = [], [], {}
        metro_missing, dom_missing = [], []

    return {
        'qso_total': len(qsos),
        'confirmed_total': total_conf,
        'has_confirmations': bool(conf),
        'dxcc': {'worked': len(countries_w), 'confirmed': len(countries_c)},
        'departments': {
            'metro_worked': len([d for d in depts_w if d in METRO]),
            'metro_total': len(METRO),
            'metro_confirmed': len([d for d in depts_c if d in METRO]),
            'dom_worked': len([d for d in depts_w if d in DOM]),
            'missing': (metro_missing + dom_missing)[:40],
        },
        'continents': sorted(conts),
        'cq_zones': sorted(zones),
        'per_band': {b: {'qso': v['qso'], 'dxcc': len(v['dxcc'])}
                     for b, v in sorted(per_band.items())},
    }


# ─── WORKED MATRIX (grille bande × CW/Phone/Digital) ─────────────────────────

def _mode_category(mode):
    """Classe un mode dans une des 3 catégories usuelles des diplômes DXCC/WAS."""
    m = str(mode or '').upper()
    if m == 'CW':
        return 'CW'
    if m in ('SSB', 'USB', 'LSB', 'AM', 'FM'):
        return 'PHONE'
    return 'DIGITAL'    # FT8/FT4/JS8/RTTY/PSK/D-STAR/inconnu


def _band_sort_key(b):
    try:
        return float(b)
    except (TypeError, ValueError):
        return 9999.0


def worked_matrix(shared_log=None):
    """Grille bande × catégorie de mode : nb de QSO travaillés/confirmés par
    case, sur toute la vie de la station (comme award_summary). Utile pour
    visualiser d'un coup d'œil les cases DXCC/WAS encore vides."""
    conf = _load_confirmations()
    qsos = collect_all_qsos(shared_log)
    cats = ('CW', 'PHONE', 'DIGITAL')
    grid = {}
    for q in qsos:
        b = str(q.get('band', '?'))
        cat = _mode_category(q.get('mode', ''))
        cell = grid.setdefault(b, {c: {'qso': 0, 'confirmed': 0} for c in cats})[cat]
        cell['qso'] += 1
        if conf.get(_confirm_key(q)):
            cell['confirmed'] += 1
    bands = sorted(grid.keys(), key=_band_sort_key)
    return {
        'bands': bands, 'categories': list(cats),
        'grid': {b: grid[b] for b in bands},
        'totals': {c: sum(grid[b][c]['qso'] for b in bands) for c in cats},
    }


# ─── RECORD DX (remplace l'ancien champ manuel record_dx) ────────────────────
# Un chiffre unique saisi à la main n'a pas de sens pour un opérateur
# multi-bandes : 3000 km est banal en HF, exceptionnel en VHF/UHF (le même
# défaut que corrigeait déjà logx_bands.py pour les seuils d'alerte). Calculé
# depuis le vrai locator de chaque QSO archivé (haversine), jamais déclaratif.

def dx_records(my_locator, shared_log=None):
    """Plus grande distance (km) travaillée PAR BANDE, sur toute la vie de la
    station. Renvoie {'overall': {...} | None, 'by_band': {bande: {...}}}.

    Filtre les distances IMPLAUSIBLES pour la bande (locator erroné, mauvais
    libellé de bande dans une archive ancienne, EME mal étiqueté...) avec le
    même plafond déjà utilisé pour écarter les spots aberrants — cf. le cas
    réel documenté dans logx_scoring.py : « FK8HA à 17 014 km en 144 MHz »
    proposé à l'agent avant ce garde-fou. Sans lui, un "record" himalayen
    en UHF serait affiché tel quel, ce qui n'inspirerait pas confiance dans
    un chiffre calculé automatiquement."""
    from logx_utils import haversine, locator_to_latlon
    from logx_scoring import _MAX_PLAUSIBLE_KM
    my_ll = locator_to_latlon(my_locator or '')
    if not my_ll[0]:
        return {'overall': None, 'by_band': {}}

    best = {}  # bande -> {call, locator, dist_km, date, mode}
    for q in collect_all_qsos(shared_log):
        loc = q.get('locator', '')
        if not loc:
            continue
        dx_ll = locator_to_latlon(loc)
        if not dx_ll[0]:
            continue
        dist = haversine(my_ll[0], my_ll[1], dx_ll[0], dx_ll[1])
        band = str(q.get('band', '?'))
        cap = _MAX_PLAUSIBLE_KM.get(band)
        if cap and dist > cap:
            continue
        cur = best.get(band)
        if not cur or dist > cur['dist_km']:
            best[band] = {'call': q.get('call', ''), 'locator': loc, 'dist_km': dist,
                          'date': q.get('date', ''), 'mode': q.get('mode', '')}

    bands = sorted(best.keys(), key=_band_sort_key)
    overall = max(best.values(), key=lambda r: r['dist_km']) if best else None
    if overall:
        overall = {**overall, 'band': next(b for b in bands if best[b] is overall)}
    return {'overall': overall, 'by_band': {b: best[b] for b in bands}}
