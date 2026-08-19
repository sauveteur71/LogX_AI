---
name: piege-verifier-sur-donnees-reelles
description: "Band map mort depuis toujours (unités kHz/MHz mélangées) — trouvé seulement en regardant de VRAIS spots ; + le heredoc bash qui mange un niveau d'antislash"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-30T15:39:57.206Z
---

Le 30/07/2026, en vérifiant une fonction nouvelle sur le serveur en marche, j'ai découvert que **le band map n'avait jamais affiché les spots cluster HF** — ni le bandscope, ni la chute d'eau, ni le scope détaché. Corrigé commit `636e75c`.

**La cause :** les sources de spots ne s'accordent pas sur l'unité. Mesuré en appelant les lecteurs pour de vrai : DXSummit HF et DXHeat rendent des **kHz** (14074, 144360), DXSummit VHF rend des **MHz** (50.313). `/data/spots_ranked` recopiait tel quel, donc le champ `freq` n'avait **aucune unité fixe** et aucun écran ne pouvait le lire juste. Seuls les spots DXSummit VHF passaient le filtre `_BM_RANGE` (en MHz) — les seuls du bon côté du hasard. Résolu par `logx_clusters.freq_en_khz(freq, band)`, qui tranche **par la clé de bande** et non par magnitude (10368 est plausible en MHz : c'est le 3 cm).

**Deux défauts se masquaient l'un l'autre :** `bandmapClick(call, mhz)` fait `mhz*1000` avant le QSY ; un spot HF affiché aurait envoyé la radio à 21,263 GHz. La liste vide empêchait le clic. Ce genre de paire survit des années.

**LEÇON, et c'est la seule qui compte :** j'avais livré la réglette de fréquence et les fenêtres par bande le matin même avec CI verte — les tests vérifiaient la *structure* du code, pas ce que l'écran montre avec de vraies données. Une suite verte ne prouve rien sur un affichage tant qu'on n'a pas regardé le rendu **alimenté par la vraie source**. Même passe : `qsy()` envoyait `{freq: …}` à `/rig/qsy` qui ne lit que `freq_hz`/`freq_khz` — clic sans effet, sans erreur. Voir [[passe-verification-distribution-2026-07-22]] (même famille : panne silencieuse jamais remarquée).

**DEUXIÈME CAS, le même jour, en sens inverse : une affirmation FAUSSE répétée trois fois.** J'ai annoncé à l'utilisateur que « 5 QSO à préfixe portable sont mal attribués ». Vérification faite sur les 9 392 QSO : **851 indicatifs à barre, 201 réellement ambigus, ZÉRO mal résolu**. `4O/ON5JE`→Monténégro, `IQ0FP/IT9`→Sicile, `VK2ZK/P4`→Aruba : tout est juste. La règle non écrite de `logx_dxcc._lookup_compute` est *le morceau le PLUS COURT qui résout gagne* — c'est ce qui traite à la fois PRÉFIXE/indicatif et indicatif/SUFFIXE. Verrouillé par `tests/test_dxcc_indicatifs_a_barre.py` (commit `611afb5`), tests dont j'ai vérifié qu'ils MORDENT en neutralisant le tri. **Ne pas rouvrir ce sujet.**

**ET LE PIÈGE QUI A FAILLI ME FAIRE CONCLURE DE TRAVERS :** mon premier script d'analyse annonçait « 0 cas ambigu » — rassurant et totalement faux. Il tournait depuis la **racine du dépôt** alors que `cty.dat` est dans `concours/` : `load_cty()` ouvre le fichier en chemin RELATIF, ne l'a pas trouvé, et la table des pays était **vide**. Tout `lookup()` rendait None, donc « aucune ambiguïté ». Signe qui aurait dû m'alerter immédiatement : `DL`, `S5`, `EA8` classés « pays inconnu ». **Tout script qui touche cty.dat, calldb ou une base locale doit tourner depuis `concours/`** — et un résultat « rien à signaler » sur une base de référence mérite toujours un contrôle de sanité sur une valeur qu'on sait présente.

**PIÈGE OUTILLAGE de ce poste (Windows/Git Bash) :** un heredoc `bash <<'PY'` **mange un niveau d'antislash**. `[^"\\]` arrive au regex comme `[^"\]` → `PatternError: unterminated character set`, et `'\\U0001F3DE'` devient l'emoji au lieu de la séquence littérale. M'a coûté deux tentatives ratées. Dès qu'un script contient des antislashs : l'écrire avec l'outil Write dans le scratchpad puis l'exécuter, jamais en heredoc.
