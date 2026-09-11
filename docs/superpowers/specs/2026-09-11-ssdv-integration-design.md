# SSDV (Slow Scan Digital Video) — spec de cadrage, à valider avant code

**Date :** 2026-09-11. **Statut : à relire par F4GLD avant tout code.** Écrit
suite à une demande d'intégration d'une note de recherche (visiblement produite
par un autre assistant IA, pas F4GLD lui-même) sur SSDV/HamStation. Doctrine du
dépôt appliquée : **rien de cette note n'a été pris pour argent comptant** —
chaque affirmation vérifiable (dépôt existe ? licence ? actif ?) a été vérifiée
via `gh api` avant d'écrire une ligne de ce document. Les points non vérifiés
restent marqués `HYPOTHÈSE À VÉRIFIER`.

## 1. Ce qui a été vérifié (11/09/2026, `gh api repos/<owner>/<repo>`)

| Dépôt | Existe | Licence détectée par GitHub | Actif |
|---|---|---|---|
| `fsphil/ssdv` | ✅ | **GPL-3.0** | ⚠️ **archivé** (mais mis à jour juin 2026 avant archivage — code stable, le format SSDV ne change pas) |
| `DL7AD/aprs_ssdv_decoder` | ✅ | GPL-2.0 | actif |
| `DL7AD/ssdv` | ✅ | GPL-2.0 | actif |
| `BY2HIT/arcss_panel_pc` | ✅ | **aucune licence détectée** | actif |
| `BY2HIT/arcssd-go` | ✅ | **aucune licence détectée** | actif |
| `BY2HIT/pcsi` | ✅ | **aucune licence détectée** | actif |
| `TomasTT7/LoRa_SSDV` | ✅ | **aucune licence détectée** | actif |

**Correction à la note reçue :** elle présentait la licence des dépôts
`BY2HIT/*` et `TomasTT7/*` comme « à vérifier » (caveat léger). En réalité
**GitHub ne détecte AUCUN fichier de licence** sur ces 4 dépôts — ce n'est pas
une zone grise à clarifier, c'est un **blocage dur** : sans licence explicite,
le code est « tous droits réservés » par défaut dans la plupart des
juridictions, et ne peut pas être réutilisé (même inspiré) sans autorisation
écrite de l'auteur. **Ces 4 dépôts sont donc HORS PÉRIMÈTRE tant qu'aucune
licence n'apparaît** (ou qu'un accord explicite n'est obtenu par F4GLD lui-même
— ni moi ni un agent ne peut négocier ça).

Non vérifié à ce stade (`HYPOTHÈSE À VÉRIFIER`) : le contenu technique détaillé
de la note (offsets exacts du format de paquet, comportement précis du FEC
Reed-Solomon, fréquences ERMINAZ, contenu du guide UKHAS) — cohérent avec ce
qui est publiquement documenté sur SSDV, mais pas relu ligne à ligne contre le
code source de `fsphil/ssdv` ni contre le guide UKHAS lui-même.

## 2. Stratégie de licence retenue

**Binaire externe `ssdv` en sous-processus, jamais de code copié/lié.** C'est
la conclusion à laquelle la note elle-même arrivait, et c'est déjà le patron
établi dans ce dépôt pour un outil natif GPL/tiers : **VOACAP**
(`concours/logx_voacap.py`, `voacapl.exe` en sous-processus + endpoint HTTP,
PR #16 du 10/08/2026). Appeler un binaire GPL non modifié en sous-processus
séparé (« mere aggregation », pas de liaison statique/dynamique) n'impose pas
la GPL au reste de LogX AI — c'est le même raisonnement déjà appliqué et non
contesté pour VOACAP.

- `fsphil/ssdv` (GPL-3.0, archivé mais stable) : seul candidat retenu comme
  binaire externe pour l'encodage/décodage SSDV bas niveau.
- Un **parseur/assembleur Python natif** est réécrit DANS LogX AI à partir du
  format PUBLIC documenté (guide UKHAS + RFC informel du format), pas copié
  depuis un dépôt GPL — permet l'inspection de paquets, les statistiques, la
  fusion multi-stations, sans dépendre de la licence d'un tiers pour cette
  partie-là.
- `DL7AD/*` (GPL-2.0) : lecture pour COMPRENDRE le transport SSDV-sur-APRS,
  jamais de copie de code.
- `BY2HIT/*`, `TomasTT7/LoRa_SSDV` : **écartés** tant qu'aucune licence
  n'apparaît (voir §1).

## 3. Portée — ce que ce chantier n'est PAS

Ce n'est pas une fonctionnalité isolée. C'est un **nouveau sous-système**,
comparable en ampleur au copilote FT8 ou à VOACAP, qui touche potentiellement :
- la réception audio (démodulation AFSK/AX.25 — matériel RX, jamais TX) ;
- le suivi de passage satellite (déjà partiellement présent : Doppler EME
  existe pour l'EME, à vérifier s'il est réutilisable) ;
- la persistance (images partielles/complètes, métadonnées par paquet) ;
- une UI de suivi de réception progressive.

**Aucune émission n'est concernée** (SSDV ici = RÉCEPTION d'images depuis des
ballons/satellites/stations distantes) — le skill `tx-human-consent` ne
s'applique pas à ce chantier tel que cadré, SAUF si un incrément futur ajoute
la retransmission (relais) d'une image reçue, auquel cas le charger avant d'y
toucher.

## 4. Découpage proposé (à valider, pas commencé)

**Phase 1 — offline, zéro radio, zéro risque.** Le seul incrément que je
proposerais de commencer sans plus de validation, car il ne touche à rien de
sensible :
- `concours/logx_ssdv.py` : wrapper sous-processus autour du binaire `ssdv`
  externe (encode/decode), sur le même patron que `logx_voacap.py`.
- Parseur de paquet SSDV pur Python (256 octets → champs), écrit depuis le
  format public, testé sur des paquets synthétiques ET sur la sortie réelle
  du binaire `ssdv -e` (aller-retour encode→decode vérifiable).
- Assembleur d'image basique (paquets → JPEG partiel/complet), gestion des
  paquets manquants/dupliqués/désordonnés.
- Tests : aucun matériel requis, tout est vérifiable en local avec une image
  de test + le binaire externe.

**Phases suivantes (PAS cadrées ici, à discuter séparément une fois la Phase 1
validée)** : transport AX.25/APRS (nécessite de choisir un chemin audio →
trame — Dire Wolf ? adaptateur maison ?), fusion multi-stations (nécessite un
canal de partage — le mécanisme d'occupation multi-postes LAN/Cloud/MySQL déjà
construit pourrait être réutilisé, à évaluer), suivi de passage satellite,
UI temps réel.

## 5. Questions ouvertes pour F4GLD

1. **Priorité** : ce chantier passe-t-il devant/après C1 (requêtes langage
   naturel du copilote, déjà en attente de cadrage) et l'incrément 5c de la
   fusion CHASSE (rediriger `logx_chasse.html`, en attente de ton feu vert) ?
2. **Binaire externe** : `ssdv` (fsphil) doit être compilé/vendorisé comment —
   même patron que `voacapl.exe` (binaire embarqué dans les releases) ou
   dépendance système que l'utilisateur installe lui-même ?
3. **Cas d'usage réel** : c'est pour toi (ballons/satellites que tu suis
   personnellement) ou une demande plus générale ? Ça oriente le Phase 2
   (quel transport prioriser : AX.25 classique, ou un mode spécifique à ton
   usage).
4. Périmètre Phase 1 ci-dessus te convient-il, ou tu veux une portée
   différente pour le premier incrément ?
