/* RadioContest AI — logique du logbook multi-opérateur.
   Externalisé de radiocontest_logbook.html (le HTML ne contient plus
   que la structure ; ce fichier est servi par le serveur local). */
// ─── DÉTECTION PROTOCOLE FILE:// ────────────────────────────────────────────
(function(){
  if(location.protocol === 'file:'){
    document.body.innerHTML = `
      <div style="position:fixed;inset:0;background:#07080F;display:flex;align-items:center;justify-content:center;z-index:9999;font-family:'Courier New',monospace">
        <div style="text-align:center;max-width:600px;padding:40px">
          <div style="font-size:60px;margin-bottom:20px">🚫</div>
          <div style="color:#FF2D55;font-size:22px;font-weight:700;margin-bottom:16px;letter-spacing:2px">OUVERT EN FILE:// — IMPOSSIBLE</div>
          <div style="color:#E9ECF5;font-size:16px;line-height:2;margin-bottom:30px">
            Le logiciel nécessite le serveur Python.<br>
            Tu ne peux pas ouvrir les fichiers directement depuis l'explorateur.
          </div>
          <div style="background:#13152A;border:2px solid #FF6B00;border-radius:10px;padding:20px;margin-bottom:24px">
            <div style="color:#A9B0C8;font-size:14px;margin-bottom:10px">ÉTAPE 1 — Lance le serveur dans un terminal :</div>
            <div style="color:#00FF88;font-size:17px;font-weight:700;letter-spacing:1px">cd "C:\\Users\\parri\\SynologyDrive\\RADIOAMATEUR\\Activites\\Rallye des point haut\\concours"</div>
            <div style="color:#00FF88;font-size:17px;font-weight:700;margin-top:8px">python radiocontest_serveur.py</div>
          </div>
          <div style="background:#13152A;border:2px solid #00D4FF;border-radius:10px;padding:20px;margin-bottom:30px">
            <div style="color:#A9B0C8;font-size:14px;margin-bottom:10px">ÉTAPE 2 — Accède via cette adresse :</div>
            <a href="http://localhost:8080/radiocontest_logbook.html" style="color:#00D4FF;font-size:20px;font-weight:700;text-decoration:none;letter-spacing:1px">http://localhost:8080/radiocontest_logbook.html</a>
          </div>
          <a href="http://localhost:8080/radiocontest_logbook.html"
             style="display:inline-block;background:linear-gradient(135deg,#00FF88,#00D4FF);color:#07080F;font-size:18px;font-weight:900;padding:16px 40px;border-radius:10px;text-decoration:none;letter-spacing:3px">
            ▶ OUVRIR VIA LE SERVEUR
          </a>
        </div>
      </div>`;
    return;
  }
})();

// ─── STATE ───────────────────────────────────────────────────────────────────
let myCall     = window._initCall    || '';
let myLocator  = window._initLocator || '';
let myOp = 'OP1';

// Lire le concours depuis la config sauvegardée (radiocontest_configuration.html) ou défaut VHF
(function initFromConfig(){
  try{
    const cfg = JSON.parse(localStorage.getItem('radiocontest_config')||'{}');
    if(cfg.contest) window._initContest = cfg.contest;
    if(cfg.locator) window._initLocator = cfg.locator;
    if(cfg.callsign_contest||cfg.callsign) window._initCall = cfg.callsign_contest||cfg.callsign;
  }catch(e){}
})();

let currentContest = window._initContest || 'REF_RPH';
let currentBand    = (['ARRL_FD','ARRL_DX_SSB','ARRL_DX_CW','CQ_WW_SSB','CQ_WW_CW',
                       'CQ_WPX_SSB','CQ_WPX_CW','REF_CDF_HF_SSB','REF_CDF_HF_CW','IARU_HF']
                      .includes(currentContest)) ? '14' : '144';
let currentMode = 'SSB';

// ─── FORMATS D'ÉCHANGE PAR CONCOURS ─────────────────────────────────────────
// auto_serial : true  = N° auto incrémenté par bande (concours VHF standard)
// auto_serial : false = champ libre à saisir (zone, dept, classe...)
// clear_sent  : false = le champ envoyé ne se vide pas entre chaque QSO (valeur fixe)
// pad_rcvd    : true  = le N° reçu est formaté en 001, 002...
const CONTEST_EXCHANGE = {
  // ── ARRL Field Day : classe + section (DX station envoie "1D DX")
  'ARRL_FD':       { label_s:'CLASSE ENV', label_r:'CLASSE RCU',
                     def_s:'1D DX', ph_r:'ex: 2A TN',
                     ml_s:7, ml_r:8, auto_serial:false, clear_s:false, pad_r:false },
  // ── CQ World Wide : RST + zone CQ (France = zone 14)
  'CQ_WW_SSB':     { label_s:'ZONE ENV', label_r:'ZONE RCU',
                     def_s:'14', ph_r:'zone 1-40',
                     ml_s:3, ml_r:3, auto_serial:false, clear_s:false, pad_r:false },
  'CQ_WW_CW':      { label_s:'ZONE ENV', label_r:'ZONE RCU',
                     def_s:'14', ph_r:'zone 1-40',
                     ml_s:3, ml_r:3, auto_serial:false, clear_s:false, pad_r:false },
  // ── CQ WPX / ARRL DX : N° de série standard
  'CQ_WPX_SSB':    { label_s:'N° ENVOYÉ', label_r:'N° REÇU',    def_s:'', ph_r:'001', ml_s:4, ml_r:4, auto_serial:true,  clear_s:true,  pad_r:true  },
  'CQ_WPX_CW':     { label_s:'N° ENVOYÉ', label_r:'N° REÇU',    def_s:'', ph_r:'001', ml_s:4, ml_r:4, auto_serial:true,  clear_s:true,  pad_r:true  },
  // ── ARRL DX : puissance envoyée (DX side) / état reçu
  'ARRL_DX_SSB':   { label_s:'PUISS. (W)', label_r:'ÉTAT/PROV',
                     def_s:'100', ph_r:'ex: TN',
                     ml_s:5, ml_r:5, auto_serial:false, clear_s:false, pad_r:false },
  'ARRL_DX_CW':    { label_s:'PUISS. (W)', label_r:'ÉTAT/PROV',
                     def_s:'100', ph_r:'ex: TN',
                     ml_s:5, ml_r:5, auto_serial:false, clear_s:false, pad_r:false },
  // ── REF CDF HF + REF 160m + UFT : RST + département
  'REF_CDF_HF_SSB':{ label_s:'DEPT ENV', label_r:'DEPT RCU',    def_s:'', ph_r:'ex: 43', ml_s:3, ml_r:3, auto_serial:false, clear_s:false, pad_r:false },
  'REF_CDF_HF_CW': { label_s:'DEPT ENV', label_r:'DEPT RCU',    def_s:'', ph_r:'ex: 43', ml_s:3, ml_r:3, auto_serial:false, clear_s:false, pad_r:false },
  'REF_160M':      { label_s:'DEPT ENV', label_r:'DEPT RCU',    def_s:'', ph_r:'ex: 43', ml_s:3, ml_r:3, auto_serial:false, clear_s:false, pad_r:false },
  'F9NL':          { label_s:'DEPT ENV', label_r:'DEPT RCU',    def_s:'', ph_r:'ex: 43', ml_s:3, ml_r:3, auto_serial:false, clear_s:false, pad_r:false },
  'UFT_RENCONTRES':{ label_s:'DEPT ENV', label_r:'DEPT RCU',    def_s:'', ph_r:'ex: 43', ml_s:3, ml_r:3, auto_serial:false, clear_s:false, pad_r:false },
};
// Format par défaut : N° de série auto (concours VHF/UHF standard)
const DEFAULT_EXCHANGE = {
  label_s:'N° ENVOYÉ', label_r:'N° REÇU', def_s:'', ph_r:'',
  ml_s:4, ml_r:4, auto_serial:true, clear_s:true, pad_r:true
};
let currentExchange = {...DEFAULT_EXCHANGE};

function applyExchangeFormat(contestId){
  currentExchange = CONTEST_EXCHANGE[contestId] || DEFAULT_EXCHANGE;
  const ex = currentExchange;
  // Labels
  const grpS = document.getElementById('inputNumSent')?.closest('.field-group');
  const grpR = document.getElementById('inputNumRcvd')?.closest('.field-group');
  if(grpS) grpS.querySelector('.field-label').textContent = ex.label_s;
  if(grpR) grpR.querySelector('.field-label').textContent = ex.label_r;
  // Attributs
  const fS = document.getElementById('inputNumSent');
  const fR = document.getElementById('inputNumRcvd');
  if(fS){ fS.maxLength = ex.ml_s; fS.placeholder = ex.def_s || '—'; }
  if(fR){ fR.maxLength = ex.ml_r; fR.placeholder = ex.ph_r; }
  // Valeur envoyée
  if(ex.auto_serial){
    updateSerialDisplay();
  } else {
    if(fS && ex.def_s && !fS.value) fS.value = ex.def_s;
  }
}

// ─── MODE EXPÉDITION : saisie simplifiée (indicatif + RST env/reçu seulement) ──
// En pile-up d'expédition l'échange est juste le report : on masque les champs
// N° de série et locator pour ne garder que l'essentiel et enchaîner très vite.
let expeditionMode = false;
function applyExpeditionMode(on){
  expeditionMode = (String(on) === '1' || on === true);
  const numRow = document.getElementById('numFieldRow');
  const locGrp = document.getElementById('locatorGroup');
  if(numRow) numRow.style.display = expeditionMode ? 'none' : '';
  if(locGrp) locGrp.style.display = expeditionMode ? 'none' : '';
  document.body.classList.toggle('expedition-on', expeditionMode);
}

// ─── ACTIVATION POTA/SOTA/IOTA/WWFF ──────────────────────────────────────────
const ACT_MIN = {POTA:10, SOTA:4, IOTA:1, WWFF:44};
let activationProgram = '';
let myActivationRef = '';
let activationTimer = null;

function applyActivationMode(program, ref){
  activationProgram = (program||'').toUpperCase();
  myActivationRef = (ref||'').trim().toUpperCase();
  const on = !!(activationProgram && myActivationRef);
  const bar = document.getElementById('activationBar');
  const trg = document.getElementById('theirRefGroup');
  if(bar) bar.style.display = on ? '' : 'none';
  if(trg) trg.style.display = on ? '' : 'none';
  if(on){
    const p = document.getElementById('actProg'); if(p) p.textContent = activationProgram;
    const r = document.getElementById('actRef'); if(r) r.textContent = myActivationRef;
    const pr = document.getElementById('actProgress');
    if(pr) pr.textContent = '0/' + (ACT_MIN[activationProgram]||10);
    refreshActivation();
    if(!activationTimer) activationTimer = setInterval(refreshActivation, 15000);
  } else if(activationTimer){
    clearInterval(activationTimer); activationTimer = null;
  }
}

async function refreshActivation(){
  if(!activationProgram || !myActivationRef) return;
  try{
    const r = await fetch('/activation/state'); if(!r.ok) return;
    const d = await r.json();
    if(!d.active) return;
    const pr = document.getElementById('actProgress');
    if(pr) pr.textContent = `${d.qso_total}/${d.min_qso}`;
    const fill = document.getElementById('actFill');
    if(fill) fill.style.width = Math.min(100, Math.round(100*d.qso_total/(d.min_qso||1))) + '%';
    const v = document.getElementById('actValid');
    if(v) v.innerHTML = d.valid
      ? '<span style="color:var(--green);font-weight:700">✅ VALIDÉE</span>'
      : `<span style="color:var(--yellow)">encore ${d.needed}</span>`;
    const p2p = document.getElementById('actP2P');
    if(p2p) p2p.textContent = d.p2p_count ? `${d.p2p_label} : ${d.p2p_count}` : '';
    const r2 = document.getElementById('actRef');
    if(r2) r2.style.color = d.valid_ref ? 'var(--text)' : 'var(--red)';
  }catch(e){}
}

// ─── HORAIRES CONCOURS ────────────────────────────────────────────────────────
// Format : {start:'ISO', end:'ISO', dur:'durée texte'}
// Déclaré tôt : référencé dès le chargement par updateClockAndCountdown() (appel
// synchrone immédiat plus bas) — un const référencé avant sa ligne d'init lève
// une ReferenceError (TDZ), même via un simple `typeof`.
const CONTEST_SCHEDULE = {
  'REF_RPH':      {start:'2026-07-04T14:00:00Z', end:'2026-07-05T14:00:00Z', dur:'24h', email:'rph@r-e-f.org'},
  'REF_CCD_JAN':  {start:'2026-01-03T13:00:00Z', end:'2026-01-03T17:00:00Z', dur:'4h',  email:'ccd@r-e-f.org'},
  'REF_CDF_SSB':  {start:'2026-03-28T14:00:00Z', end:'2026-03-29T14:00:00Z', dur:'24h', email:'logs@r-e-f.org'},
  'REF_CDF_CW':   {start:'2026-03-28T14:00:00Z', end:'2026-03-29T14:00:00Z', dur:'24h', email:'logs@r-e-f.org'},
  'REF_NAT_THF':  {start:'2026-03-07T06:00:00Z', end:'2026-03-08T06:00:00Z', dur:'24h', email:'thf@r-e-f.org'},
  'CQ_WW_SSB':    {start:'2026-10-24T00:00:00Z', end:'2026-10-26T00:00:00Z', dur:'48h', email:'logcheck@cqww.com'},
  'CQ_WW_CW':     {start:'2026-11-28T00:00:00Z', end:'2026-11-30T00:00:00Z', dur:'48h', email:'logcheck@cqww.com'},
  'CQ_WPX_SSB':   {start:'2026-03-28T00:00:00Z', end:'2026-03-30T00:00:00Z', dur:'48h', email:'wpxlog@cqww.com'},
  'CQ_WPX_CW':    {start:'2026-05-30T00:00:00Z', end:'2026-06-01T00:00:00Z', dur:'48h', email:'wpxlog@cqww.com'},
  'ARRL_DX_SSB':  {start:'2026-02-21T00:00:00Z', end:'2026-02-23T00:00:00Z', dur:'48h', email:'contests@arrl.org'},
  'ARRL_DX_CW':   {start:'2026-03-07T00:00:00Z', end:'2026-03-09T00:00:00Z', dur:'48h', email:'contests@arrl.org'},
  'IARU_TVA':     {start:'2026-05-09T06:00:00Z', end:'2026-05-10T06:00:00Z', dur:'24h', email:'vhf@iaru-r1.org'},
  'REF_IARU_TVA': {start:'2026-05-09T06:00:00Z', end:'2026-05-10T06:00:00Z', dur:'24h', email:'vhf@r-e-f.org'},
  'REF_IARU_50':  {start:'2026-05-09T06:00:00Z', end:'2026-05-10T06:00:00Z', dur:'24h', email:'vhf@r-e-f.org'},
  'REF_IARU_VHF': {start:'2026-07-04T06:00:00Z', end:'2026-07-05T06:00:00Z', dur:'24h', email:'vhf@r-e-f.org'},
  'REF_IARU_UHF': {start:'2026-07-04T06:00:00Z', end:'2026-07-05T06:00:00Z', dur:'24h', email:'uhf@r-e-f.org'},
  'REF_DDFM_50':  {start:'2026-06-20T06:00:00Z', end:'2026-06-20T10:00:00Z', dur:'4h',  email:'ddfm@r-e-f.org'},
  'REF_F9NL':     {start:'2026-03-15T08:00:00Z', end:'2026-03-15T16:00:00Z', dur:'8h',  email:'logs@r-e-f.org'},
  'CUSTOM':       {start:'', end:'', dur:'', email:''},
};

// ─── SÉLECTEUR CONCOURS (liste groupée pour csFilter/csSelect/csSetValue) ─────
// Mêmes id que radiocontest_configuration.html, groupés pour le combobox cherchable du modal.
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

let currentFilter = 'all';
let qsoLog = [];       // log local (cache)
let serialByBand = {}; // numéros de série par bande
let refreshTimer = null;
let isSetupDone = false;

const OP_COLORS = {OP1:'op-1',OP2:'op-2',OP3:'op-3',OP4:'op-4',OP5:'op-5'};

// ─── AUDIO ───────────────────────────────────────────────────────────────────
let _audioCtx = null;
function playBeep(freq=880, dur=80, vol=0.18){
  if(!bipEnabled) return;
  try{
    if(!_audioCtx) _audioCtx = new (window.AudioContext||window.webkitAudioContext)();
    const ctx = _audioCtx;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain); gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(freq, ctx.currentTime);
    gain.gain.setValueAtTime(vol, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur/1000);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + dur/1000 + 0.05);
  } catch(e){ /* pas de son possible */ }
}

// ─── UTILS ───────────────────────────────────────────────────────────────────
function locLL(loc){
  if(!loc||loc.length<6)return null;
  const l=loc.toUpperCase();
  try{
    const lon=(l.charCodeAt(0)-65)*20-180+parseInt(l[2])*2+(l.charCodeAt(4)-65)*(2/24)+1/24;
    const lat=(l.charCodeAt(1)-65)*10-90+parseInt(l[3])+(l.charCodeAt(5)-65)*(1/24)+0.5/24;
    return{lat,lon};
  }catch{return null;}
}

function hav(lat1,lon1,lat2,lon2){
  const R=6371,dLat=(lat2-lat1)*Math.PI/180,dLon=(lon2-lon1)*Math.PI/180;
  const a=Math.sin(dLat/2)**2+Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLon/2)**2;
  return Math.round(R*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a)));
}

function calcPoints(locDX, band, callDX, mode){
  const myLL = locLL(myLocator);
  const dxLL = locLL(locDX);
  if(!myLL||!dxLL) return 0;
  const dist = hav(myLL.lat,myLL.lon,dxLL.lat,dxLL.lon);

  // Scoring selon le concours actif
  const c = currentContest || '';

  // ── HF nord-américains : pts fixes par mode ───────────────────────────────
  if(['ARRL_FD','ARRL_DX_SSB','ARRL_DX_CW'].includes(c)){
    // ARRL FD : SSB=1pt, CW=2pts, Digital=2pts
    const m = (mode||'SSB').toUpperCase();
    const qsoPts = m==='CW'?2 : (m==='FT8'||m==='FT4'||m==='RTTY'||m==='PSK')?2 : 1;
    // Station hors NA = 0 pt
    if(callDX){
      const NA_PFX = /^(W|K|N|AA|AB|AC|AD|AE|AF|AG|AH|AI|AJ|AK|WA|WB|WC|WD|WE|WF|WG|WH|WI|WJ|WK|WL|WM|WN|WO|WP|WQ|WR|WS|WT|WU|WV|WW|WX|WY|WZ|KA|KB|KC|KD|KE|KF|KG|KH|KI|KJ|KK|KL|KM|KN|KO|KP|KQ|KR|KS|KT|KU|KV|KW|KX|KY|KZ|NA|NB|NC|ND|NE|NF|NG|NH|NI|NJ|NK|NL|NM|NN|NO|NP|NQ|NR|NS|NT|NU|NV|NW|NX|NY|NZ|VE|VA|VO|VY)/i;
      if(!NA_PFX.test(callDX)) return 0;
    }
    return qsoPts;
  }

  // ── CQ WW : 0/1/3 pts selon continent ────────────────────────────────────
  if(['CQ_WW_SSB','CQ_WW_CW'].includes(c)){
    if(!callDX) return 3;
    const CONTINENT = {F:'EU',G:'EU',DL:'EU',ON:'EU',PA:'EU',W:'NA',K:'NA',N:'NA',VE:'NA',JA:'AS',PY:'SA',VK:'OC',ZS:'AF'};
    const pfx2 = (callDX||'').slice(0,2).toUpperCase();
    const pfx1 = (callDX||'').slice(0,1).toUpperCase();
    const myPfx = (myCall||'F').slice(0,1).toUpperCase();
    const dxCont = CONTINENT[pfx2]||CONTINENT[pfx1]||'EU';
    const myCont = CONTINENT[myPfx]||'EU';
    const myCtry = (myCall||'').slice(0,2).toUpperCase();
    const dxCtry = (callDX||'').slice(0,2).toUpperCase();
    if(myCtry===dxCtry) return 0;
    if(myCont===dxCont) return 1;
    return 3;
  }

  // ── CQ WPX : 2-6 pts selon continent ─────────────────────────────────────
  if(['CQ_WPX_SSB','CQ_WPX_CW'].includes(c)){
    if(!callDX) return 3;
    const CONT = {F:'EU',G:'EU',DL:'EU',ON:'EU',W:'NA',K:'NA',N:'NA',VE:'NA',JA:'AS',PY:'SA',VK:'OC',ZS:'AF'};
    const myCont = CONT[(myCall||'F').slice(0,1).toUpperCase()]||'EU';
    const dxCont = CONT[(callDX||'').slice(0,2).toUpperCase()]||CONT[(callDX||'').slice(0,1).toUpperCase()]||'EU';
    if(myCont!==dxCont) return 6;
    if(/^(W|K|N|VE|XE)/.test(callDX||'')) return 2;
    return 1;
  }

  // ── REF HF : 1pt franco / 3pts DX ────────────────────────────────────────
  if(['REF_CDF_HF_SSB','REF_CDF_HF_CW','IARU_HF'].includes(c)){
    if(!callDX) return 1;
    if(/^(F|TM)/.test(callDX||'')) return 1;
    return 3;
  }

  // ── VHF/UHF (REF RPH, IARU VHF, EU VHF) : 1pt/km ───────────────────────
  return dist;
}

function calcDist(locDX){
  const myLL = locLL(myLocator);
  const dxLL = locLL(locDX);
  if(!myLL||!dxLL) return 0;
  return hav(myLL.lat,myLL.lon,dxLL.lat,dxLL.lon);
}

// ─── TABLE PRÉFIXES DXCC ─────────────────────────────────────────────────────
// Clé = préfixe (le plus long match gagne), valeur = {c:pays, ct:continent, cq:zone, flag:emoji}
const CTY_PREFIX = (function(){
  const EU14={ct:'EU',cq:14}, EU15={ct:'EU',cq:15}, EU16={ct:'EU',cq:16};
  const EU18={ct:'EU',cq:18}, EU20={ct:'EU',cq:20}, EU40={ct:'EU',cq:40};
  const NA5={ct:'NA',cq:5}, NA8={ct:'NA',cq:8};
  return {
    // ── France & DOM-TOM ──
    'F'  :{...EU14,c:'France',flag:'🇫🇷'},    'TM':{...EU14,c:'France',flag:'🇫🇷'},
    'FM' :{...NA8, c:'Martinique',flag:'🇲🇶'}, 'FG':{...NA8, c:'Guadeloupe',flag:'🇬🇵'},
    'FY' :{ct:'SA',cq:9,c:'Guyane fr.',flag:'🇬🇫'},
    'FR' :{ct:'AF',cq:39,c:'La Réunion',flag:'🇷🇪'},
    'FK' :{ct:'OC',cq:28,c:'Nvl-Calédonie',flag:'🇳🇨'},
    'FO' :{ct:'OC',cq:31,c:'Polynésie fr.',flag:'🇵🇫'},
    'FP' :{...NA5, c:'St-Pierre-Miquelon',flag:'🇵🇲'},
    'FH' :{ct:'AF',cq:39,c:'Mayotte',flag:'🇾🇹'},
    // ── Europe Occidentale ──
    'G'  :{...EU14,c:'Angleterre',flag:'🏴󠁧󠁢󠁥󠁮󠁧󠁿'}, 'GW':{...EU14,c:'Pays de Galles',flag:'🏴󠁧󠁢󠁷󠁬󠁳󠁿'},
    'GM' :{...EU14,c:'Écosse',flag:'🏴󠁧󠁢󠁳󠁣󠁴󠁿'},    'GI':{...EU14,c:'Irlande du Nord',flag:'🇬🇧'},
    'GD' :{...EU14,c:'Île de Man',flag:'🇮🇲'},   'GJ':{...EU14,c:'Jersey',flag:'🇯🇪'},
    'GU' :{...EU14,c:'Guernesey',flag:'🇬🇬'},
    'PA' :{...EU14,c:'Pays-Bas',flag:'🇳🇱'},    'PI':{...EU14,c:'Pays-Bas',flag:'🇳🇱'},
    'ON' :{...EU14,c:'Belgique',flag:'🇧🇪'},    'OO':{...EU14,c:'Belgique',flag:'🇧🇪'},
    'LX' :{...EU14,c:'Luxembourg',flag:'🇱🇺'},
    'HB9':{...EU14,c:'Suisse',flag:'🇨🇭'},      'HB':{...EU14,c:'Suisse',flag:'🇨🇭'},
    'HB0':{...EU14,c:'Liechtenstein',flag:'🇱🇮'},
    'DL' :{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DA' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DB':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DC' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DD':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DE' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DF':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DG' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DH':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DJ' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DK':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DM' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DO':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DQ' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DR':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'OE' :{...EU15,c:'Autriche',flag:'🇦🇹'},
    'CT' :{...EU14,c:'Portugal',flag:'🇵🇹'},   'CT3':{ct:'AF',cq:33,c:'Madère',flag:'🇵🇹'},
    'CU' :{...EU14,c:'Açores',flag:'🇵🇹'},
    'EA' :{...EU14,c:'Espagne',flag:'🇪🇸'},    'EH':{...EU14,c:'Espagne',flag:'🇪🇸'},
    'EA6':{...EU14,c:'Baléares',flag:'🇪🇸'},   'EA8':{ct:'AF',cq:33,c:'Canaries',flag:'🇮🇨'},
    'EI' :{...EU14,c:'Irlande',flag:'🇮🇪'},    'EJ':{...EU14,c:'Irlande',flag:'🇮🇪'},
    // ── Scandinavie ──
    'SM' :{...EU18,c:'Suède',flag:'🇸🇪'},    'SA':{...EU18,c:'Suède',flag:'🇸🇪'},
    'SB' :{...EU18,c:'Suède',flag:'🇸🇪'},    'SC':{...EU18,c:'Suède',flag:'🇸🇪'},
    'SE' :{...EU18,c:'Suède',flag:'🇸🇪'},    'SF':{...EU18,c:'Suède',flag:'🇸🇪'},
    'SG' :{...EU18,c:'Suède',flag:'🇸🇪'},    'SH':{...EU18,c:'Suède',flag:'🇸🇪'},
    'SI' :{...EU18,c:'Suède',flag:'🇸🇪'},    'SJ':{...EU18,c:'Suède',flag:'🇸🇪'},
    'SK' :{...EU18,c:'Suède',flag:'🇸🇪'},    'SL':{...EU18,c:'Suède',flag:'🇸🇪'},
    'LA' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LB':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'LC' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LD':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'LE' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LF':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'LG' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LH':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'LI' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LJ':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'LK' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LL':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'LM' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LN':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'OH' :{...EU18,c:'Finlande',flag:'🇫🇮'},  'OH0':{...EU18,c:'Åland',flag:'🇫🇮'},
    'OZ' :{...EU14,c:'Danemark',flag:'🇩🇰'},
    'OY' :{...EU18,c:'Féroé',flag:'🇫🇴'},
    'TF' :{...EU40,c:'Islande',flag:'🇮🇸'},
    'JW' :{...EU40,c:'Svalbard',flag:'🇸🇯'},   'JX':{...EU40,c:'Jan Mayen',flag:'🇸🇯'},
    // ── Europe de l'Est ──
    'SP' :{...EU15,c:'Pologne',flag:'🇵🇱'},    'SN':{...EU15,c:'Pologne',flag:'🇵🇱'},
    'SO' :{...EU15,c:'Pologne',flag:'🇵🇱'},    'SQ':{...EU15,c:'Pologne',flag:'🇵🇱'},
    'SR' :{...EU15,c:'Pologne',flag:'🇵🇱'},
    'OK' :{...EU15,c:'Rép. Tchèque',flag:'🇨🇿'}, 'OL':{...EU15,c:'Rép. Tchèque',flag:'🇨🇿'},
    'OM' :{...EU15,c:'Slovaquie',flag:'🇸🇰'},
    'HA' :{...EU15,c:'Hongrie',flag:'🇭🇺'},    'HG':{...EU15,c:'Hongrie',flag:'🇭🇺'},
    'YU' :{...EU15,c:'Serbie',flag:'🇷🇸'},     'YT':{...EU15,c:'Serbie',flag:'🇷🇸'},
    '9A' :{...EU15,c:'Croatie',flag:'🇭🇷'},
    'S5' :{...EU15,c:'Slovénie',flag:'🇸🇮'},
    'E7' :{...EU15,c:'Bosnie-Herzégovine',flag:'🇧🇦'},
    'Z3' :{...EU15,c:'Macédoine du Nord',flag:'🇲🇰'},
    'ZA' :{...EU15,c:'Albanie',flag:'🇦🇱'},
    'SV' :{...EU20,c:'Grèce',flag:'🇬🇷'},      'SV9':{...EU20,c:'Crète',flag:'🇬🇷'},
    'SV5':{...EU20,c:'Dodécanèse',flag:'🇬🇷'},
    'LZ' :{...EU20,c:'Bulgarie',flag:'🇧🇬'},
    'YO' :{...EU20,c:'Roumanie',flag:'🇷🇴'},   'YP':{...EU20,c:'Roumanie',flag:'🇷🇴'},
    'IT9':{...EU15,c:'Sicile',flag:'🇮🇹'},     'IS':{...EU15,c:'Sardaigne',flag:'🇮🇹'},
    'I'  :{...EU15,c:'Italie',flag:'🇮🇹'},
    'ES' :{...EU15,c:'Estonie',flag:'🇪🇪'},
    'YL' :{...EU15,c:'Lettonie',flag:'🇱🇻'},
    'LY' :{...EU15,c:'Lituanie',flag:'🇱🇹'},
    'EU' :{...EU16,c:'Biélorussie',flag:'🇧🇾'}, 'EV':{...EU16,c:'Biélorussie',flag:'🇧🇾'},
    'EW' :{...EU16,c:'Biélorussie',flag:'🇧🇾'},
    'UR' :{...EU16,c:'Ukraine',flag:'🇺🇦'},    'UT':{...EU16,c:'Ukraine',flag:'🇺🇦'},
    'UZ' :{...EU16,c:'Ukraine',flag:'🇺🇦'},
    'UA' :{...EU16,c:'Russie',flag:'🇷🇺'},     'R':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RA' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RB':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RC' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RD':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RE' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RF':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RG' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RK':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RL' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RM':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RN' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RO':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RP' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RQ':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RU' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RV':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RW' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RX':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RY' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RZ':{...EU16,c:'Russie',flag:'🇷🇺'},
    '3A' :{...EU14,c:'Monaco',flag:'🇲🇨'},
    // ── Proche-Orient / Asie ──
    'TA' :{ct:'AS',cq:20,c:'Turquie',flag:'🇹🇷'},
    '4X' :{ct:'AS',cq:20,c:'Israël',flag:'🇮🇱'},   '4Z':{ct:'AS',cq:20,c:'Israël',flag:'🇮🇱'},
    '5B' :{ct:'AS',cq:20,c:'Chypre',flag:'🇨🇾'},
    'EK' :{ct:'AS',cq:21,c:'Arménie',flag:'🇦🇲'},
    'JA' :{ct:'AS',cq:25,c:'Japon',flag:'🇯🇵'},
    'BY' :{ct:'AS',cq:24,c:'Chine',flag:'🇨🇳'},    'BD':{ct:'AS',cq:24,c:'Chine',flag:'🇨🇳'},
    'HL' :{ct:'AS',cq:25,c:'Corée du Sud',flag:'🇰🇷'},
    // ── Amérique du Nord ──
    'W'  :{...NA5,c:'États-Unis',flag:'🇺🇸'}, 'K':{...NA5,c:'États-Unis',flag:'🇺🇸'},
    'N'  :{...NA5,c:'États-Unis',flag:'🇺🇸'},
    'VE' :{...NA5,c:'Canada',flag:'🇨🇦'},    'VA':{...NA5,c:'Canada',flag:'🇨🇦'},
    'VO' :{...NA5,c:'Canada',flag:'🇨🇦'},    'VY':{...NA5,c:'Canada',flag:'🇨🇦'},
    'XE' :{ct:'NA',cq:6,c:'Mexique',flag:'🇲🇽'},
    // ── Amérique du Sud ──
    'PY' :{ct:'SA',cq:11,c:'Brésil',flag:'🇧🇷'},
    'LU' :{ct:'SA',cq:13,c:'Argentine',flag:'🇦🇷'},
    'CE' :{ct:'SA',cq:12,c:'Chili',flag:'🇨🇱'},
    // ── Océanie ──
    'VK' :{ct:'OC',cq:29,c:'Australie',flag:'🇦🇺'},
    'ZL' :{ct:'OC',cq:32,c:'Nouvelle-Zélande',flag:'🇳🇿'},
    // ── Afrique ──
    'ZS' :{ct:'AF',cq:38,c:'Afrique du Sud',flag:'🇿🇦'},
  };
})();

// Retourne {c, ct, cq, flag} pour un indicatif, ou null
function lookupDXCC(call){
  if(!call) return null;
  const c = call.toUpperCase().split('/')[0];
  // Essai du préfixe le plus long vers le plus court (max 4 chars)
  for(let len = Math.min(c.length, 4); len >= 1; len--){
    const pfx = c.slice(0, len);
    if(CTY_PREFIX[pfx]) return CTY_PREFIX[pfx];
  }
  return null;
}

// ─── QSO TIMER ───────────────────────────────────────────────────────────────
let lastQsoTime = null; // timestamp ms du dernier QSO validé

function updateQsoTimer(){
  const el = document.getElementById('sbQsoTimer');
  if(!el) return;
  if(!lastQsoTime || !qsoLog.length){
    el.textContent = '—';
    el.style.color = 'var(--muted)';
    return;
  }
  const sec = Math.floor((Date.now() - lastQsoTime) / 1000);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  el.textContent = m > 0 ? `${m}m ${s}s` : `${s}s`;
  // Couleur selon l'urgence
  el.style.color = m >= 5 ? 'var(--red)' : m >= 2 ? 'var(--yellow)' : 'var(--green)';
}
setInterval(updateQsoTimer, 1000);

function nowUTC(){
  const n=new Date();
  return `${String(n.getUTCHours()).padStart(2,'0')}:${String(n.getUTCMinutes()).padStart(2,'0')}`;
}

function nowDateUTC(){
  const n=new Date();
  return `${n.getUTCFullYear()}${String(n.getUTCMonth()+1).padStart(2,'0')}${String(n.getUTCDate()).padStart(2,'0')}`;
}

function nextSerial(band){
  if(!serialByBand[band]) serialByBand[band] = 0;
  serialByBand[band]++;
  return String(serialByBand[band]).padStart(3,'0');
}

function isDup(call, band){
  return qsoLog.some(q=>
    q.call.toUpperCase()===call.toUpperCase() && q.band===band
  );
}

// ─── QTC (WAE) ───────────────────────────────────────────────────────────────
// Visible uniquement quand le concours actif a un mécanisme QTC (WAE) :
// score final = (QSO + QTC) × mults, chaque QTC transféré vaut 1 point.
async function refreshQTC(){
  try{
    const r = await fetch('/qtc/list');
    if(!r.ok) return;
    const d = await r.json();
    const btn = document.getElementById('qtcBtn');
    if(!btn) return;
    btn.textContent = `✉ QTC : ${d.total || 0}`;
    // Afficher le bouton pour les concours à QTC (WAE*) — sinon masqué
    const contest = (JSON.parse(localStorage.getItem('radiocontest_config')||'{}').contest)||'';
    btn.style.display = /^WAEDC/i.test(contest) ? '' : 'none';
  }catch(e){}
}

async function addQTC(){
  const call = (prompt('QTC — indicatif de la station (série reçue ou envoyée) :')||'').toUpperCase().trim();
  if(!call) return;
  const n = parseInt(prompt(`Nombre de QTC échangés avec ${call} (1-10) :`, '10')||'0', 10);
  if(!n || n < 1) return;
  try{
    const r = await fetch('/qtc/add', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({call, count: n})
    });
    const d = await r.json();
    if(r.ok){
      notify(`✉ +${n} QTC avec ${call} — total ${d.total} (+${d.total} pts au score final)`);
      refreshQTC();
    } else {
      notify('QTC refusé : ' + (d.error || '?'));
    }
  }catch(e){ notify('Serveur injoignable — QTC non enregistré.'); }
}

setInterval(refreshQTC, 60*1000);
setTimeout(refreshQTC, 1500);

// ─── STATUT À LA FRAPPE (serveur) ────────────────────────────────────────────
// GET /log/check : nouveau / doublon / nouveau_mult, évalué par le MOTEUR DE
// SCORING contre le log partagé multi-op (pas seulement le log local).
let _checkTimer = null;
let _checkSeq = 0;

// ─── FICHE QRZ.com (à la frappe) ─────────────────────────────────────────────
// Affiche nom / QTH / locator du correspondant depuis QRZ (identifiants côté
// serveur). Debounce plus long (600 ms) : une requête réseau par indicatif fini.
let _qrzTimer = null, _qrzSeq = 0;

function lookupQRZ(call){
  clearTimeout(_qrzTimer);
  const el = document.getElementById('qrzInfo');
  if(!el) return;
  if(!call || call.length < 3){ el.style.display = 'none'; return; }
  const seq = ++_qrzSeq;
  _qrzTimer = setTimeout(async () => {
    try{
      const r = await fetch('/qrz/lookup?call=' + encodeURIComponent(call));
      if(!r.ok || seq !== _qrzSeq) return;
      const d = await r.json();
      if(d.enabled === false){ el.style.display = 'none'; return; }  // QRZ non configuré
      if(!d.ok){ el.style.display = 'none'; return; }
      const bits = [];
      if(d.name) bits.push('👤 ' + d.name);
      if(d.qth)  bits.push('📍 ' + d.qth);
      if(d.grid) bits.push('🗺 ' + d.grid);
      if(d.country && !d.qth) bits.push(d.country);
      el.innerHTML = bits.join(' · ');
      el.style.display = bits.length ? 'block' : 'none';
      // Pré-remplit le locator s'il est vide et que QRZ en connaît un
      const locInput = document.getElementById('inputLocator');
      if(locInput && !locInput.value && d.grid && d.grid.length >= 4){
        locInput.value = d.grid;
        onLocatorInput();
      }
    }catch(e){ /* réseau QRZ indispo : rien */ }
  }, 600);
}

function checkCallStatus(call){
  clearTimeout(_checkTimer);
  const badge = document.getElementById('callStatusBadge');
  if(!badge) return;
  if(!call || call.length < 3){ badge.style.display = 'none'; return; }
  const seq = ++_checkSeq;
  _checkTimer = setTimeout(async () => {
    try{
      const r = await fetch(`/log/check?call=${encodeURIComponent(call)}` +
                            `&band=${encodeURIComponent(currentBand || '')}` +
                            `&mode=${encodeURIComponent(currentMode || '')}`);
      if(!r.ok || seq !== _checkSeq) return;   // réponse périmée : ignorer
      const st = await r.json();
      if(st.status === 'inconnu'){ badge.style.display = 'none'; return; }
      const styles = {
        doublon:      ['⚠️ DOUBLON sur cette bande', 'var(--red)'],
        nouveau_mult: ['📈 NOUVEAU MULTIPLICATEUR' + (st.mult_type ? ' (' + st.mult_type + ')' : ''), 'var(--green)'],
        nouveau:      ['✔ nouveau' + (st.points ? ' · ' + st.points + ' pt' + (st.points > 1 ? 's' : '') : ''), 'var(--accent2)'],
      };
      const [txt, col] = styles[st.status] || styles.nouveau;
      badge.textContent = txt;
      badge.style.color = col;
      badge.style.border = '1px solid ' + col;
      badge.style.display = 'block';
      badge.title = st.explanation || '';
    }catch(e){ /* hors ligne : badge local dupWarn suffit */ }
  }, 250);
}

// ─── « DÉJÀ CONTACTÉ » (historique station, tous concours) ───────────────────
// À la frappe d'un indicatif, montre tous les QSO passés avec cette station
// (dates, bandes, confirmé LoTW) + alerte « NOUVEAU PAYS/DÉPARTEMENT » à vie —
// façon fiche « previous contacts » de Log4OM / HRD.
let _prevTimer = null, _prevSeq = 0;

function checkPrevQsos(call){
  clearTimeout(_prevTimer);
  const el = document.getElementById('prevQsos');
  if(!el) return;
  if(!call || call.length < 3){ el.style.display = 'none'; return; }
  const seq = ++_prevSeq;
  _prevTimer = setTimeout(async () => {
    try{
      const r = await fetch(`/call/history?call=${encodeURIComponent(call)}` +
                            `&band=${encodeURIComponent(currentBand || '')}`);
      if(!r.ok || seq !== _prevSeq) return;
      const d = await r.json();
      const parts = [];
      // Alerte « nouveau à vie » (pays / département jamais contacté)
      (d.new_one || []).forEach(n => {
        parts.push(`<div style="color:var(--green);font-weight:700">🌟 ${n.label}</div>`);
      });
      if(d.count > 0){
        const conf = d.confirmed ? ` · <span style="color:var(--green)">${d.confirmed} confirmé${d.confirmed>1?'s':''}</span>` : '';
        const bands = d.bands && d.bands.length ? ` sur ${d.bands.join('/')} MHz` : '';
        parts.push(`<div><b style="color:var(--accent2)">${d.count} QSO</b>${bands}${conf}` +
                   (d.last ? ` · dernier ${fmtDate(d.last)}` : '') + '</div>');
        // Les 3 plus récents
        d.qsos.slice(0,3).forEach(q => {
          parts.push(`<div style="opacity:.75">${fmtDate(q.date)} — ${q.band} MHz ${q.mode}` +
                     `${q.contest ? ' · ' + q.contest.replace(/_/g,' ') : ''}` +
                     `${q.confirmed ? ' ✅' : ''}</div>`);
        });
      } else if(!(d.new_one||[]).length){
        parts.push(`<span style="color:var(--muted)">jamais contacté</span>`);
      }
      el.innerHTML = parts.join('');
      el.style.display = parts.length ? 'block' : 'none';
    }catch(e){ el.style.display = 'none'; }
  }, 350);
}

function fmtDate(d){
  d = String(d || '');
  return d.length === 8 ? `${d.slice(6,8)}/${d.slice(4,6)}/${d.slice(0,4)}` : d;
}

// ─── BAND MAP (spots de la bande courante par fréquence, clic = QSY) ──────────
// Réutilise /data/spots_ranked (moteur : priorité + new_mult). Le marqueur ▶
// montre la fréquence de la radio (CAT). Clic sur un spot : remplit l'indicatif
// et QSY la radio si le CAT est actif.
const _BM_PCOL = {1:'var(--red)', 2:'var(--accent)', 3:'var(--yellow)',
                  4:'var(--accent2)', 5:'var(--muted)'};
// Plages de fréquence (MHz) par bande — le band map ne montre QUE la bande
// courante, filtrée par FRÉQUENCE (infaillible : un spot 50/432 ne peut pas
// apparaître sur 2 m même si le serveur l'a mal étiqueté).
const _BM_RANGE = {
  '1.8':[1.8,2.0], '3.5':[3.5,4.0], '7':[7.0,7.3], '14':[14.0,14.35],
  '21':[21.0,21.45], '28':[28.0,29.7], '50':[50,54], '70':[70,70.5],
  '144':[144,148], '432':[430,440], '1296':[1240,1300], '2320':[2300,2450],
  '3400':[3400,3475], '5760':[5650,5925], '10368':[10000,10500],
  '24048':[24000,24250], '47088':[47000,47200],
};

async function refreshBandMap(){
  const list = document.getElementById('bandmapList');
  if(!list) return;
  const bandEl = document.getElementById('bandmapBand');
  if(bandEl) bandEl.textContent = (currentBand || '—') + ' MHz';
  try{
    const r = await fetch('/data/spots_ranked');
    if(!r.ok) return;
    const d = await r.json();
    const rng = _BM_RANGE[String(currentBand)];
    const inBand = s => {
      if(!s.freq) return false;
      if(rng){ const f = parseFloat(s.freq); return f >= rng[0] && f <= rng[1]; }
      return String(s.band) === String(currentBand);   // repli si bande hors table
    };
    const spots = (d.spots || [])
      .filter(inBand)
      .sort((a,b) => parseFloat(b.freq) - parseFloat(a.freq));   // fréquence haute en haut
    const rig = (typeof rigState !== 'undefined') ? rigState : {};
    const txMhz = (rig.enabled && rig.freq_khz) ? rig.freq_khz/1000 : null;
    const rows = [];
    let txDone = false;
    const txRow = m => `<div class="bm-tx">▶ ${m.toFixed(3)} (radio)</div>`;
    for(const s of spots){
      const f = parseFloat(s.freq);
      if(txMhz && !txDone && f <= txMhz){ rows.push(txRow(txMhz)); txDone = true; }
      const col = s.new_mult ? 'var(--green)' : (_BM_PCOL[s.priority] || 'var(--text)');
      const style = `color:${col}` + (s.already_done ? ';opacity:.45;text-decoration:line-through' : '');
      rows.push(`<div class="bm-spot" onclick="bandmapClick('${s.call}',${f})" title="${(s.explanation||'').replace(/"/g,'')}">`
        + `<span class="bm-f">${f.toFixed(3)}</span>`
        + `<span class="bm-c" style="${style}">${s.new_mult ? '★' : ''}${s.call}</span></div>`);
    }
    if(txMhz && !txDone) rows.push(txRow(txMhz));
    list.innerHTML = rows.length ? rows.join('')
      : '<div class="bm-empty">aucun spot sur cette bande</div>';
    drawBandscope(spots, rng, txMhz);   // spectre d'activité visuel
  }catch(e){ /* serveur injoignable : band map inchangé */ }
}

// ─── BANDSCOPE : spectre d'activité de la bande (densité de spots) ────────────
// Un « scope » sans SDR : chaque spot devient une barre placée à sa fréquence,
// hauteur selon la priorité, vert = nouveau multiplicateur, ▼ = fréquence radio.
function drawBandscope(spots, rng, txMhz){
  const svg = document.getElementById('bandscope');
  if(!svg) return;
  if(!rng){ svg.innerHTML = ''; return; }
  const base = 62, x0 = 4, x1 = 176, span = (rng[1] - rng[0]) || 1;
  const xf = f => x0 + Math.max(0, Math.min(1, (f - rng[0]) / span)) * (x1 - x0);
  let g = `<line x1="${x0}" y1="${base}" x2="${x1}" y2="${base}" style="stroke:var(--border)" stroke-width="1"/>`;
  for(let i = 0; i <= 4; i++){
    const x = x0 + (x1 - x0) * i / 4;
    g += `<line x1="${x}" y1="${base}" x2="${x}" y2="${base+3}" style="stroke:var(--border)" stroke-width="0.5"/>`;
  }
  for(const s of (spots || [])){
    const f = parseFloat(s.freq);
    if(!isFinite(f)) continue;
    const x = xf(f);
    const h = s.new_mult ? 50 : Math.max(8, 46 - (s.priority || 3) * 7);
    const col = s.new_mult ? 'var(--green)' : (_BM_PCOL[s.priority] || 'var(--muted)');
    const op = s.already_done ? 0.35 : 1;
    const safeCall = String(s.call || '').replace(/[^A-Z0-9/]/gi, '');
    g += `<rect class="bs-bar" x="${(x-1).toFixed(1)}" y="${(base-h).toFixed(1)}" width="2" height="${h.toFixed(1)}"`
       + ` style="fill:${col}" opacity="${op}" onclick="bandmapClick('${safeCall}',${f})">`
       + `<title>${escHtml(s.call)} ${f.toFixed(3)}</title></rect>`;
  }
  if(txMhz && txMhz >= rng[0] && txMhz <= rng[1]){
    const x = xf(txMhz).toFixed(1);
    g += `<line x1="${x}" y1="8" x2="${x}" y2="${base}" style="stroke:var(--accent)" stroke-width="1.2"/>`
       + `<text x="${x}" y="7" style="fill:var(--accent)" font-size="6" text-anchor="middle">▼</text>`;
  }
  g += `<text x="${x0}" y="72" style="fill:var(--muted)" font-size="7">${rng[0]}</text>`
     + `<text x="${x1}" y="72" style="fill:var(--muted)" font-size="7" text-anchor="end">${rng[1]}</text>`;
  svg.innerHTML = g;
}

function bandmapClick(call, mhz){
  const inp = document.getElementById('inputCall');
  if(inp){ inp.value = call; onCallInput(); inp.focus(); }
  const rig = (typeof rigState !== 'undefined') ? rigState : {};
  if(rig.enabled){
    fetch('/rig/qsy', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({freq_khz: Math.round(mhz*1000), mode: currentMode || undefined})
    }).catch(()=>{});
  }
}
setInterval(refreshBandMap, 15000);
setTimeout(refreshBandMap, 2500);

// ═══ OPÉRER PLUS VITE : keyer vocal · ESM · décodeur CW ══════════════════════

// ─── KEYER VOCAL (phonie) ────────────────────────────────────────────────────
// Enregistre de courts messages WAV (CQ, réponse, report, merci) et les rejoue
// d'un clic — l'équivalent phonie des macros CW. Stockés en base64 (localStorage).
const VOICE_SLOTS = [
  {key:'V1', label:'CQ'}, {key:'V2', label:'RÉPONSE'},
  {key:'V3', label:'REPORT'}, {key:'V4', label:'MERCI'},
];
let _mediaRec = null, _recSlot = null, _recChunks = [];

function voiceStore(){ try{ return JSON.parse(localStorage.getItem('rc_voice')||'{}'); }catch(e){ return {}; } }
function voiceSave(s){ localStorage.setItem('rc_voice', JSON.stringify(s)); }

function renderVoicePanel(){
  const box = document.getElementById('voiceBtns');
  if(!box) return;
  const store = voiceStore();
  box.innerHTML = VOICE_SLOTS.map(s => {
    const has = !!store[s.key];
    return `<div style="display:flex;gap:4px;margin:3px 0">
      <button class="macro-btn" style="flex:1;${has?'':'opacity:.5'}" onclick="voicePlay('${s.key}')" ${has?'':'disabled'}>▶ ${s.label}</button>
      <button class="macro-btn" style="width:36px" onclick="voiceRecord('${s.key}')" id="rec_${s.key}" title="Enregistrer ${s.label}">⏺</button>
    </div>`;
  }).join('');
}

async function voiceRecord(key){
  const btn = document.getElementById('rec_'+key);
  if(_mediaRec && _recSlot === key){   // 2e clic = stop
    _mediaRec.stop();
    return;
  }
  try{
    const stream = await navigator.mediaDevices.getUserMedia({audio:true});
    _recChunks = []; _recSlot = key;
    _mediaRec = new MediaRecorder(stream);
    _mediaRec.ondataavailable = e => { if(e.data.size) _recChunks.push(e.data); };
    _mediaRec.onstop = () => {
      stream.getTracks().forEach(t=>t.stop());
      const blob = new Blob(_recChunks, {type: _mediaRec.mimeType||'audio/webm'});
      const rd = new FileReader();
      rd.onload = () => { const s = voiceStore(); s[key] = rd.result; voiceSave(s); renderVoicePanel(); notify('🎙 Message '+key+' enregistré'); };
      rd.readAsDataURL(blob);
      _mediaRec = null; _recSlot = null;
      if(btn){ btn.textContent = '⏺'; btn.style.color=''; }
    };
    _mediaRec.start();
    if(btn){ btn.textContent = '■'; btn.style.color='var(--red)'; }
    notify('🎙 Enregistrement… reclique ⏺ pour arrêter');
  }catch(e){ notify('❌ Micro indisponible : '+e.message); }
}

function voicePlay(key){
  const s = voiceStore();
  if(!s[key]) return;
  try{ const a = new Audio(s[key]); a.play(); }catch(e){}
}

// ─── ESM (Enter Sends Message) ───────────────────────────────────────────────
// Entrée enchaîne : (champ vide) appel CQ → (indicatif saisi) échange → (Entrée
// dans le N° reçu) log + « merci ». Utilise le keyer CW (macros) ou vocal (WAV)
// selon le mode. À la N1MM.
let esmMode = false, esmExchanged = false;

function toggleEsm(){
  esmMode = !esmMode;
  const b = document.getElementById('esmBtn');
  if(b){ b.textContent = 'ESM '+(esmMode?'●':'○'); b.style.color = esmMode?'var(--green)':'var(--muted)';
    b.style.borderColor = esmMode?'var(--green)':'var(--border)'; }
  notify(esmMode ? '⏎ ESM activé : Entrée enchaîne appel → échange → log' : 'ESM désactivé');
}

function esmSend(role){
  const cw = (typeof rigState!=='undefined') && rigState.enabled && /CW/i.test(rigState.mode||currentMode);
  if(cw){
    // Macros CW par convention : F1=CQ, F2=échange/report, F3=merci
    const idx = {cq:0, exchange:1, tu:2}[role] ?? 0;
    if(typeof copyMacro==='function') copyMacro(idx);
  }else{
    const slot = {cq:'V1', exchange:'V3', tu:'V4'}[role] || 'V1';
    voicePlay(slot);
  }
}

// Appelée par la touche Entrée du champ indicatif quand ESM est actif.
// Retourne true si ESM a « consommé » l'Entrée (pas de log immédiat).
function esmHandleEnter(){
  if(!esmMode) return false;
  const call = document.getElementById('inputCall').value.trim();
  if(!call){ esmSend('cq'); return true; }
  if(!esmExchanged){
    esmSend('exchange'); esmExchanged = true;
    const nr = document.getElementById('inputNumRcvd') || document.getElementById('inputRSTrcvd');
    if(nr) nr.focus();
    return true;
  }
  return false;   // échange déjà envoyé → laisser submitQSO() logguer
}

// ─── DÉCODEUR CW (Web Audio) ─────────────────────────────────────────────────
// getUserMedia → AnalyserNode → détection d'énergie dans la bande CW (~500-900 Hz)
// via Goertzel → chronométrie des points/traits → Morse → texte. Longueur de
// point adaptative. Décodeur « best effort » (CW propre bien décodée).
const MORSE = {'.-':'A','-...':'B','-.-.':'C','-..':'D','.':'E','..-.':'F','--.':'G',
 '....':'H','..':'I','.---':'J','-.-':'K','.-..':'L','--':'M','-.':'N','---':'O',
 '.--.':'P','--.-':'Q','.-.':'R','...':'S','-':'T','..-':'U','...-':'V','.--':'W',
 '-..-':'X','-.--':'Y','--..':'Z','-----':'0','.----':'1','..---':'2','...--':'3',
 '....-':'4','.....':'5','-....':'6','--...':'7','---..':'8','----.':'9','-.-.-':'K',
 '.-.-.':'+','-...-':'=','..--..':'?','-..-.':'/'};
let _cwCtx=null, _cwStream=null, _cwAnalyser=null, _cwRAF=null, _cwOn=false;
let _cwState={on:false, since:0, dot:70, morse:'', text:'', lastEdge:0, gapDone:false};

async function toggleCwDecoder(){
  if(_cwOn){ stopCwDecoder(); return; }
  try{
    _cwStream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false, noiseSuppression:false, autoGainControl:false}});
    _cwCtx = _audioCtx || new (window.AudioContext||window.webkitAudioContext)();
    if(_cwCtx.state==='suspended') await _cwCtx.resume();
    const src = _cwCtx.createMediaStreamSource(_cwStream);
    _cwAnalyser = _cwCtx.createAnalyser();
    _cwAnalyser.fftSize = 1024;
    src.connect(_cwAnalyser);
    _cwOn = true;
    _cwState = {on:false, since:performance.now(), dot:70, morse:'', text:'', lastEdge:performance.now(), gapDone:false};
    const b=document.getElementById('cwDecodeBtn'); if(b){ b.textContent='■ stop'; b.style.color='var(--red)'; }
    _cwLoop();
  }catch(e){ notify('❌ Micro indisponible : '+e.message); }
}

function stopCwDecoder(){
  _cwOn=false;
  if(_cwRAF) cancelAnimationFrame(_cwRAF);
  if(_cwStream) _cwStream.getTracks().forEach(t=>t.stop());
  const b=document.getElementById('cwDecodeBtn'); if(b){ b.textContent='▶ écouter'; b.style.color='var(--green)'; }
}

function _cwGoertzel(buf, rate){
  // Cherche l'énergie max dans la bande CW 450-950 Hz (par pas de 50 Hz)
  let best=0, bestF=0;
  for(let f=450; f<=950; f+=50){
    const w = 2*Math.PI*f/rate, cw = Math.cos(w), coeff=2*cw;
    let s0=0,s1=0,s2=0;
    for(let i=0;i<buf.length;i++){ s0=coeff*s1-s2+buf[i]; s2=s1; s1=s0; }
    const mag = s1*s1+s2*s2-coeff*s1*s2;
    if(mag>best){ best=mag; bestF=f; }
  }
  return {mag:Math.sqrt(best)/buf.length, freq:bestF};
}

let _cwFloor=0.002;
function _cwLoop(){
  if(!_cwOn) return;
  const N=_cwAnalyser.fftSize, buf=new Float32Array(N);
  _cwAnalyser.getFloatTimeDomainData(buf);
  const {mag,freq}=_cwGoertzel(buf, _cwCtx.sampleRate);
  _cwFloor = _cwFloor*0.99 + mag*0.01;               // plancher de bruit adaptatif
  const on = mag > Math.max(0.004, _cwFloor*3);
  const now=performance.now();
  const toneEl=document.getElementById('cwTone');
  if(toneEl) toneEl.textContent = on ? (freq+' Hz') : '—';

  const st=_cwState;
  if(on !== st.on){
    const dur = now - st.lastEdge;
    if(st.on){                       // fin d'un signal (mark)
      if(dur < st.dot*2){ st.morse+='.'; st.dot = st.dot*0.7 + dur*0.3; }
      else { st.morse+='-'; st.dot = st.dot*0.85 + (dur/3)*0.15; }
      st.dot = Math.max(30, Math.min(200, st.dot));
    }
    st.on=on; st.lastEdge=now; st.gapDone=false;
  } else if(!on && !st.gapDone && st.morse){
    const gap = now - st.lastEdge;
    if(gap > st.dot*2){              // fin de lettre
      const ch = MORSE[st.morse] || '';
      st.text += ch; st.morse='';
      _cwRender();
      st.gapDone=true;
    }
  } else if(!on && st.text && (now - st.lastEdge) > st.dot*6 && !st.spaced){
    st.text += ' '; st.spaced=true; _cwRender();
  }
  if(on) st.spaced=false;
  _cwRAF=requestAnimationFrame(_cwLoop);
}

function _cwRender(){
  const out=document.getElementById('cwDecodeOut');
  if(!out) return;
  const t=_cwState.text.slice(-40);
  out.innerHTML = t.replace(/(\S+)/g, '<span style="cursor:pointer" onclick="cwToCall(this.textContent)">$1</span>') || '—';
}
function cwToCall(w){
  const inp=document.getElementById('inputCall');
  if(inp && /\d/.test(w)){ inp.value=w.trim().toUpperCase(); onCallInput(); inp.focus(); }
}

// ─── AFFICHAGE DES PANNEAUX SELON LE MODE ────────────────────────────────────
function updateKeyerPanels(){
  const cw = (typeof rigState!=='undefined') && /CW/i.test(rigState.mode||currentMode||'');
  const macro=document.getElementById('macroPanel');
  const voice=document.getElementById('voicePanel');
  const cwd=document.getElementById('cwDecodePanel');
  if(macro) macro.style.display = cw ? '' : 'none';
  if(voice) voice.style.display = cw ? 'none' : '';
  if(cwd) cwd.style.display = cw ? '' : 'none';   // décodeur utile surtout en CW
}
renderVoicePanel();
setTimeout(updateKeyerPanels, 300);

// ─── SAUVEGARDE IMMÉDIATE (dossier cloud/NAS) ────────────────────────────────
async function backupNow(){
  try{
    const r = await fetch('/backup/now', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const d = await r.json();
    if(d.ok) notify(`💾 Sauvegarde OK → ${d.folder} (${d.files.length} fichiers)`);
    else notify('❌ '+(d.error||'sauvegarde impossible')+' — configure le dossier dans CONFIG');
  }catch(e){ notify('❌ '+e.message); }
}

// ─── SETUP ───────────────────────────────────────────────────────────────────
function setupDone(){
  const call = document.getElementById('setupCallsign').value.trim().toUpperCase();
  const loc  = document.getElementById('setupLocator').value.trim().toUpperCase();
  const op   = document.getElementById('setupOperator').value;
  const cont = document.getElementById('setupContest').value;

  if(!call||!loc||!op){
    notify('Remplis tous les champs !');
    return;
  }

  myCall = call;
  myLocator = loc;
  myOp = op;
  currentContest = cont;

  // Synchroniser le concours dans la config partagée (radiocontest_configuration.html le lira aussi)
  let stored = {};
  try{
    stored = JSON.parse(localStorage.getItem('radiocontest_config')||'{}');
    stored.contest = cont;
    stored.callsign = stored.callsign || call;
    stored.callsign_contest = call;
    stored.locator = stored.locator || loc;

    // Appliquer les dates du CONTEST_SCHEDULE uniquement si l'utilisateur n'en a pas configuré
    const sched = CONTEST_SCHEDULE[cont];
    if(sched && sched.start && !stored.contest_end_date){
      const s = new Date(sched.start), e = new Date(sched.end);
      stored.contest_start_date = s.toISOString().slice(0,10);
      stored.contest_start_utc  = s.toISOString().slice(11,16);
      stored.contest_end_date   = e.toISOString().slice(0,10);
      stored.contest_end_utc    = e.toISOString().slice(11,16);
    }
    localStorage.setItem('radiocontest_config', JSON.stringify(stored));
  }catch(e2){}

  // Afficher uniquement les bandes et modes autorisés par le concours choisi
  renderBandButtons(cont);
  renderModeButtons(cont);
  applyExchangeFormat(cont);
  // Priorité au réglage local (page CONFIG de ce navigateur) ; sinon on hérite
  // du réglage serveur partagé pour que tous les postes d'expédition l'aient.
  applyExpeditionMode(stored.expedition_mode !== undefined && stored.expedition_mode !== ''
    ? stored.expedition_mode
    : (typeof serverExpeditionMode !== 'undefined' ? serverExpeditionMode : ''));
  // Activation POTA/SOTA/IOTA/WWFF (config locale prioritaire, sinon serveur partagé)
  applyActivationMode(
    stored.activation_program || (typeof serverActivationProgram !== 'undefined' ? serverActivationProgram : ''),
    stored.my_activation_ref  || (typeof serverActivationRef !== 'undefined' ? serverActivationRef : ''));

  // Sélectionner le bon bouton OP
  document.querySelectorAll('.op-btn').forEach(b=>{
    b.classList.toggle('active', b.dataset.op===op);
  });

  // Affichage proéminent de la station opérée : indicatif, locator, altitude, département
  const hdrParts = [call, loc];
  if(stored.altitude) hdrParts.push(`${stored.altitude}m`);
  if(stored.postal && stored.postal.length>=2) hdrParts.push(`Dépt.${stored.postal.slice(0,2)}`);
  document.getElementById('hdrStation').textContent = hdrParts.join(' · ');
  document.getElementById('hdrContest').textContent = cont;
  // Indicateur « OP : » — en single-op, montrer l'indicatif plutôt que « OP1 »
  const opsCfg = stored.operators || [];
  const opIdx = parseInt((op||'OP1').replace('OP',''), 10) - 1;
  const opCall = (opsCfg[opIdx] && (opsCfg[opIdx].call || opsCfg[opIdx].callsign)) || call;
  document.getElementById('currentOp').textContent = opCall || op;
  document.getElementById('setupModal').style.display = 'none';
  // Recharger les dates de début/fin pour le countdown
  contestEndUTC   = getContestEndUTC();
  contestStartUTC = getContestStartUTC();
  updateClockAndCountdown();

  isSetupDone = true;
  updateSerialDisplay();
  startRefresh();
  startON4KSTReminder();
  startChat();
  fetchLog();

  document.getElementById('inputCall').focus();
}

// ─── CLOCK + COUNTDOWN ───────────────────────────────────────────────────────
function getContestEndUTC(){
  try{
    const cfg = JSON.parse(localStorage.getItem('radiocontest_config')||'{}');
    if(cfg.contest_end_date && cfg.contest_end_utc){
      return new Date(`${cfg.contest_end_date}T${cfg.contest_end_utc}Z`);
    }
  }catch(e){}
  return new Date('2026-07-05T14:00:00Z'); // fallback RPH 2026 (sam 4 juil 14h UTC → dim 5 juil 14h UTC)
}
function getContestStartUTC(){
  try{
    const cfg = JSON.parse(localStorage.getItem('radiocontest_config')||'{}');
    if(cfg.contest_start_date && cfg.contest_start_utc){
      return new Date(`${cfg.contest_start_date}T${cfg.contest_start_utc}Z`);
    }
  }catch(e){}
  return null; // pas de date de début configurée
}
let contestEndUTC   = getContestEndUTC();
let contestStartUTC = getContestStartUTC();
let contestEndAlertShown = false;

// Le libellé du compte à rebours n'est écrit que lorsqu'il CHANGE de phase
// (pas chaque seconde) : évite de réécrire du texte en continu — donc évite le
// clignotement quand une langue ≠ français re-traduit le libellé. On re-traduit
// une seule fois, au changement.
let _cdPhase = '';
function setCountdownLabel(phase, text){
  const lbl = document.getElementById('sbCountdownLbl');
  if(!lbl || _cdPhase === phase) return;
  _cdPhase = phase;
  lbl.textContent = text;
  if(window.rcTranslate) window.rcTranslate();
}

function updateClockAndCountdown(){
  const n = new Date();
  document.getElementById('clock').textContent =
    `${String(n.getUTCHours()).padStart(2,'0')}:${String(n.getUTCMinutes()).padStart(2,'0')}:${String(n.getUTCSeconds()).padStart(2,'0')} UTC`;

  const cd  = document.getElementById('sbCountdown');
  const lbl = document.getElementById('sbCountdownLbl');
  const box = document.getElementById('sbCountdownItem');

  // ── Phase 1 : concours pas encore commencé ──────────────────────────────
  // Si contestStartUTC non dispo en localStorage, essayer CONTEST_SCHEDULE
  let effStartUTC = contestStartUTC;
  if(!effStartUTC && typeof CONTEST_SCHEDULE !== 'undefined'){
    try{
      const _cfg = JSON.parse(localStorage.getItem('radiocontest_config')||'{}');
      const _s = CONTEST_SCHEDULE[_cfg.contest];
      if(_s && _s.start) effStartUTC = new Date(_s.start);
    }catch(_e){}
  }
  if(effStartUTC && n < effStartUTC){
    const diff = effStartUTC - n;
    const totalSec = Math.floor(diff / 1000);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    setCountdownLabel('before', '🟢 DÉBUTE DANS');
    cd.textContent = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    cd.style.color = '#34C759';
    if(box) box.style.borderLeftColor = '#34C759';
    return;
  }

  // ── Phase 2 : concours en cours ─────────────────────────────────────────
  setCountdownLabel('run', '⏱ TEMPS RESTANT');
  if(box) box.style.borderLeftColor = 'var(--red)';

  const diff = contestEndUTC - n;
  if(diff <= 0){
    cd.textContent = '🏁 TERMINÉ';
    cd.style.color = '#4A5080';
    if(!contestEndAlertShown && isSetupDone){
      contestEndAlertShown = true;
      setTimeout(()=>notify('🏁 CONCOURS TERMINÉ !\n\nPense à exporter ton log maintenant :\n📥 EDI / ADIF dans la barre d\'outils du logbook.'), 300);
    }
    return;
  }
  const totalSec = Math.floor(diff / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  cd.textContent = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  if(h < 1)       cd.style.color = '#FF2D55';
  else if(h < 4)  cd.style.color = '#FFD60A';
  else             cd.style.color = '#FF6B00';
}
setInterval(updateClockAndCountdown, 1000);
updateClockAndCountdown();

// ─── OPÉRATEUR / BANDE / MODE ────────────────────────────────────────────────
function setOp(el){
  document.querySelectorAll('.op-btn').forEach(b=>b.classList.remove('active'));
  el.classList.add('active');
  myOp = el.dataset.op;
  document.getElementById('currentOp').textContent = myOp;
}

function setBand(el){
  document.querySelectorAll('#bandSelect .bm-btn').forEach(b=>b.classList.remove('active'));
  el.classList.add('active');
  currentBand = el.dataset.val;
  setFreqForBand(currentBand);
  updateSerialDisplay();
  if(typeof refreshBandMap === 'function') refreshBandMap();  // spots de la nouvelle bande
  document.getElementById('inputCall').focus();
}

// Pré-remplit le champ FRÉQUENCE : fréquence réelle de la radio (CAT) si dispo,
// sinon fréquence d'appel par défaut de la bande.
function setFreqForBand(band){
  const el = document.getElementById('inputFreq');
  if(!el) return;
  delete el.dataset.userEdited;   // changement de bande → la saisie manuelle est réinitialisée
  const rigMhz = (typeof rigState === 'object' && rigState && rigState.enabled && rigState.freq_khz > 0)
    ? rigState.freq_khz / 1000 : null;
  // N'utiliser la fréquence radio que si elle tombe DANS la bande demandée
  // (sinon on collerait la freq d'une autre bande → couple bande/freq incohérent).
  if(rigMhz != null && bandFromFreq(rigMhz) === band){
    el.value = rigMhz.toFixed(3);
  } else {
    el.value = BAND_FREQ[band] || '';
  }
}

// L'opérateur tape une fréquence → sélectionne automatiquement la bonne bande.
function onFreqInput(){
  const el = document.getElementById('inputFreq');
  if(!el) return;
  el.dataset.userEdited = '1';   // saisie manuelle → le CAT ne doit plus écraser
  const b = bandFromFreq(el.value);
  if(b && b !== currentBand){
    const btn = document.querySelector(`#bandSelect .bm-btn[data-val="${b}"]`);
    if(btn){
      document.querySelectorAll('#bandSelect .bm-btn').forEach(x=>x.classList.remove('active'));
      btn.classList.add('active');
      currentBand = b;
      updateSerialDisplay();
      if(typeof refreshBandMap === 'function') refreshBandMap();
    }
  }
}

// Bouton 📻 : force la lecture de la fréquence radio (CAT) dans le champ.
function freqFromRig(){
  const el = document.getElementById('inputFreq');
  if(el && typeof rigState === 'object' && rigState && rigState.freq_khz > 0){
    el.value = (rigState.freq_khz / 1000).toFixed(3);
    onFreqInput();
    delete el.dataset.userEdited;   // on suit à nouveau la radio en direct
  } else {
    notify('Radio non connectée (CAT) — saisis la fréquence à la main.');
  }
}

function setMode(el){
  document.querySelectorAll('#modeSelect .bm-btn').forEach(b=>b.classList.remove('active'));
  el.classList.add('active');
  currentMode = el.dataset.val;
  if(typeof updateKeyerPanels==='function') updateKeyerPanels();  // keyer vocal/CW
  document.getElementById('inputCall').focus();
}

// ─── BANDES & MODES PAR CONCOURS (selon règlements REF / IARU / CQ) ───────────
const BAND_LABELS = {
  // HF — noms par longueur d'onde
  '1.8':'160m','3.5':'80m','7':'40m','14':'20m','21':'15m','28':'10m',
  // VHF/UHF/SHF
  '50':'6m','70':'4m','144':'2m','432':'70cm','1296':'23cm',
  '2320':'13cm','3400':'9cm','5760':'6cm','10368':'3cm',
  '24048':'6mm','47088':'4mm',
};
// Fréquence d'appel par défaut (MHz) par bande — pré-remplit le champ FRÉQUENCE
// quand on change de bande (sauf si le CAT donne la fréquence réelle).
const BAND_FREQ = {
  '1.8':'1.843','3.5':'3.650','7':'7.130','14':'14.150','21':'21.250','28':'28.400',
  '50':'50.150','70':'70.200','144':'144.300','432':'432.200','1296':'1296.200',
  '2320':'2320.200','3400':'3400.200','5760':'5760.200','10368':'10368.200',
  '24048':'24048.200','47088':'47088.200',
};
// Échappement HTML — pour toute donnée d'origine externe (ADIF importé, spots
// cluster) insérée via innerHTML. Empêche l'injection (XSS) en contexte attribut.
function escHtml(v){
  return String(v == null ? '' : v).replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// Fréquence (MHz) → clé de bande interne, via les plages _BM_RANGE. Permet de
// sélectionner automatiquement la bonne bande quand l'opérateur saisit une freq.
function bandFromFreq(freqMHz){
  const f = parseFloat(freqMHz);
  if(!isFinite(f)) return null;
  for(const [b, r] of Object.entries(_BM_RANGE)){
    if(f >= r[0] && f <= r[1]) return b;
  }
  return null;
}
const BANDS_THF = ['144','432','1296','2320','3400','5760','10368','24048','47088']; // 144 MHz → 47 GHz
const BANDS_HF  = ['1.8','3.5','7','14','21','28'];
const ALL_BANDS = ['1.8','3.5','7','14','21','28','50','70','144','432','1296','2320','3400','5760','10368','24048','47088'];

// Bandes autorisées par concours
const CONTEST_BANDS = {
  REF_RPH:       ['144','432','1296','2320','3400','5760','10368','24048','47088'], // RPH : 144 MHz → 47 GHz
  REF_NAT_THF:   BANDS_THF,
  REF_PRINTEMPS: BANDS_THF,
  REF_ETE:       BANDS_THF,
  REF_CDF_THF:   BANDS_THF,
  REF_IARU_VHF:  ['144'],
  REF_IARU_UHF:  ['432','1296','2320','3400','5760','10368','24048','47088'],
  REF_CCD:       ['144','432','1296','2320'],
  CQ_WW_SSB:     BANDS_HF,
  CQ_WW_CW:      BANDS_HF,
  ARRL_FD:       [...BANDS_HF, '50'],
  CUSTOM:        ALL_BANDS,
};

// Modes autorisés par concours
const CONTEST_MODES = {
  REF_RPH:       ['SSB','CW','FM'],    // RPH : lu depuis config.json au démarrage
  REF_NAT_THF:   ['SSB','CW','FM'],
  REF_PRINTEMPS: ['SSB','CW','FM'],
  REF_ETE:       ['SSB','CW','FM'],
  REF_CDF_THF:   ['SSB','CW','FM'],
  REF_IARU_VHF:  ['SSB','CW'],
  REF_IARU_UHF:  ['SSB','CW'],
  REF_CCD:       ['SSB','CW','FM'],
  CQ_WW_SSB:     ['SSB'],
  CQ_WW_CW:      ['CW'],
  ARRL_FD:       ['SSB','CW','FT8','FT4','RTTY'],
  CUSTOM:        ['SSB','CW','FM','FT8'],
};

// Correspondance valeur bande → clé toggle configuration
const BAND_TOGGLE_KEY = {
  '1.8':   'band_160m', '3.5':   'band_80m',  '7':     'band_40m',
  '14':    'band_20m',  '21':    'band_15m',   '28':    'band_10m',
  '50':    'band_6m',   '70':    'band_4m',    '144':   'band_2m',
  '432':   'band_70cm', '1296':  'band_23cm',  '2320':  'band_13cm',
  '3400':  'band_9cm',  '5760':  'band_6cm',   '10368': 'band_3cm',
  '24048': 'band_6mm',  '47088': 'band_4mm',
};

function renderBandButtons(contest){
  // Bandes du concours filtrées par les toggles de configuration
  const contestBands = CONTEST_BANDS[contest] || ALL_BANDS;

  // Lire les toggles depuis localStorage pour masquer les bandes décochées
  let toggles = {};
  try{ toggles = JSON.parse(localStorage.getItem('radiocontest_config')||'{}').toggles || {}; }catch(e){}

  const finalBands = contestBands.filter(b => {
    const key = BAND_TOGGLE_KEY[b];
    // Si la clé toggle n'existe pas → bande toujours visible
    // Si le toggle est explicitement false → bande masquée
    return !key || toggles[key] !== false;
  });

  const visibleBands = finalBands.length ? finalBands : contestBands; // fallback si tout est masqué
  const box = document.getElementById('bandSelect');
  box.innerHTML = visibleBands.map((b,i)=>
    `<button class="bm-btn${i===0?' active':''}" data-val="${b}" onclick="setBand(this)">${BAND_LABELS[b]||b+' MHz'}</button>`
  ).join('');
  currentBand = visibleBands[0];
  setFreqForBand(currentBand);
}

// Correspondance mode affiché → clé toggle configuration
const MODE_TOGGLE_KEY = {
  'SSB':  'mode_ssb',
  'CW':   'mode_cw',
  'FM':   'mode_fm',
  'FT8':  'mode_ft8',
  'FT4':  'mode_ft4',
  'RTTY': 'mode_rtty',
  'DIGI': 'mode_ft8',
};

function renderModeButtons(contest){
  const allModes = CONTEST_MODES[contest] || ['SSB','CW','FM','FT8'];
  // Modes affichés = modes explicitement activés par l'utilisateur en config,
  // sans se limiter à la liste par défaut du concours (ex: FT8 coché doit
  // apparaître même si le règlement du concours ne le propose pas par défaut).
  let cfgLocal = {};
  try{ cfgLocal = JSON.parse(localStorage.getItem('radiocontest_config')||'{}'); }catch(e){}
  const toggles = cfgLocal.toggles || {};
  const hasModeTgls = Object.keys(toggles).some(k => k.startsWith('mode_'));
  const modes = hasModeTgls
    ? ['SSB','CW','FM','FT8','FT4','RTTY'].filter(m => toggles[MODE_TOGGLE_KEY[m]] === true)
    : allModes;
  const finalModes = modes.length > 0 ? modes : allModes; // sécurité: tout afficher si rien de coché
  const box = document.getElementById('modeSelect');
  box.innerHTML = finalModes.map((m,i)=>
    `<button class="bm-btn${i===0?' active':''}" data-val="${m}" onclick="setMode(this)">${m}</button>`
  ).join('');
  currentMode = finalModes[0];
}

function updateSerialDisplay(){
  const numSentEl = document.getElementById('inputNumSent');
  // Ne rien faire si le concours utilise une valeur fixe (ex: "1D DX" pour ARRL Field Day)
  if(!currentExchange.auto_serial){
    numSentEl.readOnly = false;
    numSentEl.tabIndex = 0;
    numSentEl.classList.remove('field-readonly');
    if(currentExchange.def_s){
      numSentEl.value = currentExchange.def_s;
    }
    return;
  }
  // Numéro envoyé 100% automatique — l'opérateur ne doit jamais pouvoir le modifier
  // ni revenir en arrière, même s'il y a un trou dans la séquence (cf. nextSerial()/fetchLog())
  numSentEl.readOnly = true;
  numSentEl.tabIndex = -1;
  numSentEl.classList.add('field-readonly');
  const next = (serialByBand[currentBand]||0) + 1;
  numSentEl.value = String(next).padStart(3,'0');
}

// ─── SAISIE ──────────────────────────────────────────────────────────────────
function onCallInput(){
  const call = document.getElementById('inputCall').value.toUpperCase();
  document.getElementById('inputCall').value = call;

  // Autocomplete
  if(call.length >= 2){
    showAC(searchCalls(call), call);
  } else {
    hideAC();
  }

  // Statut serveur à la frappe : nouveau / doublon / NOUVEAU MULT (moteur
  // de scoring + log partagé multi-op, pas seulement le log local)
  checkCallStatus(call);
  lookupQRZ(call);
  checkPrevQsos(call);   // « déjà contacté » + nouveau pays/dept à vie

  // Badge pays DXCC
  const dxccBadge = document.getElementById('dxccBadge');
  if(call.length >= 2){
    const dxcc = lookupDXCC(call);
    const dup3 = isDup(call, currentBand);
    if(dxcc){
      document.getElementById('dxccFlag').textContent = dxcc.flag;
      document.getElementById('dxccCountry').textContent = dxcc.c;
      document.getElementById('dxccInfo').textContent = `${dxcc.ct} · Zone CQ ${dxcc.cq}${dup3?' · ⚠️ DUPE':''}`;
      dxccBadge.style.display = 'flex';
      dxccBadge.classList.toggle('dupe', dup3);
    } else {
      dxccBadge.style.display = 'none';
    }
  } else {
    dxccBadge.style.display = 'none';
  }

  // Dup check
  const dup = isDup(call, currentBand);
  const warn = document.getElementById('dupWarn');
  const input = document.getElementById('inputCall');
  if(dup && call.length >= 3){
    warn.style.background = 'rgba(255,45,85,.1)';
    warn.style.borderColor = 'var(--red)';
    warn.style.color = 'var(--red)';
    warn.textContent = '⚠️ DOUBLON — Ce correspondant est déjà dans le log !';
    warn.classList.add('show');
    input.classList.add('error');
    input.classList.remove('ok');
    hideCompassInline();
  } else if(call.length >= 3 && !dup){
    input.classList.add('ok');
    input.classList.remove('error');
    // Lookup 1 : base calldb + cluster
    const dbData      = lookupCall(call);
    const clusterData = lookupCluster(call);
    // Lookup 2 : log courant (QSO précédent avec ce correspondant)
    const logEntry = qsoLog.slice().reverse().find(q => q.call === call && q.locator && q.locator.length === 6);
    clearTimeout(callLookupTimer);
    if(dbData || clusterData || logEntry){
      applyCallData(dbData, clusterData, logEntry);
    } else {
      warn.classList.remove('show');
      hideCompassInline();
      // Lookup distant HamQTH avec debounce 600 ms
      if(call.length >= 4)
        callLookupTimer = setTimeout(() => remoteCallLookup(call), 600);
    }
    crossBandAlert(call, currentBand);
  } else {
    warn.classList.remove('show');
    input.classList.remove('ok','error');
    hideCompassInline();
    const _cbh=document.getElementById('crossBandHint');if(_cbh)_cbh.classList.remove('show');
  }
}

function bearing(loc){
  const myLL = locLL(myLocator);
  const dxLL = locLL(loc);
  if(!myLL||!dxLL) return null;
  const φ1=myLL.lat*Math.PI/180, φ2=dxLL.lat*Math.PI/180;
  const Δλ=(dxLL.lon-myLL.lon)*Math.PI/180;
  const y=Math.sin(Δλ)*Math.cos(φ2);
  const x=Math.cos(φ1)*Math.sin(φ2)-Math.sin(φ1)*Math.cos(φ2)*Math.cos(Δλ);
  return Math.round((Math.atan2(y,x)*180/Math.PI+360)%360);
}

function cardinalDir(deg){
  const dirs=["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSO","SO","OSO","O","ONO","NO","NNO"];
  return dirs[Math.round(deg/22.5)%16];
}

function validateLocator(loc){
  return /^[A-R]{2}[0-9]{2}[A-X]{2}$/i.test(loc);
}

function onLocatorInput(){
  const loc = document.getElementById('inputLocator').value.toUpperCase();
  document.getElementById('inputLocator').value = loc;
  const field = document.getElementById('inputLocator');
  const hint = document.getElementById('locHint');

  if(loc.length === 0){
    field.classList.remove('ok','error');
    hint.style.display = 'none';
    hideCompassInline();
    hideLocAC();
    return;
  }
  if(loc.length < 6){
    field.classList.remove('ok','error');
    hint.style.display = 'none';
    hideCompassInline();
    // Reverse lookup : dès 4 caractères, proposer des indicatifs de ce carré
    if(loc.length >= 4){
      const matches = searchByLocator(loc);
      if(matches.length) showLocAC(matches);
      else hideLocAC();
    } else {
      hideLocAC();
    }
    return;
  }
  hideLocAC(); // locator complet → on cache la suggestion
  if(loc.length === 6){
    if(!validateLocator(loc)){
      field.classList.add('error');
      field.classList.remove('ok');
      hint.textContent = '⚠️ Format invalide — attendu : AA00AA (ex: JN03QQ)';
      hint.style.color = 'var(--red)';
      hint.style.display = 'block';
      return;
    }
    field.classList.add('ok');
    field.classList.remove('error');
    const dist = calcDist(loc);
    const callInput = document.getElementById('inputCall')?.value?.toUpperCase()||'';
    const modeInput = document.getElementById('inputMode')?.value||currentMode||'SSB';
    const pts = calcPoints(loc, currentBand, callInput, modeInput);
    const locAlreadyUsed = qsoLog.some(q => q.locator === loc);
    if(dist > 0){
      const cap = bearing(loc);
      const card = cap !== null ? cardinalDir(cap) : '';
      const capStr = cap !== null ? `🧭 ${cap}° ${card}` : '';
      const dupNote = locAlreadyUsed ? '  ⚠️ Locator déjà loggué' : '';
      hint.textContent = `📏 ${dist} km  ${capStr}  → 🏆 ${pts} pts${dupNote}`;
      hint.style.color = locAlreadyUsed ? 'var(--yellow)' : 'var(--accent)';
      hint.style.display = 'block';
      if(cap !== null) showCompassInline(cap, dist, pts);
      else hideCompassInline();
    } else {
      if(locAlreadyUsed){
        hint.textContent = '⚠️ Locator déjà loggué';
        hint.style.color = 'var(--yellow)';
        hint.style.display = 'block';
      }
      hideCompassInline();
    }
  }
}

function focusNext(id){
  document.getElementById(id)?.focus();
  document.getElementById(id)?.select();
}

async function submitQSO(){
  const call = document.getElementById('inputCall').value.trim().toUpperCase();
  const rstSent = document.getElementById('inputRSTsent').value.trim() || '59';
  const rstRcvd = document.getElementById('inputRSTrcvd').value.trim() || '59';
  const numSent = document.getElementById('inputNumSent').value.trim();
  const numRcvdRaw = document.getElementById('inputNumRcvd').value.trim();
  const numRcvd = (currentExchange.pad_r === true && numRcvdRaw)
    ? String(parseInt(numRcvdRaw, 10) || 0).padStart(3, '0')
    : numRcvdRaw;
  const loc     = document.getElementById('inputLocator').value.trim().toUpperCase();

  if(!call){ notify('Indicatif manquant !'); return; }
  if(loc && !validateLocator(loc)){
    document.getElementById('inputLocator').focus();
    notify('Locator invalide !\nFormat attendu : AA00AA  (ex: JN03QQ)');
    return;
  }
  // Locator vide : simple avertissement, le QSO est quand même enregistré (0 pt).
  // En mode expédition le locator est masqué : pas d'avertissement, on enchaîne.
  if(!loc && !expeditionMode){
    notify('⚠️ Locator non renseigné !\nLe QSO va être enregistré sans locator (0 pt).');
  }

  // Vérification doublon
  if(isDup(call, currentBand)){
    if(!confirm(`⚠️ ${call} est déjà dans le log sur ${currentBand} MHz.\nQuand même enregistrer ?`)) return;
  }

  // N° envoyé : auto-série (VHF) ou valeur du champ (FD classe, CQ WW zone, HF dept...)
  const numSentField = document.getElementById('inputNumSent').value.trim();
  const serial = currentExchange.auto_serial ? nextSerial(currentBand) : numSentField;
  const dist = (loc && loc.length >= 6) ? calcDist(loc) : 0;
  const pts  = calcPoints(loc, currentBand, call, currentMode);

  const freq = (document.getElementById('inputFreq')?.value || '').trim();
  const qso = {
    id: Date.now(),
    date: nowDateUTC(),
    time: nowUTC(),
    call, band: currentBand, mode: currentMode, freq,
    rst_sent: rstSent, num_sent: serial,
    rst_rcvd: rstRcvd, num_rcvd: numRcvd,
    locator: loc, dist, points: pts,
    operator: myOp,
    my_call: myCall, my_locator: myLocator,
    contest: currentContest,
  };

  // Activation POTA/SOTA/IOTA/WWFF : ma référence sur chaque QSO, + réf.
  // correspondant si c'est un Park-to-Park / Summit-to-Summit.
  if(activationProgram && myActivationRef){
    qso.my_sig = activationProgram;
    qso.my_sig_info = myActivationRef;
    const tr = (document.getElementById('inputTheirRef')?.value || '').trim().toUpperCase();
    if(tr){ qso.sig = activationProgram; qso.sig_info = tr; }
  }

  // Mise à jour automatique de la base si nouvelles infos
  if(loc) updateCallDB(call, loc, null);

  // Envoi au serveur
  try{
    const res = await fetch('/log/add', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(qso)
    });
    if(res.ok){
      qsoLog.push(qso);
      bcBroadcast('add', qso);
      lastQsoTime = Date.now();
      if(esmMode) esmSend('tu');   // ESM : envoie « merci » à la validation
      // Vider le formulaire EN PREMIER (avant stats, avant tout)
      clearForm();
      document.getElementById('inputCall').focus();
      try{ renderLog(); }catch(e){ console.warn('renderLog',e); }
      try{ updateStats(); }catch(e){ console.warn('updateStats',e); }
      try{ updateLastQso(qso); }catch(e){}
      if(activationProgram) refreshActivation();   // MAJ immédiate du compteur d'activation
      playBeep(880, 80);
    } else if(res.status === 409){
      // Doublon détecté par le serveur : l'opérateur décide (2e période,
      // dupe assumé pour l'arbitre...) — confirm() volontairement bloquant.
      const err = await res.json();
      const ex = err.existing || {};
      if(confirm(`DOUBLON : ${qso.call} déjà contacté sur ${qso.band} MHz en ${qso.mode}`+
                 `${ex.time ? ' à '+ex.time : ''}${ex.operator ? ' par '+ex.operator : ''}.\n\n`+
                 `Enregistrer quand même ?`)){
        const res2 = await fetch('/log/add', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({...qso, force:true})
        });
        if(res2.ok){
          qsoLog.push(qso); bcBroadcast('add', qso); lastQsoTime = Date.now();
          clearForm(); document.getElementById('inputCall').focus();
          try{ renderLog(); }catch(e){} try{ updateStats(); }catch(e){}
          playBeep(880, 80);
        } else {
          notify('Erreur serveur : '+(await res2.json()).error);
        }
      } else {
        notify('Doublon ignoré — QSO non enregistré.');
      }
    } else {
      const err = await res.json();
      notify('Erreur serveur : '+err.error);
    }
  }catch(e){
    // Mode hors ligne : sauvegarde locale + localStorage
    qsoLog.push(qso);
    bcBroadcast('add', qso);
    lastQsoTime = Date.now();
    // Vider le formulaire EN PREMIER
    clearForm();
    document.getElementById('inputCall').focus();
    try{ renderLog(); }catch(ex){ console.warn('renderLog',ex); }
    try{ updateStats(); }catch(ex){ console.warn('updateStats',ex); }
    try{ updateLastQso(qso); }catch(ex){}
    playBeep(660, 120);
    // Stocker dans la file hors-ligne pour resync ultérieur
    let offlineQueue = [];
    try{ offlineQueue = JSON.parse(localStorage.getItem('rc_offline_queue')||'[]'); }catch(ex){}
    offlineQueue.push(qso);
    localStorage.setItem('rc_offline_queue', JSON.stringify(offlineQueue));
    console.warn(`Mode hors ligne, QSO sauvegardé localement (file: ${offlineQueue.length})`);
  }
}

function clearForm(){
  esmExchanged = false;   // ESM : nouveau QSO → l'échange sera à renvoyer
  clearTimeout(callLookupTimer);
  document.getElementById('inputCall').value = '';
  document.getElementById('inputCall').classList.remove('ok','error');
  document.getElementById('inputRSTsent').value = '59';
  document.getElementById('inputRSTrcvd').value = '59';
  document.getElementById('inputNumRcvd').value = '';
  document.getElementById('inputLocator').value = '';
  const _tr = document.getElementById('inputTheirRef'); if(_tr) _tr.value = '';
  setFreqForBand(currentBand);   // ré-affiche la fréquence d'appel/CAT de la bande
  document.getElementById('locHint').style.display = 'none';
  document.getElementById('dupWarn').classList.remove('show');
  const _cbh = document.getElementById('crossBandHint'); if(_cbh) _cbh.classList.remove('show');
  const _db = document.getElementById('dxccBadge'); if(_db) _db.style.display = 'none';
  const _pq = document.getElementById('prevQsos'); if(_pq) _pq.style.display = 'none';
  const _qz = document.getElementById('qrzInfo'); if(_qz) _qz.style.display = 'none';
  const _cs = document.getElementById('callStatusBadge'); if(_cs) _cs.style.display = 'none';
  hideCompassInline();
  if(currentExchange.auto_serial){
    updateSerialDisplay();
  } else if(currentExchange.clear_s){
    document.getElementById('inputNumSent').value = currentExchange.def_s || '';
  } else if(currentExchange.def_s){
    // Valeur fixe : toujours restaurer (ex: "1D DX" pour ARRL Field Day)
    document.getElementById('inputNumSent').value = currentExchange.def_s;
  }
}

// ─── AUDIO BIP CONFIRMATION QSO ──────────────────────────────────────────────
let bipEnabled = (localStorage.getItem('rc_bip') !== 'off');
(function initBipBtn(){
  const btn = document.getElementById('bipToggle');
  if(btn) btn.textContent = bipEnabled ? '🔔' : '🔕';
})();

function toggleBip(){
  bipEnabled = !bipEnabled;
  localStorage.setItem('rc_bip', bipEnabled ? 'on' : 'off');
  const btn = document.getElementById('bipToggle');
  if(btn) btn.textContent = bipEnabled ? '🔔' : '🔕';
}

// (playBeep défini plus haut — version unique avec _audioCtx réutilisé)

// ─── FETCH LOG DEPUIS SERVEUR ─────────────────────────────────────────────────
async function fetchLog(){
  try{
    const res = await fetch('/log/list');
    if(!res.ok) return;
    const data = await res.json();
    if(data.qsos){
      // Recalculer les sériaux — toujours le plus grand N° envoyé déjà utilisé,
      // jamais un simple comptage (sinon une suppression ou un trou fait reculer le compteur)
      const maxSerialByBand = {};
      data.qsos.forEach(q=>{
        const n = parseInt(q.num_sent, 10);
        if(!isNaN(n) && n > (maxSerialByBand[q.band]||0)) maxSerialByBand[q.band] = n;
      });
      Object.keys(maxSerialByBand).forEach(band=>{
        if(maxSerialByBand[band] > (serialByBand[band]||0)) serialByBand[band] = maxSerialByBand[band];
      });
      qsoLog = data.qsos;
      // Initialiser le timer depuis le dernier QSO logué
      if(qsoLog.length && !lastQsoTime){
        const last = qsoLog[qsoLog.length-1];
        try{
          const ms = new Date(`${last.date.slice(0,4)}-${last.date.slice(4,6)}-${last.date.slice(6,8)}T${last.time}:00Z`).getTime();
          if(!isNaN(ms)) lastQsoTime = ms;
        }catch(e){}
      }
      renderLog();
      updateStats();
      updateSerialDisplay();
    }
    // Status réseau
    const dot = document.getElementById('netDot');
    dot.className = 'net-dot online';
    document.getElementById('netStatus').textContent = 'Connecté au serveur';
    document.getElementById('netPeers').textContent = data.peers || '1';
    // Synchroniser la file hors-ligne si elle existe
    syncOfflineQueue();
  }catch(e){
    const dot = document.getElementById('netDot');
    dot.className = 'net-dot offline';
    document.getElementById('netStatus').textContent = 'Hors ligne — log local uniquement';
  }
}

async function syncOfflineQueue(){
  let queue = [];
  try{ queue = JSON.parse(localStorage.getItem('rc_offline_queue')||'[]'); }catch(e){}
  if(!queue.length) return;
  const synced = [];
  for(const qso of queue){
    try{
      // force:true : ces QSO ont déjà été validés à la saisie (mode hors
      // ligne) — le contrôle de doublon ne doit pas les faire disparaître.
      const res = await fetch('/log/add', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({...qso, force:true})
      });
      if(res.ok) synced.push(qso.id);
    }catch(e){ break; } // serveur encore inaccessible
  }
  if(synced.length){
    const remaining = queue.filter(q => !synced.includes(q.id));
    localStorage.setItem('rc_offline_queue', JSON.stringify(remaining));
    console.log(`[SYNC] ${synced.length} QSO hors-ligne synchronisés`);
    document.getElementById('netStatus').textContent = `Connecté — ${synced.length} QSO hors-ligne resynchronisés`;
  }
}

function backupLog(){
  if(!qsoLog.length) return;
  const now = new Date();
  const hhmm = `${String(now.getUTCHours()).padStart(2,'0')}:${String(now.getUTCMinutes()).padStart(2,'0')}`;
  localStorage.setItem('rc_log_backup', JSON.stringify(qsoLog));
  localStorage.setItem('rc_log_backup_time', hhmm+' UTC');
  const el = document.getElementById('backupTime');
  if(el) el.textContent = `Backup: ${hhmm} UTC`;
}

function startRefresh(){
  fetchLog();
  refreshTimer = setInterval(fetchLog, 5000); // refresh toutes les 5 secondes
  // Backup automatique toutes les 5 minutes
  backupLog(); // backup immédiat au démarrage
  setInterval(backupLog, 5 * 60 * 1000);
}

// Adresse de partage réelle (IP du serveur) : lien cliquable + copie.
// Lancée IMMÉDIATEMENT (pas après l'assistant de config) : un poste pas
// encore configuré doit déjà pouvoir afficher l'adresse aux autres.
function initShareLink(){
  fetch('/network/info').then(r=>r.json()).then(d=>{
    if(d.local_ip){
      const link = document.getElementById('shareLink');
      if(link){ link.href = d.url_logbook; link.textContent = d.url_logbook; }
      const sa = document.getElementById('serverAddr');
      if(sa) sa.textContent = window.location.host;
    }
  }).catch(()=>{ setTimeout(initShareLink, 10000); }); // serveur pas encore prêt
}
initShareLink();

function copyShareLink(){
  const url = document.getElementById('shareLink')?.href || '';
  if(!url || url.endsWith('#')){ notify('Adresse pas encore disponible — serveur injoignable ?'); return; }
  navigator.clipboard.writeText(url)
    .then(()=>notify(`📋 Adresse copiée : ${url}\nColle-la dans le navigateur des autres postes (même WiFi).`))
    .catch(()=>prompt('Copie manuelle (Ctrl+C) :', url));
}

// ─── RENDER LOG ───────────────────────────────────────────────────────────────
// QSO incomplet = champ critique manquant (souvent dû à une coupure réseau ou
// un souci pendant la saisie) — jamais supprimé automatiquement, seulement
// signalé pour correction manuelle via le bouton ✏️.
function isValidQSO(q){
  return !!(q.call && q.mode && q.time && q.date && q.rst_sent && q.rst_rcvd);
}

function setFilter(el){
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
  el.classList.add('active');
  currentFilter = el.dataset.f;
  renderLog();
}

function filterLog(){
  renderLog();
}

function renderLog(){
  const search = document.getElementById('logSearch').value.toUpperCase();
  const tbody = document.getElementById('logBody');

  let filtered = qsoLog.filter(q=>{
    if(currentFilter==='144' && q.band!=='144') return false;
    if(currentFilter==='432' && q.band!=='432') return false;
    if(currentFilter==='hf' && !['14','7','3.5','1.8','21','28'].includes(q.band)) return false;
    if(currentFilter==='mine' && q.operator!==myOp) return false;
    if(search && !(q.call||'').includes(search) && !(q.locator||'').includes(search)) return false;
    return true;
  });

  const incompleteCount = qsoLog.filter(q=>!isValidQSO(q)).length;
  document.getElementById('logCount').textContent = incompleteCount
    ? `${filtered.length} QSO — ⚠️ ${incompleteCount} incomplet(s)`
    : `${filtered.length} QSO`;

  // Rafraîchir la carte si elle est visible
  if(document.getElementById('mapWrap').classList.contains('visible')) refreshMapLayers();

  tbody.innerHTML = filtered.slice().reverse().map((q,i)=>{
    const opClass = OP_COLORS[q.operator] || '';
    const isDupQ = qsoLog.filter(x=>x.call===q.call&&x.band===q.band).length > 1;
    const incomplete = !isValidQSO(q);
    const distColor = q.dist>1000?'#FF6B00':q.dist>500?'#FFD60A':q.dist>200?'#A0C0FF':'#506090';
    const _brg = (q.locator&&q.locator.length>=6) ? bearing(q.locator) : null;
    const cap = _brg !== null ? cardinalDir(_brg) : '—';
    const rowClass = [isDupQ?'dup-entry':'', q._new?'new-entry':'', incomplete?'incomplete-entry':''].filter(Boolean).join(' ');
    return `<tr class="${rowClass}" id="qso_${q.id}" ondblclick="editQSO(${q.id})" title="Double-clic pour corriger ce QSO">
      <td class="td-num">${incomplete?'<span class=\"incomplete-flag\" title=\"QSO incomplet — champ(s) manquant(s), à corriger\">⚠️</span>':''}${qsoLog.indexOf(q)+1}</td>
      <td class="td-time">${q.time||'—'}</td>
      <td class="td-call">${q.call||'—'}</td>
      <td class="td-band"${q.freq?` title="${escHtml(q.freq)} MHz"`:''}>${BAND_LABELS[q.band]||escHtml(q.band)||'—'}${q.freq?`<span style="display:block;font-size:10px;color:var(--muted);font-weight:400">${escHtml(q.freq)}</span>`:''}</td>
      <td class="td-mode">${q.mode||'—'}</td>
      <td class="td-sent">${q.rst_sent||'—'}/${q.num_sent||'—'}</td>
      <td class="td-rcvd">${q.rst_rcvd||'—'}/${q.num_rcvd||'—'}</td>
      <td class="td-loc">${q.locator||'—'}</td>
      <td style="color:${distColor};font-weight:700;font-size:15px">${q.dist?q.dist+' km':'—'}${cap!=='—'?' '+cap:''}</td>
      <td class="td-pts">${q.points||'—'}</td>
      <td><span class="td-op ${opClass}">${q.operator||'—'}</span></td>
      <td class="td-edit" onclick="editQSO(${q.id})" title="Corriger">✏️</td>
      <td class="td-del" onclick="deleteQSO(${q.id})" title="Supprimer">✕</td>
    </tr>`;
  }).join('');
}

function updateLastQso(q){
  const list = document.getElementById('lastQsoList');
  const div = document.createElement('div');
  div.className = 'last-qso-item';
  div.innerHTML = `
    <span class="lqi-call">${q.call}</span>
    <span class="lqi-loc">${q.locator||'—'}</span>
    <span class="lqi-pts">${q.points||0} pts</span>
    <span class="lqi-op">${q.operator}</span>
  `;
  list.insertBefore(div, list.firstChild);
  if(list.children.length > 5) list.removeChild(list.lastChild);
}

// ─── ÉDITION QSO ─────────────────────────────────────────────────────────────
function editQSO(id){
  const q = qsoLog.find(x=>x.id===id);
  if(!q) return;
  document.getElementById('editId').value = id;
  document.getElementById('editCall').value = q.call||'';
  document.getElementById('editDate').value = q.date||'';
  document.getElementById('editTime').value = q.time||'';
  document.getElementById('editRSTsent').value = q.rst_sent||'';
  document.getElementById('editNumSent').value = q.num_sent||'';
  document.getElementById('editRSTrcvd').value = q.rst_rcvd||'';
  document.getElementById('editNumRcvd').value = q.num_rcvd||'';
  // Peupler le select bande avec les bandes du concours
  const editBandSel = document.getElementById('editBand');
  const contestBands = CONTEST_BANDS[currentContest] || ALL_BANDS;
  editBandSel.innerHTML = contestBands.map(b =>
    `<option value="${b}"${b===q.band?' selected':''}>${BAND_LABELS[b]||b+' MHz'}</option>`
  ).join('');
  if(!editBandSel.value) editBandSel.value = q.band; // fallback si bande hors concours
  // Peupler le select mode avec les modes du concours
  const editModeSel = document.getElementById('editMode');
  const contestModes = CONTEST_MODES[currentContest] || ['SSB','CW','FM','FT8','FT4','RTTY'];
  editModeSel.innerHTML = contestModes.map(m =>
    `<option value="${m}"${m===q.mode?' selected':''}>${m}</option>`
  ).join('');
  if(!editModeSel.value) editModeSel.value = q.mode;
  document.getElementById('editLocator').value = q.locator||'';
  updateEditDistInfo(q.locator);
  document.getElementById('editLocator').addEventListener('input', function(){
    updateEditDistInfo(this.value.toUpperCase());
    this.value = this.value.toUpperCase();
  });
  document.getElementById('editOverlay').classList.add('show');
  document.getElementById('editCall').focus();
}

function updateEditDistInfo(loc){
  const info = document.getElementById('editDistInfo');
  if(loc && loc.length===6){
    const dist = calcDist(loc);
    const pts = calcPoints(loc, document.getElementById('editBand').value||currentBand);
    if(dist>0){
      info.textContent = `📏 Distance : ${dist} km → 🏆 ${pts} pts`;
      info.style.display = 'block';
    }
  } else {
    info.style.display = 'none';
  }
}

function closeEdit(){
  document.getElementById('editOverlay').classList.remove('show');
}

async function saveEdit(){
  const id = parseInt(document.getElementById('editId').value);
  const q = qsoLog.find(x=>x.id===id);
  if(!q) return;

  const newCall = document.getElementById('editCall').value.trim().toUpperCase();
  const newLoc  = document.getElementById('editLocator').value.trim().toUpperCase();
  const newBand = document.getElementById('editBand').value;
  const newDate = document.getElementById('editDate').value.trim() || nowDateUTC();
  const newTime = document.getElementById('editTime').value.trim() || nowUTC();

  if(!newCall){ notify('Indicatif manquant !'); return; }
  if(!/^\d{8}$/.test(newDate)){ notify('Date invalide !\nFormat attendu : AAAAMMJJ (ex: 20260705)'); return; }
  if(!/^\d{1,2}:\d{2}$/.test(newTime)){ notify('Heure invalide !\nFormat attendu : HH:MM (ex: 14:32)'); return; }

  const dist = calcDist(newLoc);
  const newMode = document.getElementById('editMode')?.value || q.mode || 'SSB';
  const pts  = newLoc ? calcPoints(newLoc, newBand, newCall, newMode) : 0;

  // Mise à jour locale
  Object.assign(q, {
    call: newCall,
    date: newDate,
    time: newTime,
    rst_sent: document.getElementById('editRSTsent').value.trim()||'59',
    num_sent: document.getElementById('editNumSent').value.trim(),
    rst_rcvd: document.getElementById('editRSTrcvd').value.trim()||'59',
    num_rcvd: currentExchange.pad_r === true
      ? (v=>v?String(parseInt(v,10)||0).padStart(3,'0'):'')(document.getElementById('editNumRcvd').value.trim())
      : document.getElementById('editNumRcvd').value.trim(),
    band: newBand,
    mode: document.getElementById('editMode').value,
    locator: newLoc,
    dist, points: pts,
    _edited: true,
  });

  // Envoi au serveur
  try{
    await fetch('/log/update', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(q)
    });
  }catch(e){ console.warn('Serveur hors ligne, correction locale uniquement'); }

  closeEdit();
  renderLog();
  updateStats();
}

async function deleteQSO(id){
  if(!confirm('Supprimer ce QSO ?')) return;
  qsoLog = qsoLog.filter(q=>q.id!==id);
  try{
    await fetch(`/log/delete/${id}`, {method:'DELETE'});
  }catch(e){}
  renderLog();
  updateStats();
  bcBroadcast('delete', {id});
}

async function undoLastQSO(){
  if(!qsoLog.length){ notify('Aucun QSO à annuler !'); return; }
  const last = qsoLog[qsoLog.length-1];
  if(!confirm(`Annuler le dernier QSO ?\n${last.call} — ${last.band} MHz — ${last.time}`)) return;
  qsoLog = qsoLog.slice(0,-1);
  try{
    await fetch(`/log/delete/${last.id}`, {method:'DELETE'});
  }catch(e){}
  renderLog();
  updateStats();
}

// ─── STATS ───────────────────────────────────────────────────────────────────
// Concours VHF/UHF — affichage 144/432
const VHF_CONTESTS = new Set(['REF_RPH','REF_QRP','REF_CCD','REF_VHF_UHF_FR',
  'IARU_VHF','IARU_UHF','EU_VHF','DARC_VHF','OARC_VHF']);

function updateStats(){
  const isVHF = VHF_CONTESTS.has(currentContest);

  // ── Recalculer points dynamiquement selon le concours actif ─────────────
  let total = 0;
  qsoLog.forEach(q => {
    if(q.locator && q.locator.length >= 6){
      total += calcPoints(q.locator, q.band, q.call, q.mode);
    } else if(q.points && q.points > 0){
      total += q.points; // fallback sur valeur stockée si pas de locator
    } else if(!isVHF){
      // Pour les concours HF sans locator : 1 pt/QSO SSB, 2 pts/QSO CW ou digital
      total += (q.mode === 'CW' || q.mode === 'FT8' || q.mode === 'FT4' || q.mode === 'RTTY') ? 2 : 1;
    }
  });

  const dups = qsoLog.filter((q,i)=>qsoLog.findIndex(x=>x.call===q.call&&x.band===q.band)<i).length;

  // ── Label et valeur QSO selon type de concours ───────────────────────────
  let qsoLbl, qsoVal;
  if(isVHF){
    const q144 = qsoLog.filter(q=>q.band==='144').length;
    const q432 = qsoLog.filter(q=>q.band==='432').length;
    qsoLbl = 'QSO 144 / 432';
    qsoVal = `${q144} / ${q432}`;
  } else {
    // HF : afficher le total + top 3 bandes utilisées
    const byBand = {};
    qsoLog.forEach(q => { byBand[q.band] = (byBand[q.band]||0) + 1; });
    const bandSummary = Object.entries(byBand)
      .sort((a,b) => b[1]-a[1])
      .slice(0,4)
      .map(([b,n]) => `${BAND_LABELS[b]||b}×${n}`)
      .join(' ');
    qsoLbl = `QSO TOTAL`;
    qsoVal = qsoLog.length > 0 ? `${qsoLog.length}  ${bandSummary}` : '0';
  }

  // ── Multiplicateurs ───────────────────────────────────────────────────────
  let multsVal, multsLbl;
  if(isVHF){
    multsLbl = 'LOCATORS UNIQUES';
    multsVal = new Set(qsoLog.map(q=>q.locator).filter(l=>l&&l.length>=6)).size;
  } else {
    // HF concours : multiplicateurs = indicatifs uniques ou sections uniques
    const sections = new Set(qsoLog.map(q=>q.num_rcvd).filter(Boolean));
    multsLbl = sections.size > 0 ? 'SECTIONS / MULTS' : 'LOCATORS UNIQUES';
    multsVal = sections.size || new Set(qsoLog.map(q=>q.locator).filter(Boolean)).size;
  }

  // ── Meilleur DX (recalculé live depuis locators) ─────────────────────────
  let bestDist = 0, bestCall = '—';
  qsoLog.forEach(q => {
    if(q.locator && q.locator.length >= 6){
      const d = calcDist(q.locator);
      if(d > bestDist){ bestDist = d; bestCall = q.call; }
    }
  });
  const bestDXstr = bestDist > 0 ? `${bestDist} km — ${bestCall}` : '—';

  // ── Taux QSO/h — fenêtre glissante 60 min + projection ───────────────────
  let rateStr = '— · —';
  const parseT = q => {
    const d = q.date; const t = q.time;
    return new Date(`${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}T${t}:00Z`).getTime();
  };
  if(qsoLog.length >= 2){
    const nowMs = Date.now();
    const win60 = qsoLog.filter(q => { try{ return (nowMs - parseT(q)) <= 3600000; }catch(e){return false;} }).length;
    const remaining = Math.max(0, (contestEndUTC - nowMs) / 3600000);
    const proj = Math.round(qsoLog.length + win60 * remaining);
    const rateEl = document.getElementById('sbRate');
    rateEl.style.color = win60 >= 30 ? 'var(--green)' : win60 >= 15 ? 'var(--yellow)' : 'var(--purple)';
    rateStr = `${win60}/h · ~${proj}`;
  }

  document.getElementById('sbQsoLbl').textContent  = qsoLbl;
  document.getElementById('sbTotal').textContent   = total.toLocaleString() + ' pts';
  document.getElementById('sbQso').textContent     = qsoVal;
  document.getElementById('sbBestDX').textContent  = bestDXstr;
  document.getElementById('sbMults').textContent   = multsVal;
  document.getElementById('sbMultsLbl').textContent  = multsLbl;
  document.getElementById('sbRate').textContent    = rateStr;
  document.getElementById('sbDups').textContent    = dups;
  updateBandRecap();
  drawHourChart();
  updateOpStats();
}

// ─── CLASSEMENT OPÉRATEURS (multi-op) ─────────────────────────────────────────
function updateOpStats(){
  const bar   = document.getElementById('opStatsBar');
  const inner = document.getElementById('opStatsInner');
  if(!bar || !inner) return;

  const opsUsed = new Set(qsoLog.map(q=>q.operator).filter(Boolean));
  if(opsUsed.size < 2){ bar.style.display = 'none'; return; }

  const stats = {};
  qsoLog.forEach(q=>{
    const op = q.operator || '—';
    if(!stats[op]) stats[op] = {count:0, pts:0};
    stats[op].count++;
    stats[op].pts += q.points || 0;
  });

  const sorted = Object.entries(stats).sort((a,b)=>b[1].pts-a[1].pts);
  const topPts = sorted.length ? sorted[0][1].pts : 0;
  inner.innerHTML = sorted.map(([op, d])=>{
    const opClass = OP_COLORS[op] || '';
    const isLeader = d.pts === topPts && topPts > 0;
    return `<div class="ops-item${isLeader?' leader':''}">`
      + `<div class="ops-op ${opClass}" style="border-radius:4px;display:inline-block;padding:1px 8px">${op}${isLeader?' 🏆':''}</div>`
      + `<div class="ops-lbl">QSO · PTS</div>`
      + `<div class="ops-vals">${d.count} · ${d.pts.toLocaleString()}</div>`
      + `</div>`;
  }).join('');
  bar.style.display = 'block';
}

// ─── RÉCAP PAR BANDE ─────────────────────────────────────────────────────────
function updateBandRecap(){
  const bar   = document.getElementById('bandRecapBar');
  const inner = document.getElementById('bandRecapInner');
  if(!bar || !inner) return;
  if(qsoLog.length === 0){ bar.style.display = 'none'; return; }

  const bands = {};
  qsoLog.forEach(q => {
    const b = q.band || '?';
    if(!bands[b]) bands[b] = {count:0, totalKm:0, maxKm:0, bestCall:'—', bestBear:'—'};
    const km = (q.locator && q.locator.length >= 6) ? calcDist(q.locator) : 0;
    bands[b].count++;
    bands[b].totalKm += km;
    if(km > bands[b].maxKm){
      bands[b].maxKm   = km;
      bands[b].bestCall = q.call || '—';
      if(q.locator && q.locator.length >= 6){ const brg = bearing(q.locator); if(brg !== null) bands[b].bestBear = cardinalDir(brg); }
    }
  });

  const sortedBands = Object.keys(bands).sort((a,b) => (parseFloat(a)||0) - (parseFloat(b)||0));
  inner.innerHTML = '';
  sortedBands.forEach(b => {
    const d   = bands[b];
    const lbl = BAND_LABELS[b] || `${b} MHz`;
    const div = document.createElement('div');
    div.className = 'brd-item';
    div.innerHTML =
      `<div class="brd-band">${lbl}</div>` +
      `<div class="brd-lbl">QSO · KM TOTAL · DX MAX</div>` +
      `<div class="brd-vals">${d.count} · ${Math.round(d.totalKm).toLocaleString()} km · <span class="brd-dx">${Math.round(d.maxKm)} km</span></div>` +
      `<div class="brd-vals" style="color:var(--muted);font-size:12px">${d.bestCall} ${d.bestBear}</div>`;
    inner.appendChild(div);
  });
  bar.style.display = 'block';
}

// ─── GRAPHE QSO/HEURE (sparkline SVG inline) ─────────────────────────────────
function drawHourChart(){
  const bar  = document.getElementById('hourChartBar');
  const svg  = document.getElementById('hourChartSvg');
  const peak = document.getElementById('hourChartPeak');
  if(!bar || !svg) return;
  if(qsoLog.length === 0){ bar.style.display = 'none'; return; }

  // Grouper par heure UTC (clé = "YYYYMMDD-HH")
  const buckets = {};
  qsoLog.forEach(q => {
    if(!q.date || !q.time) return;
    const key = q.date + '-' + q.time.slice(0,2);
    buckets[key] = (buckets[key]||0) + 1;
  });
  const keys = Object.keys(buckets).sort();
  if(keys.length === 0){ bar.style.display = 'none'; return; }

  const maxVal = Math.max(...Object.values(buckets));
  // Heure courante UTC pour surligner la barre active
  const now = new Date();
  const nowKey = now.toISOString().slice(0,8).replace(/-/g,'') + '-' + now.toISOString().slice(11,13);

  // Dimensions SVG en unités viewBox
  const VW = 1000, VH = 40;
  const n = keys.length;
  const gap = 1;
  const bw = Math.floor((VW - gap * (n - 1)) / n);

  let markup = '';
  let bestHour = '', bestCount = 0;
  keys.forEach((k, i) => {
    const count = buckets[k];
    const x = i * (bw + gap);
    const barH = Math.max(3, Math.round((count / maxVal) * (VH - 10)));
    const y = VH - barH;
    const isCurrent = (k === nowKey);
    const col = isCurrent ? '#ffffff'
              : count >= 20 ? 'var(--green)'
              : count >= 10 ? 'var(--yellow)'
              : count >=  5 ? '#FF8C00'
              : 'var(--accent2)';
    const hh = k.slice(-2); // "HH"
    markup += `<rect x="${x}" y="${y}" width="${bw}" height="${barH}" fill="${col}" rx="1" opacity="${isCurrent?1:.85}">`;
    markup += `<title>${hh}:00 UTC — ${count} QSO</title></rect>`;
    // Étiquette heure toutes les 3h ou si n≤12
    if(n <= 12 || parseInt(hh,10) % 3 === 0){
      markup += `<text x="${x+bw/2}" y="${VH+7}" text-anchor="middle" font-size="10" font-family="monospace" fill="var(--muted)">${hh}</text>`;
    }
    // Valeur sur barre haute
    if(count === maxVal || count >= 10){
      markup += `<text x="${x+bw/2}" y="${y-2}" text-anchor="middle" font-size="10" font-family="monospace" fill="${col}">${count}</text>`;
    }
    if(count > bestCount){ bestCount = count; bestHour = hh + ':00'; }
  });

  // Ligne objectif de taux (20 QSO/h)
  const TARGET_RATE = 20;
  if(maxVal > 0 && TARGET_RATE <= maxVal){
    const ty = Math.round(VH - (TARGET_RATE / maxVal) * (VH - 10));
    markup += `<line x1="0" y1="${ty}" x2="${VW}" y2="${ty}" stroke="rgba(255,214,10,.55)" stroke-width="1.5" stroke-dasharray="8,5"/>`;
    markup += `<text x="${VW-2}" y="${ty-2}" text-anchor="end" font-size="6.5" font-family="monospace" fill="rgba(255,214,10,.8)">${TARGET_RATE}/h</text>`;
  }
  svg.setAttribute('viewBox', `0 0 ${VW} ${VH + 10}`);
  svg.innerHTML = markup;
  if(peak) peak.textContent = `PEAK ${bestHour} UTC — ${bestCount} QSO/h`;
  bar.style.display = 'block';
}

// ─── SOAPBOX PAR BANDE ───────────────────────────────────────────────────────
const SOAPBOX_BANDS = ['144','432','1296'];
function toggleSoapbox(){
  const title  = document.getElementById('soapboxToggle');
  const fields = document.getElementById('soapboxFields');
  if(!title || !fields) return;
  const collapsed = title.classList.toggle('collapsed');
  fields.classList.toggle('hidden', collapsed);
}
function saveSoapbox(){
  const data = {};
  SOAPBOX_BANDS.forEach(b => {
    const el = document.getElementById(`soap_${b}`);
    if(el) data[b] = el.value;
  });
  localStorage.setItem('radiocontest_soapbox', JSON.stringify(data));
}
function loadSoapbox(){
  try{
    const data = JSON.parse(localStorage.getItem('radiocontest_soapbox')||'{}');
    SOAPBOX_BANDS.forEach(b => {
      const el = document.getElementById(`soap_${b}`);
      if(el && data[b]) el.value = data[b];
    });
  }catch(e){}
}
function getSoapbox(band){
  try{
    const data = JSON.parse(localStorage.getItem('radiocontest_soapbox')||'{}');
    return (data[band]||'').trim();
  }catch(e){ return ''; }
}

// ─── MACROS F1–F8 ────────────────────────────────────────────────────────────
const DEFAULT_MACROS = [
  {key:'F1', label:'CQ RPH',   text:'CQ RPH {CALL} {CALL}'},
  {key:'F2', label:'ÉCHANGE',  text:'59 {NR} {LOC}'},
  {key:'F3', label:'TU',       text:'TU {CALL} TEST'},
  {key:'F4', label:'QSY 432?', text:'QSY 432.200?'},
  {key:'F5', label:'LOCATOR',  text:'{LOC} {LOC}'},
  {key:'F6', label:'?',        text:'{CALL}?'},
  {key:'F7', label:'AGN?',     text:'AGN?'},
  {key:'F8', label:'73',       text:'73 {CALL}'},
];
function getMacros(){ try{ const s=localStorage.getItem('radiocontest_macros'); return s?JSON.parse(s):DEFAULT_MACROS; }catch(e){ return DEFAULT_MACROS; } }
function saveMacros(m){ localStorage.setItem('radiocontest_macros', JSON.stringify(m)); }
function expandMacro(text){
  const cfg = JSON.parse(localStorage.getItem('radiocontest_config')||'{}');
  const call = cfg.callsign || myCall || '—';
  const loc  = cfg.locator  || myLocator || '—';
  const nr   = String(qsoLog.length + 1).padStart(3,'0');
  return text.replace(/{CALL}/g,call).replace(/{LOC}/g,loc).replace(/{NR}/g,nr);
}
function renderMacroPanel(){
  const btns = document.getElementById('macroBtns');
  if(!btns) return;
  const macros = getMacros();
  btns.innerHTML = '';
  macros.forEach((m, idx) => {
    const btn = document.createElement('button');
    btn.className = 'macro-btn';
    btn.title = expandMacro(m.text);
    btn.innerHTML = `<span class="mk">${m.key}</span><span class="mt">${m.label}</span>`;
    btn.onclick    = e => { e.stopPropagation(); copyMacro(idx); };
    btn.ondblclick = e => { e.stopPropagation(); editMacro(idx); };
    btns.appendChild(btn);
  });
}
// Notification non bloquante — remplace notify() pour ne jamais figer la saisie
// en plein concours. Couleur selon le contenu, durée selon la longueur.
function notify(msg, ms){
  const t = document.getElementById('macroToast');
  if(!t){ alert(msg); return; }   // repli improbable
  msg = String(msg);
  t.textContent = msg;
  t.className = 'macro-toast';
  if(/❌|[Ee]rreur|[Ii]nvalide|manquant|[Ii]mpossible|injoignable/.test(msg)) t.classList.add('toast-err');
  else if(/⚠|[Aa]nnulé/.test(msg)) t.classList.add('toast-warn');
  t.classList.add('show');
  clearTimeout(notify._tm);
  notify._tm = setTimeout(()=>t.classList.remove('show'), ms || Math.min(10000, 2500 + msg.length*35));
}

function copyMacro(idx){
  const m = getMacros()[idx]; if(!m) return;
  const txt = expandMacro(m.text);
  // Radio en CW + pilotage actif → la macro part directement par le keyer
  // de la radio ; sinon (SSB/RTTY, ou pas de CAT) on copie dans le presse-papier.
  if(rigState.enabled && /CW/i.test(rigState.mode || currentMode)){
    fetch('/rig/cw', {method:'POST', headers:{'Content-Type':'application/json'},
                      body: JSON.stringify({text: txt})})
      .then(r=>r.json()).then(d=>{
        const toast = document.getElementById('macroToast');
        if(toast){ toast.textContent = d.ok ? `📻 CW → ${txt}` : `❌ ${d.error}`;
          toast.className = 'macro-toast' + (d.ok ? '' : ' toast-err');
          toast.classList.add('show'); setTimeout(()=>toast.classList.remove('show'), 2200); }
      }).catch(()=>{});
    return;
  }
  navigator.clipboard.writeText(txt).catch(()=>{});
  const toast = document.getElementById('macroToast');
  if(toast){ toast.textContent = `📋 ${txt}`; toast.classList.add('show'); setTimeout(()=>toast.classList.remove('show'), 2000); }
}

// ─── RADIO CAT (rigctld) ─────────────────────────────────────────────────────
// Widget état radio (fréq/mode) + envoi CW des macros. Actif uniquement si le
// pilotage est activé dans CONFIG. Sondage doux (3 s) ; tolère l'absence de radio.
let rigState = {enabled:false, mode:'', freq_khz:0};

function refreshRig(){
  fetch('/rig/state').then(r=>r.ok?r.json():null).then(d=>{
    const panel = document.getElementById('rigPanel');
    const freqBtn = document.getElementById('freqRigBtn');
    if(!d || !d.enabled){ rigState.enabled=false; if(panel) panel.style.display='none'; if(freqBtn) freqBtn.style.display='none'; return; }
    rigState.enabled = true;
    if(panel) panel.style.display = 'block';
    if(freqBtn) freqBtn.style.display = '';
    const dot = document.getElementById('rigDot');
    if(d.ok){
      rigState.mode = d.mode; rigState.freq_khz = d.freq_khz;
      document.getElementById('rigFreq').textContent = d.freq_khz.toFixed(1) + ' kHz';
      document.getElementById('rigMode').textContent = d.mode || '—';
      if(dot) dot.classList.add('on');
      // Suivi automatique : la bande/le mode de saisie suivent la radio
      syncBandModeFromRig(d.freq_khz, d.mode);
      // La fréquence suit la radio en direct, SAUF si l'opérateur est en train de
      // la saisir ou l'a saisie manuellement (split, annonce) → on ne l'écrase pas.
      const fEl = document.getElementById('inputFreq');
      if(fEl && d.freq_khz > 0 && document.activeElement !== fEl && !fEl.dataset.userEdited)
        fEl.value = (d.freq_khz / 1000).toFixed(3);
      if(typeof updateKeyerPanels==='function') updateKeyerPanels();
    } else {
      document.getElementById('rigFreq').textContent = 'rigctld injoignable';
      document.getElementById('rigMode').textContent = '';
      if(dot) dot.classList.remove('on');
    }
  }).catch(()=>{});
}

function syncBandModeFromRig(freqKhz, mode){
  // Fréquence radio → bande interne (bornes larges pour les segments contest)
  const mhz = freqKhz / 1000;
  const BANDS = [[1.8,2,'1.8'],[3.5,4,'3.5'],[7,7.3,'7'],[14,14.35,'14'],
                 [21,21.45,'21'],[28,29.7,'28'],[50,54,'50'],[144,148,'144'],[430,440,'432']];
  for(const [lo,hi,b] of BANDS){
    if(mhz>=lo && mhz<=hi){
      if(typeof currentBand!=='undefined' && currentBand!==b){
        const btn = document.querySelector(`.bm-btn[data-val="${b}"]`);
        if(btn) setBand(btn);
      }
      break;
    }
  }
}

function rigStopCW(){
  fetch('/rig/stop', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'}).catch(()=>{});
}

refreshRig();
setInterval(refreshRig, 3000);

// ─── ROTOR (rotctld) ─────────────────────────────────────────────────────────
// Sonde l'état pour savoir si le pilotage est actif (affiche le bouton
// « pointer » sous la boussole) ; le pointage réel se fait à la demande.
let rotorState = {enabled:false};
function refreshRotor(){
  fetch('/rotor/state').then(r=>r.ok?r.json():null).then(d=>{
    rotorState.enabled = !!(d && d.enabled);
  }).catch(()=>{ rotorState.enabled = false; });
}
refreshRotor();
setInterval(refreshRotor, 15000);

// ─── MÉTÉO DU POINT HAUT (sécurité matériel /P) ──────────────────────────────
function refreshWeather(){
  fetch('/data/weather').then(r=>r.ok?r.json():null).then(d=>{
    const el = document.getElementById('weatherWidget');
    if(!el || !d || !d.ok){ if(el) el.style.display='none'; return; }
    el.style.display = '';
    el.innerHTML = `${d.icon} ${d.temp}°C · 💨 ${d.wind}` +
      (d.gust >= d.wind + 10 ? `/${d.gust}` : '') + ` km/h` +
      (d.precip > 0 ? ` · 🌧️ ${d.precip}mm` : '') +
      (d.warn ? ` <b style="color:var(--red)">${d.warn}</b>` : '');
    el.style.color = d.warn ? 'var(--red)' : 'var(--muted)';
  }).catch(()=>{});
}
refreshWeather();
setInterval(refreshWeather, 10 * 60 * 1000);   // cache serveur 10 min

// ─── PONT WSJT-X (FT8/FT4) ───────────────────────────────────────────────────
// Indicateur de liaison + rafraîchissement du log quand un QSO est auto-loggé.
let _wsjtxLastTotal = -1;
function refreshWsjtx(){
  fetch('/wsjtx/state').then(r=>r.ok?r.json():null).then(d=>{
    const el = document.getElementById('wsjtxWidget');
    if(!el || !d || !d.enabled){ if(el) el.style.display='none'; return; }
    el.style.display = '';
    if(d.connected){
      el.innerHTML = `💻 WSJT-X <b style="color:var(--green)">●</b> ${d.dial_mhz||''} MHz ${d.mode||''} · ${d.logged_total||0} auto-loggés`;
      el.style.color = 'var(--muted)';
    } else {
      el.innerHTML = `💻 WSJT-X <b style="color:var(--red)">○</b> en attente (port ${d.port})`;
      el.style.color = 'var(--muted)';
    }
    // Un nouveau QSO auto-loggé → recharger la table du log
    if(_wsjtxLastTotal >= 0 && (d.logged_total||0) > _wsjtxLastTotal){
      try{ fetchLog(); playBeep && playBeep(1046, 90); }catch(e){}
    }
    _wsjtxLastTotal = d.logged_total || 0;
  }).catch(()=>{});
}
refreshWsjtx();
setInterval(refreshWsjtx, 4000);
function editMacro(idx){
  const macros = getMacros();
  const m = macros[idx];
  const newLabel = prompt(`Label pour ${m.key} :`, m.label);
  if(newLabel === null) return;
  const newText = prompt(`Message ({CALL} {LOC} {NR}) :`, m.text);
  if(newText === null) return;
  macros[idx] = {...m, label:newLabel.trim()||m.label, text:newText.trim()||m.text};
  saveMacros(macros); renderMacroPanel();
}

// ─── EXPORTS ─────────────────────────────────────────────────────────────────
function exportEDI(){
  // Validation avant export
  const warnings = [];
  const invalid = qsoLog.filter(q=>!isValidQSO(q));
  if(invalid.length) warnings.push(`⚠️ ${invalid.length} QSO incomplet(s) ignoré(s) (${invalid.map(q=>q.call||'?').join(', ')})`);
  const missingLoc = qsoLog.filter(q=>isValidQSO(q) && (!q.locator||q.locator.length<6));
  if(missingLoc.length) warnings.push(`⚠️ ${missingLoc.length} QSO sans locator (points = 0)`);
  const dups = qsoLog.filter((q,i)=>qsoLog.findIndex(x=>x.call===q.call&&x.band===q.band)<i).length;
  if(dups) warnings.push(`⚠️ ${dups} doublon(s) dans le log`);
  if(warnings.length){
    if(!confirm('VALIDATION LOG\n\n'+warnings.join('\n')+'\n\nGénérer quand même le fichier EDI ?')) return;
  }

  // Lire config depuis localStorage
  let ediCfg = {};
  try{ ediCfg = JSON.parse(localStorage.getItem('radiocontest_config')||'{}'); }catch(e){}
  const ediCall    = ediCfg.callsign || myCall || 'F6KQJ';
  const ediLocator = ediCfg.locator  || myLocator || '';
  const ediClub    = ediCfg.club     || ediCfg.callsign || 'F6KQJ';
  const ediRName   = ediCfg.op_name  || 'Opérateur';
  const ediRCall   = ediCfg.op_call  || ediCall;
  const ediCity    = ediCfg.city     || '';
  const ediPostal  = ediCfg.postal   || '';
  const ediAltitude= ediCfg.altitude || '';
  const ediDept    = ediPostal.length>=2 ? ediPostal.slice(0,2) : '';
  const ediEmail   = ediCfg.email    || '';
  const ediPower   = ediCfg.power    || '100';
  const ediRadio   = ediCfg.radio    || 'IC-9700';
  const ediCountry = ediCfg.country  || 'FRA';
  const ediAnt144  = ediCfg.ant_144  || 'Yagi';
  const ediAnt432  = ediCfg.ant_432  || 'Yagi';
  // Tous les opérateurs réels (multi-op) — MOpe1/MOpe2 = format EDI (2 slots max),
  // la liste complète est aussi rappelée dans les Remarks pour ne perdre personne.
  const ediOpList  = (ediCfg.operators||[]).map(o=>o.call).filter(Boolean);
  const ediMOpe1   = ediOpList[0] || ediRCall;
  const ediMOpe2   = ediOpList[1] || '';
  // Dates du concours
  const TDATE_START = (ediCfg.contest_start_date||'20260704').replace(/-/g,'');
  const TDATE_END   = (ediCfg.contest_end_date  ||'20260705').replace(/-/g,'');
  const totalScore  = qsoLog.reduce((s,q)=>s+(q.points||0),0);

  // Détecter si concours HF → Cabrillo, VHF/UHF → EDI
  const HF_CONTESTS = ['ARRL_FD','ARRL_DX_SSB','ARRL_DX_CW','CQ_WW_SSB','CQ_WW_CW',
                        'CQ_WPX_SSB','CQ_WPX_CW','REF_CDF_HF_SSB','REF_CDF_HF_CW',
                        'IARU_HF','WAE_CW','WAE_SSB'];
  const isHFContest = HF_CONTESTS.includes(currentContest);

  if(isHFContest){
    exportCabrillo(ediCfg, myCall);
    return;
  }

  const VHF_UHF_SHF_BANDS = ['144','432','1296','2320','3400','5760','10368','24048','47088'];
  const bands = [...new Set(qsoLog.map(q=>q.band))].filter(b=>VHF_UHF_SHF_BANDS.includes(b));
  if(!bands.length){ notify('Aucun QSO VHF/UHF à exporter !\n\nPour les concours HF (ARRL FD, CQ WW, etc.),\nle format Cabrillo sera généré automatiquement.'); return; }

  // Téléchargements espacés dans le temps : déclenchés trop vite d'affilée
  // (boucle synchrone), Chrome bloque silencieusement le 2e fichier en
  // pensant à un spam de téléchargements — d'où "je ne reçois que le 144".
  bands.forEach((band, bandIdx)=>{ setTimeout(()=>{
    const bandQSOs = qsoLog.filter(q=>q.band===band && isValidQSO(q));
    if(!bandQSOs.length) return;
    const bandScore = bandQSOs.reduce((s,q)=>s+(q.points||0),0);
    const antBand   = band==='432' ? ediAnt432 : ediAnt144;

    const lines = [
      '[REG1TEST;1]',
      `TName=${ediCfg.contest||'Rallye des Points Hauts'}`,
      `TDate=${TDATE_START};${TDATE_END}`,
      `PCall=${myCall||ediCall}`,
      `PWWLo=${myLocator||ediLocator}`,
      `PExch=`,
      `PSect=${ediCfg.section||'SOMB'}`,
      `PBand=${band} MHz`,
      `PClub=${ediClub}`,
      `RName=${ediRName}`,
      `RCall=${ediRCall}`,
      `RAdr1=${ediCity}`,
      `RPoCo=${ediPostal}`,
      `RCity=${ediCity}`,
      `RCoun=${ediCountry}`,
      `RPhon=`,
      `RHBBS=${ediEmail}`,
      `MOpe1=${ediMOpe1}`,
      `MOpe2=${ediMOpe2}`,
      `STXEq=${ediRadio}`,
      `SPowe=${ediPower}`,
      `SRXEq=${ediRadio}`,
      `SAnte=${antBand}`,
      `SAntH=`,
      `CQSOs=${bandQSOs.length}`,
      `CQSOP=${bandScore}`,
      `CScor=${bandScore}`,
      `TMore=`,
      `[Remarks]`,
      `Logiciel: RadioContest AI v3.0 — ${ediCall} ${ediLocator}`,
      ...(ediAltitude ? [`Altitude: ${ediAltitude}m`] : []),
      ...(ediDept ? [`Département: ${ediDept}`] : []),
      ...(ediOpList.length ? [`Opérateurs : ${ediOpList.join(', ')}`] : []),
      ...(getSoapbox(band) ? [getSoapbox(band)] : []),
      `[QSOrecords;${bandQSOs.length}]`,
    ];

    let edi = lines.join('\r\n') + '\r\n';
    bandQSOs.forEach((q, idx)=>{
      const serial = String(idx+1).padStart(3,'0');
      const timeStr = q.time.replace(':',''); // HHMM
      const modeCode = q.mode==='CW'?2:q.mode==='FM'?6:1; // 1=SSB
      edi += `${q.date};${timeStr};${q.call};${modeCode};${q.rst_sent};${serial};${q.rst_rcvd};${q.num_rcvd||'001'};;${q.locator||''};${q.points||0};;${q.mode};\r\n`;
    });
    edi += `[END; do not edit below this line]\r\n`;

    const blob = new Blob([edi],{type:'text/plain;charset=utf-8'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    // Nom fichier dynamique : CALL_CONTESTNAME_YEAR_BANDMHz.edi
    const contestSlug = (ediCfg.contest||'Contest').replace(/[^A-Za-z0-9]/g,'_').replace(/_+/g,'_').slice(0,30);
    const contestYear = TDATE_START.slice(0,4) || new Date().getFullYear();
    a.download = `${myCall.replace('/','_')}_${contestSlug}_${contestYear}_${band}MHz.edi`;
    a.click();
  }, bandIdx * 500); });

  // Rappel soumission
  setTimeout(()=>{
    const submitUrl = ediCfg.submit_url || 'http://concours.r-e-f.org/tools/upload/thf.php';
    const submitDeadline = ediCfg.submit_deadline || '';
    const deadlineLine = submitDeadline ? `\nDélai : ${submitDeadline}` : '';
    notify(`📤 SOUMISSION DU LOG\n\nURL : ${submitUrl}${deadlineLine}\n\n⚠️ 1 fichier EDI PAR BANDE (144 MHz et 432 MHz séparés)`);
  }, bands.length * 500 + 300);
}

function exportCabrillo(cfg, call){
  const contestName = {
    'ARRL_FD':       'ARRL-FIELD-DAY',
    'ARRL_DX_SSB':   'ARRL-DX-SSB',
    'ARRL_DX_CW':    'ARRL-DX-CW',
    'CQ_WW_SSB':     'CQ-WW-SSB',
    'CQ_WW_CW':      'CQ-WW-CW',
    'CQ_WPX_SSB':    'CQ-WPX-SSB',
    'CQ_WPX_CW':     'CQ-WPX-CW',
    'IARU_HF':       'IARU-HF',
    'WAE_CW':        'WAE-CW',
    'WAE_SSB':       'WAE-SSB',
    'REF_CDF_HF_SSB':'CDF-HF-SSB',
    'REF_CDF_HF_CW': 'CDF-HF-CW',
  }[currentContest] || currentContest;

  const BAND_MHZ = {
    '1.8':'1800','3.5':'3500','7':'7000','14':'14000',
    '21':'21000','28':'28000','50':'50000',
    '144':'144000','432':'432000',
  };

  const MODE_CAB = {'SSB':'PH','CW':'CW','FT8':'DG','FT4':'DG','RTTY':'RY','FM':'PH'};

  const totalScore = qsoLog.reduce((s,q)=>s+(q.points||0),0);
  const operators  = (cfg.operators||[]).map(o=>o.call).filter(Boolean).join(',') || call;

  let cab = `START-OF-LOG: 3.0\r\n`;
  cab += `CREATED-BY: RadioContest AI v3.0\r\n`;
  cab += `CONTEST: ${contestName}\r\n`;
  cab += `CALLSIGN: ${call||cfg.callsign||'F4GLD'}\r\n`;
  cab += `OPERATORS: ${operators}\r\n`;
  cab += `CLUB: ${cfg.club||''}\r\n`;
  cab += `NAME: ${cfg.op_name||''}\r\n`;
  cab += `ADDRESS: ${cfg.city||''}\r\n`;
  cab += `ADDRESS-CITY: ${cfg.city||''}\r\n`;
  cab += `ADDRESS-COUNTRY: ${cfg.country||'FRANCE'}\r\n`;
  cab += `EMAIL: ${cfg.email||''}\r\n`;
  cab += `LOCATION: ${cfg.section||''}\r\n`;

  // ARRL FD spécifique : classe
  if(currentContest === 'ARRL_FD'){
    const nTx = cfg.operators?.length || 1;
    const fdClass = cfg.section||'DX';
    cab += `CATEGORY-OPERATOR: ${nTx>1?'MULTI-OP':'SINGLE-OP'}\r\n`;
    cab += `CATEGORY-TRANSMITTER: ${nTx}\r\n`;
    cab += `CATEGORY-POWER: ${parseInt(cfg.power||100)<=5?'QRP':parseInt(cfg.power||100)<=100?'LOW':'HIGH'}\r\n`;
    cab += `CATEGORY-STATION: PORTABLE\r\n`;
    cab += `CATEGORY-SECTION: ${fdClass}\r\n`;
  }

  cab += `CLAIMED-SCORE: ${totalScore}\r\n`;
  cab += `\r\n`;

  qsoLog.forEach(q=>{
    const freq = BAND_MHZ[q.band] || q.band;
    const mode = MODE_CAB[q.mode] || 'PH';
    const date = `${q.date.slice(0,4)}-${q.date.slice(4,6)}-${q.date.slice(6,8)}`;
    const time = q.time.replace(':','');
    const myExch = q.num_sent || '001';
    const dxExch = q.num_rcvd || '001';
    // QSO: freq mode date time mycall sent dxcall rcvd
    cab += `QSO: ${freq.padEnd(6)} ${mode} ${date} ${time} ${(call||'F4GLD').padEnd(13)} ${String(myExch).padEnd(6)} ${q.call.padEnd(13)} ${dxExch}\r\n`;
  });

  cab += `END-OF-LOG:\r\n`;

  const blob = new Blob([cab],{type:'text/plain;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  const year = (cfg.contest_start_date||'').slice(0,4) || new Date().getUTCFullYear();
  a.download = `${(call||'F4GLD').replace('/','_')}_${currentContest}_${year}.log`;
  a.click();

  setTimeout(()=>{
    const submitUrl = cfg.submit_url || '';
    const deadline  = cfg.submit_deadline || '';
    let msg = `📤 FICHIER CABRILLO GÉNÉRÉ\n\n`;
    msg += `Concours : ${contestName}\n`;
    msg += `QSOs : ${qsoLog.length} — Score déclaré : ${totalScore} pts\n`;
    if(submitUrl) msg += `\nURL soumission : ${submitUrl}`;
    if(deadline)  msg += `\nDélai : ${deadline}`;
    notify(msg);
  }, 400);
}

function exportADIF(){
  const validQSOs = qsoLog.filter(isValidQSO);
  const skipped = qsoLog.length - validQSOs.length;
  if(skipped && !confirm(`⚠️ ${skipped} QSO incomplet(s) seront ignorés dans l'export ADIF.\n\nContinuer ?`)) return;

  let adif = 'RadioContest AI — Export ADIF\n<EOH>\n\n';
  validQSOs.forEach(q=>{
    adif += `<CALL:${q.call.length}>${q.call} <BAND:${(q.band+'M').length}>${q.band}M <MODE:${q.mode.length}>${q.mode} `;
    adif += `<RST_SENT:${q.rst_sent.length}>${q.rst_sent} <RST_RCVD:${q.rst_rcvd.length}>${q.rst_rcvd} `;
    if(q.locator) adif += `<GRIDSQUARE:${q.locator.length}>${q.locator} `;
    adif += `<QSO_DATE:8>${q.date} <TIME_ON:4>${q.time.replace(':','')} <EOR>\n`;
  });
  const blob = new Blob([adif],{type:'text/plain'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${myCall.replace('/','_')}_log.adif`;
  a.click();
}

function exportCSV(){
  let csv = 'N°,Date,Heure,Indicatif,Bande,Mode,RST_env,N°_env,RST_recu,N°_recu,Locator,Distance_km,Points,Operateur\n';
  qsoLog.forEach((q,i)=>{
    csv += `${i+1},${q.date},${q.time},${q.call},${q.band},${q.mode},${q.rst_sent},${q.num_sent},${q.rst_rcvd},${q.num_rcvd||''},${q.locator||''},${q.dist||0},${q.points||0},${q.operator}\n`;
  });
  const blob = new Blob([csv],{type:'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${myCall.replace('/','_')}_log.csv`;
  a.click();
}

// ─── RESET LOG ───────────────────────────────────────────────────────────────
// Archive le concours actif dans un dossier permanent (log + Cabrillo + ADIF
// + résumé). Optionnellement, vide ensuite ce concours du log actif.
async function archiveLog(){
  try{
    const clear = confirm('📦 ARCHIVER CE CONCOURS\n\n' +
      'Le log du concours actif va être conservé dans un dossier permanent\n' +
      '(log.json + Cabrillo + ADIF + résumé), qui restera même si tu changes\n' +
      'de concours.\n\n' +
      'OK  = archiver ET vider ce concours du log actif (repartir à neuf)\n' +
      'Annuler = archiver SANS rien effacer');
    const res = await fetch('/log/archive', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({clear: clear})
    });
    const d = await res.json();
    if(d.ok){
      notify(`📦 Archivé : ${d.qso_count} QSO dans « ${d.name} »` +
             (d.cleared ? ' — log vidé, prêt pour la suite.' : ' — log conservé.'));
      if(d.cleared){ qsoLog = qsoLog.filter(q => false); renderLog(); updateStats(); }
      else { fetchLog(); }
    } else {
      notify('Archivage : ' + (d.error || 'échec'));
    }
  }catch(e){ notify('Serveur injoignable — archivage impossible.'); }
}

async function resetLog(){
  const n = qsoLog.length;
  if(!confirm(`⚠️ NOUVEAU LOG\n\nSupprime ${n} QSO du log ACTIF.\nⓘ Ils sont d'abord ARCHIVÉS dans un dossier permanent (par concours),\ndonc rien n'est perdu — tu les retrouveras dans archives/.\n\nTape OK pour continuer.`)) return;
  const confirmation = prompt('Tape RESET pour confirmer la suppression complète du log :');
  if(confirmation !== 'RESET'){
    notify('Annulé — le log est inchangé.');
    return;
  }
  try{
    const res = await fetch('/log/reset',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({confirm:'RESET'})
    });
    if(res.ok){
      const d = await res.json().catch(()=>({}));
      qsoLog = [];
      serialByBand = {};
      renderLog();
      updateStats();
      updateSerialDisplay();
      const nb = (d.folders || []).length;
      notify('✅ Log archivé' + (nb ? ` (${nb} dossier${nb>1?'s':''})` : '') +
             ' puis réinitialisé — prêt pour le concours !');
    } else {
      notify('Erreur serveur lors de la réinitialisation.');
    }
  } catch(e){
    notify('Impossible de contacter le serveur : '+e.message);
  }
}

// ─── LOOKUP DISTANT HAMQTH (debounce 600 ms) ─────────────────────────────────
async function remoteCallLookup(call){
  if(call.length < 4) return;
  if(document.getElementById('inputLocator').value) return; // déjà rempli
  try{
    const res = await fetch(`/calldb/lookup/${encodeURIComponent(call)}`);
    if(!res.ok) return;
    const d = await res.json();
    // Indicatif changé entre-temps → ignorer
    if(document.getElementById('inputCall').value.toUpperCase() !== call) return;
    if(d.locator){
      callDB[call] = callDB[call] || {};
      callDB[call].locator = d.locator;
      applyCallData({locator: d.locator}, null, null);
      // Correction du label source → HamQTH
      const hint = document.getElementById('locHint');
      if(hint && hint.style.display !== 'none')
        hint.textContent = hint.textContent.replace('[🗂️ base]','[🌐 HamQTH]');
    }
  } catch(e){}
}

// ─── CACHE CLUSTER ────────────────────────────────────────────────────────────
// callsign → { locator, freq, band, time, spotter, source }
let clusterCache = {};
let clusterLastRefresh = 0;
let callLookupTimer = null;

async function refreshCluster(){
  // Récupère les spots cluster depuis le serveur et alimente clusterCache
  try{
    const res = await fetch('/log/status');
    if(!res.ok) return;
    const data = await res.json();
    const spots = data.spots || {};
    const cache = {};
    Object.keys(spots).forEach(band=>{
      const list = spots[band] || [];
      list.forEach(s=>{
        const call = (s.call||'').toUpperCase().split('/')[0];
        if(!call) return;
        cache[call] = {
          locator: s.locator||'',
          freq:    s.freq||'',
          band:    String(band).replace(/[^0-9.]/g,'') || band,
          time:    s.time||'',
          spotter: s.spotter||'',
          source:  s.source||'cluster',
        };
      });
    });
    clusterCache = cache;
    clusterLastRefresh = Date.now();
  }catch(e){ /* serveur hors ligne : on conserve le cache existant */ }
}

// ─── BASE D'INDICATIFS (calldb.json) ─────────────────────────────────────────
let callDB = {};

async function loadCallDB(){
  // Index FUSIONNÉ serveur (/call/index = calldb + archives + anciens concours,
  // enrichi de worked/qso_count) ; repli sur calldb.json brut si indisponible.
  // Plusieurs tentatives rapprochées : la 1ère requête « à froid » peut échouer
  for(let attempt=1; attempt<=6; attempt++){
    try{
      let res = await fetch('/call/index');
      if(!res.ok) res = await fetch('/calldb.json', {cache:'force-cache'});
      if(!res.ok) throw new Error('HTTP '+res.status);
      const data = await res.json();
      callDB = data.calls || {};
      return;
    }catch(e){
      if(attempt === 6){ console.warn('base indicatifs indisponible :', e.message); }
      else { await new Promise(r=>setTimeout(r, 150)); }
    }
  }
}

function lookupCall(call){
  if(!call) return null;
  const c = call.toUpperCase().split('/')[0];
  return callDB[c] || callDB[call.toUpperCase()] || null;
}

function lookupCluster(call){
  if(!call) return null;
  const c = call.toUpperCase().split('/')[0];
  return clusterCache[c] || null;
}

// ─── AUTOCOMPLETE INDICATIF ───────────────────────────────────────────────────
let acResults = [];
let acSelected = -1;

function searchCalls(prefix){
  prefix = prefix.toUpperCase();
  const seen = new Set();
  const out  = [];

  // 1. Appels déjà travaillés dans le log courant (source la plus précieuse)
  for(const q of qsoLog){
    if(q.call && q.call.startsWith(prefix) && !seen.has(q.call)){
      seen.add(q.call);
      out.push({call:q.call, src:'log', locator:q.locator, dup:isDup(q.call,currentBand)});
      if(out.length >= 10) break;
    }
  }

  // 2. Base fusionnée (calldb + archives + anciens concours) — SUPER CHECK
  //    PARTIAL : préfixe d'abord, puis FRAGMENT n'importe où dans l'indicatif
  //    (dès 3 caractères, comme N1MM). Les stations déjà travaillées dans un
  //    concours passé remontent en tête.
  if(out.length < 10){
    const starts = [], contains = [];
    for(const call in callDB){
      if(seen.has(call)) continue;
      if(call.startsWith(prefix)) starts.push(call);
      else if(prefix.length >= 3 && call.includes(prefix)) contains.push(call);
    }
    const rank = c => ((callDB[c]||{}).worked ? 0 : 1);
    const byRank = (a,b) => rank(a)-rank(b) || a.localeCompare(b);
    starts.sort(byRank);
    contains.sort(byRank);
    for(const call of starts.concat(contains)){
      const d = callDB[call] || {};
      out.push({call, src: d.worked ? 'hist' : 'db',
                locator:d.locator, dept:d.dept, dup:isDup(call,currentBand)});
      if(out.length >= 10) break;
    }
  }
  return out;
}

function showAC(results, call){
  const box = document.getElementById('acBox');
  acResults = results || [];
  acSelected = -1;
  if(!acResults.length){ hideAC(); return; }
  box.innerHTML = acResults.map(item=>{
    const c     = typeof item === 'string' ? item : item.call;
    const src   = item.src  || 'db';
    const loc   = item.locator || (callDB[c]||{}).locator || '';
    const dept  = item.dept  || (callDB[c]||{}).dept  || '';
    const dup   = item.dup   || false;
    const dxcc  = lookupDXCC(c);
    const flag  = dxcc ? dxcc.flag : '';
    const cname = dxcc ? dxcc.c    : '';
    const srcTag = src==='log'
      ? `<span style="color:var(--green);font-size:13px;font-weight:700">📋 LOG</span>`
      : src==='hist'
      ? `<span style="color:var(--green);font-size:13px;font-weight:700">✓ DÉJÀ VU</span>`
      : `<span style="color:var(--muted);font-size:14px">🗂️</span>`;
    const dupTag = dup
      ? `<span style="color:var(--red);font-size:14px;font-weight:800">DUPE</span>`
      : '';
    const locStr = loc ? `<span style="color:var(--accent2);font-size:14px;font-weight:700">${loc}</span>` : '';
    const deptStr = dept ? `<span style="color:var(--yellow);font-size:14px;font-weight:700">dpt${dept}</span>` : '';
    const cStr  = cname ? `<span style="color:var(--muted);font-size:14px">${cname}</span>` : '';
    return `<div class="ac-item${dup?' dupe-item':''}" data-call="${c}" onmousedown="selectAC('${c}')">`
      + `<span style="font-size:16px">${flag}</span>`
      + `<b class="ac-call${dup?' dupe-call':''}" style="${dup?'color:var(--red)':'color:var(--green)'}">${c}</b>`
      + `<span style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;flex:1">${locStr}${deptStr}${cStr}${dupTag}</span>`
      + srcTag
      + `</div>`;
  }).join('');
  box.style.display = 'block';
}

function hideAC(){
  const box = document.getElementById('acBox');
  if(box) box.style.display = 'none';
  acSelected = -1;
}

function highlightAC(){
  document.querySelectorAll('#acBox .ac-item')
    .forEach((it,i)=> it.classList.toggle('selected', i===acSelected));
}

function selectAC(call){
  document.getElementById('inputCall').value = call;
  hideAC();

  // ── Vérification doublon ─────────────────────────────────────────────────
  const warn  = document.getElementById('dupWarn');
  const input = document.getElementById('inputCall');
  if(isDup(call, currentBand)){
    warn.style.background  = 'rgba(255,45,85,.15)';
    warn.style.borderColor = 'var(--red)';
    warn.style.color       = 'var(--red)';
    warn.textContent       = `⚠️ DOUBLON — ${call} déjà dans le log sur ${currentBand} MHz !`;
    warn.classList.add('show');
    input.classList.add('error');
    input.classList.remove('ok');
    // Bip d'erreur (deux bips courts)
    if(bipEnabled){
      playBeep(880, 0.12, 'square', 0.3);
      setTimeout(()=>playBeep(880, 0.12, 'square', 0.3), 200);
    }
  } else {
    warn.classList.remove('show');
    input.classList.remove('error');
    input.classList.add('ok');
  }

  // ── Préremplissage locator ────────────────────────────────────────────────
  const locField = document.getElementById('inputLocator');
  locField.value = '';
  const db  = lookupCall(call);
  const cl  = lookupCluster(call);
  const log = qsoLog.slice().reverse().find(q => q.call === call && q.locator && q.locator.length === 6);
  if(db || cl || log) applyCallData(db, cl, log);

  // ── Alerte double-bande ───────────────────────────────────────────────────
  crossBandAlert(call, currentBand);
  // ── Focus : RST si locator connu, sinon locator ───────────────────────────
  const locVal = document.getElementById('inputLocator').value;
  if(locVal && validateLocator(locVal)){
    focusNext('inputRSTsent');
  } else {
    focusNext('inputLocator');
  }
}

function onCallKeydown(e){
  const box = document.getElementById('acBox');
  const open = box && box.style.display !== 'none' && acResults.length;
  if(e.key === 'ArrowDown' && open){
    e.preventDefault();
    acSelected = Math.min(acSelected+1, acResults.length-1);
    highlightAC();
  } else if(e.key === 'ArrowUp' && open){
    e.preventDefault();
    acSelected = Math.max(acSelected-1, 0);
    highlightAC();
  } else if(e.key === 'Enter'){
    if(open && acSelected >= 0){
      e.preventDefault();
      const item = acResults[acSelected];
      selectAC(typeof item === 'string' ? item : item.call);
    } else {
      hideAC();
      e.preventDefault();
      // ESM : Entrée enchaîne appel CQ → échange (sinon valide le QSO).
      if(esmHandleEnter()) return;
      submitQSO();
    }
  } else if(e.key === 'Escape'){
    hideAC();
  }
}

// ─── APPLICATION DES DONNÉES D'UN INDICATIF CONNU ─────────────────────────────
function applyCallData(dbData, clusterData, logEntry){
  const callField = document.getElementById('inputCall');
  const locField  = document.getElementById('inputLocator');
  const hint      = document.getElementById('locHint');

  // Priorité : cluster (temps réel) > log courant > calldb
  const clLoc  = clusterData && clusterData.locator;
  const logLoc = logEntry    && logEntry.locator;
  const dbLoc  = dbData      && dbData.locator;
  const loc    = clLoc || logLoc || dbLoc || '';

  // Remplir le locator si :
  //  - la source est le cluster (temps réel → toujours prioritaire)
  //  - OU le champ est vide / invalide
  const existingLoc = locField.value;
  const existingValid = existingLoc && validateLocator(existingLoc);
  if(loc && (clLoc || !existingValid)){
    locField.value = loc;
    hideLocAC();
    onLocatorInput(); // calcule distance + cap → compas + hint
    const src = clLoc ? '📡 cluster' : logLoc ? '📋 log' : '🗂️ base';
    if(hint && hint.style.display !== 'none'){
      hint.textContent += `  [${src}]`;
    } else if(hint){
      hint.style.display = 'block';
      hint.style.color   = 'var(--accent2)';
      hint.textContent   = `Locator : ${src}`;
    }
  }

  // ── Département attendu (concours REF HF : l'échange EST le département) ──
  // Pré-rempli seulement si le champ est vide — l'opérateur reste maître de
  // ce qu'il a réellement reçu.
  if((currentExchange.label_r || '').includes('DEPT')){
    const numR = document.getElementById('inputNumRcvd');
    const dept = (dbData && dbData.dept) || (logEntry && logEntry.num_rcvd) || '';
    if(numR && !numR.value && dept){
      numR.value = dept;
      numR.classList.add('ok');
    }
  }
  if(callField) callField.classList.add('ok');
}

// ─── MISE À JOUR DE LA BASE D'INDICATIFS ──────────────────────────────────────
function updateCallDB(call, locator, dept){
  call = (call||'').toUpperCase().split('/')[0];
  if(!call) return;
  const entry = callDB[call] || {};
  let changed = false;
  if(locator && entry.locator !== locator){ entry.locator = locator; changed = true; }
  if(dept && entry.dept !== dept){ entry.dept = dept; changed = true; }
  if(changed){
    callDB[call] = entry;
    fetch('/calldb/update', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({call, locator: locator||'', dept: dept||''})
    }).catch(()=>{});
  }
}

// ─── REVERSE LOOKUP LOCATOR → INDICATIFS ─────────────────────────────────────
let locAcResults = [];
let locAcSelected = -1;

function searchByLocator(prefix){
  prefix = prefix.toUpperCase();
  const seen = new Set();
  const out  = [];

  // 1. Log courant : stations vues à ce locator
  for(const q of qsoLog){
    if(q.locator && q.locator.toUpperCase().startsWith(prefix) && !seen.has(q.call)){
      seen.add(q.call);
      out.push({call:q.call, locator:q.locator, src:'log', dup:isDup(q.call,currentBand)});
      if(out.length >= 12) return out;
    }
  }

  // 2. Base callDB
  for(const call in callDB){
    const d = callDB[call];
    if(d.locator && d.locator.toUpperCase().startsWith(prefix) && !seen.has(call)){
      seen.add(call);
      out.push({call, locator:d.locator, dept:d.dept||'', src:'db', dup:isDup(call,currentBand)});
      if(out.length >= 12) return out;
    }
  }
  return out;
}

function showLocAC(results){
  const box = document.getElementById('locAcBox');
  if(!box) return;
  locAcResults = results || [];
  locAcSelected = -1;
  if(!locAcResults.length){ hideLocAC(); return; }
  box.innerHTML = locAcResults.map((item, idx) => {
    const dup     = item.dup || false;
    const dxcc    = lookupDXCC(item.call);
    const flag    = dxcc ? dxcc.flag : '';
    const srcTag  = item.src === 'log'
      ? `<span style="color:var(--green);font-size:13px;font-weight:700">📋 LOG</span>`
      : `<span style="color:var(--muted);font-size:14px">🗂️</span>`;
    const dupTag  = dup ? `<span style="color:var(--red);font-size:14px;font-weight:800">DUPE</span>` : '';
    const deptStr = item.dept ? `<span style="color:var(--yellow);font-size:14px;font-weight:700">dpt${item.dept}</span>` : '';
    const locStr  = `<span style="color:var(--accent2);font-size:14px;font-weight:800">${item.locator}</span>`;
    return `<div class="ac-item${dup?' dupe-item':''}" data-idx="${idx}" onmousedown="selectLocAC(${idx})">`
      + `<span style="font-size:16px">${flag}</span>`
      + `<b style="font-size:19px;font-weight:900;min-width:110px;letter-spacing:1px;${dup?'color:var(--red)':'color:var(--green)'}">${item.call}</b>`
      + `<span style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;flex:1">${locStr}${deptStr}${dupTag}</span>`
      + srcTag
      + `</div>`;
  }).join('');
  box.style.display = 'block';
}

function hideLocAC(){
  const box = document.getElementById('locAcBox');
  if(box) box.style.display = 'none';
  locAcSelected = -1;
}

function selectLocAC(idx){
  const item = locAcResults[idx];
  if(!item) return;
  hideLocAC();
  // Remplir l'indicatif
  const callField = document.getElementById('inputCall');
  if(callField && !callField.value){
    callField.value = item.call;
    onCallInput();
  }
  // Confirmer le locator exact
  const locField = document.getElementById('inputLocator');
  if(locField) locField.value = item.locator;
  onLocatorInput();
}

function onLocatorKeydown(e){
  const box = document.getElementById('locAcBox');
  const open = box && box.style.display !== 'none' && locAcResults.length;
  if(e.key === 'ArrowDown' && open){
    e.preventDefault();
    locAcSelected = Math.min(locAcSelected + 1, locAcResults.length - 1);
    document.querySelectorAll('#locAcBox .ac-item').forEach((it,i) => it.classList.toggle('selected', i === locAcSelected));
  } else if(e.key === 'ArrowUp' && open){
    e.preventDefault();
    locAcSelected = Math.max(locAcSelected - 1, 0);
    document.querySelectorAll('#locAcBox .ac-item').forEach((it,i) => it.classList.toggle('selected', i === locAcSelected));
  } else if(e.key === 'Enter' && open && locAcSelected >= 0){
    e.preventDefault();
    selectLocAC(locAcSelected);
  } else if(e.key === 'Escape'){
    hideLocAC();
  } else if(e.key === 'Enter' && !open){
    e.preventDefault();
    submitQSO();
  }
}

// ─── COMPAS INLINE ────────────────────────────────────────────────────────────
let _lastCompassDeg = null;   // cap courant, pour le bouton « pointer »

function showCompassInline(deg, distKm, pts){
  const el      = document.getElementById('compassInline');
  const needle  = document.getElementById('compassNeedle');
  const degEl   = document.getElementById('compassDeg');
  const cardEl  = document.getElementById('compassCard');
  const distEl  = document.getElementById('compassDist');
  const ptsEl   = document.getElementById('compassPts');
  if(!el || !needle) return;
  needle.setAttribute('transform', `rotate(${deg},30,30)`);
  if(degEl)  degEl.textContent  = `${deg}°`;
  if(cardEl) cardEl.textContent = cardinalDir(deg);
  if(distEl) distEl.textContent = `${Math.round(distKm)} km`;
  if(ptsEl)  ptsEl.textContent  = `${pts} pts`;
  el.classList.add('show');
  // Bouton « pointer » : visible seulement si le rotor est piloté
  _lastCompassDeg = deg;
  const pb = document.getElementById('pointAntennaBtn');
  if(pb) pb.style.display = (typeof rotorState !== 'undefined' && rotorState.enabled) ? '' : 'none';
}

function pointAntennaFromCompass(){
  if(_lastCompassDeg == null) return;
  fetch('/rotor/point', {method:'POST', headers:{'Content-Type':'application/json'},
                         body: JSON.stringify({azimuth: _lastCompassDeg})})
    .then(r=>r.json()).then(d=>{
      notify(d.ok ? `🧭 Antenne pointée sur ${_lastCompassDeg}°` : `❌ ${d.error}`);
    }).catch(()=>notify('Rotor injoignable.'));
}
function hideCompassInline(){
  const el = document.getElementById('compassInline');
  if(el) el.classList.remove('show');
}

// ─── CHAT MULTI-OPÉRATEUR ─────────────────────────────────────────────────────
let chatLastId = 0;
let chatTimer = null;

function startChat(){
  pollChat();
  if(!chatTimer) chatTimer = setInterval(pollChat, 3000);
}

async function pollChat(){
  try{
    const r = await fetch('/chat/list?since=' + chatLastId);
    if(!r.ok) return;
    const d = await r.json();
    (d.messages || []).forEach(renderChatMsg);
    if(typeof d.last_id === 'number') chatLastId = d.last_id;
  }catch(e){ /* serveur injoignable : on réessaiera */ }
}

function renderChatMsg(m){
  const box = document.getElementById('chatBox');
  if(!box) return;
  const mine = (m.op === myOp);
  const div = document.createElement('div');
  div.className = 'chatmsg' + (mine ? ' mine' : '');
  const meta = document.createElement('span');
  meta.className = 'chatmeta';
  meta.textContent = `${m.time} ${m.op}${m.call ? ' · ' + m.call : ''}`;
  const txt = document.createElement('div');
  txt.className = 'chattext';
  txt.textContent = m.text;
  div.appendChild(meta); div.appendChild(txt);
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  // Point rouge clignotant si le panneau est fermé et que ce n'est pas mon message
  const panel = document.getElementById('chatPanel');
  if(!panel.classList.contains('open') && !mine){
    document.getElementById('chatDot').style.display = 'inline-block';
  }
}

async function sendChat(){
  const inp = document.getElementById('chatInput');
  const text = inp.value.trim();
  if(!text) return;
  inp.value = '';
  try{
    await fetch('/chat/send', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ op: myOp, call: myCall, text })
    });
    pollChat();
  }catch(e){
    inp.value = text;
    notify('Chat : serveur injoignable, message non envoyé.');
  }
}

function toggleChat(){
  const panel = document.getElementById('chatPanel');
  panel.classList.toggle('open');
  if(panel.classList.contains('open')){
    document.getElementById('chatDot').style.display = 'none';
    document.getElementById('chatBox').scrollTop = document.getElementById('chatBox').scrollHeight;
    document.getElementById('chatInput').focus();
  }
}

// ─── TOGGLE JOUR/NUIT ────────────────────────────────────────────────────────
function toggleTheme(){
  const day = document.body.classList.toggle('day-mode');
  localStorage.setItem('rc_theme', day ? 'day' : 'night');
  document.getElementById('themeToggle').textContent = day ? '🌙' : '☀️';
}

function toggleShortcutsHelp(){
  document.getElementById('shortcutsOverlay').classList.toggle('show');
}

function toggleChecklist(){
  document.getElementById('checklistOverlay').classList.toggle('show');
}

async function showChecklist(){
  document.getElementById('checklistOverlay').classList.add('show');
  const inner = document.getElementById('checklistInner');
  inner.innerHTML = '<div class="shortcuts-row"><span>⏳ Vérification en cours…</span></div>';

  const rows = [];

  // 1. Config sauvegardée
  let cfg = {};
  try{ cfg = JSON.parse(localStorage.getItem('radiocontest_config')||'{}'); }catch(e){}
  const cfgOk = !!(cfg.callsign && cfg.locator && cfg.contest);
  rows.push({ok: cfgOk, label: cfgOk ? `Config sauvegardée (${cfg.callsign}, ${cfg.contest})` : 'Config incomplète — vérifie l\'onglet CONFIG'});

  // 2. Base d'indicatifs chargée
  const dbCount = Object.keys(callDB).length;
  rows.push({ok: dbCount > 0, label: dbCount > 0 ? `Base d'indicatifs chargée (${dbCount.toLocaleString()} entrées)` : 'Base d\'indicatifs non chargée — recharge la page'});

  // 3. Serveur connecté
  const netDotEl = document.getElementById('netDot');
  const netOk = netDotEl && netDotEl.classList.contains('online');
  rows.push({ok: netOk, label: netOk ? 'Serveur connecté' : 'Hors ligne — le log restera local jusqu\'à reconnexion'});

  // 4. Heure synchronisée (comparaison avec l'en-tête Date renvoyé par le serveur)
  let timeOk = false, timeMsg = 'Impossible de vérifier l\'heure serveur';
  try{
    const res = await fetch('/config', {cache:'no-store'});
    const serverDate = new Date(res.headers.get('Date'));
    const diffSec = Math.abs((Date.now() - serverDate.getTime())/1000);
    timeOk = diffSec < 30;
    timeMsg = timeOk ? `Heure système synchronisée (écart ${diffSec.toFixed(0)}s)` : `Écart de ${diffSec.toFixed(0)}s avec le serveur — vérifie l'heure système`;
  }catch(e){}
  rows.push({ok: timeOk, label: timeMsg});

  // 5. Postes connectés (info)
  const peersEl = document.getElementById('netPeers');
  rows.push({ok: true, info: true, label: `Postes connectés au réseau : ${peersEl ? peersEl.textContent : '—'}`});

  inner.innerHTML = rows.map(r=>{
    const icon  = r.info ? 'ℹ️' : (r.ok ? '✅' : '⚠️');
    const color = r.info ? 'var(--accent2)' : (r.ok ? 'var(--green)' : 'var(--yellow)');
    return `<div class="shortcuts-row"><span class="shortcuts-key" style="color:${color};min-width:32px">${icon}</span><span>${r.label}</span></div>`;
  }).join('');
}

// ─── VÉRIFICATION DU LOG AVANT SOUMISSION (validateur serveur, spécial REF) ───
// Doublons, locators absents/invalides, distances anormales, départements
// invalides, QSO hors fenêtre — tout ce qui coûterait des points au contrôle.
async function showValidation(){
  const ov = document.getElementById('validateOverlay');
  const inner = document.getElementById('validateInner');
  if(!ov || !inner) return;
  ov.classList.add('show');
  inner.innerHTML = '<div class="shortcuts-row"><span>⏳ Analyse du log en cours…</span></div>';
  let d;
  try{
    const r = await fetch('/log/validate');
    if(!r.ok) throw new Error('HTTP '+r.status);
    d = await r.json();
  }catch(e){
    inner.innerHTML = `<div class="shortcuts-row"><span style="color:var(--red)">❌ Serveur injoignable (${e.message})</span></div>`;
    return;
  }
  const c = d.counts || {};
  const head =
    `<div class="shortcuts-row" style="font-weight:700">`+
    `<span>${d.qso_count} QSO analysés — `+
    `<span style="color:var(--red)">${c.erreur||0} erreur${(c.erreur||0)>1?'s':''}</span> · `+
    `<span style="color:var(--yellow)">${c.attention||0} à vérifier</span> · `+
    `<span style="color:var(--accent2)">${c.info||0} info${(c.info||0)>1?'s':''}</span></span></div>`;
  if(!(d.findings||[]).length){
    inner.innerHTML = head +
      `<div class="shortcuts-row"><span style="color:var(--green);font-weight:700">`+
      `✅ Aucun problème détecté — le log est prêt à être exporté et envoyé.</span></div>`;
    return;
  }
  const ICO = {erreur:'❌', attention:'⚠️', info:'ℹ️'};
  const COL = {erreur:'var(--red)', attention:'var(--yellow)', info:'var(--accent2)'};
  inner.innerHTML = head + d.findings.map(f =>
    `<div class="shortcuts-row">`+
    `<span class="shortcuts-key" style="color:${COL[f.level]||'var(--muted)'};min-width:32px">${ICO[f.level]||'•'}</span>`+
    `<span>${f.msg}${f.at ? ` <span style="color:var(--muted);font-size:12px">(${f.at})</span>` : ''}</span></div>`
  ).join('') + (d.truncated ? `<div class="shortcuts-row"><span style="color:var(--muted)">… liste tronquée</span></div>` : '');
}

// ─── DIPLÔMES & QSL (carnet permanent, tous concours) ────────────────────────
async function showAwards(){
  const ov = document.getElementById('awardsOverlay');
  const inner = document.getElementById('awardsInner');
  if(!ov || !inner) return;
  ov.classList.add('show');
  inner.innerHTML = '<div class="shortcuts-row"><span>⏳ Calcul des diplômes…</span></div>';
  let a, q;
  try{
    [a, q] = await Promise.all([
      fetch('/awards/summary').then(r=>r.json()),
      fetch('/qsl/status').then(r=>r.json()),
    ]);
  }catch(e){
    inner.innerHTML = `<div class="shortcuts-row"><span style="color:var(--red)">❌ Serveur injoignable</span></div>`;
    return;
  }
  const dep = a.departments || {};
  const bar = (w,t) => {
    const pct = t ? Math.round(100*w/t) : 0;
    return `<div style="background:var(--bg3);border-radius:5px;height:10px;overflow:hidden;border:1px solid var(--border)">`+
           `<div style="height:100%;width:${pct}%;background:linear-gradient(90deg,var(--green),var(--accent2))"></div></div>`;
  };
  const row = (label, val) => `<div style="display:flex;justify-content:space-between;padding:4px 0"><span>${label}</span><b>${val}</b></div>`;
  const confNote = a.has_confirmations ? '' :
    `<div style="color:var(--muted);font-size:12px;margin:4px 0 10px">Aucune confirmation importée — synchronise LoTW ci-dessous pour voir le « confirmé ».</div>`;
  const perBand = Object.entries(a.per_band||{}).map(([b,v]) =>
    `<span style="display:inline-block;margin:2px 6px 2px 0;color:var(--muted)">${b} MHz : <b style="color:var(--text)">${v.qso}</b> QSO / ${v.dxcc} DXCC</span>`).join('');

  inner.innerHTML = `
    <div style="font-family:var(--font-mono);font-size:13px;line-height:1.6">
      <div style="color:var(--accent2);letter-spacing:1px;margin:6px 0">📊 CARNET PERMANENT — ${a.qso_total} QSO à vie</div>
      ${confNote}
      ${row('🌍 DXCC (pays)', `${a.dxcc.worked} travaillés · <span style="color:var(--green)">${a.dxcc.confirmed} confirmés</span>`)}
      ${row('🇫🇷 Départements métropole', `${dep.metro_worked}/${dep.metro_total} · <span style="color:var(--green)">${dep.metro_confirmed||0} conf.</span>`)}
      ${bar(dep.metro_worked, dep.metro_total)}
      ${dep.dom_worked ? row('🏝️ Outre-mer', dep.dom_worked) : ''}
      ${row('🗺️ Continents', (a.continents||[]).join(' '))}
      <div style="margin-top:8px;font-size:12px">${perBand}</div>
      ${dep.missing && dep.missing.length ? `<div style="margin-top:8px;font-size:12px;color:var(--muted)">Départements manquants : ${dep.missing.join(', ')}${dep.missing.length>=40?'…':''}</div>` : ''}
    </div>
    <div style="border-top:1px solid var(--border);margin-top:14px;padding-top:12px;font-family:var(--font-mono);font-size:13px">
      <div style="color:var(--accent2);letter-spacing:1px;margin-bottom:8px">📮 QSL — ${a.confirmed_total||0} QSO confirmés (${q.confirmations||0} croisés)</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="export-btn" onclick="qslAction('upload','eqsl',this)" ${q.eqsl?'':'disabled title="Configure eQSL dans CONFIG"'} style="color:var(--accent2);border-color:rgba(0,212,255,.4)">⬆ eQSL</button>
        <button class="export-btn" onclick="qslAction('upload','clublog',this)" ${q.clublog?'':'disabled title="Configure ClubLog dans CONFIG"'} style="color:var(--accent2);border-color:rgba(0,212,255,.4)">⬆ ClubLog</button>
        <button class="export-btn" onclick="qslAction('sync','lotw',this)" ${q.lotw?'':'disabled title="Configure LoTW dans CONFIG"'} style="color:var(--green);border-color:rgba(0,255,136,.4)">⬇ Confirmations LoTW</button>
      </div>
      <div id="qslResult" style="margin-top:10px;color:var(--muted);font-size:12px">${qslLastSync(q)}</div>
      <div style="margin-top:8px;font-size:11px;color:var(--muted)">Identifiants des services : CONFIG → étape PROPAGATION → « QSL & DIPLÔMES ». Stockés côté serveur.</div>
    </div>`;
}

function qslLastSync(q){
  const l = q.last || {};
  const bits = [];
  if(l.eqsl_upload) bits.push('eQSL envoyé le ' + l.eqsl_upload);
  if(l.clublog_upload) bits.push('ClubLog envoyé le ' + l.clublog_upload);
  if(l.lotw) bits.push('LoTW synchro le ' + l.lotw);
  return bits.length ? bits.join(' · ') : 'aucune synchro encore';
}

async function qslAction(kind, service, btn){
  const out = document.getElementById('qslResult');
  const old = btn.textContent;
  btn.disabled = true; btn.textContent = '⏳…';
  if(out) out.textContent = (kind==='upload'?'Envoi vers ':'Synchro ') + service + ' en cours…';
  try{
    const url = kind === 'upload' ? '/qsl/upload' : '/qsl/sync';
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({service})});
    const d = await r.json();
    if(d.ok){
      if(kind==='upload') out.innerHTML = `<span style="color:var(--green)">✅ ${d.qso_count} QSO envoyés à ${d.service}.</span>`;
      else out.innerHTML = `<span style="color:var(--green)">✅ ${d.newly_added} nouvelles confirmations (${d.total_confirmations} au total).</span>`;
      notify('✅ QSL ' + (kind==='upload'?'envoyé':'synchronisé'));
      if(kind==='sync') setTimeout(showAwards, 800);   // rafraîchit les « confirmés »
    }else{
      out.innerHTML = `<span style="color:var(--red)">❌ ${d.error||'échec'}</span>`;
    }
  }catch(e){
    out.innerHTML = `<span style="color:var(--red)">❌ ${e.message}</span>`;
  }finally{
    btn.disabled = false; btn.textContent = old;
  }
}

(function applyTheme(){
  if(localStorage.getItem('rc_theme') === 'day'){
    document.body.classList.add('day-mode');
    document.addEventListener('DOMContentLoaded', ()=>{
      const t = document.getElementById('themeToggle');
      if(t) t.textContent = '🌙';
    });
  }
})();

// ─── RACCOURCIS CLAVIER ───────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  // F9 : soumettre le QSO depuis n'importe où
  if(e.key === 'F9'){
    e.preventDefault();
    if(isSetupDone) submitQSO();
    return;
  }
  // Escape : fermer le modal de setup
  if(e.key === 'Escape'){
    const modal = document.getElementById('setupModal');
    if(modal && modal.style.display !== 'none') modal.style.display = 'none';
    const editModal = document.getElementById('editModal');
    if(editModal && editModal.style.display !== 'none') editModal.style.display = 'none';
    const scOverlay = document.getElementById('shortcutsOverlay');
    if(scOverlay) scOverlay.classList.remove('show');
    const valOverlay = document.getElementById('validateOverlay');
    if(valOverlay) valOverlay.classList.remove('show');
    const awOverlay = document.getElementById('awardsOverlay');
    if(awOverlay) awOverlay.classList.remove('show');
    return;
  }
  // ? : afficher/masquer l'aide des raccourcis (sauf pendant une saisie)
  if(e.key === '?' && !['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)){
    e.preventDefault();
    toggleShortcutsHelp();
    return;
  }
  // Ctrl+Z : annuler le dernier QSO
  if((e.ctrlKey || e.metaKey) && e.key === 'z'){
    e.preventDefault();
    undoLastQSO();
    return;
  }
  // Ctrl+F : focus sur le champ indicatif
  if((e.ctrlKey || e.metaKey) && e.key === 'f'){
    e.preventDefault();
    const inp = document.getElementById('inputCall');
    if(inp){ inp.focus(); inp.select(); }
    return;
  }
  // Entrée : valider le QSO depuis n'importe quel champ de la saisie
  // (filet de sécurité pour les boutons OPÉRATEUR/BANDE/MODE — les champs texte
  // gèrent déjà Enter eux-mêmes et appellent preventDefault, donc pas de double envoi)
  if(e.key === 'Enter' && !e.defaultPrevented){
    const form = document.querySelector('.saisie-form');
    if(form && form.contains(e.target) && e.target.tagName !== 'TEXTAREA'){
      e.preventDefault();
      submitQSO();
    }
  }
});

// ─── PRÉREMPLISSAGE MODAL + NOMS OPÉRATEURS ──────────────────────────────────
function prefillSetupFromConfig(){
  let cfg = {};
  try{ cfg = JSON.parse(localStorage.getItem('radiocontest_config')||'{}'); }catch(e){}

  // Pré-remplir indicatif et locator
  const callEl  = document.getElementById('setupCallsign');
  const locEl   = document.getElementById('setupLocator');
  const contEl  = document.getElementById('setupContest');
  const opEl    = document.getElementById('setupOperator');

  // Callsign : localStorage (config perso) prioritaire sur le serveur
  if(cfg.callsign_contest || cfg.callsign || serverCallsign)
    callEl.value = cfg.callsign_contest || cfg.callsign || serverCallsign;
  if(cfg.locator || serverLocator)
    locEl.value = cfg.locator || serverLocator;
  // Choix explicite utilisateur (localStorage) prioritaire sur le défaut serveur
  const contestToSet = cfg.contest || serverContest;
  if(contestToSet) csSetValue(contestToSet);

  // Injecter les vrais noms opérateurs depuis config
  const ops = cfg.operators || [];
  // SINGLE-OP : la section concours SO* (Single Operator) prime — un seul
  // opérateur, sélecteur inutile. On considère aussi single-op si la config
  // ne liste qu'un opérateur. Sinon (MO*) : le multi-op reste disponible.
  const isSingleOp = /^SO/i.test(cfg.section || '') || ops.length <= 1;
  if(ops.length){
    opEl.innerHTML = '<option value="">-- Sélectionne ton identifiant opérateur --</option>';
    ops.forEach((op, i) => {
      const val = `OP${i+1}`;
      const call = op.call || op.callsign || '';
      const lbl = call ? `${val} — ${call}${op.name?' ('+op.name+')':''}` : val;
      opEl.innerHTML += `<option value="${val}">${lbl}</option>`;
    });
    // Boutons OP du formulaire : vrai indicatif, et on masque les emplacements
    // sans indicatif configuré (plus de OP4/OP5 fantômes).
    document.querySelectorAll('.op-btn').forEach((btn, i) => {
      const call = ops[i] && (ops[i].call || ops[i].callsign);
      if(call){ btn.textContent = call; btn.style.display = ''; }
      else { btn.style.display = 'none'; }
    });
  }
  // Masquer tout ce qui est multi-op en single-op : sélecteur d'opérateur,
  // classement par opérateur, chat inter-postes. L'opérateur reste OP1.
  const opGroup = document.getElementById('opSelect').closest('.field-group');
  if(opGroup) opGroup.style.display = isSingleOp ? 'none' : '';
  const opStats = document.getElementById('opStatsBar');
  if(opStats) opStats.style.display = isSingleOp ? 'none' : '';
  const chatPanel = document.getElementById('chatPanel');
  if(chatPanel) chatPanel.style.display = isSingleOp ? 'none' : '';
  const peersInfo = document.getElementById('netPeers');
  if(peersInfo && isSingleOp){
    const wrap = peersInfo.closest('span'); if(wrap) wrap.style.display = 'none';
  }
  if(isSingleOp){
    myOp = 'OP1';
    const cur = document.getElementById('currentOp');
    if(cur) cur.textContent = (ops[0] && (ops[0].call || ops[0].callsign)) || cfg.callsign || 'OP1';
  }

  const modal = document.getElementById('setupModal');

  // Config complète → démarrage direct, sans afficher le modal
  if(callEl.value && locEl.value){
    if(!opEl.value) opEl.value = 'OP1';
    // modal reste caché (display:none par défaut)
    setupDone();
  } else {
    // Config incomplète → afficher le modal pour que l'utilisateur complète
    modal.style.display = 'flex';
  }
}

// ─── DÉMARRAGE AUTO DEPUIS CONFIG ────────────────────────────────────────────
// Appelé dès que la page est prête : si la config est complète, démarre sans modal
// ─── GPS → LOCATOR MAIDENHEAD ────────────────────────────────────────────────
function latLonToMaidenhead(lat, lon){
  lon += 180; lat += 90;
  const L = 'ABCDEFGHIJKLMNOPQRSTUVWX';
  let loc = '';
  loc += L[Math.floor(lon/20)];
  loc += L[Math.floor(lat/10)];
  loc += Math.floor((lon%20)/2).toString();
  loc += Math.floor(lat%10).toString();
  loc += L[Math.floor(((lon%20)%2)*12)];
  loc += L[Math.floor((lat%1)*24)];
  return loc.toUpperCase();
}

function getGPSLocator(){
  if(!navigator.geolocation){ notify('Géolocalisation non disponible dans ce navigateur.'); return; }
  const btn = document.querySelector('.gps-btn');
  if(btn) btn.textContent = '⏳…';
  navigator.geolocation.getCurrentPosition(pos=>{
    const loc = latLonToMaidenhead(pos.coords.latitude, pos.coords.longitude);
    const el = document.getElementById('setupLocator');
    if(el) el.value = loc;
    if(btn) btn.textContent = '📍 GPS';
    notify(`Locator GPS : ${loc}\n(${pos.coords.latitude.toFixed(4)}°N, ${pos.coords.longitude.toFixed(4)}°E)`);
  }, err=>{
    if(btn) btn.textContent = '📍 GPS';
    notify('Erreur GPS : ' + (err.message||err.code));
  }, {timeout:10000, enableHighAccuracy:true});
}

// ─── ALERTE DOUBLE-BANDE ──────────────────────────────────────────────────────
function crossBandAlert(call, band){
  const hint = document.getElementById('crossBandHint');
  if(!hint) return;
  if(!call || call.length < 3 || !band){ hint.classList.remove('show'); return; }
  const hasOnOther  = qsoLog.some(q => q.call === call && q.band !== band);
  const hasOnCurrent = qsoLog.some(q => q.call === call && q.band === band);
  if(hasOnOther && !hasOnCurrent){
    const worked = [...new Set(qsoLog.filter(q=>q.call===call&&q.band!==band).map(q=>BAND_LABELS[q.band]||q.band+' MHz'))];
    hint.textContent = `📡 Double-bande possible — déjà loggé en ${worked.join(', ')} !`;
    hint.classList.add('show');
  } else {
    hint.classList.remove('show');
  }
}

// ─── IMPORT ADIF ─────────────────────────────────────────────────────────────
function adifBandToMhz(band){
  const map = {'160m':'1.8','80m':'3.5','40m':'7','30m':'10','20m':'14','17m':'18','15m':'21',
    '12m':'24','10m':'28','6m':'50','4m':'70','2m':'144','70cm':'432','23cm':'1296',
    '13cm':'2320','9cm':'3400','6cm':'5760','3cm':'10368'};
  return map[(band||'').toLowerCase()] || band;
}

function importADIF(text){
  const records = text.split(/<EOR>/gi).map(r=>r.trim()).filter(r=>r.length>0);
  let imported = 0, skipped = 0;
  records.forEach(rec => {
    const get = tag => { const m = rec.match(new RegExp('<'+tag+':[^>]*>([^<]*)', 'i')); return m ? m[1].trim() : ''; };
    const call = get('CALL').toUpperCase();
    const freq = get('FREQ');                       // MHz (ADIF)
    // Bande depuis <BAND> ; à défaut, dérivée de la fréquence
    const band = adifBandToMhz(get('BAND')) || (freq ? bandFromFreq(freq) : '');
    const mode = get('MODE').toUpperCase() || 'SSB';
    const qsoDate = get('QSO_DATE');       // YYYYMMDD
    const timeOn  = (get('TIME_ON')+'0000').slice(0,4); // HHMM
    const loc     = get('GRIDSQUARE').toUpperCase().slice(0,6);
    const rst_sent = get('RST_SENT') || '59';
    const rst_rcvd = get('RST_RCVD') || '59';
    if(!call || !band){ skipped++; return; }
    if(isDup(call, band)){ skipped++; return; }
    const time = timeOn.slice(0,2)+':'+timeOn.slice(2,4);
    const date = qsoDate || nowDateUTC();
    const dist = (loc&&loc.length>=6) ? calcDist(loc) : 0;
    const pts  = calcPoints(loc, band, call, mode);
    const qso  = {
      id: Date.now() + imported,
      date, time, call, band, mode, freq,
      rst_sent, num_sent:'', rst_rcvd, num_rcvd:'',
      locator: loc, dist, points: pts,
      operator: myOp, my_call: myCall, my_locator: myLocator, contest: currentContest,
    };
    qsoLog.push(qso);
    imported++;
  });
  renderLog(); updateStats();
  notify(`Import ADIF terminé :\n✅ ${imported} QSO importés\n⏩ ${skipped} ignorés (doublons ou invalides)`);
}

function triggerImport(){
  const inp = document.createElement('input');
  inp.type = 'file'; inp.accept = '.adi,.adif,.ADI,.ADIF';
  inp.onchange = e => {
    const f = e.target.files[0]; if(!f) return;
    const reader = new FileReader();
    reader.onload = ev => importADIF(ev.target.result);
    reader.readAsText(f, 'UTF-8');
  };
  inp.click();
}

// ─── EXPORT ON4KST ────────────────────────────────────────────────────────────
function exportON4KST(){
  const entered = (document.getElementById('inputFreq')?.value || '').trim();
  const freq = entered || BAND_FREQ[currentBand] || (currentBand+' MHz');
  const msg = `${myCall} ${myLocator} ${freq} ${currentMode||'SSB'} CQ RPH`;
  navigator.clipboard.writeText(msg).then(()=>{
    const btn = document.querySelector('[onclick="exportON4KST()"]');
    if(btn){ const orig=btn.textContent; btn.textContent='✅ Copié !'; setTimeout(()=>btn.textContent=orig,2000); }
  }).catch(()=>{ prompt('Copier ce message ON4KST :', msg); });
}

// ─── SELF-SPOT (publier son spot sur le cluster DX avec sa fréquence) ─────────
async function selfSpot(){
  // Fréquence : champ saisi > radio (CAT) > fréquence d'appel de la bande
  let mhz = parseFloat(document.getElementById('inputFreq')?.value);
  if(!isFinite(mhz) || mhz <= 0){
    if(typeof rigState === 'object' && rigState && rigState.freq_khz > 0) mhz = rigState.freq_khz / 1000;
    else mhz = parseFloat(BAND_FREQ[currentBand] || '0');
  }
  if(!isFinite(mhz) || mhz <= 0){ notify('Fréquence inconnue — saisis-la dans le champ FRÉQUENCE.'); return; }
  const freq_khz = Math.round(mhz * 1000 * 10) / 10;   // MHz → kHz (commande DX Spider)
  if(!confirm(`Publier ce spot sur le cluster DX ?\n\n${myCall}   ${mhz.toFixed(3)} MHz   ${currentMode||''}\n\n`+
              `⚠️ Vérifie que l'auto-spot est autorisé par le règlement du concours.`)) return;
  const btn = document.getElementById('selfSpotBtn');
  const orig = btn ? btn.textContent : '';
  if(btn){ btn.disabled = true; btn.textContent = '📡 …'; }
  try{
    const r = await fetch('/cluster/spot', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({freq_khz, comment: 'CQ ' + ((currentContest||'').replace(/_/g,' '))})});
    const d = await r.json();
    if(d.ok && d.confirmed) notify(`📡 Spot publié et confirmé : ${myCall}  ${mhz.toFixed(3)} MHz`);
    else if(d.ok) notify(`📡 Spot envoyé (non confirmé par le nœud) : ${myCall}  ${mhz.toFixed(3)} MHz\nVérifie sur le cluster qu'il apparaît.`);
    else notify('❌ Self-spot : ' + (d.error || 'échec'));
  }catch(e){ notify('❌ ' + e.message); }
  finally{ if(btn){ btn.disabled = false; btn.textContent = orig || '📡 SELF-SPOT'; } }
}

// ─── RAPPEL PÉRIODIQUE ON4KST ─────────────────────────────────────────────────
let on4kstReminderTimer = null;
function hideON4KSTReminder(){
  const el = document.getElementById('on4kstReminder');
  if(el) el.classList.remove('show');
}
function startON4KSTReminder(){
  if(on4kstReminderTimer) return; // déjà démarré
  on4kstReminderTimer = setInterval(()=>{
    const n = new Date();
    const contestActive = contestStartUTC ? (n >= contestStartUTC && n < contestEndUTC) : (n < contestEndUTC);
    if(!contestActive) return;
    const el = document.getElementById('on4kstReminder');
    if(!el) return;
    el.classList.add('show');
    setTimeout(()=>el.classList.remove('show'), 20000); // auto-masquage après 20s
  }, 10 * 60 * 1000); // toutes les 10 minutes
}

// ─── BROADCAST CHANNEL (sync multi-onglet) ────────────────────────────────────
let _bc = null;
function initBroadcastChannel(){
  if(!window.BroadcastChannel) return;
  _bc = new BroadcastChannel('radiocontest_log');
  _bc.onmessage = ev => {
    const {type, data} = ev.data || {};
    if(type === 'add'){
      if(!qsoLog.find(q => q.id === data.id)){
        qsoLog.push(data);
        try{ renderLog(); }catch(e){}
        try{ updateStats(); }catch(e){}
      }
    } else if(type === 'delete'){
      if(qsoLog.find(q => q.id === data.id)){
        qsoLog = qsoLog.filter(q => q.id !== data.id);
        try{ renderLog(); }catch(e){}
        try{ updateStats(); }catch(e){}
      }
    }
  };
}
function bcBroadcast(type, data){
  if(_bc) try{ _bc.postMessage({type, data}); }catch(e){}
}

// Re-rendre les boutons bande/mode quand la config change dans un autre onglet
window.addEventListener('storage', e => {
  if(e.key === 'radiocontest_config'){
    renderBandButtons(currentContest);
    renderModeButtons(currentContest);
  }
  // Suivre le thème jour/nuit choisi dans un autre onglet (ex: radiocontest_configuration.html)
  if(e.key === 'rc_theme'){
    const day = e.newValue === 'day';
    document.body.classList.toggle('day-mode', day);
    const t = document.getElementById('themeToggle');
    if(t) t.textContent = day ? '🌙' : '☀️';
  }
});

// Empêche de quitter/rafraîchir la page par erreur pendant une session active
// (mais pas lors d'une navigation volontaire vers une autre page de l'appli,
// ex: clic sur CARTE IA / CONFIG dans la barre du haut)
let intentionalNavigation = false;
window.addEventListener('beforeunload', e => {
  if(!intentionalNavigation && isSetupDone && qsoLog.length > 0){
    e.preventDefault();
    e.returnValue = '';
  }
});

window.addEventListener('DOMContentLoaded', () => {
  init(); // charge calldb.json + config serveur + cluster, puis prefillSetupFromConfig()
  renderMacroPanel();
  loadSoapbox();
  initBroadcastChannel();
});

// ─── CARTE QSO (Leaflet) ──────────────────────────────────────────────────────
let qsoMap = null;
let homeMarker = null;
let mapLayers = [];   // markers + polylines dynamiques

const BAND_COLORS = {
  '1.8':   '#FF2D55',  // 160m rouge
  '3.5':   '#FF6B35',  // 80m  orange-rouge
  '7':     '#FF9F0A',  // 40m  orange
  '14':    '#FFD60A',  // 20m  jaune
  '21':    '#34C759',  // 15m  vert
  '28':    '#00C7BE',  // 10m  cyan-vert
  '50':    '#00D4FF',  // 6m   cyan
  '70':    '#40C8FF',  // 4m   bleu clair
  '144':   '#BF5AF2',  // 2m   violet
  '432':   '#FF8C00',  // 70cm orange-foncé
  '1296':  '#FF2D55',  // 23cm rose
  '2320':  '#00FF88',  // 13cm vert fluo
  '3400':  '#E040FB',  // 9cm  magenta
  'default':'#AAAAAA',
};

function initMap(){
  if(qsoMap) return;
  const homeLL = locLL(myLocator);
  const center = homeLL ? [homeLL.lat, homeLL.lon] : [46.5, 2.5];
  qsoMap = L.map('qsoMap', {zoomControl:true}).setView(center, 7);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
    attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom:14,
  }).addTo(qsoMap);
  // Marqueur station home
  if(homeLL){
    homeMarker = L.circleMarker([homeLL.lat, homeLL.lon],{
      radius:11, fillColor:'#FFD60A', color:'#000', weight:2,
      fillOpacity:1, zIndexOffset:1000,
    }).bindPopup(`<b>${myCall}</b><br>📍 ${myLocator}<br>Station HOME`).addTo(qsoMap);
  }
}

function refreshMapLayers(){
  if(!qsoMap) return;
  mapLayers.forEach(l => l.remove());
  mapLayers = [];
  const homeLL = locLL(myLocator);

  // Séparer contacts avec/sans locator
  const seen = {};
  const toPlot = [];
  let noLocCount = 0;
  qsoLog.slice().reverse().forEach(q => {
    if(!q.locator || q.locator.length < 6){ noLocCount++; return; }
    const key = q.call + '|' + q.locator;
    if(!seen[key]){ seen[key] = true; toPlot.push(q); }
  });

  toPlot.forEach(q => {
    const dxLL = locLL(q.locator);
    if(!dxLL) return;
    const col = BAND_COLORS[q.band] || BAND_COLORS['default'];
    const bandLabel = BAND_LABELS[q.band] || q.band + ' MHz';
    if(homeLL){
      const line = L.polyline([[homeLL.lat,homeLL.lon],[dxLL.lat,dxLL.lon]],{
        color:col, weight:1.8, opacity:.6, dashArray:'5 4',
      }).addTo(qsoMap);
      mapLayers.push(line);
    }
    const m = L.circleMarker([dxLL.lat,dxLL.lon],{
      radius:8, fillColor:col, color:'#000', weight:1.5, fillOpacity:.9,
    }).bindPopup(
      `<div style="font-family:monospace;font-size:14px;line-height:1.7">` +
      `<b style="font-size:15px">${q.call}</b><br>` +
      `📍 ${q.locator}<br>` +
      `📡 ${bandLabel} — ${q.mode}<br>` +
      `📏 ${q.dist||'?'} km — 🏆 ${q.points||0} pts` +
      `</div>`
    ).addTo(qsoMap);
    mapLayers.push(m);
  });

  let noLocInfo = document.getElementById('mapNoLocInfo');
  if(!noLocInfo){
    noLocInfo = document.createElement('div');
    noLocInfo.id = 'mapNoLocInfo';
    noLocInfo.style.cssText = 'position:absolute;bottom:10px;left:50%;transform:translateX(-50%);' +
      'background:rgba(0,0,0,.7);color:#aaa;font-size:14px;padding:4px 12px;border-radius:20px;z-index:999;pointer-events:none';
    document.getElementById('mapWrap').style.position = 'relative';
    document.getElementById('mapWrap').appendChild(noLocInfo);
  }
  noLocInfo.textContent = noLocCount > 0
    ? `⚠️ ${noLocCount} contact${noLocCount>1?'s':''} sans locator non affiché${noLocCount>1?'s':''}`
    : '';
  noLocInfo.style.display = noLocCount > 0 ? 'block' : 'none';
}

function toggleMapView(){
  const tableWrap = document.getElementById('logTableWrap');
  const mapWrap   = document.getElementById('mapWrap');
  const btn       = document.getElementById('mapToggleBtn');
  const showMap   = !mapWrap.classList.contains('visible');
  if(showMap){
    tableWrap.style.display = 'none';
    mapWrap.classList.add('visible');
    btn.classList.add('active');
    btn.textContent = '📋 TABLEAU';
    initMap();
    refreshMapLayers();
    setTimeout(() => qsoMap && qsoMap.invalidateSize(), 120);
  } else {
    mapWrap.classList.remove('visible');
    tableWrap.style.display = '';
    btn.classList.remove('active');
    btn.textContent = '🗺️ CARTE';
  }
}

// ─── INIT SERVEUR ─────────────────────────────────────────────────────────────
async function loadServerConfig(){
  try{
    const res = await fetch('/config');
    if(!res.ok) return;
    const cfg = await res.json();
    if(cfg.callsign)  serverCallsign = cfg.callsign;
    if(cfg.locator)   serverLocator  = cfg.locator;
    if(cfg.contest)   serverContest  = cfg.contest;
    // Mode expédition : partagé par le serveur → s'applique à tous les postes,
    // même ceux dont le navigateur n'a jamais ouvert la page CONFIG.
    serverExpeditionMode = cfg.expedition_mode || '';
    serverActivationProgram = cfg.activation_program || '';
    serverActivationRef = cfg.my_activation_ref || '';
    // Bouton SELF-SPOT : visible seulement si l'auto-spot est activé (config partagée)
    const ssBtn = document.getElementById('selfSpotBtn');
    if(ssBtn) ssBtn.style.display =
      (String(cfg.cluster_spot_enabled||'') && cfg.cluster_spot_enabled!=='0') ? '' : 'none';
  }catch(e){}
}

async function init(){
  await loadCallDB();
  await loadServerConfig();
  refreshCluster();
  setInterval(refreshCluster, 60000);
  prefillSetupFromConfig();
}

// ─── SÉLECTEUR CONCOURS FONCTIONS ────────────────────────────────────────────
function csToggle(){
  const panel = document.getElementById('csPanel');
  const btn   = document.getElementById('csTrigger');
  const open  = panel.classList.toggle('open');
  btn.classList.toggle('open', open);
  if(open) { document.getElementById('csSearch').value=''; csFilter(''); document.getElementById('csSearch').focus(); }
}

function csFilter(q){
  const list = document.getElementById('csList');
  q = q.toLowerCase();
  list.innerHTML = CS_DATA.map(grp=>{
    const items = grp.items.filter(it=> !q || it.l.toLowerCase().includes(q) || it.v.toLowerCase().includes(q));
    if(!items.length) return '';
    return `<div class="cs-group">${grp.g}</div>`
      + items.map(it=>`<div class="cs-option${it.v===document.getElementById('setupContest').value?' cs-selected':''}" data-val="${it.v}" onclick="csSelect('${it.v}','${it.l.replace(/'/g,'&#39;')}')">${it.l}</div>`).join('');
  }).join('') || `<div class="cs-empty">Aucun concours trouvé</div>`;
}

function csSelect(val, lbl){
  document.getElementById('setupContest').value = val;
  const trigLbl = document.getElementById('csTriggerLabel');
  trigLbl.textContent = lbl;
  trigLbl.style.color = 'var(--accent2)';
  // Fermer le panneau
  const panel = document.getElementById('csPanel');
  const btn   = document.getElementById('csTrigger');
  panel.classList.remove('open');
  btn.classList.remove('open');
  // Mettre à jour les horaires du concours
  updateContestTiming(val);
}

function csSetValue(val){
  const flat = [];
  CS_DATA.forEach(grp => grp.items.forEach(it => flat.push(it)));
  const item = flat.find(it => it.v === val);
  if(item) csSelect(val, item.l);
}

function updateContestTiming(contestId){
  const box = document.getElementById('contestTimingBox');
  if(!box) return;
  const sched = CONTEST_SCHEDULE[contestId];
  if(!sched || !sched.start){
    box.style.display = 'none';
    return;
  }
  const fmtUTC = iso => {
    const d = new Date(iso);
    const j = d.toLocaleDateString('fr-FR',{weekday:'short',day:'2-digit',month:'2-digit',year:'numeric',timeZone:'UTC'});
    const h = d.toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit',timeZone:'UTC'});
    return `${j} ${h} UTC`;
  };
  const fmtLocal = iso => {
    const d = new Date(iso);
    const j = d.toLocaleDateString('fr-FR',{weekday:'short',day:'2-digit',month:'2-digit',year:'numeric',timeZone:'Europe/Paris'});
    const h = d.toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Paris'});
    const tz = new Intl.DateTimeFormat('fr-FR',{timeZone:'Europe/Paris',timeZoneName:'short'}).formatToParts(new Date(iso)).find(p=>p.type==='timeZoneName').value;
    return `${j} ${h} (${tz})`;
  };
  const startEl = document.getElementById('ctStartUTC');
  const startLocEl = document.getElementById('ctStartLocal');
  const endEl = document.getElementById('ctEndUTC');
  const endLocEl = document.getElementById('ctEndLocal');
  const durEl = document.getElementById('ctDuration');
  if(startEl) startEl.textContent = fmtUTC(sched.start);
  if(startLocEl) startLocEl.textContent = fmtLocal(sched.start);
  if(endEl) endEl.textContent = fmtUTC(sched.end);
  if(endLocEl) endLocEl.textContent = fmtLocal(sched.end);
  if(durEl) durEl.textContent = sched.dur;
  const emailRow = document.getElementById('ctEmailRow');
  const emailEl  = document.getElementById('ctEmail');
  if(emailRow && emailEl){
    if(sched.email){ emailEl.textContent = sched.email; emailEl.href = `mailto:${sched.email}`; emailRow.style.display = 'block'; }
    else emailRow.style.display = 'none';
  }
  box.style.display = 'block';
}

// Fermer le sélecteur concours si clic en dehors
document.addEventListener('click', e => {
  const panel = document.getElementById('csPanel');
  const trigger = document.getElementById('csTrigger');
  if(panel && trigger && !panel.contains(e.target) && !trigger.contains(e.target)){
    panel.classList.remove('open');
    trigger.classList.remove('open');
  }
});

// ─── PANNEAU STATISTIQUES / RATE CHART ───────────────────────────────────────
function showRatePanel(){
  const ov = document.getElementById('rateOverlay');
  if(ov){ ov.classList.add('show'); renderRateChart(); }
}
function closeRatePanel(){
  const ov = document.getElementById('rateOverlay');
  if(ov) ov.classList.remove('show');
  if(window._rateChartInst){ window._rateChartInst.destroy(); window._rateChartInst = null; }
}
function switchRateTab(tab, btn){
  document.querySelectorAll('.rate-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('rateTabRate').style.display = tab === 'rate' ? '' : 'none';
  document.getElementById('rateTabBand').style.display = tab === 'band' ? '' : 'none';
  document.getElementById('rateTabHour').style.display = tab === 'hour' ? '' : 'none';
  if(tab === 'rate') renderRateChart();
  else if(tab === 'band') renderBandStats();
  else renderHourStats();
}
function renderRateChart(){
  if(typeof Chart === 'undefined'){ console.warn('Chart.js non chargé'); return; }
  const buckets = {};
  qsoLog.forEach(q => {
    if(!q.datetime) return;
    const h = q.datetime.slice(0,13);
    buckets[h] = (buckets[h]||0) + 1;
  });
  const labels = Object.keys(buckets).sort();
  const data = labels.map(k => buckets[k]);
  const ctx = document.getElementById('rateChart');
  if(!ctx) return;
  if(window._rateChartInst) window._rateChartInst.destroy();
  window._rateChartInst = new Chart(ctx, {
    type:'bar',
    data:{
      labels: labels.map(l => l.slice(11)+'h'),
      datasets:[{ label:'QSO/heure', data, backgroundColor:'rgba(0,212,255,.55)', borderColor:'#00D4FF', borderWidth:1 }]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      scales:{
        y:{ beginAtZero:true, ticks:{color:'#A9B0C8'}, grid:{color:'rgba(255,255,255,.05)'} },
        x:{ ticks:{color:'#A9B0C8'}, grid:{color:'rgba(255,255,255,.05)'} }
      },
      plugins:{ legend:{ labels:{ color:'#E9ECF5', font:{family:'Share Tech Mono'} } } }
    }
  });
}
function renderBandStats(){
  const body = document.getElementById('bandStatsBody');
  if(!body) return;
  const bands = {};
  qsoLog.forEach(q => {
    const b = q.band || currentBand || '?';
    if(!bands[b]) bands[b] = {qso:0, pts:0, mults:new Set()};
    bands[b].qso++;
    bands[b].pts += (Number(q.pts)||1);
    if(q.locator) bands[b].mults.add(q.locator.toUpperCase().slice(0,4));
  });
  const rows = Object.entries(bands).sort((a,b)=>parseFloat(a[0])-parseFloat(b[0]));
  const totQso = rows.reduce((s,[,v])=>s+v.qso,0);
  const totPts = rows.reduce((s,[,v])=>s+v.pts,0);
  const totScore = rows.reduce((s,[,v])=>s+v.pts*v.mults.size,0);
  body.innerHTML = rows.map(([b,s])=>{
    const sc = s.pts*s.mults.size;
    return `<tr><td>${b}m</td><td>${s.qso}</td><td>${s.pts}</td><td>${s.mults.size}</td><td>${sc}</td></tr>`;
  }).join('') + (rows.length?`<tr><td>TOTAL</td><td>${totQso}</td><td>${totPts}</td><td>—</td><td>${totScore}</td></tr>`:'')
    || '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:18px">Aucun QSO — saisis un indicatif dans le panneau SAISIE et appuie sur Entrée 🎙</td></tr>';
}
function renderHourStats(){
  const head = document.getElementById('hourHead');
  const body = document.getElementById('hourBody');
  if(!head||!body) return;
  const allBands = [...new Set(qsoLog.map(q=>q.band||currentBand||'?'))].sort((a,b)=>parseFloat(a)-parseFloat(b));
  const rows = {};
  qsoLog.forEach(q => {
    if(!q.datetime) return;
    const h = q.datetime.slice(11,13)+'h';
    const b = q.band||currentBand||'?';
    if(!rows[h]) rows[h]={};
    rows[h][b] = (rows[h][b]||0)+1;
  });
  head.innerHTML = '<tr><th>HEURE</th>'+allBands.map(b=>`<th>${b}m</th>`).join('')+'<th>TOTAL</th></tr>';
  const sorted = Object.entries(rows).sort((a,b)=>a[0].localeCompare(b[0]));
  body.innerHTML = sorted.map(([h,bs])=>{
    const tot = Object.values(bs).reduce((a,c)=>a+c,0);
    return `<tr><td>${h}</td>${allBands.map(b=>`<td>${bs[b]||0}</td>`).join('')}<td>${tot}</td></tr>`;
  }).join('') || '<tr><td colspan="99" style="text-align:center;color:var(--muted);padding:18px">Aucun QSO</td></tr>';
}
