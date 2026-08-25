# Copilote FT8 — niveau « supervisé » du séquenceur (spec, révisée)

**Date :** 2026-08-25
**Décisions produit (F4GLD, cadrage 25/08) :**
- Première action : **répondre à un appel reçu** (une station répond à mon CQ / m'appelle).
- Source : **FT8**.
- Autonomie : **l'IA PROPOSE, l'humain confirme CHAQUE émission** (jamais d'auto-émission).
- Déclenchement : **AUTO** — dès qu'un décode m'est adressé, l'IA remplit la barre.

Première brique concrète de la roadmap « copilote IA » (mémoire
`projet-ia-copilote-roadmap`) : IA discrète, ne remplace jamais l'émission.

## Révision majeure vs 1re version de la spec

L'exploration a montré que **le séquenceur FT8 existe déjà** dans
`logx_ft8.html` (mode #179) et contient TOUT :
- la **machine d'état** du QSO FT8 (validée par la doc protocole fournie par
  F4GLD : appel+grille → report → R+report → RR73 → 73) ;
- le **calcul du message suivant** (`TX1`…`TX5`, extraction indicatifs/grille/
  report, pièges déjà corrigés type grille='RR73') ;
- la **journalisation** du QSO (« Séquenceur — déroule le QSO et le logue ») ;
- des **niveaux d'autonomie gradués** : `seqNiveau ∈ {manuel, assisté,
  séquenceur, auto}` (déjà l'ossature des « 4 niveaux » de la roadmap) ;
- un **point d'émission unique** `envoyerMessage()` (→ `/rig/ptt`, engage le PTT).
- banc de tests existant : `tests/test_ft8_sequenceur.py`.

**Conséquence : on ne réécrit RIEN de cette logique** (ce serait un doublon +
un risque, cf. règle DRY et pièges déjà payés). Le copilote = **un nouveau
niveau `seqNiveau === 'copilote'`** qui insère le **consentement humain** entre
« calculer le message suivant » et « émettre ».

## Principe

> À `seqNiveau === 'copilote'`, dès qu'un décode m'est adressé, le séquenceur
> calcule le message suivant **exactement comme aujourd'hui**, mais au lieu
> d'appeler `envoyerMessage()` (auto-TX), il appelle
> `LogxTxBar.proposer({mode:'FT8', message, …})`. La barre s'affiche ;
> **l'humain clique ÉMETTRE** → alors seulement `envoyerMessage()` part.
> Aucune auto-émission. Le consentement (#255/#257) relit le CAT réel au PTT.

Déterministe, zéro réseau → marche en zone blanche. « Copilote » = le logiciel
prépare la réponse standard, l'opérateur garde la main sur CHAQUE émission.

## Composants

### 1. `logx_ft8.html` (modifié) — nouveau niveau `copilote`

- **Sélecteur de niveau** : ajouter l'option `copilote` (« Copilote —
  l'IA prépare, tu confirmes chaque émission ») entre `assisté` et `séquenceur`
  dans `<select>` (ligne ~526). Persisté comme les autres (`seqNiveau`).
- **Inclusion** : `<script src="logx_tx_bar.js">` (barre #256, auto-montante)
  sur la page FT8 (aujourd'hui seulement sur `logx_logbook.html`).
- **Point d'accroche** : là où le séquenceur décide d'émettre le message calculé
  (juste avant `envoyerMessage()`), si `seqNiveau === 'copilote'` → router vers
  `LogxTxBar.proposer(...)` au lieu d'émettre ; sur confirmation (ÉMETTRE),
  `envoyerMessage()` avec CE message. Sinon (`séquenceur`/`auto`), comportement
  inchangé.
- La gate de CONTINUATION du QSO (`seqNiveau === 'sequenceur' || 'auto'`,
  ligne ~3998) est étendue pour que `copilote` déroule aussi la séquence — mais
  chaque pas passe par la barre.

### 2. `logx_ft8_copilote.js` (nouveau, MINCE, client) — colle testable

Le séquenceur reste la source de vérité ; ce module n'expose que la **glue
pure et testable** pour ne pas noyer la logique dans `logx_ft8.html` :

```
LogxFt8Copilote.doitProposer(seqNiveau)      -> bool   # true seulement si 'copilote'
LogxFt8Copilote.messagePropose(txMsg, dxCall, freqHz, monCall)
    -> {mode:'FT8', message, frequency_hz, operator, ...}   # payload pour proposer()
LogxFt8Copilote.cle(dxCall, txMsg)           -> string # clé anti-spam (idempotence)
```
- **anti-spam** : on ne re-propose pas la même `cle(dxCall,txMsg)` déjà proposée
  et non émise (re-décodes du même cycle 15 s).
- Le module NE calcule PAS le message FT8 (c'est le séquenceur existant) — il
  ne fait que décider *si* proposer et *emballer* la proposition.

## Flux de données

```
décode « pour moi » → séquenceur calcule le message suivant (TX1..TX5, logique
  existante) → SI niveau 'copilote' : LogxFt8Copilote.doitProposer → proposer()
  → /tx/prepare → barre affichée → [HUMAIN clique ÉMETTRE] → /tx/authorize
  (relit CAT + garde-fou) → envoyerMessage() (émission FT8 réelle) →
  journalisation existante du QSO à la clôture (RRR/RR73/73 reçu)
```

## Journalisation & données (confirmé par F4GLD)

Réutilise la journalisation FT8 existante du séquenceur (elle stocke déjà
call/station_callsign/date/time/band/freq/mode MFSK/submode FT8/rst_sent/
rst_rcvd/gridsquare/my_gridsquare). **Ajout** demandé : un champ interne
**« autorisation humaine TX utilisée »** — relier l'entrée de journal d'audit
du consentement (jeton, horodatage UTC, cf. `logx_tx_consent._audit_entry`) au
QSO logué, pour justifier a posteriori pourquoi/qu'il a été émis avec
consentement. Détail d'implémentation à préciser dans le plan (le QSO logué
porte une référence au dernier audit TX de ce DX).

Règle de clôture (déjà appliquée par le séquenceur, confirmée par la doc) :
loguer quand RRR/RR73/73 est REÇU du correspondant, message contenant les deux
indicatifs, cohérent avec la séquence active, reports échangés, fenêtre
temporelle réaliste, pas un doublon.

## Erreurs / garde-fous

- Décode illisible / format inattendu → aucune proposition, jamais d'exception.
- Niveau ≠ `copilote` → comportement historique strictement inchangé.
- Consentement expiré (30 s sans ÉMETTRE) → la proposition s'efface (barre/#255).
- **Jamais d'auto-émission** au niveau `copilote` : l'émission passe TOUJOURS
  par ÉMETTRE. Le PTT réel relit le CAT (fréq/mode) via le consentement.
- Un seul QSO à la fois (comportement séquenceur existant) ; pile-up hors scope.

## Tests

- `logx_ft8_copilote.js` en V8 (`test_ft8_copilote.py`) + mutation :
  `doitProposer` (seul 'copilote' → true), `messagePropose` (payload correct),
  `cle`/anti-spam (deux fois la même clé → une proposition).
- Structurel : `logx_ft8.html` inclut `logx_tx_bar.js` ; l'option `copilote`
  présente dans le `<select>`.
- Non-régression : `tests/test_ft8_sequenceur.py` doit rester vert (les niveaux
  `séquenceur`/`auto` inchangés).
- Vérif navigateur (thèmes jour/nuit) sur la page FT8 = étape supervisée F4GLD
  (déclencher un décode simulé « pour moi », voir la barre s'afficher).

## Hors scope (roadmap ultérieure)

- Pile-up (choisir parmi plusieurs appelants — stratégie serveur `/wsjtx/strategy`
  existe déjà, à relier plus tard).
- Relancer un CQ automatiquement, suggérer un QSY, modes CW/SSB.
- Niveaux d'autorisation 2-4 pleinement formalisés (semi-auto temporisé…) — ici
  uniquement « IA propose, humain confirme chaque émission ».
