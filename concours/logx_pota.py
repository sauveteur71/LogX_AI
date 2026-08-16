# -*- coding: utf-8 -*-
"""Spots d'activateurs POTA (Parks On The Air) en direct + base des parcs.

Complète le mode Activation (logx_activation.py, purement local/déterministe :
validation de référence + progression depuis le log) par une vue en direct de
qui active quoi ACTUELLEMENT dans le monde, utile aussi bien à un chasseur
(hunter) qu'à un activateur qui veut repérer les parcs déjà occupés à
proximité, ET par l'auto-spot (post_spot ci-dessous) pour publier SA PROPRE
activation.

Spots en direct, endpoint public sans clé : https://api.pota.app/spot/activator
Doc communautaire : https://docs.pota.app/

Auto-spot (POST) : format vérifié contre le code source ouvert de hunterlog
(cwhelchel/hunterlog, src/pota/pota.py, fonction post_spot — pas deviné) :
endpoint https://api.pota.app/spot/, JSON {activator, spotter, frequency,
reference, mode, source, comments}, sans authentification (même API ouverte
que la lecture ci-dessus). fréquence en kHz : cohérent avec fetch_pota_spots
ci-dessous ET avec le guide utilisateur hunterlog (« Frequency should be
entered in kilohertz (kHz) »).

Base des parcs : https://pota.app/all_parks_ext.csv, l'export CSV complet
(~9 Mo, ~50 000 parcs) proposé en téléchargement direct par POTA lui-même
(lié depuis leur page « Park Search »). Comme pour SOTA (logx_sota.py), sert
à VALIDER une référence saisie (nom, localisation) et à la RECHERCHER par
code ou par nom — via le moteur générique logx_activation_db.py."""
import csv
import json
import re
import time

from logx_activation_db import ActivationDatabase

POTA_SPOTS_URL = 'https://api.pota.app/spot/activator'
CACHE_TTL = 90  # secondes — assez réactif sans marteler l'API publique

_cache = {'data': None, 'ts': 0}


def fetch_pota_spots():
    """Spots activateurs POTA en direct, au format spot générique du logiciel
    (mêmes clés que les autres sources : call/freq/band/mode/info/time/...).
    Cache court ; en cas d'échec réseau, renvoie le dernier résultat connu
    plutôt qu'une liste vide (dégrade proprement, comme les autres sources)."""
    if _cache['data'] is not None and time.time() - _cache['ts'] < CACHE_TTL:
        return _cache['data']
    from logx_utils import fetch_url  # import local : mockable par les tests (monkeypatch sur logx_utils)
    raw = fetch_url(POTA_SPOTS_URL, timeout=10)
    if not raw:
        return _cache['data'] or []
    try:
        items = json.loads(raw)
    except (ValueError, TypeError):
        return _cache['data'] or []
    if not isinstance(items, list):
        return _cache['data'] or []

    from logx_scoring import _band_from_freq
    spots = []
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            freq_khz = float(it.get('frequency') or 0)
        except (TypeError, ValueError):
            freq_khz = 0
        spots.append({
            'call': str(it.get('activator', '')).upper(),
            'freq': freq_khz,  # kHz, cohérent avec les autres sources de spots
            'band': _band_from_freq(freq_khz),
            'mode': str(it.get('mode', '')).upper(),
            'reference': it.get('reference', ''),
            'park_name': it.get('name') or it.get('parkName') or '',
            'location': it.get('locationDesc', ''),
            'grid': it.get('grid6') or it.get('grid4') or '',
            'lat': it.get('latitude'),
            'lon': it.get('longitude'),
            'comment': it.get('comments', ''),
            'spotter': it.get('spotter', ''),
            'time': it.get('spotTime', ''),
            'count': it.get('count', 0),
            'source': 'pota',
        })
    _cache['data'] = spots
    _cache['ts'] = time.time()
    return spots


# ─── AUTO-SPOT (POST) ─────────────────────────────────────────────────────────
# Voir le docstring du module : format vérifié contre hunterlog, pas deviné.
POTA_POST_SPOT_URL = 'https://api.pota.app/spot/'


def post_spot(activator, reference, freq_khz, mode, spotter='', comment=''):
    """Publie un spot d'activateur sur le flux public POTA (équivalent du
    bouton « Add Spot » de pota.app) — visible immédiatement par tous les
    chasseurs. Aucune authentification (comme la lecture ci-dessus) : à
    l'activateur d'appeler cette fonction seulement pour SA PROPRE activation.
    Valide localement avant tout appel réseau (évite un aller-retour pour une
    erreur de saisie triviale) ; ne lève jamais, renvoie {'ok': bool, ...}
    comme les autres fonctions réseau du projet (logx_qsl, logx_clusters...)."""
    # str() explicite AVANT .strip() : le payload JSON du endpoint HTTP peut
    # contenir un champ non-chaîne (ex. {"reference": 123}) — (x or '') ne
    # protège pas dans ce cas puisque 123 est "truthy" et n'a pas de .strip().
    activator = str(activator or '').strip().upper()
    reference = str(reference or '').strip().upper()
    mode = str(mode or '').strip().upper()
    try:
        freq_khz = float(freq_khz)
    except (TypeError, ValueError):
        freq_khz = 0
    if not activator:
        return {'ok': False, 'error': 'Indicatif activateur manquant'}
    if not reference:
        return {'ok': False, 'error': 'Référence parc manquante'}
    if freq_khz <= 0:
        return {'ok': False, 'error': 'Fréquence manquante ou invalide'}
    if not mode:
        return {'ok': False, 'error': 'Mode manquant'}

    from logx_utils import post_url_json  # import local : mockable par les tests
    from logx_version import APP_VERSION
    payload = {
        'activator': activator,
        'spotter': str(spotter or activator).strip().upper(),
        # f'{:.1f}' et non str() brut : freq_khz est un float qui peut avoir
        # traversé une conversion MHz->kHz (ex. 14.2853 * 1000), et str() sur
        # un float renvoie parfois du bruit IEEE-754 (14285.299999999999) — un
        # arrondi à 1 décimale (résolution largement suffisante en kHz) évite
        # d'envoyer ça tel quel à l'API publique POTA.
        'frequency': f'{freq_khz:.1f}',
        'reference': reference,
        'mode': mode,
        'source': 'LogXAI',
        'comments': str(comment or ''),
    }
    status, text = post_url_json(
        POTA_POST_SPOT_URL, payload, timeout=10,
        headers={'User-Agent': f'LogXAI/{APP_VERSION}'})
    if status is None:
        return {'ok': False, 'error': 'api.pota.app injoignable (réseau)'}
    if status >= 400:
        return {'ok': False, 'error': f'POTA a refusé le spot (HTTP {status}) : {(text or "")[:200].strip()}'}
    return {'ok': True, 'response': (text or '')[:200].strip()}


# ─── EXPORT ADIF (prêt à téléverser) ──────────────────────────────────────────
# POTA n'expose aucune API publique DOCUMENTÉE pour l'upload de log (contraire
# à LoTW/tqsl, cf. logx_qsl.py) — seule voie officielle : dépôt manuel du
# fichier ADIF sur la page « My Log Uploads » de pota.app (ou par e-mail).
# Décision F4GLD (16/08/2026) après vérification que même les logiciels
# concurrents ne font PAS d'upload automatique : ne pas reproduire l'auth
# non-officielle par mot de passe de compte (bibliothèque tierce trouvée,
# v0.1.0, très jeune) — on retire toute la friction qui PEUT l'être sans
# stocker d'identifiant : bon format ADIF (déjà géré par build_adif, qui
# émet MY_SIG/MY_SIG_INFO par QSO) + bon NOM de fichier.

def export_filename(callsign, park_ref, qsos):
    """Nom de fichier EXACT attendu par l'auto-uploader « My Log Uploads » de
    pota.app : callsign@parkRef-activationDate.adi — format et exemple
    officiel (KA8H@US-1515-20201127.adi) vérifiés sur
    docs.pota.app/docs/activator_reference/submitting_logs.html (16/08/2026).

    La date vient du QSO le plus RÉCENT du lot ; en usage normal ce lot est
    déjà réduit à un seul jour UTC par logx_activation.activation_qsos()
    (règle POTA), donc tous les QSO partagent la même date de toute façon."""
    call = re.sub(r'[^A-Z0-9\-]', '', (callsign or '').upper()) or 'LOG'
    ref = re.sub(r'[^A-Z0-9\-]', '', (park_ref or '').upper()) or 'PARK'
    dates = sorted({str(q.get('date', '')).replace('-', '')[:8]
                     for q in (qsos or []) if q.get('date')})
    date = dates[-1] if dates else ''
    return f'{call}@{ref}-{date}.adi' if date else f'{call}@{ref}.adi'


# ─── BASE DES PARCS ───────────────────────────────────────────────────────────

POTA_PARKS_URL = 'https://pota.app/all_parks_ext.csv'
PARKS_FILE = 'pota_parks.csv'


def _looks_valid_parks_csv(content):
    """Garde-fou avant d'écraser le cache : jamais un fichier tronqué ou une
    page d'erreur à la place du vrai export (~9 Mo, ~50 000 lignes)."""
    if not content or len(content) < 500_000:
        return False
    return content.count('"reference"') >= 1 and content.count(',') > 50_000


def _parse_parks_csv(content):
    """CSV -> liste de dicts. En-têtes réels (vérifiés en direct) :
    reference,name,active,entityId,locationDesc,latitude,longitude,grid."""
    reader = csv.DictReader(content.splitlines())
    out = []
    for row in reader:
        code = (row.get('reference') or '').strip().upper()
        if not code:
            continue
        try:
            lat = float(row.get('latitude') or '')
            lon = float(row.get('longitude') or '')
        except ValueError:
            lat = lon = None
        out.append({
            'code': code,
            'name': (row.get('name') or '').strip(),
            'location': (row.get('locationDesc') or '').strip(),
            'grid': (row.get('grid') or '').strip(),
            'active': (row.get('active') or '') == '1',
            'lat': lat,
            'lon': lon,
        })
    return out


parks_db = ActivationDatabase(
    label='POTA',
    source_url=POTA_PARKS_URL,
    cache_file=PARKS_FILE,
    parse_fn=_parse_parks_csv,
    valid_fn=_looks_valid_parks_csv,
    max_age_days=30,
    fetch_timeout=60,
)
