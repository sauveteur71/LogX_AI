# -*- coding: utf-8 -*-
"""Les macros se déclenchent aux touches F1 à F8.

Les boutons AFFICHENT « F1 »… « F8 » depuis toujours, mais seul le clic les
déclenchait : la main devait quitter le clavier en plein run. C'est la
fonction que N1MM, Win-Test et DXLog mettent en avant en premier.

Ces tests EXÉCUTENT le vrai gestionnaire keydown (désormais dans
logx_theme_shortcuts.js, EV-7 22e incrément) dans un moteur V8, avec un DOM
minimal. On ne cherche pas des motifs dans le source : on appuie sur les
touches et on regarde ce qui part.

Le point le plus important est `preventDefault` : dans un navigateur, **F5
recharge la page**. Sans lui, appuyer sur la macro F5 en plein concours vide
la saisie en cours. F1 (aide), F3 (recherche) et F6 (barre d'adresse) sont
détournées de la même façon.
"""
import json
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_logbook.html')
# EV-7 22e incrément : le gestionnaire keydown (dont le bloc F1-F8 ci-dessous)
# a été extrait vers ce fichier -- _source_js() doit désormais y lire le
# bloc réel, plus dans logx_logbook.js.
THEME_SHORTCUTS_JS = os.path.join(CONCOURS, 'logx_theme_shortcuts.js')

py_mini_racer = pytest.importorskip('py_mini_racer')


def _source_js():
    with open(THEME_SHORTCUTS_JS, encoding='utf-8') as f:
        return f.read()


def _bloc_f1_f8():
    """Le bloc F1-F8 du gestionnaire, extrait du VRAI fichier (pas recopié :
    une recopie testerait ma transcription, pas le code livré)."""
    src = _source_js()
    debut = src.index("if(/^F[1-8]$/.test(e.key)")
    fin = src.index('// F9 : soumettre le QSO', debut)
    return src[debut:fin]


def _lire(ctx, expr):
    """py_mini_racer rend un JSObject opaque pour un tableau : on repasse par
    JSON pour comparer a des listes Python."""
    return json.loads(ctx.eval('JSON.stringify(%s)' % expr))


def _moteur(setup_done=True, modale=False, macros=None):
    """Contexte V8 minimal : le bloc réel + juste ce qu'il touche."""
    if macros is None:
        macros = [{'key': 'F%d' % i, 'label': 'M%d' % i, 'text': 't%d' % i}
                  for i in range(1, 9)]
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
        var journal = {envoyees: [], defaultEmpeche: []};
        var isSetupDone = %s;
        var _modaleOuverte = function(){ return %s; };
        var MACROS = %s;
        var getMacros = function(){ return MACROS; };
        var copyMacro = function(idx){ journal.envoyees.push(idx); };
        function appuyer(key, opts){
            opts = opts || {};
            var e = {
                key: key,
                ctrlKey: !!opts.ctrl, altKey: !!opts.alt, metaKey: !!opts.meta,
                preventDefault: function(){ journal.defaultEmpeche.push(key); }
            };
            (function(e){ %s })(e);
        }
    """ % ('true' if setup_done else 'false',
           'true' if modale else 'false',
           json.dumps(macros),
           _bloc_f1_f8()))
    return ctx


@pytest.mark.parametrize('touche,attendu', [('F%d' % i, i - 1) for i in range(1, 9)])
def test_chaque_touche_envoie_sa_macro(touche, attendu):
    ctx = _moteur()
    ctx.eval("appuyer('%s')" % touche)
    assert _lire(ctx, 'journal.envoyees') == [attendu]


@pytest.mark.parametrize('touche', ['F1', 'F3', 'F5', 'F6'])
def test_preventDefault_est_toujours_appele(touche):
    """F5 recharge la page, F3 ouvre la recherche, F1 l'aide, F6 la barre
    d'adresse. Le défaut du navigateur doit être coupé dans TOUS les cas."""
    ctx = _moteur()
    ctx.eval("appuyer('%s')" % touche)
    assert _lire(ctx, 'journal.defaultEmpeche') == [touche]


def test_preventDefault_meme_quand_la_macro_ne_part_pas():
    """Cas piège : setup non validé. Si on sortait sans couper le défaut,
    appuyer sur F5 avant d'avoir validé la fenêtre de démarrage rechargerait
    la page — le pire moment pour ça."""
    ctx = _moteur(setup_done=False)
    ctx.eval("appuyer('F5')")
    assert _lire(ctx, 'journal.envoyees') == []
    assert _lire(ctx, 'journal.defaultEmpeche') == ['F5']


def test_rien_ne_part_tant_que_le_setup_n_est_pas_valide():
    ctx = _moteur(setup_done=False)
    for i in range(1, 9):
        ctx.eval("appuyer('F%d')" % i)
    assert _lire(ctx, 'journal.envoyees') == []


def test_rien_ne_part_quand_une_fenetre_est_ouverte():
    """En train d'éditer un QSO ou de relire le vérificateur : une touche de
    fonction ne doit pas partir en émission."""
    ctx = _moteur(modale=True)
    for i in range(1, 9):
        ctx.eval("appuyer('F%d')" % i)
    assert _lire(ctx, 'journal.envoyees') == []


@pytest.mark.parametrize('modif', ['ctrl', 'alt', 'meta'])
def test_les_combinaisons_sont_laissees_au_navigateur(modif):
    """Alt+F4 ferme la fenêtre, Ctrl+F5 force le rechargement : ce sont des
    gestes système, on n'y touche pas et on ne coupe pas leur défaut."""
    ctx = _moteur()
    ctx.eval("appuyer('F2', {%s: true})" % modif)
    assert _lire(ctx, 'journal.envoyees') == []
    assert _lire(ctx, 'journal.defaultEmpeche') == []


def test_F9_n_est_pas_capture_par_le_bloc_macros():
    """F9 valide le QSO — elle est traitée par le bloc suivant et ne doit pas
    être avalée ici."""
    ctx = _moteur()
    ctx.eval("appuyer('F9')")
    assert _lire(ctx, 'journal.envoyees') == []
    assert _lire(ctx, 'journal.defaultEmpeche') == []


def test_la_touche_suit_la_macro_reaffectee():
    """L'utilisateur peut réaffecter la touche d'une macro (double-clic sur le
    bouton). Le clavier doit suivre ce qui est ÉCRIT sur le bouton, donc la
    recherche se fait par libellé de touche, pas par position dans la liste."""
    macros = [{'key': 'F8', 'label': 'derniere-en-premier', 'text': 'x'},
              {'key': 'F1', 'label': 'premiere-en-second', 'text': 'y'}]
    ctx = _moteur(macros=macros)
    ctx.eval("appuyer('F8')")
    assert _lire(ctx, 'journal.envoyees') == [0], "F8 doit viser la macro dont key='F8'"
    ctx.eval("appuyer('F1')")
    assert _lire(ctx, 'journal.envoyees') == [0, 1]


def test_une_touche_sans_macro_ne_plante_pas():
    """Liste de macros incomplète (config ancienne, macros supprimées) : la
    touche ne doit rien envoyer, mais surtout pas lever."""
    ctx = _moteur(macros=[{'key': 'F1', 'label': 'seule', 'text': 'x'}])
    ctx.eval("appuyer('F7')")
    assert _lire(ctx, 'journal.envoyees') == []
    assert _lire(ctx, 'journal.defaultEmpeche') == ['F7']


def test_l_aide_ne_dit_plus_que_les_touches_sont_ignorees():
    """L'aide affichait « clic pour copier » et le guide affirmait noir sur
    blanc que les touches n'étaient pas interceptées. Les deux mentiraient
    maintenant."""
    with open(HTML, encoding='utf-8') as f:
        html = f.read()
    ligne = re.search(r'<span class="shortcuts-key">F1 – F8</span><span>([^<]*)</span>', html)
    assert ligne, "la ligne d'aide F1-F8 a disparu"
    assert 'clavier' in ligne.group(1) or 'Envoyer' in ligne.group(1), \
        "l'aide ne mentionne plus le déclenchement au clavier : " + ligne.group(1)

    guide = os.path.join(os.path.dirname(CONCOURS), 'docs', 'GUIDE_UTILISATEUR.md')
    with open(guide, encoding='utf-8') as f:
        texte = f.read()
    assert 'ne sont pas interceptées' not in texte, \
        "le guide affirme encore que les touches F1-F8 sont ignorées"
