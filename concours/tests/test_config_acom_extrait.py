# -*- coding: utf-8 -*-
"""Extraction du bloc ACOM (ampli série RS-232) hors de logx_configuration.js.

Chantier « alléger les gros fichiers » (PASSATION §6), 2e lot après Cloud Sync.
Les 3 fonctions (refreshAcomPorts, testAcomConnection, acomSetOperate) sont
DÉPLACÉES vers logx_configuration_acom.js, chargé en <script src> après
configuration.js. Déplacement PUR. Particularité vérifiée : ces fonctions ne
sont appelées que par des handlers HTML (onfocus/onclick), jamais au
chargement -> l'ordre de chargement n'a aucune incidence ; et elles s'appuient
sur le global escC() de configuration.js, disponible au moment de l'appel.
Ces tests verrouillent l'équivalence structurelle + le câblage.
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_configuration.js'), encoding='utf-8').read()
NEW = open(os.path.join(BASE, 'logx_configuration_acom.js'), encoding='utf-8').read()
HTML = open(os.path.join(BASE, 'logx_configuration.html'), encoding='utf-8').read()

_DEFS = (
    'async function refreshAcomPorts(',
    'async function testAcomConnection(',
    'async function acomSetOperate(',
)


def test_fonctions_definies_dans_le_nouveau_fichier():
    for d in _DEFS:
        assert d in NEW, "définition manquante dans le fichier extrait : %s" % d


def test_fonctions_retirees_de_configuration_js():
    for d in _DEFS:
        assert d not in JS, "définition encore présente dans configuration.js : %s" % d


def test_definie_exactement_une_fois_au_total():
    for d in _DEFS:
        assert (JS.count(d) + NEW.count(d)) == 1, "définition non-unique : %s" % d


def test_bloc_na_pas_deborde_sur_lampli():
    # Garde-fou du piège PASSATION : la zone AMPLIFICATEUR HF (mixte ACOM/AMP/
    # CAT/QRZ) commence juste après — elle NE DOIT PAS être partie avec le bloc.
    assert 'AMP_DEFAULT_BAUD' not in NEW, "le fichier ACOM a happé du code AMPLI"
    assert 'updateEnabledFieldsVisibility' not in NEW
    assert 'AMP_DEFAULT_BAUD' in JS, "le code AMPLI doit rester dans configuration.js"


def test_html_charge_le_nouveau_fichier_apres_configuration_js():
    assert '<script src="logx_configuration_acom.js"></script>' in HTML, \
        "logx_configuration.html doit charger le fichier extrait"
    assert HTML.index('logx_configuration.js') < HTML.index('logx_configuration_acom.js')


def test_cablage_handlers_preserve():
    # Câblage UI préservé (fonctions globales, toujours résolu).
    assert 'onfocus="refreshAcomPorts()"' in HTML, "onfocus refreshAcomPorts perdu"
    assert 'onclick="testAcomConnection()"' in HTML, "onclick testAcomConnection perdu"
    for arg in ('operate', 'standby', 'off'):
        assert ('acomSetOperate(\'%s\')' % arg) in HTML, "câblage acomSetOperate(%s) perdu" % arg
