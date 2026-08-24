# IA-1 — Contrôle & validation du log — Spécification de conception

> Sous-projet « IA-1 » de la feuille de route copilote IA (voir mémoire
> `projet-ia-copilote-roadmap.md` : la validation du log est la PREMIÈRE brique,
> avant enrichissement/FT8/diplômes). Rédigé le 24/08/2026 sous mandat de
> travail autonome nocturne de F4GLD ; les décisions de conception y sont des
> **arbitrages documentés**, soumis à la revue de F4GLD (relecture de cette
> spec + PR) avant fusion sur `main`.

## 1. Problème

Un log qui part à l'export ADIF ou à l'upload LoTW peut porter des anomalies
silencieuses : fréquence qui ne correspond pas à la bande loguée, RST « 59 » sur
un QSO FT8 (qui attend un rapport en dB), QSO d'activation SOTA/POTA sans sa
référence, date dans le futur, heure de fin avant l'heure de début. Aujourd'hui
elles ne sont détectées **nulle part** avant que le fichier ne parte.

Un validateur déterministe existe déjà (`logx_validator.validate_log`) mais il
est **spécialisé concours REF** (doublon, locator THF, département, fenêtre du
concours) et la plupart de ses contrôles sont désactivés en mode simple ou hors
concours. Un carnet **généraliste / déca / DXpédition / activation** n'a donc
quasiment aucun contrôle de cohérence.

## 2. Objectif et non-objectifs

**Objectif.** Étendre le validateur déterministe existant avec des contrôles de
**cohérence indépendants de l'activité** (valables pour TOUT carnet, y compris
en mode simple et hors concours), et offrir un **contrôle pré-vol** avant export
ADIF / upload LoTW. Le tout restitué dans le panneau « VÉRIFIER » existant.

**Non-objectifs (arbitrages).**
- **Ne rien reconstruire.** On RÉUTILISE `logx_validator.validate_log`,
  `logx_verif_panel.js`, l'endpoint `/log/validate`, les tables
  `logx_adif_enums`, `logx_activation`, la détection de doublons existante
  (`add_qso_to_log`, `logx_dup_finder.js`), le filet busted-call
  (`near_matches`). IA-1 AJOUTE des contrôles, il n'en remplace aucun.
- **Jamais bloquer l'opérateur.** Principe permanent « masquer ≠ bloquer » et
  « l'émission/la décision reste le geste de l'humain » (mémoire
  `projet-ia-copilote-roadmap.md`). Le contrôle pré-vol INFORME et prévient ;
  il ne refuse jamais un export ni un upload de sa propre autorité. L'opérateur
  garde la main (il peut exporter/uploader malgré un avertissement).
- **Déterministe d'abord.** IA-1 est le socle DÉTERMINISTE. L'audit IA
  non-déterministe existe déjà (`build_audit_input`/`/log/audit`) et reste le
  complément « approfondi » ; IA-1 ne le double pas.
- **Aucune valeur de domaine inventée.** Seuils/plages de bande, énumérations de
  mode, formats de référence proviennent des tables déjà sourcées du dépôt
  (`logx_adif_enums.ADIF_BANDS`, `is_valid_mode`, `logx_activation.PROGRAM_SPECS`)
  — jamais d'une constante inventée ici.

## 3. Architecture

Un seul module de logique nouvelle : **`concours/logx_controles.py`**, un jeu de
fonctions PURES `(qso) -> finding|None` (une par anomalie), déterministes et
testables sans serveur. `logx_validator.validate_log` les APPELLE dans sa boucle
existante, en plus de ses contrôles concours actuels. Les nouveaux contrôles
s'exécutent **pour chaque QSO, quelle que soit l'activité** (pas de garde
`contest_id`, pas de garde `simple_mode`) — ils ne dépendent d'aucun règlement.

Chaque finding respecte le format EXACT déjà produit par `validate_log`
(`{level, code, msg, call, band, at, id}`), pour que `logx_verif_panel.js`
l'affiche sans modification et que les boutons Corriger/Supprimer marchent tels
quels.

```
logx_controles.py   (nouveau — fonctions pures de cohérence)
        ▲
        │ importées et appelées dans la boucle
logx_validator.validate_log()   (existant — étendu, pas réécrit)
        ▲
        │ GET /log/validate (existant)      +   pré-vol export/LoTW (nouveau)
logx_verif_panel.js  (existant — aucun changement de structure)
```

### 3.1 Contrôles de cohérence (nouveaux, dans `logx_controles.py`)

Chaque fonction reçoit le QSO (dict interne du log) et rend un finding ou `None`.
Niveaux : `erreur` (fichier probablement rejeté / donnée fausse), `attention`
(probable erreur de saisie), `info` (à confirmer). Codes en `snake_case`.

1. **`controle_freq_bande(q)`** — `attention` `freq_bande_incoherente`.
   Si `q['freq']` est présent ET `logx_adif_enums.band_from_freq(freq)` renvoie
   une bande NON vide qui DIFFÈRE de `q['band']` (bande interne). Source de
   vérité : la table `ADIF_BANDS`. Silencieux si freq absent ou hors table (on
   ne signale pas ce qu'on ne sait pas trancher).

2. **`controle_date_future(q, maintenant_utc)`** — `attention` `date_future`.
   Si `q['date']` (AAAAMMJJ) est strictement postérieure au jour UTC courant.
   `maintenant_utc` est injecté (via `logx_utils.utcnow`) pour rester pur et
   testable — jamais `datetime.now()` en dur dans la fonction.

3. **`controle_heure_fin(q)`** — `info` `heure_fin_avant_debut`.
   Si `time_off` ET `time` présents, MÊME date (`date`), et `time_off` < `time`
   (HHMM comparés numériquement). Niveau `info` (et non `attention`) précisément
   parce qu'un QSO chevauchant minuit UTC produit légitimement `time_off < time`
   à date égale : c'est le seul faux positif possible, rare et à faible enjeu, et
   `info` le rend non alarmant. Pas de seuil arbitraire — la simplicité prime.

4. **`controle_rst_mode(q)`** — `info` `rst_incoherent_mode`.
   RST implausible pour le mode. CONSERVATEUR : on ne signale que le cas NET —
   un mode « à rapport dB » (FT8/FT4/JT*/MFSK/FST4…) portant un RST de type
   `59`/`599` au lieu d'un rapport en dB (entier signé, ex. `-12`). La liste des
   modes-dB vient d'une constante SOURCÉE (modes numériques à rapport SNR), pas
   d'une invention. On ne signale PAS l'inverse fin (un `599` en SSB) tant qu'il
   reste ambigu — YAGNI, éviter le bruit.

5. **`controle_activation_ref(q)`** — deux findings possibles :
   - `attention` `activation_sans_ref` : `my_sig` (programme) renseigné mais
     `my_sig_info` (référence) vide — activation déclarée sans référence.
   - `attention` `ref_format_invalide` : `my_sig_info` présent mais
     `logx_activation.validate_ref(my_sig, my_sig_info)` est faux — la référence
     ne respecte pas le format du programme (`PROGRAM_SPECS[...]['ref_re']`).
   Idem côté correspondant (`sig`/`sig_info`) → `info` (moins critique : c'est la
   réf de l'autre, on la subit). Réutilise `PROGRAM_SPECS`, aucune regex nouvelle.

> **Mode enum** — un contrôle « mode hors énumération ADIF » via `is_valid_mode`
> est TENTANT mais risqué : les modes INTERNES de LogX (`FT8`, `FT2`…) ne sont
> pas forcément des modes ADIF canoniques (FT8 = MFSK/submode). Il est donc
> **hors scope v1** pour éviter les faux positifs, et noté comme extension à
> instruire séparément contre la vraie table `ADIF_MODES_FLAT`.

### 3.2 Contrôle pré-vol avant export / LoTW (nouveau)

Fonction `resume_controle(qsos, contest_id, cfg)` dans `logx_validator.py` (ou
`logx_controles.py`) : renvoie un **résumé compact** `{erreurs, attentions,
infos, findings_bloquants[]}` en s'appuyant sur `validate_log`. Elle ne fait que
LIRE et résumer — aucun effet de bord, aucun blocage.

**Câblage (INFORMATIF, jamais bloquant) :**
- **Upload LoTW** (`logx_qsl.upload_lotw` / endpoint serveur) : avant de lancer
  `tqsl`, calculer `resume_controle` et JOINDRE le résumé à la réponse (ex.
  `{queued:N, controle:{erreurs:2,...}}`) pour que l'UI puisse avertir « 2 QSO
  en erreur seront tout de même uploadés ». **Ruling** : on n'annule PAS
  l'upload — l'opérateur reste maître (masquer ≠ bloquer). Le résumé est un
  avertissement, pas un verrou. Coût si faux : un opérateur upload malgré un
  avertissement qu'il aura vu — c'est son droit ; l'inverse (bloquer) violerait
  le principe permanent.
- **Export ADIF** : idem, le résumé peut accompagner la réponse d'export ; le
  bandeau existant côté client (`exportADIF` → « N QSO incomplets ignorés »)
  reste. IA-1 n'ajoute PAS de blocage.

### 3.3 UI

Aucune refonte du panneau « VÉRIFIER » : les nouveaux findings, au format
existant, apparaissent automatiquement dans `showValidation()`. Seule évolution
possible v1 : un compteur du pré-vol dans la réponse d'upload/export, affiché en
bandeau `notify()` (non bloquant) — à faire dans un lot UI dédié, APRÈS que la
logique déterministe soit verte et fusionnée, pour ne pas mêler logique et
présentation.

## 4. Découpage pressenti (lots TDD)

1. **`logx_controles.py` — cohérence freq/bande + date/heure.** Fonctions pures
   `controle_freq_bande`, `controle_date_future`, `controle_heure_fin`. Test :
   chaque fonction rend le bon finding sur un cas net, `None` sur un cas sain et
   sur les cas ambigus (freq absente, minuit).
2. **`logx_controles.py` — RST/mode + références d'activation.**
   `controle_rst_mode`, `controle_activation_ref`. Test : un FT8 à `599` signalé,
   un FT8 à `-12` OK ; activation sans réf signalée, réf mal formée signalée, réf
   valide OK. Réutilise `PROGRAM_SPECS`/`validate_ref`.
3. **Branchement dans `validate_log`.** Appeler les contrôles pour chaque QSO,
   indépendamment de `contest_id`/`simple_mode`, sans casser les findings
   concours existants. Test : un carnet HORS concours (mode simple) reçoit
   désormais les findings de cohérence ; les findings concours restent
   inchangés sur un log REF.
4. **`resume_controle` + câblage informatif upload/export.** Le résumé accompagne
   la réponse, ne bloque jamais. Test : `resume_controle` compte correctement ;
   `upload_lotw` renvoie le résumé sans changer son comportement d'upload
   (contre-épreuve : un log en erreur est TOUJOURS proposé à l'upload).
5. **(UI, différé)** bandeau `notify()` du pré-vol côté client. Hors de ce
   premier périmètre logique.

## 5. Contraintes globales (rappel, valables pour chaque lot)

- **Français** partout (UI + messages de findings), vocabulaire radioamateur.
- **Fonctions pures et testables** sans serveur ; `utcnow`/dates injectés,
  jamais `datetime.now()` en dur (rejouabilité des tests).
- **Format de finding identique** à `validate_log` (`{level, code, msg, call,
  band, at, id}`) — condition pour que l'UI existante l'affiche sans changement.
- **Jamais bloquant** : aucun contrôle n'annule un export/upload.
- **Contre-épreuve par mutation** obligatoire après chaque lot (témoin vert →
  remettre le défaut → le test rougit → restaurer → md5).
- **Valeurs de domaine sourcées** : bandes/modes/formats depuis les tables du
  dépôt, jamais inventées ici.
- **CRLF** : `logx_validator.py`/`logx_qsl.py` sont en CRLF — en tenir compte
  pour toute mutation scriptée (piège déjà rencontré au sous-chantier B).
