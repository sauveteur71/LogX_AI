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

// ─── DÉCIMATION AVANT DÉCODAGE ─────────────────────────────────────────────
//
// POURQUOI. La carte son livre l'audio à sa cadence naturelle — 48 kHz sur la
// quasi-totalité des codecs USB de postes récents. Le décodage travaillait
// directement à cette cadence, alors que le signal FT8 tient tout entier sous
// 3 kHz : les trois quarts des échantillons ne portaient AUCUNE information
// utile, et coûtaient pourtant leur temps plein dans le banc de Goertzel et la
// recherche de synchro, dont le coût est linéaire en nombre d'échantillons.
//
// La conséquence n'était pas seulement « c'est lent ». ft8DecodeAudioAll est
// appelée de façon SYNCHRONE sur le thread principal à chaque fin de créneau,
// et pendant tout ce temps le navigateur ne peut ni redessiner la cascade, ni
// exécuter le ScriptProcessorNode qui collecte l'audio. D'où les deux
// symptômes signalés par F4GLD le 18/08/2026 : « le waterfall continue à se
// figer », et le compteur « N resynchro. audio » qui grimpait sans fin — les
// blocs audio sautés pendant le décodage font dériver l'horloge du tampon,
// que pousserEchantillons doit alors reprendre sur l'horloge réelle.
//
// Autrement dit, le décodage se sabote lui-même : plus il dure, plus il perd
// d'audio, donc plus il doit resynchroniser.
//
// ⚠ CE QUE LA DÉCIMATION FAIT, ET CE QU'ELLE NE FAIT PAS. Elle divise le
// blocage par 4 — c'est considérable, et cela suffit à faire repasser la
// fenêtre d'analyse au-dessus des 14 s exigées par extraireFenetre, donc à
// rétablir le décodage continu. Elle NE SUPPRIME PAS le symptôme.
// Mesuré dans un vrai navigateur (Chrome 148 / Electron 42), pas seulement
// sous le moteur des tests :
//     avant  : 10 319 ms de blocage par créneau de 15 s
//     après  :  2 576 ms
// Or DERIVE_MAX_MS vaut 400 ms et un bloc audio 85,3 ms : le résiduel reste
// 6,4 fois au-dessus du seuil de resynchronisation et 30 fois au-dessus d'un
// bloc. Le compteur « N resynchro. audio » continuera donc de monter, et la
// cascade se figera encore — moins longtemps.
//
// Le seul correctif qui rende le trou NUL est de sortir le décodage du thread
// principal (Web Worker : l'entrée est un Float32Array transférable, la sortie
// un petit tableau d'objets ; l'émission n'est pas concernée). Chantier
// distinct, à ne pas greffer ici sans vérification en navigateur réel.
//
// CE QU'ON NE FAIT PAS. On ne descend pas systématiquement à 12 kHz : toutes
// les cartes ne sont pas à 48 kHz (44,1 kHz reste courant) et un rééchantillon-
// nage à rapport non entier demanderait une interpolation, avec sa propre
// distorsion. On décime donc par un facteur ENTIER, le plus grand qui laisse
// au moins FT8_DEFAULT_SAMPLE_RATE en sortie. 48000 -> 4 (12 kHz exactement),
// 44100 -> 3 (14,7 kHz), 96000 -> 8 (12 kHz), 12000 -> 1 (on ne touche à rien).
// Le décodeur prend sa cadence en paramètre : il n'a que faire d'un chiffre
// rond.
function ft8FacteurDecimation(sampleRate, cadenceMin){
  const cible = cadenceMin || FT8_DEFAULT_SAMPLE_RATE;
  if(!(sampleRate > 0) || !isFinite(sampleRate)) return 1;
  return Math.max(1, Math.floor(sampleRate / cible));
}

// Filtre anti-repliement : sinus cardinal fenêtré de Blackman, construit à la
// volée — même politique que le noyau gaussien ci-dessus et que la FFT maison
// du panadapter : pas de bibliothèque DSP tierce.
//
// SANS CE FILTRE, décimer serait pire que ne rien faire. Tout ce qui dépasse
// la nouvelle fréquence de Nyquist ne disparaît pas : il se REPLIE dans la
// bande utile, et un souffle à 20 kHz atterrit au beau milieu des tons FT8
// sous forme de bruit qu'aucun traitement ultérieur ne peut plus séparer du
// signal.
//
// Coupure à 0,42 x la cadence de sortie : franchement au-dessus des 3 kHz
// occupés par FT8 dans un passe-bande SSB, et franchement en dessous de la
// nouvelle demi-cadence (0,5), pour laisser la bande de transition du filtre
// tenir sans replier.
function ft8NoyauAntiRepliement(facteur, longueur){
  const n = longueur || (12 * facteur + 1);
  const demi = (n - 1) / 2;
  const fc = 0.42 / facteur;          // coupure normalisée à la cadence d'ENTRÉE
  const h = new Float32Array(n);
  let somme = 0;
  for(let i = 0; i < n; i++){
    const x = i - demi;
    // sinc(2*fc*x), prolongé par continuité en x = 0
    const arg = 2 * Math.PI * fc * x;
    const sinc = (x === 0) ? (2 * fc) : (Math.sin(arg) / (Math.PI * x));
    // Fenêtre de Blackman : lobes secondaires à -58 dB, bien plus bas que
    // Hamming (-41 dB). Ce qui compte ici c'est justement ce qui fuit
    // au-dessus de la coupure.
    const w = 0.42 - 0.5 * Math.cos(2 * Math.PI * i / (n - 1))
                   + 0.08 * Math.cos(4 * Math.PI * i / (n - 1));
    h[i] = sinc * w;
    somme += h[i];
  }
  // Gain unité en continu : sans normalisation, le niveau change avec la
  // longueur du noyau, et tous les seuils réglés en aval deviendraient faux.
  if(somme !== 0) for(let i = 0; i < n; i++) h[i] /= somme;
  return h;
}

// Rend {samples, sampleRate}. Ne calcule le filtre QUE sur les échantillons
// conservés (un sur `facteur`) : filtrer d'abord la totalité puis jeter les
// trois quarts du résultat coûterait quatre fois plus cher pour rien.
function ft8Decimer(samples, sampleRate, cadenceMin){
  const facteur = ft8FacteurDecimation(sampleRate, cadenceMin);
  if(facteur <= 1) return {samples: samples, sampleRate: sampleRate};
  const h = ft8NoyauAntiRepliement(facteur);
  const demi = (h.length - 1) >> 1;
  const nOut = Math.floor(samples.length / facteur);
  const out = new Float32Array(nOut);
  for(let k = 0; k < nOut; k++){
    const centre = k * facteur;
    let acc = 0;
    for(let j = 0; j < h.length; j++){
      const idx = centre + j - demi;
      // Bords traités comme du silence. La fenêtre extraite déborde le créneau
      // de 1,5 s de chaque côté : les quelques échantillons concernés sont
      // très loin de la zone où un signal est cherché.
      if(idx >= 0 && idx < samples.length) acc += samples[idx] * h[j];
    }
    out[k] = acc;
  }
  return {samples: out, sampleRate: sampleRate / facteur};
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

// Affinage local autour d'un candidat grossier : +/-1 symbole en pas de
// sps/8, +/- 1 pas grossier en fréquence par pas de 0.5 Hz. Factorisé hors
// de ft8FindSync/ft8FindAllSync car les deux en ont besoin.
function ft8RefineSync(samples, sampleRate, coarse, freqStepCoarse, freqMin, freqMax){
  const sps = ft8SamplesPerSymbol(sampleRate);
  const totalSpan = FT8_NN * sps;
  const fineTimeStep = Math.max(1, Math.round(sps / 8));
  let bestFine = coarse;
  for(let dt = -sps; dt <= sps; dt += fineTimeStep){
    const startSample = coarse.startSample + dt;
    if(startSample < 0 || startSample + totalSpan > samples.length) continue;
    for(let df = -freqStepCoarse; df <= freqStepCoarse; df += 0.5){
      const f = coarse.baseFreqHz + df;
      if(f < freqMin || f > freqMax) continue;
      const score = ft8CostasScore(samples, startSample, f, sampleRate);
      if(score > bestFine.score) bestFine = { startSample, baseFreqHz: f, score };
    }
  }
  return bestFine;
}

// Recherche de synchro en 2 étapes : balayage grossier (pas entiers de
// symbole en temps, demi-pas de ton en fréquence) sur toute la plage
// candidate, puis affinage local autour du meilleur candidat (pas fins en
// temps ET en fréquence, mais sur une toute petite plage). Retourne LE
// SEUL meilleur candidat — {startSample, baseFreqHz, score} ou null si
// samples est trop court. Pour un vrai passage FT8 (plusieurs dizaines de
// signaux simultanés dans la même fenêtre de 15s), voir ft8FindAllSync().
// ─── Centrage de la recherche temporelle ───────────────────────────────────
//
// opts.centerSample : position, DANS LA FENÊTRE FOURNIE, où se trouverait le
// début d'un signal émis par une station PARFAITEMENT synchronisée. Le
// balayage grossier explore alors centerSample ± timeSlopSymbols symboles,
// c'est-à-dire un intervalle SYMÉTRIQUE autour du DT nul.
//
// Bug corrigé le 18/08/2026 (trouvé en écrivant le test du DT, pas par
// lecture) : la recherche partait de 0, donc du DÉBUT DE LA FENÊTRE. Or la
// page fournit une fenêtre qui commence 1 s AVANT le créneau (marge de
// extraireFenetre) : une station à DT=0 se trouve donc à 1 s = 6,25 symboles
// du début, alors que le balayage ne montait qu'à 6 symboles (0,96 s), et
// ft8RefineSync n'ajoutait qu'un symbole de plus (1,12 s au total). La plage
// de DT réellement acceptée était [-1,00 s ; +0,12 s] : quasiment aucune
// tolérance du côté positif, alors que la tenue d'heure attendue en FT8 est
// de l'ordre de LA SECONDE (horloge PC synchronisée NTP sur l'UTC — une
// première rédaction annonçait ici « ±2 s selon le guide utilisateur de
// WSJT-X », attribution fausse corrigée le 18/08/2026).
// Concrètement, un PC en retard de seulement 200 ms sur l'UTC ne
// décodait presque plus rien — beaucoup de signaux visibles sur la cascade,
// deux ou trois décodages, puis plus rien. C'est le symptôme rapporté par
// F4GLD le 18/08/2026.
//
// Par défaut 0 : le comportement historique est conservé pour les appelants
// qui fournissent une fenêtre déjà calée sur le début du signal (c'est le cas
// de tous les tests de synthèse/décodage, où le signal commence à 0).
function ft8FindSync(samples, sampleRate, opts){
  opts = opts || {};
  const sps = ft8SamplesPerSymbol(sampleRate);
  const totalSpan = FT8_NN * sps;
  if(samples.length < totalSpan) return null;

  const freqMin = opts.freqMin || 200;
  const freqMax = opts.freqMax || 2900;
  const freqStepCoarse = FT8_TONE_SPACING / 2;
  const timeSlopSymbols = (opts.timeSlopSymbols === undefined) ? 6 : opts.timeSlopSymbols;
  const centerSample = Math.round(opts.centerSample || 0);   // voir le pavé ci-dessus

  let best = { startSample: 0, baseFreqHz: freqMin, score: -Infinity };
  for(let symOffset = -timeSlopSymbols; symOffset <= timeSlopSymbols; symOffset++){
    const startSample = centerSample + symOffset * sps;
    if(startSample < 0 || startSample + totalSpan > samples.length) continue;
    for(let f = freqMin; f <= freqMax; f += freqStepCoarse){
      const score = ft8CostasScore(samples, startSample, f, sampleRate);
      if(score > best.score) best = { startSample, baseFreqHz: f, score };
    }
  }
  if(best.score === -Infinity) return null;
  return ft8RefineSync(samples, sampleRate, best, freqStepCoarse, freqMin, freqMax);
}

// Recherche de TOUS les candidats de synchro plausibles dans la fenêtre —
// une vraie bande FT8 porte des dizaines de signaux simultanés dans les
// mêmes 15s, pas un seul. Même balayage grossier que ft8FindSync(), mais au
// lieu de ne garder que le meilleur score, on garde les `maxCandidates`
// meilleurs pics LOCAUX (suppression des non-maxima : deux candidats trop
// proches en fréquence sont presque toujours le même signal détecté deux
// fois, pas deux signaux distincts — voir minFreqSeparationHz, par défaut
// la largeur d'un banc de 8 tons). Chaque survivant du balayage grossier
// est ensuite affiné individuellement. Retourne un tableau (triable par
// score), potentiellement vide si rien ne dépasse le bruit de fond.
function ft8FindAllSync(samples, sampleRate, opts){
  opts = opts || {};
  const sps = ft8SamplesPerSymbol(sampleRate);
  const totalSpan = FT8_NN * sps;
  if(samples.length < totalSpan) return [];

  const freqMin = opts.freqMin || 200;
  const freqMax = opts.freqMax || 2900;
  const freqStepCoarse = FT8_TONE_SPACING / 2;
  const timeSlopSymbols = (opts.timeSlopSymbols === undefined) ? 6 : opts.timeSlopSymbols;
  const maxCandidates = opts.maxCandidates || 30;
  const minFreqSeparationHz = (opts.minFreqSeparationHz === undefined) ? 8 * FT8_TONE_SPACING : opts.minFreqSeparationHz;
  const centerSample = Math.round(opts.centerSample || 0);   // voir ft8FindSync

  const all = [];
  for(let symOffset = -timeSlopSymbols; symOffset <= timeSlopSymbols; symOffset++){
    const startSample = centerSample + symOffset * sps;
    if(startSample < 0 || startSample + totalSpan > samples.length) continue;
    for(let f = freqMin; f <= freqMax; f += freqStepCoarse){
      all.push({ startSample, baseFreqHz: f, score: ft8CostasScore(samples, startSample, f, sampleRate) });
    }
  }
  all.sort((a, b) => b.score - a.score);

  const picked = [];
  for(const cand of all){
    if(picked.length >= maxCandidates) break;
    if(picked.some(p => Math.abs(p.baseFreqHz - cand.baseFreqHz) < minFreqSeparationHz)) continue;
    picked.push(cand);
  }
  return picked.map(c => ft8RefineSync(samples, sampleRate, c, freqStepCoarse, freqMin, freqMax));
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
  return { text, freqHz: sync.baseFreqHz,
           syncScore: sync.score / ft8SamplesPerSymbol(sampleRate),
           startSample: sync.startSample };
}

// Décode TOUS les signaux détectables dans la fenêtre (voir ft8FindAllSync)
// — c'est la fonction que la page FT8 utilise réellement à chaque cycle de
// 15s, ft8DecodeAudio() (un seul signal) n'étant conservée que pour sa
// simplicité de test. La plupart des candidats du balayage grossier sont du
// bruit qui ressemble un peu à une synchro Costas par hasard — ÉCHOUER le
// LDPC/CRC pour un candidat donné est le cas normal, pas une erreur : on
// l'ignore silencieusement et on passe au suivant. Dédoublonne par texte
// décodé (un même signal fort peut produire deux pics voisins qui passent
// tous les deux la suppression de non-maxima et redécodent le même message).
function ft8DecodeAudioAll(samples, sampleRate, hashTable, opts){
  const syncs = ft8FindAllSync(samples, sampleRate, opts);
  const seen = new Set();
  const results = [];
  for(const sync of syncs){
    const llr = ft8ExtractLlr(samples, sync, sampleRate, opts && opts.gain);
    const text = ft8DecodeLlr(llr, hashTable, (opts && opts.maxIters) || 20);
    if(!text || seen.has(text)) continue;
    seen.add(text);
    // startSample = position EXACTE du motif de synchro Costas dans la
    // fenêtre analysée. Remonté à l'appelant parce que c'est de là que se
    // déduit le DT (décalage temporel du signal reçu) : sans lui, la page
    // n'a aucun moyen de savoir si l'horloge du PC est juste. Voir
    // logx_ft8.html, calculerDt().
    // Score NORMALISÉ par le nombre d'échantillons par symbole : c'est une
    // somme de magnitudes de Goertzel, donc proportionnelle à la cadence
    // d'échantillonnage. Non normalisé, il valait 36039 à 48 kHz et 9012 après
    // décimation pour le MÊME signal — et il variait désormais de 23 % d'une
    // carte son à l'autre (44,1 kHz décime par 3, 48 kHz par 4) contre 8 %
    // avant. Un indice affiché à l'opérateur ne doit pas dépendre de son
    // matériel. Le tri interne, lui, compare des scores d'un même appel : il
    // est indifférent au facteur.
    results.push({ text, freqHz: sync.baseFreqHz,
                   syncScore: sync.score / ft8SamplesPerSymbol(sampleRate),
                   startSample: sync.startSample });
  }
  results.sort((a, b) => b.syncScore - a.syncScore);
  return results;
}

if(typeof module !== 'undefined' && module.exports){
  module.exports = {
    FT8_DEFAULT_SAMPLE_RATE, FT8_DEFAULT_TONE0_HZ, FT8_GAUSSIAN_BT,
    ft8SamplesPerSymbol, ft8GaussianKernel, ft8SynthesizeGfsk,
    ft8GoertzelMag, ft8GoertzelToneBank, ft8CostasScore, ft8FindSync,
    ft8FindAllSync, ft8ExtractLlr, ft8DecodeAudio, ft8DecodeAudioAll,
    ft8FacteurDecimation, ft8NoyauAntiRepliement, ft8Decimer,
  };
}
