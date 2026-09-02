# -*- coding: utf-8 -*-
"""GMA (Global Mountain Activity) — détails d'un sommet PAR RÉFÉRENCE.

Contrairement à POTA/SOTA/WWFF (gros export CSV téléchargé + mis en cache),
GMA expose une API officielle PAR RÉFÉRENCE : https://cqgma.org/api/ref/?REF
-> JSON {ref,name,height,latitude,longitude,region_name,act_count,wwff,deleted…}
(vérifié en direct). C'est exactement le besoin du relevé de saisie : on
interroge la réf que l'opérateur tape (la sienne ou celle du correspondant
chassé), rien d'autre. Donc :

- AUCUN téléchargement massif, AUCUNE redistribution de base (contrairement aux
  bulk POTA/WWFF/WWBOTA) — le souci de droits ne se pose même pas.
- Cache MÉMOIRE : une même réf n'est demandée qu'une fois par session.
- Tolérant réseau : une réf absente renvoie un corps VIDE ('' -> None, cachée
  comme « absente » — absente ≠ invalide) ; une ERREUR réseau (fetch_url -> None)
  n'est PAS mémorisée, pour que la réf soit réessayée plus tard.

Réf GMA : même schéma que SOTA (assoc/région-n°, ex. DL/BE-055) — cf.
PROGRAM_SPECS['GMA']. Pas de recherche par nom (API par-réf) : le relevé de
saisie n'interroge que par réf exacte, get() suffit.
"""
import json

GMA_API_URL = 'https://cqgma.org/api/ref/?'
_USER_AGENT = 'LogX-AI/1.2 (F4GLD)'
_cache = {}   # ref normalisée -> entry|None (résultats définitifs uniquement)


def _normaliser(ref):
    return (ref or '').strip().upper()


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _mapper(d):
    """JSON GMA -> entrée générique (mêmes clés que les autres programmes pour
    le relevé de saisie : name/region/alt_m/lat/lon)."""
    try:
        alt = int(float(d.get('height')))
    except (TypeError, ValueError):
        alt = None
    return {
        'code': d.get('ref', ''),
        'name': d.get('name', ''),
        'region': d.get('region_name') or '',
        'alt_m': alt,
        'lat': _num(d.get('latitude')),
        'lon': _num(d.get('longitude')),
        'act_count': str(d.get('act_count') or ''),
        'wwff': d.get('wwff') or '',
    }


def get(ref):
    """Réf GMA -> détails du sommet, ou None (absente / réseau KO)."""
    ref = _normaliser(ref)
    if not ref:
        return None
    if ref in _cache:
        return _cache[ref]
    from logx_utils import fetch_url
    raw = fetch_url(GMA_API_URL + ref, timeout=15, user_agent=_USER_AGENT)
    if raw is None:
        return None                      # erreur réseau -> ne pas mémoriser (réessai plus tard)
    entry = None
    if raw.strip():
        try:
            d = json.loads(raw)
        except (ValueError, TypeError):
            d = None
        # dict avec une vraie réf et non supprimé (deleted != '0' -> ignoré)
        if isinstance(d, dict) and d.get('ref') and str(d.get('deleted', '0')) in ('0', ''):
            entry = _mapper(d)
    _cache[ref] = entry                  # corps vide OU sommet trouvé -> résultat définitif
    return entry


def search(query, limit=25):
    """API par-référence : pas de recherche par nom (le relevé de saisie
    n'interroge que par réf exacte)."""
    return []


def status():
    return {'ready': True, 'loading': False, 'count': len(_cache),
            'source': GMA_API_URL, 'mode': 'api_par_reference'}
