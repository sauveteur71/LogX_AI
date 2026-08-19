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

// ─── Rapport signal/bruit ─────────────────────────────────────────────────

// Correction, en dB, entre la bande de mesure d'un filtre de Goertzel sur UN
// symbole et la bande de reference conventionnelle de 2500 Hz.
//
// La reference 2500 Hz n'est pas un choix libre : c'est la convention des
// tables de seuils K1JT, deja utilisee ailleurs dans ce depot pour convertir
// des seuils de decodage (voir logx_voacap.py, « 10*log10(BW), table de
// seuils K1JT (2500 Hz) »). Un report FT8 qui ne s'y refere pas ne serait
// comparable a aucun autre report echange sur l'air.
//
// La valeur elle-meme n'est PAS ecrite de memoire ni derivee sur le papier :
// elle est MESUREE par calibration contre des signaux de rapport connu. Verite
// terrain, pour une porteuse d'amplitude A (GFSK a enveloppe constante) noyee
// dans un bruit blanc uniforme sur [-L,+L] (variance L^2/3) echantillonne a fe :
//
//     SNR_2500 = 10*log10( (A^2/2) / ((L^2/3) * 2500/(fe/2)) )
//
// Mesure sur la PLAGE REELLE du FT8, 6 tirages de bruit par palier — pas sur
// une plage confortable ou l'on ne trafique pas. Erreur RESIDUELLE du report
// final (verite terrain moins valeur rendue), offset applique :
//
//     vise     biais    pire ecart   dispersion
//     +15 dB   +0,43      0,74          0,32
//     +10 dB   +0,26      0,54          0,29
//      +5 dB   +0,18      0,44          0,27
//       0 dB   +0,18      0,43          0,24
//      -5 dB   +0,14      0,39          0,22
//     -10 dB   +0,08      0,34          0,20
//     -14 dB   -0,03      0,32          0,19
//     -17 dB   -0,21      0,43          0,29
//
//     biais global 0,13 dB — pire ecart 0,74 dB
//
// Theoriquement on attendrait 10*log10(6,25/2500) = -26,0 dB, rapport entre la
// bande d'un filtre de Goertzel sur un symbole et la reference 2500 Hz. Les
// ~1,8 dB d'ecart sont reels et reproductibles : le lissage gaussien GFSK
// etale une part de l'energie du symbole hors de son propre filtre. C'est
// precisement pourquoi cette constante est MESUREE et pas calculee — la
// theorie donne le bon ordre de grandeur, pas la bonne valeur.
//
// UNE FAUSSE PISTE, notee pour qu'on ne la reprenne pas : la puissance du
// signal est une MOYENNE et le plancher une MEDIANE, et median = ln(2) x
// moyenne pour une puissance de bruit. Corriger d'un facteur 1/ln(2) semble
// donc s'imposer. Mesure faite : ca ne change QUE l'offset (etendue de la
// derive 1,78 -> 1,77 dB), donc rien du tout apres calibration. La derive
// residuelle vient de la fuite du signal dans les sondes, pas de la.
//
// tests/test_ft8_snr.py refait la mesure : la constante ne peut pas deriver
// sans qu'un test rougisse.
const FT8_SNR_OFFSET_DB = -27.83;

// Estime le rapport signal/bruit d'un signal deja synchronise, en dB
// reference 2500 Hz — l'unite des reports FT8 echanges sur l'air.
//
// Mesure prise sur les 21 symboles de SYNCHRO (3 groupes Costas de 7) : ce
// sont les seuls dont on connaisse le ton A PRIORI, donc les seuls ou l'on
// puisse separer « le ton du signal » de « tout le reste » sans avoir decode.
//
//   signal+bruit : magnitude du ton ATTENDU ;
//   bruit seul   : magnitude des tons ECARTES D'AU MOINS DEUX crans.
//
// Les deux tons IMMEDIATEMENT voisins sont volontairement exclus du calcul du
// bruit : la frequence de base n'est affinee qu'au demi-hertz, et un signal
// legerement hors-bin fuit dans les bins adjacents. Les compter comme du
// bruit ferait baisser le rapport d'autant plus que la synchro est bonne.
//
// C'est un RAPPORT de deux puissances mesurees dans la meme fenetre : il ne
// depend donc ni du gain de la carte son, ni du volume du poste. C'est toute
// la difference avec un score de correlation brut, qui suit le niveau
// d'entree et ne veut rien dire d'un recepteur a l'autre.
// Ecarts, en crans de 6,25 Hz depuis la frequence de base, ou l'on va SONDER
// le plancher de bruit. Le signal occupe les crans 0 a 7 (50 Hz) ; on sonde
// de part et d'autre, assez loin pour sortir des jupes du signal.
//
// POURQUOI PAS DANS LA BANDE — mesure a l'appui. La premiere version prenait
// pour bruit les tons non attendus du banc, dans la bande du signal. A bas
// rapport c'etait juste (offset mesure -25,9 dB, conforme aux -26,0 attendus)
// mais a fort signal la mesure SATURAIT : ce qui tombe dans les filtres
// voisins n'est plus le bruit, c'est la fuite du signal lui-meme. Le plancher
// ne descendait plus, le rapport plafonnait vers 31 dB brut, et l'offset
// derivait de 20 dB sur la plage utile (-25,9 dB a -5,7 dB selon le signal).
// Un report qui se trompe de 20 dB sur les signaux forts ne vaut rien.
//
// Meme largeur de filtre que pour le signal (un symbole) : c'est la condition
// pour que la calibration vers 2500 Hz reste valable des deux cotes du
// rapport.
// Places de -300 a -175 Hz sous le ton du bas, et de +175 a +300 Hz au-dessus
// du ton du haut : symetrique par rapport a la bande du signal.
// La DISTANCE a ete choisie par mesure, pas par principe. Sur la plage reelle
// du FT8 (+15 a -17 dB), en comparant l'ecart a la verite terrain :
//     sondes a  50..130 Hz  : derive 0,93 dB, dispersion 0,54, pire 1,55
//     sondes a 175..300 Hz  : derive 0,44 dB, dispersion 0,44, pire 1,16
//     idem, 11 fenetres     : derive 0,45 dB, dispersion 0,36, pire 0,94
//     sondes a 225..444 Hz  : derive 0,34 dB, dispersion 0,46, pire 1,24
// Trop pres, les jupes du signal polluent le plancher et la mesure se tasse
// sur les signaux forts ; trop loin, on sort de la zone ou le bruit ressemble
// encore a celui qui gene le signal, et on rencontre plus de porteuses
// etrangeres. L'avant-derniere ligne est retenue.
const FT8_SNR_SONDES = [-48, -47, -46, -45, -44, -43, -42, -41, -40, -39, -38,
                        -37, -36, -35, -34, -33, -32, -31, -30, -29, -28,
                        35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47,
                        48, 49, 50, 51, 52, 53, 54, 55];

// Fenetres temporelles ou l'on sonde le plancher, reparties sur la trame.
// Mesure : 3 fenetres -> dispersion 0,54 dB ; 7 -> 0,44 ; 11 -> 0,36. Le cout
// est negligeable ici, la recherche de synchro domine largement le temps de
// decodage (mesure : x3,4 sur le nombre de filtres = +5 ms sur 280).
const FT8_SNR_FENETRES_BRUIT = 11;

// Plancher en dessous duquel on ne rend PAS de valeur. Sur du bruit pur, sans
// aucun signal, l'estimateur ne rendait pas « pas de mesure » mais -42 dB : la
// moyenne des 21 fenetres de signal depasse toujours un peu la mediane du
// plancher, donc la soustraction reste positive par le seul jeu du hasard.
// Un tel nombre n'a aucun sens et serait affiche tel quel.
//
// -30 dB est choisi sur MESURE, pas au jugé : ce decodeur ne decode plus rien
// en dessous de -20 dB (2 messages sur 16 a -20, 0 sur 16 a -22), et l'erreur
// propre de l'estimateur y depasse 1,3 dB a -24 et 2,4 dB a -28. En dessous de
// -30 il n'y a donc ni message a reporter ni mesure fiable a rendre.
const FT8_SNR_PLANCHER_DB = -30;

function ft8EstimerSnr(samples, startSample, baseFreqHz, sampleRate){
  const sps = ft8SamplesPerSymbol(sampleRate);
  const groups = [0, FT8_SYNC_OFFSET, 2 * FT8_SYNC_OFFSET];
  let sommeSignalPlusBruit = 0, nFenetres = 0;

  for(const g of groups){
    for(let i = 0; i < FT8_LENGTH_SYNC; i++){
      const offset = startSample + (g + i) * sps;
      if(offset < 0 || offset + sps > samples.length) return null;
      const mags = ft8GoertzelToneBank(samples, offset, sps, baseFreqHz, sampleRate);
      sommeSignalPlusBruit += mags[FT8_COSTAS_PATTERN[i]] * mags[FT8_COSTAS_PATTERN[i]];
      nFenetres++;
    }
  }
  if(!nFenetres) return null;

  // Plancher de bruit : sondes hors bande, sur des fenetres reparties sur
  // toute la trame — le plancher est stable dans le temps, mais l'echantillon
  // gagne en fiabilite a etre pris largement.
  const echantillonsBruit = [];
  const fMin = 100, fMax = sampleRate / 2 - 100;
  const derniereFenetre = FT8_NN - 1;
  for(let w = 0; w < FT8_SNR_FENETRES_BRUIT; w++){
    const symbole = Math.round(w * derniereFenetre / (FT8_SNR_FENETRES_BRUIT - 1));
    const offset = startSample + symbole * sps;
    if(offset < 0 || offset + sps > samples.length) continue;
    for(const cran of FT8_SNR_SONDES){
      const f = baseFreqHz + cran * FT8_TONE_SPACING;
      if(f < fMin || f > fMax) continue;               // bord de bande
      const m = ft8GoertzelMag(samples, offset, sps, f, sampleRate);
      echantillonsBruit.push(m * m);
    }
  }
  if(echantillonsBruit.length < 4) return null;        // trop pres du bord

  // MEDIANE, pas moyenne : la separation minimale entre deux stations
  // decodees est de 50 Hz, donc une station voisine PEUT tomber dans les
  // sondes. Une moyenne s'en trouverait tiree vers le haut et ferait
  // sous-estimer le report ; la mediane encaisse quelques sondes polluees.
  echantillonsBruit.sort((a, b) => a - b);
  const milieu = echantillonsBruit.length >> 1;
  const pBruit = (echantillonsBruit.length % 2)
    ? echantillonsBruit[milieu]
    : (echantillonsBruit[milieu - 1] + echantillonsBruit[milieu]) / 2;

  const pSignalPlusBruit = sommeSignalPlusBruit / nFenetres;
  if(!(pBruit > 0)) return null;                        // silence numerique

  // Le ton attendu porte le signal ET le bruit qui tombe dans son filtre.
  // MESURE DE L'EFFET, pour ne pas se raconter d'histoires : l'ecart entre
  // avec et sans soustraction vaut 0,01 dB a 0 dB, 0,07 a -10, 0,34 a -17,
  // 1,31 a -24 et 2,43 a -28. Elle ne change donc RIEN dans la plage ou l'on
  // trafique — c'est simplement la formule juste, et elle evite que la valeur
  // parte n'importe ou sur les signaux tres faibles.
  const pSignal = pSignalPlusBruit - pBruit;
  if(!(pSignal > 0)) return null;                       // sous le bruit

  const snr = 10 * Math.log10(pSignal / pBruit) + FT8_SNR_OFFSET_DB;
  // Pas de valeur plutot qu'une valeur qui ne veut rien dire.
  return (snr < FT8_SNR_PLANCHER_DB) ? null : snr;
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
    // snrDb : le report que l'operateur enverra reellement a cette station.
    // Sans lui, le sequenceur n'avait rien a annoncer et retombait sur une
    // valeur par defaut, la MEME pour toutes les stations — un report faux
    // envoye sur l'air a chaque QSO.
    // null quand la mesure n'est pas possible (signal sous le bruit, fenetre
    // tronquee) : c'est une absence de mesure, surtout pas un 0 dB, qui se
    // lirait comme « signal aussi fort que le bruit ».
    results.push({ text, freqHz: sync.baseFreqHz,
                   syncScore: sync.score / ft8SamplesPerSymbol(sampleRate),
                   snrDb: ft8EstimerSnr(samples, sync.startSample,
                                        sync.baseFreqHz, sampleRate),
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
    ft8EstimerSnr, FT8_SNR_OFFSET_DB, FT8_SNR_SONDES, FT8_SNR_FENETRES_BRUIT,
    FT8_SNR_PLANCHER_DB,
    ft8FindAllSync, ft8ExtractLlr, ft8DecodeAudio, ft8DecodeAudioAll,
    ft8FacteurDecimation, ft8NoyauAntiRepliement, ft8Decimer,
  };
}
