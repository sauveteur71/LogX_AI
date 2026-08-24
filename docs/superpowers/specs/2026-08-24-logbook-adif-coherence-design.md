# Cohérence & complétude ADIF du LOGBOOK (sous-chantier B) — design

Écrit le 24/08/2026, à la suite du sous-chantier A (refonte saisie). B **mappe en
ADIF** les clés que A a posées, corrige les défauts d'intégrité de l'export
existant, et symétrise import↔export. Pré-requis : A fusionné (les nouvelles clés
existent) — mais plusieurs défauts de B sont INDÉPENDANTS de A et pourraient être
corrigés seuls.

## 1. Objectif

Que **rien ne se perde** entre logbook, export et import, et que l'ADIF émis soit
**complet** (couvre les champs utiles diplômes/contest/FT8/confirmations). Valeur
de sécurité (« rien ne se perd », leçon de l'incident du carnet), pas cosmétique.

## 2. Défauts mesurés (audit du 24/08)

1. **DEUX générateurs ADIF divergents** — `logx_export.py build_adif` (complet)
   vs `logx_export_adif.js buildAdifText` (**10 tags de moins** : omet NAME, QTH,
   COMMENT, STATE, DISTANCE, PROP_MODE, SAT_NAME, MY_SIG*, SIG*). Un export
   déclenché **côté client perd des données** que l'export serveur émet. Défaut
   d'intégrité réel.
2. **Asymétrie import↔export** — FREQ, TIME_OFF, NAME/QTH/COMMENT, PROP_MODE sont
   exportés (ou stockés) mais **non re-mappés à l'import** (tombent en
   `extra_fields`, donc préservés mais non typés).
3. **Confirmations hors QSO** — QSL/LoTW/eQSL vivent dans `qsl_confirmations.json`
   (`logx_qsl.py`), **jamais réémises dans l'ADIF** exporté.
4. **Clés de A non mappées** — `tx_pwr`, `freq_rx`, `cqz`, `ituz`, `cnty`,
   `prop_mode` (déjà partiel), `operating_location`, `email`, `qsl_via`,
   `my_refs`/`refs` (multi-programmes), `qsl_sent`/`lotw_qsl_sent`/`eqsl_qsl_sent`,
   `activity_tags` — posées par A, à émettre en ADIF.
5. **Données calculées** — `ant_az` (azimut, désormais persisté par A) et le pays
   à émettre.

## 3. Contraintes

- **Une seule source de vérité pour l'export** : supprimer la divergence, pas la
  documenter. Idéalement, l'export client délègue au serveur, OU les deux lisent
  une même table de mapping. Le plus sûr : **l'export passe par le serveur**
  (`build_adif`) et le client ne fait qu'appeler l'endpoint — à valider (il existe
  un export client hors-ligne pour la zone blanche : garder une capacité locale).
- **Zone blanche** : un export doit rester possible **sans réseau** (autonomie).
  Donc si le client délègue au serveur LOCAL (127.0.0.1), c'est OK ; s'il faut un
  export 100 % client, alors **une table de mapping partagée** (générée/synchronisée)
  plutôt que deux implémentations.
- **Aucune valeur de domaine inventée** : noms de tags ADIF (`TX_PWR`, `FREQ_RX`,
  `QSL_SENT`, `LOTW_QSL_SENT`, `MY_SOTA_REF`, `PROP_MODE`…) et énumérations depuis
  la **spec ADIF** (citable) ; charger le skill `radioamateur` pour les cas
  ambigus.
- **Multi-références → ADIF mono-valué** : `MY_SIG`/`MY_SIG_INFO` ne portent qu'UNE
  référence. Émettre les autres via leurs tags dédiés quand ils existent
  (`MY_SOTA_REF`, POTA via `MY_SIG=POTA`/`MY_SIG_INFO`, `MY_WWFF_REF`…) ou, à
  défaut, **un enregistrement ADIF par programme** (comme POTA/WWFF l'attendent
  souvent). À trancher par programme, sourcé.
- **LoTW minimal** : indicatif, date/heure UTC début, bande, mode/groupe — le
  contrôle avant export (sous-chantier IA-1) s'appuiera là-dessus.

## 4. Découpage pressenti (sous-lots B, TDD)

1. **Unifier l'export** : supprimer la divergence JS↔Python (délégation serveur
   local OU table de mapping partagée) — le plus gros gain d'intégrité. Test : un
   même QSO exporté par les deux chemins produit le MÊME ADIF (tag à tag).
2. **Mapper les clés de A** : `TX_PWR`, `FREQ_RX`, `CQZ`, `ITUZ`, `CNTY`,
   `OPERATING`/suffixe, `EMAIL`, `QSL_VIA`, `ANT_AZ`, pays. Test : présence de
   chaque tag pour un QSO qui porte la clé.
3. **Multi-références** : `my_refs`/`refs` → tags par programme (ou ADIF/programme).
   Test : un QSO SOTA+POTA émet les deux références de façon exploitable.
4. **Confirmations dans l'ADIF** : injecter QSL/LoTW/eQSL (envoyé ET reçu) depuis
   `logx_qsl.py` dans l'export. Test : un QSO confirmé LoTW émet `LOTW_QSL_RCVD=Y`.
5. **Symétriser l'import** : mapper FREQ, TIME_OFF, NAME/QTH/COMMENT, PROP_MODE,
   TX_PWR, zones, QSL_*/LOTW_* (aller-retour export→import→export idempotent).
   Test : round-trip sans perte ni dégradation en `extra_fields`.
6. **`activity_tags`** : décider de l'émission (tag propriétaire `APP_LOGX_TAGS`
   pour ne pas casser l'ADIF standard). Test : tags exportés/réimportés.

## 5. Hors périmètre

Nouveaux décodeurs, couverture d'activités absentes (C) ; l'IA de contrôle de log
(IA-1) qui CONSOMMERA cet export complet est un chantier distinct (roadmap IA).

## 6. Risques

- **Casser l'export existant** : les deux générateurs sont décrits « jumeaux à
  garder synchrones » — les unifier touche du code sensible. Contre-épreuve par
  mutation + round-trip obligatoires ; ne jamais réduire un export sans test.
- **Zone blanche** : ne pas rendre l'export dépendant du réseau externe.
- **CRLF / `newline=''`** sur les écritures ADIF (pièges connus).
