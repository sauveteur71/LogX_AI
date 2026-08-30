# -*- coding: utf-8 -*-
"""Points de chasse SOTA « indicatifs » — calcul local (logx_sota_points).

Règles vérifiées, sourcées sur les SOTA General Rules v1.20 :
- valeur d'un sommet = champ `points` (règle 3.11) ;
- chasse : 1 sommet compte 1×/jour UTC (règle 3.8 §3) ;
- S2S : sous-ensemble où mon propre sommet SOTA est renseigné (règle 3.8 §7) ;
- aucun bonus saisonnier (règle 3.11.1).
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_sota_points as sp   # noqa: E402


# Base de sommets factice : code -> détails. Points sourcés du barème 3.11.
_SOMMETS = {
    'G/LD-001': {'points': 8},    # Scafell Pike
    'G/LD-003': {'points': 6},
    'F/AB-001': {'points': 10},
    'HB/BE-100': {'points': 0},   # sommet à 0 pt (bande 1 / non-P150m, règle 3.11)
}


def _lookup(code):
    return _SOMMETS.get(code)


def _qso(sig_info, date, my=None, sig='SOTA'):
    q = {'call': 'DL1ABC', 'sig': sig, 'sig_info': sig_info, 'date': date}
    if my:
        q['my_sig'] = 'SOTA'
        q['my_sig_info'] = my
    return q


def test_un_qso_vaut_les_points_du_sommet():
    r = sp.points_chasse([_qso('G/LD-001', '20260130')], _lookup)
    assert r['chasse'] == 8
    assert r['sommets'] == 1
    assert r['s2s'] == 0


def test_meme_sommet_meme_jour_utc_compte_une_seule_fois():
    # Règle 3.8 §3 : un seul QSO par sommet et par jour UTC compte.
    log = [_qso('G/LD-001', '20260130'), _qso('G/LD-001', '20260130')]
    r = sp.points_chasse(log, _lookup)
    assert r['chasse'] == 8
    assert r['sommets'] == 1


def test_meme_sommet_jours_differents_recompte():
    log = [_qso('G/LD-001', '20260130'), _qso('G/LD-001', '20260131')]
    r = sp.points_chasse(log, _lookup)
    assert r['chasse'] == 16
    assert r['sommets'] == 2


def test_reference_non_sota_ignoree():
    # Le filtre programme (sig=='SOTA') doit exclure une réf logée sous un autre
    # programme MÊME si son sig_info coïncide avec un code de sommet valide —
    # sinon le filtre ne contraint rien (le lookup l'exclurait déjà tout seul).
    log = [_qso('G/LD-003', '20260130', sig='POTA'),   # 6 pts SI compté à tort
           _qso('G/LD-001', '20260130')]               # seul QSO SOTA : 8 pts
    r = sp.points_chasse(log, _lookup)
    assert r['chasse'] == 8
    assert r['sommets'] == 1


def test_sommet_inconnu_de_la_base_ignore():
    r = sp.points_chasse([_qso('G/XX-999', '20260130')], _lookup)
    assert r['chasse'] == 0
    assert r['sommets'] == 0


def test_sommet_a_zero_point_ignore():
    r = sp.points_chasse([_qso('HB/BE-100', '20260130')], _lookup)
    assert r['chasse'] == 0
    assert r['sommets'] == 0


def test_s2s_sous_ensemble_de_la_chasse():
    # QSO S2S (mon sommet + le sien) + un QSO de chasse pure.
    log = [
        _qso('F/AB-001', '20260201', my='G/LD-003'),   # S2S : 10 pts
        _qso('G/LD-001', '20260201'),                  # chasse pure : 8 pts
    ]
    r = sp.points_chasse(log, _lookup)
    assert r['chasse'] == 18          # 10 + 8, S2S compris dans la chasse
    assert r['s2s'] == 10
    assert r['s2s_sommets'] == 1
    assert r['s2s'] <= r['chasse']


def test_s2s_ignore_si_mon_sommet_absent():
    # my_sig SOTA mais my_sig_info vide -> pas un vrai S2S.
    q = _qso('F/AB-001', '20260201')
    q['my_sig'] = 'SOTA'
    q['my_sig_info'] = ''
    r = sp.points_chasse([q], _lookup)
    assert r['chasse'] == 10
    assert r['s2s'] == 0


def test_filtre_par_annee_utc():
    log = [_qso('G/LD-001', '20251231'), _qso('F/AB-001', '20260101')]
    r2026 = sp.points_chasse(log, _lookup, year=2026)
    assert r2026['chasse'] == 10          # seul F/AB-001 (2026)
    r2025 = sp.points_chasse(log, _lookup, year='2025')
    assert r2025['chasse'] == 8           # seul G/LD-001 (2025)


def test_frontiere_annee_31dec_vs_1er_jan():
    # 20261231 et 20270101 sont des années UTC différentes.
    log = [_qso('F/AB-001', '20261231'), _qso('F/AB-001', '20270101')]
    assert sp.points_chasse(log, _lookup, year=2026)['chasse'] == 10
    assert sp.points_chasse(log, _lookup, year=2027)['chasse'] == 10
    assert sp.points_chasse(log, _lookup)['chasse'] == 20   # tout le carnet


def test_totaux_annee_et_cumul():
    log = [
        _qso('G/LD-001', '20251115'),                  # 2025, chasse 8
        _qso('F/AB-001', '20260201', my='G/LD-003'),   # 2026, S2S 10
    ]
    t = sp.totaux(log, _lookup, annee_courante=2026)
    assert t['year'] == 2026
    assert t['chasse_year'] == 10 and t['s2s_year'] == 10
    assert t['chasse_all'] == 18 and t['s2s_all'] == 10


def test_entree_non_dict_toleree():
    log = [None, 'oups', _qso('G/LD-001', '20260130')]
    assert sp.points_chasse(log, _lookup)['chasse'] == 8
