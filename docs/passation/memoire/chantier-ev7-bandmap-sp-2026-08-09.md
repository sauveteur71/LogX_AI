---
name: chantier-ev7-bandmap-sp-2026-08-09
description: "EV-7 28e incrément : extraction BAND MAP S&P (bandmapNoter/bandmapSaut) vers logx_bandmap_sp.js (09/08, merge 2be436d) — 0 constat, périmètre de lignes strict respecté, épuise la liste FAIBLE du 3e inventaire"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T04:37:51.816Z
---

28e incrément de la campagne, candidat n°2 du 3e inventaire
([[inventaire-ev7-3e-2026-08-09]]) — dernier candidat FAIBLE, la liste
FAIBLE du 3e inventaire est désormais épuisée (comme le 2e l'était après
le 26e incrément). Extraction de 51 lignes de `concours/logx_logbook.js`
vers `concours/logx_bandmap_sp.js` (nouveau) : `_bmSpots`, `bandmapNoter()`,
`bandmapSaut()`. `logx_logbook.js` : ~4473 → ~4425 lignes.

Point de vigilance de l'inventaire respecté avec succès : le périmètre de
lignes (984-1034) est resté STRICT, sans empiéter sur la section voisine
`_BM_PCOL`/`_BM_CSSVAR`/`_BM_RANGE` (juste au-dessus, utilisée par
`bandFromFreq()`, chemin critique) — cette section reste dans le cœur.

Dépendances croisées (toutes fonction-corps, sûres) : `bandmapNoter()` →
`refreshBandMap()` (cœur), `bandmapSaut()` → `bandmapClick()` (cœur),
`refreshBandMap()` (cœur) ÉCRIT `_bmSpots` (variable maintenant déclarée
dans le fichier extrait) — sûr car `logx_bandmap_sp.js` charge TOUJOURS
avant `logx_logbook.js`. `logx_theme_shortcuts.js` (déjà extrait) devient
optionnel→optionnel pour ses appels à ces deux fonctions ; son en-tête a
été mis à jour en conséquence (2e fichier de cette nature à recevoir une
mise à jour d'en-tête après une nouvelle extraction, après
`logx_hardware_cat.js` au 19e incrément).

Un seul fichier de test dédié affecté (`test_bandmap_sp.py`, extraction
par comptage d'accolades, repointé vers le nouveau fichier). Un 2e
fichier suspecté (`test_freq_unite_spots.py`, recherche de sous-chaîne
sur l'assignation `_bmSpots = spots`) a été vérifié comme NE nécessitant
PAS de changement : cette ligne précise appartient à `refreshBandMap()`,
restée dans le cœur, non touchée par cette extraction.

Suite pytest complète verte du premier coup. Vérification navigateur :
appel réel de `bandmapSaut(1)` avec un `_bmSpots` synthétique (2 spots) et
une `rigState` simulée a correctement sauté au bon spot via un vrai appel
à `bandmapClick()` intercepté — confirme la lecture/écriture croisée entre
les deux fichiers en conditions réelles. **Piège de vérification rencontré
en écrivant le test navigateur** : une première tentative mockait
`window.rigState` au lieu de la variable top-level `rigState` — sans
effet, puisque `let rigState` déclaré ailleurs (dans un autre script
classique) crée une liaison lexicale, PAS une propriété de `window` ;
`_bmSpots` avait été correctement mocké (assignation directe sans
`window.`), ce qui a permis de repérer l'écart. Corrigé en assignant
directement `rigState = {...}` (sans préfixe `window.`). Revue
adversariale : 0 constat.

Suite : passage aux candidats MOYEN du 3e inventaire — SOAPBOX PAR BANDE
(33 lignes) devient le 29e incrément.
