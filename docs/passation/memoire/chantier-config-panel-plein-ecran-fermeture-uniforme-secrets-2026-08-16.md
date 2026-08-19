---
name: chantier-config-panel-plein-ecran-fermeture-uniforme-secrets-2026-08-16
description: "CONFIG : panneau plein écran + fermeture uniforme (clic extérieur/✕/LOGGER/Échap) navigue vers LOGBOOK (PR #103) + point de statut configuré/vide sur les 17 champs secrets (PR #104) — retour F4GLD 16/08/2026"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-16T12:19:30.070Z
---

Retour F4GLD (16/08/2026, 2 captures d'écran CONFIG — sidebar + panneau QSL &
DIPLÔMES) traité en 2 PR distinctes le même jour.

## Demande 1 — lisibilité du panneau CONFIG (PR #103, fusionnée)

Verbatim : « je souhaite que le panneau configuration prenne toute la page
hateur et largeur pour plus de lisibilité cette page se ferme si je clique a
coté ou si je clique siur fermer ou pret a a logger ou touche escape. le menu
doit aussi disparaitre dans ce cas! »

Point ambigu clarifié via AskUserQuestion (1re tentative rejetée par F4GLD —
« [User dismissed — do not proceed, wait for next instruction] » — reposée en
texte simple, réponse arrivée en message intercalé) : est-ce que fermer doit
RESTER sur CONFIG (panneau juste caché) ou NAVIGUER vers LOGBOOK ? Réponse :
« doit rester visible sur la page CONFIG je pense que des que c'est fermé on
doit revenir diectement sur logbbok idem pour mogger direction le logbook »
— les 4 déclencheurs (clic extérieur, ✕, bouton LOGGER, Échap) doivent TOUS
naviguer vers `logx_logbook.html`, alignés sur le comportement déjà existant
du bouton LOGGER.

Livré : marges `.config-sidebar`/`.cat-modal-box` 6%→2%, nouveau bouton
`.config-close-btn` (cercle ✕ fixe, coin haut-droit), `closeCategoryPanel()`
réécrite pour naviguer au lieu de masquer, écouteur Échap ajouté.

**Piège CSS résolu au passage** : `--config-panel-top` (calculée par
`_updateConfigPanelTop()`, mesure le bas de `#rcStatusBar`/`.app-nav`/
`.usage-mode-bar`) restait périmée après fermeture de l'overlay d'onboarding
— son `ResizeObserver` ne surveillait QUE `.app-nav`, pas les barres révélées
après coup. Fixé en appelant `_updateConfigPanelTop()` dans
`_closeOnboarding()`. Piège annexe : `.config-close-btn` en
`position:fixed;transform:translateY(-50%)` ne suivait PAS les mises à jour
live de cette variable CSS (confirmé par comparaison avec un clone identique
sans transform, qui suivait correctement) — contourné en remplaçant
transform+margin-top par un simple `calc(var(--config-panel-top,2%) - 17px)`.
Cause racine non confirmée (probablement lié aux compositor layers), mais le
contournement est fiable.

## Demande 2 — lisibilité des mots de passe (PR #104, fusionnée)

Verbatim (avec capture du panneau QSL & DIPLÔMES) : « concernat les mot de
passe difficile de voir ce qui a ete rempli ou pas et il faut conserver ces
mots ou pas selon le changement de station emetrice!? »

Deux volets distincts :
1. **Lisibilité** (code livré) — point coloré (`.secret-dot`/`.secret-dot.set`,
   motif réutilisé de `.tree-badge`) à côté du label de chacun des 17 champs
   de `SECRET_CONFIG_FIELDS` dans `logx_configuration.js`. Vert = valeur
   présente, neutre = vide. Mise à jour live via écouteur `input` posé au
   `DOMContentLoaded`, sans attendre un rechargement. Problème sous-jacent :
   les points masqués d'un `type="password"` ET les champs `type="text"`
   (clés API en clair, ex. ClubLog/QRZCQ) sont visuellement quasi
   indiscernables entre rempli/vide sur une grille dense d'~15 champs
   similaires.
2. **Persistance selon la station émettrice** (réponse donnée, AUCUN code
   changé) — le mécanisme existe déjà : un **profil** (barre PROFIL en haut
   de CONFIG, `saveProfile()`/`loadProfile()`) capture et restaure tous ces
   identifiants en clair, DÉLIBÉRÉMENT à part du blob `localStorage`
   expurgé des secrets. Changer de profil = retrouver les identifiants
   propres à CE profil. Expliqué directement à F4GLD, rien à livrer.

Tests : `tests/test_config_secret_dots.py` (6 tests, JS réel via
py_mini_racer) — voir [[piege-py-mini-racer-dict-mirror-diverge-etat-v8]]
pour le piège de conception rencontré en écrivant ce fichier de test.

## Réutilisable pour la suite

- Motif `.secret-dot` réutilisable pour tout futur champ sensible ajouté à
  `SECRET_CONFIG_FIELDS` — ajouter le `<span class="secret-dot" id="X_dot">`
  et rien d'autre, `_refreshAllSecretDots()` couvre déjà tous les champs de
  la liste dynamiquement (pas de liste à dupliquer, voir
  [[piege-liste-identifiants-ecrite-a-la-main]]).
- Les 4 déclencheurs de fermeture CONFIG naviguent maintenant TOUS vers
  LOGBOOK — si une future demande touche à `closeCategoryPanel()`, ce
  comportement est confirmé 2 fois par F4GLD (demande initiale + clarification
  explicite après question), pas une supposition.
- Voir [[piege-async-microtask-verification-javascript-tool]] pour le piège
  de vérification rencontré en testant `closeCategoryPanel()` (async) en
  navigateur.
