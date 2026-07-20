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
