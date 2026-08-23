// ─── Soundcard CW (Web Audio) — keyer CW backend « carte son » ────────────────
// Émission CW en générant une tonalité audio dans le NAVIGATEUR (comme l'École
// CW), pour un poste SANS entrée KEY : la BF part sur l'entrée micro/ligne du
// poste en SSB (VOX ou PTT CAT). Émission 100 % locale — aucun POST serveur,
// donc le garde-fou serveur ne s'applique pas : on vérifie côté client (TX armé)
// AVANT de jouer. En SSB le poste n'est PAS en mode CW, donc on n'exige pas le
// mode CW pour cette voie (contrairement aux keyers matériels).
//
// Réutilise la convention PARIS et l'enveloppe anti-clic de logx_cw.html.
// <script> classique : fonctions globales.

const CW_SC_MORSE = {
  'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.', 'G': '--.',
  'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.',
  'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-', 'U': '..-',
  'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--', 'Z': '--..',
  '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-', '5': '.....',
  '6': '-....', '7': '--...', '8': '---..', '9': '----.', '/': '-..-.', '?': '..--..',
  '.': '.-.-.-', ',': '--..--', '=': '-...-', '+': '.-.-.', '-': '-....-'
};

function cwScDitMs(wpm){ return 1200 / Math.max(8, Math.min(40, wpm)); }   // PARIS

// Schedule PUR (testable sans Web Audio) : liste des segments de tonalité
// {onset, duree} en ms depuis le début. Convention PARIS : point 1 dit, trait 3,
// silence intra 1 / inter-caractère 3 / inter-mot 7 — silences JAMAIS après le
// dernier élément (l'espace porte déjà le sien). Caractère absent -> ignoré.
function cwSoundcardSchedule(texte, wpm){
  const dit = cwScDitMs(wpm);
  const segs = [];
  let t = 0;
  const chars = [...String(texte || '').toUpperCase()];
  for(let i = 0; i < chars.length; i++){
    const ch = chars[i];
    if(ch === ' '){ t += 7 * dit; continue; }
    const motif = CW_SC_MORSE[ch];
    if(!motif) continue;
    for(let k = 0; k < motif.length; k++){
      const duree = (motif[k] === '-' ? 3 : 1) * dit;
      segs.push({onset: t, duree: duree});
      t += duree;
      if(k < motif.length - 1) t += dit;             // entre éléments
    }
    const suivant = chars[i + 1];
    if(suivant !== undefined && suivant !== ' ') t += 3 * dit;   // entre caractères
  }
  return segs;
}

function _cwScCfg(){
  try{ return JSON.parse(localStorage.getItem('logx_config') || '{}'); }catch(e){ return {}; }
}
function cwSoundcardActif(){
  const v = String(_cwScCfg().soundcard_cw_enabled || '').trim();
  return v !== '' && v !== '0' && v !== 'false' && v !== 'False';
}
function cwSoundcardHz(){
  const hz = parseInt(_cwScCfg().soundcard_cw_hz, 10);
  return (hz >= 300 && hz <= 1200) ? hz : 700;
}
function cwSoundcardWpm(){
  const w = parseInt(_cwScCfg().soundcard_cw_wpm, 10);
  return (w >= 5 && w <= 40) ? w : 20;
}

let _cwScCtx = null, _cwScOscs = [];

function cwSoundcardStop(){
  _cwScOscs.forEach(o => { try{ o.stop(); }catch(e){} });
  _cwScOscs = [];
}

// Joue `texte` à la carte son. Retourne une promesse résolue à la fin de
// l'émission. Repli silencieux (promesse résolue) si Web Audio est absent.
function cwSoundcardPlay(texte, wpm, hz){
  const segs = cwSoundcardSchedule(texte, wpm);
  if(!segs.length) return Promise.resolve();
  const AC = (typeof window !== 'undefined') && (window.AudioContext || window.webkitAudioContext);
  if(!AC) return Promise.resolve();
  if(!_cwScCtx) _cwScCtx = new AC();
  cwSoundcardStop();
  const RAMPE = 0.004, t0 = _cwScCtx.currentTime + 0.15;
  segs.forEach(s => {
    const t = t0 + s.onset / 1000, duree = s.duree / 1000;
    const osc = _cwScCtx.createOscillator(), g = _cwScCtx.createGain();
    osc.frequency.value = hz; osc.type = 'sine';
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(0.25, t + RAMPE);
    g.gain.setValueAtTime(0.25, t + duree - RAMPE);
    g.gain.linearRampToValueAtTime(0, t + duree);
    osc.connect(g).connect(_cwScCtx.destination);
    osc.start(t); osc.stop(t + duree + 0.01);
    _cwScOscs.push(osc);
  });
  const last = segs[segs.length - 1];
  const finS = t0 + (last.onset + last.duree) / 1000;
  return new Promise(res => setTimeout(res, Math.max(0, (finS - _cwScCtx.currentTime) * 1000) + 60));
}
