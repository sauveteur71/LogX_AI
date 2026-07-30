# -*- coding: utf-8 -*-
"""Bandscope détaché : deux indicatifs proches ne doivent JAMAIS se superposer.

DÉFAUT SIGNALÉ PAR L'UTILISATEUR, capture d'écran à l'appui (30/07/2026) : sur
15 m, trois stations à 21.076 et trois autres à 21.140 écrivaient leurs
indicatifs exactement au même endroit — un pâté noir illisible. Et deux
fréquences voisines, VE6CQ à 21.270 et YC7ONI à 21.287, se télescopaient en
« VE6CQC7ONI ».

DEUX CAUSES DIFFÉRENTES, souvent confondues :
  1. MÊME fréquence. En FT8/FT4 tout le monde émet sur LA porteuse de la bande.
     Trois stations à 21.076, c'est trois barres au même pixel. Aucun écart
     horizontal ne peut les séparer : il faut EMPILER.
  2. Fréquences VOISINES. 17 kHz d'écart valent 11 px de large, une étiquette
     en fait 50. Il faut décaler VERTICALEMENT le second bloc.

La fonction est EXÉCUTÉE dans un moteur V8 à partir du fichier livré, et le SVG
produit est relu pour vérifier qu'aucune paire d'étiquettes ne se recouvre.
Vérifier « il y a un regroupement dans le code » ne prouverait rien : c'est la
géométrie du résultat qui compte.
"""
import os
import re
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

SCOPE = os.path.join(CONCOURS, 'logx_scope.html')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _source_js():
    """Extrait les constantes de mise en page + hauteurBarre + drawScope du
    fichier LIVRÉ. Rien n'est recopié : si la page change, le test suit."""
    src = open(SCOPE, encoding='utf-8').read()
    debut = src.index('const HMAX = 150;')
    fin = src.index('async function tick()')
    bloc = src[debut:fin]
    assert 'function drawScope' in bloc, 'drawScope introuvable dans le bloc extrait'
    return bloc


def _tracer(spots, rng=(21.0, 21.45)):
    """Rend le SVG et retourne les étiquettes [(texte, x, y)]."""
    import json
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
        var _svg = {innerHTML: ''};
        var document = {getElementById: function(){ return _svg; }};
        var PCOL = {1:'r',2:'o',3:'y',4:'b',5:'m'};
        var rigMhz = null;
        function esc(v){ return String(v == null ? '' : v); }
        %s
        function rendre(spots, rng){ drawScope(spots, rng); return _svg.innerHTML; }
    """ % _source_js())
    svg = ctx.call('rendre', spots, list(rng))
    etiquettes = []
    for m in re.finditer(r'<text x="([-\d.]+)" y="([-\d.]+)"[^>]*>([^<]*)</text>', svg):
        x, y, t = float(m.group(1)), float(m.group(2)), m.group(3)
        # On écarte les graduations de l'axe (des nombres) et le repère radio.
        if re.fullmatch(r'\d+(\.\d+)?', t) or 'radio' in t:
            continue
        etiquettes.append((t, x, y))
    return etiquettes


def _collisions(etiquettes, larg_car=8.6, haut=15.0):
    """Paires dont les rectangles se recouvrent. Le texte est centré (text-anchor
    middle), d'où la demi-largeur de part et d'autre."""
    boites = [(t, x - len(t) * larg_car / 2, x + len(t) * larg_car / 2, y)
              for t, x, y in etiquettes]
    mauvaises = []
    for i in range(len(boites)):
        for j in range(i + 1, len(boites)):
            t1, a1, a2, y1 = boites[i]
            t2, b1, b2, y2 = boites[j]
            if abs(y1 - y2) < haut and a1 < b2 and b1 < a2:
                mauvaises.append((t1, t2))
    return mauvaises


def spot(call, freq, **kw):
    s = {'call': call, 'freq': freq, 'priority': 3,
         'new_mult': False, 'already_done': False}
    s.update(kw)
    return s


# ─── Les deux cas de la capture d'écran ──────────────────────────────────────

def test_TROIS_STATIONS_SUR_LA_MEME_FREQUENCE_sont_toutes_lisibles():
    """Le cas FT8 : 21.076 porte trois stations. Aucun écart horizontal ne peut
    les séparer — sans empilement, on lit un seul pâté."""
    et = _tracer([spot('W9RSM', 21.076), spot('K2KIG', 21.076), spot('KC8QDQ', 21.076)])
    assert _collisions(et) == []
    assert {t for t, _, _ in et} == {'W9RSM', 'K2KIG', 'KC8QDQ'}
    ys = sorted(y for _, _, y in et)
    assert len(set(ys)) == 3, 'les trois doivent etre sur trois hauteurs distinctes'


def test_DEUX_FREQUENCES_VOISINES_ne_se_telescopent_plus():
    """Le cas « VE6CQC7ONI » : 17 kHz d'ecart, des etiquettes cinq fois plus
    larges que cet ecart."""
    et = _tracer([spot('VE6CQ', 21.270), spot('YC7ONI', 21.287)])
    assert _collisions(et) == []


def test_le_cas_complet_de_la_capture():
    """Les onze stations de la capture d'ecran de l'utilisateur, telles quelles."""
    et = _tracer([
        spot('YB7ONC', 21.330), spot('YC7ONI', 21.287), spot('VE6CQ', 21.270),
        spot('AA0HJ', 21.140), spot('WA4MB', 21.140), spot('KA9EKJ', 21.140),
        spot('W9RSM', 21.076), spot('K2KIG', 21.076), spot('KC8QDQ', 21.076),
        spot('W1AMJ', 21.074), spot('AE0BK', 21.074),
    ])
    assert _collisions(et) == []
    assert len(et) == 11, 'aucune station ne doit disparaitre'


# ─── Cas limites ─────────────────────────────────────────────────────────────

def test_une_pile_enorme_ne_deborde_pas_du_cadre():
    """Quinze stations sur une frequence : on ne peut pas toutes les ecrire.
    Le comportement attendu est d'en montrer quelques-unes et d'annoncer le
    reste par « +N » — surtout PAS d'ecrire hors du cadre, ni de mentir en
    n'affichant que les premieres sans le dire."""
    et = _tracer([spot('ST%02d' % i, 21.076) for i in range(15)])
    assert _collisions(et) == []
    assert all(y >= 0 for _, _, y in et), 'aucune etiquette au-dessus du cadre'
    assert any(t.startswith('+') for t, _, _ in et), 'le reliquat doit etre annonce'


def test_une_etiquette_en_bord_de_bande_reste_dans_le_cadre():
    """Une station au tout debut de la bande centrerait son texte sur x=20 et
    deborderait a gauche du trace."""
    et = _tracer([spot('OH0ABCDEF', 21.001)])
    (t, x, _), = et
    assert x - len(t) * 8.6 / 2 >= 0


def test_le_nouveau_multiplicateur_mene_le_groupe():
    """Sur une frequence partagee, la barre et la premiere ligne doivent porter
    le spot le plus interessant : un nouveau multiplicateur ne doit pas etre
    relegue derriere un deja-travaille."""
    et = _tracer([spot('DEJA', 21.076, already_done=True),
                  spot('NEUF', 21.076, new_mult=True)])
    bas = max(y for _, _, y in et)          # y croissant = plus bas a l'ecran
    premier = [t for t, _, y in et if y == bas][0]
    assert premier == '★NEUF'


def test_liste_vide():
    assert _tracer([]) == []
