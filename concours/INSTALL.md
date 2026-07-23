# LogX AI — Installation en application

Deux façons d'utiliser LogX AI :

- **Application autonome** (recommandé) — un seul fichier à lancer, **sans
  installer Python**. C'est ce que décrit ce document.
- Mode développeur — Python 3 installé, puis depuis ce dossier :
  ```
  python -m pip install -r requirements.txt
  python logx_serveur.py
  ```
  (sans le `pip install`, le programme démarre mais perd le pilotage radio
  CAT, le keyer vocal et le calcul EME — sans message d'erreur.)

L'application est un **serveur local** : au lancement, elle démarre en tâche
de fond et **ouvre votre navigateur** sur la page de configuration. Tout se
passe ensuite dans le navigateur (config, logbook, carte, propagation…).

---

## 🪟 Windows

### Utiliser l'exécutable déjà construit
Le fichier **`dist\LogXAI.exe`** est autonome (~35 Mo). Copiez-le où
vous voulez et **double-cliquez** dessus. Une fenêtre noire s'ouvre (le
serveur — laissez-la ouverte) et le navigateur démarre sur l'application.
Pour arrêter : fermez la fenêtre noire, ou Ctrl+C dedans.

> ⚠️ Windows SmartScreen peut afficher « Windows a protégé votre PC » car
> l'exécutable n'est pas signé. Cliquez sur **Informations complémentaires →
> Exécuter quand même**.

### (Re)construire l'exécutable soi-même
Il faut Python 3 installé. Puis, dans ce dossier :
```
build_windows.bat
```
Le script installe d'abord les dépendances (`requirements.txt`) puis
construit. Le résultat apparaît dans `dist\LogXAI.exe`.

---

## 🍎 macOS

PyInstaller ne peut pas fabriquer l'app Mac depuis Windows — **la construction
doit se faire sur un Mac**. Sur un Mac, dans ce dossier :
```
chmod +x build_macos.sh
./build_macos.sh
```
Le résultat apparaît dans `dist/LogXAI`. Lancez-le par double-clic.

> ⚠️ Au 1er lancement, macOS (Gatekeeper) bloque les apps non signées :
> faites **clic droit → Ouvrir**, puis confirmez. À faire une seule fois.

Pas de Mac sous la main ? Le workflow **GitHub Actions** du dépôt
(`.github/workflows/build-release.yml`) construit automatiquement les
exécutables **Windows, macOS et Linux** à chaque tag de release `v*` et les
attache à la release — aucun Mac à posséder.

---

## 🐧 Linux (et Raspberry Pi)

Le code tourne nativement sous Linux (la CI du projet exécute d'ailleurs
toute la suite de tests sous Ubuntu). Deux façons :

- **Exécutable autonome** : `./build_linux.sh` dans ce dossier produit
  `dist/LogXAI` (à construire sur la machine Linux cible ; PortAudio requis
  pour le keyer vocal : `sudo apt install libportaudio2`). Les releases
  GitHub incluent aussi un binaire pré-construit (x86_64), nommé avec le tag
  de la version, par ex. `LogXAI-v0.9-beta2-linux`.
- **Depuis les sources** : `pip install -r requirements.txt` puis
  `python3 logx_serveur.py`.

💡 **Raspberry Pi** : un Pi fait un excellent serveur LogX AI permanent du
shack — il reste allumé, et tous les postes (PC, téléphones, tablettes) se
connectent à son adresse WiFi. Construction sur le Pi avec `build_linux.sh`
(architecture ARM), ou mode sources.

---

## 📱 Android / iPhone

**Aucune application à installer** : les téléphones et tablettes sont des
*clients* du PC (ou du Pi) qui fait tourner LogX AI. Sur le même WiFi :

1. Ouvrez `http://IP-DU-PC:8080/logx_mobile.html` dans le navigateur du
   téléphone (Chrome, Safari...) — page de **saisie tactile** dédiée :
   gros champs, log partagé en direct, identité héritée du serveur.
2. Menu du navigateur → **« Ajouter à l'écran d'accueil »** : LogX AI
   apparaît comme une vraie appli (icône, plein écran, sans barre
   d'adresse) — c'est une PWA, Android et iOS le gèrent nativement.

Le logbook complet, l'écran mural et toutes les autres pages restent aussi
accessibles depuis le téléphone pour consultation.

---

## Où sont mes données ?

L'exécutable ne modifie jamais son propre fichier. Vos données (log, config,
base d'indicatifs, historique) sont dans un dossier **inscriptible** de votre
profil, créé au premier lancement :

- **Windows** : `%APPDATA%\LogXAI\`
  (soit `C:\Users\VOUS\AppData\Roaming\LogXAI\`)
- **macOS** : `~/Library/Application Support/LogXAI/`

On y trouve `shared_log.json`, `logx.db` (le log), `config.json`, etc.
Pour **sauvegarder** votre travail, copiez ce dossier. Pour **repartir de
zéro**, supprimez-le (il sera recréé au prochain lancement).

---

## Multi-poste (WiFi)

Un seul PC lance l'application ; les autres postes du même réseau WiFi
l'ouvrent dans leur navigateur à l'adresse affichée dans le bandeau du
logbook (`http://IP-DU-PC:8080/logx_logbook.html`). Le bouton
**COPIER** du logbook met cette adresse dans le presse-papier.

Le port utilisé est **8080** — assurez-vous qu'aucun autre programme ne
l'occupe (une seule instance de LogX AI à la fois).

> ⚠️ **Si un téléphone/second PC n'arrive pas à charger la page**, c'est
> presque toujours le pare-feu Windows du PC serveur. Deux réglages, sur le
> PC qui fait tourner LogX AI :
> 1. Le WiFi doit être en réseau **« Privé »** : Paramètres → Réseau et
>    Internet → Wi-Fi → votre réseau → Type de profil réseau → **Réseau
>    privé** (en « Public », Windows bloque toutes les connexions entrantes).
> 2. Au premier lancement de `LogXAI.exe`, à la fenêtre « Autoriser
>    l'accès » : cochez **Réseaux privés** puis **Autoriser l'accès**.
