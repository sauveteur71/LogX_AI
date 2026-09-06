// EV-7 51e increment : DONNEES DU SELECTEUR CONCOURS (CS_DATA) -- extrait de
// logx_logbook.js (docs/LogX_AI_PRD.md). Charge en <script> classique dans
// logx_logbook.html, AVANT logx_logbook.js -- portee globale partagee.
//
// CS_DATA = liste groupee des concours (memes id que logx_configuration.html),
// consommee UNIQUEMENT par logx_contest_picker.js (csFilter/csSelect/csSetValue,
// le combobox cherchable du modal). Le coeur logbook.js ne la lit pas.

// ─── SÉLECTEUR CONCOURS (liste groupée pour csFilter/csSelect/csSetValue) ─────
// Mêmes id que logx_configuration.html, groupés pour le combobox cherchable du modal.
const CS_DATA = [
  { g:'REF', items:[
    {v:'REF_CHALLENGE_THF', l:'Challenge THF'},
    {v:'REF_CCD_JAN1',      l:'Courte Durée Cumulatif — 1re partie'},
    {v:'REF_CCD_JAN2',      l:'Courte Durée Cumulatif — 2e partie'},
    {v:'REF_CDF_HF_CW',     l:'Championnat de France HF Télégraphie'},
    {v:'REF_CCD_FEV1',      l:'Courte Durée Cumulatif — 3e partie'},
    {v:'REF_CCD_FEV2',      l:'Courte Durée Cumulatif — 4e partie'},
    {v:'REF_CDF_HF_SSB',    l:'Championnat de France HF Téléphonie'},
    {v:'REF_NAT_THF',       l:'National THF — Trophée F3SK'},
    {v:'REF_CCD_MAR',       l:'Concours de Courte Durée (Mars)'},
    {v:'REF_NAT_TVA',       l:'National TVA'},
    {v:'REF_CCD_AVR_CW',    l:'Concours de Courte Durée CW (Avril)'},
    {v:'REF_PRINTEMPS',     l:'Concours du Printemps'},
    {v:'REF_CCD_MAI',       l:'Concours de Courte Durée (Mai)'},
    {v:'REF_CDF_THF',       l:'Championnat de France THF'},
    {v:'REF_IARU_TVA',      l:'IARU R1 TVA'},
    {v:'REF_DDFM_50',       l:'DDFM 50MHz'},
    {v:'REF_IARU_50',       l:'IARU R1 50MHz — Mémorial F8SH'},
    {v:'REF_RPH',           l:'Rallye des Points Hauts'},
    {v:'REF_QRP',           l:"Bol d'or des QRP — Trophée F8BO"},
    {v:'REF_ETE',           l:"Concours d'été"},
    {v:'REF_F8TD',          l:'Trophée F8TD'},
    {v:'REF_IARU_VHF',      l:'IARU R1 VHF'},
    {v:'REF_CDF_TVA',       l:'Championnat de France TVA'},
    {v:'REF_IARU_UHF',      l:'IARU UHF/SHF'},
    {v:'REF_CCD_OCT',       l:'Concours de Courte Durée (Octobre)'},
    {v:'REF_MARCONI',       l:'IARU R1 VHF CW — Mémorial Marconi'},
    {v:'REF_160M',          l:'REF 160m — Trophée F8EX'},
    {v:'REF_CCD_NOV',       l:'Concours de Courte Durée (Novembre)'},
    {v:'REF_CCD_DEC',       l:'Concours de Courte Durée (Décembre)'},
    {v:'REF_CCD_DEC_CW',    l:'Concours de Courte Durée CW (Décembre)'},
    {v:'REF_NAT_TVA_DEC',   l:'National TVA (Décembre)'},
  ]},
  { g:'AUTRE FR', items:[
    {v:'F9NL',            l:'Mémorial F9NL'},
    {v:'UFT_RENCONTRES',  l:'Rencontres UFT'},
  ]},
  { g:'INTERNATIONAL', items:[
    {v:'CQ_WW_SSB',    l:'CQ World Wide DX — SSB'},
    {v:'CQ_WW_CW',     l:'CQ World Wide DX — CW'},
    {v:'CQ_WPX_SSB',   l:'CQ WPX — SSB'},
    {v:'CQ_WPX_CW',    l:'CQ WPX — CW'},
    {v:'ARRL_DX_SSB',  l:'ARRL DX — SSB'},
    {v:'ARRL_DX_CW',   l:'ARRL DX — CW'},
    {v:'ARRL_FD',      l:'ARRL Field Day'},
    {v:'SOTA',         l:'Summits on the Air'},
    {v:'POTA',         l:'Parks on the Air'},
  ]},
  { g:'AUTRE', items:[
    {v:'CUSTOM', l:'Concours personnalisé'},
  ]},
];
