---
name: chantier-ev7-tx-audio-2026-08-09
description: "EV-7 27e incrément : extraction TX audio générique (txAudioPtt) vers logx_tx_audio.js (09/08, merge 54a1f9a) — candidat le plus sûr des 3 inventaires cumulés, 0 constat, pytest vert du 1er coup"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T04:07:51.136Z
---

27e incrément de la campagne, candidat n°1 du 3e inventoire
([[inventaire-ev7-3e-2026-08-09]]), premier après les 2 rejets successifs
(candidats n°1 et n°5 du 2e inventaire). Extraction de 43 lignes de
`concours/logx_logbook.js` vers `concours/logx_tx_audio.js` (nouveau) :
`txAudioPtt()` (PTT ON → lecture Web Audio → PTT OFF garanti dans un
`finally`). `logx_logbook.js` : ~4513 → ~4473 lignes.

Confirmé comme "le plus sûr des 3 inventaires cumulés" : 0 appel
top-level, 0 référence dans `logx_logbook.js` en dehors de sa propre
définition, ses 2 seuls appelants (`rttyEnvoyerTexte()` dans
`logx_rtty_panel.js`, `sstvEnvoyerImage()` dans `logx_sstv_panel.js`)
étaient DÉJÀ des fichiers optionnels extraits — dépendance
optionnel→optionnel, le sens sûr établi par la convention EV-7. Aucun
fichier de test ne le référence directement.

Suite pytest complète verte du premier coup (aucun cycle correctif
nécessaire). Vérification navigateur : appel réel avec `fetch` mocké a
produit exactement 2 appels à `/rig/ptt` (`{"on":true}` puis
`{"on":false}`) et retourné `{ok:true}` — comportement PTT ON→lecture→PTT
OFF confirmé de bout en bout. Revue adversariale (2 dimensions, avec
instruction explicite de re-vérifier le croisement chemin critique vu les
2 rejets précédents dans cette campagne) : 0 constat.

Suite : candidat n°2 du 3e inventaire (BAND MAP S&P, `bandmapNoter`/
`bandmapSaut`, 51 lignes) devient le 28e incrément — périmètre de lignes
à respecter STRICTEMENT (voir [[inventaire-ev7-3e-2026-08-09]]).
