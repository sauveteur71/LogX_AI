---
name: chantier-kpa1500-reseau-2026-08-06
description: "Ajout du pilotage réseau TCP/UDP du KPA1500 Elecraft — port Ethernet natif, mêmes commandes ASCII que le port série"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-06T07:00:12.635Z
---

Demande explicite de F4GLD, citant mot pour mot un item que j'avais moi-même
noté dans une précédente liste d'améliorations futures : « Amplificateur
KPA1500 : pilotage série uniquement pour l'instant, pas de support réseau
TCP/UDP (comme le CAT natif à ses débuts, avant TCI). »

**Recherche préalable (Workflow dédié)** avant tout code : le KPA1500 (pas
le KPA500) a un port Ethernet natif (RJ45) donnant accès à un serveur TCP
ET un serveur UDP, tous deux par défaut sur le port 1500 (modifiable via la
commande `^CP`), qui acceptent EXACTEMENT le même jeu de commandes ASCII
`^XX;` que le port série — confirmé par la Programming Reference officielle
Elecraft (Rev 2.03, p.6 : "A TCP server at port 1500 accepts the same
serial command set"). Serveur UDP ajouté en firmware 01.84, canal
indépendant du TCP. Piège de recherche trouvé : le port TCP 4526 mentionné
ailleurs dans la doc/les forums Elecraft concerne un mécanisme TOTALEMENT
différent — le logiciel officiel "KPA1500 Remote" (relais applicatif pour
accès Internet via port forwarding), PAS le serveur de commandes natif.

**Implémentation** : `TcpAmpPort`/`UdpAmpPort` dans `logx_amp.py`,
implémentant la même interface que `SerialPort` (write/transceive/
read_until/close) — donc **zéro changement** dans `KpaAmp` elle-même, qui
ne sait même pas quel transport elle utilise. `amp_settings()` gagne un
`conn_mode` ('serial' par défaut — rétrocompatible, 'tcp' ou 'udp').
Réseau réservé à la marque `elecraft` : Icom/SPE n'ont aucun accès réseau
documenté officiellement, refusé explicitement avec message clair plutôt
que de laisser deviner un comportement non testé.

**Tests** : contrairement aux autres tests de `logx_amp.py` (transports en
mémoire, `FakeKpaAmp` etc.), ceux du réseau ouvrent un VRAI socket loopback
(127.0.0.1, port éphémère détecté par bind puis fermeture) avec un serveur
de test TCP/UDP en thread de fond — prouve que le transport parle
correctement au FIL du protocole (bufferisation TCP fragmentée, terminateur
`;`, surplus conservé pour l'appel suivant), pas seulement à un dict Python.
`socket.socketpair()` utilisé pour tester `_recv_until()` en white-box sans
dépendre d'un serveur complet.

**Vérification navigateur** : bout en bout réel avec un faux serveur TCP
KPA1500 sur une instance de serveur isolée (port 8099) — a déclenché
[[piege-instance-isolee-partage-server-config]], un vrai incident de config
partagée corrigé avec l'accord explicite de l'utilisateur.

**Contexte découvert en même temps** : la tâche SOTA demandée juste avant
(« API officielle + enums ADIF + repli RBN ») s'est révélée déjà
ENTIÈREMENT livrée par une session antérieure non capturée dans l'index de
mémoire (voir [[ressources-techniques-veille-2026-07-21]], corrigé) — aucun
code à écrire, juste vérifier avant de refaire un travail déjà fait.
