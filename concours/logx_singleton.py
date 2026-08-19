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

import http.client
import http.server
import json
import os
import socket
import sys
import threading

WINDOWS = sys.platform.startswith('win')

# Adresse d'écoute du serveur — partagée avec logx_serveur.py pour que le test
# d'occupation ci-dessous porte EXACTEMENT sur ce que le vrai bind demandera.
BIND_HOST = '0.0.0.0'

# États retournés par probe()
FREE = 'free'       # personne n'écoute : on peut démarrer
LOGX = 'logx'       # une instance de LogX AI répond déjà
OTHER = 'other'     # le port est pris par un tiers, ET il nous prendrait
                    # l'adresse que nous annonçons : démarrer serait inutile
SHARED = 'shared'   # un tiers écoute aussi ce port, mais sur d'AUTRES adresses
                    # que la nôtre : LogX AI se lie et répond normalement.
                    # Avertissement en console, PAS un refus de démarrer.

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

# Échéance MURALE de l'identification HTTP, en secondes — à ne pas confondre
# avec le timeout de socket, qui borne CHAQUE opération réseau et jamais leur
# somme. _MAX_BODY borne la mémoire, pas l'attente : mesuré ici, un tiers qui
# répond au goutte à goutte (1 octet toutes les 0,1 s, donc jamais le moindre
# silence de 1,5 s) n'a déclenché AUCUN timeout — la sonde tournait encore à
# T+10 s avec 99 octets reçus sur les 65 536 attendus, soit ~1 h 50 projetées,
# sans qu'une seule ligne ne s'affiche. Le même piège vaut pour les en-têtes
# (http.client les lit ligne par ligne, jusqu'à 100 lignes de 64 Kio), d'où une
# échéance qui couvre TOUT l'échange et pas seulement le corps.
#
# 2 s : une instance LogX AI répond /network/info en quelques millisecondes
# (mesuré : 0,357 s pour la sonde complète, connexion comprise) ; ce budget lui
# laisse un facteur 5 même sur un poste chargé, tout en restant sous le seuil
# où l'utilisateur qui double-clique croirait à un plantage. Dépassement =
# état OTHER, jamais FREE : on ne démarre pas un second serveur sur un port
# qui, de toute évidence, répond à quelqu'un.
_HTTP_BUDGET = 2.0


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

    def handle_error(self, request, client_address):
        """Journalise une exception non rattrapée dans un handler.

        SANS cette surcharge, une exception levée dans do_GET/do_POST était
        AVALÉE : socketserver la rattrape à l'intérieur de
        process_request_thread(), donc elle n'atteint jamais les crochets posés
        par logx_errorlog.install() (sys.excepthook et threading.excepthook, qui
        ne voient que les exceptions qui REMONTENT jusqu'au sommet d'un thread).
        Résultat : rien dans errors.log, rien dans /debug/errors, donc un
        rapport de bogue vide — pendant que l'opérateur, lui, voyait une simple
        connexion coupée qu'il attribuait à son réseau.

        La classe de base se contente d'imprimer la trace sur stderr, invisible
        quand le serveur tourne en fenêtre minimisée (cas nominal :
        LANCER_LOGX_AI.bat le démarre minimisé). On journalise d'abord, puis on
        délègue pour ne rien retirer du comportement d'origine."""
        try:
            import sys
            import threading
            import logx_errorlog
            import logx_http
            # Filtre identique à celui de _journaliser_et_500 : une coupure de
            # liaison n'est pas un bogue serveur. Sans lui, le tampon de 50
            # entrées de /debug/errors se remplissait de déconnexions normales
            # et évinçait la vraie panne du rapport de bogue, qui ne joint que
            # la dernière entrée. (Revue adversariale du lot, 18/08/2026.)
            if not logx_http._est_incident_reseau(sys.exc_info()[1]):
                logx_errorlog._record(*sys.exc_info(),
                                      thread_name=threading.current_thread().name)
        except Exception:
            pass   # un bug du journal ne doit jamais masquer l'erreur d'origine
        super().handle_error(request, client_address)


# ─── A) DÉTECTION AVANT LE BIND ──────────────────────────────────────────────

def _bind_test(port, host=BIND_HOST):
    """Le port est-il libre ? Retourne (libre: bool, detail_erreur: str).

    `host` par défaut = l'adresse du vrai serveur (0.0.0.0). Il est aussi
    appelé avec une adresse PRÉCISE par _garde_l_adresse_sondee, qui a besoin
    de savoir non pas « puis-je ouvrir le port » mais « qui gagnera cette
    adresse-là » — voir sa docstring.

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
        s.bind((host, port))
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
    conflit entre cette socket et un bind IPv4 sur 0.0.0.0 : le bind de test
    réussit alors que quelqu'un écoute bel et bien ce port. Seule une vraie
    connexion vers 127.0.0.1 (l'adresse que le navigateur utilisera) le
    révèle.

    ATTENTION : « quelqu'un répond ici » ne veut PAS dire « ce sera lui que
    le navigateur trouvera après notre bind ». Répondre à cette question-là
    est le travail de _garde_l_adresse_sondee, et le confondre avec ce test
    revenait à refuser des démarrages parfaitement légitimes.

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


def _garde_l_adresse_sondee(host, port):
    """Une fois NOTRE serveur lié à 0.0.0.0, les connexions vers `host`
    arriveront-elles chez nous, ou chez le logiciel déjà en écoute ?

    C'est LA question qui décide entre « je démarre » et « je renonce », et
    elle n'a rien d'évident : un tiers peut écouter le port sans nous prendre
    l'adresse dont nous avons besoin. Windows (comme Linux) route une
    connexion vers la socket la PLUS SPÉCIFIQUE ; notre bind 0.0.0.0 est donc
    prioritaire sur un [::] dual-stack, mais perdant face à un 127.0.0.1
    nominatif. Mesuré sur ce poste, tiers et LogX AI liés simultanément au
    même port (0.0.0.0 pour LogX AI) :

      tiers lié sur      | notre bind 0.0.0.0 | bind de test sur 127.0.0.1
                         |                    |  → qui sert 127.0.0.1 ?
      -------------------+--------------------+---------------------------
      [::] (dual-stack)  | réussit            | réussit  → LogX AI
      127.0.0.1          | réussit            | ÉCHOUE   → le tiers
      <IP LAN>           | réussit            | réussit  → LogX AI
      0.0.0.0            | ÉCHOUE (traité en amont : conflit franc)

    Le bind de test sur l'adresse PRÉCISE suit donc exactement le routage
    réel : il échoue si et seulement si le tiers nous prendrait cette
    adresse. Un bind, pas une connexion : c'est instantané, sans listen()
    (donc sans fenêtre de pare-feu Windows) et sans le moindre paquet envoyé
    au logiciel d'en face.
    """
    return _bind_test(port, host=host)[0]


def _couper(sock, echeance_depassee):
    """Débloque une lecture en cours quand l'échéance est dépassée.

    Le drapeau est levé AVANT la coupure : le thread principal doit pouvoir
    distinguer « c'est moi qui ai coupé » d'une vraie erreur réseau au moment
    où son exception remonte. Sans lui, le détail affiché serait le message
    système brut — mesuré ici : « [WinError 10053] Une connexion etablie a ete
    abandonnee par un logiciel de votre ordinateur hote », accentué (donc
    mojibaké sur la console de LogXAI.exe) et trompeur : il désigne un logiciel
    fautif alors que la coupure est notre propre garde-fou.

    shutdown() plutôt que close() : il fait rendre EOF au recv() bloqué sans
    invalider le descripteur, que le thread principal est en train d'utiliser.
    Fermer une socket sous les pieds d'un autre thread rend le descripteur
    réutilisable immédiatement — une autre socket ouverte au même instant
    hériterait du numéro et la lecture en cours lirait ses octets à elle.
    Muet par construction : la socket peut avoir été fermée normalement entre
    le déclenchement du minuteur et cet appel, c'est le cas le plus fréquent.
    """
    echeance_depassee.set()
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


def _fetch_signature(host, port, timeout, budget=_HTTP_BUDGET):
    """Interroge PROBE_PATH. Retourne (données_json_ou_None, detail_texte).

    Retourne au plus tard à `budget` secondes (échéance murale) : voir
    _HTTP_BUDGET. Le timeout de socket seul ne suffit pas — il borne chaque
    recv(), pas leur nombre — donc un minuteur coupe la socket à l'échéance,
    ce qui fait échouer la lecture en cours au lieu de la laisser durer. Le
    minuteur est armé APRÈS connect(), le seul moment où la socket existe ; ce
    connect() est, lui, une opération unique, déjà bornée par `timeout`.

    http.client en direct plutôt qu'urllib, pour deux raisons de fond :

    1. AUCUNE redirection n'est suivie, alors que l'opener d'urllib embarque
       HTTPRedirectHandler par défaut. Une instance LogX AI répond 200 sur
       /network/info, elle n'a jamais besoin d'être redirigée ; à l'inverse,
       suivre une redirection laisserait le logiciel qui occupe le port
       décider de l'URL interrogée — identification détournable, et surtout
       requête sortante vers une adresse arbitraire (portail captif, agent
       d'entreprise qui répond 302) à CHAQUE démarrage. Mesuré avant
       correction : la sonde demandait bien /network/info puis /ailleurs.
    2. Aucun proxy n'est consulté : http.client se connecte à l'adresse
       demandée, point. Un proxy système configuré ne doit surtout pas
       intercepter une requête vers 127.0.0.1, sans quoi la sonde
       interrogerait le proxy et LogX AI ne se reconnaîtrait pas lui-même.
       C'est acquis par construction, là où urllib l'obtenait par un
       ProxyHandler vide qu'il ne fallait pas oublier.

    Adresse IP littérale : aucune résolution DNS ne peut rallonger l'attente.
    """
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    echeance_depassee = threading.Event()
    minuteur = None
    raw = None
    statut = None
    detail = ''
    try:
        conn.connect()
        minuteur = threading.Timer(budget, _couper, (conn.sock, echeance_depassee))
        minuteur.daemon = True     # ne doit jamais retarder l'arrêt du process
        minuteur.start()
        conn.request('GET', PROBE_PATH)
        r = conn.getresponse()
        statut = r.status
        raw = r.read(_MAX_BODY)
    except Exception as e:
        detail = '%s: %s' % (type(e).__name__, e)
    finally:
        if minuteur is not None:
            minuteur.cancel()
        try:
            conn.close()
        except Exception:
            pass
    if raw is None:
        if echeance_depassee.is_set():
            # ASCII strict, comme tous les messages de ce module : ce texte
            # ressort tel quel dans message_port_occupe(), sur une console
            # dont la page de code n'est pas prévisible.
            return None, ('pas de reponse exploitable en %.1f s '
                          '(port occupe par un logiciel qui repond trop '
                          'lentement pour etre identifie)' % budget)
        return None, detail
    if statut != 200:
        # Inclut le cas de la redirection, désormais non suivie : le dire
        # explicitement vaut mieux qu'un « reponse non-JSON (0 octets) »
        # incompréhensible pour qui cherche quel logiciel occupe le port.
        return None, 'reponse HTTP %d (une instance LogX AI repond 200)' % statut
    try:
        data = json.loads(raw.decode('utf-8', 'replace'))
    except Exception:
        return None, 'reponse non-JSON (%d octets)' % len(raw)
    if not isinstance(data, dict) or not all(k in data for k in _SIGNATURE):
        return None, 'reponse JSON etrangere a LogX AI'
    return data, ''


def probe(port, host='127.0.0.1', connect_timeout=0.35, http_timeout=1.5,
          http_budget=_HTTP_BUDGET, extra_hosts=(), bind_host=BIND_HOST):
    """Qui occupe le port ? Retourne {'state', 'version', 'detail'}.

    `bind_host` -- adresse que le VRAI serveur va demander (voir
    logx_serveur.py) : par défaut BIND_HOST ('0.0.0.0'), mais l'appelant peut
    passer '127.0.0.1' quand l'accès réseau (LAN) est désactivé en CONFIG --
    le premier test de la sonde (_bind_test) doit alors porter sur la MÊME
    adresse que le futur bind, sinon il prédirait un conflit sur une
    interface que le serveur n'ouvrira jamais.

    Deux tests dont AUCUN ne peut déclarer un port occupé à tort (un échec de
    l'un ou l'autre conclut toujours « libre ») : le bind, instantané et
    fidèle à ce que fera le vrai serveur, puis — seulement s'il dit libre — une
    connexion vers 127.0.0.1, qui rattrape les serveurs invisibles au bind
    IPv4. Le port occupé est ensuite IDENTIFIÉ par un appel HTTP : distinguer
    « LogX AI tourne déjà » de « un autre logiciel occupe le port » change du
    tout au tout le message et la conduite à tenir.

    Un tiers identifié ne suffit PAS à renoncer : encore faut-il qu'il nous
    prenne l'adresse que nous annonçons. Un écouteur dual-stack [::] (banal :
    `python -m http.server`, tout serveur Node ou Go sur :8080) laisse notre
    bind 0.0.0.0 gagner 127.0.0.1 et l'IP du réseau local — l'application est
    alors 100 % utilisable, et la refuser était une VRAIE régression : le
    logiciel ne démarrait plus du tout sur ces postes. D'où le troisième
    verdict SHARED (avertir, puis démarrer), réservé au cas mesuré comme sûr
    par _garde_l_adresse_sondee. Refuser reste la conduite quand le tiers
    détient réellement notre adresse (état OTHER).

    extra_hosts -- adresses SUPPLÉMENTAIRES que LogX AI va annoncer (l'IP LAN
    WiFi du poste, typiquement, voir detecter_ip_lan()) et qui doivent donc,
    elles aussi, nous revenir pour que le verdict SHARED soit fiable : la
    boucle locale seule ne le garantit pas, voir le cas <IP LAN> mesuré dans
    _garde_l_adresse_sondee.

    Coût, borné dans TOUS les cas (aucun chemin ne peut attendre sans fin) :
      * port libre et connexions refusées vite : ~0 s ;
      * port libre, système lent à refuser : connect_timeout (0,35 s), c'est
        le pire cas du démarrage normal, borne assumée pour ne pas faire
        patienter l'utilisateur ;
      * port occupé : + au plus http_budget (2 s) pour l'identification, quoi
        que réponde le logiciel en face — silence, goutte à goutte ou flux
        sans fin (voir _HTTP_BUDGET). Ce cas se termine de toute façon par un
        message et un arrêt : rien ne tourne derrière.

    Ne lève jamais : en cas d'imprévu on renvoie FREE plutôt que d'empêcher un
    démarrage légitime, le filet de sécurité au bind rattrapant de toute façon
    une vraie collision.
    """
    try:
        libre, bind_err = _bind_test(port, host=bind_host)
        if libre:
            if not _port_accepts(host, port, connect_timeout):
                return {'state': FREE, 'version': None, 'detail': ''}
            bind_err = ''   # le bind aurait réussi : ne pas polluer le détail
        data, http_err = _fetch_signature(host, port, http_timeout, http_budget)
        if data is not None:
            version = data.get('app_version') or None
            return {'state': LOGX, 'version': version, 'detail': ''}
        # Un tiers occupe le port. Reste à savoir s'il nous prend l'adresse
        # que nous annonçons : si non, notre serveur répondra normalement et
        # l'arrêter serait un refus de démarrage injustifié.
        detail = '; '.join(x for x in (bind_err, http_err) if x)
        # dict.fromkeys plutôt qu'un tuple brut : déduplique host/extra_hosts
        # (fréquent quand la détection LAN retombe sur 127.0.0.1) sans changer
        # l'ordre, et évite de sonder deux fois la même adresse pour rien.
        adresses = tuple(dict.fromkeys((host,) + tuple(h for h in extra_hosts if h)))
        if libre and all(_garde_l_adresse_sondee(h, port) for h in adresses):
            return {'state': SHARED, 'version': None, 'detail': detail}
        return {'state': OTHER, 'version': None, 'detail': detail}
    except Exception as e:      # défensif : jamais bloquer le démarrage
        return {'state': FREE, 'version': None,
                'detail': 'sonde impossible: %s' % e}


def detecter_ip_lan():
    """IP LAN réellement annoncée aux autres postes WiFi (même technique que
    logx_serveur.py), factorisée ici pour que TOUT appelant de probe() --
    y compris logx_instance.py -- puisse la passer en extra_hosts sans
    dupliquer la logique. '127.0.0.1' en repli : dans ce cas extra_hosts
    redevient un doublon du host par défaut, sans effet (voir dict.fromkeys
    ci-dessus), pas une régression."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        return '127.0.0.1'


def sonde_sans_bind(port, host='127.0.0.1', timeout=1.5, budget=_HTTP_BUDGET):
    """Une instance LogX AI répond-elle DÉJÀ sur ce port ? Retourne sa version
    ('' si elle répond sans la communiquer), ou None si rien d'identifiable.

    NE SE LIE JAMAIS AU PORT, contrairement à probe(). C'est toute la raison
    d'être de cette fonction, et ce n'est pas un détail de style : `_bind_test`
    ouvre réellement le port le temps du test. Employée en boucle pendant qu'un
    serveur est en train de démarrer — exactement ce que fait le lanceur quand
    il attend que le serveur réponde — elle lui volerait le port à l'instant
    précis de son bind, et sous Windows (où `allow_reuse_address` est
    volontairement désactivé, voir LogXHTTPServer) ce bind échouerait avec
    WinError 10048. L'attente aurait alors PROVOQUÉ la panne qu'elle surveille.

    Ne sert donc qu'à la question « est-ce déjà debout ? », jamais à « puis-je
    démarrer ici ? » — cette seconde question reste celle de probe().
    """
    data, _ = _fetch_signature(host, port, timeout, budget)
    if data is None:
        return None
    return data.get('app_version') or ''


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


def message_deja_lance(port, version=None, ouvre_navigateur=True,
                       version_locale=None):
    """Instance LogX AI déjà en écoute : ce lancement s'arrête volontairement.

    ouvre_navigateur=False (mode développeur, où le démarrage n'ouvre jamais
    le navigateur tout seul) : on donne l'adresse au lieu d'annoncer une
    ouverture qui n'aura pas lieu — un message faux ferait douter du reste.

    version_locale — version présente DANS CE DOSSIER (APP_VERSION). Quand elle
    diffère de celle qui répond, on le dit en toutes lettres, avec les deux
    numéros côte à côte. Le texte générique en dessous décrivait déjà le
    mécanisme (« c est l ANCIEN qui continuerait de repondre »), mais décrire
    un mécanisme n'est pas constater un fait : l'utilisateur qui vient de
    mettre à jour cherche un numéro de version, pas une explication. Cas réel
    ayant motivé ce paramètre : un serveur laissé en route depuis la veille
    faisait afficher la 0.9-beta5 alors que la 0.9-beta7 était installée, sans
    que rien nulle part ne rapproche les deux numéros. Ce module n'important
    aucun module applicatif (voir docstring), la version locale est PASSÉE ici,
    jamais importée."""
    qui = ('version %s' % version) if version else 'version non communiquee'
    if ouvre_navigateur:
        suite = '  -> Ouverture de la fenetre existante dans le navigateur.'
    else:
        suite = '  -> Elle repond ici : http://127.0.0.1:%d/logx_logbook.html' % port
    lignes = [
        _LIGNE,
        '  LogX AI est DEJA lance sur ce poste.',
        '  Une instance repond sur le port %d (%s).' % (port, qui),
        suite,
    ]
    if version and version_locale and version != version_locale:
        lignes += [
            '',
            '  ATTENTION : ce n est PAS la version installee dans ce dossier.',
            '     version qui repond    : %s' % version,
            '     version installee ici : %s' % version_locale,
            '  Tant que cette instance tourne, la mise a jour reste SANS EFFET',
            '  a l ecran : c est l ancienne qui repond au navigateur.',
        ]
    lignes += [
        '',
        '  Ce nouveau lancement s arrete ici, VOLONTAIREMENT : deux serveurs',
        '  sur le meme port ecriraient en meme temps dans le meme journal de',
        '  contacts (risque reel de QSO perdus), et c est l ANCIEN qui',
        '  continuerait de repondre -- donc l ancienne version du logiciel.',
        '',
        '  Pour redemarrer pour de bon (apres une mise a jour par exemple) :',
        _comment_fermer(),
        _LIGNE,
    ]
    return '\n'.join(lignes)


def message_port_partage(port, detail=''):
    """Un tiers écoute aussi le port, mais pas sur notre adresse : LogX AI
    démarre normalement — c'est un AVERTISSEMENT, pas un refus.

    Ton volontairement rassurant : l'utilisateur voit passer un pavé au
    démarrage, il doit comprendre en une ligne que son logiciel fonctionne.
    On ne lui demande RIEN tant qu'il ne constate pas d'anomalie : lui
    prescrire de fermer un autre programme qui ne le gêne pas le lancerait
    dans une chasse inutile (et l'autre programme est peut-être le sien)."""
    lignes = [
        _LIGNE,
        '  Note : un AUTRE logiciel ecoute aussi le port %d sur ce poste.' % port,
        '  Il n occupe pas les memes adresses que LogX AI (typiquement une',
        '  socket IPv6 dite dual-stack : python -m http.server, un serveur',
        '  Node ou Go...). Verification faite avant ce demarrage : les',
        '  adresses annoncees par LogX AI lui reviennent bien.',
        '',
        '  LogX AI demarre normalement. A savoir :',
        '   - utilise http://127.0.0.1:%d/ (adresse affichee ci-dessous)' % port,
        '     ainsi que l adresse WiFi du poste : elles sont bien a nous ;',
        '   - evite en revanche http://localhost:%d/ : selon le poste, ce' % port,
        '     nom peut mener a l AUTRE logiciel.',
        '',
        '  Si une page inattendue s affichait malgre tout, identifie le',
        '  programme qui partage le port %d :' % port,
        _qui_occupe(port),
    ]
    if detail:
        lignes.append('  Detail technique : %s' % detail)
    lignes.append(_LIGNE)
    return '\n'.join(lignes)


def message_port_occupe(port, detail=''):
    """Le port est pris, la réponse ne vient pas de LogX AI, ET le tiers nous
    prend l'adresse que nous annonçons (mesuré par _garde_l_adresse_sondee) :
    démarrer donnerait un serveur que le navigateur ne trouverait pas."""
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


# ─── VERROU SUR LE DOSSIER DE DONNEES ────────────────────────────────────────
#
# probe() ne protege QUE le port. Or ce qui fait perdre des QSO, ce n est pas
# de partager un port : c est de partager un DOSSIER. logx.db et
# shared_log.json sont des chemins RELATIFS au repertoire de travail
# (logx_storage.DB_FILE), donc deux serveurs lances dans le meme dossier sur
# deux ports differents ecrivent dans le MEME carnet, chacun avec sa propre
# copie en memoire. Le premier qui sauvegarde grave son etat par-dessus celui
# de l autre, sans erreur, sans trace, et sans que ni l un ni l autre s en
# apercoive : leurs miroirs de persistance incrementale restent perimes.
#
# Cas reels, tous atteignables sans rien faire d anormal :
#   - le raccourci Windows lance une seconde instance sur un autre port ;
#   - l executable (dossier de donnees du profil) tourne pendant qu un
#     serveur de developpement tourne dans le meme dossier ;
#   - un script tiers importe logx_http/logx_storage avec ce dossier pour
#     repertoire courant.
#
# On prend un VERROU SYSTEME sur un fichier, tenu ouvert pour toute la vie du
# processus. C est la bonne primitive plutot qu un fichier .pid : le systeme
# libere le verrou tout seul si le processus meurt, plante ou est tue. Un
# fichier .pid, lui, laisse un verrou fantome apres chaque coupure de courant,
# et verifier qu un pid est vivant n est pas portable (sous Windows,
# os.kill(pid, 0) TUE le processus au lieu de le sonder).
FICHIER_VERROU = '.logx_dossier.lock'
_poignee_verrou = None      # gardee ouverte volontairement : fermer = liberer


def verrouiller_dossier_donnees():
    """Prend le verrou du dossier courant. Retourne True si obtenu.

    Ne leve jamais : sur un systeme de fichiers qui ne sait pas verrouiller
    (certains montages reseau), on prefere demarrer sans protection plutot que
    de refuser de demarrer -- l absence de verrou n a jamais fait perdre un
    QSO a elle seule, un refus de demarrage en pleine expedition, si."""
    global _poignee_verrou
    if _poignee_verrou is not None:
        return True
    try:
        f = open(FICHIER_VERROU, 'a+b')
    except Exception as e:
        # Dossier non inscriptible : on demarre sans protection, mais on le
        # DIT. Un repli muet qui rend True ferait croire le verrou pris.
        print('[VERROU] dossier non inscriptible (%s) : demarrage sans '
              'protection du dossier de donnees.' % e)
        return True
    try:
        if WINDOWS:
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False                     # tenu par un autre processus VIVANT
    except Exception as e:
        # Verrouillage non supporte par ce systeme de fichiers. On demarre,
        # mais BRUYAMMENT : c est exactement en avalant ce genre d exception
        # qu on croit protege ce qui ne l est pas. La premiere version de
        # cette fonction utilisait os.name sans avoir importe os -- le
        # NameError tombait ici, et la fonction rendait True sans avoir pris
        # le moindre verrou. Trouve en essayant reellement deux processus.
        f.close()
        print('[VERROU] verrouillage indisponible (%s) : demarrage sans '
              'protection du dossier de donnees.' % e)
        return True
    try:
        f.seek(0)
        f.truncate()
        f.write(('%d\n' % os.getpid()).encode('ascii'))
        f.flush()
    except Exception:
        pass
    _poignee_verrou = f                  # NE PAS fermer : le verrou tomberait
    return True


def message_dossier_verrouille(dossier=None):
    """Un autre processus LogX AI travaille deja dans ce dossier.

    Le parametre `dossier` vaut par defaut le repertoire de travail
    courant, calcule ICI plutot qu au site d appel. Le
    site d appel (logx_serveur) n a pas a importer os pour ca -- il ne
    l importe pas, et la premiere version faisait planter le message d erreur
    lui-meme par un NameError. Deux fois la meme supposition dans le meme lot :
    ne jamais tenir un import pour acquis."""
    if dossier is None:
        dossier = os.getcwd()
    return '\n'.join((
        _LIGNE,
        '  Demarrage impossible : un autre LogX AI utilise deja ce dossier.',
        '',
        '  Dossier : %s' % dossier,
        '',
        '  Deux programmes qui ecrivent le meme carnet finissent par se',
        '  l effacer mutuellement : chacun garde sa propre copie en memoire,',
        '  et le premier qui enregistre remplace le travail de l autre. Sans',
        '  message, sans erreur. C est pour ca que ce demarrage est refuse.',
        '',
        '  Ferme l autre LogX AI (regarde la barre des taches et la zone de',
        '  notification), puis relance celui-ci.',
        _LIGNE,
    ))


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
