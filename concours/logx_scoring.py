# -*- coding: utf-8 -*-
"""Moteur de score : valeur d'un QSO selon le concours, classement des stations, contexte de scoring pour l'IA."""

import re

from logx_definitions import CONTEST_DEFINITIONS
from logx_utils import locator_to_latlon, haversine, bearing, cardinal
from logx_storage import shared_log

# ─── MOTEUR DE SCORING UNIVERSEL ─────────────────────────────────────────────
# Calcule la valeur réelle en points d'un contact selon le règlement actif

# Pays / continent / zones : base DXCC hors ligne cty.dat (AD1C) — la même
# référence que N1MM/DXLog. Remplace l'ancienne table de ~50 préfixes qui
# approximait le pays par 2 caractères et défaillait en 'EU' par défaut.
import logx_dxcc as dxcc


def get_continent(callsign):
    """Retourne le continent d'un indicatif (base cty.dat, repli 'EU')."""
    return dxcc.continent(callsign, default='EU')

def get_large_locator(locator):
    """Retourne le grand carré (4 premiers caractères) d'un locator"""
    if locator and len(locator) >= 4:
        return locator[:4].upper()
    return None

def get_propagation_boost(dist_km, band_norm, noaa, dxmaps):
    """
    Renvoie (delta_priorite, note) si une propagation VHF confirmée
    (Sporadique-E, Tropo renforcé, Aurore) rend ce contact plus atteignable
    que la distance seule ne le suggère. delta négatif = priorité améliorée
    (1 = meilleure priorité possible dans ce moteur).
    """
    if band_norm not in ('144', '432', '50'):
        return 0, ''
    if dxmaps and dxmaps.get('es_active') and 700 <= dist_km <= 2000:
        return -1, "🌟 Sporadique-E signalé quelque part en Europe (DXMaps) — pas de garantie sur ce trajet précis, à tenter"
    if dxmaps and dxmaps.get('tropo_active') and 300 <= dist_km <= 1200:
        return -1, "🌊 Ouverture tropo signalée (DXMaps) — indicateur régional, pas spécifique à ce trajet"
    if noaa and noaa.get('aurora_possible') and dist_km >= 500:
        return -1, "⚡ Aurore possible (K-index NOAA élevé) — signal flutter probable si ouverture"
    return 0, ''

# ═══════════════════════════════════════════════════════════════════════════
#  MOTEUR À BRIQUES COMPOSABLES (Phase 2)
#
#  Un scoring se décrit par des briques déclaratives (JSON-compatibles) :
#    points     : liste ordonnée de règles {'when': <prédicat>, 'points': <val>}
#                 — la première règle qui matche donne les points du QSO.
#                 <val> = nombre | 'per_km' | {'param': clé_scoring, 'default': n}
#    multiplier : {'kind': <famille>} — détection de nouveau multiplicateur
#                 et estimation de l'impact (familles dans MULT_EVALUATORS)
#    validity   : prédicat optionnel — station hors périmètre = 0 pt (ex. FD : NA only)
#    + options : same_square_points, priority_thresholds, propagation_boost...
#
#  Un concours jamais vu se décrit en assemblant ces briques dans sa définition
#  ('scoring': {'bricks': {...}}) sans coder de nouvelle branche. Les types
#  historiques ('type': 'km', ...) sont convertis via LEGACY_SCORING_PRESETS.
# ═══════════════════════════════════════════════════════════════════════════

# Indicatifs nord-américains (W/K/N/VE...) — utilisé par Field Day et ARRL DX
_NA_CALL_RE = re.compile(
    r'^(W|K|N|AA|AB|AC|AD|AE|AF|AG|AH|AI|AJ|AK|'
    r'WA|WB|WC|WD|WE|WF|WG|WH|WI|WJ|WK|WL|WM|WN|WO|WP|'
    r'WQ|WR|WS|WT|WU|WV|WW|WX|WY|WZ|'
    r'KA|KB|KC|KD|KE|KF|KG|KH|KI|KJ|KK|KL|KM|KN|KO|KP|'
    r'KQ|KR|KS|KT|KU|KV|KW|KX|KY|KZ|'
    r'NA|NB|NC|ND|NE|NF|NG|NH|NI|NJ|NK|NL|NM|NN|NO|NP|'
    r'NQ|NR|NS|NT|NU|NV|NW|NX|NY|NZ|'
    r'VE|VA|VO|VY)', re.I)

# ── Prédicats nommés (référencés par les briques 'when' / 'validity') ────────
PREDICATES = {
    'always':              lambda c: True,
    'same_country':        lambda c: c['dx_country'] == c['my_country'],
    'same_continent':      lambda c: c['dx_cont'] == c['my_cont'],
    'different_continent': lambda c: c['dx_cont'] != c['my_cont'],
    'is_french':           lambda c: c['dx_base'].startswith('F') or c['dx_base'].startswith('TM'),
    'is_na':               lambda c: bool(_NA_CALL_RE.match(c['dx_base'])),
    'na_w_ve':             lambda c: c['dx_base'].startswith(('W', 'K', 'N', 'VE', 'XE')),
    'is_asia':             lambda c: c['dx_cont'] == 'AS',   # All Asian DX...
    'is_eu':               lambda c: c['dx_cont'] == 'EU',
}

def _check_validity(validity, ctx):
    """Brique validité : prédicat nommé OU {'prefix_in': ['SP','SQ',...]}
    (concours où seuls les contacts avec un pays organisateur comptent)."""
    if isinstance(validity, dict) and 'prefix_in' in validity:
        return ctx['dx_base'].startswith(tuple(validity['prefix_in']))
    return PREDICATES.get(validity, PREDICATES['always'])(ctx)

def _points_value(rule, ctx, scoring):
    """Résout la valeur de points d'une règle : nombre, 'per_km', ou paramètre."""
    v = rule.get('points', 0)
    if isinstance(v, dict):
        v = scoring.get(v.get('param'), v.get('default', 0))
    if v == 'per_km':
        return ctx['dist_km']
    return v

def _eval_points(rules, ctx, scoring):
    """Première règle dont le prédicat matche → points du QSO.
    Filtres optionnels par règle :
      'bands': ['1.8','3.5','7'] — ex. CQ WPX : points doublés bandes basses ;
      'prefix_in': ['ON','OO'] — ex. UBA : 10 pts pour une station belge ;
      'modes': ['CW'] — ex. ARRL 10m : CW=4 pts. Une règle filtrée par mode est
      SAUTÉE quand le mode est inconnu (spots cluster) : mettre la valeur
      plancher dans la règle suivante sans filtre."""
    for rule in rules or []:
        bands = rule.get('bands')
        if bands and ctx['band_norm'] not in bands:
            continue
        prefixes = rule.get('prefix_in')
        if prefixes and not ctx['dx_base'].startswith(tuple(prefixes)):
            continue
        modes = rule.get('modes')
        if modes and (ctx.get('mode') or '').upper() not in [m.upper() for m in modes]:
            continue
        pred = PREDICATES.get(rule.get('when', 'always'), PREDICATES['always'])
        if pred(ctx):
            return _points_value(rule, ctx, scoring)
    return 0

def _max_rule_points(rules, ctx, scoring):
    """Meilleurs points possibles parmi les règles (sert aux seuils de priorité)."""
    best = 0
    for rule in rules or []:
        v = _points_value(rule, ctx, scoring)
        if isinstance(v, (int, float)) and v > best:
            best = v
    return best

# ── Détecteurs de multiplicateur, par famille ────────────────────────────────
# Chaque détecteur remplit result (new_mult, impact, priority, explanation)
# à partir des points déjà calculés — textes et formules identiques au moteur
# historique pour les types migrés.

def _mult_locator(ctx, pts, result, scoring):
    new_loc = ctx['dx_locator'] and ctx['dx_locator'] not in ctx['done_locators']
    if new_loc:
        result['new_mult'] = True
        result['mult_type'] = 'locator'
        result['mult_value'] = 1
        # Impact = score_actuel entier car multiplicateur +1
        result['total_impact'] = pts + ctx['current_score_total']
        result['explanation'] = f"{ctx['dist_km']} km + NOUVEAU locator {ctx['dx_locator']} → score×(mult+1)"
        result['priority'] = 1
    else:
        result['total_impact'] = pts
        result['explanation'] = f"{ctx['dist_km']} km (locator déjà connu)"
        result['priority'] = 2 if ctx['dist_km'] > 500 else 3

def _mult_large_square(ctx, pts, result, scoring):
    large_sq = get_large_locator(ctx['dx_locator'])
    new_sq = large_sq and large_sq not in ctx['done_large_squares']
    if new_sq:
        result['new_mult'] = True
        result['mult_type'] = 'grand_carre'
        result['mult_value'] = 1
        nb_sq = len(ctx['done_large_squares'])
        # Score_actuel × (nb_sq+1)/(nb_sq) = gain estimé
        gain = ctx['current_score_total'] // max(nb_sq, 1) if nb_sq > 0 else ctx['dist_km'] * 5
        result['total_impact'] = pts + gain
        result['explanation'] = f"{ctx['dist_km']} km + NOUVEAU carré {large_sq} → mult {nb_sq}→{nb_sq+1}"
        result['priority'] = 1
    else:
        result['total_impact'] = pts
        result['explanation'] = f"{ctx['dist_km']} km (carré {large_sq} déjà compté)"
        result['priority'] = 2 if ctx['dist_km'] > 400 else 3

def _mult_zone_dxcc(ctx, pts, result, scoring):
    nb_mults = len(ctx['done_cq_zones']) + len(ctx['done_dxcc'])
    # Zone CQ réelle depuis la base cty.dat (le bug historique comparait
    # l'INDICATIF au set des zones — toujours vrai). None si indicatif inconnu.
    dx_zone = ctx.get('dx_cq_zone')
    new_zone = dx_zone is not None and str(dx_zone) not in ctx['done_cq_zones']
    new_dxcc = (ctx['dx_country'] not in ctx['done_dxcc'])
    if new_zone or new_dxcc:
        result['new_mult'] = True
        result['mult_type'] = 'zone_cq' if new_zone else 'dxcc'
        result['mult_value'] = 1
        # Impact = score_actuel / nb_mults (valeur d'un mult)
        mult_value_est = ctx['current_score_total'] // max(nb_mults, 1)
        result['total_impact'] = pts + mult_value_est
        label = 'NOUVELLE ZONE CQ' if new_zone else 'NOUVEAU DXCC'
        result['explanation'] = (
            f"{pts}pts ({ctx['my_cont']}→{ctx['dx_cont']}) + "
            f"{label} → +{mult_value_est}pts estimés"
        )
        result['priority'] = 1 if pts == 3 else 2
    else:
        result['total_impact'] = pts
        result['explanation'] = f"{pts}pts ({ctx['my_cont']}→{ctx['dx_cont']}), pas de nouveau mult"
        result['priority'] = 2 if pts == 3 else 3 if pts == 1 else 5

def _mult_prefix(ctx, pts, result, scoring):
    # Extraire préfixe du DX (ex. F6, DL1, ON4) — suivi via done_dxcc (proxy)
    pfx_match = re.match(r'^([A-Z]{1,3}\d)', ctx['dx_base'])
    dx_pfx = pfx_match.group(1) if pfx_match else ctx['dx_base'][:3]
    new_pfx = dx_pfx not in ctx['done_dxcc']
    if new_pfx:
        result['new_mult'] = True
        result['mult_type'] = 'prefix'
        result['mult_value'] = 1
        mult_val = (ctx['current_score_total'] // max(len(ctx['done_dxcc']), 1)
                    if ctx['done_dxcc'] else pts * 10)
        result['total_impact'] = pts + mult_val
        result['explanation'] = f"{pts}pts + NOUVEAU PRÉFIXE {dx_pfx} → +{mult_val}pts estimés"
        result['priority'] = 1
    else:
        result['total_impact'] = pts
        result['explanation'] = f"{pts}pts (préfixe {dx_pfx} déjà compté)"
        # Priorité 2 si le QSO vaut le maximum du barème (ex. continent différent)
        best = _max_rule_points(ctx.get('bricks', {}).get('points'), ctx, scoring)
        result['priority'] = 2 if pts == best and best > 0 else 3

def _mult_dept_dxcc(ctx, pts, result, scoring):
    is_french = PREDICATES['is_french'](ctx)
    new_mult = ctx['dx_country'] not in ctx['done_dxcc']
    if new_mult:
        result['new_mult'] = True
        result['mult_type'] = 'dept_dxcc'
        mult_val = (ctx['current_score_total'] // max(len(ctx['done_dxcc']), 1)
                    if ctx['done_dxcc'] else pts * 5)
        result['total_impact'] = pts + mult_val
        result['explanation'] = f"{pts}pts + NOUVEAU {'DEPT' if is_french else 'DXCC'} → +{mult_val}pts estimés"
        result['priority'] = 1
    else:
        result['total_impact'] = pts
        result['explanation'] = f"{pts}pts ({'F' if is_french else 'DX'}, mult connu)"
        result['priority'] = 3

def _mult_na_section(ctx, pts, result, scoring):
    # Sections/états nord-américains — suivi via done_dxcc (proxy 3 caractères)
    section_new = ctx['dx_base'][:3] not in ctx['done_dxcc']
    label = scoring.get('_section_label', 'SSB')
    if section_new:
        result['new_mult'] = True
        result['mult_type'] = 'section_na'
        result['mult_value'] = 1
        result['total_impact'] = pts * 2  # 1pt × mult ×2 puissance = 2 pts/QSO max
        result['explanation'] = f"{pts}pt {label} × mult (NA valide W/VE)"
        result['priority'] = 1
    else:
        result['total_impact'] = pts
        result['explanation'] = f"{pts}pt {label}, section déjà travaillée"
        result['priority'] = 2

def _mult_na_state(ctx, pts, result, scoring):
    # ARRL DX vu depuis l'Europe : multiplicateur = états US + provinces VE.
    # L'état exact vient de l'échange (inconnu au stade du spot) → proxy préfixe.
    state_new = ctx['dx_base'][:3] not in ctx['done_dxcc']
    if state_new:
        result['new_mult'] = True
        result['mult_type'] = 'etat_province'
        result['mult_value'] = 1
        mult_val = (ctx['current_score_total'] // max(len(ctx['done_dxcc']), 1)
                    if ctx['done_dxcc'] else pts * 5)
        result['total_impact'] = pts + mult_val
        result['explanation'] = f"{pts}pts + probable NOUVEL ÉTAT/PROVINCE → +{mult_val}pts estimés"
        result['priority'] = 1
    else:
        result['total_impact'] = pts
        result['explanation'] = f"{pts}pts (état/province probablement déjà travaillé)"
        result['priority'] = 3

def _mult_exchange_distinct(ctx, pts, result, scoring):
    """Multiplicateur = valeurs d'ÉCHANGE distinctes reçues par bande (EUHFC :
    année de 1re licence). Par nature INCONNAISSABLE avant le QSO : au spot,
    aucun faux « nouveau mult » — le décompte exact se fait sur le log
    (coach.exchange_mult_stats)."""
    result['total_impact'] = pts
    result['explanation'] = (f"{pts}pts — mult = échange reçu (inconnu avant le QSO), "
                             f"décompte exact sur le log")
    result['priority'] = 3 if pts else 5


MULT_EVALUATORS = {
    'locator':      _mult_locator,
    'large_square': _mult_large_square,
    'zone_dxcc':    _mult_zone_dxcc,
    'prefix':       _mult_prefix,
    'dept_dxcc':    _mult_dept_dxcc,
    'na_section':   _mult_na_section,
    'na_state':     _mult_na_state,
    'exchange_distinct': _mult_exchange_distinct,
}

# ── Conversion des types historiques en compositions de briques ─────────────
# Chaque preset reproduit EXACTEMENT le comportement de l'ancienne branche
# if/elif correspondante (priorités, formules d'impact, textes d'explication).
LEGACY_SCORING_PRESETS = {
    # 1pt/km (REF RPH) — pas de multiplicateur, priorité par paliers de distance
    'km': {
        'points': [{'when': 'always', 'points': 'per_km'}],
        'multiplier': None,
        'priority_thresholds': [[1000, 1], [500, 2], [200, 3]],
        'priority_default': 4,
        'explain_direct': '{dist_km} km = {pts} pts directs',
        'propagation_boost': True,
        'on4kst_priority_cap': True,
    },
    # km × locators (REF THF)
    'km_x_locators': {
        'points': [{'when': 'always', 'points': 'per_km'}],
        'multiplier': {'kind': 'locator'},
        'propagation_boost': True,
    },
    # km × grands carrés (IARU VHF/UHF) — QSO même grand carré = points fixes
    'km_x_large_locator_squares': {
        'points': [{'when': 'always', 'points': 'per_km'}],
        'multiplier': {'kind': 'large_square'},
        'same_square_points': {'param': 'same_square_bonus', 'default': 50},
        'propagation_boost': True,
    },
    # pts × (zones CQ + DXCC) par bande (CQ WW)
    'zone_country_per_band': {
        'points': [
            {'when': 'same_country',   'points': {'param': 'points_same_country',   'default': 0}},
            {'when': 'same_continent', 'points': {'param': 'points_same_continent', 'default': 1}},
            {'when': 'always',         'points': {'param': 'points_dx',             'default': 3}},
        ],
        'multiplier': {'kind': 'zone_dxcc'},
    },
    # pts × préfixes uniques (CQ WPX) — les définitions déclarent 3/1/1
    'prefix_multiplier': {
        'points': [
            {'when': 'different_continent', 'points': {'param': 'points_dx',             'default': 3}},
            {'when': 'same_country',        'points': {'param': 'points_same_country',   'default': 1}},
            {'when': 'always',              'points': {'param': 'points_same_continent', 'default': 1}},
        ],
        'multiplier': {'kind': 'prefix'},
    },
    # Ancien type 'prefix' (barème WPX bas de bande 6/2/1) — conservé par compat
    'prefix': {
        'points': [
            {'when': 'different_continent', 'points': 6},
            {'when': 'na_w_ve',             'points': 2},
            {'when': 'always',              'points': 1},
        ],
        'multiplier': {'kind': 'prefix'},
    },
    # ARRL DX depuis l'Europe : 3 pts par QSO W/VE, mult = états/provinces
    'power_state': {
        'points': [{'when': 'always', 'points': {'param': 'points', 'default': 3}}],
        'validity': 'is_na',
        'validity_fail_explanation': 'Station {dx_base} hors W/VE — 0 pt ARRL DX',
        'multiplier': {'kind': 'na_state'},
    },
    # ARRL Field Day : 1pt SSB (plancher), sections NA uniquement
    'fd_class': {
        'points': [{'when': 'always', 'points': {'param': 'points_phone', 'default': 1}}],
        'validity': 'is_na',
        'validity_fail_explanation': 'Station {dx_base} hors NA — 0 pt ARRL FD',
        'multiplier': {'kind': 'na_section'},
    },
    # pts × (depts + DXCC) (REF HF) : F=1pt, DX=3pts
    'dept_dxcc': {
        'points': [
            {'when': 'is_french', 'points': 1},
            {'when': 'always',    'points': 3},
        ],
        'multiplier': {'kind': 'dept_dxcc'},
    },
    # SOTA : points selon le sommet (inconnus au stade du spot)
    'summit_points': {
        'points': [{'when': 'always', 'points': {'param': 'points', 'default': 1}}],
        'multiplier': None,
        'priority_default': 3,
        'explain_direct': 'Activation SOTA — points selon altitude du sommet ({pts} pt de base)',
    },
    # POTA : 1 pt par parc
    'park_points': {
        'points': [{'when': 'always', 'points': {'param': 'points', 'default': 1}}],
        'multiplier': None,
        'priority_default': 3,
        'explain_direct': 'Activation POTA — {pts} pt par parc',
    },
}

def resolve_scoring_bricks(scoring):
    """Retourne les briques d'un bloc scoring : déclaration explicite
    ('bricks') prioritaire, sinon conversion du type historique."""
    if isinstance(scoring.get('bricks'), dict):
        return scoring['bricks']
    return LEGACY_SCORING_PRESETS.get(scoring.get('type', 'km'),
                                      LEGACY_SCORING_PRESETS['km'])


def contest_geo_mode(contest_id):
    """Type de « chasse aux multiplicateurs géographiques » d'un concours, pour
    décider si l'onglet montre les DÉPARTEMENTS (FR) ou les PAYS (DXCC) :
      'dept'      -> départements FR (concours VHF/km français)
      'dept_dxcc' -> départements FR + pays DXCC (REF HF, 160m)
      'dxcc'      -> pays DXCC (concours internationaux : CQ WW, WPX, ARRL DX...)
      'other'     -> ni dept ni pays (états US, sections...) -> repli dept
    Lit le multiplicateur effectif (briques explicites OU preset legacy), en
    gérant les DEUX emplacements de classification."""
    cdef = CONTEST_DEFINITIONS.get(contest_id, {})
    bricks = resolve_scoring_bricks(cdef.get('scoring', {}))
    mult = (bricks or {}).get('multiplier') or {}
    kind = mult.get('kind', '') if isinstance(mult, dict) else ''
    if kind == 'dept_dxcc':
        return 'dept_dxcc'
    if kind in ('zone_dxcc', 'prefix'):
        return 'dxcc'
    if kind in ('na_state', 'na_section'):
        return 'other'
    # locator, large_square, exchange_distinct, None -> français par défaut
    return 'dept'

def calc_qso_value(contest_id, dx_call, dx_locator, my_call, my_locator,
                   done_calls_by_band, done_locators, done_large_squares,
                   done_cq_zones, done_dxcc, current_score_total,
                   band=None, dist_km=0, noaa=None, dxmaps=None, source='',
                   mode=''):
    """
    Calcule la VALEUR RÉELLE d'un QSO selon le règlement du concours.
    Retourne un dict avec points directs, impact multiplicateur, valeur totale estimée.
    """
    cdef = CONTEST_DEFINITIONS.get(contest_id, {})
    scoring = cdef.get('scoring', {})
    bricks = resolve_scoring_bricks(scoring)

    result = {
        'direct_pts': 0,
        'new_mult': False,
        'mult_type': '',
        'mult_value': 0,
        'total_impact': 0,
        'priority': 5,
        'explanation': '',
    }

    dx_base = dx_call.split('/')[0].upper() if dx_call else ''
    my_base = my_call.split('/')[0].upper() if my_call else ''
    # "Déjà fait" = déjà contacté SUR CETTE BANDE précisément. Tous les concours
    # gérés ici sont multi-bandes (RPH, IARU VHF/UHF, CQ WW/WPX...) où le même
    # indicatif sur une bande différente est un QSO neuf à part entière — ex.
    # RPH : un contact déjà fait en 144 MHz reste PLEINEMENT valable en 432 MHz
    # (points doublés, règle d'or du concours). Ne jamais le marquer "déjà fait"
    # sous prétexte qu'il a été travaillé sur une autre bande.
    band_norm = str(band).replace(' MHz', '').replace(' GHz', '').strip() if band else ''
    is_already_done = band_norm in done_calls_by_band.get(dx_base, set())

    # Contexte partagé par toutes les briques
    ctx = {
        'dx_base': dx_base, 'my_base': my_base,
        'dx_locator': dx_locator, 'my_locator': my_locator,
        'dx_country': dxcc.country_key(dx_base),
        'my_country': dxcc.country_key(my_base) if my_base else 'F',
        'dx_cont': get_continent(dx_base), 'my_cont': get_continent(my_base),
        'dx_cq_zone': dxcc.cq_zone(dx_base),
        'dist_km': dist_km, 'band_norm': band_norm, 'source': source,
        'mode': mode,
        'done_locators': done_locators, 'done_large_squares': done_large_squares,
        'done_cq_zones': done_cq_zones, 'done_dxcc': done_dxcc,
        'current_score_total': current_score_total,
        'bricks': bricks,  # accessible aux détecteurs (ex. seuils de priorité)
    }
    # Exposés dans le résultat (pas seulement ctx) pour le constructeur de
    # règles d'alerte côté client — pays/continent/zone CQ du DX.
    result['dx_country'] = ctx['dx_country']
    result['dx_continent'] = ctx['dx_cont']
    result['dx_cq_zone'] = ctx['dx_cq_zone']

    # ── Brique validité : station hors périmètre du concours → 0 pt ─────────
    validity = bricks.get('validity')
    if validity and not _check_validity(validity, ctx):
        result['direct_pts'] = 0
        result['total_impact'] = 0
        result['priority'] = 6
        _tpl = bricks.get('validity_fail_explanation',
                          'Station {dx_base} hors périmètre — 0 pt')
        # Gabarit issu d'une définition extraite par l'IA : un placeholder absent
        # de ctx (ex. {call} au lieu de {dx_base}) levait un KeyError dans
        # .format() pour CHAQUE spot évalué, plantant tout le concours. On retombe
        # sur le gabarit brut plutôt que de casser le classement.
        try:
            result['explanation'] = _tpl.format(**ctx)
        except (KeyError, IndexError, ValueError):
            result['explanation'] = _tpl
        result['already_done'] = is_already_done
        if is_already_done:
            result['priority'] = 6
            result['total_impact'] = 0
        return result

    # ── Brique points fixes "même grand carré" (IARU) ───────────────────────
    ssp = bricks.get('same_square_points')
    if ssp is not None and get_large_locator(my_locator) == get_large_locator(dx_locator):
        fixed = scoring.get(ssp.get('param'), ssp.get('default', 50)) if isinstance(ssp, dict) else ssp
        result['direct_pts'] = fixed
        result['total_impact'] = fixed
        result['explanation'] = f"Même grand carré → {fixed} pts fixes"
        result['priority'] = 4
    else:
        # ── Brique points ────────────────────────────────────────────────────
        pts = _eval_points(bricks.get('points'), ctx, scoring)
        result['direct_pts'] = pts

        # ── Brique multiplicateur ────────────────────────────────────────────
        mult = bricks.get('multiplier')
        evaluator = MULT_EVALUATORS.get(mult.get('kind')) if isinstance(mult, dict) else None
        if evaluator:
            evaluator(ctx, pts, result, scoring)
            # Brique : multiplicateurs pondérés par bande (ex. WAE : pays ×4 sur
            # 3.5 MHz, ×3 sur 7 MHz, ×2 au-dessus) — l'impact estimé du nouveau
            # mult est mis à l'échelle du poids de la bande courante.
            weights = bricks.get('mult_weight_by_band')
            if weights and result.get('new_mult'):
                w = weights.get(band_norm)
                if w and w != 1:
                    result['mult_value'] = w
                    gain = result['total_impact'] - result['direct_pts']
                    result['total_impact'] = result['direct_pts'] + int(gain * w)
                    result['explanation'] += f" — mult ×{w} sur {band_norm} MHz"
        else:
            # Pas de multiplicateur : impact = points, priorité par paliers
            result['total_impact'] = pts
            prio = bricks.get('priority_default', 5)
            for threshold, p in bricks.get('priority_thresholds', []):
                if dist_km > threshold:
                    prio = p
                    break
            result['priority'] = prio
            template = bricks.get('explain_direct', '{pts} pts')
            try:
                result['explanation'] = template.format(pts=pts, **ctx)
            except (KeyError, IndexError, ValueError):
                result['explanation'] = template
            # Un contact vu uniquement sur le chat ON4KST (personne connectée en
            # ligne) n'est PAS un signal radio confirmé — juste une occasion de
            # proposer un sked. Sur un contest 1pt/km, la distance seule pousse
            # ces candidats en priorité 1 ("DX EXCEPTIONNEL") alors qu'aucune
            # propagation réelle n'a été vérifiée sur ce trajet précis. On
            # plafonne leur priorité pour ne pas noyer le TOP 5 avec des paris
            # spéculatifs au détriment de contacts réellement spotés.
            if bricks.get('on4kst_priority_cap') and source == 'on4kst-chat' and result['priority'] < 3:
                result['priority'] = 3
                result['explanation'] += " — via chat ON4KST, propagation non confirmée sur ce trajet"

    # Propagation confirmée (Sporadique-E / Tropo / Aurore) : priorité renforcée
    # sur les contacts VHF/UHF que ça rend exceptionnellement possibles — sans
    # ça, ces opportunités ne se distinguaient pas d'un contact ordinaire à
    # la même distance alors que la fenêtre de propagation est souvent courte.
    if bricks.get('propagation_boost') and not is_already_done:
        boost, note = get_propagation_boost(dist_km, band_norm, noaa, dxmaps)
        if boost:
            result['priority'] = max(1, result['priority'] + boost)
            result['explanation'] += f" — {note}"

    result['already_done'] = is_already_done
    if is_already_done:
        result['priority'] = 6
        result['total_impact'] = 0

    return result

def rank_stations_by_value(stations_data, contest_id, my_call, my_locator,
                            done_calls_by_band, done_locators, done_large_squares,
                            done_cq_zones, done_dxcc, current_score,
                            noaa=None, dxmaps=None):
    """
    Prend une liste de stations et les classe par valeur décroissante.
    stations_data = [{'call':str, 'locator':str, 'dist_km':int, 'band':str, ...}]
    Retourne la liste triée avec valeurs calculées.
    """
    ranked = []
    for s in stations_data:
        val = calc_qso_value(
            contest_id,
            s.get('call',''), s.get('locator',''),
            my_call, my_locator,
            done_calls_by_band, done_locators, done_large_squares,
            done_cq_zones, done_dxcc, current_score,
            s.get('band',''), s.get('dist_km', 0),
            noaa, dxmaps, s.get('source','')
        )
        s['scoring'] = val
        s['value_total'] = val['total_impact']
        s['priority'] = val['priority']
        ranked.append(s)

    # Trier par valeur totale décroissante, puis par priorité
    ranked.sort(key=lambda x: (-x['value_total'], x['priority']))
    return ranked

def extract_dx_locator(dx_call, info, spotter_call=''):
    """Locator du DX depuis le commentaire d'un spot — en se méfiant du piège
    classique : les spotteurs écrivent souvent LEUR PROPRE grille dans le
    commentaire (« JO70OB 539 QSB »). Chaque candidat est confronté aux
    centroïdes pays (cty.dat) du DX et du spotteur : un locator qui colle au
    pays du spotteur mais pas à celui du DX est rejeté.
    Accepte les grilles 6 et 4 caractères ('JN23' → 'JN23MM')."""
    text = (info or '').upper()
    cands = re.findall(r'[A-R]{2}\d{2}[A-X]{2}', text)
    # Grilles 4 caractères non déjà couvertes par une 6-caractères
    for m in re.findall(r'[A-R]{2}\d{2}', text):
        if not any(c.startswith(m) for c in cands):
            cands.append(m + 'MM')
    if not cands:
        return ''
    dx_info = dxcc.lookup(dx_call)
    sp_info = dxcc.lookup(spotter_call) if spotter_call else None
    if not dx_info or dx_info.get('lat') is None:
        return cands[0]  # pays inconnu : au moins un locator plausible

    best, best_d = '', None
    for loc in cands:
        ll = locator_to_latlon(loc)
        if ll[0] is None:
            continue
        d_dx = haversine(ll[0], ll[1], dx_info['lat'], dx_info['lon'])
        if sp_info and sp_info.get('lat') is not None \
                and sp_info['prefix'] != dx_info['prefix']:
            d_sp = haversine(ll[0], ll[1], sp_info['lat'], sp_info['lon'])
            if d_sp * 2 < d_dx:
                continue  # nettement plus proche du spotteur : sa grille à lui
        if best_d is None or d_dx < best_d:
            best, best_d = loc, d_dx
    # Au-delà de ~3000 km du centroïde, ce n'est pas le locator du DX
    # (3000 : les très grands pays — W, VK, UA9 — ont des côtes lointaines)
    if best_d is not None and best_d > 3000:
        return ''
    return best


def _band_from_freq(freq):
    """'14032' (kHz) ou '14.032' (MHz) → bande interne ('14'). '' si inconnue."""
    try:
        v = float(str(freq).replace(',', '.'))
    except (ValueError, TypeError):
        return ''
    mhz = v / 1000.0 if v > 1000 else v
    for lo, hi, b in ((1.8, 2.0, '1.8'), (3.5, 4.0, '3.5'), (7.0, 7.3, '7'),
                      (10.1, 10.15, '10.1'), (14.0, 14.35, '14'), (18.0, 18.2, '18'),
                      (21.0, 21.45, '21'), (24.8, 25.0, '24'), (28.0, 29.7, '28'),
                      (50, 54, '50'), (144, 148, '144'), (430, 440, '432')):
        if lo <= mhz <= hi:
            return b
    return ''


# Fenêtres d'appel FT8/FT4 (kHz) — un spot dans une de ces fenêtres est un
# contact numérique, à écarter quand le concours est SSB/CW uniquement
# (cas réel : spots 144.174 FT8 proposés au Bol d'Or QRP NO-DIGI).
_DIGITAL_WINDOWS_KHZ = (
    (1840, 1846), (3568, 3576), (7071, 7078), (10131, 10140),
    (14071, 14081), (18095, 18109), (21071, 21081), (24911, 24920),
    (28071, 28081), (50310, 50325), (144170, 144182), (432170, 432178),
)

def _is_digital_freq(freq):
    try:
        v = float(str(freq).replace(',', '.'))
    except (ValueError, TypeError):
        return False
    khz = v if v > 1000 else v * 1000.0
    return any(lo <= khz <= hi for lo, hi in _DIGITAL_WINDOWS_KHZ)


# Distance max plausible par bande (km) pour un spot terrestre : au-delà,
# c'est une position erronée ou de l'EME — jamais un contact de concours
# tropo/Es (cas réel : FK8HA « à 17 014 km en 144 MHz » proposé à l'agent).
_MAX_PLAUSIBLE_KM = {
    '50': 6000, '70': 3000, '144': 2500, '432': 2000,
    '1296': 1200, '2320': 900, '3400': 800, '5760': 700, '10368': 600,
}

def filter_spots_for_contest(stations, contest):
    """Ne garde que les spots jouables dans le concours actif : bande autorisée
    par la définition, mode compatible (fenêtres FT8/FT4 écartées si le
    concours n'accepte pas le numérique), distance plausible pour la bande.
    Retourne (gardés, écartés_par_raison)."""
    cdef = CONTEST_DEFINITIONS.get(contest, {})
    allowed_bands = {str(b) for b in (cdef.get('bands') or [])}
    if {b.upper() for b in allowed_bands} & {'ALL', 'TOUTES'}:
        allowed_bands = set()   # 'all' (SOTA/POTA) = aucune restriction de bande
    modes = [str(m).upper() for m in (cdef.get('modes') or [])]
    digital_ok = (not modes) or bool(
        {'FT8', 'FT4', 'RTTY', 'PSK', 'DIGI', 'DATA', 'ALL'} & set(modes))
    kept, dropped = [], {'hors_bande': 0, 'numerique': 0, 'distance': 0,
                         'freq_bande': 0}
    for s in stations:
        band = str(s.get('band', ''))
        # Cohérence fréquence ↔ bande : un spot 50.125 MHz étiqueté « 144 »
        # est un déchet de parsing (vécu : il polluait 144 ET 432). La
        # fréquence fait foi quand elle est exploitable.
        freq_band = _band_from_freq(s.get('freq', ''))
        if freq_band and freq_band != band:
            dropped['freq_bande'] += 1
            continue
        if allowed_bands and band not in allowed_bands:
            dropped['hors_bande'] += 1
            continue
        if not digital_ok and _is_digital_freq(s.get('freq', '')):
            dropped['numerique'] += 1
            continue
        cap = _MAX_PLAUSIBLE_KM.get(band)
        if cap and s.get('dist_km', 0) > cap:
            dropped['distance'] += 1
            continue
        kept.append(s)
    return kept, dropped


def build_ranked_spots(logs, spots_by_band, cfg, noaa=None, dxmaps=None, on4kst_users=None):
    """Extrait l'état du log, évalue chaque spot au barème du concours et
    retourne (ranked, meta) STRUCTURÉS — consommé par le contexte IA
    (build_scoring_context) ET par /data/spots_ranked pour l'affichage direct
    de la « need list » (nouveaux multiplicateurs en évidence)."""
    contest = cfg.get('contest', 'CUSTOM')
    my_call = cfg.get('callsign_contest', cfg.get('callsign', ''))
    my_locator = cfg.get('locator', 'JN00AA')

    # Extraire l'état actuel du log — indicatifs suivis PAR BANDE : un contact
    # déjà fait sur 144 MHz reste une opportunité pleine sur 432 MHz (RPH,
    # IARU VHF/UHF, CQ WW... comptent chaque bande séparément).
    done_calls_by_band = {}  # indicatif -> set(bandes normalisées, ex: '144')
    done_locators = set()
    done_large_squares = set()
    done_cq_zones = set()
    done_dxcc = set()
    current_score = 0

    def _mark_done(call, band):
        base = (call or '').split('/')[0].upper()
        band_norm = str(band or '').replace(' MHz', '').replace(' GHz', '').strip()
        if base:
            done_calls_by_band.setdefault(base, set()).add(band_norm)
        return base

    def _mark_country_zone(base):
        """Pays et zone CQ travaillés — via la base cty.dat hors ligne."""
        if not base:
            return
        done_dxcc.add(dxcc.country_key(base))
        z = dxcc.cq_zone(base)
        if z is not None:
            done_cq_zones.add(str(z))

    # Depuis logs EDI/ADIF (un fichier EDI = une bande = la clé band_label)
    for band_label, log_data in logs.items():
        for q in log_data.get('qsos', []):
            base = _mark_done(q.get('call',''), band_label)
            loc = q.get('locator','')
            if loc:
                done_locators.add(loc)
                large = get_large_locator(loc)
                if large: done_large_squares.add(large)
            _mark_country_zone(base)
            current_score += q.get('points', 0)

    # Depuis log partagé multi-op (band déjà présent par QSO)
    for q in shared_log:
        base = _mark_done(q.get('call',''), q.get('band',''))
        loc = q.get('locator','')
        if loc:
            done_locators.add(loc)
            large = get_large_locator(loc)
            if large: done_large_squares.add(large)
        _mark_country_zone(base)
        if q.get('cq_zone'): done_cq_zones.add(str(q['cq_zone']))
        current_score += q.get('points', 0)

    # Collecter tous les spots
    all_stations = []
    for band_label, spots in spots_by_band.items():
        band = band_label.replace(' MHz','').replace(' GHz','')
        for s in spots:
            if isinstance(s, dict):
                dx = s.get('dx','').split('/')[0]
                # Locator validé contre les centroïdes pays : la grille que le
                # spotteur met dans le commentaire est la SIENNE, pas celle du DX
                loc = extract_dx_locator(dx, s.get('info',''), s.get('spotter',''))
                dx_ll = locator_to_latlon(loc) if loc else (None, None)
                # Sans locator fiable : coordonnées DX fournies par la source
                # (l'API DXSummit donne la vraie position de la station)
                if dx_ll[0] is None:
                    try:
                        la, lo = s.get('lat'), s.get('lon')
                        if la is not None and lo is not None:
                            dx_ll = (float(la), float(lo))
                    except (ValueError, TypeError):
                        pass
                my_ll = locator_to_latlon(my_locator)
                dist = 0
                if dx_ll[0] and my_ll[0]:
                    dist = haversine(my_ll[0], my_ll[1], dx_ll[0], dx_ll[1])
                # Bande réelle depuis la fréquence quand le lot est générique
                # 'HF' — indispensable aux barèmes par bande (WAE ×4 sur 3.5).
                band_eff = band
                if band.upper() == 'HF':
                    band_eff = _band_from_freq(s.get('freq', '')) or band
                all_stations.append({
                    'call': dx, 'locator': loc, 'dist_km': dist,
                    'lat': dx_ll[0], 'lon': dx_ll[1],
                    'freq': s.get('freq',''), 'band': band_eff,
                    'spotter': s.get('spotter',''),
                    'time': s.get('time',''),
                    'source': 'cluster', 'info': s.get('info',''),
                })
            elif isinstance(s, list) and len(s) >= 2:
                call_val = s[0] if s else ''
                loc_val = ''
                for cell in s:
                    if re.match(r'^[A-R]{2}\d{2}[A-X]{2}$', str(cell).strip()):
                        loc_val = str(cell).strip()
                        break
                dx_ll = locator_to_latlon(loc_val) if loc_val else (None, None)
                my_ll = locator_to_latlon(my_locator)
                dist = 0
                if dx_ll[0] and my_ll[0]:
                    dist = haversine(my_ll[0], my_ll[1], dx_ll[0], dx_ll[1])
                all_stations.append({
                    'call': call_val, 'locator': loc_val, 'dist_km': dist,
                    'band': band, 'source': 'cluster',
                })

    # Stations actives sur le chat ON4KST : candidates au même titre que les
    # spots cluster — présentes au clavier, locator connu, joignables pour un
    # sked. Injectées sur 144 ET 432 (opportunité double-bande RPH), sauf si
    # déjà vues via un spot cluster.
    if on4kst_users:
        existing_calls = {s.get('call','').split('/')[0].upper() for s in all_stations}
        my_ll = locator_to_latlon(my_locator)
        for u in on4kst_users:
            if not u.get('present'):
                continue  # absent du clavier → sked improbable dans l'immédiat
            base = u['call'].split('/')[0].upper()
            if base in existing_calls or base == my_call.split('/')[0].upper():
                continue
            pos = locator_to_latlon(u.get('locator',''))
            dist = haversine(my_ll[0], my_ll[1], pos[0], pos[1]) if (my_ll[0] and pos[0]) else 0
            # Portée VHF plausible : ~2500 km = maximum Sporadique-E un bond.
            # Au-delà (stations US/asiatiques du chat mondial), c'est EME —
            # hors de portée d'un contest tropo, ne pas polluer le TOP 5.
            if not dist or dist > 2500:
                continue
            for band in ('144', '432'):
                all_stations.append({
                    'call': u['call'], 'locator': u['locator'], 'dist_km': dist,
                    'band': band, 'freq': '', 'spotter': 'ON4KST',
                    'time': 'actif maintenant', 'source': 'on4kst-chat',
                })

    # Ne garder que les spots JOUABLES dans ce concours (bandes/modes de la
    # définition, distances plausibles) — sinon l'agent IA et la carte
    # reçoivent des contacts hors concours (50 MHz au Bol d'Or, FT8 en
    # NO-DIGI, DX à 17 000 km « en 144 MHz »).
    total_before = len(all_stations)
    all_stations, dropped = filter_spots_for_contest(all_stations, contest)

    # Calculer et classer
    ranked = rank_stations_by_value(
        all_stations, contest, my_call, my_locator,
        done_calls_by_band, done_locators, done_large_squares,
        done_cq_zones, done_dxcc, current_score,
        noaa, dxmaps
    )
    cdef = CONTEST_DEFINITIONS.get(contest, {})
    meta = {
        'contest': contest,
        'my_call': my_call,
        'my_locator': my_locator,
        'current_score': current_score,
        'nb_calls': len(done_calls_by_band),
        'nb_qso_bands': sum(len(b) for b in done_calls_by_band.values()),
        'nb_locators': len(done_locators),
        'nb_large_squares': len(done_large_squares),
        'nb_dxcc': len(done_dxcc),
        'spots_total': total_before,
        'spots_dropped': dropped,
        'contest_bands': [str(b) for b in (cdef.get('bands') or [])],
        'contest_modes': [str(m) for m in (cdef.get('modes') or [])],
    }
    return ranked, meta


def build_scoring_context(logs, spots_by_band, cfg, noaa=None, dxmaps=None, on4kst_users=None):
    """
    Construit le contexte de scoring pour l'IA :
    calcule la valeur de chaque spot et les classe (via build_ranked_spots).
    """
    ranked, meta = build_ranked_spots(logs, spots_by_band, cfg, noaa, dxmaps, on4kst_users)
    contest = meta['contest']
    my_locator = meta['my_locator']
    current_score = meta['current_score']

    # Construire le texte de contexte
    bands_txt = '/'.join(meta.get('contest_bands') or []) or 'toutes'
    modes_txt = '/'.join(meta.get('contest_modes') or []) or 'tous'
    dropped = meta.get('spots_dropped') or {}
    nb_dropped = sum(dropped.values())
    lines = ["\n=== CLASSEMENT STATIONS PAR VALEUR RÉELLE (moteur scoring) ==="]
    lines.append(f"Concours : {contest} | Score actuel : {current_score} pts")
    lines.append(f"Bandes du concours : {bands_txt} MHz | Modes : {modes_txt}")
    lines.append("⚠️ CONSIGNE : les spots ci-dessous sont DÉJÀ filtrés (bandes/modes du "
                 "concours, distances plausibles). Ne propose JAMAIS un contact qui n'y "
                 "figure pas ; ne propose JAMAIS une bande ou un mode hors concours.")
    if nb_dropped:
        lines.append(f"({nb_dropped} spots écartés avant classement : "
                     f"{dropped.get('hors_bande', 0)} hors bande, "
                     f"{dropped.get('numerique', 0)} numérique interdit, "
                     f"{dropped.get('distance', 0)} distance non plausible)")
    lines.append(f"État : {meta['nb_calls']} indicatifs ({meta['nb_qso_bands']} QSO toutes bandes) | "
                f"{meta['nb_locators']} locators | "
                f"{meta['nb_large_squares']} grands carrés | {meta['nb_dxcc']} pays/depts\n")

    priority_labels = {1:'🌟 PRIORITÉ MAX', 2:'🔴 HAUTE', 3:'🟠 MOYENNE', 4:'🟡 BASSE', 5:'🟢 INFO', 6:'⚪ DÉJÀ FAIT'}

    for i, s in enumerate(ranked[:15]):
        sc = s.get('scoring', {})
        prio = priority_labels.get(s.get('priority', 5), '—')
        lines.append(
            f"{i+1:2}. {prio} | {s.get('call','?'):12} | {s.get('band','?'):6} MHz | "
            f"{s.get('dist_km',0):4} km | "
            f"💰 {sc.get('direct_pts',0):4}pts directs | "
            f"{'📈 NOUVEAU MULT !' if sc.get('new_mult') else '          '} | "
            f"🏆 Impact total: ~{sc.get('total_impact',0):5} pts | "
            f"Loc:{s.get('locator','?'):6} | "
            f"{sc.get('explanation','')[:50]}"
        )

    if not ranked:
        lines.append(f"AUCUN SPOT EXPLOITABLE pour ce concours en ce moment"
                     f"{f' ({nb_dropped} spots vus mais tous hors concours)' if nb_dropped else ''}.")
        lines.append("→ CONSIGNE : dis-le simplement à l'opérateur. NE PROPOSE AUCUN contact "
                     "inventé ni hors bandes/modes. Donne plutôt un conseil d'action : lancer "
                     "appel (CQ) sur la bande principale, orienter l'antenne vers les zones "
                     "actives, revenir aux spots dans quelques minutes.")

    lines.append("\n=== TOP 5 RECOMMANDATIONS AGENT ===")
    top5 = [s for s in ranked if not s.get('scoring',{}).get('already_done', False)][:5]
    for i, s in enumerate(top5):
        sc = s.get('scoring', {})
        bearing_deg = 0
        my_ll = locator_to_latlon(my_locator)
        dx_ll = locator_to_latlon(s.get('locator',''))
        if my_ll[0] and dx_ll and dx_ll[0]:
            bearing_deg = bearing(my_ll[0], my_ll[1], dx_ll[0], dx_ll[1])
        card = cardinal(bearing_deg)
        lines.append(f"""
{'='*55}
#{i+1} — {s.get('call','?')} | {s.get('band','?')} MHz | {s.get('locator','?')}
📏 Distance : {s.get('dist_km',0)} km depuis {my_locator}
🧭 Cap antenne : {bearing_deg}° {card}
💰 Points directs : {sc.get('direct_pts',0)} pts
{'📈 ' + sc.get('mult_type','').upper() + ' MANQUANT → impact x(mult+1) !' if sc.get('new_mult') else ''}
🏆 Impact total estimé : ~{sc.get('total_impact',0)} pts
📡 {sc.get('explanation','')}
🕐 Spoté il y a {s.get('time','')} | Source: {s.get('source','')}""")

    lines.append("\n=== FIN CLASSEMENT ===")
    return '\n'.join(lines)
