# -*- coding: utf-8 -*-
"""Tests des moteurs propagation/compétition : météores, avion, tropo,
RBN (parseur), scoreboard, backup."""
import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Météores ────────────────────────────────────────────────────────────────

def test_meteores_perseides_actif_a_laube():
    import radiocontest_meteors as met
    q = met.ms_quality(datetime.datetime(2026, 8, 12, 6, 0))
    assert q['level'] == 'excellent'
    assert any(s['active'] and s['name'] == 'Perséides' for s in q['showers'])


def test_meteores_faible_hors_creneau_hiver():
    import radiocontest_meteors as met
    q = met.ms_quality(datetime.datetime(2026, 3, 1, 15, 0))
    assert q['level'] in ('faible', 'moyen')


# ─── Tropo (physique de réfractivité) ────────────────────────────────────────

def test_tropo_refractivite_decroit_avec_altitude():
    import radiocontest_tropo as tr
    n_bas = tr._refractivity(1000, 15, 70)
    n_haut = tr._refractivity(900, 9, 55)
    assert n_bas > n_haut                      # N décroît normalement
    g = (n_haut - n_bas) / ((990 - 110) / 1000)
    level, score = tr._classify(g)
    assert level in ('normal', 'super')


def test_tropo_classification_ducting():
    import radiocontest_tropo as tr
    assert tr._classify(-200)[0] == 'ducting'
    assert tr._classify(-100)[0] == 'super'
    assert tr._classify(-40)[0] == 'normal'
    assert tr._classify(10)[0] == 'sous'


# ─── RBN (parseur, sans réseau) ──────────────────────────────────────────────

def test_rbn_parse_mes_spots():
    import radiocontest_rbn as rbn
    txt = ('DX de DL0ABC-#:  14025.0  F6KQJ  CW    22 dB  28 wpm  CQ    1432Z\n'
           'DX de W3ZZZ-#:  14025.1  F6KQJ  CW  15 dB 25 wpm CQ 1433Z\n'
           'DX de X-#:  7005.0  OTHER  CW  30 dB  20 wpm  CQ  1434Z\n')
    sp = rbn.parse_rbn(txt, 'F6KQJ')
    assert len(sp) == 2                        # OTHER exclu
    assert sp[0]['snr'] == 22 and sp[0]['band'] == '14'
    assert all(s['spotter'] in ('DL0ABC', 'W3ZZZ') for s in sp)


# ─── Scoreboard ──────────────────────────────────────────────────────────────

def test_scoreboard_snapshot_et_xml():
    import radiocontest_scoreboard as sb
    log = [{'contest': 'X', 'call': 'A', 'band': '144', 'points': 45, 'locator': 'JN25GO'},
           {'contest': 'X', 'call': 'B', 'band': '432', 'points': 30, 'locator': 'JN33AA'}]
    snap = sb.build_score_snapshot(log, {'contest': 'X'})
    assert snap['score'] == 75 and snap['qso'] == 2 and snap['mults'] == 2
    xml = sb.build_n1mm_xml(snap, {'callsign_contest': 'F6KQJ'})
    assert '<score>75</score>' in xml and '<dynamicresults>' in xml


def test_scoreboard_desactive_par_defaut():
    import radiocontest_scoreboard as sb
    assert sb.push({}, [{'call': 'A'}])['ok'] is False


# ─── Backup ──────────────────────────────────────────────────────────────────

def test_backup_ecrit_et_retention():
    import radiocontest_backup as bk
    d = tempfile.mkdtemp()
    try:
        log = [{'call': 'F1ABC', 'band': '144', 'mode': 'SSB', 'date': '20260718'}]
        r = bk.run_backup({'callsign': 'F6KQJ', 'backup_folder': d}, log)
        assert r['ok']
        assert any(f.endswith('.json') for f in r['files'])
        assert bk.status({'backup_folder': d})['backups_kept'] >= 0
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
        for f in ('backup_state.json',):
            if os.path.exists(f):
                os.remove(f)


def test_backup_sans_dossier():
    import radiocontest_backup as bk
    assert bk.run_backup({}, [])['ok'] is False
