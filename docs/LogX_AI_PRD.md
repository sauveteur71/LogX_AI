# PRD — LogX AI

**Product Requirements Document**
**Projet :** LogX AI — logbook & assistant de contest radioamateur assisté par IA
**Auteur / mainteneur :** équipe F6KQJ
**Version du document :** 1.2 — 21 juillet 2026 *(ajout EV-4.5 : relevé manuel MUF/propagation par balises NCDXF/IBP, retour terrain groupe TX7N — v1.1 : vérification du dépôt GitHub réel : CI existante, hygiène secrets, WebSDR/QTC, robustesse réseau)*
**Statut du produit :** Phases 0 à 4 livrées (15-16/07/2026) · Phase 5 (validation terrain) en cours
**Audience de ce PRD :** développeur solo / mainteneur (concret, orienté implémentation, avec critères d'acceptation et accroches dans le code)
**Ambition :** projet open-source public international

---

## 0. Comment lire ce document

Ce PRD sert deux buts à la fois :

1. **Consolider l'existant** — figer noir sur blanc ce que LogX AI *fait déjà*, pour ne pas le casser et pour pouvoir raisonner dessus (parties 1 à 6).
2. **Cadrer les évolutions à venir** — transformer les trous identifiés dans la roadmap et le plan de bataille en exigences actionnables, priorisées, avec critères d'acceptation (parties 7 à 12).

Convention : chaque exigence future porte un identifiant `EV-x.y`, une priorité (**P0** critique / **P1** important / **P2** confort), un effort estimé (**S** ≤1 session, **M** 2-4 sessions, **L** chantier), et une **accroche code** (`logx_*.py` / fichier HTML) quand le point de départ existe déjà.

---

## 1. Vision & positionnement

### 1.1 Énoncé de vision
> LogX AI est le premier logbook de contest radioamateur qui **lit un règlement et s'adapte tout seul**, épaulé par un **copilote IA temps réel** qui recommande le prochain meilleur QSO — le tout dans une application **locale, multiplateforme, sans cloud obligatoire, et open-source**.

### 1.2 Ce qui différencie LogX AI
- **Auto-adaptation par IA réelle** : lecture de règlement (PDF/HTML, multilingue) → définition structurée validée → moteur de score reconfiguré, sans coder une branche par concours.
- **Copilote IA en session** : recommandation RUN/S&P, plan de bande horaire, budget off-time, impact score par spot.
- **Profondeur propagation** : solaire, tropo (gradient de réfractivité), météores, grey-line, prévision Es/aurore, carte 24h par bande/heure.
- **Ancrage radioamateur français** : concours REF (RPH, THF, HF), départements REF, format EDI/REG1TEST natif — un créneau mal couvert par les loggers anglophones.
- **Local-first & respect de la vie privée** : tourne en serveur local (port 8080), données dans le profil utilisateur, aucun compte requis pour l'usage de base.

### 1.3 Anti-vision (ce que LogX AI n'est pas)
- Pas un service SaaS avec abonnement obligatoire.
- Pas un clone d'un logger existant : on vise le *bénéfice utilisateur*, avec notre propre code, nos propres textes et notre propre design.
- Pas un pilote propriétaire multi-marques : on reste sur l'approche **Hamlib/rigctld générique** (couvre le parc sans maintenir 10 drivers).

---

## 2. Objectifs & non-objectifs

### 2.1 Objectifs produit (12 mois)
- **O1** — « N'importe quel concours, quasi automatique » : couvrir ≥90 % des concours REF/IARU/EU/monde soit par la base intégrée, soit par l'analyse IA d'un règlement, sans intervention code.
- **O2** — « Ne plus jamais se perdre » : un opérateur configure et lance un concours en ≤3 clics ; un débutant ne voit que l'essentiel.
- **O3** — Interopérer avec l'écosystème existant (import ADIF depuis d'autres loggers, interop réseau N1MM/WSJT-X, upload LoTW/eQSL/ClubLog).
- **O4** — Devenir un projet open-source vivant : licence claire, doc contributeur, i18n, releases reproductibles.
- **O5** — Zéro perte de log terrain (backup, résilience réseau, mode dégradé).

### 2.2 Non-objectifs (pour cette itération)
- Application mobile native (la PWA/`logx_mobile.html` couvre le besoin).
- Support CAT propriétaire exhaustif marque par marque.
- Hébergement cloud managé par le projet (le cloud sync reste *self-hostable* / optionnel).

### 2.3 Métriques de succès (voir §11 pour le détail)
Temps config→lancement, taux d'extraction IA correcte champ par champ, nombre de concours couverts, taux de QSO perdus (=0), adoption open-source (stars/forks/contributeurs/issues).

---

## 3. Personas & cas d'usage

| Persona | Description | Besoin dominant |
|---|---|---|
| **Le contesteur THF (REF)** | Opère RPH / National THF depuis un point haut, souvent hors réseau | Fiabilité offline, EDI par bande, score temps réel, scoring km/locators |
| **Le contesteur HF DX** | CQ WW, WAE, IARU HF | Multiplicateurs DXCC/zones/préfixes, cluster/RBN, cascade callbook, dupe check |
| **Le chasseur de diplômes / activateur** | POTA/SOTA/IOTA/WWFF, chasse DXCC | Alertes personnalisables, spots activations, upload LoTW/ClubLog |
| **Le débutant concours** | Première participation | Mode débutant, assistant nouveau concours, textes clairs |
| **Le contributeur open-source** | Dev radioamateur externe | Code lisible, doc, tests, contrat de données stable |

**Cas d'usage clés :**
1. *Préparer un concours jamais vu* → coller l'URL/PDF du règlement → IA propose une définition → relecture humaine → lancement.
2. *Session terrain multi-poste sans internet fiable* → un PC serveur, tablettes en navigateur sur le WiFi local, backup auto.
3. *Chasser un multiplicateur* → spot cluster/RBN → copilote signale l'impact score → log en 1 raccourci.
4. *Après-concours* → export Cabrillo/EDI → upload LoTW/eQSL/ClubLog → débrief IA.

---

## 4. Périmètre existant (socle à préserver)

Inventaire de référence de ce qui est **déjà livré** — sert de baseline de non-régression.

### 4.1 Moteur & données
- **Moteur de score générique à briques composables** (`logx_scoring.py`) : prédicats nommés (`same_country`, `different_continent`, `is_na/eu/asia`, `prefix_in`…), 7 familles de multiplicateurs, règles de points filtrables par bande, `mult_weight_by_band`, options transverses (bonus même carré, boost propagation, plafond ON4KST). Preuve de non-régression : **44 064 comparaisons** ancien/nouveau moteur, identiques.
- **Base intégrée** : **36 concours** prêts à l'emploi (REF, IARU R1, CQ WW/WPX, ARRL DX/FD, SOTA/POTA, WAE, UBA, Russian DX, All Asian, Stew Perry, ARRL 10/160m…) + **358 concours mondiaux** WA7BNM préparables en un clic.
- **Contrat de données** : `contest_schema.json` (JSON Schema 2020-12) + `validate_definitions.py` valide les définitions **contre le moteur lui-même** (désync impossible).

### 4.2 IA
- **Copilote temps réel** (`logx_prompts.py`) : recommandation de QSO selon spot, propagation, distance, impact score.
- **Lecture automatique de règlement** (`logx_rules_ai.py`, `logx_rules.py`) : extraction PDF fiable (pymupdf→pdfplumber→pypdf), PDF natif en vision (Anthropic), sortie JSON forcée (tool use), **passe de vérification adversariale** (checklist de 8 pièges), citations sources obligatoires, **relecture humaine obligatoire** avant sauvegarde, multilingue.
- **Corpus d'évaluation** (`eval_extraction.py`) : 3 règlements réels notés champ par champ.

### 4.3 Interfaçage radio & réseau
- CAT via Hamlib/rigctld (`logx_rig.py`, `logx_cat.py`), rotor (`logx_rotor.py`), ampli (`logx_amp.py`), TCI (`logx_tci.py`), pont WSJT-X (`logx_wsjtx.py` / `logx_adifnet.py`).
- Clusters multi-sources (`logx_clusters.py`), RBN (`logx_rbn.py`), PSK Reporter (`logx_psk.py`), beacons (`logx_beacons.py`).

### 4.4 Métier & sortie
- Callbook QRZ (`logx_callbook.py`, `logx_qrz.py`), call history/SCP (`logx_callhistory.py`), DXCC/pays (`logx_dxcc.py`, `logx_countries.py`, `cty.dat`).
- Activations POTA/SOTA/IOTA/WWFF (`logx_activation.py`), départements REF (`logx_departments.py`, `france_departements.geojson`), diplômes (`logx_awards.py`).
- Export Cabrillo/EDI/ADIF (`logx_export.py`), import (`logx_import.py`), QSL/upload eQSL/ClubLog + LoTW (`logx_qsl.py`), scoreboard (`logx_scoreboard.py`), archive (`logx_archive.py`), backup (`logx_backup.py`).
- **QTC** (échanges QTC type WAE) : `qtc_log.json`.
- Propagation (`logx_propagation.html`, `logx_tropo.py`, `logx_meteors.py`).
- **Annuaire WebSDR + guide de configuration** (`logx_websdr.py`, `logx_websdr.html`) : écoute déportée quand la station n'a pas de récepteur sur une bande.

### 4.5 UX & plateforme
- Frontend : pages HTML (config, logbook, carte, calendrier, propagation, départements, mobile, scope, panel) + `logx_statusbar.js`, `logx_logbook.js`, `logx_i18n.js`, PWA (`logx_sw.js`).
- **Assistant nouveau concours** (3 clics), **mode débutant/expert**, **barre de statut permanente** (compte à rebours, backups, check règlements), **backup auto** (démarrage + toutes les 5 min).
- Distribution : app autonome PyInstaller (`LogXAI.exe` ~35 Mo, build Win/macOS), serveur local port 8080, multi-poste WiFi, données dans le profil utilisateur.
- i18n : 8 langues (UI + agent + coach), auto-détection navigateur.

### 4.6 Robustesse réseau (durcissement récent, orienté diffusion publique)
Travaux déjà commités (branche `fix/audit-securite-robustesse-perf` et main) :
- Plus aucun appel bloquant dans le thread HTTP ; `/log/list` ne garde plus le `log_lock` pendant l'envoi réseau ; compteur de version pour ne pas retransmettre tout le log à chaque poll de 5 s.
- Diagnostic réseau automatique au démarrage (portable, sans dépendre d'un antivirus précis) ; remplacement de `localhost` par `127.0.0.1` partout (latence antivirus).
- Spots POTA en direct via `api.pota.app` ; annuaire WebSDR nettoyé des stations hors service.

### 4.7 Infra dépôt existante
- **Dépôt** : `github.com/sauveteur71/radioaamateur-program-Contest` (88 commits, Python 52,7 % / HTML 30,1 % / JS 16,9 %). Cœur applicatif dans `concours/` (**118 fichiers suivis**).
- **CI déjà en place** : `.github/workflows/check.yml` — sur push/PR touchant `concours/**` : `pytest`, `logx_validate.py`, `logx_eval.py --mock`.
- **Docs suivies** : `docs/GUIDE_UTILISATEUR.md`, `docs/LogX_AI_Presentation.docx`. **Pas de README racine** (voir EV-6.4).
- **Hygiène secrets déjà correcte** : `.gitignore` exclut `clef API.txt`, `config.json`, `logx.db`, `calldb.json`, tokens et états de sync (voir R1 corrigé).
- **Branches actives** : `main`, `feat/aide-config-websdr-guide`, `fix/audit-securite-robustesse-perf` (1 PR ouverte).
- **Nota** : les documents de préparation (`Plan_Bataille_RadioContest_AI.md`, `Analyse_QSODirector_Roadmap.md`, PDF/DOCX de rallye) sont **volontairement git-ignorés** — le dépôt public n'a donc aujourd'hui **aucune roadmap publiée** ; ce PRD (une fois expurgé) et un README combleraient ce manque.

---

## 5. Modèle de données (contrat actuel)

Source de vérité : `config.json` + `contest_schema.json` + `logx.db` (SQLite) + `shared_log.json`.

### 5.1 Entités principales
- **Station** : callsign (+ portable), locator, ville, département, DXCC, continent, lat/lon, puissance/classe, antennes par bande, opérateur, club, section, format de log.
- **Contest (définition)** : `id`, `name`, bandes, modes, règle de dates (grammaire ouverte `DATE_RULE_PATTERN`), `start_utc`/`end_utc`/`duration_h`, `scoring` (soit `type` historique, soit `bricks` composables), exchange, URL de soumission, deadline, notes, source (`intégré` / `🤖 IA+relecture` / `WA7BNM`).
- **QSO** : identifiant, timestamp UTC, callsign, bande, mode, fréquence, RST envoyé/reçu, exchange, locator/grid, points calculés, multiplicateur, statut (dupe/mult/confirmé), source (manuel/WSJT-X/réseau).
- **Operator**, **Site**, **Frequencies**, **Clusters/Propagation**.

### 5.2 Contrats à figer pour l'open-source (voir EV-6.x)
Le PRD acte que **le schéma QSO et le schéma contest sont des contrats publics versionnés** : toute évolution passe par un numéro de version et une migration. C'est la condition pour que des contributeurs et des outils tiers s'appuient dessus.

---

## 6. Architecture & contraintes techniques

- **Backend** : Python, découpé en modules `logx_*.py` (Phase 0), point d'entrée léger `logx_serveur.py`, serveur HTTP local (`logx_http.py`), stockage `logx_storage.py`, persistance SQLite + JSON.
- **Frontend** : HTML/CSS/JS natif (pas de framework), servi par le backend local. **Dette identifiée** : pages monolithiques de 1000-4000 lignes, logique métier mêlée à la présentation (voir EV-7).
- **IA** : multi-fournisseur (Anthropic / OpenAI / Gemini), clé par fournisseur, contrat = `contest_schema.json`.
- **Contraintes structurantes** :
  - Le serveur local **ne peut pas accéder au HTTPS sortant** dans certains cas → le navigateur pousse les spots au serveur via `POST /data/spots` (bug historique corrigé en Phase 0). Toute nouvelle intégration réseau doit tenir compte de ce sens de flux.
  - Un seul port (8080), une seule instance à la fois.
  - Offline-first : le terrain n'a pas toujours de réseau.
  - Exécutable non signé (SmartScreen/Gatekeeper) → chantier signature pour la diffusion publique.

---

## 7. Évolutions à venir — exigences détaillées

> Les 4 domaines priorisés + le chantier phare architecture + le refactor frontend. Chaque item : user story, critères d'acceptation, accroche code, priorité/effort.

### EV-1 — Import ADIF & callbook en cascade **(P0)**

#### EV-1.1 Assistant d'import ADIF — *P0 · M · `logx_import.py`*
**User story :** *En tant qu'opérateur venant d'un autre logiciel, je veux importer mon historique ADIF pour voir tout de suite mes QSO dans LogX AI.*
**Exigences :**
- Assistant en quelques étapes (choisir fichier → mapping/options → prévisualisation → confirmation → rapport).
- Validation contre les **énumérations ADIF 3.1.7 officielles** (fichiers TSV/JSON machine-readable, cf. doc ressources §1.1) plutôt qu'une liste codée à la main.
- Déduplication à l'import (call+bande+mode+date à la minute près, seuil configurable).
- Rapport final : n importés / n ignorés (doublons) / n en erreur, avec cause par ligne.

**Critères d'acceptation :**
- *Étant donné* un fichier ADIF de 5 000 QSO issu d'un autre logger, *quand* je lance l'import, *alors* les QSO valides apparaissent au log, les doublons sont signalés et aucun champ inconnu ne casse l'import.
- *Étant donné* un champ ADIF non conforme, *quand* j'importe, *alors* la ligne est rejetée avec un message citant le champ et la valeur fautive (pas de crash global).

#### EV-1.2 Callbook en cascade multi-source avec repli gratuit — *P0 · M · `logx_callbook.py` / `logx_qrz.py` / `logx_callhistory.py`*
**User story :** *En tant qu'opérateur sans abonnement QRZ, je veux que le lookup fonctionne quand même via des sources gratuites.*
**Exigences :**
- Cascade configurable : Primaire / Secondaire / Tertiaire, avec mode *Use First Response* ou *Merge*.
- Sources : **Previous QSOs (SCP local, gratuit, en tête)** → QRZ (payant) → **HamQTH** (session XML gratuite) → **HamDB / callook.info** (gratuit sans clé).
- Écran « identifiants callbook » pour stocker les credentials par service.
- Repli automatique si une source échoue/timeout.

**Critères d'acceptation :**
- *Étant donné* QRZ non configuré, *quand* je saisis un indicatif, *alors* HamQTH ou HamDB répond et remplit ville/DXCC/locator sans erreur bloquante.
- *Étant donné* la source locale « Previous QSOs », *quand* l'indicatif a déjà été travaillé, *alors* la réponse locale est retournée sans appel réseau.

---

### EV-2 — Interopérabilité réseau générique **(P1)**

#### EV-2.1 Serveur ADIF-over-UDP configurable — *P1 · M · `logx_adifnet.py`*
**User story :** *En tant qu'opérateur multi-logiciels, je veux que LogX AI reçoive des QSO/spots de n'importe quel outil parlant ADIF en réseau, pas seulement WSJT-X.*
**Exigences :**
- Petit serveur/port UDP configurable (host, port, filtre IP) réutilisant la fonction factorisée `add_qso_to_log()`.
- Actions à la réception : logger le contact, ajouter un spot, lookup callbook auto.
- Network Listeners **et** Network Senders (émettre nos propres QSO/spots vers des outils tiers).

#### EV-2.2 Compatibilité protocole N1MM+ — *P1 · M · `logx_adifnet.py`*
**User story :** *Je veux brancher LogX AI à l'écosystème N1MM/DXLog/Log4OM.*
**Exigences :**
- Écoute des messages **N1MM External UDP** (XML UTF-8) : `Contact`, `ContactReplace/Delete`, `Spot`, `RadioInfo`, `Score`, `AppInfo`, `LookupInfo`.
- Port par défaut **12060**, UDP unicast/broadcast, `SO_REUSEADDR` (partage de port).
- Attention aux fréquences en unités de 10 Hz (pas de décimale) — cf. doc ressources §4.4.

**Critères d'acceptation :**
- *Étant donné* un émetteur envoyant un `contactinfo` N1MM sur 12060, *quand* LogX AI écoute, *alors* le QSO est loggé avec call/bande/mode/heure corrects et la fréquence convertie.
- *Étant donné* un message d'édition (`ContactReplace`), *quand* il est reçu, *alors* le QSO correspondant est mis à jour (pas dupliqué).

---

### EV-3 — Cloud sync multi-poste **(P1)**

#### EV-3.1 Synchronisation à 3 niveaux — *P1 · L · `logx_cloudsync.py` / `logx_mobile.html`*
**User story :** *En tant qu'opérateur avec plusieurs installations (station + secours + poste isolé), je veux garder mes QSO cohérents entre elles.*
**Exigences :**
- Trois modes : **Full Synchronisation** (recommandé, bidirectionnel) / **Push Only** (poste de secours qui ne fait que pousser) / **No Synchronisation** (isolé volontaire).
- Périmètre synchronisé : QSO, stations, opérateurs, emplacements, événements.
- **Self-hostable / optionnel** (cohérent avec l'anti-vision « pas de cloud obligatoire ») : le transport de sync ne doit pas exiger un service propriétaire du projet.
- Résolution de conflits déterministe (dernier écrit gagnant par champ, ou horodatage QSO), et journal de sync.

**Critères d'acceptation :**
- *Étant donné* deux postes en Full Sync, *quand* l'un logge un QSO hors ligne puis se reconnecte, *alors* le QSO apparaît sur l'autre poste sans doublon ni perte.
- *Étant donné* un poste en Push Only, *quand* il pousse, *alors* il n'importe jamais les QSO des autres.

---

### EV-4 — Layouts, alertes & activations **(P1)**

#### EV-4.1 Constructeur de règles d'alerte — *P1 · M · `logx_alerts.py`*
**User story :** *En tant que chasseur, je veux définir mes propres alertes (pays + statut travaillé + zone) et pas seulement des alertes figées.*
**Exigences :** règles nommées, activables, combinant 2-3 critères pour commencer (pays/entité DXCC, zone CQ/ITU, statut travaillé nouveau/déjà/confirmé, type d'activation POTA/SOTA/IOTA/WWFF, rang « most wanted »). Option filtre global.
**Critère d'acceptation :** *Étant donné* une règle « nouveau DXCC en 6m », *quand* un spot matche, *alors* une alerte se déclenche et est visible/audible.

#### EV-4.2 Extension programmes d'activation — *P2 · S/M · `logx_activation.py`*
Ajouter **ARLHS (phares)** et **WCA (châteaux)** — extension de champs et de format de référence, pas de nouvelle architecture. Les autres (ILLW/WLOTA/COTA/BOTA) à la demande.

#### EV-4.3 Toggles individuels des sources cluster + cluster personnalisé — *P2 · S · `logx_clusters.py`*
Exposer les sources déjà codées sous forme de toggles CONFIG + champ « cluster telnet perso host:port ». Répertoire par défaut basé sur la liste REF (cf. doc ressources §3.1).

#### EV-4.4 Panneaux d'info ponctuels — *P2 · S chacun*
Widget Time of Day (arc lever/coucher), graphe de rythme QSO/heure sur la session complète (débrief), vue Great Circle (cercles concentriques centrés QTH) comme mode de la carte existante, Worked Matrix (bande × mode).

#### EV-4.5 Relevé manuel MUF/propagation par balises NCDXF/IBP — *P1 · S/M · `logx_beacons.py` / `logx_propagation.html`*

**User story :** *En tant qu'opérateur en terrain sans connexion Internet fiable, je veux enregistrer ce que j'entends sur les balises NCDXF/IBP (niveau reçu : 100 W / 10 W / 1 W / rien) pour connaître en temps réel la MUF et la meilleure fréquence d'ouverture vers une région donnée, sans dépendre d'un cluster/RBN en ligne.*

**Contexte (retour terrain, groupe TX7N, 21/07/2026) :** `beacons_now()` calcule déjà QUI émet MAINTENANT sur chaque bande (calcul d'horloge pur, sans réseau, cf. §4.3) mais ne capture pas ce que l'opérateur ENTEND réellement. Des opérateurs expérimentés du groupe décrivent la technique manuelle qu'ils pratiquent déjà : sur un cycle complet de 3 minutes, noter le niveau reçu de chaque balise (100 W / 10 W / jusqu'à s'efforcer d'entendre le 1 W) ; en se concentrant sur les 3 bandes hautes, en déduire la MUF ; en suivant la MÊME balise du 20 m au 10 m, établir avec un fort niveau de fiabilité quelle fréquence « passe » sur ce trajet ionosphérique précis (utile pour cibler un pile-up) — le tout sans aucune connexion Internet, juste un récepteur et l'oreille. C'est exactement le complément « offline » du solaire/MUF déjà en ligne (N0NBH/KC2G) et des clusters/RBN (qui, eux, dépendent tous d'Internet).

**Exigences :**
- Relevé manuel rapide (clic/raccourci clavier) pendant le cycle de 3 minutes : pour la balise actuellement active sur chaque bande (déjà calculée par `beacons_now()`), noter le niveau entendu (100 W / 10 W / 1 W / 100 mW / rien).
- À partir de ces relevés, estimer et afficher : (a) la MUF actuelle — la bande la plus haute où au moins une balise a été entendue ; (b) pour une balise/région donnée, la meilleure bande actuelle sur ce trajet précis (comparaison des niveaux entendus pour LA MÊME balise sur ses passages successifs bande par bande dans le cycle).
- Fonctionne 100 % hors ligne (aucun appel réseau) — cohérent avec l'anti-vision « offline-first » déjà actée (§8) et complémentaire, pas redondant, du solaire/MUF en ligne et du cluster/RBN.
- Option : historiser les relevés sur la session pour visualiser l'évolution de la MUF/propagation dans le temps (graphe simple, comme le rythme QSO/h du débrief).

**Critères d'acceptation :**
- *Étant donné* un cycle de balises en cours, *quand* j'enregistre le niveau entendu pour chaque bande active, *alors* l'app affiche une MUF estimée cohérente avec mes relevés (la bande la plus haute avec un niveau renseigné autre que « rien »).
- *Étant donné* que j'ai suivi une même balise (ex. CS3B) sur plusieurs bandes au cours d'un même cycle, *quand* je consulte son détail, *alors* l'app m'indique la bande où elle a été reçue avec le niveau le plus fort — sans aucun appel réseau.

---

### EV-5 — Chantier phare : espace de travail à layouts nommés **(P1 · L)**

**Positionnement :** évolution structurante majeure — le vrai différenciateur d'ergonomie. On ne copie **pas** un système de docking générique façon IDE (coûteux, fragile sur le web). On vise le **même bénéfice** avec une approche plus simple, déjà à moitié en place (fenêtres détachables déjà livrées).

**User story :** *En tant qu'opérateur, je veux composer mon espace de travail et basculer d'un mode « Contest » à « Activation POTA » à « Log général » en un clic.*

**Exigences :**
- **Détachement généralisé** de TOUS les blocs (Log Book, Coach, Cluster, Band Map, Solar Weather, Carte, Worked Matrix…), en s'appuyant sur le détachement déjà livré pour certains widgets.
- **Layouts nommés** persistés (JSON/localStorage) : quels panneaux ouverts, sur quel écran, à quelle taille → *Sauvegarder / Charger / Renommer / Réinitialiser*.
- **Association layout ↔ mode d'activité** : un layout par défaut pour « Log général / Contest / Activation / NET ».
- Le sélecteur de mode d'activité est la porte d'entrée.

**Critères d'acceptation :**
- *Étant donné* un layout « Contest » sauvegardé, *quand* je le charge, *alors* les panneaux réapparaissent aux bons endroits/tailles/écrans.
- *Étant donné* que je passe en mode « Activation », *quand* le mode change, *alors* le layout par défaut associé s'applique.

**Dépendances / séquencement :** s'appuie sur le multi-écran/fenêtres détachables existant ; à traiter **après** stabilisation des features métier P0 pour ne pas empiler le risque. **Fort couplage avec EV-7** (un frontend modularisé rend ce chantier réaliste).

---

### EV-6 — Exigences open-source public **(P0 pour la diffusion)**

#### EV-6.1 Licence & gouvernance — *P0 · S*
**Tranché (07/08/2026) : GPLv3** — cohérent avec l'écosystème ham libre Tucnak/qxsl/Cloudlog, fichier `LICENSE` ajouté à la racine. Reste à faire : `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, gabarits d'issue/PR (`.github/`).

#### EV-6.2 Contrats de données publics versionnés — *P0 · S · `contest_schema.json`*
Publier `contest_schema.json` et le schéma QSO comme **contrats stables** avec numéro de version et politique de migration. C'est la fondation de l'interop tierce.

#### EV-6.3 Qualité & CI — *P1 · M · `.github/workflows/check.yml`*
**La CI existe déjà** (pytest + `logx_validate.py` + `logx_eval.py --mock` sur push/PR `concours/**`). Il reste à **l'étendre** : ajouter un **lint** (ruff/flake8), le **build multiplateforme** de l'exécutable (Windows + macOS via runner `macos-latest`, déjà envisagé) et la **publication de releases** reproductibles (aujourd'hui aucune release publiée).

#### EV-6.4 README, i18n complète & documentation — *P1 · M · `logx_i18n.js`, `logx_coach_i18n.py`, `docs/`*
- **README racine manquant** (P0 pour l'open-source) : pitch, captures, installation, licence, lien vers `docs/GUIDE_UTILISATEUR.md`, statut des fonctionnalités.
- Externaliser 100 % des chaînes ; compléter doc contributeur + doc d'architecture (le guide utilisateur existe déjà).
- Signature de l'exécutable (Windows/macOS) pour supprimer SmartScreen/Gatekeeper.

#### EV-6.5 API locale publique documentée — *P2 · M · `logx_http.py`*
Documenter les endpoints locaux (`/data/*`, `/log/*`, `/rules/*`, `/data/spots`…) comme une API stable pour outils tiers, en s'inspirant du modèle REST de Cloudlog/Wavelog.

---

### EV-7 — Refactor frontend (dette technique) **(P1 · L)**

**Constat :** 3 HTML de 1000-4000 lignes, logique métier mêlée à la présentation — même douleur que le backend avant la Phase 0. Bloque l'ajout de features sans régression et rend EV-5 (layouts) difficile.

**User story (mainteneur) :** *Je veux ajouter/détacher un panneau sans risquer de casser une page entière.*

**Exigences :**
- Extraire la logique métier des HTML vers des modules JS réutilisables (composant « panneau » unifié : monter/détacher/redimensionner/persister).
- Séparer données / rendu / état ; API interne stable entre panneaux.
- Rester en **HTML/JS natif** (pas de framework lourd imposé) — modularisation ES modules, pas réécriture Big Bang.
- **Filet de sécurité obligatoire** : constituer d'abord une suite de non-régression UI (comme le test d'or 44 064 côté scoring) avant de refactorer.

**Critères d'acceptation :**
- *Étant donné* le refactor d'une page, *quand* je rejoue le parcours config→assistant→log→export, *alors* le comportement est identique à la baseline (aucune régression).
- *Étant donné* un nouveau panneau, *quand* je l'ajoute, *alors* il réutilise le composant panneau commun (monter/détacher/persister) sans dupliquer de code.

---

## 8. Exigences non-fonctionnelles

- **Fiabilité / zéro perte** : backup auto (déjà là), transactions SQLite, mode dégradé si réseau/IA indisponible (l'appli doit logger même sans IA ni internet).
- **Performance** : log fluide en session intense (rate élevé), import ADIF de dizaines de milliers de QSO sans blocage UI.
- **Offline-first** : toutes les fonctions cœur (log, score, export) marchent sans internet ; les fonctions réseau (callbook, cluster, IA) dégradent proprement.
- **Sécurité / vie privée** : clés API et credentials stockés localement, jamais commités (déjà : `config.json` git-ignoré, `clef API.txt` à sortir du repo — cf. §10 risques) ; pas de télémétrie cachée.
- **Portabilité** : Windows + macOS (+ Linux via mode dev) ; un seul exécutable autonome.
- **Accessibilité & i18n** : 8 langues aujourd'hui, cible = chaînes 100 % externalisées, mode débutant/expert conservé.
- **Compatibilité standards** : ADIF 3.1.7, Cabrillo v3 (WWROF), EDI/REG1TEST (IARU R1), cty.dat (AD1C) — conformité vérifiable (ex. via adif-multitool).

---

## 9. Intégrations externes (registre)

| Domaine | Intégration | Statut | Réf. ressource |
|---|---|---|---|
| Format QSO | ADIF 3.1.7 (TSV/JSON officiels) | À brancher sur validation | doc §1.1 |
| Contest HF | Cabrillo v3 (WWROF) | Existant | doc §1.2 |
| Contest THF | EDI/REG1TEST (IARU R1) | Existant, à durcir | doc §1.3 |
| Pays/DXCC | cty.dat (AD1C) | Existant, auto-refresh à ajouter | doc §1.4 |
| Callbook | QRZ / HamQTH / HamDB / callook | QRZ ok, cascade à faire (EV-1.2) | doc §2 |
| Spots | Cluster REF / RBN / PSK Reporter | Existant | doc §3 |
| Activations | POTA/SOTA API, ParksNPeaks | Existant, extension EV-4.2 | doc §3.4-3.5 |
| CAT | Hamlib/rigctld, TCI | Existant | doc §4.1-4.2 |
| Interop | WSJT-X UDP, N1MM UDP, ADIF-UDP | WSJT-X ok, reste EV-2 | doc §4.3-4.4 |
| Propagation | HamQSL/N0NBH XML, VOACAP | Existant | doc §5 |
| Upload | LoTW (TQSL), eQSL, ClubLog, HamQTH | Existant | doc §6 |

*(« doc » = LogX_AI_Ressources_Techniques.md, livré le 21/07/2026.)*

---

## 10. Risques & dette technique

- **R1 — Secrets : ✅ déjà maîtrisé (vérifié le 21/07)** : `concours/clef API.txt` est **git-ignoré, jamais commité, non suivi** ; `config.json`, `logx.db`, `calldb.json`, tokens et états de sync le sont aussi. Aucune fuite dans l'historique. *Reste conseillé* : documenter la config des clés par variable d'environnement et ajouter une vérification anti-secret en CI (garde-fou pour les contributeurs futurs).
- **R2 — Frontend monolithique** : ralentit toute évolution (traité par EV-7).
- **R3 — Dépendance API IA payantes** : garder le mode « sans IA » pleinement fonctionnel ; l'IA est un plus, pas un prérequis.
- **R4 — APIs tierces changeantes** (POTA, HamQTH, WA7BNM…) : couche d'abstraction par source + tests de contrat ; `log()` explicite en cas de source indisponible (pas d'échec silencieux).
- **R5 — Exécutable non signé** : friction d'installation (SmartScreen/Gatekeeper) — traité par EV-6.4.
- **R6 — Barèmes « à confirmer »** dans certaines définitions Phase 4 : les faire valider via l'analyse IA + relecture avant usage en compétition.

---

## 11. Métriques de succès (mesurables)

- **M1 — Temps config→lancement** d'un concours connu : ≤ 60 s / 3 clics (déjà atteint, à préserver).
- **M2 — Qualité extraction IA** : score `eval_extraction.py` par champ ≥ seuil cible (mesurer avec/sans passe de vérification pour prouver l'apport).
- **M3 — Couverture concours** : % de concours du calendrier de l'opérateur jouables sans code (base + IA).
- **M4 — Perte de log** : 0 QSO perdu sur N sessions terrain.
- **M5 — Interop** : import ADIF d'un logger tiers réussi ; réception d'un flux N1MM/WSJT-X validée.
- **M6 — Open-source** : présence licence + CI verte + doc contributeur ; puis stars/forks/issues/PR externes dans le temps.

---

## 12. Roadmap & séquencement proposé

> Priorité par valeur/risque, en tenant compte des dépendances. Les efforts sont indicatifs (S/M/L).

**Jalon A — Interop & onboarding (valeur immédiate, faible couplage)**
1. EV-1.1 Import ADIF (P0, M)
2. EV-1.2 Callbook cascade + repli gratuit (P0, M)
3. EV-4.3 Toggles clusters + cluster perso (P2, S)
4. EV-6.1/6.2 Licence + contrats de données + retrait `clef API.txt` (P0, S) — *à faire avant toute ouverture publique*

**Jalon B — Écosystème réseau**
5. EV-2.1 Serveur ADIF-over-UDP (P1, M)
6. EV-2.2 Compat N1MM UDP (P1, M)
7. EV-6.3 CI + build multiplateforme (P1, M)

**Jalon C — Multi-poste & chasse**
8. EV-3.1 Cloud sync 3 niveaux (P1, L)
9. EV-4.1 Constructeur d'alertes (P1, M)
10. EV-4.2 Extension activations ARLHS/WCA (P2, S/M)
11. EV-4.5 Relevé manuel MUF/propagation par balises NCDXF/IBP (P1, S/M)

**Jalon D — Fondations UI (chantier long)**
12. EV-7 Refactor frontend + filet de non-régression UI (P1, L)
13. EV-5 Espace de travail à layouts nommés (P1, L) — *après EV-7*
14. EV-4.4 Panneaux ponctuels (Time of Day, graphe rythme, Great Circle, Worked Matrix)

**Transverse continu :** EV-6.4 (i18n complète, doc, signature), EV-6.5 (API locale documentée), Phase 5 (validation terrain sur RPH puis concours étranger, `eval_extraction.py` régulier).

---

## 13. Questions ouvertes (à trancher)
- ~~**Licence**~~ : tranché le 07/08/2026 → **GPLv3**, voir EV-6.1.
- **Transport du cloud sync** : quel mécanisme self-hostable (fichier partagé Synology déjà en place ? WebDAV ? petit service Git ? endpoint HTTP simple) ?
- **Refactor frontend** : jusqu'où aller (ES modules seuls vs micro-framework léger type Preact/Alpine) sans trahir « HTML/JS natif » ?
- **Signature exécutable** : budget certificat Windows / notarisation Apple ?

---

## 14. Glossaire (rappel)
ADIF (format d'échange QSO) · Cabrillo (soumission contest HF) · EDI/REG1TEST (soumission contest THF IARU R1) · cty.dat (fichier pays/DXCC) · RBN (Reverse Beacon Network) · SCP (Super Check Partial, historique d'indicatifs) · CAT (Computer Aided Transceiver) · POTA/SOTA/IOTA/WWFF (programmes d'activation) · S&P / RUN (Search & Pounce / appel) · LoTW (Logbook of the World, ARRL).

---

*Documents liés : `Plan_Bataille_RadioContest_AI.md` (phases 0-5, git-ignoré), `Analyse_QSODirector_Roadmap.md` (analyse concurrentielle, git-ignoré), `docs/GUIDE_UTILISATEUR.md` (suivi dans le dépôt), `LogX_AI_Ressources_Techniques.md` (ressources & specs, 21/07/2026).*
*Base vérifiée : dépôt `github.com/sauveteur71/radioaamateur-program-Contest` @ 88 commits, branche `feat/aide-config-websdr-guide`.*
