# Copilote FT8 — niveaux 3-4 (session autonome) — Design

**But :** Ajouter au copilote FT8 deux niveaux d'autonomie au-delà du niveau 2
(semi-auto temporisé, une émission à la fois) :

- **Niveau 3 `copilote_qso`** — une fois engagé sur un correspondant, enchaîne
  **tout le QSO** seul (`report → R+report → RR73 → 73`) sans reconfirmer chaque
  trame.
- **Niveau 4 `copilote_cq`** — en plus, **appelle CQ** et **travaille les
  répondants** automatiquement (pile-up / DXpédition), un QSO après l'autre.

Le tout dans une **session autonome** explicitement armée par l'opérateur, qui
**tourne en continu jusqu'à Stop** (décision F4GLD 02/09/2026), sous garde-fous
de sécurité non-négociables.

## Décision F4GLD (02/09/2026) — verbatim et cadrage

> « une fois les tests faits le ft8 doit pouvoir tourner sans jamais s'arrêter
> juste quand l'opérateur dit stop »

Deux implications actées :

1. **Préalable on-air.** « une fois les tests faits » : les niveaux **1-2**
   doivent avoir été validés **sur l'air** par F4GLD avant tout usage réel de
   N3/N4. N3/N4 sont livrés **OFF par défaut** et ne seront **jamais annoncés
   « prêts à l'usage »** sans cet essai (aucun banc ne le remplace — PASSATION
   §« En attente d'un essai sur l'air »).
2. **Pas de budget.** Contrairement au modèle « session limitée » par défaut du
   skill `tx-human-consent` (expiration rapide OU plafond de transmissions), la
   session N3/N4 **n'a ni expiration ni plafond** : elle tourne en continu et ne
   s'arrête que sur **Stop TX** (ou une invalidation de sécurité, ci-dessous).
   C'est un choix assumé de l'opérateur titulaire.

### Note de conformité (à garder visible)

`tx-human-consent` interdit « l'émission automatique » sans autorisation
humaine. Ici l'autorisation humaine existe et est explicite : **armer la
session** EST l'acte d'autorisation, et **Stop TX** la révoque. La
réglementation amateur exige que **l'opérateur de contrôle reste présent et aux
commandes** : le logiciel ne peut pas le garantir, mais il (a) n'émet jamais
sans armement humain, (b) offre un Stop instantané et toujours visible, (c)
**invalide la session dès que l'état radio autorisé change**, et (d) propose un
**contrôle de présence optionnel**. Le logiciel ne rend pas la station
« sans surveillance » : il exécute la volonté d'un opérateur présent.

## État actuel (ce qui existe déjà, à réutiliser)

`concours/logx_ft8_copilote.js` porte **déjà toute la logique pure** nécessaire :

- `reponseFt8(decodeMsg, snr, monCall)` — machine d'état QSO (report → R+report →
  RR73 → fin) ; renvoie `null` à la clôture. **C'est le moteur de N3.**
- `appelInitial(cible, monCall, monGrid)` — message d'appel / réponse à CQ.
- `estFinQso(decodeMsg, monCall)` — détecte RRR/RR73/73 qui m'est adressé.
- File pile-up : `ajouterFile`, `retirerFile`, `epurerFile` (péremption ~90 s),
  `prochainFile` (priorité : cliqué manuel > nouveau DXCC > FIFO). **Base de N4.**
- `doitProposer` / `delaiAutoMs` — connaissent `copilote` (N1) et
  `copilote_auto` (N2). **À étendre pour N3/N4.**

Émission & traçabilité (PASSATION #256/#262/#266) : le FT8 **émet côté client**
(`logx_ft8.html`, hors `/tx/authorize`), et la barre `logx_tx_bar.js` **POSTe
`/tx/trace`** ; `logx_tx_consent.journal_copilote_emission` grave
`TX_COPILOTE_EMISSION` dans le journal d'audit serveur (`/tx/audit`). Backend
d'autorisation `logx_tx_consent.py` (jeton `TxConsent`, `authorize_transmission`
relit le CAT réel) : utilisé par les émissions **voix/CW** serveur, pas par le
FT8 client.

### Contrainte architecturale honnête

Le FT8 émettant **côté client**, le garde-fou de session vit en **JS client +
audit serveur** (même modèle que le consentement FT8 actuel). Le backend **ne
peut pas** PTT-gater le FT8. La spec ne prétend pas le contraire : la sûreté
N3/N4 repose sur (a) le contrôle client rigoureux et testé, (b) la trace
serveur inviolable a posteriori, (c) le Stop TX qui coupe la boucle client.

## Architecture

### 1. Niveaux

Ajouter au sélecteur `#ft8Niveau` deux valeurs, **sous** N1/N2, marquées d'un
avertissement (⚠️ « émission autonome — essai sur l'air requis ») :

| Niveau | Clé | Comportement |
|---|---|---|
| N1 | `copilote` | propose → l'humain confirme CHAQUE trame (inchangé) |
| N2 | `copilote_auto` | propose → émet UNE trame après délai, annulable (inchangé) |
| **N3** | `copilote_qso` | session armée → **QSO complet** auto sur le correspondant engagé |
| **N4** | `copilote_cq` | session armée → **CQ + pile-up** : appelle, met en file, travaille chaque répondant en QSO N3 |

`doitProposer` reste vrai pour tous les niveaux copilote. Un nouveau prédicat
`estSessionAutonome(niveau)` = `niveau === 'copilote_qso' || niveau ===
'copilote_cq'` gouverne l'enchaînement sans reconfirmation.

### 2. Modèle de session autonome (client)

Une **session** est un objet client (module neuf `logx_ft8_session.js`, logique
PURE et testable) :

```
SessionAutonome {
  armed: bool,                 // false tant que l'humain n'a pas armé
  niveau: 'copilote_qso'|'copilote_cq',
  radioEmpreinte: {band, dial_hz, mode, power_w},  // enveloppe autorisée
  demarreeUtc, txCount,        // audit/affichage (pas une LIMITE)
  presence: {actif, dernierPingUtc, delaiPauseS}   // filet optionnel
}
```

- **Armement** = geste humain explicite : bouton « Autoriser une session
  autonome » qui affiche l'enveloppe (radio/bande/fréquence/mode/puissance) et
  passe `armed=true` en mémorisant `radioEmpreinte`. Rien n'émet avant.
- **Pas de budget** : ni `expiresAt`, ni `maxTx`. `txCount` n'est qu'un compteur
  d'affichage/audit.
- **Invalidation immédiate** (`armed=false`, la boucle s'arrête, rien ne repart
  sans ré-armement) déclenchée par, fonction pure `sessionValide(session,
  radioActuelle, cat, horloge)` :
  - **Stop TX** (bouton global, toujours visible) ;
  - tout **écart** entre `radioEmpreinte` et l'état radio courant (bande,
    dial ±tolérance, mode, puissance) — règle verbatim `tx-human-consent`
    « émettre après un changement … sans NOUVELLE validation » interdit ;
  - **CAT déconnecté** ou **horloge UTC désynchronisée** (réutilise les gardes
    existants `test_ft8_dt_horloge` / état CAT) ;
  - désarmement manuel.

### 3. N3 — QSO complet automatique

Engagement : soit l'opérateur **clique** une station, soit — session armée — le
**premier décode « pour moi »** engage ce correspondant (`qsoActifDx`). Ensuite,
à chaque cycle de décodes, tant que `sessionValide` :

1. `reponseFt8(decode, snr, monCall)` calcule la trame suivante ;
2. si non-`null` **et** pas déjà émise ce cycle (`cle` anti-spam), **émettre**
   directement (pas de barre de confirmation), `txCount++`, **tracer**
   `/tx/trace {declencheur:'copilote_qso', session_id}` ;
3. `estFinQso` → QSO clôturé : **proposer le log** (geste humain inchangé, le
   log reste humain), puis désengager (`qsoActifDx=null`) ; en N4, prendre le
   `prochainFile`.

Watchdog QSO : si le correspondant ne répond plus pendant N cycles (réutiliser
la péremption `epurerFile` / un `maxCyclesSansReponse`), **abandonner** ce QSO
(pas la session) et relancer (N4) ou attendre (N3).

### 4. N4 — CQ + pile-up

Session armée, aucun QSO en cours : **appeler CQ** (`appelInitial` en variante
CQ : `CQ MONCALL MONGRID`), émettre, tracer `declencheur:'copilote_cq'`. Sur les
répondants : `ajouterFile` (dédup, plafond 10, péremption 90 s existants), puis
`prochainFile` (priorité nouveau-DXCC / cliqué) → engager en QSO **N3**. À la
clôture, station suivante. Le pile-up réutilise **tel quel** le code existant.

### 5. Contrôle de présence (optionnel, recommandé)

Filet contre l'oubli (opérateur parti) **sans** contredire « tourne jusqu'au
Stop » : réglage **activable/désactivable**, **désactivé par défaut** (décision
F4GLD 02/09 : vrai continu dès le départ ; le filet reste disponible si
l'opérateur le coche). Si actif : après `delaiPauseS` sans interaction (souris/
touche/ping), la session **met l'émission en PAUSE** (n'émet plus, n'annule pas
la session) et affiche « Toujours là ? » ; un clic reprend. **Désactivable**
pour un vrai fonctionnement continu sans interaction. Logique pure
`doitPauserPresence(session, nowUtc)` testable.

### 6. Traçabilité (audit serveur, inchangé dans son principe)

Chaque émission autonome POSTe `/tx/trace` avec `declencheur ∈
{copilote_qso,copilote_cq}` + un **`session_id`** (uuid par armement) ;
`journal_copilote_emission` grave `TX_COPILOTE_EMISSION`. Ajouter deux entrées
d'audit : `TX_SESSION_ARMED` (à l'armement, avec l'enveloppe radio) et
`TX_SESSION_ENDED` (au Stop/invalidation, avec la raison). Consultable via
`/tx/audit` et le panneau « Journal d'émission » existant. Fire-and-forget (une
trace ratée ne défait jamais une émission, comme #266).

### 7. UI (`logx_ft8.html`)

- Sélecteur niveau : deux options N3/N4 avec pastille ⚠️ et, tant qu'aucun essai
  on-air confirmé, un texte « à valider sur l'air ».
- **Bandeau de session** (quand N3/N4) : bouton **« Autoriser une session
  autonome »** (affiche l'enveloppe avant d'armer) ; une fois armée : état
  (armée/en pause/QSO en cours avec DX, `txCount`, `session_id` court), et
  **STOP TX** géant toujours visible. Invalidation → bandeau rouge « Session
  arrêtée : <raison> — ré-armer ». Réglage présence (case à cocher + délai).
- Charte graphite & cuivre, tokens de page, jour/nuit ; `textContent` pour tout
  état dynamique (jamais `innerHTML`) ; toute chaîne visible via `Tf(...)`.

## Garde-fous — récapitulatif non-négociable

1. **Rien n'émet sans armement humain explicite** de la session.
2. **Stop TX** instantané, global, toujours visible → coupe la boucle et
   désarme.
3. **Invalidation** immédiate à tout changement de l'enveloppe radio autorisée
   (bande/fréquence/mode/puissance), CAT perdu, horloge désync.
4. **Le log reste un geste humain** (proposé, jamais écrit par l'IA — invariant
   `test_invariants_securite`).
5. **OFF par défaut**, gaté sur l'essai on-air des niveaux 1-2 par F4GLD.
6. **Trace serveur** inviolable de chaque émission + armement/arrêt.
7. Contrôle de présence **recommandé** (activable), pause douce si absence.

## Tests (banc uniquement — zéro prétention on-air)

- `logx_ft8_session.js` (PUR) : `estSessionAutonome`, `sessionValide` (chaque
  cause d'invalidation → false, contre-épreuve par mutation), enchaînement N3
  (séquence de décodes simulés → trames attendues, arrêt à `estFinQso`), N4
  (CQ → file → prochain → QSO), watchdog, `doitPauserPresence`. En V8
  (py_mini_racer), à la manière de `test_ft8_copilote.py`.
- Serveur : `/tx/trace` + audit `TX_SESSION_ARMED/ENDED` (Python), datetimes
  aware-UTC, `now` injectable.
- **Invariants sécurité** : étendre `test_invariants_securite.py` — « aucune
  émission N3/N4 quand `armed=false` », « Stop désarme », « changement radio
  invalide », « 0 écriture QSO par l'IA ».
- Chaque test précédé d'un **témoin vert** et suivi d'une **contre-épreuve par
  mutation** (méthode du dépôt).

## Hors scope

- Toute validation **sur l'air** (geste F4GLD, prérequis, non automatisable).
- Émission FT8 **serveur/PTT-gated** (le FT8 reste client + tracé ; pas de
  refonte de l'architecture d'émission).
- FT4/FT2, CW/SSB en session autonome (N3/N4 = FT8 d'abord).
- Tri « intelligent » avancé des appelants au-delà de l'existant (nouveau-DXCC /
  cliqué / FIFO).

## Auto-revue

- **Placeholders** : aucun TODO/TBD. Le défaut du contrôle de présence est
  tranché (désactivé, F4GLD 02/09).
- **Cohérence** : réutilise `reponseFt8`/`appelInitial`/`estFinQso`/file
  existants (source de vérité inchangée) ; n'ajoute que le moteur d'autonomie +
  la session + l'UI + la trace. Pas de duplication de la machine d'état QSO.
- **Sécurité vs décision opérateur** : « pas de budget » assumé et documenté ;
  les garde-fous conservés ne bornent pas l'autonomie, ils garantissent que la
  session reflète l'état radio réel et reste sous Stop humain.
- **Périmètre** : tenable en un plan d'implémentation (module session + glue
  logx_ft8.html + UI + trace + tests). N4 réutilise N3 + file existante.
