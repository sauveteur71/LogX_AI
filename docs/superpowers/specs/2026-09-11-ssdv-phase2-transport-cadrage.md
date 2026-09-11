# SSDV Phase 2 — transport AX.25/APRS : spec de cadrage

**Date :** 2026-09-11. **Statut : à valider par F4GLD avant tout code.**
Phase 1 (parseur d'en-tête + assembleur + wrapper sous-processus, PR #472)
livrée et mergée — voir `docs/superpowers/specs/2026-09-11-ssdv-integration-
design.md`, qui listait explicitement les phases suivantes comme NON
cadrées : « transport AX.25/APRS (nécessite de choisir un chemin audio →
trame — Dire Wolf ? adaptateur maison ?), fusion multi-stations, suivi de
passage satellite, UI temps réel. » Ce document cadre la PREMIÈRE de ces
quatre — le transport — condition préalable aux trois autres (rien à
fusionner/suivre/afficher sans paquets reçus).

## 1. Le problème

La Phase 1 sait parser un en-tête de paquet SSDV DÉJÀ EXTRAIT et assembler
une image à partir de paquets bruts. Elle ne sait pas comment ces paquets
ARRIVENT : un ballon/satellite les transmet en AFSK 1200 bauds encapsulés
dans une trame AX.25 (protocole radioamateur de paquet), reçue sur une
fréquence VHF/UHF via une radio + une carte son (ou un TNC matériel).
Démoduler l'AFSK et décoder l'AX.25 depuis un flux audio brut est un
sous-système à part entière (filtrage, synchronisation bit, désembrouillage
HDLC, CRC AX.25) — PAS quelque chose à réimplémenter dans LogX AI.

## 2. Précédent directement applicable dans ce dépôt

**LogX AI a déjà résolu EXACTEMENT ce problème pour un autre protocole** :
WSJT-X fait tout le traitement DSP lourd (démodulation FT8/FT4/...) et
publie ses résultats décodés en **UDP** (protocole Qt QDataStream) ;
`logx_wsjtx.py` écoute ce port et consomme des messages déjà structurés
(`start_listener`, écouteur en thread de fond, idempotent). LogX AI ne fait
AUCUNE démodulation audio lui-même pour FT8.

**Proposition : reproduire ce patron pour AX.25/APRS**, avec **Direwolf**
(`wb2osz/direwolf`, GPL-2.0, actif, vérifié via `gh api` le 11/09/2026 — pas
supposé) comme équivalent de WSJT-X : c'est le logiciel de référence pour
transformer un flux audio radioamateur en trames AX.25 décodées, standard
de facto dans la communauté (ballons haute altitude, APRS, packet radio). Il
expose ses trames décodées via **KISS-sur-TCP** (port 8001 par défaut) ou
AGW packet engine — LogX AI écouterait ce port, EXACTEMENT comme il écoute
déjà le port UDP de WSJT-X, sans jamais toucher à l'audio brut ni
réimplémenter la couche AX.25/HDLC.

- **Licence** : même raisonnement déjà appliqué à VOACAP et au binaire
  `ssdv` — Direwolf tourne en processus EXTERNE séparé, LogX AI se connecte
  à son port réseau local. Aucun code copié/lié, aucune obligation GPL
  reportée sur le dépôt.
- **Ce que LogX AI aurait à écrire** : un client KISS (parseur de trames
  KISS — encadrement simple par octets FEND/FESC, PAS un décodeur AX.25
  complet puisque Direwolf a déjà désencapsulé jusqu'à la trame AX.25 ; il
  reste à extraire le CHAMP INFO de la trame AX.25 — c'est là que vivent
  les 256 octets SSDV) + le câblage vers `logx_ssdv.ajouter_paquet`/
  `assembler_image` (Phase 1, déjà en place).

## 3. Ce que ce document NE tranche PAS

- **Fusion multi-stations** (plusieurs récepteurs partagent leurs paquets
  reçus pour compléter une image que chacun a reçue partiellement) :
  nécessite un canal de partage. Le mécanisme d'occupation multi-postes
  LAN/Cloud/MySQL déjà construit dans LogX AI est un candidat, à évaluer
  SÉPARÉMENT une fois le transport de base validé.
- **Suivi de passage satellite/ballon** (savoir QUAND pointer/écouter) :
  chantier à part, peut réutiliser des briques existantes (Doppler EME) à
  vérifier plutôt que supposer.
- **UI temps réel** (voir l'image se construire paquet par paquet) : dépend
  du transport ci-dessus pour exister, cadrage séparé une fois les paquets
  effectivement reçus par un chemin réel.

## 4. Questions ouvertes pour F4GLD

1. **Confirmes-tu Direwolf** comme le chemin audio → trame à intégrer (vs.
   un TNC matériel qui parlerait KISS directement sur un port série — dans
   ce cas le client KISS serait le même, seule la source du port change,
   TCP vs série) ?
2. **As-tu déjà (ou prévois-tu) le matériel pour tester réellement** — une
   radio VHF/UHF + interface son sur une fréquence où passe du SSDV
   (ballons HAB, ARISS, etc.) ? Sans un vrai flux à un moment donné, ce
   chantier reste vérifié uniquement sur des trames KISS synthétiques
   (comme la Phase 1 a été vérifiée sans le binaire `ssdv` réel) — pas
   bloquant pour commencer, mais à savoir pour situer quand une vérification
   terrain deviendra possible.
3. **Priorité relative à C1** (déjà en incrément 1, la suite — questions IA
   complètes — n'est pas cadrée non plus) : ce chantier Phase 2 SSDV
   passe-t-il devant ou après la suite de C1 ?
