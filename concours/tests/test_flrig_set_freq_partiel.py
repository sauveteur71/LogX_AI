# -*- coding: utf-8 -*-
"""set_freq() masque un succès partiel (logx_flrig.py) — Strate 2, moyenne.

set_freq() réglait la fréquence PUIS le mode dans le même try. Si set_mode()
levait (mode non supporté par flrig/la radio), l'exception était rattrapée et la
fonction renvoyait ok:False — alors que la fréquence, elle, AVAIT déjà été
réglée. Le QSY apparaissait échoué à l'appelant/à l'UI, qui ne pouvait pas
savoir que la fréquence avait bougé.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_flrig as flrig   # noqa: E402


class _FakeRig:
    def __init__(self, mode_raises=False, freq_raises=False):
        self.mode_raises = mode_raises
        self.freq_raises = freq_raises
        self.freq = None
        self.mode = None

    def set_frequency(self, f):
        if self.freq_raises:
            raise RuntimeError('freq fail')
        self.freq = f

    def set_mode(self, m):
        if self.mode_raises:
            raise RuntimeError('mode non supporté')
        self.mode = m


class _FakeProxy:
    def __init__(self, rig):
        self.rig = rig


def test_freq_reglee_meme_si_le_mode_echoue(monkeypatch):
    fake = _FakeRig(mode_raises=True)
    monkeypatch.setattr(flrig, '_proxy', lambda host, port: _FakeProxy(fake))
    r = flrig.set_freq('h', 1, 14074000, mode='FT8')
    assert fake.freq == 14074000.0, "la fréquence aurait dû être réglée"
    assert r.get('freq_set') is True, (
        "l'échec de mode ne doit pas masquer que la fréquence a été réglée"
    )
    assert r.get('ok') is False


def test_set_freq_ok_nominal(monkeypatch):
    fake = _FakeRig()
    monkeypatch.setattr(flrig, '_proxy', lambda host, port: _FakeProxy(fake))
    r = flrig.set_freq('h', 1, 14074000, mode='USB')
    assert r.get('ok') is True and fake.freq == 14074000.0 and fake.mode == 'USB'
