---
name: chantier-cw-hors-mode-bandeau-expedition-2026-08
description: "Suite de l'étude d'affichage par mode (ETUDE_AFFICHAGE_PAR_MODE) — bouton de forçage du décodeur CW hors mode CW + bandeau discret CHASSE en expédition, livré 05/08/2026 (`72ef73d`)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-05T06:35:10.083Z
---

Deux correctifs issus de [[etude-affichage-par-mode-2026-08]] (à créer si pas
déjà fait) livrés ensemble sur `main` le 05/08/2026 (commit `5f506ed`, merge
`72ef73d`) suite à la réponse F4GLD « oui les deux » :

1. **Décodeur CW injoignable hors mode CW** — `renderModeButtons()`
   (`logx_logbook.js`) ne propose que les modes cochés dans CONFIG > MODES ;
   si CW n'est pas coché, aucun bouton CW n'existe dans le sélecteur, donc
   `updateKeyerPanels()` ne peut jamais faire matcher `/CW/i.test(mode)`, et
   le panneau `#cwPanel` reste injoignable même exceptionnellement. Fix :
   variable module `cwPanelForcedOpen` + bouton dédié `#cwForceBtn` dans la
   barre d'outils band map (`toggleCwPanelForce()`), condition devenue
   `(cw || cwPanelForcedOpen)`. N'affecte QUE le panneau décodeur, pas les
   macros F1-F8 ni le keyer vocal (qui restent liés au vrai mode radio).
2. **Bandeau CHASSE en expédition** — `verifierBandeauExpedition()`
   (`logx_chasse.html`) lit `logx_config` du localStorage, affiche un
   bandeau discret (pas un masquage) quand `usage_mode==='expedition'` ET
   qu'une activation est configurée (`activation_program`+`my_activation_ref`),
   rappelant que la chasse aux autres stations est secondaire. Écoute aussi
   l'event `storage` pour se mettre à jour si CONFIG est ouvert dans un autre
   onglet.

**Piège rencontré et corrigé pendant l'écriture du CSS** : `display:none;...;
display:flex` dans la MÊME règle — la déclaration la plus tardive gagne
toujours, rendant le bandeau visible en permanence au lieu de caché par
défaut. Repéré à la relecture avant tout test. Fix : `display:flex` déplacé
dans une classe séparée `.show` togglée en JS — même famille de piège que
[[piege-min-width-vs-max-width-css]] (une règle CSS qui semble correcte à la
lecture rapide mais où l'ORDRE/la présence de deux déclarations concurrentes
décide, pas l'intention).

**Test cassé par un changement de comportement LÉGITIME** (pas une
régression) : `tests/test_sstv_decodeur.py::test_updateKeyerPanels_pilote_
les_panneaux_cw_et_sstv` figeait la regex exacte `cwDec\.style\.display\s*=
\s*cw\s*\?` — cassée par l'ajout du OR `cwPanelForcedOpen`. Corrigé en
assouplissant la regex (`cwDec\.style\.display\s*=\s*\(?\s*cw\b`) plutôt que
d'annuler le changement. Réflexe suivi : après tout changement de
`updateKeyerPanels()`, greper `tests/` pour `cwDec.style.display` avant de
considérer le chantier fini — cf. réflexe déjà noté dans CLAUDE.md pour les
conversions emoji→icône (« après toute conversion, greper les tests »),
généralisable à TOUT changement de comportement d'une fonction déjà couverte
par un test à assertion exacte.

Vérifié en navigateur directement sur le serveur de production (lecture
seule, aucun redémarrage) : bouton CW bascule bien dans les deux sens sans
toucher au mode SSB en cours ; bandeau simulé via `localStorage.setItem`
temporaire (restauré ensuite) confirme le texte et le toggle `.show`.
