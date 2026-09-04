# SSTV — Robustesse d'acquisition VIS + banc à fading (QSB)

**Date :** 2026-09-04
**Auteur :** F4GLD + Claude (brainstorming)
**Statut :** design validé en cadrage, en attente de relecture spec avant plan d'implémentation
**Suite de :** `2026-09-03-sstv-robustesse-rx-et-modes-design.md` (Lot A/B) — voir sa §10.

---

## 1. Contexte et motivation

Le Lot A (spec du 03/09) a livré un banc de mesure SNR + trois leviers DSP
(A1 rejeté inerte, A2/A3). **Constat mesuré et diagnostiqué (§10 du Lot A) :**
aucun levier n'abaisse le SNR de décrochage sur le banc **AWGN**, pour deux
raisons structurelles :

1. **Le genou de décrochage est gouverné par l'ACQUISITION de l'en-tête VIS.**
   Si le VIS ne se décode pas, il n'y a **pas d'image du tout** — le reste
   (synchro, estimation pixel) ne joue jamais. Or l'acquisition VIS est
   aujourd'hui **100 % à seuils durs et instantanés** (vérifié dans
   `logx_sstvdecoder.js`) :
   - `_chercherLeader` : compte les échantillons dans `|f − 1900| < 75` Hz,
     exige ≥ 100 ms cumulées ; un craquement décrémente le compteur.
   - `_verifierStart` : moyenne de `f` sur `[5 ; 25] ms`, accepte si
     `|moy − 1200| ≤ 100` Hz.
   - `_lireBitsVis` : 9 créneaux de 30 ms, **décision DURE par bit**
     (`f < 1200 → 1`), parité paire, bit de stop.
   Sous bruit, ces décisions instantanées lâchent **avant** tout le reste.

2. **Le banc ne modélise que l'AWGN, pas le FADING (QSB).** Or le symptôme
   rapporté par F4GLD (« décrochage sur signal faible / QSB ») est en grande
   partie du **fading** — une variation lente d'amplitude que l'AWGN ne
   représente pas. On ne peut donc **pas mesurer** la robustesse à ce que
   l'opérateur vit réellement.

**Objectif de ce chantier :** rendre l'acquisition VIS robuste au bruit,
modéliser le fading pour pouvoir MESURER, et tenir l'image pendant un
évanouissement — les trois étant liés (le fading est ce qui fait échouer
l'acquisition et corrompt l'image).

## 2. Périmètre

**Dans le périmètre (les trois, décision F4GLD) :**
- **F1 — Banc à fading Rayleigh plat** (préalable à toute mesure honnête).
- **F2 — Acquisition VIS robuste** (leader/start par énergie-corrélation, bits
  VIS en décision douce + correction guidée par la parité).
- **F3 — Image sous fading** (squelch sur l'amplitude : geler le recalage de
  synchro et tenir le pixel pendant un évanouissement).

**Hors périmètre :**
- L'émission RF / PTT / CAT (inchangés).
- Un modèle de fading **sélectif en fréquence** (Watterson multi-trajets) —
  écarté (§9) : la SSTV est à tonalité unique étroite, un fading **plat**
  (non sélectif) est le bon modèle.
- Le filtre adapté sur tout le VIS (un gabarit par mode) — écarté (§9) au
  profit de l'évolution incrémentale.

**Ordre décidé :** F1 d'abord (sans banc, « c'est mieux » est invérifiable —
règle du dépôt), puis F2, puis F3.

## 3. F1 — Modèle de fading Rayleigh plat (banc)

**Modèle.** Fading **plat** (non sélectif en fréquence, adapté à la tonalité
SSTV étroite) à enveloppe **Rayleigh**, band-limité par un **taux de fading**
(étalement Doppler) réglable :

1. Générer un processus **gaussien complexe** (I et Q gaussiens indépendants),
   **filtré passe-bas** à `tauxHz` (le taux de fading / Doppler) — c'est ce
   filtrage qui donne la corrélation temporelle d'un vrai QSB (fading lent =
   `tauxHz` petit).
2. Enveloppe = **module** de ce processus (loi de Rayleigh).
3. **Normaliser** l'enveloppe en puissance moyenne unité (le fading redistribue
   la puissance dans le temps, il ne l'ajoute pas).
4. Multiplier le signal réel par l'enveloppe, PUIS ajouter l'AWGN au SNR cible
   (le fading module le signal ; le bruit du récepteur, lui, est constant).

**Reproductible :** graine fixe (LCG + Box-Muller, comme `bruitGaussienSnr` du
banc actuel) — un échec se rejoue à l'identique (règle du dépôt).

**Sweep.** La mesure devient à **deux dimensions** : `(SNR × tauxHz)` (ex. SNR
30→0 dB, taux 0,1 / 0,5 / 1 / 2 Hz). Métrique par point : **acquisition VIS
réussie (oui/non)** ET **MAE image** sur la portion reçue. Le « décrochage »
devient une SURFACE, pas une courbe.

**Réutilise** l'infrastructure du banc existant (`test_sstv_robustesse.py` :
`sstvEncodeSamples`, `bruitGaussienSnr`, `mesureSnr`, `_snr_decrochage`).
Nouveau : `fadingRayleighPlat(sig, tauxHz, graine)` et une variante de
`mesureSnr` acceptant un `tauxFading`.

## 4. F2 — Acquisition VIS robuste (approche incrémentale, option-gatée)

Remplacer les décisions **instantanées à seuil** par des décisions **par
énergie / corrélation sur fenêtre**, en réutilisant le Goertzel corrélé
introduit par A3. Gaté par une option de constructeur (défaut activé), sur le
modèle A2/A3, pour rester mesurable A/B et contre-épreuvable par mutation.

- **Leader (1900 Hz)** — au lieu de compter les échantillons `|f − 1900| < 75`,
  intégrer l'**énergie à 1900 Hz** sur une fenêtre glissante (Goertzel) ;
  déclarer le leader quand cette énergie est soutenue au-dessus d'un seuil
  relatif. Robuste au bruit (intègre) et aux craquements (n'effondre pas un
  compteur instantané).
- **Bit de start (1200 Hz)** — corrélation d'énergie à 1200 Hz sur la durée du
  start (30 ms) au lieu d'une moyenne de fréquence seuillée.
- **9 bits VIS — décision DOUCE.** Par créneau de 30 ms, comparer l'**énergie à
  1100 Hz** (bit = 1) à l'**énergie à 1300 Hz** (bit = 0) — décider par la plus
  grande, et conserver une **confiance** (écart normalisé, pondéré par
  l'amplitude). Puis :
  - **Correction guidée par la parité** : si la parité paire échoue, **retourner
    le bit le moins sûr** (la confiance la plus faible) et revérifier —
    correction d'une erreur unique, très fréquente près du seuil. Si la parité
    reste fausse après un retournement, rejeter (pas d'invention).
  - Le bit de **stop** (1200 Hz) reste vérifié (garde anti-faux-positif).

**Ce qui ne change pas :** la machine à états (leader → vis-start → vis-bits →
image), la table `SSTV_MODES`, le rejet des codes VIS inconnus / parité
définitivement fausse. On durcit la DÉTECTION, pas la sémantique.

**Critère F2 :** sur le banc (AWGN et fading), l'option abaisse le SNR
d'**acquisition VIS réussie** d'une marge mesurable, **sans** augmenter le taux
de faux positifs (un VIS accepté à tort = 2 min de garbage au mauvais timing)
ni régresser l'acquisition en clair.

## 5. F3 — Tenir l'image pendant un évanouissement (squelch, option-gatée)

Pendant un fade, l'amplitude I/Q (`this._lastAmpl`, exposée par A1) s'effondre :
la fréquence instantanée devient du bruit, ce qui (a) **corrompt le recalage de
synchro** (t0 dérive sur du bruit) et (b) **écrit des pixels de bruit**.

Levier (gaté par option, défaut activé) : un **squelch sur `_lastAmpl`** —
quand l'amplitude passe sous un seuil (relatif à sa moyenne récente) :
- **geler le recalage de synchro** (`_recalerSyncCorr` / `_recalerSync` ne
  s'appliquent pas) → t0 est **préservé**, l'image ne penche pas à cause du
  fade ;
- **tenir le pixel** : ne pas écrire la valeur bruitée — **conserver la dernière
  valeur écrite** de cette cellule (repli le plus simple et sans nouvel état
  d'image) plutôt qu'un point aberrant.
Récupération **automatique** dès que l'amplitude revient : t0 intact, la synchro
reprend sur les impulsions suivantes.

`_lastAmpl` est donc enfin PLEINEMENT utile (c'était le seul acquis d'A1) : non
comme limiteur (inerte, prouvé), mais comme **détecteur d'évanouissement**.

**Critère F3 :** sur le banc fading, à SNR clair mais fading marqué, l'image
reste exploitable (MAE sous seuil) là où, sans squelch, un fade fait pencher ou
tacher l'image. Sans régression AWGN ni en clair.

## 6. Stratégie de validation

- **Banc synthétique (F1)** : baseline + non-régression chiffrées sur la
  surface `(SNR × fading)`, pour F2 et F3.
- **Méthode (règle du dépôt)** : pour chaque levier, **témoin vert** d'abord,
  puis **contre-épreuve par mutation** (remettre le défaut, voir rougir,
  restaurer). Propriétés **structurelles/comportementales**, pas de présence de
  chaîne.
- **A/B par option** (comme A2/A3) : chaque levier gaté par une option de
  constructeur (défaut activé), pour mesurer on vs off et empêcher le test de
  rôtir après fusion.
- 🚨 **Piège du faux positif VIS.** Durcir l'acquisition ne doit PAS augmenter
  les VIS acceptés à tort (parité + stop restent des gardes). Un test dédié
  vérifie que la correction guidée par la parité **ne valide jamais** un VIS
  dont la parité était structurellement fausse (pas une simple erreur unique).
- **Honnêteté (règle du dépôt)** : si un levier n'apporte pas de gain mesuré,
  il est **rejeté** (comme A1), pas gardé « au cas où ». Le bilan chiffré (comme
  la §10 du Lot A) dira ce qui marche, avec les chiffres.

## 7. Architecture / fichiers touchés

- `concours/logx_sstvdecoder.js` — options de constructeur pour F2 (acquisition
  VIS) et F3 (squelch) ; réutilise le Goertzel d'A3 et `_lastAmpl` d'A1. Les
  fonctions touchées : `_chercherLeader`, `_verifierStart`, `_lireBitsVis`
  (F2) ; `_decoderImage` / le recalage + `_finaliserCellule` (F3). Branches OFF
  = comportement historique bit-à-bit (A/B).
- `concours/tests/test_sstv_robustesse.py` — `fadingRayleighPlat`, sweep 2D
  `(SNR × fading)`, tests F2 (acquisition) et F3 (image sous fade), garde
  anti-faux-positif VIS.
- **Non modifié :** `logx_tx_audio.js`, PTT, CAT, la table des modes.

## 8. Décisions et alternatives écartées

- **Watterson (ITU-R F.1487) — écarté.** Modèle HF de référence mais **sélectif
  en fréquence** (2 trajets) : surdimensionné pour une tonalité SSTV unique et
  étroite, et bien plus lourd à implémenter/tester. Le fading **plat** Rayleigh
  capture le QSB pertinent pour la SSTV.
- **QSB déterministe sinusoïdal — écarté comme modèle principal**, éventuellement
  conservé comme cas de non-régression verrouillé simple si utile ; moins
  réaliste qu'un vrai fading aléatoire band-limité.
- **Filtre adapté sur tout le VIS (un gabarit par mode) — écarté** au profit de
  l'évolution incrémentale (énergie + décision douce) : ~14 gabarits +
  alignement temporel pour un gain incertain sur le gain déjà attendu de la
  décision douce. Reste une évolution conditionnelle si la mesure le justifie
  (YAGNI, même doctrine que l'« approche 2 » du Lot A).
- **Ordre F1 → F2 → F3** : le banc d'abord (mesurer avant de toucher), puis
  l'acquisition (le genou), puis l'image (ce qui reste une fois qu'on acquiert).

## 9. Séquencement d'implémentation

1. **F1** — `fadingRayleighPlat` + sweep 2D + baseline chiffrée
   `(SNR × fading)` des modes actuels (aucune modif décodeur).
2. **F2** — acquisition VIS robuste (option), mesurée : gain d'acquisition
   chiffré ou rejet, garde anti-faux-positif.
3. **F3** — squelch image sous fade (option), mesuré : gain image sous fading
   chiffré ou rejet.
4. **Consolidation** — non-régression des modes existants (AWGN ET clair) +
   bilan chiffré (surface `(SNR × fading)`, on vs off), écrit en spec.

## 10. Risques

- **Faux positifs VIS** en durcissant l'acquisition → atténué par le maintien
  parité + stop et un test anti-faux-positif dédié.
- **Régression des modes existants** en touchant le front-end commun →
  atténué par les branches OFF bit-à-bit et la non-régression AWGN/clair avant
  fusion.
- **Modèle de fading trop simplifié** → assumé : fading plat Rayleigh, pas
  Watterson ; le banc chiffre une robustesse RELATIVE (on vs off, avant/après),
  pas une perf terrain absolue. La vraie validation reste un essai on-air, non
  disponible ici (pas de radio) — honnêteté maintenue.
- **Aucun gain mesuré** possible pour F2 ou F3 → c'est un résultat valide
  (rejet chiffré, comme A1), pas un échec du chantier.

## 12. Résultats mesurés (VIS + fading)

Bilan de fin de chantier (Task 4, 2026-09-04). Trois leviers livrés, tous
option-gatés (défaut ON, A/B toggleable), zéro régression mesurée sur les
14 modes existants. Chiffres tirés directement des sorties `pytest -s` des
tâches 0-3 (task-0/1/2/3-report.md) et de la consolidation ci-dessous — aucun
n'est inventé ni extrapolé au-delà de ce qui a tourné sur ce banc.

### 12.1 F2 — Acquisition VIS robuste : le vrai gain du chantier

C'est le levier qui a trouvé le vrai « genou » de robustesse, là où le Lot A
précédent (A1 limiteur d'amplitude, A2 estimation de pixel) s'était révélé
inerte sous AWGN pur (A1 rejeté, gain 0 dB mesuré à l'algèbre près ; A2 gain
mesurable seulement sur un signal fabriqué à amplitude effondrée, pas sur ce
banc). F2 casse cette série : sur le banc AWGN sans fading (`test_f2b_gain_
acquisition_sous_bruit`, R36) —

| | SNR minimal encore acquis |
|---|---|
| **on** (`acqVisRobuste:true`) | **2 dB** |
| **off** (historique) | **10 dB** |

Étendu au sweep bas (`lignes=10`) sur M1/S1/R36/PD90 : **on descend à 0 dB**
partout contre **10 dB** pour off — soit **~8 à 10 dB** de SNR gagnés pour
l'acquisition du VIS, uniforme entre les 4 familles testées.

**Sous fading, le gain est asymétrique — honnêteté par taux** (task-1-report.md,
sweep [12,10,8,6,4] dB, taux d'acquisition on/off) :

| mode | fading LENT 0.2 Hz on/off | fading RAPIDE 1.0 Hz on/off |
|------|---------------------------|-----------------------------|
| M1   | **0.40 / 0.00**           | **0.00 / 0.00**             |
| S1   | **0.60 / 0.00**           | 0.20 / 0.00                 |
| R36  | **0.60 / 0.00**           | **0.00 / 0.00**             |
| PD90 | **0.80 / 0.00**           | 0.20 / 0.00                 |

- **Fading LENT (0.2 Hz)** — le plus destructeur de la baseline F1 : c'est là
  que F2 compte, l'historique n'acquiert **rien** (0.00) et le robuste récupère
  **0.40 à 0.80** selon le mode. Vrai gain.
- **Fading RAPIDE (1.0 Hz)** : F2 est **quasi NIL** — pour **M1 et R36 le gain
  est exactement nul** (0.00 on = 0.00 off, identique à l'historique) ; S1 et
  PD90 ne récupèrent qu'un mince 0.20. Les creux rapides sont trop courts et
  trop profonds pour que l'intégration ~10 ms de l'énergie les traverse.

Donc **la généralisation « 0.4-1.0 selon le taux » serait fausse** : le plancher
réel sous fading rapide est **0.00** pour la moitié des modes testés. F2
robustifie l'acquisition sous AWGN et sous fading **lent**, pas sous fading
rapide.

**Décomposition honnête du gain** (task-2-report.md) : la quasi-totalité du
gain vient du **leader par énergie glissante (F2a) + start par énergie + bits
VIS doux (F2b)** — la détection intègre le bruit sur ~10 ms au lieu de décider
sur un seuil de fréquence instantanée. La **correction guidée par la parité**
(retournement d'UN bit ambigu, gardé par un seuil de confiance `<0.5`) montre
en revanche un **gain d'acquisition AWGN non mesurable** : neutralisée, elle
donne des taux d'acquisition quasi identiques (R36/M1/S1, 30 graines,
1.00/0.97/0.83/0.47/0.13-0.17 dans les deux cas) — le décrochage AWGN vient du
leader/start, pas d'erreurs de bit isolées. Elle est gardée quand même car
elle **récupère structurellement un bit réellement ambigu isolé**
(`test_f2b_correction_parite_recupere_un_bit_ambigu`, cas plausible sous
fading corrélé plutôt qu'AWGN pur) et n'introduit **aucune régression ni
aucun faux positif** (0/600 sur stress `pariteFausse`, 0/30 vs 0/30 sur bruit
pur — task-2-report.md §addendum).

**Garde anti-faux-positif structurellement verrouillée** : un en-tête à
parité sciemment fausse n'est **jamais** accepté, acquisition robuste ou non
(`test_f2b_pas_de_faux_positif_vis`, contre-épreuve par mutation faite —
neutraliser la garde `!pariteOk` fait accepter 3/3 en-têtes corrompus). Sur
bruit pur (aucun signal SSTV, 30 graines × 3 s), le chemin robuste n'accepte
**pas plus** de VIS fantômes que l'historique (0/30 des deux côtés).

### 12.2 F3 — Squelch image sous fading : gain modeste, honnête sur sa limite

Gain MAE (off − on, positif = amélioration), fading **rapide** (1 Hz), image
entière (task-3-report.md §4) :

| Mode | 30 dB | 24 dB | 18 dB |
|---|---|---|---|
| M1 | +0.40 | +0.59 | +1.12 |
| S1 | +0.31 | +0.48 | +0.95 |
| R36 | +0.24 | +0.73 | +1.70 |
| PD90 | +0.47 | +0.90 | +1.68 |

Gain **systématiquement positif** (jamais de régression), croissant quand le
SNR baisse — mais modeste (+0.24 à +1.7 niveau de MAE sur une échelle 0-255).

**Limite honnête** : sous fading **lent** (0.2 Hz) — le taux identifié par la
baseline F1 comme le PLUS destructeur (il fait décrocher M1/S1/R36/PD90 dès
15 dB contre 9 dB sans fading) — le squelch est **NIL** : le seuil détecte un
creux via le ratio `amplitude instantanée / moyenne glissante`, et une moyenne
causale à `τ=600 ms` suit une déclinaison lente d'enveloppe d'assez près pour
que le ratio ne descende jamais sous `squelchK=0.35` — le creux n'est jamais
vu comme un creux. F3 agit sur le fading RAPIDE, pas sur le lent, qui reste le
cas le plus dur du chantier sans réponse. Sans fading, l'effet est nul et
strict (`|on−off| < 1e-6` mesuré) : le squelch ne se déclenche jamais en clair
(marge conçue : le plancher d'amplitude en clair reste à 0.41-0.65 selon
SNR/mode, bien au-dessus du seuil 0.35).

**Décision : GARDÉ, défaut ON** — gain réel et sans contrepartie sous fading
rapide, honnêtement inefficace (mais pas régressif) sous fading lent.

### 12.2bis Complémentarité F2/F3 — la ligne de fond honnête

Les deux leviers se répartissent le terrain de façon presque exactement
complémentaire, et **aucun ne couvre le cas le plus dur** :

| Canal | F2 (acquisition VIS) | F3 (image sous fade) |
|---|---|---|
| AWGN pur | **~8-10 dB** de gain | nul (par construction, pas de creux) |
| Fading LENT (0.2 Hz) | **0 → 0.4-0.8** (vrai gain) | **NIL** (moyenne causale suit le creux) |
| Fading RAPIDE (1.0 Hz) | **NIL** (M1/R36 = 0.00 ; S1/PD90 = 0.20) | **+0.24 à +1.7 MAE** (vrai gain) |

- **F2 aide l'AWGN et le fading LENT** (les creux prolongés font échouer la
  décision par seuil instantané, que l'énergie intègre).
- **F3 aide le fading RAPIDE** (les creux courts et profonds sont détectables
  par le ratio amplitude/moyenne, et le sample-and-hold recopie la dernière
  bonne ligne).
- **Le cas le plus dur reste sans réponse** : l'ACQUISITION VIS sous fading
  LENT ET profond — F2 la récupère partiellement (0.4-0.8) mais pas
  entièrement, et F3 (image) n'entre en jeu qu'APRÈS l'acquisition. Un fading
  lent qui noie l'en-tête VIS reste le mur du chantier.

### 12.3 F1 — Banc de fading : livrable d'instrumentation

Aucun gain direct à rapporter (F1 est le banc, pas un levier DSP) : il a
livré `fadingRayleighPlat` (enveloppe Rayleigh band-limitée, 1 pôle à
`tauxHz`, normalisée en puissance) et le balayage 2D `(SNR × taux de fading)`
qui a permis de MESURER F2 et F3 ci-dessus, et d'établir que le fading lent
(0.2 Hz) est plus destructeur que le fading rapide (1.0 Hz) à SNR égal — sans
ce constat, F3 n'aurait pas pu être évalué sur son vrai point faible.

### 12.4 Non-régression — consolidation finale

`test_consolidation_pas_de_regression` (8 familles témoins M1/M2/S1/S2/SDX/
R36/R72/PD90, `concours/tests/test_sstv_robustesse.py`) : aux défauts
(`acqVisRobuste:true`, `squelchFade:true`), chaque mode reste acquis et
exploitable à 30 dB sans fading, MAE non dégradé de plus de 2 niveaux vs la
config tout-off historique (`acqVisRobuste:false`, `squelchFade:false`).
**8/8 vert.** Témoin de mutation fait (forcer `enFade=true` en permanence
dans `_decoderImage`, simulant une régression F3) : les 8 cas passent au
ROUGE (MAE PD90 2.2 → 139.1, tous > seuil) — restauré, md5 du décodeur
identique avant/après (`ffaec56e7a3f2eb191b504fede95f849`), retour au vert
confirmé.

Suite complète de robustesse (`test_sstv_robustesse.py`) : **47 passed**
(39 avant Task 4 + 8 nouveaux). Suite historique complète
(`test_sstv_decodeur.py`, les 43 tests de comportement du décodeur AVANT ce
chantier) : **43 passed** — inchangée, aucune régression sur les 14 modes
existants.

### 12.5 Limite globale assumée

Ce banc mesure une robustesse **RELATIVE** (levier on vs off) sur un canal
synthétique (bruit blanc gaussien + fading Rayleigh plat band-limité), pas
une performance terrain absolue : pas de bruit impulsionnel, pas de
sélectivité récepteur, pas de fading Watterson multi-trajet, pas de QRM
co-canal. **L'essai on-air (F4GLD, radio réelle) reste hors de portée ici**
(pas de radio disponible pendant ce chantier) et constitue la vraie preuve de
terrain qui manque encore avant de considérer le sujet clos.
