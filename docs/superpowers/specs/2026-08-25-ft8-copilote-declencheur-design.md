# Copilote FT8 — déclencheur « répondre à un appel » (spec)

**Date :** 2026-08-25
**Décisions produit (F4GLD, cadrage 25/08) :**
- Première action : **répondre à un appel reçu** (une station répond à mon CQ / m'appelle).
- Source : **FT8** (décodes déjà classés « pour moi » sur `logx_ft8.html`).
- Autonomie : **l'IA PROPOSE, l'humain confirme CHAQUE émission** (jamais d'auto-émission).
- Déclenchement : **AUTO** — dès qu'un décode m'est adressé, l'IA remplit la barre.

C'est la première brique concrète de la roadmap « copilote IA » (mémoire
`projet-ia-copilote-roadmap`) : IA discrète, ne remplace jamais l'émission.

## Principe

> L'IA **prépare** une émission (remplit la barre), l'**humain déclenche**
> (bouton ÉMETTRE de la barre `logx_tx_bar.js`, #256). Aucune émission
> automatique. Le contrôle de consentement (#255/#257) et le garde-fou
> mode/bande relisent l'état radio réel au PTT — inchangés.

L'« IA » de cette étape est **déterministe** : le protocole d'un QSO FT8 fixe la
réponse (grille → report → RR73 → fin). Pas de LLM, pas de réseau : marche en
zone blanche. Le mot « copilote » = le logiciel prépare la réponse standard, tu
gardes la main.

## Ce qui EXISTE déjà (réutilisé, non réécrit)

- `logx_ft8.html` : table des décodes, classe `tr.tome` = décode qui m'est
  adressé (détection « pour moi » déjà faite), lignes cliquables.
- `logx_tx_bar.js` (#256) : barre d'émission auto-montante, `LogxTxBar.proposer()`.
- `logx_tx_consent` / `/tx/*` (#255/#257/#258) : consentement + PTT + audit.
- `logx_tx_guard.tx_autorise` : garde-fou mode/bande.

## Composants

### 1. `logx_ft8_copilote.js` (nouveau, client, sur `logx_ft8.html`)

Bloc IIFE exposant `window.LogxFt8Copilote`. Deux parties :

**a) Cœur PUR (testé en V8) :**

```
reponseFt8(decode, monCall, etatQso) -> {message, dxCall} | null
```
- `decode` : `{message: 'F4GLD DL1ABC JN48', ...}` (texte FT8 brut décodé).
- `monCall` : mon indicatif (ex. 'F4GLD').
- `etatQso` : `{dxCall, phase}` du QSO courant, où `phase` ∈
  `'idle' | 'called' | 'reportSent' | 'rogerSent'` — ce que J'AI envoyé en
  dernier ; `dxCall` = la station que je travaille (ou '').
- **Sortie** : le message FT8 à émettre + l'indicatif DX, ou `null` si rien à
  proposer.

Règles (protocole FT8 standard, transitions déterministes) :
- décode NON adressé à `monCall` → `null` (jamais proposer).
- « `monCall DXCALL <grille>` » (on m'appelle avec sa grille) →
  `'DXCALL monCall <report>'` (je réponds report ; report = SNR du décode, ex.
  '-12').
- « `monCall DXCALL R<report>` » (il m'accuse réception avec R+report) →
  `'DXCALL monCall RR73'`.
- « `monCall DXCALL RR73 | RRR | 73` » → QSO terminé → `null` (rien à proposer ;
  on pourra plus tard proposer « relancer CQ », hors scope ici).
- décode d'une AUTRE station que celle en QSO, pendant un QSO en cours → `null`
  (on ne détourne pas un QSO en cours ; gestion pile-up = hors scope).

**b) Effet (non testé unitairement, colle mince) :** `onDecode(decode)` appelé à
chaque décode reçu :
- calcule `r = reponseFt8(decode, monCall, etatQso)` ;
- si `r` et que la barre n'est pas déjà en train de proposer/émettre CE même
  message → `LogxTxBar.proposer({mode:'FT8', message:r.message, frequency_hz,
  power_w, operator:monCall, radio_id})` ;
- anti-spam : ne pas re-proposer le même `{dxCall, message}` déjà proposé et non
  encore émis (idempotence par clé `dxCall|message`).

**Interrupteur** : `LogxFt8Copilote.setActif(bool)` (défaut : inactif au
chargement — on n'arme pas l'auto-préparation sans un geste). Rendu par une
case « Copilote FT8 » sur la page. AUTO ne veut pas dire ON par défaut :
l'opérateur arme le copilote une fois, ensuite les propositions sont
automatiques tant qu'il est armé.

### 2. `logx_ft8.html` (modifié)

- inclut `<script src="logx_tx_bar.js">` (la barre) + `<script src="logx_ft8_copilote.js">`.
- branche `LogxFt8Copilote.onDecode(d)` là où un décode est ajouté à la table.
- ajoute la case « Copilote FT8 » (identité graphite & cuivre).

## Flux de données

```
WSJT-X/décodeur natif → décode → table (tr.tome) → onDecode()
  → reponseFt8() → (message) → LogxTxBar.proposer() → /tx/prepare (jeton)
  → barre affichée → [HUMAIN clique ÉMETTRE] → /tx/authorize (relit CAT +
    garde-fou) → PTT + émission FT8 → journal d'audit
```

## Erreurs / garde-fous

- Décode illisible / format inattendu → `reponseFt8` renvoie `null` (jamais
  d'exception qui casse la page).
- Copilote inactif → `onDecode` ne fait rien.
- Le consentement expire en 30 s (si tu ne confirmes pas, la proposition
  s'efface) — déjà géré par la barre/#255.
- Jamais d'auto-émission : l'émission passe TOUJOURS par ÉMETTRE (geste humain).
- `etatQso` inconnu (page rechargée) → phase `'idle'` : on répond à un appel
  entrant, on ne fabrique pas d'état faux.

## Tests

- `reponseFt8` en TDD (V8, `test_ft8_copilote.py`) + mutation :
  - appel avec grille → report ;
  - R+report → RR73 ;
  - RR73/73 → `null` (fin) ;
  - décode pas pour moi → `null` ;
  - décode d'une autre station pendant un QSO → `null`.
- anti-spam (idempotence) : deux décodes identiques → une seule proposition
  (testable sur une fonction pure `doitProposer(cle, dejaPropose)` ).
- inclusion scripts sur `logx_ft8.html` (ordre) : test structurel.

## Hors scope (étapes suivantes de la roadmap)

- Gestion pile-up (choisir qui répondre parmi plusieurs appels) — une stratégie
  serveur existe déjà (`/wsjtx/strategy`), à relier plus tard.
- Relancer un CQ, suggérer un QSY, autres modes (CW/SSB).
- Niveaux d'autorisation 2-4 (semi-auto temporisé, etc.) — ici uniquement
  « IA propose, humain confirme ».
