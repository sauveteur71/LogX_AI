# -*- coding: utf-8 -*-
"""Utilitaires génériques : réseau (fetch_url), géodésie locator/distance/azimut, modes numériques."""

import urllib.request
import urllib.error
import urllib.parse
import json
import math
import re
import datetime
import ssl as _ssl
import concurrent.futures as _cf

PORT = 8080
CURRENT_YEAR = datetime.datetime.now().year


# ─── TEMPS : UN SEUL MODÈLE, L'UTC NAÏF ──────────────────────────────────────

def utcnow():
    """L'instant présent en UTC, en datetime NAÏF (sans tzinfo).

    Remplace `datetime.datetime.utcnow()`, déprécié depuis Python 3.12 et
    programmé pour suppression. La valeur rendue est rigoureusement la même :
    même instant, même absence de fuseau.

    POURQUOI NAÏF, ET NON `datetime.now(datetime.UTC)` DIRECTEMENT ?
    Parce que tout le modèle temporel du logiciel est en UTC naïf, et pas par
    accident — un datetime AWARE ne se soustrait PAS à un naïf, il lève
    TypeError. Or l'instant « maintenant » rencontre partout des naïfs :

      - ephem rend des datetime naïfs (`aos.datetime()`), comparés directement
        à cet instant dans logx_sat_passes.passages() ;
      - les dates/heures du log sont naïves PAR NORME (ADIF, Cabrillo) ;
      - les caches DÉJÀ écrits sur le disque des utilisateurs portent des
        horodatages sans fuseau — le cache TLE, les fichiers d'estampille ;
      - l'API ionosondes KC2G rend « 2026-03-19T22:10:05 », sans offset.

    Sur plusieurs de ces frontières le TypeError serait avalé par un `except`
    voisin : la panne serait SILENCIEUSE (la MUF réelle disparaîtrait sans un
    mot). D'où la règle unique du dépôt : en interne le temps est naïf-UTC, et
    ce qui vient de l'extérieur y est ramené par `as_naive_utc`.
    """
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def as_naive_utc(dt):
    """Ramène un datetime au modèle interne : UTC, sans fuseau.

    Un datetime AWARE est réellement CONVERTI en UTC (pas seulement dépouillé
    de son fuseau, ce qui décalerait l'instant) ; un naïf est rendu tel quel,
    supposé déjà UTC ; None passe sans bruit.

    À utiliser aux frontières de LECTURE — `fromisoformat` sur un cache disque
    ou sur une réponse d'API : rien ne garantit qu'un « +00:00 » n'apparaîtra
    pas un jour, et ce jour-là la soustraction qui suit ne doit pas exploser.
    """
    if dt is None or dt.tzinfo is None:
        return dt
    return dt.astimezone(datetime.UTC).replace(tzinfo=None)


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

# Modèle par défaut de chaque fournisseur — la valeur employée quand la config
# n'en porte aucune. Les deux fournisseurs au format propre ne sont pas dans
# OPENAI_COMPATIBLE_ENDPOINTS, d'où cette table qui les couvre tous.
MODELE_DEFAUT = {
    'anthropic': 'claude-sonnet-4-6',
    'gemini':    'gemini-2.0-flash',
    'openai':    OPENAI_COMPATIBLE_ENDPOINTS['openai'][1],
    'mistral':   OPENAI_COMPATIBLE_ENDPOINTS['mistral'][1],
    'xai':       OPENAI_COMPATIBLE_ENDPOINTS['xai'][1],
    'deepseek':  OPENAI_COMPATIBLE_ENDPOINTS['deepseek'][1],
}

# À quoi ressemble un nom de modèle chez chaque fournisseur. Ne sert QU'À
# écarter un nom qui ne peut pas lui appartenir — jamais à valider finement un
# nom de modèle, ce qui périmerait à chaque sortie.
FAMILLES_MODELE = {
    'anthropic': ('claude-',),
    'gemini':    ('gemini-',),
    'openai':    ('gpt-', 'o1', 'o3', 'o4', 'chatgpt-'),
    'mistral':   ('mistral-', 'ministral-', 'magistral-', 'open-mistral',
                  'codestral', 'pixtral'),
    'xai':       ('grok-',),
    'deepseek':  ('deepseek-',),
}


def modele_effectif(provider, demande=None, configure=None):
    """Quel modèle employer réellement — LE CHOIX APPARTIENT À LA CONFIGURATION.

    Une page qui appelle l'IA n'a pas à décider du modèle : elle ignore quel
    fournisseur l'opérateur a réglé. La carte IA envoyait pourtant un nom
    Anthropic codé en dur, et il écrasait le choix de la page CONFIG. Deux
    conséquences mesurées : un opérateur ayant choisi Opus ou Haiku ne l'obtenait
    jamais, et un opérateur ayant choisi OpenAI, Mistral, xAI, DeepSeek ou Gemini
    voyait ce nom Anthropic partir tel quel à leur API — échec garanti à chaque
    message, alors que la veille automatique continuait de fonctionner (elle
    passe par un chemin qui ignorait déjà ce champ).

    `demande` n'est donc honoré que s'il appartient à la FAMILLE du fournisseur
    configuré : un appelant interne garde ainsi le droit de viser un palier
    (Haiku pour une tâche courte), sans pouvoir réintroduire l'incohérence.
    """
    p = (provider or 'anthropic').strip().lower()
    conf = (configure or '').strip()
    dem = (demande or '').strip()
    if dem:
        prefixes = FAMILLES_MODELE.get(p)
        # Fournisseur inconnu de la table : on ne peut rien affirmer, on laisse
        # passer plutôt que d'imposer un défaut qui serait tout aussi arbitraire.
        if prefixes is None or dem.lower().startswith(prefixes):
            return dem
    return conf or MODELE_DEFAUT.get(p, MODELE_DEFAUT['anthropic'])



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


def fetch_url(url, timeout=10, log_url=True):
    """Requête HTTP(S) réellement bornée dans le temps.

    urlopen(timeout=...) ne couvre PAS la résolution DNS : socket.create_connection()
    appelle getaddrinfo() (résolution système, bloquante) AVANT de créer le socket
    et d'appliquer le timeout — sur un réseau captif ou un DNS muet (terrain /P
    sans Internet), l'appel peut rester figé bien au-delà de `timeout` sans
    qu'aucun except ne s'applique encore. On soumet donc la requête à un pool de
    threads et on borne l'ATTENTE du résultat avec .result(timeout=...) : si le
    thread ne revient pas à temps, l'appelant est débloqué immédiatement (le
    thread abandonné continue seul en arrière-plan jusqu'à sa propre fin, sans
    jamais allonger le blocage perçu par l'appelant au-delà de la marge fixée).

    log_url=False (audit sécurité) : quelques appelants (logx_qrz._authenticate)
    portent un secret DANS l'URL elle-même (mot de passe en query string) — même
    tronqué à 60 caractères, `url[:60]` peut exposer les premiers caractères du
    mot de passe pour un indicatif court. Ces appelants passent log_url=False
    pour ne jamais journalier l'URL, seulement le type d'échec."""
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
        if log_url:
            print(f"  [FETCH] {url[:60]}... -> {e}")
        else:
            print(f"  [FETCH] (URL non journalisée — contient un secret) -> {type(e).__name__}")
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

def post_url_json_binary(url, payload, timeout=10, headers=None):
    """Comme post_url_json(), mais pour une réponse BINAIRE (audio, image…) au
    lieu de texte — décoder un flux audio comme de l'UTF-8 le corromprait.
    Utilisé pour les API de synthèse vocale IA cloud (logx_voicekeyer),
    même pool de threads partagé, même bornage DNS/attente.

    Renvoie (status_http, octets_bruts) ; (None, None) si injoignable
    (DNS/timeout/réseau). Sur une erreur HTTP (4xx/5xx), le corps est aussi
    binaire ici — la plupart des API renvoient alors un message JSON, à
    décoder par l'appelant s'il veut l'afficher."""
    def _do():
        data = json.dumps(payload).encode('utf-8')
        hdrs = {'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)'}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data, headers=hdrs, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    try:
        fut = _FETCH_EXECUTOR.submit(_do)
        return fut.result(timeout=timeout + 3)
    except Exception as e:
        print(f"  [FETCH] POST(bin) {url[:60]}... -> {e}")
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

# Maidenhead : champ 2 lettres A-R (20° lon × 10° lat), carré 2 chiffres 0-9
# (2° × 1°), sous-carré 2 lettres A-X (5′ × 2,5′). Le prolongement à 8
# caractères (2 chiffres de plus) existe et reste toléré — on l'ignore, le
# sous-carré suffit largement pour une distance ou un azimut.
#
# CE QUE LA VALIDATION CORRIGE. Il n'y en avait aucune, et le `except:` nu ne
# rattrapait que le int() des chiffres. Mesuré : 'JN18ZZ' rendait 49,06 N —
# HORS de son propre carré, qui s'arrête à 49 ; 'ZZ99XX' rendait une longitude
# de 339° ; 'JN18@@' un point situé AVANT le coin du carré. Aucun message, une
# position plausible et fausse. Les locators arrivent du cluster, de PSK
# Reporter, de l'import ADIF d'un log tiers et surtout de la SAISIE MANUELLE
# en concours, où la faute de frappe est la règle : en THF, un locator faux
# c'est un multiplicateur faux et une distance fausse, donc des points refusés
# au dépouillement.
#
# Les trois copies JavaScript (config, propagation, mobile) validaient déjà
# par une expression régulière équivalente. Seul le Python acceptait tout.
_LOCATOR_RE = re.compile(r'^[A-R]{2}[0-9]{2}(?:[A-X]{2}(?:[0-9]{2})?)?$')


# ─── LA DATE LIMITE DE DÉPÔT, EN VRAIE DATE ─────────────────────────────────
# Le champ `log_deadline` des définitions mêle des codes exploitables
# (« wednesday_after », « 7_days_after », « second_monday_after »…) et du texte
# libre (« 14 jours »). Ces codes étaient AFFICHÉS TELS QUELS à l'opérateur —
# le coach lui annonçait « délai wednesday_after », ce qui ne dit pas s'il lui
# reste quatre jours ou s'il est déjà en retard.
#
# Cette fonction rend la date réelle quand le code est interprétable, et laisse
# passer le texte libre sans l'inventer : mieux vaut « 14 jours » affiché tel
# quel qu'une date fausse au jour près sur une échéance de dépôt.
_DEADLINE_JOURS = {'lundi': 0, 'monday': 0, 'mardi': 1, 'tuesday': 1,
                   'mercredi': 2, 'wednesday': 2, 'jeudi': 3, 'thursday': 3,
                   'vendredi': 4, 'friday': 4, 'samedi': 5, 'saturday': 5,
                   'dimanche': 6, 'sunday': 6}


def date_limite_depot(log_deadline, fin_concours):
    """(date, texte_brut) — la date limite de dépôt, résolue si possible.

    `fin_concours` : date ou datetime de fin de l'épreuve.
    Rend (None, texte) quand le délai n'est pas interprétable : l'appelant
    affiche alors le texte tel quel, sans prétendre à une date.
    """
    brut = str(log_deadline or '').strip()
    if not brut or fin_concours is None:
        return None, brut
    fin = fin_concours
    if isinstance(fin, datetime.datetime):
        fin = fin.date()
    if not isinstance(fin, datetime.date):
        return None, brut
    cle = brut.lower()

    m = re.match(r'^(\d+)_days?_after$', cle)
    if m:
        return fin + datetime.timedelta(days=int(m.group(1))), brut
    m = re.match(r'^(\d+)_hours?_after$', cle)
    if m:
        # Arrondi au jour SUPÉRIEUR : une échéance à 48 h après une fin le
        # dimanche tombe le mardi. Annoncer le lundi ferait courir l'opérateur
        # pour rien ; annoncer trop tard lui coûterait sa participation, donc
        # on ne dépasse jamais l'échéance réelle.
        h = int(m.group(1))
        return fin + datetime.timedelta(days=h // 24), brut
    m = re.match(r'^(?:(second|deuxieme|deuxième|first|premier)_)?'
                 r'([a-zéè]+)_after$', cle)
    if m:
        rang, nom = m.group(1), m.group(2)
        jour = _DEADLINE_JOURS.get(nom)
        if jour is not None:
            delta = (jour - fin.weekday()) % 7 or 7   # STRICTEMENT après la fin
            d = fin + datetime.timedelta(days=delta)
            if rang in ('second', 'deuxieme', 'deuxième'):
                d += datetime.timedelta(days=7)
            return d, brut
    return None, brut


def locator_to_latlon(loc):
    """Centre de la case Maidenhead, en (lat, lon). (None, None) si invalide.

    Un locator à 4 caractères est un Maidenhead valide (correctif M8) : les
    spots PSK Reporter en donnent souvent. On renvoie alors le centre du CARRÉ.
    """
    if not loc:
        return None, None
    l = str(loc).upper().strip().replace(' ', '')
    if not _LOCATOR_RE.match(l):
        return None, None
    lon = (ord(l[0])-65)*20 - 180 + int(l[2])*2
    lat = (ord(l[1])-65)*10 - 90  + int(l[3])
    if len(l) >= 6:
        lon += (ord(l[4])-65)*(2/24) + 1/24     # centre du sous-carré
        lat += (ord(l[5])-65)*(1/24) + 0.5/24
    else:
        # CENTRE DU CARRÉ, soit +1° de longitude et +0,5° de latitude.
        #
        # Le code complétait par 'MM' avant de dérouler le calcul du
        # sous-carré, ce qui donnait +1,0417° et +0,5208° : le point tombait
        # 3,8 km au NORD-EST du centre, systématiquement, sur tout locator à
        # 4 caractères. 'M' est la 13e lettre, or le milieu des 24 lettres
        # n'en est aucune — il est entre 'L' et 'M'. Aucun complément par
        # lettres ne peut donc donner le centre : il faut le calculer.
        lon += 1.0
        lat += 0.5
    return lat, lon

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
