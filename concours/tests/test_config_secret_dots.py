# -*- coding: utf-8 -*-
"""Point coloré « configuré / vide » sur les 17 champs de SECRET_CONFIG_FIELDS
(CONFIG) -- retour F4GLD (16/08/2026, capture d'écran QSL & DIPLÔMES) :
« difficile de voir ce qui a été rempli ou pas ». _refreshSecretDot()/
_refreshAllSecretDots() posent/retirent la classe .secret-dot.set selon que
le champ a une valeur, indépendamment de type="password" (dots masqués) ou
type="text" (clé API/code, sans masquage visuel du tout).

Exécute le VRAI code (extrait par comptage d'accolades, même technique que
tests/test_config_category_switch.py) dans un moteur JS réel (V8 via
py_mini_racer)."""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_configuration.js')

with open(JS_PATH, encoding='utf-8') as _f:
    _JS_SRC = _f.read()


def _extract_function(src, name):
    m = re.search(r'^function %s\(' % re.escape(name), src, re.M)
    assert m, 'fonction %s introuvable dans %s' % (name, JS_PATH)
    depth = 0
    i = src.index('{', m.start())
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[m.start():i + 1]
        i += 1


_SECRET_FIELDS_SRC = re.search(r'^const SECRET_CONFIG_FIELDS = \[.*?\];', _JS_SRC, re.S | re.M).group(0)
_REFRESHDOT_SRC = _extract_function(_JS_SRC, '_refreshSecretDot')
_REFRESHALL_SRC = _extract_function(_JS_SRC, '_refreshAllSecretDots')

# DOM factice minimal : un champ = {value}, son point = {_classes: [...]}.
# _els reste côté V8 -- toute lecture/écriture d'état APRÈS la construction
# du contexte doit passer par ctx.eval(), jamais par un dict Python (qui ne
# serait qu'un instantané figé au moment du json.dumps ci-dessous).
_DOM_HARNESS = r"""
function _makeClassList(el){
  if(!el._classesObj){
    el._classesObj = {
      toggle: function(c, force){
        var has = el._classes.indexOf(c) !== -1;
        var want = (force === undefined) ? !has : force;
        if(want && !has) el._classes.push(c);
        if(!want && has) el._classes.splice(el._classes.indexOf(c), 1);
      },
      contains: function(c){ return el._classes.indexOf(c) !== -1; }
    };
  }
  return el._classesObj;
}
var document = {
  getElementById: function(id){
    if(!(id in _els)) return null;
    var el = _els[id];
    if(el._classes) el.classList = _makeClassList(el);
    return el;
  }
};
"""


def _make_ctx(fields_and_values):
    """fields_and_values : {field_id: valeur_ou_None}. Un champ à None n'a
    même pas d'élément dans le DOM factice (cas d'un champ absent de la
    catégorie actuellement ouverte -- getElementById doit rendre null, pas
    lever)."""
    els = {}
    for field, value in fields_and_values.items():
        if value is not None:
            els[field] = {'value': value}
        els[field + '_dot'] = {'_classes': []}
    ctx = py_mini_racer.MiniRacer()
    ctx.eval('var _els = %s;' % json.dumps(els))
    ctx.eval(_DOM_HARNESS)
    ctx.eval(_SECRET_FIELDS_SRC)
    ctx.eval(_REFRESHDOT_SRC)
    ctx.eval(_REFRESHALL_SRC)
    return ctx


def _is_set(ctx, field):
    return ctx.eval("_els['%s_dot']._classes.indexOf('set')" % field) != -1


def test_champ_rempli_marque_le_point_configure():
    ctx = _make_ctx({'eqsl_password': 'motdepasse123'})
    ctx.eval("_refreshSecretDot('eqsl_password');")
    assert _is_set(ctx, 'eqsl_password')


def test_champ_vide_ne_marque_pas_le_point():
    ctx = _make_ctx({'eqsl_password': ''})
    ctx.eval("_refreshSecretDot('eqsl_password');")
    assert not _is_set(ctx, 'eqsl_password')


def test_champ_type_texte_fonctionne_pareil_qu_un_mot_de_passe():
    """Le point ne doit pas dépendre du masquage visuel du navigateur --
    une clé API en clair (type=text) doit être détectée exactement comme un
    mot de passe (type=password)."""
    ctx = _make_ctx({'clublog_api_key': 'abc123XYZ'})
    ctx.eval("_refreshSecretDot('clublog_api_key');")
    assert _is_set(ctx, 'clublog_api_key')


def test_effacer_le_champ_retire_le_point_live():
    """Cas d'usage direct du retour F4GLD : l'opérateur vide le champ à la
    main, le point doit redevenir neutre immédiatement (pas seulement au
    prochain rechargement de page)."""
    ctx = _make_ctx({'lotw_password': 'ancien'})
    ctx.eval("_refreshSecretDot('lotw_password');")
    assert _is_set(ctx, 'lotw_password')
    ctx.eval("_els.lotw_password.value = '';")
    ctx.eval("_refreshSecretDot('lotw_password');")
    assert not _is_set(ctx, 'lotw_password')


def test_champ_absent_du_dom_ne_leve_pas():
    """Catégorie pas encore ouverte (le champ n'existe pas dans le DOM
    courant) : ne doit ni lever ni marquer le point comme configuré."""
    ctx = _make_ctx({'mysql_password': None})
    ctx.eval("_refreshSecretDot('mysql_password');")
    assert not _is_set(ctx, 'mysql_password')


def _secret_field_names():
    """Liste des champs lue depuis le VRAI code (pas recopiée à la main --
    une liste dupliquée diverge silencieusement le jour où le fichier
    source change)."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_SECRET_FIELDS_SRC)
    return json.loads(ctx.eval("JSON.stringify(SECRET_CONFIG_FIELDS)"))


def test_refresh_all_couvre_les_17_champs_de_secret_config_fields():
    fields = _secret_field_names()
    assert len(fields) == 17
    all_fields = {f: ('valeur' if i % 2 == 0 else '') for i, f in enumerate(fields)}
    ctx = _make_ctx(all_fields)
    ctx.eval("_refreshAllSecretDots();")
    for i, f in enumerate(fields):
        expected_set = (i % 2 == 0)
        assert _is_set(ctx, f) == expected_set, f'{f} : attendu set={expected_set}'
