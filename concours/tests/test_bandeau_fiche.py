# -*- coding: utf-8 -*-
"""Fiche « spot » au clic sur le bandeau (logx_bandeau_fiche.js), généralisée à
accueil + logbook (CHASSE a sa propre fiche intégrée -> module PAS chargé là).

Corrige le bug F4GLD 03/09/2026 : sans interception, le clic suivait le href de
repli et faisait « Quitter le site » -> navigation vers CHASSE. Attendu : fiche
sur place + bouton QSY.

MÉTHODE DU DÉPÔT :
  - logique PURE (homeCall) testée en V8, avec un DOM minimal stubé (le module
    est une IIFE qui exige #bandeaux avant de s'exposer) ;
  - le reste = STRUCTURE du câblage (pas une simple présence de chaîne), après
    DÉPOUILLAGE DES COMMENTAIRES (sinon l'ordre serait faussé par les pavés
    explicatifs qui nomment preventDefault/QSY avant le code) ;
  - un TÉMOIN vérifie que le module s'expose bien : sinon les tests V8
    passeraient sur du vide.
"""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(CONCOURS, 'logx_bandeau_fiche.js')
PAGES = ['logx_accueil.html', 'logx_logbook.html']


def _src(nom):
    with open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        return f.read()


def _sans_commentaires(txt):
    sans_bloc = re.sub(r'/\*.*?\*/', ' ', txt, flags=re.S)
    return '\n'.join(l for l in sans_bloc.split('\n')
                     if not l.strip().startswith('//'))


# ── V8 : DOM minimal pour que l'IIFE s'exécute et expose LogxBandeauFiche ─────

def _ctx():
    py_mini_racer = pytest.importorskip('py_mini_racer')
    ctx = py_mini_racer.MiniRacer()
    # #bandeaux doit exister (sinon l'IIFE fait `return` AVANT d'exposer). On
    # stube juste ce que l'IIFE touche AU CHARGEMENT (getElementById +
    # addEventListener) — fetch/injecterStyle ne sont appelés qu'au clic.
    ctx.eval("""
      var window = {};
      function _el(){ return { style:{}, addEventListener:function(){},
        appendChild:function(){}, insertBefore:function(){},
        setAttribute:function(){}, firstChild:null }; }
      var document = { getElementById:function(){ return _el(); },
        addEventListener:function(){}, createElement:function(){ return _el(); },
        head:_el(), body:_el() };
    """)
    with open(MODULE, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_temoin_le_module_s_expose():
    """Anti-vacant : si l'IIFE ne s'exposait pas (return prématuré, renommage),
    les tests homeCall ci-dessous passeraient sur `undefined`. Ce témoin ROUGIT
    d'abord dans ce cas."""
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxBandeauFiche") == 'object'
    assert ctx.eval("typeof window.LogxBandeauFiche.homeCall") == 'function'


def test_homeCall_prefixe_et_suffixe_portable():
    """homeCall doit rendre l'indicatif de BASE, que le '/' porte un suffixe
    (DL1ABC/P) ou un préfixe (VP8/DL1ABC) — un split('/')[0] naïf renverrait le
    préfixe 'VP8'."""
    ctx = _ctx()
    assert ctx.eval("window.LogxBandeauFiche.homeCall('DL1ABC/P')") == 'DL1ABC'
    assert ctx.eval("window.LogxBandeauFiche.homeCall('VP8/DL1ABC')") == 'DL1ABC'
    assert ctx.eval("window.LogxBandeauFiche.homeCall('F4GLD')") == 'F4GLD'


# ── Câblage dans les pages ───────────────────────────────────────────────────

def test_les_deux_pages_chargent_le_module():
    """accueil ET logbook doivent charger le module (sinon leur clic bandeau
    retombe sur la navigation qui a produit le bug). CHASSE, elle, ne doit PAS
    le charger (double handler = double popup)."""
    for nom in PAGES:
        assert 'src="logx_bandeau_fiche.js"' in _src(nom), \
            nom + " ne charge pas logx_bandeau_fiche.js"
    assert 'src="logx_bandeau_fiche.js"' not in _src('logx_chasse.html'), \
        "CHASSE ne doit PAS charger le module (elle a sa propre fiche intégrée)"


# ── Structure du handler : intercepte, empêche la navigation, ouvre ──────────

def test_clic_intercepte_item_actif_et_empeche_navigation():
    """Le CŒUR du correctif : un écouteur de clic délégué qui vise les items
    ACTIFS (a.rcb-item[data-fiche]) et appelle preventDefault AVANT d'ouvrir la
    fiche — sans ça, le navigateur suit le href de repli (bug « Quitter »)."""
    src = _sans_commentaires(_src('logx_bandeau_fiche.js'))
    assert "addEventListener('click'" in src, "aucun écouteur de clic délégué"
    assert "closest('a.rcb-item[data-fiche]')" in src, \
        "le handler ne cible pas les items ACTIFS (a.rcb-item[data-fiche])"
    i_cible = src.index("closest('a.rcb-item[data-fiche]')")
    i_prevent = src.index('preventDefault')
    i_ouvrir = src.index('ouvrir({')   # l'APPEL (ouvrir({...}) ), pas la def `function ouvrir(d){`
    assert i_cible < i_prevent < i_ouvrir, (
        "ordre attendu : cibler l'item -> preventDefault (bloquer la navigation) "
        "-> ouvrir la fiche")


def test_qsy_regle_le_vfo_via_rig_qsy_en_khz():
    """Le bouton QSY doit poster sur /rig/qsy avec freq_khz (même contrat que la
    page CHASSE). C'est ce qui « fait passer la radio sur la fréquence »."""
    src = _sans_commentaires(_src('logx_bandeau_fiche.js'))
    assert "'/rig/qsy'" in src, "le QSY ne poste pas sur /rig/qsy"
    assert 'freq_khz' in src, "le QSY n'envoie pas freq_khz au serveur"


def test_bouton_qsy_garde_par_l_etat_du_pilotage_cat():
    """Le bouton QSY n'est proposé que si le pilotage CAT est activé (/rig/state
    -> enabled) : sur une station sans CAT, on ne montre pas un bouton qui
    échouerait. La fiche (fréquence, nom, QRZ) reste utile sans lui."""
    src = _sans_commentaires(_src('logx_bandeau_fiche.js'))
    assert "'/rig/state'" in src, "l'état du pilotage CAT n'est pas consulté"
    # le QSY est bien SUBORDONNÉ à cet état (rigActive() résolu avant d'ajouter
    # le bouton) : la référence à rigActive précède l'ajout du bouton QSY.
    assert 'rigActive()' in src, "rigActive() (garde CAT) absent du code"
    assert src.index('rigActive()') < src.index("'▶ QSY '"), \
        "le bouton QSY est ajouté sans attendre la garde CAT rigActive()"
