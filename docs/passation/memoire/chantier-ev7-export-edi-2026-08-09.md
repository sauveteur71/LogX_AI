---
name: chantier-ev7-export-edi-2026-08-09
description: "EV-7 25e incrément : extraction Exports EDI+Cabrillo vers logx_export_edi.js (09/08, merge 9a747e9) — piège classe 3 sur une CONSTANTE LOCALE (VHF_UHF_SHF_BANDS), invisible au grep des noms de fonction, trouvé uniquement par la suite pytest complète"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T03:21:53.044Z
---

25e incrément de la campagne [[inventaire-ev7-23e-2026-08-09]] (candidat
n°4). Extraction de 212 lignes de `concours/logx_logbook.js` vers
`concours/logx_export_edi.js` (nouveau) : `ediSerial()`, `exportEDI()`
(format REG1TEST par bande VHF/UHF/SHF), `exportCabrillo()` (le fichier
lui-même est fabriqué PAR LE SERVEUR, ce client ne fait que naviguer vers
`/log/export/cabrillo`), `remindSubmitLog()`. `logx_logbook.js` : ~4722 →
~4513 lignes.

**Nouvelle variante du piège classe 3 (substring/regex-extraction)** :
le grep exhaustif des 4 noms de fonction extraits (`exportEDI`/
`exportCabrillo`/`ediSerial`/`remindSubmitLog`) était propre — 0 dépendance
trouvée. Mais la suite pytest complète a révélé un échec sur
`test_revue_jour_correctifs.py::test_le_50MHz_est_dans_les_listes_THF` :
ce test cherchait par regex `VHF_UHF_SHF_BANDS\s*=\s*\[...\]` dans
`logx_logbook.js` — or `VHF_UHF_SHF_BANDS` est une **constante LOCALE**,
déclarée DANS le corps de `exportEDI()` (pas un symbole de niveau module),
donc totalement invisible à un grep centré sur les 4 noms de FONCTION du
bloc. Corrigé en élargissant la recherche du test à la concaténation de
`logx_logbook.js` + `logx_export_edi.js`.

**Leçon générale pour tout incrément futur** : le grep « noms des fonctions
extraites » ne suffit PAS à couvrir tout ce qu'un test peut chercher par
texte — une constante locale, une clé d'objet, une chaîne de configuration
interne au bloc peuvent aussi être la cible d'une recherche de sous-chaîne
dans un test totalement étranger au sujet apparent du bloc (ici un test
sur le rotor/grey-line/multi-op, PAS sur les exports). La suite pytest
complète reste le SEUL filet fiable — confirmé une fois de plus.

Deux autres fichiers de test dédiés corrigés (attendus, via le grep des 4
noms de fonction) : `test_cabrillo_conforme.py` (extraction par
sous-chaîne du corps de `exportCabrillo()`, repointée vers le nouveau
fichier) et `test_export_edi_num_sent.py` (`exportEDI()` évaluée en V8,
`EXPORT_EDI_JS_PATH` ajouté à `_real_source()` et à
`test_pas_de_qso_director()`).

Suite pytest complète : verte sur 2 passages (1er passage avait l'échec
VHF_UHF_SHF_BANDS, corrigé, 2e passage 100% vert). Revue adversariale
(2 dimensions, avec instruction explicite de re-grep les constantes
locales type `ediCfg`/`TDATE_START`/clés de config) : 0 constat.

Suite : candidat n°5 (Sélecteurs OPÉRATEUR/BANDE/MODE + fréquence,
`pickBand`/`setFreqForBand`, 198 lignes) devient le 26e incrément — point
de vigilance déjà noté dans l'inventaire : `test_export_adif_client_bande.py`
(jamais touché par un incrément précédent) à mettre à jour EN PLUS de
`test_macro_cw_serie_bande.py`.
