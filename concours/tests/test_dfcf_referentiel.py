# -*- coding: utf-8 -*-
"""Référentiel COMPLET DFCF (logx_dfcf) : parseur DÉFENSIF par tokens des pages
départementales (dfcf.fr/dept/dNN.html), agrégation multi-pages, recherche par
référence/nom. Pages IRRÉGULIÈRES (tabs OU espaces multiples, date en plage,
indicatif collé à la commune) — d'où le parseur positionnel. Réseau simulé."""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_dfcf as dfcf       # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def _injecter(monkeypatch, items):
    """Charge un catalogue directement dans l'état (court-circuite le thread de
    fond + le réseau) : _charger() revient tout de suite car loaded=True."""
    monkeypatch.setattr(dfcf, '_state', {
        'by_code': {it['code']: it for it in items},
        'list': items, 'loading': False, 'loaded': True, 'error': None})


# ── Parseur de ligne défensif (le cœur) ─────────────────────────────────────

def test_lignes_fixture_reelles():
    """Les 3 formats de F4GLD + variantes réelles (date, tabs, plage, réactiv.)."""
    with open(os.path.join(FIXTURES, 'dfcf_department_lines.txt'), encoding='utf-8') as f:
        lignes = [l.rstrip('\n') for l in f if l.strip()]
    parsed = [dfcf._parse_ligne(l) for l in lignes]
    by = {p['code']: p for p in parsed if p}

    # Cas C : indicatif COLLÉ à la commune « F5NLX/P(Marcorignan »
    assert by['11-104']['callsign'] == 'F5NLX/P'
    assert by['11-104']['name'] == 'Gléon Berty'
    assert by['11-104']['commune'] == 'Marcorignan' and by['11-104']['cp'] == '11120'
    # Nom multi-mots, indicatif séparé
    assert by['11-105']['name'] == 'Tour des Templiers'
    # Commune multi-mots
    assert by['31-087']['commune'] == 'Roquefort sur Garonne' and by['31-087']['cp'] == '31360'
    # Séparateurs par TABULATION
    assert by['01-001']['callsign'] == 'F5NYZ/P' and by['01-001']['commune'] == 'Culoz'
    # Date en PLAGE « 10-23/12/2000 » : retirée du nom, pas dans le nom
    assert by['01-004']['name'] == 'Angeville'
    # Séparateur par espaces MULTIPLES
    assert by['01-002']['name'] == 'de Pont de Veyle'


def test_ligne_reactivation_ignoree():
    r = dfcf._parse_ligne('01-001 (Réactivation) 01/11/2023\tF5NLX/P')
    assert r is None                        # pas un vrai nom -> ne pas écraser l'original


def test_ligne_sans_indicatif_conservee():
    """Ligne sans indicatif détectable : CONSERVÉE (reference_only), pas jetée."""
    r = dfcf._parse_ligne('55-999 Château sans indicatif connu')
    assert r is not None and r['status'] == 'reference_only'
    assert r['code'] == '55-999' and r['callsign'] == ''


def test_ligne_non_chateau_rejetee():
    assert dfcf._parse_ligne('Mois de janvier 2026') is None
    assert dfcf._parse_ligne('') is None


def test_entete_collee_a_la_ref():
    """1re ligne d'une page : en-tête <TD>/titre collé devant la réf -> on démarre
    à la réf, l'en-tête est jeté."""
    r = dfcf._parse_ligne('Titre Page   01-001 de Montveran\t08/01/00\tF5NYZ/P (Culoz\t01350)')
    assert r and r['code'] == '01-001' and r['name'] == 'de Montveran'


# ── Parse d'une page (<br>) et agrégation multi-pages ───────────────────────

_D01 = ('<html><body><table><tr><td>'
        '01-001 de Montveran\t08/01/00\tF5NYZ/P (Culoz\t01350)<br>'
        '01-001 (<b>Réactivation</b>) 01/11/2023\tF5NLX/P<br>'
        '01-002      de Pont de Veyle   13/05/00   F5KBD/P<br>'
        '</td></tr></table></body></html>')
_D34 = '<td>34-002 d\'Aumelas 15/03/26 F4ABC (Aumelas 34230)<br></td>'
_INDEX = ('<table><tr><td><a href="dept/d01.html">01</a></td>'
          '<td><a href="dept/d34.html">34</a></td></tr></table>')


def test_parse_page_dedoublonne_reactivation():
    recs = dfcf._parse(_D01)
    codes = [r['code'] for r in recs]
    assert codes == ['01-001', '01-002']    # la réactivation 01-001 n'ajoute pas de doublon
    assert recs[0]['commune'] == 'Culoz' and recs[0]['cp'] == '01350'


def test_dept_urls_extrait_et_quote():
    urls = dfcf._dept_urls(_INDEX + '<a href="dept/d 972 FM.html">972</a>')
    assert dfcf.DFCF_BASE + 'dept/d01.html' in urls
    assert any('%20' in u for u in urls)    # nom DOM avec espaces -> quoté


def test_agreger_catalogue_multi_pages():
    def fetch(url):
        if url == dfcf.DFCF_INDEX_URL:
            return _INDEX
        if url.endswith('d01.html'):
            return _D01
        if url.endswith('d34.html'):
            return _D34
        return ''
    cat = dfcf.agreger_catalogue(fetch=fetch)
    codes = sorted(r['code'] for r in cat)
    assert codes == ['01-001', '01-002', '34-002']


def test_agreger_prefere_fiche_complete_au_repli():
    """Un reference_only rencontré avant ne doit pas masquer la fiche complète."""
    page_repli = '<td>77-001 Donjon sans indicatif<br></td>'
    page_pleine = '<td>77-001 Donjon de Blandy F5ABC (Blandy 77115)<br></td>'
    def fetch(url):
        if url == dfcf.DFCF_INDEX_URL:
            return ('<a href="dept/da.html">a</a><a href="dept/db.html">b</a>')
        return page_repli if url.endswith('da.html') else page_pleine
    cat = dfcf.agreger_catalogue(fetch=fetch)
    assert len(cat) == 1 and cat[0]['status'] == 'official_validated'
    assert cat[0]['callsign'] == 'F5ABC'


# ── API publique (get/search/status/normalisation) ──────────────────────────

def test_get_et_normalisation_prefixe(monkeypatch):
    _injecter(monkeypatch, [{'code': '49-0010', 'name': 'de Montsabert',
                             'region': '', 'commune': '', 'cp': '', 'callsign': '',
                             'status': 'official_validated'}])
    assert dfcf.get('49-0010')['name'] == 'de Montsabert'
    assert dfcf.get('DFCF49-0010')['name'] == 'de Montsabert'   # préfixe normalisé
    assert dfcf.get('dfcf-49-0010')['name'] == 'de Montsabert'
    assert dfcf.get('99-999') is None                           # absente


def test_search_par_nom(monkeypatch):
    _injecter(monkeypatch, [
        {'code': '49-0010', 'name': 'de Montsabert', 'region': '', 'commune': '',
         'cp': '', 'callsign': '', 'status': 'official_validated'},
        {'code': '11-104', 'name': 'Gléon Berty', 'region': '', 'commune': '',
         'cp': '', 'callsign': '', 'status': 'official_validated'}])
    res = dfcf.search('montsabert')
    assert len(res) == 1 and res[0]['code'] == '49-0010'
    assert dfcf.search('') == []


def test_status_pret(monkeypatch):
    _injecter(monkeypatch, [{'code': '11-104', 'name': 'x', 'region': '', 'commune': '',
                             'cp': '', 'callsign': '', 'status': 'official_validated'}])
    st = dfcf.status()
    assert st['ready'] is True and st['count'] == 1


def test_normaliser_code():
    assert dfcf._normaliser_code('DFCF49-0010') == '49-0010'
    assert dfcf._normaliser_code('11-104') == '11-104'
    assert dfcf._normaliser_code(' dfcf-11-104 ') == '11-104'
