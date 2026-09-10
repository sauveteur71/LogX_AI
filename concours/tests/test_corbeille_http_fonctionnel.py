# -*- coding: utf-8 -*-
"""Round-trip HTTP RÉEL de la corbeille de QSO : démarre un vrai serveur,
supprime un QSO via /log/delete/<id> (DELETE réel, comme un client PC),
vérifie qu'il apparaît dans GET /log/corbeille, le restaure via POST
/log/corbeille/restore et vérifie qu'il est revenu dans le carnet. Même
harnais que test_operator_goals_http_fonctionnel.py / test_log_delta_sync.py
(shared_log/save_log_to_disk monkeypatchés, aucune écriture réelle)."""
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
import logx_corbeille as cb          # noqa: E402
import logx_storage as storage       # noqa: E402

QSO = {'id': 42, 'call': 'F4TEST', 'band': '14', 'mode': 'SSB',
       'date': '20260910', 'time': '1200'}


@pytest.fixture
def serveur(tmp_path, monkeypatch):
    monkeypatch.setattr(cb, 'FICHIER', str(tmp_path / 'corbeille.json'))
    monkeypatch.setattr(httpmod, 'shared_log', [dict(QSO)])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda *a, **kw: None)
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'simple'})
    # mark_qso_deleted() (appelé par /log/delete/<id>) mute logx_storage.
    # deleted_qsos EN PLACE (append), une liste GLOBALE au process pytest --
    # sans cette isolation, chaque suppression déclenchée par ces tests
    # polluait deleted_qsos pour TOUT LE RESTE de la suite (reproduit :
    # test_log_delta_sync.py::test_log_list_since_valide_ne_renvoie_que_le_delta
    # voyait apparaître [42, 42] dans data['deleted'] alors qu'il ne touche
    # jamais /log/delete lui-même).
    monkeypatch.setattr(storage, 'deleted_qsos', [])
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


def _get(port, path):
    c = _conn(port)
    c.request('GET', path, headers=_headers())
    r = c.getresponse(); body = r.read(); c.close()
    return r.status, json.loads(body or b'{}')


def _delete(port, path):
    c = _conn(port)
    c.request('DELETE', path, headers=_headers())
    r = c.getresponse(); body = r.read(); c.close()
    return r.status, json.loads(body or b'{}')


def _post(port, path, payload):
    c = _conn(port)
    data = json.dumps(payload).encode()
    c.request('POST', path, body=data, headers=_headers())
    r = c.getresponse(); body = r.read(); c.close()
    return r.status, json.loads(body or b'{}')


def test_corbeille_vide_au_depart(serveur):
    st, d = _get(serveur, '/log/corbeille')
    assert st == 200 and d['entries'] == []


def test_suppression_capture_le_qso_dans_la_corbeille(serveur):
    st, d = _delete(serveur, '/log/delete/42')
    assert st == 200 and d['ok'] is True and d['deleted'] == 1
    assert httpmod.shared_log == []                      # bien retiré du carnet

    st2, d2 = _get(serveur, '/log/corbeille')
    assert st2 == 200 and len(d2['entries']) == 1
    entree = d2['entries'][0]
    assert entree['id'] == 42 and entree['call'] == 'F4TEST' and entree['band'] == '14'


def test_restauration_remet_le_qso_dans_le_carnet(serveur):
    _delete(serveur, '/log/delete/42')
    st, d = _post(serveur, '/log/corbeille/restore', {'id': 42})
    assert st == 200 and d['ok'] is True
    assert d['qso']['call'] == 'F4TEST'
    assert len(httpmod.shared_log) == 1
    assert httpmod.shared_log[0]['call'] == 'F4TEST'
    # id TOUJOURS réattribué, jamais l'original : mark_qso_deleted (posé à la
    # suppression) met l'id sous tombstone, et reserve_qso_id_locked traite un
    # id tombstoné comme pris (logx_storage._used_qso_ids) — protection anti-
    # résurrection pour un pair cloud déjà synchronisé sur « id X supprimé ».
    assert httpmod.shared_log[0]['id'] != 42

    # retiré de la corbeille après restauration (pas restaurable deux fois)
    st2, d2 = _get(serveur, '/log/corbeille')
    assert st2 == 200 and d2['entries'] == []


def test_restauration_naffecte_jamais_un_id_deja_utilise(serveur):
    _delete(serveur, '/log/delete/42')
    # un AUTRE QSO occupe déjà l'id que reserve_qso_id_locked allouerait
    # naturellement (ex. import, autre poste) — la restauration ne doit
    # jamais créer de doublon d'id, quelle que soit la situation du carnet.
    httpmod.shared_log.append({'id': 43, 'call': 'AUTRE'})
    st, d = _post(serveur, '/log/corbeille/restore', {'id': 42})
    assert st == 200 and d['ok'] is True
    ids = [q['id'] for q in httpmod.shared_log]
    assert len(ids) == len(set(ids))                        # aucun doublon d'id
    restaure = next(q for q in httpmod.shared_log if q.get('call') == 'F4TEST')
    assert restaure['id'] not in (42, 43)


def test_restauration_id_introuvable_rend_erreur(serveur):
    st, d = _post(serveur, '/log/corbeille/restore', {'id': 999})
    assert st == 404 and d['ok'] is False


def test_corbeille_get_sans_auth_refuse(serveur):
    c = _conn(serveur)
    c.request('GET', '/log/corbeille')
    r = c.getresponse(); r.read(); c.close()
    assert r.status in (401, 403)


def test_corbeille_restore_sans_auth_refuse(serveur):
    c = _conn(serveur)
    c.request('POST', '/log/corbeille/restore', body=b'{"id":42}',
              headers={'Content-Type': 'application/json'})
    r = c.getresponse(); r.read(); c.close()
    assert r.status in (401, 403)
