# -*- coding: utf-8 -*-
"""Tests HTTP de la vue PARTNER (saisie en direct, lecture seule) : POST
/chat/typing (diffusion, éphémère, jamais persisté) + GET /chat/list qui
l'expose (même poll que le chat, cf. logx_logbook.js pollChat/renderPartnerTyping).

Même modèle que tests/test_http_scope_endpoints.py (vrai serveur sur port
éphémère, pas de mock du dispatch HTTP)."""
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


@pytest.fixture(autouse=True)
def _clean_typing_state():
    """L'état de saisie en direct est un dict module-level : le vider avant
    CHAQUE test pour éviter toute pollution entre tests (process partagé)."""
    with httpmod.typing_lock:
        httpmod.typing_state.clear()
    yield
    with httpmod.typing_lock:
        httpmod.typing_state.clear()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def _post(base, path, payload):
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json',
                 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_typing_apparait_dans_chat_list(server):
    status, res = _post(server, '/chat/typing',
                        {'op': 'OP2', 'label': 'OP2 — F4ABC', 'band': '14',
                         'mode': 'CW', 'text': 'F5A'})
    assert status == 200 and res['ok']
    d = _get(server, '/chat/list?since=0')
    typing = {t['op']: t for t in d['typing']}
    assert 'OP2' in typing
    assert typing['OP2']['text'] == 'F5A'
    assert typing['OP2']['band'] == '14'
    assert typing['OP2']['label'] == 'OP2 — F4ABC'


def test_typing_ecrase_par_operateur(server):
    """Chaque frappe écrase l'entrée précédente du MÊME opérateur (une seule
    ligne par opérateur, pas un historique)."""
    _post(server, '/chat/typing', {'op': 'OP2', 'text': 'F5'})
    _post(server, '/chat/typing', {'op': 'OP2', 'text': 'F5ABC'})
    d = _get(server, '/chat/list?since=0')
    entries = [t for t in d['typing'] if t['op'] == 'OP2']
    assert len(entries) == 1
    assert entries[0]['text'] == 'F5ABC'


def test_typing_plusieurs_operateurs_distincts(server):
    _post(server, '/chat/typing', {'op': 'OP1', 'text': 'DL1AB'})
    _post(server, '/chat/typing', {'op': 'OP2', 'text': 'F5XYZ'})
    d = _get(server, '/chat/list?since=0')
    ops = {t['op'] for t in d['typing']}
    assert ops == {'OP1', 'OP2'}


def test_typing_sans_operateur_ignore(server):
    """Payload sans 'op' : rien n'est stocké (pas d'erreur non plus — la
    requête reste 'ok' pour ne jamais faire échouer un throttle client)."""
    status, res = _post(server, '/chat/typing', {'text': 'F5ABC'})
    assert status == 200 and res['ok']
    d = _get(server, '/chat/list?since=0')
    assert d['typing'] == []


def test_typing_perime_disparait(server, monkeypatch):
    """Une saisie non renouvelée depuis plus de TYPING_STALE_S doit
    disparaître de /chat/list (poste éteint/onglet fermé sans dernier POST vide)."""
    _post(server, '/chat/typing', {'op': 'OP3', 'text': 'DL2XX'})
    d = _get(server, '/chat/list?since=0')
    assert any(t['op'] == 'OP3' for t in d['typing'])

    import time as _time
    real_time = _time.time
    monkeypatch.setattr(httpmod.time, 'time',
                        lambda: real_time() + httpmod.TYPING_STALE_S + 1)
    d2 = _get(server, '/chat/list?since=0')
    assert not any(t['op'] == 'OP3' for t in d2['typing'])


def test_typing_texte_vide_efface_l_affichage_cote_serveur(server):
    """Le runner vide son champ (clearForm) : l'entrée est mise à jour avec un
    texte vide plutôt que supprimée (le client filtre déjà les textes vides à
    l'affichage, cf. renderPartnerTyping)."""
    _post(server, '/chat/typing', {'op': 'OP2', 'text': 'F5ABC'})
    _post(server, '/chat/typing', {'op': 'OP2', 'text': ''})
    d = _get(server, '/chat/list?since=0')
    entries = [t for t in d['typing'] if t['op'] == 'OP2']
    assert len(entries) == 1 and entries[0]['text'] == ''
