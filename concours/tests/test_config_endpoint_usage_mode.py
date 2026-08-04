# -*- coding: utf-8 -*-
"""GET /config expose usage_mode (liste blanche publique, logx_http.py) —
même harnais que tests/test_pota_spot_http.py (vrai serveur sur port éphémère).

Sans ce champ, une page détachée comme logx_panel.html (qui n'a accès qu'à
cet endpoint public, pas à current_config côté serveur) ne peut pas
reproduire côté client la règle logx_storage.contest_actif() — d'où le
bouton "Ce concours" du Worked Matrix affiché même quand il n'a aucun effet
(usage_mode == 'simple', voir logx_storage.cfg_scope_id)."""
import http.server
import json
import os
import sys
import threading

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
        srv.server_close()
        t.join(timeout=5)


def _get(base, path):
    import urllib.request
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def test_config_expose_usage_mode(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {
        'callsign': 'F4GLD', 'contest': 'REF_RPH', 'usage_mode': 'contest',
    })
    status, d = _get(server, '/config')
    assert status == 200
    assert d['usage_mode'] == 'contest'
    assert d['contest'] == 'REF_RPH'


def test_config_usage_mode_absent_replie_sur_chaine_vide(server, monkeypatch):
    """Config sans usage_mode (profil ancien/incomplet) : la liste blanche
    utilise cfg_snap.get(k, ''), pas cfg_snap[k] -> pas de KeyError."""
    monkeypatch.setattr(httpmod, 'current_config', {'callsign': 'F4GLD', 'contest': ''})
    status, d = _get(server, '/config')
    assert status == 200
    assert d['usage_mode'] == ''


def test_config_n_expose_aucun_secret():
    """Garde-fou : la liste blanche ne doit jamais gagner de clé sensible en
    passant (API keys, mots de passe...) — voir le commentaire "AUCUN secret"
    à côté de la liste blanche dans logx_http.py."""
    import inspect
    src = inspect.getsource(httpmod)
    i = src.index("safe = {k: cfg_snap.get(k, '') for k in (")
    j = src.index(')}', i)
    bloc = src[i:j]
    for interdit in ('password', 'api_key', 'apikey', 'token', 'secret', 'clublog_password'):
        assert interdit not in bloc.lower(), f'{interdit} ne doit pas apparaître dans la liste blanche /config'
