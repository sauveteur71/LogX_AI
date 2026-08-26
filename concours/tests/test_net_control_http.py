# -*- coding: utf-8 -*-
"""Round-trip HTTP RÉEL du contrôle de réseau (net control), tranche 1. On
démarre un vrai serveur et on exerce GET /data/nets + POST /nets/* via
http.client, cookie d'auth inclus. Fichier de stockage isolé dans un tmp
(aucune écriture sur l'état réel). Même harnais que
test_operator_goals_http_fonctionnel.py."""
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
import logx_net_control as nc        # noqa: E402


@pytest.fixture
def serveur(tmp_path, monkeypatch):
    monkeypatch.setattr(nc, 'FICHIER', str(tmp_path / 'nets.json'))
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
    c.request('GET', '/data/nets', headers=_headers())
    r = c.getresponse(); body = r.read(); c.close()
    return r.status, json.loads(body or b'{}')


def _post(port, path, payload):
    c = _conn(port)
    c.request('POST', path, body=json.dumps(payload).encode(), headers=_headers())
    r = c.getresponse(); body = r.read(); c.close()
    return r.status, json.loads(body or b'{}')


def test_get_vide_par_defaut(serveur):
    st, d = _get(serveur)
    assert st == 200 and d == {'nets': []}


def test_creer_puis_get_persiste(serveur):
    st, d = _post(serveur, '/nets/create',
                  {'nom': 'Dimanche', 'freq': '3.650', 'mode': 'LSB', 'bande': '80m'})
    assert st == 200 and d['ok'] is True
    net = d['net']
    assert net['nom'] == 'Dimanche' and isinstance(net['id'], int)
    # relecture par un NOUVEAU GET : persisté côté serveur
    st2, d2 = _get(serveur)
    assert st2 == 200 and len(d2['nets']) == 1 and d2['nets'][0]['id'] == net['id']


def test_repertoire_ajout_dedupe_et_retrait(serveur):
    _, d = _post(serveur, '/nets/create', {'nom': 'A'})
    nid = d['net']['id']
    _, d1 = _post(serveur, '/nets/roster/add', {'net_id': nid, 'membre': {'call': 'f5abc', 'nom': 'Jean'}})
    assert [m['call'] for m in d1['net']['roster']] == ['F5ABC']
    # même indicatif (casse différente) -> pas de doublon, info mise à jour
    _, d2 = _post(serveur, '/nets/roster/add', {'net_id': nid, 'membre': {'call': 'F5ABC', 'qth': 'Lyon'}})
    assert len(d2['net']['roster']) == 1 and d2['net']['roster'][0]['qth'] == 'Lyon'
    # retrait insensible à la casse
    _, d3 = _post(serveur, '/nets/roster/remove', {'net_id': nid, 'call': 'f5abc'})
    assert d3['net']['roster'] == []


def test_supprimer_reseau(serveur):
    _, d = _post(serveur, '/nets/create', {'nom': 'A'})
    nid = d['net']['id']
    st, _ = _post(serveur, '/nets/delete', {'id': nid})
    assert st == 200
    _, g = _get(serveur)
    assert g['nets'] == []


def test_get_sans_auth_refuse(serveur):
    c = _conn(serveur)
    c.request('GET', '/data/nets')          # aucun cookie
    r = c.getresponse(); r.read(); c.close()
    assert r.status in (401, 403)           # jamais 200


def test_post_sans_auth_refuse(serveur):
    c = _conn(serveur)
    c.request('POST', '/nets/create', body=b'{"nom":"X"}',
              headers={'Content-Type': 'application/json'})
    r = c.getresponse(); r.read(); c.close()
    assert r.status in (401, 403)
