# Connecter sa radio via microHAM à LogX AI — marche à suivre

Ce guide s'adresse à un opérateur utilisant une interface microHAM
(microKEYER, microKEYER III, MK2R+, StationMaster, Digi Keyer...) qui
n'arrive pas à faire piloter sa radio par LogX AI en mode CAT natif.

## Pourquoi ça ne marche pas tout de suite

Une interface microHAM n'est **pas** un simple câble : c'est un boîtier USB
qui expose un ou plusieurs **ports COM virtuels** à Windows. Le logiciel qui
crée et gère ces ports — **microHAM Router** (aussi appelé *USB Device
Router*) — doit tourner et être configuré **avant** que LogX AI (ou tout
autre logiciel : WSJT-X, N1MM, etc.) puisse s'y connecter. Sans ça, le port
COM soit n'existe pas encore, soit répond mais ne parle à aucune radio.

## Étape par étape

1. **Lancer microHAM Router** (ou *USB Device Router* selon le modèle
   d'interface) et vérifier qu'il détecte bien le boîtier microHAM branché
   en USB.
2. **Dans microHAM Router**, sélectionner la bonne radio (marque + modèle)
   et vérifier que le statut affiche une liaison active avec la radio
   (fréquence/mode qui remontent dans le Router lui-même).
3. **Noter le port COM virtuel** que le Router assigne pour le CAT — il est
   affiché dans l'interface du Router. C'est CE port qu'il faut choisir
   dans LogX AI, **pas forcément** celui utilisé par un autre logiciel
   (WSJT-X par exemple), s'il y a plusieurs ports virtuels.
4. **Fermer tout autre logiciel** qui pourrait déjà avoir ce port ouvert
   (un autre logbook, un test précédent resté ouvert...). Un port série ne
   peut être ouvert que par un seul programme à la fois.
5. **Dans LogX AI → CONFIG → 5. Radio (CAT)** :
   - Mode de pilotage : **Natif**
   - Marque / Modèle : la marque et le modèle réels de la radio (pas de
     "microHAM" dans cette liste — microHAM est transparent, LogX parle
     directement au protocole natif de la radio à travers lui)
   - Port série : rafraîchir la liste (🔄) et choisir le port COM virtuel
     noté à l'étape 3
   - Vitesse (bauds) : laisser la valeur proposée par défaut, sauf réglage
     particulier fait sur la radio elle-même (menu CAT RATE)
6. **Cliquer sur "🔍 Auto-détecter"** si la marque/modèle exacts ne sont pas
   certains, ou sur "🔌 Tester la connexion" pour vérifier le réglage
   choisi. Le message d'erreur (s'il y en a un) indique maintenant
   explicitement si le port est déjà pris par un autre logiciel ou s'il
   n'existe pas/n'est pas branché — plus la même chose qu'un message
   Windows brut illisible.

## Cas particulier : radio CAT binaire (FT-817/818/857/897/847/100)

Ces Yaesu utilisent un protocole binaire 5 octets que le pilotage NATIF de
LogX ne parle pas (ce n'est pas spécifique à microHAM). Passer par le mode
**"Hamlib rigctld"** dans LogX à la place, avec `rigctld` lancé séparément
sur le port COM microHAM correspondant.

## Si ça ne fonctionne toujours pas

- Vérifier dans le Gestionnaire de périphériques Windows que le port COM
  choisi existe bien et n'affiche pas de point d'exclamation (pilote
  manquant).
- Redémarrer microHAM Router après tout changement de configuration —
  certains changements ne sont pas pris en compte à chaud.
- Essayer un autre logiciel (ex. un terminal série basique, ou même
  WSJT-X) sur ce même port pour isoler si le problème vient de microHAM
  Router ou de LogX AI spécifiquement.
