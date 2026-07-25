# -*- coding: utf-8 -*-
"""Foudre : plus d'iframe Blitzortung encadree dans LogX AI, et un cadre
tiers ne peut jamais revenir sans bac a sable.

Historique du defaut, qui explique pourquoi ces tests restent :

1) La carte Blitzortung etait encadree en pleine page dans PROPAGATION. La
   page tierce embarque un « frame-buster » (du JavaScript qui force
   top.location pour s'extraire d'un cadre) : une dizaine de secondes apres
   l'ouverture de PROPAGATION, tout l'onglet basculait sur blitzortung.org et
   LogX AI disparaissait sans que l'operateur ait rien demande. Un controle
   des en-tetes X-Frame-Options/CSP au moment de l'integration ne le detecte
   PAS : rien n'interdit l'encadrement, c'est le script de la page qui s'en
   echappe une fois charge, et seulement apres un delai.

2) Premier correctif (commit 20307e3) : sandboxer l'iframe SANS
   'allow-top-navigation' — la seule parade fiable, appliquee par le
   navigateur lui-meme quoi que fasse le script encadre.

3) Correctif definitif (ici) : il n'y a plus d'iframe du tout. Un panneau de
   420 px occupe en permanence par une carte qu'on ne consulte qu'en cas
   d'orage a ete remplace par une PASTILLE D'ALERTE dans la barre de statut
   (#rcsbStormItem), presente sur toutes les pages, qui ouvre la carte dans un
   onglet separe. Sans cadre, le frame-buster n'a plus aucune prise.

Les tests ci-dessous figent les deux moities : l'iframe ne doit pas revenir,
et si un jour un AUTRE cadre tiers est ajoute a cette page, il devra etre
sandboxe — sinon on rejouerait exactement le meme scenario, avec la meme
verification initiale faussement rassurante.
"""
import os
import re

CONCOURS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(CONCOURS_DIR, 'logx_propagation.html')
STATUSBAR_PATH = os.path.join(CONCOURS_DIR, 'logx_statusbar.js')
WEATHER_PATH = os.path.join(CONCOURS_DIR, 'logx_weather.py')


def _iframes(src):
    """Toutes les balises <iframe ...> du fichier, attributs bruts inclus."""
    return re.findall(r'<iframe\b[^>]*>', src, flags=re.IGNORECASE | re.DOTALL)


def _lire(chemin=HTML_PATH):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def _sans_commentaires(src):
    """Les commentaires expliquent le demenagement : ce ne sont pas des
    references vivantes, il ne faut pas les compter comme du marquage."""
    src = re.sub(r'<!--.*?-->', '', src, flags=re.DOTALL)
    return '\n'.join(l for l in src.split('\n')
                     if not l.lstrip().startswith(('//', '*', '/*')))


# ── L'iframe a disparu ──────────────────────────────────────────────────────

def test_plus_aucune_iframe_blitzortung():
    frames = [f for f in _iframes(_lire()) if 'blitzortung' in f.lower()]
    assert not frames, (
        "l'iframe Blitzortung est de retour dans logx_propagation.html : la "
        "page tierce peut de nouveau detourner l'onglet entier\n"
        + '\n'.join(frames))


def test_plus_de_panneau_foudre_dans_la_page():
    """Le marquage du panneau doit avoir suivi l'iframe : un panneau vide de
    420 px ne leverait aucune erreur, il occuperait juste la place."""
    src = _sans_commentaires(_lire())
    for reste in ('FOUDRE EN DIRECT', 'lightning-frame'):
        assert reste not in src, (
            'reste du panneau foudre dans logx_propagation.html : ' + reste)


def test_toute_iframe_tierce_de_la_page_reste_sandboxee():
    """Garde-fou generique, la vraie protection a long terme : une future
    iframe vers un autre site tiers (carte, service externe...) doit etre
    sandboxee et privee de 'allow-top-navigation' — sous toutes ses formes, y
    compris la variante ...-by-user-activation."""
    for f in _iframes(_lire()):
        if not re.search(r'src\s*=\s*["\']https?://', f, flags=re.IGNORECASE):
            continue                      # iframe locale : hors sujet ici
        assert 'sandbox=' in f.lower(), (
            'iframe tierce sans sandbox dans logx_propagation.html\n' + f)
        assert 'allow-top-navigation' not in f.lower(), (
            "'allow-top-navigation' autorise la page tierce a remplacer "
            "l'onglet LogX AI — c'est exactement le defaut d'origine\n" + f)


# ── La pastille de la barre de statut l'a remplacee ─────────────────────────

def test_pastille_orage_dans_la_barre_de_statut():
    """Supprimer l'iframe sans la remplacer aurait retire une information de
    securite materiel (orage = debrancher les antennes) sans rien dire."""
    src = _lire(STATUSBAR_PATH)
    assert 'rcsbStormItem' in src, 'pastille orage absente de la barre de statut'
    assert '/data/weather' in src, "la pastille n'interroge aucune source meteo"
    assert 'blitzortung.org' in src.lower(), (
        'la pastille doit toujours donner acces a la carte de foudre')


def test_la_carte_de_foudre_s_ouvre_hors_cadre():
    """Le lien de la pastille doit ouvrir un ONGLET (target=_blank), pas
    rouvrir un cadre : c'est ce qui rend le frame-busting sans objet."""
    src = _lire(STATUSBAR_PATH)
    m = re.search(r'<a id="rcsbStormLink"[^>]*>', src)
    assert m, 'lien de la pastille orage introuvable'
    balise = m.group(0)
    assert 'target="_blank"' in balise, balise
    assert 'rel="noopener noreferrer"' in balise, balise
    assert '<iframe' not in src.lower(), (
        'la barre de statut ne doit encadrer aucun site tiers')


def test_la_pastille_ne_devine_pas_l_orage_dans_une_phrase_francaise():
    """Le serveur expose un booleen `storm` DEDIE (codes WMO 95/96/99). Sans
    lui, le client devrait chercher le mot « ORAGE » dans `warn`, une phrase
    francaise qui agrege aussi rafales et gel : le premier reformulage — ou la
    traduction de l'interface — eteindrait l'alerte en silence."""
    weather = _lire(WEATHER_PATH)
    assert re.search(r"'storm':\s*code in \(95, 96, 99\)", weather), (
        "logx_weather.py n'expose plus le booleen `storm`")
    bar = _sans_commentaires(_lire(STATUSBAR_PATH))
    assert 'd.storm' in bar, "la pastille n'utilise pas le booleen `storm`"
    # Le mot ORAGE peut rester dans le LIBELLE affiche ; ce qui est interdit
    # c'est de s'en servir comme test.
    assert not re.search(r"(indexOf|includes|search|match)\(\s*['\"][^'\"]*ORAGE",
                         bar), (
        "la pastille redevine l'orage en cherchant du texte francais")
