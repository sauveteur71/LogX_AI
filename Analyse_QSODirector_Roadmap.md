# ANALYSE CONCURRENTIELLE — QSO Director → feuille de route RadioContest AI
**Date d'analyse :** 18 juillet 2026
**Source :** 44 captures d'écran fournies par l'utilisateur (client Windows QSO Director, éditeur Short Path Limited — EULA du 9 mars 2026) + inspection du dossier d'installation `%LOCALAPPDATA%\QSODirector` (aucun asset exploitable trouvé : uniquement l'exécutable, WebView2, et les caches — le produit est un Electron/WebView2 packagé).

**Méthode et limites (à lire avant le reste) :** ce document ne décrit QUE des *mécanismes fonctionnels et architecturaux* observés (quels réglages existent, comment l'information est organisée, quels flux sont possibles). Il ne reproduit aucun texte de l'éditeur au-delà de noms de champs génériques du métier radioamateur (« K Index », « DXCC Entity »... — vocabulaire standard non appropriable), ne copie aucune icône/palette/mise en page pixel-près, et ne cite pas l'EULA. Tout ce qui suit est écrit de ma propre plume à partir de ce que fait le logiciel, pas de comment son code ou ses textes sont écrits. C'est la bonne pratique standard de veille concurrentielle logicielle.

---

## 1. LE PLUS GROS ÉCART STRUCTUREL : tout est un panneau dockable

C'est l'observation la plus importante de toute l'analyse, et celle qui rejoint ta remarque initiale sur « les menus avec ouverture de fenêtre de configuration ».

QSO Director n'a **pas de pages fixes**. L'application entière est un espace de travail façon IDE professionnel :
- Chaque bloc fonctionnel (Log Book, Call Information, Solar Weather, Rig Control, Worked Matrix, Cluster, Previous QSOs, Map, Notifications, Time of Day, Statistics, Call Sense, Great Circle, Band Map — **14 panneaux recensés**) est une fenêtre dockable : épinglable, redimensionnable, fermable, regroupable en onglets avec d'autres panneaux.
- Menu **Window** : coche/décoche chaque panneau (afficher/masquer), + "Add Band Map / Add Spectrum Scope / Add Amplifier Controller" pour ouvrir une **deuxième instance** d'un panneau (utile en SO2R : un Band Map par VFO).
- Menu **Layout** : *Save Current Layout*, *Switch Layout...*, *Manage Layouts...*, *Save As New Layout...*, *Reset Layout*. L'opérateur peut donc avoir une disposition « Contest », une disposition « Activation POTA », une disposition « Log général » et **basculer de l'une à l'autre en un clic**, chacune avec ses propres panneaux ouverts, tailles et emplacements.

**Chez nous aujourd'hui :** RadioContest AI est organisé en **pages HTML séparées** (config / logbook / carte IA / calendrier / propagation / départements / mobile / mur) avec navigation par onglets fixes en haut. C'est plus simple à développer et très bien pour un usage mono-écran classique, mais ça ne permet pas à un opérateur de composer SON espace de travail, ni de basculer instantanément entre "je fais du contest" et "je fais une activation POTA" sans changer de page.

**Recommandation (gros chantier, fort différenciant) :** ne pas copier le docking générique (coûteux, fragile, peu adapté au web). À la place, viser le **même bénéfice utilisateur** avec une approche plus simple et déjà à moitié en place grâce à la Feature #4 « second écran / fenêtres détachables » déjà livrée :
- Généraliser le détachement de panneaux (déjà fait pour certains widgets) à TOUS les blocs : Log Book, Coach, Cluster, Band Map, Solar Weather, Carte, Worked Matrix...
- Un système de **layouts nommés** en localStorage/JSON : quels panneaux sont ouverts, sur quel écran, à quelle taille → sauvegarder/charger/réinitialiser, exactement le menu Layout observé.
- Le sélecteur de mode d'activité déjà présent chez eux (« General Logging / Contesting / An Activation / Running a NET ») est une bonne porte d'entrée : associer un layout par défaut à chaque mode.

---

## 2. CE QUE NOUS AVONS DÉJÀ ET QUI ÉGALE OU DÉPASSE QSO DIRECTOR

Point important pour ne pas sous-estimer notre position : plusieurs choses vues chez eux sont **déjà couvertes, parfois plus largement**, côté RadioContest AI.

| Domaine | QSO Director | RadioContest AI |
|---|---|---|
| Copilote IA temps réel | Absent (aucun écran vu) | Carte IA + coach déterministe + débrief post-session |
| Multilingue | Non observé dans les captures (UI anglais uniquement) | 8 langues (menu + agent + coach), auto-détection navigateur |
| CAT radio | Oui (10 marques, config série détaillée) | Oui (`radiocontest_rig.py`, rigctld/Hamlib, moins de marques mais protocole universel) |
| Rotor | Non vu dans les captures | Oui (`radiocontest_rotor.py`, rotctld) |
| RBN (Reverse Beacon) | Non vu | Oui (`radiocontest_rbn.py`) |
| Propagation avancée | Solar Flux/K/A + tables HF/VHF day-night | Tout ça + tropo (gradient réfractivité), météores, grey-line, carte 24h par bande/heure, prévision Es/aurore |
| Départements REF (carte France) | Non applicable (produit anglophone généraliste) | Page dédiée avec carte géographique + cibles actionnables |
| Mode expédition / écran mural | Non vu | Oui (mur configurable, Club Log Live push) |
| Diplômes & QSL | QSO Upload multi-cible (voir §3) | Diplômes (DXCC/depts/continents) + upload eQSL/ClubLog + sync LoTW |
| PWA / mobile | Cloud Sync (voir §3) | Page mobile généralisée, URLs relatives, prompt IA serveur |
| Score temps réel contest | Worked Matrix (bandes×modes), Statistics (rate) | Coach avec plan de bande horaire, budget off-time, recommandation RUN/S&P |

**Conclusion de cette section :** notre différenciation IA + radioamateur français (REF, départements, EDI) + profondeur propagation est réelle et solide. Le vrai chantier n'est pas de rattraper un retard généralisé, c'est de combler des **trous précis** (ci-dessous) et de répondre à l'écart architectural du §1.

---

## 3. TROUS FONCTIONNELS PRÉCIS (par domaine)

### 3.1 Callbook — lookup en cascade multi-source
QSO Director : **Primary / Secondary / Tertiary Callbook** avec cascade configurable parmi *None, Previous QSOs (gratuit, local), QRZ, HamQTH, QRZCQ, HAMDB, HamCall, HRDLog*, + mode *Merge* (fusionner les réponses) ou *Use First Response*. Écran séparé « Callbook Credentials » pour stocker les identifiants de chaque service.

**Chez nous :** uniquement QRZ (`radiocontest_qrz.py`), pas de cascade, pas de fallback gratuit.

**Recommandation :** ajouter au minimum **HamQTH** (gratuit, déjà utilisé ailleurs dans le projet pour un lookup ponctuel) et **HamDB** (gratuit, sans identifiants) comme repli quand QRZ échoue ou n'est pas configuré — beaucoup d'utilisateurs n'ont pas d'abonnement QRZ XML. Le "Previous QSOs" en tête de cascade, on l'a déjà via `radiocontest_callhistory.py` (SCP) — juste à le brancher formellement comme source n°1 avant l'appel réseau.

### 3.2 Programmes d'activation — 11 vs 4
QSO Director couvre au moins : **IOTA, IOTA ID, POTA, SOTA, WWFF, ARLHS (phares), WCA (châteaux), ILLW (semaine phares/bateaux-phares), WLOTA (phares monde), COTA (châteaux), HSOTA, BOTA (bunkers)**.

**Chez nous :** POTA/SOTA/IOTA/WWFF (`radiocontest_activation.py`, feature #1 du 17/07).

**Recommandation :** étendre `radiocontest_activation.py` avec ARLHS et WCA au minimum (programmes phares/châteaux, communauté active en Europe) — c'est une extension de champs et de format de référence, pas une nouvelle architecture. Les autres (ILLW/WLOTA/COTA/HSOTA/BOTA) sont plus de niche, à faire à la demande.

### 3.3 Répertoire intégré de serveurs DX Cluster
QSO Director propose un **menu déroulant pré-rempli de dizaines de serveurs cluster telnet publics réels**, groupés par indicatif de continent (AF/EU/NA...), avec host:port prêts à l'emploi, en plus de la possibilité d'ajouter un cluster personnalisé. Toggle séparé « POTA Cluster Enabled » (spots POTA tirés directement de pota.app).

**Chez nous :** clusters codés en dur dans `radiocontest_clusters.py` (F5LEN, DXSummit, DXWatch, HamQTH, HamSpirit, DXMaps, ON4KST, telnet DX Spider) — bonne couverture des sources, mais pas de **répertoire visible/éditable par l'utilisateur**, ni de toggle dédié pour activer/désactiver chaque source individuellement depuis l'UI.

**Recommandation :** exposer la liste actuelle des sources sous forme de toggles individuels dans CONFIG (déjà en partie le cas via les toggles `src_*` de l'étape PROPAGATION), et ajouter un champ "cluster telnet personnalisé host:port" pour que l'utilisateur ajoute SA source préférée sans dépendre d'un déploiement de code.

### 3.4 QSO Upload multi-destination avec déclencheurs configurables
QSO Director : ajouter plusieurs uploaders simultanés (**Clublog, QRZ.COM, QRZCQ, HamQTH, HRDlog.Net**), chacun avec sa clé API, ses toggles indépendants *Batch Upload Enabled* / *Realtime Upload Enabled*, portée *Apply to all stations* / *Apply to this station*, et un réglage global *Batch Upload Time* (intervalle en secondes).

**Chez nous :** upload eQSL/ClubLog (`radiocontest_qsl.py`) + sync LoTW + push temps réel Club Log Live en mode expédition — bonne couverture, mais pas de QRZCQ/HamQTH/HRDLog, et le déclenchement batch vs temps réel n'est pas un réglage explicite unifié (le push Club Log Live est un cas séparé du "Mode Expédition").

**Recommandation :** unifier la config QSL/upload en une liste de destinations (comme eux), chacune avec son toggle batch/temps réel — évite de dupliquer la logique "Mode Expédition" pour chaque nouvelle destination future.

### 3.5 Cloud Sync — 3 niveaux clairs
QSO Director : **Full Synchronisation (recommandé) / Push Only / No Synchronisation**, synchronise QSOs + Stations + Opérateurs + Emplacements + Événements entre plusieurs installations liées à un compte.

**Chez nous :** c'est exactement l'item n°3 de la roadmap « dépasser QSO Director » déjà notée en mémoire (`radiocontest_mobile.html` existe partiellement, mais pas de vrai compte cloud multi-poste). Le modèle à 3 niveaux de QSO Director est un bon gabarit à reprendre tel quel pour la conception : simple à expliquer, couvre les 3 vrais cas d'usage (poste unique confiant / poste de secours qui ne fait que pousser / poste isolé volontairement).

### 3.6 Réseau temps réel générique pour apps tierces
QSO Director expose des **Network Listeners / Network Senders** configurables (protocole ADIF, port, filtre IP, actions "logger le contact" / "ajouter un spot" / "lookup callbook automatique à la réception") — un vrai petit protocole d'interopérabilité locale, généralisé à N'IMPORTE QUEL logiciel tiers qui parle ce protocole, pas seulement WSJT-X.

**Chez nous :** le pont WSJT-X (`radiocontest_wsjtx.py`) est spécifique à ce seul logiciel (protocole UDP QDataStream propriétaire WSJT-X).

**Recommandation (moyen terme) :** généraliser en exposant un petit serveur/port ADIF-over-UDP configurable, qui reprendrait le même `add_qso_to_log()` déjà factorisé — ouvre la porte à N1MM, DXLog, et tout logiciel qui sait pousser de l'ADIF en réseau, pas seulement WSJT-X.

### 3.7 Constructeur de règles d'alerte
QSO Director : écran dédié « Manage Alerts » → règles multi-critères combinables : indicatif/commentaire de spot (avec motifs avancés), pays, entité DXCC, **statut travaillé** (nouveau/déjà travaillé/confirmé), statut contest, zone ITU/CQ, **rang "Most Wanted"**, et un filtre par type d'activation (IOTA/POTA/SOTA/WWFF) — chaque règle nommée, activable, avec option "filtre global (s'applique à tous les événements)".

**Chez nous :** alertes fixes (nouveau multiplicateur spotté, mention ON4KST) — pas de règles personnalisables par l'utilisateur.

**Recommandation :** c'est un morceau substantiel mais à fort impact pour les chasseurs de DX/diplômes (pas seulement les contesteurs) — un constructeur de règles simple (2-3 critères combinables : pays/zone + statut travaillé + activation) couvrirait 80% des usages sans la richesse complète de QSO Director.

### 3.8 Assistant d'import/migration
QSO Director : un assistant en 6 étapes (Choisir le type → Fichier → Options → Confirmer → Import → Terminé) avec un **menu déroulant de types de migration** — suggère un import non seulement ADIF mais depuis les formats/bases d'autres loggers concurrents, pour abaisser la barrière au changement de logiciel.

**Chez nous :** pas d'assistant d'import dédié identifié (le log est alimenté en direct pendant le concours, migré vers SQLite en interne, mais pas d'import "je viens d'un autre logiciel").

**Recommandation :** un import ADIF simple dans un premier temps (beaucoup de valeur pour peu d'effort — un radioamateur qui teste RadioContest AI veut voir SON historique tout de suite), avec assistant en quelques étapes façon onboarding existant.

### 3.9 Panneaux d'information ponctuels à considérer
- **Great Circle map** : projection azimutale centrée sur le QTH avec cercles de distance (1000/2000/3000/4000 km) — visuellement clair pour juger d'un coup d'œil "c'est loin comment". On a la carte du monde (Leaflet) + la carte de propagation 24h, mais pas cette vue "cercles concentriques centrés sur moi" — pourrait être un mode d'affichage de plus sur la carte IA existante plutôt qu'une page séparée.
- **Time of Day widget** (arc lever/coucher de soleil, heure locale, HOME vs DX) — ludique et lisible, notre grey-line existe déjà sur la carte mais pas ce petit widget compact.
- **Statistics avec graphe de rythme QSO/heure dans le temps** (pas juste un instantané 10/30 min comme le coach actuel, un vrai graphique sur toute la session) — on a les taux instantanés, un graphique cumulatif serait un ajout léger et parlant en debrief.
- **Worked Matrix** (grille bande × CW/Phone/Digital avec compteurs) — utile en log général (DXCC awards) plus qu'en concours ; peut compléter le panneau diplômes existant.

---

## 4. FEUILLE DE ROUTE PROPOSÉE (par impact/effort)

### Lot rapide (1 session chacun, forte valeur immédiate)
1. **Import ADIF** (assistant simple, §3.8) — abaisse la barrière à l'essai.
2. **Callbook en cascade avec repli gratuit** HamQTH + HamDB avant/après QRZ (§3.1).
3. **Toggles individuels des sources cluster déjà codées**, exposés proprement en CONFIG (§3.3) — surtout de la présentation, le code existe déjà.
4. **Extension ARLHS/WCA** dans `radiocontest_activation.py` (§3.2).

### Lot moyen (2-4 sessions)
5. **QSO Upload unifié multi-destination** avec toggles batch/temps réel par service (§3.4) — refactor du QSL existant plutôt que nouveau code.
6. **Constructeur de règles d'alerte simplifié** (§3.7) — 2-3 critères combinables pour commencer.
7. **Panneaux ponctuels** : widget Time of Day, graphe de rythme sur la session complète (§3.9) — additions à la carte/logbook existants.

### Lot structurant (chantier à part entière)
8. **Système de layouts nommés + détachement généralisé de tous les panneaux** (§1) — le vrai différenciateur architectural, à traiter comme un projet en soi une fois les 4 features "dépasser QSO Director" déjà en cours (POTA/SOTA/IOTA/WWFF ✅, bandscope, sync cloud+mobile, multi-écran) terminées, puisqu'elles posent une bonne partie des fondations (fenêtres détachables déjà livrées en Feature #4).
9. **Cloud Sync à 3 niveaux** (§3.5) — s'appuie sur le multi-écran/mobile déjà en chantier.
10. **Réseau ADIF générique** pour interop 3rd-party au-delà de WSJT-X (§3.6).

### Non retenu pour l'instant
- Support multi-marques radio/ampli exhaustif (10+ marques CAT propriétaires) : notre approche rigctld/Hamlib générique couvre déjà la quasi-totalité du parc sans maintenir 10 pilotes.
- Docking window système générique façon IDE : trop coûteux pour le bénéfice réel sur le web ; l'approche layouts nommés + détachement ciblé (déjà amorcée) donne 90% du bénéfice pour une fraction du coût.

---

## 5. NOTE COPYRIGHT / PROPRIÉTÉ INTELLECTUELLE

Ce document ne contient : aucun extrait de code de QSO Director, aucune image ou icône de QSO Director, aucun texte de son EULA/CGU/politique de confidentialité, aucune reproduction de sa palette de couleurs ou de sa mise en page exacte. Il décrit des **fonctionnalités et flux** (ce qui, en droit, n'est pas protégeable en tant que tel — seule l'expression concrète, code/design/texte, l'est). Avant toute implémentation, veiller à :
- écrire notre propre code et nos propres textes d'interface (jamais copier-coller depuis leurs écrans),
- choisir nos propres icônes/couleurs (déjà le cas, palette RadioContest AI distincte),
- ne jamais réutiliser le nom "QSO Director" ni s'en approcher dans notre communication.
