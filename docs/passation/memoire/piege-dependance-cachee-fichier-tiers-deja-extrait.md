---
name: piege-dependance-cachee-fichier-tiers-deja-extrait
description: "PIÈGE EV-7 : une extraction peut casser un test qui ne mentionne AUCUN identifiant du bloc extrait — la dépendance passe par un TROISIÈME fichier déjà extrait que le test charge et exécute (logx_verif_panel.js lit callDB, test_peer_version_xss.py ne le sait pas)"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T20:01:59.377Z
---

Découvert pendant le 17e incrément EV-7 (extraction Lookup indicatifs vers
`logx_lookup.js`, 08/08/2026). Vient compléter
[[chantier-ev7-callbook-2026-08-08]] (16e incrément), qui avait déjà
montré qu'un grep par nom de fonction sur `tests/` ne suffit pas quand la
dépendance passe par un gestionnaire d'événement simulé.

## Le piège (variante n°2, plus sournoise)

Avant d'extraire, grep exhaustif de `tests/` pour les 19 identifiants du
bloc (6 variables + 13 fonctions) : **1 seul résultat**, un commentaire
prose sans rapport (`refreshCluster()` mentionné dans une docstring de
`test_peer_version_xss.py`, jamais exécuté). Conclusion apparente : aucun
test touché en dehors de la convention `JS_EXTRAITS_EV7`.

**Ce que le grep ne pouvait pas voir** : `test_peer_version_xss.py` charge
`logx_verif_panel.js` (déjà un fichier EV-7 extrait, 4e incrément) puis
appelle réellement `showChecklist()` en V8. Or `showChecklist()` (dans
`logx_verif_panel.js`, PAS dans le fichier de test lui-même) contient
`Object.keys(callDB).length` — une lecture directe de `callDB`, une des
variables du bloc en cours d'extraction. Le nom `callDB` n'apparaît NULLE
PART dans le texte de `test_peer_version_xss.py` : il vit dans un fichier
tiers que le test charge et exécute, invisible à un grep sur le fichier de
test seul.

Résultat sans le correctif : `ReferenceError: callDB is not defined` à
l'exécution de `showChecklist()`, capturé proprement par ce test (contrairement
au 16e incrément où l'échec était silencieux) car ce fichier vérifie
explicitement `_testError` — mais aurait quand même cassé la CI si non
détecté avant le commit.

**Deuxième cas trouvé le même jour, plus classique** : `submitQSO()` (reste
dans `logx_logbook.js`) appelle `updateCallDB(call, loc, null)` — cette
fois la fonction extraite EST bien nommée dans `logx_logbook.js`, donc
détectable par relecture directe du code source (pas du grep sur les
tests), mais `test_macro_cw_serie_bande.py` exerce `submitQSO()` via
`__qso()` sans jamais nommer `updateCallDB` dans son propre texte non plus.

## Réflexe pour tout futur incrément EV-7 (mise à jour du réflexe du 16e)

Avant de conclure "0 test à adapter" sur la seule base d'un grep des
identifiants du bloc dans `tests/`, faire EN PLUS, dans cet ordre :

1. **Lire le VRAI code appelant** (pas seulement grep) : pour chaque
   fonction/variable du bloc, trouver tous ses sites d'appel/lecture dans
   `logx_logbook.js` ET dans TOUS les autres fichiers `logx_*.js` déjà
   extraits par EV-7 (`grep <identifiants> concours/logx_*.js`, pas
   seulement `concours/tests/`).
2. Pour chaque fichier tiers trouvé à l'étape 1 (ex. `logx_verif_panel.js`
   lisant `callDB`), chercher quels fichiers de test le CHARGENT et
   l'EXÉCUTENT réellement (grep du nom du fichier, ex.
   `VERIF_PANEL_JS_PATH`, dans `tests/`) — ce sont des candidats à corriger
   même si le bloc en cours d'extraction n'y est jamais nommé.
3. Pour chaque fonction du bloc appelée depuis une fonction "cœur" restée
   dans `logx_logbook.js` (ex. `submitQSO()`, `onCallInput()`), chercher
   quels fichiers de test EXERCENT réellement cette fonction cœur (motif
   `__qso`/`__run`/appel direct en V8), pas seulement ceux qui la citent en
   texte.
4. Après extraction, lancer la suite ciblée sur TOUS les fichiers identifiés
   aux étapes 2-3 avant de conclure — ne jamais se fier uniquement au grep
   initial, même exhaustif en apparence.
