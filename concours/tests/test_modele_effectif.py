# -*- coding: utf-8 -*-
"""modele_effectif : le modèle Anthropic 'claude-sonnet-4-6' n'existe pas (l'API
renvoie 400). Le Sonnet réel est 'claude-sonnet-5'. On vérifie que le défaut est
correct ET qu'une config existante figée sur l'ancien ID est auto-réparée (alias),
sans casser le choix explicite d'un autre palier (Opus/Haiku)."""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

from logx_utils import modele_effectif, MODELE_DEFAUT  # noqa: E402


def test_defaut_anthropic_est_un_modele_valide():
    # 'claude-sonnet-4-6' est invalide (400 API) — le défaut doit être Sonnet 5.
    assert MODELE_DEFAUT['anthropic'] == 'claude-sonnet-5'
    assert modele_effectif('anthropic') == 'claude-sonnet-5'


def test_config_figee_sur_ancien_id_est_auto_reparee():
    # Un opérateur avait 'claude-sonnet-4-6' enregistré : ne PAS le renvoyer tel
    # quel (sinon 400 garanti), le remapper vers l'ID courant.
    assert modele_effectif('anthropic', configure='claude-sonnet-4-6') == 'claude-sonnet-5'
    assert modele_effectif('anthropic', demande='claude-sonnet-4-6') == 'claude-sonnet-5'


def test_choix_explicite_dun_palier_preserve():
    # Un appelant peut viser Opus/Haiku (même famille anthropic) : on l'honore.
    assert modele_effectif('anthropic', demande='claude-opus-4-8') == 'claude-opus-4-8'
    assert modele_effectif('anthropic', configure='claude-haiku-4-5-20251001') == 'claude-haiku-4-5-20251001'


def test_autre_fournisseur_intact():
    # La normalisation Anthropic ne doit pas toucher les autres fournisseurs.
    assert modele_effectif('gemini') == MODELE_DEFAUT['gemini']
