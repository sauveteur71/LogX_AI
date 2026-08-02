# -*- coding: utf-8 -*-
"""Recherche d'indicatifs sur QRZ.com (API XML).

L'opérateur saisit ses identifiants QRZ dans CONFIG (stockés côté serveur,
jamais renvoyés au navigateur — comme les accès ON4KST). À chaque indicatif
saisi, le logbook affiche nom / QTH / locator / pays de la station contactée.

Deux étapes API :
  1. auth : xmldata.qrz.com/xml/current/?username=U;password=P → <Key> de session
  2. lookup : ...?s=KEY;callsign=CALL → <Callsign> (fname, name, addr2, grid...)

La session (~24 h) et les recherches sont mises en cache. Une recherche
enrichit aussi calldb.json (locator) au bénéfice du reste de l'app.
NB : QRZ limite les champs détaillés aux comptes abonnés XML ; sans abonnement
on récupère au moins le pays. Toute erreur → dict {'ok': False, 'error': ...}.
"""
import re
import time
import threading

_session = {'key': '', 'ts': 0}
_session_lock = threading.Lock()
_lookup_cache = {}          # CALL -> {'ts', 'data'}
SESSION_TTL = 20 * 3600     # re-auth avant l'expiration ~24 h
LOOKUP_TTL = 24 * 3600      # une fiche QRZ ne change quasiment jamais

BASE = 'https://xmldata.qrz.com/xml/current/'


def _tag(xml, name):
    """Contenu d'une balise <name>...</name> (insensible au namespace)."""
    m = re.search(rf'<{name}>(.*?)</{name}>', xml, re.S | re.I)
    return m.group(1).strip() if m else ''


QRZ_TIMEOUT = 6  # recherche interactive (frappe d'indicatif) : pas de valeur "confort"


def _authenticate(user, pw):
    """Ouvre une session QRZ, retourne (key, error).

    fetch_url(log_url=False) : cette URL contient le mot de passe QRZ en clair
    dans la query string — fetch_url() journalise normalement `url[:60]` en
    cas d'échec réseau, ce qui pour un indicatif court (3-4 caractères,
    courant en concours : K5D, N2S...) ferait apparaître les premiers
    caractères du mot de passe sur la console. log_url=False supprime cette
    journalisation pour CET appel précis, sans dupliquer fetch_url()
    elle-même (borne DNS/timeout déjà correcte, partagée avec tout le reste
    de l'app — voir logx_utils.fetch_url)."""
    import urllib.parse as up
    from logx_utils import fetch_url
    url = f'{BASE}?username={up.quote(user)};password={up.quote(pw)};agent=LogXAI'
    xml = fetch_url(url, timeout=QRZ_TIMEOUT, log_url=False)
    if not xml:
        return '', 'QRZ injoignable'
    key = _tag(xml, 'Key')
    if key:
        return key, ''
    err = _tag(xml, 'Error') or 'Authentification QRZ refusée'
    return '', err


def _get_session(user, pw):
    """Clé de session valide (ré-authentifie si expirée). (key, error).

    _authenticate() (appel réseau, jusqu'à QRZ_TIMEOUT s) s'exécute HORS du
    verrou : le tenir pendant l'appel bloquerait tout autre indicatif tapé
    entre-temps derrière cette même attente, avant même sa propre tentative."""
    with _session_lock:
        if _session['key'] and time.time() - _session['ts'] < SESSION_TTL:
            return _session['key'], ''
    key, err = _authenticate(user, pw)
    if key:
        with _session_lock:
            _session.update(key=key, ts=time.time())
    return key, err


def lookup(call, user, pw):
    """Recherche un indicatif. Retourne {'ok', 'call', 'name', 'qth', 'state',
    'country', 'grid', 'dxcc'} ou {'ok': False, 'error': ...}."""
    call = (call or '').upper().strip()
    if not call:
        return {'ok': False, 'error': 'Indicatif vide'}
    if not user or not pw:
        return {'ok': False, 'error': 'Identifiants QRZ non configurés'}
    hit = _lookup_cache.get(call)
    if hit and time.time() - hit['ts'] < LOOKUP_TTL:
        return hit['data']

    from logx_utils import fetch_url
    key, err = _get_session(user, pw)
    if not key:
        return {'ok': False, 'error': err}
    xml = fetch_url(f'{BASE}?s={key};callsign={call}', timeout=QRZ_TIMEOUT)
    if not xml:
        return {'ok': False, 'error': 'QRZ injoignable'}
    # Session expirée : ré-authentifier une fois
    if 'Session Timeout' in xml or (_tag(xml, 'Error') and 'timeout' in _tag(xml, 'Error').lower()):
        with _session_lock:
            _session['key'] = ''
        key, err = _get_session(user, pw)
        if not key:
            return {'ok': False, 'error': err}
        xml = fetch_url(f'{BASE}?s={key};callsign={call}', timeout=QRZ_TIMEOUT) or ''

    if '<Callsign>' not in xml:
        return {'ok': False, 'error': _tag(xml, 'Error') or 'Indicatif introuvable sur QRZ'}

    fname = _tag(xml, 'fname')
    lname = _tag(xml, 'name')
    name = ' '.join(p for p in (fname, lname) if p).strip()
    city = _tag(xml, 'addr2')
    state = _tag(xml, 'state')
    grid = _tag(xml, 'grid').upper()
    data = {
        'ok': True, 'call': call, 'name': name,
        'qth': ', '.join(p for p in (city, state) if p),
        'state': state, 'country': _tag(xml, 'country'),
        'grid': grid, 'dxcc': _tag(xml, 'dxcc'),
    }
    _lookup_cache[call] = {'ts': time.time(), 'data': data}
    _enrich_calldb(call, grid, data['country'])
    return data


def _enrich_calldb(call, grid, country):
    """Ajoute le locator QRZ à calldb.json (bénéficie au reste de l'app)."""
    if not grid or len(grid) < 4:
        return
    try:
        import json, os
        from logx_storage import save_json_atomic, calldb_lock
        # calldb_lock protège tout le cycle lecture-modification-écriture ici
        # (pas seulement l'écriture) : deux lookups QRZ concurrents ne doivent
        # pas pouvoir lire la même version du fichier avant qu'aucun n'écrive.
        # save_json_atomic est appelée avec lock=None car calldb_lock (non
        # réentrant) est déjà tenu par ce bloc.
        with calldb_lock:
            db = {}
            if os.path.exists('calldb.json'):
                with open('calldb.json', encoding='utf-8') as f:
                    db = json.load(f)
            calls = db.setdefault('calls', {})
            entry = calls.setdefault(call, {})
            if not entry.get('locator'):
                entry['locator'] = grid
            if country and not entry.get('country'):
                entry['country'] = country
            save_json_atomic('calldb.json', db, lock=None, compact=True)
    except Exception:
        pass


def qrz_settings(cfg):
    """Identifiants QRZ depuis la config CLIENT puis config.json."""
    cfg = cfg or {}
    user = (cfg.get('qrz_user') or '').strip()
    pw = cfg.get('qrz_password') or ''
    if not user or not pw:
        try:
            import json
            with open('config.json', encoding='utf-8') as f:
                q = (json.load(f).get('qrz', {}) or {})
            user = user or q.get('user', '')
            pw = pw or q.get('password', '')
        except Exception:
            pass
    return {'enabled': bool(user and pw), 'user': user, 'pw': pw}
