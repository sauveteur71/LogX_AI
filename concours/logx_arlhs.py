# -*- coding: utf-8 -*-
"""ARLHS (Amateur Radio Lighthouse Society) — détails d'un phare PAR RÉFÉRENCE.

Comme GMA, on interroge la base officielle WLOL (World List of Lights) PAR
RÉFÉRENCE plutôt que de télécharger toute la base : une réf « FRA-113 » se
décompose en section=FRA + number=113, envoyés au formulaire
https://wlol.arlhs.com/index.php?mode=search -> une fiche HTML unique
(vérifié en direct : FRA-113 = Aber Ildut, IN78ol, 48°28'N/004°46'W).

DROITS : la WLOL est explicitement « Copyright ARLHS, LLC » (affiché sur chaque
page). On ne récupère donc QUE la réf que l'opérateur tape (la sienne ou celle
du correspondant chassé), en cache mémoire — AUCUN téléchargement massif, AUCUNE
copie de la base dans le dépôt. Le souci de redistribution ne se pose pas.

Tolérant réseau : réf absente -> pas de ligne résultat -> None caché
(absente ≠ invalide) ; erreur réseau -> None NON mémorisé (réessai plus tard).
Réf ARLHS : préfixe pays 2-3 lettres + n° 3-4 chiffres (+ lettre), ex. FRA-113
— cf. PROGRAM_SPECS['ARLHS']. Pas de recherche par nom (lookup par réf exacte).
"""
import re
import urllib.parse

WLOL_URL = 'https://wlol.arlhs.com/index.php'
_USER_AGENT = 'LogX-AI/1.2 (F4GLD)'
_cache = {}   # ref normalisée -> entry|None (résultats définitifs uniquement)

_REF_RE = re.compile(r'^([A-Z]{2,3})-?(\d{3,4})([A-Z]?)$')
# Ligne résultat : <tr bgcolor="lightgreen"> ... </tr>
_ROW_RE = re.compile(r'<tr[^>]*bgcolor="lightgreen"[^>]*>(.*?)</tr>', re.S | re.I)
_CELL_RE = re.compile(r'<td[^>]*>(.*?)</td>', re.S | re.I)
# Coordonnées propres depuis le lien geohack : params=48_28_00_N_004_46_00_W
_GEOHACK_RE = re.compile(
    r'params=(\d+)_(\d+)_(\d+)_([NS])_(\d+)_(\d+)_(\d+)_([EW])', re.I)
_LOCATOR_RE = re.compile(r'\b([A-R]{2}\d{2}[a-x]{2})\b')


def _normaliser(ref):
    return (ref or '').strip().upper().replace(' ', '')


def _sans_html(s):
    return re.sub(r'<[^>]+>', '', s or '').strip()


def _dms_to_dd(deg, minutes, sec, hemi):
    dd = int(deg) + int(minutes) / 60 + int(sec) / 3600
    return -dd if hemi in ('S', 'W') else dd


def _parse_fiche(html, code):
    """HTML de résultat WLOL -> entrée, ou None si aucune ligne (réf absente)."""
    m = _ROW_RE.search(html or '')
    if not m:
        return None
    cells = [_sans_html(c) for c in _CELL_RE.findall(m.group(1))]
    if not cells:
        return None
    name = cells[0]
    lat = lon = None
    g = _GEOHACK_RE.search(m.group(1))
    if g:
        lat = _dms_to_dd(g.group(1), g.group(2), g.group(3), g.group(4).upper())
        lon = _dms_to_dd(g.group(5), g.group(6), g.group(7), g.group(8).upper())
    loc = _LOCATOR_RE.search(m.group(1))
    # nombre d'activations = dernière cellule numérique
    act = next((c for c in reversed(cells) if c.isdigit()), '')
    return {
        'code': code,
        'name': name,
        'region': '',
        'locator': loc.group(1) if loc else '',
        'lat': lat,
        'lon': lon,
        'act_count': act,
    }


def get(ref):
    """Réf ARLHS -> détails du phare, ou None (absente / réseau KO)."""
    ref = _normaliser(ref)
    m = _REF_RE.match(ref)
    if not m:
        return None
    code = '%s-%s%s' % (m.group(1), m.group(2), m.group(3))
    if code in _cache:
        return _cache[code]
    from logx_utils import fetch_url
    url = WLOL_URL + '?' + urllib.parse.urlencode({
        'mode': 'search', 'section': m.group(1), 'number': m.group(2), 'go': '1'})
    html = fetch_url(url, timeout=20, user_agent=_USER_AGENT)
    if html is None:
        return None                      # erreur réseau -> ne pas mémoriser
    entry = _parse_fiche(html, code)
    _cache[code] = entry                 # fiche trouvée OU absente -> résultat définitif
    return entry


def search(query, limit=25):
    """Base WLOL protégée + lookup par réf exacte : pas de recherche par nom."""
    return []


def status():
    return {'ready': True, 'loading': False, 'count': len(_cache),
            'source': WLOL_URL, 'mode': 'api_par_reference'}
