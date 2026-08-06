# -*- coding: utf-8 -*-
"""Tests de la cascade callbook (logx_callbook) : QRZ (si configuré)
-> HamQTH -> HamDB. Avant ce module, un opérateur sans abonnement QRZ n'avait
STRICTEMENT AUCUNE fiche à la frappe — /qrz/lookup répondait juste "non
configuré" sans jamais tenter les deux sources gratuites."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_callbook as callbook
import logx_qrz as qrz
import logx_clusters as clusters
import logx_callhistory

HAMDB_OK = ('{"hamdb":{"version":"1","callsign":{"call":"W1AW","class":"","expires":'
            '"02/26/2031","status":"A","grid":"FN31pr","lat":"41.71","lon":"-72.72",'
            '"fname":"ARRL","mi":"","name":"HQ OPERATORS CLUB","suffix":"","addr1":'
            '"225 MAIN ST","addr2":"NEWINGTON","state":"CT","zip":"06111",'
            '"country":"United States"},"messages":{"status":"OK"}}}')
HAMDB_NOT_FOUND = ('{"hamdb":{"version":"1","callsign":{"call":"NOT_FOUND","class":'
                   '"NOT_FOUND","expires":"NOT_FOUND","status":"NOT_FOUND","grid":'
                   '"NOT_FOUND","lat":"NOT_FOUND","lon":"NOT_FOUND","fname":"NOT_FOUND",'
                   '"mi":"NOT_FOUND","name":"NOT_FOUND","suffix":"NOT_FOUND","addr1":'
                   '"NOT_FOUND","addr2":"NOT_FOUND","state":"NOT_FOUND","zip":"NOT_FOUND",'
                   '"country":"NOT_FOUND"},"messages":{"status":"NOT_FOUND"}}}')


def _reset():
    callbook._cache.clear()
    qrz._session.update(key='', ts=0)
    qrz._lookup_cache.clear()
    callbook._circuit.update(fails=0, until=0)


# ─── lookup_hamdb (parsing JSON réel, vérifié contre l'API en direct) ──────

def test_lookup_hamdb_ok(monkeypatch):
    monkeypatch.setattr('logx_utils.fetch_url', lambda url, timeout=8: HAMDB_OK)
    r = callbook.lookup_hamdb('w1aw')
    assert r['ok'] and r['call'] == 'W1AW' and r['source'] == 'hamdb'
    assert r['name'] == 'ARRL HQ OPERATORS CLUB'
    assert r['grid'] == 'FN31PR' and r['country'] == 'United States'
    assert r['qth'] == 'NEWINGTON, CT'


def test_lookup_hamdb_indicatif_hors_usa(monkeypatch):
    monkeypatch.setattr('logx_utils.fetch_url', lambda url, timeout=8: HAMDB_NOT_FOUND)
    r = callbook.lookup_hamdb('F4GLD')
    assert not r['ok'] and 'USA' in r['error']


def test_lookup_hamdb_injoignable(monkeypatch):
    monkeypatch.setattr('logx_utils.fetch_url', lambda url, timeout=8: None)
    r = callbook.lookup_hamdb('W1AW')
    assert not r['ok'] and 'injoignable' in r['error']


def test_lookup_hamdb_reponse_illisible(monkeypatch):
    monkeypatch.setattr('logx_utils.fetch_url', lambda url, timeout=8: 'pas du json')
    r = callbook.lookup_hamdb('W1AW')
    assert not r['ok'] and 'illisible' in r['error']


def test_lookup_hamdb_indicatif_vide():
    r = callbook.lookup_hamdb('')
    assert not r['ok'] and 'vide' in r['error'].lower()


# ─── Cascade complète ───────────────────────────────────────────────────────

def test_cascade_qrz_en_tete_si_configure(monkeypatch):
    _reset()
    monkeypatch.setattr(qrz, 'lookup', lambda call, user, pw: {'ok': True, 'call': call, 'name': 'X'})
    hamqth_called = {'n': 0}
    monkeypatch.setattr(clusters, 'lookup_hamqth', lambda call: hamqth_called.update(n=hamqth_called['n'] + 1) or None)
    r = callbook.lookup('F6KQJ', {'qrz_user': 'u', 'qrz_password': 'p'})
    assert r['ok'] and r['source'] == 'qrz'
    assert hamqth_called['n'] == 0  # jamais tenté : QRZ a déjà répondu


def test_cascade_photo_qrz_transmise_telle_quelle(monkeypatch):
    """La cascade ne filtre/transforme pas 'image' — logx_qrz.py a déjà validé
    le schéma http(s) avant de le renvoyer (voir test_qrz.py)."""
    _reset()
    monkeypatch.setattr(qrz, 'lookup', lambda call, user, pw:
                        {'ok': True, 'call': call, 'name': 'X', 'image': 'https://cdn-xml.qrz.com/z/f6kqj/f6kqj.jpg'})
    r = callbook.lookup('F6KQJ', {'qrz_user': 'u', 'qrz_password': 'p'})
    assert r['ok'] and r['image'] == 'https://cdn-xml.qrz.com/z/f6kqj/f6kqj.jpg'


def test_cascade_repli_hamqth_si_qrz_non_configure(monkeypatch):
    _reset()
    monkeypatch.setattr(clusters, 'lookup_hamqth',
                        lambda call: {'call': call, 'locator': 'JN15XC', 'country': 'France', 'continent': 'EU'})
    r = callbook.lookup('F6KQJ', {})  # pas d'identifiants QRZ dans cfg
    assert r['ok'] and r['source'] == 'hamqth'
    assert r['grid'] == 'JN15XC' and r['country'] == 'France'
    assert r['name'] == ''  # HamQTH ne donne jamais le nom


def test_cascade_repli_hamqth_si_qrz_echoue(monkeypatch):
    _reset()
    monkeypatch.setattr(qrz, 'lookup', lambda call, user, pw: {'ok': False, 'error': 'Indicatif introuvable sur QRZ'})
    monkeypatch.setattr(clusters, 'lookup_hamqth',
                        lambda call: {'call': call, 'locator': 'FN31PR', 'country': 'USA', 'continent': 'NA'})
    r = callbook.lookup('W1AW', {'qrz_user': 'u', 'qrz_password': 'p'})
    assert r['ok'] and r['source'] == 'hamqth'


def test_cascade_repli_hamdb_si_hamqth_muet(monkeypatch):
    _reset()
    monkeypatch.setattr(clusters, 'lookup_hamqth', lambda call: None)
    monkeypatch.setattr(callbook, 'lookup_hamdb',
                        lambda call: {'ok': True, 'call': call, 'name': 'ARRL', 'qth': '', 'state': 'CT',
                                     'country': 'United States', 'grid': 'FN31PR', 'dxcc': '', 'source': 'hamdb'})
    r = callbook.lookup('W1AW', {})
    assert r['ok'] and r['source'] == 'hamdb'


def test_cascade_tout_echoue(monkeypatch):
    _reset()
    monkeypatch.setattr(clusters, 'lookup_hamqth', lambda call: None)
    monkeypatch.setattr(callbook, 'lookup_hamdb', lambda call: {'ok': False, 'error': 'Indicatif introuvable sur HamDB'})
    r = callbook.lookup('ZZ9ZZZ', {})
    assert not r['ok']
    assert 'HamQTH' in r['error'] and 'HamDB' in r['error']


def test_cascade_indicatif_vide():
    r = callbook.lookup('', {})
    assert not r['ok'] and 'vide' in r['error'].lower()


def test_cascade_cache_evite_double_appel_hamqth(monkeypatch):
    _reset()
    calls = {'n': 0}
    def fake_hamqth(call):
        calls['n'] += 1
        return {'call': call, 'locator': 'JN15XC', 'country': 'France', 'continent': 'EU'}
    monkeypatch.setattr(clusters, 'lookup_hamqth', fake_hamqth)
    callbook.lookup('F6KQJ', {})
    callbook.lookup('F6KQJ', {})  # 2e appel : depuis le cache de la cascade
    assert calls['n'] == 1


# ─── Régression : enrich_unknown_calls ne doit plus écraser l'entrée calldb ──
# (bug réel documenté en mémoire : un enrichissement HamQTH remplaçait toute
# l'entrée calls_db[call], perdant le 'dept' déjà connu localement — un
# radioamateur REF perdait son suivi de département dès que HamQTH répondait).


# ─── Previous QSOs (historique local, logx_callhistory) ─────────────────────
# Ajouté en tête (disjoncteur ouvert = hors ligne) et en filet de dernier
# recours (cascade réseau tout entière en échec) — jamais de réseau, jamais
# prioritaire sur un résultat QRZ/HamQTH/HamDB positif.

def test_previous_qso_filet_si_cascade_reseau_echoue_totalement(monkeypatch):
    _reset()
    monkeypatch.setattr(clusters, 'lookup_hamqth', lambda call: None)
    monkeypatch.setattr(callbook, 'lookup_hamdb', lambda call: {'ok': False, 'error': 'Indicatif introuvable sur HamDB'})
    monkeypatch.setattr(logx_callhistory, 'lookup',
                        lambda call, shared_log=None: {'call': call, 'dept': None,
                                                       'locator': 'JN15XC', 'qso_count': 3,
                                                       'last_date': '20260101', 'worked': True})
    r = callbook.lookup('F6ZZZ', {}, shared_log=[])
    assert r['ok'] and r['source'] == 'previous_qso' and r['grid'] == 'JN15XC'


def test_previous_qso_ignore_si_aucun_historique(monkeypatch):
    _reset()
    monkeypatch.setattr(clusters, 'lookup_hamqth', lambda call: None)
    monkeypatch.setattr(callbook, 'lookup_hamdb', lambda call: {'ok': False, 'error': 'Indicatif introuvable sur HamDB'})
    monkeypatch.setattr(logx_callhistory, 'lookup', lambda call, shared_log=None: None)
    r = callbook.lookup('ZZ9ZZZ', {}, shared_log=[])
    assert not r['ok']  # aucun filet : jamais croisé localement


def test_previous_qso_ne_prime_jamais_sur_un_resultat_reseau_positif(monkeypatch):
    _reset()
    monkeypatch.setattr(qrz, 'lookup', lambda call, user, pw: {'ok': True, 'call': call, 'name': 'X', 'grid': 'AA00AA'})
    monkeypatch.setattr(logx_callhistory, 'lookup',
                        lambda call, shared_log=None: {'call': call, 'dept': None,
                                                       'locator': 'JN15XC', 'qso_count': 3,
                                                       'last_date': '20260101', 'worked': True})
    r = callbook.lookup('F6KQJ', {'qrz_user': 'u', 'qrz_password': 'p'}, shared_log=[])
    assert r['ok'] and r['source'] == 'qrz'  # QRZ garde la priorité, pas previous_qso


def test_previous_qso_en_tete_si_disjoncteur_ouvert(monkeypatch):
    _reset()
    import time as _t
    callbook._circuit['until'] = _t.time() + 60   # disjoncteur ouvert (hors ligne simulé)
    reseau_appele = {'n': 0}
    monkeypatch.setattr(clusters, 'lookup_hamqth', lambda call: reseau_appele.update(n=reseau_appele['n'] + 1))
    monkeypatch.setattr(logx_callhistory, 'lookup',
                        lambda call, shared_log=None: {'call': call, 'dept': None,
                                                       'locator': 'JN15XC', 'qso_count': 1,
                                                       'last_date': '20260101', 'worked': True})
    r = callbook.lookup('F6ZZZ', {}, shared_log=[])
    assert r['ok'] and r['source'] == 'previous_qso'
    assert reseau_appele['n'] == 0   # jamais tenté : disjoncteur ouvert


def test_sans_shared_log_comportement_inchange(monkeypatch):
    """Rétrocompatibilité : les appelants qui ne passent pas shared_log
    (logx_departments.py) gardent le comportement d'avant ce correctif."""
    _reset()
    monkeypatch.setattr(clusters, 'lookup_hamqth', lambda call: None)
    monkeypatch.setattr(callbook, 'lookup_hamdb', lambda call: {'ok': False, 'error': 'Indicatif introuvable sur HamDB'})
    r = callbook.lookup('ZZ9ZZZ', {})   # pas de 3e argument
    assert not r['ok']


def test_enrich_unknown_calls_preserve_le_dept_existant(monkeypatch, tmp_path):
    calldb_path = str(tmp_path / 'calldb.json')
    with open(calldb_path, 'w', encoding='utf-8') as f:
        json.dump({'calls': {'F6KQJ': {'dept': '43'}}}, f)
    monkeypatch.setattr(clusters, 'lookup_hamqth',
                        lambda call: {'call': call, 'locator': 'JN15XC', 'country': 'France', 'continent': 'EU'})
    enriched = clusters.enrich_unknown_calls({'F6KQJ': {}}, calldb_path)
    assert enriched.get('F6KQJ', {}).get('locator') == 'JN15XC'
    with open(calldb_path, encoding='utf-8') as f:
        saved = json.load(f)
    entry = saved['calls']['F6KQJ']
    assert entry['dept'] == '43'          # PAS perdu
    assert entry['locator'] == 'JN15XC'   # bien ajouté
    assert entry['country'] == 'France'


# ─── RE-RÉSOLUTION EN MASSE ─────────────────────────────────────────────────
import logx_storage as storage


def _reset_bulk():
    callbook._bulk_state.update(running=False, done=0, total=0, updated=0,
                                 errors=0, started_at=None, finished_at=None)


def test_bulk_resolve_remplit_les_locators_vides(monkeypatch):
    _reset_bulk()
    log = [
        {'id': 1, 'call': 'F4ABC', 'locator': '', 'state': ''},
        {'id': 2, 'call': 'F4ABC', 'locator': '', 'state': ''},
    ]
    monkeypatch.setattr(storage, 'shared_log', log)
    calls_recus = []
    def fake_lookup(call, cfg, shared_log=None):
        calls_recus.append(call)
        return {'ok': True, 'grid': 'JN18XX', 'state': ''}
    monkeypatch.setattr(callbook, 'lookup', fake_lookup)
    monkeypatch.setattr(storage, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(storage, 'bump_log_version', lambda: None)

    callbook._bulk_resolve_run(lambda: {}, ids=None, overwrite=False)

    assert log[0]['locator'] == 'JN18XX' and log[1]['locator'] == 'JN18XX'
    # DÉDUPLIQUÉ par indicatif : 2 QSO du même call = UN seul appel réseau.
    assert calls_recus == ['F4ABC']
    st = callbook.bulk_resolve_status()
    assert st['updated'] == 2 and st['errors'] == 0 and not st['running']


def test_bulk_resolve_ne_touche_pas_un_locator_deja_rempli_sans_overwrite(monkeypatch):
    _reset_bulk()
    log = [{'id': 1, 'call': 'F4ABC', 'locator': 'JN99ZZ', 'state': ''}]
    monkeypatch.setattr(storage, 'shared_log', log)
    monkeypatch.setattr(callbook, 'lookup', lambda call, cfg, shared_log=None:
                        {'ok': True, 'grid': 'JN18XX', 'state': ''})
    monkeypatch.setattr(storage, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(storage, 'bump_log_version', lambda: None)

    callbook._bulk_resolve_run(lambda: {}, ids=None, overwrite=False)

    # QSO déjà résolu (locator ET state ni l'un ni l'autre vide n'existe ici,
    # mais locator seul suffit à le sortir de la cible par défaut) — un QSO
    # avec un locator réel n'a pas besoin d'écraser (state vide n'entre pas
    # en jeu tant que overwrite=False force le remplissage du champ manquant
    # SANS toucher au locator déjà bon).
    assert log[0]['locator'] == 'JN99ZZ'   # inchangé


def test_bulk_resolve_overwrite_remplace_une_valeur_existante(monkeypatch):
    _reset_bulk()
    log = [{'id': 1, 'call': 'F4ABC', 'locator': 'JN99ZZ', 'state': ''}]
    monkeypatch.setattr(storage, 'shared_log', log)
    monkeypatch.setattr(callbook, 'lookup', lambda call, cfg, shared_log=None:
                        {'ok': True, 'grid': 'JN18XX', 'state': ''})
    monkeypatch.setattr(storage, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(storage, 'bump_log_version', lambda: None)

    callbook._bulk_resolve_run(lambda: {}, ids=None, overwrite=True)

    assert log[0]['locator'] == 'JN18XX'   # écrasé, overwrite=True


def test_bulk_resolve_filtre_par_ids(monkeypatch):
    _reset_bulk()
    log = [
        {'id': 1, 'call': 'F4ABC', 'locator': '', 'state': ''},
        {'id': 2, 'call': 'F4XYZ', 'locator': '', 'state': ''},
    ]
    monkeypatch.setattr(storage, 'shared_log', log)
    monkeypatch.setattr(callbook, 'lookup', lambda call, cfg, shared_log=None:
                        {'ok': True, 'grid': 'JN18XX', 'state': ''})
    monkeypatch.setattr(storage, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(storage, 'bump_log_version', lambda: None)

    callbook._bulk_resolve_run(lambda: {}, ids=[1], overwrite=False)

    assert log[0]['locator'] == 'JN18XX'   # ciblé
    assert log[1]['locator'] == ''         # PAS dans la liste d'IDs, intact


def test_bulk_resolve_start_refuse_si_deja_en_cours(monkeypatch):
    _reset_bulk()
    monkeypatch.setattr(storage, 'shared_log', [])
    callbook._bulk_state['running'] = True
    ok, msg = callbook.bulk_resolve_start(lambda: {})
    assert not ok and 'cours' in msg
    _reset_bulk()


def test_bulk_resolve_echec_lookup_compte_en_erreur_sans_modifier(monkeypatch):
    _reset_bulk()
    log = [{'id': 1, 'call': 'F4ABC', 'locator': '', 'state': ''}]
    monkeypatch.setattr(storage, 'shared_log', log)
    monkeypatch.setattr(callbook, 'lookup', lambda call, cfg, shared_log=None:
                        {'ok': False, 'error': 'introuvable'})
    monkeypatch.setattr(storage, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(storage, 'bump_log_version', lambda: None)

    callbook._bulk_resolve_run(lambda: {}, ids=None, overwrite=False)

    assert log[0]['locator'] == ''
    st = callbook.bulk_resolve_status()
    assert st['updated'] == 0 and st['errors'] == 1
