# LogX AI — Installation en application

Deux façons d'utiliser LogX AI :

- **Application autonome** (recommandé) — un seul fichier à lancer, **sans
  installer Python**. C'est ce que décrit ce document.
- Mode développeur — `python logx_serveur.py` depuis ce dossier.

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
Le résultat apparaît dans `dist\LogXAI.exe`.

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

Pas de Mac sous la main ? La construction peut aussi se faire gratuitement
via **GitHub Actions** (runner `macos-latest`) — demandez-moi le workflow.

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
