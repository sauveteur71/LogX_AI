# -*- coding: utf-8 -*-
"""Prévision d'ouverture par région — depuis N'IMPORTE QUEL QTH.

Où que soit la station (Hiva Oa, l'Europe, ailleurs), estime pour chaque bande
la probabilité d'ouverture vers une grande région DX (Europe, Amérique du Nord,
Japon…). Heuristique (pas VOACAP) combinant :
  - la géométrie : distance, azimut court/long chemin, nombre de sauts F2 ;
  - le jour/nuit aux DEUX extrémités (élévation solaire) : bandes basses la
    nuit, bandes hautes le jour ;
  - la grey-line (terminateur) : bonus, surtout sur les bandes basses ;
  - la MUF et le flux solaire (SFI/indice K) fournis par le module propagation.

Sert un endpoint /data/openings et surtout ALIMENTE le contexte de l'agent IA :
l'opérateur peut demander « mes chances vers l'Europe ce soir ? » et l'IA
répond avec ces chiffres.
"""
import datetime
import math

from logx_utils import locator_to_latlon, haversine, bearing, cardinal

# Centres représentatifs (densité de stations) des grandes régions DX.
REGIONS = {
    'EU': ('Europe',           48.0, 10.0),
    'NA': ('Amérique du Nord',  40.0, -95.0),
    'SA': ('Amérique du Sud',  -15.0, -60.0),
    'AF': ('Afrique',            5.0, 20.0),
    'AS': ('Asie',              45.0, 90.0),
    'JA': ('Japon',             36.0, 138.0),
    'OC': ('Océanie',          -28.0, 140.0),
}

BANDS = ['1.8', '3.5', '7', '10', '14', '18', '21', '24', '28', '50']
LOW = {'1.8', '3.5', '7'}
HIGH = {'21', '24', '28', '50'}
HOP_KM = 3500.0            # portée max d'un saut F2


def sun_elevation(lat, lon, when):
    """Élévation solaire (degrés) au point (lat, lon) à l'instant UTC `when`.
    < 0 = nuit, ~0 = grey-line, > 0 = jour."""
    n = when.timetuple().tm_yday
    decl = 23.45 * math.sin(math.radians(360.0 / 365.0 * (284 + n)))
    hours = when.hour + when.minute / 60.0 + when.second / 3600.0
    lst = hours + lon / 15.0                 # temps solaire local (approx)
    hour_angle = 15.0 * (lst - 12.0)
    la, de, ha = map(math.radians, (lat, decl, hour_angle))
    elev = math.asin(max(-1, min(1, math.sin(la) * math.sin(de)
                                 + math.cos(la) * math.cos(de) * math.cos(ha))))
    return math.degrees(elev)


def _tod_side(locator, when):
    lat, lon = locator_to_latlon(locator)
    if lat is None:
        return None
    elev = sun_elevation(lat, lon, when)
    # Heure solaire locale (même approximation que sun_elevation, longitude/15 —
    # pas de base de fuseaux horaires politiques, cohérent avec le reste du module).
    local_hour = (when.hour + when.minute / 60.0 + lon / 15.0) % 24
    return {'elevation': round(elev, 1), 'is_day': elev > 0, 'local_hour': round(local_hour, 2)}


def time_of_day_state(my_locator, dx_locator=None, when=None):
    """Comparatif jour/nuit HOME vs DX (widget Time of Day) : élévation
    solaire + heure locale approximée pour chacun des deux points. `dx_locator`
    optionnel — absent tant que l'opérateur ne travaille aucune station."""
    when = when or datetime.datetime.utcnow()
    result = {'utc': when.strftime('%H:%M'), 'home': _tod_side(my_locator, when)}
    if dx_locator:
        result['dx'] = _tod_side(dx_locator, when)
    return result


def _muf_mhz(solar):
    try:
        v = (solar or {}).get('muf', {})
        if isinstance(v, dict):
            v = v.get('muf_mhz') or v.get('muf') or v.get('value')
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _sfi_k(solar):
    s = (solar or {}).get('solar', solar) or {}
    def num(*keys, default=0):
        for k in keys:
            v = s.get(k)
            try:
                if v not in (None, ''):
                    return float(v)
            except (TypeError, ValueError):
                pass
        return default
    return num('sfi', 'solar_flux', default=100), num('k_index', 'kindex', 'k', default=2)


def _a_index(solar):
    """Indice A (Ap) — moyenne sur 24 h des huit valeurs trihoraires ak.

    POURQUOI IL EST REMONTÉ ALORS QU'IL NE PONDÈRE RIEN. Chaque Kp trihoraire
    se convertit en amplitude équivalente ak (table de Bartels) ; Ap est la
    moyenne des huit sur 24 h (définition SWPC/GFZ). A n'apporte donc AUCUNE
    information physique nouvelle par rapport à la série des K — il apporte de
    l'HISTORIQUE, ce qu'un K instantané n'a pas. Et c'est justement l'historique
    que la littérature utilise : le modèle STORM (intégré à IRI) est piloté par
    les 33 heures précédentes de ap.

    Il était récupéré depuis NOAA, affiché, et n'entrait dans aucun calcul :
    la variable même dont on a besoin était jetée. Elle est désormais SERVIE au
    client et à l'IA, qui peuvent la lire. Elle n'est délibérément multipliée à
    rien — voir le commentaire de _band_score : sans les tables de coefficients
    de STORM, tout facteur « Ap → dégradation » serait inventé.
    """
    s = (solar or {}).get('solar', solar) or {}
    for k in ('a_index', 'aindex', 'ap', 'a'):
        v = s.get(k)
        try:
            if v not in (None, ''):
                return float(v)
        except (TypeError, ValueError):
            pass
    return None


def _band_score(band, my_elev, dx_elev, muf, sfi, k, greyline):
    """Score 0-100 d'ouverture d'une bande vers la région à cet instant.

    `k` est CONSERVÉ dans la signature mais volontairement inutilisé : voir le
    bloc « L'INDICE K NE PONDÈRE PLUS RIEN » plus bas. Le retirer donnerait
    l'impression d'un oubli ; le garder dit qu'on a tranché.
    """
    f = float(band)
    # 1) MUF : au-dessus de la MUF, quasi mort ; juste en dessous = optimal.
    if muf <= 0:
        muf_factor = 0.6                     # pas de données MUF : neutre
    elif f > muf * 1.15:
        muf_factor = 0.08
    elif f > muf:
        muf_factor = 0.35
    elif f > muf * 0.55:
        muf_factor = 1.0
    else:
        muf_factor = 0.75
    # 2) Jour/nuit selon la bande (moyenne des deux extrémités)
    day = (max(0, min(1, (my_elev + 6) / 18.0)) + max(0, min(1, (dx_elev + 6) / 18.0))) / 2
    night = 1 - day
    if band in LOW:
        tod = 0.35 + 0.65 * night
    elif band in HIGH:
        tod = 0.30 + 0.70 * day
    else:
        tod = 0.6 + 0.2 * (1 - abs(day - 0.5) * 2)   # bandes moyennes : polyvalentes
    # 3) Grey-line : bonus (les basses en profitent le plus)
    gl = (0.18 if band in LOW else 0.10) if greyline else 0.0
    # 4) Flux solaire : le SFI aide les bandes hautes. Sourçable (l'ionisation
    #    F2 croît avec le flux 10,7 cm), et c'est une médiane, pas un événement.
    sfi_factor = 1.0
    if band in HIGH:
        sfi_factor = max(0.5, min(1.15, sfi / 110.0))
    #
    # L'INDICE K NE PONDÈRE PLUS RIEN, ET C'EST UNE SUPPRESSION VOULUE.
    #
    # Il y avait ici `if k >= 5: sfi_factor *= 0.6`, appliqué aux seules bandes
    # HAUTES — or HIGH contient '50'. Mesuré : à K=6 le score du 6 m tombait de
    # 8 à 5, PENDANT que es_aurora_forecast() annonçait sur cette même bande
    # « orage géomagnétique, aurora possible, pointe au nord ». Le logiciel se
    # trompait de signe sur 6 m, et se contredisait dans la même seconde.
    #
    # Ce coefficient n'était étayé par rien. Il n'existe pas de norme donnant
    # une dégradation « par bande » en fonction de K :
    #   - l'échelle G du NOAA est définie sur Kp (G1 = Kp 5) et son libellé HF
    #     est LATITUDINAL — affaiblissement aux hautes latitudes, coupure sur
    #     les trajets polaires — jamais « bandes hautes » ;
    #   - ITU-R P.533-14 et VOACAP, les deux modèles de référence, sont pilotés
    #     par R12 et n'ingèrent PAS Kp ;
    #   - une tempête ionosphérique a une phase POSITIVE (foF2 en hausse) et
    #     une phase négative, et le modèle de référence (STORM, intégré à IRI)
    #     dépend de la latitude, de la saison et de l'heure locale.
    #
    # Le bon axe n'est donc pas la bande : c'est (latitude géomagnétique du
    # trajet, saison, heure locale, phase de la tempête). Deux voies honnêtes
    # existent — implémenter STORM (Araujo-Pradere, Fuller-Rowell & Codrescu,
    # « STORM: An empirical storm-time ionospheric correction model: 1. Model
    # description », Radio Science 37(5), 1070, 2002 : entrée = historique 33 h
    # de ap, sortie = correction de foF2), ou ne pas modéliser la tempête et
    # AFFICHER K et Ap bruts. C'est la seconde qui est retenue ici, faute des
    # tables de coefficients de STORM.
    #
    # L'aurora reste traitée là où elle est sourçable : es_aurora_forecast(),
    # sur l'échelle G du NOAA, et elle OUVRE la VHF au lieu de la fermer.
    score = 100 * muf_factor * tod * sfi_factor + 100 * gl
    return int(max(0, min(100, score)))


def path_openings(my_lat, my_lon, region_key, when=None, solar=None):
    """Ouvertures par bande vers `region_key` MAINTENANT + meilleure fenêtre 24 h."""
    when = when or datetime.datetime.utcnow()
    name, dlat, dlon = REGIONS[region_key]
    dist = haversine(my_lat, my_lon, dlat, dlon)
    az_short = bearing(my_lat, my_lon, dlat, dlon)
    az_long = (az_short + 180) % 360
    hops = max(1, round(dist / HOP_KM))
    muf = _muf_mhz(solar)
    sfi, k = _sfi_k(solar)

    my_el = sun_elevation(my_lat, my_lon, when)
    dx_el = sun_elevation(dlat, dlon, when)
    greyline = abs(my_el) < 6 or abs(dx_el) < 6

    bands = []
    for b in BANDS:
        sc = _band_score(b, my_el, dx_el, muf, sfi, k, greyline)
        bands.append({'band': b, 'score': sc,
                      'level': 'bon' if sc >= 62 else 'possible' if sc >= 38 else 'faible'})
    bands.sort(key=lambda x: -x['score'])

    # Meilleure fenêtre : sur 24 h, l'heure où la meilleure bande culmine
    best_band = bands[0]['band'] if bands else '14'
    best_hour, best_val = None, -1
    for dh in range(0, 24):
        t = when + datetime.timedelta(hours=dh)
        el1 = sun_elevation(my_lat, my_lon, t)
        el2 = sun_elevation(dlat, dlon, t)
        gl = abs(el1) < 6 or abs(el2) < 6
        v = _band_score(best_band, el1, el2, muf, sfi, k, gl)
        if v > best_val:
            best_val, best_hour = v, t

    return {
        'region': region_key, 'region_name': name,
        'distance_km': dist, 'hops': hops,
        'bearing_short': az_short, 'cardinal_short': cardinal(az_short),
        'bearing_long': az_long, 'cardinal_long': cardinal(az_long),
        'long_path': dist > 9000,          # au-delà, le long chemin vaut le coup
        'my_sun_elev': round(my_el), 'dx_sun_elev': round(dx_el),
        # `a_index` : historique géomagnétique 24 h. Il ne pondère aucun score
        # (voir _a_index et _band_score) mais il est SERVI — c'est la variable
        # que la littérature utilise, et la jeter serait la vraie perte.
        'greyline': greyline, 'muf_mhz': round(muf, 1), 'sfi': sfi, 'k': k,
        'a_index': _a_index(solar),
        'bands': bands,
        'best_band': best_band,
        'best_window_utc': best_hour.strftime('%H:%M') if best_hour else None,
        'best_window_score': best_val,
    }


def all_regions(my_lat, my_lon, when=None, solar=None):
    """Meilleure bande + score par région (survol pour l'agent IA)."""
    when = when or datetime.datetime.utcnow()
    out = []
    for key in REGIONS:
        p = path_openings(my_lat, my_lon, key, when, solar)
        top = p['bands'][0] if p['bands'] else {}
        out.append({
            'region': key, 'region_name': p['region_name'],
            'distance_km': p['distance_km'],
            'bearing_short': p['bearing_short'], 'cardinal_short': p['cardinal_short'],
            'long_path': p['long_path'],
            'best_band': top.get('band'), 'best_score': top.get('score'),
            'open_bands': [b['band'] for b in p['bands'] if b['score'] >= 62],
            'best_window_utc': p['best_window_utc'],
        })
    out.sort(key=lambda r: -(r.get('best_score') or 0))
    return out


def _dist_factor(band, dist):
    """Aptitude d'une bande à une DISTANCE donnée (footprint réaliste) :
    les basses portent proche/médium, les hautes veulent du DX."""
    if band in LOW:                      # 160/80/40 : proche-médium
        return 1.0 if dist < 3000 else max(0.25, 1 - (dist - 3000) / 9000.0)
    if band in HIGH:                     # 15/12/10/6 : DX (skip zone proche)
        return 0.25 if dist < 800 else min(1.0, 0.25 + (dist - 800) / 2200.0)
    return 1.0 if 300 < dist < 9000 else 0.6   # 30/20 : polyvalentes


_grid_cache = {}     # (band, hour_key, muf, sfi, k, mylat, mylon, step) -> cells


def prop_grid(my_lat, my_lon, band='best', when=None, solar=None, step=15):
    """Grille mondiale de scores d'ouverture depuis le QTH, pour une bande
    donnée (ou 'best' = meilleure bande par point). Chaque cellule :
    {lat, lon, score, band}. Cache par (bande, heure, solaire)."""
    when = when or datetime.datetime.utcnow()
    muf = _muf_mhz(solar)
    sfi, k = _sfi_k(solar)
    key = (band, when.strftime('%Y%m%d%H'), round(muf), round(sfi), round(k),
           round(my_lat, 1), round(my_lon, 1), step)
    if key in _grid_cache:
        return _grid_cache[key]

    my_el = sun_elevation(my_lat, my_lon, when)
    bands = BANDS if band == 'best' else [band]
    cells = []
    lat = -75
    while lat <= 75:
        lon = -180
        while lon < 180:
            dx_el = sun_elevation(lat, lon, when)
            greyline = abs(dx_el) < 6 or abs(my_el) < 6
            dist = haversine(my_lat, my_lon, lat, lon)
            best_sc, best_b = -1, band
            for b in bands:
                sc = _band_score(b, my_el, dx_el, muf, sfi, k, greyline)
                sc = int(sc * _dist_factor(b, dist))
                if sc > best_sc:
                    best_sc, best_b = sc, b
            cells.append({'lat': lat, 'lon': lon, 'score': max(0, best_sc), 'band': best_b})
            lon += step
        lat += step
    if len(_grid_cache) > 60:
        _grid_cache.clear()
    _grid_cache[key] = cells
    return cells


def context_block(my_lat, my_lon, when=None, solar=None):
    """Bloc texte compact pour le contexte de l'agent IA : ouvertures depuis le
    QTH vers chaque grande région. Vide si position inconnue."""
    if my_lat is None or my_lon is None:
        return ''
    when = when or datetime.datetime.utcnow()
    rows = all_regions(my_lat, my_lon, when, solar)
    lines = ["OUVERTURES DEPUIS TON QTH (estimation heuristique, "
             f"{when.strftime('%H:%M')} UTC) :"]
    for r in rows:
        openb = ', '.join(r['open_bands']) if r['open_bands'] else 'aucune bonne'
        lines.append(
            f"- {r['region_name']} ({r['distance_km']} km, cap {r['bearing_short']}° "
            f"{r['cardinal_short']}{' / long path' if r['long_path'] else ''}) : "
            f"meilleure {r['best_band']} MHz ({r['best_score']}/100), bandes ouvertes : "
            f"{openb} ; pic vers {r['best_window_utc']} UTC")
    return '\n'.join(lines)
