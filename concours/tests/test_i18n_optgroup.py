# -*- coding: utf-8 -*-
"""Les titres de GROUPES dans un menu déroulant se traduisaient-ils ? Non.

DÉFAUT TROUVÉ EN VÉRIFIANT À L'ÉCRAN, pas en lisant le code. En espagnol, le
sélecteur de satellite affichait ses choix traduits — « Geoestacionario » n'y
était pas — tandis que les intitulés qui les REGROUPENT restaient en français,
dans le même menu. Un utilisateur y voit deux langues côte à côte.

LA CAUSE : `label` d'un `<optgroup>` est un ATTRIBUT, pas un nœud texte. Le
TreeWalker qui parcourt la page ne peut pas le voir, et la boucle des attributs
ne traitait que `title` et `placeholder`. C'est la même famille de défaut que
les `<option>` autrefois exclus par erreur : le dictionnaire peut être complet,
si rien ne va lire l'endroit, rien ne se traduit.

DEUXIÈME DÉFAUT, dans mon propre outillage : « Relais FM » n'avait aucune
entrée parce que mon détecteur « ça ressemble à du français » cherchait des
accents ou des mots-outils — et cette expression n'en a aucun. Sur un ensemble
aussi petit, prendre TOUT et regarder vaut mieux que filtrer.
"""
import glob
import html as H
import io
import json
import os
import re
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

I18N = os.path.join(CONCOURS, 'logx_i18n.js')


# Les clés s'écrivent avec DEUX styles de guillemets : le dictionnaire de base
# de logx_i18n.js utilise des apostrophes simples et empile plusieurs paires par
# ligne, les objets correctifs des guillemets doubles. Ne lire que le second
# style revient à ignorer le dictionnaire principal — donc à croire manquantes
# des centaines de clés qui existent.
_PAIRE = re.compile(
    r"""(?P<q>['"])(?P<cle>(?:[^'"\\]|\\.|(?!(?P=q))['"])*)(?P=q)\s*:\s*"""
    r"""(?P<q2>['"])""")


def _cles():
    src = io.open(I18N, encoding='utf-8').read()
    out = set()
    for m in _PAIRE.finditer(src):
        k = m.group('cle')
        out.add(k.replace('\\\\', '\x00').replace("\\'", "'")
                 .replace('\\"', '"').replace('\x00', '\\'))
    return out


def _optgroups():
    """(page, label) pour chaque <optgroup> de chaque page."""
    trouves = []
    for f in sorted(glob.glob(os.path.join(CONCOURS, 'logx_*.html'))):
        src = io.open(f, encoding='utf-8').read()
        for lab in re.findall(r'<optgroup[^>]*label="([^"]+)"', src):
            trouves.append((os.path.basename(f), H.unescape(lab).strip()))
    return trouves


# ─── Le moteur va-t-il LIRE cet attribut ? ───────────────────────────────────

def test_LE_MOTEUR_TRADUIT_L_ATTRIBUT_label():
    """Sans cette ligne, le dictionnaire a beau être complet : personne ne va
    chercher la valeur, et les titres de groupes restent en français au milieu
    de choix traduits."""
    src = io.open(I18N, encoding='utf-8').read()
    assert "querySelectorAll('optgroup[label]')" in src
    bloc = src[src.index("querySelectorAll('optgroup[label]')"):]
    bloc = bloc[:bloc.index('\n    });') + 8]
    assert "translateAttr(dict, el, 'label')" in bloc


def test_le_label_passe_par_translateAttr_comme_title():
    """translateAttr mémorise le français d'origine ; sans lui, revenir au
    français laisserait la valeur traduite en place — un aller sans retour."""
    src = io.open(I18N, encoding='utf-8').read()
    i = src.index("querySelectorAll('optgroup[label]')")
    # la boucle des attributs classiques existe toujours et juste avant
    avant = src[:i]
    assert "'title', 'placeholder', 'alt', 'aria-label'" in avant


# ─── La liste des attributs porteurs est-elle COMPLETE ? ─────────────────────

def _attributs_traites():
    """Ce que le moteur va reellement chercher, tableau de taille quelconque."""
    src = io.open(I18N, encoding='utf-8').read()
    traites = set(re.findall(r"translateAttr\(dict, el, '([a-z-]+)'\)", src))
    for bloc in re.findall(r"\[((?:'[a-z-]+',?\s*)+)\]\.forEach\(", src):
        traites |= set(re.findall(r"'([a-z-]+)'", bloc))
    return traites


@pytest.mark.parametrize('attr', ['title', 'placeholder', 'label', 'alt', 'aria-label'])
def test_TOUS_LES_ATTRIBUTS_PORTEURS_DE_TEXTE_SONT_LUS(attr):
    """Recensement fait sur toutes les pages : title 63, placeholder 23,
    label 3, alt 1, aria-label 1. Ce sont les cinq seuls attributs dont la
    valeur est lue par un utilisateur.

    `alt` et `aria-label` ne SAUTENT PAS AUX YEUX quand ils restent en
    français — l'un ne s'affiche que si l'image manque, l'autre n'est
    prononcé que par un lecteur d'écran. C'est exactement pourquoi ils
    étaient restés dehors : personne ne les voit.
    """
    assert attr in _attributs_traites()


def test_alt_et_aria_label_ont_leur_traduction():
    """Le moteur peut bien les lire : sans entree, il rendrait la cle telle
    quelle et rien ne changerait."""
    cles = _cles()
    assert 'Vues de la propagation' in cles
    assert any(k.startswith('Carte mondiale de la MUF') for k in cles)


# ─── Le dictionnaire est-il complet pour ces titres ? ────────────────────────

def test_TOUS_les_titres_de_groupes_ont_leur_entree():
    """On ne filtre pas sur « ça ressemble à du français » : c'est ce filtre
    qui a laissé passer « Relais FM », qui n'a ni accent ni mot-outil."""
    cles = _cles()
    manquants = sorted({(p, lab) for p, lab in _optgroups() if lab not in cles})
    assert manquants == [], manquants


@pytest.mark.parametrize('libelle', ['Géostationnaire', 'Relais FM',
                                     'Transpondeur linéaire (SSB/CW)'])
def test_les_groupes_du_selecteur_satellite_sont_traduits(libelle):
    """Ce sélecteur est le cas qui a revele le defaut."""
    assert libelle in _cles()


def test_RELAIS_FM_le_piege_du_detecteur_de_francais():
    """Verrouille la RAISON du test ci-dessus. « Relais FM » est du francais
    sans le moindre signe distinctif : ni accent, ni article, ni preposition.
    Tout outil qui detecte le francais par ces marqueurs le rate."""
    marqueurs = re.compile(r'[éèêàçùôîûï]|\b(le|la|les|un|une|des|du|de|et|ou|pour|sur|dans)\b',
                           re.I)
    assert not marqueurs.search('Relais FM'), \
        'si ce test tombe, le detecteur aurait trouve le libelle et la lecon ne tient plus'
    assert 'Relais FM' in _cles()


def test_il_y_a_bien_des_optgroups_a_proteger():
    """Garde-fou du garde-fou : si l'extraction ne trouvait plus rien, les
    tests ci-dessus passeraient tous en ne verifiant rien."""
    assert len(_optgroups()) >= 3
