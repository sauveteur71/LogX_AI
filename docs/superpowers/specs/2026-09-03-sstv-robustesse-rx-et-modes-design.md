# SSTV — Robustesse réception faible signal + modes manquants

**Date :** 2026-09-03
**Auteur :** F4GLD + Claude (brainstorming)
**Statut :** design validé en cadrage, en attente de relecture spec avant plan d'implémentation

---

## 1. Contexte et motivation

LogX AI possède **déjà** une chaîne SSTV complète, en JavaScript côté
navigateur (cohérente avec toute l'infra modes numériques — FT8 en
`logx_ft8_dsp.js`, RTTY, CW) :

- **Réception** — `concours/logx_sstvdecoder.js` (~658 lignes) : détection VIS
  automatique, 14 modes (Martin M1/M2, Scottie S1/S2/DX, Robot 36/72,
  PD50/90/120/160/180/240/290), correction de dérive d'horloge (slant), démod
  FM I/Q. Réf. timing : N7CXI, « Proposal for SSTV Mode Specifications »,
  Dayton 2000.
- **Émission** — encodeur complet `sstvEncodeSamples()` (même fichier) →
  `txAudioPtt()` de `logx_tx_audio.js` (audio + PTT).
- **UI** — `concours/logx_sstv.html` (~293 lignes) + `logx_sstv_panel.js`
  (~232 lignes) : page dédiée, choix du périphérique audio, lecture `/config`.

Deux défauts réels signalés par F4GLD (03/09/2026) :

1. **La réception décroche sur signal faible / bruité (QSB).** Symptôme confirmé
   par F4GLD : « bruit / décrochage sur signal faible ». En fort signal ça
   fonctionne ; la synchro et l'image se dégradent dès que le S/N baisse.
2. **Des modes manquent :** Martin M3/M4, Scottie S3/S4, Robot 8/12/24 BW
   (monochrome), Wraase SC2-120/SC2-180.

Un 3ᵉ point rapporté (« je n'ai pas réussi à émettre ») est en réalité un
**blocage CAT/PTT** (port COM4 — diagnostic en cours dans un autre fil), **pas**
un défaut du code SSTV. **Hors périmètre de ce design.**

## 2. Périmètre

**Dans le périmètre :**
- **Lot A** — robustesse de la réception sur signal faible (cœur DSP).
- **Lot B** — ajout des modes manquants ci-dessus.
- Un **banc de mesure** reproductible pour chiffrer la robustesse.

**Hors périmètre :**
- L'émission RF et le PTT (bloqués par le CAT, traités ailleurs). On ne modifie
  pas le chemin TX. *Exception :* l'encodeur `sstvEncodeSamples()` est
  **réutilisé en lecture** par le banc de test et pour générer les nouveaux
  modes — mais on ne touche pas à `txAudioPtt()` ni au PTT.
- Le remplacement du décodeur par un moteur externe (MMSSTV/pySSTV) —
  **écarté** (voir §7).

**Ordre décidé (F4GLD) :** une **seule spec** couvrant A + B, implémentation en
**commençant par A**.

## 3. Lot A — Robustesse réception (approche validée : évolution mesurée)

État actuel (vérifié dans `logx_sstvdecoder.js`) : démodulation FM I/Q —
oscillateur local, filtre I/Q (~800 Hz), fréquence instantanée par **dérivée de
phase** (`atan2(I2·Qp − Q2·Ip, …)`) ; chaque pixel = **moyenne** de la fréquence
sur sa fenêtre ; synchro détectée par **seuil de fréquence** (`|moy − 1200| ≤
100 Hz`).

Le décrochage sous bruit s'explique par la nature du discriminateur de phase :
sous le seuil FM, le bruit fait « claquer » la phase (sauts de ±2π = clics), et
un détecteur de sync par simple seuil rate les impulsions noyées dans le bruit.

**Trois leviers, greffés sur l'existant, chacun mesurable séparément :**

### A1 — Limiteur d'amplitude avant discriminateur
Normaliser le vecteur I/Q (amplitude → 1) avant la dérivée de phase. Un
discriminateur de phase est sensible aux chutes d'amplitude ; le limiteur réduit
l'impact des clics. Changement local, faible risque.

### A2 — Estimation de fréquence pixel robuste
Remplacer la **moyenne** brute sur la fenêtre pixel par une statistique robuste
aux valeurs aberrantes : **médiane**, ou moyenne **pondérée par l'amplitude
instantanée** (déprioriser les échantillons où |I/Q| s'effondre — là où le bruit
domine). Objectif : un pixel n'est plus faussé par quelques échantillons de bruit.

### A3 — Synchro par corrélation
Remplacer le seuil `|moy − 1200| ≤ 100 Hz` par une **corrélation** avec le
gabarit d'impulsion de synchro (énergie à 1200 Hz sur la durée de sync du mode),
et retenir le **pic** de corrélation pour recaler t0. C'est le levier principal
contre le décrochage : une corrélation intègre l'énergie et résiste au bruit
bien mieux qu'une décision instantanée.

**Décision d'évolution ciblée :** si, *après mesure*, le plafond de A1–A3 reste
insuffisant, on pourra basculer **le seul détecteur de sync** vers un banc
Goertzel corrélé (élément de l'« approche 2 » écartée globalement). On ne le fait
**que** si les mesures le justifient (YAGNI) — pas de refonte spéculative du
front-end, pour ne pas régresser les 14 modes qui fonctionnent.

### Banc de mesure (préalable à tout levier)
Sans mesure, « c'est mieux » est invérifiable (règle du dépôt). Construire un
banc **avant** de toucher au DSP :

1. Encoder une **mire de référence** connue via `sstvEncodeSamples()` (mode par
   mode).
2. Injecter un **bruit blanc gaussien** à SNR décroissant (ex. 30 → 0 dB, pas de
   3 dB), graine fixe pour la reproductibilité.
3. Décoder, mesurer l'**erreur image** vs la mire (ex. PSNR / % pixels corrects /
   perte de synchro oui-non).
4. Produire une **courbe SNR → qualité** = la baseline chiffrée.

**Critère de succès Lot A :** à SNR égal, les leviers A1–A3 **abaissent le SNR de
décrochage** (le point où l'image devient inexploitable) d'une marge mesurable,
**sans régression** de la courbe en fort signal ni des 14 modes existants. Le
chiffre cible précis sera fixé une fois la baseline mesurée (pas d'objectif
inventé avant de connaître le point de départ).

## 4. Lot B — Modes manquants

La table de modes (`SSTV_MODES`, indexée par VIS ; `SSTV_MODES_PAR_NOM`) est déjà
extensible par **famille** (`rgb`, `robot36`, `robot72`, `pd`). Ajouts :

| Mode | Famille | Nature de l'ajout |
|------|---------|-------------------|
| Martin **M3, M4** | `rgb` (existante) | Variantes de timing — mécanique via `sstvModeMartin()`. |
| Scottie **S3, S4** | `rgb` (existante) | Variantes de timing — mécanique via `sstvModeScottie()`. |
| Robot **8/12/24 BW** | **`mono`** (nouvelle) | Nouvelle famille **monochrome** : sync + porch + un seul balayage luminance. |
| Wraase **SC2-120, SC2-180** | **`sc2`** (nouvelle) | Nouvelle famille : ordre RGB séquentiel, structure de sync propre. |

**Valeurs à sourcer (ne pas inventer — cf. règle du dépôt) :** codes VIS,
durées de sync/porch/scan et ordre des canaux de **chaque** mode ajouté sont
`VALEUR À SOURCER` depuis la spec N7CXI (et recoupées avec la doc MMSSTV). Aucune
valeur de timing ne sera écrite sans source citée en commentaire.

**Encodeur symétrique :** `sstvEncodeSamples()` doit produire chaque nouveau mode
(nécessaire au banc de test et cohérent avec l'existant qui encode déjà tous les
modes).

## 5. Stratégie de validation

F4GLD ne peut pas fournir de WAV réels pour l'instant. Validation à deux
niveaux :

1. **Interne (synthétique)** — banc §3 : baseline + non-régression chiffrées,
   pour la robustesse (Lot A) et la cohérence encode↔décode (Lot B).
2. **Externe (obligatoire pour Lot B)** — **au moins une source externe par
   nouveau mode** : un WAV encodé par un **autre** logiciel (ou WAV public de
   référence), OU les timings N7CXI vérifiés à la main.

> 🚨 **Piège mannequin (documenté dans le dépôt, arrivé 3×).** L'aller-retour
> encode→décode **interne** ne prouve **rien** sur un nouveau mode : si encodeur
> et décodeur partagent le **même timing faux**, le test passe au vert. Un mode
> dont on n'a **aucune** source externe sera livré marqué **« non vérifié en
> externe »** — jamais présenté comme validé.

**Méthode de test (règle du dépôt) :** pour chaque correctif, obtenir d'abord un
**témoin vert**, puis **contre-épreuve par mutation** (remettre le défaut, voir
le test rougir, restaurer). Tests structurels, pas de simple présence de chaîne.

## 6. Architecture / fichiers touchés

- `concours/logx_sstvdecoder.js` — cœur : leviers A1–A3 (démod + sync), nouvelles
  familles `mono`/`sc2`, nouvelles entrées de `SSTV_MODES`, encodeur symétrique.
  Fichier déjà volumineux mais **cohérent** (décodeur + encodeur ensemble, comme
  le RTTY) ; on reste dans ce fichier sauf si le banc justifie un module de test
  séparé.
- `concours/tests/` — **nouveau** banc de mesure SNR + tests par mode.
  **Harnais vérifié** : pytest + **py_mini_racer** (MiniRacer exécute le JS), sur
  le modèle de `test_sstv_decodeur.py` (qui charge `logx_sstvdecoder.js` et fait
  déjà l'aller-retour encode↔décode) ; voisins : `test_sstv_decoder_reentrance.py`,
  `test_sstv_revoke_differe.py`, `test_rtty_decodeur.py`. Nouveau fichier probable
  `test_sstv_robustesse.py`. ⚠️ Consulter la fiche mémoire « pièges py_mini_racer »
  avant d'écrire les tests JS (pièges connus de sérialisation JS→Python).
- `concours/logx_sstv_panel.js` / `logx_sstv.html` — ajout des nouveaux modes au
  sélecteur d'émission ; **aucune** autre modif UI dans ce lot (intuitivité : ne
  pas alourdir la page). Les nouveaux modes reçus s'affichent sans changement
  d'UI (détection VIS automatique).

**Non modifié :** `logx_tx_audio.js`, chemin PTT, CAT.

## 7. Décisions et alternatives écartées

- **Moteur externe MMSSTV/pySSTV — écarté.** LogX est sous **GPL-3.0** (racine du
  dépôt), donc la licence n'est **pas** un obstacle (GPL/LGPL compatibles). Motif
  du rejet purement **technique** : `SSTVENG.DLL` est du C++ Windows — l'intégrer
  casserait le modèle « tout-JS dans le navigateur » multiplateforme de LogX et
  ajouterait une dépendance lourde, alors qu'un décodeur maison fonctionnel
  existe. MMSSTV/pySSTV restent des **références algorithmiques** (constantes VIS,
  timings, structure), pas du code lié.
- **Refonte front-end Goertzel/FFT (approche 2) — écartée globalement**, conservée
  comme **évolution ciblée conditionnelle** du seul détecteur de sync si la mesure
  l'exige.
- **Ordre A→B** : la robustesse d'abord, car un nouveau mode ajouté sur un
  décodeur qui décroche décrocherait pareil.

## 8. Séquencement d'implémentation

1. **Banc de mesure** (synthétique) + baseline chiffrée des modes actuels.
2. **Lot A** : A1, puis A2, puis A3 — un levier à la fois, chacun mesuré (gain
   chiffré ou rejet).
3. **Lot B** : familles existantes d'abord (M3/M4, S3/S4 — mécaniques), puis
   familles nouvelles (`mono` Robot BW, `sc2` Wraase), chacune avec sa validation
   externe.
4. Ajout des nouveaux modes au sélecteur TX (UI minimale).

## 9. Risques

- **Absence de WAV réels** → couverture terrain limitée ; atténué par banc
  synthétique + sources externes + N7CXI, et par l'honnêteté « non vérifié en
  externe » quand aucune source n'existe.
- **Régression des 14 modes existants** en touchant le démodulateur commun →
  atténué par la baseline de non-régression *avant* toute modif DSP.
- **Timings faux sur nouveaux modes** → atténué par le garde-fou anti-mannequin
  (§5) et le sourçage obligatoire N7CXI.
