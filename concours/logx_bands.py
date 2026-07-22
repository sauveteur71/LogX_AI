# -*- coding: utf-8 -*-
"""Seuils DX/fiabilité spotter PAR BANDE, pour l'alerte "DX exceptionnel".

La propagation ionosphérique (HF, 1.8-28 MHz) rend des milliers de km
ROUTINIERS ; la propagation VHF/UHF/SHF est normalement en visibilité
directe/tropo, avec une portée qui chute avec la fréquence (tropo ~100-300 km
en 2m, quelques dizaines de km en microonde hors conditions exceptionnelles).
Un seuil unique (l'ancien réglage global alert_dx_km/spotter_reliable_km)
n'a donc de sens pour AUCUNE des deux gammes à la fois : banal en HF,
quasi inatteignable en microonde. cfg['alert_dx_km']/cfg['spotter_reliable_km']
restent le repli pour toute bande absente des tables ci-dessous (bande
personnalisée, future extension...).

Valeurs approximatives, calibrées sur les usages typiques (Es/F2 estivaux en
50 MHz, tropo/Es en 144-432 MHz, ligne de vue stricte au-delà) — pas une
vérité absolue, juste un ordre de grandeur raisonnable par bande."""

_HF_LABELS = (
    '1.8 MHz', '3.5 MHz', '5 MHz', '7 MHz', '10 MHz', '14 MHz',
    '18 MHz', '21 MHz', '24 MHz', '28 MHz', '40 MHz', 'HF',
)

# Distance (km) au-delà de laquelle une station est un "DX exceptionnel"
BAND_DX_THRESHOLD_KM = {
    **{b: 8000 for b in _HF_LABELS},   # HF : DX = intercontinental, pas juste "loin"
    '50 MHz': 2500,                    # 6m — Es/F2 fréquents en saison
    '70 MHz': 1200, '144 MHz': 800, '432 MHz': 400,
    '1.2 GHz': 400, '2.4 GHz': 300, '3.4 GHz': 250,
    '5.7 GHz': 150, '10 GHz': 100, '24 GHz': 50, '47 GHz': 30,
    # QO-100 (relais géostationnaire) volontairement absent : la distance
    # sol ne reflète pas la difficulté réelle (couverture quasi uniforme
    # sur toute l'empreinte Europe/Afrique/Asie) — repli sur alert_dx_km.
}

# Distance (km) en-deçà de laquelle un spotter est jugé fiable pour cette bande
BAND_SPOTTER_RELIABLE_KM = {
    **{b: 4000 for b in _HF_LABELS},
    '50 MHz': 800, '70 MHz': 500, '144 MHz': 300, '432 MHz': 150,
    '1.2 GHz': 100, '2.4 GHz': 80, '3.4 GHz': 60,
    '5.7 GHz': 40, '10 GHz': 30, '24 GHz': 15, '47 GHz': 10,
}


def dx_threshold_km(band_label, fallback):
    """Seuil DX exceptionnel (km) pour `band_label` — `fallback` (typiquement
    cfg['alert_dx_km']) si la bande n'est pas dans la table."""
    return BAND_DX_THRESHOLD_KM.get(band_label, fallback)


def band_spotter_km(band_label, fallback):
    """Distance de fiabilité spotter (km) pour `band_label` — `fallback`
    (typiquement cfg['spotter_reliable_km']) si la bande n'est pas dans la table."""
    return BAND_SPOTTER_RELIABLE_KM.get(band_label, fallback)
