---
name: suite-tests-flakes-sous-charge
description: "Les flakes ~1 par passe etaient un VRAI defaut produit (fermer une socket au tampon non vide -> RST qui detruit la reponse) — RESOLU, methode a garder"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-27T06:31:49.666Z
---

**RÉSOLU le 27/07/2026** (commit 8fe6dca). Deux passes completes de 1624 tests sans aucun
echec, la ou on observait ~1 echec aleatoire par passe sur un test DIFFERENT a chaque fois.

**La cause n'etait pas un defaut de test : c'etait un vrai defaut produit.** Les chemins de
refus HTTP (429 anti-bruteforce sur /auth/login, 403 sans jeton dans _require_auth) ne
lisaient pas le corps puis fermaient la connexion. Or **fermer une socket dont le tampon de
RECEPTION contient encore des octets fait envoyer un RST au lieu d'un FIN, et le RST
DETRUIT la reponse deja emise**. L'utilisateur recevait une erreur reseau au lieu du
message qui lui dit quoi faire. Correctif : vider le corps (borne : 4 Ko / 64 Ko) puis
repondre — l'invariant « les octets ne parasitent pas la requete suivante » est preserve
sans le RST.

Cause aggravante : 21 fichiers de test montaient un `http.server.HTTPServer` MONO-THREAD
contre un handler passe en HTTP/1.1 persistant, et 17 ne fermaient jamais la socket
d'ecoute. La production utilise `ThreadingHTTPServer` — ces serveurs de test n'etaient
meme pas representatifs.

**Why:** un faux rouge par passe apprend a ne plus regarder la CI. Et ici, derriere le
« flake », il y avait un bug que des mois de CI verte n'auraient jamais montre.

**How to apply (la methode, qui a marche 3 fois) :**
1. Ne jamais conclure a une regression sur un echec unique en suite complete : relancer le
   fichier seul 5-10 fois. `0 echec isole` = flake.
2. **Reproduire SOUS CHARGE** : lancer la suite complete en tache de fond, puis marteler le
   test seul 10-12 fois. C'est ce qui a fait apparaitre le vrai message
   (`ConnectionResetError WinError 10054`) au lieu d'un simple echec d'assertion.
3. Chercher le motif : etat module-global + thread de fond + fixture qui remplace l'etat
   sans attendre les threads (cf. `_download` de logx_update, commit 0959e93).
4. Ne PAS « corriger » un flake en affaiblissant une assertion. Sur le rate-limiter, un
   reessai reseau aurait pu compter deux fois un echec de connexion.
5. Quand un test existant tombe apres le correctif, verifier s'il testait le MECANISME ou
   l'INVARIANT. Deux tests exigeaient « la connexion doit etre fermee » (le moyen) et l'un
   acceptait meme le RST comme « fermeture attendue », donc tolerait que la reponse soit
   PERDUE. Reecrits sur l'invariant reel.

Voir [[piege-faux-dom-stub-et-passes-paires]] pour l'autre famille de pieges de tests.


## 2ᵉ épisode (31/07/2026) — encore un VRAI bug produit : le verrou fantôme

Le flake est revenu (~50 % par passe, jamais le même test, CI ubuntu toujours
verte). Diagnostic par workflow : 4 autopsies parallèles puis chaque hypothèse
attaquée par un sceptique — **17 hypothèses, 12 réfutées**. Corrigé par
`f54dbb8` / fusion `05ef61a`.

- **Le bug** : `start_download*` pose `status='downloading'` puis refuse tout
  nouvel appel. Les premières lignes de `_do_download_via_network` (makedirs,
  `_ASSET_SUFFIX_BY_PLATFORM[...]`) et le scan pair-à-pair étaient **hors de
  tout try**, et `Thread.start()` peut lever sous famine : le thread mourait
  sans état terminal, le statut restait 'downloading' **à jamais** — mise à
  jour morte jusqu'au redémarrage, sans message. Le thread traînard écrivait
  aussi `'error'` dans l'état tout neuf du test suivant → le flake.
- **Correctif** : `_demarrer_telechargement()` — statut + start d'un bloc sous
  _lock, start sous try, **auto-guérison de l'orphelin** (downloading + thread
  mort → réinitialisé). Référence du thread HORS de `_download` (sérialisé
  JSON). Corps enveloppé de bout en bout.
- **Pièges neufs à retenir** :
  - `socketserver._Threads.append` (Python 3.13.7) **ignore les threads
    daemon** → `server_close()` ne joint JAMAIS les handlers en vol. Un
    shutdown « propre » (shutdown+server_close+join du serve_forever) ne
    garantit rien sur les handlers.
  - Une barrière de teardown qui **poll un statut** au lieu de joindre le
    thread a des trous (sortie sur 'idle', abandon silencieux à 30 s). Joindre
    LE THREAD, et **échouer bruyamment**.
  - Une sonde de test qui utilise un état interne comme marqueur («
    downloading sans thread = déjà en cours ») casse quand cet état devient
    un cas géré. Adapter la sonde, pas affaiblir le test.
  - Un faux thread doit porter TOUTE l'interface (is_alive ET join, mort après
    join) — 3ᵉ occurrence du stub trop pauvre en une journée.
- **Réfutées par la mesure** (ne pas re-suspecter sans mesure nouvelle) :
  épuisement des ports éphémères (pic mesuré **105** TIME_WAIT / 16 384
  dispo pendant une passe complète) ; pytest-randomly (pas installé, vérifié
  sur les 3 interpréteurs + CI) ; contamination cache TTL awards pour CE test
  (il se protège déjà).
- **Verdict** : 10 tests reproduisant chaque mécanisme + **3 passes complètes
  consécutives vertes** (le flake frappait 1/2). `pytest.ini` porte désormais
  `-ra` pour que le prochain flake livre son traceback.
