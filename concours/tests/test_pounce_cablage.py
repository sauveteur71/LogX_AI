# -*- coding: utf-8 -*-
"""Le câblage : c'est ici que le logiciel se met VRAIMENT à émettre tout seul.

Le moteur de décision (logx_pounce) était livré inerte. Ce fichier couvre le
branchement sur les décodages réels — le changement le plus lourd de
conséquences du projet, isolé exprès pour être relisable seul.

OÙ TOURNE LA DÉCISION, ET POURQUOI LÀ. Dans le thread UDP de logx_wsjtx, pas
dans un handler HTTP. « Personne devant la radio » veut dire personne pour
ouvrir un navigateur : rien ne peut dépendre d'un client qui interroge. C'est
la contrainte qui a dicté toute l'architecture.

LES DEUX RAPPELS SONT ENVELOPPÉS SÉPARÉMENT de l'auto-log. Une erreur dans la
logique d'appel ne doit pas emporter le pont WSJT-X avec elle : le thread
d'écoute mort, c'est TOUT l'auto-log qui s'arrête jusqu'au redémarrage. Ce
défaut a déjà été rencontré sur ce fichier, on ne le refait pas.
"""
import os
import re
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_pounce as p    # noqa: E402
import logx_wsjtx as w     # noqa: E402


def _source(nom):
    with open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        return f.read()


# ─── Le rappel est bien branché, et isolé ────────────────────────────────────

def test_le_rappel_est_appele_sur_un_decodage():
    """Sans ce branchement, tout le moteur reste inerte quoi qu'on arme."""
    src = _source('logx_wsjtx.py')
    bloc = src[src.index("elif msg['type'] == 'decode':"):]
    bloc = bloc[:bloc.index('threading.Thread')]
    assert 'on_decode(calls, msg)' in bloc


def test_LE_RAPPEL_NE_PEUT_PAS_TUER_L_AUTO_LOG():
    """L'invariant qui compte. Le thread d'écoute mort, c'est tout le pont
    WSJT-X qui s'arrête — auto-log compris — jusqu'au redémarrage. Le rappel
    doit donc avoir SON PROPRE try, pas partager celui de record_decode."""
    src = _source('logx_wsjtx.py')
    bloc = src[src.index("elif msg['type'] == 'decode':"):]
    bloc = bloc[:bloc.index('threading.Thread')]
    avant = bloc[:bloc.index('on_decode(calls, msg)')]
    # Un try/except est ouvert JUSTE avant l'appel du rappel, distinct de celui
    # qui protège record_decode (les deux 'except' doivent exister).
    assert avant.count('try:') == 2, 'le rappel doit avoir son propre try'
    assert bloc.count('except Exception as e:') >= 2


def test_le_QSO_abouti_est_signale_a_la_session():
    """Sans ça, la session rappellerait indéfiniment une station déjà
    travaillée — le plafond finirait par tout désarmer sans qu'on comprenne."""
    src = _source('logx_wsjtx.py')
    assert 'on_qso(msg)' in src
    http = _source('logx_http.py')
    assert 'def _pounce_sur_qso' in http and 'noter_qso' in http


def test_les_deux_rappels_sont_fournis_au_demarrage():
    http = _source('logx_http.py')
    bloc = http[http.index('def _wsjtx_state_dict'):]
    bloc = bloc[:bloc.index('st = wsjtx.current_status()')]
    assert 'on_decode=_pounce_sur_decodage' in bloc
    assert 'on_qso=_pounce_sur_qso' in bloc


# ─── Le chemin chaud ─────────────────────────────────────────────────────────

def test_SORTIE_IMMEDIATE_QUAND_AUCUNE_SESSION_N_EST_ARMEE():
    """Ce chemin est traversé à CHAQUE décodage FT8, plusieurs fois par cycle
    de 15 s. Tant que la fonction n'est pas utilisée, elle ne doit rien coûter :
    ni copie du carnet, ni lookup DXCC, ni parcours du cache."""
    http = _source('logx_http.py')
    corps = http[http.index('def _pounce_sur_decodage'):]
    corps = corps[:corps.index('def _pounce_sur_qso')]
    debut = corps[:corps.index('if pounce.session.expiree()')]
    assert 'if not pounce.session.active:' in debut and 'return' in debut
    # ... et rien de coûteux avant ce test
    assert 'log_lock' not in debut and 'recent_decodes' not in debut


def test_recent_decodes_n_est_parcouru_QU_UNE_FOIS():
    """Il purge le cache sous verrou : l'appeler une fois par indicatif serait
    payé à chaque décodage, pour rien."""
    http = _source('logx_http.py')
    corps = http[http.index('def _pounce_sur_decodage'):]
    corps = corps[:corps.index('def _pounce_sur_qso')]
    # Les lignes de COMMENTAIRE sont retirées : celle qui explique justement
    # pourquoi il n'y a qu'un appel mentionne la fonction, et faisait tomber
    # une première version de ce test.
    code = '\n'.join(l for l in corps.split('\n') if not l.strip().startswith('#'))
    assert code.count('recent_decodes()') == 1


def test_UN_SEUL_APPEL_PAR_DECODAGE():
    """WSJT-X mène un QSO à la fois. Un décodage porte souvent deux indicatifs
    (destinataire + émetteur) : sans ce return, on pourrait en armer deux."""
    http = _source('logx_http.py')
    corps = http[http.index('def _pounce_sur_decodage'):]
    corps = corps[:corps.index('def _pounce_sur_qso')]
    assert corps.rstrip().endswith('return          # un seul appel par décodage : WSJT-X en mène un à la fois')


def test_l_appel_n_est_JOURNALISE_QU_APRES_un_envoi_reussi():
    """Noter un appel qui a échoué fausserait le plafond ET l'historique que
    l'opérateur relira pour savoir ce que sa station a fait."""
    http = _source('logx_http.py')
    corps = http[http.index('def _pounce_sur_decodage'):]
    corps = corps[:corps.index('def _pounce_sur_qso')]
    i_envoi = corps.index('res = wsjtx.repondre_a(call)')
    i_test = corps.index("if res.get('ok')")
    i_note = corps.index('noter_appel')
    assert i_envoi < i_test < i_note


# ─── L'intérêt réutilise les fonctions éprouvées ─────────────────────────────

def test_L_INTERET_NE_REECRIT_PAS_UNE_LOGIQUE_PARALLELE():
    """Deux réponses différentes à « cette station vaut-elle un appel ? » selon
    qu'on la pose à l'écran ou au moteur d'appel, c'est le genre d'incohérence
    qui fait perdre confiance dans tout le reste — exactement le défaut corrigé
    sur la grille bande × mode (454 cases contre 435)."""
    http = _source('logx_http.py')
    corps = http[http.index('def _interet_pounce'):http.index('def _pounce_sur_decodage')]
    assert 'awards.besoin_lotw(' in corps
    assert 'awards.suivi_carres(' in corps
    assert 'active_scope_id(cfg_snap)' in corps, 'la regle de portee doit etre appliquee'


def test_les_criteres_du_moteur_et_ceux_calcules_CONCORDENT():
    """Si l'un produit une clé que l'autre n'attend pas, le critère est
    silencieusement toujours faux : la station n'appellerait jamais, sans la
    moindre erreur."""
    http = _source('logx_http.py')
    corps = http[http.index('def _interet_pounce'):http.index('def _pounce_sur_decodage')]
    produites = set(re.findall(r"interet\['(\w+)'\]", corps))
    assert produites == set(p.MOTIFS), (produites, set(p.MOTIFS))


# ─── La minuterie coupe VRAIMENT l'émission ──────────────────────────────────

def test_LA_FIN_DE_MINUTERIE_COUPE_L_EMISSION():
    """Désarmer sans couper laisserait WSJT-X finir sa séquence — et surtout
    continuer si son propre automatique est enclenché. La minuterie doit
    couper, pas seulement cesser d'armer."""
    http = _source('logx_http.py')
    corps = http[http.index('def _pounce_sur_decodage'):]
    corps = corps[:corps.index('def _pounce_sur_qso')]
    bloc = corps[corps.index('expiree()'):corps.index('cfg_snap = ')]
    assert 'desarmer' in bloc and 'couper_emission' in bloc


def test_desarmer_a_la_main_coupe_AUSSI(monkeypatch):
    """Cliquer « arrêter » et voir la station finir sa séquence n'est pas ce
    que l'opérateur attend."""
    http = _source('logx_http.py')
    bloc = http[http.index("if self.path == '/pounce/desarmer':"):]
    bloc = bloc[:bloc.index('return', bloc.index('self._json'))]
    assert 'couper_emission' in bloc and 'auto_seulement=False' in bloc


def test_l_etat_se_desarme_aussi_quand_plus_rien_ne_decode():
    """Si la minuterie expire pendant une bande morte, aucun décodage ne vient
    la constater : la session resterait « active » à l'écran sans l'être."""
    http = _source('logx_http.py')
    bloc = http[http.index("if path == '/pounce/state':"):]
    bloc = bloc[:bloc.index('return')]
    assert 'expiree()' in bloc and 'desarmer' in bloc


# ─── Bout en bout, sans réseau ───────────────────────────────────────────────

def test_une_session_armee_puis_expiree_ne_decide_plus():
    class H:
        t = 5000.0

        def __call__(self):
            return self.t
    h = H()
    s = p.Session(horloge=h)
    s.armer({'niveau': p.NIVEAU_SANS_PERSONNE, 'criteres': ['besoin_lotw'],
             'duree_min': 5})
    d = {'call': 'DL1ABC', 'band': '14', 'mode': 'FT8'}
    assert s.decider(d, {'besoin_lotw': True})['appeler'] is True
    h.t += 5 * 60 + 1
    assert s.decider(d, {'besoin_lotw': True})['appeler'] is False
    assert s.active is False
