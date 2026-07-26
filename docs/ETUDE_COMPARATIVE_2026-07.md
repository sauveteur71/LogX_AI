# LogX AI face aux autres logiciels de concours

*Juillet 2026 — état des lieux après l'audit de la v0.9-beta6*

## Comment cette étude a été faite

Deux sources ont été croisées : une recherche sur la documentation officielle des
concurrents (juillet 2026), et une analyse du dépôt menée par la passe d'audit — qui a
lu le guide utilisateur, les 73 modules et le code d'export avant de conclure.

Le croisement a corrigé **deux erreurs** de ma première rédaction, que je signale parce
qu'elles allaient dans le sens de la complaisance :

- j'avais compté l'**export Cabrillo** comme acquis parce que la fonction existe. Elle
  existe, mais elle produit un fichier que les robots de réception peuvent refuser. Voir
  plus bas — c'est un des manques les plus sérieux de la liste.
- j'avais **entièrement raté l'opération au clavier**, qui est probablement le premier
  écart à combler.

Ce qui n'a toujours pas été fait : aucun de ces logiciels n'a été installé ni utilisé en
concours. On compare des fonctionnalités, pas des sensations d'opérateur.

## Le paysage

**N1MM Logger+** — la référence. Gratuit, Windows uniquement, HF avant tout, vingt ans
d'existence. Couvre « tous les grands concours HF et beaucoup de petits ».

**DXLog.net** — moderne, orienté Europe, héritier de la lignée Win-Test. Fort en SO2R,
couvre aussi les concours VHF RSGB. Développement actif en 2026.

**Tucnak** — le logiciel THF européen. Multiplateforme, libre, EDI région 1, ON4KST
intégré, rotors Hamlib. Le concurrent le plus direct sur le terrain VHF français.

**Win-Test** — commercial, très implanté en multi-opérateur européen.

**Wavelog / Cloudlog** — carnets web auto-hébergés. Même architecture que LogX AI, mais
**ce ne sont pas des logiciels de concours** : ni saisie temps réel, ni scoring.

## Ce qui est déjà au niveau — et qu'il ne faut pas refaire

L'audit a inventorié ce qui existe. Plusieurs points que je croyais à combler sont en
réalité au niveau des concurrents, voire au-dessus :

- **Super Check Partial + N+1** : fusion calldb / archives / log actif, import
  MASTER.SCP (~45 000 indicatifs) et Call History N1MM par concours, vérification
  Damerau-Levenshtein. Au niveau de N1MM et Win-Test.
- **ESM** (Enter Sends Message), calqué sur N1MM.
- **Serveur de numéros de série** par bande et par portée concours+année, côté serveur.
  C'est l'équivalent du *serial number server* de N1MM, et c'est la difficulté cachée du
  multi-poste — elle est déjà résolue.
- **Règle des 10 minutes** multi-single, que beaucoup de loggers n'ont pas.
- **Export EDI REG1TEST** : un fichier par bande, en-tête complet. Au niveau de
  DXLog/Win-Test sur les concours THF, c'est-à-dire le cœur de cible REF.
- **Vérificateur de log avant soumission** avec correction en place — Win-Test et DXLog
  n'ont pas d'équivalent aussi guidé.
- **Pilotage matériel** : 4 backends CAT, 3 familles d'amplis, rotor. La couverture
  ampli dépasse celle de N1MM.
- **Enregistrement audio par QSO**, équivalent du QSO recording de N1MM.

Et ce que **personne d'autre ne fait** : l'assistant IA branché sur le log et le
règlement en cours (la recherche ne trouve aucun équivalent grand public — l'IA en radio
reste au stade des promesses dans la presse 2026), l'interface navigateur qui rend le
multi-poste gratuit et multiplateforme là où N1MM est Windows seul, les programmes
d'activation intégrés avec 415 000 références embarquées, le relais de mise à jour par
réseau local, l'écran mural, le décodeur CW dans le navigateur, et 8 langues d'interface.

## Les manques réels

Classés par ce qu'ils coûtent, pas par leur difficulté.

> **État au 27 juillet 2026.** Cinq de ces huit points ont été traités dans la
> nuit du 26 au 27 juillet. Les descriptions ci-dessous sont conservées telles
> qu'elles étaient au moment du constat — c'est ce qui rend la correction
> lisible —, avec l'état réel en tête de chaque section.
>
> Reste à faire : le **band map Search & Pounce** (6), le **RTTY** (7), le
> **SO2R** (8), et le volet **WinKeyer matériel** du point 3, seul capable de
> couvrir Icom et Yaesu.

### 1. L'opération au clavier — ✅ FAIT (commit 87d6c6d)

C'est la promesse commune de N1MM, Win-Test et DXLog : **tout faire sans quitter le
clavier**. F1 à F8 pour les macros, Tab entre les champs, Ctrl+W pour effacer.

Dans LogX AI, le gestionnaire clavier ne traite que F9, Échap, `?`, Ctrl+Z et Ctrl+F.
Les 8 macros CW et les 4 emplacements du keyer vocal **ne se déclenchent qu'au clic**.
Le guide l'admet déjà noir sur blanc (§8.1).

Pourquoi c'est le premier de la liste : c'est la différence entre 60 et 120 QSO/h, et
c'est ce qu'un contester teste dans les cinq premières minutes. S'il doit viser un bouton
à la souris, il referme le logiciel. Le reste de l'ergonomie de saisie est pourtant déjà
excellent — ESM, autocomplétion, focus qui revient sur l'indicatif. Il manque
l'interception des touches.

### 2. Cabrillo réellement soumissible — ✅ FAIT (commits 1c7ae46 et ed97c38)

C'est l'argument le plus cité en faveur de N1MM : *« un log presque toujours parfait et
prêt à soumettre »*. Les robots de réception (CQ WW, WPX, ARRL, IARU) refusent ou
déclassent en *checklog* un fichier dont l'en-tête ou l'échange ne colle pas.

Deux chemins d'export, deux problèmes distincts :

- **Côté navigateur** : les lignes `CATEGORY-*` ne sont émises que pour ARRL Field Day.
  Pour CQ WW, WPX, ARRL DX, IARU HF, WAE et CDF HF, il manque `CATEGORY-OPERATOR`,
  `ASSISTED`, `BAND`, `MODE`, `POWER`, `TRANSMITTER`. Plus grave : la ligne QSO n'émet
  que les numéros, **sans le RST**. Un CQ WW attend `59 14`, LogX AI écrit `001`.
- **Côté serveur** : l'en-tête utilise une clé `cabrillo_name` qui n'existe dans
  **aucune** des 40 définitions de concours. Le fichier porte donc `CONTEST: REF_CDF_HF_SSB`
  au lieu du nom officiel. Et le locator est ajouté à l'échange même sur les concours HF,
  ce qui en casse le format.

Un week-end entier de trafic peut être déclassé pour une ligne d'en-tête. C'est le moment
précis où la confiance dans un logiciel se gagne ou se perd. *(L'export EDI, lui, est
irréprochable.)*

### 3. Manipulation CW — ⚠️ PARTIELLEMENT FAIT (commit 9259953)

Plus sérieux que je ne l'avais écrit. Le CW n'existe qu'en TCI et rigctld. Le mode
**« Natif (recommandé) »** — celui que la page CONFIG pousse par défaut pour Icom, Yaesu,
Kenwood, Elecraft et Xiegu — répond explicitement *« Envoi CW non disponible en mode
Natif »*. En mode natif, ESM se contente de copier le texte dans le presse-papier.

Sans manipulation, il n'y a pas de concours CW possible : Coupe du REF CW, IARU, Marconi
Memorial, CQ WW CW. N1MM, Win-Test et DXLog gèrent tous le **WinKeyer K1EL**, standard de
fait du contest CW, avec une régularité que les commandes CAT n'atteignent pas.

À noter : la voie Icom CI-V est un cul-de-sac, Icom ne publiant pas de commande d'envoi de
texte CW. Le WinKeyer est donc la vraie réponse, avec la commande `KY` en bonus pour
Kenwood et Elecraft.

**Fait :** la commande `KY` est branchée en mode Natif pour **Kenwood et Elecraft**. Icom
reste sans manipulation native (CI-V n'a pas la commande) et Yaesu est volontairement
écarté — sa commande équivalente n'a pas la même signification selon les modèles, et
l'envoyer à l'aveugle mettrait n'importe quoi sur l'air. Le **WinKeyer matériel**, qui
couvrirait ces deux marques, reste à faire. Aucune radio n'a été branchée : les trames
sont vérifiées octet par octet contre la documentation constructeur, pas sur l'air.

### 4. Support des transverters — ✅ FAIT (commit 06a1be3)

Zéro occurrence dans tout le dépôt. Sur 1296, 2320, 5760, 10 GHz et au-delà, la radio
affiche la FI et non la fréquence réelle : sans table d'offsets, le CAT choisit la
mauvaise bande, la fréquence loguée est fausse et le fichier EDI part avec une bande
erronée.

N1MM gère les offsets jusqu'à 241 GHz. Or les bandes jusqu'à 47 GHz sont **déjà
déclarées partout** dans LogX AI (CONFIG, band map, EDI) : il ne manque que la table et
son application. Et le public concerné — Rallye des Points Hauts, National THF, F8TD SHF,
Challenge THF — est exactement celui que LogX AI vise.

### 5. Keyer vocal vers la radio — ✅ FAIT (commit 2d762d1)

`voicePlay()` fait un simple `new Audio().play()` : sortie par défaut du navigateur,
aucune sélection de périphérique, aucun PTT. Les WAV vivent dans le navigateur, donc
perdus en changeant de poste. Le guide l'admet (§6.4).

Un concours SSB de 24 h détruit la voix ; le DVK est ce qui permet de tenir. Sans lui,
l'ESM ne sert qu'en CW. Toute la plomberie existe déjà — le PTT est disponible dans les
trois modes CAT, et le module keyer vocal sait sélectionner un périphérique de sortie.

### 6. Band map Search & Pounce — partiel, effort moyen

Le band map ne lit que le cluster. Il fait déjà très bien le reste (filtrage par
fréquence réelle, étoile sur les nouveaux multiplicateurs, stations faites barrées, QSY au
clic, bandscope, détachable). Il manque la moitié **« ce que j'ai entendu moi-même »** et
la navigation clavier de spot en spot.

Le S&P représente facilement la moitié des QSO d'un mono-opérateur, et une station
entendue mais spottée par personne est aujourd'hui perdue.

### 7. RTTY — manquant, effort important

N1MM s'interface avec MMTTY, MMVARI et Fldigi, jusqu'à 4 fenêtres de décodage. LogX AI
couvre proprement FT8/FT4 via WSJT-X, mais le RTTY n'existe que comme étiquette de mode.

À relativiser : **aucun concours REF n'est en RTTY**. C'est un élargissement de public
plus qu'un manque pour l'utilisateur type, et c'est l'effort le plus lourd de la liste.

### 8. SO2R — fondations présentes, mode absent, effort important

Le module CAT contient déjà un gestionnaire multi-radios que le code décrit lui-même
comme « la brique de base d'un futur mode SO2R », et l'allocation des numéros de série est
déjà centralisée — c'est la difficulté cachée du SO2R, elle est réglée. Il manque la
couche opération : second band map, focus TX, commutation audio, raccourcis.

C'est le manque le plus spectaculaire sur le papier, et **le seul de cette liste où
l'écart relève du prestige plutôt que de l'usage** pour le public francophone
REF / IARU / activations que LogX AI vise. À faire en dernier.

## Ce que je recommanderais

*(Section rédigée avant les travaux ; l'ordre a été suivi. Les cinq premiers
points sont faits, sauf le volet WinKeyer matériel du point 5.)*

**D'abord, parce que c'est peu de travail pour beaucoup d'effet :**

1. **Les touches F1-F8.** Effort faible, et c'est ce que le contester teste en premier.
2. **Les transverters.** Effort faible, et ça sert précisément la cible THF.
3. **Le keyer vocal vers la radio.** Toute la plomberie existe déjà.

**Ensuite, parce que c'est là que la confiance se joue :**

4. **La conformité Cabrillo.** Un log déclassé pour une ligne d'en-tête, et l'utilisateur
   ne revient pas.
5. **Le WinKeyer**, qui débloque les concours CW dans le mode que la config recommande.

**En dernier :** le band map S&P, puis le RTTY, puis le SO2R.

**Ce sur quoi creuser l'écart :** l'assistant IA, le multi-poste sans installation et les
programmes d'activation. Personne d'autre ne les a, et deux d'entre eux découlent d'un
choix d'architecture que les concurrents ne peuvent pas copier sans tout réécrire.

## Réserve

Cette étude compare des fonctionnalités déclarées. Elle ne dit rien de la vitesse de
saisie en pile-up, de la lisibilité à 3 h du matin, ni de ce qui se passe quand le réseau
tombe en plein concours. Ces réponses-là ne viendront que du terrain — c'est un
bêta-testeur, pas une grille de comparaison, qui a déclenché la refonte de PROPAGATION.
