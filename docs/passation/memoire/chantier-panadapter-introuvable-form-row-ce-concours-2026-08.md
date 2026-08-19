---
name: chantier-panadapter-introuvable-form-row-ce-concours-2026-08
description: "3 bugs UI remontés par F4GLD le jour même du ship du panadapter — introuvable, ALERTES/CAT2 empilés sur 1 colonne, bouton \"Ce concours\" fantôme"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-04T14:51:35.369Z
---

Le 04/08/2026, dans la même conversation qui venait de livrer le panadapter
(voir [[chantier-panadapter-audio-et-civ-2026-08]] et le volet TCI), F4GLD a
remonté 3 bugs UI distincts en un seul tour : screenshot d'ALERTES
PERSONNALISÉES ("pourquoi tu n'exploites pas toute la largeur!!!"), screenshot
du popup WORKED MATRIX en mode log simple ("pourquoi ce concours alors que je
suis en log simple?"), puis "je ne trouve pas le panadapter ou est il?" — sans
screenshot, en investigation pure. Les 3 corrigés + testés + mergés dans la
même branche `fix/panadapter-nav-form-row-ce-concours`.

## 1. Panadapter introuvable

Le seul point d'accès était une icône dans le toolbar de `.bandmap-panel`
(`logx_logbook.html`) — panneau soumis à
`@media(max-width:1100px){.bandmap-panel{display:none}}`. Vérifié en
direct sur la prod (lecture seule, `javascript_tool` + `getComputedStyle`) :
à la largeur réelle de la fenêtre de F4GLD (838px), `display:none`
confirmé — le bouton n'était pas juste peu visible, il n'existait pas dans
le rendu. Fix : lien "PANADAPTER" ajouté dans `<nav class="app-nav">` sur
les 10 pages qui la partagent (comme `popoutPanadapter()`/`window.open()`,
pas une navigation — cohérent avec le principe "chaque panneau se détache
dans sa propre fenêtre"). `logx_cw.html` a un nav RÉDUIT (pas les mêmes 9
liens que les 9 autres pages) — vérifié fichier par fichier avant d'éditer,
pas de script en aveugle cette fois (seulement 10 fichiers, faisable à la
main avec Read+Edit).

**Réflexe retenu** : quand un utilisateur dit "je ne trouve pas X" pour une
fonctionnalité tout juste livrée, ne pas supposer un problème de
découvrabilité pure — vérifier d'abord si l'élément est structurellement
absent du DOM rendu (media query, JS conditionnel) à la taille réelle de sa
fenêtre, PUIS seulement discuter ergonomie.

## 2. `.form-row` sans `display:flex`

Cf. [[piege-couleur-data-vs-theme]] pour le style "grep avant de toucher" —
ici le piège est inverse : une classe utilisée 7 fois avec des styles
inline `flex:`/`max-width:`/`align-items:` qui ne faisaient RIEN parce que
`.form-row` elle-même n'avait jamais de `display:flex` dans la feuille de
style. Détail complet du fix (et de la correction du fix) dans
[[piege-min-width-vs-max-width-css]].

## 3. "Ce concours" fantôme dans Worked Matrix

`logx_panel.html` (`tickWorkedMatrix()`) affichait toujours 2 boutons
"Vie entière"/"Ce concours" même quand `usage_mode == 'simple'` ou sans
concours sélectionné — cas où `logx_storage.cfg_scope_id()` renvoie `''`
dans LES DEUX positions du bouton (aucun effet réel, juste confus).
`contest_actif(cfg)` est déjà la source unique de vérité côté serveur pour
cette question exacte — mais `logx_panel.html` est une fenêtre détachée qui
n'a accès qu'à l'endpoint public `/config` (liste blanche stricte, "AUCUN
secret"), qui n'exposait PAS `usage_mode`. Ajouté à la liste blanche
(non-sensible, au même niveau que `expedition_mode`/`activation_program`
déjà exposés) plutôt que de dupliquer la logique serveur. Le toggle est
maintenant absent du DOM (pas juste désactivé) quand `contestActif` est
faux, et `_wmScope` est forcé à `'life'` dans ce cas.

Test ajouté : `tests/test_config_endpoint_usage_mode.py` — vérifie que
`usage_mode` apparaît dans `/config`, que l'absence du champ replie sur `''`
(pas de `KeyError`), et un garde-fou anti-régression qui grep le tuple de
la liste blanche pour `password`/`token`/`secret`/etc. (piège rencontré en
l'écrivant : une regex trop large sur 700 caractères capturait un
commentaire voisin mentionnant `auth_token` sans rapport — resserrer
l'extraction au tuple exact, pas un nombre de caractères arbitraire).
