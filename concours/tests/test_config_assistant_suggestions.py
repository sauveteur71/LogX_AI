# -*- coding: utf-8 -*-
"""Boutons de suggestions de l'assistant CONFIG (logx_configuration.js) — Strate 2, haute.

Les 6 questions pré-remplies étaient générées avec
`onclick="askAssistant(${JSON.stringify(q)})"`. JSON.stringify d'une chaîne
produit TOUJOURS une valeur entourée de guillemets DOUBLES ; injectée dans un
attribut onclick lui-même délimité par des guillemets doubles, le premier
guillemet fermait l'attribut prématurément → handler compilé cassé (SyntaxError)
→ cliquer une suggestion ne déclenchait RIEN (seule la saisie manuelle marchait).

Correctif : câbler chaque bouton par addEventListener (référence sur la question)
au lieu d'un onclick inline ; le libellé passe par textContent (pas d'injection).

Test structurel de non-régression : le motif buggé ne doit plus exister et le
câblage par événement doit être présent. (La vérification comportementale
complète des boutons se fait en navigateur — pratique du dépôt pour l'UI.)
"""
import pathlib

_JS = pathlib.Path(__file__).resolve().parent.parent / "logx_configuration.js"


def _src():
    return _JS.read_text(encoding="utf-8")


def test_onclick_des_suggestions_nest_plus_casse_par_json_stringify():
    src = _src()
    assert 'onclick="askAssistant(${JSON.stringify(q)})"' not in src, (
        "onclick des suggestions cassé par les guillemets de JSON.stringify "
        "(les boutons ne déclenchent rien)"
    )


def test_suggestions_cablees_par_addeventlistener():
    src = _src()
    assert "addEventListener('click', () => askAssistant(q))" in src, (
        "les boutons de suggestion doivent être câblés par addEventListener "
        "sur askAssistant(q)"
    )
