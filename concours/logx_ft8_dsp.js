// ─── DSP FT8 (modulation GFSK / synchro Costas / démodulation) ──────────────
// Couche audio au-dessus de logx_ft8_codec.js (protocole pur, sans audio).
// Même séparation que le CW/RTTY : le codec est testé contre des vecteurs
// exacts (bit à bit), le DSP est testé par aller-retour synthétique — il n'y
// a pas de "vecteur de test" pour une forme d'onde, seulement la question
// « ça se décode ou pas » (voir tests/test_ft8_dsp.py, même principe que
// tests/test_rtty_decodeur.py : on encode, on synthétise, on décode, on
// compare, avec et sans bruit ajouté).
//
// Choix de conception (pas de norme à respecter ici, contrairement au
// codec) :
// - Mise en forme gaussienne BT=2.0 par filtre FIR construit à la volée
//   (gaussien normalisé, pas de bibliothèque DSP tierce — même politique
//   que la FFT maison du panadapter, logx_tci.py).
// - Démodulation par banc de filtres de Goertzel (8 tons par symbole) :
//   évite une FFT généraliste alors qu'on ne cherche que 8 fréquences
//   précises par fenêtre — beaucoup moins cher qu'une FFT complète, et pas
//   contraint à une taille de fenêtre puissance de 2.
// - Recherche de synchro en 2 étapes (large/grossière puis fine autour du
//   meilleur candidat) : une recherche fine seule sur toute la plage
//   temps x fréquence serait de plusieurs centaines de millions
//   d'évaluations Goertzel — bien trop lent en JS pur.

const FT8_DEFAULT_SAMPLE_RATE = 12000;
const FT8_DEFAULT_TONE0_HZ = 1500;   // fréquence audio du ton 0 (au centre du passe-bande SSB habituel)
const FT8_GAUSSIAN_BT = 2.0;

function ft8SamplesPerSymbol(sampleRate){
  return Math.round(sampleRate * FT8_SYMBOL_PERIOD);
}

// ─── TX : synthèse GFSK ───────────────────────────────────────────────────

// Noyau gaussien normalisé (aire unitaire) pour la mise en forme BT=2.0.
// sigma en échantillons, dérivé de la formule standard GFSK :
// sigma_symboles = sqrt(ln2) / (2*pi*BT).
function ft8GaussianKernel(samplesPerSymbol, bt){
  const sigmaSymbols = Math.sqrt(Math.LN2) / (2 * Math.PI * bt);
  const sigma = sigmaSymbols * samplesPerSymbol;
  const radius = Math.max(1, Math.round(3 * sigma));
  const kernel = new Float64Array(2 * radius + 1);
  let sum = 0;
  for(let i = -radius; i <= radius; i++){
    const v = Math.exp(-(i * i) / (2 * sigma * sigma));
    kernel[i + radius] = v;
    sum += v;
  }
  for(let i = 0; i < kernel.length; i++) kernel[i] /= sum;
  return { kernel, radius };
}

// symbols79 : 79 tons 0..7 (voir ft8CodewordToSymbols). Retourne un
// Float32Array de l'onde audio (mono, [-amplitude, +amplitude]).
function ft8SynthesizeGfsk(symbols79, opts){
  opts = opts || {};
  const sampleRate = opts.sampleRate || FT8_DEFAULT_SAMPLE_RATE;
  const toneHz0 = opts.toneHz0 || FT8_DEFAULT_TONE0_HZ;
  const amplitude = (opts.amplitude === undefined) ? 0.9 : opts.amplitude;
  const sps = ft8SamplesPerSymbol(sampleRate);
  const total = symbols79.length * sps;

  // Fréquence "brute" par échantillon (paliers, avant lissage gaussien).
  const rawFreq = new Float64Array(total);
  for(let s = 0; s < symbols79.length; s++){
    const f = toneHz0 + symbols79[s] * FT8_TONE_SPACING;
    for(let j = 0; j < sps; j++) rawFreq[s * sps + j] = f;
  }

  // Lissage gaussien (convolution directe — le noyau est court, ~1/4 de
  // symbole pour BT=2.0, donc pas besoin d'une FFT pour cette étape).
  const { kernel, radius } = ft8GaussianKernel(sps, FT8_GAUSSIAN_BT);
  const smoothFreq = new Float64Array(total);
  for(let i = 0; i < total; i++){
    let acc = 0;
    for(let k = -radius; k <= radius; k++){
      const idx = i + k;
      const sample = (idx < 0) ? rawFreq[0] : (idx >= total ? rawFreq[total - 1] : rawFreq[idx]);
      acc += sample * kernel[k + radius];
    }
    smoothFreq[i] = acc;
  }

  // Intégration de phase (CPFSK : la phase est continue d'un symbole à
  // l'autre, ce qui limite l'énergie hors-bande par rapport à un simple
  // changement de fréquence discontinu).
  const wave = new Float32Array(total);
  let phase = 0;
  const twoPiOverFs = 2 * Math.PI / sampleRate;
  for(let i = 0; i < total; i++){
    phase += smoothFreq[i] * twoPiOverFs;
    wave[i] = amplitude * Math.cos(phase);
  }
  return wave;
}

// ─── RX : filtre de Goertzel ──────────────────────────────────────────────

// Magnitude du signal à freqHz sur N échantillons commençant à offset.
// N n'a pas besoin d'être une puissance de 2 (contrairement à une FFT) —
// un banc de 8 filtres de Goertzel par fenêtre est beaucoup moins cher
// qu'une FFT complète quand on ne cherche que 8 fréquences précises.
function ft8GoertzelMag(samples, offset, N, freqHz, sampleRate){
  const k = freqHz * N / sampleRate;
  const w = 2 * Math.PI * k / N;
  const cosW = Math.cos(w), sinW = Math.sin(w);
  const coeff = 2 * cosW;
  let q0 = 0, q1 = 0, q2 = 0;
  for(let i = 0; i < N; i++){
    q0 = coeff * q1 - q2 + samples[offset + i];
    q2 = q1;
    q1 = q0;
  }
  const real = q1 - q2 * cosW;
  const imag = q2 * sinW;
  return Math.sqrt(real * real + imag * imag);
}

// Magnitude des 8 tons FT8 pour une fenêtre (un symbole) donnée.
function ft8GoertzelToneBank(samples, offset, N, baseFreqHz, sampleRate){
  const mags = new Float64Array(8);
  for(let tone = 0; tone < 8; tone++){
    mags[tone] = ft8GoertzelMag(samples, offset, N, baseFreqHz + tone * FT8_TONE_SPACING, sampleRate);
  }
  return mags;
}

// Score de corrélation Costas : somme des magnitudes du ton ATTENDU sur les
// 21 positions de synchro (3 groupes de 7), pour un candidat
// (startSample, baseFreqHz) donné. Plus le score est haut, plus le candidat
// ressemble à un vrai motif de synchro FT8.
function ft8CostasScore(samples, startSample, baseFreqHz, sampleRate){
  const sps = ft8SamplesPerSymbol(sampleRate);
  let score = 0;
  const groups = [0, FT8_SYNC_OFFSET, 2 * FT8_SYNC_OFFSET];
  for(const g of groups){
    for(let i = 0; i < FT8_LENGTH_SYNC; i++){
      const symIdx = g + i;
      const offset = startSample + symIdx * sps;
      if(offset < 0 || offset + sps > samples.length) return -Infinity;
      const expectedTone = FT8_COSTAS_PATTERN[i];
      score += ft8GoertzelMag(samples, offset, sps, baseFreqHz + expectedTone * FT8_TONE_SPACING, sampleRate);
    }
  }
  return score;
}

// Recherche de synchro en 2 étapes : balayage grossier (pas entiers de
// symbole en temps, demi-pas de ton en fréquence) sur toute la plage
// candidate, puis affinage local autour du meilleur candidat (pas fins en
// temps ET en fréquence, mais sur une toute petite plage). Retourne
// {startSample, baseFreqHz, score} ou null si samples est trop court.
function ft8FindSync(samples, sampleRate, opts){
  opts = opts || {};
  const sps = ft8SamplesPerSymbol(sampleRate);
  const totalSpan = FT8_NN * sps;
  if(samples.length < totalSpan) return null;

  const freqMin = opts.freqMin || 200;
  const freqMax = opts.freqMax || 2900;
  const freqStepCoarse = FT8_TONE_SPACING / 2;
  const timeSlopSymbols = (opts.timeSlopSymbols === undefined) ? 6 : opts.timeSlopSymbols;

  let best = { startSample: 0, baseFreqHz: freqMin, score: -Infinity };
  for(let symOffset = -timeSlopSymbols; symOffset <= timeSlopSymbols; symOffset++){
    const startSample = symOffset * sps;
    if(startSample < 0 || startSample + totalSpan > samples.length) continue;
    for(let f = freqMin; f <= freqMax; f += freqStepCoarse){
      const score = ft8CostasScore(samples, startSample, f, sampleRate);
      if(score > best.score) best = { startSample, baseFreqHz: f, score };
    }
  }
  if(best.score === -Infinity) return null;

  // Affinage local : +/-1 symbole en pas de sps/8, +/- 1 pas grossier en
  // fréquence par pas de 0.5 Hz.
  const fineTimeStep = Math.max(1, Math.round(sps / 8));
  let bestFine = best;
  for(let dt = -sps; dt <= sps; dt += fineTimeStep){
    const startSample = best.startSample + dt;
    if(startSample < 0 || startSample + totalSpan > samples.length) continue;
    for(let df = -freqStepCoarse; df <= freqStepCoarse; df += 0.5){
      const f = best.baseFreqHz + df;
      if(f < freqMin || f > freqMax) continue;
      const score = ft8CostasScore(samples, startSample, f, sampleRate);
      if(score > bestFine.score) bestFine = { startSample, baseFreqHz: f, score };
    }
  }
  return bestFine;
}

// ─── Extraction des symboles de données (softbits) ───────────────────────

// À partir d'un candidat de synchro déjà localisé, extrait les 174 LLR
// (vraisemblances) des bits codés — convention alignée sur ft8BpDecode
// (LLR>0 pousse vers 1). gain contrôle la mise à l'échelle (une valeur
// trop grande sature fast_tanh/fast_atanh, une valeur trop petite laisse le
// décodeur quasi-aveugle) — 3.0 est un compromis raisonnable, pas une
// valeur "correcte" au sens propre : il n'y a pas de référence externe à
// matcher ici, seule la robustesse du décodage compte.
function ft8ExtractLlr(samples, sync, sampleRate, gain){
  gain = (gain === undefined) ? 3.0 : gain;
  const sps = ft8SamplesPerSymbol(sampleRate);
  const llr = new Array(174);
  let bitIdx = 0;

  function processDataBlock(startSym, count){
    for(let s = 0; s < count; s++){
      const symIdx = startSym + s;
      const offset = sync.startSample + symIdx * sps;
      const mags = ft8GoertzelToneBank(samples, offset, sps, sync.baseFreqHz, sampleRate);
      const avg = (mags[0]+mags[1]+mags[2]+mags[3]+mags[4]+mags[5]+mags[6]+mags[7]) / 8;
      const norm = avg > 1e-9 ? avg : 1;

      for(let bit = 0; bit < 3; bit++){
        let maxOne = -Infinity, maxZero = -Infinity;
        for(let tone = 0; tone < 8; tone++){
          const v = FT8_GRAY_MAP_INV[tone];
          const bitVal = (v >> (2 - bit)) & 1;
          const m = mags[tone] / norm;
          if(bitVal) { if(m > maxOne) maxOne = m; }
          else { if(m > maxZero) maxZero = m; }
        }
        llr[bitIdx++] = gain * (maxOne - maxZero);
      }
    }
  }
  processDataBlock(FT8_LENGTH_SYNC, 29);
  processDataBlock(FT8_SYNC_OFFSET + FT8_LENGTH_SYNC, 29);
  return llr;
}

// ─── API haut niveau : audio -> texte ─────────────────────────────────────

// samples : Float32Array/Array mono, fenêtre d'environ 15s (ou plus, avec
// une marge de recherche temporelle). Retourne {text, freqHz} ou null si
// rien n'a pu être décodé dans cette fenêtre.
function ft8DecodeAudio(samples, sampleRate, hashTable, opts){
  const sync = ft8FindSync(samples, sampleRate, opts);
  if(!sync) return null;
  const llr = ft8ExtractLlr(samples, sync, sampleRate, opts && opts.gain);
  const text = ft8DecodeLlr(llr, hashTable, (opts && opts.maxIters) || 20);
  if(!text) return null;
  return { text, freqHz: sync.baseFreqHz, syncScore: sync.score };
}

if(typeof module !== 'undefined' && module.exports){
  module.exports = {
    FT8_DEFAULT_SAMPLE_RATE, FT8_DEFAULT_TONE0_HZ, FT8_GAUSSIAN_BT,
    ft8SamplesPerSymbol, ft8GaussianKernel, ft8SynthesizeGfsk,
    ft8GoertzelMag, ft8GoertzelToneBank, ft8CostasScore, ft8FindSync,
    ft8ExtractLlr, ft8DecodeAudio,
  };
}
