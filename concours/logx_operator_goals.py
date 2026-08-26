# -*- coding: utf-8 -*-
"""Profil d'OBJECTIFS opérateur pour la CHASSE : quels crédits comptent pour
CET opérateur (nouvelle entité DXCC, nouvelle bande, nouveau mode, confirmation
LoTW, carré VUCC). F4GLD, 25/08/2026 : « ne donnez pas une priorité
universelle… proposez un profil opérateur ».

Stockage DÉDIÉ (fichier JSON isolé de `.server_config.json`) : un bug ici ne
peut PAS corrompre la config principale. Le moteur (`logx_chasse_priorite` via
`logx_awards.annoter_credit`) et l'interface CHASSE lisent/écrivent LA MÊME
vérité par ce module — une seule source, jamais deux.

Défaut : tous les objectifs ACTIFS = comportement historique (aucun crédit
annulé tant que l'opérateur n'a rien réglé)."""
import json
import threading

# Fichier dédié, à côté de .server_config.json (chemin relatif au cwd du
# serveur, même convention que SERVER_CONFIG_FILE).
FICHIER = '.operator_goals.json'

# Les 5 objectifs, alignés EXACTEMENT sur les clés que
# logx_chasse_priorite._OBJECTIF_POUR_CLASSE associe à ses classes de crédit
# (atno->dxcc, new_band->dxcc_new_band, new_mode->dxcc_new_mode,
# needed_confirm->lotw_confirmation_priority, new_grid->vucc). Un test
# structurel garde cet alignement.
CLES = ('dxcc', 'dxcc_new_band', 'dxcc_new_mode', 'lotw_confirmation_priority', 'vucc')
DEFAUTS = {k: True for k in CLES}

_lock = threading.Lock()


def normaliser(brut):
    """Ne garde que les clés connues, en booléens ; complète les absentes au
    défaut (True). Toute entrée douteuse (non-dict, clé inconnue) est ignorée —
    jamais d'exception, jamais de clé parasite écrite sur disque."""
    out = dict(DEFAUTS)
    if isinstance(brut, dict):
        for k in CLES:
            if k in brut:
                out[k] = bool(brut[k])
    return out


def charger():
    """Objectifs persistés, complétés par les défauts. Fichier absent ou
    illisible -> tous actifs (comportement historique). Ne lève jamais."""
    try:
        with open(FICHIER, encoding='utf-8') as f:
            return normaliser(json.load(f))
    except (OSError, ValueError):
        return dict(DEFAUTS)


def enregistrer(brut):
    """Valide (normaliser) puis écrit ATOMIQUEMENT (isolé du reste). Retourne
    l'état réellement écrit — c'est lui que l'UI ré-affiche."""
    import logx_storage
    goals = normaliser(brut)
    logx_storage.save_json_atomic(FICHIER, goals, lock=_lock)
    return goals
