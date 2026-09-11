# SSDV (Slow Scan Digital Video) — spec de cadrage

**Date :** 2026-09-11. **Statut : VALIDÉ par F4GLD (11/09/2026), Phase 1 en
cours d'implémentation.** Les 3 questions ouvertes du §5 sont tranchées :
binaire vendorisé (option A, patron `voacapl.exe`), usage général (pas
seulement personnel), portée Phase 1 confirmée sans changement (« zéro
risque »). Écrit
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

**Mise à jour (11/09/2026, avant implémentation)** : les offsets du format de
paquet ont été relus ligne à ligne contre le vrai code source de
`fsphil/ssdv` (`ssdv.c`/`ssdv.h`, via `gh`/fetch direct du dépôt, pas la note
reçue) — deux extractions indépendantes, dont une contradiction trouvée et
résolue (une première lecture inversait `SSDV_TYPE_NORMAL`/`SSDV_TYPE_NOFEC`,
corrigée en relisant `ssdv_enc_get_packet`/`ssdv_dec_is_packet` directement) :

- Paquet = 256 octets (`SSDV_PKT_SIZE`). En-tête = 15 octets (offsets 0-14) :
  `[0]` sync `0x55` · `[1]` type = `0x66 + type` (`SSDV_TYPE_NORMAL=0x00` avec
  FEC Reed-Solomon, `SSDV_TYPE_NOFEC=0x01` sans FEC) · `[2-5]` indicatif encodé
  base-40 (32 bits) · `[6]` id image · `[7-8]` id paquet (MSB puis LSB) ·
  `[9]` largeur/16 · `[10]` hauteur/16 · `[11]` fanions : qualité =
  `((o[11]>>3)&7)^4`, EOI = `(o[11]>>2)&1`, mode MCU = `o[11]&0x03` ·
  `[12]` décalage MCU · `[13-14]` id MCU (MSB puis LSB).
- Indicatif base-40 : `-`→0, `0`-`9`→1-10, `A`-`Z`→14-39 (11-13 inutilisés) ;
  encodage = construction depuis le DERNIER caractère (poids fort = premier
  caractère de l'indicatif) — le décodage doit donc extraire les chiffres
  base-40 par divisions/modulos successifs puis les inverser.
- Charge utile : `256 - 15 (en-tête) - 4 (CRC)` sans FEC, `- 32` de plus
  (Reed-Solomon) avec FEC — non exploité en Phase 1 (voir §4 : la
  reconstruction complète reste déléguée au binaire `ssdv`, le parseur Python
  ne lit QUE l'en-tête pour le suivi/l'affichage, jamais la charge utile ni le
  FEC, pour rester dans la portée « zéro risque » votée).
- Fréquences ERMINAZ/contenu détaillé du guide UKHAS : toujours non vérifiés,
  non nécessaires pour la Phase 1 (aucun transport radio dedans).

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

## 5. Décisions de F4GLD (11/09/2026)

1. **Priorité** : tranchée de fait — 5c (fusion CHASSE) a été fait en premier
   (mergé), C1 reste en attente de cadrage séparé, SSDV démarre maintenant.
2. **Binaire externe — Option A retenue** : `ssdv` (fsphil) est **vendorisé**,
   même patron que `voacapl.exe` (`concours/voacap/win64/`) — binaire
   embarqué dans les releases, pas une dépendance système à installer par
   l'utilisateur. Conséquence pour l'implémentation : `logx_ssdv.py` résout
   un chemin vendorisé (`concours/ssdv/<plateforme>/`, à créer) avant de
   retomber sur le `PATH` système (utile en dev tant que le binaire n'est pas
   encore commité — obtention/compilation du binaire lui-même est un suivi
   séparé, pas bloquant pour la Phase 1 qui ne l'exige pas pour tourner :
   parseur/assembleur sont testables sur des paquets synthétiques sans lui,
   les tests d'intégration sous-processus se `skip` si absent, même patron
   que `test_q65_natif.py` pour `jt9`).
3. **Cas d'usage — demande générale**, pas seulement l'usage personnel de
   F4GLD. Oriente la Phase 2 (non cadrée ici) vers un transport générique
   plutôt qu'un mode spécifique à une pratique individuelle.
4. **Portée Phase 1 confirmée sans changement** (« zéro risque ») : le
   découpage du §4 est adopté tel quel.
