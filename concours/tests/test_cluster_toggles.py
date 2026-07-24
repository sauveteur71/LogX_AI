# -*- coding: utf-8 -*-
"""Tests des toggles individuels de sources cluster. Avant ce lot, les
boutons CONFIG src_f5len/src_dxsummit/src_dxwatch/
src_dxmaps existaient dans l'UI mais n'étaient JAMAIS lus côté serveur —
désactiver une source n'avait strictement aucun effet, toutes les sources
étaient toujours interrogées. `fetch_dxwatch_hf` (DXWatch HF) était même du
code mort : implémenté mais jamais appelé nulle part."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_clusters as clusters
import logx_http as http


# ─── fetch_all_vhf_spots (VHF) ──────────────────────────────────────────────

def _stub_all_vhf_sources(monkeypatch, calls):
    """Neutralise les 6 sources VHF, chacune enregistrant son appel dans `calls`
    et renvoyant une liste vide (le contenu réel n'importe pas ici, seul le
    FAIT d'avoir été appelée ou non compte)."""
    def make(name):
        def _f(*a, **k):
            calls.append(name)
            return []
        return _f
    monkeypatch.setattr(clusters, 'fetch_cluster_f5len', make('f5len'))
    monkeypatch.setattr(clusters, 'fetch_dxsummit', make('dxsummit'))
    monkeypatch.setattr(clusters, 'fetch_dxwatch_vhf', make('dxwatch'))
    monkeypatch.setattr(clusters, 'fetch_hamqth_spots', make('hamqth'))
    monkeypatch.setattr(clusters, 'fetch_hamspirit_vhf', make('hamspirit'))
    monkeypatch.setattr(clusters, 'fetch_dxmaps_spots_vhf', make('dxmaps'))


def test_toutes_sources_vhf_actives_par_defaut_si_toggles_absents(monkeypatch):
    calls = []
    _stub_all_vhf_sources(monkeypatch, calls)
    clusters.fetch_all_vhf_spots(144, True)  # sans argument toggles (repli historique)
    assert set(calls) == {'f5len', 'dxsummit', 'dxwatch', 'hamqth', 'hamspirit', 'dxmaps'}


def test_source_vhf_desactivee_nest_plus_appelee(monkeypatch):
    calls = []
    _stub_all_vhf_sources(monkeypatch, calls)
    clusters.fetch_all_vhf_spots(144, True, toggles={'src_dxmaps': False, 'src_hamspirit': False})
    assert 'dxmaps' not in calls and 'hamspirit' not in calls
    assert 'f5len' in calls and 'dxsummit' in calls and 'dxwatch' in calls and 'hamqth' in calls


def test_config_existante_sans_les_nouveaux_toggles_garde_tout_actif(monkeypatch):
    """Une config sauvegardée AVANT l'ajout de src_hamqth_spots/src_hamspirit
    n'a pas ces clés dans son dict toggles -> comportement historique
    inchangé (les deux sources restent actives, pas de régression)."""
    calls = []
    _stub_all_vhf_sources(monkeypatch, calls)
    old_toggles = {'src_f5len': True, 'src_dxsummit': True, 'mode_ssb': True}  # config "ancienne"
    clusters.fetch_all_vhf_spots(144, True, toggles=old_toggles)
    assert 'hamqth' in calls and 'hamspirit' in calls


# ─── _fetch_spots_hf_src (HF) ───────────────────────────────────────────────

def _stub_all_hf_sources(monkeypatch, calls):
    def make(name):
        def _f(*a, **k):
            calls.append(name)
            return []
        return _f
    monkeypatch.setattr(http, 'fetch_dxsummit_hf', make('dxsummit'))
    monkeypatch.setattr(http, 'fetch_f5len_hf', make('f5len'))
    monkeypatch.setattr(http, 'fetch_dxwatch_hf', make('dxwatch'))
    monkeypatch.setattr(http, 'fetch_telnet_cluster', make('telnet'))
    monkeypatch.setattr(http, 'fetch_dxheat', make('dxheat'))


def test_dxwatch_hf_desormais_reellement_appelee(monkeypatch):
    """Avant ce lot : fetch_dxwatch_hf n'était appelée nulle part (code mort)."""
    calls = []
    _stub_all_hf_sources(monkeypatch, calls)
    http._fetch_spots_hf_src('F4GLD', False, {})
    assert 'dxwatch' in calls


def test_toutes_sources_hf_actives_par_defaut(monkeypatch):
    calls = []
    _stub_all_hf_sources(monkeypatch, calls)
    http._fetch_spots_hf_src('F4GLD', False, {})
    assert set(calls) == {'dxsummit', 'f5len', 'dxwatch', 'telnet', 'dxheat'}


def test_source_hf_desactivee_nest_plus_appelee(monkeypatch):
    calls = []
    _stub_all_hf_sources(monkeypatch, calls)
    http._fetch_spots_hf_src('F4GLD', False, {'src_dxwatch': False, 'src_telnet': False})
    assert calls == ['dxsummit', 'f5len', 'dxheat']  # dxwatch et telnet sautés, jamais appelés


def test_dxheat_desactivable_individuellement(monkeypatch):
    """src_dxheat suit le même contrat que les autres toggles HF : off = jamais
    appelée, mais les autres sources continuent de tourner normalement."""
    calls = []
    _stub_all_hf_sources(monkeypatch, calls)
    http._fetch_spots_hf_src('F4GLD', False, {'src_dxheat': False})
    assert 'dxheat' not in calls
    assert set(calls) == {'dxsummit', 'f5len', 'dxwatch', 'telnet'}


def test_config_existante_sans_src_dxheat_garde_la_source_active(monkeypatch):
    """Une config sauvegardée AVANT l'ajout de DXHeat n'a pas cette clé dans
    son dict toggles -> comportement par défaut = actif, pas de régression."""
    calls = []
    _stub_all_hf_sources(monkeypatch, calls)
    old_toggles = {'src_dxsummit': True, 'src_f5len': True, 'mode_ssb': True}
    http._fetch_spots_hf_src('F4GLD', False, old_toggles)
    assert 'dxheat' in calls


# ─── _fetch_spots_50_src (6 m) ──────────────────────────────────────────────

def test_50mhz_desactive_si_f5len_off(monkeypatch):
    called = {'n': 0}
    monkeypatch.setattr(http, 'fetch_cluster_f5len', lambda *a, **k: called.update(n=called['n']+1) or [])
    s = http._fetch_spots_50_src(False, {'src_f5len': False})
    assert s == [] and called['n'] == 0


def test_50mhz_actif_par_defaut(monkeypatch):
    called = {'n': 0}
    monkeypatch.setattr(http, 'fetch_cluster_f5len', lambda *a, **k: called.update(n=called['n']+1) or [])
    http._fetch_spots_50_src(False, {})
    assert called['n'] == 1
