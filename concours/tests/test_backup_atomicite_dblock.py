# -*- coding: utf-8 -*-
"""Non-régression : run_backup ne doit jamais produire une SAUVEGARDE invalide.

Deux défauts corrigés (audit + vérification adversariale) :

1. shutil.copy2('logx.db', dst) était appelé depuis le thread backup SANS
   prendre logx_storage._db_lock, alors que save_log_to_disk() (thread HTTP,
   à chaque /log/add) réécrit la base par DELETE FROM qso + INSERT dans une
   transaction. Une copie tombant dans cette fenêtre capture le fichier en
   plein milieu de transaction, sans son journal de rollback : backup .db
   corrompu ou vide (« database disk image is malformed » reproduit sur un
   log de 4000 QSO), alors que c'est LE fichier compté par status().

2. Les backups .json/.adi (et backup_state.json) étaient écrits par
   open(dst, 'w') + write directs : un kill en pleine écriture (fermeture de
   l'appli — le thread backup est daemon —, arrêt Windows) laissait un
   fichier TRONQUÉ sous un nom de sauvegarde légitime, qui devenait « la
   sauvegarde la plus récente » pour _prune/_stamp.
"""
import json
import os
import sqlite3
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_backup as bk
import logx_storage as storage


def _mini_db(path='logx.db'):
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE qso (id INTEGER, call TEXT)')
    conn.executemany('INSERT INTO qso VALUES (?, ?)',
                     [(i, f'F{i}ABC') for i in range(50)])
    conn.commit()
    conn.close()


def test_copie_db_attend_le_verrou_db(tmp_path, monkeypatch):
    """_db_lock pris (= transaction DELETE+INSERT de save_log_to_disk en
    cours) : run_backup doit ATTENDRE le verrou avant de copier logx.db,
    pas copier un fichier en plein milieu de transaction."""
    monkeypatch.chdir(tmp_path)
    _mini_db()
    folder = tmp_path / 'backups'
    cfg = {'backup_folder': str(folder), 'callsign': 'F4GLD'}

    result = {}
    t = threading.Thread(target=lambda: result.update(bk.run_backup(cfg, None)),
                         daemon=True)
    assert storage._db_lock.acquire(timeout=5)
    try:
        t.start()
        t.join(timeout=1.5)
        assert t.is_alive(), (
            'run_backup a copié logx.db alors que _db_lock était pris '
            '(transaction save_log_to_disk simulée en cours) : la copie ne '
            'prend pas le verrou -> backup potentiellement corrompu/vide')
    finally:
        storage._db_lock.release()
    t.join(timeout=10)
    assert not t.is_alive() and result.get('ok'), result

    # Le backup produit une fois le verrou rendu est une base SAINE.
    dbs = list(folder.glob('logx_*.db'))
    assert len(dbs) == 1
    conn = sqlite3.connect(str(dbs[0]))
    assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert conn.execute('SELECT COUNT(*) FROM qso').fetchone()[0] == 50
    conn.close()


def test_echec_ecriture_json_ne_laisse_pas_de_backup_tronque(tmp_path,
                                                             monkeypatch):
    """Écriture .json qui meurt en plein vol (ici : objet non sérialisable
    au milieu du log — même effet qu'un kill : l'écriture s'arrête après un
    contenu partiel) : AUCUN fichier tronqué ne doit rester sous un nom de
    sauvegarde légitime logx_*.json."""
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / 'backups'
    cfg = {'backup_folder': str(folder), 'callsign': 'F4GLD'}
    shared = [{'id': i, 'call': f'F{i}ABC', 'comment': 'x' * 200}
              for i in range(2000)]
    shared.append({'bad': object()})   # sérialisation JSON échoue ICI,
                                       # après des centaines de Ko déjà émis

    r = bk.run_backup(cfg, shared)

    assert not r.get('ok')
    tronques = sorted(p.name for p in folder.glob('logx_*.json'))
    assert tronques == [], (
        f'backup .json TRONQUÉ laissé sous un nom légitime : {tronques} — '
        f'il deviendrait « la sauvegarde la plus récente » et pousserait un '
        f'bon backup hors de la rétention KEEP')


def test_nominal_backup_complet_valide(tmp_path, monkeypatch):
    """Cas nominal inchangé : .db sain + .json parseable + .adi présent +
    stamp valide (non-régression du comportement d'avant le correctif)."""
    monkeypatch.chdir(tmp_path)
    _mini_db()
    folder = tmp_path / 'backups'
    cfg = {'backup_folder': str(folder), 'callsign': 'F4GLD'}
    shared = [{'id': i, 'call': f'F{i}ABC', 'band': '20m', 'mode': 'CW',
               'date': '2026-07-25', 'time': '12:00'} for i in range(10)]

    r = bk.run_backup(cfg, shared)

    assert r.get('ok'), r
    exts = sorted(p.suffix for p in folder.iterdir())
    assert exts == ['.adi', '.db', '.json']
    js = next(folder.glob('logx_*.json'))
    assert len(json.loads(js.read_text(encoding='utf-8'))) == 10
    conn = sqlite3.connect(str(next(folder.glob('logx_*.db'))))
    assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    conn.close()
    # Aucun résidu .tmp, et le stamp est un JSON valide.
    assert not list(folder.glob('*.tmp'))
    stamp = json.loads((tmp_path / 'backup_state.json').read_text(
        encoding='utf-8'))
    assert stamp.get('files') and stamp.get('last')
