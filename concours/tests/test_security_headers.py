# -*- coding: utf-8 -*-
"""En-têtes de sécurité HTTP émis par _security_headers().

Le serveur pose déjà X-Frame-Options: SAMEORIGIN et une CSP frame-ancestors
pour empêcher l'encadrement (cf. test_lightning_iframe_sandbox). Ce test fige
en plus X-Content-Type-Options: nosniff — sans lui, un fichier servi (scan QSL,
export…) pourrait être MIME-sniffé par le navigateur au lieu de respecter le
Content-Type déclaré. C'est de la défense en profondeur : bon marché, sans
changement de comportement pour les réponses au type correct.

Le test frappe le VRAI serveur (ThreadingHTTPServer) sur une route publique
sans auth (/data/rules_status) : _security_headers() est appelée par l'émetteur
de réponse commun, donc l'en-tête doit être présent sur toute réponse.
"""
import http.server
import threading
import urllib.request
import urllib.error

import pytest

import logx_http as httpmod


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield 'http://127.0.0.1:%d' % port
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _get_headers(base, path):
    req = urllib.request.Request(base + path, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}


def test_nosniff_present(server):
    status, headers = _get_headers(server, '/data/rules_status')
    assert status == 200, status
    assert headers.get('x-content-type-options') == 'nosniff', headers


def test_frame_options_toujours_present(server):
    # Le jeu d'en-têtes de sécurité complet reste posé (garde-fou de non-régression).
    _status, headers = _get_headers(server, '/data/rules_status')
    assert headers.get('x-frame-options') == 'SAMEORIGIN', headers
