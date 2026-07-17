# -*- coding: utf-8 -*-
"""Historique d'indicatifs — Super Check Partial (SCP) à la N1MM.

Fusionne trois sources en un index  indicatif → {dept, locator, qso_count,
last_date}  pour :
  - l'AUTOCOMPLÉTION de l'indicatif à la saisie (préfixe ou fragment),
  - le PRÉ-REMPLISSAGE de l'échange attendu : département (concours REF HF,
    scoring dept_dxcc) ou locator (concours THF, scoring km × locators).

Sources, de la moins à la plus fiable (la plus fiable écrase) :
  1. calldb.json 'calls'  : base REF/QRZ (~19 000 indicatifs, dept + locator)
  2. archives/*/log.json  : concours archivés (QSO réellement faits)
  3. shared_log           : log actif (le plus récent)

L'index est un cache mémoire reconstruit au plus toutes les TTL secondes ;
update_from_qso() l'enrichit au fil de l'eau à chaque QSO loggé (pas
d'attente du TTL pour resuggérer une station qu'on vient de travailler).
"""
import json
import os
import re
import threading
import time

TTL = 300          # s — reconstruction complète au plus toutes les 5 min
MAX_SUGGEST = 20

_index = {}        # CALL -> {'dept','locator','qso_count','last_date'}
_built_at = 0.0
_lock = threading.Lock()

_LOC_RE = re.compile(r'^[A-R]{2}[0-9]{2}([A-X]{2})?$', re.I)


def _norm_loc(loc):
    loc = str(loc or '').strip().upper()
    return loc if _LOC_RE.match(loc) else None


def _entry(call):
    return _index.setdefault(call, {
        'dept': None, 'locator': None, 'qso_count': 0, 'last_date': None,
    })


def _feed(call, dept=None, locator=None, count=0, date=None):
    """Fusionne une observation dans l'index. Les champs non vides ÉCRASENT
    (les sources sont parcourues de la moins à la plus fiable)."""
    call = str(call or '').strip().upper()
    if len(call) < 3 or not re.match(r'^[A-Z0-9/]+$', call):
        return
    call = call.split('/')[0] if '/' in call and len(call.split('/')[0]) >= 3 else call
    e = _entry(call)
    dept = str(dept or '').strip()
    if dept:
        e['dept'] = dept
    loc = _norm_loc(locator)
    if loc:
        e['locator'] = loc
    e['qso_count'] += count
    d = str(date or '').strip()
    if d and (e['last_date'] is None or d > e['last_date']):
        e['last_date'] = d


def _feed_qso(q):
    """Observation depuis un QSO réel : le locator reçu fait foi ; le
    département vient de l'échange si le module départements le reconnaît."""
    dept = None
    try:
        from radiocontest_departments import dept_from_exchange
        dept = dept_from_exchange(str(q.get('num_rcvd', '')))
    except Exception:
        pass
    _feed(q.get('call'), dept=dept, locator=q.get('locator'),
          count=1, date=q.get('date'))


def _load_calldb():
    try:
        with open('calldb.json', encoding='utf-8') as f:
            calls = (json.load(f) or {}).get('calls', {})
        for call, info in calls.items():
            if isinstance(info, dict):
                _feed(call, dept=info.get('dept'), locator=info.get('locator'))
    except Exception:
        pass


def _load_archives():
    try:
        from radiocontest_archive import ARCHIVE_DIR
        if not os.path.isdir(ARCHIVE_DIR):
            return
        for name in os.listdir(ARCHIVE_DIR):
            logp = os.path.join(ARCHIVE_DIR, name, 'log.json')
            if not os.path.isfile(logp):
                continue
            try:
                with open(logp, encoding='utf-8') as f:
                    for q in json.load(f) or []:
                        _feed_qso(q)
            except Exception:
                continue
    except Exception:
        pass


def _load_qso_archive():
    """Table SQLite qso_archive : QSO archivés par /log/reset AVANT la
    création du dossier archives/ — l'autre moitié de l'historique."""
    try:
        import sqlite3
        if not os.path.isfile('radiocontest.db'):
            return
        con = sqlite3.connect('radiocontest.db')
        try:
            rows = con.execute(
                'SELECT call, locator, date, extra FROM qso_archive').fetchall()
        except Exception:
            rows = []
        finally:
            con.close()
        for call, locator, date, extra in rows:
            num_rcvd = ''
            try:
                num_rcvd = (json.loads(extra or '{}') or {}).get('num_rcvd', '')
            except Exception:
                pass
            _feed_qso({'call': call, 'locator': locator, 'date': date,
                       'num_rcvd': num_rcvd})
    except Exception:
        pass


def build_index(shared_log=None, force=False):
    """(Re)construit l'index si le TTL est écoulé. Thread-safe."""
    global _built_at
    with _lock:
        if not force and _index and time.time() - _built_at < TTL:
            return _index
        _index.clear()
        _load_calldb()                       # base large, la moins fraîche
        _load_qso_archive()                  # anciens QSO (table SQLite)
        _load_archives()                     # QSO réels archivés (dossiers)
        for q in (shared_log or []):         # log actif = le plus frais
            _feed_qso(q)
        _built_at = time.time()
        return _index


def update_from_qso(qso):
    """Enrichit l'index à chaud quand un QSO vient d'être loggé."""
    with _lock:
        if _index:
            _feed_qso(qso)


def suggest(fragment, shared_log=None, limit=12):
    """Suggestions SCP : d'abord les indicatifs qui COMMENCENT par le
    fragment, puis ceux qui le CONTIENNENT (check partial classique).
    Tri : déjà travaillés d'abord (qso_count), puis alphabétique."""
    fragment = str(fragment or '').strip().upper()
    if len(fragment) < 2:
        return []
    idx = build_index(shared_log)
    starts, contains = [], []
    for call, e in idx.items():
        if call.startswith(fragment):
            starts.append((call, e))
        elif fragment in call:
            contains.append((call, e))
    key = lambda ce: (-ce[1]['qso_count'], ce[0])
    starts.sort(key=key)
    contains.sort(key=key)
    out = []
    for call, e in (starts + contains)[:min(limit, MAX_SUGGEST)]:
        out.append({'call': call, 'dept': e['dept'], 'locator': e['locator'],
                    'qso_count': e['qso_count'], 'last_date': e['last_date'],
                    'worked': e['qso_count'] > 0})
    return out


def lookup(call, shared_log=None):
    """Fiche exacte d'un indicatif (None si inconnu)."""
    call = str(call or '').strip().upper()
    if len(call) < 3:
        return None
    e = build_index(shared_log).get(call)
    if not e:
        return None
    return {'call': call, 'dept': e['dept'], 'locator': e['locator'],
            'qso_count': e['qso_count'], 'last_date': e['last_date'],
            'worked': e['qso_count'] > 0}


def export_index(shared_log=None):
    """Index complet sérialisable pour le client (GET /call/index) — même
    forme que calldb.json ('calls' + 'depts') pour remplacer sa source sans
    changer le rendu, enrichie de qso_count/worked/last_date (historique)."""
    idx = build_index(shared_log)
    calls = {}
    for call, e in idx.items():
        c = {}
        if e['dept']:
            c['dept'] = e['dept']
        if e['locator']:
            c['locator'] = e['locator']
        if e['qso_count']:
            c['qso_count'] = e['qso_count']
            c['worked'] = True
        if e['last_date']:
            c['last_date'] = e['last_date']
        calls[call] = c
    depts = {}
    try:
        from radiocontest_departments import DEPARTMENTS
        depts = DEPARTMENTS
    except Exception:
        pass
    return {'calls': calls, 'depts': depts, 'count': len(calls)}


def exchange_wants(cdef):
    """Ce que l'échange du concours attend, d'après la définition :
    {'dept': bool, 'locator': bool} — pilote le pré-remplissage client."""
    ex = str((cdef or {}).get('exchange', '')).lower()
    stype = str(((cdef or {}).get('scoring', {}) or {}).get('type', ''))
    return {
        'dept': 'dept' in ex or stype == 'dept_dxcc',
        'locator': 'locator' in ex or stype in ('km_x_locators', 'distance_km'),
    }
