# -*- coding: utf-8 -*-
"""GET /activation/summary : résumé à vie des activations/chasses par programme,
agrégé depuis le log partagé. Harnais serveur réel sur port éphémère."""
import http.server
import json
import os
import sys
import threading
import urllib.request

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
    req = urllib.request.Request(base + path, headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def test_activation_summary_endpoint(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'shared_log', [
        {'my_sig': 'POTA', 'my_sig_info': 'FR-0123'},
        {'my_sig': 'POTA', 'my_sig_info': 'FR-0456'},
        {'sig': 'SOTA', 'sig_info': 'F/AB-001'},
    ])
    status, data = _get(server, '/activation/summary')
    assert status == 200
    assert data['POTA']['activated'] == 2 and data['POTA']['hunted'] == 0
    assert data['POTA']['activated_refs'] == ['FR-0123', 'FR-0456']
    assert data['SOTA']['hunted'] == 1 and data['SOTA']['hunted_refs'] == ['F/AB-001']
