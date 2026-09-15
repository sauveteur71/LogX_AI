# -*- coding: utf-8 -*-
"""Câblage UI de « QUESTIONS SUR LE CARNET » dans LOGBOOK (C1, incrément 1).

cadrage docs/superpowers/specs/2026-09-11-c1-requetes-langage-naturel-
carnet.md, « logbook » validé par F4GLD le 11/09/2026. Même esprit que
test_logbook_corbeille_ui.py (fonctionnalité pas expert-only, câblage réel
plutôt qu'une simple présence de texte).

Découpage logx_logbook.js (14/09/2026, EV-7) : l'implémentation vit
désormais dans logx_carnet_questions.js (déplacement pur, candidat vérifié
non atteignable depuis submitQSO()/renderLog()/autoFillQso() avant tout
déplacement) -- seuls l'entrée de menu et le HTML de l'overlay restent
dans logx_logbook.js/html.
"""
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(nom):
    with open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        return f.read()


def test_entree_de_menu_presente_et_pas_expert_only():
    js = _lire('logx_logbook.js')
    i = js.index("['❓', 'QUESTIONS SUR LE CARNET', 'showCarnetQuestions']")
    # PAS dans le groupe 'expert-only' -- même raisonnement que CORBEILLE
    # juste au-dessus dans le tableau `suivi`.
    bloc = js[max(0, i - 400):i]
    assert 'showCorbeille' in bloc, "doit rester dans le même groupe que CORBEILLE"


def test_overlay_present_avec_bouton_fermer():
    html = _lire('logx_logbook.html')
    assert 'id="carnetQuestionsOverlay"' in html
    m = re.search(r'<div class="shortcuts-overlay"\s+id="carnetQuestionsOverlay"[^>]*>', html)
    assert m
    bloc = html[m.end():m.end() + 3000]
    fin_bloc = bloc.index('</div>\n</div>')
    bloc = bloc[:fin_bloc]
    assert 'closeCarnetQuestions()' in bloc
    assert 'id="qcReponse"' in bloc
    assert 'id="qcIndicatifInput"' in bloc
    # les 4 questions rapides + « déjà travaillé »
    for topic in ('total', 'par_bande', 'par_mode', 'dernier', 'deja_travaille'):
        assert "poserQuestionCarnet('%s')" % topic in bloc
    # incr. 2 : question libre -> palier IA
    assert 'id="qcLibreInput"' in bloc
    assert 'poserQuestionLibreCarnet()' in bloc


_DEFS_DEPLACEES = (
    'let carnetHistorique',
    'const CARNET_HISTORIQUE_MAX',
    'function showCarnetQuestions(',
    'function closeCarnetQuestions(',
    'async function poserQuestionCarnet(',
    'async function poserQuestionLibreCarnet(',
    'function reinitialiserConversationCarnet(',
    'function majIndicateurConversationCarnet(',
)


def test_definitions_retirees_de_logx_logbook_js():
    # PROPRIÉTÉ D'ÉQUIVALENCE : plus aucune de ces définitions dans le
    # monolithe (sinon double définition -- la seconde chargée écraserait
    # silencieusement la première).
    js = _lire('logx_logbook.js')
    for d in _DEFS_DEPLACEES:
        assert d not in js, "définition encore présente dans logx_logbook.js : %s" % d


def test_definie_exactement_une_fois_au_total():
    js = _lire('logx_logbook.js')
    new = _lire('logx_carnet_questions.js')
    for d in _DEFS_DEPLACEES:
        assert (js.count(d) + new.count(d)) == 1, "définition non-unique : %s" % d


def test_script_carnet_questions_charge_avant_logx_logbook():
    html = _lire('logx_logbook.html')
    i_carnet = html.index('<script src="logx_carnet_questions.js">')
    i_logbook = html.index('<script src="logx_logbook.js">')
    assert i_carnet < i_logbook, (
        "logx_carnet_questions.js doit charger AVANT logx_logbook.js "
        "(portee globale partagee, meme patron que tout EV-7)")


def test_js_fonctions_de_cablage_presentes():
    js = _lire('logx_carnet_questions.js')
    for fn in ('showCarnetQuestions', 'closeCarnetQuestions', 'poserQuestionCarnet'):
        assert 'function %s' % fn in js or 'async function %s' % fn in js


def test_poser_question_appelle_log_question():
    js = _lire('logx_carnet_questions.js')
    i = js.index('async function poserQuestionCarnet')
    corps = js[i:i + 1200]
    assert "fetch('/log/question" in corps


def test_reponse_assignee_via_textcontent_jamais_innerhtml():
    """La réponse vient du serveur et PEUT échoïr l'indicatif fourni par
    l'utilisateur (repondre() -> 'Aucun QSO trouvé avec %s.' etc.) -- une
    affectation via innerHTML ouvrirait une XSS réfléchie si un indicatif
    contenant du balisage était un jour renvoyé tel quel. textContent
    échappe structurellement ce risque."""
    js = _lire('logx_carnet_questions.js')
    i = js.index('async function poserQuestionCarnet')
    corps = js[i:i + 1200]
    assert 'box.textContent = d.reponse' in corps
    assert 'box.innerHTML' not in corps


def test_css_qc_box_existe():
    html = _lire('logx_logbook.html')
    assert '.qc-box' in html


# ═══════════════════════════════════════════════════════════════════════════
# Question libre -> palier IA (C1, incrément 2, 12/09/2026)
# ═══════════════════════════════════════════════════════════════════════════

def test_js_fonction_question_libre_presente():
    js = _lire('logx_carnet_questions.js')
    assert 'async function poserQuestionLibreCarnet' in js


def test_question_libre_envoie_texte_et_historique_en_post():
    """Contrairement à poserQuestionCarnet (topic préréglé côté client, GET),
    la question libre (incr. 3, historique multi-tour) POSTe `texte` et
    `historique` -- jamais de `topic`, c'est le dispatch serveur motif-fixe-
    puis-IA (logx_http.py) qui décide."""
    js = _lire('logx_carnet_questions.js')
    i = js.index('async function poserQuestionLibreCarnet')
    corps = js[i:i + 1500]
    assert "fetch('/log/question'" in corps
    assert "method: 'POST'" in corps
    assert 'texte: texte' in corps
    assert 'historique: carnetHistorique' in corps
    assert 'topic:' not in corps


def test_question_libre_reponse_assignee_via_textcontent_jamais_innerhtml():
    js = _lire('logx_carnet_questions.js')
    i = js.index('async function poserQuestionLibreCarnet')
    corps = js[i:i + 1500]
    assert 'box.textContent = d.reponse' in corps
    assert 'box.innerHTML' not in corps


def test_champ_libre_present_dans_loverlay_avec_bouton_demander():
    html = _lire('logx_logbook.html')
    assert 'id="qcLibreInput"' in html
    i = html.index('id="qcLibreInput"')
    bloc = html[i:i + 300]
    assert 'poserQuestionLibreCarnet()' in bloc


# ═══════════════════════════════════════════════════════════════════════════
# Historique multi-tour (C1, incrément 3, 12/09/2026)
# ═══════════════════════════════════════════════════════════════════════════

def test_js_fonctions_historique_presentes():
    js = _lire('logx_carnet_questions.js')
    assert 'let carnetHistorique' in js
    assert 'function reinitialiserConversationCarnet' in js
    assert 'function majIndicateurConversationCarnet' in js


def test_seul_un_tour_ia_alimente_lhistorique():
    """Un topic déterministe (ex. 'deja_travaille' reconnu dans le texte
    libre) ne doit PAS être poussé dans carnetHistorique -- seul un vrai
    tour LLM (topic === 'ia') a sa place dans le contexte multi-tour."""
    js = _lire('logx_carnet_questions.js')
    i = js.index('async function poserQuestionLibreCarnet')
    corps = js[i:js.index('function reinitialiserConversationCarnet')]
    assert "d.topic === 'ia'" in corps
    assert 'carnetHistorique.push' in corps


def test_historique_borne_cote_client():
    js = _lire('logx_carnet_questions.js')
    assert 'CARNET_HISTORIQUE_MAX' in js
    assert 'carnetHistorique.slice(-CARNET_HISTORIQUE_MAX)' in js


def test_reinitialiser_vide_lhistorique():
    js = _lire('logx_carnet_questions.js')
    i = js.index('function reinitialiserConversationCarnet')
    corps = js[i:i + 200]
    assert 'carnetHistorique = []' in corps


def test_bouton_reset_present_dans_loverlay_et_cache_par_defaut():
    html = _lire('logx_logbook.html')
    assert 'id="qcResetBtn"' in html
    i = html.index('id="qcResetBtn"')
    bloc = html[max(0, i - 120):i + 120]
    assert 'reinitialiserConversationCarnet()' in bloc
    assert 'hidden' in bloc   # invisible tant qu'aucune conversation n'existe
