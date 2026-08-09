# -*- coding: utf-8 -*-
"""Recherche plein-texte dans les pages (logx_search.py + /search) — demande
F4GLD 07/08/2026 : retrouver où un terme (ex. « sstv ») est mentionné dans le
logiciel sans devoir connaître par cœur la page qui en parle.

Tests unitaires sur un mini-répertoire de pages HTML fabriquées (base_dir) :
indépendants du contenu réel des pages, qui change souvent. Un test
d'intégration à la fin vérifie sur le VRAI contenu (concours/*.html) que
« sstv » retombe bien sur au moins une page connue pour en parler — filet
de sécurité minimal contre une regex cassée qui ne matcherait plus rien."""
import http.server
import json
import os
import sys
import threading
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_search
import logx_http as httpmod


def _write(tmp_path, name, html):
    (tmp_path / name).write_text(html, encoding='utf-8')


@pytest.fixture
def pages(tmp_path, monkeypatch):
    _write(tmp_path, 'logx_configuration.html', '''
        <div class="section-title">STATION RADIO</div>
        <p>Indicatif, locator, antenne.</p>
        <div class="section-title"><span class="nav-ico"><svg viewBox="0 0 18 18"><path d="M1 1"/></svg></span> SSTV &amp; RTTY</div>
        <p>Active le décodeur d'images SSTV dans le logbook.</p>
    ''')
    _write(tmp_path, 'logx_logbook.html', '''
        <div class="panel-title">CARTES ENTENDUES</div>
        <p>Rien à voir ici.</p>
    ''')
    monkeypatch.setattr(logx_search, 'SEARCHABLE_PAGES',
                         ['logx_configuration.html', 'logx_logbook.html'])
    return str(tmp_path)


def test_recherche_trouve_le_bon_titre_de_section(pages):
    results = logx_search.search('sstv', base_dir=pages)
    assert any(r['page'] == 'logx_configuration.html' and 'SSTV' in r['title']
               for r in results)


def test_recherche_insensible_a_la_casse(pages):
    assert logx_search.search('SsTv', base_dir=pages) == logx_search.search('sstv', base_dir=pages)


def test_recherche_matche_aussi_le_corps_pas_seulement_le_titre(pages):
    results = logx_search.search('locator', base_dir=pages)
    assert any(r['page'] == 'logx_configuration.html' and r['title'] == 'STATION RADIO'
               for r in results)


def test_recherche_sans_resultat_page_absente(pages):
    assert logx_search.search('un_terme_qui_napparait_nulle_part', base_dir=pages) == []


def test_recherche_requete_vide_ou_trop_courte(pages):
    assert logx_search.search('', base_dir=pages) == []
    assert logx_search.search('s', base_dir=pages) == []
    assert logx_search.search('   ', base_dir=pages) == []


def test_recherche_fichier_manquant_ne_plante_pas(tmp_path, monkeypatch):
    monkeypatch.setattr(logx_search, 'SEARCHABLE_PAGES', ['logx_absent.html'])
    assert logx_search.search('sstv', base_dir=str(tmp_path)) == []


def test_recherche_snippet_extrait_une_fenetre_autour_du_terme(pages):
    results = logx_search.search('rtty', base_dir=pages)
    hit = next(r for r in results if r['page'] == 'logx_configuration.html' and 'SSTV' in r.get('title', ''))
    assert 'RTTY' in hit['title'] or 'RTTY' in hit['snippet']


def test_page_sans_titre_de_section_retombe_sur_une_section_unique(tmp_path, monkeypatch):
    _write(tmp_path, 'logx_sans_titre.html', '<p>Un contenu qui parle de foudre et d\'orages.</p>')
    monkeypatch.setattr(logx_search, 'SEARCHABLE_PAGES', ['logx_sans_titre.html'])
    results = logx_search.search('foudre', base_dir=str(tmp_path))
    assert len(results) == 1
    assert results[0]['title'] == ''


def test_script_et_style_exclus_de_la_recherche(tmp_path, monkeypatch):
    _write(tmp_path, 'logx_avecjs.html', '''
        <style>.sstv-secret{color:red}</style>
        <script>var sstv_internal_var = 1;</script>
        <div class="section-title">RIEN À VOIR</div>
        <p>Pas de sstv ici dans le texte visible.</p>
    ''')
    monkeypatch.setattr(logx_search, 'SEARCHABLE_PAGES', ['logx_avecjs.html'])
    # "sstv" apparaît dans le CSS et le JS mais pas dans le texte visible réel
    # de la section "RIEN À VOIR" — confirme qu'on ne cherche que ce qui reste
    # après avoir retiré <script>/<style>, pas le texte visible + le code.
    results = logx_search.search('sstv-secret', base_dir=str(tmp_path))
    assert results == []
    results2 = logx_search.search('sstv_internal_var', base_dir=str(tmp_path))
    assert results2 == []


def test_titre_avec_icone_svg_imbriquee_extrait_juste_le_texte(pages):
    results = logx_search.search('sstv', base_dir=pages)
    hit = next(r for r in results if r['title'] and 'SSTV' in r['title'])
    assert '<svg' not in hit['title'] and '<span' not in hit['title']


# ─── Correctifs audit trouvabilité/intuitivité (09/08/2026) ──────────────────
# Constat : les requêtes en langage naturel ("comment exporter mon log")
# donnaient 0 résultat alors que le mot-clé seul en donnait, "reglement"
# (sans accent) donnait 0 résultat alors que "règlement" en donnait, et
# search('FT8') faisait remonter 4 quasi-doublons du <nav> partagé avant la
# vraie page logx_ft8.html. Les 3 tests ci-dessous couvrent ces correctifs.

def test_recherche_multi_mots_langage_naturel_ordre_different(pages):
    """L'ancien comportement comparait la requête ENTIÈRE comme une seule
    sous-chaîne littérale : une requête dont les mots n'apparaissent pas
    consécutivement et dans le même ordre que dans le texte source (ce qui
    est la norme pour une question en langage naturel) ne matchait jamais,
    même si chaque mot pris isolément était présent. Le nouveau comportement
    tokénise par mot et score par nombre de mots présents - l'ordre des mots
    dans la requête n'a plus à correspondre à celui du texte."""
    results = logx_search.search('decodeur sstv active', base_dir=pages)
    assert any(r['page'] == 'logx_configuration.html' and 'SSTV' in r['title']
               for r in results)


def test_recherche_insensible_aux_accents(tmp_path, monkeypatch):
    """« reglement » (saisi sans accent, cas courant au clavier ou par
    fatigue) doit retrouver une section dont le texte source contient
    « règlement » - la comparaison se fait sur une version normalisée
    (NFD, marques diacritiques retirées) des deux côtés, même principe que
    _searchLocalHelp() côté JS (logx_configuration.html)."""
    _write(tmp_path, 'logx_test_accents.html', '''
        <div class="section-title">RÈGLEMENT DU CONCOURS</div>
        <p>Consulte le règlement officiel avant de participer.</p>
    ''')
    monkeypatch.setattr(logx_search, 'SEARCHABLE_PAGES', ['logx_test_accents.html'])
    results = logx_search.search('reglement', base_dir=str(tmp_path))
    assert any('RÈGLEMENT' in r['title'] for r in results)


def test_recherche_exclut_nav_et_trie_par_score_decroissant(tmp_path, monkeypatch):
    """Le bloc <nav class="app-nav"> (identique sur presque toutes les
    pages) ne doit jamais produire de résultat à lui seul - seules les
    VRAIES sections de contenu apparaissent. Et à score égal ou différent,
    les résultats doivent être triés par pertinence : un mot-clé présent
    dans le TITRE de section (page_b) doit passer avant un mot-clé présent
    seulement dans le corps (page_a) - reproduit le constat réel où
    search('FT8') remontait des quasi-doublons de nav avant logx_ft8.html."""
    _write(tmp_path, 'logx_page_a.html', '''
        <nav class="app-nav">
          <a href="logx_ft8.html">FT8</a>
          <a href="logx_cw.html">CW</a>
        </nav>
        <div class="section-title">DIVERS</div>
        <p>On parle un peu de FT8 dans cette section, en passant.</p>
    ''')
    _write(tmp_path, 'logx_page_b.html', '''
        <nav class="app-nav">
          <a href="logx_ft8.html">FT8</a>
        </nav>
        <div class="section-title">FT8 DECODEUR</div>
        <p>Reglages du decodeur.</p>
    ''')
    monkeypatch.setattr(logx_search, 'SEARCHABLE_PAGES',
                         ['logx_page_a.html', 'logx_page_b.html'])
    results = logx_search.search('FT8', base_dir=str(tmp_path))
    assert len(results) == 2
    assert all(r['title'] in ('DIVERS', 'FT8 DECODEUR') for r in results)
    assert results[0]['title'] == 'FT8 DECODEUR'


# ─── Intégration : sur le vrai contenu de concours/*.html ────────────────────

def test_recherche_reelle_sstv_trouve_au_moins_une_page_connue():
    results = logx_search.search('sstv')
    pages_touchees = {r['page'] for r in results}
    assert pages_touchees & {'logx_configuration.html', 'logx_logbook.html'}


# ─── HTTP : GET /search ───────────────────────────────────────────────────────

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
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def test_http_search_ne_requiert_aucun_jeton(server):
    status, data = _get(server, '/search?q=sstv')
    assert status == 200
    assert data['query'] == 'sstv'
    assert isinstance(data['results'], list)
    assert len(data['results']) >= 1


def test_http_search_requete_vide_renvoie_liste_vide(server):
    status, data = _get(server, '/search?q=')
    assert status == 200
    assert data['results'] == []


def test_http_search_parametre_absent_renvoie_liste_vide(server):
    status, data = _get(server, '/search')
    assert status == 200
    assert data['results'] == []
