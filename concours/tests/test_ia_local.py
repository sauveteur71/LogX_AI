# -*- coding: utf-8 -*-
"""Mode local uniquement (config ia_local_only) : AUCUN appel réseau IA.

Quand l'opérateur active le mode local, tous les chemins LLM basculent sur un
repli propre SANS toucher le réseau (zéro crédit). Les moteurs déterministes ne
sont pas concernés (ils n'appellent pas de LLM). On vérifie ici, pour chaque
chemin, le repli ET l'absence d'appel réseau (mouchard sur urlopen).
"""
import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.request

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as h   # noqa: E402

LOCAL = {'ia_local_only': True, 'api_key': 'x', 'api_provider': 'anthropic'}


def _mouchard_reseau(monkeypatch):
    """Toute tentative d'appel réseau fait ÉCHOUER le test (le mode local ne doit
    jamais atteindre le réseau)."""
    def interdit(*a, **k):
        raise AssertionError('appel réseau alors que le mode local est actif')
    monkeypatch.setattr(h.urllib.request, 'urlopen', interdit)


def test_ia_local_tolere_la_chaine_du_select():
    # Le <select> de CONFIG renvoie 'oui'/'non' — bool('non') vaudrait True, d'où
    # la tolérance explicite. Un booléen réel marche aussi.
    assert h._ia_local({'ia_local_only': 'oui'}) is True
    assert h._ia_local({'ia_local_only': 'true'}) is True
    assert h._ia_local({'ia_local_only': True}) is True
    assert h._ia_local({'ia_local_only': 'non'}) is False
    assert h._ia_local({'ia_local_only': ''}) is False
    assert h._ia_local({}) is False


def test_cablage_config_interrupteur():
    with open(os.path.join(CONCOURS, 'logx_configuration.html'), encoding='utf-8') as f:
        html = f.read()
    assert 'id="ia_local_only"' in html          # l'interrupteur existe
    with open(os.path.join(CONCOURS, 'logx_configuration.js'), encoding='utf-8') as f:
        js = f.read()
    assert "ia_local_only: (document.getElementById('ia_local_only')" in js   # lu à la sauvegarde
    assert "'ia_local_only'" in js               # appliqué au chargement (liste)


def test_call_llm_leve_sans_reseau(monkeypatch):
    _mouchard_reseau(monkeypatch)
    with pytest.raises(RuntimeError) as e:
        h.call_llm(LOCAL, 's', [{'role': 'user', 'content': 'q'}])
    assert 'local' in str(e.value).lower()


def test_call_llm_actions_repli_sans_reseau(monkeypatch):
    _mouchard_reseau(monkeypatch)
    r = h.call_llm_actions(LOCAL, 's', [{'role': 'user', 'content': 'q'}])
    assert r['action'] is None and 'local' in r['text'].lower()


def test_call_llm_stream_repli_sans_reseau(monkeypatch):
    _mouchard_reseau(monkeypatch)
    recu = []
    txt = h.call_llm_stream(LOCAL, 's', [{'role': 'user', 'content': 'q'}], on_delta=recu.append)
    assert 'local' in txt.lower() and recu and 'local' in recu[0].lower()


# ── Endpoint /proxy/ai (chat navigateur) ─────────────────────────────────────

@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % port
    srv.shutdown()


def _post(base, path, obj):
    rq = urllib.request.Request(base + path, data=json.dumps(obj).encode(),
                                headers={'Content-Type': 'application/json', 'X-RC-Token': h.AUTH_TOKEN},
                                method='POST')
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _seed(cfg):
    with h.config_lock:
        saved = dict(h.current_config)
        h.current_config.clear()
        h.current_config.update(cfg)
    return saved


def _restore(saved):
    with h.config_lock:
        h.current_config.clear()
        h.current_config.update(saved)


def test_proxy_ai_mode_local(serveur, monkeypatch):
    # le serveur ne doit PAS appeler le réseau ; on ne mouchard que côté serveur
    # via call_llm/urlopen : le proxy gate AVANT tout réseau.
    saved = _seed(LOCAL)
    try:
        code, j = _post(serveur, '/proxy/ai', {'messages': [{'role': 'user', 'content': 'salut'}]})
        assert code == 200
        assert 'local' in json.dumps(j).lower()      # message de repli, pas une vraie réponse IA
    finally:
        _restore(saved)


def test_session_plan_mode_local(serveur):
    saved = _seed(LOCAL)
    try:
        code, j = _post(serveur, '/session/plan', {'duree_min': 30})
        assert 'error' in j and 'local' in j['error'].lower()
    finally:
        _restore(saved)
