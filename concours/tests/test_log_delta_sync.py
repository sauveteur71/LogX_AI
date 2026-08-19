# -*- coding: utf-8 -*-
"""Synchro différentielle de /log/list (?since=&boot=) : voir logx_storage
(stamp_qso_version, mark_qso_deleted, mark_hard_reset, SERVER_BOOT_ID) et
logx_http._valid_since. Avant ce correctif, /log/list ne connaissait que deux
réponses : 'unchanged' (rien n'a changé depuis ?v=) ou la retransmission
TOTALE du log — même pour un seul QSO ajouté à un log de 9000+ entrées."""
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

import logx_storage as storage
import logx_http as httpmod


def _qso(**kw):
    base = {'call': 'F5ABC', 'band': '14', 'mode': 'SSB',
            'date': '20260720', 'time': '10:00'}
    base.update(kw)
    return base


# ─── Briques pures (logx_storage) ────────────────────────────────────────────

def test_stamp_qso_version_marque_la_version_courante(monkeypatch):
    monkeypatch.setattr(storage, 'log_version', 41)
    q = {'id': 1}
    storage.stamp_qso_version(q)
    assert q['_v'] == 41


def test_mark_qso_deleted_ajoute_un_tombstone(monkeypatch):
    monkeypatch.setattr(storage, 'deleted_qsos', [])
    monkeypatch.setattr(storage, 'log_version', 7)
    storage.mark_qso_deleted(99)
    assert storage.deleted_qsos == [{'id': 99, 'v': 7}]


def test_mark_qso_deleted_borne_le_nombre_de_tombstones(monkeypatch):
    monkeypatch.setattr(storage, 'deleted_qsos', [])
    monkeypatch.setattr(storage, '_MAX_DELETED_TOMBSTONES', 3)
    for i in range(5):
        monkeypatch.setattr(storage, 'log_version', i)
        storage.mark_qso_deleted(i)
    assert len(storage.deleted_qsos) == 3
    assert [d['id'] for d in storage.deleted_qsos] == [2, 3, 4]


def test_mark_hard_reset_fige_la_version_courante(monkeypatch):
    monkeypatch.setattr(storage, 'log_version', 12)
    storage.mark_hard_reset()
    assert storage.hard_reset_version == 12


# ─── _valid_since (logx_http) ────────────────────────────────────────────────

def test_valid_since_absent_ou_non_numerique(monkeypatch):
    monkeypatch.setattr(storage, 'hard_reset_version', 0)
    monkeypatch.setattr(storage, 'SERVER_BOOT_ID', 'boot1')
    assert httpmod._valid_since('', 'boot1', 10) is None
    assert httpmod._valid_since('abc', 'boot1', 10) is None


def test_valid_since_dans_le_futur_invalide(monkeypatch):
    """since > version courante : impossible en fonctionnement normal (un
    redémarrage a dû remettre log_version à zéro entretemps) -> repli."""
    monkeypatch.setattr(storage, 'hard_reset_version', 0)
    monkeypatch.setattr(storage, 'SERVER_BOOT_ID', 'boot1')
    assert httpmod._valid_since('99', 'boot1', 10) is None


def test_valid_since_avant_un_hard_reset_invalide(monkeypatch):
    monkeypatch.setattr(storage, 'hard_reset_version', 50)
    monkeypatch.setattr(storage, 'SERVER_BOOT_ID', 'boot1')
    assert httpmod._valid_since('40', 'boot1', 60) is None
    assert httpmod._valid_since('50', 'boot1', 60) == 50


def test_valid_since_jeton_de_demarrage_absent_ou_different(monkeypatch):
    monkeypatch.setattr(storage, 'hard_reset_version', 0)
    monkeypatch.setattr(storage, 'SERVER_BOOT_ID', 'boot1')
    assert httpmod._valid_since('5', '', 10) is None
    assert httpmod._valid_since('5', 'autre-boot', 10) is None


def test_valid_since_cas_valide(monkeypatch):
    monkeypatch.setattr(storage, 'hard_reset_version', 0)
    monkeypatch.setattr(storage, 'SERVER_BOOT_ID', 'boot1')
    assert httpmod._valid_since('5', 'boot1', 10) == 5


# ─── /log/list de bout en bout (vrai serveur, voir test_http_scope_endpoints.py) ─

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


def _delete(base, path):
    req = urllib.request.Request(base + path, method='DELETE',
                                  headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def test_log_list_sans_since_inchange_par_rapport_a_avant(server, monkeypatch):
    """Compatibilité ascendante totale : un client qui n'envoie pas ?since=
    doit recevoir EXACTEMENT ce qu'il recevait avant cette fonctionnalité
    (même forme de réponse, pas de clé 'delta')."""
    qso = _qso(id=1)
    monkeypatch.setattr(httpmod, 'shared_log', [qso])
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'simple'})
    monkeypatch.setattr(storage, 'log_version', 3)
    data = _get(server, '/log/list')
    assert 'delta' not in data
    assert data['qsos'] == [qso]
    assert data['version'] == 3
    assert 'boot' in data   # champ additif : ignoré sans risque par un vieux client


def test_log_list_since_invalide_replie_sur_liste_complete(server, monkeypatch):
    qso = _qso(id=1)
    monkeypatch.setattr(httpmod, 'shared_log', [qso])
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'simple'})
    monkeypatch.setattr(storage, 'log_version', 3)
    monkeypatch.setattr(storage, 'hard_reset_version', 0)
    data = _get(server, '/log/list?since=3&boot=un-jeton-perime')
    assert 'delta' not in data
    assert data['qsos'] == [qso]


def test_log_list_since_valide_ne_renvoie_que_le_delta(server, monkeypatch):
    old = _qso(id=1, _v=1)
    new = _qso(id=2, call='F6XYZ', _v=2)
    monkeypatch.setattr(httpmod, 'shared_log', [old, new])
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'simple'})
    monkeypatch.setattr(storage, 'log_version', 2)
    monkeypatch.setattr(storage, 'hard_reset_version', 0)
    data = _get(server, f'/log/list?since=1&boot={storage.SERVER_BOOT_ID}')
    assert data['delta'] is True
    assert [q['id'] for q in data['qsos']] == [2]
    assert data['total'] == 2   # total = log complet, pas la taille du delta
    assert data['deleted'] == []


def test_log_list_since_reflete_les_suppressions(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'shared_log', [])
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'simple'})
    monkeypatch.setattr(storage, 'log_version', 5)
    monkeypatch.setattr(storage, 'hard_reset_version', 0)
    monkeypatch.setattr(storage, 'deleted_qsos', [{'id': 42, 'v': 4}])
    data = _get(server, f'/log/list?since=1&boot={storage.SERVER_BOOT_ID}')
    assert data['delta'] is True
    assert data['deleted'] == [42]


def test_log_list_bout_en_bout_ajout_puis_suppression(server, monkeypatch):
    """Scénario réel : sync complète -> ajout d'un QSO -> poll delta (ne
    contient QUE le nouveau QSO) -> suppression -> poll delta (l'id supprimé
    apparaît dans 'deleted', plus dans 'qsos')."""
    monkeypatch.setattr(httpmod, 'shared_log', [])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda effacement_autorise=False: None)
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'simple'})
    monkeypatch.setattr(storage, 'log_version', 0)
    monkeypatch.setattr(storage, 'hard_reset_version', 0)
    monkeypatch.setattr(storage, 'deleted_qsos', [])

    # 1er sync : pas de ?since= -> liste complète (vide ici)
    first = _get(server, '/log/list')
    assert first['qsos'] == []
    v0, boot = first['version'], first['boot']

    # Un QSO est ajouté (chemin partagé avec /log/add et le pont WSJT-X)
    ok, _info = httpmod.add_qso_to_log(_qso(call='F4ABC'))
    assert ok

    # Poll delta : uniquement le QSO neuf
    delta1 = _get(server, f'/log/list?since={v0}&boot={boot}')
    assert delta1['delta'] is True
    assert len(delta1['qsos']) == 1 and delta1['qsos'][0]['call'] == 'F4ABC'
    v1 = delta1['version']
    qso_id = delta1['qsos'][0]['id']

    # Ce QSO est supprimé (DELETE réel, comme le fait le client)
    _delete(server, f'/log/delete/{qso_id}')

    # Poll delta suivant : rien de neuf ajouté, mais l'id supprimé remonte
    delta2 = _get(server, f'/log/list?since={v1}&boot={boot}')
    assert delta2['delta'] is True
    assert delta2['qsos'] == []
    assert delta2['deleted'] == [qso_id]


def test_config_save_force_un_resync_complet_meme_avec_since_valide(server, monkeypatch):
    """/config/save change la portée concours visible SANS toucher un seul
    QSO (voir logx_storage.cfg_scope_id) : un ?since= antérieur ne doit pas
    renvoyer un delta vide (qui laisserait l'ancienne portée affichée), mais
    forcer un resync complet — voir mark_hard_reset() dans /config/save."""
    qso = _qso(id=1, contest='REF_QRP', date='20270101', _v=1)
    monkeypatch.setattr(httpmod, 'shared_log', [qso])
    monkeypatch.setattr(httpmod, 'save_json_atomic', lambda *a, **kw: None)
    # Portée initiale = un AUTRE concours : le QSO REF_QRP existe déjà dans
    # shared_log (importé/loggué plus tôt) mais reste invisible tant que ce
    # concours n'est pas celui sélectionné.
    monkeypatch.setattr(httpmod, 'current_config', {
        'usage_mode': 'contest', 'contest': 'AUTRE_CONCOURS',
        'contest_start_date': '2027-01-01'})
    monkeypatch.setattr(storage, 'log_version', 1)
    monkeypatch.setattr(storage, 'hard_reset_version', 0)

    before = _get(server, '/log/list')
    v0, boot = before['version'], before['boot']
    assert before['qsos'] == []   # portée AUTRE_CONCOURS#2027 -> QSO REF_QRP invisible

    status, _res = _post(server, '/config/save', {
        'usage_mode': 'contest', 'contest': 'REF_QRP',
        'contest_start_date': '2027-01-01'})
    assert status == 200

    after = _get(server, f'/log/list?since={v0}&boot={boot}')
    assert 'delta' not in after          # repli explicite sur liste complète
    assert after['qsos'] == [qso]        # portée REF_QRP#2027 -> QSO maintenant visible


# ─── Revue adversariale du commit 5bf7091 : fenêtre de course lecture/écriture ──

def test_add_qso_bump_et_stamp_sont_atomiques_avec_le_verrou(server, monkeypatch):
    """PROBLEME 1 : avant correctif, bump_log_version() et stamp_qso_version()
    s'exécutaient APRÈS avoir relâché log_lock (le seul with log_lock: du
    chemin d'ajout ne couvrait que shared_log.append). Un lecteur /log/list
    concurrent (ThreadingHTTPServer, propre with log_lock:) pouvait alors
    s'intercaler ENTRE le bump (version déjà incrémentée) et le stamp (encore
    absent) : il capturait un QSO déjà dans shared_log mais sans son '_v' à
    jour (défaut 0), exclu à tort d'un delta calculé contre une version déjà
    avancée -> ce QSO devenait invisible À JAMAIS pour ce pair (il adopte ce
    curseur de version, qui ne redescend jamais).

    On force le pire agencement possible : un thread lecteur prêt à dégainer
    sa capture pile au moment où bump_log_version() vient de s'exécuter. Avec
    le correctif (bump+stamp DANS le même with log_lock: que l'append), ce
    lecteur reste bloqué sur l'acquisition du verrou jusqu'à la fin complète
    de l'écriture : il ne peut plus jamais observer une version bumpée sans le
    QSO correspondant déjà stampé dans le delta. Sans le correctif, ce test
    échoue (vérifié en local en repassant temporairement sur le code d'avant :
    delta renvoyé vide alors que la version a déjà avancé)."""
    monkeypatch.setattr(httpmod, 'shared_log', [])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda effacement_autorise=False: None)
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'simple'})
    monkeypatch.setattr(storage, 'log_version', 0)
    monkeypatch.setattr(storage, 'hard_reset_version', 0)
    monkeypatch.setattr(storage, 'deleted_qsos', [])

    reader_may_run = threading.Event()
    reader_done = threading.Event()
    reader_result = {}

    real_bump = storage.bump_log_version

    def bump_puis_signale_le_lecteur():
        v = real_bump()
        # Le lecteur tente sa capture PILE APRÈS le bump. Avec le correctif,
        # log_lock est encore tenu à cet instant (bump appelé DANS le même
        # with log_lock: que l'append) : le lecteur bloque sur l'acquisition
        # et ne peut plus s'intercaler. Sans le correctif, log_lock était déjà
        # relâché ici -> le lecteur passait librement.
        reader_may_run.set()
        reader_done.wait(timeout=0.4)
        return v

    monkeypatch.setattr(httpmod, 'bump_log_version', bump_puis_signale_le_lecteur)

    def lecteur():
        reader_may_run.wait(timeout=2)
        data = _get(server, f'/log/list?since=0&boot={storage.SERVER_BOOT_ID}')
        reader_result.update(data)
        reader_done.set()

    t = threading.Thread(target=lecteur)
    t.start()
    ok, _info = httpmod.add_qso_to_log(_qso(call='F4XYZ'))
    t.join(timeout=5)

    assert ok
    assert reader_result, "le thread lecteur n'a pas obtenu de réponse"
    if reader_result.get('version', 0) > 0:
        # Invariant : version déjà bumpée => le QSO neuf DOIT être dans le
        # delta (jamais l'un sans l'autre, sous peine d'invisibilité définitive).
        assert reader_result.get('delta') is True
        assert len(reader_result.get('qsos', [])) == 1, (
            "QSO invisible : le lecteur a vu la version déjà incrémentée "
            "mais le QSO neuf absent du delta (fenêtre de course rouverte)")


@pytest.fixture
def threaded_server():
    """ThreadingHTTPServer — le serveur de PRODUCTION (logx_serveur.py), un
    thread par requête. Indispensable pour une course entre deux REQUÊTES
    HTTP : avec le HTTPServer mono-thread de la fixture `server`, le GET
    concurrent est sérialisé derrière le POST et la course est masquée
    (le test passerait même sans le correctif)."""
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


def test_import_adif_commit_bump_et_stamp_sont_atomiques_avec_le_verrou(
        threaded_server, monkeypatch):
    """Même course que test_add_qso_bump_et_stamp_sont_atomiques_avec_le_verrou
    (PROBLEME 1), mais sur le chemin d'IMPORT ADIF : /log/import_adif/commit
    faisait `with log_lock: shared_log.extend(...)` puis bump_log_version() et
    la boucle stamp_qso_version() APRÈS avoir relâché le verrou — le motif
    d'avant correctif que /log/add, /log/update et /log/delete ont déjà
    abandonné. Un lecteur /log/list?since= concurrent pouvait s'intercaler
    entre le bump et le stamp : il capturait les QSO importés sans '_v'
    (défaut 0), les excluait du delta calculé contre une version déjà
    avancée, et adoptait ce curseur — les QSO stampés ensuite avec _v égal
    (jamais strictement supérieur) au curseur restaient invisibles À JAMAIS
    pour ce pair. Fenêtre d'autant plus large que l'import est gros (le
    stamp boucle sur tout l'import). Sans le correctif (bump+stamp DANS le
    même with log_lock: que l'extend), ce test échoue : delta vide alors que
    la version a déjà avancé."""
    monkeypatch.setattr(httpmod, 'shared_log', [])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda effacement_autorise=False: None)
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'simple'})
    monkeypatch.setattr(storage, 'log_version', 0)
    monkeypatch.setattr(storage, 'hard_reset_version', 0)
    monkeypatch.setattr(storage, 'deleted_qsos', [])

    reader_may_run = threading.Event()
    reader_done = threading.Event()
    reader_result = {}

    real_bump = storage.bump_log_version

    def bump_puis_signale_le_lecteur():
        v = real_bump()
        # Le lecteur dégaine PILE APRÈS le bump. Avec le correctif, log_lock
        # est encore tenu ici (bump appelé DANS le même with log_lock: que
        # l'extend) : le lecteur bloque jusqu'à la fin des stamps. Sans le
        # correctif, le verrou était déjà relâché -> il passait librement.
        reader_may_run.set()
        reader_done.wait(timeout=0.4)
        return v

    monkeypatch.setattr(httpmod, 'bump_log_version', bump_puis_signale_le_lecteur)

    def lecteur():
        reader_may_run.wait(timeout=5)
        data = _get(threaded_server,
                    f'/log/list?since=0&boot={storage.SERVER_BOOT_ID}')
        reader_result.update(data)
        reader_done.set()

    t = threading.Thread(target=lecteur)
    t.start()
    adif = ("<CALL:5>F4XYZ<BAND:3>20m<MODE:3>SSB"
            "<QSO_DATE:8>20260720<TIME_ON:4>1000<EOR>")
    status, res = _post(threaded_server, '/log/import_adif/commit',
                        {'adif': adif})
    t.join(timeout=5)

    assert status == 200 and res.get('imported') == 1
    assert reader_result, "le thread lecteur n'a pas obtenu de réponse"
    if reader_result.get('version', 0) > 0:
        # Invariant : version déjà bumpée => le QSO importé DOIT être dans le
        # delta (jamais l'un sans l'autre, sous peine d'invisibilité définitive).
        assert reader_result.get('delta') is True
        assert len(reader_result.get('qsos', [])) == 1, (
            "QSO importé invisible : le lecteur a vu la version déjà "
            "incrémentée mais le QSO absent du delta (fenêtre de course "
            "de /log/import_adif/commit rouverte)")


def test_log_update_changement_de_portee_force_un_resync_complet(server, monkeypatch):
    """PROBLEME 2 : qso_scope_id() dérive la portée d'un QSO de 'contest' +
    l'année de son champ 'date'. /log/update laisse modifier cette date (donc
    la portée) mais n'appelait jamais mark_hard_reset() — contrairement à
    /config/save qui le fait pour le même genre d'événement (portée qui change
    sans qu'aucun QSO ne soit ajouté/supprimé). Reproduction : QSO id=42 dans
    la portée active REF_QRP#2026, déjà vu par un pair (?since= valide) ; sa
    date est corrigée vers 2027 (portée REF_QRP#2027, qui n'est plus la portée
    active) -> sans le correctif, ce QSO ne réapparaît ni dans un delta (le
    filtre de portée l'exclut de log_copy AVANT même la comparaison de
    version) ni dans les tombstones (ce n'est pas une suppression) : le pair
    continue de l'afficher indéfiniment. Avec le correctif, le changement de
    portée force un resync complet (repli explicite, pas de 'delta')."""
    qso = _qso(id=42, contest='REF_QRP', date='20260101', _v=1)
    monkeypatch.setattr(httpmod, 'shared_log', [qso])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda effacement_autorise=False: None)
    # Portée active = REF_QRP#2026 (édition en cours) : le QSO y est visible.
    monkeypatch.setattr(httpmod, 'current_config', {
        'usage_mode': 'contest', 'contest': 'REF_QRP',
        'contest_start_date': '2026-01-01'})
    monkeypatch.setattr(storage, 'log_version', 1)
    monkeypatch.setattr(storage, 'hard_reset_version', 0)
    monkeypatch.setattr(storage, 'deleted_qsos', [])

    before = _get(server, '/log/list')
    v0, boot = before['version'], before['boot']
    assert before['qsos'] == [qso]   # portée REF_QRP#2026 -> visible

    # Correction de la date : le QSO passe à l'édition 2027 (portée différente)
    updated = dict(qso, date='20270101')
    status, _res = _post(server, '/log/update', updated)
    assert status == 200

    after = _get(server, f'/log/list?since={v0}&boot={boot}')
    # Le QSO n'est plus dans la portée active (REF_QRP#2026) : sans le
    # correctif, il resterait absent en silence d'un delta vide qui laisse le
    # cache du pair inchangé -> il faut un repli explicite sur liste complète.
    assert 'delta' not in after
    assert after['qsos'] == []
