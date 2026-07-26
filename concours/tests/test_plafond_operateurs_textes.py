# -*- coding: utf-8 -*-
"""Le plafond d'operateurs ANNONCE doit etre celui qui s'applique VRAIMENT.

Le commit 14d6204 a fait passer le plafond de 5 a 40 en CONCOURS et en
EXPEDITION (opRowCap() ne distingue plus que le mode 'simple'), mais les
deux textes qui DECRIVENT cette regle a l'utilisateur sont restes a 5 :

- CONFIG_HELP.usage_mode, affiche verbatim par l'assistant de la page
  CONFIG (le bouton « Quel mode d'utilisation choisir ? » retombe sur
  l'aide locale quand aucune cle API n'est renseignee), et injecte dans
  le system prompt de l'IA quand il y en a une ;
- le guide d'aide logicielle de logx_prompts.build_system_prompt(),
  donne a l'IA comme verite autoritaire.

Consequence : a l'operateur de DXpedition qui veut declarer ses 10
equipiers, le logiciel repondait « bascule en RADIOCLUB » alors que son
mode le permet deja. C'est precisement le cas d'usage a l'origine de
14d6204 que sa propre documentation integree decourageait.

Ces tests ne comparent a aucune constante ecrite ici : ils lisent le
plafond REEL dans opRowCap() et exigent que les textes disent la meme
chose. Un futur changement de plafond les fera donc echouer tant que la
documentation integree n'aura pas suivi.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(BASE, 'logx_configuration.html')
sys.path.insert(0, BASE)

import logx_prompts  # noqa: E402

# « jusqu'a N operateurs » sous toutes ses formes (singulier/pluriel).
PLAFOND_ANNONCE = re.compile(r"jusqu'à\s+(\d+)\s+opérateur", re.IGNORECASE)


def _source_html():
    with open(HTML, encoding='utf-8') as f:
        return f.read()


def _plafond_reel(src):
    """Le plafond hors mode 'simple', lu dans le code qui l'applique."""
    m = re.search(r"function\s+opRowCap\s*\(\s*\)\s*\{[^}]*?"
                  r"===\s*'simple'\s*\?\s*\d+\s*:\s*(\d+)", src, re.S)
    assert m, ("opRowCap() n'a plus la forme attendue : ces tests ne peuvent "
               "plus deduire le plafond reel, il faut les mettre a jour")
    return int(m.group(1))


def _aide_usage_mode(src):
    """La valeur de CONFIG_HELP.usage_mode, telle qu'affichee a l'utilisateur."""
    m = re.search(r'^\s*usage_mode:\s*"(.*?)",\s*$', src, re.M | re.S)
    assert m, 'CONFIG_HELP.usage_mode introuvable dans logx_configuration.html'
    return m.group(1)


def test_le_plafond_reel_est_bien_lisible():
    """Garde-fou : si ce test tombe, les trois suivants ne prouvent plus rien."""
    assert _plafond_reel(_source_html()) > 1


def test_aide_usage_mode_n_annonce_pas_un_plafond_perime():
    """L'aide de MODE D'UTILISATION ne doit citer que le plafond en vigueur."""
    src = _source_html()
    cap = _plafond_reel(src)
    annonces = [int(n) for n in PLAFOND_ANNONCE.findall(_aide_usage_mode(src))]
    perimes = sorted({n for n in annonces if n != cap})
    assert not perimes, (
        "CONFIG_HELP.usage_mode annonce un plafond de %s operateur(s) alors "
        "que opRowCap() en autorise %d hors mode 'simple' : l'aide affichee "
        "contredit le logiciel." % (perimes, cap))


def test_aide_usage_mode_annonce_le_plafond_en_vigueur():
    """Et elle doit le citer : une aide muette sur le sujet ne suffit pas."""
    src = _source_html()
    cap = _plafond_reel(src)
    assert cap in [int(n) for n in PLAFOND_ANNONCE.findall(_aide_usage_mode(src))], (
        "CONFIG_HELP.usage_mode ne dit nulle part « jusqu'à %d opérateurs »" % cap)


def test_libelle_radioclub_ne_s_approprie_pas_le_plafond():
    """Le <select> laissait croire que 40 etait une exclusivite RADIOCLUB,
    ce qui pousse a changer de mode sans raison."""
    src = _source_html()
    cap = _plafond_reel(src)
    m = re.search(r'<option value="radioclub">(.*?)</option>', src)
    assert m, 'option RADIOCLUB introuvable'
    assert str(cap) not in m.group(1), (
        "le libelle RADIOCLUB annonce le plafond de %d comme s'il lui etait "
        "propre : %r" % (cap, m.group(1)))


def test_prompt_ia_n_annonce_pas_un_plafond_perime():
    """Le guide donne a l'IA sert de reference autoritaire (« n'invente
    jamais un champ ») : un plafond faux ici, et l'assistant renvoie
    l'utilisateur vers RADIOCLUB sans necessite."""
    cap = _plafond_reel(_source_html())
    prompt = logx_prompts.build_system_prompt({
        'callsign': 'F4GLD', 'usage_mode': 'expedition', 'locator': 'JN15XC'})
    annonces = [int(n) for n in PLAFOND_ANNONCE.findall(prompt)]
    perimes = sorted({n for n in annonces if n != cap})
    assert not perimes, (
        "le system prompt annonce un plafond de %s operateur(s) au lieu de %d"
        % (perimes, cap))
    assert 'OP1-OP5' not in prompt, (
        "le system prompt enumere les operateurs jusqu'a OP5 : l'IA en "
        "deduira qu'au-dela il faut changer de mode")


def test_prompt_ia_annonce_le_plafond_en_vigueur():
    cap = _plafond_reel(_source_html())
    prompt = logx_prompts.build_system_prompt({
        'callsign': 'F4GLD', 'usage_mode': 'expedition', 'locator': 'JN15XC'})
    assert cap in [int(n) for n in PLAFOND_ANNONCE.findall(prompt)], (
        "le system prompt ne dit nulle part « jusqu'à %d opérateurs »" % cap)
