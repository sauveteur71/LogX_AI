# -*- coding: utf-8 -*-
"""Câblage client de l'auto-remplissage du PRÉNOM du correspondant (demande
F4GLD) : champ éditable #inputName, pré-rempli au lookup (base interne + QRZ),
corrigeable, la correction prime et enrichit la base interne à l'enregistrement.
Assertions STRUCTURELLES (le comportement pur est couvert par test_calldb_name).
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


def test_champ_prenom_editable_present():
    html = _lire('logx_logbook.html')
    assert 'id="inputName"' in html                         # champ éditable
    assert 'PRÉNOM CORRESPONDANT' in html                   # étiquette explicite


def test_applycalldata_remplit_le_prenom_si_vide():
    js = _lire('logx_lookup.js')
    # rempli depuis la base interne (dbData.name), seulement si le champ est vide
    assert 'inputName' in js
    assert 'dbData && dbData.name' in js
    assert '!nameField.value' in js                         # ne surcharge jamais une correction


def test_lookup_interne_et_maj_base_portent_le_prenom():
    js = _lire('logx_lookup.js')
    # /calldb/lookup : le prénom (base interne) est rempli, corrigeable
    assert '/calldb/lookup/' in js and 'd.name' in js
    # updateCallDB envoie le prénom au serveur (enrichissement base interne)
    assert 'function updateCallDB(call, locator, dept, name)' in js
    assert 'name: name||' in js


def test_lookup_qrz_remplit_le_prenom():
    js = _lire('logx_callbook.js')
    # QRZ (seule source internet de prénom) : #inputName rempli si vide
    assert "getElementById('inputName')" in js
    assert '!nameInput.value && d.name' in js


def test_submit_le_prenom_saisi_prime_et_enrichit_la_base():
    js = _lire('logx_logbook.js')
    # la valeur du champ prime sur l'annuaire (callbookPourQso, spread avant)
    assert 'const nameManuel' in js
    assert 'if(nameManuel) qso.name = nameManuel;' in js
    # à l'enregistrement, le prénom enrichit la base interne
    assert 'updateCallDB(call, loc, null, nameManuel)' in js


def test_clearform_vide_le_prenom():
    js = _lire('logx_logbook.js')
    assert "getElementById('inputName')" in js
    # nettoyé comme les autres champs propres au contact
    assert re.search(r"_nm\s*=\s*document\.getElementById\('inputName'\);\s*if\(_nm\)\s*_nm\.value\s*=\s*'';", js)


import re  # noqa: E402
