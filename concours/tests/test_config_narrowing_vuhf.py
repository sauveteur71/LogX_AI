# -*- coding: utf-8 -*-
"""Narrowing de la grille de concours CONFIG par activité (chantier « page
d'accueil par activité », 22/08/2026) : quand localStorage.logx_activity
vaut 'vuhf', buildContestQuickView() ne doit proposer que des concours dont
le règlement (résolu via _resolveContestFilters(), logx_contest_rules.js)
est POSITIVEMENT connu et tient entièrement dans VHF_BANDS -- un concours à
l'axe libre (CUSTOM, POTA/SOTA « au choix »...) est délibérément écarté
plutôt que deviné compatible (voir le commentaire de _contestCompatibleVuhf
dans logx_configuration.js). L'échappatoire reste « Voir tous les concours »
(buildContestGrid, jamais filtré par activité).

Ce module exécute le VRAI code (_activiteEstVuhf/_contestCompatibleVuhf,
extraits tels quels par comptage d'accolades depuis logx_configuration.js,
plus le VRAI logx_contest_rules.js) dans un moteur JS réel (V8 via
py_mini_racer) -- pas une réimplémentation."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_JS_PATH = os.path.join(BASE, 'logx_configuration.js')
RULES_JS_PATH = os.path.join(BASE, 'logx_contest_rules.js')


def _extract_function(src, name):
    start = src.index('function ' + name + '(')
    brace_open = src.index('{', start)
    depth, i = 0, brace_open
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1


def _extract_line(src, start_marker):
    """Extrait `start_marker...;` -- même technique que _HF_VHF_BANDS_SRC
    dans test_config_bands_modes_from_server.py."""
    start = src.index(start_marker)
    end = src.index(';', start)
    return src[start:end + 1]


with open(CONFIG_JS_PATH, encoding='utf-8') as _f:
    _CONFIG_SRC = _f.read()

_VHF_BANDS_SRC = _extract_line(_CONFIG_SRC, 'const VHF_BANDS')
_ACTIVITE_VUHF_SRC = _extract_function(_CONFIG_SRC, '_activiteEstVuhf')
_CONTEST_COMPAT_VUHF_SRC = _extract_function(_CONFIG_SRC, '_contestCompatibleVuhf')


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
    var __store = {};
    var localStorage = {
      getItem: function(k){ return (k in __store) ? __store[k] : null; },
      setItem: function(k, v){ __store[k] = String(v); },
      removeItem: function(k){ delete __store[k]; },
    };
    """)
    with open(RULES_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    ctx.eval(_VHF_BANDS_SRC)
    ctx.eval(_ACTIVITE_VUHF_SRC)
    ctx.eval(_CONTEST_COMPAT_VUHF_SRC)
    return ctx


def test_activite_vuhf_faux_par_defaut():
    ctx = _make_ctx()
    assert ctx.eval('_activiteEstVuhf()') is False


def test_activite_vuhf_vrai_quand_posee():
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('logx_activity', 'vuhf');")
    assert ctx.eval('_activiteEstVuhf()') is True


def test_activite_vuhf_faux_pour_une_autre_activite():
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('logx_activity', 'normal');")
    assert ctx.eval('_activiteEstVuhf()') is False


def test_marconi_144mhz_cw_compatible_vuhf():
    """REF_MARCONI (144 MHz, CW uniquement) -- absent du serveur, résolu via
    LEGACY_CONTEST_FILTERS (logx_contest_rules.js)."""
    ctx = _make_ctx()
    assert ctx.eval("_contestCompatibleVuhf({id:'REF_MARCONI'})") is True


def test_ccd_jan1_432_1296_2320_compatible_vuhf():
    ctx = _make_ctx()
    assert ctx.eval("_contestCompatibleVuhf({id:'REF_CCD_JAN1'})") is True


def test_ddfm_50_6m_compatible_vuhf():
    ctx = _make_ctx()
    assert ctx.eval("_contestCompatibleVuhf({id:'REF_DDFM_50'})") is True


def test_uft_rencontres_hf_pas_compatible_vuhf():
    """Concours HF (80-40-20-15-10m, CW) résolu via LEGACY_CONTEST_FILTERS --
    doit être écarté, pas juste 'non trouvé'."""
    ctx = _make_ctx()
    assert ctx.eval("_contestCompatibleVuhf({id:'UFT_RENCONTRES'})") is False


def test_concours_axe_libre_ecarte_pas_devine_compatible():
    """SOTA/CUSTOM (bands:['all']) : _resolveContestFilters() rend .bands=null
    -- axe libre, jamais deviné V/UHF, précisément pour ne pas fabriquer une
    valeur de domaine (CLAUDE.md : « ne rien inventer »)."""
    ctx = _make_ctx()
    ctx.eval("SERVER_CONTEST_RULES['SOTA'] = {bands:['all'], modes:['all']};")
    assert ctx.eval("_contestCompatibleVuhf({id:'SOTA'})") is False


def test_concours_totalement_inconnu_ecarte():
    ctx = _make_ctx()
    assert ctx.eval("_contestCompatibleVuhf({id:'ID_INCONNU_XYZ'})") is False
