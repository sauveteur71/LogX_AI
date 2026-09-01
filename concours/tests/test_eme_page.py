# -*- coding: utf-8 -*-
"""Fonctions JS pures du cockpit EME (hors DOM)."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(CONCOURS, 'logx_eme.html')


def _extraire_script(html, marqueur):
    # Le premier <script> contenant le marqueur (fonctions pures).
    for m in re.finditer(r'<script>(.*?)</script>', html, re.S):
        if marqueur in m.group(1):
            return m.group(1)
    raise AssertionError('script pur introuvable')


@pytest.fixture(scope='module')
def ctx():
    from py_mini_racer import py_mini_racer
    with open(PAGE, encoding='utf-8') as f:
        html = f.read()
    js = _extraire_script(html, 'function dopplerLabel')
    c = py_mini_racer.MiniRacer()
    c.eval('var window = {};')
    c.eval(js)
    return c


def test_dopplerLabel_signe_et_arrondi(ctx):
    assert ctx.eval('dopplerLabel(-412.4)') == '-412 Hz'
    assert ctx.eval('dopplerLabel(37.8)') == '+38 Hz'
    assert ctx.eval('dopplerLabel(null)') == '—'


def test_formatDecode_ligne_compacte(ctx):
    ligne = ctx.eval("formatDecode({call:'DL7APV', snr:-24, mode:'Q65', freq_mhz:432.071})")
    assert 'DL7APV' in ligne and '-24 dB' in ligne and 'Q65' in ligne


def test_la_page_charge_le_theme_et_le_garde(ctx):
    with open(PAGE, encoding='utf-8') as f:
        html = f.read()
    assert 'logx_theme.css' in html
    assert 'logx_theme_guard.js' in html
    # Vocabulaire : pas d'"activation"/"activateur" en texte visible.
    assert 'activateur' not in html.lower()


def _corps_renderDecodes(html):
    """Isole le CORPS de renderDecodes (entre sa signature et le commentaire
    de section suivant), commentaires // dépouillés — pour vérifier la
    STRUCTURE réelle du garde-fou (pas une simple présence de texte, qui
    serait satisfaite par un commentaire l'expliquant sans le faire)."""
    m = re.search(
        r'function renderDecodes\(([^)]*)\)\s*\{(.*?)\n\s*//\s*──\s*TRANSVERTER',
        html, re.S)
    assert m, 'function renderDecodes introuvable'
    signature, corps = m.group(1), m.group(2)
    corps_sans_commentaires = re.sub(r'//[^\n]*', '', corps)
    return signature, corps_sans_commentaires


def test_renderDecodes_source_parametre_present():
    # Finding C1 : renderDecodes doit recevoir la source ('wsjtx'/'natif')
    # pour distinguer le pont WSJT-X du moteur natif.
    with open(PAGE, encoding='utf-8') as f:
        html = f.read()
    signature, _ = _corps_renderDecodes(html)
    params = [p.strip() for p in signature.split(',')]
    assert params == ['decodes', 'rig', 'source']


def test_renderDecodes_garde_wsjtx_ne_court_circuite_pas_le_mode_natif():
    # Le bloc "WSJT-X non relié" ne doit se déclencher qu'en mode wsjtx —
    # assertion STRUCTURELLE sur la condition réelle du if (pas juste la
    # présence du mot 'natif' quelque part dans la fonction, qui serait
    # satisfaite par un commentaire ou un if(false) mort).
    with open(PAGE, encoding='utf-8') as f:
        html = f.read()
    _, corps = _corps_renderDecodes(html)
    # Parenthèses imbriquées possibles (ex. `(!rig || !rig.connected)`) : on
    # capture donc jusqu'à 1 niveau d'imbrication, pas juste jusqu'à la
    # première parenthèse fermante — puis on vérifie que c'est bien LE if qui
    # teste rig.connected (le premier if de la fonction).
    m = re.search(r"if\s*\(((?:[^()]|\([^()]*\))*)\)\s*\{", corps)
    assert m, 'aucun if trouvé en tête de renderDecodes'
    condition = m.group(1)
    assert 'rig.connected' in condition, (
        'le premier if de renderDecodes ne teste plus rig.connected : ' + condition)
    # La garde doit exclure explicitement le mode natif de la condition.
    assert "source !== 'natif'" in condition
    assert '&&' in condition  # combinée, pas un OR qui la rendrait inopérante

    # Le rendu des lignes de décodage (.map) doit rester ATTEIGNABLE après la
    # garde : structurellement présent hors du bloc if précédent, donc
    # exécuté quand source === 'natif' fait échouer la condition ci-dessus.
    assert '.map(' in corps
    assert corps.index('.map(') > corps.index(condition)


def test_renderDecodes_empty_state_natif_distinct():
    # En mode natif sans décodage, un empty-state DÉDIÉ (pas la redite du
    # message "WSJT-X non relié", ni le générique wsjtx silencieux).
    with open(PAGE, encoding='utf-8') as f:
        html = f.read()
    _, corps = _corps_renderDecodes(html)
    assert "source === 'natif'" in corps
    assert 'Moteur natif' in corps


def test_poll_transmet_la_source_a_renderDecodes():
    with open(PAGE, encoding='utf-8') as f:
        html = f.read()
    assert 'renderDecodes(d.decodes || [], d.rig, d.source)' in html
