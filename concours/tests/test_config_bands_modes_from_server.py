# -*- coding: utf-8 -*-
"""Filtres bandes/modes de l'étape FILTRES (concours/logx_configuration.html) —
avant ce correctif, la grille de toggles était restreinte par CONTEST_FILTERS,
un objet client codé à la main (~35 concours) qui (1) ne couvrait pas les
concours absents de cette liste (concours personnalisés extraits par l'IA,
concours serveur ajoutés depuis), et (2) ne masquait que les BANDES hors
règlement — un mode hors règlement restait cochable librement.

Ce module exécute le VRAI code de _resolveContestFilters()/applyContestFilters()
— extrait tel quel du fichier source par comptage d'accolades, pas retapé —
dans un moteur JS réel (V8 via py_mini_racer, même technique que
tests/test_config_html_sota_qrz_race.py), avec un DOM minimal reconstruit à
partir des VRAIS data-key du fichier (extraits par regex), pour vérifier que :
  - un concours connu côté serveur (SERVER_CONTEST_RULES, simulant /data/
    calendar) restreint désormais aussi bien les bandes que les modes ;
  - 'all' explicite (SOTA/POTA) sur LES DEUX axes ne restreint rien du tout ;
  - 'all' explicite sur UN SEUL des deux axes (ex. bands:['all'], modes:['CW']
    pour un concours CW-only sans limite de bande) ne lève la restriction que
    sur CET axe — jamais sur l'autre. Avant correctif (revue adversariale du
    24/07/2026), un OR unique (bands.includes('all') || modes.includes('all'))
    levait TOUTE restriction dès qu'un seul axe était 'all' ;
  - un code de bande/mode non traduisible par BAND_TOGGLE_KEY/MODE_TOGGLE_KEY
    sur UN SEUL axe ne masque pas non plus tout l'axe opposé s'il est
    traduisible, lui (même correctif, pendant symétrique) ;
  - un concours absent du serveur retombe sur LEGACY_CONTEST_FILTERS s'il y
    est, sinon aucune restriction ;
  - un toggle masqué est explicitement remis à false (pas seulement caché
    visuellement) — la fuite constatée par l'audit."""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_configuration.html')

with open(HTML_PATH, encoding='utf-8') as _f:
    _HTML_SRC = _f.read()
# Script inline extrait vers logx_configuration.js (10/08/2026) -- concaténer
# pour que les extractions de fonctions ci-dessous continuent de les trouver.
_JS_PATH = os.path.join(BASE, 'logx_configuration.js')
if os.path.exists(_JS_PATH):
    with open(_JS_PATH, encoding='utf-8') as _f:
        _HTML_SRC += '\n' + _f.read()


def _extract_braces(src, start_marker, open_char='{', close_char='}'):
    """Extrait `start_marker...}` (ou `...]`) par comptage d'accolades/crochets
    — même technique que _extract_function ci-dessous, généralisée aux objets
    littéraux (LEGACY_CONTEST_FILTERS, BAND_TOGGLE_KEY, MODE_TOGGLE_KEY)."""
    start = src.index(start_marker)
    brace_open = src.index(open_char, start)
    depth = 0
    i = brace_open
    while True:
        c = src[i]
        if c == open_char:
            depth += 1
        elif c == close_char:
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1


def _extract_function(src, name):
    """Extrait le texte complet `function <name>(){...}` par comptage
    d'accolades (aucune des fonctions ciblées ne contient de `{`/`}` dans une
    chaîne ou un commentaire — vérifié à la main)."""
    start = src.index(f'function {name}(')
    brace_open = src.index('{', start)
    depth = 0
    i = brace_open
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1


_LEGACY_FILTERS_SRC = _extract_braces(_HTML_SRC, 'const LEGACY_CONTEST_FILTERS = {')
_BAND_TOGGLE_KEY_SRC = _extract_braces(_HTML_SRC, 'const BAND_TOGGLE_KEY = {')
_MODE_TOGGLE_KEY_SRC = _extract_braces(_HTML_SRC, 'const MODE_TOGGLE_KEY = {')
_HF_VHF_BANDS_SRC = re.search(r"const HF_BANDS\s*=.*?;\s*\nconst VHF_BANDS\s*=.*?;",
                               _HTML_SRC, re.S).group(0)
_RESOLVE_FILTERS_SRC = _extract_function(_HTML_SRC, '_resolveContestFilters')
_APPLY_FILTERS_SRC = _extract_function(_HTML_SRC, 'applyContestFilters')

# Extrait les VRAIS data-key band_/mode_ du fichier (grille de l'étape
# FILTRES) — le DOM de test reste ainsi synchronisé avec le markup réel au
# lieu de dupliquer une 3e fois la liste des boutons à la main.
_REAL_TOGGLE_KEYS = sorted(set(re.findall(
    r'data-key="((?:band|mode)_[a-z0-9]+)"', _HTML_SRC)))
assert 'band_2m' in _REAL_TOGGLE_KEYS and 'mode_ssb' in _REAL_TOGGLE_KEYS  # sanity


_DOM_PREAMBLE = r"""
var __idStore = {};
var __dataKeyEls = {};

function ElProxy(){
  var s = { style:{display:''}, textContent:'', innerHTML:'', dataset:{} };
  var clsSet = new Set();
  var cls = {
    add:function(c){ clsSet.add(c); },
    remove:function(c){ clsSet.delete(c); },
    contains:function(c){ return clsSet.has(c); }
  };
  var handler = {
    get:function(target, prop){
      if(prop === 'classList') return cls;
      if(prop === 'style') return s.style;
      if(prop === 'dataset') return s.dataset;
      return s[prop];
    },
    set:function(target, prop, val){ s[prop] = val; return true; }
  };
  return new Proxy({}, handler);
}

function _matchesSelector(el, sel){
  sel = sel.trim();
  var m = sel.match(/^\[data-key(\^)?=("|')(.*)\2\]$/);
  if(!m) return false;
  var prefix = !!m[1];
  var val = m[3];
  var key = el.dataset.key;
  if(!key) return false;
  return prefix ? key.indexOf(val) === 0 : key === val;
}

var document = {
  getElementById: function(id){ if(!__idStore[id]) __idStore[id] = ElProxy(); return __idStore[id]; },
  querySelectorAll: function(selectorList){
    var sels = selectorList.split(',');
    var out = [];
    Object.keys(__dataKeyEls).forEach(function(k){
      var el = __dataKeyEls[k];
      for(var i=0;i<sels.length;i++){
        if(_matchesSelector(el, sels[i])){ out.push(el); break; }
      }
    });
    return out;
  },
  querySelector: function(selector){
    var all = document.querySelectorAll(selector);
    return all.length ? all[0] : null;
  }
};

var state = { toggles: {} };
var CONTESTS = [];
var _usageMode = 'contest';
function getUsageMode(){ return _usageMode; }
var SERVER_CONTEST_RULES = {};
"""


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    for key in _REAL_TOGGLE_KEYS:
        ctx.eval(f"""
        (function(){{
          var el = ElProxy();
          el.dataset.key = {key!r};
          el.textContent = {key!r};
          __dataKeyEls[{key!r}] = el;
        }})();
        """)
    ctx.eval(_LEGACY_FILTERS_SRC.replace('const LEGACY_CONTEST_FILTERS', 'var LEGACY_CONTEST_FILTERS', 1))
    ctx.eval(_BAND_TOGGLE_KEY_SRC.replace('const BAND_TOGGLE_KEY', 'var BAND_TOGGLE_KEY', 1))
    ctx.eval(_MODE_TOGGLE_KEY_SRC.replace('const MODE_TOGGLE_KEY', 'var MODE_TOGGLE_KEY', 1))
    ctx.eval(_HF_VHF_BANDS_SRC.replace('const HF_BANDS', 'var HF_BANDS', 1)
                               .replace('const VHF_BANDS', 'var VHF_BANDS', 1))
    ctx.eval(_RESOLVE_FILTERS_SRC)
    ctx.eval(_APPLY_FILTERS_SRC)
    return ctx


def _js(ctx, expr):
    """Retourne un résultat JS complexe (array/objet) sous forme Python native
    — py_mini_racer renvoie un JSObject opaque pour les arrays/objets, pas
    directement itérable/indexable côté Python (même contournement que
    tests/test_mobile_offline_serial.py : JSON.stringify + json.loads)."""
    return json.loads(ctx.eval(f"JSON.stringify({expr})"))


def _on_keys(ctx):
    """Retourne l'ensemble des data-key band_/mode_ actuellement affichés
    (display != 'none')."""
    return set(_js(ctx, """
    Object.keys(__dataKeyEls).filter(function(k){
      var el = __dataKeyEls[k];
      return el.style.display !== 'none';
    })
    """))


def _checked_keys(ctx):
    return set(_js(ctx, """
    Object.keys(__dataKeyEls).filter(function(k){
      return state.toggles[k] === true;
    })
    """))


# ─── _resolveContestFilters() : cas 'all' explicite ──────────────────────────

def test_all_bands_all_modes_ne_restreint_rien():
    """SOTA/POTA : bands=['all'], modes=['all'] → aucune restriction."""
    ctx = _make_ctx()
    ctx.eval("SERVER_CONTEST_RULES['SOTA'] = {bands:['all'], modes:['all']};")
    assert ctx.eval("_resolveContestFilters('SOTA')") is None


def test_all_sur_un_seul_des_deux_ne_leve_la_restriction_que_sur_cet_axe():
    """'all' sur bands SEUL (modes précis par ailleurs) ne doit lever la
    restriction QUE sur l'axe bandes — les modes listés restent restreints.
    Symétriquement pour 'all' sur modes seul. Avant correctif : un OR unique
    levait TOUTE restriction dès qu'un seul des deux axes valait 'all' (ex.
    un concours CW-only sans limite de bande laissait SSB/FT8/... cochables)."""
    ctx = _make_ctx()
    ctx.eval("SERVER_CONTEST_RULES['X'] = {bands:['all'], modes:['SSB','CW']};")
    result_x = _js(ctx, "_resolveContestFilters('X')")
    assert result_x == {'bands': None, 'modes': ['mode_ssb', 'mode_cw']}
    ctx.eval("SERVER_CONTEST_RULES['Y'] = {bands:['144','432'], modes:['all']};")
    result_y = _js(ctx, "_resolveContestFilters('Y')")
    assert result_y == {'bands': ['band_2m', 'band_70cm'], 'modes': None}


def test_bande_non_traduisible_ne_masque_pas_les_modes_traduisibles():
    """Régression du même bug (OR unique) côté 'rien de traduisible', pas
    seulement 'all' : bands:['XYZ_INCONNU'] (aucune clé BAND_TOGGLE_KEY ne
    correspond) + modes:['CW'] (traduisible) doit restreindre les modes à CW
    sans toucher aux bandes (axe libre, pas 'toutes masquées')."""
    ctx = _make_ctx()
    ctx.eval("SERVER_CONTEST_RULES['Z'] = {bands:['XYZ_INCONNU'], modes:['CW']};")
    result = _js(ctx, "_resolveContestFilters('Z')")
    assert result == {'bands': None, 'modes': ['mode_cw']}


def test_concours_inconnu_partout_ne_restreint_rien():
    ctx = _make_ctx()
    assert ctx.eval("_resolveContestFilters('INTROUVABLE_XYZ')") is None


def test_concours_absent_du_serveur_retombe_sur_legacy():
    """REF_MARCONI n'a pas d'entrée CONTEST_DEFINITIONS server-side (id
    distinct de IARU_MARCONI) → repli sur LEGACY_CONTEST_FILTERS."""
    ctx = _make_ctx()
    result = _js(ctx, "_resolveContestFilters('REF_MARCONI')")
    assert result == {'modes': ['mode_cw'], 'bands': ['band_2m']}


# ─── Traduction MHz/mode brut → clé toggle (le coeur du correctif) ───────────

def test_wwa_traduit_bien_ft2_et_psk_vers_mode_ft8_et_mode_rtty():
    """Reproduction du bug constaté par l'audit : CONTEST_FILTERS n'avait
    jamais prévu de clé pour FT2/PSK (WWA). Ici, la traduction passe par
    MODE_TOGGLE_KEY (FT2→mode_ft8, PSK→mode_rtty) donc le bug ne peut plus se
    reproduire, quel que soit le concours ajouté côté serveur."""
    ctx = _make_ctx()
    ctx.eval("""
    SERVER_CONTEST_RULES['WWA_TEST'] = {
      bands:['3.5','7','10.1','14','18','21','24','28'],
      modes:['SSB','CW','FT8','FT4','FT2','RTTY','PSK']
    };
    """)
    result = _js(ctx, "_resolveContestFilters('WWA_TEST')")
    assert set(result['modes']) == {'mode_ssb', 'mode_cw', 'mode_ft8', 'mode_ft4', 'mode_rtty'}
    assert set(result['bands']) == {'band_80m', 'band_40m', 'band_30m', 'band_20m',
                                     'band_17m', 'band_15m', 'band_12m', 'band_10m'}


# ─── applyContestFilters() : masquage symétrique bandes ET modes ────────────

def test_concours_hf_pur_masque_vhf_et_masque_les_modes_hors_reglement():
    """CQ WW SSB : HF uniquement, SSB uniquement. Avant ce correctif, CW/FT8/
    etc. restaient visibles et cochables (seules les bandes étaient
    filtrées) — désormais masqués et décochés eux aussi."""
    ctx = _make_ctx()
    ctx.eval("""
    SERVER_CONTEST_RULES['CQ_WW_SSB'] = {
      bands:['1.8','3.5','7','14','21','28'], modes:['SSB']
    };
    """)
    ctx.eval("applyContestFilters('CQ_WW_SSB');")
    visible = _on_keys(ctx)
    checked = _checked_keys(ctx)
    assert 'mode_ssb' in visible and 'mode_ssb' in checked
    # Le vrai bug corrigé : CW ne doit plus être visible ni coché.
    assert 'mode_cw' not in visible
    assert 'mode_cw' not in checked
    assert 'mode_ft8' not in visible
    # Bandes VHF hors règlement masquées.
    assert 'band_2m' not in visible
    assert 'band_70cm' not in visible
    # Bandes HF du règlement bien visibles/cochées.
    assert {'band_160m', 'band_80m', 'band_40m', 'band_20m', 'band_15m', 'band_10m'} <= visible
    assert ctx.eval("document.getElementById('section_vhf').style.display") == 'none'
    assert ctx.eval("document.getElementById('section_hf').style.display") == ''


def test_concours_vhf_pur_masque_hf():
    """REF_RPH (via serveur) : 144MHz→47GHz, SSB uniquement — HF entièrement
    masqué, section HF cachée."""
    ctx = _make_ctx()
    ctx.eval("""
    SERVER_CONTEST_RULES['REF_RPH'] = {
      bands:['144','432','1296','2320','3400','5760','10368'], modes:['SSB']
    };
    """)
    ctx.eval("applyContestFilters('REF_RPH');")
    visible = _on_keys(ctx)
    assert 'band_2m' in visible and 'band_70cm' in visible
    assert 'band_80m' not in visible and 'band_20m' not in visible
    assert ctx.eval("document.getElementById('section_hf').style.display") == 'none'
    assert ctx.eval("document.getElementById('section_vhf').style.display") == ''


def test_concours_cw_only_sans_limite_de_bande_ne_masque_que_les_modes():
    """Problème 1 (revue adversariale 24/07/2026) : bands:['all'], modes:['CW']
    (concours CW-only sans limite de bande) doit laisser TOUTES les bandes
    visibles/sélectionnables (axe libre) mais restreindre les modes à CW
    seul. Avant correctif, bands:['all'] levait aussi la restriction sur les
    modes : SSB/FT8/... restaient cochables alors que seul CW est autorisé."""
    ctx = _make_ctx()
    ctx.eval("SERVER_CONTEST_RULES['CW_ALL_BANDS'] = {bands:['all'], modes:['CW']};")
    ctx.eval("applyContestFilters('CW_ALL_BANDS');")
    visible = _on_keys(ctx)
    checked = _checked_keys(ctx)
    # Axe bandes libre : tout reste visible, sections HF et VHF non masquées.
    assert {'band_160m', 'band_20m', 'band_2m', 'band_70cm'} <= visible
    assert ctx.eval("document.getElementById('section_hf').style.display") == ''
    assert ctx.eval("document.getElementById('section_vhf').style.display") == ''
    # Axe modes restreint : seul CW visible/coché, les autres masqués.
    assert 'mode_cw' in visible and 'mode_cw' in checked
    assert 'mode_ssb' not in visible and 'mode_ft8' not in visible


def test_bande_non_traduisible_seule_ne_masque_pas_toutes_les_bandes():
    """Problème 4 (revue adversariale 24/07/2026) : bands:['60'] (code absent
    de BAND_TOGGLE_KEY côté serveur) + modes:['CW'] (traduisible) ne doit pas
    masquer TOUTES les bandes de l'étape FILTRES. Avant correctif,
    _resolveContestFilters renvoyait quand même {bands:[], modes:['mode_cw']}
    (seul le cas où LES DEUX axes étaient vides retombait sur null), et
    applyContestFilters cachait alors tous les boutons de bande sans en
    réafficher aucun — sélection de bande totalement bloquée."""
    ctx = _make_ctx()
    ctx.eval("SERVER_CONTEST_RULES['UNK_BAND'] = {bands:['60'], modes:['CW']};")
    ctx.eval("applyContestFilters('UNK_BAND');")
    visible = _on_keys(ctx)
    assert {'band_160m', 'band_20m', 'band_2m'} <= visible  # aucune bande masquée
    assert 'mode_cw' in visible
    assert 'mode_ssb' not in visible


def test_all_ne_masque_rien_dans_applyContestFilters():
    """SOTA/POTA : toutes les bandes/modes restent affichés et la note est
    masquée (aucune restriction appliquée)."""
    ctx = _make_ctx()
    ctx.eval("SERVER_CONTEST_RULES['SOTA'] = {bands:['all'], modes:['all']};")
    ctx.eval("document.getElementById('filterAutoNote').style.display = 'block';")  # état précédent
    ctx.eval("applyContestFilters('SOTA');")
    visible = _on_keys(ctx)
    # Tout reste visible (aucun masquage).
    assert set(_REAL_TOGGLE_KEYS) <= visible
    assert ctx.eval("document.getElementById('filterAutoNote').style.display") == 'none'


def test_concours_introuvable_ne_restreint_rien():
    """Concours personnalisé/EXT_* non encore reconnu côté serveur (ex. lien
    profond avant que mergeServerContests() ait fini) → aucune restriction,
    comportement sûr par défaut."""
    ctx = _make_ctx()
    ctx.eval("applyContestFilters('EXT_UNKNOWN_CONTEST');")
    visible = _on_keys(ctx)
    assert set(_REAL_TOGGLE_KEYS) <= visible


def test_usage_mode_simple_ne_restreint_jamais():
    ctx = _make_ctx()
    ctx.eval("""
    SERVER_CONTEST_RULES['CQ_WW_SSB'] = { bands:['3.5','7'], modes:['SSB'] };
    _usageMode = 'simple';
    """)
    ctx.eval("applyContestFilters('CQ_WW_SSB');")
    visible = _on_keys(ctx)
    assert set(_REAL_TOGGLE_KEYS) <= visible


# ─── Fuite de toggle : masquer implique explicitement toggles[key]=false ────

def test_toggle_masque_est_explicitement_remis_a_false():
    """Le coeur de la fuite constatée par l'audit : une bande hors règlement
    ne doit pas seulement être masquée visuellement, state.toggles doit
    explicitement retomber à false (sinon une restauration ultérieure de
    profil peut la remettre à true et la re-sauvegarder telle quelle)."""
    ctx = _make_ctx()
    ctx.eval("""
    SERVER_CONTEST_RULES['CQ_WW_SSB'] = {
      bands:['1.8','3.5','7','14','21','28'], modes:['SSB']
    };
    // Simule une valeur restaurée d'un profil sauvegardé pour un AUTRE concours.
    state.toggles['band_2m'] = true;
    state.toggles['mode_cw'] = true;
    """)
    ctx.eval("applyContestFilters('CQ_WW_SSB');")
    assert ctx.eval("state.toggles['band_2m']") is False
    assert ctx.eval("state.toggles['mode_cw']") is False


def test_pas_de_qso_director():
    assert 'QSO Director' not in _HTML_SRC
