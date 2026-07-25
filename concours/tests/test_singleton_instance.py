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
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        serveurs.append(srv)
        return srv.server_address[1]

    yield _start
    for srv in serveurs:
        srv.shutdown()
        srv.server_close()


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


def test_probe_detecte_un_serveur_invisible_au_bind(monkeypatch, serveur_ephemere):
    """Cas mesuré en vrai avec `python -m http.server` : le tiers écoute sur
    une socket IPv6 « dual-stack », Windows n'y voit aucun conflit avec un
    bind IPv4 0.0.0.0 — le test de bind conclut « libre » alors que le
    navigateur, lui, tombera sur l'autre logiciel en visitant 127.0.0.1.
    Seule la connexion réelle le révèle : elle doit rester dans la sonde."""
    port = serveur_ephemere(json.dumps({'service': 'autre'}).encode())
    monkeypatch.setattr(S, '_bind_test', lambda p: (True, ''))   # bind aveugle
    assert S.probe(port)['state'] == S.OTHER


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


# ─── MESSAGES CONSOLE ────────────────────────────────────────────────────────

def _tous_les_messages():
    return [
        S.message_deja_lance(8080, '0.9-beta5'),
        S.message_deja_lance(8080, None),
        S.message_deja_lance(8080, '0.9-beta5', ouvre_navigateur=False),
        S.message_port_occupe(8080, 'HTTPError: 404'),
        S.message_port_occupe(8080, ''),
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


def test_serveur_traite_les_trois_verdicts_de_la_sonde():
    src = _source_serveur()
    assert 'logx_singleton.LOGX' in src
    assert 'logx_singleton.OTHER' in src
    assert 'message_deja_lance' in src
    assert 'message_port_occupe' in src
    assert 'message_bind_impossible' in src
    # Instance déjà là = situation normale, pas une panne : code de sortie 0
    # (un code d'erreur ferait afficher une alerte par certains lanceurs).
    assert 'code=0' in src


def test_spec_pyinstaller_embarque_le_module():
    """Sans logx_singleton dans les hiddenimports, l'exécutable construit
    planterait au démarrage — panne totale, invisible en développement."""
    with open(os.path.join(CONCOURS_DIR, 'logx.spec'), encoding='utf-8') as f:
        spec = f.read()
    assert "'singleton'" in spec
