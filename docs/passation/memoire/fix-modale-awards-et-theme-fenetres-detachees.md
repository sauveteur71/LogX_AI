---
name: fix-modale-awards-et-theme-fenetres-detachees
description: Fix modale Diplômes/QSL trop petite (classe CSS partagée mal dimensionnée) + fenêtres détachées bloquées en mode nuit (thème jamais lu)
metadata: 
  node_type: memory
  type: project
  originSessionId: e727f52a-b66b-4617-abb1-afba96fda04d
  modified: 2026-07-20T12:08:38.519Z
---

Deux bugs signalés et corrigés (commit `d4790d4`) après le renommage LogX AI ([[radiocontest-phase0-done]]) :

1. **Modale Diplômes & QSL trop petite** : `#awardsOverlay` réutilisait `.shortcuts-box` (classe pensée pour la petite liste de raccourcis clavier, `width:480px` fixe) avec juste un `style="max-width:560px"` inline — inutile puisque `max-width` ne peut jamais réduire en dessous de `width`, et 560>480 ne change rien non plus. Corrigé en passant à `style="width:860px;max-width:92vw"` + `max-height:78vh` sur `#awardsInner`.
   **Piège réutilisable** : toujours vérifier qu'un override `max-width` inline s'accompagne (ou remplace) la propriété `width` de la classe de base — sinon il est silencieusement inopérant.

2. **Fenêtres détachées toujours en mode nuit** : `logx_scope.html`, `logx_panel.html`, `logx_wall.html`, `logx_mobile.html` (fenêtres pop-out ouvertes via `window.open`) n'avaient ni bloc CSS `body.day-mode{...}` ni lecture JS de `localStorage.getItem('rc_theme')` — contrairement aux 6 pages principales qui utilisent `logx_statusbar.js` (fonction `applyTheme()` + listener `storage`). Corrigé en dupliquant le bloc de palette claire (mêmes valeurs partout : `--bg:#EEF0F8` etc.) et en ajoutant `if(localStorage.getItem('rc_theme')==='day') document.body.classList.add('day-mode');` sur les 4 fichiers.
   **Piège réutilisable** : ces 4 pages n'incluent PAS `logx_statusbar.js` (trop lourd pour une fenêtre pop-out) donc toute future feature globale ajoutée à `logx_statusbar.js` doit être vérifiée/dupliquée manuellement sur ces 4 fichiers si elle doit s'y appliquer aussi.

Vérifié via serveur isolé (port 8099, technique de [[qso-director-parity]]) : `showAwards()` appelé en JS direct pour contourner un viewport de test trop petit (492×415) qui masquait le bouton ; largeur mesurée à 860px après fix (contre 480 avant). Les 4 pages détachées confirmées `day-mode:true` via `document.body.classList.contains('day-mode')` après navigation avec `rc_theme` déjà à `'day'` en localStorage partagé (même origine).
