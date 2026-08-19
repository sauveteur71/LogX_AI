---
name: chantier-fix-release-cassee-et-repli-version-bugreport-2026-08-12
description: "Repli _fastVersion pour le bouton signaler un problème (PR #39) + découverte/correction d'un bug qui cassait TOUT build de release depuis 2 jours (PR #40) — v0.9-beta27 publiée"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-12T04:14:29.679Z
---

Suite à "bosse toute la nuit et une fois lescorrctif fait pousse une beta"
(F4GLD, nuit du 11 au 12/08/2026), deux chantiers distincts menés à terme
cette nuit.

## 1. Repli rapide de version pour "signaler un problème" (PR #39, mergée)

Demande : « si quelqu'un signale un bug sa version de programme doit etre
integré dans le massage automatiquement ». `openReportIssue()`
(`logx_statusbar.js`) pré-remplissait déjà le champ version du formulaire
GitHub Issue Forms via `_updState.current`, mais celui-ci vient d'un fetch
async (`/app/update_check`) qui peut ne pas avoir abouti si l'opérateur
clique tout de suite après le chargement de la page — repli silencieux sur
`"inconnue"`.

Ajouté `_fastVersion`, alimenté par `/network/info` (sonde déjà existante,
non authentifiée, ~0,36s, conçue à l'origine pour `logx_singleton.py`) comme
repli intermédiaire. `openReportIssue()` reste **entièrement synchrone**
(contrainte anti-popup-blocker documentée dans le code existant) —
`refreshFastVersion()` est un fetch best-effort lancé au `boot()`, jamais
attendu par le bouton.

**Piège de test retrouvé (déjà documenté ailleurs, confirmé de nouveau)** :
3 fichiers de test (`test_report_issue_form_prefill.py`,
`test_report_issue_error_journal.py`, `test_report_issue_unicode.py`)
extraient le bloc source de `openReportIssue()` par comptage d'accolades à
partir de `const REPORT_REPO_FALLBACK` — donc APRÈS la déclaration de
`_fastVersion` dans le vrai fichier. Le harnais V8 minimal de ces 3 tests
ne déclarait `_updState` qu'à la main (`var _updState = {...}`) ; sans
ajouter `var _fastVersion = null;` au même endroit, les 3 tests auraient
levé `ReferenceError` dès que le bloc extrait référence la nouvelle
variable. Réflexe pour toute future variable ajoutée AVANT
`REPORT_REPO_FALLBACK` dans ce fichier : chercher tous les harnais de test
qui extraient ce bloc et déclarer la variable dans leur préambule aussi.

## 2. Build de release cassé depuis 2 jours, découvert en poussant le tag (PR #40, mergée)

Après avoir mergé le bump de version (PR #38, `0.9-beta26` → `0.9-beta27`)
et poussé le tag `v0.9-beta27`, **le build multi-OS a échoué sur les 3 OS
en 46s** — vérifié explicitement au lieu de supposer que "tag poussé = build
en cours de réussir" (voir [[piege-artefacts-perimes-verification]] pour la
même discipline appliquée ailleurs). Erreur identique partout :

```
File "logx.spec", line 55, in <module>
    a = Analysis(...)
ValueError: too many values to unpack (expected 2)
```

**Root cause** : `logx.spec` construit `_datas` (liste de tuples `(src,
dest)` à 2 champs, format BRUT attendu par `Analysis(datas=...)`), puis lui
ajoute `Tree('voacap', prefix='voacap')` — mais `Tree()` renvoie une liste
d'entrées à **3 champs** `(dest, src, typecode)`, le format TOC déjà
TRAITÉ (celui de `a.datas`/`a.binaries` APRÈS `Analysis()`, pas avant).
Mélanger les deux formats dans `_datas` casse `Analysis()` dès qu'un
dossier `voacap/` existe — donc systématiquement en CI puisque `voacap/`
est versionné (217 fichiers, voir
[[chantier-voacap-moteur-point-a-point-2026-08-10]]).

**Cette régression était latente depuis le chantier VOACAP du 10/08** — la
ligne `_datas += Tree('voacap', prefix='voacap')` a été ajoutée ce jour-là,
mais **aucun build release n'avait tourné depuis** (le tag `v0.9-beta26` du
09/08 précède le chantier VOACAP). `v0.9-beta27` est donc le 1er tag à
l'avoir révélée — 2 jours de silence total où toute tentative de release
aurait échoué sans que personne ne le sache.

**Correctif** : `Tree()` gardé séparé (`_voacap_tree`), combiné avec
`a.datas` (même format 3-champs, déjà traité) au niveau de `EXE()`, pas
avant `Analysis()` — usage canonique de `Tree()` en spec PyInstaller.

**Vérifié par un vrai build PyInstaller local** (pas juste une relecture de
code) : `python -m PyInstaller --noconfirm --clean logx.spec` en local
Windows a produit `dist/LogXAI.exe` (56 Mo, arbre voacap inclus) sans
erreur. Seule cette vérification par exécution réelle donne une vraie
confiance sur ce genre de bug d'outillage de build — une revue de code seule
n'aurait rien montré de plus qu'un simple contrôle syntaxique.

**Flake croisé pendant la vérification** : la suite pytest complète tournée
EN PARALLÈLE du build PyInstaller local a fait échouer 1 test
(`test_awards_activity_days_enorme_est_borne`, `ConnectionResetError`) par
contention CPU/IO — confirmé non lié en le rejouant seul (vert). Réflexe :
ne pas lancer un build PyInstaller complet (très gourmand CPU) en même
temps qu'une suite pytest si un flake apparaît near-simultanément — le
rejouer isolé avant de le traiter comme un vrai bug.

**Après fix** : tag `v0.9-beta27` supprimé (local + remote) et repoussé sur
le nouveau commit de merge — build multi-OS relancé et réussi en 1m20s,
release publiée avec les 3 exécutables (Linux/macOS/Windows) :
https://github.com/sauveteur71/radioaamateur-program-Contest/releases/tag/v0.9-beta27

**Réflexe pour toute future release** : après TOUT changement touchant
`logx.spec` (ajout de données embarquées, nouveau `Tree()`, etc.), lancer un
vrai `pyinstaller logx.spec` en local avant de pousser un tag — le seul test
qui aurait détecté ce bug 2 jours plus tôt.
