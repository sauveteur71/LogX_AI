---
name: chantier-cat-plug-and-play-2026-08
description: "Audit + implémentation d'une auto-connexion CAT partielle (bandeau de détection USB, jamais 100% automatique) — 2 vrais bugs corrigés en cours de route, 2 follow-ups flagués"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-03T18:01:01.006Z
---

F4GLD a demandé un audit + avis sur la faisabilité d'un « brancher et ça
marche tout seul » pour la connexion radio (CAT direct ou via boîtier
interface). Réponse après un audit multi-agents (workflow, 7 agents :
existant du code, protocoles, VID:PID, hotplug, état de l'art, contre-
arguments sceptiques) : **le zéro-clic total n'est pas raisonnable** — le
seul logiciel du marché qui l'a tenté (Ham Radio Deluxe) voit sa propre
doc dire de ne PAS s'en servir ; tous les autres (WSJT-X, N1MM+, flrig,
Log4OM, DXLab Commander) évitent même le réglage « Auto » côté radio. En
revanche, un vrai progrès est possible et sûr : passer de 5-7 clics à 1 clic
de confirmation, en combinant VID:PID/numéro de série (zéro risque, aucun
octet CAT envoyé) + la sonde active déjà existante (`autodetect_scan`).

**Implémenté** (branche `feat/cat-plug-and-play`) :
1. `list_ports()` enrichi (vid/pid/serial_number/product — déjà fournis
   par pyserial, juste pas remontés avant).
2. `guess_from_usb_signature()` : pré-filtre passif. Icom identifiable via
   son numéro de série USB (« IC-7300 03000000 », confirmé par recherche —
   ne distingue PAS port CAT vs port audio d'un IC-9700, suffixe A/B
   traité pareil, documenté comme limitation assumée). microHAM/RIGblaster/
   RIGtalk identifiables via leur PID USB dédié. Puces génériques (CP210x/
   FTDI/CH340/PL2303) ne disent RIEN seules.
3. Watcher de branchement (`port_watcher_loop`, thread daemon démarré
   depuis `logx_serveur.py`) : diff de `list_ports()` toutes les 1.5s,
   jamais d'octet CAT envoyé. Choisi plutôt que WM_DEVICECHANGE/WMI
   (latence gagnée imperceptible pour un humain, coût = dépendance +
   piège de thread Windows/COM en plus).
4. 2 endpoints HTTP (`GET /rig/pending_detections`, `POST /rig/dismiss_detection`)
   + bandeau flottant dans `logx_configuration.html` (poll 2s) : « Radio
   détectée sur COMx — Configurer ? ». Le clic « Configurer » ouvre la
   popup radio, sélectionne le port, puis relance `autodetectCat()` (sonde
   active déjà sûre) — **jamais d'activation automatique du pilotage sans
   ce clic**, choix assumé après l'audit (voir plus haut).

**2 vrais bugs trouvés et corrigés au fil de l'implémentation** (pas
propres au plug-and-play, présents en usage normal) :
1. **Faux positif CI-V par écho/bouclage** : `civ_parse_frame()` ne
   vérifiait jamais le SENS de la trame (TO=E0/PC, FROM=adresse radio) —
   un câble en boucle ou un port sans vraie UART derrière était accepté à
   tort comme une vraie réponse, silencieusement. Corrigé dans
   `CivRadio._query()`/`autodetect()` (logx_cat.py) ET `IcomAmp._get()`/
   `_set()` (logx_amp.py, même bug racine, trouvé en creusant). Complété
   par la revue adversariale (voir plus bas) : le garde-fou initial ne
   vérifiait pas non plus que `cmd`/`sub` correspondent à la requête
   envoyée — critique sur un bus CI-V partagé entre plusieurs logiciels
   (LogX + WSJT-X via séparateur, tous avec l'adresse contrôleur 0xE0 par
   convention), sinon la réponse d'un AUTRE logiciel à SA propre commande
   pouvait être mal interprétée (ex. fréquence BCD lue comme booléen PTT).
2. **RTS/DTR non maîtrisés à l'ouverture** : par défaut, ouvrir un port
   série lève RTS/DTR — sur une interface qui y câble le PTT, un simple
   test de connexion pourrait déclencher l'émission. Voir
   [[piege-pyserial-rts-dtr-constructeur]] pour le détail : **mon premier
   correctif (rts=/dtr= en kwargs du constructeur) cassait TOTALEMENT
   l'ouverture de port en production** (pyserial 3.5 rejette ces kwargs),
   masqué par un test dont le double acceptait n'importe quel kwarg —
   trouvé et corrigé grâce à la revue adversariale AVANT toute fusion.

🚨 **Revue adversariale (workflow, 5 dimensions + vérification
contradictoire) lancée avant fusion** — a trouvé le bug RTS/DTR ci-dessus
(critique, jamais poussé grâce à ça) + 6 autres constats corrigés :
- Garde-fou de commande manquant (voir bug #1 ci-dessus).
- XSS : `refreshCatPorts()`/`refreshAmpPorts()` injectaient `device`/
  `description` (venant du descripteur USB, donc falsifiable par un
  périphérique malveillant) en innerHTML SANS échapper — corrigé avec
  `escC()` déjà existant dans le fichier. Le nouveau flux plug-and-play
  rendait ce bug préexistant directement exploitable (branchement USB →
  refreshCatPorts() automatique).
- `applyCatDetection()` ne vérifiait pas que le port détecté existait
  encore après `refreshCatPorts()` — pouvait sonder silencieusement
  l'ANCIEN port déjà configuré et afficher un faux "succès". Corrigé avec
  un message d'avertissement explicite si le port a disparu.
- Clignotement du bandeau (course entre le dismiss fire-and-forget côté
  client et la confirmation serveur) — corrigé en ne remettant
  `_catDetectionShown` à zéro que quand le serveur confirme la liste vide.
- `_port_watcher_tick()` n'absorbait les exceptions que pour `list_ports()`,
  pas pour `guess_from_usb_signature()`/la construction du dict — une
  exception là aurait tué le thread daemon pour de bon, silencieusement,
  jusqu'au redémarrage du serveur (potentiellement plusieurs jours en
  expédition). Élargi à tout le corps de la fonction.
- `get_pending_detections()` renvoyait des références directes aux dicts
  internes plutôt que des copies — corrigé (latent, pas encore exploité).
- Test `test_icom_amp_echo_boucle_ne_donne_jamais_ok` ne testait RIEN du
  garde-fou de `_set()` (l'écho d'une requête SET ne se termine jamais par
  hasard en FB/FD) — ajouté 2 tests adversariaux dédiés (accusé bien formé
  mais mauvais sens ; accusé sans vrai préambule).

**Follow-ups flagués (spawn_task, pas fait dans ce chantier)** :
- Relire plusieurs trames dans la fenêtre de timeout d'un essai CAT (une
  trame parasite unique sur un bus CI-V partagé fait échouer tout l'essai
  au lieu de simplement l'ignorer — faux négatif qui nuit à la promesse
  plug-and-play).
- Permettre de configurer l'adresse CI-V de la radio PRINCIPALE dans
  CONFIG (seul l'ampli a ce champ aujourd'hui) — pré-existant, indépendant
  de ce chantier.

**Leçon de méthode** : le premier "correctif" de sécurité (RTS/DTR) était
en réalité une régression critique qui aurait cassé TOUT le CAT natif en
production — jamais détecté par mes propres tests (mock trop permissif),
détecté uniquement parce qu'un workflow de revue adversariale a été lancé
AVANT de considérer le chantier terminé, avec des agents qui ont
**reproduit l'erreur directement contre la vraie bibliothèque installée**
plutôt que de se fier au code lu. Systématiser cette revue pour tout
changement touchant à l'ouverture de ports/bibliothèques externes.
