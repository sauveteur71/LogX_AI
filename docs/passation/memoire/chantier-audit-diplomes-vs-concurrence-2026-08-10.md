---
name: chantier-audit-diplomes-vs-concurrence-2026-08-10
description: "Audit quantifié du catalogue de diplômes LogX AI vs Wavelog (20+) — 1 ajout justifié (zones ITU), le reste explicitement écarté (diplômes locaux étrangers)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-10T08:11:48.407Z
---

Suite de [[analyse-concurrence-logx-ai-2026-08-10]] (recommandation P2 : « quantifier l'écart réel sur les diplômes avant d'agir »). PR #13 (branche feat/diplome-zones-itu), mergée le 10/08/2026.

**Catalogue LogX AI confirmé par lecture de `logx_awards.py`** : DXCC (pays), WAS (50 états US), WAC (6 continents), WAZ (40 zones CQ), DXCC Challenge (entité×bande), VUCC (carrés QRA), CQ DX Field, + REF départements (métropole/DOM, l'équivalent français des « comtés » — déjà le bon choix pour un public francophone, pas un import étranger).

**Le seul ajout retenu : diplôme zones ITU (RSGB, 90 zones)**. `logx_dxcc.lookup()` extrait déjà `itu_zone` depuis cty.dat — EXACTEMENT la même source que `cq_zone`, déjà utilisée pour le WAZ — mais cette donnée n'était jamais exploitée nulle part dans `logx_awards.py`. Ajout à coût quasi nul : même patron exact que le WAZ (`_enrich()` → `award_summary()` → `logx_awards.js`), aucune nouvelle source de données, aucun nouveau référentiel à maintenir. Nombre total (90 zones) vérifié par recherche web AVANT codage — voir [[piege-table-domaine-ecrite-de-memoire]], le skill radioamateur n'avait pas ce chiffre en fiche.

**Diplômes de Wavelog explicitement écartés, décision assumée** (mêmes raisons que le hors-scope drapeaux de langue dans CLAUDE.md — pas un oubli si jamais reposé) :
- WAB (Worked All Britain), Helvetia (cantons suisses), RAC (provinces canadiennes), JCC (comtés japonais), WAP/WAIP (Pologne/Italie), FFMA, comtés US — tous des diplômes **nationaux étrangers**, sans intérêt pour la base d'utilisateurs francophone/REF actuelle de LogX AI. Copier ce catalogue aurait été du gonflage de fonctionnalités sans valeur réelle.
- IOTA (« îles confirmées ») : envisagé puis écarté après investigation — contrairement à WAZ/WAZ-ITU, il n'existe PAS de correspondance simple indicatif→île (contrairement au préfixe→zone CQ/ITU via cty.dat). Une vraie liste "IOTA travaillées/confirmées" demanderait soit que le correspondant envoie sa référence IOTA en direct (rare hors chasse d'une activation annoncée), soit une base de correspondance station↔île qui n'existe pas publiquement de façon fiable. La base de RÉFÉRENCES IOTA (`logx_iota.py`, pour identifier/loguer une activation en cours) reste correcte et déjà faite — c'est le calcul retour « combien d'îles ai-je confirmées sur toute ma vie » qui n'est pas un ajout simple, à ne pas reprendre sans réévaluer le coût réel.

**Détail technique retenu pour du code futur similaire** : `_paire(worked, confirmed, total, missing)` est le patron commun à tous les diplômes classiques de `logx_awards.py` — un nouveau diplôme dérivable du même cty.dat (par indicatif) se branche en 3 points : `_enrich()` (lire le champ), la boucle de `award_summary()` (agréger dans un set worked/confirmed), le dict retourné (`_paire(...)`). Reproductible pour toute future donnée déjà présente dans `logx_dxcc.lookup()` mais non exploitée.
