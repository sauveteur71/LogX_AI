# Guide utilisateur — LogX AI

> **À maintenir à jour.** Ce document décrit le logiciel tel qu'il se comporte réellement. Chaque fois qu'une fonctionnalité change, est ajoutée ou retirée, mettez à jour la section concernée dans la même session de travail — ne laissez jamais ce guide dériver du code. La dernière mise à jour est notée en bas de fichier.

LogX AI est un logiciel de journal de trafic (« logbook ») pour radioamateurs : il couvre le **trafic courant** (chasse DX au fil de l'eau), les **concours** (règlement, échange, scoring, need list), et les **expéditions/activations** (multi-poste, écran mural, SOTA/POTA/IOTA). Il tourne en local sur votre ordinateur et s'utilise depuis un navigateur — aucune donnée ne quitte votre poste sans que vous ne l'ayez explicitement configuré (QSL, cloud sync, IA...).

## Sommaire

1. [Installation et premier lancement](#1-installation-et-premier-lancement)
2. [Prise en main en 5 minutes](#2-prise-en-main-en-5-minutes)
3. [Choisir son mode d'utilisation](#3-choisir-son-mode-dutilisation)
4. [Configurer sa station, étape par étape](#4-configurer-sa-station-étape-par-étape)
5. [L'assistant de configuration](#5-lassistant-de-configuration)
6. [Utiliser le Logbook au quotidien](#6-utiliser-le-logbook-au-quotidien)
7. [Faire un concours de A à Z](#7-faire-un-concours-de-a-à-z)
8. [Piloter sa radio et son matériel](#8-piloter-sa-radio-et-son-matériel)
9. [Cartes, propagation et écoute à distance](#9-cartes-propagation-et-écoute-à-distance)
10. [Le copilote IA](#10-le-copilote-ia)
11. [Diplômes, QSL et historique à vie](#11-diplômes-qsl-et-historique-à-vie)
12. [Multi-poste, expédition et collaboration](#12-multi-poste-expédition-et-collaboration)
13. [Import / export](#13-import--export)
14. [Dépannage rapide](#14-dépannage-rapide)

---

## 1. Installation et premier lancement

L'installation détaillée (Windows/macOS, version autonome vs mode développeur) est décrite dans [`concours/INSTALL.md`](../concours/INSTALL.md). En résumé :

- **Version autonome (recommandée)** : un seul fichier `LogXAI.exe` (Windows) à double-cliquer. Aucune installation de Python nécessaire.
- Au premier lancement, le logiciel crée tout seul son dossier de données personnel et y recopie les fichiers de référence (base des indicatifs DXCC, schéma des concours, carte des départements) — vous n'avez rien à copier à la main.
- Le navigateur s'ouvre automatiquement sur la page de configuration. Si ce n'est pas le cas, ouvrez `http://localhost:8080/logx_configuration.html`.
- **Autres postes du même WiFi** : l'adresse à utiliser (ex. `http://192.168.1.x:8080/`) s'affiche dans la fenêtre du serveur au démarrage.

---

## 2. Prise en main en 5 minutes

Pour logger votre tout premier QSO sans vous perdre dans les réglages :

1. Ouvrez l'onglet **⚙ CONFIG**.
2. Étape **1 · MA STATION** : renseignez votre **INDICATIF** et votre **LOCATOR MAIDENHEAD** (bouton **📍 Sur la carte** si vous ne le connaissez pas — voir [§4](#4-configurer-sa-station-étape-par-étape)).
3. En haut de la page, laissez **MODE D'UTILISATION** sur **📋 LOGBOOK SIMPLE** si vous ne participez à aucun concours pour l'instant.
4. Cliquez **💾 SAUVEGARDER** en bas, puis ouvrez l'onglet **📋 LOGBOOK**.
5. Tapez un indicatif dans le champ prévu, complétez le RST, validez avec **Entrée** ou **F9**.

C'est tout : le QSO est enregistré, une fiche du correspondant (pays, callbook, historique) s'est affichée pendant la frappe. Les sections suivantes détaillent chaque brique pour aller plus loin.

---

## 3. Choisir son mode d'utilisation

En haut de la page CONFIG, le sélecteur **MODE D'UTILISATION** change le comportement de tout le logiciel :

| Mode | Pour qui | Ce qui change |
|---|---|---|
| **📋 LOGBOOK SIMPLE** | Chasse DX / trafic courant, sans concours | Pas de règle « 1 QSO/station/bande », pas d'étape CONCOURS, recontacter la même station à une autre date n'est pas un doublon |
| **🏆 CONCOURS** | Participation à une épreuve avec règlement | Échange, scoring, multiplicateurs et détection de doublon actifs, need list et coach affichés |
| **📡 EXPÉDITION / ACTIVATION** | DXpédition, SOTA/POTA/IOTA, multi-poste | Saisie simplifiée (indicatif + reports), écran mural, pile-up, suivi de progression d'activation |

Vous pouvez changer de mode à tout moment ; vos QSO existants ne sont jamais perdus lors du changement.

---

## 4. Configurer sa station, étape par étape

La configuration se fait en 5 étapes cliquables (revenez en arrière à tout moment) :

### Étape 1 — MA STATION
Identité (indicatif, indicatif concours si différent, ville, altitude, puissance) et **locator Maidenhead**. Si vous ne connaissez pas votre locator, cliquez **📍 Sur la carte** à côté du champ : une carte s'ouvre, vous cliquez votre position (ou cherchez une ville, ou utilisez **🛰️ Ma position**), et la grille 6 caractères est calculée automatiquement. Cette même fenêtre permet aussi de **comparer** votre position à un locator distant tapé à la main (distance + azimut affichés, ligne tracée sur la carte).

### Étape 2 — CONCOURS
Une grille de cartes recense des dizaines de concours pré-configurés (REF, IARU, CQ WW/WPX, ARRL, WAE, SOTA, POTA...) avec recherche instantanée. Choisir un concours pré-remplit dates, bandes et modes. Pour un concours absent de la liste, collez l'URL de son règlement dans **🤖 ANALYSER UN RÈGLEMENT** : l'IA en extrait bandes, dates, échange et barème — la proposition est **toujours présentée en relecture** avant d'être enregistrée, jamais automatiquement.

### Étape 3 — FILTRES
Bandes et modes actifs, filtre de préfixe pour ne garder que certains pays dans la need list, distance à partir de laquelle un spot est considéré comme un DX exceptionnel.

### Étape 4 — PROPAGATION
Réglages liés aux alertes de propagation (Sporadique-E, tropo, aurore) et aux sources de spots à activer (cluster DX, RBN, chat ON4KST).

### Étape 5 — RÉSUMÉ
Récapitulatif complet avant de démarrer. Un bouton **🎚 EXPERT** (en haut de page) révèle les réglages avancés (radio CAT, ampli, rotor, cloud sync, alertes personnalisées) — masqués par défaut pour ne pas noyer un débutant.

### Profils
Plusieurs configurations peuvent être sauvegardées sous un nom (ex. « HF fixe », « VHF portable ») et rechargées en un clic via le sélecteur de profil en haut de page.

---

## 5. L'assistant de configuration

Si un champ n'est pas clair, deux niveaux d'aide, **sans jamais bloquer** :

- Une petite icône **❓** apparaît à côté de chaque champ connu — cliquez dessus pour une explication immédiate, sans connexion ni clé API.
- Le bouton flottant **🤖** (en bas à droite de la page CONFIG) ouvre un panneau de questions libres : il cherche d'abord dans la même base locale, et si une clé API IA est déjà renseignée dans le formulaire, peut aussi poser la question au copilote pour une réponse plus personnalisée.

---

## 6. Utiliser le Logbook au quotidien

L'onglet **📋 LOGBOOK** est l'écran principal de saisie.

- **Autocomplétion** : dès les premières lettres d'un indicatif, des suggestions apparaissent (avec locator/département connus), et les doublons déjà loggés sont signalés.
- **Fiche automatique du correspondant** : nom, QTH, locator et pays s'affichent en interrogeant QRZ.com, puis HamQTH, puis HamDB en secours — une fiche apparaît presque toujours, même sans abonnement payant.
- **Historique « déjà contacté »** : tous les QSO passés avec cette station (tous concours confondus) sont rappelés, avec une alerte dorée si c'est un **nouveau pays ou département à vie**.
- **Calcul en direct** : dès que le locator du correspondant est complet, distance, cap boussole et points s'affichent instantanément.
- **Raccourcis clavier** : `F9` ou `Entrée` valide le QSO, `Ctrl+Z` annule le dernier, `Ctrl+F` retourne au champ indicatif.
- **🔍 VÉRIFIER** : ce bouton audite le log entier (doublons, locators absents/invalides, distances anormales, département incohérent, QSO hors fenêtre du concours). Chaque problème signalé propose directement **✏️ Corriger** (ouvre l'édition du QSO) ou **🗑 Supprimer**, avec relance automatique de l'analyse après action.
  > Note : un indicatif comme `EA/F4GLD` (F4GLD émettant depuis l'Espagne) est reconnu comme valide — les préfixes de lieu portables ne sont plus signalés à tort comme suspects.
- **Édition/suppression** d'un QSO : double-clic sur la ligne, ou icônes ✏️/✕ en bout de ligne.
- **Archiver / Nouveau log** : « Archiver » conserve une copie complète (log, Cabrillo, ADIF, résumé) sans vider le log actif ; « Nouveau log » exige de taper `RESET` pour confirmer et archive automatiquement l'ancien log avant de le vider — impossible de perdre un concours par erreur de manipulation.

---

## 7. Faire un concours de A à Z

**Avant** : sélectionnez le concours en CONFIG (§4), vérifiez la checklist avant-concours (indicatif, locator, base d'indicatifs chargée, horloge synchronisée). Le tableau de bord de propagation (SFI, K-index, MUF) et le calendrier des concours vous aident à préparer la session.

**Pendant** :
- L'onglet **🗺️ CARTE IA** et le panneau **need list** classent chaque station repérée par **valeur réelle en points** selon le barème exact du concours, avec priorité (PRIORITÉ MAX/HAUTE/MOYENNE) et raison (nouveau multiplicateur, DX exceptionnel...).
- Le **Coach** (visible dans le logbook et détachable en fenêtre séparée) surveille le rythme et pousse des conseils concrets : silence radio prolongé, recommandation RUN vs Search & Pounce, plan de bande le plus rentable à l'instant T.
- Le **bandmap/bandscope** liste les spots de la bande active ; un clic règle la radio sur cette fréquence si le pilotage CAT est actif.
- Les **macros F1–F8** (CW ou phonie selon le mode radio) accélèrent l'échange.

**Après** : `🔍 VÉRIFIER` avant tout export. Le bouton d'export bascule automatiquement sur le bon format (EDI pour REF/IARU VHF, Cabrillo pour la plupart des concours HF internationaux, ADIF pour SOTA/POTA), avec en-têtes déjà remplis depuis votre configuration. Un débrief post-concours peut être généré par le copilote IA (voir [§10](#10-le-copilote-ia)).

---

## 8. Piloter sa radio et son matériel

Dans CONFIG (mode 🎚 EXPERT), section radio :

- **CAT** : trois protocoles au choix — **natif** (câble série direct, sans logiciel tiers, compatible Icom/Yaesu/Kenwood/Elecraft/Xiegu), **TCI** (réseau, pour les transceivers SDR type SunSDR/ExpertSDR3), ou **rigctld** (Hamlib, pour les radios non couvertes nativement). Un bouton teste et auto-détecte la radio branchée.
- Une fois actif, le pilotage permet le **QSY en un clic** depuis un spot ou le bandmap, le suivi automatique bande/mode, et sert de base au **keyer vocal** et à l'**envoi CW automatique**.
- **Amplificateur** : Elecraft KPA500/1500, Icom PW-1/PW2, SPE/Expert — bascule standby/operate, changement de bande, lecture puissance/ROS/défauts en direct.
- **Rotor** (rotctld) : pointage automatique sur le cap calculé pour un correspondant ou un spot, directement depuis la boussole affichée dans le logbook ou la carte.
- **Keyer vocal / callbot** : synthèse vocale hors-ligne qui épelle l'indicatif (alphabet OACI) et le report, avec PTT automatique — équivalent phonie des macros CW.
- **Décodeur CW par micro** : bouton « écouter » qui décode le morse capté par le micro de l'ordinateur, sans logiciel tiers.

---

## 9. Cartes, propagation et écoute à distance

- **🗺️ CARTE IA** : carte de trafic en temps réel, stations colorées par priorité, anneaux de distance, ligne grise (terminateur jour/nuit), mode Great Circle, vues rapides Europe/Monde/USA/France.
- **🇫🇷 Cartes** : carte de France des départements REF à verdir, carte du monde des pays DXCC travaillés.
- **📶 PROPAG** : indices solaires (SFI, K, A, taches, rayons X — également résumés en permanence dans la barre de statut, badge `☀️ SFI x · K x` en haut de chaque page), MUF avec verdict ouvert/fermé par bande, conditions Sporadique-E/tropo/météores, balises NCDXF/IBP. Complété d'un lien direct vers la **carte mondiale PSK Reporter** (filtrée sur votre indicatif) et d'un panneau **🛰️ Satellites** (liens calculés vers Heavens-Above pour les passages visibles et AMSAT pour l'état des satellites radioamateur).
- **📡 WEBSDR** (nouveau) : annuaire de récepteurs distants (France et international) pilotables depuis un navigateur. Utile pour vérifier comment votre propre émission est reçue ailleurs, écouter une bande fermée chez vous mais ouverte là-bas, ou repérer une station avant de tenter le contact. Ces récepteurs sont opérés bénévolement par d'autres radioamateurs — leur disponibilité n'est pas garantie, un badge de test rapide l'indique à l'ouverture de la page.
- **🏞️ Activateurs POTA en direct** (nouveau, page PROPAG) : liste en temps réel des activations Parks On The Air en cours dans le monde (indicatif, référence de parc, bande, mode), utile aussi bien pour chasser un parc que pour vérifier qu'un site n'est pas déjà occupé avant sa propre activation. Distinct du suivi de progression d'activation (§7/§11), qui reste local à votre propre session.

---

## 10. Le copilote IA

Nécessite une clé API (Anthropic, OpenAI ou Gemini — champ **CLÉ API** en CONFIG, étape PROPAGATION en mode expert). Sans clé, tout le reste du logiciel fonctionne normalement ; seul le copilote est indisponible.

Une fois configuré, le chat IA (accessible depuis le logbook et en mobilité) reçoit **automatiquement** votre contexte réel : indicatif, locator, concours actif et son règlement exact, votre log complet, le log partagé multi-opérateur, et tous les spots actifs. Vous n'avez rien à copier/coller. Il peut :

- classer les meilleures cibles du moment par gain de points réel, avec cap d'antenne,
- signaler une incohérence indicatif/locator repérée en arrière-plan,
- générer un **débrief post-concours** (points forts, axes d'amélioration, silences radio),
- répondre à des questions d'usage du logiciel lui-même (« où est le bouton pour... »),
- répondre dans la langue choisie dans le menu de langue.

---

## 11. Diplômes, QSL et historique à vie

Le panneau **carnet permanent** (accessible depuis le logbook) cumule, sur toute la vie de la station et tous concours confondus : pays DXCC, départements français, continents et zones CQ travaillés/confirmés, avec la **Worked Matrix** (grille bande × CW/Phone/Digital).

Services QSL pris en charge, avec upload/synchronisation en un clic depuis le même écran : **eQSL, ClubLog, LoTW, QRZCQ, HRDLog**. Le téléchargement des confirmations LoTW ne nécessite pas d'installer TQSL — indicatif/mot de passe suffisent.

---

## 12. Multi-poste, expédition et collaboration

- **Accès réseau local** : un lien (adresse IP locale) s'affiche et se copie en un clic ; n'importe quel autre poste du même WiFi (PC, tablette, téléphone via la page **mobile**) rejoint le même log partagé sans configuration serveur.
- **Cloud Sync** : combine les QSO de plusieurs postes en pointant chacun vers un même dossier déjà synchronisé (Synology Drive, Dropbox, OneDrive...) — aucun compte tiers à créer. Mode « complet » (fusion bidirectionnelle) ou « envoi seul » (poste isolé).
- **Mode Expédition/Activation** : saisie réduite à l'indicatif et aux reports, écran mural (page dédiée, plein écran, personnalisable) pour projeter le flux de QSO en direct, chat intégré entre opérateurs, classement en temps réel.
- **Interopérabilité N1MM/DXLog** : réception et/ou émission des QSO en UDP `<contactinfo>`, pour cohabiter avec un logger tiers déjà en place sur le même réseau.
- **Sauvegardes automatiques** et **Scoreboard en ligne** (contestonlinescore.com) se règlent en CONFIG (mode expert).

---

## 13. Import / export

- **Export** : EDI (REG1TEST, multi-bandes VHF/UHF/SHF), Cabrillo v3 (concours HF), ADIF 3 (avec champs SIG/SIG_INFO pour POTA/SOTA/IOTA/WWFF), CSV. Le bon format est choisi automatiquement selon le concours actif ; un contrôle qualité s'affiche avant génération.
- **Import** : ADIF avec aperçu (nouveaux QSO / doublons / échantillon) avant toute écriture réelle.
- **Auto-log WSJT-X** (FT8/FT4) et **réseau ADIF N1MM/DXLog** : les QSO arrivent directement dans le journal sans ressaisie, une fois l'IP/le port renseignés côté réglages.

---

## 14. Dépannage rapide

- **Le navigateur ne s'ouvre pas au démarrage** : ouvrez manuellement `http://localhost:8080/logx_configuration.html`.
- **Un autre poste ne voit pas le log partagé** : vérifiez qu'il est sur le **même réseau WiFi**, et utilisez l'adresse IP affichée au démarrage du serveur (pas `localhost`).
- **Le copilote IA ne répond pas** : vérifiez la clé API en CONFIG (icône ❓ à côté du champ pour son explication) ; sans clé, tout le reste du logiciel reste utilisable.
- **Un champ de configuration n'est pas clair** : cliquez l'icône **❓** à côté, ou ouvrez l'assistant **🤖** (voir [§5](#5-lassistant-de-configuration)).
- **Le pilotage radio ne répond pas** : vérifiez le bon port série (Gestionnaire de périphériques Windows) et que la vitesse (bauds) correspond exactement au réglage de la radio.
- **Un récepteur WebSDR est marqué « injoignable »** : ce sont des services bénévoles tiers, pas hébergés par LogX AI — réessayez plus tard ou choisissez-en un autre dans la liste.

---

*Dernière mise à jour : 21 juillet 2026 — reflète l'état du logiciel après ajout de l'assistant de configuration, du sélecteur de locator sur carte, du badge météo solaire partagé, du lien PSK Reporter, du panneau satellites, de l'annuaire WebSDR et des spots POTA en direct.*
