# -*- coding: utf-8 -*-
"""Le 8 m (40 MHz) héritait à tort du seuil DX de la HF (8000 km) et du seuil
spotter HF (4000 km), via _HF_LABELS. Or 40 MHz est entre le 10 m (28 MHz) et le
6 m (50 MHz) : une ouverture 8 m réellement remarquable (bien en deçà de 8000 km)
ne déclenchait JAMAIS l'alerte, et un spotter jusqu'à 4000 km était jugé fiable.

Valeurs (heuristique produit LogX, sourcée F4GLD 23/08/2026 depuis les obs de
propagation SpE/F2 sur 8 m — pas une norme radioamateur) : alerte DX à partir de
3000 km, spotter fiable jusqu'à 2500 km. (Le badge « DX exceptionnel ≥ 8000 km »
F2 transcontinental reste une évolution distincte, non implémentée ici.)
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_bands as bands  # noqa: E402


def test_8m_ne_herite_plus_des_seuils_hf():
    assert bands.dx_threshold_km('40 MHz', 99999) == 3000
    assert bands.band_spotter_km('40 MHz', 99999) == 2500


def test_hf_et_6m_inchanges():
    assert bands.dx_threshold_km('28 MHz', 99999) == 8000   # vraie HF
    assert bands.band_spotter_km('14 MHz', 99999) == 4000
    assert bands.dx_threshold_km('50 MHz', 99999) == 2500   # 6 m adjacent
    assert bands.band_spotter_km('50 MHz', 99999) == 800
