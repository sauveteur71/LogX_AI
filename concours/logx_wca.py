# -*- coding: utf-8 -*-
"""WCA (World Castles Award) — base des châteaux + activations annoncées.

Ne réutilise PAS le moteur générique logx_activation_db.py : la source est un
classeur OpenDocument (.ods, un zip contenant du XML) sans coordonnées GPS,
là où POTA/WWFF/IOTA sont des CSV/JSON plats avec lat/lon — assez différent
pour justifier un parsing dédié plutôt que de forcer le moteur générique à
gérer deux formats. Le schéma général (thread de fond, cache disque avec
péremption, statut ready/loading/error) reste le même que logx_sota.py.

  - Base des châteaux : https://wcagroup.org/FORMS/WCALIST.ods, le classeur
    officiel complet (~2,1 Mo compressé, 201 feuilles — une par préfixe pays,
    ex. « F » pour la France), lié en téléchargement direct depuis
    wcagroup.org. Colonnes réelles (vérifiées en direct, feuille F) : № WCA,
    № CASTLES, PREFIX, NAME OF CASTLE, LOCATION, INFORMATION — PAS de lat/lon
    dans ce fichier, donc pas de nearby() possible pour les châteaux (il
    faudrait géocoder ~15-20k entrées, hors de question avec Nominatim limité
    à 1 requête/s). En revanche geocode_castle()/get_castle_geocoded()
    géocodent à la demande LA SEULE référence que l'opérateur active (nom +
    localisation + pays -> lat/lon via Nominatim, sens inverse de
    _reverseGeocodeCity côté logx_configuration.html), avec mise en cache
    disque permanente : de quoi positionner MON château sur une carte et
    calculer distance/azimut depuis ma station, comme les 5 autres
    programmes le font nativement grâce à leurs propres coordonnées.
  - Activations annoncées : https://wcagroup.org/?feed=rss2, un flux RSS
    WordPress standard. ATTENTION : ce sont des activations PLANIFIÉES /
    auto-annoncées par les opérateurs (« DF6EX va activer... »), PAS des
    spots confirmés sur l'air comme POTA/SOTA/WWFF — à afficher étiqueté
    différemment côté UI. La référence WCA est en texte libre dans le titre/
    la description (ex. « WCA: DL-03166 ») : on l'extrait par une regex, pas
    de champ structuré dédié.
"""
import html
import io
import re
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from urllib.parse import urlencode

from logx_activation_db import age_days, atomic_write

WCA_ODS_URL = 'https://wcagroup.org/FORMS/WCALIST.ods'
CASTLES_CACHE_FILE = 'wca_castles.json'
MAX_AGE_DAYS = 30

_TABLE_NS = 'urn:oasis:names:tc:opendocument:xmlns:table:1.0'
_TEXT_NS = 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'
_CODE_RE = re.compile(r'^[A-Z0-9]{1,4}-\d{4,5}$')

_state = {'by_code': {}, 'list': [], 'loading': False, 'loaded': False, 'error': None}
_lock = threading.Lock()


def _walk_text(node, buf):
    """Collecte récursive du texte d'un nœud OpenDocument : .text, enfants
    (en développant <text:s text:c="N"/> en N espaces) puis .tail. Nécessaire
    car LibreOffice/Excel enveloppent dans des <text:span> toute portion de
    cellule portant une mise en forme de caractères — un simple parcours des
    enfants directs perdrait leur contenu (« Château <span>de Foix</span> »
    deviendrait « Château  »)."""
    if node.text:
        buf.append(node.text)
    for child in node:
        tag = child.tag.split('}')[-1]
        if tag == 's':
            n = int(child.get(f'{{{_TEXT_NS}}}c', '1') or '1')
            buf.append(' ' * n)
        else:
            _walk_text(child, buf)
        if child.tail:
            buf.append(child.tail)


def _cell_text(cell):
    """Texte d'une cellule .ods : concatène les <text:p>, en développant les
    <text:s text:c="N"/> (répétition d'espaces, pas du texte litéral dans le
    XML OpenDocument) et en descendant dans les <text:span> (mise en forme)."""
    parts = []
    for p in cell.findall(f'{{{_TEXT_NS}}}p'):
        buf = []
        _walk_text(p, buf)
        parts.append(''.join(buf))
    return ' '.join(parts).strip()


def _parse_wca_ods(raw_bytes):
    """Classeur .ods (bytes) -> liste de dicts. Parcourt content.xml en
    streaming (iterparse + clear()) plutôt que de charger tout le DOM : le
    XML décompressé fait ~60 Mo pour ~2 Mo de fichier zippé."""
    castles = []
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
        with zf.open('content.xml') as f:
            current_table = None
            header_seen = False
            for event, elem in ET.iterparse(f, events=('start', 'end')):
                tag = elem.tag.split('}')[-1]
                if event == 'start' and tag == 'table':
                    current_table = elem.get(f'{{{_TABLE_NS}}}name')
                    header_seen = False
                elif event == 'end' and tag == 'table-row' and current_table and current_table != 'INFO':
                    cells = []
                    for c in elem.findall(f'{{{_TABLE_NS}}}table-cell'):
                        repeat = int(c.get(f'{{{_TABLE_NS}}}number-columns-repeated', '1') or '1')
                        cells.extend([_cell_text(c)] * repeat)
                    if not header_seen:
                        header_seen = True
                    elif len(cells) >= 5 and cells[0]:
                        code = cells[0].strip().upper()
                        if _CODE_RE.match(code):
                            castles.append({
                                'code': code,
                                'castle_no': cells[1].strip(),
                                'prefix': cells[2].strip(),
                                'name': cells[3].strip(),
                                'location': cells[4].strip(),
                            })
                    elem.clear()
                elif event == 'end' and tag == 'table':
                    current_table = None
    return castles


def _load():
    try:
        age = age_days(CASTLES_CACHE_FILE)
        castles = None
        if age is not None and age < MAX_AGE_DAYS:
            try:
                import json
                with open(CASTLES_CACHE_FILE, encoding='utf-8') as f:
                    castles = json.load(f)
                if not isinstance(castles, list) or len(castles) < 5000:
                    castles = None
            except (OSError, ValueError):
                castles = None
        if castles is None:
            from logx_utils import fetch_url_binary
            raw = fetch_url_binary(WCA_ODS_URL, timeout=90)
            if not raw:
                with _lock:
                    _state['loading'] = False
                    _state['error'] = 'Base indisponible (réseau/cache)'
                return
            castles = _parse_wca_ods(raw)
            if len(castles) < 5000:  # garde-fou : le vrai fichier compte ~15-20k châteaux
                with _lock:
                    _state['loading'] = False
                    _state['error'] = f'Fichier téléchargé mais parsing suspect ({len(castles)} entrées)'
                return
            try:
                import json
                atomic_write(CASTLES_CACHE_FILE, json.dumps(castles, ensure_ascii=False))
            except OSError as e:
                print(f"[WCA] Ecriture cache impossible (non bloquant): {e}")

        by_code = {c['code']: c for c in castles}
        with _lock:
            _state['by_code'] = by_code
            _state['list'] = castles
            _state['loaded'] = True
            _state['loading'] = False
            _state['error'] = None
        print(f"[WCA] {len(castles)} châteaux chargés")
    except Exception as e:
        with _lock:
            _state['loading'] = False
            _state['error'] = str(e)
        print(f"[WCA] Erreur chargement: {e}")


def ensure_loading_started():
    with _lock:
        if _state['loaded'] or _state['loading']:
            return
        _state['loading'] = True
    threading.Thread(target=_load, daemon=True).start()


def status():
    ensure_loading_started()
    with _lock:
        return {'ready': _state['loaded'], 'loading': _state['loading'],
                'count': len(_state['list']), 'error': _state['error']}


def get_castle(code):
    ensure_loading_started()
    code = (code or '').strip().upper()
    with _lock:
        return _state['by_code'].get(code)


def search_castles(query, limit=25):
    ensure_loading_started()
    query = (query or '').strip()
    if len(query) < 2:
        return []
    q_upper = query.upper()
    from logx_activation_db import strip_accents
    q_folded = strip_accents(query).lower()
    with _lock:
        items = _state['list']
        if not items:
            return []
        by_code_prefix = [it for it in items if it['code'].startswith(q_upper)]
        if len(by_code_prefix) >= limit:
            return by_code_prefix[:limit]
        by_name = [it for it in items
                   if q_folded in strip_accents(it['name']).lower()
                   or q_folded in strip_accents(it['location']).lower()]
        seen = {it['code'] for it in by_code_prefix}
        merged = by_code_prefix + [it for it in by_name if it['code'] not in seen]
        return merged[:limit]


# ─── GÉOCODAGE (sens direct) DE LA RÉFÉRENCE ACTIVÉE ─────────────────────────
# WCALIST.ods ne fournit aucune coordonnée : impossible de géocoder les
# ~15-20k châteaux de la base (Nominatim limite à 1 req/s — des heures, et
# une utilisation en masse contraire à sa politique d'usage). En revanche,
# UN SEUL château (celui que l'opérateur déclare activer dans MA RÉFÉRENCE
# ACTIVÉE) peut l'être à la demande, résultat mis en cache disque à vie (un
# château ne déménage pas) : de quoi lui donner une position sur la carte et
# une distance/azimut depuis la station, comme les 5 autres programmes
# d'activation le font nativement grâce à leurs propres coordonnées.
NOMINATIM_SEARCH_URL = 'https://nominatim.openstreetmap.org/search'
GEOCODE_CACHE_FILE = 'wca_geocode_cache.json'
# Un échec (réseau, ou château introuvable sur Nominatim) est re-tenté après
# ce délai plutôt que mis en cache indéfiniment (transitoire possible) ; un
# succès, lui, est définitif.
GEOCODE_NEG_RETRY_DAYS = 7

_geocode_cache = None  # dict code -> {'lat','lon','ts'} ; chargé à la demande
# Réentrant : geocode_castle() tient ce verrou sur TOUT son cycle lire-décider-
# écrire (chargement du cache inclus), y compris pendant _throttle_nominatim()
# qui le reprend en interne — un Lock simple ferait deadlocker ce dernier appel.
_geocode_lock = threading.RLock()
# Horodatage de la dernière requête Nominatim envoyée (toutes références
# confondues) : impose l'espacement minimal de la politique d'usage Nominatim
# (1 req/s), même si plusieurs threads appellent geocode_castle() en parallèle.
_last_nominatim_call = [0.0]


def _load_geocode_cache():
    """Charge (une fois) le cache disque dans la variable globale partagée.
    DOIT toujours être appelée avec _geocode_lock déjà tenu par l'appelant :
    sans verrou, deux tout premiers appels concurrents constatent chacun
    `_geocode_cache is None`, créent chacun leur PROPRE dict, et écrasent la
    référence globale l'un après l'autre — la variable locale que le premier
    appelant a capturée devient alors orpheline, et tout ce qu'il y écrit
    ensuite n'est jamais persisté par _save_geocode_cache() (qui sauvegarde
    toujours la variable globale, pas la référence locale de l'appelant)."""
    global _geocode_cache
    if _geocode_cache is not None:
        return _geocode_cache
    try:
        import json
        with open(GEOCODE_CACHE_FILE, encoding='utf-8') as f:
            cache = json.load(f)
        _geocode_cache = cache if isinstance(cache, dict) else {}
    except (OSError, ValueError):
        _geocode_cache = {}
    return _geocode_cache


def _save_geocode_cache():
    """Persiste _geocode_cache. DOIT elle aussi être appelée avec
    _geocode_lock tenu (cf. _load_geocode_cache) : ce n'est JAMAIS une
    référence locale qui est sauvegardée, mais toujours la variable globale
    couramment tenue par le verrou."""
    try:
        import json
        atomic_write(GEOCODE_CACHE_FILE, json.dumps(_geocode_cache, ensure_ascii=False))
    except OSError as e:
        print(f"[WCA] Ecriture cache geocodage impossible (non bloquant): {e}")


def _country_for_prefix(prefix):
    """Préfixe indicatif WCA (ex. 'DL', '9A') -> nom de pays, via la même
    base cty.dat que le reste de l'app (logx_dxcc) — pour compléter la
    requête Nominatim au-delà du seul nom du château + sa localisation."""
    if not prefix:
        return ''
    try:
        import logx_dxcc as dxcc
        info = dxcc.lookup(prefix)
        return (info or {}).get('country', '') or ''
    except Exception:
        return ''


def _throttle_nominatim():
    """Respecte la politique d'usage Nominatim (1 requête/s max) : attend le
    complément nécessaire depuis le dernier appel, verrou partagé car on ne
    géocode jamais qu'une référence à la fois en pratique (une par activation)."""
    with _geocode_lock:
        wait = 1.0 - (time.time() - _last_nominatim_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_nominatim_call[0] = time.time()


def geocode_castle(code):
    """Coordonnées GPS d'UN château (nom + localisation + pays -> lat/lon via
    Nominatim, en cache disque permanent côté succès). Ne déclenche JAMAIS de
    géocodage pour une référence absente de la base (pas d'appel réseau pour
    une saisie invalide/inconnue). Renvoie {'lat','lon'} ou None."""
    castle = get_castle(code)
    if not castle:
        return None
    code = castle['code']

    # Tout le cycle lire (charger le cache + regarder si déjà connu) - décider
    # - au besoin interroger Nominatim - écrire (cache + disque) tient sous LE
    # MÊME verrou, sans jamais le relâcher entre-temps : c'est le chargement
    # non protégé de _geocode_cache qui causait la perte silencieuse d'un
    # résultat fraîchement géocodé (cf. docstring de _load_geocode_cache).
    with _geocode_lock:
        cache = _load_geocode_cache()
        hit = cache.get(code)
        if hit is not None:
            if hit.get('lat') is not None:
                return {'lat': hit['lat'], 'lon': hit['lon']}
            age = (time.time() - hit.get('ts', 0)) / 86400
            if age < GEOCODE_NEG_RETRY_DAYS:
                return None

        country = _country_for_prefix(castle.get('prefix', ''))
        query = ', '.join(p for p in (castle.get('name'), castle.get('location'), country) if p)
        lat = lon = None
        if query:
            _throttle_nominatim()
            from logx_utils import fetch_url
            qs = urlencode({'format': 'json', 'limit': 1, 'q': query})
            raw = fetch_url(f'{NOMINATIM_SEARCH_URL}?{qs}', timeout=10)
            if raw:
                try:
                    import json
                    results = json.loads(raw)
                    if results:
                        lat, lon = float(results[0]['lat']), float(results[0]['lon'])
                except (ValueError, KeyError, TypeError, IndexError):
                    lat = lon = None

        cache[code] = {'lat': lat, 'lon': lon, 'ts': time.time()}
        _save_geocode_cache()
    return {'lat': lat, 'lon': lon} if lat is not None else None


def get_castle_geocoded(code):
    """Comme get_castle(), avec 'lat'/'lon' en plus (None si non géocodable) —
    utilisé UNIQUEMENT par la validation de MA RÉFÉRENCE ACTIVÉE (une requête
    Nominatim par référence choisie), jamais par search_castles() (des
    dizaines de suggestions à chaque frappe : géocoder chacune enfreindrait
    la politique d'usage Nominatim)."""
    castle = get_castle(code)
    if not castle:
        return None
    coords = geocode_castle(code)
    merged = dict(castle)
    merged['lat'] = coords['lat'] if coords else None
    merged['lon'] = coords['lon'] if coords else None
    return merged


# ─── ACTIVATIONS ANNONCÉES (RSS — planifiées, PAS des spots confirmés) ────────

RSS_URL = 'https://wcagroup.org/?feed=rss2'
_RSS_CACHE_TTL = 900  # 15 min : simple flux RSS de blog, pas un flux de spots temps réel
_rss_cache = {'data': None, 'ts': 0}
# Même famille de codes que _CODE_RE (préfixe pouvant contenir un chiffre :
# 9A- Croatie, S5- Slovénie ; 4 OU 5 chiffres) — une regex plus étroite ici
# faisait disparaître silencieusement ces annonces du flux RSS.
_REF_RE = re.compile(r'\b([A-Z0-9]{1,4}-\d{4,5})\b')


def _strip_html(s):
    return html.unescape(re.sub(r'<[^>]+>', ' ', s or '')).strip()


def fetch_planned_activations():
    """Activations WCA/COTA annoncées à l'avance par les opérateurs sur leur
    blog (WordPress RSS standard) — PAS des spots confirmés sur l'air. La
    référence est en texte libre : extraite par regex, peut être absente sur
    certains billets (dans ce cas l'entrée est simplement omise)."""
    if _rss_cache['data'] is not None and time.time() - _rss_cache['ts'] < _RSS_CACHE_TTL:
        return _rss_cache['data']
    from logx_utils import fetch_url
    raw = fetch_url(RSS_URL, timeout=15)
    if not raw:
        return _rss_cache['data'] or []
    try:
        # Le flux contient un <script> avant le prologue XML (pub du thème
        # WordPress) — on repart du vrai début du document XML.
        xml_start = raw.find('<?xml')
        if xml_start > 0:
            raw = raw[xml_start:]
        root = ET.fromstring(raw)
    except ET.ParseError:
        return _rss_cache['data'] or []

    items = []
    for item in root.iter('item'):
        title = (item.findtext('title') or '').strip()
        desc = _strip_html(item.findtext('description') or '')
        link = (item.findtext('link') or '').strip()
        pub_date = (item.findtext('pubDate') or '').strip()
        m = _REF_RE.search(title) or _REF_RE.search(desc)
        if not m:
            continue
        items.append({
            'reference': m.group(1),
            'title': title,
            'description': desc[:300],
            'link': link,
            'pub_date': pub_date,
            'source': 'wca_planned',
        })
    _rss_cache['data'] = items
    _rss_cache['ts'] = time.time()
    return items
