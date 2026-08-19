---
name: chantier-etude-ia-cinq-points-2026-08-01
description: "Étude « ce que l'IA pourrait apporter » → 4 points sur 5 étaient des BUGS ou du code débranché, pas des manques d'IA (01/08/2026)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-01T08:29:49.672Z
---

F4GLD a demandé une étude des apports possibles de l'IA, puis « attaque ça » sur
les recommandations. Fusionné dans `main` en `eea01a7`, CI verte, suite passée
de 3092 à **3223 tests**.

**LE RÉSULTAT LE PLUS UTILE DE L'ÉTUDE : sur 5 points, 4 étaient des bugs
produit ou du code écrit-testé-débranché.** Une seule vraie nouveauté (l'école
de CW), et elle ne consomme aucune requête IA.

1. **Modèle IA codé en dur** — `logx_carte.html` envoyait
   `model:'claude-sonnet-4-6'`, qui écrasait le choix CONFIG. Chat MORT chez
   OpenAI/Mistral/xAI/DeepSeek/Gemini (nom Claude envoyé à leur API), et Opus
   ou Haiku ignorés en silence. Symptôme trompeur : la veille automatique passe
   par `/proxy/ai` qui ignorait déjà ce champ → elle marchait pendant que le
   chat échouait. Règle posée : `logx_utils.modele_effectif()`, le modèle
   appartient à la CONFIG ; une page n'en décide jamais.
2. **Filet anti-busted call** — `/call/near` + `near_matches()` existaient,
   testés, **sans aucun appelant** (6e occurrence du motif dans ce projet).
   PIÈGE de ma conception : filtrer sur « déjà travaillé » rejetait
   `F4GLDD → F4GLD` (on ne se travaille pas soi-même). Règle à deux détentes :
   voisin travaillé, sinon SEUL voisin connu.
3. **Horloge sans internet** — dérive mesurée sur le consensus des DT WSJT-X.
   `_decodes` est indexé PAR INDICATIF (le dernier écrase) → flux séparé borné.
   Sens du DT DÉMONTRÉ dans le code, pas recopié : horloge en avance de e →
   fenêtre ouverte e trop tôt → DT = +e.
4. **Format de dépôt** — voir [[piege-liste-identifiants-ecrite-a-la-main]].
5. **École de CW** (`logx_cw_ecole.py`, `logx_cw.html`, `/cw/serie`,
   `/cw/corriger`) — indicatifs tirés de l'index du poste, échange du concours
   réel. 3 défauts trouvés EN NAVIGATEUR : chronométrage faux de 6 % (silence
   inter-caractères + silence de mot cumulés → « PARIS » 3,18 s au lieu de 3,00
   à 20 WPM) ; vitesse jamais transmise au serveur (ramenait toujours à 19) ;
   `exchange_wants()['num']` — **clé inexistante**, donc numéro de série jamais
   envoyé pour 24 concours.

**PIÈGES DE TEST rencontrés, tous deux instructifs :**
- `itemsMenuLogbook()` doit rester PURE : `test_logbook_menu_debut_fin.py`
  l'exécute SEULE dans un V8 nu. Y appeler une fonction globale = 27 tests
  rouges d'un coup. Passer la valeur en PARAMÈTRE.
- Un test qui passe SEUL et **SKIP dans la suite** ne vérifie rien :
  `logx_callhistory.build_index` lit en chemins RELATIFS avec cache, et
  `test_archive.py` fait `monkeypatch.chdir(tmp_path)`. Se replacer dans le
  dépôt + `force=True`.

**Conflit de fusion** : la tâche `datetime.utcnow()` lancée en parallèle a
atterri sur `main` pendant le chantier (ajout de `logx_utils.utcnow()` /
`as_naive_utc()`). Conflit bénin sur un import, résolu en gardant les deux.
