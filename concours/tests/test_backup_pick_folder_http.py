# -*- coding: utf-8 -*-
"""Tests HTTP de bout en bout pour POST /backup/pick_folder (bouton
« 📁 » à côté du champ DOSSIER DE SAUVEGARDE, CONFIG). Même harnais que
tests/test_pota_spot_http.py (vrai serveur sur port éphémère).
logx_winshell.pick_folder est monkeypatché : ces tests couvrent le CÂBLAGE
du handler (jeton, transmission de initial_dir, code HTTP selon le
résultat), pas le dialogue Windows réel (voir tests/test_winshell.py)."""
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
import logx_winshell as winshell


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


def _post(base, path, payload, with_token=True):
    body = json.dumps(payload).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if with_token:
        headers['X-RC-Token'] = httpmod.AUTH_TOKEN
    req = urllib.request.Request(base + path, data=body, method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_sans_jeton_refuse(server):
    """Comme toute autre route POST (hors /auth/login) : jeton exigé, même
    pour un dialogue purement local — sinon un autre appareil du LAN
    pourrait déclencher un dialogue Windows sur ce poste."""
    status, d = _post(server, '/backup/pick_folder', {}, with_token=False)
    assert status in (401, 403)


def test_dossier_choisi_rempli_dans_la_reponse(server, monkeypatch):
    monkeypatch.setattr(winshell, 'pick_folder',
                        lambda **kw: {'ok': True, 'path': 'C:\\Users\\test\\logs'})
    status, d = _post(server, '/backup/pick_folder', {'initial_dir': 'C:\\old'})
    assert status == 200
    assert d == {'ok': True, 'path': 'C:\\Users\\test\\logs'}


def test_annulation_remonte_400_sans_lever(server, monkeypatch):
    monkeypatch.setattr(winshell, 'pick_folder', lambda **kw: {'ok': False, 'error': 'annule'})
    status, d = _post(server, '/backup/pick_folder', {})
    assert status == 400 and d['ok'] is False and d['error'] == 'annule'


def test_plateforme_non_supportee_remonte_le_message(server, monkeypatch):
    monkeypatch.setattr(winshell, 'pick_folder', lambda **kw: {
        'ok': False, 'error': 'plateforme non supportee',
        'message': "Le choix graphique du dossier n'est disponible que sous Windows."})
    status, d = _post(server, '/backup/pick_folder', {})
    assert status == 400
    assert d['error'] == 'plateforme non supportee'
    assert 'Windows' in d['message']


def test_initial_dir_transmise_a_pick_folder(server, monkeypatch):
    captured = {}
    def fake_pick_folder(title='', initial_dir=''):
        captured['title'] = title
        captured['initial_dir'] = initial_dir
        return {'ok': True, 'path': initial_dir}
    monkeypatch.setattr(winshell, 'pick_folder', fake_pick_folder)

    status, d = _post(server, '/backup/pick_folder', {'initial_dir': 'C:\\Sauvegardes'})
    assert status == 200
    assert captured['initial_dir'] == 'C:\\Sauvegardes'
    assert captured['title']  # un titre non vide est passé au dialogue


def test_corps_vide_ne_plante_pas_le_handler(server, monkeypatch):
    """Le client peut appeler sans corps JSON (aucun dossier initial connu) :
    le handler doit tolérer ça plutôt que planter sur json.loads('')."""
    monkeypatch.setattr(winshell, 'pick_folder', lambda **kw: {'ok': True, 'path': 'C:\\x'})
    body = b''
    req = urllib.request.Request(
        server + '/backup/pick_folder', data=body, method='POST',
        headers={'Content-Type': 'application/json', 'X-RC-Token': httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        status = r.status
        d = json.loads(r.read().decode('utf-8'))
    assert status == 200 and d['ok'] is True


def test_exception_dans_pick_folder_remonte_500(server, monkeypatch):
    def _boom(**kw):
        raise RuntimeError('powershell introuvable')
    monkeypatch.setattr(winshell, 'pick_folder', _boom)
    status, d = _post(server, '/backup/pick_folder', {})
    assert status == 500 and d['ok'] is False
