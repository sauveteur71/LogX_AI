---
name: adif-validation
description: À charger AVANT d'écrire ou de modifier tout code qui valide, normalise, importe ou exporte des QSO / de l'ADIF dans LogX AI — générateurs ADIF (serveur build_adif ou client buildAdifText), parseur d'import, contrôles de cohérence, validateur de log, énumérations de bandes/modes, références d'activation (POTA/SOTA/WWFF/ILLW/WWBOTA…), export CSV/Cabrillo. Déclenche dès qu'apparaît un tag ADIF, un libellé de bande, un mode/sous-mode, une valeur de zone/état, un aller-retour export→import, ou une règle « ce QSO est-il valide ? ». Raison d'être : réutiliser l'infrastructure DÉJÀ SOURCÉE du dépôt au lieu de réinventer un parseur ou d'INVENTER des valeurs de domaine.
---

# adif-validation — écrire du code ADIF/validation dans LogX AI

Toute valeur ADIF (nom de tag, libellé de bande, mode/sous-mode, zone, état,
format de référence) est une **valeur de domaine**. Règle CLAUDE.md : jamais
inventer, source citable ou `VALEUR À SOURCER`. Le dépôt a déjà payé ce sourçage —
on le RÉUTILISE, on ne le recrée pas. (Les numéros de ligne ci-dessous sont
indicatifs — vérifier le symbole, pas la ligne exacte.)

## 1. Ne jamais inventer une valeur de domaine — d'où viennent les tables

| Besoin | Table à réutiliser | Source |
|---|---|---|
| Bandes ADIF (libellé + plage MHz) | `ADIF_BANDS` (`logx_adif_enums.py`) | adif.org, recopié offline-first |
| Modes / sous-modes ADIF | `ADIF_MODES` + aplati `ADIF_MODES_FLAT` (`logx_adif_enums.py`) | ADIF 3.1.7 officiel |
| Bande interne (MHz) → libellé ADIF | `ADIF_BAND` (`logx_export.py`) et son **jumeau JS** (`logx_export_adif.js`) | — |
| Fréq → bande | `band_from_freq()` (`logx_adif_enums.py`) ; interne `_band_from_freq` (`logx_scoring.py`) | — |
| Sous-mode → MODE parent | `_SUBMODE_PARENT` (`logx_export.py`, dérivé d'ADIF_MODES) + jumeau JS `SUBMODE_PARENT` | ADIF 3.1.7 |
| Réf. d'activation (format + min QSO) | `PROGRAM_SPECS` + `validate_ref()` (`logx_activation.py`) | règles officielles citées en commentaire |
| Tags dédiés par programme (SOTA_REF…) | `ADIF_PROGRAM_TAGS` (`logx_activation.py`) + jumeau JS `REF_ADIF_TAGS` | adif.org/315 |

Avant d'ajouter une bande/mode/zone/programme : vérifier qu'elle n'est pas déjà
là. Si elle manque vraiment, la sourcer (adif.org ou règle officielle) et
l'ajouter à la table EXISTANTE avec son commentaire de source — jamais une
constante locale parallèle. `is_known_mode()`/`is_valid_mode` tolère volontairement
qu'un ADIF réel mette un sous-mode dans `MODE` (WSJT-X) : ne pas « corriger ».

## 2. Les deux générateurs ADIF sont des JUMEAUX à garder synchronisés

`build_adif()` (`logx_export.py`, serveur) et `buildAdifText()`
(`logx_export_adif.js`, client) produisent le MÊME format ; un correctif de l'un
se reflète dans l'autre (un test de parité le fige). Idem tables jumelles
`ADIF_BAND`, `_SUBMODE_PARENT`/`SUBMODE_PARENT`, `ADIF_PROGRAM_TAGS`/`REF_ADIF_TAGS`,
`_ADIF_STD_TAGS`/`ADIF_STD_TAGS`. Ne jamais réutiliser une table d'AFFICHAGE
comme libellé ADIF.

## 3. Le piège du round-trip : tag émis SANS mapping d'import = donnée perdue

**Classe de bug trouvée en sous-projet B (et re-vérifiée en IA-2).** Mécanisme :

1. `build_adif` émet un tag T depuis un champ dédié ET T ∈ `_ADIF_STD_TAGS`
   (anti-duplication).
2. L'import range tout tag NON présent dans `_TAGS_MAPPES`/`_ADIF_VERS_INTERNE`
   (`logx_import.py`) dans `extra_fields[T]` (MAJUSCULES).
3. Au ré-export, la boucle `extra_fields` SAUTE tout tag de `_ADIF_STD_TAGS`.
4. Si l'import n'a jamais peuplé le champ interne correspondant → **perte
   silencieuse** au 2ᵉ export.

**Invariant à tenir** pour CHAQUE tag émis : soit il est mappé vers un champ
interne dans `_ADIF_VERS_INTERNE` (réémis depuis ce champ), soit il n'est PAS
dans `_ADIF_STD_TAGS` (préservé via `extra_fields`). Ajouter un tag impose de
CHOISIR explicitement l'un des deux + un test d'aller-retour. Exception documentée
côté RCVD/SUBMODE : volontairement HORS `_ADIF_STD_TAGS` car émis
conditionnellement (anti-dup dynamique `_conf_tags_emis`).

## 4. Sous-modes : MODE=MFSK + SUBMODE=…, jamais MODE=FT4

FT4/JS8/Q65/FST4/FT2 sont des SOUS-MODES de MFSK. `MODE=FT4` = ADIF non conforme
(rejet possible par robots concours/LoTW). Patron : `_adif_mode()`
(`logx_export.py`) via `_SUBMODE_PARENT` + jumeau JS ; import miroir `_lire_mode()`.
Le sous-mode PRIME à la lecture (clé `submode` ou `extra_fields['SUBMODE']`, cf.
`_mode_effectif` dans `logx_controles.py`). Tout nouveau sous-mode : les DEUX
côtés (export ET import) simultanément, sinon l'aller-retour casse.

## 5. Validation déterministe d'abord ; ne jamais écraser ni bloquer

- **Déterministe en premier** : `validate_log()` (`logx_validator.py`) + les
  contrôles purs de `logx_controles.py` (freq↔bande, date future, heure de fin,
  RST↔mode dB, réf d'activation). L'audit IA vient EN COMPLÉMENT, même format
  `{level, code, msg, id}`.
- **Niveaux** `erreur`/`attention`/`info` ; seule l'`erreur` fait `ok=False`.
  Dans le doute s'abstenir (un faux positif fait perdre confiance). `_f` n'évince
  JAMAIS une `erreur` au-delà de MAX_FINDINGS.
- **Ne jamais écraser la saisie opérateur** (import comme enrichissement ne
  remplissent que le vide). La validation LIT, ne réécrit pas.
- **Masquer ≠ bloquer** : l'export ne bloque jamais ; les QSO incomplets sont
  ignorés/signalés (`isValidQSO`), l'utilisateur n'est pas empêché d'exporter.
  Le contrôle pré-vol (`resume_controle`) est INFORMATIF.

## 6. Fidélité d'aller-retour (export → import → export STABLE)

- Dédup d'import stricte `(call, band, mode, date, time)` (`_dedup_key`) — `None`
  si date vide (jamais traité comme doublon → jamais de QSO perdu).
- Assainir CHAQUE champ texte importé (`_clean_text`) : une bande hors table
  revient BRUTE et pourrait injecter un saut de ligne.
- `extra_fields` = canal de préservation partagé import↔export↔éditeur client —
  ne pas le court-circuiter.
- Satellite (`PROP_MODE=SAT`+`SAT_NAME`) et activation (`MY_SIG`/`SIG` + refs
  multiples `my_refs`/`refs`) : les champs vont ENSEMBLE, sinon LoTW dégrade/rejette.
  L'ensemble qui fait foi pour une activation = `activation_qsos()`.
- Confirmations reçues (LOTW_QSL_RCVD…) : viennent du STORE
  (`qsl_confirmations.json`, clé `awards._confirm_key`), injectées à l'export via
  `build_adif(..., confirmations=)` — jamais pour les uploads (LoTW recalcule).

## 7. Méthode de test obligatoire (« Vérifier plutôt que croire »)

1. **Témoin vert** avant toute mutation.
2. **Rougir** : remettre le défaut (émettre `MODE=FT4`, retirer un tag de
   `_ADIF_VERS_INTERNE`…) et vérifier que le test ÉCHOUE.
3. **Restaurer** + contrôler l'empreinte **md5** (piège CRLF : `logx_*.py` en
   CRLF, muter par lignes).
4. Tester le **comportement, pas la structure** : pour l'ADIF, exécuter le VRAI
   `buildAdifText` en V8 (py_mini_racer) ou faire un round-trip et comparer les
   champs, plutôt qu'un `assert '<MODE:4>MFSK' in adif` (satisfait par un
   commentaire). Cibles pures testables : `build_adif`, `buildAdifText`,
   `parse_adif_to_qsos`, `validate_log`, `controles_coherence`, `enrichir`,
   `build_csv`.

Après toute conversion touchant un libellé, greper `tests/` pour l'ancienne
valeur figée (un test peut geler un titre décoratif sans régression réelle).
