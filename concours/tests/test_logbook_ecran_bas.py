# -*- coding: utf-8 -*-
"""LOGBOOK en 1366×768 : saisie et ENREGISTRER visibles sans défiler
(audit 25/11/2026 — mesuré en navigateur : indicatif à 606 px, ENREGISTRER à
999 px ; après correctif 720-760 px en concours, 749 px en activité portable).

Trois leviers, aucun ne masque le chemin critique :
  1. le bloc chasseur/portable + réf. correspondant suit l'ACTIVITÉ ;
  2. MODE sur la même ligne que BANDE ;
  3. marges resserrées sous 820 px de haut (@media), bandeaux de rythme sur
     une ligne (libellés en infobulle).
Fonctions EXTRAITES des sources ; mise en page contrôlée sur la STRUCTURE.
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
    m = re.search(r'\n\s*function ' + re.escape(nom) + r'\s*\(', src)
    assert m, nom
    i = src.index('function', m.start())
    j, prof = src.index('{', i), 0
    for k in range(j, len(src)):
        prof += {'{': 1, '}': -1}.get(src[k], 0)
        if prof == 0:
            return src[i:k + 1]


def _ctx(activite=None, role=None, chaser_cfg=None, activation=('', '')):
    c = py_mini_racer.MiniRacer()
    st = {}
    if activite:
        st['logx_activity'] = activite
    if role:
        st['logx_xota_role'] = role
    if chaser_cfg:
        st['logx_config'] = '{"chaser_mode":"%s"}' % chaser_cfg
    c.eval("""
      var __st = %r;
      var localStorage = {getItem: function(k){ return k in __st ? __st[k] : null; },
                          setItem: function(k, v){ __st[k] = String(v); }};
      var window = this; this.localStorage = localStorage;
      var __sw = {hidden: true, innerHTML: ''};
      var document = {getElementById: function(id){ return id === 'xotaRoleSwitch' ? __sw : null; }};
      var activationProgram = %r, myActivationRef = %r;
    """ % (st, activation[0], activation[1]))
    c.eval(_src('logx_xota_role.js'))
    lb = _src('logx_logbook.js')
    c.eval(_fn(lb, '_activiteEstXota'))
    c.eval(_fn(lb, 'chaserModeActif'))
    c.eval(_fn(_src('logx_activation_ui.js'), 'renderXotaRoleSwitch'))
    return c


def test_hors_activite_portable_pas_de_bloc_chasse():
    c = _ctx()
    assert c.eval('chaserModeActif()') is False
    c.eval('renderXotaRoleSwitch()')
    assert c.eval('__sw.hidden') is True


def test_activite_portable_bloc_present_selon_le_role():
    assert _ctx('iota_pota').eval('chaserModeActif()') is True            # défaut « les deux »
    assert _ctx('iota_pota', 'chasse').eval('chaserModeActif()') is True
    assert _ctx('iota_pota', 'portable').eval('chaserModeActif()') is False
    c = _ctx('iota_pota')
    c.eval('renderXotaRoleSwitch()')
    assert c.eval('__sw.hidden') is False and 'basculerRoleXota' in c.eval('__sw.innerHTML')


def test_choix_explicite_config_toujours_respecte():
    assert _ctx(chaser_cfg='oui').eval('chaserModeActif()') is True


def test_activation_en_cours_montre_la_bascule():
    c = _ctx(activation=('SOTA', 'F/AB-001'))
    c.eval('renderXotaRoleSwitch()')
    assert c.eval('__sw.hidden') is False


def test_activation_rafraichit_la_bascule():
    corps = _sans_commentaires_js(_fn(_src('logx_logbook.js'), 'applyActivationMode'))
    assert re.search(r"if\(typeof renderXotaRoleSwitch === 'function'\) renderXotaRoleSwitch\(\);", corps)


# ── mise en page ─────────────────────────────────────────────────────────────

def _html():
    return re.sub(r'<!--.*?-->', '', _src('logx_logbook.html'), flags=re.S)


def test_mode_sur_la_ligne_de_la_bande():
    h = _html()
    i = h.index('id="bandCurrentBtn"')
    debut = h.rfind('<div class="field-row">', 0, i)
    assert debut >= 0
    # fin de la ligne : premier </div> au niveau de la ligne
    prof, k = 0, debut
    for m in re.finditer(r'<div\b|</div>', h[debut:]):
        prof += 1 if m.group(0) == '<div' else -1
        if prof == 0:
            k = debut + m.end()
            break
    ligne = h[debut:k]
    assert 'id="bandCurrentBtn"' in ligne and 'id="modeCurrentBtn"' in ligne
    assert h.count('id="modeCurrentBtn"') == 1


def test_resserrement_ecran_bas_sans_masquer_la_saisie():
    css = re.sub(r'/\*.*?\*/', '', _html(), flags=re.S)
    m = re.search(r'@media \(max-height:820px\)\{(.*?)\n\}', css, re.S)
    assert m, 'bloc @media écran bas absent'
    bloc = m.group(1)
    assert '.saisie-form .field-input{padding-top:3px;padding-bottom:3px}' in bloc
    assert '#hourChartSvg{height:24px}' in bloc
    assert '.brd-lbl,.ops-lbl{display:none}' in bloc
    # Le chemin critique n'est JAMAIS masqué par ce bloc.
    for sel in ('inputCall', 'submitBtn', 'inputNumRcvd', 'inputRSTsent', 'field-input',
                'submit-btn', 'field-group', 'saisie-form{', 'saisie-panel'):
        assert not re.search(re.escape(sel) + r'[^{]*\{[^}]*display:\s*none', bloc), sel


def test_libelles_masques_repris_en_infobulle():
    s = _sans_commentaires_js(_src('logx_stats_bars.js'))
    assert "div.title = 'QSO · KM TOTAL · DX MAX';" in s
    assert 'title="QSO · PTS"' in s
    assert re.search(r"getElementById\('sbQso'\)\.title\s*=\s*qsoVal;", _src('logx_logbook.js'))


def test_bouton_occupation_ne_couvre_plus_la_saisie():
    css = re.sub(r'/\*.*?\*/', '', _html(), flags=re.S)
    assert re.search(r'#occupationToggle\{left:calc\(max\(432px, min\(48%, 855px\)\) \+ 14px\)\}', css)
