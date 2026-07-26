# -*- coding: utf-8 -*-
"""do_POST : un corps dont la longueur n'est pas DETERMINABLE ne doit jamais
laisser la connexion persistante desynchronisee.

Pourquoi ce fichier : depuis le passage en HTTP/1.1, la connexion sert
plusieurs requetes a la suite. Le corps d'un POST doit donc etre soit
entierement lu, soit suivi d'une fermeture — sinon ses octets sont lus comme
la requete SUIVANTE.

Le calcul de la longueur retombait sur 0 des qu'il echouait :

  * « Content-Length: abc » (en-tete illisible),
  * plusieurs Content-Length contradictoires,
  * « Transfer-Encoding: chunked » (aucun Content-Length, et
    BaseHTTPRequestHandler ne sait pas decoder le chunked).

Or read(0) ne consomme RIEN et la connexion restait ouverte : mesure avant
correction, le corps du POST etait recolle a la ligne de requete du GET
suivant (« 501 Unsupported method ('{"theme":"day"}GET') ») et ce GET ne
recevait jamais sa reponse.

Symetriquement, un VRAI « Content-Length: 0 » est parfaitement determine : il
ne doit surtout pas fermer la connexion, sinon on paierait a chaque POST sans
corps le cout qu'on cherchait justement a supprimer.

Comme dans test_http_keepalive.py, on mesure ce qu'un vrai client observe sur
la socket, pas la presence de tel appel dans le source.
"""
import http.client
import http.server
import os
import re
import socket
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def _cookie():
    return b'Cookie: rc_token=' + getattr(httpmod, 'AUTH_TOKEN', '').encode() + b'\r\n'


def _dialogue(port, octets, suite=None, attente=1.2):
    """Envoie des octets bruts (requete volontairement malformee, impossible a
    fabriquer avec http.client), lit tout ce qui revient, et rend le tampon.
    ConnectionReset est tolere : sous Windows, une fermeture avec des octets
    non lus se solde par un RST — c'est un resultat, pas une erreur de test."""
    s = socket.create_connection(('127.0.0.1', port), timeout=5)
    s.settimeout(attente)
    buf = b''
    try:
        s.sendall(octets)
        if suite is not None:
            time.sleep(0.3)
            try:
                s.sendall(suite)
            except OSError:
                pass          # deja ferme par le serveur : issue acceptable
        while True:
            d = s.recv(65536)
            if not d:
                break
            buf += d
    except (socket.timeout, OSError):
        pass
    finally:
        s.close()
    return buf


def _statuts(buf):
    return re.findall(rb'HTTP/1\.\d (\d\d\d)', buf)


# ── Le defaut lui-meme : desynchronisation de la connexion ──────────────────

def test_content_length_illisible_ne_recolle_pas_le_corps_a_la_requete_suivante(serveur):
    """Scenario mesure du defaut : le corps non lu devenait le debut de la
    requete suivante. Le GET qui suit ne doit JAMAIS etre servi de travers."""
    buf = _dialogue(
        serveur,
        b'POST /data/spots HTTP/1.1\r\nHost: x\r\n' + _cookie() +
        b'Content-Type: application/json\r\nContent-Length: abc\r\n\r\n[]',
        suite=b'GET /network/info HTTP/1.1\r\nHost: x\r\n\r\n')
    assert b'Unsupported method' not in buf, (
        "le corps du POST a ete lu comme la ligne de requete suivante : la "
        "connexion persistante est desynchronisee")
    assert len(_statuts(buf)) <= 1, (
        "une 2e reponse a ete produite a partir des octets du corps : %r" % buf[:400])


def test_transfer_encoding_chunked_ne_laisse_pas_le_corps_dans_le_tampon(serveur):
    """Aucun Content-Length ici, et le chunked n'est pas decode : la longueur
    est tout aussi indeterminable. Le corps chunke ne doit pas etre interprete
    comme la requete suivante."""
    buf = _dialogue(
        serveur,
        b'POST /data/spots HTTP/1.1\r\nHost: x\r\n' + _cookie() +
        b'Content-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n'
        b'2\r\n[]\r\n0\r\n\r\n',
        suite=b'GET /network/info HTTP/1.1\r\nHost: x\r\n\r\n')
    assert b'Bad request syntax' not in buf, (
        "les lignes du corps chunke ont ete parsees comme des requetes")
    assert len(_statuts(buf)) <= 1, (
        "plus d'une reponse pour une seule requete : %r" % buf[:400])


# ── Le refus doit etre ANNONCE (sinon le client rejoue dans une socket morte)

@pytest.mark.parametrize('entetes,attendu', [
    (b'Content-Length: abc\r\n', b'400'),                     # illisible
    (b'Content-Length: \r\n', b'400'),                        # vide
    (b'Content-Length: 12\r\nContent-Length: 40\r\n', b'400'),  # contradictoires
    (b'Transfer-Encoding: chunked\r\n', b'411'),              # longueur non annoncee
])
def test_longueur_indeterminable_refusee_et_fermeture_annoncee(serveur, entetes, attendu):
    """Aucun corps n'est envoye ici : la reponse revient donc entiere, sans
    RST possible. On verifie le refus ET l'en-tete Connection: close — sans
    lui le client croit la connexion reutilisable, envoie sa requete suivante
    dans une socket condamnee et doit la rejouer."""
    buf = _dialogue(
        serveur,
        b'POST /data/spots HTTP/1.1\r\nHost: x\r\n' + _cookie() +
        b'Content-Type: application/json\r\n' + entetes + b'\r\n')
    assert _statuts(buf) == [attendu], 'reponse inattendue : %r' % buf[:400]
    assert b'Connection: close' in buf, (
        "refus sans lecture du corps : la fermeture doit etre annoncee")


# ── Le revers : ne pas fermer ce qui est parfaitement determine ─────────────

def test_un_vrai_content_length_zero_garde_la_connexion(serveur):
    """Garde-fou anti-sur-correction : « Content-Length: 0 » est une longueur
    VALIDE (POST sans corps). Le confondre avec un echec d'analyse ferait
    rouvrir une connexion a chaque appel de ce type."""
    c = http.client.HTTPConnection('127.0.0.1', serveur, timeout=8)
    c.request('POST', '/data/spots', body=b'',
              headers={'Content-Type': 'application/json',
                       'Content-Length': '0',
                       'Cookie': 'rc_token=%s' % getattr(httpmod, 'AUTH_TOKEN', '')})
    r = c.getresponse()
    r.read()
    premiere = id(c.sock)
    assert (r.getheader('Connection') or '').lower() != 'close', (
        "une longueur nulle mais valide ne doit pas fermer la connexion")
    c.request('GET', '/network/info')
    r2 = c.getresponse()
    r2.read()
    assert r2.status == 200
    assert id(c.sock) == premiere, 'la connexion a ete rouverte'
    c.close()


def test_un_post_normal_reste_servi_et_la_connexion_reutilisee(serveur):
    """Le chemin de CHAQUE requete de CHAQUE poste : rien de tout cela ne doit
    gener un POST correctement forme."""
    c = http.client.HTTPConnection('127.0.0.1', serveur, timeout=8)
    c.request('POST', '/data/spots', body=b'[]',
              headers={'Content-Type': 'application/json',
                       'Cookie': 'rc_token=%s' % getattr(httpmod, 'AUTH_TOKEN', '')})
    r = c.getresponse()
    r.read()
    assert r.status == 200
    premiere = id(c.sock)
    c.request('GET', '/network/info')
    r2 = c.getresponse()
    r2.read()
    assert r2.status == 200
    assert id(c.sock) == premiere, 'la connexion a ete rouverte'
    c.close()
