# -*- coding: utf-8 -*-
"""Câblage UI de « QUESTIONS SUR LE CARNET » dans LOGBOOK (C1, incrément 1).

cadrage docs/superpowers/specs/2026-09-11-c1-requetes-langage-naturel-
carnet.md, « logbook » validé par F4GLD le 11/09/2026. Même esprit que
test_logbook_corbeille_ui.py (fonctionnalité pas expert-only, câblage réel
plutôt qu'une simple présence de texte).
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
    bloc = html[m.end():m.end() + 2000]
    fin_bloc = bloc.index('</div>\n</div>')
    bloc = bloc[:fin_bloc]
    assert 'closeCarnetQuestions()' in bloc
    assert 'id="qcReponse"' in bloc
    assert 'id="qcIndicatifInput"' in bloc
    # les 4 questions rapides + « déjà travaillé »
    for topic in ('total', 'par_bande', 'par_mode', 'dernier', 'deja_travaille'):
        assert "poserQuestionCarnet('%s')" % topic in bloc


def test_js_fonctions_de_cablage_presentes():
    js = _lire('logx_logbook.js')
    for fn in ('showCarnetQuestions', 'closeCarnetQuestions', 'poserQuestionCarnet'):
        assert 'function %s' % fn in js or 'async function %s' % fn in js


def test_poser_question_appelle_log_question():
    js = _lire('logx_logbook.js')
    i = js.index('async function poserQuestionCarnet')
    corps = js[i:i + 1200]
    assert "fetch('/log/question" in corps


def test_reponse_assignee_via_textcontent_jamais_innerhtml():
    """La réponse vient du serveur et PEUT échoïr l'indicatif fourni par
    l'utilisateur (repondre() -> 'Aucun QSO trouvé avec %s.' etc.) -- une
    affectation via innerHTML ouvrirait une XSS réfléchie si un indicatif
    contenant du balisage était un jour renvoyé tel quel. textContent
    échappe structurellement ce risque."""
    js = _lire('logx_logbook.js')
    i = js.index('async function poserQuestionCarnet')
    corps = js[i:i + 1200]
    assert 'box.textContent = d.reponse' in corps
    assert 'box.innerHTML' not in corps


def test_css_qc_box_existe():
    html = _lire('logx_logbook.html')
    assert '.qc-box' in html
