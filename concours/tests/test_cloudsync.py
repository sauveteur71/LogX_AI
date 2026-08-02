# -*- coding: utf-8 -*-
"""Tests de Cloud Sync (logx_cloudsync) : synchronisation multi-poste
via un dossier déjà synchronisé (Synology Drive/Dropbox/OneDrive), sans
service hébergé. Conception anti-collision testée explicitement : chaque
poste n'écrit JAMAIS que son propre fichier."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_cloudsync as cs

QSO_A = {'id': 1001, 'call': 'DL1AA', 'band': '14', 'mode': 'SSB', 'server_time': 100}
QSO_B = {'id': 1002, 'call': 'G3XYZ', 'band': '14', 'mode': 'CW', 'server_time': 200}


def test_settings_desactive_par_defaut():
    s = cs.cloudsync_settings({})
    assert s['enabled'] is False and s['mode'] == 'off'


def test_settings_mode_invalide_retombe_sur_off():
    s = cs.cloudsync_settings({'cloudsync_mode': 'n_importe_quoi', 'cloudsync_folder': '/tmp/x'})
    assert s['mode'] == 'off' and s['enabled'] is False


def test_settings_replie_sur_backup_folder_si_pas_de_dossier_dedie():
    s = cs.cloudsync_settings({'cloudsync_mode': 'push', 'backup_folder': '/tmp/backup'})
    assert s['folder'] == '/tmp/backup' and s['enabled'] is True


def test_settings_dossier_dedie_prioritaire_sur_backup_folder():
    s = cs.cloudsync_settings({'cloudsync_mode': 'push', 'cloudsync_folder': '/tmp/sync',
                               'backup_folder': '/tmp/backup'})
    assert s['folder'] == '/tmp/sync'


def test_nom_de_fichier_inclut_indicatif_et_id_installation():
    s = cs.cloudsync_settings({'cloudsync_mode': 'push', 'cloudsync_folder': '/tmp/x',
                              'callsign_contest': 'F4GLD'})
    assert s['my_file'].startswith('logx_cloudsync_F4GLD_')
    assert s['my_file'].endswith('.json')


def test_sync_now_desactive():
    r = cs.sync_now({}, [])
    assert not r['ok'] and 'désactivé' in r['error'].lower()


def test_sync_now_dossier_inaccessible(monkeypatch):
    monkeypatch.setattr(cs.os, 'makedirs', lambda *a, **k: (_ for _ in ()).throw(OSError('refusé')))
    r = cs.sync_now({'cloudsync_mode': 'push', 'cloudsync_folder': '/tmp/x'}, [])
    assert not r['ok'] and 'inaccessible' in r['error'].lower()


def test_push_ecrit_son_propre_fichier(tmp_path):
    cfg = {'cloudsync_mode': 'push', 'cloudsync_folder': str(tmp_path), 'callsign_contest': 'F4GLD'}
    r = cs.sync_now(cfg, [QSO_A, QSO_B])
    assert r['ok'] and r['mode'] == 'push' and r['pushed'] == 2 and r['pulled'] == 0
    my_file = tmp_path / cs.cloudsync_settings(cfg)['my_file']
    assert my_file.exists()
    saved = json.loads(my_file.read_text(encoding='utf-8'))
    assert {q['id'] for q in saved} == {1001, 1002}


def test_push_ne_lit_jamais_les_fichiers_des_autres(tmp_path, monkeypatch):
    """En mode push, aucun appel à add_qso_to_log même si d'autres fichiers existent."""
    (tmp_path / 'logx_cloudsync_G3XYZ_abcd1234.json').write_text(
        json.dumps([QSO_B]), encoding='utf-8')
    called = {'n': 0}
    def fake_add(q, force=False):
        called['n'] += 1
        return True, {}
    monkeypatch.setattr('logx_http.add_qso_to_log', fake_add)
    cfg = {'cloudsync_mode': 'push', 'cloudsync_folder': str(tmp_path), 'callsign_contest': 'F4GLD'}
    r = cs.sync_now(cfg, [QSO_A])
    assert r['ok'] and r['pulled'] == 0
    assert called['n'] == 0


def test_full_pousse_et_recupere_les_autres_postes(tmp_path, monkeypatch):
    (tmp_path / 'logx_cloudsync_G3XYZ_abcd1234.json').write_text(
        json.dumps([QSO_B]), encoding='utf-8')
    pulled_ids = []
    def fake_add(q, force=False):
        pulled_ids.append(q['id'])
        return True, {}
    monkeypatch.setattr('logx_http.add_qso_to_log', fake_add)
    cfg = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path), 'callsign_contest': 'F4GLD'}
    r = cs.sync_now(cfg, [QSO_A])
    assert r['ok'] and r['mode'] == 'full'
    assert r['pushed'] == 1 and r['pulled'] == 1 and r['sources'] == 1
    assert pulled_ids == [1002]


def test_full_ignore_son_propre_fichier_au_pull(tmp_path, monkeypatch):
    """Le fichier qu'on vient d'écrire soi-même ne doit jamais être relu comme
    s'il venait d'un autre poste — sinon un poste seul se "pull" lui-même."""
    called = {'n': 0}
    def fake_add(q, force=False):
        called['n'] += 1
        return True, {}
    monkeypatch.setattr('logx_http.add_qso_to_log', fake_add)
    cfg = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path), 'callsign_contest': 'F4GLD'}
    r = cs.sync_now(cfg, [QSO_A])
    assert r['ok'] and r['sources'] == 0 and called['n'] == 0


def test_full_qso_deja_present_localement_nest_pas_recompte(tmp_path, monkeypatch):
    """add_qso_to_log rejette les doublons (call+band+mode+contest) -> pulled
    ne doit compter QUE les insertions reelles, pas les rejets."""
    (tmp_path / 'logx_cloudsync_G3XYZ_abcd1234.json').write_text(
        json.dumps([QSO_B]), encoding='utf-8')
    def fake_add(q, force=False):
        return False, {'duplicate': True}   # déjà connu localement
    monkeypatch.setattr('logx_http.add_qso_to_log', fake_add)
    cfg = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path), 'callsign_contest': 'F4GLD'}
    r = cs.sync_now(cfg, [QSO_A])
    assert r['ok'] and r['pulled'] == 0 and r['sources'] == 1


def test_full_deux_syncs_concurrentes_ne_dupliquent_pas_en_mode_simple(tmp_path, monkeypatch):
    """Non-régression : deux synchronisations 'full' CONCURRENTES (POST
    /cloudsync/now pendant un cycle de _cloudsync_loop, ou worker abandonné
    après SYNC_TIMEOUT qui continue seul pendant le cycle suivant) tiraient
    chacune le même QSO distant. Chaque worker amorçait son 'seen' depuis un
    snapshot figé AVANT les insertions de l'autre, et add_qso_to_log ne refuse
    pas les doublons en usage_mode 'simple' (par conception) : doublon
    PERSISTANT dans le carnet (logx.db + shared_log.json + exports ADIF),
    jamais résorbé aux cycles suivants. Deux protections vérifiées ensemble ici
    (chacune insuffisante seule) : sérialisation des syncs (_sync_serial_lock)
    ET amorçage de 'seen' depuis le log VIVANT plutôt que depuis le snapshot de
    l'appelant — les vrais appelants figent leur copie AVANT sync_now."""
    import threading
    import logx_http as httpmod

    monkeypatch.setattr(httpmod, 'shared_log', [])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'simple'})

    remote = {'call': 'F5REM', 'band': '14', 'mode': 'SSB',
              'date': '20260720', 'time': '10:00', 'id': 111}
    (tmp_path / 'logx_cloudsync_AUTREPOSTE_deadbeef.json').write_text(
        json.dumps([remote]), encoding='utf-8')
    cfg = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path),
           'callsign_contest': 'F4GLD', 'usage_mode': 'simple'}

    # Barrière dans _read_qsos : force l'entrelacement au pire moment (les deux
    # 'seen' déjà calculés, aucune insertion faite) — le hasard des threads
    # produit le même entrelacement sans barrière dès que la lecture du dossier
    # cloud prend quelques centaines de ms (SYNC_TIMEOUT existe précisément
    # parce qu'elle peut durer des minutes). Timeout court : avec le correctif,
    # les syncs sont sérialisées, un seul worker atteint la barrière — elle
    # casse au bout de 2 s et chacun continue seul.
    barrier = threading.Barrier(2, timeout=2)
    real_read = cs._read_qsos

    def read_avec_barriere(path, secret=None):
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            pass
        return real_read(path, secret)

    monkeypatch.setattr(cs, '_read_qsos', read_avec_barriere)

    # Comme les vrais appelants (/cloudsync/now dans logx_http, _cloudsync_loop
    # dans logx_serveur) : chaque déclencheur fige SA copie du log AVANT
    # d'appeler sync_now.
    snapshots = [list(httpmod.shared_log), list(httpmod.shared_log)]
    results = []
    threads = [threading.Thread(target=lambda s=s: results.append(cs.sync_now(cfg, s)))
               for s in snapshots]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    calls = [q.get('call') for q in httpmod.shared_log]
    assert calls.count('F5REM') == 1, \
        f"QSO distant dupliqué par deux syncs concurrentes : {calls}"
    assert len(results) == 2 and all(r.get('ok') for r in results)
    assert sum(r.get('pulled', 0) for r in results) == 1


def test_status_compte_les_autres_installations(tmp_path):
    cfg = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path), 'callsign_contest': 'F4GLD'}
    cs.sync_now(cfg, [QSO_A])
    (tmp_path / 'logx_cloudsync_G3XYZ_abcd1234.json').write_text(
        json.dumps([QSO_B]), encoding='utf-8')
    st = cs.status(cfg)
    assert st['enabled'] and st['mode'] == 'full' and st['other_installations'] == 1


def test_status_desactive():
    st = cs.status({})
    assert st['enabled'] is False and st['mode'] == 'off'


def test_sync_now_borne_si_dossier_cloud_bloque_indefiniment(monkeypatch, tmp_path):
    """Dossier cloud en mode « placeholder » non hydraté (OneDrive/Synology
    Drive/Dropbox) : os.makedirs() peut rester bloqué indéfiniment sans lever
    aucune exception ni respecter aucun timeout Python (ce n'est pas un socket).
    sync_now() doit quand même rendre la main à l'appelant après SYNC_TIMEOUT,
    plutôt que de le geler sans fin."""
    import time
    def hung_makedirs(*a, **k):
        time.sleep(cs.SYNC_TIMEOUT + 5)
    monkeypatch.setattr(cs.os, 'makedirs', hung_makedirs)
    monkeypatch.setattr(cs, 'SYNC_TIMEOUT', 1)
    cfg = {'cloudsync_mode': 'push', 'cloudsync_folder': str(tmp_path), 'callsign_contest': 'F4GLD'}
    t0 = time.time()
    r = cs.sync_now(cfg, [QSO_A])
    elapsed = time.time() - t0
    assert not r['ok'] and 'lent' in r['error'].lower()
    assert elapsed < 4  # bien avant les cs.SYNC_TIMEOUT+5 s du blocage simulé


def test_status_borne_si_dossier_cloud_bloque_indefiniment(monkeypatch, tmp_path):
    """GET /data/network_status (pollé toutes les 20 s par la barre de statut
    de CHAQUE page ouverte, logx_statusbar.js) appelle status() dans le thread
    de la requête HTTP. Si le dossier de sync est un partage SMB/NAS
    injoignable, os.path.isdir() y bloque ~21 s (timeout SMB Windows) SANS
    lever d'exception — exactement le blocage déjà couvert pour sync_now par
    SYNC_TIMEOUT. status() doit rendre la main en STATUS_SCAN_TIMEOUT maxi
    (valeur en cache, sinon 0) au lieu de geler un thread serveur à chaque
    poll, précisément quand la pastille « Cloud Sync en échec » serait utile."""
    import threading
    import time
    release = threading.Event()
    real_isdir = os.path.isdir

    def hung_isdir(path):
        if os.path.abspath(str(path)) == os.path.abspath(str(tmp_path)):
            release.wait(15)   # seul le dossier de sync « SMB » bloque
            return False
        return real_isdir(path)

    monkeypatch.setattr(cs.os.path, 'isdir', hung_isdir)
    # raising=False : sans le correctif la constante n'existe pas encore —
    # on veut alors exercer le vrai chemin bloquant, pas un AttributeError.
    monkeypatch.setattr(cs, 'STATUS_SCAN_TIMEOUT', 1, raising=False)
    cfg = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path), 'callsign_contest': 'F4GLD'}
    try:
        t0 = time.time()
        st = cs.status(cfg)
        elapsed = time.time() - t0
    finally:
        release.set()   # libère le thread de scan abandonné avant le test suivant
    assert elapsed < 5  # bien avant les 15 s du blocage SMB simulé
    assert st['other_installations'] == 0  # aucune valeur connue -> 0, pas de gel


def test_status_rend_la_derniere_valeur_connue_quand_le_scan_bloque(monkeypatch, tmp_path):
    """Pendant un blocage SMB, les polls suivants doivent recevoir le DERNIER
    comptage complet connu (cache mémoire), pas un 0 mensonger qui ferait
    croire que les autres postes ont disparu."""
    import threading
    import time
    cfg = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path), 'callsign_contest': 'F4GLD'}
    (tmp_path / 'logx_cloudsync_G3XYZ_abcd1234.json').write_text(
        json.dumps([QSO_B]), encoding='utf-8')
    assert cs.status(cfg)['other_installations'] == 1  # cache chauffé, dossier sain

    release = threading.Event()
    real_isdir = os.path.isdir

    def hung_isdir(path):
        if os.path.abspath(str(path)) == os.path.abspath(str(tmp_path)):
            release.wait(15)
            return False
        return real_isdir(path)

    monkeypatch.setattr(cs.os.path, 'isdir', hung_isdir)
    monkeypatch.setattr(cs, 'STATUS_SCAN_TIMEOUT', 1, raising=False)
    try:
        t0 = time.time()
        st = cs.status(cfg)
        elapsed = time.time() - t0
    finally:
        release.set()
    assert elapsed < 5
    assert st['other_installations'] == 1  # cache, pas 0


def test_last_error_disparait_quand_on_desactive_cloudsync(tmp_path):
    """Revue adversariale : un échec avec Cloud Sync activé ne doit plus
    jamais réapparaître une fois l'utilisateur repassé en mode='off'."""
    # Un chemin de lecteur Windows (ex. "Z:\...") n'échoue QUE sous Windows —
    # sous Linux (CI), ':' et '\' sont des caractères de nom de fichier
    # valides : os.makedirs() créerait bêtement un dossier ainsi nommé au
    # lieu d'échouer (constaté en CI, cf. revue). Un sous-dossier d'un
    # FICHIER ordinaire échoue de façon garantie sur les deux plateformes
    # (NotADirectoryError), sans dépendre d'un chemin propre à un OS.
    blocker = tmp_path / 'bloqueur.txt'
    blocker.write_text('pas un dossier')
    cfg_bad = {'cloudsync_mode': 'full', 'cloudsync_folder': str(blocker / 'sous_dossier'),
               'callsign_contest': 'F4GLD'}
    cs.sync_now(cfg_bad, [])
    assert cs.status(cfg_bad)['last_error'] is not None  # échec bien enregistré

    cfg_off = dict(cfg_bad, cloudsync_mode='off')
    st = cs.status(cfg_off)
    assert st['enabled'] is False and st['last_error'] is None


def test_last_error_disparait_quand_le_dossier_est_corrige(tmp_path):
    """Revue adversariale : dossier cassé -> corrigé (toujours activé) mais
    aucune nouvelle tentative n'a encore eu lieu -> ne doit pas afficher
    l'ancienne erreur comme si le nouveau dossier avait déjà échoué."""
    # Même technique de dossier garanti invalide sur toute plateforme que
    # ci-dessus (voir commentaire dans test_last_error_disparait_quand_on_desactive_cloudsync).
    blocker = tmp_path / 'bloqueur2.txt'
    blocker.write_text('pas un dossier')
    cfg_bad = {'cloudsync_mode': 'full', 'cloudsync_folder': str(blocker / 'sous_dossier'),
               'callsign_contest': 'F4GLD'}
    cs.sync_now(cfg_bad, [])
    assert cs.status(cfg_bad)['last_error'] is not None

    cfg_fixed = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path),
                 'callsign_contest': 'F4GLD'}
    st = cs.status(cfg_fixed)
    assert st['enabled'] is True and st['last_error'] is None

    # et si le dossier redevient cassé sans nouvelle tentative, la pastille
    # ne doit pas non plus être ressuscitée par erreur (aucun test n'a couru
    # sur cfg_bad depuis le sync_now ci-dessus -> reste correctement signalée)
    assert cs.status(cfg_bad)['last_error'] is not None


# ─── Non-régression : suppressions/corrections vs fusion 'full' (tombstones) ──
# Bug critique confirmé : la fusion purement additive ressuscitait un QSO
# supprimé localement dès qu'un fichier d'un autre poste le contenait encore
# (résurrection silencieuse à chaque cycle de _cloudsync_loop), et
# ré-importait en DOUBLON — avec collision d'id — l'ancienne version d'un QSO
# corrigé via /log/update (la clé call+band+mode+date+heure diffère alors que
# l'id est identique). Tests avec le VRAI add_qso_to_log (pas de mock) : le
# scénario reproduit exactement le flux /log/delete → sync et /log/update →
# sync des postes réels.

def _isole_log_vivant(monkeypatch, initial_log):
    """Isole l'état partagé (log vivant, tombstones mémoire, config, disque)
    pour un test de fusion — tout est restauré par monkeypatch."""
    import logx_http as httpmod
    import logx_storage as storage
    monkeypatch.setattr(httpmod, 'shared_log', list(initial_log))
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(httpmod, 'current_config', {})
    monkeypatch.setattr(storage, 'deleted_qsos', [])
    return httpmod, storage


def test_full_ne_ressuscite_pas_un_qso_supprime(tmp_path, monkeypatch):
    """Scénario 1 du bug : le poste A supprime le QSO id=555001 (/log/delete :
    retrait de shared_log + mark_qso_deleted), le fichier du poste B le
    contient encore -> le pull ne doit PAS le ré-importer ('ok, pulled=1'
    silencieux avant correctif), et un tombstone persistant doit être écrit
    pour que la suppression se propage à B et survive à un redémarrage."""
    httpmod, storage = _isole_log_vivant(monkeypatch, [])
    supprime = {'id': 555001, 'call': 'F5ABC', 'band': '14', 'mode': 'SSB',
                'date': '20260720', 'time': '10:00'}
    (tmp_path / 'logx_cloudsync_G3XYZ_abcd1234.json').write_text(
        json.dumps([supprime]), encoding='utf-8')
    # Réplique fidèle de l'état APRÈS /log/delete/555001 côté A :
    storage.deleted_qsos.append({'id': 555001, 'v': 1})

    cfg = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path),
           'callsign_contest': 'F4GLD'}
    r = cs.sync_now(cfg, list(httpmod.shared_log))
    assert r['ok'] and r['pulled'] == 0, \
        f"QSO supprimé ressuscité par la sync : {r} / {httpmod.shared_log}"
    assert httpmod.shared_log == []
    # Le tombstone est persisté (la clé vient de la copie distante) : il
    # propage la suppression au poste B et survit à un redémarrage du serveur.
    tomb = tmp_path / cs.cloudsync_settings(cfg)['my_tomb']
    assert tomb.exists()
    assert 555001 in {t['id'] for t in json.loads(tomb.read_text(encoding='utf-8'))}


def test_full_ne_reimporte_pas_l_ancienne_version_d_un_qso_corrige(tmp_path, monkeypatch):
    """Scénario 2 du bug : correction F5ABC -> F5ABD via /log/update
    (remplacement EN PLACE, même id). L'ancienne version restée dans le
    fichier du poste B a une clé de fusion différente -> avant correctif elle
    revenait en DOUBLON avec collision d'id (deux QSO id=555002, /log/update
    et /log/delete visant le premier trouvé)."""
    corrige = {'id': 555002, 'call': 'F5ABD', 'band': '14', 'mode': 'SSB',
               'date': '20260720', 'time': '10:00'}
    ancienne = {'id': 555002, 'call': 'F5ABC', 'band': '14', 'mode': 'SSB',
                'date': '20260720', 'time': '10:00'}
    httpmod, _storage = _isole_log_vivant(monkeypatch, [corrige])
    (tmp_path / 'logx_cloudsync_G3XYZ_abcd1234.json').write_text(
        json.dumps([ancienne]), encoding='utf-8')

    cfg = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path),
           'callsign_contest': 'F4GLD'}
    r = cs.sync_now(cfg, list(httpmod.shared_log))
    assert r['ok'] and r['pulled'] == 0
    assert [q['call'] for q in httpmod.shared_log] == ['F5ABD'], \
        f"Ancienne version revenue en doublon : {httpmod.shared_log}"
    assert [q['id'] for q in httpmod.shared_log] == [555002]  # pas de collision d'id


def test_full_applique_la_suppression_d_un_autre_poste(tmp_path, monkeypatch):
    """Propagation : le poste B a supprimé le QSO id=555003 (tombstone dans
    SON fichier logx_cloudtomb_*). Ce poste doit le supprimer aussi (avec
    tombstone /log/list pour ses propres clients) au lieu de le re-pousser
    indéfiniment — c'est ce re-push qui rendait la suppression impossible."""
    qso = {'id': 555003, 'call': 'F5DEL', 'band': '14', 'mode': 'SSB',
           'date': '20260720', 'time': '10:00'}
    httpmod, storage = _isole_log_vivant(monkeypatch, [qso])
    (tmp_path / 'logx_cloudtomb_G3XYZ_abcd1234.json').write_text(
        json.dumps([{'id': 555003, 'key': ['F5DEL', '14', 'SSB', '20260720', '10:00'],
                     'ts': 1}]), encoding='utf-8')
    # B n'a pas encore réécrit son fichier de QSO : il contient toujours 555003
    (tmp_path / 'logx_cloudsync_G3XYZ_abcd1234.json').write_text(
        json.dumps([qso]), encoding='utf-8')

    cfg = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path),
           'callsign_contest': 'F4GLD'}
    r = cs.sync_now(cfg, list(httpmod.shared_log))
    assert r['ok'] and r.get('removed') == 1 and r['pulled'] == 0
    assert httpmod.shared_log == []
    # tombstone /log/list posé : un client delta de CE poste voit la disparition
    assert 555003 in {d['id'] for d in storage.deleted_qsos}


def test_tombstone_distant_ne_supprime_pas_un_qso_a_id_en_collision(tmp_path, monkeypatch):
    """Garde-fou : deux postes peuvent créer deux QSO DIFFÉRENTS à la même
    milliseconde (id = int(time*1000)). Un tombstone distant ne supprime que
    sur id ET clé identiques — jamais un QSO local légitime qui partage l'id
    par coïncidence."""
    autre_qso = {'id': 555004, 'call': 'F5BBB', 'band': '7', 'mode': 'CW',
                 'date': '20260720', 'time': '10:00'}
    httpmod, _storage = _isole_log_vivant(monkeypatch, [autre_qso])
    (tmp_path / 'logx_cloudtomb_G3XYZ_abcd1234.json').write_text(
        json.dumps([{'id': 555004, 'key': ['F5AAA', '14', 'SSB', '20260720', '09:00'],
                     'ts': 1}]), encoding='utf-8')

    cfg = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path),
           'callsign_contest': 'F4GLD'}
    r = cs.sync_now(cfg, list(httpmod.shared_log))
    assert r['ok'] and r.get('removed') == 0
    assert [q['call'] for q in httpmod.shared_log] == ['F5BBB']


def test_tombstone_persiste_bloque_encore_apres_redemarrage(tmp_path, monkeypatch):
    """logx_storage.deleted_qsos est une mémoire de PROCESS (vidée à chaque
    redémarrage du serveur) : c'est le fichier de tombstones de ce poste qui
    doit continuer de bloquer la résurrection après redémarrage."""
    httpmod, _storage = _isole_log_vivant(monkeypatch, [])   # deleted_qsos vide = redémarré
    supprime = {'id': 555005, 'call': 'F5OLD', 'band': '14', 'mode': 'SSB',
                'date': '20260720', 'time': '10:00'}
    (tmp_path / 'logx_cloudsync_G3XYZ_abcd1234.json').write_text(
        json.dumps([supprime]), encoding='utf-8')
    cfg = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path),
           'callsign_contest': 'F4GLD'}
    tomb = tmp_path / cs.cloudsync_settings(cfg)['my_tomb']
    tomb.write_text(json.dumps(
        [{'id': 555005, 'key': ['F5OLD', '14', 'SSB', '20260720', '10:00'], 'ts': 1}]),
        encoding='utf-8')

    r = cs.sync_now(cfg, list(httpmod.shared_log))
    assert r['ok'] and r['pulled'] == 0
    assert httpmod.shared_log == []


# ── Anti-rejeu (saved_at signé + suivi local par-poste) ────────────────────
# La signature HMAC ne couvrait que 'data' : elle protège contre la
# FALSIFICATION (forger un contenu sans le secret) mais pas contre le REJEU
# d'un ancien fichier légitimement signé (restauré depuis l'historique de
# versions du dossier cloud, une sauvegarde, une copie de conflit
# Synology/Dropbox...) — sig(data) reste valide indéfiniment, et un QSO
# tombstoné pouvait ressusciter si le fichier rejoué est antérieur à sa
# suppression. Chaque test réinitialise cs._seen_saved_at (cache mémoire du
# suivi anti-rejeu) : sans ça, plusieurs tests de ce fichier utilisant le même
# nom de fichier distant ('logx_cloudsync_G3XYZ_abcd1234.json', convention
# reprise par toute la suite ci-dessus) partageraient un état résiduel d'un
# test à l'autre — le même piège que la mémoire ci-dessus sur les fichiers
# partagés dans concours/, ici côté cache PROCESS plutôt que fichier disque.
def _seen_isole(monkeypatch):
    monkeypatch.setattr(cs, '_seen_saved_at', {})


def test_write_signed_inclut_saved_at_couvert_par_la_signature(tmp_path):
    """saved_at doit être signé, pas seulement présent : le modifier sans
    connaître le secret (donc sans recalculer 'sig') doit invalider le
    fichier — sinon saved_at ne protégerait rien du tout contre un rejeu."""
    path = tmp_path / 'f.json'
    cs._write_signed(str(path), [QSO_A], 'secret-equipe')
    raw = json.loads(path.read_text(encoding='utf-8'))
    assert 'saved_at' in raw and isinstance(raw['saved_at'], (int, float))
    assert 'sig' in raw and 'data' in raw

    # Contenu intact, signature intacte : la vérification passe et rend le
    # même saved_at que celui écrit.
    data, saved_at = cs._verify_signed(raw, 'secret-equipe')
    assert data == [QSO_A] and saved_at == raw['saved_at']

    # saved_at modifié SANS recalculer 'sig' (exactement ce qu'un tiers sans
    # le secret peut faire en remplaçant le fichier par une vieille copie
    # signée AILLEURS, ou en trafiquant le champ à la main) -> rejeté.
    triche = dict(raw)
    triche['saved_at'] = raw['saved_at'] + 1000
    data2, saved_at2 = cs._verify_signed(triche, 'secret-equipe')
    assert data2 is None and saved_at2 is None


def test_read_qsos_rejette_un_fichier_rejoue_anterieur_deja_connu(tmp_path, monkeypatch):
    """Cœur du correctif : un fichier plus ANCIEN mais VALIDEMENT signé
    (rejeu depuis l'historique du dossier cloud, une sauvegarde, une copie de
    conflit...) doit être rejeté dès qu'une version plus récente du MÊME
    fichier a déjà été lue — même si sa signature est parfaitement correcte
    en elle-même."""
    _seen_isole(monkeypatch)
    secret = 'secret-equipe'
    path = tmp_path / 'logx_cloudsync_G3XYZ_abcd1234.json'

    monkeypatch.setattr(cs.time, 'time', lambda: 1_000.0)
    cs._write_signed(str(path), [QSO_B], secret)
    ancien_contenu = path.read_bytes()   # snapshot de la version ANCIENNE

    assert cs._read_qsos(str(path), secret) == [QSO_B]   # lecture normale OK

    monkeypatch.setattr(cs.time, 'time', lambda: 2_000.0)
    cs._write_signed(str(path), [QSO_A, QSO_B], secret)
    assert cs._read_qsos(str(path), secret) == [QSO_A, QSO_B]   # nouvelle version OK

    # REJEU : le fichier redevient (octet pour octet) l'ancienne version,
    # toujours signée correctement -> _verify_signed seul la validerait.
    path.write_bytes(ancien_contenu)
    assert cs._read_qsos(str(path), secret) == [], \
        "un fichier rejoué (saved_at antérieur au dernier connu) a été accepté"


def test_read_tombstones_rejette_un_fichier_rejoue(tmp_path, monkeypatch):
    """Même protection côté fichier de tombstones : un rejeu qui « oublierait »
    une suppression déjà connue doit être rejeté, pas traité comme un fichier
    à jour amputé de son tombstone."""
    _seen_isole(monkeypatch)
    secret = 'secret-equipe'
    path = tmp_path / 'logx_cloudtomb_G3XYZ_abcd1234.json'

    monkeypatch.setattr(cs.time, 'time', lambda: 1_000.0)
    cs._write_signed(str(path), [], secret)
    vieux = path.read_bytes()
    assert cs._read_tombstones(str(path), secret) == []

    monkeypatch.setattr(cs.time, 'time', lambda: 2_000.0)
    tomb = {'id': 1002, 'key': list(cs._qso_key(QSO_B)), 'ts': 2000.0}
    cs._write_signed(str(path), [tomb], secret)
    assert cs._read_tombstones(str(path), secret) == [tomb]

    path.write_bytes(vieux)   # rejeu de la version SANS le tombstone
    assert cs._read_tombstones(str(path), secret) == [], \
        "un fichier de tombstones rejoué a été accepté malgré un saved_at antérieur"


def test_full_rejeu_ne_ressuscite_pas_un_qso_supprime_par_un_autre_poste(tmp_path, monkeypatch):
    """Scénario complet du défaut : le poste G3XYZ pousse un QSO, F4GLD le
    récupère, G3XYZ le supprime et repousse un fichier vide (avec tombstone) —
    F4GLD applique la suppression. Un tiers ayant accès en écriture au dossier
    partagé (mais PAS le secret) restaure ensuite l'ANCIEN fichier de G3XYZ
    (celui qui contenait encore le QSO) tel quel, octet pour octet — signature
    toujours valide puisqu'il a réellement été signé par G3XYZ à l'époque.
    Sans le correctif, ce fichier repasse pour « nouveau » au prochain cycle et
    le QSO supprimé ressuscite silencieusement ; avec le correctif, son
    saved_at est antérieur au dernier connu pour ce fichier -> rejeté."""
    secret = 'secret-equipe'
    _seen_isole(monkeypatch)
    httpmod, storage = _isole_log_vivant(monkeypatch, [])
    remote_path = tmp_path / 'logx_cloudsync_G3XYZ_abcd1234.json'
    cfg = {'cloudsync_mode': 'full', 'cloudsync_folder': str(tmp_path),
           'callsign_contest': 'F4GLD', 'cloudsync_secret': secret}
    # date/time EXPLICITES (contrairement à QSO_B) : add_qso_to_log complète
    # sinon date/time avec 'maintenant', ce qui changerait la clé de fusion
    # de la copie locale par rapport à celle calculée ici pour le tombstone.
    qso_remote = {'id': 1002, 'call': 'G3XYZ', 'band': '14', 'mode': 'CW',
                  'date': '20260720', 'time': '11:00'}

    # Cycle 1 (G3XYZ pousse le QSO) : F4GLD le récupère.
    monkeypatch.setattr(cs.time, 'time', lambda: 1_000.0)
    cs._write_signed(str(remote_path), [qso_remote], secret)
    ancien_fichier = remote_path.read_bytes()   # snapshot AVANT suppression

    r1 = cs.sync_now(cfg, list(httpmod.shared_log))
    assert r1['ok'] and r1['pulled'] == 1
    assert [q['id'] for q in httpmod.shared_log] == [1002]

    # Cycle 2 (G3XYZ supprime le QSO et repousse fichier vide + tombstone) :
    # F4GLD applique la suppression.
    monkeypatch.setattr(cs.time, 'time', lambda: 2_000.0)
    tomb_path = tmp_path / 'logx_cloudtomb_G3XYZ_abcd1234.json'
    cs._write_signed(str(remote_path), [], secret)
    cs._write_signed(str(tomb_path),
                      [{'id': 1002, 'key': list(cs._qso_key(qso_remote)), 'ts': 2000.0}], secret)

    r2 = cs.sync_now(cfg, list(httpmod.shared_log))
    assert r2['ok'] and r2.get('removed') == 1
    assert httpmod.shared_log == []

    # ATTAQUE : rejeu de l'ANCIEN fichier de G3XYZ (celui du cycle 1), signé
    # légitimement mais périmé — restauré tel quel dans le dossier partagé.
    remote_path.write_bytes(ancien_fichier)

    r3 = cs.sync_now(cfg, list(httpmod.shared_log))
    assert r3['ok'] and r3['pulled'] == 0, \
        f"QSO supprimé ressuscité par le rejeu d'un ancien fichier : {r3} / {httpmod.shared_log}"
    assert httpmod.shared_log == [], \
        f"QSO supprimé ressuscité par le rejeu d'un ancien fichier : {httpmod.shared_log}"
