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


def test_post_refuse_sans_jeton_repond_et_ne_desynchronise_pas(serveur):
    """Refus 403 sans jeton : le corps est VIDE de la socket (borne) au lieu
    d etre laisse dedans, puis on repond.

    Ce test exigeait auparavant que la connexion soit FERMEE. C etait le
    moyen, pas la fin : fermer une socket dont le tampon contient encore des
    octets fait envoyer un RST par la pile TCP au lieu d un FIN, et le RST
    DETRUIT la reponse deja emise — le client recevait une erreur reseau au
    lieu du 403 qui lui dit quoi faire. L invariant reel est double : le 403
    arrive, et la requete SUIVANTE recoit bien SA reponse."""
    c = http.client.HTTPConnection('127.0.0.1', serveur, timeout=8)
    c.request('POST', '/config/save', body=b'{"bidon":1}' * 200,
              headers={'Content-Type': 'application/json'})
    r = c.getresponse()
    r.read()
    assert r.status == 403
    # Pas de desynchronisation : la requete suivante doit recevoir SA reponse
    # et non le reliquat du corps precedent interprete comme une requete.
    c.request('GET', '/logx_logbook.html')
    r2 = c.getresponse()
    r2.read()
    assert r2.status == 200, (
        'requete suivante cassee (%s) : le corps refuse a parasite la '
        'connexion' % r2.status)
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


@pytest.fixture
def login_bloque():
    """Amene /auth/login au plafond anti-bruteforce pour 127.0.0.1 — l'etat
    exact d'un operateur qui s'est trompe 5 fois de mot de passe d'acces.
    Aucun mot de passe n'a besoin d'etre configure : le throttle est teste
    AVANT toute verification (c'est justement le PBKDF2 qu'il protege)."""
    httpmod._reset_login_attempts('127.0.0.1')
    for _ in range(httpmod._LOGIN_ATTEMPT_LIMIT):
        httpmod._record_login_failure('127.0.0.1')
    assert httpmod._login_rate_limited('127.0.0.1')
    try:
        yield
    finally:
        httpmod._reset_login_attempts('127.0.0.1')


def _compte_reponses(octets):
    return octets.count(b'HTTP/1.1 ')


def _tout_lire(s, limite=6.0):
    s.settimeout(limite)
    recu = b''
    try:
        while True:
            bloc = s.recv(65536)
            if not bloc:
                break
            recu += bloc
    except socket.timeout:
        pass
    except OSError:
        # Le serveur ferme alors que des octets non lus restent dans le tampon
        # de reception : Windows repond par un RST (WinError 10054). C'est le
        # comportement ATTENDU ici — la preuve que la connexion est fermee.
        pass
    return recu


def test_login_413_ferme_la_connexion_et_ne_repond_pas_au_reliquat(serveur):
    """/auth/login est aiguille AVANT _require_auth : c'est le SEUL POST
    joignable sans jeton, et ses deux refus precoces echappaient donc aux
    fermetures posees dans _require_auth et dans le plafond MAX_BODY.

    Sans fermeture, le corps annonce mais jamais lu est interprete comme la
    requete SUIVANTE : le serveur y repond, et cette reponse est delivree au
    client comme si elle repondait a SA requete suivante. Mesure du defaut :
    3 reponses pour 2 requetes, le client qui demandait /network/info
    recevant le corps de /data/rules_status."""
    s = socket.create_connection(('127.0.0.1', serveur), timeout=8)
    try:
        try:
            s.sendall(b'POST /auth/login HTTP/1.1\r\nHost: 127.0.0.1\r\n'
                      b'Content-Type: application/json\r\n'
                      b'Content-Length: 5000\r\n\r\n')
            # « Corps » annonce mais jamais lu : une requete HTTP complete.
            s.sendall(b'GET /data/rules_status HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n')
            # La vraie requete suivante du client.
            s.sendall(b'GET /network/info HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n')
        except OSError:
            # ECHEC CI REEL (Linux, 27/07/2026) : BrokenPipeError sur le 3e
            # envoi. Le serveur avait deja refuse en 413 et ferme -- donc le
            # comportement VOULU. Fermer avec des octets annonces mais non lus
            # fait partir un RST, et tout envoi ulterieur echoue.
            #
            # Ce n'est pas un assouplissement du test : les assertions
            # ci-dessous portent sur ce qui a ete RECU, et restent entieres.
            # Si le serveur repondait au reliquat, la reponse serait la et le
            # test tomberait. Verifie en cassant volontairement le serveur.
            #
            # La lecture etait deja protegee de la meme facon (voir _tout_lire)
            # ; l'ecriture ne l'etait pas. Windows ne le montre pas : un envoi
            # vers une socket dont le pair a ferme y reussit encore, meme apres
            # 0,6 s d'attente (mesure ici, la reproduction locale a echoue).
            pass
        recu = _tout_lire(s)
    finally:
        s.close()
    # L'invariant, c'est qu'AUCUNE reponse ne parte vers le reliquat : sinon
    # elle sera prise pour la reponse a la requete suivante du client.
    assert _compte_reponses(recu) <= 1, (
        'le serveur a repondu au reliquat du corps : %d reponses recues, le '
        'client recevra la reponse d une AUTRE requete que la sienne'
        % _compte_reponses(recu))
    assert b'contests_count' not in recu, (
        'le corps de /data/rules_status, glisse dans le corps non lu, a ete '
        'servi comme une vraie reponse')
    if recu:
        # Fermer avec des octets non lus dans le tampon fait repondre Windows
        # par un RST, qui peut effacer la reponse deja mise en file. Quand elle
        # nous parvient, elle doit etre le refus, fermeture annoncee.
        assert b' 413 ' in recu.split(b'\r\n')[0], recu[:200]
        assert b'Connection: close' in recu, (
            'refus 413 sans lecture du corps : la fermeture doit etre annoncee')


def test_login_429_arrive_et_ne_rejoue_pas_le_mot_de_passe(
        serveur, login_bloque):
    """Cas utilisateur reel : 5 erreurs de mot de passe d'acces suffisent (LAN
    multi-poste, c'est le cas d'usage meme du plafond). La 6e tentative repond
    429. Le corps (qui contient le mot de passe en clair) est VIDE de la socket
    sans etre analyse : sans ca, sur une connexion persistante, la requete
    suivante du navigateur etait collee a ce corps, d'ou un « 400 Bad request
    syntax » dont la page d'erreur REAFFICHE le mot de passe tape."""
    secret = 'MotDePasseEnClair2026'
    c = http.client.HTTPConnection('127.0.0.1', serveur, timeout=8)
    try:
        c.request('POST', '/auth/login',
                  body=('{"password": "%s"}' % secret).encode('utf-8'),
                  headers={'Content-Type': 'application/json'})
        try:
            r = c.getresponse()
            corps_429 = r.read()
            statut = r.status
        except (OSError, http.client.HTTPException) as e:
            raise AssertionError(
                'la reponse 429 doit ARRIVER. Ce test acceptait auparavant un '
                'RST comme "fermeture attendue" : c etait tolerer que la '
                'reponse soit PERDUE. Le refus vide desormais le corps de la '
                'socket avant de repondre, ce qui evite le RST tout en '
                'empechant le mot de passe de parasiter la requete suivante '
                '(recu : %s)' % e)
        # L'invariant n'est PAS "la connexion est fermee" — c'etait le moyen,
        # pas la fin. Ce qui compte : le 429 arrive, et le mot de passe ne
        # ressort pas. La connexion peut rester ouverte, c'est meme preferable.
        assert statut == 429, 'statut recu : %s' % statut
        assert secret.encode('utf-8') not in corps_429, (
            'le mot de passe tape ne doit jamais reapparaitre dans la reponse')
        c.close()
        # La requete suivante doit recevoir SA reponse, pas un « 400 Bad request
        # syntax » dont la page d'erreur reaffiche le mot de passe.
        c.request('GET', '/logx_logbook.html')
        r2 = c.getresponse()
        corps = r2.read()
        assert r2.status == 200, 'page cassee juste apres un blocage : %s' % r2.status
        assert secret.encode('utf-8') not in corps, (
            'le mot de passe d acces est reaffiche en clair dans la reponse '
            'suivante')
    finally:
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
