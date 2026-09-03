# -*- coding: utf-8 -*-
"""Banc de robustesse SSTV : courbe SNR -> qualite, mesuree sur signal
synthetique bruite. Sert de baseline chiffree AVANT toute modif DSP, puis de
garde-fou de non-regression et de mesure A/B des leviers A1-A3.

Ce que ce banc NE prouve PAS : le QRM/QSB reel sur l'air (bruit non gaussien,
selectivite, fading correle). Il chiffre une robustesse RELATIVE (lever on vs
off, avant vs apres) sur un canal bruit-blanc — suffisant pour decider
« gain chiffre ou rejet » de chaque lever, pas pour certifier une perf terrain.

BASELINE CHIFFREE (2026-09-03, avant tout levier DSP A1-A3) — sortie REELLE de
`python -m pytest concours/tests/test_sstv_robustesse.py::test_baseline_snr_decrochage_actuel -v -s`,
balayage {snr, mode, lignes, mae, utilisable} sur 24 lignes, SEUIL_UTILISABLE=25 :

BASELINE M1     decrochage=9 dB  courbe=[(30, 1.3), (27, 1.6), (24, 2.1), (21, 2.8), (18, 3.8), (15, 5.2), (12, 7.1), (9, 9.7), (6, None), (3, None), (0, None)]
BASELINE M2     decrochage=9 dB  courbe=[(30, 2.0), (27, 2.3), (24, 2.8), (21, 3.5), (18, 4.6), (15, 6.1), (12, 8.2), (9, 11.2), (6, None), (3, None), (0, None)]
BASELINE S1     decrochage=9 dB  courbe=[(30, 1.4), (27, 1.7), (24, 2.2), (21, 2.9), (18, 3.9), (15, 5.3), (12, 7.4), (9, 10.2), (6, None), (3, None), (0, None)]
BASELINE S2     decrochage=9 dB  courbe=[(30, 1.6), (27, 2.0), (24, 2.5), (21, 3.3), (18, 4.4), (15, 6.0), (12, 8.4), (9, 11.7), (6, None), (3, None), (0, None)]
BASELINE R36    decrochage=9 dB  courbe=[(30, 8.8), (27, 9.0), (24, 9.5), (21, 10.4), (18, 11.8), (15, 14.2), (12, 17.3), (9, 22.9), (6, None), (3, None), (0, None)]
BASELINE R72    decrochage=9 dB  courbe=[(30, 4.1), (27, 4.5), (24, 5.3), (21, 6.5), (18, 8.4), (15, 11.1), (12, 14.9), (9, 20.2), (6, None), (3, None), (0, None)]
BASELINE PD90   decrochage=9 dB  courbe=[(30, 2.2), (27, 2.8), (24, 3.6), (21, 4.9), (18, 6.7), (15, 9.2), (12, 12.7), (9, 17.8), (6, None), (3, None), (0, None)]

Lecture : les 7 modes decrochent tous a 9 dB sur ce banc synthetique
(bruit-blanc gaussien, 24 lignes, graine fixe) — c'est le SNR le plus bas du
balayage ou le MAE reste encore sous le seuil (25) pour chacun d'eux ; a 6 dB
tous echouent deja (mode ou MAE invalide). Le vrai point de decrochage de
chaque mode est donc quelque part entre 6 et 9 dB, plus fin que la resolution
de ce balayage a 3 dB pres — un balayage resserre dans cette plage serait
necessaire pour les departager. Ce chiffre sert de reference AVANT les
leviers A1-A3 ; les taches suivantes mesurent le gain (dB gagnes sur ce
decrochage, ou sur un balayage plus fin) avec le meme banc.
"""
import json
import os

import pytest

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
    # Bloc JS sans aucun formatage Python (pas de '%') : FS est injecte a
    # part dans un eval separe ci-dessous, pour ne jamais faire collision
    # avec un '%' qui apparaitrait un jour dans ce bloc (piège documente
    # dans le brief -- test_sstv_decodeur.py utilise le formatage inline,
    # mais ce fichier prefere l'approche la plus robuste).
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
    """)
    # FS injecte a part cote Python -- MiniRacer n'a pas la variable FS et le
    # bloc ci-dessus ne contient aucun formatage Python.
    ctx.eval('var FS = %d;' % FS)
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
    comme une protection parfaite (regle du depot).

    Contre-epreuve par mutation faite le 2026-09-03 : SEUIL_UTILISABLE mute a
    -1 (rien n'est jamais utilisable) -> ce test ECHOUE bien sur
    `assert d is not None`. Restaure, revert au vert. Mutation de
    bruitGaussienSnr pour renvoyer `sig` inchange : ce temoin reste VERT --
    ATTENDU, il ne teste QUE la mecanique du banc (encode/decode/MAE), pas la
    sensibilite au bruit -- cette derniere est prouvee par les mesures A/B
    des taches A1-A3 (courbe qui degrade avec le SNR), pas par ce temoin."""
    c = _courbe(moteur, 'R36', SNRS_DB, {'lignes': 16})
    haut = next(p for p in c if p['snr'] == 30)
    assert haut['mode'] == 'R36'
    assert haut['mae'] is not None and haut['mae'] < SEUIL_UTILISABLE
    d = _snr_decrochage(c)
    assert d is not None, 'aucun SNR utilisable — banc suspect'


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
        print('\nBASELINE %-6s decrochage=%s dB  courbe=%s' % (
            mode, _snr_decrochage(c),
            [(p['snr'], None if p['mae'] is None else round(p['mae'], 1)) for p in c]))


# ─── A1 : REJETE (limiteur d'amplitude avant discriminateur) ───────────────
# Le levier A1 du plan (normaliser le vecteur I/Q avant l'atan2 du
# discriminateur) a ete MESURE INERTE : atan2(k*y, k*x) = atan2(y, x) pour
# k>0, donc mettre chaque vecteur a l'echelle avant l'atan2 ne change PAS la
# phase demodulee. Gain nul prouve (algebre + 100000 vecteurs aleatoires,
# ecart max 4.4e-16 ; sweep fin 0.5 dB sur M1/R36/PD90, courbes identiques au
# centieme, decrochage identique a 9 dB). Rejet acte (spec §3 « gain chiffre
# ou rejet »). SEUL livrable garde : l'exposition de `_lastAmpl` (amplitude
# I/Q instantanee), consommee par le levier A2 (estimation de pixel ponderee).
# Le test ci-dessous verrouille ce contrat dont A2 depend.

def _lastampl_pour_tonalite(moteur, ampl, freq=1900, nEch=4096):
    """Pousse une tonalite pure d'amplitude `ampl` a `freq` Hz dans un decodeur
    frais, laisse le filtre I/Q s'etablir, et renvoie `_lastAmpl` (amplitude
    I/Q instantanee du dernier echantillon). Traverse la frontiere py_mini_racer
    via un scalaire JSON. `freq` est prise dans la bande utile du detecteur
    (leader 1900 Hz) pour que le vecteur I/Q soit bien etabli."""
    js = (
        'var _d = new SstvDecodeur({sampleRate: FS});'
        'var _w = 2*Math.PI*%s/FS, _n = %d;'
        'for(var _i=0; _i<_n; _i++){ _d._freq(%s * Math.sin(_w*_i)); }'
        '_d._lastAmpl;'
    ) % (json.dumps(freq), int(nEch), json.dumps(ampl))
    return float(moteur.eval(js))


def test_a1_lastampl_suit_l_amplitude_du_signal(moteur):
    """Contrat pour A2 : `_lastAmpl` reflete l'amplitude I/Q instantanee et
    croit ~proportionnellement a l'amplitude du signal d'entree. Une tonalite
    a 2A doit produire un `_lastAmpl` ~2x celui a A (le filtre I/Q est lineaire,
    le rapport est donc conserve a la tolerance numerique pres). Si ce test est
    rouge, la ponderation par amplitude d'A2 n'a aucun sens."""
    a1 = _lastampl_pour_tonalite(moteur, 0.25)
    a2 = _lastampl_pour_tonalite(moteur, 0.50)
    assert a1 > 1e-6, '_lastAmpl nul a amplitude A — non peuple ?'
    assert a2 > 1e-6, '_lastAmpl nul a amplitude 2A — non peuple ?'
    ratio = a2 / a1
    assert 1.8 <= ratio <= 2.2, \
        '_lastAmpl ne suit pas l\'amplitude : A->%.5f 2A->%.5f ratio=%.3f' % (a1, a2, ratio)


# ─── A2 : estimation de frequence pixel robuste (mediane / ponderee) ──────

def test_a2_ne_regresse_pas_en_clair(moteur):
    """A SNR eleve, l'estimateur robuste ne doit pas degrader le MAE (>1 niveau)
    vs la moyenne historique."""
    for mode in ['M1', 'R36', 'PD90']:
        rob = _courbe(moteur, mode, [30], {'lignes': 16, 'dec': {'estimPixel': 'ponderee'}})[0]
        moy = _courbe(moteur, mode, [30], {'lignes': 16, 'dec': {'estimPixel': 'moyenne'}})[0]
        assert rob['mae'] is not None and moy['mae'] is not None
        assert rob['mae'] <= moy['mae'] + 1.0, '%s rob=%s moy=%s' % (mode, rob['mae'], moy['mae'])


def test_a2_option_est_bien_cablee(moteur, capsys):
    """Liveness de la branche 'mediane' : sous bruit, elle ne doit pas produire
    la MEME empreinte que 'moyenne' — sinon cette branche est morte. Assertion
    INDEPENDANTE (plus de OU), avec son propre message. Journalise le decrochage
    des trois variantes.

    Pourquoi 'ponderee' n'est PAS gardee ICI : sur ce banc AWGN pur, l'amplitude
    I/Q ne s'effondre pas de facon informative, donc 'ponderee' ne differe de
    'moyenne' que d'UN point a ~0.1 MAE pres — marge trop fine (fragile a la
    derive flottante) pour un garde durable, et exactement le « knife-edge » a
    ne pas figer. La liveness ROBUSTE de 'ponderee' est verrouillee separement
    par test_a2_ponderee_deprioritise_amplitude_effondree (signal fabrique,
    marge > 100 niveaux). La mediane, elle, differe SYSTEMATIQUEMENT de la
    moyenne sur tout le balayage (efficacite moindre sous bruit gaussien) — la
    comparaison d'empreinte differe sur plusieurs points, marge robuste ici.

    Ainsi le OU d'origine est remplace par DEUX assertions independantes, une par
    variante non-historique : mediane ici (banc), ponderee dans le test dedie."""
    base = {'lignes': 24}
    moy = _courbe(moteur, 'R36', SNRS_DB, dict(base, dec={'estimPixel':'moyenne'}))
    med = _courbe(moteur, 'R36', SNRS_DB, dict(base, dec={'estimPixel':'mediane'}))
    pon = _courbe(moteur, 'R36', SNRS_DB, dict(base, dec={'estimPixel':'ponderee'}))
    empreinte = lambda c: [None if p['mae'] is None else round(p['mae'],1) for p in c]
    assert empreinte(moy) != empreinte(med), \
        'mediane sans effet vs moyenne — branche morte ?'
    with capsys.disabled():
        print('\nA2 R36 decro moy=%s med=%s pon=%s' % (
            _snr_decrochage(moy), _snr_decrochage(med), _snr_decrochage(pon)))


def _pixel_cellule_craftee(moteur, estim):
    """Pilote le VRAI chemin produit (_demarrerImage -> _decoderImage ->
    _finaliserCellule) sur UNE cellule de pixel fabriquee, ou l'amplitude I/Q
    (_lastAmpl) est CORRELEE a l'erreur de frequence : la vraie frequence (blanc,
    2300 Hz) est portee a pleine amplitude, une frequence fausse (noir, 1500 Hz)
    a amplitude effondree — le cas que la ponderation A2 est censee exploiter,
    absent du banc AWGN pur. _n est GELE pour que tous les echantillons tombent
    dans la meme cellule (canal g, pixel 0 de M1). Ce n'est pas un mannequin :
    on appelle les vraies methodes du decodeur, la branche de collecte
    ponderee lit le vrai champ this._lastAmpl. Renvoie la valeur de pixel
    ecrite (0..255)."""
    js = (
        '(function(){'
        ' var d = new SstvDecodeur({sampleRate:FS, estimPixel:%s});'
        ' var mode = SSTV_MODES_PAR_NOM["M1"];'
        ' d._demarrerImage(mode);'
        ' d._n = Math.round(d._t0 + 0.005600*FS);'
        ' var pat = [[2300,1.0],[2300,1.0],[2300,1.0],[2300,1.0],[2300,1.0],'
        '            [1500,0.01],[1500,0.01],[1500,0.01],[1500,0.01],[1500,0.01]];'
        ' for(var k=0;k<pat.length;k++){ d._lastAmpl=pat[k][1]; d._decoderImage(pat[k][0]); }'
        ' var plan=d._cellPlan, idx=d._cellIdx;'
        ' d._finaliserCellule();'
        ' return plan[idx];'
        '})()'
    ) % json.dumps(estim)
    return float(moteur.eval(js))


def test_a2_ponderee_deprioritise_amplitude_effondree(moteur):
    """Garde ROBUSTE de la branche 'ponderee' (marge > 100 niveaux, insensible a
    la derive flottante). Dans une cellule ou 5 echantillons portent la vraie
    frequence (blanc, 2300 Hz -> pixel 255) a pleine amplitude et 5 une frequence
    fausse (noir, 1500 Hz -> pixel 0) a amplitude effondree (0.01) :
      - 'moyenne' pese tout pareil -> pixel ~127 (tire loin du vrai par le faux),
      - 'ponderee' depriorise les echantillons effondres -> pixel ~252 (proche du
        vrai blanc 255).
    Ce garde fournit ce que le OU de test_a2_option_est_bien_cablee ne pouvait
    pas : la detection d'un effondrement de la SEULE branche 'ponderee'.

    Contre-epreuve par mutation (2026-09-03) : forcer `const w = 1;` dans la
    branche de collecte 'ponderee' de _decoderImage rend 'ponderee' identique a
    'moyenne' (pixel ~127) -> ce test ROUGIT (pon a 127 ne respecte plus
    abs(pon-255)<=10). Restaure -> revert au vert. Egalement verifie : un simple
    passage a la moyenne non ponderee (repli inconditionnel) est capture pareil."""
    VRAI = 255.0
    moy = _pixel_cellule_craftee(moteur, 'moyenne')
    pon = _pixel_cellule_craftee(moteur, 'ponderee')
    assert abs(moy - VRAI) >= 100, \
        'moyenne devrait etre tiree loin du vrai pixel par les echantillons a ' \
        'frequence fausse : moy=%.1f (attendu loin de %.0f)' % (moy, VRAI)
    assert abs(pon - VRAI) <= 10, \
        'ponderee devrait ignorer les echantillons a amplitude effondree et ' \
        'rester proche du vrai pixel : pon=%.1f (attendu proche de %.0f) — ' \
        'ponderation par _lastAmpl bien cablee ?' % (pon, VRAI)


# ─── A3 : synchro par correlation d'energie 1200 Hz ───────────────────────────
# Le decrochage AWGN vient d'un recalage de t0 rate quand l'impulsion de synchro
# est noyee dans le bruit : le detecteur historique (seuil instantane f<1350)
# manque une impulsion des qu'un echantillon bruite remonte au-dessus du seuil.
# A3 remplace ce seuil instantane par le PIC d'une energie glissante a 1200 Hz
# integree sur la duree de sync du mode — un integrateur moyenne le bruit et
# fait ressortir l'impulsion. C'est le levier attendu comme le plus efficace
# contre le decrochage (spec §3), contrairement a A1 (inerte) et A2 (0 dB AWGN).

# Balayage fin autour du genou de decrochage (~9 dB en baseline, resolution 3 dB
# trop grossiere pour departager on/off) : pas de 0.5 dB entre 4 et 14 dB.
SNRS_FINS = [round(4 + 0.5 * k, 1) for k in range(21)]  # 4.0 .. 14.0


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
    """Liveness de la branche correlation. DEUX assertions :

    1. Sous bruit, l'empreinte differe du seuil historique — sinon l'option est
       morte (branche jamais prise). Garde FAIBLE a elle seule : elle est aussi
       satisfaite si _recalerSyncCorr ne fait RIEN (la branche correlation ne
       recale alors pas du tout, ce qui differe deja du recalage historique).

    2. Garde FORTE : sous derive d'horloge (0,03 %, ecart courant entre cartes
       son), la synchro correlee DOIT recaler t0 pour empecher le slant —
       l'image reste complete et exploitable (MAE << le slant). Contre-epreuve
       par mutation (2026-09-03) : `return;` en tete de _recalerSyncCorr fait
       passer ce MAE de ~2 a ~20 (34 ms de derive cumulee sur M1) -> ROUGIT ;
       restaure -> vert. C'est CETTE assertion qui prouve que le recalage A3
       agit, pas seulement qu'il existe.

    Mesure en prime le gain de decrochage A3 sur un balayage FIN (0.5 dB) autour
    du genou, pour M1 et S1."""
    cor = _courbe(moteur, 'M1', SNRS_DB, {'lignes': 48, 'dec': {'syncCorrelation': True}})
    seu = _courbe(moteur, 'M1', SNRS_DB, {'lignes': 48, 'dec': {'syncCorrelation': False}})
    emp = lambda c: [None if p['mae'] is None else round(p['mae'], 1) for p in c]
    assert emp(cor) != emp(seu), 'syncCorrelation sans effet — option morte ?'

    drift = FS * (1 - 3e-4)   # decodeur ~0,03 % plus lent que l'encodeur -> slant sans recalage
    cd = _courbe(moteur, 'M1', [30], {'dec': {'syncCorrelation': True, 'sampleRate': drift}})[0]
    assert cd['complete'] and cd['mae'] is not None and cd['mae'] < 5.0, \
        'A3 ne recale pas t0 sous derive — _recalerSyncCorr inerte ? complete=%s mae=%s' % (
            cd['complete'], cd['mae'])
    with capsys.disabled():
        print('\nA3 M1 decro cor=%s seu=%s' % (_snr_decrochage(cor), _snr_decrochage(seu)))
        # Balayage fin (0.5 dB) pour departager on/off au genou, M1 et S1.
        for mode in ['M1', 'S1']:
            fcor = _courbe(moteur, mode, SNRS_FINS, {'lignes': 48, 'dec': {'syncCorrelation': True}})
            fseu = _courbe(moteur, mode, SNRS_FINS, {'lignes': 48, 'dec': {'syncCorrelation': False}})
            dcor, dseu = _snr_decrochage(fcor), _snr_decrochage(fseu)
            gain = None if (dcor is None or dseu is None) else round(dseu - dcor, 1)
            print('A3 %-3s FIN decro cor=%s seu=%s  gain=%s dB' % (mode, dcor, dseu, gain))
            print('    cor=%s' % [(p['snr'], None if p['mae'] is None else round(p['mae'], 1)) for p in fcor])
            print('    seu=%s' % [(p['snr'], None if p['mae'] is None else round(p['mae'], 1)) for p in fseu])


# ─── Consolidation Lot A : non-regression des 14 modes ────────────────────
# Verrouille la configuration par defaut retenue en fin de Lot A :
#   estimPixel='ponderee' (A2 garde), syncCorrelation=true (A3 garde).
# A1 (limiteur d'amplitude) a ete REJETE (mesure INERTE, cf. commentaire A1
# plus haut) : il n'existe PAS d'option 'limiteurAmpl' dans le decodeur —
# une cle de ce nom serait silencieusement ignoree par Object.assign, donc
# elle est volontairement ABSENTE de la config "origine" ci-dessous plutot
# que d'ecrire une option qui n'existe pas (regle du depot : pas de valeur
# inventee).
#
# "origine" = comportement historique (avant tout levier A1-A3) :
# estimPixel='moyenne', syncCorrelation=False.

FAMILLES_TEMOIN = ['M1', 'M2', 'S1', 'S2', 'SDX', 'R36', 'R72', 'PD90']


@pytest.mark.parametrize('mode', FAMILLES_TEMOIN)
def test_lotA_ne_regresse_aucun_mode_en_clair(moteur, mode):
    """Avec les leviers aux DEFAUTS retenus, chaque mode doit rester utilisable
    a SNR eleve (30 dB) — aucun des 14 modes existants n'est casse par le Lot A.
    Compare au comportement d'ORIGINE (moyenne + seuil historique, avant A2/A3) :
    pas de degradation > 2 niveaux de MAE."""
    defaut = _courbe(moteur, mode, [30], {'lignes': 24})[0]
    origine = _courbe(moteur, mode, [30], {'lignes': 24, 'dec': {
        'estimPixel': 'moyenne', 'syncCorrelation': False}})[0]
    assert defaut['mode'] == mode and defaut['mae'] is not None
    assert defaut['mae'] <= max(SEUIL_UTILISABLE, origine['mae'] + 2.0), \
        '%s regresse : defaut=%s origine=%s' % (mode, defaut['mae'], origine['mae'])

