# -*- coding: utf-8 -*-
"""Autonomie zone blanche : _loadLeaflet() (logx_configuration.js) doit charger
Leaflet depuis la copie VENDORISÉE locale (/vendor/leaflet/), jamais depuis un
CDN. Leaflet est déjà vendorisé (utilisé par logx_carte.html) ; ce chargeur de
la carte « choisir le locator » dans CONFIG était le dernier reliquat CDN de
code -> échouait hors ligne (« connexion Internet requise »)."""
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_configuration.js')


def _corps_loadLeaflet():
    src = open(JS, encoding='utf-8').read()
    m = re.search(r'function _loadLeaflet\(\)\s*\{', src)
    assert m, '_loadLeaflet introuvable'
    i = m.start()
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                corps = src[i:k + 1]
                break
    else:
        raise AssertionError('accolade fermante introuvable')
    # DÉPOUILLER LES COMMENTAIRES avant d'analyser (piège du dépôt) : un
    # commentaire expliquant l'ANCIEN CDN ne doit pas faire échouer l'assertion
    # « aucune URL CDN dans le CODE ».
    return '\n'.join(re.sub(r'//.*$', '', ligne) for ligne in corps.splitlines())


def test_leaflet_charge_depuis_vendor_local():
    corps = _corps_loadLeaflet()
    assert '/vendor/leaflet/leaflet.min.js' in corps
    assert '/vendor/leaflet/leaflet.min.css' in corps


def test_aucune_url_cdn_dans_le_chargeur():
    corps = _corps_loadLeaflet()
    assert 'cdnjs' not in corps
    assert 'http://' not in corps and 'https://' not in corps


def test_fichiers_vendorises_presents():
    v = os.path.join(CONCOURS, 'vendor', 'leaflet')
    assert os.path.isfile(os.path.join(v, 'leaflet.min.js'))
    assert os.path.isfile(os.path.join(v, 'leaflet.min.css'))
