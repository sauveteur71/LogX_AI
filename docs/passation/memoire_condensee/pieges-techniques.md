---
name: pieges-techniques
description: "Référence consolidée des pièges techniques rencontrés sur LogX AI (33 fiches d'origine, fusionnées le 21/08/2026) — vérification navigateur, tests py_mini_racer, git/worktree, Bash, CSS, domaine radioamateur, Python"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e5854853-072f-4b5f-895a-57c4ab0111d2
  modified: 2026-08-21T03:35:18.128Z
---

Consolidation du 21/08/2026 de 33 fiches `piege-*.md` individuelles (conservées telles quelles, git-trackées, dans `docs/passation/memoire/` du dépôt — cette fiche est la version condensée pour la mémoire active). Organisé par thème, pas par date.

## A. Vérification navigateur — le piège le plus récurrent de tous

**État périmé après une action async.** Déclencher un `click()`/`dispatchEvent()` qui appelle une fonction `async` PUIS lire l'état résultant (`location.href`, classes DOM) **dans le même appel `javascript_exec`** renvoie l'état D'AVANT — la continuation après le premier `await` tourne en microtask, ordonnancée après la fin du bloc synchrone courant. Toujours scinder en deux appels d'outils séparés : un qui déclenche, un second (après un vrai aller-retour) qui lit.

**Cache HTTP du navigateur masque un correctif JS.** `navigate({force:true})` recharge la page HTML mais pas forcément les `<script src>` référencés — un correctif JS peut sembler ne pas s'appliquer alors qu'il tourne, juste servi depuis le cache. Signe : des `console.log()` de diagnostic ajoutés exprès n'apparaissent pas. Comparer le contenu réellement exécuté à `fetch(url).then(r=>r.text())` depuis la page elle-même ; le correctif fiable est un hard reload (`Ctrl+Shift+R`), pas un nouveau `navigate()`.

**`localStorage` ne se resynchronise PAS au reload.** Écrire dans `localStorage.logx_config` pour un test, puis recharger la page (même `force:true`) ne purge rien — c'est un cache client persistant par origine. Après tout test qui touche `localStorage` sur une page servie par le serveur réel, restaurer explicitement (`fetch('/config').then(r=>r.json()).then(cfg=>localStorage.setItem('logx_config', JSON.stringify(cfg)))`), jamais compter sur un `navigate()` pour « nettoyer ».

**Un Service Worker périmé casse `fetch()` avec `Failed to fetch`.** Réutiliser un port de test déjà servi lors d'une session précédente peut ressusciter un SW enregistré alors, qui intercepte les requêtes et échoue au lieu de les laisser passer au nouveau serveur — alors que `curl`/Python direct sur le même endpoint répond normalement. Vérifier `navigator.serviceWorker.getRegistrations()` avant de suspecter le code ; désinscrire + vider les caches si un SW traîne. Préférer un port de test jamais réutilisé dans la session.

**`#setupModal` (ou tout overlay plein écran) intercepte les clics en silence sur un serveur de test frais.** Un clic sur un champ visible ne fait rien, sans erreur ; `document.activeElement` reste `BODY`. Vérifier `document.elementFromPoint(x,y)` à la position ciblée avant de suspecter le code modifié. Sur LOGBOOK : remplir `#setupCallsign`/`#setupLocator`/`#setupOperator` + appeler `setupDone()` avant toute interaction.

**Le serveur déjà lancé sert le DÉPÔT PRINCIPAL, pas le worktree courant** (`.claude/launch.json` d'un worktree pointe souvent vers un chemin absolu du dépôt principal, exprès, pour qu'un seul process partage l'accès au matériel réel). Une édition dans le worktree n'apparaît jamais tant qu'on pointe sur ce port, même après hard reload — comparer le contenu réellement servi (`fetch()`) au fichier du worktree pour distinguer ce cas d'un problème de cache. Pour vérifier du JS pur sans toucher au serveur partagé : `python -m http.server <port> --directory concours` (statique, zéro risque, aucun endpoint POST possible).

**`/concours/logx_logbook.html` (avec le préfixe) sert du VIDE** sur le serveur réel — toujours naviguer vers `/logx_logbook.html` à la racine, jamais avec le préfixe `/concours/`.

**Le bac à sable de test ne simule pas fidèlement `window.open()`** (fenêtres détachées) ni la boucle UDP locale (émission→réception sur soi-même) — un échec dans ce cas précis n'est pas forcément un bug de code, vérifier d'abord via navigation HTTP directe / logique isolée avant de conclure.

**`qsoLog.push(...)` de test peut apparaître dans le tableau réel SANS `renderLog()` explicite** — un cycle de rafraîchissement automatique (polling) peut re-rendre tout seul. Toujours `filter()` + `renderLog()`/`updateStats()` explicites juste après un push de test, et confirmer par un hard reload serveur que rien n'a persisté.

## B. Tests JS (py_mini_racer / V8 embarqué) — les limites de l'infrastructure, pas du code produit

- **`Intl` n'existe PAS DU TOUT** dans ce V8 (pas juste des données ICU manquantes) — `new Intl.DateTimeFormat(...)` lève `ReferenceError`. `toLocaleDateString()`/`toLocaleTimeString()` fonctionnent (repli non-ICU). Stub minimal si un test doit couvrir un chemin `Intl` : `var Intl = {DateTimeFormat: function(){return {formatToParts:function(){return [{type:'timeZoneName',value:'CET'}]}}}}`.
- **`\p{...}` (propriété Unicode) est une `SyntaxError`** dans ce V8 sans ICU — une regex littérale invalide n'est compilée qu'à sa PREMIÈRE évaluation, donc peut dormir des mois si la ligne n'est jamais atteinte en test. Ne jamais utiliser de propriété Unicode dans du JS destiné à être exercé par la suite py_mini_racer.
- **Un dict Python passé en seed JSON n'est qu'un instantané figé** — les mutations JS faites ensuite (`classList.toggle`) ne se répercutent JAMAIS dans le dict Python d'origine. Toujours relire l'état via `ctx.eval(...)`, jamais via le miroir Python. Et `ctx.eval()` sur un tableau JS renvoie un `JSObject` sans `len()` — repasser par `json.loads(ctx.eval("JSON.stringify(x)"))`.
- **Un stub de faux DOM trop PAUVRE rend un bloc entier inexécutable** (ex. `querySelectorAll` qui renvoie toujours `[]`) — zéro couverture sans qu'aucun test ne rougisse. Un stub trop **PERMISSIF** est pire : il exécute le chemin et certifie du code qui ne peut pas tourner dans un vrai navigateur (ex. `dataset:{}` qui accepte un tiret, alors qu'un vrai `DOMStringMap` le refuse — un `aria-label` a fait planter en silence toute la traduction des éléments suivants). Un faux DOM doit reproduire les REFUS de l'API, pas seulement ses succès.
- **Un nombre PAIR de passes masque une oscillation** (bascule à chaque passe = état final identique) — asserter après CHAQUE passe, jamais seulement à la fin.

## C. Git, worktree, process — perte de travail et confusion de branche

- **Édition perdue, dépôt sous SynologyDrive** : un fichier fraîchement édité peut revenir SILENCIEUSEMENT à son état d'avant (course avec la synchronisation cloud), reproduit avec ET sans agents parallèles. Ne jamais faire confiance au rapport d'un agent — `git status --short` + grep indépendant du marqueur attendu, **juste avant de committer** (pas seulement juste après l'édition — la fenêtre de course peut s'ouvrir n'importe quand entre les deux).
- **Un Workflow d'audit en tâche de fond peut committer DANS le worktree où l'on travaille**, même isolé exprès — un worktree isole le répertoire, pas le dépôt. Vérifier `git status --short` + `git log --oneline -3` avant tout commit/rebase ; ne jamais stash/jeter des modifications non commitées qui ne sont pas de soi.
- **Continuer un nouveau sujet sur une branche dont la PR est déjà créée/mergée** casse `gh pr merge --delete-branch`. Dès qu'un nouveau sujet démarre (utilisateur ou soi-même), vérifier `git branch --show-current` et ouvrir une nouvelle branche AVANT le premier Edit — réflexe à appliquer même en enchaînement autonome, pas seulement sur demande explicite.
- **Deux dépôts GitHub distincts** peuvent exister sous le même compte (code vs site vitrine) — ne jamais déduire le dépôt cible d'une capture d'écran seule, lister via `gh api user/repos` en cas de doute sur le nom affiché.
- **Un artefact lu sans vérifier son contexte ment** : un serveur laissé tourner depuis la veille sert du vieux code (200 OK, sans indiquer son âge) ; un rapport `--junitxml` n'est réécrit qu'à la FIN d'une passe encore en cours ; `git log` peut être lu sur une branche différente si une autre session a checkouté dans le MÊME répertoire ; une CI verte ne vaut que pour SON run, même à SHA identique (course réseau possible) ; un inventaire de grep peut périmer si une branche parallèle avance pendant le chantier. Toujours vérifier l'horodatage/l'origine avant de conclure, et arrêter tout serveur lancé soi-même dès la vérification finie.

## D. Bash / outils shell sur ce poste (Windows/Git Bash)

- **`cmd ; echo $?`** rapporte le code de sortie de `echo` (toujours 0), pas celui de `cmd` — a fait annoncer une suite verte avec des échecs réels. Écrire le VRAI code dans le fichier de log lui-même, en deux commandes séparées (`cmd > out 2>&1` puis `echo "EXIT=$?" >> out`), jamais chaîné par `;`.
- **`run_in_background: true` + `&` shell interne à la même commande = double détachement.** Le harness reçoit la notification de fin du WRAPPER, pas de la vraie commande, qui continue orpheline. Utiliser SOIT l'un SOIT l'autre, jamais les deux.
- **Un heredoc `bash <<'PY'` mange un niveau d'antislash** — `[^"\\]` arrive comme `[^"\]` (regex cassée), `'\\U0001F3DE'` devient l'emoji littéral. Dès qu'un script contient des antislashs : l'écrire avec l'outil Write dans le scratchpad, jamais en heredoc.
- **CRLF invisible casse `Workflow(scriptPath)`** — `open(path,'w',encoding='utf-8')` sans `newline=''` traduit `\n`→`\r\n` sur Windows ; une relecture texte normale (universal newlines) ne le voit JAMAIS, seule une lecture binaire (`'rb'` + `.count(b'\r')`) le révèle. `newline=''` sur CHAQUE écriture ET relecture de la chaîne de génération d'un script destiné à `Workflow`.

## E. CSS

- **`min-width` générique gagne TOUJOURS sur un `max-width` inline plus spécifique** en cas de conflit — la cascade (spécificité, ordre) ne départage jamais deux propriétés DIFFÉRENTES. Avant d'ajouter un `min-width` par défaut, lister toutes les instances héritantes et vérifier si l'une pose déjà un `max-width` inline plus petit.
- **Un conteneur `flex-wrap` partagé entre deux usages** (boutons uniques vs lignes composites) affiche ces dernières en mosaïque désordonnée sans largeur propre — donner `width:100%;box-sizing:border-box` à chaque ligne composite, et écraser les bornes héritées sur ses enfants.

## F. Domaine radioamateur — ne jamais écrire une table de mémoire

- **Charger le skill `anthropic-skills:radioamateur` AVANT toute table de domaine** (plan de bandes, segments, fréquences d'appel, puissances). Un premier jet réutilisant l'annexe d'un manuel nord-américain a classé FT8 en PHONE sur 4 bandes, inventé une bande 222 MHz absente en région 1, proposé le 4 m hors de France — quatre défauts mesurés, aucun deviné.
- **Le plan officiel et l'usage réel ne coïncident pas** : 144,174 MHz est en segment SSB du plan IARU R1 et c'est pourtant LA fréquence FT8 du 2 m. Une table de fréquences d'appel numériques doit être consultée AVANT le découpage par plage, pas déduite de lui.
- **Classer un spot ≠ dessiner la bande de l'opérateur** — une station étrangère en règle chez elle peut apparaître hors de l'allocation française ; marquer, ne jamais masquer.
- **Une liste d'identifiants (concours, contest bands…) écrite à la main diverge dans les DEUX sens** (oublie des entrées réelles ET garde des fantômes) sans qu'aucun test ne le voie — chercher le CHAMP qui porte l'info dans la source de vérité, ou dériver des données réelles, jamais recopier une liste séparée. Vérifier par un script de comptage (`set(a) ^ set(b)`), pas à l'œil.
- **Un hex identique à l'accent du thème peut être une DONNÉE sans rapport** (code-couleur par groupe de concours, par opérateur, par bande) — lire le contexte de chaque groupe de résultats d'un grep avant tout remplacement en masse.
- **Vérifier sur données réelles, pas sur la structure du code** : un band map peut être mort depuis toujours (unités kHz/MHz mélangées entre sources) avec une CI verte à 100 % — la suite ne teste que la structure, pas ce que l'écran montre avec de vrais spots. Une suite verte ne prouve rien sur un affichage tant qu'on n'a pas regardé le rendu alimenté par la vraie source.

## G. Python / bibliothèques système

- **`time.monotonic()` n'a PAS l'epoch Unix pour origine** — un sentinel `0.0` pour dire « il y a longtemps » peut valoir quelques secondes seulement sur un système qui vient de démarrer (CI fraîche, ou PC relancé pendant un concours). Toujours une valeur négative garantie (`-1e6`) ou mocker `time.monotonic()` lui-même — jamais `0.0`. Confirmé en PRODUCTION une fois, pas seulement en test : `logx_departments.py` avait le même sentinel, désactivant silencieusement le repli géographique pendant les 5 premières minutes après un redémarrage.
- **pyserial 3.5 rejette `rts=`/`dtr=` comme kwargs du constructeur `Serial()`** (`ValueError`) — seulement des propriétés d'instance à poser AVANT `open()` : construire fermé (`serial.Serial()`), poser `.port`/`.rts`/`.dtr`, puis `.open()`. Aucune impulsion haute ne se produit si l'ordre est respecté.
- **26 tests écrivaient des fichiers d'état PARTAGÉS dans `concours/`** (course avec le serveur réel ou une suite concurrente). Le garde-fou qui les a tous trouvés photographie la date des DOSSIERS, pas seulement des fichiers — un test qui écrit puis supprime dans son `finally` ne laisse aucune trace entre deux photos de fichiers seuls, mais change le mtime du dossier parent.

## H. Config partagée / instance « isolée »

**Un port différent isole le RÉSEAU, pas le DISQUE.** Une instance `logx_serveur.py` lancée sur un autre port pour tester sans risque continue de lire/écrire le MÊME `.server_config.json` que la production (chemin relatif codé en dur). `saveConfig()`/tout `POST /config/save` reste dangereux même en « isolation » par port ; seule une instance statique (`python -m http.server`, pas de backend) ou une copie complète du dossier avec un `PORT` différent est réellement isolée. `/config/save` fait un REMPLACEMENT COMPLET de la config, jamais une fusion — un test qui poste un objet partiel écrase silencieusement le reste (identifiants compris).

## J. Flakes de test qui étaient de vrais bugs produit (deux épisodes)

**Épisode 1 (27/07) — fermer une socket au tampon de réception non vide envoie un RST qui détruit la réponse déjà émise.** Les chemins de refus HTTP (429 anti-bruteforce, 403 sans jeton) ne lisaient pas le corps avant de fermer la connexion — l'utilisateur recevait une erreur réseau au lieu du message utile, de façon aléatoire (~1 échec par passe, jamais le même test). Correctif : vider le corps (borné) avant de répondre. Méthode qui a marché et qui reste la référence pour tout flake futur : (1) ne jamais conclure à une régression sur un échec isolé — relancer le test seul 5-10 fois ; (2) **reproduire SOUS CHARGE** (suite complète en fond + test seul martelé 10-12 fois) — c'est ce qui a fait apparaître le vrai message d'erreur au lieu d'un simple échec d'assertion ; (3) ne jamais affaiblir une assertion pour faire taire un flake ; (4) si un test existant tombe après le correctif, vérifier s'il testait le MÉCANISME ou l'INVARIANT réel (un test acceptait même le RST comme « fermeture attendue », donc tolérait une réponse perdue).

**Épisode 2 (31/07) — un verrou fantôme après une exception hors `try`.** `Thread.start()` peut lever sous famine ; si les premières lignes de la tâche de fond sont hors de tout `try`, le thread meurt sans état terminal et un statut `'downloading'` reste bloqué À JAMAIS jusqu'au redémarrage. Correctif : bloc statut+start sous verrou, corps entièrement sous try, auto-guérison de l'orphelin au prochain appel (statut actif + thread mort → réinitialisé). Pièges annexes trouvés en creusant : `socketserver` ignore les threads daemon dans son registre de fermeture (un shutdown « propre » ne joint jamais les handlers en vol) ; une barrière de teardown qui POLL un statut au lieu de JOINDRE le thread a des trous ; un faux thread de test doit porter toute l'interface réelle (`is_alive` ET `join`, mort après join) — 3e occurrence du même stub trop pauvre en une journée.

## I. Vocabulaire imposé (identifiants de code, pas seulement texte visible)

`tests/test_vocabulaire_portable.py` interdit « activation »/« activateur » dans le texte VISIBLE français — mais un `onclick="exportActivationAdif()"` est lu comme du texte au même titre qu'un libellé. Avant de nommer une NOUVELLE fonction/variable JS touchant POTA/SOTA/IOTA/WWFF, éviter le mot dans le nom plutôt que d'élargir la liste blanche du test.
