# -*- coding: utf-8 -*-
"""Le filet anti-busted call : le code N+1 est-il enfin BRANCHÉ ?

POURQUOI CE FICHIER EXISTE. `near_matches()` (distance de Damerau-Levenshtein
sur l'index d'indicatifs du poste) était écrit, testé, et servi par l'endpoint
`/call/near` — sans un seul appelant côté client. Sixième occurrence dans ce
projet d'une valeur calculée que personne ne lit : popoutBandes, usage_mode,
path_loss_db, a_index, /data/sat sans écran, et celle-ci.

Un test qui vérifierait seulement `near_matches` passerait au vert avec le
filet toujours débranché. Ces tests vérifient donc LE FIL : le client appelle,
au bon moment, et n'agit que sur un candidat crédible.

CE QUI EST VÉRIFIÉ ICI :
  - le moment : APRÈS l'enregistrement du QSO, jamais pendant la frappe ;
  - le seuil : seul un indicatif DÉJÀ TRAVAILLÉ est proposé — un voisin jamais
    contacté n'est pas une preuve de faute, et une pastille qui se trompe est
    une pastille qu'on cesse de lire ;
  - l'endpoint rend bien ce que le client attend, sur des indicatifs réels ;
  - la pastille est invisible au repos et n'a aucun libellé non traduit.
"""
import http.server
import json
import os
import re
import sys
import threading
import urllib.parse
import urllib.request

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_callhistory as callhistory   # noqa: E402
import logx_http as httpmod              # noqa: E402


def _lire(nom):
    with open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        return f.read()


def _lire_tout():
    """logx_logbook.js + logx_busted_call.js (EV-7 13e incrément, le filet
    anti-busted call a été extrait vers son propre fichier) -- même
    convention que JS_EXTRAITS_EV7 dans test_logbook_menu_debut_fin.py.
    Nécessaire pour les 3 assertions qui lisent la DÉFINITION des fonctions
    (pas seulement leur site d'appel, resté dans logx_logbook.js)."""
    return _lire('logx_logbook.js') + '\n' + _lire('logx_busted_call.js')


# ─── LE FIL : le client appelle-t-il vraiment, et au bon moment ? ───────────

def test_l_endpoint_call_near_a_ENFIN_un_appelant():
    """LE point de ce chantier. Sans cette assertion, tout le reste peut être
    vert avec la fonction toujours morte."""
    js = _lire_tout()
    assert '/call/near?call=' in js, (
        "/call/near n'est appelé par AUCUN client — le filet est débranché")


def test_la_verification_a_lieu_APRES_l_enregistrement_pas_pendant_la_frappe():
    """Vérifier pendant la frappe, c'est interrompre l'opérateur au pire
    moment et se tromper une fois sur deux : un indicatif à demi tapé
    ressemble à tout."""
    js = _lire('logx_logbook.js')
    i_push = js.find('qsoLog.push(qso)')
    i_filet = js.find('verifierIndicatifApres(qso)')
    assert i_push != -1 and i_filet != -1
    assert i_push < i_filet, "le filet doit être posé APRÈS l'ajout au log"
    # Et surtout : jamais depuis la saisie du champ indicatif.
    onc = js[js.find('function onCallInput('):]
    onc = onc[:onc.find('\nfunction ')]
    assert 'verifierIndicatifApres' not in onc, (
        'le filet ne doit JAMAIS être déclenché par la frappe')


def test_le_candidat_propose_suit_la_regle_a_deux_detentes():
    """Trouvé en vérifiant dans un VRAI navigateur, sur le poste réel : la
    première règle (« seulement un indicatif déjà travaillé ») rejetait
    F4GLDD → F4GLD, parce que F4GLD est dans la base d'indicatifs sans avoir
    jamais été travaillé — on ne se travaille pas soi-même. Un filet qui ne se
    déclenche jamais vaut un filet débranché.

    Règle retenue : un voisin déjà travaillé passe ; sinon, seulement s'il est
    le SEUL voisin connu — deux candidats jamais travaillés, c'est une
    devinette."""
    js = _lire_tout()
    corps = js[js.find('async function verifierIndicatifApres('):]
    corps = corps[:corps.find('\nfunction afficherPastilleBusted')]
    assert 'c.qso_count > 0' in corps, 'le voisin travaillé doit primer'
    assert 'm.length === 1' in corps, (
        "sans la levée d'ambiguïté, la pastille devine entre plusieurs "
        'candidats jamais contactés')


def test_la_pastille_s_efface_toute_seule():
    js = _lire_tout()
    assert 'vieillirPastilleBusted()' in js
    assert 'restant: 2' in js, 'la pastille doit expirer au bout de 2 QSO'


def test_la_pastille_est_invisible_au_repos():
    """Rappel de la consigne d'expédition : rien qui prenne de la place tant
    qu'il n'y a rien à dire."""
    html = _lire('logx_logbook.html')
    m = re.search(r'<div id="bustedPastille"[^>]*>', html)
    assert m, 'la pastille n\'existe pas dans la page'
    assert 'display:none' in m.group(0)


@pytest.mark.parametrize('cle', [
    'corriger', 'non', '{n} QSO dans ton historique',
    '{a} corrigé en {b}',
    'QSO introuvable — corrige-le à la main dans le log.',
])
def test_les_libelles_du_filet_sont_traduits_dans_les_7_langues(cle):
    i18n = _lire('logx_i18n.js')
    n = i18n.count(json.dumps(cle, ensure_ascii=False) + ':')
    assert n >= 7, '%r : %d traductions trouvées, 7 attendues' % (cle, n)


# ─── L'endpoint, sur des indicatifs réels ──────────────────────────────────

@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield 'http://127.0.0.1:%d' % port
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _near(base, call):
    url = base + '/call/near?call=' + urllib.parse.quote(call)
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))['matches']


def test_l_endpoint_rend_le_contrat_attendu_par_le_client(server, monkeypatch):
    """Le client lit c.worked et c.qso_count : si ces noms changent, la
    pastille ne s'affiche plus jamais, en silence."""
    faux = [{'call': 'F4GLD', 'dept': '43', 'locator': 'JN15XC',
             'qso_count': 12, 'worked': True}]
    monkeypatch.setattr(callhistory, 'near_matches',
                        lambda call, log=None, limit=5: faux)
    m = _near(server, 'F4GLDD')
    assert m and set(('call', 'qso_count', 'worked')) <= set(m[0])


def test_un_indicatif_deja_connu_ne_declenche_rien(server):
    """near_matches rend [] quand l'indicatif est lui-même dans l'index :
    il n'y a rien à corriger, et une pastille serait une fausse alerte."""
    idx = callhistory.build_index([])
    if not idx:
        pytest.skip('aucun index local sur ce poste')
    connu = sorted(idx)[len(idx) // 2]
    assert _near(server, connu) == []


def test_un_indicatif_trop_court_ne_declenche_rien(server):
    """Sous 3 caractères, le bruit dépasse l'utilité."""
    assert _near(server, 'F4') == []
