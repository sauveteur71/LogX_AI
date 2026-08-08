# -*- coding: utf-8 -*-
"""Épuration de la page logbook : le menu DÉBUT / FIN.

DEMANDE UTILISATEUR : « le logbook a énormément d'icônes d'info qui d'ailleurs
souvent ne servent qu'à la fin d'un concours ou au début. Regarde comment
épurer cette page. »

COMPTÉ AVANT DE TRANCHER — c'est ce qui a décidé du découpage, pas un goût
personnel : 30 commandes dans la zone outils, dont 11 utilisées uniquement
AVANT ou APRÈS l'épreuve. Elles occupaient la moitié de la barre pendant tout
le trafic, alors qu'on les touche deux fois par concours.

TROIS DÉCISIONS :
  1. la barre ne garde que ce qu'on touche la main sur le manipulateur ;
  2. SCOPE, MUR et BANDES DISPARAISSENT sans remplacement — le menu
     DISPOSITION de la barre de statut fait déjà exactement cela, sur toutes
     les pages, avec les dispositions enregistrées ;
  3. le reste passe dans un menu unique, dont le contenu S'ADAPTE AU MODE :
     en logbook simple il n'y a ni règlement, ni score, ni log à soumettre —
     proposer EDI, VÉRIFIER ou ARCHIVER n'y a aucun sens.

Ce fichier exécute le VRAI logx_logbook.js dans V8, comme
tests/test_panneaux_multi_fenetres.py : on observe le menu réellement
construit, pas une relecture du source.
"""
import io
import json
import os
import re
import sys

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

JS = os.path.join(CONCOURS, 'logx_logbook.js')
HTML = os.path.join(CONCOURS, 'logx_logbook.html')
# EV-7 : openFilterBuilder/openDupFinder/openBulkResolve/openNetControl ont
# été extraites de logx_logbook.js vers ces fichiers (chargés en <script>
# classique dans logx_logbook.html, portée globale partagée) -- une entrée
# de menu qui les cible existe toujours réellement, juste plus dans CE
# fichier précis. Voir test_chaque_entree_du_menu_pointe_sur_une_fonction_REELLE.
JS_EXTRAITS_EV7 = [os.path.join(CONCOURS, n) for n in (
    'logx_filter_builder.js', 'logx_dup_finder.js',
    'logx_bulk_resolve.js', 'logx_net_control.js',
    'logx_rate_panel.js', 'logx_verif_panel.js',
    'logx_awards.js', 'logx_popout_selfspot.js',
    'logx_qtc.js', 'logx_import_adif.js',
    'logx_outils_autonomes.js', 'logx_scan_qsl.js', 'logx_hardware_cat.js',
    'logx_contest_picker.js', 'logx_dxcc_lookup.js', 'logx_qso_map.js',
    'logx_busted_call.js', 'logx_sstv_panel.js', 'logx_rtty_panel.js')]


def _lire_tout():
    """logx_logbook.js + tous les fichiers extraits par EV-7 -- une fonction
    du menu peut désormais vivre dans n'importe lequel (même portée globale,
    <script> classique, voir les en-têtes des fichiers extraits)."""
    return _lire(JS) + '\n'.join(_lire(p) for p in JS_EXTRAITS_EV7)


def _lire(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def _bloc_menu(src):
    """itemsMenuLogbook() extraite telle quelle, par comptage d'accolades."""
    deb = src.index('function itemsMenuLogbook(')
    ouv = src.index('{', deb)
    prof, i = 0, ouv
    while True:
        c = src[i]
        if c == '{':
            prof += 1
        elif c == '}':
            prof -= 1
            if prof == 0:
                return src[deb:i + 1]
        i += 1


def _items(concours):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval('function contestActif(){ return %s; }' % ('true' if concours else 'false'))
    ctx.eval(_bloc_menu(_lire(JS)))
    return json.loads(ctx.eval('JSON.stringify(itemsMenuLogbook())'))


def _fonctions(concours):
    out = []
    for _titre, items in _items(concours):
        out += [x[2] for x in items]
    return out


# ─── Le menu s'adapte au mode ────────────────────────────────────────────────

@pytest.mark.parametrize('fn', ['showChecklist', 'showValidation', 'exportEDI',
                                'archiveLog', 'exportON4KST'])
def test_LES_COMMANDES_DE_CONCOURS_SONT_ABSENTES_en_logbook_simple(fn):
    """Il n'y a ni règlement, ni score, ni log à soumettre : les proposer
    n'égarerait que l'utilisateur."""
    assert fn not in _fonctions(concours=False), fn


@pytest.mark.parametrize('fn', ['showChecklist', 'showValidation', 'exportEDI',
                                'archiveLog', 'exportON4KST'])
def test_elles_sont_bien_la_en_concours(fn):
    assert fn in _fonctions(concours=True), fn


@pytest.mark.parametrize('fn', ['triggerImport', 'showRatePanel', 'showAwards',
                                'exportADIF', 'exportCSV', 'backupNow', 'resetLog'])
def test_ce_qui_sert_TOUJOURS_est_la_dans_les_deux_cas(fn):
    """Un log personnel s'exporte, se sauvegarde et compte des diplômes tout
    autant qu'un log de concours."""
    assert fn in _fonctions(concours=False), fn
    assert fn in _fonctions(concours=True), fn


def test_le_menu_de_concours_est_STRICTEMENT_plus_riche():
    sans, avec = set(_fonctions(False)), set(_fonctions(True))
    assert sans < avec, (sans - avec)


# ─── Rien n'a été perdu au passage ───────────────────────────────────────────

TOUTES = ['showChecklist', 'triggerImport', 'showRatePanel', 'showAwards',
          'showValidation', 'exportEDI', 'exportADIF', 'exportCSV',
          'archiveLog', 'backupNow', 'exportON4KST', 'resetLog']


@pytest.mark.parametrize('fn', TOUTES)
def test_AUCUNE_COMMANDE_N_A_DISPARU_du_logiciel(fn):
    """Épurer ne doit pas amputer : chaque commande retirée de la barre reste
    atteignable par le menu, et sa fonction existe toujours."""
    assert fn in _fonctions(concours=True), fn
    assert 'function %s(' % fn in _lire_tout(), fn


def test_chaque_entree_du_menu_pointe_sur_une_fonction_REELLE():
    """Le menu appelle window[nom] : une faute de frappe donnerait un bouton
    parfaitement dessiné qui ne fait rien. La fonction peut vivre dans
    logx_logbook.js OU dans l'un des fichiers extraits par EV-7 (même portée
    globale, voir JS_EXTRAITS_EV7 ci-dessus)."""
    src = _lire_tout()
    for fn in _fonctions(concours=True):
        assert 'function %s(' % fn in src, fn


# ─── La barre est réellement allégée ─────────────────────────────────────────

def _commandes_barre():
    s = re.sub(r'<script.*?</script>|<!--.*?-->', '', _lire(HTML), flags=re.S)
    i = s.find('Rechercher indicatif')
    bloc = s[max(0, i - 2500): i + 4000]
    return {m.group(1) for m in re.finditer(r'<button[^>]*onclick="([^"(]+)', bloc)}


def test_LA_BARRE_EST_PASSEE_SOUS_LA_MOITIE():
    """Mesure, pas impression : 30 commandes avant."""
    assert len(_commandes_barre()) <= 15, sorted(_commandes_barre())


@pytest.mark.parametrize('fn', ['exportEDI', 'exportADIF', 'exportCSV',
                                'archiveLog', 'backupNow', 'resetLog',
                                'showRatePanel', 'showAwards', 'showValidation',
                                'showChecklist', 'triggerImport'])
def test_les_commandes_de_debut_et_de_fin_ONT_QUITTE_la_barre(fn):
    assert fn not in _commandes_barre(), fn


@pytest.mark.parametrize('fn', ['popoutWall', 'popoutBandes'])
def test_les_fenetres_detachees_ont_quitte_la_barre(fn):
    """Le menu DISPOSITION de la barre de statut fait déjà cela sur toutes les
    pages, avec les dispositions enregistrées : trois boutons de moins sans
    rien perdre."""
    assert fn not in _commandes_barre(), fn


def test_le_bouton_du_menu_EXISTE_dans_la_page():
    """Sans lui, tout ce qui précède serait devenu inatteignable."""
    assert 'toggleLbMenu' in _commandes_barre()
    assert 'id="lbMenuDD"' in _lire(HTML)


def test_ce_qui_sert_PENDANT_le_trafic_est_reste():
    barre = _commandes_barre()
    for fn in ('setFilter', 'toggleMapView', 'selfSpot', 'showQTCPanel'):
        assert fn in barre, fn


# ─── Garde-fous du banc d'essai ──────────────────────────────────────────────

def test_l_extraction_du_bloc_est_bien_le_vrai_code():
    bloc = _bloc_menu(_lire(JS))
    assert 'contestActif()' in bloc
    assert 'AVANT LA SESSION' in bloc and 'APRÈS LA SESSION' in bloc


def test_le_menu_n_est_jamais_vide():
    for concours in (True, False):
        assert len(_fonctions(concours)) >= 6, concours
