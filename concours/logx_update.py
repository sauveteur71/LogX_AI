# -*- coding: utf-8 -*-
"""Mise à jour automatique de LogX AI — vérifie la dernière release GitHub,
propose le téléchargement + l'installation à l'utilisateur (jamais silencieux :
c'est un clic de l'opérateur qui déclenche le téléchargement ET l'installation),
et relance l'exécutable une fois remplacé.

Ne touche JAMAIS au dossier de données utilisateur (logx_bootstrap.user_data_dir()) :
seul l'exécutable lui-même est remplacé, exactement comme une réinstallation
manuelle — aucune perte de log, config, ou cache.

Toute la partie "remplacer l'exe en cours d'exécution" ne s'applique qu'en
mode figé (PyInstaller) : en développement (`python logx_serveur.py`),
sys.executable est l'interpréteur Python lui-même, rien à remplacer.

─── VÉRIFICATION D'INTÉGRITÉ (SHA-256) ───────────────────────────────────────
L'API GitHub Releases expose, par asset, un champ 'digest' au format
'sha256:<64 hex>' (vérifié en direct sur ce dépôt : présent et cohérent sur
toutes les releases publiées par le workflow build-release.yml — asset upload
via `actions/upload-release-asset`/`gh release create`, qui calcule et publie
ce digest automatiquement depuis 2024). AUCUN téléchargement — direct, via
passerelle réseau (B) ou via un pair local (C) — n'est accepté sans que son
empreinte SHA-256 corresponde exactement à ce digest : si l'API ne l'expose
pas pour un asset donné (champ absent/format inattendu), le téléchargement de
CET asset est REFUSÉ plutôt que d'accepter un binaire non vérifié en silence.

─── RELAIS RÉSEAU (B, priorité) ET PAIR-À-PAIR (C, secours) ──────────────────
Contexte : retour beta-testeur sur la fiabilité en DXpédition/contest multi-op
avec internet absent ou dégradé sur le poste qui a besoin de la mise à jour.

  B) Passerelle réseau : un poste qui a internet relaie, sur simple demande
     d'un autre poste du LAN, une requête de téléchargement vers l'API
     GitHub Releases officielle. Le contenu qui transite est le contenu
     AUTHENTIQUE de GitHub — la passerelle fait une requête HTTPS normale
     (même SSL_CTX que le chemin direct) vers l'URL officielle de l'asset et
     RESTREINT à cette URL (construite ici à partir d'un tag+plateforme
     validés, jamais d'une URL fournie par l'appelant — voir resolve_relay_
     asset, anti-SSRF), puis relaie les octets EN FLUX (jamais un fichier de
     son propre disque, jamais une copie mise en cache pour l'occasion).
  C) Pair-à-pair — SECOURS UNIQUEMENT, déclenché seulement si (B) est
     indisponible : un poste qui a DÉJÀ téléchargé et VÉRIFIÉ un exécutable
     (hash SHA-256 validé, voir ci-dessus) le sert à un autre poste via un
     point HTTP dédié, TOUJOURS le même fichier interne (_download['path']),
     jamais un chemin fourni par le client (pas de traversée de répertoire).
     Priorité B>C RESTREINTE CÔTÉ SERVEUR (pas seulement une convention
     d'interface côté client) : avant de servir une requête mode='peer',
     _do_download_via_network sonde elle-même (scan_network_candidates) la
     liste des candidats — ceux fournis par l'appelant UNIS à ceux que CE
     serveur a lui-même vus passer sur le LAN (peer_versions, voir logx_
     http.py, jamais une donnée fournie par le client) — et REFUSE le
     secours pair-à-pair si l'un d'eux répond disponible comme passerelle,
     même pour un appel HTTP direct qui contournerait l'IHM cliente.

  Compromis de sécurité (documenté aussi dans le commit) : dans LES DEUX cas,
  le poste RECEVEUR doit déjà posséder sa PROPRE référence de hash (obtenue
  par un contact DIRECT antérieur avec l'API GitHub, même périmé en fraîcheur
  — un digest de release publiée est stable indéfiniment) AVANT de tenter un
  téléchargement via le réseau local : jamais une référence fournie par la
  passerelle ou le pair lui-même, même en (B) où le contenu vient bien de
  GitHub — sans ça, UNE SEULE machine compromise pourrait fournir à la fois
  le contenu ET la preuve de son intégrité. Un poste qui n'a JAMAIS réussi un
  contact direct avec GitHub (aucune référence locale) voit donc les deux
  chemins réseau REFUSÉS explicitement, avec un message clair — jamais un
  repli silencieux sur la confiance aveugle envers le pair/la passerelle.

  « Même ancien » vaut Y COMPRIS après un redémarrage de l'exécutable
  (coupure secteur, déplacement du poste — routinier en DXpédition) : la
  référence {tag, asset_sha256, asset_size} est PERSISTÉE sur disque à chaque
  contact GitHub réussi (_save_reference, dans user_data_dir()/update/ comme
  les téléchargements du module) et rechargée en secours par
  start_download_via_network quand le cache mémoire du processus est vide
  (_load_persisted_reference). Sans cette persistance, la fenêtre
  d'utilisabilité réelle de B/C se réduisait à « contact GitHub réussi plus
  tôt dans le MÊME run de processus » — un simple restart de LogXAI.exe
  ramenait un poste sans internet au refus « jamais contacté », contredisant
  le compromis documenté ci-dessus.
"""
import hashlib
import ipaddress
import os
import re
import shlex
import socket
import sys
import stat
import json
import time
import threading
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from logx_utils import PORT, SSL_CTX
from logx_version import APP_VERSION
from logx_bootstrap import is_frozen, user_data_dir

GITHUB_REPO = 'sauveteur71/radioaamateur-program-Contest'
# /releases/latest (PAS utilisé ici) exclut par définition tout release
# marqué "prerelease" — or CHAQUE release LogX AI l'est tant qu'on reste en
# beta (v0.9-beta1...), ce qui le ferait toujours répondre 404. On prend donc
# la liste complète (déjà triée du plus récent au plus ancien par l'API) et
# on garde son 1er élément — vérifié en direct : /latest -> 404, /releases[0] -> v0.9-beta1.
RELEASES_API = f'https://api.github.com/repos/{GITHUB_REPO}/releases'
RELEASE_BY_TAG_API = f'https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{{tag}}'
CHECK_TTL = 6 * 3600  # 6h : une nouvelle release n'apparaît pas seconde par seconde

# Suffixe/extension de l'artefact par plateforme — doit correspondre
# EXACTEMENT à la matrice de .github/workflows/build-release.yml. Le nom
# COMPLET inclut aussi le tag de la release (ex. LogXAI-v0.9-beta2.exe,
# LogXAI-v0.9-beta2-macos) : impossible à figer ici puisqu'il change à
# chaque version, il est reconstruit dans _build_result() à partir du
# tag_name de la release effectivement récupérée.
_ASSET_SUFFIX_BY_PLATFORM = {
    'win': ('', '.exe'),
    'darwin': ('-macos', ''),
    'linux': ('-linux', ''),
}

# Taille de bloc pour TOUS les flux (téléchargement direct, relais passerelle,
# service pair-à-pair, ré-hachage) — jamais un fichier entier chargé en
# mémoire, même pour un exécutable de plusieurs dizaines de Mo.
_CHUNK = 262144

# Format de tag accepté pour un relais/service réseau — voir resolve_relay_
# asset : borne stricte contre une injection dans l'URL GitHub reconstruite
# (le tag vient d'un appelant sur le LAN, jamais garanti de confiance avant
# validation). Exemples valides : v0.9-beta3, 1.2.3.
_TAG_RE = re.compile(r'^v?[0-9][0-9A-Za-z.\-]{0,40}$')

_lock = threading.Lock()
_cache = {'ts': 0, 'result': None}
_checking = False
_download = {
    'status': 'idle', 'pct': 0, 'error': '', 'path': '',
    # Champs ajoutés par la vérification d'intégrité / les chemins réseau —
    # voir get_download_status() : exposés tels quels, consommés par
    # logx_statusbar.js (installer) et logx_logbook.js (étiquette réseau).
    'verified': False, 'sha256': '', 'version': '',
    'via': 'direct',      # 'direct' | 'gateway' (B) | 'peer' (C, secours)
    'via_peer': '',       # IP du poste passerelle/pair utilisé, si via != 'direct'
}

# Le thread de téléchargement EN COURS — hors de _download, qui est sérialisé
# tel quel vers le client (get_download_status -> dict -> JSON) : un objet
# Thread n'y a pas sa place.
#
# POURQUOI CETTE RÉFÉRENCE EXISTE : LE VERROU FANTÔME. start_download* pose
# status='downloading' puis refuse tout nouvel appel tant que ce statut tient.
# Si le thread meurt SANS poser d'état terminal (exception hors try — c'était
# le cas des premières lignes de _do_download_via_network — ou Thread.start()
# qui lève sous famine de threads), rien ne réinitialisait jamais ce statut :
# LA MISE À JOUR ÉTAIT MORTE JUSQU'AU REDÉMARRAGE, sans message. Sur une
# expédition, c'est la panne qu'on découvre le jour où on en a besoin.
# Avec cette référence, _demarrer_telechargement() détecte l'orphelin
# (status='downloading' + thread mort) et s'auto-guérit.
_download_thread = None


def _demarrer_telechargement(target, args, via='direct'):
    """Pose 'downloading' et démarre le thread, le tout SOUS _lock, d'un bloc.

    Retourne (True, '') ou (False, raison). Trois protections, chacune née
    d'un défaut réel constaté :
      1. l'ORPHELIN s'auto-guérit : status='downloading' avec un thread mort
         (ou jamais démarré) est un état cadavre — on le remplace par 'error'
         et on laisse le nouveau téléchargement partir ;
      2. Thread.start() PEUT LEVER (RuntimeError « can't start new thread »
         sous famine — observé sur ce poste pendant la suite de tests) : sans
         le try, le statut 'downloading' venait d'être posé et devenait
         précisément l'orphelin du point 1 ;
      3. start() est appelé sous _lock : entre la pose du statut et celle de
         _download_thread, aucun autre appel ne peut observer un 'downloading'
         sans thread et conclure à tort à un orphelin. Pas de deadlock : le
         thread enfant qui voudrait _lock attend simplement la sortie du with.
    """
    global _download_thread
    with _lock:
        if _download['status'] == 'downloading':
            if _download_thread is not None and _download_thread.is_alive():
                return False, 'Un téléchargement est déjà en cours.'
            # Orphelin : le statut dit « en cours », aucun thread ne vit.
            _download.update(
                status='error', verified=False,
                error='Téléchargement précédent interrompu sans état terminal '
                      '(thread mort) — état réinitialisé automatiquement.')
        t = threading.Thread(target=target, args=args, daemon=True)
        _download.update(status='downloading', pct=0, error='', path='',
                          verified=False, sha256='', version='',
                          via=via, via_peer='')
        try:
            t.start()
        except Exception as e:
            _download.update(status='error', verified=False,
                             error=f'Impossible de démarrer le téléchargement : {e}')
            _download_thread = None
            return False, f'Impossible de démarrer le téléchargement : {e}'
        _download_thread = t
    return True, ''


def _platform_key():
    if sys.platform.startswith('win'):
        return 'win'
    if sys.platform == 'darwin':
        return 'darwin'
    return 'linux'


def _parse_digest(raw):
    """'sha256:<64 hex>' -> hex en minuscules, ou None si absent/format
    inattendu/algorithme différent. Ne JAMAIS accepter un autre algorithme
    que sha256 ici : un digest 'sha1:...' (plus faible) ou un format non
    reconnu doit être traité comme ABSENT (retombe sur le refus prévu par
    _do_download quand expected_sha256 est vide), jamais une fausse
    confiance sur un algorithme plus faible ou mal parsé."""
    raw = str(raw or '')
    if not raw.startswith('sha256:'):
        return None
    hexpart = raw[len('sha256:'):].strip().lower()
    if len(hexpart) == 64 and all(c in '0123456789abcdef' for c in hexpart):
        return hexpart
    return None


def _fetch_latest_release():
    """Appel réseau RÉEL et bloquant — uniquement depuis un thread
    d'arrière-plan (voir get_cached_check), jamais depuis le thread HTTP.
    Renvoie None si le dépôt n'a encore aucune release publiée (liste vide),
    plutôt que de planter sur un accès data[0] hors limites."""
    req = urllib.request.Request(RELEASES_API, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)',
        'Accept': 'application/vnd.github+json',
    })
    with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
        releases = json.loads(resp.read().decode('utf-8', errors='replace'))
    return releases[0] if releases else None


def _fetch_release_by_tag(tag):
    """Comme _fetch_latest_release mais pour un tag précis — utilisé par le
    poste PASSERELLE (chemin B) pour retrouver l'asset d'une plateforme qui
    n'est pas forcément la sienne (le poste receveur peut tourner sur un OS
    différent). Appel réseau réel, jamais depuis le thread HTTP principal."""
    url = RELEASE_BY_TAG_API.format(tag=urllib.parse.quote(tag, safe=''))
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)',
        'Accept': 'application/vnd.github+json',
    })
    with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
        return json.loads(resp.read().decode('utf-8', errors='replace'))


def _build_result(data):
    tag = str(data.get('tag_name', '') or '').strip()
    latest = tag[1:] if tag[:1].lower() == 'v' else tag
    suffix, ext = _ASSET_SUFFIX_BY_PLATFORM[_platform_key()]
    # Nom attendu reconstruit avec CE tag (celui de la release récupérée),
    # pas APP_VERSION : c'est justement quand ils diffèrent qu'on cherche
    # l'artefact à télécharger.
    asset_name = f'LogXAI-{tag}{suffix}{ext}' if tag else ''
    asset_url = ''
    asset_sha256 = ''
    asset_size = 0
    for a in (data.get('assets') or []):
        if a.get('name') == asset_name:
            asset_url = a.get('browser_download_url', '')
            asset_size = int(a.get('size') or 0)
            asset_sha256 = _parse_digest(a.get('digest')) or ''
            break
    return {
        'available': bool(latest) and latest != APP_VERSION,
        'current': APP_VERSION,
        'latest': latest or APP_VERSION,
        # Tag GitHub BRUT (avec son 'v' éventuel, ex. 'v0.9-beta3') — 'latest'
        # ci-dessus est la version "affichable" (sans 'v'), mais reconstruire
        # une URL d'asset ou interroger /releases/tags/{tag} exige le tag
        # EXACT tel que GitHub le connaît (voir resolve_relay_asset,
        # start_download_via_network).
        'tag': tag,
        'release_url': data.get('html_url', ''),
        'notes': str(data.get('body', '') or '')[:2000],
        'asset_url': asset_url,
        # '' si l'API n'expose pas de digest fiable pour CET asset — dans ce
        # cas _do_download refuse le téléchargement plutôt que l'accepter à
        # l'aveugle (voir docstring du module).
        'asset_sha256': asset_sha256,
        'asset_size': asset_size,
        # Le téléchargement+remplacement automatique n'a de sens qu'en exe
        # figé ET si l'artefact de cette plateforme existe sur la release.
        'installable': bool(asset_url) and is_frozen(),
        'checking': False,
        # Repo exposé ici pour que le bouton "signaler un problème" de la
        # barre de statut construise son lien GitHub sans dupliquer
        # GITHUB_REPO côté JS (une seule source de vérité).
        'repo': GITHUB_REPO,
    }


def _reference_path():
    """Fichier de persistance de la référence de mise à jour réseau —
    recalculé à chaque appel (jamais figé à l'import) : user_data_dir() peut
    être redirigé par les tests, et le sous-dossier 'update' est le même que
    celui des téléchargements du module."""
    return os.path.join(user_data_dir(), 'update', 'update_reference.json')


def _save_reference(result):
    """Persiste sur disque la référence {tag, asset_sha256, asset_size} issue
    d'un contact DIRECT réussi avec l'API GitHub — pour qu'elle survive à un
    redémarrage du processus (voir docstring du module : « même ancien » doit
    valoir y compris après un restart de LogXAI.exe, pas seulement dans le
    même run). Écriture atomique (tmp + os.replace) : jamais un fichier
    tronqué lisible par un prochain démarrage. Un résultat SANS digest
    exploitable n'écrase JAMAIS une bonne référence antérieure (un digest de
    release publiée est stable indéfiniment — mieux vaut une référence
    ancienne complète que rien). Ne lève jamais : un échec disque ne doit pas
    casser la vérification de version elle-même."""
    tag = str(result.get('tag') or '').strip()
    sha = str(result.get('asset_sha256') or '').strip()
    if not tag or not sha:
        return
    path = _reference_path()
    tmp = path + '.tmp'
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'tag': tag, 'asset_sha256': sha,
                       'asset_size': int(result.get('asset_size') or 0),
                       'saved_ts': time.time()}, f)
        os.replace(tmp, path)
    except Exception as e:
        print(f"[UPDATE] Persistance de la référence impossible : {e}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def _load_persisted_reference():
    """Relit la référence écrite par _save_reference lors d'une session
    ANTÉRIEURE. Renvoie {'tag', 'asset_sha256', 'asset_size'} ou None si
    absente/corrompue. Validation défensive du contenu (fichier sur disque,
    modifiable hors du programme) : le tag doit passer _TAG_RE — il finit
    dans l'URL de relais reconstruite (voir resolve_relay_asset côté
    passerelle, défense en profondeur ici aussi) — et l'empreinte doit être
    exactement 64 hex minuscules, comme _parse_digest l'exige d'un digest
    GitHub. Tout contenu douteux est traité comme ABSENT (refus sûr en aval),
    jamais comme une référence de confiance."""
    try:
        with open(_reference_path(), 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    tag = str(data.get('tag') or '').strip()
    sha = str(data.get('asset_sha256') or '').strip().lower()
    if not _TAG_RE.match(tag):
        return None
    if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        return None
    try:
        size = max(0, int(data.get('asset_size') or 0))
    except (TypeError, ValueError):
        size = 0
    return {'tag': tag, 'asset_sha256': sha, 'asset_size': size}


def _refresh(force=False):
    global _checking
    with _lock:
        if _checking:
            return
        if not force and _cache['result'] and (time.time() - _cache['ts']) < CHECK_TTL:
            return
        _checking = True
    result = None
    try:
        data = _fetch_latest_release()
        if data:
            result = _build_result(data)
    except Exception as e:
        print(f"[UPDATE] Vérification impossible : {e}")
    with _lock:
        if result:
            _cache['result'] = result
            _cache['ts'] = time.time()
        _checking = False
    if result:
        # Hors du verrou (I/O disque) et déjà dans un thread de fond, jamais
        # le thread HTTP : la référence survit désormais aux redémarrages.
        _save_reference(result)


def get_cached_check(force=False):
    """Ne bloque JAMAIS sur le réseau : renvoie le dernier résultat connu et
    déclenche un rafraîchissement en tâche de fond si le cache est absent ou
    périmé (le tout premier appel après démarrage renvoie donc 'checking',
    rattrapé par le client au prochain sondage)."""
    stale = force or not _cache['result'] or (time.time() - _cache['ts']) >= CHECK_TTL
    if stale and not _checking:
        threading.Thread(target=_refresh, args=(force,), daemon=True).start()
    if _cache['result']:
        return _cache['result']
    return {'available': False, 'current': APP_VERSION, 'latest': APP_VERSION,
            'tag': '', 'release_url': '', 'notes': '', 'asset_url': '',
            'asset_sha256': '', 'asset_size': 0, 'installable': False,
            'checking': True, 'repo': GITHUB_REPO}


def gateway_status():
    """Ce poste peut-il servir de PASSERELLE réseau (chemin B, priorité 1) à
    un autre poste sans internet ? Heuristique, pas un ping actif dédié : on
    réutilise le même signal que "une release est peut-être disponible",
    déjà rafraîchi périodiquement par chaque client (logx_statusbar.js,
    refreshUpdateCheck toutes les 30 min, lui-même borné par CHECK_TTL=6h
    côté cache) — càd "ce poste a réussi à joindre l'API GitHub Releases il
    y a moins de CHECK_TTL". Un poste peut se déclarer disponible et pourtant
    échouer au moment T (connexion redevenue mauvaise entretemps) : le
    relais lui-même (voir /app/update_relay) peut toujours échouer, ceci
    n'est qu'un indicateur pour orienter la recherche, pas une garantie."""
    with _lock:
        ok = bool(_cache['result']) and (time.time() - _cache['ts']) < CHECK_TTL
    return {'gateway_available': ok, 'repo': GITHUB_REPO, 'version': APP_VERSION}


def resolve_relay_asset(tag, platform):
    """Valide (tag, platform) fournis par un AUTRE poste du LAN et reconstruit
    l'URL GitHub OFFICIELLE de l'asset — ne fait JAMAIS confiance à une URL
    fournie par l'appelant (protection anti-SSRF : sans cette validation,
    /app/update_relay serait un proxy HTTP ouvert vers n'importe quelle URL).
    Le nom de fichier suit exactement le même schéma que _build_result.
    Renvoie (True, {'asset_url':..., 'asset_name':...}) ou (False, message)."""
    tag = (tag or '').strip()
    platform = (platform or '').strip()
    if not _TAG_RE.match(tag):
        return False, 'Tag de release invalide.'
    if platform not in _ASSET_SUFFIX_BY_PLATFORM:
        return False, 'Plateforme invalide.'
    if not gateway_status()['gateway_available']:
        return False, ("Ce poste n'a pas d'accès internet confirmé récemment "
                        "— indisponible comme passerelle pour l'instant.")
    suffix, ext = _ASSET_SUFFIX_BY_PLATFORM[platform]
    asset_name = f'LogXAI-{tag}{suffix}{ext}'
    asset_url = f'https://github.com/{GITHUB_REPO}/releases/download/{tag}/{asset_name}'
    return True, {'asset_url': asset_url, 'asset_name': asset_name}


def serve_status():
    """État du fichier VÉRIFIÉ actuellement disponible sur CE poste pour le
    servir à un pair en secours (chemin C) — toujours _download['path'],
    JAMAIS un chemin fourni par le client (aucune traversée de répertoire
    possible, ce n'est même pas un paramètre d'entrée ici)."""
    with _lock:
        d = dict(_download)
    path = d.get('path', '')
    ok = bool(d.get('status') == 'done' and d.get('verified') and path and os.path.exists(path))
    if not ok:
        return {'available': False, 'sha256': '', 'size': 0, 'version': ''}
    try:
        size = os.path.getsize(path)
    except OSError:
        return {'available': False, 'sha256': '', 'size': 0, 'version': ''}
    return {'available': True, 'sha256': d.get('sha256', ''), 'size': size,
            'version': d.get('version', '')}


def verify_file_sha256(path, expected_hex):
    """Relit `path` PAR BLOCS (jamais entièrement en mémoire, voir _CHUNK) et
    compare son empreinte SHA-256 à expected_hex. Utilisé pour re-vérifier un
    exécutable déjà sur disque (tests, contrôle défensif) — le téléchargement
    lui-même hache déjà en flux pendant l'écriture (_do_download /
    _do_download_via_network), ceci n'est pas sur le chemin chaud."""
    if not expected_hex:
        return False
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(_CHUNK)
                if not chunk:
                    break
                h.update(chunk)
    except OSError:
        return False
    return h.hexdigest() == expected_hex.lower()


def _is_valid_ip(ip):
    """True SEULEMENT si `ip` est un littéral IPv4/IPv6 valide — JAMAIS un
    nom d'hôte/domaine (anti-SSRF, voir audit sécurité : sans ce filtre,
    _peer_get_json/scan_network_candidates/_do_download_via_network
    construisaient f'http://{ip}:{PORT}{path}' à partir de N'IMPORTE QUELLE
    chaîne fournie par le client — un appelant pouvait ainsi forcer ce
    serveur à émettre de vraies requêtes HTTP sortantes vers un hôte/domaine
    arbitraire, par ex. 'localhost' ou un nom public pointant vers un
    service interne). ipaddress.ip_address() rejette tout ce qui n'est pas
    une adresse littérale — pas de résolution DNS ici, donc pas de fenêtre
    de "DNS rebinding" non plus."""
    try:
        ipaddress.ip_address(str(ip).strip())
        return True
    except (ValueError, TypeError):
        return False


# ─── EXCLUSION DE SOI-MÊME (jamais son propre candidat de mise à jour) ───────
# Défaut corrigé : la découverte réseau n'excluait JAMAIS le poste demandeur
# de ses propres candidats. peer_versions (logx_http.py) contient TOUJOURS
# '127.0.0.1' dès qu'un navigateur local est ouvert (le serveur invite à
# ouvrir http://127.0.0.1:PORT au démarrage — usage nominal), donc le scan
# sondait http://127.0.0.1:PORT/app/gateway_status = CE serveur lui-même,
# dont gateway_status() répond 'disponible' tant que le cache GitHub a moins
# de CHECK_TTL (6 h) — précisément le cas du poste qui VIENT de perdre
# internet, le scénario DXpédition visé par ce module. Trois conséquences :
# le poste se proposait LUI-MÊME comme passerelle (relayer GitHub via
# soi-même, sans internet → échec garanti), une vraie passerelle était
# masquée ('127.0.0.1' trie avant '192.168.x.x' et le client ne propose que
# gateways[0]), et le secours pair-à-pair (C) était refusé en s'auto-citant
# comme passerelle (B) disponible. D'où : la boucle locale et les adresses
# des interfaces de CE poste ne sont JAMAIS retenues comme candidats — ni
# ici (scan_network_candidates), ni côté logx_http (_known_peer_ips).

_SELF_IPS_TTL = 300  # les interfaces changent (DHCP, Wi-Fi) : re-relevé périodique
_self_ips_cache = {'ts': 0.0, 'ips': frozenset()}
_self_ips_lock = threading.Lock()


def _local_interface_ips():
    """Adresses IP des interfaces de CE poste (toutes cartes), en cache
    _SELF_IPS_TTL. Deux relevés complémentaires, purement locaux (jamais de
    requête DNS externe ni de paquet émis) : les adresses associées au nom
    d'hôte local (résolution locale par la pile IP), et l'IP source de la
    route sortante par défaut (connect() UDP n'émet AUCUN paquet — simple
    décision de routage locale). Ne lève jamais : au pire un ensemble vide,
    la boucle locale restant couverte par _is_self_ip() sans ce relevé."""
    now = time.time()
    with _self_ips_lock:
        if now - _self_ips_cache['ts'] < _SELF_IPS_TTL:
            return _self_ips_cache['ips']
    found = set()
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            infos = ex.submit(socket.getaddrinfo, socket.gethostname(), None).result(timeout=2)
        for info in infos:
            try:
                found.add(str(ipaddress.ip_address(str(info[4][0]))))
            except ValueError:
                pass  # ex. IPv6 avec zone '%...' non parsable : ignoré
    except (OSError, concurrent.futures.TimeoutError):
        pass  # résolveur muet/lent : le thread abandonné se termine seul en arrière-plan
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('192.0.2.1', 9))  # TEST-NET-1 (RFC 5737), jamais joint réellement
            found.add(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    ips = frozenset(found)
    with _self_ips_lock:
        _self_ips_cache.update(ts=now, ips=ips)
    return ips


def _is_self_ip(ip):
    """True si `ip` désigne CE poste lui-même : boucle locale (127.0.0.0/8,
    ::1, y compris la forme IPv6-mappée ::ffff:127.x.x.x), adresse non
    spécifiée (0.0.0.0/::), ou adresse d'une des interfaces locales (voir
    _local_interface_ips). Un poste ne doit JAMAIS être son propre candidat
    passerelle/pair — voir le bloc de commentaire ci-dessus. Renvoie False
    pour tout ce qui n'est pas un littéral IP (déjà exclu par _is_valid_ip
    en amont, jamais sondé de toute façon)."""
    try:
        addr = ipaddress.ip_address(str(ip).strip())
    except (ValueError, TypeError):
        return False
    mapped = getattr(addr, 'ipv4_mapped', None)
    if mapped is not None:
        addr = mapped
    if addr.is_loopback or addr.is_unspecified:
        return True
    return str(addr) in _local_interface_ips()


def _peer_get_json(ip, path, timeout=3):
    """GET JSON vers un AUTRE poste du LAN (même port que celui-ci, voir
    PORT) — utilisé pour sonder /app/gateway_status et /app/update_serve_
    status avant de tenter un vrai transfert. Ne lève jamais : renvoie None
    sur toute erreur (poste éteint, pas LogX AI à cette IP, timeout...).
    Anti-SSRF : refuse tout `ip` qui n'est pas un littéral IPv4/IPv6 (voir
    _is_valid_ip) AVANT de construire la moindre URL — défense en profondeur,
    même si les appelants (scan_network_candidates, _do_download_via_network)
    filtrent déjà en amont."""
    if not _is_valid_ip(ip):
        return None
    try:
        req = urllib.request.Request(
            f'http://{ip}:{PORT}{path}',
            headers={'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8', errors='replace'))
    except Exception:
        return None


def _local_reference():
    """Référence GitHub LOCALE de CE poste — (tag, sha256, size), issue d'un
    contact DIRECT antérieur avec l'API GitHub : cache mémoire d'abord
    (lecture directe de _cache, JAMAIS get_cached_check() ici — pas question
    de déclencher un rafraîchissement réseau depuis un scan LAN dont la
    raison d'être est précisément « ce poste n'a pas internet »), sinon la
    référence persistée d'une session antérieure (_load_persisted_reference,
    même logique de secours que start_download_via_network). Renvoie
    ('', '', 0) si ce poste n'a jamais réussi de contact direct."""
    with _lock:
        result = dict(_cache['result'] or {})
    tag = str(result.get('tag') or '').strip()
    sha = str(result.get('asset_sha256') or '').strip().lower()
    try:
        size = max(0, int(result.get('asset_size') or 0))
    except (TypeError, ValueError):
        size = 0
    if not tag or not sha:
        persisted = _load_persisted_reference()
        if persisted:
            return persisted['tag'], persisted['asset_sha256'], persisted['asset_size']
        return '', '', 0
    return tag, sha, size


def _peer_asset_mismatch(status, ref_sha, ref_size):
    """Compare ce qu'un pair ANNONCE servir (serve_status() : sha256/size/
    version) à la référence GitHub LOCALE de ce poste — AVANT le moindre GET
    de l'exécutable. Renvoie '' si rien ne PROUVE que le pair sert un autre
    asset, sinon un message explicite (jamais « corrompu/altéré » : ce n'est
    pas une altération, juste le mauvais asset — autre plateforme ou autre
    version). Défaut corrigé : le pair sert TOUJOURS son propre fichier
    (_download['path'], l'asset de SA plateforme dans SA version) sans aucune
    négociation possible via /app/update_serve — sans ce pré-filtrage, un
    receveur macOS/Linux avec un pair Windows (ou un pair resté sur une
    version antérieure) téléchargeait l'exécutable EN ENTIER (dizaines de Mo
    sur le lien dégradé du scénario DXpédition visé par ce module) avant un
    rejet CERTAIN, avec un message évoquant une altération. La comparaison
    est GRATUITE : serve_status() expose déjà ces champs, aucun octet de
    l'exécutable n'a besoin de transiter pour conclure. Un champ absent côté
    pair (réponse partielle/hostile) n'est PAS une preuve de mismatch : on
    laisse alors le transfert se faire — le contenu reçu reste de toute façon
    haché et vérifié contre la même référence locale après transfert
    (_do_download_via_network), ce pré-filtrage est une économie de bande
    passante + un message honnête, jamais LA barrière d'intégrité."""
    status = status or {}
    peer_sha = str(status.get('sha256') or '').strip().lower()
    ref_sha = str(ref_sha or '').strip().lower()
    if peer_sha and ref_sha and peer_sha != ref_sha:
        peer_version = str(status.get('version') or '').strip()
        detail = f" (version annoncée : {peer_version})" if peer_version else ''
        return ("le pair sert un autre exécutable que celui attendu par ce "
                f"poste — autre plateforme ou autre version{detail}, ignoré "
                "sans téléchargement.")
    try:
        peer_size = max(0, int(status.get('size') or 0))
    except (TypeError, ValueError):
        peer_size = 0
    try:
        ref_size = max(0, int(ref_size or 0))
    except (TypeError, ValueError):
        ref_size = 0
    if peer_size and ref_size and peer_size != ref_size:
        return (f"le pair annonce une taille ({peer_size} o) différente de la "
                f"référence GitHub locale ({ref_size} o) — autre plateforme ou "
                "autre version, ignoré sans téléchargement.")
    return ''


def scan_network_candidates(ips):
    """Sonde chaque IP candidate (postes vus via /log/status → peer_list, cf.
    logx_http.peer_versions) pour savoir qui peut servir de PASSERELLE
    (chemin B, prioritaire) et, à défaut, qui a déjà un exécutable vérifié à
    servir en SECOURS (chemin C). Un pair n'est retenu que s'il annonce LE
    BON asset (voir _peer_asset_mismatch : sha256/size de serve_status()
    comparés à la référence GitHub locale) — sans ce filtre, un pair d'une
    autre plateforme ou d'une autre version était proposé « pair vérifié »
    à l'IHM (logx_logbook.js) alors que son téléchargement ne pouvait JAMAIS
    réussir (rejet certain après transfert complet). Purement informatif — ne télécharge rien ;
    c'est start_download_via_network qui agit, sur un second clic explicite
    de l'opérateur (voir logx_logbook.js). Sondes en parallèle (borné) pour
    rester réactif même avec une dizaine de postes sur le LAN.
    Anti-SSRF : `ips` peut, à cet appel, provenir indirectement d'un corps
    JSON client (voir logx_http./app/update_network_scan, qui doit lui-même
    déjà restreindre aux pairs CONNUS de ce serveur — peer_versions, jamais
    une IP choisie librement par l'appelant) ; ici, en secours, on rejette
    aussi tout ce qui n'est pas un littéral IP valide (_is_valid_ip) — un nom
    d'hôte comme 'localhost' ou un domaine arbitraire n'est JAMAIS sondé.
    Exclusion de soi-même (_is_self_ip, voir bloc de commentaire dédié) : le
    poste demandeur ne se sonde JAMAIS lui-même — sinon il se découvrait
    comme sa propre passerelle (127.0.0.1, toujours présent dans
    peer_versions dès qu'un navigateur local est ouvert) et masquait/bloquait
    les vrais candidats du LAN."""
    import concurrent.futures
    # dédoublonne, valide, exclut soi-même, borne
    ips = [ip for ip in dict.fromkeys(ips)
           if ip and _is_valid_ip(ip) and not _is_self_ip(ip)][:20]
    gateways, peers = [], []
    if not ips:
        return {'gateways': gateways, 'peers': peers}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(ips))) as ex:
        gw_results = dict(zip(ips, ex.map(lambda ip: _peer_get_json(ip, '/app/gateway_status', 2), ips)))
    gateways = [ip for ip in ips if gw_results.get(ip) and gw_results[ip].get('gateway_available')]
    remaining = [ip for ip in ips if ip not in gateways]
    if remaining:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(remaining))) as ex:
            sv_results = dict(zip(remaining, ex.map(lambda ip: _peer_get_json(ip, '/app/update_serve_status', 2), remaining)))
        # Même pré-filtrage que le téléchargement lui-même (_peer_asset_
        # mismatch) : un pair qui annonce un AUTRE asset que la référence
        # locale n'est jamais proposé comme « pair vérifié ». Sans référence
        # locale (jamais de contact direct GitHub), pas de comparaison
        # possible : comportement inchangé — le refus explicite « jamais
        # contacté » de start_download_via_network prend le relais.
        _tag, ref_sha, ref_size = _local_reference()
        peers = [ip for ip in remaining
                 if sv_results.get(ip) and sv_results[ip].get('available')
                 and not _peer_asset_mismatch(sv_results[ip], ref_sha, ref_size)]
    return {'gateways': gateways, 'peers': peers}


# ─── TÉLÉCHARGEMENT DIRECT (GitHub) ───────────────────────────────────────────

def start_download(asset_url, expected_sha256='', expected_size=0):
    """Démarre le téléchargement en tâche de fond (jamais dans le thread
    HTTP — un exécutable fait plusieurs dizaines de Mo). Idempotent : un
    téléchargement déjà en cours n'en relance pas un second.
    expected_sha256/expected_size : référence attendue (voir _build_result,
    champ 'digest' de l'API GitHub) — voir _do_download pour la vérification
    et le refus si absente."""
    # Pose du statut + démarrage du thread d'un seul bloc sous _lock, avec
    # auto-guérison de l'orphelin — voir _demarrer_telechargement.
    _demarrer_telechargement(_do_download,
                             (asset_url, expected_sha256, expected_size),
                             via='direct')


def _do_download(asset_url, expected_sha256='', expected_size=0):
    dest_dir = os.path.join(user_data_dir(), 'update')
    tmp = None
    try:
        if not expected_sha256:
            # Aucune vérification fiable possible pour cette source (l'API
            # GitHub n'a pas exposé de digest pour cet asset) : on REFUSE
            # plutôt que d'accepter un binaire non vérifié en silence — voir
            # docstring du module (compromis de sécurité documenté).
            raise ValueError(
                "Aucune empreinte SHA-256 de référence disponible pour cet "
                "exécutable (l'API GitHub n'expose pas de digest fiable pour "
                "cet asset) — téléchargement refusé par sécurité.")
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, os.path.basename(asset_url) or 'LogXAI_new.exe')
        tmp = dest + '.part'
        req = urllib.request.Request(asset_url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)'})
        hasher = hashlib.sha256()
        with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as resp:
            total = int(resp.headers.get('Content-Length', 0) or 0)
            got = 0
            with open(tmp, 'wb') as f:
                while True:
                    chunk = resp.read(_CHUNK)
                    if not chunk:
                        break
                    f.write(chunk)
                    hasher.update(chunk)
                    got += len(chunk)
                    pct = int(got * 100 / total) if total else 0
                    with _lock:
                        _download['pct'] = pct
        digest = hasher.hexdigest()
        if expected_size and got != expected_size:
            raise ValueError(
                f"Taille reçue ({got} o) différente de celle annoncée par "
                f"GitHub ({expected_size} o) — fichier corrompu ou tronqué, rejeté.")
        if digest != expected_sha256:
            raise ValueError(
                "Empreinte SHA-256 du fichier reçu différente de celle "
                "publiée par GitHub — fichier potentiellement altéré, rejeté.")
        os.replace(tmp, dest)
        with _lock:
            _download.update(status='done', pct=100, path=dest, verified=True, sha256=digest)
    except Exception as e:
        try:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        with _lock:
            _download.update(status='error', error=str(e), verified=False)


def get_download_status():
    with _lock:
        return dict(_download)


# ─── TÉLÉCHARGEMENT VIA LE RÉSEAU LOCAL (B : passerelle, C : pair-à-pair) ────
# Déclenché UNIQUEMENT par une action utilisateur explicite côté client (voir
# logx_logbook.js) — jamais sondé/lancé automatiquement en tâche de fond.

def start_download_via_network(mode, ips, known_lan_ips=None):
    """mode: 'gateway' (chemin B, priorité 1) ou 'peer' (chemin C, secours,
    seulement si B est indisponible). ips : postes candidats (déjà connus
    du client via /log/status → peer_list). Essaie chaque IP dans l'ordre
    jusqu'à la première qui répond ET dont le hash vérifie contre la
    référence LOCALE de ce poste (jamais une référence fournie par le pair/
    la passerelle — voir docstring du module). Renvoie (True, '') si le
    téléchargement démarre, (False, message) sinon (refus immédiat, sans
    lancer de thread ni ouvrir la moindre connexion réseau).
    Priorité B>C RESTREINTE CÔTÉ SERVEUR, pas seulement côté client : pour
    mode='peer', _do_download_via_network sonde elle-même — dans le thread
    de fond, jamais dans ce thread HTTP — l'UNION de `ips` et de
    `known_lan_ips` (postes que CE serveur a lui-même vus passer sur le LAN,
    voir peer_versions dans logx_http.py, jamais une donnée fournie par
    l'appelant) et REFUSE le secours si l'un d'eux répond disponible comme
    passerelle. Un appel HTTP direct à mode='peer' qui contournerait l'IHM
    cliente (voir logx_logbook.js) ne peut donc plus obtenir le secours tant
    qu'une passerelle connue de ce serveur est disponible.
    Anti-SSRF : `ips` peut provenir indirectement d'un corps JSON client (voir
    logx_http./app/update_download_via_network, qui doit lui-même déjà
    restreindre aux pairs CONNUS de ce serveur — peer_versions). Ici, en
    secours, tout ce qui n'est pas un littéral IPv4/IPv6 valide (_is_valid_ip)
    est rejeté avant même d'être retenu comme candidat : jamais un nom
    d'hôte/domaine arbitraire, jamais de résolution DNS pour ce chemin."""
    if mode not in ('gateway', 'peer'):
        return False, 'Mode de mise à jour réseau invalide.'
    check = get_cached_check()
    ref_sha = check.get('asset_sha256') or ''
    ref_tag = check.get('tag') or ''
    ref_size = int(check.get('asset_size') or 0)
    if not ref_sha or not ref_tag:
        # Cache mémoire vide — cas d'un processus fraîchement (re)démarré,
        # routinier en DXpédition (coupure secteur, déplacement du poste) :
        # la référence a pu être obtenue lors d'une session ANTÉRIEURE et
        # persistée par _save_reference. La recharger ici honore le compromis
        # documenté (« même ancien : l'empreinte d'une release publiée ne
        # change jamais ») — sans ça, un simple restart ramenait tous les
        # postes sans internet au refus « jamais contacté ». Ça reste bien
        # SA PROPRE référence (contact direct GitHub antérieur de CE poste),
        # jamais une donnée fournie par la passerelle ou le pair.
        persisted = _load_persisted_reference()
        if persisted:
            ref_sha = persisted['asset_sha256']
            ref_tag = persisted['tag']
            ref_size = persisted['asset_size']
    if not ref_sha or not ref_tag:
        return False, (
            "Ce poste n'a jamais réussi à vérifier une version directement "
            "auprès de GitHub — aucune empreinte de référence fiable en local. "
            "La mise à jour réseau (passerelle ou pair) est refusée par "
            "sécurité tant qu'un contact direct n'a pas réussi au moins une "
            "fois (même ancien : l'empreinte d'une release publiée ne change "
            "jamais).")
    ips = [str(ip).strip() for ip in (ips or []) if str(ip).strip() and _is_valid_ip(ip)]
    if not ips:
        return False, 'Aucun poste candidat sur le réseau local.'
    # ref_size est calculé en tête (cache mémoire, sinon référence persistée
    # d'une session antérieure) — jamais réécrasé ici depuis `check`, qui est
    # vide après un redémarrage.
    platform = _platform_key()
    known_lan_ips = [str(ip).strip() for ip in (known_lan_ips or []) if str(ip).strip()]
    # Pose du statut + démarrage du thread d'un seul bloc sous _lock, avec
    # auto-guérison de l'orphelin — voir _demarrer_telechargement.
    return _demarrer_telechargement(
        _do_download_via_network,
        (mode, ips, ref_tag, platform, ref_sha, ref_size, known_lan_ips),
        via=mode)


def _do_download_via_network(mode, ips, tag, platform, expected_sha256, expected_size,
                              known_lan_ips=None):
    """Enveloppe de _do_download_via_network_corps : QUOI QU'IL ARRIVE, un état
    terminal est posé.

    DÉFAUT RÉEL QUE CE FILET CORRIGE. Les premières lignes du corps —
    user_data_dir(), os.makedirs, _ASSET_SUFFIX_BY_PLATFORM[platform] — et le
    scan pair-à-pair (scan_network_candidates, qui utilise un ThreadPoolExecutor
    et peut lever « can't start new thread » sous famine) vivaient HORS de tout
    try, alors que le chemin direct (_do_download) est protégé de bout en bout.
    Une exception y tuait le thread SANS état terminal : status restait
    'downloading' pour toujours, et start_download_via_network refusait tout
    nouvel essai — la mise à jour était morte jusqu'au redémarrage, sans un
    message. C'est aussi ce thread traînard qui écrivait 'error' dans l'état
    tout neuf du test suivant (le flake de test_update_integrity).
    """
    try:
        _do_download_via_network_corps(mode, ips, tag, platform,
                                       expected_sha256, expected_size,
                                       known_lan_ips)
    except Exception as e:
        with _lock:
            _download.update(status='error', verified=False,
                             error=f'Téléchargement réseau interrompu : {e}')


def _do_download_via_network_corps(mode, ips, tag, platform, expected_sha256,
                                   expected_size, known_lan_ips=None):
    dest_dir = os.path.join(user_data_dir(), 'update')
    os.makedirs(dest_dir, exist_ok=True)
    suffix, ext = _ASSET_SUFFIX_BY_PLATFORM[platform]
    dest = os.path.join(dest_dir, f'LogXAI-{tag}{suffix}{ext}')
    last_err = 'Aucun poste candidat joignable ou valide sur le réseau.'
    if mode == 'peer':
        # Priorité B>C RESTREINTE ICI, côté serveur — pas seulement une
        # convention respectée par le client (voir logx_logbook.js). Sonde
        # (réseau, donc dans CE thread de fond, jamais dans le thread HTTP —
        # voir logx_update.py docstring module) l'UNION des candidats fournis
        # par l'appelant ET de ceux que ce serveur a lui-même vus passer sur
        # le LAN (known_lan_ips, voir peer_versions dans logx_http.py) : un
        # appelant qui omettrait délibérément l'IP d'une passerelle de son
        # `ips` (pour forcer le secours via un appel HTTP direct) ne peut
        # donc pas empêcher cette détection, qui repose sur la connaissance
        # PROPRE de ce serveur, jamais sur ce que le client déclare.
        candidates = list(dict.fromkeys(list(ips) + list(known_lan_ips or [])))
        scan = scan_network_candidates(candidates)
        if scan['gateways']:
            with _lock:
                _download.update(status='error', verified=False, error=(
                    f"Passerelle disponible sur le réseau local ({scan['gateways'][0]}) — "
                    "le secours pair-à-pair (C) est refusé tant qu'une passerelle (B) "
                    "répond, même si elle n'était pas dans la liste de candidats fournie."))
            return
    for ip in ips:
        tmp = dest + '.part'
        # Anti-SSRF (défense en profondeur — start_download_via_network filtre
        # déjà `ips` en amont, mais cette fonction reste appelable directement,
        # ex. depuis un test) : jamais de requête sortante vers autre chose
        # qu'un littéral IPv4/IPv6 (voir _is_valid_ip). Un nom d'hôte comme
        # 'localhost' ou un domaine arbitraire est rejeté ICI, avant toute
        # tentative de connexion.
        if not _is_valid_ip(ip):
            last_err = f'{ip} : IP invalide.'
            continue
        try:
            if mode == 'gateway':
                status = _peer_get_json(ip, '/app/gateway_status', timeout=3)
                # Même distinction que côté pair, plus bas : injoignable et
                # « pas passerelle » ne se dépannent pas au même endroit.
                if status is None:
                    last_err = (f'{ip} : injoignable (poste éteint, occupé, ou '
                                f'délai de sonde de 3 s dépassé).')
                    continue
                if not status.get('gateway_available'):
                    last_err = f'{ip} : pas disponible comme passerelle.'
                    continue
                url = (f'http://{ip}:{PORT}/app/update_relay'
                       f'?tag={urllib.parse.quote(tag)}&platform={urllib.parse.quote(platform)}')
            else:  # 'peer' — secours
                status = _peer_get_json(ip, '/app/update_serve_status', timeout=3)
                # DEUX CAUSES DISTINCTES, DEUX MESSAGES. _peer_get_json rend
                # None sur TOUTE erreur (poste éteint, délai de sonde 3 s
                # dépassé sur un poste chargé...) : l'ancien message unique
                # « aucun exécutable vérifié à servir » accusait le pair de ne
                # rien avoir alors qu'il n'avait simplement pas répondu à
                # temps — en multi-op, l'opérateur cherchait le problème sur
                # le mauvais poste.
                if status is None:
                    last_err = (f'{ip} : injoignable (poste éteint, occupé, ou '
                                f'délai de sonde de 3 s dépassé).')
                    continue
                if not status.get('available'):
                    last_err = f'{ip} : aucun exécutable vérifié à servir.'
                    continue
                # Pré-filtrage AVANT le GET (voir _peer_asset_mismatch) : le
                # pair sert toujours l'asset de SA plateforme dans SA version,
                # sans négociation — s'il annonce (sha256/size) un autre asset
                # que la référence locale, on l'IGNORE ici, sans transférer un
                # seul octet de l'exécutable, avec un message qui dit le vrai
                # problème (mauvais asset) au lieu d'évoquer une altération.
                mismatch = _peer_asset_mismatch(status, expected_sha256, expected_size)
                if mismatch:
                    last_err = f'{ip} : {mismatch}'
                    continue
                url = f'http://{ip}:{PORT}/app/update_serve'

            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)'})
            hasher = hashlib.sha256()
            # Trafic LAN en clair (comme tout le reste de l'application, qui
            # n'utilise jamais TLS en interne — voir compromis documenté dans
            # le commit) : PAS de context=SSL_CTX ici, ce n'est pas du HTTPS.
            with urllib.request.urlopen(req, timeout=20) as resp:
                total = int(resp.headers.get('Content-Length', 0) or 0)
                got = 0
                with open(tmp, 'wb') as f:
                    while True:
                        chunk = resp.read(_CHUNK)
                        if not chunk:
                            break
                        f.write(chunk)
                        hasher.update(chunk)
                        got += len(chunk)
                        pct = int(got * 100 / total) if total else 0
                        with _lock:
                            _download['pct'] = pct
            digest = hasher.hexdigest()
            if expected_size and got != expected_size:
                raise ValueError(f"taille reçue ({got} o) ≠ référence GitHub ({expected_size} o)")
            if digest != expected_sha256:
                raise ValueError("empreinte SHA-256 ne correspond pas à la référence GitHub — rejeté")
            os.replace(tmp, dest)
            with _lock:
                _download.update(status='done', pct=100, path=dest, verified=True,
                                  sha256=digest, version=tag, via=mode, via_peer=ip)
            return
        except Exception as e:
            last_err = f'{ip} : {e}'
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            continue
    with _lock:
        _download.update(status='error', error=last_err, verified=False)


# ─── INSTALLATION (remplacement de l'exécutable + relance) ──────────────────

def dev_mode_relaunch():
    """Mode développement (python logx_serveur.py, pas l'exécutable PyInstaller
    figé) : il n'y a pas d'exécutable à remplacer — le code source est déjà à
    jour sur disque (édité/tiré directement). « Installer et redémarrer » se
    réduit donc à relancer CE MÊME process Python, pour recharger les modules
    (APP_VERSION notamment : une constante figée en mémoire au tout premier
    import, jamais relue depuis logx_version.py tant que le process vit).

    os.execv() REMPLACE l'image du process en place (même PID) plutôt que
    d'en lancer un second : les sockets Python ont CLOEXEC par défaut depuis
    la 3.4 (PEP 446), donc le socket d'écoute se ferme automatiquement
    pendant l'exec — le port se libère proprement AVANT que le script
    relancé ne tente son propre bind(), sans fenêtre de conflit ni script
    auxiliaire détaché (contrairement au cas figé ci-dessous)."""
    os.execv(sys.executable, [sys.executable] + sys.argv)


def apply_update_and_relaunch(new_exe_path):
    """Lance un script auxiliaire détaché qui attend la fin du processus
    courant, remplace l'exécutable, puis le relance — puis retourne
    immédiatement (l'appelant doit arrêter le serveur juste après, sinon le
    script auxiliaire attendra indéfiniment que ce processus se termine).
    Fonctionne à l'identique quelle que soit la provenance du fichier déjà
    vérifié (téléchargement direct, passerelle réseau ou pair-à-pair) — la
    vérification d'intégrité a déjà eu lieu en amont dans _do_download /
    _do_download_via_network, jamais ici.

    Mode développement (not is_frozen()) : rien à faire ICI — pas de fichier
    à déplacer ni de script auxiliaire à générer, le code source est déjà à
    jour sur disque. Réussit sans effet de bord ; c'est l'APPELANT
    (/app/update_install dans logx_http.py) qui, après ce retour réussi,
    déclenche le vrai redémarrage via dev_mode_relaunch() — jamais ici,
    pour ne jamais contourner ses propres vérifications (status/verified)
    en amont ni risquer un os.execv() prématuré si cette fonction est un
    jour appelée depuis un autre contexte (tests, script d'admin...)."""
    if not is_frozen():
        return True, ''
    if not os.path.exists(new_exe_path):
        return False, "Fichier téléchargé introuvable"

    # Défense en profondeur contre le TOCTOU : le fichier vérifié peut rester
    # posé un temps non borné dans user_data_dir()/update/ (dossier
    # inscriptible par tout process du même compte) avant que l'opérateur ne
    # clique "installer". On exige qu'il s'agisse EXACTEMENT du fichier que
    # _do_download / _do_download_via_network ont marqué verified=True, et on
    # re-hache juste avant de générer le script de remplacement pour détecter
    # toute altération survenue depuis la vérification initiale.
    #
    # TOCTOU RÉSIDUEL (celui-ci ne suffit PAS à le fermer) : le script
    # détaché généré plus bas attend 2 s puis retente jusqu'à 30 fois à 1 s
    # d'intervalle avant de déplacer le fichier vers l'exécutable courant et
    # de le lancer. Entre le re-hachage Python ci-dessus et l'exécution
    # réelle du move, il reste donc jusqu'à ~32 s pendant lesquelles un autre
    # process du même compte peut substituer le fichier à ce chemin
    # prévisible — le re-hachage Python, fait une seule fois AVANT de générer
    # le script, ne protège pas contre ça. D'où la seconde vérification,
    # DANS le script détaché lui-même, refaite à CHAQUE itération de sa
    # boucle de retente (pas seulement avant) : certutil/SHA256 côté Windows,
    # sha256sum/shasum côté POSIX — voir plus bas.
    with _lock:
        expected_path = _download.get('path', '')
        expected_sha = _download.get('sha256', '')
        was_verified = bool(_download.get('verified'))
    # normcase() en plus d'abspath() : sur Windows le système de fichiers est
    # insensible à la casse (C:\... vs c:\...) et NTFS normalise les
    # séparateurs — une comparaison abspath() seule pourrait rejeter à tort
    # un chemin strictement identique mais formaté différemment par
    # l'appelant (get_download_status() renvoie normalement la même chaîne,
    # mais ne pas en dépendre implicitement ici).
    same_path = (expected_path and
                 os.path.normcase(os.path.abspath(new_exe_path)) ==
                 os.path.normcase(os.path.abspath(expected_path)))
    if not (was_verified and expected_sha and same_path):
        return False, ("Fichier non reconnu comme provenant d'un téléchargement "
                        "vérifié — installation refusée par sécurité.")
    if not verify_file_sha256(new_exe_path, expected_sha):
        return False, ("L'exécutable téléchargé a été modifié depuis sa "
                        "vérification — installation refusée par sécurité.")

    current_exe = sys.executable
    update_dir = os.path.join(user_data_dir(), 'update')
    os.makedirs(update_dir, exist_ok=True)

    if sys.platform.startswith('win'):
        helper = os.path.join(update_dir, '_apply_update.bat')
        # PIÈGE d'encodage (bug réel corrigé ici) : cmd.exe n'interprète
        # JAMAIS un .bat en UTF-8. Écrit en UTF-8 avec les chemins EN DUR,
        # tout chemin accentué (« C:\\Users\\Frédéric\\Téléchargements » —
        # cas ultra-courant pour le public francophone visé : new_exe_path
        # est sous %APPDATA%, current_exe là où l'utilisateur a posé
        # LogXAI.exe) était relu mojibaké ('é' UTF-8 0xC3 0xA9 -> 2
        # caractères), le move /Y échouait 30 fois en silence, `start` n'était
        # jamais atteint : l'application se fermait (os._exit dans le caller)
        # et ne redémarrait JAMAIS — sans même le marqueur .update_failed.txt
        # de :giveup, écrit lui aussi vers le chemin mangé. Pire : la page de
        # lecture de cmd n'est même pas prévisible — OEM (cp850) avec une
        # console, mais ANSI (cp1252) quand cmd est lancé en DETACHED_PROCESS
        # sans console comme ici, et `chcp 65001` est INOPÉRANT sans console
        # (les trois mesurés sur ce poste, voir le test de non-régression).
        # La seule écriture fiable est donc un .bat 100 % ASCII (identique
        # dans TOUTES les pages de code) : plus aucun chemin dans le fichier,
        # ils sont transmis par variables d'environnement (UTF-16 de bout en
        # bout via CreateProcessW, expansion %VAR% en mémoire par cmd — aucun
        # aller-retour par un encodage de fichier, tout Unicode accepté).
        # encoding='ascii' STRICT : si un caractère non-ASCII se glisse un
        # jour dans ce script, échec bruyant à l'écriture plutôt qu'une mise
        # à jour silencieusement morte.
        #
        # Fermeture du TOCTOU résiduel (voir commentaire plus haut) : le hash
        # attendu transite lui aussi UNIQUEMENT par variable d'environnement
        # (LOGX_UPDATE_SHA256, même mécanisme que LOGX_UPDATE_NEW/CURRENT) —
        # jamais interpolé en dur dans le texte du script. certutil est
        # présent nativement sur tout Windows 10/11 ; sa sortie est
        # redirigée vers un fichier temporaire puis cherchée avec findstr
        # /i /c:"..." (recherche de sous-chaîne insensible à la casse : pas
        # besoin de parser finement les lignes d'en-tête/pied de certutil,
        # le hash hex est sur sa propre ligne sans espace). Le contrôle est
        # placé DANS la boucle :retry, donc refait à chaque itération — pas
        # seulement avant elle — pour rattraper une substitution survenue
        # entre deux tentatives. Si le hash ne correspond plus (fichier
        # absent, tronqué, ou substitué), on saute directement à :giveup :
        # même message d'échec que l'épuisement des 30 tentatives, et
        # surtout ni move ni start.
        #
        # DEUX pièges réels (mesurés sur ce poste, exécution RÉELLE de bout
        # en bout — voir tests) qui n'apparaissent qu'en dehors d'un mock :
        #   1) certutil.exe n'écrit RIEN sur sa sortie redirigée quand le
        #      process n'a AUCUNE console (le cas exact de cmd lancé en
        #      DETACHED_PROCESS ci-dessous) — le fichier temporaire reste
        #      vide et le hash "ne correspond jamais". Contournement :
        #      `start "" /min /wait cmd /c "..."` alloue une console propre
        #      (minimisée, jamais mise au premier plan) au SEUL sous-appel
        #      certutil, sans changer les creationflags du cmd détaché
        #      englobant.
        #   2) certutil.exe ET findstr.exe (contrairement à move/del/start,
        #      des commandes INTERNES à cmd, donc pleinement Unicode) sont
        #      des .exe externes dont le décodage de LEURS PROPRES arguments
        #      de ligne de commande passe par la page de code OEM active :
        #      un chemin contenant un caractère hors de cp850/cp1252 (« Δ₿ »
        #      — le cas de non-régression hors_pages_de_code) y devient
        #      littéralement « ?? », et findstr échoue à OUVRIR le fichier
        #      ("Impossible d'ouvrir ...") — pas un problème de contenu,
        #      malgré tout le soin apporté à transmettre le chemin par
        #      variable d'environnement. Contournement : résoudre le nom
        #      court 8.3 (%%~sA, garanti pur ASCII quel que soit le nom
        #      long) AVANT la boucle et ne plus jamais donner à certutil/
        #      findstr que ce nom court — le hash recalculé sur le nom court
        #      porte sur les mêmes octets que le fichier réel (c'est un
        #      alias NTFS du même fichier, pas une copie).
        script = '''@echo off
set count=0
timeout /t 2 /nobreak >NUL
for %%A in ("%LOGX_UPDATE_NEW%") do set LOGX_HASHCHK=%%~sA
:retry
if "%LOGX_UPDATE_SHA256%"=="" goto giveup
if "%LOGX_HASHCHK%"=="" goto giveup
start "" /min /wait cmd /c "certutil -hashfile ""%LOGX_HASHCHK%"" SHA256 > ""%LOGX_HASHCHK%.sha256check.tmp"" 2>NUL"
findstr /i /c:"%LOGX_UPDATE_SHA256%" "%LOGX_HASHCHK%.sha256check.tmp" >NUL
if errorlevel 1 goto giveup
move /Y "%LOGX_UPDATE_NEW%" "%LOGX_UPDATE_CURRENT%" >NUL 2>&1
if not errorlevel 1 goto launch
set /a count+=1
if %count% GEQ 30 goto giveup
timeout /t 1 /nobreak >NUL
goto retry
:launch
del "%LOGX_HASHCHK%.sha256check.tmp" >NUL 2>&1
start "" "%LOGX_UPDATE_CURRENT%"
del "%~f0"
goto :eof
:giveup
del "%LOGX_HASHCHK%.sha256check.tmp" >NUL 2>&1
echo Echec du remplacement - fermez LogXAI.exe puis relancez-le manuellement. > "%LOGX_UPDATE_CURRENT%.update_failed.txt"
'''
        with open(helper, 'w', encoding='ascii') as f:
            f.write(script)
        env = os.environ.copy()
        env['LOGX_UPDATE_NEW'] = new_exe_path
        env['LOGX_UPDATE_CURRENT'] = current_exe
        env['LOGX_UPDATE_SHA256'] = expected_sha
        subprocess.Popen(
            ['cmd', '/c', helper],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
            env=env,
        )
    else:
        helper = os.path.join(update_dir, '_apply_update.sh')
        # shlex.quote() (et non de simples guillemets doubles) : le texte du
        # script est interpolé, et les guillemets doubles POSIX n'empêchent
        # PAS l'expansion de variables ($VAR) ni la substitution de commande
        # ($(...) / `...`) — un chemin forgé pourrait sinon exécuter du code
        # arbitraire dans /bin/sh. Même protection de fond que côté Windows
        # (variables d'environnement), adaptée au shell POSIX.
        #
        # Fermeture du TOCTOU résiduel (voir commentaire plus haut, même
        # motif que côté .bat) : le hash attendu est lui aussi interpolé via
        # shlex.quote() — jamais en dur — exactement comme new_exe_q/
        # current_exe_q. sha256sum (Linux) est préféré, shasum -a 256
        # (macOS) en repli — la disponibilité est testée avec `command -v`,
        # jamais supposée. Seul le premier champ de la sortie (le hash,
        # avant l'espace séparateur du nom de fichier) est comparé, via
        # `cut -d ' ' -f1`. Le contrôle est refait à CHAQUE itération de la
        # boucle — pas seulement avant elle — pour rattraper une
        # substitution survenue entre deux tentatives ; en cas de
        # non-correspondance, sortie immédiate SANS mv ni relance, avec le
        # même message d'échec que l'épuisement des 30 tentatives.
        new_exe_q = shlex.quote(new_exe_path)
        current_exe_q = shlex.quote(current_exe)
        expected_sha_q = shlex.quote(expected_sha)
        script = f'''#!/bin/sh
sleep 2
if command -v sha256sum >/dev/null 2>&1; then
  HASHCMD="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
  HASHCMD="shasum -a 256"
else
  HASHCMD=""
fi
i=0
while :; do
  if [ -n "$HASHCMD" ]; then
    actual=$($HASHCMD {new_exe_q} 2>/dev/null | cut -d ' ' -f1)
  else
    actual=""
  fi
  if [ "$actual" != {expected_sha_q} ]; then
    echo "Echec du remplacement - fermez LogXAI puis relancez-le manuellement." > {current_exe_q}.update_failed.txt
    exit 1
  fi
  if mv -f {new_exe_q} {current_exe_q} 2>/dev/null; then
    break
  fi
  i=$((i+1))
  if [ "$i" -ge 30 ]; then
    echo "Echec du remplacement - fermez LogXAI puis relancez-le manuellement." > {current_exe_q}.update_failed.txt
    exit 1
  fi
  sleep 1
done
chmod +x {current_exe_q}
nohup {current_exe_q} >/dev/null 2>&1 &
rm -f "$0"
'''
        with open(helper, 'w', encoding='utf-8') as f:
            f.write(script)
        os.chmod(helper, os.stat(helper).st_mode | stat.S_IEXEC)
        subprocess.Popen(['/bin/sh', helper], start_new_session=True, close_fds=True)

    return True, ''
