# Binaire jt9 embarqué — Tâche 8

## Provenance

Le binaire `jt9` est issu de **WSJT-X vanilla**, distribution officielle :
- Site officiel : https://wsjt.sourceforge.io/
- Dépôt source : https://sourceforge.net/projects/wsjt/

**Ce répertoire n'embarque PAS un fork** — seul le binaire compilé pour cette version spécifique de WSJT-X y est archivé.

## Version à vendoriser

**VERSION À FIXER PAR L'UTILISATEUR**

Indiquer ici la version exacte de WSJT-X dont le binaire jt9 est tiré. Par exemple :
- WSJT-X 2.6.1 (date de sortie)
- WSJT-X 2.7.0 (date de sortie)

La version doit rester documentée pour permettre la reproductibilité des décodages et faciliter les mises à jour futures.

## Licence : GPLv3

Le binaire jt9 est soumis à la **Licence Générale Publique v3 (GPLv3)**, tout comme LogX AI.

### Obligations conformes à la GPLv3

LogX AI et ses contributeurs doivent :
1. **Fournir ou offrir la source correspondante** : la source jt9 compilée dans ce binaire doit rester disponible (hébergée, ou offerte par demande) pour que tout utilisateur puisse recompiler ou vérifier le code distribué.
2. **Conserver les mentions de copyright** : aucun copyright ou mention de licence ne doit être retiré du code ou de la documentation du binaire jt9.
3. **Rester conforme à la GPLv3** : toute modification du binaire ou de son code source doit être redistribuée sous les mêmes termes.

## Emplacements attendus

Le binaire jt9 doit être placé à l'un des emplacements suivants, respectant la structure multi-OS :

- **Linux/macOS** : `concours/vendor/jt9/jt9` (binaire sans extension)
- **Windows** : `concours/vendor/jt9/jt9.exe` (exécutable Windows)

Le code de `resoudre_jt9()` dans `logx_q65_natif.py` (ligne 62-66) recherche d'abord `jt9.exe`, puis `jt9`, à cet exact emplacement.

### Dépendances runtime à vérifier

Selon l'OS et la build statique/dynamique du binaire WSJT-X source :

- **Windows** : vérifier la présence de DLL FFTW et runtimes Fortran/C nécessaires (libc, libgfortran, libgcc…). Les détailler ici si elles ne sont pas statiquement liées.
- **Linux** : idem — certaines build de WSJT-X incluent des dépendances systèmes (libfftw3f.so.3, libgfortran…).
- **macOS** : vérifier les frameworks et dylib embarqués vs système.

À remplir après validation multi-OS (étape hors scope de ce commit — voir section CI/release ci-dessous).

## Procédure de vendorisation (étapes manuelles)

Les étapes suivantes guident un contributeur ou l'opérateur de release :

1. **Télécharger WSJT-X** depuis https://sourceforge.net/projects/wsjt/files/ pour la version à archiver.
2. **Extraire le binaire jt9** de l'archive WSJT-X (emplacements courants) :
   - **Windows** : fichier `jt9.exe` dans le dossier racine de l'installation.
   - **Linux** : `/usr/bin/jt9` ou `/opt/wsjtx/bin/jt9` selon le package.
   - **macOS** : `WSJT-X.app/Contents/MacOS/jt9`.
3. **Placer** le binaire dans `concours/vendor/jt9/` avec le bon nom de fichier (`.exe` sur Windows, pas d'extension sur Unix).
4. **Tester** que `python -m pytest concours/tests/test_q65_natif.py::test_resoudre_jt9_trouve_binaire_embarque -v` passe (voir test ajouté, Tâche 8).
5. **Vérifier les dépendances** : sur Windows, utiliser `Dependency Walker` ou `ldd` (Linux) / `otool -L` (macOS) pour lister les DLL/dylib attendues au runtime. Les copier dans `concours/vendor/jt9/` si elles ne sont pas déjà disponibles système.
6. **Documenter** : mettre à jour la section « Version à vendoriser » ci-dessus avec la version WSJT-X exacte.
7. **Committer** : intégrer dans une branche (`feat/vendor-jt9`) et créer une PR pour fusion avant release.

## Résolution par `resoudre_jt9(cfg=None)`

La fonction `resoudre_jt9()` dans `logx_q65_natif.py` cherche le binaire jt9 par ordre de priorité :

1. **Config explicite** : `cfg['eme']['jt9_path']` (chemin absolu fourni par l'utilisateur dans `config.json`).
2. **Binaire embarqué** (Tâche 8) : `concours/vendor/jt9/jt9.exe` (Windows) ou `concours/vendor/jt9/jt9` (Unix).
3. **PATH système** : `shutil.which('jt9')` ou `shutil.which('jt9.exe')` — pour les utilisateurs avec WSJT-X déjà installé.

Si aucune source ne trouve le binaire, lève `FileNotFoundError` avec un message explicite invitant l'utilisateur à :
- Installer WSJT-X, **OU**
- Fournir `eme.jt9_path` dans `config.json`, **OU**
- Attendre la prochaine release qui inclura le binaire embarqué.

## En attente utilisateur — CI et release (hors scope de ce commit)

Les deux tâches suivantes sont **HORS DE CETTE TÂCHE** et laissées à l'opérateur de release :

1. **Câblage CI (`build-release.yml`)** : ajouter des étapes de téléchargement/commit automatique du binaire jt9 multi-OS au déclenchement d'une release (`on: release`). Doit télécharger WSJT-X, extraire jt9, placer dans `concours/vendor/jt9/`, et committer avant de finaliser le tag/artefact de release.

2. **Binaire réel** : un binaire WSJT-X réel, testé sur chaque OS (Windows, Linux, macOS), doit être fourni avant la première release contenant ce commit. Jusqu'à ce moment, les utilisateurs suivront la procédure manuelle ci-dessus ou utiliseront le PATH système.

Voir le plan complet de la Tâche 8 (`docs/passation/PASSATION.md`) pour les détails d'orchestration et de timing.

## Voir aussi

- `concours/logx_q65_natif.py` — module de décodage Q65 natif, fonction `resoudre_jt9()`.
- `concours/tests/test_q65_natif.py` — tests de validation du décodage et de la résolution du binaire.
- `docs/passation/PASSATION.md` — plan détaillé des tâches 1-8 et timing de release.
