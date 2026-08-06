# -*- coding: utf-8 -*-
"""Dispatch CAT propriétaire (OmniRig/FlexRadio/Icom-remote) + PowerGenius XL
dans logx_http.py — vérifie que _rig_state_dict_impl() route vers le bon
module selon cat_mode, et que _pgxl_state_dict() délègue à logx_powergenius,
sur le même motif que les tests de dispatch tci/flrig/rigctld déjà existants
(voir tests/test_voicekeyer.py pour le même principe côté PTT)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as http


def test_rig_state_dict_impl_dispatch_omnirig(monkeypatch):
    import logx_cat as cat
    import logx_omnirig as omnirig
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'omnirig'})
    monkeypatch.setattr(omnirig, 'get_state', lambda cfg: {'ok': True, 'via': 'omnirig'})
    assert http._rig_state_dict_impl({}) == {'ok': True, 'via': 'omnirig'}


def test_rig_state_dict_impl_dispatch_flex(monkeypatch):
    import logx_cat as cat
    import logx_flexradio as flexradio
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'flex'})
    monkeypatch.setattr(flexradio, 'get_state', lambda cfg: {'ok': True, 'via': 'flex'})
    assert http._rig_state_dict_impl({}) == {'ok': True, 'via': 'flex'}


def test_rig_state_dict_impl_dispatch_icom_remote(monkeypatch):
    import logx_cat as cat
    import logx_icomremote as icomremote
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'icom_remote'})
    monkeypatch.setattr(icomremote, 'get_state', lambda cfg: {'ok': False, 'via': 'icom_remote'})
    assert http._rig_state_dict_impl({}) == {'ok': False, 'via': 'icom_remote'}


def test_rig_state_dict_impl_mode_inconnu_retombe_sur_rigctld(monkeypatch):
    """Un cat_mode qui ne correspond à AUCUNE des 6 valeurs connues (config
    corrompue, ancienne valeur retirée...) doit retomber sur le comportement
    historique (rigctld) plutôt que de lever une exception — même garantie
    que pour les 4 modes préexistants."""
    import logx_cat as cat
    import logx_rig as rig
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'inconnu'})
    monkeypatch.setattr(rig, 'rig_settings', lambda cfg: {'enabled': False})
    assert http._rig_state_dict_impl({}) == {'enabled': False}


def test_pgxl_state_dict_delegue_a_powergenius(monkeypatch):
    import logx_powergenius as pgxl
    monkeypatch.setattr(pgxl, 'get_state', lambda cfg: {'ok': True, 'fwd_dbm': 45.2})
    assert http._pgxl_state_dict({}) == {'ok': True, 'fwd_dbm': 45.2}
