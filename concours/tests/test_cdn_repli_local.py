# -*- coding: utf-8 -*-
"""Repli CDN local (demande F4GLD) : Leaflet + Chart.js vendorisés dans
`concours/vendor/`, les 5 pages repointées en LOCAL, aucun CDN externe pour ces
deux libs. En zone blanche (DXpédition, /P, réseau bloquant les CDN) la page
charge et les overlays fonctionnent au lieu de mourir (`L`/`Chart` undefined).

Le service worker précache les libs (dispo au 1er chargement hors-ligne). Le
serveur confine `/vendor/…` sous `concours/` (sous-dossier servi, testé via un
vrai serveur éphémère).
"""
import http.server
import os
import sys
import threading
import urllib.request

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

LEAFLET_JS = '/vendor/leaflet/leaflet.min.js'
LEAFLET_CSS = '/vendor/leaflet/leaflet.min.css'
CHART_JS = '/vendor/chartjs/chart.umd.min.js'

PAGES_LEAFLET = ['logx_carte.html', 'logx_departements.html', 'logx_logbook.html',
                 'logx_wall.html', 'logx_websdr.html']
PAGE_CHART = 'logx_logbook.html'

_CDN = ('unpkg.com', 'cdnjs.cloudflare', 'cdn.jsdelivr')


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


def test_pages_referencent_le_vendor_local():
    for nom in PAGES_LEAFLET:
        html = _lire(nom)
        assert LEAFLET_JS in html, nom
        assert LEAFLET_CSS in html, nom
    assert CHART_JS in _lire(PAGE_CHART)


def test_plus_aucun_cdn_pour_leaflet_ni_chart():
    # Aucune ligne ne doit mentionner un CDN externe ET (leaflet|chart) :
    # c'est ce qui casse en zone blanche.
    for nom in PAGES_LEAFLET:
        for ligne in _lire(nom).splitlines():
            bas = ligne.lower()
            if any(cdn in bas for cdn in _CDN):
                assert 'leaflet' not in bas and 'chart' not in bas, (nom, ligne.strip())


def test_fichiers_vendor_reels():
    # présents ET substantiels ET signature de la vraie lib (pas un stub 404).
    js = _lire('vendor/leaflet/leaflet.min.js')
    assert len(js) > 100_000 and 'leaflet' in js.lower()
    css = _lire('vendor/leaflet/leaflet.min.css')
    assert len(css) > 5_000 and '.leaflet-' in css
    chart = _lire('vendor/chartjs/chart.umd.min.js')
    assert len(chart) > 100_000 and 'Chart.js' in chart


def test_leaflet_css_images_presentes():
    # chaque url(images/…) du CSS doit résoudre dans vendor/leaflet/images/,
    # sinon fonds/contrôles cassés hors-ligne.
    import re
    css = _lire('vendor/leaflet/leaflet.min.css')
    refs = set(re.findall(r'url\(\s*(images/[^)\s]+?)\s*\)', css))
    assert refs, 'aucune référence images/ trouvée dans le CSS'
    for ref in refs:
        p = os.path.join(BASE, 'vendor', 'leaflet', ref)
        assert os.path.isfile(p), ref


def test_sw_precache_inclut_le_vendor():
    # logx_sw.js doit précacher les libs (SHELL) : sans ça, 1er chargement
    # hors-ligne = pas encore en cache = page morte.
    sw = _lire('logx_sw.js')
    for p in (LEAFLET_JS, LEAFLET_CSS, CHART_JS):
        assert p in sw, p


@pytest.fixture
def server():
    import logx_http as httpmod
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


# On teste le service des PETITS fichiers du vendor (CSS 10.9 Ko, PNG 1.5 Ko) :
# ça prouve que /vendor/… ET /vendor/leaflet/images/… (sous-dossiers imbriqués)
# sont servis, confinés sous concours/, avec le bon Content-Type. Le mapping
# .js -> application/javascript est le MÊME bloc de code que .css/.png
# (logx_http.py) ; on NE télécharge PAS les gros .js (147/208 Ko) sur HTTP ici
# car un antivirus/inspecteur réseau LOCAL (Avast sur ce poste) coupe les
# grosses réponses localhost -> reset/timeout de test (artefact machine
# documenté à logx_http.py, autour du Content-Length ; absent en CI Linux).
# La réalité des gros .js est couverte par test_fichiers_vendor_reels (disque)
# et leur précache par test_sw_precache_inclut_le_vendor.
@pytest.mark.parametrize('chemin, ctype', [
    (LEAFLET_CSS, 'text/css'),
    ('/vendor/leaflet/images/marker-icon.png', 'image/png'),
])
def test_serveur_sert_le_vendor(server, chemin, ctype):
    with urllib.request.urlopen(server + chemin, timeout=15) as r:
        assert r.status == 200
        assert ctype in r.headers.get('Content-Type', '')
        assert len(r.read()) > 400
