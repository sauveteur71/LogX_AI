# -*- coding: utf-8 -*-
"""L'endpoint /data/focus : un seul appel pour toute la page FOCUS BANDE.

POURQUOI UN SEUL APPEL. La page est faite pour rester ouverte sur un 2e écran,
et elle a besoin de six choses : le cluster de la bande, les carrés manquants,
la propagation, les concours actifs sur cette bande et ce mode, le classement
de toutes les bandes, l'état du concours. Six requêtes toutes les 15 s, ce sont
six connexions à tenir pour une information que le serveur a déjà en cache.

CE QUI EST TESTÉ ICI : que l'endpoint réponde, qu'il FILTRE réellement sur la
bande demandée, et surtout qu'il ne tombe pas quand une source extérieure
manque. La propagation vient d'un service en ligne, le calendrier d'un calcul
de dates, les carrés d'un module de diplômes : sur une expédition sans
Internet, aucun des trois ne répond — et la page doit continuer d'afficher le
cluster local plutôt que de rendre une erreur.
"""
import http.server
import json
import os
import sys
import threading
import urllib.request

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as httpmod   # noqa: E402


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))


# ─── Réponse de base ─────────────────────────────────────────────────────────

def test_l_endpoint_repond_et_porte_TOUTES_les_sections(server):
    """Une section manquante, et la page affiche un bloc vide sans dire
    pourquoi — pire qu'une erreur franche."""
    d = _get(server, '/data/focus')
    assert d['ok'] is True
    for cle in ('bandes', 'classement', 'spots', 'regions', 'concours',
                'carres_manquants', 'contest_actif'):
        assert cle in d, cle


def test_la_bande_demandee_est_renvoyee_telle_quelle(server):
    d = _get(server, '/data/focus?band=14&mode=SSB')
    assert d['band'] == '14' and d['mode'] == 'SSB'


def test_les_spots_sont_FILTRES_sur_la_bande(server):
    """Sans filtrage, la page « 20 m » afficherait le cluster de toutes les
    bandes — exactement ce que l'utilisateur a déjà dans le logbook."""
    d = _get(server, '/data/focus?band=14')
    for s in d['spots']:
        assert str(s.get('band', '')).startswith('14'), s


def test_sans_bande_demandee_rien_n_est_filtre(server):
    """Le classement doit pouvoir se calculer sur tout ce qui est connu."""
    tout = _get(server, '/data/focus')
    quatorze = _get(server, '/data/focus?band=14')
    assert len(tout['spots']) >= len(quatorze['spots'])


def test_la_bande_demandee_apparait_dans_la_liste_meme_si_hors_concours(server):
    """On peut vouloir regarder une bande que le concours n'utilise pas — la
    faire disparaître du sélecteur serait incompréhensible."""
    d = _get(server, '/data/focus?band=10.1')
    assert '10.1' in d['bandes']


# ─── Le classement ───────────────────────────────────────────────────────────

def test_le_classement_couvre_les_bandes_proposees(server):
    d = _get(server, '/data/focus')
    assert {c['band'] for c in d['classement']} == set(d['bandes'])


def test_le_classement_est_trie_du_meilleur_au_moins_bon(server):
    d = _get(server, '/data/focus')
    scores = [c['score'] for c in d['classement']]
    assert scores == sorted(scores, reverse=True), scores


def test_chaque_ligne_du_classement_porte_sa_justification(server):
    d = _get(server, '/data/focus')
    for c in d['classement']:
        assert c.get('pourquoi'), c


# ─── Résilience : une source absente ne casse pas la page ────────────────────
# Sur une expédition sans Internet, propagation/calendrier/diplômes sont tous
# injoignables en même temps. La page doit continuer à servir le reste.

def _casser(monkeypatch, nom_module, nom_fonction):
    import importlib
    mod = importlib.import_module(nom_module)

    def boum(*a, **k):
        raise RuntimeError('source indisponible (test)')
    monkeypatch.setattr(mod, nom_fonction, boum)


def test_sans_propagation_la_page_repond_quand_meme(server, monkeypatch):
    _casser(monkeypatch, 'logx_paths', 'all_regions')
    d = _get(server, '/data/focus?band=14')
    assert d['ok'] is True and d['regions'] == []


def test_sans_calendrier_la_page_repond_quand_meme(server, monkeypatch):
    _casser(monkeypatch, 'logx_http', 'calc_all_dates')
    d = _get(server, '/data/focus?band=14')
    assert d['ok'] is True and d['concours'] == []


def test_sans_module_de_diplomes_la_page_repond_quand_meme(server, monkeypatch):
    _casser(monkeypatch, 'logx_awards', 'carres_travailles')
    d = _get(server, '/data/focus?band=14')
    assert d['ok'] is True and d['carres_manquants'] == []


def test_les_trois_sources_absentes_A_LA_FOIS(server, monkeypatch):
    """Le cas expédition : rien ne répond sauf le cluster déjà en cache."""
    _casser(monkeypatch, 'logx_paths', 'all_regions')
    _casser(monkeypatch, 'logx_http', 'calc_all_dates')
    _casser(monkeypatch, 'logx_awards', 'carres_travailles')
    d = _get(server, '/data/focus?band=14')
    assert d['ok'] is True
    assert 'spots' in d and 'classement' in d


# ─── Entrées douteuses ───────────────────────────────────────────────────────

@pytest.mark.parametrize('q', [
    '?band=', '?band=%20', '?mode=', '?band=abc', '?band=14&mode=INCONNU',
    '?band=' + 'x' * 300, '?band=<script>', '?band=14&band=21',
])
def test_une_requete_douteuse_ne_fait_pas_tomber_l_endpoint(server, q):
    """La bande peut venir d'une URL tapée à la main ou d'un vieux favori."""
    d = _get(server, '/data/focus' + q)
    assert d['ok'] is True


def test_la_reponse_reste_LEGERE(server):
    """Cette page se rafraîchit en boucle sur un 2e écran. Le panneau coach
    envoyait 5,5 Mo toutes les 15 s pour une donnée que personne n'affichait :
    on ne recommence pas."""
    with urllib.request.urlopen(server + '/data/focus?band=14', timeout=20) as r:
        taille = len(r.read())
    assert taille < 300_000, '%d octets' % taille
