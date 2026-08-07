# -*- coding: utf-8 -*-
"""Synchronisation MySQL partagée (logx_mysql_sync) — 4e mécanisme
multi-poste (radio-club ou 2 postes d'un même radioamateur), même famille que
Cloud Sync (logx_cloudsync.py). pymysql n'est PAS installé dans
l'environnement de test (dépendance optionnelle, voir HAS_PYMYSQL) : toute la
couche réseau est doublée par un faux connecteur (FakeConnection/FakeCursor)
qui n'ouvre JAMAIS de vrai socket — voir _isole(monkeypatch) ci-dessous."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_mysql_sync as mysql


# ─── Faux connecteur MySQL (jamais de vrai socket) ───────────────────────────

class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.conn.calls.append((sql, params))
        up = sql.upper()
        # raise_on_schema : simule un CREATE TABLE qui échoue (droits
        # insuffisants) — voir test_ensure_schema_echoue_ferme_la_connexion.
        if 'CREATE TABLE' in up and self.conn.raise_on_schema is not None:
            raise self.conn.raise_on_schema
        # raise_on_execute_at : simule un execute() qui échoue EN COURS de
        # synchro (pas à la connexion/au schéma) — le Nème appel à execute()
        # sur cette connexion lève, quel que soit son SQL.
        if (self.conn.raise_on_execute_at is not None
                and len(self.conn.calls) == self.conn.raise_on_execute_at):
            raise self.conn.raise_on_execute_exc
        if 'SELECT ID, DATA' in up:
            self._result = self.conn.select_result
        elif 'SELECT COUNT' in up:
            self._result = [(len(self.conn.select_result),)]
        else:
            self._result = None

    def fetchall(self):
        return self._result or []

    def fetchone(self):
        r = self._result
        return r[0] if r else None


class FakeConnection:
    def __init__(self, select_result=None, raise_on_connect=None,
                 raise_on_schema=None, raise_on_execute_at=None,
                 raise_on_execute_exc=None):
        self.calls = []
        self.closed = False
        self.select_result = select_result or []
        self.raise_on_schema = raise_on_schema
        self.raise_on_execute_at = raise_on_execute_at
        self.raise_on_execute_exc = raise_on_execute_exc or RuntimeError('execute a échoué')

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


def _isole(monkeypatch, tmp_path):
    """Redirige les fichiers d'état vers un dossier temporaire — même réflexe
    que pour logx_telemetry.py (voir la mémoire de session sur la fuite de
    fichiers de test), et force HAS_PYMYSQL=True pour que le code de
    connexion s'exécute (sinon _connect() lève avant même d'atteindre le faux
    connecteur)."""
    monkeypatch.setattr(mysql, '_STAMP_FILE', str(tmp_path / 'mysql_sync_state.json'))
    monkeypatch.setattr(mysql, 'HAS_PYMYSQL', True)


def _cfg(**kw):
    base = {'mysql_mode': 'full', 'mysql_host': 'db.local', 'mysql_database': 'logxclub'}
    base.update(kw)
    return base


# ─── mysql_settings() ─────────────────────────────────────────────────────────

def test_mysql_settings_desactive_par_defaut():
    assert mysql.mysql_settings({})['enabled'] is False


def test_mysql_settings_mode_invalide_retombe_sur_off():
    s = mysql.mysql_settings({'mysql_mode': 'n\'importe quoi', 'mysql_host': 'h', 'mysql_database': 'd'})
    assert s['mode'] == 'off' and s['enabled'] is False


def test_mysql_settings_active_si_mode_host_et_database():
    s = mysql.mysql_settings(_cfg())
    assert s['enabled'] is True
    assert s['host'] == 'db.local' and s['database'] == 'logxclub'


def test_mysql_settings_desactive_si_host_manquant():
    assert mysql.mysql_settings({'mysql_mode': 'full', 'mysql_database': 'd'})['enabled'] is False


def test_mysql_settings_port_par_defaut():
    assert mysql.mysql_settings(_cfg())['port'] == mysql.DEFAULT_PORT


def test_mysql_settings_port_invalide_retombe_sur_defaut():
    assert mysql.mysql_settings(_cfg(mysql_port='abc'))['port'] == mysql.DEFAULT_PORT


# ─── _connect() / test_connection() sans pymysql installé ────────────────────

def test_connect_leve_sans_pymysql(monkeypatch):
    monkeypatch.setattr(mysql, 'HAS_PYMYSQL', False)
    try:
        mysql._connect(mysql.mysql_settings(_cfg()))
        assert False, "devait lever"
    except RuntimeError as e:
        assert 'pymysql' in str(e)


def test_test_connection_sans_pymysql_installe(monkeypatch):
    monkeypatch.setattr(mysql, 'HAS_PYMYSQL', False)
    r = mysql.test_connection('db.local', 3306, 'u', 'p', 'logxclub')
    assert r['ok'] is False and 'pymysql' in r['error']


def test_test_connection_hote_manquant():
    r = mysql.test_connection('', 3306, 'u', 'p', 'logxclub')
    assert r['ok'] is False


def test_test_connection_ok(monkeypatch):
    monkeypatch.setattr(mysql, 'HAS_PYMYSQL', True)
    fake_conn = FakeConnection()
    fake_pymysql = type('FakePymysql', (), {'connect': staticmethod(lambda **kw: fake_conn)})
    monkeypatch.setattr(mysql, '_pymysql_mod', fake_pymysql)
    r = mysql.test_connection('db.local', 3306, 'u', 'p', 'logxclub')
    assert r['ok'] is True and r['qso_count'] == 0
    assert fake_conn.closed is True


# ─── sync_now() : dispatch/désactivé ──────────────────────────────────────────

def test_sync_now_desactive_ne_se_connecte_jamais(monkeypatch, tmp_path):
    _isole(monkeypatch, tmp_path)
    monkeypatch.setattr(mysql, '_connect', lambda s: (_ for _ in ()).throw(
        AssertionError('ne doit jamais se connecter')))
    r = mysql.sync_now({}, [])
    assert r['ok'] is False


def test_sync_now_connexion_impossible(monkeypatch, tmp_path):
    _isole(monkeypatch, tmp_path)
    monkeypatch.setattr(mysql, '_connect', lambda s: (_ for _ in ()).throw(OSError('injoignable')))
    r = mysql.sync_now(_cfg(), [])
    assert r['ok'] is False and 'injoignable' in r['error']


# ─── PUSH ──────────────────────────────────────────────────────────────────────

def test_push_insere_chaque_qso_local_avec_id(monkeypatch, tmp_path):
    _isole(monkeypatch, tmp_path)
    fake_conn = FakeConnection()
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)
    log = [{'id': 1001, 'call': 'F4GLD'}, {'id': 1002, 'call': 'DL1AA'}]
    r = mysql.sync_now(_cfg(mysql_mode='push'), log)
    assert r['ok'] is True and r['pushed'] == 2
    inserts = [c for c in fake_conn.calls if 'INSERT INTO' in c[0].upper()]
    assert len(inserts) == 2
    assert inserts[0][1][0] == 1001


def test_push_ignore_qso_sans_id(monkeypatch, tmp_path):
    _isole(monkeypatch, tmp_path)
    fake_conn = FakeConnection()
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)
    log = [{'call': 'F4GLD'}]   # pas d'id
    r = mysql.sync_now(_cfg(mysql_mode='push'), log)
    assert r['ok'] is True and r['pushed'] == 0


def test_push_mode_ne_pull_jamais(monkeypatch, tmp_path):
    """mode='push' : aucun SELECT, jamais d'appel à add_qso_to_log."""
    _isole(monkeypatch, tmp_path)
    fake_conn = FakeConnection(select_result=[(9999, json.dumps({'id': 9999, 'call': 'X'}), 1.0, None)])
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)
    r = mysql.sync_now(_cfg(mysql_mode='push'), [])
    assert r['ok'] is True and r['pulled'] == 0
    assert not any('SELECT ID, DATA' in c[0].upper() for c in fake_conn.calls)


def test_push_propage_les_suppressions_locales(monkeypatch, tmp_path):
    _isole(monkeypatch, tmp_path)
    import logx_storage as storage
    fake_conn = FakeConnection()
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)
    monkeypatch.setattr(storage, 'deleted_qsos', [{'id': 555, 'v': 1}])
    mysql.sync_now(_cfg(mysql_mode='push'), [])
    updates = [c for c in fake_conn.calls if c[0].strip().upper().startswith('UPDATE ')]
    assert len(updates) == 1
    assert updates[0][1][1] == 555


# ─── PULL (mode='full') ────────────────────────────────────────────────────────

def test_pull_ajoute_un_qso_distant_nouveau(monkeypatch, tmp_path):
    _isole(monkeypatch, tmp_path)
    remote_qso = {'id': 2001, 'call': 'DL1AA', 'band': '20m', 'mode': 'SSB',
                  'date': '20260806', 'time': '12:00'}
    fake_conn = FakeConnection(select_result=[(2001, json.dumps(remote_qso), 100.0, None)])
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)

    import logx_http as http
    monkeypatch.setattr(http, 'shared_log', [])
    added = []
    monkeypatch.setattr(http, 'add_qso_to_log',
                        lambda q, force=False: (added.append(q) or (True, {})))

    r = mysql.sync_now(_cfg(), [])
    assert r['ok'] is True and r['pulled'] == 1
    assert added and added[0]['id'] == 2001


def test_pull_ignore_id_deja_present_localement(monkeypatch, tmp_path):
    _isole(monkeypatch, tmp_path)
    remote_qso = {'id': 3001, 'call': 'DL1AA', 'band': '20m', 'mode': 'SSB',
                  'date': '20260806', 'time': '12:00'}
    fake_conn = FakeConnection(select_result=[(3001, json.dumps(remote_qso), 100.0, None)])
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)

    import logx_http as http
    monkeypatch.setattr(http, 'shared_log', [dict(remote_qso)])   # déjà présent (même id)
    monkeypatch.setattr(http, 'add_qso_to_log',
                        lambda q, force=False: (_ for _ in ()).throw(
                            AssertionError('ne doit jamais être appelé')))

    r = mysql.sync_now(_cfg(), [dict(remote_qso)])
    assert r['ok'] is True and r['pulled'] == 0


def test_pull_ignore_meme_cle_avec_id_different(monkeypatch, tmp_path):
    """Même dédup que logx_cloudsync : call+band+mode+date+heure identiques
    mais id différent -> ancienne version d'un QSO corrigé ici, jamais
    ré-importée en doublon."""
    _isole(monkeypatch, tmp_path)
    local_qso = {'id': 4001, 'call': 'DL1AA', 'band': '20m', 'mode': 'SSB',
                'date': '20260806', 'time': '12:00'}
    remote_qso = dict(local_qso, id=4002)   # même clé, id différent
    fake_conn = FakeConnection(select_result=[(4002, json.dumps(remote_qso), 100.0, None)])
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)

    import logx_http as http
    monkeypatch.setattr(http, 'shared_log', [dict(local_qso)])
    monkeypatch.setattr(http, 'add_qso_to_log',
                        lambda q, force=False: (_ for _ in ()).throw(
                            AssertionError('ne doit jamais être appelé')))

    r = mysql.sync_now(_cfg(), [dict(local_qso)])
    assert r['ok'] is True and r['pulled'] == 0


def test_pull_supprime_localement_un_qso_marque_supprime_a_distance(monkeypatch, tmp_path):
    _isole(monkeypatch, tmp_path)
    local_qso = {'id': 5001, 'call': 'DL1AA', 'band': '20m', 'mode': 'SSB',
                'date': '20260806', 'time': '12:00'}
    fake_conn = FakeConnection(select_result=[(5001, json.dumps(local_qso), 50.0, 100.0)])
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)

    import logx_http as http
    import logx_storage as storage
    monkeypatch.setattr(http, 'shared_log', [dict(local_qso)])
    monkeypatch.setattr(http, 'save_log_to_disk', lambda: None)
    marked = []
    monkeypatch.setattr(storage, 'mark_qso_deleted', lambda qid: marked.append(qid))
    monkeypatch.setattr(storage, 'bump_log_version', lambda: None)

    r = mysql.sync_now(_cfg(), [dict(local_qso)])
    assert r['ok'] is True and r['removed'] == 1
    assert marked == [5001]
    assert http.shared_log == []


def test_pull_avance_le_stamp_meme_sans_nouveau_qso(monkeypatch, tmp_path):
    """Le curseur de dernier pull doit avancer même si tous les QSO renvoyés
    étaient déjà connus — sinon la même page de résultats reviendrait à
    chaque cycle indéfiniment."""
    _isole(monkeypatch, tmp_path)
    remote_qso = {'id': 6001, 'call': 'DL1AA', 'band': '20m', 'mode': 'SSB',
                  'date': '20260806', 'time': '12:00'}
    fake_conn = FakeConnection(select_result=[(6001, json.dumps(remote_qso), 200.0, None)])
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)

    import logx_http as http
    monkeypatch.setattr(http, 'shared_log', [dict(remote_qso)])   # déjà présent
    monkeypatch.setattr(http, 'add_qso_to_log', lambda q, force=False: (True, {}))

    mysql.sync_now(_cfg(), [dict(remote_qso)])
    key = f"{'db.local'}:{mysql.DEFAULT_PORT}/logxclub"
    stamp = mysql._load_stamp()
    assert stamp.get(key) == 200.0


def test_pull_ignore_suppression_distante_avec_meme_id_mais_cle_differente(monkeypatch, tmp_path):
    """Correctif revue adversariale (bug critique) : l'id du QSO est
    Date.now() côté client SANS coordination inter-poste (voir
    logx_storage.reserve_qso_id_locked, unicité locale seulement) — deux
    postes différents peuvent produire le même id à la même milliseconde pour
    deux QSO totalement différents. Une ligne 'deleted_at' distante dont
    l'id correspond à un QSO local mais dont la CLÉ (call+band+mode+date+
    heure) diffère ne doit JAMAIS supprimer ce QSO local : ce n'est pas le
    même QSO, juste une collision d'id."""
    _isole(monkeypatch, tmp_path)
    local_qso = {'id': 5555, 'call': 'F4GLD', 'band': '40m', 'mode': 'CW',
                'date': '20260807', 'time': '08:00'}
    # Même id que le QSO local, mais QSO complètement différent (collision).
    remote_deleted_qso = {'id': 5555, 'call': 'DL9ZZ', 'band': '15m', 'mode': 'SSB',
                          'date': '20260101', 'time': '23:59'}
    fake_conn = FakeConnection(select_result=[(5555, json.dumps(remote_deleted_qso), 50.0, 100.0)])
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)

    import logx_http as http
    monkeypatch.setattr(http, 'shared_log', [dict(local_qso)])
    monkeypatch.setattr(http, 'save_log_to_disk', lambda: None)

    r = mysql.sync_now(_cfg(), [dict(local_qso)])
    assert r['ok'] is True and r['removed'] == 0
    assert http.shared_log == [local_qso]


def test_ensure_schema_echoue_ferme_la_connexion(monkeypatch, tmp_path):
    """Droits MySQL insuffisants pour CREATE TABLE IF NOT EXISTS : sync_now()
    doit renvoyer une erreur exploitable ET la connexion doit être refermée
    (le finally: conn.close() doit s'exécuter même si _ensure_schema lève)."""
    _isole(monkeypatch, tmp_path)
    fake_conn = FakeConnection(raise_on_schema=RuntimeError('droits insuffisants'))
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)
    r = mysql.sync_now(_cfg(mysql_mode='push'), [])
    assert r['ok'] is False and 'droits insuffisants' in r['error']
    assert fake_conn.closed is True


def test_pull_lot_avec_une_ligne_json_corrompue_les_autres_appliquees(monkeypatch, tmp_path):
    """Un lot de plusieurs lignes où UNE SEULE a une colonne data JSON
    corrompue ne doit ni planter la synchro ni bloquer les autres lignes,
    valides, du même lot."""
    _isole(monkeypatch, tmp_path)
    good_qso = {'id': 7001, 'call': 'DL1AA', 'band': '20m', 'mode': 'SSB',
                'date': '20260806', 'time': '12:00'}
    rows = [
        (7001, json.dumps(good_qso), 100.0, None),
        (7002, '{ceci n est pas du json valide', 100.0, None),   # corrompue
    ]
    fake_conn = FakeConnection(select_result=rows)
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)

    import logx_http as http
    monkeypatch.setattr(http, 'shared_log', [])
    added = []
    monkeypatch.setattr(http, 'add_qso_to_log',
                        lambda q, force=False: (added.append(q) or (True, {})))

    r = mysql.sync_now(_cfg(), [])
    assert r['ok'] is True and r['pulled'] == 1
    assert added and added[0]['id'] == 7001


def test_execute_echoue_en_cours_de_synchro_ferme_la_connexion(monkeypatch, tmp_path):
    """execute() qui échoue APRÈS la connexion et APRÈS le CREATE TABLE (donc
    pendant le push lui-même) : chemin différent de l'échec de connexion déjà
    testé (test_sync_now_connexion_impossible) — la connexion doit quand même
    être refermée par le finally."""
    _isole(monkeypatch, tmp_path)
    # 1er execute() = CREATE TABLE (_ensure_schema), 2e = le premier INSERT du
    # push : c'est celui-là qui échoue, une fois la synchro déjà en cours.
    fake_conn = FakeConnection(raise_on_execute_at=2)
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)
    log = [{'id': 8001, 'call': 'F4GLD'}]
    r = mysql.sync_now(_cfg(mysql_mode='push'), log)
    assert r['ok'] is False
    assert fake_conn.closed is True


def test_pull_lot_mixte_suppression_et_ajout_meme_cycle(monkeypatch, tmp_path):
    """Un même lot contient une ligne supprimée (deleted_at renseigné) ET une
    ligne ajoutée (deleted_at NULL) : l'ordre de traitement (suppressions
    d'abord, recalcul de local_ids/seen APRÈS la purge) doit rester correct
    dans les deux sens."""
    _isole(monkeypatch, tmp_path)
    local_qso = {'id': 9001, 'call': 'F4GLD', 'band': '40m', 'mode': 'CW',
                'date': '20260807', 'time': '08:00'}
    new_qso = {'id': 9002, 'call': 'DL1AA', 'band': '20m', 'mode': 'SSB',
              'date': '20260806', 'time': '12:00'}
    rows = [
        (9001, json.dumps(local_qso), 50.0, 100.0),   # suppression distante
        (9002, json.dumps(new_qso), 150.0, None),     # ajout distant
    ]
    fake_conn = FakeConnection(select_result=rows)
    monkeypatch.setattr(mysql, '_connect', lambda s: fake_conn)

    import logx_http as http
    import logx_storage as storage
    monkeypatch.setattr(http, 'shared_log', [dict(local_qso)])
    monkeypatch.setattr(http, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(storage, 'mark_qso_deleted', lambda qid: None)
    monkeypatch.setattr(storage, 'bump_log_version', lambda: None)
    added = []
    monkeypatch.setattr(http, 'add_qso_to_log',
                        lambda q, force=False: (added.append(q) or (True, {})))

    r = mysql.sync_now(_cfg(), [dict(local_qso)])
    assert r['ok'] is True and r['removed'] == 1 and r['pulled'] == 1
    assert added and added[0]['id'] == 9002
    assert http.shared_log == []   # le QSO supprimé a bien disparu, le nouveau a été ajouté via add_qso_to_log (mock)


# ─── status() ──────────────────────────────────────────────────────────────────

def test_status_sans_synchro_prealable(monkeypatch, tmp_path):
    _isole(monkeypatch, tmp_path)
    s = mysql.status({})
    assert s['enabled'] is False and s['last'] == {}


def test_status_expose_has_pymysql(monkeypatch, tmp_path):
    _isole(monkeypatch, tmp_path)
    assert mysql.status({})['has_pymysql'] is True
    monkeypatch.setattr(mysql, 'HAS_PYMYSQL', False)
    assert mysql.status({})['has_pymysql'] is False


# ─── Câblage HTTP /mysql/test et /mysql/now ───────────────────────────────────

import http.server
import threading
import urllib.error
import urllib.request

import pytest

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


def _post(base, path, payload):
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json', 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_http_mysql_test_route_correctement(server, monkeypatch):
    monkeypatch.setattr(mysql, 'test_connection',
                        lambda host, port, user, password, database: {'ok': True, 'qso_count': 3})
    status, d = _post(server, '/mysql/test', {'host': 'db.local', 'port': 3306,
                                              'user': 'u', 'password': 'p', 'database': 'logxclub'})
    assert status == 200 and d == {'ok': True, 'qso_count': 3}


def test_http_mysql_test_echec_renvoie_400(server, monkeypatch):
    monkeypatch.setattr(mysql, 'test_connection',
                        lambda host, port, user, password, database: {'ok': False, 'error': 'boom'})
    status, d = _post(server, '/mysql/test', {'host': 'db.local'})
    assert status == 400 and d['ok'] is False


def test_http_mysql_now_utilise_les_valeurs_saisies_pas_celles_sauvegardees(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {'mysql_mode': 'off', 'mysql_host': 'ancien'})
    captured = {}
    monkeypatch.setattr(mysql, 'sync_now',
                        lambda cfg, log: captured.update(cfg) or {'ok': True, 'mode': 'full',
                                                                   'pushed': 0, 'pulled': 0, 'removed': 0})
    status, d = _post(server, '/mysql/now', {'mysql_mode': 'full', 'mysql_host': 'nouveau'})
    assert status == 200 and d['ok'] is True
    assert captured['mysql_host'] == 'nouveau' and captured['mysql_mode'] == 'full'


def test_http_network_status_contient_mysql_sync(server, monkeypatch):
    monkeypatch.setattr(mysql, 'status', lambda cfg: {'enabled': False})
    with urllib.request.urlopen(server + '/data/network_status', timeout=5) as r:
        d = json.loads(r.read().decode('utf-8'))
    assert 'mysql_sync' in d


def _post_sans_jeton(base, path, payload):
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(base + path, data=body, method='POST',
                                 headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=5)


def test_http_mysql_now_sans_jeton_refuse(server, monkeypatch):
    """Comme toutes les autres routes POST (hors /auth/login) : jeton exigé
    — voir _require_auth() dans logx_http.py, même patron que
    test_cat_detection_http.py::test_dismiss_detection_sans_token_refuse et
    test_serial_allocation.py::test_endpoint_sans_jeton_refuse_403_et_ne_consomme_rien.
    Rien ne doit être consommé côté synchro si la requête est rejetée avant
    d'atteindre le handler (le rejet a lieu en tout début de do_POST, avant
    même le dispatch sur /mysql/now)."""
    called = []
    monkeypatch.setattr(mysql, 'sync_now',
                        lambda cfg, log: called.append(1) or {'ok': True, 'mode': 'full',
                                                               'pushed': 0, 'pulled': 0, 'removed': 0})
    try:
        _post_sans_jeton(server, '/mysql/now', {'mysql_mode': 'full'})
        assert False, "la requête sans jeton aurait dû être rejetée"
    except urllib.error.HTTPError as e:
        assert e.code in (401, 403)
    assert called == []


def test_http_mysql_test_sans_jeton_refuse(server, monkeypatch):
    """Même exigence que /mysql/now ci-dessus, pour le bouton « Tester la
    connexion » (CONFIG) — ne doit jamais déclencher de vraie connexion
    MySQL sans jeton de session valide."""
    called = []
    monkeypatch.setattr(mysql, 'test_connection',
                        lambda host, port, user, password, database: called.append(1) or {'ok': True})
    try:
        _post_sans_jeton(server, '/mysql/test', {'host': 'db.local', 'database': 'logxclub'})
        assert False, "la requête sans jeton aurait dû être rejetée"
    except urllib.error.HTTPError as e:
        assert e.code in (401, 403)
    assert called == []
