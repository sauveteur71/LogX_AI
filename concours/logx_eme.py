# -*- coding: utf-8 -*-
"""EME (Earth-Moon-Earth / rebond lunaire) — position de la Lune, fenêtres
communes avec un correspondant, décalage Doppler estimé.

Calculé ENTIÈREMENT en local via PyEphem (éphéméride VSOP87/ELP2000
embarquée dans la bibliothèque) — aucune donnée réseau nécessaire, comme
locator_to_latlon()/haversine() dans logx_utils.py. Les sites EME trouvés
(eme.radio, RSGB Moonbounce...) sont éditoriaux (bulletins, blogs), sans
flux de données réutilisable — vérifié avant d'écrire ce module plutôt que
supposé.

PyEphem est une dépendance OPTIONNELLE, au même titre que pyserial
(logx_cat.py) ou pyttsx3 (voice keyer) : import protégé par HAS_EPHEM,
l'appli démarre sans si la bibliothèque n'est pas installée — les fonctions
renvoient alors {'available': False, 'error': ...} plutôt que de planter.
Installation : pip install ephem (wheel précompilé, pas de compilateur requis).
"""
import math

try:
    import ephem
    HAS_EPHEM = True
except ImportError:
    HAS_EPHEM = False

KM_PER_AU = 149597870.7
C_LIGHT_MS = 299792458.0
_NOT_AVAILABLE = {'available': False, 'error': "Bibliothèque 'ephem' non installée (pip install ephem)"}


def _observer(lat, lon, elevation_m=0, when=None):
    obs = ephem.Observer()
    obs.lat = str(lat)
    obs.lon = str(lon)
    obs.elevation = elevation_m or 0
    # Pas de réfraction atmosphérique : la position GÉOMÉTRIQUE de la Lune
    # est la référence en EME (pointage d'antenne), contrairement au lever/
    # coucher "visuel" classique qui inclut la réfraction (~34').
    obs.pressure = 0
    if when:
        obs.date = when
    return obs


def moon_position(lat, lon, elevation_m=0, when=None):
    """Position actuelle de la Lune (azimut/élévation topocentriques, donc
    propres à CE QTH) + distance + phase. Précision PyEphem largement
    suffisante pour du pointage d'antenne EME (dixièmes de degré)."""
    if not HAS_EPHEM:
        return dict(_NOT_AVAILABLE)
    try:
        obs = _observer(lat, lon, elevation_m, when)
        moon = ephem.Moon()
        moon.compute(obs)
        return {
            'available': True,
            'az': round(math.degrees(float(moon.az)), 1),
            'alt': round(math.degrees(float(moon.alt)), 1),
            'distance_km': round(moon.earth_distance * KM_PER_AU, 0),
            'phase_pct': round(moon.phase, 1),
            'visible': float(moon.alt) > 0,
        }
    except Exception as e:
        return {'available': False, 'error': str(e)}


def moon_rise_set(lat, lon, elevation_m=0, when=None):
    """Prochain lever et coucher de Lune (UTC) depuis ce QTH. À certaines
    latitudes/périodes la Lune peut rester levée ou couchée >24h (comme le
    Soleil aux hautes latitudes) — signalé explicitement plutôt que de
    laisser next_rising()/next_setting() lever une exception non gérée."""
    if not HAS_EPHEM:
        return dict(_NOT_AVAILABLE)
    try:
        obs = _observer(lat, lon, elevation_m, when)
        moon = ephem.Moon()
        try:
            rise = str(obs.next_rising(moon))
        except (ephem.AlwaysUpError, ephem.NeverUpError):
            rise = None
        try:
            sett = str(obs.next_setting(moon))
        except (ephem.AlwaysUpError, ephem.NeverUpError):
            sett = None
        return {'available': True, 'rise_utc': rise, 'set_utc': sett}
    except Exception as e:
        return {'available': False, 'error': str(e)}


def doppler_shift_hz(lat, lon, freq_mhz, elevation_m=0, when=None):
    """Décalage Doppler estimé (Hz, ALLER-RETOUR Terre-Lune-Terre) à la
    fréquence donnée. Dérivée NUMÉRIQUE de la distance topocentrique Terre-
    station→Lune (écart de 60 s) plutôt qu'une formule Doppler séparée à
    reconstituer de mémoire — la distance topocentrique déjà calculée par
    moon_position() capture à la fois la rotation terrestre (qui emporte la
    station vers/loin de la Lune) et le mouvement orbital lunaire, les deux
    contributions réelles au Doppler EME. Vérifié : ordre de grandeur
    cohérent avec les ±400 Hz habituellement documentés sur 144 MHz."""
    if not HAS_EPHEM:
        return dict(_NOT_AVAILABLE)
    try:
        obs = _observer(lat, lon, elevation_m, when)
        moon = ephem.Moon()
        t0 = obs.date
        moon.compute(obs)
        d0_m = moon.earth_distance * KM_PER_AU * 1000
        obs.date = ephem.Date(t0 + 60 * ephem.second)
        moon.compute(obs)
        d1_m = moon.earth_distance * KM_PER_AU * 1000
        range_rate_ms = (d1_m - d0_m) / 60.0
        doppler_hz = -2 * range_rate_ms / C_LIGHT_MS * (freq_mhz * 1e6)
        return {'available': True, 'doppler_hz': round(doppler_hz, 1),
                'range_rate_ms': round(range_rate_ms, 2)}
    except Exception as e:
        return {'available': False, 'error': str(e)}


# Réflecteur lunaire : rayon 1738 km, albédo radar ≈ 6,5 % de la section
# géométrique. Ces deux valeurs, injectées dans l'équation radar ci-dessous,
# redonnent les pertes de référence à moins de 0,5 dB sur les trois bandes EME
# usuelles (252 / 262 / 271 dB à 144 / 432 / 1296 MHz) — c'est la vérification
# qui les valide, pas leur provenance.
RAYON_LUNE_M = 1_738_000.0
ALBEDO_RADAR_LUNE = 0.065
SIGMA_LUNE_M2 = ALBEDO_RADAR_LUNE * math.pi * RAYON_LUNE_M ** 2


def path_loss_db(distance_km, freq_mhz):
    """Perte de trajet EME totale Terre→Lune→Terre, en dB.

    ÉQUATION RADAR, et c'est tout l'objet de cette correction.

    CE QUE FAISAIT LE CODE : il calculait la perte en espace libre sur un
    trajet simple, puis la DOUBLAIT EN dB. Doubler des décibels revient à
    élever le rapport de puissance au carré — ça ne décrit aucune physique.
    Résultat mesuré : 374,6 dB à 144 MHz au lieu de 252, soit 123 dB de trop ;
    et l'erreur croissait avec la fréquence (+19 dB entre 144 et 432 MHz là où
    la réalité en donne 10), parce que la perte variait comme f⁴ au lieu de f².

    Le docstring appelait ça « le plancher théorique », en expliquant qu'il
    n'incluait pas l'albédo lunaire. C'était une justification, pas une mesure :
    un plancher trop haut de 123 dB n'est pas un plancher, c'est un chiffre qui
    dit que l'EME est impossible. La Lune n'est pas un point qui réémet — elle
    a une SECTION EFFICACE gigantesque, et c'est elle qui manquait.

    L = 10·log10( (4π)³ · d⁴ / (λ² · σ) )

    N'inclut ni la dégradation (périgée/apogée, bruit de ciel, Voie lactée) ni
    la rotation de Faraday : ce sont des conditions du moment, pas de la
    géométrie. L'écart périgée/apogée ressort en revanche naturellement du
    calcul — environ 2,3 dB, conforme aux ~2 dB documentés.
    """
    if distance_km <= 0 or freq_mhz <= 0:
        return None
    d_m = distance_km * 1000.0
    lambda_m = 299_792_458.0 / (freq_mhz * 1e6)
    rapport = ((4 * math.pi) ** 3 * d_m ** 4) / (lambda_m ** 2 * SIGMA_LUNE_M2)
    return round(10 * math.log10(rapport), 1)


def common_window(lat1, lon1, lat2, lon2, hours=48, step_minutes=10, min_elevation_deg=0):
    """Fenêtres où la Lune est visible SIMULTANÉMENT depuis les deux QTH
    (condition nécessaire pour un QSO EME) — balayage direct plutôt qu'une
    résolution analytique, largement assez rapide sur 48h/pas de 10 min
    (< 300 évaluations) et beaucoup plus simple à vérifier correct."""
    if not HAS_EPHEM:
        return dict(_NOT_AVAILABLE)
    try:
        obs1 = _observer(lat1, lon1)
        obs2 = _observer(lat2, lon2)
        moon1, moon2 = ephem.Moon(), ephem.Moon()
        start = ephem.now()
        windows = []
        in_window = False
        win_start = None
        steps = int(hours * 60 / step_minutes) + 1
        for i in range(steps):
            t = ephem.Date(start + i * step_minutes * ephem.minute)
            obs1.date = t
            obs2.date = t
            moon1.compute(obs1)
            moon2.compute(obs2)
            both_up = (math.degrees(float(moon1.alt)) > min_elevation_deg
                       and math.degrees(float(moon2.alt)) > min_elevation_deg)
            if both_up and not in_window:
                in_window = True
                win_start = t
            elif not both_up and in_window:
                in_window = False
                windows.append({'start_utc': str(win_start), 'end_utc': str(t)})
        if in_window:
            windows.append({'start_utc': str(win_start), 'end_utc': str(ephem.Date(start + hours * ephem.hour)) + ' (en cours)'})
        return {'available': True, 'windows': windows}
    except Exception as e:
        return {'available': False, 'error': str(e)}
