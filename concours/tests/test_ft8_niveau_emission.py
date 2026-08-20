# -*- coding: utf-8 -*-
"""FT8 : le niveau d'émission était fixe, la consigne inapplicable.

LE DÉFAUT. La page FT8 donne la bonne règle dans son aide, et l'écrit en gras :

    « ALC à ZÉRO pendant l'émission. Pas « dans la zone », pas « au premier
      tiers » : à zéro. On règle la puissance par le niveau audio envoyé au
      poste, jamais en laissant l'ALC écrêter. »

Sauf que ce niveau audio, l'opérateur ne pouvait pas le régler. La synthèse
appelait `ft8SynthesizeGfsk()` SANS `amplitude`, donc avec son défaut — **0,9,
soit 90 % de la pleine échelle**. Aucun curseur dans la page. Restaient le
mixeur Windows ou le gain d'entrée du poste.

DEUX CHOIX QUI COMPTENT, tous deux tenus par un test ci-dessous :

  - **90 % par défaut** — exactement l'amplitude 0,9 émise jusqu'ici. Ajouter
    un réglage ne doit PAS modifier en douce ce qui part de la station d'un
    opérateur qui met à jour.
  - **plancher à 5 %, jamais 0** — un niveau nul émettrait un silence tout en
    affichant « émission en cours ».

POURQUOI CE FICHIER EXÉCUTE LE CODE AU LIEU DE LE LIRE. Sa première version
comptait neuf tests verts et une contre-épreuve à 7/7 — et une revue a montré
que HUIT autres mutations passaient au vert, dont deux qui remettaient le
défaut d'origine à l'identique : retirer `oninput=` du curseur, et figer
l'affichage à « 90 % ». Cause commune : le banc posait
`document.getElementById → null`, donc le corps de `majNiveauTx` n'était JAMAIS
exécuté, et les assertions restantes cherchaient des sous-chaînes dans le texte
du fichier — une occurrence morte ailleurs les satisfaisait.

Le banc ci-dessous rend donc de VRAIS objets, et le faux localStorage HONORE la
clé demandée (l'ancien renvoyait la même valeur quelle que soit la clé, si bien
que la cohérence écriture/lecture était tenue par le mannequin, jamais par la
page). Ce qui ne peut pas s'exécuter — attributs HTML, forme de l'appel à la
synthèse — est tenu par des assertions de STRUCTURE, pas de présence.

CE QUE CES TESTS NE PROUVENT PAS : le bon réglage pour SA station. Il dépend de
la carte son, du câblage et de la sensibilité d'entrée du poste — ça se règle
sur l'ALC de la radio, pas dans un test. Et sur le chemin VOX sans CAT, aucun
test ne peut dire à partir de quel niveau le poste cesse de se déclencher : le
seuil de VOX est un réglage du poste, que le logiciel ne connaît pas.
"""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

from test_ft8_sequenceur import _lire  # noqa: E402

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(CONCOURS, 'logx_ft8.html')

CLE_ATTENDUE = 'rc_ft8_niveau_tx'


def _code_sans_commentaires():
    """Le fichier dépouillé de ses commentaires HTML ET JavaScript.

    Indispensable ici : les commentaires de ce lot CITENT abondamment « ALC »,
    « amplitude » et « window » pour expliquer les choix. Chercher ces mots
    dans le texte brut, c'est se faire satisfaire par le pavé qui EXPLIQUE le
    code au lieu du code lui-même.
    """
    src = _lire(PAGE)
    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'//.*$', '', li) for li in src.splitlines())


def _bloc_niveau():
    """Le bloc de niveau TEL QU'IL EST DANS LA PAGE, du premier const jusqu'à
    la fermeture de l'IIFE de câblage — bornes prises dans le texte, pas des
    numéros de ligne qui dériveraient à la première insertion."""
    src = _lire(PAGE)
    debut = src.index('const CLE_NIVEAU_TX')
    ancre = src.index('function cablerNiveauTx', debut)
    fin = src.index('})();', ancre) + len('})();')
    return src[debut:fin]


def _balise_curseur():
    """La balise <input id="ft8Niveau" …> entière, commentaires ôtés."""
    code = _code_sans_commentaires()
    i = code.index('id="ft8Niveau"')
    debut = code.rindex('<input', 0, i)
    return code[debut:code.index('>', i) + 1]


def _banc(memo=None):
    """Évalue le VRAI bloc de la page avec un DOM et un stockage qui répondent.

    Le curseur et l'affichage sont de vrais objets : le corps de majNiveauTx
    s'exécute donc pour de bon, y compris le bornage, l'écriture mémoire et la
    mise à jour du texte affiché. localStorage honore la CLÉ demandée, sans
    quoi une page qui lirait/écrirait ailleurs passerait quand même.
    """
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
    var __memo = {};
    var localStorage = {
      getItem: function(k){
        return Object.prototype.hasOwnProperty.call(__memo, k) ? __memo[k] : null;
      },
      setItem: function(k, v){ __memo[k] = String(v); }
    };
    var __curseur = {value: '90'};
    var __affich  = {textContent: ''};
    var document = {getElementById: function(id){
      if(id === 'ft8Niveau')    return __curseur;
      if(id === 'ft8NiveauVal') return __affich;
      return null;
    }};
    var window = {};
    """)
    if memo is not None:
        ctx.eval('__memo[%r] = %r;' % (CLE_ATTENDUE, str(memo)))
    ctx.eval(_bloc_niveau())
    return ctx


def _regler(ctx, position):
    """Pose le curseur comme le ferait un doigt, puis déclenche le gestionnaire."""
    ctx.eval('__curseur.value = %r;' % str(position))
    ctx.eval('window.majNiveauTx();')


# ─── ce qui part sur l'air ────────────────────────────────────────────────────

def test_par_defaut_on_emet_exactement_comme_avant():
    """Le point le plus important pour un opérateur qui met à jour : rien ne
    change sur l'air tant qu'il ne touche pas au curseur. 0,9 est l'amplitude
    par défaut de ft8SynthesizeGfsk, donc ce que la page émettait."""
    ctx = _banc(memo=None)
    assert ctx.eval('niveauTxPourcent()') == 90
    assert abs(ctx.eval('amplitudeTx()') - 0.9) < 1e-9, (
        "le défaut doit reproduire l'amplitude 0,9 émise jusqu'ici")


def test_le_niveau_choisi_est_bien_celui_applique():
    """Sans ça, le curseur serait décoratif."""
    ctx = _banc(memo=40)
    assert ctx.eval('niveauTxPourcent()') == 40
    assert abs(ctx.eval('amplitudeTx()') - 0.4) < 1e-9


def test_la_synthese_recoit_le_niveau_DANS_l_appel():
    """Assertion de STRUCTURE, et la formulation compte.

    `assert 'amplitude: amplitudeTx()' in code` ne vaudrait rien : n'importe
    quelle occurrence morte ailleurs dans le fichier la satisferait. Mutation
    vérifiée sur l'ancienne version — amplitude retirée du VRAI appel et une
    ligne morte `const _jamaisUtilise = {amplitude: amplitudeTx()};` ajoutée
    plus haut : les neuf tests restaient verts pendant que la station réémettait
    à 0,9. On exige donc le paramètre DANS les arguments de ft8SynthesizeGfsk.
    """
    code = _code_sans_commentaires()
    i = code.index('ft8SynthesizeGfsk(')
    profondeur, fin = 0, None
    for j in range(i + len('ft8SynthesizeGfsk('), len(code)):
        if code[j] == '(':
            profondeur += 1
        elif code[j] == ')':
            if profondeur == 0:
                fin = j
                break
            profondeur -= 1
    assert fin is not None, "appel à ft8SynthesizeGfsk non refermé"
    arguments = code[i:fin]
    assert 'amplitudeTx()' in arguments, (
        "ft8SynthesizeGfsk doit recevoir amplitudeTx() DANS ses arguments — "
        'sinon il retombe sur 0,9 et le curseur est purement décoratif :\n'
        + arguments)


# ─── bornes ──────────────────────────────────────────────────────────────────

def test_on_ne_peut_jamais_tomber_a_zero_par_la_memoire():
    """Un silence annoncé comme une émission est pire que pas de réglage."""
    for memo in (0, -20, 'nimportequoi'):
        ctx = _banc(memo=memo)
        p = ctx.eval('niveauTxPourcent()')
        assert p >= 5, 'mémoire=%r a donné %r %%' % (memo, p)
        assert ctx.eval('amplitudeTx()') > 0


def test_le_curseur_pousse_a_fond_a_gauche_retombe_sur_le_PLANCHER():
    """DÉFAUT RÉEL DE LA PREMIÈRE VERSION, mesuré puis corrigé.

    Le code faisait `parseInt(curseur.value,10) || NIVEAU_TX_DEFAUT`. Or
    parseInt('0') vaut 0, qui est faux au sens de `||` : le repli s'appliquait
    AVANT le plancher et un curseur à 0 repartait à 90 %, c'est-à-dire à
    PLEINE ÉCHELLE — l'inverse exact de la règle de sûreté revendiquée. Mesuré
    à l'époque : value='0' donnait 90, quand value='3' donnait bien 5.
    """
    ctx = _banc()
    _regler(ctx, 0)
    assert ctx.eval('__curseur.value') == 5, (
        'un curseur à 0 doit retomber sur le plancher, jamais remonter au défaut')
    assert ctx.eval('niveauTxPourcent()') == 5


def test_une_valeur_illisible_retombe_sur_le_defaut():
    """Le repli vers 90 % reste le bon comportement quand la valeur n'est PAS
    un nombre — c'est le seul cas où il s'applique."""
    ctx = _banc()
    _regler(ctx, 'abc')
    assert ctx.eval('__curseur.value') == 90


def test_on_ne_depasse_jamais_la_pleine_echelle():
    """Au-delà de 1,0 la forme d'onde serait écrêtée à la synthèse — le signal
    sale que toute la consigne ALC cherche justement à éviter."""
    # La mémoire est repositionnée APRÈS le câblage, et c'est indispensable :
    # l'IIFE de restauration appelle majNiveauTx, qui borne et RÉÉCRIT la
    # mémoire. Poser 250 avant l'évaluation, c'est donc trouver 100 en mémoire
    # au moment de lire — et le plafond de niveauTxPourcent n'est plus éprouvé
    # du tout. Vérifié : en retirant le Math.min de niveauTxPourcent, ce test
    # restait vert tant que la valeur n'était posée qu'avant.
    ctx = _banc()
    ctx.eval('__memo[%r] = "250";' % CLE_ATTENDUE)
    assert ctx.eval('niveauTxPourcent()') == 100
    assert ctx.eval('amplitudeTx()') <= 1.0
    ctx2 = _banc()
    _regler(ctx2, 300)
    assert ctx2.eval('__curseur.value') == 100


def test_les_bornes_du_curseur_sont_celles_annoncees():
    """Le bornage JS ne protège que ce qui lui parvient : les attributs du
    contrôle sont la première barrière, et rien d'autre ne les tient.
    Mutations vérifiées sur l'ancienne version — min="0" et max="300" passaient
    tous les tests, ouvrant une zone morte et un curseur qui saute à 90 %."""
    balise = _balise_curseur()
    assert 'min="5"' in balise, balise
    assert 'max="100"' in balise, balise
    assert 'type="range"' in balise, balise


def test_le_pas_du_curseur_permet_un_reglage_fin_en_bas_d_echelle():
    """L'échelle est linéaire en amplitude alors que l'ALC se règle en dB : de
    100 à 50 % il n'y a que 6,0 dB, mais de 10 à 5 % il y en a 6,0 aussi. Au
    pas de 5 ce dernier saut se faisait d'UN cran — l'opérateur passait de
    « rien ne bouge » à 12 dB plus bas sans réglage intermédiaire atteignable.
    """
    balise = _balise_curseur()
    m = re.search(r'step="(\d+)"', balise)
    assert m, 'le curseur doit déclarer un pas explicite : ' + balise
    assert int(m.group(1)) <= 1, (
        'un pas de %s laisse un saut de ~6 dB entre 10 %% et 5 %%, là où se '
        'joue tout le réglage' % m.group(1))


# ─── ce que l'opérateur VOIT et ce qui est mémorisé ───────────────────────────

def test_l_affichage_suit_reellement_le_curseur():
    """LE SYMPTÔME PAR LEQUEL LE PREMIER DÉFAUT A ÉTÉ TROUVÉ EN NAVIGATEUR :
    curseur poussé à 40, affichage figé à « 90 % ». Trois mutations restaient
    vertes sur l'ancienne version — supprimer la ligne d'affichage, la figer à
    '90 %', ou retirer le <span> — parce que le banc rendait null et que le
    corps de majNiveauTx n'était jamais exécuté."""
    ctx = _banc()
    _regler(ctx, 40)
    affiche = ctx.eval('__affich.textContent')
    assert '40' in affiche and '%' in affiche, (
        'affichage attendu autour de 40 %%, obtenu : %r' % affiche)
    assert '90' not in affiche, (
        "l'affichage est resté sur l'ancienne valeur : %r" % affiche)


def test_l_affichage_donne_aussi_les_decibels():
    """Sans le dB, l'échelle ment à l'œil : tirer le curseur sur la moitié de
    sa course ne retire que 6 dB et l'ALC ne bouge pas — l'opérateur conclut
    que le réglage ne sert à rien. Le chiffre en dB lui dit où agir."""
    ctx = _banc()
    _regler(ctx, 50)
    affiche = ctx.eval('__affich.textContent')
    assert 'dB' in affiche, affiche
    assert '6' in affiche, ('50 %% vaut -6,0 dBFS, non affiché : %r' % affiche)


def test_le_niveau_est_memorise_SOUS_LA_BONNE_CLE():
    """L'ancien banc renvoyait la même valeur quelle que soit la clé demandée :
    la cohérence écriture/lecture était tenue par le mannequin, jamais par la
    page. Mutation vérifiée : écriture sur 'rc_autre', lecture sur 'rc_autre2',
    et les deux bons appels laissés dans une fonction morte — neuf tests verts,
    pendant que le niveau repartait à 90 % à chaque rechargement."""
    ctx = _banc()
    _regler(ctx, 35)
    assert ctx.eval('__memo[%r]' % CLE_ATTENDUE) == '35'
    assert ctx.eval('Object.keys(__memo).length') == 1, (
        'une seule clé doit être écrite : ' + ctx.eval('JSON.stringify(__memo)'))


def test_le_reglage_est_restaure_au_chargement():
    """Une session FT8 dure des heures et la page peut être rechargée. C'est
    l'IIFE de câblage qui tient cette propriété — et rien ne la contraignait :
    la vider entièrement laissait les neuf tests verts. La page aurait alors
    affiché 90 % en émettant à 40 %."""
    ctx = _banc(memo=40)
    assert ctx.eval('__curseur.value') == 40, (
        'le curseur doit être repositionné sur la valeur mémorisée au chargement')
    assert '40' in ctx.eval('__affich.textContent')


# ─── ce que l'écran dit à l'opérateur ────────────────────────────────────────

def test_le_curseur_a_bien_un_gestionnaire():
    """Sans cet attribut, le curseur bouge et ne fait RIEN — le défaut n°1 du
    lot dans sa forme la plus directe. Mutation vérifiée sur l'ancienne
    version : retirer oninput/onchange laissait les neuf tests verts, parce que
    le test construisait l'ensemble des fonctions appelées À PARTIR des
    attributs présents — les retirer rendait son assertion vide de sens."""
    balise = _balise_curseur()
    assert re.search(r'on(input|change)\s*=\s*"[^"]*majNiveauTx', balise), (
        'le curseur doit appeler majNiveauTx : ' + balise)


def test_aucun_gestionnaire_inline_ne_pointe_dans_le_vide():
    """Tout le <script> de la page vit dans une IIFE. Une fonction déclarée
    dedans existe, mais un gestionnaire inline est résolu dans la portée
    GLOBALE : elle doit donc être posée sur window, comme les huit autres
    fonctions appelées depuis le HTML de cette page."""
    src = _lire(PAGE)
    appelees = set()
    for m in re.finditer(r'\son[a-z]+\s*=\s*"([^"]*)"', src):
        appelees.update(re.findall(r'([A-Za-z_$][\w$]*)\s*\(', m.group(1)))
    exposees = set(re.findall(r'window\.([\w$]+)\s*=', src))
    locales = set(re.findall(r'\bfunction\s+([\w$]+)\s*\(', src))
    injoignables = sorted((appelees & locales) - exposees)
    assert not injoignables, (
        "gestionnaire(s) inline pointant sur une fonction locale à l'IIFE, "
        'donc jamais atteinte depuis le HTML : %s — poser sur window' % injoignables)
    assert 'window.majNiveauTx' in src


def test_l_infobulle_donne_le_critere_de_reglage_ET_le_piege_du_VOX():
    """Intuitivité : un curseur nommé « NIVEAU TX » sans explication laisserait
    l'opérateur deviner. L'infobulle doit renvoyer à l'ALC — seul critère
    utilisable — ET avertir du piège propre au VOX.

    LE PIÈGE, et c'est le point de sûreté du lot : sur le chemin VOX sans CAT,
    le niveau audio n'est plus la seule modulation, c'est LE déclencheur de
    l'émission. Le critère « baisse jusqu'à ce que l'ALC ne bouge plus » est
    satisfait À L'IDENTIQUE par « niveau propre » et par « le poste ne se
    déclenche plus » — seul le voyant d'émission du poste sépare les deux.

    Lecture sur la source DÉPOUILLÉE : sur le texte brut, le commentaire qui
    EXPLIQUE le curseur cite lui-même la consigne ALC et satisfaisait
    l'assertion à la place de l'infobulle. Mutations vérifiées : infobulle
    supprimée, ou remplacée par « Règle le volume. » — neuf tests verts.
    """
    code = _code_sans_commentaires()
    i = code.index('id="ft8Niveau"')
    debut = code.rindex('<label', 0, i)
    etiquette = code[debut:i]
    assert 'title=' in etiquette, "le curseur doit porter une infobulle"
    assert 'ALC' in etiquette, (
        "l'infobulle doit donner le critère de réglage — l'ALC du poste :\n"
        + etiquette)
    assert 'VOX' in etiquette, (
        "l'infobulle doit avertir qu'en VOX un niveau trop bas empêche le poste "
        'de se déclencher :\n' + etiquette)


def test_la_consigne_de_niveau_nomme_le_curseur_qui_permet_de_l_appliquer():
    """Le lot se justifie par « une consigne sans moyen de l'appliquer ne vaut
    rien ». Le moyen a été ajouté — encore faut-il que la consigne y renvoie :
    elle vit dans un panneau replié, à 90 lignes du curseur. Sinon le débutant
    lit « on règle par le niveau audio » et part chercher dans le mixeur de
    Windows, exactement comme avant.

    ANCRE CHANGÉE le 20/08/2026 : elle portait sur « ALC à ZÉRO », formulation
    retirée sur décision de F4GLD après vérification à la source — le guide
    officiel WSJT-X ne contient pas le mot ALC, et le manuel de l'IC-7300
    prescrit au contraire de rester « within the ALC zone ». La PROPRIÉTÉ
    testée n'a pas bougé d'un pouce : la consigne de niveau doit nommer le
    curseur. Seul son ancrage textuel a suivi le nouveau critère.
    """
    code = _code_sans_commentaires()
    i = code.index('puissance HF commence tout')
    consigne = code[i:code.index('</li>', i)]
    assert 'NIVEAU TX' in consigne, (
        'la consigne de niveau doit nommer le curseur NIVEAU TX :\n' + consigne)


def test_les_deux_chaines_visibles_sont_traduites():
    """La page est traduite en 7 langues, par correspondance exacte du français,
    sur les nœuds texte ET sur l'attribut title. Une chaîne absente de TOUS les
    dictionnaires est parfaitement paritaire : le test de parité entre langues
    ne peut pas la voir. Les libellés voisins de la même rangée, eux, sont
    couverts 7 fois."""
    dico = _lire(os.path.join(CONCOURS, 'logx_i18n.js'))
    assert dico.count('"NIVEAU TX"') >= 7, (
        'NIVEAU TX doit être traduit dans les 7 langues, trouvé %d fois'
        % dico.count('"NIVEAU TX"'))
    assert dico.count("Baisse-le jusqu'à ce que l'ALC") >= 7, (
        "l'infobulle porte le seul critère de réglage : elle doit être traduite")
