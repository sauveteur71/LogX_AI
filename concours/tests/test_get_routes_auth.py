# -*- coding: utf-8 -*-
"""Trois routes GET de lecture d'activité station exigent le jeton de session.

Avant : `/rig/cw/journal`, `/tx/audit`, `/dxcc/besoin` répondaient à quiconque
atteignait le port — un appareil non authentifié du LAN pouvait lire le journal
CW, la traçabilité d'émission TX et sonder les besoins DXCC (qui consulte le
carnet). Mêmes exigences que `/log/list` (durci en A09) : sans le jeton de
session, 403 ; avec, la route répond normalement.

Sans danger pour l'usage navigateur : les pages de l'appli appellent ces routes
en same-origin, le cookie rc_token part tout seul.
"""
import http.server
import threading
import urllib.request
import urllib.error

import pytest

import logx_http as httpmod

ROUTES = ['/rig/cw/journal', '/tx/audit', '/dxcc/besoin?call=F1ABC&band=14&mode=FT8']


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


def _get(base, path, token=False):
    req = urllib.request.Request(base + path, method='GET')
    if token:
        req.add_header('X-RC-Token', httpmod.AUTH_TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


@pytest.mark.parametrize('route', ROUTES)
def test_sans_jeton_403(server, route):
    assert _get(server, route, token=False) == 403, route


@pytest.mark.parametrize('route', ROUTES)
def test_avec_jeton_pas_403(server, route):
    # Avec le jeton, l'auth passe : la route répond (200, ou 4xx métier), jamais 403.
    assert _get(server, route, token=True) != 403, route
