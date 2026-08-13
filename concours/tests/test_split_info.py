# -*- coding: utf-8 -*-
"""parse_split_info() (logx_clusters.py) : détection best-effort d'un split/
QSX dans le commentaire libre d'un spot cluster. Aucun test ne couvrait cette
fonction jusqu'ici. Couvre en particulier le garde-fou contre les faux
positifs sur "UP"/"DOWN"/"DN" sans chiffre — ces mots sont un jargon radio
courant sans rapport avec un split ("SIGS UP" = signaux qui montent, pas une
station en split) et ne doivent être retenus que combinés à un chiffre
d'offset, à SPLIT, ou en tout début de commentaire."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_clusters as clusters   # noqa: E402


# ─── Vrais positifs ─────────────────────────────────────────────────────────

def test_up_seul():
    r = clusters.parse_split_info('UP')
    assert r['split'] is True
    assert r['direction'] == 'up'
    assert r['offset_khz'] is None


def test_up_avec_offset_colle():
    r = clusters.parse_split_info('UP5')
    assert r['split'] is True
    assert r['direction'] == 'up'
    assert r['offset_khz'] == 5.0


def test_down_avec_offset_espace():
    r = clusters.parse_split_info('DOWN 2')
    assert r['split'] is True
    assert r['direction'] == 'down'
    assert r['offset_khz'] == 2.0


def test_dn_avec_offset():
    r = clusters.parse_split_info('DN 3')
    assert r['split'] is True
    assert r['direction'] == 'down'
    assert r['offset_khz'] == 3.0


def test_qsx_frequence():
    r = clusters.parse_split_info('QSX 14195')
    assert r['split'] is True
    assert r['qsx_khz'] == 14195.0


def test_split_seul():
    r = clusters.parse_split_info('SPLIT')
    assert r['split'] is True


def test_up_combine_a_split_pas_en_tete():
    """"SPLIT" ailleurs dans le commentaire valide un UP/DOWN non-initial,
    même sans chiffre d'offset."""
    r = clusters.parse_split_info('LOUD SPLIT UP')
    assert r['split'] is True
    assert r['direction'] == 'up'


# ─── Faux positifs à éviter (le bug corrigé) ───────────────────────────────

def test_sigs_up_pas_un_split():
    r = clusters.parse_split_info('SIGS UP')
    assert r['direction'] is None
    assert r['split'] is False


def test_sigs_up_good_pas_un_split():
    r = clusters.parse_split_info('SIGS UP GOOD')
    assert r['direction'] is None
    assert r['split'] is False


def test_conds_up_pas_un_split():
    r = clusters.parse_split_info("COND'S UP")
    assert r['direction'] is None
    assert r['split'] is False


def test_conds_up_and_down_pas_un_split():
    r = clusters.parse_split_info("COND'S UP AND DOWN")
    assert r['direction'] is None
    assert r['split'] is False


# ─── Bords ──────────────────────────────────────────────────────────────────

def test_vide_pas_de_split():
    r = clusters.parse_split_info('')
    assert r == {'split': False, 'qsx_khz': None, 'offset_khz': None, 'direction': None}


def test_none_pas_de_split():
    r = clusters.parse_split_info(None)
    assert r['split'] is False


def test_update_upload_pas_confondus_avec_up():
    """UPDATE/UPLOAD ne doivent pas déclencher UP (lookahead (?![A-Z]))."""
    r = clusters.parse_split_info('FT8 UPDATE SOON')
    assert r['direction'] is None
    assert r['split'] is False
