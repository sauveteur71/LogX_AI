# -*- coding: utf-8 -*-
"""L'activité d'activation portable (id `iota_pota`) porte un label ÉLARGI à
tout le XOTA, pas seulement « IOTA / POTA ».

Le socle couvre POTA/SOTA/WWFF/IOTA/WCA/DFCF/WWBOTA/GMA/ARLHS ; un label
« LOG IOTA / POTA » sous-vend l'activité et perd le débutant qui fait du SOTA
ou des châteaux. Vérifie l'entrée PRÉCISE (pas une présence n'importe où) côté
accueil et la cohérence du label côté barre de statut.
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


def test_entree_iota_pota_label_elargi():
    acc = _lire('logx_accueil.js')
    m = re.search(r"\{id:'iota_pota',[^}]*\}", acc)
    assert m, "entrée iota_pota introuvable dans ACTIVITIES"
    entry = m.group(0)
    assert 'LOG activation portable' in entry, entry
    assert 'SOTA' in entry, "le hint doit s'élargir au-delà de IOTA/POTA (SOTA, châteaux…)"
    assert 'IOTA / POTA' not in entry, "ancien label étroit encore présent"


def test_statusbar_label_coherent():
    sb = _lire('logx_statusbar.js')
    assert re.search(r"iota_pota:\s*'LOG activation portable'", sb), \
        "ACTIVITY_LABELS.iota_pota doit être aligné sur le label élargi"
