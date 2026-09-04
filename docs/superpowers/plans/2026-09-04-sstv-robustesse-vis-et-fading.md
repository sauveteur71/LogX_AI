# SSTV — Robustesse acquisition VIS + banc à fading — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fiabiliser l'acquisition de l'en-tête VIS sous bruit et fading (le vrai genou du décrochage signal faible), modéliser le fading QSB pour pouvoir le MESURER, et tenir l'image pendant un évanouissement — sans régresser les modes existants ni toucher au chemin d'émission.

**Architecture :** Tout côté navigateur dans `concours/logx_sstvdecoder.js` (décodeur + encodeur, comme le RTTY). F1 étend le banc `test_sstv_robustesse.py` (fading Rayleigh plat + sweep 2D). F2 remplace les décisions à seuil dur de l'acquisition VIS par des décisions par **énergie glissante** (DFT-bin, généralisation du Goertzel corrélé d'A3) + **décision douce** des bits VIS avec correction guidée par la parité. F3 ajoute un **squelch** piloté par `this._lastAmpl` (exposé par A1) qui gèle le recalage de synchro et tient le pixel pendant un fade. F2 et F3 sont **gatés par option** (défaut activé) pour rester mesurables A/B et contre-épreuvables par mutation, comme A2/A3.

**Tech Stack :** JavaScript vanille (navigateur), tests pytest + `py_mini_racer` (MiniRacer exécute le JS ; frontière JS→Python par `JSON.stringify`).

**Spec :** `docs/superpowers/specs/2026-09-04-sstv-robustesse-vis-et-fading-design.md`

## Global Constraints

- **Un témoin vert AVANT toute mutation.** Après chaque correctif, remettre le défaut, vérifier que le test ROUGIT, restaurer. Contre-épreuve par mutation obligatoire. (règle du dépôt)
- **Tests structurels/comportementaux, pas de présence de chaîne.**
- **Branches OFF bit-à-bit.** Chaque option (`acqVisRobuste`, `squelchFade`) à `false` reproduit le comportement historique à l'octet près (garde A/B).
- **Options par défaut activées** (comme `estimPixel:'ponderee'`, `syncCorrelation:true`).
- 🚨 **Zéro faux positif VIS.** Durcir l'acquisition ne doit JAMAIS augmenter les VIS acceptés à tort : parité paire + bit de stop restent des gardes. La correction guidée par la parité ne corrige qu'UNE erreur unique (un retournement) ; au-delà, rejet. Un test dédié le verrouille.
- **Ordre F1 → F2 → F3** : le banc d'abord (mesurer avant de toucher — sans lui « c'est mieux » est invérifiable).
- **Honnêteté (règle du dépôt) :** un levier sans gain mesuré est REJETÉ (comme A1), pas gardé. Bilan chiffré à la fin.
- **Chemin TX intouché** : `logx_tx_audio.js`, PTT, CAT, table des modes.
- **`FS = 11025`** pour les tests (comme le banc actuel).
- **Consulter la fiche mémoire « pièges py_mini_racer »** avant tout test JS.
- **Réponse à F4GLD en français.**

## File Structure

- `concours/logx_sstvdecoder.js` (MODIFIER) — F2 : helper `EnergieGlissante` (généralise le Goertzel d'A3), buffers d'acquisition dans le constructeur, `raw` passé aux fonctions d'acquisition, `_chercherLeader`/`_verifierStart`/`_lireBitsVis` re-câblés énergie + décision douce. F3 : squelch sur `_lastAmpl` dans le recalage de synchro et `_finaliserCellule`. Options `acqVisRobuste` + `squelchFade`.
- `concours/tests/test_sstv_robustesse.py` (MODIFIER) — F1 : `fadingRayleighPlat` + `mesureSnr` acceptant `tauxFading` + sweep 2D + baseline. F2 : tests d'acquisition VIS (gain + anti-faux-positif). F3 : test image sous fade. Consolidation : non-régression AWGN/clair + bilan.
- **Non modifié** : `logx_tx_audio.js`, chemin PTT/CAT, `SSTV_MODES`.

---

## Task 0 : F1 — Banc à fading Rayleigh plat + sweep 2D + baseline

**Files:**
- Test : `concours/tests/test_sstv_robustesse.py` (modifier — aucune modif décodeur)

**Interfaces:**
- Produit : JS `fadingRayleighPlat(sig, tauxHz, graine)` ; `mesureSnr(nomMode, snrDb, opts)` accepte `opts.tauxFading` (Hz, 0 = pas de fading) ; Python `_surface(moteur, mode, snrs, tauxList, opts)` → liste de `{snr, taux, mode, mae, acquis}` ; `acquis` = mode correctement détecté (VIS acquis).
- Consomme : `bruitGaussienSnr`, `mesureSnr`, `sstvEncodeSamples`, `FS` (existants).

- [ ] **Step 1 : Écrire le test du banc fading (témoin) + helper**

Ajouter à l'éval de fixture de `test_sstv_robustesse.py` :

```javascript
// Fading Rayleigh PLAT : enveloppe = module d'un processus gaussien complexe
// filtre passe-bas au taux de fading (Doppler). Band-limite par un filtre 1 pole
// de coupure tauxHz -> correlation temporelle d'un vrai QSB (taux petit = fading
// lent). Enveloppe normalisee en puissance moyenne unite (le fading redistribue
// la puissance, il ne l'ajoute pas). Graine fixe = reproductible (comme
// bruitGaussienSnr). fs = FS injecte cote Python.
function fadingRayleighPlat(sig, tauxHz, graine){
  var s = graine || 1;
  function g(){
    s=(s*1103515245+12345)&0x7fffffff; var u1=(s/0x7fffffff)||1e-9;
    s=(s*1103515245+12345)&0x7fffffff; var u2=(s/0x7fffffff);
    return Math.sqrt(-2*Math.log(u1))*Math.cos(2*Math.PI*u2);
  }
  var a = 1 - Math.exp(-2*Math.PI*tauxHz/FS);   // 1 pole a tauxHz
  var fi=0, fq=0, env=new Float32Array(sig.length), p=0;
  for(var i=0;i<sig.length;i++){
    fi += (g()-fi)*a; fq += (g()-fq)*a;         // I/Q gaussiens filtres
    var e = Math.sqrt(fi*fi+fq*fq);             // enveloppe Rayleigh
    env[i]=e; p += e*e;
  }
  var rms = Math.sqrt(p/sig.length) || 1e-9;
  var out = new Float32Array(sig.length);
  for(var i=0;i<sig.length;i++) out[i] = sig[i]*(env[i]/rms);
  return out;
}
```

Étendre `mesureSnr` pour appliquer le fading AVANT le bruit :

```javascript
function mesureSnr(nomMode, snrDb, opts){
  opts = opts || {};
  var m = SSTV_MODES_PAR_NOM[nomMode];
  var px = imageTestSstv(m.largeur, m.hauteur);
  var lignes = opts.lignes || null;
  var sig = sstvEncodeSamples({mode:nomMode, pixels:px, sampleRate:FS, lignes:lignes});
  if(opts.tauxFading) sig = fadingRayleighPlat(sig, opts.tauxFading, 13);   // fading AVANT le bruit
  sig = bruitGaussienSnr(sig, snrDb, 7);
  var d = sstvDecodeSamples(sig, Object.assign({sampleRate:FS}, opts.dec||{}));
  var r = d.resume();
  r.snr = snrDb; r.taux = opts.tauxFading || 0;
  r.acquis = (r.mode === nomMode);   // le VIS a-t-il ete acquis (bon mode) ?
  r.mae = (r.acquis && r.lignesEmises>0) ? maeSstv(d, px, m.largeur, r.lignesEmises) : null;
  return r;
}
```

Ajouter le témoin Python :

```python
def _surface(moteur, mode, snrs, taux_list, opts=None):
    """Surface (SNR x taux de fading) : chaque point = mesureSnr avec ce fading."""
    base = opts or {}
    out = []
    for t in taux_list:
        for s in snrs:
            o = dict(base); o['tauxFading'] = t
            js = 'JSON.stringify(mesureSnr(%s, %s, %s))' % (
                json.dumps(mode), json.dumps(s), json.dumps(o))
            out.append(json.loads(moteur.eval(js)))
    return out


def test_banc_fading_temoin(moteur):
    """Témoin du modèle de fading : à SNR clair (30 dB), un fading LENT (0.2 Hz)
    laisse l'image acquise et exploitable ; un fading combiné à un SNR bas
    dégrade (surface non triviale). Sans ce témoin, un fading cassé (enveloppe
    constante) se lirait comme une protection parfaite (règle du dépôt)."""
    pts = _surface(moteur, 'R36', [30], [0, 0.2, 1.0], {'lignes': 16})
    clair = next(p for p in pts if p['snr'] == 30 and p['taux'] == 0)
    assert clair['acquis'] and clair['mae'] is not None
    lent = next(p for p in pts if p['snr'] == 30 and p['taux'] == 0.2)
    assert lent['acquis'], 'fading lent à SNR clair ne devrait pas empêcher l’acquisition'
    # le fading DOIT avoir un effet mesurable quelque part (sinon enveloppe inerte)
    maes = [p['mae'] for p in pts if p['mae'] is not None]
    assert len(set(round(x, 1) for x in maes)) > 1, 'le fading n’a aucun effet — enveloppe constante ?'
```

- [ ] **Step 2 : Lancer, vérifier vert**

Run : `python -m pytest concours/tests/test_sstv_robustesse.py::test_banc_fading_temoin -v`
Expected : PASS.

- [ ] **Step 3 : Contre-épreuve du banc**

Muter `fadingRayleighPlat` pour renvoyer `sig` inchangé → `test_banc_fading_temoin` doit rougir sur `set(...) > 1` (le fading n'a plus d'effet). Restaurer, revérifier vert.

- [ ] **Step 4 : Mesurer et consigner la baseline 2D**

Ajouter un test qui imprime la surface `(SNR × fading)` de quelques modes aux DÉFAUTS actuels (acquisition VIS non encore modifiée) et fige lâchement (acquisition en clair) :

```python
@pytest.mark.parametrize('mode', ['M1', 'S1', 'R36', 'PD90'])
def test_baseline_2d_actuelle(moteur, mode, capsys):
    """Baseline (SNR x fading) AVANT F2/F3. Assertion lâche : acquis en clair sans
    fading. Journalise la surface (acquisition + MAE) — point de départ des mesures A/B."""
    snrs = [30, 21, 15, 12, 9, 6]
    pts = _surface(moteur, mode, snrs, [0, 0.2, 1.0], {'lignes': 24})
    clair = next(p for p in pts if p['snr'] == 30 and p['taux'] == 0)
    assert clair['acquis']
    with capsys.disabled():
        for t in [0, 0.2, 1.0]:
            ligne = [(p['snr'], p['acquis'], None if p['mae'] is None else round(p['mae'],1))
                     for p in pts if p['taux'] == t]
            print('\\nBASELINE %-5s fading=%.1fHz : %s' % (mode, t, ligne))
```

Run avec `-s`, copier les surfaces dans un commentaire daté en tête du fichier — la **baseline chiffrée** dont dépendent F2/F3.

- [ ] **Step 5 : Commit**

```bash
git add concours/tests/test_sstv_robustesse.py
git commit -m "test(sstv): banc a fading Rayleigh plat + sweep 2D (SNR x fading) + baseline"
```

---

## Task 1 : F2a — Énergie glissante d'acquisition + leader par énergie

**Files:**
- Modifier : `concours/logx_sstvdecoder.js` (constructeur ~L334 ; `pousser` L452-457 ; `_chercherLeader` L464-475 ; nouveau helper `EnergieGlissante`)
- Test : `concours/tests/test_sstv_robustesse.py`

**Interfaces:**
- Produit : option de constructeur `acqVisRobuste` (booléen, **défaut `true`**). Helper `EnergieGlissante(freqHz, nFenetre, sampleRate)` avec `pousser(x)→énergie`. Buffers d'acquisition dans le constructeur (instances pour 1900/1200/1100/1300 Hz). `pousser` passe le sample brut aux fonctions d'acquisition. Leader détecté par énergie soutenue à 1900 Hz quand `acqVisRobuste`.
- Consomme : `this.sampleRate`, l'état d'acquisition existant.

- [ ] **Step 1 : Écrire le test comparatif (échoue tant que l'option n'existe pas)**

```python
def _taux_acquisition(moteur, mode, snrs, taux, dec):
    """Fraction des points (sur les SNR donnés, à ce taux de fading) où le VIS est
    acquis (bon mode). Mesure directe et mutation-sensible de la robustesse
    d'acquisition."""
    pts = _surface(moteur, mode, snrs, [taux], {'lignes': 12, 'dec': dec})
    return sum(1 for p in pts if p['acquis']) / max(1, len(pts))


def test_f2_option_acq_est_bien_cablee(moteur, capsys):
    """L'option acqVisRobuste a un effet réel sur l'acquisition (sinon option
    morte). Journalise le taux d'acquisition on vs off."""
    snrs = [12, 10, 8, 6, 4]
    on  = _taux_acquisition(moteur, 'R36', snrs, 0.0, {'acqVisRobuste': True})
    off = _taux_acquisition(moteur, 'R36', snrs, 0.0, {'acqVisRobuste': False})
    with capsys.disabled():
        print('\\nF2 R36 acquisition on=%.2f off=%.2f' % (on, off))
    assert on != off, 'acqVisRobuste sans effet sur l’acquisition — option morte ?'


def test_f2_ne_regresse_pas_l_acquisition_en_clair(moteur):
    """À SNR clair, l'acquisition robuste ne doit pas rater ce que l'historique
    acquiert : au moins aussi bon à 30 dB sans fading."""
    for mode in ['M1', 'S1', 'R36', 'PD90']:
        on  = _surface(moteur, mode, [30], [0], {'lignes': 12, 'dec': {'acqVisRobuste': True}})[0]
        off = _surface(moteur, mode, [30], [0], {'lignes': 12, 'dec': {'acqVisRobuste': False}})[0]
        assert on['acquis'] and off['acquis'], '%s : acquisition en clair perdue' % mode
```

- [ ] **Step 2 : Lancer, vérifier l'ÉCHEC**

Run : `python -m pytest concours/tests/test_sstv_robustesse.py -k f2_option -v`
Expected : FAIL (option `acqVisRobuste` absente → on == off).

- [ ] **Step 3 : Implémenter le helper `EnergieGlissante` + l'option + le leader par énergie**

Ajouter le helper (avant la classe `SstvDecodeur`, à côté des fonctions de mode) :

```javascript
// Énergie glissante à UNE fréquence (bin DFT sur fenêtre glissante). Généralise
// le Goertzel corrélé d'A3 (_suivreCorr) en composant autonome et paramétré :
// plusieurs instances tournent pendant l'ACQUISITION VIS (1900/1200/1100/1300),
// AVANT qu'une image existe (les buffers _corr* d'A3 sont, eux, image-scoped).
function EnergieGlissante(freqHz, nFenetre, sampleRate){
  this.w = 2 * Math.PI * freqHz / sampleRate; this.ph = 0;
  this.n = Math.max(3, nFenetre | 0);
  this.ringC = new Float32Array(this.n); this.ringS = new Float32Array(this.n);
  this.sc = 0; this.ss = 0; this.idx = 0;
}
EnergieGlissante.prototype.pousser = function(x){
  const c = Math.cos(this.ph), s = Math.sin(this.ph);
  this.ph += this.w; if(this.ph > 2 * Math.PI) this.ph -= 2 * Math.PI;
  const kc = x * c, ks = x * s, i = this.idx;
  this.sc += kc - this.ringC[i]; this.ss += ks - this.ringS[i];
  this.ringC[i] = kc; this.ringS[i] = ks;
  this.idx = (i + 1) % this.n;
  return (this.sc * this.sc + this.ss * this.ss) / (this.n * this.n);   // énergie normalisée
};
```

Constructeur : lire l'option + créer les estimateurs d'acquisition (fenêtre courte, ~10 ms, pour suivre le leader/start/bits) :

```javascript
constructor({sampleRate = 44100, /* … */, estimPixel = 'ponderee',
             syncCorrelation = true, acqVisRobuste = true} = {}){
  // …existant…
  this._acqVisRobuste = acqVisRobuste;
  // Estimateurs d'énergie d'acquisition VIS (fenêtre ~10 ms = 2 tiers d'un bit
  // VIS de 30 ms, compromis intégration/réactivité). Créés seulement si l'option
  // est active, pour ne rien coûter en OFF.
  if(acqVisRobuste){
    const nAcq = Math.max(3, Math.round(0.010 * sampleRate));
    this._eLeader = new EnergieGlissante(1900, nAcq, sampleRate);
    this._eSync   = new EnergieGlissante(1200, nAcq, sampleRate);
    this._eUn     = new EnergieGlissante(1100, nAcq, sampleRate);   // bit = 1
    this._eZero   = new EnergieGlissante(1300, nAcq, sampleRate);   // bit = 0
  }
}
```

`pousser` : passer le sample brut aux fonctions d'acquisition (le `f` reste calculé pour la branche OFF et l'image) :

```javascript
pousser(samples){
  for(let i = 0; i < samples.length; i++){
    const f = this._freq(samples[i]);
    this._n++;
    if(this._etat === 'leader')          this._chercherLeader(f, samples[i]);
    else if(this._etat === 'vis-start')  this._verifierStart(f, samples[i]);
    else if(this._etat === 'vis-bits')   this._lireBitsVis(f, samples[i]);
    else                                 this._decoderImage(f, samples[i]);
  }
}
```

`_chercherLeader` : branche énergie quand l'option est active (leader = énergie 1900 Hz > énergie 1200 Hz, soutenue) ; sinon historique bit-à-bit :

```javascript
_chercherLeader(f, raw){
  if(this._acqVisRobuste){
    const e1900 = this._eLeader.pousser(raw);
    const e1200 = this._eSync.pousser(raw);
    this._eUn.pousser(raw); this._eZero.pousser(raw);   // maintenir toutes les phases
    // Leader présent = énergie 1900 domine nettement. On accumule un compteur
    // (comme l'historique) mais sur une DÉCISION D'ÉNERGIE, pas un seuil de f
    // instantané : robuste au bruit (intègre) et au fading (l'énergie chute avec).
    if(e1900 > 2 * e1200 && e1900 > this._eSeuilLeader()){
      this._leaderEch++;
    } else if(e1200 > 2 * e1900 && this._leaderEch > 0.1 * this.sampleRate){
      this._etat = 'vis-start'; this._visDebut = this._n;
      this._visAcc = 0; this._visCnt = 0; this._leaderEch = 0;
    } else {
      this._leaderEch = Math.max(0, this._leaderEch - 4);
    }
    return;
  }
  // ── branche OFF : historique bit-à-bit, INCHANGÉE ──
  if(Math.abs(f - 1900) < 75){ this._leaderEch++; }
  else if(f < 1400 && this._leaderEch > 0.1 * this.sampleRate){
    this._etat = 'vis-start'; this._visDebut = this._n;
    this._visAcc = 0; this._visCnt = 0; this._leaderEch = 0;
  } else { this._leaderEch = Math.max(0, this._leaderEch - 4); }
}
```

`_eSeuilLeader()` : un seuil d'énergie relatif au signal reçu — À CONCEVOIR par l'implémenteur (ex. fraction d'une énergie de référence mise à jour, ou seuil absolu bas puisque l'énergie est normalisée par la fenêtre). Documenter le choix ; le mesurer (Step 4). Si un seuil relatif s'avère nécessaire, suivre une énergie max récente. ⚠️ Ne pas inventer une valeur « magique » sans la mesurer.

> ⚠️ Cette tâche porte le cœur DSP de F2. Si la conception du seuil de leader dérape, la découper : 1a = helper + estimateurs + câblage `raw` (sans changer la décision), 1b = décision d'énergie du leader. Ne pas mélanger avec F2b.

- [ ] **Step 4 : Lancer, mesurer, PASS**

Run : `python -m pytest concours/tests/test_sstv_robustesse.py -k f2 -v -s`
Expected : PASS. Relever le taux d'acquisition on vs off. **Décision keep/reject** : garder si l'acquisition tient au moins aussi bien en clair ET progresse sous bruit ; sinon documenter (le gain principal peut venir de F2b, les bits).

- [ ] **Step 5 : Contre-épreuve par mutation**

Forcer la branche énergie du leader à ne jamais transiter (ex. `if(false && e1200 > 2*e1900 …)`) → un test d'acquisition doit rougir. Restaurer.

- [ ] **Step 6 : Non-régression des modes existants (AWGN + clair)**

Run : `python -m pytest concours/tests/test_sstv_decodeur.py -v`
Expected : PASS intégral (le défaut `acqVisRobuste:true` ne doit pas casser l'aller-retour des modes en clair). Toute régression = défaut réel à traiter.

- [ ] **Step 7 : Commit**

```bash
git add concours/logx_sstvdecoder.js concours/tests/test_sstv_robustesse.py
git commit -m "feat(sstv): F2a acquisition VIS — energie glissante + leader par energie (option)"
```

---

## Task 2 : F2b — Start par énergie + bits VIS en décision douce + correction parité

**Files:**
- Modifier : `concours/logx_sstvdecoder.js` (`_verifierStart` L482-496 ; `_lireBitsVis` L502-534)
- Test : `concours/tests/test_sstv_robustesse.py`

**Interfaces:**
- Consomme : `this._acqVisRobuste`, `this._eSync`/`_eUn`/`_eZero` (Task 1). 
- Produit : décision de start par énergie 1200 Hz ; par créneau VIS, décision douce (énergie 1100 vs 1300) + confiance ; correction guidée par la parité (un retournement du bit le moins sûr). Garde anti-faux-positif inchangée (parité + stop).

- [ ] **Step 1 : Écrire les tests (gain bits + anti-faux-positif)**

```python
def test_f2b_gain_acquisition_sous_bruit(moteur, capsys):
    """Sous bruit (sans fading), l'acquisition robuste complète (leader+start+bits
    doux) acquiert le VIS à un SNR plus bas que l'historique. On mesure le SNR le
    plus bas encore acquis, on vs off."""
    snrs = [14, 12, 10, 8, 6, 4, 2]
    def snr_min_acquis(dec):
        pts = _surface(moteur, 'R36', snrs, [0], {'lignes': 10, 'dec': dec})
        ok = [p['snr'] for p in pts if p['acquis']]
        return min(ok) if ok else None
    on  = snr_min_acquis({'acqVisRobuste': True})
    off = snr_min_acquis({'acqVisRobuste': False})
    with capsys.disabled():
        print('\\nF2b R36 SNR min acquis on=%s off=%s' % (on, off))
    assert on is not None, 'acquisition robuste n’acquiert jamais — cassée ?'


def test_f2b_pas_de_faux_positif_vis(moteur):
    """🚨 Durcir l'acquisition ne doit JAMAIS accepter un VIS à parité
    structurellement fausse. Un en-tête à parité FAUSSE (pariteFausse) ne doit
    JAMAIS être accepté, même acquisition robuste active, même sous bruit — la
    correction guidée par la parité ne corrige qu'UNE erreur, pas un en-tête faux."""
    for snr in [30, 12, 6]:
        m = SSTV_MODES_PAR_NOM['M1']
        js = """(function(){
          var px = imageTestSstv(%d, %d);
          var sig = sstvEncodeSamples({mode:'M1', pixels:px, sampleRate:%d, lignes:2, pariteFausse:true});
          sig = bruitGaussienSnr(sig, %d, 7);
          var d = sstvDecodeSamples(sig, {sampleRate:%d, acqVisRobuste:true});
          return JSON.stringify(d.resume());
        })()""" % (m['largeur'] if False else 0, 0, FS, snr, FS)  # placeholder remplacé ci-dessous
        # (l'implémenteur écrit l'appel réel : mode M1, pariteFausse:true, acqVisRobuste:true)
        pass
    # Version robuste sans f-string cassante : passer par un helper JS dédié.
    ok = moteur.eval("""(function(){
      var m = SSTV_MODES_PAR_NOM['M1'];
      var px = imageTestSstv(m.largeur, m.hauteur);
      var accepte = 0;
      [30,12,6].forEach(function(snr){
        var sig = sstvEncodeSamples({mode:'M1', pixels:px, sampleRate:FS, lignes:2, pariteFausse:true});
        sig = bruitGaussienSnr(sig, snr, 7);
        var d = sstvDecodeSamples(sig, {sampleRate:FS, acqVisRobuste:true});
        if(d.resume().mode !== null) accepte++;
      });
      return accepte;
    })()""")
    assert ok == 0, 'un en-tête à parité fausse a été accepté (%s/3) — faux positif VIS' % ok
```

(NB : la 1ʳᵉ moitié illustrative est à remplacer par le seul bloc `moteur.eval` propre — l'implémenteur garde uniquement l'appel JS dédié.)

- [ ] **Step 2 : Lancer, vérifier l'état initial**

Run : `python -m pytest concours/tests/test_sstv_robustesse.py -k f2b -v`
Expected : `test_f2b_pas_de_faux_positif_vis` doit passer DÉJÀ (parité toujours vérifiée), `test_f2b_gain_acquisition_sous_bruit` peut déjà passer si F2a suffit — sinon il guide F2b. Le vrai témoin de F2b est la contre-épreuve du Step 5.

- [ ] **Step 3 : Implémenter start par énergie + bits doux + correction parité**

`_verifierStart` : quand `acqVisRobuste`, décision par énergie 1200 Hz sur la fenêtre `[5;25]ms` (accumuler `this._eSync.pousser(raw)` ; comparer à l'énergie hors-1200). Garder la branche OFF (moyenne de `f`) intacte.

`_lireBitsVis` : quand `acqVisRobuste`, par créneau accumuler l'énergie 1100 (`_eUn`) et 1300 (`_eZero`) sur `[5;25]ms` ; à la décision :

```javascript
// Décision douce : bit = 1 si énergie(1100) > énergie(1300). Confiance =
// |e1 - e0| / (e1 + e0) (0 = ambigu, 1 = net). L'énergie intègre le bruit ET
// dépriorise naturellement les échantillons faibles (fading) — sans clic de f.
const bits = [], conf = [];
for(let k = 0; k < 9; k++){
  const e1 = this._visE1[k], e0 = this._visE0[k];
  bits.push(e1 > e0 ? 1 : 0);
  conf.push(Math.abs(e1 - e0) / ((e1 + e0) || 1e-12));
}
let code = 0, uns = 0;
for(let k = 0; k < 7; k++){ if(bits[k]){ code |= (1 << k); uns++; } }
let bitParite = bits[7], stopOk = /* énergie 1200 du créneau 8 > énergies 1100/1300 */;
let pariteOk = ((uns + bitParite) % 2) === 0;
// Correction guidée par la parité : si la parité échoue, retourner le bit LE
// MOINS SÛR (confiance minimale) parmi les 8 (7 données + parité) et revérifier.
// Ne corrige qu'UNE erreur unique ; au-delà, on rejette (pas d'invention).
if(!pariteOk){
  let kmin = 0; for(let k = 1; k < 8; k++) if(conf[k] < conf[kmin]) kmin = k;
  bits[kmin] ^= 1;
  code = 0; uns = 0;
  for(let k = 0; k < 7; k++){ if(bits[k]){ code |= (1 << k); uns++; } }
  bitParite = bits[7];
  pariteOk = ((uns + bitParite) % 2) === 0;
}
```

(Les accumulateurs par créneau `this._visE1[k]`/`this._visE0[k]` remplacent `_visSommes`/`_visComptes` quand `acqVisRobuste` ; l'implémenteur les initialise à l'entrée en `vis-bits`. Le calcul de `stopOk` par énergie 1200 est à écrire proprement.) **Garde intacte** : après correction, si `pariteOk` reste faux OU `stopOk` faux → rejet (comportement historique). La correction n'AJOUTE jamais un chemin d'acceptation d'un VIS faux : un en-tête à parité structurellement fausse a un nombre PAIR d'erreurs incohérentes qu'un seul retournement ne « répare » pas vers un code valide contrôlé — verrouillé par `test_f2b_pas_de_faux_positif_vis`.

- [ ] **Step 4 : Lancer, mesurer, PASS**

Run : `python -m pytest concours/tests/test_sstv_robustesse.py -k f2b -v -s`
Expected : PASS. Relever le SNR min acquis on vs off. **Décision keep/reject** chiffrée.

- [ ] **Step 5 : Contre-épreuve par mutation (2 propriétés)**

(a) Désactiver la correction parité (ne jamais retourner) → `test_f2b_gain_acquisition_sous_bruit` doit montrer un on dégradé (ou un test dédié rougir). (b) **Anti-faux-positif** : muter la garde pour accepter malgré `!pariteOk` → `test_f2b_pas_de_faux_positif_vis` doit rougir. Restaurer les deux.

- [ ] **Step 6 : Non-régression modes + Commit**

Run : `python -m pytest concours/tests/test_sstv_decodeur.py -v` → PASS intégral.
```bash
git add concours/logx_sstvdecoder.js concours/tests/test_sstv_robustesse.py
git commit -m "feat(sstv): F2b start par energie + bits VIS doux + correction parite (anti-faux-positif verrouille)"
```

---

## Task 3 : F3 — Squelch image sous fading (option)

**Files:**
- Modifier : `concours/logx_sstvdecoder.js` (constructeur ; `_decoderImage` recalage L673-687 ; `_finaliserCellule`)
- Test : `concours/tests/test_sstv_robustesse.py`

**Interfaces:**
- Produit : option `squelchFade` (booléen, **défaut `true`**). Quand `true` et `this._lastAmpl` sous un seuil (relatif à sa moyenne récente) : (a) le recalage de synchro (`_suivreCorr`/`_recalerSyncCorr` et la branche historique) est GELÉ ; (b) `_finaliserCellule` conserve la dernière valeur du pixel au lieu d'écrire la valeur bruitée.
- Consomme : `this._lastAmpl` (A1), le recalage (A3), `_finaliserCellule` (A2).

- [ ] **Step 1 : Écrire le test comparatif**

```python
def test_f3_option_squelch_est_bien_cablee(moteur, capsys):
    """squelchFade a un effet réel sous fading (sinon option morte)."""
    on  = _surface(moteur, 'M1', [24], [1.0], {'dec': {'squelchFade': True}})[0]
    off = _surface(moteur, 'M1', [24], [1.0], {'dec': {'squelchFade': False}})[0]
    with capsys.disabled():
        print('\\nF3 M1 fading=1Hz MAE on=%s off=%s' % (on['mae'], off['mae']))
    assert (on['mae'] is None) != (off['mae'] is None) or (
        on['mae'] is not None and off['mae'] is not None and abs(on['mae'] - off['mae']) > 0.1), \
        'squelchFade sans effet mesurable sous fading — option morte ?'


def test_f3_ne_regresse_pas_sans_fading(moteur):
    """Sans fading (amplitude stable), le squelch ne doit jamais se déclencher :
    MAE à 30 dB non dégradé vs sans squelch (M1, image entière)."""
    on  = _surface(moteur, 'M1', [30], [0], {'dec': {'squelchFade': True}})[0]
    off = _surface(moteur, 'M1', [30], [0], {'dec': {'squelchFade': False}})[0]
    assert on['acquis'] and off['acquis']
    assert on['mae'] <= off['mae'] + 1.0, 'squelch actif sans fading : MAE %s vs %s' % (on['mae'], off['mae'])
```

- [ ] **Step 2 : Lancer, vérifier l'ÉCHEC** (option absente → pas d'effet).

- [ ] **Step 3 : Implémenter le squelch**

Constructeur : `squelchFade = true` ; suivi d'une amplitude de référence (moyenne glissante longue de `_lastAmpl`) pour un seuil relatif ; `this._pixFade` (drapeau « échantillon en fade »).

Dans `_decoderImage`, avant le recalage : calculer si on est en fade (`_lastAmpl < k · ampliMoyenne`, k ~0,4 à concevoir/mesurer). Si `squelchFade && enFade` : **ne pas** appeler `_suivreCorr`/`_recalerSync` (geler t0), et marquer la cellule courante « fade ».

Dans `_finaliserCellule` : si la cellule a été majoritairement en fade (compteur d'échantillons fade > moitié), **ne pas écrire** `_cellPlan[_cellIdx]` (conserver la dernière valeur) au lieu d'écrire la fréquence bruitée.

⚠️ Le seuil `k` et la constante de la moyenne d'amplitude sont À CONCEVOIR et MESURER (Step 4) — pas de valeur magique non mesurée. Documenter.

- [ ] **Step 4 : Lancer, mesurer, PASS** (gain image sous fading chiffré, keep/reject).

- [ ] **Step 5 : Contre-épreuve par mutation** (forcer `enFade=false` toujours → le test de câblage rougit ; restaurer).

- [ ] **Step 6 : Non-régression + Commit**

Run : `python -m pytest concours/tests/test_sstv_decodeur.py -v` → PASS.
```bash
git add concours/logx_sstvdecoder.js concours/tests/test_sstv_robustesse.py
git commit -m "feat(sstv): F3 squelch image sous fading (gel recalage + tenue pixel, option)"
```

---

## Task 4 : Consolidation — non-régression + bilan chiffré 2D

**Files:**
- Modifier : `concours/tests/test_sstv_robustesse.py` ; spec (bilan).

- [ ] **Step 1 : Non-régression globale (défauts vs tout-off historique)**

```python
FAMILLES = ['M1', 'M2', 'S1', 'S2', 'SDX', 'R36', 'R72', 'PD90']

@pytest.mark.parametrize('mode', FAMILLES)
def test_consolidation_pas_de_regression(moteur, mode):
    """Aux DÉFAUTS (acqVisRobuste+squelchFade), chaque mode reste acquis et
    exploitable à 30 dB sans fading, MAE non dégradé de plus de 2 vs le tout-off
    historique."""
    defaut = _surface(moteur, mode, [30], [0], {'lignes': 24})[0]
    orig = _surface(moteur, mode, [30], [0], {'lignes': 24,
        'dec': {'acqVisRobuste': False, 'squelchFade': False}})[0]
    assert defaut['acquis'] and defaut['mae'] is not None
    assert defaut['mae'] <= max(25, orig['mae'] + 2.0), \
        '%s régresse : defaut=%s orig=%s' % (mode, defaut['mae'], orig['mae'])
```

- [ ] **Step 2 : Suite historique verte**

Run : `python -m pytest concours/tests/test_sstv_decodeur.py -v` → PASS intégral.

- [ ] **Step 3 : Bilan chiffré en spec**

Ajouter une §12 « Résultats mesurés (VIS + fading) » à la spec : baseline vs défauts, gain d'acquisition VIS (SNR min acquis on/off), gain image sous fading (MAE on/off aux points de fading), leviers gardés/rejetés avec les chiffres. Honnêteté : rejet chiffré si pas de gain.

- [ ] **Step 4 : Commit**

```bash
git add concours/tests/test_sstv_robustesse.py docs/superpowers/specs/2026-09-04-sstv-robustesse-vis-et-fading-design.md
git commit -m "test(sstv): non-regression + bilan chiffre VIS/fading"
```

**→ CHECKPOINT F4GLD : valider le bilan chiffré (essai on-air impossible ici, pas de radio) avant fusion.**

---

## Self-Review

**Spec coverage :** F1 (banc fading Rayleigh plat + sweep 2D) → Task 0. F2 (acquisition VIS : leader énergie / start énergie / bits doux + parité) → Tasks 1-2. F3 (squelch image sous fade) → Task 3. Non-régression + bilan → Task 4. §5 anti-faux-positif VIS → `test_f2b_pas_de_faux_positif_vis` + garde parité/stop. §6 A/B par option + mutation → chaque tâche. §8 hors périmètre TX → Global Constraints. ✓

**Placeholder scan :** Deux valeurs restent « À CONCEVOIR et MESURER » (le seuil d'énergie du leader `_eSeuilLeader`, le seuil de fade `k` + constante d'amplitude). Ce sont des **paramètres DSP à régler par mesure** (Step 4 de leurs tâches), pas du hand-waving : la tâche impose de les mesurer et documenter, jamais d'inventer une valeur magique — cohérent avec la règle du dépôt « ne rien annoncer sans l'avoir mesuré ». Le bloc illustratif cassant de `test_f2b_pas_de_faux_positif_vis` Step 1 est explicitement signalé à remplacer par le seul `moteur.eval` propre.

**Type consistency :** options `acqVisRobuste`(bool)/`squelchFade`(bool) cohérentes constructeur↔tests↔branches. `EnergieGlissante.pousser` produit une énergie normalisée, consommée par le leader (T1) et les bits (T2). `_surface`/`_taux_acquisition`/`mesureSnr(...,tauxFading)` définis en T0, réutilisés ensuite. `_lastAmpl` (A1) consommé par F3. Réutilise le pattern Goertzel d'A3 (`_suivreCorr`) sans le modifier.

**Dépendances d'ordre :** T1 (helper + estimateurs + `raw`) avant T2 (start/bits qui utilisent `_eSync`/`_eUn`/`_eZero`). T0 (banc) avant tout (mesure). T3 indépendant de T1/T2 mais après T0. T4 après tout.
