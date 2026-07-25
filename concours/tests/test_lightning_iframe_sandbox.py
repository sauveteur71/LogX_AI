# -*- coding: utf-8 -*-
"""L'iframe Blitzortung de logx_propagation.html doit rester SANDBOXÉE, et
sans 'allow-top-navigation'.

Défaut constaté en usage réel : l'opérateur ouvrait la page PROPAGATION et,
une dizaine de secondes plus tard, tout son onglet basculait sur
blitzortung.org — LogX AI disparaissait sans qu'il ait rien demandé. Cause :
la page encadrée embarque un « frame-buster » (du JavaScript qui force
top.location pour s'extraire d'un cadre). Un simple contrôle des en-têtes
X-Frame-Options/CSP au moment de l'intégration ne le détecte PAS : rien
n'interdit l'encadrement, c'est le script de la page qui s'en échappe une
fois chargé, et seulement après un délai — d'où le fait que la vérification
initiale (immédiate) ait conclu à tort que l'intégration était sûre.

La seule parade fiable est côté navigateur : un iframe sandboxé sans
'allow-top-navigation' se voit REFUSER la navigation du contexte parent,
quoi que fasse son script. Ces tests figent cette garantie, car retirer
l'attribut ne casse rien de visible immédiatement (la carte s'affiche
toujours) — la régression ne se manifesterait qu'à l'usage, une dizaine de
secondes plus tard, exactement comme la première fois.
"""
import os
import re

CONCOURS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(CONCOURS_DIR, 'logx_propagation.html')


def _iframes(src):
    """Toutes les balises <iframe ...> du fichier, attributs bruts inclus."""
    return re.findall(r'<iframe\b[^>]*>', src, flags=re.IGNORECASE | re.DOTALL)


def _lire():
    with open(HTML_PATH, encoding='utf-8') as f:
        return f.read()


def test_iframe_foudre_presente_et_sandboxee():
    """L'iframe tierce existe et porte bien un attribut sandbox."""
    frames = [f for f in _iframes(_lire()) if 'blitzortung' in f.lower()]
    assert frames, "l'iframe Blitzortung a disparu de logx_propagation.html"
    for f in frames:
        assert 'sandbox=' in f.lower(), (
            "iframe Blitzortung SANS sandbox : la page tierce peut de nouveau "
            "detourner l'onglet entier (frame-busting)\n" + f)


def test_iframe_foudre_interdit_la_navigation_du_parent():
    """Le coeur du correctif : 'allow-top-navigation' (sous toutes ses formes,
    y compris la variante ...-by-user-activation) ne doit JAMAIS etre accorde,
    sinon le frame-buster reprend la main sur l'onglet."""
    for f in _iframes(_lire()):
        if 'blitzortung' not in f.lower():
            continue
        assert 'allow-top-navigation' not in f.lower(), (
            "'allow-top-navigation' reautorise la page tierce a remplacer "
            "l'onglet LogX AI — c'est exactement le defaut d'origine\n" + f)


def test_toute_iframe_tierce_de_la_page_est_sandboxee():
    """Garde-fou generique : une future iframe vers un autre site tiers
    (carte, service externe...) doit elle aussi etre sandboxee — le meme
    piege se reproduirait a l'identique."""
    for f in _iframes(_lire()):
        if not re.search(r'src\s*=\s*["\']https?://', f, flags=re.IGNORECASE):
            continue                      # iframe locale : hors sujet ici
        assert 'sandbox=' in f.lower(), (
            'iframe tierce sans sandbox dans logx_propagation.html\n' + f)


def test_sandbox_conserve_le_necessaire_a_l_affichage():
    """Non-regression inverse : sandboxer ne doit pas vider la carte de sa
    substance. La carte est dynamique (JavaScript) et interroge sa propre
    origine — sans ces deux permissions, le panneau resterait vide, ce qui
    serait une regression tout aussi visible pour l'operateur."""
    frames = [f for f in _iframes(_lire()) if 'blitzortung' in f.lower()]
    assert frames
    sandbox = re.search(r'sandbox\s*=\s*["\']([^"\']*)["\']', frames[0],
                        flags=re.IGNORECASE)
    assert sandbox, 'attribut sandbox illisible'
    jetons = sandbox.group(1).lower().split()
    assert 'allow-scripts' in jetons, 'carte dynamique : allow-scripts requis'
    assert 'allow-same-origin' in jetons, (
        'la carte interroge sa propre origine : allow-same-origin requis')
