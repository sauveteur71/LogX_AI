# -*- coding: utf-8 -*-
"""Compression gzip des réponses JSON (logx_http.Handler._raw, dont dérive
_json — le point d'unification de la quasi-totalité des endpoints) : activée
seulement si le client l'annonce (Accept-Encoding: gzip) et si le corps est
assez gros pour que ça vaille le coup (voir _GZIP_MIN_SIZE). Avant ce
correctif, AUCUNE compression n'existait : /log/list renvoie plusieurs Mo de
JSON brut sur un log de plusieurs milliers de QSO, à chaque poll de chaque
poste connecté."""
import gzip
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
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()   # libere la socket d ecoute
        t.join(timeout=5)


def _raw_get(base, path, accept_encoding=None):
    """Requête HTTP bas niveau : urllib.request décompresserait tout seul et
    masquerait le header Content-Encoding qu'on veut justement vérifier."""
    u = urlparse(base)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
    # A09 (docs/FEUILLE_DE_ROUTE.md) : /log/list exige désormais le jeton de
    # session, comme les autres routes de lecture protégées.
    headers = {'X-RC-Token': httpmod.AUTH_TOKEN}
    if accept_encoding is not None:
        headers['Accept-Encoding'] = accept_encoding
    conn.request('GET', path, headers=headers)
    r = conn.getresponse()
    body = r.read()
    headers_out = dict(r.getheaders())
    conn.close()
    return r.status, headers_out, body


def _big_log(n=500):
    return [{'id': i, 'call': f'F{i}ABC', 'band': '14', 'mode': 'SSB',
             'date': '20260720', 'time': '10:00'} for i in range(n)]


def test_pas_de_compression_sans_accept_encoding(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'shared_log', _big_log())
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'simple'})
    status, headers, body = _raw_get(server, '/log/list')
    assert status == 200
    assert 'Content-Encoding' not in headers
    data = json.loads(body.decode('utf-8'))
    assert len(data['qsos']) == 500


def test_compression_gzip_avec_accept_encoding(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'shared_log', _big_log())
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'simple'})
    status, headers, body = _raw_get(server, '/log/list', accept_encoding='gzip, deflate')
    assert status == 200
    assert headers.get('Content-Encoding') == 'gzip'
    decompressed = gzip.decompress(body)
    data = json.loads(decompressed.decode('utf-8'))
    assert len(data['qsos']) == 500
    # Content-Length doit correspondre au corps COMPRESSÉ réellement envoyé
    # (sinon le client tronque/bloque la lecture de la réponse).
    assert int(headers['Content-Length']) == len(body)
    assert len(body) < len(decompressed)


def test_petite_reponse_non_compressee_meme_avec_accept_encoding(server, monkeypatch):
    """Sous _GZIP_MIN_SIZE, compresser coûterait plus cher (CPU + en-tête
    gzip ~20 octets) que ça ne rapporte — ex. un log vide."""
    monkeypatch.setattr(httpmod, 'shared_log', [])
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'simple'})
    status, headers, body = _raw_get(server, '/log/list', accept_encoding='gzip')
    assert status == 200
    assert 'Content-Encoding' not in headers
    assert len(body) <= httpmod.Handler._GZIP_MIN_SIZE
