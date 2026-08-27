# -*- coding: utf-8 -*-
"""Occupation des bandes multi-postes — cœur PUR (logx_occupancy.vue_occupation).

Carte « qui est sur quelle bande/mode » pour un log partagé (radioclub / expé /
activation spéciale). Ce module est TRANSPORT-AGNOSTIQUE : il reçoit des statuts
de postes venant de N'IMPORTE quel canal (LAN, Cloud Sync, MySQL) déjà fusionnés,
et en tire la vue d'occupation + les conflits. « Priorité locale » = le statut le
plus FRAIS gagne (le LAN est plus récent que le cloud) — émerge du latest-ts-wins.

Règle F4GLD : deux postes ne doivent jamais émettre sur la MÊME bande ET le MÊME
mode (même bande + mode différent = permis). Un tel recouvrement = conflit signalé.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logx_occupancy as occ  # noqa: E402


def test_dedup_par_station_le_plus_frais_gagne():
    """Un même poste vu par deux canaux (LAN frais + cloud périmé) -> on garde le
    plus RÉCENT (priorité locale). Une seule ligne par poste."""
    statuts = [
        {'station': 'A', 'call': 'TM6KJS', 'band': '20', 'mode': 'SSB', 'ts': 100},   # cloud, vieux
        {'station': 'A', 'call': 'TM6KJS', 'band': '40', 'mode': 'CW', 'ts': 195},    # LAN, frais
    ]
    v = occ.vue_occupation(statuts, maintenant=200, ttl_s=180)
    assert len(v['stations']) == 1
    assert v['stations'][0]['band'] == '40' and v['stations'][0]['ts'] == 195   # le frais


def test_filtre_les_postes_perimes():
    statuts = [
        {'station': 'A', 'call': 'X', 'band': '20', 'mode': 'SSB', 'ts': 190},   # vivant
        {'station': 'B', 'call': 'Y', 'band': '40', 'mode': 'CW', 'ts': 10},     # périmé (>180 s)
    ]
    v = occ.vue_occupation(statuts, maintenant=200, ttl_s=180)
    assert [s['station'] for s in v['stations']] == ['A']


def test_conflit_meme_bande_meme_mode():
    """Deux postes sur 20 m SSB = conflit (règle « jamais 2 sur la même
    bande/mode »)."""
    statuts = [
        {'station': 'A', 'call': 'X', 'band': '20', 'mode': 'SSB', 'ts': 195},
        {'station': 'B', 'call': 'Y', 'band': '20', 'mode': 'SSB', 'ts': 195},
    ]
    v = occ.vue_occupation(statuts, maintenant=200, ttl_s=180)
    assert len(v['conflits']) == 1
    c = v['conflits'][0]
    assert c['band'] == '20' and c['mode'] == 'SSB'
    assert sorted(c['stations']) == ['A', 'B']


def test_pas_de_conflit_meme_bande_mode_different():
    """Même bande mais mode différent = PERMIS (pas de conflit)."""
    statuts = [
        {'station': 'A', 'call': 'X', 'band': '20', 'mode': 'SSB', 'ts': 195},
        {'station': 'B', 'call': 'Y', 'band': '20', 'mode': 'CW', 'ts': 195},
    ]
    v = occ.vue_occupation(statuts, maintenant=200, ttl_s=180)
    assert v['conflits'] == []
    assert len(v['stations']) == 2


def test_pas_de_conflit_bandes_differentes():
    statuts = [
        {'station': 'A', 'call': 'X', 'band': '20', 'mode': 'SSB', 'ts': 195},
        {'station': 'B', 'call': 'Y', 'band': '40', 'mode': 'SSB', 'ts': 195},
    ]
    v = occ.vue_occupation(statuts, maintenant=200, ttl_s=180)
    assert v['conflits'] == []


def test_station_sans_id_ignoree():
    statuts = [{'call': 'X', 'band': '20', 'mode': 'SSB', 'ts': 195}]   # pas de 'station'
    v = occ.vue_occupation(statuts, maintenant=200, ttl_s=180)
    assert v['stations'] == [] and v['conflits'] == []
