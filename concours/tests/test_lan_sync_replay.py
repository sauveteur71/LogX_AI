# -*- coding: utf-8 -*-
"""Synchro LAN — preuve de découverte anti-rejeu (audit 22/08 logx_lan_sync.py:100,
re-vérifié vivant le 26/08). Avant : la preuve = HMAC(jeton, message CONSTANT) =
valeur fixe diffusée en clair -> quiconque sniffe le beacon la REJOUE et se fait
enregistrer comme pair. Le HMAC (obs 277) empêche de retrouver le jeton, PAS le
rejeu.

Correctif : preuve HORODATÉE (HMAC sur un message incluant le créneau de 30 s).
La preuve tourne ; une preuve sniffée expire. À la réception on accepte le
créneau courant ±1 (tolérance d'horloge). Fenêtre de rejeu ramenée de « pour
toujours » à ~30-60 s."""
import json
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_lan_sync as lan   # noqa: E402

CFG = {'lan_sync_token': 'secret-equipe'}
NOW = 1_000_000.0             # instant fixe -> créneau déterministe


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(lan, '_my_iid', lambda: 'MOI')
    with lan._peers_lock:
        lan._peers.clear()
    yield
    with lan._peers_lock:
        lan._peers.clear()


def _creneau(t):
    return int(t // lan._FENETRE_S)


def _beacon(token, iid='AUTRE', port=8080):
    return json.dumps({'logx': 1, 'iid': iid, 'http_port': port,
                       'call': 'F4ABC', 'token': token}).encode()


def test_preuve_du_creneau_courant_acceptee():
    proof = lan._discovery_proof(CFG, _creneau(NOW))
    attendus = lan._proofs_acceptables(CFG, maintenant=NOW)
    lan.note_beacon('192.168.1.5', _beacon(proof), expected_token=attendus)
    assert len(lan.peers()) == 1


def test_preuve_creneau_adjacent_toleree():
    # ±1 créneau : léger décalage d'horloge entre postes -> toujours accepté.
    proof_prec = lan._discovery_proof(CFG, _creneau(NOW) - 1)
    proof_suiv = lan._discovery_proof(CFG, _creneau(NOW) + 1)
    attendus = lan._proofs_acceptables(CFG, maintenant=NOW)
    lan.note_beacon('192.168.1.6', _beacon(proof_prec, iid='A1'), expected_token=attendus)
    lan.note_beacon('192.168.1.7', _beacon(proof_suiv, iid='A2'), expected_token=attendus)
    assert len(lan.peers()) == 2


def test_preuve_ancienne_rejouee_refusee():
    # LE fix : une preuve sniffée il y a plus d'un créneau (>~1 min) et rejouée
    # n'est plus acceptée.
    proof_vieux = lan._discovery_proof(CFG, _creneau(NOW) - 2)
    attendus = lan._proofs_acceptables(CFG, maintenant=NOW)
    lan.note_beacon('192.168.1.8', _beacon(proof_vieux), expected_token=attendus)
    assert lan.peers() == []


def test_mauvais_jeton_refuse():
    faux = lan._discovery_proof({'lan_sync_token': 'pas-le-bon'}, _creneau(NOW))
    attendus = lan._proofs_acceptables(CFG, maintenant=NOW)
    lan.note_beacon('192.168.1.9', _beacon(faux), expected_token=attendus)
    assert lan.peers() == []


def test_sans_jeton_reste_ouvert():
    # Aucun jeton configuré : LAN de confiance, on accepte tout (comportement
    # historique inchangé).
    attendus = lan._proofs_acceptables({}, maintenant=NOW)   # ensemble vide
    lan.note_beacon('192.168.1.10', _beacon('peu-importe'), expected_token=attendus)
    assert len(lan.peers()) == 1


def test_beacon_emis_est_du_creneau_courant():
    # L'émetteur met bien la preuve du créneau courant -> un récepteur à l'heure
    # l'accepte (bout en bout, sans rejeu).
    import logx_lan_sync as lan2
    beacon = lan2._my_beacon(CFG)          # utilise le créneau courant réel
    token = json.loads(beacon)['token']
    attendus = lan2._proofs_acceptables(CFG)   # maintenant = réel
    lan2.note_beacon('192.168.1.11', _beacon(token, iid='PAIR'), expected_token=attendus)
    assert len(lan2.peers()) == 1
