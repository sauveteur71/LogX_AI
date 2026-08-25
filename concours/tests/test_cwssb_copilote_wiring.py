# -*- coding: utf-8 -*-
"""Câblage du copilote CW/SSB dans le LOGBOOK. Vérifie la présence (inclusion +
interrupteur opt-in + hook « indicatif résolu ») ET verrouille la propriété de
SÛRETÉ centrale : on ne fait que PROPOSER — les seules émissions (cwEnvoyerTexte
en CW, /rig/voice en phonie) sont DANS le callback de confirmation (ÉMETTRE),
jamais un appel direct qui émettrait tout seul.
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(BASE, 'logx_logbook.html')
MACROS = os.path.join(BASE, 'logx_macros.js')
LOOKUP = os.path.join(BASE, 'logx_lookup.js')


def _lire(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def test_inclusion_et_interrupteur_optin():
    html = _lire(HTML)
    assert 'logx_cwssb_copilote.js' in html                 # module inclus
    assert 'id="copiloteCwSsbBtn"' in html                  # interrupteur opt-in
    assert 'toggleCopiloteCwSsb()' in html                  # bascule câblée


def test_hook_sur_indicatif_resolu():
    lookup = _lire(LOOKUP)
    # le copilote est déclenché depuis applyCallData (indicatif RÉSOLU), pas à
    # chaque frappe — via garde typeof (le câblage vit dans logx_macros.js).
    assert re.search(r"if\(typeof proposerEchangeCopilote === 'function'\) proposerEchangeCopilote\(\);", lookup)
    m = re.search(r'function applyCallData\(.*?\n\}', lookup, re.S)
    assert m and 'proposerEchangeCopilote()' in m.group(0), "hook absent d'applyCallData"


def test_optin_gate_present():
    macros = _lire(MACROS)
    m = re.search(r'function proposerEchangeCopilote\(.*?\n\}', macros, re.S)
    assert m, 'proposerEchangeCopilote introuvable'
    corps = m.group(0)
    # éteint par défaut : sort immédiatement si le copilote n'est pas actif
    assert re.search(r'if\(!copiloteCwSsbActif\(\)\) return;', corps)


def test_propose_only_aucune_emission_directe():
    """SÛRETÉ : dans proposerEchangeCopilote, les émissions (cwEnvoyerTexte,
    _voixEchangeCopilote) ne doivent apparaître QUE dans le callback passé à
    LogxTxBar.proposer (déclenché par ÉMETTRE), jamais en tête d'instruction."""
    macros = _lire(MACROS)
    m = re.search(r'function proposerEchangeCopilote\(.*?\n\}', macros, re.S)
    assert m, 'proposerEchangeCopilote introuvable'
    corps = m.group(0)
    assert 'LogxTxBar.proposer(' in corps
    for ligne in corps.splitlines():
        if 'cwEnvoyerTexte(' in ligne or '_voixEchangeCopilote(' in ligne:
            assert 'function(){' in ligne or 'function () {' in ligne, (
                "émission copilote CW/SSB hors du callback ÉMETTRE (auto-émission "
                "possible) : %r" % ligne.strip())
