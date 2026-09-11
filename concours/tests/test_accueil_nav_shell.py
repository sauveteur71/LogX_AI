# -*- coding: utf-8 -*-
"""Barre de navigation standard sur l'accueil (fusion incr. 5a, 11/09/2026).

logx_accueil.html était volontairement dépourvue de la nav partagée des 13
autres pages (page minimaliste) — mais CHASSE doit pouvoir y rediriger
(incr. 5) sans priver l'opérateur de tout accès aux autres pages. Ce fichier
verrouille l'ajout : nav présente, scripts requis chargés, ET la règle CSS
`.app-nav{display:flex...}` elle-même présente comme règle DISTINCTE (pas
seulement `.app-nav a{...}`).

Piège réellement rencontré en construisant cet incrément, vérifié en
navigateur réel (Playwright) : un commentaire CSS contenait `.nav-tools*/
.rcb-*` — la sous-chaîne `*/` fermait le commentaire PRÉMATURÉMENT, ce qui
rendait le texte suivant invalide et faisait disparaître la règle
`.app-nav{display:flex}` du CSSOM du navigateur alors qu'elle était bien
présente, telle quelle, dans le HTML servi (`curl` la voyait, Chrome non) —
la nav s'empilait verticalement, plein écran. `test_le_css_ne_ferme_pas_de_
commentaire_prematurement` verrouille cette classe de piège pour tout le
bloc `<style>` de cette page."""
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_accueil.html')


def _lire():
    with open(HTML, encoding='utf-8') as f:
        return f.read()


def test_nav_app_nav_presente():
    assert '<nav class="app-nav"' in _lire()


def test_regle_app_nav_display_flex_est_bien_une_regle_css_distincte():
    """Pas seulement `.app-nav a{...}` : la règle SUR LE CONTENEUR lui-même,
    sans laquelle les liens s'empilent verticalement plein écran (piège
    réel, voir l'en-tête de ce fichier)."""
    src = _lire()
    assert re.search(r'\.app-nav\s*\{\s*display\s*:\s*flex', src), (
        "règle .app-nav{display:flex...} introuvable comme règle distincte "
        "(un commentaire mal fermé juste avant l'a déjà fait disparaître une fois)")


def test_le_css_ne_ferme_pas_de_commentaire_prematurement():
    """Un `*/` À L'INTÉRIEUR du texte voulu d'un commentaire referme le
    commentaire AU PREMIER `*/` rencontré (c'est ainsi qu'un vrai parseur CSS
    lit `/* ... */` — non-greedy, pas de commentaires imbriqués) : tout le
    texte voulu après ce point devient du CSS littéral, jusqu'au `*/`
    SUIVANT qui, lui, n'a plus de `/*` pour le fermer et reste orphelin.

    Contre-épreuve faite à la main sur CETTE régression précise (réintroduite
    puis retirée) : une version naïve qui cherche `*/` DANS le groupe capturé
    par un regex non-greedy `/\\*(.*?)\\*/` ne peut JAMAIS le trouver (le
    regex s'arrête par construction au premier `*/`, donc le groupe capturé
    ne le contient jamais) — ce test-ci vérifie au contraire qu'IL NE RESTE
    AUCUN `*/` ORPHELIN une fois les commentaires correctement retirés avec
    cette même sémantique premier-match, ce qui détecte la fuite de texte."""
    src = _lire()
    m = re.search(r'<style>(.*?)</style>', src, re.S)
    assert m, 'bloc <style> introuvable'
    style = m.group(1)
    sans_commentaires = re.sub(r'/\*.*?\*/', '', style, flags=re.S)
    assert '*/' not in sans_commentaires, (
        "un '*/' orphelin subsiste après retrait des commentaires (premier-match) "
        "-- signe qu'un commentaire s'est refermé au milieu de son propre texte")


def test_scripts_nav_charges():
    src = _lire()
    for script in ('logx_statusbar.js', 'logx_i18n.js', 'logx_search.js'):
        assert '<script src="%s">' % script in src, script


def test_nav_dans_lordre_attendu_des_13_pages():
    """Réutilise le contrat déjà verrouillé par test_page_chasse_split.py
    (ORDRE_NAV_ATTENDU) plutôt que de le redupliquer ici."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from test_page_chasse_split import ORDRE_NAV_ATTENDU, _nav
    cibles = re.findall(r'<a href="([^"]+)"', _nav(_lire()))
    assert cibles == ORDRE_NAV_ATTENDU


def test_lien_chasse_a_un_id_pour_le_marquage_actif_dynamique():
    """Contrairement aux 13 pages (active STATIQUE, chacune marque sa propre
    entrée), l'accueil sert PLUSIEURS rôles (accueil normal + future
    destination du redirect CHASSE, incr. 5b) : l'entrée CHASSE porte un id
    pour un marquage actif dynamique en JS plutôt qu'un class="active" en dur."""
    src = _lire()
    assert re.search(r'<a href="logx_chasse\.html" id="navChasse"', src)
