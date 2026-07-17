# -*- coding: utf-8 -*-
"""Calendrier des essaims météoritiques — aide au Meteor Scatter (MS) VHF.

Le MS se pratique surtout sur 6 m et 2 m : chaque météore laisse une traînée
ionisée qui réfléchit brièvement les signaux VHF sur ~800-2200 km. Deux
facteurs déterminent la qualité :
  - l'ACTIVITÉ : bruit de fond permanent (sporadiques) + PICS d'essaims
    (Perséides, Géminides…) — d'où ce calendrier.
  - l'HEURE : l'activité culmine quand le radiant de l'essaim est haut, en
    pratique surtout entre ~00 h et ~08 h locales (pic vers l'aube).

Tout est DÉTERMINISTE (dates/ZHR tabulées, heuristique horaire) : aucune
donnée réseau. Sert un panneau « MÉTÉORES » et enrichit le coach VHF.
"""
import datetime

# Essaims majeurs exploitables en MS. (mois, jour) = maximum ; ZHR = taux
# horaire zénithal au pic ; window = ± jours d'activité notable ; radiant_az =
# azimut approximatif du radiant au lever (indicatif pour orienter l'antenne,
# le MS se travaille surtout vers le point de réflexion, pas le radiant).
SHOWERS = [
    {'name': 'Quadrantides', 'peak': (1, 3),  'zhr': 110, 'window': 2, 'radiant_az': 55},
    {'name': 'Lyrides',      'peak': (4, 22), 'zhr': 18,  'window': 3, 'radiant_az': 50},
    {'name': 'Êta Aquarides','peak': (5, 6),  'zhr': 50,  'window': 5, 'radiant_az': 110},
    {'name': 'Arietides',    'peak': (6, 7),  'zhr': 60,  'window': 6, 'radiant_az': 70,
     'note': 'essaim DIURNE — excellent MS de jour'},
    {'name': 'Perséides',    'peak': (8, 12), 'zhr': 100, 'window': 6, 'radiant_az': 45,
     'note': 'le meilleur essaim MS de l\'année'},
    {'name': 'Draconides',   'peak': (10, 8), 'zhr': 10,  'window': 2, 'radiant_az': 350},
    {'name': 'Orionides',    'peak': (10, 21),'zhr': 20,  'window': 4, 'radiant_az': 95},
    {'name': 'Léonides',     'peak': (11, 17),'zhr': 15,  'window': 3, 'radiant_az': 65},
    {'name': 'Géminides',    'peak': (12, 14),'zhr': 120, 'window': 4, 'radiant_az': 75,
     'note': 'essaim MS très riche'},
    {'name': 'Ursides',      'peak': (12, 22),'zhr': 10,  'window': 2, 'radiant_az': 10},
]


def _peak_dt(year, shower):
    m, d = shower['peak']
    try:
        return datetime.datetime(year, m, d, 6, 0)   # pic ~ 06 h (aube)
    except ValueError:
        return datetime.datetime(year, m, min(d, 28), 6, 0)


def _days_between(a, b):
    return (b - a).total_seconds() / 86400.0


def active_showers(now=None):
    """Essaims actifs (dans leur fenêtre) ou à venir sous 30 jours, triés du
    plus proche/actif au plus lointain. Chaque entrée porte days_to_peak et
    active(bool)."""
    now = now or datetime.datetime.utcnow()
    out = []
    for s in SHOWERS:
        best = None
        for y in (now.year - 1, now.year, now.year + 1):
            pk = _peak_dt(y, s)
            dd = _days_between(now, pk)
            if best is None or abs(dd) < abs(best):
                best = dd
        active = abs(best) <= s['window']
        if active or (0 < best <= 30):
            out.append({
                'name': s['name'], 'zhr': s['zhr'],
                'days_to_peak': round(best, 1), 'active': active,
                'radiant_az': s['radiant_az'], 'note': s.get('note', ''),
            })
    out.sort(key=lambda x: (not x['active'], abs(x['days_to_peak'])))
    return out


def ms_quality(now=None):
    """Qualité MS courante (heuristique heure + essaims actifs).
    Retourne {level, score, reason, best_hours, showers}. level ∈
    {'excellent','bon','moyen','faible'}."""
    now = now or datetime.datetime.utcnow()
    showers = active_showers(now)
    active = [s for s in showers if s['active']]

    # Base : sporadiques, meilleurs autour de l'aube (04-08 UTC ≈ créneau EU).
    h = now.hour
    hour_boost = 2 if 4 <= h <= 8 else (1 if (0 <= h <= 10) else 0)
    peak_zhr = max([s['zhr'] for s in active], default=0)
    shower_boost = 3 if peak_zhr >= 80 else 2 if peak_zhr >= 40 else 1 if active else 0
    score = hour_boost + shower_boost

    if score >= 4:
        level = 'excellent'
    elif score >= 3:
        level = 'bon'
    elif score >= 1:
        level = 'moyen'
    else:
        level = 'faible'

    bits = []
    if active:
        top = active[0]
        bits.append(f"{top['name']} actif (ZHR ~{top['zhr']})")
    else:
        bits.append("fond sporadique seulement")
    if 4 <= h <= 8:
        bits.append("créneau favorable (aube)")
    elif 0 <= h <= 10:
        bits.append("matinée correcte")
    else:
        bits.append("hors du meilleur créneau (vise 04-08 UTC)")

    return {
        'level': level, 'score': score,
        'reason': ' — '.join(bits),
        'best_hours': '04-08 UTC (pic à l\'aube)',
        'distance_km': '800-2200 km',
        'bands': ['50', '144'],
        'showers': showers[:5],
    }
