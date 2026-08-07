# Contribuer à LogX AI

Merci de l'intérêt porté au projet ! Ce guide couvre l'essentiel pour
proposer un correctif, une fonctionnalité ou une nouvelle définition de
concours. Pour signaler un bug ou suggérer une idée sans toucher au code,
pas besoin de lire cette page : les [gabarits d'issue](.github/ISSUE_TEMPLATE/)
suffisent.

Toute contribution est soumise au [code de conduite](CODE_OF_CONDUCT.md) du
projet.

## Installer l'environnement de développement

Le cœur du serveur n'utilise que la bibliothèque standard Python — les
dépendances ci-dessous ne couvrent que la validation des règlements et le
pilotage matériel (chacune est optionnelle : l'appli démarre sans, avec la
fonctionnalité correspondante simplement désactivée).

```bash
git clone https://github.com/sauveteur71/radioaamateur-program-Contest.git
cd radioaamateur-program-Contest/concours
python -m venv .venv
.venv\Scripts\activate   # ou source .venv/bin/activate sur macOS/Linux
pip install -r requirements.txt
python logx_serveur.py
```

Le serveur écoute sur `http://127.0.0.1:8080` (voir
[docs/GUIDE_UTILISATEUR.md](docs/GUIDE_UTILISATEUR.md) pour la prise en
main). Python 3.11+ recommandé (c'est la version utilisée par la CI).

## Lancer les tests

Toujours depuis `concours/` :

```bash
python -m pytest -q
```

La suite dépasse le millier de tests — attends-toi à quelques minutes. Un
sous-ensemble utilise un vrai moteur JavaScript (`py_mini_racer`, package
optionnel) pour exécuter le code JS des pages HTML sans navigateur ; ces
tests sont automatiquement ignorés (`pytest.importorskip`) si le package
n'est pas installé, plutôt que d'échouer.

Si un fichier de règlement de concours (`contests/*.json` ou équivalent) a
été touché, valide-le aussi :

```bash
python logx_validate.py
```

La CI (`.github/workflows/check.yml`) relance exactement ces deux commandes
sur chaque *pull request* — un correctif dont les tests ne passent pas en
local ne passera pas non plus sur GitHub.

## Conventions du projet

- **Français partout** : interface, commentaires de code, messages de
  commit. Le logiciel propose 8 langues à l'utilisateur final via
  `logx_i18n.js`, mais le code et la documentation interne restent en
  français.
- **Commentaires qui expliquent le POURQUOI, pas le QUOI** : le code
  lui-même dit ce qu'il fait ; un commentaire n'a de valeur que s'il explique
  une contrainte cachée, un piège déjà rencontré, ou une décision qui
  surprendrait sinon un·e relecteur·rice.
- **Un correctif de bug s'accompagne d'un test qui aurait échoué avant lui**
  — le dossier `tests/` compte plusieurs "tests de reproduction" qui rejouent
  l'ancien code (`git show <hash>:fichier`) pour prouver qu'un bug se
  reproduisait avant son correctif ; pas obligatoire, mais fortement
  encouragé pour tout correctif non trivial.
- **Pas de dépendance lourde ajoutée sans discussion préalable** (ouvrir une
  issue d'abord) : le projet vise à rester un exécutable autonome, facile à
  construire sur Windows/macOS/Linux.

## Proposer un nouveau concours

Les définitions de concours vivent dans un format JSON versionné
(`contest_schema.json`) — voir la section correspondante de
[docs/LogX_AI_PRD.md](docs/LogX_AI_PRD.md) pour le contrat de données exact.
Le logiciel embarque déjà une extraction assistée par IA (lecture d'un
règlement PDF/web) pour défricher une première version, toujours soumise à
relecture humaine avant d'être proposée en PR.

## Processus de *pull request*

1. Une branche par sujet, à partir de `main`.
2. Les commits en français, qui expliquent le *pourquoi* plutôt que de
   décrire le diff (le diff se suffit à lui-même).
3. `python -m pytest -q` vert en local avant d'ouvrir la PR.
4. Le [gabarit de PR](.github/PULL_REQUEST_TEMPLATE.md) se remplit
   automatiquement à l'ouverture — la checklist aide à ne rien oublier.
5. La CI doit passer avant fusion (`Check LogX AI` sur GitHub Actions).

Pas d'obligation de PR "parfaite" du premier coup : les allers-retours en
relecture font partie du processus.
