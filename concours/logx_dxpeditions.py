# -*- coding: utf-8 -*-
"""DXpeditions annoncées — flux RSS public NG3K ADXO (Announced DX Operations).

Référence historique de la communauté DX (maintenue par Bill Feidt/NG3K
depuis 1996, alimentée par OPDX/425DXN/TDDX/DX cluster) : la liste que la
plupart des loggers/outils DX consultent déjà. Choisie plutôt que :
  - ham365.net/Dxpeditions : données tirées d'une API interne privée
    (/IndexAjax/OnAirDxPedition) qui renvoie 500 hors session navigateur —
    pas prévue pour un accès programmatique tiers.
  - 425dxn.org : bulletin/archive consultable, mais pas de flux structuré.
NG3K, lui, publie explicitement un flux RSS destiné à la consommation
programmatique (icône RSS sur la page ADXO, lien direct vers adxo.xml) —
seule des trois sources avec une autorisation implicite claire de lecture
automatisée. Lecture seule, comme logx_pota.py.

Flux : https://www.ng3k.com/adxo.xml
Page d'origine (lecture humaine) : https://www.ng3k.com/Misc/adxo.html
"""
import re
import time
import xml.etree.ElementTree as ET

ADXO_RSS_URL = 'https://www.ng3k.com/adxo.xml'
CACHE_TTL = 3600  # 1h — liste annoncée, ne change pas minute par minute

_cache = {'data': None, 'ts': 0}


def _parse_description(desc):
    """'Jul 4-23, 2026 -- Crete -- SV9 -- QSL: LoTW -- Source: OPDX (13 May
    2026) -- By HB9EMP...' -> champs structurés. Format généré côté NG3K par
    un script (donc stable), mais on reste tolérant : un segment manquant ou
    en plus ne fait jamais échouer les autres — DXCC/pays est le champ dont
    on a le plus besoin (cross-référence avec les pays déjà travaillés)."""
    # Le flux met chaque segment sur sa propre ligne ("champ --\nchamp suivant --\n...") :
    # normaliser les espaces/retours à la ligne avant de séparer sur "--".
    normalized = re.sub(r'\s+', ' ', (desc or '')).strip()
    parts = [p.strip() for p in normalized.split(' -- ') if p.strip()]
    out = {'dates': '', 'entity': '', 'callsign': '', 'qsl': '', 'source': '', 'info': ''}
    if len(parts) >= 1:
        out['dates'] = parts[0]
    if len(parts) >= 2:
        out['entity'] = parts[1]
    if len(parts) >= 3:
        out['callsign'] = parts[2]
    if len(parts) >= 4:
        out['qsl'] = parts[3].split(':', 1)[-1].strip()
    if len(parts) >= 5:
        out['source'] = parts[4].split(':', 1)[-1].strip()
    if len(parts) >= 6:
        out['info'] = ' -- '.join(parts[5:])
    return out


def _fetch_raw():
    if _cache['data'] is not None and time.time() - _cache['ts'] < CACHE_TTL:
        return _cache['data']
    from logx_utils import fetch_url  # import local : mockable par les tests
    raw = fetch_url(ADXO_RSS_URL, timeout=10)
    if not raw:
        return _cache['data'] or []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return _cache['data'] or []

    expeditions = []
    for item in root.iter('item'):
        title = (item.findtext('title') or '').strip()
        fields = _parse_description(item.findtext('description') or '')
        if not fields['callsign'] and not fields['entity']:
            continue  # entrée vide/mal formée — ignorée plutôt que polluer la liste
        expeditions.append({'title': title, **fields})
    _cache['data'] = expeditions
    _cache['ts'] = time.time()
    return expeditions


def fetch_dxpeditions(worked_entities=None):
    """DXpeditions annoncées (actives + à venir), dans l'ordre du flux
    source. `worked_entities` (optionnel) : ensemble de noms de pays DXCC
    déjà travaillés (mêmes libellés que logx_dxcc, ex. via
    logx_countries.countries_progress()['by_continent'][...]['country']) —
    si fourni, chaque entrée est annotée 'worked': True/False/None (None =
    correspondance de nom non trouvée, le libellé NG3K ne colle pas
    exactement à celui de cty.dat — pas assez fiable pour trancher).
    Cache 1h ; en cas d'échec réseau, renvoie le dernier résultat connu
    plutôt qu'une liste vide (dégrade proprement, comme logx_pota.py)."""
    expeditions = _fetch_raw()
    if worked_entities is None:
        return expeditions
    worked_lower = {str(w).strip().lower() for w in worked_entities}
    out = []
    for exp in expeditions:
        e = dict(exp)
        name = (exp.get('entity') or '').strip().lower()
        e['worked'] = (name in worked_lower) if name else None
        out.append(e)
    return out
