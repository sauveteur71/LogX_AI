---
name: chantier-voacap-moteur-point-a-point-2026-08-10
description: "VOACAP embarqué : compilation voacapl.exe natif Windows depuis les sources NTIA/ITS + logx_voacap.py + endpoint HTTP + UI LOGBOOK/CARTE IA — tâches #380-384 COMPLET, commits 5bf8f8e/91c04f3/98a0d0e, PR #16"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-11T04:59:24.128Z
---

PR #16 fusionnée sur main.

Demandé le 10/08/2026 par F4GLD ("attaque chantier voacap point à point"),
après avoir été DÉLIBÉRÉMENT écarté dans une session antérieure comme "trop
gros pour un axe non prioritaire" — décision explicitement inversée par
l'utilisateur cette fois. Choix validé par AskUserQuestion : moteur VOACAP
RÉEL embarqué (pas une approximation), compilé depuis la source officielle
NTIA/ITS (pas le binaire précompilé voacapw.exe de voacap.com, dont les
conditions de redistribution étaient ambiguës — voir recherche de licence
dans le résumé de session, pas reproduite ici).

## Ce qui a été livré (#380-383, non #384)

- `concours/voacap/win64/voacapl.exe` : binaire Windows natif PE32+
  **statiquement lié** (`-static`, aucune DLL MinGW requise sur la machine
  cible — seulement KERNEL32/msvcrt, présentes sur tout Windows), compilé
  depuis voacapl (github.com/jawatson/voacapl) via MSYS2/MinGW64 gfortran.
  Sortie validée **octet pour octet identique** (après normalisation
  CRLF/LF) à une référence produite sous WSL Ubuntu avec le même code
  source — confirme que le binaire Windows est correct, pas juste "il
  tourne sans planter".
- `concours/voacap/win64/itshfbc/` : arbre de données (coefficients
  CCIR/URSI binarisés, antennes, géo) — ~11 Mo au total, embarqué entier.
- `concours/logx_voacap.py` : génère un fichier `.DAT` VOACAP (format
  Fortran à colonnes fixes), lance `voacapl.exe` en sous-processus, parse
  la sortie `.OUT` en {heure→{bande→{rel, snr_db, mode}}}. `predict()` est
  le point d'entrée public.
- `concours/tests/test_voacap.py` : 20 tests, dont 19 purs (générateur
  `.DAT` + parseur `.OUT` sur un extrait RÉEL figé, pas un texte inventé) +
  1 test d'intégration réel protégé par `voacap_available()` (sauté hors
  Windows).
- `concours/logx.spec` : `Tree('voacap', prefix='voacap')` ajouté — sans
  ça, le moteur ne serait PAS embarqué dans l'exécutable PyInstaller
  distribué (glob() ne couvre pas un dossier profond).
- `logx_voacap._resolve_voacap_root()` : en mode PyInstaller figé,
  `sys._MEIPASS` est en lecture seule (voir `logx_bootstrap.py`) mais
  `voacapl.exe` DOIT pouvoir écrire son sous-dossier `run/` — copie
  l'arbre `voacap/` vers `user_data_dir()` au premier lancement figé, même
  pattern que `_SEED_FILES` dans `logx_bootstrap.py` mais pour un dossier
  entier (`shutil.copytree`) plutôt que des fichiers plats.
- `fetch_ssn()`/`get_ssn_cached()`/`sfi_to_ssn_fallback()` déjà présents
  dans `logx_clusters.py` (tâche #383, écrits dans une session antérieure,
  committés dans le même commit faute de branche dédiée à l'époque) : SSN
  mensuel lissé NOAA/SWPC, avec repli linéaire depuis le SFI N0NBH déjà en
  cache si NOAA est injoignable. `resolve_ssn()` dans logx_voacap.py
  chaîne les deux et renvoie `None` (jamais une valeur inventée) si aucune
  donnée solaire n'est disponible — `predict()` refuse alors le calcul
  plutôt que produire une prédiction fausse en silence.

## #384 : endpoint HTTP + UI point-à-point — FAIT (commits 91c04f3, 98a0d0e)

- `logx_http.py` : endpoint `/data/voacap?dx=<locator ou indicatif>&mode=&power=`
  — résout `dx` via locator Maidenhead d'abord, repli `logx_dxcc.lookup()`
  si ce n'est pas un locator valide. Renvoie `predict()` tel quel en JSON.
- **LOGBOOK** (`logx_logbook.html`/`.js`) : panneau dédié `#voacapOverlay`
  (bouton "PROPAG." près d'AIDE) — indicatif pré-rempli depuis le champ QSO
  en cours, sélecteurs mode/puissance, tableau thermique heure×bande.
- **CARTE IA** (`logx_carte.html`) : bouton "VÉRIFIER VOACAP" dans
  l'infobulle (`#tooltip`) d'un candidat déjà repéré par l'heuristique
  rapide (`logx_paths.py`, tri temps réel de TOUS les spots — jamais
  remplacée). VOACAP est un complément volontairement DISTINCT : calcul
  scientifique lourd, un seul à la fois côté serveur (verrou global dans
  `logx_voacap.py`), jamais utilisé pour noter des dizaines de candidats —
  seulement pour approfondir LE candidat que l'opérateur regarde déjà.
- **Bug réel trouvé et corrigé avant le commit LOGBOOK** : `resolve_ssn()`
  renvoyait un SSN non arrondi sur le chemin de repli SFI→SSN (ex.
  `41.62087912087912`), contrairement au SSN NOAA déjà arrondi à 1
  décimale. Invisible dans le test d'intégration existant qui forçait
  `ssn=110.0` explicitement — trouvé seulement en testant en navigateur
  réel (affichage "SSN 41.62087912087912" dans le panneau LOGBOOK). Fixé
  avec `ssn = round(ssn, 1)` dans `predict()` + test de régression dédié
  (chaîne réelle `fetch_ssn()`/`fetch_solar_data()` pour forcer un cache
  chaud déterministe, cf. piège suivant).
- **Piège de test découvert en écrivant le test de régression SSN** :
  `get_ssn_cached()`/`get_solar_cached()` sont délibérément non-bloquants
  (rafraîchissement en tâche de fond) — un process pytest neuf voit
  TOUJOURS un cache vide au démarrage, faisant sauter le test
  d'intégration silencieusement. Corrigé en appelant explicitement les
  fonctions SYNCHRONES `fetch_ssn()`/`fetch_solar_data()` (les mêmes que
  le rafraîchissement de fond utilise) en tête de test pour forcer un
  cache chaud déterministe, plutôt que de mocker `subprocess`/`open` (deux
  premières tentatives, écartées — trop fragiles).
- Icône du bouton CARTE IA : SVG monochrome réutilisé depuis LOGBOOK
  (cohérence graphite&cuivre) — le premier jet utilisait l'emoji 🔭,
  corrigé avant commit par comparaison directe avec le bouton PROPAG. de
  LOGBOOK.
- **Piège CSS trouvé en vérification navigateur** : le tableau 24h×bandes
  déborde largement des ~195px habituels de `.map-tooltip` — `checkVoacapForSpot()`
  élargit `#tooltip` à `min-width:480px` et reproduit le garde-fou anti-
  débordement à droite déjà présent dans `showTooltip()`. Sans ça, un
  candidat proche du bord droit de l'écran afficherait un tableau coupé.
  Piège symétrique : `showTooltip()` doit AUSSI réinitialiser ce
  `min-width` à chaque nouveau candidat affiché, sinon un tooltip élargi
  par un résultat VOACAP précédent reste large (avec `#ttVoacap` vide en
  dessous) pour le candidat suivant tant qu'on n'a pas recliqué VÉRIFIER.
- **Faux négatifs de l'outil `computer` (clic par coordonnées)** pendant la
  vérification : deux clics via `computer{action:"left_click"}` ont
  timeout à 30s sans qu'aucune erreur console ni requête réseau échouée
  n'apparaisse. Diagnostiqué comme un problème de l'OUTIL (probablement lié
  aux nombreuses erreurs de chargement de tuiles Leaflet qui saturent le
  rendu de la page dans cet environnement sans accès réseau externe), pas
  un bug applicatif — confirmé par `document.elementFromPoint()` au centre
  exact du bouton (renvoie bien le bouton, pas le parent `pointer-events:
  none`) ET par `btn.click()` via `javascript_tool` qui déclenche le vrai
  gestionnaire `onclick` et fonctionne immédiatement. Réflexe pour la
  prochaine fois qu'un clic `computer` timeout sans trace d'erreur :
  vérifier `elementFromPoint()` + `.click()` direct avant de conclure à un
  bug de pointer-events/z-index.
- Uniquement Windows. `voacap_available()` renvoie `False` ailleurs — pas
  de build Linux/macOS (le build WSL de la tâche #380 a servi de RÉFÉRENCE
  de validation, jamais vendu tel quel).

## Pièges rencontrés (dans l'ordre où ils ont mordu)

1. **MSYS2 traite un chemin à double-slash comme un chemin UNC.**
   `sed "s|__PREFIX__|$prefix|" //home/user/.../makeitshfbc` échoue
   silencieusement (« No such file or directory ») quand `$prefix` sans
   slash final concaténé à un `/` littéral produit `//home/...` — Cygwin/
   MSYS interprète un préfixe `//` comme un chemin réseau, pas un chemin
   POSIX normal. Contournement : rejouer la commande à la main avec un
   slash simple. Touché `make install`/`make install-data` à deux endroits
   différents (le hook d'installation ET la binarisation des coefficients)
   — donc pas un cas isolé, vérifier CHAQUE étape `make` qui échoue avec
   ce message précis sur MSYS2/Cygwin.
2. **Variable Fortran non initialisée, jamais détectée par le compilateur**
   (`anttyp90.f`) : `nch_run` utilisé dans `run_directory(1:nch_run)` sans
   jamais être assigné — corrigé en ajoutant `nch_run = len_trim(run_directory)`.
   Ce bug n'a jamais gêné le programme original car `nch_run` faisait
   partie d'un COMMON block ailleurs dans le vrai projet (implicitement
   initialisé à zéro par le linker dans certains cas) ; recompiler le
   fichier isolément a exposé la variable comme vraiment non initialisée.
   → **Devenu sans objet** : `anttyp90.exe` s'est avéré être le MAUVAIS
   outil pour nos antennes par défaut (voir piège 4) et a été retiré du
   dépôt vendu — corrigé "pour rien" dans l'absolu, mais la méthode de
   diagnostic (tester contre le vrai binaire, pas supposer) reste le point
   à retenir.
3. **Buffers Fortran `CHARACTER*80` trop courts pour un chemin de dépôt
   profond** (`anttyp90.f` : `filename`/`gainfile` déclarés `len=80`,
   troncature SILENCIEUSE de Fortran sur assignation à une chaîne à
   longueur fixe, aucune erreur levée). Le chemin réel du dépôt
   (`...\SynologyDrive\RADIOAMATEUR\Programme pour contest\concours\
   voacap\win64\itshfbc`) dépasse 80 caractères une fois concaténé au
   sous-dossier antennes — piège généralisable à TOUT chemin d'installation
   profond (OneDrive, dossiers synchronisés, Program Files imbriqués),
   pas spécifique à cette machine. Élargi à `len=255`. **Idem piège 2**,
   devenu sans objet une fois `anttyp90.exe` écarté — gardé en mémoire
   pour tout futur binaire Fortran tiers compilé dans ce projet : ne
   jamais faire confiance à une déclaration `CHARACTER*N` fixe sans
   vérifier N contre la longueur réelle du chemin d'installation.
4. **`anttyp90.exe` n'est PAS le bon outil pour les antennes "2-D Table"**
   (const17.voa/swwhip.voa, type 11 = "91 valeurs de gain en élévation").
   Son lecteur `ant90_read` attend un format DIFFÉRENT (mots-clés
   `frequency`/`normalize`/`antenna_efficiency` + triplets azimut/
   élévation/gain) — plante avec "Bad integer for item 1 in list input"
   sur nos fichiers. **Découverte cruciale, testée empiriquement plutôt
   que supposée** : `voacapl.exe` régénère en fait `gain01.dat`/
   `gain02.dat` **lui-même, en interne**, à partir du fichier `.voa` +
   l'azimut calculé depuis la carte CIRCUIT — confirmé en supprimant les
   fichiers gain*.dat pré-existants et en relançant `voacapl.exe` seul, il
   les recrée correctement. `anttyp90.exe` (famille "type 90 externe") est
   pour un genre d'antenne complètement différent, jamais utilisé par nos
   antennes par défaut. **Résultat : le pipeline final n'a besoin QUE
   d'UN SEUL sous-processus** (`voacapl.exe`), pas de préprocessing
   antenne séparé — bien plus simple que l'architecture envisagée au
   départ. `anttyp90.exe` retiré du dépôt vendu (code mort).
5. **`voacapl.exe` résout TOUJOURS `run/` comme un sous-dossier FIXE de
   l'argument racine passé en ligne de commande** — confirmé en testant
   des chemins absolus arbitraires pour les fichiers `.dat`/`.out` : le
   binaire les ignore et cherche/écrit systématiquement dans
   `<racine>/run/<nom-nu>`, jamais ailleurs. Conséquence directe :
   `gain01.dat`/`gain02.dat` sont des noms FIXES qu'on ne peut pas
   personnaliser par appel → verrou global (`threading.Lock()`) obligatoire
   dans `logx_voacap.py`, un seul calcul VOACAP à la fois dans tout le
   process. Seuls le `.dat`/`.out` de la carte du circuit peuvent porter un
   nom unique (uuid) puisqu'ils sont passés en argument.
6. **`F5.2` etc. ne veut pas dire "toujours 2 décimales" côté écriture** —
   Fortran accepte, en LECTURE, un nombre de décimales inférieur à celui
   déclaré tant qu'un point décimal explicite est présent dans le champ
   (`"100."` = 100.0 en F5.2, alors que `"100.00"` ferait 6 caractères et
   ne rentrerait pas dans un champ de 5). `_fit_field()` dans
   `logx_voacap.py` réduit les décimales jusqu'à ce que ça rentre plutôt
   que de lever une erreur sur un SSN à 3 chiffres — piège trouvé en
   testant un SSN=110 (le fichier de référence n'utilisait que SSN=100,
   qui rentre "par hasard" en 2 décimales).
7. **Deux fréquences ≥10 MHz adjacentes se "collent" sans espace
   séparateur** dans un champ `F5.2` (`"9.7011.85"` au lieu de
   `"9.70 11.85"`) — vu littéralement dans l'écho d'entrée du fichier
   `.OUT`. `str.split()` casserait ce genre de valeur. Neutralisé dans le
   générateur (`build_dat`) en calculant chaque champ à largeur fixe
   plutôt qu'en joignant par espace ; documenté comme risque pour tout
   futur code qui reparserait une ligne FREQUENCY échoée.
8. **Le champ MODE peut contenir un espace INTERNE** (`"4 E"` = 4 sauts,
   couche E) — un `str.split()` naïf sur la ligne MODE de la sortie `.OUT`
   fusionne ce token en deux et DÉCALE toutes les colonnes suivantes de
   cette ligne précise (silencieux, pas d'erreur). REL et SNR n'ont
   jamais cet espace interne (valeurs toujours ≤4 caractères, gérées sans
   risque par `split()`). Solution dans `_parse_out()` : déduire les
   positions de colonnes (spans) depuis la ligne REL — jamais ambiguë —
   et les appliquer telles quelles à la ligne MODE plutôt que de la
   `split()` indépendamment. Trouvé en testant un VRAI calcul (Paris→New
   York), pas visible sur un texte inventé à la main.
9. **PyInstaller n'embarque QUE ce qui est listé explicitement** — `Tree()`
   nécessaire pour un dossier profond (pas seulement `_datas.append()` fichier
   par fichier comme pour les autres fichiers de référence), sinon
   `voacap_available()` renverrait `False` uniquement dans l'exécutable
   distribué, jamais en dev — piège de la classe « ça marche chez moi »
   version PyInstaller déjà documentée ailleurs dans ce dépôt pour d'autres
   fichiers, généralisée ici à un dossier entier.
10. **`sys._MEIPASS` est en lecture seule** — `voacapl.exe` a besoin
    d'écrire dans son sous-dossier `run/` (voir piège 5), qui est
    OBLIGATOIREMENT un sous-dossier de la racine passée en argument. En
    exécutable figé, cette racine ne peut donc PAS être `_MEIPASS` — copie
    obligatoire vers `user_data_dir()` au premier lancement figé (voir
    `logx_bootstrap.py`, pattern déjà établi pour `_SEED_FILES`, étendu
    ici à un dossier entier via `shutil.copytree`). **Jamais testé en
    conditions réelles PyInstaller** (pas de build de l'exécutable dans ce
    chantier) — à vérifier au prochain build multi-OS.

## Réutilisable pour toute suite (#384 ou un futur moteur Fortran tiers)

- Méthode de travail qui a permis de trouver TOUS les pièges ci-dessus :
  ne JAMAIS déduire un format de fichier ou un comportement binaire d'une
  lecture de code seule — toujours reproduire une exécution RÉELLE (WSL en
  référence, puis Windows) et comparer/tester empiriquement à chaque
  étape. Deux bugs source réels (pièges 2 et 3) et une architecture
  entièrement fausse (préprocessing antenne inutile, piège 4) n'auraient
  jamais été trouvés en lisant seulement le Fortran.
- `logx_bootstrap.resource_dir()`/`user_data_dir()`/`is_frozen()` : le
  point d'entrée correct pour TOUT futur composant embarqué qui a besoin
  d'écrire des fichiers (pas seulement les lire) dans un exécutable
  PyInstaller — ne pas réinventer un autre mécanisme de résolution de
  chemin.
