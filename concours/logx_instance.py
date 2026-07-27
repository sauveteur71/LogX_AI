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
import sys

import logx_singleton
from logx_version import APP_VERSION
from logx_utils import PORT

# Codes de sortie, nommes pour que le .bat et les tests parlent de la meme
# chose (un litteral 2 seme dans trois fichiers finit toujours par diverger).
DEMARRER = 0
OUVRIR_SEULEMENT = 10
VERSION_DIFFERENTE = 11
PORT_OCCUPE = 12


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


def main():
    # PORT relu ici (et non pris dans les valeurs par defaut de decider, figees
    # a l'import) : les tests peuvent ainsi viser un port ephemere.
    code, message = decider(logx_singleton.probe(PORT), port=PORT)
    if message:
        print(message)
    return code


if __name__ == '__main__':
    sys.exit(main())
