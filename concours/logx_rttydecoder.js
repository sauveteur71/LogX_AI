// ─── DÉCODEUR RTTY (Baudot/ITA2) DANS LE NAVIGATEUR ──────────────────────────
// CQ WW RTTY, CQ WPX RTTY et WAE RTTY sont des concours majeurs où beaucoup de
// stations F sont actives. Jusqu'ici, un utilisateur de LogX AI qui voulait en
// faire un devait ouvrir N1MM à côté : le RTTY n'existait que comme étiquette
// de mode dans le log et les exports.
//
// N1MM s'interface avec MMTTY/MMVARI/Fldigi — trois logiciels externes. Ici le
// décodage se fait dans la page, comme le décodeur CW : rien à installer, et ça
// marche sur les postes secondaires qui n'ont que le navigateur.
//
// POURQUOI PAS UN GOERTZEL PAR BLOC, comme en CW : les deux tons RTTY sont
// séparés de 170 Hz seulement. Un Goertzel de N points a une résolution de
// (fréquence d'échantillonnage / N) : il faudrait N ≥ 512 à 44,1 kHz pour les
// distinguer, soit 11,6 ms — la moitié d'un bit à 45,45 bauds. Beaucoup trop
// grossier pour se caler sur le bit de start. On démodule donc en continu.

// ─── ITA2 / Baudot, variante télétype américaine (celle du trafic amateur) ───
// Indexé par la valeur 5 bits, bit 0 = premier bit ÉMIS.
const RTTY_LTRS = [
  '\0', 'E', '\n', 'A', ' ', 'S', 'I', 'U',
  '\r', 'D', 'R', 'J', 'N', 'F', 'C', 'K',
  'T', 'Z', 'L', 'W', 'H', 'Y', 'P', 'Q',
  'O', 'B', 'G', null, 'M', 'X', 'V', null,
];
const RTTY_FIGS = [
  '\0', '3', '\n', '-', ' ', "'", '8', '7',
  '\r', '$', '4', "\x07", ',', '!', ':', '(',
  '5', '+', ')', '2', '#', '6', '0', '1',
  '9', '?', '&', null, '.', '/', ';', null,
];
const CODE_FIGS = 27;   // 11011
const CODE_LTRS = 31;   // 11111

// Décodage d'un caractère avec l'état de bascule LTRS/FIGS. Retourné à part de
// la démodulation pour rester testable sans audio.
function rttyBaudotChar(code, etat){
  if(code === CODE_FIGS){ etat.figs = true;  return ''; }
  if(code === CODE_LTRS){ etat.figs = false; return ''; }
  const table = etat.figs ? RTTY_FIGS : RTTY_LTRS;
  const c = table[code & 31];
  return (c === null || c === '\0') ? '' : c;
}

// ─── Démodulateur FSK + récepteur asynchrone ────────────────────────────────
// Deux détecteurs de tonalité en quadrature, lissés par un filtre du premier
// ordre, puis la différence des puissances donne le bit : positif = mark,
// négatif = space. La synchro est celle d'une liaison série asynchrone —
// front descendant = bit de start, puis échantillonnage au MILIEU de chaque
// bit (c'est là que la décision est la plus sûre, loin des transitions).
class RttyDemodulator {
  constructor({sampleRate = 44100, baud = 45.45, mark = 2125, space = 2295,
               onChar} = {}){
    this.sampleRate = sampleRate;
    this.baud = baud;
    this.mark = mark;
    this.space = space;
    this.onChar = onChar || (() => {});
    this.samplesPerBit = sampleRate / baud;
    this.etat = {figs: false};

    // Constante du filtre : environ un quart de bit. Plus court, le bruit
    // passe ; plus long, les transitions sont lissées au point de décaler la
    // détection du front de start.
    this.alpha = 1 / Math.max(1, this.samplesPerBit / 4);

    this._n = 0;                    // index d'échantillon (phase des oscillateurs)
    this._mI = 0; this._mQ = 0;
    this._sI = 0; this._sQ = 0;
    this._prev = 1;                 // niveau precedent (1 = mark, repos)
    this._etatRx = 'repos';         // repos | start | data | stop
    this._prochain = 0;             // index d'echantillon du prochain point de decision
    this._bits = [];
    this._texte = '';
  }

  // Niveau instantané : +1 = mark, -1 = space. Public pour les tests.
  _niveau(x){
    const wM = 2 * Math.PI * this.mark / this.sampleRate;
    const wS = 2 * Math.PI * this.space / this.sampleRate;
    const t = this._n;
    const a = this.alpha;
    this._mI += (x * Math.cos(wM * t) - this._mI) * a;
    this._mQ += (x * Math.sin(wM * t) - this._mQ) * a;
    this._sI += (x * Math.cos(wS * t) - this._sI) * a;
    this._sQ += (x * Math.sin(wS * t) - this._sQ) * a;
    const pM = this._mI * this._mI + this._mQ * this._mQ;
    const pS = this._sI * this._sI + this._sQ * this._sQ;
    return pM >= pS ? 1 : 0;
  }

  // Consomme un bloc d'échantillons (Float32Array ou tableau).
  pousser(samples){
    for(let i = 0; i < samples.length; i++){
      const bit = this._niveau(samples[i]);
      this._n++;

      if(this._etatRx === 'repos'){
        // Front mark -> space : début probable d'un bit de start. On vise le
        // MILIEU de ce bit pour confirmer, plutôt que de faire confiance au
        // front lui-même (un parasite le franchirait).
        if(this._prev === 1 && bit === 0){
          this._etatRx = 'start';
          this._prochain = this._n + Math.round(this.samplesPerBit / 2);
        }
      } else if(this._n >= this._prochain){
        if(this._etatRx === 'start'){
          if(bit === 0){                     // start confirmé
            this._etatRx = 'data';
            this._bits = [];
            this._prochain = this._n + Math.round(this.samplesPerBit);
          } else {
            this._etatRx = 'repos';          // parasite : on rejette
          }
        } else if(this._etatRx === 'data'){
          this._bits.push(bit);
          if(this._bits.length === 5){
            this._etatRx = 'stop';
          }
          this._prochain = this._n + Math.round(this.samplesPerBit);
        } else if(this._etatRx === 'stop'){
          // Le bit de stop DOIT être un mark. S'il ne l'est pas, la trame est
          // fausse (bruit, mauvaise vitesse, mauvais shift) : on la jette au
          // lieu d'écrire un caractère aléatoire à l'écran.
          if(bit === 1){
            let code = 0;
            for(let b = 0; b < 5; b++) if(this._bits[b]) code |= (1 << b);
            const c = rttyBaudotChar(code, this.etat);
            if(c){ this._texte += c; this.onChar(c); }
          }
          this._etatRx = 'repos';
        }
      }
      this._prev = bit;
    }
    return this._texte;
  }

  texte(){ return this._texte; }
  reset(){ this._texte = ''; this._etatRx = 'repos'; this.etat.figs = false; }
}

// Décodage d'un signal complet — utilisé par les tests, qui synthétisent un
// signal AFSK valide et vérifient qu'on retrouve le texte. Le RTTY étant
// généré à cadence FIXE par machine (contrairement au CW, où la main humaine
// fait varier les durées), un signal synthétique est représentatif du réel.
function rttyDecodeSamples(samples, opts){
  const d = new RttyDemodulator(opts || {});
  d.pousser(samples);
  return d.texte();
}

// Générateur AFSK : sert aux tests, et à l'auto-test du panneau (« est-ce que
// ma chaîne audio fonctionne ? ») sans avoir à trouver une station sur l'air.
function rttyEncodeSamples(texte, {sampleRate = 44100, baud = 45.45,
                                   mark = 2125, space = 2295,
                                   amplitude = 0.5, preambleBits = 8} = {}){
  const spb = sampleRate / baud;
  const bits = [];
  for(let i = 0; i < preambleBits; i++) bits.push(1);   // repos (mark)

  let figs = false;
  const pousserCode = code => {
    bits.push(0);                                        // start (space)
    for(let b = 0; b < 5; b++) bits.push((code >> b) & 1);
    bits.push(1); bits.push(1);                          // stop (1,5 bit -> 2)
  };
  for(const ch of String(texte).toUpperCase()){
    let idx = RTTY_LTRS.indexOf(ch);
    let versFigs = false;
    if(idx < 0 || idx === CODE_FIGS || idx === CODE_LTRS){
      idx = RTTY_FIGS.indexOf(ch);
      versFigs = true;
      if(idx < 0) continue;                              // caractère non transmissible
    }
    if(versFigs !== figs){
      pousserCode(versFigs ? CODE_FIGS : CODE_LTRS);
      figs = versFigs;
    }
    pousserCode(idx);
  }
  bits.push(1, 1, 1, 1);                                 // retour au repos

  const out = new Float32Array(Math.ceil(bits.length * spb));
  let n = 0;
  for(const b of bits){
    const f = b ? mark : space;
    const w = 2 * Math.PI * f / sampleRate;
    const fin = Math.round((n + 1) * spb);
    for(let i = Math.round(n * spb); i < fin && i < out.length; i++){
      out[i] = amplitude * Math.sin(w * i);
    }
    n++;
  }
  return out;
}

// ─── Chaîne audio temps réel (même motif que le décodeur CW) ────────────────
class RttyAudioDecoder {
  constructor(opts = {}){
    this.opts = opts;
    this.demod = null;
    this.ctx = null; this.stream = null; this.source = null; this.proc = null;
    this.blockSize = 1024;
  }

  async start(deviceId){
    // Garde de ré-entrance : libère une session déjà ouverte avant d'en
    // recréer une nouvelle (double-clic, changement de périphérique).
    if(this.ctx) this.stop();
    const contraintes = {audio: deviceId
      ? {deviceId: {exact: deviceId}, echoCancellation: false, noiseSuppression: false, autoGainControl: false}
      : {echoCancellation: false, noiseSuppression: false, autoGainControl: false}};
    this.stream = await navigator.mediaDevices.getUserMedia(contraintes);
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    this.demod = new RttyDemodulator(Object.assign({}, this.opts,
                                                   {sampleRate: this.ctx.sampleRate}));
    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.proc = this.ctx.createScriptProcessor(this.blockSize, 1, 1);
    this.proc.onaudioprocess = e => this.demod.pousser(e.inputBuffer.getChannelData(0));
    this.source.connect(this.proc);
    // Comme pour le CW : le graphe n'avance que si le node est connecté à une
    // destination — un gain à 0 garde le pipeline actif sans rien sortir sur
    // les haut-parleurs.
    this._sink = this.ctx.createGain();
    this._sink.gain.value = 0;
    this.proc.connect(this._sink);
    this._sink.connect(this.ctx.destination);
  }

  stop(){
    try{ if(this.proc) this.proc.disconnect(); }catch(e){}
    try{ if(this.source) this.source.disconnect(); }catch(e){}
    try{ if(this.stream) this.stream.getTracks().forEach(t => t.stop()); }catch(e){}
    try{ if(this.ctx) this.ctx.close(); }catch(e){}
    this.proc = this.source = this.stream = this.ctx = null;
  }

  setShift(mark, space){
    if(this.demod){ this.demod.mark = mark; this.demod.space = space; }
    this.opts.mark = mark; this.opts.space = space;
  }
}

if(typeof module !== 'undefined' && module.exports){
  module.exports = {RttyDemodulator, rttyDecodeSamples, rttyEncodeSamples,
                    rttyBaudotChar, RTTY_LTRS, RTTY_FIGS};
}
