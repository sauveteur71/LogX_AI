# -*- coding: utf-8 -*-
"""Régression : la modale « jamais configuré » de LOGBOOK
(#setupModal) ne doit PAS être court-circuitée par une fausse identité par
défaut. Avant ce correctif, #setupCallsign/#setupLocator portaient un
`value="F6KQJ/P"`/`value="JN15XC"` codé en dur EN PLUS de leur
`placeholder=` -- prefillSetupFromConfig() (logx_logbook.js) teste
`callEl.value && locEl.value` pour décider d'afficher la modale ou de
démarrer directement : avec un `value=` toujours vrai dès le chargement de
la page, ce test était toujours vrai même sur une installation jamais
configurée, la modale ne s'affichait JAMAIS et setupDone() persistait
silencieusement F6KQJ/P dans localStorage comme identité réelle.

Trouvé par l'audit trouvabilité/intuitivité du 09/08/2026 (F4GLD)."""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_logbook.html')


def _html():
    with open(HTML_PATH, encoding='utf-8') as f:
        return f.read()


def test_setup_callsign_na_pas_de_value_code_en_dur():
    src = _html()
    m = re.search(r'<input[^>]*id="setupCallsign"[^>]*>', src)
    assert m, 'input #setupCallsign introuvable dans logx_logbook.html'
    tag = m.group(0)
    assert 'placeholder="F6KQJ/P"' in tag, 'le placeholder doit rester (aide visuelle)'
    assert 'value=' not in tag, (
        'un value= codé en dur sur #setupCallsign rend le champ toujours '
        '"rempli" dès le chargement -- la modale de première config ne '
        "s'affiche alors plus jamais, voir prefillSetupFromConfig()")


def test_setup_locator_na_pas_de_value_code_en_dur():
    src = _html()
    m = re.search(r'<input[^>]*id="setupLocator"[^>]*>', src)
    assert m, 'input #setupLocator introuvable dans logx_logbook.html'
    tag = m.group(0)
    assert 'placeholder="JN15XC"' in tag, 'le placeholder doit rester (aide visuelle)'
    assert 'value=' not in tag, (
        'un value= codé en dur sur #setupLocator rend le champ toujours '
        '"rempli" dès le chargement -- la modale de première config ne '
        "s'affiche alors plus jamais, voir prefillSetupFromConfig()")


def test_prefill_teste_bien_callsign_et_locator_avant_de_masquer_la_modale():
    """Garde-fou de non-régression sur la logique elle-même (pas seulement
    le HTML) : si ce test de complétude disparaissait un jour du fichier
    JS, la protection ci-dessus perdrait tout son sens."""
    with open(os.path.join(BASE, 'logx_logbook.js'), encoding='utf-8') as f:
        js = f.read()
    assert 'if(callEl.value && locEl.value){' in js
