---
name: chantier-francais-fabrique-en-js
description: "i18n JS : le moteur traduit TOUT ce qui arrive dans le DOM — seules 3 familles lui échappent (alert/prompt/confirm, document.title réécrit, phrases à valeur). ~190 chaînes au total, pas 646 ; les 5 pages détachées sont faites (31/07/2026)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-31T05:10:22.296Z
---

## La règle qui change tout

**Une chaîne injectée dans le DOM est traduite par le moteur, sans aucun appel
`rcT`.** Vérifié à l'écran : les infobulles de la barre de statut, écrites en dur
dans `logx_statusbar.js`, s'affichent en allemand telles quelles.

Le moteur ne peut PAS attraper trois familles, et seulement celles-là :

| famille | pourquoi | quoi faire |
|---|---|---|
| `alert()` / `prompt()` / `confirm()` | ne passent jamais par le DOM | `rcT(...)` |
| `document.title = …` réécrit en JS | `translateTitle()` ne lit que le titre INITIAL | `rcT(...)` |
| **phrases à VALEUR** (`` `Aucun spot sur ${b} MHz` ``) | la phrase assemblée change → ne peut être aucune clé | `rcTf('… {b} …', {b})` — **modifier le code appelant** |

## Correction d'une erreur de mesure (31/07/2026)

J'avais annoncé **646 chaînes à traduire**. Très large surestimation : je comptais
tout littéral français d'un fichier JS, sans distinguer ce que le moteur attrape
déjà. Mesure refaite avec la grille ci-dessus : **~190**, dont ~176 phrases à
valeur. Une bonne part des alertes de `logx_logbook.js` passait déjà par un
helper local `trF()` à paramètres.

**Why:** un inventaire qui ne reproduit pas le comportement du moteur invente du
travail — et fait courir le risque d'« écraser » des traductions existantes, comme
c'est arrivé avec TABLEAU DE CHASSE (voir
[[piege-faux-dom-stub-et-passes-paires]]).

## État au 31/07/2026 (commit `2e74085`, branche `feat/i18n-js-textes-fabriques`)

✅ **Fait** : les 5 pages détachées (`bande`, `scope`, `panel`, `mobile`, `wall`) —
23 clés, 161 entrées, 30 appels `T()`/`Tf()`, un repli local identité par page.

⬜ **Reste** : `logx_configuration.html` (~68 phrases à valeur), `logx_logbook.js`
(~53), `carte` (12), `calendrier` (10), `propagation` (7), `chasse` (5),
`departements` (3).

**How to apply:**
- Poser un repli local par page (`const T`/`const Tf`), motif de
  `logx_statusbar.js` — ne jamais supposer que `window.rcTf` existe.
- **Le script d'insertion doit refuser d'écrire si une traduction perd ou renomme
  un trou `{x}`** : `rcTf` remplace APRÈS traduction, un trou oublié laisse
  `{call}` à l'écran, dans une seule langue, sans que rien ne le signale.
- Ne pas créer de clé dont les 7 traductions seraient identiques (`{n} km`) :
  du bruit dans un dictionnaire déjà long.
- Écrire ces scripts avec l'outil Write, **jamais en heredoc bash** : les ancres
  contiennent des antislashs (`\'` des chaînes JS) et le heredoc en mange un
  niveau — piège rencontré 4 fois.
- Ces fichiers sont en **CRLF** : une ancre multiligne écrite en `\n` ne
  correspond à rien.
