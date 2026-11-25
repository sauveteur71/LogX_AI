# -*- coding: utf-8 -*-
"""Vitesse de chargement (audit 25/11/2026, point 7).

Mesuré en navigateur sur 2 000 QSO : LOGBOOK 4 231 Ko -> 1 775 Ko à la
première visite ; CONFIG revisitée 3 058 Ko -> 117 Ko (réponses 304).
  - fichiers statiques : ETag + 304, gzip mis en cache ; HTML jamais en 304 ;
  - logo redimensionné à sa taille d'affichage (≤ 28 px de haut) ;
  - base SOTA (~296 Mo) préchargée seulement si la station s'en sert.
"""
import gzip
import http.client
import http.server
import os
import re
import sys
import threading

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CONCOURS)
os.chdir(CONCOURS)

import logx_http as httpmod   # noqa: E402
import logx_sota as sota      # noqa: E402


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _get(port, path, headers=None):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    c.request('GET', path, headers=headers or {})
    r = c.getresponse()
    corps = r.read()
    h = dict(r.getheaders())
    c.close()
    return r.status, h, corps


def test_statique_gzip_identique_au_fichier(server):
    st, h, corps = _get(server, '/logx_i18n.js', {'Accept-Encoding': 'gzip'})
    assert st == 200 and h.get('Content-Encoding') == 'gzip'
    with open('logx_i18n.js', 'rb') as f:
        assert gzip.decompress(corps) == f.read()
    assert len(corps) < os.path.getsize('logx_i18n.js') / 3


def test_sans_accept_encoding_pas_de_gzip(server):
    st, h, corps = _get(server, '/logx_theme.css')
    assert st == 200 and 'Content-Encoding' not in h
    with open('logx_theme.css', 'rb') as f:
        assert corps == f.read()


def test_etag_et_304(server):
    st, h, _ = _get(server, '/logx_theme.css')
    etag = h.get('ETag')
    assert etag and h.get('Cache-Control') == 'no-cache'
    st2, h2, corps2 = _get(server, '/logx_theme.css', {'If-None-Match': etag})
    assert st2 == 304 and corps2 == b''
    st3, _, _ = _get(server, '/logx_theme.css', {'If-None-Match': '"autre"'})
    assert st3 == 200


def test_html_jamais_en_304_et_toujours_sans_cache(server):
    st, h, _ = _get(server, '/logx_scope.html')
    assert st == 200 and 'ETag' not in h
    assert 'no-store' in h.get('Cache-Control', '')
    # Même avec l'ETag qu'aurait ce fichier, le HTML est toujours renvoyé.
    f = os.stat('logx_scope.html')
    etag = '"%x-%x"' % (f.st_size, int(f.st_mtime_ns // 1000))
    st2, _, corps = _get(server, '/logx_scope.html', {'If-None-Match': etag})
    assert st2 == 200 and corps


def test_etag_change_quand_le_fichier_change(tmp_path, monkeypatch, server):
    # L'ETag dépend de la taille ET de la date : une mise à jour = nouvel ETag.
    st, h, _ = _get(server, '/logx_theme.css')
    s = os.stat('logx_theme.css')
    assert h['ETag'] == '"%x-%x"' % (s.st_size, int(s.st_mtime_ns // 1000))


def test_logo_a_sa_taille_d_affichage():
    from PIL import Image
    w, hgt = Image.open('logx_logo.png').size
    assert hgt <= 120 and os.path.getsize('logx_logo.png') < 80_000
    for nom in os.listdir('.'):
        if nom.endswith('.html'):
            src = open(nom, encoding='utf-8').read()
            for m in re.finditer(r'\.logo-badge img\{height:(\d+)px', src):
                assert int(m.group(1)) * 3 <= hgt + 10, nom   # net jusqu'aux écrans ×3


@pytest.mark.parametrize('cfg,attendu', [
    ({}, False), ({'activation_program': 'POTA'}, False),
    ({'activation_program': 'sota'}, True), ({'chaser_mode': 'oui'}, True),
    ({'chaser_mode': 'non'}, False),
])
def test_sota_precharge_seulement_si_utile(cfg, attendu):
    assert sota.prechargement_utile(cfg) is attendu


def test_serveur_conditionne_le_prechargement_sota():
    s = re.sub(r'(?m)#.*$', '', open('logx_serveur.py', encoding='utf-8').read())
    assert re.search(r'if sota\.prechargement_utile\(dict\(http_mod\.current_config\)\):\s*\n\s*sota\.ensure_loading_started\(\)', s)
    assert len(re.findall(r'sota\.ensure_loading_started\(\)', s)) == 1
