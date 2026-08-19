---
name: chantier-differes-majeur-et-lancement-triage-mineur-2026-08-12
description: "PR #42 (correctifs différés du 2e audit, lot majeur clos) + lancement du triage sémantique des 162 constats mineur"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-12T07:58:35.170Z
---

Suite directe de [[chantier-triage-et-correctifs-majeur-2026-08-12]] (PR #41).
F4GLD a explicitement autorisé de continuer : « Il reste ~75-80 constats
"majeur" et les 162 "mineur" go » — la synthèse de triage de PR #41 avait déjà
dédupliqué la TOTALITÉ des 132 constats majeur bruts en groupes fix_now/
defer ; ce qui restait après #41 n'était que les groupes fix_now non encore
traités faute de temps (perf réseau/verrous), pas un nouveau triage.

## PR #42 (mergée, squash, branche supprimée) — le bucket "majeur" est clos

Motif jeton de génération (8 sites) appliqué à `logx_scope.html` (tick),
`logx_carte.html` (checkVoacapForSpot), `logx_chasse.html` (pollStrat),
`logx_filtre_spots.js` (refreshBandMap, 2 gardes), `logx_propagation.html`
(loadSat + rendreRegle via `bande` capturée en `bandeDemandee` — la vraie
race ici n'était pas 2 fetches concurrents mais une fermeture périmée sur
la variable module-level `bande`), `logx_departements.html` (loadProgress/
loadWorldProgress, UN SEUL jeton partagé car les deux écrivent le même DOM),
`logx_busted_call.js` (verifierIndicatifApres).

`logx_wwa.get_roster()` rendu non bloquant, même remède que
`get_weather_cached()`/`get_tropo_cached()` (cache lu direct + thread de
fond par edition_code, verrou par clé). Appelé depuis le moteur de scoring
(`is_wwa_station`) via `/log/check` (chaque frappe), `/data/refresh`, le
coach — aucun n'était protégé par `_SCORE_EXECUTOR` (qui ne borne que
`add_qso_to_log`).

**Décision assumée de NE PAS appliquer le même motif à amp.py/tci.py/
flrig.py** : leurs connexions socket sont synchrones mais déjà bornées
(2-3s), sur des endpoints de test/poll DÉDIÉS déjà isolés par thread HTTP
(pas partagés avec le moteur de scoring comme WWA). Appliquer un cache+
refresh-async y afficherait une fréquence/PTT PÉRIMÉE pendant un contrôle
live d'ampli/radio — pire que l'attente bornée actuelle. Vérifié aussi que
`/agent/act` et `/log/audit` (proxy IA) sont déjà en tâche de fond
(`threading.Thread` + polling d'état côté client) — rien à faire. Le proxy
IA streaming (`/proxy/ai`) reste synchrone : structurellement un flux SSE
(`for raw in resp:` + callback `on_delta`), incompatible avec le motif
"un appel borné = un résultat" des autres correctifs ; nécessiterait une
restructuration thread+queue, non entreprise (documenté, pas oublié).

Pipeline complet : pytest 9010 verts, ruff propre, vérification navigateur
réelle (serveur isolé port 8092, PAS le port 8080 live) sur les 8 fichiers
touchés — onglet VHF/EME de PROPAG confirmé avec satellites/EME/météores
réellement rendus (donc `loadSat`/`loadEme` fonctionnent après le jeton de
génération), ZONES TRAVAILLÉES confirmé avec la progression département
réelle. PR mergée, `local/live-8080-combined` resynchronisée, pytest
re-vérifié sur la branche live, serveur 8080 redémarré, worktree +
branche différée supprimés.

## Piège récurrent (déjà documenté, retombé dedans puis corrigé)

Première tentative de lancer le serveur de test isolé (port 8092) a combiné
`run_in_background: true` ET un `&` final dans la commande bash
(`... > log 2>&1 &`) — exactement [[piege-double-arriere-plan-detache-log-incomplet]].
Le process s'est détaché, notification prématurée avec exit code 7.
Corrigé en relançant SANS le `&` final. Deuxième piège distinct rencontré
ensuite : `logx_serveur.py` n'a pas de fonction `main()` (tout est sous
`if __name__=='__main__':`), donc un script `import logx_serveur;
logx_serveur.main()` échoue avec `AttributeError`. Pour lancer le serveur
sur un port différent de 8080 (constante `PORT` codée en dur dans
`logx_utils.py`, aucune variable d'env), la méthode qui marche : patcher
`logx_utils.PORT` puis `runpy.run_path('logx_serveur.py', run_name='__main__')`
(PAS `runpy.run_module`, qui réimporterait logx_utils proprement et
perdrait le patch).

## Triage sémantique des 162 constats "mineur" — LANCÉ (Workflow, pas encore synthétisé)

Extraction depuis `audit_r2_summary.tsv` (colonnes severity/file/line/summary,
UTF-8 réel malgré un artefact d'affichage terminal qui suggérait le
contraire — toujours vérifier les octets bruts avant de suspecter un bug
d'encodage, cf script Python `data[:400]` qui a confirmé `\xc3\xa9` = 'é').
162 lignes `severity=mineur` extraites en JSON, embarquées EN LITTÉRAL dans
le script Workflow (`const FINDINGS = [...]`) — toujours PAS via le
paramètre `args` du tool Workflow, qui ne délivre pas le payload au script
dans cet environnement (bug non résolu, contournement déjà utilisé pour
PR #41, reconduit ici).

Méthodologie : 11 lots de 15 constats, agents en parallèle qui relisent le
VRAI code (Read + Grep depot-entier pour tout "jamais appelé/lu", pas
confiance au résumé tronqué), verdict par constat (`still_valid`,
`worth_fixing`, `confidence`, `category`, `root_cause_key`,
`fix_description`, `risk_notes`) — puis 1 agent de synthèse qui déduplique
en groupes `fix_now`/`defer_needs_discussion`/`reject_not_worth_it`.
Consigne explicite à la synthèse : généreux sur `fix_now` pour du code mort
vérifié SANS risque de régression (suppression pure), prudent sur les
refactors de duplication multi-fichiers (`defer` sauf triviaux).

**Piège potentiel identifié AVANT lancement, pas encore vérifié empiriquement** :
le script pointait initialement vers le worktree `wt-audit-p2-differes`
(chemin `REPO` codé en dur) — supprimé entre l'écriture du script et son
lancement (nettoyage post-merge PR #42). Corrigé en repointant `REPO` vers
le worktree principal (`Programme pour contest\concours`, à jour, synced)
AVANT d'invoquer `Workflow({scriptPath})`. Réflexe pour la suite : si un
script Workflow référence un chemin de worktree éphémère, vérifier qu'il
existe encore juste avant de (re)lancer, pas seulement au moment de
l'écrire.

Suite prévue une fois la synthèse revenue (tâches #14 fin / #15) : nouveau
worktree depuis `origin/main`, appliquer les groupes `fix_now` avec la même
rigueur que PR #41/#42 (relire le code réel avant de faire confiance à
`fix_description`, vérifier empiriquement les suggestions douteuses comme
le cas `is_french` de PR #41), puis même pipeline tests+ruff+navigateur+PR+
merge+sync.
