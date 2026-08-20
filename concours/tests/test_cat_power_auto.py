# -*- coding: utf-8 -*-
"""Puissance TX automatique par mode -- protection du final en numérique
(FT8/FT4/RTTY... à 100% de cycle de service, souvent recommandé par le
constructeur en dessous de la puissance max phonie/CW). Demande explicite de
F4GLD (15/08/2026).

Câblage : _qsyVersRadio() (logx_logbook.js), le même point d'accroche que la
synchro bande/mode CAT (PR #81, tests/test_cat_manual_bandmode_qsy.py),
appelle désormais aussi _puissanceAutoVersRadio() -- qui pousse
POST /rig/set_power SEULEMENT si CONFIG > RADIO > PUISSANCE TX AUTOMATIQUE
est activé (cat_power_auto_enabled, lu depuis localStorage.logx_config, même
convention que contestActif()/initFromConfig()) ET que la puissance
correspondant au mode courant est renseignée -- jamais 0 W poussé sur l'air
faute de réglage.

Côté serveur, voir tests/test_cat.py (cat.set_power(), AsciiRadio.set_power())
et tests/test_cat_proprietaire_dispatch.py (endpoint /rig/set_power).

Même patron (VRAI logx_logbook.js + logx_hardware_cat.js dans un moteur JS
réel via py_mini_racer) que tests/test_cat_manual_bandmode_qsy.py -- réutilise
son DOM minimal telle quelle plutôt que d'en écrire un 2e."""
import json

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

from test_cat_manual_bandmode_qsy import _DOM_PREAMBLE, _real_source  # noqa: E402

_NET_STUB = r"""
var __fetchCalls = [];
function fetch(url, opts){
  var body = {};
  try{ body = (opts && opts.body) ? JSON.parse(opts.body) : {}; }catch(e){}
  __fetchCalls.push({url:String(url), body:body});
  return Promise.resolve({ok:true, status:200, json:function(){ return Promise.resolve({}); }});
}
function __powerCalls(){ return __fetchCalls.filter(function(c){ return c.url === '/rig/set_power'; }); }
"""

_INIT = r"""
function __init(){
  myCall = 'F4TEST'; myLocator = 'JN03QQ'; myOp = 'OP1';
  usageMode = 'contest';
  currentContest = null;
  contestScoringDefs = {};
  qsoLog = [];
  serialByBand = {};
  __fetchCalls = [];
  expeditionMode = false;
  applyExpeditionMode(false);
  pickBand('144');
  document.getElementById('inputCall').value = 'F6KQJ';
  rigState.enabled = true;
}
"""


def _module_puissance():
    """concours/logx_puissance_auto.js — la règle elle-même, sortie de
    logx_logbook.js pour servir AUSSI à la page FT8 (qui est celle qui émet
    réellement en FT8 et n'appliquait donc aucune protection).

    Le banc le charge parce que la PAGE le charge : logx_logbook.html a une
    balise <script> pour chacun des deux, dans cet ordre. Un banc qui ne
    monterait que logx_logbook.js éprouverait une page qui n'existe pas.
    """
    import os
    ici = os.path.dirname(os.path.abspath(__file__))
    chemin = os.path.join(os.path.dirname(ici), 'logx_puissance_auto.js')
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_module_puissance())
    ctx.eval(_real_source())
    ctx.eval(_NET_STUB)   # après la source : remplace le fetch du préambule
    ctx.eval(_INIT)
    ctx.eval('__init();')
    return ctx


def _power_calls(ctx):
    return json.loads(ctx.eval('JSON.stringify(__powerCalls())'))


def _set_cfg(ctx, cfg):
    ctx.eval("localStorage.setItem('logx_config', %s);" % json.dumps(json.dumps(cfg)))


# ─── Désactivé par défaut : rien ne doit partir sans que ce soit explicitement coché ───

def test_pickMode_sans_config_sauvegardee_ne_pousse_rien():
    """Aucune config jamais sauvegardée sur ce poste (localStorage vide) --
    même situation qu'un tout nouvel utilisateur."""
    ctx = _make_ctx()
    ctx.eval("""
    __fetchCalls = [];
    pickMode('FT8');
    """)
    assert _power_calls(ctx) == []


def test_pickMode_reglage_desactive_ne_pousse_rien():
    ctx = _make_ctx()
    _set_cfg(ctx, {'cat_power_auto_enabled': False, 'cat_power_phone_w': '100',
                   'cat_power_digital_w': '50'})
    ctx.eval("""
    __fetchCalls = [];
    pickMode('FT8');
    """)
    assert _power_calls(ctx) == []


def test_pickMode_active_mais_puissances_vides_ne_pousse_rien():
    """Activé en CONFIG, mais aucun des deux champs n'a été rempli -- repli
    sûr : jamais de puissance non voulue poussée sur l'air."""
    ctx = _make_ctx()
    _set_cfg(ctx, {'cat_power_auto_enabled': True, 'cat_power_phone_w': '',
                   'cat_power_digital_w': ''})
    ctx.eval("""
    __fetchCalls = [];
    pickMode('FT8');
    """)
    assert _power_calls(ctx) == []
    ctx.eval("pickMode('SSB');")
    assert _power_calls(ctx) == []


# ─── Activé : bascule numérique/phonie selon le mode choisi ─────────────────

def test_pickMode_numerique_pousse_la_puissance_numerique():
    ctx = _make_ctx()
    _set_cfg(ctx, {'cat_power_auto_enabled': True, 'cat_power_phone_w': '100',
                   'cat_power_digital_w': '50'})
    ctx.eval("""
    __fetchCalls = [];
    pickMode('FT8');
    """)
    calls = _power_calls(ctx)
    assert len(calls) == 1
    assert calls[0]['body']['watts'] == 50


def test_pickMode_phonie_pousse_la_puissance_phonie_cw():
    ctx = _make_ctx()
    _set_cfg(ctx, {'cat_power_auto_enabled': True, 'cat_power_phone_w': '100',
                   'cat_power_digital_w': '50'})
    ctx.eval("""
    __fetchCalls = [];
    pickMode('SSB');
    """)
    calls = _power_calls(ctx)
    assert len(calls) == 1
    assert calls[0]['body']['watts'] == 100


def test_pickMode_cw_traite_comme_phonie():
    ctx = _make_ctx()
    _set_cfg(ctx, {'cat_power_auto_enabled': True, 'cat_power_phone_w': '100',
                   'cat_power_digital_w': '50'})
    ctx.eval("""
    __fetchCalls = [];
    pickMode('CW');
    """)
    calls = _power_calls(ctx)
    assert len(calls) == 1
    assert calls[0]['body']['watts'] == 100


@pytest.mark.parametrize('mode', ['FT8', 'FT4', 'RTTY', 'PSK', 'JS8', 'MSK144', 'Q65'])
def test_pickMode_familles_numeriques_reconnues(mode):
    ctx = _make_ctx()
    _set_cfg(ctx, {'cat_power_auto_enabled': True, 'cat_power_phone_w': '100',
                   'cat_power_digital_w': '50'})
    ctx.eval("""
    __fetchCalls = [];
    pickMode(%s);
    """ % json.dumps(mode))
    calls = _power_calls(ctx)
    assert len(calls) == 1, f'{mode} devrait être reconnu comme numérique'
    assert calls[0]['body']['watts'] == 50


def test_pickMode_seule_puissance_numerique_renseignee():
    """Puissance phonie laissée vide (opérateur ne veut réduire QU'en
    numérique) -- un choix SSB ne doit rien pousser, un choix FT8 doit."""
    ctx = _make_ctx()
    _set_cfg(ctx, {'cat_power_auto_enabled': True, 'cat_power_phone_w': '',
                   'cat_power_digital_w': '50'})
    ctx.eval("""
    __fetchCalls = [];
    pickMode('SSB');
    """)
    assert _power_calls(ctx) == []
    ctx.eval("pickMode('FT8');")
    calls = _power_calls(ctx)
    assert len(calls) == 1
    assert calls[0]['body']['watts'] == 50


# ─── Sans CAT actif : rien ne doit partir (même garde que le QSY) ───────────

def test_pickMode_sans_cat_actif_ne_pousse_rien():
    ctx = _make_ctx()
    _set_cfg(ctx, {'cat_power_auto_enabled': True, 'cat_power_phone_w': '100',
                   'cat_power_digital_w': '50'})
    ctx.eval("""
    rigState.enabled = false;
    __fetchCalls = [];
    pickMode('FT8');
    """)
    assert _power_calls(ctx) == []


# ─── pickBand seul (pas de changement de mode) doit rejouer le mode courant ─

def test_pickBand_seul_repousse_la_puissance_du_mode_courant():
    """_qsyVersRadio() est partagée par pickBand()/pickMode() -- un simple
    changement de bande doit lui aussi réappliquer la puissance du mode
    COURANT (idempotent, même logique que le QSY qui renvoie déjà `mode`
    à chaque changement de bande)."""
    ctx = _make_ctx()
    _set_cfg(ctx, {'cat_power_auto_enabled': True, 'cat_power_phone_w': '100',
                   'cat_power_digital_w': '50'})
    ctx.eval("""
    currentMode = 'FT8';
    _currentVisibleBands = ['144', '432', '14'];
    __fetchCalls = [];
    pickBand('14');
    """)
    calls = _power_calls(ctx)
    assert len(calls) == 1
    assert calls[0]['body']['watts'] == 50


# ─── fromRig (synchro radio -> carnet) : ne doit PAS reboucler de puissance ─

def test_pickMode_fromRig_ne_pousse_pas_de_puissance():
    """pickMode(mode, {fromRig:true}) (appelée par syncBandModeFromRig(),
    quand la radio annonce un changement de mode fait SUR L'APPAREIL) saute
    tout l'appel à _qsyVersRadio() -- donc aussi _puissanceAutoVersRadio(),
    par construction (même garde `if(!opts.fromRig)` que le QSY fréquence/
    mode, voir test_pickMode_fromRig_ne_pousse_pas_de_mise_a_jour_optimiste_en_double
    dans test_cat_manual_bandmode_qsy.py). Évite la même boucle poll->CAT->poll
    que pour la fréquence/le mode."""
    ctx = _make_ctx()
    _set_cfg(ctx, {'cat_power_auto_enabled': True, 'cat_power_phone_w': '100',
                   'cat_power_digital_w': '50'})
    ctx.eval("""
    __fetchCalls = [];
    pickMode('FT8', {fromRig: true});
    """)
    assert _power_calls(ctx) == []
