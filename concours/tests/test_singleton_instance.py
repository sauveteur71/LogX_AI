# -*- coding: utf-8 -*-
"""Tests de logx_singleton.py — une seule instance de serveur par port.

Pourquoi ces tests existent : le bug d'origine ne se voyait PAS. Relancer
LogX AI alors qu'une instance tournait affichait un démarrage normal, sans
erreur, mais c'était l'ancien processus qui répondait (SO_REUSEADDR laisse
voler un port en écoute sous Windows) — et deux serveurs écrivaient dans les
mêmes fichiers de log sans exclusion mutuelle. Une régression ici serait donc
de nouveau silencieuse : d'où un filet automatique.

Les tests utilisent des serveurs éphémères sur port 0 (le système attribue un
port libre) : jamais de port fixe, donc jamais de collision avec le serveur
réel de l'utilisateur ni entre exécutions parallèles.
"""
import http.server
import json
import os
import socket
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_singleton as S

CONCOURS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ─── OUTILLAGE ───────────────────────────────────────────────────────────────

def _free_port():
    """Un port libre au moment de l'appel (attribué puis relâché par l'OS)."""
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _FakeHandler(http.server.BaseHTTPRequestHandler):
    """Répond PAYLOAD (défini par sous-classe) sur n'importe quelle URL."""
    payload = b'{}'
    ctype = 'application/json'

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', self.ctype)
        self.send_header('Content-Length', str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, *a):
        pass


@pytest.fixture
def serveur_ephemere():
    """Démarre un serveur HTTP sur un port libre et retourne ce port."""
    serveurs = []

    def _start(payload, ctype='application/json', host='127.0.0.1'):
        handler = type('H', (_FakeHandler,),
                       {'payload': payload, 'ctype': ctype})
        srv = http.server.ThreadingHTTPServer((host, 0), handler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        serveurs.append((srv, t))
        return srv.server_address[1]

    yield _start
    # shutdown + server_close + JOIN : sans le join, le thread serve_forever
    # du test N vit encore pendant le test N+1 — la famille de fuites qui
    # rendait la suite non reproductible (diagnostic du 31/07/2026).
    for srv, t in serveurs:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


@pytest.fixture
def serveur_dual_stack():
    """Tiers écoutant sur [::] en « dual-stack » — donc joignable en IPv4 sans
    tenir aucune adresse IPv4 en propre. C'est le cas de `python -m
    http.server`, de tout serveur Node (`server.listen(8080)`) et de tout
    serveur Go (`:8080`) : banal sur un port comme 8080, et c'est exactement
    la configuration qui empêchait LogX AI de démarrer."""
    serveurs = []

    class _DualStack(http.server.ThreadingHTTPServer):
        address_family = socket.AF_INET6
        allow_reuse_address = False

        def server_bind(self):
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            super().server_bind()

    def _start(payload=b'{"service":"autre"}'):
        handler = type('H', (_FakeHandler,), {'payload': payload})
        try:
            srv = _DualStack(('::', 0), handler)
        except OSError as e:                     # poste sans IPv6
            pytest.skip('pas de socket IPv6 dual-stack ici : %s' % e)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        serveurs.append((srv, t))
        port = srv.server_address[1]
        if not S._port_accepts('127.0.0.1', port, 1.0):
            pytest.skip('IPv6 dual-stack non joignable en IPv4 sur ce poste')
        return port

    yield _start
    for srv, t in serveurs:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


@pytest.fixture
def ecouteur_meme_adresse():
    """Socket en écoute sur EXACTEMENT l'adresse que le vrai serveur demande
    (S.BIND_HOST) — c'est le cas « une autre instance de LogX AI tient déjà le
    port ». Un écouteur sur 127.0.0.1 ne conviendrait pas : Windows n'y voit
    aucun conflit avec un bind 0.0.0.0 (mesuré), le test ne prouverait rien."""
    lst = socket.socket()
    lst.bind((S.BIND_HOST, 0))
    lst.listen(5)
    yield lst.getsockname()[1]
    lst.close()


@pytest.fixture
def serveur_brut():
    """Serveur TCP piloté octet par octet, pour les comportements que
    http.server ne sait pas produire : réponse au goutte à goutte, redirection.
    Retourne (port, chemins_demandes) — la liste des chemins se remplit au fil
    des requêtes, c'est elle qui prouve ce que la sonde est allée chercher.

    `servir(chemin, conn)` écrit la réponse brute. Une connexion qui n'envoie
    rien est ignorée : c'est celle de _port_accepts, qui se contente d'ouvrir
    et de refermer — la compter fausserait tout raisonnement sur l'ordre des
    requêtes (piège rencontré en écrivant ces tests)."""
    ecouteurs = []

    def _start(servir):
        lst = socket.socket()
        lst.bind(('127.0.0.1', 0))
        lst.listen(8)
        ecouteurs.append(lst)
        chemins = []

        def _client(c):
            try:
                req = c.recv(8192).decode('latin-1')
                if not req.strip():
                    return
                chemins.append(req.split(' ')[1])
                servir(chemins[-1], c)
            except OSError:
                pass
            finally:
                try:
                    c.close()
                except OSError:
                    pass

        def _boucle():
            while True:
                try:
                    c, _ = lst.accept()
                except OSError:
                    return
                threading.Thread(target=_client, args=(c,), daemon=True).start()

        threading.Thread(target=_boucle, daemon=True).start()
        return lst.getsockname()[1], chemins

    yield _start
    for lst in ecouteurs:
        lst.close()


def _http_200(corps):
    return (b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
            b'Content-Length: %d\r\n\r\n' % len(corps)) + corps


def _reponse_logx(version='9.9-test'):
    return json.dumps({
        'local_ip': '192.168.1.10', 'port': 1234,
        'url_logbook': 'http://192.168.1.10:1234/logx_logbook.html',
        'url_terrain': 'http://192.168.1.10:1234/logx_mobile.html',
        'peers': 0, 'app_version': version,
    }).encode()


# ─── B) FILET DE SÉCURITÉ AU BIND ────────────────────────────────────────────

def test_allow_reuse_address_desactive_sous_windows_seulement():
    """LE correctif du bug. Sous Windows, SO_REUSEADDR autorise un second
    processus à se lier à un port DÉJÀ ÉCOUTÉ : le bind réussit en silence et
    l'ancien serveur continue de répondre. Ailleurs, l'option ne sert qu'à
    reprendre un port en TIME_WAIT et la retirer casserait le redémarrage
    rapide — d'où un réglage qui DOIT dépendre de la plateforme."""
    attendu = not sys.platform.startswith('win')
    assert S.LogXHTTPServer.allow_reuse_address == attendu
    # Et surtout : pas la valeur héritée de http.server (1 = SO_REUSEADDR)
    if sys.platform.startswith('win'):
        assert not S.LogXHTTPServer.allow_reuse_address
        assert http.server.HTTPServer.allow_reuse_address  # l'héritage dangereux


def test_bind_refuse_un_port_deja_ecoute(ecouteur_meme_adresse):
    """LE test du bug : un serveur écoute déjà, LogXHTTPServer doit refuser le
    port au lieu de s'y greffer en silence. Avec le SO_REUSEADDR hérité de
    http.server, ce bind RÉUSSISSAIT sous Windows — et c'est l'ancien serveur
    qui continuait de répondre aux requêtes."""
    with pytest.raises(OSError):
        srv = S.LogXHTTPServer((S.BIND_HOST, ecouteur_meme_adresse), _FakeHandler)
        srv.server_close()   # au cas où (le test échoue quand même)


def test_bind_test_reproduit_les_options_du_vrai_serveur(monkeypatch):
    """_bind_test doit poser SO_REUSEADDR si et seulement si le vrai serveur
    le pose. Sous Unix, un test sans SO_REUSEADDR échouerait sur un simple
    TIME_WAIT résiduel et l'application refuserait de démarrer alors que le
    vrai bind, lui, réussirait — panne totale au redémarrage rapide."""
    poses = []
    vraie_socket = socket.socket

    class SocketEspionne(vraie_socket):
        def setsockopt(self, level, optname, value):
            poses.append((level, optname, value))
            return super().setsockopt(level, optname, value)

    monkeypatch.setattr(socket, 'socket', SocketEspionne)
    S._bind_test(_free_port())
    reuse_pose = (socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) in poses
    assert reuse_pose == bool(S.LogXHTTPServer.allow_reuse_address)


def test_bind_test_dit_libre_sur_un_port_libre():
    libre, detail = S._bind_test(_free_port())
    assert libre is True
    assert detail == ''


def test_bind_test_dit_occupe_et_explique(ecouteur_meme_adresse):
    libre, detail = S._bind_test(ecouteur_meme_adresse)
    assert libre is False
    assert detail            # une explication technique, pas une chaîne vide


# ─── A) DÉTECTION AVANT LE BIND ──────────────────────────────────────────────

def test_probe_reconnait_une_instance_logx(serveur_ephemere):
    port = serveur_ephemere(_reponse_logx('1.2.3'))
    r = S.probe(port)
    assert r['state'] == S.LOGX
    assert r['version'] == '1.2.3'


def test_probe_reconnait_une_instance_sans_app_version(serveur_ephemere):
    """Une instance ANCIENNE peut ne pas renvoyer app_version : elle reste une
    instance LogX AI (sinon on afficherait « un autre logiciel occupe le port »
    en plein scénario de mise à jour, le pire moment pour mentir)."""
    vieux = json.dumps({'local_ip': '10.0.0.1', 'port': 8080,
                        'url_logbook': 'http://10.0.0.1:8080/index.html'}).encode()
    r = S.probe(serveur_ephemere(vieux))
    assert r['state'] == S.LOGX
    assert r['version'] is None


def test_probe_distingue_un_logiciel_tiers_json(serveur_ephemere):
    """Un autre logiciel qui répond du JSON ne doit JAMAIS être pris pour
    LogX AI : le message et la conduite à tenir sont totalement différents."""
    r = S.probe(serveur_ephemere(json.dumps({'service': 'autre'}).encode()))
    assert r['state'] == S.OTHER
    assert r['version'] is None
    assert r['detail']


def test_probe_distingue_un_logiciel_tiers_html(serveur_ephemere):
    r = S.probe(serveur_ephemere(b'<html>autre serveur</html>', 'text/html'))
    assert r['state'] == S.OTHER


def test_probe_port_libre():
    r = S.probe(_free_port())
    assert r['state'] == S.FREE
    assert r['version'] is None


def test_probe_detecte_un_serveur_invisible_au_bind(serveur_ephemere):
    """Le bind joker 0.0.0.0 ne voit RIEN d'un tiers lié à 127.0.0.1 (mesuré :
    il réussit). Sans la connexion réelle, la sonde conclurait « libre » et on
    démarrerait un serveur que le navigateur ne trouverait jamais — c'est
    pourquoi _port_accepts doit rester dans la sonde."""
    port = serveur_ephemere(json.dumps({'service': 'autre'}).encode())
    if S.WINDOWS:
        # Windows : le bind joker 0.0.0.0 est aveugle a un tiers lie a
        # 127.0.0.1 — il REUSSIT, d'ou l'interet vital de _port_accepts.
        assert S._bind_test(port)[0] is True
    else:
        # Linux/macOS : une adresse plus specifique bloque le joker, le bind
        # echoue de lui-meme. La sonde par connexion reste utile (elle sert
        # aussi a IDENTIFIER qui repond), mais elle n'est plus le seul filet.
        assert S._bind_test(port)[0] is False
    # Universel, et c'est ce qui compte pour l'utilisateur : un tiers occupe
    # l'adresse que le navigateur utilisera -> on refuse de demarrer.
    assert S.probe(port)['state'] == S.OTHER


def test_probe_laisse_demarrer_derriere_un_ecouteur_dual_stack(serveur_dual_stack):
    """LA régression corrigée ici. Un tiers dual-stack [::] (python -m
    http.server, tout serveur Node ou Go) faisait conclure OTHER, et
    logx_serveur.py s'arrêtait en code 1 : LogX AI devenait IMPOSSIBLE à
    lancer sur ces postes, alors qu'il fonctionnait parfaitement avant.

    Mesuré : notre bind 0.0.0.0 est plus spécifique que le [::] du tiers, donc
    c'est LogX AI qui sert 127.0.0.1 et l'IP du réseau local — soit toutes les
    URL que l'application affiche et ouvre elle-même. Verdict attendu : SHARED
    (on avertit, on démarre), surtout pas OTHER (on refuse)."""
    port = serveur_dual_stack()
    assert S._port_accepts('127.0.0.1', port, 1.0)   # le tiers repond bien
    if S.WINDOWS:
        assert S._bind_test(port)[0] is True         # on POURRAIT se lier...
        assert S.probe(port)['state'] == S.SHARED
    else:
        # Sous Linux/macOS un ecouteur [::] occupe AUSSI l'IPv4 : notre bind
        # echoue, il n'y a donc rien a partager et SHARED n'a pas lieu d'etre.
        # Refuser est alors la seule conduite correcte — demarrer serait
        # impossible de toute facon.
        assert S._bind_test(port)[0] is False
        assert S.probe(port)['state'] == S.OTHER


@pytest.mark.skipif(not S.WINDOWS,
                    reason="SHARED n'existe que sous Windows : ailleurs, un "
                           "ecouteur [::] occupe aussi l'IPv4 et notre bind "
                           'echoue, il n y a donc pas d adresse a partager')
def test_shared_veut_bien_dire_que_c_est_nous_qui_repondrons(serveur_dual_stack):
    """Preuve de bout en bout du verdict SHARED : on démarre VRAIMENT le
    serveur comme le fait logx_serveur.py, puis on resonde. Si le tiers gardait
    l'adresse, la sonde continuerait de voir un inconnu ; elle doit maintenant
    reconnaître LogX AI. Sans ce test, SHARED ne serait qu'une intention."""
    port = serveur_dual_stack()
    assert S.probe(port)['state'] == S.SHARED
    srv = S.LogXHTTPServer((S.BIND_HOST, port),
                           type('H', (_FakeHandler,),
                                {'payload': _reponse_logx('7.7-preuve')}))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = S.probe(port)
        assert r['state'] == S.LOGX, 'le tiers repond encore : SHARED etait faux'
        assert r['version'] == '7.7-preuve'
    finally:
        srv.shutdown()
        srv.server_close()


def test_other_veut_bien_dire_que_le_tiers_garde_l_adresse(serveur_ephemere):
    """Le pendant du test précédent, et la raison de ne PAS transformer tous
    les OTHER en avertissements : un tiers lié nominativement à 127.0.0.1 nous
    prend cette adresse (socket la plus spécifique). Même après notre bind, il
    répond toujours — refuser de démarrer est ici la bonne conduite."""
    port = serveur_ephemere(json.dumps({'service': 'autre'}).encode())
    assert S.probe(port)['state'] == S.OTHER
    if not S.WINDOWS:
        # Sous Linux/macOS la demonstration s'arrete la, et elle est meme plus
        # forte : le tiers lie a 127.0.0.1 nous interdit carrement le bind
        # joker. Tenter de demarrer par-dessus leverait EADDRINUSE — ce que
        # faisait ce test, ecrit avec les seules semantiques Windows en tete.
        assert S._bind_test(port)[0] is False
        return
    srv = S.LogXHTTPServer((S.BIND_HOST, port),
                           type('H', (_FakeHandler,), {'payload': _reponse_logx()}))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert S.probe(port)['state'] == S.OTHER
    finally:
        srv.shutdown()
        srv.server_close()


def test_un_conflit_franc_reste_un_refus(ecouteur_meme_adresse):
    """Garde-fou du nouvel état : SHARED est réservé au cas où notre bind
    réussit. Quand le port est tenu sur 0.0.0.0, le bind échoue et le verdict
    doit rester OTHER — sinon on démarrerait dans le mur."""
    r = S.probe(ecouteur_meme_adresse, http_timeout=0.3)
    assert r['state'] == S.OTHER


def test_probe_bornee_dans_le_temps_si_le_port_ne_repond_pas():
    """Un service qui accepte la connexion mais ne répond jamais ne doit pas
    figer le démarrage : l'utilisateur qui double-clique attendrait sans rien
    comprendre."""
    lst = socket.socket()
    lst.bind(('127.0.0.1', 0))
    lst.listen(5)
    port = lst.getsockname()[1]
    accepted = []
    threading.Thread(target=lambda: accepted.append(lst.accept()),
                     daemon=True).start()
    try:
        t0 = time.perf_counter()
        r = S.probe(port, connect_timeout=0.3, http_timeout=0.5)
        ecoule = time.perf_counter() - t0
        assert r['state'] == S.OTHER
        assert ecoule < 5, 'sonde non bornée : %.1f s' % ecoule
    finally:
        lst.close()


def test_probe_ne_leve_jamais_et_laisse_demarrer(monkeypatch):
    """Défensif : si la sonde casse (pare-feu exotique, pile réseau bizarre),
    elle ne doit pas empêcher un démarrage légitime — le filet au bind reste
    en travers du chemin de toute façon."""
    def _boom(*a, **k):
        raise RuntimeError('pile reseau cassee')
    monkeypatch.setattr(S, '_bind_test', _boom)
    r = S.probe(12345)
    assert r['state'] == S.FREE


def test_probe_ignore_le_proxy_systeme(monkeypatch, serveur_ephemere):
    """Un proxy HTTP configuré sur le poste ne doit pas intercepter la sonde :
    sans ProxyHandler({}), urllib enverrait la requête au proxy et LogX AI ne
    se reconnaîtrait pas lui-même."""
    port = serveur_ephemere(_reponse_logx())
    monkeypatch.setenv('http_proxy', 'http://127.0.0.1:9')   # proxy mort
    monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:9')
    assert S.probe(port)['state'] == S.LOGX


def test_probe_ne_lit_pas_un_flux_sans_fin():
    """Un serveur tiers pourrait répondre un flux infini : la lecture est
    bornée, sinon le démarrage se bloquerait en avalant de la mémoire."""
    class Infini(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            try:
                while True:
                    self.wfile.write(b'x' * 4096)
            except Exception:
                pass

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Infini)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = S.probe(srv.server_address[1], http_timeout=2.0)
        assert r['state'] == S.OTHER
    finally:
        srv.shutdown()
        srv.server_close()


def test_probe_bornee_face_a_un_flux_au_goutte_a_goutte(serveur_brut):
    """LE test du second bug : _MAX_BODY borne les OCTETS, jamais l'ATTENTE.

    Le test ci-dessus ne couvrait que le tiers qui inonde à pleine vitesse —
    les 65 536 octets arrivent instantanément et tout va bien. Un tiers qui
    répond au goutte à goutte ne déclenche AUCUN timeout de socket (chaque
    recv() rend un octet bien avant l'échéance) et la lecture dure jusqu'à ce
    que la limite d'octets soit atteinte. Mesuré avant correction, timeouts par
    défaut : la sonde tournait encore à T+10 s avec 99 octets sur 65 536, soit
    ~1 h 50 projetées, sans qu'une ligne ne s'affiche — et comme _bind_test
    disait « libre », l'utilisateur n'avait même pas de collision à soupçonner.

    Ici : 1 octet toutes les 50 ms, soit ~55 min pour atteindre la limite si
    l'attente n'est pas bornée."""
    def servir(chemin, c):
        c.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
                  b'Content-Length: 65536\r\n\r\n')
        while True:
            c.sendall(b'x')
            time.sleep(0.05)

    port, _ = serveur_brut(servir)
    t0 = time.perf_counter()
    r = S.probe(port, http_budget=0.6)
    ecoule = time.perf_counter() - t0
    assert r['state'] == S.OTHER
    assert ecoule < 3, 'sonde non bornee dans le temps : %.1f s' % ecoule
    # Le détail s'affiche sur la console de LogXAI.exe : il doit rester
    # lisible (ASCII) et dire « delai », pas rapporter un WinError localisé
    # qui accuserait un logiciel tiers de notre propre coupure.
    r['detail'].encode('ascii')
    if S.WINDOWS:
        # Windows : notre bind reussit malgre le tiers, la sonde va donc au
        # bout de l'echange HTTP et c'est bien l'attente de reponse qui est
        # bornee — le detail doit le dire.
        assert 'reponse exploitable' in r['detail']
    else:
        # Linux/macOS : le tiers nous prend l'adresse, le bind echoue AVANT
        # meme l'echange HTTP. Le bornage reste verifie (assertion de duree
        # ci-dessus, la seule qui compte pour l'utilisateur), mais le detail
        # rapporte logiquement le refus de bind. Exiger ici le libelle Windows
        # reviendrait a tester la plateforme, pas le bornage.
        assert 'bind refuse' in r['detail']


def test_probe_ne_suit_pas_les_redirections(serveur_brut):
    """La sonde ne doit interroger QUE PROBE_PATH.

    urllib.request.build_opener() embarque HTTPRedirectHandler par défaut :
    avant correction, la sonde demandait bien /network/info puis /ailleurs
    (mesuré). Trois conséquences, toutes évitées ici :
      * l'identification devient détournable — d'où la réponse redirigée qui
        IMITE la signature LogX AI ci-dessous : si elle était suivie, LogX AI
        se croirait déjà lancé et refuserait de démarrer ;
      * le logiciel qui occupe le port choisit une URL vers laquelle une
        requête part, à chaque démarrage (une adresse externe ferait sortir
        cette requête du poste) ;
      * chaque saut ajoute son délai au démarrage."""
    def servir(chemin, c):
        if chemin == S.PROBE_PATH:
            c.sendall(b'HTTP/1.1 302 Found\r\nLocation: /ailleurs\r\n'
                      b'Content-Length: 0\r\n\r\n')
        else:
            c.sendall(_http_200(_reponse_logx()))

    port, chemins = serveur_brut(servir)
    r = S.probe(port)
    assert r['state'] == S.OTHER, (
        'une redirection ne doit jamais pouvoir faire passer un tiers pour '
        'une instance LogX AI')
    assert chemins == [S.PROBE_PATH], 'chemins demandes : %r' % chemins


def test_probe_ne_laisse_aucun_thread_non_daemon(serveur_brut):
    """Le minuteur d'échéance ne doit pas retarder l'arrêt du processus : un
    thread non-daemon serait attendu à la sortie de l'interpréteur, ce qui
    rendrait au démarrage le blocage que cette échéance vient supprimer."""
    def servir(chemin, c):
        while True:
            time.sleep(0.05)

    port, _ = serveur_brut(servir)
    avant = set(threading.enumerate())
    S.probe(port, http_budget=0.4)
    restants = [t for t in threading.enumerate()
                if t not in avant and not t.daemon]
    assert not restants, 'threads non-daemon residuels : %r' % restants


# ─── MESSAGES CONSOLE ────────────────────────────────────────────────────────

def _tous_les_messages():
    return [
        S.message_deja_lance(8080, '0.9-beta5'),
        S.message_deja_lance(8080, None),
        S.message_deja_lance(8080, '0.9-beta5', ouvre_navigateur=False),
        S.message_port_occupe(8080, 'HTTPError: 404'),
        S.message_port_occupe(8080, ''),
        S.message_port_partage(8080, 'HTTPError: 404'),
        S.message_port_partage(8080, ''),
        S.message_bind_impossible(8080, OSError('[WinError 10048] occupe')),
    ]


@pytest.mark.parametrize('msg', _tous_les_messages())
def test_messages_100_pourcent_ascii(msg):
    """La console de LogXAI.exe n'a pas de page de code prévisible (cp850 ou
    cp1252 selon le lancement) : un accent ressortirait mojibaké au moment
    précis où l'utilisateur doit lire une consigne. Test volontairement
    strict — c'est un bug déjà rencontré sur ce projet (_apply_update.bat)."""
    msg.encode('ascii')


@pytest.mark.parametrize('msg', _tous_les_messages())
def test_messages_nomment_le_port(msg):
    assert '8080' in msg


def test_message_deja_lance_nomme_la_version_qui_repond():
    msg = S.message_deja_lance(8080, '0.9-beta5')
    assert '0.9-beta5' in msg
    # …et dit comment fermer l'instance en cours, sinon l'utilisateur qui
    # voulait vraiment redémarrer (après mise à jour) reste bloqué.
    assert 'Ctrl+C' in msg


def test_message_deja_lance_sans_version_reste_lisible():
    assert 'None' not in S.message_deja_lance(8080, None)


def test_message_deja_lance_annonce_le_navigateur_seulement_si_ouvert():
    """Ne pas promettre une ouverture de navigateur qui n'aura pas lieu."""
    assert 'navigateur' in S.message_deja_lance(8080, '1.0').lower()
    sans = S.message_deja_lance(8080, '1.0', ouvre_navigateur=False)
    assert 'navigateur' not in sans.lower()
    assert 'http://127.0.0.1:8080' in sans


def test_message_port_occupe_ne_pretend_pas_que_logx_tourne():
    """Régression visée : afficher « LogX AI est déjà lancé » alors qu'un
    logiciel tiers occupe le port enverrait l'utilisateur chercher une
    instance qui n'existe pas."""
    msg = S.message_port_occupe(8080, 'HTTPError: 404')
    assert 'DEJA lance' not in msg
    assert 'AUTRE' in msg
    assert msg != S.message_deja_lance(8080, None)


def test_message_port_partage_annonce_un_demarrage_qui_reussit():
    """Ce message accompagne un démarrage NORMAL : s'il ressemblait à un
    message d'échec, l'utilisateur fermerait la fenêtre en croyant que rien
    n'a démarré — exactement le mal qu'on vient de corriger."""
    msg = S.message_port_partage(8080, '')
    assert 'Demarrage impossible' not in msg
    assert 'DEJA lance' not in msg
    assert 'demarre normalement' in msg
    # Et il oriente vers l'adresse qui fonctionne, en écartant celle qui peut
    # mener au tiers (mesuré : « localhost » part en IPv6 et tombe sur lui).
    assert 'http://127.0.0.1:8080/' in msg
    assert 'localhost' in msg


def test_message_bind_impossible_rapporte_l_erreur_systeme():
    msg = S.message_bind_impossible(8080, OSError('[WinError 10048] occupe'))
    assert '10048' in msg


# ─── CHEMIN DE DÉMARRAGE (logx_serveur.py) ───────────────────────────────────
# logx_serveur.py ne s'importe pas sans démarrer un serveur : on vérifie donc
# son câblage sur la source. Grossier, mais c'est le seul filet possible sur
# LE fichier dont une erreur empêche l'application de démarrer.

def _source_serveur():
    with open(os.path.join(CONCOURS_DIR, 'logx_serveur.py'), encoding='utf-8') as f:
        return f.read()


def test_serveur_utilise_la_classe_protegee():
    src = _source_serveur()
    assert 'logx_singleton.LogXHTTPServer(' in src
    assert 'http.server.ThreadingHTTPServer(' not in src, (
        'le serveur de production doit passer par LogXHTTPServer, sinon '
        'SO_REUSEADDR revient et le vol de port silencieux avec')


def test_serveur_sonde_avant_de_charger_les_donnees():
    """La sonde doit précéder tout chargement/écriture : un second processus
    ne doit jamais toucher aux fichiers de données de l'instance en cours."""
    src = _source_serveur()
    i_probe = src.index('logx_singleton.probe(')
    i_load = src.index('load_log_from_disk()')
    i_bind = src.index('logx_singleton.LogXHTTPServer(')
    assert i_probe < i_load < i_bind


def test_serveur_traite_les_quatre_verdicts_de_la_sonde():
    src = _source_serveur()
    assert 'logx_singleton.LOGX' in src
    assert 'logx_singleton.OTHER' in src
    assert 'logx_singleton.SHARED' in src
    assert 'message_deja_lance' in src
    assert 'message_port_occupe' in src
    assert 'message_port_partage' in src
    assert 'message_bind_impossible' in src
    # Instance déjà là = situation normale, pas une panne : code de sortie 0
    # (un code d'erreur ferait afficher une alerte par certains lanceurs).
    assert 'code=0' in src


def test_serveur_ne_s_arrete_pas_sur_un_port_seulement_partage():
    """Le cœur de la correction, côté chemin de démarrage : SHARED doit
    AVERTIR puis laisser le démarrage continuer. Le verdict a beau être juste
    dans logx_singleton.py, un _abandonner() ici ramènerait tel quel le bug —
    LogX AI impossible à lancer derrière un écouteur dual-stack."""
    src = _source_serveur()
    i_shared = src.index("_instance['state'] == logx_singleton.SHARED")
    i_load = src.index('load_log_from_disk()')
    assert i_shared < i_load, 'la branche SHARED doit rester avant le chargement'

    # On scanne le CORPS DU `if` SHARED, pas tout l'intervalle jusqu'au
    # chargement. L'intention du test est « le verdict SHARED ne doit pas
    # interrompre le demarrage » ; scanner jusqu'a load_log_from_disk() etait
    # un raccourci, et il interdisait tout _abandonner() pose ENTRE les deux
    # pour une raison SANS RAPPORT. C'est arrive le 19/08/2026 avec le verrou
    # du dossier de donnees (voir l'assertion suivante) : un garde legitime
    # faisait rougir un test qui ne le visait pas. Bornage par indentation.
    lignes = src[i_shared:i_load].split('\n')
    corps = [lignes[0]]
    for ligne in lignes[1:]:
        if ligne.strip() and not ligne.startswith('        '):
            break
        corps.append(ligne)
    assert '_abandonner' not in '\n'.join(corps), (
        'un port seulement partage ne doit PAS interrompre le demarrage')


def test_le_verrou_du_dossier_est_pris_AVANT_de_lire_le_carnet():
    """Deux serveurs dans le meme dossier partagent logx.db et finissent par
    s effacer mutuellement (chemins RELATIFS au repertoire de travail). La
    sonde de port ne protege QUE le port : elle laisse passer deux instances
    sur deux ports differents.

    Le verrou doit etre pris AVANT load_log_from_disk() : lire puis reecrire
    un carnet qu un autre processus est en train de modifier est exactement le
    scenario a empecher."""
    src = _source_serveur()
    i_verrou = src.index('verrouiller_dossier_donnees()')
    i_load = src.index('load_log_from_disk()')
    assert i_verrou < i_load, (
        'le verrou doit preceder la lecture du carnet')
    # Et un echec doit ARRETER le demarrage, pas seulement l afficher.
    zone = src[i_verrou:i_load]
    assert '_abandonner' in zone, (
        'un dossier deja verrouille doit interrompre le demarrage : %r' % zone)


def test_spec_pyinstaller_embarque_le_module():
    """Sans logx_singleton dans les hiddenimports, l'exécutable construit
    planterait au démarrage — panne totale, invisible en développement."""
    with open(os.path.join(CONCOURS_DIR, 'logx.spec'), encoding='utf-8') as f:
        spec = f.read()
    assert "'singleton'" in spec
