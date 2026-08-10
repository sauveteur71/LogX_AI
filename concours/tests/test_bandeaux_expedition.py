# -*- coding: utf-8 -*-
"""Bandeaux de rythme masqués en EXPÉDITION.

DEMANDE UTILISATEUR, capture d'écran à l'appui : « supprime tout ce qui est en
jaune en mode expédition, prend trop de place ». Le surlignage couvrait la
bannière score, le récap par bande, le classement opérateurs et le graphe
QSO/heure.

CE QUE ÇA LIBÈRE, mesuré sur la page réelle : 310 px (score 86, récap bandes
96, opérateurs 60, graphe horaire 68). En expédition il n'y a NI score à
suivre, NI temps restant, NI classement à départager — on log en continu
pendant des jours. Sur un portable en /P, ces 310 px sont exactement ce qui
manquait à la zone de saisie.

LE PIÈGE DE CETTE CORRECTION, et la raison de ces tests : masquer les bandeaux
au changement de mode NE SUFFIT PAS. Trois fonctions de rendu repositionnent
leur propre bandeau à CHAQUE rafraîchissement des statistiques, chacune avec sa
copie du test `usageMode === 'simple'`. Sans les traiter, les bandeaux
réapparaissaient au premier calcul de stats — c'est-à-dire dès le premier QSO.
D'où la règle centralisée dans bandeauxRythmeMasques(), que ces tests
verrouillent.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

JS_PATH = os.path.join(CONCOURS, 'logx_logbook.js')

BANDEAUX = ('bandRecapBar', 'opStatsBar', 'hourChartBar')


def _src():
    with open(JS_PATH, encoding='utf-8') as f:
        return f.read()


# ─── La règle est-elle à UN seul endroit ? ───────────────────────────────────

def test_la_regle_existe_et_couvre_expedition():
    src = _src()
    bloc = src[src.index('function bandeauxRythmeMasques'):]
    bloc = bloc[:bloc.index('\n}')]
    assert "'simple'" in bloc and "'expedition'" in bloc


def test_les_trois_fonctions_de_rendu_passent_par_la_regle():
    """Le point qui a failli m'échapper : chacune repositionne son bandeau à
    chaque rafraîchissement des stats. Si l'une garde sa copie du test, son
    bandeau réapparaît en expédition dès le premier QSO."""
    src = _src()
    assert src.count("if(bandeauxRythmeMasques()){ bar.style.display = 'none'; return; }") == 3
    assert "if(usageMode === 'simple'){ bar.style.display = 'none'; return; }" not in src, (
        'une fonction de rendu garde sa propre copie de la regle : elle '
        'divergera, et le bandeau reviendra en expedition'
    )


def test_aucun_test_de_mode_en_dur_sur_les_bandeaux():
    """Garde-fou général : plus aucune comparaison de mode ne doit décider du
    sort d'un bandeau ailleurs que par la règle centrale."""
    src = _src()
    for ligne in src.splitlines():
        if any(b in ligne for b in BANDEAUX) and 'usageMode' in ligne:
            assert 'bandeauxRythmeMasques' in ligne, ligne


# ─── Masquer ET restaurer ────────────────────────────────────────────────────

def test_le_changement_de_mode_RESTAURE_aussi():
    """Défaut trouvé en passant : l'ancien code faisait `if(el && simple)
    el.style.display='none'` — il masquait sans jamais restaurer. Repasser de
    logbook simple à CONCOURS laissait donc les trois bandeaux invisibles
    jusqu'au rechargement de la page, un réglage impossible à annuler depuis
    l'écran où on venait de le faire."""
    src = _src()
    bloc = src[src.index("['bandRecapBar', 'opStatsBar', 'hourChartBar'].forEach"):]
    bloc = bloc[:bloc.index('});')]
    assert "sansBandeaux ? 'none' : ''" in bloc, (
        'le ternaire est ce qui restaure : sans lui on ne peut que masquer')
    assert 'if(el && simple)' not in bloc


def test_la_banniere_score_suit_la_meme_regle():
    src = _src()
    i = src.index("const scoreBanner = document.querySelector('.score-banner')")
    bloc = src[i:i + 200]
    assert "sansBandeaux ? 'none' : ''" in bloc


def test_sansBandeaux_vient_bien_de_la_regle_centrale():
    src = _src()
    assert 'const sansBandeaux = bandeauxRythmeMasques();' in src


# ─── Ce qui NE doit PAS changer ──────────────────────────────────────────────

@pytest.mark.parametrize('autre_usage', [
    "const hideNum = (expeditionMode && !realContestExchange) || usageMode === 'simple'",
    "const isSingleOp = usageMode === 'simple'",
])
def test_les_autres_usages_du_mode_simple_sont_intacts(autre_usage):
    """La centralisation ne concerne QUE les bandeaux de rythme. Le champ
    numéro de série et la détection mono-opérateur gardent leur propre règle —
    les confondre changerait le comportement de la saisie en expédition."""
    assert autre_usage in _src()


def test_le_mode_concours_garde_ses_bandeaux():
    """C'est tout l'intérêt de ces bandeaux : en concours, le rythme et le
    classement se regardent en permanence."""
    src = _src()
    bloc = src[src.index('function bandeauxRythmeMasques'):]
    bloc = bloc[:bloc.index('\n}')]
    assert "'contest'" not in bloc, "le mode concours ne doit pas masquer"
