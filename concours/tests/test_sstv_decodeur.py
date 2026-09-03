# -*- coding: utf-8 -*-
"""Décodeur SSTV (Martin/Scottie/Robot/PD) dans le navigateur.

Activations, ISS (PD120), dimanches SSTV : jusqu'ici il fallait ouvrir MMSSTV
ou RX-SSTV à côté de LogX AI. Ici le décodage se fait dans la page, comme le
CW et le RTTY : rien à installer.

POURQUOI CES TESTS SONT REPRÉSENTATIFS, comme ceux du RTTY : la SSTV est
générée par machine à timing FIXE (spec N7CXI — chaque pixel a sa fenêtre
temporelle à la microseconde près). Un signal synthétique est donc un vrai
signal SSTV. On encode une image de référence, on la décode, et on mesure
l'erreur moyenne par pixel (MAE) — le décodeur est exercé de bout en bout,
démodulation FM et détection VIS comprises, sans radio.

Le MAE n'est jamais nul : le filtre du démodulateur adoucit les transitions
entre pixels, et les modes Robot/PD sous-échantillonnent la chrominance.
L'image de test est un dégradé lisse, l'erreur admise est de quelques niveaux
sur 255.

Ce que ces tests NE prouvent PAS : le comportement sous QRM/QSB réel et les
signaux hors spec de certains logiciels exotiques. Ça reste à éprouver sur
l'air.

Fréquence d'échantillonnage des tests : 11025 Hz (Nyquist 5512 Hz, largement
au-dessus des 2300 Hz du blanc). Une image Martin M1 dure 114 s : à 44,1 kHz
chaque aller-retour manipulerait 5 millions d'échantillons, à 11025 c'est
4 fois moins pour une couverture identique.
"""
import json
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_sstvdecoder.js')
LOGBOOK_JS = os.path.join(CONCOURS, 'logx_logbook.js')
# MODE_TOGGLE_KEY a été extrait vers ce fichier partagé le 22/08/2026
# (chantier « page d'accueil par activité ») -- plus dans LOGBOOK_JS.
RULES_JS = os.path.join(CONCOURS, 'logx_contest_rules.js')
LOGBOOK_HTML = os.path.join(CONCOURS, 'logx_logbook.html')
CONFIG_HTML = os.path.join(CONCOURS, 'logx_configuration.html')

py_mini_racer = pytest.importorskip('py_mini_racer')

FS = 11025

# Tous les modes de la table — un oubli ici laisserait un mode non testé.
TOUS_MODES = ['M1', 'M2', 'M3', 'M4', 'S1', 'S2', 'S3', 'S4', 'SDX', 'R36', 'R72',
              'PD50', 'PD90', 'PD120', 'PD160', 'PD180', 'PD240', 'PD290',
              'R8BW', 'R12BW', 'R24BW']


@pytest.fixture(scope='module')
def moteur():
    ctx = py_mini_racer.MiniRacer()
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    ctx.eval("""
    // Dégradé lisse en x (rouge), en y (vert) et diagonal inversé (bleu) :
    // chaque pixel a une valeur unique, une erreur de timing (ligne décalée,
    // canal permuté) fait donc EXPLOSER le MAE au lieu de passer inaperçue
    // comme sur une mire à aplats.
    function imageTestSstv(l, h){
      var px = new Uint8ClampedArray(l*h*3);
      for(var y=0;y<h;y++) for(var x=0;x<l;x++){
        var i=(y*l+x)*3;
        var r=Math.round(x*255/(l-1)), g=Math.round(y*255/(h-1));
        px[i]=r; px[i+1]=g; px[i+2]=Math.round(255-(r+g)/2);
      }
      return px;
    }
    // Bruit blanc reproductible (générateur à graine) : un échec se rejoue.
    function avecBruitSstv(sig, niveau, graine){
      var s = graine || 1, out = new Float32Array(sig.length);
      for(var i=0;i<sig.length;i++){
        s = (s*1103515245 + 12345) & 0x7fffffff;
        out[i] = sig[i] + ((s/0x7fffffff)*2-1)*niveau;
      }
      return out;
    }
    // Erreur absolue moyenne par composante, sur les lignes effectivement
    // émises (les signaux tronqués n'émettent pas la dernière ligne).
    // `mono` (famille Robot BW, Lot B2) : le mode ne transmet QUE la
    // luminance — comparer le gris décodé aux 3 canaux R/G/B ORIGINAUX
    // indépendamment ferait exploser le MAE par construction (le mode ne
    // PEUT PAS reproduire la couleur, ce n'est pas un bug de timing). On
    // compare alors le gris décodé à la luminance ITU BT.601 attendue
    // (sstvRgbVersYcc, même formule que l'encodeur) — un vrai décalage de
    // timing/canal continue de faire exploser cette erreur-là.
    function maeSstv(dec, px, l, lignes, mono){
      var s=0, n=0;
      for(var y=0;y<lignes;y++) for(var x=0;x<l;x++){
        var i=y*l+x;
        if(mono){
          var yAttendu = sstvRgbVersYcc(px[i*3], px[i*3+1], px[i*3+2])[0];
          s += Math.abs(dec.rgba[i*4] - yAttendu);
          n += 1;
        } else {
          s += Math.abs(dec.rgba[i*4]-px[i*3])
             + Math.abs(dec.rgba[i*4+1]-px[i*3+1])
             + Math.abs(dec.rgba[i*4+2]-px[i*3+2]);
          n += 3;
        }
      }
      return s/n;
    }
    function allerRetourSstv(nomMode, optsEnc, optsDec){
      optsEnc = optsEnc || {}; optsDec = optsDec || {};
      var m = SSTV_MODES_PAR_NOM[nomMode];
      var px = imageTestSstv(m.largeur, m.hauteur);
      var sig = sstvEncodeSamples(Object.assign(
        {mode: nomMode, pixels: px, sampleRate: %d}, optsEnc));
      if(optsEnc.bruit) sig = avecBruitSstv(sig, optsEnc.bruit, 7);
      var d = sstvDecodeSamples(sig, Object.assign({sampleRate: %d}, optsDec));
      var r = d.resume();
      r.mae = (r.mode === nomMode && r.lignesEmises > 0)
            ? maeSstv(d, px, m.largeur, r.lignesEmises, m.famille === 'mono') : null;
      return r;
    }""" % (FS, FS))
    return ctx


def _aller_retour(moteur, mode, enc=None, dec=None):
    # JSON.stringify côté JS : py_mini_racer renvoie les objets JS sous forme
    # de poignées opaques, pas de dicts.
    return json.loads(moteur.eval('JSON.stringify(allerRetourSstv(%s, %s, %s))' % (
        json.dumps(mode), json.dumps(enc or {}), json.dumps(dec or {}))))


# ─── Détection VIS et tables de timing ───────────────────────────────────────

@pytest.mark.parametrize('mode', TOUS_MODES)
def test_vis_et_timing_de_chaque_mode(moteur, mode):
    """Signal tronqué à 8 balayages : suffisant pour vérifier que l'en-tête
    VIS identifie le bon mode ET que la table de timing est juste — une durée
    de balayage fausse de 1 % décale les pixels et fait exploser le MAE."""
    r = _aller_retour(moteur, mode, {'lignes': 8})
    assert r['mode'] == mode
    assert r['lignesEmises'] >= 6
    assert r['mae'] is not None and r['mae'] < 15, 'MAE %s : %s' % (mode, r['mae'])


def test_le_timing_pd160_est_conforme_a_la_spec_n7cxi(moteur):
    """Audit de conformité (14/08/2026) : signalait la constante de balayage
    PD160 comme transposée (0.195584 -> 0.195854 attendu). Vérification faite
    contre 3 recoupements indépendants -- la table N7CXI/liste des modes SSTV
    (sstv-handbook.com), la constante PIXEL de pySSTV multipliée par la
    largeur de l'image (0.382 ms/px * 512 px = 195.584 ms), et la cohérence
    avec la durée totale de transmission publiée (~161 s) -- 0.195584 EST la
    valeur correcte, pas 0.195854. Rien n'a donc été changé dans le fichier ;
    ce test verrouille la valeur vérifiée contre une future régression dans
    un sens comme dans l'autre."""
    assert moteur.eval("SSTV_MODES_PAR_NOM['PD160'].scan") == pytest.approx(0.195584)
    # Les autres constantes de balayage PD, vérifiées au passage (même
    # formule PIXEL * largeur), pour s'assurer qu'aucune autre n'est
    # transposée dans le même bloc.
    attendu = {
        'PD50': 0.09152, 'PD90': 0.17024, 'PD120': 0.1216,
        'PD180': 0.18304, 'PD240': 0.24448, 'PD290': 0.2288,
    }
    for mode, scan in attendu.items():
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].scan" % mode) == pytest.approx(scan)


def test_timing_martin_scottie_ajoutes_sont_sources(moteur):
    """Fige les VIS/scan/hauteur SOURCES de M3/M4/S3/S4 (Lot B1).

    Sources croisees (3 references independantes) :
      - sstv-handbook.com (OK2MNM, "List of SSTV modes", table Martin/Scottie) :
        VIS, duree totale publiee et lpm (lignes/minute) par mode.
      - slowrx (windytan/slowrx, modespec.c + VISmap[]) — decodeur tiers en
        production, seul a definir explicitement M3/M4 (pas S3/S4) : VIS
        0x24/0x20 et NumLines=128 pour M3/M4, confirmes.
      - docs.preterhuman.net "SSTV Transmission Modes" (compilation VIS de
        John Langner WB2OSZ + table durees/lignes) : confirme VIS Scottie
        (0x34=52, 0x30=48) et la structure "128 lignes totales dont 120
        utiles" (note 'c') pour les 4 modes, coherente avec le "256 dont 240
        utiles" (note 'b') deja connu de M1/M2/S1/S2/DX.

    Constat structurel (pas seulement une valeur de `scan`) : M3/M4/S3/S4 ne
    sont PAS de simples variantes de VIS de M1/M2/S1/S2 a hauteur egale — ce
    sont des versions a MOITIE MOINS DE LIGNES (128 balayages, pas 256), a la
    MEME vitesse de balayage par ligne que leur mode "parent" (M3=vitesse M1,
    M4=vitesse M2, S3=vitesse S1, S4=vitesse S2). D'ou `scan` identique au
    parent mais `hauteur`/`balayages` a 128 — objet du parametre optionnel
    `lignes` ajoute aux fabriques (defaut 256, comportement M1/M2/S1/S2/SDX
    inchange).

    Recoupement arithmetique (formule deja utilisee par
    test_le_timing_pd160_est_conforme_a_la_spec_n7cxi, generalisee ici a
    partir du lpm publie plutot que de PIXEL*largeur seul, car scan est ici
    la duree de balayage d'un CANAL entier, pas d'un pixel) :
      dureeBalayage(Martin)  = sync+porch+3*(scan+sep) avec sync=0.004862,
        porch=sep=0.000572
      dureeBalayage(Scottie) = 2*sep+sync+porch+3*scan avec sync=0.009,
        porch=sep=0.0015
      lpm_calcule = 60/dureeBalayage ; duree totale ~= 128*dureeBalayage
        (+ entete VIS ~0.3s, non compte) doit approcher la duree publiee.

      M3 : scan=0.146432 (= M1) -> dureeBalayage=0.446446s -> lpm=134.40
           (handbook : 134.395) ; 128*0.446446=57.14s (handbook : 57s).
      M4 : scan=0.073216 (= M2) -> dureeBalayage=0.226798s -> lpm=264.55
           (handbook : 264.553) ; 128*0.226798=29.03s (handbook : 29s).
      S3 : scan=0.13824  (= S1) -> dureeBalayage=0.42822s  -> lpm=140.12
           (handbook : 140.115) ; 128*0.42822=54.81s (handbook : 55s).
      S4 : scan=0.088064 (= S2) -> dureeBalayage=0.277692s -> lpm=216.07
           (handbook : 216.067) ; 128*0.277692=35.54s (handbook : 36s).

    Un scan ou une hauteur devines feraient passer l'aller-retour interne
    (mannequin, cf. test_vis_et_timing_de_chaque_mode) mais echoueraient ce
    recoupement arithmetique independant contre les 3 sources ci-dessus.
    Non verifie en externe (WAV tiers) — timings sources
    N7CXI/sstv-handbook/slowrx + recoupes par la formule ci-dessus (honnetete
    spec Lot B, §5)."""
    attendu = {
        'M3': {'vis': 36, 'scan': 0.146432, 'hauteur': 128},
        'M4': {'vis': 32, 'scan': 0.073216, 'hauteur': 128},
        'S3': {'vis': 52, 'scan': 0.13824,  'hauteur': 128},
        'S4': {'vis': 48, 'scan': 0.088064, 'hauteur': 128},
    }
    assert attendu, 'valeurs non sourcees — completer Step 1 avant de valider'
    for mode, v in attendu.items():
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].vis" % mode) == v['vis']
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].scan" % mode) == pytest.approx(v['scan'])
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].hauteur" % mode) == v['hauteur']
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].balayages" % mode) == v['hauteur']


def test_timing_robot_bw_est_source(moteur):
    """Fige les VIS/sync/porch/scan/hauteur SOURCES de la nouvelle famille
    `mono` (Robot 8/12/24 BW, Lot B2).

    Sources croisees (independantes, aucune ne cite l'autre) :
      - slowrx (windytan/slowrx, modespec.c) -- decodeur tiers en production.
        Le fichier attribue en commentaire CHAQUE entree a "N7CXI, 2000" mais
        c'est un intitule de bloc errone pour les 3 modes BW : le PDF N7CXI
        "Proposal for SSTV Mode Specifications" (recupere via web.archive.org,
        barberdsp.com etant injoignable directement) NE DEFINIT PAS ces modes
        -- grep sur le texte extrait (pdftotext) ne trouve que ROBOT 36
        COLOR / ROBOT 72 COLOR, aucune mention de BW. Verifie moi-meme avant
        de faire confiance au commentaire du fichier tiers (regle du depot :
        ne pas reprendre un constat sans le verifier).
      - pySSTV (dnet/pySSTV, pysstv/grayscale.py) -- 2e decodeur/encodeur
        tiers en production, implementation independante. Ne definit QUE
        Robot8BW et Robot24BW (pas de Robot12BW dans ce projet).
      - WB2OSZ (John Langner, compilation "SSTV Transmission Modes", version
        mars 1996 -- ANTERIEURE a N7CXI 2000, via docs.preterhuman.net) :
        table Temps total (s) / Lignes balayees, independante de toute
        implementation logicielle -- sert de recoupement ARITHMETIQUE (le
        meme principe que test_le_timing_pd160_est_conforme_a_la_spec_n7cxi
        et test_timing_martin_scottie_ajoutes_sont_sources) :
        duree totale = balayages * (sync+porch+scan), doit approcher la
        duree publiee.

    Valeurs retenues (slowrx x pySSTV, sync=7ms/porch=0 UNIFORME sur les 3
    modes -- pas les sync=10.0/12.0ms d'une table tierce de sstv-handbook.com
    consultee en parallele : cette derniere s'est revelee INCOHERENTE avec
    elle-meme sur la ligne Robot B&W 24 [sync 12 + scan 93 = 105ms, alors que
    son propre lpm=600 implique 100ms] -- ecartee au profit du couple
    slowrx/pySSTV qui s'accorde EXACTEMENT et recoupe l'arithmetique WB2OSZ a
    moins de 0.4% pres, cf. calculs ci-dessous). NB : `scan` (DUREE d'une
    ligne) provient de slowrx/pySSTV ; `largeur` (nombre de PIXELS par ligne)
    est sourcee SEPAREMENT (pySSTV WIDTH + resolution sstv-handbook), car le
    recoupement scan*largeur est invariant par produit et ne peut pas trancher
    le partage largeur/temps-par-pixel -- defaut trouve en revue (largeur
    figee a 320 pour les 3 alors que R8BW/R12BW font 160) :

      R8BW  : vis=2,  sync=0.007, porch=0, scan=0.0599 (=0.1871875e-3*320,
              slowrx PixelTime*ImgWidth ; DUREE, cf. pySSTV SCAN=60ms/160px),
              largeur=160 (pySSTV Robot8BW.WIDTH=160 + sstv-handbook
              "160x120" -- 2 sources), hauteur=120.
              dureeBalayage=0.0669 ; 120*0.0669=8.028s (WB2OSZ : 8s, +0.35%).
      R12BW : vis=6,  sync=0.007, porch=0, scan=0.09312 (=0.291e-3*320 ;
              = sstv-handbook "Scan line 93ms" a 0.13%), largeur=160
              (sstv-handbook "Robot B&W 12 : 160x120" -- SOURCE UNIQUE, pySSTV
              ne l'implemente pas ; corrobore par la resolution identique a
              BW8 dans la meme table + WB2OSZ "120 lignes"), hauteur=120.
              Seule slowrx donne le VIS pour ce mode (pySSTV muet ;
              pedrokv.com donne VIS=8 mais source auto-contradictoire, cf.
              rapport). Confiance la plus basse des 3 (VIS + largeur a source
              unique, pas de WAV externe).
              dureeBalayage=0.10012 ; 120*0.10012=12.014s (WB2OSZ : 12s,+0.12%).
      R24BW : vis=10, sync=0.007, porch=0, scan=0.09312, largeur=320 (pySSTV
              Robot24BW.WIDTH=320 + sstv-handbook "320x240" -- 2 sources),
              hauteur=240.
              dureeBalayage=0.10012 ; 240*0.10012=24.029s (WB2OSZ : 24s, +0.12%).

    Un scan/largeur/hauteur devines feraient passer l'aller-retour interne
    (mannequin, cf. test_vis_et_timing_de_chaque_mode) mais echoueraient ce
    recoupement independant -- c'est CE test (pas la validation externe) qui
    protege `largeur` en CI. R8BW/R24BW decodes une fois depuis un WAV pySSTV
    tiers (MAE degrade 3.3/1.6 ; le MAE est peu sensible a `largeur`, qui
    fixe la densite d'echantillonnage de sortie et non le timing -- cf.
    rapport Lot B2, section fix) ; run manuel NON committe, NON re-jouable en
    CI. R12BW non verifie en externe (pySSTV muet)."""
    attendu = {
        'R8BW':  {'vis': 2,  'sync': 0.007, 'porch': 0, 'scan': 0.0599,  'largeur': 160, 'hauteur': 120},
        'R12BW': {'vis': 6,  'sync': 0.007, 'porch': 0, 'scan': 0.09312, 'largeur': 160, 'hauteur': 120},
        'R24BW': {'vis': 10, 'sync': 0.007, 'porch': 0, 'scan': 0.09312, 'largeur': 320, 'hauteur': 240},
    }
    for mode, v in attendu.items():
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].famille" % mode) == 'mono'
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].vis" % mode) == v['vis']
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].sync" % mode) == pytest.approx(v['sync'])
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].porch" % mode) == pytest.approx(v['porch'])
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].scan" % mode) == pytest.approx(v['scan'])
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].largeur" % mode) == v['largeur']
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].hauteur" % mode) == v['hauteur']
        assert moteur.eval("SSTV_MODES_PAR_NOM['%s'].balayages" % mode) == v['hauteur']


@pytest.mark.parametrize('mode', ['R8BW', 'R12BW', 'R24BW'])
def test_la_famille_mono_restitue_bien_du_gris(moteur, mode):
    """La famille `mono` n'a qu'un seul canal luminance -- le décodeur DOIT
    produire R=G=B sur CHAQUE pixel émis (pas juste « proche », strictement
    égal : les 3 canaux RGBA sont recopiés depuis la MÊME valeur `v` dans
    `_emettreBalayage`). Un bug qui permuterait ou décolorerait la sortie
    (ex. `[v, 0, v]`, ou une confusion de canal) casserait cette égalité
    stricte sur au moins un pixel -- test structurel, pas un simple MAE."""
    r = _aller_retour(moteur, mode, {'lignes': 8})
    assert r['mode'] == mode
    assert r['lignesEmises'] >= 6
    # Vérification structurelle directe sur le buffer RGBA du décodeur : on
    # relance l'aller-retour côté JS pour garder une référence à l'objet
    # décodeur (allerRetourSstv ne renvoie qu'un résumé JSON côté Python).
    egal = moteur.eval("""
    (function(){
      var m = SSTV_MODES_PAR_NOM[%s];
      var px = imageTestSstv(m.largeur, m.hauteur);
      var sig = sstvEncodeSamples({mode: %s, pixels: px, sampleRate: %d, lignes: 8});
      var d = sstvDecodeSamples(sig, {sampleRate: %d});
      var n = d.lignesEmises, l = m.largeur, faux = 0;
      for(var y = 0; y < n; y++){
        for(var x = 0; x < l; x++){
          var i = (y*l+x)*4;
          if(d.rgba[i] !== d.rgba[i+1] || d.rgba[i+1] !== d.rgba[i+2]) faux++;
        }
      }
      return faux;
    })()""" % (json.dumps(mode), json.dumps(mode), FS, FS))
    assert egal == 0, '%s : %d pixels avec R != G != B (famille mono)' % (mode, egal)


# ─── Aller-retour complet ────────────────────────────────────────────────────

@pytest.mark.parametrize('mode', ['M1', 'S1', 'R36', 'PD90'])
def test_une_image_complete_se_decode_fidelement(moteur, mode):
    """Image entière (256 ou 240 lignes) : couvre une famille de chaque type
    de balayage — Martin (synchro en tête), Scottie (synchro au milieu),
    Robot 36 (chroma alternée) et PD (deux lignes par balayage)."""
    r = _aller_retour(moteur, mode)
    assert r['mode'] == mode
    assert r['complete'] is True
    assert r['lignesEmises'] == r['hauteur']
    assert r['mae'] < 12, 'MAE %s : %s' % (mode, r['mae'])


def test_la_derive_d_horloge_est_compensee(moteur):
    """Le décodeur croit à une fréquence d'échantillonnage fausse de 0,03 %
    (écart courant entre deux cartes son grand public). Sans le recalage sur
    les impulsions de synchro, l'erreur cumulée atteindrait 34 ms en fin
    d'image Martin M1 — 7 fois la largeur d'une impulsion — et l'image serait
    penchée au point d'être illisible (MAE > 60 sur le dégradé)."""
    r = _aller_retour(moteur, 'M1', None, {'sampleRate': FS * (1 - 3e-4)})
    assert r['mode'] == 'M1'
    assert r['complete'] is True
    assert r['mae'] < 20, 'MAE avec dérive : %s' % r['mae']


def test_le_bruit_n_empeche_pas_le_decodage(moteur):
    """Bruit blanc à 30 % de l'amplitude du signal : le VIS doit toujours
    accrocher et l'image rester exploitable (le filtre I/Q du démodulateur
    moyenne le bruit sur chaque fenêtre de pixel)."""
    r = _aller_retour(moteur, 'R36', {'bruit': 0.15})
    assert r['mode'] == 'R36'
    assert r['complete'] is True
    assert r['mae'] < 20, 'MAE avec bruit : %s' % r['mae']


# ─── Rejet des en-têtes invalides ────────────────────────────────────────────

def test_un_code_vis_inconnu_est_rejete(moteur):
    """Code VIS 1 : parité correcte mais mode absent de la table. Le décodeur
    doit rester en attente au lieu d'inventer une image avec un timing
    quelconque."""
    r = _aller_retour(moteur, 'M1', {'lignes': 2, 'visCode': 1})
    assert r['mode'] is None
    assert r['vis'] == 1          # le code a bien été LU, puis refusé

def test_une_parite_fausse_est_rejetee(moteur):
    """Bit de parité inversé : c'est la protection contre un bit de mode lu
    de travers dans le bruit — accepter l'en-tête ferait décoder 2 minutes de
    garbage avec le timing du mauvais mode."""
    r = _aller_retour(moteur, 'M1', {'lignes': 2, 'pariteFausse': True})
    assert r['mode'] is None
    assert r['vis'] is None       # jamais validé, donc jamais retenu


# ─── Intégration UI : chaque décodeur n'apparaît que dans SON mode ──────────
# Vérifications par lecture de source (même modèle que
# test_cw_panel_consolidation.py) : demande utilisateur explicite — « pas la
# peine d'afficher CW et SSTV si pas sélectionnés dans les modes ».

def _lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def test_updateKeyerPanels_pilote_les_panneaux_cw_et_sstv():
    """updateKeyerPanels() doit décider de la visibilité des DEUX panneaux
    décodeurs : cwPanel en mode CW (avant, il restait affiché dans tous les
    modes sauf RTTY) — ou via le forçage manuel cwPanelForcedOpen (bouton
    dédié du band map, F4GLD 05/08/2026 : accès exceptionnel au décodeur CW
    même si CW n'est pas dans les modes activés) —, sstvPanel seulement en
    mode SSTV."""
    src = _lire(LOGBOOK_JS)
    m = re.search(r'function\s+updateKeyerPanels\s*\([^)]*\)\s*\{(.*?)\n\}', src, re.S)
    assert m, 'updateKeyerPanels() introuvable'
    corps = m.group(1)
    assert 'sstvPanel' in corps
    assert 'cwPanel' in corps
    assert re.search(r'cwDec\.style\.display\s*=\s*\(?\s*cw\b', corps), \
        'cwPanel doit suivre le mode CW (éventuellement OR forçage manuel), pas « tout sauf RTTY »'


def test_panneaux_decodeurs_masques_par_defaut_dans_le_html():
    """Les panneaux partent masqués dans le HTML : c'est updateKeyerPanels()
    (appelé dès renderModeButtons) qui les montre dans leur mode. Sans ça, un
    panneau flasherait à l'écran au chargement dans les modes phonie."""
    html = _lire(LOGBOOK_HTML)
    for panneau in ('cwPanel', 'sstvPanel'):
        m = re.search(r'<div[^>]*id="%s"[^>]*>' % panneau, html)
        assert m, panneau + ' introuvable dans le HTML'
        assert 'display:none' in m.group(0), panneau + ' doit partir masqué'


def test_le_mode_sstv_est_declare_partout():
    """Le mode SSTV doit exister dans les deux endroits qui se répondent : la
    case de la page CONFIG (mode_sstv) et la table MODE_TOGGLE_KEY du logbook
    — en oublier un rendrait le décodeur inaccessible sans qu'aucune erreur
    n'apparaisse.

    Ce test vérifiait aussi une 3e liste littérale ('RTTY','SSTV'] dans
    renderModeButtons). Elle n'existe plus depuis le 18/08/2026 : les modes
    proposables sont désormais DÉRIVÉS de MODE_TOGGLE_KEY, précisément pour
    qu'un mode déclaré ici ne puisse plus manquer là-bas — c'est ce qui était
    arrivé à JS8/PSK/AM/D-STAR. La couverture est reprise par
    test_lot2_carnet_generaliste.py, qui exécute le vrai renderModeButtons."""
    assert 'data-key="mode_sstv"' in _lire(CONFIG_HTML)
    src = _lire(RULES_JS)
    assert re.search(r"'SSTV':\s*'mode_sstv'", src)


# ─── Conversions couleur ─────────────────────────────────────────────────────

def test_la_conversion_ycc_est_reversible(moteur):
    """RGB → YCrCb → RGB (coefficients BT.601 de la spec N7CXI) : l'erreur
    d'arrondi doit rester sous 2 niveaux sur 255 — au-delà, les couleurs des
    modes Robot/PD dérivent visiblement (teint verdâtre classique quand les
    matrices ne sont pas inverses l'une de l'autre)."""
    err = moteur.eval("""
    (function(){
      var pire = 0;
      var essais = [[0,0,0],[255,255,255],[255,0,0],[0,255,0],[0,0,255],
                    [128,64,200],[10,250,30],[200,200,10],[77,148,255]];
      for(var i=0;i<essais.length;i++){
        var e = essais[i];
        var ycc = sstvRgbVersYcc(e[0], e[1], e[2]);
        var rgb = sstvYccVersRgb(ycc[0], ycc[1], ycc[2]);
        for(var c=0;c<3;c++) pire = Math.max(pire, Math.abs(rgb[c]-e[c]));
      }
      return pire;
    })()""")
    assert err <= 2, 'erreur YCC max : %s' % err
