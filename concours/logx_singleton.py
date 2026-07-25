# -*- coding: utf-8 -*-
"""Instance unique — deux serveurs LogX AI ne doivent JAMAIS servir le même port.

BUG RÉEL CORRIGÉ ICI (constaté par un utilisateur, puis reproduit en mesure) :
relancer LogX AI alors qu'une instance tournait déjà affichait un démarrage
parfaitement normal, sans la moindre erreur… mais c'était l'ANCIEN processus
qui continuait de répondre. L'utilisateur croyait utiliser la nouvelle version
(sa barre de statut proposait une mise à jour vers une version DÉJÀ installée,
parce que le vieux serveur répondait encore à /app/update_check).

Cause : `http.server.ThreadingHTTPServer` hérite de `HTTPServer` qui pose
`allow_reuse_address = 1`, donc SO_REUSEADDR sur le socket d'écoute. Sous
Unix, cette option autorise seulement à reprendre un port en TIME_WAIT — elle
ne permet PAS de voler un port en écoute, et rester sans elle casserait le
redémarrage rapide. Sous Windows, la sémantique est tout autre : SO_REUSEADDR
autorise un second socket à se lier à un port DÉJÀ ÉCOUTÉ par un autre
processus. Le bind réussit en silence et la répartition des connexions
devient indéterminée (en pratique : l'ancien continue de servir).

Mesures faites sur le poste de développement (Windows 11, Python 3.13.7) —
c'est ce qui justifie les choix ci-dessous, rien n'a été supposé :
  * socketserver.TCPServer.allow_reuse_address vaut False depuis CPython 3.11,
    mais http.server.HTTPServer le remet à 1 → c'est bien lui le coupable ;
  * A écoute (reuse=1), B se lie au même port avec reuse=1 → SUCCÈS, et c'est
    A qui répond : le bug de l'utilisateur, reproduit à l'identique ;
  * même situation, B avec allow_reuse_address=False → ÉCHEC WinError 10048
    (« une seule utilisation de chaque adresse de socket ») : vol empêché ;
  * rebind immédiat sur un port portant 3 connexions réellement en TIME_WAIT
    (vérifiées à netstat) → SUCCÈS avec ou sans SO_REUSEADDR : sous Windows,
    retirer l'option ne coûte donc RIEN au redémarrage rapide.

Pourquoi allow_reuse_address=False plutôt que SO_EXCLUSIVEADDRUSE : les deux
bloquent le vol (mesuré), mais ils ne protègent pas la même chose.
SO_EXCLUSIVEADDRUSE protège l'instance en place contre un voleur — utile
seulement si le voleur est une version ANCIENNE (mesuré : elle est alors
rejetée avec WSAEACCES) ; allow_reuse_address=False empêche CE processus-ci de
voler, ce qui est exactement le scénario signalé (on relance une nouvelle
version par-dessus une ancienne qui tourne). Le second cas est couvert en plus
par la détection amicale ci-dessous, et SO_EXCLUSIVEADDRUSE demande de
surcharger server_bind() en ajoutant une option dont Microsoft documente des
refus de rebind en présence de TIME_WAIT : trop de risque pour un gain
marginal sur un chemin de démarrage qui ne doit JAMAIS échouer. Retirer un
drapeau que Windows n'aurait jamais dû recevoir est la correction minimale.

Deux protections indépendantes, chacune suffisante à elle seule :
  A) probe() — AVANT le bind : le port est-il pris, et par qui ? Le lanceur
     affiche alors un message clair, ouvre la fenêtre de l'instance existante
     et s'arrête sans démarrer de second serveur (voir logx_serveur.py).
  B) LogXHTTPServer — filet de sécurité AU bind, pour la course possible entre
     la sonde et le bind (deux double-clics rapprochés) : sous Windows le bind
     ÉCHOUE bruyamment au lieu de réussir en silence.

Ce module n'importe QUE la bibliothèque standard (aucun module applicatif) :
il doit rester utilisable très tôt au démarrage, sans effet de bord.
"""

import http.server
import json
import socket
import sys
import urllib.request

WINDOWS = sys.platform.startswith('win')

# Adresse d'écoute du serveur — partagée avec logx_serveur.py pour que le test
# d'occupation ci-dessous porte EXACTEMENT sur ce que le vrai bind demandera.
BIND_HOST = '0.0.0.0'

# États retournés par probe()
FREE = 'free'     # personne n'écoute : on peut démarrer
LOGX = 'logx'     # une instance de LogX AI répond déjà
OTHER = 'other'   # le port est pris, mais pas par LogX AI

# Endpoint de détection : /network/info est servi tout en haut de do_GET, sans
# jeton de session (il sert justement à afficher l'URL WiFi avant toute
# authentification), il ne touche ni au log ni à la config, et il renvoie
# app_version — soit exactement ce qu'il faut pour nommer la version qui
# répond. /app/update_check ferait aussi l'affaire mais son contenu dépend
# d'un cache réseau, donc d'un état ; celui-ci est constant.
PROBE_PATH = '/network/info'

# Clés qui signent une réponse LogX AI (présentes depuis bien avant le
# renommage RadioContest → LogX AI : une instance ancienne est reconnue).
_SIGNATURE = ('local_ip', 'port', 'url_logbook')

_MAX_BODY = 65536   # un serveur tiers pourrait répondre un flux sans fin


# ─── B) FILET DE SÉCURITÉ AU BIND ────────────────────────────────────────────

class LogXHTTPServer(http.server.ThreadingHTTPServer):
    """Serveur HTTP de production. Seule différence avec la classe standard :
    sous Windows, PAS de SO_REUSEADDR (voir la docstring du module) — un port
    déjà écouté fait échouer le bind avec WinError 10048 au lieu d'être volé
    en silence. Ailleurs (Linux/macOS), l'option est conservée : elle y sert
    uniquement à reprendre un port en TIME_WAIT, et la retirer casserait le
    redémarrage rapide du serveur.

    Définie AVANT la sonde : c'est elle qui fixe les options de socket que le
    test d'occupation doit reproduire à l'identique."""
    allow_reuse_address = not WINDOWS


# ─── A) DÉTECTION AVANT LE BIND ──────────────────────────────────────────────

def _bind_test(port):
    """Le port est-il libre ? Retourne (libre: bool, detail_erreur: str).

    Premier des deux tests de la sonde (le second est _port_accepts), et
    d'abord celui-ci parce que :

    1. Il répond à la vraie question — « mon serveur pourra-t-il ouvrir ce
       port ? » — là où une connexion répond seulement « quelqu'un
       accepte-t-il des connexions ? ». Un service à l'écoute derrière un
       pare-feu qui jette les paquets, ou dont la file d'attente est pleine,
       tromperait la seconde et pas celui-ci.
    2. Il est instantané, donc gratuit dans le cas de très loin le plus
       fréquent : le port est libre. Mesuré sur ce poste (Windows 11) : un
       connect() vers un port loopback FERMÉ met ~2 s à être refusé
       (retransmissions SYN), et ~4 s via « localhost » (deux familles
       d'adresses) — sonder d'abord par connexion coûterait ce délai à CHAQUE
       démarrage normal.

    Le socket de test porte les MÊMES options que LogXHTTPServer, sinon sa
    réponse ne prédirait pas celle du vrai bind. C'est vital sous Unix : sans
    SO_REUSEADDR, un simple TIME_WAIT résiduel (redémarrage juste après un
    arrêt) ferait échouer le test alors que le vrai serveur, lui, démarrerait
    parfaitement — l'application refuserait de se lancer sans aucune raison.
    Pas de listen() : le test n'a pas à déclencher la fenêtre de pare-feu
    Windows, seul le vrai serveur écoute.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if LogXHTTPServer.allow_reuse_address:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((BIND_HOST, port))
        return True, ''
    except OSError as e:
        return False, 'bind refuse: %s' % e
    finally:
        s.close()


def _port_accepts(host, port, timeout):
    """Quelqu'un accepte-t-il une connexion sur host:port ?

    Indispensable EN PLUS de _bind_test, et ce n'est pas théorique : mesuré
    ici avec `python -m http.server` (comme beaucoup d'outils modernes, il
    écoute sur une socket IPv6 « dual-stack » [::]). Windows ne voit aucun
    conflit entre cette socket et un bind IPv4 sur 0.0.0.0 — le bind de test
    réussit donc alors que le navigateur, lui, tombe bel et bien sur l'autre
    logiciel en visitant http://127.0.0.1:8080. Seule une vraie connexion vers
    127.0.0.1 (l'adresse que le navigateur utilisera) le révèle.

    Timeout court assumé : sur ce poste, un port loopback FERMÉ met ~2 s à
    refuser la connexion (retransmissions SYN), et l'utilisateur qui
    double-clique n'a pas à attendre ça. Un dépassement de délai est sans
    danger : il ne peut que conclure « libre », jamais « occupé » à tort — et
    le filet de sécurité au bind reste en travers du chemin.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _fetch_signature(host, port, timeout):
    """Interroge PROBE_PATH. Retourne (données_json_ou_None, detail_texte).

    Adresse IP littérale : aucune résolution DNS ne peut donc rallonger
    l'attente au-delà du timeout (piège connu de urlopen). ProxyHandler vide :
    un proxy système configuré ne doit surtout pas intercepter une requête
    vers 127.0.0.1 — sans ça la sonde interrogerait le proxy, pas l'instance.
    """
    url = 'http://%s:%d%s' % (host, port, PROBE_PATH)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=timeout) as r:
            raw = r.read(_MAX_BODY)
    except Exception as e:
        return None, '%s: %s' % (type(e).__name__, e)
    try:
        data = json.loads(raw.decode('utf-8', 'replace'))
    except Exception:
        return None, 'reponse non-JSON (%d octets)' % len(raw)
    if not isinstance(data, dict) or not all(k in data for k in _SIGNATURE):
        return None, 'reponse JSON etrangere a LogX AI'
    return data, ''


def probe(port, host='127.0.0.1', connect_timeout=0.35, http_timeout=1.5):
    """Qui occupe le port ? Retourne {'state', 'version', 'detail'}.

    Deux tests dont AUCUN ne peut déclarer un port occupé à tort (un échec de
    l'un ou l'autre conclut toujours « libre ») : le bind, instantané et
    fidèle à ce que fera le vrai serveur, puis — seulement s'il dit libre — une
    connexion vers 127.0.0.1, qui rattrape les serveurs invisibles au bind
    IPv4. Le port occupé est ensuite IDENTIFIÉ par un appel HTTP : distinguer
    « LogX AI tourne déjà » de « un autre logiciel occupe le port » change du
    tout au tout le message et la conduite à tenir.

    Coût : ~0 s quand le port est libre ET que le système refuse vite les
    connexions ; au pire connect_timeout (0,35 s) au démarrage normal, borne
    assumée pour ne pas faire patienter l'utilisateur. Ne lève jamais : en cas
    d'imprévu on renvoie FREE plutôt que d'empêcher un démarrage légitime, le
    filet de sécurité au bind rattrapant de toute façon une vraie collision.
    """
    try:
        libre, bind_err = _bind_test(port)
        if libre:
            if not _port_accepts(host, port, connect_timeout):
                return {'state': FREE, 'version': None, 'detail': ''}
            bind_err = ''   # le bind aurait réussi : ne pas polluer le détail
        data, http_err = _fetch_signature(host, port, http_timeout)
        if data is None:
            return {'state': OTHER, 'version': None,
                    'detail': '; '.join(x for x in (bind_err, http_err) if x)}
        version = data.get('app_version') or None
        return {'state': LOGX, 'version': version, 'detail': ''}
    except Exception as e:      # défensif : jamais bloquer le démarrage
        return {'state': FREE, 'version': None,
                'detail': 'sonde impossible: %s' % e}


# ─── MESSAGES (console) ──────────────────────────────────────────────────────
# ASCII strict, à dessein : ces messages s'affichent dans la fenêtre console
# de l'exécutable Windows, dont la page de code n'est pas prévisible (cp850 ou
# cp1252 selon le lancement). Un accent y ressortirait mojibaké justement au
# moment où l'utilisateur a besoin de lire une consigne claire.

_LIGNE = '=' * 62


def _comment_fermer():
    if WINDOWS:
        return ("    1. ferme l'instance en cours : Ctrl+C dans sa fenetre noire,\n"
                "       ou Gestionnaire des taches > LogXAI.exe > Fin de tache ;\n"
                "    2. relance LogX AI.")
    return ("    1. ferme l'instance en cours : Ctrl+C dans son terminal,\n"
            "       ou `pkill -f logx_serveur` ;\n"
            "    2. relance LogX AI.")


def _qui_occupe(port):
    if WINDOWS:
        return ('     Get-Process -Id (Get-NetTCPConnection -LocalPort %d '
                '-State Listen).OwningProcess' % port)
    return '     lsof -nP -iTCP:%d -sTCP:LISTEN' % port


def message_deja_lance(port, version=None, ouvre_navigateur=True):
    """Instance LogX AI déjà en écoute : ce lancement s'arrête volontairement.

    ouvre_navigateur=False (mode développeur, où le démarrage n'ouvre jamais
    le navigateur tout seul) : on donne l'adresse au lieu d'annoncer une
    ouverture qui n'aura pas lieu — un message faux ferait douter du reste."""
    qui = ('version %s' % version) if version else 'version non communiquee'
    if ouvre_navigateur:
        suite = '  -> Ouverture de la fenetre existante dans le navigateur.'
    else:
        suite = '  -> Elle repond ici : http://127.0.0.1:%d/logx_logbook.html' % port
    return '\n'.join((
        _LIGNE,
        '  LogX AI est DEJA lance sur ce poste.',
        '  Une instance repond sur le port %d (%s).' % (port, qui),
        suite,
        '',
        '  Ce nouveau lancement s arrete ici, VOLONTAIREMENT : deux serveurs',
        '  sur le meme port ecriraient en meme temps dans le meme journal de',
        '  contacts (risque reel de QSO perdus), et c est l ANCIEN qui',
        '  continuerait de repondre -- donc l ancienne version du logiciel.',
        '',
        '  Pour redemarrer pour de bon (apres une mise a jour par exemple) :',
        _comment_fermer(),
        _LIGNE,
    ))


def message_port_occupe(port, detail=''):
    """Le port est pris, mais la réponse ne vient pas de LogX AI."""
    lignes = [
        _LIGNE,
        '  Demarrage impossible : le port %d est deja utilise par un AUTRE' % port,
        '  logiciel (ce qui repond sur ce port n est pas LogX AI).',
    ]
    if detail:
        lignes.append('  Detail technique : %s' % detail)
    lignes += [
        '',
        '  Que faire :',
        '   - identifier le programme qui occupe le port %d :' % port,
        _qui_occupe(port),
        '     puis le fermer, et relancer LogX AI ;',
        '   - si LogX AI semblait deja ouvert, c est qu il ne repond plus :',
        '     ferme-le completement avant de relancer.',
        _LIGNE,
    ]
    return '\n'.join(lignes)


def message_bind_impossible(port, err):
    """Le bind a échoué malgré la sonde (course, pare-feu, port réservé...)."""
    return '\n'.join((
        _LIGNE,
        '  Demarrage impossible : le serveur n a pas pu ouvrir le port %d.' % port,
        '  Le systeme a repondu : %s' % err,
        '',
        '  Cause la plus frequente : le port vient d etre pris entre la',
        '  verification et le demarrage -- typiquement une autre instance de',
        '  LogX AI lancee au meme moment (deux double-clics rapproches).',
        '  Aucun second serveur n a ete demarre : c est voulu, deux serveurs',
        '  ecrivant dans le meme journal peuvent faire perdre des QSO.',
        '',
        '  Verifie qui occupe le port %d :' % port,
        _qui_occupe(port),
        _LIGNE,
    ))
