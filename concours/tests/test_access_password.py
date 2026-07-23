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
from urllib.parse import urlparse, quote

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
def isolated_auth_token_file(tmp_path, monkeypatch):
    """Redirige AUTH_TOKEN_FILE vers un tmp_path : _set_access_password fait
    maintenant tourner AUTH_TOKEN (voir _rotate_auth_token), qui écrirait sinon
    dans le VRAI .auth_token du poste à chaque test — inacceptable (jeton de
    production changé par la suite de tests). Le `monkeypatch.setattr` sur
    AUTH_TOKEN lui-même capture la valeur courante et la restaure après le
    test, même si _rotate_auth_token la réaffecte entre-temps via `global`."""
    tok_file = tmp_path / '.auth_token'
    monkeypatch.setattr(httpmod, 'AUTH_TOKEN_FILE', str(tok_file))
    monkeypatch.setattr(httpmod, 'AUTH_TOKEN', httpmod.AUTH_TOKEN)
    yield tok_file


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    """La fenêtre anti-bruteforce (_login_attempts) est un dict global tenu en
    mémoire pour toute la durée du process pytest : sans reset, les échecs
    accumulés par un test (ex. le test de rate-limit lui-même) pollueraient
    les tests suivants qui utilisent la même IP (127.0.0.1)."""
    httpmod._login_attempts.clear()
    yield
    httpmod._login_attempts.clear()


@pytest.fixture
def server(isolated_password_file, isolated_auth_token_file):
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

def test_verify_access_password_helpers(isolated_password_file, isolated_auth_token_file):
    assert httpmod._access_password_enabled() is False
    assert httpmod._verify_access_password('anything') is False
    httpmod._set_access_password('correcthorse')
    assert httpmod._access_password_enabled() is True
    assert httpmod._verify_access_password('correcthorse') is True
    assert httpmod._verify_access_password('wrong') is False
    assert httpmod._verify_access_password('') is False
    httpmod._clear_access_password()
    assert httpmod._access_password_enabled() is False


# ─── Revue adversariale du commit 040e32f : XSS reflété sur /auth/login ──────
# (voir _serve_login_page). Avant le fix, `next_path` (query string, jamais
# neutralisé pour un contexte HTML/JS) était interpolé via json.dumps() dans
# un littéral JS à l'intérieur d'un <script> — json.dumps() n'échappe pas
# '<'/'>' : une valeur contenant "</script><script>...</script>" refermait le
# <script> d'origine et exécutait le script injecté sur LA MÊME origine (vol
# possible du cookie rc_token via un fetch() automatique).

def test_login_page_next_echappe_les_balises_html(server, isolated_password_file):
    _enable_password(server)
    poc_variants = [
        '/</script><script>alert(document.domain)</script>',
        '/</ScRiPt><ScRiPt>alert(document.domain)</ScRiPt>',  # casse mixte
    ]
    for payload in poc_variants:
        status, headers, body = _raw_request(
            server, 'GET', '/auth/login?next=' + quote(payload, safe=''))
        assert status == 200
        text = body.decode('utf-8')
        # La séquence de rupture ne doit plus jamais apparaître non échappée
        # (peu importe la casse) : c'est elle qui referme le <script> d'origine.
        assert '</script><script>' not in text.lower()
        # Le nom de balise ne doit plus apparaître adjacent à '<' ou '>' bruts
        # dans la zone <script> — seule une forme échappée (&lt;/&gt;) est admise.
        assert '<script>alert(document.domain)' not in text
        assert '<scRipt>alert(document.domain)' not in text


def test_login_page_next_legitime_toujours_fonctionnel(server, isolated_password_file):
    """Non-régression : un `next` légitime (relatif, sans caractère spécial)
    doit toujours être repris tel quel après le fix (échappement HTML neutre
    sur ce genre de valeur)."""
    _enable_password(server)
    status, headers, body = _raw_request(
        server, 'GET', '/auth/login?next=' + quote('/logx_carte.html', safe=''))
    assert status == 200
    assert b'/logx_carte.html' in body


# ─── Revue adversariale : DoS CPU trivial sur /auth/login (pas de limite) ────
# (voir _login_rate_limited). Chaque tentative déclenche normalement un
# PBKDF2-HMAC-SHA256 à 200000 itérations (~83 ms) — sans limite par IP, un
# client peut le rejouer en boucle serrée et saturer le CPU du serveur.

def test_login_rate_limit_apres_echecs_repetes(server, isolated_password_file, monkeypatch):
    _enable_password(server)
    verify_calls = []
    orig_verify = httpmod._verify_access_password

    def counting_verify(pw):
        verify_calls.append(pw)
        return orig_verify(pw)

    monkeypatch.setattr(httpmod, '_verify_access_password', counting_verify)
    statuses = [
        _raw_request(server, 'POST', '/auth/login', {'password': 'faux'})[0]
        for _ in range(httpmod._LOGIN_ATTEMPT_LIMIT + 3)
    ]
    # Au-delà du seuil, le serveur rejette (429) sans plus jamais recalculer
    # le hash coûteux — sans ce fix, chaque appel appelle _verify_access_password
    # et le dernier statut resterait 401 (mauvais mot de passe), jamais 429.
    assert statuses[-1] == 429
    assert len(verify_calls) <= httpmod._LOGIN_ATTEMPT_LIMIT


def test_login_rate_limit_nest_pas_par_ip_partagee_entre_tests(server, isolated_password_file):
    """Un seul échec ne doit jamais suffire à déclencher la limite (seuil
    largement au-dessus d'une simple faute de frappe)."""
    _enable_password(server)
    status, headers, body = _raw_request(
        server, 'POST', '/auth/login', {'password': 'faux'})
    assert status == 401


# ─── Revue adversariale : lecture tronquée du corps si Content-Length > 4096 ─
# (voir MAX_LOGIN_BODY dans _handle_auth_login_post). Avant le fix,
# `length = max(0, min(length, 4096))` lisait silencieusement les 4096
# premiers octets d'un corps plus grand au lieu de rejeter — incohérent avec
# MAX_BODY dans do_POST (vérifié AVANT lecture, 413 immédiat).

def test_login_corps_trop_volumineux_rejete_413(server, isolated_password_file):
    _enable_password(server)
    huge_password = 'a' * 5000  # garantit un Content-Length > 4096
    status, headers, body = _raw_request(
        server, 'POST', '/auth/login', {'password': huge_password})
    assert status == 413
    assert 'Set-Cookie' not in headers


# ─── Revue adversariale : le token n'est jamais tourné (best-effort, LOW) ────
# (voir _rotate_auth_token, appelée depuis _set_access_password). Avant le
# fix, AUTH_TOKEN était un secret statique jamais modifié : activer ou
# changer le mot de passe d'accès ne révoquait aucun cookie rc_token déjà
# distribué (ex. obtenu pendant que le port était encore en accès libre).

def test_set_password_tourne_le_jeton_et_revoque_les_anciens_cookies(
        server, isolated_password_file, isolated_auth_token_file):
    old_token = httpmod.AUTH_TOKEN
    status, headers, body = _raw_request(
        server, 'POST', '/auth/set_password', {'password': 'topsecret'},
        headers={'X-RC-Token': old_token})
    assert status == 200
    assert json.loads(body) == {'ok': True, 'enabled': True}
    new_token = httpmod.AUTH_TOKEN
    assert new_token != old_token
    # L'ancien cookie ne doit plus donner les droits d'écriture.
    status2, _, _ = _raw_request(
        server, 'POST', '/auth/set_password', {'password': ''},
        headers={'Cookie': f'rc_token={old_token}'})
    assert status2 == 403
    # La session qui vient de définir le mot de passe reçoit immédiatement le
    # nouveau jeton — elle ne doit pas se retrouver déconnectée par son propre
    # changement.
    assert _cookie_value(headers) == new_token
    _, _, status_body = _raw_request(
        server, 'GET', '/auth/status', headers={'Cookie': f'rc_token={new_token}'})
    assert json.loads(status_body)['authorized'] is True
