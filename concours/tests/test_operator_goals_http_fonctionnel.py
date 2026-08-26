# -*- coding: utf-8 -*-
"""Round-trip HTTP RÉEL du profil d'objectifs (option b). Au-delà des tests
unitaires (module) et structurels (câblage), on démarre un vrai serveur et on
exerce GET/POST /data/operator_goals via http.client, cookie d'auth inclus —
comme un vrai client. Fichier de stockage isolé dans un tmp (aucune écriture
sur l'état réel). Même harnais que test_http_body_length.py."""
import http.client
import http.server
import json
import os
import sys
import threading

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CONCOURS)

import logx_http as httpmod          # noqa: E402
import logx_operator_goals as og     # noqa: E402


@pytest.fixture
def serveur(tmp_path, monkeypatch):
    # stockage dédié isolé : le POST écrit ici, pas dans le vrai .operator_goals.json
    monkeypatch.setattr(og, 'FICHIER', str(tmp_path / 'objectifs.json'))
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _conn(port):
    return http.client.HTTPConnection('127.0.0.1', port, timeout=8)


def _headers():
    return {'Content-Type': 'application/json',
            'Cookie': 'rc_token=%s' % getattr(httpmod, 'AUTH_TOKEN', '')}


def _get(port):
    c = _conn(port)
    c.request('GET', '/data/operator_goals', headers=_headers())
    r = c.getresponse(); body = r.read(); c.close()
    return r.status, json.loads(body or b'{}')


def _post(port, payload):
    c = _conn(port)
    data = json.dumps(payload).encode()
    c.request('POST', '/data/operator_goals', body=data, headers=_headers())
    r = c.getresponse(); body = r.read(); c.close()
    return r.status, json.loads(body or b'{}')


def test_get_defaut_tout_actif(serveur):
    st, d = _get(serveur)
    assert st == 200
    assert d['goals'] == {k: True for k in og.CLES}      # fichier absent -> défauts


def test_post_puis_get_persiste(serveur):
    st, d = _post(serveur, {'goals': {'dxcc': False, 'vucc': False}})
    assert st == 200 and d['ok'] is True
    assert d['goals']['dxcc'] is False and d['goals']['vucc'] is False
    assert d['goals']['dxcc_new_band'] is True           # les autres au défaut
    # relecture par un NOUVEAU GET : la valeur a bien été persistée côté serveur
    st2, d2 = _get(serveur)
    assert st2 == 200 and d2['goals'] == d['goals']


def test_post_jette_les_cles_inconnues(serveur):
    st, d = _post(serveur, {'goals': {'inconnue': True, 'dxcc': False}})
    assert st == 200
    assert set(d['goals']) == set(og.CLES)               # que les clés connues
    assert 'inconnue' not in d['goals']


def test_post_sans_auth_refuse(serveur):
    # sans cookie rc_token, le POST doit être refusé (porte d'auth globale)
    c = _conn(serveur)
    c.request('POST', '/data/operator_goals', body=b'{"goals":{}}',
              headers={'Content-Type': 'application/json'})
    r = c.getresponse(); r.read(); c.close()
    assert r.status in (401, 403)                         # jamais 200
