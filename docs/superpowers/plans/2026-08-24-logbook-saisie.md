# Refonte saisie LOGBOOK (sous-chantier A) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Réorganiser la fenêtre de saisie du carnet en un bandeau critique permanent + 4 onglets (QSO / Correspondant / Ma station / QSL), y rendre saisissables les champs manquants, et ajouter les tags multi-activité et les références multiples — sans jamais casser ni cacher le chemin critique.

**Architecture:** Le stockage a un schéma OUVERT (`logx_storage.py` : colonnes `_CORE` + blob `extra` JSON) → tout nouveau champ persiste sans migration. Le travail est donc côté SAISIE (`logx_logbook.html` / `logx_logbook.js`) + un module JS dédié aux onglets et aux tags pour ne pas grossir `logx_logbook.js`. Les listes de domaine sont sourcées des tables existantes. Rétro-compat : `my_refs[0]` ⇄ `my_sig`/`my_sig_info`.

**Tech Stack:** HTML/CSS/JS vanille (pas de framework), Python 3 (serveur `http.server`), tests `pytest` + `py_mini_racer` (V8) pour le JS, `ruff`. Rendu vérifié en Chrome headless (jour + nuit).

**Spec:** `docs/superpowers/specs/2026-08-24-logbook-saisie-design.md`

## Global Constraints

- **Chemin critique jamais cachable** : `inputCall`, `inputRSTsent`/`inputRSTrcvd`, `inputNumSent`/`inputNumRcvd`, sélecteurs bande/mode, `submitQSO`, nav CONFIG↔LOGBOOK restent dans le bandeau permanent, jamais `expert-only`, jamais dans un onglet.
- **Palette graphite & cuivre** ; **vérifier jour ET nuit** en navigateur avant de clore un lot touchant l'UI. Aucune règle `background:var(--accent2?)` + `color:#hex` sombre sans override `body.day-mode`.
- **Aucune valeur de domaine inventée** : listes issues de `logx_adif_enums.ADIF_MODES`, `logx_activation.PROGRAM_SPECS`, `logx_cat.MODES_*`; compléments → charger le skill `radioamateur`; sinon `VALEUR À SOURCER` dans le code.
- **Rétro-compat** : QSO existants (mono-`my_sig`, mono-`contest`) lisibles/éditables ; `my_refs[0]` recopié dans `my_sig`/`my_sig_info` à l'écriture ; l'export ADIF existant reste vert.
- **Méthode dépôt** : témoin vert AVANT toute mutation ; après correctif, remettre le défaut → le test doit ROUGIR → restaurer + md5. `pytest -p no:cacheprovider`. Écritures Python avec `newline=''`. Fichiers de test .py en LF.
- **Hors périmètre** : export ADIF (sous-chantier B) ; nouveaux décodeurs/couverture d'activités (C). A pose seulement les CLÉS de données.

---

## Design (passe impeccable — validée jour + nuit)

Refinement de l'identité graphite & cuivre (mode Operate). Langage visuel figé
par un mockup construit et **vérifié en Chrome headless dans les deux thèmes** :

- **Hiérarchie par la taille** : le chemin critique domine (indicatif mono 26px
  majuscule ; RST 22px jaune) ; le secondaire des onglets s'efface (mono 14px,
  labels 10-11px muet). C'est la hiérarchie qui rend l'écran « propre ».
- **Onglets** : pas de boîtes lourdes — bouton mono muet, actif = couleur
  `--accent` + **soulignement 2px cuivre** (`::after`). Un seul moment animé :
  fondu-montée du panneau à la bascule (`cubic-bezier(.16,1,.3,1)`).
- **Chips de tags** : AUTO = fantôme (bord `--border`, fond transparent, texte
  `--muted`) ; MANUEL = plein `--accent` + texte sombre + `×` cliquable ;
  `+ tag` = bord pointillé. Auto vs manuel distinguables d'un coup d'œil.
- **Surfaces navigateur thématisées** (signal « construit, pas assemblé ») :
  `::selection`, scrollbar (`::-webkit-scrollbar-thumb` → `--border`, hover
  `--accent`), `:focus-visible{outline:2px solid var(--accent);outline-offset:2px}`.
- **Profondeur** : ombres offset+blur (`0 18px 44px -20px rgba(0,0,0,.6)`),
  jamais de halo zéro-offset.
- **Icônes dessinées** (SVG `stroke=currentColor`), jamais d'emoji.
- **Défaut corrigé au mockup** : le N° d'échange ne tient PAS dans la rangée RST
  à la largeur mini du panneau (432px) → **N° sur sa propre rangée**
  (`numFieldRow`, concours seulement), RST envoyé/reçu = 2 colonnes.

CSS de référence (à intégrer au bloc `<style>` de `logx_logbook.html`, tokens du
thème ; c'est la cible des lots 1 et 4) :

```css
/* Onglets */
.entry-tabs{display:flex;gap:2px;margin:16px 0 0;border-bottom:1px solid var(--border)}
.entry-tab{font-family:var(--font-mono);font-size:12px;letter-spacing:1px;padding:8px 13px 9px;background:transparent;border:none;color:var(--muted);cursor:pointer;position:relative;transition:color .15s}
.entry-tab:hover{color:var(--text)}
.entry-tab.active{color:var(--accent)}
.entry-tab.active::after{content:"";position:absolute;left:9px;right:9px;bottom:-1px;height:2px;background:var(--accent);border-radius:2px 2px 0 0}
.entry-tabpane{padding:13px 2px 4px;animation:entryFade .28s cubic-bezier(.16,1,.3,1)}
@keyframes entryFade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
/* Boutons rapides RST 59/599 */
.rst-quick{display:flex;flex-direction:column;gap:4px}
.rst-quick button{font-family:var(--font-mono);font-size:11px;letter-spacing:1px;color:var(--muted);background:transparent;border:1px solid var(--border);border-radius:5px;padding:2px 8px;cursor:pointer;transition:.12s}
.rst-quick button:hover{color:var(--accent);border-color:var(--accent)}
/* Chips de tags */
.chip{font-family:var(--font-mono);font-size:11px;letter-spacing:.5px;padding:3px 9px;border-radius:999px;display:inline-flex;align-items:center;gap:5px}
.chip.auto{color:var(--muted);border:1px solid var(--border);background:transparent}
.chip.man{color:var(--bg);background:var(--accent);border:1px solid var(--accent);font-weight:700}
.chip.man .x{cursor:pointer;opacity:.7}.chip.man .x:hover{opacity:1}
.chip.add{color:var(--accent);border:1px dashed var(--border);cursor:pointer}
.chip.add:hover{border-color:var(--accent)}
/* Références multiples */
.ref-row{display:flex;gap:6px;margin-bottom:6px}
.ref-add{font-family:var(--font-mono);font-size:11px;color:var(--accent);background:transparent;border:1px dashed var(--border);border-radius:6px;padding:5px 10px;cursor:pointer}
.ref-add:hover{border-color:var(--accent)}
/* Surfaces navigateur (scoper au panneau de saisie) */
.saisie-panel ::selection{background:rgba(var(--accent-rgb),.30);color:var(--text)}
.saisie-panel ::-webkit-scrollbar{width:10px}
.saisie-panel ::-webkit-scrollbar-thumb{background:var(--border);border-radius:6px}
.saisie-panel ::-webkit-scrollbar-thumb:hover{background:var(--accent)}
.saisie-panel :focus-visible{outline:2px solid var(--accent);outline-offset:2px}
```

⚠️ **Attention `.chip.man{color:var(--bg)}`** : texte = couleur de fond du
thème sur fond cuivre plein. En JOUR le cuivre-encre (#8B4F1F) porte du texte
clair (`--bg`=#EDEAE0) → OK ; en NUIT (#E8964A) porte du texte sombre
(`--bg`=#17181A) → OK. Vérifié au mockup dans les deux thèmes ; re-vérifier si
la valeur d'accent change (piège « fond accent + texte fixe » de CLAUDE.md).

**Exigences du plancher de qualité à contrôler à chaque lot UI** : contraste
texte ≥ 4.5:1 (labels muet compris) ; états hover/focus/disabled/error/vide ;
le chemin critique reste le plus gros élément ; jour ET nuit.

---

## File Structure

- **Créer** `concours/logx_entry_tabs.js` — logique des onglets (bascule, mémorisation) + barre de tags `activity_tags` (dérivation auto + ajout/retrait manuel). Chargé dans `logx_logbook.html` après `logx_logbook.js`. Raison : ne pas grossir `logx_logbook.js` (déjà ~4100 lignes).
- **Modifier** `concours/logx_logbook.html` — envelopper les champs SECONDAIRES existants dans une coquille d'onglets ; ajouter les nouveaux champs par onglet ; ajouter boutons 59/599 ; ajouter la barre de tags.
- **Modifier** `concours/logx_logbook.js` — `submitQSO()` collecte les nouveaux champs + `my_refs`/`refs` + `activity_tags` ; auto-remplissage éditable (DXCC/zones) ; persistance `dist`/`ant_az`.
- **Modifier** `concours/logx_edit_qso.js` — la modale d'édition lit/écrit les nouvelles clés (au minimum ne les perd pas).
- **Tests** : `concours/tests/test_entry_tabs.py` (onglets + tags, py_mini_racer), `concours/tests/test_saisie_nouveaux_champs.py` (collecte/persistance des champs, py_mini_racer sur `submitQSO` extrait ou HTTP), `concours/tests/test_refs_multiples.py` (my_refs ⇄ my_sig), `concours/tests/test_activity_tags_derivation.py`.

---

## Task 1 : Coquille onglets + bandeau (sans nouveau champ)

Objectif : introduire la structure d'onglets autour des champs SECONDAIRES **existants**, le chemin critique restant dans le bandeau. Aucun champ nouveau. Non-régression totale de la saisie.

**Files:**
- Create: `concours/logx_entry_tabs.js`
- Modify: `concours/logx_logbook.html` (zone de saisie `#saisie…`, région autour de `id="inputCall"` … `id="inputComment"`)
- Test: `concours/tests/test_entry_tabs.py`

**Interfaces:**
- Produces (dans `logx_entry_tabs.js`, portée globale, appelés par la page) :
  - `entryTabSelect(name)` — affiche l'onglet `name` (`'qso'|'corr'|'mystation'|'qsl'`), mémorise `localStorage.logx_entry_tab`, marque le bouton actif.
  - `entryTabsInit()` — pose les gestionnaires de clic des `.entry-tab[data-tab]`, restaure l'onglet mémorisé (défaut `'qso'`).
- Consumes : rien (Task 1 est la base).

- [ ] **Step 1 : Lire l'existant AVANT d'éditer**

Run: `grep -nE 'id="inputCall"|id="inputComment"|saisie-secondary|saisie-panel|expert-only' concours/logx_logbook.html | head`
But: repérer la région des champs secondaires et le conteneur, pour envelopper sans déplacer le chemin critique.

- [ ] **Step 2 : Écrire le test qui échoue (structure onglets + chemin critique hors onglet)**

```python
# concours/tests/test_entry_tabs.py
import os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()
JS = open(os.path.join(BASE, 'logx_entry_tabs.js'), encoding='utf-8').read()

def _entry_zone():
    i = HTML.index('id="inputCall"')
    return HTML[i:i+8000]

def test_les_quatre_onglets_existent():
    for t in ('data-tab="qso"', 'data-tab="corr"', 'data-tab="mystation"', 'data-tab="qsl"'):
        assert t in HTML, t

def test_chemin_critique_hors_onglet():
    # inputCall/RST/submit ne sont pas dans un conteneur .entry-tabpane, ni expert-only
    z = HTML[HTML.index('id="inputCall"')-400:HTML.index('id="inputCall"')]
    assert 'entry-tabpane' not in z
    assert 'expert-only' not in z

def test_init_et_select_definis():
    assert 'function entryTabsInit(' in JS
    assert 'function entryTabSelect(' in JS
    assert "localStorage" in JS and 'logx_entry_tab' in JS
```

- [ ] **Step 3 : Vérifier que ça échoue**

Run: `python -m pytest concours/tests/test_entry_tabs.py -q -p no:cacheprovider`
Expected: FAIL (fichier `logx_entry_tabs.js` inexistant / onglets absents).

- [ ] **Step 4 : Créer `logx_entry_tabs.js` (minimal)**

```javascript
// Onglets de la fenêtre de saisie + barre de tags (sous-chantier A).
// Le chemin critique (indicatif, RST, échange, enregistrer) reste HORS onglet.
function entryTabSelect(name){
  var panes = document.querySelectorAll('.entry-tabpane');
  for (var i=0;i<panes.length;i++) panes[i].style.display = (panes[i].getAttribute('data-pane')===name)?'':'none';
  var tabs = document.querySelectorAll('.entry-tab');
  for (var j=0;j<tabs.length;j++) tabs[j].classList.toggle('active', tabs[j].getAttribute('data-tab')===name);
  try { localStorage.setItem('logx_entry_tab', name); } catch(e){}
}
function entryTabsInit(){
  var tabs = document.querySelectorAll('.entry-tab');
  for (var i=0;i<tabs.length;i++){
    tabs[i].addEventListener('click', function(){ entryTabSelect(this.getAttribute('data-tab')); });
  }
  var last = 'qso';
  try { last = localStorage.getItem('logx_entry_tab') || 'qso'; } catch(e){}
  entryTabSelect(last);
}
```

- [ ] **Step 5 : Envelopper les champs secondaires en onglets dans `logx_logbook.html`**

Ajouter la barre d'onglets + 4 conteneurs `.entry-tabpane[data-pane=...]`. Les champs secondaires EXISTANTS (locator, commentaire long, source, etc.) vont dans l'onglet approprié ; le bandeau (indicatif/RST/N°/bande/mode/enregistrer) NE bouge pas. Charger le script : ajouter `<script src="logx_entry_tabs.js"></script>` après `logx_logbook.js`, et appeler `entryTabsInit()` à l'init de la page (près de l'init logbook existante). Barre d'onglets :

```html
<div class="entry-tabs">
  <button type="button" class="entry-tab active" data-tab="qso">QSO</button>
  <button type="button" class="entry-tab" data-tab="corr">Correspondant</button>
  <button type="button" class="entry-tab" data-tab="mystation">Ma station</button>
  <button type="button" class="entry-tab" data-tab="qsl">QSL</button>
</div>
<div class="entry-tabpane" data-pane="qso"><!-- champs QSO secondaires --></div>
<div class="entry-tabpane" data-pane="corr" style="display:none"></div>
<div class="entry-tabpane" data-pane="mystation" style="display:none"></div>
<div class="entry-tabpane" data-pane="qsl" style="display:none"></div>
```

CSS : utiliser **le CSS de la section « Design » ci-dessus** (onglets à
soulignement cuivre + fondu-montée `entryFade` + surfaces navigateur), PAS des
onglets « boîtes » — le plancher de qualité refuse les bordures lourdes.

- [ ] **Step 6 : Vérifier vert**

Run: `python -m pytest concours/tests/test_entry_tabs.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 7 : Non-régression saisie**

Run: `python -m pytest concours/tests/ -q -p no:cacheprovider -k "logbook or saisie or edit_qso or macros or storage"`
Expected: PASS (adapter tout test figeant l'ancienne structure SANS l'affaiblir — préserver l'assertion, ajuster l'ancre).

- [ ] **Step 8 : Vérif navigateur jour + nuit** (harnais Chrome headless : onglets qui basculent, chemin critique visible dans les 2 thèmes). Puis **Commit**.

```bash
git add concours/logx_entry_tabs.js concours/logx_logbook.html concours/tests/test_entry_tabs.py
git commit -m "Saisie : coquille onglets + bandeau critique permanent (lot 1/6)"
```

---

## Task 2 : Champs saisissables nouveaux par onglet

Objectif : rendre saisissables puissance, e-mail, QSL via, zones CQ/ITU, état/comté, prop_mode, lieu d'exploitation, fréq RX, heure de fin, nom/QTH éditables. Persistés via le schéma ouvert.

**Files:**
- Modify: `concours/logx_logbook.html` (ajouter les inputs dans les bons `.entry-tabpane`)
- Modify: `concours/logx_logbook.js` (`submitQSO()` : lire ces inputs → clés du QSO)
- Test: `concours/tests/test_saisie_nouveaux_champs.py`

**Interfaces:**
- Consumes : conteneurs d'onglets de Task 1.
- Produces : un QSO enregistré porte désormais les clés `tx_pwr, email, qsl_via, cqz, ituz, cnty, prop_mode, operating_location, freq_rx, time_off` + `name`/`qth` éditables. `submitQSO()` inchangé de signature.

- [ ] **Step 1 : Test qui échoue — les inputs existent et sont dans le bon onglet**

```python
# concours/tests/test_saisie_nouveaux_champs.py
import os, re
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()

CHAMPS = {
  'mystation': ['inputTxPwr','inputMyRig','inputMyAntenna','inputOperatingLocation'],
  'corr': ['inputEmail','inputQslVia','inputCqz','inputItuz','inputCnty'],
  'qso': ['inputFreqRx','inputTimeOff','inputPropMode'],
}
def _pane(name):
    i = HTML.index('data-pane="%s"' % name)
    j = HTML.index('data-pane="', i+5) if HTML.find('data-pane="', i+5)!=-1 else len(HTML)
    return HTML[i:j]

def test_chaque_champ_dans_son_onglet():
    for pane, ids in CHAMPS.items():
        bloc = _pane(pane)
        for cid in ids:
            assert ('id="%s"' % cid) in bloc, (pane, cid)
```

- [ ] **Step 2 : Vérifier l'échec** — Run: `python -m pytest concours/tests/test_saisie_nouveaux_champs.py -q -p no:cacheprovider` → FAIL.

- [ ] **Step 3 : Ajouter les inputs dans `logx_logbook.html`** (dans les bons `.entry-tabpane`). Exemple onglet Ma station :

```html
<label>Puissance (W) <input type="number" id="inputTxPwr" min="0" max="2000" placeholder="ex. 20"></label>
<label>Matériel <input type="text" id="inputMyRig" placeholder="IC-7300"></label>
<label>Antenne <input type="text" id="inputMyAntenna" placeholder="Dipôle 20 m"></label>
<label>Lieu d'exploitation
  <select id="inputOperatingLocation">
    <option value="">— (fixe)</option><option value="PORTABLE">Portable</option>
    <option value="MOBILE">Mobile</option><option value="MARITIME_MOBILE">Maritime mobile</option>
    <option value="AERONAUTICAL_MOBILE">Aéronautique mobile</option><option value="REMOTE">Remote</option>
  </select></label>
```

Onglet QSO — `inputPropMode` : construire les `<option>` depuis la source de domaine (skill radioamateur / enum ADIF), pas de mémoire. Onglet Correspondant : `inputEmail`, `inputQslVia`, `inputCqz`, `inputItuz`, `inputCnty`. Styliser inputs/labels avec les classes existantes de la page.

- [ ] **Step 4 : `submitQSO()` collecte ces champs** dans `logx_logbook.js`. Repérer la construction de l'objet `q` (autour de `id: Date.now()`), ajouter :

```javascript
var _v = function(id){ var e=document.getElementById(id); return e ? e.value.trim() : ''; };
if(_v('inputTxPwr')) q.tx_pwr = Number(_v('inputTxPwr'));
['email','qsl_via','cqz','ituz','cnty','prop_mode','operating_location','freq_rx','time_off']
  .forEach(function(k){ var id='input'+k.replace(/(^|_)([a-z])/g,function(_,__,c){return c.toUpperCase();});
    var val=_v(id); if(val) q[k]=val; });
```
(Vérifier que les `id` générés correspondent à ceux du HTML ; sinon lister explicitement le mapping id→clé.)

- [ ] **Step 5 : Test de persistance (aller-retour)** — étendre le test : un QSO construit avec ces champs, sérialisé via le chemin serveur (`logx_storage`), relu → mêmes valeurs. (Réutiliser le harnais de `test_storage.py`.)

- [ ] **Step 6 : Vert + non-régression** — Run les tests du lot + `-k "logbook or storage or export"`. Adapter sans affaiblir.

- [ ] **Step 7 : Vérif navigateur jour+nuit** des 4 onglets remplis. **Commit** `Saisie : champs saisissables nouveaux par onglet (lot 2/6)`.

---

## Task 3 : Références multiples (`my_refs` / `refs`) + rétro-compat `my_sig`

**Files:**
- Modify: `concours/logx_logbook.html` (onglets Ma station & Correspondant : UI liste de références `{programme, valeur}`)
- Modify: `concours/logx_logbook.js` (collecte `my_refs`/`refs`, recopie `my_refs[0]`→`my_sig`)
- Modify: `concours/logx_edit_qso.js` (lecture rétro-compat)
- Test: `concours/tests/test_refs_multiples.py`

**Interfaces:**
- Produces : QSO porte `my_refs` = `[{program, ref}, …]` et `refs` idem ; helpers globaux `refsToMySig(q)` (écrit `my_sig`/`my_sig_info` depuis `my_refs[0]`) et `mySigToRefs(q)` (synthétise `my_refs` depuis `my_sig` si absent).

- [ ] **Step 1 : Test rétro-compat (aller-retour my_sig ⇄ my_refs)**

```python
# concours/tests/test_refs_multiples.py — py_mini_racer sur les helpers extraits
import os, re, json, pytest
py_mini_racer = pytest.importorskip('py_mini_racer')
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE,'logx_logbook.js'),encoding='utf-8').read()
def _fn(name):
    m=re.search(r'^function %s\(' % name, JS, re.M); assert m, name
    d=0;i=JS.index('{',m.start())
    while True:
        if JS[i]=='{':d+=1
        elif JS[i]=='}':
            d-=1
            if d==0:return JS[m.start():i+1]
        i+=1
def _ctx():
    c=py_mini_racer.MiniRacer(); c.eval(_fn('refsToMySig')); c.eval(_fn('mySigToRefs')); return c
def test_my_sig_vers_refs():
    c=_ctx()
    q=json.loads(c.eval("(function(){var q={my_sig:'POTA',my_sig_info:'FR-1234'};mySigToRefs(q);return JSON.stringify(q);})()"))
    assert q['my_refs']==[{'program':'POTA','ref':'FR-1234'}]
def test_refs_vers_my_sig_premier():
    c=_ctx()
    q=json.loads(c.eval("(function(){var q={my_refs:[{program:'SOTA',ref:'F/AB-1'},{program:'POTA',ref:'FR-2'}]};refsToMySig(q);return JSON.stringify(q);})()"))
    assert q['my_sig']=='SOTA' and q['my_sig_info']=='F/AB-1'
```

- [ ] **Step 2 : Échec** — Run pytest → FAIL (helpers absents).

- [ ] **Step 3 : Implémenter les helpers** dans `logx_logbook.js` :

```javascript
function mySigToRefs(q){
  if((!q.my_refs || !q.my_refs.length) && q.my_sig){ q.my_refs=[{program:q.my_sig, ref:q.my_sig_info||''}]; }
  if((!q.refs || !q.refs.length) && q.sig){ q.refs=[{program:q.sig, ref:q.sig_info||''}]; }
  return q;
}
function refsToMySig(q){
  if(q.my_refs && q.my_refs.length){ q.my_sig=q.my_refs[0].program; q.my_sig_info=q.my_refs[0].ref; }
  if(q.refs && q.refs.length){ q.sig=q.refs[0].program; q.sig_info=q.refs[0].ref; }
  return q;
}
```

- [ ] **Step 4 : Vert** — pytest test_refs_multiples → PASS.

- [ ] **Step 5 : UI liste de références** (onglet Ma station : `#myRefsList` + bouton `+ référence` ; programme = `<select>` sourcé de `PROGRAM_SPECS`, valeur = input). `submitQSO()` : construire `q.my_refs` depuis la liste puis appeler `refsToMySig(q)` avant l'envoi. Idem correspondant (`#refsList`).

- [ ] **Step 6 : `logx_edit_qso.js`** appelle `mySigToRefs(q)` à l'ouverture (affiche la liste), `refsToMySig(q)` à l'enregistrement.

- [ ] **Step 7 : Non-régression export** — Run `-k "export or pota or activation or import"` : l'export ADIF actuel (`MY_SIG`/`MY_SIG_INFO`) reste identique grâce à `refsToMySig`. **Contre-épreuve par mutation** sur `refsToMySig` (casser la recopie → export/test rougit). **Commit** `Saisie : références multiples + rétro-compat my_sig (lot 3/6)`.

---

## Task 4 : Barre de tags `activity_tags` (auto + manuel)

**Files:**
- Modify: `concours/logx_entry_tabs.js` (dérivation + rendu barre de tags)
- Modify: `concours/logx_logbook.html` (conteneur `#activityTags` + `#addTagBtn`)
- Modify: `concours/logx_logbook.js` (`submitQSO()` : `q.activity_tags`)
- Test: `concours/tests/test_activity_tags_derivation.py`

**Interfaces:**
- Produces (dans `logx_entry_tabs.js`) : `deriveActivityTags(q)` → renvoie la liste des tags AUTO d'après le QSO ; `mergeTags(auto, manuels)` → union sans doublon, préserve les manuels.

- [ ] **Step 1 : Test de dérivation**

```python
# concours/tests/test_activity_tags_derivation.py — py_mini_racer sur deriveActivityTags
import os, re, json, pytest
py_mini_racer=pytest.importorskip('py_mini_racer')
BASE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS=open(os.path.join(BASE,'logx_entry_tabs.js'),encoding='utf-8').read()
def _fn(n):
    m=re.search(r'function %s\('%n,JS);d=0;i=JS.index('{',m.start())
    while True:
        if JS[i]=='{':d+=1
        elif JS[i]=='}':
            d-=1
            if d==0:return JS[m.start():i+1]
        i+=1
def _tags(qjson):
    c=py_mini_racer.MiniRacer();c.eval(_fn('deriveActivityTags'))
    return json.loads(c.eval("JSON.stringify(deriveActivityTags(%s))"%qjson))
def test_mode_devient_tag():
    assert 'FT8' in _tags('{"mode":"FT8"}')
def test_qrp_depuis_puissance():
    assert 'QRP' in _tags('{"mode":"CW","tx_pwr":5}')
    assert 'QRP' not in _tags('{"mode":"CW","tx_pwr":100}')
def test_sota_depuis_reference():
    assert 'SOTA' in _tags('{"mode":"SSB","my_refs":[{"program":"SOTA","ref":"F/AB-1"}]}')
def test_portable_depuis_lieu():
    assert 'PORTABLE' in _tags('{"mode":"SSB","operating_location":"PORTABLE"}')
```

- [ ] **Step 2 : Échec** → FAIL.

- [ ] **Step 3 : `deriveActivityTags` + `mergeTags`** dans `logx_entry_tabs.js`. Le seuil QRP (5 W) et le seuil DX sont des valeurs de domaine → constantes commentées `// SOURCE:` (skill radioamateur), pas de mémoire ; si non sourcé au moment d'écrire, laisser le tag DX hors dérivation avec un `// VALEUR À SOURCER`.

```javascript
function deriveActivityTags(q){
  var t=[];
  if(q.mode) t.push(String(q.mode).toUpperCase());
  if(q.tx_pwr!=null && Number(q.tx_pwr)>0 && Number(q.tx_pwr)<=5) t.push('QRP'); // 5 W : SOURCE skill radioamateur
  (q.my_refs||[]).concat(q.refs||[]).forEach(function(r){ if(r&&r.program) t.push(String(r.program).toUpperCase()); });
  if(q.operating_location && q.operating_location!=='HOME') t.push(q.operating_location);
  if(q.prop_mode) t.push(String(q.prop_mode).toUpperCase());
  if(q.sat_name) t.push('SAT');
  // DX : dépend d'un seuil de distance — VALEUR À SOURCER (heuristique DX existante 3000/8000 km)
  return t.filter(function(v,i,a){return a.indexOf(v)===i;});
}
function mergeTags(auto, manuels){
  var out=(manuels||[]).slice();
  (auto||[]).forEach(function(x){ if(out.indexOf(x)===-1) out.push(x); });
  return out;
}
```

- [ ] **Step 4 : Vert** → PASS.

- [ ] **Step 5 : Barre de tags UI** (`#activityTags` sous les onglets) : rendre les tags (chips), `+` pour ajouter un tag manuel (mémorisé à part `q._manual_tags`), clic sur un chip manuel = retirer. `submitQSO()` : `q.activity_tags = mergeTags(deriveActivityTags(q), manuels)`.

- [ ] **Step 6 : Recherche** — brancher `activity_tags` dans le filtre existant du carnet (`filterLog()`), pour retrouver un QSO par tag. Test : un QSO taggé `SOTA` ressort en filtrant `SOTA`.

- [ ] **Step 7 : Vérif navigateur jour+nuit** (chips lisibles, manuel vs auto distinguables). **Commit** `Saisie : tags multi-activité auto+manuel + recherche (lot 4/6)`.

---

## Task 5 : Auto-remplissage éditable + persistance des calculs

**Files:**
- Modify: `concours/logx_logbook.js` (remplir DXCC/pays/continent/zones depuis indicatif+locator ; persister `dist`/`ant_az`)
- Test: étendre `concours/tests/test_saisie_nouveaux_champs.py`

**Interfaces:**
- Consumes : `lookupDXCC` (existant), `bearing`/`calcDist` (existants).
- Produces : à la saisie, `q.dxcc`, `q.country`, `q.cont`, `q.cqz`, `q.ituz`, `q.ant_az` sont renseignés (éditables), `q.dist` persisté.

- [ ] **Step 1 : Test** — un QSO avec indicatif+locator connus produit `q.ant_az` (azimut) et `q.dxcc` non vides après `submitQSO`. (py_mini_racer avec `lookupDXCC`/`bearing` stubés, OU test HTTP.)

- [ ] **Step 2 : Échec** → FAIL (azimut/dxcc pas encore écrits sur le QSO).

- [ ] **Step 3 : Implémenter** dans `submitQSO()` : après calcul distance existant, `q.ant_az = Math.round(bearing(q.locator))`; renseigner `q.dxcc/country/cont/cqz/ituz` depuis les lookups SI les champs correspondants sont vides (respecter une saisie manuelle : ne pas écraser une valeur éditée). Les zones auto : uniquement si `lookupDXCC` fournit CQ/ITU ; sinon laisser vide (pas d'invention).

- [ ] **Step 4 : Vert** → PASS.

- [ ] **Step 5 : Champs auto affichés mais éditables** — les inputs `inputCqz/inputItuz` (Task 2) sont pré-remplis à la frappe de l'indicatif/locator (event existant qui met à jour le badge DXCC), sans verrouiller.

- [ ] **Step 6 : Non-régression** `-k "logbook or export or storage"`. **Commit** `Saisie : auto-remplissage éditable + persistance azimut/DXCC (lot 5/6)`.

---

## Task 6 : Onglet QSL + polissage densité/mobile + vérif finale

**Files:**
- Modify: `concours/logx_logbook.html` (onglet QSL : statuts lus de `logx_qsl.py`)
- Modify: `concours/logx_logbook.js` (afficher l'état QSL/LoTW/eQSL du QSO édité)
- Test: `concours/tests/test_entry_tabs.py` (présence onglet QSL peuplé)

- [ ] **Step 1 : Test** — l'onglet QSL contient des champs `qsl_sent/qsl_rcvd/lotw_qsl_rcvd/eqsl` (au moins présents en lecture). Ajouter à `test_entry_tabs.py`.

- [ ] **Step 2 : Échec** → FAIL.

- [ ] **Step 3 : Peupler l'onglet QSL** (affichage statut env/reçu séparés ; les confirmations viennent de `qsl_confirmations.json` via l'endpoint existant — ne PAS ré-exporter ADIF ici, c'est B). Champs éditables : `qsl_sent`, `qsl_via` (déjà en corr), dates.

- [ ] **Step 4 : Vert** → PASS.

- [ ] **Step 5 : Densité / mobile** — vérifier ≤ 1100 px que les onglets restent utilisables (le band map se masque déjà) ; pas de `align-items:center` dans un conteneur scrollable (piège CLAUDE.md).

- [ ] **Step 6 : Vérif navigateur FINALE jour+nuit** des 4 onglets + bandeau + tags, sur une instance statique isolée. `ruff` E9,F. Suite large `-k "logbook or saisie or entry or refs or tags or storage or export or edit_qso"` verte.

- [ ] **Step 7 : Commit + PR**

```bash
git add -A concours/
git commit -m "Saisie : onglet QSL + polissage densité/mobile (lot 6/6)"
git push -u origin <branche>
gh pr create --title "Refonte saisie LOGBOOK (A) : bandeau + onglets + tags + refs multiples"
```

---

## Self-review (fait par l'auteur du plan)

- **Couverture spec** : §4 mise en page → T1 ; §5 champs par onglet → T2/T6 ; §5 tags → T4 ; §5/§6 refs multiples → T3 ; §5 auto-remplissage + calculs persistés → T5 ; §5 onglet QSL → T6 ; §9 tests → chaque tâche ; §3 contraintes → Global Constraints. **Pas de section orpheline.**
- **Placeholders** : les seuls `VALEUR À SOURCER` sont des valeurs de domaine à sourcer via le skill radioamateur (règle du dépôt), signalées comme telles dans le code — pas des TODO de plan.
- **Cohérence des types** : `my_refs`/`refs` = `[{program, ref}]` partout ; `deriveActivityTags(q)`/`mergeTags(auto,manuels)`/`refsToMySig`/`mySigToRefs` nommés identiquement entre définition (T3/T4) et usage (`submitQSO`, edit).
