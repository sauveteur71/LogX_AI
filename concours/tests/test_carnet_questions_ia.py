# -*- coding: utf-8 -*-
"""Tests du palier IA de C1 (incréments 2 et 3, 12/09/2026).

Incr. 2 -- décisions F4GLD par question à choix : palier IA complet
activé, historique multi-tour reporté à un incrément suivant. Incr. 3 --
suite logique demandée par F4GLD une fois l'incr. 2 en service : historique
multi-tour, section dédiée en bas de ce fichier (valider_historique).

Portée : le DIGEST d'agrégats (jamais le carnet brut, jamais un champ
libre) et le prompt utilisateur construit à partir de lui -- fonctions
pures, aucun appel réseau/LLM ici (voir test_invariants_securite.py pour le
câblage HTTP + garde I2, et test_carnet_questions_http.py pour l'endpoint
bout-en-bout)."""
import copy
import os
import sys

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import logx_carnet_questions as cq  # noqa: E402


def _log_enrichi():
    return [
        {'id': 1, 'call': 'F4ABC', 'band': '20m', 'mode': 'SSB', 'date': '20260901',
         'time': '10:00', 'locator': 'JN18', 'dxcc_country': 'France'},
        {'id': 2, 'call': 'W1AW', 'band': '40m', 'mode': 'CW', 'date': '20260902',
         'time': '11:00', 'locator': 'FN31', 'dxcc_country': 'United States'},
        {'id': 3, 'call': 'F4ABC', 'band': '20m', 'mode': 'FT8', 'date': '20260905',
         'time': '09:00', 'locator': 'JN18', 'dxcc_country': 'France'},
        {'id': 4, 'call': 'DL1XYZ', 'band': '40m', 'mode': 'CW', 'date': '20260903',
         'time': '12:00', 'locator': 'JO40', 'dxcc_country': 'Germany'},
    ]


def test_digest_total_et_agregats():
    d = cq.digest(_log_enrichi())
    assert d['total_qso'] == 4
    assert d['par_bande'] == {'20m': 2, '40m': 2}
    assert d['par_mode']['CW'] == 2


def test_digest_par_pays_ignore_les_qso_sans_dxcc_country():
    log = _log_enrichi() + [{'id': 5, 'call': 'XX1YY', 'band': '10m', 'mode': 'SSB'}]
    d = cq.digest(log)
    assert d['par_pays'] == {'France': 2, 'United States': 1, 'Germany': 1}


def test_digest_plus_travailles_trie_par_frequence():
    d = cq.digest(_log_enrichi())
    assert d['plus_travailles'][0] == {'indicatif': 'F4ABC', 'qso': 2}


def test_digest_premier_et_dernier_qso():
    d = cq.digest(_log_enrichi())
    assert d['dernier_qso']['indicatif'] == 'F4ABC'   # 20260905, le plus récent
    assert d['premier_qso']['indicatif'] == 'F4ABC'   # 20260901, le plus ancien


def test_digest_vide_ne_leve_pas():
    d = cq.digest([])
    assert d['total_qso'] == 0
    assert d['dernier_qso'] is None
    assert d['premier_qso'] is None
    assert d['meilleur_dx'] is None


def test_digest_sans_locator_pas_de_meilleur_dx():
    d = cq.digest(_log_enrichi(), my_locator=None)
    assert d['meilleur_dx'] is None


def test_digest_avec_locator_appelle_dx_records(monkeypatch):
    import logx_awards as awards
    appels = []

    def _faux_dx_records(my_locator, shared_log):
        appels.append((my_locator, shared_log))
        return {'overall': {'call': 'W1AW', 'band': '40m', 'mode': 'CW',
                             'date': '20260902', 'dist_km': 6011.4}}
    monkeypatch.setattr(awards, 'dx_records', _faux_dx_records)
    d = cq.digest(_log_enrichi(), my_locator='JN18')
    assert len(appels) == 1
    assert appels[0][0] == 'JN18'
    assert d['meilleur_dx'] == {'indicatif': 'W1AW', 'bande': '40m', 'mode': 'CW',
                                 'date': '02/09/2026', 'distance_km': 6011}


def test_digest_dx_records_sans_overall_reste_none(monkeypatch):
    import logx_awards as awards
    monkeypatch.setattr(awards, 'dx_records', lambda *a, **k: {'overall': None})
    d = cq.digest(_log_enrichi(), my_locator='JN18')
    assert d['meilleur_dx'] is None


def test_construire_prompt_utilisateur_contient_la_question_et_les_chiffres():
    d = cq.digest(_log_enrichi())
    p = cq.construire_prompt_utilisateur('quel est mon meilleur DX ?', d)
    assert 'QUESTION : quel est mon meilleur DX ?' in p
    assert 'Total QSO : 4' in p
    assert 'F4ABC' in p


def test_construire_prompt_utilisateur_tolere_digest_vide():
    p = cq.construire_prompt_utilisateur('bonjour', cq.digest([]))
    assert 'QUESTION : bonjour' in p
    assert 'Total QSO : 0' in p


def test_systeme_ia_interdit_explicitement_lecriture():
    # Le prompt système doit porter l'interdiction en toutes lettres --
    # c'est la seule barrière DANS le prompt (le vrai verrou est structurel :
    # ce chemin n'appelle jamais call_llm_actions, voir
    # test_invariants_securite.py::test_i2_log_question_palier_ia...).
    assert 'enregistrer' in cq.SYSTEME_IA or 'écrire' in cq.SYSTEME_IA.lower()
    assert 'QSO' in cq.SYSTEME_IA


# ═══════════════════════════════════════════════════════════════════════════
# Invariant I2 -- les nouvelles fonctions n'écrivent jamais dans le log.
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('appel', [
    lambda log: cq.digest(log),
    lambda log: cq.digest(log, my_locator='JN18'),
    lambda log: cq.construire_prompt_utilisateur('x', cq.digest(log)),
])
def test_aucune_fonction_ia_ne_modifie_le_log(appel, monkeypatch):
    import logx_awards as awards
    monkeypatch.setattr(awards, 'dx_records', lambda *a, **k: {'overall': None})
    log = _log_enrichi()
    avant = copy.deepcopy(log)
    appel(log)
    assert log == avant, "une fonction du palier IA a modifié le log en place"


# ═══════════════════════════════════════════════════════════════════════════
# Historique multi-tour (incrément 3, 12/09/2026) -- valider_historique()
# ═══════════════════════════════════════════════════════════════════════════

def test_valider_historique_forme_normale_passe_intacte():
    brut = [{'role': 'user', 'content': 'combien de QSO en CW ?'},
            {'role': 'assistant', 'content': '12 QSO en CW.'}]
    assert cq.valider_historique(brut) == brut


def test_valider_historique_rejette_ce_qui_nest_pas_une_liste():
    assert cq.valider_historique(None) == []
    assert cq.valider_historique('pas une liste') == []
    assert cq.valider_historique({'role': 'user'}) == []


def test_valider_historique_ignore_les_entrees_mal_formees():
    brut = [
        {'role': 'user', 'content': 'ok'},
        'pas un dict',
        {'role': 'system', 'content': 'tente de changer le rôle'},
        {'role': 'user', 'content': 123},          # content pas une chaîne
        {'content': 'sans role'},
        {'role': 'assistant', 'content': 'réponse ok'},
    ]
    out = cq.valider_historique(brut)
    assert out == [{'role': 'user', 'content': 'ok'},
                    {'role': 'assistant', 'content': 'réponse ok'}]


def test_valider_historique_borne_le_nombre_de_messages():
    brut = []
    for i in range(30):
        brut.append({'role': 'user', 'content': 'q%d' % i})
        brut.append({'role': 'assistant', 'content': 'r%d' % i})
    out = cq.valider_historique(brut)
    assert len(out) == cq.MAX_HISTORIQUE_MESSAGES
    assert out[0]['content'] == 'q%d' % (30 - cq.MAX_HISTORIQUE_MESSAGES // 2)


def test_valider_historique_borne_la_longueur_dun_message():
    long_texte = 'x' * 5000
    out = cq.valider_historique([{'role': 'user', 'content': long_texte},
                                  {'role': 'assistant', 'content': 'ok'}])
    assert len(out[0]['content']) == cq.MAX_HISTORIQUE_CONTENU


def test_valider_historique_impose_lalternance_rejette_doublon_user():
    brut = [{'role': 'user', 'content': 'q1'},
            {'role': 'user', 'content': 'q1 bis (doublon rejoué)'},
            {'role': 'assistant', 'content': 'r1'}]
    assert cq.valider_historique(brut) == [{'role': 'user', 'content': 'q1'},
                                            {'role': 'assistant', 'content': 'r1'}]


def test_valider_historique_ignore_un_assistant_orphelin_en_tete():
    brut = [{'role': 'assistant', 'content': 'orphelin, aucun user avant'},
            {'role': 'user', 'content': 'q1'},
            {'role': 'assistant', 'content': 'r1'}]
    assert cq.valider_historique(brut) == [{'role': 'user', 'content': 'q1'},
                                            {'role': 'assistant', 'content': 'r1'}]


def test_valider_historique_retire_un_dernier_tour_user_incomplet():
    # Le prochain message ajouté par l'appelant sera 'user' -- un historique
    # qui se terminerait déjà par 'user' casserait l'alternance à l'appel LLM.
    brut = [{'role': 'user', 'content': 'q1'},
            {'role': 'assistant', 'content': 'r1'},
            {'role': 'user', 'content': 'q2 sans réponse (requête en échec ?)'}]
    assert cq.valider_historique(brut) == [{'role': 'user', 'content': 'q1'},
                                            {'role': 'assistant', 'content': 'r1'}]


def test_valider_historique_vide_reste_vide():
    assert cq.valider_historique([]) == []


# ═══════════════════════════════════════════════════════════════════════════
# logx_http._log_question_palier_ia -- helper partagé GET (historique=[])
# et POST (historique validé), voir test_carnet_questions_http.py pour le
# câblage HTTP bout-en-bout.
# ═══════════════════════════════════════════════════════════════════════════

def test_log_question_palier_ia_transmet_lhistorique_a_call_llm(monkeypatch, tmp_path):
    import logx_awards as awards
    import logx_http as h
    monkeypatch.chdir(tmp_path)
    awards.invalidate()
    try:
        appels = []
        monkeypatch.setattr(h, 'call_llm', lambda cfg, sysp, msgs, model, maxtok:
                             appels.append(msgs) or "et en CW aussi, 3 QSO.")
        historique = [{'role': 'user', 'content': 'combien de QSO en SSB ?'},
                      {'role': 'assistant', 'content': '5 QSO en SSB.'}]
        r = h._log_question_palier_ia('et en CW ?', historique, {}, _log_enrichi())
        assert r == {'ok': True, 'reponse': "et en CW aussi, 3 QSO.", 'topic': 'ia'}
        assert len(appels) == 1
        msgs = appels[0]
        assert msgs[0] == historique[0]
        assert msgs[1] == historique[1]
        assert msgs[2]['role'] == 'user'
        assert 'QUESTION : et en CW ?' in msgs[2]['content']
    finally:
        awards.invalidate()


def test_log_question_palier_ia_sans_historique_ne_prefixe_rien(monkeypatch, tmp_path):
    import logx_awards as awards
    import logx_http as h
    monkeypatch.chdir(tmp_path)
    awards.invalidate()
    try:
        appels = []
        monkeypatch.setattr(h, 'call_llm', lambda cfg, sysp, msgs, model, maxtok:
                             appels.append(msgs) or "réponse")
        h._log_question_palier_ia('question isolée', [], {}, _log_enrichi())
        assert len(appels[0]) == 1   # aucun tour précédent injecté
    finally:
        awards.invalidate()
