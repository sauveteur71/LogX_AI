# -*- coding: utf-8 -*-
"""La sonde des stations curées — le point le plus dangereux du module pour
une expédition de quinze jours.

CE QUE LA REVUE ADVERSARIALE A TROUVÉ ICI (01/08/2026), et que ces tests
empêchent de revenir :

1. FUITE DU POOL RÉSEAU PARTAGÉ (critique). La sonde passait par fetch_url(),
   dont le pool de 8 threads sert TOUTE l'application (cluster DX, QRZ,
   solaire, POTA, mises à jour). Son `.result(timeout)` ne débloque que
   l'appelant : le thread abandonné continue. Or `resp.read()` ne rend jamais
   la main face à un hôte qui envoie un octet toutes les 0,4 s — le timeout de
   socket est réarmé à chaque octet. Une seule des 43 stations dans cet état
   suffisait à consumer un worker par passe horaire : pool mort en huit heures,
   et avec lui tout le réseau du logiciel. Sur 360 h non-stop, une certitude.

2. LE DÉLAI EXPIRÉ JETAIT LE DÉJÀ-LU. Première version du correctif : un
   récepteur lent avait bel et bien répondu « HTTP/1.1 200 OK », mais
   l'exception de fin de lecture emportait le tampon et le déclarait MORT.

3. L'ÉTAT ÉCRIT SANS GARDE. Un portail captif d'hôtel répond 200 avec sa page
   de connexion à toutes les URL : 43 stations mortes marquées vivantes, et
   « écouter ce spot » envoyait l'opérateur sur un récepteur éteint. Symétrie :
   plus de réseau du tout n'est pas « les 43 stations sont mortes cette
   heure-ci ». Même leçon que le cache TLE.

Les serveurs de test LISENT la requête avant de répondre — un serveur factice
qui répond puis ferme aussitôt provoque un RST sur Windows et fait échouer la
sonde pour une raison qui n'existe pas en production. Le premier jet de ces
tests est tombé dans ce piège et accusait le code.
"""
import json
import os
import socket
import sys
import threading
import time

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_websdr as ws   # noqa: E402

PAGE = (b'<html><body>' + b'page d accueil du recepteur. ' * 20
        + b'</body></html>')


class FauxRecepteur:
    """Serveur HTTP minimal au comportement choisi. `drip` = envoie un octet
    toutes les 0,4 s sans jamais finir (l'hôte pathologique) ; `muet` = accepte
    la connexion et ne répond rien (l'autre grand classique)."""

    def __init__(self, reponse=b'', drip=False, muet=False):
        self.reponse, self.drip, self.muet = reponse, drip, muet
        self._stop = threading.Event()
        self._srv = socket.socket()
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(('127.0.0.1', 0))
        self._srv.listen(32)
        self.port = self._srv.getsockname()[1]
        self._t = threading.Thread(target=self._boucle, daemon=True)
        self._t.start()

    @property
    def url(self):
        return 'http://127.0.0.1:%d/' % self.port

    def _boucle(self):
        while not self._stop.is_set():
            try:
                self._srv.settimeout(0.3)
                cli, _ = self._srv.accept()
            except Exception:
                continue
            threading.Thread(target=self._servir, args=(cli,),
                             daemon=True).start()

    def _servir(self, cli):
        try:
            cli.settimeout(5)
            cli.recv(4096)                 # un vrai serveur lit la requête
            if self.muet:
                while not self._stop.is_set():
                    time.sleep(0.1)
                return
            cli.sendall(self.reponse)
            while self.drip and not self._stop.is_set():
                cli.sendall(b'x')
                time.sleep(0.4)
            time.sleep(0.1)
            cli.close()
        except Exception:
            pass

    def fermer(self):
        self._stop.set()
        try:
            self._srv.close()
        except Exception:
            pass


@pytest.fixture
def recepteurs():
    ouverts = []

    def _ouvrir(**kw):
        r = FauxRecepteur(**kw)
        ouverts.append(r)
        return r
    yield _ouvrir
    for r in ouverts:
        r.fermer()


def _cures(dossier, urls, etat_ancien=None):
    with open(os.path.join(dossier, 'websdr_cures.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'stations': [{'nom': 'S%d' % i, 'url': u, 'type': 'websdr'}
                                for i, u in enumerate(urls)]}, f)
    if etat_ancien is not None:
        with open(os.path.join(dossier, 'websdr_etat_cures.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({'sonde': '2026-08-01T07:00:00', 'etat': etat_ancien}, f)


def _etat_sur_disque(dossier):
    with open(os.path.join(dossier, 'websdr_etat_cures.json'),
              encoding='utf-8') as f:
        return json.load(f)['etat']


# ─── La sonde elle-même ─────────────────────────────────────────────────────

def test_un_hote_au_goutte_a_goutte_ne_retient_jamais_le_thread(recepteurs):
    """LE constat critique. Sans borne réelle, l'appel ne revient JAMAIS et le
    worker est perdu — c'est ainsi que le pool commun mourait."""
    r = recepteurs(reponse=b'HTTP/1.1 200 OK\r\n\r\n', drip=True)
    t0 = time.monotonic()
    vivant, _ = ws._sonde_http(r.url, timeout=3)
    duree = time.monotonic() - t0
    assert duree < 6, 'la sonde a duré %.1f s : elle n\'est pas bornée' % duree
    # ... et le récepteur, qui a bel et bien répondu 200, reste VIVANT :
    # la fin de lecture ne doit pas emporter le tampon déjà reçu.
    assert vivant is True


def test_un_hote_qui_accepte_et_se_tait_est_borne_aussi(recepteurs):
    r = recepteurs(muet=True)
    t0 = time.monotonic()
    vivant, _ = ws._sonde_http(r.url, timeout=2)
    assert time.monotonic() - t0 < 5
    assert vivant is False


@pytest.mark.parametrize('statut, attendu', [
    (b'HTTP/1.1 200 OK', True),
    (b'HTTP/1.1 302 Found', True),
    (b'HTTP/1.1 401 Unauthorized', True),    # protégé par mot de passe = vivant
    (b'HTTP/1.1 403 Forbidden', True),
    (b'HTTP/1.1 404 Not Found', False),
    (b'HTTP/1.1 502 Bad Gateway', False),
])
def test_le_verdict_suit_le_code_http(recepteurs, statut, attendu):
    r = recepteurs(reponse=statut + b'\r\n\r\n' + PAGE)
    assert ws._sonde_http(r.url, timeout=3)[0] is attendu


def test_ce_qui_n_est_pas_du_http_n_est_pas_un_recepteur(recepteurs):
    """Un port qui répond une bannière SSH n'est pas un WebSDR."""
    r = recepteurs(reponse=b'SSH-2.0-OpenSSH_9.6\r\n')
    assert ws._sonde_http(r.url, timeout=2)[0] is False


@pytest.mark.parametrize('url', [
    'javascript:alert(1)',       # sans « // » : ne doit PAS être préfixé http
    'JavaScript:alert(1)',
    'ftp://exemple.test/',
    'file:///etc/passwd',
    'http://exemple.test:port/',  # port non numérique -> ValueError sur u.port
    'http://exemple.test:99999/',
    'http:///pas-d-hote',
    '',
    None,
])
def test_une_url_inexploitable_n_est_jamais_sondee(url):
    """Écrit après un échec de CE fichier : la sonde préfixait « http:// »
    devant toute URL sans « // », si bien que « javascript:… » passait le
    contrôle de schéma, puis plantait sur un port non numérique."""
    assert ws._sonde_http(url, timeout=1) == (False, '')


def test_la_sonde_n_utilise_PAS_le_pool_reseau_commun(recepteurs, tmp_path):
    """Le cœur du correctif : quoi qu'il arrive aux hôtes sondés, le pool de
    fetch_url() — celui du cluster, de QRZ, du solaire — reste disponible."""
    from logx_utils import _FETCH_EXECUTOR
    avant = len(_FETCH_EXECUTOR._threads)
    lents = [recepteurs(reponse=b'HTTP/1.1 200 OK\r\n\r\n', drip=True)
             for _ in range(4)]
    _cures(str(tmp_path), [r.url for r in lents])
    for _ in range(3):
        ws.sonder_cures(dossier=str(tmp_path), timeout=2)
    assert len(_FETCH_EXECUTOR._threads) == avant, (
        'la sonde a consommé des threads du pool partagé de fetch_url')
    assert len(ws._executeur_sonde()._threads) <= 4


# ─── L'état écrit : jamais écrasé par une réponse inexploitable ─────────────

def test_portail_captif_la_meme_page_partout_ne_remplace_pas_l_etat(
        recepteurs, tmp_path):
    """WiFi d'hôtel : 200 + page de connexion pour TOUTES les URL. Sans cette
    garde, 43 stations mortes passaient pour vivantes et « écouter ce spot »
    ouvrait un récepteur éteint."""
    login = (b'HTTP/1.1 200 OK\r\n\r\n<html><body>'
             + b'Portail WiFi : identifiez-vous. ' * 30 + b'</body></html>')
    r = recepteurs(reponse=login)
    urls = ['http://127.0.0.1:%d/s%d' % (r.port, i) for i in range(6)]
    ancien = {u: (i == 0) for i, u in enumerate(urls)}
    _cures(str(tmp_path), urls, ancien)
    res = ws.sonder_cures(dossier=str(tmp_path), timeout=3)
    assert res['ok'] is False and 'captif' in res['error']
    assert _etat_sur_disque(str(tmp_path)) == ancien   # rien n'a bougé


def test_plus_aucun_reseau_ne_declare_pas_les_stations_mortes(tmp_path):
    """Ce n'est pas « les 43 stations sont mortes cette heure-ci » : c'est
    « je ne sais pas ». Même leçon que le cache TLE."""
    urls = ['http://127.0.0.1:%d/' % (1 + i) for i in range(4)]
    ancien = {u: True for u in urls}
    _cures(str(tmp_path), urls, ancien)
    res = ws.sonder_cures(dossier=str(tmp_path), timeout=1)
    assert res['ok'] is False
    assert _etat_sur_disque(str(tmp_path)) == ancien


def test_des_recepteurs_distincts_s_enregistrent_normalement(recepteurs,
                                                             tmp_path):
    """La garde anti-portail ne doit pas bloquer le cas NORMAL — une garde qui
    refuse tout serait pire que pas de garde du tout."""
    rs = [recepteurs(reponse=b'HTTP/1.1 200 OK\r\n\r\n<html>recepteur '
                     + bytes(str(i) * 250, 'ascii') + b'</html>')
          for i in range(6)]
    _cures(str(tmp_path), [r.url for r in rs])
    res = ws.sonder_cures(dossier=str(tmp_path), timeout=3)
    assert res['ok'] is True and res['vivantes'] == 6
    assert sum(_etat_sur_disque(str(tmp_path)).values()) == 6


def test_des_hotes_lents_ne_passent_pas_pour_un_portail_captif(recepteurs,
                                                               tmp_path):
    """Piège trouvé en vérifiant le correctif lui-même : des hôtes lents ne
    livrent que leur ligne de statut avant l'échéance, donc des empreintes
    identiques — la détection de portail se déclenchait à tort et l'état
    n'était plus jamais mis à jour."""
    lents = [recepteurs(reponse=b'HTTP/1.1 200 OK\r\n\r\n', drip=True)
             for _ in range(6)]
    _cures(str(tmp_path), [r.url for r in lents])
    res = ws.sonder_cures(dossier=str(tmp_path), timeout=2)
    assert res['ok'] is True, res
    assert res['vivantes'] == 6
