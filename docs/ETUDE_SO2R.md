# Étude : SO2R (Single Operator 2 Radios) pour LogX AI

Synthèse de 4 recherches (domaine général SO2R, matériel d'interlock,
audit du CAT existant, audit audio/keyer existant) en un plan
d'implémentation phasé. Objectif : décider QUOI construire, dans quel
ordre, et où s'arrête la responsabilité du logiciel — pas un résumé des
recherches, un plan d'action.

---

## 1. Le SO2R en 3 phrases

Le SO2R, c'est un seul opérateur qui pilote deux transceivers reliés à
deux antennes séparées, avec un seul clavier/interface de log, pour
réduire les temps morts : pendant qu'une radio tient un CQ (« Run »),
l'opérateur explore l'autre bande à la recherche de nouveaux contacts
(« Search & Pounce ») sur la seconde radio. Ce n'est **jamais** une
émission simultanée sur les deux radios — les règlements de concours
(CQ WW : *« Only one transmitted signal is permitted at any time »*)
l'interdisent formellement en catégorie Single Operator — c'est une
technique d'**écoute double avec bascule rapide et exclusive de
l'émission**. La bascule (quelle radio reçoit les frappes clavier, les
macros, et vers laquelle le PTT logique est armé) se fait par raccourci
clavier, pédale, clic, ou automatiquement selon l'état TX — jamais par
un vrai double PTT.

---

## 2. Logiciel vs matériel — la limite de responsabilité

C'est le point de sécurité le plus important de ce document. Deux
risques bien distincts existent en SO2R, et **un seul des deux peut être
traité en logiciel** :

**(a) Non-conformité réglementaire — double émission.** Un logiciel qui
laisse les deux PTT actifs en même temps produit un log disqualifiable.
C'est un risque qu'un logiciel PEUT réduire : un verrou logiciel simple
(« seule la radio qui a le focus TX peut émettre, l'autre est refusée
tant que la première est active ») suffit à traiter ce cas — c'est
exactement ce que font N1MM+ (« First One Wins »/« Last One Wins »),
Win-Test et DXLog.net.

**(b) Dégât ou désensibilisation du récepteur voisin.** Même quand une
seule radio émet à la fois (donc conforme au règlement), le récepteur de
l'**autre** radio reste exposé à l'énergie RF de l'antenne voisine si les
bandes/antennes sont proches. La recherche de domaine est catégorique
là-dessus : c'est *« quite easy to damage a receiver with just a 100W
transmitter if some precautions are not taken »*, et aucune des trois
recherches consultées (dont l'audit matériel dédié) n'a trouvé un seul
mécanisme purement logiciel qui traite ce risque. C'est une limite
physique — de l'énergie RF réelle sur une antenne réelle — pas une
limite d'ingénierie logicielle contournable à coup de code.

**Ce que ça donne concrètement pour LogX AI :**

| Couche | Responsabilité | LogX AI peut le faire |
|---|---|---|
| Focus clavier, macros CW/phonie par radio | Logiciel | Oui — c'est le cœur du chantier |
| PTT logique exclusif (empêcher un 2e ordre TX pendant que le 1er est actif) | Logiciel | Oui, mais comme garde-fou explicite documenté comme **plus faible** qu'un interlock matériel — jamais présenté comme équivalent |
| Routage audio physique (répartition casque stéréo, commutation micro) | Matériel dédié (ou 2 cartes son + config OS) | Partiel — voir Phase 2 |
| Interlock RF (empêcher physiquement, au niveau relais, un double PTT même en cas de bug logiciel) | **Matériel exclusivement** | **Non** — LogX AI ne doit jamais prétendre le remplacer |
| Protection anti hot-switching (relais d'antenne, étage final) | **Matériel exclusivement** | **Non** |
| Filtres passe-bande (désensibilisation/dégât récepteur voisin) | **Matériel exclusivement**, qualifiés « quasi obligatoires » en usage sérieux par la communauté | **Non** |

Toute doc utilisateur produite pour ce chantier devra répéter cette
limite en clair : un verrou logiciel LogX AI réduit le risque (a), il ne
protège **pas** le matériel contre (b). C'est la même prudence déjà
appliquée dans ce projet aux protocoles CAT propriétaires non documentés
(ACOM laissé en attente faute de source — voir §5) : ne jamais faire
croire au matériel une garantie que le logiciel seul ne peut pas tenir.

---

## 3. État actuel de LogX AI vis-à-vis du SO2R

### Ce qui EXISTE déjà et est réutilisable

Le SO2R n'est pas un vide architectural — un module dédié existe et une
partie du dispatch HTTP le respecte déjà :

- **`concours/logx_so2r.py`** : focus radio 1/2 tenu côté serveur
  (`_focus`, module-level), `cle_radio_active()` et
  `config_radio_active(cfg)` qui présentent les clés `cat2_*` sous les
  noms `cat_*` pour la radio qui a le focus — les backends CAT n'ont pas
  besoin de savoir qu'il existe une radio 2. Endpoints `/so2r/focus` et
  `/so2r/state`.
- **4 endpoints déjà focus-aware** : `/rig/qsy`, `/rig/cw`, `/rig/stop`
  et `/rig/ptt` (`logx_http.py`, lignes ~5296 et ~5441) appellent bien
  `so2r.config_radio_active(self._cfg_snapshot())` avant de piloter la
  radio — les macros F1-F8 et le PTT manuel fonctionnent déjà en SO2R.
- **Côté client** : `logx_logbook.js` a déjà un état de focus
  (`_so2rFocus`), un indicateur visible (`#so2rIndicateur`) et un
  raccourci clavier dédié **Ctrl+Espace** (`so2rBasculer()`) — le
  mécanisme de bascule que ce chantier aurait dû inventer existe déjà et
  n'est pas à reconstruire.
- **OmniRig n'a aucune connexion persistante** (`logx_omnirig.py`) :
  chaque appel HTTP redispatche un objet COM frais vers `Rig1` ou
  `Rig2`. Contrairement au CAT natif, rien n'empêche mécaniquement
  d'adresser les deux radios en alternance rapide — c'est la voie la
  moins coûteuse vers un vrai SO2R à deux connexions simultanées (détail
  en §4, Phase MVP).
- **`class RigManager`** (`logx_cat.py`, ~lignes 1552-1584) : un vrai
  registre `radio_id -> connexion` est déjà écrit, avec un commentaire
  explicite le présentant comme la « brique de base d'un futur mode
  SO2R » — mais il est **mort** : jamais importé ni appelé par
  `logx_http.py`, seulement exercé isolément par
  `tests/test_cat.py:test_rig_manager_multi_radio`. C'est une fondation
  posée, pas branchée.
- **Le verrou par-instance de `SerialPort`** (`logx_cat.py`, docstring
  ~1078-1081) est déjà pensé SO2R : « un port = un verrou, pas de verrou
  global : plusieurs radios sur des ports différents fonctionnent en
  parallèle. » Le vrai blocage n'est pas ce verrou (voir ci-dessous).
- **`CwAudioDecoder`** (`logx_cwdecoder.js`) et `play_wav(path,
  device_index)` (`logx_voicekeyer.py`) sont déjà réentrants/paramétrés
  par appel — la plomberie technique pour deux flux audio distincts
  existe, seul le branchement UI (singleton) manque.

### Ce qui suppose structurellement une seule radio, et devra changer

- **CAT natif série = singleton.** `_persistent['default']`
  (`logx_cat.py`, ~1287-1320) ne tient qu'**un seul** emplacement de
  connexion, fermé puis rouvert à chaque changement de config. Résultat
  concret : basculer le focus SO2R en CAT natif ferme la connexion à la
  radio qui perd le focus — **écouter la radio 2 pendant qu'on tient un
  CQ sur la radio 1, le cas d'usage central du SO2R, est aujourd'hui
  impossible en CAT natif**, pas par prudence voulue mais parce que le
  registre multi-radio (`RigManager`) n'est pas branché.
- **Deux trous de cohérence dans le dispatch focus** (des bugs, pas des
  limites structurelles) : `/rig/voice` (keyer vocal CQ/RAPPORT/73),
  `/voice/play` (messages DVK), `/rig/state`, `/hardware/state`,
  `/rig/scope_*` et `/rig/tci_spectrum_*` (panadapter) utilisent tous
  `self._cfg_snapshot()` **brut**, sans passer par
  `so2r.config_radio_active()` — contrairement à QSY/CW/STOP/PTT. En
  clair : après Ctrl+Espace vers la radio 2, le CQ vocal automatique
  continue de parler vers la radio 1, et le champ FRÉQUENCE/band map
  affiché reste celui de la radio 1 même si le pilotage réel a basculé.
- **OmniRig n'est pas raccordé au focus.** `omnirig_rig_num` ne figure
  pas dans la liste (fermée) des clés remappées par
  `config_radio_active()` — même configuré en OmniRig, la radio 2
  utiliserait toujours le même `rig_num` que la radio 1. L'UI CONFIG
  interdit même déjà ce cas : `logx_configuration.html` fige en dur
  `cat2_mode: 'native'` pour la radio 2, aucune autre valeur possible.
- **`voicekeyer_device` est une clé unique**, pas de
  `voicekeyer_device2` — contrairement au CAT radio 2 (`cat2_*`), le
  keyer vocal n'a jamais eu de second jeu de paramètres prévu.
- **`rigState` côté client est un objet global unique**, pas un tableau
  indexé par radio — même une fois le backend corrigé, l'UI ne peut
  afficher qu'un état à la fois, jamais les deux radios en parallèle.
- **Le formulaire SAISIE QSO est structurellement unique** : aucun
  attribut `data-radio`, aucune boucle de template, aucune trace d'une
  seconde colonne anticipée. Un vrai double panneau de saisie serait un
  chantier neuf.
- **Aucun verrou logiciel d'exclusivité TX n'existe.** Le focus contrôle
  le *routage* (vers quelle radio la commande part), mais rien
  n'empêche aujourd'hui, une fois deux connexions simultanées ouvertes
  (ce qui n'est pas encore possible, d'où le point précédent), d'armer
  un PTT sur la radio 2 pendant que la radio 1 est encore en train
  d'émettre. C'est un vrai manque à combler **avant** d'activer tout
  pilotage réellement simultané — voir Phase 0 ci-dessous.
- **Multi-poste (radioclub) n'est pas un modèle réutilisable pour le
  SO2R.** Le multi-poste (`logx_mysql_sync.py`) est multi-**process** :
  chaque poste est une instance LogX AI complète et autonome,
  synchronisée de façon asynchrone. Le SO2R est un seul process, deux
  radios, dans le même serveur — deux architectures différentes, à ne
  pas confondre en conception.

---

## 4. Plan d'implémentation phasé

Chaque phase précise ce qui est livré, les fichiers concernés, et les
risques — en particulier tout ce qui touche à la sécurité d'un vrai
matériel radio.

### Phase 0 — Fiabiliser le focus existant (prérequis, pas de nouvelle radio pilotée en parallèle)

**Livré :** le mécanisme de focus déjà écrit (`logx_so2r.py`) devient
honnête sur *tout* le pilotage, pas seulement CW/QSY/PTT manuel — plus
aucun endpoint ne peut afficher ou piloter la mauvaise radio après une
bascule. Un verrou logiciel d'exclusivité TX explicite est introduit
(équivalent du « First/Last One Wins » de N1MM+).

**Fichiers :**
- `concours/logx_http.py` : appliquer `so2r.config_radio_active()` aux
  endpoints qui l'ignorent encore (`/rig/voice`, `/voice/play`,
  `/rig/state`, `/hardware/state`, `/rig/scope_available`,
  `/rig/scope_line`, `/rig/tci_spectrum_available`,
  `/rig/tci_spectrum_line`) — même motif que les 4 endpoints déjà
  corrects, appliqué aux 8 restants.
- `concours/logx_so2r.py` : nouvel état serveur « radio actuellement en
  train d'émettre » (posé à l'armement PTT/CW/voix, levé à la fin ou par
  un timeout de sécurité), consulté avant tout nouvel ordre d'émission
  vers l'autre radio.
- `concours/tests/test_so2r.py` : un test par endpoint corrigé (éviter
  la régression silencieuse déjà documentée ailleurs dans ce projet pour
  ce type d'oubli), plus un test dédié du verrou TX
  (« PTT radio1 actif → tentative PTT radio2 refusée »).

**Risques :**
- Calibrer le timeout du verrou est le seul vrai risque de cette
  phase : trop court, il coupe un CQ vocal légitime en cours ; trop
  long, il bloque l'opérateur si la radio focus reste « collée » en
  émission après une erreur (radio déconnectée, plantage). À caler sur
  les durées réelles déjà connues du keyer vocal/CW plutôt qu'une
  valeur arbitraire.
- Aucun risque matériel nouveau à ce stade — aucune radio
  supplémentaire n'est pilotée en parallèle, c'est un travail de mise en
  cohérence pure.

### Phase 1 (MVP) — SO2R logiciel seul, via OmniRig, sans boîtier dédié

**Livré :** un opérateur peut pour la première fois écouter/QSY la
radio 2 pendant que la radio 1 tient un CQ — le cas d'usage central du
SO2R — sans aucun matériel dédié, en configurant la radio 2 en OmniRig
(backend déjà sans connexion persistante, donc sans le verrou singleton
qui bloque le CAT natif). Bascule clavier Ctrl+Espace déjà existante,
verrou TX de la Phase 0 actif.

**Fichiers :**
- `concours/logx_so2r.py` : ajouter `omnirig_rig_num` (et son pendant
  radio 2) à la liste fermée des clés remappées par
  `config_radio_active()`.
- `concours/logx_configuration.html` : retirer le `cat2_mode: 'native'`
  codé en dur, autoriser `'omnirig'` comme mode radio 2 dans l'UI
  CONFIG.
- `concours/tests/test_so2r.py` : étendre au-delà du seul couple
  native/native testé aujourd'hui (natif/OmniRig, OmniRig/OmniRig).
- Documentation utilisateur (nouveau paragraphe, `docs/GUIDE_UTILISATEUR.md`
  ou équivalent) : avertissement explicite — pas d'interlock matériel,
  pas de protection contre la désensibilisation, filtres passe-bande à
  la charge de l'opérateur si puissance/antennes proches.

**Ce qui N'EST PAS livré en MVP (limite assumée, à documenter) :**
pas de second panneau de saisie QSO, pas d'écoute stéréo, pas de CAT
natif dual (radio 2 doit être OmniRig tant que `RigManager` n'est pas
branché — Phase 3).

**Risques :**
- **C'est la première phase où deux radios sont réellement adressables
  en parallèle** — le verrou TX de la Phase 0 devient pour la première
  fois sollicité en conditions réelles. Ne pas livrer cette phase sans
  avoir explicitement testé le scénario « PTT radio1 actif + tentative
  PTT radio2 » avant mise à disposition utilisateur.
- `_EXECUTOR` d'OmniRig est un `ThreadPoolExecutor(max_workers=1)`
  **partagé** entre les deux `rig_num` — les appels Rig1/Rig2 sont
  sérialisés dans le temps. C'est une limite de débit (latence en
  S&P rapide), pas un défaut de sécurité — à ne pas confondre avec le
  verrou d'exclusivité TX, qui lui est un mécanisme volontaire.
- Avertissement UI obligatoire dès cette phase (cf. §2 et §5) : aucune
  garantie matérielle n'existe, le logiciel seul ne protège que contre
  le risque réglementaire (double émission), jamais contre la
  désensibilisation/dégât récepteur.

### Phase 2 — Audio SO2R (écoute stéréo, décodeur CW et panadapter par radio)

**Livré :** périphérique de sortie voix distinct par radio, décodeur CW
et panadapter capables de viser une radio ou l'autre (au minimum
suivant le focus, idéalement en parallèle), écoute stéréo casque
optionnelle (radio 1 dans une oreille, radio 2 dans l'autre).

**Fichiers :**
- `concours/logx_voicekeyer.py` / `logx_configuration.html` : ajouter
  `voicekeyer_device2` (la fonction bas niveau `play_wav(path,
  device_index)` accepte déjà un device par appel — seul le
  branchement config manque).
- `concours/logx_cwdecoder.js` / `logx_logbook.js` : permettre une
  seconde instance de `CwAudioDecoder` (déjà réentrante) ciblant l'autre
  radio, au lieu du singleton `_cwAudioDecoder` actuel *(fait, puis
  refactoré : les deux instances vivent désormais dans la classe
  `CwPanel` de `concours/logx_cw_panel.js`, pilote EV-7 — le nom
  `_cwAudioDecoder` n'existe plus dans le code)*.
- `concours/logx_panadapter.html` / `logx_http.py` : les endpoints
  scope/spectrum devront accepter un paramètre radio explicite si
  l'affichage simultané des deux spectres est visé — sinon rester
  « le panadapter suit le focus » (limite acceptée, à trancher en §6).

**Risques :**
- Aucun risque d'émission direct (c'est un pipeline de réception) —
  **mais** attention à ne pas laisser diverger le device audio réglé
  sur une radio et le focus TX resté sur l'autre : les loggers de
  référence distinguent une bascule RX-seule d'une bascule TX+RX
  (ex. N1MM+ : `\` bascule RX seul, `Pause` bascule TX+RX ensemble) —
  reproduire cette distinction explicitement dans l'UX Ctrl+Espace de
  LogX AI, pour qu'un opérateur ne croie jamais parler dans le micro de
  la radio qu'il croit avoir sélectionnée.

### Phase 3 — CAT natif dual et/ou intégration matérielle ouverte (OTRSP)

**Livré :** deux connexions CAT natives simultanées (en branchant
`RigManager`, déjà écrit, à la place du singleton `_persistent`),
et/ou support du protocole ouvert OTRSP pour dialoguer avec un vrai
boîtier d'interlock externe.

**Fichiers :**
- `concours/logx_cat.py` : remplacer `_persistent`/`_ensure_connected()`
  par un usage réel de `RigManager` — le verrou par-instance de
  `SerialPort` est déjà prêt, rien à changer de ce côté.
- Nouveau module `concours/logx_otrsp.py` (si la recommandation §5 est
  suivie) : protocole OTRSP (série 9600 bauds, trames RX1/RX2/TX1/TX2,
  ligne DSR pour le PTT) pour piloter un boîtier externe compatible
  (YCCC SO2R Box, SO2Rduino, ou tout autre boîtier OTRSP).
- `concours/tests/test_cat.py` : `test_rig_manager_multi_radio`
  (existant, aujourd'hui isolé) devient un vrai test d'intégration.

**Risques — c'est la phase la plus sensible du chantier :**
- C'est la première fois que le code natif pilote **réellement** deux
  radios physiques en parallèle sans réseau de sécurité matériel connu
  par LogX AI (sauf si l'utilisateur a effectivement câblé un boîtier
  OTRSP). Exiger une revue adversariale dédiée avant fusion, comme pour
  les autres chantiers CAT propriétaires du projet — avec un scénario
  explicite « les deux PTT ne sont jamais actifs en même temps » rejoué
  en conditions dégradées (perte de port série, timeout, redémarrage
  radio pendant une émission).
- Si intégration OTRSP : LogX AI n'a pas de boîtier physique pour
  tester en interne — prévoir une validation par un contributeur/
  bêta-testeur possédant du vrai matériel avant de documenter le
  support comme « validé » plutôt que « implémenté selon la spec ».

### Phase 4 (optionnelle) — Affichage double radio, second panneau de saisie

**Livré :** `rigState` devient un état par radio côté client (plus un
singleton), affichage simultané des deux radios, éventuellement un
second panneau de saisie QSO.

**Fichiers :** `concours/logx_logbook.js`, `concours/logx_logbook.html`.

**Risques :** purement UI/ergonomie, aucun risque matériel nouveau si
les phases 0-3 sont solides. Risque principal = dette frontend — ce
chantier bénéficierait d'attendre le refactor frontend déjà planifié
(EV-7 du PRD), exactement comme EV-5 (layouts) l'attend déjà.

---

## 5. Recommandation : logiciel seul, ou intégration matérielle d'emblée ?

**Recommandation : viser d'abord un SO2R « logiciel seul » (Phases 0-2),
avec des garde-fous stricts et des avertissements explicites — pas une
intégration matérielle d'emblée.** Justification, appuyée sur les faits
trouvés :

1. **C'est la voie la moins coûteuse et déjà amorcée.** L'audit du CAT
   existant montre qu'OmniRig n'a aucune connexion persistante à
   protéger — contrairement au CAT natif (singleton), rien n'y bloque
   structurellement un pilotage à deux radios. Deux corrections ciblées
   (remap `omnirig_rig_num`, retrait d'un verrou UI codé en dur)
   suffisent à débloquer le cas d'usage central du SO2R, contre une
   réécriture du pipeline de connexion pour le CAT natif.
2. **Les trois loggers de référence étudiés (N1MM+, Win-Test, DXLog.net)
   proposent tous un mode SO2R logiciel-seul fonctionnel** (config « Two
   Soundcards Mono » chez N1MM+, OTRSP en « software only » via port
   virtuel) — ce n'est pas une impasse théorique, c'est une
   configuration reconnue et documentée par la communauté contest,
   suffisante pour l'ergonomie (bascule rapide, macros par radio, écoute
   stéréo).
3. **Mais aucun des trois ne prétend que ce mode remplace un interlock
   matériel** pour un usage sérieux (puissance HF réelle, antennes
   proches) — Win-Test délègue explicitement la gestion temps réel à un
   contrôleur externe en mode Advanced SO2R, et N1MM+ documente
   lui-même son verrou logiciel comme moins fiable qu'un interlock
   matériel. LogX AI doit tenir exactement le même discours : le
   logiciel seul convient à un usage occasionnel/faible puissance avec
   antennes déjà isolées, pas à une station de concours haute puissance
   sans filtres passe-bande.
4. **Si/quand une intégration matérielle est visée (Phase 3), le
   candidat est OTRSP, pas microHAM.** OTRSP est un protocole ouvert
   (licence Creative Commons), déjà adopté nativement par les trois
   loggers de référence (N1MM+ ≥ 9.8.5, Win-Test ≥ 4.4, DXLog.net), avec
   un écosystème matériel ouvert pour prototyper sans achat coûteux
   (SO2Rduino, open source). microHAM, à l'inverse, documente un
   protocole SO2R réel dans ses manuels (Appendix B du MK2R) mais reste
   **propriétaire et non standardisé publiquement** — l'audit matériel
   n'a trouvé aucune spécification ouverte du dialogue bas niveau entre
   le logiciel Router et le boîtier lui-même. Ce choix est cohérent avec
   la pratique déjà établie dans ce projet : ACOM a été explicitement
   laissé en attente (#168) faute de protocole documenté publiquement —
   le même standard doit s'appliquer ici plutôt que de reverse-engineer
   microHAM.
5. **Le risque (b) de §2 (désensibilisation/dégât récepteur) reste hors
   de portée logicielle quelle que soit la phase.** Même la Phase 3
   avec OTRSP ne fait que piloter un boîtier — les filtres passe-bande
   restent un achat/câblage à la charge de l'opérateur, jamais une
   fonctionnalité LogX AI peut fournir. Ce point doit rester visible
   dans la doc utilisateur à chaque phase, pas seulement au lancement du
   chantier.

En résumé : MVP logiciel-seul d'abord (valeur immédiate, coût faible,
risque contenu par le verrou TX de la Phase 0), OTRSP comme cible
matérielle si/quand F4GLD veut aller plus loin — jamais microHAM comme
cible principale faute de protocole ouvert, et jamais de discours
laissant croire qu'un verrou logiciel protège le matériel.

---

## 6. Questions ouvertes (à trancher par F4GLD avant le code)

- **Point d'entrée** : démarrer directement sur la Phase 0 (fiabilisation
  du focus existant) + Phase 1 (MVP OmniRig), ou une validation
  intermédiaire est-elle souhaitée avant d'ouvrir la Phase 1 à des
  utilisateurs bêta ?
- **Calibrage du verrou TX (Phase 0)** : quelle durée de timeout de
  sécurité avant déblocage forcé d'un PTT resté « collé » — à caler sur
  les durées réelles du keyer vocal/CW, mais la valeur exacte reste à
  choisir ?
- **Filtres passe-bande** : LogX AI doit-il se contenter d'un texte
  d'avertissement statique dans la doc/UI CONFIG SO2R, ou faut-il un
  champ déclaratif (« je confirme disposer de filtres passe-bande »)
  avant d'activer le mode SO2R — sachant que LogX AI ne peut rien
  vérifier physiquement dans les deux cas ?
- **Écoute stéréo (Phase 2)** : périmètre visé — deux cartes son
  distinctes gérées nativement par l'OS (comme N1MM+ « Two Soundcards
  Mono »), ou dépendance à un mixeur/périphérique externe explicitement
  documentée comme non gérée par LogX AI ?
- **Priorité Phase 3** : CAT natif dual (brancher `RigManager`) et
  intégration OTRSP sont-ils visés en parallèle, ou l'un doit-il
  précéder l'autre ? Le CAT natif dual n'a pas besoin de matériel externe
  pour être livré (juste deux ports série), contrairement à OTRSP qui
  suppose un boîtier réel pour validation.
- **Boîtier à nommer dans la doc** : rester générique
  (« tout boîtier compatible OTRSP ») ou recommander nommément un
  produit (YCCC SO2R Box, SO2Rduino en test communautaire, PIEXX
  SO2RXlate) une fois la Phase 3 engagée ?
- **Second panneau de saisie (Phase 4)** : vaut-il d'attendre le
  refactor frontend (EV-7 du PRD), comme EV-5 (layouts) l'attend déjà,
  ou ce chantier est-il jugé assez isolé pour avancer indépendamment ?
- **Bêta-test matériel réel (Phase 3)** : F4GLD ou un contributeur du
  projet dispose-t-il (ou compte-t-il acquérir) un boîtier OTRSP pour
  valider l'intégration avant diffusion — sans quoi la Phase 3 resterait
  « implémentée selon la spec » sans validation terrain, comme documenté
  dans ce projet pour d'autres protocoles matériels ?

---

## Sources des recherches synthétisées

- **Domaine général SO2R** : [N1MM Logger+ — Single Operator
  Contesting](https://n1mmwp.hamdocs.com/manual-operating/single-operator-contesting/),
  [CQ WW Rules](https://cqww.com/rules.htm), [Win-Test Wiki —
  SO2R/Advanced SO2R](https://docs.win-test.com/wiki/SO2R/Advanced_SO2R),
  [DXLog.net — Menu Operating](https://www.dxlog.net/docs/index.php/Menu_Operating),
  [OTRSP — k1xm.org](https://www.k1xm.org/OTRSP/), [A Survey of Bandpass
  Filters for Contesting](http://audiosystemsgroup.com/BandpassFilterSurvey.pdf).
- **Matériel d'interlock** : [MK2R English Manual
  (PDF)](https://www.microham.com/Downloads/MK2R_English_Manual.pdf),
  [EA4TX Interlock](https://ea4tx.com/en/products-page/ea4tx-interlock/),
  [DX Doubler — eHam review](https://www.eham.net/reviews/detail/1490),
  [SO2Rduino — GitHub](https://github.com/m1dst/SO2Rduino).
- **Audits internes** : lecture directe de `concours/logx_so2r.py`,
  `concours/logx_cat.py`, `concours/logx_omnirig.py`,
  `concours/logx_voicekeyer.py`, `concours/logx_http.py`,
  `concours/logx_configuration.html`, `concours/logx_logbook.js`,
  `concours/logx_cwdecoder.js`, `concours/logx_panadapter.html`,
  `concours/logx_mysql_sync.py` et leurs tests associés dans
  `concours/tests/`.
