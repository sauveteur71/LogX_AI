# -*- coding: utf-8 -*-
"""Serveur HTTP : endpoints REST, orchestration du refresh (do_refresh), état partagé navigateur/chat/config."""

import http.server
import urllib.request
import urllib.error
import html
import json
import os
import re
import sys
import datetime
import threading
import time
import socket

import logx_rules as rules
from logx_utils import (PORT, CURRENT_YEAR, locator_to_latlon, haversine, SSL_CTX,
                          OPENAI_COMPATIBLE_ENDPOINTS)
from logx_definitions import (CONTEST_DEFINITIONS, CONTEST_SCORING,
                                 CUSTOM_CONTEST_IDS, save_custom_contest,
                                 delete_custom_contest)
from logx_validate import validate_definition
from logx_rules_ai import analyze_rules
from logx_storage import (shared_log, log_lock, save_log_to_disk,
                                  save_json_atomic, calldb_lock, bump_log_version,
                                  qso_scope_id, active_scope_id, cfg_scope_id,
                                  stamp_qso_version, mark_qso_deleted, mark_hard_reset)
from logx_scoring import build_scoring_context, score_new_qso
from logx_prompts import build_system_prompt, build_terrain_context
from logx_rules import calc_all_dates, run_annual_update, refresh_external_contests, fetch_contest_rules
from logx_clusters import (SPOTS_CACHE, fetch_all_vhf_spots, fetch_cluster_f5len,
                      fetch_dxsummit_hf, fetch_f5len_hf, fetch_telnet_cluster, fetch_dxwatch_hf,
                      fetch_on4kst_data, fetch_on4kst_raw, fetch_log_edi, fetch_log_adif,
                      fetch_noaa_kindex, fetch_dxmaps_vhf, fetch_3830_scores,
                      lookup_hamqth, enrich_unknown_calls)

# ─── CACHE SPOTS CLUSTER ENVOYÉS PAR LE NAVIGATEUR ───────────────────────────
# Le navigateur accède à HTTPS/DXSummit, le serveur Python ne peut pas (bloqué).
# Le front-end push les spots via POST /data/spots → stockés ici.
browser_spots_cache = []      # liste de dicts {spotter, dx, freq, info, time}
browser_spots_lock  = threading.Lock()
browser_spots_ts    = 0       # timestamp dernier push
connected_peers = set()

# ─── ANALYSES IA CÔTÉ SERVEUR (survivent au changement de page) ──────────────
# Une analyse lancée depuis la CARTE IA tourne dans un thread serveur et son
# résultat est stocké ici : si l'opérateur change d'onglet (la nav recharge la
# page), il retrouve le résultat au retour via GET /agent/analyze/state?id=.
_agent_analyses = {}          # id -> {ts, status:'running|done|error', reply, error}
_agent_seq = 0
_agent_lock = threading.Lock()


def _call_openai_compatible(base_url, ai_model, default_model, api_key, system_prompt, messages, max_tokens=4096):
    """Appelle un fournisseur au format OpenAI Chat Completions, renvoie le TEXTE de la réponse."""
    msgs = ([{'role': 'system', 'content': system_prompt}] if system_prompt else []) + messages
    payload = {'model': ai_model or default_model, 'max_tokens': max_tokens, 'messages': msgs}
    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
        method='POST')
    with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as resp:
        d = json.loads(resp.read())
    return d.get('choices', [{}])[0].get('message', {}).get('content', '')


def call_llm(cfg, system_prompt, messages, model=None, max_tokens=4096):
    """Appelle le fournisseur IA configuré et retourne le TEXTE de la réponse.
    Même logique que /proxy/ai mais réutilisable côté serveur (analyse en fond).
    Lève une exception en cas d'échec."""
    provider = (cfg or {}).get('api_provider', 'anthropic')
    ai_model = model or (cfg or {}).get('ai_model', 'claude-sonnet-4-6')
    api_key = (cfg or {}).get('api_key', '') or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        raise RuntimeError('Clé API non configurée')

    if provider == 'anthropic':
        payload = {'model': ai_model or 'claude-sonnet-4-6',
                   'max_tokens': max_tokens, 'messages': messages}
        if system_prompt:
            payload['system'] = system_prompt
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages', data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json', 'x-api-key': api_key,
                     'anthropic-version': '2023-06-01'}, method='POST')
        with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as resp:
            data = json.loads(resp.read())
        return ''.join(b.get('text', '') for b in data.get('content', [])
                       if b.get('type') == 'text')

    if provider in OPENAI_COMPATIBLE_ENDPOINTS:
        base_url, default_model = OPENAI_COMPATIBLE_ENDPOINTS[provider]
        return _call_openai_compatible(base_url, ai_model, default_model, api_key,
                                       system_prompt, messages, max_tokens)

    if provider == 'gemini':
        model_id = ai_model or 'gemini-2.0-flash'
        contents = [{'role': 'model' if m['role'] == 'assistant' else 'user',
                     'parts': [{'text': m['content']}]} for m in messages]
        payload = {'contents': contents}
        if system_prompt:
            payload['systemInstruction'] = {'parts': [{'text': system_prompt}]}
        url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
               f'{model_id}:generateContent?key={api_key}')
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as resp:
            d = json.loads(resp.read())
        return (d.get('candidates', [{}])[0].get('content', {})
                .get('parts', [{}])[0].get('text', ''))

    raise RuntimeError(f'Fournisseur inconnu : {provider}')


def _parse_multipart_form(body, content_type):
    """Extrait champs texte + fichiers d'un corps multipart/form-data. PAS de
    cgi.FieldStorage (module supprimé en Python 3.13, déjà rencontré sur ce
    poste — voir mémoire) : parseur minimal suffisant pour un formulaire
    simple (upload de scan QSL — 1 fichier + qso_id), généré par le propre
    FormData/fetch du navigateur, pas par un client multipart exotique."""
    m = re.search(r'boundary=([^;]+)', content_type or '')
    if not m:
        return {}, {}
    boundary = ('--' + m.group(1).strip('"')).encode('utf-8')
    fields, files = {}, {}
    for chunk in body.split(boundary)[1:-1]:   # [0]=préambule, [-1]='--\r\n' final
        chunk = chunk[2:] if chunk[:2] == b'\r\n' else chunk
        if b'\r\n\r\n' not in chunk:
            continue
        head, data = chunk.split(b'\r\n\r\n', 1)
        if data.endswith(b'\r\n'):
            data = data[:-2]
        head_txt = head.decode('utf-8', 'replace')
        name_m = re.search(r'name="([^"]*)"', head_txt)
        if not name_m:
            continue
        name = name_m.group(1)
        fn_m = re.search(r'filename="([^"]*)"', head_txt)
        if fn_m and fn_m.group(1):
            files[name] = {'filename': fn_m.group(1), 'data': data}
        else:
            fields[name] = data.decode('utf-8', 'replace')
    return fields, files

# ─── CONFIGURATION COURANTE (mise à jour par /config/save) ───────────────────
# Persistée dans .server_config.json (gitignoré : contient les identifiants
# ON4KST) : après un redémarrage du serveur, le coach, la statusbar et la
# page mobile connaissent le concours actif sans attendre qu'un navigateur
# recharge une page.
SERVER_CONFIG_FILE = '.server_config.json'

def _load_saved_config():
    try:
        with open(SERVER_CONFIG_FILE, encoding='utf-8') as f:
            cfg = json.load(f)
        if isinstance(cfg, dict) and cfg:
            print(f"[CFG] Config restauree ({cfg.get('callsign','?')} / {cfg.get('contest','?')})")
            return cfg
    except Exception:
        pass
    return {}

current_config = _load_saved_config()
config_lock = threading.Lock()

# ─── CACHE DXMAPS POUR LE COACH (TTL 10 min) ─────────────────────────────────
_coach_dxmaps_cache = None
_coach_dxmaps_ts = 0

# ─── TOKEN D'AUTHENTIFICATION PARTAGÉ ────────────────────────────────────────
# Priorité : config.json server.auth_token > fichier .auth_token > généré et
# persisté dans .auth_token (stable entre redémarrages, jamais suivi par git).
AUTH_TOKEN_FILE = '.auth_token'

def _load_auth_token():
    try:
        with open('config.json', encoding='utf-8') as f:
            tok = (json.load(f).get('server', {}) or {}).get('auth_token', '')
        if tok:
            return str(tok)
    except Exception:
        pass
    try:
        with open(AUTH_TOKEN_FILE, encoding='utf-8') as f:
            tok = f.read().strip()
        if tok:
            return tok
    except Exception:
        pass
    import secrets as _secrets
    tok = _secrets.token_hex(16)
    try:
        with open(AUTH_TOKEN_FILE, 'w', encoding='utf-8') as f:
            f.write(tok)
    except Exception:
        pass
    return tok

AUTH_TOKEN = _load_auth_token()

def _rotate_auth_token():
    """Génère un nouveau jeton d'écriture partagé et le persiste dans
    AUTH_TOKEN_FILE (même fichier que _load_auth_token, pour survivre à un
    redémarrage). Appelée quand le mot de passe d'accès est activé ou modifié
    (voir _set_access_password) : un cookie rc_token distribué AVANT cette
    activation/modification (LAN de confiance, invité déjà reparti, port
    forwardé par erreur...) n'a plus aucune raison de rester valide après —
    sans rotation, définir un mot de passe ne révoquerait aucune session déjà
    ouverte. NB : si server.auth_token est fixé dans config.json, ce fichier
    reprendra la main au prochain redémarrage (même priorité que
    _load_auth_token) — cette rotation ne vaut que pour la session serveur en
    cours, best-effort, pas une garantie absolue face à ce cas de config
    avancée."""
    global AUTH_TOKEN
    import secrets as _secrets
    AUTH_TOKEN = _secrets.token_hex(16)
    try:
        with open(AUTH_TOKEN_FILE, 'w', encoding='utf-8') as f:
            f.write(AUTH_TOKEN)
    except Exception:
        pass
    return AUTH_TOKEN

# ─── MOT DE PASSE D'ACCÈS OPTIONNEL (avant remise du jeton d'écriture) ───────
# Par défaut (fichier absent), comportement INCHANGÉ : rc_token est distribué
# automatiquement à toute page HTML servie (voir do_GET) — adapté à un LAN de
# confiance. Si un mot de passe est défini depuis CONFIG (POST
# /auth/set_password), cette distribution automatique s'arrête : seule
# /auth/login peut désormais poser le cookie, après vérification du mot de
# passe en temps constant (même logique que AUTH_TOKEN, voir
# _client_authorized). Le mot de passe n'est JAMAIS conservé en clair :
# PBKDF2-HMAC-SHA256 + sel aléatoire (un simple sha256 sans sel serait
# cassable par table arc-en-ciel). Pas de TLS ici (volontairement hors scope,
# voir le commentaire de _handle_auth_login_post) : le mot de passe circule en
# clair sur le réseau local, comme les autres identifiants déjà envoyés par
# /config/save (ON4KST, QRZ...) — cette protection couvre un accès non voulu,
# pas une écoute réseau active.
ACCESS_PASSWORD_FILE = '.access_password'
_access_pw_lock = threading.Lock()
_PBKDF2_ITERATIONS = 200_000

def _hash_password(password, salt_hex=None):
    import hashlib
    import secrets as _secrets
    salt_hex = salt_hex or _secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                                  bytes.fromhex(salt_hex), _PBKDF2_ITERATIONS)
    return salt_hex, digest.hex()

def _load_access_password():
    """(sel, hash) actuels, ou None si aucun mot de passe n'est configuré
    (repli explicite : fichier absent/corrompu = protection désactivée, comme
    le comportement par défaut)."""
    try:
        with open(ACCESS_PASSWORD_FILE, encoding='utf-8') as f:
            data = json.load(f)
        salt_hex, h = data.get('salt', ''), data.get('hash', '')
        if salt_hex and h:
            return salt_hex, h
    except Exception:
        pass
    return None

def _access_password_enabled():
    with _access_pw_lock:
        return _load_access_password() is not None

def _verify_access_password(password):
    with _access_pw_lock:
        stored = _load_access_password()
    if not stored or not password:
        return False
    salt_hex, expected_hash = stored
    _, candidate_hash = _hash_password(password, salt_hex)
    import secrets as _secrets
    return _secrets.compare_digest(candidate_hash, expected_hash)

def _set_access_password(password):
    salt_hex, h = _hash_password(password)
    with _access_pw_lock:
        save_json_atomic(ACCESS_PASSWORD_FILE, {'salt': salt_hex, 'hash': h})
    # Révoque les cookies rc_token déjà distribués avant cette
    # activation/modification (voir _rotate_auth_token) — sinon un accès
    # obtenu avant la mise en place du mot de passe resterait valide
    # indéfiniment après coup.
    _rotate_auth_token()

# ─── ANTI-BRUTEFORCE SUR /auth/login (voir _handle_auth_login_post) ─────────
# Chaque tentative déclenche normalement un PBKDF2-HMAC-SHA256 à 200000
# itérations (~83 ms) : sans limite, un client du LAN peut le rejouer en
# boucle serrée (ThreadingHTTPServer crée un thread OS par connexion, sans
# plafond) et saturer le CPU du serveur. Fenêtre glissante par IP, en mémoire
# seulement (best-effort : redémarrer le serveur remet le compteur à zéro,
# acceptable pour ce risque).
_LOGIN_ATTEMPT_LIMIT = 5
_LOGIN_ATTEMPT_WINDOW = 60.0  # secondes
_login_attempts_lock = threading.Lock()
_login_attempts = {}  # ip -> [timestamps des échecs récents]

def _login_rate_limited(ip):
    """True si `ip` a déjà atteint la limite d'échecs récents — purge et
    lecture dans le MÊME verrou (jamais relâché entre les deux) pour éviter
    qu'une rafale concurrente ne contourne la limite."""
    now = time.time()
    with _login_attempts_lock:
        attempts = [t for t in _login_attempts.get(ip, ()) if now - t < _LOGIN_ATTEMPT_WINDOW]
        _login_attempts[ip] = attempts
        return len(attempts) >= _LOGIN_ATTEMPT_LIMIT

def _record_login_failure(ip):
    now = time.time()
    with _login_attempts_lock:
        attempts = [t for t in _login_attempts.get(ip, ()) if now - t < _LOGIN_ATTEMPT_WINDOW]
        attempts.append(now)
        _login_attempts[ip] = attempts

def _reset_login_attempts(ip):
    with _login_attempts_lock:
        _login_attempts.pop(ip, None)

def _clear_access_password():
    with _access_pw_lock:
        try:
            os.remove(ACCESS_PASSWORD_FILE)
        except FileNotFoundError:
            pass

# ─── PORTÉE CONCOURS (voir logx_storage.qso_scope_id/active_scope_id/cfg_scope_id) ─
def _scope_filtered(qsos, cfg):
    """Sous-ensemble de `qsos` appartenant à la portée active de `cfg` (voir
    logx_storage.cfg_scope_id) — renvoie une copie de `qsos` inchangée si
    aucune portée n'est active (mode simple, ou aucun concours sélectionné)."""
    scope_id = cfg_scope_id(cfg)
    if not scope_id:
        return list(qsos or [])
    return [q for q in (qsos or []) if qso_scope_id(q) == scope_id]


# ─── SYNCHRO DIFFÉRENTIELLE DE /log/list (voir logx_storage : stamp_qso_version,
# mark_qso_deleted, mark_hard_reset, SERVER_BOOT_ID) ──────────────────────────
def _valid_since(since_raw, boot_raw, current_v):
    """Version à utiliser pour un delta /log/list?since=, ou None si absente/
    invalide — repli explicite sur la liste complète dans ce cas (voir /log/list).
    Invalide si : pas un entier, hors de [hard_reset_version, current_v], ou
    jeton de démarrage serveur absent/différent de SERVER_BOOT_ID (un
    redémarrage remet log_version à zéro : un ancien "since" pourrait sinon
    retomber par coincidence dans la nouvelle plage de versions et faire
    croire à tort qu'aucun QSO plus ancien n'a changé)."""
    # Import local du module (pas juste des noms) : hard_reset_version est
    # réassigné en place par mark_hard_reset(), un import direct du nom aurait
    # figé sa valeur au chargement de logx_http.
    import logx_storage as storage
    if not since_raw or not since_raw.isdigit():
        return None
    since = int(since_raw)
    if since < 0 or since > current_v:
        return None
    if since < storage.hard_reset_version:
        return None
    if not boot_raw or boot_raw != storage.SERVER_BOOT_ID:
        return None
    return since


# ─── INSERTION D'UN QSO (dédup + persistance) ────────────────────────────────
def add_qso_to_log(qso, force=False):
    """Ajoute un QSO au log partagé avec détection de doublon. Retourne
    (ok, info). Chemin commun à /log/add et au pont WSJT-X."""
    import time as _t
    qso['server_time'] = _t.time()
    now_utc = datetime.datetime.utcnow()
    qso.setdefault('date', now_utc.strftime('%Y%m%d'))
    qso.setdefault('time', now_utc.strftime('%H:%M'))
    key = (str(qso.get('call', '')).upper().strip(),
           str(qso.get('band', '')), str(qso.get('mode', '')).upper())
    # Portée du NOUVEAU QSO (contest+année, voir logx_storage.active_scope_id) —
    # dérivée de ses propres champs contest+date plutôt que du contest_id brut :
    # sans l'année, retravailler la même station/bande sur la même édition d'un
    # concours ANNUEL récurrent une année différente était refusé comme doublon.
    scope_id = qso_scope_id(qso)
    with config_lock:
        simple_mode = current_config.get('usage_mode') == 'simple'
    dup = None
    # LOGBOOK SIMPLE : recontacter la même station sur la même bande au fil
    # des années est normal (pas de règle "1 QSO/station/bande" hors concours)
    # — le blocage "doublon" n'a de sens que pendant un concours actif.
    if not simple_mode:
        with log_lock:
            dup = next((q for q in shared_log
                        if (str(q.get('call', '')).upper().strip(),
                            str(q.get('band', '')),
                            str(q.get('mode', '')).upper()) == key
                        and qso_scope_id(q) == scope_id), None)
    if dup and not force:
        return False, {'duplicate': True, 'existing': {
            'id': dup.get('id'), 'date': dup.get('date'),
            'time': dup.get('time'), 'operator': dup.get('operator', '')}}
    qso.pop('force', None)
    qso.setdefault('id', int(_t.time() * 1000))
    # Recalcule les points côté serveur (moteur unique logx_scoring, celui déjà
    # utilisé pour classer les spots) — jamais confiance dans la valeur envoyée
    # par le client : la page mobile assume un barème "points = distance" en
    # dur, WSJT-X/le pont ADIF réseau n'envoient même pas de points du tout, et
    # un client PC pourrait être une version ancienne/désynchronisée du barème.
    # Borné : la seule brique de scoring qui touche le réseau (WWA, roster
    # hamaward.cloud — voir logx_wwa.py) a un cache 6h et ne fetch qu'à froid ;
    # au cas où elle tombe sur un cache froid ET un réseau lent, on ne bloque
    # JAMAIS le thread HTTP au-delà de quelques secondes (voir logx_utils.
    # fetch_url pour le même principe) — en cas de dépassement/erreur, la
    # valeur envoyée par le client est conservée plutôt que de faire échouer
    # l'enregistrement du QSO.
    try:
        from concurrent.futures import ThreadPoolExecutor
        _score_ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix='score')
        qso['points'] = _score_ex.submit(score_new_qso, qso).result(timeout=3)
    except Exception as e:
        print(f"[SCORING] Recalcul points abandonné ({type(e).__name__}: {e}) "
              f"— valeur envoyée par le client conservée")
    # bump_log_version()/stamp_qso_version() DANS le même verrou que l'ajout :
    # /log/list capture current_v+log_copy sous SON PROPRE with log_lock (lecteur
    # concurrent, ThreadingHTTPServer). Si le stamp arrivait après un relâchement
    # du verrou, ce lecteur pourrait s'intercaler entre le bump (version déjà
    # incrémentée) et le stamp (encore absent) : il verrait ce QSO sans '_v' à
    # jour (défaut 0), donc exclu à tort d'un delta calculé contre une version
    # déjà avancée — le client adopterait ce curseur et ne reverrait plus JAMAIS
    # ce QSO. save_log_to_disk() reste HORS verrou (elle reprend log_lock elle-
    # même pour sa copie ; log_lock n'est pas réentrant, l'appeler ici deadlockerait).
    with log_lock:
        shared_log.append(qso)
        bump_log_version()
        stamp_qso_version(qso)   # voir /log/list?since= (synchro différentielle)
    save_log_to_disk()
    # Mode expédition : pousse le QSO vers le flux Club Log Live (fire-and-forget)
    try:
        with config_lock:
            cfg_now = dict(current_config)
        if str(cfg_now.get('clublog_live', '')) in ('1', 'true', 'True', 'on'):
            import logx_qsl as qsl
            threading.Thread(target=lambda: qsl.realtime_push(cfg_now, dict(qso)),
                             daemon=True).start()
    except Exception:
        pass
    # QRZ Logbook : insertion temps réel (ACTION=INSERT), fire-and-forget —
    # même schéma d'activation que Club Log Live ci-dessus (bouton dédié,
    # pas seulement la présence de la clé — cf. logx_qrz_push.qrz_logbook_settings).
    try:
        with config_lock:
            cfg_now3 = dict(current_config)
        import logx_qrz_push as qrz_push
        if qrz_push.qrz_logbook_settings(cfg_now3)['push_enabled']:
            threading.Thread(target=lambda: qrz_push.push_qso(cfg_now3, dict(qso)),
                             daemon=True).start()
    except Exception:
        pass
    # Réseau ADIF générique : rediffuse le QSO en UDP <contactinfo> pour un
    # N1MM/DXLog voisin (mode send/both), fire-and-forget.
    try:
        with config_lock:
            cfg_now2 = dict(current_config)
        import logx_adifnet as adifnet
        if adifnet.adifnet_settings(cfg_now2)['send']:
            threading.Thread(target=lambda: adifnet.broadcast_qso(dict(qso), cfg_now2),
                             daemon=True).start()
    except Exception:
        pass
    # Publication MQTT optionnelle (topics logx/qso + logx/score) — désactivée
    # par défaut, dégradée proprement si paho-mqtt n'est pas installé (voir
    # logx_mqtt.py). Même schéma fire-and-forget que Club Log Live/QRZ
    # Logbook/réseau ADIF ci-dessus : le thread HTTP ne doit jamais attendre
    # le broker. Le score publié est celui de la PORTÉE du QSO (contest+année,
    # comme le reste de la dédup) — calcul en mémoire, aucun réseau.
    try:
        with config_lock:
            cfg_now4 = dict(current_config)
        import logx_mqtt as mqtt_bridge
        if mqtt_bridge.mqtt_settings(cfg_now4)['enabled']:
            scope_now = qso_scope_id(qso)
            with log_lock:
                score_total = sum(q.get('points', 0) or 0 for q in shared_log
                                  if qso_scope_id(q) == scope_now)
            def _publish_mqtt(cfg=cfg_now4, qso_copy=dict(qso), score=score_total):
                # Le concours publié est celui DU QSO (qso['contest'], la
                # même portée que score_total ci-dessus), pas celui de
                # current_config — les deux divergent en pratique pour un
                # QSO auto-loggé WSJT-X pendant un changement de concours
                # entre-temps, ou hors mode concours (contest='').
                mqtt_bridge.publish_qso(cfg, qso_copy)
                mqtt_bridge.publish_score(cfg, score, qso_copy.get('contest', ''))
            threading.Thread(target=_publish_mqtt, daemon=True).start()
    except Exception:
        pass
    # Enrichit l'historique d'indicatifs à chaud (Super Check Partial)
    try:
        import logx_callhistory as callhistory
        callhistory.update_from_qso(qso)
    except Exception:
        pass
    return True, {'total': len(shared_log)}


# ─── SPOTS DEPUIS LES CACHES (sans re-fetch réseau) ──────────────────────────
def _spots_from_caches():
    """{label: spots} depuis SPOTS_CACHE + spots poussés par le navigateur —
    consommé par /data/spots_ranked et le comptage de mults du coach."""
    spots_by_band = {}
    for key, label in (('144', '144 MHz'), ('432', '432 MHz'),
                       ('50', '50 MHz'), ('HF', 'HF')):
        cached = SPOTS_CACHE.get(key) or []
        if cached:
            spots_by_band[label] = list(cached)
    with browser_spots_lock:
        if browser_spots_cache and time.time() - browser_spots_ts < 600:
            merged = spots_by_band.setdefault('HF', [])
            seen = {(sp.get('dx', ''), str(sp.get('freq', '')))
                    for sp in merged if isinstance(sp, dict)}
            for sp in browser_spots_cache:
                k = (sp.get('dx', ''), str(sp.get('freq', '')))
                if k not in seen:
                    merged.append(sp)
                    seen.add(k)
    return spots_by_band

# ─── CHAT MULTI-OPÉRATEUR ─────────────────────────────────────────────────────
chat_messages = []     # liste {id, op, call, time, text}
chat_lock = threading.Lock()
chat_seq = 0           # identifiant auto-incrémenté

# ─── VUE PARTNER (saisie en direct, lecture seule) ───────────────────────────
# État ÉPHÉMÈRE (jamais écrit sur disque, contrairement à chat_messages) : ce
# qu'un opérateur est en train de taper dans le champ indicatif, pour qu'un
# second poste (radioclub/expédition) le voie en quasi temps réel. Une entrée
# par opérateur (écrasée à chaque frappe) ; périmée après TYPING_STALE_S sans
# mise à jour (poste éteint/onglet fermé sans dernier POST vide).
typing_state = {}      # op -> {op, label, band, mode, text, ts}
typing_lock = threading.Lock()
TYPING_STALE_S = 8


def _active_typing():
    """Saisies en direct encore fraîches, pour GET /chat/list."""
    now = time.time()
    with typing_lock:
        return [dict(v) for v in typing_state.values()
                if now - v.get('ts', 0) <= TYPING_STALE_S]

# ─── REFRESH DONNÉES ─────────────────────────────────────────────────────────
# Chaque source réseau est isolée dans sa fonction et lancée EN PARALLÈLE via
# un ThreadPoolExecutor : une source lente ou en panne est abandonnée au
# timeout global au lieu de bloquer tout le refresh.
REFRESH_TIMEOUT_S = 25

def _fetch_logs_src(cfg, log_sw, no_digi):
    logs = {}
    if log_sw == 'net-test-thf':
        url144 = cfg.get('log_url_144', '')
        url432 = cfg.get('log_url_432', '')
        if url144:
            logs['144 MHz'] = fetch_log_edi(url144, filter_digital=no_digi)
        if url432:
            logs['432 MHz'] = fetch_log_edi(url432, filter_digital=no_digi)
    elif log_sw in ('n1mm', 'log4om', 'hamrs'):
        log_url = cfg.get('log_url_144', '')
        if log_url:
            logs['Principal'] = fetch_log_adif(log_url, filter_digital=no_digi)
    if not logs:
        logs['Log'] = {'qsos': [], 'score': 0, 'total_qso': 0, 'error': 'URL log non configurée'}
    return logs

def _fetch_spots_vhf_src(band, no_digi, toggles):
    s = fetch_all_vhf_spots(band, filter_digital=no_digi, toggles=toggles)
    SPOTS_CACHE[str(band)] = s
    print(f"[DATA] {band} MHz: {len(s)} spots (multi-cluster)")
    return s

def _fetch_spots_50_src(no_digi, toggles):
    if not toggles.get('src_f5len', True):
        SPOTS_CACHE['50'] = []
        return []
    s = fetch_cluster_f5len(50, filter_digital=no_digi)
    SPOTS_CACHE['50'] = s
    print(f"[DATA] 50 MHz: {len(s)} spots")
    return s

def _fetch_spots_hf_src(callsign, no_digi, toggles):
    """5 sources HF fusionnées et dédupliquées (DXSummit, F5LEN, DXWatch, Telnet,
    navigateur) — chacune désactivable individuellement depuis CONFIG
    (toggles src_dxsummit/src_f5len/src_dxwatch/src_telnet). Toutes actives par
    défaut (True) si le toggle est absent d'une config existante, pour ne rien
    changer au comportement des utilisateurs qui n'y touchent jamais."""
    on = lambda key: toggles.get(key, True)
    s_summit = fetch_dxsummit_hf(filter_digital=no_digi) if on('src_dxsummit') else []
    s_f5len = fetch_f5len_hf(filter_digital=no_digi) if on('src_f5len') else []
    s_dxwatch = fetch_dxwatch_hf(filter_digital=no_digi) if on('src_dxwatch') else []
    s_telnet = fetch_telnet_cluster(callsign=callsign or 'F4GLD', filter_digital=no_digi) if on('src_telnet') else []
    s_browser = []
    with browser_spots_lock:
        age = time.time() - browser_spots_ts
        if browser_spots_cache and age < 600:  # valides 10 min
            s_browser = list(browser_spots_cache)
            print(f"[BROWSER-SPOTS] {len(s_browser)} spots (age {int(age)}s)")
        elif browser_spots_cache:
            print(f"[BROWSER-SPOTS] cache perime ({int(age)}s)")
    all_hf = s_summit + s_f5len + s_dxwatch + s_telnet + s_browser
    seen_hf = set()
    s = []
    for sp in all_hf:
        dx = sp.get('dx','') if isinstance(sp, dict) else (sp[0] if sp else '')
        freq = str(sp.get('freq','')) if isinstance(sp, dict) else (sp[1] if len(sp)>1 else '')
        key = f"{dx}|{freq}"
        if key not in seen_hf:
            seen_hf.add(key)
            s.append(sp)
    print(f"[DATA] HF: {len(s)} spots total (DXSummit:{len(s_summit)} F5LEN:{len(s_f5len)} "
          f"DXWatch:{len(s_dxwatch)} Telnet:{len(s_telnet)} Browser:{len(s_browser)})")
    SPOTS_CACHE['HF'] = s   # consommé par /data/spots_ranked sans re-fetch
    return s

def _fetch_on4kst_src(cfg):
    try:
        data = fetch_on4kst_data(cfg['on4kst_callsign'], cfg['on4kst_password'])
        if data.get('error'):
            print(f"[ON4KST] Erreur : {data['error']}")
            return None
        return data
    except Exception as e:
        print(f"[ON4KST] Exception : {e}")
        return None

def do_refresh(cfg):
    from concurrent.futures import ThreadPoolExecutor

    toggles = cfg.get('toggles', {})
    no_digi = toggles.get('flag_no_digi', False)
    contest = cfg.get('contest', 'CUSTOM')
    log_sw  = cfg.get('log_software', 'manual')
    callsign = cfg.get('callsign_contest', cfg.get('callsign', ''))

    print(f"[DATA] Refresh — {callsign} | {cfg.get('locator','?')} | {contest}")

    # ── Bandes du concours ACTIF depuis sa définition — plus jamais de liste
    # codée en dur (l'ancienne HF_CONTESTS ignorait EU_HF_CHAMP, les WAEDC et
    # tous les concours des Phases 3/4 : cluster vide le jour J).
    HF_BAND_SET = {'1.8', '3.5', '7', '10', '14', '18', '21', '24', '28'}
    cdef_bands = [str(b) for b in CONTEST_DEFINITIONS.get(contest, {}).get('bands', [])]
    has_hf_bands = any(b in HF_BAND_SET for b in cdef_bands)
    has_vhf_bands = any(b not in HF_BAND_SET for b in cdef_bands)
    # Concours purement HF : ne pas fetcher les spots VHF même si un toggle
    # 2m traîne dans la config (2m est secondaire en HF contest)
    is_hf_contest = has_hf_bands and not has_vhf_bands
    is_vhf = ('144' in cdef_bands or '432' in cdef_bands
              or ((toggles.get('band_2m', False) or toggles.get('band_70cm', False)
                   or '144' in str(contest)) and not is_hf_contest))
    hf_bands = ['band_20m','band_40m','band_80m','band_160m','band_10m','band_15m']

    # ── Lancement parallèle de toutes les sources réseau ─────────────────────
    ex = ThreadPoolExecutor(max_workers=10, thread_name_prefix='refresh')
    deadline = time.time() + REFRESH_TIMEOUT_S
    futs = {'logs': ex.submit(_fetch_logs_src, cfg, log_sw, no_digi),
            'noaa': ex.submit(fetch_noaa_kindex),
            'rules': ex.submit(fetch_contest_rules, contest),
            '3830': ex.submit(fetch_3830_scores, contest, callsign)}
    if '144' in cdef_bands or (toggles.get('band_2m', False) and not is_hf_contest) \
            or ('144' in str(contest) and not is_hf_contest):
        futs['spots_144'] = ex.submit(_fetch_spots_vhf_src, 144, no_digi, toggles)
    if '432' in cdef_bands or (toggles.get('band_70cm', False) and not is_hf_contest) \
            or ('432' in str(contest) and not is_hf_contest):
        futs['spots_432'] = ex.submit(_fetch_spots_vhf_src, 432, no_digi, toggles)
    if '50' in cdef_bands or toggles.get('band_6m', False):
        futs['spots_50'] = ex.submit(_fetch_spots_50_src, no_digi, toggles)
    if has_hf_bands or any(toggles.get(b, False) for b in hf_bands):
        futs['spots_hf'] = ex.submit(_fetch_spots_hf_src, callsign, no_digi, toggles)
    if is_vhf:
        futs['dxmaps'] = ex.submit(fetch_dxmaps_vhf)
    if (is_vhf and toggles.get('src_on4kst', False)
            and cfg.get('on4kst_callsign') and cfg.get('on4kst_password')):
        futs['on4kst'] = ex.submit(_fetch_on4kst_src, cfg)

    def take(key, default=None):
        """Résultat d'une source, borné par le deadline global — jamais bloquant."""
        fut = futs.get(key)
        if fut is None:
            return default
        try:
            return fut.result(timeout=max(0.5, deadline - time.time()))
        except Exception as e:
            print(f"[REFRESH] Source '{key}' abandonnee ({type(e).__name__}: {e})")
            return default

    # ── 1. Logs (HamQTH en dépend → lancé dès qu'ils arrivent) ───────────────
    logs = take('logs') or {'Log': {'qsos': [], 'score': 0, 'total_qso': 0,
                                    'error': 'URL log non configurée'}}
    calldb_path = os.path.join(os.getcwd(), 'calldb.json')
    all_log_calls = {}
    for log_data in logs.values():
        for q in log_data.get('qsos', []):
            base = q.get('call','').split('/')[0]
            if base:
                all_log_calls[base] = {'locator': q.get('locator','')}
    futs['hamqth'] = ex.submit(enrich_unknown_calls, all_log_calls, calldb_path)

    # ── 2. Spots par bande ────────────────────────────────────────────────────
    spots_by_band = {}
    for key, label in (('spots_144','144 MHz'), ('spots_432','432 MHz'),
                       ('spots_50','50 MHz'), ('spots_hf','HF')):
        if key in futs:
            spots_by_band[label] = take(key, []) or []

    # ── 3-7. Autres sources ───────────────────────────────────────────────────
    noaa = take('noaa')
    if noaa:
        print(f"[NOAA] {noaa['summary']}")
    dxmaps = take('dxmaps')
    if dxmaps:
        print(f"[DXMAPS] {dxmaps['summary']}")
    on4kst = take('on4kst')
    rules_info = take('rules')
    if rules_info and rules_info.get('ok'):
        print(f"[RULES] Reglement {contest} disponible")
    scores_3830 = take('3830')
    if scores_3830:
        print(f"[3830] {scores_3830['summary']}")
    hamqth_enriched = take('hamqth', {}) or {}
    # Les threads retardataires finiront en arrière-plan sans bloquer la réponse
    ex.shutdown(wait=False, cancel_futures=True)

    # ── Filtre préfixe spots (si configuré) ──────────────────────────────────
    prefix_filter_raw = cfg.get('spot_prefix_filter', '')
    prefix_filter = [p.strip().upper() for p in prefix_filter_raw.split(',') if p.strip()] if prefix_filter_raw else []
    if prefix_filter:
        def _match_prefix(call):
            call = call.upper()
            return any(call.startswith(p) for p in prefix_filter)
        filtered_total = 0
        for band_key in list(spots_by_band.keys()):
            before = len(spots_by_band[band_key])
            spots_by_band[band_key] = [
                sp for sp in spots_by_band[band_key]
                if _match_prefix(sp.get('dx','') if isinstance(sp, dict) else (sp[0] if sp else ''))
            ]
            filtered_total += before - len(spots_by_band[band_key])
        if filtered_total:
            print(f"[PREFIX-FILTER] {filtered_total} spots supprimes (filtre: {','.join(prefix_filter)})")

    # ── Score total ───────────────────────────────────────────────────────────
    total_score = sum(l.get('score', 0) for l in logs.values())
    total_qso   = sum(l.get('total_qso', 0) for l in logs.values())

    # ── Contexte enrichi pour l'IA ───────────────────────────────────────────
    context = build_terrain_context(logs, spots_by_band, cfg)

    # Ajouter les données internet au contexte
    extra = ['\n=== DONNÉES INTERNET EN TEMPS RÉEL ===']

    if noaa:
        k = noaa['k_index']
        extra.append(f"\n📡 GÉOMAGNÉTISME NOAA : {noaa['summary']}")
        if noaa['aurora_possible']:
            extra.append("  ⚡ ATTENTION : Aurore possible → perturbations sur 144 MHz, propagation aurora envisageable !")
        elif k < 2:
            extra.append("  ✅ Conditions calmes — propagation normale attendue")

    if dxmaps:
        extra.append(f"\n🗺️ DXMAPS VHF : {dxmaps['summary']}")
        if dxmaps.get('es_active'):
            extra.append("  🌟 SPORADIC-E CONFIRMÉ SUR DXMAPS — contacts longue distance possibles !")
        if dxmaps.get('tropo_active'):
            extra.append("  🌊 TROPO CONFIRMÉ SUR DXMAPS — favoriser les contacts côtiers !")

    if rules_info and rules_info.get('ok'):
        extra.append(f"\n📋 RÈGLEMENT {contest} (extrait) :")
        extra.append(f"  {rules_info['text_extract'][:500]}...")
        extra.append(f"  → Règlement complet : {rules_info['url']}")

    if scores_3830:
        extra.append(f"\n🏆 CLASSEMENT 3830SCORES — {scores_3830['contest']} :")
        for row in scores_3830['top_scores'][:5]:
            extra.append(f"  {' | '.join(str(c) for c in row)}")
        if scores_3830['our_rank']:
            extra.append(f"  → Notre position : #{scores_3830['our_rank']}")

    if hamqth_enriched:
        extra.append(f"\n📖 HAMQTH — {len(hamqth_enriched)} indicatifs enrichis :")
        for call, data in hamqth_enriched.items():
            extra.append(f"  {call}: {data.get('locator','')} / {data.get('country','')} ({data.get('continent','')})")

    if on4kst and on4kst.get('users'):
        my_ll = locator_to_latlon(cfg.get('locator', 'JN00AA'))
        users_sorted = []
        for u in on4kst['users']:
            pos = locator_to_latlon(u['locator'])
            dist = haversine(my_ll[0], my_ll[1], pos[0], pos[1]) if (my_ll[0] and pos[0]) else 0
            users_sorted.append((dist, u))
        users_sorted.sort(key=lambda x: -x[0])
        nb_present = sum(1 for _, u in users_sorted if u['present'])
        extra.append(f"\n💬 ON4KST CHAT 144/432 — {len(users_sorted)} stations connectées ({nb_present} au clavier) :")
        extra.append("Ces stations sont ACTIVES MAINTENANT et joignables pour un sked via le chat.")
        for dist, u in users_sorted[:25]:
            flag = '' if u['present'] else ' (absent clavier)'
            extra.append(f"  {u['call']:12} {u['locator']} ~{dist:4} km{flag}  {u['name']}")
        if on4kst.get('messages'):
            extra.append(f"\n💬 DERNIERS MESSAGES DU CHAT ({len(on4kst['messages'])}) :")
            my_base = callsign.split('/')[0].upper()
            my_name_hits = []
            for msg in on4kst['messages'][:15]:
                extra.append(f"  {msg['time']} {msg['call']}: {msg['text']}")
                if my_base and my_base in msg['text'].upper():
                    my_name_hits.append({'time': msg['time'], 'call': msg['call'],
                                         'text': msg['text']})
            on4kst_mentions = my_name_hits
            if my_name_hits:
                extra.append(f"\n⚡ ATTENTION : {len(my_name_hits)} message(s) du chat mentionnent {my_base} — quelqu'un cherche peut-être un sked avec nous !")

    extra.append('\n=== FIN DONNÉES INTERNET ===')
    on4kst_mentions = locals().get('on4kst_mentions', [])
    context += '\n'.join(extra)

    # ── Ouvertures par région depuis le QTH (l'agent peut estimer « mes chances
    #    vers l'Europe ? » où que soit la station) ──────────────────────────────
    try:
        import logx_paths as paths
        my_ll_op = locator_to_latlon(cfg.get('locator', '') or 'JN15XC')
        if my_ll_op[0] is not None:
            solar_op = {'solar': {'k_index': (noaa or {}).get('k_index', 2)}}
            try:
                from logx_clusters import get_solar_cached, get_muf_cached
                sd = get_solar_cached() or {}
                solar_op = {'solar': sd, 'muf': get_muf_cached(my_ll_op[0], my_ll_op[1])}
            except Exception:
                pass
            ob = paths.context_block(my_ll_op[0], my_ll_op[1], solar=solar_op)
            if ob:
                context += '\n\n=== PROPAGATION PAR RÉGION ===\n' + ob
    except Exception:
        pass

    # ── 8. Classement stations par valeur réelle ──────────────────────────────
    scoring_context = build_scoring_context(logs, spots_by_band, cfg, noaa, dxmaps,
                                            on4kst['users'] if on4kst else None)
    context += scoring_context

    system_prompt = build_system_prompt(cfg)

    return {
        'logs': logs,
        'spots': {k: v[:15] for k, v in spots_by_band.items()},
        'context': context,
        'system_prompt': system_prompt,
        'score_total': total_score,
        'qso_total': total_qso,
        'contest': contest,
        'callsign': callsign,
        'locator': cfg.get('locator', ''),
        'noaa': noaa,
        'dxmaps': dxmaps,
        'scores_3830': scores_3830,
        'rules_loaded': bool(rules_info and rules_info.get('ok')),
        'hamqth_enriched': len(hamqth_enriched),
        'on4kst_users': len(on4kst['users']) if on4kst else 0,
        'on4kst_mentions': on4kst_mentions,
    }

# ─── ÉTAT MATÉRIEL (rig/amp/wsjtx/rotor) ─────────────────────────────────────
# Extrait des anciens corps de handler pour être appelé à la fois par les
# endpoints individuels (/rig/state, /amp/state, /wsjtx/state, /rotor/state —
# gardés pour les autres pages) et par /hardware/state (fusion des 4 pour le
# logbook, qui les pollait séparément à cadence rapide).

def _rig_state_dict(cfg_snap):
    """Enveloppe _rig_state_dict_impl() pour y greffer la publication MQTT
    optionnelle (topic logx/rig/freq) SANS toucher aux 4 points de retour de
    l'implémentation (native/TCI/flrig/rigctld) — un seul endroit à modifier
    plutôt que dupliquer le hook dans chaque branche."""
    state = _rig_state_dict_impl(cfg_snap)
    try:
        if state.get('enabled') and state.get('ok') and state.get('freq_khz'):
            import logx_mqtt as mqtt_bridge
            if (mqtt_bridge.mqtt_settings(cfg_snap)['enabled']
                    and mqtt_bridge.freq_changed(state['freq_khz'])):
                threading.Thread(target=lambda: mqtt_bridge.publish_rig_freq(
                    cfg_snap, state['freq_khz'], state.get('mode', '')), daemon=True).start()
    except Exception:
        pass
    return state


def _rig_state_dict_impl(cfg_snap):
    import logx_cat as cat
    cat_settings = cat.cat_settings(cfg_snap)
    if cat_settings['enabled'] and cat_settings['mode'] == 'native':
        return cat.get_state(cfg_snap)
    if cat_settings['enabled'] and cat_settings['mode'] == 'tci':
        import logx_tci as tci
        return tci.get_state(cfg_snap)
    if cat_settings['enabled'] and cat_settings['mode'] == 'flrig':
        import logx_flrig as flrig
        settings = flrig.flrig_settings(cfg_snap)
        state = flrig.get_state(settings['host'], settings['port'])
        state['enabled'] = True
        return state
    import logx_rig as rig
    settings = rig.rig_settings(cfg_snap)
    if not settings['enabled']:
        return {'enabled': False}
    state = rig.get_state(settings['host'], settings['port'])
    state['enabled'] = True
    return state


def _amp_state_dict(cfg_snap):
    import logx_amp as amp
    return amp.get_state(cfg_snap)


def _wsjtx_state_dict(cfg_snap):
    import logx_wsjtx as wsjtx
    settings = wsjtx.wsjtx_settings(cfg_snap)
    if not settings['enabled']:
        return {'enabled': False}
    # Démarrage à chaud (idempotent) : pas besoin de relancer le serveur
    wsjtx.start_listener(
        get_cfg=lambda: dict(current_config),
        add_qso=lambda q: add_qso_to_log(q, force=False)[0],
        port=settings['port'])
    st = wsjtx.current_status()
    st['enabled'] = True
    st['port'] = settings['port']
    # Alerte « DXCC/département manquant » façon GridTracker : les indicatifs
    # décodés récemment en FT8/FT4 (pas seulement ceux loggués) sont croisés
    # avec TOUTE la vie de la station via logx_awards.spotted_new_ones() —
    # déjà écrite pour poser exactement la même question aux spots du
    # cluster DX côté /coach/state, réutilisée telle quelle plutôt que
    # dupliquée (spots_by_label a la même forme : {label: [{dx, freq}...]}).
    try:
        import logx_awards as awards
        decodes = wsjtx.recent_decodes()
        if decodes:
            # Groupé par bande réelle (label lisible, même convention que
            # _spots_from_caches() : '14 MHz'/'HF'...) plutôt qu'une seule
            # clé 'wsjtx' — spotted_new_ones() recopie ce label tel quel
            # dans son résultat ('band'), autant qu'il soit parlant pour
            # l'alerte affichée côté client.
            spots_by_label = {}
            for d in decodes:
                label = f"{d['band']} MHz" if d.get('band') else 'FT8/FT4'
                spots_by_label.setdefault(label, []).append({'dx': d['call'], 'freq': d['freq_mhz']})
            with log_lock:
                log_copy = list(shared_log)
            st['missing'] = awards.spotted_new_ones(log_copy, spots_by_label, max_n=12)
        else:
            st['missing'] = []
    except Exception:
        st['missing'] = []
    return st


def _rotor_state_dict(cfg_snap):
    import logx_rotor as rotor
    settings = rotor.rotor_settings(cfg_snap)
    if not settings['enabled']:
        return {'enabled': False}
    state = rotor.get_position(settings['host'], settings['port'])
    state['enabled'] = True
    return state


def _activation_db_adapter(program):
    """Programme d'activation -> {search(q), lookup(ref), nearby(lat,lon,max_km)
    ou None, status()} — interface commune à SOTA (fonctions historiques de
    logx_sota.py, non modifiées) et POTA/WWFF/IOTA (moteur générique
    logx_activation_db.ActivationDatabase), pour UNE seule UI de recherche
    côté configuration plutôt que 5 implémentations quasi identiques. WCA n'a
    pas de coordonnées GPS dans sa source (cf. logx_wca.py) : nearby=None
    (chercher les châteaux autour de moi resterait impossible sans géocoder
    toute la base). lookup() géocode en revanche à la demande LA référence
    demandée (une seule, mise en cache) pour donner une position à MA
    référence activée, cf. logx_wca.get_castle_geocoded."""
    program = (program or '').upper()
    if program == 'SOTA':
        import logx_sota as sota
        return {'search': sota.search_summits, 'lookup': sota.get_summit,
                'nearby': sota.nearby_summits, 'status': sota.summits_status}
    if program == 'POTA':
        import logx_pota as pota
        return {'search': pota.parks_db.search, 'lookup': pota.parks_db.get,
                'nearby': pota.parks_db.nearby, 'status': pota.parks_db.status}
    if program == 'WWFF':
        import logx_wwff as wwff
        return {'search': wwff.directory_db.search, 'lookup': wwff.directory_db.get,
                'nearby': wwff.directory_db.nearby, 'status': wwff.directory_db.status}
    if program == 'IOTA':
        import logx_iota as iota
        return {'search': iota.search_groups, 'lookup': iota.groups_db.get,
                'nearby': iota.groups_db.nearby, 'status': iota.groups_db.status}
    if program == 'WCA':
        import logx_wca as wca
        return {'search': wca.search_castles, 'lookup': wca.get_castle_geocoded,
                'nearby': None, 'status': wca.status}
    return None


def _freq_khz_from_payload(payload):
    """Fréquence en kHz depuis un payload JSON de self-spot : freq_khz direct,
    ou repli sur freq_mhz * 1000. Factorisé depuis /cluster/spot, /pota/spot
    et /sota/spot qui recopiaient exactement ce bloc (copier-coller repéré en
    revue de code). Renvoie 0 si absent/invalide, sans lever — à l'appelant
    de décider si une fréquence manquante est bloquante."""
    freq_khz = payload.get('freq_khz') or 0
    if not freq_khz and payload.get('freq_mhz'):
        try:
            freq_khz = float(payload['freq_mhz']) * 1000
        except (TypeError, ValueError):
            freq_khz = 0
    return freq_khz


# ─── HTTP HANDLER ─────────────────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def do_OPTIONS(self):
        self._raw(200, None, None)

    def do_DELETE(self):
        """Gérer les requêtes DELETE (ex: /log/delete/42)."""
        # DELETE supprime des QSO du log : mêmes exigences d'auth que do_POST
        # (sans quoi n'importe quel appareil du LAN pouvait effacer le carnet).
        if not self._require_auth():
            return
        if self.path.startswith('/log/delete/'):
            try:
                qso_id = int(self.path.split('/')[-1])
                # bump_log_version()/mark_qso_deleted() DANS le même verrou que la
                # suppression (voir commentaire équivalent dans add_qso_to_log) :
                # sans quoi un lecteur /log/list concurrent pourrait capturer un
                # log_copy déjà privé du QSO mais un tombstone pas encore posé,
                # et l'afficherait indéfiniment chez un pair déjà synchronisé.
                with log_lock:
                    before = len(shared_log)
                    removed = [q for q in shared_log if q.get('id') == qso_id]
                    shared_log[:] = [q for q in shared_log if q.get('id') != qso_id]
                    bump_log_version()
                    mark_qso_deleted(qso_id)   # voir /log/list?since= (synchro différentielle)
                save_log_to_disk()
                # Le QSO supprimé (id normalement unique) peut avoir un scan QSL
                # papier attaché (voir /qsl_scan/upload) — sans ce nettoyage, le
                # fichier restait orphelin sur disque indéfiniment (seul le
                # REMPLACEMENT d'un scan appelait delete_scan(), jamais la
                # suppression du QSO lui-même).
                for q in removed:
                    scan = q.get('qsl_scan')
                    if scan:
                        import logx_qsl_scan as qslscan
                        qslscan.delete_scan(scan)
                self._json({'ok': True, 'deleted': before - len(shared_log)})
            except Exception as e:
                self._json({'error': str(e)}, 400)
        elif self.path.startswith('/qtc/delete/'):
            # Corriger une série QTC mal saisie (règlement WAE : pas de tolérance
            # sur le format) sans devoir vider tout qtc_log.json à la main.
            try:
                from logx_storage import qtc_log, qtc_lock, save_qtc_to_disk
                qtc_id = int(self.path.split('/')[-1])
                with qtc_lock:
                    before = len(qtc_log)
                    qtc_log[:] = [q for q in qtc_log if q.get('id') != qtc_id]
                    deleted = before - len(qtc_log)
                save_qtc_to_disk()
                self._json({'ok': True, 'deleted': deleted})
            except Exception as e:
                self._json({'error': str(e)}, 400)
        else:
            self._raw(404, None, None)

    def do_GET(self):
        path = self.path.split('?')[0]

        # Info réseau (IP locale pour les clients WiFi)
        if path == '/network/info':
            import socket as _sock
            try:
                _s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
                _s.connect(('8.8.8.8', 80))
                local_ip = _s.getsockname()[0]
                _s.close()
            except:
                local_ip = '127.0.0.1'
            self._json({
                'local_ip': local_ip,
                'port': PORT,
                'url_logbook': f'http://{local_ip}:{PORT}/logx_logbook.html',
                'url_terrain': f'http://{local_ip}:{PORT}/logx_mobile.html',
                'peers': len(connected_peers),
            })
            return

        # Journal d'erreurs local (sys.excepthook/threading.excepthook, voir
        # logx_errorlog.py) — alimente le bouton "Signaler un problème" de la
        # barre de statut (logx_statusbar.js). EXCLU du gate debug ci-dessous
        # à dessein : contrairement aux autres /debug/*, celui-ci doit rester
        # utilisable par n'importe quel testeur, pas seulement en mode debug.
        # Reste protégé par le token de session (_require_auth) : ce sont des
        # traces Python complètes + un chemin de fichier local, pas question
        # de les exposer sans auth à n'importe quel appareil du LAN.
        if path == '/debug/errors':
            if not self._require_auth():
                return
            import logx_errorlog as _errlog
            self._json({'errors': _errlog.get_recent_errors(), 'log_path': _errlog.log_path()})
            return

        # ── Endpoints de diagnostic : désactivés par défaut ──────────────────
        # Activer : "debug": true dans la section server de config.json,
        # ou toggle debug dans la config envoyée par le client.
        if path.startswith('/debug/'):
            with config_lock:
                dbg = bool((current_config or {}).get('debug', False))
            if not dbg:
                try:
                    with open('config.json', encoding='utf-8') as f:
                        dbg = bool((json.load(f).get('server', {}) or {}).get('debug', False))
                except Exception:
                    dbg = False
            if not dbg:
                self._json({'error': 'Endpoints /debug/* désactivés '
                                     '(server.debug=true dans config.json pour activer)'}, 404)
                return

        # Diagnostic ON4KST — teste la connexion avec les identifiants sauvegardés
        # (lus depuis current_config, jamais depuis la requête). Le mot de passe
        # n'apparaît jamais dans la réponse, seule la sortie du serveur ON4KST.
        # Paramètres optionnels : ?chat=2 (salon 144/432) &cmd=/show users (commande)
        if path == '/debug/test_on4kst':
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            cfg_snap = self._cfg_snapshot()
            callsign = cfg_snap.get('on4kst_callsign', '')
            password = cfg_snap.get('on4kst_password', '')
            result = fetch_on4kst_raw(
                callsign, password,
                chat=(qs.get('chat', [None])[0]),
                command=(qs.get('cmd', [None])[0]),
            )
            self._json({'ok': result['ok'], 'error': result['error'], 'raw': result['raw']})
            return

        # Log partagé — liste tous les QSO
        if path == '/log/list':
            client_ip = self.client_address[0]
            connected_peers.add(client_ip)
            # Version demandée par le client (?v=N, voir logx_storage.log_version) :
            # si elle correspond à la version actuelle, RIEN n'a changé depuis son
            # dernier appel → réponse minuscule au lieu de retransmettre tout le
            # log. Avec un log de plusieurs milliers de QSO pollé toutes les 5 s
            # par poste connecté, la quasi-totalité des polls ne voient aucun
            # changement (personne ne loggue un QSO toutes les 5 s) : c'était
            # plusieurs Mo transmis, parsés et re-rendus pour rien à chaque fois.
            from urllib.parse import parse_qs, urlparse
            import logx_storage as _storage
            qs = parse_qs(urlparse(self.path).query)
            client_v = qs.get('v', [''])[0]
            since_raw = qs.get('since', [''])[0]
            boot_raw = qs.get('boot', [''])[0]
            # Copie sous verrou (rapide, juste des références), puis sérialisation
            # JSON + écriture socket HORS verrou : c'était le seul endpoint qui
            # gardait log_lock pendant tout l'envoi. Avec un gros log (milliers de
            # QSO) et ce endpoint pollé toutes les 5 s par chaque poste connecté,
            # ça bloquait en cascade tout autre accès à shared_log (ajout de QSO,
            # /coach/state, /log/status...) pendant toute la durée du transfert.
            with log_lock:
                current_v = _storage.log_version
                unchanged = client_v.isdigit() and int(client_v) == current_v
                total_now = len(shared_log)
                log_copy = None if unchanged else list(shared_log)
            if unchanged:
                self._json({'unchanged': True, 'version': current_v,
                           'total': total_now, 'peers': len(connected_peers),
                           'boot': _storage.SERVER_BOOT_ID})
                return
            # Portée du concours actif (logx_storage.active_scope_id) : en mode
            # concours/expédition avec un concours sélectionné, le logbook ne
            # doit montrer QUE les QSO de CETTE édition (contest+année) —
            # jamais le log de base (simple), ni un concours/année différent
            # resté dans shared_log faute d'avoir été archivé. En mode simple,
            # ou si aucun concours n'est sélectionné, aucun filtrage (log
            # complet, comportement historique — la "logbook simple" est le
            # journal personnel complet).
            log_copy = _scope_filtered(log_copy, self._cfg_snapshot())
            # Synchro différentielle (?since=&boot=, voir logx_storage.stamp_qso_version/
            # mark_qso_deleted/mark_hard_reset et _valid_since ci-dessus) :
            # renvoie UNIQUEMENT les QSO ajoutés/modifiés depuis cette version
            # + les id supprimés depuis, au lieu de retransmettre tout le log
            # filtré. 'total'/'score' restent calculés sur le log COMPLET (pas
            # le delta) : le client les affiche tels quels, ce ne sont pas des
            # deltas. Repli explicite sur la liste complète si ?since= est
            # absent/invalide — compatibilité ascendante totale : un client
            # qui n'envoie pas ?since reçoit exactement ce qu'il recevait
            # avant cette fonctionnalité.
            since = _valid_since(since_raw, boot_raw, current_v)
            if since is not None:
                delta_qsos = [q for q in log_copy if q.get('_v', 0) > since]
                deleted_ids = [d['id'] for d in _storage.deleted_qsos if d['v'] > since]
                self._json({
                    'delta': True,
                    'qsos': delta_qsos,
                    'deleted': deleted_ids,
                    'total': len(log_copy),
                    'peers': len(connected_peers),
                    'score': sum(q.get('points', 0) for q in log_copy),
                    'version': current_v,
                    'boot': _storage.SERVER_BOOT_ID,
                })
                return
            self._json({
                'qsos': log_copy,
                'total': len(log_copy),
                'peers': len(connected_peers),
                'score': sum(q.get('points', 0) for q in log_copy),
                'version': current_v,
                'boot': _storage.SERVER_BOOT_ID,
            })
            return

        # N° de série suivant pour une bande — allocation SERVEUR (voir
        # logx_storage.allocate_next_serial) : remplace l'incrémentation locale
        # de logx_logbook.js (PC) et le champ texte libre de logx_mobile.html,
        # pour qu'aucune saisie concurrente (PC + mobile, ou deux mobiles) ne
        # puisse émettre le même numéro sur la même bande.
        # ?peek=1 : simple APERÇU (logx_storage.peek_next_serial), ne consomme
        # PAS le compteur — utilisé par la mobile pour ne faire que PRÉ-REMPLIR
        # une suggestion (changement de bande, après un QSO, au chargement de
        # la page) sans brûler un numéro tant qu'aucun QSO n'est réellement
        # soumis avec.
        if path == '/log/next_serial':
            from urllib.parse import parse_qs, urlparse
            import logx_storage as _storage
            qs = parse_qs(urlparse(self.path).query)
            band = (qs.get('band', ['']) or [''])[0]
            peek = (qs.get('peek', ['']) or [''])[0] in ('1', 'true')
            serial = _storage.peek_next_serial(band) if peek else _storage.allocate_next_serial(band)
            self._json({'serial': str(serial).zfill(3)})
            return

        # Lookup indicatif en temps réel (local → HamQTH si inconnu)
        if path.startswith('/calldb/lookup/'):
            try:
                call = path.split('/calldb/lookup/')[-1].upper().strip()
                if not call:
                    self._json({'error': 'indicatif manquant'}, 400)
                    return
                base = call.split('/')[0]
                calldb_path = os.path.join(os.getcwd(), 'calldb.json')
                # Lecture via le cache mémoire (invalidé au mtime) : /calldb/lookup
                # est appelé à chaque frappe d'indicatif — relire tout le fichier
                # (~19 000 entrées) à chaque fois était le point chaud principal.
                import logx_departments as _dep
                local = _dep._load_calldb().get(base, {})
                # Locator déjà connu localement
                if local.get('locator'):
                    self._json({'call': base, 'locator': local['locator'], 'dept': local.get('dept',''), 'source': 'local'})
                    return
                # Sinon interroger HamQTH
                result = lookup_hamqth(base)
                if result and result.get('locator'):
                    # Persister dans calldb.json — FUSION, jamais de remplacement
                    # total (une entrée locale peut déjà porter un 'dept' REF
                    # que HamQTH ignore ; l'écraser cassait le tableau de chasse).
                    if os.path.exists(calldb_path):
                        with open(calldb_path, 'r', encoding='utf-8') as f:
                            db2 = json.load(f)
                        entry = db2.setdefault('calls', {}).setdefault(base, {})
                        entry['locator'] = result['locator']
                        if result.get('country'):
                            entry['country'] = result['country']
                        save_json_atomic(calldb_path, db2, lock=calldb_lock, compact=True)
                    self._json({'call': base, 'locator': result['locator'], 'country': result.get('country',''), 'source': 'hamqth'})
                    return
                self._json({'call': base, 'locator': '', 'source': 'none'})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Status réseau + spots clusters
        if path == '/log/status':
            self._json({
                'peers':     len(connected_peers),
                'qso_count': len(shared_log),
                'spots':     SPOTS_CACHE,
            })
            return

        # Test direct fetch DXSummit HF
        if path == '/debug/spots':
            import urllib.request as _ur
            results = {}
            for band in ['14MHz','7MHz','21MHz']:
                url = f'http://www.dxsummit.fi/api/v1/spots?include={band}&limit=5'
                try:
                    req = _ur.Request(url, headers={'User-Agent':'Mozilla/5.0'})
                    with _ur.urlopen(req, timeout=8) as r:
                        raw = r.read().decode('utf-8','replace')
                    data = json.loads(raw)
                    items = data if isinstance(data,list) else data.get('spots',[])
                    results[band] = {
                        'count': len(items),
                        'fields': list(items[0].keys()) if items else [],
                        'sample': items[0] if items else None,
                    }
                except Exception as e:
                    results[band] = f'ERREUR: {e}'
            # Appel direct fetch_dxsummit_hf
            try:
                spots = fetch_dxsummit_hf(filter_digital=False)
                results['fetch_dxsummit_hf_nofilter'] = {
                    'count': len(spots),
                    'sample': spots[:2] if spots else [],
                }
            except Exception as e:
                results['fetch_dxsummit_hf_nofilter'] = f'ERREUR: {e}'
            self._json(results)
            return

        # Diagnostic cluster final
        if path == '/debug/cluster':
            results = {}
            hdrs = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)','Accept':'application/json,*/*'}

            # ── 1. APIs cluster en HTTP (pas HTTPS) ───────────────────────────
            http_apis = [
                ('spothole_http',  'http://spothole.app/api/spots?limit=20'),
                ('spothole_api',   'http://api.spothole.app/spots?limit=20'),
                ('dxheat_http',    'http://dxheat.com/dxc/'),
                ('dxheat_api',     'http://dxheat.com/api/spots?limit=20&band=20m'),
                ('dxsummit_http',  'http://www.dxsummit.fi/api/v1/spots?include=14MHz&limit=10'),
                ('lecluster_f5len','http://lecluster.f5len.org/search/index.php?band=14&limit=30'),
                ('f4hxn_http',     'http://dx.f4hxn.fr/'),
                ('f4hxn_api',      'http://dx.f4hxn.fr/api/spots'),
                ('dxfun_http',     'http://dxfuncluster.com/'),
            ]
            for label, url in http_apis:
                try:
                    req = urllib.request.Request(url, headers=hdrs)
                    with urllib.request.urlopen(req, timeout=6) as r:
                        raw = r.read(2000).decode('utf-8','replace')
                    calls = re.findall(r'\b([A-Z]{1,3}[0-9][A-Z0-9]{0,3}[A-Z]{2})\b', raw)
                    results[label] = f"HTTP OK — {len(raw)}B — {len(calls)} callsigns — {raw[:150]!r}"
                except Exception as e:
                    results[label] = f"ERREUR: {e}"

            # ── 2. Telnet cluster sur port 80 (certains clusters l'acceptent) ─
            telnet_p80 = [
                ('f4hxn_t80',  'dx.f4hxn.fr',    80),
                ('dxfun_t80',  'dxfuncluster.com',80),
                ('f5len_t80',  'cluster.f5len.org',80),
                ('f5len_t23',  'cluster.f5len.org',23),
                ('f4hxn_t7300','dx.f4hxn.fr',   7300),
                ('dxfun_t7300','dxfuncluster.com',7300),
                ('ve7cc_p80',  'dxc.ve7cc.net',   80),
            ]
            for label, host, port in telnet_p80:
                try:
                    s = socket.socket()
                    s.settimeout(5)
                    s.connect((host, port))
                    time.sleep(0.3)
                    banner = s.recv(512).decode('utf-8','replace')
                    s.close()
                    results[label] = f"CONNECT OK port {port} — banner: {banner[:80].strip()!r}"
                except Exception as e:
                    results[label] = f"ERREUR port {port}: {e}"

            # ── 3. Variables d'env proxy ──────────────────────────────────────
            results['env_proxy'] = {
                'HTTP_PROXY':  os.environ.get('HTTP_PROXY','—'),
                'HTTPS_PROXY': os.environ.get('HTTPS_PROXY','—'),
                'http_proxy':  os.environ.get('http_proxy','—'),
                'https_proxy': os.environ.get('https_proxy','—'),
            }
            self._json(results)
            return

        # Refresh données IA (clusters + logs + scoring)
        if path == '/data/refresh':
            try:
                cfg = self._load_config_from_query()
                result = do_refresh(cfg)
                self._json(result)
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                print(f"[DATA] ERREUR refresh : {e}\n{tb}")
                self._json({'error': str(e), 'traceback': tb}, 500)
            return

        # Chat multi-opérateur — récupérer les messages depuis un id donné
        if path.startswith('/chat/list'):
            try:
                since = 0
                if 'since=' in self.path:
                    since = int(self.path.split('since=')[-1].split('&')[0])
            except Exception:
                since = 0
            with chat_lock:
                new_msgs = [m for m in chat_messages if m['id'] > since]
                last_id = chat_messages[-1]['id'] if chat_messages else 0
            self._json({'messages': new_msgs, 'last_id': last_id,
                        'typing': _active_typing()})
            return

        # Prompt système actuel
        if path == '/data/system_prompt':
            cfg = self._load_config_from_query()
            self._json({'system_prompt': build_system_prompt(cfg)})
            return

        # Liste des concours
        if path == '/data/contests':
            self._json(list(CONTEST_SCORING.keys()))
            return

        # Calendrier externe WA7BNM
        if path == '/data/external_contests':
            year = CURRENT_YEAR
            try: year = int(self.path.split('year=')[-1].split('&')[0]) if 'year=' in self.path else year
            except: pass
            # Accès via rules.EXTERNAL_CONTESTS_CACHE : le refresh RÉASSIGNE
            # ce cache, un nom importé resterait figé sur l'ancien dict.
            if not rules.EXTERNAL_CONTESTS_CACHE or rules.EXTERNAL_CONTESTS_CACHE.get('year') != year:
                data = refresh_external_contests()
            else:
                data = rules.EXTERNAL_CONTESTS_CACHE
            self._json({
                'year': year,
                'contests': data.get('contests', []) if year == CURRENT_YEAR else data.get('contests_next', []),
                'total': len(data.get('contests', [])),
                'updated': data.get('updated', ''),
                'source': 'WA7BNM Contest Calendar (contestcalendar.com)',
            })
            return

        # Forcer refresh WA7BNM
        if path == '/data/refresh_external':
            threading.Thread(target=refresh_external_contests, daemon=True).start()
            self._json({'ok': True, 'message': 'Rafraîchissement WA7BNM lancé'})
            return

        # Calendrier avec prochaines dates calculées automatiquement
        if path.startswith('/data/calendar'):
            calendar_data = calc_all_dates()
            today = datetime.date.today()
            result = []
            for cid, cdef in CONTEST_DEFINITIONS.items():
                info = calendar_data.get(cid, {})
                result.append({
                    'id': cid,
                    'name': cdef['name'],
                    'organizer': cdef['organizer'],
                    'date': info.get('date', '—'),
                    'year': info.get('year', CURRENT_YEAR),
                    'next_year': info.get('next_year', False),
                    'bands': cdef.get('bands', []),
                    'modes': cdef.get('modes', []),
                    'exchange': cdef.get('exchange', ''),
                    'scoring': cdef.get('scoring', {}),
                    'log_format': cdef.get('log_format', ''),
                    'log_submit': cdef.get('log_submit', ''),
                    'log_deadline': cdef.get('log_deadline', ''),
                    'notes': cdef.get('notes', ''),
                    'rules_url': cdef.get('rules_url', ''),
                    # Permet au client de calculer début/fin sans dupliquer
                    # les règles de dates (assistant "nouveau concours")
                    'duration_h': cdef.get('duration_h'),
                    'start_utc': cdef.get('start_utc', '00:00'),
                    # Concours ajouté par extraction IA + relecture humaine
                    'custom': cid in CUSTOM_CONTEST_IDS,
                })
            # Trier par date croissante
            def sort_key(c):
                m = re.search(r'(\d{2})/(\d{2})/(\d{4})', c.get('date',''))
                if m: return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                return datetime.date(2099, 1, 1)
            result.sort(key=sort_key)
            self._json({
                'year': CURRENT_YEAR,
                'contests': result,
                'last_update': rules.rules_db.get('last_update', ''),
                'alerts': rules.rules_db.get('alerts', []),
            })
            return

        # Export des concours validés (partage communautaire entre stations)
        if path == '/rules/export_custom':
            try:
                data = {}
                if os.path.exists('custom_contests.json'):
                    with open('custom_contests.json', 'r', encoding='utf-8') as f:
                        data = json.load(f)
                self._json({
                    'format': 'logx-custom-contests',
                    'version': 1,
                    'exported_at': datetime.datetime.utcnow().isoformat(),
                    'exported_by': self._cfg_snapshot().get('callsign', ''),
                    'contests': data,
                })
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Forcer une mise à jour des règlements
        if path == '/data/update_rules':
            # Déclenche des écritures (rules_db) : token exigé comme les POST.
            if not self._require_auth():
                return
            threading.Thread(target=run_annual_update, daemon=True).start()
            self._json({'ok': True, 'message': f'Mise à jour {CURRENT_YEAR} lancée'})
            return

        # Coach de stratégie — état structuré, sans appel IA (rapide, pollable).
        # DXMaps (réseau) : uniquement pour les concours VHF+, avec cache 10 min.
        if path == '/coach/state':
            import logx_coach as coach
            with config_lock:
                cfg_snapshot = dict(current_config)
            dxmaps = None
            cdef = CONTEST_DEFINITIONS.get(cfg_snapshot.get('contest', ''), {})
            bands = [str(b) for b in cdef.get('bands', [])]
            if bands and not any(b in coach.HF_BANDS for b in bands):
                global _coach_dxmaps_cache, _coach_dxmaps_ts
                if time.time() - _coach_dxmaps_ts > 600:
                    try:
                        _coach_dxmaps_cache = fetch_dxmaps_vhf()
                    except Exception:
                        _coach_dxmaps_cache = None
                    _coach_dxmaps_ts = time.time()
                dxmaps = _coach_dxmaps_cache
            # Densité de nouveaux mults sur le cluster (caches, pas de réseau)
            mult_count = None
            try:
                from logx_scoring import build_ranked_spots
                ranked, _ = build_ranked_spots({}, _spots_from_caches(), cfg_snapshot)
                mult_count = sum(1 for s in ranked
                                 if s.get('scoring', {}).get('new_mult')
                                 and not s.get('scoring', {}).get('already_done'))
            except Exception:
                pass
            # Indice K pour la prévision aurora — lecture cache seule, jamais
            # de réseau bloquant (get_solar_cached ne fait qu'un rafraîchissement
            # de fond si le cache est périmé, /coach/state doit rester rapide).
            k_index = None
            try:
                from logx_clusters import get_solar_cached
                k_index = (get_solar_cached() or {}).get('k_index')
            except Exception:
                pass
            # Langue des textes du coach (le front la connaît : localStorage rc_lang).
            from urllib.parse import parse_qs, urlparse
            lang = (parse_qs(urlparse(self.path).query).get('lang') or ['fr'])[0]
            state = coach.build_coach_state(cfg_snapshot, shared_log, dxmaps,
                                            mult_spots_count=mult_count,
                                            k_index=k_index, lang=lang)
            # Suggestions IA proactives : pays/départements JAMAIS travaillés à
            # VIE (pas seulement le multiplicateur du concours en cours) parmi
            # les stations actuellement spottées sur le cluster — poussées ici
            # sans action de l'utilisateur, comme demandé.
            try:
                import logx_awards as awards
                from logx_coach_i18n import t
                new_ones = awards.spotted_new_ones(shared_log, _spots_from_caches())
                new_hints = []
                for n in new_ones:
                    freq_txt = f" {n['freq']}" if n.get('freq') else ''
                    key = 'hint_new_dxcc' if n['type'] == 'dxcc' else 'hint_new_dept'
                    new_hints.append({'level': 'action', 'icon': '🎯',
                                      'text': t(lang, key, label=n['label'],
                                                call=n['call'], freq_txt=freq_txt)})
                state['hints'] = new_hints + state['hints']
                state['new_targets'] = new_ones
            except Exception:
                pass
            self._json(state)
            return

        # Débrief post-concours : stats déterministes + prompt prêt pour l'IA
        # (le client l'envoie ensuite à /proxy/ai — la clé reste côté serveur).
        if path == '/coach/debrief':
            import logx_coach as coach
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            self._json(coach.build_debrief(cfg_snap, log_copy))
            return

        # Recherche d'un indicatif en cascade : QRZ.com (si identifiants
        # configurés) -> HamQTH -> HamDB (identifiants QRZ lus dans la config,
        # jamais dans la requête ni renvoyés au client ; les deux replis
        # gratuits ne demandent aucun identifiant).
        if path.startswith('/qrz/lookup'):
            from urllib.parse import parse_qs, urlparse
            import logx_callbook as callbook
            call = (parse_qs(urlparse(self.path).query).get('call', [''])[0])
            res = callbook.lookup(call, self._cfg_snapshot(), shared_log)
            res['enabled'] = True
            self._json(res)
            return

        # Statut d'un indicatif À LA FRAPPE : nouveau / doublon / nouveau_mult.
        # Réutilise le moteur de scoring (état reconstruit depuis shared_log).
        if path.startswith('/log/check'):
            from urllib.parse import parse_qs, urlparse
            from logx_scoring import build_ranked_spots
            qs = parse_qs(urlparse(self.path).query)
            call = (qs.get('call', [''])[0]).upper().strip()
            band = (qs.get('band', [''])[0]).strip()
            mode = (qs.get('mode', [''])[0]).upper().strip()
            if len(call) < 3:
                self._json({'status': 'inconnu'})
                return
            cfg_snap = self._cfg_snapshot()
            # Portée (contest+année, comme add_qso_to_log) : sans l'année, un
            # indicatif déjà travaillé sur la MÊME édition annuelle d'un
            # concours récurrent une année précédente était signalé "doublon"
            # à tort, en désaccord avec la vraie détection de add_qso_to_log.
            scope_id = active_scope_id(cfg_snap)
            # LOGBOOK SIMPLE : pas de règle "1 QSO/station/bande" hors concours.
            if cfg_snap.get('usage_mode') != 'simple':
                with log_lock:
                    dup = any(
                        str(q.get('call', '')).upper().strip() == call
                        and str(q.get('band', '')) == band
                        and (not mode or str(q.get('mode', '')).upper() == mode)
                        and qso_scope_id(q) == scope_id
                        for q in shared_log)
                if dup:
                    self._json({'status': 'doublon'})
                    return
            label = f"{band} MHz" if band else 'HF'
            ranked, _ = build_ranked_spots(
                {}, {label: [{'dx': call, 'freq': '', 'info': ''}]}, cfg_snap)
            sc = ranked[0].get('scoring', {}) if ranked else {}
            self._json({
                'status': 'nouveau_mult' if sc.get('new_mult') else 'nouveau',
                'points': sc.get('direct_pts', 0),
                'mult_type': sc.get('mult_type', ''),
                'explanation': sc.get('explanation', ''),
            })
            return

        # Validateur de log AVANT soumission (départements/locators/doublons/
        # fenêtre du concours) — lecture seule, spécial REF.
        if path == '/log/validate':
            import logx_validator as validator
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            self._json(validator.validate_log(
                log_copy, cfg_snap.get('contest', ''), cfg_snap))
            return

        # Index d'indicatifs fusionné (MASTER.SCP + calldb + archives +
        # qso_archive + log) : remplace /calldb.json côté client pour le
        # Super Check Partial — même forme, enrichie de qso_count/worked/
        # last_date. Le concours actif surclasse dept/locator/nom/section/zone
        # avec le Call History N1MM importé pour LUI (voir export_index()).
        if path == '/call/index':
            import logx_callhistory as callhistory
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            self._json(callhistory.export_index(log_copy, contest=cfg_snap.get('contest', '')))
            return

        # Historique de station (« déjà contacté ») + « nouveau à vie » :
        # tous les QSO passés avec cette station, sur TOUTE la vie du log.
        if path.startswith('/call/history'):
            from urllib.parse import parse_qs, urlparse
            import logx_awards as awards
            qp = parse_qs(urlparse(self.path).query)
            call = (qp.get('call', [''])[0]).upper().strip()
            band = (qp.get('band', [''])[0]).strip()
            with log_lock:
                log_copy = list(shared_log)
            h = awards.history(call, log_copy)
            h['new_one'] = awards.new_one(call, band, '', log_copy)
            self._json(h)
            return

        # Vérification « N+1 » (busted call check, façon N1MM) : indicatifs
        # connus à une distance de Damerau-Levenshtein de 1 de celui tapé —
        # calcul 100% local (aucun réseau), donc appelable directement ici.
        if path.startswith('/call/near'):
            from urllib.parse import parse_qs, urlparse
            import logx_callhistory as callhistory
            qp = parse_qs(urlparse(self.path).query)
            call = (qp.get('call', [''])[0]).upper().strip()
            with log_lock:
                log_copy = list(shared_log)
            self._json({'matches': callhistory.near_matches(call, log_copy)})
            return

        # État des imports (bouton CONFIG) : nombre d'indicatifs MASTER.SCP et
        # de fiches Call History déjà importées pour le concours actif.
        if path == '/callhistory/status':
            from urllib.parse import parse_qs, urlparse
            import logx_callhistory as callhistory
            cfg_snap = self._cfg_snapshot()
            scp_count = 0
            try:
                if os.path.exists(callhistory.MASTER_SCP_FILE):
                    with open(callhistory.MASTER_SCP_FILE, encoding='utf-8') as f:
                        scp_count = (json.load(f) or {}).get('count', 0)
            except Exception:
                pass
            # Le concours qu'affiche/vient de choisir le CLIENT (?contest=,
            # state.contest côté logx_configuration.html) peut différer de
            # celui SAUVEGARDÉ côté serveur — cfg_snap ne se met à jour qu'au
            # clic « Enregistrer » — d'où la priorité au paramètre explicite
            # quand il est fourni (sinon on retombe sur la config serveur,
            # comme avant, pour les appels sans concours en cours de sélection).
            qp = parse_qs(urlparse(self.path).query)
            contest = (qp.get('contest', [''])[0] or cfg_snap.get('contest', '')).strip().upper()
            ch_count = callhistory.call_history_count(contest) if contest else 0
            self._json({'master_scp_count': scp_count, 'contest': contest,
                       'call_history_count': ch_count})
            return

        # Tableau de bord diplômes : DXCC / départements travaillés & confirmés
        # sur toute la vie de la station (pas seulement le concours en cours).
        if path == '/awards/summary':
            import logx_awards as awards
            with log_lock:
                log_copy = list(shared_log)
            self._json(awards.award_summary(log_copy))
            return

        # Worked Matrix : grille bande × CW/Phone/Digital. Par défaut sur
        # toute la vie de la station (Diplômes/QSL) — d'un coup d'œil, quelles
        # cases DXCC/WAS sont vides. ?scope=contest la restreint au concours
        # actuellement configuré (panneau détachable, vue "ce concours").
        if path.startswith('/awards/matrix'):
            from urllib.parse import parse_qs, urlparse
            import logx_awards as awards
            qp = parse_qs(urlparse(self.path).query)
            scope_id = cfg_scope_id(current_config) if qp.get('scope', [''])[0] == 'contest' else ''
            with log_lock:
                log_copy = list(shared_log)
            self._json(awards.worked_matrix(log_copy, scope_id))
            return

        # Activité par jour (vie entière) : petite vue statistique du popup
        # Diplômes — ?days=N (défaut 30). Réutilise collect_all_qsos comme
        # award_summary/worked_matrix, aucun nouveau parcours de fichiers.
        if path.startswith('/awards/activity'):
            from urllib.parse import parse_qs, urlparse
            import logx_awards as awards
            qp = parse_qs(urlparse(self.path).query)
            try:
                days = int(qp.get('days', ['30'])[0])
            except (TypeError, ValueError):
                days = 30
            # activity_by_day() ne fait que max(1, ...) côté bas : sans borne haute
            # ici, un ?days= énorme construirait une liste de sortie de taille
            # arbitraire (mémoire/temps de réponse) — 3650 = 10 ans, largement
            # suffisant pour ce petit graphique du popup Diplômes.
            days = max(1, min(days, 3650))
            with log_lock:
                log_copy = list(shared_log)
            self._json({'days': awards.activity_by_day(log_copy, days)})
            return

        # Record DX par bande — calculé depuis le vrai locator de chaque QSO
        # archivé (haversine), remplace l'ancien champ manuel record_dx (un
        # chiffre unique n'a pas de sens multi-bandes).
        if path == '/data/dx_records':
            import logx_awards as awards
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            self._json(awards.dx_records(cfg_snap.get('locator', ''), log_copy))
            return

        # EME (rebond lunaire) : position de la Lune depuis mon QTH + lever/
        # coucher — calculé localement (PyEphem), aucune donnée réseau.
        if path == '/data/eme_moon':
            import logx_eme as eme
            cfg_snap = self._cfg_snapshot()
            lat, lon = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            if lat is None:
                self._json({'available': False, 'error': 'Locator manquant ou invalide (page CONFIG)'})
                return
            alt_m = cfg_snap.get('altitude', 0) or 0
            pos = eme.moon_position(lat, lon, alt_m)
            rs = eme.moon_rise_set(lat, lon, alt_m)
            self._json({**pos, **rs})
            return

        # Décalage Doppler estimé à la fréquence courante (ou 144.1 MHz par défaut).
        if path.startswith('/data/eme_doppler'):
            import logx_eme as eme
            from urllib.parse import parse_qs, urlparse
            cfg_snap = self._cfg_snapshot()
            lat, lon = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            if lat is None:
                self._json({'available': False, 'error': 'Locator manquant ou invalide (page CONFIG)'})
                return
            qs = parse_qs(urlparse(self.path).query)
            try:
                freq_mhz = float((qs.get('freq') or ['144.1'])[0])
            except ValueError:
                freq_mhz = 144.1
            self._json(eme.doppler_shift_hz(lat, lon, freq_mhz, cfg_snap.get('altitude', 0) or 0))
            return

        # Fenêtre commune (Lune visible des DEUX QTH simultanément) avec un
        # correspondant, identifié par son locator (ex: FN31pr).
        if path.startswith('/data/eme_window'):
            import logx_eme as eme
            from urllib.parse import parse_qs, urlparse
            cfg_snap = self._cfg_snapshot()
            lat1, lon1 = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            if lat1 is None:
                self._json({'available': False, 'error': 'Locator manquant ou invalide (page CONFIG)'})
                return
            qs = parse_qs(urlparse(self.path).query)
            loc2 = (qs.get('locator') or [''])[0]
            lat2, lon2 = locator_to_latlon(loc2)
            if lat2 is None:
                self._json({'available': False, 'error': 'Locator du correspondant manquant ou invalide (ex: FN31pr)'})
                return
            try:
                hours = float((qs.get('hours') or ['48'])[0])
            except ValueError:
                hours = 48
            # Borne dure : le balayage éphéméride fait hours*60/pas itérations
            # PyEphem dans CE thread HTTP — sans plafond, ?hours=48000000
            # (faute de frappe ou n'importe quel poste du réseau local) bloque
            # un thread à 100 % CPU pendant des heures. NaN/inf passent float().
            if not (1 <= hours <= 168):   # faux aussi pour NaN
                hours = 48
            self._json(eme.common_window(lat1, lon1, lat2, lon2, hours=hours))
            return

        # État de configuration QSL + horodatage des dernières synchros.
        if path == '/qsl/status':
            import logx_qsl as qsl
            self._json(qsl.qsl_status(self._cfg_snapshot()))
            return

        # Tableau de chasse départements REF : contactés vs total (depuis le log)
        if path == '/data/departments_worked':
            import logx_departments as dep
            cfg_snap = self._cfg_snapshot()
            self._json(dep.departments_progress(shared_log, cfg_scope_id(cfg_snap)))
            return

        # Chasse aux départements : manquants + stations connues, croisés avec
        # les spots cluster actuels (station spottée = cible immédiate).
        if path == '/departments/targets':
            import logx_departments as dep
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            self._json(dep.department_targets(
                log_copy, cfg_scope_id(cfg_snap), _spots_from_caches(),
                cfg=cfg_snap))
            return

        # GeoJSON des départements français (cache disque, offline après 1er DL)
        if path == '/data/france_geojson':
            import logx_departments as dep
            body = dep.load_france_geojson()
            if not body:
                self._json({'error': 'GeoJSON indisponible (hors ligne au 1er accès)'}, 503)
                return
            body_bytes = body.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body_bytes)))
            self.send_header('Cache-Control', 'max-age=86400')
            self._cors()
            self.end_headers()
            self.wfile.write(body_bytes)
            return

        # GeoJSON mondial des pays (Europe/continent/monde — sélecteur d'échelle
        # de la page départements). Cache disque, offline après 1er téléchargement.
        if path == '/data/world_geojson':
            import logx_worldmap as wm
            body = wm.load_world_geojson()
            if not body:
                self._json({'error': 'GeoJSON indisponible (hors ligne au 1er accès)'}, 503)
                return
            body_bytes = body.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body_bytes)))
            self.send_header('Cache-Control', 'max-age=86400')
            self._cors()
            self.end_headers()
            self.wfile.write(body_bytes)
            return

        # Statut travaillé/non par pays (choroplèthe monde), projeté depuis les
        # entités DXCC contactées (même calcul que /data/countries_worked).
        if path == '/data/world_worked':
            import logx_worldmap as wm
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            self._json(wm.worked_by_country(log_copy, cfg_scope_id(cfg_snap)))
            return

        # URL(s) LAN pour connecter un téléphone/tablette (terrain/expédition) :
        # ouvre le logbook depuis le mobile sur le même WiFi, installable en PWA.
        if path == '/data/lan_url':
            import socket as _sock
            port = self.server.server_address[1] if self.server else 8080
            ips = set()
            try:
                s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
                s.settimeout(0.3)
                s.connect(('8.8.8.8', 80))
                ips.add(s.getsockname()[0])
                s.close()
            except OSError:
                pass
            try:
                for info in _sock.getaddrinfo(_sock.gethostname(), None, _sock.AF_INET):
                    ip = info[4][0]
                    if not ip.startswith('127.'):
                        ips.add(ip)
            except OSError:
                pass
            urls = [f'http://{ip}:{port}/logx_logbook.html' for ip in sorted(ips)]
            self._json({'port': port, 'ips': sorted(ips), 'urls': urls})
            return

        # Activation POTA/SOTA/IOTA/WWFF : avancement en direct (X/min QSO, P2P)
        if path == '/activation/state':
            import logx_activation as act
            cfg_snap = self._cfg_snapshot()
            program = cfg_snap.get('activation_program', '')
            my_ref = cfg_snap.get('my_activation_ref', '')
            if not program or not my_ref:
                self._json({'active': False, 'programs': act.programs_meta()})
                return
            with log_lock:
                log_copy = list(shared_log)
            st = act.activation_state(log_copy, program, my_ref)
            st['active'] = True
            st['programs'] = act.programs_meta()
            self._json(st)
            return

        # Mode de chasse géo du concours : 'dept' | 'dept_dxcc' | 'dxcc' | 'other'
        # -> l'onglet bascule entre chasse aux DÉPARTEMENTS et chasse aux PAYS.
        if path == '/contest/geo_mode':
            import logx_scoring as sc
            from urllib.parse import parse_qs, urlparse
            cfg_snap = self._cfg_snapshot()
            cid = (parse_qs(urlparse(self.path).query).get('contest') or
                   [cfg_snap.get('contest', '')])[0]
            self._json({'contest': cid, 'mode': sc.contest_geo_mode(cid)})
            return

        # Chasse aux PAYS (DXCC) — variante internationale de la chasse aux dépts
        if path == '/data/countries_worked':
            import logx_countries as co
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            self._json(co.countries_progress(log_copy, cfg_scope_id(cfg_snap)))
            return
        if path == '/countries/targets':
            import logx_countries as co
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            self._json(co.country_targets(
                log_copy, cfg_scope_id(cfg_snap), _spots_from_caches()))
            return

        # DXpeditions annoncées (NG3K ADXO) — chaque entrée annotée 'worked'
        # selon les pays DXCC déjà travaillés (portée active), pour repérer
        # d'un coup d'œil les expéditions vers un pays réellement nouveau.
        if path == '/data/dxpeditions':
            import logx_dxpeditions as dxp
            import logx_countries as co
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            progress = co.countries_progress(log_copy, cfg_scope_id(cfg_snap))
            worked_names = {x['country'] for grp in progress['by_continent'].values()
                            for x in grp if x['worked']}
            self._json({'expeditions': dxp.fetch_dxpeditions(worked_names)})
            return

        # Balises NCDXF/IBP : quelle balise émet MAINTENANT sur chaque bande
        # (+ distance/azimut depuis le locator) — calcul pur, pas de réseau.
        if path == '/beacons/now':
            import logx_beacons as beacons
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            out = beacons.beacons_now()
            from logx_utils import bearing, cardinal
            for b in out:
                bll = locator_to_latlon(b['locator'])
                if my_ll[0] is not None and bll[0] is not None:
                    b['dist_km'] = haversine(my_ll[0], my_ll[1], bll[0], bll[1])
                    deg = bearing(my_ll[0], my_ll[1], bll[0], bll[1])
                    b['bearing'] = deg
                    b['cardinal'] = cardinal(deg)
            self._json({'beacons': out})
            return

        # PSK Reporter : où mon signal a été décodé (carte d'ouverture propag)
        if path == '/data/heard_where':
            import logx_psk as psk
            cfg_snap = self._cfg_snapshot()
            call = (cfg_snap.get('callsign_contest') or cfg_snap.get('callsign') or '')
            self._json(psk.heard_where(call, cfg_snap.get('locator', '')))
            return

        # Météo du point haut (open-meteo, sans clé) — sécurité matériel /P
        if path == '/data/weather':
            import logx_weather as weather
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            self._json(weather.get_weather(my_ll[0], my_ll[1]))
            return

        # Prévision tropo (ducting) — gradient de réfractivité (open-meteo niveaux)
        if path == '/data/tropo':
            import logx_tropo as tropo
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            self._json(tropo.tropo_forecast(my_ll[0], my_ll[1]))
            return

        # Calendrier météores (Meteor Scatter VHF) — déterministe, pas de réseau
        if path == '/data/meteors':
            import logx_meteors as met
            self._json(met.ms_quality())
            return

        # Annuaire de récepteurs WebSDR distants — liste statique, pas de réseau
        if path == '/data/websdr':
            import logx_websdr as websdr
            self._json({'receivers': websdr.list_websdr()})
            return

        # Spots d'activateurs POTA en direct (api.pota.app, cache 90 s)
        if path == '/data/pota_spots':
            import logx_pota as pota
            self._json({'spots': pota.fetch_pota_spots()})
            return

        # Mise à jour logicielle : dernière release GitHub connue (cache 6h,
        # jamais d'appel réseau dans ce thread — voir logx_update.py).
        if path == '/app/update_check':
            import logx_update as upd
            self._json(upd.get_cached_check())
            return

        # Progression du téléchargement en cours (idle/downloading/done/error)
        if path == '/app/update_status':
            import logx_update as upd
            self._json(upd.get_download_status())
            return

        # Spots d'activateurs SOTA en direct (api2.sota.org.uk, cache 60 s)
        if path == '/data/sota_spots':
            import logx_sota as sota
            self._json({'spots': sota.fetch_sota_spots()})
            return

        # Auto-spot SOTA : état de la connexion SOTA SSO (clientId configuré,
        # jeton présent, case d'approbation IA cochée — voir logx_sota_spot.py).
        if path == '/sota/status':
            import logx_sota_spot as sotaspot
            self._json(sotaspot.status(self._cfg_snapshot()))
            return

        # Auto-spot SOTA : lance la connexion SOTA SSO (Authorization Code +
        # PKCE) — ouvert dans un nouvel onglet par le bouton « Se connecter à
        # SOTA » (CONFIG), redirige vers le vrai serveur SSO SOTA.
        if path == '/sota/oauth/start':
            import logx_sota_spot as sotaspot
            url, err = sotaspot.build_authorize_url(self._cfg_snapshot())
            if not url:
                self._json({'ok': False, 'error': err}, 400)
                return
            self._redirect(url)
            return

        # Auto-spot SOTA : callback de retour depuis SOTA SSO (redirect_uri
        # enregistré = ce serveur local, voir SOTA_REDIRECT_URI). Échange le
        # code contre un jeton puis affiche une page de confirmation minimale.
        if path == '/sota/oauth/callback':
            import logx_sota_spot as sotaspot
            from urllib.parse import parse_qs, urlparse
            qp = parse_qs(urlparse(self.path).query)
            code = (qp.get('code') or [''])[0]
            state = (qp.get('state') or [''])[0]
            sso_error = (qp.get('error_description') or qp.get('error') or [''])[0]
            if sso_error and not code:
                ok, msg = False, f'SOTA SSO : {sso_error}'
            else:
                ok, msg = sotaspot.handle_oauth_callback(code, state, self._cfg_snapshot())
            title = 'Connexion SOTA réussie' if ok else 'Échec de la connexion SOTA'
            color = '#2ea043' if ok else '#f85149'
            # Échappement HTML : `msg` peut reprendre error_description, un
            # paramètre de requête fourni par l'appelant du callback (en
            # pratique SOTA SSO, mais rien n'empêche un autre appel local) —
            # jamais interpolé tel quel dans la page.
            safe_msg = html.escape(msg)
            page = (f'<!doctype html><html lang="fr"><head><meta charset="utf-8">'
                    f'<title>{html.escape(title)}</title></head>'
                    f'<body style="background:#0d1117;color:#e6edf3;font-family:Arial,sans-serif;'
                    f'display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0">'
                    f'<div style="text-align:center;max-width:420px;padding:24px">'
                    f'<h2 style="color:{color}">{html.escape(title)}</h2><p>{safe_msg}</p>'
                    f'<p style="color:#8b949e;font-size:13px">Tu peux fermer cet onglet et revenir à CONFIG.</p>'
                    f'</div></body></html>')
            self._raw(200, 'text/html; charset=utf-8', page.encode('utf-8'))
            return

        # Spots d'activateurs WWFF en direct (spots.wwff.co, cache 60 s)
        if path == '/data/wwff_spots':
            import logx_wwff as wwff
            self._json({'spots': wwff.fetch_wwff_spots()})
            return

        # Spots IOTA en direct : PAS une source réseau dédiée (aucune fiable,
        # cf. logx_iota.py), mais les références IOTA reconnues dans les
        # commentaires des spots cluster déjà en cache — aucun fetch ici.
        if path == '/data/iota_spots':
            import logx_iota as iota
            self._json({'spots': iota.spots_from_clusters(_spots_from_caches())})
            return

        # Activations WCA/COTA ANNONCÉES à l'avance (flux RSS wcagroup.org) —
        # PAS des spots confirmés sur l'air, cf. logx_wca.py.
        if path == '/data/wca_planned':
            import logx_wca as wca
            self._json({'items': wca.fetch_planned_activations()})
            return

        # Recherche dans la base de références du programme d'activation en
        # cours (POTA/SOTA/IOTA/WWFF/WCA — code ou nom), pour l'auto-complétion
        # du champ MA RÉFÉRENCE ACTIVÉE. Jamais bloquant : renvoie [] tant que
        # la base (téléchargée en tâche de fond au premier appel) n'est pas prête.
        if path.startswith('/activation_db/search'):
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            adapter = _activation_db_adapter((qs.get('program') or [''])[0])
            if not adapter:
                self._json({'results': [], 'status': {'ready': False, 'error': 'programme inconnu'}})
                return
            q = (qs.get('q') or [''])[0]
            self._json({'results': adapter['search'](q), 'status': adapter['status']()})
            return

        # Référence exacte -> détails (validation de MA RÉFÉRENCE ACTIVÉE contre
        # la vraie base, au-delà de la simple vérification de FORMAT déjà faite
        # par logx_activation.py).
        if path.startswith('/activation_db/lookup'):
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            adapter = _activation_db_adapter((qs.get('program') or [''])[0])
            if not adapter:
                self._json({'entry': None, 'status': {'ready': False, 'error': 'programme inconnu'}})
                return
            ref = (qs.get('ref') or [''])[0]
            self._json({'entry': adapter['lookup'](ref), 'status': adapter['status']()})
            return

        # Références les plus proches d'un point (par défaut : le locator de la
        # station) — le service que rend sotamaps.org (Range Calculator) pour
        # SOTA, généralisé aux autres programmes qui ont des coordonnées GPS
        # (pas WCA : sa source n'en fournit pas). Construit directement sur la
        # base déjà en mémoire, sans dépendance réseau tierce supplémentaire.
        if path.startswith('/activation_db/nearby'):
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            adapter = _activation_db_adapter((qs.get('program') or [''])[0])
            if not adapter or not adapter['nearby']:
                self._json({'entries': [], 'status': (adapter['status']() if adapter else {'ready': False})})
                return
            lat_q, lon_q = (qs.get('lat') or [''])[0], (qs.get('lon') or [''])[0]
            if lat_q and lon_q:
                lat, lon = lat_q, lon_q
            else:
                cfg_snap = self._cfg_snapshot()
                lat, lon = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            max_km = float((qs.get('max_km') or ['100'])[0])
            self._json({'entries': adapter['nearby'](lat, lon, max_km=max_km),
                        'status': adapter['status']()})
            return

        # État d'une analyse IA serveur (pour la reprise après changement de page)
        if path.startswith('/agent/analyze/state'):
            from urllib.parse import parse_qs, urlparse
            aid = (parse_qs(urlparse(self.path).query).get('id') or [''])[0]
            with _agent_lock:
                a = dict(_agent_analyses.get(aid) or {'status': 'unknown'})
            a['id'] = aid
            self._json(a)
            return

        # Ouvertures par région depuis le QTH (probabilité par bande). ?region=EU
        # (défaut : survol de toutes les régions).
        if path.startswith('/data/openings'):
            from urllib.parse import parse_qs, urlparse
            import logx_paths as paths
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            if my_ll[0] is None:
                self._json({'ok': False, 'error': 'Locator station non défini'})
                return
            try:
                from logx_clusters import get_solar_cached, get_muf_cached
                solar = {'solar': get_solar_cached() or {},
                         'muf': get_muf_cached(my_ll[0], my_ll[1])}
            except Exception:
                solar = {}
            region = (parse_qs(urlparse(self.path).query).get('region') or [''])[0].upper()
            if region and region in paths.REGIONS:
                self._json({'ok': True, 'detail': paths.path_openings(my_ll[0], my_ll[1], region, solar=solar)})
            else:
                self._json({'ok': True, 'regions': paths.all_regions(my_ll[0], my_ll[1], solar=solar)})
            return

        # Widget Time of Day : jour/nuit HOME vs DX (?dx=<locator> optionnel,
        # ex. locator de la station en cours de saisie dans le logbook).
        if path.startswith('/data/timeofday'):
            from urllib.parse import parse_qs, urlparse
            import logx_paths as paths
            cfg_snap = self._cfg_snapshot()
            dx_locator = (parse_qs(urlparse(self.path).query).get('dx') or [''])[0]
            self._json(paths.time_of_day_state(cfg_snap.get('locator', '') or 'JN15XC', dx_locator))
            return

        # Carte de propagation mondiale (grille colorée) pour la surcouche carte IA.
        # ?band=best|14|7… & ?hour=0..23 (décalage horaire depuis maintenant).
        if path.startswith('/data/propmap'):
            from urllib.parse import parse_qs, urlparse
            import logx_paths as paths
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            if my_ll[0] is None:
                self._json({'ok': False, 'error': 'Locator station non défini'})
                return
            qp = parse_qs(urlparse(self.path).query)
            band = (qp.get('band') or ['best'])[0]
            try:
                hour = max(0, min(24, int((qp.get('hour') or ['0'])[0])))
            except ValueError:
                hour = 0
            try:
                from logx_clusters import get_solar_cached, get_muf_cached
                solar = {'solar': get_solar_cached() or {}, 'muf': get_muf_cached(my_ll[0], my_ll[1])}
            except Exception:
                solar = {}
            when = datetime.datetime.utcnow() + datetime.timedelta(hours=hour)
            cells = paths.prop_grid(my_ll[0], my_ll[1], band, when, solar, step=15)
            self._json({'ok': True, 'band': band, 'hour': hour,
                        'when_utc': when.strftime('%H:%M'), 'step': 15,
                        'my': {'lat': my_ll[0], 'lon': my_ll[1]}, 'cells': cells})
            return

        # Écran mural d'expédition : agrégation du log commun en temps réel.
        # Config PUBLIQUE (whitelist stricte, AUCUN secret) — permet à chaque
        # poste d'expédition d'hériter du concours, de la station et du mode
        # expédition partagés, sans jamais exposer mots de passe / clés API.
        if path == '/config':
            cfg_snap = self._cfg_snapshot()
            safe = {k: cfg_snap.get(k, '') for k in (
                'callsign', 'callsign_contest', 'locator', 'contest',
                'expedition_mode', 'clublog_live', 'cluster_spot_enabled',
                'activation_program', 'my_activation_ref',
                'city', 'altitude', 'ui_theme')}  # ni l'un ni l'autre n'est un secret
            self._json(safe)
            return

        # config.json est un fichier de config avancé (structure imbriquée
        # station/contest lue par la page mobile) qui peut AUSSI contenir une
        # section 'server' avec auth_token/debug. On le sert par cette route en
        # retirant systématiquement 'server' — le fichier brut, lui, est bloqué
        # au service statique (_NEVER_SERVE) pour ne jamais fuiter le jeton.
        if path == '/config.json':
            data = {}
            try:
                with open('config.json', encoding='utf-8') as f:
                    data = json.load(f) or {}
            except Exception:
                data = {}
            if isinstance(data, dict):
                data.pop('server', None)
            self._json(data)
            return

        if path == '/data/wall':
            import logx_wall as wall
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            self._json(wall.wall_state(log_copy, cfg_snap))
            return

        # RBN : où mon signal CW est entendu (skimmers Reverse Beacon Network)
        if path == '/data/rbn':
            import logx_rbn as rbn
            cfg_snap = self._cfg_snapshot()
            call = (cfg_snap.get('callsign_contest') or cfg_snap.get('callsign') or '')
            self._json(rbn.where_heard(call))
            return

        # État scoreboard / sauvegarde (config + dernière synchro)
        if path == '/scoreboard/status':
            import logx_scoreboard as sb
            self._json(sb.status(self._cfg_snapshot()))
            return
        if path == '/backup/status':
            import logx_backup as bk
            self._json(bk.status(self._cfg_snapshot()))
            return
        if path == '/cloudsync/status':
            import logx_cloudsync as cs
            self._json(cs.status(self._cfg_snapshot()))
            return

        # Propagation : indices solaires N0NBH + MUF réelle KC2G (caches 15 min,
        # lecture seule ici — le rafraîchissement réseau se fait en tâche de fond).
        if path == '/data/propagation':
            from logx_clusters import get_solar_cached, get_muf_cached
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            solar = get_solar_cached()
            muf = get_muf_cached(my_ll[0], my_ll[1]) if my_ll[0] else get_muf_cached()
            self._json({'solar': solar, 'muf': muf})
            return

        # Need list structurée : les spots du dernier refresh évalués au barème
        # du concours actif et triés par valeur (nouveaux mults en tête) —
        # AUCUN re-fetch réseau, aucune IA : lecture des caches, pollable.
        if path == '/data/spots_ranked':
            from logx_scoring import build_ranked_spots
            import logx_alerts as alerts
            cfg_snap = self._cfg_snapshot()
            ranked, meta = build_ranked_spots({}, _spots_from_caches(), cfg_snap)
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15AA')
            # Toutes les correspondances (pas seulement les 40 affichées) : une
            # règle d'alerte doit pouvoir signaler un spot même hors du top
            # valeur affiché — les critères d'alerte ne sont pas ceux du score.
            full_entries = []
            for s in ranked:
                sc = s.get('scoring', {})
                dx_ll = locator_to_latlon(s.get('locator', ''))
                entry = {
                    'call': s.get('call', ''), 'band': s.get('band', ''),
                    'freq': s.get('freq', ''), 'locator': s.get('locator', ''),
                    'lat': s.get('lat'), 'lon': s.get('lon'),
                    'dist_km': s.get('dist_km', 0), 'time': s.get('time', ''),
                    'source': s.get('source', ''), 'info': s.get('info', ''),
                    'points': sc.get('direct_pts', 0),
                    'new_mult': bool(sc.get('new_mult')),
                    'mult_type': sc.get('mult_type', ''),
                    'priority': s.get('priority', 5),
                    'value': s.get('value_total', 0),
                    'already_done': bool(sc.get('already_done')),
                    'explanation': sc.get('explanation', ''),
                    # Pour le constructeur de règles d'alerte (pays/continent/zone CQ)
                    'dx_country': sc.get('dx_country', ''),
                    'dx_continent': sc.get('dx_continent', ''),
                    'dx_cq_zone': sc.get('dx_cq_zone'),
                }
                if my_ll[0] and dx_ll[0]:
                    from logx_utils import bearing, cardinal
                    deg = bearing(my_ll[0], my_ll[1], dx_ll[0], dx_ll[1])
                    entry['bearing'] = deg
                    entry['cardinal'] = cardinal(deg)
                full_entries.append(entry)
            alert_matches = alerts.check_alerts(cfg_snap.get('alert_rules'), full_entries)
            self._json({'spots': full_entries[:40], 'meta': meta, 'alert_matches': alert_matches})
            return

        # Pont WSJT-X (FT8/FT4) : état de la liaison UDP — pollé par le logbook
        if path == '/wsjtx/state':
            self._json(_wsjtx_state_dict(self._cfg_snapshot()))
            return

        # Réseau ADIF générique (N1MM/DXLog) : état de l'écoute — pollé par CONFIG
        if path == '/adifnet/state':
            import logx_adifnet as adifnet
            settings = adifnet.adifnet_settings(self._cfg_snapshot())
            if settings['listen']:
                # Démarrage à chaud (idempotent)
                adifnet.start_listener(
                    get_cfg=lambda: dict(current_config),
                    add_qso=lambda q: add_qso_to_log(q, force=False)[0],
                    port=settings['port'])
            st = adifnet.current_status()
            st.update(settings)
            self._json(st)
            return

        # Keyer vocal : périphériques audio de sortie + voix TTS installées
        # (pour les select de CONFIG) — appelé une fois, jamais en polling.
        if path == '/voicekeyer/devices':
            import logx_voicekeyer as vk
            self._json({'devices': vk.list_output_devices(), 'voices': vk.list_tts_voices()})
            return

        # Radio CAT (natif / TCI / rigctld / flrig) : état courant — pollé par le logbook
        if path == '/rig/state':
            self._json(_rig_state_dict(self._cfg_snapshot()))
            return

        # Amplificateur HF (Elecraft KPA500/1500, Icom PW-1/PW2, SPE Expert) :
        # état courant (puissance/SWR/défaut/operate) — pollé par le logbook.
        if path == '/amp/state':
            self._json(_amp_state_dict(self._cfg_snapshot()))
            return

        # Radio CAT native : ports série disponibles (pour le sélecteur CONFIG)
        if path == '/rig/ports':
            import logx_cat as cat
            self._json({'ports': cat.list_ports()})
            return

        # Rotor d'antenne (rotctld) : position courante — pollée par le logbook
        if path == '/rotor/state':
            self._json(_rotor_state_dict(self._cfg_snapshot()))
            return

        # État matériel groupé : rig+amp+wsjtx+rotor en UNE requête plutôt que 4
        # séparées. Le logbook pollait chacun individuellement à cadence rapide
        # (3-4s) — jusqu'à 4 connexions/cycle pour de petits payloads, un coût
        # non négligeable quand un antivirus inspecte chaque connexion locale.
        # Les 4 endpoints individuels restent disponibles tels quels (utilisés
        # aussi par logx_propagation.html/logx_scope.html).
        if path == '/hardware/state':
            cfg_snap = self._cfg_snapshot()
            self._json({
                'rig': _rig_state_dict(cfg_snap),
                'amp': _amp_state_dict(cfg_snap),
                'wsjtx': _wsjtx_state_dict(cfg_snap),
                'rotor': _rotor_state_dict(cfg_snap),
            })
            return

        # Liste des archives de concours (dossiers permanents)
        if path == '/log/archives':
            import logx_archive as arch
            self._json({'archives': arch.list_archives()})
            return

        # QTC (WAE) : total et détail par station
        if path.startswith('/qtc/list'):
            from logx_storage import qtc_log, qtc_lock, qtc_total
            cfg_snap = self._cfg_snapshot()
            scope_id = cfg_scope_id(cfg_snap)
            with qtc_lock:
                entries = _scope_filtered(qtc_log, cfg_snap)
            self._json({'total': qtc_total(scope_id), 'entries': entries[-50:]})
            return

        # Exports du log partagé — Cabrillo v3 et ADIF 3
        if path in ('/log/export/cabrillo', '/log/export/adif'):
            import logx_export as export
            cfg_snap = self._cfg_snapshot()
            contest_id = cfg_snap.get('contest', '')
            # Portée QSO (contest+année) : sans elle, un Cabrillo/ADIF exporté
            # pour CE concours embarquait aussi tout QSO non tagué (import
            # générique, log perso jamais nettoyé) — inacceptable pour un
            # fichier de soumission de concours.
            with log_lock:
                qsos = _scope_filtered(shared_log, cfg_snap)
            call = (cfg_snap.get('callsign_contest') or cfg_snap.get('callsign')
                    or 'LOG').upper().replace('/', '-')
            if path.endswith('cabrillo'):
                from logx_storage import qtc_log, qtc_lock
                cdef = CONTEST_DEFINITIONS.get(contest_id, {})
                with qtc_lock:
                    qtc_series = _scope_filtered(qtc_log, cfg_snap)
                body = export.build_cabrillo(qsos, cdef, cfg_snap, qtc_series).encode('utf-8')
                fname = f"{call}_{contest_id or 'ALL'}.cbr"
            else:
                body = export.build_adif(qsos, cfg_snap).encode('utf-8')
                fname = f"{call}_{contest_id or 'ALL'}.adi"
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Content-Disposition', f'attachment; filename="{fname}"')
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return

        # Status du système de mise à jour
        if path == '/data/rules_status':
            self._json({
                'year': rules.rules_db.get('year', CURRENT_YEAR),
                'last_update': rules.rules_db.get('last_update', ''),
                'alerts': rules.rules_db.get('alerts', []),
                'contests_count': len(CONTEST_DEFINITIONS),
                'current_year': CURRENT_YEAR,
                'next_update': f"Automatique au 1er janvier {CURRENT_YEAR+1}",
            })
            return

        # Mot de passe d'accès optionnel : état courant (page CONFIG et
        # formulaire de connexion) — jamais le hash, un simple booléen.
        if path == '/auth/status':
            self._json({'enabled': _access_password_enabled(),
                        'authorized': self._client_authorized()})
            return

        # Page de connexion : SEULE porte d'entrée du jeton d'écriture quand un
        # mot de passe est configuré (voir _access_password_enabled). Reste
        # joignable même protection active — elle ne fuite aucune donnée.
        if path == '/auth/login':
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            self._serve_login_page(qs.get('next', ['/'])[0])
            return

        if path in ('/', ''):
            path = '/logx_configuration.html'

        # Anciennes URL (avant le renommage logx_*) : on continue de
        # les servir pour ne casser ni favoris ni habitudes de l'équipe.
        LEGACY_PAGES = {
            '/configuration.html': '/logx_configuration.html',
            '/logbook.html': '/logx_logbook.html',
            '/calendrier.html': '/logx_calendrier.html',
            '/radiocontest.html': '/logx_carte.html',
            '/rallye-vhf-terrain.html': '/logx_mobile.html',
            '/logx_terrain.html': '/logx_mobile.html',
            '/statusbar.js': '/logx_statusbar.js',
        }
        path = LEGACY_PAGES.get(path, path)

        filepath = self._resolve(path)
        if filepath and os.path.isfile(filepath):
            pw_enabled = _access_password_enabled()
            # Mot de passe configuré : une page HTML ne se sert plus toute
            # seule le jeton d'écriture — sans cookie déjà valide, direction
            # /auth/login au lieu du contenu demandé. Ne s'applique qu'aux
            # pages HTML (le CSS/JS d'une page déjà affichée doit continuer de
            # charger normalement, ces fichiers n'ont jamais posé le cookie).
            if filepath.endswith('.html') and pw_enabled and not self._client_authorized():
                from urllib.parse import quote
                self._redirect('/auth/login?next=' + quote(path, safe=''))
                return
            with open(filepath, 'rb') as f:
                body = f.read()
            self.send_response(200)
            ct = 'text/html; charset=utf-8'
            if filepath.endswith('.js'):   ct = 'application/javascript'
            if filepath.endswith('.css'):  ct = 'text/css'
            if filepath.endswith('.json'): ct = 'application/json'
            if filepath.endswith('.svg'):  ct = 'image/svg+xml'
            if filepath.endswith('.png'):  ct = 'image/png'
            if filepath.endswith(('.jpg', '.jpeg')): ct = 'image/jpeg'
            if filepath.endswith('.gif'):  ct = 'image/gif'
            if filepath.endswith('.webp'): ct = 'image/webp'
            if filepath.endswith('.pdf'):  ct = 'application/pdf'
            if filepath.endswith('.webmanifest'): ct = 'application/manifest+json'
            if ct.startswith('text/html') and not pw_enabled:
                # Distribution automatique SEULEMENT si aucun mot de passe n'est
                # configuré (comportement historique, LAN de confiance) — sinon
                # seule /auth/login (mot de passe vérifié) pose ce cookie
                # (SameSite=Strict : jamais envoyé depuis un site tiers).
                self.send_header('Set-Cookie',
                                 f'rc_token={AUTH_TOKEN}; Path=/; SameSite=Strict; HttpOnly')
            self.send_header('Content-Type', ct)
            # Content-Length explicite : sans lui (HTTP/1.0 par défaut chez
            # BaseHTTPRequestHandler, pas de chunked non plus), le client n'a
            # aucun moyen fiable de savoir où s'arrête le corps de la réponse
            # — un proxy/antivirus/outil d'inspection réseau local (déjà vu
            # avec Avast sur ce poste) peut alors couper la connexion en
            # plein milieu d'un gros fichier (ex. logx_logbook.js).
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        else:
            self._raw(404, None, None)

    def do_POST(self):
        global current_config, chat_seq, browser_spots_cache, browser_spots_ts
        # /auth/login est LA route qui pose rc_token quand un mot de passe est
        # configuré : elle doit rester joignable SANS jeton (sinon personne ne
        # pourrait jamais se connecter) — c'est le mot de passe lui-même qui
        # est vérifié en temps constant (voir _verify_access_password).
        if self.path.split('?')[0] == '/auth/login':
            self._handle_auth_login_post()
            return
        # Toutes les autres routes POST écrivent ou appellent l'IA : token exigé.
        if not self._require_auth():
            return
        # Plafond de taille du corps : un client malveillant du LAN pouvait
        # envoyer plusieurs Go et faire gonfler la mémoire jusqu'au crash.
        # 32 Mo couvre largement un gros import ADIF ; au-delà on refuse.
        MAX_BODY = 32 * 1024 * 1024
        try:
            length = int(self.headers.get('Content-Length', 0) or 0)
        except (TypeError, ValueError):
            length = 0
        if length < 0 or length > MAX_BODY:
            self._json({'error': 'Corps de requête trop volumineux'}, 413)
            return
        body = self.rfile.read(length)

        # Réception spots cluster depuis le navigateur (HTTPS bloqué côté serveur).
        # NB : cette route vivait dans do_GET avec un test "method == 'POST'"
        # jamais vrai (les POST n'atteignent pas do_GET) — le push navigateur
        # ne fonctionnait donc jamais. Corrigé lors du découpage en modules.
        if self.path == '/data/spots':
            try:
                spots = json.loads(body)
                if isinstance(spots, list):
                    with browser_spots_lock:
                        browser_spots_cache = spots[:200]
                        browser_spots_ts = time.time()
                    print(f"[BROWSER-SPOTS] {len(spots)} spots reçus du navigateur")
                    self._json({'ok': True, 'count': len(spots)})
                else:
                    self._json({'ok': False, 'error': 'expected array'}, 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Upload du log vers un service QSL (eQSL / ClubLog / QRZCQ / HRDLog).
        # Le point d'entrée est unifié côté qsl.upload_log — ajouter un
        # service futur ne touche plus à ce handler, juste à logx_qsl.py.
        # Identifiants générés/lus côté serveur, jamais transmis au client.
        if self.path == '/qsl/upload':
            try:
                payload = json.loads(body) if body else {}
                service = (payload.get('service') or '').lower()
                cfg = self._cfg_snapshot()
                contest_id = payload.get('contest', cfg.get('contest', ''))
                if 'contest' in payload:
                    # Portée explicitement demandée par le client : honorée
                    # telle quelle, même en mode simple (un envoi QSL explicite
                    # prime sur le mode d'usage courant).
                    scope_id = active_scope_id({**cfg, 'contest': contest_id})
                else:
                    scope_id = cfg_scope_id(cfg)
                with log_lock:
                    qsos = [q for q in shared_log
                            if not scope_id or qso_scope_id(q) == scope_id]
                if not qsos:
                    self._json({'ok': False, 'error': 'Aucun QSO à envoyer'}, 400)
                    return
                import logx_qsl as qsl
                res = qsl.upload_log(cfg, service, qsos)
                res['qso_count'] = len(qsos)
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Upload d'un scan de carte QSL PAPIER attaché à un QSO (multipart,
        # champs qso_id + file) — ne pas confondre avec /qsl/upload ci-dessus
        # (services de confirmation en ligne). Stockage simple sur disque
        # (logx_qsl_scan.SCANS_DIR), la référence est posée sur le QSO lui-même
        # (champ qsl_scan) pour être servie par le service de fichiers statique
        # habituel (GET /qsl_scans/xxx, voir Handler._resolve).
        if self.path == '/qsl_scan/upload':
            try:
                fields, files = _parse_multipart_form(body, self.headers.get('Content-Type', ''))
                qso_id_raw = fields.get('qso_id')
                upload = files.get('file')
                if not qso_id_raw or not upload:
                    self._json({'ok': False, 'error': 'qso_id ou fichier manquant'}, 400)
                    return
                qso_id = int(qso_id_raw)
                # Pré-check SOUS verrou, mais séparé de la mutation finale (juste une
                # existence, pas un lire-modifier-écrire) : sert seulement à éviter
                # d'écrire un fichier sur disque pour un id manifestement inexistant.
                # save_scan() (I/O disque, pas d'accès à shared_log) peut rester hors
                # verrou — seule la mutation finale ci-dessous doit être atomique.
                with log_lock:
                    if not any(q.get('id') == qso_id for q in shared_log):
                        self._json({'ok': False, 'error': 'QSO introuvable'}, 404)
                        return
                import logx_qsl_scan as qslscan
                rel_path = qslscan.save_scan(qso_id, upload['filename'], upload['data'])
                # Récupération de la référence + assignation qsl_scan + stamp_qso_version
                # DANS LE MÊME bloc with log_lock (comme /log/update) : le QSO a pu être
                # supprimé ou remplacé (shared_log[i]=...) entre le pré-check ci-dessus
                # et maintenant, donc on le retrouve et on le mute d'un seul geste,
                # jamais avec le verrou relâché entre les deux.
                old_path = None
                target = None
                with log_lock:
                    target = next((q for q in shared_log if q.get('id') == qso_id), None)
                    if target is not None:
                        old_path = target.get('qsl_scan')
                        target['qsl_scan'] = rel_path   # dict déjà référencé dans shared_log
                        bump_log_version()
                        stamp_qso_version(target)   # voir /log/list?since=
                if target is None:
                    qslscan.delete_scan(rel_path)   # QSO disparu entretemps : pas de fichier orphelin
                    self._json({'ok': False, 'error': 'QSO introuvable'}, 404)
                    return
                save_log_to_disk()
                if old_path and old_path != rel_path:
                    qslscan.delete_scan(old_path)   # ancien scan remplacé
                self._json({'ok': True, 'qsl_scan': rel_path})
            except ValueError as e:
                self._json({'ok': False, 'error': str(e)}, 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Publication du score sur le scoreboard en direct (contestonlinescore).
        if self.path == '/scoreboard/push':
            try:
                import logx_scoreboard as sb
                with log_lock:
                    log_copy = list(shared_log)
                self._json(sb.push(self._cfg_snapshot(), log_copy))
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Sauvegarde manuelle immédiate vers le dossier configuré (cloud/NAS).
        if self.path == '/backup/now':
            try:
                import logx_backup as bk
                with log_lock:
                    log_copy = list(shared_log)
                res = bk.run_backup(self._cfg_snapshot(), log_copy)
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Cloud Sync manuel immédiat (voir aussi le thread de fond périodique).
        if self.path == '/cloudsync/now':
            try:
                import logx_cloudsync as cs
                # Correctif M6 : le client envoie désormais les valeurs
                # ACTUELLEMENT affichées (cloudsync_mode/cloudsync_folder) —
                # elles surchargent la dernière config sauvegardée, pour ne
                # pas synchroniser avec des réglages déjà obsolètes si
                # l'utilisateur vient de les modifier sans cliquer SAUVEGARDER.
                try:
                    payload = json.loads(body) if body else {}
                except Exception:
                    payload = {}
                cfg_now = self._cfg_snapshot()
                if 'cloudsync_mode' in payload:
                    cfg_now['cloudsync_mode'] = payload['cloudsync_mode']
                if 'cloudsync_folder' in payload:
                    cfg_now['cloudsync_folder'] = payload['cloudsync_folder']
                with log_lock:
                    log_copy = list(shared_log)
                res = cs.sync_now(cfg_now, log_copy)
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Import des confirmations QSL (LoTW) → marque les QSO « confirmé ».
        if self.path == '/qsl/sync':
            try:
                payload = json.loads(body) if body else {}
                import logx_qsl as qsl
                res = qsl.sync_lotw(self._cfg_snapshot(), since=payload.get('since'))
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # QRZ Logbook : vérifie la clé API (ACTION=STATUS) sans insérer de QSO
        # factice — bouton « Tester la connexion » (CONFIG → QSL), même
        # logique que /amp/test.
        if self.path == '/qrz_logbook/test':
            try:
                import logx_qrz_push as qrz_push
                res = qrz_push.test_connection(self._cfg_snapshot())
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # ── Phase 3 : analyse IA d'un règlement ──────────────────────────────
        # Télécharge le règlement (ou reçoit son texte), l'envoie à l'IA
        # configurée, valide la proposition contre le schema et le moteur.
        # NE SAUVEGARDE RIEN : la relecture humaine passe par /rules/save_definition.
        if self.path == '/rules/analyze':
            try:
                payload = json.loads(body) if body else {}
                result = analyze_rules(
                    url=payload.get('url', ''),
                    rules_text=payload.get('text', ''),
                    contest_name=payload.get('name', ''),
                    cfg=self._cfg_snapshot(),
                )
                self._json(result, 200 if result.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Enregistrement d'une définition APRÈS relecture/correction humaine
        if self.path == '/rules/save_definition':
            try:
                payload = json.loads(body)
                cid = str(payload.get('id', '')).strip().upper()
                definition = payload.get('definition')
                if not cid or not isinstance(definition, dict):
                    self._json({'ok': False, 'error': "champs 'id' et 'definition' requis"}, 400)
                    return
                errors = validate_definition(definition, cid)
                if errors:
                    self._json({'ok': False, 'error': 'Définition non conforme',
                                'validation_errors': errors}, 400)
                    return
                ok, msg = save_custom_contest(cid, definition, meta={
                    'validated_at': datetime.datetime.utcnow().isoformat(),
                    'source_url': payload.get('source_url', ''),
                    'ai_confidence': payload.get('confidence', ''),
                })
                self._json({'ok': ok, 'message': msg}, 200 if ok else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Import de concours validés partagés par une autre station.
        # Chaque définition est re-validée ici — on n'importe jamais à l'aveugle.
        if self.path == '/rules/import_custom':
            try:
                payload = json.loads(body)
                contests = payload.get('contests', payload)
                if not isinstance(contests, dict) or not contests:
                    self._json({'ok': False, 'error': "Aucun concours dans le fichier "
                                "(clé 'contests' attendue)"}, 400)
                    return
                imported, updated, skipped, errors = [], [], [], {}
                for cid, entry in contests.items():
                    cid = str(cid).upper()
                    definition = entry.get('definition', entry) if isinstance(entry, dict) else None
                    errs = validate_definition(definition, cid)
                    if errs:
                        errors[cid] = errs
                        continue
                    if cid in CONTEST_DEFINITIONS and cid not in CUSTOM_CONTEST_IDS:
                        skipped.append(cid)  # existe dans la base intégrée
                        continue
                    was_update = cid in CUSTOM_CONTEST_IDS
                    meta = {k: v for k, v in (entry.items() if isinstance(entry, dict) else [])
                            if k != 'definition'}
                    meta['imported_at'] = datetime.datetime.utcnow().isoformat()
                    ok, _ = save_custom_contest(cid, definition, meta=meta)
                    if ok:
                        (updated if was_update else imported).append(cid)
                self._json({'ok': True, 'imported': imported, 'updated': updated,
                            'skipped_builtin': skipped, 'errors': errors})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Suppression d'un concours personnalisé
        if self.path == '/rules/delete_custom':
            try:
                payload = json.loads(body)
                ok, msg = delete_custom_contest(str(payload.get('id', '')).upper())
                self._json({'ok': ok, 'message': msg}, 200 if ok else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Sauvegarde configuration courante (appelé par logx_carte.html au démarrage)
        if self.path == '/config/save':
            try:
                cfg = json.loads(body)
                with config_lock:
                    current_config = cfg
                save_json_atomic(SERVER_CONFIG_FILE, cfg)
                # /log/list filtre désormais par portée (concours+année, voir
                # active_scope_id) : changer de concours/mode d'usage change ce
                # que CETTE portée désigne sans qu'aucun QSO n'ait bougé — sans
                # ce bump, un client dont le ?v= était déjà à jour recevrait
                # 'unchanged' et garderait affiché l'ancien concours jusqu'au
                # prochain vrai QSO ajouté.
                bump_log_version()
                # Idem pour la synchro différentielle (?since=) : aucun QSO
                # n'a été ajouté/modifié/supprimé, seule la portée visible a
                # changé — un delta ('_v' de chaque QSO inchangé) serait vide
                # à tort et laisserait l'ancien concours affiché. mark_hard_reset()
                # force un client avec un ?since= antérieur à repasser par la
                # liste complète, recalculée sous la NOUVELLE portée.
                mark_hard_reset()
                print(f"[CFG] Config reçue : {cfg.get('callsign','')} / {cfg.get('locator','')} / {cfg.get('contest','')}")
                self._json({'ok': True})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Définit/modifie (password non vide) ou désactive (password vide) le
        # mot de passe d'accès — voir _access_password_enabled. Volontairement
        # PAS dans current_config/config/save : ce dernier REMPLACE tout à
        # chaque sauvegarde (silencieuse ou non) — un champ mot de passe vide
        # par défaut dans le formulaire aurait effacé la protection à chaque
        # sauvegarde de n'importe quel autre réglage. Route dédiée, sur le
        # modèle de /ui/theme (ne touche QUE ce qu'elle doit toucher).
        # Nécessite déjà le jeton (comme toute route POST) : cohérent, on ne
        # peut changer ce réglage qu'en étant déjà connecté.
        if self.path == '/auth/set_password':
            try:
                payload = json.loads(body)
                new_pw = str(payload.get('password', ''))
                if new_pw == '':
                    _clear_access_password()
                    self._json({'ok': True, 'enabled': False})
                elif len(new_pw) < 4:
                    self._json({'ok': False,
                               'error': 'Mot de passe trop court (4 caractères minimum)'}, 400)
                else:
                    _set_access_password(new_pw)
                    # _set_access_password vient de tourner AUTH_TOKEN (voir
                    # _rotate_auth_token) : sans reposer immédiatement un
                    # cookie valide, la session qui vient de définir ce mot
                    # de passe se retrouverait elle-même déconnectée par son
                    # propre changement.
                    body_out = json.dumps({'ok': True, 'enabled': True}).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Set-Cookie',
                                     f'rc_token={AUTH_TOKEN}; Path=/; SameSite=Strict; HttpOnly')
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Length', str(len(body_out)))
                    self._cors()
                    self.end_headers()
                    self.wfile.write(body_out)
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Thème jour/nuit : préférence légère partagée entre tous les postes
        # qui ouvrent le lien multi-poste (sinon un poste qui rejoint pour la
        # 1re fois retombe sur le mode nuit par défaut, même si la station
        # principale est en mode jour). Contrairement à /config/save (qui
        # REMPLACE tout current_config), on ne touche QUE cette clé — un
        # poste qui n'a jamais vu le reste de la config ne doit pas pouvoir
        # l'écraser en poussant juste son thème.
        if self.path == '/ui/theme':
            try:
                payload = json.loads(body)
                theme = payload.get('theme')
                if theme not in ('day', 'night'):
                    self._json({'error': 'theme invalide'}, 400)
                    return
                with config_lock:
                    current_config['ui_theme'] = theme
                    snap = dict(current_config)
                save_json_atomic(SERVER_CONFIG_FILE, snap)
                self._json({'ok': True})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Mise à jour logicielle : déclenché par un clic opérateur ("Télécharger
        # et installer"), jamais automatiquement — voir logx_update.py. Ne
        # touche jamais au dossier de données utilisateur, seul l'exécutable
        # est remplacé.
        if self.path == '/app/update_download':
            import logx_update as upd
            check = upd.get_cached_check()
            if not check.get('asset_url'):
                self._json({'error': 'Aucun exécutable disponible pour cette plateforme'}, 400)
                return
            upd.start_download(check['asset_url'])
            self._json({'ok': True})
            return

        if self.path == '/app/update_install':
            import logx_update as upd
            status = upd.get_download_status()
            if status.get('status') != 'done' or not status.get('path'):
                self._json({'error': 'Téléchargement pas terminé'}, 400)
                return
            ok, err = upd.apply_update_and_relaunch(status['path'])
            if not ok:
                self._json({'error': err}, 400)
                return
            self._json({'ok': True, 'restarting': True})
            # Laisse le temps à la réponse HTTP de partir avant de couper le
            # serveur — le script auxiliaire attend déjà la fin de CE
            # processus pour remplacer l'exécutable et le relancer.
            threading.Timer(1.0, lambda: os._exit(0)).start()
            return

        # Radio CAT native/TCI/flrig : test éphémère depuis CONFIG (avant même de
        # sauvegarder) — ouvre, interroge, ferme, ne touche pas au polling.
        if self.path == '/rig/connect_test':
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            if payload.get('mode') == 'tci':
                import logx_tci as tci
                res = tci.test_connection(payload.get('host'), payload.get('port'))
            elif payload.get('mode') == 'rigctld':
                # Correctif H6 : jusqu'ici absent — le mode rigctld tombait dans
                # le "else" natif ci-dessous, qui teste un port SÉRIE (jamais
                # utilisé par rigctld, protocole réseau texte sur rig_host/rig_port).
                import logx_rig as rig
                host = (payload.get('host') or '').strip() or rig.DEFAULT_HOST
                try:
                    port = int(payload.get('port') or rig.DEFAULT_PORT)
                except (TypeError, ValueError):
                    port = rig.DEFAULT_PORT
                res = rig.get_state(host, port)
            elif payload.get('mode') == 'flrig':
                import logx_flrig as flrig
                host = (payload.get('host') or '').strip() or flrig.DEFAULT_HOST
                try:
                    port = int(payload.get('port') or flrig.DEFAULT_PORT)
                except (TypeError, ValueError):
                    port = flrig.DEFAULT_PORT
                res = flrig.test_connection(host, port)
            else:
                import logx_cat as cat
                res = cat.test_connection(payload.get('brand'), payload.get('model'),
                                          payload.get('port'), payload.get('baudrate'))
            self._json(res, 200 if res.get('ok') else 502)
            return

        # Radio CAT : QSY, envoi CW, stop CW — natif/TCI/flrig si configuré, sinon rigctld
        if self.path in ('/rig/qsy', '/rig/cw', '/rig/stop'):
            cfg_snap = self._cfg_snapshot()
            import logx_cat as cat
            cat_settings = cat.cat_settings(cfg_snap)
            native = cat_settings['enabled'] and cat_settings['mode'] == 'native'
            use_tci = cat_settings['enabled'] and cat_settings['mode'] == 'tci'
            use_flrig = cat_settings['enabled'] and cat_settings['mode'] == 'flrig'
            if use_tci:
                import logx_tci as tci
            if use_flrig:
                import logx_flrig as flrig
                flrig_settings = flrig.flrig_settings(cfg_snap)
            if not native and not use_tci and not use_flrig:
                import logx_rig as rig
                settings = rig.rig_settings(cfg_snap)
                if not settings['enabled']:
                    self._json({'ok': False, 'error': 'Radio CAT désactivée — '
                                'active-la dans CONFIG (mode expert, section RADIO)'}, 400)
                    return
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}

            if self.path == '/rig/qsy':
                freq = payload.get('freq_hz') or 0
                if not freq and payload.get('freq_khz'):
                    freq = float(payload['freq_khz']) * 1000
                if not freq:
                    self._json({'ok': False, 'error': 'Fréquence manquante'}, 400)
                    return
                if native:
                    res = cat.set_freq(cfg_snap, int(freq), payload.get('mode'))
                elif use_tci:
                    res = tci.set_freq(cfg_snap, int(freq), payload.get('mode'))
                elif use_flrig:
                    res = flrig.set_freq(flrig_settings['host'], flrig_settings['port'],
                                        int(freq), payload.get('mode'))
                else:
                    res = rig.set_freq(settings['host'], settings['port'], int(freq), payload.get('mode'))
                if res.get('ok'):
                    print(f"[RIG] QSY {int(freq)} Hz {payload.get('mode') or ''}")
            elif native:
                # Keyer CW natif non implémenté (mode natif = pyserial direct,
                # pas de sous-couche keyer) — utiliser rigctld ou TCI pour le CW.
                self._json({'ok': False, 'error': 'Envoi CW non disponible en mode "Natif" — '
                            'bascule en mode "Hamlib rigctld" ou "TCI" pour le keyer CW'}, 400)
                return
            elif use_flrig:
                # flrig n'expose pas de méthode XML-RPC générique d'envoi CW fiable
                # sans montage DTR/RTS supplémentaire (voir logx_flrig.py) — même
                # choix que le mode natif.
                self._json({'ok': False, 'error': 'Envoi CW non disponible en mode "flrig" — '
                            'bascule en mode "Hamlib rigctld" ou "TCI" pour le keyer CW'}, 400)
                return
            elif use_tci:
                if self.path == '/rig/cw':
                    res = tci.send_cw(cfg_snap, str(payload.get('text', ''))[:120])
                    if res.get('ok'):
                        print(f"[RIG] CW (TCI): {str(payload.get('text',''))[:40]}")
                else:
                    res = tci.stop_cw(cfg_snap)
            elif self.path == '/rig/cw':
                res = rig.send_morse(settings['host'], settings['port'], str(payload.get('text', ''))[:120])
                if res.get('ok'):
                    print(f"[RIG] CW: {str(payload.get('text',''))[:40]}")
            else:
                res = rig.stop_morse(settings['host'], settings['port'])
            self._json(res, 200 if res.get('ok') else 502)
            return

        # Keyer vocal dynamique : indicatif/report épelés phonétiquement,
        # synthétisés (TTS hors-ligne) et émis par la radio (PTT via CAT
        # autour de la lecture, quel que soit le mode natif/TCI/rigctld/flrig).
        if self.path == '/rig/voice':
            import logx_voicekeyer as vk
            cfg_snap = self._cfg_snapshot()
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            template = str(payload.get('template', payload.get('text', '')))[:200]
            ctx = {
                'call': payload.get('call', ''), 'mycall': payload.get('mycall', ''),
                'rst_sent': payload.get('rst_sent', ''), 'rst_rcvd': payload.get('rst_rcvd', ''),
                'nr': payload.get('nr', ''),
            }
            text = vk.expand_voice_text(template, ctx)
            res = vk.send_voice_message(cfg_snap, text)
            if res.get('ok'):
                print(f"[RIG] Voix : {text[:60]}")
            self._json(res, 200 if res.get('ok') else 400)
            return

        # Amplificateur HF : bascule standby/operate, changement de bande,
        # acquittement de défaut, mise sous/hors tension à distance, test de
        # connexion éphémère (bouton CONFIG).
        if self.path in ('/amp/operate', '/amp/band', '/amp/clear_fault',
                         '/amp/power', '/amp/test'):
            import logx_amp as amp
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            if self.path == '/amp/test':
                res = amp.test_connection(
                    payload.get('brand', ''), payload.get('port', ''),
                    payload.get('baudrate') or 0, payload.get('civ_addr'))
                self._json(res, 200 if res.get('ok') else 400)
                return
            cfg_snap = self._cfg_snapshot()
            if self.path == '/amp/operate':
                res = amp.set_operate(cfg_snap, bool(payload.get('on')))
            elif self.path == '/amp/band':
                res = amp.set_band(cfg_snap, payload.get('band', ''))
            elif self.path == '/amp/clear_fault':
                res = amp.clear_fault(cfg_snap)
            else:
                res = amp.power_toggle(cfg_snap, bool(payload.get('on')))
            self._json(res, 200 if res.get('ok') else 400)
            return

        # Rotor d'antenne (rotctld) : pointer, stopper
        if self.path in ('/rotor/point', '/rotor/stop'):
            import logx_rotor as rotor
            settings = rotor.rotor_settings(self._cfg_snapshot())
            if not settings['enabled']:
                self._json({'ok': False, 'error': 'Rotor désactivé — '
                            'active-le dans CONFIG (mode expert, section ROTOR)'}, 400)
                return
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            host, port = settings['host'], settings['port']
            if self.path == '/rotor/point':
                az = payload.get('azimuth')
                if az is None:
                    self._json({'ok': False, 'error': 'Azimut manquant'}, 400)
                    return
                res = rotor.set_position(host, port, az, payload.get('elevation', 0))
                if res.get('ok'):
                    print(f"[ROTOR] Pointe {res['azimuth']} deg")
            else:
                res = rotor.stop(host, port)
            self._json(res, 200 if res.get('ok') else 502)
            return

        # Self-spot : publier son propre spot sur un cluster DX (avec sa fréquence)
        if self.path == '/cluster/spot':
            import logx_clusters as clusters
            cfg_now = self._cfg_snapshot()
            settings = clusters.cluster_spot_settings(cfg_now)
            if not settings['enabled']:
                self._json({'ok': False, 'error': 'Self-spot désactivé — '
                            'active-le dans CONFIG (section DX CLUSTER)'}, 400)
                return
            if not settings['login']:
                self._json({'ok': False, 'error': 'Indicatif manquant '
                            '(configure ta station dans CONFIG)'}, 400)
                return
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            # Fréquence en kHz (freq_khz direct, ou freq_mhz * 1000)
            freq_khz = _freq_khz_from_payload(payload)
            if not freq_khz:
                self._json({'ok': False, 'error': 'Fréquence manquante'}, 400)
                return
            # L'indicatif spotté = celui de l'opérateur (login), JAMAIS depuis le body.
            res = clusters.publish_self_spot(
                settings['host'], settings['port'], settings['login'],
                settings['login'], freq_khz, str(payload.get('comment', '')))
            self._json(res, 200 if res.get('ok') else 502)
            return

        # Auto-spot POTA (publication sur l'API publique api.pota.app, cf.
        # logx_pota.post_spot) — pendant de /cluster/spot pour un activateur.
        # L'indicatif spotté = celui de l'opérateur (station), jamais depuis
        # le body, comme pour /cluster/spot ci-dessus.
        if self.path == '/pota/spot':
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            import logx_pota as pota
            cfg_now = self._cfg_snapshot()
            call = (cfg_now.get('callsign_contest') or cfg_now.get('callsign') or '').strip()
            if not call:
                self._json({'ok': False, 'error': 'Indicatif manquant (configure ta station dans CONFIG)'}, 400)
                return
            # str() explicite AVANT .strip()/.upper() : reference peut être un
            # nombre dans le payload JSON ({"reference": 123}), qui n'a pas de
            # .strip() -> AttributeError non capturée (requête plantée sans
            # réponse JSON). (payload.get('mode') or '') plutôt que
            # .get('mode', '') : {"mode": null} est une clé PRÉSENTE, le
            # défaut de .get() ne s'applique donc pas et str(None) == 'None'
            # se serait glissé dans le payload envoyé à l'API publique POTA.
            reference = str(payload.get('reference') or cfg_now.get('my_activation_ref') or '').strip().upper()
            freq_khz = _freq_khz_from_payload(payload)
            res = pota.post_spot(call, reference, freq_khz,
                                  str(payload.get('mode') or ''), spotter=call,
                                  comment=str(payload.get('comment') or ''))
            self._json(res, 200 if res.get('ok') else 502)
            return

        # Auto-spot SOTA (SOTA SSO + api2.sota.org.uk, cf. logx_sota_spot.py)
        # — pendant de /pota/spot pour un activateur SOTA. Reste inactif tant
        # que clientId + case d'approbation IA ne sont pas configurés (voir
        # sota_spot_settings) : c'est post_spot() qui vérifie, pas ce handler.
        if self.path == '/sota/spot':
            # try/except global : freq_khz vient du payload JSON de l'appelant
            # et peut être n'importe quoi (chaîne non numérique, liste, bool...)
            # — `freq_khz / 1000` plante alors avec une TypeError non capturée
            # (requête plantée sans réponse JSON, cf. /pota/spot un peu plus
            # haut qui a un commentaire dédié sur ce même genre de piège).
            # Même filet que /qrz_logbook/test : jamais de 500 sans corps JSON.
            try:
                try:
                    payload = json.loads(body) if body else {}
                except Exception:
                    payload = {}
                import logx_sota_spot as sotaspot
                cfg_now = self._cfg_snapshot()
                reference = str(payload.get('reference') or cfg_now.get('my_activation_ref') or '').strip().upper()
                freq_khz = _freq_khz_from_payload(payload)
                freq_mhz = (freq_khz / 1000) if freq_khz else 0
                res = sotaspot.post_spot(cfg_now, reference, freq_mhz,
                                          str(payload.get('mode') or ''),
                                          comment=str(payload.get('comment') or ''))
                self._json(res, 200 if res.get('ok') else 502)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # QTC (WAE) : enregistrer une série QTC (émise ou reçue) avec une station.
        # Deux formes de payload acceptées :
        #  - simple (historique) : {call, count} — comptage seul, pas de détail
        #    exportable en Cabrillo.
        #  - détaillée (voir logx_logbook.js:saveQTCSeries) : {call, direction,
        #    band, mode, series_number, entries:[{time,call,nr}, ...]} — le
        #    détail réglementaire WAE (1 à 10 QSO rapportés), repris tel quel
        #    par logx_export.build_cabrillo pour générer les lignes "QTC:".
        if self.path == '/qtc/add':
            try:
                from logx_storage import (qtc_log, qtc_lock, next_qtc_id,
                                                  save_qtc_to_disk,
                                                  qtc_count_for_call, qtc_total)
                payload = json.loads(body)
                call = str(payload.get('call', '')).upper().strip()
                direction = payload.get('direction') or 'sent'
                if direction not in ('sent', 'recv'):
                    direction = 'sent'

                raw_entries = payload.get('entries') or []
                entries = []
                for e in raw_entries:
                    e_time = str((e or {}).get('time', '')).strip()
                    e_call = str((e or {}).get('call', '')).upper().strip()
                    e_nr = str((e or {}).get('nr', '')).strip()
                    if not (e_time or e_call or e_nr):
                        continue  # ligne totalement vide (repli du formulaire) : ignorée
                    if not (e_time and e_call and e_nr):
                        self._json({'ok': False, 'error':
                                    "Chaque QTC doit avoir heure + indicatif + n° "
                                    "(règlement WAE) — ligne incomplète"}, 400)
                        return
                    entries.append({'time': e_time, 'call': e_call, 'nr': e_nr})
                if entries and not 1 <= len(entries) <= 10:
                    self._json({'ok': False, 'error':
                                "Une série QTC contient de 1 à 10 QTC (règlement WAE)"}, 400)
                    return

                count = len(entries) if entries else max(1, min(10, int(payload.get('count', 1))))
                cfg_snap = self._cfg_snapshot()
                cid = cfg_snap.get('contest', '')
                # Portée (contest+année) : qtc_count_for_call/qtc_total lisent
                # qso_scope_id(entrée) en interne depuis ce correctif — leur
                # passer le nom brut du concours (sans année) les faisait
                # toujours répondre 0, cassant le plafond réglementaire de 10
                # QTC par station.
                scope_id = active_scope_id(cfg_snap)
                already = qtc_count_for_call(call, scope_id)
                if call and already + count > 10:
                    self._json({'ok': False,
                                'error': f"Max 10 QTC par station — déjà {already} "
                                         f"avec {call}"}, 400)
                    return
                now_utc = datetime.datetime.utcnow()
                entry = {'id': next_qtc_id(), 'call': call, 'count': count,
                         'contest': cid, 'date': now_utc.strftime('%Y%m%d'),
                         'time': now_utc.strftime('%H:%M'), 'direction': direction}
                if payload.get('band'):
                    entry['band'] = str(payload['band']).strip()
                if payload.get('mode'):
                    entry['mode'] = str(payload['mode']).upper().strip()
                if payload.get('series_number'):
                    try:
                        entry['series_number'] = int(payload['series_number'])
                    except (TypeError, ValueError):
                        pass
                if entries:
                    entry['entries'] = entries
                with qtc_lock:
                    qtc_log.append(entry)
                save_qtc_to_disk()
                print(f"[QTC] +{count} avec {call or '?'} ({direction})")
                self._json({'ok': True, 'total': qtc_total(scope_id),
                            'with_call': already + count, 'id': entry['id']})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Chat multi-opérateur — envoi d'un message
        if self.path == '/chat/send':
            try:
                msg = json.loads(body)
                now = datetime.datetime.utcnow().strftime('%H:%M')
                with chat_lock:
                    chat_seq += 1
                    entry = {
                        'id':   chat_seq,
                        'op':   msg.get('op', 'OP?'),
                        'call': msg.get('call', ''),
                        'time': now,
                        'text': str(msg.get('text', ''))[:500],
                    }
                    chat_messages.append(entry)
                    if len(chat_messages) > 200:
                        chat_messages.pop(0)
                self._json({'ok': True, 'id': chat_seq})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Vue PARTNER — un opérateur diffuse ce qu'il tape dans le champ
        # indicatif (état éphémère, jamais persisté, écrasé à chaque frappe ;
        # voir _active_typing pour la lecture). Payload volontairement
        # minuscule (throttlé côté client à ~3/s) : pas de log, pas de disque.
        if self.path == '/chat/typing':
            try:
                msg = json.loads(body)
                op = str(msg.get('op', '') or '').strip()[:10]
                if op:
                    with typing_lock:
                        typing_state[op] = {
                            'op': op,
                            'label': str(msg.get('label', op) or op)[:60],
                            'band': str(msg.get('band', '') or '')[:10],
                            'mode': str(msg.get('mode', '') or '')[:10],
                            'text': str(msg.get('text', '') or '')[:20],
                            'ts': time.time(),
                        }
                self._json({'ok': True})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Mise à jour base indicatifs
        if self.path == '/calldb/update':
            try:
                update = json.loads(body)
                call = update.get('call','').upper()
                locator = update.get('locator','').upper()
                dept = update.get('dept','').upper()
                if call:
                    calldb_path = os.path.join(os.getcwd(), 'calldb.json')
                    if os.path.exists(calldb_path):
                        with open(calldb_path, 'r', encoding='utf-8') as f:
                            db = json.load(f)
                        entry = db.get('calls', {}).get(call, {})
                        changed = False
                        if locator and entry.get('locator') != locator:
                            entry['locator'] = locator
                            changed = True
                        if dept and entry.get('dept') != dept:
                            entry['dept'] = dept
                            changed = True
                        if changed:
                            db['calls'][call] = entry
                            save_json_atomic(calldb_path, db, lock=calldb_lock, compact=True)
                            print(f"[DB] Mis à jour : {call} -> loc:{locator} dept:{dept}")
                self._json({'ok': True})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Import MASTER.SCP (Super Check Partial N1MM) : fusionné dans l'index
        # de logx_callhistory.py, jamais un second système de suggestion.
        # Calcul 100% local (parsing texte) : pas d'appel réseau, donc pas
        # besoin du pattern ThreadPoolExecutor+timeout réservé aux vrais I/O.
        if self.path == '/callhistory/import_scp':
            try:
                import logx_callhistory as callhistory
                payload = json.loads(body) if body else {}
                text = payload.get('text', '')
                if not text:
                    self._json({'ok': False, 'error': 'Fichier vide.'}, 400)
                    return
                res = callhistory.import_master_scp(text)
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Import d'un fichier Call History (format N1MM) pour UN concours :
        # préremplit dept/locator/nom/section/zone de ce concours précis,
        # en plus (jamais à la place) des données propres à la station.
        if self.path == '/callhistory/import_n1mm':
            try:
                import logx_callhistory as callhistory
                payload = json.loads(body) if body else {}
                text = payload.get('text', '')
                contest = payload.get('contest', '') or self._cfg_snapshot().get('contest', '')
                if not text:
                    self._json({'ok': False, 'error': 'Fichier vide.'}, 400)
                    return
                res = callhistory.import_call_history_n1mm(contest, text)
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Mise à jour d'un QSO (correction)
        if self.path == '/log/update':
            try:
                updated_qso = json.loads(body)
                qso_id = updated_qso.get('id')
                # bump_log_version()/stamp_qso_version() DANS le même verrou que la
                # mutation (même risque de course que l'ajout/la suppression, voir
                # add_qso_to_log). Portée AVANT/APRÈS (qso_scope_id : contest+année
                # tirée du champ 'date') comparée pour détecter une correction de
                # date qui fait sortir le QSO de la portée concours active — le
                # même genre d'événement que /config/save (qui appelle déjà
                # mark_hard_reset() pour un changement de portée SANS toucher un
                # QSO). Sans ce hard reset, un pair déjà synchronisé continuerait
                # d'afficher indéfiniment ce QSO : il n'est ni dans le delta (son
                # nouveau 'contest'/'date' le fait exclure par le filtre de portée
                # AVANT même la comparaison de version) ni dans les tombstones (ce
                # n'est pas une suppression).
                with log_lock:
                    old_scope = None
                    for i, q in enumerate(shared_log):
                        if q.get('id') == qso_id:
                            old_scope = qso_scope_id(q)
                            shared_log[i] = updated_qso
                            break
                    bump_log_version()
                    stamp_qso_version(updated_qso)   # voir /log/list?since=
                    if old_scope is not None and qso_scope_id(updated_qso) != old_scope:
                        mark_hard_reset()   # voir /log/list?since= : portée du QSO changée
                save_log_to_disk()
                print(f"[LOG] ~QSO corrige id={qso_id}")
                self._json({'ok': True})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Ajout d'un QSO
        if self.path == '/log/add':
            try:
                qso = json.loads(body)
                if not qso.get('call'):
                    self._json({'error': 'Indicatif manquant'}, 400)
                    return
                ok, info = add_qso_to_log(qso, force=bool(qso.get('force')))
                if not ok:
                    ex = info['existing']
                    key0 = str(qso.get('call', '')).upper().strip()
                    print(f"[LOG] DUP refuse {key0} {qso.get('band')}MHz")
                    self._json({'ok': False, 'duplicate': True, 'existing': ex,
                                'error': f"Doublon : {key0} déjà contacté sur "
                                         f"{qso.get('band')} MHz en "
                                         f"{str(qso.get('mode','')).upper()} à "
                                         f"{ex.get('time','?')} "
                                         f"(renvoyer avec force=true pour insister)"},
                               409)
                    return
                print(f"[LOG] +QSO {qso.get('call')} {qso.get('band')}MHz")
                self._json({'ok': True, 'total': info['total'], 'duplicate': False})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Suppression d'un QSO
        if self.path.startswith('/log/delete/'):
            try:
                qso_id = int(self.path.split('/')[-1])
                # bump_log_version()/mark_qso_deleted() DANS le même verrou que la
                # suppression (voir commentaire équivalent dans add_qso_to_log/
                # do_DELETE) : sinon un lecteur /log/list concurrent pourrait voir
                # le QSO déjà absent de shared_log mais sans tombstone posé, et
                # l'afficherait indéfiniment chez un pair déjà synchronisé.
                with log_lock:
                    before = len(shared_log)
                    removed = [q for q in shared_log if q.get('id') == qso_id]
                    shared_log[:] = [q for q in shared_log if q.get('id') != qso_id]
                    bump_log_version()
                    mark_qso_deleted(qso_id)   # voir /log/list?since= (synchro différentielle)
                save_log_to_disk()
                # Même nettoyage du scan QSL attaché que dans do_DELETE (voir
                # /qsl_scan/upload) : ce point d'entrée POST duplique la même
                # suppression, il ne doit pas laisser de fichier orphelin non plus.
                for q in removed:
                    scan = q.get('qsl_scan')
                    if scan:
                        import logx_qsl_scan as qslscan
                        qslscan.delete_scan(scan)
                self._json({'ok': True, 'deleted': before - len(shared_log)})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Reset log
        # Import ADIF — aperçu SANS écrire (compte nouveaux/doublons/erreurs)
        if self.path == '/log/import_adif/preview':
            try:
                payload = json.loads(body)
                import logx_import as imp
                with log_lock:
                    snapshot = list(shared_log)
                self._json(imp.preview_import(payload.get('adif', ''), snapshot))
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 400)
            return

        # Import ADIF — écrit réellement les QSO neufs (une seule sauvegarde
        # disque, pas de push Club Log Live : import historique, pas un QSO live)
        if self.path == '/log/import_adif/commit':
            try:
                payload = json.loads(body)
                import logx_import as imp
                with log_lock:
                    snapshot = list(shared_log)
                new_qsos, errors = imp.commit_import(payload.get('adif', ''), snapshot)
                with log_lock:
                    shared_log.extend(new_qsos)
                    total = len(shared_log)
                bump_log_version()
                for q in new_qsos:
                    stamp_qso_version(q)   # voir /log/list?since=
                save_log_to_disk()
                for q in new_qsos:
                    try:
                        import logx_callhistory as callhistory
                        callhistory.update_from_qso(q)
                    except Exception:
                        pass
                print(f"[IMPORT] {len(new_qsos)} QSO importés depuis ADIF ({len(errors)} erreurs)")
                self._json({'ok': True, 'imported': len(new_qsos), 'errors': errors, 'total': total})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 400)
            return

        if self.path == '/log/reset':
            try:
                payload = json.loads(body)
                if payload.get('confirm') == 'RESET':
                    from logx_storage import archive_current_log
                    import logx_archive as arch
                    cfg_snap = self._cfg_snapshot()
                    # Archive dossier permanent (log.json + Cabrillo + ADIF +
                    # résumé) par PORTÉE (concours+année, pas le seul nom brut)
                    # présente dans le log, AVANT d'effacer — sinon deux éditions
                    # non purgées d'un même concours annuel (ex. REF_QRP 2026 et
                    # 2027) se retrouvaient fusionnées dans UN SEUL Cabrillo/ADIF.
                    archived_folders = []
                    with log_lock:
                        scopes = sorted({qso_scope_id(q) for q in shared_log})
                        snapshot = list(shared_log)
                    # QTC (WAE) : snapshot à part (verrou dédié qtc_lock) puis
                    # filtré PAR SCOPE comme les QSO — sinon le Cabrillo archivé
                    # ici n'a jamais de ligne "QTC:" (voir logx_export.build_cabrillo).
                    from logx_storage import qtc_log, qtc_lock
                    with qtc_lock:
                        qtc_snapshot = list(qtc_log)
                    for scope in scopes:
                        qs = [q for q in snapshot if qso_scope_id(q) == scope]
                        qtc_series = [q for q in qtc_snapshot if qso_scope_id(q) == scope]
                        r = arch.archive_log(qs, scope or 'SANS_CONCOURS', cfg_snap, qtc_series)
                        if r.get('ok'):
                            archived_folders.append(r['name'])
                    archived = archive_current_log()   # + table SQLite (secours)
                    with log_lock:
                        shared_log.clear()
                    bump_log_version()
                    mark_hard_reset()   # voir /log/list?since= : trop de QSO effacés pour des tombstones un par un
                    save_log_to_disk()
                    print('[LOG] Log reinitialise !')
                    self._json({'ok': True, 'archived': archived,
                                'folders': archived_folders})
                else:
                    self._json({'error': 'Confirmation requise'}, 400)
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Archiver le concours ACTIF dans un dossier permanent (sans effacer,
        # sauf clear=true). Fonctionne à la fin d'un concours ou à tout moment.
        if self.path == '/log/archive':
            try:
                payload = json.loads(body) if body else {}
                import logx_archive as arch
                cfg_snap = self._cfg_snapshot()
                cid = cfg_snap.get('contest', '')
                # Portée QSO (contest+année, cfg_scope_id — pas active_scope_id :
                # respecte aussi le mode 'simple'). Si AUCUNE portée n'est active
                # (pas de concours sélectionné, ou logbook simple), archiver/vider
                # ne doit porter que sur les QSO NON TAGUÉS (qso_scope_id == '') —
                # jamais sur tout shared_log, sinon un simple oubli de sélection
                # de concours effaçait aussi tout l'historique d'autres concours
                # et années au moment du clear=true.
                scope_id = cfg_scope_id(cfg_snap)
                with log_lock:
                    qs = [q for q in shared_log if qso_scope_id(q) == scope_id]
                # QTC (WAE) : mêmes séries que /log/export/cabrillo (scopées par
                # contest+année) — sans ça, le Cabrillo archivé perd les lignes
                # "QTC:" (voir logx_export.build_cabrillo).
                from logx_storage import qtc_log, qtc_lock
                with qtc_lock:
                    qtc_series = [q for q in qtc_log if qso_scope_id(q) == scope_id]
                res = arch.archive_log(qs, cid or 'CONTEST', cfg_snap, qtc_series)
                if res.get('ok') and payload.get('clear'):
                    with log_lock:
                        keep = [q for q in shared_log if qso_scope_id(q) != scope_id]
                        shared_log[:] = keep
                    bump_log_version()
                    mark_hard_reset()   # voir /log/list?since= : effacement en masse, pas un tombstone par QSO
                    save_log_to_disk()
                    res['cleared'] = True
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Proxy IA universel (Anthropic / OpenAI / Gemini)
        # Analyse IA lancée CÔTÉ SERVEUR (thread de fond) : le résultat est
        # stocké et récupérable via GET /agent/analyze/state — l'analyse se
        # termine même si l'opérateur change d'onglet (la nav recharge la page).
        if self.path == '/agent/analyze':
            global _agent_seq
            try:
                cfg_snap = self._cfg_snapshot()
                payload = json.loads(body) if body else {}
                messages = payload.get('messages', [])
                # Nouveau chemin : le client envoie la demande BRUTE + needs_context.
                # L'enrichissement (do_refresh ~25 s) se fait DANS le thread serveur :
                # avant, le client attendait /data/refresh AVANT de poster l'analyse —
                # un changement d'onglet pendant cette phase perdait tout.
                message = payload.get('message', '')
                needs_context = bool(payload.get('needs_context'))
                system_prompt = payload.get('system') or (build_system_prompt(cfg_snap) if cfg_snap else '')
                model = payload.get('model')
                max_tokens = payload.get('max_tokens', 4096)
                with _agent_lock:
                    _agent_seq += 1
                    aid = f"{int(time.time())}-{_agent_seq}"
                    _agent_analyses[aid] = {'ts': time.time(), 'status': 'running',
                                            'reply': '', 'error': ''}
                    # Rétention : ne garder que les 10 dernières analyses
                    if len(_agent_analyses) > 10:
                        for k in sorted(_agent_analyses, key=lambda k: _agent_analyses[k]['ts'])[:-10]:
                            _agent_analyses.pop(k, None)

                def _run(aid=aid, cfg=cfg_snap, sysp=system_prompt, msgs=messages,
                         mdl=model, mt=max_tokens, msg=message, ctx=needs_context):
                    try:
                        if msg:
                            enriched = msg
                            if ctx:
                                try:
                                    data = do_refresh(cfg)
                                    if data.get('context'):
                                        enriched = data['context'] + '\n\nDemande opérateur : ' + msg
                                    if data.get('system_prompt'):
                                        sysp = data['system_prompt']
                                except Exception as e:
                                    print(f"[AGENT] contexte indisponible : {e}")
                            msgs = list(msgs) + [{'role': 'user', 'content': enriched}]
                        text = call_llm(cfg, sysp, msgs, mdl, mt)
                        with _agent_lock:
                            _agent_analyses[aid].update(status='done', reply=text)
                    except Exception as e:
                        with _agent_lock:
                            _agent_analyses[aid].update(status='error', error=str(e))
                threading.Thread(target=_run, daemon=True).start()
                self._json({'id': aid, 'status': 'running'})
            except Exception as e:
                self._json({'error': str(e)}, 500)
            return

        if self.path in ('/proxy/ai', '/proxy/anthropic'):
            cfg_snap = self._cfg_snapshot()
            provider = cfg_snap.get('api_provider', 'anthropic')
            ai_model = cfg_snap.get('ai_model', 'claude-sonnet-4-6')
            api_key  = cfg_snap.get('api_key', '')
            if not api_key:
                api_key = os.environ.get('ANTHROPIC_API_KEY', '')
            print(f"[API] Fournisseur={provider} Modele={ai_model}")
            try:
                payload  = json.loads(body)
                messages = payload.get('messages', [])
                system_prompt = payload.get('system') or (build_system_prompt(cfg_snap) if cfg_snap else '')

                if not api_key:
                    self._json({'error': {'message': 'Cle API non configuree'}}, 400)
                    return

                # ── Anthropic ───────────────────────────────────────────────
                if provider == 'anthropic':
                    anth_payload = {
                        'model':      payload.get('model', ai_model or 'claude-sonnet-4-6'),
                        'max_tokens': payload.get('max_tokens', 4096),
                        'messages':   messages,
                    }
                    if system_prompt:
                        anth_payload['system'] = system_prompt
                    req = urllib.request.Request(
                        'https://api.anthropic.com/v1/messages',
                        data=json.dumps(anth_payload).encode(),
                        headers={
                            'Content-Type':      'application/json',
                            'x-api-key':         api_key,
                            'anthropic-version': '2023-06-01',
                        },
                        method='POST'
                    )
                    with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as resp:
                        result = resp.read()
                    self._raw(200, 'application/json', result)
                    print(f"[API] Anthropic OK ({len(result)} bytes)")

                # ── OpenAI / Mistral / xAI / DeepSeek (même format d'API) ────
                elif provider in OPENAI_COMPATIBLE_ENDPOINTS:
                    base_url, default_model = OPENAI_COMPATIBLE_ENDPOINTS[provider]
                    oai_messages = []
                    if system_prompt:
                        oai_messages.append({'role': 'system', 'content': system_prompt})
                    oai_messages.extend(messages)
                    oai_payload = {
                        'model':      ai_model or default_model,
                        'max_tokens': payload.get('max_tokens', 4096),
                        'messages':   oai_messages,
                    }
                    req = urllib.request.Request(
                        base_url,
                        data=json.dumps(oai_payload).encode(),
                        headers={
                            'Content-Type':  'application/json',
                            'Authorization': f'Bearer {api_key}',
                        },
                        method='POST'
                    )
                    with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as resp:
                        oai_data = json.loads(resp.read())
                    # Normaliser en format Anthropic
                    text = oai_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    result = json.dumps({'content': [{'type': 'text', 'text': text}]}).encode()
                    self._raw(200, 'application/json', result)
                    print(f"[API] {provider} OK ({len(text)} chars)")

                # ── Gemini ──────────────────────────────────────────────────
                elif provider == 'gemini':
                    model_id = ai_model or 'gemini-2.0-flash'
                    gem_contents = []
                    for m in messages:
                        role = 'model' if m['role'] == 'assistant' else 'user'
                        gem_contents.append({'role': role, 'parts': [{'text': m['content']}]})
                    gem_payload = {'contents': gem_contents}
                    if system_prompt:
                        gem_payload['systemInstruction'] = {'parts': [{'text': system_prompt}]}
                    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}'
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(gem_payload).encode(),
                        headers={'Content-Type': 'application/json'},
                        method='POST'
                    )
                    with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as resp:
                        gem_data = json.loads(resp.read())
                    text = gem_data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                    result = json.dumps({'content': [{'type': 'text', 'text': text}]}).encode()
                    self._raw(200, 'application/json', result)
                    print(f"[API] Gemini OK ({len(text)} chars)")

                else:
                    self._json({'error': {'message': f'Fournisseur inconnu: {provider}'}}, 400)

            except urllib.error.HTTPError as e:
                err = e.read()
                print(f"[API] Erreur HTTP {e.code}: {err[:200]}")
                self._raw(e.code, 'application/json', err)
            except Exception as e:
                print(f"[API] Exception: {e}")
                self._raw(500, 'application/json',
                          json.dumps({'error': {'message': str(e)}}).encode())
            return

        self._raw(404, None, None)

    def _cfg_snapshot(self):
        """Copie de current_config prise sous config_lock — AUCUN handler ne
        doit lire current_config directement (montage/écriture concurrents)."""
        with config_lock:
            return dict(current_config)

    def _load_config_from_query(self):
        return self._cfg_snapshot()

    # Fichiers présents dans le dossier servi mais qui ne doivent JAMAIS sortir
    # par HTTP : secrets (clé API, jetons, identifiants) et données locales.
    # RÈGLE : tout fichier caché (commençant par '.') est bloqué — cela couvre
    # .server_config.json (clé API + mots de passe), .auth_token (jeton qui
    # protège toutes les routes d'écriture) et .cloudsync_instance_id. La liste
    # noire explicite ajoute les fichiers de config/données SANS point de tête.
    # Sans ce garde-fou, un GET /.server_config.json livrait tous les secrets à
    # n'importe quel poste du réseau, sans authentification.
    _NEVER_SERVE = {
        'clef api.txt', 'config.json', 'logx.db', 'shared_log.json',
        'qtc_log.json', 'cloudsync_state.json',
        'qsl_sync.json', 'scoreboard_sync.json', 'backup_state.json',
    }
    # Le test par nom exact ne couvre pas les copies renommées (logx.db.bak,
    # shared_log.json.20260722.bak...) — on bloque aussi par suffixe.
    _NEVER_SERVE_SUFFIXES = ('.bak', '.db')

    def _resolve(self, path):
        import urllib.parse
        rel = urllib.parse.unquote(path).lstrip('/\\')
        base = os.path.basename(rel).lower()
        if (base.startswith('.') or base in self._NEVER_SERVE
                or base.endswith(self._NEVER_SERVE_SUFFIXES)):
            return None
        bases = [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]
        if hasattr(sys, '_MEIPASS'):
            bases.append(sys._MEIPASS)
        for base in bases:
            base_real = os.path.realpath(base)
            candidate = os.path.realpath(os.path.join(base_real, rel))
            # Confinement anti-traversée : le fichier résolu doit rester
            # STRICTEMENT à l'intérieur du répertoire de base (404 sinon).
            if not candidate.startswith(base_real + os.sep):
                continue
            if os.path.isfile(candidate):
                return candidate
        return None

    # Sous ce seuil, gzip ne vaut pas le coût CPU (en-tête gzip ~20 octets +
    # compression) — seules les réponses substantielles (ex. /log/list avec
    # plusieurs milliers de QSO, plusieurs Mo bruts) en profitent vraiment.
    _GZIP_MIN_SIZE = 512

    def _raw(self, status, content_type, body_bytes):
        """Réponse brute : statut + Content-Type + Content-Length + CORS + corps.
        Content-Length explicite (voir commentaire équivalent dans do_GET) —
        sans lui le client n'a aucun moyen fiable de savoir où s'arrête le
        corps de la réponse en HTTP/1.0 sans chunked encoding.
        Compression gzip : activée seulement si le client l'annonce
        (Accept-Encoding) — sans quoi un client qui ne sait pas décompresser
        recevrait un corps illisible. C'est le point d'unification de TOUTES
        les réponses JSON (_json en dérive) : le log partagé (plusieurs Mo à
        9000+ QSO) en profite sans code dédié par endpoint."""
        accept_enc = self.headers.get('Accept-Encoding', '') or ''
        if (body_bytes and len(body_bytes) > self._GZIP_MIN_SIZE
                and 'gzip' in accept_enc.lower()):
            import gzip
            body_bytes = gzip.compress(body_bytes)
            compressed = True
        else:
            compressed = False
        self.send_response(status)
        if content_type:
            self.send_header('Content-Type', content_type)
        if compressed:
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(body_bytes) if body_bytes else 0))
        self._cors()
        self.end_headers()
        if body_bytes:
            self.wfile.write(body_bytes)

    def _json(self, data, code=200):
        self._raw(code, 'application/json; charset=utf-8',
                  json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _cors(self):
        # CORS restreint aux origines locales attendues (le logiciel est servi
        # en LAN sur le port du serveur) — plus de wildcard '*'.
        origin = self.headers.get('Origin', '')
        if origin and re.match(
                rf'^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:{PORT})?$',
                origin):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-RC-Token')

    # ── Authentification par token partagé ────────────────────────────────────
    # Le token est distribué en cookie SameSite=Strict à la première page HTML
    # servie : les navigateurs du LAN (multi-opérateur) sont autorisés
    # automatiquement, un site web tiers ne peut pas rejouer les routes
    # d'écriture ni /proxy/ai (le cookie n'est pas envoyé cross-site et le
    # header X-RC-Token reste possible pour les scripts).
    def _client_authorized(self):
        tok = self.headers.get('X-RC-Token', '')
        if not tok:
            m = re.search(r'(?:^|;\s*)rc_token=([0-9a-fA-F]+)', self.headers.get('Cookie', ''))
            if m:
                tok = m.group(1)
        import secrets as _secrets
        return bool(tok) and _secrets.compare_digest(tok, AUTH_TOKEN)

    def _require_auth(self):
        if self._client_authorized():
            return True
        if _access_password_enabled():
            self._json({'error': "Non autorisé — connecte-toi via /auth/login "
                                 "(mot de passe d'accès configuré)"}, 403)
        else:
            self._json({'error': "Non autorisé — recharge une page du logiciel "
                                 "(cookie de session manquant ou invalide)"}, 403)
        return False

    def _redirect(self, location):
        self.send_response(302)
        self.send_header('Location', location)
        self.send_header('Content-Length', '0')
        self._cors()
        self.end_headers()

    # ── Mot de passe d'accès optionnel (voir _access_password_enabled) ───────
    def _serve_login_page(self, next_path):
        """GET /auth/login?next=... : petit formulaire autonome (pas de
        dépendance CSS/JS externe) qui POST le mot de passe puis redirige vers
        `next` une fois le cookie rc_token obtenu."""
        # Anti-redirection-ouverte : `next` vient de la query string, on ne
        # suit qu'un chemin relatif de CE site, jamais une URL absolue ou un
        # //hôte-externe.
        if not next_path or not next_path.startswith('/') or next_path.startswith('//'):
            next_path = '/'
        # XSS reflété corrigé ici : `next_path` est un texte arbitraire fourni
        # par le client (query string), jamais interpolé dans un littéral JS
        # (un json.dumps() seul n'échappe pas '<'/'>' : un `next` contenant
        # "</script><script>..." refermait le <script> ci-dessous et exécutait
        # du JS injecté sur cette origine — vol du cookie rc_token possible).
        # On le pose en attribut HTML échappé par html.escape (déjà utilisé
        # pour les pages d'erreur, voir plus haut) et on le relit côté JS
        # depuis le DOM (dataset), jamais interpolé dans du code.
        next_attr = html.escape(next_path, quote=True)
        page = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>LogX AI — Accès protégé</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body{{background:#0d1117;color:#e6edf3;font-family:'Segoe UI',Arial,sans-serif;
       display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
  .box{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:32px 36px;
       width:100%;max-width:340px;box-sizing:border-box}}
  h1{{font-size:17px;margin:0 0 6px}}
  p.sub{{color:#8b949e;font-size:13px;margin:0 0 20px;line-height:1.5}}
  input{{width:100%;box-sizing:border-box;background:#0d1117;border:1px solid #30363d;
        color:#e6edf3;border-radius:6px;padding:10px 12px;font-size:14px;margin-bottom:14px}}
  button{{width:100%;background:#238636;border:none;color:#fff;border-radius:6px;
         padding:10px 12px;font-size:14px;cursor:pointer}}
  button:hover{{background:#2ea043}}
  button:disabled{{opacity:.6;cursor:default}}
  p.err{{color:#f85149;font-size:13px;margin:0 0 14px}}
</style></head>
<body>
  <form class="box" id="loginForm" data-next="{next_attr}">
    <h1>🔒 LogX AI — Accès protégé</h1>
    <p class="sub">Un mot de passe est requis pour obtenir les droits d'écriture
    (ajout de QSO, configuration...) sur ce poste.</p>
    <input type="password" id="pw" placeholder="Mot de passe" autofocus autocomplete="current-password">
    <button type="submit">Se connecter</button>
  </form>
<script>
const form = document.getElementById('loginForm');
const next = form.dataset.next;
const pwField = document.getElementById('pw');
function showErr(msg){{
  let p = document.getElementById('errMsg');
  if(!p){{ p = document.createElement('p'); p.id = 'errMsg'; p.className = 'err';
           form.insertBefore(p, pwField); }}
  p.textContent = msg;
}}
form.addEventListener('submit', async (e) => {{
  e.preventDefault();
  const btn = form.querySelector('button');
  btn.disabled = true; btn.textContent = 'Connexion...';
  try {{
    const r = await fetch('/auth/login', {{method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{password: pwField.value}})}});
    if (r.ok) {{ location.href = next; return; }}
    showErr('Mot de passe incorrect.');
  }} catch (err) {{ showErr('Serveur injoignable.'); }}
  btn.disabled = false; btn.textContent = 'Se connecter';
}});
</script>
</body></html>"""
        self._raw(200, 'text/html; charset=utf-8', page.encode('utf-8'))

    def _handle_auth_login_post(self):
        """POST /auth/login : vérifie le mot de passe d'accès en temps
        constant (voir _verify_access_password) et pose rc_token si correct —
        SEULE route qui distribue le jeton d'écriture quand un mot de passe
        est configuré. Volontairement sans TLS (hors scope de cette
        fonctionnalité — trop de complexité/avertissements navigateur pour ce
        lot, à traiter séparément) : le mot de passe circule en clair sur le
        réseau local, comme les identifiants déjà envoyés par /config/save
        (ON4KST, QRZ...). Cette protection couvre un accès non voulu (invité
        au radioclub, port forwardé par erreur), pas une écoute réseau active
        — un LAN non fiable (WiFi public) reste hors du modèle de menace visé
        ici. Anti-bruteforce (voir _login_rate_limited) : chaque vérification
        déclenche un PBKDF2 à 200000 itérations (~83 ms) — sans limite par IP,
        un client du LAN peut le rejouer en boucle serrée et saturer le CPU
        du serveur (ThreadingHTTPServer crée un thread par connexion, sans
        plafond)."""
        ip = self.client_address[0]
        # Throttle AVANT même de lire le corps : le calcul qu'on protège
        # (PBKDF2) n'a pas encore eu lieu, autant rejeter au plus tôt.
        if _login_rate_limited(ip):
            self._json({'ok': False,
                       'error': 'Trop de tentatives, réessaie plus tard'}, 429)
            return
        # Même principe que MAX_BODY dans do_POST : la taille est vérifiée
        # AVANT toute lecture, avec un rejet immédiat (413) si elle dépasse le
        # plafond — jamais de lecture partielle qui tronquerait silencieusement
        # un corps trop grand (un mot de passe tient largement dans 4096 octets).
        MAX_LOGIN_BODY = 4096
        try:
            length = int(self.headers.get('Content-Length', 0) or 0)
        except (TypeError, ValueError):
            length = 0
        if length < 0 or length > MAX_LOGIN_BODY:
            self._json({'ok': False, 'error': 'Corps de requête trop volumineux'}, 413)
            return
        body = self.rfile.read(length) if length else b''
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}
        password = str(payload.get('password', ''))
        if not _access_password_enabled():
            self._json({'ok': False, 'error': 'Aucun mot de passe configuré'}, 400)
            return
        if _verify_access_password(password):
            _reset_login_attempts(ip)
            body_out = json.dumps({'ok': True}).encode('utf-8')
            self.send_response(200)
            self.send_header('Set-Cookie',
                             f'rc_token={AUTH_TOKEN}; Path=/; SameSite=Strict; HttpOnly')
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body_out)))
            self._cors()
            self.end_headers()
            self.wfile.write(body_out)
        else:
            _record_login_failure(ip)
            self._json({'ok': False, 'error': 'Mot de passe incorrect'}, 401)
