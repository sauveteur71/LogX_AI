# -*- coding: utf-8 -*-
"""Test d'intégration : /wsjtx/state (logx_http._wsjtx_state_dict) expose bien
une alerte « DXCC manquant » façon GridTracker quand un décodage FT8/FT4
correspond à un pays jamais travaillé — le croisement réel avec
logx_awards.spotted_new_ones(), pas seulement les fonctions unitaires testées
séparément dans test_wsjtx.py (extract_calls/record_decode) et
test_awards_qsl.py (spotted_new_ones). Exécute le vrai chemin de code plutôt
que de le relire, pour éviter le piège documenté dans la mémoire du projet
(un câblage qui a l'air correct à la lecture mais ne s'exécute jamais)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_awards as awards
import logx_http as http
import logx_wsjtx as wsjtx


def _isolate_awards(monkeypatch):
    # Même isolation que test_awards_qsl.py : spotted_new_ones() s'appuie sur
    # collect_all_qsos(), qui fusionne shared_log avec les VRAIES archives/
    # qso_archive du poste — sans ce monkeypatch, le résultat dépendrait de
    # l'historique réel de la station qui lance les tests.
    monkeypatch.setattr(awards, '_read_archives', lambda: [])
    monkeypatch.setattr(awards, '_read_qso_archive', lambda: [])
    awards.invalidate()


def _prep_wsjtx(monkeypatch, decodes):
    # start_listener() ouvrirait un vrai socket UDP en tâche de fond — jamais
    # souhaitable dans un test, d'où le no-op.
    monkeypatch.setattr(wsjtx, 'start_listener', lambda **kw: None)
    monkeypatch.setattr(wsjtx, 'wsjtx_settings', lambda cfg: {'enabled': True, 'port': 2237})
    monkeypatch.setattr(wsjtx, 'current_status', lambda: {
        'connected': True, 'dial_mhz': 14.074, 'mode': 'FT8',
        'tx_mode': '', 'de_call': '', 'logged_total': 0})
    monkeypatch.setattr(wsjtx, 'recent_decodes', lambda: decodes)


def test_wsjtx_state_signale_un_pays_jamais_travaille(monkeypatch):
    _isolate_awards(monkeypatch)
    _prep_wsjtx(monkeypatch, [
        {'call': 'JA1AAA', 'band': '14', 'freq_mhz': 14.0755, 'mode': 'FT8', 'last_seen': 0}])
    monkeypatch.setattr(http, 'shared_log', [
        {'call': 'DL1AA', 'band': '14', 'mode': 'SSB', 'contest': 'X',
         'date': '20260101', 'time': '10:00', 'locator': 'JO40AA'},
    ])
    monkeypatch.setattr(http, 'current_config', {})

    st = http._wsjtx_state_dict({})
    assert st['enabled'] is True
    assert any(m['call'] == 'JA1AAA' and m['type'] == 'dxcc' for m in st['missing'])
    hit = next(m for m in st['missing'] if m['call'] == 'JA1AAA')
    assert hit['band'] == '14 MHz'
    assert hit['freq'] == 14.0755


def test_wsjtx_state_ne_signale_rien_si_pays_deja_travaille(monkeypatch):
    _isolate_awards(monkeypatch)
    _prep_wsjtx(monkeypatch, [
        {'call': 'DL2BBB', 'band': '14', 'freq_mhz': 14.0755, 'mode': 'FT8', 'last_seen': 0}])
    monkeypatch.setattr(http, 'shared_log', [
        {'call': 'DL1AA', 'band': '14', 'mode': 'SSB', 'contest': 'X',
         'date': '20260101', 'time': '10:00', 'locator': 'JO40AA'},
    ])
    monkeypatch.setattr(http, 'current_config', {})

    st = http._wsjtx_state_dict({})
    assert st['missing'] == []


def test_wsjtx_state_sans_decode_liste_vide(monkeypatch):
    _isolate_awards(monkeypatch)
    _prep_wsjtx(monkeypatch, [])
    monkeypatch.setattr(http, 'shared_log', [])
    monkeypatch.setattr(http, 'current_config', {})

    st = http._wsjtx_state_dict({})
    assert st['missing'] == []


def test_wsjtx_state_desactive_ne_calcule_rien(monkeypatch):
    monkeypatch.setattr(wsjtx, 'wsjtx_settings', lambda cfg: {'enabled': False, 'port': 2237})
    assert http._wsjtx_state_dict({}) == {'enabled': False}
