# -*- coding: utf-8 -*-
"""Extraction du bloc Cloud Sync + MySQL hors de logx_configuration.js.

Chantier « alléger les gros fichiers » (PASSATION §6), bloc le plus sûr :
zéro dépendance externe, aucune émission radio. Les 4 fonctions
(cloudsyncNow, _mysqlFieldsFromForm, testMysqlConnection, mysqlSyncNow) sont
DÉPLACÉES vers logx_configuration_cloudsync.js, chargé en <script src> dans
logx_configuration.html. Un déplacement ne doit RIEN changer : ces tests
verrouillent (1) que chaque fonction est définie une seule fois, dans le
nouveau fichier ; (2) que le HTML charge bien le nouveau fichier après
configuration.js ; (3) que le câblage onclick du HTML reste résoluble
(fonctions globales). L'équivalence byte-à-byte du code déplacé a été vérifiée
au moment de l'extraction (contre-épreuve mutation).
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_configuration.js'), encoding='utf-8').read()
NEW = open(os.path.join(BASE, 'logx_configuration_cloudsync.js'), encoding='utf-8').read()
HTML = open(os.path.join(BASE, 'logx_configuration.html'), encoding='utf-8').read()

_DEFS = (
    'async function cloudsyncNow(',
    'function _mysqlFieldsFromForm(',
    'async function testMysqlConnection(',
    'async function mysqlSyncNow(',
)


def test_fonctions_definies_dans_le_nouveau_fichier():
    for d in _DEFS:
        assert d in NEW, "définition manquante dans le fichier extrait : %s" % d


def test_fonctions_retirees_de_configuration_js():
    # PROPRIÉTÉ D'ÉQUIVALENCE : plus AUCUNE de ces définitions dans le monolithe
    # (sinon double définition — la seconde chargée écraserait, bug silencieux).
    for d in _DEFS:
        assert d not in JS, "définition encore présente dans configuration.js : %s" % d


def test_definie_exactement_une_fois_au_total():
    # Ni doublon, ni disparition : chaque définition existe une seule fois sur
    # l'ensemble des deux fichiers.
    for d in _DEFS:
        assert (JS.count(d) + NEW.count(d)) == 1, "définition non-unique : %s" % d


def test_html_charge_le_nouveau_fichier_apres_configuration_js():
    assert '<script src="logx_configuration_cloudsync.js"></script>' in HTML, \
        "logx_configuration.html doit charger le fichier extrait"
    # Ordre : après configuration.js (les fonctions ne sont appelées que sur
    # clic, mais on garde un ordre lisible et sans surprise).
    assert HTML.index('logx_configuration.js') < HTML.index('logx_configuration_cloudsync.js')


def test_cablage_onclick_preserve():
    # Le câblage UI (onclick) reste : fonctions globales, donc toujours résolu.
    for handler in ('onclick="cloudsyncNow()"', 'onclick="testMysqlConnection()"',
                    'onclick="mysqlSyncNow()"'):
        assert handler in HTML, "câblage onclick perdu : %s" % handler
