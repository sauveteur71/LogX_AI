# -*- coding: utf-8 -*-
"""Serveur HTTP : endpoints REST, orchestration du refresh (do_refresh), état partagé navigateur/chat/config."""

import http.server
import urllib.request
import urllib.error
import html
import ipaddress
import json
import math
import os
import re
import sys
import datetime
import threading
import time
import socket
from concurrent.futures import ThreadPoolExecutor

import logx_crypto
import logx_rules as rules
import logx_ref_bulletin as ref_bulletin
from logx_utils import (PORT, CURRENT_YEAR, locator_to_latlon, haversine, SSL_CTX,
                        modele_effectif, _FETCH_EXECUTOR,
                          OPENAI_COMPATIBLE_ENDPOINTS, utcnow)
from logx_definitions import (CONTEST_DEFINITIONS, CONTEST_SCORING,
                                 CUSTOM_CONTEST_IDS, save_custom_contest,
                                 delete_custom_contest)
from logx_validate import validate_definition
from logx_rules_ai import analyze_rules
from logx_storage import (shared_log, log_lock, save_log_to_disk,
                                  save_json_atomic, calldb_lock, bump_log_version,
                                  qso_scope_id, active_scope_id, cfg_scope_id,
                                  contest_actif,
                                  stamp_qso_version, mark_qso_deleted, mark_hard_reset,
                                  allocate_qso_ids_locked, reserve_qso_id_locked)
from logx_scoring import build_scoring_context, score_new_qso, resolve_scoring_bricks
import logx_transverter as transverter
from logx_prompts import build_system_prompt, build_terrain_context
from logx_rules import calc_all_dates, run_annual_update, refresh_external_contests, fetch_contest_rules
from logx_ref_bulletin import refresh_ref_bulletin, REF_BULLETIN_URL
from logx_clusters import (SPOTS_CACHE, SPOTS_CACHE_LOCK, fetch_all_vhf_spots, fetch_cluster_f5len,
                      fetch_dxsummit_hf, fetch_f5len_hf, fetch_telnet_cluster, fetch_dxwatch_hf,
                      fetch_dxheat, fetch_on4kst_data, fetch_on4kst_raw, fetch_log_edi, fetch_log_adif,
                      fetch_noaa_kindex, fetch_dxmaps_vhf, fetch_3830_scores,
                      lookup_hamqth, enrich_unknown_calls, freq_en_khz)
from logx_version import APP_VERSION

# ─── CACHE SPOTS CLUSTER ENVOYÉS PAR LE NAVIGATEUR ───────────────────────────
# Le navigateur accède à HTTPS/DXSummit, le serveur Python ne peut pas (bloqué).
# Le front-end push les spots via POST /data/spots → stockés ici.
browser_spots_cache = []      # liste de dicts {spotter, dx, freq, info, time}
browser_spots_lock  = threading.Lock()
browser_spots_ts    = 0       # timestamp dernier push
# {ip: last_seen epoch} — purgé comme peer_versions (voir
# _prune_stale_connected_peers) pour que 'peers' ne croisse pas sans fin.
connected_peers = {}
connected_peers_lock = threading.Lock()
# ─── VERSIONS DES POSTES CONNECTÉS (multi-op / DXpédition) ───────────────────
# {ip: {'version': str, 'last_seen': float epoch}} — alimenté à chaque poll
# /log/list (paramètre ?ver=, la version que CE poste croit faire tourner,
# figée côté client au chargement de sa page, voir logx_logbook.js
# initShareLink()/fetchLog()). Exposé via /log/status pour que chaque poste
# puisse comparer sa version à celle des autres AVANT un concours/DXpédition
# — même logique que les équipes N1MM qui s'alignent sur un numéro de
# version avant l'événement. Un écart reste un simple INDICATEUR visuel côté
# client, jamais un verrou : rien ici ne bloque quoi que ce soit.
# RÉTENTION (défaut corrigé — voir _prune_stale_peer_versions) : une entrée
# n'est conservée que PEER_VERSION_TTL secondes après le dernier poll de son
# IP. Sans cette purge, un poste parti (téléphone d'un visiteur, onglet de
# test fermé) ou revenu sous une AUTRE IP DHCP laissait son ancienne entrée
# servie à vie par /log/status → badge "⚠️ versions différentes" et item
# CHECKLIST "Version cohérente sur tous les postes" ROUGES en permanence,
# sans aucun moyen de purger sauf redémarrer le serveur — et l'IP périmée
# restait candidate du scan de mise à jour réseau (_known_peer_ips).
peer_versions = {}
peer_versions_lock = threading.Lock()
# Un poste ACTIF polle /log/list toutes les 5 s (logx_logbook.js, refreshTimer)
# mais un onglet en arrière-plan peut voir ses timers ralentis à ~1/min par le
# navigateur : 300 s laissent une marge très large avant de déclarer un poste
# parti, tout en effaçant une alerte fantôme en quelques minutes au lieu de
# jamais. Même pattern de fenêtre de fraîcheur que _DECODE_TTL (logx_wsjtx.py)
# et la fenêtre 30 s de logx_adifnet.py.
PEER_VERSION_TTL = 300  # secondes

# Format admis pour une version DÉCLARÉE par un pair (?ver=). Un poste s'annonce
# avec logx_version.APP_VERSION ('0.9-beta4') : chiffres, lettres, '.', '-', '+',
# '_' suffisent largement, y compris pour un futur '1.2.3+build.7'.
# POURQUOI valider (faille corrigée) : /log/list est servi par do_GET SANS
# authentification (aucun jeton requis pour POSER la valeur), et cette chaîne
# était stockée telle quelle puis restituée brute par /log/status → peer_list,
# que chaque poste polle. Côté client, le badge de version et surtout l'item
# CHECKLIST l'interpolaient dans de l'HTML : n'importe quel appareil du LAN
# pouvait donc faire exécuter du script dans l'origine d'un opérateur
# AUTHENTIFIÉ (le cookie rc_token part tout seul en same-origin → /log/reset,
# /config/save, /auth/set_password...). L'échappement côté client reste la
# défense principale (voir escHtml dans logx_logbook.js), celle-ci coupe le mal
# à la racine : une valeur non conforme n'entre jamais en mémoire.
# La borne de longueur ferme au passage la croissance non bornée de la valeur
# (la ligne de requête HTTP autorise ~64 Ko, tous stockés verbatim auparavant).
PEER_VERSION_RE = re.compile(r'[\w.+-]{1,32}')   # utilisé avec .fullmatch()


def _prune_stale_peer_versions():
    """Supprime de peer_versions les postes muets depuis plus de
    PEER_VERSION_TTL secondes. Appelée à chaque écriture (poll /log/list?ver=)
    et à chaque lecture (/log/status, _known_peer_ips) : la purge est donc
    effective même si plus personne ne polle, dès la prochaine consultation.
    Suppression réelle (pas un simple filtre d'affichage) : libère aussi la
    mémoire (croissance par IP distincte sinon) et retire l'IP des candidats
    du scan de mise à jour réseau."""
    cutoff = time.time() - PEER_VERSION_TTL
    with peer_versions_lock:
        for ip in [ip for ip, info in peer_versions.items()
                   if info.get('last_seen', 0) < cutoff]:
            del peer_versions[ip]


def _prune_stale_connected_peers():
    """Purge connected_peers des IP muettes depuis plus de PEER_VERSION_TTL
    secondes (même fenêtre que _prune_stale_peer_versions) — sinon 'peers'
    (exposé par /network/info, /log/list, /log/status) ne fait que croître
    sur une session longue, y compris pour les postes qui pollent sans
    ?ver= (donc absents de peer_versions mais présents ici)."""
    cutoff = time.time() - PEER_VERSION_TTL
    with connected_peers_lock:
        for ip in [ip for ip, ts in connected_peers.items() if ts < cutoff]:
            del connected_peers[ip]


def _known_peer_ips():
    """IP des postes que CE serveur a lui-même vus se connecter — clés de
    peer_versions, alimenté UNIQUEMENT depuis self.client_address[0] (l'IP
    socket réelle de la connexion TCP entrante sur /log/list, jamais une
    valeur lue dans un corps de requête). Anti-SSRF (voir audit sécurité) :
    /app/update_network_scan et /app/update_download_via_network reçoivent
    un champ 'ips' fourni par le CLIENT dans le corps JSON — sans ce filtre,
    un appelant pourrait y placer n'importe quel hôte/IP arbitraire et
    forcer ce serveur à émettre de vraies requêtes HTTP sortantes vers lui
    (scan de service interne, voire un début de téléchargement, cf.
    logx_update._peer_get_json/_do_download_via_network). En restreignant
    aux IP que ce serveur a lui-même observées comme pairs réels, un
    attaquant ne peut plus faire sonder/télécharger que des postes qui se
    sont DÉJÀ connectés ici de leur propre initiative — il ne peut pas
    injecter une IP/un hôte de son choix via le seul corps JSON.
    Exclusion de soi-même (défaut corrigé — voir logx_update._is_self_ip) :
    le navigateur LOCAL poll /log/list?ver= depuis 127.0.0.1 (le serveur
    invite à ouvrir http://127.0.0.1:PORT, usage nominal), donc la boucle
    locale figurait TOUJOURS dans peer_versions — et le poste se découvrait
    LUI-MÊME comme passerelle de mise à jour (gateway_status() répond
    'disponible' 6 h après la perte d'internet, cache CHECK_TTL) : vraie
    passerelle masquée (tri par IP, 127.0.0.1 en tête) et secours
    pair-à-pair refusé en s'auto-citant. La boucle locale et les IP des
    interfaces de CE poste ne sont donc jamais des pairs candidats — noter
    que peer_versions lui-même n'est PAS filtré : /log/status → peer_list
    (badge de versions) continue d'afficher tous les postes vus, y compris
    le navigateur local. Fraîcheur : purge TTL d'abord (voir _prune_stale_
    peer_versions) — une IP qui ne polle plus depuis PEER_VERSION_TTL n'est
    plus un pair candidat du scan de mise à jour réseau."""
    import logx_update as upd
    _prune_stale_peer_versions()
    with peer_versions_lock:
        ips = list(peer_versions.keys())
    return {ip for ip in ips if not upd._is_self_ip(ip)}


# ─── ANALYSES IA CÔTÉ SERVEUR (survivent au changement de page) ──────────────
# Une analyse lancée depuis la CARTE IA tourne dans un thread serveur et son
# résultat est stocké ici : si l'opérateur change d'onglet (la nav recharge la
# page), il retrouve le résultat au retour via GET /agent/analyze/state?id=.
_agent_analyses = {}          # id -> {ts, status:'running|done|error', reply, error}
_agent_seq = 0
_agent_lock = threading.Lock()

# Flux SSE d'une analyse (voir /agent/analyze/stream et _sse_agent_stream) :
# ThreadingHTTPServer mobilise UN thread OS par connexion ouverte, et le
# logiciel tourne 24h/24 pendant des expéditions de 15 jours — un flux qui ne
# se termine JAMAIS serait une fuite de threads garantie sur 360 h. La deadline
# dure ci-dessous borne la vie d'un flux quoi qu'il arrive (générations LLM
# < 120 s) ; le heartbeat tient la socket sous le timeout d'inactivité (30 s).
SSE_DEADLINE_S = 150
SSE_HEARTBEAT_S = 12

# Audit IA du log avant dépôt (voir /log/audit) : l'appel LLM (latence longue,
# sortie JSON forcée) tourne en THREAD DE FOND — jamais dans le thread HTTP —
# et son résultat est récupéré par polling (/log/audit/state), comme les
# analyses de la carte. Constats au format de validate_log.
_audit_jobs = {}              # id -> {ts, status:'running|done|error', findings, error}
_audit_seq = 0
_audit_lock = threading.Lock()

# Chasse assistée (voir /agent/act) : l'agent PROPOSE une action physique
# (pointer le rotor, QSY) via un outil ; le serveur ne l'EXÉCUTE PAS, il renvoie
# une `action` que le client affiche en carte de confirmation. Job de fond
# (tool-use non streamé), récupéré par polling /agent/act/state.
_act_jobs = {}                # id -> {ts, status, reply, action, error}
_act_seq = 0
_act_lock = threading.Lock()

# Stratégie pile-up FT8 (voir /wsjtx/strategy) : l'IA lit la SÉRIE des décodages
# d'UNE station et conseille où/quand appeler. Purement consultatif (jamais
# d'émission auto). Job de fond, récupéré par /wsjtx/strategy/state.
_strat_jobs = {}
_strat_seq = 0
_strat_lock = threading.Lock()


FT8_STRATEGY_SYSTEM = (
    "Tu es un opérateur FT8 chevronné. On te donne la SÉRIE des derniers "
    "décodages WSJT-X d'UNE station DX (heure relative en secondes, SNR en dB, "
    "décalage audio en Hz, message brut). La grammaire FT8 est « <destinataire> "
    "<émetteur> <report/grille> ». À partir de CES cycles seulement :\n"
    "- repère la fréquence audio (Hz) à laquelle la DX émet et si elle travaille "
    "en SPLIT (répond à des stations sur d'autres décalages) ;\n"
    "- vois qui elle répond (SNR de ceux qu'elle contacte) pour situer le niveau "
    "de signal qui « passe » ;\n"
    "- déduis OÙ te caler et QUAND appeler (tout de suite, ou attendre un cycle).\n"
    "Reste CONSULTATIF et PRUDENT : c'est peu de données, ne SURVENDS pas. Ne "
    "propose JAMAIS d'émettre automatiquement — l'opérateur garde la main. "
    "Réponds en 2-4 phrases COURTES, en français."
)


def build_ft8_strategy_prompt(call, series):
    lignes = []
    for d in series:
        lignes.append('il y a %ss | SNR %s dB | %s Hz | %s' % (
            d.get('il_y_a_s', '?'),
            d.get('snr') if d.get('snr') is not None else '?',
            d.get('df') if d.get('df') is not None else '?',
            d.get('msg', '')))
    return ("Station visée : %s\nDerniers décodages (du plus ancien au plus "
            "récent) :\n%s\n\nOù et quand dois-je appeler %s ?" % (call, '\n'.join(lignes), call))


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
    # Le modèle vient de la CONFIGURATION ; celui que passe l'appelant n'est
    # retenu que s'il appartient au fournisseur configuré (voir modele_effectif).
    ai_model = modele_effectif(provider, model, (cfg or {}).get('ai_model'))
    api_key = (cfg or {}).get('api_key', '') or (os.environ.get('ANTHROPIC_API_KEY', '') if provider == 'anthropic' else '')
    if not api_key:
        raise RuntimeError('Clé API non configurée')

    if provider == 'anthropic':
        payload = {'model': ai_model,
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
        model_id = ai_model
        contents = [{'role': 'model' if m['role'] == 'assistant' else 'user',
                     'parts': [{'text': m['content']}]} for m in messages]
        payload = {'contents': contents}
        if system_prompt:
            payload['systemInstruction'] = {'parts': [{'text': system_prompt}]}
        url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
               f'{model_id}:generateContent')
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json',
                                              'x-goog-api-key': api_key}, method='POST')
        with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as resp:
            d = json.loads(resp.read())
        return (d.get('candidates', [{}])[0].get('content', {})
                .get('parts', [{}])[0].get('text', ''))

    raise RuntimeError(f'Fournisseur inconnu : {provider}')


def _stream_openai_compatible(base_url, ai_model, default_model, api_key,
                              system_prompt, messages, max_tokens, on_delta):
    """Streame un fournisseur au format OpenAI (SSE 'data:' + '[DONE]'). Appelle
    on_delta(fragment) au fil de l'eau et retourne le TEXTE complet."""
    msgs = ([{'role': 'system', 'content': system_prompt}] if system_prompt else []) + messages
    payload = {'model': ai_model or default_model, 'max_tokens': max_tokens,
               'messages': msgs, 'stream': True}
    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
        method='POST')
    morceaux = []
    with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as resp:
        for raw in resp:                       # itération = readline : streame au fil de l'eau
            line = raw.decode('utf-8', 'replace').strip()
            if not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            try:
                obj = json.loads(data)
            except Exception:
                continue
            piece = ((obj.get('choices') or [{}])[0].get('delta', {}) or {}).get('content') or ''
            if piece:
                morceaux.append(piece)
                if on_delta:
                    on_delta(piece)
    return ''.join(morceaux)


def call_llm_stream(cfg, system_prompt, messages, model=None, max_tokens=4096, on_delta=None):
    """Comme call_llm mais STREAME : on_delta(fragment) est appelé à chaque bout
    de texte reçu du fournisseur, et le TEXTE complet est retourné. Anthropic et
    les fournisseurs OpenAI-compatibles streament en natif (SSE 'stream:true') ;
    Gemini (format SSE distinct) et tout fournisseur non streamable retombent sur
    call_llm() — un seul on_delta avec le texte entier. Le dispatch (modèle
    effectif, clé) est STRICTEMENT celui de call_llm : c'est la même logique, en
    flux, pour ne pas dupliquer une 4e fois la sélection de fournisseur."""
    provider = (cfg or {}).get('api_provider', 'anthropic')
    ai_model = modele_effectif(provider, model, (cfg or {}).get('ai_model'))
    api_key = (cfg or {}).get('api_key', '') or (os.environ.get('ANTHROPIC_API_KEY', '') if provider == 'anthropic' else '')
    if not api_key:
        raise RuntimeError('Clé API non configurée')

    if provider == 'anthropic':
        payload = {'model': ai_model, 'max_tokens': max_tokens,
                   'messages': messages, 'stream': True}
        if system_prompt:
            payload['system'] = system_prompt
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages', data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json', 'x-api-key': api_key,
                     'anthropic-version': '2023-06-01'}, method='POST')
        morceaux = []
        with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as resp:
            for raw in resp:
                line = raw.decode('utf-8', 'replace').strip()
                if not line.startswith('data:'):
                    continue
                try:
                    obj = json.loads(line[5:].strip())
                except Exception:
                    continue
                typ = obj.get('type')
                if typ == 'content_block_delta':
                    piece = (obj.get('delta') or {}).get('text') or ''
                    if piece:
                        morceaux.append(piece)
                        if on_delta:
                            on_delta(piece)
                elif typ == 'error':
                    raise RuntimeError((obj.get('error') or {}).get('message', 'stream error'))
                elif typ == 'message_stop':
                    break
        return ''.join(morceaux)

    if provider in OPENAI_COMPATIBLE_ENDPOINTS:
        base_url, default_model = OPENAI_COMPATIBLE_ENDPOINTS[provider]
        return _stream_openai_compatible(base_url, ai_model, default_model, api_key,
                                         system_prompt, messages, max_tokens, on_delta)

    # Gemini et tout fournisseur non streamable : repli NON streamé (un bloc).
    text = call_llm(cfg, system_prompt, messages, model, max_tokens)
    if on_delta and text:
        on_delta(text)
    return text


# ─── CHASSE ASSISTÉE : l'agent PROPOSE une action physique (tool-use) ─────────
# Le serveur n'EXÉCUTE JAMAIS l'action ici : il renvoie ce que le modèle propose,
# et c'est le CLIC de l'opérateur (carte de confirmation côté client) qui appelle
# l'endpoint existant (/rotor/point, /rig/qsy). Single-shot (pas de boucle), et
# seul Anthropic gère les outils — les autres fournisseurs répondent en TEXTE.
ACTION_TOOLS = [
    {
        'name': 'pointer_rotor',
        'description': "Proposer de faire tourner le rotor d'antenne vers un azimut "
                       "(degrés vrais, 0-360) pour viser une station ou une région. "
                       "À utiliser quand orienter l'antenne fait gagner du signal vers "
                       "un DX ou un multiplicateur intéressant.",
        'input_schema': {
            'type': 'object',
            'properties': {
                'azimut': {'type': 'number', 'description': 'azimut vrai en degrés (0-360)'},
                'cible': {'type': 'string', 'description': 'libellé court (indicatif/région) pour la confirmation'},
                'bande': {'type': 'string', 'description': "bande de la cible si connue (ex: '20m', '144MHz'), pour pointer l'antenne dédiée à cette bande (décalage mécanique compris)"},
            },
            'required': ['azimut', 'cible'],
        },
    },
    {
        'name': 'qsy_radio',
        'description': "Proposer d'amener la radio sur une fréquence (kHz) et un mode "
                       "pour travailler un spot précis qui en vaut la peine.",
        'input_schema': {
            'type': 'object',
            'properties': {
                'freq_khz': {'type': 'number', 'description': 'fréquence en kHz'},
                'mode': {'type': 'string', 'description': 'CW, SSB, USB, LSB, FT8... (optionnel)'},
                'cible': {'type': 'string', 'description': 'libellé court (indicatif) pour la confirmation'},
            },
            'required': ['freq_khz', 'cible'],
        },
    },
]


def call_llm_actions(cfg, system_prompt, messages, max_tokens=1024):
    """Comme call_llm mais avec les OUTILS d'action (tool-use Anthropic). Ne les
    exécute pas : renvoie {'text', 'action'} où action = le 1er tool_use proposé
    (ou None). Single-shot. Seul Anthropic gère les outils ; les autres
    fournisseurs retombent sur une réponse TEXTE (action None) — le chat ne casse
    jamais."""
    provider = (cfg or {}).get('api_provider', 'anthropic')
    ai_model = modele_effectif(provider, None, (cfg or {}).get('ai_model'))
    api_key = (cfg or {}).get('api_key', '') or (os.environ.get('ANTHROPIC_API_KEY', '') if provider == 'anthropic' else '')
    if not api_key:
        raise RuntimeError('Clé API non configurée')
    if provider != 'anthropic':
        return {'text': call_llm(cfg, system_prompt, messages, None, max_tokens), 'action': None}
    payload = {'model': ai_model, 'max_tokens': max_tokens, 'messages': messages,
               'tools': ACTION_TOOLS}
    if system_prompt:
        payload['system'] = system_prompt
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages', data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'x-api-key': api_key,
                 'anthropic-version': '2023-06-01'}, method='POST')
    with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as resp:
        data = json.loads(resp.read())
    text = ''.join(b.get('text', '') for b in data.get('content', [])
                   if b.get('type') == 'text')
    action = None
    for b in data.get('content', []):
        if b.get('type') == 'tool_use':
            action = {'tool': b.get('name'), 'input': b.get('input', {})}
            break
    return {'text': text, 'action': action}


def pending_action_from_tool(action):
    """Valide et normalise l'action proposée par le modèle en une `pending_action`
    exploitable par le client — ou None si elle est aberrante (azimut hors 0-360,
    fréquence non positive) : on ne propose JAMAIS de piloter la station sur une
    valeur absurde, même si le modèle la sort."""
    if not action or not isinstance(action, dict):
        return None
    inp = action.get('input') or {}
    tool = action.get('tool')
    if tool == 'pointer_rotor':
        try:
            az = float(inp.get('azimut'))
        except (TypeError, ValueError):
            return None
        if not (0 <= az <= 360) or not math.isfinite(az):
            return None
        return {'type': 'rotor', 'azimut': round(az), 'cible': str(inp.get('cible', ''))[:40],
                'bande': str(inp.get('bande', ''))[:16]}
    if tool == 'qsy_radio':
        try:
            khz = float(inp.get('freq_khz'))
        except (TypeError, ValueError):
            return None
        if not math.isfinite(khz) or khz <= 0:
            return None
        return {'type': 'qsy', 'freq_khz': round(khz, 3),
                'mode': str(inp.get('mode', '') or '')[:6],
                'cible': str(inp.get('cible', ''))[:40]}
    return None


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
            # Déchiffré UNE FOIS ici : current_config reste en clair en mémoire
            # pour tout le reste de l'appli (aucun autre code ne doit savoir
            # que les mots de passe/clés API sont chiffrés sur disque).
            return logx_crypto.decrypt_config(cfg)
    except Exception:
        pass
    return {}

def _save_config_to_disk(cfg):
    """Seul point d'écriture de .server_config.json — les identifiants y sont
    chiffrés au repos (logx_crypto.encrypt_config). Centralisé ici pour que
    les endroits qui sauvegardent la config (/config/save, /ui/theme,
    /data/spot_filter) ne puissent pas diverger sur ce point."""
    save_json_atomic(SERVER_CONFIG_FILE, logx_crypto.encrypt_config(cfg))

current_config = _load_saved_config()
config_lock = threading.Lock()

# ─── CACHE DXMAPS POUR LE COACH (TTL 10 min) ─────────────────────────────────
_coach_dxmaps_cache = None
_coach_dxmaps_ts = 0
_coach_dxmaps_lock = threading.Lock()

def _refresh_coach_dxmaps_async():
    if not _coach_dxmaps_lock.acquire(blocking=False):
        return
    def _run():
        global _coach_dxmaps_cache, _coach_dxmaps_ts
        try:
            _coach_dxmaps_cache = fetch_dxmaps_vhf()
        except Exception:
            _coach_dxmaps_cache = None
        _coach_dxmaps_ts = time.time()
        _coach_dxmaps_lock.release()
    threading.Thread(target=_run, daemon=True).start()

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
        try:
            os.chmod(AUTH_TOKEN_FILE, 0o600)
        except Exception:
            pass
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
        try:
            os.chmod(AUTH_TOKEN_FILE, 0o600)
        except Exception:
            pass
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

def _purge_stale_ips(store, now, window):
    """Retire de `store` (ip -> liste de timestamps) les IP dont le dernier
    timestamp date de plus de `window` secondes — boucle de purge partagée par
    _login_rate_limited et _relay_rate_limited (verrou déjà tenu par
    l'appelant), qui gardent chacune leur propre logique de vérification/
    enregistrement (check-only vs check-et-record)."""
    for other in [k for k, v in store.items() if not v or now - v[-1] >= window]:
        del store[other]

def _login_rate_limited(ip):
    """True si `ip` a déjà atteint la limite d'échecs récents — purge et
    lecture dans le MÊME verrou (jamais relâché entre les deux) pour éviter
    qu'une rafale concurrente ne contourne la limite. Purge aussi, dans ce
    même verrou, les AUTRES ip devenues inactives (dernier échec plus vieux
    que la fenêtre) : sans ce balayage global, une ip qui échoue une fois
    puis ne revient jamais laisserait son entrée en mémoire à vie — croissance
    non bornée sur une exécution longue (expédition 15 jours)."""
    now = time.time()
    with _login_attempts_lock:
        _purge_stale_ips(_login_attempts, now, _LOGIN_ATTEMPT_WINDOW)
        attempts = [t for t in _login_attempts.get(ip, ()) if now - t < _LOGIN_ATTEMPT_WINDOW]
        if attempts:
            _login_attempts[ip] = attempts
        else:
            _login_attempts.pop(ip, None)
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

# ─── BORNAGE DES ENDPOINTS DE RELAIS RÉSEAU (voir /app/gateway_status,
# /app/update_relay, /app/update_serve_status, /app/update_serve dans do_GET,
# et logx_update.py pour le contexte complet) ─────────────────────────────
# Ces 4 routes sont volontairement SANS jeton de session (_require_auth) :
# ce sont des appels backend-à-backend entre postes LogX AI distincts (voir
# logx_update._peer_get_json) — l'appelant n'a jamais le jeton propre à CE
# poste, exiger _require_auth casserait donc le mécanisme lui-même. Mais
# sans aucune autre barrière, N'IMPORTE QUEL appareil capable d'atteindre le
# serveur (0.0.0.0 : tout le LAN, voire au-delà si le port est redirigé
# depuis une box/routeur) pouvait déclencher /app/update_relay — une VRAIE
# requête HTTPS sortante vers GitHub — en boucle serrée, sans limite : abus
# possible en relais de bande passante ou épuisement de threads locaux
# (ThreadingHTTPServer, un thread OS par connexion, sans plafond). Deux
# garde-fous complémentaires, cohérents avec le modèle de menace déjà
# documenté ailleurs dans ce fichier (voir _handle_auth_login_post : "un LAN
# non fiable... reste hors du modèle de menace visé ici", donc on ne vise
# PAS à authentifier chaque pair, seulement à exclure internet et les abus
# en rafale) :
#   1) _is_lan_ip : réutilise le même principe que _cors() (origines LAN
#      RFC1918 + boucle locale) mais sur l'IP SOURCE réelle de la connexion
#      TCP (self.client_address, jamais falsifiable par un en-tête HTTP) —
#      bloque tout appelant hors LAN, y compris via port forwarding.
#   2) _relay_rate_limited : fenêtre glissante par IP, même principe que
#      _login_rate_limited ci-dessus, état séparé (une rafale sur l'un ne
#      doit pas geler l'autre).
_LAN_IPV4_RE = re.compile(
    r'^(127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)$')

def _is_lan_ip(ip):
    """True si `ip` (self.client_address[0], jamais un en-tête falsifiable)
    appartient à un bloc privé RFC1918 ou à la boucle locale."""
    return bool(_LAN_IPV4_RE.match(ip or ''))

def _strict_content_length(headers):
    """Même validation stricte que do_POST (voir son commentaire détaillé) :
    rejette un en-tête Content-Length illisible ou plusieurs valeurs
    contradictoires plutôt que de silencieusement retomber sur 0 — un 0 par
    défaut sur un corps réellement présent laisse ses octets non lus sur la
    socket, qui contaminent alors la requête suivante (connexion
    persistante désynchronisée). Réutilisée par _require_auth() et
    _handle_auth_login_post(), qui avant ce correctif refaisaient chacun
    leur propre `int(headers.get('Content-Length',0) or 0)` naïf.
    Renvoie (length, ok) — ok=False signifie : refuser ET fermer la
    connexion (self.close_connection = True) sans tenter de drainer."""
    annonces = [str(v).strip() for v in (headers.get_all('Content-Length') or [])]
    if any(not re.fullmatch(r'[0-9]+', v) for v in annonces) or len(set(annonces)) > 1:
        return 0, False
    return (int(annonces[0]) if annonces else 0), True

def _is_loopback_or_private_host(host, dns_timeout=3):
    """True si `host` (champ de config équipement — CAT/ampli/PowerGenius/
    MySQL testé côté serveur, ex. /rig/connect_test, /amp/test, /pgxl/test,
    /mysql/test) résout vers une adresse locale ou privée, jamais un hôte
    Internet public.

    Cet équipement est TOUJOURS sur le même poste ou le même LAN dans
    l'usage réel de LogX AI — sans ce filtre, ces routes de "test de
    connexion" laissaient un attaquant faire sonder par LE SERVEUR n'importe
    quel hôte Internet de son choix (SSRF), le résultat (connecté / refusé /
    timeout) étant reflété au client : exactement le primitif d'un scan de
    port distant. Contrairement à _is_safe_host (logx_rules_ai.py, qui REJETTE
    le privé/loopback pour un téléchargement de règlement censé viser
    Internet), cette fonction fait l'INVERSE : n'ACCEPTER que le privé/
    loopback, car c'est ici la cible légitime.

    Résolution DNS bornée dans le temps (même motif que
    logx_rules_ai._resolve_host_ips : socket.getaddrinfo() n'est pas couvert
    par un timeout de socket, un DNS muet gèlerait sinon le thread HTTP)."""
    host = (host or '').strip()
    if not host:
        return False
    if host.lower() == 'localhost':
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        pass
    try:
        fut = _FETCH_EXECUTOR.submit(socket.getaddrinfo, host, None)
        infos = fut.result(timeout=dns_timeout)
    except Exception:
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if not (ip.is_private or ip.is_loopback or ip.is_link_local):
            return False
    return True

_RELAY_ATTEMPT_LIMIT = 10
_RELAY_ATTEMPT_WINDOW = 60.0  # secondes
_relay_attempts_lock = threading.Lock()
_relay_attempts = {}  # ip -> [timestamps des appels récents à /app/update_relay ou /app/update_serve]

def _relay_rate_limited(ip):
    """True si `ip` a déjà déclenché _RELAY_ATTEMPT_LIMIT appels à
    /app/update_relay ou /app/update_serve dans la fenêtre glissante — sinon
    enregistre CET appel et renvoie False. Vérification + enregistrement dans
    le MÊME verrou (jamais relâché entre les deux), même précaution que
    _login_rate_limited contre une rafale concurrente qui contournerait la
    limite. Purge aussi, dans ce même verrou, les AUTRES ip devenues inactives
    (dernier appel plus vieux que la fenêtre) — même principe que
    _login_rate_limited : sans ce balayage global, une ip qui appelle une
    fois puis ne revient jamais laisserait son entrée en mémoire à vie."""
    now = time.time()
    with _relay_attempts_lock:
        _purge_stale_ips(_relay_attempts, now, _RELAY_ATTEMPT_WINDOW)
        attempts = [t for t in _relay_attempts.get(ip, ()) if now - t < _RELAY_ATTEMPT_WINDOW]
        if len(attempts) >= _RELAY_ATTEMPT_LIMIT:
            _relay_attempts[ip] = attempts
            return True
        attempts.append(now)
        _relay_attempts[ip] = attempts
        return False

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
# Pool partagé (module-level) pour border le recalcul de score à 3 s dans
# add_qso_to_log() — évite de créer/détruire un fil OS à CHAQUE QSO logué.
# max_workers=4 (pas 1) : calc_qso_value()/logx_wwa.fetch_url() a son propre
# timeout de 10s, plus long que le timeout=3 ci-dessous — avec un seul worker
# partagé, une rafale de QSO logués coup sur coup (pile-up) ferait attendre
# les QSO suivants derrière celui qui est lent. Plusieurs workers gardent le
# partage du pool sans réintroduire ce couplage.
_SCORE_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix='score')


def _tamponner_satellite(qso):
    """Reporte le satellite actif de CONFIG sur le QSO, s'il n'en porte pas.

    Le champ existait déjà en configuration mais son aide le disait elle-même :
    « repère informatif uniquement ». Il devient ici la source de SAT_NAME, donc
    de PROP_MODE=SAT à l'export — sans quoi LoTW crédite un contact TERRESTRE.

    DEUX PRÉCAUTIONS. Un QSO qui porte DÉJÀ un satellite n'est jamais écrasé :
    il peut venir d'un import ADIF ou d'un autre poste, et sa valeur est plus
    sûre qu'un réglage global. Et la valeur « AUTRE » du sélecteur est ignorée :
    envoyer SAT_NAME=AUTRE à LoTW ferait rejeter le FICHIER ENTIER, ce qui est
    pire que ne rien envoyer.
    """
    if qso.get('sat_name'):
        return qso
    # Sous config_lock comme le reste de add_qso_to_log : /config/save REMPLACE
    # current_config en entier, une lecture non protégée pourrait tomber sur
    # l'ancien dictionnaire pendant l'échange.
    with config_lock:
        nom = str(current_config.get('active_satellite') or '').strip().upper()
    if nom and nom != 'AUTRE':
        qso['sat_name'] = nom
    return qso


def add_qso_to_log(qso, force=False):
    """Ajoute un QSO au log partagé avec détection de doublon. Retourne
    (ok, info). Chemin commun à /log/add et au pont WSJT-X."""
    import time as _t
    qso['server_time'] = _t.time()
    _tamponner_satellite(qso)
    now_utc = utcnow()
    # setdefault() ne pose la valeur que si la clé est ABSENTE : une date/heure
    # explicitement vide envoyée par le client (champ vidé côté formulaire)
    # existait déjà comme clé et passait au travers, laissant un QSO sans
    # date/heure valide (export Cabrillo/ADIF cassé pour ce QSO).
    if not qso.get('date'):
        qso['date'] = now_utc.strftime('%Y%m%d')
    if not qso.get('time'):
        qso['time'] = now_utc.strftime('%H:%M')
    key = (str(qso.get('call', '')).upper().strip(),
           str(qso.get('band', '')), str(qso.get('mode', '')).upper())
    # Portée du NOUVEAU QSO (contest+année, voir logx_storage.active_scope_id) —
    # dérivée de ses propres champs contest+date plutôt que du contest_id brut :
    # sans l'année, retravailler la même station/bande sur la même édition d'un
    # concours ANNUEL récurrent une année différente était refusé comme doublon.
    scope_id = qso_scope_id(qso)
    with config_lock:
        simple_mode = current_config.get('usage_mode') == 'simple'
    # Concours à réinitialisation QUOTIDIENNE du doublon (bricks['dupe_reset']
    # == 'daily', ex. WWA §7 : 1 QSO/jour/bande/mode) : le scope_id seul
    # (contest+ANNÉE) ne suffit pas à distinguer un vrai doublon d'un
    # recontact légitime un autre jour de la même édition — même piège que
    # celui déjà résolu pour l'année (voir commentaire ci-dessus), mais à
    # l'échelle du jour. calc_qso_value()/build_ranked_spots() le gèrent déjà
    # côté classement des spots (via done_today_by_band) ; add_qso_to_log()
    # ne le lisait pas du tout avant ce correctif (constat de la passe de
    # vérification du 09/08/2026) — trouvé en relisant réellement le code,
    # pas supposé depuis le nom de la brique.
    _cdef = CONTEST_DEFINITIONS.get(qso.get('contest', ''), {})
    _daily_dupe_reset = resolve_scoring_bricks(_cdef.get('scoring', {})).get('dupe_reset') == 'daily'

    def _find_dup():
        return next((q for q in shared_log
                     if (str(q.get('call', '')).upper().strip(),
                         str(q.get('band', '')),
                         str(q.get('mode', '')).upper()) == key
                     and qso_scope_id(q) == scope_id
                     and (not _daily_dupe_reset
                          or str(q.get('date', '')) == str(qso.get('date', '')))), None)

    dup = None
    # LOGBOOK SIMPLE : recontacter la même station sur la même bande au fil
    # des années est normal (pas de règle "1 QSO/station/bande" hors concours)
    # — le blocage "doublon" n'a de sens que pendant un concours actif.
    if not simple_mode:
        with log_lock:
            dup = _find_dup()
    if dup and not force:
        return False, {'duplicate': True, 'existing': {
            'id': dup.get('id'), 'date': dup.get('date'),
            'time': dup.get('time'), 'operator': dup.get('operator', '')}}
    qso.pop('force', None)
    # L'id n'est PLUS attribué ici : il l'est sous log_lock, dans le même
    # verrou que l'insertion dans shared_log (voir plus bas) — un id lu puis
    # posé hors du verrou peut être distribué deux fois.
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
        qso['points'] = _SCORE_EXECUTOR.submit(score_new_qso, qso).result(timeout=3)
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
        # Re-vérification ATOMIQUE juste avant l'insertion : ferme la fenêtre
        # TOCTOU ouverte par le relâchement du verrou pendant le scoring — sans
        # elle, deux requêtes quasi simultanées pour le même call+bande+mode
        # passent toutes les deux le contrôle de doublon ci-dessus (aucune n'a
        # encore inséré son QSO au moment du contrôle de l'autre).
        if not simple_mode and not force:
            dup2 = _find_dup()
            if dup2:
                return False, {'duplicate': True, 'existing': {
                    'id': dup2.get('id'), 'date': dup2.get('date'),
                    'time': dup2.get('time'), 'operator': dup2.get('operator', '')}}
        # Id attribué ICI, dans le verrou qui couvre aussi l'insertion : c'est
        # la seule façon d'en garantir l'unicité (voir logx_storage
        # .reserve_qso_id_locked). L'id proposé par l'appelant est conservé
        # s'il est libre — les pages client envoient un `id: Date.now()` et
        # logx_cloudsync réinsère les QSO d'un autre poste en gardant leur id,
        # qui est son identité de fusion — mais un id DÉJÀ PRIS (typiquement
        # celui d'un QSO fraîchement importé, l'import réservant autrefois
        # plusieurs secondes d'id futurs) est remplacé plutôt que dupliqué :
        # deux QSO de même id, et /log/delete en efface deux au lieu d'un.
        qso['id'] = reserve_qso_id_locked(qso.get('id'), shared_log)
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

def _prune_typing_state():
    """Retire de typing_state les entrées périmées (verrou déjà tenu par
    l'appelant), même filtre TTL que _active_typing — sans quoi un poste
    éteint sans dernier POST vide y laisserait son entrée à vie."""
    now = time.time()
    for op in [k for k, v in typing_state.items() if now - v.get('ts', 0) > TYPING_STALE_S]:
        del typing_state[op]

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
    with SPOTS_CACHE_LOCK:
        SPOTS_CACHE[str(band)] = s
    print(f"[DATA] {band} MHz: {len(s)} spots (multi-cluster)")
    return s

def _fetch_spots_50_src(no_digi, toggles):
    if not toggles.get('src_f5len', True):
        with SPOTS_CACHE_LOCK:
            SPOTS_CACHE['50'] = []
        return []
    s = fetch_cluster_f5len(50, filter_digital=no_digi)
    with SPOTS_CACHE_LOCK:
        SPOTS_CACHE['50'] = s
    print(f"[DATA] 50 MHz: {len(s)} spots")
    return s

def _fetch_spots_hf_src(callsign, no_digi, toggles):
    """6 sources HF fusionnées et dédupliquées (DXSummit, F5LEN, DXWatch, Telnet,
    DXHeat, navigateur) — chacune désactivable individuellement depuis CONFIG
    (toggles src_dxsummit/src_f5len/src_dxwatch/src_telnet/src_dxheat). Toutes
    actives par défaut (True) si le toggle est absent d'une config existante,
    pour ne rien changer au comportement des utilisateurs qui n'y touchent
    jamais.
    DXHeat n'est PAS restreinte à une bande côté requête (elle ramène HF ET
    VHF/UHF en un seul appel, chaque spot déjà étiqueté avec sa bande réelle
    via _band_from_freq côté logx_clusters) — on la fusionne ici plutôt que
    dans les pipelines VHF/144-432/50 dédiés : le lot 'HF' est le seul déjà
    reclassé par bande à partir de la fréquence de CHAQUE spot dans
    build_ranked_spots (logx_scoring.py), donc un spot VHF/UHF qui s'y trouve
    finit malgré tout dans la bonne bande au moment du scoring. Un doublon
    possible avec les caches 144/432/50 (déjà toléré aujourd'hui : DXSummit-HF
    inclut aussi du 50 MHz sans dédup inter-cache) n'est pas une régression."""
    on = lambda key: toggles.get(key, True)
    s_summit = fetch_dxsummit_hf(filter_digital=no_digi) if on('src_dxsummit') else []
    s_f5len = fetch_f5len_hf(filter_digital=no_digi) if on('src_f5len') else []
    s_dxwatch = fetch_dxwatch_hf(filter_digital=no_digi) if on('src_dxwatch') else []
    s_telnet = fetch_telnet_cluster(callsign=callsign or 'F4GLD', filter_digital=no_digi) if on('src_telnet') else []
    s_dxheat = fetch_dxheat(filter_digital=no_digi) if on('src_dxheat') else []
    s_browser = []
    with browser_spots_lock:
        age = time.time() - browser_spots_ts
        if browser_spots_cache and age < 600:  # valides 10 min
            s_browser = list(browser_spots_cache)
            print(f"[BROWSER-SPOTS] {len(s_browser)} spots (age {int(age)}s)")
        elif browser_spots_cache:
            print(f"[BROWSER-SPOTS] cache perime ({int(age)}s)")
    all_hf = s_summit + s_f5len + s_dxwatch + s_telnet + s_dxheat + s_browser
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
          f"DXWatch:{len(s_dxwatch)} Telnet:{len(s_telnet)} DXHeat:{len(s_dxheat)} Browser:{len(s_browser)})")
    with SPOTS_CACHE_LOCK:
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
        # Les scores ci-dessus n'ont de sens QUE si un concours est
        # sélectionné — sinon le barème retombe sur le repli 1 pt/km et
        # affiche un total qu'aucun règlement ne compte (cf. contest_actif()).
        'contest_actif': contest_actif(cfg),
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
    # Transverter AVANT tout le reste : à partir d'ici, la fréquence manipulée
    # est la fréquence RÉELLE sur l'air. MQTT publie donc lui aussi la vraie
    # fréquence — un écran mural annonçant 144 MHz pendant qu'on trafique en
    # 1296 serait exactement le défaut que ce chantier corrige.
    state = _appliquer_transverter(_rig_state_dict_impl(cfg_snap), cfg_snap)
    try:
        if state.get('enabled') and state.get('ok') and state.get('freq_khz'):
            import logx_mqtt as mqtt_bridge
            if (mqtt_bridge.mqtt_settings(cfg_snap)['enabled']
                    and mqtt_bridge.freq_changed(state['freq_khz'])):
                threading.Thread(target=lambda: mqtt_bridge.publish_rig_freq(
                    cfg_snap, state['freq_khz'], state.get('mode', '')), daemon=True).start()
    except Exception:
        pass
    # Auto-pilotage du commutateur d'antenne par relais (comme PstRotator) :
    # bascule le relais mappé dès que la BANDE change — voir
    # logx_relay.maybe_apply_band, qui déduplique en interne (ne rejoue pas
    # la commutation à chaque poll ~3s tant que la bande ne change pas).
    try:
        if state.get('enabled') and state.get('ok') and state.get('freq_hz'):
            import logx_relay as relay
            band = transverter.bande_depuis_hz(state['freq_hz'])
            if band:
                relay.maybe_apply_band(cfg_snap, band)
    except Exception:
        pass
    return state


def _appliquer_transverter(state, cfg_snap):
    """Convertit la fréquence FI rendue par la radio en fréquence RÉELLE.

    Appliqué ICI, sur le seul point de passage commun aux 4 backends CAT
    (natif, TCI, flrig, rigctld) : chacun rend le même dict {freq_hz, freq_khz},
    et convertir dans chacun d'eux aurait garanti qu'un des quatre soit oublié.
    Sans transverter configuré, la fréquence ressort inchangée.

    `freq_fi_hz` est conservée à part : c'est ce qui est réellement affiché sur
    la radio, utile pour comprendre un écart quand on regarde le poste."""
    if not isinstance(state, dict) or not state.get('ok'):
        return state
    fi = state.get('freq_hz')
    if fi in (None, 0):
        return state
    reelle = transverter.rf_depuis_fi(fi, cfg_snap)
    if reelle != fi:
        state['freq_fi_hz'] = fi
        state['freq_hz'] = reelle
        state['freq_khz'] = round(reelle / 1000.0, 2)
        state['transverter'] = transverter.bande_depuis_hz(reelle)
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
    if cat_settings['enabled'] and cat_settings['mode'] == 'omnirig':
        import logx_omnirig as omnirig
        return omnirig.get_state(cfg_snap)
    if cat_settings['enabled'] and cat_settings['mode'] == 'flex':
        import logx_flexradio as flexradio
        return flexradio.get_state(cfg_snap)
    if cat_settings['enabled'] and cat_settings['mode'] == 'icom_remote':
        import logx_icomremote as icomremote
        return icomremote.get_state(cfg_snap)
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


def _pgxl_state_dict(cfg_snap):
    """État du PowerGenius XL (4O3A) — module séparé de logx_amp.py (voir sa
    docstring : protocole réseau propre, pas un 4e "brand" de _make_driver),
    donc sa propre clé dans /hardware/state plutôt qu'un mélange avec 'amp'."""
    import logx_powergenius as pgxl
    return pgxl.get_state(cfg_snap)


def _acom_state_dict(cfg_snap):
    """État de l'ACOM (série RS-232) — même raisonnement que _pgxl_state_dict()
    ci-dessus : module séparé de logx_amp.py (transport/protocole propres,
    doc communautaire, voir logx_acom.py), sa propre clé dans /hardware/state."""
    import logx_acom as acom
    return acom.get_state(cfg_snap)


# ─── WAIT-AND-POUNCE : le câblage, niveaux 3 et 4 ────────────────────────────
# Ces deux fonctions sont appelées DEPUIS LE THREAD UDP de logx_wsjtx, pas
# depuis un handler HTTP. C'est la seule façon de tenir le niveau 4 : « personne
# devant la radio » veut dire personne pour ouvrir un navigateur, donc rien ne
# peut dépendre d'un client qui interroge.
#
# Le calcul de l'intérêt REUTILISE les fonctions déjà éprouvées de logx_awards
# plutôt que d'en réécrire une variante. Deux réponses différentes à « cette
# station vaut-elle un appel ? » selon qu'on la pose à l'écran ou au moteur
# d'appel, c'est le genre d'incohérence qui fait perdre confiance dans tout le
# reste — c'est exactement le défaut corrigé sur la grille bande × mode.

def _interet_pounce(call, band, mode, grid, cfg_snap):
    """Ce que LogX sait de cette station, sous la forme attendue par le moteur."""
    import logx_awards as awards
    interet = {'nouveau_pays': False, 'besoin_lotw': False,
               'carre_neuf': False, 'nouveau_mult': False}
    with log_lock:
        log_copy = list(shared_log)
    try:
        b = awards.besoin_lotw(call, band, mode, log_copy)
        interet['besoin_lotw'] = bool(b.get('besoin'))
        # « Jamais confirmée nulle part » est le cas fort : l'entité n'est
        # confirmée LoTW sur AUCUNE bande ni AUCUN mode.
        interet['nouveau_pays'] = (b.get('raison') == 'jamais_confirme')
    except Exception:
        pass
    if grid:
        try:
            # active_scope_id vit dans logx_storage, PAS dans logx_awards — il
            # est déjà importé en tête de ce module. Le passer permet à
            # suivi_carres d'appliquer la règle de portée posée par
            # l'utilisateur : en concours, seule la durée du concours compte,
            # mais un carré absent AUSSI du carnet à vie passe devant.
            suivi = awards.suivi_carres([{'call': call, 'grid': grid, 'band': band}],
                                        log_copy, scope_id=active_scope_id(cfg_snap),
                                        bande=band)
            if suivi:
                interet['carre_neuf'] = bool(suivi[0].get('neuf_a_vie'))
                interet['nouveau_mult'] = suivi[0].get('interet', 0) > 0
        except Exception:
            pass
    return interet


def _pounce_sur_decodage(calls, _msg):
    """Un décodage vient d'arriver : faut-il appeler ?

    Sortie IMMÉDIATE si aucune session n'est armée — ce chemin est traversé à
    chaque décodage FT8, soit plusieurs fois par cycle de 15 s, et il ne doit
    rien coûter tant que la fonction n'est pas utilisée.
    """
    import logx_pounce as pounce
    import logx_wsjtx as wsjtx
    if not pounce.session.active:
        return
    if pounce.session.expiree():
        pounce.session.desarmer('duree ecoulee')
        wsjtx.couper_emission(auto_seulement=True)
        print("[POUNCE] Duree ecoulee : session desarmee, emission coupee")
        return
    cfg_snap = dict(current_config)
    # Un SEUL appel à recent_decodes() : il parcourt et purge le cache sous
    # verrou, l'appeler une fois par indicatif serait payé à chaque décodage.
    par_call = {d['call']: d for d in wsjtx.recent_decodes()}
    for call in calls:
        d = par_call.get(call)
        if not d:
            continue
        interet = _interet_pounce(call, d.get('band', ''), d.get('mode', ''),
                                  d.get('grid', ''), cfg_snap)
        avis = pounce.session.decider(d, interet)
        if not avis.get('appeler'):
            continue
        res = wsjtx.repondre_a(call)
        if res.get('ok'):
            # Journalisé APRÈS l'envoi seulement : noter un appel qui a échoué
            # fausserait le plafond et l'historique que l'opérateur relira.
            pounce.session.noter_appel(call, avis.get('motif', ''))
            print("[POUNCE] Appel %s — %s" % (call, avis.get('motif', '')))
        else:
            print("[POUNCE] Appel %s refuse : %s" % (call, res.get('error')))
        return          # un seul appel par décodage : WSJT-X en mène un à la fois


def _pounce_sur_qso(msg):
    """QSO abouti : la station ne doit plus être rappelée."""
    import logx_pounce as pounce
    if pounce.session.active:
        pounce.session.noter_qso(msg.get('call', ''))


def _wsjtx_state_dict(cfg_snap):
    import logx_wsjtx as wsjtx
    settings = wsjtx.wsjtx_settings(cfg_snap)
    if not settings['enabled']:
        return {'enabled': False}
    # Démarrage à chaud (idempotent) : pas besoin de relancer le serveur
    wsjtx.start_listener(
        get_cfg=lambda: dict(current_config),
        add_qso=lambda q: add_qso_to_log(q, force=False)[0],
        port=settings['port'],
        on_decode=_pounce_sur_decodage,
        on_qso=_pounce_sur_qso)
    st = wsjtx.current_status()
    st['enabled'] = True
    st['port'] = settings['port']
    # L'horloge mesurée sur le consensus des stations reçues — la seule
    # référence de temps disponible en expédition, sans NTP. Calcul purement
    # local sur des décodages déjà en mémoire : aucun réseau, aucune IA.
    try:
        st['horloge'] = wsjtx.derive_horloge()
    except Exception:
        st['horloge'] = {'etat': 'aucune_mesure', 'couleur': 'inconnu'}
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
            # BESOIN LoTW en direct : une entité DÉJÀ travaillée mais pas encore
            # confirmée par LoTW sur cette bande/mode reste un besoin pour le
            # DXCC — critère explicite de l'utilisateur (voir besoin_lotw). Ce
            # cas n'était alerté que sur les spots du cluster, jamais sur les
            # décodages FT8/FT4 reçus ici. Dédupliqué contre st['missing'] : une
            # station jamais travaillée y figure déjà, plus fortement.
            st['lotw'] = awards.besoins_lotw_decodes(
                decodes, exclure=[m.get('call') for m in st['missing']],
                shared_log=log_copy, max_n=12)
            # LOCATOR TRACKER : les carrés entendus, neufs ou non. Le carré
            # vient du décodage lui-même (« CQ F4ABC JN18 ») et reste mémorisé
            # tant que la station est active — les messages suivants (-15,
            # RR73, 73) n'en portent pas.
            #
            # La PORTÉE change tout, et c'est un choix de l'utilisateur : en
            # concours l'alerte suit la durée du concours (un carré travaillé
            # en 2019 reste un multiplicateur à faire ce week-end), mais celui
            # qui est EN PLUS absent du carnet à vie passe devant — il vaut
            # multiplicateur ET carré neuf pour les diplômes.
            st['carres'] = awards.suivi_carres(
                decodes, log_copy, scope_id=active_scope_id(cfg_snap))
        else:
            st['missing'] = []
            st['lotw'] = []
            st['carres'] = []
    except Exception:
        st['missing'] = []
        st['lotw'] = []
        st['carres'] = []
    return st


def _rotor_state_dict(cfg_snap):
    import logx_rotor as rotor
    import logx_station as station
    # Le rotor par défaut du parc OU l'ancien rotor unique — sans quoi une
    # station configurée uniquement via le nouvel éditeur de parc voyait son
    # bouton « pointer » masqué (revue 01/08/2026).
    d = station.rotor_defaut(cfg_snap)
    if not d['enabled']:
        return {'enabled': False}
    state = rotor.get_position(d['host'], d['port'], d.get('proto', 'rotctld'))
    state['enabled'] = True
    # Protocole/marque/modèle : l'UI affiche « GS-232 · Yaesu G-5500 » et sait
    # si l'élévation est pertinente (boîtier Az/El).
    state['proto'] = d.get('proto', 'rotctld')
    state['brand'] = d.get('brand', '')
    state['model'] = d.get('model', '')
    info = rotor.model_info(d.get('brand'), d.get('model'))
    state['elevation_capable'] = bool(info and info.get('elevation'))
    # nb_rotors permet à l'UI de proposer un sélecteur quand il y en a plusieurs.
    state['nb_rotors'] = len(station.charger(cfg_snap)['rotors'])
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
        return {'search': lambda q: pota.parks_db.search(q, name_keys=('name', 'location')),
                'lookup': pota.parks_db.get,
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

    # ── CONNEXIONS PERSISTANTES (HTTP/1.1) ───────────────────────────────────
    # En HTTP/1.0 (le défaut de BaseHTTPRequestHandler), le serveur RACCROCHE
    # après chaque réponse : ouvrir une page = autant de connexions TCP que de
    # ressources (HTML + JS + CSS + fetch), et chaque sondage périodique
    # (balises 5 s, spots, statut) en rouvre une. En multi-poste, plusieurs
    # machines multiplient ce va-et-vient — et sous Windows chaque fermeture
    # laisse le port en TIME_WAIT plusieurs minutes. Mesuré ici : sous rafale
    # de connexions simultanées, une petite part d'entre elles échoue
    # (timeout / connexion réinitialisée), ce qui peut figer une page dont un
    # script bloquant n'arrive jamais.
    #
    # En HTTP/1.1 la connexion reste ouverte et sert plusieurs requêtes. Deux
    # conditions IMPÉRATIVES, sans quoi le remède serait pire que le mal :
    #
    #   1. CHAQUE réponse doit délimiter son corps. Tant que le serveur
    #      raccrochait, « fin de connexion » signifiait « fin du corps » ; ce
    #      n'est plus vrai. Une réponse sans Content-Length exact fait attendre
    #      le navigateur INDÉFINIMENT. Toutes les réponses de ce fichier en
    #      envoient un (vérifié une par une) ; les deux seules qui ne le
    #      peuvent pas — relais d'un asset dont la source ne l'annonce pas, et
    #      flux interrompu en cours d'envoi — forcent close_connection (voir
    #      _stream_asset_relay / _stream_verified_file).
    #
    #   2. Le corps d'une requête POST doit être ENTIÈREMENT lu, sinon les
    #      octets restants seraient interprétés comme la requête suivante sur
    #      la même connexion. Les deux chemins qui refusent AVANT de lire le
    #      corps (jeton absent, corps trop volumineux) ferment donc la
    #      connexion — voir _require_auth() et le plafond MAX_BODY de do_POST.
    #
    # timeout : un fil d'exécution est mobilisé par connexion ouverte. Sans
    # délai d'inactivité, des onglets qui gardent la ligne épuiseraient les
    # fils. Au-delà, BaseHTTPRequestHandler met fin à la connexion de
    # lui-même (socket.timeout -> close_connection), le navigateur en rouvre
    # une au besoin : invisible pour l'utilisateur.
    protocol_version = 'HTTP/1.1'
    timeout = 30

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

        # Recherche plein-texte dans les pages (widget de la nav, logx_search.js)
        # — texte visible seulement (titres/contenu des pages HTML), rien de
        # secret, pas de jeton requis (même logique que /network/info ci-dessous).
        if path == '/search':
            from urllib.parse import parse_qs, urlparse
            import logx_search
            q = parse_qs(urlparse(self.path).query).get('q', [''])[0]
            self._json({'query': q, 'results': logx_search.search(q)})
            return

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
            _prune_stale_connected_peers()
            self._json({
                'local_ip': local_ip,
                'port': PORT,
                'url_logbook': f'http://{local_ip}:{PORT}/logx_logbook.html',
                'url_terrain': f'http://{local_ip}:{PORT}/logx_mobile.html',
                'peers': len(connected_peers),
                # Version de CE serveur — capturée une fois par le client à son
                # chargement de page (voir logx_logbook.js initShareLink()) pour
                # savoir "sa propre version" et la comparer plus tard à celle,
                # toujours à jour, que renvoie /log/status.
                'app_version': APP_VERSION,
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
            # Comme /debug/errors ci-dessus : le drapeau debug autorise
            # l'EXISTENCE de la route, mais l'accès à des données potentiellement
            # privées (ici du contenu de chat ON4KST obtenu avec les identifiants
            # stockés côté serveur) reste soumis au jeton de session.
            if not self._require_auth():
                return
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
            with connected_peers_lock:
                connected_peers[client_ip] = time.time()
            _prune_stale_connected_peers()
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
            # Version LOGICIELLE du poste qui poll (?ver=, voir peer_versions
            # ci-dessus) : purement déclarative, jamais utilisée pour filtrer
            # ou refuser quoi que ce soit — juste enregistrée pour affichage.
            # Filtrée par PEER_VERSION_RE : une valeur non conforme (HTML/JS
            # injecté par un appareil du LAN, chaîne géante) est IGNORÉE, pas
            # stockée — voir le commentaire de PEER_VERSION_RE.
            client_ver = qs.get('ver', [''])[0].strip()
            if client_ver and not PEER_VERSION_RE.fullmatch(client_ver):
                client_ver = ''
            if client_ver:
                with peer_versions_lock:
                    peer_versions[client_ip] = {'version': client_ver, 'last_seen': time.time()}
                # Purge TTL au fil de l'eau : les polls sains des postes
                # présents évacuent les entrées des postes partis, même si
                # personne ne consulte jamais /log/status (borne la mémoire).
                _prune_stale_peer_versions()
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
            # Seul l'aperçu (peek) est sans effet de bord et reste ouvert au
            # LAN ; la consommation réelle du compteur (allocate_next_serial)
            # exige le jeton de session, comme toute autre mutation d'état
            # côté serveur — sinon n'importe quel appareil du LAN peut brûler
            # des numéros de série réels en boucle sans jamais loguer de QSO.
            if not peek and not self._require_auth():
                return
            # Portée du concours actif (cfg_scope_id, même règle que /log/list) :
            # sans elle, le max était calculé sur TOUT shared_log — le 1er QSO
            # d'un nouveau concours héritait du max d'un concours précédent
            # resté en log (ex. 801 au lieu de 001), transmis sur l'air sans
            # recours (champ readOnly côté opérateur, purge des anciens
            # concours opt-in depuis le commit 4d91f6a).
            scope_id = cfg_scope_id(self._cfg_snapshot())
            serial = (_storage.peek_next_serial(band, scope_id) if peek
                      else _storage.allocate_next_serial(band, scope_id))
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
                # Sinon interroger HamQTH — cet appel réseau (potentiellement
                # plusieurs secondes) reste HORS du verrou, pour ne pas
                # bloquer les autres threads dessus.
                result = lookup_hamqth(base)
                if result and result.get('locator'):
                    # Persister dans calldb.json — FUSION, jamais de remplacement
                    # total (une entrée locale peut déjà porter un 'dept' REF
                    # que HamQTH ignore ; l'écraser cassait le tableau de chasse).
                    # Lecture-modification-écriture sous calldb_lock EN ENTIER
                    # (pas seulement l'écriture finale) : sinon deux lookups
                    # concurrents (deux indicatifs différents en même temps)
                    # lisent le même état initial et la seconde écriture écrase
                    # la modification de la première. On relit le fichier ICI,
                    # sous le verrou — après le lookup réseau — plutôt que de
                    # réutiliser une lecture faite avant l'appel HamQTH, qui
                    # aurait pu devenir périmée pendant les quelques secondes
                    # de l'appel (même patron que /calldb/update et
                    # _enrich_calldb dans logx_qrz.py).
                    if os.path.exists(calldb_path):
                        with calldb_lock:
                            with open(calldb_path, 'r', encoding='utf-8') as f:
                                db2 = json.load(f)
                            entry = db2.setdefault('calls', {}).setdefault(base, {})
                            entry['locator'] = result['locator']
                            if result.get('country'):
                                entry['country'] = result['country']
                            # lock déjà tenu ci-dessus (calldb_lock n'est pas
                            # réentrant) : on n'en redemande pas un second à
                            # save_json_atomic.
                            save_json_atomic(calldb_path, db2, lock=None, compact=True)
                    self._json({'call': base, 'locator': result['locator'], 'country': result.get('country',''), 'source': 'hamqth'})
                    return
                self._json({'call': base, 'locator': '', 'source': 'none'})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Status réseau + spots clusters
        if path == '/log/status':
            # peer_list : un poste par IP ayant déjà pollé /log/list?ver=,
            # avec la version qu'il a déclarée et l'horodatage (epoch) de son
            # dernier contact — voir peer_versions ci-dessus. app_version =
            # version RÉELLE de CE serveur, à l'instant présent (contrairement
            # à la version déclarée par un poste, jamais figée) : c'est la
            # référence à laquelle chaque poste (soi-même y compris) doit se
            # comparer côté client pour détecter un écart avant un événement.
            # Purge TTL AVANT lecture : un poste parti (ou revenu sous une
            # autre IP DHCP) ne doit pas laisser un badge "versions
            # différentes" fantôme permanent — voir _prune_stale_peer_versions.
            _prune_stale_peer_versions()
            _prune_stale_connected_peers()
            with peer_versions_lock:
                peer_list = [
                    {'ip': ip, 'version': info.get('version', ''), 'last_seen': info.get('last_seen', 0)}
                    for ip, info in peer_versions.items()
                ]
            peer_list.sort(key=lambda p: p['ip'])
            # Copie sous verrou avant sérialisation JSON : SPOTS_CACHE reçoit
            # une nouvelle clé par thread de refresh pendant qu'un autre poste
            # peut interroger /log/status au même instant — sans ce verrou,
            # une insertion de clé pendant l'itération de json.dumps() lève
            # RuntimeError("dictionary changed size during iteration").
            with SPOTS_CACHE_LOCK:
                spots_snapshot = dict(SPOTS_CACHE)
            self._json({
                'peers':       len(connected_peers),
                'qso_count':   len(shared_log),
                'spots':       spots_snapshot,
                'app_version': APP_VERSION,
                'peer_list':   peer_list,
            })
            return

        # Test direct fetch DXSummit HF
        if path == '/debug/spots':
            # Ces routes de diagnostic déclenchent des dizaines de vraies
            # requêtes sortantes (jusqu'à ~90 s pour /debug/cluster) : le
            # jeton de session écarte un appareil du LAN totalement étranger,
            # et _relay_rate_limited (déjà utilisé pour /app/update_relay,
            # voir plus haut) borne aussi un poste authentifié qui boucle.
            if not self._require_auth():
                return
            if _relay_rate_limited(self.client_address[0]):
                self._json({'error': 'Trop de requêtes /debug/* — réessaie dans une minute'}, 429)
                return
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
            # Même garde que /debug/spots ci-dessus : jusqu'à ~90 s de requêtes
            # sortantes par appel (9 HTTP + 7 telnet), à border par le jeton de
            # session ET la limite de fréquence, pas seulement par le drapeau
            # debug global.
            if not self._require_auth():
                return
            if _relay_rate_limited(self.client_address[0]):
                self._json({'error': 'Trop de requêtes /debug/* — réessaie dans une minute'}, 429)
                return
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
            # Booléen seulement (pas la valeur) : une URL de proxy peut embarquer
            # des identifiants (http://user:pass@host), exposés en clair sinon à
            # tout poste authentifié du LAN.
            results['env_proxy'] = {
                'HTTP_PROXY':  'défini' if os.environ.get('HTTP_PROXY') else 'non défini',
                'HTTPS_PROXY': 'défini' if os.environ.get('HTTPS_PROXY') else 'non défini',
                'http_proxy':  'défini' if os.environ.get('http_proxy') else 'non défini',
                'https_proxy': 'défini' if os.environ.get('https_proxy') else 'non défini',
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
                self._json({'error': str(e)}, 500)
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

        # Bulletin hebdomadaire REF (rubrique "Commission des concours" :
        # soirées d'activité THF + concours DX du week-end) — cache 7 jours,
        # jamais de fetch synchrone dans cette requête (voir logx_ref_bulletin).
        if path == '/data/ref_bulletin':
            data = ref_bulletin.REF_BULLETIN_CACHE or {}
            self._json({
                'year': data.get('year'),
                'week': data.get('week'),
                'text': data.get('text', ''),
                'source_url': data.get('source_url', REF_BULLETIN_URL),
                'updated': data.get('updated', ''),
            })
            return

        # Forcer refresh bulletin REF
        if path == '/data/refresh_ref_bulletin':
            threading.Thread(target=refresh_ref_bulletin, daemon=True).start()
            self._json({'ok': True, 'message': 'Rafraîchissement bulletin REF lancé'})
            return

        # Calendrier avec prochaines dates calculées automatiquement
        if path.startswith('/data/calendar'):
            calendar_data = calc_all_dates()
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
                    'exported_at': utcnow().isoformat(),
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
                if time.time() - _coach_dxmaps_ts > 600:
                    _refresh_coach_dxmaps_async()
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
            # Nudge événementiel (UNE phrase d'action) : calculé UNIQUEMENT si la
            # page le demande (?nudges=1) — sinon le serveur ne dépense rien et
            # les stations qui n'ont pas activé l'option ne paient aucun calcul.
            if (parse_qs(urlparse(self.path).query).get('nudges') or [''])[0] == '1':
                try:
                    state['nudge'] = coach.coach_nudge(state, lang)
                except Exception:
                    state['nudge'] = None
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

        # Réponse DÉTERMINISTE (zéro LLM) à un sujet du chat — repli HORS-LIGNE :
        # quand l'IA est injoignable (expédition sans internet), les boutons
        # rapides du chat basculent ici. Réutilise build_coach_state (aucune
        # logique de score recopiée) et le formateur answer_text. Aucun réseau :
        # le K vient du cache seul, tout le reste est calculé depuis le log.
        if path == '/coach/answer':
            import logx_coach as coach
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            topic = (q.get('topic') or [''])[0]
            lang = (q.get('lang') or ['fr'])[0]
            cfg_snap = self._cfg_snapshot()
            k_index = None
            try:
                from logx_clusters import get_solar_cached
                k_index = (get_solar_cached() or {}).get('k_index')
            except Exception:
                pass
            with log_lock:
                log_copy = list(shared_log)
            state = coach.build_coach_state(cfg_snap, log_copy, None,
                                            mult_spots_count=None, k_index=k_index, lang=lang)
            text = coach.answer_text(state, topic, lang)
            self._json({'ok': bool(text), 'topic': topic, 'text': text})
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

        # Progression de la re-résolution en masse démarrée par
        # /log/bulk_resolve/start — pollé par le client (voir logx_logbook.js).
        if path == '/log/bulk_resolve/status':
            import logx_callbook as callbook
            self._json(callbook.bulk_resolve_status())
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
            # Concours à réinitialisation QUOTIDIENNE (bricks['dupe_reset']
            # == 'daily', ex. WWA) : même garde que add_qso_to_log() — sans
            # elle, un indicatif déjà travaillé un jour précédent de la même
            # édition était signalé "doublon" à tort par cet indicateur à la
            # frappe, en désaccord avec la vraie détection au moment du log.
            _cdef_check = CONTEST_DEFINITIONS.get(cfg_snap.get('contest', ''), {})
            _daily_dupe_reset = resolve_scoring_bricks(_cdef_check.get('scoring', {})).get('dupe_reset') == 'daily'
            today_str = utcnow().strftime('%Y%m%d')
            # LOGBOOK SIMPLE : pas de règle "1 QSO/station/bande" hors concours.
            if cfg_snap.get('usage_mode') != 'simple':
                with log_lock:
                    dup = any(
                        str(q.get('call', '')).upper().strip() == call
                        and str(q.get('band', '')) == band
                        and (not mode or str(q.get('mode', '')).upper() == mode)
                        and qso_scope_id(q) == scope_id
                        and (not _daily_dupe_reset or str(q.get('date', '')) == today_str)
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

        # État d'un audit IA du log (lancé par POST /log/audit, tourne en fond).
        if path.startswith('/log/audit/state'):
            from urllib.parse import parse_qs, urlparse
            aid = (parse_qs(urlparse(self.path).query).get('id') or [''])[0]
            with _audit_lock:
                a = dict(_audit_jobs.get(aid) or {'status': 'unknown'})
            a['id'] = aid
            self._json(a)
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
            mode = (qp.get('mode', [''])[0]).strip()
            with log_lock:
                log_copy = list(shared_log)
            h = awards.history(call, log_copy)
            h['new_one'] = awards.new_one(call, band, log_copy)
            # « Pas confirmé LoTW » n'est PAS la même question que « jamais
            # contacté » : un pays travaillé dix fois mais jamais confirmé par
            # LoTW ne compte toujours pas pour le DXCC. Calculé au grain
            # entité × bande × mode, celui auquel se décide un appel.
            h['lotw_need'] = awards.besoin_lotw(call, band, mode, log_copy)
            # État US / province canadienne. En ADIF, STATE porte la
            # « subdivision administrative primaire » : c'est le même champ des
            # deux côtés de la frontière (MA, TX… mais aussi ON, QC, BC). Seul
            # le compteur WAS filtre sur les 50 états — l'affichage, lui, montre
            # ce qui est connu, quel que soit le pays.
            h['state'] = next((q.get('state') for q in log_copy
                               if str(q.get('call', '')).upper() == call
                               and q.get('state')), '')
            # Cette station uploade-t-elle vers LoTW ? Décisif quand l'alerte
            # ci-dessus dit « pas confirmé LoTW » : si le correspondant n'y est
            # pas, le créneau ne se comblera jamais avec lui.
            try:
                import logx_lotwusers as lotw
                h['lotw_user'] = lotw.is_lotw_user(call)
                h['lotw_last'] = lotw.last_upload(call)
            except Exception:
                h['lotw_user'], h['lotw_last'] = None, ''
            self._json(h)
            return

        # École de CW : une série d'entraînement tirée de l'index du poste, avec
        # l'échange RÉELLEMENT demandé par le concours choisi. Aucun réseau,
        # aucune IA, aucun coût — et rien ne part sur l'air : le morse est
        # généré dans le navigateur, dans le casque.
        if path.startswith('/cw/serie'):
            from urllib.parse import parse_qs, urlparse
            import logx_callhistory as callhistory
            import logx_cw_ecole as ecole
            qp = parse_qs(urlparse(self.path).query)
            try:
                n = max(1, min(60, int(qp.get('n', ['20'])[0])))
            except ValueError:
                n = 20
            cfg_snap = self._cfg_snapshot()
            cdef = CONTEST_DEFINITIONS.get(cfg_snap.get('contest', ''), {})
            with log_lock:
                log_copy = list(shared_log)
            idx = callhistory.build_index(log_copy)
            # Les locators et départements viennent du log RÉEL : les échanges
            # entendus à l'entraînement ressemblent alors à ceux du concours,
            # au lieu d'être tous identiques.
            locs = [q.get('locator') for q in log_copy if q.get('locator')][-40:]
            deps = [q.get('num_rcvd') for q in log_copy if q.get('num_rcvd')][-40:]
            self._json({
                'serie': ecole.serie(idx, cdef, n=n, locators=locs, depts=deps,
                                     zone=cfg_snap.get('cq_zone')),
                'contest': cfg_snap.get('contest', ''),
                'exchange': cdef.get('exchange', ''),
                'indicatifs_disponibles': len(idx),
            })
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

        # Garde-fou « multiplicateur fantôme » : la zone CQ SAISIE correspond-elle
        # à ce que cty.dat attend pour cet indicatif ? DÉTERMINISTE et instantané
        # (aucun LLM, aucun réseau) — l'IA n'intervient qu'à la demande, côté
        # client, via /proxy/ai (bouton « est-ce plausible ? »). Une zone bustée
        # compte comme mult puis est retirée au checking : pénalité nette évitée
        # AU MOMENT de la saisie.
        if path.startswith('/exchange/check'):
            from urllib.parse import parse_qs, urlparse
            import logx_dxcc as dxcc
            qp = parse_qs(urlparse(self.path).query)
            call = (qp.get('call', [''])[0]).upper().strip()
            value = (qp.get('value', [''])[0]).strip()
            kind = (qp.get('kind', ['cq_zone'])[0]).strip()
            if kind == 'cq_zone':
                res = dxcc.verifier_zone_cq(call, value)
                res['kind'] = 'cq_zone'
                res['ok'] = True
                self._json(res)
            else:
                self._json({'ok': False, 'match': None, 'kind': kind})
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
            contest = (qp.get('contest', [''])[0] or cfg_snap.get('contest') or '').strip().upper()
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

        # Carrés QRA travaillés, pour la carte VUCC. ?band=144 restreint à une
        # bande : le VUCC s'obtient bande par bande, jamais toutes bandes
        # confondues — une carte « toutes bandes » ne correspondrait à aucun
        # diplôme réel.
        # Découpage CW / numérique / phonie d'une bande — pour dessiner la
        # réglette des fenêtres de surveillance. Lecture seule, aucun accès au
        # log : pollé par autant de fenêtres que l'opérateur en ouvre.
        if path.startswith('/data/bande_segments'):
            from urllib.parse import parse_qs, urlparse
            import logx_awards as awards
            qp = parse_qs(urlparse(self.path).query)
            self._json(awards.segments_bande((qp.get('band', [''])[0]).strip())
                       or {'segments': []})
            return

        if path.startswith('/awards/carres'):
            from urllib.parse import parse_qs, urlparse
            import logx_awards as awards
            qp = parse_qs(urlparse(self.path).query)
            bande = (qp.get('band', [''])[0]).strip()
            with log_lock:
                log_copy = list(shared_log)
            self._json(awards.carres_travailles(log_copy, bande))
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

        # SATELLITES : quand passe-t-il, et où pointer.
        #
        # UN SEUL APPEL rend le prochain passage, la liste des suivants, la
        # position instantanée, le Doppler et L'ÂGE DU JEU TLE. Cet âge n'est
        # pas un détail de journal : un TLE se dégrade, et une prédiction
        # calculée sur un jeu de trois semaines est fausse sans le dire. Il
        # part donc avec la réponse, systématiquement.
        #
        # AUCUN ACCÈS RÉSEAU ICI : le téléchargement des TLE se fait en tâche
        # de fond (logx_serveur), le handler ne lit que le cache disque. Sur une
        # expédition sans Internet, cet endpoint continue de répondre avec le
        # dernier jeu connu — dégradé, mais annoncé comme tel.
        if path.startswith('/data/sat'):
            from urllib.parse import parse_qs, urlparse
            import logx_sat_passes as satp
            qp = parse_qs(urlparse(self.path).query)
            cfg_snap = self._cfg_snapshot()
            lat, lon = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            if lat is None:
                self._json({'available': False,
                            'error': 'Locator manquant ou invalide (page CONFIG)'})
                return
            alt_m = cfg_snap.get('altitude', 0) or 0
            nom = (qp.get('sat', [''])[0] or cfg_snap.get('satellite', '')
                   or 'ISS (ZARYA)').strip()
            try:
                heures = max(1, min(168, float(qp.get('hours', ['24'])[0])))
            except ValueError:
                heures = 24
            try:
                el_min = max(0.0, min(89.0, float(qp.get('min_el', ['0'])[0])))
            except ValueError:
                el_min = 0.0
            try:
                freq = float(qp.get('freq', ['145.8'])[0])
            except ValueError:
                freq = 145.8

            cache = satp.charger_tle()
            out = {'available': False, 'sat': nom,
                   'tle_age': satp.age_tle(cache),
                   'satellites': satp.satellites_connus(cache)}
            # État du suivi rotor : la boucle de fond ÉCRIT, ce handler LIT —
            # aucun appel réseau ici, la dernière position rotor connue vient
            # de la boucle elle-même (logx_sat_track).
            try:
                import logx_sat_track as strack
                out['tracking'] = strack.etat_suivi()
                import logx_rotor as _rot
                out['rotor_enabled'] = _rot.rotor_settings(cfg_snap)['enabled']
            except Exception:
                pass
            if not cache:
                out['error'] = ("Aucun jeu TLE en cache — il se télécharge au "
                                "démarrage du serveur (CelesTrak).")
                self._json(out)
                return
            # Chaque source est isolée : un satellite absent du jeu ne doit pas
            # emporter la position, ni l'inverse.
            try:
                r = satp.passages(cache, nom, lat, lon, alt_m, heures=heures,
                                  elevation_min=el_min)
                out['passages'] = r.get('passages', [])
                out['available'] = bool(r.get('available'))
                if r.get('error'):
                    out['error'] = r['error']
            except Exception as e:
                out['error'] = str(e)
            try:
                pos = satp.position(cache, nom, lat, lon, alt_m)
                if pos.get('available'):
                    out['position'] = pos
                    out['doppler_hz'] = satp.doppler_hz(pos['range_rate_ms'], freq)
                    out['freq_mhz'] = freq
            except Exception:
                pass
            self._json(out)
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
            _dop = eme.doppler_shift_hz(lat, lon, freq_mhz, cfg_snap.get('altitude', 0) or 0)
            # PERTE DE TRAJET, jointe au Doppler. path_loss_db() existait déjà
            # mais n'avait AUCUN appelant : une fonction fausse de 123 dB que
            # personne ne voyait — corrigée par l'équation radar, elle sert
            # enfin à quelque chose. La distance vient de la position lunaire
            # du moment, donc le chiffre suit le cycle périgée/apogée (≈ 2 dB).
            try:
                _pos = eme.moon_position(lat, lon, cfg_snap.get('altitude', 0) or 0)
                _d = _pos.get('distance_km') if isinstance(_pos, dict) else None
                if _d:
                    _dop['path_loss_db'] = eme.path_loss_db(_d, freq_mhz)
                    _dop['distance_km'] = _d
            except Exception:
                pass    # la perte de trajet est un bonus : jamais au prix du Doppler
            self._json(_dop)
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
            with log_lock:
                log_copy = list(shared_log)
            self._json(dep.departments_progress(log_copy, cfg_scope_id(cfg_snap)))
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
            worked_bands = co.worked_bands_by_country(log_copy, cfg_scope_id(cfg_snap))
            self._json({'expeditions': dxp.fetch_dxpeditions(worked_names, worked_bands)})
            return

        # Panneau CHASSE : mêmes annonces NG3K que /data/dxpeditions, mais
        # annotées 'status' (active/upcoming) + fréquence live si repérées
        # sur le cluster déjà agrégé pour le reste de l'appli (voir
        # logx_dxpeditions.fetch_dxpeditions_chasse) — les terminées sont
        # retirées, CHASSE montre ce qu'on peut encore travailler.
        if path == '/data/dxpeditions_active':
            import logx_dxpeditions as dxp
            import logx_countries as co
            cfg_snap = self._cfg_snapshot()
            with log_lock:
                log_copy = list(shared_log)
            progress = co.countries_progress(log_copy, cfg_scope_id(cfg_snap))
            worked_names = {x['country'] for grp in progress['by_continent'].values()
                            for x in grp if x['worked']}
            worked_bands = co.worked_bands_by_country(log_copy, cfg_scope_id(cfg_snap))
            self._json({'expeditions': dxp.fetch_dxpeditions_chasse(
                worked_names, _spots_from_caches(), worked_bands=worked_bands)})
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

        # Météo du point haut (open-meteo, sans clé) — sécurité matériel /P.
        # Lecture cache seule ici (jamais bloquant) : le rafraîchissement
        # réseau se fait en tâche de fond, comme get_solar_cached()/
        # get_muf_cached() — voir logx_weather.get_weather_cached().
        if path == '/data/weather':
            import logx_weather as weather
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            self._json(weather.get_weather_cached(my_ll[0], my_ll[1]))
            return

        # Prévision tropo (ducting) — gradient de réfractivité (open-meteo niveaux)
        if path == '/data/tropo':
            import logx_tropo as tropo
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            self._json(tropo.get_tropo_cached(my_ll[0], my_ll[1]))
            return

        # Calendrier météores (Meteor Scatter VHF) — déterministe, pas de réseau
        if path == '/data/meteors':
            import logx_meteors as met
            self._json(met.ms_quality())
            return

        # Indice d'ouverture VHF (Es et au-delà) — statistique sur le flux de
        # spots déjà collecté (voir logx_es_opening.py), pas une prévision
        # physique : {'50': {...}, '144': {...}}.
        if path == '/data/es_opening':
            import logx_es_opening as eso
            cfg_snap = self._cfg_snapshot()
            self._json(eso.opening_summary(cfg_snap.get('locator', '')))
            return

        # « Écouter ce spot » / « s'écouter » depuis le logbook : UN récepteur,
        # choisi côté serveur (annuaire en cache, AUCUN réseau ici), l'URL déjà
        # réglée sur la fréquence. Avec lat/lon (position du DX spotté) le tri
        # privilégie la proximité du DX ; sans, c'est « s'écouter » : le
        # meilleur SNR près du QTH. Route AVANT /data/websdr : ce chemin en est
        # un préfixe.
        if path == '/data/websdr/ecouter':
            import logx_websdr as websdr
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            def _qf(nom):
                # float('nan') et float('1e400') réussissent SANS exception :
                # sans isfinite, pres_de=(nan, nan) atteignait haversine(), qui
                # lève ValueError sur round(nan) — la requête mourait alors sans
                # aucune réponse HTTP (connexion fermée, traceback sur stderr).
                # L'API n'est pas authentifiée et le logbook est servi en WiFi
                # au reste de l'équipe : n'importe quel poste pouvait forger
                # l'URL. Rien n'oblige à passer par le client officiel.
                try:
                    v = float(qs.get(nom, [''])[0])
                except (TypeError, ValueError):
                    return None
                return v if math.isfinite(v) else None
            khz, lat, lon = _qf('khz'), _qf('lat'), _qf('lon')
            mode = (qs.get('mode', [''])[0] or '').strip()
            # Le cluster donne bien plus souvent une GRILLE que des
            # coordonnées : sans ce repli, « écouter ce spot » retombait en
            # silence sur le tri « près de chez moi » et l'opérateur croyait
            # entendre ce que le DX entend.
            if (lat is None or lon is None):
                loc = (qs.get('loc', [''])[0] or '').strip()
                if loc:
                    lat, lon = locator_to_latlon(loc)
            cfg_snap = self._cfg_snapshot()
            a = websdr.annuaire(cfg_snap)
            pres_de = (lat, lon) if lat is not None and lon is not None else None
            r = websdr.meilleur_recepteur(a['stations'], pres_de=pres_de)
            # url_ecoute rend '' pour une URL au schéma refusé : sans ce test,
            # ok=True porterait une URL vide et le bouton ouvrirait un onglet
            # sur la page courante au lieu de dire qu'il n'a rien trouvé.
            lien = websdr.url_ecoute(r, khz, mode) if r else ''
            if not r or not lien:
                self._json({'ok': False})
                return
            # La distance affichée est celle qui a guidé le choix : au DX pour
            # un spot, au QTH pour s'écouter (déjà dans dist_km via annuaire).
            d = r.get('dist_km')
            if pres_de is not None and r.get('lat') is not None:
                d = round(haversine(pres_de[0], pres_de[1], r['lat'], r['lon']))
            # `pres_du_dx` dit au client CE QU'IL A OBTENU. Sans ce drapeau,
            # un spot sans position faisait retomber le choix sur « près de
            # chez moi » sans que rien ne le signale : le bouton promettait
            # d'entendre ce que le DX entend et donnait tout autre chose.
            self._json({'ok': True, 'nom': r.get('nom'), 'snr': r.get('snr'),
                        'dist_km': d, 'url': lien,
                        'pres_du_dx': pres_de is not None})
            return

        # Annuaire de récepteurs WebSDR distants — liste statique, pas de réseau
        if path == '/data/websdr':
            # UN appel = tout l'annuaire (~880 stations) + l'âge du jeu vivant.
            # AUCUN appel réseau ici : la tâche de fond (logx_serveur) écrit
            # les caches, ce handler LIT. ~350 Ko de JSON — c'est une page
            # qu'on ouvre, pas un poll : acceptable, et le client filtre en
            # local sans re-demander.
            import logx_websdr as websdr
            cfg_snap = self._cfg_snapshot()
            a = websdr.annuaire(cfg_snap)
            # `suggestion` : le meilleur récepteur près du QTH — le bouton
            # « s'écouter » du logbook n'a alors qu'à lire ce champ.
            try:
                a['suggestion'] = websdr.meilleur_recepteur(a['stations'])
            except Exception:
                a['suggestion'] = None
            self._json(a)
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

        # ── Mise à jour réseau local (voir logx_update.py, docstring du module) ─
        # B) Passerelle : ce poste a-t-il un accès internet confirmé récemment
        # (donc capable de relayer une requête GitHub pour un autre poste) ?
        # Interrogé PAR UN AUTRE poste du LAN (backend-à-backend, pas depuis un
        # navigateur) — pas de jeton de session (comme /app/update_check),
        # mais borné au LAN (voir _is_lan_ip ci-dessus) : simple booléen, sans
        # donnée sensible, mais sonder ce poste depuis internet n'a aucune
        # raison d'être autorisé.
        if path == '/app/gateway_status':
            if not _is_lan_ip(self.client_address[0]):
                self._json({'error': 'Réservé au réseau local'}, 403)
                return
            import logx_update as upd
            self._json(upd.gateway_status())
            return

        # B) Relais RÉEL : ce poste (qui SE DÉCLARE passerelle, voir ci-dessus)
        # fait sa propre requête HTTPS vers l'asset GitHub officiel (tag/
        # plateforme validés côté logx_update.resolve_relay_asset — jamais une
        # URL fournie par l'appelant, anti-SSRF) et relaie les octets EN FLUX,
        # jamais un fichier de son propre disque. Le poste appelant revérifie
        # le SHA-256 reçu contre SA PROPRE référence locale (voir
        # logx_update._do_download_via_network) — ce relais n'envoie même pas
        # de digest, il n'est pas la source de vérité. Borné au LAN + limité
        # en fréquence par IP (voir _is_lan_ip/_relay_rate_limited ci-dessus) :
        # c'est la route qui déclenche une VRAIE requête sortante vers
        # GitHub, jamais à exposer à internet ni à laisser rejouer en boucle.
        if path == '/app/update_relay':
            ip = self.client_address[0]
            if not _is_lan_ip(ip):
                self._json({'error': 'Réservé au réseau local'}, 403)
                return
            if _relay_rate_limited(ip):
                self._json({'error': 'Trop de requêtes de relais, réessaie plus tard'}, 429)
                return
            import logx_update as upd
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            tag = (qs.get('tag', [''])[0] or '').strip()
            platform = (qs.get('platform', [''])[0] or '').strip()
            ok, info = upd.resolve_relay_asset(tag, platform)
            if not ok:
                self._json({'error': info}, 400)
                return
            self._stream_asset_relay(info['asset_url'])
            return

        # C) SECOURS uniquement : état du fichier déjà téléchargé + VÉRIFIÉ
        # (hash SHA-256, voir logx_update.py) que CE poste peut servir à un
        # pair sans internet du tout — jamais un chemin arbitraire. Borné au
        # LAN (voir _is_lan_ip ci-dessus), même raisonnement que gateway_status.
        if path == '/app/update_serve_status':
            if not _is_lan_ip(self.client_address[0]):
                self._json({'error': 'Réservé au réseau local'}, 403)
                return
            import logx_update as upd
            self._json(upd.serve_status())
            return

        # C) Service RÉEL du fichier déjà vérifié — TOUJOURS le même chemin
        # interne (logx_update._download['path']), jamais un paramètre client
        # (aucune traversée de répertoire possible). Le poste appelant
        # revérifie le SHA-256 reçu contre SA PROPRE référence locale, exactement
        # comme pour /app/update_relay — voir docstring de logx_update.py pour
        # le compromis de sécurité de ce chemin de secours. Borné au LAN +
        # limité en fréquence par IP, même raisonnement que /app/update_relay
        # (ce fichier peut faire plusieurs dizaines de Mo, servi en flux).
        if path == '/app/update_serve':
            ip = self.client_address[0]
            if not _is_lan_ip(ip):
                self._json({'error': 'Réservé au réseau local'}, 403)
                return
            if _relay_rate_limited(ip):
                self._json({'error': 'Trop de requêtes de relais, réessaie plus tard'}, 429)
                return
            import logx_update as upd
            info = upd.serve_status()
            if not info.get('available'):
                self._json({'error': 'Aucun exécutable vérifié disponible sur ce poste'}, 404)
                return
            self._stream_verified_file(upd.get_download_status().get('path', ''))
            return

        # Raccourci bureau proposé au premier lancement figé (voir
        # logx_shortcut.py) : indique au logbook s'il doit afficher la
        # bannière "Créer un raccourci ?". Pas d'auth requise (comme
        # /app/update_check) — c'est un simple booléen, sans donnée sensible.
        if path == '/shortcut/status':
            import logx_shortcut as shortcut
            self._json({'show': shortcut.should_offer()})
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
            # Converti en float (et validé fini) comme partout ailleurs dans ce
            # fichier où des coordonnées de requête sont acceptées (/data/
            # websdr/ecouter, /data/sat...) — lat_q/lon_q restaient des CHAÎNES
            # brutes ici, ce qui cassait adapter['nearby'](lat, lon) (TypeError
            # dans le calcul haversine) dès que le client les fournissait.
            def _qf(name):
                try:
                    v = float((qs.get(name) or [''])[0])
                except (TypeError, ValueError):
                    return None
                return v if math.isfinite(v) else None
            lat, lon = _qf('lat'), _qf('lon')
            if lat is None or lon is None:
                cfg_snap = self._cfg_snapshot()
                lat, lon = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            max_km = _qf('max_km')
            if max_km is None or max_km <= 0:
                max_km = 100.0
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

        # Flux SSE d'une analyse IA : pousse la réponse au fil de l'eau (token
        # par token) au lieu d'attendre le texte complet (~120 s figés avant).
        # La GÉNÉRATION tourne dans le thread de fond de /agent/analyze (elle
        # survit au changement d'onglet) ; ce handler ne fait que TAILER le
        # buffer. Le client retombe sur /agent/analyze/state (polling) si
        # l'EventSource coupe — le buffer streamé y est aussi visible.
        if path == '/agent/analyze/stream':
            from urllib.parse import parse_qs, urlparse
            aid = (parse_qs(urlparse(self.path).query).get('id') or [''])[0]
            self._sse_agent_stream(aid)
            return

        # État d'une chasse assistée (tool-use) : texte + action proposée à
        # confirmer (voir POST /agent/act).
        if path.startswith('/agent/act/state'):
            from urllib.parse import parse_qs, urlparse
            aid = (parse_qs(urlparse(self.path).query).get('id') or [''])[0]
            with _act_lock:
                a = dict(_act_jobs.get(aid) or {'status': 'unknown'})
            a['id'] = aid
            self._json(a)
            return

        # État d'une stratégie pile-up FT8 (voir POST /wsjtx/strategy).
        if path.startswith('/wsjtx/strategy/state'):
            from urllib.parse import parse_qs, urlparse
            aid = (parse_qs(urlparse(self.path).query).get('id') or [''])[0]
            with _strat_lock:
                a = dict(_strat_jobs.get(aid) or {'status': 'unknown'})
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
            when = utcnow() + datetime.timedelta(hours=hour)
            cells = paths.prop_grid(my_ll[0], my_ll[1], band, when, solar, step=15)
            self._json({'ok': True, 'band': band, 'hour': hour,
                        'when_utc': when.strftime('%H:%M'), 'step': 15,
                        'my': {'lat': my_ll[0], 'lon': my_ll[1]}, 'cells': cells})
            return

        # Prédiction VOACAP point-à-point (vrai moteur scientifique, pas
        # l'heuristique de logx_paths ci-dessus) : ?dx=<locator ou indicatif
        # resoluble> obligatoire, ?mode=CW|SSB|DIGITAL et ?power=<watts>
        # optionnels. Windows uniquement -- voacap_available() renvoie une
        # erreur claire ailleurs plutot que de planter.
        if path.startswith('/data/voacap'):
            from urllib.parse import parse_qs, urlparse
            import logx_voacap as voacap
            qp = parse_qs(urlparse(self.path).query)
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            if my_ll[0] is None:
                self._json({'ok': False, 'error': 'Locator station non défini'})
                return
            dx_input = (qp.get('dx') or [''])[0].strip()
            if not dx_input:
                self._json({'ok': False, 'error': 'Paramètre dx manquant (locator ou indicatif)'})
                return
            dx_ll = locator_to_latlon(dx_input)
            if dx_ll[0] is None:
                from logx_dxcc import lookup as dxcc_lookup
                info = dxcc_lookup(dx_input) or {}
                dx_ll = (info.get('lat'), info.get('lon'))
            if dx_ll[0] is None:
                self._json({'ok': False, 'error': f"Impossible de localiser « {dx_input} » (ni locator, ni indicatif reconnu)"})
                return
            mode = (qp.get('mode') or ['SSB'])[0].upper()
            if mode not in voacap.REQUIRED_SNR_DB:
                mode = 'SSB'
            try:
                power_w = float((qp.get('power') or ['100'])[0])
            except ValueError:
                power_w = 100.0
            result = voacap.predict(
                tx_lat=my_ll[0], tx_lon=my_ll[1], rx_lat=dx_ll[0], rx_lon=dx_ll[1],
                mode=mode, power_w=power_w,
                tx_label=cfg_snap.get('callsign', '') or 'TX', rx_label=dx_input,
            )
            self._json(result)
            return

        # Écran mural d'expédition : agrégation du log commun en temps réel.
        # Config PUBLIQUE (whitelist stricte, AUCUN secret) — permet à chaque
        # poste d'expédition d'hériter du concours, de la station et du mode
        # expédition partagés, sans jamais exposer mots de passe / clés API.
        if path == '/config':
            cfg_snap = self._cfg_snapshot()
            safe = {k: cfg_snap.get(k, '') for k in (
                'callsign', 'callsign_contest', 'locator', 'contest', 'usage_mode',
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
            # Repli documente juste au-dessus : plusieurs modules (logx_qrz,
            # logx_qsl, logx_rig, logx_rotor, logx_wsjtx, logx_mqtt) y lisent
            # des identifiants en clair quand ils ne sont pas (encore) dans la
            # config en memoire -- ce n'est PAS un fichier public, contrairement
            # a ce que cette route supposait avant ce correctif (aucune garde,
            # a la difference de sa jumelle /config/secrets juste en dessous).
            # _require_auth() n'exige pas un mot de passe REGLE : il exige un
            # rc_token valide, distribue automatiquement des le premier GET
            # d'une page .html tant qu'aucun mot de passe n'est configure --
            # meme frontiere que toutes les autres routes sensibles, la page
            # mobile (qui charge une .html avant ce fetch) n'est pas affectee.
            if not self._require_auth():
                return
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
            # cfg_scope_id() encapsule déjà la bonne règle (voir logx_storage.py,
            # même logique que /log/list et le Worked Matrix) : '' en LOGBOOK
            # SIMPLE ou si aucun concours n'est sélectionné (mode EXPÉDITION
            # sans concours -> le mur reste "tout ce qui est loggé", cf.
            # test_wall_state_ignore_contest_mismatch) ; sinon le concours
            # réellement actif -> le mur ne montre alors QUE ses QSO (et donc
            # ses bandes, calculées à partir des mêmes entrées filtrées).
            contest_id = cfg_snap.get('contest') if cfg_scope_id(cfg_snap) else None
            self._json(wall.wall_state(log_copy, cfg_snap, contest_id=contest_id))
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

        # Dégradations réseau à signaler DISCRÈTEMENT côté client (barre de
        # statut, logx_statusbar.js) : ces mécanismes existent déjà côté
        # serveur (disjoncteur callbook, échecs solaires consécutifs, dernier
        # échec Cloud Sync) mais restaient invisibles en dehors des print()
        # console — l'opérateur ne savait jamais pourquoi une fiche indicatif
        # ou la météo solaire ne se rafraîchissait plus. Lecture seule :
        # callbook et solaire rendent l'état déjà calculé en mémoire ;
        # cs.status() touche le dossier de sync (isdir + glob) mais avec une
        # attente BORNÉE (STATUS_SCAN_TIMEOUT + cache, logx_cloudsync.py) —
        # sans cette borne, un NAS/partage SMB injoignable gelait CE thread
        # ~21 s à chaque poll (timeout SMB Windows), précisément le cas que
        # la pastille doit signaler. Pollable à intervalle rapproché.
        if path == '/data/network_status':
            import logx_callbook as callbook
            import logx_cloudsync as cs
            import logx_mysql_sync as mysql
            from logx_clusters import solar_status
            self._json({
                'callbook': callbook.circuit_status(),
                'solar': solar_status(),
                'cloudsync': cs.status(self._cfg_snapshot()),
                'mysql_sync': mysql.status(self._cfg_snapshot()),
            })
            return

        # Propagation : indices solaires N0NBH + MUF réelle KC2G (caches 15 min,
        # lecture seule ici — le rafraîchissement réseau se fait en tâche de fond).
        if path == '/data/propagation':
            from logx_clusters import get_solar_cached, get_muf_cached
            cfg_snap = self._cfg_snapshot()
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            solar = get_solar_cached()
            muf = get_muf_cached(my_ll[0], my_ll[1]) if my_ll[0] else get_muf_cached()
            # Verdict par bande calculé DEPUIS LE QTH (élévation solaire aux
            # deux bouts, MUF de l'ionosonde la plus proche). Il remplace le
            # `fréquence <= MUF` que faisait la page : la MUF est la borne
            # HAUTE, et sans borne basse le 160 m passait pour ouvert en plein
            # midi. Calculé ici, en Python, où il est testable — et non plus
            # dupliqué dans le JavaScript de la page.
            etat_bandes = None
            if my_ll[0] is not None:
                try:
                    from logx_paths import etat_bandes_hf
                    etat_bandes = etat_bandes_hf(my_ll[0], my_ll[1],
                                                 solar={'solar': solar or {},
                                                        'muf': muf or {}})
                except Exception:
                    etat_bandes = None
            self._json({'solar': solar, 'muf': muf, 'etat_bandes': etat_bandes})
            return

        # Need list structurée : les spots du dernier refresh évalués au barème
        # du concours actif et triés par valeur (nouveaux mults en tête) —
        # AUCUN re-fetch réseau, aucune IA : lecture des caches, pollable.
        # ─── FOCUS BANDE : tout ce qu'on sait d'UNE bande, + où aller ────────
        # DEMANDE UTILISATEUR : « une seconde page qui affiche l'ensemble des
        # éléments que le programme a en sa possession lorsqu'une bande est
        # choisie » — cluster, carrés manquants, propagation, concours actifs
        # sur cette bande ET ce mode, suggestions, band map. Plus le classement
        # de TOUTES les bandes : « qu'y a-t-il sur 20 m » est utile, « où
        # devrais-je être » l'est davantage.
        #
        # UN SEUL APPEL pour six informations : cette page est faite pour
        # rester ouverte sur un 2e écran. Six requêtes toutes les 15 s, c'est
        # six fois plus de connexions à tenir pour la même chose — et le
        # serveur a déjà tout en cache ici.
        if path.startswith('/data/focus'):
            from urllib.parse import parse_qs, urlparse
            import logx_focus as focus
            from logx_scoring import build_ranked_spots
            qp = parse_qs(urlparse(self.path).query)
            cfg_snap = self._cfg_snapshot()
            bande = (qp.get('band', [''])[0] or '').strip()
            mode = (qp.get('mode', [''])[0] or '').strip()

            import logx_awards as _aw
            ranked, meta = build_ranked_spots({}, _spots_from_caches(), cfg_snap)
            spots = []
            for s in ranked:
                sc = s.get('scoring', {})
                _khz = freq_en_khz(s.get('freq', ''), s.get('band', ''))
                spots.append({
                    'call': s.get('call', ''), 'band': s.get('band', ''),
                    'freq': _khz,
                    # Le cluster n'annonce pas le mode de façon fiable : on le
                    # déduit de la fréquence, avec la MÊME table que la
                    # réglette de bande. Sans ce champ, choisir CW ou SSB ne
                    # changeait rien à la liste affichée.
                    'mode': s.get('mode') or _aw.mode_depuis_frequence(_khz),
                    # Spot situé hors des bandes amateur françaises — cas
                    # courant et légitime : une station de région 2 à 7,250 MHz
                    # est en règle chez elle. Le spot est CONSERVÉ (l'entendre
                    # est instructif) mais marqué : sans ça, un clic dessus
                    # commande à la radio un QSY hors bande, sans un mot.
                    'hors_bande': _aw.hors_bande_france(_khz),
                    'time': s.get('time', ''), 'info': s.get('info', ''),
                    'spotter': s.get('spotter', ''),
                    'dist_km': s.get('dist_km', 0),
                    'dx_country': sc.get('dx_country', ''),
                    'new_mult': bool(sc.get('new_mult')),
                    'already_done': bool(sc.get('already_done')),
                    'value': s.get('value_total', 0),
                    'explanation': sc.get('explanation', ''),
                })

            # Ouvertures : même source que /data/openings, sans refaire l'appel.
            regions = []
            try:
                import logx_paths as paths
                from logx_clusters import get_solar_cached, get_muf_cached
                my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
                if my_ll[0] is not None:
                    solar = {'solar': get_solar_cached() or {},
                             'muf': get_muf_cached(my_ll[0], my_ll[1])}
                    regions = paths.all_regions(my_ll[0], my_ll[1], solar=solar) or []
            except Exception:
                regions = []   # propagation indisponible ≠ page cassée

            with log_lock:
                log_copy = list(shared_log)

            # Bandes proposées : TOUT le plan de bandes, dans l'ordre des
            # fréquences — plus celles du concours et celles où un spot tombe.
            # Se limiter aux bandes du concours rendait la page borgne dès
            # qu'aucun concours ne tournait, ou qu'il n'en utilisait que deux.
            bandes_concours = [str(b) for b in (cfg_snap.get('bands') or [])
                               if str(b).strip()]
            bandes = focus.bandes_a_proposer(bandes_concours, spots, bande)

            calendrier = []
            try:
                cal = calc_all_dates()
                for cid, cdef in CONTEST_DEFINITIONS.items():
                    info = cal.get(cid, {})
                    calendrier.append({
                        'id': cid, 'name': cdef.get('name', cid),
                        'date': info.get('date', ''),
                        'start_utc': cdef.get('start_utc', '0000'),
                        'duration_h': cdef.get('duration_h', 0),
                        'bands': cdef.get('bands', []), 'modes': cdef.get('modes', []),
                        'exchange': cdef.get('exchange', ''),
                    })
            except Exception:
                calendrier = []

            # Carrés : /awards/carres renvoie les carrés TRAVAILLÉS
            # ({'g','n','conf','bands'}), pas les manquants. On appelle donc
            # SANS filtre de bande — sinon on ne recevrait que ceux déjà faits
            # ici — et on en déduit les cibles : faits ailleurs, pas ici.
            carres = []
            try:
                import logx_awards as awards
                res = awards.carres_travailles(log_copy, '')
                carres = focus.carres_a_faire_sur_la_bande(res.get('squares') or [], bande)
            except Exception:
                carres = []

            # « Les propositions de contact IA » : parmi les stations SPOTTÉES,
            # celles qui apporteraient un pays ou un département JAMAIS
            # travaillé À VIE — pas seulement un multiplicateur du concours en
            # cours. Même source que les suggestions proactives du coach.
            #
            # ATTENTION AU CHAMP `band` : dans spotted_new_ones il contient le
            # nom de la SOURCE du spot (« cluster »…), pas une bande — un
            # héritage de logx_awards. Filtrer dessus vidait la carte à tous
            # les coups. On déduit donc la bande de la FRÉQUENCE.
            suggestions = []
            try:
                import logx_awards as awards
                for n in awards.spotted_new_ones(log_copy, _spots_from_caches()) or []:
                    b = focus.bande_depuis_freq(n.get('freq'), bandes)
                    n = dict(n, band=b or '')
                    if bande and b and b != focus._bande(bande):
                        continue
                    suggestions.append(n)
            except Exception:
                suggestions = []

            self._json({
                'ok': True,
                'band': bande, 'mode': mode,
                'bandes': bandes,
                'suggestions': suggestions,
                'classement': focus.classer_bandes(
                    bandes, spots=spots, regions=regions, log=log_copy,
                    bandes_concours=bandes_concours),
                # Bande PUIS mode : le mode ne filtrait rien jusqu'ici, faute
                # de champ `mode` sur les spots.
                'spots': focus.filtrer_par_mode(
                    [s for s in spots
                     if not bande or focus._bande(s.get('band')) == focus._bande(bande)],
                    mode),
                # Score d'ouverture POUR CETTE BANDE, calculé ici : /data/openings
                # ne chiffre que la meilleure bande de chaque région, et la page
                # affichait « · » pour toutes les autres.
                'regions': [dict(r, score_bande=focus.score_ouverture_region(r, bande))
                            for r in regions if isinstance(r, dict)],
                'concours': focus.concours_actifs(calendrier, bande=bande, mode=mode),
                'carres_manquants': carres[:60],
                'contest_actif': (meta or {}).get('contest_actif', False),
            })
            return

        if path == '/data/spots_ranked':
            from logx_scoring import build_ranked_spots
            import logx_alerts as alerts
            import logx_awards as awards
            cfg_snap = self._cfg_snapshot()
            ranked, meta = build_ranked_spots({}, _spots_from_caches(), cfg_snap)
            my_ll = locator_to_latlon(cfg_snap.get('locator', '') or 'JN15XC')
            # Toutes les correspondances (pas seulement les 40 affichées) : une
            # règle d'alerte doit pouvoir signaler un spot même hors du top
            # valeur affiché — les critères d'alerte ne sont pas ceux du score.
            full_entries = []
            for s in ranked:
                sc = s.get('scoring', {})
                dx_ll = locator_to_latlon(s.get('locator', ''))
                # Fréquence RAMENÉE EN kHz. Les sources ne s'accordent pas sur
                # l'unité (DXSummit HF et DXHeat en kHz, DXSummit VHF en MHz),
                # si bien que ce champ n'en avait aucune de fixe et qu'aucun
                # écran ne pouvait le lire juste. Un seul point de conversion,
                # ici, pour les six pages qui consomment cet endpoint —
                # voir logx_clusters.freq_en_khz.
                _khz = freq_en_khz(s.get('freq', ''), s.get('band', ''))
                entry = {
                    'call': s.get('call', ''), 'band': s.get('band', ''),
                    'freq': _khz,
                    'locator': s.get('locator', ''),
                    'lat': s.get('lat'), 'lon': s.get('lon'),
                    'dist_km': s.get('dist_km', 0), 'time': s.get('time', ''),
                    'source': s.get('source', ''), 'info': s.get('info', ''),
                    # Qui a posté le spot : jusqu'ici la donnée existait dans
                    # le cache cluster mais mourait ici. C'est pourtant elle
                    # qui dit si la liaison annoncée ressemble à la mienne —
                    # un JA qui spotte une VK décrit un chemin JA-VK.
                    'spotter': s.get('spotter', ''),
                    # Mode annoncé par la source quand elle en a un (DXHeat,
                    # DXSummit…), sinon DÉDUIT de la fréquence (même repli que
                    # /data/focus, voir logx_awards.mode_depuis_frequence) : le
                    # bouton « écouter ce spot » ouvre alors le WebSDR dans la
                    # bonne modulation au lieu de retomber en SSB par défaut.
                    'mode': s.get('mode') or awards.mode_depuis_frequence(_khz),
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
            # Utilisateur LoTW ou non : inutile de courir après une station qui
            # n'uploade jamais, le QSO ne sera jamais confirmé et ne comptera
            # jamais pour le DXCC. Annoté en UNE passe pour toute la liste
            # (voir logx_lotwusers.annoter). 'lotw' vaut None tant que la liste
            # n'est pas téléchargée — « on ne sait pas » n'est pas « non ».
            try:
                import logx_lotwusers as lotw
                lotw.annoter(full_entries)
            except Exception:
                pass
            # Besoin DXCC non confirme LoTW sur CE creneau bande x mode : les
            # fenetres de surveillance par bande le surlignent. On ANNOTE sans
            # filtrer — elles montrent tout ce qui est spotte, masquer le reste
            # priverait l'operateur de la vue d'ensemble qu'il vient chercher.
            try:
                import logx_awards as awards
                with log_lock:
                    log_copy = list(shared_log)
                awards.annoter_besoin_lotw(full_entries, log_copy)
            except Exception:
                pass
            alert_matches = alerts.check_alerts(cfg_snap.get('alert_rules'), full_entries)
            # Filtre d'affichage. L'ORDRE des trois opérations est le fond du
            # sujet : les alertes sont évaluées AVANT (elles doivent voir tout
            # le cluster, cf. le commentaire plus haut), le filtre s'applique
            # ENSUITE, et la coupe à 40 vient EN DERNIER. Filtrer après la
            # coupe ne servirait à rien — c'est justement parce qu'on coupe
            # qu'il faut d'abord écarter. Les spots retenus par une alerte
            # traversent le filtre, marqués hors_filtre (logx_spotfilter).
            visibles, comptes_filtre = full_entries, {}
            try:
                import logx_spotfilter as spotfilter
                calls_alertes = [(m.get('spot') or {}).get('call', '')
                                 for m in alert_matches]
                for e in full_entries:
                    e['spotter_continent'] = spotfilter.continent_spotteur(e)
                visibles, comptes_filtre = spotfilter.filtrer(
                    full_entries, cfg_snap.get('spot_filter'), calls_alertes)
                # Les réglages effectifs repartent avec la réponse : l'écran se
                # synchronise sur la vérité du serveur au premier rafraîchisse-
                # ment, sans requête supplémentaire ni ordre de chargement à
                # respecter — et en multi-poste, un réglage changé sur un poste
                # apparaît sur les autres au tick suivant.
                comptes_filtre['reglages'] = spotfilter.reglages_valides(
                    cfg_snap.get('spot_filter'))
            except Exception:
                pass        # un filtre en panne montre tout, il ne cache rien
            self._json({'spots': visibles[:40], 'meta': meta,
                        'alert_matches': alert_matches, 'filtre': comptes_filtre})
            return

        # État de la session d'appel automatique : minuterie restante, appel en
        # cours, journal de ce qui est parti. Consultable depuis N'IMPORTE quel
        # poste — au niveau 4 l'opérateur n'est pas devant la radio, mais il
        # doit pouvoir regarder ce qu'elle fait depuis son téléphone.
        if path == '/pounce/state':
            import logx_pounce as pounce
            # Une session dont la minuterie est écoulée pendant que rien ne
            # décodait doit se désarmer ICI aussi : sinon elle resterait
            # « active » à l'écran, sans plus jamais l'être en fait.
            if pounce.session.expiree():
                pounce.session.desarmer('duree ecoulee')
            self._json(pounce.session.etat())
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
        # SO2R : la vue de la config suit le FOCUS, sinon l'état affiché reste
        # celui de la radio 1 même après bascule sur la radio 2 (Ctrl+Espace).
        if path == '/rig/state':
            import logx_so2r as so2r
            self._json(_rig_state_dict(so2r.config_radio_active(self._cfg_snapshot())))
            return

        # Band map Search & Pounce : les stations que l'opérateur a entendues
        # lui-même. Côté serveur, donc partagées entre postes — la station
        # entendue depuis le poste 144 est visible du poste 432.
        # SO2R : quelle radio emet, et ce qu'on ecoute. Etat cote serveur,
        # donc identique sur toutes les pages ouvertes.
        if path == '/so2r/state':
            import logx_so2r as so2r
            etat = so2r.focus()
            etat['configure'] = so2r.parametres(self._cfg_snapshot())['enabled']
            etat['tx'] = so2r.tx_actif()
            self._json(etat)
            return

        if path == '/bandmap/local':
            import logx_bandmap as bm
            self._json({'ok': True, 'spots': bm.spots()})
            return

        # Quels emplacements DVK sont réellement enregistrés (et leur durée) —
        # côté serveur, donc identiques sur tous les postes du réseau.
        if path == '/voice/slots':
            import logx_voicekeyer as vk
            self._json({'ok': True, 'slots': vk.messages_disponibles()})
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

        # Scope CI-V 0x27 (panadapter natif Icom, large bande, sans matériel
        # supplémentaire) : disponible seulement en CAT natif sur un modèle
        # qui publie effectivement ce flux (voir MODELES_SCOPE_CIV) — appelé
        # une fois au chargement de logx_panadapter.html pour savoir si
        # l'option "CI-V natif" doit apparaître dans le sélecteur de source.
        if path == '/rig/scope_available':
            import logx_cat as cat
            import logx_so2r as so2r
            self._json(cat.scope_civ_available(so2r.config_radio_active(self._cfg_snapshot())))
            return

        # Une ligne de spectre scope CI-V déjà réassemblée (475 pixels,
        # amplitude 0-160) — pollée par logx_panadapter.html quand la source
        # CI-V est active. ok=False (radio muette, hors CAT natif, paquets
        # incomplets...) reste un 200 : c'est un état de polling normal, pas
        # une erreur serveur — même convention que /rig/state.
        if path == '/rig/scope_line':
            import logx_cat as cat
            import logx_so2r as so2r
            self._json(cat.scope_line(so2r.config_radio_active(self._cfg_snapshot())))
            return

        # Panadapter TCI (3e source, après audio universel et scope CI-V
        # Icom) : disponible seulement en pilotage TCI actif (voir
        # logx_tci.tci_spectrum_available) — appelé une fois au chargement de
        # logx_panadapter.html pour savoir si l'option "TCI" doit apparaître
        # dans le sélecteur de source.
        if path == '/rig/tci_spectrum_available':
            import logx_tci as tci
            import logx_so2r as so2r
            self._json(tci.tci_spectrum_available(so2r.config_radio_active(self._cfg_snapshot())))
            return

        # Une ligne de spectre TCI déjà calculée côté serveur (FFT pure
        # Python sur le flux IQ brut, échelle 0-255) — pollée par
        # logx_panadapter.html quand la source TCI est active. ok=False
        # (buffer pas encore plein, flux pas démarré...) reste un 200 :
        # même convention que /rig/scope_line et /rig/state.
        if path == '/rig/tci_spectrum_line':
            import logx_tci as tci
            import logx_so2r as so2r
            self._json(tci.tci_spectrum_line(so2r.config_radio_active(self._cfg_snapshot())))
            return

        # Détections de branchement en attente (watcher de fond, indice passif
        # VID:PID/numéro de série — jamais appliqué sans confirmation en un
        # clic côté UI). Pollé par CONFIG toutes les ~2s.
        if path == '/rig/pending_detections':
            import logx_cat as cat
            self._json({'detections': cat.get_pending_detections()})
            return

        # Rotor d'antenne (rotctld) : position courante — pollée par le logbook
        # La station physique : antennes, rotors, amplis, et ce qui sert sur
        # une bande donnée. Un seul appel, aucune I/O — les écrans (CONFIG,
        # logbook, band map) y lisent la même vérité.
        if path.startswith('/station'):
            import logx_station as station
            from urllib.parse import parse_qs, urlparse
            cfg_snap = self._cfg_snapshot()
            st = station.charger(cfg_snap)
            rep = dict(st)
            rep['resume'] = station.resume(st)
            bande = (parse_qs(urlparse(self.path).query).get('bande', [''])[0]).strip()
            if bande:
                choix = cfg_snap.get('antenne_par_bande')
                a = station.antenne_active(st, bande, choix)
                r = station.rotor_pour_bande(st, bande, choix)
                m = station.ampli_pour_bande(st, bande, choix)
                rep['pour_bande'] = {
                    'bande': bande, 'antenne': a, 'rotor': r, 'ampli': m,
                    'choix_possibles': station.antennes_pour_bande(st, bande),
                }
            self._json(rep)
            return

        if path == '/rotor/state':
            self._json(_rotor_state_dict(self._cfg_snapshot()))
            return

        # Catalogue des marques/modèles de rotor, pour les listes déroulantes de
        # CONFIG (marque -> modèles -> protocole + élévation). Statique, aucune
        # config : sert juste à ce que l'opérateur reconnaisse SON rotor.
        if path == '/rotor/models':
            import logx_rotor as rotor
            self._json({'brands': rotor.catalog()})
            return

        # SECRETS DE CONFIG (mots de passe / clés API / jetons) : servis SÉPARÉMENT
        # du reste de la config, et seulement au client authentifié qui les demande
        # explicitement — pour que le CLIENT n'ait plus besoin de les garder en
        # clair dans localStorage['logx_config'] (audit sécurité) juste pour
        # pré-remplir ces champs au rechargement de la page. Les champs NON
        # secrets continuent d'être mis en cache localStorage comme avant (rapide,
        # fonctionne hors-ligne) ; seuls ceux-ci transitent par cet endpoint,
        # relu à chaque chargement de la page CONFIG.
        if path == '/config/secrets':
            if not self._require_auth():
                return
            cfg_snap = self._cfg_snapshot()
            # Même liste que logx_crypto.SECRET_FIELDS (chiffrement au repos) —
            # une seule source de vérité, pour ne jamais diverger.
            self._json({f: cfg_snap.get(f, '') for f in logx_crypto.SECRET_FIELDS})
            return

        # Annuaire de nœuds DX cluster publics, pour le sélecteur CONFIG.
        if path == '/data/clusters':
            import logx_clusters as clusters
            self._json({'nodes': clusters.cluster_catalog()})
            return

        # SYNCHRO LAN DIRECTE : export du log pour qu'un poste PAIR le tire et
        # fusionne (logx_lan_sync). Servi UNIQUEMENT si la synchro LAN est activée
        # — sinon un poste n'expose rien de plus qu'aujourd'hui. GET non protégé
        # PAR DÉFAUT, comme /log/status : même modèle que l'écran multi-poste déjà
        # ouvert à tout le réseau local. Un jeton d'équipe optionnel
        # (lan_sync_token, communiqué hors-bande entre postes) restreint cet accès
        # quand il est configuré — voir logx_lan_sync._lan_token, qui l'ajoute déjà
        # en ?token= sur le GET émis par pull_and_merge().
        if path == '/log/lan/export':
            cfg_snap = self._cfg_snapshot()
            if str(cfg_snap.get('lan_sync_enabled', '')) not in ('1', 'true', 'True', 'on'):
                self._json({'enabled': False, 'qsos': []})
                return
            import logx_lan_sync as lan
            expected = lan._lan_token(cfg_snap)
            if expected:
                import hmac as _hmac
                from urllib.parse import parse_qs, urlparse as _uparse
                got = (parse_qs(_uparse(self.path).query).get('token') or [''])[0]
                if not _hmac.compare_digest(got, expected):
                    self._json({'enabled': False, 'qsos': [], 'error': 'Jeton invalide'}, 403)
                    return
            with log_lock:
                qsos = list(shared_log)
            self._json({'enabled': True, 'iid': lan._my_iid(),
                        'callsign': cfg_snap.get('callsign_contest') or cfg_snap.get('callsign') or '',
                        'qsos': qsos})
            return

        # État de la synchro LAN (pairs découverts), pour l'UI CONFIG/statut.
        if path == '/log/lan/peers':
            import logx_lan_sync as lan
            self._json({'peers': lan.peers()})
            return

        # État matériel groupé : rig+amp+wsjtx+rotor en UNE requête plutôt que 4
        # séparées. Le logbook pollait chacun individuellement à cadence rapide
        # (3-4s) — jusqu'à 4 connexions/cycle pour de petits payloads, un coût
        # non négligeable quand un antivirus inspecte chaque connexion locale.
        # Les 4 endpoints individuels restent disponibles tels quels (utilisés
        # aussi par logx_propagation.html/logx_scope.html).
        if path == '/hardware/state':
            import logx_so2r as so2r
            # SO2R : seule la clé 'rig' dépend du focus (cat_* est remappé) —
            # amp/wsjtx/rotor/pgxl ne lisent pas ces clés, le remap est donc
            # sans effet pour eux, inutile de dupliquer cfg_snapshot().
            cfg_snap = so2r.config_radio_active(self._cfg_snapshot())
            self._json({
                'rig': _rig_state_dict(cfg_snap),
                'amp': _amp_state_dict(cfg_snap),
                'wsjtx': _wsjtx_state_dict(cfg_snap),
                'rotor': _rotor_state_dict(cfg_snap),
                'pgxl': _pgxl_state_dict(cfg_snap),
                'acom': _acom_state_dict(cfg_snap),
            })
            return

        # Liste des archives de concours (dossiers permanents)
        if path == '/log/archives':
            import logx_archive as arch
            self._json({'archives': arch.list_archives()})
            return

        # "Score à battre" : meilleur QSO count / meilleur score déjà réalisés
        # pour CE concours parmi les éditions archivées (?contest=<id>) --
        # affiché à la sélection du concours en CONFIG.
        if path.startswith('/log/archives/best'):
            from urllib.parse import parse_qs, urlparse
            import logx_archive as arch
            qp = parse_qs(urlparse(self.path).query)
            contest_id = (qp.get('contest') or [''])[0].strip()
            best = arch.best_for_contest(contest_id)
            self._json(best or {'ok': False, 'error': 'Aucune édition archivée pour ce concours'})
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

        # Planning de roulement des opérateurs (écran mural) : trié par heure
        # de début, voir logx_storage.shifts_sorted().
        if path == '/shifts/list':
            from logx_storage import shifts_sorted
            self._json({'shifts': shifts_sorted()})
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
            # Neutralise tout caractère qui pourrait casser l'en-tête
            # Content-Disposition (CR/LF, guillemets — injection d'en-tête) :
            # seuls les caractères légitimes d'un indicatif/id de concours
            # (lettres/chiffres/tiret) sont conservés. `call` vient de
            # /config/save (protégé par jeton) mais rien n'y contraint son
            # format, et cette route d'export n'est elle-même pas protégée.
            call = re.sub(r'[^A-Z0-9\-]', '', call) or 'LOG'
            contest_id_safe = re.sub(r'[^A-Z0-9\-]', '', str(contest_id or 'ALL').upper()) or 'ALL'
            if path.endswith('cabrillo'):
                from logx_storage import qtc_log, qtc_lock
                cdef = CONTEST_DEFINITIONS.get(contest_id, {})
                with qtc_lock:
                    qtc_series = _scope_filtered(qtc_log, cfg_snap)
                body = export.build_cabrillo(qsos, cdef, cfg_snap, qtc_series).encode('utf-8')
                fname = f"{call}_{contest_id_safe}.cbr"
            else:
                body = export.build_adif(qsos, cfg_snap).encode('utf-8')
                fname = f"{call}_{contest_id_safe}.adi"
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
            self._security_headers()
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
        # CSRF via same-site-mais-port-different : SameSite=Strict n'empêche
        # PAS un tiers colocalisé sur la même adresse IP (nue, sans domaine
        # public) mais un port différent de recevoir le cookie rc_token — la
        # notion de « site » de SameSite ignore le port. Sans ce garde-fou,
        # une requête CORS « simple » (Content-Type text/plain, donc SANS
        # préflight OPTIONS, donc jamais bloquée par _cors() qui ne fait
        # qu'échoir des en-têtes sur la RÉPONSE) suffisait à déclencher
        # AVEUGLÉMENT n'importe quelle route d'écriture protégée, y compris
        # /auth/set_password. Exiger application/json force un préflight
        # CORS pour tout appelant cross-origin : _cors() refuse alors la
        # requête pour toute origine hors LAN/localhost, AVANT même que ce
        # handler ne s'exécute.
        #
        # /qsl_scan/upload est exempté : multipart/form-data est un des TROIS
        # content-types CORS « simples » (comme text/plain), donc cette garde
        # ne peut pas le couvrir sans casser l'upload légitime — impact résiduel
        # bien plus faible qu'un CSRF sur /auth/set_password ou /config/save
        # (au pire, une image poussée à l'aveugle sur un QSO, sans lecture de
        # la réponse possible par l'attaquant).
        ctype = (self.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if self.path != '/qsl_scan/upload' and ctype != 'application/json':
            self._json({'error': 'Content-Type application/json requis'}, 415)
            return
        # Plafond de taille du corps : un client malveillant du LAN pouvait
        # envoyer plusieurs Go et faire gonfler la mémoire jusqu'au crash.
        # 32 Mo couvre largement un gros import ADIF ; au-delà on refuse.
        MAX_BODY = 32 * 1024 * 1024
        # La longueur du corps doit être CERTAINE avant de le lire. Trois cas
        # la rendent indéterminable : en-tête illisible (« Content-Length:
        # abc »), plusieurs Content-Length contradictoires, ou corps annoncé
        # en « Transfer-Encoding: chunked » — que BaseHTTPRequestHandler ne
        # sait pas décoder. On retombait alors sur length = 0, or read(0) ne
        # consomme RIEN : en connexion persistante les octets du corps sont
        # ensuite lus comme la requête SUIVANTE (mesuré : le corps recollé à
        # la ligne de requête du GET suivant, qui ne reçoit jamais sa
        # réponse). C'est la même désynchronisation que pour un refus avant
        # lecture, donc le même remède — refuser ET fermer. Un vrai
        # « Content-Length: 0 » (POST sans corps) reste parfaitement
        # déterminé : il doit continuer normalement, connexion réutilisable.
        te = (self.headers.get('Transfer-Encoding') or '').strip().lower()
        if te and te != 'identity':
            self.close_connection = True
            self._json({'error': "Transfer-Encoding non supporté : "
                                 "envoie un Content-Length"}, 411)
            return
        annonces = [str(v).strip() for v in (self.headers.get_all('Content-Length') or [])]
        if (any(not re.fullmatch(r'[0-9]+', v) for v in annonces)
                or len(set(annonces)) > 1):
            self.close_connection = True
            self._json({'error': 'Content-Length invalide'}, 400)
            return
        length = int(annonces[0]) if annonces else 0
        if length < 0 or length > MAX_BODY:
            # Même raison que dans _require_auth : on refuse sans lire le
            # corps, il faut donc fermer la connexion plutôt que de laisser
            # ces octets parasiter la requête suivante. (Les lire pour les
            # jeter serait absurde : c'est justement leur volume qu'on refuse.)
            self.close_connection = True
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

        # Sélecteur de dossier natif Windows pour le champ DOSSIER DE
        # SAUVEGARDE (CONFIG). Bloque volontairement le thread de CETTE
        # requête le temps que l'utilisateur réponde au dialogue — déclenché
        # par un clic, ce n'est pas un appel réseau automatique (voir
        # logx_winshell.py). Hors Windows : message de repli, le champ reste
        # utilisable en saisie manuelle.
        if self.path == '/backup/pick_folder':
            if _relay_rate_limited(self.client_address[0]):
                self._json({'error': 'Trop de requêtes /backup/pick_folder — réessaie dans une minute'}, 429)
                return
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            try:
                import logx_winshell as winshell
                res = winshell.pick_folder(
                    title='Choisir le dossier de sauvegarde',
                    initial_dir=payload.get('initial_dir', ''),
                )
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Bannière "Créer un raccourci sur le bureau ?" (premier lancement de
        # l'exécutable figé, voir logx_shortcut.py) — clic "Oui" : crée
        # réellement le raccourci ET pose le marqueur dans tous les cas
        # (succès ou échec), pour ne plus jamais reproposer la bannière.
        if self.path == '/shortcut/create_desktop':
            try:
                import logx_shortcut as shortcut
                res = shortcut.create_and_mark()
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Clic "Non" sur la même bannière : ne crée rien, pose juste le
        # marqueur pour ne plus jamais la réafficher.
        if self.path == '/shortcut/dismiss':
            try:
                import logx_shortcut as shortcut
                shortcut.mark_offered()
                self._json({'ok': True})
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

        # Synchro MySQL manuelle immédiate (voir aussi le thread de fond
        # périodique, _mysql_sync_loop dans logx_serveur.py). Même motif que
        # /cloudsync/now : les valeurs saisies mais pas encore enregistrées
        # priment sur la config sauvegardée.
        if self.path == '/mysql/now':
            try:
                import logx_mysql_sync as mysql
                try:
                    payload = json.loads(body) if body else {}
                except Exception:
                    payload = {}
                cfg_now = self._cfg_snapshot()
                for k in ('mysql_mode', 'mysql_host', 'mysql_port', 'mysql_user',
                         'mysql_password', 'mysql_database'):
                    if k in payload:
                        cfg_now[k] = payload[k]
                with log_lock:
                    log_copy = list(shared_log)
                res = mysql.sync_now(cfg_now, log_copy)
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Test de connexion MySQL éphémère (bouton CONFIG) — connecte, crée
        # le schéma si absent, ferme.
        if self.path == '/mysql/test':
            import logx_mysql_sync as mysql
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            res = mysql.test_connection(
                payload.get('host'), payload.get('port'), payload.get('user'),
                payload.get('password'), payload.get('database'))
            self._json(res, 200 if res.get('ok') else 400)
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
                cid = re.sub(r'[^A-Z0-9_]', '', str(payload.get('id', '')).strip().upper())
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
                    'validated_at': utcnow().isoformat(),
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
                    cid = re.sub(r'[^A-Z0-9_]', '', str(cid).upper())
                    if not cid:
                        continue
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
                    meta['imported_at'] = utcnow().isoformat()
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

        # Sauvegarde configuration courante. SEUL appelant client légitime :
        # logx_configuration.html (action explicite de l'opérateur). Cette
        # route REMPLACE tout current_config, dont les champs qui définissent
        # la portée partagée (contest/contest_start_date/usage_mode) — aucune
        # page d'affichage ne doit la solliciter en silence au chargement
        # (cf. le POST retiré de logx_carte.html:loadConfig).
        if self.path == '/config/save':
            try:
                cfg = json.loads(body)
                # Transverters : deux actifs sur la même FI rendraient toute
                # fréquence lue ambiguë (144,100 = 1296,100 ou 2320,100 ?).
                # On refuse la sauvegarde plutôt que de départager au hasard :
                # un mauvais choix ici produit un log entier sur la mauvaise
                # bande, sans le moindre message.
                _erreurs_tvtr = transverter.erreurs_config(cfg.get('transverters'))
                if _erreurs_tvtr:
                    self._json({'ok': False, 'error': ' '.join(_erreurs_tvtr)}, 400)
                    return
                with config_lock:
                    current_config = cfg
                    _save_config_to_disk(cfg)
                # /log/list filtre désormais par portée (concours+année, voir
                # active_scope_id) : changer de concours/mode d'usage change ce
                # que CETTE portée désigne sans qu'aucun QSO n'ait bougé — sans
                # ce bump, un client dont le ?v= était déjà à jour recevrait
                # 'unchanged' et garderait affiché l'ancien concours jusqu'au
                # prochain vrai QSO ajouté.
                # Idem pour la synchro différentielle (?since=) : aucun QSO
                # n'a été ajouté/modifié/supprimé, seule la portée visible a
                # changé — un delta ('_v' de chaque QSO inchangé) serait vide
                # à tort et laisserait l'ancien concours affiché. mark_hard_reset()
                # force un client avec un ?since= antérieur à repasser par la
                # liste complète, recalculée sous la NOUVELLE portée.
                # Les deux SOUS log_lock (et non plus hors de tout verrou) :
                # log_version += 1 (logx_storage.py) est un compteur global
                # non atomique (LOAD/ADD/STORE) — tous les AUTRES appelants de
                # ce dépôt l'appellent déjà sous 'with log_lock:', convention
                # documentée explicitement pour éviter cette course.
                with log_lock:
                    bump_log_version()
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
                    _save_config_to_disk(snap)
                self._json({'ok': True})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Wait-and-Pounce niveaux 3 et 4 : ARMER l'appel automatique. C'est LE
        # geste qui autorise la station à émettre sans qu'on la touche — il est
        # donc explicite, daté, et borné dans le temps par construction (voir
        # logx_pounce.Session.armer, qui refuse un armement sans critère).
        if self.path == '/pounce/armer':
            import logx_pounce as pounce
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            res = pounce.session.armer(payload)
            if res.get('ok'):
                print("[POUNCE] ARME niveau %d pour %d min"
                      % (res['niveau'], payload.get('duree_min', pounce.DUREE_DEFAUT_MIN)))
            self._json(res, 200 if res.get('ok') else 400)
            return

        # DÉSARMER. Comme le coupe-circuit : sans condition, et il coupe AUSSI
        # l'émission en cours — désarmer sans arrêter WSJT-X laisserait la
        # séquence en cours partir jusqu'au bout, ce que personne n'attend en
        # cliquant « arrêter ».
        if self.path == '/pounce/desarmer':
            import logx_pounce as pounce
            import logx_wsjtx as wsjtx
            res = pounce.session.desarmer('arret manuel')
            try:
                wsjtx.couper_emission(auto_seulement=False)
            except Exception:
                pass
            self._json(res)
            return

        # NIVEAU 2 de Wait-and-Pounce : « armer le coup ». On demande à WSJT-X
        # de préparer la réponse à un décodage — indicatif rempli, décalage
        # audio calé — exactement comme un double-clic sur la ligne. RIEN NE
        # PART SUR L'AIR de ce seul fait : c'est l'opérateur qui appuie ensuite
        # sur Enable TX. La route est protégée comme toutes les écritures.
        # École de CW : la correction d'une série. Le barème vit en Python
        # (testé), pas dans la page — un bilan qui se trompe décourage
        # l'opérateur au lieu de le faire progresser.
        if self.path == '/cw/corriger':
            import logx_cw_ecole as ecole
            try:
                p = json.loads(body)
            except (ValueError, TypeError):
                self._json({'error': 'corps JSON invalide'}, 400)
                return
            serie = p.get('serie') or []
            if not isinstance(serie, list) or len(serie) > 200:
                self._json({'error': 'série invalide'}, 400)
                return
            bilan = ecole.corriger(serie, p.get('reponses') or [])
            try:
                wpm = int(p.get('wpm') or 18)
            except (TypeError, ValueError):
                wpm = 18
            bilan['vitesse_suivante'] = ecole.vitesse_suivante(wpm, bilan['taux'])
            self._json(bilan)
            return

        if self.path == '/wsjtx/repondre':
            import logx_wsjtx as wsjtx
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            res = wsjtx.repondre_a(payload.get('call', ''))
            self._json(res, 200 if res.get('ok') else 400)
            return

        # Le coupe-circuit. Volontairement SANS condition : il doit répondre
        # même si tout le reste est en panne, et depuis n'importe quel poste du
        # réseau — l'opérateur qui veut arrêter l'émission ne doit jamais avoir
        # à chercher où cliquer.
        if self.path == '/wsjtx/couper':
            import logx_wsjtx as wsjtx
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            res = wsjtx.couper_emission(bool(payload.get('auto_seulement')))
            self._json(res, 200 if res.get('ok') else 400)
            return

        # Filtre d'affichage des spots. Même précaution que /ui/theme juste
        # au-dessus : on n'écrit QUE 'spot_filter', jamais tout current_config.
        # Réglage partagé entre postes à dessein — en multi-op, deux écrans qui
        # affichent des listes de spots différentes sans que personne ne sache
        # pourquoi, c'est la garantie d'un multiplicateur perdu.
        if self.path == '/spots/filter':
            try:
                import logx_spotfilter as spotfilter
                payload = json.loads(body) if body else {}
                propre = spotfilter.reglages_valides(payload)
                with config_lock:
                    current_config['spot_filter'] = propre
                    snap = dict(current_config)
                    _save_config_to_disk(snap)
                self._json({'ok': True, 'spot_filter': propre,
                            'actif': spotfilter.actif(propre)})
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
            # asset_sha256/asset_size : référence vérifiée en flux pendant le
            # téléchargement (voir logx_update._do_download) — sans digest
            # fiable exposé par l'API GitHub pour cet asset, le téléchargement
            # est refusé plutôt qu'accepté à l'aveugle (docstring logx_update.py).
            upd.start_download(check['asset_url'], check.get('asset_sha256', ''),
                                check.get('asset_size', 0))
            self._json({'ok': True})
            return

        # ── Mise à jour réseau local (B priorité, C secours — voir logx_update.py) ─
        # Découverte SEULE (ne télécharge rien) : sonde chaque poste candidat
        # (peer_list connu du client via /log/status) pour savoir qui peut
        # servir de passerelle (B) et, à défaut, qui a déjà un exécutable
        # vérifié à servir en secours (C). Action utilisateur explicite côté
        # client (bouton "chercher sur le réseau"), jamais un sondage
        # automatique en tâche de fond.
        if self.path == '/app/update_network_scan':
            import logx_update as upd
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            # Anti-SSRF (revue sécurité) : le corps JSON vient du CLIENT et
            # n'est donc jamais digne de confiance tel quel — sans ce filtre,
            # scan_network_candidates() construisait une requête HTTP sortante
            # vers N'IMPORTE QUELLE IP/hôte fourni ici (ex. {"ips": ["1.2.3.4"]}
            # ou même un nom comme "localhost"), y compris un poste qui ne
            # s'est JAMAIS connecté à ce serveur. On ne retient donc que les IP
            # que CE serveur a lui-même vues comme pairs réels (_known_peer_ips,
            # alimenté depuis l'IP socket de connexions entrantes réelles,
            # jamais depuis un corps de requête) — un appelant ne peut plus
            # faire sonder que des postes déjà connus, pas un hôte de son choix.
            ips = [ip for ip in (payload.get('ips') or []) if str(ip).strip() in _known_peer_ips()]
            self._json(upd.scan_network_candidates(ips))
            return

        # Déclenche le téléchargement via un poste candidat (passerelle ou
        # pair — voir 'mode' dans le corps) : REFUSE immédiatement si ce
        # poste n'a lui-même aucune référence SHA-256 obtenue par contact
        # direct antérieur avec GitHub (voir logx_update.start_download_via_
        # network — jamais de confiance aveugle envers le pair/la passerelle
        # pour la référence elle-même). Priorité B>C RESTREINTE CÔTÉ SERVEUR :
        # pour mode='peer', on transmet aussi known_lan_ips=_known_peer_ips()
        # (postes que CE serveur a lui-même vus, jamais une donnée du corps
        # JSON) — start_download_via_network/_do_download_via_network sondent
        # alors elles-mêmes cette liste pour une passerelle disponible et
        # refusent le secours si l'une répond, même si l'appelant a omis son
        # IP de `ips` pour tenter de contourner l'IHM cliente (voir revue
        # sécurité : le mode='peer' n'était auparavant restreint que par
        # convention côté client, jamais vérifié ici).
        if self.path == '/app/update_download_via_network':
            import logx_update as upd
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            mode = payload.get('mode', '')
            # Anti-SSRF (revue sécurité, même filtre que /app/update_network_
            # scan ci-dessus) : `ips` vient du corps JSON du CLIENT — sans ce
            # filtre, un appelant pouvait faire ouvrir par ce serveur une VRAIE
            # connexion HTTP sortante (sonde + éventuel début de téléchargement
            # en flux) vers n'importe quel hôte de son choix, jamais vérifié
            # contre les pairs réellement connus. On ne retient que les IP déjà
            # vues comme pairs réels par CE serveur (_known_peer_ips).
            known = _known_peer_ips()
            ips = [ip for ip in (payload.get('ips') or []) if str(ip).strip() in known]
            ok, err = upd.start_download_via_network(mode, ips, known_lan_ips=list(known))
            if not ok:
                self._json({'error': err}, 400)
                return
            self._json({'ok': True})
            return

        if self.path == '/app/update_install':
            import logx_update as upd
            status = upd.get_download_status()
            if status.get('status') != 'done' or not status.get('path'):
                self._json({'error': 'Téléchargement pas terminé'}, 400)
                return
            # Dernier verrou avant remplacement de l'exécutable en cours : ne
            # JAMAIS faire confiance aveugle à status=='done' seul. Contrôle
            # défensif explicite du flag 'verified' ICI, au point qui EXÉCUTE
            # réellement apply_update_and_relaunch — même si les 3 chemins de
            # téléchargement (_do_download, _do_download_via_network B et C)
            # sont censés toujours le fixer ensemble avec status='done' dans
            # le même appel _download.update() atomique. Une régression future
            # sur l'un de ces sites d'écriture (ou un nouveau chemin ajouté
            # plus tard) ne doit jamais suffire à faire remplacer le binaire
            # par un fichier non vérifié.
            if not status.get('verified'):
                self._json({'error': 'Fichier téléchargé non vérifié'}, 400)
                return
            ok, err = upd.apply_update_and_relaunch(status['path'])
            if not ok:
                self._json({'error': err}, 400)
                return
            self._json({'ok': True, 'restarting': True})
            # Laisse le temps à la réponse HTTP de partir avant de couper le
            # serveur. Figé (PyInstaller) : le script auxiliaire attend déjà
            # la fin de CE processus pour remplacer l'exécutable et le
            # relancer — os._exit(0) suffit. Développement (python
            # logx_serveur.py direct) : rien n'attend ce processus, il n'y a
            # pas d'exécutable à remplacer — dev_mode_relaunch() relance
            # lui-même le même script via os.execv().
            if upd.is_frozen():
                threading.Timer(1.0, lambda: os._exit(0)).start()
            else:
                threading.Timer(1.0, upd.dev_mode_relaunch).start()
            return

        # Radio CAT native/TCI/flrig : test éphémère depuis CONFIG (avant même de
        # sauvegarder) — ouvre, interroge, ferme, ne touche pas au polling.
        if self.path == '/rig/connect_test':
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            # Anti-SSRF (revue sécurité) : cet équipement (TCI/rigctld/flrig/
            # FlexRadio/IC-remote) est toujours sur ce poste ou le LAN dans
            # l'usage réel — sans ce filtre, `host` (config client) laissait
            # sonder par CE SERVEUR n'importe quel hôte Internet de son choix.
            # Voir _is_loopback_or_private_host ci-dessus.
            _NOT_LAN_ERR = {'ok': False, 'error': "hôte non autorisé (doit être local/LAN)"}
            if payload.get('mode') == 'tci':
                import logx_tci as tci
                host = (payload.get('host') or '').strip() or tci.DEFAULT_HOST
                if not _is_loopback_or_private_host(host):
                    self._json(_NOT_LAN_ERR, 400)
                    return
                res = tci.test_connection(host, payload.get('port'))
            elif payload.get('mode') == 'rigctld':
                # Correctif H6 : jusqu'ici absent — le mode rigctld tombait dans
                # le "else" natif ci-dessous, qui teste un port SÉRIE (jamais
                # utilisé par rigctld, protocole réseau texte sur rig_host/rig_port).
                import logx_rig as rig
                host = (payload.get('host') or '').strip() or rig.DEFAULT_HOST
                if not _is_loopback_or_private_host(host):
                    self._json(_NOT_LAN_ERR, 400)
                    return
                try:
                    port = int(payload.get('port') or rig.DEFAULT_PORT)
                except (TypeError, ValueError):
                    port = rig.DEFAULT_PORT
                res = rig.get_state(host, port)
            elif payload.get('mode') == 'flrig':
                import logx_flrig as flrig
                host = (payload.get('host') or '').strip() or flrig.DEFAULT_HOST
                if not _is_loopback_or_private_host(host):
                    self._json(_NOT_LAN_ERR, 400)
                    return
                try:
                    port = int(payload.get('port') or flrig.DEFAULT_PORT)
                except (TypeError, ValueError):
                    port = flrig.DEFAULT_PORT
                res = flrig.test_connection(host, port)
            elif payload.get('mode') == 'omnirig':
                import logx_omnirig as omnirig
                res = omnirig.test_connection(payload.get('rig_num') or 1)
            elif payload.get('mode') == 'flex':
                import logx_flexradio as flexradio
                host = (payload.get('host') or '').strip() or flexradio.DEFAULT_HOST
                if not _is_loopback_or_private_host(host):
                    self._json(_NOT_LAN_ERR, 400)
                    return
                try:
                    port = int(payload.get('port') or flexradio.DEFAULT_PORT)
                except (TypeError, ValueError):
                    port = flexradio.DEFAULT_PORT
                res = flexradio.test_connection(host, port)
            elif payload.get('mode') == 'icom_remote':
                import logx_icomremote as icomremote
                host = (payload.get('host') or '').strip() or icomremote.DEFAULT_HOST
                if not _is_loopback_or_private_host(host):
                    self._json(_NOT_LAN_ERR, 400)
                    return
                try:
                    port = int(payload.get('port') or icomremote.DEFAULT_CONTROL_PORT)
                except (TypeError, ValueError):
                    port = icomremote.DEFAULT_CONTROL_PORT
                res = icomremote.test_connection(host, port)
            else:
                import logx_cat as cat
                res = cat.test_connection(payload.get('brand'), payload.get('model'),
                                          payload.get('port'), payload.get('baudrate'),
                                          payload.get('civ_addr'))
            self._json(res, 200 if res.get('ok') else 502)
            return

        # Auto-détection CAT native : marque/modèle encore inconnus, on balaie
        # les vitesses courantes sur le port et on tente autodetect() (retour
        # microHAM 02/08/2026 — le bouton "Tester" existant exigeait déjà
        # marque+modèle, donc n'auto-détectait jamais rien).
        if self.path == '/rig/autodetect':
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            import logx_cat as cat
            res = cat.autodetect_scan(payload.get('port'))
            self._json(res, 200 if res.get('ok') else 502)
            return

        # Écarte une détection de branchement en attente (l'opérateur a
        # cliqué "Configurer" ou "Ignorer" côté bandeau CONFIG) — sinon elle
        # réapparaîtrait à l'identique tant que le port reste branché.
        if self.path == '/rig/dismiss_detection':
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            import logx_cat as cat
            cat.dismiss_detection(payload.get('device'))
            self._json({'ok': True})
            return

        # Scope CI-V 0x27 : configuration mode/span (27 14 puis 27 15) sur la
        # connexion série déjà ouverte pour le CAT — appelé quand l'opérateur
        # choisit la source "CI-V natif" ou change de span dans le panadapter.
        if self.path == '/rig/scope_configure':
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            import logx_cat as cat
            mode = str(payload.get('mode') or 'center').strip().lower()
            try:
                span_hz = int(payload.get('span_hz')) if payload.get('span_hz') else None
            except (TypeError, ValueError):
                span_hz = None
            # Le <select> de logx_panadapter.html ne propose que les 8 spans
            # valides (2.5 à 500 kHz, CIV_SCOPE_SPANS_HZ) — mais l'endpoint
            # est appelable directement (pas seulement depuis cette page), et
            # sans ce garde-fou un span hors spec serait encodé tel quel et
            # envoyé à la radio dans la trame 27 15, comportement non
            # documenté par la spec constructeur pour une valeur invalide.
            if span_hz is not None and span_hz not in cat.CIV_SCOPE_SPANS_HZ:
                self._json({'ok': False, 'error': f'Span scope invalide ({span_hz} Hz) — '
                            f'valeurs acceptées : {", ".join(str(s) for s in cat.CIV_SCOPE_SPANS_HZ)}'}, 400)
                return
            res = cat.scope_configure(self._cfg_snapshot(), mode, span_hz)
            self._json(res, 200 if res.get('ok') else 400)
            return

        # Panadapter TCI : démarre/arrête le flux IQ (IQ_SAMPLERATE + DDS +
        # IQ_START, ou IQ_STOP) sur la connexion WebSocket TCI déjà ouverte
        # pour le CAT — appelé quand l'opérateur choisit la source "TCI" du
        # panadapter, change de fréquence d'échantillonnage, ou quand la
        # page se ferme (enabled=false, pour ne pas laisser le flux IQ
        # tourner pour rien).
        if self.path == '/rig/tci_spectrum_configure':
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            import logx_tci as tci
            enabled = bool(payload.get('enabled'))
            try:
                sample_rate_hz = int(payload.get('sample_rate_hz')) if payload.get('sample_rate_hz') else None
            except (TypeError, ValueError):
                sample_rate_hz = None
            # Le <select> de logx_panadapter.html ne propose que les 4
            # valeurs valides — mais l'endpoint est appelable directement,
            # et sans ce garde-fou une valeur hors spec passerait telle
            # quelle jusqu'à tci_spectrum_configure() (qui la refuse aussi,
            # mais un 400 explicite ici évite un aller-retour serveur inutile
            # pour une erreur détectable sans toucher au réseau TCI).
            if enabled and sample_rate_hz not in tci.TCI_IQ_SAMPLE_RATES_HZ:
                self._json({'ok': False, 'error': "Fréquence d'échantillonnage IQ invalide "
                            f"({sample_rate_hz}) — valeurs acceptées : "
                            f"{', '.join(str(r) for r in tci.TCI_IQ_SAMPLE_RATES_HZ)}"}, 400)
                return
            res = tci.tci_spectrum_configure(self._cfg_snapshot(), enabled, sample_rate_hz)
            self._json(res, 200 if res.get('ok') else 400)
            return

        # Test du WinKeyer : l'ouverture de session renvoie la version du
        # micrologiciel, seule preuve qu'un manipulateur est bien au bout du
        # câble — un adaptateur USB sans rien derrière passerait sinon pour un
        # WinKeyer et les macros partiraient dans le vide.
        if self.path == '/winkeyer/test':
            import logx_winkeyer as wk
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            cfg_test = dict(self._cfg_snapshot())
            if payload.get('port'):
                cfg_test['winkeyer_port'] = payload['port']
            if payload.get('wpm'):
                cfg_test['winkeyer_wpm'] = payload['wpm']
            res = wk.tester(cfg_test)
            self._json(res, 200 if res.get('ok') else 502)
            return

        # Radio CAT : QSY, envoi CW, stop CW — natif/TCI/flrig si configuré, sinon rigctld
        if self.path in ('/rig/qsy', '/rig/cw', '/rig/stop'):
            # SO2R : tout le pilotage vise la radio qui a le FOCUS. La config
            # de la radio 2 (cat2_*) est présentée sous les noms cat_*, si bien
            # que les quatre backends fonctionnent sans savoir qu'il y a deux
            # radios. Sans SO2R configuré, la config ressort inchangée.
            import logx_so2r as so2r
            # radio_active lu UNE SEULE FOIS, avant de dériver cfg_snap : la
            # même valeur sert au remap de config ET au verrou TX, pour éviter
            # qu'une bascule de focus concurrente (Ctrl+Espace pendant cette
            # requête) ne fasse correspondre le verrou à une radio différente
            # de celle réellement pilotée (revue adversariale 07/08/2026).
            radio_active = so2r.focus()['focus']
            cfg_snap = so2r.config_radio_active(self._cfg_snapshot(), radio=radio_active)
            # Verrou d'exclusivité TX (Phase 0 SO2R) : la manip CW démarre une
            # émission fire-and-forget (WinKeyer/CAT natif tiennent leur propre
            # buffer, cette requête HTTP revient avant la fin réelle) — sans ce
            # verrou, rien n'empêche d'armer la radio 2 pendant que la radio 1
            # émet encore. QSY n'émet rien, non concerné. STOP relâche TOUJOURS
            # la radio qui détient réellement le verrou (pas celle qui a le
            # focus AU MOMENT du stop — un changement de focus entre l'armement
            # et le clic sur ■ STOP laisserait sinon le verrou d'origine
            # orphelin, bug trouvé en revue adversariale 07/08/2026).
            if self.path == '/rig/cw':
                verrou = so2r.verrouiller_tx(radio_active)
                if not verrou['ok']:
                    self._json(verrou, 409)
                    return
            elif self.path == '/rig/stop':
                so2r.deverrouiller_tx(so2r.tx_actif()['radio'])

            def _reponse_cw(res, status):
                # Le verrou TX n'a de sens que tant qu'une émission est
                # RÉELLEMENT en cours -- un refus (port fermé, backend qui ne
                # sait pas manipuler...) ne doit jamais laisser l'AUTRE radio
                # bloquée pour rien jusqu'au timeout de 120s. N'est appelée
                # QUE depuis les branches /rig/cw (radio_active y est déjà
                # défini) -- bug trouvé en revue adversariale 07/08/2026 :
                # AUCUN chemin d'échec de /rig/cw ne relâchait le verrou.
                if not res.get('ok'):
                    so2r.deverrouiller_tx(radio_active)
                self._json(res, status)

            # WinKeyer AVANT tout backend CAT, et quel que soit le mode : c'est
            # tout son intérêt. Il a son propre port et son propre processeur,
            # donc une cadence qui ne dépend pas du trafic CAT — et il est la
            # SEULE voie de manipulation pour Icom (CI-V n'a pas de commande
            # d'envoi de texte CW) et pour Yaesu. Le QSY, lui, reste au CAT :
            # un manipulateur ne règle pas la fréquence.
            if self.path in ('/rig/cw', '/rig/stop'):
                import logx_winkeyer as wk
                if wk.parametres(cfg_snap)['enabled']:
                    if self.path == '/rig/stop':
                        res = wk.arreter(cfg_snap)
                        self._json(res, 200 if res.get('ok') else 400)
                    else:
                        res = wk.envoyer(cfg_snap, (json.loads(body) if body else {}).get('text', ''))
                        if res.get('ok'):
                            print(f"[WK] CW -> {str(res.get('text',''))[:60]} "
                                  f"({res.get('wpm')} mots/min)")
                        _reponse_cw(res, 200 if res.get('ok') else 400)
                    return
            import logx_cat as cat
            cat_settings = cat.cat_settings(cfg_snap)
            native = cat_settings['enabled'] and cat_settings['mode'] == 'native'
            use_tci = cat_settings['enabled'] and cat_settings['mode'] == 'tci'
            use_flrig = cat_settings['enabled'] and cat_settings['mode'] == 'flrig'
            use_omnirig = cat_settings['enabled'] and cat_settings['mode'] == 'omnirig'
            use_flex = cat_settings['enabled'] and cat_settings['mode'] == 'flex'
            use_icomremote = cat_settings['enabled'] and cat_settings['mode'] == 'icom_remote'
            if use_tci:
                import logx_tci as tci
            if use_flrig:
                import logx_flrig as flrig
                flrig_settings = flrig.flrig_settings(cfg_snap)
            if use_omnirig:
                import logx_omnirig as omnirig
            if use_flex:
                import logx_flexradio as flexradio
            if use_icomremote:
                import logx_icomremote as icomremote
            if not (native or use_tci or use_flrig or use_omnirig or use_flex or use_icomremote):
                import logx_rig as rig
                settings = rig.rig_settings(cfg_snap)
                if not settings['enabled']:
                    erreur = {'ok': False, 'error': 'Radio CAT désactivée — '
                              'active-la dans CONFIG (mode expert, section RADIO)'}
                    if self.path == '/rig/cw':
                        _reponse_cw(erreur, 400)
                    else:
                        self._json(erreur, 400)
                    return
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}

            if self.path == '/rig/qsy':
                try:
                    freq = payload.get('freq_hz') or 0
                    if not freq and payload.get('freq_khz'):
                        freq = float(payload['freq_khz']) * 1000
                    if not freq:
                        self._json({'ok': False, 'error': 'Fréquence manquante'}, 400)
                        return
                    # La fréquence demandée est celle du trafic RÉEL (un spot à
                    # 1296,200). La radio, elle, ne comprend que sa FI : sans cette
                    # conversion inverse on lui demanderait 1296,200 MHz, hors de
                    # sa couverture — refus, ou pire, déplacement silencieux en
                    # bord de bande. Sans transverter configuré, freq est inchangée.
                    freq_reelle = int(freq)
                except (TypeError, ValueError):
                    self._json({'ok': False, 'error': 'Fréquence invalide'}, 400)
                    return
                freq = transverter.fi_depuis_rf(freq_reelle, cfg_snap)
                if native:
                    res = cat.set_freq(cfg_snap, int(freq), payload.get('mode'))
                elif use_tci:
                    res = tci.set_freq(cfg_snap, int(freq), payload.get('mode'))
                elif use_flrig:
                    res = flrig.set_freq(flrig_settings['host'], flrig_settings['port'],
                                        int(freq), payload.get('mode'))
                elif use_omnirig:
                    res = omnirig.set_freq(cfg_snap, int(freq), payload.get('mode'))
                elif use_flex:
                    # Hors périmètre volontaire de logx_flexradio.py (voir sa
                    # docstring) : aucune commande "slice t"/"slice s" exposée.
                    res = {'ok': False, 'error': 'QSY non pris en charge en mode "FlexRadio" — '
                           'hors périmètre de ce module, bascule en mode "Hamlib rigctld" ou "TCI"'}
                elif use_icomremote:
                    res = icomremote.set_freq(cfg_snap, int(freq), payload.get('mode'))
                else:
                    res = rig.set_freq(settings['host'], settings['port'], int(freq), payload.get('mode'))
                if res.get('ok'):
                    _via = ('' if freq == freq_reelle
                            else f" (reel {freq_reelle} Hz via transverter)")
                    print(f"[RIG] QSY {int(freq)} Hz{_via} {payload.get('mode') or ''}")
            elif native:
                # Manipulation CW en natif (commande KY, Kenwood et Elecraft).
                # Le mode natif refusait TOUT envoi CW — or c'est celui que la
                # CONFIG recommande par défaut : un opérateur CW n'avait donc
                # aucune manipulation, ESM se contentant de copier le texte
                # dans le presse-papier. Icom et Yaesu restent refusés, mais
                # avec un message qui nomme la cause et la solution.
                if self.path == '/rig/stop':
                    res = cat.stop_cw(cfg_snap)
                    self._json(res, 200 if res.get('ok') else 400)
                else:
                    res = cat.send_cw(cfg_snap, payload.get('text', ''))
                    if res.get('ok'):
                        print(f"[RIG] CW natif -> {str(res.get('text',''))[:60]}")
                    _reponse_cw(res, 200 if res.get('ok') else 400)
                return
            elif use_flrig:
                # flrig n'expose pas de méthode XML-RPC générique d'envoi CW fiable
                # sans montage DTR/RTS supplémentaire (voir logx_flrig.py) — même
                # choix que le mode natif.
                erreur = {'ok': False, 'error': 'Envoi CW non disponible en mode "flrig" — '
                          'bascule en mode "Hamlib rigctld" ou "TCI" pour le keyer CW'}
                if self.path == '/rig/cw':
                    _reponse_cw(erreur, 400)
                else:
                    self._json(erreur, 400)
                return
            elif use_omnirig or use_flex or use_icomremote:
                # Aucun des 3 : pas de commande d'envoi de texte CW documentée/
                # exposée par ces modules (OmniRig ne fait que Tx=PM_TX/PM_RX,
                # FlexRadio est volontairement hors périmètre, Icom-remote est
                # désactivé par conception) — même refus propre que flrig.
                erreur = {'ok': False, 'error': 'Envoi CW non disponible dans ce mode CAT — '
                          'utilise un manipulateur WinKeyer, ou bascule en mode '
                          '"Hamlib rigctld" ou "TCI" pour le keyer CW'}
                if self.path == '/rig/cw':
                    _reponse_cw(erreur, 400)
                else:
                    self._json(erreur, 400)
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
            if self.path == '/rig/cw':
                _reponse_cw(res, 200 if res.get('ok') else 502)
            else:
                self._json(res, 200 if res.get('ok') else 502)
            return

        # PTT explicite, sans passer par le keyer vocal (celui-ci enrobe
        # systématiquement synthèse+lecture). Utilisé par le décodeur FT8
        # natif (logx_ft8.html) : la radio ne sait rien du protocole FT8,
        # seul le ton audio compte — LogX AI doit donc commander le PTT
        # lui-même autour de la lecture, comme pour un micro externe.
        if self.path == '/rig/ptt':
            import logx_so2r as so2r
            import logx_voicekeyer as vk
            # radio_active lu UNE SEULE FOIS, avant cfg_snap : évite qu'une
            # bascule de focus concurrente entre les deux lectures ne fasse
            # correspondre le verrou TX à une radio différente de celle
            # réellement pilotée (revue adversariale 07/08/2026).
            radio_active = so2r.focus()['focus']
            cfg_snap = so2r.config_radio_active(self._cfg_snapshot(), radio=radio_active)
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            on = bool(payload.get('on'))
            if on:
                verrou = so2r.verrouiller_tx(radio_active)
                if not verrou['ok']:
                    self._json(verrou, 409)
                    return
            res = vk.set_ptt(cfg_snap, on)
            if not on or not res.get('ok'):
                # PTT relâché (demande normale), ou PTT ON refusé par la radio :
                # dans les deux cas, le verrou pris pour CETTE radio doit retomber.
                so2r.deverrouiller_tx(radio_active)
            self._json(res, 200 if res.get('ok') else 400)
            return

        # Keyer vocal dynamique : indicatif/report épelés phonétiquement,
        # synthétisés (TTS hors-ligne) et émis par la radio (PTT via CAT
        # autour de la lecture, quel que soit le mode natif/TCI/rigctld/flrig).
        if self.path in ('/so2r/focus', '/so2r/test'):
            import logx_so2r as so2r
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            cfg_snap = self._cfg_snapshot()
            if self.path == '/so2r/test':
                # Le port saisi dans la page PRIME sur celui de la config
                # enregistrée : sinon le bouton « Tester » ne pourrait rien
                # tester tant qu'on n'a pas sauvegardé — c'est exactement
                # l'inverse de ce qu'on attend d'un bouton de test. Même
                # comportement que /winkeyer/test.
                cfg_test = dict(cfg_snap)
                if payload.get('port'):
                    cfg_test['so2r_port'] = payload['port']
                res = so2r.tester(cfg_test)
            else:
                res = so2r.basculer(cfg_snap, payload.get('radio'))
                if res.get('ok'):
                    print(f"[SO2R] emission -> radio {res.get('focus')} "
                          f"({res.get('ecoute')})")
            self._json(res, 200 if res.get('ok') else 502)
            return

        if self.path in ('/bandmap/add', '/bandmap/delete', '/bandmap/clear'):
            import logx_bandmap as bm
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            if self.path == '/bandmap/clear':
                res = bm.vider()
            elif self.path == '/bandmap/delete':
                res = bm.supprimer(payload.get('call'), payload.get('freq_khz'))
            else:
                res = bm.ajouter(payload.get('call'), payload.get('freq_khz'),
                                 payload.get('band', ''), payload.get('mode', ''),
                                 payload.get('note', ''))
            self._json(res, 200 if res.get('ok') else 400)
            return

        # ─── DVK : messages enregistrés par l'opérateur ──────────────────────
        # Enregistrés dans le navigateur mais STOCKÉS ET JOUÉS ICI. Avant, ils
        # vivaient en localStorage et partaient par `new Audio().play()` : sortie
        # par défaut du navigateur, aucun PTT — le correspondant n'entendait
        # rien, et changer de poste perdait les messages.
        if self.path in ('/voice/save', '/voice/play', '/voice/delete'):
            import logx_voicekeyer as vk
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            slot = str(payload.get('slot', ''))
            if self.path == '/voice/save':
                import base64
                brut = payload.get('wav_base64') or ''
                # Data URL éventuelle ("data:audio/wav;base64,....") : on ne
                # garde que la charge utile.
                if ',' in brut[:64] and brut.lstrip().startswith('data:'):
                    brut = brut.split(',', 1)[1]
                try:
                    donnees = base64.b64decode(brut, validate=True)
                except Exception:
                    self._json({'ok': False, 'error': 'Données audio illisibles'}, 400)
                    return
                res = vk.enregistrer_message(slot, donnees)
            elif self.path == '/voice/delete':
                res = vk.supprimer_message(slot)
            else:
                import logx_so2r as so2r
                # Verrou TX (Phase 0 SO2R) : emettre_wav() est bloquant (PTT
                # ON -> lecture -> PTT OFF), donc englobable directement --
                # contrairement au CW WinKeyer/natif, fire-and-forget.
                radio_active = so2r.focus()['focus']
                verrou = so2r.verrouiller_tx(radio_active)
                if not verrou['ok']:
                    self._json(verrou, 409)
                    return
                try:
                    # radio_active déjà lu ci-dessus, repassé explicitement :
                    # évite une SECONDE lecture indépendante du focus (revue
                    # adversariale 07/08/2026).
                    res = vk.envoyer_message(
                        so2r.config_radio_active(self._cfg_snapshot(), radio=radio_active), slot)
                finally:
                    so2r.deverrouiller_tx(radio_active)
                if res.get('ok'):
                    print(f"[RIG] Message vocal {slot} emis")
            self._json(res, 200 if res.get('ok') else 400)
            return

        if self.path == '/rig/voice':
            import logx_voicekeyer as vk
            import logx_so2r as so2r
            # radio_active lu UNE SEULE FOIS, avant cfg_snap : évite qu'une
            # bascule de focus concurrente entre les deux lectures ne fasse
            # correspondre le verrou TX à une radio différente de celle
            # réellement pilotée (revue adversariale 07/08/2026).
            radio_active = so2r.focus()['focus']
            cfg_snap = so2r.config_radio_active(self._cfg_snapshot(), radio=radio_active)
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
            # segments : synthèse multi-voix (un moteur/une voix par langue
            # rencontrée dans le message) — voir expand_voice_segments().
            # skip_ptt : réservé au bouton "Tester" de CONFIG (indicatif
            # fictif) — jamais envoyé par le déclenchement réel depuis le
            # logbook (logx_logbook.js), qui a besoin du PTT pour transmettre.
            skip_ptt = bool(payload.get('skip_ptt'))
            # Verrou TX (Phase 0 SO2R) : pas d'émission réelle si skip_ptt
            # (bouton "Tester" de CONFIG, indicatif fictif) -- rien à verrouiller.
            if not skip_ptt:
                verrou = so2r.verrouiller_tx(radio_active)
                if not verrou['ok']:
                    self._json(verrou, 409)
                    return
            try:
                res = vk.send_voice_message(cfg_snap, text, lang=vk.message_lang(ctx),
                                            skip_ptt=skip_ptt,
                                            segments=vk.expand_voice_segments(template, ctx))
            finally:
                if not skip_ptt:
                    so2r.deverrouiller_tx(radio_active)
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
                # Anti-SSRF (revue sécurité) : en mode réseau (tcp/udp,
                # KPA1500 Ethernet), `host` vient du client — l'ampli est
                # toujours sur ce poste ou le LAN dans l'usage réel, voir
                # _is_loopback_or_private_host ci-dessus. Le mode série
                # n'utilise jamais host, pas de vérification à y faire.
                if (payload.get('conn_mode') or 'serial').strip().lower() in ('tcp', 'udp') \
                        and not _is_loopback_or_private_host(payload.get('host', '')):
                    self._json({'ok': False, 'error': "hôte non autorisé (doit être local/LAN)"}, 400)
                    return
                res = amp.test_connection(
                    payload.get('brand', ''), payload.get('port', ''),
                    payload.get('baudrate') or 0, payload.get('civ_addr'),
                    conn_mode=payload.get('conn_mode') or 'serial',
                    host=payload.get('host', ''), net_port=payload.get('net_port') or None)
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

        # PowerGenius XL (4O3A) : test de connexion éphémère depuis CONFIG.
        # Pas de route "operate" — set_operate() refuse toujours (voir
        # logx_powergenius.py : aucune commande OPERATE/STANDBY confirmée par
        # la doc officielle, un ampli est un dispositif de sécurité, mieux
        # vaut refuser explicitement que deviner). Le pilotage standby/operate
        # se fait au panneau avant du PGXL ou via SmartSDR en attendant.
        if self.path == '/pgxl/test':
            import logx_powergenius as pgxl
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            # Anti-SSRF (revue sécurité) : le PowerGenius est toujours sur ce
            # poste ou le LAN dans l'usage réel — voir
            # _is_loopback_or_private_host ci-dessus. Le plafond de timeout
            # est appliqué côté logx_powergenius.test_connection().
            if not _is_loopback_or_private_host(payload.get('host', '')):
                self._json({'ok': False, 'error': "hôte non autorisé (doit être local/LAN)"}, 400)
                return
            res = pgxl.test_connection(payload.get('host'), payload.get('port'),
                                       payload.get('timeout'))
            self._json(res, 200 if res.get('ok') else 400)
            return

        # ACOM (série RS-232) : test de connexion éphémère depuis CONFIG.
        # Contrairement à /pgxl/test ci-dessus, une route "operate" EXISTE bien
        # (voir logx_acom.py : Operate/Standby/Off sont 3 commandes confirmées,
        # sémantique non ambiguë) — /acom/operate juste en dessous.
        if self.path == '/acom/test':
            import logx_acom as acom
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            res = acom.test_connection(payload.get('port'), payload.get('model'),
                                       payload.get('timeout'))
            self._json(res, 200 if res.get('ok') else 400)
            return

        if self.path == '/acom/operate':
            import logx_acom as acom
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            cfg_snap = self._cfg_snapshot()
            res = acom.set_operate(cfg_snap, payload.get('mode', ''))
            self._json(res, 200 if res.get('ok') else 400)
            return

        # Télémétrie : envoi immédiat d'un heartbeat (bouton "Tester" de
        # CONFIG) — le champ saisi PRIME sur celui déjà enregistré, comme
        # /winkeyer/test et /so2r/test, pour pouvoir tester avant de
        # sauvegarder. Le payload envoyé (voir logx_telemetry.build_payload)
        # est identique à celui du heartbeat quotidien réel.
        if self.path == '/telemetry/test':
            import logx_telemetry as tel
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            cfg_test = dict(self._cfg_snapshot())
            cfg_test['telemetry_enabled'] = True
            if payload.get('endpoint'):
                cfg_test['telemetry_endpoint'] = payload['endpoint']
            res = tel.send_heartbeat(cfg_test)
            self._json(res, 200 if res.get('ok') else 400)
            return

        # Panneau Station Control (relais WebSwitch/KMTronic/Denkovi/série
        # générique) : bascule manuelle d'un relais, test de connexion.
        # L'auto-pilotage par bande (relay.maybe_apply_band) est appelé côté
        # polling (_rig_state_dict), pas via cette route.
        if self.path in ('/relay/set', '/relay/test'):
            import logx_relay as relay
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            cfg_snap = self._cfg_snapshot()
            if self.path == '/relay/test':
                res = relay.test_connection(cfg_snap)
            else:
                try:
                    relay_num = int(payload.get('relay'))
                except (TypeError, ValueError):
                    self._json({'ok': False, 'error': 'Numéro de relais invalide'}, 400)
                    return
                res = relay.set_relay(cfg_snap, relay_num, bool(payload.get('on')))
            self._json(res, 200 if res.get('ok') else 400)
            return

        # Rotor d'antenne (rotctld) : pointer, stopper
        # Suivi rotor d'un passage satellite : démarrage/arrêt de la boucle de
        # fond (logx_sat_track). Les refus sont SYNCHRONES — rotor éteint,
        # satellite inconnu, passage trop lointain — pour que l'opérateur ait
        # la raison sous les yeux immédiatement.
        if self.path in ('/rotor/sat_track', '/rotor/sat_track_stop'):
            import logx_sat_track as strack
            if self.path == '/rotor/sat_track_stop':
                strack.arreter_suivi()
                self._json({'ok': True})
                return
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            ok, msg = strack.demarrer_suivi(payload.get('sat', ''),
                                            self._cfg_snapshot())
            self._json({'ok': ok, 'error': msg} if not ok else {'ok': True},
                       200 if ok else 409)
            return

        if self.path in ('/rotor/point', '/rotor/stop'):
            import logx_rotor as rotor
            import logx_station as station
            cfg_now = self._cfg_snapshot()
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            # QUEL rotor ? Une station peut en avoir plusieurs (trois pylônes,
            # trois antennes, trois rotors). Deux façons de le désigner :
            #   - `bande` : le rotor de l'antenne active sur cette bande. C'est
            #     le chemin du clic sur un spot — SEUL ce pylône tourne, les
            #     autres restent où ils sont (indispensable en multi-opérateur) ;
            #   - `rotor_id` : désignation directe, pour un pointage à la main.
            # Sans l'un ni l'autre : l'ancien rotor unique, pour que les
            # configurations non migrées continuent de fonctionner.
            st = station.charger(cfg_now)
            cible = None
            if payload.get('rotor_id'):
                cible = station.rotor_par_id(st, payload['rotor_id'])
                if cible is None:
                    self._json({'ok': False,
                                'error': 'Rotor inconnu : %s' % payload['rotor_id']}, 404)
                    return
            elif payload.get('bande'):
                cible = station.rotor_pour_bande(st, payload['bande'],
                                                 cfg_now.get('antenne_par_bande'))
                if cible is None:
                    # Antenne fixe, ou aucune antenne déclarée sur la bande :
                    # ne RIEN faire tourner est la bonne réponse, et le dire
                    # vaut mieux qu'un silence qu'on prendrait pour une panne.
                    self._json({'ok': False, 'sans_rotor': True,
                                'error': "Aucun rotor pour l'antenne de cette bande"}, 200)
                    return
            if cible is not None:
                if not cible['enabled'] or not cible['host']:
                    self._json({'ok': False, 'error': 'Rotor « %s » désactivé ou '
                                'sans adresse' % (cible['nom'] or cible['id'])}, 400)
                    return
                host, port, offset = cible['host'], cible['port'], cible
                proto = cible.get('proto', 'rotctld')
            else:
                # Sans sélecteur : le rotor par défaut du parc (avec son
                # décalage), ou l'ancien rotor unique. C'est ce chemin que
                # prend le bouton « pointer » de la boussole et de la chasse
                # tant qu'ils n'envoient pas de bande — il applique désormais
                # le décalage mécanique, qui était perdu (revue 01/08/2026).
                d = station.rotor_defaut(cfg_now)
                if not d['enabled']:
                    self._json({'ok': False, 'error': 'Rotor désactivé — '
                                'active-le dans CONFIG (mode expert, section ROTOR)'}, 400)
                    return
                host, port = d['host'], d['port']
                proto = d.get('proto', 'rotctld')
                offset = d if d['offset_deg'] else None
            if self.path == '/rotor/point':
                az = payload.get('azimuth')
                if az is None:
                    self._json({'ok': False, 'error': 'Azimut manquant'}, 400)
                    return
                # Décalage mécanique du pylône appliqué ICI, une seule fois :
                # l'appelant raisonne toujours en azimut VRAI.
                if offset is not None:
                    az = station.azimut_rotor(offset, az)
                    if az is None:
                        self._json({'ok': False, 'error': 'Azimut invalide'}, 400)
                        return
                res = rotor.set_position(host, port, az, payload.get('elevation', 0), proto)
                if res.get('ok'):
                    print(f"[ROTOR] Pointe {res['azimuth']} deg ({proto})")
            else:
                res = rotor.stop(host, port, proto)
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
        #  - détaillée (voir logx_qtc.js:saveQTCSeries) : {call, direction,
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
                with qtc_lock:
                    already = qtc_count_for_call(call, scope_id)
                    if call and already + count > 10:
                        self._json({'ok': False,
                                    'error': f"Max 10 QTC par station — déjà {already} "
                                             f"avec {call}"}, 400)
                        return
                    now_utc = utcnow()
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
                    qtc_log.append(entry)
                save_qtc_to_disk()
                print(f"[QTC] +{count} avec {call or '?'} ({direction})")
                self._json({'ok': True, 'total': qtc_total(scope_id),
                            'with_call': already + count, 'id': entry['id']})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Planning de roulement des opérateurs (écran mural) : ajouter un
        # créneau. Outil INFORMATIF — le seul refus possible est un opérateur
        # INCONNU de la config (operators[].call, voir logx_configuration.html
        # popup OPÉRATEURS) ; une qualification de mode manquante
        # (operators[].modes) ne bloque jamais la création, elle renvoie
        # seulement un 'warning' pour que l'UI l'affiche.
        if self.path == '/shifts/add':
            try:
                from logx_storage import (operator_shifts, shifts_lock, next_shift_id,
                                           save_shifts_to_disk)
                payload = json.loads(body)
                call = str(payload.get('call', '')).upper().strip()
                start = str(payload.get('start', '')).strip()
                end = str(payload.get('end', '')).strip()
                if not call or not start or not end:
                    self._json({'ok': False, 'error':
                                "Indicatif, heure de début et heure de fin sont requis"}, 400)
                    return
                cfg_snap = self._cfg_snapshot()
                operators = cfg_snap.get('operators') or []
                op = next((o for o in operators
                           if str(o.get('call', '')).upper().strip() == call), None)
                if op is None:
                    self._json({'ok': False, 'error':
                                f"Opérateur inconnu : {call} — ajoute-le d'abord dans "
                                "CONFIG ▸ Opérateurs avant de planifier son créneau"}, 400)
                    return
                entry = {'id': next_shift_id(), 'call': call,
                         'name': str(payload.get('name') or op.get('name') or '').strip(),
                         'start': start, 'end': end}
                date = str(payload.get('date') or '').strip()
                if date:
                    entry['date'] = date
                note = str(payload.get('note') or '').strip()
                if note:
                    entry['note'] = note
                mode = str(payload.get('mode') or '').strip().lower()
                warning = None
                if mode in ('ssb', 'cw', 'digi'):
                    entry['mode'] = mode
                    # Qualification absente de la config -> considérée acquise
                    # par défaut (même convention que collectConfig() côté
                    # client, logx_configuration.html) : un opérateur dont la
                    # config ne précise rien n'est jamais signalé à tort comme
                    # non qualifié.
                    qualified = bool((op.get('modes') or {}).get(mode, True))
                    if not qualified:
                        warning = (f"{call} n'est pas déclaré qualifié {mode.upper()} "
                                   "dans CONFIG ▸ Opérateurs — créneau ajouté quand même "
                                   "(le planning reste informatif, pas un verrou).")
                with shifts_lock:
                    operator_shifts.append(entry)
                    if len(operator_shifts) > 500:
                        operator_shifts.pop(0)
                save_shifts_to_disk()
                res = {'ok': True, 'shift': entry}
                if warning:
                    res['warning'] = warning
                self._json(res)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 400)
            return

        # Planning : suppression d'un créneau (POST plutôt que DELETE — voir
        # /log/delete et /qtc/delete pour la variante DELETE déjà utilisée
        # ailleurs ; celle-ci suit la spécification demandée pour ce module).
        if self.path.startswith('/shifts/delete/'):
            try:
                from logx_storage import operator_shifts, shifts_lock, save_shifts_to_disk
                shift_id = int(self.path.split('/')[-1])
                with shifts_lock:
                    before = len(operator_shifts)
                    operator_shifts[:] = [s for s in operator_shifts if s.get('id') != shift_id]
                    deleted = before - len(operator_shifts)
                save_shifts_to_disk()
                self._json({'ok': True, 'deleted': deleted})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 400)
            return

        # Chat multi-opérateur — envoi d'un message
        if self.path == '/chat/send':
            try:
                msg = json.loads(body)
                now = utcnow().strftime('%H:%M')
                with chat_lock:
                    chat_seq += 1
                    entry = {
                        'id':   chat_seq,
                        'op':   str(msg.get('op', 'OP?') or 'OP?')[:20],
                        'call': str(msg.get('call', '') or '')[:20],
                        'time': now,
                        'text': str(msg.get('text', ''))[:500],
                    }
                    chat_messages.append(entry)
                    if len(chat_messages) > 200:
                        chat_messages.pop(0)
                    entry_id = entry['id']
                self._json({'ok': True, 'id': entry_id})
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
                        _prune_typing_state()
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
                    # Lecture-modification-écriture sous calldb_lock EN ENTIER
                    # (pas seulement l'écriture finale) : sinon deux requêtes
                    # concurrentes (deux opérateurs qui corrigent deux indicatifs
                    # différents au même moment) lisent le même état initial et
                    # la seconde écriture écrase la modification de la première.
                    with calldb_lock:
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
                                # lock déjà tenu ci-dessus (calldb_lock n'est pas
                                # réentrant) : on n'en redemande pas un second à
                                # save_json_atomic.
                                save_json_atomic(calldb_path, db, lock=None, compact=True)
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

        # Alternative au bouton d'import manuel ci-dessus : télécharge
        # MASTER.SCP depuis sa source publique de référence. Vrai appel
        # réseau (contrairement à /callhistory/import_scp) -- borné via le
        # pool partagé de fetch_url() (logx_utils.py), même motif que
        # /qrz_logbook/test. Bloquant mais acceptable : ThreadingHTTPServer,
        # un thread OS par connexion (voir fetch_url() pour le détail du
        # bornage DNS/attente).
        if self.path == '/callhistory/update_scp':
            try:
                import logx_callhistory as callhistory
                res = callhistory.fetch_and_import_master_scp()
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 500)
            return

        # Bouton « Lancer » par ligne du panneau AUTO-LANCEMENT (CONFIG) :
        # lance UN programme immédiatement, sans attendre le prochain
        # démarrage du serveur (logx_autostart.lancer_tous() ne s'exécute
        # qu'une fois, au boot). Même fonction que le démarrage auto, juste
        # déclenchée à la demande — pas une capacité nouvelle, seulement une
        # version manuelle de ce qui se passe déjà sans confirmation à chaque
        # lancement de LogX.
        if self.path == '/autostart/launch':
            try:
                import logx_autostart
                payload = json.loads(body) if body else {}
                res = logx_autostart.lancer(payload)
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
                # Même correctif que add_qso_to_log (voir sa docstring) : ne
                # JAMAIS faire confiance au champ 'points' envoyé par le
                # client -- une correction manuelle (bande/locator changés en
                # édition) doit recalculer le score au MÊME moteur, sinon
                # /log/update devenait le seul chemin d'écriture du log où le
                # client choisissait librement ses propres points. Même
                # borne de 3s, même repli sur la valeur client en cas
                # d'échec/dépassement (jamais bloquer une correction pour un
                # souci de scoring réseau).
                try:
                    updated_qso['points'] = _SCORE_EXECUTOR.submit(score_new_qso, updated_qso).result(timeout=3)
                except Exception as _e:
                    print(f"[SCORING] Recalcul points (update) abandonné ({type(_e).__name__}: {_e}) "
                          f"— valeur envoyée par le client conservée")
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
                    if old_scope is None:
                        # QSO déjà supprimé par un autre poste (course avec
                        # /log/delete) entre le chargement côté client et
                        # l'envoi de la correction : erreur explicite plutôt
                        # qu'un ok:True qui masquerait la perte de la correction.
                        self._json({'ok': False,
                                    'error': f"QSO id={qso_id} introuvable (supprimé entre-temps ?)"}, 404)
                        return
                    bump_log_version()
                    stamp_qso_version(updated_qso)   # voir /log/list?since=
                    if qso_scope_id(updated_qso) != old_scope:
                        mark_hard_reset()   # voir /log/list?since= : portée du QSO changée
                save_log_to_disk()
                print(f"[LOG] ~QSO corrige id={qso_id}")
                self._json({'ok': True})
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Démarre une re-résolution en masse (locator/état via cty/QRZ/
        # ClubLog — cascade callbook déjà existante). `ids`: liste d'IDs
        # QSO ciblés, ou absent/vide = tout le log. `overwrite`: écrase
        # aussi les locator/état déjà renseignés (par défaut, ne comble que
        # les vides — voir logx_callbook.bulk_resolve_start).
        if self.path == '/log/bulk_resolve/start':
            try:
                import logx_callbook as callbook
                payload = json.loads(body) if body else {}
                ids = payload.get('ids')
                ids = [int(i) for i in ids] if ids else None
                overwrite = bool(payload.get('overwrite'))
                ok, msg = callbook.bulk_resolve_start(
                    self._cfg_snapshot, ids=ids, overwrite=overwrite)
                self._json({'ok': ok, 'error': msg if not ok else ''})
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
                # bump_log_version()/stamp_qso_version() DANS le même verrou que
                # l'extend : même fenêtre de course que /log/add (voir le
                # commentaire détaillé dans add_qso_to_log) — un lecteur
                # /log/list?since= concurrent (ThreadingHTTPServer) pouvait
                # s'intercaler entre le bump (version déjà incrémentée) et le
                # stamp (encore absent) et exclure à jamais les QSO importés de
                # tous ses deltas. Fenêtre d'autant plus large ici que le stamp
                # boucle sur TOUT l'import. save_log_to_disk() reste HORS verrou
                # (elle reprend log_lock elle-même ; non réentrant sinon deadlock).
                with log_lock:
                    # Numérotation AUTORITAIRE des id sous le verrou : celle de
                    # commit_import() a été calculée contre l'INSTANTANÉ pris
                    # plus haut, et un /log/add concurrent (ThreadingHTTPServer,
                    # expédition multi-opérateur) a pu s'insérer entre les deux.
                    # Sans ça un QSO importé et un QSO live pourraient partager
                    # un id, et /log/delete les effacerait tous les deux.
                    for q, new_id in zip(new_qsos,
                                         allocate_qso_ids_locked(len(new_qsos), shared_log)):
                        q['id'] = new_id
                    shared_log.extend(new_qsos)
                    bump_log_version()
                    for q in new_qsos:
                        stamp_qso_version(q)   # voir /log/list?since=
                    total = len(shared_log)
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

        # Import ADIF LoTW/ClubLog — ENRICHIT les QSO déjà au log (état US pour
        # le diplôme WAS) et fusionne les confirmations. N'ajoute AUCUN QSO :
        # c'est /log/import_adif/commit qui fait ça, et mélanger les deux
        # ferait entrer des contacts d'un rapport de confirmations dans le
        # carnet. L'état ne se déduit pas d'un indicatif — c'est la seule
        # source possible pour le passé.
        if self.path == '/log/import_adif/etats':
            try:
                payload = json.loads(body)
                adif = payload.get('adif', '')
                import logx_import as imp
                etats = imp.etats_depuis_adif(adif)
                with log_lock:
                    remplis, calls = imp.appliquer_etats(shared_log, etats)
                    if remplis:
                        bump_log_version()
                        for q in shared_log:
                            if q.get('call') in calls:
                                stamp_qso_version(q)
                if remplis:
                    save_log_to_disk()
                # Les confirmations passent par le mécanisme existant (même
                # fichier, même clé CALL|MHz|MODE que le calcul des diplômes).
                confirmes = 0
                try:
                    import logx_qsl as qsl
                    _, confirmes = qsl.merge_confirmations(
                        qsl.parse_confirmations(adif, source='lotw'))
                except Exception:
                    pass
                try:
                    import logx_awards as awards
                    awards.invalidate()   # le cache des diplômes doit repartir
                except Exception:
                    pass
                print(f"[IMPORT] etats US : {remplis} QSO renseignes "
                      f"({len(etats)} indicatifs), {confirmes} confirmations")
                self._json({'ok': True, 'states_filled': remplis,
                            'calls': len(etats), 'confirmations': confirmes})
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
                        archived_ids = {q.get('id') for q in snapshot}
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
                        # Ne retire que les QSO effectivement archivés (par id) :
                        # un QSO ajouté par /log/add pendant l'archivage (hors
                        # verrou, I/O disque potentiellement lente) n'était pas
                        # dans l'instantané et doit survivre au reset plutôt que
                        # d'être effacé sans avoir jamais été sauvegardé.
                        shared_log[:] = [q for q in shared_log if q.get('id') not in archived_ids]
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
                    archived_ids = {q.get('id') for q in qs}
                # QTC (WAE) : mêmes séries que /log/export/cabrillo (scopées par
                # contest+année) — sans ça, le Cabrillo archivé perd les lignes
                # "QTC:" (voir logx_export.build_cabrillo).
                from logx_storage import qtc_log, qtc_lock
                with qtc_lock:
                    qtc_series = [q for q in qtc_log if qso_scope_id(q) == scope_id]
                res = arch.archive_log(qs, cid or 'CONTEST', cfg_snap, qtc_series)
                if res.get('ok') and payload.get('clear'):
                    with log_lock:
                        # Ne retire QUE les QSO effectivement archivés (par id),
                        # jamais "tout ce qui matche encore la portée" : un QSO
                        # ajouté par /log/add après l'instantané (même portée)
                        # n'a pas été archivé et doit rester dans le log courant
                        # plutôt que d'être perdu.
                        keep = [q for q in shared_log if q.get('id') not in archived_ids]
                        shared_log[:] = keep
                    bump_log_version()
                    mark_hard_reset()   # voir /log/list?since= : effacement en masse, pas un tombstone par QSO
                    save_log_to_disk()
                    res['cleared'] = True
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'error': str(e)}, 400)
            return

        # Importer un VIEUX log de concours (ADIF ou Cabrillo, jamais loggué
        # dans LogX AI) comme archive permanente -- alimente le "score à
        # battre" (/log/archives/best) sans toucher au log actif. Payload :
        # {format:'adif'|'cabrillo', text, contest, score?}. `score` est
        # optionnel (Cabrillo : remplace CLAIMED-SCORE si fourni ; ADIF :
        # seule source de score possible, l'ADIF n'en transporte pas).
        if self.path == '/log/archives/import':
            try:
                payload = json.loads(body) if body else {}
                import logx_archive as arch
                text = payload.get('text', '')
                fmt = payload.get('format', '')
                contest_id = payload.get('contest', '')
                score = payload.get('score')
                manual_score = int(score) if score not in (None, '') else None
                res = arch.import_external_log(text, fmt, contest_id,
                                                 self._cfg_snapshot(), manual_score)
                self._json(res, 200 if res.get('ok') else 400)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)}, 400)
            return

        # Proxy IA universel (Anthropic / OpenAI / Gemini)
        # Analyse IA lancée CÔTÉ SERVEUR (thread de fond) : le résultat est
        # stocké et récupérable via GET /agent/analyze/state — l'analyse se
        # termine même si l'opérateur change d'onglet (la nav recharge la page).
        # Stratégie pile-up FT8 : l'IA lit la SÉRIE des décodages d'UNE station DX
        # et conseille où/quand appeler. Job de fond ; purement CONSULTATIF (aucune
        # émission). Le client poll /wsjtx/strategy/state.
        if self.path == '/wsjtx/strategy':
            global _strat_seq
            try:
                import logx_wsjtx as wsjtx
                cfg_snap = self._cfg_snapshot()
                payload = json.loads(body) if body else {}
                call = (payload.get('call') or '').strip().upper()
                if not call:
                    self._json({'error': 'Indicatif manquant'}, 400)
                    return
                provider = cfg_snap.get('api_provider', 'anthropic')
                api_key = cfg_snap.get('api_key', '') or (os.environ.get('ANTHROPIC_API_KEY', '') if provider == 'anthropic' else '')
                if not api_key:
                    self._json({'error': 'Clé API non configurée'}, 400)
                    return
                series = wsjtx.decode_history(call)
                with _strat_lock:
                    _strat_seq += 1
                    aid = f"{int(time.time())}-strat-{_strat_seq}"
                    _strat_jobs[aid] = {'ts': time.time(), 'status': 'running',
                                        'reply': '', 'call': call, 'decodes': series, 'error': ''}
                    if len(_strat_jobs) > 10:
                        for k in sorted(_strat_jobs, key=lambda k: _strat_jobs[k]['ts'])[:-10]:
                            _strat_jobs.pop(k, None)

                def _run(aid=aid, cfg=cfg_snap, call=call, series=series):
                    try:
                        if len(series) < 2:
                            with _strat_lock:
                                if aid in _strat_jobs:
                                    _strat_jobs[aid].update(
                                        status='done',
                                        reply=("Pas assez de décodages récents de %s pour "
                                               "analyser sa stratégie — il faut l'entendre "
                                               "sur plusieurs cycles FT8." % call))
                            return
                        prompt = build_ft8_strategy_prompt(call, series)
                        text = call_llm(cfg, FT8_STRATEGY_SYSTEM,
                                        [{'role': 'user', 'content': prompt}], None, 800)
                        with _strat_lock:
                            if aid in _strat_jobs:
                                _strat_jobs[aid].update(status='done', reply=text)
                    except Exception as e:
                        with _strat_lock:
                            if aid in _strat_jobs:
                                _strat_jobs[aid].update(status='error', error=str(e))
                threading.Thread(target=_run, daemon=True).start()
                self._json({'id': aid, 'status': 'running'})
            except Exception as e:
                self._json({'error': str(e)}, 500)
            return

        # Chasse assistée : l'agent PROPOSE une action physique (pointer rotor /
        # QSY) via tool-use. Job de fond ; le serveur n'exécute rien — le client
        # affiche une carte de confirmation, et c'est le CLIC qui appelle
        # /rotor/point ou /rig/qsy. Single-shot ; non-Anthropic -> texte seul.
        if self.path == '/agent/act':
            global _act_seq
            try:
                cfg_snap = self._cfg_snapshot()
                payload = json.loads(body) if body else {}
                message = payload.get('message') or (
                    "Trouve LE meilleur spot non-doublon à travailler maintenant "
                    "(mult ou DX rentable) et, si c'est pertinent, propose de pointer "
                    "l'antenne dessus ou de m'y amener en fréquence. Sinon, conseille "
                    "en une phrase.")
                needs_context = payload.get('needs_context', True)
                system_prompt = payload.get('system') or (build_system_prompt(cfg_snap) if cfg_snap else '')
                provider = cfg_snap.get('api_provider', 'anthropic')
                api_key = cfg_snap.get('api_key', '') or (os.environ.get('ANTHROPIC_API_KEY', '') if provider == 'anthropic' else '')
                if not api_key:
                    self._json({'error': 'Clé API non configurée'}, 400)
                    return
                with _act_lock:
                    _act_seq += 1
                    aid = f"{int(time.time())}-act-{_act_seq}"
                    _act_jobs[aid] = {'ts': time.time(), 'status': 'running',
                                      'reply': '', 'action': None, 'error': ''}
                    if len(_act_jobs) > 10:
                        for k in sorted(_act_jobs, key=lambda k: _act_jobs[k]['ts'])[:-10]:
                            _act_jobs.pop(k, None)

                def _run(aid=aid, cfg=cfg_snap, sysp=system_prompt, msg=message, ctx=needs_context):
                    try:
                        enriched = msg
                        if ctx:
                            try:
                                data = do_refresh(cfg)
                                if data.get('context'):
                                    enriched = data['context'] + '\n\nDemande opérateur : ' + msg
                                if data.get('system_prompt'):
                                    sysp = data['system_prompt']
                            except Exception as e:
                                print(f"[ACT] contexte indisponible : {e}")
                        r = call_llm_actions(cfg, sysp, [{'role': 'user', 'content': enriched}])
                        pending = pending_action_from_tool(r.get('action'))
                        with _act_lock:
                            if aid in _act_jobs:
                                _act_jobs[aid].update(status='done', reply=r.get('text', ''), action=pending)
                    except Exception as e:
                        with _act_lock:
                            if aid in _act_jobs:
                                _act_jobs[aid].update(status='error', error=str(e))
                threading.Thread(target=_run, daemon=True).start()
                self._json({'id': aid, 'status': 'running'})
            except Exception as e:
                self._json({'error': str(e)}, 500)
            return

        # Audit IA du log avant dépôt : lance un job de fond (l'appel LLM à
        # sortie JSON forcée peut durer). Le client poll /log/audit/state et
        # fusionne les constats sous ceux du VÉRIFIER déterministe.
        if self.path == '/log/audit':
            global _audit_seq
            try:
                import logx_validator as validator
                cfg_snap = self._cfg_snapshot()
                with log_lock:
                    log_copy = list(shared_log)
                inp = validator.build_audit_input(
                    log_copy, cfg_snap.get('contest', ''), cfg_snap)
                if not inp['valid_ids']:
                    self._json({'error': 'Aucun QSO à auditer'}, 400)
                    return
                provider = cfg_snap.get('api_provider', 'anthropic')
                model = modele_effectif(provider, None, cfg_snap.get('ai_model'))
                api_key = cfg_snap.get('api_key', '') or (os.environ.get('ANTHROPIC_API_KEY', '') if provider == 'anthropic' else '')
                if not api_key:
                    self._json({'error': 'Clé API non configurée'}, 400)
                    return
                with _audit_lock:
                    _audit_seq += 1
                    aid = f"{int(time.time())}-{_audit_seq}"
                    _audit_jobs[aid] = {'ts': time.time(), 'status': 'running',
                                        'findings': [], 'error': '',
                                        'truncated': inp['truncated'], 'count': inp['count']}
                    if len(_audit_jobs) > 10:
                        for k in sorted(_audit_jobs, key=lambda k: _audit_jobs[k]['ts'])[:-10]:
                            _audit_jobs.pop(k, None)

                def _run(aid=aid, inp=inp, provider=provider, model=model, api_key=api_key):
                    try:
                        import logx_rules_ai as rai
                        import logx_validator as validator
                        obj = rai.call_ai_structured(
                            provider, model, api_key, inp['system'], inp['user_text'],
                            validator.AUDIT_SCHEMA, max_tokens=4000)
                        found = validator.normalize_audit_findings(
                            (obj or {}).get('findings', []), inp['valid_ids'])
                        with _audit_lock:
                            if aid in _audit_jobs:
                                _audit_jobs[aid].update(status='done', findings=found)
                    except Exception as e:
                        with _audit_lock:
                            if aid in _audit_jobs:
                                _audit_jobs[aid].update(status='error', error=str(e))
                threading.Thread(target=_run, daemon=True).start()
                self._json({'id': aid, 'status': 'running',
                            'truncated': inp['truncated'], 'count': inp['count']})
            except Exception as e:
                self._json({'error': str(e)}, 500)
            return

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
                # Comme /proxy/ai : le modèle demandé par la page est ignoré,
                # c'est le réglage de CONFIG qui fait foi. C'est ici que le nom
                # Anthropic codé en dur de la carte partait vers OpenAI ou
                # Gemini, et faisait échouer tout le chat.
                model = None
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
                        # Streamé : chaque fragment est ajouté au buffer sous
                        # verrou, ce que /agent/analyze/state (polling) ET
                        # /agent/analyze/stream (SSE) exposent au fil de l'eau.
                        # La génération reste dans CE thread de fond : elle
                        # survit au changement d'onglet, le flux SSE ne fait que
                        # tailer le buffer (il ne tient PAS la génération).
                        def _on_delta(piece, _aid=aid):
                            with _agent_lock:
                                a = _agent_analyses.get(_aid)
                                if a is not None:
                                    a['reply'] = (a.get('reply') or '') + piece
                        text = call_llm_stream(cfg, sysp, msgs, mdl, mt, on_delta=_on_delta)
                        with _agent_lock:
                            a = _agent_analyses.get(aid)
                            if a is not None:
                                # Recale sur le texte complet (cohérence finale
                                # buffer == réponse), puis marque terminé.
                                a.update(status='done', reply=text)
                    except Exception as e:
                        with _agent_lock:
                            a = _agent_analyses.get(aid)
                            if a is not None:
                                # On GARDE le partiel déjà streamé (le flux SSE
                                # l'a montré) et on signale l'erreur à côté.
                                a.update(status='error', error=str(e))
                threading.Thread(target=_run, daemon=True).start()
                self._json({'id': aid, 'status': 'running'})
            except Exception as e:
                self._json({'error': str(e)}, 500)
            return

        if self.path in ('/proxy/ai', '/proxy/anthropic'):
            cfg_snap = self._cfg_snapshot()
            provider = cfg_snap.get('api_provider', 'anthropic')
            ai_model = modele_effectif(provider, None, cfg_snap.get('ai_model'))
            api_key  = cfg_snap.get('api_key', '')
            if not api_key and provider == 'anthropic':
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
                        # `payload['model']` est DÉLIBÉRÉMENT ignoré : ce proxy
                        # sert des pages du navigateur, et une page n'a pas à
                        # décider du modèle — l'opérateur l'a réglé dans CONFIG.
                        # Un appelant SERVEUR qui a besoin d'un palier précis
                        # passe par call_llm(model=…), dont la demande est
                        # honorée si elle est de la bonne famille.
                        'model':      ai_model,
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
                    model_id = ai_model
                    gem_contents = []
                    for m in messages:
                        role = 'model' if m['role'] == 'assistant' else 'user'
                        gem_contents.append({'role': role, 'parts': [{'text': m['content']}]})
                    gem_payload = {'contents': gem_contents}
                    if system_prompt:
                        gem_payload['systemInstruction'] = {'parts': [{'text': system_prompt}]}
                    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent'
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(gem_payload).encode(),
                        headers={'Content-Type': 'application/json',
                                 'x-goog-api-key': api_key},
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
        # Jetons OAuth SOTA (access_token/refresh_token) ecrits en clair par
        # logx_sota_spot._save_tokens() -- sans point de tete, donc PAS deja
        # couvert par la regle generale sur les fichiers/segments caches
        # (voir plus bas) : quiconque atteint le serveur pouvait les lire par
        # un simple GET et publier des spots SOTA au nom de l'operateur.
        'sota_oauth_tokens.json',
    }
    # Le test par nom exact ne couvre pas les copies renommées (logx.db.bak,
    # shared_log.json.20260722.bak...) — on bloque aussi par suffixe.
    _NEVER_SERVE_SUFFIXES = ('.bak', '.db')

    @classmethod
    def _interdit(cls, candidate, base_real):
        """Liste noire appliquée au chemin RÉELLEMENT résolu, pas à la chaîne
        d'URL brute. Tester os.path.basename(rel) avant normalisation laissait
        passer toutes les écritures équivalentes du même fichier : '/.auth_token/'
        et '/.auth_token%2F' donnent un basename VIDE, '/x/../.auth_token/' aussi,
        et realpath() les ramenait ensuite sur le vrai secret — le jeton d'écriture
        partait alors à n'importe quel poste du LAN, sans authentification.
        On inspecte donc chaque segment du chemin final : un seul segment caché
        (fichier OU dossier, ex. /.git/config dont le basename est 'config')
        suffit à refuser."""
        try:
            rel_real = os.path.relpath(candidate, base_real)
        except ValueError:          # lecteurs Windows différents
            return True
        segments = [s for s in rel_real.replace('\\', '/').split('/') if s]
        if not segments:
            return True
        if any(seg.startswith('.') for seg in segments):
            return True
        dernier = segments[-1].lower()
        return (dernier in cls._NEVER_SERVE
                or dernier.endswith(cls._NEVER_SERVE_SUFFIXES))

    def _resolve(self, path):
        import urllib.parse
        rel = urllib.parse.unquote(path).lstrip('/\\')
        # Un ':' ne peut désigner qu'un flux de données alternatif NTFS
        # ('shared_log.json::$DATA' ouvre bien shared_log.json alors que le nom
        # vu par la liste noire diffère) ou une lettre de lecteur : aucun
        # fichier légitimement servi n'en contient, on refuse d'emblée.
        if ':' in rel:
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
            if not os.path.isfile(candidate):
                continue
            # Interdit ici et pas plus haut : la liste noire doit voir le chemin
            # normalisé, seul reflet de ce que open() lira réellement.
            if self._interdit(candidate, base_real):
                return None
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
        # Si un appelant a decidé de fermer (refus avant lecture du corps, voir
        # _require_auth et le plafond MAX_BODY), il faut le DIRE au client :
        # sinon il croit la connexion réutilisable, envoie sa requête suivante
        # dans une socket déjà fermée et doit la rejouer — erreur transitoire
        # visible pour rien. L'en-tête rend la fermeture explicite et attendue.
        if self.close_connection:
            self.send_header('Connection', 'close')
        if content_type:
            self.send_header('Content-Type', content_type)
        if compressed:
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(body_bytes) if body_bytes else 0))
        self._security_headers()
        self._cors()
        self.end_headers()
        if body_bytes:
            self.wfile.write(body_bytes)

    def _json(self, data, code=200):
        self._raw(code, 'application/json; charset=utf-8',
                  json.dumps(data, ensure_ascii=False).encode('utf-8'))

    # ── Mise à jour réseau (voir logx_update.py) : réponses STREAMÉES, jamais
    # un exécutable entier chargé en mémoire (contrairement à _json/_raw qui
    # supposent un corps déjà en RAM — adapté au JSON, pas à 15-30 Mo binaires).
    def _stream_asset_relay(self, asset_url):
        """Chemin B (passerelle) : relaie l'asset GitHub officiel en flux vers
        le poste appelant. urlopen() est fait ICI (pas avant d'envoyer les
        entêtes) pour pouvoir répondre une erreur JSON propre si GitHub
        renvoie 404/erreur AVANT d'avoir engagé la réponse HTTP en flux."""
        try:
            req = urllib.request.Request(asset_url, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)'})
            upstream = urllib.request.urlopen(req, timeout=20, context=SSL_CTX)
        except Exception as e:
            self._json({'error': f'Relais impossible : {e}'}, 502)
            return
        with upstream:
            length = upstream.headers.get('Content-Length', '')
            try:
                annonce = int(length)
            except (TypeError, ValueError):
                annonce = None
            if annonce is None:
                # Sans taille annoncée par la source, on ne peut PAS délimiter
                # le corps en connexion persistante : le poste appelant
                # attendrait indéfiniment la suite d'un fichier déjà complet.
                # On revient alors au seul délimiteur possible — la fermeture
                # de connexion — en l'annonçant explicitement.
                self.close_connection = True
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            if annonce is not None:
                self.send_header('Content-Length', str(annonce))
            else:
                self.send_header('Connection', 'close')
            self._cors()
            self.end_headers()
            envoyes = 0
            while True:
                chunk = upstream.read(262144)
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except Exception:
                    # Envoi interrompu : le corps est tronqué par rapport au
                    # Content-Length annoncé. Réutiliser cette connexion ferait
                    # lire ce reliquat comme la réponse suivante — on la ferme.
                    self.close_connection = True
                    return  # poste appelant parti en cours de route
                envoyes += len(chunk)
            if annonce is not None and envoyes != annonce:
                # L'amont a annoncé une taille et en a livré MOINS : uplink de
                # la passerelle coupé pendant le relais, ou source qui tronque.
                # La boucle sort alors NORMALEMENT (chunk vide) et rien ne
                # signalerait l'anomalie : le corps est pourtant plus court que
                # le Content-Length que nous venons d'annoncer nous-mêmes. En
                # connexion persistante, le poste appelant attendrait la suite
                # jusqu'au délai d'inactivité (30 s) avant de pouvoir basculer
                # sur le secours pair-à-pair ; la fermeture lui rend l'échec
                # immédiat qu'il avait en HTTP/1.0.
                self.close_connection = True

    def _stream_verified_file(self, path):
        """Chemin C (pair-à-pair, secours) : sert `path` (toujours
        logx_update._download['path'], jamais un paramètre client — voir
        l'appelant) en flux, jamais chargé entièrement en mémoire."""
        try:
            size = os.path.getsize(path)
            f = open(path, 'rb')
        except OSError as e:
            self._json({'error': str(e)}, 404)
            return
        with f:
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(size))
            self._cors()
            self.end_headers()
            envoyes = 0
            while True:
                chunk = f.read(262144)
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except Exception:
                    # Corps tronqué par rapport au Content-Length annoncé :
                    # même raisonnement que dans _stream_asset_relay, la
                    # connexion ne peut pas être réutilisée telle quelle.
                    self.close_connection = True
                    return  # poste appelant parti en cours de route
                envoyes += len(chunk)
            if envoyes != size:
                # Le fichier a rétréci entre getsize() et la fin de la lecture
                # (l'exécutable est justement remplacé pendant qu'on le sert) :
                # on a annoncé plus d'octets qu'on n'en a écrits. Même
                # conséquence que dans _stream_asset_relay — sans fermeture, le
                # pair attend la suite jusqu'au délai d'inactivité.
                self.close_connection = True

    def _sse_agent_stream(self, aid):
        """Flux SSE (text/event-stream) qui TAILE le buffer d'une analyse IA :
        pousse chaque nouveau fragment de _agent_analyses[aid]['reply'], puis un
        événement 'done' (réponse complète) ou 'failed' (erreur/introuvable/délai).

        BORNÉ PAR CONCEPTION (contrainte 360 h, un thread OS par connexion) : la
        boucle se termine TOUJOURS — soit l'analyse finit (done/error), soit la
        deadline dure tombe, soit le client part (write échoue). Un `retry:` très
        long est envoyé en tête : si le client oublie de fermer, EventSource ne
        reconnecte qu'une fois par heure au lieu d'une rafale (le client appelle
        es.close() sur 'done'/'failed')."""
        self.close_connection = True
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('X-Accel-Buffering', 'no')   # pas de tampon proxy intermédiaire
            self.send_header('Connection', 'close')
            self._cors()
            self.end_headers()
        except Exception:
            return

        def _send(block):
            """Écrit un bloc SSE ; renvoie False si le client est parti."""
            try:
                self.wfile.write(block.encode('utf-8'))
                self.wfile.flush()
                return True
            except Exception:
                return False

        # Backstop anti-reconnexion en rafale (voir docstring).
        if not _send('retry: 3600000\n\n'):
            return

        start = time.time()
        last_beat = start
        sent = 0                       # position déjà poussée dans reply
        while True:
            now = time.time()
            with _agent_lock:
                a = _agent_analyses.get(aid)
                if a is None:
                    status, reply, err = None, '', ''
                else:
                    status = a.get('status', 'running')
                    reply = a.get('reply') or ''
                    err = a.get('error') or ''
            if a is None:
                _send('event: failed\ndata: ' + json.dumps({'error': 'introuvable'}) + '\n\n')
                return
            if len(reply) > sent:
                if not _send('data: ' + json.dumps({'t': reply[sent:]}) + '\n\n'):
                    return
                sent = len(reply)
                last_beat = now
            if status == 'done':
                _send('event: done\ndata: ' + json.dumps({'reply': reply}) + '\n\n')
                return
            if status == 'error':
                _send('event: failed\ndata: '
                      + json.dumps({'error': err or 'analyse échouée', 'reply': reply}) + '\n\n')
                return
            if now - start > SSE_DEADLINE_S:
                _send('event: failed\ndata: '
                      + json.dumps({'error': 'délai dépassé', 'reply': reply}) + '\n\n')
                return
            if now - last_beat > SSE_HEARTBEAT_S:
                if not _send(': ping\n\n'):     # commentaire SSE : tient la socket
                    return
                last_beat = now
            time.sleep(0.2)

    def _security_headers(self):
        # Anti-clickjacking : aucune page LogX AI ne doit pouvoir être
        # embarquée dans un <iframe> d'une origine tierce. SAMEORIGIN/'self'
        # laissent passer les iframes internes au logiciel (même origine,
        # voir test_lightning_iframe_sandbox.py pour l'iframe externe déjà
        # sandboxée séparément).
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Content-Security-Policy', "frame-ancestors 'self'")

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
            m = re.search(r'(?:^|;\s*)rc_token=([^;]+)', self.headers.get('Cookie', ''))
            if m:
                tok = m.group(1)
        import secrets as _secrets
        return bool(tok) and _secrets.compare_digest(tok, AUTH_TOKEN)

    def _require_auth(self):
        if self._client_authorized():
            return True
        # Le corps n'est pas EXPLOITÉ, mais il doit être VIDÉ DE LA SOCKET,
        # sinon ses octets seraient lus comme la requête suivante — requête
        # corrompue, réponse incohérente.
        #
        # Vider PLUTÔT QUE fermer : fermer une connexion dont le tampon de
        # réception contient encore des octets fait envoyer un RST par la pile
        # TCP au lieu d'un FIN, et le RST DÉTRUIT la réponse déjà émise. Le
        # client recevait alors une erreur réseau au lieu du 403 qui lui dit
        # quoi faire (« recharge une page du logiciel »).
        #
        # Borné : vider un corps de taille quelconque serait un vecteur de
        # déni de service (un client non autorisé ferait lire des mégaoctets
        # au serveur). Au-delà du plafond on ferme franchement — le RST est
        # alors acceptable, ce cas étant rare et déjà anormal.
        _DRAIN_MAX = 64 * 1024
        # Transfer-Encoding: chunked (jamais décodé par BaseHTTPRequestHandler)
        # rendait `_len` toujours à 0 sans jamais fermer ni drainer : les
        # octets chunked restaient sur la socket et contaminaient la requête
        # suivante — même désynchronisation que do_POST prévient déjà.
        te = (self.headers.get('Transfer-Encoding') or '').strip().lower()
        if te and te != 'identity':
            self.close_connection = True
            _len = 0
        else:
            _len, _ok = _strict_content_length(self.headers)
            if not _ok:
                self.close_connection = True
                _len = 0
        if 0 < _len <= _DRAIN_MAX:
            try:
                self.rfile.read(_len)   # lu puis jeté : jamais analysé
            except Exception:
                self.close_connection = True
        elif _len:
            self.close_connection = True
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
        # //hôte-externe. Les navigateurs normalisent '\' en '/' pour les
        # schémas spéciaux (http/https) : "/\evil.com" est donc équivalent à
        # "//evil.com" une fois résolu par le navigateur, un contournement du
        # test startswith('//') seul si on ne neutralise pas '\' d'abord.
        _next_norm = next_path.replace('\\', '/') if next_path else ''
        if not next_path or not next_path.startswith('/') or _next_norm.startswith('//'):
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
        te = (self.headers.get('Transfer-Encoding') or '').strip().lower()
        if te and te != 'identity':
            self.close_connection = True
            self._json({'ok': False, 'error': "Transfer-Encoding non supporté"}, 411)
            return
        # Throttle AVANT même de lire le corps : le calcul qu'on protège
        # (PBKDF2) n'a pas encore eu lieu, autant rejeter au plus tôt.
        if _login_rate_limited(ip):
            # Le corps n'est pas EXPLOITÉ (on refuse avant tout PBKDF2), mais il
            # doit quand même être VIDÉ DE LA SOCKET avant de fermer.
            #
            # Fermer une connexion dont le tampon de réception contient encore
            # des octets fait envoyer un RST par la pile TCP au lieu d'un FIN —
            # et un RST DÉTRUIT la réponse déjà émise, y compris si elle est
            # entièrement partie. L'utilisateur qui atteint la limite recevait
            # donc, une fois sur trois sous charge, une erreur réseau au lieu du
            # message « Trop de tentatives ». Reproduit sous charge (3 échecs
            # sur 12) avant correction : ConnectionResetError WinError 10054.
            #
            # Vider règle aussi ce pour quoi la fermeture avait été posée : plus
            # d'octets résiduels interprétés comme la requête SUIVANTE, donc pas
            # de page d'erreur « Bad request syntax » réaffichant le mot de passe
            # en clair. La lecture est BORNÉE au même plafond que le chemin
            # nominal : un corps annoncé au-delà relève du 413 juste en dessous,
            # qui lui ne peut pas être vidé et ferme donc franchement.
            _len, _ok = _strict_content_length(self.headers)
            if not _ok:
                self.close_connection = True
                _len = 0
            if 0 < _len <= 4096:
                try:
                    self.rfile.read(_len)   # lu puis jeté : jamais analysé
                except Exception:
                    pass
            else:
                self.close_connection = True
            self._json({'ok': False,
                       'error': 'Trop de tentatives, réessaie plus tard'}, 429)
            return
        # Même principe que MAX_BODY dans do_POST : la taille est vérifiée
        # AVANT toute lecture, avec un rejet immédiat (413) si elle dépasse le
        # plafond — jamais de lecture partielle qui tronquerait silencieusement
        # un corps trop grand (un mot de passe tient largement dans 4096 octets).
        MAX_LOGIN_BODY = 4096
        length, _ok = _strict_content_length(self.headers)
        if not _ok:
            length = -1   # longueur réelle indéterminable : forcer la fermeture ci-dessous
        if length < 0 or length > MAX_LOGIN_BODY:
            # Ce corps ne sera pas EXPLOITÉ — c'est justement son volume qu'on
            # refuse — mais il doit quand même être VIDÉ DE LA SOCKET, pour la
            # raison déjà expliquée au 429 plus haut : fermer sur un tampon de
            # réception non vide fait envoyer un RST au lieu d'un FIN, et le RST
            # DÉTRUIT la réponse 413 déjà émise. Le client recevait alors une
            # erreur réseau au lieu de « corps trop volumineux ». Mesuré avant
            # correction : 3 échecs sur 10 en exécution ISOLÉE — donc pas un
            # aléa de charge, mais une course permanente que la fermeture
            # « franche » causait elle-même.
            #
            # Vider dispense AUSSI de fermer : plus d'octets résiduels à prendre
            # pour la requête suivante, donc la connexion reste réutilisable.
            # C'est cette propriété-là qui est testable de façon déterministe,
            # contrairement à la course (voir test_access_password.py).
            #
            # Le vidage est BORNÉ : au-delà de PURGE_MAX on ne brûle pas de la
            # bande passante pour rester poli avec un client qui annonce des
            # mégaoctets sur une route de mot de passe — là seulement on ferme
            # sèchement, en assumant le RST.
            PURGE_MAX = 256 * 1024
            if 0 < length <= PURGE_MAX:
                reste = length
                try:
                    while reste > 0:
                        morceau = self.rfile.read(min(reste, 65536))
                        if not morceau:
                            break
                        reste -= len(morceau)     # lu puis jeté : jamais analysé
                except Exception:
                    self.close_connection = True
            else:
                self.close_connection = True
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
