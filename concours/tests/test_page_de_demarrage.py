# -*- coding: utf-8 -*-
"""Sur quelle page le navigateur s'ouvre-t-il au lancement ?

DEMANDE UTILISATEUR : « à chaque ouverture la page configuration s'ouvre
inutilement, la configuration se fait à la première utilisation ? »

C'était exact. logx_bootstrap.start_network_diagnosis() envoyait le navigateur
sur `/logx_configuration.html` À CHAQUE DÉMARRAGE, sans jamais regarder si la
station était déjà réglée. Une fois l'indicatif saisi — une fois pour toutes —
la page utile est le LOGBOOK, celle où l'on trafique.

POURQUOI L'INDICATIF ET PAS LA PRÉSENCE DU FICHIER : `.server_config.json` est
créé dès la PREMIÈRE sauvegarde, même partielle (un changement de thème ou de
langue suffit). Tester son existence ferait croire à une station configurée
alors que rien d'essentiel n'a été renseigné, et enverrait un nouvel
utilisateur droit sur un logbook inutilisable.
"""
import json
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_bootstrap as boot   # noqa: E402

CONFIG = '/logx_configuration.html'
LOGBOOK = '/logx_logbook.html'


def _ecrire(dossier, contenu):
    p = os.path.join(str(dossier), boot.SERVER_CONFIG_FILE)
    with open(p, 'w', encoding='utf-8') as f:
        if isinstance(contenu, str):
            f.write(contenu)
        else:
            json.dump(contenu, f)
    return p


# ─── Première utilisation ────────────────────────────────────────────────────

def test_SANS_config_on_ouvre_la_page_CONFIG(tmp_path):
    """Premier lancement : il n'y a rien à faire d'autre que se configurer."""
    assert boot.page_de_demarrage(str(tmp_path)) == CONFIG


def test_un_fichier_de_config_SANS_indicatif_reste_une_premiere_utilisation(tmp_path):
    """Le fichier existe dès qu'un réglage quelconque a été sauvegardé — un
    thème, une langue. Ça ne veut pas dire que la station est réglée."""
    _ecrire(tmp_path, {'ui_theme': 'day', 'rc_lang': 'de'})
    assert boot.page_de_demarrage(str(tmp_path)) == CONFIG


@pytest.mark.parametrize('valeur', ['', '   ', None])
def test_un_indicatif_vide_ne_compte_pas(tmp_path, valeur):
    _ecrire(tmp_path, {'callsign': valeur})
    assert boot.page_de_demarrage(str(tmp_path)) == CONFIG


# ─── Utilisations suivantes ──────────────────────────────────────────────────

def test_AVEC_un_indicatif_on_ouvre_LE_LOGBOOK(tmp_path):
    """Le cœur de la demande : ne plus imposer CONFIG à chaque démarrage."""
    _ecrire(tmp_path, {'callsign': 'F4GLD'})
    assert boot.page_de_demarrage(str(tmp_path)) == LOGBOOK


def test_un_indicatif_entoure_d_espaces_compte_quand_meme(tmp_path):
    _ecrire(tmp_path, {'callsign': '  F4GLD/P  '})
    assert boot.page_de_demarrage(str(tmp_path)) == LOGBOOK


# ─── Robustesse : jamais d'exception au démarrage ────────────────────────────
# Cette fonction tourne dans le fil d'amorçage : une exception y empêcherait le
# navigateur de s'ouvrir du tout, sur un fichier abîmé que l'utilisateur ne
# peut ni voir ni réparer.

@pytest.mark.parametrize('contenu', [
    '{ pas du json',
    '',
    '[]',            # JSON valide mais pas un objet
    '"F4GLD"',       # une chaîne, pas un objet
    'null',
])
def test_un_fichier_ABIME_retombe_sur_CONFIG_sans_lever(tmp_path, contenu):
    _ecrire(tmp_path, contenu)
    assert boot.page_de_demarrage(str(tmp_path)) == CONFIG


def test_un_dossier_inexistant_ne_leve_pas():
    assert boot.page_de_demarrage(os.path.join(os.sep, 'dossier', 'qui',
                                               'nexiste', 'pas')) == CONFIG


def test_un_callsign_non_textuel_ne_leve_pas(tmp_path):
    """Une config bricolée à la main peut contenir n'importe quoi."""
    for v in (42, {'x': 1}, ['F4GLD']):
        _ecrire(tmp_path, {'callsign': v})
        assert boot.page_de_demarrage(str(tmp_path)) in (CONFIG, LOGBOOK)


# ─── Le câblage ──────────────────────────────────────────────────────────────

def test_l_ouverture_du_navigateur_passe_par_page_de_demarrage():
    """Sans ça, la fonction pourrait être parfaite et n'être appelée par
    personne — l'adresse en dur resterait dans le code d'amorçage."""
    with open(os.path.join(CONCOURS, 'logx_bootstrap.py'), encoding='utf-8') as f:
        src = f.read()
    bloc = src[src.index('def start_network_diagnosis('):]
    bloc = bloc[:bloc.index('\ndef ', 1)]
    assert 'page_de_demarrage()' in bloc
    assert 'logx_configuration.html' not in bloc, (
        "adresse en dur : le navigateur retournerait sur CONFIG a chaque fois")


def test_la_console_annonce_la_meme_page_que_celle_ouverte():
    """Deux vérités différentes seraient pires que l'ancien comportement :
    l'utilisateur verrait le logbook s'ouvrir pendant que la console lui dit
    d'aller sur CONFIG."""
    with open(os.path.join(CONCOURS, 'logx_serveur.py'), encoding='utf-8') as f:
        src = f.read()
    assert 'station_deja_configuree()' in src
