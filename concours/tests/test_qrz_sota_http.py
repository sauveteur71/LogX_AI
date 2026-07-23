# -*- coding: utf-8 -*-
"""Tests HTTP de bout en bout pour le câblage QRZ Logbook / SOTA auto-spot
(POST /qrz_logbook/test, POST /sota/spot, GET /sota/status, GET
/sota/oauth/start, GET /sota/oauth/callback) — même harnais que
tests/test_pota_spot_http.py (vrai serveur sur port éphémère). Les modules
métier (logx_qrz_push, logx_sota_spot) sont monkeypatchés : ces tests
couvrent le CÂBLAGE du handler, pas le réseau (déjà couvert par
tests/test_qrz_push.py et tests/test_sota_spot.py)."""
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
import logx_qrz_push as qrz_push
import logx_sota_spot as sotaspot


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
    """(status, texte_du_corps, content_type) — le corps est lu ICI, dans le
    bloc `with` : le rendre après la fermeture de la réponse (comme le ferait
    un simple `return r.status, r`) renvoie un flux déjà épuisé (texte vide)."""
    req = urllib.request.Request(base + path, headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode('utf-8'), r.headers.get('Content-Type', '')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8'), e.headers.get('Content-Type', '') if e.headers else ''


def _post(base, path, payload=None):
    body = json.dumps(payload).encode('utf-8') if payload is not None else b''
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json', 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


# ─── /qrz_logbook/test ────────────────────────────────────────────────────────

def test_qrz_logbook_test_ok(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {'qrz_logbook_key': 'ABCD'})
    monkeypatch.setattr(qrz_push, 'test_connection', lambda cfg: {'ok': True, 'status': {}})
    status, d = _post(server, '/qrz_logbook/test')
    assert status == 200 and d['ok'] is True


def test_qrz_logbook_test_echec_remonte_en_400(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {})
    monkeypatch.setattr(qrz_push, 'test_connection', lambda cfg: {'ok': False, 'error': 'Clé manquante'})
    status, d = _post(server, '/qrz_logbook/test')
    assert status == 400 and d['ok'] is False


# ─── /sota/spot ───────────────────────────────────────────────────────────────

def test_sota_spot_reference_par_defaut_et_conversion_freq(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config',
                        {'callsign': 'F6KQJ', 'contest': '', 'my_activation_ref': 'F/AL-001'})
    captured = {}
    def fake_post_spot(cfg, reference, freq_mhz, mode, comment=''):
        captured.update(reference=reference, freq_mhz=freq_mhz, mode=mode)
        return {'ok': True, 'response': 'ok'}
    monkeypatch.setattr(sotaspot, 'post_spot', fake_post_spot)

    status, d = _post(server, '/sota/spot', {'freq_khz': 145500, 'mode': 'FM'})
    assert status == 200 and d['ok'] is True
    assert captured['reference'] == 'F/AL-001'
    assert captured['freq_mhz'] == pytest.approx(145.5)
    assert captured['mode'] == 'FM'


def test_sota_spot_echec_remonte_en_502(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config',
                        {'callsign': 'F6KQJ', 'contest': '', 'my_activation_ref': 'F/AL-001'})
    monkeypatch.setattr(sotaspot, 'post_spot',
                        lambda *a, **k: {'ok': False, 'error': 'SOTA non configuré'})
    status, d = _post(server, '/sota/spot', {'freq_khz': 145500, 'mode': 'FM'})
    assert status == 502 and d['ok'] is False


# ─── /sota/status ─────────────────────────────────────────────────────────────

def test_sota_status(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {})
    monkeypatch.setattr(sotaspot, 'status',
                        lambda cfg: {'configured': False, 'ai_approval_ack': False,
                                     'ready_to_post': False, 'authenticated': False})
    status, text, _ct = _get(server, '/sota/status')
    assert status == 200
    assert json.loads(text)['configured'] is False


# ─── /sota/oauth/start ────────────────────────────────────────────────────────

def test_sota_oauth_start_redirige_vers_sso(server, monkeypatch):
    """urllib suit les redirections par défaut — on parle directement en
    HTTP brut (http.client) pour observer le 302 + Location AVANT qu'il ne
    soit suivi, plutôt que de bidouiller un opener personnalisé."""
    import http.client
    from urllib.parse import urlsplit
    monkeypatch.setattr(httpmod, 'current_config', {'sota_client_id': 'CLIENT1'})
    monkeypatch.setattr(sotaspot, 'build_authorize_url',
                        lambda cfg: ('https://sso.sota.org.uk/auth/realms/SOTA/protocol/openid-connect/auth?x=1', ''))
    host_port = urlsplit(server).netloc
    conn = http.client.HTTPConnection(host_port, timeout=5)
    try:
        conn.request('GET', '/sota/oauth/start', headers={'X-RC-Token': httpmod.AUTH_TOKEN})
        resp = conn.getresponse()
        assert resp.status == 302
        assert resp.getheader('Location', '').startswith('https://sso.sota.org.uk/')
    finally:
        conn.close()


def test_sota_oauth_start_sans_client_id(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {})
    monkeypatch.setattr(sotaspot, 'build_authorize_url', lambda cfg: (None, 'clientId SOTA manquant'))
    status, text, _ct = _get(server, '/sota/oauth/start')
    assert status == 400 and 'clientId' in text


# ─── /sota/oauth/callback ─────────────────────────────────────────────────────

def test_sota_oauth_callback_succes(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {'sota_client_id': 'CLIENT1'})
    monkeypatch.setattr(sotaspot, 'handle_oauth_callback',
                        lambda code, state, cfg: (True, 'Authentification SOTA réussie.'))
    status, text, ct = _get(server, '/sota/oauth/callback?code=abc&state=xyz')
    assert status == 200
    assert 'réussie' in text
    assert ct.startswith('text/html')


def test_sota_oauth_callback_echec(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {})
    monkeypatch.setattr(sotaspot, 'handle_oauth_callback',
                        lambda code, state, cfg: (False, 'Session expirée'))
    status, text, _ct = _get(server, '/sota/oauth/callback?code=abc&state=xyz')
    assert status == 200   # la page d'erreur elle-même reste un 200 HTML, pas un code d'erreur HTTP
    assert 'Échec' in text
