---
name: chantier-nettoyage-i18n-mufmap-fuseaux-2026-07-24
description: "Nettoyage git external_contests.json, i18n carte/propagation, carte MUF graphique (hamqsl.com), fuseaux DX sur l'écran mural"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-24T20:36:31.114Z
---

Commits 6c73029, 1346508, 96e5fd1, 9ea4d74, a3af09b, 7a46ac1 (24/07/2026), suite directe de [[chantier-bandes-modes-serveur-dxheat]] / [[chantier-feedback-batch2-2026-07-24]] — 4 items choisis par l'utilisateur après un audit "qu'est-ce qui reste à faire" (multiSelect sur toutes les options proposées).

- **`external_contests.json` retiré du suivi git** (`.gitignore` + `git rm --cached`) : c'est un cache auto-régénéré (scrapé WA7BNM par `refresh_external_contests()` dans `logx_rules.py`, réécrit dès qu'il a >7 jours), il polluait `git status` en permanence sans valeur — le diff observé n'était jamais une vraie donnée (juste le timestamp `updated` + un réordonnancement instable du scraping).
- **Bug i18n réel corrigé** : le bouton "SANS DUPES" ne se traduisait jamais — le dictionnaire avait une entrée pour "SANS DOUBLONS" (mot différent), jamais utilisée dans le DOM réel. Le moteur i18n fait une correspondance EXACTE après trim, aucune tolérance.
- **i18n complété** sur `logx_carte.html`/`logx_propagation.html` (~60-70 chaînes, 7 langues).
- **Carte MUF graphique** (`hamqsl.com/solarmuf.php`, N0NBH) intégrée sur `logx_propagation.html` (panneau complet) + vignette compacte dans CONDITIONS sur `logx_wall.html`. Même méthodologie que Blitzortung : vérification live AVANT d'implémenter (200 OK, pas de blocage anti-hotlink, licence de réutilisation explicite sur le site). Rafraîchie par bucket de 15 min (jamais à chaque poll). PIÈGE de vérification : un test naïf sur un onglet navigateur déjà "chargé" (beaucoup de polling accumulé dans la session) peut faire croire que l'image ne charge jamais (timeout) — sur un onglet FRAIS elle charge en réalité immédiatement (400x200 confirmé). Toujours tester ce genre de ressource externe sur un onglet propre avant de conclure à un bug.
- **Fuseaux DX de référence sur l'écran mural** (`#wDxZones`, panneau "🌐 FUSEAUX DX") : 4 horloges fixes (USA Est/Ouest, Japon, Océanie) calculées 100% en JS via `Intl.DateTimeFormat({timeZone,...})`, aucune dépendance externe. Décision documentée dans le commit : rien dans `wall_state()` ne permettait de dériver dynamiquement des fuseaux plus pertinents (pays/départements cibles) sans dupliquer la logique de scoring pour un gain marginal — zones fixes retenues sciemment.
- **Fix adversarial layout** : le panneau FUSEAUX DX en pile de 4 lignes (~209px) poussait le panneau PAR OPÉRATEUR hors écran à 1920×1080 (résolution TV standard) — passé en grille 2×2 (133px), confirmé par mesure DOM réelle que plus aucun bloc ne dépasse `window.innerHeight`.

**Vérification indépendante** (au-delà de l'auto-évaluation du workflow) : suite complète 1073/1073 reproduite deux fois, grep "QSO Director" propre, horloges DX vérifiées par comparaison à un calcul `Intl.DateTimeFormat` indépendant (correspondance exacte à la minute), carte MUF confirmée chargée (400×200) sur propagation ET mur, panneau FUSEAUX DX mesuré à 133px de haut (bottom=672 < 1080).

Pas encore poussé sur GitHub à la fin de ce chantier (l'utilisateur pousse explicitement à chaque fois, jamais automatique — cf. pattern établi).
