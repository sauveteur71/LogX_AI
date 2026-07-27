# -*- coding: utf-8 -*-
"""Tests du planning de roulement des opérateurs (écran mural) : modèle de
données bas niveau dans logx_storage (attribution d'id, rétro-compatibilité
au chargement, tri) + les 3 endpoints HTTP dans logx_http (/shifts/list,
/shifts/add, /shifts/delete/<id>). Calqué sur tests/test_qtc.py (modèle) et
tests/test_http_scope_endpoints.py (HTTP bout en bout, vrai serveur sur port
éphémère) — le planning réutilise exactement le même patron que le système
QTC déjà en place."""
import http.server
import json
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_storage as st


def _in_tmp(tmp_path, fn):
    """Exécute fn dans un dossier vierge (SHIFTS_FILE est un chemin relatif)."""
    old = os.getcwd()
    os.chdir(tmp_path)
    saved_shifts = list(st.operator_shifts)
    saved_next_id = st._shifts_next_id
    try:
        st.operator_shifts[:] = []
        return fn()
    finally:
        st.operator_shifts[:] = saved_shifts
        st._shifts_next_id = saved_next_id
        os.chdir(old)


# ─── Modèle de données (logx_storage) ────────────────────────────────────────

def test_next_shift_id_est_croissant(tmp_path):
    def run():
        a = st.next_shift_id()
        b = st.next_shift_id()
        c = st.next_shift_id()
        assert a < b < c
    _in_tmp(tmp_path, run)


def test_load_shifts_backfill_id_creneau_ancien_format(tmp_path):
    """Comme load_qtc_from_disk() : un créneau sans champ 'id' (fichier
    modifié à la main, ou format antérieur) reçoit un id qui n'entre jamais
    en collision avec un id déjà présent ailleurs dans le fichier."""
    def run():
        with open(st.SHIFTS_FILE, 'w', encoding='utf-8') as f:
            json.dump([
                {'call': 'F5ABC', 'start': '10:00', 'end': '12:00'},          # sans id
                {'id': 5, 'call': 'DL0XM', 'start': '12:00', 'end': '14:00'},
            ], f)
        st.load_shifts_from_disk()
        ids = [s['id'] for s in st.operator_shifts]
        assert len(ids) == len(set(ids)), 'ids dupliqués après rétro-compatibilité'
        assert all(isinstance(i, int) for i in ids)
        assert st.next_shift_id() not in ids
    _in_tmp(tmp_path, run)


def test_shifts_sorted_trie_par_heure_debut(tmp_path):
    def run():
        st.operator_shifts[:] = [
            {'id': 1, 'call': 'F5ABC', 'start': '14:00', 'end': '16:00'},
            {'id': 2, 'call': 'F6XYZ', 'start': '08:00', 'end': '10:00'},
            {'id': 3, 'call': 'F4GLD', 'start': '10:00', 'end': '12:00'},
        ]
        ordered = [s['id'] for s in st.shifts_sorted()]
        assert ordered == [2, 3, 1]
    _in_tmp(tmp_path, run)


def test_shifts_sorted_ne_mute_pas_la_liste_source(tmp_path):
    """shifts_sorted() renvoie une COPIE triée — la liste source (parcourue
    ailleurs sans verrou, ex. écran mural) ne doit jamais être réordonnée par
    effet de bord d'un simple GET /shifts/list."""
    def run():
        st.operator_shifts[:] = [
            {'id': 1, 'call': 'B', 'start': '14:00', 'end': '16:00'},
            {'id': 2, 'call': 'A', 'start': '08:00', 'end': '10:00'},
        ]
        st.shifts_sorted()
        assert [s['id'] for s in st.operator_shifts] == [1, 2]
    _in_tmp(tmp_path, run)


# ─── Endpoints HTTP (vrai serveur, port éphémère) ────────────────────────────

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod
import urllib.error
import urllib.request


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


@pytest.fixture(autouse=True)
def _isolate_shifts(monkeypatch):
    """Aucun test HTTP ne doit toucher operator_shifts.json ni laisser de
    créneau fuiter d'un test à l'autre (état global partagé du module)."""
    import logx_storage as storage
    monkeypatch.setattr(storage, 'save_shifts_to_disk', lambda: None)
    saved = list(storage.operator_shifts)
    saved_next_id = storage._shifts_next_id
    storage.operator_shifts[:] = []
    yield
    storage.operator_shifts[:] = saved
    storage._shifts_next_id = saved_next_id


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def _post(base, path, payload):
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json',
                 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def _cfg(**kw):
    base = {'usage_mode': 'contest', 'operators': [
        {'call': 'F4GLD', 'name': 'Olivier', 'modes': {'ssb': True, 'cw': True, 'digi': True}},
        {'call': 'F6XYZ', 'name': 'Jean', 'modes': {'ssb': True, 'cw': False, 'digi': True}},
    ]}
    base.update(kw)
    return base


def test_shifts_add_creneau_valide(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', _cfg())
    status, res = _post(server, '/shifts/add',
                         {'call': 'f4gld', 'start': '10:00', 'end': '12:00', 'note': 'pile-up EU'})
    assert status == 200 and res.get('ok')
    assert 'warning' not in res
    shift = res['shift']
    assert shift['call'] == 'F4GLD'   # normalisé en majuscules
    assert shift['name'] == 'Olivier'  # repris de la config, pas transmis par le client
    assert shift['note'] == 'pile-up EU'
    import logx_storage as storage
    assert len(storage.operator_shifts) == 1
    assert storage.operator_shifts[0]['id'] == shift['id']


def test_shifts_add_operateur_inconnu_rejete(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', _cfg())
    status, res = _post(server, '/shifts/add',
                         {'call': 'F1INCONNU', 'start': '10:00', 'end': '12:00'})
    assert status == 400
    assert res.get('ok') is False
    assert 'F1INCONNU' in res.get('error', '')
    import logx_storage as storage
    assert storage.operator_shifts == []   # rien n'a été ajouté


def test_shifts_add_champs_requis_manquants(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', _cfg())
    status, res = _post(server, '/shifts/add', {'call': 'F4GLD', 'start': '10:00'})  # end manquant
    assert status == 400 and res.get('ok') is False


def test_shifts_add_avertissement_qualification_manquante(server, monkeypatch):
    """F6XYZ n'est PAS qualifié CW (modes.cw=False) — la création doit quand
    même réussir (planning informatif, pas un verrou) mais renvoyer un
    'warning' explicite."""
    monkeypatch.setattr(httpmod, 'current_config', _cfg())
    status, res = _post(server, '/shifts/add',
                         {'call': 'F6XYZ', 'start': '10:00', 'end': '12:00', 'mode': 'cw'})
    assert status == 200 and res.get('ok')
    assert res.get('warning'), "un avertissement était attendu (opérateur non qualifié CW)"
    assert 'CW' in res['warning'] or 'cw' in res['warning'].lower()
    import logx_storage as storage
    assert len(storage.operator_shifts) == 1   # le créneau est bien créé malgré l'avertissement


def test_shifts_add_sans_avertissement_si_qualifie(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', _cfg())
    status, res = _post(server, '/shifts/add',
                         {'call': 'F6XYZ', 'start': '10:00', 'end': '12:00', 'mode': 'ssb'})
    assert status == 200 and res.get('ok')
    assert 'warning' not in res


def test_shifts_delete_retire_creneau(server, monkeypatch):
    import logx_storage as storage
    monkeypatch.setattr(httpmod, 'current_config', _cfg())
    storage.operator_shifts[:] = [
        {'id': 42, 'call': 'F4GLD', 'name': 'Olivier', 'start': '10:00', 'end': '12:00'},
    ]
    status, res = _post(server, '/shifts/delete/42', {})
    assert status == 200 and res.get('ok') and res.get('deleted') == 1
    assert storage.operator_shifts == []


def test_shifts_delete_id_absent_ne_supprime_rien(server, monkeypatch):
    import logx_storage as storage
    monkeypatch.setattr(httpmod, 'current_config', _cfg())
    storage.operator_shifts[:] = [
        {'id': 1, 'call': 'F4GLD', 'name': 'Olivier', 'start': '10:00', 'end': '12:00'},
    ]
    status, res = _post(server, '/shifts/delete/999', {})
    assert status == 200 and res.get('ok') and res.get('deleted') == 0
    assert len(storage.operator_shifts) == 1


def test_shifts_list_trie_par_heure_debut(server, monkeypatch):
    import logx_storage as storage
    monkeypatch.setattr(httpmod, 'current_config', _cfg())
    storage.operator_shifts[:] = [
        {'id': 1, 'call': 'F4GLD', 'start': '18:00', 'end': '20:00'},
        {'id': 2, 'call': 'F6XYZ', 'start': '06:00', 'end': '08:00'},
        {'id': 3, 'call': 'F4GLD', 'start': '12:00', 'end': '14:00'},
    ]
    res = _get(server, '/shifts/list')
    assert [s['id'] for s in res['shifts']] == [2, 3, 1]


def test_shifts_list_endpoint_reflete_lajout(server, monkeypatch):
    """Bout en bout complet : /shifts/add puis /shifts/list retrouve le
    créneau fraîchement créé, trié correctement parmi les autres."""
    monkeypatch.setattr(httpmod, 'current_config', _cfg())
    _post(server, '/shifts/add', {'call': 'F4GLD', 'start': '20:00', 'end': '22:00'})
    _post(server, '/shifts/add', {'call': 'F6XYZ', 'start': '06:00', 'end': '08:00'})
    res = _get(server, '/shifts/list')
    starts = [s['start'] for s in res['shifts']]
    assert starts == sorted(starts)
    assert len(res['shifts']) == 2
