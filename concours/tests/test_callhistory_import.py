# -*- coding: utf-8 -*-
"""Tests de l'extension de logx_callhistory.py (Super Check Partial) :
import MASTER.SCP, vérification « N+1 » (distance de Damerau-Levenshtein de
1, façon busted call check des gros loggers de concours), import Call
History au format N1MM (préremplissage d'échange PAR CONCOURS).

Isolé du vrai calldb.json/archives/master_scp.json du poste (gitignorés,
propres à cette machine) via tmp_path/monkeypatch.chdir OU monkeypatch des
loaders — même piège documenté dans test_ref_features.py : sans ça, un test
passe ou échoue selon l'historique local accumulé, invisible en dev mais
cassant sur un checkout propre / en CI."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import logx_callhistory as ch


@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch):
    """Isole chaque test de l'index général ET du cache Call History N1MM
    (tous deux des globals de module, partagés entre tests sans ce reset)."""
    monkeypatch.setattr(ch, '_index', {})
    monkeypatch.setattr(ch, '_built_at', 0.0)
    monkeypatch.setattr(ch, '_ch_cache', None)
    monkeypatch.setattr(ch, '_ch_cache_mtime', None)
    yield


def _row(*fields):
    return ','.join(fields)


# ─── MASTER.SCP : parsing pur ────────────────────────────────────────────────

def test_parse_master_scp_dedoublonne_trie_et_filtre():
    text = "F4GLD\nf5abc\n\n# commentaire\n; autre commentaire\nF6KQJ\nF4GLD\n"
    assert ch.parse_master_scp(text) == ['F4GLD', 'F5ABC', 'F6KQJ']


def test_parse_master_scp_ignore_mot_sans_chiffre():
    """Un vrai indicatif contient toujours au moins un chiffre — un mot
    ordinaire glissé dans un fichier tiers mal formé ne doit pas passer
    pour un indicatif."""
    assert ch.parse_master_scp("BONJOUR\nF4GLD\n") == ['F4GLD']


def test_parse_master_scp_texte_vide_ou_none():
    assert ch.parse_master_scp('') == []
    assert ch.parse_master_scp(None) == []


# ─── MASTER.SCP : import (fusion, jamais un remplacement) ──────────────────

def test_import_master_scp_fusionne_sans_ecraser(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r1 = ch.import_master_scp("F4GLD\nF5ABC\n")
    assert r1['ok'] and r1['imported'] == 2 and r1['added'] == 2 and r1['total'] == 2
    r2 = ch.import_master_scp("F5ABC\nF6KQJ\n")   # F5ABC déjà présent, F6KQJ nouveau
    assert r2['ok'] and r2['imported'] == 2 and r2['added'] == 1 and r2['total'] == 3
    with open('master_scp.json', encoding='utf-8') as f:
        data = json.load(f)
    assert set(data['calls']) == {'F4GLD', 'F5ABC', 'F6KQJ'}


def test_import_master_scp_fichier_sans_indicatif_valide(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = ch.import_master_scp('texte sans aucun indicatif valide')
    assert r['ok'] is False and 'error' in r
    assert not os.path.isfile('master_scp.json')


def test_master_scp_alimente_build_index_sans_ecraser_calldb(tmp_path, monkeypatch):
    """MASTER.SCP est chargé en PREMIER (voir build_index) : un indicatif
    présent dans calldb.json avec un dept/locator ne doit JAMAIS les perdre
    parce qu'il est AUSSI dans MASTER.SCP (source sans dept/locator)."""
    monkeypatch.chdir(tmp_path)
    ch.import_master_scp("F4GLD\nF9ZZZ\n")   # F9ZZZ : SEULEMENT dans MASTER.SCP
    with open('calldb.json', 'w', encoding='utf-8') as f:
        json.dump({'calls': {'F4GLD': {'dept': '75', 'locator': 'JN18AA'}}}, f)
    idx = ch.build_index(force=True)
    assert idx['F4GLD']['dept'] == '75' and idx['F4GLD']['locator'] == 'JN18AA'
    assert 'F9ZZZ' in idx and idx['F9ZZZ']['dept'] is None   # connu, mais sans dept


# ─── Vérification N+1 (Damerau-Levenshtein == 1) ───────────────────────────

@pytest.mark.parametrize('a,b,expected', [
    ('F4GLD', 'F4GLD', False),      # identique : rien à corriger
    ('F4GLD', 'F4GLDD', True),      # insertion (lettre en trop)
    ('F4GLD', 'F4GL', True),        # suppression (lettre en moins)
    ('F4GLD', 'F4XLD', True),       # substitution
    ('F4GLD', 'F4GDL', True),       # transposition de deux lettres adjacentes
    ('F4GLD', 'W1ABC', False),      # trop éloigné
    ('F4GLD', 'F4GLDXY', False),    # 2 caractères de différence de longueur
])
def test_one_edit_away(a, b, expected):
    assert ch._one_edit_away(a, b) is expected


def test_near_matches_rattrape_une_frappe_fausse():
    log = [{'call': 'F4GLD', 'locator': 'JN18AA', 'date': '20260101', 'num_rcvd': ''}]
    ch.build_index(log, force=True)
    matches = ch.near_matches('F4GLDD')     # une lettre en trop à la frappe
    assert any(m['call'] == 'F4GLD' for m in matches)


def test_near_matches_rien_si_deja_connu():
    log = [{'call': 'F4GLD', 'locator': 'JN18AA', 'date': '20260101', 'num_rcvd': ''}]
    ch.build_index(log, force=True)
    assert ch.near_matches('F4GLD') == []


def test_near_matches_trop_court_ignore():
    assert ch.near_matches('F4') == []


def test_near_matches_tries_travailles_avant(monkeypatch):
    """Deux corrections possibles : celle déjà travaillée (qso_count > 0)
    remonte en premier, comme suggest()."""
    _neutralize_global_sources(monkeypatch)
    log = [
        {'call': 'F4GLX', 'locator': 'JN18AA', 'date': '20260101', 'num_rcvd': ''},
        {'call': 'F4GLY', 'locator': 'JN18AA', 'date': '20260101', 'num_rcvd': ''},
    ]
    ch.build_index(log, force=True)
    ch.update_from_qso({'call': 'F4GLX', 'locator': 'JN18AA', 'date': '20260102'})
    matches = ch.near_matches('F4GLZ')   # distance 1 des deux
    assert [m['call'] for m in matches][0] == 'F4GLX'


# ─── Call History N1MM : parsing pur ───────────────────────────────────────

def test_parse_n1mm_ordre_par_defaut():
    row = _row('F4GLD', 'Jean', 'JN18AA', '', '', '', '', '', '59', '', '', '', '', '', '')
    parsed, errors = ch.parse_n1mm_call_history(row + '\n')
    assert not errors
    assert parsed['F4GLD']['name'] == 'Jean'
    assert parsed['F4GLD']['locator'] == 'JN18AA'
    assert parsed['F4GLD']['dept'] == '59'


def test_parse_n1mm_directive_order():
    text = "!!Order!!,Call,Name,Sect,Exch1\nF4GLD,Jean,IDF,75\n"
    parsed, errors = ch.parse_n1mm_call_history(text)
    assert not errors
    assert parsed['F4GLD']['section'] == 'IDF'
    assert parsed['F4GLD']['dept'] == '75'


def test_parse_n1mm_zone_depuis_cqzone():
    row = _row('F4GLD', '', '', '', '', '', '', '', '', '', '', '14', '', '', '')
    parsed, _ = ch.parse_n1mm_call_history(row + '\n')
    assert parsed['F4GLD']['zone'] == '14'


def test_parse_n1mm_mapstatetosect():
    text = "!!Order!!,Call,State,Sect\n!!MapStateToSect!!\nF4GLD,CA,\n"
    parsed, _ = ch.parse_n1mm_call_history(text)
    assert parsed['F4GLD']['section'] == 'CA'


def test_parse_n1mm_sans_mapstatetosect_sect_vide_reste_absente():
    text = "!!Order!!,Call,State,Sect\nF4GLD,CA,\n"
    parsed, _ = ch.parse_n1mm_call_history(text)
    assert 'section' not in parsed.get('F4GLD', {})


def test_parse_n1mm_fourchargridsq_tronque_a_4():
    text = "!!Order!!,Call,Loc1\n!!FourCharGridSq!!\nF4GLD,JN18AA\n"
    parsed, _ = ch.parse_n1mm_call_history(text)
    assert parsed['F4GLD']['locator'] == 'JN18'


def test_parse_n1mm_directive_inconnue_reconnue_sans_effet():
    text = "!!Order!!,Call,Name\n!!Validate50State!!\nF4GLD,Jean\n"
    parsed, errors = ch.parse_n1mm_call_history(text)
    assert not errors and parsed['F4GLD']['name'] == 'Jean'


def test_parse_n1mm_ligne_invalide_comptee_en_erreur_pas_bloquante():
    text = "!!Order!!,Call,Name\n,Sans indicatif\nF4GLD,Jean\n"
    parsed, errors = ch.parse_n1mm_call_history(text)
    assert len(errors) == 1 and list(parsed) == ['F4GLD']


def test_parse_n1mm_ignore_commentaires_et_lignes_vides():
    text = "!!Order!!,Call,Name\n# commentaire\n\nF4GLD,Jean\n"
    parsed, errors = ch.parse_n1mm_call_history(text)
    assert not errors and parsed['F4GLD']['name'] == 'Jean'


def test_parse_n1mm_point_virgule_accepte():
    text = "!!Order!!;Call;Exch1\nF4GLD;33\n"
    parsed, errors = ch.parse_n1mm_call_history(text)
    assert not errors and parsed['F4GLD']['dept'] == '33'


def test_parse_n1mm_texte_vide():
    parsed, errors = ch.parse_n1mm_call_history('')
    assert parsed == {} and errors == []


# ─── Call History N1MM : import (par concours, jamais un remplacement pur) ─

def test_import_n1mm_sans_concours_erreur():
    r = ch.import_call_history_n1mm('', "!!Order!!,Call,Name\nF4GLD,Jean\n")
    assert r['ok'] is False


def test_import_n1mm_isole_par_concours(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r1 = ch.import_call_history_n1mm('REF_CDF_HF_CW', "!!Order!!,Call,Exch1\nF4GLD,75\n")
    assert r1['ok'] and r1['imported'] == 1 and r1['total_for_contest'] == 1
    r2 = ch.import_call_history_n1mm('CQ_WW_SSB', "!!Order!!,Call,Exch1\nF4GLD,14\n")
    assert r2['ok'] and r2['total_for_contest'] == 1
    assert ch.call_history_count('REF_CDF_HF_CW') == 1
    assert ch.call_history_count('CQ_WW_SSB') == 1
    # même indicatif, mais dept différent selon le concours (14 n'est pas un
    # département valide -> pas de dept pour l'entrée CQ_WW_SSB)
    e1 = ch.lookup('F4GLD', shared_log=[], contest='REF_CDF_HF_CW')
    assert e1['dept'] == '75'


def test_import_n1mm_reimport_ecrase_ses_propres_entrees(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ch.import_call_history_n1mm('REF_CDF_HF_CW', "!!Order!!,Call,Exch1\nF4GLD,75\n")
    ch.import_call_history_n1mm('REF_CDF_HF_CW', "!!Order!!,Call,Exch1\nF4GLD,13\n")
    assert ch.call_history_count('REF_CDF_HF_CW') == 1
    e = ch.lookup('F4GLD', shared_log=[], contest='REF_CDF_HF_CW')
    assert e['dept'] == '13'


def test_import_n1mm_fichier_sans_entree_valide(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = ch.import_call_history_n1mm('REF_CDF_HF_CW', "!!Order!!,Call,Name\n,Sans indicatif\n")
    assert r['ok'] is False


# ─── Surclassement à la lecture : lookup/suggest/export_index(contest=...) ──

def _neutralize_global_sources(monkeypatch):
    """Empêche build_index() de lire le vrai calldb.json/archives/logx.db/
    master_scp.json du poste : seul le `shared_log` passé explicitement (et
    le Call History importé dans tmp_path) alimente l'index pour ce test."""
    monkeypatch.setattr(ch, '_load_calldb', lambda: None)
    monkeypatch.setattr(ch, '_load_archives', lambda: None)
    monkeypatch.setattr(ch, '_load_qso_archive', lambda: None)
    monkeypatch.setattr(ch, '_load_master_scp', lambda: None)


def test_lookup_via_call_history_seul_meme_si_jamais_travaille(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _neutralize_global_sources(monkeypatch)
    ch.import_call_history_n1mm('REF_CDF_HF_CW', "!!Order!!,Call,Exch1,Name\nDL1XYZ,33,Hans\n")
    assert ch.lookup('DL1XYZ', shared_log=[]) is None            # sans concours : inconnu
    e = ch.lookup('DL1XYZ', shared_log=[], contest='REF_CDF_HF_CW')
    assert e is not None
    assert e['dept'] == '33' and e['name'] == 'Hans' and e['worked'] is False


def test_lookup_surclasse_dept_locator_deja_connus(tmp_path, monkeypatch):
    """Le dept du Call History (spécifique à CE concours) prime sur celui
    déjà présent dans l'index général (calldb/log), sans effacer qso_count."""
    monkeypatch.chdir(tmp_path)
    _neutralize_global_sources(monkeypatch)
    log = [{'call': 'F4GLD', 'locator': 'JN18AA', 'date': '20260101', 'num_rcvd': '99'}]
    ch.build_index(log, force=True)
    ch.import_call_history_n1mm('REF_CDF_HF_CW', "!!Order!!,Call,Exch1\nF4GLD,75\n")
    sans = ch.lookup('F4GLD', log)
    assert sans['dept'] is None    # '99' n'est pas un dept valide -> rien dans l'index général
    avec = ch.lookup('F4GLD', log, contest='REF_CDF_HF_CW')
    assert avec['dept'] == '75' and avec['worked'] is True   # qso_count préservé


def test_suggest_ajoute_les_indicatifs_uniquement_connus_via_call_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _neutralize_global_sources(monkeypatch)
    log = [{'call': 'DL1AAA', 'locator': 'JO40AA', 'date': '20260101', 'num_rcvd': ''}]
    ch.build_index(log, force=True)
    ch.import_call_history_n1mm('REF_CDF_HF_CW', "!!Order!!,Call,Exch1\nDL1ABZ,33\n")
    # sans concours : seul l'indicatif déjà travaillé remonte
    out = ch.suggest('DL1A', log)
    assert {s['call'] for s in out} == {'DL1AAA'}
    # avec concours : l'indicatif du Call History apparaît aussi, après lui
    out2 = ch.suggest('DL1A', log, contest='REF_CDF_HF_CW')
    calls = [s['call'] for s in out2]
    assert calls[0] == 'DL1AAA'
    assert 'DL1ABZ' in calls
    dl1abz = next(s for s in out2 if s['call'] == 'DL1ABZ')
    assert dl1abz['dept'] == '33' and dl1abz['worked'] is False


def test_export_index_surclasse_et_ajoute_pour_le_concours(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _neutralize_global_sources(monkeypatch)
    log = [{'call': 'F4GLD', 'locator': 'JN18AA', 'date': '20260101', 'num_rcvd': '99'}]
    ch.build_index(log, force=True)
    ch.import_call_history_n1mm(
        'REF_CDF_HF_CW', "!!Order!!,Call,Exch1,Name\nF4GLD,75,Jean\nDL9ZZZ,33,Hans\n")
    idx_sans = ch.export_index(log)
    assert 'name' not in idx_sans['calls']['F4GLD']
    assert 'DL9ZZZ' not in idx_sans['calls']
    idx_avec = ch.export_index(log, contest='REF_CDF_HF_CW')
    assert idx_avec['calls']['F4GLD']['name'] == 'Jean'
    assert idx_avec['calls']['F4GLD']['dept'] == '75'
    assert idx_avec['calls']['DL9ZZZ']['dept'] == '33'
    assert 'worked' not in idx_avec['calls']['DL9ZZZ']   # jamais travaillé
