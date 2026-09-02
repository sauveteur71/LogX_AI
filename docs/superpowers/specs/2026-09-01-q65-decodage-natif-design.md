# Décodage Q65 natif (hors-ligne) dans LogX AI — Design

Date : 2026-09-01
Statut : design validé, prêt pour plan d'implémentation
Branche : `feat/q65-decodage-natif`

## 1. Contexte et motivation

Aujourd'hui LogX AI **reçoit déjà** les décodages Q65/JT65, mais uniquement en
**relayant WSJT-X par UDP** (`concours/logx_wsjtx.py` → `eme_decodes()`,
consommé par le cockpit EME). WSJT-X doit tourner et décoder ; LogX ne fait
qu'afficher.

F4GLD veut que le **décodage natif** soit envisagé. Motivations exprimées
(les quatre, aucune bloquante isolément) :

- **Zéro dépendance externe** — décoder l'EME dans LogX seul, sans lancer
  WSJT-X. Cohérent avec la doctrine « offline-first / antivirus-proof » déjà
  appliquée (carte de sortie, garde-fou `logx_theme.css`).
- **Intégration plus fine** — piloter les paramètres de décodage (AP,
  moyennage, fenêtre) et croiser en temps réel avec le log/Doppler LogX.
- **Fonction que WSJT-X ne fait pas** — pile-up EME orchestré par l'IA,
  large bande. *Découplé du moteur* : se construit par-dessus les décodages,
  quelle qu'en soit la source. **Hors périmètre de ce design.**
- **Exploration / maîtrise de la chaîne.**

Comme aucune motivation n'est bloquante, l'approche est **étagée** et
**opt-in** : on ajoute une source, on ne casse rien.

## 2. Décision de licence — VÉRIFIÉE, pas un obstacle

`LICENSE` du dépôt = **GNU GPL Version 3** (mesuré, `head LICENSE`). WSJT-X est
GPLv3 aussi. LogX AI est public et distribué à des tiers (radioclub, testeurs).

→ **Aucun conflit copyleft.** On peut embarquer *et/ou* lier du code WSJT-X
sans contrainte supplémentaire (obligations GPL déjà remplies : source
publique). Tout le paragraphe du brief d'origine sur « si LogX est sous licence
incompatible… » est sans objet ici.

Obligation à tenir au packaging : livrer/offrir la source correspondante du
`jt9` embarqué et conserver ses mentions de copyright.

## 3. Résultat du spike (mesuré le 2026-09-01, à ne pas re-supposer)

Décodeur ciblé : `jt9.exe` (livré avec WSJT-X). Confirmations **directes** :

- `jt9` **lit un `.wav` en ligne de commande** (`Usage: jt9 [OPTIONS] file1 …
  Reads data from *.wav files.`). Aucune GUI, aucun shared-memory requis.
- Flags utiles : `-3/--q65`, `-6/--jt65`, `-b/--sub-mode A` (→ Q65-60A…),
  `-p/--tr-period 60`, `-d/--depth 1-3`, `-q/--quiet` (supprime
  `<DecodeFinished>`), et **AP gratuit** : `-c` (my-call), `-G` (my-grid),
  `-x` (his-call), `-g` (his-grid), `-Q` (QSO progress), `-X`
  (experience-decode).
- Décodage réel d'un échantillon **EME Q65-60A 6 m** officiel
  (`sourceforge.net/projects/wsjt/files/samples/Q65/60A_EME_6m/210106_1621.wav`) :
  **3 stations décodées à −24, −20, −19 dB** (near-threshold EME), exit 0.
- **Correction au brief** : le `.wav` est **12 kHz mono 16 bit**, PAS 48 kHz.
  jt9 décode en 12 kHz (WSJT-X sous-échantillonne 48k→12k pour les modes
  lents). La chaîne audio LogX devra donc produire du **12 kHz mono**.

### 3.1 Formats de sortie disponibles (à parser)

Trois sorties produites par un décodage (dans le `-a data-path`) :

1. **stdout** : `UTC SNR DT FREQ : message  q0`
   Ex. `0000 -24  2.8  697 :  W7GJ N8JX EN73    q0`
2. `decoded.txt` : `UTC sync SNR DT FREQ ? message MODE`
3. **`q65_decodes.txt`** — le plus riche, retenu pour le parser :
   colonnes internes + `DT`, `FREQ`, `SNR`, un **indice de confiance**
   (0.67 / 0.82 / 0.86 dans le sample) et le message.
   Ex. `… 2.78  696.7 -24.0  0.0 0.67 K1ABC W9XYZ EN37 W7GJ N8JX EN73`

Décision : **parser `q65_decodes.txt`** (SNR + DT + fréquence + confiance),
avec stdout comme repli si le format fichier bouge entre versions de jt9.

### 3.2 Réserve mesurée — JT65 et KVASD

L'aide expose `-e PATH … Location of subordinate executables (KVASD)`. KVASD
est le décodeur deep-search **JT65** séparé et **non-GPL** (redistribution
restreinte). **Q65 n'en dépend pas.** → argument décisif pour faire **Q65
d'abord** (V1 propre côté licence) ; JT65 est un étage ultérieur qui devra
trancher la question KVASD (depth réduite sans KVASD, ou exclusion).

## 4. Périmètre V1

**V1 = réception Q65 hors-ligne dans le cockpit EME, sans WSJT-X lancé.**

Explicitement **hors V1** (chantiers distincts) :

- **Émission Q65 / PTT** — INTERDIT d'y toucher sans le skill
  `tx-human-consent`. Étage séparé, ultérieur, non couvert ici.
- **JT65 natif** — après Q65, avec la réserve KVASD (§3.2).
- **MAP65 / large bande**, **orchestration pile-up par l'IA**, **astronomie
  autonome** (le cockpit EME a déjà suivi Lune + Doppler).

## 5. Décisions d'architecture (tranchées avec F4GLD)

1. **Source additionnelle, opt-in.** Le natif **ne remplace pas** le pont UDP.
   Sélecteur CONFIG : « EME via WSJT-X (UDP) » **OU** « EME natif (jt9
   embarqué) ». **Désactivé par défaut.** On ne touche pas au chemin UDP
   existant.
2. **Binaire embarqué = `jt9` vanilla K1JT** (WSJT-X officiel), pas le fork
   3.0.1 installé sur la machine de dev (celui-ci expose des options `MTft8` de
   fork ; comportement/format moins documentés). Le binaire livré fait
   référence pour le format à parser.

## 6. Architecture technique

```
Carte son RX ─► capture 12 kHz mono 16 bit ─► segmenteur (fenêtre 60 s, alignée minute UTC)
                                                     │  .wav temporaire (scratch)
                                                     ▼
                              jt9 embarqué  (-3 -p 60 -b <submode> -a <tmp> [AP: -c/-G/-x/-g/-Q])
                                                     │  parse q65_decodes.txt
                                                     ▼
                         normalisation → MÊME structure que wsjtx.eme_decodes()
                                                     │
                                                     ▼
                                  cockpit EME (inchangé) + croisement log
```

### 6.1 Nouveau module `concours/logx_q65_natif.py`

Responsabilité unique : produire des décodages Q65 au format `eme_decodes()`
à partir d'une carte son, sans WSJT-X. Sous-parties testables séparément :

- **Capture audio** : énumération des périphériques, ouverture flux 12 kHz
  mono (nouvelle dépendance à choisir : `sounddevice`/PortAudio ou
  équivalent — à valider dans le plan). C'est **le vrai gros du travail** :
  LogX ne captait pas d'audio jusqu'ici (WSJT-X s'en chargeait).
- **Segmenteur** : fenêtres de 60 s **alignées sur la minute UTC** (Q65-60),
  sans décrochage d'échantillonnage ; écriture d'un `.wav` temporaire dans le
  scratchpad.
- **Runner jt9** : `subprocess` sur le binaire embarqué avec les flags §3,
  timeout, gestion exit code, parse de `q65_decodes.txt`.
- **Normalisation** : projeter chaque décodage sur la structure exacte
  consommée par `eme_decodes()` (call, grid, snr, dt, df, mode, message,
  timestamp) afin que le cockpit et le croisement log restent **inchangés**.

### 6.2 Sélection de source (CONFIG)

Réglage station (pas une activité) → relève du résidu « mode expert /
plomberie de station » : sélecteur de source EME + choix carte son.
Désactivé par défaut ; le natif est une profondeur, pas le chemin critique.

## 7. Tests (méthode du dépôt : témoin vert + contre-épreuve par mutation)

- **Fixture de référence** : l'échantillon EME Q65-60A 6 m officiel (téléchargé
  pendant le spike). Un test décode ce `.wav` via le module et **exige les 3
  indicatifs attendus** (`N8JX`, `W1VD`, `VE1JF`) et les SNR (~−24/−20/−19).
  → assertion sur le **contenu décodé**, pas sur la présence d'une chaîne.
- **Contre-épreuve** : muter le parser (ex. mauvais index de colonne SNR) et
  vérifier que le test ROUGIT ; restaurer, contrôler md5. Obtenir le témoin
  vert **avant** toute mutation.
- **Segmenteur** : test unitaire sur l'alignement minute UTC et la longueur
  exacte des fenêtres (pas d'appel réseau, pas de carte son).
- **Normalisation** : test que la structure de sortie est byte-pour-byte
  compatible avec ce que `eme_decodes()` fournit au cockpit (banc contre la
  vraie structure, pas un mannequin).

## 8. Hypothèses restantes à vérifier au moment de l'implémentation

- `HYPOTHÈSE À VÉRIFIER` : le format de `q65_decodes.txt` du **jt9 vanilla**
  livré == celui observé sur le fork 3.0.1 (spike). Revalider sur le binaire
  effectivement embarqué avant de figer le parser.
- `À VÉRIFIER` : dépendances runtime du `jt9` vanilla à empaqueter (DLL FFTW,
  runtime C/Fortran) par OS (Win/macOS/Linux).
- `À VÉRIFIER` : latence de décodage jt9 sur la plateforme cible (doit tenir
  dans le cycle de 60 s avec marge) — **mesurer sur la cible**, pas ailleurs.
- `À SOURCER` : paramètres exacts par sous-mode Q65 (60A/B/C/D…) depuis la
  table WSJT-X — ne pas figer les valeurs approximatives du brief d'origine
  (qui se contredisait : code « (63,13) » vs « (65,15) »).

## 9. Risques

- **Capture audio = surface neuve** dans une app qui n'en avait pas. Décrochages
  / mauvais périphérique / resampling = principale source de bugs. D'où
  l'opt-in et le repli UDP conservé.
- **Packaging multi-OS du binaire GPL** + ses dépendances : à industrialiser
  dans le workflow `build-release.yml`.
- **Périmètre** : ne pas laisser V1 déborder sur TX / JT65 / IA. Chaque étage
  = sa propre spec.

## 10. Étages ultérieurs (hors ce design, pour mémoire)

1. JT65 natif (avec décision KVASD).
2. Émission Q65 (`tx-human-consent` obligatoire, séquenceur PTT).
3. Large bande / MAP65-QMAP.
4. Orchestration pile-up EME par l'IA (au-dessus des décodages).
