# -*- coding: utf-8 -*-
"""Tests du stockage SQLite du log partagé (radiocontest_storage)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import radiocontest_storage as st

QSO = {'id': 123, 'call': 'DL1ABC', 'band': '14', 'mode': 'CW',
       'contest': 'EU_HF_CHAMP', 'date': '20260801', 'time': '12:03',
       'operator': 'OP1', 'points': 1, 'locator': 'JO31AA',
       'rst_sent': '599', 'num_sent': '001', 'dist': 700, '_edited': True}


def _in_tmp(tmp_path, fn):
    """Exécute fn dans un dossier vierge (les chemins du module sont relatifs)."""
    old = os.getcwd()
    os.chdir(tmp_path)
    saved = list(st.shared_log)
    try:
        st.shared_log[:] = []
        return fn()
    finally:
        st.shared_log[:] = saved
        os.chdir(old)


def test_roundtrip_sqlite(tmp_path):
    def run():
        st.shared_log[:] = [QSO]
        st.save_log_to_disk()
        assert os.path.exists(st.DB_FILE)
        st.shared_log[:] = []
        st.load_log_from_disk()
        assert len(st.shared_log) == 1
        q = st.shared_log[0]
        # Colonnes structurées ET champs annexes (extra JSON) restitués
        assert q['call'] == 'DL1ABC' and q['band'] == '14'
        assert q['rst_sent'] == '599' and q['_edited'] is True and q['dist'] == 700
    _in_tmp(tmp_path, run)


def test_migration_one_shot_depuis_json(tmp_path):
    def run():
        with open('shared_log.json', 'w', encoding='utf-8') as f:
            json.dump([QSO, {**QSO, 'id': 124, 'call': 'F1XYZ'}], f)
        st.load_log_from_disk()
        assert len(st.shared_log) == 2
        assert os.path.exists(st.DB_FILE)          # base créée par la migration
        # Redémarrage suivant : la base est la source, plus le JSON
        st.shared_log[:] = []
        st.load_log_from_disk()
        assert {q['call'] for q in st.shared_log} == {'DL1ABC', 'F1XYZ'}
    _in_tmp(tmp_path, run)


def test_reset_archive_sans_perte(tmp_path):
    def run():
        st.shared_log[:] = [QSO]
        st.save_log_to_disk()
        assert st.archive_current_log() == 1
        st.shared_log[:] = []
        st.save_log_to_disk()                       # le reset vide la table qso
        conn = st._db()
        live = conn.execute('SELECT COUNT(*) FROM qso').fetchone()[0]
        arch = conn.execute('SELECT COUNT(*) FROM qso_archive').fetchone()[0]
        conn.close()
        assert live == 0 and arch == 1              # rien de perdu
    _in_tmp(tmp_path, run)
