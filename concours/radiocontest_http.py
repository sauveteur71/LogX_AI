# -*- coding: utf-8 -*-
"""Serveur HTTP : endpoints REST, orchestration du refresh (do_refresh), état partagé navigateur/chat/config."""

import http.server
import urllib.request
import urllib.error
import json
import os
import re
import sys
import datetime
import threading
import time
import socket

import radiocontest_rules as rules
from radiocontest_utils import PORT, CURRENT_YEAR, locator_to_latlon, haversine, SSL_CTX
from radiocontest_definitions import (CONTEST_DEFINITIONS, CONTEST_SCORING,
                                 CUSTOM_CONTEST_IDS, save_custom_contest,
                                 delete_custom_contest)
from radiocontest_validate import validate_definition
from radiocontest_rules_ai import analyze_rules
from radiocontest_storage import (shared_log, log_lock, save_log_to_disk,
                                  save_json_atomic, calldb_lock)
from radiocontest_scoring import build_scoring_context
from radiocontest_prompts import build_system_prompt, build_terrain_context
from radiocontest_rules import calc_all_dates, run_annual_update, refresh_external_contests, fetch_contest_rules
from radiocontest_clusters import (SPOTS_CACHE, fetch_all_vhf_spots, fetch_cluster_f5len,
                      fetch_dxsummit_hf, fetch_f5len_hf, fetch_telnet_cluster,
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

    if provider == 'openai':
        msgs = ([{'role': 'system', 'content': system_prompt}] if system_prompt else []) + messages
        payload = {'model': ai_model or 'gpt-4o', 'max_tokens': max_tokens, 'messages': msgs}
        req = urllib.request.Request(
            'https://api.openai.com/v1/chat/completions', data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json',
                     'Authorization': f'Bearer {api_key}'}, method='POST')
        with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as resp:
            d = json.loads(resp.read())
        return d.get('choices', [{}])[0].get('message', {}).get('content', '')

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
def _load_auth_token():
    try:
        with open('config.json', encoding='utf-8') as f:
            tok = (json.load(f).get('server', {}) or {}).get('auth_token', '')
        if tok:
            return str(tok)
    except Exception:
        pass
    try:
        with open('.auth_token', encoding='utf-8') as f:
            tok = f.read().strip()
        if tok:
            return tok
    except Exception:
        pass
    import secrets as _secrets
    tok = _secrets.token_hex(16)
    try:
        with open('.auth_token', 'w', encoding='utf-8') as f:
            f.write(tok)
    except Exception:
        pass
    return tok

AUTH_TOKEN = _load_auth_token()

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
    contest_id = qso.get('contest', '')
    with log_lock:
        dup = next((q for q in shared_log
                    if (str(q.get('call', '')).upper().strip(),
                        str(q.get('band', '')),
                        str(q.get('mode', '')).upper()) == key
                    and q.get('contest', '') == contest_id), None)
    if dup and not force:
        return False, {'duplicate': True, 'existing': {
            'id': dup.get('id'), 'date': dup.get('date'),
            'time': dup.get('time'), 'operator': dup.get('operator', '')}}
    qso.pop('force', None)
    qso.setdefault('id', int(_t.time() * 1000))
    with log_lock:
        shared_log.append(qso)
    save_log_to_disk()
    # Mode expédition : pousse le QSO vers le flux Club Log Live (fire-and-forget)
    try:
        with config_lock:
            cfg_now = dict(current_config)
        if str(cfg_now.get('clublog_live', '')) in ('1', 'true', 'True', 'on'):
            import radiocontest_qsl as qsl
            threading.Thread(target=lambda: qsl.realtime_push(cfg_now, dict(qso)),
                             daemon=True).start()
    except Exception:
        pass
    # Enrichit l'historique d'indicatifs à chaud (Super Check Partial)
    try:
        import radiocontest_callhistory as callhistory
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

def _fetch_spots_vhf_src(band, no_digi):
    s = fetch_all_vhf_spots(band, filter_digital=no_digi)
    SPOTS_CACHE[str(band)] = s
    print(f"[DATA] {band} MHz: {len(s)} spots (multi-cluster)")
    return s

def _fetch_spots_50_src(no_digi):
    s = fetch_cluster_f5len(50, filter_digital=no_digi)
    SPOTS_CACHE['50'] = s
    print(f"[DATA] 50 MHz: {len(s)} spots")
    return s

def _fetch_spots_hf_src(callsign, no_digi):
    """4 sources HF fusionnées et dédupliquées (DXSummit, F5LEN, Telnet, navigateur)."""
    s_summit = fetch_dxsummit_hf(filter_digital=no_digi)
    s_f5len = fetch_f5len_hf(filter_digital=no_digi)
    s_telnet = fetch_telnet_cluster(callsign=callsign or 'F4GLD', filter_digital=no_digi)
    s_browser = []
    with browser_spots_lock:
        age = time.time() - browser_spots_ts
        if browser_spots_cache and age < 600:  # valides 10 min
            s_browser = list(browser_spots_cache)
            print(f"[BROWSER-SPOTS] {len(s_browser)} spots (age {int(age)}s)")
        elif browser_spots_cache:
            print(f"[BROWSER-SPOTS] cache perime ({int(age)}s)")
    all_hf = s_summit + s_f5len + s_telnet + s_browser
    seen_hf = set()
    s = []
    for sp in all_hf:
        dx = sp.get('dx','') if isinstance(sp, dict) else (sp[0] if sp else '')
        freq = str(sp.get('freq','')) if isinstance(sp, dict) else (sp[1] if len(sp)>1 else '')
        key = f"{dx}|{freq}"
        if key not in seen_hf:
            seen_hf.add(key)
            s.append(sp)
    print(f"[DATA] HF: {len(s)} spots total (DXWatch:{len(s_summit)} F5LEN:{len(s_f5len)} Telnet:{len(s_telnet)} Browser:{len(s_browser)})")
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
    log_sw  = cfg.get('log_software', 'net-test-thf')
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
        futs['spots_144'] = ex.submit(_fetch_spots_vhf_src, 144, no_digi)
    if '432' in cdef_bands or (toggles.get('band_70cm', False) and not is_hf_contest) \
            or ('432' in str(contest) and not is_hf_contest):
        futs['spots_432'] = ex.submit(_fetch_spots_vhf_src, 432, no_digi)
    if '50' in cdef_bands or toggles.get('band_6m', False):
        futs['spots_50'] = ex.submit(_fetch_spots_50_src, no_digi)
    if has_hf_bands or any(toggles.get(b, False) for b in hf_bands):
        futs['spots_hf'] = ex.submit(_fetch_spots_hf_src, callsign, no_digi)
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
        import radiocontest_paths as paths
        my_ll_op = locator_to_latlon(cfg.get('locator', '') or 'JN15XC')
        if my_ll_op[0] is not None:
            solar_op = {'solar': {'k_index': (noaa or {}).get('k_index', 2)}}
            try:
                from radiocontest_clusters import fetch_solar_data, fetch_muf
                sd = fetch_solar_data() or {}
                solar_op = {'solar': sd, 'muf': fetch_muf(my_ll_op[0], my_ll_op[1])}
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

# ─── HTTP HANDLER ─────────────────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def do_OPTIONS(self):
        self._raw(200, None, None)

    def do_DELETE(self):
        """Gérer les requêtes DELETE (ex: /log/delete/42)."""
        if self.path.startswith('/log/delete/'):
            try:
                qso_id = int(self.path.split('/')[-1])
                with log_lock:
                    before = len(shared_log)
                    shared_log[:] = [q for q in shared_log if q.get('id') != qso_id]
                save_log_to_disk()
                self._json({'ok': True, 'deleted': before - len(shared_log)})
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
                'url_logbook': f'http://{local_ip}:{PORT}/radiocontest_logbook.html',
                'url_terrain': f'http://{local_ip}:{PORT}/radiocontest_mobile.html',
                'peers': len(connected_peers),
            })
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
            with log_lock:
                self._json({
                    'qsos': shared_log,
                    'total': len(shared_log),
                    'peers': len(connected_peers),
                    'score': sum(q.get('points',0) for q in shared_log),
                })
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
                local = {}
                if os.path.exists(calldb_path):
                    with open(calldb_path, 'r', encoding='utf-8') as f:
                        db = json.load(f)
                    local = db.get('calls', {}).get(base, {})
                # Locator déjà connu localement
                if local.get('locator'):
                    self._json({'call': base, 'locator': local['locator'], 'dept': local.get('dept',''), 'source': 'local'})
                    return
                # Sinon interroger HamQTH
                result = lookup_hamqth(base)
                if result and result.get('locator'):
                    # Persister dans calldb.json
                    if os.path.exists(calldb_path):
                        with open(calldb_path, 'r', encoding='utf-8') as f:
                            db2 = json.load(f)
                        db2.setdefault('calls', {})[base] = {
                            'locator': result['locator'],
                            'country': result.get('country', ''),
                        }
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
            self._json({'messages': new_msgs, 'last_id': last_id})
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
                    'format': 'radiocontest-custom-contests',
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
            import radiocontest_coach as coach
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
                from radiocontest_scoring import build_ranked_spots
                ranked, _ = build_ranked_spots({}, _spots_from_caches(), cfg_snapshot)
                mult_count = sum(1 for s in ranked
                                 if s.get('scoring', {}).get('new_mult')
                                 and not s.get('scoring', {}).get('already_done'))
            except Exception:
                pass
            # Indice K pour la prévision aurora (cache solaire, pas de réseau bloquant)
            k_index = None
            try:
                from radiocontest_clusters import fetch_solar_data
                k_index = (fetch_solar_data() or {}).get('k_index')
            except Exception:
                pass
            # Langue des textes du coach (le front la connaît : localStorage rc_lang).
            from urllib.parse import parse_qs, urlparse
            lang = (parse_qs(urlparse(self.path).query).get('lang') or ['fr'])[0]
            self._json(coach.build_coach_state(cfg_snapshot, shared_log, dxmaps,
                                               mult_spots_count=mult_count,
                                               k_index=k_index, lang=lang))
            return

        # Débrief post-concours : stats déterministes + prompt prêt pour l'IA
        # (le client l'envoie ensuite à /proxy/ai — la clé reste côté serveur).
        if path == '/coach/debrief':
            import radiocontest_coach as coach
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            self._json(coach.build_debrief(cfg_snap, log_copy))
            return

        # Recherche QRZ.com d'un indicatif (identifiants lus dans la config,
        # jamais dans la requête ni renvoyés au client).
        if path.startswith('/qrz/lookup'):
            from urllib.parse import parse_qs, urlparse
            import radiocontest_qrz as qrz
            call = (parse_qs(urlparse(self.path).query).get('call', [''])[0])
            settings = qrz.qrz_settings(self._cfg_snapshot())
            if not settings['enabled']:
                self._json({'ok': False, 'enabled': False,
                            'error': 'QRZ non configuré (CONFIG → identifiants QRZ)'})
                return
            res = qrz.lookup(call, settings['user'], settings['pw'])
            res['enabled'] = True
            self._json(res)
            return

        # Statut d'un indicatif À LA FRAPPE : nouveau / doublon / nouveau_mult.
        # Réutilise le moteur de scoring (état reconstruit depuis shared_log).
        if path.startswith('/log/check'):
            from urllib.parse import parse_qs, urlparse
            from radiocontest_scoring import build_ranked_spots
            qs = parse_qs(urlparse(self.path).query)
            call = (qs.get('call', [''])[0]).upper().strip()
            band = (qs.get('band', [''])[0]).strip()
            mode = (qs.get('mode', [''])[0]).upper().strip()
            if len(call) < 3:
                self._json({'status': 'inconnu'})
                return
            cfg_snap = self._cfg_snapshot()
            contest_id = cfg_snap.get('contest', '')
            with log_lock:
                dup = any(
                    str(q.get('call', '')).upper().strip() == call
                    and str(q.get('band', '')) == band
                    and (not mode or str(q.get('mode', '')).upper() == mode)
                    and q.get('contest', '') == contest_id
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
            import radiocontest_validator as validator
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            self._json(validator.validate_log(
                log_copy, cfg_snap.get('contest', ''), cfg_snap))
            return

        # Index d'indicatifs fusionné (calldb + archives + qso_archive + log) :
        # remplace /calldb.json côté client pour le Super Check Partial —
        # même forme, enrichie de qso_count/worked/last_date.
        if path == '/call/index':
            import radiocontest_callhistory as callhistory
            with log_lock:
                log_copy = list(shared_log)
            self._json(callhistory.export_index(log_copy))
            return

        # Historique de station (« déjà contacté ») + « nouveau à vie » :
        # tous les QSO passés avec cette station, sur TOUTE la vie du log.
        if path.startswith('/call/history'):
            from urllib.parse import parse_qs, urlparse
            import radiocontest_awards as awards
            qp = parse_qs(urlparse(self.path).query)
            call = (qp.get('call', [''])[0]).upper().strip()
            band = (qp.get('band', [''])[0]).strip()
            with log_lock:
                log_copy = list(shared_log)
            h = awards.history(call, log_copy)
            h['new_one'] = awards.new_one(call, band, '', log_copy)
            self._json(h)
            return

        # Tableau de bord diplômes : DXCC / départements travaillés & confirmés
        # sur toute la vie de la station (pas seulement le concours en cours).
        if path == '/awards/summary':
            import radiocontest_awards as awards
            with log_lock:
                log_copy = list(shared_log)
            self._json(awards.award_summary(log_copy))
            return

        # État de configuration QSL + horodatage des dernières synchros.
        if path == '/qsl/status':
            import radiocontest_qsl as qsl
            self._json(qsl.qsl_status(self._cfg_snapshot()))
            return

        # Tableau de chasse départements REF : contactés vs total (depuis le log)
        if path == '/data/departments_worked':
            import radiocontest_departments as dep
            cfg_snap = self._cfg_snapshot()
            self._json(dep.departments_progress(shared_log, cfg_snap.get('contest', '')))
            return

        # Chasse aux départements : manquants + stations connues, croisés avec
        # les spots cluster actuels (station spottée = cible immédiate).
        if path == '/departments/targets':
            import radiocontest_departments as dep
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            self._json(dep.department_targets(
                log_copy, cfg_snap.get('contest', ''), _spots_from_caches()))
            return

        # GeoJSON des départements français (cache disque, offline après 1er DL)
        if path == '/data/france_geojson':
            import radiocontest_departments as dep
            body = dep.load_france_geojson()
            if not body:
                self._json({'error': 'GeoJSON indisponible (hors ligne au 1er accès)'}, 503)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'max-age=86400')
            self._cors()
            self.end_headers()
            self.wfile.write(body.encode('utf-8'))
            return

        # Balises NCDXF/IBP : quelle balise émet MAINTENANT sur chaque bande
        # (+ distance/azimut depuis le locator) — calcul pur, pas de réseau.
        if path == '/beacons/now':
            import radiocontest_beacons as beacons
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            out = beacons.beacons_now()
            from radiocontest_utils import bearing, cardinal
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
            import radiocontest_psk as psk
            cfg_snap = self._cfg_snapshot()
            call = (cfg_snap.get('callsign_contest') or cfg_snap.get('callsign') or '')
            self._json(psk.heard_where(call, cfg_snap.get('locator', '')))
            return

        # Météo du point haut (open-meteo, sans clé) — sécurité matériel /P
        if path == '/data/weather':
            import radiocontest_weather as weather
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            self._json(weather.get_weather(my_ll[0], my_ll[1]))
            return

        # Prévision tropo (ducting) — gradient de réfractivité (open-meteo niveaux)
        if path == '/data/tropo':
            import radiocontest_tropo as tropo
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            self._json(tropo.tropo_forecast(my_ll[0], my_ll[1]))
            return

        # Calendrier météores (Meteor Scatter VHF) — déterministe, pas de réseau
        if path == '/data/meteors':
            import radiocontest_meteors as met
            self._json(met.ms_quality())
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
            import radiocontest_paths as paths
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            if my_ll[0] is None:
                self._json({'ok': False, 'error': 'Locator station non défini'})
                return
            try:
                from radiocontest_clusters import fetch_solar_data, fetch_muf
                solar = {'solar': fetch_solar_data() or {},
                         'muf': fetch_muf(my_ll[0], my_ll[1])}
            except Exception:
                solar = {}
            region = (parse_qs(urlparse(self.path).query).get('region') or [''])[0].upper()
            if region and region in paths.REGIONS:
                self._json({'ok': True, 'detail': paths.path_openings(my_ll[0], my_ll[1], region, solar=solar)})
            else:
                self._json({'ok': True, 'regions': paths.all_regions(my_ll[0], my_ll[1], solar=solar)})
            return

        # Carte de propagation mondiale (grille colorée) pour la surcouche carte IA.
        # ?band=best|14|7… & ?hour=0..23 (décalage horaire depuis maintenant).
        if path.startswith('/data/propmap'):
            from urllib.parse import parse_qs, urlparse
            import radiocontest_paths as paths
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
                from radiocontest_clusters import fetch_solar_data, fetch_muf
                solar = {'solar': fetch_solar_data() or {}, 'muf': fetch_muf(my_ll[0], my_ll[1])}
            except Exception:
                solar = {}
            when = datetime.datetime.utcnow() + datetime.timedelta(hours=hour)
            cells = paths.prop_grid(my_ll[0], my_ll[1], band, when, solar, step=15)
            self._json({'ok': True, 'band': band, 'hour': hour,
                        'when_utc': when.strftime('%H:%M'), 'step': 15,
                        'my': {'lat': my_ll[0], 'lon': my_ll[1]}, 'cells': cells})
            return

        # Écran mural d'expédition : agrégation du log commun en temps réel.
        if path == '/data/wall':
            import radiocontest_wall as wall
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            self._json(wall.wall_state(log_copy, cfg_snap))
            return

        # RBN : où mon signal CW est entendu (skimmers Reverse Beacon Network)
        if path == '/data/rbn':
            import radiocontest_rbn as rbn
            cfg_snap = self._cfg_snapshot()
            call = (cfg_snap.get('callsign_contest') or cfg_snap.get('callsign') or '')
            self._json(rbn.where_heard(call))
            return

        # État scoreboard / sauvegarde (config + dernière synchro)
        if path == '/scoreboard/status':
            import radiocontest_scoreboard as sb
            self._json(sb.status(self._cfg_snapshot()))
            return
        if path == '/backup/status':
            import radiocontest_backup as bk
            self._json(bk.status(self._cfg_snapshot()))
            return

        # Propagation : indices solaires N0NBH + MUF réelle KC2G (caches 15 min)
        if path == '/data/propagation':
            from radiocontest_clusters import fetch_solar_data, fetch_muf
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            solar = fetch_solar_data()
            muf = fetch_muf(my_ll[0], my_ll[1]) if my_ll[0] else fetch_muf()
            self._json({'solar': solar, 'muf': muf})
            return

        # Need list structurée : les spots du dernier refresh évalués au barème
        # du concours actif et triés par valeur (nouveaux mults en tête) —
        # AUCUN re-fetch réseau, aucune IA : lecture des caches, pollable.
        if path == '/data/spots_ranked':
            from radiocontest_scoring import build_ranked_spots
            cfg_snap = self._cfg_snapshot()
            ranked, meta = build_ranked_spots({}, _spots_from_caches(), cfg_snap)
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15AA')
            out = []
            for s in ranked[:40]:
                sc = s.get('scoring', {})
                dx_ll = locator_to_latlon(s.get('locator', ''))
                entry = {
                    'call': s.get('call', ''), 'band': s.get('band', ''),
                    'freq': s.get('freq', ''), 'locator': s.get('locator', ''),
                    'lat': s.get('lat'), 'lon': s.get('lon'),
                    'dist_km': s.get('dist_km', 0), 'time': s.get('time', ''),
                    'source': s.get('source', ''),
                    'points': sc.get('direct_pts', 0),
                    'new_mult': bool(sc.get('new_mult')),
                    'mult_type': sc.get('mult_type', ''),
                    'priority': s.get('priority', 5),
                    'value': s.get('value_total', 0),
                    'already_done': bool(sc.get('already_done')),
                    'explanation': sc.get('explanation', ''),
                }
                if my_ll[0] and dx_ll[0]:
                    from radiocontest_utils import bearing, cardinal
                    deg = bearing(my_ll[0], my_ll[1], dx_ll[0], dx_ll[1])
                    entry['bearing'] = deg
                    entry['cardinal'] = cardinal(deg)
                out.append(entry)
            self._json({'spots': out, 'meta': meta})
            return

        # Pont WSJT-X (FT8/FT4) : état de la liaison UDP — pollé par le logbook
        if path == '/wsjtx/state':
            import radiocontest_wsjtx as wsjtx
            settings = wsjtx.wsjtx_settings(self._cfg_snapshot())
            if not settings['enabled']:
                self._json({'enabled': False})
                return
            # Démarrage à chaud (idempotent) : pas besoin de relancer le serveur
            wsjtx.start_listener(
                get_cfg=lambda: dict(current_config),
                add_qso=lambda q: add_qso_to_log(q, force=False)[0],
                port=settings['port'])
            st = wsjtx.current_status()
            st['enabled'] = True
            st['port'] = settings['port']
            self._json(st)
            return

        # Radio CAT (rigctld) : état courant — pollé par le logbook
        if path == '/rig/state':
            import radiocontest_rig as rig
            settings = rig.rig_settings(self._cfg_snapshot())
            if not settings['enabled']:
                self._json({'enabled': False})
                return
            state = rig.get_state(settings['host'], settings['port'])
            state['enabled'] = True
            self._json(state)
            return

        # Rotor d'antenne (rotctld) : position courante — pollée par le logbook
        if path == '/rotor/state':
            import radiocontest_rotor as rotor
            settings = rotor.rotor_settings(self._cfg_snapshot())
            if not settings['enabled']:
                self._json({'enabled': False})
                return
            state = rotor.get_position(settings['host'], settings['port'])
            state['enabled'] = True
            self._json(state)
            return

        # Liste des archives de concours (dossiers permanents)
        if path == '/log/archives':
            import radiocontest_archive as arch
            self._json({'archives': arch.list_archives()})
            return

        # QTC (WAE) : total et détail par station
        if path.startswith('/qtc/list'):
            from radiocontest_storage import qtc_log, qtc_lock, qtc_total
            cfg_snap = self._cfg_snapshot()
            cid = cfg_snap.get('contest', '')
            with qtc_lock:
                entries = [q for q in qtc_log
                           if not cid or q.get('contest', '') in ('', cid)]
            self._json({'total': qtc_total(cid), 'entries': entries[-50:]})
            return

        # Exports du log partagé — Cabrillo v3 et ADIF 3
        if path in ('/log/export/cabrillo', '/log/export/adif'):
            import radiocontest_export as export
            cfg_snap = self._cfg_snapshot()
            contest_id = cfg_snap.get('contest', '')
            with log_lock:
                qsos = [q for q in shared_log
                        if not contest_id or q.get('contest', '') in ('', contest_id)]
            call = (cfg_snap.get('callsign_contest') or cfg_snap.get('callsign')
                    or 'LOG').upper().replace('/', '-')
            if path.endswith('cabrillo'):
                cdef = CONTEST_DEFINITIONS.get(contest_id, {})
                body = export.build_cabrillo(qsos, cdef, cfg_snap).encode('utf-8')
                fname = f"{call}_{contest_id or 'ALL'}.cbr"
            else:
                body = export.build_adif(qsos, cfg_snap).encode('utf-8')
                fname = f"{call}_{contest_id or 'ALL'}.adi"
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
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


        if path in ('/', ''):
            path = '/radiocontest_configuration.html'

        # Anciennes URL (avant le renommage radiocontest_*) : on continue de
        # les servir pour ne casser ni favoris ni habitudes de l'équipe.
        LEGACY_PAGES = {
            '/configuration.html': '/radiocontest_configuration.html',
            '/logbook.html': '/radiocontest_logbook.html',
            '/calendrier.html': '/radiocontest_calendrier.html',
            '/radiocontest.html': '/radiocontest_carte.html',
            '/rallye-vhf-terrain.html': '/radiocontest_mobile.html',
            '/radiocontest_terrain.html': '/radiocontest_mobile.html',
            '/statusbar.js': '/radiocontest_statusbar.js',
        }
        path = LEGACY_PAGES.get(path, path)

        filepath = self._resolve(path)
        if filepath and os.path.isfile(filepath):
            self.send_response(200)
            ct = 'text/html; charset=utf-8'
            if filepath.endswith('.js'):   ct = 'application/javascript'
            if filepath.endswith('.css'):  ct = 'text/css'
            if filepath.endswith('.json'): ct = 'application/json'
            if ct.startswith('text/html'):
                # Distribue le token aux navigateurs du logiciel (SameSite=Strict :
                # jamais envoyé depuis un site tiers → routes d'écriture protégées).
                self.send_header('Set-Cookie',
                                 f'rc_token={AUTH_TOKEN}; Path=/; SameSite=Strict; HttpOnly')
            self.send_header('Content-Type', ct)
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self._cors()
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self._raw(404, None, None)

    def do_POST(self):
        global current_config, chat_seq, browser_spots_cache, browser_spots_ts
        # Toutes les routes POST écrivent ou appellent l'IA : token exigé.
        if not self._require_auth():
            return
        length = int(self.headers.get('Content-Length', 0))
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

        # Upload du log vers un service QSL (eQSL / ClubLog). Le log ADIF est
        # généré côté serveur ; les identifiants ne quittent jamais le serveur.
        if self.path == '/qsl/upload':
            try:
                payload = json.loads(body) if body else {}
                service = (payload.get('service') or '').lower()
                cfg = self._cfg_snapshot()
                contest_id = payload.get('contest', cfg.get('contest', ''))
                with log_lock:
                    qsos = [q for q in shared_log
                            if not contest_id or q.get('contest', '') in ('', contest_id)]
                if not qsos:
                    self._json({'ok': False, 'error': 'Aucun QSO à envoyer'}, 400)
                    return
                import radiocontest_export as export
                import radiocontest_qsl as qsl
                adif = export.build_adif(qsos, cfg)
                if service == 'eqsl':
                    res = qsl.upload_eqsl(cfg, adif)
                elif service == 'clublog':
                    res = qsl.upload_clublog(cfg, adif)
                else:
                    res = {'ok': False, 'error': 'Service inconnu (eqsl|clublog)'}
                res['qso_count'] = len(qsos)
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Publication du score sur le scoreboard en direct (contestonlinescore).
        if self.path == '/scoreboard/push':
            try:
                import radiocontest_scoreboard as sb
                with log_lock:
                    log_copy = list(shared_log)
                self._json(sb.push(self._cfg_snapshot(), log_copy))
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Sauvegarde manuelle immédiate vers le dossier configuré (cloud/NAS).
        if self.path == '/backup/now':
            try:
                import radiocontest_backup as bk
                with log_lock:
                    log_copy = list(shared_log)
                res = bk.run_backup(self._cfg_snapshot(), log_copy)
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Import des confirmations QSL (LoTW) → marque les QSO « confirmé ».
        if self.path == '/qsl/sync':
            try:
                payload = json.loads(body) if body else {}
                import radiocontest_qsl as qsl
                res = qsl.sync_lotw(self._cfg_snapshot(), since=payload.get('since'))
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

        # Sauvegarde configuration courante (appelé par radiocontest_carte.html au démarrage)
        if self.path == '/config/save':
            try:
                cfg = json.loads(body)
                with config_lock:
                    current_config = cfg
                save_json_atomic(SERVER_CONFIG_FILE, cfg)
                print(f"[CFG] Config reçue : {cfg.get('callsign','')} / {cfg.get('locator','')} / {cfg.get('contest','')}")
                self._json({'ok': True})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Radio CAT (rigctld) : QSY, envoi CW, stop CW
        if self.path in ('/rig/qsy', '/rig/cw', '/rig/stop'):
            import radiocontest_rig as rig
            settings = rig.rig_settings(self._cfg_snapshot())
            if not settings['enabled']:
                self._json({'ok': False, 'error': 'Radio CAT désactivée — '
                            'active-la dans CONFIG (mode expert, section RADIO)'}, 400)
                return
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            host, port = settings['host'], settings['port']
            if self.path == '/rig/qsy':
                freq = payload.get('freq_hz') or 0
                if not freq and payload.get('freq_khz'):
                    freq = float(payload['freq_khz']) * 1000
                if not freq:
                    self._json({'ok': False, 'error': 'Fréquence manquante'}, 400)
                    return
                res = rig.set_freq(host, port, int(freq), payload.get('mode'))
                if res.get('ok'):
                    print(f"[RIG] QSY {int(freq)} Hz {payload.get('mode') or ''}")
            elif self.path == '/rig/cw':
                res = rig.send_morse(host, port, str(payload.get('text', ''))[:120])
                if res.get('ok'):
                    print(f"[RIG] CW: {str(payload.get('text',''))[:40]}")
            else:
                res = rig.stop_morse(host, port)
            self._json(res, 200 if res.get('ok') else 502)
            return

        # Rotor d'antenne (rotctld) : pointer, stopper
        if self.path in ('/rotor/point', '/rotor/stop'):
            import radiocontest_rotor as rotor
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

        # QTC (WAE) : enregistrer un échange de QTC avec une station
        if self.path == '/qtc/add':
            try:
                from radiocontest_storage import (qtc_log, qtc_lock,
                                                  save_qtc_to_disk,
                                                  qtc_count_for_call, qtc_total)
                payload = json.loads(body)
                call = str(payload.get('call', '')).upper().strip()
                count = max(1, min(10, int(payload.get('count', 1))))
                cfg_snap = self._cfg_snapshot()
                cid = cfg_snap.get('contest', '')
                already = qtc_count_for_call(call, cid)
                if call and already + count > 10:
                    self._json({'ok': False,
                                'error': f"Max 10 QTC par station — déjà {already} "
                                         f"avec {call}"}, 400)
                    return
                now_utc = datetime.datetime.utcnow()
                with qtc_lock:
                    qtc_log.append({'call': call, 'count': count, 'contest': cid,
                                    'date': now_utc.strftime('%Y%m%d'),
                                    'time': now_utc.strftime('%H:%M')})
                save_qtc_to_disk()
                print(f"[QTC] +{count} avec {call or '?'}")
                self._json({'ok': True, 'total': qtc_total(cid),
                            'with_call': already + count})
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

        # Mise à jour d'un QSO (correction)
        if self.path == '/log/update':
            try:
                updated_qso = json.loads(body)
                qso_id = updated_qso.get('id')
                with log_lock:
                    for i, q in enumerate(shared_log):
                        if q.get('id') == qso_id:
                            shared_log[i] = updated_qso
                            break
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
                with log_lock:
                    before = len(shared_log)
                    shared_log[:] = [q for q in shared_log if q.get('id') != qso_id]
                save_log_to_disk()
                self._json({'ok': True, 'deleted': before - len(shared_log)})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Reset log
        if self.path == '/log/reset':
            try:
                payload = json.loads(body)
                if payload.get('confirm') == 'RESET':
                    from radiocontest_storage import archive_current_log
                    import radiocontest_archive as arch
                    cfg_snap = self._cfg_snapshot()
                    # Archive dossier permanent (log.json + Cabrillo + ADIF +
                    # résumé) par concours présent dans le log, AVANT d'effacer.
                    archived_folders = []
                    with log_lock:
                        contests = sorted({q.get('contest', '') for q in shared_log})
                        snapshot = list(shared_log)
                    for cid in contests:
                        qs = [q for q in snapshot if q.get('contest', '') == cid]
                        r = arch.archive_log(qs, cid or 'SANS_CONCOURS', cfg_snap)
                        if r.get('ok'):
                            archived_folders.append(r['name'])
                    archived = archive_current_log()   # + table SQLite (secours)
                    with log_lock:
                        shared_log.clear()
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
                import radiocontest_archive as arch
                cfg_snap = self._cfg_snapshot()
                cid = cfg_snap.get('contest', '')
                with log_lock:
                    qs = [q for q in shared_log
                          if not cid or q.get('contest', '') in ('', cid)]
                res = arch.archive_log(qs, cid or 'CONTEST', cfg_snap)
                if res.get('ok') and payload.get('clear'):
                    with log_lock:
                        keep = [q for q in shared_log
                                if cid and q.get('contest', '') not in ('', cid)]
                        shared_log[:] = keep
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
                         mdl=model, mt=max_tokens):
                    try:
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

                # ── OpenAI ──────────────────────────────────────────────────
                elif provider == 'openai':
                    oai_messages = []
                    if system_prompt:
                        oai_messages.append({'role': 'system', 'content': system_prompt})
                    oai_messages.extend(messages)
                    oai_payload = {
                        'model':      ai_model or 'gpt-4o',
                        'max_tokens': payload.get('max_tokens', 4096),
                        'messages':   oai_messages,
                    }
                    req = urllib.request.Request(
                        'https://api.openai.com/v1/chat/completions',
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
                    print(f"[API] OpenAI OK ({len(text)} chars)")

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

    # Fichiers présents dans le dossier servi mais qui ne doivent JAMAIS
    # sortir par HTTP (la clé API notamment).
    _NEVER_SERVE = {'clef api.txt'}

    def _resolve(self, path):
        import urllib.parse
        rel = urllib.parse.unquote(path).lstrip('/\\')
        if os.path.basename(rel).lower() in self._NEVER_SERVE:
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

    def _raw(self, status, content_type, body_bytes):
        """Réponse brute : statut + Content-Type + CORS + corps."""
        self.send_response(status)
        if content_type:
            self.send_header('Content-Type', content_type)
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
        self._json({'error': "Non autorisé — recharge une page du logiciel "
                             "(cookie de session manquant ou invalide)"}, 403)
        return False
