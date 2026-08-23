# -*- coding: utf-8 -*-
"""Reprise du journal d'appoint au démarrage : les QSO repris doivent être
PERSISTÉS immédiatement (axe « carnet perdu », station F4GLD).

Sur la branche « base présente » de load_log_from_disk(), la séquence était
chargement base -> _reprendre_journal_apres_chargement() -> return, SANS aucun
save_log_to_disk(). Or _rejouer_journal() renomme le fichier journal (os.replace)
AVANT toute écriture, et la reprise se contente de poser _disk_version=None en
pariant sur une mutation FUTURE. Si le process est fermé entre la reprise et la
1re mutation, les QSO repris n'existent NI en base (jamais écrite) NI dans le
journal (renommé, non rejoué au démarrage suivant) : perte silencieuse.

La branche migration/sans-base faisait, elle, bien
`if _reprendre_journal_apres_chargement() or migration: save_log_to_disk()` —
l'incohérence prouve que le save était l'intention.

Ce test mesure la VRAIE base SQLite (pas un mannequin), à travers un redémarrage.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_storage as st  # noqa: E402


def _qso(i):
    return {'id': 1000 + i, 'call': f'F{i}ABC', 'band': '14', 'mode': 'CW',
            'contest': '', 'date': '20260801', 'time': '12:03',
            'operator': 'OP1', 'points': 1, 'locator': 'JO31AA'}


def _in_tmp(tmp_path, fn):
    old = os.getcwd()
    os.chdir(tmp_path)
    saved = (list(st.shared_log), st.log_version, st.load_failed,
             st.ecriture_bloquee, set(st._journal_ids))
    try:
        st.shared_log[:] = []
        st.log_version = 0
        st.load_failed = False
        st.ecriture_bloquee = None
        st._journal_ids = set()
        st._forget_disk_state()
        return fn()
    finally:
        st.shared_log[:] = saved[0]
        st.log_version, st.load_failed = saved[1], saved[2]
        st.ecriture_bloquee = saved[3]
        st._journal_ids = saved[4]
        st._forget_disk_state()
        os.chdir(old)


def _base_calls():
    conn = sqlite3.connect(st.DB_FILE)
    try:
        return sorted(r[0] for r in conn.execute('SELECT call FROM qso'))
    finally:
        conn.close()


def test_reprise_journal_persistee_survit_au_redemarrage(tmp_path):
    def scenario():
        # Session A : base avec 1 QSO + 1 QSO seulement dans le journal d'appoint
        # (comme une session à persistance gelée : jamais écrit en base).
        st.shared_log[:] = [_qso(1)]
        st.bump_log_version()
        st.save_log_to_disk()
        assert _base_calls() == ['F1ABC']
        st._journaliser([_qso(2)])
        assert os.path.exists(st.FICHIER_JOURNAL)

        # Session B : rechargement -> les 2 QSO en mémoire, journal mis de côté.
        st.shared_log[:] = []
        st._forget_disk_state()
        st.load_log_from_disk()
        assert sorted(q['call'] for q in st.shared_log) == ['F1ABC', 'F2ABC']
        assert not os.path.exists(st.FICHIER_JOURNAL)

        # Session C : fermeture AVANT toute mutation, puis rechargement. Le QSO
        # repris doit avoir été persisté en base par la reprise (le correctif).
        st.shared_log[:] = []
        st._forget_disk_state()
        st.load_log_from_disk()
        assert sorted(q['call'] for q in st.shared_log) == ['F1ABC', 'F2ABC'], \
            "QSO repris du journal PERDU : non persisté après la reprise"
        assert _base_calls() == ['F1ABC', 'F2ABC']

    _in_tmp(tmp_path, scenario)
