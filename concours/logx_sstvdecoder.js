// ─── DÉCODEUR SSTV DANS LE NAVIGATEUR ────────────────────────────────────────
// La SSTV (télévision à balayage lent) transmet des images fixes sur l'air :
// activations, ISS (PD120), dimanches SSTV sur 20 m/80 m. Jusqu'ici il fallait
// ouvrir MMSSTV ou RX-SSTV à côté de LogX AI. Comme pour le CW et le RTTY, le
// décodage se fait ici dans la page : rien à installer, et ça marche sur les
// postes secondaires qui n'ont que le navigateur.
//
// PRINCIPE : la luminosité de chaque pixel est codée en FRÉQUENCE (1500 Hz =
// noir, 2300 Hz = blanc), les impulsions de synchro sont à 1200 Hz. On mesure
// donc la fréquence instantanée en continu (détecteur en quadrature, comme le
// RTTY mais avec une sortie continue au lieu d'une décision binaire), puis :
//   1. l'en-tête VIS (1900/1200/1100/1300 Hz) identifie le mode — Martin,
//      Scottie, Robot, PD — et donne l'instant t0 du début d'image ;
//   2. chaque pixel est la moyenne de la fréquence sur sa fenêtre temporelle,
//      calculée d'après la table de timing du mode (spécification N7CXI,
//      « Proposal for SSTV Mode Specifications », Dayton 2000) ;
//   3. les impulsions de synchro observées recalent t0 au fil des lignes —
//      sans ça, un écart d'horloge de 0,03 % entre les cartes son TX et RX
//      (courant) penche l'image (le « slant ») bien avant la dernière ligne.
//
// Le fichier contient aussi un ENCODEUR complet : il sert aux tests
// (aller-retour encode → décode, comme le RTTY) — un signal SSTV est généré
// par machine à timing fixe, un signal synthétique est donc représentatif.

// ─── Constantes de modulation ────────────────────────────────────────────────
const SSTV_NOIR = 1500;                    // Hz — niveau 0
const SSTV_BLANC = 2300;                   // Hz — niveau 255
const SSTV_SYNC = 1200;                    // Hz — impulsions de synchro et VIS
const SSTV_PENTE = (SSTV_BLANC - SSTV_NOIR) / 255;   // Hz par niveau de gris

// ─── Table des modes ─────────────────────────────────────────────────────────
// Toutes les durées en SECONDES (les specs les donnent en ms — converties ici
// une fois pour toutes, plutôt que des /1000 éparpillés dans le code).
//
// Chaque « balayage » couvre 1 ligne d'image (Martin/Scottie/Robot) ou 2
// lignes (famille PD : Y ligne paire, chroma moyenné, Y ligne impaire).
// `canaux` décrit les fenêtres de pixels À L'INTÉRIEUR d'un balayage :
//   debut/duree — position dans le balayage ; plan — r/g/b/y/cr/cb ;
//   rangee — comment convertir l'index de balayage en n° de ligne du plan
//   ('bal' = même n°, 'demi' = bal/2, 'double0'/'double1' = 2·bal / 2·bal+1).
function sstvModeMartin(nom, vis, scan, lignes){
  // `lignes` (optionnel, défaut 256) : M3/M4 transmettent 128 balayages, pas
  // 256 (image deux fois moins haute, à la MÊME vitesse par ligne que M1/M2
  // respectivement) — cf. commentaire de sourcing sur le bloc SSTV_MODES plus
  // bas. Même pattern que sstvModePd(), qui prend déjà `hauteur` en paramètre.
  lignes = lignes || 256;
  const sync = 0.004862, porch = 0.000572, sep = 0.000572;
  return {nom, vis, famille: 'rgb', largeur: 320, hauteur: lignes, balayages: lignes,
    lignesParBalayage: 1, decalageDepart: 0,
    dureeBalayage: sync + porch + 3 * (scan + sep),
    syncDebut: 0, syncDuree: sync, sync, porch, sep, scan,
    canaux: [
      {plan: 'g', debut: sync + porch,                        duree: scan, rangee: 'bal'},
      {plan: 'b', debut: sync + porch + scan + sep,           duree: scan, rangee: 'bal'},
      {plan: 'r', debut: sync + porch + 2 * (scan + sep),     duree: scan, rangee: 'bal'},
    ]};
}
function sstvModeScottie(nom, vis, scan, lignes){
  // `lignes` (optionnel, défaut 256) : S3/S4 transmettent 128 balayages, pas
  // 256 — même remarque que sstvModeMartin() ci-dessus.
  lignes = lignes || 256;
  const sync = 0.009, porch = 0.0015, sep = 0.0015;
  return {nom, vis, famille: 'rgb', largeur: 320, hauteur: lignes, balayages: lignes,
    lignesParBalayage: 1,
    // Une unique impulsion de synchro de 9 ms précède la PREMIÈRE ligne ;
    // ensuite la synchro est AU MILIEU de chaque ligne, juste avant le rouge.
    decalageDepart: sync,
    dureeBalayage: 2 * sep + sync + porch + 3 * scan,
    syncDebut: sep + scan + sep + scan, syncDuree: sync, sync, porch, sep, scan,
    canaux: [
      {plan: 'g', debut: sep,                              duree: scan, rangee: 'bal'},
      {plan: 'b', debut: sep + scan + sep,                 duree: scan, rangee: 'bal'},
      {plan: 'r', debut: 2 * sep + 2 * scan + sync + porch, duree: scan, rangee: 'bal'},
    ]};
}
function sstvModeRobot36(){
  // 240 lignes en 150 ms : Y sur chaque ligne, chroma en alternance — lignes
  // paires R-Y (séparateur 1500 Hz), impaires B-Y (séparateur 2300 Hz).
  const sync = 0.009, porch = 0.003, scanY = 0.088, sep = 0.0045,
        porch2 = 0.0015, scanC = 0.044;
  const debutC = sync + porch + scanY + sep + porch2;
  return {nom: 'Robot 36', vis: 8, famille: 'robot36', largeur: 320, hauteur: 240,
    balayages: 240, lignesParBalayage: 1, decalageDepart: 0,
    dureeBalayage: debutC + scanC,
    syncDebut: 0, syncDuree: sync, sync, porch, sep, porch2, scanY, scanC,
    canauxPair: [
      {plan: 'y',  debut: sync + porch, duree: scanY, rangee: 'bal'},
      {plan: 'cr', debut: debutC,       duree: scanC, rangee: 'demi'},
    ],
    canauxImpair: [
      {plan: 'y',  debut: sync + porch, duree: scanY, rangee: 'bal'},
      {plan: 'cb', debut: debutC,       duree: scanC, rangee: 'demi'},
    ]};
}
function sstvModeRobot72(){
  const sync = 0.009, porch = 0.003, scanY = 0.138, sep = 0.0045,
        porch2 = 0.0015, scanC = 0.069;
  const debutCr = sync + porch + scanY + sep + porch2;
  const debutCb = debutCr + scanC + sep + porch2;
  return {nom: 'Robot 72', vis: 12, famille: 'robot72', largeur: 320, hauteur: 240,
    balayages: 240, lignesParBalayage: 1, decalageDepart: 0,
    dureeBalayage: debutCb + scanC,
    syncDebut: 0, syncDuree: sync, sync, porch, sep, porch2, scanY, scanC,
    canaux: [
      {plan: 'y',  debut: sync + porch, duree: scanY, rangee: 'bal'},
      {plan: 'cr', debut: debutCr,      duree: scanC, rangee: 'bal'},
      {plan: 'cb', debut: debutCb,      duree: scanC, rangee: 'bal'},
    ]};
}
function sstvModePd(nom, vis, scan, largeur, hauteur){
  // Famille PD : un balayage = DEUX lignes d'image. Y(2k), R-Y et B-Y moyennés
  // sur la paire, Y(2k+1). C'est le format de l'ISS (PD120).
  const sync = 0.020, porch = 0.00208;
  return {nom, vis, famille: 'pd', largeur, hauteur, balayages: hauteur / 2,
    lignesParBalayage: 2, decalageDepart: 0,
    dureeBalayage: sync + porch + 4 * scan,
    syncDebut: 0, syncDuree: sync, sync, porch, scan,
    canaux: [
      {plan: 'y',  debut: sync + porch,            duree: scan, rangee: 'double0'},
      {plan: 'cr', debut: sync + porch + scan,     duree: scan, rangee: 'bal'},
      {plan: 'cb', debut: sync + porch + 2 * scan, duree: scan, rangee: 'bal'},
      {plan: 'y',  debut: sync + porch + 3 * scan, duree: scan, rangee: 'double1'},
    ]};
}
function sstvModeMono(nom, vis, scan, largeur, hauteur){
  // Famille `mono` (Robot 8/12/24 BW, Lot B2) : sync PUIS un seul balayage
  // luminance — pas de porch ni de séparateur (mode monochrome, un seul
  // canal). sync=7ms/porch=0 sont UNIFORMES sur les 3 modes de la famille —
  // SOURCE : slowrx (windytan/slowrx, modespec.c — SyncTime=7e-3,
  // PorchTime=0 pour R8BW/R12BW/R24BW) × pySSTV (dnet/pySSTV,
  // pysstv/grayscale.py — SYNC=7 pour Robot8BW/Robot24BW, ce dernier
  // n'implémentant pas Robot12BW). `scan` (DURÉE de balayage, indépendante
  // du nombre de pixels), `largeur` et `hauteur` sourcés par mode, cf. bloc
  // SSTV_MODES plus bas et test_timing_robot_bw_est_source.
  //
  // ⚠️ `largeur` EST paramétré (pas figé à 320) : R8BW/R12BW font 160 px de
  // large, seul R24BW fait 320 — cf. commentaires par mode ci-dessous. Une
  // première version figeait 320 partout (défaut trouvé en revue) : le
  // recoupement `scan × largeur` ne pouvait PAS le détecter car il est
  // invariant par produit (160×0.375ms = 320×0.1875ms = 60ms) — seule la
  // largeur "fil" réelle, sourcée séparément, tranche le partage
  // largeur/temps-par-pixel. Même piège de "doublage d'affichage" que la
  // hauteur des M3/M4 (slowrx normalise `ImgWidth=320` dans son buffer
  // d'affichage pour les 3, ce n'est pas la largeur transmise).
  const sync = 0.007, porch = 0;
  return {nom, vis, famille: 'mono', largeur, hauteur, balayages: hauteur,
    lignesParBalayage: 1, decalageDepart: 0,
    dureeBalayage: sync + porch + scan,
    syncDebut: 0, syncDuree: sync, sync, porch, scan,
    canaux: [
      {plan: 'y', debut: sync + porch, duree: scan, rangee: 'bal'},
    ]};
}

function sstvModeSc2(nom, vis, scan){
  // Famille `rgb` RÉUTILISÉE (Lot B3, Wraase SC2-120/180) — PAS une nouvelle
  // famille DSP : structure par ligne identique à Martin/Scottie (synchro +
  // porch puis 3 canaux couleur dos-à-dos), déjà couverte par la branche
  // `famille === 'rgb'` de `_emettreBalayage`. Confirmé au niveau du CODE
  // décodeur réel (pas seulement sa table de constantes) : slowrx
  // (windytan/slowrx, video.c/GetVideo()) ne spécialise PAS W2120/W2180 dans
  // son switch(Mode) — contrairement à Robot36/Robot24/Scottie/PD qui ONT
  // leur propre `case` — ils tombent dans le `default`, la MÊME formule
  // générique que Martin (ChanStart[0]=Sync+Porch, ChanStart[n]=
  // ChanStart[n-1]+ChanLen[n-1]+SeptrTime).
  //
  // ⚠️ PIÈGE Wraase (signalé au brief) : ordre des canaux R, G, B — PAS
  // G, B, R comme Martin/Scottie. SOURCE croisée à 3 implémentations/docs
  // indépendantes : N7CXI (Dayton 2000, section "WRASSE SC2-180", "SCAN
  // SEQUENCE Red, Green, Blue") × slowrx (modespec.c, `ColorEnc = RGB` pour
  // W2120/W2180, PAS `GBR` comme M1-M4/S1-SDX ; video.c confirme le mapping
  // DIRECT canal0→rouge/canal1→vert/canal2→bleu pour `ColorEnc=RGB`, contre
  // une permutation pour `GBR`) × pySSTV (dnet/pySSTV, color.py,
  // `WraaseSC2180`/`WraaseSC2120` : `COLOR_SEQ=(Color.red, Color.green,
  // Color.blue)` pour LES DEUX modes).
  //
  // sync=5.5225ms/porch=0.5ms/SEP=0 (pas de séparateur, contrairement à
  // Martin/Scottie) IDENTIQUES pour SC2-120 et SC2-180 (slowrx : SyncTime/
  // PorchTime/SeptrTime des 2 entrées W2120/W2180, valeurs identiques ;
  // pySSTV : SC2-120 hérite SYNC/PORCH de SC2-180 sans les redéfinir).
  // `scan` (durée de balayage d'un canal, sourcée séparément par mode) : cf.
  // commentaire détaillé + discordance N7CXI/slowrx documentée dans le bloc
  // SSTV_MODES plus bas et test_timing_wraase_sc2_est_source.
  const sync = 0.0055225, porch = 0.0005, sep = 0;
  return {nom, vis, famille: 'rgb', largeur: 320, hauteur: 256, balayages: 256,
    lignesParBalayage: 1, decalageDepart: 0,
    dureeBalayage: sync + porch + 3 * scan,
    syncDebut: 0, syncDuree: sync, sync, porch, sep, scan,
    canaux: [
      {plan: 'r', debut: sync + porch,               duree: scan, rangee: 'bal'},
      {plan: 'g', debut: sync + porch + scan,         duree: scan, rangee: 'bal'},
      {plan: 'b', debut: sync + porch + 2 * scan,     duree: scan, rangee: 'bal'},
    ]};
}

const SSTV_MODES = {};                     // indexés par code VIS
const SSTV_MODES_PAR_NOM = {};             // indexés par nom court (M1, S1…)
for(const [cle, m] of Object.entries({
  M1:   sstvModeMartin('Martin M1', 44, 0.146432),
  M2:   sstvModeMartin('Martin M2', 40, 0.073216),
  // M3/M4 (Lot B1, 03/09/2026) : PAS de simples variantes de VIS de M1/M2 à
  // hauteur égale — ce sont des versions à 128 balayages (moitié de M1/M2),
  // à la MÊME vitesse de balayage par ligne que leur mode "parent" (`scan`
  // identique à M1/M2 respectivement). SOURCE VIS+scan+hauteur : croisement
  // sstv-handbook.com (OK2MNM, table Martin — VIS 36/32, 128 lignes, durée
  // publiée 57s/29s, lpm 134.395/264.553) × slowrx (windytan/slowrx,
  // modespec.c+VISmap[] — seul décodeur tiers en production à définir M3/M4
  // explicitement : VIS 0x24=36/0x20=32, NumLines=128 confirmés ; LineTime
  // de M3=446.446ms confirme scan=M1 malgré un PixelTime incohérent dans ce
  // fichier tiers, probablement une coquille de transcription — écarté au
  // profit du LineTime, cohérent avec sstv-handbook) × docs.preterhuman.net
  // (compilation VIS historique WB2OSZ + table durées, note 'c' "128 lignes
  // dont 120 utiles", même convention que "256 dont 240 utiles" déjà connue
  // pour M1/M2/S1/S2/DX). Recoupement arithmétique détaillé dans
  // tests/test_sstv_decodeur.py::test_timing_martin_scottie_ajoutes_sont_sources.
  M3:   sstvModeMartin('Martin M3', 36, 0.146432, 128),
  M4:   sstvModeMartin('Martin M4', 32, 0.073216, 128),
  S1:   sstvModeScottie('Scottie S1', 60, 0.13824),
  S2:   sstvModeScottie('Scottie S2', 56, 0.088064),
  // S3/S4 (Lot B1) : même situation que M3/M4 ci-dessus — 128 balayages,
  // `scan` identique à S1/S2 respectivement. SOURCE : sstv-handbook.com (VIS
  // 52/48, 128 lignes, durée publiée 55s/36s, lpm 140.115/216.067) ×
  // docs.preterhuman.net (VIS WB2OSZ 0x34=52/0x30=48 sur la colonne Scottie
  // de la table de compilation, durées 55s/36s identiques, note 'c' "128
  // lignes dont 120 utiles"). slowrx NE définit PAS S3/S4 (absents de son
  // VISmap[]) — pas de 3e source indépendante pour ces deux-là, seulement 2
  // qui s'accordent exactement (VIS et durée publiée identiques au chiffre
  // près) + le recoupement arithmétique (test dédié, cf. M3/M4 ci-dessus).
  S3:   sstvModeScottie('Scottie S3', 52, 0.13824, 128),
  S4:   sstvModeScottie('Scottie S4', 48, 0.088064, 128),
  SDX:  sstvModeScottie('Scottie DX', 76, 0.3456),
  R36:  sstvModeRobot36(),
  R72:  sstvModeRobot72(),
  PD50:  sstvModePd('PD50',  93, 0.09152,  320, 240),
  PD90:  sstvModePd('PD90',  99, 0.17024,  320, 240),
  PD120: sstvModePd('PD120', 95, 0.1216,   640, 496),
  PD160: sstvModePd('PD160', 98, 0.195584, 512, 400),
  PD180: sstvModePd('PD180', 96, 0.18304,  640, 496),
  PD240: sstvModePd('PD240', 97, 0.24448,  640, 496),
  PD290: sstvModePd('PD290', 94, 0.2288,   800, 616),
  // Famille `mono` (Lot B2, 03/09/2026) : Robot 8/12/24 BW — sync + UN SEUL
  // balayage luminance (rendu gris R=G=B), pas de porch ni de séparateur.
  // SOURCES croisées (détail complet dans le commentaire de sstvModeMono()
  // et test_timing_robot_bw_est_source) : slowrx (windytan/slowrx,
  // modespec.c) × pySSTV (dnet/pySSTV, grayscale.py — R8BW/R24BW seulement)
  // × sstv-handbook.com (BruXy/sstv-handbook, sstv/bw_mode.ctex, table
  // "Parameters of black and white SSTV modes") × recoupement arithmétique
  // contre la durée totale publiée par WB2OSZ (John Langner, compilation
  // "SSTV Transmission Modes", mars 1996 — antérieure à N7CXI 2000, qui ne
  // définit PAS ces modes BW : vérifié par grep sur le texte du PDF N7CXI
  // lui-même, le commentaire "// N7CXI, 2000" présent dans modespec.c pour
  // ces 3 entrées est un intitulé de bloc erroné).
  //
  // `scan` = DURÉE de balayage d'une ligne entière (indépendante du nombre
  // de pixels). `largeur` = nombre de pixels transmis PAR ligne (largeur
  // "fil"), sourcé SÉPARÉMENT car le recoupement scan×largeur est invariant
  // par produit et ne peut pas le déduire :
  //   R8BW  : scan=0.0599 (slowrx PixelTime 0.1871875e-3 × ImgWidth 320 ;
  //           = pySSTV SCAN 60 ms à 0.17% près, DURÉE cohérente) ;
  //           largeur=160 (pySSTV Robot8BW.WIDTH=160 × sstv-handbook
  //           "Robot B&W 8 : 160×120" — 2 sources) ; hauteur=120 (slowrx
  //           NumLines, pySSTV HEIGHT, WB2OSZ "8 sec / 120 lignes").
  //           dureeBalayage=0.0669 → 120×0.0669=8.028s (WB2OSZ 8s, +0.35%).
  //   R12BW : scan=0.09312 (slowrx PixelTime 0.291e-3 × 320 ; = sstv-handbook
  //           "Scan line 93.0 ms" à 0.13% près) ; largeur=160 (sstv-handbook
  //           "Robot B&W 12 : 160×120" — SOURCE UNIQUE directe, pySSTV
  //           n'implémente pas ce mode ; corroboré structurellement : même
  //           ligne de résolution que BW8 dans la table, et WB2OSZ "120
  //           lignes" identique à BW8) ; hauteur=120 (slowrx, WB2OSZ).
  //           dureeBalayage=0.10012 → 120×0.10012=12.014s (WB2OSZ 12s,+0.12%).
  //           VIS=6 slowrx SEUL (pedrokv.com donne VIS=8, mais source
  //           auto-contradictoire — cf. rapport). Confiance la plus basse
  //           des 3 (VIS + largeur à source unique, pas de WAV externe).
  //   R24BW : scan=0.09312 (slowrx 0.291e-3 × 320 ; = pySSTV SCAN 93 ms) ;
  //           largeur=320 (pySSTV Robot24BW.WIDTH=320 × sstv-handbook
  //           "Robot B&W 24 : 320×240" — 2 sources) ; hauteur=240 (slowrx,
  //           pySSTV, WB2OSZ). dureeBalayage=0.10012 → 240×0.10012=24.029s
  //           (WB2OSZ 24s, +0.12%).
  R8BW:  sstvModeMono('Robot 8 BW',  2,  0.0599,  160, 120),
  R12BW: sstvModeMono('Robot 12 BW', 6,  0.09312, 160, 120),
  R24BW: sstvModeMono('Robot 24 BW', 10, 0.09312, 320, 240),
  // Famille `rgb` réutilisée (Lot B3, 03/09/2026) : Wraase SC2-120/180 — cf.
  // commentaire complet de sstvModeSc2() ci-dessus (décision famille +
  // ordre des canaux) et test_timing_wraase_sc2_est_source (recoupement
  // détaillé). Résumé du choix de `scan` par mode (discordance interne à
  // slowrx entre son champ PixelTime et son champ LineTime, même motif que
  // M3 au Lot B1 — tranchée en gardant la valeur qui RECONCILIE le mieux
  // avec le LineTime déclaré, chiffres exacts dans le test dédié) :
  //   SC2-180 : scan=0.235 (N7CXI "COLOR SCAN TIME 235.000ms" exact — PAS le
  //             0.23505024 impliqué par le PixelTime de slowrx) — reconcilie
  //             EXACTEMENT le LineTime slowrx (711.0225ms) et correspond au
  //             SCAN=235.0 de pySSTV. 256 balayages × 0.7110225 = 182.02 s
  //             (N7CXI "182 seconds" publié — PAS 180 malgré le nom,
  //             vérifié).
  //   SC2-120 : scan=0.1564925 (PixelTime slowrx 0.489039081e-3 × 320 — PAS
  //             le 0.156 arrondi de pySSTV) — reconcilie le LineTime slowrx
  //             (475.530018ms) à 30µs près (0.006%), contre 1.5ms d'écart
  //             (0.32%) avec la valeur pySSTV (qui ajoute par ailleurs des
  //             impulsions de porch supplémentaires entre canaux pour ce
  //             mode précis, en rustine d'interopérabilité déclarée
  //             incertaine par son propre auteur — écartée du modèle
  //             structurel ici, cf. sstvModeSc2()). 256 × 0.4755000 = 121.73
  //             s (nom "SC2-120" lui aussi approximatif — vérifié, pas
  //             supposé).
  // VIS : SC2-180=55 (0x37), SC2-120=63 (0x3F) — slowrx VISmap[] ET pySSTV
  // VIS_CODE, 2 sources exactement concordantes pour les 2 modes.
  SC2_120: sstvModeSc2('Wraase SC2-120', 63, 0.1564925),
  SC2_180: sstvModeSc2('Wraase SC2-180', 55, 0.235),
})){
  m.cle = cle;
  SSTV_MODES[m.vis] = m;
  SSTV_MODES_PAR_NOM[cle] = m;
}

// ─── Conversions couleur (ITU-R BT.601, coefficients de la spec N7CXI) ──────
// Les modes Robot et PD transmettent Y / R-Y / B-Y, pas du RGB.
function sstvClamp255(v){ return v < 0 ? 0 : (v > 255 ? 255 : v); }
function sstvRgbVersYcc(r, g, b){
  return [16 + (65.738 * r + 129.057 * g + 25.064 * b) / 256,
          128 + (112.439 * r - 94.154 * g - 18.285 * b) / 256,
          128 + (-37.945 * r - 74.494 * g + 112.439 * b) / 256];
}
function sstvYccVersRgb(y, cr, cb){
  return [sstvClamp255((298.082 * (y - 16) + 408.583 * (cr - 128)) / 256),
          sstvClamp255((298.082 * (y - 16) - 208.120 * (cr - 128) - 100.291 * (cb - 128)) / 256),
          sstvClamp255((298.082 * (y - 16) + 516.412 * (cb - 128)) / 256)];
}

// ─── Énergie glissante à UNE fréquence (bin DFT sur fenêtre glissante) ───────
// Généralise le Goertzel corrélé d'A3 (_suivreCorr, image-scoped) en composant
// AUTONOME et paramétré : plusieurs instances tournent pendant l'ACQUISITION VIS
// (leader 1900, sync/start 1200, bits 1100/1300), AVANT qu'une image existe —
// là où les buffers _corr* d'A3 (dimensionnés et remis à zéro à _demarrerImage)
// sont inutilisables. On corrèle le signal BRUT x contre e^{-jωn} sur une fenêtre
// glissante de `nFenetre` échantillons et on renvoie l'énergie |Σ x·e^{-jωn}|²
// NORMALISÉE par la fenêtre : pour une tonalité pure d'amplitude A au bin, elle
// vaut A²/4 quel que soit nFenetre — un intégrateur qui moyenne le bruit et rend
// une décision d'énergie comparable d'une instance à l'autre.
function EnergieGlissante(freqHz, nFenetre, sampleRate){
  this.w = 2 * Math.PI * freqHz / sampleRate; this.ph = 0;
  this.n = Math.max(3, nFenetre | 0);
  this.ringC = new Float32Array(this.n); this.ringS = new Float32Array(this.n);
  this.sc = 0; this.ss = 0; this.idx = 0;
}
EnergieGlissante.prototype.pousser = function(x){
  const c = Math.cos(this.ph), s = Math.sin(this.ph);
  this.ph += this.w; if(this.ph > 2 * Math.PI) this.ph -= 2 * Math.PI;
  const kc = x * c, ks = x * s, i = this.idx;
  this.sc += kc - this.ringC[i]; this.ss += ks - this.ringS[i];   // ajoute l'entrant, retire le sortant
  this.ringC[i] = kc; this.ringS[i] = ks;
  this.idx = (i + 1) % this.n;
  return (this.sc * this.sc + this.ss * this.ss) / (this.n * this.n);   // énergie normalisée
};

// ─── Décodeur ────────────────────────────────────────────────────────────────
// Consomme des blocs d'échantillons audio (pousser), produit des lignes RGBA
// (onLigne) au fil de la réception. États : leader → vis-start → vis-bits →
// image → retour à leader (prêt pour l'image suivante).
class SstvDecodeur {
  constructor({sampleRate = 44100, onDebutImage, onLigne, onFinImage, onEtat, estimPixel = 'ponderee', syncCorrelation = true, acqVisRobuste = true} = {}){
    this.sampleRate = sampleRate;
    this.onDebutImage = onDebutImage || (() => {});
    this.onLigne = onLigne || (() => {});
    this.onFinImage = onFinImage || (() => {});
    this.onEtat = onEtat || (() => {});
    // A3 : recalage de t0 par CORRELATION plutot que par seuil instantane.
    // `false` = comportement historique bit-a-bit (seuil f<1350 + _recalerSync,
    //   conserves intacts pour la mesure A/B) ;
    // `true` (defaut) = le pic d'une energie glissante a 1200 Hz sur une fenetre
    //   = duree de sync du mode pilote le recalage (_recalerSyncCorr). Un
    //   integrateur moyenne le bruit : l'impulsion de synchro ressort la ou le
    //   seuil instantane la manque des qu'un echantillon bruite remonte au-dessus.
    // Levier principal contre le decrochage AWGN (spec §3) — A1 rejete (inerte),
    // A2 sans effet sur bruit blanc pur ; A3 attaque le vrai mode d'echec (sync).
    this._syncCorrelation = syncCorrelation;
    this._corrRingC = null; this._corrRingS = null;   // contributions cos/sin (x·e^{-jωn})
    this._corrCos = 0; this._corrSin = 0;              // sommes glissantes sur la fenetre
    this._corrIdx = 0; this._corrN = 0;                // curseur d'anneau, taille de fenetre
    this._corrW = 0; this._corrPh = 0;                 // ω=2π·1200/fs, phase courante repliee
    this._corrPic = 0; this._corrPicN = -1;            // max d'energie suivi + son echantillon
    this._corrBal = -1;                                // balayage dont la fenetre de sync est suivie
    this._corrDernierBal = -1;                         // dernier balayage recale (garde monotone)
    // A2 : reduction d'une cellule de pixel a une valeur unique.
    // 'moyenne' = comportement historique (branche off pour l'A/B) ;
    // 'mediane' = mediane des frequences de la cellule ;
    // 'ponderee' = moyenne ponderee par l'amplitude I/Q instantanee
    // (_lastAmpl), qui deprioritise les echantillons a I/Q effondre.
    this._estimPixel = estimPixel;
    // Amplitude I/Q instantanée du dernier échantillon (mise à jour dans _freq).
    // Levier A1 (« limiteur » : normaliser le vecteur I/Q avant l'atan2 du
    // discriminateur) a été MESURÉ INERTE et REJETÉ : atan2(k·y,k·x)=atan2(y,x)
    // pour k>0, donc mettre chaque vecteur à l'échelle avant l'atan2 ne change
    // rien à la phase (gain nul prouvé, 0.5 dB de résolution sur M1/R36/PD90).
    // On garde SEULEMENT l'exposition de _lastAmpl : le levier A2 (estimation
    // de pixel pondérée par l'amplitude) s'en sert pour dépriorer les
    // échantillons à I/Q effondré.
    this._lastAmpl = 0;

    // Détecteur de fréquence en quadrature, centré entre le bit VIS le plus
    // bas (1100 Hz) et le blanc (2300 Hz). Le filtre I/Q (~800 Hz) doit
    // laisser passer ±600 Hz de bande de base : plus étroit, les transitions
    // entre pixels bavent ; plus large, le bruit entre.
    //
    // DEUX étages de filtrage + moyenne glissante sur la fréquence : le
    // mélange produit aussi une composante IMAGE à f+fc (≈ 3600 Hz pour le
    // leader). Un seul pôle ne l'atténue qu'à 22 % — la fréquence instantanée
    // oscillait alors de ±800 Hz autour de la vraie valeur, assez pour que le
    // compteur de leader (fenêtre ±75 Hz) ne monte JAMAIS, tout en restant
    // invisible sur une moyenne (constaté en test : moyenne à 1900 pile,
    // détection à zéro). Deux pôles la ramènent à 5 %, la moyenne glissante
    // de 0,6 ms (≈ 2 périodes de l'image) mange l'essentiel du reste :
    // ondulation résiduelle ±20 Hz, compatible avec toutes les fenêtres de
    // décision de ce fichier.
    this._fc = 1700;
    this._wc = 2 * Math.PI * this._fc / sampleRate;
    this._alpha = 1 - Math.exp(-2 * Math.PI * 800 / sampleRate);
    this._ph = 0;                       // phase de l'oscillateur local (repliée)
    this._I = 0; this._Q = 0;           // étage 1
    this._I2 = 0; this._Q2 = 0;         // étage 2
    this._Ip = 0; this._Qp = 0;
    const nMoy = Math.max(3, Math.round(0.0006 * sampleRate));
    this._fRing = new Float32Array(nMoy);
    this._fIdx = 0; this._fSomme = 0;

    // F2a : ACQUISITION VIS par ÉNERGIE glissante (bin DFT) plutôt que par seuils
    // de fréquence INSTANTANÉE. `false` = comportement historique bit-à-bit
    //   (_chercherLeader sur |f-1900|<75, conservé intact pour la mesure A/B) ;
    // `true` (défaut) = le leader est détecté par une énergie 1900 Hz soutenue qui
    //   DOMINE l'énergie 1200 Hz (intègre le bruit ; invariant au fading PLAT, où
    //   e1900 ET e1200 chutent ensemble en laissant leur rapport intact).
    // Fenêtre ~10 ms (deux tiers d'un bit VIS de 30 ms : compromis intégration/
    // réactivité). Estimateurs créés seulement si l'option est active (rien ne
    // coûte en OFF). _eSync/_eUn/_eZero sont posés ici pour être CONSOMMÉS par
    // F2b (bits VIS souples) — ne pas les renommer.
    this._acqVisRobuste = acqVisRobuste;
    if(acqVisRobuste){
      const nAcq = Math.max(3, Math.round(0.010 * sampleRate));
      this._eLeader = new EnergieGlissante(1900, nAcq, sampleRate);   // leader/VIS 1900
      this._eSync   = new EnergieGlissante(1200, nAcq, sampleRate);   // sync/start/stop 1200
      this._eUn     = new EnergieGlissante(1100, nAcq, sampleRate);   // bit = 1
      this._eZero   = new EnergieGlissante(1300, nAcq, sampleRate);   // bit = 0
      this._eLeaderPeak = 0;   // peak-hold décroissant de e1900 (niveau du leader reçu)
    }

    this._n = 0;                        // index d'échantillon global
    this._etat = 'leader';
    this._leaderEch = 0;                // échantillons de leader 1900 Hz cumulés
    this._visDebut = 0;                 // front leader→1200 (candidat bit de start)
    this._visAcc = 0; this._visCnt = 0;
    this._visSommes = null; this._visComptes = null;

    // Image en cours
    this._mode = null;
    this._t0 = 0;                       // début d'image, en échantillons (float)
    this._plans = null;
    this._balayage = 0;
    this._cellCle = -1; this._cellSomme = 0; this._cellCompte = 0;
    this._cellSommePoids = 0;           // A2 ponderee : somme des amplitudes
    this._cellFreqs = [];               // A2 mediane : frequences de la cellule
    this._cellPlan = null; this._cellIdx = 0;
    this._basDebut = -1;                // début du passage sous 1350 Hz en cours
    this.rgba = null;                   // image RGBA complète (remplie ligne à ligne)
    this.lignesEmises = 0;
    this._dernierVis = null;
    this._complete = false;
  }

  // Fréquence instantanée d'un échantillon. Mélange en quadrature vers la
  // bande de base puis dérivée de phase entre deux échantillons successifs :
  // exact en régime établi quel que soit le filtre, contrairement à un
  // Goertzel par blocs qui imposerait un compromis résolution/temps (le pixel
  // Martin M2 ne dure que 0,23 ms).
  _freq(x){
    const c = Math.cos(this._ph), s = Math.sin(this._ph);
    this._ph += this._wc;
    if(this._ph > 2 * Math.PI) this._ph -= 2 * Math.PI;
    const a = this._alpha;
    this._Ip = this._I2; this._Qp = this._Q2;
    this._I += (x * c - this._I) * a;
    this._Q += (x * s - this._Q) * a;
    this._I2 += (this._I - this._I2) * a;
    this._Q2 += (this._Q - this._Q2) * a;
    // Amplitude I/Q instantanée du vecteur d'étage 2 — exposée pour le levier
    // A2 (pondération pixel). N'influe PAS sur le discriminateur ci-dessous
    // (atan2 est invariant à l'échelle du vecteur : cf. A1 rejeté, constructeur).
    this._lastAmpl = Math.hypot(this._I2, this._Q2);
    const dphi = Math.atan2(this._I2 * this._Qp - this._Q2 * this._Ip,
                            this._Q2 * this._Qp + this._I2 * this._Ip);
    const f = this._fc + dphi * this.sampleRate / (2 * Math.PI);
    this._fSomme += f - this._fRing[this._fIdx];
    this._fRing[this._fIdx] = f;
    this._fIdx = (this._fIdx + 1) % this._fRing.length;
    return this._fSomme / this._fRing.length;
  }

  pousser(samples){
    for(let i = 0; i < samples.length; i++){
      const f = this._freq(samples[i]);
      this._n++;
      if(this._etat === 'leader')          this._chercherLeader(f, samples[i]);
      else if(this._etat === 'vis-start')  this._verifierStart(f, samples[i]);
      else if(this._etat === 'vis-bits')   this._lireBitsVis(f, samples[i]);
      else                                 this._decoderImage(f, samples[i]);
    }
  }

  // Leader : au moins 100 ms de 1900 Hz avant d'accepter un front vers
  // 1200 Hz. Le compteur DÉCROÎT sur les échantillons hors tolérance au lieu
  // de repartir de zéro : un craquement ne doit pas faire perdre le leader.
  _chercherLeader(f, raw){
    if(this._acqVisRobuste){
      const e1900 = this._eLeader.pousser(raw);
      const e1200 = this._eSync.pousser(raw);
      this._eUn.pousser(raw); this._eZero.pousser(raw);   // maintenir toutes les phases
      // Peak-hold décroissant du niveau leader (0.9999^n atteint 1/e à n≈10 000,
      // soit ~0,23 s à 44,1 kHz) : suit le pic récent d'énergie 1900 pour un seuil
      // AUTO-CALIBRÉ.
      this._eLeaderPeak = e1900 > this._eLeaderPeak
                        ? e1900 : this._eLeaderPeak * 0.9999;
      // ACCUMULATION du leader par ÉNERGIE : e1900 DOMINE nettement e1200 (gate de
      // sélectivité, invariant au fading plat et rejetant le bruit blanc qui ne
      // privilégie aucun bin), ET porte une énergie cohérente avec son pic récent
      // (_eSeuilLeader, floor relatif anti-silence). C'est le vrai levier : le
      // compteur monte sur une DÉCISION D'ÉNERGIE intégrée là où le seuil de f
      // instantané (±75 Hz, branche OFF) décroche dès qu'un échantillon bruité
      // sort de la fenêtre — d'où l'acquisition qui tient bien plus bas en SNR.
      //
      // L'ÉDGE leader→start est en revanche daté sur la fréquence INSTANTANÉE
      // (f<1400) pour MINIMISER le lag de t0. Attention : ce n'est PAS un ancrage
      // identique à l'historique. Le `else if(f<1400 …)` n'est atteint que quand
      // le `if(e1900>2·e1200 …)` est FAUX ; or e1900 intègre sur la fenêtre ~10 ms,
      // donc le gate de dominance reste vrai ~4 ms après la chute réelle du ton →
      // _visDebut est capturé ~2-3 ms PLUS TARD que la branche OFF (qui, elle, tire
      // sur le f<1400 instantané ~1-2 ms après la chute). Dater plutôt sur le
      // franchissement d'énergie e1200>2·e1900 coûterait ~6 ms (l'énergie 1200 doit
      // d'abord remplir la fenêtre) : le passage à f<1400 RAMÈNE ce lag de ~6 ms à
      // un résidu de ~2-3 ms, sans l'éliminer. Ce résidu est un OFFSET HORIZONTAL
      // CONSTANT (pas un slant), absorbé empiriquement par le recalage A3 (±2,5 ms
      // par impulsion) — d'où l'absence de régression MAE en clair (43/43). On
      // garde ainsi la ROBUSTESSE d'énergie pour DÉTECTER le leader et la fréquence
      // instantanée pour le DATER au mieux. Sous fading plat comme sous bruit, f au
      // bit de start moyenne 1200 (fréquence préservée, seule l'amplitude fade),
      // l'edge reste net.
      if(e1900 > 2 * e1200 && e1900 > this._eSeuilLeader()){
        this._leaderEch++;
      } else if(f < 1400 && this._leaderEch > 0.1 * this.sampleRate){
        this._etat = 'vis-start'; this._visDebut = this._n;
        this._visAcc = 0; this._visCnt = 0; this._leaderEch = 0;
        this._eLeaderPeak = 0;
      } else {
        this._leaderEch = Math.max(0, this._leaderEch - 4);
      }
      return;
    }
    // ── branche OFF : historique bit-à-bit, INCHANGÉE (mesure A/B) ──
    if(Math.abs(f - 1900) < 75){
      this._leaderEch++;
    } else if(f < 1400 && this._leaderEch > 0.1 * this.sampleRate){
      this._etat = 'vis-start';
      this._visDebut = this._n;
      this._visAcc = 0; this._visCnt = 0;
      this._leaderEch = 0;
    } else {
      this._leaderEch = Math.max(0, this._leaderEch - 4);
    }
  }

  // Seuil d'énergie pour valider un échantillon de leader. PAS une constante
  // magique liée à l'amplitude reçue (inconnue en réel : AGC, propagation) mais
  // un seuil RELATIF au peak-hold décroissant de l'énergie 1900 Hz (_eLeaderPeak),
  // qui s'auto-calibre sur n'importe quel niveau de signal. Le rejet du BRUIT est
  // porté par le gate de sélectivité e1900>2*e1200 (le bruit blanc ne privilégie
  // pas 1900 sur 1200) et par la décroissance -4 du compteur ; ce floor n'exige
  // que la cohérence du leader avec son propre pic récent, SANS le rejeter dans
  // les creux de fading PLAT (où e1900 ET e1200 chutent ensemble, laissant le
  // RATIO — donc le gate — intact). Fraction 1/16 (~ -12 dB) : choisie basse
  // exprès pour tolérer des creux jusqu'à ~12 dB sous le pic tout en écartant le
  // régime silence/cold-start (e1900 ≈ 0). MESURÉ (balayage de fraction, banc
  // F2a, R36) : à 1/2 le floor rejette les creux de fading et l'acquisition sous
  // QSB lent (0,2 Hz) tombe à 0 ; à 1/4 et en dessous (1/8, 1/16, 1/32, 0) elle
  // est identique (0,60) — le gate de ratio porte alors la décision, le floor
  // n'est plus limitant. 1/16 retenu : franchement dans la zone plate, marge
  // confortable au-dessus du régime silence.
  _eSeuilLeader(){
    return this._eLeaderPeak * 0.0625;
  }

  // Le front vers 1200 Hz peut être la CASSURE de 10 ms au milieu de
  // l'en-tête, pas le bit de start (30 ms). On ne juge que sur la fenêtre
  // [5 ; 25 ms] : pour la cassure, la moyenne est tirée vers 1900 (le leader
  // a repris dès 10 ms) et le candidat est rejeté — le second leader de
  // 300 ms redonne largement les 100 ms nécessaires avant le vrai start.
  _verifierStart(f){
    const tau = this._n - this._visDebut;
    const fs = this.sampleRate;
    if(tau >= 0.005 * fs && tau <= 0.025 * fs){ this._visAcc += f; this._visCnt++; }
    if(tau >= 0.030 * fs){
      const moy = this._visCnt ? this._visAcc / this._visCnt : 0;
      if(Math.abs(moy - SSTV_SYNC) <= 100){
        this._etat = 'vis-bits';
        this._visSommes = new Float64Array(9);
        this._visComptes = new Int32Array(9);
      } else {
        this._etat = 'leader';
      }
    }
  }

  // 9 créneaux de 30 ms après le bit de start : 7 bits de données (poids
  // faible d'abord, 1100 Hz = 1, 1300 Hz = 0), parité PAIRE, bit de stop à
  // 1200 Hz. On moyenne le CENTRE de chaque créneau ([5 ; 25 ms]) : les
  // transitions entre créneaux sont adoucies par le filtre I/Q.
  _lireBitsVis(f){
    const fs = this.sampleRate;
    const tau = this._n - this._visDebut - Math.round(0.030 * fs);
    const creneau = Math.floor(tau / (0.030 * fs));
    if(creneau >= 0 && creneau < 9){
      const dansCreneau = tau - creneau * 0.030 * fs;
      if(dansCreneau >= 0.005 * fs && dansCreneau <= 0.025 * fs){
        this._visSommes[creneau] += f;
        this._visComptes[creneau]++;
      }
      return;
    }

    // Les 9 créneaux sont passés : décision.
    const freqs = [];
    for(let k = 0; k < 9; k++){
      freqs.push(this._visComptes[k] ? this._visSommes[k] / this._visComptes[k] : 0);
    }
    let code = 0, uns = 0;
    for(let k = 0; k < 7; k++){
      if(freqs[k] < 1200){ code |= (1 << k); uns++; }
    }
    const bitParite = freqs[7] < 1200 ? 1 : 0;
    const stopOk = Math.abs(freqs[8] - SSTV_SYNC) <= 100;
    const pariteOk = ((uns + bitParite) % 2) === 0;
    const mode = SSTV_MODES[code];
    this._etat = 'leader';
    if(!stopOk || !pariteOk){
      this.onEtat('En-tête VIS invalide (parité ou stop) — on attend le suivant');
      return;
    }
    this._dernierVis = code;
    if(!mode){
      this.onEtat('Mode SSTV non géré (VIS ' + code + ')');
      return;
    }
    this._demarrerImage(mode);
  }

  _demarrerImage(mode){
    const fs = this.sampleRate;
    this._mode = mode;
    // Fin du bit de stop = 300 ms après le front du start. `decalageDepart`
    // absorbe l'impulsion de synchro initiale des Scottie (9 ms, une fois).
    this._t0 = this._visDebut + (0.300 + mode.decalageDepart) * fs;
    const l = mode.largeur, h = mode.hauteur;
    const demi = Math.ceil(h / 2);
    this._plans = (mode.famille === 'rgb')
      ? {r: new Float32Array(l * h), g: new Float32Array(l * h), b: new Float32Array(l * h)}
      : (mode.famille === 'mono')
      ? {y: new Float32Array(l * h)}
      : {y: new Float32Array(l * h),
         cr: new Float32Array(l * (mode.famille === 'robot72' ? h : demi)),
         cb: new Float32Array(l * (mode.famille === 'robot72' ? h : demi))};
    this.rgba = new Uint8ClampedArray(l * h * 4);
    this._balayage = 0;
    this._cellCle = -1; this._cellSomme = 0; this._cellCompte = 0;
    this._basDebut = -1;
    // A3 : fenetre de correlation dimensionnee sur la duree de sync du mode
    // (nCorr echantillons), une fois le mode connu. Anneaux + accumulateurs
    // remis a zero a chaque nouvelle image.
    if(this._syncCorrelation){
      const nCorr = Math.max(3, Math.round(mode.syncDuree * fs));
      this._corrN = nCorr;
      this._corrRingC = new Float32Array(nCorr);
      this._corrRingS = new Float32Array(nCorr);
      this._corrCos = 0; this._corrSin = 0; this._corrIdx = 0;
      this._corrW = 2 * Math.PI * SSTV_SYNC / fs;
      this._corrPh = 0; this._corrPic = 0; this._corrPicN = -1;
      this._corrBal = -1; this._corrDernierBal = -1;
    }
    this.lignesEmises = 0;
    this._complete = false;
    this._etat = 'image';
    this.onDebutImage(mode);
    this.onEtat(mode.nom + ' — réception…');
  }

  // Recalage de synchro : chaque passage sous 1350 Hz d'une durée plausible
  // (0,5 à 2,5 × la durée de synchro du mode) est comparé à l'impulsion
  // attendue la plus proche ; la moitié de l'écart est appliquée à t0,
  // bornée à ±1 ms par impulsion. Corrige la dérive d'horloge entre cartes
  // son (le « slant ») sans jamais laisser un parasite déplacer l'image.
  _recalerSync(){
    const fs = this.sampleRate, m = this._mode;
    const duree = (this._n - this._basDebut) / fs;
    if(duree < m.syncDuree * 0.5 || duree > m.syncDuree * 2.5) return;
    const centre = (this._basDebut + this._n) / 2;
    const centreRel = (centre - this._t0) / fs;
    const attenduDansBal = m.syncDebut + m.syncDuree / 2;
    const b = Math.round((centreRel - attenduDansBal) / m.dureeBalayage);
    if(b < 0 || b >= m.balayages) return;
    const err = centre - (this._t0 + (b * m.dureeBalayage + attenduDansBal) * fs);
    if(Math.abs(err) > 0.0025 * fs) return;
    const borne = 0.001 * fs;
    this._t0 += Math.max(-borne, Math.min(borne, err * 0.5));
  }

  // A3 : énergie glissante à 1200 Hz sur une fenêtre = durée de sync du mode.
  // On corrèle le signal BRUT x contre e^{-jωn} (Goertzel/DFT-bin glissant :
  // |Σ x·e^{-jωn}|² sur la fenêtre) plutôt que de seuiller la fréquence
  // démodulée f — un intégrateur moyenne le bruit, l'impulsion de synchro
  // (seule composante 1200 Hz du balayage, le noir étant à 1500) ressort là où
  // le seuil instantané la manque.
  //
  // L'énergie de la fenêtre finissant à l'échantillon n est maximale quand la
  // fenêtre est CENTRÉE sur l'impulsion : ce centre vaut `picN = n - nCorr/2`.
  // On cherche le MAX de cette énergie UNIQUEMENT dans la fenêtre où la synchro
  // du balayage courant est ATTENDUE (± la même borne de ±2,5 ms que
  // _recalerSyncCorr), en s'appuyant sur la table de timing du mode. Cela borne
  // la recherche à un seul pic par balayage (pas de double-détection sur la
  // traîne de l'impulsion, pas de faux pic pris dans le balayage lui-même) et
  // le recalage n'est appliqué qu'à la sortie de cette fenêtre.
  _suivreCorr(x){
    const c = Math.cos(this._corrPh), s = Math.sin(this._corrPh);
    this._corrPh += this._corrW;
    if(this._corrPh > 2 * Math.PI) this._corrPh -= 2 * Math.PI;
    const kc = x * c, ks = x * s;
    const i = this._corrIdx;
    this._corrCos += kc - this._corrRingC[i];      // ajoute l'entrant, retire le sortant (fenêtre glissante)
    this._corrSin += ks - this._corrRingS[i];
    this._corrRingC[i] = kc; this._corrRingS[i] = ks;
    this._corrIdx = (i + 1) % this._corrN;
    const ener = this._corrCos * this._corrCos + this._corrSin * this._corrSin;

    const fs = this.sampleRate, m = this._mode;
    const picN = this._n - (this._corrN >> 1);      // centre de la fenêtre courante
    const relP = (picN - this._t0) / fs;
    const attenduDansBal = m.syncDebut + m.syncDuree / 2;
    const b = Math.round((relP - attenduDansBal) / m.dureeBalayage);
    const delta = relP - (b * m.dureeBalayage + attenduDansBal);   // écart au centre de sync attendu
    // Garde MONOTONE `b > _corrDernierBal` : chaque balayage n'est recalé
    // qu'UNE fois. Sans elle, le +½écart appliqué à t0 décale le bord de
    // fenêtre et réinclut le même picN, ce qui refait feu tous les ~10
    // échantillons et emballe t0 (positive feedback au bord de fenêtre).
    if(b >= 0 && b < m.balayages && b > this._corrDernierBal && Math.abs(delta) <= 0.0025){
      if(b !== this._corrBal){ this._corrBal = b; this._corrPic = 0; this._corrPicN = -1; }
      if(ener > this._corrPic){ this._corrPic = ener; this._corrPicN = picN; }
    } else {
      this._flushCorr();                // sortie de fenêtre : recale sur le max collecté
    }
  }

  // Applique le pic d'énergie collecté sur la fenêtre de sync du balayage
  // courant (s'il y en a un), marque ce balayage comme traité (garde monotone)
  // puis réarme le suivi pour le balayage suivant.
  _flushCorr(){
    if(this._corrBal >= 0 && this._corrPicN >= 0 && this._corrPic > 0){
      this._recalerSyncCorr(this._corrPicN);
      this._corrDernierBal = this._corrBal;
    }
    this._corrBal = -1; this._corrPic = 0; this._corrPicN = -1;
  }

  // Recalage par corrélation (A3) : même logique de bornage que _recalerSync
  // (associer le pic au balayage le plus proche, appliquer la moitié de l'écart,
  // borner à ±1 ms) mais `nPic` (échantillon du max d'énergie 1200 Hz) sert de
  // centre au lieu de (basDebut+n)/2, et la fenêtre de durée [0,5× ; 2,5×] est
  // supprimée — la sélectivité fréquentielle de la corrélation la remplace.
  _recalerSyncCorr(nPic){
    const fs = this.sampleRate, m = this._mode;
    const centreRel = (nPic - this._t0) / fs;
    const attenduDansBal = m.syncDebut + m.syncDuree / 2;
    const b = Math.round((centreRel - attenduDansBal) / m.dureeBalayage);
    if(b < 0 || b >= m.balayages) return;
    const err = nPic - (this._t0 + (b * m.dureeBalayage + attenduDansBal) * fs);
    if(Math.abs(err) > 0.0025 * fs) return;
    const borne = 0.001 * fs;
    this._t0 += Math.max(-borne, Math.min(borne, err * 0.5));
  }

  _decoderImage(f, raw){
    const fs = this.sampleRate, m = this._mode;

    if(this._syncCorrelation){
      // A3 : recalage piloté par le pic de corrélation d'énergie 1200 Hz.
      this._suivreCorr(raw || 0);
    } else {
      // Historique : suivi des impulsions 1200 Hz par seuil instantané. Le noir
      // est à 1500 Hz : seuls la synchro (et du bruit franc) descendent sous 1350.
      if(f < 1350){
        if(this._basDebut < 0) this._basDebut = this._n;
      } else if(this._basDebut >= 0){
        this._recalerSync();
        this._basDebut = -1;
      }
    }

    const rel = (this._n - this._t0) / fs;
    if(rel < 0) return;                  // synchro initiale Scottie
    const bal = Math.floor(rel / m.dureeBalayage);
    if(bal >= m.balayages){ this._finirImage(); return; }
    if(bal > this._balayage){
      this._finaliserCellule();
      while(this._balayage < bal){ this._emettreBalayage(this._balayage); this._balayage++; }
    }

    const tau = rel - bal * m.dureeBalayage;
    const canaux = m.famille === 'robot36'
      ? (bal % 2 === 0 ? m.canauxPair : m.canauxImpair) : m.canaux;
    let cle = -1, plan = null, idx = 0;
    for(let c = 0; c < canaux.length; c++){
      const ch = canaux[c];
      if(tau >= ch.debut && tau < ch.debut + ch.duree){
        let px = Math.floor((tau - ch.debut) / ch.duree * m.largeur);
        if(px >= m.largeur) px = m.largeur - 1;
        let rang = bal;
        if(ch.rangee === 'demi') rang = bal >> 1;
        else if(ch.rangee === 'double0') rang = 2 * bal;
        else if(ch.rangee === 'double1') rang = 2 * bal + 1;
        cle = ((bal * 8 + c) * 4096) + px;
        plan = this._plans[ch.plan];
        idx = rang * m.largeur + px;
        break;
      }
    }
    if(cle !== this._cellCle){
      this._finaliserCellule();
      this._cellCle = cle; this._cellPlan = plan; this._cellIdx = idx;
      this._cellSomme = 0; this._cellCompte = 0;
      this._cellSommePoids = 0;
      if(this._estimPixel === 'mediane') this._cellFreqs.length = 0;
    }
    if(cle !== -1){
      this._cellCompte++;
      if(this._estimPixel === 'ponderee'){
        const w = this._lastAmpl;       // deprioritise les echantillons a I/Q effondre
        this._cellSomme += f * w; this._cellSommePoids += w;
      } else if(this._estimPixel === 'mediane'){
        this._cellFreqs.push(f);
      } else {
        this._cellSomme += f;           // 'moyenne' : comportement historique
      }
    }
  }

  _finaliserCellule(){
    if(this._cellCle === -1 || !this._cellCompte || !this._cellPlan) return;
    let fMoy;
    if(this._estimPixel === 'ponderee'){
      // Repli sur la moyenne simple si tous les poids sont ~nuls (silence
      // total) : _cellSomme accumule alors f*w (pas f), donc ce repli n'est
      // PAS la moyenne des f — acceptable car il ne joue qu'a amplitude
      // quasi nulle (silence), jamais en signal etabli.
      fMoy = this._cellSommePoids > 1e-9
           ? this._cellSomme / this._cellSommePoids
           : this._cellSomme / this._cellCompte;
    } else if(this._estimPixel === 'mediane'){
      const a = this._cellFreqs.slice().sort((x, y) => x - y);
      const n = a.length;
      fMoy = n % 2 ? a[(n - 1) >> 1] : (a[n/2 - 1] + a[n/2]) / 2;
    } else {
      fMoy = this._cellSomme / this._cellCompte;
    }
    this._cellPlan[this._cellIdx] = sstvClamp255((fMoy - SSTV_NOIR) / SSTV_PENTE);
    this._cellCle = -1; this._cellCompte = 0;
  }

  // Un balayage est terminé : assemble et émet la ou les lignes RGBA
  // correspondantes. Robot 36 émet la PAIRE à la fin de la ligne impaire —
  // c'est elle qui apporte le B-Y manquant de la ligne paire.
  _emettreBalayage(bal){
    const m = this._mode, l = m.largeur, p = this._plans;
    const ligne = (y, pixel) => {
      const rangee = new Uint8ClampedArray(l * 4);
      for(let x = 0; x < l; x++){
        const [r, g, b] = pixel(x);
        const o = x * 4;
        rangee[o] = r; rangee[o + 1] = g; rangee[o + 2] = b; rangee[o + 3] = 255;
      }
      this.rgba.set(rangee, y * l * 4);
      this.lignesEmises++;
      this.onLigne(y, rangee, m);
    };
    if(m.famille === 'rgb'){
      ligne(bal, x => [p.r[bal * l + x], p.g[bal * l + x], p.b[bal * l + x]]);
    } else if(m.famille === 'robot72'){
      ligne(bal, x => sstvYccVersRgb(p.y[bal * l + x], p.cr[bal * l + x], p.cb[bal * l + x]));
    } else if(m.famille === 'robot36'){
      if(bal % 2 === 1){
        const k = bal >> 1;
        for(const y of [bal - 1, bal]){
          ligne(y, x => sstvYccVersRgb(p.y[y * l + x], p.cr[k * l + x], p.cb[k * l + x]));
        }
      }
    } else if(m.famille === 'mono'){
      ligne(bal, x => { const v = p.y[bal * l + x]; return [v, v, v]; });
    } else {                             // pd : deux lignes par balayage
      for(const y of [2 * bal, 2 * bal + 1]){
        ligne(y, x => sstvYccVersRgb(p.y[y * l + x], p.cr[bal * l + x], p.cb[bal * l + x]));
      }
    }
    if(this.lignesEmises % 8 === 0 || this.lignesEmises >= m.hauteur){
      this.onEtat(m.nom + ' — ligne ' + this.lignesEmises + '/' + m.hauteur);
    }
  }

  _finirImage(){
    this._finaliserCellule();
    while(this._balayage < this._mode.balayages){
      this._emettreBalayage(this._balayage); this._balayage++;
    }
    this._complete = true;
    this._etat = 'leader';
    this._leaderEch = 0;
    if(this._acqVisRobuste) this._eLeaderPeak = 0;   // leader suivant : pic frais
    this.onEtat(this._mode.nom + ' — image complète');
    this.onFinImage(this._mode);
  }

  // État courant sous forme sérialisable — utilisé par les tests et l'UI.
  resume(){
    return {
      mode: this._mode ? this._mode.cle : null,
      nomMode: this._mode ? this._mode.nom : null,
      vis: this._dernierVis,
      largeur: this._mode ? this._mode.largeur : 0,
      hauteur: this._mode ? this._mode.hauteur : 0,
      lignesEmises: this.lignesEmises,
      complete: this._complete,
    };
  }
}

// Décodage d'un signal complet en une passe — utilisé par les tests.
function sstvDecodeSamples(samples, opts){
  const d = new SstvDecodeur(opts || {});
  d.pousser(samples);
  return d;
}

// ─── Encodeur ────────────────────────────────────────────────────────────────
// Génère un signal SSTV complet : leader + VIS + image. Sert aux tests
// aller-retour et à l'auto-test du panneau (« ma chaîne audio marche-t-elle ? »)
// sans attendre une station sur l'air. `pixels` : RGB entrelacé (3 octets par
// pixel), aux dimensions EXACTES du mode. `lignes` limite le nombre de
// balayages émis (signaux tronqués pour les tests). `visCode`/`pariteFausse`
// fabriquent des en-têtes invalides pour tester le rejet.
function sstvEncodeSamples({mode = 'M1', pixels, sampleRate = 44100,
                            amplitude = 0.5, lignes = null,
                            visCode = null, pariteFausse = false} = {}){
  const m = SSTV_MODES_PAR_NOM[mode];
  if(!m) throw new Error('Mode SSTV inconnu : ' + mode);
  const l = m.largeur, h = m.hauteur;
  if(!pixels || pixels.length < l * h * 3) throw new Error('pixels : attendu ' + (l * h * 3) + ' octets RGB');
  const nBal = lignes === null ? m.balayages : Math.min(lignes, m.balayages);

  // 100 ms de 1900 Hz en queue : le décodeur ne clôt une image qu'en voyant
  // un échantillon APRÈS sa dernière ligne — sur l'air le flux audio continue
  // toujours, mais un signal de test tronqué pile à la fin resterait ouvert.
  const queue = 0.100;
  const dureeTotale = 0.300 + 0.010 + 0.300 + 9 * 0.030
                    + m.decalageDepart + nBal * m.dureeBalayage + queue;
  const out = new Float32Array(Math.ceil(dureeTotale * sampleRate) + 16);

  // Oscillateur à PHASE CONTINUE et curseur temporel FLOTTANT : les durées
  // SSTV ne tombent jamais sur un nombre entier d'échantillons (0,572 ms de
  // porch Martin = 25,2 échantillons à 44,1 kHz). Arrondir chaque segment
  // accumulerait jusqu'à plusieurs pixels d'erreur en fin de ligne.
  let curseur = 0, tCible = 0, phase = 0;
  const ton = (f, duree) => {
    tCible += duree * sampleRate;
    const w = 2 * Math.PI * f / sampleRate;
    while(curseur < tCible && curseur < out.length){
      out[curseur++] = amplitude * Math.sin(phase);
      phase += w;
      if(phase > 2 * Math.PI) phase -= 2 * Math.PI;
    }
  };
  const scan = (duree, valeur) => {
    const dpx = duree / l;
    for(let x = 0; x < l; x++){
      ton(SSTV_NOIR + sstvClamp255(valeur(x)) * SSTV_PENTE, dpx);
    }
  };

  // En-tête VIS : leader 1900 (300 ms), cassure 1200 (10 ms), leader 1900
  // (300 ms), start 1200 (30 ms), 7 bits poids faible d'abord (1100 = 1,
  // 1300 = 0), parité paire, stop 1200 (30 ms).
  const code = visCode === null ? m.vis : visCode;
  ton(1900, 0.300);
  ton(1200, 0.010);
  ton(1900, 0.300);
  ton(1200, 0.030);
  let uns = 0;
  for(let k = 0; k < 7; k++){
    const bit = (code >> k) & 1;
    uns += bit;
    ton(bit ? 1100 : 1300, 0.030);
  }
  let parite = uns % 2;
  if(pariteFausse) parite = 1 - parite;
  ton(parite ? 1100 : 1300, 0.030);
  ton(1200, 0.030);

  // Plans YCrCb pour Robot/PD, calculés une fois. `mono` (Robot BW) ne
  // transmet que Y — ne pas allouer cr/cb pour cette famille (elle n'appelle
  // jamais plan('cr'/'cb', ...) plus bas, cf. la branche mono du dispatch).
  let plans = null;
  if(m.famille !== 'rgb'){
    const mono = m.famille === 'mono';
    plans = mono ? {y: new Float32Array(l * h)}
                 : {y: new Float32Array(l * h), cr: new Float32Array(l * h), cb: new Float32Array(l * h)};
    for(let i = 0; i < l * h; i++){
      const [y, cr, cb] = sstvRgbVersYcc(pixels[i * 3], pixels[i * 3 + 1], pixels[i * 3 + 2]);
      plans.y[i] = y;
      if(!mono){ plans.cr[i] = cr; plans.cb[i] = cb; }
    }
  }
  const rgb = (rangee, comp) => x => pixels[(rangee * l + x) * 3 + comp];
  const plan = (nom, rangee) => x => plans[nom][rangee * l + x];
  const planMoy = (nom, r1, r2) => x => (plans[nom][r1 * l + x] + plans[nom][r2 * l + x]) / 2;

  if(m.famille === 'rgb' && m.decalageDepart) ton(SSTV_SYNC, m.decalageDepart);

  for(let bal = 0; bal < nBal; bal++){
    if(m.nom.startsWith('Martin')){
      ton(SSTV_SYNC, m.sync); ton(1500, m.porch);
      scan(m.scan, rgb(bal, 1)); ton(1500, m.sep);
      scan(m.scan, rgb(bal, 2)); ton(1500, m.sep);
      scan(m.scan, rgb(bal, 0)); ton(1500, m.sep);
    } else if(m.nom.startsWith('Scottie')){
      ton(1500, m.sep); scan(m.scan, rgb(bal, 1));
      ton(1500, m.sep); scan(m.scan, rgb(bal, 2));
      ton(SSTV_SYNC, m.sync); ton(1500, m.porch);
      scan(m.scan, rgb(bal, 0));
    } else if(m.nom.startsWith('Wraase')){
      // SC2-120/180 (Lot B3) : synchro+porch puis R,G,B dos-à-dos, PAS de
      // séparateur entre canaux (m.sep=0, cf. sstvModeSc2()) — ordre R,G,B
      // (comp 0/1/2 de `pixels`, RGB entrelacé), pas G,B,R comme Martin.
      ton(SSTV_SYNC, m.sync); ton(1500, m.porch);
      scan(m.scan, rgb(bal, 0));           // rouge
      scan(m.scan, rgb(bal, 1));           // vert
      scan(m.scan, rgb(bal, 2));           // bleu
    } else if(m.famille === 'robot36'){
      ton(SSTV_SYNC, m.sync); ton(1500, m.porch);
      scan(m.scanY, plan('y', bal));
      if(bal % 2 === 0){
        ton(1500, m.sep); ton(1900, m.porch2);
        scan(m.scanC, plan('cr', bal));            // R-Y de la ligne paire
      } else {
        ton(2300, m.sep); ton(1900, m.porch2);
        scan(m.scanC, plan('cb', bal));            // B-Y de la ligne impaire
      }
    } else if(m.famille === 'robot72'){
      ton(SSTV_SYNC, m.sync); ton(1500, m.porch);
      scan(m.scanY, plan('y', bal));
      ton(1500, m.sep); ton(1900, m.porch2);
      scan(m.scanC, plan('cr', bal));
      ton(2300, m.sep); ton(1900, m.porch2);
      scan(m.scanC, plan('cb', bal));
    } else if(m.famille === 'mono'){
      // Gris = luminance ITU BT.601 (sstvRgbVersYcc(...)[0], déjà calculée
      // dans plans.y ci-dessus pour toute famille != 'rgb') — même
      // convention que le canal Y des familles robot36/robot72/pd.
      ton(SSTV_SYNC, m.sync); ton(1500, m.porch);
      scan(m.scan, plan('y', bal));
    } else if(m.famille === 'pd'){
      ton(SSTV_SYNC, m.sync); ton(1500, m.porch);
      scan(m.scan, plan('y', 2 * bal));
      scan(m.scan, planMoy('cr', 2 * bal, 2 * bal + 1));
      scan(m.scan, planMoy('cb', 2 * bal, 2 * bal + 1));
      scan(m.scan, plan('y', 2 * bal + 1));
    } else {
      // Garde : toute famille future non reconnue par ce dispatch doit
      // ÉCHOUER BRUYAMMENT plutôt que de retomber en silence sur le chemin
      // PD (c'était l'ancien `else` nu) — revue finale du 2026-09-03.
      throw new Error('sstvEncodeSamples : famille non gérée — ' + m.famille);
    }
  }
  ton(1900, queue);
  return out.subarray(0, Math.min(curseur, out.length));
}

// ─── Chaîne audio temps réel (même motif que les décodeurs CW et RTTY) ──────
class SstvAudioDecoder {
  constructor(opts = {}){
    this.opts = opts;
    this.decodeur = null;
    this.ctx = null; this.stream = null; this.source = null; this.proc = null;
    // Blocs plus gros qu'en RTTY : une ligne SSTV dure 150 à 1000 ms, une
    // latence de 85 ms est invisible et divise par 4 le coût des rappels.
    this.blockSize = 4096;
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
    this.decodeur = new SstvDecodeur(Object.assign({}, this.opts,
                                                   {sampleRate: this.ctx.sampleRate}));
    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.proc = this.ctx.createScriptProcessor(this.blockSize, 1, 1);
    this.proc.onaudioprocess = e => this.decodeur.pousser(e.inputBuffer.getChannelData(0));
    this.source.connect(this.proc);
    // Le graphe n'avance que si le node est relié à une destination — un gain
    // à 0 garde le pipeline actif sans rien sortir sur les haut-parleurs.
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
}
