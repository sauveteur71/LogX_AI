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
from datetime import date

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


# ─── STATUT ACTIF/À VENIR + FRÉQUENCE LIVE (panneau CHASSE) ──────────────────
# NG3K liste des ANNONCES (dates prévues, jamais une fréquence — ce n'est pas
# un flux temps réel) ; le statut "active MAINTENANT" et la fréquence sont
# reconstruits ici à partir de ce qui existe déjà côté serveur :
#   1. le champ 'dates' ("Jul 7-Aug 4, 2026") comparé à la date du jour ;
#   2. si l'indicatif de l'expédition apparaît dans les spots cluster VIVANTS
#      déjà agrégés pour le reste de l'appli (_spots_from_caches() côté
#      logx_http.py) -> preuve directe d'activité, plus fiable qu'une simple
#      fenêtre de dates (les op's démarrent/arrêtent rarement pile aux
#      dates annoncées) : un spot repéré force le statut à 'active' même si
#      le calcul de dates dit 'upcoming' ou n'a pas pu être fait ('unknown').
_MOIS_EN = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
           'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}

# 'Jul 7-Aug 4, 2026' (mois différents) / 'Aug 3-9, 2026' (même mois) /
# 'Aug 5, 2026' (un seul jour) -- les 3 formes réellement vues dans le flux
# NG3K (vérifié sur adxo.xml, 04/08/2026). Un format inattendu (entrée mal
# formée, ça arrive) ne fait jamais planter l'appelant : voir _parse_date_range.
_DATE_RANGE_RE = re.compile(
    r'^(?P<m1>[A-Za-z]{3})\s+(?P<d1>\d{1,2})'
    r'(?:\s*-\s*(?:(?P<m2>[A-Za-z]{3})\s+)?(?P<d2>\d{1,2}))?'
    r',\s*(?P<y>\d{4})$'
)


def _parse_date_range(texte):
    """Renvoie (date_debut, date_fin) ou (None, None) si le texte ne
    correspond à aucun des formats connus du flux NG3K — jamais d'exception,
    une entrée mal formée devient simplement 'unknown' plutôt que de faire
    échouer tout l'endpoint."""
    m = _DATE_RANGE_RE.match((texte or '').strip())
    if not m:
        return None, None
    m1 = _MOIS_EN.get(m.group('m1')[:3].lower())
    if not m1:
        return None, None
    try:
        y = int(m.group('y'))
        debut = date(y, m1, int(m.group('d1')))
    except ValueError:
        return None, None
    if not m.group('d2'):
        return debut, debut
    m2_str = m.group('m2')
    m2 = _MOIS_EN.get(m2_str[:3].lower()) if m2_str else m1
    if not m2:
        return None, None
    try:
        d2 = int(m.group('d2'))
        # Franchissement d'année ("Dec 28-Jan 15, 2027") : l'année écrite
        # dans le flux se rapporte à la DERNIÈRE date du texte (la fin) —
        # la date de début recule donc d'un an quand son mois est APRÈS
        # celui de fin (déc > jan). Hypothèse documentée, jamais vérifiée
        # sur un cas réel faute d'exemple dans le flux au moment d'écrire
        # ceci — au pire, une expédition à cheval sur le nouvel an affiche
        # une fenêtre de dates décalée d'un an, sans jamais planter.
        if m2 < m1:
            fin = date(y, m2, d2)
            debut = date(y - 1, m1, debut.day)
        else:
            fin = date(y, m2, d2)
    except ValueError:
        return None, None
    return debut, fin


def _match_spot_freq(callsign, spots_by_band):
    """Cherche CET indicatif d'expédition dans les spots cluster vivants
    (dict {label_bande: [spots]}, voir logx_http._spots_from_caches — clés
    'dx'/'freq' en kHz, PAS 'call'/'freq' comme logx_clusters._normalize_spot :
    deux conventions différentes coexistent dans cette appli, à ne pas
    confondre). Renvoie (freq_khz, label_bande) du premier spot trouvé, ou
    (None, None). NG3K liste parfois un simple PRÉFIXE en attendant l'annonce
    de l'indicatif exact (ex. '4K' pour l'Azerbaïdjan) — dans ce cas la
    correspondance échoue silencieusement, ce qui est le comportement voulu
    (mieux vaut ne pas afficher de fréquence que d'en afficher une fausse)."""
    target = re.split(r'[,/ ]', (callsign or '').strip())[0].upper()
    if not target:
        return None, None
    for label, spots in (spots_by_band or {}).items():
        for sp in spots:
            if not isinstance(sp, dict):
                continue
            dx = str(sp.get('dx', '') or '').upper().split('/')[0]
            if dx == target:
                return sp.get('freq'), label
    return None, None


def fetch_dxpeditions_chasse(worked_entities=None, spots_by_band=None, today=None):
    """Comme fetch_dxpeditions(), pour le panneau CHASSE : chaque entrée
    reçoit en plus 'status' ('active'/'upcoming'/'unknown' — voir le
    commentaire au-dessus de _MOIS_EN) et, si trouvée en direct sur le
    cluster, 'freq_khz'/'spot_band'. Les expéditions déjà TERMINÉES sont
    retirées (CHASSE montre ce qu'on peut encore travailler, pas
    l'historique — voir fetch_dxpeditions()/l'onglet CALENDRIER pour la
    liste complète non filtrée).

    Tri (retour F4GLD 04/08/2026 : « si elle apparaît sur le cluster et que
    le contact n'a pas été fait, la proposer en priorité ») :
      0. active + repérée sur le cluster (freq_khz connu) + PAS encore
         travaillée (worked is False, DXCC jamais confirmé dans ce log) —
         c'est CE qu'on doit appeler maintenant, ça prime sur tout le reste ;
      1. active + repérée sur le cluster, mais déjà travaillée (ou pays non
         identifiable, worked is None) — sur l'air, mais rien à y gagner ;
      2. active selon les dates NG3K, mais pas (encore) vue sur le cluster ;
      3. à venir, triées par date de début croissante ;
      4. le reste ('unknown', dates illisibles)."""
    expeditions = fetch_dxpeditions(worked_entities)
    aujourdhui = today or _aujourdhui_utc()
    out = []
    for exp in expeditions:
        e = dict(exp)
        debut, fin = _parse_date_range(e.get('dates', ''))
        if debut and fin:
            if debut <= aujourdhui <= fin:
                e['status'] = 'active'
            elif aujourdhui < debut:
                e['status'] = 'upcoming'
            else:
                e['status'] = 'ended'
        else:
            e['status'] = 'unknown'
        e['starts'] = debut.isoformat() if debut else None
        e['ends'] = fin.isoformat() if fin else None
        e['freq_khz'] = None
        e['spot_band'] = None
        if e['status'] != 'ended':
            freq, band = _match_spot_freq(e.get('callsign', ''), spots_by_band)
            if freq:
                e['freq_khz'] = freq
                e['spot_band'] = band
                e['status'] = 'active'   # repéré sur le cluster = preuve directe, prime sur le calcul de dates
        if e['status'] != 'ended':
            out.append(e)

    def _cle_tri(e):
        actif_spotte = e['status'] == 'active' and e.get('freq_khz')
        if actif_spotte and e.get('worked') is False:
            rang = 0    # sur l'air MAINTENANT + jamais travaillé : à appeler en priorité
        elif actif_spotte:
            rang = 1    # sur l'air, mais déjà travaillé (ou pays non identifiable)
        elif e['status'] == 'active':
            rang = 2    # active selon les dates NG3K, pas encore vue sur le cluster
        elif e['status'] == 'upcoming':
            rang = 3
        else:
            rang = 4
        return (rang, e.get('starts') or '9999-99-99')

    out.sort(key=_cle_tri)
    return out


def _aujourdhui_utc():
    from logx_utils import utcnow  # import local : mockable par les tests
    return utcnow().date()
