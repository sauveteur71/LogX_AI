# -*- coding: utf-8 -*-
"""SOTA (Summits On The Air) — spots en direct + base des sommets.

Deux sources officielles, publiques, sans clé :
  - Spots en direct : api2.sota.org.uk (l'API qui alimente sotawatch.sota.org.uk
    lui-même — vérifié en inspectant les requêtes réseau de la page officielle).
  - Base des sommets : storage.sota.org.uk/summitslist.csv, l'export CSV complet
    (224 associations, ~230 000 sommets) proposé en téléchargement direct sur
    sotadata.org.uk/en/summits ("download a CSV file containing a list of all
    summits by clicking here"). Sert à VALIDER une référence saisie (nom, altitude,
    points) et à la RECHERCHER par code ou par nom — logx_activation.py ne
    vérifiait jusqu'ici que le FORMAT (regex), jamais l'existence réelle du sommet.

Le CSV fait ~25 Mo : téléchargé et parsé UNE FOIS en tâche de fond (thread
séparé, jamais dans le thread qui répond aux requêtes HTTP — cf. la
robustesse réseau déjà en place ailleurs dans le serveur), puis mis en cache
disque (rafraîchi si > 30 jours, comme cty.dat dans logx_dxcc.py). Pendant le
chargement, les fonctions de recherche renvoient 'ready': False plutôt que de
bloquer une requête jusqu'à une minute le temps du tout premier téléchargement.
"""
import csv
import io
import os
import threading
import time
import unicodedata

SOTA_SPOTS_URL = 'https://api2.sota.org.uk/api/spots/3/all/all'  # 3 dernières heures
SOTA_SUMMITS_URL = 'https://storage.sota.org.uk/summitslist.csv'
SUMMITS_FILE = 'sota_summits.csv'
SUMMITS_MAX_AGE_DAYS = 30

SPOTS_CACHE_TTL = 60  # secondes
_spots_cache = {'data': None, 'ts': 0}

_summits = {'by_code': {}, 'list': [], 'loading': False, 'loaded': False, 'error': None}
_summits_lock = threading.Lock()


# ─── SPOTS EN DIRECT ─────────────────────────────────────────────────────────

def fetch_sota_spots():
    """Spots d'activateurs SOTA en direct, format générique du logiciel (mêmes
    clés que logx_pota.fetch_pota_spots — call/freq/band/mode/...). Cache
    court ; en cas d'échec réseau, renvoie le dernier résultat connu plutôt
    qu'une liste vide (dégrade proprement, comme les autres sources)."""
    if _spots_cache['data'] is not None and time.time() - _spots_cache['ts'] < SPOTS_CACHE_TTL:
        return _spots_cache['data']
    from logx_utils import fetch_url  # import local : mockable par les tests
    raw = fetch_url(SOTA_SPOTS_URL, timeout=10)
    if not raw:
        return _spots_cache['data'] or []
    import json
    try:
        items = json.loads(raw)
    except (ValueError, TypeError):
        return _spots_cache['data'] or []
    if not isinstance(items, list):
        return _spots_cache['data'] or []

    from logx_scoring import _band_from_freq
    spots = []
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            freq_khz = float(it.get('frequency') or 0) * 1000  # MHz -> kHz, cohérent avec les autres sources
        except (TypeError, ValueError):
            freq_khz = 0
        spots.append({
            'call': str(it.get('activatorCallsign', '')).upper(),
            'freq': freq_khz,
            'band': _band_from_freq(freq_khz),
            'mode': str(it.get('mode', '')).upper(),
            'reference': it.get('summitCode', ''),
            'summit_name': it.get('summitName', ''),
            'alt_m': it.get('AltM'),
            'points': it.get('points'),
            'comment': it.get('comments', ''),
            'time': it.get('timeStamp', ''),
            'source': 'sota',
        })
    _spots_cache['data'] = spots
    _spots_cache['ts'] = time.time()
    return spots


# ─── BASE DES SOMMETS ─────────────────────────────────────────────────────────

def _age_days(path):
    if not os.path.exists(path):
        return None
    return (time.time() - os.path.getmtime(path)) / 86400


def _looks_valid_csv(content):
    """Garde-fou avant d'écraser le cache : jamais un fichier tronqué ou une
    page d'erreur à la place du vrai export."""
    if not content or len(content) < 1_000_000:  # le vrai fichier fait ~25 Mo
        return False
    return content.count('SummitCode') >= 1 and content.count(',') > 100_000


def _parse_summits_csv(content):
    """CSV -> liste de dicts. En-têtes réels du fichier (vérifiés en direct) :
    SummitCode,AssociationName,RegionName,SummitName,AltM,AltFt,GridRef1,
    GridRef2,Longitude,Latitude,Points,BonusPoints,ValidFrom,ValidTo,
    ActivationCount,ActivationDate,ActivationCall — première ligne = titre
    ("SOTA Summits List (Date=...)"), deuxième = vrai en-tête de colonnes."""
    lines = content.splitlines()
    if len(lines) < 2:
        return []
    reader = csv.DictReader(lines[1:])
    out = []
    for row in reader:
        code = (row.get('SummitCode') or '').strip()
        if not code:
            continue
        try:
            alt_m = int(float(row.get('AltM') or 0))
        except ValueError:
            alt_m = 0
        try:
            points = int(float(row.get('Points') or 0))
        except ValueError:
            points = 0
        out.append({
            'code': code.upper(),
            'association': (row.get('AssociationName') or '').strip(),
            'region': (row.get('RegionName') or '').strip(),
            'name': (row.get('SummitName') or '').strip(),
            'alt_m': alt_m,
            'points': points,
            'lat': row.get('Latitude') or '',
            'lon': row.get('Longitude') or '',
            'activations': row.get('ActivationCount') or '0',
        })
    return out


def _strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def _load_from_disk_or_network():
    """Exécuté dans un thread séparé (jamais le thread HTTP) : charge le cache
    disque s'il est valide et pas trop vieux, sinon télécharge et écrit
    atomiquement, comme update_cty_if_stale() dans logx_dxcc.py."""
    try:
        age = _age_days(SUMMITS_FILE)
        content = None
        if age is not None and age < SUMMITS_MAX_AGE_DAYS:
            try:
                with open(SUMMITS_FILE, encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except OSError:
                content = None
        if not content or not _looks_valid_csv(content):
            from logx_utils import fetch_url
            downloaded = fetch_url(SOTA_SUMMITS_URL, timeout=60)
            if _looks_valid_csv(downloaded or ''):
                content = downloaded
                try:
                    import tempfile
                    target_dir = os.path.dirname(os.path.abspath(SUMMITS_FILE)) or '.'
                    fd, tmp = tempfile.mkstemp(prefix='sota_summits.', suffix='.tmp', dir=target_dir)
                    with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
                        f.write(content)
                    os.replace(tmp, SUMMITS_FILE)
                except OSError as e:
                    print(f"[SOTA] Ecriture cache impossible (non bloquant): {e}")
            elif content is None:
                # Ni cache disque exploitable, ni téléchargement : abandon propre
                with _summits_lock:
                    _summits['loading'] = False
                    _summits['error'] = 'Base des sommets indisponible (réseau/cache)'
                return

        summits = _parse_summits_csv(content)
        by_code = {s['code']: s for s in summits}
        with _summits_lock:
            _summits['by_code'] = by_code
            _summits['list'] = summits
            _summits['loaded'] = True
            _summits['loading'] = False
            _summits['error'] = None
        print(f"[SOTA] {len(summits)} sommets chargés")
    except Exception as e:
        with _summits_lock:
            _summits['loading'] = False
            _summits['error'] = str(e)
        print(f"[SOTA] Erreur chargement base sommets: {e}")


def ensure_loading_started():
    """Démarre le chargement en tâche de fond s'il n'a pas déjà commencé —
    appelable sans risque à chaque requête, ne lance jamais deux threads."""
    with _summits_lock:
        if _summits['loaded'] or _summits['loading']:
            return
        _summits['loading'] = True
    threading.Thread(target=_load_from_disk_or_network, daemon=True).start()


def summits_status():
    ensure_loading_started()
    with _summits_lock:
        return {'ready': _summits['loaded'], 'loading': _summits['loading'],
                'count': len(_summits['list']), 'error': _summits['error']}


def get_summit(code):
    """Référence exacte -> détails, ou None si absente de la base (peut aussi
    signifier "base pas encore chargée" — vérifier summits_status()['ready'])."""
    ensure_loading_started()
    code = (code or '').strip().upper()
    with _summits_lock:
        return _summits['by_code'].get(code)


def search_summits(query, limit=25):
    """Recherche par code (préfixe) OU par nom/région/association (sous-chaîne,
    insensible à la casse et aux accents) — pour l'auto-complétion de la
    référence SOTA. Renvoie [] tant que la base n'est pas chargée (le premier
    appel démarre le chargement en tâche de fond, jamais bloquant)."""
    ensure_loading_started()
    query = (query or '').strip()
    if len(query) < 2:
        return []
    q_upper = query.upper()
    q_folded = _strip_accents(query).lower()
    with _summits_lock:
        summits = _summits['list']
        if not summits:
            return []
        by_code_prefix = [s for s in summits if s['code'].startswith(q_upper)]
        if len(by_code_prefix) >= limit:
            return by_code_prefix[:limit]
        by_name = [s for s in summits
                   if q_folded in _strip_accents(s['name']).lower()
                   or q_folded in _strip_accents(s['region']).lower()]
        seen = {s['code'] for s in by_code_prefix}
        merged = by_code_prefix + [s for s in by_name if s['code'] not in seen]
        return merged[:limit]
