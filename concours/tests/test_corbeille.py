# -*- coding: utf-8 -*-
"""Corbeille de QSO (logx_corbeille) : capture la donnée COMPLÈTE d'un QSO
supprimé (contrairement au tombstone logx_storage.mark_qso_deleted qui ne
retient que {'id','v'}, inexploitable pour une restauration). Fonctions
PURES (capturer/purger_perimes/lister/restaurer/resume) + persistance
disque dédiée (charger/enregistrer), même patron que logx_operator_goals."""
import json
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_corbeille as cb  # noqa: E402


# ─── capturer ────────────────────────────────────────────────────────────

def test_capturer_une_entree_par_qso():
    qsos = [{'id': 1, 'call': 'F4ABC'}, {'id': 2, 'call': 'F4DEF'}]
    r = cb.capturer(qsos, now=1000.0)
    assert len(r) == 2
    assert all(e['deleted_at'] == 1000.0 for e in r)
    assert {e['qso']['call'] for e in r} == {'F4ABC', 'F4DEF'}


def test_capturer_ignore_les_qso_sans_id():
    qsos = [{'call': 'F4ABC'}, {'id': 2, 'call': 'F4DEF'}]
    r = cb.capturer(qsos, now=1000.0)
    assert len(r) == 1 and r[0]['qso']['call'] == 'F4DEF'


def test_capturer_copie_le_qso_pas_de_reference_partagee():
    qso = {'id': 1, 'call': 'F4ABC'}
    r = cb.capturer([qso], now=1000.0)
    qso['call'] = 'MUTE'
    assert r[0]['qso']['call'] == 'F4ABC'          # la capture n'a pas suivi la mutation


# ─── purger_perimes ─────────────────────────────────────────────────────

def test_purge_retire_les_entrees_trop_vieilles():
    entrees = [
        {'qso': {'id': 1}, 'deleted_at': 0},                       # vieux de 40j
        {'qso': {'id': 2}, 'deleted_at': 39 * 86400},               # vieux de 1j
    ]
    now = 40 * 86400
    r = cb.purger_perimes(entrees, now, retention_s=30 * 86400)
    assert [e['qso']['id'] for e in r] == [2]


def test_purge_garde_pile_a_la_limite():
    entrees = [{'qso': {'id': 1}, 'deleted_at': 0}]
    r = cb.purger_perimes(entrees, now=30 * 86400, retention_s=30 * 86400)
    assert len(r) == 1                             # <= retention -> gardé


def test_purge_borne_le_nombre_garde_les_plus_recentes():
    entrees = [{'qso': {'id': i}, 'deleted_at': i} for i in range(10)]
    r = cb.purger_perimes(entrees, now=100, retention_s=1000, max_entrees=3)
    assert [e['qso']['id'] for e in r] == [7, 8, 9]


# ─── lister ──────────────────────────────────────────────────────────────

def test_lister_ordre_plus_recent_dabord():
    entrees = [
        {'qso': {'id': 1}, 'deleted_at': 10},
        {'qso': {'id': 2}, 'deleted_at': 30},
        {'qso': {'id': 3}, 'deleted_at': 20},
    ]
    r = cb.lister(entrees, now=100, retention_s=1000)
    assert [e['qso']['id'] for e in r] == [2, 3, 1]


def test_lister_exclut_les_perimees():
    entrees = [{'qso': {'id': 1}, 'deleted_at': 0}]
    r = cb.lister(entrees, now=1000, retention_s=500)
    assert r == []


# ─── restaurer ───────────────────────────────────────────────────────────

def test_restaurer_retire_lentree_et_rend_le_qso():
    entrees = [{'qso': {'id': 1, 'call': 'F4ABC'}, 'deleted_at': 10},
               {'qso': {'id': 2, 'call': 'F4DEF'}, 'deleted_at': 20}]
    qso, reste = cb.restaurer(entrees, 1)
    assert qso == {'id': 1, 'call': 'F4ABC'}
    assert [e['qso']['id'] for e in reste] == [2]


def test_restaurer_id_absent_rend_none_et_ne_modifie_rien():
    entrees = [{'qso': {'id': 1}, 'deleted_at': 10}]
    qso, reste = cb.restaurer(entrees, 999)
    assert qso is None
    assert reste == entrees


def test_restaurer_choisit_la_plus_recente_si_id_duplique():
    entrees = [{'qso': {'id': 1, 'v': 'vieille'}, 'deleted_at': 10},
               {'qso': {'id': 1, 'v': 'recente'}, 'deleted_at': 20}]
    qso, reste = cb.restaurer(entrees, 1)
    assert qso['v'] == 'recente'
    assert len(reste) == 1 and reste[0]['qso']['v'] == 'vieille'


def test_restaurer_rend_une_copie_pas_une_reference():
    entrees = [{'qso': {'id': 1, 'call': 'F4ABC'}, 'deleted_at': 10}]
    qso, _ = cb.restaurer(entrees, 1)
    qso['call'] = 'MUTE'
    assert entrees[0]['qso']['call'] == 'F4ABC'


# ─── resume ──────────────────────────────────────────────────────────────

def test_resume_champs_attendus():
    e = {'qso': {'id': 1, 'call': 'F4ABC', 'band': '14', 'mode': 'SSB',
                 'date': '20260910', 'time': '1200'}, 'deleted_at': 42}
    r = cb.resume(e)
    assert r == {'id': 1, 'call': 'F4ABC', 'band': '14', 'mode': 'SSB',
                 'date': '20260910', 'time': '1200', 'deleted_at': 42}


def test_resume_qso_partiel_jamais_dexception():
    r = cb.resume({'qso': {'id': 5}, 'deleted_at': 1})
    assert r['id'] == 5 and r['call'] == '' and r['band'] == ''


# ─── persistance (charger/enregistrer) ──────────────────────────────────

def test_charger_fichier_absent_donne_liste_vide(tmp_path, monkeypatch):
    monkeypatch.setattr(cb, 'FICHIER', str(tmp_path / 'pas_la.json'))
    assert cb.charger() == []


def test_charger_fichier_corrompu_donne_liste_vide(tmp_path, monkeypatch):
    p = tmp_path / 'c.json'
    p.write_text('{ pas du json', encoding='utf-8')
    monkeypatch.setattr(cb, 'FICHIER', str(p))
    assert cb.charger() == []


def test_aller_retour_enregistrer_puis_charger(tmp_path, monkeypatch):
    monkeypatch.setattr(cb, 'FICHIER', str(tmp_path / 'c.json'))
    entrees = [{'qso': {'id': 1, 'call': 'F4ABC'}, 'deleted_at': 1000.0}]
    cb.enregistrer(entrees)
    assert cb.charger(now=1000.0) == entrees
    disque = json.load(open(str(tmp_path / 'c.json'), encoding='utf-8'))
    assert disque == entrees


def test_charger_purge_les_perimees_au_chargement(tmp_path, monkeypatch):
    import time
    monkeypatch.setattr(cb, 'FICHIER', str(tmp_path / 'c.json'))
    vieux = time.time() - 40 * 86400
    cb.enregistrer([{'qso': {'id': 1}, 'deleted_at': vieux}])
    assert cb.charger() == []                     # trop vieux -> filtré à la lecture


# ─── glue capturer_et_persister / restaurer_et_persister ────────────────

def test_capturer_et_persister_ajoute_a_lexistant(tmp_path, monkeypatch):
    monkeypatch.setattr(cb, 'FICHIER', str(tmp_path / 'c.json'))
    cb.capturer_et_persister([{'id': 1, 'call': 'F4ABC'}], now=1000.0)
    cb.capturer_et_persister([{'id': 2, 'call': 'F4DEF'}], now=2000.0)
    dispo = cb.charger(now=2000.0)
    assert {e['qso']['id'] for e in dispo} == {1, 2}


def test_capturer_et_persister_liste_vide_ne_touche_pas_le_fichier(tmp_path, monkeypatch):
    cible = tmp_path / 'c.json'
    monkeypatch.setattr(cb, 'FICHIER', str(cible))
    cb.capturer_et_persister([], now=1000.0)
    assert not cible.exists()                      # aucune écriture pour rien


def test_restaurer_et_persister_aller_retour(tmp_path, monkeypatch):
    monkeypatch.setattr(cb, 'FICHIER', str(tmp_path / 'c.json'))
    cb.capturer_et_persister([{'id': 7, 'call': 'F4ABC', 'band': '14'}], now=1000.0)
    qso = cb.restaurer_et_persister(7, now=1000.0)
    assert qso == {'id': 7, 'call': 'F4ABC', 'band': '14'}
    assert cb.charger(now=1000.0) == []              # retiré de la corbeille


def test_restaurer_et_persister_id_absent_rend_none(tmp_path, monkeypatch):
    monkeypatch.setattr(cb, 'FICHIER', str(tmp_path / 'c.json'))
    assert cb.restaurer_et_persister(999, now=1000.0) is None
