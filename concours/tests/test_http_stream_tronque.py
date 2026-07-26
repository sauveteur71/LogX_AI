# -*- coding: utf-8 -*-
"""Flux tronque en HTTP/1.1 : quand le corps est plus COURT que le
Content-Length deja annonce, la connexion doit etre fermee tout de suite.

Rappel du piege (voir test_http_keepalive.py) : depuis le passage en HTTP/1.1,
« fin de connexion » ne veut plus dire « fin du corps ». Les deux fonctions de
relais de mise a jour annoncent une taille AVANT d'envoyer le corps :

  - _stream_asset_relay recopie le Content-Length de l'amont GitHub ;
  - _stream_verified_file annonce os.path.getsize() du fichier deja verifie.

Dans les deux cas la taille peut se reveler FAUSSE en cours d'envoi : uplink de
la passerelle coupe pendant le relais, source qui tronque, ou executable
remplace pendant qu'on le sert. La boucle de copie sort alors normalement (plus
rien a lire) et, sans precaution, la connexion reste persistante avec un corps
plus court que promis : le poste appelant attend la suite jusqu'au delai
d'inactivite de 30 s au lieu de constater l'echec et de basculer aussitot sur
le chemin de secours pair-a-pair. En HTTP/1.0 le serveur raccrochait, l'echec
etait immediat — c'est cette immediatete que ces tests reverifient.

Comme toujours ici, on mesure le comportement OBSERVABLE par un vrai client
socket (le serveur raccroche-t-il ?), pas la presence d'un appel dans le code.
"""
import http.client
import http.server
import os
import socket
import sys
import threading
from urllib.parse import parse_qs, quote, urlparse

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod

ATTENTE = 5.0          # bien au-dela d'un echange local, bien en deca des 30 s


class _FauxAmont(threading.Thread):
    """Amont HTTP minimal en socket brute. Indispensable : aucun serveur
    correct n'annonce une taille puis en livre moins — il faut donc mentir
    volontairement pour rejouer la coupure d'uplink."""

    def __init__(self):
        super().__init__(daemon=True)
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(('127.0.0.1', 0))
        self.srv.listen(8)
        self.port = self.srv.getsockname()[1]

    def url(self, chemin):
        return 'http://127.0.0.1:%d%s' % (self.port, chemin)

    def run(self):
        while True:
            try:
                conn, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._sert, args=(conn,), daemon=True).start()

    def _sert(self, conn):
        try:
            conn.settimeout(ATTENTE)
            requete = b''
            while b'\r\n\r\n' not in requete:
                bloc = conn.recv(4096)
                if not bloc:
                    return
                requete += bloc
            chemin = requete.split(b' ')[1].decode('latin-1')
            if chemin.startswith('/court'):
                # Annonce 1 Mo, livre 4 Ko, raccroche : la coupure d'uplink.
                conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 1000000\r\n\r\n'
                             + b'A' * 4096)
            elif chemin.startswith('/complet'):
                conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 4096\r\n\r\n'
                             + b'B' * 4096)
            else:
                conn.sendall(b'HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n')
        except OSError:
            pass
        finally:
            conn.close()

    def arrete(self):
        try:
            self.srv.close()
        except OSError:
            pass


class _HandlerTest(httpmod.Handler):
    """Expose les DEUX vraies methodes de flux sur des routes de test, sans
    toucher a logx_http.py : c'est bien le code de production qui repond."""

    _a_tronquer = None

    def do_GET(self):
        cible = urlparse(self.path)
        params = parse_qs(cible.query)
        if cible.path == '/test/relais':
            self._stream_asset_relay(params['url'][0])
            return
        if cible.path == '/test/fichier':
            self._stream_verified_file(params['p'][0])
            return
        if cible.path == '/test/fichier_retreci':
            # Le fichier retrecira entre l'annonce de sa taille et sa lecture
            # (cas reel : l'executable est remplace pendant qu'on le sert).
            self._a_tronquer = params['p'][0]
            self._stream_verified_file(self._a_tronquer)
            return
        return httpmod.Handler.do_GET(self)

    def end_headers(self):
        httpmod.Handler.end_headers(self)
        if self._a_tronquer:
            os.truncate(self._a_tronquer, 4096)
            self._a_tronquer = None

    def log_message(self, *a):
        pass


@pytest.fixture
def amont():
    a = _FauxAmont()
    a.start()
    try:
        yield a
    finally:
        a.arrete()


@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _HandlerTest)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _requete_brute(port, cible):
    """Envoie UNE requete et lit jusqu'a la fermeture par le serveur.
    Renvoie (entetes, corps, ferme) ; ferme=False = le serveur garde la
    connexion ouverte (le client attendrait alors les 30 s du delai)."""
    s = socket.create_connection(('127.0.0.1', port), timeout=ATTENTE)
    s.settimeout(ATTENTE)
    s.sendall(('GET %s HTTP/1.1\r\nHost: 127.0.0.1\r\n'
               'Accept-Encoding: identity\r\n\r\n' % cible).encode())
    donnees, ferme = b'', False
    try:
        while True:
            bloc = s.recv(65536)
            if not bloc:
                ferme = True
                break
            donnees += bloc
    except socket.timeout:
        ferme = False
    finally:
        s.close()
    entetes, _, corps = donnees.partition(b'\r\n\r\n')
    return entetes.decode('latin-1'), corps, ferme


def test_relais_amont_plus_court_que_sa_taille_annoncee_ferme_la_connexion(
        amont, serveur):
    """LE defaut : l'amont annonce 1 Mo et en livre 4 Ko. On a deja annonce
    1 Mo au poste appelant — il faut donc raccrocher, sinon il patiente 30 s
    avant de pouvoir tenter le secours pair-a-pair."""
    cible = '/test/relais?url=' + quote(amont.url('/court'), safe='')
    entetes, corps, ferme = _requete_brute(serveur, cible)
    assert '200 OK' in entetes
    assert 'Content-Length: 1000000' in entetes, entetes
    assert len(corps) == 4096, 'lecture de l amont inattendue'
    assert ferme, (
        'corps tronque mais connexion gardee ouverte : le poste appelant '
        'attend la suite jusqu au delai d inactivite (30 s) au lieu de voir '
        'l echec tout de suite')


def test_relais_complet_garde_bien_la_connexion(amont, serveur):
    """Contre-epreuve indispensable : le relais NORMAL ne doit pas raccrocher,
    sinon on aurait « corrige » en perdant les connexions persistantes."""
    c = http.client.HTTPConnection('127.0.0.1', serveur, timeout=ATTENTE)
    c.request('GET', '/test/relais?url=' + quote(amont.url('/complet'), safe=''))
    r = c.getresponse()
    assert r.status == 200
    assert len(r.read()) == 4096
    premiere = id(c.sock)
    c.request('GET', '/network/info')
    r2 = c.getresponse()
    r2.read()
    assert r2.status == 200
    assert id(c.sock) == premiere, (
        'la connexion a ete rouverte apres un relais pourtant complet')
    c.close()


def test_fichier_verifie_qui_retrecit_ferme_la_connexion(serveur, tmp_path):
    """Meme faute, autre fonction : la taille est prise avant la lecture, le
    fichier peut avoir maigri entre-temps (executable remplace en plein
    service)."""
    f = tmp_path / 'maj.bin'
    f.write_bytes(b'C' * 300000)
    cible = '/test/fichier_retreci?p=' + quote(str(f), safe='')
    entetes, corps, ferme = _requete_brute(serveur, cible)
    assert 'Content-Length: 300000' in entetes, entetes
    assert len(corps) < 300000, 'le fichier n a pas retreci : test inoperant'
    assert ferme, (
        'fichier plus court que la taille annoncee mais connexion gardee '
        'ouverte : le pair attend jusqu au delai d inactivite')


def test_fichier_verifie_intact_garde_la_connexion(serveur, tmp_path):
    """Contre-epreuve du service pair-a-pair normal."""
    f = tmp_path / 'maj_ok.bin'
    f.write_bytes(b'D' * 300000)
    c = http.client.HTTPConnection('127.0.0.1', serveur, timeout=ATTENTE)
    c.request('GET', '/test/fichier?p=' + quote(str(f), safe=''))
    r = c.getresponse()
    assert r.status == 200
    assert len(r.read()) == 300000
    premiere = id(c.sock)
    c.request('GET', '/network/info')
    r2 = c.getresponse()
    r2.read()
    assert r2.status == 200
    assert id(c.sock) == premiere, (
        'la connexion a ete rouverte apres un envoi pourtant complet')
    c.close()
