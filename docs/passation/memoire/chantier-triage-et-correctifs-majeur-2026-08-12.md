---
name: chantier-triage-et-correctifs-majeur-2026-08-12
description: "Triage sémantique (workflow 10 agents) des 132 constats 'majeur' du 2e passage d'audit + correction de ~55 causes racines (PR #41, 12/08)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-12T06:46:00.241Z
---

Suite à "continu" (F4GLD, nuit du 11-12/08/2026), reprise du travail
d'audit après la publication de v0.9-beta27 (voir
[[chantier-fix-release-cassee-et-repli-version-bugreport-2026-08-12]]).
Les 132 constats **majeur** du 2e passage d'audit (voir
[[chantier-audit-passe2-2026-08-12]]) étaient documentés comme "à ne
pas corriger en bloc sans triage" — ce chantier fait exactement ce
triage puis applique les correctifs sûrs.

## Méthode : triage sémantique AVANT correction

Plutôt que de corriger les 132 constats bruts un par un (risque : les
résumés sont tronqués, certains sont déjà résolus par PR #37, plusieurs
sont dupliqués sous des lignes différentes), un Workflow dédié (9 agents
en parallèle, 1 lot de ~15 constats chacun, chaque agent LIT le code
réel autour de la ligne indiquée plutôt que de se fier au résumé) a
d'abord produit un verdict individuel par constat (still_valid,
root_cause_key, confidence, fix_description), puis un agent de synthèse
a déduplique le tout en **58 groupes de cause racine distincte**,
chacun taggé `fix_now` ou `defer_needs_discussion`.

**Résultat du triage** : sur 132 constats bruts, plusieurs dizaines
étaient déjà résolus (effet de bord de PR #37) ou des doublons d'une
même cause racine — confirme la leçon du 1er triage (dédup fichier:ligne
trop fragile à grande échelle).

**Piège trouvé pendant l'application (pas pendant le triage)** : le
triage a proposé pour `is_french` (logx_scoring.py) de comparer
`ctx['dx_country'] in ('France', 'Corsica')` — mais vérifié empiriquement
(`dxcc.country_key()` renvoie le PRÉFIXE canonique 'F'/'TK', jamais le
nom complet), la suggestion du triage était fausse sur ce point précis.
Corrigé en `('F', 'TK')` après vérification directe en Python. **Réflexe
confirmé une fois de plus : ne jamais appliquer aveuglément le
fix_description d'un triage, toujours revérifier sur le code/les
données réelles avant d'écrire le correctif.**

## Corrections notables (au-delà du résumé du commit/PR)

- **Biais locator 4 caractères** (`extract_dx_locator`, logx_scoring.py) :
  le correctif retire le complément 'MM' AVANT le calcul de distance
  (qui réintroduisait le biais NE de ~3,8 km que le correctif M8 avait
  déjà corrigé dans `locator_to_latlon()`), mais le garde pour la VALEUR
  RETOURNÉE (`pad()` appliqué seulement au retour) — un test existant
  (`test_scoring.py::test_...`) attendait explicitement `'JN23MM'` comme
  valeur de retour ; la distinction fetch-sans-padding / retour-avec-
  padding a permis de corriger le bug réel sans casser ce test.
- **`calcPoints()`/`evalPointsFromDef()` (logx_logbook.js)** : ajout d'un
  5e paramètre optionnel `myLoc` (défaut : global `myLocator`) pour que
  `updateStats()` recalcule chaque QSO avec `q.my_locator` (position au
  moment du QSO) plutôt que la position actuelle — seulement 2 sites
  d'appel dans tout le fichier, changement à faible risque malgré son
  importance.
- **SSRF sur les routes de test d'équipement** (`/rig/connect_test`,
  `/amp/test`, `/pgxl/test`) : nouveau helper `_is_loopback_or_private_host()`
  qui fait l'INVERSE de `logx_rules_ai._is_safe_host()` (n'accepte QUE le
  privé/loopback, puisque l'équipement radio est toujours local/LAN dans
  l'usage réel — jamais un hôte Internet).
- **Session Wait-and-Pounce** (logx_pounce.py) : verrouillage complet de
  la classe avec `threading.RLock()` (pas un `Lock` simple — `decider()`
  appelle `self.desarmer()`, `etat()` appelle `self.restant_s()` : un
  Lock simple aurait fait deadlocker).
- **`/data/tropo`** : motif cache-puis-refresh-async copié tel quel de
  `logx_weather.get_weather_cached()` — `get_tropo_cached()` ajouté dans
  `logx_tropo.py`.

## Piège CI trouvé par la suite pytest (pas par relecture)

Le nouveau garde anti-SSRF sur `/pgxl/test` a cassé
`test_pgxl_test_corps_de_requete_malforme_ne_plante_pas` : le test
attendait que `test_connection` soit appelée avec `host=None` (JSON
malformé → payload={} → host vide) — mais le garde rejette désormais
AVANT d'atteindre `test_connection`. Corrigé en mettant à jour
l'assertion du test (`captured == {}`), pas en affaiblissant le garde —
comportement objectivement meilleur (rejet précoce, pas de connexion
tentée avec un hôte vide).

## Volontairement NON traité (décision documentée dans le commit/PR)

- Comptage réel états/sections ARRL (`scoreboard.py` geo_mode 'other') —
  nécessite un parsing du champ d'échange non vérifiable avec la même
  confiance qu'un simple ajout de garde.
- `do_DELETE`/POST `/log/delete` dupliqués — refactor pur, aucun bug.
- Motif "réponse async tardive écrase un état plus récent" sur 8 fichiers
  distincts (scope.html, carte.html, chasse.html, filtre_spots.js,
  propagation.html ×2, departements.html, busted_call.js) — trop
  volumineux pour cette passe, nécessite un jeton de génération par site.
- WWA `get_roster()`/TcpAmpPort/WebSocketClient(TCI)/flrig/proxy IA —
  appels réseau/socket synchrones restants (motif déjà appliqué
  ailleurs mais dispersé sur plusieurs fichiers).

## Pipeline

Workflow de triage (10 agents, ~1,4M tokens) → 32 fichiers corrigés
(PR [#41](https://github.com/sauveteur71/radioaamateur-program-Contest/pull/41))
→ suite complète 9009 passed (1 échec trouvé et corrigé : le test
pgxl ci-dessus) → ruff (1 variable inutilisée trouvée et corrigée) →
vérification navigateur réelle (QSO loggué avec succès sur Challenge
THF, 501 pts calculés, carte affiche le QSO via `/log/list`, WebSDR/
PROPAG/mobile chargent sans erreur console) → merge → sync branche live
→ pytest complet sur live (9010 passed) → redémarrage serveur 8080.

## Reste à faire

~75-80 constats "majeur" restants (le triage a dédupliqué 132 constats
en 58 groupes ; ~50 traités dans cette PR, le reste explicitement
différé ci-dessus) + les 162 constats "mineur" du 2e passage, jamais
triés. À traiter dans un futur chantier, avec le même triage sémantique
en amont plutôt qu'une correction fichier:ligne brute.
