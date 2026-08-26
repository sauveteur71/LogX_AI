# -*- coding: utf-8 -*-
"""Net Control (contrôle de réseau dirigé) — modèle serveur, tranche 1.

Trou identifié par la veille concurrentielle (docs/veille/opslog.md) : fort
levier sur le marché francophone (réseaux de clubs). Ce module gère la partie
DURABLE (réseaux + répertoire) et la logique PURE de la file de passage du
micro. Le branchement UI (maquette #306) et le log dans le carnet unique
viennent aux tranches suivantes.

Tests unitaires purs (data -> data), sans I/O disque : chaque fonction CRUD est
une transformation testable, comme le patron de logx_operator_goals (#292)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_net_control as nc


# ── Normalisation ────────────────────────────────────────────────────────
def test_normaliser_membre_met_le_call_en_majuscules_et_complete():
    m = nc.normaliser_membre({'call': ' f5abc ', 'nom': 'Jean'})
    assert m['call'] == 'F5ABC'
    assert m['nom'] == 'Jean'
    assert m['qth'] == '' and m['locator'] == ''   # champs complétés


def test_normaliser_membre_sans_call_est_rejete():
    assert nc.normaliser_membre({'nom': 'sans call'}) is None
    assert nc.normaliser_membre('pas un dict') is None


def test_normaliser_structure_top_level_toujours_dict_nets_liste():
    assert nc.normaliser(None) == {'nets': []}
    assert nc.normaliser({'nets': 'pas une liste'}) == {'nets': []}
    assert nc.normaliser({'nets': [{'nom': 'X'}]})['nets'][0]['nom'] == 'X'


# ── CRUD réseaux ─────────────────────────────────────────────────────────
def test_creer_net_attribue_un_id_unique_croissant():
    data = {'nets': []}
    data, a = nc.creer_net(data, nom='Dimanche', freq='3.650', mode='LSB', bande='80m')
    data, b = nc.creer_net(data, nom='Départemental')
    assert a['id'] != b['id']
    assert b['id'] > a['id']
    assert a['nom'] == 'Dimanche' and a['freq'] == '3.650' and a['mode'] == 'LSB'
    assert len(data['nets']) == 2


def test_supprimer_net_retire_le_bon():
    data = {'nets': []}
    data, a = nc.creer_net(data, nom='A')
    data, b = nc.creer_net(data, nom='B')
    data = nc.supprimer_net(data, a['id'])
    ids = [n['id'] for n in data['nets']]
    assert a['id'] not in ids and b['id'] in ids


# ── CRUD répertoire (roster) ─────────────────────────────────────────────
def test_ajouter_membre_au_repertoire():
    data = {'nets': []}
    data, net = nc.creer_net(data, nom='A')
    data = nc.ajouter_membre(data, net['id'], {'call': 'f5abc', 'nom': 'Jean'})
    roster = nc.trouver_net(data, net['id'])['roster']
    assert len(roster) == 1 and roster[0]['call'] == 'F5ABC'


def test_ajouter_membre_dedupe_par_indicatif():
    data = {'nets': []}
    data, net = nc.creer_net(data, nom='A')
    data = nc.ajouter_membre(data, net['id'], {'call': 'F5ABC', 'nom': 'Jean'})
    data = nc.ajouter_membre(data, net['id'], {'call': 'f5abc', 'qth': 'Lyon'})  # même call
    roster = nc.trouver_net(data, net['id'])['roster']
    assert len(roster) == 1                    # pas de doublon
    assert roster[0]['qth'] == 'Lyon'          # la nouvelle info met à jour


def test_ajouter_membre_sans_call_valide_ne_casse_rien():
    data = {'nets': []}
    data, net = nc.creer_net(data, nom='A')
    data = nc.ajouter_membre(data, net['id'], {'nom': 'sans call'})
    assert nc.trouver_net(data, net['id'])['roster'] == []


def test_retirer_membre():
    data = {'nets': []}
    data, net = nc.creer_net(data, nom='A')
    data = nc.ajouter_membre(data, net['id'], {'call': 'F5ABC'})
    data = nc.ajouter_membre(data, net['id'], {'call': 'F6DEF'})
    data = nc.retirer_membre(data, net['id'], 'f5abc')   # insensible à la casse
    calls = [m['call'] for m in nc.trouver_net(data, net['id'])['roster']]
    assert calls == ['F6DEF']


# ── Logique PURE de la file de passage du micro ──────────────────────────
def test_mettre_a_l_air_puis_ordre_de_passage():
    s = {'on_air': [], 'logged': []}
    s = nc.mettre_a_l_air(s, 'f5abc')
    s = nc.mettre_a_l_air(s, 'F6DEF')
    s = nc.mettre_a_l_air(s, 'F5ABC')          # déjà à l'air (casse) -> pas de doublon
    assert s['on_air'] == ['F5ABC', 'F6DEF']   # ordre d'arrivée, call normalisé


def test_passer_au_suivant_fait_tourner_la_file():
    s = {'on_air': ['F5ABC', 'F6DEF', 'F4GHI'], 'logged': []}
    s = nc.passer_au_suivant(s)
    assert s['on_air'] == ['F6DEF', 'F4GHI', 'F5ABC']   # l'actuel repart en fin


def test_loguer_courant_retire_de_la_file_et_empile_dans_logged():
    s = {'on_air': ['F5ABC', 'F6DEF'], 'logged': []}
    s = nc.loguer_courant(s)
    assert s['on_air'] == ['F6DEF']            # F5ABC quitte la file (au micro suivant)
    assert s['logged'] == ['F5ABC']


def test_loguer_courant_sur_file_vide_ne_casse_rien():
    s = {'on_air': [], 'logged': ['F5ABC']}
    s = nc.loguer_courant(s)
    assert s['on_air'] == [] and s['logged'] == ['F5ABC']
