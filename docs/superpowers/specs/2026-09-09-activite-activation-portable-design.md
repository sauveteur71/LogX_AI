# Design — Activité « LOG activation portable (POTA/SOTA/XOTA) » (A3)

Spec rédigé le 09/09/2026. **Statut : à relire par F4GLD avant tout code.**
Rédigé pendant sa sieste → les décisions de cadrage sont prises par défaut et
**marquées « ⚠️ À CONFIRMER »** ; il valide/corrige au réveil, ensuite seulement
on passe au plan d'implémentation (writing-plans).

> Doctrine appliquée : l'axe = l'ACTIVITÉ ; intuitivité maître mot ; **carnet
> UNIQUE** (l'activité est une VUE, jamais un silo) ; masquer ≠ bloquer.

---

## 1. Objectif

Faire de « l'activation portable » une **activité de premier plan** de l'accueil,
qui pré-câble en un geste tout ce dont un opérateur a besoin pour partir activer
un parc / sommet / château (POTA, SOTA, WWFF, IOTA, WCA, DFCF, WWBOTA, GMA,
ARLHS) **ou** chasser ces activateurs — sans jamais imposer la complexité des
autres domaines (concours, EME…).

## 2. Reframe majeur — presque tout le socle EXISTE déjà

L'exploration du code montre qu'A3 est surtout de **l'unification/UX**, pas du
nouveau backend. Déjà présent et fonctionnel :

- **Rôle de session XOTA** `chasse` / `portable` / `mixte` — `logx_xota_role.js`
  (`window.LogxXotaRole`, persisté `localStorage.logx_xota_role`), déjà affiché
  en tuiles sur l'accueil (`logx_accueil.js:82-100`) et bascule dans le logbook
  (`logx_activation_ui.js:106-126`).
- **UI d'activation** — `logx_activation_ui.js` : compteurs, points de chasse
  SOTA, exports POTA/SOTA par rôle (`/pota/export_adif`, `/sota/export_adif`,
  `/activation/state`).
- **Carte de sortie PNG hors-ligne** — `logx_xota_carte.js`
  (`window.ouvrirCarteSortie`).
- **Lookup référentiels** (9 programmes) — `logx_ref_info.js`
  (`/activation_db/lookup|search|nearby`).
- **Mode activation dans le logbook** — `applyActivationMode(program,ref)`
  (`logx_logbook.js:454-492`) : barre d'activation, spot, export, champ réf/S2S.
- **Page CHASSE** — `logx_chasse.html` : 5 listes de cibles en direct
  (`/data/spots_ranked`), need-list cluster, DXpéditions NG3K. **A sa propre
  fiche** (ne pas y charger `logx_bandeau_fiche.js`).
- **Serveur** : tous les endpoints XOTA existent (`/activation/*`, `/pota/*`,
  `/sota/*`, `/activation_db/*`, spots).

→ **A3 v1 = relier ces pièces en une activité cohérente**, pas les réécrire.

## 3. Patron « activité » à reproduire (établi par LOG V/UHF)

Une activité se déclare dans `ACTIVITIES` (`logx_accueil.js:24-35`,
`{id,label,hint,icon,pilote?}`) puis se câble par `id` dans 3-4 tables :
`ACTIVITY_DISPLAY_PRESETS` (`logx_statusbar.js:1795`, panneaux montrés/masqués),
bandes par défaut du logbook (`logx_logbook.js:1513-1531`), et — optionnel —
narrowing des concours (`logx_configuration.js:2446-2497`). Persistance
`localStorage.logx_activity` + geste « Reprendre » fournis gratis. Carnet
inchangé (VUE client).

## 4. Décisions de conception

### D1 — Une activité, le rôle en sous-choix ⚠️ À CONFIRMER
Aujourd'hui l'accueil a un duo confus : la grille d'activités **et** des tuiles
de rôle XOTA séparées. Proposition : **une seule entrée d'activité**
`{id:'xota', label:'LOG activation portable', hint:'POTA · SOTA · WWFF · châteaux…'}`.
Le **rôle chasse/portable/mixte devient un sous-choix DANS l'activité** (réutilise
`logx_xota_role.js`), présenté juste après le clic sur la carte — pas une deuxième
grille concurrente. Les tuiles de rôle actuelles de l'accueil sont **repliées**
dans ce flux (rien de supprimé côté logique).
*Alternative si tu préfères : garder les 3 rôles comme 3 cartes d'accueil
distinctes (chasse / activateur / mixte) sans carte « activation » chapeau.*

### D2 — Cockpit d'activité (ce qui s'affiche au choix) ⚠️ À CONFIRMER
Au clic sur l'activité, un **cockpit léger** (pas une nouvelle grosse page) :
- **Rôle** (chasse ▸ portable ▸ mixte) en bascule claire ;
- si **portable/mixte** : champ « ma référence du jour » (lookup `logx_ref_info`)
  + bouton « ouvrir le LOGBOOK en mode activation » (`applyActivationMode`) ;
- si **chasse/mixte** : accès direct à la page **CHASSE** existante (spots en
  direct) — on ne la réécrit pas, on y route ;
- bouton **Carte de sortie** (réutilise `ouvrirCarteSortie`) ;
- **Reprendre** la dernière session (déjà géré par `_pageSuivante`).
*Réutilise au maximum l'existant ; le cockpit est surtout un aiguilleur clair.*

### D3 — Pré-câblage de la VUE logbook ⚠️ À CONFIRMER (surtout les bandes)
Preset d'affichage `xota` dans `ACTIVITY_DISPLAY_PRESETS` : montrer la **barre
d'activation** + **compteurs**, masquer les panneaux concours (soapbox, stats
op, règles). **Bandes portables par défaut** proposées :
`['7','14','21','28','50','144','432']` (déca SSB/CW courant + V/UHF portable).
⚠️ à ajuster selon ta pratique POTA/SOTA réelle. Colonne **Référence** + repère
**S2S/P2P** visibles. Aucune restriction de concours (activité « honnête », pas
de leurre).

### D4 — Chasse ↔ activation ⚠️ À CONFIRMER
La bascule est le **rôle** (`logx_xota_role.js`), surfacée à la fois dans le
cockpit et dans le logbook (bascule existante). Défaut = dernier rôle mémorisé,
sinon `mixte`.

### D5 — Périmètre v1 (incrément) ⚠️ À CONFIRMER
**v1 = unification/UX pure** (déclaration activité + preset + bandes + cockpit
aiguilleur), **zéro nouveau backend**, risque faible, forte valeur d'intuitivité.
Incréments suivants (séparés, à décider plus tard) : « réf du jour »
intelligente (proximité GPS via `/activation_db/nearby`), débrief post-activation
(C2), suggestions IA.

## 5. Architecture / fichiers touchés (v1)

| Fichier | Changement |
|---|---|
| `logx_accueil.js` | entrée `xota` dans `ACTIVITIES` + icône `_ICO`; intégrer le sous-choix de rôle au flux (replier `_renderXotaRoleAccueil`) ; cockpit aiguilleur |
| `logx_accueil.html` | conteneur du cockpit d'activité (si besoin) |
| `logx_statusbar.js` | `ACTIVITY_LABELS.xota` + `ACTIVITY_DISPLAY_PRESETS.xota` |
| `logx_logbook.js` | `_activiteEstXota()` + `XOTA_ACTIVITY_DEFAULT_BANDS`, branchés dans `renderBandButtons()` (même patron que vuhf) |
| `logx_logbook.html` | classe `hf`/`vhf` selon bandes (activité mixte → défaut hf) |
| **Réutilisés SANS modif** | `logx_xota_role.js`, `logx_activation_ui.js`, `logx_xota_carte.js`, `logx_ref_info.js`, `applyActivationMode`, `logx_chasse.html`, tous les endpoints serveur |

Aucun changement serveur en v1. Aucun nouveau fichier obligatoire (peut-être un
petit `logx_activite_xota.js` si le cockpit grossit — à décider au plan).

## 6. Tests (méthode CLAUDE.md : témoin vert + mutation)

- **V8 (py_mini_racer)** : `_activiteEstXota()` renvoie vrai ssi
  `localStorage.logx_activity==='xota'` ; `XOTA_ACTIVITY_DEFAULT_BANDS` utilisées
  en repli quand aucun concours ne restreint ; le preset `xota` bascule bien les
  panneaux attendus (mannequin → assertion structurelle côté fonction réelle).
- **Statique** : l'entrée `xota` existe dans `ACTIVITIES` ; le cockpit route vers
  logbook (portable) et CHASSE (chasse).
- **Non-régression** : les activités existantes (`vuhf`, `normal`…) inchangées ;
  relancer la famille `test_accueil*`, `test_activation*`, `test_logbook_band_picker*`.

## 7. Garde-fous (doctrine)

- Carnet **unique** : `xota` n'est jamais un filtre de données serveur, juste une
  VUE client (comme `vuhf`).
- **Masquer ≠ bloquer** : tout reste accessible en changeant d'activité.
- **Émission** : aucune fonction TX touchée en v1 (spots = annonces, pas TX).
  Si un incrément futur ajoute un « spot self » qui déclenche une émission,
  charger `tx-human-consent` AVANT.
- Intuitivité : un débutant qui clique « activation portable » doit comprendre en
  un coup d'œil « je pars activer » vs « je chasse » et démarrer sans réglage.

## 8. Questions ouvertes pour F4GLD (à trancher au réveil)

1. **D1** : activité chapeau + sous-choix rôle, OU 3 cartes de rôle distinctes ?
2. **D3** : les **bandes portables par défaut** — ma liste te convient-elle, ou
   tu en veux d'autres (ex. WARC 10/18/24 MHz, 6 m prioritaire) ?
3. **D2** : le cockpit doit-il router vers la page **CHASSE existante**, ou tu
   veux à terme fusionner CHASSE dans l'activité (plus gros, incrément séparé) ?
4. **D5** : v1 = unification pure te va, ou tu veux embarquer la « réf du jour par
   proximité GPS » dès le premier incrément ?
