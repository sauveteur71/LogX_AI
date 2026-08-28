# -*- coding: utf-8 -*-
"""Mode démo : données SYNTHÉTIQUES pour montrer l'app sans radio connectée.

Isolé par construction : ne touche NI au log NI à l'émission — ne fait que
FOURNIR des spots synthétiques quand l'opérateur active le mode démo (config
demo_mode). Chaque spot est marqué `demo: True` et l'UI affiche « MODE DÉMO ».
Déterministe (liste fixe, aucun aléa) pour une démo reproductible.
"""

# Spots synthétiques réalistes : MÊME forme que les spots classés réels de
# /data/spots_ranked (call, freq kHz, band, mode, dx_country, credit_*,
# priority, value...) — pour qu'ils traversent l'affichage existant sans code
# spécial (need list CHASSE, HUD Opportunités, fil IA).
_SPOTS = [
    {'call': 'JA1XYZ', 'freq': 14074, 'band': '20', 'mode': 'FT8', 'dx_country': 'Japan',
     'credit_classe': 'atno', 'credit_score': 1000, 'credit_raison': 'nouveau DXCC', 'priority': 1},
    {'call': '9M2JKL', 'freq': 28074, 'band': '10', 'mode': 'FT8', 'dx_country': 'West Malaysia',
     'credit_classe': 'atno', 'credit_score': 1000, 'credit_raison': 'nouveau DXCC', 'priority': 1},
    {'call': 'PY2ABC', 'freq': 21205, 'band': '15', 'mode': 'SSB', 'dx_country': 'Brazil',
     'credit_classe': 'new_band', 'credit_score': 600, 'credit_raison': 'nouvelle bande', 'priority': 2},
    {'call': 'VK3DEF', 'freq': 7025, 'band': '40', 'mode': 'CW', 'dx_country': 'Australia',
     'credit_classe': 'new_mode', 'credit_score': 500, 'credit_raison': 'nouveau mode', 'priority': 2},
    {'call': 'LU5MNO', 'freq': 18100, 'band': '17', 'mode': 'SSB', 'dx_country': 'Argentina',
     'credit_classe': 'new_band', 'credit_score': 600, 'credit_raison': 'nouvelle bande', 'priority': 2},
    {'call': 'ZL2GHI', 'freq': 14025, 'band': '20', 'mode': 'CW', 'dx_country': 'New Zealand',
     'credit_classe': 'needed_confirm', 'credit_score': 200, 'credit_raison': 'à confirmer LoTW', 'priority': 4},
]


def spots_demo():
    """Spots synthétiques (copies indépendantes, chacun marqué demo:True)."""
    out = []
    for s in _SPOTS:
        d = dict(s)
        d['demo'] = True
        d.setdefault('value', d.get('credit_score', 0))
        d.setdefault('already_done', False)
        d.setdefault('new_mult', False)
        out.append(d)
    return out
