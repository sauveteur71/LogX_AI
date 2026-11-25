# -*- coding: utf-8 -*-
"""Champs pré-remplis rattachés à leur indicatif (audit F4GLD, 25/11/2026).

Défaut mesuré dans le vrai carnet : le locator / prénom / département
pré-remplis pour un correspondant restaient dans la saisie quand on tapait
l'indicatif suivant (EA7IXM enregistré avec le locator d'IQ2AAH, un même
prénom attribué à quatre indicatifs).

Le module logx_champs_auto.js est chargé TEL QUEL ; onCallInput() est extrait
de logx_logbook.js (pas réimplémenté). Les remplisseurs (applyCallData,
remoteCallLookup, lookupQRZ) sont contraints sur leur STRUCTURE, commentaires
retirés.
"""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
py_mini_racer = pytest.importorskip('py_mini_racer')


def _src(nom):
    with open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        return f.read()


def _sans_commentaires_js(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'(?m)(^|[^:\'"\\])//.*$', r'\1', s)


def _fn(src, nom):
    m = re.search(r'\n\s*(async\s+)?function ' + re.escape(nom) + r'\s*\(', src)
    assert m, 'fonction %s introuvable' % nom
    i = src.index('function', m.start())
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return ('async ' if m.group(1) else '') + src[i:k + 1]
    raise AssertionError('accolade fermante introuvable')


# Champs avec un `dataset` qui se comporte comme celui du navigateur sur le
# point utile : clés absentes = undefined, `delete` les retire.
_DOM = r"""
var __els = {};
function __champ(id){ return __els[id] = {id:id, value:'', dataset:{},
  setSelectionRange:function(){}, selectionStart:0, selectionEnd:0,
  classList:{add:function(){}, remove:function(){}}, focus:function(){}}; }
['inputCall','inputLocator','inputName','inputNumRcvd'].forEach(__champ);
var document = {getElementById: function(id){ return __els[id] || null; }};
var window = this;
var __locRecalc = 0;
function onLocatorInput(){ __locRecalc++; }
"""


def _ctx():
    c = py_mini_racer.MiniRacer()
    c.eval(_DOM)
    c.eval(_src('logx_champs_auto.js'))
    return c


def test_valeur_auto_d_un_autre_indicatif_retiree():
    c = _ctx()
    c.eval("LogxChampsAuto.poser(__els.inputLocator, 'JN15AA', 'f4abc');"
           "LogxChampsAuto.poser(__els.inputName, 'Paul', 'F4ABC');"
           "LogxChampsAuto.poser(__els.inputNumRcvd, '43', 'F4ABC');")
    vides = c.eval("LogxChampsAuto.purger('DL1XYZ').join(',')")
    assert vides == 'inputLocator,inputName,inputNumRcvd'
    assert c.eval("__els.inputLocator.value + '|' + __els.inputName.value + '|' + __els.inputNumRcvd.value") == '||'
    assert c.eval("__locRecalc") == 1          # distance / cap effacés
    assert c.eval("__els.inputLocator.dataset.autoPour === undefined") is True


def test_meme_indicatif_garde_la_valeur():
    c = _ctx()
    c.eval("LogxChampsAuto.poser(__els.inputLocator, 'JN15AA', ' f4abc ');")
    assert c.eval("LogxChampsAuto.purger('F4ABC').length") == 0
    assert c.eval("__els.inputLocator.value") == 'JN15AA'
    assert c.eval("__locRecalc") == 0


def test_valeur_retouchee_par_l_operateur_conservee():
    c = _ctx()
    c.eval("LogxChampsAuto.poser(__els.inputName, 'Paul', 'F4ABC');"
           "__els.inputName.value = 'Pierre';")
    assert c.eval("LogxChampsAuto.purger('DL1XYZ').length") == 0
    assert c.eval("__els.inputName.value") == 'Pierre'
    # Devenue la sienne : un changement d'indicatif ultérieur ne l'efface pas non plus.
    assert c.eval("LogxChampsAuto.purger('EA8XX').length") == 0
    assert c.eval("__els.inputName.value") == 'Pierre'


def test_champ_saisi_a_la_main_jamais_touche():
    c = _ctx()
    c.eval("__els.inputLocator.value = 'JN25AB';")
    assert c.eval("LogxChampsAuto.purger('DL1XYZ').length") == 0
    assert c.eval("__els.inputLocator.value") == 'JN25AB'


def test_onCallInput_reel_purge_au_changement_d_indicatif():
    c = _ctx()
    c.eval(_fn(_src('logx_logbook.js'), 'onCallInput'))
    c.eval("LogxChampsAuto.poser(__els.inputLocator, 'JN61SR', 'IQ2AAH');"
           "__els.inputCall.value = 'EA7IXM';")
    # La suite de onCallInput appelle des dizaines de services de la page :
    # seul compte ce qui est fait avant (réécriture + purge).
    c.eval("try{ onCallInput(); }catch(e){}")
    assert c.eval("__els.inputLocator.value") == ''


# ── câblage des remplisseurs ─────────────────────────────────────────────────

def test_applyCallData_pose_via_poserAuto():
    corps = _fn(_sans_commentaires_js(_src('logx_lookup.js')), 'applyCallData')
    assert re.search(r"_poserAuto\(locField,\s*loc,\s*callField \? callField\.value : ''\)", corps)
    assert re.search(r"_poserAuto\(numR,\s*dept,", corps)
    assert re.search(r"_poserAuto\(nameField,\s*nm,", corps)
    assert not re.search(r'(locField|nameField|numR)\.value\s*=(?!=)', corps)


def test_remoteCallLookup_pose_le_prenom_via_poserAuto():
    corps = _fn(_sans_commentaires_js(_src('logx_lookup.js')), 'remoteCallLookup')
    assert re.search(r'_poserAuto\(nameEl,\s*d\.name,\s*call\)', corps)
    assert not re.search(r'nameEl\.value\s*=(?!=)', corps)


def test_lookupQRZ_pose_locator_et_prenom_via_poserAuto():
    corps = _fn(_sans_commentaires_js(_src('logx_callbook.js')), 'lookupQRZ')
    # Repli seulement si le module de lookup est absent : `if(...) poser; else value=`.
    for el, v in (('locInput', 'd.grid'), ('nameInput', 'd.name')):
        assert re.search(r"if\(typeof _poserAuto === 'function'\) _poserAuto\(%s,\s*%s,\s*call\);"
                         r"\s*else %s\.value = %s;" % (el, re.escape(v), el, re.escape(v)), corps), el


def test_poserAuto_delegue_au_module():
    c = _ctx()
    c.eval(_fn(_src('logx_lookup.js'), '_poserAuto'))
    c.eval("_poserAuto(__els.inputName, 'Paul', 'F4ABC')")
    assert c.eval("__els.inputName.dataset.autoPour") == 'F4ABC'


def test_module_charge_avant_les_remplisseurs():
    h = _src('logx_logbook.html')
    i = h.index('src="logx_champs_auto.js"')
    assert i < h.index('src="logx_callbook.js"') and i < h.index('src="logx_lookup.js"')
    js = _sans_commentaires_js(_fn(_src('logx_logbook.js'), 'onCallInput'))
    assert re.search(r'LogxChampsAuto\.purger\(call\)', js)
