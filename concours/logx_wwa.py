# -*- coding: utf-8 -*-
"""World Wide Award (WWA) — roster public des stations spéciales à contacter
(hamaward.cloud, plateforme tierce indépendante de LogX AI).

Le WWA n'est PAS un concours classique : les « hunters » ne marquent des
points qu'en contactant l'une des stations spéciales inscrites pour l'édition
en cours (ex. II1WWA, DA0WWA...) — tout le reste de l'échange se limite au
report signal (RS/RST), sans numéro de série ni multiplicateur géographique
(voir https://hamaward.cloud/wwa/rules, section 3 et 6).

Ce module ne fait QUE lire la liste publique des équipes/stations spéciales
(page /wwa/teams, aucune authentification, aucune donnée personnelle) pour
que le moteur de scoring (logx_scoring.py) sache reconnaître un spot cluster
comme cible valable. Il n'existe AUCUNE API JSON documentée pour cette page
(vérifié : zéro appel XHR au chargement) — on parcourt donc le HTML public,
comme pour les annonces WWA/WCA (logx_wca.py). Structure vérifiée en direct
le 22/07/2026 (94 équipes, 94/94/94 blocs callsign/pays/opérateurs cohérents),
tolérante à un léger changement de mise en forme (regex sur les propriétés
CSS distinctives, pas sur le HTML complet).

IMPORTANT — ce que LogX AI NE fait PAS : il n'existe aucune intégration de
soumission vers hamaward.cloud (aucune API publique documentée pour ça). Le
score affiché ici est une ESTIMATION LOCALE pour prioriser vos contacts ;
le classement officiel reste calculé par la plateforme WWA elle-même.
"""
import re
import time
import datetime

from logx_utils import fetch_url

TEAMS_URL = 'https://hamaward.cloud/wwa/teams'
CACHE_TTL = 6 * 3600  # 6h : le roster grandit au fil des inscriptions, pas seconde par seconde

# Concours LogX AI -> code d'édition hamaward.cloud (paramètre ?sub_menu=).
# Explicite plutôt que déduit de la date du jour : le concours choisi par
# l'opérateur dans CONFIG fait foi, pas une heuristique de calendrier fragile.
CONTEST_ID_TO_EDITION = {
    'WWA_2027_JAN': 'w27',   # WWA janvier 2027 (1er - 31 janvier)
    'WWA_2027_JUL': 's27',   # WWA Sprint juillet 2027 (28 juin - 4 juillet)
}

_cache = {}  # edition_code -> {'ts': float, 'roster': {indicatif: pays}}


_CALL_RE = re.compile(r'font-weight:bold;?">([^<]*)</div>')
_COUNTRY_RE = re.compile(r'font-size:14px;padding-top:2px;color:#ffffff">([^<]*)</div>')


def _parse_teams_html(html):
    """HTML public (aucune API JSON documentée) -> {indicatif: pays}. Repose
    sur 2 propriétés CSS distinctives plutôt qu'une structure DOM complète —
    tolère mieux un changement de mise en page mineur qu'un parseur strict.
    Les deux listes doivent être alignées (même ordre d'apparition) ; en cas
    de décompte différent (mise en page modifiée côté hamaward.cloud), on
    tronque au plus court plutôt que de planter."""
    calls = _CALL_RE.findall(html or '')
    countries = _COUNTRY_RE.findall(html or '')
    n = min(len(calls), len(countries))
    roster = {}
    for i in range(n):
        call = calls[i].strip().upper()
        country = countries[i].strip()
        if call:
            roster[call] = country
    return roster


def get_roster(edition_code, force_refresh=False):
    """Roster {indicatif spécial: pays} pour ce code d'édition. Dégradation
    propre : jamais d'exception — renvoie {} si injoignable sans cache, ou
    le cache existant même expiré plutôt que de bloquer le scoring."""
    if not edition_code:
        return {}
    entry = _cache.get(edition_code)
    if not force_refresh and entry and (time.time() - entry['ts']) < CACHE_TTL:
        return entry['roster']
    html = fetch_url(f'{TEAMS_URL}?sub_menu={edition_code}', timeout=10)
    if not html:
        return entry['roster'] if entry else {}   # repli sur le cache périmé si le réseau échoue
    roster = _parse_teams_html(html)
    if roster or not entry:
        _cache[edition_code] = {'ts': time.time(), 'roster': roster}
        return roster
    return entry['roster']   # page vide/inchangée : garder le dernier roster non-vide connu


def roster_for_contest(contest_id):
    """Roster du concours LogX AI donné (via CONTEST_ID_TO_EDITION), ou {} si
    ce n'est pas un concours WWA connu."""
    code = CONTEST_ID_TO_EDITION.get(contest_id)
    return get_roster(code) if code else {}


def is_wwa_station(callsign, contest_id):
    """La station (indicatif de base, sans /P /QRP...) est-elle une station
    spéciale WWA inscrite pour ce concours ?"""
    base = (callsign or '').split('/')[0].upper()
    if not base:
        return False
    return base in roster_for_contest(contest_id)


def station_country(callsign, contest_id):
    """Pays déclaré pour cette station spéciale WWA, ou '' si inconnue."""
    base = (callsign or '').split('/')[0].upper()
    return roster_for_contest(contest_id).get(base, '')
