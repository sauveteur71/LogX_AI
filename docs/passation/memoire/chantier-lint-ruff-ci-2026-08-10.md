---
name: chantier-lint-ruff-ci-2026-08-10
description: "Ajoute ruff (E9+F seulement) à la CI, 50 violations trouvées et corrigées à la main — PR #18 ouverte non fusionnée"
metadata:
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-11T04:59:19.176Z
---

Suite de la session autonome du 10/08/2026 (après VOACAP et le chantier
dialogues non bloquants) : un agent Explore avait trouvé qu'aucun linter
n'existait dans le dépôt (aucun `ruff.toml`/`.flake8`/`pyproject.toml`,
aucune mention dans `requirements.txt` ni les workflows CI) — un vrai gap
de qualité pour un projet qui grossit vite (des dizaines de fichiers .py).

## Décision de scope : E9+F seulement, pas de règles de style

`concours/ruff.toml` sélectionne uniquement `E9` (erreurs de syntaxe) et
`F` (pyflakes classique : imports/variables inutilisés, f-strings sans
placeholder). Décision DÉLIBÉRÉE de ne PAS activer les règles de style
(longueur de ligne, quotes, tri des imports...) : sur un dépôt jamais linté
avant, ça aurait produit des centaines/milliers de "violations" de pure
forme, rendant le garde-fou CI ingérable dès le premier jour. Seulement 50
violations réelles trouvées avec ce scope minimal — un chiffre gérable qui
a permis de tout corriger d'un coup plutôt que de laisser une dette.

## Les 11 corrections manuelles (F841, variable locale inutilisée)

Les 39 autres (F401 imports inutilisés, F541 f-strings sans placeholder)
étaient mécaniquement sûres via `ruff check --fix`. Les 11 F841 ont
nécessité une vérification au cas par cas : **la variable est inutilisée,
mais l'EXPRESSION qui lui est assignée peut avoir un effet de bord à
préserver** — retirer l'assignation ≠ retirer l'appel :
- `logx_cat.py:set_freq()` : `reply = self._cmd(...)` — `_cmd()` envoie une
  vraie commande CAT au poste radio. Gardé l'appel, retiré l'assignation.
- `tests/test_sat_track.py`/`tests/test_omnirig.py` : `rotor = _rotor(monkeypatch)`
  / `fake = _FakeOmniRig(...)` — `_rotor()` installe des mocks via
  `monkeypatch.setattr()` (effet de bord réel), mais `_FakeOmniRig(...)`
  seul (constructeur pur, vérifié en lisant `__init__`) n'en a aucun — ligne
  entièrement supprimée dans ce second cas, juste dé-assignée dans le
  premier.
- `logx_awards.py` : l'import `DEPARTMENTS` (ligne 774) n'était flaggé nulle
  part par F401 alors qu'il est tout aussi inutilisé que sa réassignation
  dans le bloc `except` (ligne 778, seule flaggée par F841) — retiré des
  DEUX endroits après avoir grep vérifié qu'aucune autre fonction du fichier
  ne référence ce nom dans CETTE portée (3 autres usages légitimes de
  `DEPARTMENTS` existent ailleurs dans le fichier, imports locaux séparés
  dans d'autres fonctions). Réflexe à généraliser : F841 sur une
  réassignation dans un `except` peut signaler un import tout aussi mort
  au niveau du `try`, que ruff ne flag pas forcément lui-même.

## État final

- Commit `b03a5d0` sur `feat/lint-ruff-ci`, PR #18
  (https://github.com/sauveteur71/radioaamateur-program-Contest/pull/18).
  Fusionnée sur main.
- `ruff check .` (depuis `concours/`) : 0 violation.
- Suite pytest complète verte après les 11 correctifs manuels.
- Étape "Lint Python (ruff)" ajoutée dans `.github/workflows/check.yml`,
  **bloquante**, juste après la suite pytest.

## Piège de discipline de session évité de justesse

Les premiers correctifs de ce chantier ont été faits SUR LA BRANCHE
`feat/dialogues-non-bloquants-chantier2-suite`, dont la PR #17 était déjà
créée — violation du piège déjà documenté
([[piege-continuer-nouveau-chantier-sur-branche-pr-deja-creee]]). Repéré
avant tout commit (`git status`/`git branch --show-current` vérifiés par
réflexe avant de committer, pas après) : tout le travail non commité a été
mis de côté (`git stash push -u`, y compris `concours/ruff.toml` non suivi),
une branche fraîche créée depuis `main` à jour, puis le stash restauré là.
Aucune perte, mais confirme qu'il faut vérifier la branche courante
AVANT le premier Edit d'un nouveau chantier, pas seulement au moment de
committer — la mémoire existante disait déjà "avant le 1er Edit" mais ce
chantier a démarré sans cette vérification par automatisme de l'enchaînement
(chantier précédent → chantier suivant sans re-belote explicite du contexte
git).
