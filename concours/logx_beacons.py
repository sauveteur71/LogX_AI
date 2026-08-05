# -*- coding: utf-8 -*-
"""Réseau international de balises NCDXF/IBP — calcul pur, sans réseau.

18 balises réparties sur le globe transmettent à tour de rôle sur 5 bandes HF
(14.100, 18.110, 21.150, 24.930, 28.200 MHz). Cycle complet = 3 minutes :
chaque balise émet 10 s par bande, décalée. À un instant donné, chaque bande
a UNE balise active — savoir laquelle indique instantanément si la bande est
ouverte vers cette région (on l'entend ou pas).

Réf : www.ncdxf.org/beacon — schéma de rotation officiel.
"""
from logx_utils import utcnow

# 18 balises dans l'ordre du créneau (slot 0..17) : indicatif, locator, QTH
BEACONS = [
    ('4U1UN',  'FN30as', 'ONU New York'),
    ('VE8AT',  'CP38gh', 'Canada (Nunavut)'),
    ('W6WX',   'CM97bd', 'USA Californie'),
    ('KH6RS',  'BL10ts', 'Hawaï'),
    ('ZL6B',   'RE78tw', 'Nouvelle-Zélande'),
    ('VK6RBP', 'OF87av', 'Australie (Perth)'),
    ('JA2IGY', 'PM84jk', 'Japon'),
    ('RR9O',   'NO14kx', 'Russie (Sibérie)'),
    ('VR2B',   'OL72bg', 'Hong Kong'),
    ('4S7B',   'MJ96wv', 'Sri Lanka'),
    ('ZS6DN',  'KG44dc', 'Afrique du Sud'),
    ('5Z4B',   'KI88hr', 'Kenya'),
    ('4X6TU',  'KM72jb', 'Israël'),
    ('OH2B',   'KP20eh', 'Finlande'),
    ('CS3B',   'IM12jt', 'Madère'),
    ('LU4AA',  'GF05tj', 'Argentine'),
    ('OA4B',   'FH17mw', 'Pérou'),
    ('YV5B',   'FJ69cc', 'Venezuela'),
]

# Bandes IBP : (fréquence kHz, libellé)
BANDS = [(14100, '20m'), (18110, '17m'), (21150, '15m'), (24930, '12m'), (28200, '10m')]

CYCLE_S = 180   # 18 balises × 10 s
SLOT_S = 10


def beacons_now(now=None):
    """Pour l'instant courant : la balise active sur chaque bande.
    Retourne [{band, freq_khz, call, locator, qth, seconds_left}]."""
    now = now or utcnow()
    # Secondes depuis minuit UTC (les balises sont synchronisées sur l'UTC)
    secs = now.hour * 3600 + now.minute * 60 + now.second
    cycle_pos = secs % CYCLE_S
    slot = cycle_pos // SLOT_S            # créneau courant 0..17
    seconds_left = SLOT_S - (cycle_pos % SLOT_S)
    out = []
    for b, (freq, label) in enumerate(BANDS):
        # Sur la bande b, au créneau `slot`, émet la balise (slot - b) mod 18
        idx = (slot - b) % len(BEACONS)
        call, loc, qth = BEACONS[idx]
        out.append({'band': label, 'freq_khz': freq,
                    'call': call, 'locator': loc, 'qth': qth,
                    'seconds_left': seconds_left})
    return out
