# -*- coding: utf-8 -*-
"""A09 (docs/FEUILLE_DE_ROUTE.md) : intégrité SRI sur les <script src="https://...">
et <link href="https://....css"> externes.

Sans `integrity`, un CDN compromis ou un man-in-the-middle sur un réseau non
fiable (hotspot, WiFi radio-club) peut substituer un fichier JS/CSS arbitraire
à celui attendu -- le navigateur l'exécute sans broncher. `integrity` fait
échouer le CHARGEMENT si le hash ne correspond pas ; `crossorigin` est requis
pour que le navigateur calcule ce hash sur une ressource cross-origin.

Garde-fou structurel : toute balise externe future doit porter les deux
attributs, sinon ce test échoue -- pas une simple vérification ponctuelle."""
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


def test_au_moins_une_balise_cdn_est_bien_verifiee_par_ce_test():
    """Contre-épreuve structurelle : si plus aucune page ne charge de CDN
    externe, le test ci-dessus passerait TOUJOURS trivialement (liste vide
    par absence de sujet, pas par conformité) -- ce test s'assure qu'il y a
    bien quelque chose à vérifier."""
    trouvees = 0
    for path in glob.glob(os.path.join(BASE, '*.html')):
        with open(path, encoding='utf-8') as f:
            trouvees += len(_EXTERNAL_TAG_RE.findall(f.read()))
    assert trouvees >= 5, f"seulement {trouvees} balise(s) CDN externe trouvée(s) -- motif de recherche cassé ?"
