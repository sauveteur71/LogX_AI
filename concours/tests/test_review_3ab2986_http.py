# -*- coding: utf-8 -*-
"""Revue adversariale du commit 3ab2986 (bandmap waterfall, scans QSL papier,
records DX) — 3 correctifs HTTP de bout en bout (vrai serveur sur port
éphémère, même technique que tests/test_http_scope_endpoints.py) :

  - POST /qsl_scan/upload mutait le QSO cible (target['qsl_scan']=...,
    bump_log_version, stamp_qso_version) HORS de log_lock, avec le verrou
    relâché entre la recherche du QSO et sa mutation — une course avec une
    suppression/modification concurrente pouvait muter un dict déjà retiré
    de shared_log (perte silencieuse + fichier de scan orphelin) ;

  - GET /awards/activity?days= n'avait aucune borne supérieure (seul
    max(1, ...) côté bas dans activity_by_day) ;

  - DELETE (et son doublon POST) /log/delete/<id> ne supprimait jamais le
    fichier de scan QSL papier attaché au QSO supprimé (seul le REMPLACEMENT
    d'un scan appelait qslscan.delete_scan())."""
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

import logx_qsl_scan as qslscan
import logx_http as httpmod

JPEG_BYTES = b'\xff\xd8\xff\xe0' + b'\x00' * 40 + b'\xff\xd9'   # en-tête/pied JPEG minimal


@pytest.fixture
def server():
    srv = http.server.HTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        t.join(timeout=5)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def _delete(base, path):
    req = urllib.request.Request(base + path, method='DELETE',
                                  headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def _post_json(base, path, payload):
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json',
                 'X-RC-Token': httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def _multipart_body(boundary, fields=None, files=None):
    """Même helper que tests/test_qsl_scan_upload.py."""
    parts = []
    for name, value in (fields or {}).items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f'{value}\r\n'.encode('utf-8'))
    for name, (filename, data, content_type) in (files or {}).items():
        head = (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n')
        parts.append(head.encode('utf-8') + data + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode('utf-8'))
    return b''.join(parts)


def _post_multipart(base, path, fields=None, files=None):
    boundary = 'PyTestUploadBoundary'
    body = _multipart_body(boundary, fields, files)
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}',
                 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


# ─── Problème 2 : mutation atomique de /qsl_scan/upload sous log_lock ────────

def test_upload_qso_supprime_pendant_lecriture_du_scan_ne_le_ressuscite_pas(server, tmp_path, monkeypatch):
    """Reproduction concrète de la course : un AUTRE thread supprime le QSO
    juste après que save_scan() a écrit le fichier sur disque — exactement la
    fenêtre où le verrou était relâché entre la recherche du QSO et sa
    mutation (avant le fix). Avec le bug, la mutation finale s'appliquait
    quand même sur le dict (déjà retiré de shared_log, mais toujours
    référencé par la variable locale 'target') : réponse 200 « ok » alors que
    le QSO est bel et bien supprimé, et le fichier tout juste écrit devenait
    orphelin (jamais nettoyé). Avec le fix, la présence du QSO est revérifiée
    SOUS le même verrou que la mutation : la disparition est détectée, la
    réponse est 404, et le fichier est nettoyé au lieu de rester orphelin."""
    monkeypatch.chdir(tmp_path)
    qso = {'id': 42, 'call': 'F5ABC'}
    monkeypatch.setattr(httpmod, 'shared_log', [qso])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)

    real_save_scan = qslscan.save_scan

    def _save_scan_puis_suppression_concurrente(qso_id, filename, data):
        rel = real_save_scan(qso_id, filename, data)
        # Simule /log/delete/<id> exécuté par un AUTRE thread PENDANT l'upload
        # (juste après l'écriture du fichier, avant la mutation du QSO).
        with httpmod.log_lock:
            httpmod.shared_log[:] = [q for q in httpmod.shared_log if q.get('id') != qso_id]
        return rel

    monkeypatch.setattr(qslscan, 'save_scan', _save_scan_puis_suppression_concurrente)

    status, res = _post_multipart(server, '/qsl_scan/upload',
                                  fields={'qso_id': '42'},
                                  files={'file': ('carte.jpg', JPEG_BYTES, 'image/jpeg')})

    assert status == 404 and not res['ok']
    assert httpmod.shared_log == []   # pas de résurrection fantôme du QSO supprimé
    # Le fichier écrit par save_scan() avant la course ne doit pas rester orphelin.
    remaining = os.listdir(qslscan.SCANS_DIR) if os.path.isdir(qslscan.SCANS_DIR) else []
    assert remaining == []


def test_upload_ok_toujours_attache_le_scan_en_labsence_de_course(server, tmp_path, monkeypatch):
    """Non-régression : le cas nominal (pas de course) continue de fonctionner
    exactement comme avant — voir aussi tests/test_qsl_scan_upload.py."""
    monkeypatch.chdir(tmp_path)
    qso = {'id': 43, 'call': 'F5ABC'}
    monkeypatch.setattr(httpmod, 'shared_log', [qso])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)

    status, res = _post_multipart(server, '/qsl_scan/upload',
                                  fields={'qso_id': '43'},
                                  files={'file': ('carte.jpg', JPEG_BYTES, 'image/jpeg')})
    assert status == 200 and res['ok']
    assert qso['qsl_scan'] == res['qsl_scan']
    assert os.path.isfile(res['qsl_scan'])


# ─── Problème 3 : /awards/activity?days= borné ───────────────────────────────

def test_awards_activity_days_enorme_est_borne(server, tmp_path, monkeypatch):
    """Sans borne haute, ?days= très grand ferait construire à activity_by_day
    (qui ne fait que max(1, ...) côté bas) une liste de sortie de taille
    arbitraire. Ici : une valeur bien au-delà de tout usage légitime doit être
    ramenée au plafond (3650 = 10 ans) plutôt que d'être prise telle quelle."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(httpmod, 'shared_log', [])
    import logx_awards as awards
    awards.invalidate()   # évite de retomber sur le cache TTL d'un cwd précédent
    d = _get(server, '/awards/activity?days=100000')
    assert len(d['days']) == 3650


def test_awards_activity_days_normal_inchange(server, tmp_path, monkeypatch):
    """Non-régression : une valeur raisonnable n'est pas affectée par le clamp."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(httpmod, 'shared_log', [])
    import logx_awards as awards
    awards.invalidate()
    d = _get(server, '/awards/activity?days=15')
    assert len(d['days']) == 15


# ─── Problème 4 : /log/delete/<id> supprime le scan QSL attaché ─────────────

def test_delete_qso_via_delete_supprime_le_scan_qsl_attache(server, tmp_path, monkeypatch):
    """Reproduction : un QSO avec un scan QSL papier attaché (qsl_scan) est
    supprimé via DELETE /log/delete/<id> — avant le fix, seul le REMPLACEMENT
    d'un scan (2e upload, voir /qsl_scan/upload) appelait delete_scan() :
    supprimer directement le QSO laissait le fichier orphelin sur disque
    indéfiniment."""
    monkeypatch.chdir(tmp_path)
    rel = qslscan.save_scan(7, 'carte.jpg', JPEG_BYTES)
    assert os.path.isfile(rel)
    qso = {'id': 7, 'call': 'F5ABC', 'qsl_scan': rel}
    monkeypatch.setattr(httpmod, 'shared_log', [qso])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)

    res = _delete(server, '/log/delete/7')
    assert res['ok'] and res['deleted'] == 1
    assert not os.path.isfile(rel)   # fichier nettoyé, pas d'orphelin


def test_delete_qso_sans_scan_ne_leve_pas(server, tmp_path, monkeypatch):
    """Non-régression : supprimer un QSO SANS scan attaché doit continuer de
    fonctionner sans erreur (pas de scan à nettoyer)."""
    monkeypatch.chdir(tmp_path)
    qso = {'id': 11, 'call': 'F5XYZ'}
    monkeypatch.setattr(httpmod, 'shared_log', [qso])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)

    res = _delete(server, '/log/delete/11')
    assert res['ok'] and res['deleted'] == 1


def test_delete_qso_via_post_supprime_aussi_le_scan_qsl(server, tmp_path, monkeypatch):
    """Le point d'entrée POST /log/delete/<id> (doublon de do_DELETE dans
    logx_http.py, conservé pour les clients qui ne peuvent pas émettre de
    vrai DELETE) doit bénéficier du même nettoyage — pas seulement DELETE."""
    monkeypatch.chdir(tmp_path)
    rel = qslscan.save_scan(8, 'carte.png', JPEG_BYTES)
    assert os.path.isfile(rel)
    qso = {'id': 8, 'call': 'F5XYZ', 'qsl_scan': rel}
    monkeypatch.setattr(httpmod, 'shared_log', [qso])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)

    res = _post_json(server, '/log/delete/8', {})
    assert res['ok'] and res['deleted'] == 1
    assert not os.path.isfile(rel)
