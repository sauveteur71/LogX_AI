# SSTV — Robustesse réception + modes manquants — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fiabiliser la réception SSTV sur signal faible/bruité (Lot A, priorité) puis ajouter les modes manquants (Lot B), sans jamais régresser les 14 modes existants ni toucher au chemin d'émission.

**Architecture :** Tout se joue côté navigateur dans `concours/logx_sstvdecoder.js` (décodeur + encodeur dans le même fichier, comme le RTTY). Lot A greffe trois leviers DSP **gatés par des options du constructeur `SstvDecodeur`** (défaut activé) afin de rester mesurables A/B et contre-épreuvables par mutation même après fusion. Un **banc de mesure SNR** synthétique (nouveau fichier de test) chiffre la robustesse *avant* toute modif DSP et sert de garde-fou de non-régression. Lot B ajoute des variantes de timing (M3/M4, S3/S4) et deux nouvelles familles (`mono`, `sc2`) dans la table `SSTV_MODES`, symétriquement côté encodeur.

**Tech Stack :** JavaScript vanille (navigateur, aucune dépendance), tests pytest + `py_mini_racer` (MiniRacer exécute le JS ; franchissement de frontière JS→Python par `JSON.stringify`).

**Spec :** `docs/superpowers/specs/2026-09-03-sstv-robustesse-rx-et-modes-design.md`

## Global Constraints

- **Un témoin vert AVANT toute mutation.** Après chaque correctif, remettre le défaut, vérifier que le test ROUGIT, restaurer. Aucune tâche n'est « faite » sans contre-épreuve par mutation. (règle du dépôt)
- **Tests structurels, pas de présence de chaîne.** Une propriété de comportement (MAE, SNR de décrochage) ; jamais `assert 'x' in corps`.
- **Aucune valeur de timing inventée.** Tout code VIS, durée de sync/porch/scan, ordre de canaux d'un mode ajouté porte un commentaire `// SOURCE : …` citant N7CXI (« Proposal for SSTV Mode Specifications », Dayton 2000), recoupé par au moins une 2ᵉ source (table MMSSTV, sstv-handbook.com) ET par le recoupement arithmétique `scan ≈ PIXEL × largeur` (cf. `test_le_timing_pd160_est_conforme_a_la_spec_n7cxi`). Sans source citable : la valeur reste `VALEUR À SOURCER` et la tâche est BLOQUÉE, pas devinée.
- **Le mannequin ne prouve rien.** L'aller-retour encode↔décode INTERNE ne valide pas un nouveau mode (encodeur et décodeur peuvent partager le même timing faux). Tout mode Lot B sans source EXTERNE (WAV tiers ou timings N7CXI vérifiés à la main) est livré marqué « non vérifié en externe ».
- **Chemin TX intouché.** Ne jamais modifier `logx_tx_audio.js`, `txAudioPtt()`, le PTT ni le CAT. L'encodeur `sstvEncodeSamples()` est réutilisé en lecture (banc de test, génération des nouveaux modes) uniquement.
- **Réponse à F4GLD en français** (consigne permanente CLAUDE.md).
- **Fréquence d'échantillonnage des tests : `FS = 11025`** (Nyquist 5512 Hz > 2300 Hz), comme `test_sstv_decodeur.py`.
- **Consulter la fiche mémoire « pièges py_mini_racer »** avant d'écrire tout test JS (sérialisation JS→Python : les objets JS reviennent en poignées opaques, franchir la frontière par `JSON.stringify`).

---

## File Structure

- `concours/logx_sstvdecoder.js` (MODIFIER) — cœur. Options de constructeur pour A1–A3 ; extension de `_freq` pour exposer l'amplitude instantanée (A1/A2) ; collecte par cellule pour l'estimateur robuste (A2) ; détecteur de sync corrélé optionnel (A3) ; nouvelles fabriques de modes + entrées de table + branches d'encodeur (Lot B).
- `concours/tests/test_sstv_robustesse.py` (CRÉER) — banc de mesure SNR (bruit gaussien calibré, métrique de décrochage), mesures comparatives A/B des leviers, non-régression des 14 modes.
- `concours/tests/test_sstv_decodeur.py` (MODIFIER) — étendre `TOUS_MODES` aux nouveaux modes une fois validés ; ajouter les audits de timing des nouveaux modes.
- `concours/logx_sstv_panel.js` + `concours/logx_sstv.html` (MODIFIER, Lot B final) — ajout des nouveaux modes au sélecteur d'émission uniquement.
- `concours/logx_contest_rules.js` / `concours/logx_configuration.html` — inchangés (le mode SSTV global existe déjà ; les sous-modes ne sont pas des modes de log séparés).

---

## Task 0 : Banc de mesure SNR + baseline chiffrée

**Files:**
- Test : `concours/tests/test_sstv_robustesse.py` (créer)
- (aucune modif de `logx_sstvdecoder.js` dans cette tâche — le banc mesure l'état ACTUEL)

**Interfaces:**
- Consomme : `sstvEncodeSamples`, `sstvDecodeSamples`, `SSTV_MODES_PAR_NOM` (existants).
- Produit : helpers JS `bruitGaussienSnr(sig, snrDb, graine, debutImage)`, `mesureSnr(nomMode, snrDb, opts)` et `courbeSnr(nomMode, snrsDb, opts)` réutilisés par toutes les tâches Lot A. Métrique par point : `{snr, mode, lignes, mae, utilisable}` ; `utilisable` = mode correct ET `mae !== null` ET `mae <= SEUIL_UTILISABLE`.

**Décisions figées ici (réutilisées partout) :**
- `SEUIL_UTILISABLE = 25` (MAE sur le dégradé lisse ; au-delà l'image penche/bruite au point d'être inexploitable). Constante nommée en tête de fichier.
- Balayage SNR par défaut : `[30, 27, 24, 21, 18, 15, 12, 9, 6, 3, 0]` dB.
- « SNR de décrochage » d'une courbe = le plus BAS SNR encore `utilisable` (plus bas = meilleur). Fonction Python `snr_decrochage(courbe)`.
- Bruit **gaussien** (Box-Muller) calibré en puissance : `sigma = rms_signal / 10^(snr/20)`, `rms_signal` mesuré sur la portion image (après l'en-tête). Graine fixe → reproductible.

- [ ] **Step 1 : Écrire le banc + un premier test de baseline (témoin)**

Créer `concours/tests/test_sstv_robustesse.py`. Reprendre le motif de fixture de `test_sstv_decodeur.py` (chargement du JS, helpers `imageTestSstv`/`maeSstv`/`allerRetourSstv`), et AJOUTER les helpers ci-dessous à l'éval de fixture :

```python
# -*- coding: utf-8 -*-
"""Banc de robustesse SSTV : courbe SNR -> qualité, mesurée sur signal
synthetique bruite. Sert de baseline chiffree AVANT toute modif DSP, puis de
garde-fou de non-regression et de mesure A/B des leviers A1-A3.

Ce que ce banc NE prouve PAS : le QRM/QSB reel sur l'air (bruit non gaussien,
selectivite, fading correle). Il chiffre une robustesse RELATIVE (lever on vs
off, avant vs apres) sur un canal bruit-blanc — suffisant pour decider
« gain chiffre ou rejet » de chaque lever, pas pour certifier une perf terrain.
"""
import json, os, pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_sstvdecoder.js')
py_mini_racer = pytest.importorskip('py_mini_racer')

FS = 11025
SEUIL_UTILISABLE = 25          # MAE au-dela duquel l'image est inexploitable
SNRS_DB = [30, 27, 24, 21, 18, 15, 12, 9, 6, 3, 0]


@pytest.fixture(scope='module')
def moteur():
    ctx = py_mini_racer.MiniRacer()
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    ctx.eval("""
    function imageTestSstv(l, h){
      var px = new Uint8ClampedArray(l*h*3);
      for(var y=0;y<h;y++) for(var x=0;x<l;x++){
        var i=(y*l+x)*3;
        var r=Math.round(x*255/(l-1)), g=Math.round(y*255/(h-1));
        px[i]=r; px[i+1]=g; px[i+2]=Math.round(255-(r+g)/2);
      }
      return px;
    }
    function maeSstv(dec, px, l, lignes){
      var s=0, n=0;
      for(var y=0;y<lignes;y++) for(var x=0;x<l;x++){
        var i=y*l+x;
        s += Math.abs(dec.rgba[i*4]-px[i*3])
           + Math.abs(dec.rgba[i*4+1]-px[i*3+1])
           + Math.abs(dec.rgba[i*4+2]-px[i*3+2]);
        n += 3;
      }
      return s/n;
    }
    // Bruit blanc GAUSSIEN calibre en SNR (dB) sur la puissance du signal.
    // Box-Muller a partir d'un LCG a graine : un echec se rejoue a l'identique.
    function bruitGaussienSnr(sig, snrDb, graine){
      var p=0;
      for(var i=0;i<sig.length;i++) p += sig[i]*sig[i];
      var rms = Math.sqrt(p/sig.length);
      var sigma = rms / Math.pow(10, snrDb/20);
      var s = graine||1, out = new Float32Array(sig.length), spare=null;
      for(var i=0;i<sig.length;i++){
        var g;
        if(spare!==null){ g=spare; spare=null; }
        else {
          s=(s*1103515245+12345)&0x7fffffff; var u1=(s/0x7fffffff)||1e-9;
          s=(s*1103515245+12345)&0x7fffffff; var u2=(s/0x7fffffff);
          var mag=Math.sqrt(-2*Math.log(u1));
          g=mag*Math.cos(2*Math.PI*u2); spare=mag*Math.sin(2*Math.PI*u2);
        }
        out[i]=sig[i]+g*sigma;
      }
      return out;
    }
    // Un point de mesure : encode la mire du mode, bruite au SNR donne, decode
    // avec les options DSP passees (leviers A1-A3), renvoie la metrique.
    function mesureSnr(nomMode, snrDb, opts){
      opts = opts || {};
      var m = SSTV_MODES_PAR_NOM[nomMode];
      var px = imageTestSstv(m.largeur, m.hauteur);
      var lignes = opts.lignes || null;
      var sig = sstvEncodeSamples({mode:nomMode, pixels:px, sampleRate:FS, lignes:lignes});
      sig = bruitGaussienSnr(sig, snrDb, 7);
      var decOpts = Object.assign({sampleRate:FS}, opts.dec||{});
      var d = sstvDecodeSamples(sig, decOpts);
      var r = d.resume();
      r.snr = snrDb;
      r.mae = (r.mode===nomMode && r.lignesEmises>0)
            ? maeSstv(d, px, m.largeur, r.lignesEmises) : null;
      return r;
    }
    function courbeSnr(nomMode, snrsDb, opts){
      return snrsDb.map(function(s){ return mesureSnr(nomMode, s, opts); });
    }
    // FS injecte cote Python via replace, MiniRacer n'a pas la variable FS.
    var FS = %d;
    """ % FS)
    return ctx


def _courbe(moteur, mode, snrs=None, opts=None):
    snrs = snrs or SNRS_DB
    js = 'JSON.stringify(courbeSnr(%s, %s, %s))' % (
        json.dumps(mode), json.dumps(snrs), json.dumps(opts or {}))
    return json.loads(moteur.eval(js))


def _snr_decrochage(courbe):
    """Plus BAS SNR encore utilisable (mode correct, mae <= seuil). Plus bas =
    meilleur. None si aucun point n'est utilisable."""
    ok = [p['snr'] for p in courbe
          if p['mode'] and p['mae'] is not None and p['mae'] <= SEUIL_UTILISABLE]
    return min(ok) if ok else None


def test_le_banc_produit_une_baseline_exploitable(moteur):
    """Temoin du banc lui-meme : sur un mode robuste (Robot 36, lignes tronquees
    pour la vitesse), a SNR eleve l'image est utilisable, et il existe un SNR de
    decrochage fini dans le balayage. Sans ce temoin, un banc casse se lirait
    comme une protection parfaite (regle du depot)."""
    c = _courbe(moteur, 'R36', SNRS_DB, {'lignes': 16})
    haut = next(p for p in c if p['snr'] == 30)
    assert haut['mode'] == 'R36'
    assert haut['mae'] is not None and haut['mae'] < SEUIL_UTILISABLE
    d = _snr_decrochage(c)
    assert d is not None, 'aucun SNR utilisable — banc suspect'
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il PASSE (témoin vert du banc)**

Run : `python -m pytest concours/tests/test_sstv_robustesse.py::test_le_banc_produit_une_baseline_exploitable -v`
Expected : PASS. (Depuis `concours/` ou racine selon la config pytest du dépôt — vérifier comment `test_sstv_decodeur.py` est lancé en CI et reproduire.)

- [ ] **Step 3 : Contre-épreuve du banc par mutation**

Muter `SEUIL_UTILISABLE` à `-1` (rien n'est jamais utilisable) → le test doit ÉCHOUER sur `assert d is not None`. Restaurer, revérifier vert. Muter `bruitGaussienSnr` pour renvoyer `sig` inchangé : le banc perd son sens mais le témoin resterait vert — c'est attendu, ce témoin ne teste QUE la mécanique ; la sensibilité au bruit est prouvée par les tâches A1–A3. Le noter en commentaire.

- [ ] **Step 4 : Mesurer et CONSIGNER la baseline des 14 modes**

Ajouter un test qui imprime (via `-s`) la baseline actuelle et la fige lâchement :

```python
BASELINE_MODES = ['M1', 'M2', 'S1', 'S2', 'R36', 'R72', 'PD90']  # 1 par famille + variantes rapides

@pytest.mark.parametrize('mode', BASELINE_MODES)
def test_baseline_snr_decrochage_actuel(moteur, mode, capsys):
    """Mesure et journalise le SNR de decrochage ACTUEL (avant tout levier).
    Assertion volontairement lache : on verrouille seulement qu'un mode decode
    en clair (SNR 30 dB). Le chiffre exact de decrochage est journalise pour
    servir de point de depart aux mesures A/B — il n'est pas fige en dur (on ne
    connait pas encore la cible, cf. spec §3)."""
    c = _courbe(moteur, mode, SNRS_DB, {'lignes': 24})
    haut = next(p for p in c if p['snr'] == 30)
    assert haut['mode'] == mode and haut['mae'] is not None
    with capsys.disabled():
        print('\\nBASELINE %-6s decrochage=%s dB  courbe=%s' % (
            mode, _snr_decrochage(c),
            [(p['snr'], None if p['mae'] is None else round(p['mae'],1)) for p in c]))
```

Run : `python -m pytest concours/tests/test_sstv_robustesse.py::test_baseline_snr_decrochage_actuel -v -s`
Copier la sortie (les SNR de décrochage par mode) dans un commentaire en tête du fichier de test, daté — c'est la **baseline chiffrée** dont dépend le critère de succès Lot A.

- [ ] **Step 5 : Commit**

```bash
git add concours/tests/test_sstv_robustesse.py
git commit -m "test(sstv): banc de mesure SNR + baseline chiffree de robustesse"
```

---

## Task 1 : Lot A1 — Limiteur d'amplitude avant discriminateur

**Files:**
- Modifier : `concours/logx_sstvdecoder.js` (constructeur `SstvDecodeur` ~L160-192 ; `_freq` L219-236)
- Test : `concours/tests/test_sstv_robustesse.py`

**Interfaces:**
- Produit : option de constructeur `limiteurAmpl` (booléen, **défaut `true`**). Quand `true`, le vecteur I/Q de l'étage 2 est normalisé (amplitude→1) avant la dérivée de phase. Expose aussi `this._lastAmpl` (amplitude I/Q instantanée du dernier échantillon) — **consommé par A2**.
- Consomme : helpers de Task 0.

- [ ] **Step 1 : Écrire le test comparatif (échoue tant que l'option n'existe pas)**

```python
def _existe_gain(moteur, mode, opt_on, opt_off):
    """Vrai s'il EXISTE un SNR ou lever-on est utilisable et lever-off ne l'est
    pas — preuve directe et mutation-sensible d'un gain de robustesse."""
    on  = _courbe(moteur, mode, SNRS_DB, {'lignes': 24, 'dec': opt_on})
    off = _courbe(moteur, mode, SNRS_DB, {'lignes': 24, 'dec': opt_off})
    util = lambda p: bool(p['mode']) and p['mae'] is not None and p['mae'] <= SEUIL_UTILISABLE
    par_snr_off = {p['snr']: util(p) for p in off}
    return any(util(p) and not par_snr_off.get(p['snr'], False) for p in on), on, off


def test_a1_limiteur_ne_regresse_pas_en_clair(moteur):
    """Non-regression : a SNR eleve (30 dB), activer le limiteur ne degrade pas
    le MAE de plus de 1 niveau vs sans. Garde-fou permanent : ce test survit a
    la fusion (comparaison on/off gatee par option)."""
    for mode in ['M1', 'R36', 'PD90']:
        on  = _courbe(moteur, mode, [30], {'lignes': 16, 'dec': {'limiteurAmpl': True}})[0]
        off = _courbe(moteur, mode, [30], {'lignes': 16, 'dec': {'limiteurAmpl': False}})[0]
        assert on['mae'] is not None and off['mae'] is not None
        assert on['mae'] <= off['mae'] + 1.0, '%s: on=%s off=%s' % (mode, on['mae'], off['mae'])


def test_a1_option_est_bien_cablee(moteur, capsys):
    """Temoin de cablage + MESURE du gain (decision keep/reject data-driven).
    Assertion minimale : les deux courbes DIFFERENT quelque part (l'option a un
    effet reel) — sinon l'option est morte. Le gain chiffre est journalise."""
    gain, on, off = _existe_gain(moteur, 'R36',
                                 {'limiteurAmpl': True}, {'limiteurAmpl': False})
    maes_on  = [None if p['mae'] is None else round(p['mae'],1) for p in on]
    maes_off = [None if p['mae'] is None else round(p['mae'],1) for p in off]
    assert maes_on != maes_off, 'limiteurAmpl sans effet mesurable — option morte ?'
    with capsys.disabled():
        print('\\nA1 R36  decro on=%s off=%s  gain=%s' % (
            _snr_decrochage(on), _snr_decrochage(off), gain))
```

- [ ] **Step 2 : Lancer, vérifier l'ÉCHEC**

Run : `python -m pytest concours/tests/test_sstv_robustesse.py -k a1 -v`
Expected : FAIL — l'option `limiteurAmpl` n'existe pas encore (les deux courbes sont identiques → `test_a1_option_est_bien_cablee` échoue sur `maes_on != maes_off`).

- [ ] **Step 3 : Implémenter A1 dans `logx_sstvdecoder.js`**

Dans le constructeur, lire l'option (défaut `true`) :

```javascript
constructor({sampleRate = 44100, onDebutImage, onLigne, onFinImage, onEtat,
             limiteurAmpl = true} = {}){
  // …existant…
  this._limiteurAmpl = limiteurAmpl;   // A1 : normalise I/Q avant discriminateur
  this._lastAmpl = 0;                  // amplitude I/Q instantanee (A1 -> A2)
```

Dans `_freq`, après le calcul de `this._I2/_Q2` et AVANT `atan2`, normaliser le vecteur d'étage 2 utilisé par le discriminateur si l'option est active. Garder l'amplitude pour A2 :

```javascript
this._I2 += (this._I - this._I2) * a;
this._Q2 += (this._Q - this._Q2) * a;
this._lastAmpl = Math.hypot(this._I2, this._Q2);
// A1 : sous le seuil FM, une chute d'amplitude fait « claquer » la phase.
// Normaliser le vecteur (amplitude -> 1) reduit l'impact de ces clics sur la
// derivee de phase. Garde numerique quand l'amplitude s'effondre (silence).
let I2 = this._I2, Q2 = this._Q2, Ip = this._Ip, Qp = this._Qp;
if(this._limiteurAmpl){
  const a2 = this._lastAmpl, ap = Math.hypot(this._Ip, this._Qp);
  if(a2 > 1e-9){ I2 /= a2; Q2 /= a2; }
  if(ap > 1e-9){ Ip /= ap; Qp /= ap; }
}
const dphi = Math.atan2(I2 * Qp - Q2 * Ip, Q2 * Qp + I2 * Ip);
```

(Le reste de `_freq` — moyenne glissante `_fRing` — inchangé.)

- [ ] **Step 4 : Lancer, vérifier le PASS + relever le gain**

Run : `python -m pytest concours/tests/test_sstv_robustesse.py -k a1 -v -s`
Expected : PASS. Noter le gain imprimé (SNR de décrochage on vs off) — **décision keep/reject** : on garde A1 si le décrochage baisse d'au moins un pas (3 dB) sur au moins un mode sans régression en clair. Sinon on documente le rejet (option laissée à `false` par défaut) — c'est un résultat valide (spec §3, « gain chiffré ou rejet »).

- [ ] **Step 5 : Contre-épreuve par mutation**

Forcer `if(false && this._limiteurAmpl)` → `test_a1_option_est_bien_cablee` doit rougir (`maes_on == maes_off`). Restaurer, revérifier vert.

- [ ] **Step 6 : Commit**

```bash
git add concours/logx_sstvdecoder.js concours/tests/test_sstv_robustesse.py
git commit -m "feat(sstv): A1 limiteur d'amplitude avant discriminateur (option, mesure A/B)"
```

---

## Task 2 : Lot A2 — Estimation de fréquence pixel robuste

**Files:**
- Modifier : `concours/logx_sstvdecoder.js` (constructeur ; `_decoderImage` L373-419 collecte de cellule ; `_finaliserCellule` L421-426)
- Test : `concours/tests/test_sstv_robustesse.py`

**Interfaces:**
- Produit : option de constructeur `estimPixel` ∈ `{'moyenne','mediane','ponderee'}`, **défaut `'ponderee'`**. `'moyenne'` = comportement historique (branche off pour l'A/B). `'mediane'` = médiane des fréquences de la cellule. `'ponderee'` = moyenne pondérée par l'amplitude instantanée (`this._lastAmpl`), qui dépriorise les échantillons où le vecteur I/Q s'effondre (bruit dominant).
- Consomme : `this._lastAmpl` produit par A1 (Task 1). **A2 dépend de A1 étant mergé** (l'amplitude est exposée là).

- [ ] **Step 1 : Écrire le test comparatif (échoue tant que l'estimateur robuste n'existe pas)**

```python
def test_a2_ne_regresse_pas_en_clair(moteur):
    """A SNR eleve, l'estimateur robuste ne doit pas degrader le MAE (>1 niveau)
    vs la moyenne historique."""
    for mode in ['M1', 'R36', 'PD90']:
        rob = _courbe(moteur, mode, [30], {'lignes': 16, 'dec': {'estimPixel': 'ponderee'}})[0]
        moy = _courbe(moteur, mode, [30], {'lignes': 16, 'dec': {'estimPixel': 'moyenne'}})[0]
        assert rob['mae'] is not None and moy['mae'] is not None
        assert rob['mae'] <= moy['mae'] + 1.0, '%s rob=%s moy=%s' % (mode, rob['mae'], moy['mae'])


def test_a2_option_est_bien_cablee(moteur, capsys):
    """Les trois estimateurs ne donnent pas tous le meme resultat sous bruit —
    sinon l'option est morte. Journalise le gain de chaque variante."""
    base = {'lignes': 24}
    moy = _courbe(moteur, 'R36', SNRS_DB, dict(base, dec={'estimPixel':'moyenne'}))
    med = _courbe(moteur, 'R36', SNRS_DB, dict(base, dec={'estimPixel':'mediane'}))
    pon = _courbe(moteur, 'R36', SNRS_DB, dict(base, dec={'estimPixel':'ponderee'}))
    empreinte = lambda c: [None if p['mae'] is None else round(p['mae'],1) for p in c]
    assert empreinte(moy) != empreinte(pon) or empreinte(moy) != empreinte(med), \
        'estimPixel sans effet — option morte ?'
    with capsys.disabled():
        print('\\nA2 R36 decro moy=%s med=%s pon=%s' % (
            _snr_decrochage(moy), _snr_decrochage(med), _snr_decrochage(pon)))
```

- [ ] **Step 2 : Lancer, vérifier l'ÉCHEC**

Run : `python -m pytest concours/tests/test_sstv_robustesse.py -k a2 -v`
Expected : FAIL (option `estimPixel` inexistante → les 3 empreintes identiques).

- [ ] **Step 3 : Implémenter A2**

Constructeur :

```javascript
constructor({/* … */, limiteurAmpl = true, estimPixel = 'ponderee'} = {}){
  // …
  this._estimPixel = estimPixel;   // A2 : 'moyenne' | 'mediane' | 'ponderee'
```

Dans le constructeur, remplacer les accumulateurs scalaires de cellule par des tampons (ne collecter le détail QUE si l'estimateur en a besoin, pour ne pas payer en 'moyenne') :

```javascript
this._cellCle = -1; this._cellSomme = 0; this._cellCompte = 0;
this._cellSommePoids = 0;           // A2 ponderee : somme des amplitudes
this._cellFreqs = [];               // A2 mediane : frequences de la cellule
this._cellPlan = null; this._cellIdx = 0;
```

Dans `_decoderImage`, à la réinitialisation de cellule (bloc `if(cle !== this._cellCle)`), réinitialiser aussi les nouveaux tampons ; à l'accumulation (`if(cle !== -1)`), alimenter selon l'estimateur :

```javascript
if(cle !== this._cellCle){
  this._finaliserCellule();
  this._cellCle = cle; this._cellPlan = plan; this._cellIdx = idx;
  this._cellSomme = 0; this._cellCompte = 0;
  this._cellSommePoids = 0;
  if(this._estimPixel === 'mediane') this._cellFreqs.length = 0;
}
if(cle !== -1){
  this._cellCompte++;
  if(this._estimPixel === 'ponderee'){
    const w = this._lastAmpl;       // depriorise les echantillons a I/Q effondre
    this._cellSomme += f * w; this._cellSommePoids += w;
  } else if(this._estimPixel === 'mediane'){
    this._cellFreqs.push(f);
  } else {
    this._cellSomme += f;           // 'moyenne' : comportement historique
  }
}
```

`_finaliserCellule` calcule `fMoy` selon l'estimateur :

```javascript
_finaliserCellule(){
  if(this._cellCle === -1 || !this._cellCompte || !this._cellPlan) return;
  let fMoy;
  if(this._estimPixel === 'ponderee'){
    // Repli sur la moyenne simple si tous les poids sont ~nuls (silence total).
    fMoy = this._cellSommePoids > 1e-9
         ? this._cellSomme / this._cellSommePoids
         : this._cellSomme / this._cellCompte;
  } else if(this._estimPixel === 'mediane'){
    const a = this._cellFreqs.slice().sort((x, y) => x - y);
    const n = a.length;
    fMoy = n % 2 ? a[(n - 1) >> 1] : (a[n/2 - 1] + a[n/2]) / 2;
  } else {
    fMoy = this._cellSomme / this._cellCompte;
  }
  this._cellPlan[this._cellIdx] = sstvClamp255((fMoy - SSTV_NOIR) / SSTV_PENTE);
  this._cellCle = -1; this._cellCompte = 0;
}
```

⚠️ **Piège** : en `'ponderee'`, `_cellSomme` accumule désormais `f*w` (plus `f`). Le repli silence utilise `_cellSomme/_cellCompte` qui n'est PAS la moyenne des `f` dans ce cas — c'est acceptable car le repli ne joue qu'à amplitude quasi nulle (silence), mais le documenter. Pour la médiane et la moyenne, `_cellSomme` garde son sens d'origine.

- [ ] **Step 4 : Lancer, vérifier le PASS + relever le gain**

Run : `python -m pytest concours/tests/test_sstv_robustesse.py -k a2 -v -s`
Expected : PASS. Comparer médiane vs pondérée vs moyenne sur les SNR de décrochage. **Décision keep/reject** du défaut : garder `'ponderee'` par défaut si elle domine ; sinon régler le défaut sur la variante gagnante (ou `'moyenne'` si aucune ne gagne sans régression).

- [ ] **Step 5 : Contre-épreuve par mutation**

Forcer l'estimateur pondéré à retomber sur `this._cellSomme/this._cellCompte` → `test_a2_option_est_bien_cablee` doit rougir. Restaurer.

- [ ] **Step 6 : Commit**

```bash
git add concours/logx_sstvdecoder.js concours/tests/test_sstv_robustesse.py
git commit -m "feat(sstv): A2 estimation pixel robuste (mediane/ponderee, option, mesure A/B)"
```

---

## Task 3 : Lot A3 — Synchro par corrélation

**Files:**
- Modifier : `concours/logx_sstvdecoder.js` (constructeur ; `_decoderImage` détection sync L376-383 ; `_recalerSync` L358-371)
- Test : `concours/tests/test_sstv_robustesse.py`

**Interfaces:**
- Produit : option de constructeur `syncCorrelation` (booléen, **défaut `true`**). Quand `true`, le recalage de t0 ne s'appuie plus sur le seuil instantané `f < 1350` + centre de passage, mais sur le **pic de corrélation** d'énergie à 1200 Hz sur une fenêtre de la durée de sync du mode. Quand `false`, comportement historique (`_basDebut`/`_recalerSync`).
- Consomme : `this._mode`, `this._t0`, helpers Task 0.

- [ ] **Step 1 : Écrire le test comparatif (échoue tant que l'option n'existe pas)**

```python
def test_a3_ne_regresse_pas_en_clair(moteur):
    """La synchro correlee ne doit pas pencher l'image en clair : MAE a 30 dB
    non degrade de plus de 1 niveau vs seuil historique, sur une image ENTIERE
    (le slant se voit sur la duree)."""
    for mode in ['M1', 'S1']:
        cor = _courbe(moteur, mode, [30], {'dec': {'syncCorrelation': True}})[0]
        seu = _courbe(moteur, mode, [30], {'dec': {'syncCorrelation': False}})[0]
        assert cor['complete'] and seu['complete']
        assert cor['mae'] <= seu['mae'] + 1.0, '%s cor=%s seu=%s' % (mode, cor['mae'], seu['mae'])


def test_a3_option_est_bien_cablee(moteur, capsys):
    cor = _courbe(moteur, 'M1', SNRS_DB, {'lignes': 48, 'dec': {'syncCorrelation': True}})
    seu = _courbe(moteur, 'M1', SNRS_DB, {'lignes': 48, 'dec': {'syncCorrelation': False}})
    emp = lambda c: [None if p['mae'] is None else round(p['mae'],1) for p in c]
    assert emp(cor) != emp(seu), 'syncCorrelation sans effet — option morte ?'
    with capsys.disabled():
        print('\\nA3 M1 decro cor=%s seu=%s' % (_snr_decrochage(cor), _snr_decrochage(seu)))
```

- [ ] **Step 2 : Lancer, vérifier l'ÉCHEC**

Run : `python -m pytest concours/tests/test_sstv_robustesse.py -k a3 -v`
Expected : FAIL (option absente → empreintes identiques).

- [ ] **Step 3 : Implémenter A3**

Constructeur : ajouter `syncCorrelation = true` ; buffers de corrélation :

```javascript
this._syncCorrelation = syncCorrelation;
// A3 : accumulateurs Goertzel glissants a 1200 Hz sur une fenetre = duree sync.
this._corrCos = 0; this._corrSin = 0; this._corrRing = null; this._corrIdx = 0;
```

L'initialisation fine de la fenêtre (taille = `Math.round(m.syncDuree * fs)`) se fait dans `_demarrerImage` une fois le mode connu :

```javascript
// dans _demarrerImage, apres avoir fixe this._mode :
if(this._syncCorrelation){
  const nCorr = Math.max(3, Math.round(mode.syncDuree * fs));
  this._corrRing = new Float32Array(nCorr);   // energie 1200 Hz glissante
  this._corrIdx = 0; this._corrCos = 0; this._corrSin = 0;
  this._corrPh = 0; this._corrPic = 0; this._corrPicN = -1;
}
```

Dans `_decoderImage`, quand `syncCorrelation` est actif, remplacer le bloc `if(f < 1350){…}` par une corrélation glissante qui calcule l'énergie à 1200 Hz sur la fenêtre et détecte son pic ; au pic, appeler un recalage recentré sur l'instant du pic. Concevoir `_recalerSyncCorr(nPic)` sur le modèle de `_recalerSync` mais en prenant `nPic` (l'échantillon du maximum d'énergie) comme centre au lieu de `(basDebut+n)/2` :

```javascript
// bloc de _decoderImage, branche syncCorrelation :
// energie a 1200 Hz sur fenetre glissante (Goertzel simplifie : |Σ x·e^{-jωn}|)
// NOTE : l'implementeur ecrit ici l'accumulation glissante reelle sur
// this._corrRing / _corrCos / _corrSin, detecte le max local d'energie sur la
// fenetre, et quand un pic net est confirme appelle :
this._recalerSyncCorr(nPic);
```

`_recalerSyncCorr` réutilise la logique de bornage de `_recalerSync` (associer le pic au balayage le plus proche, appliquer la moitié de l'écart, borner à ±1 ms) mais sans la fenêtre de durée `[0.5×,2.5×]` (remplacée par la sélectivité de la corrélation). **Garder `_recalerSync`/`_basDebut` intacts** pour la branche `false`.

> ⚠️ Cette tâche est la plus lourde du Lot A (le détail Goertzel glissant est de la vraie implémentation, non trivialisable en pseudo-code). Si le budget de la tâche dérape, la découper : 3a = corrélation qui détecte le pic et LOG (sans recaler, mesure de détection), 3b = branchement du recalage. Ne PAS mélanger avec une autre tâche.

- [ ] **Step 4 : Lancer, vérifier le PASS + relever le gain (levier principal attendu)**

Run : `python -m pytest concours/tests/test_sstv_robustesse.py -k a3 -v -s`
Expected : PASS. A3 est le levier principal contre le décrochage (spec §3) : on attend le gain le plus net ici. **Décision keep/reject** documentée avec les chiffres.

- [ ] **Step 5 : Contre-épreuve par mutation**

Court-circuiter `_recalerSyncCorr` (return immédiat) → `test_a3_option_est_bien_cablee` doit rougir. Restaurer.

- [ ] **Step 6 : Commit**

```bash
git add concours/logx_sstvdecoder.js concours/tests/test_sstv_robustesse.py
git commit -m "feat(sstv): A3 synchro par correlation d'energie 1200 Hz (option, mesure A/B)"
```

---

## Task 4 : Consolidation Lot A — non-régression des 14 modes + bilan chiffré

**Files:**
- Modifier : `concours/tests/test_sstv_robustesse.py` ; éventuellement défauts d'options dans `logx_sstvdecoder.js` selon les décisions keep/reject.

**Interfaces:**
- Consomme : tout le Lot A. Fige la configuration par défaut retenue.

- [ ] **Step 1 : Test de non-régression globale (défauts vs tout-off)**

```python
FAMILLES_TEMOIN = ['M1', 'M2', 'S1', 'S2', 'SDX', 'R36', 'R72', 'PD90']

@pytest.mark.parametrize('mode', FAMILLES_TEMOIN)
def test_lotA_ne_regresse_aucun_mode_en_clair(moteur, mode):
    """Avec les leviers aux DEFAUTS retenus, chaque mode doit rester utilisable
    a SNR eleve (30 dB) — aucun des 14 modes existants n'est casse par le Lot A.
    Compare au tout-off (comportement d'origine) : pas de degradation > 2."""
    defaut = _courbe(moteur, mode, [30], {'lignes': 24})[0]
    origine = _courbe(moteur, mode, [30], {'lignes': 24, 'dec': {
        'limiteurAmpl': False, 'estimPixel': 'moyenne', 'syncCorrelation': False}})[0]
    assert defaut['mode'] == mode and defaut['mae'] is not None
    assert defaut['mae'] <= max(SEUIL_UTILISABLE, origine['mae'] + 2.0), \
        '%s regresse : defaut=%s origine=%s' % (mode, defaut['mae'], origine['mae'])
```

- [ ] **Step 2 : Lancer + contre-épreuve**

Run : `python -m pytest concours/tests/test_sstv_robustesse.py -k lotA -v`
Expected : PASS pour les 8 témoins. Muter un défaut d'option vers une valeur cassante (ex. si un jour `estimPixel` défaut mal réglé) doit faire rougir un mode → prouve la sensibilité.

- [ ] **Step 3 : Vérifier que la suite SSTV historique reste verte**

Run : `python -m pytest concours/tests/test_sstv_decodeur.py -v`
Expected : PASS intégral (les défauts d'options ne changent pas le comportement en clair au-delà de la tolérance des tests existants — MAE < 12/15/20 selon les cas). Si un test historique rougit, c'est une régression réelle à traiter avant de continuer.

- [ ] **Step 4 : Bilan chiffré dans la spec**

Ajouter à la fin de la spec une sous-section « Résultats mesurés (Lot A) » : baseline vs défauts retenus, gain de décrochage par levier, leviers gardés/rejetés avec le chiffre. C'est la clôture du critère de succès Lot A (spec §3).

- [ ] **Step 5 : Commit**

```bash
git add concours/tests/test_sstv_robustesse.py concours/logx_sstvdecoder.js docs/superpowers/specs/2026-09-03-sstv-robustesse-rx-et-modes-design.md
git commit -m "test(sstv): non-regression des 14 modes + bilan chiffre Lot A"
```

**→ CHECKPOINT F4GLD : fin du Lot A (priorité). Valider le bilan chiffré avant d'entamer le Lot B.**

---

## Task 5 : Lot B1 — Martin M3/M4 et Scottie S3/S4 (variantes de timing)

**Files:**
- Modifier : `concours/logx_sstvdecoder.js` (bloc `SSTV_MODES` L120-139)
- Modifier : `concours/tests/test_sstv_decodeur.py` (`TOUS_MODES` + audit de timing)

**Interfaces:**
- Produit : entrées `M3`, `M4`, `S3`, `S4` dans `SSTV_MODES`/`SSTV_MODES_PAR_NOM`, via les fabriques existantes `sstvModeMartin`/`sstvModeScottie` (aucune nouvelle famille : `rgb`, encodeur déjà symétrique via `m.nom.startsWith('Martin'/'Scottie')`).

- [ ] **Step 1 : SOURCER les valeurs (action bloquante, pas un placeholder)**

Récupérer et CITER, pour chacun des 4 modes : le **code VIS** et la **durée de scan par ligne**. Sources : N7CXI Dayton 2000 (référence primaire) + table MMSSTV (`slcmd`) + sstv-handbook.com. Recouper chaque `scan` par `scan ≈ PIXEL × 320` (cf. `test_le_timing_pd160`). Écrire chaque valeur avec un commentaire `// SOURCE : N7CXI …, recoupe MMSSTV / PIXEL×320`. **Si une valeur reste introuvable ou discordante entre sources → marquer `VALEUR À SOURCER` et STOPPER cette tâche** (ne pas deviner — règle du dépôt). Martin M3/M4 et Scottie S3/S4 sont des modes documentés ; les VIS et scans sont dans la littérature N7CXI/MMSSTV — l'implémenteur les transcrit, il ne les invente pas.

- [ ] **Step 2 : Écrire le test (échoue tant que les modes n'existent pas)**

Étendre dans `test_sstv_decodeur.py` :

```python
TOUS_MODES = ['M1', 'M2', 'M3', 'M4', 'S1', 'S2', 'S3', 'S4', 'SDX',
              'R36', 'R72', 'PD50', 'PD90', 'PD120', 'PD160', 'PD180',
              'PD240', 'PD290']
```

(`test_vis_et_timing_de_chaque_mode` est déjà `@parametrize('mode', TOUS_MODES)` : il couvre automatiquement M3/M4/S3/S4 par aller-retour + MAE < 15.)

Ajouter un audit de timing dédié qui fige les valeurs SOURCÉES (recoupement PIXEL×320) :

```python
def test_timing_martin_scottie_ajoutes_sont_sources(moteur):
    """Fige les scan/VIS SOURCES de M3/M4/S3/S4 (recoupes PIXEL×320, cf. PD160).
    Un mode ajoute avec un scan devine ferait passer l'aller-retour interne
    (mannequin) mais echouerait ce recoupement arithmetique independant."""
    attendu = {
        # SOURCE a reporter ici depuis Step 1 (VALEUR A SOURCER si non trouve) :
        # 'M3': {'vis': ..., 'scan': ...}, 'M4': ..., 'S3': ..., 'S4': ...,
    }
    assert attendu, 'valeurs non sourcees — completer Step 1 avant de valider'
    for mode, v in attendu.items():
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].vis" % mode) == v['vis']
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].scan" % mode) == pytest.approx(v['scan'])
```

- [ ] **Step 3 : Lancer, vérifier l'ÉCHEC**

Run : `python -m pytest concours/tests/test_sstv_decodeur.py -k "timing_martin_scottie or vis_et_timing" -v`
Expected : FAIL (modes absents de la table).

- [ ] **Step 4 : Implémenter — ajouter les 4 entrées**

Dans le bloc `Object.entries({…})`, avec les valeurs sourcées :

```javascript
  M3:   sstvModeMartin('Martin M3', /*VIS SOURCE*/, /*scan SOURCE*/),
  M4:   sstvModeMartin('Martin M4', /*VIS SOURCE*/, /*scan SOURCE*/),
  S3:   sstvModeScottie('Scottie S3', /*VIS SOURCE*/, /*scan SOURCE*/),
  S4:   sstvModeScottie('Scottie S4', /*VIS SOURCE*/, /*scan SOURCE*/),
```

Renseigner `attendu` dans le test avec ces mêmes valeurs.

- [ ] **Step 5 : Lancer, vérifier le PASS + contre-épreuve**

Run : `python -m pytest concours/tests/test_sstv_decodeur.py -k "timing_martin_scottie or vis_et_timing" -v`
Expected : PASS. Muter le `scan` de M3 de +1 % → `test_vis_et_timing_de_chaque_mode[M3]` (MAE explose) ET `test_timing_martin_scottie_ajoutes_sont_sources` doivent rougir. Restaurer.

- [ ] **Step 6 : Validation externe (obligatoire Lot B)**

Consigner en commentaire : ces 4 modes sont des variantes de timing des familles Martin/Scottie déjà validées, timings **sourcés N7CXI/MMSSTV et recoupés arithmétiquement**. Si aucun WAV tiers n'est décodé, marquer « non vérifié en externe (WAV) — timings vérifiés sur source N7CXI/MMSSTV » (honnêteté spec §5).

- [ ] **Step 7 : Commit**

```bash
git add concours/logx_sstvdecoder.js concours/tests/test_sstv_decodeur.py
git commit -m "feat(sstv): modes Martin M3/M4 + Scottie S3/S4 (timings sources N7CXI)"
```

---

## Task 6 : Lot B2 — Famille `mono` (Robot 8/12/24 BW)

**Files:**
- Modifier : `concours/logx_sstvdecoder.js` (nouvelle fabrique `sstvModeMono` ; branche décodeur `mono` dans `_demarrerImage`/`_emettreBalayage`/`_decoderImage` ; branche encodeur `mono` dans `sstvEncodeSamples`)
- Modifier : `concours/tests/test_sstv_decodeur.py`

**Interfaces:**
- Produit : famille `'mono'` (sync + porch + un seul balayage luminance, `plan:'y'` mappé en gris R=G=B). Entrées `R8BW`, `R12BW`, `R24BW`.

- [ ] **Step 1 : SOURCER (bloquant)** — VIS, sync/porch, scan (largeur/hauteur) des 3 modes BW depuis N7CXI + MMSSTV, recoupés. `VALEUR À SOURCER` + STOP si introuvable.

- [ ] **Step 2 : Écrire le test** — ajouter `R8BW/R12BW/R24BW` à `TOUS_MODES` ; un test dédié vérifie que la famille `mono` restitue le gris (R=G=B à la tolérance MAE). Lancer → ÉCHEC.

- [ ] **Step 3 : Implémenter la fabrique + branches décodeur** — `sstvModeMono` (structure : `famille:'mono'`, `canaux:[{plan:'y', debut:sync+porch, duree:scan, rangee:'bal'}]`). Dans `_demarrerImage`, plan `{y:...}` seul ; dans `_emettreBalayage`, branche `mono` : `ligne(bal, x => { const v = p.y[bal*l+x]; return [v, v, v]; })`. `_decoderImage` fonctionne déjà via `m.canaux` (pas de `robot36`).

- [ ] **Step 4 : Implémenter la branche encodeur** — dans `sstvEncodeSamples`, ajouter `else if(m.famille === 'mono'){ ton(SSTV_SYNC, m.sync); ton(1500, m.porch); scan(m.scan, x => plansGris(bal, x)); }` où le gris vient de la luminance ITU (ou moyenne RGB — à sourcer avec le mode). Encoder depuis `pixels` RGB : `y = sstvRgbVersYcc(r,g,b)[0]` puis niveau.

- [ ] **Step 5 : Lancer PASS + contre-épreuve** (muter le scan → MAE explose). Restaurer.

- [ ] **Step 6 : Validation externe obligatoire** — famille NOUVELLE : l'aller-retour interne ne prouve rien seul (piège mannequin). Chercher un WAV Robot BW tiers (MMSSTV) ; si absent → livrer marqué « non vérifié en externe ».

- [ ] **Step 7 : Commit** — `feat(sstv): famille monochrome Robot 8/12/24 BW (timings sources N7CXI)`

---

## Task 7 : Lot B3 — Famille `sc2` (Wraase SC2-120/180)

**Files:**
- Modifier : `concours/logx_sstvdecoder.js` (fabrique `sstvModeSc2` ; branches décodeur/encodeur `sc2`)
- Modifier : `concours/tests/test_sstv_decodeur.py`

**Interfaces:**
- Produit : famille `'sc2'` (RGB séquentiel, structure de sync propre à Wraase). Entrées `SC2_120`, `SC2_180`.

- [ ] **Step 1 : SOURCER (bloquant)** — VIS, ordre des canaux RGB, sync/porch/sep, scan des SC2-120/180. N7CXI + MMSSTV + doc Wraase. `VALEUR À SOURCER` + STOP si discordant. ⚠️ L'ordre des canaux Wraase (RGB vs GBR) est un piège classique — sourcer explicitement.

- [ ] **Step 2 : Écrire le test** — ajouter à `TOUS_MODES` ; audit de timing dédié. Lancer → ÉCHEC.

- [ ] **Step 3 : Implémenter fabrique + branches** — `sstvModeSc2` sur le modèle de `sstvModeMartin` (famille `'sc2'`, 3 canaux RGB dans l'ordre sourcé). Décodeur : réutilise `m.canaux` (famille non spéciale → chemin RGB de `_emettreBalayage` via `famille==='rgb'`… ATTENTION : `_emettreBalayage` teste `m.famille === 'rgb'` — soit ranger `sc2` en `famille:'rgb'` si la structure est identique, soit ajouter une branche `sc2`). Décider selon le timing sourcé et le documenter.

- [ ] **Step 4 : Implémenter encodeur** — branche `sc2` dans `sstvEncodeSamples` (ordre RGB sourcé, sync/porch propres).

- [ ] **Step 5 : PASS + contre-épreuve** (muter l'ordre des canaux → couleurs permutées, MAE explose sur le dégradé). Restaurer.

- [ ] **Step 6 : Validation externe obligatoire** — famille NOUVELLE : WAV Wraase tiers requis, sinon « non vérifié en externe ».

- [ ] **Step 7 : Commit** — `feat(sstv): famille Wraase SC2-120/180 (timings + ordre canaux sources)`

---

## Task 8 : Lot B4 — Nouveaux modes au sélecteur d'émission (UI minimale)

**Files:**
- Modifier : `concours/logx_sstv_panel.js` et/ou `concours/logx_sstv.html` (sélecteur de mode d'émission)

**Interfaces:**
- Consomme : les modes ajoutés (Tasks 5-7). Les modes REÇUS s'affichent déjà sans changement (détection VIS auto) — seule l'ÉMISSION a besoin du sélecteur.

- [ ] **Step 1 : Localiser le sélecteur** — lire `logx_sstv_panel.js`/`logx_sstv.html` pour trouver comment la liste des modes TX est construite (liste littérale ou dérivée de `SSTV_MODES_PAR_NOM`).

- [ ] **Step 2 : Écrire le test de présence structurel** — si la liste est dérivée de la table, un test vérifiant que le sélecteur propose tous les `SSTV_MODES_PAR_NOM` ; si elle est littérale, test que chaque nouveau mode y figure. Lancer → ÉCHEC (ou PASS déjà si dérivé — auquel cas rien à coder, le noter).

- [ ] **Step 3 : Implémenter** — ajouter les nouveaux modes au sélecteur. Ne PAS alourdir la page (intuitivité, spec §6) : juste des `<option>`/entrées, aucun autre changement d'UI.

- [ ] **Step 4 : PASS + contre-épreuve.**

- [ ] **Step 5 : Commit** — `feat(sstv): nouveaux modes disponibles au selecteur d'emission`

---

## Self-Review

**Spec coverage :**
- §3 Lot A (banc + A1/A2/A3 + critère de succès chiffré) → Tasks 0-4. ✓
- §4 Lot B (M3/M4, S3/S4, mono, sc2) → Tasks 5-7. ✓ Sélecteur TX §6 → Task 8. ✓
- §5 validation (mannequin, témoin+mutation, non vérifié en externe) → Steps de sourçage + validation externe dans chaque tâche Lot B ; contre-épreuves partout. ✓
- §2 hors périmètre TX → Global Constraints (chemin TX intouché). ✓
- §9 risques (régression 14 modes, timings faux) → Task 4 non-régression + sourçage bloquant Tasks 5-7. ✓

**Placeholder scan :** Les `VALEUR À SOURCER` des Tasks 5-7 sont des **actions concrètes bloquantes** (source citée, recoupement arithmétique, STOP si introuvable), pas du hand-waving — déviation assumée de la règle « no placeholder » du skill, imposée par la règle plus forte du dépôt « ne jamais inventer une valeur de domaine ». Le détail Goertzel de A3-Step3 est signalé comme vraie implémentation avec option de découpe 3a/3b.

**Type consistency :** `limiteurAmpl` (bool), `estimPixel` (str), `syncCorrelation` (bool) cohérents entre constructeur, tests et branches. `this._lastAmpl` produit en Task 1, consommé en Task 2. `mesureSnr`/`courbeSnr`/`_snr_decrochage`/`_existe_gain` définis en Task 0, réutilisés tels quels ensuite.

**Dépendances d'ordre :** Task 2 dépend de Task 1 (amplitude exposée). Tasks 5-7 indépendantes entre elles mais après le checkpoint Lot A. Task 8 après 5-7.
