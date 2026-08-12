// ─── DÉCODEUR CW (Morse → texte, temps réel, 100% navigateur) ───────────────
// Écoute l'AUDIO DE RÉCEPTION de la radio (câble audio virtuel ou interface
// dédiée vers l'entrée micro du PC — même principe que le keyer vocal, mais
// dans l'autre sens : radio → PC au lieu de PC → radio) et affiche le texte
// décodé en direct. Tout tourne dans le navigateur via l'API Web Audio, sans
// aller-retour serveur.
//
// Principe (pipeline DSP standard, rien d'exotique) :
//  1. Goertzel monofréquence calé sur le ton CW (bien plus robuste qu'une
//     détection d'enveloppe large bande : rejette la voix/le bruit hors bande)
//  2. Seuil ADAPTATIF (plancher de bruit suivi en continu) -> signal ON/OFF
//  3. Durées des impulsions/espaces -> classification point/trait/espace par
//     rapport à une unité de temps elle-même adaptative (poursuit la vitesse)
//  4. Table Morse -> caractères
//
// AVERTISSEMENT HONNÊTE (voir aussi la note affichée dans l'UI) : un
// décodeur de ce type reste très en retrait de l'oreille humaine dès qu'il y a
// du QRM, du fading ou un pileup serré — correct sur du CW propre et pas trop
// rapide, pas un substitut à l'entraînement pour du trafic difficile.

const MORSE_TABLE = {
  '.-':'A','-...':'B','-.-.':'C','-..':'D','.':'E','..-.':'F','--.':'G',
  '....':'H','..':'I','.---':'J','-.-':'K','.-..':'L','--':'M','-.':'N',
  '---':'O','.--.':'P','--.-':'Q','.-.':'R','...':'S','-':'T','..-':'U',
  '...-':'V','.--':'W','-..-':'X','-.--':'Y','--..':'Z',
  '-----':'0','.----':'1','..---':'2','...--':'3','....-':'4',
  '.....':'5','-....':'6','--...':'7','---..':'8','----.':'9',
  '.-.-.-':'.',  '--..--':',',  '..--..':'?',  '-..-.':'/',
  '-...-':'=',  '.-.-.':'+',  '-.--.':'(',  '-.--.-':')',
  '.-...':'<AS>', '...-.-':'<SK>', '-...-.-':'<BK>', '.-.-':'<AR>',
  '-.-.-':'<KA>', '...-.':'<SN>',
};

// ─── Décodeur temporel pur (aucune dépendance audio — testable isolément) ───
// pushEdge(isMark, durationMs) : appelé à chaque transition ON->OFF ou
// OFF->ON avec la durée du segment qui vient de se terminer. onChar(ch)
// est appelé pour chaque caractère décodé (ou ' ' pour un espace de mot).
class MorseTimingDecoder {
  constructor(onChar){
    this.onChar = onChar || (()=>{});
    this.unitMs = 80;                    // ~15 mots/min au départ, s'adapte ensuite
    this.recentMarks = new Array(12).fill(80);  // fenêtre glissante, sert à estimer le point
    this.buffer = '';                    // points/traits accumulés du caractère en cours
    this.wpm = 15;
  }

  // Réestime l'unité de temps (durée d'un point) via le MINIMUM d'une fenêtre
  // glissante de marques récentes — PAS une moyenne sur tout ce qui est
  // classé "court". Une moyenne se laisse entraîner vers le haut dès qu'un
  // TRAIT est classé par erreur comme un point (ça arrive : bruit, fist
  // irrégulier) : ce point mesuré "trop long" pousse l'unité vers le haut,
  // ce qui rend le PROCHAIN trait encore plus susceptible d'être mal classé
  // -> boucle de rétroaction qui fait dériver l'unité indéfiniment (vérifié
  // par test : un signal propre finissait par ne plus reconnaître aucun
  // espace de mot après quelques lettres). Un minimum est immunisé contre
  // ça : un trait mal classé ne peut JAMAIS tirer un minimum vers le haut,
  // seul un vrai point plus court peut le faire descendre. Limite connue et
  // acceptée : une longue série de traits consécutifs sans aucun point (rare
  // en trafic réel — même RST/n° de série ont presque toujours un point
  // quelque part) peut temporairement fausser l'estimation jusqu'au
  // prochain point.
  _adaptUnit(markMs){
    this.recentMarks.push(markMs);
    if(this.recentMarks.length > 12) this.recentMarks.shift();
    const minRecent = Math.min(...this.recentMarks);
    this.unitMs = this.unitMs * 0.6 + minRecent * 0.4;
    this.unitMs = Math.max(20, Math.min(300, this.unitMs));  // 4-60 mots/min plausible
    this.wpm = Math.round(1200 / this.unitMs);
  }

  _flushChar(){
    if(!this.buffer) return;
    const ch = MORSE_TABLE[this.buffer] || '�';
    this.onChar(ch);
    this.buffer = '';
  }

  pushEdge(isMark, durationMs){
    if(isMark){
      // Point vs trait : seuil à 2x l'unité courante (point=1, trait=3 -> le
      // milieu naturel est à 2).
      this.buffer += (durationMs < this.unitMs * 2) ? '.' : '-';
      this._adaptUnit(durationMs);
    } else {
      // Espace : intra-caractère (<2u) ignoré, inter-caractère (2-6u) ferme
      // la lettre, inter-mot (>6u) ferme la lettre ET émet un espace.
      if(durationMs >= this.unitMs * 2){
        this._flushChar();
        if(durationMs >= this.unitMs * 6) this.onChar(' ');
      }
    }
  }

  // À appeler périodiquement pendant un silence prolongé (fin de mot/lettre
  // qui ne serait jamais "fermée" par une transition suivante si l'émetteur
  // s'arrête) — sans ça le dernier caractère resterait bloqué en mémoire.
  flushIfIdle(idleMs){
    if(idleMs >= this.unitMs * 2) this._flushChar();
  }
}

// ─── Détecteur Goertzel monofréquence ────────────────────────────────────────
// Magnitude du signal à `targetFreq` sur un bloc de `blockSize` échantillons —
// bien moins cher qu'une FFT complète pour une seule fréquence, exactement ce
// dont on a besoin ici (le ton CW est une porteuse pure, pas un spectre large).
function goertzelMagnitude(samples, sampleRate, targetFreq){
  const n = samples.length;
  const k = Math.round(n * targetFreq / sampleRate);
  const w = (2 * Math.PI / n) * k;
  const cosine = Math.cos(w), sine = Math.sin(w), coeff = 2 * cosine;
  let q0=0, q1=0, q2=0;
  for(let i=0;i<n;i++){
    q0 = coeff*q1 - q2 + samples[i];
    q2 = q1; q1 = q0;
  }
  const real = q1 - q2*cosine, imag = q2*sine;
  return Math.sqrt(real*real + imag*imag) / n;
}

// ─── Pipeline audio temps réel (getUserMedia -> Goertzel -> décodeur) ───────
class CwAudioDecoder {
  constructor({freq=650, onChar, onLevel} = {}){
    this.freq = freq;
    this.onLevel = onLevel || (()=>{});
    this.decoder = new MorseTimingDecoder(onChar);
    this.decoder.wpm = 0;   // 0 tant qu'aucune marque réelle n'a été mesurée — voir onLevel plus bas
    this.ctx = null; this.stream = null; this.source = null; this.proc = null;
    this.noiseFloor = 0.01;
    this.keyDown = false;
    this.edgeStartMs = 0;
    this.lastSampleMs = 0;
    this.blockSize = 512;   // ~11.6ms à 44.1kHz : assez court pour suivre du CW rapide
    this._buf = [];
  }

  async start(deviceId){
    // Garde de ré-entrance : un second appel avant un stop() correspondant
    // (double-clic, redémarrage sur changement de périphérique) libère
    // d'abord toute session déjà ouverte au lieu d'écraser ses références.
    if(this.ctx) this.stop();
    const constraints = {audio: deviceId ? {deviceId:{exact:deviceId}, echoCancellation:false, noiseSuppression:false, autoGainControl:false}
                                          : {echoCancellation:false, noiseSuppression:false, autoGainControl:false}};
    this.stream = await navigator.mediaDevices.getUserMedia(constraints);
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    this.source = this.ctx.createMediaStreamSource(this.stream);
    // ScriptProcessorNode : déprécié mais universellement supporté et bien
    // assez pour un flux mono à quelques dizaines de Hz de résolution
    // temporelle — pas besoin d'un AudioWorklet pour ce cas d'usage.
    this.proc = this.ctx.createScriptProcessor(this.blockSize, 1, 1);
    this.edgeStartMs = performance.now();
    this.lastSampleMs = this.edgeStartMs;
    this.proc.onaudioprocess = (e) => this._onBlock(e.inputBuffer.getChannelData(0));
    this.source.connect(this.proc);
    // Le graphe Web Audio n'avance que si le node est connecté à une
    // destination — un GainNode à 0 évite de faire sortir le son des
    // haut-parleurs tout en gardant le pipeline actif.
    this._sink = this.ctx.createGain();
    this._sink.gain.value = 0;
    this.proc.connect(this._sink);
    this._sink.connect(this.ctx.destination);
  }

  setFreq(hz){ this.freq = hz; }

  _onBlock(samples){
    const now = performance.now();
    const mag = goertzelMagnitude(samples, this.ctx.sampleRate, this.freq);

    // Plancher de bruit : moyenne très lente, tirée vers le bas plus vite
    // qu'elle ne monte (ne doit jamais "apprendre" un signal continu comme
    // étant du bruit, sinon le décodeur devient sourd à un CW soutenu).
    if(mag < this.noiseFloor) this.noiseFloor = this.noiseFloor*0.98 + mag*0.02;
    else this.noiseFloor = this.noiseFloor*0.999 + mag*0.001;
    const threshold = this.noiseFloor * 2.8 + 0.003;
    const isOn = mag > threshold;
    this.onLevel(mag, threshold, this.decoder.wpm);

    if(isOn !== this.keyDown){
      // Compensation du retard de détection lié au découpage en blocs : un
      // changement d'état n'est confirmé qu'au bloc COMPLET suivant, ce qui
      // allonge systématiquement chaque marque et raccourcit symétriquement
      // l'espace qui suit (vérifié empiriquement contre un signal de test :
      // biais ≈ une durée de bloc). Sans cette correction, l'unité de temps
      // adaptative dérive lentement vers le haut au fil du message et finit
      // par plus reconnaître les espaces de mot.
      const blockMs = this.blockSize / this.ctx.sampleRate * 1000;
      let durationMs = (now - this.edgeStartMs) + (this.keyDown ? -blockMs : blockMs);
      durationMs = Math.max(1, durationMs);
      this.decoder.pushEdge(this.keyDown, durationMs);
      this.keyDown = isOn;
      this.edgeStartMs = now;
    } else if(!this.keyDown){
      this.decoder.flushIfIdle(now - this.edgeStartMs);
    }
    this.lastSampleMs = now;
  }

  stop(){
    try{ this.proc && this.proc.disconnect(); }catch(e){}
    try{ this._sink && this._sink.disconnect(); }catch(e){}
    try{ this.source && this.source.disconnect(); }catch(e){}
    try{ this.stream && this.stream.getTracks().forEach(t=>t.stop()); }catch(e){}
    try{ this.ctx && this.ctx.close(); }catch(e){}
    this.ctx = null; this.stream = null;
  }
}

if(typeof module !== 'undefined') module.exports = {MORSE_TABLE, MorseTimingDecoder, goertzelMagnitude, CwAudioDecoder};
