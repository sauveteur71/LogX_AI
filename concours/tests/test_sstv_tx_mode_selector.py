# -*- coding: utf-8 -*-
"""Sélecteur de mode d'ÉMISSION SSTV (Task 8, Lot B4).

Les tâches 5-7 ont ajouté 9 modes à SSTV_MODES_PAR_NOM dans
logx_sstvdecoder.js (M3/M4, S3/S4, R8BW/R12BW/R24BW, SC2_120/SC2_180). La
RÉCEPTION les gère déjà automatiquement (détection VIS). Reste l'ÉMISSION :
remplirSstvModeSelect() (logx_sstv_panel.js) construit le <select
id="sstvTxMode"> -- il faut vérifier que les nouveaux modes y sont proposables.

Investigation (avant d'écrire quoi que ce soit) : remplirSstvModeSelect()
énumère `Object.keys(SSTV_MODES_PAR_NOM)` (pas une liste littérale figée) --
voir logx_sstv_panel.js:151. Les 9 nouveaux modes apparaissent donc SANS
modification de logx_sstv_panel.js/logx_sstv.html. Aucun changement de
production n'a été fait pour cette tâche ; ce test verrouille le comportement
DYNAMIQUE pour qu'une future régression (retour à une liste littérale, filtre
oublié...) soit détectée.

Le test exécute la VRAIE fonction (extraite par source, comme
test_sstv_revoke_differe.py) contre la VRAIE table SSTV_MODES_PAR_NOM
(chargée depuis logx_sstvdecoder.js, jamais rejouée à la main) -- un
mannequin qui réimplémenterait l'énumération ne contraindrait que lui-même
(piège documenté dans CLAUDE.md)."""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL_JS = os.path.join(CONCOURS, 'logx_sstv_panel.js')
DECODER_JS = os.path.join(CONCOURS, 'logx_sstvdecoder.js')

# Les 9 modes ajoutés par les tâches 5-7 (Lot B) -- la preuve concrète que le
# sélecteur les propose déjà.
NOUVEAUX_MODES_LOT_B = ['M3', 'M4', 'S3', 'S4', 'R8BW', 'R12BW', 'R24BW',
                         'SC2_120', 'SC2_180']


def _fn(src, nom):
    m = re.search(r'\n\s*function ' + re.escape(nom) + r'\s*\(', src)
    assert m, nom
    i = src.index('function', m.start())
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[i:k + 1]
    raise AssertionError


def _contexte():
    """document.getElementById('sstvTxMode') renvoie un faux <select> qui
    capture innerHTML ; SSTV_MODES_PAR_NOM est la vraie table du décodeur."""
    c = py_mini_racer.MiniRacer()
    with open(DECODER_JS, encoding='utf-8') as f:
        c.eval(f.read())
    c.eval("""
        var _sstvModeSelectRempli = false;
        var _sel = { innerHTML: '' };
        var document = { getElementById: function(id){
            return id === 'sstvTxMode' ? _sel : null;
        }};
        function escHtml(s){ return s; }
    """)
    c.eval(_fn(open(PANEL_JS, encoding='utf-8').read(), 'remplirSstvModeSelect'))
    return c


def test_selecteur_tx_derive_dynamiquement_de_toute_la_table_des_modes():
    """remplirSstvModeSelect() doit proposer TOUTES les clés de
    SSTV_MODES_PAR_NOM, sans exception -- preuve que l'énumération est
    dynamique (Object.keys) et non une liste littérale figée qui aurait pu
    oublier les modes ajoutés après son écriture."""
    c = _contexte()
    c.eval("remplirSstvModeSelect()")
    html = c.eval("_sel.innerHTML")
    cles = json.loads(c.eval("JSON.stringify(Object.keys(SSTV_MODES_PAR_NOM))"))
    # 14 modes historiques + 9 modes Lot B = 23. Si ce total régresse, la
    # table SSTV_MODES_PAR_NOM elle-même a perdu des entrées (hors scope de
    # cette tâche mais alerte utile).
    assert len(cles) >= 23, 'la table SSTV_MODES_PAR_NOM a régressé (%d clés)' % len(cles)
    for cle in cles:
        assert 'value="%s"' % cle in html, cle + ' absent du sélecteur TX (sstvTxMode)'


def test_les_9_nouveaux_modes_du_lot_b_sont_selectionnables_en_emission():
    """Preuve ciblée, nommant chaque mode ajouté par les tâches 5-7 --
    contrairement au test précédent (générique sur toute la table), un
    oubli précis d'UN mode dans SSTV_MODES_PAR_NOM ferait échouer CE test-ci
    avec un message qui le nomme."""
    c = _contexte()
    c.eval("remplirSstvModeSelect()")
    html = c.eval("_sel.innerHTML")
    cles = json.loads(c.eval("JSON.stringify(Object.keys(SSTV_MODES_PAR_NOM))"))
    for mode in NOUVEAUX_MODES_LOT_B:
        assert mode in cles, mode + ' absent de SSTV_MODES_PAR_NOM (régression Tasks 5-7 ?)'
        assert 'value="%s"' % mode in html, mode + ' absent du sélecteur TX (sstvTxMode)'
