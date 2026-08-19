---
name: chantier-fix-rect-negatif-graphe-heure-2026-08-08
description: "Fix erreur console en boucle '<rect> attribute width: A negative value is not valid (\"-1\")' sur LOGBOOK — drawHourChart, commit 7002539"
metadata: 
  node_type: memory
  type: project
  modified: 2026-08-08T11:22:10.642Z
  originSessionId: c4f29576-6255-461b-811a-c46aa9ee71bb
---

Signalé par F4GLD : erreur console en boucle sur logx_configuration.html ET
logx_logbook.html (hypothèse initiale : composant partagé type
logx_statusbar.js). Diagnostic réel après instrumentation navigateur
(MutationObserver + override innerHTML n'ont RIEN capté — c'est une erreur
native du parseur SVG du moteur de rendu, pas un appel `console.error()` côté
page, donc invisible à ce type de hook JS ; seul `read_console_messages` du
navigateur la voit) : source unique dans `drawHourChart()`
(`concours/logx_logbook.js`, fonction du graphe sparkline « QSO/heure » du
LOGBOOK), PAS dans un composant partagé. `logx_configuration.html` n'a
jamais eu ce bug — l'impression de bug partagé venait d'un tampon de
console non réinitialisé entre deux navigations dans le même onglet
(confirmé faux en rouvrant un onglet neuf pour chaque page).

**Cause** : `bw = Math.floor((VW - gap*(n-1))/n)` (VW=1000, gap=1) où `n` =
nombre de tranches heure/date distinctes dans `qsoLog`. Au-delà de ~1000
tranches (log couvrant beaucoup de jours — LogX AI est un logbook général,
pas juste par contest), la formule devient négative. Reproduit sur instance
réelle : 9875 QSO chargés → 1653 tranches → `bw = -1` exactement, d'où
l'erreur identique répétée une fois par barre (1653 fois).

**Fix** : `Math.max(0.1, Math.floor(...))` — garantit une largeur toujours
valide sans changer le rendu dans le cas normal.

**Piège rencontré pendant ce chantier** : voir
[[piege-perte-edition-synologydrive-agents-paralleles]] — le premier Edit a
été perdu silencieusement (disparu du disque) AVANT le commit, sans agent
parallèle actif cette fois (édition solo). Réappliqué et re-grepé juste
avant `git add`/`git commit`, pas seulement juste après l'Edit.

**Repéré au passage, hors scope, non corrigé** : `ReferenceError:
adaptivePoll is not defined` à chaque chargement de logx_logbook.html
(logx_hardware_cat.js:524) — le polling matériel radio/ampli/rotor/WSJT-X
ne démarre jamais silencieusement. Tâche de fond créée (task_42eef06f) pour
investiguer séparément ; un correctif similaire avait déjà été appliqué lors
d'un chantier EV-7 précédent ([[chantier-ev7-radio-cat-2026-08-08]]) mais ne
suffit apparemment plus.
