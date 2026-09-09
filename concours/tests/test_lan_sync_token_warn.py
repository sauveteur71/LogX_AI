# -*- coding: utf-8 -*-
"""Avertissement UI : synchro LAN activée SANS jeton d'équipe (Option B, #audit A1).

/log/lan/export sert le carnet à tout le réseau local quand lan_sync_enabled=1
et lan_sync_token vide (compromis multi-poste assumé, rétro-compat). On ne bloque
pas — on alerte dans CONFIG. Ce test exécute la VRAIE fonction de la page
(extraite de logx_configuration.js) dans un moteur JS réel (V8) avec un DOM stub,
et fige la règle : l'alerte s'affiche SSI (activée ET jeton vide).

Un test statique complémentaire vérifie que la page câble bien la fonction
(div + handlers), sinon la logique serait juste, mais jamais déclenchée.
"""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_configuration.js')
HTML_PATH = os.path.join(BASE, 'logx_configuration.html')


def _extract_fn():
    """Source EXACTE de updateLanSyncTokenWarn() depuis le fichier de prod."""
    with open(JS_PATH, encoding='utf-8') as f:
        lines = f.readlines()
    start = next(i for i, l in enumerate(lines)
                 if l.startswith('function updateLanSyncTokenWarn('))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].rstrip() == '}')
    return ''.join(lines[start:end + 1])


FN = _extract_fn()


def _display(enabled, token, init='INIT'):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(r"""
      var _els = {
        lan_sync_enabled: {value: %s},
        lan_sync_token:   {value: %s},
        lanSyncTokenWarn: {style: {display: %s}}
      };
      var document = { getElementById: function(id){ return _els[id] || null; } };
    """ % (_js(enabled), _js(token), _js(init)))
    ctx.eval(FN)
    ctx.eval("updateLanSyncTokenWarn();")
    return ctx.eval("_els.lanSyncTokenWarn.style.display")


def _js(v):
    import json
    return json.dumps(v)


def test_alerte_affichee_si_active_sans_jeton():
    assert _display('1', '') == ''            # visible


def test_alerte_masquee_si_jeton_present():
    assert _display('1', 'SECRET123') == 'none'


def test_alerte_masquee_si_synchro_desactivee():
    assert _display('', '') == 'none'
    assert _display('', 'SECRET123') == 'none'


def test_jeton_espaces_seuls_compte_comme_vide():
    # trim() : un jeton de blancs ne protège rien -> alerte visible.
    assert _display('1', '   ') == ''


def test_html_cable_la_fonction():
    with open(HTML_PATH, encoding='utf-8') as f:
        html = f.read()
    assert 'id="lanSyncTokenWarn"' in html
    assert re.search(r'<select id="lan_sync_enabled"[^>]*onchange="updateLanSyncTokenWarn\(\)"', html)
    assert re.search(r'id="lan_sync_token"[^>]*oninput="updateLanSyncTokenWarn\(\)"', html)
