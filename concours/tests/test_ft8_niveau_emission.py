# -*- coding: utf-8 -*-
"""FT8 : le niveau d'émission était fixe, la consigne inapplicable.

LE DÉFAUT. La page FT8 donne la bonne règle dans son aide, et l'écrit en gras :

    « ALC à ZÉRO pendant l'émission. Pas « dans la zone », pas « au premier
      tiers » : à zéro. On règle la puissance par le niveau audio envoyé au
      poste, jamais en laissant l'ALC écrêter. »

Sauf que ce niveau audio, l'opérateur ne pouvait pas le régler. La synthèse
appelait `ft8SynthesizeGfsk()` SANS `amplitude`, donc avec son défaut — **0,9,
soit 90 % de la pleine échelle**. Aucun curseur dans la page. Restaient le
mixeur Windows ou le gain d'entrée du poste. WSJT-X, lui, a son curseur `Pwr`
exactement pour ça.

Une consigne sans moyen de l'appliquer ne vaut rien : c'est ce que ce lot
corrige.

DEUX CHOIX QUI COMPTENT, tous deux tenus par un test ci-dessous :

  - **90 % par défaut** — exactement l'amplitude 0,9 émise jusqu'ici. Ajouter
    un réglage ne doit PAS modifier en douce ce qui part de la station d'un
    opérateur qui met à jour.
  - **plancher à 5 %, jamais 0** — un niveau nul émettrait un silence tout en
    affichant « émission en cours ». L'opérateur croirait appeler alors que
    rien ne part : un piège pire que l'absence de réglage.

CE QUE CES TESTS NE PROUVENT PAS : le bon réglage pour SA station. Il dépend
de la carte son, du câblage et de la sensibilité d'entrée du poste — ça se
règle sur l'ALC de la radio, pas dans un test.
"""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

from test_ft8_sequenceur import _extraire_fonction, _lire  # noqa: E402

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(CONCOURS, 'logx_ft8.html')


def _code_sans_commentaires():
    src = _lire(PAGE)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'//.*$', '', li) for li in src.splitlines())


def _moteur(memo=None):
    """Évalue les VRAIES fonctions de niveau extraites de la page.

    On ne réimplémente rien : un banc qui recopierait la formule ne
    contraindrait que sa propre copie, et divergerait au premier changement.
    localStorage est simulé, avec la valeur mémorisée qu'on veut éprouver.
    """
    src = _lire(PAGE)
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
    var __memo = null;
    var localStorage = {getItem: function(){ return __memo; },
                        setItem: function(k, v){ __memo = String(v); }};
    var document = {getElementById: function(){ return null; }};
    """)
    if memo is not None:
        ctx.eval('__memo = %s;' % ('null' if memo is None else repr(str(memo))))
    # Les constantes vivent hors des fonctions : on les rejoue telles quelles.
    for ligne in _code_sans_commentaires().splitlines():
        if ligne.strip().startswith(('const CLE_NIVEAU_TX', 'const NIVEAU_TX_')):
            ctx.eval(ligne.strip().replace('const ', 'var '))
    ctx.eval(_extraire_fonction(src, 'niveauTxPourcent'))
    ctx.eval(_extraire_fonction(src, 'amplitudeTx'))
    return ctx


def test_par_defaut_on_emet_exactement_comme_avant():
    """Le point le plus important pour un opérateur qui met à jour : rien ne
    change sur l'air tant qu'il ne touche pas au curseur. 0,9 est l'amplitude
    par défaut de ft8SynthesizeGfsk, donc ce que la page émettait."""
    ctx = _moteur(memo=None)
    assert ctx.eval('niveauTxPourcent()') == 90
    assert abs(ctx.eval('amplitudeTx()') - 0.9) < 1e-9, (
        "le défaut doit reproduire l'amplitude 0,9 émise jusqu'ici")


def test_le_niveau_choisi_est_bien_celui_applique():
    """Sans ça, le curseur serait décoratif."""
    ctx = _moteur(memo=40)
    assert ctx.eval('niveauTxPourcent()') == 40
    assert abs(ctx.eval('amplitudeTx()') - 0.4) < 1e-9


def test_on_ne_peut_jamais_tomber_a_zero():
    """Un silence annoncé comme une émission est pire que pas de réglage :
    l'opérateur appelle dans le vide sans le savoir. Même une valeur aberrante
    en mémoire (0, négative, texte) doit être ramenée au plancher."""
    for memo in (0, -20, 'nimportequoi'):
        ctx = _moteur(memo=memo)
        p = ctx.eval('niveauTxPourcent()')
        assert p >= 5, 'mémoire=%r a donné %r %%' % (memo, p)
        assert ctx.eval('amplitudeTx()') > 0


def test_on_ne_depasse_jamais_la_pleine_echelle():
    """Au-delà de 1,0 la forme d'onde serait écrêtée à la synthèse — le signal
    sale que toute la consigne ALC cherche justement à éviter."""
    ctx = _moteur(memo=250)
    assert ctx.eval('niveauTxPourcent()') == 100
    assert ctx.eval('amplitudeTx()') <= 1.0


def test_la_synthese_recoit_reellement_le_niveau():
    """Assertion de STRUCTURE, et elle est indispensable : les tests ci-dessus
    portent sur les fonctions extraites, ils passeraient même si la page
    n'appelait jamais amplitudeTx() au moment d'émettre. Sans ce paramètre,
    ft8SynthesizeGfsk retombe sur 0,9 et le curseur ne sert à rien.
    Commentaires dépouillés avant recherche."""
    code = _code_sans_commentaires()
    assert 'amplitude: amplitudeTx()' in code, (
        "la synthèse doit recevoir amplitude: amplitudeTx() — sinon le curseur "
        'est purement décoratif et le défaut est intact')


def test_le_reglage_survit_au_rechargement():
    """Une session FT8 dure des heures et la page peut être rechargée. Un
    niveau qui repart à 90 % après un rafraîchissement remettrait la station
    à pleine puissance sans prévenir."""
    code = _code_sans_commentaires()
    assert "localStorage.setItem(CLE_NIVEAU_TX" in code, (
        'le niveau doit être mémorisé')
    assert "localStorage.getItem(CLE_NIVEAU_TX)" in code, (
        'et relu au chargement')


def _bloc_niveau():
    """Le bloc de niveau TEL QU'IL EST DANS LA PAGE, du premier const jusqu'à
    la fermeture de l'IIFE de câblage — bornes prises dans le texte, pas des
    numéros de ligne qui dériveraient à la première insertion."""
    src = _lire(PAGE)
    debut = src.index('const CLE_NIVEAU_TX')
    ancre = src.index('function cablerNiveauTx', debut)
    fin = src.index('})();', ancre) + len('})();')
    return src[debut:fin]


def test_le_bloc_de_niveau_s_execute_sans_tuer_ce_qui_suit():
    """LE SECOND DÉFAUT DE CE LOT, et le plus grave — la page ENTIÈRE était
    morte pendant que les sept tests précédents étaient verts.

    En passant `majNiveauTx` de déclaration à `window.majNiveauTx = function(){}`,
    j'ai laissé la fermeture en `}` au lieu de `};`. L'insertion automatique de
    point-virgule ne coupe jamais devant une parenthèse ouvrante : l'IIFE de
    câblage de la ligne suivante a donc été lue comme un APPEL de la fonction
    qu'on venait d'affecter. La chaîne a avalé tout le reste du bloc et est
    morte sur le `})();` final de la page. Mesuré en navigateur : plus rien
    n'était défini au-delà — ni l'envoi de message, ni le séquenceur. Aucune
    erreur de syntaxe, le fichier restait parfaitement valide.

    Un test qui LIT le texte ne peut pas voir ça. Celui-ci l'EXÉCUTE, et pose
    une sentinelle derrière : si la chaîne repart, l'évaluation lève avant de
    l'atteindre."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
    var __memo = null;
    var localStorage = {getItem: function(){ return __memo; },
                        setItem: function(k, v){ __memo = String(v); }};
    var document = {getElementById: function(){ return null; }};
    var window = {};
    """)
    ctx.eval(_bloc_niveau() + '\nvar SENTINELLE = 1;')
    assert ctx.eval('SENTINELLE') == 1, (
        "l'évaluation du bloc n'a pas atteint la ligne suivante : une chaîne "
        "d'appel a avalé la suite (point-virgule manquant après une "
        'affectation de fonction ?)')
    assert ctx.eval('typeof window.majNiveauTx') == 'function'


def test_le_curseur_atteint_reellement_son_gestionnaire():
    """LE DÉFAUT QUE CE LOT A RÉELLEMENT PRODUIT, trouvé en navigateur.

    Tout le <script> de la page vit dans une IIFE. Une `function majNiveauTx()`
    déclarée dedans existe — les tests ci-dessus la trouvaient et passaient —
    mais `oninput="majNiveauTx()"` est résolu dans la portée GLOBALE, où elle
    n'était pas. Résultat mesuré : curseur poussé à 40, affichage figé à
    « 90 % », mémoire à 90, aucune erreur visible. Un curseur purement
    décoratif, exactement ce que le lot prétendait corriger.

    La règle générale : une fonction DÉCLARÉE localement dans cette page ne
    peut pas servir de gestionnaire inline ; elle doit être posée sur window,
    comme les huit autres de la page (window.majTonPropre, window.toggleRx…).
    """
    src = _lire(PAGE)
    appelees = set()
    for m in re.finditer(r'\son[a-z]+\s*=\s*"([^"]*)"', src):
        appelees.update(re.findall(r'([A-Za-z_$][\w$]*)\s*\(', m.group(1)))
    exposees = set(re.findall(r'window\.([\w$]+)\s*=', src))
    locales = set(re.findall(r'\bfunction\s+([\w$]+)\s*\(', src))
    injoignables = sorted((appelees & locales) - exposees)
    assert not injoignables, (
        'gestionnaire(s) inline pointant sur une fonction locale à l\'IIFE, '
        'donc jamais atteinte depuis le HTML : %s — poser sur window' % injoignables)
    assert 'window.majNiveauTx' in src, (
        'majNiveauTx doit être exposée sur window pour que oninput la trouve')


def test_le_controle_existe_et_dit_a_quoi_il_sert():
    """Intuitivité : un curseur nommé « NIVEAU TX » sans explication laisserait
    l'opérateur deviner. L'infobulle doit renvoyer à l'ALC, qui est le critère
    de réglage réel."""
    src = _lire(PAGE)
    assert 'id="ft8Niveau"' in src, 'le curseur doit exister dans la page'
    assert 'type="range"' in src
    i = src.index('id="ft8Niveau"')
    autour = src[max(0, i - 900):i]
    assert 'ALC' in autour, (
        "l'infobulle du curseur doit dire de le régler sur l'ALC — c'est le "
        'seul critère utilisable par un opérateur')
