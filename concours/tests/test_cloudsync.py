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

    def read_avec_barriere(path):
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            pass
        return real_read(path)

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
