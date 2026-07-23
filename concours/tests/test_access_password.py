# -*- coding: utf-8 -*-
"""Mot de passe d'accès optionnel avant remise du jeton d'écriture (rc_token).

Comportement par défaut (fichier .access_password absent) INCHANGÉ : le
cookie rc_token est distribué automatiquement à toute page HTML servie (voir
logx_http.do_GET). Ces tests couvrent le chemin optionnel ajouté (POST
/auth/set_password + page /auth/login) sans jamais toucher au VRAI fichier
.access_password du poste — il est redirigé vers un tmp_path à chaque test
(fixture `isolated_password_file`), sans quoi un test pourrait écraser ou
effacer le mot de passe réel de l'opérateur."""
import http.client
import http.server
import json
import os
import sys
import threading
from urllib.parse import urlparse

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod


@pytest.fixture
def isolated_password_file(tmp_path, monkeypatch):
    pw_file = tmp_path / '.access_password'
    monkeypatch.setattr(httpmod, 'ACCESS_PASSWORD_FILE', str(pw_file))
    yield pw_file


@pytest.fixture
def server(isolated_password_file):
    srv = http.server.HTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        t.join(timeout=5)


def _raw_request(base, method, path, body=None, headers=None):
    """Requête HTTP bas niveau : pas de suivi automatique des redirections
    (contrairement à urllib.request) et accès direct aux en-têtes bruts
    (Set-Cookie, Location)."""
    u = urlparse(base)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=10)
    data = json.dumps(body).encode('utf-8') if body is not None else None
    hdrs = dict(headers or {})
    if data is not None:
        hdrs.setdefault('Content-Type', 'application/json')
    conn.request(method, path, body=data, headers=hdrs)
    r = conn.getresponse()
    out_body = r.read()
    out_headers = dict(r.getheaders())
    conn.close()
    return r.status, out_headers, out_body


def _cookie_value(headers):
    sc = headers.get('Set-Cookie', '')
    if 'rc_token=' not in sc:
        return None
    return sc.split('rc_token=', 1)[1].split(';', 1)[0]


# ─── Comportement par défaut (aucun mot de passe configuré) : INCHANGÉ ───────

def test_par_defaut_cookie_distribue_automatiquement(server):
    status, headers, _ = _raw_request(server, 'GET', '/logx_scope.html')
    assert status == 200
    assert _cookie_value(headers) == httpmod.AUTH_TOKEN


def test_par_defaut_auth_status_desactive(server):
    status, headers, body = _raw_request(server, 'GET', '/auth/status')
    assert status == 200
    assert json.loads(body) == {'enabled': False, 'authorized': False}


# ─── Activation du mot de passe (POST /auth/set_password) ───────────────────

def test_set_password_active_la_protection(server, isolated_password_file):
    status, headers, body = _raw_request(
        server, 'POST', '/auth/set_password', {'password': 'topsecret'},
        headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    assert status == 200
    assert json.loads(body) == {'ok': True, 'enabled': True}
    assert isolated_password_file.exists()


def test_mot_de_passe_jamais_stocke_en_clair(server, isolated_password_file):
    _raw_request(server, 'POST', '/auth/set_password', {'password': 'topsecret'},
                 headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    raw = isolated_password_file.read_text(encoding='utf-8')
    assert 'topsecret' not in raw
    stored = json.loads(raw)
    assert set(stored.keys()) == {'salt', 'hash'}
    assert len(stored['hash']) == 64  # sha256 hex digest


def test_set_password_trop_court_rejete(server):
    status, headers, body = _raw_request(
        server, 'POST', '/auth/set_password', {'password': 'abc'},
        headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    assert status == 400
    assert json.loads(body)['ok'] is False
    assert httpmod._access_password_enabled() is False


def test_set_password_exige_deja_un_jeton_valide(server):
    # Aucun cookie, aucun header X-RC-Token : la route /auth/set_password est
    # une route POST comme les autres, donc protégée par _require_auth.
    status, headers, body = _raw_request(
        server, 'POST', '/auth/set_password', {'password': 'topsecret'})
    assert status == 403
    assert httpmod._access_password_enabled() is False


# ─── Une fois le mot de passe activé : le cookie n'est plus automatique ──────

def _enable_password(server, pw='topsecret'):
    _raw_request(server, 'POST', '/auth/set_password', {'password': pw},
                 headers={'X-RC-Token': httpmod.AUTH_TOKEN})


def test_page_html_redirige_vers_login_sans_cookie(server, isolated_password_file):
    _enable_password(server)
    status, headers, _ = _raw_request(server, 'GET', '/logx_scope.html')
    assert status == 302
    assert headers['Location'].startswith('/auth/login?next=')
    assert 'Set-Cookie' not in headers


def test_page_html_servie_normalement_avec_cookie_valide(server, isolated_password_file):
    _enable_password(server)
    status, headers, body = _raw_request(
        server, 'GET', '/logx_scope.html',
        headers={'Cookie': f'rc_token={httpmod.AUTH_TOKEN}'})
    assert status == 200
    assert b'<html' in body.lower() or b'<!doctype' in body.lower()


def test_auth_status_reflete_activation(server, isolated_password_file):
    _enable_password(server)
    status, headers, body = _raw_request(server, 'GET', '/auth/status')
    assert json.loads(body)['enabled'] is True


def test_login_mauvais_mot_de_passe_refuse(server, isolated_password_file):
    _enable_password(server)
    status, headers, body = _raw_request(
        server, 'POST', '/auth/login', {'password': 'faux'})
    assert status == 401
    assert 'Set-Cookie' not in headers
    assert json.loads(body)['ok'] is False


def test_login_bon_mot_de_passe_pose_le_cookie(server, isolated_password_file):
    _enable_password(server)
    status, headers, body = _raw_request(
        server, 'POST', '/auth/login', {'password': 'topsecret'})
    assert status == 200
    assert json.loads(body)['ok'] is True
    assert _cookie_value(headers) == httpmod.AUTH_TOKEN


def test_login_page_get_accessible_sans_cookie(server, isolated_password_file):
    """/auth/login lui-même ne doit jamais rediriger vers /auth/login (boucle)."""
    _enable_password(server)
    status, headers, body = _raw_request(server, 'GET', '/auth/login?next=/logx_carte.html')
    assert status == 200
    assert b'form' in body.lower()


def test_login_sans_mot_de_passe_configure_est_rejete(server):
    """Si /auth/login est appelée alors qu'aucun mot de passe n'est configuré
    (ex. lien /auth/login trouvé dans l'historique après désactivation) —
    ne doit jamais accorder le cookie silencieusement."""
    status, headers, body = _raw_request(
        server, 'POST', '/auth/login', {'password': 'peu importe'})
    assert status == 400
    assert 'Set-Cookie' not in headers


# ─── Désactivation (password vide) : retour au comportement par défaut ──────

def test_disable_password_restaure_la_distribution_automatique(server, isolated_password_file):
    _enable_password(server)
    status, headers, body = _raw_request(
        server, 'POST', '/auth/set_password', {'password': ''},
        headers={'Cookie': f'rc_token={httpmod.AUTH_TOKEN}'})
    assert status == 200
    assert json.loads(body) == {'ok': True, 'enabled': False}
    assert not isolated_password_file.exists()
    status2, headers2, _ = _raw_request(server, 'GET', '/logx_scope.html')
    assert status2 == 200
    assert _cookie_value(headers2) == httpmod.AUTH_TOKEN


# ─── Vérification directe des helpers (temps constant, robustesse) ──────────

def test_verify_access_password_helpers(isolated_password_file):
    assert httpmod._access_password_enabled() is False
    assert httpmod._verify_access_password('anything') is False
    httpmod._set_access_password('correcthorse')
    assert httpmod._access_password_enabled() is True
    assert httpmod._verify_access_password('correcthorse') is True
    assert httpmod._verify_access_password('wrong') is False
    assert httpmod._verify_access_password('') is False
    httpmod._clear_access_password()
    assert httpmod._access_password_enabled() is False
