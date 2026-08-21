# -*- coding: utf-8 -*-
"""logx_carte.html:loadConfig() POSTait INCONDITIONNELLEMENT le localStorage
`logx_config` de CE navigateur vers /config/save, à chaque chargement de la
page carte, sans aucune action de l'opérateur (ligne 807 avant correctif,
appelée par le bloc INIT ligne 1454).

Or /config/save REMPLACE intégralement current_config côté serveur
(logx_http.py), et cfg_scope_id(current_config) est un état PARTAGÉ : il pilote
le filtrage de /log/list pour TOUS les postes, l'allocation des n° de série
(/log/next_serial) et la portée des exports. Un opérateur qui arrive en cours
de concours avec le portable de secours et ouvre simplement la page CARTE —
localStorage encore sur le concours du mois dernier, ou usage_mode:'simple' —
mettait ainsi le carnet des 5 postes à 0 QSO et remettait les n° de série à
001 (numéros dupliqués sur l'air), sans le moindre clic de configuration. Les
QSO restaient dans shared_log, mais plus rien ne les montrait.

Deux tests complémentaires, tous deux sur du VRAI code :
 1. le vrai loadConfig() extrait du fichier source est exécuté dans un moteur
    JS réel (V8 via py_mini_racer, même technique que tests/test_qtc_panel_js.py)
    et ne doit émettre AUCUNE requête d'écriture ;
 2. les requêtes qu'il a réellement émises sont rejouées contre un VRAI serveur
    (ThreadingHTTPServer + logx_http.Handler) chargé d'un concours en cours :
    la portée, le carnet et le prochain n° de série doivent être intacts après
    l'ouverture de la carte.
"""
import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.request

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod
import logx_storage as storage

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_carte.html')


def _extract_function(src, name):
    """Extrait `function <name>(){...}` par comptage d'accolades : on exécute
    le VRAI code du fichier, pas une réécriture qui pourrait diverger. (Le
    corps de loadConfig() ne contient aucune accolade déséquilibrée en
    chaîne/commentaire — le seul `${...}` du template literal est équilibré.)"""
    start = src.index(f'function {name}(')
    i = src.index('{', start)
    depth = 0
    while True:
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1


with open(HTML_PATH, encoding='utf-8') as _f:
    _LOAD_CONFIG_SRC = _extract_function(_f.read(), 'loadConfig')


# localStorage périmé du portable de secours : le concours du mois DERNIER,
# celui qui écrasait la portée du concours en cours sur tout le réseau.
_STALE_LOCAL_CONFIG = {
    'callsign': 'F6KQJ', 'locator': 'JN18AA',
    'contest': 'CQ_WW_SSB', 'contest_start_date': '2025-10-25',
    'usage_mode': 'contest',
}

# Environnement minimal : localStorage, fetch enregistreur, et les fonctions
# que loadConfig() appelle mais qui ne font pas l'objet du test.
_PREAMBLE = r"""
var __fetch = [];
function fetch(url, opts){
  opts = opts || {};
  __fetch.push({url: url, method: opts.method || 'GET', body: opts.body || ''});
  var p = {};
  p.then  = function(){ return p; };
  p.catch = function(){ return p; };
  return p;
}
var __ls = {};
var localStorage = {
  getItem: function(k){ return Object.prototype.hasOwnProperty.call(__ls, k) ? __ls[k] : null; },
  setItem: function(k, v){ __ls[k] = String(v); },
  removeItem: function(k){ delete __ls[k]; }
};
var console = {warn: function(){}, log: function(){}, error: function(){}};
var cfg = {};
var __applyConfigCalls = 0;
function applyConfig(){ __applyConfigCalls++; }
function initMap(){}
function loadDxRecordForMap(){}
"""


def _run_load_config():
    """Exécute le vrai loadConfig() avec un localStorage périmé et retourne
    la liste des requêtes réellement émises."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBLE)
    ctx.eval(_LOAD_CONFIG_SRC)
    ctx.eval('__ls["logx_config"] = %s;' % json.dumps(json.dumps(_STALE_LOCAL_CONFIG)))
    ctx.eval('loadConfig();')
    # Garde-fou anti-test-vide : si la branche `if(saved)` n'avait pas été
    # prise (localStorage mal injecté), le test ne prouverait plus rien.
    assert ctx.eval('__applyConfigCalls') == 1
    return json.loads(ctx.eval('JSON.stringify(__fetch)'))


def test_carte_loadconfig_nemet_aucune_ecriture_serveur():
    """Le chargement de la carte ne doit émettre AUCUNE requête d'écriture —
    et surtout aucun /config/save, qui remplacerait la config partagée par le
    localStorage local de ce navigateur."""
    calls = _run_load_config()
    assert not [c for c in calls if '/config/save' in c['url']], (
        "logx_carte.html pousse encore sa config locale vers /config/save : "
        f"{calls}")
    assert not [c for c in calls if c['method'].upper() != 'GET'], (
        f"la page carte émet une requête d'écriture au chargement : {calls}")


# ─── Conséquence réelle, sur un vrai serveur ────────────────────────────────

@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()   # libere la socket d ecoute
        t.join(timeout=5)


def _get(base, path):
    # A09 (docs/FEUILLE_DE_ROUTE.md) : /log/list exige désormais le jeton de
    # session, comme les autres routes de lecture protégées.
    req = urllib.request.Request(base + path, headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def _replay(base, call):
    """Rejoue telle quelle une requête émise par la page carte."""
    req = urllib.request.Request(
        base + call['url'],
        data=(call['body'] or '').encode('utf-8'),
        method=call['method'].upper(),
        headers={'Content-Type': 'application/json',
                 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_ouvrir_la_carte_ne_change_pas_la_portee_des_autres_postes(server, monkeypatch):
    """Concours en cours (IARU_VHF 2026, 3 QSO sur 144). Un poste ouvre la
    page CARTE avec un localStorage périmé : le carnet et le prochain n° de
    série vus par TOUS les postes doivent être inchangés."""
    log = [{'id': i, 'call': c, 'band': '144', 'mode': 'SSB',
            'contest': 'IARU_VHF', 'date': '20260704', 'time': f'14:0{i}',
            'num_sent': f'00{i}', 'points': 1}
           for i, c in enumerate(('DL1AAA', 'ON4BBB', 'G3CCC'), start=1)]
    monkeypatch.setattr(httpmod, 'shared_log', log)
    monkeypatch.setattr(storage, 'shared_log', log)
    monkeypatch.setattr(storage, '_serial_high_water', {})
    monkeypatch.setattr(httpmod, 'current_config', {
        'callsign': 'F6KQJ', 'locator': 'JN18AA',
        'contest': 'IARU_VHF', 'contest_start_date': '2026-07-04',
        'usage_mode': 'contest'})
    # Le correctif porte sur le client : sans ce garde-fou, la version FAUTIVE
    # du code écrirait pour de bon .server_config.json du dépôt en rejouant
    # son POST (/config/save persiste sur disque).
    monkeypatch.setattr(httpmod, 'save_json_atomic', lambda *a, **k: None)

    avant_total = _get(server, '/log/list')['total']
    avant_serial = _get(server, '/log/next_serial?band=144&peek=1')['serial']
    assert (avant_total, avant_serial) == (3, '004')

    for call in _run_load_config():
        if call['method'].upper() != 'GET':
            _replay(server, call)

    apres_total = _get(server, '/log/list')['total']
    apres_serial = _get(server, '/log/next_serial?band=144&peek=1')['serial']
    assert apres_total == 3, (
        "ouvrir la carte a vidé le carnet de tous les postes "
        f"({avant_total} -> {apres_total} QSO)")
    assert apres_serial == '004', (
        "ouvrir la carte a remis le compteur de n° de série à zéro "
        f"({avant_serial} -> {apres_serial}) : numéros dupliqués sur l'air")
    # Les QSO n'avaient jamais bougé : c'est bien la PORTÉE qui était écrasée.
    assert len(storage.shared_log) == 3
