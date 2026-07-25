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
        for info in socket.getaddrinfo(socket.gethostname(), None):
            try:
                found.add(str(ipaddress.ip_address(str(info[4][0]))))
            except ValueError:
                pass  # ex. IPv6 avec zone '%...' non parsable : ignoré
    except OSError:
        pass
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


def scan_network_candidates(ips):
    """Sonde chaque IP candidate (postes vus via /log/status → peer_list, cf.
    logx_http.peer_versions) pour savoir qui peut servir de PASSERELLE
    (chemin B, prioritaire) et, à défaut, qui a déjà un exécutable vérifié à
    servir en SECOURS (chemin C). Purement informatif — ne télécharge rien ;
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
        peers = [ip for ip in remaining if sv_results.get(ip) and sv_results[ip].get('available')]
    return {'gateways': gateways, 'peers': peers}


# ─── TÉLÉCHARGEMENT DIRECT (GitHub) ───────────────────────────────────────────

def start_download(asset_url, expected_sha256='', expected_size=0):
    """Démarre le téléchargement en tâche de fond (jamais dans le thread
    HTTP — un exécutable fait plusieurs dizaines de Mo). Idempotent : un
    téléchargement déjà en cours n'en relance pas un second.
    expected_sha256/expected_size : référence attendue (voir _build_result,
    champ 'digest' de l'API GitHub) — voir _do_download pour la vérification
    et le refus si absente."""
    with _lock:
        if _download['status'] == 'downloading':
            return
        _download.update(status='downloading', pct=0, error='', path='',
                          verified=False, sha256='', version='', via='direct', via_peer='')
    threading.Thread(target=_do_download, args=(asset_url, expected_sha256, expected_size),
                      daemon=True).start()


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
    with _lock:
        if _download['status'] == 'downloading':
            return False, 'Un téléchargement est déjà en cours.'
        _download.update(status='downloading', pct=0, error='', path='',
                          verified=False, sha256='', version='', via=mode, via_peer='')
    # ref_size est calculé en tête (cache mémoire, sinon référence persistée
    # d'une session antérieure) — jamais réécrasé ici depuis `check`, qui est
    # vide après un redémarrage.
    platform = _platform_key()
    known_lan_ips = [str(ip).strip() for ip in (known_lan_ips or []) if str(ip).strip()]
    threading.Thread(target=_do_download_via_network,
                      args=(mode, ips, ref_tag, platform, ref_sha, ref_size, known_lan_ips),
                      daemon=True).start()
    return True, ''


def _do_download_via_network(mode, ips, tag, platform, expected_sha256, expected_size,
                              known_lan_ips=None):
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
                if not status or not status.get('gateway_available'):
                    last_err = f'{ip} : pas disponible comme passerelle.'
                    continue
                url = (f'http://{ip}:{PORT}/app/update_relay'
                       f'?tag={urllib.parse.quote(tag)}&platform={urllib.parse.quote(platform)}')
            else:  # 'peer' — secours
                status = _peer_get_json(ip, '/app/update_serve_status', timeout=3)
                if not status or not status.get('available'):
                    last_err = f'{ip} : aucun exécutable vérifié à servir.'
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

def apply_update_and_relaunch(new_exe_path):
    """Lance un script auxiliaire détaché qui attend la fin du processus
    courant, remplace l'exécutable, puis le relance — puis retourne
    immédiatement (l'appelant doit arrêter le serveur juste après, sinon le
    script auxiliaire attendra indéfiniment que ce processus se termine).
    Fonctionne à l'identique quelle que soit la provenance du fichier déjà
    vérifié (téléchargement direct, passerelle réseau ou pair-à-pair) — la
    vérification d'intégrité a déjà eu lieu en amont dans _do_download /
    _do_download_via_network, jamais ici."""
    if not is_frozen():
        return False, "Pas d'exécutable à remplacer en mode développement"
    if not os.path.exists(new_exe_path):
        return False, "Fichier téléchargé introuvable"

    current_exe = sys.executable
    pid = os.getpid()
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
        script = '''@echo off
set count=0
timeout /t 2 /nobreak >NUL
:retry
move /Y "%LOGX_UPDATE_NEW%" "%LOGX_UPDATE_CURRENT%" >NUL 2>&1
if not errorlevel 1 goto launch
set /a count+=1
if %count% GEQ 30 goto giveup
timeout /t 1 /nobreak >NUL
goto retry
:launch
start "" "%LOGX_UPDATE_CURRENT%"
del "%~f0"
goto :eof
:giveup
echo Echec du remplacement - fermez LogXAI.exe puis relancez-le manuellement. > "%LOGX_UPDATE_CURRENT%.update_failed.txt"
'''
        with open(helper, 'w', encoding='ascii') as f:
            f.write(script)
        env = os.environ.copy()
        env['LOGX_UPDATE_NEW'] = new_exe_path
        env['LOGX_UPDATE_CURRENT'] = current_exe
        subprocess.Popen(
            ['cmd', '/c', helper],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
            env=env,
        )
    else:
        helper = os.path.join(update_dir, '_apply_update.sh')
        script = f'''#!/bin/sh
sleep 2
i=0
while ! mv -f "{new_exe_path}" "{current_exe}" 2>/dev/null; do
  i=$((i+1))
  if [ "$i" -ge 30 ]; then
    echo "Echec du remplacement - fermez LogXAI puis relancez-le manuellement." > "{current_exe}.update_failed.txt"
    exit 1
  fi
  sleep 1
done
chmod +x "{current_exe}"
nohup "{current_exe}" >/dev/null 2>&1 &
rm -f "$0"
'''
        with open(helper, 'w', encoding='utf-8') as f:
            f.write(script)
        os.chmod(helper, os.stat(helper).st_mode | stat.S_IEXEC)
        subprocess.Popen(['/bin/sh', helper], start_new_session=True, close_fds=True)

    return True, ''
