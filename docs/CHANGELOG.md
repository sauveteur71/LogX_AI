# Journal des modifications

Toutes les évolutions notables de LogX AI sont documentées dans ce fichier.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). LogX AI
n'a pas encore de politique de versionnage strictement [semver](https://semver.org/lang/fr/) —
les tags `vX.Y`/`vX.Y-betaN`/`vX.Y-rcN` servent surtout à déclencher la
construction des exécutables (voir `.github/workflows/build-release.yml`) et
à comparer la version installée à la dernière disponible. La version
affichée dans la barre de statut de l'application correspond à la constante
`APP_VERSION` de `logx_version.py`, qui doit être incrémentée à chaque tag
poussé.

## [Non publié]

### Ajouté

- **« Prochaines cibles recommandées » sur l'accueil.** Le cockpit d'accueil
  affiche, par entité déjà entamée, le prochain slot à aller chercher :
  **« à confirmer LoTW »** pour un pays travaillé mais pas encore confirmé, ou un
  **mode manquant** sur une bande déjà travaillée (ex. **« Japon · CW · 15 m »**).
  Priorisé par ce que vous avez le plus travaillé. Déterministe, calculé depuis
  votre log — un objectif concret plutôt qu'un chiffre abstrait.

### Modifié

- **Désencombrement du LOGBOOK.** Maintenant que le **fil IA « Ce que l'IA
  remarque »** rassemble tout, le **badge de validation** (en-tête) et la
  **pastille « après-QSO »** — qui faisaient doublon — ont été retirés ; le fil
  les résume, avec les mêmes actions au clic. Le **panneau Opportunités** (fiche
  FAIT/CALCUL/PROPOSITION + QSY) et la **pastille busted-call** (corriger/non)
  restent, car ils offrent plus que le résumé.

## [1.2-beta2] — 2026-08-28

### Sécurité

- **Durcissement du consentement d'émission (additif, rétro-compatible).** Le
  journal d'audit d'émission grave désormais l'**empreinte SHA-256 du message**
  (autorisation ET copilote FT8) : la trace prouve exactement ce qui a été
  autorisé et émis, un caractère changé donnant une empreinte différente.
  L'autorisation accepte en plus un **plafond de puissance** optionnel
  (`tx_max_power_w` en configuration) : au-delà, l'émission est refusée et le
  jeton n'est pas consommé — garde-fou anti-sur-puissance accidentelle. Sans
  configuration, le comportement est **inchangé**. Rien de tout cela ne modifie
  l'émission elle-même (la validation on-air reste le geste de l'opérateur).

### Ajouté

- **Mode local uniquement (économie de crédits).** Un interrupteur dans la
  configuration (section **Assistant IA**) coupe **tous** les appels réseau de
  l'IA : chat, analyse, plan de session, audit du log, analyse de règlement…
  basculent sur un repli propre — **zéro crédit dépensé**. Les moteurs
  **déterministes** (coach, validation du log, diplômes, distances,
  enrichissement) continuent normalement. Idéal en expédition ou pour maîtriser
  sa consommation. Verrouillé par des tests (repli + « aucun appel réseau »).

- **Cockpit d'accueil « Que puis-je faire maintenant ? ».** La page d'accueil
  affiche désormais, en plus des tuiles d'activité, un **cockpit** en un coup
  d'œil : les **opportunités** du moment (meilleures stations à travailler), la
  **progression** des diplômes (DXCC, départements, QSO) et l'**état de la
  station** (CAT, FT8, DXCC). Pour l'habitué, un gros bouton **« Reprendre :
  <dernière activité> »** repart en **un seul clic** — l'accueil ne redirige plus
  automatiquement, mais ne rallonge pas non plus le chemin quotidien. Lecture
  seule (agrège des endpoints existants), rien n'est piloté.

- **Fil IA unifié « Ce que l'IA remarque » (LOGBOOK).** Un seul panneau discret
  rassemble ce que l'IA observe, jusque-là éparpillé : les **opportunités** à
  travailler maintenant, les **QSO à vérifier**, les **gains du dernier QSO** et
  une éventuelle **correction d'indicatif** (busted-call) — chacun avec une
  pastille de couleur (attention / proposition / info) et, quand c'est utile, une
  action au clic (appeler, ouvrir VÉRIFIER, corriger). Priorisé, caché tant qu'il
  n'y a rien à dire. **Lecture seule**, les actions réutilisent les fonctions
  existantes (jamais d'émission). Les widgets d'origine restent en place.

- **Planificateur de session (assistant, consultatif).** Un nouvel écran **Plan
  de session** : vous indiquez vos contraintes (durée, objectif, mode(s),
  bande(s), puissance) et l'IA propose un **plan découpé en créneaux horaires**,
  avec pour chaque créneau la bande/mode à privilégier, la cible visée, et des
  **critères d'arrêt** clairs. C'est un **conseil** : rien n'est déclenché, aucun
  réglage ni aucune émission automatique — vous gardez le contrôle de chaque
  changement de fréquence et de chaque émission. Accessible depuis le menu
  **Outils** de toutes les pages.

- **Écran « Santé de la station ».** Une page de diagnostic qui montre en un coup
  d'œil l'état des sous-systèmes — **Radio (CAT)**, **Rotor**, **FT8/WSJT-X**,
  **Callbook**, **Synchro Cloud/MySQL**, **Base DXCC**, **Émission
  (consentement)** et **IA (consommation de tokens)** — chacun avec une pastille
  **verte** (OK) / **jaune**
  (attention) / **rouge** (à corriger) / **grise** (non configuré), plus
  l'**horloge UTC**. Lecture seule (agrège des endpoints d'état existants), rien
  n'est piloté. Rafraîchi automatiquement. Répond tout de suite à « est-ce que
  tout est prêt ? ». Une section **Progression des diplômes** (DXCC, départements
  FR, WAC, WAZ, total QSO) complète l'écran.

- **Suivi de consommation IA (tokens réels).** Comme vous payez vos propres
  crédits d'API, le logiciel compte désormais les **tokens réellement
  consommés** (entrée / sortie) par fournisseur et par modèle, consultables via
  `GET /ai/usage`. Ce sont des **faits** : aucun prix n'est inventé. Un **coût
  estimé** n'apparaît **que si vous configurez vos propres tarifs**
  (`ai_prix_usd_par_mtok`) — sinon le suivi n'affiche que des tokens. Le comptage
  est branché de façon défensive (il ne peut jamais casser un appel IA).

- **HUD « Opportunités » dans le LOGBOOK.** Un panneau discret (en bas à droite,
  repliable) remonte directement dans le carnet la **NEED LIST** jusque-là
  réservée à la page CHASSE : les meilleures stations à travailler **maintenant**
  (nouveau pays/ATNO, nouvelle bande, nouveau mode, nouveau carré, confirmation
  LoTW manquante), classées par intérêt — **exactement le même moteur** que
  CHASSE (`/data/spots_ranked`, profil d'objectifs compris), aucun recalcul.
  Nouveauté : chaque opportunité se déplie en **trois couches explicites** —
  **FAIT** (données sourcées : pays·bande·mode), **CALCUL** (la raison + le score
  du moteur déterministe), **PROPOSITION** (un bouton **▶ Appeler**). « Appeler »
  **pré-remplit toujours l'indicatif** dans la saisie du QSO et **règle la radio
  (QSY) uniquement si le CAT est branché** — jamais d'émission, jamais
  d'armement (doctrine « l'IA prépare, l'humain déclenche »). Le corps se replie
  via l'en-tête (masquer ≠ bloquer : le suivi continue en fond).

- **Récap « après-QSO » — voir sa progression à chaque contact.** Juste après
  l'enregistrement d'un QSO, une pastille discrète (non-modale, sous la saisie)
  annonce **ce que ce QSO vient d'apporter** — nouveau pays, nouvelle bande,
  nouveau département — et **ce qui reste à confirmer** (LoTW non confirmé). Elle
  reste **silencieuse sur un doublon** (aucun bruit) et s'efface seule après
  quelques QSO. C'est la boucle de gratification : la même donnée que le panneau
  d'avant-QSO (moteur diplômes via `/call/history`), rejouée **après** coup —
  aucun recalcul, lecture seule, jamais d'écriture au log.

- **Bandeaux défilants (tickers) — l'info live sous la nav.** Sur l'accueil, le
  LOGBOOK et la page CHASSE, de fines bandes défilent avec ce qui compte à
  l'instant : **DX ≤7J** (DXpéditions actives ou annoncées sous 7 jours, avec la
  fréquence du cluster), **PROPAG** (bandes exploitables maintenant, **votre
  bande en cours de saisie mise en tête et marquée**), **SPOTS DX** (meilleurs
  spots du cluster classés par intérêt, optionnel), et **MULTS** (nouveaux
  multiplicateurs à chercher, **uniquement en concours**). Le défilement
  **s'arrête au survol** ; un **clic sur un item actif ouvre une fiche** :
  entité/pays, fréquence·bande·mode du cluster, nom de l'opérateur (recherché
  automatiquement), bouton **▶ QSY** si la radio est pilotée, et lien direct
  **QRZ.com**. Un **⚙** à droite de chaque bande permet d'**afficher/masquer**
  chaque bandeau, choix **retenu par activité**.
- **Adaptation des bandeaux à votre activité** (doctrine « l'axe, c'est
  l'activité »). En VHF/UHF/SHF/satellites, les bandeaux **HF** (DX ≤7J, PROPAG
  déca) **disparaissent** — ils n'ont rien à faire là. Le bandeau **MULTS**
  n'apparaît **que lorsqu'un concours est actif**, quelle que soit la bande (un
  concours VHF reste un concours). Une bande sans rien de vivant à dire ne
  s'affiche pas (pas de bandeau mort), et rien ne gêne jamais la saisie.

- **Carte d'occupation des bandes multi-postes.** Pour un log partagé
  (radioclub, expédition, ou indicatif spécial opéré depuis plusieurs stations),
  un bouton **📻 Occupation** sur le LOGBOOK ouvre un assistant **« Activer un
  log partagé »** (radioclub / expédition / indicatif spécial) qui conseille le
  sync adapté, puis affiche **qui est sur quelle bande/mode** en direct, avec
  **recouvrement surligné en rouge** (deux postes sur la même bande ET le même
  mode). La carte prend automatiquement le canal actif avec **priorité au
  local** : instantané entre postes du même réseau, sinon **Cloud Sync** (dossier
  partagé, réseaux distants) ou **MySQL** (radioclub temps réel). Transport
  **séparé du carnet** — le log n'est jamais touché.

### Modifié

- **Cockpit du LOGBOOK réorganisé.** La barre de statut est regroupée en **blocs
  sémantiques** (concours, propagation, maintenance) séparés visuellement, pour
  retrouver chaque indicateur d'un coup d'œil. Les items sont ordonnés par usage
  plutôt que par hasard historique.
- **Navigation refondue.** Le **cœur** (CONFIG · LOGBOOK · CHASSE · PROPAG) reste
  au premier niveau ; les **outils secondaires** passent dans un menu **« Outils
  ▾ »** (disclosure accessible : bouton `aria-expanded`, panneau `hidden`, Échap
  ferme et rend le focus, clic-dehors). Moins de bruit, l'essentiel toujours à
  portée.
- **Alerte sécurité pylône escaladée et accessible.** L'avertissement
  vent/rafales (« surveille le pylône ») sort du widget météo dans un nœud dédié
  `role="alert"` (annoncé par les lecteurs d'écran), avec clignotement — coupé
  sous `prefers-reduced-motion`. La météo de routine n'est plus assertive.

### Accessibilité

- Champs de saisie en **bordure renforcée** (`--border-strong`) pour un contour
  net et contrasté.
- Tableaux avec en-têtes `scope`, lien courant `aria-current="page"`, langue de
  page (`<html lang>`) alignée sur le contenu, motif **disclosure clavier**
  unifié (Échap + retour focus) pour les menus.

## [1.2-beta1] - 2026-08-26

### Ajouté

- **Copilote FT8 — de la proposition à la semi-automatique tracée.** Sur un
  décode « pour moi », l'IA calcule la réponse standard et la propose dans la
  barre d'émission. Nouveau niveau `copilote_auto` : l'IA émet après un **délai
  réglable** (3/5/8/12 s) **sauf annulation**, avec décompte visible — STOP TX
  ou l'appui sur ÉMETTRE reprennent la main à tout moment ; jamais d'émission
  spontanée hors de ce niveau explicitement choisi. File d'attente pile-up
  (priorité station cliquée > nouveau DXCC > FIFO) avec péremption des stations
  qui ne rappellent plus. **Toute émission copilote est gravée** dans le journal
  d'audit serveur (POST `/tx/trace`, événements `TX_COPILOTE_EMISSION`), de même
  que le lien avec le QSO réellement loggé (`TX_COPILOTE_QSO_LOGGED`) — le tout
  consultable dans un panneau « Journal d'émission » sur la page FT8, même après
  fermeture du navigateur.
- **Copilote CW/SSB.** À l'indicatif résolu (lookup), l'IA prépare l'échange
  en CW comme en phonie — **proposition seule**, jamais de déclenchement
  automatique, cohérent avec le garde-fou d'émission unifié.
- **Aides « départements » pour les concours REF (THF/HF).** Grille
  départements **00-99 en un clic** pour l'échange-département, le département
  saisi primant sur le locator pour le score et les diplômes. Panneau
  **« départements à faire »** sur l'écran contest, trié par **proximité de
  fréquence** (minimise le QSY) ou par **rareté**, avec bascule. Sur le band
  map, les stations de départements non encore faits sont surlignées : un clic
  **QSY sur leur fréquence + pré-remplit le QSO**. Sur la carte des
  départements, ceux qui restent à faire ressortent d'une couleur distincte.
- **Saisie assistée du correspondant.** À la frappe de l'indicatif, le
  **prénom**, le **drapeau** du pays et le **locator** s'affichent
  automatiquement (base interne d'abord, puis internet), tous corrigeables. La
  base interne des prénoms peut être **amorcée depuis le carnet existant**.

### Modifié

- **Heure de fin de QSO automatique.** Le champ manuel « HEURE DE FIN (UTC) »
  disparaît de la saisie : `time_off` est renseigné automatiquement à
  l'enregistrement (= heure du QSO). La donnée reste exportée en ADIF
  (`TIME_OFF`) et l'édition d'un QSO importé préserve sa valeur — seule la
  frappe manuelle disparaît.
- **Autonomie « zone blanche » renforcée.** Leaflet et Chart.js sont désormais
  **embarqués localement** (plus aucune dépendance CDN externe) et précachés par
  le service worker : cartographie et graphiques chargent et fonctionnent **sans
  connexion Internet** (DXpédition, /P, réseau bloquant les CDN), au lieu de
  pages inertes.

### Corrigé

- **Panneau « départements à faire » aveugle aux indicatifs jamais loggés.**
  `department_targets()` ignorait un chasseur jamais loggué apparaissant sur un
  département manquant, rendant le panneau structurellement incomplet. La
  résolution du département d'un spot est désormais unifiée : historique →
  locator local → repli réseau.

## [1.1-beta8] - 2026-08-24

### Ajouté

- **Page d'accueil par activité.** Nouvelle page `logx_accueil.html`, devenue
  la porte d'entrée de l'app (routage racine `/`) : une grille de tuiles
  (LOG normal, LOG 6m, LOG V/UHF, LOG SHF, LOG Satellites, LOG Concours, LOG
  DXp, LOG Call spéciaux, LOG IOTA/POTA, LOG QRP) remplace le mode
  simple/expert comme axe premier de l'interface — décision de F4GLD du
  19/08/2026 suite à un échange avec un correspondant expérimenté (Didier) :
  « pas besoin de mode débutant et expert... un logiciel comme une super
  boîte à outils où on rentre très facilement dedans ». Un clic pose
  `localStorage.logx_activity` puis redirige (CONFIG si aucun concours actif,
  LOGBOOK sinon) ; les visites suivantes sautent directement la grille —
  résumé en un geste, sans ralentir l'habitué. Le lien « ↺ ACTIVITÉ » dans
  CONFIG (`?changer=1`) permet de revenir sur ce choix à tout moment :
  masquer n'est jamais bloquer. Seule **LOG V/UHF** obtient un vrai filtrage
  à ce stade (doctrine : valider le modèle sur UNE activité avant les 18
  autres pages) — les autres tuiles routent honnêtement vers le comportement
  actuel de l'app, sans filtre supplémentaire ni promesse non tenue.
- **LOG V/UHF filtre réellement les concours et les bandes.** La grille de
  concours de CONFIG (vue « à venir ») ne propose plus, en activité V/UHF,
  que les concours dont le règlement est positivement connu comme tenant
  entièrement dans les bandes VHF/UHF (`_contestCompatibleVuhf()`) — un
  concours à l'axe libre (CUSTOM, POTA/SOTA « au choix »...) est écarté
  plutôt que deviné compatible, conformément à la règle du dépôt de ne
  jamais fabriquer une valeur de domaine. L'échappatoire « Voir tous les
  concours » reste toujours accessible, jamais filtrée. Hors concours (QSO
  occasionnel), le sélecteur de bandes du LOGBOOK propose par défaut
  144/432/1296 MHz plutôt que la totalité des bandes HF+V/UHF — « 2m, 70cm,
  23cm, et ça suffit » (F4GLD, 22/08/2026).
- **Score masqué par défaut hors concours, affiché sur demande.** Nouveau
  bouton SCORE dans l'en-tête du LOGBOOK : hors concours actif, le bandeau
  de score (QSO, meilleur DX, rythme, temps restant...) reste masqué par
  défaut pour épurer l'écran, et ne s'affiche que sur demande explicite —
  retour F4GLD du 22/08/2026 (« afin d'épurer au maximum les pages tout ce
  qui est scoring doit apparaître uniquement sur demande »). Étend le
  mécanisme déjà existant pour les modes simple/expedition
  (`bandeauxRythmeMasques()`) plutôt que d'en inventer un second ; un
  concours réellement actif continue d'afficher le score sans qu'on ait
  besoin de le demander — aucun changement pour l'usage contest classique.
- **Lien profond PROPAG depuis le LOGBOOK.** Le lien PROPAG de la barre de
  navigation du LOGBOOK ouvre désormais directement `logx_propagation.html`
  sur la bande actuellement journalisée (`?band=...#propPane-focus`), au
  lieu du dernier onglet consulté — évite un aller-retour pour retrouver la
  bonne bande en pleine activité.
- **FT8 : mode « Automatique » (CQ + QSO en totale autonomie), strictement
  optionnel.** Nouveau 4e niveau dans le sélecteur du séquenceur FT8, en
  plus de manuel/assisté/séquenceur : une fois activé par le menu ET un
  bouton dédié (double geste explicite, jamais un simple choix de menu), la
  station appelle CQ, décode les réponses, déroule l'échange complet
  (grille/report/RRR/73), logue, puis relance CQ — en boucle, sans reclic à
  chaque étape. Demandé par F4GLD le 22/08/2026 pour une activation à
  indicatif spécial (TM6KJS), en dérogation explicite et assumée à la règle
  de sécurité par défaut du séquenceur (« aucune émission automatique sans
  confirmation humaine ») — dérogation qui NE s'applique QU'à ce mode
  optionnel ; les 3 modes existants n'ont pas changé de comportement. Le
  bouton STOP SÉQUENCE et la touche Échap arrêtent tout immédiatement, à
  tout moment du cycle (y compris pendant l'attente entre deux CQ) ; un
  bandeau d'avertissement reste affiché en permanence tant que le mode est
  actif — pas une bulle au survol.
- **FT8 : panneau « QSO en cours » séparé de l'activité de bande.** Nouveau
  panneau dédié à l'échange en cours (grille/report/RRR/73 reçus et émis),
  distinct du tableau existant qui liste toute l'activité décodée sur la
  bande — demandé par F4GLD pour distinguer d'un coup d'œil « ce qui se
  passe sur la bande » de « mon QSO ».

### Corrigé

- **Le sélecteur de bandes du LOGBOOK ignorait les vrais concours V/UHF.**
  `renderBandButtons()` indexait une table locale (`CONTEST_BANDS`) qui ne
  connaissait que des clés génériques (`REF_CCD`, `REF_IARU_VHF`...) —
  aucune des vraies clés d'édition utilisées partout ailleurs dans l'app
  (`REF_CCD_JAN1`, `REF_MARCONI`, `REF_DDFM_50`, `REF_IARU_50`...). Le
  sélecteur retombait donc sur la totalité des bandes (HF comprises) pour la
  quasi-totalité des concours V/UHF réels — trouvé en construisant le
  narrowing LOG V/UHF, pas signalé par un utilisateur. Corrigé en extrayant
  le résolveur déjà correct côté CONFIG (`_resolveContestFilters()`,
  `LEGACY_CONTEST_FILTERS`, `BAND_TOGGLE_KEY`, `MODE_TOGGLE_KEY`) vers un
  nouveau fichier partagé `logx_contest_rules.js`, chargé par les deux pages
  — corrige tous les concours concernés, pas seulement ceux de l'activité
  V/UHF.

## [1.1-beta7] - 2026-08-21

### Ajouté

- **Upload QSL vers Cloudlog/Wavelog.** Nouveau service d'upload dans
  `logx_qsl.py`, au même niveau qu'eQSL/ClubLog/QRZCQ/HRDLog (URL de
  l'instance + clé API + ID de profil station dans CONFIG, bouton dans la
  popup Diplômes du LOGBOOK). Contrat d'API (`POST /index.php/api/qso`)
  vérifié directement dans le code source des deux projets — leur doc ne
  précise pas le format de réponse, qui diffère d'ailleurs entre forks
  (`imported_count` chez Cloudlog, `adif_count` chez Wavelog, les deux lus).
- **Détection automatique du ton CW à l'écoute.** Un bouton 🔍 Détecter, à
  côté du champ « Ton CW à l'écoute » (radio 1 et radio 2 SO2R), écoute
  quelques secondes une station en train de transmettre et règle le champ
  tout seul — plus besoin de connaître le réglage CW Pitch de son poste.
  Écoute plusieurs fréquences candidates en parallèle et ne retient que
  celle qui produit du VRAI Morse décodable (pas seulement un rythme
  ON/OFF plausible, qu'un simple ronflement grave peut imiter) ET à une
  vitesse humainement plausible (≤ 45 MPM) — un bruit haché en impulsions
  courtes se décode presque toujours en caractères "valides" au sens
  strict du code Morse (1 à 3 symboles = toujours une lettre existante),
  d'où ce second filtre, ajouté après l'avoir vu se faire piéger en
  direct sur un vrai poste avant la sortie de cette beta.
- **PTT par ligne série (RTS/DTR).** Beaucoup de postes derrière un boîtier
  d'interface (ex. XGGComms Digimode-4) n'activent l'entrée audio de leur
  prise DATA que si le PTT matériel est actionné — piloté par la seule
  commande CAT, un tel poste passe en émission et ne sort aucune
  puissance, en silence. `cat_ptt_method` (`cat`/`rts`/`dtr`) dans
  CONFIG → RADIO ; le PTT matériel n'exige pas un CAT actif, ce qui permet
  de continuer à émettre même quand le câble CAT lui-même ne fonctionne
  pas. Message « Aucune radio détectée » amélioré au passage : nomme
  enfin les ports série réellement présents au lieu de renvoyer vérifier
  vaguement « le câble/port ».
- **Lien de soutien (don HelloAsso).** Un lien 💛 soutenir dans la barre de
  statut partagée (les 15 pages de l'app) et un widget de don sur le
  [site vitrine](https://sauveteur71.github.io/LogX_AI/) — don libre au
  Radio-Club du Velay (F6KQJ), entièrement facultatif, aucune
  fonctionnalité n'en dépend.

### Corrigé

- **10 constats de l'audit du 18-19/08/2026 (A01-A10), traités un par un** —
  détail complet dans `docs/FEUILLE_DE_ROUTE.md`. Les plus significatifs :
  le score déclaré (export Cabrillo, archivage, affichage live) n'appliquait
  le multiplicateur sur AUCUN de ses 6 chemins d'exposition (A10) ; `/log/list`
  n'exigeait aucune authentification et 6 CDN externes chargeaient sans
  intégrité SRI (A09) ; le miroir JS des barèmes de score ne gérait pas les
  règles `when` en liste et ignorait des prédicats connus, cassant
  l'affichage en direct sur le concours REF phare (A05) ; 10 noms de
  concours Cabrillo non conformes, sourcés et corrigés (A04). Les autres
  constats (A01, A02, A03, A06) se sont révélés déjà corrigés ou non
  reproductibles à la vérification — documenté avec preuve plutôt que
  simplement refermé.
- **Panneau réglages FT8 qui se rouvrait de force.** Le panneau « Réglages à
  faire sur ton poste » se réaffichait ouvert à CHAQUE visite de la page
  FT8, même après une fermeture manuelle une fois les réglages appliqués.
  Mémorise désormais la fermeture par poste précis (marque+modèle) — un
  changement de radio redonne une bonne raison de le revoir.
- **Liste des périphériques audio du keyer vocal, dédupliquée.** PortAudio
  interroge Windows via jusqu'à 4 sous-systèmes distincts (MME/
  DirectSound/WASAPI/WDM-KS) : chaque périphérique apparaissait donc
  jusqu'à 4 fois dans le sélecteur CONFIG, noyant l'interface USB radio au
  milieu d'une vingtaine d'entrées pour moitié identiques.
- Balayage cohérence documentaire : 2 chiffres périmés oubliés dans les
  documents de promotion.

## [1.1-beta6] - 2026-08-21

### Ajouté

- **FT8 — afficher les réglages à adopter sur LE poste déclaré.** Le panneau de
  conseils restait générique et replié, sans savoir quelle radio l'opérateur
  avait déclarée en CONFIG. Il s'ouvre désormais au chargement, se titre du
  poste choisi, et donne les chemins de menu exacts pour dix modèles
  (IC-7300, IC-705, IC-9700, IC-7610, FT-991A, FT-991, FT-891, TS-590S,
  TS-590SG, TS-890S) — chaque ligne sourcée et citée depuis les manuels
  officiels, jamais écrite de mémoire. Un modèle non documenté ne reçoit que
  le socle universel, avec la mention explicite qu'aucune source propre n'a
  été trouvée. Corrige au passage une consigne erronée reprise du panneau :
  l'« ALC à zéro » attribué à WSJT-X ne figure dans aucun des deux manuels —
  le critère retenu est de descendre jusqu'à ce que la puissance HF commence
  tout juste à baisser, qui reste valable aussi en VOX.
- **FT8 — un curseur NIVEAU TX, parce que la consigne était inapplicable.** La
  page demande, en gras, de régler la puissance par le niveau audio et de
  garder **l'ALC à zéro**. Or ce niveau était figé à 90 % de la pleine échelle,
  sans aucun réglage : restaient le mixeur Windows ou le gain d'entrée du
  poste. Le curseur va de 5 à 100 % et se retient d'une session à l'autre.
  Deux choix assumés : **90 % par défaut**, soit exactement ce qui partait
  jusqu'ici — mettre à jour ne change rien sur l'air tant qu'on ne touche pas
  au curseur ; et **plancher à 5 %, jamais 0** — un niveau nul émettrait un
  silence en affichant « émission en cours », et on appellerait dans le vide
  sans le savoir. Le bon réglage reste celui de VOTRE station : on descend
  jusqu'à ce que l'ALC du poste ne bouge plus du tout.
  L'affichage donne aussi **l'équivalent en décibels** (« 40 % · −8,0 dB »),
  parce que l'échelle est trompeuse sans lui : de 100 à 50 % il n'y a que 6 dB,
  mais de 10 à 5 % il y en a 6 aussi. Toute la finesse utile est en bas de
  course, d'où un pas de 1 %.
  **Si votre poste passe en émission par le VOX** (sans pilotage CAT), le
  niveau n'est plus seulement la modulation : c'est ce qui DÉCLENCHE
  l'émission. Trop bas, le poste ne se déclenche plus — et le critère « l'ALC
  ne bouge plus » ne permet pas de distinguer ce cas d'un réglage propre.
  L'infobulle et le message d'émission le disent maintenant : vérifiez que le
  voyant d'émission du poste s'allume encore.
- **LOGBOOK — noter un QSO fait sur un poste que le PC ne commande pas.** En
  FT8 piloté par CAT sur une radio, noter à la main un QSO CW/phonie fait sur
  un second poste non connecté déplaçait la radio pilotée : sélectionner la
  bande/mode du second poste lui envoyait un QSY, et le sondage CAT ramenait
  ensuite bande/mode/fréquence sur ceux du poste piloté. Un bouton SOURCE DU
  QSO (RADIO PILOTÉE / AUTRE POSTE) sous le sélecteur de mode découple les
  deux — masqué sans CAT, l'état survit au rechargement. Le logiciel ne
  bloque ni ne protège le second poste : la règle « une seule porteuse »
  reste à la charge de l'opérateur.

### Corrigé

- **« NOUVEAU LOG » annonçait le nombre de QSO AFFICHÉS, pas celui du carnet.**
  Filtré sur un concours à 50 QSO, le dialogue écrivait « Supprime 50 QSO »
  alors que le carnet entier — 9 870 QSO sur la station de F4GLD — était
  archivé puis vidé. Rien n'était perdu, l'archivage précède l'effacement,
  mais c'est ce chiffre-là que l'on lit pour décider. Le dialogue affiche
  désormais le total réel et **dit l'écart** quand un filtre est actif. Si le
  serveur ne répond pas, il n'affiche pas le compte de la vue — ce serait
  reproduire le défaut au pire moment — il écrit « TOUS les QSO ».

- **La protection de puissance en numérique ne s'appliquait pas là où on
  émet.** Le réglage « puissance TX automatique par mode » (CONFIG > RADIO,
  décoché par défaut) sert à protéger le final : un mode numérique émet à
  100 % du cycle de service quand la phonie et la CW n'y sont pas. Mais il
  n'était poussé vers la radio **que** par le sélecteur de bande/mode du
  LOGBOOK. Si vous ouvrez MODE NUMÉRIQUE → FT8 directement — le chemin
  naturel — votre poste restait sur son réglage phonie, et chaque créneau
  partait à cette puissance-là pendant 12,6 s en porteuse continue. Exactement
  ce que le réglage existe pour éviter, pendant que la page vous présentait le
  curseur NIVEAU TX comme le réglage de puissance du mode. La protection est
  maintenant appliquée aussi sur la page FT8, au moment où vous activez
  l'émission.
  **Et surtout, elle DIT ce qui s'est passé.** L'ancien code partait en
  « envoie et oublie » : un refus était strictement invisible. Or le refus est
  le cas le plus courant — le réglage de puissance n'est pas disponible en
  CI-V (Icom/Xiegu), parce que la commande CI-V règle un niveau relatif et non
  des watts, et il exige le pilotage natif. La page affiche désormais l'un des
  trois : la puissance appliquée, « radio non pilotée, règle-la à la main », ou
  le motif exact du refus. Un opérateur d'IC-7300 sait donc qu'il doit régler
  son poste lui-même, au lieu de croire son final protégé.
- **Un QSO sans identifiant était impossible à supprimer.** Une entrée du
  carnet réel de F4GLD sans `id` (ADIF mal formé, import partiel — pas un cas
  d'école) ne pouvait être visée par aucun chemin de suppression ou
  d'édition : aucun moyen de l'effacer depuis le logiciel. Tout QSO sans
  identifiant en reçoit désormais un au chargement, calé au-dessus du plus
  grand déjà pris, sur les deux chemins de chargement (base SQLite et
  migration JSON).
- **VOACAP échouait EN SILENCE si LogX AI est installé trop profond.** Au-delà
  de **128 caractères** de chemin, `voacapl.exe` rend une erreur vide et toute
  la propagation s'arrête, avec un message qui n'explique rien. Un OneDrive
  redirigé, un dossier Documents, un nom d'utilisateur long suffisaient. Le
  seuil est mesuré (128 passe, 129 échoue) ; le logiciel raccourcit désormais
  le chemin tout seul — le plus souvent sans déplacer un seul fichier — et,
  s'il échoue quand même, il **dit** que le chemin est trop long.
- **FT8 — émettre en VOX quand aucune radio n'est pilotée.** Sans CAT, la page
  ne fabriquait aucune forme d'onde : elle conseillait pourtant « passe en
  émission au micro ou en VOX », un conseil impossible à suivre. Le son part
  maintenant dans la carte son et c'est le VOX du poste qui déclenche
  l'émission. **Ce qu'il faut savoir** : sans CAT, le logiciel ne peut plus
  faire taire la radio par une commande — c'est **couper le son** qui arrête
  l'émission, donc le bouton STOP et Échap. Ils restent visibles et actifs
  pendant toute l'émission, et le chien de garde aussi.
- **Sécurité d'émission — Échap pouvait libérer le verrou du séquenceur FT8.**
  Échap est le coupe-circuit CW ; il envoie un arrêt dès qu'un manipulateur
  existe. Or cet arrêt levait le verrou d'exclusivité d'émission **sans
  regarder qui le détenait** : pendant que le FT8 émettait, un Échap réflexe
  pour fermer une popup rouvrait la porte à une émission de la seconde radio.
  Deux porteuses en même temps. Le verrou retient maintenant qui l'a pris, et
  un arrêt CW ne lève plus qu'un verrou CW — le coupe-circuit, lui, reste
  entier.
- **FT8 — le décodage quitte le fil principal.** Il y tournait en entier :
  l'interface gelait pendant tout le décodage d'un créneau, et la réponse ne
  pouvait pas partir dans le créneau suivant — elle laissait passer un tour.
  Le décodage part maintenant dans un Web Worker (`logx_ft8_worker.js`, le
  premier du dépôt). Mesuré en navigateur sur la machine de F4GLD : blocage du
  fil principal **1 942 ms → 12 ms**, durée du décodage inchangée (2 023 →
  2 021 ms — le travail n'a pas été réduit, il a été déplacé), et 51 → 244
  battements d'horloge pendant le décodage. Les 3 messages décodés sont
  identiques avant et après. Si `new Worker` échoue (fichier absent, contexte
  restreint), la page retombe sur le décodage en ligne : le mode dégradé reste
  le comportement d'avant, jamais une panne. Corrige le point « Le décodage
  bloque le fil principal ~2,1 s par créneau » listé en connu/non corrigé
  ci-dessous.
- **FT8 — deux stations à moins de 50 Hz : la seconde n'était jamais
  décodée.** Le décodeur écartait tout candidat situé à moins de 50 Hz d'un
  candidat déjà retenu ; toute station proche d'une autre disparaissait, sans
  message ni indice. La limite passe à **~19 Hz**. Ce n'est PAS la suppression
  de la règle : mesuré, la retirer ferait tomber une bande à 28 stations de
  28/28 à 14/28, parce qu'elle sert en réalité à effondrer les détections
  multiples d'un même signal fort. Seule sa largeur était en cause (18,75 Hz,
  soit 3 espacements de tons, est la seule valeur qui recouvre les stations
  proches sans dégrader la bande chargée), avec le budget de candidats porté
  de 30 à 60 pour compenser. Le report SNR est inchangé, vérifié par la
  mesure et non supposé. **Ce qui reste** : sous ~19 Hz d'écart la seconde
  station est toujours perdue — la limite est déplacée, pas supprimée. Dit
  tel quel dans le guide utilisateur.
- **FT8 — « Ignorer » perdait la fiche du correspondant**, et le bouton STOP
  du séquenceur n'était retenu par aucun test malgré son rôle de sécurité
  d'émission.
- **Barre de statut — la sauvegarde affichée était celle du navigateur**, pas
  celle réellement écrite sur le disque : l'indicateur pouvait annoncer une
  sauvegarde à jour alors que rien n'était écrit. `/log/status` remonte
  désormais l'horodatage du fichier de sauvegarde lui-même.

### Documentation

- **PASSATION : les 5 constats FT8 donnés pour « restants » ne l'étaient
  pas.** Vérification faite un par un, le document est corrigé.

## [1.1-beta5] - 2026-08-19

Deux chantiers dans cette version, dont un qui n'était pas prévu.

**Le carnet.** Le 19/08/2026, l'auteur du logiciel a perdu son carnet complet —
9 871 QSO de 2011 à 2026 — en redémarrant. Il n'a été récupéré que parce que le
fichier ADIF d'origine existait encore. **La cause racine n'a jamais été
identifiée** : remise à zéro, vidage par archivage, les quatre chemins de
synchronisation et la suite de tests ont tous été éliminés par la mesure. Les
protections ci-dessous ferment donc le goulot par lequel TOUTE destruction
passe, au lieu de condamner une porte supposée.

**Le FT8 natif**, à partir d'essais en trafic réel sur 20 m. Chaque correctif
vient d'un constat fait à la station, pas d'une revue de code.

### Sécurité — protection du carnet

- **La sauvegarde automatique tourne dès le premier lancement, sans réglage.**
  Avant, le champ « dossier de sauvegarde » était vide à l'installation et
  **rien n'était jamais écrit** — c'est précisément ce qui a rendu la perte
  irréversible. Sans dossier choisi, les copies horodatées vont dans un
  sous-dossier `sauvegardes/` à côté du carnet. Le champ de CONFIG ne sert donc
  plus à *activer* la sauvegarde mais à la **déplacer**, idéalement vers un
  dossier synchronisé (Synology Drive, Dropbox, OneDrive) ou une clé USB. Ce
  repli est sur le même disque que le carnet : il protège d'un carnet vidé,
  **pas** d'un disque perdu.
- **Refus d'écriture destructrice.** Si une opération s'apprête à faire
  disparaître un grand nombre de QSO sans que l'opérateur l'ait demandé,
  l'écriture est refusée et la base reste intacte. Les remises à zéro
  explicitement demandées (« vider le log », « archiver et vider ») continuent
  de fonctionner normalement.
- **Journal d'appoint.** Quand l'enregistrement est suspendu, les QSO suivants
  sont mis de côté dans un fichier ajout-seul poussé sur le support (`fsync`),
  rejoué automatiquement au démarrage suivant. Sans lui, le garde-fou
  ci-dessus serait devenu un second sinistre : l'opérateur aurait continué à
  logguer dans le vide.
- **Verrou du dossier de données.** Deux LogX AI travaillant dans le même
  dossier partagent le même carnet et finissent par s'effacer mutuellement ; la
  seconde instance refuse désormais de démarrer et dit pourquoi. Verrou système
  sur le dossier, pas un simple fichier `.pid`.
- **Bandeau rouge permanent** sur les 15 pages tant que l'enregistrement est
  suspendu : un blocage de persistance ne doit jamais être silencieux.

### Ajouté

- **Séquenceur FT8** : le QSO s'enchaîne et se loggue seul (appel, report, RRR,
  73), avec relances tant que la station n'a pas répondu. **Le mode « manuel »
  reste le défaut, y compris après mise à jour** : personne ne se retrouve avec
  une émission automatique sans l'avoir demandée. Cinq chemins d'arrêt (STOP,
  Échap, désarmement, arrêt d'écoute, changement de mode) et deux abandons
  automatiques (plafond de relances, la station répond à un tiers).
- **Colonne SNR en dB** à la place de l'ancien « Score ». C'est un RAPPORT,
  donc insensible au gain de la carte son — l'ancienne colonne affichait 0 sur
  la totalité des décodages chez F4GLD. Le décodeur ne produisait auparavant
  aucune estimation de rapport signal/bruit : le séquenceur envoyait donc le
  même report à toutes les stations. Constante de calibration MESURÉE
  (biais 0,13 dB, pire écart 0,74 dB sur la plage réelle du FT8) ; recoupée
  après coup avec le code de WSJT-X, qui utilise -27,0 dB là où la mesure
  donne -27,83.
- **Avertissement de propreté du signal** : un ton d'émission sous 1500 Hz voit
  son harmonique 2 tomber dans la passe-bande et partir sur l'air comme
  parasite. L'avis chiffre la fréquence exacte du parasite pour le ton choisi.
- **Décalage de VFO à l'émission** (équivalent du « Fake It » de WSJT-X),
  DÉSACTIVÉ PAR DÉFAUT : décale la fréquence pendant l'émission pour que le ton
  reste entre 1500 et 2000 Hz, et la restaure ensuite. La fréquence réellement
  émise ne change pas. Nécessite le CAT. **Pas encore éprouvé sur l'air.**

### Corrigé

- **Le panneau ÉMISSION n'exige plus de scroller.** La liste des décodages
  n'avait aucune borne de HAUTEUR : à chaque cycle de 15 s, tout ce qui se
  trouvait dessous descendait. La liste défile désormais dans son cadre, et le
  panneau Émission est passé EN TÊTE de colonne. Mesuré : défilement de page
  ~2400 px -> 0 sur le chemin critique.
- **Plus d'émission dans le créneau de la station appelée.** L'émission était
  programmée sur « le prochain créneau, quel qu'il soit » : répondre sans
  tarder tombait juste par hasard, une seconde de retard faisait émettre
  par-dessus le correspondant — aucun des deux n'entendait l'autre, et rien ne
  l'expliquait. La parité se déduit désormais du créneau où la station a été
  entendue, sans réglage à faire. L'écran dit quand un tour est passé.
- **Une seule page FT8 à la fois.** Deux pages, ce sont deux décodeurs sur la
  même carte son et deux commandes de PTT sur la même radio. Le hub revient
  désormais sur la page ouverte au lieu de la recharger (le décodeur repartait
  de zéro et la session était perdue), et une seconde page refuse de démarrer.
- **L'intro de la page FT8 n'est plus bridée à 900 px** : sur une fenêtre de
  1900 px elle s'entassait sur 7 lignes dans la moitié gauche et poussait tout
  le reste de 60 px. FT8 était l'exception — CW, RTTY et SSTV n'ont aucune
  limite.

- **Le même QSO FT8 pouvait être loggué deux fois** (constaté sur CT1END/P
  dans le carnet de F4GLD). Une fiche déjà écrite pour un indicatif sur une
  bande donnée n'est plus réécrite dans la fenêtre qui suit, et les
  informations des deux passages sont fusionnées au lieu de s'écraser.
- **25 concours proposés dans l'interface ne rendaient aucune bande.** Les
  douze Concours de Courte Durée mensuels, le Challenge THF, le Trophée F8TD,
  le Mémorial Marconi, les IARU VHF/UHF/50 MHz, le DDFM 50 et les quatre TVA
  étaient sélectionnables mais n'avaient aucune définition côté serveur :
  détection HF/V-UHF muette, filtrage de spots sans contrainte de bande,
  validation sans bande autorisée, et « BANDES : ? » dans le contexte envoyé à
  l'IA — le tout **en silence**. Quinze d'entre eux retrouvent leurs bandes,
  déduites du barème qui les portait déjà en clair. Les dix autres, dont le
  barème est une plage (« 144MHz-47GHz ») ou un mot (« HF », « 438MHz+ TVA »),
  restent volontairement sans bandes : les développer supposerait de décider
  quelles bandes en font partie.

### Documentation

- **Le guide utilisateur ignorait le FT8 natif** : sur 1458 lignes, il ne
  connaissait le FT8 que comme un pont vers WSJT-X. Le §8.6 devient « Modes
  numériques natifs : FT8, RTTY, SSTV — sans logiciel tiers », avec les trois
  modes d'envoi, les cinq façons d'arrêter le séquenceur et l'avertissement
  qu'il émet sans intervention.
- **Le chapitre 2 décrit la sauvegarde telle qu'elle est**, y compris ce
  qu'elle ne protège pas.

### Connu, non corrigé

- **Le décodage bloque le fil principal ~2,1 s par créneau** sur la machine de
  F4GLD (mesuré et affiché dans le diagnostic). Conséquence directe : la
  réponse ne peut pas partir dans le créneau qui suit immédiatement le
  décodage, et laisse passer un tour. Seul le passage du décodage dans un
  Web Worker le supprime — chantier à part, à éprouver sur machine réelle.
- **Deux stations séparées de moins de 50 Hz** : la seconde n'est pas décodée.

## [1.1-beta4] - 2026-08-15

### Ajouté

- **CAT natif — alignement avec Hamlib 4.7.2** (pris comme référence) : flag
  DATA CI-V (Icom/Xiegu) armé automatiquement en mode numérique, manipulation
  CW Kenwood/Elecraft pilotée par interrogation active du tampon radio (au
  lieu d'un délai fixe pouvant déborder à vitesse concours), connexion
  Kenwood/Elecraft plus robuste aux trames spontanées (AI0), lecture du mode
  Yaesu par requête dédiée plutôt que par une position fragile dans la trame
  IF, et prise en charge de l'IC-905 au-dessus de 5,85 GHz.
- **rigctld (Hamlib)** : connexion TCP persistante et reconnexion
  automatique et transparente en cas de coupure, au lieu de rouvrir une
  connexion à chaque commande.
- **CARTE IA** : dictée vocale disponible aussi pour poser une question au
  chat (déjà présente pour le champ indicatif).
- **CONFIG, section 5. RADIO (CAT)** : propose directement les postes déjà
  déclarés dans le parc RADIOS au lieu de ressaisir marque/modèle.
- **Bandeau de rapport de bug automatique** : une requête IA qui échoue
  déclenche désormais une proposition de rapport pré-rempli, sans action de
  l'utilisateur.

## [1.1-beta3] - 2026-08-15

### Ajouté

- **CONFIG, sélection du concours** : vue "concours à venir" par défaut
  (quelques concours triés par date avec compte à rebours) au lieu de la
  grille complète des 330+ concours REF/international/WA7BNM/perso, jugée
  trop encombrante — la grille complète reste accessible en un clic ou via
  la recherche. Le concours déjà configuré reste toujours visible même hors
  de cette fenêtre.
- **CONFIG, amplificateur** : PowerGenius XL et ACOM sont désormais des
  marques du sélecteur unique "6. Amplificateur" (au lieu de catégories
  séparées) — un seul endroit pour tout piloter, quelle que soit la marque.
- **Parc RADIOS** : plusieurs postes radio en inventaire, associables aux
  antennes du parc, sur le même principe que les rotors/amplis existants.
- **Puissance TX automatique par mode** en émission numérique (FT8/FT4/RTTY),
  protection de l'étage final contre un excès de puissance en cycle continu.
- **Fenêtre détachée SSTV** (réception + émission), sur le modèle des
  fenêtres RTTY/FT8 déjà détachables.
- Définition du concours **IARU HF World Championship** (manquante jusque-là).

### Corrigé

- **CAT bidirectionnel** : un changement de bande/mode fait directement sur
  la radio (IC-7300 notamment) ne se répercutait pas dans LOGBOOK.
- Port série signalé « déjà utilisé » même après redémarrage du serveur.
- Décodeur CW peu fiable à vitesse concours (>22 MPM) + nouvel outil de test
  du périphérique audio pour bien choisir sa source.
- Waterfall FT8 qui se figeait après un certain temps + clic sur le
  waterfall pour caler directement le ton d'émission.
- 6 bugs de scoring trouvés par un audit de conformité aux règlements
  officiels (REF Coupe du REF, multiplicateurs par bande, WAE, ARRL DX
  KH6/KL7, NA W/VE).
- 4 bugs CAT Yaesu trouvés par un audit croisé avec les manuels officiels
  FT-991/FT-991A (trame IF, commande MD, split, table d'identification).
- 3 bugs ADIF/Cabrillo (catégorie bande micro-ondes, catégorie mode FM,
  version ADIF) trouvés par le même audit de conformité.
- 2 bugs VOACAP/propagation (format de l'indice K NOAA, seuils SNR requis).
- POTA : le seuil de 10 QSO doit être atteint en un seul jour UTC (les
  QSO répartis sur plusieurs jours ne comptaient pas correctement).
- Diplôme WAS : le District de Columbia crédite désormais le Maryland,
  conformément au règlement ARRL.
- Table de code RTTY FIGS (USTTY vs ITA2, 3 erreurs de transposition).
- i18n : environ 1000 clés de traduction manquantes rattrapées sur les 18
  pages du logiciel (audit statique + fichiers JS générés dynamiquement).
- 8 retours d'usage terrain F4GLD sur CONFIG/LOGBOOK (détails divers).

## [1.1-beta2] - 2026-08-13

### Corrigé

- **i18n : fragments de phrase français résiduels** au milieu du texte
  traduit, sur les pages MODE NUMÉRIQUE/CW (trouvé par F4GLD en testant la
  1.1-beta1 en allemand). Cause : une phrase française contenant un lien ou
  un mot en gras en plein milieu se scinde en plusieurs nœuds de texte côté
  moteur i18n — les liens se traduisent (déjà connus), mais les fragments de
  prose autour d'eux avaient été filtrés à tort comme "hors scope" par
  l'audit précédent.

## [1.1-beta1] - 2026-08-13

Première bêta post-1.0 : refonte majeure de CARTE IA et interface enfin
traduite en profondeur dans les 7 langues. Aucune rupture de format
(ADIF/Cabrillo/réseau multi-poste inchangés).

### Ajouté

- **CARTE IA, refonte multi-phase** : paliers de coût IA Basique (0 jeton,
  réponses déterministes)/Intermédiaire/Expert avec BILAN diplômes et
  DÉBRIEF disponibles en palier Basique ; fenêtres VOACAP ciblées sur les
  DXpéditions annoncées ; backlog complet (pile-up/split, coordination
  radioclub, mémoire inter-concours, saisie vocale, repli de mode) ; carte
  **détachable sur un second écran** (`?panel=map`, parité fonctionnelle
  totale) ; menu **PLUS** regroupant les actions secondaires pour laisser
  la place au texte du chat ; **chat persistant** entre changements
  d'onglet ; **annulation d'une analyse en cours par la touche Échap** ;
  sélecteurs NIVEAU (ton des réponses) et PALIER IA (coût) rendus
  explicites (étiquettes visibles, infobulles, confirmation par toast).
- **CHASSE/DXpéditions** : distinction pays jamais travaillé / partiellement
  travaillé / toutes bandes confirmées.
- **CALENDRIER** : nouveau panneau pour le bulletin hebdomadaire du REF.
- **Lien GUIDE** (wiki) contextuel par écran, dans la barre de statut.
- **Interface traduite en profondeur** : 414 chaînes d'interface jamais
  traduites ajoutées dans les 7 langues (panneaux avancés de CARTE IA/
  LOGBOOK/MOBILE — QTC, filtre avancé, recherche de doublons, contrôle de
  net, keyer vocal, callbot, décodeurs CW/SSTV, carte QSL, checklist,
  diplômes...), puis revue qualité par 7 relecteurs natifs indépendants
  (29 corrections de sens, de registre et de cohérence terminologique).
- Dépôt renommé en `LogX_AI` (toutes les références mises à jour).

### Corrigé

- **Vérification approfondie pré-bêta** : 37 correctifs (4 critiques, 21
  modérés, 12 mineurs), dont un bug réel de score CQ WPX qui ne doublait
  jamais les points sur les bandes basses (80/40/160 m), une injection
  Cabrillo via le champ bande non assaini à l'import ADIF, et un bouton
  STOP SO2R qui routait vers la mauvaise radio.
- **Deux audits d'intuitivité complets** : 12 correctifs critiques puis 54
  correctifs modérés/mineurs (perte de contexte de fenêtres détachées,
  filtres inopérants selon l'onglet, échecs réseau silencieux...).
- Version affichée par `LANCER_LOGX_AI.bat` (codée en dur, désynchronisée
  de la version réelle).

## [1.0] - 2026-08-12

Première version stable de LogX AI. Le format ADIF/Cabrillo, le moteur de
scoring et le protocole réseau multi-poste restent inchangés — ce numéro
marque la maturité du logiciel, pas une rupture de compatibilité.

### Ajouté

- **Designer de carte QSL imprimable** (export PNG/JPG) : dernière brique
  concurrentielle manquante face aux loggers établis.
- **VOACAP point-à-point** : vrai moteur de prévision NTIA/ITS (`voacapl`
  natif embarqué), intégré à LOGBOOK et CARTE IA — plus une estimation
  approximative.
- **Barre de statut personnalisable** (survol, popup de mise à jour, menu
  AFFICHAGE à cocher) et feedback immédiat dans l'École CW.
- **Score à battre par concours** + import d'anciens logs ADIF/Cabrillo,
  avec détection automatique du concours et du format à l'import.
- **Onglet MODE NUMÉRIQUE** : FT8 et RTTY s'ouvrent chacun dans leur propre
  fenêtre détachable (déplaçable sur un second écran), remplaçant l'ancien
  panneau FT8 fixe dans LOGBOOK.
- **Réorganisation de la navigation** : FOCUS BANDE fusionné dans PROPAG,
  DEPARTEMENTS renommé ZONES TRAVAILLÉES (couvre désormais aussi les zones
  hors France).
- **Lint Python (ruff)** ajouté à l'intégration continue.
- Concours personnalisé ARRL International EME Contest ; correction des
  noms Cabrillo officiels REF-SSB/REF-CW, ARRL Field Day/10m/160m, WAE
  SSB/RTTY.

### Sécurité & fiabilité

Deux passages d'audit indépendants sur l'intégralité du dépôt, avec
vérification empirique (relecture du code réel, pas seulement des résumés
d'audit) avant chaque correctif :

- **RCE corrigée** via `autostart_programs` (exécution de programme
  arbitraire depuis la configuration), plus plusieurs XSS stockées
  (LOGBOOK, CARTE IA, CONFIG, décodeurs CW/RTTY, widgets météo) et une
  faille CSRF sur les routes POST authentifiées par cookie seul.
- **En-têtes anti-clickjacking** (`X-Frame-Options`, `Content-Security-Policy
  frame-ancestors`) sur toutes les pages servies.
- **Races et verrous manquants** corrigés sur une douzaine de sections
  critiques (cache DXCC, synchronisation cloud, session Wait-and-Pounce,
  cache spots cluster, callbook, chat multi-opérateur) et motif de "jeton
  de génération" généralisé à 9 endroits pour empêcher une réponse réseau
  tardive d'écraser un état plus récent affiché à l'écran.
- **Perf réseau** : plusieurs appels bloquants (roster WWA, prévision tropo)
  rendus non bloquants (cache lu immédiatement, rafraîchissement en tâche
  de fond) — ils pouvaient auparavant geler le thread HTTP jusqu'à 10s.
- **~200 correctifs mineurs** : code mort supprimé (vérifié par recherche
  dans tout le dépôt avant suppression), échappement HTML manquant sur une
  dizaine de sites, clés API déplacées des URL vers des en-têtes HTTP,
  incohérences de dates UTC/heure locale, doublons de logique factorisés.
- Build de release multi-OS (Windows/macOS/Linux) réparé après une
  régression PyInstaller passée inaperçue pendant deux jours faute de
  vérification par build réel.

### Corrigé

- Dialogues bloquants (`alert()`/`confirm()` natifs) éliminés du reste de
  l'interface, remplacés par des bandeaux non bloquants cohérents avec le
  reste du logiciel.
- CONFIG : import ADIF ouvre directement le sélecteur de fichier, popup se
  ferme sur clic extérieur sans naviguer ailleurs.
- Panneau décodeur SSTV agrandi (352→520px) ; panneau RTTY : clic sans
  effet et scroll de la colonne de saisie corrigés.
- `TypeError` récurrent dans l'horloge de la barre de statut.
- Version du programme intégrée automatiquement au message pré-rempli du
  bouton « signaler un problème ».

## [0.9-beta25] - 2026-08-07

### Ajouté

- **SO2R (deuxième radio)** : fiabilisation complète du focus existant
  (8 endpoints supplémentaires suivent désormais la bascule Ctrl+Espace —
  état radio, panadapter, keyer vocal), verrou logiciel d'exclusivité TX
  (empêche d'armer une émission sur une radio pendant que l'autre émet),
  MVP OmniRig pour la radio 2 (le CAT natif série reste limité à une seule
  connexion à la fois), périphérique de sortie vocal et second décodeur CW
  propres à la radio 2 (tourne en parallèle du premier). Revue adversariale
  avant fusion de la partie verrou/focus : 4 bugs critiques trouvés et
  corrigés (verrou jamais relâché sur un échec, verrou orphelin après
  bascule de focus, fenêtre de course entre deux lectures du focus,
  garde-fou OmniRig non remappé pour la radio 2).
- **Licence GPLv3** : le code de LogX AI est désormais sous licence libre
  GPLv3.
- **Import ADIF durci** pour les exports d'autres loggers de concours :
  convention de mode `PH`→SSB, tags propriétaires `APP_*` préservés,
  déduction de bande depuis la fréquence quand absente.
- **Fiche comparative** face aux loggers de concours établis
  (`docs/COMPARATIF_CONCURRENTS.md`) et contenu prêt à l'emploi pour un
  groupe d'entraide groups.io.

### Corrigé

- La fiche comparative affirmait à tort l'absence de support SO2R — corrigé
  pour refléter l'état réel (logiciel + protocole OTRSP, jamais testé sur
  un vrai boîtier).

## [0.9-beta24] - 2026-08-07

### Ajouté

- **Recherche plein-texte dans les pages** (`logx_search.py`/`.js`) : icône
  loupe dans la nav, indexe les titres et le texte visible de 12 pages —
  retrouver où une fonctionnalité (ex. SSTV) est mentionnée sans connaître
  par cœur la page concernée. Clic sur un résultat : navigation + passage
  mis en surbrillance sur la page cible.
- **Synchronisation MySQL partagée** (`logx_mysql_sync.py`, #163) :
  4ᵉ mécanisme de sync multi-poste (radio-club ou plusieurs postes d'un
  même OM), quasi temps réel via une base MySQL fournie par l'utilisateur —
  module optionnel (`pip install pymysql`), sans effet sur le reste de
  l'appli en son absence. Revue adversariale avant fusion : 2 bugs
  critiques de résurrection/perte silencieuse de QSO trouvés et corrigés.
- **Wiki GitHub** (site de présentation) : guide utilisateur découpé en
  pages navigables — https://github.com/sauveteur71/LogX_AI/wiki

### Corrigé

- Contraste illisible (texte quasi blanc) des champs de saisie en mode
  jour sur la page CONFIGURATION, et confusion entre un exemple de
  placeholder et une vraie valeur saisie.
- L'assistant CONFIGURATION répondait à côté de la plaque sur des
  questions sans correspondance réelle (recherche locale par sous-chaîne
  au lieu de mot entier).

## [0.9-beta22] - 2026-08-05

### Ajouté

- Décodeur CW accessible depuis le band map même hors mode CW (bouton dédié,
  sans affecter les macros ni le keyer vocal).
- Bandeau discret dans CHASSE rappelant que la chasse est secondaire pendant
  une activation (mode expédition avec référence configurée).

### Corrigé

- **Passe de vérification pré-bêta complète** (revue exhaustive du dépôt,
  30 lots domaine, chaque constat re-vérifié par un agent sceptique
  indépendant) : 58 correctifs, dont 2 critiques.
  - Pilotage ampli (KpaAmp/IcomAmp/SpeAmp) inopérant sur du vrai matériel
    série (méthode manquante sur le transport).
  - Faille XSS stockée via `/log/add` (indicatif non échappé dans le
    panneau « meilleur DX »), exécutable chez tous les opérateurs connectés.
  - Plusieurs risques sécurité (SSRF sur les règlements/URLs de log
    configurables, fuite de clé API entre fournisseurs IA, injection de
    prompt via données de cluster/concours personnalisé, traceback exposé
    sans authentification).
  - Plusieurs races/TOCTOU (config, QTC, cache GeoJSON, OAuth SOTA, cache
    voix IA) et bugs de score (Field Day CW/Digital sous-évalué, bonus
    "grand carré" IARU déclenché à tort).
  - Résolutions DNS non bornées (CAT rig/rotor, mise à jour, upload QSL)
    pouvant geler un thread indéfiniment en terrain/expédition.
  - Horloge d'en-tête du logbook qui plantait en boucle au chargement de
    page (trouvé en vérification navigateur, hors périmètre de l'audit).

## [0.9-beta21] - 2026-08-04

*Le journal a repris après une pause aux betas 14 à 20 (bump de version
seul, sans entrée détaillée) — voir l'historique git pour cette période.*

### Ajouté

- **📡 Panadapter**, en trois volets, chacun réutilisable seul :
  - **Audio universel** : spectre + chute d'eau calculés depuis l'audio de
    réception (câble/interface radio, jamais le micro), dans une fenêtre
    détachée dédiée. Marche avec n'importe quel poste, zéro matériel
    supplémentaire — limité à la largeur du filtre audio du poste.
  - **Scope CI-V natif (Icom)** : sur IC-7300/7610/9700/705/7851, un vrai
    panadapter large bande (jusqu'à 500 kHz de span) en réutilisant le port
    série déjà ouvert pour le CAT — le poste calcule son spectre en interne
    et le publie sur la même liaison.
  - **TCI (Flex/SunSDR)** : le protocole TCI n'a pas de "spectre tout fait"
    comme CI-V — LogX calcule sa propre FFT (écrite en pur Python, aucune
    dépendance ajoutée) à partir du flux IQ brut du serveur TCI.
- **🎙️ Keyer vocal : synthèse multi-voix.** Un correspondant DL, JA, etc.
  faisait lire l'indicatif et le report ("fifty-nine") avec l'accent de la
  voix locale choisie pour le message — le texte était déjà correct, seule
  la voix ne l'était pas. Chaque segment de langue est désormais synthétisé
  avec sa propre voix, jouée en séquence sous une seule prise de PTT.

### Corrigé

- **Le clic sur le tableau de bande ne faisait QSY qu'en fréquence, jamais
  en mode** — la radio changeait de fréquence mais restait sur le mode déjà
  affiché, y compris pour un spot CW pendant une saisie SSB.
- **Décodeur CW : aucun retour si le signal n'atteignait pas le seuil de
  détection.** Le pipeline de décodage lui-même n'avait pas de défaut
  identifiable, mais rien n'indiquait si le niveau audio, le périphérique ou
  le ton étaient en cause — ajout d'un vumètre de diagnostic (niveau reçu vs
  seuil) directement dans le panneau.

### Interne

- Scope CI-V et panadapter TCI développés et vérifiés par un processus à
  plusieurs passes indépendantes (implémentation puis relecture
  adversariale séparée) : un bug bloquant a été trouvé sur le scope CI-V
  avant fusion (une méthode utilisée par le nouveau code n'existait pas sur
  la connexion série de production, invisible aux tests parce que leur
  double de test l'exposait lui) — corrigé avant toute mise en ligne.

## [0.9-beta13] - 2026-07-31

### Ajouté

- **🛰 Prédiction de passages satellite.** LogX savait nommer un satellite
  (export ADIF) et pointer un rotor en azimut et en élévation — mais pas dire
  *quand* le satellite passe. Il fallait ouvrir Gpredict à côté. Le nouveau
  panneau de la page propagation (onglet VHF & EME, dont l'intitulé annonçait
  « satellites » depuis toujours) donne les prochains passages — heure,
  élévation maximale, azimuts de lever et de coucher, durée — la position
  instantanée, le Doppler, et un sélecteur des ~90 satellites amateur du jeu
  d'éphémérides CelesTrak.
  - **L'âge des éphémérides est la première ligne, colorée** : un TLE se
    dégrade, et trois semaines de dérive décalent un passage de plusieurs
    minutes — sur un passage qui en dure dix. Une prédiction sans son âge est
    une prédiction dont on ignore ce qu'elle vaut.
  - **Pensé pour l'expédition** : les éphémérides sont en cache sur disque et
    un jeu périmé reste utilisable ; le téléchargement tourne en tâche de fond
    et **refuse d'écraser un cache valide** par une réponse inexploitable — un
    portail captif d'hôtel répond « 200 » avec une page de connexion, et
    l'écraser détruirait la seule chose encore utilisable sur le terrain.
  - Le Doppler satellite n'a **pas** de facteur 2, contrairement à l'EME où le
    signal fait l'aller-retour — le piège de recopie est testé.
- **📻 La réglette de fréquence fonctionne enfin au-dessus de 440 MHz** : 23 cm,
  13 cm, 9 cm, 6 cm, 3 cm et 24 GHz, d'après le plan de bandes IARU Région 1
  (édition 2017, conférence de Landshut). Les segments sans équivalent
  d'affichage (télévision amateur, satellite) laissent un blanc plutôt qu'une
  couleur qui ment.
- **Le 23 cm d'après la CMR-23.** La décision ECC (25)01 du 27 juin 2025 ne
  redécoupe pas la bande : elle **plafonne la puissance** par sous-bande entre
  1258 et 1300 MHz pour protéger les récepteurs Galileo. Ces plafonds sont
  dans le logiciel avec leur grandeur exacte (e.i.r.p. ou puissance émetteur —
  les confondre fausserait le chiffre de plusieurs dizaines de dB), la
  dérogation EME conditionnelle, et les trois paliers par angle de site pour
  la montée satellite. *Période transitoire nationale possible jusqu'à trois
  ans : la date d'application réelle dépend du pays.*

### Corrigé

- **La mise à jour pouvait mourir jusqu'au redémarrage, sans un message.** Si
  le téléchargement échouait dans ses toutes premières étapes (création du
  dossier, démarrage du fil d'exécution sous une machine chargée), le statut
  « téléchargement en cours » restait posé à jamais et tout nouvel essai était
  refusé. Sur une expédition — quinze jours, rien de réparable sur place —
  c'est la panne qu'on découvre le jour où on en a besoin. L'état bloqué est
  désormais **détecté et réparé automatiquement**, et chaque échec pose un
  message.
- **Les messages du téléchargement pair-à-pair distinguent enfin deux pannes**
  qui ne se dépannent pas au même endroit : « poste injoignable (éteint,
  occupé, délai de sonde dépassé) » et « aucun exécutable vérifié à servir ».
  L'ancien message unique accusait le pair de ne rien avoir alors qu'il
  n'avait simplement pas répondu à temps — en multi-op, on cherchait le
  problème sur le mauvais poste.

### Interne

- La suite de tests locale est redevenue **reproductiblement verte** : le
  défaut ci-dessus contaminait les tests suivants au hasard (un échec par
  passe, jamais le même). Diagnostic par vérification adversariale — 17
  hypothèses, 12 réfutées, dont l'épuisement des ports réseau, écarté par la
  mesure. Trois passes complètes consécutives vertes après correctif.

## [0.9-beta12] - 2026-07-31

Suite de la beta11, même méthode : le code confronté à des références
chiffrées plutôt que relu. Six défauts de plus, et le chantier des traductions
terminé.

### Corrigé

- **Les dialogues du logiciel étaient intraduisibles.** Le moteur de traduction
  couvre tout ce qui passe par le DOM, mais `alert`/`confirm`/`prompt` ne sont
  jamais des nœuds : rien ne pouvait les voir. La page CONFIGURATION — la plus
  longue, celle qu'on voit en premier — n'avait même aucun mécanisme de
  traduction pour ses 20 dialogues. **31 textes traduits × 7 langues.**
- **Le locator n'était pas validé côté serveur.** `JN18ZZ` donnait un point
  situé **hors de son propre carré** ; `ZZ99XX`, une longitude de 339° ;
  `JN18@@`, un point avant le coin du carré. Aucun message : une position
  plausible et fausse. Les locators viennent du cluster, de PSK Reporter, de
  l'import ADIF — et surtout de la saisie manuelle en concours, où la faute de
  frappe est la règle. En THF, un locator faux, c'est un multiplicateur faux.
- **Tout locator à 4 caractères tombait 3,8 km au nord-est du centre de son
  carré**, systématiquement, dans les trois implémentations à la fois.
- **La perte de trajet EME était fausse de 123 dB** — 374 dB à 144 MHz au lieu
  de 252 — et sa croissance avec la fréquence l'était aussi. Le calcul doublait
  une atténuation en décibels au lieu d'appliquer l'équation radar : la Lune
  n'est pas un point qui réémet, elle a une immense surface réfléchissante.
  Vérifié contre les trois valeurs de référence à moins de 0,4 dB. *La fonction
  n'avait aucun appelant : personne n'a jamais vu ce chiffre. Elle est désormais
  branchée sur le panneau EME, avec la distance lunaire du moment.*
- **Pendant un orage géomagnétique, le logiciel fermait le 6 m au moment même où
  il y annonçait l'aurora.** À K=6 le score d'ouverture de la bande chutait de
  40 %, pendant que le coach affichait « aurora possible, pointe au nord ».
  Il se trompait de signe. La pénalité par bande a été **retirée** : aucune
  norme n'en donne (l'échelle du NOAA est latitudinale, pas fréquentielle), et
  une tempête peut tout aussi bien *améliorer* la propagation. L'aurora reste
  annoncée là où elle est fondée — et elle **ouvre** la VHF.
- **La table de bandes des transverters décrivait encore la région 2** (6 m
  jusqu'à 54 MHz, 2 m jusqu'à 148) après la correction de la beta11 : deux
  tables du même logiciel décrivaient les mêmes bandes différemment.

### Modifié

- **L'indice A géomagnétique est enfin servi.** Il était récupéré, affiché, et
  n'entrait dans aucun calcul — or c'est lui qui porte l'**historique** des
  dernières 24 h, ce qu'un indice instantané ne peut pas donner. Il est
  désormais transmis à l'écran et à l'assistant IA, qui peuvent en tenir compte.
- **Le plan de bandes dit d'où viennent ses chiffres.** Les bornes légales
  (ANFR) et le découpage par mode (convention IARU) sont deux choses
  différentes, qui évoluent à des rythmes différents ; elles étaient mélangées
  sans que rien ne le dise. L'absence de segments au-dessus de 440 MHz est
  maintenant un **choix documenté** — la réglementation du 23 cm est en cours
  de révision — et non un oubli.

## [0.9-beta11] - 2026-07-31

Version de **correction**, sans nouvelle fonctionnalité. Sept défauts, tous
trouvés en confrontant le code à une référence radioamateur chiffrée (plan de
bandes IARU R1 / France, et fiches de pilotage CAT) au lieu de le relire.

### Corrigé — plan de bandes

- **FT8 était classé PHONIE sur 6 m, 2 m et 70 cm, et CW sur 160, 80 et 12 m.**
  Six bandes sur douze. Choisir « SSB » sur 2 m affichait donc les spots FT8 —
  le mode le plus utilisé au monde, sur les bandes des concours THF. *Pourquoi
  un découpage par plages ne pouvait pas y arriver : le plan de bandes officiel
  et l'usage réel ne coïncident pas. 144,174 MHz tombe dans le segment « SSB »
  du plan IARU R1, et c'est pourtant LA fréquence FT8 du 2 m, la même partout
  dans le monde.* Les fréquences d'appel numériques (FT8, FT4, JS8, WSPR) sont
  désormais consultées avant le plan de bandes.
- **La table des segments décrivait l'Amérique du Nord** : 40 m jusqu'à 7,300 ·
  80 m jusqu'à 4,000 · 160 m jusqu'à 2,000 · 6 m jusqu'à 54 · 2 m jusqu'à 148,
  et une bande 222 MHz **qui n'existe pas en région 1**. La réglette montrait
  des centaines de kHz où un opérateur français n'a pas le droit d'émettre, et
  un clic sur une épingle placée là commandait un QSY hors bande. Un spot hors
  des bandes françaises est maintenant **conservé mais marqué** : l'entendre
  renseigne sur la propagation, y répondre n'est pas permis.
- **Le 4 m (70 MHz) était proposé comme bande standard.** Il est attribué dans
  plusieurs pays de région 1, pas aux amateurs en France. Il réapparaît si un
  spot y tombe ou si un concours l'utilise — le cas de l'expédition.
- **Une bande WARC pouvait être « recommandée » pendant un concours**, où la
  convention IARU les interdit. Seule la recommandation est bridée : la bande
  reste affichée avec son score, et hors concours elle redevient recommandable.

### Corrigé — pilotage de la radio

- **« SSB » n'atteignait aucune table de mode, sur aucune marque.** Le carnet
  parle *SSB · FT8 · FT4 · PSK*, la radio veut *LSB · USB*. Sur douze modes du
  carnet, cinq seulement arrivaient quelque part. Cliquer un spot changeait la
  fréquence et **laissait la radio dans son mode précédent**, sans un mot.
  Deux conventions sont désormais appliquées, et elles ne se déduisent pas
  l'une de l'autre : la **phonie** est en LSB sur 160/80/40 m puis USB à partir
  du 20 m ; le **numérique est en USB sur toutes les bandes**, y compris là où
  la phonie est en LSB — sans quoi la radio se serait mise en LSB sur 7,074 MHz.
- **Le QSY ne fonctionnait pas sur les Yaesu ASCII** (FT-891, FT-991/991A,
  FTDX10, FTDX101) : la fréquence partait sur 11 chiffres à un protocole à
  champs de largeur fixe qui en attend 9.
- **FT-817, FT-818, FT-857 et FT-897 étaient proposés** alors que leur CAT est
  binaire et que le pilotage natif ne parle qu'ASCII : la radio ne répondait
  jamais, exactement comme un câble débranché. Ils restent proposés, marqués
  **« via rigctld/Hamlib »**, avec l'explication affichée — et le pilote natif
  les refuse avant d'ouvrir le port au lieu d'attendre un délai d'expiration.
- **Le mode DATA-USB manquait pour les Yaesu** : la radio ne pouvait pas être
  mise en numérique par le logiciel.
- **La vitesse série** est signalée sur la page CONFIG : le champ propose
  4800 bauds (valeur d'usine des FT-8x7 et des Yaesu historiques), mais les
  postes pilotés en natif sortent d'usine plus haut, et les deux valeurs
  doivent coïncider sinon rien ne répond.

## [0.9-beta10] - 2026-07-31

### Ajouté

- **🎯 FOCUS BANDE — une page entière consacrée à la bande que vous regardez.**
  Tout ce que le logiciel sait déjà de cette bande, rassemblé sur un écran au
  lieu d'être éparpillé : le cluster filtré **bande ET mode**, les carrés
  travaillés ailleurs mais pas ici, l'état des ouvertures région par région,
  les concours actifs **sur cette bande et ce mode à cet instant**, les
  suggestions de contact de l'IA, et le classement de toutes les bandes avec la
  raison du classement écrite en clair. La bande se choisit à la main **ou suit
  la radio** (CAT). Faite pour rester ouverte sur un deuxième écran : un seul
  appel serveur (`/data/focus`) toutes les 15 s au lieu de six, et une réponse
  bornée — le panneau coach envoyait jusque-là 5,5 Mo à chaque rafraîchissement
  pour une donnée que personne n'affichait.
- **Autant de fenêtres par bande qu'on veut, côte à côte.** Cinq band maps sur
  un deuxième écran pour surveiller cinq bandes en même temps, chacune dans sa
  propre fenêtre.
- **Les écrans détachés sont atteignables depuis TOUTES les pages** — SCOPE,
  MUR et FENÊTRES PAR BANDE ont rejoint le menu DISPOSITION de la barre de
  statut. On peut donc ouvrir l'écran mural depuis la page propagation, ce qui
  était impossible auparavant.
- **Menu « DÉBUT / FIN » du logbook**, dont le contenu s'adapte au mode : en
  logbook simple, ni CHECKLIST, ni VÉRIFIER, ni EDI, ni ARCHIVER — il n'y a
  aucun log à soumettre.

### Modifié

- **La page CONFIGURATION ne s'impose plus à chaque démarrage.** Elle ne
  s'ouvre que tant que la station n'est pas configurée ; ensuite le logiciel
  ouvre directement le logbook. Le test porte sur l'indicatif renseigné, pas
  sur l'existence du fichier de configuration : un fichier créé par un réglage
  sans rapport ne doit pas faire croire que la station est prête.
- **Logbook épuré : 30 commandes dans la barre, 11 désormais.** Compté avant de
  trancher — 11 d'entre elles ne servaient qu'avant ou après l'épreuve, pour
  deux clics par concours, tout en occupant la moitié de la barre pendant tout
  le trafic. Ne reste que ce qu'on touche la main sur le manipulateur.
- **L'assistant IA sait enfin à quel usage il répond.** Le réglage
  *logbook simple / concours / expédition / radioclub* existait depuis
  longtemps mais **n'arrivait jamais jusqu'au prompt** : l'IA parlait stratégie
  de concours à quelqu'un qui chasse tranquillement le DX. La consigne envoyée
  au modèle est écrite en langage clair — pas en drapeaux — ce qui la rend
  valable pour **n'importe quel fournisseur d'IA**, et elle porte autant sur ce
  qu'il ne faut PAS évoquer que sur ce qui compte. Hors concours, les
  règlements ne sont plus chargés du tout dans le prompt.
- **Le bandeau des bandes sort dans l'ordre des fréquences**, et non plus par
  score : il se relit toutes les 15 s, les bandes changeaient donc de place
  sous le doigt. Le classement passe de la position à un marqueur (barre de
  score + liseré vert sur la bande recommandée), qui ne déplace rien.
- **Tout le plan de bandes est proposé** (1,8 · 3,5 · 7 · 10,1 · 14 · 18 · 21 ·
  24 · 28 · 50 · 70 · 144 · 432), WARC comprises, plus les bandes du concours
  et celles où un spot tombe. La liste venait des seules bandes du concours
  actif : sur une épreuve à deux bandes, la page devenait borgne.

### Corrigé

- **Un attribut à tiret faisait exploser la traduction de tous les suivants.**
  Le moteur i18n mémorisait l'original d'un attribut dans `dataset`, sous une
  clé reprenant son nom : `aria-label` donnait `__i18n_aria-label`, que
  `DOMStringMap` **refuse** avec une exception. Celle-ci avortait la boucle,
  donc la traduction de tous les attributs restants de la page — sans le
  moindre message. Les tests ne pouvaient pas le voir : leur faux DOM acceptait
  n'importe quelle clé.
- **Cinq pages ne chargeaient pas du tout le moteur de traduction** — fenêtre
  par bande, mobile, panneau détaché, scope, écran mural : un cinquième du
  logiciel restait en français quelle que soit la langue choisie.
- **Le coach décomptait vers un concours qui n'existait pas** : « départ dans
  18,2 h — passe la CHECKLIST » alors que la barre de statut affichait « aucun
  concours ». Les dates d'une épreuve précédente survivent dans la
  configuration ; le compte à rebours était cohérent et ne portait sur rien.
- **Cinq fenêtres par bande demandées ne donnaient qu'UNE fenêtre**, chaque
  nouvelle bande remplaçant la précédente : `window.open` réutilise la fenêtre
  qui porte déjà le nom demandé.
- **FOCUS : le filtre de mode ne filtrait rien** (les spots du cluster ne
  portent pas de mode fiable — il est désormais **déduit de la fréquence**, par
  la même table que la réglette de bande), **la carte des carrés restait vide
  en permanence** et **les suggestions aussi** (deux hypothèses fausses sur la
  forme des données, l'une et l'autre silencieuses), **les ouvertures
  s'affichaient sans chiffre** pour toutes les régions sauf une.
- **Traductions : 7 formulations établies étaient réécrites en silence.**
  L'extracteur de clés ne lisait qu'un seul style de guillemets et une seule
  paire par ligne — il annonçait donc des textes « non traduits » qui
  l'étaient, et faisait apparaître un trou allemand qui n'existait pas.

### Interne

- **Les phrases à valeur variable sont traduisibles.** « Aucun spot sur 14 MHz »
  ne peut être aucune clé de dictionnaire ; `rcTf()` remplace les trous
  **après** traduction, et le script de génération refuse d'écrire si une
  traduction perd ou renomme un trou — sans ce garde-fou, `{call}` s'afficherait
  tel quel dans une seule langue, sans que rien ne le signale.
- **Mesure corrigée** : j'avais annoncé « 646 chaînes JavaScript à traduire ».
  Une chaîne injectée dans le DOM est traduite par le moteur sans aucun appel
  explicite ; seules trois familles lui échappent. Le vrai chiffre est ~190.

## [0.9-beta9] - 2026-07-30

### Ajouté

- **🎯 WAIT & POUNCE — appel automatique en FT8/FT4, en quatre niveaux
  activables séparément.** Niveau 1 : signaler (son + couleur). Niveau 2 : un
  clic sur un indicatif entendu prépare la réponse dans WSJT-X, l'émission
  restant sous votre doigt. Niveau 3 : le logiciel appelle seul dès qu'un
  décodage correspond à vos critères. Niveau 4 : la même chose **sans personne
  devant la radio**. Les critères s'appuient sur ce que LogX sait déjà et
  qu'aucun utilitaire équivalent ne connaît — entité jamais travaillée, entité
  non confirmée LoTW **sur ce créneau bande × mode précis**, carré jamais
  travaillé, nouveau multiplicateur — le tout contre le carnet à vie.
  Garde-fous : durée maximale avec désarmement automatique, un seul appel en
  vol, trois appels maximum par station, plafond de 30 appels par quart d'heure
  qui désarme la session, journal de tout ce qui est parti, et coupe-circuit
  atteignable depuis n'importe quel poste. La session n'est jamais enregistrée
  sur disque : un redémarrage ne peut pas relancer l'émission.
- **La liaison WSJT-X sait désormais ÉMETTRE**, pas seulement écouter. C'est
  la fondation des quatre niveaux : LogX envoie un message `Reply`, strictement
  équivalent à un double-clic sur la ligne du waterfall. Aucun signal radio
  n'est fabriqué par LogX — WSJT-X reste maître de ce qui part sur l'air.
- **Satellites : `PROP_MODE=SAT` et `SAT_NAME` à l'export ADIF.** Sans ces deux
  champs, LoTW créditait les QSO satellite comme des contacts **terrestres**.
  Le satellite choisi en CONFIG est désormais reporté sur les QSO, avec deux
  précautions : un QSO qui porte déjà un satellite n'est jamais écrasé, et la
  valeur « Autre » du sélecteur n'est jamais envoyée — `SAT_NAME=AUTRE` ferait
  rejeter le fichier entier au téléversement.
- **Filtres d'affichage des spots** (inspirés de `SET/FILTER` des clusters CC) :
  continent du spotteur, continent de la station DX, masquer les déjà
  travaillés, utilisateurs LoTW seulement, besoins DXCC seulement. Appliqués
  **côté serveur avant la coupe à 40** : c'est ce qui fait apparaître des
  stations qui étaient auparavant repoussées hors de la liste par le bruit. Le
  nombre de spots masqués est toujours affiché, et un spot retenu par une règle
  d'alerte traverse le filtre plutôt que de disparaître.
- **Grille bande × mode : le nombre d'entités DXCC**, en plus des QSO, avec la
  colonne LoTW distincte. C'est ce chiffre qui dit où vous en êtes du Challenge.

### Corrigé

- **Le band map, le bandscope, la chute d'eau et le scope détaché
  n'affichaient PAS les spots HF du cluster** — et ce depuis toujours, pas
  depuis une régression. Les sources ne s'accordent pas sur l'unité (DXSummit
  HF et DXHeat en kHz, DXSummit VHF en MHz) et le serveur recopiait la valeur
  telle quelle : seuls les spots du bon côté du hasard passaient. Une seule
  unité est désormais imposée, tranchée **par la bande** et non par la
  magnitude. Dessous se cachait un second défaut : un clic sur un spot HF
  aurait commandé un QSY 1000 fois trop haut.
- **Bandscope détaché : les indicatifs se superposaient.** Trois stations sur
  la même fréquence FT8 écrivaient au même endroit ; deux fréquences voisines
  se télescopaient. Les indicatifs s'empilent maintenant, avec un filet de
  rappel vers leur barre.
- **La réglette de fréquence des fenêtres par bande était vide en
  permanence**, et le clic sur une épingle ne faisait rien — le message envoyé
  à la radio ne portait pas un champ que le serveur sait lire.
- **Le refus « corps trop volumineux » de la page de connexion n'arrivait pas
  au client** : la connexion était fermée sur des octets non lus, ce qui
  détruit la réponse déjà émise. L'utilisateur voyait une erreur réseau au lieu
  du message.
- **Grille bande × mode et panneau Diplômes annonçaient un nombre de cases
  Challenge différent** (454 contre 435) : la grille comptait des bandes qui
  n'entrent pas dans le Challenge ARRL.
- Deux liens du sommaire du guide utilisateur (chapitres 6 et 12) ne menaient
  nulle part depuis leur écriture.

### Modifié

- **Vocabulaire : « activation » et « activateur » ont disparu des écrans
  français** (demande utilisateur), au profit du vocabulaire radioamateur —
  « stations en direct », « trafic », « EXPÉDITION / PORTABLE ». L'anglais et
  l'allemand conservent les termes officiels de POTA, SOTA et WWFF.

### Sécurité

- Les motifs `.gitignore` protégeant les secrets étaient **ancrés sur
  `concours/`**. Un serveur, un test ou un script lancé depuis la racine y crée
  les mêmes fichiers, non ignorés : un `git add -A` aurait pu publier
  `.auth_token`, le jeton qui autorise toutes les écritures.

## [0.9-beta8] - 2026-07-28

### Modifié

- **Les panneaux décodeurs n'apparaissent plus que dans leur mode** (demande
  utilisateur) : le panneau 🔤 DÉCODEUR CW n'est visible qu'en mode CW — il
  restait auparavant affiché dans tous les modes sauf RTTY — et le panneau
  🖼 DÉCODEUR SSTV qu'en mode SSTV. Le mode SSTV lui-même est opt-in : une
  case **SSTV** a été ajoutée à CONFIG > MODES (aucun concours ne l'impose,
  c'est un mode d'activité — dimanches SSTV, ISS) ; cochée, le bouton SSTV
  apparaît dans le sélecteur de mode du logbook. Les deux panneaux occupent
  le même emplacement bas-gauche puisqu'ils ne peuvent plus coexister.

### Ajouté

- **Décodeur SSTV intégré au logbook** (panneau 🖼 en bas de l'écran, visible
  en mode SSTV) : réception des images à balayage lent — activations,
  dimanches SSTV, transmissions de l'ISS en PD120 — **sans MMSSTV ni RX-SSTV
  à côté**, tout se passe dans le navigateur comme pour les décodeurs CW et
  RTTY. Détection automatique du mode par l'en-tête VIS (Martin M1/M2,
  Scottie S1/S2/DX, Robot 36/72, PD50 à PD290), image construite ligne par
  ligne pendant la réception, compensation continue de la dérive d'horloge
  entre cartes son (l'image « penchée » classique) sur les impulsions de
  synchro, export PNG horodaté. Pipeline DSP dans `logx_sstvdecoder.js`,
  couvert par des tests aller-retour encode → décode (fidélité mesurée au
  pixel près sur les 14 modes, dérive d'horloge, bruit, rejet des en-têtes
  VIS invalides).

### Corrigé

- **Le lanceur Windows pouvait rouvrir l'ANCIENNE version après une mise à
  jour, en affichant que tout allait bien.** `LANCER_RADIOCONTEST.bat` testait
  le port avec `curl http://localhost:8080/` : dès que quelque chose répondait,
  il affichait « [OK] Serveur deja en route » et ouvrait le navigateur **sans
  jamais exécuter `logx_serveur.py`**. Or c'est ce dernier qui porte la
  détection d'instance déjà lancée (`logx_singleton`). Un serveur laissé en
  route depuis la veille servait donc indéfiniment son ancienne version, et
  l'utilisateur concluait que la mise à jour avait échoué. Constaté sur poste
  réel : la 0.9-beta5 s'affichait alors que la 0.9-beta7 était installée.
  Le lanceur appelle désormais `logx_instance.py`, qui compare la version qui
  répond à celle du dossier ; à version différente il **n'ouvre aucune page**
  et explique quoi fermer.
- **Le message « LogX AI est déjà lancé » nomme maintenant les deux versions**
  côte à côte (celle qui répond, celle installée). Il décrivait le mécanisme
  — « c'est l'ANCIEN qui continuerait de répondre » — sans jamais donner les
  numéros, alors que c'est exactement ce que cherche quelqu'un qui vient de
  mettre à jour. Vaut aussi pour `LogXAI.exe`, qui ne passe pas par le `.bat`
  mais tombait dans le même piège.

- **Bande vide et défilement inutile sous le keyer vocal.** La hauteur réservée
  au panneau décodeur flottant était calculée une seule fois, au chargement,
  avant que la page ait fini de se construire — puis conservée toute la
  session. Mesuré en fenêtre 1400 px, décodeur fermé (donc rien à réserver) :
  la zone était bridée à 257 px alors qu'elle pouvait en occuper 366, d'où
  109 px de vide en dessous et une barre de défilement sur un contenu qui
  serait tenu sans. Le calcul est refait une fois la page terminée et à chaque
  changement de taille de fenêtre — agrandir la fenêtre ne rendait jamais la
  hauteur gagnée.
- **Le lanceur n'ouvre plus le navigateur sans savoir si le serveur a
  démarré.** Il attendait `timeout /t 3` en aveugle, puis ouvrait les pages
  quoi qu'il arrive. Deux conséquences : la fenêtre du serveur étant lancée
  minimisée (`start /MIN`), un refus de démarrer — port pris entre la sonde et
  le bind, fichier manquant — s'affichait là où personne ne regarde pendant
  que le navigateur montrait « impossible de se connecter » sans la moindre
  explication ; et 3 secondes n'était qu'une devinette, donc sur un poste lent
  (ou avec un antivirus qui inspecte l'interpréteur) la page s'ouvrait trop tôt
  sur la même erreur alors que tout allait bien. Le lanceur attend désormais
  que le port **réponde** ; s'il ne répond pas, il n'ouvre rien, nomme la
  fenêtre minimisée où lire la cause, et affiche les dernières lignes du
  journal d'erreurs **si elles datent de ce démarrage** (un journal n'étant pas
  effacé entre deux lancements, l'afficher sans regarder sa date désignerait
  une panne ancienne comme cause du problème du jour).

### Interne

- `logx_i18n.js` n'emploie plus `\p{L}` : les échappements de propriété
  Unicode exigent un moteur JS compilé **avec ICU**, or le V8 embarqué par la
  suite de tests (`py_mini_racer`) est un build **sans ICU** et lève une
  `SyntaxError` dessus. Comme V8 ne compile une expression régulière littérale
  qu'à sa *première évaluation*, l'erreur restait invisible tant que la
  correspondance directe aboutissait : la règle du préfixe emoji était
  structurellement **intestable**. Remplacé par une recherche de première
  lettre écrite à la main, vérifiée sur un corpus de 1005 chaînes réelles
  (14 divergences, toutes multilignes, toutes sans effet).
- `logx_singleton.sonde_sans_bind()` : sonde qui se contente de se connecter,
  sans jamais ouvrir le port. `probe()` fait un vrai `bind` pour savoir si le
  port est libre ; l'employer en boucle pendant qu'un serveur démarre lui
  volerait le port à l'instant de son bind — sous Windows, où
  `allow_reuse_address` est volontairement désactivé, ce bind échouerait en
  `WinError 10048`. L'attente aurait provoqué la panne qu'elle surveille.
- `LANCER_RADIOCONTEST.bat` était listé dans `.gitignore` parmi les
  « documents personnels de préparation », entre deux PDF. C'est un fichier du
  programme (chemins relatifs, prévu pour un zip extrait n'importe où) : il est
  désormais suivi, et son câblage est vérifié par les tests.

## [0.9-beta7] - 2026-07-27

Version issue d'une **étude comparative** avec les loggers de concours établis
(voir `docs/ETUDE_COMPARATIVE_2026-07.md`). Huit écarts y avaient été
identifiés et vérifiés ; les huit sont traités ici. S'y ajoutent les
correctifs d'une passe d'audit, dont plusieurs pertes de données silencieuses.

**Réserve importante, à lire avant de compter dessus** : le WinKeyer, la
commande CW `KY`, les transverters, le keyer vocal et le boîtier SO2R ont été
développés **sans qu'aucun matériel soit branché**. Les trames sont conformes
aux spécifications des protocoles et vérifiées octet par octet, mais le premier
essai sur un poste réel reste à faire. Le décodeur RTTY, lui, est vérifié de
bout en bout par signal synthétique — sauf en pile-up réel.

### Ajouté
- **Les macros se déclenchent aux touches F1 à F8.** Les boutons affichaient « F1 »… « F8 » depuis toujours, mais seul le clic les déclenchait : en run, la main devait quitter le clavier pour viser un bouton. Actif même pendant la saisie — on tape l'indicatif, on envoie l'échange, on continue.
- **Manipulation CW en mode Natif** (commande `KY`) pour **Kenwood et Elecraft**. Le mode que la configuration recommande par défaut refusait auparavant tout envoi CW : un opérateur CW n'avait donc aucune manipulation.
- **Manipulateur WinKeyer K1EL** sur son propre port série. Il prend la main sur l'envoi CW **quelle que soit la marque** — c'est la seule manipulation possible en Icom (le protocole CI-V ne publie aucune commande d'envoi de texte CW) et en Yaesu. Sa cadence ne dépend plus du trafic CAT.
- **Support des transverters.** Au-dessus de 1296 MHz la radio affiche sa fréquence intermédiaire : sans table de conversion, la bande déduite, le QSO enregistré, le filtre du band map, le QSY et le fichier EDI étaient **tous faux au même moment, sans le moindre message**. Concerne directement le Rallye des Points Hauts, le National THF et le Challenge THF.
- **Décodeur RTTY (Baudot/ITA2) dans le navigateur**, sans logiciel externe. Chaque indicatif décodé est **cliquable** et part dans la saisie : c'est ce geste qui fait la vitesse en RTTY.
- **Band map Search & Pounce** : les stations que vous entendez vous-même en balayant s'ajoutent à celles du cluster, avec un repère distinct. `Ctrl+Entrée` note la station en cours, `Ctrl+↑`/`Ctrl+↓` sautent de spot en spot (QSY et indicatif pré-remplis). Les notes vivent sur le serveur — partagées entre postes — et s'effacent au bout de 30 minutes, une station entendue il y a une heure ayant presque sûrement changé de fréquence.
- **SO2R** : deuxième radio déclarable, bascule d'émission par `Ctrl+Espace`, pilotage d'un boîtier OTRSP (microHAM, YCCC, EA4TX). Le QSY, les macros et le manipulateur visent la radio qui a l'émission. Le « dueling CQ » automatique et le second band map ne sont **pas** faits.

### Modifié
- **Le keyer vocal émet enfin par la radio.** Les messages enregistrés partaient vers la sortie par défaut du navigateur, sans PTT : le correspondant n'entendait rien. Ils empruntent désormais le chemin du callbot (PTT levé, lecture vers le périphérique choisi, PTT relâché avec vérification). Ils sont stockés **sur le serveur**, donc suivent l'opérateur d'un poste à l'autre et survivent au vidage du cache ; les enregistrements existants sont repris automatiquement.
- **Les points ne s'affichent que si un concours est sélectionné.** Sans concours, le barème retombait sur 1 pt/km et affichait des scores parfaitement calculés mais qu'aucun règlement ne compte. Distance, nombre de QSO, meilleur DX et pays restent affichés — eux sont vrais dans tous les cas.
- **PROPAGATION** : le tableau OUVERTURES PAR RÉGION passe en pleine largeur au-dessus des autres panneaux. Coincé dans une colonne, il se repliait derrière une barre de défilement horizontale qui masquait la colonne RÉGION — la seule qui identifie la ligne.

### Corrigé
- **Cabrillo enfin soumissible.** Deux générateurs coexistaient pour le même fichier, chacun avec ses défauts : l'en-tête portait l'identifiant interne (`REF_CDF_HF_SSB`) au lieu du nom officiel, le locator était ajouté à l'échange même en HF, et le générateur du navigateur écrivait l'échange **sans le compte-rendu** — un CQ WW partait avec `001` au lieu de `59 14`. Les robots de réception refusent ou déclassent en *checklog* pour moins que ça. Un seul générateur subsiste, et les lignes `CATEGORY-*` sont complètes.
- **Un seul QSO malformé gelait définitivement toute la sauvegarde sur disque**, en silence.
- **Les identifiants de QSO pouvaient entrer en collision** : l'import ADIF consommait plusieurs secondes d'identifiants futurs, si bien qu'un QSO saisi juste après en héritait. Supprimer un contact en effaçait alors un autre, sans erreur.
- **Chaque QSO réécrivait l'intégralité du carnet** — de l'ordre du téraoctet écrit sur une expédition de 15 jours.
- **La rotation des sauvegardes effaçait les fichiers Cloud Sync** et les marqueurs de suppression du poste.
- **Export EDI** : le numéro de série envoyé était régénéré depuis la position dans la liste ; le numéro réellement passé sur l'air était jeté.
- **Macro CW `{NR}`** : envoyait le nombre total de QSO + 1 au lieu du numéro de série de la bande — le numéro annoncé n'était pas celui du log.
- **Ouvrir la page CARTE écrasait la configuration partagée** du serveur : carnet vidé et numérotation remise à 001 sur tous les postes.
- **Export ADIF** : le champ `<BAND>` était invalide sur les 14 bandes.
- **Refus HTTP** : les réponses « trop de tentatives » et « non autorisé » pouvaient se perdre. Fermer une connexion dont le tampon contient encore des octets fait envoyer un RST qui détruit la réponse déjà émise — l'utilisateur recevait une erreur réseau au lieu du message lui disant quoi faire.
- **Le guide récité par l'assistant IA** décrivait une page de configuration en 5 étapes remplacée depuis par un ensemble de cartes : il envoyait les utilisateurs vers des écrans inexistants. Même correction pour un texte de la page CONFIG.
- **Suite de tests** : elle produisait environ un échec aléatoire par passe, sur un test différent à chaque fois. Deux causes corrigées ; deux passes complètes de 1691 tests sont désormais sans échec.

## [0.9-beta6] - 2026-07-26

Refonte de la page PROPAGATION, jugée « inutilisable » par un utilisateur :
18 panneaux répondant à 5 questions différentes y étaient empilés. Plus une
série de correctifs de fond sur le serveur.

### Ajouté
- **Page CHASSE** : les cibles de trafic (activateurs POTA, SOTA, WWFF, châteaux WCA, need list du cluster) quittent la propagation pour une page dédiée — chercher qui appeler et consulter les conditions sont deux gestes différents.
- **PROPAGATION en 3 onglets** : HF · VHF & EME · M'entend-on ? La page s'ouvre automatiquement sur l'onglet pertinent selon le concours actif (bandes VHF → onglet VHF). Aucun défilement, vérifié par mesure à 1366×768 comme à 1920×1080.
- **Alerte orage dans la barre de statut**, présente sur toutes les pages, à la place du panneau de carte permanent : on n'a pas besoin de voir la foudre en continu, mais d'être prévenu quand il faut débrancher les antennes.
- **Nombre d'opérateurs saisi directement**, au lieu d'un clic par opérateur — neuf clics pour une équipe de dix. Réduire l'effectif demande confirmation si les lignes supprimées contiennent déjà un indicatif.
- **Plafond d'opérateurs porté de 5 à 40** en concours et expédition. La limite de 5 était historique et sans justification technique (le mode radioclub tournait déjà à 40 avec le même export) : une DXpédition à 10 opérateurs, ou une équipe de 9 en contest IOTA, était purement et simplement bloquée.
- **Protection contre le double lancement** : relancer le logiciel alors qu'une instance tournait affichait un démarrage normal… mais c'est l'ANCIENNE qui continuait de répondre, et deux serveurs écrivaient dans le même journal de contacts. Message clair et ouverture de la fenêtre existante.
- **Réseau de balises NCDXF/IBP** rendu accessible depuis toutes les pages.

### Modifié
- **Connexions HTTP persistantes** : une page ouvrait autant de connexions réseau que de fichiers, et chaque sondage périodique en rouvrait une. Elles sont désormais réutilisées — moins de va-et-vient réseau, utile en multi-poste.
- Les rafraîchissements d'un onglet masqué sont **suspendus** : une page laissée ouverte en arrière-plan interrogeait le serveur en continu pour personne (mesuré : 27 requêtes en 68 s).

### Corrigé
- **Infobulles qui clignotaient** indéfiniment entre le français et la langue choisie, sur toutes les pages en langue étrangère.
- **Le champ de recherche de concours de la configuration restait en français** dans les 7 langues traduites — il n'avait de traduction dans aucune. Plus généralement, les infobulles et champs de saisie introduits par un pictogramme (🔍, ✅…) suivent désormais la même règle de traduction que le reste du texte : jusqu'ici seuls les libellés en bénéficiaient.
- Traduction du titre d'onglet qui, si elle échouait, interrompait **toute** la traduction de la page — celle-ci restait alors intégralement en français sans le moindre message.
- Plusieurs libellés illisibles à 1366×768 (mode et nom du parc dans les listes d'activateurs, explication de la need list).
- Mise à jour réseau : un fichier plus court qu'annoncé bloquait 30 s au lieu d'échouer immédiatement.

### Sécurité
- **Mot de passe d'accès réaffiché en clair.** Après 5 essais infructueux — exactement le cas pour lequel la protection anti-force-brute existe — la tentative suivante était refusée sans lire les données envoyées. Celles-ci se retrouvaient collées à la requête suivante du navigateur, produisant une page d'erreur qui contenait le mot de passe tapé. Défaut apparu avec les connexions persistantes de cette même version, jamais publié.
- Deux autres cas de désynchronisation de connexion (requête refusée dont les données n'étaient ni lues ni écartées) pouvant délivrer à un client la réponse destinée à une autre requête.

## [0.9-beta5] - 2026-07-25

Version issue d'un audit systématique du code (6 angles d'analyse, chaque
constat soumis à une vérification adversariale indépendante avant correction) :
17 défauts réels confirmés et corrigés. **Mise à jour recommandée à tous les
utilisateurs de la 0.9-beta4**, qui contient les deux défauts critiques
ci-dessous.

### Sécurité
- **Critique — fuite du jeton d'écriture et des identifiants** : la liste noire des fichiers jamais servis (`.auth_token`, `.server_config.json`, log complet…) filtrait l'URL demandée au lieu du fichier réellement atteint. Un simple slash final (`/.auth_token/`), un `%2F` ou un détour par `..` la contournaient et renvoyaient le contenu en clair. Ces routes étant servies avant toute authentification et le serveur écoutant sur le réseau local, n'importe quel appareil du LAN pouvait récupérer le jeton d'écriture partagé — et donc réinitialiser le log, modifier la configuration ou déclencher une mise à jour. La protection par mot de passe optionnelle ne couvrait pas ce chemin.
- **Injection de code sans authentification** : la version déclarée par un poste voisin (`/log/list?ver=`, route sans jeton) était réinjectée sans échappement dans la CHECKLIST d'avant-concours. Un appareil du réseau pouvait ainsi faire exécuter son propre JavaScript dans l'onglet d'un opérateur authentifié. Corrigé par un double verrou (échappement côté client + filtrage de la valeur avant stockage côté serveur).

### Corrigé
- **Critique — corruption silencieuse du carnet (Cloud Sync `full`)** : la fusion était purement additive. Un QSO supprimé réapparaissait au cycle de synchronisation suivant (suppression définitivement impossible), et corriger un QSO recréait son ancienne version en doublon. Corrigé par des marqueurs de suppression persistants, qui propagent la suppression au lieu de l'annuler.
- **Numéro de série faux en concours** : l'allocation ignorait la portée du concours actif et repartait du plus grand numéro de tout l'historique de la bande — le premier QSO d'un nouveau concours pouvait recevoir 801 au lieu de 001, échange erroné transmis sur l'air puis enregistré, sans recours possible.
- **Mise à jour Windows impossible dès qu'un accent figure dans le chemin** (`C:\Users\Frédéric\…`) : le script d'installation était écrit dans un encodage que `cmd` ne lit pas, l'application s'arrêtait sans jamais redémarrer ni signaler d'erreur, et reproposait indéfiniment la même mise à jour.
- **QSO importés invisibles pour les autres postes** : sur un import ADIF, le marquage de version se faisait hors du verrou du log ; un poste qui interrogeait le serveur au mauvais moment n'apprenait jamais l'existence de ces QSO.
- Blocage du serveur jusqu'à 21 s (mesuré) sur un dossier Cloud Sync injoignable, sondé toutes les 20 s par toutes les pages.
- Sauvegarde la plus récente supprimée immédiatement après un changement d'indicatif (tri des fichiers par nom au lieu de la date).
- Copie de la base de données sans verrou lors des sauvegardes (instantané potentiellement corrompu) et écritures de sauvegarde non atomiques.
- Assistant « Nouveau concours » invisible et deux boutons sans effet dans sa bannière (régression de la refonte de la page CONFIGURATION).
- Mise à jour réseau : un poste se découvrait lui-même comme passerelle, masquant les passerelles réelles ; un pair d'une autre plateforme était proposé puis rejeté après téléchargement complet ; la référence d'intégrité ne survivait pas à un redémarrage.
- Alerte « versions différentes » fantôme après le départ d'un poste, et synchronisation différentielle qui retransmettait presque tout le log après chaque redémarrage.

## [0.9-beta4] - 2026-07-25

### Ajouté
- Mise à jour réseau résiliente en DXpédition/multi-op : relais passerelle (un poste avec internet relaie l'authentique contenu GitHub) en priorité, relais pair-à-pair (un poste sert un exécutable déjà téléchargé et vérifié) en secours strict uniquement si aucune passerelle n'est disponible — vérification SHA-256 systématique contre une référence obtenue directement de GitHub, jamais du pair/de la passerelle.
- Affichage de la version logicielle de chaque poste connecté en réseau multi-op, avec alerte visuelle si un poste est resté sur une version différente.
- Indicateur de dégradation réseau (callbook, solaire, Cloud Sync) dans la barre de statut, au lieu d'une dégradation silencieuse visible seulement en console.
- CWops (CWT) et les 2 éditions UFT (été/hiver) ajoutés aux concours suivis.
- Réseau de balises NCDXF/IBP rendu découvrable depuis toutes les pages (il était déjà présent mais peu visible).

### Corrigé
- Dérive du schéma de définition des concours vis-à-vis de la réalité (CQ WW/CQ WPX, World Wide Award) qui faisait échouer silencieusement la validation en CI.
- CI GitHub Actions « Check LogX AI » cassée par un clone git superficiel incompatible avec les tests de non-régression qui rejouent un ancien commit.
- Flakes pytest intermittents (test HTTP sans fermeture explicite de serveur, chemin de dossier invalide non portable sous Linux).
- Alerte Cloud Sync fantôme qui pouvait rester affichée après correction du dossier.

### Sécurité
- 3 défauts trouvés en revue adversariale sur le nouveau mécanisme de mise à jour réseau, corrigés avant publication : verrou de vérification d'intégrité absent juste avant le remplacement de l'exécutable, SSRF possible via le champ IP fourni par le client (requêtes serveur sortantes forcées vers une cible arbitraire), priorité passerelle-avant-pair non appliquée côté serveur (seulement une convention d'interface).

## [0.9-beta3] - 2026-07-24

### Ajouté
- CONFIG : les bandes et modes proposés pour un concours sélectionné reflètent désormais le vrai règlement serveur (calendrier + définitions), plus un objet client dupliqué à la main qui pouvait dériver.
- DXHeat ajouté comme 6e source cluster HF+VHF/UHF, avec locator structuré (plus fiable qu'un regex sur commentaire).
- Carte MUF mondiale graphique en direct (hamqsl.com) sur la page Propagation et en vignette sur l'écran mural.
- Carte de foudre en direct (Blitzortung.org) intégrée à la page Propagation + lien depuis l'écran mural.
- Fuseaux horaires DX de référence sur l'écran mural, au-delà d'UTC et de l'heure locale.
- Sélecteur de dossier natif Windows pour la sauvegarde automatique (CONFIG).
- Raccourci bureau proposé au premier lancement de l'exécutable figé.

### Modifié
- Décodeur CW : suppression d'un panneau en double qui cassait silencieusement le bouton, et correction de l'affichage qui pouvait cacher l'enregistreur de QSO.
- Traductions complétées (dont le bouton « ENREGISTRER LE QSO », resté en français dans toutes les langues) et corrections structurelles du moteur i18n pour le texte généré dynamiquement.

### Corrigé
- 4 défauts de revue adversariale sur les filtres bandes/modes (les deux axes doivent être restreints indépendamment) et sur les spots DXHeat (priorité du locator structuré, doublons entre les lots HF et VHF/UHF).
- Cache de calendrier externe retiré du suivi git (régénéré automatiquement, n'avait jamais dû être versionné) + bouton « SANS DUPES » qui ne se traduisait jamais.

## [0.9-beta2] - 2026-07-24

### Ajouté
- World Wide Award (hamaward.cloud) : nouveau concours avec roster de stations spéciales et scoring dédié.
- Auto-spot SOTA sur le cluster + push temps réel vers QRZ Logbook.
- Auto-spot POTA (bouton « Se spotter », POST vers api.pota.app).
- IOTA : spots en direct extraits des commentaires du cluster DX existant.
- WCA : géocodage de la référence activée pour donner une position au château sur la carte.
- flrig comme 4e backend de pilotage CAT (XML-RPC), aux côtés du natif/TCI/rigctld.
- Bandmap waterfall (canvas), scans QSL papier et records DX dans le panneau Diplômes.
- Enregistreur audio par QSO (tampon glissant 2 min, clip 20 s attaché au log).
- QTC (WAE) : saisie détaillée émis/reçu + export Cabrillo.
- Multi-opérateur : compte à rebours de la règle des 10 minutes + vue Partner (saisie en direct).
- Extension du check partiel (SCP) : import MASTER.SCP, vérification N+1, import de fichiers Call History par concours.
- Worked Matrix : panneau détachable, adapté à chaque concours.
- Mécanisme de mise à jour logicielle proposée automatiquement, sans perte de données.
- Mot de passe d'accès optionnel avant remise du jeton d'écriture (rc_token).
- Vraie page de saisie mobile (`logx_mobile.html`) + bannière sur petit écran.
- Build Linux + workflow GitHub Actions multi-plateforme (Windows/macOS/Linux, exécutables attachés à la release).
- Journal d'erreurs local (`sys.excepthook`/`threading.excepthook`) exposé au diagnostic.
- Affichage de la version installée + bouton « Signaler un problème » dans la barre de statut.
- Formulaire d'issue GitHub structuré (`.github/ISSUE_TEMPLATE/bug.yml`) pour les bêta-testeurs non techniques (que faisiez-vous / version / OS / description), issues « vierges » désactivées pour canaliser les retours dedans.
- Ce journal des modifications (`docs/CHANGELOG.md`), au format Keep a Changelog.

### Modifié
- WSJT-X : alerte DXCC/département manquant + publication MQTT optionnelle.
- Parité mobile : scoring calculé côté serveur, n° de série centralisé, file d'attente hors ligne.
- Compression gzip + synchronisation différentielle de `/log/list` (ne retransmet que les QSO modifiés).
- Le thème jour/nuit se partage désormais entre postes (lien multi-poste).
- Fenêtre de rendu limitée pour les gros logs dans le logbook (300 lignes + bouton « Afficher plus »).
- Les artefacts de release Windows/macOS/Linux embarquent désormais le tag de version dans leur nom (ex. `LogXAI-v0.9-beta2.exe`) au lieu d'un nom fixe, pour qu'un testeur avec plusieurs versions en local puisse les distinguer ; la mise à jour automatique (`logx_update.py`) a été adaptée pour retrouver ce nouveau nom.

### Corrigé
- Repli RPH périmé + alerte DX QO-100 basée sur une distance sans tenir compte du sens.
- RBN : repli HTTP si le telnet du port 7000 est bloqué (verdict « aucun » au lieu de rester bloqué).
- Pare-feu Windows qui bloquait l'accès multi-poste (réseau « Public » sans règle de pare-feu).

## [0.9-beta1] - 2026-07-22

Première bêta packagée (Windows/macOS/Linux). Résumé des grands chantiers menés
depuis le premier commit ; voir `git log` pour le détail commit par commit.

### Ajouté
- Moteur de concours générique (barèmes/bandes/dates/échange pilotés par une définition JSON), lu automatiquement à partir d'un règlement PDF ou web via extraction IA vérifiée par une passe adversariale.
- 36 concours intégrés (REF, IARU R1, CQ WW/WPX, ARRL DX/FD, WAE, UBA, Russian DX, All Asian, Stew Perry, ARRL 10/160 m…) + 358 concours mondiaux préparables depuis le calendrier WA7BNM.
- Coach stratégique IA par concours (Run vs Search & Pounce, plan de bande, ouvertures par région) + agent et coach multilingues (8 langues).
- Carnet de log partagé multi-poste (SQLite), dédup des QSO, exports Cabrillo v3 / ADIF 3 / EDI-REG1TEST.
- Carnet permanent : déjà-contacté, diplômes/QSL, band map, tableau de chasse départements avec carte de France qui se colore.
- Callbook en cascade QRZ → HamQTH → HamDB, fiche du correspondant à la saisie, historique d'indicatifs Super Check Partial.
- Base DXCC hors ligne (cty.dat), mise à jour automatique si elle a plus de 30 jours.
- Page PROPAGATION : MUF réelle (ionosondes KC2G), indices solaires, grey-line, tropo/météores/avion, RBN, balises NCDXF/IBP, PSK Reporter, prévision Es/aurore VHF, carte de propagation mondiale 24 h.
- Pilotage radio CAT natif (pyserial), Hamlib rigctld, TCI (SDR type SunSDR/ExpertSDR3), rotor d'antenne (rotctld), amplificateurs HF (Elecraft KPA500/1500, Icom PW-1/PW2, SPE Expert).
- Programmes d'activation POTA / SOTA / IOTA / WWFF, puis ARLHS (phares) et WCA (châteaux), EME (rebond lunaire), moteur générique partagé entre tous ces programmes.
- Bandscope (activité de bande sans matériel SDR) + décodeur CW temps réel (Morse → texte, 100 % navigateur).
- Application mobile installable (PWA), page mobile généralisée multi-concours, utilisable en mobilité ou à domicile.
- Second écran / fenêtres détachables (multi-moniteur), panneaux détachables généralisés avec dispositions nommées, mode expédition (écran mural + Club Log Live).
- Auto-spot (self-spot) sur cluster DX avec la fréquence courante.
- Keyer vocal automatique (callbot) : indicatif et report dits/reçus par la radio.
- Chasse aux DXpeditions (flux RSS public NG3K ADXO) + onglet Calendrier dédié.
- Chasse aux départements français : lookup callbook en direct pour les indicatifs spottés jamais croisés ; coach avec suggestions proactives de pays/départements jamais travaillés.
- Constructeur de règles d'alerte personnalisées ; Cloud Sync multi-poste via dossier synchronisé.
- Réseau ADIF générique (interopérabilité UDP `<contactinfo>` avec d'autres loggers) ; QSO Upload unifié (QRZCQ, HRDLog, ClubLog, eQSL, LoTW).
- Modes d'utilisation (logbook simple / concours / expédition) + mode Radioclub (postes partagés, jusqu'à 40 opérateurs).
- Carte multi-échelle (France / Europe / continent / monde), horloge UTC + heure locale partout.
- Assistant de configuration guidé + annuaire de WebSDR distants.
- Packaging en exécutable autonome Windows/macOS/Linux (PyInstaller), aucune installation de Python requise.
- Guide utilisateur complet et document de promotion (`docs/GUIDE_UTILISATEUR.md`, `docs/LogX_AI_Promotion.md`).
- CI locale (`check.bat`) et GitHub Actions (`check.yml`) : tests pytest + validation des définitions de concours.

### Modifié
- Renommage complet du produit en LogX AI (fichiers, marque, logo, charte de couleur) — auparavant nommé RadioContest AI.
- Refonte de la page CONFIGURATION en hub de catégories + popups, à la place de l'ancien assistant pas-à-pas.
- Refonte lisibilité (tailles de caractères, contraste) et zéro scroll de page sur l'ensemble des écrans.
- Nettoyage du dépôt : seuls le code (`concours/`) et la CI sont suivis par git, purge des fichiers hérités du tout premier commit.

### Corrigé
- Fix critique : perte de données possible en page CONFIGURATION + pilotage rigctld inopérant.
- Fix logbook simple : bandes/modes fiables, doublons hors concours non traités comme erreurs, concours fantôme après expiration.
- Fix lenteur majeure de `/log/list` (verrou du log gardé pendant tout l'envoi réseau).
- Fix mode CONCOURS qui affichait le log de base au lieu du log filtré par portée concours + année.
- Fix HTTPS bloqué par Avast sous Python 3.13 + fiabilisation de l'extraction IA du règlement.
- Corrections issues de plusieurs revues adversariales dédiées (propagation, audit CONFIG H1-H6/M1-M9/B2-B5, sécurité/robustesse/perf).

### Sécurité
- Traversée de répertoire bloquée dans `Handler._resolve()` + liste noire des fichiers sensibles (clé API…) jamais servis.
- Authentification par jeton partagé sur les écritures et l'IA, CORS restreint au réseau local.
- Endpoints `/debug/*` désactivés par défaut ; écritures JSON atomiques et thread-safe.
- Robustesse réseau pour une diffusion publique : plus aucun appel réseau bloquant dans le thread HTTP (QRZ, callbook, cluster, RBN, PSK Reporter, solaire, HRDLog, LoTW, Cloud Sync).
