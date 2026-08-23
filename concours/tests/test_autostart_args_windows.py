# -*- coding: utf-8 -*-
"""shlex.split() POSIX détruit les backslashes des chemins Windows.

`shlex.split(r'--config C:\\Users\\op\\rig.ini')` (posix=True, défaut) rend
`['--config', 'C:Usersoprig.ini']` : le backslash est traité comme échappement
et avalé. Un autostart Windows (WSJT-X, N1MM…) lançait donc les programmes avec
des chemins d'arguments faux. Le découpage est extrait dans `_split_args` pour
être testé de façon déterministe quel que soit l'OS de la CI (Linux).
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_autostart as A   # noqa: E402


def test_split_args_preserve_backslashes_windows():
    got = A._split_args(r'--config C:\Users\op\rig.ini', system='Windows')
    assert got == ['--config', r'C:\Users\op\rig.ini']


def test_split_args_windows_retire_guillemets_entourage():
    # un chemin avec espace est entre guillemets : posix=False les garde dans le
    # token, on les retire à la main pour ne pas les passer à CreateProcess.
    got = A._split_args(r'"C:\a b\x.ini" --flag', system='Windows')
    assert got == [r'C:\a b\x.ini', '--flag']


def test_split_args_posix_ailleurs():
    got = A._split_args('--rig-name foo bar', system='Linux')
    assert got == ['--rig-name', 'foo', 'bar']


def test_split_args_liste_inchangee():
    assert A._split_args(['--a', 'b'], system='Windows') == ['--a', 'b']
    assert A._split_args(None, system='Windows') == []
