# -*- coding: utf-8 -*-
"""Réponses HORS-LIGNE du chat (évolution IA #4, 01/08/2026).

En expédition SANS internet, tout le chat échouait « ❌ vérifie ta clé API »
pile pendant les 15 jours où le logiciel sert. Le coach étant déjà 100 %
déterministe, on expose /coach/answer (zéro LLM) et les boutons rapides du chat
y basculent. Ces tests figent le formateur answer_text et l'endpoint.
"""
import http.server
import json
import os
import re
import sys
import threading
import urllib.request

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_coach as coach   # noqa: E402
import logx_http as h        # noqa: E402


def _state():
    return {
        'clock': {'status': 'en_cours', 'remaining_h': 5.4, 'pct_done': 63},
        'stats': {'qso_total': 120, 'score': 340, 'score_with_mults': 1200,
                  'exchange_mults': ['A', 'B', 'C'], 'departments': 12,
                  'by_band': {'14': 60, '7': 40, '3.5': 20},
                  'qso_last_hour': 18, 'rate_avg': 22.5, 'minutes_since_last': 3},
        'band_plan': [{'band': '14', 'reason': 'ouverte à cette heure'},
                      {'band': '7', 'reason': 'hors créneau de propagation'}],
        'hints': [{'text': 'Change de bande, le rythme baisse'}],
    }


def test_answer_score_donne_qso_score_horloge():
    txt = coach.answer_text(_state(), 'score')
    assert '120' in txt and '340' in txt          # QSO + points
    assert '1200' in txt                           # score avec mults
    assert '5 h' in txt and '63' in txt            # horloge


def test_answer_prop_liste_les_bandes():
    txt = coach.answer_text(_state(), 'prop')
    assert '14 MHz' in txt and 'ouverte' in txt
    # 'openings' est un alias du même sujet
    assert coach.answer_text(_state(), 'openings') == txt


def test_answer_mults_compte_et_repartit_par_bande():
    txt = coach.answer_text(_state(), 'mults')
    assert '3' in txt                              # 3 mults d'échange
    assert '14 MHz (60)' in txt                    # répartition triée par bande
    assert txt.index('14 MHz (60)') < txt.index('7 MHz (40)')   # tri décroissant


def test_answer_resume_inclut_un_conseil():
    txt = coach.answer_text(_state(), 'resume')
    assert '💡' in txt and 'rythme' in txt.lower()


def test_answer_spots_reste_honnete_hors_ligne():
    """« Suis-je spoté ? » N'EST PAS répondable sans réseau : réponse honnête,
    jamais une valeur inventée."""
    txt = coach.answer_text(_state(), 'spots')
    assert 'Hors-ligne' in txt or 'hors-ligne' in txt.lower()


def test_answer_texte_libre_renvoie_vide():
    """Un sujet inconnu (texte libre) renvoie '' : le client montre alors le
    message « boutons seulement »."""
    assert coach.answer_text(_state(), '') == ''
    assert coach.answer_text(_state(), 'raconte moi une blague') == ''


def test_answer_ne_plante_pas_sur_etat_vide():
    for topic in ('score', 'prop', 'mults', 'resume', 'spots', 'projection'):
        coach.answer_text({}, topic)              # aucun KeyError


# ─── Projection de fin de concours (backlog CARTE IA #118) ─────────────────

def test_answer_projection_estime_qso_et_score_futurs():
    txt = coach.answer_text(_state(), 'projection')
    # _state() : 120 QSO à 22.5/h, 5.4 h restantes -> projection > état actuel.
    assert 'QSO' in txt
    assert 'estimé' in txt.lower()
    qso_proj = int(re.search(r'~(\d+) QSO', txt).group(1))
    score_proj = int(re.search(r'estimé\s*:\s*~(\d+)', txt).group(1))
    assert qso_proj > 120                          # plus que le total actuel
    assert score_proj > 1200                        # plus que score_with_mults actuel


def test_answer_projection_reste_honnete_sur_ses_limites():
    """L'estimation ne doit jamais se présenter comme une certitude -- un
    avertissement sur l'hypothèse (rythme constant) doit toujours accompagner
    le chiffre."""
    txt = coach.answer_text(_state(), 'projection')
    assert 'rythme constant' in txt.lower() or 'estimation' in txt.lower()


def test_answer_projection_hors_concours_ne_projette_pas():
    state = _state()
    state['clock']['status'] = 'avant'
    txt = coach.answer_text(state, 'projection')
    assert 'QSO' not in txt or 'estimé' not in txt.lower()   # pas de chiffre inventé
    assert txt                                      # message explicatif quand même


def test_answer_projection_pas_assez_de_qso_reste_honnete():
    """Sous le seuil de fiabilité (même seuil que hint_rate_drop, 10 QSO),
    aucune projection n'est risquée -- mieux vaut le dire que d'halluciner
    un score sur 2 QSO."""
    state = {'clock': {'status': 'en_cours', 'remaining_h': 5}, 'stats': {'qso_total': 3, 'rate_avg': 10}}
    txt = coach.answer_text(state, 'projection')
    assert 'estimé' not in txt.lower()
    assert txt


def test_answer_projection_sans_rate_avg_reste_honnete():
    """Tout début de concours : rate_avg est encore None (clock['elapsed_h']
    trop proche de 0) -- pas de division par un rythme inexistant."""
    state = {'clock': {'status': 'en_cours', 'remaining_h': 47}, 'stats': {'qso_total': 2, 'rate_avg': None}}
    txt = coach.answer_text(state, 'projection')
    assert 'estimé' not in txt.lower()


# ─── Endpoint /coach/answer (zéro LLM) ──────────────────────────────────────

@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % port
    srv.shutdown()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return json.loads(r.read())


def test_endpoint_repond_a_un_bouton_sans_llm(serveur):
    d = _get(serveur, '/coach/answer?topic=score&lang=fr')
    assert d['ok'] is True
    assert d['topic'] == 'score'
    assert d['text']                              # texte non vide, aucun appel IA


def test_endpoint_sujet_inconnu_ok_false(serveur):
    d = _get(serveur, '/coach/answer?topic=blague')
    assert d['ok'] is False
    assert d['text'] == ''


def test_endpoint_projection_repond_sans_llm(serveur):
    d = _get(serveur, '/coach/answer?topic=projection&lang=fr')
    assert d['ok'] is True
    assert d['topic'] == 'projection'
    assert d['text']
