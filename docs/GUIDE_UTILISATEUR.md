# Guide utilisateur — LogX AI

> **À maintenir à jour.** Ce document décrit le logiciel tel qu'il se comporte réellement. Chaque fois qu'une fonctionnalité change, est ajoutée ou retirée, mettez à jour la section concernée dans la même session de travail — ne laissez jamais ce guide dériver du code. La dernière mise à jour est notée en bas de fichier.

## Sommaire

1. [Qu'est-ce que LogX AI ?](#1-quest-ce-que-logx-ai-)
2. [Installation et premier lancement](#2-installation-et-premier-lancement)
3. [Prise en main en 5 minutes](#3-prise-en-main-en-5-minutes)
4. [Les quatre modes d'utilisation](#4-les-quatre-modes-dutilisation)
5. [Configurer sa station : le hub de catégories](#5-configurer-sa-station--le-hub-de-catégories)
6. [Le logbook au quotidien](#6-le-logbook-au-quotidien)
7. [Faire un concours de A à Z](#7-faire-un-concours-de-a-à-z)
8. [Piloter sa radio et son matériel](#8-piloter-sa-radio-et-son-matériel)
9. [Cartes, propagation, chasse, EME et écoute à distance](#9-cartes-propagation-chasse-eme-et-écoute-à-distance)
10. [Activations POTA, SOTA, WWFF, IOTA, WCA](#10-activations-pota-sota-wwff-iota-wca)
11. [Multi-poste, expédition, radioclub et écran mural](#11-multi-poste-expédition-radioclub-et-écran-mural)
12. [Diplômes, QSL et historique à vie](#12-diplômes-qsl-et-historique-à-vie)
13. [Le copilote IA](#13-le-copilote-ia)
14. [Import, export et vos données](#14-import-export-et-vos-données)
15. [Dépannage rapide](#15-dépannage-rapide)

---

## 1. Qu'est-ce que LogX AI ?

LogX AI est un logiciel de journal de trafic (logbook) en français qui couvre trois usages dans une seule interface : le trafic courant et la chasse au DX, les concours (règlement, échange, score et multiplicateurs calculés en direct) et les expéditions ou activations de programmes comme POTA, SOTA, IOTA, WWFF, les phares (ARLHS) ou les châteaux (WCA).

Son fonctionnement le distingue des logbooks « en ligne » : un petit serveur tourne sur votre propre PC, et vous utilisez l'application dans votre navigateur habituel. Vos QSO, votre configuration et vos archives restent chez vous, dans un dossier de votre ordinateur. C'est la philosophie du logiciel : rien ne quitte votre poste sans un réglage explicite de votre part (envoi d'un log, synchronisation cloud, assistant IA...).

Comme l'interface est une simple page web servie localement, tout appareil connecté au même réseau WiFi peut l'ouvrir : les autres opérateurs d'un concours de club, une tablette ou un téléphone dans la station, sans rien installer sur ces machines.

Enfin, un assistant IA optionnel peut lire les règlements, suggérer des cibles et répondre à vos questions. Il nécessite une clé API souscrite auprès d'un fournisseur d'IA (catégorie **🤖 15. Assistant IA** de la configuration) et reste entièrement facultatif : le logiciel est complet sans lui.

L'interface est disponible en **huit langues** (français, anglais, allemand, espagnol, italien, portugais, néerlandais, polonais) via le sélecteur de langue en haut de chaque page — le vocabulaire radioamateur est respecté dans chacune, et la langue choisie s'impose aussi aux réponses du copilote IA.

## 2. Installation et premier lancement

Ce chapitre vous amène d'un ordinateur vierge à l'application ouverte dans votre navigateur, et vous indique où vivent vos données — ce qu'il faut savoir avant le premier QSO pour ne jamais rien perdre.

### L'application autonome Windows (recommandée)

Le plus simple est l'exécutable autonome `LogXAI.exe` (environ 35 Mo, dossier `dist`). Il ne nécessite ni Python ni aucune installation préalable. Double-cliquez dessus :

1. Une fenêtre noire s'ouvre : c'est le serveur. **Laissez-la ouverte** pendant toute votre session.
2. Après une à deux secondes, votre navigateur s'ouvre automatiquement sur la page de configuration.
3. Pour arrêter LogX AI : fermez la fenêtre noire, ou tapez Ctrl+C dedans.

Un seul PC de la station lance l'application à la fois (le port 8080 n'accepte qu'une instance).

### L'avertissement Windows SmartScreen

Au tout premier lancement, Windows peut afficher « Windows a protégé votre PC » : l'exécutable n'est pas signé numériquement (la signature commerciale est payante), c'est un avertissement normal. Cliquez sur **Informations complémentaires**, puis **Exécuter quand même**. Windows ne redemandera plus.

### Où sont vos données ?

L'exécutable ne modifie jamais son propre dossier. Au premier lancement, LogX AI crée un dossier de données personnel :

| Système | Emplacement |
|---|---|
| Windows | `C:\Users\VOTRE-NOM\AppData\Roaming\LogXAI\` |
| macOS | `~/Library/Application Support/LogXAI/` |
| Linux | `~/.local/share/LogXAI/` |

Tout y est : votre journal de trafic, votre configuration, la base d'indicatifs, les archives. À retenir :

- **Sauvegarder** = copier ce dossier (sur une clé USB, dans votre cloud personnel...).
- **Repartir de zéro** = supprimer ce dossier ; il sera recréé vide au prochain lancement.
- Le fichier des pays DXCC (`cty.dat`) est mis à jour automatiquement à chaque démarrage dès qu'il a plus de 30 jours. Les bases de références d'activation (sommets SOTA, parcs POTA, réserves WWFF, îles IOTA, châteaux WCA) sont de même téléchargées à leur première utilisation puis rafraîchies automatiquement selon la même règle des 30 jours.

### Sur macOS

L'application doit être construite une fois sur un Mac avec le script fourni (voir `INSTALL.md`). Au premier lancement, macOS bloque les applications non signées : faites un clic droit sur l'application puis **Ouvrir** — une seule fois, macOS s'en souviendra.

### Le mode développeur (depuis les sources)

Si Python est installé sur votre poste, vous pouvez lancer LogX AI directement depuis les sources ; la marche à suivre détaillée est dans `INSTALL.md`. Attention à un piège réel : si vous sautez l'installation des dépendances, le programme **démarre normalement** mais perd silencieusement le pilotage radio CAT, le keyer vocal et le calcul EME, sans aucun message d'erreur. Dans ce mode, les données restent dans le dossier du programme (pas dans le dossier de données ci-dessus).

### Ouvrir LogX AI depuis les autres postes du réseau

La fenêtre noire affiche au démarrage toutes les adresses utiles, dont une ligne « Autres postes WiFi » avec l'adresse exacte à saisir (de la forme `http://IP-DU-PC:8080/...`, l'adresse IP de votre PC étant détectée automatiquement). Les autres opérateurs ouvrent simplement cette adresse dans leur navigateur : aucune installation. Le plus pratique : dans le logbook, le bouton **📋 COPIER** copie l'adresse à envoyer aux autres postes.

### Antivirus et lenteur locale

Certains antivirus (Avast avec son « Web Shield », notamment) inspectent même le trafic local et peuvent ajouter jusqu'à 2 secondes par requête. LogX AI mesure lui-même la latence des deux adresses locales possibles et ouvre automatiquement la plus rapide ; au-delà de 400 ms, il affiche un avertissement dans la fenêtre noire. Si vous voyez ce message, reportez-vous au chapitre Dépannage de ce guide.

## 3. Prise en main en 5 minutes

Voici le chemin le plus court entre un LogX AI fraîchement installé et votre premier QSO dans le log. Deux champs obligatoires, un concours si vous en faites un, et vous loguez.

La page **⚙ CONFIG** (ouverte automatiquement au premier lancement) est un hub de cartes cliquables, groupées par thème ; chaque carte ouvre une fenêtre de réglage.

### Étape 1 — Votre identité

Ouvrez la carte **📛 1. Identité** et remplissez :

- **INDICATIF** : votre indicatif.
- **LOCATOR MAIDENHEAD** : 6 caractères, ex. JN15XC. Si vous ne le connaissez pas, le bouton **📍 Sur la carte** vous le donne en cliquant sur votre position. Le format est vérifié pendant la frappe.

Validez avec le bouton **💾 Enregistrer** de la fenêtre.

### Étape 2 — Le concours (si vous en faites un)

En mode **🏆 CONCOURS** (le mode par défaut, voir chapitre 4), ouvrez la carte **🏆 3. Sélection** et choisissez votre concours : les dates, bandes et modes se pré-remplissent depuis le règlement. En mode logbook simple ou expédition, cette étape est sautée.

### Étape 3 — Lancer le logbook

Cliquez sur le grand bouton **🚀 TOUT EST BON — LOGGER** en bas de page (ou **🚀 COMMENCER À LOGGER** dans le panneau **📊 Résumé ▸**). La configuration est sauvegardée et le logbook s'ouvre. Variante : **🗺️ Ouvrir la carte IA** pour démarrer sur la carte.

S'il manque quelque chose, une alerte « ⚠️ Configuration incomplète » liste précisément les champs à compléter (indicatif, locator valide, concours sélectionné, dates cohérentes, au moins une bande et un mode actifs). À savoir : le bouton **💾 SAUVEGARDER** de l'en-tête enregistre sans rien vérifier — seul le lancement contrôle que tout est prêt.

### Étape 4 — Le premier QSO

Si votre indicatif et votre locator sont connus, le logbook démarre directement. Sinon, une fenêtre « ⚡ LOGBOOK MULTI-OP » vous demande le minimum : indicatif, locator (bouton **📍 GPS**), votre identifiant opérateur et, en concours, le concours — avec un encart **⏱ HORAIRE DU CONCOURS** rappelant début, fin, durée et adresse d'envoi du log. Cliquez **DÉMARRER LA SAISIE ▶**.

Ensuite : tapez l'indicatif de votre correspondant, ajustez les RST (et le numéro ou le locator selon le mode), puis validez avec **Entrée** — le QSO est dans le log.

### Les raccourcis essentiels

| Touche | Action |
|---|---|
| Entrée | Valider le QSO (depuis n'importe quel champ) |
| F9 | Valider le QSO (depuis n'importe où) |
| Échap | Fermer une fenêtre ou une liste de suggestions |
| ↑ / ↓ | Naviguer dans les suggestions d'indicatifs |
| Ctrl+Z | Annuler le dernier QSO |
| Ctrl+F | Revenir au champ INDICATIF |
| F1 à F8 | Macros (CQ, échange...) |
| ? | Afficher l'aide des raccourcis |

Pour les habitués de N1MM, un mode ESM (« Enter Sends Message ») optionnel enchaîne appel, échange et enregistrement sur la seule touche Entrée.

## 4. Les quatre modes d'utilisation

Le mode d'utilisation adapte toute l'interface à ce que vous faites réellement : un chasseur de DX n'a pas besoin d'un numéro de série, un radioclub a besoin de 40 boutons d'opérateurs. Vous le choisissez en tête de la page **⚙ CONFIG**, sélecteur **MODE D'UTILISATION**, et vous pouvez en changer à tout moment.

### Les quatre modes

| Mode (libellé exact) | Pour quoi faire | Concours | Opérateurs | Ce que ça change |
|---|---|---|---|---|
| **📋 LOGBOOK SIMPLE — chasse DX / trafic courant, sans concours** | Le trafic de tous les jours | Aucun | 1 | Tout ce qui est lié au score disparaît (bannière score, numéro de série, récap par bande, classement, bouton d'archivage). Bandes et modes librement réglables. Le journal affiché est votre journal personnel **complet**. Un doublon (même indicatif, même bande) n'est ni bloqué ni signalé — recontacter une station au fil des années est normal ; le panneau « Déjà contacté » affiche de toute façon votre historique avec cette station. Suffixes acceptés dans l'indicatif : /P, /M, /MM, /AM, ou préfixe pays (ex. EA/F4GLD). |
| **🏆 CONCOURS — règlement, échange, scoring, multiplicateurs** | Participer à un concours (mode par défaut) | Obligatoire | Jusqu'à 5 | Toutes les fonctions de rythme et de score sont actives. Le logbook n'affiche que les QSO de l'édition en cours du concours (voir la portée ci-dessous). |
| **📡 EXPÉDITION / ACTIVATION — pile-up, multi-poste** | POTA, SOTA, IOTA, WWFF, phares, châteaux, ou toute sortie portable | Optionnel | Jusqu'à 5 | Saisie simplifiée « juste indicatif + RST » pré-activée. La carte **🏝️ 14. Expédition / Activation** permet de choisir le **PROGRAMME** (POTA, SOTA, IOTA, WWFF, ARLHS, WCA — chacun avec son minimum de QSO pour valider) et **MA RÉFÉRENCE ACTIVÉE**, avec vérification du format et, pour POTA, SOTA, WWFF, IOTA et WCA, contrôle de l'existence de la référence dans la vraie base du programme (ARLHS : vérification du format uniquement, sans base embarquée). Le logbook affiche une barre de progression vers la validation et un compteur de contacts parc-à-parc. |
| **🏛️ RADIOCLUB — plusieurs postes, jusqu'à 40 opérateurs** | Concours de club, opérateurs qui se relaient | Obligatoire | Jusqu'à 40 | Section **POSTES RADIO** visible (déclarez les postes physiques du club). Le logbook affiche un bouton par opérateur réel, généré depuis la configuration. |

Deux précisions honnêtes :

- **Passer en 📋 LOGBOOK SIMPLE décoche toutes les bandes et tous les modes.** C'est volontaire, et cela ne se produit qu'au moment du changement : le but est de repartir d'une page blanche plutôt que d'hériter des bandes imposées par votre dernier concours. Recochez ce que vous pratiquez à l'étape des filtres.
- Ce réglage fait partie de la **configuration de la station** : il est partagé par tous les postes du réseau. À l'inverse, le thème jour/nuit et le mode débutant/expert sont des préférences propres à chaque navigateur.

### La portée « concours + année » : une vue filtrée, jamais une perte

C'est le point le plus important à comprendre : **il n'y a qu'un seul journal de trafic**. Chaque QSO logué pendant un concours porte une étiquette invisible « tel concours, telle année ».

- En mode **🏆 CONCOURS**, le logbook n'affiche que les QSO de l'édition active (le même concours l'an dernier est une édition distincte — les scores ne se mélangent pas d'une année sur l'autre).
- Un QSO sans étiquette — import ADIF d'un ancien log, trafic WSJT-X hors concours, votre journal personnel — **ne compte jamais** dans un concours : la carte des multiplicateurs ne sera pas faussement « déjà travaillée » avant votre premier QSO.
- Vos QSO personnels ne sont **pas perdus** quand vous passez en mode concours : ils sont simplement filtrés à l'affichage. Repassez en **📋 LOGBOOK SIMPLE** et le journal complet réapparaît, concours compris.

La barre de statut, sous la navigation, indique en permanence dans quelle vue vous êtes : le nom du concours actif, « aucun concours », ou « logbook simple ».

### Ne pas confondre avec le mode 🎚 DÉBUTANT / EXPERT

C'est un réglage différent, purement d'affichage. Le bouton **🎚 EXPERT** / **🎚 DÉBUTANT** dans l'en-tête de la page **⚙ CONFIG** masque ou révèle les réglages avancés (assistant IA, propagation, clusters, alertes, champs d'export EDI comme le responsable du log ou la section). En mode débutant, ces réglages gardent leurs valeurs par défaut en arrière-plan — rien n'est désactivé, seulement caché. À la première visite, LogX AI choisit débutant si aucun indicatif n'est encore configuré, expert sinon. Exception utile : en mode **📡 EXPÉDITION / ACTIVATION**, le panneau expédition reste accessible même en affichage débutant.

---

## 5. Configurer sa station : le hub de catégories

La page **⚙ CONFIG** rassemble tout le paramétrage de LogX AI en un seul écran : un « hub » de 15 cartes cliquables, regroupées en 7 sections thématiques. Vous ouvrez les cartes dans l'ordre que vous voulez, vous ne remplissez que ce qui vous concerne, et des badges d'état vous montrent d'un coup d'œil ce qui est prêt, incomplet ou simplement laissé de côté — la grande majorité des catégories étant optionnelles.

### 5.1 Vue d'ensemble de la page

En haut de page, vous retrouvez :

- le bouton **💾 SAUVEGARDER** : enregistrement immédiat et « permissif » — il n'exige rien, vous pouvez sauvegarder une configuration à moitié remplie et y revenir plus tard. Un message **✅ ENREGISTRÉ** s'affiche brièvement en confirmation ;
- le bouton **🎚 EXPERT** / **🎚 DÉBUTANT** : en mode débutant, les champs avancés sont masqués pour alléger l'écran. À la première visite, si aucun indicatif n'est encore configuré, la page démarre automatiquement en mode débutant ;
- le bouton de thème **☀️** / **🌙** (jour/nuit), synchronisé entre tous les onglets ouverts du logiciel ;
- la barre de navigation vers les autres pages : **📋 LOGBOOK**, **🗺️ CARTE IA**, **📶 PROPAG**, **🎯 CHASSE**, **🇫🇷 Cartes**, **📅 CALENDRIER**, **📡 WEBSDR**, avec le nom du concours actif rappelé à droite.

Juste en dessous, la barre **MODE D'UTILISATION** conditionne toute la suite : **📋 LOGBOOK SIMPLE** (chasse DX, trafic courant, sans concours), **🏆 CONCOURS** (le mode par défaut), **📡 EXPÉDITION / ACTIVATION** (pile-up, multi-poste) ou **🏛️ RADIOCLUB** (plusieurs postes, jusqu'à 40 opérateurs). Une note contextuelle explique les conséquences du mode choisi. Deux effets à connaître : passer en EXPÉDITION pré-coche la saisie simplifiée, et passer en LOGBOOK SIMPLE décoche toutes les bandes et tous les modes (vous repartez d'une page blanche à régler librement à l'étape FILTRES). En modes SIMPLE et EXPÉDITION, le choix d'un concours est facultatif.

En tête du hub, le bouton **📊 Résumé ▸** ouvre le récapitulatif **📊 RÉSUMÉ DE LA SESSION** : l'état de votre configuration en une page, avec en mode expert la zone **PROMPT SYSTÈME GÉNÉRÉ** (le contexte que l'assistant IA recevra), les boutons **📋 COPIER LE PROMPT** et **💾 SAUVEGARDER CONFIG**, et deux raccourcis : **🚀 COMMENCER À LOGGER** et **🗺️ Ouvrir la carte IA**. Tout en bas du hub, le bouton **🚀 TOUT EST BON — LOGGER** effectue une sauvegarde stricte (voir §5.8) puis vous emmène directement dans le logbook.

Chaque carte ouvre une fenêtre de réglages avec deux boutons : **💾 Enregistrer** (sauvegarde et ferme) et **✕ Fermer** (ferme sans enregistrer, les badges sont alors recalculés).

### 5.2 Les 15 cartes et leurs badges

| Section | Carte | Ce qu'on y règle |
|---|---|---|
| **MA STATION** | **📛 1. Identité** | Indicatif, locator, antennes... |
| | **🧑‍🤝‍🧑 2. Opérateurs** | Multi-op, responsable log |
| **CONCOURS** | **🏆 3. Sélection** | Le concours choisi (ou « Aucun concours choisi » / « Non requis dans ce mode ») |
| | **📅 4. Dates & filtres** | Dates, bandes, modes |
| **MATÉRIEL** | **📻 5. Radio (CAT)** | Natif / TCI / rigctld |
| | **🔋 6. Amplificateur** | Pilotage ampli linéaire |
| | **🧭 7. Rotor** | Pointage d'antenne |
| **RÉSEAU & SAUVEGARDE** | **☁️ 8. Multi-poste & Cloud** | Cloud Sync, réseau ADIF |
| | **💾 9. Sauvegarde auto** | Dossier, intervalle |
| **PROPAGATION & ALERTES** | **📡 10. Sources** | Cluster, RBN, ON4KST... |
| | **🔔 11. Alertes** | DX, spotter, règles perso |
| **APRÈS LE CONCOURS** | **📮 12. QSL & diplômes** | QRZ, eQSL, LoTW, ClubLog... |
| | **🏆 13. Scoreboard & soumission** | Score en direct, envoi du log |
| **SPÉCIAL** | **🏝️ 14. Expédition / Activation** | POTA, SOTA, IOTA, WWFF... |
| | **🤖 15. Assistant IA** | Fournisseur, clé API |

Chaque carte porte un badge d'état :

| Badge | Signification |
|---|---|
| ✅ | Catégorie correctement configurée (ex. Identité : indicatif + locator valide ; Radio/Ampli/Rotor : pilotage « Activé ») |
| ⚠️ | Catégorie remplie mais invalide ou incomplète (ex. indicatif saisi mais locator manquant ou mal formé) |
| ○ | Catégorie non configurée — souvent parfaitement normal, la plupart sont optionnelles |

Quelques particularités : la carte **📡 10. Sources** reste toujours en ○ (elle contient de nombreux interrupteurs indépendants, sans « état unique ») ; **🏆 13. Scoreboard & soumission** aussi (purement optionnelle) ; **🏆 3. Sélection** passe en ✅ dès qu'un concours est choisi *ou* que le mode d'utilisation n'en exige pas ; **📅 4. Dates & filtres** est toujours ✅ en mode simple ; **📮 12. QSL & diplômes** affiche ✅ par défaut, même sans aucun identifiant saisi (elle ne passe en ⚠️ que si CLUB LOG LIVE STREAM est activé avec des identifiants ClubLog incomplets) ; **🏝️ 14. Expédition** n'est évaluée qu'en mode expédition (✅ si un programme est choisi, ⚠️ sinon).

### 5.3 Le détail des réglages, section par section

#### MA STATION

**📛 1. IDENTITÉ DE LA STATION** — Le champ **INDICATIF** est le point de départ : il pré-remplit automatiquement l'indicatif concours, l'opérateur OP1 et le pays. En mode simple, les suffixes /P, /M, /MM, /AM et les préfixes de pays (ex. EA/F4GLD) sont acceptés. **INDICATIF CONCOURS (si différent)** est masqué en mode LOGBOOK SIMPLE et visible dans les trois autres modes (concours, expédition, radioclub). Le **LOCATOR MAIDENHEAD** se saisit à la main ou via le bouton **📍 Sur la carte** (voir §5.5), avec validation en direct du format. Suivent **VILLE / QTH**, puis en mode expert : **ALTITUDE (m)**, **NOM RESPONSABLE LOG**, **INDICATIF RESPONSABLE**, **CLUB / ASSOCIATION**, **CODE POSTAL**, **EMAIL RESPONSABLE** et **SECTION CONCOURS** (SOMB/SOSB/MOMB/MOSB, repris dans l'export EDI). La partie **STATION RADIO** regroupe **PUISSANCE (WATTS)**, **CLASSE PUISSANCE** (QRP, QRP 10W, QRP 15W, LP, HP), **RECORD DX (auto)** (calculé depuis votre log, aucune saisie), **LOG EXTERNE (PONT RÉSEAU)** en mode expert (Net-TEST THF, N1MM Logger+, Log4OM, HamRS, VQLog), **TRANSCEIVER** et **PAYS (code 3 lettres)** (déduit de l'indicatif). La partie **ANTENNES** décrit vos aériens **HF**, **144 MHz**, **432 MHz** et **UHF/SHF**.

**🧑‍🤝‍🧑 2. OPÉRATEURS** — Un tableau POSTE / INDICATIF / PRÉNOM, avec OP1 fixe et les boutons **+ Ajouter un opérateur** / **－ Retirer le dernier**. Le plafond dépend du mode : 1 opérateur en simple, 5 en concours ou expédition, 40 en radioclub. En mode radioclub uniquement, la section **POSTES RADIO** décrit les positions physiques du club (**+ Ajouter un poste** / **－ Retirer le dernier**).

#### CONCOURS

**🏆 3. SÉLECTION DU CONCOURS** est traitée en détail au §5.6.

**📅 4. DATES & BANDES/MODES** — La partie **DATES DU CONCOURS (EXPORT EDI)** contient **DATE DÉBUT (auto ou manuel)**, **DATE FIN** et **HEURE FIN UTC** (qui alimente le compte à rebours du logbook). **MODES** : SSB (activé par défaut), CW, FT8, FT4, JS8, RTTY, PSK, AM, FM, D-STAR. **OPTIONS SPÉCIALES** : QRP, IOTA, SOTA, POTA, PORTABLE /P, MOBILE /M, BEACON, EME, Meteor Scatter, NO-DIGI. Les bandes couvrent tout le spectre : **BANDES VLF / HF** (VLF, 1.8 à 28 MHz, plus le 40 MHz/8 m) et **BANDES VHF / UHF / SHF** (50, 70, 144 et 220 MHz ; 432 MHz à 2.4 GHz ; 3.4 à 47 GHz ; **QO-100** et **Autres SAT**). Le dépliant **🛰️ Satellite actif & liens de suivi** permet de noter le **SATELLITE ACTIF (repère informatif)** (QO-100, ISS, SO-50, AO-91, RS-44…) avec des liens vers AMSAT, Heavens-Above, N2YO et Gpredict.

#### MATÉRIEL

**📻 5. RADIO (PILOTAGE CAT)** — Activez le **PILOTAGE RADIO** puis choisissez le **MODE DE PILOTAGE** : **Natif (recommandé — pas de logiciel externe)**, **TCI (postes SDR — SunSDR/ExpertSDR3 et compatibles)** ou **Hamlib rigctld (avancé — autres marques)**. Le dépliant **📖 Quel mode choisir pour ma radio ?** vous guide : CI-V pour Icom et Xiegu, protocole ASCII pour Yaesu/Kenwood/Elecraft, TCI pour les SDR, rigctld pour les plus de 200 modèles couverts par Hamlib. En natif : **MARQUE** (Icom, Yaesu, Kenwood, Elecraft, Xiegu), **MODÈLE**, **PORT SÉRIE** avec **🔄 Rafraîchir la liste**, **VITESSE (bauds)** et le bouton **🔌 Tester / auto-détecter**. En TCI : **ADRESSE TCI** et **PORT TCI** (50001 par défaut, 40001 pour ExpertSDR2). En rigctld : **ADRESSE RIGCTLD** et **PORT RIGCTLD** (4532). La section **💻 WSJT-X (FT8/FT4 — auto-log)** enregistre automatiquement vos QSO numériques (**AUTO-LOG WSJT-X**, **PORT UDP WSJT-X**, 2237 par défaut). Enfin, la section **🎙️ KEYER VOCAL (phonie — indicatif dit automatiquement)** fait annoncer votre indicatif par une voix de synthèse entièrement hors-ligne, avec passage en émission automatique : choisissez le **PÉRIPHÉRIQUE DE SORTIE** — un câble audio virtuel relié à la radio, « PAS tes enceintes » —, la **VOIX**, la **VITESSE (mots/min)**, et validez avec **🔊 Tester (indicatif fictif)**. Le keyer vocal nécessite que le pilotage radio soit actif.

La **manipulation CW en mode Natif** fonctionne pour **Kenwood et Elecraft** (commande `KY` : le texte part au keyer interne de la radio, à la vitesse réglée sur le poste). Elle reste indisponible pour **Icom** — le protocole CI-V ne publie aucune commande d'envoi de texte CW — et pour **Yaesu**, dont la commande équivalente n'a pas la même signification selon les modèles : l'envoyer à l'aveugle mettrait n'importe quoi sur l'air. Dans ces deux cas, le message vous indique d'utiliser rigctld ou TCI, qui savent manipuler sur toute la gamme.

Les **messages enregistrés avec votre propre voix** (panneau MESSAGES VOCAUX du LOGBOOK, §6.4) empruntent exactement le même chemin : le serveur lève le PTT, joue le message par le périphérique de sortie choisi ci-dessus, puis relâche le PTT en vérifiant qu'il est bien retombé. Ils sont **enregistrés sur le serveur, pas dans le navigateur** : vous les retrouvez donc à l'identique depuis n'importe quel poste du réseau, et ils survivent au vidage du cache. Si vous aviez déjà enregistré des messages dans une version précédente, ils sont repris automatiquement au premier lancement.

La section **📡 TRANSVERTERS (hyperfréquences)** ne concerne que le trafic au-dessus de 1296 MHz. Sur ces bandes, la radio n'émet pas directement : un transverter convertit une bande intermédiaire (**FI**, généralement 144 ou 432 MHz) vers la bande réelle. La radio affiche donc 144,100 MHz pendant que vous trafiquez à 1296,100 — et sans cette déclaration, la bande déduite, le QSO enregistré, le filtre du band map, le QSY au clic sur un spot et le fichier EDI seraient tous faux **au même moment, sans le moindre message d'erreur**. Déclarez une ligne par transverter : **FI (radio)**, **BANDE RÉELLE**, et éventuellement l'**OSCILLATEUR** si votre montage ne fait pas correspondre les fréquences nominales (laissé vide, il se déduit : un 144 → 1296 donne 1152 MHz). Un seul transverter par bande FI peut être actif à la fois — deux montages sur la même FI rendraient la fréquence lue ambiguë (144,100 signifierait 1296,100 *ou* 2320,100), et la sauvegarde est refusée dans ce cas. Vous pouvez en revanche conserver la configuration de plusieurs transverters et n'en activer qu'un, sans avoir à la ressaisir à chaque changement de bande.

**🔋 6. AMPLIFICATEUR HF** — **PILOTAGE AMPLI**, **MARQUE** (**Elecraft (KPA500 / KPA1500)**, **Icom (IC-PW2 / PW-1, CI-V)**, **SPE / Expert (1.3K-FA / 1.5K-FA / 2K-FA)**), **PORT SÉRIE** (indépendant de celui de la radio) avec **🔄 Rafraîchir la liste**, **VITESSE (bauds)** (« 9600 à 38400 selon marque »), **ADRESSE CI-V** (Icom uniquement, AA en sortie d'usine) et **🔌 Tester la connexion**. Une fois configuré, puissance, ROS et défauts de l'ampli s'affichent dans le logbook.

**🧭 7. ROTOR D'ANTENNE** — Le pilotage passe par le logiciel rotctld (Hamlib), qui doit tourner sur votre machine : sans lui, l'option n'a aucun effet (**PILOTAGE ROTOR** est d'ailleurs « Désactivé par défaut »). Renseignez **ADRESSE ROTCTLD** et **PORT ROTCTLD** (4533).

#### RÉSEAU & SAUVEGARDE

**☁️ 8. MULTI-POSTE & CLOUD SYNC** — Deux mécanismes distincts. Le **🌐 RÉSEAU ADIF (N1MM / DXLog / loggers tiers)** échange les QSO en direct avec d'autres logiciels de log sur le réseau local : **MODE** (Désactivé, **Réception seule (importer leurs QSO)**, **Émission seule (leur envoyer nos QSO)**, **Réception + émission**), **PORT UDP** (12060) et **IP CIBLE (émission)**. Le **☁️ CLOUD SYNC (multi-poste, sans compte ni service en ligne)** synchronise plusieurs postes LogX AI via un simple **DOSSIER PARTAGÉ** (Dropbox, Drive, NAS… le même chemin sur tous les postes ; pensez à régler le dossier en « toujours conserver sur cet appareil »), avec **MODE** (**Synchronisation complète (lit + écrit)** ou **Envoi seul (écrit, ne récupère rien)**), **INTERVALLE (min)** et le bouton **☁️ SYNCHRONISER MAINTENANT**. Ne confondez pas avec la sauvegarde : ici les QSO des différents postes se combinent réellement en un seul log.

**💾 9. SAUVEGARDE AUTOMATIQUE** — **DOSSIER DE SAUVEGARDE** (« Copie horodatée (.db + .json + ADIF) ; vide = désactivé ») et **SAUVEGARDE — INTERVALLE (min)** (de 5 à 120 minutes, 15 par défaut).

#### PROPAGATION & ALERTES

**📡 10. SOURCES DE PROPAGATION** — 13 interrupteurs indépendants :

| Source | Par défaut |
|---|---|
| **Cluster F5LEN**, **DXSummit**, **DXWatch**, **Tropo F5LEN**, **DXMaps**, **HamQTH spots (VHF)**, **HamSpirit (VHF)**, **Telnet DX Spider (HF)** | Activés |
| **ON4KST Chat** | Activé |
| **VOACAP (HF)**, **PSK Reporter**, **Cycle solaire**, **NOAA K-index** | Désactivés |

La section **COMPTE ON4KST CHAT (optionnel)** accueille votre **INDICATIF ON4KST** et **MOT DE PASSE ON4KST** (« Stocké en local uniquement — jamais transmis à l'IA »). L'option **RBN CW (où mon signal est entendu)** est activée par défaut. Ces sources sont des services bénévoles tiers : leur disponibilité ne dépend pas de LogX AI.

**🔔 11. ALERTES PERSONNALISÉES** — Choisissez les **MODES DE PROPAGATION À SURVEILLER** : Troposphérique, Sporadique-E et F2 (ionosphérique) activés par défaut ; Aurore, Meteor Scatter, EME et Ducting maritime au choix. Les **PARAMÈTRES D'ALERTE** règlent **DISTANCE ALERTE DX (KM) — repli** (1200 — c'est un seuil de repli, le logiciel l'ajuste déjà automatiquement par bande), **DISTANCE PROBABLE SPOTTER (KM) — repli** (600), **SON DES ALERTES**, **VOLUME ALERTES (%)**, **RAFRAÎCHISSEMENT AUTO (MIN)**, **PRIORITÉ PRINCIPALE** (Distance (pts/km), Département manquant, DXCC manquant ou Zone manquante) et **FILTRE PRÉFIXE SPOTS**. La zone **🔔 RÈGLES D'ALERTE PERSONNALISÉES** vous permet de créer vos propres déclencheurs — en plus des alertes toujours actives (nouveau multiplicateur, mention de votre indicatif sur ON4KST) : **NOM DE LA RÈGLE**, **PRÉFIXE INDICATIF**, **CONTINENT**, **ZONE CQ**, **BANDE (MHz)**, **STATUT** (Indifférent / Nouveau multiplicateur / Déjà travaillé), **COMMENTAIRE DE SPOT CONTIENT**, puis **➕ AJOUTER LA RÈGLE**. Chaque règle peut être activée ou désactivée individuellement ; elles sont évaluées par le serveur LogX AI lui-même, pas seulement par la page.

#### APRÈS LE CONCOURS

**📮 12. QSL & DIPLÔMES** — Le **🌐 COMPTE QRZ.com** (**IDENTIFIANT QRZ**, **MOT DE PASSE QRZ**) enrichit vos QSO ; le mot de passe est « Stocké côté serveur uniquement — jamais renvoyé au navigateur ni à l'IA ». Limite honnête : les informations détaillées (nom, adresse…) exigent un abonnement XML payant chez QRZ ; sans abonnement, vous obtenez au moins le pays. La partie **📮 QSL & DIPLÔMES (services en ligne)** regroupe les identifiants **eQSL** (envoi ADIF), **LoTW** (« Import des confirmations (pas d'upload : garde TQSL pour publier) » — LogX AI ne remplace pas TQSL), **ClubLog** (email, indicatif, mot de passe, clé API), **QRZCQ** (indicatif, clé API) et **HRDLog** (indicatif, code d'upload — envoi QSO par QSO, qui peut être lent). Les boutons d'action correspondants se trouvent dans le logbook, rubrique **🏅 DIPLÔMES**.

**🏆 13. SCOREBOARD & SOUMISSION** — **SCOREBOARD EN DIRECT** (« Activé — publier le score ») envoie périodiquement votre score au site contestonlinescore.com (**SCOREBOARD — INTERVALLE (min)**, 5 par défaut). La partie **SOUMISSION DU LOG** mémorise l'**URL SOUMISSION LOG** et le **DÉLAI SOUMISSION** (purement informatif : c'est un pense-bête, pas un envoi automatique).

#### SPÉCIAL

**🏝️ 14. EXPÉDITION / ACTIVATION** — La section **🏕️ ACTIVATION (POTA / SOTA / IOTA / WWFF / ARLHS / WCA)** transforme LogX AI en journal d'activation :

| **PROGRAMME** | Minimum de QSO |
|---|---|
| **POTA — Parks on the Air** | 10 |
| **SOTA — Summits on the Air** | 4 |
| **IOTA — Islands on the Air** | 1 |
| **WWFF — Flora & Fauna** | 44 |
| **ARLHS — Lighthouses** | 2 |
| **WCA — World Castles Award** | 50 |

Le champ **MA RÉFÉRENCE ACTIVÉE** propose autocomplétion et validation du format (« POTA : XX-NNNN · SOTA : XX/RR-NNN · IOTA : CC-NNN · WWFF : XXFF-NNNN · ARLHS : XXX-NNN · WCA : X-NNNNN »). Le bloc **🗺️ RÉFÉRENCES À PROXIMITÉ** (**🔍 Chercher autour de moi**, rayon 60 km par défaut) liste les références proches calculées depuis votre locator, sur la base embarquée du logiciel — aucun service tiers n'est consulté. Limite : le message **⚠️ Non disponible pour ce programme** apparaît quand la base ne contient pas de coordonnées GPS, ce qui est le cas du WCA. Pendant l'activation, le logbook affiche votre avancement (X QSO sur le minimum requis), détecte les liaisons Park-to-Park / Summit-to-Summit, et l'export ADIF inclut les champs officiels du programme. La section **🏝️ MODE EXPÉDITION** ajoute : **MODE EXPÉDITION** (« Activé — juste indicatif + RST envoyé/reçu » : saisie ultra-rapide pour le pile-up), **CLUB LOG LIVE STREAM** (« Activé — pousser chaque QSO en temps réel », nécessite vos identifiants ClubLog complets), **AUTO-SPOT DX CLUSTER** (ajoute un bouton **📡 SELF-SPOT** dans le logbook — attention : « ⚠️ Interdit par certains règlements en single-op »), **NŒUD CLUSTER (host : port)** (dxc.ve7cc.net:7300 par défaut), le lien **🖥️ OUVRIR L'ÉCRAN MURAL** (grand écran d'affichage des derniers QSO, utilisable dans tous les modes, avec **ÉCRAN MURAL — CHAMPS À AFFICHER** : Heure, 🏴 Drapeau, Pays, Prénom, Bande, Fréquence, Mode, Report (RST), Opérateur — l'indicatif est toujours affiché) et **📱 CONNECTER UN TÉLÉPHONE / TABLETTE** (adresses du réseau local détectées automatiquement, installation en application via « Ajouter à l'écran d'accueil »).

**🤖 15. ASSISTANT IA** — Choisissez votre **FOURNISSEUR** parmi six : **Claude / Anthropic**, **ChatGPT / OpenAI**, **Gemini / Google**, **Mistral AI / France**, **Grok / xAI**, **DeepSeek** ; puis le **MODÈLE** et votre **CLÉ API** (« 🔒 Stockée localement par fournisseur — jamais partagée » : une clé est mémorisée par fournisseur et restaurée quand vous rebasculez). Point important : sans clé API, tout le logiciel fonctionne normalement — seul le copilote IA est indisponible. La clé s'obtient (souvent moyennant paiement à l'usage) directement chez le fournisseur choisi.

### 5.4 Les profils nommés

La barre **PROFIL** en haut de page permet de mémoriser plusieurs configurations complètes — par exemple « F6KQJ RPH 2026 », « Club 144 » et « Home HF » — et de basculer de l'une à l'autre en deux clics. **💾 Sauvegarder** demande un nom puis capture l'intégralité du formulaire (confirmation **✅ Profil "X" sauvegardé.**) ; **📂 Charger** réapplique tout d'un coup ; **🗑️ Supprimer** demande confirmation. Les profils sont triés alphabétiquement et stockés uniquement dans le navigateur de ce poste : ils ne sont ni synchronisés ni envoyés nulle part — pensez-y si vous changez d'ordinateur.

### 5.5 Le sélecteur de locator sur carte

Si vous ne connaissez pas votre locator Maidenhead, le bouton **📍 Sur la carte** (carte Identité) ouvre l'overlay **📍 Locator sur la carte** : cliquez sur votre emplacement et le locator 6 caractères s'affiche instantanément — le calcul est fait localement, sans aucun service externe. Seul l'affichage du fond de carte (OpenStreetMap) nécessite Internet : hors connexion, un message vous invite à saisir le locator à la main, et une bannière **⚠️ Tuiles de carte indisponibles (openstreetmap.org bloqué ?)** signale le cas où seules les tuiles échouent. Pour vous repérer : le champ « Ville / adresse… » avec **🔍 Chercher** (géocodage OpenStreetMap) ou **🛰️ Ma position** (géolocalisation du navigateur). **✓ Utiliser** reporte le locator dans le formulaire et, si le champ VILLE est vide, tente de le remplir automatiquement. Bonus pratique : la barre **📏 Comparer à un locator distant :** calcule distance en km, azimut en degrés et direction cardinale vers n'importe quel locator, avec le tracé sur la carte — les mêmes formules que celles du logbook. À la saisie manuelle, le champ **LOCATOR MAIDENHEAD** est validé en direct : « 📍 Locator XXnnXX détecté — coordonnées calculées automatiquement » ou « ⚠️ Locator invalide — format attendu : 2 lettres (A-R) + 2 chiffres + 2 lettres optionnelles (A-X), ex. JN15XC ».

### 5.6 Choisir son concours

La carte **🏆 3. SÉLECTION DU CONCOURS** vous évite de configurer bandes, modes et dates à la main : choisir un concours applique automatiquement son règlement.

**Rechercher et choisir.** Le champ **🔍 Rechercher : Field Day, VHF, RPH, CQ WW…** filtre en direct sur le nom, l'organisateur, les bandes, les modes et le barème. Les concours sont groupés dans l'ordre : **REF** (marqués **⭐** et « — Calendrier 2026 officiel »), **Autre FR**, **International**, **Mondial (WA7BNM)** (issu du calendrier mondial externe WA7BNM) et **Autre**. Chaque carte de concours porte un badge de confiance : **✓ RÈGLEMENT SUIVI** (base intégrée, dates et règlement re-vérifiés chaque année), **🤖 IA + RELECTURE** (règlement extrait par l'IA puis validé par relecture humaine) ou **⚠ À CONFIRMER** (concours WA7BNM non vérifié — faites lire le règlement par l'IA avant de vous y fier). Un lien **📄 RÈGLEMENT** ouvre le texte officiel quand il est disponible. À la sélection, bandes et modes sont cochés automatiquement et les dates calculées quand la règle est connue (une bannière les affiche : « Début : … · Fin : … UTC — Modifie manuellement si besoin » ; sinon, on vous invite à les saisir). Attention : changer de concours alors qu'un autre est déjà actif réinitialise bandes, modes et dates — une confirmation explicite vous prévient que vos personnalisations seront perdues.

**Le bouton ✕ Aucun concours** vous ramène à un fonctionnement « sans concours » sans toucher aux bandes et modes déjà cochés — typiquement utile en mode EXPÉDITION/ACTIVATION quand vous ne participez pas (ou plus) à un concours.

**Depuis le calendrier.** Si vous arrivez depuis la page **📅 CALENDRIER** avec un concours pré-choisi, la bannière **🧭 ASSISTANT NOUVEAU CONCOURS** affiche une check-list : concours sélectionné, station configurée (avec lien vers l'étape 1 sinon), dates calculées ou à saisir, et pour un concours WA7BNM un avertissement de contrôle du règlement officiel. Le mode d'utilisation bascule automatiquement de simple vers concours si nécessaire.

**Analyser un règlement par l'IA.** La section **🤖 ANALYSER UN RÈGLEMENT (IA)** ajoute à la base n'importe quel concours absent : collez l'URL du règlement (PDF ou HTML), un nom optionnel, puis **🤖 ANALYSER**. Après 30 à 90 secondes d'analyse, le modal **🤖 PROPOSITION IA — RELECTURE OBLIGATOIRE** s'ouvre — et son titre est à prendre au pied de la lettre : « Rien n'est enregistré tant que tu n'as pas validé. » Vous y trouvez le niveau de confiance de l'IA (HIGH/MEDIUM/LOW), une passe de vérification automatique (restrictions de participation, off-time, multiplicateurs pondérés, QTC, échange, dates, deadline), les avertissements, et chaque champ éditable (nom, organisateur, règle de date, durée, bandes, modes, échange, format de log, deadline, barème…) accompagné de sa citation extraite du règlement — ou du signal « ⚠ aucune citation source — vérifie dans le règlement ». Un aperçu **📅** montre la prochaine occurrence calculée. Validez avec **✓ J'AI RELU — ENREGISTRER LE CONCOURS** (le serveur re-vérifie la définition), ou **✕ Annuler** ; **📄 Ouvrir le règlement** garde le texte source sous les yeux. Une fois validé, le concours rejoint la base et resservira chaque année. Cette fonction nécessite une clé API (carte 15).

**Partager entre stations.** **📤 Exporter mes concours validés** télécharge vos définitions dans un fichier à transmettre à un autre utilisateur ; **📥 Importer un fichier partagé** les intègre après validation, avec un compte rendu détaillé (importés, mis à jour, déjà présents, refusés).

### 5.7 L'aide intégrée : les « ? » et l'assistant 🤖

Plus de 90 champs de la page portent une icône **?** à côté de leur libellé : un clic ouvre une bulle d'explication en français. Ces fiches sont embarquées dans le logiciel — elles fonctionnent 100 % hors-ligne, sans réseau ni clé API.

Pour les questions plus ouvertes, le bouton rond **🤖** en bas à droite ouvre le panneau **🤖 ASSISTANT CONFIGURATION**, avec six questions fréquentes cliquables (différence INDICATIF / INDICATIF CONCOURS, choix du mode d'utilisation, trouver son locator, CAT/TCI/rigctld, Cloud Sync, besoin d'une clé API) et un champ libre « Ta question… ». Son comportement dépend de votre configuration : sans clé API, il répond uniquement à partir des fiches locales (recherche par mots-clés, insensible aux accents) ; avec une clé API, votre question est envoyée au fournisseur d'IA configuré, avec pour consigne de répondre en 2 à 5 phrases maximum, dans un vocabulaire accessible, et sans jamais inventer de champ qui n'existe pas. En cas de panne réseau, il se rabat automatiquement sur les fiches locales.

### 5.8 Les garde-fous : impossible de partir avec une config bancale

LogX AI distingue deux niveaux de sauvegarde. La sauvegarde **silencieuse** (**💾 SAUVEGARDER** en en-tête, **💾 Enregistrer** dans les popups) est volontairement permissive : elle ne bloque jamais votre saisie progressive, vous pouvez enregistrer un travail en cours. La sauvegarde **explicite** (**💾 SAUVEGARDER CONFIG** du Résumé, **🚀 TOUT EST BON — LOGGER**, **🚀 COMMENCER À LOGGER**), elle, effectue une validation complète et refuse de continuer si un élément essentiel manque, avec l'alerte « ⚠️ Configuration incomplète — merci de compléter avant de continuer : » suivie de la liste précise :

| Contrôle bloquant | Condition |
|---|---|
| « INDICATIF (étape MA STATION) » | Toujours exigé |
| « LOCATOR MAIDENHEAD valide, ex. JN15XC (étape MA STATION) » | Toujours exigé (format vérifié) |
| « un CONCOURS sélectionné (étape CONCOURS) » | Seulement si le mode l'exige — pas en LOGBOOK SIMPLE ni en EXPÉDITION |
| « DATE FIN doit être postérieure ou égale à DATE DÉBUT (étape CONCOURS) » | Cohérence des dates |
| « au moins une BANDE active (étape FILTRES) » | Toujours exigé |
| « au moins un MODE actif (étape FILTRES) » | Toujours exigé |

Un contrôle supplémentaire vise le temps réel : si **CLUB LOG LIVE STREAM** est activé alors que vos identifiants ClubLog (email, indicatif, mot de passe, clé API) sont incomplets, la sauvegarde explicite est refusée avec une alerte dédiée — mieux vaut le découvrir avant le concours que pendant.

Enfin, quelques filets de sécurité s'appliquent à chaque sauvegarde : les valeurs numériques aberrantes sont ramenées dans leurs bornes (puissance, intervalles de sauvegarde, de synchronisation et de scoreboard), la liste d'opérateurs est plafonnée selon le mode (1, 5 ou 40), et la configuration est à la fois conservée dans le navigateur et transmise au serveur local. Et si la sauvegarde stricte échoue au moment de cliquer **🚀 TOUT EST BON — LOGGER**, vous restez sur la page CONFIG : le logbook ne s'ouvre jamais sur une configuration invalide.

---

## 6. Le logbook au quotidien — l'écran de saisie détaillé

C'est ici que vous passerez 95 % de votre temps : l'écran **📋 LOGBOOK** réunit la saisie des QSO, la table du log, le score en direct et tous les outils de concours. Ce chapitre décrit chaque champ, chaque bouton et chaque automatisme, dans l'ordre où vous les rencontrez à l'écran.

**Préalable** : cette page a besoin du serveur LogX AI démarré sur votre PC (un écran d'erreur dédié s'affiche si vous ouvrez le fichier directement sans serveur). Au tout premier lancement, un assistant **⚡ LOGBOOK MULTI-OP** vous demande votre indicatif, votre locator (bouton **📍 GPS** pour le calculer automatiquement), votre identifiant d'opérateur et le concours (sélecteur cherchable avec horaires 2026 en UTC et heure locale, et e-mail de soumission). Si votre configuration est déjà complète, le logbook démarre directement.

### 6.1 Le formulaire « ⌨ SAISIE QSO », champ par champ

Le panneau de gauche, titré **⌨ SAISIE QSO**, est conçu pour être piloté au clavier seul : chaque champ valide le QSO avec Entrée, et le focus revient toujours sur l'indicatif après enregistrement.

#### OPÉRATEUR et BANDE (même ligne)

Ces deux sélecteurs partagent le même principe : un bouton qui affiche la valeur courante (flèche ▼), et un clic ouvre une grille de choix. C'est volontaire : afficher en permanence jusqu'à 17 boutons de bande (de 1,8 MHz à 47 GHz) ou 40 boutons d'opérateur serait illisible. Les grilles se referment d'un clic en dehors.

- **OPÉRATEUR** (bouton orange, pour le distinguer des sélecteurs cyan) : la grille liste les indicatifs réellement déclarés dans votre configuration (jusqu'à 40 en mode radioclub) — la couleur d'étiquette propre à chaque opérateur apparaît dans la colonne OP de la table du log et dans le classement des opérateurs. Ce sélecteur est **masqué** si vous opérez seul : catégorie single-op, un seul opérateur configuré, ou mode LOGBOOK SIMPLE.
- **BANDE** : la grille ne propose que les bandes **autorisées par le concours choisi** (ex. IARU VHF = 144 MHz seulement) et cochées dans votre CONFIG. Les libellés sont en longueur d'onde (« 2m », « 70cm », « 23cm », et 160m→10m en HF). Changer de bande pré-remplit la fréquence (fréquence d'appel de la bande, ou fréquence réelle de la radio si le pilotage CAT est actif et déjà dans cette bande), met à jour le numéro envoyé (les séries sont comptées par bande), rafraîchit le **📻 BAND MAP** et remet le focus sur l'indicatif.

#### La barre d'activation (POTA, SOTA, IOTA, WWFF…)

Visible uniquement en mode activation, elle affiche le programme, votre référence, la progression vers le minimum de QSO exigé (POTA 10, SOTA 4, IOTA 1, WWFF 44, ARLHS 2, WCA 50), un badge **✅ VALIDÉE** (ou « encore N »), le compteur de contacts Park-to-Park et une barre de progression. Elle se met à jour toutes les 15 secondes.

#### FRÉQUENCE (MHz)

Champ texte libre (exemple affiché : 144.300). Deux intelligences :

- Taper une fréquence **sélectionne automatiquement la bonne bande** (parmi les bandes autorisées uniquement).
- Si le pilotage CAT est activé, la fréquence **suit la radio en direct** — sauf pendant que vous tapez dans le champ ou après une modification manuelle, pour ne pas écraser un split ou une fréquence annoncée. Un changement de bande réactive le suivi. Le bouton **📻 Radio** (visible seulement avec le CAT actif) force la relecture de la fréquence de la radio ; sans CAT, un message vous invite à saisir la fréquence à la main.

#### MODE

Même principe bouton + grille que la bande. Les modes proposés sont ceux du concours (ex. CQ WW SSB → SSB seul ; ARRL Field Day → SSB/CW/FT8/FT4/RTTY), filtrés par vos réglages de CONFIG. Passer en CW affiche le panneau des macros et le décodeur ; passer en phonie affiche le keyer vocal (voir §6.4).

#### INDICATIF CORRESPONDANT

Le champ le plus assisté du logiciel. La saisie est forcée en majuscules, et dès 2 caractères plusieurs aides se déclenchent :

- **Autocomplétion** (façon « Super Check Partial » de N1MM) : d'abord les stations de votre log courant (tag « 📋 LOG »), puis la base fusionnée du serveur (base d'indicatifs, archives, anciens concours) — par préfixe, puis par fragment n'importe où dans l'indicatif dès 3 caractères. Les stations déjà travaillées lors d'un concours passé remontent en tête avec le tag « ✓ DÉJÀ VU ». Chaque ligne montre le drapeau, l'indicatif, le locator, le département, le pays, et un tag rouge « DUPE » si la station est déjà dans le log sur la bande courante. Navigation ↑/↓, Entrée pour choisir, Échap pour fermer. La sélection pré-remplit le locator et place le curseur directement sur le RST.
- **Alerte doublon** : bandeau rouge « ⚠️ DOUBLON — Ce correspondant est déjà dans le log ! » si l'indicatif est déjà loggé sur la même bande, avec bordure rouge du champ. Désactivée en mode LOGBOOK SIMPLE, où recontacter une station au fil des années est normal.
- **Badge de statut serveur** (calculé par le moteur de score sur le log partagé multi-op) : « ⚠️ DOUBLON sur cette bande » (rouge), « 📈 NOUVEAU MULTIPLICATEUR » (vert), ou « ✔ nouveau · N pts » (cyan).
- **Fiche du correspondant** : interrogation automatique des annuaires en cascade — QRZ.com (uniquement si vous avez configuré vos identifiants), puis HamQTH, puis HamDB. S'affichent le nom, le QTH et le grid (« 👤 · 📍 · 🗺 ») avec la source utilisée ; le locator est pré-rempli s'il était vide. Ces annuaires sont des services tiers, parfois bénévoles : une absence de réponse est possible et sans gravité.
- **Badge pays DXCC** : drapeau, nom du pays en français, continent et zone CQ, reconnus par une table de préfixes embarquée (environ 160 préfixes — les entités les plus exotiques peuvent ne pas être reconnues).
- **Alerte double-bande** : « 📡 Double-bande possible — déjà loggé en 2m ! » quand la station a été faite sur une autre bande mais pas encore sur celle-ci : un contact facile à aller chercher.
- **« Déjà contacté »** : votre historique complet avec cette station, tous concours confondus — « 🌟 » si c'est un nouveau pays ou département à vie, nombre de QSO par bande, nombre de confirmés, date du dernier contact et les 3 QSO les plus récents. Ou « jamais contacté ».
- **Widget jour/nuit** : « ☀️/🌙 CHEZ TOI » et « ☀️/🌙 DX » avec l'heure solaire approximative de chaque côté, dès qu'un locator DX est connu — pratique pour juger une ouverture en bandes basses. C'est une heure solaire estimée, pas le fuseau horaire officiel du pays.

#### RÉF. CORRESPONDANT (P2P / S2S)

Visible uniquement en mode activation. Si votre correspondant active lui aussi un parc ou un sommet, saisissez sa référence (ex. DL-0042) : le QSO est enregistré comme Park-to-Park / Summit-to-Summit (champs SIG/MY_SIG) dans les fichiers ADIF générés par le serveur — notamment ceux de l'archivage 📦 ARCHIVER. Attention : l'export rapide 📥 ADIF de la barre d'outils n'inclut pas ces champs.

#### RST ENVOYÉ / RST REÇU

Deux champs côte à côte, pré-remplis à 59 (3 caractères maximum), remis à 59 après chaque QSO.

#### N° ENVOYÉ / N° REÇU — des libellés qui s'adaptent au concours

| Concours | Champ « envoyé » | Champ « reçu » |
|---|---|---|
| Concours VHF/UHF (défaut) | **N° ENVOYÉ** — auto-incrémenté **par bande**, en lecture seule (vous ne pouvez ni le modifier ni revenir en arrière ; après une suppression, la série repart du plus grand numéro déjà utilisé) | **N° REÇU** — saisi, formaté 001/002 à la sortie du champ |
| ARRL Field Day | **CLASSE ENV** (fixe, ex. « 1D DX ») | **CLASSE RCU** (ex. « 2A TN ») |
| CQ WW | **ZONE ENV** (14 par défaut) | **ZONE RCU** (1 à 40) |
| ARRL DX | **PUISS. (W)** | **ÉTAT/PROV** |
| REF CDF HF, REF 160m, F9NL, UFT | **DEPT ENV** | **DEPT RCU** — pré-rempli automatiquement depuis la base ou un QSO antérieur, seulement s'il est vide |
| CQ WPX | numéro de série standard automatique | numéro reçu |

Cette ligne est entièrement masquée en mode LOGBOOK SIMPLE et en mode expédition (hors concours).

#### LOCATOR CORRESPONDANT

6 caractères, majuscules, au format AA00AA (ex. JN03QQ) — sinon « ⚠️ Format invalide » et bordure rouge. Trois intelligences :

- **Autocomplétion inversée** : dès 4 caractères, la liste propose les indicatifs connus dans ce carré locator. Sélectionner remplit l'indicatif (s'il est vide) et le locator exact.
- **Distance et points en direct** : dès que le locator est complet et valide, une ligne affiche « 📏 distance km, 🧭 cap et cardinal, → 🏆 points », calculés en temps réel selon le barème du concours actif (avec un calcul de secours si le serveur est injoignable). Un avertissement jaune « ⚠️ Locator déjà loggué » signale un carré déjà travaillé, et un tag indique d'où vient le pré-remplissage : « [📡 cluster] », « [📋 log] », « [🗂️ base] » ou « [🌐 HamQTH] ».
- **Compas** : une petite rose des caps avec aiguille orientée, le cap en degrés, le cardinal (en français, « O » pour Ouest), la distance et les points. Si un rotor est piloté, le bouton **🧭 POINTER** envoie directement l'azimut au rotor.

Ce champ est masqué en mode expédition.

#### ✅ ENREGISTRER LE QSO

Le gros bouton vert valide le contact (Entrée fait la même chose depuis n'importe quel champ). Ce qui se passe :

- Indicatif vide → refus (« Indicatif manquant ! »). Locator invalide → refus.
- Locator vide (hors expédition) → simple avertissement « le QSO va être enregistré sans locator (0 pt) » — le QSO **est** enregistré.
- Doublon → demande de confirmation ; si le serveur détecte de son côté un doublon saisi par un autre poste, une seconde confirmation affiche l'heure et l'opérateur du QSO existant.
- Succès → bip de confirmation (désactivable par le bouton 🔔 de l'en-tête), formulaire vidé, focus sur l'indicatif, table et statistiques mises à jour.
- **Serveur injoignable** → le QSO est stocké localement dans le navigateur (bip plus grave) et resynchronisé automatiquement dès le retour du serveur. Vous ne perdez rien.

#### Sous le formulaire

Une zone secondaire à défilement indépendant regroupe : **REMARQUES EDI (soapbox)** (une zone de texte par bande 144/432/1296, reprise dans l'export EDI), les panneaux RADIO et AMPLI si votre matériel est piloté (fréquence, mode, bouton **■ STOP CW** ; puissance, ROS, bascule STANDBY/OPERATE), les macros et le keyer vocal (§6.4), et « DERNIERS QSO SAISIS » (les 5 derniers).

#### Le panneau « 📻 BAND MAP »

Entre la saisie et la table (masqué sur les écrans étroits), le **📻 BAND MAP** affiche les spots du cluster DX pour la bande courante uniquement, triés par fréquence. Le filtrage se fait **par fréquence réelle** : un spot mal étiqueté ne peut pas apparaître sur la mauvaise bande. Une ★ verte signale un nouveau multiplicateur, les stations déjà faites sont barrées et estompées, et un marqueur « ▶ (radio) » suit la fréquence de votre radio. **Un clic sur un spot remplit l'indicatif et fait QSY la radio** si le CAT est actif. Au-dessus, un « bandscope » sans SDR représente l'activité : une barre par spot, placée à sa fréquence, cliquable. Deux boutons permettent de détacher le Band Map (**⇱**) ou le bandscope (**📡**) dans une fenêtre séparée pour un second écran. Rafraîchissement toutes les 15 secondes.

### 6.2 Le mode ESM (Enter Sends Message), pas à pas

L'ESM transforme la touche Entrée en chef d'orchestre du pile-up, comme sur N1MM : vous ne touchez plus la souris entre deux QSO. Activez-le par le bouton **ESM ○** en haut du panneau de saisie (il devient **ESM ●**, vert).

Une fois actif, Entrée **dans le champ indicatif** enchaîne trois étapes :

1. **Champ vide** → envoi de votre appel CQ (macro CW F1 si la radio est en CW avec le CAT, sinon message vocal V1). Rien n'est loggé.
2. **Indicatif saisi** → envoi de votre échange (macro F2 ou message vocal V3), et le curseur saute dans le numéro reçu. Rien n'est loggé.
3. **Entrée suivante** → le QSO est enregistré pour de bon, et le « merci » (F3 ou V4) part automatiquement.

Le champ indicatif se vide alors, prêt pour l'appel suivant. ESM désactivé, Entrée valide simplement le QSO depuis n'importe quel champ. Convention à respecter dans vos macros : F1 = CQ, F2 = échange, F3 = merci (et côté vocal : V1 = CQ, V3 = REPORT, V4 = MERCI). Le détail est rappelé dans l'aide (bouton **?**), section « ⏎ ESM (Enter Sends Message) — comme sur N1MM ».

### 6.3 Les raccourcis clavier

Appuyez sur **?** (ou cliquez le bouton **?** de l'en-tête) pour afficher le modal **⌨️ RACCOURCIS CLAVIER** :

| Touche | Action |
|---|---|
| Entrée | Valider le QSO — depuis n'importe quel champ de saisie |
| F9 | Valider le QSO — depuis n'importe où sur la page |
| Échap | Fermer une fenêtre ou une liste de suggestions |
| ↑ / ↓ | Naviguer dans les suggestions d'indicatif ou de locator |
| Ctrl+Z | Annuler le dernier QSO enregistré |
| Ctrl+F | Focus sur le champ INDICATIF |
| F1 – F8 | Macros — clic pour copier, double-clic pour modifier |
| ? | Afficher/masquer cette aide |

Précisions utiles : Ctrl+Z demande toujours confirmation (avec l'indicatif, la bande et l'heure du QSO concerné) ; la touche ? est ignorée pendant une saisie dans un champ ; Échap ferme aussi l'édition de QSO, la vérification, les diplômes et l'aperçu d'import ; Ctrl+F (ou Cmd+F sur Mac) est détourné de la recherche du navigateur vers le champ indicatif.

### 6.4 Macros CW, keyer vocal et CALLBOT

Ces trois outils automatisent vos messages répétitifs. Ils sont masqués si vous avez choisi le mode débutant dans la CONFIG.

#### Macros F1–F8 (mode CW)

Le panneau « MACROS — clic: copier · double-clic: modifier » apparaît quand le mode est CW. Huit macros par défaut :

| Touche | Label | Texte |
|---|---|---|
| F1 | CQ RPH | CQ RPH {CALL} {CALL} |
| F2 | ÉCHANGE | 59 {NR} {LOC} |
| F3 | TU | TU {CALL} TEST |
| F4 | QSY 432? | QSY 432.200? |
| F5 | LOCATOR | {LOC} {LOC} |
| F6 | ? | {CALL}? |
| F7 | AGN? | AGN? |
| F8 | 73 | 73 {CALL} |

Attention à la convention : dans les macros CW, `{CALL}` est **votre** indicatif (celui de votre station), `{LOC}` votre locator, `{NR}` le prochain numéro de série. Un clic envoie le texte **directement par le keyer de la radio** si elle est pilotée en CAT et en CW (toast « 📻 CW → … ») ; sinon, le texte est copié dans le presse-papier. Double-clic pour modifier le label puis le texte. Le bouton **■ STOP CW** (panneau RADIO) interrompt un envoi en cours.

#### 🎙 KEYER VOCAL (modes phonie)

Le panneau « 🎙 KEYER VOCAL — clic: jouer · ⏺: enregistrer » remplace les macros quand le mode n'est pas CW. Quatre slots : **CQ**, **RÉPONSE**, **REPORT**, **MERCI**. Le bouton ⏺ enregistre au micro de votre PC (re-clic pour arrêter), ▶ rejoue le message. Le message part **par la radio** : le serveur lève le PTT, l'envoie vers le périphérique de sortie choisi dans CONFIG (le câble vers l'entrée micro de la radio — voir §5, carte Radio), puis relâche le PTT en vérifiant qu'il est bien retombé. La durée de chaque message est affichée sur son bouton. Les enregistrements vivent **sur le serveur** : vous les retrouvez depuis n'importe quel poste du réseau, et ils survivent au vidage du cache du navigateur. Le pilotage radio et le keyer vocal doivent être activés dans CONFIG — sans eux, le PTT ne peut pas être levé et le message est refusé avec un message explicite plutôt que joué dans le vide.

#### 🤖 CALLBOT (phonie automatisée par la radio)

Le panneau « 🤖 CALLBOT — clic: dire · double-clic: modifier » va plus loin : des messages vocaux **dynamiques**, générés par synthèse vocale et émis **par la radio avec PTT automatique** (nécessite le pilotage CAT). Contrairement aux macros CW, ici `{CALL}` désigne **le correspondant** tapé dans la saisie ; `{MYCALL}` est votre station, et `{RST_SENT}`, `{RST_RCVD}`, `{NR}` sont disponibles. Quatre boutons par défaut : B1 « CQ » (« CQ Contest, {MYCALL} »), B2 « RÉPONSE » (« {CALL} »), B3 « REPORT » (« {RST_SENT}, {MYCALL} »), B4 « MERCI » (« Thank you, {MYCALL} »). Le texte réellement prononcé s'affiche sous les boutons.

### 6.5 La table du log : recherche, filtres, édition, doublons

Le panneau de droite liste tous les QSO avec ces colonnes : **#** (position, préfixée ⚠️ si le QSO est incomplet), **HEURE** (UTC), **INDICATIF**, **BANDE** (avec la fréquence exacte en petit si elle a été enregistrée), **MODE**, **ENVOYÉ**, **REÇU**, **LOCATOR**, **DIST/CAP** (km coloré : rouge > 1000, jaune > 500, bleu clair > 200, avec le cardinal), **PTS**, **OP** (badge coloré par opérateur), plus les icônes ✏️ (corriger) et ✕ (supprimer).

- **Recherche** : le champ « 🔍 Rechercher indicatif, locator... » filtre en direct, sur l'indicatif ou le locator, sans tenir compte de la casse.
- **Filtres** : boutons **TOUS** / **144** / **432** / **MES QSO** (vos QSO seulement). Les filtres de bande sont masqués en mode LOGBOOK SIMPLE. Le compteur « N QSO » signale aussi les incomplets.
- **Édition** : double-cliquez une ligne (ou ✏️) pour ouvrir **✏️ CORRIGER LE QSO** : indicatif, date (UTC, AAAAMMJJ), heure (UTC, HH:MM), RST et numéros, bande (limitée aux bandes du concours), mode, locator — la distance et les points sont recalculés en direct pendant la correction. **ANNULER** / **✅ SAUVEGARDER**.
- **Suppression** : ✕ puis confirmation.
- **Doublons** : les lignes en double (même indicatif + même bande) sont barrées et estompées — sauf en mode LOGBOOK SIMPLE, où retravailler une station est normal. Les QSO **incomplets** (champ critique manquant) sont sur fond jaune avec ⚠️ : jamais supprimés automatiquement, mais ignorés à l'export.
- **En arrière-plan** : la table se rafraîchit depuis le serveur toutes les 5 secondes, une sauvegarde locale automatique tourne toutes les 5 minutes (heure affichée dans la barre réseau), les onglets ouverts se synchronisent entre eux, et le navigateur vous avertit si vous tentez de fermer la page en pleine session avec des QSO.

### 6.6 La barre d'outils : tous les boutons

| Bouton | Rôle |
|---|---|
| **🗺️ CARTE** | Bascule la table en carte OpenStreetMap : marqueur jaune pour votre station, un point par correspondant coloré par bande, lignes vers chaque DX, popup par contact (indicatif, locator, bande/mode, km, points). Signale les contacts sans locator non affichés. Le bouton devient **📋 TABLEAU** pour revenir. |
| **📥 EDI** | Export officiel REG1TEST : validation préalable (incomplets ignorés, sans-locator = 0 pt, doublons signalés), puis **un fichier .edi par bande** avec l'en-tête complet issu de votre config (indicatif, locator, section, club, opérateurs, matériel, antennes, soapbox par bande). **Si le concours actif est un concours HF** (CQ WW, WPX, ARRL, REF CDF HF, IARU HF, WAE), ce même bouton génère automatiquement un **Cabrillo 3.0** à la place. Un rappel final affiche l'adresse de soumission et le délai. |
| **📥 ADIF** | Export .adif des QSO valides (confirmation si des incomplets sont écartés). |
| **📥 CSV** | Export tableur, 14 colonnes (date, heure, indicatif, bande, mode, échanges, locator, distance, points, opérateur…). |
| **📂 IMPORTER** | Import ADIF en deux temps : un aperçu chiffre les QSO valides, les nouveaux et les doublons exacts déjà présents (comparaison indicatif + bande + mode + date + heure), puis **✅ CONFIRMER L'IMPORT** (grisé s'il n'y a rien de nouveau). |
| **📡 ON4KST** | Copie dans le presse-papier une annonce prête à coller dans le chat ON4KST (votre indicatif, locator, fréquence, mode). Un rappel « 📡 PENSE À REPOSTER TON CQ » surgit toutes les 10 minutes pendant le concours. Masqué en mode débutant. |
| **📡 SELF-SPOT** | Publie votre indicatif et votre fréquence sur le cluster DX (visible seulement si l'auto-spot est activé dans la config). La confirmation rappelle : « ⚠️ Vérifie que l'auto-spot est autorisé par le règlement du concours. » |
| **🖥️ SCOPE** | Ouvre le bandscope graphique dans une fenêtre séparée, pensée pour un second écran. |
| **🖥️ MUR** | Ouvre l'écran mural (scores + flux des QSO) pour un second écran ou un vidéoprojecteur en radioclub. |
| **✉ QTC : N** | Visible uniquement en WAE : enregistre un échange de QTC (indicatif + nombre de 1 à 10 ; 1 point chacun, maximum 10 par station). Le compteur du bouton se met à jour. |
| **📦 ARCHIVER** | Conserve le log du concours actif dans un dossier permanent (log, Cabrillo, ADIF, résumé). La confirmation propose deux issues : OK = archiver **et** vider ce concours du log actif ; Annuler = archiver **sans** rien effacer. Masqué en LOGBOOK SIMPLE. |
| **💾 SAUVEGARDER** | Sauvegarde immédiate vers le dossier configuré (NAS Synology, Dropbox…). Une sauvegarde automatique existe aussi si vous l'avez activée dans la CONFIG. |
| **🗑️ NOUVEAU LOG** | Réinitialisation protégée par **deux** confirmations : un message expliquant que les QSO sont d'abord archivés dans un dossier permanent (rien n'est perdu), puis la saisie obligatoire du mot « RESET ». Les compteurs de série repartent à zéro. |
| **📊 STATS** | Modal **📊 STATISTIQUES DU CONCOURS**, 3 onglets : **📈 TAUX QSO/HEURE** (histogramme), **📡 PAR BANDE** (QSO/points/multiplicateurs/score par bande), **⏱ HEURE × BANDE** (table croisée). |
| **🔍 VÉRIFIER** | Validateur du log **avant soumission** : doublons, locators absents ou invalides, distances anormales, départements invalides, QSO hors fenêtre du concours. Chaque constat propose « ✏️ Corriger » et « 🗑 Supprimer », avec re-vérification. |
| **🏅 DIPLÔMES** | Modal **🏅 DIPLÔMES & QSL**, votre carnet permanent tous concours : DXCC travaillés/confirmés, départements français (barre de progression et manquants), continents, matrice bande × mode, et la section **📮 QSL** avec envois eQSL, ClubLog, QRZCQ, HRDLog et téléchargement des confirmations LoTW (boutons grisés tant que le service correspondant n'est pas configuré). |
| **✅ CHECKLIST** | **✅ CHECKLIST AVANT CONCOURS** : 5 contrôles — configuration complète, base d'indicatifs chargée, serveur connecté, heure du PC synchronisée (seuil 30 s), postes connectés. |

### 6.7 Le décodeur CW intégré

LogX AI embarque un décodeur Morse temps réel qui tourne entièrement dans le navigateur, sans logiciel supplémentaire. Le panneau **🔤 DÉCODEUR CW** est fixé en bas à gauche de l'écran (en-tête cliquable pour l'ouvrir ou le replier ; la vitesse détectée en mots/minute s'affiche dans l'en-tête).

**Prérequis matériel important** : il doit écouter **l'audio de réception de votre radio** (câble audio virtuel ou interface dédiée), **pas le micro du PC**. Choisissez le bon périphérique d'entrée dans le sélecteur — le navigateur demande une autorisation micro à l'ouverture pour pouvoir lister les périphériques. Réglez le **Ton (Hz)** sur la tonalité de votre récepteur (650 Hz par défaut, réglable de 300 à 1200, même en cours de décodage), puis **▶ Démarrer**. Le texte décodé défile ; **🗑 Effacer** vide la zone.

Soyez lucide sur ses limites, affichées dans le panneau lui-même : le décodage est fiable sur un signal propre et pas trop rapide — ce n'est **pas** un substitut à l'oreille en QRM ou en pile-up serré.

Un second décodeur, plus simple (**🎧 DÉCODEUR CW**, dans la colonne de saisie, visible en mode CW et masqué en mode débutant), offre un raccourci précieux : **cliquer sur un mot décodé contenant un chiffre le place directement dans le champ indicatif**.

À droite, le panneau **💬 CHAT MULTI-OP** (visible uniquement en multi-opérateurs) permet de discuter entre postes : messages horodatés avec l'opérateur, badge rouge de messages non lus quand le panneau est replié, Entrée pour envoyer. Si le serveur est injoignable, votre texte est remis dans le champ au lieu d'être perdu.

### 6.8 Le bandeau de score et le compte à rebours

Sous l'en-tête, huit cases donnent l'état du concours d'un coup d'œil (le bandeau entier est masqué en mode LOGBOOK SIMPLE) :

| Case | Contenu |
|---|---|
| **SCORE TOTAL** | Points recalculés en direct selon le barème du concours actif (avec un barème de secours hors ligne : km en VHF, barèmes CQ WW/WPX/ARRL/REF intégrés). |
| **QSO** | En VHF : « QSO 144 / 432 » avec les deux compteurs ; sinon total + les 4 bandes les plus actives. |
| **MEILLEUR DX** | Distance et indicatif du plus long contact. |
| **LOCATORS UNIQUES** | Nombre de carrés travaillés (devient « SECTIONS / MULTS » en HF). |
| **QSO/HEURE · PROJECTION** | Taux sur les 60 dernières minutes + projection du total final (« 24/h · ~350 ») ; vert dès 30/h, jaune dès 15/h. |
| **DOUBLONS** | Compteur en rouge. |
| **⏱ TEMPS RESTANT** | Compte à rebours à 3 phases : **🟢 DÉBUTE DANS** (vert) avant le départ ; **⏱ TEMPS RESTANT** pendant (orange, jaune sous 4 h, rouge sous 1 h) ; **🏁 TERMINÉ** à la fin, avec une notification unique vous rappelant d'exporter votre log. Les horaires viennent de votre config, sinon du calendrier 2026 intégré. |
| **⏲ DERNIER QSO** | Chrono depuis le dernier QSO : vert sous 2 minutes, jaune de 2 à 5, rouge au-delà — votre aiguillon anti-pause. |

Dès qu'il y a des QSO, trois blocs complémentaires apparaissent dessous : le **récap par bande** (QSO, km total, DX max avec l'indicatif et le cardinal), le **classement des opérateurs** (si au moins 2 opérateurs ont loggé, leader marqué 🏆) et le graphe **QSO / HEURE UTC** (barre de l'heure courante en blanc, ligne d'objectif 20/h en pointillés, heure de pointe affichée).

Enfin, l'en-tête de page reste toujours visible : double horloge UTC/locale, identité de la station (indicatif, locator, altitude, département), nom du concours, boutons 🔔 (bip), ☀️/🌙 (thème jour/nuit, synchronisé entre onglets) et **?** (aide). La barre réseau, dessous, indique l'état de la connexion au serveur, le nombre de postes connectés, l'heure du dernier backup, et l'adresse à ouvrir sur les autres PC ou téléphones du même réseau WiFi, avec un bouton **📋 COPIER** pour la partager.

### La barre de statut, présente sur toutes les pages

Une barre commune accompagne toutes les pages du logiciel (logbook, config, cartes, propagation...) avec des outils permanents :

- **☀️ Météo solaire** : le SFI et l'index K sont rappelés en continu, sur toutes les pages — un clic ouvre la page **📶 PROPAG** pour le détail.
- **⚡ Rate meter** : le rythme instantané s'affiche en permanence (`N/h (10min) · N/h (60min)`). Cliquez dessus pour définir votre **objectif de rate** (QSO/h) : la valeur passe au vert au-dessus de l'objectif, au rouge en dessous — un aiguillon discret pendant un concours.
- **🗔 DISPOSITION** : ce menu ouvre ou ferme d'un clic les quatre panneaux flottants (Coach, Cluster/need list, Soleil & ionosphère, Band Map) depuis n'importe quelle page, et permet d'**enregistrer des dispositions nommées** (« 💾 enregistrer l'actuelle », charger, supprimer, tout fermer) — pratique pour basculer entre un agencement « concours » et un agencement « trafic calme ».
- **🌦️ Météo du point haut** (logbook) : température, vent et rafales, pluie à votre QTH, avec avertissement rouge en cas de conditions dangereuses — pensé pour la sécurité du matériel en portable /P. Données open-meteo, sans clé ni compte.

---


## 7. Faire un concours de A à Z

Ce chapitre déroule un concours complet avec LogX AI, de la préparation à la soumission du log : le logiciel choisit les dates tout seul, adapte la saisie au règlement, valorise chaque spot en points réels du barème, puis produit le fichier au format exigé par le correcteur. Vous n'avez ni classeur de règlements à relire, ni calculatrice de score à tenir.

### 7.1 AVANT — choisir le concours et se préparer

#### La base de concours suivie

LogX AI connaît les concours à trois niveaux de profondeur. Ordre de grandeur à retenir : **environ 35 concours entièrement « jouables »** (dates automatiques, bandes, modes, échange, barème, format de log, deadline et adresse de soumission) **et environ 360 concours par an visibles au calendrier mondial**.

| Niveau | Contenu | Ce que le logiciel sait en faire |
|---|---|---|
| Base intégrée | ~35 concours définis de bout en bout : REF (Rallye des Points Hauts, National THF — Trophée F3SK, Championnats de France HF phonie et télégraphie, REF 160m, Bol d'Or des QRP…), IARU R1 (145 MHz, UHF/SHF, 50 MHz, Marconi Memorial), CQ WW et CQ WPX, ARRL (DX, Field Day, 10m, 160m), WAE (avec QTC), UBA, European HF Championship, Russian DX, SP DX, HA DX, All Asian, Stew Perry, SOTA, POTA | Tout : score en direct, saisie adaptée, rappel de deadline ; export automatique au bon format pour les concours VHF/UHF (EDI) et pour CQ WW/WPX, ARRL et championnats de France HF (Cabrillo) — les autres passent par l'archive (Cabrillo générique) ou l'ADIF |
| Barèmes complémentaires | Le calendrier REF complet 2026 (Challenge THF cumulatif, Courtes Distances mensuels dont sessions CW, TVA/ATV, DDFM 50 MHz, F8TD SHF…) et quelques concours français hors REF (F9NL, rencontres UFT) | Score au barème correspondant |
| Calendrier mondial | ~358 concours par an issus du calendrier perpétuel WA7BNM (nom, dates, horaires, lien vers le règlement), rafraîchi automatiquement en tâche de fond | Consultation et préparation ; le badge **⚠ À CONFIRMER** signale qu'il faut faire lire le règlement à l'IA avant de jouer le score |

La page **CALENDRIER** présente tout cela en trois onglets : **⭐ REF / IARU / Internationaux**, **🌍 MONDIAL WA7BNM** et **🏝️ DXPEDITIONS (NG3K)**. Un clic sur **▶ DÉMARRER** (ou **▶ PRÉPARER** pour un concours du calendrier mondial) active le concours ; vous pouvez aussi passer par la page **CONFIG**, section **🏆 3. SÉLECTION DU CONCOURS**, où la fiche choisie s'orne du badge **✓ SÉLECTIONNÉ**. Le bouton **🔄 VÉRIFIER LES RÈGLEMENTS** relance la mise à jour du calendrier à la demande.

#### Les dates se calculent toutes seules

Chaque concours intégré porte une règle de date (« premier samedi de juillet », « dernier week-end complet d'octobre »…) : les dates se recalculent chaque année sans aucune maintenance de votre part. Limite connue et assumée : la grammaire ne connaît que les samedis et dimanches, si bien que l'ARRL 160m, qui démarre en réalité le vendredi à 22h00 UTC, s'affiche à la date du samedi.

#### Ajouter un concours absent : l'analyse de règlement par IA

Pour un concours que la base ne connaît pas, le bouton **🤖 ANALYSER UN RÈGLEMENT (IA)** de la page **CONFIG** lit un règlement (PDF ou adresse web) et en extrait une définition complète — que vous relisez et corrigez avant enregistrement, l'IA ne publie jamais rien sans validation humaine. Le concours ainsi créé rejoint la base et devient un concours comme les autres : calendrier, saisie, score en direct, tout fonctionne sans traitement particulier. Il est impossible d'écraser un concours intégré par ce biais, et seuls les concours personnalisés peuvent être supprimés. Cette fonction nécessite d'avoir configuré la clé API du service d'IA (voir le chapitre CONFIG).

#### Le point essentiel : le barème appliqué est celui du règlement

Le moteur de score ne fait pas d'estimation « à la louche » : chaque QSO et chaque spot sont valorisés selon le barème réel du concours actif — points directs (par bande, par mode, par distance en km, selon le pays ou le continent…) plus l'impact estimé d'un nouveau multiplicateur (locators, grands carrés, zones CQ, préfixes, départements + DXCC, sections ou états nord-américains…). La règle des doublons est la vraie règle des concours : « déjà fait » signifie déjà contacté **sur cette bande précise** — une station travaillée en 144 MHz reste pleinement valable en 432 MHz. L'identification des pays, continents et zones s'appuie sur la référence hors ligne cty.dat (AD1C), la même que N1MM ou DXLog. Et comme l'analyse IA produit exactement les mêmes règles déclaratives que la base intégrée, **un concours ajouté par IA est scoré avec la même rigueur qu'un concours d'origine**.

Par honnêteté, quelques barèmes portent des approximations documentées : le HA DX est marqué « à confirmer via analyse du règlement », les multiplicateurs UBA (provinces belges) sont approchés par zone/DXCC, le Stew Perry classe correctement les spots par distance mais simplifie son barème au point-par-km au stade du spot, et l'état exact d'une station américaine n'est connu qu'au moment de l'échange (avant, il est estimé d'après le préfixe).

#### La check-list de départ

Le bouton **✅ CHECKLIST** du logbook ouvre la liste de préparation, et le coach commence à vous alerter 48 heures avant le départ (matériel, catégorie, dates). Vérifiez aussi à ce stade votre locator et votre département dans **CONFIG** : ils servent au calcul des km et des multiplicateurs.

### 7.2 PENDANT — opérer avec le score en temps réel

#### Une saisie qui s'adapte au règlement

Dès qu'un concours est actif, les champs d'échange du **📋 LOGBOOK** prennent la forme exigée par son règlement — vous n'avez rien à paramétrer :

| Concours | Champs affichés | Particularité |
|---|---|---|
| Concours VHF/HF standard (REF THF, IARU, WPX…) | N° ENVOYÉ / N° REÇU | Numéro de série auto-incrémenté, par bande |
| CQ WW | ZONE ENV / ZONE RCU | Pré-rempli « 14 » (zone de la France) |
| ARRL Field Day | CLASSE ENV / CLASSE RCU | Classe + section (ex. « 2A TN ») ; la valeur envoyée reste en place d'un QSO à l'autre |
| ARRL DX | PUISS. (W) / ÉTAT/PROV | Puissance envoyée (défaut 100), état ou province reçu |
| Championnats de France HF, REF 160m, F9NL, UFT | DEPT ENV / DEPT RCU | Départements (ex. « 43 ») |

Pendant que vous tapez l'indicatif, un badge s'affiche en temps réel : **⚠️ DOUBLON sur cette bande** (rouge), **📈 NOUVEAU MULTIPLICATEUR** (vert, avec le type de multiplicateur), ou « ✔ nouveau » avec les points que rapportera le contact. S'y ajoutent la fiche de la station (annuaire QRZ → HamQTH → HamDB en cascade) et l'historique complet de vos contacts avec elle, tous concours confondus. En station multi-opérateurs, la détection de doublon porte sur le log partagé de toute l'équipe.

#### Need list et carte : les priorités en points réels

La **🎯 CLUSTER — NEED LIST** (page **🎯 CHASSE** et panneau détachable) classe les spots du cluster par valeur réelle au barème du concours : nouveaux multiplicateurs en tête, puis points directs décroissants, avec pour chacun la distance, le cap antenne (degrés + point cardinal) et une explication en clair. Les onglets de chasse ciblée (**🎯 CIBLES — QUI PEUT LES DONNER**) listent, selon le concours, les départements qui vous manquent (toutes bandes confondues) ou les pays qui vous manquent **sur chaque bande**, avec les stations spottées prêtes à être appelées et leur fréquence.

Sur la carte, la couleur et la taille des marqueurs viennent du moteur de score, pas d'une appréciation libre de l'IA : priorités 1 et 2 en surbrillance, stations déjà travaillées grisées. Deux nuances honnêtes : un spot VHF passe en priorité maximale quand une ouverture Sporadique-E, tropo ou aurore est signalée, mais avec la mention explicite qu'il n'y a « pas de garantie sur ce trajet précis » ; et une station vue seulement sur le chat ON4KST est plafonnée en priorité, sa propagation n'étant pas confirmée.

#### Le coach de rythme

Le panneau **🧠 COACH** (carte et panneau détachable) suit votre course en continu, de façon entièrement déterministe — aucun appel IA, donc aucune latence ni coût :
- horloge du concours (avant / en cours / terminé, % accompli, heures restantes) ;
- rythme : QSO/h moyen, cadence des 10 et 60 dernières minutes, minutes depuis le dernier QSO ;
- plan de bande recommandé, pondéré par le barème (exemple : en WAE, les multiplicateurs comptent ×4 sur 80 m — le coach vous y pousse aux bonnes heures) et par la propagation ;
- recommandation **RUN / S&P / changement de bande** selon votre cadence et les multiplicateurs disponibles sur le cluster ;
- alertes : silence radio de plus de 15 minutes, chute de rythme, budget de temps de repos (WAE : 36 h d'opération maximum sur 48, avec plan de pauses), rappel des QTC, et « chasse aux mults » sur les deux dernières heures.

Les textes du coach existent en 8 langues (français, anglais, allemand, espagnol, italien, portugais, néerlandais, polonais).

#### Band map, bandscope et QSY au clic

Le panneau **📻 BAND MAP** affiche les spots de votre bande courante, classés par fréquence, filtrés par la fréquence elle-même (un spot 432 ne peut pas se glisser dans la liste 144, même mal étiqueté à la source). Vert avec ★ = nouveau multiplicateur ; station déjà travaillée barrée ; un marqueur suit la fréquence de votre radio. **Un clic sur un spot remplit l'indicatif dans la saisie et, si le pilotage CAT est configuré, fait directement QSY la radio** sur la fréquence et le mode du spot. Le bandscope au-dessus est un « scope sans SDR » : chaque spot y est une barre placée à sa fréquence, cliquable de la même façon. Les deux se détachent sur un second écran (boutons **🖥️ SCOPE** et **🖥️ MUR**).

#### Macros et assistance à l'opérateur (mode expert)

En mode expert, le bandeau bas du logbook propose : les **macros F1–F8** (clic pour copier, double-clic pour modifier), le **🎙 KEYER VOCAL** en phonie (messages enregistrés rejoués avec passage en émission automatique — nécessite le pilotage CAT de la radio), le **🤖 CALLBOT** (l'indicatif tapé et le report épelés par synthèse vocale et émis par la radio) et le **🎧 DÉCODEUR CW** (décodage Morse en direct dans le navigateur, l'audio de la radio devant arriver sur l'entrée micro du PC ; un clic sur un mot décodé le place dans le champ indicatif).

#### Cas particulier : les QTC du WAE

Quand le concours actif comporte un mécanisme QTC (WAE SSB et RTTY), un bouton **✉ QTC** apparaît dans la barre du logbook : vous y saisissez l'indicatif et le nombre de QTC échangés (1 point chacun), le logiciel refusant de dépasser la limite réglementaire de 10 QTC par station et le coach vous rappelant d'y penser. Limite assumée : les QTC ne sont pas intégrés à la valorisation des spots — ils sont comptés séparément, via ce compteur, dans le score final.

### 7.3 APRÈS — vérifier, exporter, soumettre, débriefer

#### 🔍 VÉRIFIER : la relecture du log avant envoi

Le bouton **🔍 VÉRIFIER** passe votre log au crible sans rien modifier, et classe chaque constat en trois niveaux : **erreur** (coûtera des points ou invalidera le QSO), **attention** (suspect, à contrôler) et **info** (mineur). Contrôles effectués :

| Contrôle | Exemple de constat |
|---|---|
| Doublons (règle REF : 1 QSO par station et par bande) | « déjà travaillé sur 144 MHz (QSO n°12) — 0 point » |
| Indicatif plausible (préfixes connus, portables composés type EA/F4GLD/P gérés) | « format inhabituel — busted call probable » |
| Locator (concours THF) | absent (« aucun km »), invalide, ou distance anormale pour la bande — signalée « à vérifier », pas rejetée |
| Département (concours REF HF) | département reçu invalide pour une station française |
| Fenêtre temporelle | QSO hors des dates du concours |
| Divers | bande hors concours, RST manquant |

Chaque constat pointe le QSO concerné et propose **✏️ Corriger** (ouvre l'édition) ou **🗑 Supprimer** (avec confirmation) ; le bouton **🔄 RE-VÉRIFIER** relance le contrôle après vos corrections. Seuls les QSO du concours et de l'édition en cours sont examinés — un log importé ou une édition précédente ne pollue pas le résultat. La liste est plafonnée à 200 constats.

#### L'export au bon format, choisi automatiquement

Le bouton **📥 EDI** produit le fichier de soumission : Cabrillo v3 pour les grands concours HF pris en charge par l'export (CQ WW/WPX, ARRL DX, ARRL Field Day, championnats de France HF), avec les noms officiels de concours, le score revendiqué et — pour le Field Day — le bloc classe/émetteurs ; EDI (REG1TEST) pour les concours VHF/UHF/SHF, avec l'en-tête complet (locator, section, club, opérateurs, matériel et antenne par bande). Pour les autres concours HF de la base (WAE, UBA, European HF Championship, Russian DX, SP DX, HA DX, All Asian, Stew Perry, ARRL 10m/160m, REF 160m…), ce bouton ne génère pas encore de Cabrillo : passez par **📦 ARCHIVER**, qui écrit un Cabrillo générique dans le dossier d'archive. ; EDI (REG1TEST) pour les concours VHF/UHF/SHF, avec l'en-tête complet (locator, section, club, opérateurs, matériel et antenne par bande).

Deux points pratiques pour l'EDI : le règlement impose **un fichier par bande** — LogX AI les génère tous, en espaçant les téléchargements pour contourner le blocage anti-téléchargements-multiples de Chrome ; si vous avez l'impression de « ne recevoir que le 144 », attendez simplement quelques secondes. À la fin, la fenêtre **📤 SOUMISSION DU LOG** vous rappelle l'adresse de dépôt (par défaut le site de dépôt du REF pour les concours THF), le délai réglementaire et le nombre de fichiers attendus. L'adresse et le délai de chaque concours sont aussi rappelés par le coach en fin d'épreuve. Le bouton **📥 ADIF** produit en parallèle un export ADIF rapide (indicatif, bande, mode, RST, locator, date/heure), et **📦 ARCHIVER** range le tout — log, Cabrillo, ADIF, résumé — dans un dossier permanent ; c'est le fichier .adi de l'archive qui contient l'ADIF 3 complet pour eQSL/LoTW (identifiant de concours, opérateur, distances et champs POTA/SOTA/WWFF).

#### Le scoreboard en ligne (pendant le concours)

LogX AI peut publier votre score en direct sur contestonlinescore.com, au format « score dynamique N1MM », pour vous comparer à vos rivaux en temps réel. Tout se règle dans **CONFIG**, section **🏆 13. SCOREBOARD & SOUMISSION** : activation (**SCOREBOARD EN DIRECT**), intervalle d'envoi (5 minutes par défaut) et catégorie. Le score publié est filtré sur le concours et l'année en cours — un vieux log importé ne gonflera jamais votre total. À savoir : contestonlinescore.com est un service tiers bénévole ; s'il est indisponible, l'envoi échoue silencieusement sans perturber votre trafic, et reprendra tout seul.

#### Le débrief

Le bouton **🎓 DÉBRIEF** (page carte) analyse le concours écoulé. La partie chiffrée est calculée localement et sans IA : meilleures et pires heures, silences de plus de 30 minutes, ODX par bande, kilomètres cumulés, carrés locator et départements travaillés. Si l'assistant IA est configuré (clé API requise), il produit en plus une analyse structurée imposée : trois points forts, trois axes d'amélioration concrets, et ce qui vous a coûté le plus de points — de quoi préparer la revanche.

---

## 8. Piloter sa radio et son matériel

LogX AI peut dialoguer avec votre transceiver, votre amplificateur, votre rotor et WSJT-X : la fréquence et le mode se remplissent tout seuls, un clic sur un spot cale la radio dessus, vos macros CW partent au manipulateur de la radio et vos QSO FT8 entrent dans le log sans ressaisie. Tout cela reste **optionnel et désactivé par défaut** : sans aucun câble, l'intégralité du reste du logiciel (saisie, vérification, score, cartes, cluster, IA…) fonctionne normalement — voir la dernière section de ce chapitre.

### 8.1 Pilotage CAT de la radio : trois modes au choix

Ouvrez la configuration, popup **📻 5. RADIO (PILOTAGE CAT)**. Passez d'abord **PILOTAGE RADIO** de Désactivé à Activé, puis choisissez le **MODE DE PILOTAGE**. Un bloc dépliable **📖 Quel mode choisir pour ma radio ?** résume les trois possibilités directement dans la page, avec le nombre de modèles couverts.

| Mode (libellé exact du menu) | Pour qui ? | Logiciel externe requis | Lecture fréquence/mode + QSY | Envoi CW |
|---|---|---|---|---|
| **Natif (recommandé — pas de logiciel externe)** | Icom, Yaesu, Kenwood, Elecraft, Xiegu reliés par un câble série/USB | Aucun | Oui | **Non** |
| **TCI (postes SDR — SunSDR/ExpertSDR3 et compatibles)** | SunSDR2 DX/PRO/QRP, MB1, ColibriDDC/NANO et tout logiciel compatible TCI (ExpertSDR2/3, Log4OM, RUMlogNG, JTDX/WSJT-X « improved », SDC…) | ExpertSDR3 (ou équivalent) avec son serveur TCI activé | Oui (+ PTT et S-mètre) | Oui |
| **Hamlib rigctld (avancé — autres marques)** | Tout le reste : Ten-Tec, FlexRadio, anciens modèles, toute radio non listée en natif (Hamlib gère plus de 200 modèles) | rigctld (Hamlib) | Oui | Oui |

Le PTT, lui, est disponible dans les **trois** modes — c'est ce qu'utilise le keyer vocal (section 8.5).

#### Mode natif : marques et modèles pris en charge

Aucun logiciel tiers : LogX parle directement à la radio sur le port série. Choisissez la **MARQUE**, puis le **MODÈLE** :

| **MARQUE** (libellé du menu) | Modèles proposés | Vitesse préremplie |
|---|---|---|
| **Icom (CI-V)** | IC-705, IC-706MKIIG, IC-7000, IC-7100, IC-718, IC-7200, IC-7300, IC-7410, IC-746, IC-746PRO, IC-756, IC-756PRO, IC-756PROII, IC-756PROIII, IC-7600, IC-7610, IC-7700, IC-7800, IC-7851, IC-905, IC-910H, IC-9100, IC-9700, plus les récepteurs IC-R75 et IC-R8600 | 19200 bauds |
| **Xiegu (CI-V compatible Icom)** | G90, G106, X6100, X5105 | 19200 bauds |
| **Yaesu (CAT)** | FT-817, FT-818, FT-857, FT-891, FT-897, FT-991, FT-991A, FTDX10, FTDX101D, FTDX101MP | 4800 bauds |
| **Kenwood (PC Control)** | TS-480, TS-570, TS-2000, TS-590S, TS-590SG, TS-890S, TS-990S | 9600 bauds |
| **Elecraft (K3/KX)** | K2, K3, K3S, KX2, KX3, K4 | 38400 bauds |

À savoir :

- Pour Icom et Xiegu, le modèle sert surtout à prérégler l'adresse CI-V d'usine (IC-7300 = 94, IC-705 = A4…) ; la note « Adresse CI-V usine : XX (modifiable sur la radio si besoin) » s'affiche. Un Icom ou Xiegu **absent de la liste** fonctionne quand même : indiquez simplement son adresse CI-V.
- Un Yaesu/Kenwood/Elecraft récent absent de la liste fonctionne généralement aussi (même famille de commandes).
- **PORT SÉRIE** : la liste des ports COM détectés se met à jour avec **🔄 Rafraîchir la liste**. **VITESSE (bauds)** est préremplie selon la marque (tableau ci-dessus) — gardez la valeur réglée dans le menu de votre radio.
- **🔌 Tester / auto-détecter** : test éphémère qui ouvre le port, interroge la radio et le referme, sans toucher la connexion en cours. En cas de succès sur Yaesu/Kenwood/Elecraft, le modèle est identifié : « ✅ Radio détectée : FT-991A (14.074 MHz) ». En cas d'échec sur Icom : « Radio muette à cette adresse — vérifie modèle/adresse CI-V/port/vitesse ».
- La connexion se rouvre toute seule si vous changez la configuration ou si le câble USB est débranché puis rebranché.
- **Limite réelle du mode natif** : pas d'envoi CW. Le message est explicite : « Envoi CW non disponible en mode "Natif" — bascule en mode "Hamlib rigctld" ou "TCI" pour le keyer CW ».

#### Mode TCI (postes SDR)

Pas de port série ni de programme à installer : LogX se connecte en réseau au serveur TCI de votre logiciel SDR. Renseignez **ADRESSE TCI** (127.0.0.1 si tout tourne sur le même PC, sinon l'IP du poste SDR) et **PORT TCI** (50001 par défaut avec ExpertSDR3 ; 40001 pour l'ancien ExpertSDR2). Le serveur TCI doit être activé dans ExpertSDR3. La liaison est permanente : fréquence, mode, PTT et S-mètre arrivent en continu, sans interrogation répétée. Le test de configuration affiche « ✅ Serveur TCI joint (host) : <appareil> (xx.xxx MHz) » ; si le logiciel SDR n'a pas fini de démarrer, un message vous invite à vérifier qu'ExpertSDR3 tourne et que son serveur TCI est activé.

#### Mode Hamlib rigctld (toutes les autres radios)

Hamlib est un logiciel libre qui pilote plus de 200 modèles. Sur le PC relié à la radio, lancez `rigctld -m <n°modèle> -r <port COM> -T 0.0.0.0` (le numéro de modèle s'obtient avec `rigctl -l`), puis renseignez **ADRESSE RIGCTLD** et **PORT RIGCTLD** (4532 par défaut). rigctld peut tourner sur un **autre poste du réseau local** que celui qui affiche LogX. Ce mode donne aussi accès à l'envoi CW via le manipulateur interne de la radio.

#### Ce que le pilotage débloque dans le logbook

- **Panneau 📻 RADIO** (visible uniquement si le pilotage est activé) : pastille de connexion, fréquence en kHz, mode, et bouton **■ STOP CW** pour interrompre immédiatement un message CW en cours.
- **Suivi en direct** : quand vous changez de bande sur la radio, la bande de saisie bascule automatiquement. Le champ FRÉQUENCE suit la radio, **sauf** si vous l'éditez à la main (split, fréquence annoncée) — votre saisie n'est jamais écrasée. Le bouton **📻 Radio** à côté du champ (« Lire la fréquence de la radio (CAT) ») recolle la fréquence de la radio et réactive le suivi.
- **QSY d'un clic** : dans le band map et le bandscope, cliquer un spot remplit l'indicatif **et** cale la radio sur la fréquence du spot. Le band map affiche aussi un marqueur « ▶ xx.xxx (radio) » à votre fréquence courante.
- **Macros CW** (panneau **MACROS — clic: copier · double-clic: modifier**) : 8 macros par défaut (« CQ RPH », « ÉCHANGE », « TU », « QSY 432? », « LOCATOR », « ? », « AGN? », « 73 »), avec variables {CALL} (votre propre indicatif ici), {LOC} et {NR} remplacées à la volée. Si la radio est en CW et le CAT actif, le texte part directement au manipulateur de la radio (toast « 📻 CW → … ») ; sinon il est copié dans le presse-papier (« 📋 … »). Les macros se déclenchent **au clavier** (touches F1 à F8) comme au clic. Le clavier fonctionne aussi pendant que vous tapez dans un champ : on saisit l'indicatif, on envoie l'échange par F2, on continue de taper sans quitter le clavier. Les touches sont neutralisées tant que la fenêtre de démarrage n'est pas validée, et pendant qu'une fenêtre est ouverte (édition d'un QSO, vérificateur, diplômes) — pour qu'une touche de fonction ne parte jamais en émission au mauvais moment. Le double-clic sur un bouton reste le moyen de modifier une macro, et de lui réaffecter une autre touche : le clavier suit ce qui est écrit sur le bouton.
- **ESM** (« Enter Sends Message », bouton **ESM**) : la touche Entrée enchaîne CQ → échange → mise au log, « à la N1MM ». En CW, la convention est F1 = CQ, F2 = échange, F3 = merci ; en phonie, ce sont les messages vocaux V1/V3/V4 (section 8.5).

### 8.2 Amplificateurs HF

LogX surveille et commande trois familles d'amplis, chacune vérifiée contre la documentation officielle du constructeur, sur un port série **dédié** (indépendant de celui de la radio). Configuration dans le popup **🔋 6. AMPLIFICATEUR HF**, menu **MARQUE** :

| **MARQUE** (libellé du menu) | LogX lit | LogX commande | Vitesse par défaut |
|---|---|---|---|
| **Elecraft (KPA500 / KPA1500)** | Puissance (W), SWR, standby/operate, code défaut, température | Standby↔Operate, acquittement de défaut, changement de bande direct, extinction **et rallumage** à distance | 38400 bauds |
| **Icom (IC-PW2 / PW-1, CI-V)** | Puissance et SWR **en valeurs brutes 0–255** (échelle constructeur, affichées « (brut) »), protection (Température, ALC, Puissance, Bande, Alimentation), standby/operate, statut TX | Standby↔Operate, bande directe 1.8–50 MHz, acquittement de défaut, marche/arrêt à distance | 19200 bauds |
| **SPE / Expert (1.3K-FA / 1.5K-FA / 2K-FA)** | 19 informations : operate, TX, entrée, bande, puissance (W), SWR ATU et antenne, tension/courant du PA, 3 températures, avertissements et alarmes en français (« SWR hors limites », « Surchauffe excessive »…) | Standby↔Operate, bande (pas à pas, géré automatiquement) | 9600 bauds |

Précisions honnêtes :

- **KPA1500** : uniquement par le port série (son accès réseau propre n'est pas pris en charge).
- **IC-PW2/PW-1** : adresse CI-V d'usine AA (champ **ADRESSE CI-V**, modifiable si vous l'avez changée sur l'ampli). Les valeurs de puissance/SWR sont volontairement affichées brutes : Icom ne publie pas l'échelle de conversion, et LogX n'invente rien.
- **SPE** : le protocole constructeur simule des appuis sur le panneau avant ; il n'offre ni acquittement de défaut ni mise sous tension à distance (messages explicites dans l'interface).
- Marques **non** prises en charge, faute de protocole documenté par le constructeur : ACOM, Ameritron, Yaesu VL-1000, Tokyo Hy-Power (ces amplis suivent la radio par band-data, pas par dialogue série).

Le bouton **🔌 Tester la connexion** répond « ✅ Ampli joint — xxx W, SWR x.x » (ou un message d'échec). Dans le logbook, le panneau **🔋 AMPLI** affiche pastille, puissance, SWR, l'éventuel défaut en rouge (« ⚠ … »), et un bouton **STANDBY**/**OPERATE** qui bascule l'état.

### 8.3 Rotor d'antenne

Le rotor pointe l'antenne d'un clic, sans ressaisir d'azimut. LogX passe par **rotctld**, le compagnon de Hamlib pour rotors (« rotctld est au rotor ce que rigctld est à la radio »). Dans le popup **🧭 7. ROTOR D'ANTENNE** : lancez `rotctld -m <n°modèle> -r <port> -T 0.0.0.0` sur le PC relié au boîtier de commande (liste des modèles : `rotctl -l`), puis renseignez **ADRESSE ROTCTLD** et **PORT ROTCTLD** (4533 par défaut) — là aussi, un autre poste du réseau convient.

Dans le logbook, dès que vous saisissez le locator du correspondant, la boussole affiche cap, cardinal, distance et points ; si le rotor est piloté, un bouton **pointer** apparaît et envoie le cap affiché (« 🧭 Antenne pointée sur xxx° »). L'azimut est borné 0–360°, l'élévation 0–90°. Désactivé par défaut — aucun effet sans rotctld.

### 8.4 Auto-log WSJT-X (FT8/FT4) : plus de ressaisie

Chaque QSO que vous validez dans WSJT-X entre automatiquement dans le logbook, avec la même vérification de doublons et le même calcul de score qu'une saisie manuelle. Dans la section **💻 WSJT-X (FT8/FT4 — auto-log)** de la configuration, activez **AUTO-LOG WSJT-X** et vérifiez le **PORT UDP WSJT-X** (2237). Côté WSJT-X : Réglages → Rapports → UDP Server = l'IP du PC qui fait tourner LogX, port 2237.

Sont repris automatiquement : indicatif, grille (complétée pour le calcul de distance), bande — y compris les bandes WARC 30/17/12 m, correctement identifiées —, mode, rapports envoyé/reçu et heure. Le logbook affiche un widget d'état : **💻 WSJT-X ●** en vert avec la fréquence, le mode et le compteur de QSO auto-loggés quand WSJT-X donne signe de vie (moins de 30 s), **💻 WSJT-X ○ en attente (port 2237)** sinon. Chaque QSO auto-loggé recharge la table et joue un bip.

### 8.5 Keyer vocal : votre indicatif dit automatiquement, 100 % hors-ligne

En phonie, le keyer vocal épargne votre voix : il annonce l'indicatif du correspondant et le report à votre place, en passant la radio en émission tout seul. La synthèse vocale utilise les voix Windows installées sur le PC — **aucune connexion Internet, aucune clé API**.

L'épellation suit les conventions radioamateur : alphabet OACI (« F4GLD/P » → « Foxtrot Four Golf Lima Delta portable »), suffixes /P /M /MM /AM /QRP dits en toutes lettres, reports chiffre par chiffre (« 59 » → « Five Nine », jamais « fifty-nine »).

Configuration, section **🎙️ KEYER VOCAL (phonie — indicatif dit automatiquement)** :

- **KEYER VOCAL** : Désactivé/Activé.
- **PÉRIPHÉRIQUE DE SORTIE** : « Le câble/l'interface relié(e) à l'entrée micro de la radio, PAS tes enceintes » — il vous faut donc un câble audio virtuel (type VB-Audio) ou une interface dédiée. **C'est le seul matériel supplémentaire requis.**
- **VOIX** : les voix Windows installées. **VITESSE (mots/min)** : 175 par défaut (80–300).
- **🔊 Tester (indicatif fictif)** : joue un exemple avec F8TEST.

À l'émission, LogX enclenche le PTT via le CAT (les trois modes conviennent), joue le message, puis relâche le PTT — relâchement **vérifié** avec seconde tentative ; en cas d'échec vous êtes prévenu : « ⚠ ÉCHEC DU RELÂCHEMENT PTT — la radio peut rester en émission ! ». Deux messages ne peuvent jamais se chevaucher.

Dans le logbook (quand le mode n'est pas CW), le panneau **🎙 KEYER VOCAL — clic: jouer · ⏺: enregistrer** propose 4 messages enregistrés à votre micro (V1 « CQ », V2 « RÉPONSE », V3 « REPORT », V4 « MERCI » — conservés dans le navigateur), et le **🤖 CALLBOT — clic: dire · double-clic: modifier** 4 macros dynamiques : B1 « CQ Contest, {MYCALL} », B2 « {CALL} », B3 « {RST_SENT}, {MYCALL} », B4 « Thank you, {MYCALL} ». **Attention à la convention** : dans le CALLBOT, {CALL} désigne le correspondant en cours de saisie — à l'inverse des macros CW, où {CALL} est votre propre indicatif.

### 8.6 Décodeur CW : lire le morse sans logiciel tiers

Le panneau **🔤 DÉCODEUR CW** transcrit en texte le CW reçu, entièrement dans le navigateur — rien à installer. Il écoute l'**audio de réception de la radio** : « Écoute l'audio de réception (câble virtuel ou interface dédiée depuis la radio, PAS le micro du PC) et affiche le CW décodé. Fiable sur signal propre et pas trop rapide — pas un substitut à l'oreille en QRM/pileup serré. »

Mode d'emploi : ouvrez le panneau (en bas à gauche du logbook), choisissez le périphérique d'**entrée** audio (les noms des périphériques n'apparaissent qu'après avoir autorisé le micro dans le navigateur), ajustez au besoin **Ton (Hz)** (650 par défaut, réglable 300–1200, même en cours de décodage), puis **▶ Démarrer**. Le texte défile dans la zone ; **■ Arrêter** stoppe l'écoute, **🗑 Effacer** vide la zone. La vitesse est estimée automatiquement et affichée en direct dans l'en-tête (« xx MPM », plage 4–60 mots/min) ; lettres, chiffres, ponctuation et prosigns (<AR>, <SK>, <BK>…) sont reconnus.

### 8.7 Et sans aucun matériel ?

Tout le reste du logiciel fonctionne à l'identique sans le moindre câble : saisie et vérification des QSO, score, cartes, cluster et spots, statistiques, assistants IA. Les fonctions matérielles se dégradent proprement :

- Les macros CW se **copient dans le presse-papier** au lieu de partir à la radio.
- La fréquence et la bande se saisissent à la main ; le bouton **📻 Radio** répond simplement « Radio non connectée (CAT) — saisis la fréquence à la main. »
- Les panneaux **📻 RADIO**, **🔋 AMPLI** et le bouton **pointer** de la boussole n'apparaissent tout simplement pas tant que le matériel correspondant n'est pas activé.
- Seuls le keyer vocal et le décodeur CW demandent un accessoire audio (câble virtuel ou interface) ; l'auto-log WSJT-X ne demande que WSJT-X lui-même sur le réseau.

---

## 9. Cartes, propagation, chasse, EME et écoute à distance

Ce chapitre couvre les six pages qui vous font sortir du logbook : voir où sont les stations à contacter, savoir quelles bandes sont ouvertes et vers où, repérer les activateurs en l'air et les spots qui valent des points, préparer un contact par rebond lunaire, écouter votre propre signal depuis un récepteur distant, et planifier vos concours et chasses aux DXpéditions. Les six pages partagent la même barre d'onglets (**⚙ CONFIG**, **📋 LOGBOOK**, **🗺️ CARTE IA**, **📶 PROPAG**, **🎯 CHASSE**, **🇫🇷 Cartes**, **📅 CALENDRIER**, **📡 WEBSDR**) et le même thème jour/nuit, mémorisé d'une visite à l'autre.

Deux pages voisines à ne pas confondre : **📶 PROPAG** répond à « quelles bandes sont ouvertes, et vers où ? » — on la consulte de temps en temps ; **🎯 CHASSE** répond à « qui est-ce que je contacte maintenant ? » — on la travaille en continu. C'est pourquoi les cinq panneaux de cibles (activateurs POTA/SOTA/WWFF, châteaux WCA, need list du cluster) vivent sur CHASSE et non sur PROPAG.

| Page | À quoi elle sert |
|---|---|
| **🗺️ CARTE IA** | Carte tactique du concours : stations classées par priorité, anneaux de distance (dont votre record DX réel), ligne grise, chat avec le coach IA |
| **🇫🇷 Cartes** | Tableaux de chasse géographiques : départements français à « verdir » et pays DXCC travaillés, avec les stations qui peuvent vous donner ce qui manque |
| **📶 PROPAG** | Salle de veille : soleil et ionosphère, ouvertures par région, conditions par bande, balises, tropo, météores, EME, qui entend votre signal (PSK/RBN) |
| **🎯 CHASSE** | Les cibles du moment : activateurs POTA/SOTA/WWFF en direct, châteaux WCA annoncés, et la need list du cluster valorisée pour votre concours |
| **📡 WEBSDR** | Annuaire de récepteurs distants pilotables au navigateur, pour écouter ailleurs qu'à la maison |
| **📅 CALENDRIER** | Dates des concours (REF, IARU, internationaux, calendrier mondial) et DXpéditions annoncées, croisées avec votre log |

**Prérequis commun** : ces pages exigent que le serveur local de LogX AI tourne. Si vous ouvrez un fichier directement et voyez le message « OUVERT EN FILE:// — IMPOSSIBLE », cliquez simplement sur le lien proposé vers l'adresse locale (`http://127.0.0.1:8080/...`) : tout fonctionnera.

### 9.1 🗺️ CARTE IA — la carte tactique du concours

C'est votre poste de commandement visuel pendant un concours : d'un coup d'œil, vous voyez qui appeler en priorité, dans quelle direction tourner l'antenne, et où passe la ligne grise. L'écran est divisé en deux : le chat avec l'IA à gauche, la carte à droite (fond sombre en mode nuit, clair en mode jour). Un bandeau de score sous la navigation affiche **SCORE TOTAL**, « BANDE 1 », « BANDE 2 », « QSO TOTAL », « MEILLEUR DX », « LOCATOR », l'horloge « UTC · local » et le badge du concours actif.

#### Les stations par priorité

La carte affiche jusqu'à 25 stations spottées dont la position est connue (locator ou coordonnées), classées par le moteur du logiciel et rafraîchies chaque minute. Une ligne relie votre QTH à chaque station ; les stations déjà contactées passent en gris pointillé avec le statut « ✓ CONTACT DÉJÀ FAIT ». Un clic sur un marqueur affiche **LOCATOR**, **DISTANCE** (km), **FRÉQUENCE** (MHz), **CAP ANTENNE** (degrés + point cardinal) et **BANDE** — de quoi tourner le rotor sans réfléchir.

| Couleur au clic | Signification |
|---|---|
| « 🌟 DX EXCEPTIONNEL » | La station rare du moment, à tenter en priorité absolue |
| « 🔴 HAUTE » / « 🟡 HAUTE » | Fort intérêt pour votre score |
| « 🟠 MOYENNE » | À prendre si l'occasion se présente |
| « 🟢 BASSE » | Points ordinaires |
| « ✓ FAIT » | Déjà dans le log |

#### Les anneaux de distance et l'anneau ★ record

Par défaut, trois anneaux entourent votre QTH : 500 km, 1000 km, et un troisième anneau au rayon de **votre record DX réel, calculé automatiquement à partir de votre log**, étiqueté « Nkm ★ record ». Chaque fois que vous battez votre record, l'anneau s'élargit — c'est votre horizon personnel, plus aucun réglage manuel n'est nécessaire. (Tant qu'aucun contact ne dépasse 1000 km, l'anneau se place à 1600 km, sans l'étoile.)

En cochant la case **🎯 GREAT CIRCLE** (choix mémorisé), vous passez à quatre anneaux standard 1000 / 2000 / 3000 / 4000 km. Point d'honnêteté : ce sont de vraies distances sur le globe, mais la carte reste en projection classique — n'attendez pas l'aspect déformé d'une carte azimutale centrée sur votre QTH.

#### Ligne grise, vues rapides et surcouche propagation

- **Terminateur jour/nuit** : la zone de nuit est dessinée en semi-transparent avec un liseré jaune, recalculée localement toutes les 5 minutes. Rappel utile affiché par le logiciel : le DX sur bandes basses s'ouvre au lever et au coucher du soleil, le long de cette ligne.
- **Vues rapides** : un bouton en en-tête cycle **🗺️ EUROPE** → **🌍 MONDE** → **🇺🇸 USA** → **🇫🇷 FRANCE**. La vue de départ est choisie automatiquement selon le concours configuré (concours HF mondial → monde, ARRL Field Day → USA, REF RPH/QRP → France, sinon Europe).
- **Surcouche 🌍 PROPAGATION** (panneau en haut à droite, activable) : colore le monde selon les chances d'ouverture depuis votre QTH, avec un sélecteur de bande (« Meilleure bande », puis 160 m à 6 m), un curseur horaire de 0 à 24 h (« maintenant » / « +N h ») et un bouton ▶ qui anime les 24 prochaines heures. La légende va de « fermé » à « ouvert » en 5 niveaux.
- **Vos QSO sur la carte** : chaque contact loggé apparaît en marqueur coloré par bande, avec un popup indicatif ✅, locator, bande — mode, distance/points et « 🧭 Cap antenne ».

#### Le chat IA et la veille automatique

Le panneau de gauche donne accès aux boutons rapides **🧠 COACH**, **🎓 DÉBRIEF**, **📡 ANALYSER**, **🏆 SCORE**, **⚡ SPOTS**, **📶 PROP**, **🌍 OUVERTURES**, **🎯 MULTS**, **📋 RÉSUMÉ**. Le panneau **🧠 COACH** (horloge du concours, rythme QSO/h, plan de bande, conseils, recommandation RUN ou S&P) peut être détaché dans une fenêtre séparée pour un deuxième écran. Une analyse lancée continue côté serveur : vous pouvez changer d'onglet et revenir, le résultat vous attendra.

Toutes les 10 minutes, une veille silencieuse tourne en arrière-plan : elle ne vous dérange (bulle « 🤖 VEILLE AUTO », alerte sonore, titre d'onglet clignotant « 🚨 ALERTE DX ! ») que si quelque chose d'urgent apparaît. Vous recevez aussi les alertes « 📈 NOUVEAU MULT spotté », vos règles personnalisées « 🔔 », et les mentions du chat ON4KST (« 💬 ON4KST — X te mentionne »).

### 9.2 🇫🇷 Cartes — départements français et pays DXCC

Cette page transforme votre log en tableau de chasse géographique : verdir les 96 départements français, ou les pays DXCC du monde entier — et surtout savoir **qui peut vous donner ce qui manque, maintenant**.

Le sélecteur **🗺️ ÉCHELLE** propose « 🇫🇷 France (départements) », « 🇪🇺 Europe », « 🌍 Un continent » (avec sous-sélecteur) et « 🌐 Monde (tous les pays) ». L'échelle par défaut suit le type du concours actif (concours départemental → France, concours DXCC → monde) ; si vous choisissez manuellement, votre choix est mémorisé et prime.

#### Vue France

Carte des départements, contactés en vert, volontairement figée (pas de déplacement ni de zoom : c'est un tableau de bord, pas un atlas). Le fond de carte est téléchargé une fois puis disponible hors ligne ; s'il est indisponible, un message le signale et la grille de droite reste utilisable. La barre de progression affiche « N / 96 », le pourcentage, « encore N départements pour verdir la France 🇫🇷 », « + N DOM », et « 🏆 FRANCE ENTIÈREMENT VERTE — bravo ! » à 100 %.

Le panneau de droite contient le « TABLEAU DE CHASSE » (grille des 96), la grille « OUTRE-MER », la légende « Contacté » / « À faire », et surtout « 🎯 CIBLES — QUI PEUT LES DONNER » : pour chaque département manquant, les stations **actuellement spottées sur le cluster** (« ⚡ indicatif + fréquence » = à appeler tout de suite) et les stations connues de votre historique. Comme l'indique la page : « Le département est détecté depuis l'échange reçu, la base d'indicatifs, ou la position du locator (stations françaises). » La progression se rafraîchit toutes les 15 s, les cibles toutes les 60 s.

#### Vues Europe / continent / monde

Carte mondiale des pays DXCC travaillés (en vert) avec compteur « N pays contactés (X%) ». Le panneau latéral liste d'abord « 🎯 NOUVEAUX PAYS SPOTTÉS » (drapeau, indicatif, pays, fréquence, mention « à appeler »), puis tous les pays groupés par continent avec compteur fait/total.

### 9.3 📶 PROPAG — la salle de veille

Cette page rassemble en un seul écran tout ce qui, autrement, vous demanderait dix sites web ouverts : conditions solaires, ouvertures calculées depuis votre QTH, balises, et la preuve que votre propre signal porte. Elle ne traite que de la propagation : les activateurs en l'air et la need list du cluster sont sur la page **🎯 CHASSE** (§9.5). Les panneaux se rafraîchissent seuls (des balises toutes les 5 s à la tropo toutes les 20 min) — laissez la page ouverte sur un coin d'écran.

| Panneau | Ce qu'il apporte |
|---|---|
| « ☀️ SOLEIL & IONOSPHÈRE » (détachable) | 6 tuiles : « SFI », « INDEX K » (verdict « stable » / « agité » / « orage ! »), « INDEX A », « TACHES », « RAYONS X », « AURORE » ; plus l'encart « MUF — FRÉQUENCE MAX UTILISABLE (3000 km) » avec l'ionosonde source |
| « 🧭 OUVERTURES PAR RÉGION » | Tableau par région du monde : cap et distance, meilleure bande avec score, bandes ouvertes, fenêtre horaire UTC. C'est un vrai calcul depuis **votre** QTH (élévation solaire aux deux bouts du trajet, MUF/SFI/K, bonus grey-line), pas une lecture de spots ; score ≥ 62 = bon, ≥ 38 = possible |
| « 📶 CONDITIONS PAR BANDE » | Verdict MUF bande par bande (« ● OUVERTE (MUF) » / « ○ fermée (MUF) » de 160 m à 10 m) et conditions jour ☀️ / nuit 🌙 (source N0NBH) |
| « 🌍 VHF / SPORADIQUE-E » | État des ouvertures Es en Europe et aurore VHF (« ⚡ » si ouvert) |
| « 📡 BALISES NCDXF/IBP » | Quelle balise du réseau international émet **en ce moment** sur chaque bande (elles tournent toutes les 10 s) : fréquence, indicatif, QTH, cap. Entendre une balise = la bande est ouverte vers sa région |
| « 🌡️ PRÉVISION TROPO (DUCTING) » | Niveau (ducting/super/normal/sous-réfraction), gradient, inversion 🔺, conseil et tendance, pour la VHF/UHF |
| « ☄️ MÉTÉORES (MS 6 m / 2 m) » | Niveau meteor-scatter, meilleur créneau, distance, essaims actifs ou à venir (ZHR) |
| « 🛰️ SATELLITES » | Pas de calcul local : liens directs vers Heavens-Above (prochains passages visibles, ISS…) et l'AMSAT, pré-réglés sur votre locator et altitude. Sans locator configuré, la page vous invite à le renseigner dans **⚙ CONFIG** |
| « 🌐 SIGNAL ENTENDU — PSK » | Où **votre** signal est décodé (PSK Reporter) : récepteur, bande, SNR, cap, distance ; lien « ↗ carte complète » pré-filtré sur votre indicatif |
| « 📻 SIGNAL CW ENTENDU — RBN » | Les skimmers CW qui vous reçoivent : spotter, bande, SNR, fréquence, vitesse wpm. Si vide : « Aucun skimmer ne t'entend en CW pour l'instant (transmets en CW). » |
| « 🌙 EME — REBOND LUNAIRE » | Voir la sous-section dédiée ci-dessous |

### 9.4 🌙 EME — rebond lunaire : deux locators suffisent

Le panneau « 🌙 EME — REBOND LUNAIRE » vous donne tout ce qu'il faut pour préparer un QSO par réflexion sur la Lune, sans logiciel d'éphémérides séparé. Point remarquable : il ne demande **que deux locators** — le vôtre (renseigné dans **⚙ CONFIG**, altitude optionnelle) et celui de votre correspondant. Tout le calcul astronomique est fait localement sur votre machine, sans aucune connexion internet. Si le message « Bibliothèque 'ephem' non installée » apparaît, un composant de calcul astronomique manque à votre installation : reportez-vous au chapitre d'installation.

Le panneau affiche en permanence :

- « 🌗 Position : Az X° / El Y° » avec le badge « ● visible » ou « ○ sous l'horizon » — pointez l'antenne sur ces valeurs ;
- « 📏 Distance : N km · Phase : N% » et « 🌅 Lever : HH UTC · 🌇 Coucher : HH UTC » ;
- « 📻 Doppler estimé » sur 144,1 MHz et 432,1 MHz : c'est le décalage **aller-retour** Terre-Lune-Terre (rotation terrestre + mouvement orbital lunaire compris), de l'ordre de quelques centaines de Hz sur 144 MHz — indispensable pour savoir où chercher le signal de retour.

Pour planifier un sked : saisissez le locator de l'autre station dans le champ « Locator correspondant (ex: FN31pr) » puis cliquez **🔍 Fenêtre commune (48h)**. Le logiciel balaie les 48 prochaines heures par pas de 10 minutes et liste les créneaux « 🌙 début → fin UTC » où la Lune est visible **simultanément** des deux QTH — la condition nécessaire à tout QSO EME. Rappel honnête : le panneau vous dit *quand* tenter, pas *si* votre station suffit — l'EME reste exigeant en antennes et en puissance, et le bilan de liaison reste à évaluer de votre côté.

### 9.5 🎯 CHASSE — qui contacter maintenant

Cette page répond à une seule question, celle qu'on se pose en permanence pendant une session : **qui est-ce que je contacte maintenant ?** Elle regroupe les cinq listes de cibles, qui vivaient auparavant au milieu des indices solaires de la page PROPAG.

Sa mise en page est faite pour l'opération : **la page ne défile jamais**. L'écran est découpé une fois pour toutes — une grille 2×2 à gauche pour les quatre programmes d'activation, la need list du cluster sur toute la hauteur à droite — et c'est chaque liste qui défile dans son propre panneau. Vous pouvez donc la laisser ouverte sur un second écran sans jamais avoir à chercher un panneau.

| Panneau | Ce qu'il apporte | Rafraîchissement |
|---|---|---|
| « 🏞️ ACTIVATEURS POTA EN DIRECT » | Spots POTA confirmés sur l'air : indicatif, bande, référence, fréquence, mode, nom du parc | 2 min |
| « 🏔️ ACTIVATEURS SOTA EN DIRECT » | Idem pour les sommets SOTA, avec altitude et points du sommet | 1 min |
| « 🌳 ACTIVATEURS WWFF EN DIRECT » | Idem pour les réserves naturelles WWFF | 1 min |
| « 🏰 CHÂTEAUX WCA/COTA — ANNONCÉS » | Attention, différent des trois précédents : ce sont des activations **annoncées à l'avance**, pas des spots confirmés sur l'air | 5 min |
| « 🎯 CLUSTER — NEED LIST » (détachable) | Colonne de droite, pleine hauteur : voir ci-dessous | 1 min |

Le panneau « 🎯 CLUSTER — NEED LIST » présente les spots du cluster valorisés pour **votre** concours, avec les filtres « TOUS » / « 📈 MULTS » / « SANS DUPES ». Chaque spot affiche sa pastille de priorité, la valeur « +N pts » ou « DÉJÀ FAIT », le badge « 📈 NOUVEAU MULT », le cap et la distance — et deux boutons d'action directe si le pilotage matériel est activé dans la configuration : **▶ QSY** règle votre radio sur la fréquence, **🧭 N°** pointe votre rotor. Le bouton **⇱** détache le panneau dans une fenêtre séparée. Tant qu'aucun spot n'est encore arrivé, la page vous le dit : « lance un refresh depuis la CARTE IA (📡 ANALYSER) », ou attendez simplement la veille automatique.

### 9.6 📡 WEBSDR — écouter ailleurs qu'à la maison

Un WebSDR est un récepteur radio installé chez un autre radioamateur ou une association, pilotable depuis votre navigateur. Trois usages concrets : vérifier comment votre propre émission est reçue ailleurs, écouter une bande fermée chez vous mais ouverte là-bas, et repérer une station avant de tenter le contact.

L'annuaire est volontairement **court et vérifié à la main** : chaque récepteur a été confirmé actif au moment de son ajout, ce n'est pas un agrégateur automatique. Sept récepteurs actuellement :

| Récepteur | Lieu | Type / couverture |
|---|---|---|
| SHTSF — Société Havraise de Télégraphie Sans Fil | Le Havre, France | KiwiSDR, HF 10 kHz–30 MHz |
| WebSDR University of Twente | Pays-Bas | « Le tout premier WebSDR au monde (2008) » |
| Northern Utah WebSDR | USA | HF + VHF/UHF |
| MWRS — Manly-Warringah Radio Society | Sydney, Australie | KiwiSDR |
| APPR WebSDR | Brésil | WebSDR |
| VE6JY | Canada | « Station de contest multi-multi bien connue » |
| SDR Hasenberg | Suisse | KiwiSDR |

À l'ouverture de la page, chaque récepteur est testé une seule fois (4 secondes maximum) et reçoit un badge « 🟢 en ligne » ou « 🔴 injoignable ». Prenez ce badge pour ce qu'il est — l'encart « ⚠ Disponibilité non garantie. » le rappelle : ce sont des serveurs **bénévoles**, qui peuvent être saturés ou arrêtés à tout moment. Filtrez par « 🌍 Tous les continents » ou par le champ « Filtrer par nom, pays, bande… », puis cliquez **▶ Ouvrir dans un nouvel onglet** : le récepteur s'ouvre sur son propre site, indépendant de LogX AI.

### 9.7 📅 CALENDRIER — concours et DXpéditions annoncées

Cette page répond à deux questions : « quel concours ce week-end ? » et « quelle expédition rare arrive, et me manque-t-elle ? ». Les dates sont recalculées automatiquement chaque année (sous-titre : « Dates calculées automatiquement · Mise à jour annuelle ») ; la barre d'état affiche la dernière vérification et le bouton **🔄 VÉRIFIER LES RÈGLEMENTS**.

| Onglet | Contenu |
|---|---|
| « ⭐ REF / IARU / Internationaux » (par défaut) | Le calendrier interne, trié à partir d'aujourd'hui et groupé par mois. Chaque concours : compte à rebours (« ⚡ AUJOURD'HUI », « Dans Nj »), badge organisateur, badge « ✓ règlement suivi » (dates et règlement re-vérifiés chaque année), échange, bandes/modes/format de log, et les boutons **▶ DÉMARRER** (ouvre la configuration avec le concours présélectionné) et **📄 Règlement**. Un clic ouvre la fiche détaillée (« DATE », « ÉCHANGE », « SCORING », « MULTIPLICATEUR », « FORMAT LOG », « DÉLAI ENVOI », « SOUMISSION LOG », « NOTES ») avec **▶ DÉMARRER CE CONCOURS** |
| « 🌍 MONDIAL WA7BNM » | Le calendrier mondial de contestcalendar.com, trié par prochaine occurrence. Ces concours ne sont **pas** vérifiés par LogX AI : badge « ⚠ à confirmer », à contrôler manuellement dans la configuration avant usage. Boutons **▶ PRÉPARER** et **📄 Détails** |
| « 🏝️ DXPEDITIONS (NG3K) » | Les expéditions annoncées (flux public NG3K ADXO, mis en cache 1 h). Chaque ligne : dates, « INDICATIF — entité », informations QSL et source. Le logiciel croise automatiquement chaque entité avec **votre log** : badge « 🆕 NOUVEAU PAYS » si l'entité DXCC ne figure pas encore dans votre log, « ✓ déjà travaillé » sinon. Pas de bouton démarrer : ce ne sont pas des concours, c'est votre liste de chasse |

Une rangée de filtres commune complète les onglets : « TOUS », « ⭐ REF », « 🌍 IARU », « 📡 CQ », « 📶 VHF », « 🌐 HF », « 🔜 À VENIR (31 j) » et « 🆕 NOUVEAU PAYS » — ce dernier n'agit que dans l'onglet DXpéditions, où il ne garde que les entités que vous n'avez jamais contactées : l'écran idéal à consulter avant chaque saison DX.

---

## 10. Activations POTA, SOTA, WWFF, IOTA, WCA

Que vous activiez un parc, un sommet ou un château, LogX AI intègre les bases officielles de référence et compte vos QSO en temps réel : vous savez à tout moment si votre activation est validée, sans pointage manuel ni tableur à côté. Le logiciel vous montre aussi les autres activateurs actuellement en l'air, pour la chasse.

### Les cinq programmes avec base intégrée

Les bases officielles sont téléchargées automatiquement en arrière-plan, conservées localement et rafraîchies au bout de 30 jours. Au tout premier lancement, l'interface affiche « ⏳ Chargement de la base (peut prendre jusqu'à une minute la première fois)… » — rien n'est bloqué pendant ce temps, et la saisie manuelle d'une référence reste toujours possible.

| Programme | Base intégrée (source officielle) | Spots en direct | Minimum de QSO |
|---|---|---|---|
| **POTA** — Parks on the Air | ~93 600 parcs (actifs et inactifs), base officielle pota.app | Oui, actualisés toutes les 2 min | 10 |
| **SOTA** — Summits on the Air | ~181 000 sommets, liste officielle sota.org.uk | Oui (3 dernières heures, même source que SOTAwatch), actualisés toutes les 1 min | 4 |
| **WWFF** — Flora & Fauna | ~68 400 réserves, répertoire officiel wwff.co | Oui, via le « Spotline » officiel WWFF, actualisés toutes les 1 min | 44 |
| **IOTA** — Islands on the Air | ~1 180 groupes d'îles + ~13 000 noms d'îles (la recherche « Agalega » trouve bien AF-001) | Non — aucune source de spots officielle et fiable n'existe pour IOTA ; plutôt que d'afficher des données douteuses, LogX n'en affiche pas | 1 |
| **WCA** — World Castles Award | ~71 300 châteaux, classeur officiel wcagroup.org (201 pays). La source ne fournit aucune coordonnée GPS | Pas de spots temps réel — LogX affiche à la place les **annonces** d'activations planifiées publiées par le WCA, actualisées toutes les 15 min (flux RSS de blog, pas un flux temps réel) et clairement étiquetées comme telles | 50 |

Deux points d'honnêteté : ces bases et spots proviennent de services bénévoles tiers (POTA, SOTA, WWFF, IOTA, WCA) ; si l'un d'eux est momentanément indisponible, LogX affiche le dernier résultat connu plutôt qu'une liste vide. Et LogX est en lecture seule : il ne publie jamais de spot POTA à votre place.

### Et ARLHS ? Sélectionnable, mais sans base intégrée

Le programme des phares **ARLHS — Lighthouses (2 QSO)** est bien proposé dans la liste, mais volontairement **sans** base de références téléchargée : la liste officielle des phares n'est pas librement réutilisable, et la permission écrite nécessaire n'a pas été obtenue. LogX respecte cette règle plutôt que de la contourner. Concrètement : vous saisissez votre référence à la main, LogX vérifie seulement son format (XXX-NNN, ex. FRA-113, ou USA-129H pour un phare historique), et il n'y a ni auto-complétion ni recherche à proximité pour ce programme. Le minimum de 2 QSO vient du règlement officiel (« Two stations must be worked from each light activated »).

### Déclarer votre activation

Tout se passe dans CONFIG, carte **🏝️ 14. EXPÉDITION / ACTIVATION**, section **🏕️ ACTIVATION (POTA / SOTA / IOTA / WWFF / ARLHS / WCA)** :

1. **PROGRAMME** : choisissez votre programme dans la liste (« POTA — Parks on the Air (10 QSO) », « SOTA — Summits on the Air (4 QSO) », etc.), ou laissez « Désactivé (concours normal) » hors activation.
2. **MA RÉFÉRENCE ACTIVÉE** : tapez le code (ex. FR-0123) **ou le nom** du lieu — l'auto-complétion interroge la base intégrée, sans tenir compte des accents, dès 2 caractères. La validité du format s'affiche sous le champ, avec un rappel des formats attendus : « POTA : XX-NNNN · SOTA : XX/RR-NNN · IOTA : CC-NNN · WWFF : XXFF-NNNN · ARLHS : XXX-NNN · WCA : X-NNNNN ».

### Les références à proximité (dont les sommets SOTA)

Sous la référence, un bloc « À PROXIMITÉ » vous évite de chercher le bon code sur une carte : cliquez **🔍 Chercher autour de moi** et LogX liste les références situées autour de votre locator, avec distance et point cardinal, dans un rayon réglable (60 km par défaut, de 5 à 500 km). Un clic sur un résultat remplit directement le champ de référence. Pour SOTA, c'est l'équivalent du « Range Calculator » de sotamaps.org — mais calculé localement, sur la base déjà chargée, sans aucun service tiers ; idéal pour planifier une sortie ou trouver un second sommet à enchaîner.

Deux exceptions, affichées honnêtement dans l'interface : pour WCA, le bloc indique « ⚠️ Non disponible pour ce programme : la base officielle ne fournit aucune coordonnée GPS par référence… La recherche par nom reste disponible » ; et pour ARLHS, ni suggestion ni proximité (pas de base, voir plus haut).

### La barre de progression et le P2P dans le logbook

Dès qu'un programme et une référence sont configurés, une barre d'activation apparaît dans le logbook. Elle affiche : le programme, votre référence (en rouge si le format est invalide), la progression « x/N » en gros et en vert (N étant le minimum du programme), une barre de progression, puis **✅ VALIDÉE** une fois le seuil atteint — ou « encore N » en jaune tant qu'il manque des QSO. Elle se met à jour toutes les 15 secondes. Seuls comptent les QSO portant **votre** référence d'activation : les QSO d'un autre concours ou d'une autre activation ne polluent jamais le compteur.

À droite de la barre, un compteur dédié suit vos contacts avec d'autres activateurs, sous le nom consacré par chaque programme : « Park-to-Park », « Summit-to-Summit », « Island-to-Island », « Flora-to-Flora », « Light-to-Light » ou « Castle-to-Castle ». Pour l'alimenter, un champ de saisie supplémentaire apparaît en mode activation : **RÉF. CORRESPONDANT (P2P / S2S)** (« si le correspondant active aussi (ex: DL-0042) »). Ces informations sont écrites dans l'export ADIF dans les champs standard (SIG / MY_SIG) lus par les sites d'upload POTA, SOTA et WWFF — votre fichier est donc directement acceptable pour la validation officielle.

### La chasse : les activateurs en direct

Sur la page **🎯 CHASSE** (onglet à droite de PROPAG, voir §9.5), quatre panneaux montrent qui est actuellement (ou bientôt) en l'air :

- **🏞️ ACTIVATEURS POTA EN DIRECT**
- **🏔️ ACTIVATEURS SOTA EN DIRECT**
- **🌳 ACTIVATEURS WWFF EN DIRECT**
- **🏰 CHÂTEAUX WCA/COTA — ANNONCÉS** (activations planifiées, annoncées à l'avance — pas des spots temps réel)

C'est l'outil du chasseur : repérez un activateur, contactez-le, et si vous êtes vous-même en activation, notez sa référence dans **RÉF. CORRESPONDANT (P2P / S2S)** pour marquer le contact programme-à-programme.

## 11. Multi-poste, expédition, radioclub et écran mural

Un seul PC fait tourner LogX AI ; tous les autres postes — ordinateurs, téléphones, tablettes — s'y connectent par simple navigateur sur le même WiFi et loggent dans le même log commun, sans rien installer. Ce chapitre couvre aussi la saisie rapide de pile-up, l'écran mural pour projecteur, le mode radioclub et la cohabitation avec N1MM ou DXLog.

### Le log partagé en WiFi, sans configuration

Lancez LogX AI sur un seul PC. Sur les autres postes, ouvrez simplement le logbook dans un navigateur : le bandeau réseau du logbook affiche « Connecté au serveur », le nombre de « Postes connectés », et surtout la ligne « Autres postes (même WiFi) : » avec l'adresse exacte à utiliser et un bouton **📋 COPIER** — l'adresse est copiée dans le presse-papier avec le message « Colle-la dans le navigateur des autres postes (même WiFi). » (si le navigateur refuse l'accès au presse-papier, l'adresse s'affiche pour copie manuelle). En cas de coupure, le bandeau passe à « Hors ligne — log local uniquement » : les QSO saisis sont mis en file d'attente puis resynchronisés automatiquement au retour du réseau.

### Sur téléphone ou tablette

Dans CONFIG, carte **🏝️ 14. EXPÉDITION / ACTIVATION**, le bloc **📱 CONNECTER UN TÉLÉPHONE / TABLETTE** liste les adresses détectées sur votre réseau local, avec cette consigne : « Sur le même WiFi, ouvre cette adresse sur ton téléphone, puis « Ajouter à l'écran d'accueil » : l'appli s'installe et tourne en plein écran (PWA) ». Il existe en outre une page « Mobile Terrain (/P) » spécialement pensée pour le portable VHF/UHF (144/432 MHz) sur le terrain.

### Le chat entre opérateurs

En multi-opérateur, un panneau **💬 CHAT MULTI-OP** est fixé en bas à droite du logbook : repliable, avec un badge rouge pour les messages non lus. Chaque message est horodaté (HH:MM UTC) et signé de l'opérateur et de l'indicatif ; les messages font 500 caractères maximum et les 200 derniers sont conservés. Pratique pour « QSY 20 m ? » sans crier à travers la pièce. Le panneau est masqué quand vous opérez seul.

### La saisie simplifiée d'expédition

Dans la carte 14, section **🏝️ MODE EXPÉDITION** : plusieurs postes sur le même site (un par bande, voire trois par bande en CW/SSB/FT8) loggent dans le même log commun, chacun depuis son navigateur avec son opérateur sélectionné.

Le réglage **MODE EXPÉDITION** → « Activé — juste indicatif + RST envoyé/reçu » allège la saisie pour le pile-up : « pas de n° de série ni locator, seulement l'indicatif et les reports (59, 55, 44…) », et plus d'avertissement de locator vide. Le réglage est partagé par le serveur : tous les postes l'héritent automatiquement, même sans avoir ouvert la page CONFIG.

Garde-fou important : si un **vrai concours** est sélectionné (sans programme d'activation), la saisie simplifiée ne s'applique pas — le numéro de série et le locator restent affichés, car le règlement en a besoin pour le score (ex. les concours REF comptés en km × locators). Impossible donc de saboter son score de concours par un réglage d'expédition oublié.

Deux options d'expédition complètent la section, toutes deux facultatives :

- **CLUB LOG LIVE STREAM** → « Activé — pousser chaque QSO en temps réel » : chaque QSO ajouté est envoyé à Club Log immédiatement, en arrière-plan (aucune latence ajoutée à la saisie). Nécessite vos identifiants Club Log dans la section QSL (email, indicatif, mot de passe et clé API — service tiers gratuit mais compte requis).
- **AUTO-SPOT DX CLUSTER** → « Activé — bouton 📡 SELF-SPOT dans le logbook » : publie votre indicatif et votre fréquence sur le cluster, et attend la confirmation du nœud (résultat « confirmé », « envoyé mais non confirmé » ou refus). Le champ **NŒUD CLUSTER (host : port)** est prérempli avec VE7CC, qui « accepte le spot avec le seul indicatif. D'autres nœuds exigent une inscription. » Attention affichée dans l'interface : « ⚠️ Interdit par certains règlements en single-op. »

### L'écran mural

L'écran mural transforme n'importe quel écran ou projecteur en tableau de bord temps réel de la station — et il « marche dans n'importe quel mode d'utilisation (concours, expédition, radioclub, ou même seul) — utile pour suivre les QSO depuis une autre pièce ». Ouvrez-le par le bouton **🖥️ OUVRIR L'ÉCRAN MURAL** de CONFIG ou le bouton **🖥️ MUR** du logbook, puis F11 pour le plein écran. Il doit être ouvert via le serveur (le bouton s'en charge) et ne dépend d'aucun service en ligne.

Contenu :

- **En-tête** : indicatif de la station en très gros, concours en cours, horloge UTC.
- **Quatre compteurs** : « QSO » (total), « QSO / H » (dernière heure glissante), « STATIONS » (indicatifs uniques), « ODX (KM) » avec l'indicatif du meilleur DX.
- **Flux central ⚡ DERNIERS QSO — LOG COMMUN** : les 25 derniers QSO, avec un flash sur chaque nouveau et le rythme instantané (« ~N/h sur 10 min »).
- **Colonne de droite** : **📊 PAR BANDE** (barres), **🎙 PAR MODE** et **👤 PAR OPÉRATEUR** (pastilles).

L'affichage se rafraîchit toutes les 3 secondes, suit le thème jour/nuit de la page principale, et montre l'intégralité du log commun — sur une expédition, le mur affiche tout, sans dépendre du concours sélectionné. Les colonnes du flux se personnalisent dans CONFIG (« ÉCRAN MURAL — CHAMPS À AFFICHER ») : Heure, 🏴 Drapeau, Pays, Prénom, Bande, Fréquence, Mode, Report (RST), Opérateur — « L'indicatif est toujours affiché. Le prénom n'apparaît que pour les indicatifs déjà consultés via QRZ. »

### Le mode RADIOCLUB

Le nombre d'opérateurs dépend du mode d'utilisation choisi :

| Mode d'utilisation | Opérateurs maximum |
|---|---|
| LOGBOOK SIMPLE | 1 |
| CONCOURS / EXPÉDITION | 5 (OP1–OP5, aligné sur l'export EDI) |
| **🏛️ RADIOCLUB — plusieurs postes, jusqu'à 40 opérateurs** | 40 |

Chaque opérateur a sa couleur dans le logbook et l'écran mural. Le mode RADIOCLUB ajoute la section **POSTES RADIO** (jusqu'à 20) : « Les positions physiques du club (ex. HF1, VHF, Salle jeunes) — repère informatif affiché à la saisie QSO. » Idéal pour savoir qui logge depuis quel poste un jour d'activité du club.

### Cloud Sync : relier des sites distants par un dossier synchronisé

Le WiFi partagé couvre un même lieu ; pour combiner les QSO avec un **autre** poste distant, CONFIG carte **☁️ 8. MULTI-POSTE & CLOUD SYNC**, section **☁️ CLOUD SYNC (multi-poste, sans compte ni service en ligne)**. Le principe : chaque poste pointe vers le **même** dossier déjà synchronisé par votre outil habituel (Synology Drive, Dropbox, OneDrive…) et voit les QSO des autres — aucun compte à créer, aucun service LogX en ligne. À ne pas confondre avec la SAUVEGARDE, qui fait des instantanés à sens unique.

Réglages : **MODE** (« Désactivé », « Synchronisation complète (lit + écrit) », ou « Envoi seul (écrit, ne récupère rien) » pour un poste isolé qui alimente sans rien récupérer), **DOSSIER PARTAGÉ** (vide = même dossier que la sauvegarde ; il doit être identique sur tous les postes ; conseil de l'interface : réglez ce dossier en « toujours conserver sur cet appareil » dans votre outil de synchronisation, pour éviter les fichiers-placeholder téléchargés à la demande), **INTERVALLE (min)** (1 à 60, 3 par défaut), et un bouton **☁️ SYNCHRONISER MAINTENANT** pour forcer un passage.

### Cohabiter avec N1MM ou DXLog

Si une partie de l'équipe logge sous N1MM+ ou DXLog, la section **🌐 RÉSEAU ADIF (N1MM / DXLog / loggers tiers)** (même carte 8) fait dialoguer les deux mondes en temps réel via le format de diffusion réseau de N1MM (UDP, port 12060 par défaut). Quatre modes : « Désactivé », « Réception seule (importer leurs QSO) », « Émission seule (leur envoyer nos QSO) », « Réception + émission » ; le champ **IP CIBLE (émission)** vise par défaut tout le réseau local, ou une IP précise.

L'interface affiche la marche à suivre côté logiciels tiers : dans N1MM, « Config → Config Ports → Broadcast Data → cocher « Contact », IP de ce PC, port 12060 » ; dans DXLog, « Options → Broadcast → QSOs (format « N1MM-like ») ». Les QSO reçus passent par la même déduplication que la saisie manuelle (pas de doublons), et chaque QSO saisi dans LogX est rediffusé aux autres loggers.

---

## 12. Diplômes, QSL et historique à vie — le carnet permanent

Le score d'un concours s'arrête à la fin du concours ; vos diplômes, eux, se construisent sur toute une vie de trafic. LogX AI tient donc, en parallèle du log actif, un **carnet permanent** : tous vos QSO — concours en cours, concours archivés, imports d'anciens logs — sont fusionnés, dédupliqués et enrichis (pays DXCC, continent, zone CQ, département français) pour vous dire à tout instant ce qui vous manque encore. Tout ce calcul est fait localement, sans aucune connexion Internet.

### 12.1 Le modal Diplômes

Dans la barre du **📋 LOGBOOK**, cliquez sur **🏅 DIPLÔMES** (infobulle : « Diplômes (DXCC, départements) travaillés/confirmés à vie + envoi/synchro QSL (eQSL, ClubLog, LoTW) »). La fenêtre **🏅 DIPLÔMES & QSL** s'ouvre et présente, de haut en bas :

| Section | Ce qu'elle affiche |
|---|---|
| **📊 CARNET PERMANENT** | Le nombre total de QSO à vie (log actif + toutes les archives) |
| **🌍 DXCC (pays)** | « X travaillés · Y confirmés » |
| **🇫🇷 Départements métropole** | « X/96 · Y conf. » avec barre de progression, plus **🏝️ Outre-mer** si vous en avez, et la liste « Départements manquants » (40 affichés au maximum) |
| **🗺️ Continents** | Les continents travaillés, avec le détail par bande (par ex. « 144 MHz : N QSO / M DXCC ») |
| **🧮 WORKED MATRIX — bande × mode** | Une grille bande × CW / PHONE / DIGITAL. SSB, USB, LSB, AM et FM comptent en PHONE ; FT8, FT4, RTTY, PSK, JS8, etc. en DIGITAL. Chaque case indique les QSO travaillés et, en vert, les confirmés — c'est l'outil idéal pour repérer les cases vides à remplir pour le DXCC ou le WAS |
| **📮 QSL** | Le nombre de QSO confirmés, et les boutons d'envoi/synchro décrits au §12.4 |

**Travaillé ou confirmé ?** Le « travaillé » est calculé à partir de vos propres QSO. Le « confirmé » vient exclusivement des confirmations importées depuis LoTW (voir §12.4). Tant que vous n'avez jamais lancé cette synchro, tout le carnet fonctionne normalement mais les compteurs « confirmés » restent à zéro — le modal l'indique clairement : « Aucune confirmation importée — synchronise LoTW ci-dessous pour voir le “confirmé”. »

### 12.2 Records DX par bande

LogX AI calcule votre plus grande distance travaillée **pour chaque bande**, à partir du vrai locator de chaque QSO — jamais d'une valeur déclarée à la main. Les distances invraisemblables pour la bande (locator erroné, contact EME mal étiqueté) sont filtrées automatiquement. Le record apparaît dans le RÉSUMÉ de la page CONFIG (« Record DX : X km ») et le copilote IA le connaît aussi : il en tient compte quand il évalue vos chances sur un spot lointain.

### 12.3 « New one » signalé pendant la saisie

C'est là que le carnet permanent devient un réflexe de trafic. Dès que vous tapez un indicatif dans le **📋 LOGBOOK**, le panneau « déjà contacté » interroge tout votre historique et affiche :

- 🌟 « NOUVEAU PAYS : X (jamais contacté) » — ou « X nouveau sur 144 MHz » si le pays est déjà travaillé mais pas sur cette bande ;
- 🌟 « NOUVEAU DÉPARTEMENT : 15 Cantal » ;
- votre historique complet avec cette station : « N QSO sur 144/432 MHz · 2 confirmés · dernier JJ/MM/AAAA », plus les 3 QSO les plus récents (date, bande, mode, concours, ✅ si confirmé) — ou « jamais contacté ».

Le tout porte sur votre vie entière de trafic, tous concours et archives confondus, à la manière des fiches « previous contacts » de Log4OM ou HRD.

En complément, le coach surveille les stations actuellement spottées sur le cluster : celles qui vous apporteraient un pays DXCC ou un département **jamais travaillé à vie** vous sont poussées automatiquement (8 au maximum), sans aucune action de votre part. Ne les confondez pas avec les cibles pays/départements du concours en cours, qui ne concernent que le concours actif.

### 12.4 QSL : cinq services, un clic chacun

Les identifiants se configurent une fois pour toutes dans CONFIG, popup **📮 12. QSL & DIPLÔMES**. Les boutons d'action, eux, sont dans le modal **🏅 DIPLÔMES & QSL** :

| Service | Sens | Bouton | À savoir |
|---|---|---|---|
| eQSL | Envoi du log | **⬆ eQSL** | Identifiant + mot de passe eqsl.cc, envoi du log complet en ADIF |
| ClubLog | Envoi du log | **⬆ ClubLog** | Email + indicatif + mot de passe + clé API (à créer sur clublog.org, Settings → API keys) |
| QRZCQ | Envoi du log | **⬆ QRZCQ** | Indicatif + clé API (qrzcq.com → Développeurs) |
| HRDLog | Envoi du log | **⬆ HRDLog** | Envoi QSO par QSO (le service n'accepte pas les lots) : « peut être lent sur un gros log ». Résultat affiché « X/N QSO envoyés » ; l'envoi s'arrête de lui-même après 5 échecs consécutifs pour ne pas geler le logiciel hors réseau |
| LoTW | **Import des confirmations uniquement** | **⬇ Confirmations LoTW** | Télécharge votre rapport de confirmations avec vos identifiants LoTW — **sans installer TQSL**. En revanche, l'envoi de votre log VERS LoTW n'est pas géré : il exige la signature par certificat, gardez TQSL pour publier (la note sous le champ LoTW en CONFIG le rappelle : « Import des confirmations (pas d'upload : garde TQSL pour publier) ») |

Points importants :

- **Portée de l'envoi** : les boutons d'upload envoient les QSO du **concours actif** (concours + année en cours). S'il n'y a rien à envoyer, le logiciel refuse avec le message « Aucun QSO à envoyer ».
- **Effet de l'import LoTW** : les confirmations téléchargées sont fusionnées avec les existantes (rien n'est perdu), puis le carnet permanent se recalcule — le « confirmé » apparaît dans le modal environ une seconde après.
- **Mode expédition** : l'option **ClubLog Live Stream** pousse chaque QSO en temps réel vers ClubLog, pour que les chasseurs suivent votre expédition en direct. La sauvegarde de la CONFIG est bloquée si vous activez le Live Stream sans avoir renseigné les 4 identifiants ClubLog.
- **Sécurité** : tous les identifiants QSL sont « Stockés côté serveur uniquement — jamais renvoyé au navigateur ni à l'IA ». Le modal affiche la date de la dernière synchro de chaque service (« eQSL envoyé le … · LoTW synchro le … »), ou « aucune synchro encore ».

Ces services sont pour la plupart gérés par des bénévoles ou de petites équipes : une indisponibilité ponctuelle de leur côté n'est pas un dysfonctionnement de LogX AI — réessayez simplement plus tard.

## 13. Le copilote IA

Le copilote transforme le flot brut de spots, de scores et de règlements en conseils exploitables : « qui appeler maintenant, sur quelle fréquence, pour combien de points ». C'est la **seule** fonction du logiciel qui nécessite une clé API auprès d'un fournisseur d'IA — tout le reste (log, score, carte, cluster, QSL, diplômes, exports) fonctionne sans. Le texte d'aide du champ le dit exactement : « Indispensable pour utiliser le copilote IA — reste stockée uniquement sur ton poste, jamais partagée. Sans elle, le logiciel fonctionne normalement, seul le copilote IA est indisponible. »

### 13.1 Choisir son fournisseur

Dans CONFIG, carte **🤖 15. ASSISTANT IA**, six fournisseurs sont proposés, chacun avec ses modèles :

| Carte | Modèles proposés |
|---|---|
| 🤖 **Claude** / Anthropic | Claude Sonnet 4.6 (recommandé) · Claude Opus 4.8 (puissant) · Claude Haiku 4.5 (rapide) |
| 💚 **ChatGPT** / OpenAI | GPT-4o (recommandé) · GPT-4o mini (rapide/économique) · o1-mini (raisonnement) |
| 🔵 **Gemini** / Google | Gemini 2.0 Flash (recommandé) · Gemini 2.5 Pro (puissant) · Gemini 1.5 Flash (rapide) |
| 🇫🇷 **Mistral AI** / France | Mistral Large (recommandé) · Mistral Small (rapide/économique) |
| ⚡ **Grok** / xAI | Grok 4.5 (recommandé) · Grok 4.3 (contexte long, 1M tokens) · Grok Build 0.1 (économique) |
| 🐋 **DeepSeek** | DeepSeek V4 Flash (recommandé/rapide) · DeepSeek V4 Pro (puissant) |

Une clé API s'obtient sur le site du fournisseur choisi (compte développeur, souvent payant à l'usage — quelques centimes par analyse en pratique). Collez-la dans le champ **CLÉ API** ; le format attendu s'affiche en exemple (sk-ant-api03-…, sk-…, AIza…, xai-…). La note sous le champ précise : « 🔒 Stockée localement par fournisseur — jamais partagée ». Chaque fournisseur mémorise **sa** clé : vous pouvez basculer de Claude à Mistral puis revenir sans jamais resaisir. Les appels partent toujours de votre poste, via le serveur local, directement vers le fournisseur choisi — aucun intermédiaire.

### 13.2 Ce que le chat sait déjà tout seul

Dans l'onglet **CARTE IA**, vous posez votre question et c'est tout : le contexte est assemblé automatiquement à chaque analyse, vous n'avez **rien à copier-coller**. L'IA reçoit :

- votre station : indicatif, locator, coordonnées, puissance, QRP/portable, votre record DX réel par bande, la position de la Lune si vous faites de l'EME ;
- le concours actif avec ses règles officielles complètes : dates calculées automatiquement, barème, stratégie (des blocs dédiés existent pour CQ WW, IARU VHF/UHF, Rallye des Points Hauts, ARRL Field Day, CQ WPX, REF HF…) ;
- vos bandes et modes actifs, vos seuils DX par bande ;
- le terrain en temps réel : score et QSO par bande, les 30 derniers QSO du log partagé multi-op, les spots cluster par bande avec le marquage « ✓FAIT » sur ceux déjà travaillés, les mentions ON4KST, les ouvertures de propagation par région, et une vérification croisée des locators (log contre cluster) qui signale les anomalies ;
- un guide d'utilisation du logiciel — vous pouvez donc aussi lui demander « où est le bouton pour… ».

La réponse suit un format imposé : une liste **📡 CONTACTS À FAIRE** classée #1 à #5, deux lignes par station avec la fréquence exacte, les points rapportés, le cap antenne et un niveau de confiance. Des boutons rapides évitent même de taper : **ANALYSER**, **SCORE**, **SPOTS**, **PROP**, **MULTS**, **RÉSUMÉ**.

### 13.3 Le débrief post-concours

Après le concours, cliquez sur **🎓 DÉBRIEF** (infobulle : « Analyse du concours écoulé : points forts, axes d'amélioration, ce qui a coûté des points »). Le logiciel calcule d'abord lui-même des statistiques exactes — QSO par heure, répartition par bande, meilleurs DX, kilomètres, périodes de silence — puis les transmet à l'IA qui en fait le récit. Les chiffres viennent donc toujours de vos données, jamais de l'imagination du modèle.

### 13.4 L'analyse de règlement

Fonction précieuse avant un concours inconnu : donnez au copilote le règlement officiel (adresse web, PDF — y compris scanné ou plein de tableaux, envoyé tel quel au modèle chez Anthropic — dans n'importe quelle langue), et il produit une définition de concours en français, prête pour le moteur de score. Le résultat passe par une **passe de vérification adversariale** sur huit pièges classiques des règlements réels : restrictions de participants, périodes off-time, multiplicateurs pondérés par bande, contenu exact de l'échange, dates et week-ends, QTC, date limite et format du log. Vous recevez la proposition accompagnée de citations du texte original et d'avertissements.

**Rien n'est enregistré automatiquement** : la relecture humaine est obligatoire, et c'est vous qui validez l'enregistrement. Une IA peut se tromper sur un règlement ambigu — les citations sont là pour que vous vérifiiez.

### 13.5 L'aide sur la configuration — avec ou sans clé

La page CONFIG offre deux niveaux d'aide :

1. Un **« ? »** à côté de chaque champ connu : explication immédiate tirée d'une base locale d'une centaine de fiches — **sans réseau ni clé API**, dès le premier lancement.
2. Le bouton flottant **🤖 Assistant** : un panneau de questions libres. Il cherche d'abord dans la base locale ; si une clé IA est renseignée, il peut poser la question au copilote (réponse courte, limitée aux champs réellement présents dans le formulaire). Sans clé, il vous répond avec la base locale et vous indique, le cas échéant : « …configure une clé API (étape PROPAGATION → COPILOTE IA) pour que je puisse répondre plus librement. »

## 14. Import, export et vos données

Un carnet de trafic n'a de valeur que si vous pouvez le soumettre, le réimporter ailleurs et être certain de ne jamais le perdre. Ce chapitre couvre les trois : formats de sortie, import avec filet de sécurité, et tout ce qui protège (ou peut faire sortir) vos données.

### 14.1 Les exports

La barre du **📋 LOGBOOK** propose trois boutons : **📥 EDI**, **📥 ADIF**, **📥 CSV**. Le format Cabrillo, lui, est produit automatiquement à l'archivage (voir §14.5) — le bon format est donc toujours disponible selon le type de concours :

| Format | Usage | Particularités |
|---|---|---|
| **EDI** (REG1TEST) | Soumission des concours VHF/UHF | En-tête complet (indicatif, locator, club, responsable, ville, code postal, altitude, email, champ « REMARQUES EDI (soapbox) »). Une **validation avant export** recense les QSO incomplets (ignorés), les QSO sans locator (0 point) et les doublons, puis demande : « Générer quand même le fichier EDI ? » |
| **Cabrillo v3** | Soumission des concours HF | En-têtes remplis automatiquement : concours, indicatif, catégorie SINGLE-OP ou MULTI-OP déduite du nombre d'opérateurs, puissance, score revendiqué, liste des opérateurs, locator |
| **ADIF 3** | Échange universel (tout logiciel de log, LoTW via TQSL, eQSL…) | Tous les champs standard, y compris les références d'activation POTA/SOTA/IOTA/WWFF **des deux côtés du QSO** — vos Park-to-Park et Summit-to-Summit sont conservés |
| **CSV** | Tableur (Excel, LibreOffice) | Colonnes N°, Date, Heure, Indicatif, Bande, Mode, RST env/reçu, N° env/reçu, Locator, Distance_km, Points, Opérateur |

### 14.2 L'import ADIF, avec aperçu avant écriture

Le bouton **📂 IMPORTER** accepte les fichiers .adi/.adif de n'importe quel autre logiciel. La fenêtre **📂 IMPORT ADIF** vous montre d'abord un **aperçu complet, sans rien écrire** :

- le total de QSO dans le fichier, le nombre de nouveaux et le nombre de doublons (comparaison stricte indicatif + bande + mode + date + heure — un import d'historique cohabite donc sans conflit avec le concours en cours) ;
- les enregistrements ignorés (sans indicatif ou sans bande, ou indicatif invalide) ;
- des avertissements pour les modes absents de l'énumération ADIF officielle (importés quand même) ;
- un échantillon de 5 QSO pour vérifier que les champs sont bien lus.

Rien n'est écrit tant que vous n'avez pas cliqué **✅ CONFIRMER L'IMPORT**. La bande est reconnue par le champ bande du fichier ou, à défaut, déduite de la fréquence. Les QSO importés arrivent avec 0 point (ils ne faussent pas le score d'un concours actif) et sont marqués comme provenant d'un import — ils alimentent immédiatement le carnet permanent et les diplômes du chapitre 12.

### 14.3 Où vivent vos données

Avec l'exécutable Windows, toutes vos données sont placées dans un dossier de votre profil : **`%APPDATA%\LogXAI`** (sous macOS : `~/Library/Application Support/LogXAI` ; sous Linux : `~/.local/share/LogXAI`). Vous y trouverez notamment la base de données `logx.db` (la source de vérité), une copie lisible du log en `shared_log.json`, le dossier `archives/` et le fichier des confirmations QSL. Les fichiers de référence (liste des pays, contours des départements…) y sont recopiés au premier lancement. Si vous lancez le programme depuis les sources Python, tout reste dans le dossier du programme.

### 14.4 Sauvegarde automatique et manuelle

La sauvegarde copie régulièrement votre carnet, horodaté, vers un dossier de votre choix. L'astuce : choisissez un dossier déjà synchronisé par Synology Drive, Dropbox ou OneDrive, et vous obtenez une sauvegarde « cloud » **sans aucun service en ligne ni compte supplémentaire** — c'est votre propre outil de synchronisation qui fait le transport.

- Chaque jeu de sauvegarde contient **3 fichiers** : la base `.db`, une copie `.json` lisible, et un `.adi` (ADIF) réimportable dans n'importe quel logiciel — même si vous abandonnez LogX AI un jour, votre log reste exploitable.
- Rétention : les 20 dernières sauvegardes sont conservées. Intervalle réglable (15 minutes par défaut).
- Sauvegarde immédiate : bouton **💾 SAUVEGARDER** du LOGBOOK (infobulle : « Sauvegarde immédiate vers le dossier configuré (Synology/Dropbox…). Sauvegarde aussi automatique si activée dans CONFIG. »). Confirmation affichée : « 💾 Sauvegarde OK → dossier (N fichiers) ».

À ne pas confondre avec le **Cloud Sync multi-postes** : là, plusieurs installations de LogX AI (fixe + portable, plusieurs opérateurs) partagent le **même** dossier synchronisé et fusionnent leurs logs dans les deux sens, toujours sans serveur hébergé. Trois modes : « full » (lit et écrit), « push » (écrit seulement), « off ». Chaque poste n'écrit que son propre fichier ; la fusion se fait à la lecture, avec déduplication — jamais d'écrasement du travail d'un autre poste.

### 14.5 Archiver un concours

En fin de concours, le bouton **📦 ARCHIVER** range tout dans un sous-dossier `archives/` dédié contenant : le log réimportable, le fichier Cabrillo `.cbr` prêt à soumettre, l'ADIF `.adi`, et un `resume.txt` (score, QSO, dates, répartition par bande). Au clic, vous choisissez : « OK = archiver ET vider ce concours du log actif (repartir à neuf) / Annuler = archiver SANS rien effacer ». Dans les deux cas, rien n'est perdu : les archives continuent d'alimenter le carnet permanent et les diplômes à vie du chapitre 12.

### 14.6 Encadré — Confidentialité : ce qui peut sortir de votre poste

> LogX AI est un serveur **local** : il tourne sur votre machine (adresse 127.0.0.1, port 8080), accessible au besoin depuis votre réseau domestique pour le téléphone ou le multi-op. **Par défaut, votre log ne quitte jamais votre poste.** Les fichiers de secrets (identifiants, clé API) sont explicitement exclus du service réseau : même un autre appareil de votre réseau local ne peut pas les lire.
>
> Six choses — et six seulement — peuvent sortir, chacune uniquement si **vous** l'avez configurée ou déclenchée :
>
> 1. **Callbook** (QRZ.com, HamQTH) : l'indicatif que vous tapez est envoyé pour récupérer nom, QTH et locator — seulement si vous avez renseigné des identifiants callbook.
> 2. **Cluster DX / RBN / PSK Reporter / ON4KST / données solaires** : consultation de spots publics. Le SELF-SPOT (publier votre propre indicatif et fréquence) est un bouton explicite, jamais automatique.
> 3. **QSL** : votre log part vers eQSL/ClubLog/QRZCQ/HRDLog, et vos identifiants LoTW vers l'ARRL, uniquement au clic des boutons du modal **🏅 DIPLÔMES & QSL** (ou si vous avez volontairement activé ClubLog Live Stream en expédition).
> 4. **IA** : votre question et son contexte (log, spots, configuration de la station — **jamais vos mots de passe**) partent vers le fournisseur choisi, uniquement si une clé API est saisie.
> 5. **Scoreboard en direct** : envoi périodique de votre score vers contestonlinescore.com, uniquement si vous avez activé **SCOREBOARD EN DIRECT — Activé — publier le score**.
> 6. **Sauvegarde / Cloud Sync** : le programme n'écrit que des fichiers dans un dossier **local** que vous avez choisi ; c'est votre propre outil (Synology, Dropbox, OneDrive…) qui assure éventuellement le transport.

---

## 15. Dépannage rapide

- **Le navigateur ne s'ouvre pas au démarrage** : ouvrez manuellement l'adresse affichée dans la fenêtre du serveur (`http://127.0.0.1:8080/logx_configuration.html` par défaut).
- **Un autre poste ne voit pas le log partagé** : vérifiez qu'il est sur le **même réseau WiFi**, et utilisez l'adresse IP affichée au démarrage du serveur (« Autres postes WiFi »), pas `127.0.0.1`/`localhost` qui ne désignent que le poste lui-même.
- **Un téléphone/second PC n'arrive pas à se connecter du tout** (la page ne charge jamais) : c'est presque toujours le **pare-feu Windows** du PC serveur — deux réglages à faire **sur le PC qui fait tourner LogX AI** :
  1. Le WiFi doit être en réseau **« Privé »** (pas « Public ») : Paramètres Windows → Réseau et Internet → Wi-Fi → cliquez votre réseau → Type de profil réseau → **Réseau privé**. Sur un réseau « Public », Windows bloque toutes les connexions entrantes.
  2. Au premier lancement de `LogXAI.exe`, quand Windows demande « Autoriser l'accès » : cochez **Réseaux privés** puis **Autoriser l'accès**. Si la fenêtre n'apparaît plus, ajoutez la règle à la main : Sécurité Windows → Pare-feu → Paramètres avancés → Règles de trafic entrant → Nouvelle règle → Port TCP **8080** → Autoriser (profil Privé).
- **Le copilote IA ne répond pas** : vérifiez la clé API en CONFIG (icône ❓ à côté du champ pour son explication) ; sans clé, tout le reste du logiciel reste utilisable.
- **Un champ de configuration n'est pas clair** : cliquez l'icône **❓** à côté, ou ouvrez l'assistant **🤖** (voir [§5](#5-configurer-sa-station--le-hub-de-catégories)).
- **Le pilotage radio ne répond pas** : vérifiez le bon port série (Gestionnaire de périphériques Windows) et que la vitesse (bauds) correspond exactement au réglage de la radio.
- **Le chat multi-opérateur n'apparaît pas** : il n'est visible qu'en configuration **multi-opérateur** (plusieurs opérateurs déclarés et section MO*) — en single-op, le panneau est masqué, c'est normal.
- **Un récepteur WebSDR est marqué « injoignable »** : ce sont des services bénévoles tiers, pas hébergés par LogX AI — réessayez plus tard ou choisissez-en un autre dans la liste.
- **Le décodeur CW n'écrit rien** : vérifiez que le navigateur a l'autorisation d'accéder au micro (icône caméra/micro dans la barre d'adresse) et que le bon périphérique d'entrée est choisi dans le panneau.
- **Un bandeau technique « FILES » apparaît en bas ou sur le côté de l'écran, avec une longue liste de requêtes qui défile** : ce n'est pas LogX AI, ce sont les **outils de développement de votre navigateur** (l'onglet « Réseau »/« Network »), ouverts par erreur — souvent en appuyant sans le vouloir sur la touche **F12**. C'est normal de voir beaucoup de lignes défiler : LogX AI interroge régulièrement le serveur en arrière-plan (spots, propagation…), rien d'anormal ni d'inquiétant pour votre sécurité. Pour le refermer, appuyez à nouveau sur **F12**, ou cliquez sur la croix **✕** du panneau.

### Le logiciel répond lentement à chaque clic (antivirus)

LogX AI teste automatiquement, à chaque démarrage, laquelle de ses deux adresses locales (`127.0.0.1` ou `localhost`) répond le plus vite sur votre poste, et utilise la meilleure sans que vous ayez à faire quoi que ce soit. Si malgré ça la fenêtre du serveur affiche un message **« ⚠ Latence locale élevée détectée »**, c'est que votre antivirus inspecte chaque connexion réseau — y compris le trafic purement local entre le logiciel et votre propre navigateur — ce qui ajoute jusqu'à 1 à 2 secondes à chaque action. LogX AI reste utilisable, juste ralenti.

Pour résoudre, ajoutez une exception dans votre antivirus pour l'application ou le port **8080** :

| Antivirus | Où chercher |
|---|---|
| **Avast / AVG** | Menu → Paramètres → Protection → **Exceptions** → ajouter le dossier d'installation ou le port 8080 |
| **Windows Defender** | Sécurité Windows → Protection contre les virus et menaces → Gérer les paramètres → **Exclusions** → ajouter un dossier ou processus |
| **Norton** | Paramètres → Antivirus → Exclusions/Faible risque → **Éléments à exclure des analyses** |
| **Kaspersky** | Paramètres → Protection → **Exclusions et applications de confiance** |
| **Bitdefender** | Protection → Antivirus → Paramètres → **Exclusions** |
| **McAfee** | Paramètres → Pare-feu ou Protection en temps réel → **Exclusions** |

Dans tous les cas, le plus simple et le plus fiable est d'exclure le **dossier d'installation complet** de LogX AI (ou l'exécutable `LogXAI.exe`) plutôt qu'une adresse réseau précise — certains antivirus filtrent les exceptions d'URL par correspondance exacte du texte (une exception pour `127.0.0.1` ne couvre pas forcément `localhost`, et inversement), alors qu'exclure le programme lui-même couvre toutes ses connexions quelle que soit l'adresse utilisée.

### Utilisation sans Internet (terrain /P, zone blanche)

LogX AI est conçu pour rester utilisable même sans aucune connexion Internet — seuls les services EN LIGNE (callbook QRZ/HamQTH/HamDB, clusters DX, propagation, PSK Reporter/RBN, QSL/LoTW, Cloud Sync, spots d'activation) sont concernés ; le logbook, le scoring, les diplômes, les bases d'activation déjà téléchargées et tout le reste fonctionnent en local sans aucun impact.

- **Recherche d'indicatif (QRZ/HamQTH/HamDB)** : si aucun des trois services ne répond après quelques indicatifs différents tapés de suite, le logiciel « met en pause » cette recherche pendant environ 1 à 2 minutes plutôt que de rejouer une longue attente à chaque nouvel indicatif — il réessaie ensuite automatiquement. C'est normal en zone blanche et n'affecte ni le log ni le scoring.
- **Envoi vers HRDLog / synchronisation LoTW / Cloud Sync** : ces actions s'arrêtent d'elles-mêmes après quelques échecs consécutifs (plutôt que de rester bloquées plusieurs minutes) et remontent une erreur claire — relancez-les une fois la connexion revenue.
- **Cloud Sync** : configurez le dossier partagé (OneDrive/Synology Drive/Dropbox) en mode **« toujours conserver sur cet appareil »** plutôt qu'en fichiers à la demande — sinon une synchronisation peut ralentir le temps que le fichier distant soit téléchargé.
- **Solaire / MUF / propagation** : ces panneaux affichent la dernière valeur connue (avec un indicateur de donnée non fraîche) plutôt que de geler en attendant une réponse réseau qui ne vient pas.
- **Bases d'activation (SOTA/POTA/WWFF/IOTA/WCA)** : téléchargées automatiquement au premier usage puis conservées en local ~30 jours — pensez à ouvrir une fois la recherche de référence AVANT de partir en portable, la base restera disponible sur le terrain.

---

*Dernière mise à jour : 25 juillet 2026 — nouvelle page **🎯 CHASSE** : les cinq panneaux de cibles (activateurs POTA/SOTA/WWFF, châteaux WCA, need list du cluster) ont quitté la page PROPAG. Chapitre 9 : entrée CHASSE ajoutée aux deux listes d'onglets, nouvelle section §9.5, panneaux retirés de la section PROPAG (WEBSDR et CALENDRIER renumérotés §9.6 et §9.7), et chapitre 10 corrigé (les activateurs en direct sont sur CHASSE).*

*Mise à jour précédente : 25 juillet 2026 — ajout au chapitre Dépannage : le bandeau « FILES »/liste de requêtes réseau qui inquiète certains utilisateurs est en fait l'onglet Réseau des outils de développement du navigateur (F12), pas un composant de LogX AI.*

*Mise à jour antérieure : 22 juillet 2026 — refonte complète du guide : nouveau plan en 15 chapitres reflétant l'état actuel du logiciel (4 modes d'utilisation dont RADIOCLUB, menus déroulants opérateur/bande/mode, ESM, décodeur CW, panneau EME, ouvertures par région, activations POTA/SOTA/WWFF/IOTA/WCA avec bases embarquées, chasse aux DXpéditions, écran mural utilisable dans tous les modes, 6 fournisseurs IA, chat multi-op).*
