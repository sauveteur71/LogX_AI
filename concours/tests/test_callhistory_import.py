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
import threading
import time

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


# ─── MASTER.SCP : récupération automatique depuis Internet ──────────────────
# Jamais de vrai appel réseau ici -- logx_utils.fetch_url est mocké (import
# local dans fetch_and_import_master_scp(), voir son commentaire "mockable
# par les tests", même convention que logx_qrz_push.test_connection).

def test_fetch_and_import_master_scp_succes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    captured = {}
    def fake_fetch_url(url, timeout=10, log_url=True):
        captured['url'] = url
        captured['timeout'] = timeout
        return "F4GLD\nF5ABC\n"
    monkeypatch.setattr('logx_utils.fetch_url', fake_fetch_url)
    r = ch.fetch_and_import_master_scp()
    assert r['ok'] and r['imported'] == 2 and r['total'] == 2
    assert captured['url'] == ch.MASTER_SCP_URL
    assert captured['timeout'] >= 10   # un fichier de ~350 Ko mérite plus que le défaut


def test_fetch_and_import_master_scp_reseau_injoignable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('logx_utils.fetch_url', lambda url, timeout=10, log_url=True: None)
    r = ch.fetch_and_import_master_scp()
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


# ─── Bug #1 (revue adversariale commit 36777e2) : cycle lire-fusionner-écrire
# SANS verrou -- deux imports concurrents perdaient silencieusement l'un des
# deux jeux de données. Reproduction avec 2 VRAIS threads (pas une simulation
# d'entrelacement) : un sleep() injecté dans json.load élargit la fenêtre de
# course pour la rendre déterministe (sans lui, la perte est intermittente,
# selon l'ordonnancement du thread par l'OS) -- il n'a aucune influence sur
# la correction du fix : le verrou sérialise les deux imports de toute façon,
# délai ou pas. Confirmé manuellement AVANT le fix (2 threads, 50+50
# indicatifs) : un thread perdait intégralement ses 50 indicatifs sans
# erreur rapportée, et un round a même levé un PermissionError (WinError 5)
# sur le double os.replace() concurrent -- les deux disparaissent avec le
# verrou (_master_scp_lock protège le cycle complet, pas seulement l'écriture).
def test_import_master_scp_concurrent_ne_perd_aucun_indicatif(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    orig_load = json.load

    def _slow_load(f, *a, **kw):
        data = orig_load(f, *a, **kw)
        time.sleep(0.05)
        return data

    monkeypatch.setattr(json, 'load', _slow_load)

    calls_a = [f"F4AAA{i:02d}" for i in range(50)]
    calls_b = [f"F4BBB{i:02d}" for i in range(50)]
    results = {}

    def _run(key, calls):
        results[key] = ch.import_master_scp("\n".join(calls))

    t1 = threading.Thread(target=_run, args=('a', calls_a))
    t2 = threading.Thread(target=_run, args=('b', calls_b))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert results['a']['ok'] and results['b']['ok']
    with open('master_scp.json', encoding='utf-8') as f:
        stored = set(json.load(f)['calls'])
    assert set(calls_a) <= stored, "indicatifs du thread A perdus (course lire-fusionner-écrire)"
    assert set(calls_b) <= stored, "indicatifs du thread B perdus (course lire-fusionner-écrire)"
    assert len(stored) == 100


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
    # contest='REF_CDF_HF_CW' : concours à échange département REF, seul cas
    # où Exch1 doit être interprété comme un département (voir bug #2).
    row = _row('F4GLD', 'Jean', 'JN18AA', '', '', '', '', '', '59', '', '', '', '', '', '')
    parsed, errors = ch.parse_n1mm_call_history(row + '\n', contest='REF_CDF_HF_CW')
    assert not errors
    assert parsed['F4GLD']['name'] == 'Jean'
    assert parsed['F4GLD']['locator'] == 'JN18AA'
    assert parsed['F4GLD']['dept'] == '59'


def test_parse_n1mm_directive_order():
    text = "!!Order!!,Call,Name,Sect,Exch1\nF4GLD,Jean,IDF,75\n"
    parsed, errors = ch.parse_n1mm_call_history(text, contest='REF_CDF_HF_CW')
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
    parsed, errors = ch.parse_n1mm_call_history(text, contest='REF_CDF_HF_CW')
    assert not errors and parsed['F4GLD']['dept'] == '33'


def test_parse_n1mm_texte_vide():
    parsed, errors = ch.parse_n1mm_call_history('')
    assert parsed == {} and errors == []


# ─── Bug #2 (revue adversariale commit 36777e2) : Exch1 n'est un département
# REF QUE si le concours ciblé a effectivement un échange département ────────

def test_parse_n1mm_exch1_non_interprete_hors_concours_dept():
    """dept_from_exchange() accepte tout jeton 2 chiffres 01-95 -- ce qui
    recouvre aussi des zones CQ/ITU ou des n° de série d'autres concours.
    Reproduction concrète du bug : importer un Call History CQ_WW_SSB avec
    Exch1='14' (zone CQ 14) ne doit PLUS produire un faux département '14'
    (Calvados)."""
    text = "!!Order!!,Call,Exch1\nDL1ABC,14\n"
    # Sans contest connu : prudence par défaut, rien n'est interprété.
    parsed, errors = ch.parse_n1mm_call_history(text)
    assert not errors and 'DL1ABC' not in parsed
    # CQ_WW_SSB : échange = RS + zone CQ, PAS un département REF.
    parsed2, errors2 = ch.parse_n1mm_call_history(text, contest='CQ_WW_SSB')
    assert not errors2 and 'DL1ABC' not in parsed2
    # REF_CDF_HF_CW : échange = RST + N°série + dept -> Exch1 EST le département.
    parsed3, errors3 = ch.parse_n1mm_call_history(text, contest='REF_CDF_HF_CW')
    assert not errors3 and parsed3['DL1ABC']['dept'] == '14'


def test_parse_n1mm_cqzone_toujours_interprete_meme_hors_concours_dept():
    """Le champ CqZone (colonne dédiée), lui, n'est jamais gaté par le type
    de concours : seul Exch1 est ambigu (échange générique)."""
    text = "!!Order!!,Call,CqZone\nDL1ABC,14\n"
    parsed, _ = ch.parse_n1mm_call_history(text, contest='CQ_WW_SSB')
    assert parsed['DL1ABC']['zone'] == '14'
    assert 'dept' not in parsed['DL1ABC']


# ─── Call History N1MM : import (par concours, jamais un remplacement pur) ─

def test_import_n1mm_sans_concours_erreur():
    r = ch.import_call_history_n1mm('', "!!Order!!,Call,Name\nF4GLD,Jean\n")
    assert r['ok'] is False


def test_import_n1mm_isole_par_concours(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r1 = ch.import_call_history_n1mm('REF_CDF_HF_CW', "!!Order!!,Call,Exch1\nF4GLD,75\n")
    assert r1['ok'] and r1['imported'] == 1 and r1['total_for_contest'] == 1
    # CQ_WW_SSB n'a PAS d'échange département REF : Exch1='14' (zone CQ) ne
    # doit jamais devenir un dept -- bug #2 (commit 36777e2, revue
    # adversariale). CqZone reste interprété (colonne dédiée, sans ambiguïté).
    r2 = ch.import_call_history_n1mm('CQ_WW_SSB', "!!Order!!,Call,Exch1,CqZone\nF4GLD,14,14\n")
    assert r2['ok'] and r2['total_for_contest'] == 1
    assert ch.call_history_count('REF_CDF_HF_CW') == 1
    assert ch.call_history_count('CQ_WW_SSB') == 1
    # même indicatif, mais dept différent selon le concours
    e1 = ch.lookup('F4GLD', shared_log=[], contest='REF_CDF_HF_CW')
    assert e1['dept'] == '75'
    e2 = ch.lookup('F4GLD', shared_log=[], contest='CQ_WW_SSB')
    assert e2.get('dept') is None      # Exch1 ignoré : pas d'échange dept sur CQ_WW_SSB
    assert e2['zone'] == '14'          # CqZone, lui, est bien remonté


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


# Bug #1 (revue adversariale commit 36777e2) : même chose que
# test_import_master_scp_concurrent_ne_perd_aucun_indicatif ci-dessus, mais
# pour call_history_n1mm.json -- avec en plus DEUX concours différents dans
# le même fichier store (le point sensible du bug : le cycle lire-fusionner-
# écrire porte sur TOUT le fichier, pas seulement la tranche d'un concours,
# donc deux imports sur deux concours DIFFÉRENTS se marchaient dessus aussi).
def test_import_n1mm_concurrent_ne_perd_aucune_fiche(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    orig_load = json.load

    def _slow_load(f, *a, **kw):
        data = orig_load(f, *a, **kw)
        time.sleep(0.05)
        return data

    monkeypatch.setattr(json, 'load', _slow_load)

    # Colonne Name (toujours non vide, quelle que soit la valeur) plutôt
    # qu'Exch1 : évite tout risque de confondre une perte par COURSE avec une
    # entrée légitimement écartée parce que sa valeur ne serait pas un n° de
    # département FR valide (01-95) -- non pertinent ici, seule la survie des
    # 100 fiches importe.
    rows_a = [f"F4AAA{i:02d},OpA{i:02d}" for i in range(50)]
    rows_b = [f"F4BBB{i:02d},OpB{i:02d}" for i in range(50)]
    text_a = "!!Order!!,Call,Name\n" + "\n".join(rows_a) + "\n"
    text_b = "!!Order!!,Call,Name\n" + "\n".join(rows_b) + "\n"
    results = {}

    def _run(key, contest, text):
        results[key] = ch.import_call_history_n1mm(contest, text)

    t1 = threading.Thread(target=_run, args=('a', 'REF_CDF_HF_CW', text_a))
    t2 = threading.Thread(target=_run, args=('b', 'REF_CDF_HF_CW', text_b))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert results['a']['ok'] and results['b']['ok']
    assert ch.call_history_count('REF_CDF_HF_CW') == 100, (
        "fiches perdues (course lire-fusionner-écrire sur call_history_n1mm.json)")
    for i in range(50):
        assert ch.lookup(f"F4AAA{i:02d}", shared_log=[], contest='REF_CDF_HF_CW') is not None
        assert ch.lookup(f"F4BBB{i:02d}", shared_log=[], contest='REF_CDF_HF_CW') is not None


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
