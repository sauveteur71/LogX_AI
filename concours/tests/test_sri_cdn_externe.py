# -*- coding: utf-8 -*-
"""A09 (docs/FEUILLE_DE_ROUTE.md) : intégrité SRI sur les <script src="https://...">
et <link href="https://....css"> externes.

Sans `integrity`, un CDN compromis ou un man-in-the-middle sur un réseau non
fiable (hotspot, WiFi radio-club) peut substituer un fichier JS/CSS arbitraire
à celui attendu -- le navigateur l'exécute sans broncher. `integrity` fait
échouer le CHARGEMENT si le hash ne correspond pas ; `crossorigin` est requis
pour que le navigateur calcule ce hash sur une ressource cross-origin.

Garde-fou structurel : toute balise externe future doit porter les deux
attributs, sinon ce test échoue -- pas une simple vérification ponctuelle.

ÉVOLUTION (repli CDN local, demande F4GLD) : Leaflet + Chart.js sont désormais
VENDORISÉS localement (`vendor/`), et plus aucune page ne charge de .js/.css
depuis un CDN externe. L'autonomie « zone blanche » est un garde-fou PLUS FORT
que le SRI (rien à substituer s'il n'y a rien d'externe). La contre-épreuve
« au moins N balises CDN à vérifier » (qui n'avait de sens que tant qu'il en
restait) est donc remplacée par l'invariant d'autonomie : ZÉRO balise CDN
externe .js/.css. Le garde-fou SRI par-balise reste, au cas où une balise
externe serait ré-introduite un jour -- elle devrait alors porter integrity+
crossorigin."""
import glob
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_EXTERNAL_TAG_RE = re.compile(
    r'<(script|link)\b[^>]*\b(?:src|href)="https://[^"]+\.(?:js|css)"[^>]*>',
    re.IGNORECASE)


def _external_tags_sans_sri():
    manquants = []
    for path in glob.glob(os.path.join(BASE, '*.html')):
        with open(path, encoding='utf-8') as f:
            html = f.read()
        for m in _EXTERNAL_TAG_RE.finditer(html):
            texte = m.group(0)
            if 'integrity=' not in texte or 'crossorigin=' not in texte:
                manquants.append((os.path.basename(path), texte[:120]))
    return manquants


def test_toute_balise_cdn_externe_porte_integrity_et_crossorigin():
    manquants = _external_tags_sans_sri()
    assert manquants == [], (
        f"balise(s) <script src=https://...>/<link href=https://...> sans "
        f"integrity/crossorigin : {manquants}")


def test_aucune_balise_cdn_externe_js_css():
    """Autonomie « zone blanche » (repli CDN local) : PLUS AUCUNE page ne
    charge de .js/.css depuis un CDN externe -- tout est vendorisé dans
    `vendor/`. Sans Internet (DXpédition, /P, réseau bloquant les CDN), la
    carte (Leaflet) et les stats (Chart.js) tiennent au lieu de mourir
    (`L`/`Chart` undefined). Invariant PLUS FORT que le SRI : rien à
    substituer s'il n'y a rien d'externe. Toute ré-introduction d'un CDN
    .js/.css (fût-il avec SRI) fait ROUGIR ce test -- décision consciente
    requise."""
    externes = []
    for path in glob.glob(os.path.join(BASE, '*.html')):
        with open(path, encoding='utf-8') as f:
            for m in _EXTERNAL_TAG_RE.finditer(f.read()):
                externes.append((os.path.basename(path), m.group(0)[:120]))
    assert externes == [], f"balise(s) CDN externe .js/.css subsistante(s) : {externes}"
