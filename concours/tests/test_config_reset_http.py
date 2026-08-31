# -*- coding: utf-8 -*-
"""Test HTTP de /config/reset (réinitialisation DOUCE de la configuration).
Vrai serveur sur port éphémère (même motif que test_autostart_http.py).

Propriété clé : la config revient aux défauts MAIS les identifiants
(SECRET_FIELDS) sont conservés ; le carnet n'est pas touché ; confirmation
obligatoire ; jeton obligatoire. `_save_config_to_disk` est MOCKÉ — jamais
écraser le vrai .server_config.json (le harnais chdir dans concours/)."""
import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod       # noqa: E402


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


def _post(base, path, payload, token=True):
    body = json.dumps(payload).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['X-RC-Token'] = httpmod.AUTH_TOKEN
    req = urllib.request.Request(base + path, data=body, method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


@pytest.fixture
def config_factice(monkeypatch):
    """Config avec un champ station (callsign) + un secret (qrz_password), et
    l'écriture disque neutralisée (capture l'objet écrit)."""
    ecrit = {}
    monkeypatch.setattr(httpmod, 'current_config', {
        'callsign': 'F4GLD', 'locator': 'JN18', 'contest': 'REF',
        'qrz_password': 'motdepasse-secret', 'api_key': 'sk-abc'})
    monkeypatch.setattr(httpmod, '_save_config_to_disk',
                        lambda cfg: ecrit.update({'cfg': dict(cfg)}))
    return ecrit


def test_reset_conserve_les_secrets_et_vide_le_reste(server, config_factice):
    status, res = _post(server, '/config/reset', {'confirm': 'RESET'})
    assert status == 200 and res['ok'] is True
    # les identifiants sont dans la liste des conservés
    assert 'qrz_password' in res['secrets_conserves'] and 'api_key' in res['secrets_conserves']
    # état résultant : secrets gardés, champs station effacés
    assert httpmod.current_config.get('qrz_password') == 'motdepasse-secret'
    assert httpmod.current_config.get('api_key') == 'sk-abc'
    assert 'callsign' not in httpmod.current_config
    assert 'locator' not in httpmod.current_config
    # ce qui a été écrit sur disque = uniquement les secrets
    assert config_factice['cfg'] == {'qrz_password': 'motdepasse-secret', 'api_key': 'sk-abc'}


def test_reset_sans_confirmation_refuse(server, config_factice):
    status, res = _post(server, '/config/reset', {})
    assert status == 400 and res['ok'] is False
    # rien n'a été écrit, la config est intacte
    assert 'cfg' not in config_factice
    assert httpmod.current_config.get('callsign') == 'F4GLD'


def test_reset_mauvaise_confirmation_refuse(server, config_factice):
    status, res = _post(server, '/config/reset', {'confirm': 'oui'})
    assert status == 400 and res['ok'] is False
    assert httpmod.current_config.get('callsign') == 'F4GLD'


def test_reset_sans_jeton_refuse(server, config_factice):
    status, res = _post(server, '/config/reset', {'confirm': 'RESET'}, token=False)
    assert status == 403
    # aucune écriture, config intacte
    assert 'cfg' not in config_factice
    assert httpmod.current_config.get('callsign') == 'F4GLD'


def test_reset_ne_touche_pas_au_carnet(server, config_factice, monkeypatch):
    import logx_storage
    avant = list(logx_storage.shared_log)
    _post(server, '/config/reset', {'confirm': 'RESET'})
    assert list(logx_storage.shared_log) == avant   # carnet inchangé
