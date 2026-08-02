# -*- coding: utf-8 -*-
"""Annuaire de nœuds DX cluster (logx_clusters.cluster_catalog) : forme et
cohérence. Les valeurs viennent de ng3k.com, PAS de mémoire — ce test verrouille
la STRUCTURE, pas la joignabilité réseau (jamais de socket ici)."""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_clusters as clusters   # noqa: E402


def test_catalogue_non_vide_et_riche():
    cat = clusters.cluster_catalog()
    assert len(cat) >= 15, 'la liste doit être conséquente'


def test_chaque_noeud_a_host_port_label_region():
    for n in clusters.cluster_catalog():
        assert n['host'] and isinstance(n['host'], str)
        assert isinstance(n['port'], int) and 0 < n['port'] < 65536
        assert n['label'] and n['region']


def test_ports_varies_pas_tous_7300():
    """Le port varie d'un nœud à l'autre (7300/7373/9000/41112…) : si tout était
    figé à 7300, ce serait le signe d'une liste inventée de mémoire."""
    ports = {n['port'] for n in clusters.cluster_catalog()}
    assert len(ports) >= 3


def test_pas_de_doublon_host_port():
    vus = [(n['host'], n['port']) for n in clusters.cluster_catalog()]
    assert len(vus) == len(set(vus))


def test_ve7cc_present():
    hosts = {n['host'] for n in clusters.cluster_catalog()}
    assert 'dxc.ve7cc.net' in hosts
