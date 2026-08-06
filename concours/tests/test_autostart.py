# -*- coding: utf-8 -*-
"""Tests de l'auto-lancement de logiciels tiers (logx_autostart) — process
et détection "déjà lancé" TOUJOURS injectés, jamais de vrai subprocess."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_autostart as autostart


class FakePopen:
    calls = []

    def __init__(self, args, **kwargs):
        FakePopen.calls.append({'args': args, 'kwargs': kwargs})


def _reset():
    FakePopen.calls.clear()


def test_lancer_chemin_vide():
    r = autostart.lancer({'path': ''}, popen=FakePopen)
    assert not r['ok']


def test_lancer_ok_construit_la_bonne_commande():
    _reset()
    r = autostart.lancer({'path': 'C:\\WSJT-X\\wsjtx.exe', 'args': '--rig=1'},
                         deja_lance_fn=lambda p: False, popen=FakePopen)
    assert r['ok'] and not r.get('skipped')
    assert FakePopen.calls[0]['args'] == ['C:\\WSJT-X\\wsjtx.exe', '--rig=1']


def test_lancer_args_liste_directement_acceptee():
    _reset()
    r = autostart.lancer({'path': '/usr/bin/foo', 'args': ['--a', '--b c']},
                         deja_lance_fn=lambda p: False, popen=FakePopen)
    assert r['ok']
    assert FakePopen.calls[0]['args'] == ['/usr/bin/foo', '--a', '--b c']


def test_lancer_deja_lance_ne_relance_pas():
    _reset()
    r = autostart.lancer({'path': 'wsjtx.exe'}, deja_lance_fn=lambda p: True, popen=FakePopen)
    assert r['ok'] and r['skipped']
    assert not FakePopen.calls   # AUCUN nouveau process


def test_lancer_echec_popen_ne_leve_pas():
    def _raise(args, **kw):
        raise OSError('introuvable')
    r = autostart.lancer({'path': 'x.exe'}, deja_lance_fn=lambda p: False, popen=_raise)
    assert not r['ok'] and 'introuvable' in r['error']


def test_lancer_tous_ignore_les_entrees_desactivees():
    _reset()
    cfg = {'autostart_programs': [
        {'path': 'a.exe', 'enabled': True, 'name': 'A'},
        {'path': 'b.exe', 'enabled': False, 'name': 'B'},
    ]}
    res = autostart.lancer_tous(cfg, deja_lance_fn=lambda p: False, popen=FakePopen)
    assert len(res) == 1 and res[0]['name'] == 'A'
    assert len(FakePopen.calls) == 1


def test_lancer_tous_sans_entrees():
    assert autostart.lancer_tous({}) == []
    assert autostart.lancer_tous(None) == []


def test_lancer_tous_une_entree_en_echec_n_empeche_pas_les_suivantes():
    _reset()
    cfg = {'autostart_programs': [
        {'path': '', 'name': 'Vide'},               # échoue (chemin vide)
        {'path': 'ok.exe', 'name': 'OK'},
    ]}
    res = autostart.lancer_tous(cfg, deja_lance_fn=lambda p: False, popen=FakePopen)
    assert len(res) == 2
    assert not res[0]['ok']
    assert res[1]['ok']
    assert len(FakePopen.calls) == 1   # seul "OK" a réellement lancé un process


def test_deja_lance_chemin_vide():
    assert autostart.deja_lance('') is False
    assert autostart.deja_lance(None) is False
