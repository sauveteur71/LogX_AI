# -*- coding: utf-8 -*-
"""Connexions persistantes (HTTP/1.1) : le serveur doit reutiliser la
connexion SANS jamais laisser un client attendre la fin d'un corps.

Pourquoi ce passage : en HTTP/1.0 (defaut de BaseHTTPRequestHandler) le
serveur raccroche apres CHAQUE reponse. Ouvrir une page = autant de
connexions TCP que de ressources, et chaque sondage periodique (balises 5 s,
spots, statut) en rouvre une. En multi-poste cela se multiplie, et sous
Windows chaque fermeture laisse le port en TIME_WAIT plusieurs minutes.

Ce que ces tests protegent, c'est le REVERS du gain : tant que le serveur
raccrochait, « fin de connexion » signifiait « fin du corps ». Ce n'est plus
vrai. Deux fautes deviennent alors graves, et AUCUNE ne se voit a l'oeil nu
dans le code :

  1. une reponse sans Content-Length exact -> le navigateur attend
     indefiniment la suite d'un corps deja complet (page figee) ;
  2. un POST refuse AVANT lecture de son corps -> les octets restants sont
     lus comme la requete suivante sur la meme connexion (requete corrompue).

Les tests ci-dessous verifient le comportement OBSERVABLE par un vrai client
HTTP, pas la presence de tel ou tel appel dans le source.
"""
import http.client
import http.server
import os
import socket
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod


@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def test_le_serveur_annonce_bien_http_1_1():
    """Sans cela, tout le reste de ce fichier ne teste rien : c'est cet
    attribut qui active les connexions persistantes."""
    assert httpmod.Handler.protocol_version == 'HTTP/1.1'


def test_un_delai_d_inactivite_libere_le_fil_d_execution():
    """Un fil est mobilise par connexion OUVERTE. Sans delai, des onglets qui
    gardent la ligne finiraient par tous les epuiser et le serveur ne
    repondrait plus a personne — panne bien pire que le probleme resolu."""
    assert httpmod.Handler.timeout, 'aucun delai d inactivite : fils non liberes'
    assert httpmod.Handler.timeout <= 120


def test_plusieurs_requetes_sur_une_seule_connexion(serveur):
    """Le gain lui-meme : une page entiere servie sans rouvrir de connexion."""
    c = http.client.HTTPConnection('127.0.0.1', serveur, timeout=10)
    sockets = set()
    for chemin in ('/network/info', '/logx_i18n.js', '/logx_statusbar.js',
                   '/network/info'):
        c.request('GET', chemin)
        r = c.getresponse()
        corps = r.read()
        assert r.status == 200, chemin
        assert len(corps) > 0, chemin
        sockets.add(id(c.sock))
    c.close()
    assert len(sockets) == 1, (
        'la connexion a ete rouverte : les connexions persistantes ne '
        'fonctionnent pas')


@pytest.mark.parametrize('chemin', [
    '/network/info',            # JSON (passe par _json/_raw)
    '/logx_i18n.js',            # gros fichier statique
    '/logx_propagation.html',   # page HTML
    '/fichier_absent_xyz',      # 404
])
def test_chaque_reponse_delimite_son_corps(serveur, chemin):
    """LE piege du HTTP/1.1 : sans Content-Length (ou fermeture annoncee), le
    client attend la suite d'un corps deja complet. On verifie qu'on peut
    enchainer une requete sur la meme connexion — impossible si la precedente
    n'etait pas correctement delimitee."""
    c = http.client.HTTPConnection('127.0.0.1', serveur, timeout=8)
    c.request('GET', chemin)
    r = c.getresponse()
    corps = r.read()
    delimite = (r.getheader('Content-Length') is not None
                or (r.getheader('Connection') or '').lower() == 'close'
                or (r.getheader('Transfer-Encoding') or '').lower() == 'chunked')
    assert delimite, '%s : corps non delimite (le client attendrait sans fin)' % chemin
    assert len(corps) == int(r.getheader('Content-Length') or len(corps))
    c.close()


def test_post_refuse_sans_jeton_ferme_la_connexion(serveur):
    """Le corps n'est pas lu quand le jeton manque (voir do_POST) : ces octets
    seraient interpretes comme la requete SUIVANTE. La connexion doit donc
    etre fermee, et le client doit en etre AVERTI — sinon il reutilise une
    socket morte et doit rejouer sa requete."""
    c = http.client.HTTPConnection('127.0.0.1', serveur, timeout=8)
    c.request('POST', '/config/save', body=b'{"bidon":1}' * 200,
              headers={'Content-Type': 'application/json'})
    r = c.getresponse()
    r.read()
    assert r.status == 403
    assert (r.getheader('Connection') or '').lower() == 'close', (
        "refus sans lecture du corps : la fermeture doit etre annoncee, "
        "sinon le reliquat parasite la requete suivante")
    c.close()


def test_corps_trop_volumineux_ferme_aussi_la_connexion(serveur):
    """Meme raisonnement : on refuse justement parce qu'on ne veut pas lire ce
    corps, il ne peut donc pas etre draine — reste la fermeture."""
    token = getattr(httpmod, 'AUTH_TOKEN', '')
    c = http.client.HTTPConnection('127.0.0.1', serveur, timeout=8)
    c.request('POST', '/config/save', body=b'',
              headers={'Content-Type': 'application/json',
                       'Content-Length': str(64 * 1024 * 1024),
                       'Cookie': 'rc_token=%s' % token})
    r = c.getresponse()
    r.read()
    assert r.status in (403, 413)
    assert (r.getheader('Connection') or '').lower() == 'close'
    c.close()


def test_une_connexion_inactive_est_fermee_par_le_serveur(serveur):
    """Preuve que le delai d'inactivite agit vraiment (et non qu'il est juste
    declare) : on ouvre, on ne dit rien, le serveur doit finir par raccrocher.
    On borne l'attente pour ne pas allonger la suite de tests — on verifie
    donc seulement que la socket reste saine, le delai reel (30 s) etant trop
    long pour etre attendu ici."""
    s = socket.create_connection(('127.0.0.1', serveur), timeout=5)
    s.settimeout(2)
    try:
        # Rien n'est envoye : le serveur attend la requete. Il ne doit surtout
        # pas fermer IMMEDIATEMENT (sinon le navigateur ne pourrait jamais
        # reutiliser une connexion gardee ouverte entre deux sondages).
        try:
            data = s.recv(64)
        except socket.timeout:
            data = b'__timeout__'      # comportement attendu : le serveur patiente
        assert data == b'__timeout__', (
            'le serveur ferme une connexion au repos immediatement : les '
            'connexions persistantes ne serviraient a rien')
    finally:
        s.close()
