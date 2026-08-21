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

    // ─── Pipeline audio complet (CwAudioDecoder._onBlock), sans navigateur ──
    // performance.now() n'existe pas en V8 nu (py_mini_racer) -- stub piloté
    // à la main pour un temps simulé déterministe entre les blocs.
    var performance = { _t: 0, now: function(){ return this._t; } };
    function __advanceTime(ms){ performance._t += ms; }

    // CwAudioDecoder.start() exige getUserMedia/AudioContext (absents ici) ;
    // _onBlock() ne lit que this.ctx.sampleRate -- un objet minimal suffit,
    // pas besoin de passer par start() pour exercer le pipeline DSP réel.
    function makeAudioDecoder(freq, onChar, onLevel){
      var dec = new CwAudioDecoder({freq: freq, onChar: onChar, onLevel: onLevel || function(){}});
      dec.ctx = {sampleRate: 44100};
      dec.edgeStartMs = 0;
      return dec;
    }

    // Fréquence calée EXACTEMENT sur un bin Goertzel pour sampleRate=44100,
    // blockSize=512 (k=8 -> 689,0625 Hz) -- élimine la fuite spectrale d'un
    // léger désalignement de bin (le vrai ton CW à 650 Hz n'y échappe pas
    // non plus, mais ce n'est pas ce que ces tests-ci cherchent à mesurer) :
    // sans ça, la magnitude Goertzel d'un ton FAIBLE s'écarte trop de
    // l'estimation théorique amplitude/2 pour choisir une marge de seuil
    // fiable. Sert UNIQUEMENT aux tests qui comparent une amplitude précise
    // à un seuil (AGC) ; les autres pipelines audio de ce fichier restent à
    // 650 Hz (fréquence réelle par défaut de l'UI).
    var BIN_FREQ = 8 * 44100 / 512;

    // Pousse `durationMs` de ton (amplitude=0 -> silence) dans _onBlock(),
    // en avançant l'horloge simulée d'un bloc à chaque itération -- même
    // granularité que le vrai pipeline (blockSize/sampleRate).
    function feedTone(dec, amplitude, freq, durationMs){
      var sr = dec.ctx.sampleRate, blockSize = dec.blockSize;
      var blockMs = blockSize / sr * 1000;
      var nBlocks = Math.max(1, Math.round(durationMs / blockMs));
      for(var b=0; b<nBlocks; b++){
        var samples = new Float64Array(blockSize);
        if(amplitude > 0){
          for(var i=0;i<blockSize;i++) samples[i] = amplitude * Math.sin(2*Math.PI*freq*i/sr);
        }
        __advanceTime(blockMs);
        dec._onBlock(samples);
      }
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


# ─── Démarrage à froid (constructeur, sans override manuel de unitMs) ───────
# Contrairement aux tests ci-dessus qui posent unitMs/recentMarks à la main
# (donc masquent toute mauvaise hypothèse de DÉPART), ceux-ci exercent le
# `new MorseTimingDecoder(cb)` réel, tel qu'utilisé par CwAudioDecoder à
# chaque clic sur "Démarrer" -- pour vérifier l'hypothèse initiale (~27 MPM,
# voir commentaire du constructeur) plutôt que de la contourner.

@pytest.mark.parametrize('texte,wpm', [
    ('OM DE F4GLD', 28),   # 1re lettre = trait pur (OM commence par --- ), vitesse concours
    ('MOTO', 32),          # que des traits/points mélangés, vitesse rapide
    ('CQ TEST', 35),       # borne haute de la plage concours réaliste
    ('PARIS', 15),         # borne basse de la plage concours réaliste
])
def test_demarrage_a_froid_vitesse_concours(moteur, texte, wpm):
    """Bug réel trouvé en lecture de code (constructeur MorseTimingDecoder,
    lignes 39-63 du fichier source) : l'ancienne hypothèse de départ (80ms,
    ~15 MPM) plaçait le seuil point/trait à 160ms -- un trait envoyé à plus
    de ~22 MPM (durée < 160ms) était alors classé par erreur comme un point
    tant qu'aucun point réel plus court n'était apparu pour corriger la
    fenêtre glissante. Résultat concret : les premières lettres d'un message
    envoyé à une vitesse concours normale (25-35 MPM) pouvaient être décodées
    n'importe comment dès le début de CHAQUE session d'écoute -- indépendant
    du niveau du signal, ce qui correspond au symptôme "décodage inefficace
    même avec un signal fort". Ce test utilise le vrai constructeur (pas de
    unitMs/recentMarks posés à la main) pour vérifier le comportement à
    froid tel que rencontré en usage réel."""
    unit_ms = 1200.0 / wpm
    decode = moteur.eval(f"""
    (function(){{
      var out = '';
      var dec = new MorseTimingDecoder(function(ch){{ out += ch; }});
      morseEncodeEdges({texte!r}, {unit_ms}).forEach(function(e){{ dec.pushEdge(e[0], e[1]); }});
      dec.flushIfIdle({unit_ms}*10);
      return out;
    }})()
    """)
    assert decode == texte


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


# ─── CwAudioDecoder._onBlock() : pipeline Goertzel + seuil AGC + timing ─────
# AVANT ce chantier (15/08/2026), CwAudioDecoder n'était exercé par AUCUN
# test -- seuls MorseTimingDecoder et goertzelMagnitude l'étaient séparément
# (voir le docstring en tête de fichier). Diagnostic réel (échec total du
# décodage sur IC-7300) : le seuil de détection était en ÉCHELLE ABSOLUE
# (`noiseFloor*2.8 + 0.003`), calibré empiriquement contre des tons de test
# synthétiques à AMPLITUDE MAXIMALE (1.0, magnitude Goertzel ~0.5) -- un
# signal radio réel capté via carte son/interface plafonne très souvent
# bien plus bas et pouvait ne JAMAIS dépasser ce plancher absolu. Corrigé
# par un seuil RELATIF (AGC : pic de signal suivi, seuil proportionnel à
# l'écart bruit/pic observé -- mirror de fldigi, cw.cxx).

def test_signal_faible_realiste_est_decode_malgre_un_ancien_seuil_trop_haut(moteur):
    """Amplitude 0.004 (magnitude Goertzel ~0.002) : nettement sous l'ancien
    plancher absolu (~0.003 dès que le bruit de fond est propre) -- ce test
    aurait échoué (silence total, buf vide) avec l'ancien seuil. Le nouveau
    seuil relatif doit décoder ce signal comme n'importe quel autre."""
    out = moteur.eval("""
    (function(){
      var out = '';
      var dec = makeAudioDecoder(BIN_FREQ, function(ch){ out += ch; });
      var unitMs = 80;   // 15 MPM, vitesse prudente pour laisser l'AGC s'établir
      // 'E' = un point, précédé d'un peu de silence pour amorcer noiseFloor/agcPeak.
      feedTone(dec, 0, BIN_FREQ, unitMs*4);
      feedTone(dec, 0.004, BIN_FREQ, unitMs);
      feedTone(dec, 0, BIN_FREQ, unitMs*10);   // assez de silence pour clore le caractère
      return out;
    })()
    """)
    assert out == 'E', f"signal faible non décodé (buf={out!r}) -- seuil encore trop haut"


def test_silence_pur_ne_declenche_jamais_de_fausse_marque(moteur):
    """Garde-fou symétrique : un seuil relatif trop permissif ferait crépiter
    le décodeur sur du silence pur (bruit numérique quasi nul ici) -- aucun
    caractère ne doit jamais en sortir."""
    out = moteur.eval("""
    (function(){
      var out = '';
      var dec = makeAudioDecoder(650, function(ch){ out += ch; });
      feedTone(dec, 0, 650, 3000);   // 3s de silence pur
      return out;
    })()
    """)
    assert out == ''


def test_un_signal_plus_fort_reste_decode_apres_le_passage_au_seuil_relatif(moteur):
    """Non-régression à l'AUTRE bout de l'échelle : un signal fort (amplitude
    proche de celle des anciens tons de test) doit continuer à être décodé
    correctement -- le passage au seuil relatif ne doit pas casser le cas
    qui marchait déjà."""
    out = moteur.eval("""
    (function(){
      var out = '';
      var dec = makeAudioDecoder(650, function(ch){ out += ch; });
      var unitMs = 60;   // 20 MPM
      feedTone(dec, 0, 650, unitMs*4);
      feedTone(dec, 0.8, 650, unitMs);        // point
      feedTone(dec, 0, 650, unitMs);          // espace intra-caractère
      feedTone(dec, 0.8, 650, unitMs*3);      // trait
      feedTone(dec, 0, 650, unitMs*10);
      return out;
    })()
    """)
    assert out == 'A'   # .- = A


# ─── Rejet des impulsions de bruit courtes (pushEdge) ───────────────────────

def test_une_impulsion_de_bruit_courte_est_ignoree_sans_corrompre_le_caractere(moteur):
    """Un blip de bruit HF (crachement statique, QRM bref) plus court que la
    moitié de l'unité courante ne doit produire NI caractère parasite NI
    perturbation de la classification -- 'E' (un point) doit rester 'E' même
    précédé d'un micro-blip largement sous le seuil de rejet."""
    out = moteur.eval("""
    JSON.stringify((function(){
      var dec = new MorseTimingDecoder(function(ch){ out += ch; });
      var out = '';
      dec.onChar = function(ch){ out += ch; };
      dec.unitMs = 60; dec.recentMarks = new Array(12).fill(60);
      dec.pushEdge(true, 5);      // blip de bruit : 5ms << 0.5*60=30ms -> rejeté
      dec.pushEdge(false, 5);
      dec.pushEdge(true, 60);     // vrai point
      dec.pushEdge(false, 180);
      dec.flushIfIdle(1000);
      return {texte: out, unitMs: dec.unitMs};
    })())
    """)
    result = json.loads(out)
    assert result['texte'] == 'E'
    assert result['unitMs'] == 60, (
        f"le blip de bruit a modifié unitMs ({result['unitMs']}, attendu 60) -- "
        "il n'aurait dû avoir AUCUN effet sur l'estimation de vitesse")


def test_une_rafale_de_bruit_ne_fait_pas_deriver_lestimation_de_vitesse(moteur):
    """Preuve directe du mécanisme de corruption décrit dans le diagnostic :
    une série de blips de bruit courts, si elle n'était PAS rejetée, ferait
    immédiatement chuter le minimum de la fenêtre glissante (_adaptUnit) et
    corromprait tout décodage suivant. Après rejet, l'unité doit rester
    inchangée malgré 10 blips consécutifs."""
    unit_final = moteur.eval("""
    (function(){
      var dec = new MorseTimingDecoder(function(){});
      dec.unitMs = 60; dec.recentMarks = new Array(12).fill(60);
      for(var i=0;i<10;i++){ dec.pushEdge(true, 3); dec.pushEdge(false, 3); }
      return dec.unitMs;
    })()
    """)
    assert unit_final == 60, (
        f"l'unité a dérivé ({unit_final}ms, départ 60ms) sous une rafale de "
        "bruit qui aurait dû être intégralement rejetée")


def test_un_point_authentique_juste_au_dessus_du_seuil_de_rejet_reste_valide(moteur):
    """Non-régression : un point réel un peu court (fist rapide/irrégulier)
    mais AU-DESSUS du seuil de rejet (0.5u) doit continuer à être décodé
    normalement -- le rejet ne doit viser QUE les impulsions implausiblement
    courtes, pas resserrer la classification point/trait existante."""
    out = moteur.eval("""
    (function(){
      var out = '';
      var dec = new MorseTimingDecoder(function(ch){ out += ch; });
      dec.unitMs = 60; dec.recentMarks = new Array(12).fill(60);
      dec.pushEdge(true, 60 * 0.6);   // > 0.5u (30ms) -> pas rejeté ; < 2u -> point
      dec.pushEdge(false, 180);
      dec.flushIfIdle(1000);
      return out;
    })()
    """)
    assert out == 'E'


# ─── CwFreqDetector : détection automatique du ton CW (retour F4GLD 21/08/2026) ─
# « c'est compliqué pour un novice, on peut pas faciliter ce réglage ? » --
# CwFreqDetector écoute plusieurs fréquences candidates À LA FOIS et retient
# celle qui montre un vrai RYTHME de signal (plusieurs transitions ON/OFF),
# jamais une simple porteuse continue (hum/DC offset à une fréquence
# étrangère) ni du bruit large bande sans fréquence dominante. Ces tests
# poussent des blocs synthétiques directement dans detector.feed() --
# CwFreqDetector ne dépend d'aucune API navigateur (comme goertzelMagnitude),
# testable en pur DSP.

def _detector_helpers(moteur):
    # Réutilise morseEncodeEdges() déjà défini dans le fixture `moteur`
    # (préambule ci-dessus) -- génère de VRAIES séquences d'édges Morse
    # depuis MORSE_TABLE réelle, pas un motif point/trait inventé à la
    # main qui ne correspondrait à aucune lettre (piège trouvé en le
    # faisant : la 1re version de ces tests utilisait un tel motif, qui ne
    # produisait plus AUCUN caractère valide une fois la validation par
    # décodage réel ajoutée à best() -- tous les tests en dessous
    # échouaient, pas seulement le nouveau).
    moteur.eval("""
    // Pousse `durationMs` de ton (amplitude=0 -> silence) à `freq` Hz dans
    // detector.feed() -- même granularité de bloc que le vrai pipeline
    // (blockSize=512, comme CwAudioDecoder).
    function feedDetector(detector, sr, blockSize, amplitude, freq, durationMs){
      var blockMs = blockSize / sr * 1000;
      var nBlocks = Math.max(1, Math.round(durationMs / blockMs));
      for(var b=0; b<nBlocks; b++){
        var samples = new Float64Array(blockSize);
        if(amplitude > 0){
          for(var i=0;i<blockSize;i++) samples[i] = amplitude * Math.sin(2*Math.PI*freq*i/sr);
        }
        detector.feed(samples, sr);
      }
    }
    // Pousse une liste d'edges [isMark, durationMs] (format morseEncodeEdges)
    // dans le détecteur, à `freq` Hz et `amplitude` donnée.
    function feedDetectorEdges(detector, sr, blockSize, freq, edges, amplitude){
      amplitude = (amplitude === undefined) ? 1.0 : amplitude;
      edges.forEach(function(e){
        feedDetector(detector, sr, blockSize, e[0] ? amplitude : 0, freq, e[1]);
      });
    }
    // Encode un VRAI texte en Morse (morseEncodeEdges, table réelle) et le
    // pousse dans le détecteur à `freq` Hz -- ce que produit ce signal DOIT
    // être décodable, contrairement à un motif point/trait/silence arbitraire.
    function feedDetectorText(detector, sr, blockSize, freq, texte, unitMs, amplitude){
      feedDetectorEdges(detector, sr, blockSize, freq, morseEncodeEdges(texte, unitMs), amplitude);
    }
    """)


def test_detector_trouve_la_frequence_dun_signal_module(moteur):
    """Cas nominal : un vrai texte encodé en Morse (donc décodable) à une
    fréquence précise -- doit être identifié, et RIEN d'autre. Fréquence
    choisie EXACTEMENT sur une candidate de la grille (pas de 100 Hz) : la
    fuite spectrale entre candidates voisines (résolution Goertzel ~86 Hz
    pour blockSize=512@44.1kHz) n'est pas ce que ce test cherche à isoler."""
    _detector_helpers(moteur)
    found = moteur.eval("""
    (function(){
      var d = new CwFreqDetector();
      feedDetectorText(d, 44100, 512, 700, 'CQ TEST DE F4GLD', 60);
      return d.best();
    })()
    """)
    assert found == 700


def test_detector_ignore_une_porteuse_continue_a_frequence_etrangere(moteur):
    """Un ton CONSTANT (jamais OFF) à une fréquence étrangère -- ronflement
    secteur, offset DC, porteuse parasite -- ne doit JAMAIS être retenu :
    il ne franchit jamais assez de transitions ON/OFF (reste "on" en
    continu), contrairement à un vrai signal Morse rythmé."""
    _detector_helpers(moteur)
    found = moteur.eval("""
    (function(){
      var d = new CwFreqDetector();
      feedDetector(d, 44100, 512, 0.8, 500, 3000);   // 500 Hz en continu, 3s
      return d.best();
    })()
    """)
    assert found is None


def test_detector_ignore_le_silence_pur(moteur):
    """Rien n'est émis nulle part -- aucune fréquence ne doit gagner par
    défaut, mieux vaut le dire honnêtement qu'inventer un résultat."""
    _detector_helpers(moteur)
    found = moteur.eval("""
    (function(){
      var d = new CwFreqDetector();
      feedDetector(d, 44100, 512, 0, 650, 2000);   // amplitude 0 = silence
      return d.best();
    })()
    """)
    assert found is None


def test_detector_exige_un_minimum_de_transitions(moteur):
    """Un unique blip isolé (une seule marque, une seule transition ON puis
    OFF) ne doit PAS suffire à désigner une fréquence -- un parasite ou un
    craquement statique produirait sinon un faux résultat convaincant."""
    _detector_helpers(moteur)
    found = moteur.eval("""
    (function(){
      var d = new CwFreqDetector();
      feedDetector(d, 44100, 512, 1.0, 700, 60);   // UN SEUL point, rien d'autre
      feedDetector(d, 44100, 512, 0, 700, 200);
      return d.best();
    })()
    """)
    assert found is None


def test_detector_departage_a_egalite_de_caracteres_valides_par_le_ratio(moteur):
    """Deux candidates arrivent à ÉGALITÉ de caractères valides décodés --
    le rapport pic/plancher (agcPeak/noiseFloor) doit alors départager,
    pas la première rencontrée dans la liste. État interne posé DIRECTEMENT
    plutôt que rejoué via feed() avec deux tons audio réels : le filtre
    Goertzel n'est pas fenêtré (fenêtre rectangulaire, lobes secondaires
    larges) -- un ton assez fort et assez long finit par fuir de façon
    quasi identique dans TOUS les candidats sur plusieurs secondes de
    calibration (constaté en le testant), ce qui n'isole plus du tout le
    départage lui-même. Ce n'est de toute façon pas le scénario réel : un
    novice n'a qu'UN signal à la fois, pas deux textes complets simultanés
    à des fréquences différentes -- la sélectivité fréquentielle sur un
    signal réel est déjà couverte par les tests ci-dessus."""
    found = moteur.eval("""
    (function(){
      var d = new CwFreqDetector();
      var a = d.stats.get(600), b = d.stats.get(800);
      a.transitions = b.transitions = 10;
      a.totalChars = b.totalChars = 5;
      a.validChars = b.validChars = 4;    // égalité de caractères valides
      a.agcPeak = 0.02; a.noiseFloor = 0.001;   // rapport faible
      b.agcPeak = 0.20; b.noiseFloor = 0.001;   // rapport net -> doit gagner
      return d.best();
    })()
    """)
    assert found == 800


def test_detector_ecarte_une_vitesse_implausible_meme_a_bon_ratio(moteur):
    """Test unitaire ciblé du second garde-fou (CW_DETECT_MAX_WPM), isolé
    du ratio de validité -- même technique d'état posé directement qu'au
    test précédent : une candidate à vitesse implausible (50 MPM, au-delà
    de tout trafic CW manuel réaliste) ne doit jamais l'emporter sur une
    candidate à vitesse plausible, même si son ratio de validité et son
    rapport pic/plancher sont MEILLEURS."""
    found = moteur.eval("""
    (function(){
      var d = new CwFreqDetector();
      var rapide = d.stats.get(300), plausible = d.stats.get(700);
      rapide.transitions = plausible.transitions = 20;
      rapide.totalChars = 10; rapide.validChars = 10;       // 100% valides
      rapide.decoder.wpm = 50;                              // implausible
      plausible.totalChars = 8; plausible.validChars = 6;   // 75% valides, sous rapide
      plausible.decoder.wpm = 22;                           // plausible
      rapide.agcPeak = 0.5; rapide.noiseFloor = 0.001;       // rapport meilleur aussi
      plausible.agcPeak = 0.05; plausible.noiseFloor = 0.001;
      return d.best();
    })()
    """)
    assert found == 700


def test_detector_prefere_du_vrai_morse_a_un_rythme_non_decodable(moteur):
    """Reproduction du cas réel (F4GLD, 21/08/2026) : une première version de
    ce détecteur, qui ne se fiait qu'au rapport pic/plancher, avait
    verrouillé sur 300 Hz (la limite basse de la plage de candidates) au
    lieu du vrai ton CW -- résultat jugé « pas concluant » par l'opérateur
    (texte décodé toujours illisible ensuite). Ici : un rythme ON/OFF
    IRRÉGULIER à 300 Hz (assez de transitions pour franchir CW_DETECT_MIN_
    TRANSITIONS, silences trop courts pour jamais fermer un caractère --
    un bourdonnement/souffle de micro modulé produit exactement ce genre de
    rythme sans respecter aucune proportion point/trait/espace) doit être
    écarté au profit d'un texte RÉELLEMENT décodable à 700 Hz, même si le
    rythme à 300 Hz a un rapport pic/plancher plus élevé."""
    _detector_helpers(moteur)
    found = moteur.eval("""
    (function(){
      var d = new CwFreqDetector();
      // 300 Hz : rythme irrégulier, amplitude PLUS FORTE que le vrai signal,
      // mais silences de 20 ms -- jamais assez pour clore un caractère
      // (loin sous le seuil inter-lettre ~2 unités) -- s'accumule en UN seul
      // buffer géant qui ne correspond à aucune entrée de MORSE_TABLE.
      var bruit = [];
      for(var i=0; i<10; i++){ bruit.push([true, 35 + (i%3)*15]); bruit.push([false, 20]); }
      feedDetectorEdges(d, 44100, 512, 300, bruit, 1.0);
      // 700 Hz : vrai texte, amplitude plus faible -- doit quand même gagner.
      feedDetectorText(d, 44100, 512, 700, 'CQ TEST DE F4GLD', 60, 0.4);
      return d.best();
    })()
    """)
    assert found == 700


def test_detector_ecarte_un_bruit_hache_qui_passe_le_ratio_de_validite(moteur):
    """Reproduction EXACTE du symptôme observé en direct chez F4GLD le
    21/08/2026 (contre-épreuve du correctif ci-dessus, insuffisant seul) :
    des impulsions COURTES (15-24 ms) et irrégulières, avec un long silence
    forçant la fermeture de chaque caractère, franchissent bel et bien
    CW_DETECT_MIN_VALID_RATIO -- en Morse, TOUTE combinaison de 1 à 3
    symboles est une lettre valide par construction du code (E/T à 1
    symbole, I/A/N/M à 2, les 8 combinaisons de 3 couvrent D/U/S/W/G/R/O/K
    en entier), donc un bruit haché en impulsions courtes produit surtout
    des caractères "valides" sans être du Morse. Mesuré : ~51 % de
    caractères valides (au-dessus du seuil 50 %) ET ~52 MPM -- calibré à
    la main pour reproduire ce cas précis, pas une coïncidence de vitesse
    de test. Seul le second garde-fou (vitesse plausible) l'écarte : SANS
    lui, ce candidat gagnerait par défaut (rien d'autre en lice) au lieu
    du null honnête attendu ici."""
    _detector_helpers(moteur)
    found = moteur.eval("""
    (function(){
      var d = new CwFreqDetector();
      var bruit = [];
      for(var i=0; i<30; i++){
        bruit.push([true, 15 + (i%4)*3]);
        bruit.push([false, 10 + (i%3)*2]);
        bruit.push([false, 200]);   // force la fermeture de chaque caractere
      }
      feedDetectorEdges(d, 44100, 512, 300, bruit, 1.0);
      return d.best();
    })()
    """)
    assert found is None


def test_detector_exige_une_proportion_minimale_de_caracteres_valides(moteur):
    """Une candidate qui accumule BEAUCOUP de caractères mais MAJORITAIREMENT
    invalides (proportion sous CW_DETECT_MIN_VALID_RATIO) ne doit jamais
    l'emporter sur une candidate avec MOINS de caractères mais TOUS valides
    -- sans ce garde-fou, le classement par NOMBRE de caractères valides
    (voir test précédent) laisserait gagner un flux bruyant qui décode
    beaucoup mais mal, simplement parce qu'il a eu plus de temps/de
    transitions pour accumuler du volume. État interne posé directement
    (même raison que le test de départage ci-dessus)."""
    found = moteur.eval("""
    (function(){
      var d = new CwFreqDetector();
      var bruyant = d.stats.get(300), reel = d.stats.get(700);
      bruyant.transitions = reel.transitions = 20;
      bruyant.totalChars = 20; bruyant.validChars = 8;    // 40% -- sous le seuil
      reel.totalChars = 5; reel.validChars = 5;           // 100% -- au-dessus, mais MOINS nombreux
      bruyant.agcPeak = 0.5; bruyant.noiseFloor = 0.001;  // rapport élevé en plus, ne doit pas suffire
      reel.agcPeak = 0.05; reel.noiseFloor = 0.001;
      return d.best();
    })()
    """)
    assert found == 700


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
