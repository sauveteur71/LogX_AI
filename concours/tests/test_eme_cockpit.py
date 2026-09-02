# -*- coding: utf-8 -*-
"""L'agrégat /eme/cockpit compose les briques existantes, sans logique neuve.

Valeurs RF alignées sur le vrai plan de bandes IARU R1 (logx_eme_bandplan.py,
Task 4) : 432.0125 MHz et 2320.0125 MHz — les 432.065/2320.065 du brief
d'origine étaient des exemples illustratifs périmés, remplacés ici par les
valeurs réellement sourcées (voir ruling contrôleur Task 5)."""
import json
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as H   # noqa: E402

CFG = {'locator': 'JN15XC', 'altitude': 100}


def _mock(monkeypatch):
    monkeypatch.setattr(H, '_wsjtx_state_dict',
                        lambda cfg: {'dial_mhz': 432.07, 'mode': 'Q65', 'connected': True})
    import logx_eme as eme
    import logx_wsjtx as w
    import logx_moon_track as mt
    monkeypatch.setattr(eme, 'moon_position', lambda *a, **k: {
        'available': True, 'az': 187.3, 'alt': 34.0, 'visible': True,
        'distance_km': 384210.0, 'phase_pct': 61.0})
    monkeypatch.setattr(eme, 'doppler_shift_hz', lambda *a, **k: {
        'available': True, 'doppler_hz': -412.0, 'range_rate_ms': 143.0})
    monkeypatch.setattr(eme, 'moon_rise_set', lambda *a, **k: {
        'available': True, 'rise_utc': '2026/9/1 20:10:00', 'set_utc': '2026/9/2 05:40:00'})
    monkeypatch.setattr(w, 'eme_decodes', lambda max_age=300: [
        {'call': 'DL7APV', 'mode': 'Q65', 'freq_mhz': 432.071, 'snr': -24,
         'message': 'CQ DL7APV JO62', 'band': '432', 'last_seen': 0}])
    monkeypatch.setattr(mt, 'etat_suivi_lune', lambda: {
        'actif': True, 'phase': 'suivi', 'cible_az': 187.0, 'cible_el': 34.0,
        'rotor_az': 186.0, 'rotor_el': 33.0, 'visible': True, 'note': '', 'envois': 3})


def test_l_agregat_compose_toutes_les_briques(monkeypatch):
    _mock(monkeypatch)
    d = H._eme_cockpit_dict(CFG, '432')
    assert d['band'] == '432'
    assert d['rf_mhz'] == 432.0125           # depuis le plan de bandes (vraie valeur IARU R1)
    assert d['transverter'] is False
    assert d['moon']['az'] == 187.3 and d['moon']['visible'] is True
    assert d['doppler_hz'] == -412.0
    assert d['rise_utc'].endswith('20:10:00')
    assert d['decodes'][0]['call'] == 'DL7APV'
    assert d['track']['phase'] == 'suivi'
    assert d['rig']['mode'] == 'Q65'
    json.dumps(d, allow_nan=False)           # JSON-safe


def test_le_doppler_est_calcule_sur_la_RF_pas_le_dial(monkeypatch):
    _mock(monkeypatch)
    vus = {}
    import logx_eme as eme

    def _doppler_espion(lat, lon, freq_mhz, *a, **k):
        # NOTE (bug du brief corrigé ici) : la version d'origine utilisait
        # `vus.setdefault('f', freq_mhz) or {...}` — cassé dès que freq_mhz
        # est truthy (tout float non nul), car setdefault() RENVOIE alors la
        # valeur stockée (freq_mhz) au lieu de retomber sur le dict via `or`.
        # Vérifié : reproduit avec 2320.0125 -> renvoie 2320.0125 (float), pas
        # le dict, ce qui casse dp.get(...) côté _eme_cockpit_dict. Remplacé
        # par une vraie fonction qui capture puis renvoie le dict, sans piège.
        vus['f'] = freq_mhz
        return {'available': True, 'doppler_hz': 0.0, 'range_rate_ms': 0.0}

    monkeypatch.setattr(eme, 'doppler_shift_hz', _doppler_espion)
    H._eme_cockpit_dict(CFG, '2320')
    assert vus['f'] == 2320.0125              # RF du plan (vraie valeur), pas un dial/FI


def test_locator_absent_ne_plante_pas(monkeypatch):
    _mock(monkeypatch)
    d = H._eme_cockpit_dict({'locator': ''}, '144')
    assert d['moon'] is None or d['moon'] == {} or 'error' in d
