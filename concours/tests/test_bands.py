# -*- coding: utf-8 -*-
"""Tests des seuils DX/spotter par bande (logx_bands) — en particulier le
drapeau satellite (QO-100) qui bascule l'alerte "DX exceptionnel" sur le
critère nouveau DXCC/grille au lieu d'une distance km sans signification
physique sur l'empreinte d'un satellite géostationnaire."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logx_bands import (dx_threshold_km, band_spotter_km, is_satellite_band,
                         dx_alert_line, SATELLITE_BANDS)


# ─── is_satellite_band ────────────────────────────────────────────────────────
def test_qo100_est_satellite():
    assert is_satellite_band('QO-100') is True


def test_bandes_terrestres_ne_sont_pas_satellite():
    for b in ('144 MHz', '432 MHz', '14 MHz', 'HF', '10 GHz'):
        assert is_satellite_band(b) is False


def test_bande_inconnue_nest_pas_satellite():
    """Une bande absente de SATELLITE_BANDS (custom, future extension) ne doit
    jamais planter — repli sur False (comportement terrestre par défaut)."""
    assert is_satellite_band('BANDE_INCONNUE') is False


# ─── dx_threshold_km / band_spotter_km : comportement existant inchangé ──────
def test_seuils_existants_toujours_corrects():
    assert dx_threshold_km('144 MHz', 1200) == 800
    assert dx_threshold_km('432 MHz', 1200) == 400
    assert band_spotter_km('144 MHz', 600) == 300


def test_bande_absente_retombe_sur_le_fallback():
    assert dx_threshold_km('BANDE_INCONNUE', 1200) == 1200
    assert band_spotter_km('BANDE_INCONNUE', 600) == 600


def test_qo100_absent_de_la_table_km_mais_a_un_fallback():
    """QO-100 reste volontairement absent de BAND_DX_THRESHOLD_KM (aucun sens
    physique) : dx_threshold_km() seule retombe donc sur le fallback générique
    — c'est dx_alert_line() qui doit éviter de s'en servir (test suivant)."""
    assert dx_threshold_km('QO-100', 1200) == 1200


# ─── dx_alert_line : la bascule qui corrige le bug ───────────────────────────
def test_dx_alert_line_qo100_pas_de_seuil_distance():
    """Pas de critère numérique "DX > X km" pour QO-100 — seul le libellé
    explicatif peut encore mentionner le mot "km" en négation."""
    line = dx_alert_line('QO-100', 1200, 600)
    assert 'DX >' not in line
    assert 'DXCC' in line or 'grille' in line


def test_dx_alert_line_bande_terrestre_garde_les_km():
    line = dx_alert_line('144 MHz', 1200, 600)
    assert 'DX > 800 km' in line
    assert 'spotter fiable < 300 km' in line


def test_dx_alert_line_bande_custom_utilise_le_fallback():
    line = dx_alert_line('BANDE_INCONNUE', 1200, 600)
    assert 'DX > 1200 km' in line
    assert 'spotter fiable < 600 km' in line


def test_satellite_bands_ne_contient_que_qo100_pour_linstant():
    """Pas une vraie contrainte métier, juste un garde-fou si quelqu'un ajoute
    une bande satellite sans passer par SATELLITE_BANDS (ex. typo de clé)."""
    assert set(SATELLITE_BANDS) == {'QO-100'}


def test_dx_alert_line_alignement_bande_documente():
    """La centralisation par dx_alert_line() change le format par rapport aux
    DEUX anciens appelants (cf. sa docstring) : build_system_prompt() alignait
    le libellé sur 9 caractères, build_terrain_context() utilisait
    deux-points/virgule sans alignement. Ce test verrouille le format assumé
    (alignement 9 caractères conservé) pour que tout changement futur soit
    volontaire, pas silencieux."""
    line = dx_alert_line('432 MHz', 1200, 600)
    assert line.startswith(f"{'432 MHz':9} DX >")
