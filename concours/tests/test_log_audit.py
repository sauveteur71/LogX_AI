# -*- coding: utf-8 -*-
"""Audit IA du log avant dépôt (évolution IA #2, 01/08/2026).

En COMPLÉMENT du VÉRIFIER déterministe, une passe IA relit le log scopé et
repère ce qu'aucune règle ne code (indicatif busté, échange incohérent, même
indicatif à deux échanges, série incohérente, mult compté 2×). Les constats
sortent au MÊME format ({level,msg,id}) et réutilisent Corriger/Supprimer. Le
piège central : chaque constat DOIT porter un qso_id du lot envoyé, sinon les
boutons n'ont pas de cible — d'où le filtrage strict testé ici.
"""
import http.server
import json
import os
import sys
import threading
import time
import urllib.request

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_validator as validator   # noqa: E402
import logx_http as h                # noqa: E402


# ─── Briques pures ──────────────────────────────────────────────────────────

def test_build_audit_input_serialise_avec_les_id():
    qsos = [{'id': 1, 'call': 'w1aw', 'band': '14', 'mode': 'SSB', 'num_rcvd': '05'},
            {'id': 2, 'call': 'JA1XYZ', 'band': '14', 'mode': 'CW', 'num_rcvd': '25'}]
    inp = validator.build_audit_input(qsos, '', {})
    assert inp['valid_ids'] == {1, 2}
    assert '1 | W1AW' in inp['user_text']       # id présent + indicatif normalisé
    assert inp['truncated'] is False


def test_build_audit_input_ignore_les_qso_sans_id():
    qsos = [{'id': 1, 'call': 'F4ABC'}, {'call': 'SANS_ID'}]
    inp = validator.build_audit_input(qsos, '', {})
    assert inp['valid_ids'] == {1}


def test_build_audit_input_tronque_aux_plus_recents():
    qsos = [{'id': i, 'call': 'F%d' % i} for i in range(validator.MAX_AUDIT_QSOS + 50)]
    inp = validator.build_audit_input(qsos, '', {})
    assert inp['truncated'] is True
    assert len(inp['valid_ids']) == validator.MAX_AUDIT_QSOS
    # ce sont les DERNIERS (plus récents) qui sont gardés
    assert (validator.MAX_AUDIT_QSOS + 49) in inp['valid_ids']
    assert 0 not in inp['valid_ids']


def test_normalize_rejette_les_id_hors_lot():
    """LE piège : un constat visant un id absent du lot n'a pas de cible pour
    Corriger/Supprimer → il est écarté."""
    raw = [{'level': 'attention', 'message': 'W1AW busté ?', 'qso_id': 1},
           {'level': 'erreur', 'message': 'id fantôme', 'qso_id': 999},
           {'level': 'info', 'message': 'sans id'},
           {'level': 'attention', 'message': '', 'qso_id': 2}]   # message vide
    out = validator.normalize_audit_findings(raw, {1, 2})
    assert len(out) == 1
    assert out[0]['id'] == 1 and out[0]['ai'] is True
    assert out[0]['msg'] == 'W1AW busté ?'


def test_normalize_corrige_un_niveau_invalide():
    out = validator.normalize_audit_findings(
        [{'level': 'bizarre', 'message': 'x', 'qso_id': 1}], {1})
    assert out[0]['level'] == 'attention'


# ─── Endpoint asynchrone /log/audit + /log/audit/state ──────────────────────

@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % port
    srv.shutdown()


def _post(base, path, body=b'{}', token=True):
    hdr = {'Content-Type': 'application/json'}
    if token:
        hdr['X-RC-Token'] = h.AUTH_TOKEN
    rq = urllib.request.Request(base + path, data=body, headers=hdr, method='POST')
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _seed(qsos, cfg):
    with h.log_lock:
        saved_log = list(h.shared_log)
        h.shared_log[:] = qsos
    with h.config_lock:
        saved_cfg = dict(h.current_config)
        h.current_config.clear()
        h.current_config.update(cfg)
    return saved_log, saved_cfg


def _restore(saved_log, saved_cfg):
    with h.log_lock:
        h.shared_log[:] = saved_log
    with h.config_lock:
        h.current_config.clear()
        h.current_config.update(saved_cfg)


def test_audit_complet_ne_garde_que_les_id_du_lot(serveur, monkeypatch):
    import logx_rules_ai as rai
    # l'IA renvoie un constat valide (id 1) et un id fantôme (999) : seul le
    # premier doit survivre, avec son bouton d'action.
    monkeypatch.setattr(rai, 'call_ai_structured', lambda *a, **k: {'findings': [
        {'level': 'attention', 'message': 'W1AW probablement busté (zone 5 ailleurs)', 'qso_id': 1},
        {'level': 'erreur', 'message': 'constat sur un id absent', 'qso_id': 999},
    ]})
    qsos = [{'id': 1, 'call': 'W1AW', 'band': '14', 'mode': 'SSB', 'num_rcvd': '20'},
            {'id': 2, 'call': 'JA1XYZ', 'band': '14', 'mode': 'SSB', 'num_rcvd': '25'}]
    saved = _seed(qsos, {'api_key': 'x', 'api_provider': 'anthropic'})
    try:
        code, j = _post(serveur, '/log/audit')
        assert code == 200 and j.get('id')
        aid = j['id']
        # poll jusqu'à done
        findings = None
        for _ in range(50):
            with urllib.request.urlopen(serveur + '/log/audit/state?id=' + aid, timeout=5) as r:
                s = json.loads(r.read())
            if s['status'] != 'running':
                findings = s.get('findings')
                assert s['status'] == 'done'
                break
            time.sleep(0.1)
        assert findings is not None, 'audit resté en running'
        assert len(findings) == 1
        assert findings[0]['id'] == 1 and findings[0]['ai'] is True
    finally:
        _restore(*saved)


def test_audit_sans_cle_refuse(serveur):
    qsos = [{'id': 1, 'call': 'W1AW'}]
    saved = _seed(qsos, {'api_key': ''})     # pas de clé
    try:
        code, j = _post(serveur, '/log/audit')
        assert code == 400 and 'error' in j
    finally:
        _restore(*saved)


def test_audit_exige_le_token(serveur):
    saved = _seed([{'id': 1, 'call': 'W1AW'}], {'api_key': 'x'})
    try:
        code, _ = _post(serveur, '/log/audit', token=False)
        assert code in (401, 403)
    finally:
        _restore(*saved)
