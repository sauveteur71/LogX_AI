---
name: rebrand-logx-ai
description: "RENOMMAGE CRITIQUE : RadioContest AI -> LogX AI, tous les fichiers radiocontest_* renommés en logx_* (commit 0b92b90, 20/07/2026)"
metadata:
  type: project
  originSessionId: e727f52a-b66b-4617-abb1-afba96fda04d
  modified: 2026-07-20T11:35:07.590Z
---

**Le produit s'appelle désormais LogX AI, pas RadioContest AI.** Logo fourni par l'utilisateur (image AI-générée : "Log" orange, "X" stylisé navy/orange avec effet particules, "AI" navy), palette : `#FF5030` (orange logo), `#000030` (navy sombre), `#FFFFFF`.

**TOUS les fichiers `concours/radiocontest_*.py/.js/.html` ont été renommés en `concours/logx_*`** (`git mv`, historique préservé). Toute mémoire ANTÉRIEURE à cette date qui mentionne un chemin `radiocontest_X.py` doit être lue comme `logx_X.py` — les anciens noms n'existent PLUS sur disque. Cas particuliers :
- `radiocontest_serveur.py` → `logx_serveur.py` (point d'entrée)
- `radiocontest.spec` → `logx.spec` (PyInstaller)
- `radiocontest_icon.svg` → `logx_icon.svg`
- `radiocontest.db` → `logx.db` (base SQLite locale, gitignorée — le fichier réel sur disque a aussi été déplacé, pas seulement le nom dans le code)
- `.gitignore` mis à jour en conséquence (`concours/logx.db`)

**Texte de marque** : toute occurrence de "RadioContest AI"/"RadioContest"/"RADIOCONTEST" dans les titres de page, en-têtes, prompts IA (`logx_prompts.py`), schéma JSON (`contest_schema.json`), manifest PWA, cache du service worker → "LogX AI"/"LogX"/"LOGX". Le format d'export `custom_contests.json` (`'format': 'logx-custom-contests'`) et le paramètre `hamdb.org/.../logxai` (attribution API HamDB) ont aussi été renommés — sans risque de rétrocompatibilité cassée (aucun code ne valide ces valeurs à l'import).

**Logo intégré en en-tête** (`concours/logx_logo.png`, copié depuis `logoXAI2.png` à la racine du repo — PAS transparent, fond gris clair `#E4E8EB`) sur les 6 pages principales (CONFIG/LOGBOOK/CARTE/PROPAG/DÉPARTEMENTS/CALENDRIER), dans un badge blanc arrondi (`.logo-badge`) pour contraster sur l'en-tête sombre. `logx_carte.html` garde un en-tête texte simple ("LOGX AI") plutôt que l'image (structure différente, pas de `.logo` div).

**Charte de couleur** : `--accent` passe de `#FF6B00` à `#FF5030` (+ variantes RGBA `rgba(255,80,48,...)` et thème clair `#CC4026`) sur les 10 pages HTML, l'icône SVG et le manifest — `--accent2` (cyan `#00D4FF`, contraste sur fond sombre) et les couleurs de fond (`--bg`/`--bg2`/`--bg3`, déjà proches du navy de marque) n'ont volontairement PAS été touchés (risque de casser le contraste/lisibilité pour un gain visuel marginal).

**Migration localStorage non destructive** : toutes les clés `radiocontest_*` (config, macros, profils, log, voice_macros, api key...) sont copiées vers `logx_*` au premier chargement si la nouvelle clé n'existe pas encore (voir le haut de `logx_i18n.js`, plus une copie inline dans `logx_panel.html`/`logx_scope.html`/`logx_wall.html` qui n'incluent pas i18n.js). Sans ça, la config/les macros déjà sauvegardées par l'utilisateur dans SON navigateur auraient semblé avoir disparu après la mise à jour — l'ancienne clé n'est jamais supprimée (idempotent, sans risque à ré-exécuter).

**Bug découvert et corrigé en marge** : `do_GET`/`_raw()` de `logx_http.py` ne servaient AUCUN fichier avec un Content-Type `.png` (seulement js/css/json/svg/webmanifest) — ajouté, sinon le nouveau logo PNG ne s'affichait pas correctement.

**Piège de vérification (déjà documenté ailleurs, reconfirmé ici)** : le navigateur automatisé de cette session échoue de façon FLAKY et NON DÉTERMINISTE (`net::ERR_ABORTED`/`ERR_CONNECTION_RESET`) à charger de gros fichiers statiques (`logx_logbook.js`, `logx_logo.png`), MÊME sur un serveur isolé flambant neuf sans aucune charge concurrente — 1 échec sur 5 requêtes identiques au même fichier. Ce n'est PAS un bug de l'app (confirmé par Content-Length correct + succès sur reload) — c'est une limite de l'outil de preview de CETTE session. Ne pas perdre de temps à sur-diagnostiquer un "échec de chargement" isolé : recharger une fois suffit à distinguer un vrai bug d'un accident du tooling.

**Technique de vérification isolée** (déjà utilisée avant, reconfirmée efficace) : copier `concours/` dans un dossier scratch, changer `PORT` dans `logx_utils.py` vers un port libre, supprimer les fichiers d'état réels copiés par erreur, lancer `python logx_serveur.py` en arrière-plan — teste sans jamais toucher au serveur réel de l'utilisateur (port 8080, actif en parallèle de cette session — son `.server_config.json` a d'ailleurs changé pendant cette session, confirmant qu'il travaillait dessus en même temps).

**Reste à faire / non touché délibérément** :
- Les 3 PNG sources à la racine du repo (`Gemini_Generated_Image_*.png`, `logoXAI.png`, `logoXAI2.png`) restent NON suivis par git (matériel source de l'utilisateur, pas un asset de l'app — seule la copie dans `concours/logx_logo.png` est trackée).
- Le launcher personnel `LANCER_RADIOCONTEST.bat` (gitignoré) a eu son CONTENU mis à jour (référence `logx_serveur.py`) mais garde son ancien NOM de fichier — l'utilisateur devra le relancer avec ce nom, ou le renommer lui-même s'il veut un raccourci cohérent avec la nouvelle marque.
- L'utilisateur doit redémarrer son serveur réel (`python logx_serveur.py` désormais, pas `radiocontest_serveur.py`) pour voir le changement — le process en cours d'exécution ne le remarquera pas tout seul (fichiers Python déjà chargés en mémoire).
