---
name: chantier-acom-doc-communautaire-2026-08-09
description: "Tâche #168 : pilotage ACOM (500S/600S/700S/1200S/2020S) par port série, logx_acom.py — doc communautaire réellement implémentée (09/08, fusionné 5b907dc)"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T14:39:54.123Z
---

Tâche #168 du backlog LogX AI (« ACOM, doc communautaire »), demandée
explicitement par F4GLD (« aller 168 ») après #166 (Icom remote-internet,
désactivé) et #167 (PowerGenius XL, refuse operate/standby). Fusionné sur
main : commit 5b907dc (merge), 446f114 (contenu) — CI verte.

## Source et niveau de confiance (plus élevé que PGXL/Icom)

Une seule source, mais de meilleure qualité que les 2 précédentes : le
dépôt GitHub open source (MIT) `bjornekelund/ACOM-Controller` de Björn
Ekelund (SM7IUN, membre CWops, propriétaire réel d'un ampli ACOM — voir
sm7iun.se/station/acom/). Fichier `MainWindow.xaml.cs` (641 lignes) téléchargé
intégralement via `gh api`/`curl` et LU LIGNE PAR LIGNE par l'outil Read —
PAS un résumé WebFetch (contrairement au blocage qui a forcé
`logx_icomremote.py` à rester désactivé : un résumé produit par un petit
modèle est insuffisant pour un protocole binaire où un octet faux invalide
tout). Corroboration indépendante trouvée par WebSearch : un fil du forum
communautaire FlexRadio confirme indépendamment que "the PA can be switched
on or off using the CTS or DSR pins" — cohérent avec le commentaire du code
source lui-même (`DtrEnable=false; RtsEnable=false; // ... to avoid blocking
front panel power button`), preuve que ce n'est pas une lecture isolée.

**Piste explicitement réfutée** : une recherche web antérieure avait fait
remonter « SunSDR utiliserait le protocole Kenwood pour ces amplis » — la
lecture du vrai code source CONTREDIT cette affirmation : le protocole est
binaire propriétaire (en-tête `0x55`), rien à voir avec l'ASCII Kenwood/
Yaesu/Elecraft de `logx_cat.py`. Piste écartée explicitement, pas ignorée
en silence.

## Différence structurelle avec PGXL : Operate/Standby/Off RÉELLEMENT implémenté

Contrairement à `logx_powergenius.py` (qui REFUSE toute bascule operate/
standby, candidat "interlock disable" à sémantique de sécurité incertaine),
`logx_acom.py` implémente réellement 3 commandes (`CMD_OPERATE`/
`CMD_STANDBY`/`CMD_OFF`, bytes fixes) car leur sémantique est NON ambiguë :
gestionnaires de bouton nommés explicitement dans le code source réel
(`OperateClick`/`StandbyClick`/`OffClick`). **How to apply** : la règle de
la maison (« un module qui refuse proprement vaut mieux qu'un module qui
invente ») n'impose pas un refus systématique — le niveau de rigueur exigé
dépend de l'ambiguïté RÉELLE de la commande candidate, pas d'un réflexe de
prudence uniforme. Vérifier au cas par cas si la source lue nomme
explicitement la fonction du bouton/de la commande.

**Ce qui reste explicitement refusé/non implémenté** (confirmé par
l'ABSENCE de toute commande correspondante dans les 641 lignes lues) :
- Aucune commande bande/fréquence : l'ampli suit lui-même le signal
  d'excitation (auto-tracking), la bande de la télémétrie est en LECTURE
  SEULE.
- RTS/DTR jamais pilotés après l'ouverture du port (posés bas une seule
  fois dans `AcomPort.__init__`, jamais retouchés) : sur l'ACOM ces lignes
  coupent/rallument l'ALIMENTATION PHYSIQUE de l'ampli (pas un PTT
  générique) — un enjeu plus grave qu'un bug logiciel sur un ampli de
  plusieurs centaines de watts.
- Transport Ethernet "ACOM eBox" non implémenté : son manuel PDF officiel
  trouvé mais illisible par l'outil WebFetch (flux FlateDecode) — seul le
  RS-232 direct est proposé, pas deviné pour le pont Ethernet.
- Unité de la puissance réfléchie (`reflected_raw`) : gardée BRUTE, la
  source elle-même ne documente pas de conversion en Watts pour ce champ.

## Protocole (résumé technique confirmé)

9600 bauds/8N1, sans contrôle de flux. 5 commandes fixes (Enable/Disable
télémétrie + Operate/Standby/Off). Télémétrie : trame 72 octets, en-tête
`0x55 0x2F`, somme totale ≡0 mod 256 = checksum valide. Table de calibration
par modèle (offset température, puissances nominale/max) confirmée pour
exactement 5 modèles (500S/600S/700S/1200S/2020S) — modèle absent =
`temp_c` reste `None`, jamais deviné.

## Bug réel trouvé par la revue adversariale (Workflow, 2 dimensions)

`CMD_DISABLE_TELEMETRY` était défini mais jamais envoyé (`AcomPort.close()`/
`disconnect_persistent()` fermaient le port sans l'envoyer), alors que le
vrai code C# (`MainWindow_Closed`) l'envoie à la fermeture propre — le
docstring décrivait Enable/Disable comme une paire symétrique sans préciser
que seule la moitié Enable était répliquée. Sévérité mineure (pas de risque
matériel, `get_state()` réactive la télémétrie à chaque appel) mais vraie
divergence doc/code. Corrigé en câblant réellement l'envoi dans
`AcomPort.close()`, PAS en édulcorant la docstring — 2 tests dédiés ajoutés
(`test_acom_port_close_envoie_disable_telemetry_avant_de_fermer` +
variante "ignore erreur écriture") avec un double `_FakeUnderlyingSerial`
(même patron que `test_cat.py::test_serialport_ouvre_avec_rts_dtr_bas`) car
le double `_FakeSerialPort` utilisé pour le reste des tests ne touche
jamais pyserial et ne pouvait PAS détecter ce bug. **How to apply** : pour
tout module qui enveloppe pyserial, prévoir DEUX niveaux de double de
test — un double de haut niveau (interface métier, ex. `send_command`/
`read_one_frame`) pour la logique, ET un double bas niveau
(`_pyserial.Serial`, patron `_FakeUnderlyingSerial`) pour prouver que la
VRAIE classe wrapper (construction RTS/DTR bas, comportement de close())
fait ce qu'elle prétend — sinon un bug dans le wrapper lui-même reste
invisible.

## Intégration (patron PGXL répliqué)

CONFIG : popup dédié `catmodal_acom` ("20. ACOM"), `CONFIG_SECTIONS`+1,
`_EXPERT_ONLY_CATS`+1 (5 catégories désormais), `_catStatus()` case ajouté,
`refreshAcomPorts()`/`testAcomConnection()`/`acomSetOperate()`. HTTP :
`_acom_state_dict()` dans `/hardware/state`, routes `POST /acom/test` ET
`POST /acom/operate` (cette dernière absente côté PGXL). 2 tests existants
cassés par le changement de nombre (20→21 entrées CONFIG_SECTIONS, 4→5
catégories expert-only) — attendu et corrigé, pas un bug (voir
[[piege-echo-exit-masque-code-sortie-reel]] : suite complète relancée 2 fois
avec `REAL_EXIT_CODE` explicite pour confirmer 0 échec avant de committer).

## Voir aussi

Précédents directs : PGXL (`chantier-cat-proprietaire-omnirig-flex-pgxl-icomremote-2026-08-06.md`
si existant, sinon docstring de `logx_powergenius.py`/`logx_icomremote.py`
eux-mêmes, qui documentent leur propre rigueur de sourcing).
