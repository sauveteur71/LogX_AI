# -*- coding: utf-8 -*-
"""OmniRig : modes du carnet non mappés + mode inconnu avalé (logx_omnirig.py) — Strate 2, haute.

MODE_TO_PARAM ne connaissait que CW/USB/LSB/DATA/AM/FM : les modes réels du
carnet (FT8, FT4, PSK, JT65…) n'étaient JAMAIS mappés, donc jamais appliqués.
De plus set_freq() renvoyait ok:True même quand le mode fourni était inconnu
(mode NON réglé, succès annoncé) — incohérent avec set_mode().

Correctif (validé F4GLD) : les modes numériques bande latérale HAUTE (famille
FT8) sont normalisés vers DATA (USB-D) ; un mode inconnu fait ok:False.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_omnirig as om   # noqa: E402


class _FakeRig:
    def __init__(self):
        self.Status = om.ST_ONLINE
        self.Freq = None
        self.Mode = None


def _patch(monkeypatch):
    fake = _FakeRig()
    monkeypatch.setattr(om, '_com_call', lambda rig_num, fn: fn(fake))
    monkeypatch.setattr(om, 'omnirig_settings', lambda cfg: {'enabled': True, 'rig_num': 1})
    return fake


def test_set_freq_ft8_mappe_vers_data(monkeypatch):
    fake = _patch(monkeypatch)
    r = om.set_freq({}, 14074000, mode='FT8')
    assert r.get('ok') is True and fake.Mode == om.PM_DIG_U, (
        "FT8 doit être appliqué comme DATA (USB-D) : %r / Mode=%r" % (r, fake.Mode)
    )


def test_set_freq_mode_inconnu_ne_renvoie_pas_ok(monkeypatch):
    _patch(monkeypatch)
    r = om.set_freq({}, 14074000, mode='ZZZINCONNU')
    assert r.get('ok') is False, "un mode inconnu ne doit plus être avalé en ok:True"


def test_set_mode_ft8_mappe_vers_data(monkeypatch):
    fake = _patch(monkeypatch)
    r = om.set_mode({}, 'FT8')
    assert r.get('ok') is True and fake.Mode == om.PM_DIG_U


def test_set_freq_usb_toujours_ok(monkeypatch):
    fake = _patch(monkeypatch)
    r = om.set_freq({}, 14074000, mode='USB')
    assert r.get('ok') is True and fake.Mode == om.PM_SSB_U
