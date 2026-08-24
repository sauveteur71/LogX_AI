# IA-2 — Enrichissement déterministe du log — PROPOSITION (à valider par F4GLD)

> ⚠️ **PROPOSITION, PAS UN CHANTIER LANCÉ.** Rédigée en travail autonome nocturne
> (24/08) après achèvement de B (#244) et IA-1 (#245), en réponse à « soit force
> de proposition sur les prochaines évolutions ». **Aucune ligne de code produit.**
> C'est la sortie de conception (brainstorming) de l'étape « enrichissement » de la
> roadmap copilote IA (voir mémoire `projet-ia-copilote-roadmap.md`, ordre :
> validation → **enrichissement** → FT8/UDP → diplômes → …). À approuver / cadrer
> avant tout plan d'implémentation.

## 1. Constat

L'export ADIF d'un QSO ne porte que ce que l'opérateur a saisi. Or beaucoup de
champs utiles aux **diplômes** (DXCC, WAZ, WAC…) et à **LoTW** sont **dérivables
sans rien demander** :
- depuis l'**indicatif** seul, via `logx_dxcc.lookup(call)` déjà présent, qui rend
  `{country, continent, cq_zone, itu_zone, prefix}` → **COUNTRY, CONT, CQZ, ITUZ**
  (+ le n° d'entité DXCC via `logx_dxcc.dxcc_entity_key`) ;
- depuis le **locator** du correspondant, via `logx_utils.locator_to_latlon` +
  `haversine` déjà présents → **DISTANCE**, azimut d'antenne **ANT_AZ** ;
- depuis la **config station** → **MY_DXCC, MY_CQZ, MY_ITUZ, MY_CNTY…**

Aujourd'hui ces champs restent vides sauf saisie manuelle. Résultat : logs
incomplets pour les diplômes, travail manuel évitable. **B** a rendu l'export
COMPLET pour les champs SAISIS ; **IA-2** remplit ceux qui sont CALCULABLES.

## 2. Objectif et non-objectifs

**Objectif.** Un module PUR `logx_enrichissement.py` qui, pour un QSO donné,
**dérive** les champs calculables et propose de remplir **UNIQUEMENT les cases
vides**, à partir de sources DÉTERMINISTES déjà dans le dépôt (cty.dat, locator,
config). Transparent, toujours éditable, jamais imposé.

**Non-objectifs (garde-fous, cohérents avec la roadmap « IA discrète »).**
- **Jamais écraser une saisie de l'opérateur.** On ne remplit que le vide. Sa
  frappe fait toujours foi.
- **Déterministe d'abord, réseau en option séparée.** Le cœur d'IA-2 n'appelle
  AUCUN service externe. L'enrichissement RÉSEAU (nom/QTH via la cascade
  `logx_callbook.lookup` QRZ→HamQTH→HamDB, déjà existante) reste un chemin
  DISTINCT, explicitement déclenché, non couvert par ce cœur (zone blanche : le
  déterministe doit marcher hors réseau).
- **Jamais bloquant, jamais « décideur ».** IA-2 calcule, il ne choisit rien à la
  place de l'opérateur et ne touche pas à l'émission.
- **Aucune valeur de domaine inventée** : entités/zones viennent de cty.dat
  (`logx_dxcc`), distances de `haversine` — jamais d'une table nouvelle codée ici.

## 3. Architecture proposée

```
logx_enrichissement.py   (NOUVEAU, pur)
  enrichir(qso, cfg) -> {champ_interne: valeur}   # SEULEMENT les champs vides
        │ réutilise
        ├─ logx_dxcc.lookup / dxcc_entity_key   (COUNTRY/CONT/CQZ/ITUZ/DXCC)
        ├─ logx_utils.locator_to_latlon + haversine  (DISTANCE, ANT_AZ)
        └─ cfg (station)                          (MY_DXCC/MY_CQZ/MY_ITUZ…)
```

Fonction PURE `enrichir(qso, cfg) -> dict` : ne modifie rien, renvoie les champs
dérivés qui MANQUENT. L'appelant décide quoi en faire.

## 4. Décisions à trancher par F4GLD (le cœur de la proposition)

1. **Où appliquer l'enrichissement ?** Trois options :
   - **(A) À l'export seulement** (dans `build_adif`, non destructif) : le log
     stocké reste tel quel, le fichier remis est complet. Le plus sûr, zéro risque
     de corrompre le log. *Recommandation par défaut.*
   - **(B) À l'enregistrement du QSO** (persisté) : les champs sont visibles/
     éditables dans le carnet tout de suite, mais on écrit dans le log.
   - **(C) Les deux** : proposer à la saisie (éditable) ET compléter à l'export.
   Recommandation : commencer par **(A)**, ajouter la proposition éditable à la
   saisie (C) dans un 2e temps si F4GLD valide l'affichage.

2. **Quels champs activer d'emblée ?** Proposition : COUNTRY, CONT, CQZ, ITUZ,
   DXCC (indicatif) + DISTANCE, ANT_AZ (locator) + MY_* (config). À élaguer selon
   ce que F4GLD juge utile.

3. **Politique de non-écrasement** : ne remplir que le vide (recommandé, sûr).
   Faut-il un mode « corriger les incohérences » (ex. CQZ saisi ≠ CQZ calculé) ?
   → **Non** en IA-2 : c'est le rôle d'**IA-1** (qui pourrait justement gagner un
   contrôle « CQZ/ITUZ incohérent avec l'indicatif », complément naturel).

4. **Indicatifs portables** (`F/DL1ABC`, `DL1ABC/P`) : `logx_dxcc.lookup` gère déjà
   le préfixe de lieu. Confirmer que l'entité retenue est celle du LIEU (F/… → France)
   et non de l'indicatif de base — comportement actuel de `logx_dxcc` à vérifier au
   plan.

## 5. Découpage pressenti (TDD, après approbation)

1. `logx_enrichissement.enrichir(qso, cfg)` pur : dérive COUNTRY/CONT/CQZ/ITUZ/DXCC
   depuis l'indicatif (via logx_dxcc), ne renvoie que les champs vides. Tests :
   indicatif connu → champs ; case déjà remplie → intacte ; indicatif inconnu → rien.
2. Ajout DISTANCE/ANT_AZ depuis les locators (correspondant + station).
3. Champs MY_* depuis la config.
4. Intégration à l'export (option A) : `build_adif` complète les vides via `enrichir`
   avant émission (sans toucher le log stocké). Test : QSO sans CQZ → l'ADIF porte
   le CQZ dérivé ; QSO avec CQZ saisi → inchangé.
5. (Si option C validée) proposition éditable à la saisie — chantier UI distinct,
   vérifié navigateur jour+nuit.

## 6. Pourquoi c'est le bon prochain pas

- **Déterministe** : conforme à l'ordre roadmap (validation puis enrichissement,
  tous deux déterministes avant les briques réseau/IA).
- **Réutilise l'existant** (logx_dxcc, locator, callbook) au lieu de le refaire.
- **Complète la trilogie ADIF** : A (saisie) → B (export complet des champs saisis)
  → IA-2 (remplit les champs calculables) → logs prêts pour les diplômes/LoTW.
- **Risque faible** : pur, non destructif (option A), jamais d'écrasement, hors ligne.

---

**Prochaine action attendue de F4GLD** : approuver / cadrer (surtout §4.1 où
appliquer, et §4.2 quels champs). Sur accord → `writing-plans` puis implémentation
TDD. Sans accord → cette proposition reste sans effet, aucun code n'a été écrit.
