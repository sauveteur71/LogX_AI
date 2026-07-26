# -*- coding: utf-8 -*-
"""Unicité des id de QSO : le préjudice, et le chemin qui l'évite.

test_import_adif.py couvre déjà l'allocation côté import. Ce fichier-ci couvre
les deux angles qui restaient sans test DIRECT :

  1. POURQUOI un id dupliqué est grave — /log/delete filtre
     `[q for q in shared_log if q.get('id') != qso_id]`, donc il efface TOUS
     les porteurs de l'id, en répondant {'ok': True}. C'est une perte de QSO
     silencieuse, pas une erreur visible. Sans ce test, on protège un invariant
     sans jamais avoir démontré ce qu'il protège.

  2. reserve_qso_id_locked() vis-à-vis d'un id PROPOSÉ : les pages client
     envoient `id: Date.now()` (horloge du téléphone pour logx_mobile) et
     logx_cloudsync réinsère les QSO d'un autre poste EN CONSERVANT leur id,
     qui est son identité de fusion. Il faut donc les deux comportements à la
     fois : conserver un id proposé LIBRE (sinon les suppressions ne se
     propagent plus entre postes), remplacer un id proposé DÉJÀ PRIS.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_storage as storage  # noqa: E402


def _supprimer_par_id(log, qso_id):
    """Reproduit EXACTEMENT le filtre de /log/delete (logx_http.py) : c'est ce
    comportement-là qui rend une collision d'id destructrice."""
    return [q for q in log if q.get('id') != qso_id]


def test_supprimer_un_qso_en_efface_deux_si_les_id_collisionnent():
    """Démonstration du préjudice, sans le correctif : deux QSO de même id, on
    en supprime un, les deux disparaissent. C'est ce que l'ancien code pouvait
    produire après un import ADIF."""
    log = [{'id': 1000, 'call': 'F4GLD'}, {'id': 1000, 'call': 'VK9DX'}]
    assert _supprimer_par_id(log, 1000) == []


def test_deux_qso_alloues_ne_collisionnent_donc_pas_a_la_suppression(monkeypatch):
    """Le même scénario en passant par l'allocateur : la suppression de l'un
    laisse l'autre intact."""
    monkeypatch.setattr(storage, 'deleted_qsos', [], raising=False)
    log = []
    for indicatif in ('F4GLD', 'VK9DX'):
        (nouvel_id,) = storage.allocate_qso_ids_locked(1, log)
        log.append({'id': nouvel_id, 'call': indicatif})

    assert len({q['id'] for q in log}) == 2
    restant = _supprimer_par_id(log, log[0]['id'])
    assert [q['call'] for q in restant] == ['VK9DX']


def test_id_propose_libre_est_conserve(monkeypatch):
    """Identité inter-postes : Cloud Sync réinsère un QSO distant avec son id
    d'origine. Le réattribuer ferait diverger l'identité d'un même QSO d'un
    poste à l'autre, et les tombstones ne s'apparieraient plus."""
    monkeypatch.setattr(storage, 'deleted_qsos', [], raising=False)
    log = [{'id': 1_700_000_000_000, 'call': 'F4GLD'}]
    propose = 1_700_000_000_042          # libre, venu d'un autre poste

    assert storage.reserve_qso_id_locked(propose, log) == propose


def test_id_propose_deja_pris_est_remplace(monkeypatch):
    """Le cas du défaut : un client propose un id que porte déjà un QSO
    importé. On alloue autre chose plutôt que de créer deux porteurs."""
    monkeypatch.setattr(storage, 'deleted_qsos', [], raising=False)
    pris = 1_700_000_000_000
    log = [{'id': pris, 'call': 'F4GLD'}]

    obtenu = storage.reserve_qso_id_locked(pris, log)
    assert obtenu != pris
    assert obtenu not in {q['id'] for q in log}


def test_un_id_supprime_n_est_jamais_recycle(monkeypatch):
    """logx_cloudsync bloque le ré-import d'un id présent dans ses tombstones :
    réattribuer l'id d'un QSO supprimé ferait silencieusement rejeter le
    nouveau QSO par les autres postes."""
    supprime = {'id': 1_800_000_000_000, 'call': 'VK9DX'}
    monkeypatch.setattr(storage, 'deleted_qsos', [supprime], raising=False)

    (nouvel_id,) = storage.allocate_qso_ids_locked(1, [], now_ms=1_700_000_000_000)
    assert nouvel_id != supprime['id']
    assert nouvel_id > supprime['id'], "l'allocateur doit passer au-dessus des tombstones"
