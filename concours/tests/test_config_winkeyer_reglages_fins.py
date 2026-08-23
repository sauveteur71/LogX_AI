# -*- coding: utf-8 -*-
"""Réglages fins WinKeyer côté CONFIG (Phase 2C) : câblage HTML/save/load.

Les 6 champs (weighting/ratio/Farnsworth/sidetone/PTT lead/PTT tail) doivent
être présents dans le HTML (input), collectés à la SAUVEGARDE et repeuplés au
CHARGEMENT — sinon un réglage saisi serait perdu ou jamais réaffiché. Test
structurel (source) : attrape le classique « ajouté au save, oublié au load ».
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_CHAMPS = ['winkeyer_weighting', 'winkeyer_ratio', 'winkeyer_farnsworth',
           'winkeyer_sidetone_hz', 'winkeyer_ptt_lead_ms', 'winkeyer_ptt_tail_ms']


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


def test_champs_presents_dans_le_html():
    html = _lire('logx_configuration.html')
    for c in _CHAMPS:
        assert re.search(r'id="%s"[^>]*type="number"|type="number"[^>]*id="%s"' % (c, c), html), c


def test_champs_collectes_a_la_sauvegarde():
    js = _lire('logx_configuration.js')
    for c in _CHAMPS:
        assert re.search(r'%s:\s*_numClamped\(' % c, js), 'save manquant: ' + c


def test_champs_repeuples_au_chargement():
    js = _lire('logx_configuration.js')
    # STRUCTURE, pas présence : on isole la LISTE de population du LOAD (celle
    # qui contient 'winkeyer_enabled' et se termine par ].forEach(k=>{ …c[k]),
    # et on vérifie l'appartenance DEDANS — sinon une occurrence quotée ailleurs
    # (save/i18n) suffirait à valider un champ pourtant retiré du chargement.
    m = re.search(r"\[([^\[\]]*?'winkeyer_enabled'.*?)\]\.forEach\(k\s*=>", js, re.S)
    assert m, 'liste de population du LOAD introuvable'
    liste = m.group(1)
    for c in _CHAMPS:
        assert ("'%s'" % c) in liste, 'load manquant: ' + c


def test_chaque_champ_a_une_aide():
    js = _lire('logx_configuration.js')
    for c in _CHAMPS:
        assert re.search(r'\b%s:\s*"' % c, js), 'description manquante: ' + c
