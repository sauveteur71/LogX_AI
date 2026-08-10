# -*- coding: utf-8 -*-
"""Bandeau de validation CONFIG non bloquant (chantier 2, audit accessibilité
09/08/2026, suite de #7/#8) : _missingStationFields() retourne désormais
[{message, category}] (au lieu de simples chaînes) et _warnMissingStation()/
_showConfigValidationBanner() remplacent l'alert() natif de saveConfig() par
un bandeau avec un lien cliquable par champ manquant, pointant directement
vers la bonne section de la sidebar (switchSection()) -- un alert() gèle
toute la page et n'offre aucun moyen de sauter directement au bon réglage.

Ce module exécute le VRAI code du fichier (extrait par comptage d'accolades,
même technique que tests/test_config_category_switch.py), pas une réécriture."""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_configuration.html')


def _extract_function(src, name):
    """Extrait le texte complet `function <name>(){...}` par comptage
    d'accolades -- le VRAI code du fichier, pas une réécriture."""
    m = re.search(r'^function %s\(' % re.escape(name), src, re.M)
    assert m, 'fonction %s introuvable dans %s' % (name, HTML_PATH)
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


with open(HTML_PATH, encoding='utf-8') as _f:
    _HTML_SRC = _f.read()
# Script inline extrait vers logx_configuration.js (10/08/2026) -- concaténer
# pour que les extractions de fonctions ci-dessous continuent de les trouver.
_JS_PATH = os.path.join(BASE, 'logx_configuration.js')
if os.path.exists(_JS_PATH):
    with open(_JS_PATH, encoding='utf-8') as _f:
        _HTML_SRC += '\n' + _f.read()

_MISSING_SRC = _extract_function(_HTML_SRC, '_missingStationFields')
_BANNER_SRC = _extract_function(_HTML_SRC, '_showConfigValidationBanner')
_DISMISS_SRC = _extract_function(_HTML_SRC, '_dismissConfigValidationBanner')
_WARN_SRC = _extract_function(_HTML_SRC, '_warnMissingStation')

# ─── DOM minimal : juste assez pour _missingStationFields()/
# _showConfigValidationBanner() -- un <ul> et un conteneur de bandeau réels
# (via ElProxy, même patron que tests/test_qtc_panel_js.py), le reste des
# champs (callsign/locator/dates/bandes/modes) stubbé selon le scénario testé. ─
_DOM_PREAMBLE = r"""
function ElProxy(id){
  var s = {id:id, value:'', textContent:'', innerHTML:'', style:{display:''}, children:[]};
  var handler = {
    get:function(target, prop){
      if(prop === 'appendChild') return function(c){ s.children.push(c); return c; };
      if(prop === 'style') return s.style;
      return s[prop];
    },
    set:function(target, prop, val){ s[prop] = val; return true; }
  };
  return new Proxy({}, handler);
}
var __els = {};
function el(id){ if(!__els[id]) __els[id] = ElProxy(id); return __els[id]; }
var __querySelectorResult = null;   // piloté par chaque test (band_/mode_ actifs ou non)
var document = {
  getElementById: function(id){ return el(id); },
  createElement: function(tag){ return ElProxy(null); },
  querySelector: function(sel){ return __querySelectorResult; },
};
var state = { contest: null };
var _switchSectionCalls = [];
function switchSection(cat){ _switchSectionCalls.push(cat); }
function isValidLocator(loc){ return /^[A-R]{2}[0-9]{2}[A-X]{2}$/i.test(loc || ''); }
function _contestOptional(){ return false; }
function T(s){ return s; }
"""


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_MISSING_SRC)
    ctx.eval(_BANNER_SRC)
    ctx.eval(_DISMISS_SRC)
    ctx.eval(_WARN_SRC)
    return ctx


def test_missing_station_fields_retourne_message_et_categorie():
    ctx = _make_ctx()
    ctx.eval("""
    document.getElementById('callsign').value = '';
    document.getElementById('locator').value = '';
    """)
    missing = json.loads(ctx.eval("JSON.stringify(_missingStationFields(2))"))
    assert len(missing) == 2
    assert all(item['category'] == 'identity' for item in missing), \
        "indicatif/locator manquants doivent tous deux pointer vers la section 'identity'"
    assert all('message' in item and item['message'] for item in missing)


def test_missing_station_fields_categorie_contest_pour_concours_manquant():
    ctx = _make_ctx()
    ctx.eval("""
    document.getElementById('callsign').value = 'F4TEST';
    document.getElementById('locator').value = 'JN15XC';
    """)
    missing = json.loads(ctx.eval("JSON.stringify(_missingStationFields(3))"))
    assert any(item['category'] == 'contest' for item in missing), \
        "aucun concours sélectionné doit pointer vers la section 'contest'"


def test_missing_station_fields_categorie_filters_pour_dates_et_bandes_modes():
    ctx = _make_ctx()
    ctx.eval("""
    document.getElementById('callsign').value = 'F4TEST';
    document.getElementById('locator').value = 'JN15XC';
    state.contest = 'CQWW';
    document.getElementById('contest_start_date').value = '2026-08-10';
    document.getElementById('contest_end_date').value = '2026-08-01';   // fin AVANT début
    __querySelectorResult = null;   // aucune bande/mode active
    """)
    missing = json.loads(ctx.eval("JSON.stringify(_missingStationFields(4))"))
    categories = [item['category'] for item in missing]
    # date fin < date début + zéro bande + zéro mode -> 3 constats, tous 'filters'
    assert categories.count('filters') == 3, categories


def test_missing_station_fields_rien_manquant_liste_vide():
    ctx = _make_ctx()
    ctx.eval("""
    document.getElementById('callsign').value = 'F4TEST';
    document.getElementById('locator').value = 'JN15XC';
    state.contest = 'CQWW';
    document.getElementById('contest_start_date').value = '2026-08-01';
    document.getElementById('contest_end_date').value = '2026-08-02';
    __querySelectorResult = {};   // au moins une bande/un mode actif (même objet réutilisé)
    """)
    missing = json.loads(ctx.eval("JSON.stringify(_missingStationFields(4))"))
    assert missing == []


def test_showConfigValidationBanner_affiche_le_bandeau_et_liste_les_items():
    ctx = _make_ctx()
    ctx.eval("""
    _showConfigValidationBanner([
      {message: 'INDICATIF (section Identité)', category: 'identity'},
      {message: 'un CONCOURS sélectionné (section Sélection du concours)', category: 'contest'}
    ]);
    """)
    assert ctx.eval("document.getElementById('configValidationBanner').style.display") == 'block'
    assert ctx.eval("document.getElementById('configValidationList').children.length") == 2


def test_showConfigValidationBanner_item_avec_categorie_est_un_lien_cliquable():
    """Cliquer le lien doit fermer le bandeau ET ouvrir la bonne section --
    c'est tout l'intérêt du bandeau par rapport à l'ancien alert() (qui ne
    faisait qu'afficher un texte, sans action possible)."""
    ctx = _make_ctx()
    ctx.eval("_showConfigValidationBanner([{message: 'INDICATIF', category: 'identity'}]);")
    # Le premier (et seul) enfant de la liste est un <li> contenant un <a> --
    # simule le clic en appelant directement le gestionnaire onclick posé par
    # _showConfigValidationBanner() sur cet <a>.
    ctx.eval("""
    var li = document.getElementById('configValidationList').children[0];
    var link = li.children[0];
    link.onclick({preventDefault: function(){}});
    """)
    assert json.loads(ctx.eval("JSON.stringify(_switchSectionCalls)")) == ['identity']
    assert ctx.eval("document.getElementById('configValidationBanner').style.display") == 'none'


def test_showConfigValidationBanner_item_sans_categorie_nest_pas_un_lien():
    """Les 3 alertes ClubLog/QRZ/SOTA de saveConfig() passent un item SANS
    category (le message dit déjà où agir) -- doit rester du texte simple,
    pas un <a> sans destination."""
    ctx = _make_ctx()
    ctx.eval("_showConfigValidationBanner([{message: 'Club Log Live Stream — section QSL'}]);")
    # ElProxy est un Proxy sans ownKeys/getOwnPropertyDescriptor -- JSON.stringify()
    # dessus sérialiserait la cible {} vide, pas les données réelles (piège déjà
    # rencontré sur le test précédent) : on lit .children.length directement.
    assert ctx.eval("document.getElementById('configValidationList').children[0].children.length") == 0, \
        "un item sans category ne doit pas produire de lien <a>"


def test_dismissConfigValidationBanner_masque_le_bandeau():
    ctx = _make_ctx()
    ctx.eval("_showConfigValidationBanner([{message: 'x', category: 'identity'}]);")
    assert ctx.eval("document.getElementById('configValidationBanner').style.display") == 'block'
    ctx.eval("_dismissConfigValidationBanner();")
    assert ctx.eval("document.getElementById('configValidationBanner').style.display") == 'none'


def test_warnMissingStation_delegue_au_bandeau():
    ctx = _make_ctx()
    ctx.eval("_warnMissingStation([{message: 'INDICATIF', category: 'identity'}]);")
    assert ctx.eval("document.getElementById('configValidationBanner').style.display") == 'block'
    assert ctx.eval("document.getElementById('configValidationList').children.length") == 1


def test_pas_dalert_natif_dans_saveConfig_pour_les_3_garde_fous():
    """ClubLog Live Stream, QRZ Logbook push, SOTA approbation -- les 3
    alert() natifs de saveConfig() (hors _missingStationFields) doivent
    avoir disparu du CODE (pas des commentaires)."""
    deb = _HTML_SRC.index('function saveConfig(')
    fin = _HTML_SRC.index('\n  const provider = getSelectedProvider();', deb)
    corps = _HTML_SRC[deb:fin]
    lignes_code = [l for l in corps.splitlines() if not l.strip().startswith('//')]
    assert not any('alert(' in l for l in lignes_code), \
        "un alert() natif est resté dans le corps (hors commentaires) des garde-fous de saveConfig()"
