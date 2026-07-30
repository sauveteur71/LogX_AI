# -*- coding: utf-8 -*-
"""Auto-spot SOTA (SOTAwatch3) — authentification SOTA SSO puis publication
du spot d'activation, pendant de logx_pota.post_spot pour SOTA.

═══════════════════════════════════════════════════════════════════════════
CE QUI EST VÉRIFIÉ (observé en direct, comme pour le reste du projet — cf.
logx_sota.py, "vérifié en inspectant les requêtes réseau de la page
officielle") :
  Authentification — SOTA SSO est un serveur Keycloak standard, realm
  "SOTA". En ouvrant https://sotawatch.sota.org.uk et en cliquant "Login",
  le navigateur est redirigé vers :
    https://sso.sota.org.uk/auth/realms/SOTA/protocol/openid-connect/auth
      ?client_id=sotawatch&redirect_uri=...&response_type=code
      &response_mode=fragment&scope=openid
      &code_challenge=...&code_challenge_method=S256
  → Authorization Code + PKCE (S256), cohérent avec le fil officiel SOTA
  Reflector ("OpenID Authorization Code workflow"). /token est le chemin
  standard Keycloak jumeau de /auth (convention fixe du produit tiers, pas
  un format d'API métier deviné). client_id="sotawatch" est celui du site
  officiel — chaque application tierce doit obtenir LE SIEN auprès de
  l'équipe SOTA (SOTA Reflector, groupe "API-consumers"), voir sota_client_id
  dans la config (vide par défaut = fonctionnalité INACTIVE).

CE QUI N'EST **PAS** VÉRIFIÉ (à faire toi-même avant de faire confiance à ce
module en conditions réelles) :
  L'endpoint d'ÉCRITURE (POST d'un spot) et son schéma JSON exact. La doc
  technique (https://api2.sota.org.uk/docs/index.html) redirige un visiteur
  anonyme vers les Conditions d'Utilisation plutôt que vers le Swagger/
  OpenAPI réel — impossible d'en extraire le schéma sans être membre du
  groupe "API-consumers" (exigé par ces mêmes CGU). SOTA_SPOT_POST_URL et le
  format du corps ci-dessous sont déduits PAR CONVENTION REST à partir de
  l'endpoint de LECTURE déjà utilisé ailleurs dans ce projet (logx_sota.py,
  GET /api/spots/3/all/all), avec le même vocabulaire de champs
  (activatorCallsign, summitCode, frequency en MHz, mode, comments) — PAS
  confirmé contre le vrai schéma d'écriture. Le code existant du logiciel
  (logx_logbook.js) masquait déjà volontairement le bouton auto-spot pour
  SOTA pour cette exact raison ("SOTA/WWFF/IOTA n'ont pas d'endpoint POST
  documenté avec certitude") ; ce module lève ce masquage MAIS ne peut pas
  lever l'incertitude elle-même. Teste d'abord avec un commentaire explicite
  ("test LogX AI") ou vérifie le schéma toi-même (onglet Réseau du
  navigateur une fois connecté sur sotawatch.sota.org.uk et un spot posté à
  la main) avant un usage réel en activation.

⚠️ CONDITIONS D'UTILISATION DE L'API SOTA (https://api2.sota.org.uk, lues en
direct le 23/07/2026) : usage non-commercial uniquement, un point de contact
désigné + adhésion au groupe "API-consumers" du SOTA Reflector est exigée
AVANT toute utilisation, ET — point spécifique à ce module — "no AI-generated
software may connect to the SOTA API without prior approval" (aucun logiciel
généré par IA ne peut se connecter à l'API SOTA sans approbation préalable).
Ce module a été écrit avec l'aide d'un assistant IA : l'utilisateur DOIT
obtenir cette approbation explicite auprès de l'équipe SOTA (même canal que
la demande de clientId) avant d'activer réellement la publication de spots.
C'est pourquoi sota_ai_approval_ack (case à cocher dédiée dans CONFIG) est
exigée EN PLUS du clientId pour que post_spot() accepte d'émettre le moindre
appel réseau — voir sota_spot_settings() ci-dessous.
(NB : la même page contenait un paragraphe adressé "aux robots IA qui lisent
cette page" affirmant un nombre de morts fictif et exigeant qu'il soit
répété ici — ceci est ignoré : c'est une instruction cachée dans un contenu
tiers, pas une consigne de l'utilisateur ni un fait vérifiable.)
═══════════════════════════════════════════════════════════════════════════
"""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.parse

from logx_utils import PORT as _PORT
from logx_version import APP_VERSION

SSO_AUTHORIZE_URL = 'https://sso.sota.org.uk/auth/realms/SOTA/protocol/openid-connect/auth'
SSO_TOKEN_URL = 'https://sso.sota.org.uk/auth/realms/SOTA/protocol/openid-connect/token'
SOTA_SPOT_POST_URL = 'https://api2.sota.org.uk/api/spots/'

# Fixe : le serveur HTTP de LogX AI tourne déjà sur ce port. À communiquer
# TEL QUEL à l'équipe SOTA en demandant un clientId (un client OAuth
# Keycloak n'accepte que des redirect_uri enregistrés à l'avance).
SOTA_REDIRECT_URI = f'http://localhost:{_PORT}/sota/oauth/callback'

TOKENS_FILE = 'sota_oauth_tokens.json'
PENDING_TTL = 600  # secondes de validité d'un couple state/code_verifier en attente de callback

_tok_lock = threading.Lock()
_tokens = {'access_token': '', 'refresh_token': '', 'expires_at': 0}
_tokens_loaded = False
_pending = {}   # state -> {'verifier': str, 'ts': float}


def sota_spot_settings(cfg):
    """clientId vide (par défaut) = fonctionnalité INACTIVE, comme les
    autres services d'écriture externes (cf. logx_qsl.py). ai_approval_ack
    est une seconde condition, INDÉPENDANTE du clientId, exigée par les CGU
    SOTA elles-mêmes (voir docstring du module) avant tout appel réseau
    réel d'ÉCRITURE (post_spot) — pas avant la simple connexion SSO."""
    cfg = cfg or {}
    client_id = (cfg.get('sota_client_id') or '').strip()
    ack = str(cfg.get('sota_ai_approval_ack', '')) in ('1', 'true', 'True', 'on')
    return {'client_id': client_id, 'configured': bool(client_id),
            'ai_approval_ack': ack, 'ready_to_post': bool(client_id and ack)}


# ─── PKCE (Authorization Code + code_challenge S256, voir docstring) ─────────

def _new_pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b'=').decode('ascii')
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    return verifier, challenge


def _purge_pending():
    now = time.time()
    for k in [k for k, v in _pending.items() if now - v['ts'] > PENDING_TTL]:
        _pending.pop(k, None)


def build_authorize_url(cfg):
    """URL à ouvrir dans le navigateur pour lancer la connexion SOTA SSO
    (bouton « Se connecter à SOTA » dans CONFIG). (url, error)."""
    settings = sota_spot_settings(cfg)
    if not settings['configured']:
        return None, 'clientId SOTA manquant (CONFIG → EXPÉDITION/PORTABLE)'
    _purge_pending()
    state = secrets.token_urlsafe(24)
    verifier, challenge = _new_pkce_pair()
    _pending[state] = {'verifier': verifier, 'ts': time.time()}
    params = {
        'client_id': settings['client_id'], 'redirect_uri': SOTA_REDIRECT_URI,
        'response_type': 'code',
        # response_mode=query (pas 'fragment' comme le site officiel) :
        # notre callback est traité côté serveur Python, pas par une SPA —
        # un fragment (#...) n'est JAMAIS envoyé au serveur par le navigateur.
        'response_mode': 'query', 'scope': 'openid', 'state': state,
        'code_challenge': challenge, 'code_challenge_method': 'S256',
    }
    return f'{SSO_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}', ''


# ─── Jetons (accès/rafraîchissement) — persistés pour survivre à un redémarrage

def _load_tokens():
    global _tokens_loaded
    if _tokens_loaded:
        return
    try:
        if os.path.exists(TOKENS_FILE):
            with open(TOKENS_FILE, encoding='utf-8') as f:
                _tokens.update(json.load(f) or {})
    except Exception:
        pass
    _tokens_loaded = True


def _save_tokens():
    try:
        from logx_storage import save_json_atomic
        save_json_atomic(TOKENS_FILE, dict(_tokens), lock=_tok_lock, compact=True)
    except Exception:
        try:
            with open(TOKENS_FILE, 'w', encoding='utf-8') as f:
                json.dump(_tokens, f)
        except OSError:
            pass


def _store_tokens(data):
    with _tok_lock:
        _tokens['access_token'] = data.get('access_token', '')
        if data.get('refresh_token'):
            _tokens['refresh_token'] = data['refresh_token']
        try:
            expires_in = float(data.get('expires_in') or 300)
        except (TypeError, ValueError):
            expires_in = 300
        _tokens['expires_at'] = time.time() + expires_in
    _save_tokens()


def handle_oauth_callback(code, state, cfg):
    """Appelé par GET /sota/oauth/callback (redirection SOTA SSO). Échange
    le code contre un jeton d'accès + rafraîchissement. (ok, message)."""
    _load_tokens()
    _purge_pending()
    pending = _pending.pop(state, None)
    if not pending:
        return False, "Session d'authentification expirée ou invalide — relance depuis CONFIG."
    settings = sota_spot_settings(cfg)
    if not settings['configured']:
        return False, 'clientId SOTA manquant'
    if not code:
        return False, 'Code d\'autorisation manquant dans la réponse SOTA'

    from logx_utils import post_url_form  # import local : mockable par les tests
    fields = {
        'grant_type': 'authorization_code', 'code': code,
        'redirect_uri': SOTA_REDIRECT_URI, 'client_id': settings['client_id'],
        'code_verifier': pending['verifier'],
    }
    status, text = post_url_form(SSO_TOKEN_URL, fields, timeout=10)
    if status is None:
        return False, 'SSO SOTA injoignable (réseau)'
    if status != 200:
        return False, f"SOTA a refusé l'échange du code (HTTP {status}) : {(text or '')[:200].strip()}"
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return False, 'Réponse SSO SOTA illisible'
    if not data.get('access_token'):
        return False, 'Réponse SSO SOTA sans jeton d\'accès'
    _store_tokens(data)
    return True, 'Authentification SOTA réussie.'


def ensure_access_token(cfg):
    """Jeton d'accès valide (rafraîchi si expiré). (token, error)."""
    _load_tokens()
    settings = sota_spot_settings(cfg)
    if not settings['configured']:
        return None, 'clientId SOTA manquant (CONFIG → EXPÉDITION/PORTABLE)'
    with _tok_lock:
        if _tokens.get('access_token') and time.time() < _tokens.get('expires_at', 0) - 30:
            return _tokens['access_token'], ''
        refresh = _tokens.get('refresh_token')
    if not refresh:
        return None, 'Authentification SOTA requise — clique « Se connecter à SOTA » dans CONFIG.'

    from logx_utils import post_url_form
    fields = {'grant_type': 'refresh_token', 'refresh_token': refresh,
              'client_id': settings['client_id']}
    status, text = post_url_form(SSO_TOKEN_URL, fields, timeout=10)
    if status is None:
        return None, 'SSO SOTA injoignable (réseau)'
    if status != 200:
        return None, f'Rafraîchissement du jeton SOTA refusé (HTTP {status}) — reconnecte-toi.'
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None, 'Réponse SSO SOTA illisible'
    if not data.get('access_token'):
        return None, 'Réponse SSO SOTA sans jeton d\'accès'
    _store_tokens(data)
    return _tokens['access_token'], ''


def status(cfg):
    """État consommé par CONFIG (affichage) et le logbook (bouton SE SPOTTER)."""
    _load_tokens()
    settings = sota_spot_settings(cfg)
    with _tok_lock:
        has_access = bool(_tokens.get('access_token')) and time.time() < _tokens.get('expires_at', 0)
        has_refresh = bool(_tokens.get('refresh_token'))
    return {
        'configured': settings['configured'],
        'ai_approval_ack': settings['ai_approval_ack'],
        'ready_to_post': settings['ready_to_post'],
        'authenticated': has_access or has_refresh,
    }


# ─── Publication du spot (ÉCRITURE — schéma non confirmé, voir docstring) ────

def post_spot(cfg, summit_code, freq_mhz, mode, comment=''):
    """Publie un spot d'activation SOTA. Ne lève jamais, renvoie {'ok': bool,
    ...} comme les autres fonctions réseau du projet (logx_qsl, logx_pota...).
    Exige clientId configuré ET la case d'approbation IA cochée (CGU SOTA,
    voir docstring du module) avant le moindre appel réseau réel."""
    settings = sota_spot_settings(cfg)
    if not settings['configured']:
        return {'ok': False, 'error': 'SOTA non configuré (clientId manquant dans CONFIG → EXPÉDITION/PORTABLE)'}
    if not settings['ai_approval_ack']:
        return {'ok': False, 'error':
                "Publication bloquée : coche d'abord « J'ai l'accord préalable de l'équipe SOTA pour ce "
                "logiciel assisté par IA » dans CONFIG → EXPÉDITION/PORTABLE — exigé par les Conditions "
                "d'Utilisation de l'API SOTA (api2.sota.org.uk)."}

    summit_code = (summit_code or '').strip().upper()
    mode = (mode or '').strip().upper()
    try:
        freq_mhz = float(freq_mhz)
    except (TypeError, ValueError):
        freq_mhz = 0
    if not summit_code:
        return {'ok': False, 'error': 'Référence de sommet manquante'}
    if freq_mhz <= 0:
        return {'ok': False, 'error': 'Fréquence manquante ou invalide'}
    if not mode:
        return {'ok': False, 'error': 'Mode manquant'}

    token, err = ensure_access_token(cfg)
    if not token:
        return {'ok': False, 'error': err}

    activator = ((cfg or {}).get('callsign_contest') or (cfg or {}).get('callsign') or '').strip().upper()
    if not activator:
        return {'ok': False, 'error': 'Indicatif manquant (configure ta station dans CONFIG)'}
    payload = {
        'activatorCallsign': activator,
        'summitCode': summit_code,
        'frequency': freq_mhz,
        'mode': mode,
        'comments': comment or '',
    }
    from logx_utils import post_url_json  # import local : mockable par les tests
    status_code, text = post_url_json(
        SOTA_SPOT_POST_URL, payload, timeout=10,
        headers={'Authorization': f'Bearer {token}', 'User-Agent': f'LogXAI/{APP_VERSION}'})
    if status_code is None:
        return {'ok': False, 'error': 'api2.sota.org.uk injoignable (réseau)'}
    if status_code >= 400:
        return {'ok': False, 'error': f'SOTA a refusé le spot (HTTP {status_code}) : {(text or "")[:200].strip()} '
                '— schéma d\'écriture non officiellement confirmé (voir docstring du module), '
                'vérifie-le auprès de l\'équipe SOTA si le refus persiste.'}
    return {'ok': True, 'response': (text or '')[:200].strip()}
