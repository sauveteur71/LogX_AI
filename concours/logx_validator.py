# -*- coding: utf-8 -*-
"""Validateur de log AVANT soumission — spécial concours REF.

Passe le log du concours actif au crible et retourne des constats classés :
  erreur     : coûtera des points ou invalidera le QSO (à corriger)
  attention  : suspect, à vérifier (busted call probable, distance anormale)
  info       : mineur (RST manquant…)

Contrôles :
  - doublons (même indicatif + même bande — règle REF : 1 QSO/station/bande)
  - indicatif plausible (motif + préfixe connu de cty.dat)
  - concours à LOCATOR (THF, km × locators) : locator présent et valide,
    distance plausible pour la bande (tropo/Es rares au-delà des seuils)
  - concours à DÉPARTEMENT (REF HF) : département reçu valide pour les
    stations françaises, numéro de série pour les étrangères
  - QSO hors de la fenêtre du concours
  - bande hors concours, champs essentiels vides

Aucune écriture : lecture seule, appelable à tout moment.
"""
import re

from logx_utils import locator_to_latlon, haversine

# Indicatif de BASE : préfixe 1-3 alphanum + un chiffre + suffixe lettres.
_BASE_CALL_RE = re.compile(r'^[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,5}[A-Z]$')
# Préfixe de LIEU d'un indicatif portable (EA/, F/, 9A/, PJ2/, VP2E/…).
_PREFIX_RE = re.compile(r'^[A-Z0-9]{1,4}$')
# Suffixe portable (/P /M /MM /AM /QRP /A /LH ou /chiffre(s)).
_PORT_SUFFIX_RE = re.compile(r'^(P|M|MM|AM|QRP|A|LH|[0-9]{1,2})$')
LOC_RE = re.compile(r'^[A-R]{2}[0-9]{2}([A-X]{2}([0-9]{2})?)?$')


def _plausible_call(call):
    """Indicatif plausible, y compris PORTABLE avec préfixe de lieu
    (EA/F4GLD = F4GLD opérant depuis l'Espagne), suffixe (F4GLD/P, W1AW/4)
    ou les deux (EA/F4GLD/P). L'ancien motif n'acceptait qu'un suffixe et
    signalait à tort tout indicatif à préfixe étranger comme « busted call »."""
    parts = [p for p in str(call).split('/') if p]
    if not parts:
        return False
    if len(parts) == 1:
        return bool(_BASE_CALL_RE.match(parts[0]))
    # Au moins une partie doit être un indicatif complet ; les autres sont des
    # préfixes de lieu ou des suffixes portables.
    if not any(_BASE_CALL_RE.match(p) for p in parts):
        return False
    return all(_BASE_CALL_RE.match(p) or _PREFIX_RE.match(p) or _PORT_SUFFIX_RE.match(p)
               for p in parts)

# Distance au-delà de laquelle un QSO est SUSPECT sur la bande (km).
# Tropo/Es exceptionnels possibles — c'est un signal « à vérifier », pas un rejet.
MAX_KM_BY_BAND = {
    '50': 2500, '70': 1800, '144': 1400, '432': 1000,
    '1296': 800, '2320': 600, '3400': 500, '5760': 400, '10368': 300,
}
MAX_FINDINGS = 200


def _f(findings, level, code, msg, q=None, index=None):
    if len(findings) >= MAX_FINDINGS:
        return
    item = {'level': level, 'code': code, 'msg': msg}
    if q is not None:
        item['call'] = str(q.get('call', '')).upper()
        item['band'] = str(q.get('band', ''))
        item['at'] = f"{q.get('date', '')} {q.get('time', '')}".strip()
        # id du QSO : permet à l'interface d'offrir « Corriger »/« Supprimer »
        # directement sur le constat.
        if q.get('id') is not None:
            item['id'] = q.get('id')
    if index is not None:
        item['index'] = index
    findings.append(item)


def _loc_latlon(loc):
    """lat/lon d'un locator 4 ou 6 caractères (centre du carré en 4)."""
    loc = str(loc or '').strip().upper()
    if len(loc) == 4:
        loc += 'MM'
    lat, lon = locator_to_latlon(loc[:6])
    return lat, lon


def validate_log(qsos, contest_id='', cfg=None):
    """Analyse le log d'un concours. Retourne
    {contest, qso_count, findings[], counts{}, ok}."""
    cfg = cfg or {}
    # LOGBOOK SIMPLE : aucun concours actif — les contraintes propres à UN
    # concours (bandes autorisées, échange locator/département obligatoire,
    # fenêtre temporelle) n'ont pas de sens et ne doivent pas s'appliquer,
    # même si `contest` garde la trace d'un concours précédent en config.
    simple_mode = cfg.get('usage_mode') == 'simple'
    if simple_mode:
        contest_id = ''
    # Portée QSO (contest+année, voir logx_storage.cfg_scope_id), dérivée de
    # `cfg` plutôt que du seul `contest_id` brut — sans elle un QSO non tagué
    # (import générique, log perso) passait le filtre de N'IMPORTE QUEL
    # concours vérifié, et un même concours d'une année précédente non purgée
    # s'y mélangeait aussi.
    from logx_storage import qso_scope_id, cfg_scope_id
    scope_id = cfg_scope_id(cfg)
    qsos = [q for q in (qsos or [])
            if not scope_id or qso_scope_id(q) == scope_id]

    from logx_definitions import CONTEST_DEFINITIONS
    cdef = CONTEST_DEFINITIONS.get(contest_id, {}) if contest_id else {}
    from logx_callhistory import exchange_wants
    wants = exchange_wants(cdef)
    bands_ok = {str(b) for b in cdef.get('bands', [])}

    try:
        import logx_dxcc as dxcc
    except Exception:
        dxcc = None
    try:
        from logx_departments import dept_from_exchange
    except Exception:
        dept_from_exchange = None

    # Fenêtre du concours (mêmes sources que le coach) — non pertinente en
    # logbook simple, même si des dates de concours précédent traînent en config.
    start = end = None
    if not simple_mode:
        from logx_coach import _parse_dt
        start = _parse_dt(cfg.get('contest_start_date', ''), cdef.get('start_utc', ''))
        end = _parse_dt(cfg.get('contest_end_date', ''), cfg.get('contest_end_utc', ''))
        if start and end and end <= start:
            import datetime
            end += datetime.timedelta(days=1)

    my_lat, my_lon = _loc_latlon(cfg.get('locator', ''))

    findings = []
    seen = {}   # (call, band) -> premier index

    for i, q in enumerate(qsos):
        call = str(q.get('call', '')).strip().upper()
        band = str(q.get('band', '')).strip()

        # Champs essentiels
        if not call:
            _f(findings, 'erreur', 'indicatif_vide',
               "QSO sans indicatif", q, i)
            continue

        # Doublon même station + même bande (règle REF : 1 QSO/station/bande
        # PENDANT le concours) — n'a pas de sens en logbook simple, où l'on
        # recontacte normalement la même station sur la même bande au fil
        # des années.
        if not simple_mode:
            key = (call, band)
            if key in seen:
                _f(findings, 'erreur', 'doublon',
                   f"{call} déjà travaillé sur {band} MHz (QSO n°{seen[key] + 1}) — 0 point",
                   q, i)
            else:
                seen[key] = i

        # Indicatif plausible (préfixe/suffixe portable inclus) + préfixe connu
        if not _plausible_call(call):
            _f(findings, 'attention', 'indicatif_suspect',
               f"{call} : format inhabituel — busted call probable", q, i)
        country = None
        if dxcc:
            # Indicatif COMPLET passé à lookup() : sa gestion des « / » choisit
            # le bon pays d'émission (EA/F4GLD → Espagne, pas France).
            info = dxcc.lookup(call)
            if not info:
                _f(findings, 'attention', 'prefixe_inconnu',
                   f"{call} : préfixe inconnu de cty.dat — vérifie l'indicatif", q, i)
            else:
                country = info.get('country')

        # Bande dans le concours
        if bands_ok and band and band not in bands_ok:
            _f(findings, 'attention', 'bande_hors_concours',
               f"{band} MHz n'est pas une bande de ce concours", q, i)

        # Échange à LOCATOR (THF : pas de locator = pas de km = pas de points)
        if wants.get('locator'):
            loc = str(q.get('locator', '')).strip().upper()
            if not loc:
                _f(findings, 'erreur', 'locator_manquant',
                   f"{call} : locator absent — le QSO ne rapportera aucun km", q, i)
            elif not LOC_RE.match(loc):
                _f(findings, 'erreur', 'locator_invalide',
                   f"{call} : locator « {loc} » invalide", q, i)
            elif my_lat is not None:
                lat, lon = _loc_latlon(loc)
                if lat is not None:
                    km = haversine(my_lat, my_lon, lat, lon)
                    limit = MAX_KM_BY_BAND.get(band)
                    if limit and km > limit:
                        _f(findings, 'attention', 'distance_suspecte',
                           f"{call} : {km} km sur {band} MHz — exceptionnel "
                           f"(> {limit} km), vérifie le locator", q, i)

        # Échange à DÉPARTEMENT (REF HF)
        if wants.get('dept'):
            exch = str(q.get('num_rcvd', '')).strip()
            if country in ('France', 'Corsica'):
                dept = dept_from_exchange(exch) if dept_from_exchange else None
                if not dept:
                    _f(findings, 'erreur', 'dept_invalide',
                       f"{call} : département reçu « {exch or '—'} » invalide "
                       f"(station française)", q, i)
            elif country and not re.search(r'\d', exch):
                _f(findings, 'info', 'serie_manquante',
                   f"{call} : numéro de série reçu vide (station étrangère)", q, i)

        # Fenêtre temporelle
        if start and end:
            dt = _parse_dt(q.get('date', ''), q.get('time', ''))
            if dt and not (start <= dt < end):
                _f(findings, 'erreur', 'hors_fenetre',
                   f"{call} : QSO hors de la fenêtre du concours "
                   f"({dt.strftime('%d/%m %H:%M')})", q, i)

        # RST manquant
        if not str(q.get('rst_rcvd', q.get('rst_recu', ''))).strip():
            _f(findings, 'info', 'rst_manquant',
               f"{call} : RST reçu vide", q, i)

    order = {'erreur': 0, 'attention': 1, 'info': 2}
    findings.sort(key=lambda x: order.get(x['level'], 3))
    counts = {'erreur': 0, 'attention': 0, 'info': 0}
    for x in findings:
        counts[x['level']] = counts.get(x['level'], 0) + 1
    return {
        'contest': contest_id,
        'qso_count': len(qsos),
        'findings': findings,
        'counts': counts,
        'ok': counts['erreur'] == 0,
        'truncated': len(findings) >= MAX_FINDINGS,
    }
