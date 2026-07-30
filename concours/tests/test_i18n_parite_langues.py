# -*- coding: utf-8 -*-
"""Une langue peut avoir MOINS de clés que ses sœurs — et personne ne le voit.

DÉFAUT TROUVÉ EN COMPARANT LES LANGUES ENTRE ELLES, pas en lisant les pages :
dans `T_PARITY_FIX`, « LOCATORS UNIQUES » avait une entrée en espagnol, en
italien, en portugais, en néerlandais et en polonais — mais pas en allemand.
Ce libellé existe pour de vrai (bandeau de score de logx_logbook.html), donc
en allemand *seulement*, il restait affiché en français.

Ce genre de trou échappe à tout : les pages sont complètes, le moteur va bien
chercher la valeur, la clé existe. Il n'y a qu'UNE langue de fausse, et il faut
ouvrir l'application dans cette langue-là, sur cette page-là, pour le voir.
Comparer les langues entre elles le trouve en une seconde.

PIÈGE DE MESURE, rencontré en écrivant ce test : découper le fichier en
« groupes de 7 blocs consécutifs » ne marche pas. Les dictionnaires n'ont pas
tous la même taille, le découpage se décale de l'un à l'autre, et on finit par
comparer l'allemand d'un dictionnaire à l'anglais du suivant — des centaines de
fausses lacunes. On détermine donc le VRAI objet parent de chaque bloc par
comptage d'accolades, ce qui ne peut pas se décaler.

DEUXIÈME LEÇON : le premier écart signalé, « DIST / CAP », était un FAUX
positif — cette chaîne (avec espaces) n'existe dans aucune page, la vraie étant
« DIST/CAP ». L'allemand n'était pas en retard : il était le seul à ne pas
traîner une clé morte. D'où `test_aucune_cle_morte_dans_le_correctif_de_parite`
ci-dessous : une clé qui ne correspond à rien ne se contente pas d'être
inutile, elle fabrique de fausses alertes.
"""
import glob
import io
import os
import re
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

I18N = os.path.join(CONCOURS, 'logx_i18n.js')
LANGUES = ('en', 'de', 'es', 'it', 'pt', 'nl', 'pl')


# DEUX styles de guillemets cohabitent dans logx_i18n.js : le dictionnaire de
# base utilise des APOSTROPHES SIMPLES et empile plusieurs paires par ligne,
# les objets correctifs des guillemets doubles, une paire par ligne. Un
# extracteur qui ne lisait que le second style ne voyait tout simplement pas le
# dictionnaire principal — il déclarait manquantes des dizaines de clés déjà
# traduites, et c'est ainsi que sept traductions établies ont failli être
# écrasées par des reformulations inutiles.
_PAIRE = re.compile(
    r"""(?P<q>['"])(?P<cle>(?:[^'"\\]|\\.|(?!(?P=q))['"])*)(?P=q)\s*:\s*"""
    r"""(?P<q2>['"])""")


def _source():
    return io.open(I18N, encoding='utf-8').read()


def _desechappe(k):
    """`'PARAMÈTRES D\\'ALERTE'` en source vaut `PARAMÈTRES D'ALERTE` à
    l'exécution : sans ça, la même clé apparaît sous deux formes selon le style
    de guillemets du bloc, et la comparaison entre langues devient absurde."""
    return k.replace('\\\\', '\x00').replace("\\'", "'").replace('\\"', '"') \
            .replace('\x00', '\\')


def _cles_du_bloc(corps):
    return {_desechappe(m.group('cle')) for m in _PAIRE.finditer(corps)}


def _parents(src):
    """position d'un '{' -> position du '{' englobant, chaînes/commentaires exclus."""
    parent, pile = {}, []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in '"\'`':
            q, i = c, i + 1
            while i < n and src[i] != q:
                i += 2 if src[i] == '\\' else 1
            i += 1
            continue
        if c == '/' and i + 1 < n and src[i + 1] == '/':
            i = src.find('\n', i)
            if i == -1:
                break
            continue
        if c == '/' and i + 1 < n and src[i + 1] == '*':
            i = src.find('*/', i) + 2
            continue
        if c == '{':
            parent[i] = pile[-1] if pile else -1
            pile.append(i)
        elif c == '}' and pile:
            pile.pop()
        i += 1
    return parent


def _fin_bloc(src, ouv):
    prof, j, n = 0, ouv, len(src)
    while j < n:
        if src[j] == '{':
            prof += 1
        elif src[j] == '}':
            prof -= 1
            if prof == 0:
                return j
        elif src[j] in '"\'`':
            q, j = src[j], j + 1
            while j < n and src[j] != q:
                j += 2 if src[j] == '\\' else 1
        j += 1
    return n


def _dictionnaires():
    """[{langue: set(cles)}] — un élément par objet dictionnaire du fichier."""
    src = _source()
    parent = _parents(src)
    objets = {}
    for m in re.finditer(r'^\s{0,8}(en|de|es|it|pt|nl|pl):\s*\{', src, re.M):
        ouv = src.index('{', m.start())
        par = parent.get(ouv)
        if par is None:
            continue
        corps = src[ouv:_fin_bloc(src, ouv)]
        objets.setdefault(par, {})[m.group(1)] = _cles_du_bloc(corps)
    return [d for d in objets.values() if any(d.values())]


# ─── Le cœur : aucune langue en retard sur ses sœurs ─────────────────────────

def _dictionnaire_effectif():
    """{langue: set(clés)} APRÈS fusion de tous les objets correctifs.

    C'est le seul niveau où la comparaison a un sens. Objet par objet, elle
    n'en a aucun : le dictionnaire de base est VOLONTAIREMENT asymétrique
    (l'anglais y porte des clés que les autres n'ont pas), et `T_PARITY_FIX`
    existe exactement pour combler les six autres langues. Comparer les objets
    un à un signalait donc 82 « lacunes » qui sont toutes comblées trois cents
    lignes plus bas — un test qui hurle sur du code correct ne sert à rien.
    """
    effectif = {}
    for d in _dictionnaires():
        for lang, cles in d.items():
            effectif.setdefault(lang, set()).update(cles)
    return effectif


def test_TOUTES_LES_LANGUES_TRADUISENT_LES_MEMES_CLES():
    """Une clé traduite dans six langues sur sept, c'est un texte qui reste en
    français dans la septième — et seulement là. Invisible tant qu'on n'ouvre
    pas l'application dans cette langue-là, sur cette page-là."""
    effectif = _dictionnaire_effectif()
    reference = set()
    for cles in effectif.values():
        reference |= cles
    ecarts = []
    for lang in LANGUES:
        for k in sorted(reference - effectif.get(lang, set())):
            ecarts.append('%s ne traduit pas |%s|' % (lang, k))
    assert ecarts == [], '%d ecarts :\n%s' % (len(ecarts), '\n'.join(ecarts))


def test_les_dictionnaires_couvrent_les_sept_langues():
    """Sauf T_PARITY_FIX, dont c'est la RAISON D'ÊTRE : il ne contient que des
    clés déjà traduites en anglais, et comble les six autres langues. Exiger
    un bloc `en` là serait exiger de recopier l'anglais sur lui-même."""
    src = _source()
    i = src.find('const T_PARITY_FIX = {')
    assert i > 0, 'T_PARITY_FIX a disparu : revoir l\'exemption ci-dessous'
    parent = _parents(src)
    # Le parent des blocs de langue EST l'accolade de T_PARITY_FIX lui-même,
    # pas celle qui l'englobe : prendre parent.get(...) ici visait un cran trop
    # haut et l'exemption ne s'appliquait jamais.
    par_parity = src.index('{', src.find('=', i))

    objets = {}
    for m in re.finditer(r'^\s{0,8}(en|de|es|it|pt|nl|pl):\s*\{', src, re.M):
        ouv = src.index('{', m.start())
        objets.setdefault(parent.get(ouv), set()).add(m.group(1))

    incomplets = []
    for par, langues in objets.items():
        if par == par_parity:
            assert langues == set(LANGUES) - {'en'}, (
                'T_PARITY_FIX doit couvrir exactement les 6 langues hors EN, '
                'trouve : %s' % sorted(langues))
            continue
        if langues and langues != set(LANGUES):
            incomplets.append('objet a %d : %s' % (par, sorted(langues)))
    assert incomplets == [], incomplets


# ─── Le faux positif qui m'a fait perdre du temps ────────────────────────────

def test_aucune_cle_morte_dans_le_correctif_de_parite():
    """Une clé qui ne correspond à AUCUN texte des pages ne se contente pas
    d'être inutile : elle fait croire, dans le test ci-dessus, qu'une langue
    est en retard. « DIST / CAP » (avec espaces) n'existait nulle part — la
    vraie chaîne est « DIST/CAP »."""
    src = _source()
    i = src.find('const T_PARITY_FIX = {')
    if i < 0:
        pytest.skip('T_PARITY_FIX supprime')
    ouv = src.index('{', src.find('=', i))
    cles = _cles_du_bloc(src[ouv:_fin_bloc(src, ouv)])

    pages = ''
    for f in sorted(glob.glob(os.path.join(CONCOURS, 'logx_*.html'))):
        pages += io.open(f, encoding='utf-8').read()
    for f in sorted(glob.glob(os.path.join(CONCOURS, 'logx_*.js'))):
        pages += io.open(f, encoding='utf-8').read()

    mortes = sorted(k for k in cles if k and k not in pages)
    assert mortes == [], (
        'cles de T_PARITY_FIX introuvables dans les pages ET le JS : %s' % mortes)


# ─── Le cas precis qui a revele le defaut ────────────────────────────────────

@pytest.mark.parametrize('lang', LANGUES)
def test_locators_uniques_est_traduit_dans_les_sept_langues(lang):
    """Libelle bien reel : bandeau de score de logx_logbook.html."""
    src = _source()
    assert '"LOCATORS UNIQUES"' in src
    d = [x for x in _dictionnaires() if any('LOCATORS UNIQUES' in c for c in x.values())]
    assert d, 'plus aucun dictionnaire ne porte cette cle'
    # au moins un dictionnaire la traduit dans cette langue
    assert any(lang in x and 'LOCATORS UNIQUES' in x[lang] for x in d), (
        '%s ne traduit « LOCATORS UNIQUES » nulle part' % lang)


def test_le_libelle_existe_vraiment_dans_le_logbook():
    """Garde-fou du test ci-dessus : s'il disparaissait de la page, les sept
    parametrages passeraient en ne protegeant plus rien."""
    page = io.open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8').read()
    assert 'LOCATORS UNIQUES' in page


def test_il_y_a_bien_plusieurs_dictionnaires_a_comparer():
    """Garde-fou du garde-fou : si l'extraction cassait et ne renvoyait rien,
    tous les tests de ce fichier passeraient sans rien verifier."""
    dicos = _dictionnaires()
    assert len(dicos) >= 5, 'seulement %d dictionnaires extraits' % len(dicos)
    assert sum(len(c) for d in dicos for c in d.values()) > 1000
