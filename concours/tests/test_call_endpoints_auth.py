# -*- coding: utf-8 -*-
"""Sécurité (A09, audit 26/08) : les endpoints /call/* exposent des données
DÉRIVÉES DU CARNET (index des indicatifs, historique par station, matches
proches) — comme /log/list, ils doivent exiger le jeton de session. Sans ça,
tout appareil du LAN lit le carnet entier sans mot de passe.

Round-trip HTTP réel : sans cookie rc_token -> refusé ; avec cookie -> autorisé.
Même harnais que test_operator_goals_http_fonctionnel / test_http_body_length."""
import http.client
import http.server
import os
import sys
import threading

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CONCOURS)

import logx_http as httpmod   # noqa: E402


@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _status(port, path, avec_cookie):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=8)
    headers = {}
    if avec_cookie:
        headers['Cookie'] = 'rc_token=%s' % getattr(httpmod, 'AUTH_TOKEN', '')
    c.request('GET', path, headers=headers)
    r = c.getresponse(); r.read(); c.close()
    return r.status


CHEMINS = ['/call/index', '/call/history?call=F4GLD', '/call/near?call=F4GLD']


@pytest.mark.parametrize('chemin', CHEMINS)
def test_sans_auth_refuse(serveur, chemin):
    # sans cookie de session : jamais 200 (le carnet ne fuit pas)
    assert _status(serveur, chemin, avec_cookie=False) in (401, 403)


@pytest.mark.parametrize('chemin', CHEMINS)
def test_avec_auth_autorise(serveur, chemin):
    # avec le cookie : l'UI légitime accède normalement (pas de 401/403)
    st = _status(serveur, chemin, avec_cookie=True)
    assert st not in (401, 403)
