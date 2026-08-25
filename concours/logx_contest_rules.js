// Règlement bandes/modes par concours — extrait TEL QUEL de logx_configuration.js
// (chantier « page d'accueil par activité », 22/08/2026) pour être partagé avec
// logx_logbook.js. Avant cette extraction, renderBandButtons() (logx_logbook.js)
// indexait une table locale CONTEST_BANDS ne connaissant que des clés génériques
// (REF_CCD, REF_IARU_VHF...) -- aucune des vraies clés d'édition qu'utilise le
// reste de l'app (REF_CCD_JAN1, REF_MARCONI, REF_DDFM_50, REF_IARU_50...), donc
// le sélecteur de bandes du LOGBOOK retombait sur TOUTES les bandes (HF comprises)
// pour la quasi-totalité des concours V/UHF réels. Ce fichier est désormais
// l'unique source de vérité pour les DEUX pages -- chargé AVANT logx_configuration.js
// et AVANT logx_logbook.js (même convention que logx_statusbar.js/logx_i18n.js).
//
// SERVER_CONTEST_RULES n'est peuplé que côté CONFIG (mergeServerContests(),
// resté dans logx_configuration.js car il enrichit aussi le catalogue CONTESTS
// propre à cette page -- dates, liens de règlement...). Le LOGBOOK ne l'alimente
// pas : _resolveContestFilters() retombe alors directement sur LEGACY_CONTEST_FILTERS,
// qui couvre déjà TOUS les concours V/UHF réels (REF_CCD_*, REF_MARCONI,
// REF_IARU_VHF/50, REF_DDFM_50...) sans round-trip serveur -- suffisant pour
// corriger le bug ci-dessus sans dupliquer la logique de fetch/enrichissement.
const SERVER_CONTEST_RULES = {};

// LEGACY_CONTEST_FILTERS : repli pour les concours ABSENTS de CONTEST_DEFINITIONS
// côté serveur (parties CCD mensuelles, TVA, Marconi, F8TD, 50 MHz REF/IARU,
// UFT...) -- leur règlement n'existe nulle part ailleurs, donc cette table reste
// l'unique source pour CES ids précis (voir _resolveContestFilters ci-dessous).
const LEGACY_CONTEST_FILTERS = {

  // ── Challenge THF annuel cumulatif (144MHz→47GHz, tous modes)
  'REF_CHALLENGE_THF': { modes:['mode_ssb','mode_cw','mode_fm','mode_ft8','mode_ft4'],
                          bands:['band_2m','band_70cm','band_23cm','band_13cm','band_9cm','band_6cm','band_3cm','band_6mm','band_4mm'] },

  // ── CCD parties THF (432/1296/2320 MHz = 70cm+23cm+13cm)
  'REF_CCD_JAN1':  { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_70cm','band_23cm','band_13cm'] },
  'REF_CCD_FEV1':  { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_70cm','band_23cm','band_13cm'] },
  'REF_CCD_MAI':   { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_70cm','band_23cm','band_13cm'] },
  'REF_CCD_OCT':   { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_70cm','band_23cm','band_13cm'] },

  // ── CCD parties 144 MHz (SSB+CW+FM)
  'REF_CCD_JAN2':  { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_2m'] },
  'REF_CCD_FEV2':  { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_2m'] },
  'REF_CCD_MAR':   { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_2m'] },
  'REF_CCD_NOV':   { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_2m'] },
  'REF_CCD_DEC':   { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_2m'] },

  // ── CCD CW uniquement (144 MHz)
  'REF_CCD_AVR_CW':{ modes:['mode_cw'], bands:['band_2m'] },
  'REF_CCD_DEC_CW':{ modes:['mode_cw'], bands:['band_2m'] },

  // ── TVA (ATV/FM relais — 70cm+23cm)
  'REF_NAT_TVA':     { modes:['mode_fm'], bands:['band_70cm','band_23cm'] },
  'REF_IARU_TVA':    { modes:['mode_fm'], bands:['band_70cm','band_23cm'] },
  'REF_CDF_TVA':     { modes:['mode_fm'], bands:['band_70cm','band_23cm'] },
  'REF_NAT_TVA_DEC': { modes:['mode_fm'], bands:['band_70cm','band_23cm'] },

  // ── 50 MHz
  'REF_DDFM_50':   { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_6m'] },
  'REF_IARU_50':   { modes:['mode_ssb','mode_cw'],           bands:['band_6m'] },
  'IARU_50':       { modes:['mode_ssb','mode_cw'],           bands:['band_6m'] },

  // ── F8TD — SHF uniquement (1296MHz→47GHz, SSB+CW)
  'REF_F8TD':      { modes:['mode_ssb','mode_cw'],
                     bands:['band_23cm','band_13cm','band_9cm','band_6cm','band_3cm','band_6mm','band_4mm'] },

  // ── IARU VHF (144MHz uniquement, SSB+CW) — id historique REF_IARU_VHF,
  // distinct de IARU_VHF (celui-ci EST dans CONTEST_DEFINITIONS)
  'REF_IARU_VHF':  { modes:['mode_ssb','mode_cw'], bands:['band_2m'] },

  // ── Marconi (144MHz, CW UNIQUEMENT) — id historique REF_MARCONI, distinct
  // de IARU_MARCONI (CONTEST_DEFINITIONS)
  'REF_MARCONI':   { modes:['mode_cw'], bands:['band_2m'] },

  // ── IARU UHF/SHF (432MHz→47GHz) — id historique REF_IARU_UHF, distinct de
  // IARU_UHF (CONTEST_DEFINITIONS)
  'REF_IARU_UHF':  { modes:['mode_ssb','mode_cw'],
                     bands:['band_70cm','band_23cm','band_13cm','band_9cm','band_6cm','band_3cm','band_6mm','band_4mm'] },

  // ── UFT (HF 80→10m, CW uniquement)
  'F9NL':          { modes:['mode_cw'], bands:['band_80m','band_40m','band_20m','band_15m','band_10m'] },
  'UFT_RENCONTRES':{ modes:['mode_cw'], bands:['band_80m','band_40m','band_20m','band_15m','band_10m'] },
};

// Correspondance valeur bande serveur (MHz brut, ex. '144') → clé toggle.
const BAND_TOGGLE_KEY = {
  '1.8':   'band_160m', '3.5':   'band_80m',  '5':     'band_60m',  '7':     'band_40m',
  '10.1':  'band_30m',  '14':    'band_20m',  '18':    'band_17m',
  '21':    'band_15m',  '24':    'band_12m',  '28':    'band_10m',
  '50':    'band_6m',   '70':    'band_4m',    '144':   'band_2m',
  '432':   'band_70cm', '1296':  'band_23cm',  '2320':  'band_13cm',
  '3400':  'band_9cm',  '5760':  'band_6cm',   '10368': 'band_3cm',
  '24048': 'band_6mm',  '47088': 'band_4mm',
};

// Correspondance mode serveur → clé toggle, y compris le rattachement WWA
// FT2→FT8 (règlement §5, même famille "DIGI", aucune case dédiée).
const MODE_TOGGLE_KEY = {
  'SSB':   'mode_ssb',
  'AM':    'mode_am',
  'CW':    'mode_cw',
  'FM':    'mode_fm',
  'DSTAR': 'mode_dstar',  // libellé ADIF ; la case de configuration dit "D-STAR"
  'FT8':   'mode_ft8',
  'FT4':   'mode_ft4',
  'JS8':   'mode_js8',
  'RTTY':  'mode_rtty',
  'PSK':   'mode_psk',
  'SSTV':  'mode_sstv',   // mode d'activité (dimanches SSTV, ISS) — jamais imposé par un concours ; active aussi le panneau décodeur SSTV du LOGBOOK (updateKeyerPanels)
  'DIGI':  'mode_ft8',    // code générique de règlement, aucune case dédiée
  'FT2':   'mode_ft8',    // WWA (règlement §5) — pas de case dédiée, rattaché à FT8
};

// Résout les clés toggle bandes/modes autorisées pour un concours :
// 1. règlement serveur (SERVER_CONTEST_RULES, source de vérité si peuplé) ;
// 2. à défaut, repli LEGACY_CONTEST_FILTERS (concours absents côté serveur) ;
// 3. sinon null → aucune restriction (comportement sûr par défaut).
// Les deux axes (bandes/modes) sont résolus INDÉPENDAMMENT l'un de l'autre :
// 'all' explicite, ou un règlement dont aucun code ne se traduit via
// BAND_TOGGLE_KEY/MODE_TOGGLE_KEY, lève la restriction sur CET axe seul —
// jamais sur l'autre. Le retour est { bands, modes } où chaque champ vaut
// soit un tableau de clés à restreindre, soit null si l'axe est libre.
function _resolveContestFilters(contestId) {
  const rules = SERVER_CONTEST_RULES[contestId];
  if (rules) {
    const bands = rules.bands || [];
    const modes = rules.modes || [];
    const bandKeys = bands.includes('all') ? [] : [...new Set(bands.map(b => BAND_TOGGLE_KEY[b]).filter(Boolean))];
    const modeKeys = modes.includes('all') ? [] : [...new Set(modes.map(m => MODE_TOGGLE_KEY[m]).filter(Boolean))];
    const restrictBands = bandKeys.length > 0;
    const restrictModes = modeKeys.length > 0;
    if (!restrictBands && !restrictModes) return null; // aucun des deux axes n'a de restriction traduisible
    return { bands: restrictBands ? bandKeys : null, modes: restrictModes ? modeKeys : null };
  }
  return LEGACY_CONTEST_FILTERS[contestId] || null;
}

if (typeof module !== 'undefined') module.exports = {
  SERVER_CONTEST_RULES, LEGACY_CONTEST_FILTERS, BAND_TOGGLE_KEY, MODE_TOGGLE_KEY, _resolveContestFilters,
};
