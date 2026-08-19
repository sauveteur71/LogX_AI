# -*- coding: utf-8 -*-
"""Le panneau ÉMISSION ne doit jamais s'éloigner à mesure que le trafic arrive.

Défaut signalé en trafic réel par F4GLD (19/08/2026) : « je suis obligé de
scroller tout en bas pour voir l'émission ». La liste des décodages grandit
d'un cycle de 15 s à l'autre, et TOUT ce qui vit en dessous descendait avec
elle. Émettre est le chemin critique de cette page ; sa position ne peut pas
dépendre de la quantité de trafic reçu.

Le plafond de 60 lignes déjà présent dans ajouterDecodage() ne protégeait de
rien ici : il borne la MÉMOIRE (pas de fuite sur une nuit d'écoute), pas la
HAUTEUR. 60 lignes occupent ~1500 px, soit près de deux écrans — le panneau
Émission restait hors de vue.

Ce fichier fige la structure qui borne la hauteur. Mesuré en navigateur réel
(1500x900, 60 lignes) après correction : liste de 1521 px qui défile dans un
cadre de 447 px, hauteur totale de page 1178 px au lieu de ~2700, et le
panneau Émission entièrement visible sans que rien ne le déplace.
"""
import io
import os
import re

import pytest

ICI = os.path.dirname(os.path.abspath(__file__))
FT8_HTML = os.path.join(ICI, '..', 'logx_ft8.html')


def _lire():
    return io.open(FT8_HTML, encoding='utf-8').read()


@pytest.fixture(scope='module')
def src():
    return _lire()


def _bloc_css(src, selecteur):
    """Corps de la règle CSS `selecteur`, sans les commentaires alentour.

    Un test qui cherche une propriété dans le fichier ENTIER est satisfait par
    le commentaire qui l'explique — piège rencontré plusieurs fois dans ce
    dépôt. On isole donc la règle elle-même.
    """
    m = re.search(re.escape(selecteur) + r'\s*\{([^}]*)\}', src)
    assert m, 'règle CSS absente : %s' % selecteur
    return m.group(1)


def test_EMISSION_est_le_premier_panneau_de_la_colonne(src):
    """Borner la hauteur ne suffisait pas : F4GLD l'a reverifie en trafic et a
    tranche — « toujours un scroll, passe le cadre emission au dessus du cadre
    reception ».

    La borne avait ramene le defilement de ~2400 px a 278 px, pas a zero :
    l'en-tete de la page (titre, intro, aide poste) occupe 242 px et la colonne
    ne peut pas tenir dessous. Placer EMISSION en tete de colonne le rend
    visible sans le moindre defilement, quelle que soit la hauteur de fenetre.

    Mesure en navigateur reel (1683x940, 60 lignes, scroll a 0) : panneau
    Emission de y=242 a y=401, case « Activer l'emission » et champ du message
    entierement visibles.
    """
    debut = src.index('<div class="center-col">')
    fin = src.index('COLONNE DROITE', debut)
    zone = src[debut:fin]
    iEmission = zone.index('<div class="panel-title">Émission</div>')
    iReception = zone.index('<div class="panel-title">Réception</div>')
    assert iEmission < iReception, (
        'ÉMISSION doit précéder RÉCEPTION dans la colonne centrale — sinon la '
        'liste des décodages le repousse hors de l\'écran, ce qui est '
        'exactement le défaut signalé')


def test_la_liste_des_decodages_vit_dans_un_cadre_qui_defile(src):
    """Sans conteneur de défilement, la liste pousse le panneau Émission vers
    le bas à chaque cycle. C'est LE défaut d'origine."""
    corps = _bloc_css(src, '.decodes-scroll')
    assert 'overflow-y:auto' in corps.replace(' ', ''), (
        'le cadre de la liste doit défiler : %r' % corps)


def test_le_tbody_des_decodages_est_bien_DANS_ce_cadre(src):
    """Le cadre ne sert à rien si le tableau est resté à côté. On vérifie
    l'IMBRICATION, pas la simple présence des deux éléments."""
    i = src.index('<div class="decodes-scroll">')
    j = src.index('<tbody id="decodesBody">')
    # Fermeture du cadre : le premier </div> qui suit le message « aucun
    # décodage », lui-même à l'intérieur.
    k = src.index('id="decodesVide"')
    assert i < j < k, (
        'decodesBody (%d) et decodesVide (%d) doivent être entre le début du '
        'cadre (%d) et sa fermeture' % (j, k, i))


def test_la_colonne_centrale_a_une_hauteur_bornee_par_l_ecran(src):
    """C'est ce qui garantit que le panneau Émission tient dans la fenêtre :
    la colonne ne peut pas dépasser la hauteur visible."""
    corps = _bloc_css(src, '.center-col').replace(' ', '')
    assert 'max-height:calc(100vh' in corps, (
        'la colonne centrale doit être bornée à la hauteur de fenêtre : %r'
        % corps)
    assert 'position:sticky' in corps, (
        'bornée mais non collante, la colonne sortirait de l\'écran au premier '
        'défilement de page : %r' % corps)


def test_la_colonne_centrale_est_une_pile_verticale_flexible(src):
    """min-height:0 sur le panneau Réception est la condition SANS LAQUELLE un
    enfant flex refuse de descendre sous la hauteur de son contenu : le cadre
    déborderait au lieu de faire défiler, et le défaut reviendrait intact
    malgré un overflow-y correctement posé."""
    colonne = _bloc_css(src, '.center-col').replace(' ', '')
    assert 'display:flex' in colonne and 'flex-direction:column' in colonne, (
        'la colonne doit être une pile flex : %r' % colonne)
    rx = _bloc_css(src, '#panelRx').replace(' ', '')
    assert 'min-height:0' in rx, (
        'sans min-height:0 le panneau Réception ne peut pas rétrécir : %r' % rx)
    liste = _bloc_css(src, '.decodes-scroll').replace(' ', '')
    assert 'flex:1' in liste, (
        'la liste doit absorber la place restante, sinon le panneau Émission '
        'flotte au milieu de la fenêtre : %r' % liste)


def test_l_entete_de_colonnes_reste_lisible_pendant_le_defilement(src):
    """Une liste qui défile sous un en-tête transparent laisse les lignes
    passer PAR-DESSUS lui en restant visibles."""
    corps = _bloc_css(src, 'table.decodes thead th').replace(' ', '')
    assert 'position:sticky' in corps, corps
    assert 'background:var(--bg2)' in corps, (
        "l'en-tête collant doit être opaque, et via un jeton de thème pour "
        'rester correct en mode jour comme en mode nuit : %r' % corps)


def test_sur_un_ecran_etroit_la_liste_reste_bornee(src):
    """En dessous de 1300 px la mise en page passe sur une seule colonne et le
    collage n'a plus de sens — mais si RIEN ne borne alors la liste, le défaut
    revient à l'identique sur les petits écrans."""
    m = re.search(r'@media \(max-width:1300px\)\{(.*?)\}\}', src, re.S)
    assert m, 'la règle @media de repli a disparu'
    bloc = m.group(1).replace(' ', '')
    assert '.center-col{position:static' in bloc, (
        'la colonne doit redevenir statique en une seule colonne : %r' % bloc)
    assert '.decodes-scroll{max-height:' in bloc, (
        'la liste doit garder une hauteur bornée en une seule colonne, sinon '
        'le panneau Émission repart vers le bas : %r' % bloc)
