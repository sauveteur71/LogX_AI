---
name: chantier-ux-mode-debutant-partout-2026-08-07
description: Mode débutant/expert rendu effectif hors CONFIG — bouton bascule global + audit workflow taguant 24 éléments avancés expert-only dans LOGBOOK/CONFIG
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T14:09:46.668Z
---

Chantier livré et fusionné sur `main` le 07/08/2026 (commit `fea5268`, merge
de `feat/ux-mode-debutant-partout`, commit de contenu `5d4d6a2`).

## Déclencheur

Suite directe de "[[chantier-onboarding-premiere-visite-2026-08-07]]". Après
avoir livré l'écran d'accueil (2 questions), investigation de ce que le choix
"débutant" changeait réellement dans l'app : quasi rien. Le mécanisme
`.expert-only` masqué globalement par `concours/logx_statusbar.js` (sur
`localStorage.rc_ui_mode==='simple'`) existait déjà et s'appliquait sur
TOUTES les pages — mais seulement **4 occurrences** de la classe dans toute
`logx_logbook.html` (macro/pounce/audio-rec/voice), et **son bouton bascule
🎚 n'existait que dans `logx_configuration.html`** — invisible/inatteignable
depuis LOGBOOK où l'utilisateur passe le plus de temps.

Pendant la même conversation, F4GLD a formulé une consigne durable : « si il
y a un maitre mot a mettre en place sur ce logiciel c'est intuitif intuitif
intuitif [...] on ne doit pas pouvoir se perdre tout doit etre ultra logique
malgré tout ce qu'il peut faire » — ajoutée telle quelle dans `CLAUDE.md`
section « Intuitivité — maître mot » (nouvelle règle permanente, transversale
à tout travail UI futur, PAS limitée à ce chantier).

## Méthode — workflow Ultracode (ultracode actif pour ce tour)

3 agents d'audit en parallèle (un par fichier : `logx_logbook.html`,
`logx_logbook.js`, `logx_configuration.html`) → regroupement des constats par
fichier (code, pas agent) → 4 agents de correctif en pipeline (un par fichier,
zéro conflit puisque fichiers disjoints) → 1 agent de tests écrivant les
assertions APRÈS avoir relu réellement les fichiers modifiés. 8 agents, 1M
tokens, ~17 min. Chaque agent recevait la consigne explicite
« masquer ≠ bloquer l'accès » (déjà actée dans le projet) et l'ordre de ne
JAMAIS taguer le chemin critique (indicatif, saisie QSO, bouton
d'enregistrement, avertissement doublon en temps réel).

## Résultat

- **`logx_statusbar.js`** : nouveau bouton 🎚 dans la barre de statut
  partagée (visible sur toutes les pages). Le libellé suit STRICTEMENT
  `rc_ui_mode==='simple'` (comme le masquage réel), PAS l'heuristique
  `getUiMode()` de CONFIG (qui regarde `logx_config.callsign` en l'absence de
  `rc_ui_mode`) — sinon le bouton aurait pu afficher "DÉBUTANT" sur une page
  où rien n'est réellement masqué. Bascule = `location.reload()`, pas de
  réapplication à chaud (fiable même pour les éléments injectés en JS).
- **24 éléments tagués** `expert-only` : SO2R (2e radio, CONFIG + panneau CW
  radio 2), OmniRig/FlexRadio/Icom-réseau, adresse CI-V avancée, filtre
  avancé, recherche de doublons, re-résolution en masse, contrôle de net,
  champs ADIF perso, filtre band map, classement multi-op, audit IA du log,
  Station Control, Auto-lancement, PowerGenius XL, Télémétrie, MySQL partagé,
  MQTT.
- **18 éléments audités et délibérément écartés** (chemin critique, décisions
  bien motivées par les agents) : avertissement doublon en saisie (`#dupWarn`
  — distinct de l'outil dédié `#dupOverlay`, lui tagué), macros CW/vocales/
  RTTY, chat multi-op + sélecteur opérateur (distinct du classement
  `#opStatsBar`, lui tagué), bandeau QTC (WAE, fait partie du barème), score
  principal, mot de passe d'accès réseau (sécurité ≠ complexité), barre de
  profils station.
- **`concours/tests/test_ux_mode_debutant_partout.py`** (25 tests, 40
  assertions) : lecture textuelle réelle des fichiers modifiés, pas de
  DOM/py_mini_racer.

## Vérification navigateur (moi, pas l'agent) — preuve fonctionnelle forte

Pas juste "la classe est posée" : appel JS DIRECT à `openFilterBuilder()` en
mode simple → `getComputedStyle(...).display` reste `'none'` malgré le JS qui
tente `display:flex` (la règle CSS `!important` l'emporte) ; même appel en
mode expert → `'flex'` (contre-épreuve positive, prouve que ce n'est pas
cassé en permanence). `.saisie-form` reste `'flex'` dans les deux modes.

## Pièges/décisions à retenir

- **Duplication du bouton sur CONFIG** : `logx_configuration.html` inclut
  aussi `logx_statusbar.js`, donc CONFIG a maintenant DEUX boutons bascule
  (l'historique en haut de page + le nouveau dans la barre). Redondant mais
  pas trompeur (même fonction, mêmes deux emplacements visuellement
  distincts) — laissé tel quel, pas traité comme un bug.
- **`#bmFiltre` tagué mais son bouton loupe `#spotFiltreBtn` non tagué** :
  clic mort mineur accepté en mode simple (bouton secondaire discret dans la
  barre d'outils du band map) — compromis documenté par l'agent, pas un oubli.
- Les 4 boutons de menu générés en JS (`openFilterBuilder`/`openDupFinder`/
  `openBulkResolve`/`openNetControl`, `itemsMenuLogbook()` dans
  `logx_logbook.js`) devaient être tagués SÉPARÉMENT du conteneur modal HTML
  correspondant (2 fichiers différents) — sinon clic mort (modale déjà
  masquée par `!important` mais bouton menu toujours actif). Fait via un
  `Set` `MENU_LB_EXPERT_ONLY_FN` plutôt que de modifier `itemsMenuLogbook()`
  elle-même, qui est extraite telle quelle par
  `tests/test_logbook_menu_debut_fin.py` (`JSON.stringify(itemsMenuLogbook())`)
  — la modifier aurait cassé ce test existant sans rapport avec ce chantier.
- Aucun régression trouvée sur le reste de la suite pytest (suite complète
  verte, code de sortie 0, avant ET après fusion sur `main`).

## Reliquat volontairement hors scope

- Barre de navigation partagée (`<nav class="app-nav">`, 10 pages) : les
  liens PANADAPTER/FT8/WEBSDR/CARTE IA restent visibles à tous les niveaux —
  scope explicitement exclu de CE lot pour éviter le risque d'édition
  identique-mais-pas-tout-à-fait sur 10 fichiers en parallèle (même piège que
  documenté pour le nav des icônes monochromes : script/agent unique
  nécessaire, pas un audit multi-fichiers). À reprendre en lot séparé si
  jugé utile.
- `.profiles-bar` (CONFIG, sélecteur de profils station) et
  `#hubcard_radio`/`#hubcard_network` (tuiles hub entières) examinés puis
  explicitement écartés — voir raisons détaillées dans les constats
  `no_change_needed` du workflow (accessibles via le journal si besoin).
