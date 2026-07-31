# -*- coding: utf-8 -*-
"""L'assistant doit s'adapter au MODE D'UTILISATION, pas parler concours partout.

SIGNALÉ À L'ÉCRAN : « pourquoi l'IA met ça alors que je suis sans concours ! »
La capture montrait le coach annonçant « départ dans 18.2 h — passe la
CHECKLIST du logbook » avec « aucun concours » dans la barre de statut.

DEUX CAUSES, indépendantes :

1. `contest_clock()` calculait l'horloge depuis contest_start_date /
   contest_end_date SANS vérifier qu'un concours est réellement sélectionné.
   Les dates d'une épreuve précédente survivent dans la configuration : le
   coach avait donc un compte à rebours parfaitement cohérent... vers rien.

2. `usage_mode` existe dans la config depuis longtemps — sauvegarde, stockage,
   validateur et écran mural le lisent — mais NI logx_prompts.py NI
   logx_coach.py ne le regardaient. L'assistant ignorait donc totalement si
   l'opérateur fait du trafic courant, du concours ou de l'expédition.

MODE DÉCLARÉ ≠ MODE EFFECTIF : le sélecteur de CONFIG vaut « CONCOURS » par
défaut. Quelqu'un qui n'a jamais choisi d'épreuve est donc en mode « contest »
déclaré tout en chassant le DX. C'est l'usage RÉEL qui doit piloter l'IA.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_mode as M       # noqa: E402
import logx_coach as C      # noqa: E402
import logx_prompts as P    # noqa: E402


def _cfg(**kw):
    """Config type : des dates de concours TRAÎNENT, comme dans la vraie vie."""
    base = {'callsign': 'F4GLD', 'locator': 'JN15WD', 'contest': '',
            'usage_mode': 'contest',
            'contest_start_date': '20260801', 'contest_end_date': '20260802',
            'contest_end_utc': '2359'}
    base.update(kw)
    return base


# ─── Mode effectif ───────────────────────────────────────────────────────────

def test_SANS_CONCOURS_le_mode_contest_declare_retombe_sur_SIMPLE():
    """Le cœur du signalement : le sélecteur vaut CONCOURS par défaut, ce n'est
    pas une intention de l'opérateur."""
    assert M.mode_utilisation(_cfg()) == 'simple'


def test_avec_un_concours_le_mode_contest_est_respecte():
    assert M.mode_utilisation(_cfg(contest='CQ_WPX_SSB')) == 'contest'


@pytest.mark.parametrize('mode', ['expedition', 'radioclub'])
def test_expedition_et_radioclub_ne_sont_PAS_retrogrades(mode):
    """Une expédition sans concours reste une expédition : ses besoins (pile-up,
    autonomie, répartition) n'ont rien à voir avec du trafic courant."""
    assert M.mode_utilisation(_cfg(usage_mode=mode)) == mode


def test_un_mode_inconnu_ne_leve_pas():
    for v in ('', None, 'nimportequoi', 42):
        assert M.mode_utilisation(_cfg(usage_mode=v)) in M.MODES


def test_une_config_absente_ne_leve_pas():
    for v in (None, {}, 'texte'):
        M.mode_utilisation(v if isinstance(v, dict) else {})


# ─── L'horloge ne parle plus dans le vide ────────────────────────────────────

def test_L_HORLOGE_NE_DECOMPTE_PLUS_VERS_RIEN():
    """« départ dans 18.2 h » venait de dates résiduelles, sans épreuve."""
    clock = C.contest_clock(_cfg())
    assert clock['status'] == 'sans_concours'
    assert 'starts_in_h' not in clock


def test_avec_un_concours_l_horloge_fonctionne_toujours():
    clock = C.contest_clock(_cfg(contest='CQ_WPX_SSB'),
                            {'start_utc': '0000', 'name': 'CQ WPX'})
    assert clock['status'] in ('avant', 'en_cours', 'termine')


def test_LE_COACH_SE_TAIT_sans_concours():
    """Plutôt que d'inventer un contexte. Les suggestions « jamais travaillé »
    et la carte restent, elles, pertinentes en trafic courant."""
    clock = C.contest_clock(_cfg())
    assert C.build_hints({}, clock, {}, {}) == []


# ─── Le prompt système, quel que soit le fournisseur d'IA ────────────────────

def test_LE_PROMPT_DIT_LE_MODE():
    """Aucun réglage propre à un modèle : des phrases, que n'importe quelle IA
    peut suivre."""
    p = P.build_system_prompt(_cfg())
    assert "MODE D'UTILISATION" in p
    assert 'LOGBOOK SIMPLE' in p


def test_LE_PROMPT_INTERDIT_EXPLICITEMENT_de_parler_concours():
    """La consigne NÉGATIVE est celle qui empêche de réclamer une checklist
    d'avant-concours à quelqu'un qui chasse le DX."""
    p = P.build_system_prompt(_cfg())
    assert 'AUCUN concours' in p
    assert 'checklist' in p.lower()


def test_le_prompt_hors_concours_NE_CHARGE_PAS_les_reglements():
    """Ils occupent la fenêtre de contexte et invitent le modèle à y revenir."""
    sans = P.build_system_prompt(_cfg())
    avec = P.build_system_prompt(_cfg(contest='CQ_WPX_SSB'))
    assert 'CQ WPX' in avec
    assert 'CQ WPX' not in sans
    assert len(sans) < len(avec)


def test_le_prompt_en_concours_garde_tout():
    p = P.build_system_prompt(_cfg(contest='CQ_WPX_SSB'))
    assert 'CONCOURS' in p and 'CQ WPX' in p


@pytest.mark.parametrize('mode,attendu', [
    ('simple', 'LOGBOOK SIMPLE'),
    ('expedition', 'EXPÉDITION'),
    ('radioclub', 'RADIOCLUB'),
])
def test_chaque_mode_a_son_bloc(mode, attendu):
    p = P.build_system_prompt(_cfg(usage_mode=mode))
    assert attendu in p, mode


def test_chaque_mode_annonce_CE_QUI_COMPTE():
    """Un mode sans priorités énoncées ne guide rien."""
    for mode in M.MODES:
        b = M.BESOINS[mode]
        assert b['compte'], mode
        assert b['titre'], mode


def test_le_bloc_de_prompt_ne_leve_sur_aucune_config():
    for cfg in ({}, {'usage_mode': None}, {'contest': None},
                {'usage_mode': 'simple', 'contest': 'X'}):
        assert M.bloc_prompt(cfg)


# ─── Garde-fou : le mode arrive VRAIMENT jusqu'au prompt ─────────────────────

def test_le_cablage_existe_reellement():
    """Sans cet appel, logx_mode.py pourrait être parfait et n'être utilisé par
    personne — c'est exactement ce qui s'est passé pendant des mois avec
    `usage_mode`, présent en config et lu nulle part côté IA."""
    with open(os.path.join(CONCOURS, 'logx_prompts.py'), encoding='utf-8') as f:
        src = f.read()
    assert 'from logx_mode import' in src
    assert 'bloc_prompt(cfg)' in src
