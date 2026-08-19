---
name: piege-time-monotonic-nest-pas-epoch
description: monkeypatcher un _last_try comparé à time.monotonic() avec 0.0 passe en local mais peut échouer en CI (conteneur frais = monotonic() proche de zéro)
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-02T16:32:11.494Z
---

Un correctif d'audit sur `logx_departments.py` a ajouté un disjoncteur réseau :
`_dept_polys_last_try = time.monotonic()` posé à chaque échec, avec un délai de
grâce de 300s avant retentative (`if now - _dept_polys_last_try < 300: return []`).

En écrivant le test qui mocke ce chargement (`tests/test_departments.py`,
suivant le patron déjà établi par `tests/test_worldmap.py`), j'ai posé
`monkeypatch.setattr(dep, '_dept_polys_last_try', 0.0)` en pensant forcer
« il y a longtemps, jamais de court-circuit ». **Faux** : `time.monotonic()`
n'a PAS l'epoch Unix pour origine — son point de départ est arbitraire selon
la plateforme, souvent proche de zéro sur un conteneur CI qui vient de
démarrer. Résultat : `now - 0.0` valait ~12-45s en CI (largement < 300),
le court-circuit tirait quand même, et le mock de `load_france_geojson()`
n'était JAMAIS appelé — 3 tests ont échoué en boucle sur GitHub Actions
alors qu'ils passaient à 100% en local (ma machine de dev a des heures
d'uptime, donc `time.monotonic()` y est toujours un grand nombre).

**2 runs CI consécutifs identiques** avant de comprendre — le 1er réflexe
« c'est sûrement un flake réseau transitoire » (`gh run rerun --failed`)
était le mauvais diagnostic ; le vrai test a été de mocker `time.monotonic()`
en local à une petite valeur (`unittest.mock.patch('time.monotonic',
return_value=12.5)`) pour reproduire le bug HORS CI.

**Correctif** : poser une valeur **négative** (`-1e6`) plutôt que `0.0` —
garantit `now - last_try > 300` quelle que soit l'origine de l'horloge
monotonic de la plateforme.

**Comment appliquer** : dès qu'un test monkeypatche un état comparé à
`time.monotonic()` (disjoncteurs, caches à expiration, rate-limiters...),
ne JAMAIS poser `0.0` pour dire « il y a longtemps » — poser une valeur
négative suffisamment grande, ou mocker `time.monotonic()` lui-même. Le
même piège existe pour tout `_last_*`/`_cache_ts` comparé à `time.monotonic()`
ailleurs dans le code (ex. `logx_callbook`, `logx_rbn`, tout disjoncteur du
pattern audit "DNS non borné"). Voir aussi [[chantier-audit-securite-94-correctifs-2026-08-02]].

🚨 **CONFIRMÉ EN PRODUCTION, pas seulement dans mon test** : la revue
adversariale post-fusion (même jour) a trouvé EXACTEMENT le même bug dans
le code réel, pas seulement dans mon mock : `logx_departments.py` initialise
`_dept_polys_last_try = 0.0` comme état de départ (pas dans un test cette
fois). Sous Windows, `time.monotonic()` = temps depuis le démarrage système
(`GetTickCount64`) — si LogX AI est lancé dans les 5 minutes suivant un
redémarrage du PC (scénario courant un matin de concours), le repli
géographique département reste silencieusement désactivé jusqu'à ce que
l'uptime dépasse 300s. Correctif à appliquer : remplacer le sentinel `0.0`
par une valeur qui ne peut jamais être confondue avec un vrai `time.monotonic()`
récent (ex. `float('-inf')` ou `-1e6`), pas seulement dans les tests mais
PARTOUT où ce pattern de disjoncteur est utilisé. Voir
[[revue-adversariale-post-fusion-audit-2026-08-02]].
