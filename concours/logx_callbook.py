# -*- coding: utf-8 -*-
"""Callbook en cascade : QRZ.com (payant, le plus complet) -> HamQTH (gratuit,
mondial) -> HamDB (gratuit, base FCC américaine uniquement — vérifié : un
indicatif hors USA y renvoie NOT_FOUND sur tous les champs).

Avant ce module, un opérateur sans abonnement QRZ XML n'avait AUCUNE fiche
correspondant à la frappe dans le logbook (endpoint /qrz/lookup renvoyait
"QRZ non configuré" et s'arrêtait là). La cascade essaie chaque source dans
l'ordre et retourne la première réponse positive, avec `source` pour que le
client sache d'où vient l'info (et adapte l'affichage : HamQTH/HamDB ne
donnent jamais le nom de l'opérant, contrairement à QRZ).

HamDB : API JSON publique sans clé (https://api.hamdb.org/v1/<call>/json/<app>),
vérifiée en direct (W1AW -> fiche complète, F4GLD -> NOT_FOUND partout —
confirme le périmètre USA uniquement documenté nulle part officiellement).
"""
import json
import threading
import time

_cache = {}          # CALL -> {'ts', 'data'}
CACHE_TTL = 24 * 3600  # les fiches HamQTH/HamDB gratuites ne sont pas mises en
                       # cache en amont (contrairement à QRZ) : on évite ici de
                       # marteler ces services publics pour le même indicatif.
NEG_CACHE_TTL = 5 * 60  # un échec (introuvable/injoignable) se recache court :
                        # retaper/reconfirmer le même indicatif dans les minutes
                        # qui suivent ne doit pas rejouer toute la cascade réseau.

# Disjoncteur réseau : en terrain /P sans Internet, chaque NOUVEL indicatif tapé
# déclenchait la cascade complète (QRZ + HamQTH + HamDB, jusqu'à ~76s cumulés)
# sans jamais s'accélérer. Après quelques échecs consécutifs sur des indicatifs
# DIFFÉRENTS (signe que le réseau est absent, pas que ces calls sont introuvables
# par coïncidence), on coupe court à la cascade pendant un temps de repos.
_circuit = {'fails': 0, 'until': 0}
CIRCUIT_THRESHOLD = 3
CIRCUIT_COOLDOWN = 90
_lock = threading.Lock()  # protège _cache/_circuit, mutés depuis le thread HTTP
                          # ET depuis _bulk_resolve_run() dans son propre thread


def circuit_status():
    """État du disjoncteur pour affichage client (voir GET /data/network_status,
    consommé par logx_statusbar.js) : le disjoncteur lui-même existe depuis la
    pause hors-ligne ci-dessus, seule cette fonction est nouvelle — elle ne fait
    que rendre visible un état déjà calculé, jusqu'ici silencieux (uniquement
    lisible dans le message d'erreur d'un /qrz/lookup individuel)."""
    wait = _circuit['until'] - time.time()
    return {'open': wait > 0, 'wait_s': max(0, int(wait))}


def lookup_hamdb(call):
    """Interroge HamDB (FCC US uniquement). {'ok', 'call', 'name', 'qth',
    'state', 'country', 'grid', 'dxcc': '', 'source': 'hamdb'} ou
    {'ok': False, 'error': ...}."""
    from logx_utils import fetch_url
    call = (call or '').upper().strip()
    if not call:
        return {'ok': False, 'error': 'Indicatif vide'}
    text = fetch_url(f'https://api.hamdb.org/v1/{call}/json/logxai', timeout=8)
    if not text:
        return {'ok': False, 'error': 'HamDB injoignable'}
    try:
        cs = json.loads(text).get('hamdb', {}).get('callsign', {})
    except (ValueError, AttributeError):
        return {'ok': False, 'error': 'Réponse HamDB illisible'}

    def field(name):
        v = cs.get(name, '')
        return '' if v == 'NOT_FOUND' else v

    if not field('call'):
        return {'ok': False, 'error': "Indicatif introuvable sur HamDB (base FCC USA "
                                      "uniquement — les indicatifs hors USA n'y sont pas)"}
    name = ' '.join(p for p in (field('fname'), field('name')) if p).strip()
    return {'ok': True, 'call': call, 'name': name,
            'qth': ', '.join(p for p in (field('addr2'), field('state')) if p),
            'state': field('state'), 'country': field('country'),
            'grid': field('grid').upper(), 'dxcc': '', 'source': 'hamdb'}


def _previous_qso_hit(call, shared_log):
    """Fiche dérivée de l'historique local (calldb + archives + log actif,
    voir logx_callhistory) — jamais de réseau. None si l'indicatif n'a jamais
    été croisé ou si aucun locator n'en est dérivable (un dept seul ne suffit
    pas à afficher grand-chose ici)."""
    if shared_log is None:
        return None
    try:
        from logx_callhistory import lookup as history_lookup
        h = history_lookup(call, shared_log)
    except Exception:
        return None
    if not h or not h.get('locator'):
        return None
    return {'ok': True, 'call': call, 'name': '', 'qth': '', 'state': '',
            'country': '', 'grid': h['locator'], 'dxcc': '',
            'source': 'previous_qso'}


def lookup(call, cfg, shared_log=None):
    """Cascade complète. Retourne le premier résultat positif ; si tout
    échoue, {'ok': False, 'error': <résumé des 3 échecs>}.

    `shared_log`, si fourni, active un filet « Previous QSOs » (historique
    local — calldb/archives/log, voir logx_callhistory) à deux moments :
    - EN TÊTE si le disjoncteur réseau est ouvert (probablement hors ligne) :
      inutile d'attendre le cooldown pour un échec garanti si l'indicatif a
      déjà été croisé — c'est la seule source disponible dans l'immédiat ;
    - EN DERNIER RECOURS si QRZ/HamQTH/HamDB échouent tous les trois malgré
      un réseau disponible (indicatif introuvable sur les 3 services alors
      qu'on l'a déjà travaillé/croisé par le passé)."""
    call = (call or '').upper().strip()
    if not call:
        return {'ok': False, 'error': 'Indicatif vide'}

    with _lock:
        hit = _cache.get(call)
        if hit:
            ttl = CACHE_TTL if hit['data'].get('ok') else NEG_CACHE_TTL
            if time.time() - hit['ts'] < ttl:
                return hit['data']

        now = time.time()
        circuit_open = now < _circuit['until']
        wait = int(_circuit['until'] - now) if circuit_open else 0

    if circuit_open:
        local = _previous_qso_hit(call, shared_log)
        if local:
            return local
        return {'ok': False, 'error': f"Callbook en pause ({wait}s) : les services "
                'ont été injoignables sur les derniers indicatifs (probablement '
                'hors connexion) — nouvelle tentative automatique ensuite.'}

    import logx_qrz as qrz
    from logx_clusters import lookup_hamqth

    errors = []
    settings = qrz.qrz_settings(cfg)
    if settings['enabled']:
        r = qrz.lookup(call, settings['user'], settings['pw'])
        if r.get('ok'):
            r['source'] = 'qrz'
            with _lock:
                _circuit['fails'] = 0
            return r  # déjà mis en cache par qrz.py lui-même (24 h)
        errors.append(f"QRZ : {r.get('error', '?')}")

    hq = lookup_hamqth(call)
    if hq and hq.get('locator'):
        data = {'ok': True, 'call': call, 'name': '', 'qth': '', 'state': '',
                'country': hq.get('country', ''), 'grid': hq.get('locator', '').upper(),
                'dxcc': '', 'source': 'hamqth'}
        with _lock:
            _cache[call] = {'ts': time.time(), 'data': data}
            _circuit['fails'] = 0
        return data
    errors.append("HamQTH : indicatif introuvable ou service injoignable")

    hd = lookup_hamdb(call)
    if hd.get('ok'):
        with _lock:
            _cache[call] = {'ts': time.time(), 'data': hd}
            _circuit['fails'] = 0
        return hd
    errors.append(f"HamDB : {hd.get('error', '?')}")

    local = _previous_qso_hit(call, shared_log)
    if local:
        return local

    result = {'ok': False, 'error': ' · '.join(errors)}
    with _lock:
        _cache[call] = {'ts': time.time(), 'data': result}
        _circuit['fails'] += 1
        if _circuit['fails'] >= CIRCUIT_THRESHOLD:
            _circuit['until'] = time.time() + CIRCUIT_COOLDOWN
            _circuit['fails'] = 0
    return result


# ─── RE-RÉSOLUTION EN MASSE (locator/état, cty/QRZ/ClubLog) ──────────────────
# OpsLog permet de re-résoudre en masse tout ou partie du log (cty/QRZ/
# ClubLog). Rien de tel ici : le seul lookup existant est le callbook en
# direct à la frappe (fonction lookup() ci-dessus), un QSO à la fois.
#
# Tourne en THREAD DE FOND (comme logx_update._download_thread) : un log de
# plusieurs milliers de QSO peut représenter des centaines d'indicatifs
# DISTINCTS, chacun une requête réseau (jusqu'à ~2s via la cascade QRZ->
# HamQTH->HamDB) — synchrone dans un handler HTTP, ça timeout. Dédupliqué par
# INDICATIF (pas par QSO) : 1000 QSO d'un même DXpédition ne doivent déclencher
# qu'UN seul lookup, pas 1000.
#
# PAR DÉFAUT NON DESTRUCTIF : ne remplit que les locator/état VIDES. Un QSO
# dont le correspondant a déménagé depuis n'est PAS silencieusement corrigé
# sans le demander explicitement (overwrite=True) — la donnée d'origine,
# saisie au moment du QSO, est présumée la bonne tant que rien ne prouve le
# contraire.
import threading as _threading

_bulk_lock = _threading.Lock()
_bulk_state = {'running': False, 'done': 0, 'total': 0, 'updated': 0,
               'errors': 0, 'started_at': None, 'finished_at': None}


def bulk_resolve_status():
    with _bulk_lock:
        return dict(_bulk_state)


def bulk_resolve_start(get_cfg, ids=None, overwrite=False):
    """Démarre la re-résolution en fond. Retourne (ok, message) — refus
    SYNCHRONE si un lot est déjà en cours (même raison que demarrer_suivi()
    dans logx_sat_track : l'opérateur doit voir tout de suite pourquoi rien
    ne se passe, pas aller le déduire d'un état à relire)."""
    with _bulk_lock:
        if _bulk_state['running']:
            return False, 'Une re-résolution est déjà en cours.'
        _bulk_state.update(running=True, done=0, total=0, updated=0,
                            errors=0, started_at=time.time(), finished_at=None)
    t = _threading.Thread(target=_bulk_resolve_run, args=(get_cfg, ids, overwrite),
                          daemon=True)
    t.start()
    return True, ''


def _bulk_needs(q, overwrite):
    return overwrite or not q.get('locator') or not q.get('state')


def _bulk_resolve_run(get_cfg, ids, overwrite):
    import logx_storage as storage
    ids_set = set(ids) if ids is not None else None
    with storage.log_lock:
        snapshot = list(storage.shared_log)
    targets = [q for q in snapshot
               if (ids_set is None or q.get('id') in ids_set) and _bulk_needs(q, overwrite)]
    calls = sorted({(q.get('call') or '').upper() for q in targets if q.get('call')})
    with _bulk_lock:
        _bulk_state['total'] = len(calls)

    cfg = get_cfg()
    results = {}
    for call in calls:
        results[call] = lookup(call, cfg, snapshot)
        with _bulk_lock:
            _bulk_state['done'] += 1

    updated = 0
    with storage.log_lock:
        for q in storage.shared_log:
            if ids_set is not None and q.get('id') not in ids_set:
                continue
            if not _bulk_needs(q, overwrite):
                continue
            r = results.get((q.get('call') or '').upper())
            if not r or not r.get('ok'):
                continue
            changed = False
            if r.get('grid') and (overwrite or not q.get('locator')):
                q['locator'] = r['grid']
                changed = True
            if r.get('state') and (overwrite or not q.get('state')):
                q['state'] = r['state']
                changed = True
            if changed:
                updated += 1
        if updated:
            storage.bump_log_version()
    if updated:
        storage.save_log_to_disk()

    with _bulk_lock:
        _bulk_state.update(
            running=False, updated=updated,
            errors=sum(1 for r in results.values() if not r.get('ok')),
            finished_at=time.time())
