# -*- coding: utf-8 -*-
"""Sous-chantier B, lot 1 — l'export ADIF CLIENT (buildAdifText) cesse de perdre
des tags que l'export serveur (build_adif) émet.

Avant : buildAdifText omettait NAME, QTH, STATE, COMMENT, DISTANCE, PROP_MODE,
SAT_NAME, MY_SIG, MY_SIG_INFO, SIG, SIG_INFO -> un export déclenché côté client
(exportADIF, filter_builder) perdait ces données. Défaut d'intégrité. Ce test
fige que ces tags sont désormais émis, et que la liste des tags standard
(ADIF_STD_TAGS, anti-duplication des extra_fields) est cohérente avec le serveur.
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_export_adif.js'), encoding='utf-8').read()
PY = open(os.path.join(BASE, 'logx_export.py'), encoding='utf-8').read()

TAGS_JADIS_OMIS = ['NAME', 'QTH', 'STATE', 'COMMENT', 'DISTANCE', 'PROP_MODE',
                   'SAT_NAME', 'MY_SIG', 'MY_SIG_INFO', 'SIG', 'SIG_INFO']


def _build_body():
    i = JS.index('function buildAdifText')
    j = JS.index('\n}', i)
    return JS[i:j]


def test_buildadiftext_emet_les_tags_jadis_omis():
    body = _build_body()
    for tag in TAGS_JADIS_OMIS:
        assert ("adifField('%s'" % tag) in body, tag


def test_adif_std_tags_couvre_les_nouveaux():
    # ADIF_STD_TAGS (anti-duplication des extra_fields) doit lister ces tags,
    # sinon un extra_field homonyme les dupliquerait dans l'export.
    i = JS.index('ADIF_STD_TAGS = new Set([')
    bloc = JS[i:JS.index('])', i)]
    for tag in TAGS_JADIS_OMIS:
        assert ("'%s'" % tag) in bloc, tag


def test_parite_avec_le_serveur():
    # Les mêmes tags standard des deux côtés (buildAdifText JS <-> build_adif PY).
    # On vérifie que chaque tag jadis omis est bien dans _ADIF_STD_TAGS (Python).
    i = PY.index('_ADIF_STD_TAGS = {')
    bloc = PY[i:PY.index('}', i)]
    for tag in TAGS_JADIS_OMIS:
        assert ("'%s'" % tag) in bloc, tag
