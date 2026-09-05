# ✅ FAIT — LIVRÉ DANS MAIN (03/09/2026)

> **Ce backlog est PÉRIMÉ.** La carte de sortie XOTA a été construite et
> fusionnée dans `main` le 01/09/2026 (commits `e17039d` logique pure,
> `a4b40c5` rendu canvas + UI + export PNG + bouton, `a8bfd93` correctif
> comptage pays). Fichier `concours/logx_xota_carte.js`, endpoint
> `/dxcc/positions` (géoloc par indicatif via `cty.dat`/`logx_dxcc.py`),
> bouton **« CARTE DE SORTIE »** dans le LOGBOOK (`#carteSortieBtn`), export
> PNG hors-ligne. Tests : `tests/test_xota_carte_js.py` (9 verts). Le
> « travail neuf » décrit ci-dessous existait déjà et était testé — vérifié
> le 03/09. Conservé pour mémoire des décisions, plus un chantier à ouvrir.

---

# BACKLOG — Carte de sortie XOTA (à concevoir APRÈS le chantier EME)

Demandé par F4GLD le 2026-09-01, PENDANT l'exécution EME. Décision de séquencement :
**finir EME (Tranche 1) d'abord**, puis ouvrir ce chantier proprement (brainstorming → spec → plan).
Ce fichier n'est PAS commité (note de travail durable, survit au changement de branche).

## Besoin
Après une sortie **portable/expédition** XOTA (SOTA, POTA, WWFF, DFCF, WWBOTA, GMA, ARLHS, WCA…),
l'opérateur veut un **résultat imagé** : carte mondiale avec les **rayons** de son QTH vers chaque
station contactée (cf. capture Facebook « QSO map depuis un ADIF »). Vaut pour **TOUTE** activité XOTA.

## Ce qui existe déjà (à réutiliser)
- `concours/logx_qso_map.js` : carte Leaflet à rayons DÉJÀ construite (polylignes QTH→station,
  couleur par bande, marqueurs cliquables). Bouton 🗺️ CARTE du LOGBOOK, `toggleMapView()`.
- Import ADIF (`logx_import_adif.js`, `logx_import.py`) et Leaflet vendored (`vendor/leaflet/`).

## Le TROU bloquant (cœur du travail neuf)
`refreshMapLayers()` ne trace un QSO que s'il a un **locator Maidenhead ≥ 6** (`q.locator`).
Or en SOTA/POTA la plupart des chasseurs n'envoient PAS de grid → carte quasi vide.
La capture géolocalise par **indicatif** (préfixe → DXCC/centroïde pays), pas par locator.
**→ Ajouter une géolocalisation par indicatif (préfixe DXCC → position approx.) en repli
quand le locator manque.** Vérifier si une table préfixe→pays/lat-lon existe déjà côté projet
(cty.dat ? logx_callbook ? logx_awards DXCC ?) avant d'en créer une (ne pas réinventer, sourcer).

## Décisions ACTÉES (F4GLD, 2026-09-01)
1. **Source = carnet LogX filtré à la sortie** (réf. XOTA + date), PAS un ADIF externe pour la v1.
   Le carnet unique reste la source (cohérent règle « carnet unique, activité = vue »).
   (L'entrée par ADIF externe = extension possible plus tard, écartée pour la v1.)
2. **Géoloc par indicatif** si le QSO n'a pas de locator ≥ 6.
3. **Rendu = carte interactive + bouton d'export IMAGE partageable** (PNG).

## À trancher au design (plus tard)
- D'où vient le filtre « une sortie » : réf. XOTA (sig/sig_info déjà loggés en mode chasseur/portable)
  + plage de dates ? Réutiliser le filtrage par portée existant.
- Table préfixe→lat/lon : source citable (cty.dat de Jim Reisert AD1C ? déjà présent ?), jamais devinée.
- Arcs de grand cercle vs traits droits (cosmétique, la capture a des arcs).
- Export PNG : `leaflet-image` / capture canvas — vérifier faisabilité hors-ligne (CSP artefacts, vendored).
- Vocabulaire : « portable »/« expédition » en texte visible, jamais « activation/activateur ».

## Prochaine étape
Après EME : invoquer superpowers:brainstorming sur ce besoin (classer bounded vs architectural —
probablement **bounded/medium** vu que le moteur carte existe), puis spec → plan.
