---
name: chantier-ev7-rejet-selecteurs-2026-08-09
description: "EV-7 : candidat n°5 du 2e inventaire (Sélecteurs OPÉRATEUR/BANDE/MODE+fréquence) REJETÉ avant extraction — appelé en corps de fonction par setupDone()/clearForm()/prefillSetupFromConfig(), les 3 fonctions du chemin critique déjà identifiées ÉLEVÉ par ce même inventaire, sous une AUTRE entrée"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T03:24:53.410Z
---

2e rejet de candidat de la campagne, même mécanisme que le 1er
([[inventaire-ev7-23e-2026-08-09]] candidat n°1, `matchesAdvancedFilter`,
rejeté au 23e incrément). Candidat n°5 : "Sélecteurs OPÉRATEUR/BANDE/MODE +
fréquence" (`pickBand`/`setFreqForBand`/`pickOp`/`pickMode`/`onFreqInput`/
`freqFromRig`, section `─── OPÉRATEUR / BANDE / MODE ───`,
`concours/logx_logbook.js` lignes ~2123-2295 au moment de l'évaluation).

## Pourquoi rejeté

Grep des sites d'appel externes (fait avant toute extraction, méthode déjà
systématique) :
- `setupDone()` (L1899, validation du modal de démarrage — CHEMIN
  CRITIQUE) appelle `_setCurrentOpLabel(op)` en son propre corps (L1957).
- `clearForm()` (L2743, réinitialisation du formulaire après chaque QSO —
  CHEMIN CRITIQUE) appelle `setFreqForBand(currentBand)` en son propre
  corps (L2755).
- `prefillSetupFromConfig()` (L4209) appelle `_setCurrentOpLabel(activeOp)`
  (L4263) — déjà documentée par CE MÊME inventaire comme un prolongement
  du bloc ÉLEVÉ (« appelle DIRECTEMENT `setupDone()` en son propre corps »).

`setupDone()` et `clearForm()` sont EXPLICITEMENT nommées dans la section
« Candidats ÉLEVÉ (à ne jamais reproposer) » du même document d'inventaire
(bloc SAISIE, `onCallInput/bearing/cardinalDir/submitQSO/clearForm`) — donc
extraire les sélecteurs ferait dépendre ce chemin critique déjà exclu d'un
fichier « optionnel », violant la convention EV-7 établie (le cœur ne
dépend jamais d'un fichier optionnel, même via un simple appel en corps de
fonction).

## Où l'évaluation de l'inventaire s'est trompée

L'agent d'évaluation avait noté « Tous les sites externes en corps de
fonction » — techniquement vrai, et c'est effectivement le critère qui
rend un appel SÛR dans le cas général (ex. `logx_dup_finder.js` ->
`deleteQSOSilent()`, `logx_verif_panel.js` -> `editQSO()` via
`fixFromValidation()`). Mais il n'a pas croisé ces sites d'appel avec la
liste ÉLEVÉ du MÊME inventaire pour vérifier si l'APPELANT lui-même
faisait partie du chemin critique déjà exclu — la direction de la
dépendance (optionnel → optionnel vs cœur/critique → optionnel) compte
autant que le fait que l'appel soit en corps de fonction plutôt qu'au
top-level.

**Réflexe généralisé pour toute suite** : avant de faire confiance au
verdict FAIBLE d'un candidat, croiser ses sites d'appel externes avec la
liste ÉLEVÉ ET les noms de fonctions du « chemin critique » (voir CLAUDE.md
« Intuitivité » : indicatif, sélection concours, saisie bande/mode/
callsign/RST/échange, bouton d'enregistrement du QSO) — pas seulement
vérifier « corps de fonction vs top-level ».

## Suite

Les 5 candidats FAIBLE du 2e inventaire sont désormais tous traités
(#1 et #5 rejetés, #2/#3/#4 extraits et fusionnés). Un 3e inventoire
Workflow est nécessaire pour la suite de la campagne.
