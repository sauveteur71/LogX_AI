# -*- coding: utf-8 -*-
"""Spots IOTA (logx_iota.spots_from_clusters) — extraits par regex des
commentaires des spots cluster déjà collectés (logx_clusters), sans jamais
appeler le réseau depuis ce module. groups_db est stubbé directement (comme
test_wca.py) : pas de vrai téléchargement, pas de thread de fond."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_iota as iota


def _stub_groups_db(entries):
    """Peuple groups_db._state directement (jamais ensure_loading_started :
    pas de vrai téléchargement dans les tests)."""
    by_code = {e['code']: e for e in entries}
    iota.groups_db._state = {
        'by_code': by_code, 'list': entries,
        'loading': False, 'loaded': True, 'error': None,
    }


EU064 = {'code': 'EU-064', 'name': 'Jersey', 'lat': 49.21, 'lon': -2.13, 'island_names': []}
EU045 = {'code': 'EU-045', 'name': 'Corsica', 'lat': 42.2, 'lon': 9.15, 'island_names': []}


def test_tague_reference_iota_valide_dans_le_commentaire():
    """Spot cluster dict (format _normalize_spot / dxsummit_hf...) avec la
    référence IOTA en commentaire -> spot IOTA taggé avec les bonnes clés."""
    _stub_groups_db([EU064])
    spots_by_band = {'HF': [
        {'call': '9A/DF5WC', 'dx': '9A/DF5WC', 'freq': 14260.0, 'mode': 'SSB',
         'spotter': 'F4GLD', 'time': '1205Z', 'info': 'IOTA EU-064 QSL VIA F4GLD'},
    ]}
    spots = iota.spots_from_clusters(spots_by_band)
    assert len(spots) == 1
    s = spots[0]
    assert s['call'] == '9A/DF5WC'
    assert s['reference'] == 'EU-064'
    assert s['band'] == '14'                # dérivée de la fréquence (14260 kHz)
    assert s['island_name'] == 'Jersey'
    assert s['lat'] == 49.21 and s['lon'] == -2.13
    assert s['spotter'] == 'F4GLD'
    assert s['source'] == 'iota-cluster'


def test_ignore_commentaire_sans_reference_iota():
    _stub_groups_db([EU064])
    spots_by_band = {'HF': [
        {'call': 'F5ABC', 'freq': 14200.0, 'info': 'TNX 73 GL DE F4GLD'},
    ]}
    assert iota.spots_from_clusters(spots_by_band) == []


def test_faux_positif_format_correct_mais_absent_de_la_base():
    """'SN-123' a le bon FORMAT (CC-NNN) mais n'existe pas dans groups_db :
    jamais tagué IOTA (un numéro de série ou une temperature ne doit pas
    devenir une fausse référence)."""
    _stub_groups_db([EU064])
    spots_by_band = {'HF': [
        {'call': 'F5ABC', 'freq': 14200.0, 'info': 'CONTEST SN-123 599'},
    ]}
    assert iota.spots_from_clusters(spots_by_band) == []


def test_format_liste_cellules_f5len():
    """Source F5LEN : spots en liste de cellules brutes (pas de clé 'info')
    -> le commentaire IOTA est cherché dans les cellules jointes."""
    _stub_groups_db([EU064])
    spots_by_band = {'50': [
        ['F5ABC', '50.185', '1200Z', 'IOTA EU-064 TNX QSL'],
    ]}
    spots = iota.spots_from_clusters(spots_by_band)
    assert len(spots) == 1
    assert spots[0]['reference'] == 'EU-064'
    assert spots[0]['call'] == 'F5ABC'
    # Format liste : pas de fréquence normalisée -> repli sur le libellé de bande
    assert spots[0]['band'] == '50'
    assert spots[0]['mode'] == ''            # pas de clé 'mode' pour ce format


def test_dedoublonne_meme_indicatif_meme_reference():
    _stub_groups_db([EU064])
    spots_by_band = {
        '144': [{'call': 'F5ABC', 'freq': 144.310, 'info': 'EU-064'}],
        'HF':  [{'call': 'F5ABC', 'freq': 14200.0, 'info': 'EU-064'}],
    }
    spots = iota.spots_from_clusters(spots_by_band)
    assert len(spots) == 1


def test_deux_references_valides_deux_spots_distincts():
    _stub_groups_db([EU064, EU045])
    spots_by_band = {'HF': [
        {'call': 'F5ABC', 'freq': 14200.0, 'info': 'EU-064'},
        {'call': 'TK/F5ABC', 'freq': 14200.0, 'info': 'EU-045'},
    ]}
    spots = iota.spots_from_clusters(spots_by_band)
    refs = {s['reference'] for s in spots}
    assert refs == {'EU-064', 'EU-045'}


def test_spot_sans_commentaire_ni_indicatif_ignore():
    _stub_groups_db([EU064])
    spots_by_band = {'HF': [{'call': '', 'freq': 14200.0, 'info': 'EU-064'}],
                     '144': [{'call': 'F5ABC', 'freq': 144.3, 'info': ''}]}
    assert iota.spots_from_clusters(spots_by_band) == []


def test_lit_spots_cache_par_defaut_si_aucun_argument(monkeypatch):
    """Sans argument, la source par défaut est logx_clusters.SPOTS_CACHE
    (jamais un fetch réseau propre à ce module)."""
    _stub_groups_db([EU064])
    import logx_clusters as clusters
    monkeypatch.setattr(clusters, 'SPOTS_CACHE',
                        {'HF': [{'call': 'F5ABC', 'freq': 14200.0, 'info': 'EU-064'}]})
    spots = iota.spots_from_clusters()
    assert len(spots) == 1 and spots[0]['reference'] == 'EU-064'
