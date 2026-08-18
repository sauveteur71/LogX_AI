# -*- coding: utf-8 -*-
"""Mesure de l'écart entre l'horloge de ce PC et l'heure UTC de référence.

POURQUOI CE MODULE EXISTE
Demandé par F4GLD le 18/08/2026, après un essai FT8 en trafic réel où rien ne
se décodait. Diagnostic établi sur sa machine : `w32tm /query /status` rendait
« Indicateur de dérive : 3 (Non synchronisé) », « Source : Local CMOS Clock »,
« Dernière synchronisation réussie : Non spécifié ». Son horloge n'avait
jamais été synchronisée et tournait libre sur le quartz de la carte mère.

En FT8 tout est calé sur des créneaux de 15 s alignés sur 00/15/30/45 s UTC,
et le signal n'occupe que 12,64 s du créneau (79 symboles à 6,25 baud —
Franke, Somerville & Taylor, « The FT4 and FT8 Communication Protocols »,
QEX juillet-août 2020). La tenue d'heure attendue est de l'ordre de LA
SECONDE. Une horloge libre sort de cette tolérance en quelques jours.

CE QUE CE MODULE NE FAIT PAS, DÉLIBÉRÉMENT
- Il ne RÈGLE PAS l'horloge. Modifier l'heure système demande les droits
  administrateur, et le faire en douce serait une modification de réglage
  système que ce logiciel n'a pas à s'autoriser. Il MESURE et il DIT ; à
  l'opérateur de corriger.
- Il n'embarque aucun outil tiers (NetTime et consorts) : Windows, macOS et
  Linux ont tous déjà un client NTP. En embarquer un serait redistribuer un
  binaire tiers, pour une fonction que le système assure déjà, et seulement
  sur une plateforme.

CONTRAINTES PRODUIT RESPECTÉES
- OPTIONNEL : rien n'appelle ce module tant que l'opérateur ne l'a pas activé.
  Le logiciel reste entièrement utilisable sans, et la page FT8 mesure déjà
  son décalage à partir des stations reçues (colonne DT), sans aucun réseau.
- VIE PRIVÉE : une requête SNTP ne transmet AUCUNE donnée personnelle. Le
  paquet client de 48 octets ne contient qu'un horodatage ; ni indicatif, ni
  position, ni identifiant. C'est la requête réseau la plus anodine du
  logiciel.
- MULTIPLATEFORME : bibliothèque standard seule (socket, struct).

PROTOCOLE
SNTP, mode client, tel que défini par la RFC 5905 (« Network Time Protocol
Version 4: Protocol and Algorithms Specification ») :
- en-tête de 48 octets, §7.3 ;
- horodatages sur 64 bits en virgule fixe 32.32, secondes depuis le
  1er janvier 1900 00:00 UTC ;
- algorithme de calcul de l'écart, §8 : avec T1 = départ client,
  T2 = arrivée serveur, T3 = départ serveur, T4 = arrivée client,
      écart  = ((T2 - T1) + (T3 - T4)) / 2
      trajet = (T4 - T1) - (T3 - T2)
  La demi-somme élimine le temps de trajet aller-retour, à condition qu'il
  soit symétrique — d'où le `trajet` rendu aussi : un trajet très long rend la
  mesure moins sûre, et l'appelant doit pouvoir en tenir compte.
"""
import socket
import struct
import time

# Décalage entre l'ère NTP (1900-01-01) et l'ère POSIX (1970-01-01), en
# secondes : 70 ans dont 17 bissextiles. RFC 5905 §6.
ERE_NTP_VERS_POSIX = 2208988800

# Serveur par défaut : le pool NTP public, sous-domaine français. Choisi parce
# qu'il est associatif, sans inscription, sans clé, et qu'il répartit la charge
# entre des centaines de serveurs bénévoles — donc aucune dépendance à un
# fournisseur unique. Reste entièrement remplaçable en configuration : un
# radio-club derrière un pare-feu strict pointera son propre serveur.
SERVEUR_DEFAUT = 'fr.pool.ntp.org'

# Un délai franc : au-delà, mieux vaut dire « pas de réponse » que faire
# attendre. La mesure n'est jamais sur un chemin critique.
TIMEOUT_DEFAUT = 3.0

# Au-delà de ce trajet aller-retour, l'hypothèse de symétrie devient douteuse
# et l'écart calculé peut être faux de l'ordre de la demi-asymétrie. On rend
# quand même la mesure, mais marquée comme peu sûre.
TRAJET_DOUTEUX_S = 1.0

# Premier octet du paquet client : LI=0 (pas d'annonce de seconde
# intercalaire), VN=4 (version 4), Mode=3 (client) — RFC 5905 §7.3.
_ENTETE_CLIENT = (0 << 6) | (4 << 3) | 3


def _vers_secondes(bloc):
    """Horodatage NTP 64 bits (32.32 virgule fixe) -> secondes POSIX."""
    entier, fraction = struct.unpack('!II', bloc)
    return (entier - ERE_NTP_VERS_POSIX) + fraction / 2 ** 32


def interroger(serveur=None, timeout=None):
    """Mesure l'écart de l'horloge locale par rapport au serveur donné.

    Rend toujours un dict, ne lève jamais — une mesure d'horloge indisponible
    ne doit sous aucun prétexte interrompre le trafic :
      {'ok': True,  'ecart_s': float, 'trajet_s': float, 'sur': bool,
       'serveur': str, 'strate': int}
      {'ok': False, 'error': str, 'serveur': str}

    `ecart_s` > 0 : l'horloge locale est EN RETARD sur la référence (il faut
    l'avancer). < 0 : elle est EN AVANCE. Convention opposée à celle du DT de
    la page FT8, qui mesure l'inverse — d'où le nom explicite et ce
    commentaire, pour qu'on ne les confonde jamais.
    """
    serveur = (serveur or SERVEUR_DEFAUT).strip() or SERVEUR_DEFAUT
    timeout = timeout or TIMEOUT_DEFAUT
    paquet = bytearray(48)
    paquet[0] = _ENTETE_CLIENT

    sock = None
    try:
        # AF_INET explicite : le pool NTP répond en IPv4 partout, et une pile
        # IPv6 mal configurée (fréquent derrière une box) ferait échouer une
        # résolution en AAAA sans que l'opérateur comprenne pourquoi.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        # time.time() et non time.monotonic() : on compare à une heure
        # ABSOLUE. monotonic n'a pas l'epoch pour origine (piège déjà rencontré
        # dans ce dépôt le 02/08/2026).
        t1 = time.time()
        sock.sendto(bytes(paquet), (serveur, 123))
        reponse, _ = sock.recvfrom(48)
        t4 = time.time()
    except socket.gaierror:
        return {'ok': False, 'serveur': serveur,
                'error': f"Serveur de temps introuvable : {serveur} "
                         "(nom mal orthographié, ou pas d'accès Internet)"}
    except socket.timeout:
        return {'ok': False, 'serveur': serveur,
                'error': f'Pas de réponse de {serveur} après {timeout:g} s '
                         '(le port UDP 123 est peut-être bloqué par le pare-feu '
                         'ou la box)'}
    except OSError as e:
        return {'ok': False, 'serveur': serveur,
                'error': f'Échec réseau vers {serveur} : {e}'}
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    if len(reponse) < 48:
        return {'ok': False, 'serveur': serveur,
                'error': f'Réponse tronquée de {serveur} ({len(reponse)} octets sur 48)'}

    mode = reponse[0] & 0b111
    if mode != 4:
        # Mode 4 = serveur (RFC 5905 §7.3). Autre chose = ce n'est pas une
        # réponse à notre requête : on refuse plutôt que de lire des octets au
        # hasard comme un horodatage.
        return {'ok': False, 'serveur': serveur,
                'error': f'Réponse inattendue de {serveur} (mode {mode}, 4 attendu)'}

    strate = reponse[1]
    if strate == 0:
        # « Kiss-o'-Death » (RFC 5905 §7.4) : le serveur refuse de nous servir
        # — surcharge, ou cadence de requêtes trop élevée. Le message tient
        # dans l'identifiant de référence, octets 12 à 15.
        code = reponse[12:16].decode('ascii', 'replace').strip('\x00 ')
        return {'ok': False, 'serveur': serveur,
                'error': f'{serveur} refuse de répondre (code {code or "inconnu"}) — '
                         'réessaie plus tard ou choisis un autre serveur'}

    t2 = _vers_secondes(reponse[32:40])   # arrivée de notre requête au serveur
    t3 = _vers_secondes(reponse[40:48])   # départ de la réponse du serveur

    ecart = ((t2 - t1) + (t3 - t4)) / 2
    trajet = (t4 - t1) - (t3 - t2)
    return {'ok': True, 'serveur': serveur, 'strate': strate,
            'ecart_s': ecart, 'trajet_s': trajet,
            'sur': abs(trajet) < TRAJET_DOUTEUX_S}
