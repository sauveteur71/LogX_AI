# Veille concurrentielle — OpsLog (+ DXHunter)

> Rédigé le 26/08/2026 à la demande de F4GLD, à partir du README public **et**
> d'une reconnaissance terrain : OpsLog installé et photographié écran par
> écran (104 captures, en français). Document interne — ne jamais citer un
> concurrent dans l'UI du produit (règle permanente du dépôt).

## 1. Qui est le concurrent

Un même auteur, **GregTroar** (github.com/GregTroar), publie deux logiciels qui
montent et concurrencent LogX AI :

- **DXHunter** — client DX cluster **seul** (Go binaire unique + Svelte). Ne
  log pas : il enrichit les spots depuis un logbook tiers (Log4OM / HRD /
  OpsLog). Croise chaque spot avec le carnet (DXCC / bande / mode / créneau
  nouveaux → code couleur), CAT OmniRig/FlexRadio, watchlist suffix-aware,
  monitoring FT8/FT4, dashboard type ClubLog.
- **OpsLog** — **carnet de bord complet**, concurrent frontal. Go + React via
  **Wails**, **Windows natif**, SQLite (config) + MySQL optionnel (log partagé
  multi-op). **Bilingue EN/FR** (français idiomatique) → vise explicitement le
  marché francophone de F4GLD. Gratuit (dons PayPal), Discord actif, dev très
  soutenu (versions 0.26.x, changelog détaillé et pédagogique).

## 2. Ce que la reconnaissance terrain a montré (preuves, pas README)

**Écran principal (dense, style Log4OM) :**
- Barre de saisie avec ~20 champs visibles simultanément (indicatif, RST tx/rx,
  nom, QTH, état, locator, bande, mode, pays, comté, CQ, ITU, DXCC,
  commentaire, note, fréq TX/RX, bande RX, badge LoTW…).
- Panneau à onglets **Stats (F1) / Info (F2) / Diplômes (F3) / Moi (F4) /
  Étendu (F5)** collé à la saisie. Stats = **matrice bande × mode** (lignes
  PH/CW/DIG) colorée (confirmé / contacté / entité / jamais contacté / saisie
  en cours). Diplômes (F3) contextuel à l'indicatif tapé (références POTA…).
  Moi (F4) = azimut / élévation / puissance TX / chemin antenne / propagation
  / station / antenne + « Mode satellite ».
- **Compas rotor** toujours visible (azimuthal-équidistant, boutons rapides
  EU/NA/SA/VK/JA/AF, 0-359 GO, STOP, SP/LP).
- **Double carte** : grand-cercle (Light/Voyager/Street/Satellite, Zoom DX,
  Grey line, distance/azimut) + carte QTH locale avec rectangle de carré
  locator.
- **Panadapter** intégré sur le bord droit (échelle px/kHz, FIT/FTx, légende
  couleur des spots : nouveau DXCC/bande/mode/POTA/comté, CW/Numérique/Phonie).
- Barre d'état : QSO count, indicateurs Cluster / CAT / Rotator / HORS LIGNE,
  horodatage UTC, chemin de la base.

**Arbre de réglages ÉNORME (~30 panneaux)** répartis en :
- *Configuration utilisateur* : Informations station, Profils, Conditions
  d'opération, Confirmations, Diplômes, Services externes.
- *Configuration logicielle* : Général, Apparence, E-mail (SMTP), Recherche
  d'indicatif, Listes (Bandes / Modes & RST / Satellites), DX Cluster,
  Connexions, Moniteur ADIF, Synchro entre PC, Publication web, Comtés US,
  Base de données, Démarrage auto.
- *Maintenance* : Bases de données.
- *Configuration matérielle* : Interface CAT, Rotator, Manipulateur CW, Antenne
  motorisée, Antenna Genius, Tuner Genius, Amplificateur, Alimentation, Relais
  automatiques, Périphériques audio.

**Réglages tout-manuel** (Interface CAT) : radio, slot OmniRig, VFO à lire,
intervalle de poll (ms), délai CAT (ms), décalage transverter, mode numérique
par défaut, partage CAT (Hamlib NET rigctl 127.0.0.1:4532 ou TCI 40001), PTT,
« régler le mode avant la fréquence ». Puissant, mais l'opérateur doit tout
savoir.

**Périphériques audio** : enregistreur de QSO (dossier, pré-enregistrement 8 s,
WAV, niveaux radio/relecture/micro), envoi auto de l'enregistrement par e-mail,
messages du manipulateur vocal F1-F6 avec méthode PTT.

**Menu Outils (exhaustif)** : Gestionnaire QSL, Statistiques, Contrôle station,
Decodes FT, Carrés locator, Créateur de carte QSL, Manipulateur CW WinKeyer,
Manipulateur vocal numérique, Décodeur CW (audio RX), Contrôle de NET, Mode
contest, Gestion des alertes, Trouver les doublons. **→ Aucune IA nulle part.**

**Contrôle de NET (vu en vrai)** : deux colonnes « EN L'AIR — QSO ACTIFS » /
« MEMBRES DU NET — RÉPERTOIRE », « Nouveau NET », sélecteur de NET, drag-to-log,
« ordre de passage du micro · ↕ pour réordonner · double-clic → éditer ·
Logger & terminer ».

## 3. Forces réelles d'OpsLog (à respecter)

1. **Profondeur d'intégration station** : 4 moteurs CAT natifs dont **Icom
   distant sans RS-BA1** (protocole IC-7610 natif over-the-top) et **TCI**
   (SunSDR/ExpertSDR2) ; amplis PowerGenius/SPE/ACOM avec télémétrie ; rotors
   PstRotator / 4O3A Rotator Genius / microHAM ARCO ; Antenna/Tuner Genius ;
   **cartes relais** (WebSwitch, KMTronic, Denkovi, CH340) avec bascule auto
   par bande.
2. **Net Control** poli (drag-to-log, ordre du micro) — fort levier sur le
   marché FR (réseaux de clubs).
3. **Moteur de récompenses** riche + **détection de référence directe** +
   Rescan des confirmations.
4. **Coffre-fort chiffré** (AES-GCM + PBKDF2) pour les mots de passe.
5. **Créateur de carte QSL**, enregistrement audio par QSO, DVK.
6. **4 thèmes** dont **high-contrast** (accessibilité) ; bilingue FR idiomatique.
7. **Communication** : changelog français pédagogique, dev très actif.

## 4. Faiblesses exploitables (où percer)

1. **Densité écrasante / zéro progressivité** : ~20 champs de saisie + ~30
   panneaux de réglages, tout exposé d'emblée. Intimidant pour un débutant.
   → **Notre doctrine « l'axe = l'activité » + « intuitif » est l'anti-thèse
   exacte.** C'est notre marché : le débutant qui grandit (144 FM → HF SSB →
   FT8 → CW → DXpédition).
2. **Aucune IA.** Confirmé par le menu Outils complet. Notre roadmap copilote
   (validation log → enrichissement → NL → temps réel) est **inrattrapable**
   pour sa stack Go/Wails.
3. **Verrue POTA-DevTools** : l'intégration POTA exige de copier un jeton
   depuis les DevTools du navigateur (Network → header Authorization). Symptôme
   d'un logiciel d'expert-bricoleur. → On peut offrir une intégration propre.
4. **Windows-only, mono-poste desktop** (le changelog se bat avec la gestion
   multi-écrans Windows). → Notre approche **web** = accès depuis n'importe
   quel appareil du réseau (tablette au pied de l'antenne, Mac, Linux).
5. **Tout-manuel** (délai CAT, poll, VFO, transverter…). → Notre principe « le
   meilleur réglage est celui qu'on n'a pas à faire ».

## 5. Où LogX AI gagne — axes à tenir

1. **IA copilote = LE fossé** (voir roadmap copilote IA). Priorité n°1.
2. **Intuitivité / axe activité** : marché débutant + progression qu'OpsLog
   n'adresse pas.
3. **Web multi-plateforme** : accès tout appareil vs Windows-only.
4. **Autonomie / zone blanche** : lui dépend du cloud (ClubLog/QRZ/POTA/
   télémétrie). **⚠️ À corriger d'abord chez nous** : dépendance CDN
   Leaflet/Chart.js sans repli local — tant qu'elle existe, l'argument
   « plus autonome » se retourne contre nous.

## 6. Trous à combler en priorité (concept, pas code — licence à confirmer)

Réimplémentation propre obligatoire (usage perso amateur ≠ droit de copier) :

- **Net Control** (réseaux dirigés) — fort levier FR, module borné et clair.
- **TCI** + **Icom distant natif** — pour ne pas perdre les possesseurs
  SunSDR / Icom.
- **Thème high-contrast** (accessibilité, peu coûteux).
- **Coffre-fort chiffré** pour nos clés d'API stockées.
- **Intégration POTA propre** (là où lui bricole via DevTools).

## 7. Verdict

Ne pas viser « meilleur partout » : il a des années d'avance sur l'intégration
matérielle. **Gagner par l'IA + l'intuitivité + le web multi-plateforme + une
autonomie réelle**, viser la **parité suffisante** sur la profondeur CAT/ampli
(sans surenchère), et combler seulement les trous les plus visibles (Net
Control, TCI/Icom-distant, high-contrast, coffre chiffré, POTA propre).
