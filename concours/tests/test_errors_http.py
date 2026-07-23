# -*- coding: utf-8 -*-
"""GET /debug/errors expose le tampon mémoire de logx_errorlog.py (alimenté
par sys.excepthook/threading.excepthook) — c'est ce que lit le bouton
"Signaler un problème" de la barre de statut (logx_statusbar.js) pour
préremplir l'issue GitHub avec la dernière erreur connue.

Point important couvert ici : CONTRAIREMENT aux autres endpoints /debug/*
(voir logx_http.py, gate 'server.debug=true'), celui-ci doit répondre même
config debug=false — sinon le bouton "Signaler un problème" serait inopérant
pour l'écrasante majorité des testeurs (qui n'activeront jamais ce réglage)."""
import http.server
import json
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod
import logx_errorlog as errlog


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


@pytest.fixture(autouse=True)
def _isolate_errors(monkeypatch):
    monkeypatch.setattr(errlog, '_errors', [])
    yield
    monkeypatch.setattr(errlog, '_errors', [])


def _get(base, path):
    import urllib.request
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def test_debug_errors_vide_par_defaut(server):
    d = _get(server, '/debug/errors')
    assert d['errors'] == []
    assert 'log_path' in d


def test_debug_errors_expose_les_erreurs_enregistrees(server):
    try:
        raise RuntimeError('panne simulée')
    except RuntimeError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        errlog._record(exc_type, exc_value, exc_tb, 'MainThread')

    d = _get(server, '/debug/errors')
    assert len(d['errors']) == 1
    assert d['errors'][0]['type'] == 'RuntimeError'
    assert d['errors'][0]['message'] == 'panne simulée'


def test_debug_errors_accessible_sans_mode_debug_active(server, monkeypatch):
    """Contrairement aux autres /debug/*, pas besoin de server.debug=true :
    voir le commentaire d'exemption dans logx_http.py juste avant le gate."""
    with httpmod.config_lock:
        httpmod.current_config['debug'] = False
    d = _get(server, '/debug/errors')
    assert 'errors' in d   # pas de 404 "Endpoints /debug/* désactivés"


def test_autres_debug_restent_gates_par_defaut(server):
    """Vérifie que l'exemption ajoutée pour /debug/errors n'a pas
    accidentellement ouvert tout le préfixe /debug/* (garde-fou de
    non-régression sur le gate existant)."""
    import urllib.request
    import urllib.error
    with httpmod.config_lock:
        httpmod.current_config['debug'] = False
    try:
        with urllib.request.urlopen(server + '/debug/spots', timeout=5) as r:
            status = r.status
            body = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        status = e.code
        body = json.loads(e.read().decode('utf-8'))
    assert status == 404
    assert 'error' in body
