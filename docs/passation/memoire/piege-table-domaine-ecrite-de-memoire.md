---
name: piege-table-domaine-ecrite-de-memoire
description: "Le skill radioamateur existe et je ne l'avais JAMAIS chargé — la table de plan de bandes venait d'un manuel nord-américain, FT8 passait pour de la phonie sur 6/2/70 cm"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-31T14:08:18.736Z
---

**Charger le skill `anthropic-skills:radioamateur` AVANT d'écrire ou de modifier
toute table de domaine radio** : plan de bandes, segments de mode, fréquences
d'appel, puissances, préfixes, code Q. Il contient les valeurs chiffrées IARU
R1 / France (`references/reglementation.md` et 11 autres fiches).

**Why :** le 31/07/2026 F4GLD m'a demandé « est-ce que tu as utilisé le skill
radioamateur ? ». Non — pas une fois de tout le chantier. J'avais écrit le matin
même une table de plan de bandes et une déduction CW/numérique/phonie, reprise
de l'annexe C du manuel **CC Cluster — qui décrit l'Amérique du Nord**, sans
vérifier à quelle région UIT elle s'applique. Quatre défauts, tous mesurés :

1. **FT8 classé PHONE sur 6 m, 2 m, 70 cm et CW sur 160/80/12 m** — 6 bandes sur
   12. C'était la suite directe du bug que l'utilisateur avait signalé (« en SSB
   je veux voir QUE les spots SSB ») et que j'avais **annoncé corrigé**.
2. Bornes région 2 : 40 m jusqu'à 7,300 · 80 m jusqu'à 4,000 · 2 m jusqu'à 148 ·
   et une **bande 222 MHz qui n'existe pas en région 1**. Un clic sur un spot
   placé là commandait un QSY hors bande.
3. Le **4 m (70 MHz) proposé comme bande standard** : attribué dans plusieurs
   pays de région 1, **pas en France**.
4. Une **bande WARC pouvait recevoir le liseré « recommandée » pendant un
   concours**, où la convention IARU les interdit.

**How to apply :**
- Le piège de fond : **le plan officiel et l'usage réel ne coïncident pas**.
  144,174 MHz est dans le segment « SSB » du plan IARU R1 et c'est pourtant LA
  fréquence FT8 du 2 m. Un découpage par plages ne peut pas y arriver seul — il
  faut une table de fréquences d'appel numériques consultée **avant** le plan.
  Ces fréquences sont identiques dans les 3 régions, c'est tout l'intérêt de la
  convention.
- **Classer un spot ≠ dessiner la bande de l'opérateur.** Une station de région 2
  à 7,250 MHz est en règle chez elle : la classer PHONE est juste, mais la
  réglette doit s'arrêter à l'allocation française. D'où un drapeau par ligne
  dans `_CRENEAUX_KHZ` (`logx_awards.py`) et `hors_bande_france()` qui **marque**
  au lieu de masquer.
- **Ne pas affiner les sous-segments de mode de mémoire.** La fiche donne les
  bornes d'allocation et renvoie explicitement au TNRBF (ANFR) et au plan IARU R1
  pour les segments, qui évoluent après chaque CMR. Les inventer est exactement
  ce qui a produit ce chantier.
- 4 tests ont dû être **réécrits, pas rafistolés** : ils affirmaient les bornes
  nord-américaines, en vert. Voir [[piege-verifier-sur-donnees-reelles]].

Corrigé par `86b0bb2` / fusion `46a8edc`. La 0.9-beta10, publiée une heure plus
tôt, **contient encore ces défauts**.

## 2ᵉ passe (le skill avait grossi : 34 fiches au lieu de 12)

Cinq fiches sur le **pilotage CAT** et une sur l'**ADIF** sont apparues — soit
exactement ce que le logiciel implémente. Trois défauts de plus, dans
`logx_cat.py`, corrigés par `d18d763` / fusion `459b38b` :

1. **`SSB` n'atteignait AUCUNE table de mode, sur aucune marque** (5 modes du
   carnet sur 12 arrivaient quelque part). Le carnet parle *SSB/FT8/PSK*, la
   radio veut *LSB/USB*. Cliquer un spot changeait la fréquence et laissait la
   radio dans son mode précédent — l'échec était **avalé** (`set_freq` ignorait
   le retour de `set_mode`). **Deux conventions qui ne se déduisent pas l'une
   de l'autre** : phonie = LSB sur 160/80/40 m puis USB ; **numérique = USB sur
   TOUTES les bandes**, y compris là où la phonie est en LSB. Appliquer la
   règle de la phonie au FT8 met la radio en LSB sur 7,074 → inaudible.
2. **La fréquence partait à 11 chiffres à tout le monde**, alors que le CAT
   ASCII Yaesu est à champs de largeur fixe et attend **9** chiffres pour `FA`.
   Le code se contredisait : `_IF_FIELDS` déclare bien 9 pour *lire*. On lisait
   9, on écrivait 11 → sur FT-891/991/FTDX, **le QSY ne marchait pas**.
3. **FT-817/818/857/897 proposés** alors qu'ils sont en CAT **binaire 5 octets**
   et que le pilote ne parle qu'ASCII : silence total, indiscernable d'un câble
   débranché. Marqués « via rigctld/Hamlib », refusés **avant** l'ouverture du
   port.

**Ce qui était bon** : les 29 adresses CI-V Icom correspondent toutes à la
fiche, modèle par modèle. Ne pas tout suspecter — vérifier.

**Ne pas corriger le code sur une fiche qui se contredit** : la fiche Icom
donne `05` pour FM *et* pour FSK-R ; le code a la table standard, laissé tel
quel. Idem pour le code de mode Yaesu `9`.

**Reste à confirmer sur du matériel réel** (je n'ai pas de poste) : le format
`FA` à 9 chiffres. F4GLD a confirmé en opérateur que **4800 reste le bon repli
Yaesu** (valeur d'usine des FT-8x7 et des FT-840/900/1000) — figé par un test ;
la page prévient désormais que les postes pilotés en natif sortent plus haut.

## 3ᵉ passe — locator et 2ᵉ table de bandes (`0a44cea`+`e166298`, fusion `2f48b96`)

- **`locator_to_latlon` n'avait AUCUNE validation** côté serveur (le `except:`
  nu ne rattrapait que le `int()`). `JN18ZZ` → 49,06 N, **hors de son propre
  carré** ; `ZZ99XX` → longitude 339° ; `JN18@@` → point avant le coin. Les
  **trois copies JavaScript validaient déjà** par regex : seul Python acceptait
  tout, et 82 appels en dépendent. En THF un locator faux = multiplicateur faux
  = points refusés.
- **Tout locator à 4 caractères tombait 3,8 km au nord-est du centre.** Le code
  complétait par `'MM'` : 'M' est la 13ᵉ lettre, or le milieu des 24 lettres
  n'en est **aucune** (entre 'L' et 'M'). **Aucun complément par lettres ne peut
  donner le centre** — il faut le calculer (+1° lon, +0,5° lat).
- **Le test figeait le défaut** : il exigeait `locator('JN15') ==
  locator('JN15MM')`, c'est-à-dire la *façon* dont le calcul était fait, pas le
  résultat. Un test écrit ainsi ne peut jamais attraper l'erreur qu'il contient.
- **Il y avait une SECONDE table de bandes** — `logx_transverter.BANDES_MHZ` —
  restée en région 2 (6 m→54, 2 m→148) après correction de la première. Réflexe
  à garder : **après avoir corrigé une table de domaine, chercher ses jumelles**
  (`grep` sur une borne caractéristique). Un **test croisé** compare désormais
  les deux borne à borne — ça vaut mieux que la correction elle-même.

**Bon, vérifié, non touché** : calcul du centre de sous-carré exact à 1e-9 sur
les 4 coins du monde ; haversine à <1,5 km de la formule de référence ; azimut
de grand cercle correct ; les 19 satellites et leurs avertissements de statut.

**Gap assumé et figé par un test** : pas de segments de mode au-dessus de
440 MHz (réglette vide en 23 cm+). La fiche donne les *allocations* mais renvoie
au plan IARU R1 pour le découpage par mode — ne pas l'inventer.

## 4ᵉ passe — EME (`43880a4`, fusion `3be8bf1`)

- **`path_loss_db` était fausse de 123 dB** : elle calculait la perte en espace
  libre d'un trajet **simple** puis la **doublait en dB**. Doubler des décibels
  = élever le rapport de puissance au carré ; ça ne décrit aucune physique.
  374,6 dB à 144 MHz au lieu de 252, et une loi en **f⁴ au lieu de f²**.
  Le docstring appelait ça « le plancher théorique » faute d'albédo — une
  **justification, pas une mesure**. Remplacé par l'équation radar
  `L = 10·log10((4π)³d⁴/(λ²σ))`, σ = albédo 6,5 % × π·R² (R = 1738 km).
- **Ce qui valide deux constantes physiques, ce n'est pas leur provenance mais
  qu'un seul jeu redonne TOUTES les valeurs de référence** : ici les trois
  bandes à <0,4 dB, la loi en f² (9,5 dB/triplement) et les ~2 dB
  périgée/apogée qui tombent tout seuls.
- **Le meilleur test n'a besoin d'aucune valeur absolue** : la loi en fréquence.
  « Tripler la fréquence coûte ~9,5 dB » aurait attrapé le défaut sans connaître
  une seule référence.
- **Elle n'avait AUCUN appelant** — seule des 5 fonctions du module dans ce cas.
  D'où 123 dB passés inaperçus. Câblée depuis, au Doppler. Troisième occurrence
  du même piège dans la journée après `popoutBandes()` et `usage_mode`.

**Propagation — aucun défaut substantiable.** Modèle heuristique honnêtement
étiqueté, seuils (MUF, SFI/110, K≥5) cohérents avec la fiche. Deux observations
reportées **sans correction faute de source assez précise** : `a_index` est
récupéré et affiché mais n'entre dans aucun calcul ; K≥5 ne dégrade que les
bandes HAUTES alors qu'un orage géomagnétique touche surtout les basses et les
trajets polaires. Ne pas « corriger » un modèle sur une intuition.
