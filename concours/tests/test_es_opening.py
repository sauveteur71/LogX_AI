# -*- coding: utf-8 -*-
"""Indice d'ouverture VHF (logx_es_opening) — pas de prevision physique
possible pour le Sporadique-E (contrairement au tropo/meteores), donc le
signal teste ici est purement statistique : volume de spots, portee, et
diversite des indicatifs, compares a une fenetre de reference.

Les tests manipulent directement `_history` (plutot que d'enchainer des
appels a opening_index() espaces de vraies minutes) pour rester rapides et
deterministes ; `_last_fetch` est force a `now` avant chaque appel pour
desactiver la collecte reseau et isoler la LOGIQUE DE SCORE de la collecte."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import logx_es_opening as eso


@pytest.fixture(autouse=True)
def _historique_propre():
    eso.reset_history()
    yield
    eso.reset_history()


NOW = 1_800_000_000.0   # epoch arbitraire, fixe pour tous les tests
MY_LOCATOR = 'JN18AA'


def _geler_collecte(band, now=NOW):
    """Empeche opening_index() de solliciter le reseau : on ne teste ici que
    la logique de score sur un historique deja seme."""
    eso._last_fetch[band] = now


def _semer(band, entries):
    """entries: liste de (age_min, call, dist_km)."""
    for age_min, call, dist_km in entries:
        eso._history[band].append({
            'ts': NOW - age_min * 60, 'call': call, 'dist_km': dist_km,
        })


def test_bande_non_supportee():
    r = eso.opening_index('999')
    assert r['ok'] is False
    assert 'error' in r


def test_calme_sans_spots_est_faible():
    _geler_collecte('50')
    r = eso.opening_index('50', MY_LOCATOR, now=NOW)
    assert r['ok'] is True
    assert r['level'] == 'faible'
    assert r['score'] == 0
    assert r['volume_15min'] == 0
    assert r['dist_max_km'] is None


def test_premiere_collecte_sans_baseline_reste_prudent():
    """Sans historique de reference (taux_base=0), le ratio de secours vaut
    2.0 quel que soit le volume — un score MODERE, pas une alerte immediate
    sur la toute premiere donnee recue."""
    _semer('50', [(2, 'F4ABC', 150)])
    _geler_collecte('50')
    r = eso.opening_index('50', MY_LOCATOR, now=NOW)
    assert r['ok'] is True
    assert r['baseline_rate_15min'] == 0
    assert r['level'] in ('faible', 'moyen')


def test_hausse_nette_volume_et_distance_donne_excellent():
    baseline = [(20 + i * 15, f'BASE{i}', 80) for i in range(8)]   # ~1/15min sur 2h
    maintenant = [(1 + i, f'DX{i}', 1400 - i * 20) for i in range(8)]
    _semer('50', baseline + maintenant)
    _geler_collecte('50')
    r = eso.opening_index('50', MY_LOCATOR, now=NOW)
    assert r['ok'] is True
    assert r['volume_15min'] == 8
    assert r['diversity'] == 8
    assert r['dist_max_km'] >= 1200
    assert r['level'] == 'excellent'
    assert r['score'] >= 6


def test_beaucoup_de_spots_proches_ne_suffit_pas():
    """Un afflux de spots TOUS proches (trafic local dense) n'est pas une
    ouverture — la portee doit compter, pas seulement le volume."""
    baseline = [(20 + i * 15, f'BASE{i}', 50) for i in range(8)]
    maintenant = [(1 + i, f'LOCAL{i}', 60 + i) for i in range(8)]
    _semer('50', baseline + maintenant)
    _geler_collecte('50')
    r = eso.opening_index('50', MY_LOCATOR, now=NOW)
    assert r['dist_max_km'] < 300
    assert r['level'] != 'excellent'


def test_un_seul_correspondant_repete_ne_suffit_pas():
    """Le meme indicatif spotte plusieurs fois n'augmente pas la diversite —
    ce n'est pas une ouverture qui s'etend a d'autres stations."""
    baseline = [(20 + i * 15, f'BASE{i}', 80) for i in range(8)]
    maintenant = [(1 + i, 'SOLO', 1500) for i in range(8)]
    _semer('50', baseline + maintenant)
    _geler_collecte('50')
    r = eso.opening_index('50', MY_LOCATOR, now=NOW)
    assert r['diversity'] == 1
    assert r['volume_15min'] == 8   # le volume brut, lui, compte bien 8 evenements
    assert r['level'] != 'excellent'


def test_historique_ancien_est_purge():
    vieux_seuil_min = eso.GARDE_MIN + 5
    _semer('50', [(vieux_seuil_min, 'VIEUX', 500)])
    _geler_collecte('50')
    eso.opening_index('50', MY_LOCATOR, now=NOW)
    assert all(s['call'] != 'VIEUX' for s in eso._history['50'])


def test_locator_absent_ne_casse_pas_et_pas_de_distance():
    _semer('50', [(1, 'F4ABC', None)])
    _geler_collecte('50')
    r = eso.opening_index('50', '', now=NOW)
    assert r['ok'] is True
    assert r['dist_max_km'] is None


def test_collecte_dedupliquee_meme_cycle(monkeypatch):
    """Le meme couple (indicatif, spotteur) rapporte deux fois par le meme
    cycle de fetch (deux clusters qui republient le meme spot) ne doit
    compter qu'une fois."""
    spots = [
        {'call': 'F4XYZ', 'spotter': 'DL1ABC', 'lat': 50.0, 'lon': 10.0},
        {'call': 'F4XYZ', 'spotter': 'DL1ABC', 'lat': 50.0, 'lon': 10.0},   # doublon exact
        {'call': 'F4XYZ', 'spotter': 'ON4DEF', 'lat': 50.0, 'lon': 10.0},  # spotteur different : compte
    ]
    def fake_fetch(band_mhz, filter_digital, toggles):
        return spots
    r = eso.opening_index('50', MY_LOCATOR, now=NOW, fetch_fn=fake_fetch)
    assert r['ok'] is True
    assert len(eso._history['50']) == 2


def test_cache_reseau_empeche_un_second_appel_trop_rapproche():
    appels = []
    def fake_fetch(band_mhz, filter_digital, toggles):
        appels.append(now_appel[0])
        return []
    now_appel = [NOW]
    eso.opening_index('50', MY_LOCATOR, now=NOW, fetch_fn=fake_fetch)
    now_appel[0] = NOW + 10   # 10 s plus tard : sous FETCH_CACHE_S (90 s)
    eso.opening_index('50', MY_LOCATOR, now=NOW + 10, fetch_fn=fake_fetch)
    assert len(appels) == 1, 'le second appel, trop rapproche, doit reutiliser le cache'


def test_cache_reseau_autorise_un_appel_apres_le_delai():
    appels = []
    def fake_fetch(band_mhz, filter_digital, toggles):
        appels.append(1)
        return []
    eso.opening_index('50', MY_LOCATOR, now=NOW, fetch_fn=fake_fetch)
    eso.opening_index('50', MY_LOCATOR, now=NOW + eso.FETCH_CACHE_S + 1, fetch_fn=fake_fetch)
    assert len(appels) == 2


def test_opening_summary_renvoie_les_deux_bandes(monkeypatch):
    def fake_fetch(band_mhz, filter_digital, toggles):
        return []
    r = eso.opening_summary(MY_LOCATOR, now=NOW, fetch_fn=fake_fetch)
    assert set(r.keys()) == {'50', '144'}
    assert r['50']['ok'] is True and r['144']['ok'] is True
