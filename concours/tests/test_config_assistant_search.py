# -*- coding: utf-8 -*-
"""Non-régression : l'assistant CONFIGURATION (recherche locale dans
CONFIG_HELP, sans clé API) ne doit plus répondre à côté de la plaque sur une
question qui ne correspond à AUCUN champ (retour F4GLD, capture d'écran
07/08/2026 : « où se trouve le module de décodage sstv » retombait sur
l'aide du champ indicatif — sans aucun rapport).

Cause réelle : `_searchLocalHelp` scorait par SOUS-CHAÎNE
(`hay.includes(w)`), donc le mot cherché "trouve" matchait à l'intérieur de
"retrouver" dans le texte d'aide de l'indicatif — un faux positif qui
suffisait à faire remonter cette entrée alors qu'aucune entrée de
CONFIG_HELP ne parle réellement de sstv (cette base ne couvre que les
champs du formulaire CONFIG, voir logx_search.py pour la recherche sur le
contenu réel des pages). Corrigé en un match par mot ENTIER
(`_wholeWordIncludes`, frontières \\b).

Ce module exécute le VRAI code de `_wholeWordIncludes` et `_searchLocalHelp`
— extrait tel quel du fichier source par comptage d'accolades, même
technique que tests/test_config_popup_backdrop_click.py — dans un moteur JS
réel (V8 via py_mini_racer)."""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_configuration.html')


def _extract_function(src, name):
    m = re.search(r'^function %s\(' % re.escape(name), src, re.M)
    assert m, 'fonction %s introuvable dans %s' % (name, HTML_PATH)
    depth = 0
    i = src.index('{', m.start())
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[m.start():i + 1]
        i += 1


with open(HTML_PATH, encoding='utf-8') as _f:
    _HTML_SRC = _f.read()

_WHOLE_WORD_SRC = _extract_function(_HTML_SRC, '_wholeWordIncludes')
_SEARCH_LOCAL_HELP_SRC = _extract_function(_HTML_SRC, '_searchLocalHelp')

# CONFIG_HELP factice : reproduit précisément le cas du bug (une entrée
# "callsign" qui contient "retrouver", sans jamais parler de sstv) plus une
# entrée qui doit matcher normalement sur un mot entier.
_FAKE_CONFIG_HELP = {
    'callsign': "Ton indicatif radioamateur personnel. Il sert notamment à te "
                "retrouver ton pays/zone automatiquement.",
    'mode_sstv': "Affiche aussi le bouton SSTV et le panneau décodeur d'images "
                 "dans le logbook.",
}


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval('var CONFIG_HELP = ' + json.dumps(_FAKE_CONFIG_HELP) + ';')
    ctx.eval(_WHOLE_WORD_SRC)
    ctx.eval(_SEARCH_LOCAL_HELP_SRC)
    return ctx


def test_pas_de_faux_positif_sous_chaine():
    """"trouve" ne doit plus matcher à l'intérieur de "retrouver"."""
    ctx = _ctx()
    hits = ctx.call('_searchLocalHelp', 'où se trouve le module de décodage sstv')
    ids = [h['id'] for h in hits]
    assert 'callsign' not in ids


def test_trouve_la_bonne_entree_quand_elle_existe():
    ctx = _ctx()
    hits = ctx.call('_searchLocalHelp', 'où se trouve le module de décodage sstv')
    ids = [h['id'] for h in hits]
    assert 'mode_sstv' in ids


def test_aucun_hit_si_rien_ne_correspond_reellement():
    """Reproduit fidèlement le bug : CONFIG_HELP sans aucune entrée sstv."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval('var CONFIG_HELP = ' + json.dumps({'callsign': _FAKE_CONFIG_HELP['callsign']}) + ';')
    ctx.eval(_WHOLE_WORD_SRC)
    ctx.eval(_SEARCH_LOCAL_HELP_SRC)
    hits = ctx.call('_searchLocalHelp', 'où se trouve le module de décodage sstv')
    assert hits == []


def test_match_mot_entier_toujours_sensible_a_la_casse_et_aux_accents():
    ctx = _ctx()
    hits = ctx.call('_searchLocalHelp', 'INDICATIF')
    assert any(h['id'] == 'callsign' for h in hits)


def test_whole_word_includes_ne_matche_pas_une_sous_chaine():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_WHOLE_WORD_SRC)
    assert ctx.call('_wholeWordIncludes', 'il faut le retrouver ici', 'trouve') is False
    assert ctx.call('_wholeWordIncludes', 'il faut le trouve ici', 'trouve') is True


def test_whole_word_includes_echappe_les_caracteres_speciaux_regex():
    """Un mot contenant un caractère spécial regex (non échappé, il casserait
    la construction du RegExp) ne doit jamais lever d'exception JS — que la
    frontière \\b matche ou non ce cas de ponctuation n'est pas ce qui est
    vérifié ici, seulement l'absence de crash."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_WHOLE_WORD_SRC)
    assert ctx.call('_wholeWordIncludes', 'texte (avec) parentheses', '(avec)') in (True, False)
    assert ctx.call('_wholeWordIncludes', 'un plus c++ pointeurs', 'c++') in (True, False)
