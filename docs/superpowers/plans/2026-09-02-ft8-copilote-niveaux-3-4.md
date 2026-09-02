# Copilote FT8 niveaux 3-4 (session autonome) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter au copilote FT8 deux niveaux d'autonomie — N3 `copilote_qso`
(QSO complet automatique) et N4 `copilote_cq` (CQ + pile-up) — pilotés par une
session autonome armée par l'humain, tournant en continu jusqu'au Stop TX.

**Architecture:** Un module PUR neuf `logx_ft8_session.js` porte tout l'état et
les décisions de session (armement, validité, choix de la trame à émettre en
enchaînant `reponseFt8`/`appelInitial`/la file pile-up déjà présents dans
`logx_ft8_copilote.js`). `logx_ft8.html` branche ce module dans la boucle de
décodes existante et ajoute l'UI (sélecteur N3/N4, bandeau de session, Stop TX).
Le backend (`logx_tx_consent.py`/`logx_http.py`) n'ajoute que la **trace**
(session_id + armement/arrêt) — le FT8 émet côté client, le backend ne PTT-gate
pas. Aucune réécriture de la machine d'état QSO.

**Tech Stack:** JavaScript vanilla (logique pure testée en V8 via
`py_mini_racer`), Python 3 `http.server`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-02-ft8-copilote-niveaux-3-4-design.md`

## Global Constraints

- **Sécurité d'émission (skill `tx-human-consent`)** : rien n'émet sans
  armement humain explicite de la session ; **Stop TX** instantané, global,
  toujours visible ; **invalidation immédiate** si bande/fréquence/mode/
  puissance change, CAT déconnecté ou horloge UTC désynchronisée ; le **log
  reste un geste humain** (l'IA ne l'écrit jamais).
- **OFF par défaut, gaté sur l'essai on-air N1-N2** : N3/N4 livrés désactivés ;
  ne JAMAIS annoncer « prêt à l'usage » sans l'essai sur l'air de F4GLD. Aucun
  banc ne le remplace.
- **Pas de budget** : session sans expiration ni plafond de transmissions —
  s'arrête uniquement sur Stop TX ou invalidation de sécurité.
- **Contrôle de présence : désactivé par défaut** (F4GLD 02/09), disponible.
- **FT8 émet côté client** : garde-fou en JS pur + audit serveur ; ne pas
  tenter de PTT-gater le FT8 côté backend.
- **Réutiliser la logique existante** de `logx_ft8_copilote.js`
  (`reponseFt8`, `appelInitial`, `estFinQso`, `ajouterFile`, `retirerFile`,
  `epurerFile`, `prochainFile`, `cle`) — source de vérité, ne pas la dupliquer.
- **Méthode du dépôt** : TÉMOIN VERT avant toute mutation ; après correctif,
  remettre le défaut → le test ROUGIT → restaurer (md5). Assertions sur le
  COMPORTEMENT/la STRUCTURE, jamais sur une simple présence de chaîne.
- **i18n** : toute chaîne visible neuve via `Tf(...)`. **Affichage** :
  `textContent` pour tout état dynamique (jamais `innerHTML`). Charte graphite
  & cuivre, tokens de page, jour/nuit par construction.

---

## Structure des fichiers

- **Créer** `concours/logx_ft8_session.js` — état + décisions de session
  (PUR, sans DOM ni réseau). Responsabilité unique : « à partir de l'état de
  session, de la radio et d'un décode, dire QUOI émettre et si la session est
  encore valide ». Exposé sur `window.LogxFt8Session`.
- **Créer** `concours/tests/test_ft8_session.js` — n/a (les tests V8 chargent
  le `.js` depuis Python). Le fichier de test est `test_ft8_session.py`.
- **Créer** `concours/tests/test_ft8_session.py` — tests V8 (py_mini_racer) de
  la logique pure de session.
- **Modifier** `concours/logx_ft8_copilote.js` — ajouter `estSessionAutonome`
  et la variante CQ `appelCQ` (message `CQ MONCALL GRID`).
- **Modifier** `concours/logx_tx_consent.py` — trace de session (armement/arrêt)
  + `session_id`/`declencheur` dans l'émission tracée.
- **Modifier** `concours/logx_http.py` — endpoint `/tx/trace` accepte
  `session_id` et les déclencheurs `copilote_qso`/`copilote_cq` ; endpoint
  `/tx/session` (armed/ended).
- **Modifier** `concours/tests/test_invariants_securite.py` — invariants N3/N4.
- **Modifier** `concours/logx_ft8.html` — sélecteur N3/N4, bandeau de session,
  branchement du driver dans la boucle de décodes, Stop TX.

---

### Task 1: `estSessionAutonome` + `appelCQ` (glue pure dans le module copilote)

**Files:**
- Modify: `concours/logx_ft8_copilote.js`
- Test: `concours/tests/test_ft8_copilote.py` (fichier existant — ajouter des cas)

**Interfaces:**
- Produces (sur `window.LogxFt8Copilote`) :
  `estSessionAutonome(niveau: string) -> bool` (vrai pour `'copilote_qso'` et
  `'copilote_cq'`) ; `appelCQ(monCall: string, monGrid: string) -> string|null`
  (`'CQ MONCALL GRID4'`, grille tronquée à 4, omise si absente ; null si monCall
  manquant).

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter dans `concours/tests/test_ft8_copilote.py` (calquer l'entête V8 existant
du fichier — `MiniRacer`, chargement de `logx_ft8_copilote.js`, `window={}`) :

```python
def test_est_session_autonome(ctx):
    assert ctx.eval("LogxFt8Copilote.estSessionAutonome('copilote_qso')") is True
    assert ctx.eval("LogxFt8Copilote.estSessionAutonome('copilote_cq')") is True
    assert ctx.eval("LogxFt8Copilote.estSessionAutonome('copilote')") is False
    assert ctx.eval("LogxFt8Copilote.estSessionAutonome('copilote_auto')") is False
    assert ctx.eval("LogxFt8Copilote.estSessionAutonome('manuel')") is False


def test_appel_cq(ctx):
    assert ctx.eval("LogxFt8Copilote.appelCQ('F4GLD','JN15xc')") == 'CQ F4GLD JN15'
    assert ctx.eval("LogxFt8Copilote.appelCQ('f4gld','')") == 'CQ F4GLD'
    assert ctx.eval("LogxFt8Copilote.appelCQ('','JN15')") is None
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd concours && python -m pytest tests/test_ft8_copilote.py -k "session_autonome or appel_cq" -v`
Expected: FAIL (fonctions non définies).

- [ ] **Step 3: Implémenter**

Dans `concours/logx_ft8_copilote.js`, avant le `window.LogxFt8Copilote = {...}` :

```javascript
  // Niveaux à autonomie de SESSION (enchaînent sans reconfirmer chaque trame).
  function estSessionAutonome(niveau) {
    return niveau === 'copilote_qso' || niveau === 'copilote_cq';
  }

  // Appel CQ : 'CQ MONCALL GRID4'. Grille tronquée à 4 (omise si absente).
  function appelCQ(monCall, monGrid) {
    monCall = String(monCall || '').trim().toUpperCase();
    if (!monCall) { return null; }
    var g = String(monGrid || '').trim().toUpperCase().slice(0, 4);
    return 'CQ ' + monCall + (g ? ' ' + g : '');
  }
```

et les ajouter à l'objet exporté :
```javascript
    estSessionAutonome: estSessionAutonome,
    appelCQ: appelCQ,
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd concours && python -m pytest tests/test_ft8_copilote.py -k "session_autonome or appel_cq" -v`
Expected: PASS.

- [ ] **Step 5: Contre-épreuve par mutation**

Remplacer `niveau === 'copilote_qso' || niveau === 'copilote_cq'` par `false`.
`test_est_session_autonome` doit rougir. Restaurer, vérifier md5.

- [ ] **Step 6: Commit**

```bash
git add concours/logx_ft8_copilote.js concours/tests/test_ft8_copilote.py
git commit -m "feat(ft8): estSessionAutonome + appelCQ (glue niveaux 3-4)"
```

---

### Task 2: Module session — `creerSession` + `sessionValide` (cœur sécurité)

**Files:**
- Create: `concours/logx_ft8_session.js`
- Create: `concours/tests/test_ft8_session.py`

**Interfaces:**
- Produces (sur `window.LogxFt8Session`) :
  `creerSession(niveau, radioEmpreinte) -> session` où `radioEmpreinte =
  {band, dial_hz, mode, power_w}` ; la session porte `{armed:true, niveau,
  radioEmpreinte, sessionId, txCount:0, qsoActifDx:null, file:[], vu:{}}`.
  `sessionId` **injectable** (`creerSession(niveau, emp, id)`) pour les tests
  (pas de `Math.random` non déterministe dans le module).
  `sessionValide(session, radioActuelle, etat) -> {ok: bool, raison: string}`
  où `radioActuelle = {band, dial_hz, mode, power_w}`,
  `etat = {stop: bool, cat_ok: bool, horloge_ok: bool, dial_tol_hz: number}`.
  Renvoie `{ok:false, raison:'stop'|'radio'|'cat'|'horloge'|'desarmee'}` sinon
  `{ok:true, raison:''}`.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `concours/tests/test_ft8_session.py` (entête V8 calqué sur
`test_ft8_copilote.py`) :

```python
# -*- coding: utf-8 -*-
"""Session autonome FT8 (logique pure) : validité = reflet de l'état radio."""
import os
import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_ft8_session.js')


@pytest.fixture()
def ctx():
    from py_mini_racer import py_mini_racer
    c = py_mini_racer.MiniRacer()
    c.eval('var window = {};')
    with open(JS, encoding='utf-8') as f:
        c.eval(f.read())
    # rendre l'API accessible au niveau global pour c.eval()
    c.eval('var LogxFt8Session = window.LogxFt8Session;')
    return c


EMP = "{band:'20m',dial_hz:14074000,mode:'USB-D',power_w:20}"
ETAT_OK = "{stop:false,cat_ok:true,horloge_ok:true,dial_tol_hz:50}"


def test_creer_session_armee(ctx):
    s = ctx.eval("JSON.stringify(LogxFt8Session.creerSession('copilote_qso',%s,'sid1'))" % EMP)
    import json
    d = json.loads(s)
    assert d['armed'] is True
    assert d['niveau'] == 'copilote_qso'
    assert d['sessionId'] == 'sid1'
    assert d['txCount'] == 0
    assert d['qsoActifDx'] is None


def test_session_valide_quand_tout_va(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,%s,%s).ok" % (EMP, EMP, ETAT_OK))
    assert r is True


def test_stop_invalide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,%s,{stop:true,cat_ok:true,horloge_ok:true,dial_tol_hz:50}).raison"
                 % (EMP, EMP))
    assert r == 'stop'


def test_changement_bande_invalide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,{band:'40m',dial_hz:14074000,mode:'USB-D',power_w:20},%s).raison"
                 % (EMP, ETAT_OK))
    assert r == 'radio'


def test_dial_hors_tolerance_invalide(ctx):
    # 14074000 -> 14074200 (200 Hz > tol 50) = changement de fréquence TX
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,{band:'20m',dial_hz:14074200,mode:'USB-D',power_w:20},%s).raison"
                 % (EMP, ETAT_OK))
    assert r == 'radio'


def test_dial_dans_tolerance_reste_valide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,{band:'20m',dial_hz:14074030,mode:'USB-D',power_w:20},%s).ok"
                 % (EMP, ETAT_OK))
    assert r is True


def test_cat_perdu_invalide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,%s,{stop:false,cat_ok:false,horloge_ok:true,dial_tol_hz:50}).raison"
                 % (EMP, EMP))
    assert r == 'cat'


def test_horloge_desync_invalide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,%s,{stop:false,cat_ok:true,horloge_ok:false,dial_tol_hz:50}).raison"
                 % (EMP, EMP))
    assert r == 'horloge'


def test_desarmee_invalide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');s.armed=false;"
                 "LogxFt8Session.sessionValide(s,%s,%s).raison" % (EMP, EMP, ETAT_OK))
    assert r == 'desarmee'
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd concours && python -m pytest tests/test_ft8_session.py -v`
Expected: FAIL (module inexistant).

- [ ] **Step 3: Implémenter le module (session + validité)**

Créer `concours/logx_ft8_session.js` :

```javascript
/* logx_ft8_session.js — Session autonome FT8 (niveaux 3-4). LOGIQUE PURE :
 * pas de DOM, pas de réseau, pas d'horloge implicite. Décide de la VALIDITÉ
 * d'une session (reflet de l'état radio réel) et de la trame à émettre en
 * enchaînant la logique du séquenceur (logx_ft8_copilote.js). N'ÉMET PAS
 * elle-même : l'appelant (logx_ft8.html) émet et trace.
 *
 * Sécurité (tx-human-consent) : une session ne vaut QUE si l'état radio n'a pas
 * bougé depuis l'armement (bande/fréquence/mode/puissance), CAT connecté,
 * horloge OK, pas de Stop, encore armée. Toute cause -> {ok:false, raison}.
 */
(function () {
  'use strict';

  function creerSession(niveau, empreinte, sessionId) {
    empreinte = empreinte || {};
    return {
      armed: true,
      niveau: String(niveau || ''),
      radioEmpreinte: {
        band: String(empreinte.band || ''),
        dial_hz: Number(empreinte.dial_hz || 0),
        mode: String(empreinte.mode || ''),
        power_w: Number(empreinte.power_w || 0)
      },
      sessionId: String(sessionId || ''),
      txCount: 0,
      qsoActifDx: null,
      file: [],
      vu: {}
    };
  }

  // Validité = reflet de l'état radio. Ordre des causes : stop > desarmee >
  // cat > horloge > radio (la plus « dure » d'abord ; un seul motif renvoyé).
  function sessionValide(session, radioActuelle, etat) {
    session = session || {}; radioActuelle = radioActuelle || {}; etat = etat || {};
    if (etat.stop) { return { ok: false, raison: 'stop' }; }
    if (!session.armed) { return { ok: false, raison: 'desarmee' }; }
    if (!etat.cat_ok) { return { ok: false, raison: 'cat' }; }
    if (!etat.horloge_ok) { return { ok: false, raison: 'horloge' }; }
    var e = session.radioEmpreinte || {};
    var tol = Number(etat.dial_tol_hz || 0);
    if (String(radioActuelle.band || '') !== e.band ||
        String(radioActuelle.mode || '') !== e.mode ||
        Number(radioActuelle.power_w || 0) !== e.power_w ||
        Math.abs(Number(radioActuelle.dial_hz || 0) - e.dial_hz) > tol) {
      return { ok: false, raison: 'radio' };
    }
    return { ok: true, raison: '' };
  }

  window.LogxFt8Session = {
    creerSession: creerSession,
    sessionValide: sessionValide
  };
})();
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd concours && python -m pytest tests/test_ft8_session.py -v`
Expected: PASS (tous).

- [ ] **Step 5: Contre-épreuve par mutation (2 mutations)**

1. Supprimer la ligne `if (etat.stop) {...}` : `test_stop_invalide` doit rougir.
2. `> tol` → `> 1e12` (tolérance infinie) : `test_dial_hors_tolerance_invalide`
   doit rougir. Restaurer après chaque, vérifier md5.

- [ ] **Step 6: Commit**

```bash
git add concours/logx_ft8_session.js concours/tests/test_ft8_session.py
git commit -m "feat(ft8): module session autonome + sessionValide (coeur securite)"
```

---

### Task 3: Driver N3 — `prochaineTrameQso` (enchaînement QSO complet)

**Files:**
- Modify: `concours/logx_ft8_session.js`
- Modify: `concours/tests/test_ft8_session.py`

**Interfaces:**
- Consumes: `LogxFt8Copilote.reponseFt8`, `.estFinQso` (chargés AVANT ce module
  dans la page ; en test, charger `logx_ft8_copilote.js` puis
  `logx_ft8_session.js`).
- Produces (sur `window.LogxFt8Session`) :
  `prochaineTrameQso(session, decode, monCall) -> {action, message, dx}` où
  `decode = {message, snr, dx}`. `action ∈ {'emettre','loguer','ignorer'}` :
  - `'emettre'` + `message` (trame FT8) + `dx` : émettre la réponse ;
  - `'loguer'` + `dx` : le correspondant a clôturé → proposer le log, désengager ;
  - `'ignorer'` : rien à faire (pas pour moi / autre station en QSO / déjà émis).
  Le module NE modifie PAS `session` (l'appelant applique le résultat).

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter dans `concours/tests/test_ft8_session.py`. **Charger aussi le copilote**
dans la fixture (modifier `ctx` pour évaluer `logx_ft8_copilote.js` PUIS
`logx_ft8_session.js`, et exposer `LogxFt8Copilote`) :

```python
# (modifier la fixture ctx pour charger AUSSI logx_ft8_copilote.js avant session,
#  et: c.eval('var LogxFt8Copilote = window.LogxFt8Copilote;'))

def test_qso_repond_a_un_appel(ctx):
    # « F4GLD DL1ABC JO31 » (on m'appelle avec grille) -> je réponds report
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineTrameQso(s,"
                 "{message:'F4GLD DL1ABC JO31',snr:-12,dx:'DL1ABC'},'F4GLD'))" % EMP)
    import json
    d = json.loads(r)
    assert d['action'] == 'emettre'
    assert d['message'] == 'DL1ABC F4GLD -12'
    assert d['dx'] == 'DL1ABC'


def test_qso_accuse_report(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineTrameQso(s,"
                 "{message:'F4GLD DL1ABC R-08',snr:-10,dx:'DL1ABC'},'F4GLD'))" % EMP)
    import json
    d = json.loads(r)
    assert d['action'] == 'emettre'
    assert d['message'] == 'DL1ABC F4GLD RR73'


def test_qso_cloture_donne_loguer(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineTrameQso(s,"
                 "{message:'F4GLD DL1ABC 73',snr:-10,dx:'DL1ABC'},'F4GLD'))" % EMP)
    import json
    d = json.loads(r)
    assert d['action'] == 'loguer'
    assert d['dx'] == 'DL1ABC'


def test_qso_ignore_pas_pour_moi(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineTrameQso(s,"
                 "{message:'CQ SP9XYZ KO02',snr:-5,dx:'SP9XYZ'},'F4GLD'))" % EMP)
    import json
    assert json.loads(r)['action'] == 'ignorer'
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd concours && python -m pytest tests/test_ft8_session.py -k qso -v`
Expected: FAIL (`prochaineTrameQso` non défini).

- [ ] **Step 3: Implémenter**

Dans `logx_ft8_session.js`, ajouter (avant l'export) :

```javascript
  function _cop() { return (window.LogxFt8Copilote || {}); }

  function prochaineTrameQso(session, decode, monCall) {
    decode = decode || {};
    var cop = _cop();
    if (cop.estFinQso && cop.estFinQso(decode.message, monCall)) {
      return { action: 'loguer', message: '', dx: decode.dx || '' };
    }
    var rep = cop.reponseFt8 ? cop.reponseFt8(decode.message, decode.snr, monCall) : null;
    if (!rep) { return { action: 'ignorer', message: '', dx: '' }; }
    return { action: 'emettre', message: rep.message, dx: rep.dxCall };
  }
```

et l'exporter : `prochaineTrameQso: prochaineTrameQso,`.

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd concours && python -m pytest tests/test_ft8_session.py -v`
Expected: PASS.

- [ ] **Step 5: Contre-épreuve**

Inverser l'ordre : appeler `reponseFt8` AVANT le test `estFinQso`. Alors un
message « 73 » (fin) tenterait une réponse au lieu de `loguer` :
`test_qso_cloture_donne_loguer` doit rougir. Restaurer, md5.

- [ ] **Step 6: Commit**

```bash
git add concours/logx_ft8_session.js concours/tests/test_ft8_session.py
git commit -m "feat(ft8): driver N3 prochaineTrameQso (QSO complet auto)"
```

---

### Task 4: Driver N4 — `prochaineAction` (CQ + pile-up)

**Files:**
- Modify: `concours/logx_ft8_session.js`
- Modify: `concours/tests/test_ft8_session.py`

**Interfaces:**
- Consumes: `LogxFt8Copilote.appelCQ`, `.prochainFile`, `.ajouterFile`,
  `prochaineTrameQso` (Task 3).
- Produces (sur `window.LogxFt8Session`) :
  `prochaineAction(session, decodes, monCall, monGrid) -> {action, message, dx, engager}`
  où `decodes` = liste de `{message,snr,dx}` du cycle. Combine N3 et N4 :
  - si `session.qsoActifDx` : cherche un décode de CE DX et délègue à
    `prochaineTrameQso` (poursuite du QSO en cours) ;
  - sinon (N4) : si un décode m'appelle, l'engager (`engager=dx`) et répondre ;
    si personne mais niveau `copilote_cq`, renvoyer l'appel CQ ;
  - niveau `copilote_qso` sans QSO engagé et sans appel pour moi : `'attendre'`.
  `action ∈ {'emettre','loguer','cq','attendre'}`. Le module renvoie une
  DÉCISION ; l'appelant met à jour `session.qsoActifDx`/`txCount`/`file`.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
def test_n4_appelle_cq_si_personne(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_cq',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineAction(s,[],'F4GLD','JN15'))" % EMP)
    import json
    d = json.loads(r)
    assert d['action'] == 'cq'
    assert d['message'] == 'CQ F4GLD JN15'


def test_n4_engage_un_appelant(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_cq',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineAction(s,"
                 "[{message:'F4GLD IK2ABC JN45',snr:-9,dx:'IK2ABC'}],'F4GLD','JN15'))" % EMP)
    import json
    d = json.loads(r)
    assert d['action'] == 'emettre'
    assert d['dx'] == 'IK2ABC'
    assert d['engager'] == 'IK2ABC'
    assert d['message'] == 'IK2ABC F4GLD -09'


def test_n4_poursuit_le_qso_en_cours(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_cq',%s,'x');s.qsoActifDx='IK2ABC';"
                 "JSON.stringify(LogxFt8Session.prochaineAction(s,"
                 "[{message:'F4GLD IK2ABC R-11',snr:-9,dx:'IK2ABC'}],'F4GLD','JN15'))" % EMP)
    import json
    d = json.loads(r)
    assert d['action'] == 'emettre'
    assert d['message'] == 'IK2ABC F4GLD RR73'


def test_n3_attend_si_aucun_appel(ctx):
    # niveau QSO (pas CQ) : sans QSO engagé ni appel pour moi -> attendre (pas de CQ)
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineAction(s,[],'F4GLD','JN15'))" % EMP)
    import json
    assert json.loads(r)['action'] == 'attendre'
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd concours && python -m pytest tests/test_ft8_session.py -k "n4 or n3_attend" -v`
Expected: FAIL.

- [ ] **Step 3: Implémenter**

```javascript
  function prochaineAction(session, decodes, monCall, monGrid) {
    session = session || {}; decodes = decodes || [];
    var cop = _cop();
    // 1) QSO en cours : poursuivre avec un décode de CE correspondant.
    if (session.qsoActifDx) {
      var cible = String(session.qsoActifDx).toUpperCase();
      for (var i = 0; i < decodes.length; i++) {
        if (String(decodes[i].dx || '').toUpperCase() === cible) {
          var t = prochaineTrameQso(session, decodes[i], monCall);
          return { action: t.action === 'ignorer' ? 'attendre' : t.action,
                   message: t.message, dx: t.dx, engager: '' };
        }
      }
      return { action: 'attendre', message: '', dx: '', engager: '' };
    }
    // 2) Pas de QSO : un décode m'appelle-t-il ? -> engager + répondre.
    for (var j = 0; j < decodes.length; j++) {
      var t2 = prochaineTrameQso(session, decodes[j], monCall);
      if (t2.action === 'emettre') {
        return { action: 'emettre', message: t2.message, dx: t2.dx, engager: t2.dx };
      }
    }
    // 3) Personne : CQ (niveau cq) ou attendre (niveau qso).
    if (session.niveau === 'copilote_cq') {
      var cq = cop.appelCQ ? cop.appelCQ(monCall, monGrid) : null;
      if (cq) { return { action: 'cq', message: cq, dx: '', engager: '' }; }
    }
    return { action: 'attendre', message: '', dx: '', engager: '' };
  }
```

Exporter : `prochaineAction: prochaineAction,`.

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd concours && python -m pytest tests/test_ft8_session.py -v`
Expected: PASS.

- [ ] **Step 5: Contre-épreuve**

Forcer le niveau CQ à toujours renvoyer CQ (retirer le bloc « QSO en cours ») :
`test_n4_poursuit_le_qso_en_cours` doit rougir. Restaurer, md5.

- [ ] **Step 6: Commit**

```bash
git add concours/logx_ft8_session.js concours/tests/test_ft8_session.py
git commit -m "feat(ft8): driver N4 prochaineAction (CQ + pile-up)"
```

---

### Task 5: Contrôle de présence — `doitPauserPresence` (désactivé par défaut)

**Files:**
- Modify: `concours/logx_ft8_session.js`
- Modify: `concours/tests/test_ft8_session.py`

**Interfaces:**
- Produces : `doitPauserPresence(presence, nowMs) -> bool` où
  `presence = {actif: bool, dernierPingMs: number, delaiPauseMs: number}`.
  `false` si `actif` faux (défaut) ; sinon `true` si `nowMs - dernierPingMs >
  delaiPauseMs`. `nowMs` injecté (pas d'horloge implicite).

- [ ] **Step 1: Écrire les tests qui échouent**

```python
def test_presence_inactif_ne_pause_jamais(ctx):
    r = ctx.eval("LogxFt8Session.doitPauserPresence({actif:false,dernierPingMs:0,delaiPauseMs:1000},999999)")
    assert r is False


def test_presence_actif_pause_apres_delai(ctx):
    assert ctx.eval("LogxFt8Session.doitPauserPresence({actif:true,dernierPingMs:0,delaiPauseMs:1000},1500)") is True
    assert ctx.eval("LogxFt8Session.doitPauserPresence({actif:true,dernierPingMs:0,delaiPauseMs:1000},800)") is False
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd concours && python -m pytest tests/test_ft8_session.py -k presence -v`
Expected: FAIL.

- [ ] **Step 3: Implémenter**

```javascript
  function doitPauserPresence(presence, nowMs) {
    presence = presence || {};
    if (!presence.actif) { return false; }
    return (Number(nowMs) - Number(presence.dernierPingMs || 0)) > Number(presence.delaiPauseMs || 0);
  }
```

Exporter : `doitPauserPresence: doitPauserPresence,`.

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd concours && python -m pytest tests/test_ft8_session.py -k presence -v`
Expected: PASS.

- [ ] **Step 5: Contre-épreuve**

Retirer le garde `if (!presence.actif) return false;` :
`test_presence_inactif_ne_pause_jamais` doit rougir. Restaurer, md5.

- [ ] **Step 6: Commit**

```bash
git add concours/logx_ft8_session.js concours/tests/test_ft8_session.py
git commit -m "feat(ft8): controle de presence doitPauserPresence (off par defaut)"
```

---

### Task 6: Trace serveur — session_id + armement/arrêt dans l'audit

**Files:**
- Modify: `concours/logx_tx_consent.py`
- Modify: `concours/logx_http.py`
- Test: `concours/tests/test_tx_session_trace.py` (nouveau)

**Interfaces:**
- Consumes: le journal d'audit existant de `logx_tx_consent.py`
  (`journal_copilote_emission`, `/tx/audit`).
- Produces :
  `journal_session(event, session_id, details, now=None)` — grave
  `TX_SESSION_ARMED` / `TX_SESSION_ENDED` (UTC, non modifiable). `/tx/session`
  (POST `{action:'armed'|'ended', session_id, ...}`) l'appelle. `/tx/trace`
  accepte désormais `session_id` et `declencheur ∈
  {copilote,copilote_auto,copilote_qso,copilote_cq}`.

- [ ] **Step 1: Écrire le test qui échoue**

Créer `concours/tests/test_tx_session_trace.py` (calquer l'entête des tests
`test_tx_*` existants ; `now` injecté aware-UTC) :

```python
# -*- coding: utf-8 -*-
import os, sys, datetime
CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)
import logx_tx_consent as tx  # noqa: E402

UTC = datetime.timezone.utc


def test_journal_session_armed_puis_ended():
    t0 = datetime.datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)
    tx.journal_session('TX_SESSION_ARMED', 'sid42',
                       {'band': '20m', 'dial_hz': 14074000, 'mode': 'USB-D', 'power_w': 20}, now=t0)
    tx.journal_session('TX_SESSION_ENDED', 'sid42', {'raison': 'stop'},
                       now=t0 + datetime.timedelta(minutes=3))
    audit = tx.lire_audit()   # liste d'entrées (fonction existante ; sinon exposer)
    evs = [e for e in audit if e.get('consent_token') is None and e.get('session_id') == 'sid42']
    kinds = [e['event'] for e in evs]
    assert 'TX_SESSION_ARMED' in kinds and 'TX_SESSION_ENDED' in kinds
    armed = next(e for e in evs if e['event'] == 'TX_SESSION_ARMED')
    assert armed['timestamp_utc'].endswith('Z') or '+00:00' in armed['timestamp_utc']
    assert armed['details']['band'] == '20m'
```

*(Si `lire_audit` n'existe pas sous ce nom, adapter au lecteur d'audit réel du
module — repérer la fonction qui rend les entrées `/tx/audit`.)*

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd concours && python -m pytest tests/test_tx_session_trace.py -v`
Expected: FAIL (`journal_session` non défini).

- [ ] **Step 3: Implémenter** dans `logx_tx_consent.py` (à côté de
  `journal_copilote_emission`, MÊME journal d'audit, MÊME format horodaté UTC) :

```python
def journal_session(event, session_id, details, now=None):
    """Grave un événement de SESSION autonome (armement/arrêt) dans le journal
    d'audit d'émission (UTC, non modifiable). Le PTT FT8 est client ; ceci
    trace l'AUTORISATION et sa fin, consultable via /tx/audit même navigateur
    fermé. `now` injectable (aware-UTC) pour les tests."""
    from datetime import datetime, timezone
    ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    _append_audit({                      # réutilise l'ajout d'audit existant
        'event': str(event),
        'timestamp_utc': ts.isoformat().replace('+00:00', 'Z'),
        'session_id': str(session_id or ''),
        'details': dict(details or {}),
        'consent_token': None,           # évènement de session, pas un jeton TX
    })
```

*(Utiliser l'helper d'append d'audit réel du module ; si l'append est inline,
factoriser `_append_audit`.)* Puis, dans `logx_http.py`, router
`POST /tx/session` → `journal_session(body['action']=='armed' and
'TX_SESSION_ARMED' or 'TX_SESSION_ENDED', body['session_id'], body.get('details',{}))`
et accepter `session_id`/`declencheur` élargi dans le handler `/tx/trace`
existant (near `journal_copilote_emission`).

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd concours && python -m pytest tests/test_tx_session_trace.py -v`
Expected: PASS.

- [ ] **Step 5: Contre-épreuve**

Faire écrire `event` en dur `'X'` dans `journal_session` : l'assertion
`'TX_SESSION_ARMED' in kinds` rougit. Restaurer, md5.

- [ ] **Step 6: Test de fumée serveur** : `python -c "import sys;
  sys.path.insert(0,'concours'); import logx_http, logx_tx_consent;
  assert hasattr(logx_tx_consent,'journal_session'); print('OK')"`.

- [ ] **Step 7: Commit**

```bash
git add concours/logx_tx_consent.py concours/logx_http.py concours/tests/test_tx_session_trace.py
git commit -m "feat(ft8): trace serveur session autonome (armed/ended + session_id)"
```

---

### Task 7: Invariants de sécurité N3/N4 (banc)

**Files:**
- Modify: `concours/tests/test_invariants_securite.py`

**Interfaces:**
- Consumes: `LogxFt8Session` (session/validité/drivers) via V8.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter (charger `logx_ft8_copilote.js` + `logx_ft8_session.js` en V8) :

```python
def test_invariant_aucune_emission_si_desarmee(ctx):
    # session désarmée : prochaineAction ne doit JAMAIS renvoyer 'emettre'/'cq'
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_cq',%s,'x');s.armed=false;"
                 "var a=LogxFt8Session.prochaineAction(s,"
                 "[{message:'F4GLD DL1ABC JO31',snr:-9,dx:'DL1ABC'}],'F4GLD','JN15');"
                 "a.action" % EMP)
    # L'appelant ne DOIT pas émettre si sessionValide est faux ; ici on prouve
    # que le garde de validité est la porte : sessionValide(désarmée)=desarmee.
    v = ctx.eval("var s2=LogxFt8Session.creerSession('copilote_cq',%s,'x');s2.armed=false;"
                 "LogxFt8Session.sessionValide(s2,%s,%s).ok" % (EMP, EMP, ETAT_OK))
    assert v is False   # la session désarmée est invalide -> l'appelant n'émet pas


def test_invariant_stop_bloque_meme_avec_appel(ctx):
    v = ctx.eval("var s=LogxFt8Session.creerSession('copilote_cq',%s,'x');"
                 "LogxFt8Session.sessionValide(s,%s,{stop:true,cat_ok:true,horloge_ok:true,dial_tol_hz:50}).ok" % (EMP, EMP))
    assert v is False


def test_invariant_changement_radio_bloque(ctx):
    v = ctx.eval("var s=LogxFt8Session.creerSession('copilote_cq',%s,'x');"
                 "LogxFt8Session.sessionValide(s,{band:'20m',dial_hz:14074000,mode:'CW',power_w:20},%s).ok" % (EMP, ETAT_OK))
    assert v is False
```

*(`EMP`/`ETAT_OK` : réutiliser les constantes ou les définir en tête du
fichier.)*

- [ ] **Step 2: Lancer, vérifier l'échec puis (après Tasks 2-4) la réussite**

Run: `cd concours && python -m pytest tests/test_invariants_securite.py -k "desarmee or stop_bloque or changement_radio" -v`
Expected: PASS (les fonctions existent depuis Tasks 2-4 ; ces tests VERROUILLENT
l'invariant « la validité de session est la seule porte d'émission »).

- [ ] **Step 3: Contre-épreuve**

Dans `sessionValide`, retirer le garde `stop` : `test_invariant_stop_bloque...`
rougit. Restaurer, md5.

- [ ] **Step 4: Commit**

```bash
git add concours/tests/test_invariants_securite.py
git commit -m "test(ft8): invariants securite N3/N4 (validite=seule porte TX)"
```

---

### Task 8: Câblage UI + boucle de décodes (`logx_ft8.html`)

**Files:**
- Modify: `concours/logx_ft8.html`

> **Test :** intégration DOM/loop non testable en banc pur (règle du dépôt :
> pas de test contre un mannequin). La logique est déjà couverte (Tasks 1-7) ;
> ici on CÂBLE. Vérification = revue de structure + **essai navigateur (geste
> F4GLD)**. Ne rien annoncer « prêt » sans l'essai on-air.

- [ ] **Step 1: Charger les modules**

Après `<script src="logx_ft8_copilote.js"></script>`, ajouter
`<script src="logx_ft8_session.js"></script>` (ordre : copilote AVANT session).

- [ ] **Step 2: Sélecteur de niveaux N3/N4**

Dans `#ft8Niveau`, ajouter deux `<option value="copilote_qso">` et
`value="copilote_cq"` (libellés via `Tf(...)`, ex. « Copilote — QSO auto ⚠️ »,
« Copilote — CQ auto ⚠️ »). À la sélection d'un niveau autonome, afficher le
**bandeau de session** (masqué sinon). Texte d'avertissement « à valider sur
l'air » tant qu'aucun essai confirmé.

- [ ] **Step 3: Bandeau de session**

Ajouter un bloc (classe charte, `expert-only` non — c'est le chemin FT8) :
bouton **« Autoriser une session autonome »** qui, au clic, LIT l'état radio
courant (bande/dial/mode/puissance — sources existantes de la page), affiche
l'enveloppe, appelle `LogxFt8Session.creerSession(niveau, empreinte, sessionId)`
(sessionId via `crypto.randomUUID?.() || Date.now()+''`), POSTe
`/tx/session {action:'armed', session_id, details:empreinte}`, et affiche
l'état. Un **bouton STOP TX géant** (réutiliser le Stop existant) toujours
visible : au clic → `sessionCourante.armed=false`, POST `/tx/session
{action:'ended', session_id, details:{raison:'stop'}}`, bandeau rouge.

- [ ] **Step 4: Brancher dans la boucle de décodes**

Là où la page traite les décodes d'un cycle (chercher l'appel existant au
copilote / `recent_decodes`), quand `LogxFt8Copilote.estSessionAutonome(niveau)`
et `sessionCourante` :
1. construire `radioActuelle` + `etat = {stop, cat_ok, horloge_ok, dial_tol_hz:50}`
   depuis l'état de page (CAT connecté, horloge NTP OK — sources existantes) ;
2. `var v = LogxFt8Session.sessionValide(sessionCourante, radioActuelle, etat);`
   si `!v.ok` → **désarmer**, bandeau rouge « Session arrêtée : `v.raison` »,
   POST `/tx/session ended`, **ne rien émettre** ;
3. si `doitPauserPresence(...)` → mettre en pause (ne pas émettre, afficher
   « Toujours là ? ») ;
4. sinon `var a = LogxFt8Session.prochaineAction(sessionCourante, decodes,
   monCall, monGrid);` puis selon `a.action` :
   - `'emettre'`/`'cq'` : émettre via le **chemin d'émission FT8 existant**
     (le même que le séquenceur `#179`/copilote), `sessionCourante.txCount++`,
     `if (a.engager) sessionCourante.qsoActifDx = a.engager;`, POST
     `/tx/trace {declencheur:niveau, session_id, message:a.message, ...}` ;
   - `'loguer'` : **proposer le log** (chemin `offrirLogQso`/humain existant,
     JAMAIS d'écriture auto), puis `sessionCourante.qsoActifDx = null` ;
   - `'attendre'` : rien.

- [ ] **Step 5: Vérifier l'absence de régression structurelle**

Run: `node --check concours/logx_ft8.html`? (non — HTML). À la place :
`python -m pytest concours/tests/test_ft8_copilote.py concours/tests/test_ft8_session.py concours/tests/test_invariants_securite.py -q` (les modules chargés par la page restent verts) et vérifier qu'aucun `<svg>` sans taille / chaîne brute i18n n'a été introduit (`test_i18n_dialogues`).

- [ ] **Step 6: Vérification navigateur (geste F4GLD, NON on-air)**

Page FT8 → choisir « Copilote — QSO auto » → le bandeau session apparaît →
« Autoriser » montre l'enveloppe → simuler un décode « pour moi » →
l'émission part au créneau SANS reconfirmation, `txCount` avance, la trace
apparaît dans « Journal d'émission » → **changer la bande** → bandeau rouge
« Session arrêtée : radio » → **Stop TX** coupe tout. Puis N4 : CQ émis, un
appelant simulé engagé, QSO enchaîné. Jour/nuit. **Aucune émission RF réelle
à ce stade** (bench/simulation) — l'essai on-air reste le geste séparé.

- [ ] **Step 7: Commit**

```bash
git add concours/logx_ft8.html
git commit -m "feat(ft8): UI session autonome N3/N4 + cablage boucle de decodes"
```

---

## Auto-revue (couverture spec)

- **§Niveaux N3/N4** → Task 1 (`estSessionAutonome`) + Task 8 (sélecteur).
- **§Modèle de session / validité** → Task 2 (`creerSession`/`sessionValide`,
  toutes les causes d'invalidation).
- **§N3 QSO complet** → Task 3 (`prochaineTrameQso`).
- **§N4 CQ + pile-up** → Task 4 (`prochaineAction`, réutilise file existante).
- **§Contrôle de présence (off par défaut)** → Task 5.
- **§Traçabilité (armement/arrêt + session_id)** → Task 6.
- **§Garde-fous non-négociables** → Task 2 (invalidation) + Task 7 (invariants)
  + Task 8 (Stop TX, armement humain, log humain).
- **§Continu jusqu'au Stop (pas de budget)** → aucune expiration/plafond dans
  `sessionValide` (vérifié : seule causes = stop/desarmee/cat/horloge/radio).
- **§OFF par défaut, gaté on-air** → Task 8 Step 2 (avertissement) + note
  répétée ; défaut du sélecteur reste un niveau non-autonome.
- **§Émission client + audit serveur** → Task 6 (trace) + Task 8 (émission par
  le chemin client existant).

**Scan placeholders** : chaque task porte le code réel des tests et de
l'implémentation ; les seuls « repérer la fonction existante » (append d'audit
Task 6, chemin d'émission/log Task 8) sont des points d'ancrage dans le code
EXISTANT, pas des trous de conception — l'implémenteur lit le fichier ciblé.

**Cohérence des types** : `session` porte partout `{armed, niveau,
radioEmpreinte{band,dial_hz,mode,power_w}, sessionId, txCount, qsoActifDx,
file, vu}` ; `decode = {message, snr, dx}` ; `sessionValide(...)->{ok,raison}` ;
`prochaineTrameQso(...)->{action,message,dx}` ; `prochaineAction(...)->
{action,message,dx,engager}` — identiques entre définition (Tasks 2-4) et usage
(Tasks 7-8).

## Séquencement

1 → 2 → 3 → 4 → 5 (logique pure, indépendantes après 2) ; 6 (serveur,
indépendant) ; 7 (invariants, après 2-4) ; 8 (câblage, après tout le reste).
Ordre conseillé : 1, 2, 3, 4, 5, 6, 7, 8.
