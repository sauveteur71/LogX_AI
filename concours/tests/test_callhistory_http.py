# -*- coding: utf-8 -*-
"""Tests HTTP de bout en bout (vrai serveur sur port éphémère, voir
test_http_scope_endpoints.py pour le même motif) pour les endpoints ajoutés
autour de logx_callhistory.py : import MASTER.SCP, import Call History N1MM,
vérification N+1, statut. La logique pure est déjà couverte par
tests/test_callhistory_import.py — ici on vérifie seulement le CÂBLAGE HTTP
(auth, lecture du corps JSON, code de statut, portée concours passée depuis
la config courante).

monkeypatch.chdir(tmp_path) est indispensable ici (contrairement aux autres
tests HTTP du dépôt) : ces endpoints écrivent de VRAIS fichiers
(master_scp.json / call_history_n1mm.json) — sans isolation de cwd, lancer
la suite de tests aurait pollué le dossier réel du projet."""
import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod
import logx_callhistory as ch


@pytest.fixture
def server():
    srv = http.server.HTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        t.join(timeout=5)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def _post(base, path, payload, token=True):
    body = json.dumps(payload).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['X-RC-Token'] = httpmod.AUTH_TOKEN
    req = urllib.request.Request(base + path, data=body, method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


@pytest.fixture(autouse=True)
def _reset_callhistory_cache(monkeypatch):
    """Même précaution que test_callhistory_import.py : jamais de cache
    hérité d'un test précédent (index général ni Call History N1MM)."""
    monkeypatch.setattr(ch, '_index', {})
    monkeypatch.setattr(ch, '_built_at', 0.0)
    monkeypatch.setattr(ch, '_ch_cache', None)
    monkeypatch.setattr(ch, '_ch_cache_mtime', None)
    yield


# ─── /callhistory/import_scp ────────────────────────────────────────────────

def test_import_scp_isole_du_repertoire_reel(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    status, res = _post(server, '/callhistory/import_scp', {'text': 'F4GLD\nF5ABC\n'})
    assert status == 200 and res['ok'] and res['imported'] == 2 and res['total'] == 2
    assert os.path.isfile(tmp_path / 'master_scp.json')


def test_import_scp_sans_token_refuse(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    status, res = _post(server, '/callhistory/import_scp', {'text': 'F4GLD\n'}, token=False)
    assert status == 403
    assert not os.path.isfile(tmp_path / 'master_scp.json')   # rien écrit


def test_import_scp_fichier_vide_erreur(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    status, res = _post(server, '/callhistory/import_scp', {'text': ''})
    assert status == 400 and res['ok'] is False


# ─── /callhistory/import_n1mm ───────────────────────────────────────────────

def test_import_n1mm_utilise_le_concours_du_payload(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = {'contest': 'REF_CDF_HF_CW', 'text': '!!Order!!,Call,Exch1\nF4GLD,75\n'}
    status, res = _post(server, '/callhistory/import_n1mm', payload)
    assert status == 200 and res['ok'] and res['imported'] == 1
    assert ch.call_history_count('REF_CDF_HF_CW') == 1


def test_import_n1mm_repli_sur_le_concours_de_la_config(server, tmp_path, monkeypatch):
    """Sans 'contest' explicite dans le corps, retombe sur le concours
    actuellement configuré côté serveur (cohérent avec le concours affiché
    dans le popup CONFIG au moment de l'import)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(httpmod, 'current_config', {'contest': 'CQ_WW_SSB'})
    status, res = _post(server, '/callhistory/import_n1mm',
                        {'text': '!!Order!!,Call,Exch1\nF4GLD,14\n'})
    assert status == 200 and res['ok']
    assert ch.call_history_count('CQ_WW_SSB') == 1


def test_import_n1mm_sans_aucun_concours_erreur(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(httpmod, 'current_config', {'contest': ''})
    status, res = _post(server, '/callhistory/import_n1mm',
                        {'text': '!!Order!!,Call,Exch1\nF4GLD,14\n'})
    assert status == 400 and res['ok'] is False


# ─── /call/near (vérification N+1) ─────────────────────────────────────────

def test_call_near_rattrape_une_frappe_fausse(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'shared_log',
                        [{'call': 'F4GLD', 'locator': 'JN18AA', 'date': '20260101', 'num_rcvd': ''}])
    res = _get(server, '/call/near?call=F4GLDD')
    assert any(m['call'] == 'F4GLD' for m in res['matches'])


# ─── /callhistory/status ────────────────────────────────────────────────────

def test_callhistory_status_reflete_les_imports(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(httpmod, 'current_config', {'contest': 'REF_CDF_HF_CW'})
    _post(server, '/callhistory/import_scp', {'text': 'F4GLD\nF5ABC\nF6KQJ\n'})
    _post(server, '/callhistory/import_n1mm',
         {'contest': 'REF_CDF_HF_CW', 'text': '!!Order!!,Call,Exch1\nF4GLD,75\n'})
    res = _get(server, '/callhistory/status')
    assert res['master_scp_count'] == 3
    assert res['contest'] == 'REF_CDF_HF_CW'
    assert res['call_history_count'] == 1


# ─── /call/index : surclassé par le concours actif ─────────────────────────

def test_call_index_surclasse_avec_le_concours_actif(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(httpmod, 'shared_log',
                        [{'call': 'F4GLD', 'locator': 'JN18AA', 'date': '20260101', 'num_rcvd': ''}])
    monkeypatch.setattr(httpmod, 'current_config', {'contest': 'REF_CDF_HF_CW'})
    _post(server, '/callhistory/import_n1mm',
         {'contest': 'REF_CDF_HF_CW', 'text': '!!Order!!,Call,Exch1,Name\nF4GLD,75,Jean\n'})
    res = _get(server, '/call/index')
    assert res['calls']['F4GLD']['dept'] == '75'
    assert res['calls']['F4GLD']['name'] == 'Jean'
