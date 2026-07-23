# -*- coding: utf-8 -*-
"""Utilitaires génériques : réseau (fetch_url), géodésie locator/distance/azimut, modes numériques."""

import urllib.request
import urllib.error
import urllib.parse
import json
import math
import datetime
import ssl as _ssl
import concurrent.futures as _cf

PORT = 8080
CURRENT_YEAR = datetime.datetime.now().year


# ─── FOURNISSEURS IA « OpenAI Chat Completions » ─────────────────────────────
# OpenAI, Mistral AI (la référence française, api.mistral.ai), xAI/Grok
# (api.x.ai) et DeepSeek (api.deepseek.com) partagent tous le même contrat
# d'API (endpoint unique, header Authorization: Bearer, messages
# [{role,content}], réponse choices[0].message.content) — vérifié sur la
# documentation officielle de chacun avant d'écrire ce code, jamais deviné.
# Seuls Anthropic (tool-use natif) et Gemini (systemInstruction dédié) ont un
# format différent et restent gérés à part dans logx_http.py/logx_rules_ai.py.
OPENAI_COMPATIBLE_ENDPOINTS = {
    'openai':   ('https://api.openai.com/v1/chat/completions', 'gpt-4o'),
    'mistral':  ('https://api.mistral.ai/v1/chat/completions', 'mistral-large-latest'),
    'xai':      ('https://api.x.ai/v1/chat/completions',       'grok-4.5'),
    'deepseek': ('https://api.deepseek.com/chat/completions',  'deepseek-v4-flash'),
}



# ─── MODES NUMÉRIQUES À FILTRER ──────────────────────────────────────────────
MODES_NUMERIQUES = ['FT8','FT4','JS8','WSPR','PSK','RTTY','DIGI','DATA','MFSK']



# ─── UTILS ───────────────────────────────────────────────────────────────────
# Python 3.13 active VERIFY_X509_STRICT par défaut, ce qui rejette le certificat
# racine des antivirus interceptant le HTTPS (Avast Web Shield : "Basic
# Constraints of CA cert not marked critical") — et donc TOUTES les requêtes
# HTTPS sur ces machines. SSL_CTX garde la vérification complète des certificats
# (racine Avast présente dans le magasin Windows) mais retire seulement le mode
# strict, i.e. le comportement de Python <= 3.12. À passer en context= sur tout
# urlopen HTTPS du projet.
SSL_CTX = _ssl.create_default_context()
if hasattr(_ssl, 'VERIFY_X509_STRICT'):
    SSL_CTX.verify_flags &= ~_ssl.VERIFY_X509_STRICT

# NOTE SÉCURITÉ : il n'y a PLUS de repli en CERT_NONE. L'ancien code retentait
# automatiquement SANS vérification de certificat dès la moindre erreur SSL — un
# attaquant en interception (WiFi public, DNS spoofing) n'avait qu'à présenter un
# certificat invalide pour déclencher lui-même ce repli et servir du contenu
# forgé (spots, données injectées dans l'app qui pilote la radio). SSL_CTX vérifie
# toujours les certificats contre le magasin Windows (racine Avast incluse) ; seul
# le mode STRICT de Python 3.13 est désactivé. Une vraie erreur SSL échoue net.

# Pool partagé et borné : fetch_url() y soumet chaque requête au lieu de
# créer un thread par appel (pas de fuite de threads en cas de dépassement).
_FETCH_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=8, thread_name_prefix='fetch_url')


def fetch_url(url, timeout=10):
    """Requête HTTP(S) réellement bornée dans le temps.

    urlopen(timeout=...) ne couvre PAS la résolution DNS : socket.create_connection()
    appelle getaddrinfo() (résolution système, bloquante) AVANT de créer le socket
    et d'appliquer le timeout — sur un réseau captif ou un DNS muet (terrain /P
    sans Internet), l'appel peut rester figé bien au-delà de `timeout` sans
    qu'aucun except ne s'applique encore. On soumet donc la requête à un pool de
    threads et on borne l'ATTENTE du résultat avec .result(timeout=...) : si le
    thread ne revient pas à temps, l'appelant est débloqué immédiatement (le
    thread abandonné continue seul en arrière-plan jusqu'à sa propre fin, sans
    jamais allonger le blocage perçu par l'appelant au-delà de la marge fixée)."""
    def _do():
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)',
        })
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            charset = resp.headers.get_content_charset() or 'utf-8'
            return resp.read().decode(charset, errors='replace')

    try:
        fut = _FETCH_EXECUTOR.submit(_do)
        return fut.result(timeout=timeout + 3)
    except Exception as e:
        print(f"  [FETCH] {url[:60]}... -> {e}")
        return None

def fetch_url_binary(url, timeout=10):
    """Comme fetch_url(), mais renvoie les octets bruts sans décodage — pour
    les formats binaires (ex. classeur .ods de wcagroup.org), même bornage
    DNS/attente via le pool de threads partagé."""
    def _do():
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)',
        })
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            return resp.read()

    try:
        fut = _FETCH_EXECUTOR.submit(_do)
        return fut.result(timeout=timeout + 3)
    except Exception as e:
        print(f"  [FETCH] {url[:60]}... -> {e}")
        return None

def post_url_json(url, payload, timeout=10, headers=None):
    """Comme fetch_url(), mais en POST avec un corps JSON — même pool de
    threads partagé, pour le même motif (getaddrinfo() bloquant hors du
    socket, non couvert par le timeout d'urlopen). Utilisé pour toute
    soumission (self-spot, API tierce...) qui ne doit jamais geler le thread
    HTTP du serveur (ex. logx_pota.post_spot).

    Renvoie (status_http, texte_réponse) ; (None, None) si injoignable
    (DNS/timeout/réseau). Un statut d'erreur HTTP (4xx/5xx) est remonté tel
    quel avec son corps — à distinguer d'une panne réseau côté appelant,
    plutôt que masqué en simple None comme le ferait un except trop large."""
    def _do():
        data = json.dumps(payload).encode('utf-8')
        hdrs = {'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)'}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data, headers=hdrs, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
                charset = resp.headers.get_content_charset() or 'utf-8'
                return resp.status, resp.read().decode(charset, errors='replace')
        except urllib.error.HTTPError as e:
            charset = (e.headers.get_content_charset() if e.headers else None) or 'utf-8'
            return e.code, e.read().decode(charset, errors='replace')

    try:
        fut = _FETCH_EXECUTOR.submit(_do)
        return fut.result(timeout=timeout + 3)
    except Exception as e:
        print(f"  [FETCH] POST {url[:60]}... -> {e}")
        return None, None

def post_url_form(url, fields, timeout=10, headers=None):
    """Comme post_url_json(), mais en POST application/x-www-form-urlencoded —
    le format attendu par la plupart des API "legacy" du monde radioamateur
    (QRZ Logbook, Club Log realtime.php, HRDLog...). Même pool de threads
    partagé, même motif de bornage (DNS non couvert par le timeout d'urlopen).

    Renvoie (status_http, texte_réponse) ; (None, None) si injoignable."""
    def _do():
        data = urllib.parse.urlencode(fields).encode('utf-8')
        hdrs = {'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)'}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data, headers=hdrs, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
                charset = resp.headers.get_content_charset() or 'utf-8'
                return resp.status, resp.read().decode(charset, errors='replace')
        except urllib.error.HTTPError as e:
            charset = (e.headers.get_content_charset() if e.headers else None) or 'utf-8'
            return e.code, e.read().decode(charset, errors='replace')

    try:
        fut = _FETCH_EXECUTOR.submit(_do)
        return fut.result(timeout=timeout + 3)
    except Exception as e:
        print(f"  [FETCH] POST {url[:60]}... -> {e}")
        return None, None

def locator_to_latlon(loc):
    # Correctif M8 : un locator à 4 caractères est un Maidenhead valide (déjà
    # accepté par le formulaire de config et par locatorToLatLon() côté JS,
    # qui le complète elle-même avec 'MM') — le rejeter ici cassait en silence
    # tout appelant qui ne compensait pas déjà (ex. logx_psk.py, dont les
    # locators PSK Reporter font souvent 4 caractères).
    if not loc:
        return None, None
    l = loc.upper()
    if len(l) == 4:
        l += 'MM'
    if len(l) < 6:
        return None, None
    try:
        lon = (ord(l[0])-65)*20 - 180 + int(l[2])*2 + (ord(l[4])-65)*(2/24) + 1/24
        lat = (ord(l[1])-65)*10 - 90  + int(l[3])   + (ord(l[5])-65)*(1/24) + 0.5/24
        return lat, lon
    except:
        return None, None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dLat = math.radians(lat2-lat1)
    dLon = math.radians(lon2-lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dLon/2)**2
    # Correctif M7 : le JS (Math.round) arrondit au plus proche alors que
    # int() ici tronque toujours vers le bas — jusqu'à 1 km d'écart entre
    # la distance affichée côté client et celle calculée côté serveur.
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

def bearing(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2-lon1)
    y = math.sin(dl)*math.cos(phi2)
    x = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dl)
    b = math.degrees(math.atan2(y, x))
    # Correctif M7 : même écart d'arrondi que haversine() ci-dessus.
    return round((b+360) % 360)

def cardinal(deg):
    dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSO','SO','OSO','O','ONO','NO','NNO']
    return dirs[round(deg/22.5) % 16]

def is_digital_mode(text):
    return any(m in text.upper() for m in MODES_NUMERIQUES)
