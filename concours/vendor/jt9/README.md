# Binaire jt9 embarqué — Tâche 8

## Provenance

Le binaire `jt9` est issu de **WSJT-X vanilla**, distribution officielle :
- Site officiel : https://wsjt.sourceforge.io/
- Téléchargements : https://wsjtx.github.io/wsjtx/downloads.html
- Dépôt source (SourceForge) : https://sourceforge.net/projects/wsjt/

**Ce répertoire n'embarque PAS un fork** — seul le binaire compilé de WSJT-X
vanilla est vendorisé, avec ses dépendances runtime.

## Version vendorisée

- **Windows / macOS** : **WSJT-X 2.7.0** (sortie du 15/02/2025), épinglée dans
  l'action CI `.github/actions/fetch-jt9` (entrée `wsjtx_version`). Fichiers
  officiels : `wsjtx-2.7.0-win64.exe`, `wsjtx-2.7.0-Darwin.dmg`.
- **Linux** : paquet **`wsjtx`** de la distribution du runner (Ubuntu). La
  version suit la distribution (≥ 2.5, donc Q65 présent) — divergence assumée :
  `apt` est le chemin d'installation le plus fiable sous Linux et évite les
  conflits de dépendances (libgfortran) connus des `.deb` hors-distribution.

Pour changer de version WSJT-X (Windows/macOS), modifier la valeur par défaut
de `wsjtx_version` dans l'action `fetch-jt9`.

## Récupération : automatique en CI (pas de binaire dans git)

Choix d'architecture : **le binaire n'est PAS commité dans git** (dépôt léger).
Il est **téléchargé et déposé ici au moment du build de release** par l'action
composite `.github/actions/fetch-jt9`, appelée depuis :

- `.github/workflows/build-release.yml` — embarque `vendor/jt9/` dans
  l'exécutable PyInstaller de chaque OS (`logx.spec`, `binaries=`).
- `.github/workflows/verify-jt9.yml` — vérifie sur les 3 OS que le jt9
  récupéré décode l'échantillon EME de référence (déclenchement manuel).

Le `.gitignore` de ce dossier ignore tout binaire fetché en local, ne gardant
sous git que ce README et le `.gitignore`.

### Détail par OS (voir l'action pour la source de vérité)

- **Windows** : l'installeur NSIS est extrait par 7-Zip ; `jt9.exe` + les DLL
  voisines (fftw3f, libgfortran, runtime MinGW…) sont copiés ici. Windows
  cherche les DLL à côté de l'exe.
- **Linux** : `apt-get install wsjtx` ; `jt9` + ses `.so` jt9-spécifiques sont
  copiés ici (le noyau système — libc, loader, pthread — reste celui de
  l'hôte).
- **macOS** : le `.dmg` est monté ; `jt9` est copié et `dylibbundler`
  relocalise ses dylibs non-système à côté de lui (`@executable_path`).

`decoder_wav()` (`logx_q65_natif.py`) ajoute ce dossier au chemin de recherche
des bibliothèques dynamiques (`LD_LIBRARY_PATH`/`DYLD_LIBRARY_PATH`) pour que
jt9 trouve ses dépendances — indispensable dans l'exécutable PyInstaller gelé,
qui réinitialise ce chemin pour les processus fils.

## Licence : GPLv3

Le binaire jt9 est soumis à la **Licence Générale Publique v3 (GPLv3)**, comme
LogX AI. Obligations respectées :

1. **Source correspondante disponible** : le code source de la version
   vendorisée reste offert par WSJT-X (tarball `wsjtx-2.7.0.tgz` et suivants
   sur SourceForge, ci-dessus) — aucune recompilation modifiée n'est faite ici.
2. **Mentions de copyright conservées** : le binaire est vanilla, aucun
   copyright ni mention de licence n'est retiré.
3. **Mêmes termes en cas de modification** : le binaire n'est pas modifié.

## Résolution par `resoudre_jt9(cfg=None)`

`resoudre_jt9()` (`logx_q65_natif.py`) cherche jt9 par ordre de priorité :

1. **Config explicite** : `cfg['eme']['jt9_path']` (chemin absolu).
2. **Binaire embarqué** : `vendor/jt9/jt9.exe` (Windows) ou `vendor/jt9/jt9`
   (Unix) — présent dans les releases grâce à `fetch-jt9` + `logx.spec`.
3. **PATH système** : `jt9`/`jt9.exe` (utilisateurs avec WSJT-X installé).

Sinon : `FileNotFoundError` explicite. En développement local, l'étape 2 est
absente (binaire non commité) : le repli PATH/`jt9_path` prend le relais.

## Voir aussi

- `concours/logx_q65_natif.py` — `resoudre_jt9()`, `decoder_wav()`.
- `concours/tests/test_q65_natif.py` — dont le test d'intégration EME.
- `.github/actions/fetch-jt9/action.yml` — source de vérité du fetch.
- `concours/logx.spec` — embarquement dans l'exécutable.
