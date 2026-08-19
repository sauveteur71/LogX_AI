---
name: chantier-cat-autodetect-microham-2026-08
description: "Auto-détection CAT réelle + erreurs traduites + guide microHAM, suite à un retour de beta-testeur bloqué"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-03T09:23:07.513Z
---

Un beta-testeur utilisant une interface microHAM n'arrivait pas à connecter
sa radio. Diagnostic : le pilotage CAT natif de LogX AI n'avait rien de
cassé — microHAM est un simple passe-plat USB↔série, le vrai point de
blocage est que microHAM Router (le logiciel de l'interface) doit tourner
et avoir la radio sélectionnée AVANT que LogX (ou tout autre logiciel)
puisse ouvrir le port COM virtuel qu'il expose.

Deux vrais bugs trouvés au passage (même famille que le patron récurrent
"fonction backend jamais câblée à l'UI", déjà vu plusieurs fois cette
session) : le bouton "Tester" ne pouvait JAMAIS auto-détecter quoi que ce
soit (il exigeait déjà marque+modèle) alors qu'une fonction `autodetect()`
fonctionnelle existait dans `logx_cat.py` sans jamais être appelée ; les
erreurs de connexion affichaient le texte Python brut de pyserial, sans
dire si la cause était "port déjà utilisé" ou "port absent".

Livré (commit `484ca6d`, fusionné) : `autodetect_scan()` (balaie plusieurs
vitesses), `_friendly_open_error()` (traduit les exceptions pyserial en
cause probable, mentionne microHAM Router), nouveau bouton dédié
"Auto-détecter" + endpoint `/rig/autodetect`, aide contextuelle sur le
champ port série, et `docs/GUIDE_CAT_MICROHAM.md` (marche à suivre pour
le beta-testeur). Beta v0.9-beta17 taguée et poussée dans la foulée (build
multi-OS automatique via `.github/workflows/build-release.yml`).
