---
name: chantier-bandeaux-non-bloquants-chantier2-2026-08-10
description: "Chantier 2 (suite audit accessibilité PR #8) — bandeaux non bloquants pour le doublon QSO et la validation CONFIG, remplaçant confirm()/alert() natifs"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-10T05:56:01.777Z
---

PR #9 (branche fix/chantier2-bandeaux-non-bloquants) mergée sur main le
10/08/2026 : remplace les dialogues natifs bloquants restants après l'audit
accessibilité PR #8 (qui les avait délibérément laissés de côté, jugés à
risque de régression comportementale plus élevé).

- **LOGBOOK** (`logx_logbook.js`/`.html`) : `#dupConfirmBanner` remplace les
  2 `confirm()` de `submitQSO()` (pré-vérification client + réponse serveur
  409) via un pattern Promise résolue par de vrais `<button onclick>`
  (`_confirmDupBanner()`/`_resolveDupConfirm()`/`_cancelPendingDupConfirm()`).
  Auto-annulation si l'opérateur reprend la frappe sans répondre (appelé
  depuis `onCallInput()`).
- **CONFIG** (`logx_configuration.html`) : `#configValidationBanner`
  remplace l'`alert()` de `_warnMissingStation()` et les 3 alertes ClubLog/
  QRZ/SOTA de `saveConfig()`. `_missingStationFields()` retourne désormais
  `[{message, category}]` (category = un ID `CONFIG_SECTIONS`) au lieu de
  chaînes brutes — chaque ligne du bandeau devient un lien cliquable vers
  la bonne section de la sidebar via `switchSection()`.
- Complète au passage un gap de l'audit précédent : `(obligatoire)` +
  `aria-required` sur INDICATIF/LOCATOR dans CONFIG.
- **Bug de contraste trouvé pendant la vérification navigateur** (pas par
  la revue de code) : `.dup-confirm-banner #dupConfirmYesBtn` utilisait
  `background:var(--red);color:#fff` — sain en mode jour (--red jour
  #CC0030, contraste 5.8:1) mais **3.65:1 en mode nuit** (--red nuit
  #FF2D55, trop clair pour du texte blanc — sous le seuil AA 4.5:1).
  Symétrique du piège copper déjà documenté (`piege-couleur-data-vs-theme`
  et le §"remplissage plein" de CLAUDE.md) mais sur le ROUGE sémantique
  cette fois, pas l'accent. Fixé avec la même recette : valeur de fond FIXE
  indépendante du thème (`#CC0030`, celle du jour) plutôt qu'un
  `var(--red)`. **Généralisation à retenir** : tout `background:var(--red)`
  (ou toute autre couleur sémantique) + texte fixe mérite le même calcul de
  contraste dans LES DEUX thèmes avant de considérer un composant fini —
  pas seulement `--accent`/`--accent2`.
- 17 tests py_mini_racer (2 nouveaux fichiers `test_dup_confirm_banner.py`
  + `test_config_validation_banner.py`), suite complète verte, vérification
  navigateur des deux bandeaux + calcul de contraste réel (getComputedStyle)
  dans les deux thèmes.

Voir aussi [[piege-couleur-data-vs-theme]] et le chantier suivant
[[chantier-qso-champs-obligatoires-2026-08-10]] (fait dans la foulée, sur
une branche séparée après un faux départ sur celle-ci — voir
[[piege-continuer-nouveau-chantier-sur-branche-pr-deja-creee]]).
