# -*- coding: utf-8 -*-
"""Décodeur CW (logx_cwdecoder.js) — constat de la passe de vérification
complète du 09/08/2026 : le fichier est explicitement conçu pour être
« testable isolément » (commentaire ligne 34, export CommonJS dédié), et
documente lui-même en commentaire un bug réel déjà rencontré (dérive de
l'unité de temps qui finissait par ne plus reconnaître les espaces de mot,
_adaptUnit()) — mais n'avait pourtant AUCUN test dans ce dépôt avant ce
fichier.

POURQUOI CES TESTS SONT MOINS REPRÉSENTATIFS QUE ceux du décodeur RTTY
(test_rtty_decodeur.py) : le RTTY est généré par une machine à cadence FIXE
(45,45 bauds) — un signal synthétique EST un vrai signal RTTY. Le CW dépend
de la main de l'opérateur (irrégularités, fist, QRM) ; on ne teste ici que
la logique temporelle PURE (MorseTimingDecoder.pushEdge/_adaptUnit) avec des
durées parfaitement régulières, PAS le pipeline audio complet (Goertzel +
getUserMedia), qui dépend d'API navigateur (AudioContext, MediaStream)
absentes de py_mini_racer et de toute façon impossibles à exercer sans une
vraie carte son. goertzelMagnitude() elle-même est testée séparément, en
pur DSP (discrimination fréquentielle sur un signal synthétique), sans
passer par CwAudioDecoder.

Ce que ces tests NE prouvent PAS : le comportement en pile-up réel, avec
QRM, fading ou un fist irrégulier — voir l'avertissement honnête déjà
présent dans le fichier source lui-même (lignes 16-19)."""
import json
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_cwdecoder.js')

py_mini_racer = pytest.importorskip('py_mini_racer')


@pytest.fixture(scope='module')
def moteur():
    ctx = py_mini_racer.MiniRacer()
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    # Encodeur Morse PARFAIT (durées exactes, aucun bruit de timing) à partir
    # de MORSE_TABLE réelle du fichier -- pas une table Morse réimplémentée
    # à la main côté test, qui pourrait diverger silencieusement de la vraie.
    ctx.eval("""
    function morseEncodeEdges(texte, unitMs){
      var inv = {};
      for(var k in MORSE_TABLE) inv[MORSE_TABLE[k]] = k;
      var edges = [];
      texte.toUpperCase().split(' ').forEach(function(mot, wi){
        if(wi > 0) edges.push([false, unitMs*7]);
        var lettres = mot.split('');
        lettres.forEach(function(ch, li){
          if(li > 0) edges.push([false, unitMs*3]);
          var code = inv[ch];
          if(!code) return;
          code.split('').forEach(function(sym, si){
            if(si > 0) edges.push([false, unitMs]);
            edges.push([true, sym === '.' ? unitMs : unitMs*3]);
          });
        });
      });
      return edges;
    }
    function decodeTexte(texte, unitMs){
      var out = '';
      var dec = new MorseTimingDecoder(function(ch){ out += ch; });
      dec.unitMs = unitMs;
      dec.recentMarks = new Array(12).fill(unitMs);
      morseEncodeEdges(texte, unitMs).forEach(function(e){ dec.pushEdge(e[0], e[1]); });
      dec.flushIfIdle(unitMs*10);
      return out;
    }
    """)
    return ctx


# ─── Aller-retour texte -> timing -> décodage, à plusieurs vitesses ─────────

@pytest.mark.parametrize('texte,wpm', [
    ('CQ TEST', 20),
    ('SOS', 25),
    ('PARIS', 12),
    ('73 DE F4GLD', 18),
])
def test_aller_retour_texte_a_plusieurs_vitesses(moteur, texte, wpm):
    unit_ms = 1200.0 / wpm   # formule PARIS standard (unité=point en ms)
    decode = moteur.eval(f"decodeTexte({texte!r}, {unit_ms})")
    assert decode == texte


def test_espace_intra_mot_vs_inter_mot(moteur):
    """Un espace de 3 unités (inter-lettre) ne doit JAMAIS émettre ' ', un
    espace de 7 unités (inter-mot) doit toujours en émettre un — frontière
    exacte du code (durationMs >= unitMs*6, pushEdge ligne 87-89)."""
    decode = moteur.eval("decodeTexte('AB CD', 60)")
    assert decode == 'AB CD'
    assert decode.count(' ') == 1


# ─── pushEdge() : classification point/trait, cas limites ──────────────────

def test_pushedge_classification_point_vs_trait(moteur):
    """Seuil à 2x l'unité courante (commentaire ligne 80-81) : juste sous 2x
    -> point, juste au-dessus -> trait."""
    out = moteur.eval("""
    (function(){
      var buf = '';
      var dec = new MorseTimingDecoder(function(ch){ buf += ch; });
      dec.unitMs = 60; dec.recentMarks = new Array(12).fill(60);
      dec.pushEdge(true, 60 * 1.9);   // < 2u -> point
      dec.pushEdge(false, 60 * 3);    // ferme la lettre
      dec.flushIfIdle(1000);
      return buf;
    })()
    """)
    assert out == 'E'   # '.' == E
    out2 = moteur.eval("""
    (function(){
      var buf = '';
      var dec = new MorseTimingDecoder(function(ch){ buf += ch; });
      dec.unitMs = 60; dec.recentMarks = new Array(12).fill(60);
      dec.pushEdge(true, 60 * 2.1);   // > 2u -> trait
      dec.pushEdge(false, 60 * 3);
      dec.flushIfIdle(1000);
      return buf;
    })()
    """)
    assert out2 == 'T'   # '-' == T


def test_flushifidle_ferme_le_dernier_caractere_sans_transition_suivante(moteur):
    """Si l'émetteur s'arrête net (dernier caractère jamais 'fermé' par une
    transition suivante), flushIfIdle() doit quand même le livrer -- sans
    ça le dernier caractère resterait bloqué en mémoire indéfiniment
    (commentaire ligne 94-96 du fichier)."""
    out = moteur.eval("""
    JSON.stringify((function(){
      var buf = '';
      var dec = new MorseTimingDecoder(function(ch){ buf += ch; });
      dec.unitMs = 60; dec.recentMarks = new Array(12).fill(60);
      dec.pushEdge(true, 60);     // point
      dec.pushEdge(false, 30);    // silence bref, PAS encore assez pour clore
      var avant = buf;
      dec.flushIfIdle(60*3);
      return {avant: avant, apres_flush: buf};
    })())
    """)
    out = json.loads(out)
    assert out['avant'] == ''
    assert out['apres_flush'] == 'E'


# ─── _adaptUnit() : résistance à la dérive (bug réel documenté en commentaire) ─

def test_adaptunit_resiste_a_une_serie_de_traits(moteur):
    """Bug réel déjà rencontré et documenté dans le fichier (lignes 47-61) :
    une MOYENNE de fenêtre se laisse entraîner vers le haut par des traits
    mal classés en points, ce qui finit par empêcher toute reconnaissance
    d'espace de mot. L'estimation par MINIMUM (implémentation actuelle) doit
    résister à une longue série de traits consécutifs (aucun point) sans que
    l'unité ne dérive vers le haut -- ce test aurait échoué avec une
    implémentation à base de moyenne."""
    unit_final = moteur.eval("""
    (function(){
      var dec = new MorseTimingDecoder(function(){});
      dec.unitMs = 60; dec.recentMarks = new Array(12).fill(60);
      // 10 traits consécutifs (180ms = 3x l'unité de départ), comme une
      // rafale de M/O -- aucun point pour "rafraîchir" le minimum.
      for(var i=0;i<10;i++){ dec.pushEdge(true, 180); dec.pushEdge(false, 60); }
      return dec.unitMs;
    })()
    """)
    assert unit_final < 90, (
        f"l'unité a dérivé vers le haut ({unit_final}ms, départ 60ms) sous "
        "une série de traits -- symptôme exact du bug déjà documenté dans "
        "le fichier source")


def test_adaptunit_redescend_des_qu_un_vrai_point_arrive(moteur):
    """Un point authentique (même isolé au milieu de traits) doit pouvoir
    faire redescendre le minimum -- contrairement aux traits, qui ne
    peuvent jamais le faire remonter à tort."""
    result = moteur.eval("""
    JSON.stringify((function(){
      var dec = new MorseTimingDecoder(function(){});
      dec.unitMs = 60; dec.recentMarks = new Array(12).fill(90);  // fenêtre "polluée"
      for(var i=0;i<5;i++){ dec.pushEdge(true, 180); dec.pushEdge(false, 60); }
      var apres_traits = dec.unitMs;
      dec.pushEdge(true, 60);   // un vrai point à l'unité d'origine
      var apres_point = dec.unitMs;
      return [apres_traits, apres_point];
    })())
    """)
    unit_after_dashes, unit_after_dot = json.loads(result)
    assert unit_after_dot < unit_after_dashes


# ─── goertzelMagnitude() : discrimination fréquentielle pure ────────────────

def test_goertzel_discrimine_la_frequence_cible(moteur):
    """Signal sinusoïdal pur à la fréquence CIBLE -> magnitude nettement plus
    élevée qu'à une fréquence éloignée -- propriété de base d'un filtre
    Goertzel monofréquence, sans laquelle le décodeur audio ne pourrait pas
    isoler le ton CW du reste du spectre (voix, bruit)."""
    ratio = moteur.eval("""
    (function(){
      var sr = 8000, n = 512, targetFreq = 650, offFreq = 1200;
      var onTone = new Float64Array(n), offTone = new Float64Array(n);
      for(var i=0;i<n;i++){
        onTone[i] = Math.sin(2*Math.PI*targetFreq*i/sr);
        offTone[i] = Math.sin(2*Math.PI*offFreq*i/sr);
      }
      var magOn = goertzelMagnitude(onTone, sr, targetFreq);
      var magOff = goertzelMagnitude(offTone, sr, targetFreq);
      return magOn / magOff;
    })()
    """)
    assert ratio > 5, f"discrimination fréquentielle insuffisante (ratio {ratio})"


def test_goertzel_silence_donne_magnitude_quasi_nulle(moteur):
    mag = moteur.eval("""
    (function(){
      var n = 512;
      var silence = new Float64Array(n);   // tout à zéro
      return goertzelMagnitude(silence, 8000, 650);
    })()
    """)
    assert mag < 1e-9


# ─── Table Morse : sanité de base ───────────────────────────────────────────

def test_table_morse_sanite():
    with open(JS, encoding='utf-8') as f:
        src = f.read()
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(src)
    assert ctx.eval("MORSE_TABLE['.-']") == 'A'
    assert ctx.eval("MORSE_TABLE['...']") == 'S'
    assert ctx.eval("MORSE_TABLE['---']") == 'O'
    assert ctx.eval("MORSE_TABLE['...-.-']") == '<SK>'
