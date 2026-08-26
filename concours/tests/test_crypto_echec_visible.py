# -*- coding: utf-8 -*-
"""Audit BASSE 612 : quand le chiffrement d'un secret ÉCHOUE (lib présente mais
AESGCM/clé en erreur), encrypt() écrit le secret EN CLAIR et ne le signalait que
par un print stdout — invisible pour l'opérateur.

Décision F4GLD : garder l'écriture (ne jamais casser la sauvegarde) MAIS rendre
l'échec VISIBLE. encrypt_config() mémorise l'échec ; echec_chiffrement_recent()
l'expose, et /config/save le remonte à l'UI (testé séparément côté HTTP).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_crypto as crypto


def test_echec_chiffrement_est_memorise_et_secret_reste_ecrit(monkeypatch):
    crypto.reset_key_cache()
    # Force un vrai échec de chiffrement (lib « présente », mais la clé lève).
    monkeypatch.setattr(crypto, 'HAS_CRYPTOGRAPHY', True)
    monkeypatch.setattr(crypto, '_load_or_create_key',
                        lambda: (_ for _ in ()).throw(RuntimeError('clé illisible')))
    out = crypto.encrypt_config({'qrz_password': 'motdepasse'})
    # 1) La sauvegarde n'est pas cassée : le secret est écrit (en clair ici).
    assert out['qrz_password'] == 'motdepasse'
    # 2) L'échec est mémorisé et récupérable pour être rendu visible.
    assert crypto.echec_chiffrement_recent(), "l'échec de chiffrement doit être signalé"


def test_pas_d_echec_signale_apres_config_sans_secret(monkeypatch):
    crypto.reset_key_cache()
    monkeypatch.setattr(crypto, 'HAS_CRYPTOGRAPHY', True)
    monkeypatch.setattr(crypto, '_load_or_create_key',
                        lambda: (_ for _ in ()).throw(RuntimeError('ne doit pas être appelé')))
    # Aucun champ secret -> encrypt() jamais appelé -> aucun échec signalé.
    crypto.encrypt_config({'callsign': 'F4TEST'})
    assert crypto.echec_chiffrement_recent() is None
