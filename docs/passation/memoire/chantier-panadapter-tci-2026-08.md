---
name: chantier-panadapter-tci-2026-08
description: "Panadapter TCI (flux IQ brut → FFT pur Python écrite à la main), 3e et dernier volet du panadapter (04/08/2026, `f00e9c8`)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-04T13:43:05.521Z
---

Suite et clôture du [[chantier-panadapter-audio-et-civ-2026-08]] — les 3 volets
recommandés par l'étude initiale sont désormais tous livrés sur `main`.

## Différence structurelle avec le scope CI-V (le volet précédent)

Contrairement à Icom (spectre déjà calculé en interne, juste à parser), le
protocole TCI (Expert Electronics, spec v2.0 officielle, dépôt GitHub
ExpertSDR3/TCI) **n'a aucune commande "spectre pré-calculé"** — seulement un
flux IQ brut (frames WebSocket binaires, header C 64 octets, 4 formats
d'échantillon possibles : INT16/INT24/INT32/FLOAT32). Toute la chaîne FFT a
donc dû être écrite à la main, en PUR PYTHON (`cmath`/`math`/`struct`/
`collections` — aucune dépendance numpy ajoutée, cohérent avec la philosophie
stdlib-only déjà établie dans ce projet) : Cooley-Tukey radix-2 itérative,
fenêtre de Hann, conversion magnitude→dB→échelle 0-255.

## Bug préexistant corrigé au passage (comme pour le has_sub CI-V)

`WebSocketClient.recv_message()` ne gérait QUE le texte (commandes TCI) —
les frames BINAIRES (opcode WS 0x2, le flux IQ) étaient **silencieusement
ignorées** avant ce chantier (jamais ajoutées au buffer, la boucle terminait
quand même sur `fin`, produisant une chaîne vide). Corrigé : la méthode
retourne désormais `(is_binary, payload)`, `_read_loop()` route vers
`_handle_line()` (texte) ou `_handle_binary_frame()` (binaire) selon le cas.

## Vérification de la FFT SANS matériel réel — la seule façon crédible

Comme pour le scope CI-V, aucun accès à un vrai serveur TCI. La seule preuve
valable qu'une FFT écrite à la main est correcte : construire un signal de
référence CONNU (sinusoïde complexe pure `amp * cmath.exp(2j*pi*f*n/fs)`) et
vérifier que le bin de plus forte amplitude tombe au bin MATHÉMATIQUEMENT
attendu (`round(f*N/fs) + N/2` après fftshift), à ±1 bin près (fuite
spectrale normale hors-bin). Les deux revues adversariales ont explicitement
vérifié que ce test existait et testait VRAIMENT la position du pic — pas
seulement la taille du tableau retourné (piège identifié à l'avance dans le
brief du workflow, jamais rencontré en pratique ici).

## Deux constats PLAUSIBLE (pas de CONFIRMED cette fois) — tous deux réels, tous deux corrigés

Contrairement au chantier CI-V précédent (1 bug critique + 1 mineur, tous
deux marqués CONFIRMED), les deux revues adversariales de ce chantier n'ont
rien trouvé de CONFIRMED — mais ont chacune remonté un constat PLAUSIBLE que
j'ai jugés réels après relecture et corrigés moi-même (une classification
"PLAUSIBLE" plutôt que "CONFIRMED" ne veut pas dire "à ignorer" — la
distinction sert seulement à décider si le pipeline automatique de
correction se déclenche, pas un jugement de réalité) :

1. **Mélange de débits d'échantillonnage pendant une transition
   `IQ_SAMPLERATE`** : le buffer circulaire IQ (`deque(maxlen=4096)`) n'était
   jamais vidé lors d'un changement de débit en cours de flux — jusqu'à 4095
   échantillons captés à l'ANCIEN débit pouvaient rester mélangés avec les
   nouveaux dans une même fenêtre FFT, pendant que `span_hz` annoncé au
   client passait déjà au nouveau débit. Corrigé : `set_iq_samplerate()`
   vide le buffer (`self._iq_buffer.clear()` + `_iq_meta['sample_rate_hz']
   = None`) AVANT d'envoyer la commande.
2. **`fetch()` sans `keepalive:true` dans le handler `beforeunload`** :
   `arreterTci()` envoie `IQ_STOP` via un `fetch()` best-effort, mais sans ce
   drapeau le navigateur peut annuler la requête à la fermeture d'onglet
   avant qu'elle n'atteigne le serveur — laissant le flux IQ tourner
   indéfiniment côté serveur (jusqu'à 384 kHz en continu). Corrigé.

## Piège trouvé en corrigeant moi-même : mon propre fix a cassé un test

Après le correctif #1, pytest complet a révélé un échec dans
`test_tci_spectrum_line_bout_en_bout` — le double de test (`_FakeWs`) était
construit avec TOUS ses messages pré-mis en file (texte `ready;vfo:...` PUIS
la trame IQ binaire), consommés quasi instantanément par le fil de lecture
dès `connect_and_start()`, **avant même** que le test appelle
`tci_spectrum_configure()`. Mon correctif #1 (légitime) vide alors ce
buffer — qui vient d'être rempli par un scénario qui n'arrive JAMAIS en
vrai (un vrai serveur TCI ne pousse de blocs IQ_STREAM qu'APRÈS avoir reçu
IQ_START, jamais avant/pendant la connexion initiale). Résolu en corrigeant
le TEST (queue la trame IQ dans `entry.ws._queue` APRÈS l'appel à
`tci_spectrum_configure()`, pas avant) plutôt qu'en affaiblissant le
correctif de vidage de buffer — le test est maintenant plus réaliste qu'avant,
pas juste "réparé". Reflex à retenir : quand un correctif de vidage/
invalidation de cache casse un test existant, vérifier D'ABORD si le test
modélisait un ordre d'événements irréaliste avant de soupçonner le
correctif — ici c'était bien le cas.

## Vérification navigateur (par moi, après le workflow)

Mock des 3 endpoints (`/rig/tci_spectrum_available`/`_configure`/`_line`),
sélection RÉELLE de la source TCI via `sel.onchange()` (propriété DOM,
invocable même si la fonction interne est scoped dans l'IIFE de la page),
clic RÉEL sur Démarrer/Arrêter, **contrôle direct du corps ET du flag
`keepalive` du `fetch()` envoyé à l'arrêt** (`{"enabled":false}` +
`keepalive:true` confirmés). Le canvas s'est rendu avec une largeur
dégénérée (2px) cette fois — panne d'affichage du panneau navigateur de la
session (`window.innerWidth/innerHeight` à 0), pas un bug de code : déjà
vérifié avec un canvas correctement dimensionné (810px) sur le volet audio
et le volet CI-V, et le code de rendu (`dessinerSpectre`/`dessinerWaterfall`/
`nBinsActuel`) est PARTAGÉ entre les 3 sources — la justesse numérique de la
FFT elle-même est de toute façon prouvée par pytest, pas par une inspection
de pixels.

## Statut final des 3 volets du panadapter

1. Audio universel (`7fdcf16`) — MERGÉ.
2. Scope CI-V Icom (`598321e`) — MERGÉ, 1 bug critique trouvé et corrigé
   (voir [[chantier-panadapter-audio-et-civ-2026-08]]).
3. TCI (`f00e9c8`, ce fichier) — MERGÉ, 2 constats mineurs trouvés et
   corrigés, 1 test corrigé en conséquence.

Les 3 méthodes de vérification "sans matériel réel" utilisées dans ce
diptyque (trames CI-V synthétiques construites à la main d'après spec PDF
officielle ; signal FFT de référence mathématiquement vérifiable) sont
réutilisables telles quelles pour tout futur chantier protocole radio sans
accès au matériel cible.
