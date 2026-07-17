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
radiocontest_qsl à partir de LoTW / eQSL / ClubLog). Absent ⇒ 0 confirmé,
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
        from radiocontest_archive import ARCHIVE_DIR
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
        if not os.path.isfile('radiocontest.db'):
            return out
        con = sqlite3.connect('radiocontest.db')
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
        import radiocontest_dxcc as dxcc
        info = dxcc.lookup(base) or {}
        q['dxcc_country'] = info.get('country')
        q['continent'] = info.get('continent')
        q['cq_zone'] = info.get('cq_zone')
    except Exception:
        q.setdefault('dxcc_country', None)
    try:
        from radiocontest_departments import dept_for_qso, _load_calldb
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
        import radiocontest_dxcc as dxcc
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
            from radiocontest_departments import _load_calldb, DEPARTMENTS
            entry = (_load_calldb() or {}).get(base, {})
            d = entry.get('dept')
            if d in DEPARTMENTS:
                q_dept = d
        except Exception:
            pass
    if q_dept and q_dept not in worked_depts:
        try:
            from radiocontest_departments import DEPARTMENTS
            nm = DEPARTMENTS.get(q_dept, '')
        except Exception:
            nm = ''
        out.append({'type': 'dept', 'scope': 'atlantic',
                    'label': f"NOUVEAU DÉPARTEMENT : {q_dept} {nm}"})
    return out


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
        from radiocontest_departments import METRO, DOM, DEPARTMENTS
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
