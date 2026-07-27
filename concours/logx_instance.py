# -*- coding: utf-8 -*-
"""Que doit faire le lanceur (.bat) avant de demarrer le serveur ?

BUG REEL CORRIGE ICI. LANCER_RADIOCONTEST.bat testait le port avec `curl` :
si QUELQUE CHOSE repondait sur 8080, il sautait directement a l'ouverture du
navigateur sans jamais executer `python logx_serveur.py`. Or c'est
logx_serveur.py qui porte la detection d'instance deja lancee
(logx_singleton.probe) et son message d'explication. Le .bat court-circuitait
donc le seul code capable de dire « une ANCIENNE version repond encore ».

Constat sur ce poste : un serveur laisse en route depuis la veille servait la
0.9-beta5 ; relancer le .bat apres l'installation de la 0.9-beta7 affichait
« [OK] Serveur deja en route » -- ce qui etait vrai -- puis ouvrait le
navigateur sur l'ancienne version, sans un mot. Le curl repondait a la
question « quelque chose ecoute-t-il ? », alors que la seule question utile
est « est-ce le bon serveur qui ecoute ? ».

Le present module ne duplique aucune logique : il appelle la meme sonde que le
serveur, et traduit son verdict en code de sortie pour le .bat.

Codes de sortie (le .bat s'y branche, voir LANCER_RADIOCONTEST.bat) :
   0  rien n'ecoute, ou un tiers partage le port sans nous prendre nos adresses
      -> le lanceur demarre le serveur normalement ;
  10  LogX AI repond deja, dans la MEME version que ce dossier
      -> le lanceur ouvre seulement le navigateur (comportement d'origine,
         legitime celui-la) ;
  11  LogX AI repond deja, dans une version DIFFERENTE de ce dossier
      -> le lanceur affiche le message et n'ouvre RIEN : ouvrir le navigateur
         montrerait l'ancienne version en faisant croire a une mise a jour
         ratee ;
  12  le port est pris par un autre logiciel
      -> le lanceur s'arrete, demarrer ne servirait a rien.

Avec --attendre (appele APRES le demarrage du serveur), meme jeu de codes,
plus :
  13  le serveur n'a pas repondu dans le delai
      -> le lanceur n'ouvre RIEN et explique ou lire la cause.

POURQUOI --attendre EXISTE. Le lanceur attendait `timeout /t 3` en aveugle
puis ouvrait le navigateur quoi qu'il arrive. Deux consequences, toutes deux
constatables :
  * la fenetre du serveur etant lancee minimisee (`start /MIN`), un refus de
    demarrer -- port pris entre la sonde et le bind, plantage a l'import --
    s'affichait dans une fenetre que personne ne regarde, pendant que le
    navigateur s'ouvrait sur une adresse morte ; l'utilisateur voyait
    « impossible de se connecter » sans la moindre explication ;
  * 3 secondes est une DEVINETTE : sur un poste lent ou un antivirus qui
    inspecte l'interpreteur, le serveur met plus longtemps, et le navigateur
    s'ouvrait trop tot sur la meme erreur -- alors que tout allait bien.
Attendre que le port REPONDE supprime les deux d'un coup.

POURQUOI 10/11/12 ET PAS 1/2/3. Python sort avec le code 1 sur toute exception
non rattrapee (ImportError, interpreteur trop ancien...). Avec un code 1
signifiant « ouvre seulement le navigateur », un simple plantage de ce
pre-controle aurait fait ouvrir le navigateur sans qu'aucun serveur ne tourne
-- une page blanche pour l'utilisateur. Les codes utiles sont donc hors de
portee d'un echec de l'interpreteur : n'importe quel imprevu retombe sur la
branche par defaut du .bat, qui DEMARRE le serveur. Et logx_serveur.py refait
de toute facon la meme sonde pour son propre compte : ce pre-controle peut
echouer entierement sans rien casser.

Un lancement normal (port libre) coute une sonde instantanee : voir
logx_singleton.probe, dont tous les chemins sont bornes.

Sortie texte en ASCII strict, comme logx_singleton : elle s'affiche dans une
console Windows dont la page de code n'est pas previsible.

PAS DANS logx.spec, ET C'EST VOULU. Ce module ne sert qu'au lancement depuis
les sources (le .bat). LogXAI.exe ne l'appelle jamais : une fois fige, c'est
logx_serveur.py lui-meme qui sonde le port et affiche le meme message par son
propre chemin. L'ajouter aux hiddenimports embarquerait du code mort dans
l'executable.
"""
import os
import sys
import time

import logx_singleton
from logx_version import APP_VERSION
from logx_utils import PORT

# Codes de sortie, nommes pour que le .bat et les tests parlent de la meme
# chose (un litteral 2 seme dans trois fichiers finit toujours par diverger).
DEMARRER = 0
OUVRIR_SEULEMENT = 10
VERSION_DIFFERENTE = 11
PORT_OCCUPE = 12
PAS_DEMARRE = 13

# Delai d'attente du demarrage, en secondes. Genereux a dessein : le cout d'un
# delai trop court est une FAUSSE alerte (« le serveur n'a pas demarre » alors
# qu'il arrivait), et celui d'un delai trop long est quelques secondes de
# patience dans le cas deja perdu. Mesure sur ce poste : le serveur repond en
# ~4 s a froid ; un antivirus qui inspecte l'interpreteur, ou un disque
# reseau, peuvent tripler ce chiffre.
DELAI_DEMARRAGE_S = 40.0

# Age maximal du journal d'erreurs pour qu'on le juge lie A CE demarrage.
# Sans cette borne on afficherait la panne de la semaine derniere comme cause
# du probleme du jour -- un artefact perime lu comme s'il etait frais.
AGE_MAX_JOURNAL_S = 180


def decider(instance, version_locale=APP_VERSION, port=PORT):
    """Traduit un verdict de probe() en (code_de_sortie, message_a_afficher).

    Separe de main() pour etre testable sans reseau ni process : c'est cette
    fonction qui porte la regle « meme version -> on ouvre, version differente
    -> on refuse d'ouvrir ».
    """
    etat = instance['state']

    if etat == logx_singleton.LOGX:
        version = instance.get('version') or None
        # Version non communiquee = instance anterieure au champ app_version,
        # donc forcement plus ancienne que ce dossier. La traiter comme « meme
        # version » ouvrirait le navigateur sur du vieux code en silence :
        # exactement le defaut qu'on corrige. Dans le doute, on avertit.
        if version and version == version_locale:
            return OUVRIR_SEULEMENT, ''
        return VERSION_DIFFERENTE, logx_singleton.message_deja_lance(
            port, version, ouvre_navigateur=False,
            version_locale=version_locale)

    if etat == logx_singleton.OTHER:
        return PORT_OCCUPE, logx_singleton.message_port_occupe(
            port, instance.get('detail', ''))

    if etat == logx_singleton.SHARED:
        # Avertissement, pas un refus : le serveur demarre et repond bien sur
        # les adresses qu'il annonce (mesure faite dans la sonde elle-meme).
        return DEMARRER, logx_singleton.message_port_partage(
            port, instance.get('detail', ''))

    return DEMARRER, ''


def journal_erreurs_frais(maintenant=None, age_max=AGE_MAX_JOURNAL_S):
    """Les dernieres lignes de errors.log SI elles datent de ce demarrage.

    Retourne '' si le fichier n'existe pas, est trop vieux, ou est illisible.
    Le filtre sur l'age est le coeur de la fonction : un journal d'erreurs
    n'est pas efface entre deux lancements, donc l'afficher sans regarder sa
    date designerait une panne ancienne comme la cause du probleme du jour.
    """
    try:
        import logx_errorlog
        chemin = logx_errorlog.log_path()
        age = (maintenant or time.time()) - os.path.getmtime(chemin)
        if age > age_max:
            return ''
        with open(chemin, 'r', encoding='utf-8', errors='replace') as f:
            lignes = f.readlines()
    except Exception:
        # Journal absent ou illisible : ce n'est pas une erreur en soi, le
        # message principal se suffit. Ne surtout pas faire echouer le
        # diagnostic parce que le diagnostic lui-meme a rate.
        return ''
    return _en_ascii(''.join(lignes[-15:]).rstrip())


def _en_ascii(texte):
    """Replie un texte quelconque en ASCII pur (e accent aigu -> e).

    TROUVE PAR LA SUITE DE TESTS, pas par relecture. Tout le reste de ce
    module est ecrit en ASCII a la main, mais ce texte-ci vient d'ailleurs :
    c'est la fin de errors.log, donc une trace Python dont les messages et les
    chemins de fichiers contiennent des accents. Le message de diagnostic
    redevenait donc mojibake dans la console Windows -- precisement au moment
    ou l'utilisateur a besoin de le lire.

    NFKD separe chaque accent de sa lettre ; on RETIRE alors explicitement les
    marques combinantes, avant d'encoder. Les jeter par `errors='replace'` ne
    marcherait pas : la marque n'etant pas ASCII, elle deviendrait '?' et
    « operateur » ressortait « ope?rateur » (mesure, pas suppose). Ce qui n'a
    aucun equivalent latin (ideogrammes...) devient '?', jamais un octet
    illisible.
    """
    import unicodedata
    decompose = unicodedata.normalize('NFKD', texte)
    sans_accent = ''.join(c for c in decompose if not unicodedata.combining(c))
    return sans_accent.encode('ascii', 'replace').decode('ascii')


def message_pas_demarre(port, delai, journal=''):
    """Le serveur a ete lance mais n'a jamais repondu. ASCII strict."""
    lignes = [
        logx_singleton._LIGNE,
        '  Le serveur n a pas repondu apres %d secondes.' % round(delai),
        '',
        '  Aucune page n a ete ouverte : elle afficherait "impossible de se',
        '  connecter" sans expliquer pourquoi.',
        '',
        '  La cause est ecrite dans la fenetre "LogX Serveur", qui est',
        '  MINIMISEE dans la barre des taches : ouvre-la, le message y est.',
        '  Causes les plus frequentes : le port %d vient d etre pris par un' % port,
        '  autre programme, ou Python a manque un fichier du dossier.',
    ]
    if journal:
        lignes += ['', '  Dernieres lignes du journal d erreurs :', '']
        lignes += ['    ' + l for l in journal.splitlines()]
    lignes.append(logx_singleton._LIGNE)
    return '\n'.join(lignes)


def attendre(delai_max=DELAI_DEMARRAGE_S, pas=0.5, port=PORT,
             version_locale=APP_VERSION, horloge=time.monotonic,
             dormir=time.sleep):
    """Le serveur qu'on vient de lancer repond-il ? Retourne (code, message).

    Sonde SANS JAMAIS SE LIER AU PORT (logx_singleton.sonde_sans_bind) : voir
    sa docstring, un bind de test pendant que le serveur cherche a se lier lui
    volerait le port et ferait echouer le demarrage meme -- l'attente
    provoquerait la panne qu'elle surveille.

    horloge/dormir sont injectables pour que les tests n'attendent pas
    reellement 40 secondes.
    """
    debut = horloge()
    while True:
        version = logx_singleton.sonde_sans_bind(port)
        if version is not None:
            if version and version == version_locale:
                return OUVRIR_SEULEMENT, ''
            # Il repond, mais ce n'est pas la version de ce dossier : le
            # serveur qu'on vient de lancer s'est efface devant une instance
            # deja en place (course entre deux lancements). Ne rien ouvrir.
            return VERSION_DIFFERENTE, logx_singleton.message_deja_lance(
                port, version or None, ouvre_navigateur=False,
                version_locale=version_locale)
        ecoule = horloge() - debut
        if ecoule >= delai_max:
            return PAS_DEMARRE, message_pas_demarre(
                port, ecoule, journal_erreurs_frais())
        dormir(pas)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    # PORT relu ici (et non pris dans les valeurs par defaut, figees a
    # l'import) : les tests peuvent ainsi viser un port ephemere.
    if '--attendre' in argv:
        code, message = attendre(port=PORT)
    else:
        code, message = decider(logx_singleton.probe(PORT), port=PORT)
    if message:
        print(message)
    return code


if __name__ == '__main__':
    sys.exit(main())
