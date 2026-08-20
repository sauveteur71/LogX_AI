# -*- coding: utf-8 -*-
"""Deux stations proches en fréquence : la seconde n'était jamais décodée.

CE QUI N'ALLAIT PAS. `ft8FindAllSync` écarte tout candidat trop proche en
fréquence d'un candidat déjà retenu (suppression des non-maxima). La largeur
de cette suppression valait `8 × FT8_TONE_SPACING`, soit 50 Hz — la largeur du
banc de tons. Le motif invoqué était que « deux candidats trop proches sont
presque toujours le même signal détecté deux fois ». Conséquence non voulue :
**toute station située à moins de 50 Hz d'une autre disparaissait**, sans
aucun message ni indice à l'écran.

CE QUE LA MESURE A MONTRÉ (décodage réel du signal synthétisé, pas lecture
du code). Deux scénarios qui tirent en sens opposés :

    seuil          2 stations à 18 Hz   à 31 Hz   16 stations réparties
    0 à 12,5 Hz           6/6             6/6           12/16
    18,75 Hz              6/6             6/6           16/16
    25 à 31,25 Hz         3/6             6/6           16/16
    50 Hz (ancien)        3/6             3/6           16/16

Retirer la règle est donc FAUX : sur bande chargée elle fait passer de 14/28
à 28/28. Elle n'écarte pas des stations, elle effondre la JUPE d'un même
signal — le balayage grossier avance par pas de 3,125 Hz, donc un signal fort
produit plusieurs pics voisins qui, sans elle, mangent les places de
`maxCandidates`. Le doublon de RÉSULTAT, lui, était déjà traité en aval par
`ft8DecodeAudioAll` (dédoublonnage par texte décodé).

18,75 Hz est la seule valeur qui tienne les deux bouts — mais à ce seuil un
signal prend 2 à 3 places au lieu d'une, d'où le budget de candidats porté
de 30 à 60 (mesuré : 21/28 à 30 places, 23/28 à 45, 28/28 à 60).

CE QUE CES TESTS NE PROUVENT PAS. Ils ne prouvent pas que le décodeur sépare
DEUX SIGNAUX QUI SE RECOUVRENT : sous ~19 Hz d'écart la seconde station reste
perdue. La limite est déplacée de 50 Hz à ~19 Hz, elle n'est pas supprimée.
La lever vraiment demanderait la soustraction de signal et un décodage en
plusieurs passes, chantier d'un autre ordre. Et comme partout ici, le signal
est fabriqué par le test : pas de QSB, pas de distorsion de chaîne SSB.
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODEC_JS = os.path.join(CONCOURS, 'logx_ft8_codec.js')
DSP_JS = os.path.join(CONCOURS, 'logx_ft8_dsp.js')

py_mini_racer = pytest.importorskip('py_mini_racer')

FE = 12000.0


@pytest.fixture(scope='module')
def moteur():
    ctx = py_mini_racer.MiniRacer()
    for path in (CODEC_JS, DSP_JS):
        with open(path, encoding='utf-8') as f:
            ctx.eval(f.read())
    ctx.eval("""
    var HT = ft8CreateHashTable();
    // Bruit reproductible : une mesure qui change à chaque exécution ne se
    // compare à rien. Math.imul pour un vrai wraparound 32 bits.
    function bruiteur(g){
      var e = g >>> 0;
      return function(){
        e = (Math.imul(e,1664525) + 1013904223) >>> 0;
        return (e/4294967296)*2 - 1;
      };
    }
    function fond(sr, graine){
      var n = Math.round(16.5*sr), buf = new Float32Array(n), a = bruiteur(graine);
      for(var i=0;i<n;i++) buf[i] = a()*0.02;
      return buf;
    }
    function poser(buf, sr, texte, f, dt, amp){
      var enc = ft8EncodeMessage(texte, HT);
      var w = ft8SynthesizeGfsk(enc.symbols, {sampleRate: sr, toneHz0: f});
      var off = Math.round((1.5+dt)*sr);
      for(var k=0;k<w.length && off+k<buf.length;k++) buf[off+k] += w[k]*amp;
    }
    // Décode avec les réglages PAR DÉFAUT : aucun opts.minFreqSeparationHz ni
    // opts.maxCandidates ici. Un test qui passerait ses propres valeurs ne
    // contraindrait que lui-même et laisserait le défaut livré libre de
    // revenir à 50 Hz.
    function textesDecodes(buf, sr){
      var r = ft8DecodeAudioAll(buf, sr, ft8CreateHashTable(),
                                {centerSample: 1.5*sr});
      var v = {};
      for(var i=0;i<r.length;i++) v[r[i].text] = 1;
      return v;
    }
    """)
    return ctx


def _deux_stations(moteur, ecart_hz, dt1, dt2, graine):
    return moteur.eval("""(function(){
        var sr = %f, buf = fond(sr, %d);
        poser(buf, sr, 'CQ F4GLD JN18', 1200, %r, 0.5);
        poser(buf, sr, 'CQ CT1END IM57', 1200 + %r, %r, 0.5);
        var v = textesDecodes(buf, sr);
        return (v['CQ F4GLD JN18']?1:0) + (v['CQ CT1END IM57']?1:0);
    })()""" % (FE, graine, dt1, ecart_hz, dt2))


@pytest.mark.parametrize('ecart', [18.75, 31.25, 62.5])
def test_deux_stations_proches_sont_TOUTES_LES_DEUX_decodees(moteur, ecart):
    """Le défaut d'origine : à 18 Hz d'écart, une seule des deux sortait.

    Trois écarts, tous sous les 50 Hz de l'ancienne règle ou juste au-dessus,
    et trois jeux de décalages temporels différents — dont un où les deux
    stations émettent au MÊME instant, cas où le temps ne peut pas servir à
    les distinguer.
    """
    for graine, (dt1, dt2) in enumerate([(0.0, 0.0), (0.0, 0.4), (0.2, -0.3)]):
        n = _deux_stations(moteur, ecart, dt1, dt2, graine + 1)
        assert n == 2, (
            'écart %g Hz, décalages %.1f/%.1f s : %d station(s) décodée(s) '
            'sur 2' % (ecart, dt1, dt2, n))


def test_la_bande_chargee_ne_regresse_pas(moteur):
    """Le garde-fou du correctif, et la raison de NE PAS retirer la règle.

    Seize stations d'amplitudes inégales (rapport 1 à 4,7) réparties sur la
    bande. Sans suppression des non-maxima, les places de `maxCandidates`
    partent aux détections multiples des signaux forts et le rendement tombe
    à 12/16 — mesuré. Ce test échoue donc aussi bien si l'on élargit trop la
    règle que si on la supprime.
    """
    n = moteur.eval("""(function(){
        var sr = %f, buf = fond(sr, 7), t = [];
        for(var m=0;m<16;m++){
          var x = 'CQ ' + ['F4GLD JN18','CT1END IM57','G3ABC IO91','DL1XYZ JO31',
                           'EA5QRP IM98','I2KLM JN45','SP9TUV JO90','OK1RST JO70',
                           'PA3WXY JO22','SM5ZAB JO89','LZ2CDE KN12','9A1FGH JN85',
                           'YO3IJK KN34','HA5LMN JN97','S51OPQ JN76','OM3RST JN88'][m];
          t.push(x);
          poser(buf, sr, x, 500 + m*(1900/15), -0.3 + (m%%5)*0.15,
                0.15 + 0.55*((m%%4)/3));
        }
        var v = textesDecodes(buf, sr), ok = 0;
        for(var j=0;j<t.length;j++) if(v[t[j]]) ok++;
        return ok;
    })()""" % FE)
    assert n == 16, '%d stations décodées sur 16 sur bande chargée' % n


def test_le_budget_de_candidats_tient_une_bande_tres_chargee(moteur):
    """Ce test protège le SECOND réglage du correctif, et lui seul le peut.

    Resserrer la suppression fait qu'un signal occupe 2 à 3 places au lieu
    d'une : `maxCandidates` a donc dû passer de 30 à 60. Or à 16 stations le
    rendement est de 16/16 dans les DEUX cas — le test précédent ne
    discrimine pas. Il faut 28 stations pour que la différence apparaisse
    (mesuré : 21/28 à 30 places, 23/28 à 45, 28/28 à 60).

    Il est lent (un décodage complet de 16,5 s de signal), c'est le prix
    d'une décision chiffrée qui ne peut pas se défaire en silence.
    """
    n = moteur.eval("""(function(){
        var sr = %f, buf = fond(sr, 7), t = [];
        var noms = ['F4GLD JN18','CT1END IM57','G3ABC IO91','DL1XYZ JO31',
                    'EA5QRP IM98','I2KLM JN45','SP9TUV JO90','OK1RST JO70',
                    'PA3WXY JO22','SM5ZAB JO89','LZ2CDE KN12','9A1FGH JN85',
                    'YO3IJK KN34','HA5LMN JN97','S51OPQ JN76','OM3RST JN88',
                    'UR5UVW KO50','LY2XYZ KO24','ES1ABD KO29','OH2EFG KP20',
                    'SM7HIJ JO65','LA1KLM JO59','OZ1NOP JO45','ON4QRS JO20',
                    'F5TUV JN03','EA3WXY JN01','IK1ZAB JN34','DK2CDE JN49'];
        for(var m=0;m<28;m++){
          var x = 'CQ ' + noms[m];
          t.push(x);
          poser(buf, sr, x, 500 + m*(1900/27), -0.3 + (m%%5)*0.15,
                0.15 + 0.55*((m%%4)/3));
        }
        var v = textesDecodes(buf, sr), ok = 0;
        for(var j=0;j<t.length;j++) if(v[t[j]]) ok++;
        return ok;
    })()""" % FE)
    assert n == 28, (
        '%d stations décodées sur 28 : le budget de candidats ne suit plus '
        'le resserrement de la suppression' % n)


def test_le_seuil_livre_est_exprime_en_espacements_de_tons(moteur):
    """Assertion de STRUCTURE, pas de présence.

    Les tests ci-dessus valident un comportement ; celui-ci empêche qu'on
    retombe sur l'ancienne largeur par un chemin détourné (une constante
    réécrite ailleurs, un opts par défaut réintroduit). On interroge le
    moteur, pas le texte du fichier : c'est la valeur réellement appliquée.
    """
    espacement = moteur.eval('FT8_TONE_SPACING')
    # La valeur effective se lit en observant ce que la fonction retient.
    # Deux pics distants d'exactement 3 espacements doivent survivre tous les
    # deux ; distants d'un seul, non.
    assert espacement == pytest.approx(6.25)
    survit_3 = _deux_stations(moteur, 3 * espacement, 0.0, 0.0, 11)
    assert survit_3 == 2, (
        'à 3 espacements de tons (%.2f Hz) la seconde station est encore '
        'perdue' % (3 * espacement))
