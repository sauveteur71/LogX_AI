/* LogX AI — logique du logbook multi-opérateur.
   Externalisé de logx_logbook.html (le HTML ne contient plus
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
          <div style="background:#13152A;border:2px solid #FF5030;border-radius:10px;padding:20px;margin-bottom:24px">
            <div style="color:#A9B0C8;font-size:14px;margin-bottom:10px">ÉTAPE 1 — Lance le serveur dans un terminal :</div>
            <div style="color:#00FF88;font-size:17px;font-weight:700;letter-spacing:1px">cd "C:\\Users\\parri\\SynologyDrive\\RADIOAMATEUR\\Activites\\Rallye des point haut\\concours"</div>
            <div style="color:#00FF88;font-size:17px;font-weight:700;margin-top:8px">python logx_serveur.py</div>
          </div>
          <div style="background:#13152A;border:2px solid #00D4FF;border-radius:10px;padding:20px;margin-bottom:30px">
            <div style="color:#A9B0C8;font-size:14px;margin-bottom:10px">ÉTAPE 2 — Accède via cette adresse :</div>
            <a href="http://127.0.0.1:8080/logx_logbook.html" style="color:#00D4FF;font-size:20px;font-weight:700;text-decoration:none;letter-spacing:1px">http://127.0.0.1:8080/logx_logbook.html</a>
          </div>
          <a href="http://127.0.0.1:8080/logx_logbook.html"
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

// Repli config serveur (renseignés par loadServerConfig(), voir plus bas) —
// déclarés ici avec une valeur par défaut : sans ça, tant que loadServerConfig()
// n'a pas trouvé de valeur non vide à assigner (ex. aucun concours configuré
// côté serveur), lire ces identifiants via `cfg.x || serverX` levait une
// ReferenceError (variable jamais déclarée) qui interrompait silencieusement
// prefillSetupFromConfig() AVANT setupDone() — bandes/modes/opérateur ne se
// mettaient alors jamais à jour selon la config réelle.
let serverCallsign = '';
let serverLocator = '';
let serverContest = '';

// Lire le concours depuis la config sauvegardée (logx_configuration.html) ou défaut VHF
(function initFromConfig(){
  try{
    const cfg = JSON.parse(localStorage.getItem('logx_config')||'{}');
    if(cfg.contest) window._initContest = cfg.contest;
    if(cfg.locator) window._initLocator = cfg.locator;
    if(cfg.callsign_contest||cfg.callsign) window._initCall = cfg.callsign_contest||cfg.callsign;
  }catch(e){}
})();

// ─── POINTS : uniquement si un concours est sélectionné ──────────────────────
// Miroir EXACT de contest_actif() (logx_storage.py) : faux en mode 'simple',
// faux aussi en mode concours tant qu'aucun concours n'est choisi. Sans
// concours, currentContest retombe sur 'REF_RPH' (voir juste dessous) et le
// barème produit 1 pt/km : un total parfaitement calculé, mais qu'aucun
// règlement ne compte. On ne l'affiche donc pas. Les pages qui reçoivent déjà
// un payload serveur (CARTE, CHASSE, panneau détaché) lisent le drapeau
// calculé par le serveur ; le logbook, lui, totalise localement — d'où ce
// miroir. Si la règle change côté serveur, elle doit changer ICI aussi.
function contestActif(){
  let cfg = {};
  try{ cfg = JSON.parse(localStorage.getItem('logx_config')||'{}'); }catch(e){}
  return cfg.usage_mode !== 'simple' && !!String(cfg.contest||'').trim();
}
// Pose/retire la classe qui masque les affichages de points (règles CSS
// body.sans-concours dans logx_logbook.html).
function applyContestActifToLogbook(){
  if(document.body) document.body.classList.toggle('sans-concours', !contestActif());
}

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
                     def_s:'14', ph_r:'zone 1-40', check:'cq_zone',
                     ml_s:3, ml_r:3, auto_serial:false, clear_s:false, pad_r:false },
  'CQ_WW_CW':      { label_s:'ZONE ENV', label_r:'ZONE RCU',
                     def_s:'14', ph_r:'zone 1-40', check:'cq_zone',
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
  // ── World Wide Award : échange = SEULEMENT le report (RS/RST), aucun n°
  // de série ni zone/dept (règlement §3) — no_exchange masque le champ N°
  // entièrement (cf. applyExpeditionMode()), même hors mode expédition.
  'WWA_2027_JAN':  { label_s:'N° ENVOYÉ', label_r:'N° REÇU', def_s:'', ph_r:'',
                     ml_s:4, ml_r:4, auto_serial:false, clear_s:false, pad_r:false, no_exchange:true },
  'WWA_2027_JUL':  { label_s:'N° ENVOYÉ', label_r:'N° REÇU', def_s:'', ph_r:'',
                     ml_s:4, ml_r:4, auto_serial:false, clear_s:false, pad_r:false, no_exchange:true },
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
  if(typeof clearExchWarn === 'function') clearExchWarn();   // change de concours : avertissement zone périmé
}

// ─── MODE EXPÉDITION : saisie simplifiée (indicatif + RST env/reçu seulement) ──
// En pile-up d'expédition (chasse DX/activation POTA-SOTA... SANS concours
// réel) l'échange est juste le report : on masque les champs N° de série et
// locator pour ne garder que l'essentiel et enchaîner très vite.
let expeditionMode = false;
function applyExpeditionMode(on){
  expeditionMode = (String(on) === '1' || on === true);
  const numRow = document.getElementById('numFieldRow');
  const locGrp = document.getElementById('locatorGroup');
  // Un VRAI concours sélectionné (REF/IARU/CQ...) impose son propre échange —
  // le masquer ferait perdre le n° de série et/ou le locator nécessaires au
  // calcul du score (ex: REF_CCD noté en km × locators -> 0 pt logué sans
  // locator correspondant). La saisie simplifiée ne doit donc s'appliquer que
  // hors concours réel (activation POTA/SOTA/... ou aucun concours choisi).
  const realContestExchange = !!currentContest && !activationProgram;
  // Certains concours réels n'ont PAS de n° de série du tout (ex. World Wide
  // Award : juste un report, règlement §3) — currentExchange.no_exchange le
  // signale explicitement (cf. applyExchangeFormat, déjà appelé avant ceci) :
  // masquer le champ N° reste correct même si realContestExchange est vrai.
  const noExchange = currentExchange && currentExchange.no_exchange === true;
  // Le n° de série (échange concours) est aussi masqué en LOGBOOK SIMPLE (pas
  // de concours -> pas d'échange à faire), indépendamment du mode expédition.
  const hideNum = (expeditionMode && !realContestExchange) || usageMode === 'simple' || noExchange;
  const hideLoc = expeditionMode && !realContestExchange;
  if(numRow) numRow.style.display = hideNum ? 'none' : '';
  if(locGrp) locGrp.style.display = hideLoc ? 'none' : '';
  document.body.classList.toggle('expedition-on', expeditionMode);
}

// ─── MODE D'UTILISATION (simple / concours / expédition) ────────────────────
// Réglé une seule fois dans CONFIG (logx_configuration.html), lu ici
// pour adapter la saisie : en LOGBOOK SIMPLE, pas de concours -> le sélecteur
// de concours et son horaire n'ont pas de sens et sont masqués.
let usageMode = 'contest';

// Les bandeaux de RYTHME (score, récap par bande, classement opérateurs,
// graphe QSO/heure) sont-ils hors sujet dans le mode courant ?
//
// POINT UNIQUE EXPRÈS : la règle est appliquée à QUATRE endroits —
// applyUsageModeToLogbook() au changement de mode, et les trois fonctions de
// rendu qui repositionnent leur bandeau à chaque rafraîchissement des stats.
// Écrite quatre fois, elle divergerait : masquer au changement de mode ne
// servirait à rien puisque le premier calcul de stats ferait réapparaître les
// bandeaux. C'est précisément ce qui serait arrivé au mode expédition.
function bandeauxRythmeMasques(){
  // Expédition : ni score à suivre, ni temps restant, ni classement à
  // départager — on log en continu pendant des jours. Les 310 px mesurés que
  // ces bandeaux occupent manquent bien davantage à la saisie, surtout sur un
  // portable en /P.
  return usageMode === 'simple' || usageMode === 'expedition';
}

// ─── Menu DÉBUT / FIN ────────────────────────────────────────────────────────
// DEMANDE UTILISATEUR : « le logbook a énormément d'icônes qui ne servent
// qu'à la fin d'un concours ou au début ; épure cette page. » Compté avant de
// trancher : 30 commandes, dont 11 utilisées uniquement AVANT ou APRÈS
// l'épreuve — la moitié de la barre, encombrée pendant tout le trafic.
//
// Le contenu S'ADAPTE AU MODE : en logbook simple il n'y a ni règlement, ni
// score, ni log à soumettre — proposer EDI, VÉRIFIER ou ARCHIVER n'y a aucun
// sens et ne ferait qu'égarer. C'est le pendant côté écran du travail fait
// côté serveur dans logx_mode.py.
// `format` : 'EDI' ou 'CABRILLO', celui que l'organisateur attend. Passé en
// paramètre — et non lu dans l'état global — pour que cette fonction reste
// PURE : elle est exécutée seule, dans un V8 nu, par le test du menu.
function itemsMenuLogbook(format){
  const concours = contestActif();
  const grp = [];
  const avant = [];
  if(concours) avant.push(['✅', 'CHECKLIST', 'showChecklist']);
  avant.push(['📂', 'IMPORTER un log (ADIF — N1MM+, Win-Test, DXLog, Log4OM, Cloudlog, LoTW...)', 'triggerImport']);
  grp.push(['AVANT LA SESSION', avant]);

  const suivi = [['📊', 'STATS — rythme et répartition', 'showRatePanel'],
                 ['🏅', 'DIPLÔMES & QSL', 'showAwards'],
                 ['🔎', 'FILTRE AVANCÉ', 'openFilterBuilder'],
                 ['🧬', 'RECHERCHE DE DOUBLONS', 'openDupFinder'],
                 ['🌐', 'RE-RÉSOUDRE (locator/état)', 'openBulkResolve'],
                 ['📋', 'CONTRÔLE DE NET', 'openNetControl']];
  grp.push(['SUIVI', suivi]);

  const apres = [];
  if(concours){
    apres.push(['🔍', 'VÉRIFIER le log avant envoi', 'showValidation']);
    // Le libellé dit le format que l'organisateur ATTEND. « Exporter EDI » était
    // affiché pour tous les concours, y compris les vingt-six qui déposent en
    // Cabrillo — et pour dix-sept d'entre eux le bouton ne produisait rien.
    // Le format arrive en PARAMÈTRE : cette fonction doit rester pure, elle est
    // exécutée seule dans un V8 nu par test_logbook_menu_debut_fin.py.
    apres.push(['📥', format === 'EDI' ? 'Exporter le log (EDI)'
                                       : 'Exporter le log (Cabrillo)', 'exportEDI']);
  }
  apres.push(['📥', 'Exporter ADIF', 'exportADIF']);
  apres.push(['📥', 'Exporter CSV', 'exportCSV']);
  if(concours) apres.push(['📦', 'ARCHIVER ce concours', 'archiveLog']);
  apres.push(['💾', 'SAUVEGARDER maintenant', 'backupNow']);
  if(concours) apres.push(['📡', 'Message ON4KST', 'exportON4KST']);
  grp.push(['APRÈS LA SESSION', apres]);

  grp.push([null, [['🗑️', 'NOUVEAU LOG (efface le log actif)', 'resetLog', true]]]);
  return grp;
}

// Sous-fonctions de maintenance/analyse avancée du menu SUIVI — masquées en
// mode UI « simple » (cf. logx_statusbar.js/.expert-only) car sans rapport
// avec la saisie d'un premier QSO ; endpoints et fonctions restent joignables,
// seul ce bouton de menu est masqué (réversible en repassant en mode expert).
const MENU_LB_EXPERT_ONLY_FN = new Set(['openFilterBuilder', 'openDupFinder', 'openBulkResolve', 'openNetControl']);

function buildLbMenu(){
  const dd = document.getElementById('lbMenuDD');
  if(!dd) return;
  const esc = s => String(s).replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let h = '';
  itemsMenuLogbook(formatDepot()).forEach(([titre, items], i) => {
    if(!items.length) return;
    if(i) h += '<hr>';
    // window.rcT et PAS rcT : une variable non déclarée lève une
    // ReferenceError, un accès de propriété rend undefined. Le menu se
    // construit avant que le moteur i18n soit forcément là.
    if(titre) h += '<div class="grp">'
                 + esc(window.rcT ? window.rcT(titre) : titre) + '</div>';
    items.forEach(([ico, lbl, fn, danger]) => {
      const cls = [danger ? 'danger' : '', MENU_LB_EXPERT_ONLY_FN.has(fn) ? 'expert-only' : '']
        .filter(Boolean).join(' ');
      h += '<button class="' + cls + '" data-fn="' + esc(fn) + '">'
         + '<span class="ico">' + ico + '</span>' + esc(lbl) + '</button>';
    });
  });
  dd.innerHTML = h;
  dd.querySelectorAll('button[data-fn]').forEach(b => {
    b.onclick = () => {
      fermerLbMenu();
      const f = window[b.dataset.fn];
      if(typeof f === 'function') f();
    };
  });
}

function fermerLbMenu(){
  const dd = document.getElementById('lbMenuDD');
  if(dd) dd.style.display = 'none';
}

function toggleLbMenu(ev){
  if(ev) ev.stopPropagation();
  const dd = document.getElementById('lbMenuDD');
  if(!dd) return;
  const ouvert = dd.style.display !== 'none';
  if(ouvert){ fermerLbMenu(); return; }
  buildLbMenu();          // reconstruit à l'ouverture : le mode a pu changer
  dd.style.display = 'block';
}
// Un menu qui ne se referme pas au clic à côté reste en travers du log.
document.addEventListener('click', e => {
  if(!e.target.closest || !e.target.closest('#lbMenu')) fermerLbMenu();
});
document.addEventListener('keydown', e => { if(e.key === 'Escape') fermerLbMenu(); });

function applyUsageModeToLogbook(mode){
  usageMode = mode || 'contest';
  const simple = usageMode === 'simple';
  buildLbMenu();   // le contenu du menu dépend du mode
  const sansBandeaux = bandeauxRythmeMasques();
  const csWrap = document.getElementById('contestSearchWrap');
  if(csWrap) csWrap.style.display = simple ? 'none' : '';
  const timingBox = document.getElementById('contestTimingBox');
  if(simple && timingBox) timingBox.style.display = 'none';
  // LOGBOOK SIMPLE : la bannière score (QSO/heure, doublons, temps restant,
  // dernier QSO...) n'a de sens que pour le rythme/la compétition d'un
  // concours chronométré — rien de tout ça ne s'applique à un log personnel.
  const scoreBanner = document.querySelector('.score-banner');
  if(scoreBanner) scoreBanner.style.display = sansBandeaux ? 'none' : '';
  // Même logique pour le récap par bande, le classement opérateurs et le
  // graphe QSO/heure : ce sont des outils de rythme de concours, sans
  // intérêt pour un log personnel hors concours.
  //
  // Le ternaire RESTAURE l'affichage, là où l'ancien `if(el && simple)` se
  // contentait de masquer : repasser en mode CONCOURS laissait les trois
  // bandeaux définitivement invisibles jusqu'au rechargement de la page —
  // un réglage qu'on ne peut plus annuler depuis l'écran où on l'a fait.
  ['bandRecapBar', 'opStatsBar', 'hourChartBar'].forEach(id => {
    const el = document.getElementById(id);
    if(el) el.style.display = sansBandeaux ? 'none' : '';
  });
  // Les boutons de filtre rapide 144/432 MHz ciblent un concours VHF/UHF
  // précis : sans intérêt (et souvent hors sujet) en logbook simple.
  document.querySelectorAll('.filter-btn[data-f="144"], .filter-btn[data-f="432"]')
    .forEach(btn => { btn.style.display = simple ? 'none' : ''; });
  // ARCHIVER clôture le log d'UN concours dans un dossier permanent (Cabrillo/
  // ADIF/résumé) — sans objet en logbook simple, qui n'a pas de concours à
  // clôturer (log personnel continu). La règle vit désormais dans
  // itemsMenuLogbook() : la commande n'est plus un bouton de la barre qu'on
  // masque, elle n'est tout simplement pas proposée dans le menu.
  document.body.classList.toggle('usage-simple', simple);
  // Appliqué aussi ici : updateStats() ne tourne qu'une fois le log chargé,
  // or la colonne PTS du tableau et le compas existent dès l'ouverture.
  applyContestActifToLogbook();
}

// ─── ACTIVATION POTA/SOTA/IOTA/WWFF/ARLHS/WCA ────────────────────────────────
const ACT_MIN = {POTA:10, SOTA:4, IOTA:1, WWFF:44, ARLHS:2, WCA:50};
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
    // Auto-spot : POTA (cf. logx_pota.post_spot) et SOTA (cf.
    // logx_sota_spot.post_spot, connexion SOTA SSO + clientId à configurer
    // dans CONFIG — reste inactif tant que ce n'est pas fait, le clic
    // renvoie alors un message d'erreur explicite plutôt que de rester masqué
    // en silence). WWFF/IOTA restent masqués : aucun endpoint POST documenté
    // avec certitude pour ces deux-là.
    const sb = document.getElementById('actSpotBtn');
    if(sb) sb.style.display = (activationProgram === 'POTA' || activationProgram === 'SOTA') ? '' : 'none';
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

// Calcule dynamiquement le prochain week-end RPH (1er samedi de juillet 14h UTC
// → dimanche 14h UTC), en basculant sur l'année suivante si celui de l'année en
// cours est déjà passé. Miroir JS de date_rule='first_saturday_july' défini
// côté serveur pour REF_RPH (logx_definitions.py / logx_rules.calc_contest_date)
// — à maintenir en cohérence si cette règle REF change un jour. Remplace une
// ancienne date figée en dur qui périmait à chaque édition (repli cassé une
// fois le week-end de l'année passé).
// Déclarée en `function` (hoisting complet) pour rester utilisable dans
// CONTEST_SCHEDULE ci-dessous malgré l'ordre d'apparition dans le fichier.
function nextRPHWeekendUTC(now){
  now = now || new Date();
  function firstSaturdayOfJulyUTC(year){
    const dowJuly1 = new Date(Date.UTC(year, 6, 1)).getUTCDay(); // 0=dim..6=sam
    const day = 1 + ((6 - dowJuly1 + 7) % 7);
    return Date.UTC(year, 6, day, 14, 0, 0);
  }
  let year  = now.getUTCFullYear();
  let start = firstSaturdayOfJulyUTC(year);
  let end   = start + 24*3600*1000;
  if(end <= now.getTime()){ // édition de cette année déjà terminée → année suivante
    year += 1;
    start = firstSaturdayOfJulyUTC(year);
    end   = start + 24*3600*1000;
  }
  return {start: new Date(start), end: new Date(end)};
}

// ─── HORAIRES CONCOURS ────────────────────────────────────────────────────────
// Format : {start:'ISO', end:'ISO', dur:'durée texte'}
// Déclaré tôt : référencé dès le chargement par updateClockAndCountdown() (appel
// synchrone immédiat plus bas) — un const référencé avant sa ligne d'init lève
// une ReferenceError (TDZ), même via un simple `typeof`.
const CONTEST_SCHEDULE = {
  'REF_RPH':      (()=>{ const w = nextRPHWeekendUTC();
                          return {start:w.start.toISOString(), end:w.end.toISOString(), dur:'24h', email:'rph@r-e-f.org'}; })(),
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

let currentFilter = 'all';
let advancedFilter = null;  // {groups:[[{field,op,value},...],...]} — OU entre groupes, ET dans un groupe

// Moteur de correspondance du filtre avancé : reste ICI (pas dans
// logx_filter_builder.js, qui n'a que l'UI du popup/les préréglages) parce
// que renderLog() -- chemin critique, jamais déplacé -- en dépend
// directement (voir plus bas). Le popup de CONSTRUCTION du filtre
// (logx_filter_builder.js) l'utilise aussi, comme n'importe quelle fonction
// globale (EV-7, docs/LogX_AI_PRD.md — trouvé en revue adversariale : le
// sens inverse, avec le moteur dans logx_filter_builder.js, faisait
// dépendre le rendu du log CŒUR d'un fichier "fonctionnalité optionnelle").
const FILTER_FIELDS = [
  {key:'call', label:'Indicatif', type:'text'},
  {key:'band', label:'Bande', type:'text'},
  {key:'mode', label:'Mode', type:'text'},
  {key:'freq', label:'Fréquence (MHz)', type:'num'},
  {key:'rst_sent', label:'RST envoyé', type:'text'},
  {key:'rst_rcvd', label:'RST reçu', type:'text'},
  {key:'num_sent', label:'N° envoyé', type:'text'},
  {key:'num_rcvd', label:'N° reçu', type:'text'},
  {key:'date', label:'Date', type:'text'},
  {key:'time', label:'Heure', type:'text'},
  {key:'locator', label:'Locator', type:'text'},
  {key:'dist', label:'Distance (km)', type:'num'},
  {key:'points', label:'Points', type:'num'},
  {key:'operator', label:'Opérateur', type:'text'},
  {key:'contest', label:'Concours', type:'text'},
  {key:'state', label:'État/région', type:'text'},
  {key:'qsl_scan', label:'Scan QSL', type:'bool'},
];
const FILTER_OPS = {
  text: [['contains','contient'], ['ncontains','ne contient pas'], ['eq','= exact'], ['neq','≠'], ['starts','commence par']],
  num:  [['eq','='], ['neq','≠'], ['gt','>'], ['lt','<'], ['gte','≥'], ['lte','≤']],
  bool: [['present','renseigné'], ['absent','vide']],
};
function fltFieldDef(key){ return FILTER_FIELDS.find(f=>f.key===key) || FILTER_FIELDS[0]; }

function matchesFilterCondition(q, cond){
  const def = fltFieldDef(cond.field);
  const raw = q[cond.field];
  if(def.type === 'bool'){
    const has = !!raw;
    return cond.op === 'present' ? has : !has;
  }
  if(def.type === 'num'){
    const a = parseFloat(raw), b = parseFloat(cond.value);
    if(isNaN(a) || isNaN(b)) return false;
    switch(cond.op){
      case 'eq': return a === b;
      case 'neq': return a !== b;
      case 'gt': return a > b;
      case 'lt': return a < b;
      case 'gte': return a >= b;
      case 'lte': return a <= b;
    }
    return true;
  }
  const a = String(raw==null?'':raw).toUpperCase();
  const b = String(cond.value==null?'':cond.value).toUpperCase();
  switch(cond.op){
    case 'contains': return a.includes(b);
    case 'ncontains': return !a.includes(b);
    case 'eq': return a === b;
    case 'neq': return a !== b;
    case 'starts': return a.startsWith(b);
  }
  return true;
}

function matchesAdvancedFilter(q, tree){
  if(!tree || !Array.isArray(tree.groups) || !tree.groups.length) return true;
  return tree.groups.some(group => !group.length || group.every(cond => matchesFilterCondition(q, cond)));
}

let qsoLog = [];       // log local (cache)
let serialByBand = {}; // numéros de série par bande
let refreshTimer = null;
let isSetupDone = false;

const OP_COLORS = {OP1:'op-1',OP2:'op-2',OP3:'op-3',OP4:'op-4',OP5:'op-5'};
// Au-delà de OP5 (mode RADIOCLUB, jusqu'à 40 opérateurs) : les 5 classes CSS
// historiques ne suffisent plus — teinte générée par index, style inline.
// 47° n'est pas un diviseur de 360 : les teintes ne se répètent pas avant
// d'avoir couvert tout le cercle chromatique, même sur une quarantaine d'index.
function opColorAttr(opValue){
  const cls = OP_COLORS[opValue];
  if(cls) return {cls, style:''};
  const idx = parseInt(String(opValue||'').replace(/^OP/i,''), 10);
  if(!idx || idx < 1) return {cls:'', style:''};
  const hue = ((idx-1) * 47) % 360;
  return {cls:'', style:`background:hsla(${hue},80%,55%,.3);color:hsl(${hue},80%,68%);border:1px solid hsla(${hue},80%,55%,.4)`};
}

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

// ─── SCORING PILOTÉ PAR LE SERVEUR (briques) ─────────────────────────────────
// Le logbook lit les définitions de scoring de /data/calendar (moteur à briques
// de logx_scoring.py) au lieu de dupliquer les barèmes en dur : tout
// concours de la base — y compris ceux analysés par l'IA — est scoré juste.
// La table codée en dur plus bas ne sert plus que de repli hors-ligne.
let contestScoringDefs = {};   // id concours → bloc scoring (type/params/bricks)
// Les règles de DÉPÔT du concours (format du fichier, adresse, date limite).
// Elles voyagent déjà dans /data/calendar mais n'étaient conservées nulle part :
// l'export retombait sur une liste d'identifiants écrite à la main.
let contestDepotDefs = {};     // id concours → {log_format, log_submit, log_deadline}

async function loadScoringDefs(){
  try{
    const res = await fetch('/data/calendar');
    const data = await res.json();
    (data.contests || []).forEach(c => {
      if (c.scoring) contestScoringDefs[c.id] = c.scoring;
      contestDepotDefs[c.id] = {log_format: c.log_format || '',
                                log_submit: c.log_submit || '',
                                log_deadline: c.log_deadline || ''};
    });
    console.log(`[SCORING] ${Object.keys(contestScoringDefs).length} barèmes chargés du serveur`);
  }catch(e){ console.warn('[SCORING] serveur indisponible, barèmes locaux :', e); }
}

// ── LE FORMAT DE DÉPÔT VIENT DU RÈGLEMENT, PAS D'UNE LISTE ÉCRITE À LA MAIN ──
// Le routage se faisait sur HF_CONTESTS, douze identifiants codés en dur, alors
// que VINGT-SIX définitions déclarent `log_format: 'CABRILLO'`. Mesuré sur la
// base livrée : dix-sept concours Cabrillo — WAEDC CW/SSB/RTTY, ARRL 10 m et
// 160 m, Russian DX, EU HF Championship, All Asian, Stew Perry, UBA, SP, HA,
// REF 160 m, les deux UFT Challenge — tombaient dans la branche EDI et
// n'obtenaient AUCUN fichier : « Aucun QSO VHF/UHF à exporter ». Au moment du
// dépôt, veille de date limite. Trois identifiants de cette liste n'existaient
// même pas (IARU_HF, WAE_CW, WAE_SSB : les vrais sont WAEDC_*).
const REPLI_FORMAT_DEPOT = {EDI: 'EDI', CABRILLO: 'CABRILLO', ADIF: 'ADIF'};

function formatDepot(contestId){
  const d = contestDepotDefs[contestId || currentContest] || {};
  const f = REPLI_FORMAT_DEPOT[String(d.log_format || '').toUpperCase()];
  if (f) return f;
  // Définition muette (3 sur 41) ou serveur injoignable au moment du clic :
  // on déduit des bandes RÉELLEMENT présentes dans le log plutôt que de
  // deviner d'après l'identifiant. L'EDI est le format des concours THF.
  return estConcoursThf() ? 'EDI' : 'CABRILLO';   // BANDES_THF, plus bas
}

// Presets points-only des types historiques — miroir de LEGACY_SCORING_PRESETS
// (logx_scoring.py), briques 'points'/'validity'/'same_square_points'.
const LEGACY_JS_BRICKS = {
  km:                        {points:[{points:'per_km'}]},
  km_x_locators:             {points:[{points:'per_km'}]},
  km_x_large_locator_squares:{points:[{points:'per_km'}], same_square_points:{param:'same_square_bonus', default:50}},
  zone_country_per_band:     {points:[{when:'same_country', points:{param:'points_same_country', default:0}},
                                      {when:'same_continent', points:{param:'points_same_continent', default:1}},
                                      {points:{param:'points_dx', default:3}}]},
  prefix_multiplier:         {points:[{when:'different_continent', points:{param:'points_dx', default:3}},
                                      {when:'same_country', points:{param:'points_same_country', default:1}},
                                      {points:{param:'points_same_continent', default:1}}]},
  prefix:                    {points:[{when:'different_continent', points:6},
                                      {when:'na_w_ve', points:2}, {points:1}]},
  power_state:               {points:[{points:{param:'points', default:3}}], validity:'is_na'},
  fd_class:                  {points:[{modes:['CW'], points:2},
                                      {modes:['FT8','FT4','RTTY','PSK'], points:2},
                                      {points:{param:'points_phone', default:1}}], validity:'is_na'},
  dept_dxcc:                 {points:[{when:'is_french', points:1}, {points:3}]},
  summit_points:             {points:[{points:{param:'points', default:1}}]},
  park_points:               {points:[{points:{param:'points', default:1}}]},
  // World Wide Award (hamaward.cloud) : points fixes par mode — miroir de
  // LEGACY_SCORING_PRESETS['wwa_sprint'] (logx_scoring.py). validity.roster_check
  // n'est PAS vérifiable côté client (pas de re-fetch réseau à chaque frappe) :
  // retour optimiste ici, le serveur (need-list /data/spots_ranked) reste seul
  // juge de la validité réelle d'une station.
  wwa_sprint:                {points:[{modes:['CW'], points:10},
                                      {modes:['SSB','USB','LSB','FM'], points:5},
                                      {modes:['FT8','FT4','FT2'], points:2},
                                      {modes:['RTTY','PSK','DIGI'], points:5},
                                      {points:5}],
                              validity:{roster_check:'wwa'}},
};

const _NA_CALL_RE = /^(W|K|N|AA|AB|AC|AD|AE|AF|AG|AH|AI|AJ|AK|WA|WB|WC|WD|WE|WF|WG|WH|WI|WJ|WK|WL|WM|WN|WO|WP|WQ|WR|WS|WT|WU|WV|WW|WX|WY|WZ|KA|KB|KC|KD|KE|KF|KG|KH|KI|KJ|KK|KL|KM|KN|KO|KP|KQ|KR|KS|KT|KU|KV|KW|KX|KY|KZ|NA|NB|NC|ND|NE|NF|NG|NH|NI|NJ|NK|NL|NM|NN|NO|NP|NQ|NR|NS|NT|NU|NV|NW|NX|NY|NZ|VE|VA|VO|VY)/i;

function _brickCtx(callDX){
  const dxBase = (callDX || '').toUpperCase().split('/')[0];
  const myBase = (myCall || '').toUpperCase().split('/')[0];
  const dxInfo = lookupDXCC(dxBase), myInfo = lookupDXCC(myBase);
  return {
    dxBase,
    dxCountry: dxInfo ? dxInfo.c : (dxBase.slice(0,2) || '??'),
    myCountry: myInfo ? myInfo.c : (myBase.slice(0,2) || 'F'),
    dxCont: (dxInfo && dxInfo.ct) || 'EU',
    myCont: (myInfo && myInfo.ct) || 'EU',
  };
}

const BRICK_PREDICATES = {
  always:              () => true,
  same_country:        x => x.dxCountry === x.myCountry,
  same_continent:      x => x.dxCont === x.myCont,
  different_continent: x => x.dxCont !== x.myCont,
  is_french:           x => /^(F|TM)/.test(x.dxBase),
  is_na:               x => _NA_CALL_RE.test(x.dxBase),
  na_w_ve:             x => /^(W|K|N|VE|XE)/.test(x.dxBase),
  is_asia:             x => x.dxCont === 'AS',
  is_eu:               x => x.dxCont === 'EU',
};

// Évalue les points d'un QSO depuis un bloc scoring serveur.
// Retourne un nombre, ou null si le bloc est inexploitable (→ repli local).
function evalPointsFromDef(scoring, callDX, band, mode, dist, locDX){
  const bricks = scoring.bricks || LEGACY_JS_BRICKS[scoring.type];
  if (!bricks || !Array.isArray(bricks.points)) return null;
  const ctx = _brickCtx(callDX);

  // Brique validité : nom de prédicat, {prefix_in:[...]}, ou {roster_check:...}
  // (roster externe publié — ex. WWA — non vérifiable ici sans réseau : on
  // reste optimiste côté client, le serveur reste l'arbitre réel).
  const v = bricks.validity;
  if (v){
    let ok;
    if (typeof v === 'object' && v.prefix_in){
      ok = v.prefix_in.some(p => ctx.dxBase.startsWith(p.toUpperCase()));
    } else if (typeof v === 'object' && v.roster_check){
      ok = true;
    } else {
      ok = (BRICK_PREDICATES[v] || BRICK_PREDICATES.always)(ctx);
    }
    if (!ok) return 0;
  }

  // Points fixes "même grand carré" (IARU)
  const ssp = bricks.same_square_points;
  if (ssp !== undefined && ssp !== null){
    const large = l => (l && l.length >= 4) ? l.slice(0,4).toUpperCase() : null;
    const mySq = large(myLocator);
    if (mySq !== null && mySq === large(locDX)){
      return (typeof ssp === 'object') ? (scoring[ssp.param] ?? ssp.default ?? 50) : ssp;
    }
  }

  // Règles de points ordonnées : filtres bands/modes/prefix_in + prédicat when
  const bandNorm = String(band || '').replace(' MHz','').replace(' GHz','').trim();
  const modeNorm = String(mode || '').toUpperCase();
  for (const rule of bricks.points){
    if (rule.bands && !rule.bands.includes(bandNorm)) continue;
    if (rule.modes && !rule.modes.map(m => m.toUpperCase()).includes(modeNorm)) continue;
    if (rule.prefix_in && !rule.prefix_in.some(p => ctx.dxBase.startsWith(p.toUpperCase()))) continue;
    if (!(BRICK_PREDICATES[rule.when || 'always'] || BRICK_PREDICATES.always)(ctx)) continue;
    let val = rule.points;
    if (val && typeof val === 'object') val = scoring[val.param] ?? val.default ?? 0;
    if (val === 'per_km') return dist;
    return (typeof val === 'number') ? val : 0;
  }
  return 0;
}

function calcPoints(locDX, band, callDX, mode){
  const myLL = locLL(myLocator);
  const dxLL = locDX ? locLL(locDX) : null;
  const dist = (myLL && dxLL) ? hav(myLL.lat,myLL.lon,dxLL.lat,dxLL.lon) : 0;

  // 1er choix : le barème du serveur (briques) — couvre TOUS les concours,
  // y compris ceux ajoutés par analyse IA, et ne requiert un locator que
  // pour les barèmes à distance
  const def = contestScoringDefs[currentContest];
  if (def){
    const pts = evalPointsFromDef(def, callDX, band, mode, dist, locDX);
    if (pts !== null) return pts;
  }

  // ── Repli local historique (serveur injoignable) ──────────────────────────
  if(!myLL||!dxLL) return 0;

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

// TABLE PREFIXES DXCC + lookupDXCC() : extrait vers logx_dxcc_lookup.js
// (EV-7 phase 2, 11e increment, docs/LogX_AI_PRD.md) -- charge en <script>
// classique dans logx_logbook.html, portee globale partagee.

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

// Alloue le n° de série AUPRÈS DU SERVEUR (voir logx_http.py:/log/next_serial)
// — jamais un simple compteur local : deux postes qui loguent au même
// instant sur la même bande ne doivent plus jamais pouvoir émettre le même
// numéro (avant, chaque poste incrémentait serialByBand pour son propre
// compte, sans aucune coordination réelle). serialByBand reste tenu à jour
// localement (repli hors ligne + affichage preview, voir updateSerialDisplay).
async function nextSerial(band){
  try{
    const r = await fetch('/log/next_serial?band=' + encodeURIComponent(band));
    if(r.ok){
      const d = await r.json();
      const n = parseInt(d.serial, 10);
      if(!isNaN(n)){
        serialByBand[band] = n;
        return d.serial;
      }
    }
  }catch(e){ /* serveur injoignable : repli local ci-dessous */ }
  // Repli hors ligne — collision possible seulement si le réseau est
  // indisponible ET qu'un autre poste logue au même instant, un cas déjà
  // couvert par la file d'attente hors-ligne (voir syncOfflineQueue()).
  if(!serialByBand[band]) serialByBand[band] = 0;
  serialByBand[band]++;
  return String(serialByBand[band]).padStart(3,'0');
}

function isDup(call, band, mode){
  return qsoLog.some(q=>
    q.call.toUpperCase()===call.toUpperCase() && q.band===band &&
    (!mode || q.mode===mode)
  );
}

// ─── STATUT À LA FRAPPE (serveur) ────────────────────────────────────────────
// GET /log/check : nouveau / doublon / nouveau_mult, évalué par le MOTEUR DE
// SCORING contre le log partagé multi-op (pas seulement le log local).
let _checkTimer = null;
let _checkSeq = 0;

// ─── FICHE CALLBOOK (à la frappe) ────────────────────────────────────────────
// Affiche nom / QTH / locator du correspondant, en cascade QRZ (si identifiants
// configurés) -> HamQTH -> HamDB (côté serveur, logx_callbook.py).
// Debounce plus long (600 ms) : une requête réseau par indicatif fini.
let _qrzTimer = null, _qrzSeq = 0;
// Dernier état US rapporté par l'annuaire, avec l'indicatif auquel il se
// rapporte ({call, state}). L'indicatif est conservé À DESSEIN : la réponse
// arrive en différé, et sans cette vérification l'état d'une station
// précédente se retrouverait collé au QSO en cours de saisie.
let _stateAnnuaire = null;
const CALLBOOK_SOURCE_LABEL = {hamqth: 'HamQTH', hamdb: 'HamDB'};  // QRZ = pas de tag (source par défaut)

function lookupQRZ(call){
  clearTimeout(_qrzTimer);
  const row = document.getElementById('qrzInfoRow');
  const el = document.getElementById('qrzInfo');
  const photo = document.getElementById('qrzPhoto');
  if(!el || !row) return;
  if(!call || call.length < 3){ row.style.display = 'none'; return; }
  const seq = ++_qrzSeq;
  _qrzTimer = setTimeout(async () => {
    try{
      const r = await fetch('/qrz/lookup?call=' + encodeURIComponent(call));
      if(!r.ok || seq !== _qrzSeq) return;
      const d = await r.json();
      if(!d.ok){ row.style.display = 'none'; return; }
      // Données d'annuaires en ligne tiers (QRZ/HamQTH/HamDB) : origine Internet
      // hors du contrôle de l'utilisateur → échappées avant insertion en innerHTML
      // (un champ QTH contenant du HTML exécuterait sinon du script à la frappe).
      const bits = [];
      if(d.name) bits.push('👤 ' + escHtml(d.name));
      if(d.qth)  bits.push('📍 ' + escHtml(d.qth));
      if(d.grid) bits.push('🗺 ' + escHtml(d.grid));
      if(d.country && !d.qth) bits.push(escHtml(d.country));
      const sourceLabel = CALLBOOK_SOURCE_LABEL[d.source];
      if(sourceLabel) bits.push('· ' + escHtml(sourceLabel));
      el.innerHTML = bits.join(' · ');
      // Photo (QRZ uniquement, comptes abonnés) : `.src` n'exécute jamais de
      // script même sur une URL malveillante, mais on revérifie quand même le
      // schéma ici — défense en profondeur, le serveur (logx_qrz.py) filtre déjà.
      if(photo){
        if(d.image && /^https?:\/\//i.test(d.image)){
          photo.onerror = () => { photo.style.display = 'none'; };   // lien mort (ex. QRZ ayant retiré la fiche depuis)
          photo.src = d.image;
          photo.style.display = 'block';
        } else {
          photo.style.display = 'none';
          photo.src = '';
        }
      }
      row.style.display = (bits.length || (photo && photo.style.display === 'block')) ? 'flex' : 'none';
      // Pré-remplit le locator s'il est vide et que la source en connaît un
      const locInput = document.getElementById('inputLocator');
      if(locInput && !locInput.value && d.grid && d.grid.length >= 4){
        locInput.value = d.grid;
        onLocatorInput();
      }
      // État US retenu pour le QSO : c'est la SEULE source à la saisie, l'état
      // ne se déduisant pas de l'indicatif (un W6 peut habiter n'importe où).
      // Mémorisé avec l'indicatif auquel il se rapporte : sans ça, un état
      // resté d'une frappe précédente serait recopié sur le QSO suivant.
      _stateAnnuaire = (d.state && /^[A-Z]{2}$/.test(String(d.state).toUpperCase()))
        ? {call: call, state: String(d.state).toUpperCase()} : null;
    }catch(e){ /* réseau callbook indispo : rien */ }
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
                            `&band=${encodeURIComponent(currentBand || '')}` +
                            `&mode=${encodeURIComponent(currentMode || '')}`);
      if(!r.ok || seq !== _prevSeq) return;
      const d = await r.json();
      const parts = [];
      // Alerte « nouveau à vie » (pays / département jamais contacté)
      (d.new_one || []).forEach(n => {
        parts.push(`<div style="color:var(--green);font-weight:700">🌟 ${n.label}</div>`);
      });
      // Besoin LoTW : « pas confirmé LoTW » n'est PAS « jamais contacté ». Un
      // pays travaillé dix fois mais jamais confirmé ne compte toujours pas
      // pour le DXCC — et une confirmation eQSL ou papier n'y change rien.
      // L'entité jamais confirmée nulle part passe en rouge : c'est celle qui
      // fait avancer le compteur.
      if(d.lotw_need && d.lotw_need.besoin){
        const jamais = d.lotw_need.raison === 'jamais_confirme';
        parts.push(`<div style="color:${jamais ? 'var(--red)' : 'var(--accent2)'};font-weight:700">` +
                   `${jamais ? '📛' : '📻'} ${escHtml(d.lotw_need.label)}</div>`);
      }
      // État US / province canadienne, quand on la connaît (même champ ADIF
      // STATE des deux côtés de la frontière).
      if(d.state){
        parts.push(`<div style="color:var(--muted)">🏛 ${escHtml(d.state)}</div>`);
      }
      // Utilisateur LoTW. Décisif juste au-dessus de l'alerte « pas confirmé
      // LoTW » : si le correspondant n'uploade pas, le créneau ne se comblera
      // jamais avec lui. `undefined`/null = liste pas encore téléchargée, on
      // n'affiche RIEN plutôt que d'annoncer « n'utilise pas LoTW » à tort.
      if(d.lotw_user === true){
        const depuis = d.lotw_last ? ` · dernier envoi ${escHtml(d.lotw_last)}` : '';
        parts.push(`<div style="color:var(--green)">✅ LoTW${depuis}</div>`);
      } else if(d.lotw_user === false){
        parts.push(`<div style="color:var(--muted)">🚫 pas sur LoTW — ne sera jamais confirmé</div>`);
      }
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
// Même mapping que _BM_PCOL mais en noms de variable CSS nus (sans 'var()')
// pour le canvas waterfall, qui doit lire les couleurs via getComputedStyle
// (un canvas ne comprend pas 'var(--x)' dans ctx.fillStyle) — garder les deux
// tables synchronisées.
const _BM_CSSVAR = {1:'--red', 2:'--accent', 3:'--yellow', 4:'--accent2', 5:'--muted'};
// Plages de fréquence (MHz) par bande — le band map ne montre QUE la bande
// courante, filtrée par FRÉQUENCE (infaillible : un spot 50/432 ne peut pas
// apparaître sur 2 m même si le serveur l'a mal étiqueté).
// Mêmes plages que _band_from_freq() côté serveur (logx_scoring.py) pour les
// bandes WARC — les deux DOIVENT s'accorder sur la clé de bande ('10.1'/'18'/'24').
const _BM_RANGE = {
  '1.8':[1.8,2.0], '3.5':[3.5,4.0], '7':[7.0,7.3], '10.1':[10.1,10.15],
  '14':[14.0,14.35], '18':[18.0,18.2], '21':[21.0,21.45], '24':[24.8,25.0],
  '28':[28.0,29.7], '50':[50,54], '70':[70,70.5],
  '144':[144,148], '432':[430,440], '1296':[1240,1300], '2320':[2300,2450],
  '3400':[3400,3475], '5760':[5650,5925], '10368':[10000,10500],
  '24048':[24000,24250], '47088':[47000,47200],
};

// ─── BAND MAP : SEARCH & POUNCE ──────────────────────────────────────────────
// Les spots réellement affichés, dans l'ordre où ils le sont : c'est sur cette
// liste que saute la navigation clavier, pour que « suivant » veuille dire la
// ligne suivante À L'ÉCRAN et pas autre chose.
let _bmSpots = [];

// Noter la station en cours : l'indicatif tapé, à la fréquence où la radio est
// posée. C'est LE geste du S&P — on entend quelqu'un, on le note, on continue
// de balayer, on le rappellera plus tard.
async function bandmapNoter(){
  const inp = document.getElementById('inputCall');
  const call = inp ? inp.value.trim().toUpperCase() : '';
  const rig = (typeof rigState !== 'undefined') ? rigState : {};
  if(!call){ notify('👂 Tape d\'abord l\'indicatif entendu'); return; }
  if(!rig.enabled || !rig.freq_khz){
    notify('👂 Fréquence radio inconnue — le pilotage CAT doit être actif');
    return;
  }
  try{
    const res = await fetch('/bandmap/add', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({call, freq_khz: rig.freq_khz, band: currentBand,
                            mode: rig.mode || currentMode})}).then(r=>r.json());
    if(res.ok){
      notify(trF('👂 {call} noté sur {f} kHz', {call, f: Math.round(rig.freq_khz)}));
      refreshBandMap();
    } else notify(trF('❌ {err}', {err: res.error || 'refus'}));
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
}

// Saut de spot en spot au clavier, sans jamais viser à la souris. L'indicatif
// est pré-rempli au passage : en S&P on arrive sur la station en sachant déjà
// qui c'est, il ne reste qu'à confirmer et loguer.
function bandmapSaut(sens){
  if(!_bmSpots.length){ notify('band map vide sur cette bande'); return; }
  const rig = (typeof rigState !== 'undefined') ? rigState : {};
  const ici = (rig.enabled && rig.freq_khz) ? rig.freq_khz / 1000 : null;
  let cible = null;
  if(ici === null){
    cible = _bmSpots[sens > 0 ? 0 : _bmSpots.length - 1];
  } else if(sens < 0){
    // _bmSpots est trié fréquence DÉCROISSANTE : « suivant vers le haut » est
    // donc le dernier élément encore au-dessus de la fréquence courante.
    const sup = _bmSpots.filter(s => parseFloat(s.freq) > ici + 0.0002);
    cible = sup.length ? sup[sup.length - 1] : null;
  } else {
    cible = _bmSpots.find(s => parseFloat(s.freq) < ici - 0.0002) || null;
  }
  if(!cible){ notify(sens > 0 ? 'dernier spot de la bande' : 'premier spot de la bande'); return; }
  bandmapClick(String(cible.call || '').replace(/[^A-Za-z0-9/]/g, ''), parseFloat(cible.freq),
              String(cible.mode || '').replace(/[^A-Za-z0-9/-]/g, ''));
}

// ─── FILTRE D'AFFICHAGE DES SPOTS ────────────────────────────────────────────
// Le filtrage lui-même est fait CÔTÉ SERVEUR (logx_spotfilter.py), avant que
// /data/spots_ranked ne coupe la liste à 40 : filtrer ici, après la coupe,
// n'écarterait que ce qui a déjà survécu — c'est-à-dire trop tard. Ici on ne
// fait que présenter les réglages et afficher ce qui a été masqué.
const _SF_CONTINENTS = ['EU','NA','SA','AS','AF','OC','AN'];
let _spotFiltre = {spotter_continents:[], dx_continents:[], masquer_deja_faits:false,
                   seulement_lotw:false, seulement_besoins:false};
// Nombre d'enregistrements en vol. Tant qu'il n'est pas nul, on ne resynchro-
// nise PAS l'écran depuis le serveur : sinon un clic pourrait être visuellement
// annulé le temps d'un tick, juste avant que le POST n'arrive.
let _spotFiltreEnVol = 0;
let _spotFiltreOuvert = false;

function toggleSpotFiltre(){
  const box = document.getElementById('bmFiltre');
  if(!box) return;
  _spotFiltreOuvert = !box.classList.contains('on');
  box.classList.toggle('on', _spotFiltreOuvert);
  if(_spotFiltreOuvert) dessinerChipsFiltre();
}

function dessinerChipsFiltre(){
  for(const [id, cle] of [['bmChipsSpotter','spotter_continents'], ['bmChipsDx','dx_continents']]){
    const box = document.getElementById(id);
    if(!box) continue;
    const sel = _spotFiltre[cle] || [];
    // Liste vide = joker « tous », même convention que côté serveur : on
    // allume alors TOUTES les pastilles, parce que « aucun coché » et « tous
    // cochés » produisent le même résultat et que montrer sept pastilles
    // éteintes ferait croire que plus rien ne passe.
    const tous = sel.length === 0;
    box.innerHTML = _SF_CONTINENTS.map(c =>
      `<button type="button" class="bm-chip${tous || sel.includes(c) ? ' on' : ''}"`
      + ` onclick="basculerContinent('${cle}','${c}')">${c}</button>`).join('');
  }
  const m = {bmFiltreDejaFaits:'masquer_deja_faits', bmFiltreLotw:'seulement_lotw',
             bmFiltreBesoins:'seulement_besoins'};
  for(const id in m){
    const el = document.getElementById(id);
    if(el) el.checked = !!_spotFiltre[m[id]];
  }
}

function basculerContinent(cle, c){
  let sel = (_spotFiltre[cle] || []).slice();
  // Partant de « tous » (liste vide), le premier clic doit vouloir dire
  // « celui-ci seulement » et non « tous sauf celui-ci » : on part donc de la
  // sélection pleine avant de retirer, sinon le clic donnerait l'inverse de
  // ce que l'opérateur vient de demander.
  if(sel.length === 0) sel = _SF_CONTINENTS.slice();
  sel = sel.includes(c) ? sel.filter(x => x !== c) : sel.concat([c]);
  // Deux cas retombent volontairement sur le joker « tous » : les sept cochés,
  // et plus aucun. Décocher le dernier continent ne vide donc pas l'écran — il
  // rallume les sept pastilles, ce qui dit tout seul où on en est.
  _spotFiltre[cle] = (sel.length === _SF_CONTINENTS.length || !sel.length) ? [] : sel;
  dessinerChipsFiltre();
  majSpotFiltre(true);
}

async function majSpotFiltre(depuisChip){
  if(!depuisChip){
    const m = {bmFiltreDejaFaits:'masquer_deja_faits', bmFiltreLotw:'seulement_lotw',
               bmFiltreBesoins:'seulement_besoins'};
    for(const id in m){
      const el = document.getElementById(id);
      if(el) _spotFiltre[m[id]] = !!el.checked;
    }
  }
  _spotFiltreEnVol++;
  try{
    await fetch('/spots/filter', {method:'POST', headers:{'Content-Type':'application/json'},
                                  body: JSON.stringify(_spotFiltre)});
  }catch(e){ /* réglage non persisté : le serveur continue avec l'ancien */ }
  finally{ _spotFiltreEnVol--; }
  refreshBandMap();
}

// Affiche ce que le filtre a retiré, et repeint les pastilles si le réglage a
// changé ailleurs (autre poste, autre fenêtre).
function appliquerRetourFiltre(f){
  const ligne = document.getElementById('bmMasques');
  const btn = document.getElementById('spotFiltreBtn');
  f = f || {};
  if(f.reglages && !_spotFiltreEnVol){
    const avant = JSON.stringify(_spotFiltre);
    _spotFiltre = Object.assign({}, _spotFiltre, f.reglages);
    if(JSON.stringify(_spotFiltre) !== avant && _spotFiltreOuvert) dessinerChipsFiltre();
  }
  const r = _spotFiltre;
  const actif = !!((r.spotter_continents||[]).length || (r.dx_continents||[]).length ||
                   r.masquer_deja_faits || r.seulement_lotw || r.seulement_besoins);
  if(btn) btn.style.color = actif ? 'var(--yellow)' : 'var(--accent2)';
  if(!ligne) return;
  const n = f.masques || 0;
  if(!n){ ligne.style.display = 'none'; ligne.textContent = ''; return; }
  let txt = '🔎 ' + n + ' spot' + (n > 1 ? 's' : '') + ' masqué' + (n > 1 ? 's' : '');
  if(f.repeches) txt += ' — ' + f.repeches + ' gardé' + (f.repeches > 1 ? 's' : '') + ' par une alerte';
  ligne.textContent = txt;
  ligne.style.display = '';
}

async function refreshBandMap(){
  const list = document.getElementById('bandmapList');
  if(!list) return;
  const bandEl = document.getElementById('bandmapBand');
  if(bandEl) bandEl.textContent = (currentBand || '—') + ' MHz';
  try{
    const r = await fetch('/data/spots_ranked');
    if(!r.ok) return;
    const d = await r.json();
    appliquerRetourFiltre(d.filtre);
    // Deuxième source : ce que l'opérateur a entendu LUI-MÊME en balayant.
    // Le S&P fait facilement la moitié des QSO d'un mono-opérateur, et une
    // station entendue mais spottée par personne était jusqu'ici perdue.
    let locaux = [];
    try{
      const rl = await fetch('/bandmap/local');
      if(rl.ok) locaux = (await rl.json()).spots || [];
    }catch(e){ /* le band map cluster reste utilisable sans les spots locaux */ }
    const rng = _BM_RANGE[String(currentBand)];
    const inBand = s => {
      if(!s.freq) return false;
      if(rng){ const f = parseFloat(s.freq); return f >= rng[0] && f <= rng[1]; }
      return String(s.band) === String(currentBand);   // repli si bande hors table
    };
    // Les spots locaux portent leur fréquence en kHz : on la ramène en MHz
    // pour parler la même langue que le cluster avant de fusionner.
    const locauxMhz = locaux.map(s => ({
      call: s.call, freq: (Number(s.freq_khz) || 0) / 1000, band: s.band,
      local: true, age_s: s.age_s, note: s.note,
      explanation: 'Entendu il y a ' + Math.round((s.age_s || 0) / 60) + ' min'
                   + (s.note ? ' — ' + s.note : ''),
    }));
    // Une station à la fois spottée et entendue ne doit pas apparaître deux
    // fois : le spot du cluster gagne (il porte les points et le statut
    // multiplicateur), on ne garde le local que s'il n'a pas d'équivalent.
    // Le serveur envoie des kHz — unité du protocole cluster, imposée à toutes
    // les sources par freq_en_khz (logx_clusters.py). Tout le band map raisonne
    // en MHz : _BM_RANGE, le bandscope, la chute d'eau et bandmapClick, qui
    // multiplie par 1000 avant de commander le QSY. UNE seule conversion, ici
    // à l'entrée, au même endroit que celle des spots locaux juste au-dessus.
    const clusterMhz = (d.spots || []).map(
      s => Object.assign({}, s, {freq: (parseFloat(s.freq) || 0) / 1000}));
    const clusterCles = new Set(clusterMhz.map(
      s => String(s.call || '').toUpperCase() + '@' + Math.round(parseFloat(s.freq) * 1000)));
    const spots = clusterMhz
      .concat(locauxMhz.filter(
        s => !clusterCles.has(String(s.call || '').toUpperCase() + '@' + Math.round(s.freq * 1000))))
      .filter(inBand)
      .sort((a,b) => parseFloat(b.freq) - parseFloat(a.freq));   // fréquence haute en haut
    _bmSpots = spots;   // memorise pour la navigation clavier
    const rig = (typeof rigState !== 'undefined') ? rigState : {};
    const txMhz = (rig.enabled && rig.freq_khz) ? rig.freq_khz/1000 : null;
    const rows = [];
    let txDone = false;
    const txRow = m => `<div class="bm-tx">▶ ${m.toFixed(3)} (radio)</div>`;
    for(const s of spots){
      const f = parseFloat(s.freq);
      if(txMhz && !txDone && f <= txMhz){ rows.push(txRow(txMhz)); txDone = true; }
      // Un spot local se distingue à l'œil du spot cluster : l'opérateur doit
      // savoir s'il regarde une information vérifiée par le réseau ou sa
      // propre note de balayage.
      const col = s.local ? 'var(--accent2)'
                          : (s.new_mult ? 'var(--green)' : (_BM_PCOL[s.priority] || 'var(--text)'));
      const style = `color:${col}` + (s.already_done ? ';opacity:.45;text-decoration:line-through' : '');
      // s.call vient du cluster DX (source externe non maîtrisée). Pour l'argument
      // onclick (contexte chaîne JS DANS un attribut HTML), escHtml ne suffit pas :
      // on restreint l'indicatif aux seuls caractères d'indicatif valides. Le texte
      // affiché et le title passent par escHtml.
      const jsCall = String(s.call || '').replace(/[^A-Za-z0-9/]/g, '');
      // Repêché par une alerte alors que le filtre l'écartait : il DOIT rester
      // visible, sinon l'alerte sonnerait pour un spot introuvable dans la
      // liste — la meilleure façon de faire couper les alertes.
      const cls = 'bm-spot' + (s.hors_filtre ? ' hors' : '');
      const infoBulle = (s.explanation || '')
        + (s.hors_filtre ? ' — hors filtre, gardé par une règle d\'alerte' : '')
        + (s.spotter ? ' — spotté par ' + s.spotter : '');
      // « Écouter ce spot » : mêmes règles d'hygiène que jsCall — mode et
      // coordonnées viennent du cluster (source externe), on ne laisse passer
      // dans l'attribut onclick que des caractères/nombres sûrs.
      const modeSpot = String(s.mode || '').replace(/[^A-Za-z0-9/-]/g, '');
      const earLat = Number.isFinite(s.lat) ? s.lat : 'null';
      const earLon = Number.isFinite(s.lon) ? s.lon : 'null';
      // Le cluster fournit bien plus souvent une GRILLE que des coordonnées,
      // et un spot local (entendu par l'opérateur) n'a aucune position. Sans
      // ça, le bouton promettait « proche du DX » et donnait en silence un
      // récepteur proche de CHEZ MOI — le titre le dit maintenant, et la
      // grille est transmise pour que le serveur situe le DX quand il peut.
      const grilleSpot = String(s.locator || '').replace(/[^A-Za-z0-9]/g, '').slice(0, 6);
      const dxSitue = Number.isFinite(s.lat) || grilleSpot.length >= 4;
      const titreOreille = dxSitue
        ? trT('Écouter ce spot sur un récepteur WebSDR proche du DX')
        : trT('Position du DX inconnue — écouter cette fréquence sur un récepteur proche de chez toi');
      rows.push(`<div class="${cls}" onclick="bandmapClick('${jsCall}',${f},'${modeSpot}')" title="${escHtml(infoBulle)}">`
        + `<span class="bm-f">${f.toFixed(3)}</span>`
        + `<span class="bm-c" style="${style}">${s.local ? '👂' : (s.new_mult ? '★' : '')}${escHtml(s.call)}</span>`
        + `<span class="bm-ear${dxSitue ? '' : ' flou'}" onclick="event.stopPropagation();`
        + `ecouterSpot(${(f * 1000).toFixed(1)},${earLat},${earLon},'${modeSpot}','${grilleSpot}')"`
        + ` title="${escHtml(titreOreille)}">🔊</span></div>`);
    }
    if(txMhz && !txDone) rows.push(txRow(txMhz));
    list.innerHTML = rows.length ? rows.join('')
      : '<div class="bm-empty">aucun spot sur cette bande</div>';
    drawBandscope(spots, rng, txMhz);   // spectre d'activité visuel
    drawWaterfallRow(spots, rng);       // chute d'eau : mêmes spots, dans le temps
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
    const safeMode = String(s.mode || '').replace(/[^A-Za-z0-9/-]/g, '');
    g += `<rect class="bs-bar" x="${(x-1).toFixed(1)}" y="${(base-h).toFixed(1)}" width="2" height="${h.toFixed(1)}"`
       + ` style="fill:${col}" opacity="${op}" onclick="bandmapClick('${safeCall}',${f},'${safeMode}')">`
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

// ─── WATERFALL : mêmes spots que le bandscope, empilés dans le temps ─────────
// Contrairement au bandscope (redessiné en entier à chaque tick), le canvas
// est décalé d'une ligne vers le bas et une seule NOUVELLE ligne est peinte en
// haut (technique standard des waterfalls SDR) — l'historique visuel des
// derniers ticks (par défaut ~15 s/ligne, voir refreshBandMap) permet de voir
// QUAND la bande s'est ouverte, pas juste où. Masqué par défaut (toggleWaterfall)
// pour ne pas faire tourner de dessin canvas inutilement en arrière-plan.
let _wfShown = false;
// Dernière bande dessinée dans le canvas — sert à détecter un changement de
// bande pour vider l'historique (voir drawWaterfallRow). Sans ce suivi, le
// canvas n'est vidé QUE quand rng est falsy (bande hors table _BM_RANGE), ce
// qui n'arrive presque jamais : en pratique, changer de bande empilait les
// nouveaux spots par-dessus l'ancien historique au lieu de repartir à zéro.
let _wfLastBand = null;

function toggleWaterfall(){
  _wfShown = !_wfShown;
  const cv = document.getElementById('bandWaterfall');
  const sv = document.getElementById('bandscope');
  if(cv) cv.style.display = _wfShown ? 'block' : 'none';
  if(sv) sv.style.display = _wfShown ? 'none' : 'block';
  const btn = document.getElementById('waterfallToggleBtn');
  if(btn) btn.style.color = _wfShown ? 'var(--green)' : 'var(--accent2)';
}

function _cssVar(name){
  return (getComputedStyle(document.body).getPropertyValue(name) || '').trim() || '#8792B5';
}

function drawWaterfallRow(spots, rng){
  const canvas = document.getElementById('bandWaterfall');
  if(!canvas) return;
  // Changement de bande : purge l'historique même si le waterfall est
  // actuellement masqué, sinon l'ancien contenu resurgit tel quel au prochain
  // toggleWaterfall() (le canvas n'est jamais touché tant qu'il est caché).
  const bandChanged = currentBand !== _wfLastBand;
  _wfLastBand = currentBand;
  if(!_wfShown){
    if(bandChanged) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
    return;   // caché : inutile de dessiner en arrière-plan
  }
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  if(bandChanged) ctx.clearRect(0, 0, w, h);   // nouvelle bande : pas l'historique de l'ancienne
  if(!rng){ ctx.clearRect(0, 0, w, h); return; }
  // Défile le contenu existant d'une ligne vers le bas en recopiant le canvas
  // sur lui-même décalé — PAS un redraw complet (on perdrait l'historique).
  ctx.drawImage(canvas, 0, 0, w, h - 1, 0, 1, w, h - 1);
  ctx.clearRect(0, 0, w, 1);   // nouvelle ligne transparente = fond du thème visible
  const x0 = 4, x1 = w - 4, span = (rng[1] - rng[0]) || 1;
  for(const s of spots){
    const f = parseFloat(s.freq);
    if(!isFinite(f)) continue;
    const x = Math.round(x0 + Math.max(0, Math.min(1, (f - rng[0]) / span)) * (x1 - x0));
    ctx.fillStyle = s.new_mult ? _cssVar('--green') : _cssVar(_BM_CSSVAR[s.priority] || '--muted');
    ctx.fillRect(Math.max(0, x - 1), 0, 3, 1);
  }
}

function bandmapClick(call, mhz, mode){
  const inp = document.getElementById('inputCall');
  if(inp){ inp.value = call; onCallInput(); inp.focus(); }
  const rig = (typeof rigState !== 'undefined') ? rigState : {};
  if(rig.enabled){
    // Mode du SPOT cliqué, pas le mode de saisie courant de l'opérateur —
    // sinon un clic sur un spot CW pendant une saisie SSB fait QSY en SSB.
    fetch('/rig/qsy', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({freq_khz: Math.round(mhz*1000), mode: mode || currentMode || undefined})
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

// Emplacements DVK réellement enregistrés, tels que le SERVEUR les connaît.
// Ils y sont stockés (et non plus en localStorage) pour deux raisons : ils sont
// joués par le serveur vers la radio, et ils doivent suivre l'opérateur d'un
// poste à l'autre — c'est tout l'intérêt du multi-poste.
let voiceSlots = {};
async function voiceRefreshSlots(){
  try{
    const d = await fetch('/voice/slots').then(r => r.json());
    voiceSlots = d.slots || {};
  }catch(e){ /* serveur injoignable : on garde le dernier état connu */ }
  renderVoicePanel();
  voiceMigrerAnciens();
}

// Reprise des messages enregistrés AVANT que le stockage passe côté serveur.
// Ils dormaient en localStorage au format WebM. Les abandonner sans rien dire
// serait une perte de données silencieuse — même si, tels quels, ils ne
// partaient de toute façon pas sur l'air.
// Une seule tentative : en cas d'échec de conversion on laisse la clé en place
// plutôt que de la détruire, et on n'insiste pas à chaque chargement de page.
let _voiceMigrationFaite = false;
async function voiceMigrerAnciens(){
  if(_voiceMigrationFaite) return;
  _voiceMigrationFaite = true;
  let anciens = {};
  try{ anciens = JSON.parse(localStorage.getItem('rc_voice') || '{}'); }catch(e){ return; }
  const aReprendre = Object.keys(anciens).filter(k => voiceSlots[k] === undefined && anciens[k]);
  if(!aReprendre.length) return;
  let repris = 0;
  for(const cle of aReprendre){
    try{
      const blob = await (await fetch(anciens[cle])).blob();   // data URL -> Blob
      const ctx = _audioCtx || (_audioCtx = new (window.AudioContext || window.webkitAudioContext)());
      const buf = await ctx.decodeAudioData(await blob.arrayBuffer());
      const canaux = [];
      for(let c = 0; c < buf.numberOfChannels; c++) canaux.push(buf.getChannelData(c));
      const b64 = await _blobToBase64(_floatChannelsToWav(canaux, buf.sampleRate));
      const res = await fetch('/voice/save', {method:'POST', headers:{'Content-Type':'application/json'},
                                              body: JSON.stringify({slot: cle, wav_base64: b64})}).then(r=>r.json());
      if(res.ok){ delete anciens[cle]; repris++; }
    }catch(e){ /* enregistrement illisible : on le laisse où il est */ }
  }
  if(repris){
    try{ localStorage.setItem('rc_voice', JSON.stringify(anciens)); }catch(e){}
    const d = await fetch('/voice/slots').then(r => r.json()).catch(()=>null);
    if(d && d.slots){ voiceSlots = d.slots; renderVoicePanel(); }
    notify(trF('🎙 {n} message(s) vocal(aux) repris depuis ce navigateur', {n: repris}));
  }
}

function renderVoicePanel(){
  const box = document.getElementById('voiceBtns');
  if(!box) return;
  // flex:1 1 300px (pas width:100%) : chaque ligne PEUT s'étaler sur toute
  // la largeur d'une colonne étroite (ancien emplacement, .saisie-secondary),
  // mais dans .keyer-dock (bandeau plein largeur, 04/08/2026) plusieurs
  // lignes se rangent maintenant côte à côte au lieu de s'empiler une par
  // une — c'est tout l'intérêt du bandeau large : moins de hauteur prise
  // pour le même nombre de messages.
  box.innerHTML = VOICE_SLOTS.map(s => {
    const dur = voiceSlots[s.key];
    const has = dur !== undefined;
    const lbl = has ? `${s.label} <span style="color:var(--muted)">${dur}s</span>` : s.label;
    return `<div style="display:flex;gap:4px;margin:3px 0;flex:1 1 300px;box-sizing:border-box">
      <button class="macro-btn" style="flex:1;min-width:0;max-width:none;text-align:left;${has?'':'opacity:.5'}" onclick="voicePlay('${s.key}')" ${has?'':'disabled'}>▶ ${lbl}</button>
      <button class="macro-btn" style="flex:0 0 36px;min-width:0;max-width:none" onclick="voiceRecord('${s.key}')" id="rec_${s.key}" title="Enregistrer ${s.label}">⏺</button>
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
    _mediaRec.onstop = async () => {
      stream.getTracks().forEach(t=>t.stop());
      const blob = new Blob(_recChunks, {type: _mediaRec.mimeType||'audio/webm'});
      _mediaRec = null; _recSlot = null;
      if(btn){ btn.textContent = '⏺'; btn.style.color=''; }
      // Réencodage en WAV AVANT l'envoi : le navigateur enregistre en WebM/Opus,
      // que le serveur ne sait pas jouer (wave.open). On réutilise l'encodeur
      // déjà écrit pour les clips de QSO plutôt que d'en poser un second.
      try{
        const ctx = _audioCtx || (_audioCtx = new (window.AudioContext || window.webkitAudioContext)());
        const buf = await ctx.decodeAudioData(await blob.arrayBuffer());
        const canaux = [];
        for(let c = 0; c < buf.numberOfChannels; c++) canaux.push(buf.getChannelData(c));
        const wav = _floatChannelsToWav(canaux, buf.sampleRate);
        const b64 = await _blobToBase64(wav);
        const res = await fetch('/voice/save', {method:'POST', headers:{'Content-Type':'application/json'},
                                                body: JSON.stringify({slot: key, wav_base64: b64})}).then(r=>r.json());
        if(res.ok){ await voiceRefreshSlots();
so2rRafraichir(); notify(trF('🎙 Message {key} enregistré', {key})); }
        else       notify(trF('❌ {err}', {err: res.error || 'enregistrement refusé'}));
      }catch(e){ notify(trF('❌ Réencodage impossible : {err}', {err: e.message})); }
    };
    _mediaRec.start();
    if(btn){ btn.textContent = '■'; btn.style.color='var(--red)'; }
    notify('🎙 Enregistrement… reclique ⏺ pour arrêter');
  }catch(e){ notify(trF('❌ Micro indisponible : {err}', {err: e.message})); }
}

// Base64 d'un Blob, sans concaténation manuelle (un message de plusieurs
// secondes dépasse la taille d'argument de String.fromCharCode(...tableau)).
function _blobToBase64(blob){
  return new Promise((resolve, reject) => {
    const rd = new FileReader();
    rd.onload = () => resolve(String(rd.result).split(',', 2)[1] || '');
    rd.onerror = () => reject(rd.error || new Error('lecture impossible'));
    rd.readAsDataURL(blob);
  });
}

// Le message part par la RADIO, pas par les enceintes : le serveur lève le PTT,
// joue le WAV vers le périphérique de sortie choisi en CONFIG (câble vers
// l'entrée micro de la radio) puis relâche le PTT en vérifiant qu'il est bien
// retombé. `new Audio().play()` ne faisait aucune des trois choses.
async function voicePlay(key){
  if(voiceSlots[key] === undefined) return;
  try{
    const res = await fetch('/voice/play', {method:'POST', headers:{'Content-Type':'application/json'},
                                            body: JSON.stringify({slot: key})}).then(r=>r.json());
    if(!res.ok) notify(trF('❌ {err}', {err: res.error || 'émission impossible'}));
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
}

// ─── ENREGISTREUR AUDIO PAR QSO (tampon glissant) ────────────────────────────
// Principe : le flux micro/entrée choisi est enregistré en petits segments
// AUTONOMES (redémarrage périodique du MediaRecorder) plutôt qu'en flux
// continu — un WebM/Ogg découpé en plein milieu n'est pas rejouable (seul le
// tout premier fragment contient l'en-tête du conteneur). Un segment complet,
// lui, EST rejouable seul, donc décodable indépendamment via Web Audio.
// Au log d'un QSO : on clôt le segment en cours (capture jusqu'à MAINTENANT),
// on décode les derniers segments couvrant REC_CLIP_SECONDS, on les recolle
// en PCM brut puis on réencode en WAV (format simple, universellement
// lisible) — pas de recollage naïf de plusieurs fichiers WebM bout à bout,
// que la plupart des lecteurs ne rejouent que jusqu'au premier morceau.
const REC_SEGMENT_MS   = 5000;    // durée d'un segment avant redémarrage
const REC_BUFFER_MS    = 130000;  // tampon glissant conservé (~2 min + marge)
const REC_CLIP_SECONDS = 20;      // durée du clip découpé au moment du log

let recEnabled = (localStorage.getItem('logx_rec_enabled') === 'on');
let _recStream = null, _recMediaRec = null, _recRestartTimer = null;
let _recSegments = [];      // [{blob, start, end}] du plus ancien au plus récent
let _recDirHandle = null;   // FileSystemDirectoryHandle (API File System Access), si choisi

function _recMimeType(){
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
  for(const c of candidates){
    if(window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c)) return c;
  }
  return '';
}

function _recPruneSegments(){
  const cutoff = Date.now() - REC_BUFFER_MS;
  while(_recSegments.length && _recSegments[0].end < cutoff) _recSegments.shift();
}

// Démarre UN segment autonome sur le flux déjà ouvert (_recStream). Chaque
// segment ferme son propre tableau de chunks (pas de variable partagée) :
// sinon un redémarrage juste après stop() risquerait de mélanger les données
// du segment sortant avec celles du segment entrant (l'événement
// dataavailable/stop du premier arrive de façon asynchrone, APRÈS que le
// second ait déjà commencé à écrire).
function _recStartSegment(){
  if(!_recStream) return;
  const start = Date.now();
  const chunks = [];
  const mime = _recMimeType();
  let rec;
  try{ rec = mime ? new MediaRecorder(_recStream, {mimeType: mime}) : new MediaRecorder(_recStream); }
  catch(e){ rec = new MediaRecorder(_recStream); }
  rec.ondataavailable = e => { if(e.data && e.data.size) chunks.push(e.data); };
  rec.onstop = () => {
    if(chunks.length){
      _recSegments.push({blob: new Blob(chunks, {type: rec.mimeType || mime || 'audio/webm'}), start, end: Date.now()});
      _recPruneSegments();
    }
  };
  rec.start();
  _recMediaRec = rec;
}

// Clôt le segment EN COURS et attend que son onstop (poussée dans
// _recSegments) soit passé, avant de relancer un nouveau segment — utilisé
// au moment du log pour capturer l'audio jusqu'à l'instant présent au lieu
// de s'arrêter au dernier redémarrage périodique (jusqu'à REC_SEGMENT_MS de
// retard sinon).
function _recFinishCurrentSegment(){
  return new Promise(resolve => {
    if(!_recMediaRec || _recMediaRec.state === 'inactive'){ resolve(); return; }
    const rec = _recMediaRec;
    const prevOnStop = rec.onstop;
    rec.onstop = ev => { try{ if(prevOnStop) prevOnStop(ev); } finally { resolve(); } };
    try{ rec.stop(); }catch(e){ resolve(); }
  });
}

function _recRestartSegment(){
  if(!recEnabled || !_recMediaRec || _recMediaRec.state === 'inactive') return;
  _recMediaRec.stop();     // pousse le segment sortant dans _recSegments (via son propre onstop)
  _recStartSegment();      // enchaîne aussitôt (léger trou possible, best effort)
}

function _updateRecToggleBtn(){
  const on = !!_recStream;
  const b = document.getElementById('qsoRecToggleBtn');
  if(b){
    b.textContent = on ? '● actif' : '○ désactivé';
    b.style.color = on ? 'var(--red)' : 'var(--muted)';
    b.style.borderColor = on ? 'var(--red)' : 'var(--border)';
  }
  // Indicateur TOUJOURS visible (en dehors du panneau .expert-only) : quel
  // que soit le mode UI (débutant/expert), un enregistrement micro actif ne
  // doit jamais rester invisible — le bouton ci-dessus, lui, est masqué avec
  // tout le panneau en mode simple.
  let ind = document.getElementById('qsoRecIndicator');
  if(on){
    if(!ind){
      ind = document.createElement('div');
      ind.id = 'qsoRecIndicator';
      ind.title = 'Enregistrement micro actif (enregistreur QSO)';
      ind.style.cssText = 'position:fixed;top:8px;right:8px;z-index:99999;background:var(--red);color:#fff;font-family:var(--font-mono);font-size:11px;padding:3px 9px;border-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,.4)';
      ind.textContent = '● REC';
      document.body.appendChild(ind);
    }
  } else if(ind){
    ind.remove();
  }
}

function _updateRecDirLabel(){
  const el = document.getElementById('qsoRecDirLabel');
  if(el) el.textContent = _recDirHandle ? ('dossier : ' + _recDirHandle.name) : 'téléchargement direct';
}

async function startAudioRecorder(){
  try{
    const deviceId = localStorage.getItem('logx_rec_device') || '';
    const constraints = {audio: deviceId ? {deviceId: {exact: deviceId}} : true};
    _recStream = await navigator.mediaDevices.getUserMedia(constraints);
    _recSegments = [];
    _recStartSegment();
    _recRestartTimer = setInterval(_recRestartSegment, REC_SEGMENT_MS);
    await loadAudioInputDevices('qsoRecDevice', true);   // true : le flux ci-dessus a déjà obtenu la permission, pas un second getUserMedia
    const sel = document.getElementById('qsoRecDevice');
    if(sel && deviceId) sel.value = deviceId;
    _updateRecToggleBtn();
    notify(trF('🎙️ Enregistreur QSO actif (tampon {s}s)', {s: Math.round(REC_BUFFER_MS/1000)}));
    return true;
  }catch(e){
    notify(trF('❌ Micro indisponible pour l\'enregistreur QSO : {err}', {err: e.message}));
    _recStream = null;
    _updateRecToggleBtn();
    return false;
  }
}

function stopAudioRecorder(){
  if(_recRestartTimer){ clearInterval(_recRestartTimer); _recRestartTimer = null; }
  if(_recMediaRec && _recMediaRec.state !== 'inactive'){
    _recMediaRec.onstop = null;   // désactivation volontaire : ce dernier segment partiel ne sert plus
    try{ _recMediaRec.stop(); }catch(e){}
  }
  _recMediaRec = null;
  if(_recStream){ _recStream.getTracks().forEach(t => t.stop()); _recStream = null; }
  _recSegments = [];
  _updateRecToggleBtn();
}

async function toggleAudioRecorder(){
  if(_recStream){
    stopAudioRecorder();
    recEnabled = false;
  } else {
    recEnabled = await startAudioRecorder();
  }
  localStorage.setItem('logx_rec_enabled', recEnabled ? 'on' : 'off');
}

async function onRecDeviceChange(){
  const val = document.getElementById('qsoRecDevice').value || '';
  localStorage.setItem('logx_rec_device', val);
  if(_recStream){   // changement à chaud : redémarre le flux sur le nouveau périphérique
    stopAudioRecorder();
    await startAudioRecorder();
  }
}

// ─── Choix du dossier de sauvegarde (File System Access API) ────────────────
// Optionnel : sans dossier choisi (ou navigateur non compatible — Firefox et
// Safari n'implémentent pas showDirectoryPicker), chaque clip est simplement
// proposé en téléchargement.
function _recIdbOpen(){
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('logx_audio_rec', 1);
    req.onupgradeneeded = () => { if(!req.result.objectStoreNames.contains('kv')) req.result.createObjectStore('kv'); };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function _recIdbGet(key){
  try{
    const db = await _recIdbOpen();
    return await new Promise((resolve, reject) => {
      const r = db.transaction('kv', 'readonly').objectStore('kv').get(key);
      r.onsuccess = () => resolve(r.result || null);
      r.onerror = () => reject(r.error);
    });
  }catch(e){ return null; }
}
async function _recIdbSet(key, val){
  try{
    const db = await _recIdbOpen();
    await new Promise((resolve, reject) => {
      const tx = db.transaction('kv', 'readwrite');
      tx.objectStore('kv').put(val, key);
      tx.oncomplete = resolve; tx.onerror = () => reject(tx.error);
    });
  }catch(e){}
}

async function chooseRecDir(){
  if(!('showDirectoryPicker' in window)){
    notify('❌ Ce navigateur ne propose pas le choix de dossier (Chrome/Edge requis) — repli sur le téléchargement.');
    return;
  }
  try{
    _recDirHandle = await window.showDirectoryPicker({id: 'logx-audio-rec', mode: 'readwrite'});
    await _recIdbSet('dirHandle', _recDirHandle);
    _updateRecDirLabel();
    notify(trF('📁 Dossier des clips QSO : {name}', {name: _recDirHandle.name}));
  }catch(e){ /* sélection annulée par l'utilisateur */ }
}

// Décide si l'auto-démarrage au chargement de page est autorisé. Isolée en
// fonction pure (aucun I/O) pour rester testable indépendamment du DOM/micro
// réel : ne JAMAIS démarrer automatiquement l'enregistreur en mode UI
// « simple » (débutant, cf. logx_statusbar.js) — le panneau #qsoRecPanel qui
// porte le bouton marche/arrêt est masqué par .expert-only dans ce mode, donc
// injoignable ; un démarrage silencieux y serait un enregistrement micro sans
// AUCUN contrôle visible pour l'utilisateur (problème de confidentialité).
function _recAutoStartAllowed(){
  return recEnabled && localStorage.getItem('rc_ui_mode') !== 'simple';
}

// Restaure au chargement le dossier choisi lors d'une session précédente, si
// la permission est encore valable — queryPermission() ne montre jamais de
// popup (contrairement à requestPermission(), qui exige un geste utilisateur,
// d'où le bouton « Dossier… » pour la reconnexion si la permission a expiré).
async function initAudioRecorderPanel(){
  try{
    const handle = await _recIdbGet('dirHandle');
    if(handle && (await handle.queryPermission({mode: 'readwrite'})) === 'granted'){
      _recDirHandle = handle;
    }
  }catch(e){}
  _updateRecDirLabel();
  if(recEnabled && !_recAutoStartAllowed()){
    // Mode UI simple : on refuse l'auto-démarrage ET on resynchronise l'état
    // persisté (sinon 'logx_rec_enabled' resterait 'on' en localStorage alors
    // que rien n'enregistre réellement — incohérence au prochain passage en
    // mode expert, qui redémarrerait le micro sans que l'utilisateur l'ait
    // redemandé cette fois-là).
    recEnabled = false;
    localStorage.setItem('logx_rec_enabled', 'off');
  } else if(recEnabled){
    const ok = await startAudioRecorder();
    if(!ok){
      // Permission refusée/périphérique disparu depuis : ne pas rester dans
      // un état incohérent — corriger AUSSI localStorage, pas seulement la
      // variable JS locale (sinon un rechargement de page retenterait
      // indéfiniment le même auto-démarrage voué à l'échec).
      recEnabled = false;
      localStorage.setItem('logx_rec_enabled', 'off');
    }
  }
  _updateRecToggleBtn();
}

// ─── Encodage WAV (PCM 16 bits) à partir de plusieurs AudioBuffer ───────────
// Concatène les canaux en ne gardant que les `maxSeconds` dernières secondes
// (les segments les plus anciens fournis peuvent dépasser la fenêtre voulue :
// seule leur QUEUE est conservée).
function _encodeWavFromBuffers(buffers, maxSeconds){
  const sampleRate = buffers[buffers.length-1].sampleRate;
  const numChannels = buffers[buffers.length-1].numberOfChannels || 1;
  const maxSamples = Math.round(maxSeconds * sampleRate);
  let totalLen = 0;
  buffers.forEach(b => totalLen += b.length);
  const keepLen = Math.min(totalLen, maxSamples);

  const channels = [];
  for(let ch = 0; ch < numChannels; ch++){
    const out = new Float32Array(keepLen);
    let writePos = keepLen;   // rempli depuis la fin vers le début
    for(let i = buffers.length - 1; i >= 0 && writePos > 0; i--){
      const b = buffers[i];
      const data = ch < b.numberOfChannels ? b.getChannelData(ch) : b.getChannelData(0);
      const take = Math.min(data.length, writePos);
      out.set(data.subarray(data.length - take), writePos - take);
      writePos -= take;
    }
    channels.push(out);
  }
  return _floatChannelsToWav(channels, sampleRate);
}

function _floatChannelsToWav(channels, sampleRate){
  const numChannels = channels.length;
  const numFrames = channels[0].length;
  const blockAlign = numChannels * 2;   // PCM 16 bits = 2 octets/échantillon
  const dataSize = numFrames * blockAlign;
  const buf = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buf);
  const writeStr = (off, s) => { for(let i=0;i<s.length;i++) view.setUint8(off+i, s.charCodeAt(i)); };
  writeStr(0, 'RIFF'); view.setUint32(4, 36 + dataSize, true); writeStr(8, 'WAVE');
  writeStr(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);   // PCM
  view.setUint16(22, numChannels, true); view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true); view.setUint16(32, blockAlign, true); view.setUint16(34, 16, true);
  writeStr(36, 'data'); view.setUint32(40, dataSize, true);
  let off = 44;
  for(let i = 0; i < numFrames; i++){
    for(let ch = 0; ch < numChannels; ch++){
      const s = Math.max(-1, Math.min(1, channels[ch][i]));
      view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      off += 2;
    }
  }
  return new Blob([buf], {type: 'audio/wav'});
}

// Nom de fichier indicatif_bande_date_heure — ex. F4ABC_144_20260723_143205.wav
// qso.time ne contient que HH:MM (pas les secondes, voir nowUTC()) : deux QSO
// du même indicatif+bande dans la MÊME MINUTE UTC (ex. relogué après un
// bust, ou dupe autorisée par le règlement) produiraient sinon EXACTEMENT le
// même nom de fichier — le second clip écraserait silencieusement le premier.
// qso.id (Date.now() au moment du log, voir submitQSO) donne une précision à
// la milliseconde : on en dérive heure:minute:seconde pour lever la collision.
function _recClipName(qso){
  const call = String(qso.call || 'QSO').replace(/[^A-Za-z0-9]/g, '') || 'QSO';
  const band = String(qso.band || '').replace(/[^A-Za-z0-9]/g, '');
  const stamp = qso.id ? new Date(qso.id) : new Date();
  const time = String(stamp.getUTCHours()).padStart(2, '0')
    + String(stamp.getUTCMinutes()).padStart(2, '0')
    + String(stamp.getUTCSeconds()).padStart(2, '0');
  return `${call}_${band}_${qso.date || ''}_${time}.wav`;
}

// Sauvegarde via l'API File System Access si un dossier a été choisi (et que
// la permission tient toujours), sinon repli sur un téléchargement classique.
async function _recSaveClip(blob, name){
  if(_recDirHandle){
    try{
      if((await _recDirHandle.queryPermission({mode: 'readwrite'})) === 'granted'){
        const fh = await _recDirHandle.getFileHandle(name, {create: true});
        const w = await fh.createWritable();
        await w.write(blob);
        await w.close();
        notify(trF('🎙️ Clip QSO enregistré : {name}', {name}));
        return;
      }
    }catch(e){ console.warn('[REC] écriture dossier échouée, repli téléchargement', e); }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
  notify(trF('🎙️ Clip QSO téléchargé : {name}', {name}));
}

// Appelée juste après chaque QSO loggué avec succès (voir submitQSO). Ne
// bloque jamais le flux de saisie : appelée sans await depuis submitQSO,
// erreurs avalées.
async function captureQsoAudioClip(qso){
  if(!recEnabled || !_recStream) return;
  try{
    await _recFinishCurrentSegment();
    _recStartSegment();   // ré-enchaîne aussitôt le tampon glissant

    const cutoff = Date.now() - REC_CLIP_SECONDS * 1000;
    const segs = _recSegments.filter(s => s.end > cutoff);
    if(!segs.length) return;

    const ctx = _audioCtx || (_audioCtx = new (window.AudioContext || window.webkitAudioContext)());
    const buffers = [];
    for(const s of segs){
      try{
        const arr = await s.blob.arrayBuffer();
        buffers.push(await ctx.decodeAudioData(arr));
      }catch(e){ /* segment trop court/corrompu (ex: tout premier après un redémarrage) : ignoré */ }
    }
    if(!buffers.length) return;

    const wav = _encodeWavFromBuffers(buffers, REC_CLIP_SECONDS);
    await _recSaveClip(wav, _recClipName(qso));
  }catch(e){ console.warn('[REC] capture clip QSO', e); }
}

// ─── CALLBOT (macros vocales DYNAMIQUES : synthèse + PTT + émission radio) ───
// Contrairement aux macros CW ({CALL} = TA propre station, jamais celle du
// correspondant — pas besoin en CW de re-taper l'indicatif de l'autre), ici
// {CALL} = LE CORRESPONDANT actuellement tapé dans la saisie (l'usage typique
// en phonie : confirmer qui on appelle avant le report), {MYCALL} = ta station.
const VOICE_MACRO_DEFAULT = [
  {key:'B1', label:'CQ', text:'CQ Contest, {MYCALL}'},
  {key:'B2', label:'RÉPONSE', text:'{CALL}'},
  {key:'B3', label:'REPORT', text:'{RST_SENT}, {MYCALL}'},
  {key:'B4', label:'73 + MERCI', text:'{TNX}, {MYCALL}'},
];
function getVoiceDynMacros(){ try{ const s=localStorage.getItem('logx_voice_macros'); return s?JSON.parse(s):VOICE_MACRO_DEFAULT; }catch(e){ return VOICE_MACRO_DEFAULT; } }
function saveVoiceDynMacros(m){ localStorage.setItem('logx_voice_macros', JSON.stringify(m)); }

function renderVoiceDynPanel(){
  const btns = document.getElementById('voiceDynBtns');
  if(!btns) return;
  const macros = getVoiceDynMacros();
  btns.innerHTML = '';
  macros.forEach((m, idx) => {
    const btn = document.createElement('button');
    btn.className = 'macro-btn';
    btn.title = m.text;
    btn.innerHTML = `<span class="mk">${m.key}</span><span class="mt">${m.label}</span>`;
    btn.onclick    = e => { e.stopPropagation(); sendVoiceDynMacro(idx); };
    btn.ondblclick = e => { e.stopPropagation(); editVoiceDynMacro(idx); };
    btns.appendChild(btn);
  });
}

async function sendVoiceDynMacro(idx){
  const m = getVoiceDynMacros()[idx]; if(!m) return;
  const cfg = JSON.parse(localStorage.getItem('logx_config')||'{}');
  const rstRcvdEl = document.getElementById('inputRSTrcvd');
  const numSentEl = document.getElementById('inputNumSent');
  const payload = {
    template: m.text,
    call: document.getElementById('inputCall').value.trim(),
    mycall: cfg.callsign_contest || cfg.callsign || myCall || '',
    rst_sent: document.getElementById('inputRSTsent').value.trim() || '59',
    rst_rcvd: rstRcvdEl ? rstRcvdEl.value.trim() : '',
    nr: numSentEl ? numSentEl.value.trim() : '',
  };
  const out = document.getElementById('voiceDynResult');
  if(out) out.textContent = '⏳…';
  try{
    const r = await fetch('/rig/voice', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)});
    const d = await r.json();
    if(out) out.textContent = d.ok ? `📻 « ${d.text} »` : `❌ ${d.error}`;
  }catch(e){
    if(out) out.textContent = '❌ ' + e.message;
  }
}

function editVoiceDynMacro(idx){
  const macros = getVoiceDynMacros();
  const m = macros[idx];
  const newLabel = prompt(trF('Label pour {k} :', {k: m.key}), m.label);
  if(newLabel === null) return;
  const newText = prompt(trT('Message ({CALL}=correspondant · {MYCALL}=toi · {RST_SENT}/{RST_RCVD}/{NR} en toutes lettres · {TNX}=73+merci selon le pays) :'), m.text);
  if(newText === null) return;
  macros[idx] = {...m, label:newLabel.trim()||m.label, text:newText.trim()||m.text};
  saveVoiceDynMacros(macros); renderVoiceDynPanel();
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
  notify(esmMode ? trT('⏎ ESM activé : Entrée enchaîne appel → échange → log') : trT('ESM désactivé'));
}

function esmSend(role){
  // Même repli que updateKeyerPanels() juste plus bas : le mode réel du QSO
  // (rigState.mode si le CAT est connecté, sinon currentMode) décide, JAMAIS
  // rigState.enabled. Avant ce correctif, exiger .enabled faisait passer un
  // opérateur en CW MANUEL (clé/manip externe, pas de CAT) par la voix — un
  // message vocal réel joué au lieu du CW attendu, pas une simple dégradation
  // d'affichage (trouvé le 08/08/2026 pendant l'extraction EV-7 du bloc
  // RADIO CAT, corrigé séparément sur demande explicite de F4GLD).
  const mode = (typeof rigState!=='undefined' && rigState.mode) || currentMode || '';
  const cw = /CW/i.test(mode);
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

// ─── DÉCODEUR CW ──────────────────────────────────────────────────────────────
// Un seul décodeur CW dans toute l'appli : le panneau flottant #cwPanel (bas-
// gauche, pipeline DSP dans logx_cwdecoder.js — voir toggleCwDecoder() plus
// bas dans ce fichier, qui branche CwAudioDecoder à l'UI). Il existait
// auparavant un second panneau ici (compact, dans .saisie-secondary) avec sa
// propre implémentation Web Audio + une fonction toggleCwDecoder() À ELLE :
// en JS, deux déclarations `function toggleCwDecoder(){...}` au même scope ne
// cohabitent pas, la SECONDE (celle du panneau flottant, plus bas dans ce
// fichier) écrasait silencieusement celle-ci — le bouton du panneau compact
// finissait par piloter les éléments DOM du panneau flottant, jamais les
// siens (#cwDecodeOut/#cwTone restaient figés à «—»). Supprimé : un seul
// panneau CW, plus complet (device/fréquence/sortie/WPM) et débogué (voir
// logx_cwdecoder.js). cwToCall() est conservée et réutilisée par le panneau
// flottant pour garder la fonctionnalité « clic sur un mot décodé → indicatif ».
function cwToCall(w){
  const inp=document.getElementById('inputCall');
  if(inp && /\d/.test(w)){ inp.value=w.trim().toUpperCase(); onCallInput(); inp.focus(); }
}

// ─── AFFICHAGE DES PANNEAUX SELON LE MODE ────────────────────────────────────
// cwPanelForcedOpen : le bouton dédié du band map (voir toggleCwPanelForce())
// permet d'ouvrir le décodeur CW même hors mode CW — sinon il est
// INJOIGNABLE dès que "CW" n'est pas coché dans CONFIG > MODES : le
// sélecteur de mode de la saisie ne PROPOSE alors même pas CW (voir
// renderModeButtons(), qui ne liste que les modes activés), donc rien ne
// peut jamais faire matcher /CW/i.test(mode) — retour F4GLD 05/08/2026,
// exemple donné : « je peux vouloir décoder exceptionnellement du CW même
// si CW n'est pas dans mes modes ».
let cwPanelForcedOpen = false;

function updateKeyerPanels(){
  const mode = (typeof rigState!=='undefined' && rigState.mode) || currentMode || '';
  const cw = /CW/i.test(mode);
  const rtty = /RTTY|RY/i.test(mode);
  // La radio ne signale jamais « SSTV » (elle reste en USB pendant la SSTV) :
  // seul le sélecteur de mode du logbook peut donc dire qu'on en fait.
  const sstv = /SSTV/i.test(mode) || /SSTV/i.test(currentMode || '');
  const macro=document.getElementById('macroPanel');
  const voice=document.getElementById('voicePanel');
  if(macro) macro.style.display = cw ? '' : 'none';
  // En RTTY comme en SSTV, ni les macros CW ni le keyer vocal n'ont de sens :
  // c'est le décodeur qui prend la place.
  if(voice) voice.style.display = (cw || rtty || sstv) ? 'none' : '';
  const dec = document.getElementById('rttyDecoder');
  if(dec) dec.style.display = rtty ? '' : 'none';
  // Boutons macro + chargement paresseux des périphériques RX/TX au premier
  // passage en RTTY — pas à toggleRttyPanel() (bascule collapse/expand du
  // contenu, qui ne se déclenche pas forcément avant que l'opérateur veuille
  // émettre) ni à un appel synchrone en fin de fichier : le panneau RTTY est
  // placé APRÈS les <script> dans logx_logbook.html (rttyMacroBtns n'existe
  // pas encore dans le DOM tant que le HTML qui le suit n'a pas fini de se
  // parser) — trouvé en vérification navigateur (0 bouton rendu), pas en
  // relisant le code. updateKeyerPanels() n'est appelée qu'après coup (poll
  // d'état radio, changement de mode), donc toujours après un DOM complet.
  if(rtty){
    renderRttyMacroBtns();
    if(!_rttyDevicesLoaded){
      loadAudioInputDevices('rttyDevice').then(ok => { _rttyDevicesLoaded = ok; });
      loadAudioOutputDevices('rttyOutDevice', true).then(ok => { _rttyOutDeviceLoaded = ok; });
    }
  }
  // Le panneau CW s'appelle cwPanel (pas cwDecoder) : viser le mauvais id
  // n'aurait leve AUCUNE erreur, le decodeur CW serait simplement reste
  // affiche en RTTY. Verifie contre le balisage.
  //
  // Chaque décodeur n'apparaît que dans SON mode (demande utilisateur) : un
  // panneau CW permanent en SSB ou FT8 est du bruit à l'écran. Avant, le
  // panneau CW restait affiché dans tous les modes sauf RTTY.
  const cwDec = document.getElementById('cwPanel');
  if(cwDec) cwDec.style.display = (cw || cwPanelForcedOpen) ? '' : 'none';
  // Décodeur radio 2 (SO2R Phase 2) : même règle de visibilité que le
  // décodeur radio 1, ET seulement si une radio 2 est déclarée — un second
  // panneau CW sur une station mono-radio serait juste un bandeau vide.
  const cwDec2 = document.getElementById('cwPanel2');
  if(cwDec2){
    let cat2Enabled = false;
    try{ cat2Enabled = !!JSON.parse(localStorage.getItem('logx_config')||'{}').cat2_enabled; }catch(e){}
    cwDec2.style.display = ((cw || cwPanelForcedOpen) && cat2Enabled) ? '' : 'none';
  }
  const sstvDec = document.getElementById('sstvPanel');
  if(sstvDec) sstvDec.style.display = sstv ? '' : 'none';
}

// Bouton dédié du band map : ouvre/ferme le décodeur CW SANS toucher aux
// macros F1-F8 ni au keyer vocal (contrairement à un vrai passage en mode
// CW, qui les affecte aussi — voir le commentaire de cwPanelForcedOpen).
// Bascule manuelle simple : reste ouvert tant qu'on ne reclique pas,
// même si le mode de saisie change entretemps (l'opérateur a
// explicitement demandé ce panneau, un changement de mode ailleurs ne
// doit pas le refermer dans son dos).
function toggleCwPanelForce(){
  cwPanelForcedOpen = !cwPanelForcedOpen;
  updateKeyerPanels();
  const btn = document.getElementById('cwForceBtn');
  if(btn) btn.style.color = cwPanelForcedOpen ? 'var(--green)' : 'var(--accent2)';
}

// ─── SO2R : bascule d'émission ───────────────────────────────────────────────
// L'état vit CÔTÉ SERVEUR : le band map, la barre de statut et toute page
// ouverte doivent voir la même radio en émission. Le tenir dans le navigateur
// ferait diverger deux écrans du même poste.
let _so2rFocus = 1;

async function so2rBasculer(radio){
  try{
    const res = await fetch('/so2r/focus', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(radio ? {radio} : {})}).then(r => r.json());
    if(res.focus){ _so2rFocus = res.focus; so2rAfficher(res); }
    if(!res.ok) notify(trF('❌ SO2R : {err}', {err: res.error || 'échec'}));
    else notify(trF('🎚 Émission → radio {n}', {n: res.focus}));
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
}

function so2rAfficher(etat){
  const el = document.getElementById('so2rIndicateur');
  if(!el) return;
  // L'indicateur n'apparaît QUE si une seconde radio est déclarée : sur une
  // station mono-radio, un voyant « RADIO 1 » permanent serait du bruit.
  if(!etat || !etat.configure){ el.style.display = 'none'; return; }
  el.style.display = '';
  el.textContent = '🎚 TX R' + (etat.focus || 1) + (etat.ecoute ? ' · ' + etat.ecoute : '');
}

async function so2rRafraichir(){
  try{
    const etat = await fetch('/so2r/state').then(r => r.json());
    if(etat && etat.focus){ _so2rFocus = etat.focus; }
    so2rAfficher(etat);
  }catch(e){ /* serveur injoignable : on garde le dernier état connu */ }
}

// PANNEAU DECODEUR + EMISSION RTTY : extrait vers logx_rtty_panel.js
// (EV-7 phase 2, 15e increment, docs/LogX_AI_PRD.md) -- charge en
// <script> classique dans logx_logbook.html, portee globale partagee.

// PANNEAU DECODEUR SSTV : extrait vers logx_sstv_panel.js (EV-7 phase 2,
// 14e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.
// Au démarrage on demande au SERVEUR quels messages existent : ils n'ont
// jamais été dans ce navigateur si l'opérateur les a enregistrés ailleurs.
voiceRefreshSlots();
renderVoiceDynPanel();
setTimeout(updateKeyerPanels, 300);
initAudioRecorderPanel();

// ─── SAUVEGARDE IMMÉDIATE (dossier cloud/NAS) ────────────────────────────────
async function backupNow(){
  try{
    const r = await fetch('/backup/now', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const d = await r.json();
    if(d.ok) notify(trF('💾 Sauvegarde OK → {folder} ({n} fichiers)', {folder: d.folder, n: d.files.length}));
    else notify(trF('❌ {err} — configure le dossier dans CONFIG', {err: d.error || trT('sauvegarde impossible')}));
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
}

// ─── SETUP ───────────────────────────────────────────────────────────────────
function setupDone(){
  const call = document.getElementById('setupCallsign').value.trim().toUpperCase();
  const loc  = document.getElementById('setupLocator').value.trim().toUpperCase();
  const op   = document.getElementById('setupOperator').value;
  // LOGBOOK SIMPLE : le sélecteur de concours est masqué, mais le champ caché
  // peut garder la valeur d'un concours choisi/testé avant de changer de mode
  // — ne jamais le réinjecter dans ce cas (bandes/modes/en-tête doivent rester
  // "libres", pas hérités d'un ancien concours).
  const cont = usageMode === 'simple' ? '' : document.getElementById('setupContest').value;

  if(!call||!loc||!op){
    notify('Remplis tous les champs !');
    return;
  }

  myCall = call;
  myLocator = loc;
  myOp = op;
  currentContest = cont;

  // Synchroniser le concours dans la config partagée (logx_configuration.html le lira aussi)
  let stored = {};
  try{
    stored = JSON.parse(localStorage.getItem('logx_config')||'{}');
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
    localStorage.setItem('logx_config', JSON.stringify(stored));
  }catch(e2){}

  // Afficher uniquement les bandes et modes autorisés par le concours choisi
  renderBandButtons(cont);
  renderModeButtons(cont);
  applyExchangeFormat(cont);
  // Activation POTA/SOTA/IOTA/WWFF (config locale prioritaire, sinon serveur
  // partagé) — DOIT être appliqué avant applyExpeditionMode() ci-dessous, qui
  // lit activationProgram pour décider si la saisie simplifiée est légitime.
  applyActivationMode(
    stored.activation_program || (typeof serverActivationProgram !== 'undefined' ? serverActivationProgram : ''),
    stored.my_activation_ref  || (typeof serverActivationRef !== 'undefined' ? serverActivationRef : ''));
  // Priorité au réglage local (page CONFIG de ce navigateur) ; sinon on hérite
  // du réglage serveur partagé pour que tous les postes d'expédition l'aient.
  applyExpeditionMode(stored.expedition_mode !== undefined && stored.expedition_mode !== ''
    ? stored.expedition_mode
    : (typeof serverExpeditionMode !== 'undefined' ? serverExpeditionMode : ''));

  // Sélectionner le bon opérateur (bouton courant + popup)
  _setCurrentOpLabel(op);

  // Affichage proéminent de la station opérée : indicatif, locator, altitude, département
  const hdrParts = [call, loc];
  if(stored.altitude) hdrParts.push(`${stored.altitude}m`);
  if(stored.postal && stored.postal.length>=2) hdrParts.push(`Dépt.${stored.postal.slice(0,2)}`);
  document.getElementById('hdrStation').textContent = hdrParts.join(' · ');
  document.getElementById('hdrContest').textContent = cont || 'LOGBOOK';
  // Indicateur « OP : » — en single-op, montrer l'indicatif plutôt que « OP1 »
  document.getElementById('currentOp').textContent = _resolveOperatorCallsign(op || 'OP1') || op;
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
  let cfg = {};
  try{ cfg = JSON.parse(localStorage.getItem('logx_config')||'{}'); }catch(e){}
  if(cfg.contest_end_date && cfg.contest_end_utc){
    return new Date(`${cfg.contest_end_date}T${cfg.contest_end_utc}Z`);
  }
  // Repli RPH dynamique UNIQUEMENT si le concours réellement configuré est
  // REF_RPH (ou qu'aucun concours n'est encore sélectionné, ex. tout premier
  // chargement) : plusieurs concours du sélecteur (CS_DATA) n'ont PAS
  // d'entrée dans CONTEST_SCHEDULE (ex. REF_CHALLENGE_THF, REF_CCD_JAN1...),
  // donc contest_end_date n'est jamais renseigné pour eux — sans ce garde,
  // on retombait sur une date RPH sans aucun rapport avec le concours choisi.
  if(!cfg.contest || cfg.contest === 'REF_RPH'){
    return nextRPHWeekendUTC().end;
  }
  return null; // état neutre explicite : pas de date de fin connue pour ce concours
}
function getContestStartUTC(){
  try{
    const cfg = JSON.parse(localStorage.getItem('logx_config')||'{}');
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
  const utcStr = `${String(n.getUTCHours()).padStart(2,'0')}:${String(n.getUTCMinutes()).padStart(2,'0')}:${String(n.getUTCSeconds()).padStart(2,'0')}`;
  const localStr = `${String(n.getHours()).padStart(2,'0')}:${String(n.getMinutes()).padStart(2,'0')}:${String(n.getSeconds()).padStart(2,'0')}`;
  const clockEl = document.getElementById('clock');
  if(clockEl) clockEl.textContent = `${utcStr} UTC · ${localStr} local`;

  const cd  = document.getElementById('sbCountdown');
  const lbl = document.getElementById('sbCountdownLbl');
  const box = document.getElementById('sbCountdownItem');

  // ── Phase 1 : concours pas encore commencé ──────────────────────────────
  // Si contestStartUTC non dispo en localStorage, essayer CONTEST_SCHEDULE
  let effStartUTC = contestStartUTC;
  if(!effStartUTC && typeof CONTEST_SCHEDULE !== 'undefined'){
    try{
      const _cfg = JSON.parse(localStorage.getItem('logx_config')||'{}');
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

  // ── Phase 2bis : date de fin inconnue (concours sans dates configurées) ──
  // État neutre explicite : ne JAMAIS afficher un compte à rebours calculé
  // sur la date d'un autre concours (cf. getContestEndUTC()).
  if(!contestEndUTC){
    setCountdownLabel('unknown', '❔ DATES NON CONFIGURÉES');
    cd.textContent = '—:—:—';
    cd.style.color = 'var(--muted)';
    if(box) box.style.borderLeftColor = 'var(--muted)';
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
  else             cd.style.color = '#FF5030';
}
setInterval(updateClockAndCountdown, 1000);
updateClockAndCountdown();

// ─── OPÉRATEUR / BANDE / MODE ────────────────────────────────────────────────
// Résout un identifiant d'opérateur INTERNE ('OP1', 'OP2'...) vers son VRAI
// indicatif (config operators[idx].call), repli sur l'indicatif de la
// station. Idempotent : une valeur qui n'a pas la forme 'OPn' (déjà un
// indicatif) est renvoyée telle quelle. UNIQUEMENT pour l'AFFICHAGE/EXPORT
// (tableau, dernier QSO, classement multi-op, CSV, ADIF) — ne JAMAIS
// utiliser en amont de opColorAttr() (qui a besoin de l'ID brut 'OPn' pour
// calculer une teinte stable) ni pour la comparaison "mine"/le champ
// `operator` réellement écrit sur le QSO (myOp reste l'ID interne partout
// ailleurs — sélecteur d'opérateur, chat inter-postes). Corrige le signalement
// F4GLD du 08/08/2026 : le tableau LOGBOOK affichait le libellé brut "OP1" au
// lieu de l'indicatif réel, alors que le badge d'en-tête (#currentOp) le
// résolvait déjà — cette fonction centralise la même logique pour tous les
// autres points d'affichage/export qui en avaient besoin.
function _resolveOperatorCallsign(opIdOrCall){
  const raw = String(opIdOrCall || '').trim();
  const m = /^OP(\d+)$/i.exec(raw);
  if(!m) return raw;
  let cfg = {};
  try{ cfg = JSON.parse(localStorage.getItem('logx_config')||'{}'); }catch(e){}
  const op = (cfg.operators || [])[parseInt(m[1], 10) - 1];
  const resolved = op && String(op.call || op.callsign || '').trim();
  return resolved || cfg.callsign_contest || cfg.callsign || myCall || raw;
}

// Opérateur courant : même schéma bouton+popup que BANDE/MODE (cf. plus bas)
// plutôt qu'une rangée de jusqu'à 40 boutons (mode RADIOCLUB).
function _setCurrentOpLabel(opVal){
  const popup = document.getElementById('opPickerPopup');
  const btn = popup ? popup.querySelector(`.op-btn[data-op="${opVal}"]`) : null;
  const label = (btn && btn.textContent) || opVal;
  const lbl = document.getElementById('opCurrentLabel');
  if(lbl) lbl.textContent = label;
  if(popup) popup.querySelectorAll('.op-btn').forEach(b => b.classList.toggle('active', b.dataset.op === opVal));
  const cur = document.getElementById('currentOp');
  if(cur) cur.textContent = label;
}

function toggleOpPicker(){
  const popup = document.getElementById('opPickerPopup');
  if(!popup) return;
  popup.style.display = popup.style.display === 'none' ? 'grid' : 'none';
}

function hideOpPicker(){
  const popup = document.getElementById('opPickerPopup');
  if(popup) popup.style.display = 'none';
}

function pickOp(opVal){
  myOp = opVal;
  _setCurrentOpLabel(opVal);
  hideOpPicker();
}

// Bande courante : un seul bouton affichant la bande active + une popup pour
// en choisir une autre (cf. #bandPickerPopup, rempli par renderBandButtons()) —
// plutôt qu'une rangée de jusqu'à 17 boutons simultanés, illisible dès qu'on
// active plus de 3-4 bandes.
function _setCurrentBandLabel(band){
  const lbl = document.getElementById('bandCurrentLabel');
  if(lbl) lbl.textContent = BAND_LABELS[band] || band + ' MHz';
  const popup = document.getElementById('bandPickerPopup');
  if(popup) popup.querySelectorAll('.bm-btn').forEach(b => b.classList.toggle('active', b.dataset.val === band));
}

function toggleBandPicker(){
  const popup = document.getElementById('bandPickerPopup');
  if(!popup) return;
  popup.style.display = popup.style.display === 'none' ? 'grid' : 'none';
}

function hideBandPicker(){
  const popup = document.getElementById('bandPickerPopup');
  if(popup) popup.style.display = 'none';
}

// Fermeture au clic en dehors du bouton/popup (pas de champ à onblur ici,
// contrairement aux suggestions de recherche — un vrai listener global s'impose).
// Gère aussi bien le popup BANDE que le popup MODE (même schéma).
document.addEventListener('click', e => {
  [['bandPickerPopup','bandCurrentBtn'], ['modePickerPopup','modeCurrentBtn'], ['opPickerPopup','opCurrentBtn']].forEach(([popupId, btnId]) => {
    const popup = document.getElementById(popupId);
    const btn = document.getElementById(btnId);
    if(popup && popup.style.display !== 'none' && !popup.contains(e.target) && e.target !== btn && !btn.contains(e.target)){
      popup.style.display = 'none';
    }
  });
});

function pickBand(band){
  currentBand = band;
  _setCurrentBandLabel(band);
  hideBandPicker();
  setFreqForBand(currentBand);
  updateSerialDisplay();
  if(typeof refreshBandMap === 'function') refreshBandMap();  // spots de la nouvelle bande
  document.getElementById('inputCall').focus();
}

// Mode courant : même schéma que la bande (un bouton + popup, cf. plus haut)
// plutôt qu'une rangée de jusqu'à 6 boutons (SSB/CW/FM/FT8/FT4/RTTY).
function _setCurrentModeLabel(mode){
  const lbl = document.getElementById('modeCurrentLabel');
  if(lbl) lbl.textContent = mode;
  const popup = document.getElementById('modePickerPopup');
  if(popup) popup.querySelectorAll('.bm-btn').forEach(b => b.classList.toggle('active', b.dataset.val === mode));
}

function toggleModePicker(){
  const popup = document.getElementById('modePickerPopup');
  if(!popup) return;
  popup.style.display = popup.style.display === 'none' ? 'grid' : 'none';
}

function hideModePicker(){
  const popup = document.getElementById('modePickerPopup');
  if(popup) popup.style.display = 'none';
}

function pickMode(mode){
  currentMode = mode;
  _setCurrentModeLabel(mode);
  hideModePicker();
  if(typeof updateKeyerPanels==='function') updateKeyerPanels();  // keyer vocal/CW
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
  updateFreqLockIcon();
}

// Cadenas visuel à côté du champ FRÉQUENCE : rend visible ce que le code sait
// déjà en interne (dataset.userEdited) mais que rien à l'écran ne montrait —
// fermé = suit la radio (CAT), ouvert = saisie manuelle, la radio n'écrase
// plus tant que la bande ne change pas ou que le bouton Radio n'est pas
// cliqué (freqFromRig()). Masqué si le CAT n'est pas connecté : pas de
// notion de verrou sans radio à suivre.
function updateFreqLockIcon(){
  const icon = document.getElementById('freqLockIcon');
  const el = document.getElementById('inputFreq');
  if(!icon || !el) return;
  const catOn = (typeof rigState !== 'undefined') && rigState && rigState.enabled;
  if(!catOn){ icon.style.display = 'none'; return; }
  icon.style.display = '';
  if(el.dataset.userEdited){
    icon.title = 'Fréquence saisie à la main — la radio ne l\'écrase plus (bouton Radio pour resynchroniser)';
    icon.innerHTML = '<svg viewBox="0 0 18 18" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="8" width="10" height="7" rx="1.3"/><path d="M6 8V5.5a3 3 0 0 1 5.8-1"/></svg>';
  } else {
    icon.title = 'Fréquence suit la radio (CAT) en direct — tape pour reprendre la main';
    icon.innerHTML = '<svg viewBox="0 0 18 18" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="8" width="10" height="7" rx="1.3"/><path d="M6 8V5.5a3 3 0 0 1 6 0V8"/></svg>';
  }
}

// L'opérateur tape une fréquence → sélectionne automatiquement la bonne bande
// (parmi les bandes actuellement autorisées — cf. _currentVisibleBands, rempli
// par renderBandButtons() ; une bande hors de cet ensemble, ex. non cochée
// dans les toggles, ne change pas la bande courante, comme avant ce correctif).
function onFreqInput(){
  const el = document.getElementById('inputFreq');
  if(!el) return;
  el.dataset.userEdited = '1';   // saisie manuelle → le CAT ne doit plus écraser
  updateFreqLockIcon();
  const b = bandFromFreq(el.value);
  if(b && b !== currentBand && _currentVisibleBands.includes(b)){
    currentBand = b;
    _setCurrentBandLabel(b);
    updateSerialDisplay();
    if(typeof refreshBandMap === 'function') refreshBandMap();
  }
}

// Bouton 📻 : force la lecture de la fréquence radio (CAT) dans le champ.
function freqFromRig(){
  const el = document.getElementById('inputFreq');
  if(el && typeof rigState === 'object' && rigState && rigState.freq_khz > 0){
    el.value = (rigState.freq_khz / 1000).toFixed(3);
    onFreqInput();
    delete el.dataset.userEdited;   // on suit à nouveau la radio en direct
    updateFreqLockIcon();
  } else {
    notify('Radio non connectée (CAT) — saisis la fréquence à la main.');
  }
}

// ─── BANDES & MODES PAR CONCOURS (selon règlements REF / IARU / CQ) ───────────
const BAND_LABELS = {
  // HF — noms par longueur d'onde (dont les 3 bandes WARC, sans concours —
  // nécessaires pour des événements comme le World Wide Award)
  '1.8':'160m','3.5':'80m','7':'40m','10.1':'30m','14':'20m','18':'17m',
  '21':'15m','24':'12m','28':'10m',
  // VHF/UHF/SHF
  '50':'6m','70':'4m','144':'2m','432':'70cm','1296':'23cm',
  '2320':'13cm','3400':'9cm','5760':'6cm','10368':'3cm',
  '24048':'6mm','47088':'4mm',
};
// Fréquence d'appel par défaut (MHz) par bande — pré-remplit le champ FRÉQUENCE
// quand on change de bande (sauf si le CAT donne la fréquence réelle).
// 30m : pas de phonie (accord international) -> fréquence en zone CW/data.
const BAND_FREQ = {
  '1.8':'1.843','3.5':'3.650','7':'7.130','10.1':'10.116','14':'14.150',
  '18':'18.100','21':'21.250','24':'24.910','28':'28.400',
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
// BANDS_HF volontairement SANS les bandes WARC (10.1/18/24 MHz) : elles sont
// exclues par accord international de tous les concours HF classiques
// (CQ WW, ARRL FD...) — ne jamais les ajouter à cette constante partagée.
const BANDS_HF  = ['1.8','3.5','7','14','21','28'];
const BANDS_HF_WARC = ['1.8','3.5','7','10.1','14','18','21','24','28']; // + WARC (ex. World Wide Award)
const ALL_BANDS = ['1.8','3.5','7','10.1','14','18','21','24','28','50','70','144','432','1296','2320','3400','5760','10368','24048','47088'];

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
  // World Wide Award : 80-40-30-20-17-15-12-10m (pas de 160m, cf. règlement §4)
  WWA_2027_JAN:  ['3.5','7','10.1','14','18','21','24','28'],
  WWA_2027_JUL:  ['3.5','7','10.1','14','18','21','24','28'],
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
  // World Wide Award : CW/SSB/DIGI(FT8,FT4,FT2,RTTY,PSK) — règlement §5
  WWA_2027_JAN:  ['SSB','CW','FT8','FT4','FT2','RTTY','PSK'],
  WWA_2027_JUL:  ['SSB','CW','FT8','FT4','FT2','RTTY','PSK'],
  CUSTOM:        ['SSB','CW','FM','FT8'],
};

// Correspondance valeur bande → clé toggle configuration
const BAND_TOGGLE_KEY = {
  '1.8':   'band_160m', '3.5':   'band_80m',  '7':     'band_40m',
  '10.1':  'band_30m',  '14':    'band_20m',  '18':    'band_17m',
  '21':    'band_15m',  '24':    'band_12m',  '28':    'band_10m',
  '50':    'band_6m',   '70':    'band_4m',    '144':   'band_2m',
  '432':   'band_70cm', '1296':  'band_23cm',  '2320':  'band_13cm',
  '3400':  'band_9cm',  '5760':  'band_6cm',   '10368': 'band_3cm',
  '24048': 'band_6mm',  '47088': 'band_4mm',
};

// Bandes actuellement autorisées (concours + toggles) — utilisé par
// onFreqInput() pour valider une bascule automatique de bande, et par le
// popup de choix de bande (#bandPickerPopup) pour lister les alternatives.
let _currentVisibleBands = [];

function renderBandButtons(contest){
  // Bandes du concours filtrées par les toggles de configuration
  const contestBands = CONTEST_BANDS[contest] || ALL_BANDS;

  // Lire les toggles depuis localStorage pour masquer les bandes décochées
  let toggles = {};
  try{ toggles = JSON.parse(localStorage.getItem('logx_config')||'{}').toggles || {}; }catch(e){}

  const finalBands = contestBands.filter(b => {
    const key = BAND_TOGGLE_KEY[b];
    // Si la clé toggle n'existe pas → bande toujours visible
    // Si le toggle est explicitement false → bande masquée
    return !key || toggles[key] !== false;
  });

  const visibleBands = finalBands.length ? finalBands : contestBands; // fallback si tout est masqué
  _currentVisibleBands = visibleBands;
  const popup = document.getElementById('bandPickerPopup');
  if(popup){
    popup.innerHTML = visibleBands.map(b =>
      `<button class="bm-btn${b===visibleBands[0]?' active':''}" data-val="${b}" onclick="pickBand('${b}')">${BAND_LABELS[b]||b+' MHz'}</button>`
    ).join('');
  }
  currentBand = visibleBands[0];
  _setCurrentBandLabel(currentBand);
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
  'SSTV': 'mode_sstv',  // active aussi le panneau décodeur SSTV (updateKeyerPanels)
  'DIGI': 'mode_ft8',
  'FT2':  'mode_ft8',   // WWA (règlement §5) — pas de toggle dédié, rattaché à FT8
  'PSK':  'mode_rtty',  // WWA — rattaché à RTTY (même famille "DIGI" au règlement)
};

function renderModeButtons(contest){
  const allModes = CONTEST_MODES[contest] || ['SSB','CW','FM','FT8'];
  // Modes affichés = modes explicitement activés par l'utilisateur en config,
  // sans se limiter à la liste par défaut du concours (ex: FT8 coché doit
  // apparaître même si le règlement du concours ne le propose pas par défaut).
  let cfgLocal = {};
  try{ cfgLocal = JSON.parse(localStorage.getItem('logx_config')||'{}'); }catch(e){}
  const toggles = cfgLocal.toggles || {};
  const hasModeTgls = Object.keys(toggles).some(k => k.startsWith('mode_'));
  // SSTV n'apparaît QUE si la case est cochée en config : aucun concours ne
  // le propose par défaut, c'est un mode d'activité (dimanches SSTV, ISS).
  const modes = hasModeTgls
    ? ['SSB','CW','FM','FT8','FT4','RTTY','SSTV'].filter(m => toggles[MODE_TOGGLE_KEY[m]] === true)
    : allModes;
  const finalModes = modes.length > 0 ? modes : allModes; // sécurité: tout afficher si rien de coché
  const popup = document.getElementById('modePickerPopup');
  if(popup){
    popup.innerHTML = finalModes.map((m,i)=>
      `<button class="bm-btn${i===0?' active':''}" data-val="${m}" onclick="pickMode('${m}')">${m}</button>`
    ).join('');
  }
  currentMode = finalModes[0];
  _setCurrentModeLabel(currentMode);
  // Le mode initial vient d'être choisi : ajuster tout de suite les panneaux
  // (décodeurs CW/SSTV, keyer). Sans cet appel, l'état par défaut du HTML
  // resterait affiché jusqu'au premier changement de mode ou retour CAT.
  if(typeof updateKeyerPanels === 'function') updateKeyerPanels();
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
  broadcastTyping(call);   // vue PARTNER : le runner diffuse sa saisie en direct
  if(typeof clearExchWarn === 'function') clearExchWarn();   // indicatif retapé : avertissement zone périmé

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
    const dup3 = usageMode !== 'simple' && isDup(call, currentBand, currentMode);
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

  // Dup check — hors concours (logbook simple), pas d'erreur "doublon"
  const dup = usageMode !== 'simple' && isDup(call, currentBand, currentMode);
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

// ─── WIDGET TIME OF DAY (jour/nuit HOME vs DX) ───────────────────────────────
let _todTimer = null, _todSeq = 0;

function refreshTimeOfDay(dxLocator){
  clearTimeout(_todTimer);
  const el = document.getElementById('todWidget');
  if(!el) return;
  if(!dxLocator){ el.style.display = 'none'; return; }
  const seq = ++_todSeq;
  _todTimer = setTimeout(async () => {
    try{
      const r = await fetch('/data/timeofday?dx=' + encodeURIComponent(dxLocator));
      if(!r.ok || seq !== _todSeq) return;
      const d = await r.json();
      if(!d.home){ el.style.display = 'none'; return; }
      const side = (label, s) => {
        if(!s) return '';
        const icon = s.is_day ? '☀️' : '🌙';
        return `<span>${icon} ${label} ${String(Math.floor(s.local_hour)).padStart(2,'0')}h${String(Math.round((s.local_hour%1)*60)).padStart(2,'0')}</span>`;
      };
      const bits = [side('CHEZ TOI', d.home)];
      if(d.dx) bits.push(side('DX', d.dx));
      el.innerHTML = bits.filter(Boolean).join('');
      el.style.display = bits.some(Boolean) ? 'flex' : 'none';
    }catch(e){ /* réseau indispo : widget inchangé */ }
  }, 400);
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
    refreshTimeOfDay('');
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
    refreshTimeOfDay(loc);
    const dist = calcDist(loc);
    const callInput = document.getElementById('inputCall')?.value?.toUpperCase()||'';
    const modeInput = currentMode||'SSB';   // le mode vit dans le picker (plus de champ inputMode)
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

  // Vérification doublon — hors concours (logbook simple), recontacter la
  // même station sur la même bande au fil des années est normal, pas une erreur.
  if(usageMode !== 'simple' && isDup(call, currentBand, currentMode)){
    if(!confirm(trF('⚠️ {call} est déjà dans le log sur {band} MHz.\nQuand même enregistrer ?', {call, band: currentBand}))) return;
  }

  // N° envoyé : auto-série (VHF) ou valeur du champ (FD classe, CQ WW zone, HF dept...)
  const numSentField = document.getElementById('inputNumSent').value.trim();
  const serial = currentExchange.auto_serial ? await nextSerial(currentBand) : numSentField;
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

  // État US (diplôme WAS) : repris de l'annuaire UNIQUEMENT s'il concerne bien
  // l'indicatif qu'on enregistre. Réserve à connaître : l'annuaire donne
  // l'adresse ACTUELLE de la station, pas forcément celle du jour du QSO —
  // pour un diplôme, seule une confirmation LoTW fait foi.
  if(_stateAnnuaire && _stateAnnuaire.call === call){
    qso.state = _stateAnnuaire.state;
  }

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
      captureQsoAudioClip(qso).catch(e => console.warn('[REC]', e));   // découpe du clip, sans bloquer la saisie
      if(esmMode) esmSend('tu');   // ESM : envoie « merci » à la validation
      // Vider le formulaire EN PREMIER (avant stats, avant tout)
      clearForm();
      document.getElementById('inputCall').focus();
      try{ renderLog(); }catch(e){ console.warn('renderLog',e); }
      try{ updateStats(); }catch(e){ console.warn('updateStats',e); }
      try{ updateLastQso(qso); }catch(e){}
      if(activationProgram) refreshActivation();   // MAJ immédiate du compteur d'activation
      playBeep(880, 80);
      vieillirPastilleBusted();      // la pastille du QSO précédent vieillit
      verifierIndicatifApres(qso);   // filet anti-busted call, APRÈS coup
    } else if(res.status === 409){
      // Doublon détecté par le serveur : l'opérateur décide (2e période,
      // dupe assumé pour l'arbitre...) — confirm() volontairement bloquant.
      const err = await res.json();
      const ex = err.existing || {};
      const atPart = ex.time ? trF(' à {t}', {t: ex.time}) : '';
      const byPart = ex.operator ? trF(' par {op}', {op: _resolveOperatorCallsign(ex.operator)}) : '';
      if(confirm(trF('DOUBLON : {call} déjà contacté sur {band} MHz en {mode}{at}{by}.\n\nEnregistrer quand même ?',
                 {call: qso.call, band: qso.band, mode: qso.mode, at: atPart, by: byPart}))){
        const res2 = await fetch('/log/add', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({...qso, force:true})
        });
        if(res2.ok){
          qsoLog.push(qso); bcBroadcast('add', qso); lastQsoTime = Date.now();
          captureQsoAudioClip(qso).catch(e => console.warn('[REC]', e));
          clearForm(); document.getElementById('inputCall').focus();
          try{ renderLog(); }catch(e){} try{ updateStats(); }catch(e){}
          playBeep(880, 80);
        } else {
          notify(trF('Erreur serveur : {err}', {err: (await res2.json()).error}));
        }
      } else {
        notify('Doublon ignoré — QSO non enregistré.');
      }
    } else {
      const err = await res.json();
      notify(trF('Erreur serveur : {err}', {err: err.error}));
    }
  }catch(e){
    // Mode hors ligne : sauvegarde locale + localStorage
    qsoLog.push(qso);
    bcBroadcast('add', qso);
    lastQsoTime = Date.now();
    captureQsoAudioClip(qso).catch(ex => console.warn('[REC]', ex));
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

// FILET ANTI-BUSTED CALL : extrait vers logx_busted_call.js (EV-7 phase 2,
// 13e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

function clearForm(){
  esmExchanged = false;   // ESM : nouveau QSO → l'échange sera à renvoyer
  clearTimeout(callLookupTimer);
  document.getElementById('inputCall').value = '';
  document.getElementById('inputCall').classList.remove('ok','error');
  if(typeof clearExchWarn === 'function') clearExchWarn();   // nouveau QSO : avertissement zone effacé
  broadcastTyping('');   // vue PARTNER : champ vidé → l'affichage distant se vide aussitôt
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
  const _tod = document.getElementById('todWidget'); if(_tod) _tod.style.display = 'none';
  const _qz = document.getElementById('qrzInfoRow'); if(_qz) _qz.style.display = 'none';
  const _qp = document.getElementById('qrzPhoto'); if(_qp){ _qp.style.display = 'none'; _qp.src = ''; }
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
// _logVersion : dernière version du log connue de CET onglet (voir
// logx_storage.log_version côté serveur). Envoyée à chaque poll : si rien n'a
// changé depuis, le serveur répond par un payload minuscule au lieu de
// retransmettre tout le log (souvent plusieurs Mo sur un log de contest/
// logbook simple de plusieurs milliers de QSO) — la quasi-totalité des polls
// de 5 s ne voient aucun changement en pratique.
let _logVersion = null;
// _serverBoot : jeton de démarrage serveur associé à _logVersion (voir
// logx_storage.SERVER_BOOT_ID) — à renvoyer avec ?since= pour que le serveur
// l'accepte. Si le serveur a redémarré entretemps le jeton ne correspond
// plus : le serveur se replie alors de lui-même sur la liste complète.
let _serverBoot = null;

// ── Version logicielle de CE poste (vérification multi-op / DXpédition) ─────
// Figée UNE SEULE FOIS au chargement de cette page (voir initShareLink(),
// qui la lit dans /network/info) et envoyée sur CHAQUE poll /log/list via
// ?ver=. Volontairement jamais réassignée après coup : si l'hôte redémarre
// le serveur avec une version plus récente pendant que cet onglet reste
// ouvert, cette valeur doit rester l'ANCIENNE pour que le serveur puisse la
// comparer à sa version actuelle (voir /log/status → app_version) et
// signaler "cet onglet tourne du code périmé, recharge la page" — c'est
// justement le scénario utile, pas un bug à corriger.
let _myVersion = null;
// Dernier snapshot connu (rafraîchi toutes les 60 s par refreshCluster() via
// /log/status) — réutilisé par updateVersionStatus() ET par la CHECKLIST
// (showChecklist()) pour ne pas dupliquer un appel réseau.
let _lastServerVersion = null;
let _lastPeerList = [];

// Liste les postes (soi-même inclus) dont la version déclarée diffère de la
// version SERVEUR actuelle (référence unique — voir logx_http.APP_VERSION).
// Partagée entre le badge de la barre réseau et l'item CHECKLIST pour ne
// jamais faire diverger les deux affichages.
function _versionMismatches(serverVer, myVer, peerList){
  const out = [];
  if(myVer && serverVer && myVer !== serverVer) out.push({ip: 'ce poste', version: myVer});
  (peerList || []).forEach(p => {
    if(p.version && serverVer && p.version !== serverVer) out.push({ip: p.ip, version: p.version});
  });
  return out;
}

// Met à jour le badge "⚠️ versions différentes" de la barre réseau + le
// détail (tooltip) de "Postes connectés". Un écart n'est JAMAIS bloquant :
// c'est un indicateur visuel, l'opérateur décide quoi en faire (recharger
// la page, prévenir l'hôte...).
function updateVersionStatus(data){
  const serverVer = data.app_version || null;
  const peerList  = data.peer_list || [];
  _lastServerVersion = serverVer;
  _lastPeerList = peerList;
  const warnEl  = document.getElementById('netVersionWarn');
  const peersEl = document.getElementById('netPeers');
  if(!serverVer) return;
  const mismatches = _versionMismatches(serverVer, _myVersion, peerList);
  if(warnEl){
    if(mismatches.length){
      warnEl.style.display = 'inline-flex';
      warnEl.title = 'Versions différentes détectées (recharge la page pour te mettre à jour) :\n'
        + mismatches.map(m => `${m.ip} : v${m.version}`).join('\n')
        + `\nRéférence serveur : v${serverVer}`;
    } else {
      warnEl.style.display = 'none';
      warnEl.title = '';
    }
  }
  if(peersEl && peerList.length){
    peersEl.title = 'Postes connectés :\n' + peerList.map(p => {
      const flag = (p.version && p.version !== serverVer) ? ' ⚠️' : '';
      return `${p.ip} — v${p.version || '?'}${flag}`;
    }).join('\n');
  }
  // Bouton "🌐 màj réseau" (voir findNetworkUpdatePath ci-dessous) : affiché
  // uniquement quand CE poste (pas un autre pair) tourne une version
  // différente de celle du serveur — c'est le seul cas où CE poste a besoin
  // de récupérer un exécutable plus récent via le réseau local.
  const pathBtn = document.getElementById('netUpdatePathBtn');
  if(pathBtn){
    const myMismatch = !!(_myVersion && serverVer && _myVersion !== serverVer);
    pathBtn.style.display = myMismatch ? 'inline-block' : 'none';
    if(!myMismatch){
      const resEl = document.getElementById('netUpdatePathResult');
      if(resEl) resEl.textContent = '';
    }
  }
}

// ── Mise à jour réseau (relais B / pair-à-pair C secours) ────────────────────
// Complète le badge de version ci-dessus : quand CE poste tourne une version
// différente de celle du serveur ET n'a lui-même pas d'accès internet direct
// ou dégradé (cas DXpédition/contest — voir docstring de logx_update.py),
// permet de récupérer l'exécutable via un AUTRE poste du réseau local au
// lieu de GitHub directement. TOUJOURS 3 clics explicites distincts —
// jamais de sondage ni de téléchargement automatique en tâche de fond :
//   1) "🌐 màj réseau" → découverte seule (ne télécharge rien)
//   2) "mettre à jour via…" → déclenche le vrai transfert vérifié
//   3) "installer et redémarrer" → applique (comme le chemin GitHub direct)
// Chemin (B) passerelle proposé EN PRIORITÉ (bouton bleu/accent2) ; le
// chemin (C) pair-à-pair n'apparaît QUE si aucune passerelle n'a été
// trouvée, et reste étiqueté "secours" (bouton jaune, libellé explicite)
// pour que l'opérateur voie tout de suite qu'il s'agit d'un repli, pas du
// chemin habituel.
async function findNetworkUpdatePath(){
  const resEl = document.getElementById('netUpdatePathResult');
  if(!resEl) return;
  const ips = (_lastPeerList || []).map(p => p.ip).filter(Boolean);
  if(!ips.length){
    resEl.textContent = "aucun autre poste détecté sur le réseau pour l'instant.";
    return;
  }
  resEl.textContent = 'recherche sur le réseau…';
  try{
    const r = await fetch('/app/update_network_scan', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ips})
    });
    const d = await r.json();
    _renderNetworkUpdatePath(d);
  }catch(e){
    resEl.textContent = 'recherche impossible.';
  }
}

function _renderNetworkUpdatePath(d){
  const resEl = document.getElementById('netUpdatePathResult');
  if(!resEl) return;
  if(d.gateways && d.gateways.length){
    const ip = d.gateways[0];
    resEl.innerHTML = 'passerelle trouvée : ' + ip
      + `<button class="net-upd-gateway" onclick="startNetworkUpdate('gateway','${ip}')">mettre à jour via cette passerelle</button>`;
  } else if(d.peers && d.peers.length){
    const ip = d.peers[0];
    resEl.innerHTML = 'aucune passerelle — SECOURS, pair vérifié trouvé : ' + ip
      + `<button class="net-upd-peer" onclick="startNetworkUpdate('peer','${ip}')">mettre à jour via ce pair (secours, vérifié)</button>`;
  } else {
    resEl.textContent = 'aucune passerelle ni pair disponible sur le réseau pour le moment.';
  }
}

async function startNetworkUpdate(mode, ip){
  const resEl = document.getElementById('netUpdatePathResult');
  if(resEl) resEl.textContent = (mode === 'gateway'
    ? 'téléchargement via la passerelle ' : 'téléchargement (SECOURS) via le pair ') + ip + '…';
  try{
    const r = await fetch('/app/update_download_via_network', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mode, ips: [ip]})
    });
    const d = await r.json();
    if(!d.ok){
      if(resEl) resEl.textContent = 'échec : ' + (d.error || '?');
      return;
    }
    _pollNetworkUpdateStatus();
  }catch(e){
    if(resEl) resEl.textContent = 'échec réseau.';
  }
}

function _pollNetworkUpdateStatus(){
  fetch('/app/update_status').then(r => r.ok ? r.json() : null).then(d => {
    const resEl = document.getElementById('netUpdatePathResult');
    if(!d || !resEl) return;
    if(d.status === 'downloading'){
      resEl.textContent = `téléchargement… ${d.pct || 0}%`;
      setTimeout(_pollNetworkUpdateStatus, 800);
    } else if(d.status === 'done' && d.verified){
      const via = d.via === 'peer' ? 'pair — SECOURS, vérifié' : 'passerelle';
      resEl.innerHTML = `✅ v${d.version} vérifiée (via ${via}${d.via_peer ? ' ' + d.via_peer : ''}) `
        + `<button class="net-upd-gateway" onclick="installNetworkUpdate()">installer et redémarrer</button>`;
    } else if(d.status === 'error'){
      resEl.textContent = 'échec : ' + (d.error || '?');
    }
  }).catch(()=>{});
}

function installNetworkUpdate(){
  const resEl = document.getElementById('netUpdatePathResult');
  if(resEl) resEl.textContent = 'redémarrage…';
  fetch('/app/update_install', {method: 'POST'})
    .then(()=> setTimeout(_pollServerBackUpAfterNetworkUpdate, 2500));
}

function _pollServerBackUpAfterNetworkUpdate(){
  // Même mécanisme que pollServerBackUp() de logx_statusbar.js (le serveur
  // coupe volontairement le processus après /app/update_install pour que le
  // script auxiliaire remplace l'exécutable) — dupliqué ici volontairement :
  // logx_statusbar.js est une IIFE qui n'expose pas cette fonction.
  fetch('/data/rules_status', {cache: 'no-store'}).then(r => {
    if(r.ok) location.reload();
    else setTimeout(_pollServerBackUpAfterNetworkUpdate, 2000);
  }).catch(()=> setTimeout(_pollServerBackUpAfterNetworkUpdate, 2000));
}

// Fusionne un delta serveur (QSO ajoutés/modifiés + id supprimés, voir
// /log/list?since=) dans le cache local qsoLog SANS tout remplacer — un QSO
// édité garde sa position (édition en place), un QSO neuf est ajouté en fin
// de liste, un QSO supprimé est retiré même s'il n'apparaît plus jamais dans
// aucune réponse serveur (d'où la liste `deletedIds` séparée : sans elle, un
// QSO supprimé resterait affiché indéfiniment côté client).
function _mergeLogDelta(changedQsos, deletedIds){
  if(deletedIds && deletedIds.length){
    const delSet = new Set(deletedIds);
    qsoLog = qsoLog.filter(q => !delSet.has(q.id));
  }
  if(changedQsos && changedQsos.length){
    const indexById = new Map();
    qsoLog.forEach((q,i)=>indexById.set(q.id,i));
    changedQsos.forEach(q=>{
      const i = indexById.get(q.id);
      if(i != null){ qsoLog[i] = q; }
      else { indexById.set(q.id, qsoLog.length); qsoLog.push(q); }
    });
  }
}

async function fetchLog(){
  try{
    // ?since=&boot= : synchro différentielle (voir logx_http._valid_since) —
    // ne redemande que ce qui a changé depuis _logVersion au lieu de tout le
    // log. ?v= reste envoyé en parallèle : garde le repli "unchanged" déjà en
    // place (le plus rapide des trois cas de figure) quand rien n'a bougé.
    let url = '/log/list';
    if(_logVersion != null){
      url = `/log/list?v=${_logVersion}&since=${_logVersion}`;
      if(_serverBoot) url += `&boot=${_serverBoot}`;
    }
    // ?ver= : version logicielle de CE poste, figée au chargement de la page
    // (voir _myVersion ci-dessus) — alimente peer_versions côté serveur pour
    // que /log/status puisse exposer "qui tourne quelle version" à tous les
    // postes connectés (voir updateVersionStatus()).
    if(_myVersion) url += (url.includes('?') ? '&' : '?') + `ver=${encodeURIComponent(_myVersion)}`;
    const res = await fetch(url);
    if(!res.ok) return;
    const data = await res.json();
    if(data.boot) _serverBoot = data.boot;
    if(data.unchanged){
      // Rien de neuf : juste confirmer la connectivité, aucun re-render/parsing
      // du log (l'essentiel du gain : pas de reconstruction du tableau DOM).
      const dot = document.getElementById('netDot');
      dot.className = 'net-dot online';
      document.getElementById('netStatus').textContent = 'Connecté au serveur';
      document.getElementById('netPeers').textContent = data.peers || '1';
      syncOfflineQueue();
      return;
    }
    if(data.version != null) _logVersion = data.version;
    if(data.qsos){
      // Recalculer les sériaux — toujours le plus grand N° envoyé déjà utilisé,
      // jamais un simple comptage (sinon une suppression ou un trou fait reculer le compteur)
      // (valable aussi en delta : serialByBand porte déjà le maximum vu lors
      // des polls précédents, il ne manque que ce qui vient de changer)
      const maxSerialByBand = {};
      data.qsos.forEach(q=>{
        const n = parseInt(q.num_sent, 10);
        if(!isNaN(n) && n > (maxSerialByBand[q.band]||0)) maxSerialByBand[q.band] = n;
      });
      Object.keys(maxSerialByBand).forEach(band=>{
        if(maxSerialByBand[band] > (serialByBand[band]||0)) serialByBand[band] = maxSerialByBand[band];
      });
      if(data.delta){
        _mergeLogDelta(data.qsos, data.deleted);
      } else {
        qsoLog = data.qsos;
        resetLogRenderWindow(); // resync complet : autre contenu, la fenêtre de rendu ne s'applique plus
      }
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
    // Capture UNE SEULE FOIS la version de ce serveur comme "ma version" — voir
    // le commentaire sur _myVersion plus haut : ne jamais réassigner ensuite,
    // même si initShareLink() est rappelée plus tard (repli hors-ligne ci-dessous).
    if(d.app_version && _myVersion == null){
      _myVersion = d.app_version;
      const vEl = document.getElementById('netVersion');
      if(vEl) vEl.textContent = 'v' + _myVersion;
    }
  }).catch(()=>{ setTimeout(initShareLink, 10000); }); // serveur pas encore prêt
}
initShareLink();

function copyShareLink(){
  const url = document.getElementById('shareLink')?.href || '';
  if(!url || url.endsWith('#')){ notify('Adresse pas encore disponible — serveur injoignable ?'); return; }
  navigator.clipboard.writeText(url)
    .then(()=>notify(trF('📋 Adresse copiée : {url}\nColle-la dans le navigateur des autres postes (même WiFi).', {url})))
    .catch(()=>prompt(trT('Copie manuelle (Ctrl+C) :'), url));
}

// ─── RENDER LOG ───────────────────────────────────────────────────────────────
// QSO incomplet = champ critique manquant (souvent dû à une coupure réseau ou
// un souci pendant la saisie) — jamais supprimé automatiquement, seulement
// signalé pour correction manuelle via le bouton ✏️.
function isValidQSO(q){
  return !!(q.call && q.mode && q.time && q.date && q.rst_sent && q.rst_rcvd);
}

// ─── FENÊTRE DE RENDU (virtualisation légère) ────────────────────────────────
// renderLog() était appelé à chaque nouveau QSO, clic de filtre ou frappe dans
// la recherche, et reconstruisait tbody.innerHTML avec TOUTES les lignes
// filtrées : sur un gros log (plusieurs milliers de QSO, ex. contest 48h ou
// logbook simple utilisé des années), ça régénère des milliers de <tr> en
// boucle. Le tri/filtre/recherche restent calculés sur qsoLog en entier
// (variable `filtered` ci-dessous) — seul le NOMBRE de <tr> réellement
// insérés dans le DOM est plafonné aux plus récents, avec un bouton pour
// étendre la fenêtre par paliers.
const LOG_RENDER_DEFAULT = 300;
const LOG_RENDER_STEP = 300;
let logRenderLimit = LOG_RENDER_DEFAULT;
// Mémorise le (filtre + recherche) du dernier rendu : un changement de l'un
// des deux revient à la fenêtre par défaut (nouveau contexte de consultation),
// alors qu'un nouveau QSO reçu sur le MÊME filtre garde la fenêtre déjà
// étendue par l'utilisateur (sinon "Afficher plus" se réinitialiserait tout
// seul dès le QSO suivant, en plein concours).
let _logRenderKey = null;

// À appeler chaque fois que qsoLog est REMPLACÉ (pas complété) par un autre
// contenu : reset complet (resetLog), archivage avec vidage (archiveLog en
// mode clear), resync serveur non-delta (fetchLog quand data.delta est
// absent). Sans ça, logRenderLimit/_logRenderKey restaient ceux de l'ancien
// log — currentFilter/search n'ayant pas changé, la fenêtre de rendu gardait
// sa valeur (potentiellement étendue) et ne pouvait plus jamais redescendre.
function resetLogRenderWindow(){
  logRenderLimit = LOG_RENDER_DEFAULT;
  _logRenderKey = null;
}

function showMoreLog(){
  logRenderLimit += LOG_RENDER_STEP;
  renderLog();
}

// Affiche/masque la barre "Afficher plus" selon ce qu'il reste à montrer.
function renderLogMoreBar(hiddenCount){
  const bar = document.getElementById('logMoreBar');
  if(!bar) return;
  const cnt = document.getElementById('logMoreCount');
  if(hiddenCount > 0){
    if(cnt) cnt.textContent = hiddenCount;
    bar.classList.add('show');
  } else {
    bar.classList.remove('show');
  }
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

// Constructeur de filtre avancé, recherche de doublons dédiée, re-résolution
// en masse et contrôle de net : extraits vers logx_filter_builder.js /
// logx_dup_finder.js / logx_bulk_resolve.js / logx_net_control.js (EV-7,
// docs/LogX_AI_PRD.md) — chargés en <script> classique dans
// logx_logbook.html, portée globale partagée comme tout le JS de ce projet.

function renderLog(){
  const search = document.getElementById('logSearch').value.toUpperCase();
  const tbody = document.getElementById('logBody');

  let filtered = qsoLog.filter(q=>{
    if(currentFilter==='144' && q.band!=='144') return false;
    if(currentFilter==='432' && q.band!=='432') return false;
    if(currentFilter==='hf' && !['14','7','3.5','1.8','21','28'].includes(q.band)) return false;
    if(currentFilter==='mine' && q.operator!==myOp) return false;
    if(search && !(q.call||'').includes(search) && !(q.locator||'').includes(search)) return false;
    if(advancedFilter && !matchesAdvancedFilter(q, advancedFilter)) return false;
    return true;
  });

  const incompleteCount = qsoLog.filter(q=>!isValidQSO(q)).length;
  document.getElementById('logCount').textContent = incompleteCount
    ? `${filtered.length} QSO — ⚠️ ${incompleteCount} incomplet(s)`
    : `${filtered.length} QSO`;

  // Rafraîchir la carte si elle est visible
  if(document.getElementById('mapWrap').classList.contains('visible')) refreshMapLayers();

  // Nouveau filtre/recherche => on repart de la fenêtre par défaut. Le même
  // filtre (ex. juste un nouveau QSO reçu) conserve la fenêtre déjà étendue.
  const renderKey = currentFilter + '|' + search + '|' + (advancedFilter ? JSON.stringify(advancedFilter) : '');
  if(renderKey !== _logRenderKey){
    logRenderLimit = LOG_RENDER_DEFAULT;
    _logRenderKey = renderKey;
  }

  // Pré-calculs O(n) : nombre d'occurrences (call|band) et position dans le log.
  // Avant, chaque ligne refaisait un qsoLog.filter() + un qsoLog.indexOf(),
  // soit O(n²) reconstruit toutes les 5 s — insoutenable sur un log de 3 000+ QSO.
  // Calculés sur qsoLog EN ENTIER (pas la fenêtre affichée) : le highlighting
  // doublon doit rester correct même pour les QSO pas encore rendus.
  const dupCounts = new Map();
  const posOf = new Map();
  qsoLog.forEach((x, idx) => {
    posOf.set(x, idx + 1);
    const k = (x.call||'') + '|' + (x.band||'');
    dupCounts.set(k, (dupCounts.get(k) || 0) + 1);
  });

  // `filtered` reste le résultat COMPLET du tri/filtre/recherche — seule la
  // tranche [0, logRenderLimit) part réellement dans le DOM (`visible`).
  const reversed = filtered.slice().reverse();
  const visible = reversed.slice(0, logRenderLimit);
  renderLogMoreBar(reversed.length - visible.length);

  tbody.innerHTML = visible.map((q,i)=>{
    const opColor = opColorAttr(q.operator);
    // LOGBOOK SIMPLE : retravailler un correspondant déjà eu (même indicatif +
    // même bande) est normal dans un log personnel — il n'y a pas de points à
    // perdre comme en concours. Barrer/griser la ligne dans ce cas n'indique
    // aucune erreur, ça rend juste illisible une vraie part de l'historique.
    const isDupQ = usageMode !== 'simple' && (dupCounts.get((q.call||'') + '|' + (q.band||'')) || 0) > 1;
    const incomplete = !isValidQSO(q);
    const distColor = q.dist>1000?'#FF5030':q.dist>500?'#FFD60A':q.dist>200?'#A0C0FF':'#506090';
    const _brg = (q.locator&&q.locator.length>=6) ? bearing(q.locator) : null;
    const cap = _brg !== null ? cardinalDir(_brg) : '—';
    const rowClass = [isDupQ?'dup-entry':'', q._new?'new-entry':'', incomplete?'incomplete-entry':''].filter(Boolean).join(' ');
    return `<tr class="${rowClass}" id="qso_${q.id}" ondblclick="editQSO(${q.id})" title="Double-clic pour corriger ce QSO">
      <td class="td-num">${incomplete?'<span class=\"incomplete-flag\" title=\"QSO incomplet — champ(s) manquant(s), à corriger\">⚠️</span>':''}${posOf.get(q)||0}</td>
      <td class="td-time">${escHtml(q.time)||'—'}</td>
      <td class="td-call">${escHtml(q.call)||'—'}${q.qsl_scan?` <span title="Scan QSL attaché">📎</span>`:''}</td>
      <td class="td-band"${q.freq?` title="${escHtml(q.freq)} MHz"`:''}>${BAND_LABELS[q.band]||escHtml(q.band)||'—'}${q.freq?`<span style="display:block;font-size:10px;color:var(--muted);font-weight:400">${escHtml(q.freq)}</span>`:''}</td>
      <td class="td-mode">${escHtml(q.mode)||'—'}</td>
      <td class="td-sent">${escHtml(q.rst_sent)||'—'}/${escHtml(q.num_sent)||'—'}</td>
      <td class="td-rcvd">${escHtml(q.rst_rcvd)||'—'}/${escHtml(q.num_rcvd)||'—'}</td>
      <td class="td-loc">${escHtml(q.locator)||'—'}</td>
      <td style="color:${distColor};font-weight:700;font-size:15px">${q.dist?q.dist+' km':'—'}${cap!=='—'?' '+cap:''}</td>
      <td class="td-pts">${escHtml(q.points)||'—'}</td>
      <td><span class="td-op ${opColor.cls}" style="${opColor.style}">${escHtml(_resolveOperatorCallsign(q.operator))||'—'}</span></td>
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
    <span class="lqi-call">${escHtml(q.call)}</span>
    <span class="lqi-loc">${escHtml(q.locator)||'—'}</span>
    <span class="lqi-pts">${escHtml(q.points)||0} pts</span>
    <span class="lqi-op">${escHtml(_resolveOperatorCallsign(q.operator))}</span>
  `;
  list.insertBefore(div, list.firstChild);
  if(list.children.length > 5) list.removeChild(list.lastChild);
}

// Replié par défaut (le tableau du log liste déjà tout) — même schéma que
// toggleSoapbox() : classe .collapsed sur le titre + .hidden sur le contenu.
function toggleLastQso(){
  const title = document.getElementById('lastQsoToggle');
  const list  = document.getElementById('lastQsoList');
  if(!title || !list) return;
  const collapsed = title.classList.toggle('collapsed');
  list.classList.toggle('hidden', collapsed);
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
  // Peupler le select bande avec les bandes du concours — PLUS celle du QSO
  // si elle n'y est pas (QSO logué sous un autre concours actif, ou hors
  // concours). Piège corrigé ici : un <select> a TOUJOURS une valeur dès
  // qu'il a des <option> (le navigateur sélectionne la première par défaut
  // si aucune n'a "selected") — `if(!editBandSel.value)` n'est donc jamais
  // vrai et ce filet ne se déclenchait jamais, laissant la bande/le mode
  // réels du QSO silencieusement remplacés par le premier choix de la
  // liste (ex. un QSO FT8 affiché "SSB" en édition dès que le concours
  // actif ne compte pas FT8 parmi ses modes). Corrigé en garantissant que
  // l'option existe TOUJOURS, plutôt qu'en réparant après coup une valeur
  // que le select a déjà mal choisie.
  const editBandSel = document.getElementById('editBand');
  const contestBands = CONTEST_BANDS[currentContest] || ALL_BANDS;
  const editBandOptions = (q.band && !contestBands.includes(q.band)) ? [...contestBands, q.band] : contestBands;
  editBandSel.innerHTML = editBandOptions.map(b =>
    `<option value="${b}"${b===q.band?' selected':''}>${BAND_LABELS[b]||b+' MHz'}</option>`
  ).join('');
  // Peupler le select mode avec les modes du concours — même correctif.
  const editModeSel = document.getElementById('editMode');
  const contestModes = CONTEST_MODES[currentContest] || ['SSB','CW','FM','FT8','FT4','RTTY'];
  const editModeOptions = (q.mode && !contestModes.includes(q.mode)) ? [...contestModes, q.mode] : contestModes;
  editModeSel.innerHTML = editModeOptions.map(m =>
    `<option value="${m}"${m===q.mode?' selected':''}>${m}</option>`
  ).join('');
  document.getElementById('editLocator').value = q.locator||'';
  updateEditDistInfo(q.locator);
  document.getElementById('editLocator').addEventListener('input', function(){
    updateEditDistInfo(this.value.toUpperCase());
    this.value = this.value.toUpperCase();
  });
  // EV-7 phase 2 : premier pilote du bus d'événements (voir logx_scan_qsl.js
  // pour le pourquoi). Le cœur ne connaît plus _renderEditQslScan() ; il
  // notifie juste qu'un QSO vient de s'ouvrir en édition.
  document.dispatchEvent(new CustomEvent('logx:qso-editing-opened', {detail: {qso: q}}));
  const scanStatus = document.getElementById('editQslScanStatus');
  if(scanStatus) scanStatus.textContent = '';
  // Champs ADIF personnalisés : {NOM: valeur} -> tableau de paires éditables
  // (un objet ne préserve pas un ordre de saisie fiable une fois qu'on retire
  // puis rajoute des clés, un tableau si).
  editExtraFields = Object.entries(q.extra_fields || {}).map(([name, value]) => ({name, value}));
  renderEditExtraFields();
  document.getElementById('editOverlay').classList.add('show');
  document.getElementById('editCall').focus();
}

// ─── CHAMPS ADIF PERSONNALISÉS ────────────────────────────────────────────
// N'importe quel tag ADIF que LogX ne modélise pas nativement (ex. MY_RIG,
// COMMENT, un champ propriétaire d'un autre logiciel) — stocké sous
// q.extra_fields, qui part dans la colonne `extra` générique de logx_storage
// (_row_from_qso sérialise déjà TOUTE clé hors de _CORE, aucun changement
// serveur nécessaire) et ressort tel quel à l'export ADIF (buildAdifText).
let editExtraFields = [];

function renderEditExtraFields(){
  const wrap = document.getElementById('editExtraFields');
  if(!wrap) return;
  const esc = s => String(s==null?'':s).replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  wrap.innerHTML = editExtraFields.map((f, i) => `<div class="exf-row">
    <input type="text" placeholder="NOM_CHAMP" value="${esc(f.name)}" oninput="updateEditExtraField(${i},'name',this.value)">
    <input type="text" placeholder="valeur" value="${esc(f.value)}" oninput="updateEditExtraField(${i},'value',this.value)">
    <span class="exf-del" onclick="removeEditExtraField(${i})" title="Retirer">✕</span>
  </div>`).join('');
}

function addEditExtraField(){
  editExtraFields.push({name:'', value:''});
  renderEditExtraFields();
}

function removeEditExtraField(i){
  editExtraFields.splice(i, 1);
  renderEditExtraFields();
}

function updateEditExtraField(i, key, value){
  editExtraFields[i][key] = value;
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

  // Champs ADIF personnalisés : noms vides ignorés, normalisés en MAJUSCULES
  // (convention ADIF) ; underscore/tiret/point tolérés (variantes courantes,
  // ex. "MY.RIG" recopié d'un autre logiciel), le reste retiré pour rester un
  // nom de tag ADIF valide. Objet supprimé plutôt que laissé vide : un QSO
  // sans champ personnalisé ne doit pas trimballer `extra_fields:{}` pour
  // toujours dans le log partagé.
  const extraObj = {};
  editExtraFields.forEach(f => {
    const name = String(f.name||'').trim().toUpperCase().replace(/[^A-Z0-9_.-]/g, '');
    if(name) extraObj[name] = f.value||'';
  });
  if(Object.keys(extraObj).length) q.extra_fields = extraObj;
  else delete q.extra_fields;

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

// Sans confirmation ni re-rendu : factorisée pour les suppressions en lot
// (recherche de doublons) qui ne veulent qu'UNE confirmation pour tout le
// lot, pas une par QSO, et qui rafraîchissent l'affichage une seule fois
// après la dernière suppression plutôt qu'à chaque itération.
async function deleteQSOSilent(id){
  qsoLog = qsoLog.filter(q=>q.id!==id);
  try{
    await fetch(`/log/delete/${id}`, {method:'DELETE'});
  }catch(e){}
  bcBroadcast('delete', {id});
}

async function deleteQSO(id){
  if(!confirm(trT('Supprimer ce QSO ?'))) return;
  await deleteQSOSilent(id);
  renderLog();
  updateStats();
}

async function undoLastQSO(){
  if(!qsoLog.length){ notify('Aucun QSO à annuler !'); return; }
  const last = qsoLog[qsoLog.length-1];
  if(!confirm(trF('Annuler le dernier QSO ?\n{call} — {band} MHz — {time}', {call: last.call, band: last.band, time: last.time}))) return;
  qsoLog = qsoLog.slice(0,-1);
  try{
    await fetch(`/log/delete/${last.id}`, {method:'DELETE'});
  }catch(e){}
  renderLog();
  updateStats();
}

// ─── STATS ───────────────────────────────────────────────────────────────────
// Concours THF : les compteurs affichent « QSO 144 / 432 » et les locators
// uniques, au lieu du total par bande et des sections.
//
// MÊME DÉFAUT QUE LE ROUTAGE D'EXPORT, mesuré sur la base livrée : la liste
// codée en dur comptait NEUF identifiants dont CINQ n'existaient pas
// (DARC_VHF, REF_CCD, EU_VHF, OARC_VHF, REF_VHF_UHF_FR), et elle en oubliait
// sept bien réels — dont REF_CDF_THF (le Championnat de France THF),
// REF_NAT_THF, IARU_MARCONI et les deux UFT Challenge. Un opérateur du CDF THF
// voyait donc des statistiques HF pendant tout le concours.
//
// On déduit désormais du LOG lui-même : si des QSO sont sur des bandes THF,
// c'est un concours THF. La donnée est sous la main, elle ne périme pas, et
// elle ne dépend d'aucun identifiant à tenir à jour.
const BANDES_THF = ['50','144','432','1296','2320','3400','5760','10368','24048','47088'];

function estConcoursThf(){
  return qsoLog.some(q => BANDES_THF.includes(String(q.band)));
}

// Compte des doublons (même call + même bande) en O(n) — remplace un
// filter()+findIndex() O(n²) qui était recalculé à chaque poll/ajout.
function countDupes(log){
  const seen = new Set();
  let n = 0;
  for(const q of (log||[])){
    const k = (q.call||'') + '|' + (q.band||'');
    if(seen.has(k)) n++; else seen.add(k);
  }
  return n;
}

function updateStats(){
  const isVHF = estConcoursThf();

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

  const dups = countDupes(qsoLog);

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
    // contestEndUTC peut être null (concours sans dates configurées, cf.
    // getContestEndUTC()) : pas de projection possible dans ce cas, plutôt
    // qu'un "~NaN" (contestEndUTC - nowMs avec contestEndUTC=null).
    const remaining = contestEndUTC ? Math.max(0, (contestEndUTC - nowMs) / 3600000) : null;
    const proj = remaining !== null ? Math.round(qsoLog.length + win60 * remaining) : null;
    const rateEl = document.getElementById('sbRate');
    rateEl.style.color = win60 >= 30 ? 'var(--green)' : win60 >= 15 ? 'var(--yellow)' : 'var(--purple)';
    rateStr = `${win60}/h · ~${proj !== null ? proj : '—'}`;
  }

  // Recalculé à chaque rafraîchissement de la bannière plutôt qu'au seul
  // changement de concours : ça garde l'affichage juste quel que soit le
  // chemin par lequel la config a changé (CONFIG, chargement de profil,
  // synchro multi-poste), sans devoir traquer chaque point d'appel.
  applyContestActifToLogbook();
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
  if(bandeauxRythmeMasques()){ bar.style.display = 'none'; return; }

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
    const opColor = opColorAttr(op);
    const isLeader = d.pts === topPts && topPts > 0;
    return `<div class="ops-item${isLeader?' leader':''}">`
      + `<div class="ops-op ${opColor.cls}" style="border-radius:4px;display:inline-block;padding:1px 8px;${opColor.style}">${escHtml(_resolveOperatorCallsign(op))}${isLeader?' 🏆':''}</div>`
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
  if(bandeauxRythmeMasques()){ bar.style.display = 'none'; return; }
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
      `<div class="brd-vals" style="color:var(--muted);font-size:12px">${escHtml(d.bestCall)} ${escHtml(d.bestBear)}</div>`;
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
  if(bandeauxRythmeMasques()){ bar.style.display = 'none'; return; }
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
  // Math.max(0.1, …) : au-delà d'~1000 tranches heure/date (log couvrant
  // beaucoup de jours), la formule devient négative ou nulle — SVG rejette
  // width<0 (erreur console en boucle, une par barre, valeur identique).
  const bw = Math.max(0.1, Math.floor((VW - gap * (n - 1)) / n));

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
  localStorage.setItem('logx_soapbox', JSON.stringify(data));
}
function loadSoapbox(){
  try{
    const data = JSON.parse(localStorage.getItem('logx_soapbox')||'{}');
    SOAPBOX_BANDS.forEach(b => {
      const el = document.getElementById(`soap_${b}`);
      if(el && data[b]) el.value = data[b];
    });
  }catch(e){}
}
function getSoapbox(band){
  try{
    const data = JSON.parse(localStorage.getItem('logx_soapbox')||'{}');
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
function getMacros(){ try{ const s=localStorage.getItem('logx_macros'); return s?JSON.parse(s):DEFAULT_MACROS; }catch(e){ return DEFAULT_MACROS; } }
function saveMacros(m){ localStorage.setItem('logx_macros', JSON.stringify(m)); }
// {NR} doit valoir EXACTEMENT le numéro qui sera loggué : la macro F2
// (« 59 {NR} {LOC} ») part directement au keyer de la radio via copyMacro() →
// POST /rig/cw, y compris automatiquement en mode ESM (esmSend('exchange')).
// La seule source de vérité est donc le champ N° ENVOYÉ (#inputNumSent), tenu
// à jour par updateSerialDisplay() à partir de serialByBand[bande] — le n° de
// série est alloué PAR BANDE et par portée concours (nextSerial() →
// /log/next_serial → logx_storage.allocate_next_serial), et c'est cette
// valeur-là qui finit dans num_sent puis dans l'EDI/Cabrillo.
//
// L'ancien calcul, String(qsoLog.length+1), comptait TOUS les QSO de l'édition
// toutes bandes confondues (et, en multi-poste, ceux loggués par les autres
// opérateurs sur les autres bandes) : les deux formules ne coïncidaient que sur
// un concours mono-bande sans trou. Dès le premier QSO d'une deuxième bande —
// cas normal en IARU UHF/SHF, Marconi, Rallye des Points Hauts, CQ WPX… — la
// radio envoyait sur l'air un numéro absent du log, et l'écart croissait à
// chaque QSO ; le correspondant note un numéro introuvable au cross-check, les
// deux QSO tombent, et l'opérateur n'a aucun recours (champ readOnly par
// conception, cf. updateSerialDisplay). Le chemin VOCAL (sendVoiceDynMacro)
// lisait déjà ce même champ : seul le chemin CW était resté sur le compteur global.
function expandMacro(text){
  const cfg = JSON.parse(localStorage.getItem('logx_config')||'{}');
  const call = cfg.callsign || myCall || '—';
  const loc  = cfg.locator  || myLocator || '—';
  const nrEl = document.getElementById('inputNumSent');
  const nrField = nrEl ? String(nrEl.value || '').trim() : '';
  // Repli si le champ n'est pas encore renseigné (panneau macros rendu avant
  // le premier updateSerialDisplay()) : même formule que l'affichage, jamais
  // un compteur global. Pour un échange non sériel (zone, dept, classe…) il
  // n'y a rien à prédire : on laisse la valeur du champ telle quelle.
  const nr = nrField || (currentExchange.auto_serial
    ? String((serialByBand[currentBand] || 0) + 1).padStart(3,'0')
    : '');
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
// ─── i18n des messages dynamiques (notify() et fonctions similaires) ────────
// window.rcT()/rcTf() (logx_i18n.js) ne traduisent qu'un texte source français
// CONNU AU MOT PRÈS : un message déjà interpolé (`${...}`/concaténation, ex.
// "Erreur serveur : " + err) ne correspond plus à AUCUNE clé du dictionnaire
// et ne peut donc jamais être traduit, même si son modèle y figure. Tout appel
// qui injecte une valeur dynamique doit donc passer par trF('modèle {clé}',
// {clé: valeur}) plutôt que par interpolation directe. trT()/trF() tolèrent
// aussi l'absence de logx_i18n.js (page qui ne le charge pas, tests JS) en
// repliant sur le français tel quel (comportement identique à rcT/rcTf en fr).
function trT(fr){ return window.rcT ? window.rcT(fr) : fr; }
function trF(fr, params){
  if (window.rcTf) return window.rcTf(fr, params);
  let s = fr;
  if (params) for (const k in params) s = s.split('{' + k + '}').join(params[k]);
  return s;
}

// Notification non bloquante — remplace notify() pour ne jamais figer la saisie
// en plein concours. Couleur selon le contenu, durée selon la longueur.
//
// i18n : msg est le texte source FRANÇAIS (voir trT()/trF() ci-dessus pour le
// construire côté appelant s'il contient une valeur dynamique). La
// classification erreur/avertissement ci-dessous se fait sur ce français
// source (mots-clés), donc TOUJOURS avant la traduction pour l'affichage.
function notify(msg, ms){
  const t = document.getElementById('macroToast');
  if(!t){ alert(msg); return; }   // repli improbable
  msg = String(msg);
  const isErr  = /❌|[Ee]rreur|[Ii]nvalide|manquant|[Ii]mpossible|injoignable/.test(msg);
  const isWarn = /⚠|[Aa]nnulé/.test(msg);
  t.textContent = trT(msg);
  t.className = 'macro-toast';
  if(isErr) t.classList.add('toast-err');
  else if(isWarn) t.classList.add('toast-warn');
  t.classList.add('show');
  clearTimeout(notify._tm);
  notify._tm = setTimeout(()=>t.classList.remove('show'), ms || Math.min(10000, 2500 + msg.length*35));
}

function copyMacro(idx){
  const m = getMacros()[idx]; if(!m) return;
  const txt = expandMacro(m.text);
  // Radio en CW + pilotage actif → la macro part directement par le keyer
  // de la radio ; sinon (SSB/RTTY, ou pas de CAT) on copie dans le presse-papier.
  // EV-7 : rigState vit maintenant dans logx_hardware_cat.js -- garde requise
  // (même motif que les 10 autres lectures de rigState hors de ce fichier).
  if(typeof rigState !== 'undefined' && rigState.enabled && /CW/i.test(rigState.mode || currentMode)){
    fetch('/rig/cw', {method:'POST', headers:{'Content-Type':'application/json'},
                      body: JSON.stringify({text: txt})})
      .then(r=>r.json()).then(d=>{
        const toast = document.getElementById('macroToast');
        if(toast){ toast.textContent = d.ok ? trF('📻 CW → {txt}', {txt})
                                             : trF('❌ {err}', {err: d.error});
          toast.className = 'macro-toast' + (d.ok ? '' : ' toast-err');
          toast.classList.add('show'); setTimeout(()=>toast.classList.remove('show'), 2200); }
      }).catch(()=>{});
    return;
  }
  navigator.clipboard.writeText(txt).catch(()=>{});
  const toast = document.getElementById('macroToast');
  if(toast){ toast.textContent = trF('📋 {txt}', {txt}); toast.classList.add('show'); setTimeout(()=>toast.classList.remove('show'), 2000); }
}

// adaptivePoll() : polling adaptatif générique (cadence rapide si le
// callback signale une activité, lente sinon). Reste ICI (pas dans
// logx_hardware_cat.js, EV-7 phase 2) car pollChat() (cœur, chat
// multi-poste) le réutilise aussi -- ce n'est pas un utilitaire propre au
// matériel radio. `fn` doit retourner la promesse du fetch.
function adaptivePoll(fn, fastMs, slowMs, isActive){
  (function tick(){
    let p; try{ p = fn(); }catch(e){ p = null; }
    Promise.resolve(p).catch(()=>{}).then(()=>{
      setTimeout(tick, isActive() ? fastMs : slowMs);
    });
  })();
}

function editMacro(idx){
  const macros = getMacros();
  const m = macros[idx];
  const newLabel = prompt(trF('Label pour {k} :', {k: m.key}), m.label);
  if(newLabel === null) return;
  const newText = prompt(trT('Message ({CALL} {LOC} {NR}) :'), m.text);
  if(newText === null) return;
  macros[idx] = {...m, label:newLabel.trim()||m.label, text:newText.trim()||m.text};
  saveMacros(macros); renderMacroPanel();
}

// ─── EXPORTS ─────────────────────────────────────────────────────────────────

// N° de série d'un enregistrement EDI, tel qu'il a RÉELLEMENT circulé sur l'air.
//
// Le n° envoyé est alloué par le serveur (logx_storage.allocate_next_serial via
// /log/next_serial), affiché à l'opérateur puis transmis au correspondant : il
// ne doit JAMAIS être redérivé de la position du QSO dans le fichier exporté.
// La séquence des num_sent comporte des trous parfaitement NOMINAUX — QSO
// supprimé en cours d'épreuve (deleteQSO/undoLastQSO), doublon refusé après
// allocation, erreur serveur après allocation, n° corrigé à la main, sans
// compter les QSO incomplets écartés par isValidQSO() — et allocate_next_serial
// ne réutilise jamais un numéro libéré (« un trou dans la séquence est
// toléré »). Renuméroter 1..N décale alors TOUS les QSO suivants de la bande :
// en cross-check IARU/REF, un n° envoyé qui ne correspond pas au n° reçu par le
// correspondant fait tomber le QSO (NIL) des DEUX côtés.
//
// Un champ vide reste vide : dans un log de soumission on n'invente pas un
// numéro qui n'a jamais été échangé (l'ancien repli `||'001'` sur le n° reçu
// fabriquait de la donnée). Un échange fixe non numérique (type Field Day) est
// recopié tel quel.
function ediSerial(v){
  const s = String(v == null ? '' : v).trim();
  if(!s) return '';
  return /^\d+$/.test(s) ? s.padStart(3,'0') : s;
}

function exportEDI(){
  // Validation avant export
  const warnings = [];
  const invalid = qsoLog.filter(q=>!isValidQSO(q));
  if(invalid.length) warnings.push(trF('⚠️ {n} QSO incomplet(s) ignoré(s) ({calls})', {n: invalid.length, calls: invalid.map(q=>q.call||'?').join(', ')}));
  const missingLoc = qsoLog.filter(q=>isValidQSO(q) && (!q.locator||q.locator.length<6));
  if(missingLoc.length) warnings.push(trF('⚠️ {n} QSO sans locator (points = 0)', {n: missingLoc.length}));
  // isValidQSO() n'exige pas le n° envoyé (import ADIF sans STX, champ vidé à la
  // main) : il partira VIDE plutôt qu'inventé — autant le signaler avant.
  const missingSerial = qsoLog.filter(q=>isValidQSO(q) && !ediSerial(q.num_sent));
  if(missingSerial.length) warnings.push(trF('⚠️ {n} QSO sans n° de série envoyé ({calls})', {n: missingSerial.length, calls: missingSerial.map(q=>q.call||'?').join(', ')}));
  const dups = countDupes(qsoLog);
  if(dups) warnings.push(trF('⚠️ {n} doublon(s) dans le log', {n: dups}));
  if(warnings.length){
    if(!confirm(trF('VALIDATION LOG\n\n{warnings}\n\nGénérer quand même le fichier EDI ?', {warnings: warnings.join('\n')}))) return;
  }

  // Lire config depuis localStorage
  let ediCfg = {};
  try{ ediCfg = JSON.parse(localStorage.getItem('logx_config')||'{}'); }catch(e){}
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

  // Le format vient du RÈGLEMENT du concours (voir formatDepot) et non plus
  // d'une liste d'identifiants tenue à la main, qui en oubliait dix-sept.
  if(formatDepot() !== 'EDI'){
    exportCabrillo(ediCfg, myCall);
    return;
  }

  // Le 6 m (50 MHz) EST du THF et se dépose en EDI : sans lui, IARU_50MHZ (et
  // tout log 6 m) donnait « Aucun QSO VHF/UHF à exporter » — aucun fichier au
  // moment du dépôt (revue 01/08/2026).
  const VHF_UHF_SHF_BANDS = ['50','144','432','1296','2320','3400','5760','10368','24048','47088'];
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
      `Logiciel: LogX AI v3.0 — ${ediCall} ${ediLocator}`,
      ...(ediAltitude ? [`Altitude: ${ediAltitude}m`] : []),
      ...(ediDept ? [`Département: ${ediDept}`] : []),
      ...(ediOpList.length ? [`Opérateurs : ${ediOpList.join(', ')}`] : []),
      ...(getSoapbox(band) ? [getSoapbox(band)] : []),
      `[QSOrecords;${bandQSOs.length}]`,
    ];

    let edi = lines.join('\r\n') + '\r\n';
    bandQSOs.forEach(q=>{
      const serial  = ediSerial(q.num_sent);   // celui transmis sur l'air, JAMAIS l'index de boucle
      const numRcvd = ediSerial(q.num_rcvd);   // vide reste vide : rien d'inventé
      const timeStr = q.time.replace(':',''); // HHMM
      const modeCode = q.mode==='CW'?2:q.mode==='FM'?6:1; // 1=SSB
      // Gabarit REG1TEST, 15 champs : date;heure;indicatif;mode;RST env;n° env;
      // RST reçu;n° reçu;échange reçu;WWL reçu;points;new exchange;new WWL;
      // new DXCC;doublon. Le mode est déjà en champ 4 sous forme de code
      // numérique — le champ 13 est l'indicateur « new WWL », pas une seconde
      // copie du mode en texte.
      edi += `${q.date};${timeStr};${q.call};${modeCode};${q.rst_sent};${serial};${q.rst_rcvd};${numRcvd};;${q.locator||''};${q.points||0};;;;\r\n`;
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
    remindSubmitLog(ediCfg, {
      fallbackUrl: 'http://concours.r-e-f.org/tools/upload/thf.php',
      extraNote: trF('⚠️ 1 fichier EDI PAR BANDE (144 MHz et 432 MHz séparés)'),
    });
  }, bands.length * 500 + 300);
}

// Le fichier Cabrillo est fabriqué PAR LE SERVEUR (logx_export.build_cabrillo).
// Il y avait ici une seconde implémentation, complète et divergente : elle
// détenait seule les noms officiels de concours, mais écrivait l'échange SANS
// le compte-rendu (un CQ WW partait avec « 001 » au lieu de « 59 14 »),
// n'émettait les lignes CATEGORY-* que pour le Field Day, et exportait qsoLog
// sans le filtrage de portée concours+année qu'applique /log/export/cabrillo.
// Deux générateurs pour un même fichier, c'est une divergence garantie : le
// second est supprimé, les noms officiels sont passés dans les définitions de
// concours (cabrillo_name), où le serveur les lit.
function exportCabrillo(cfg, call){
  const nom = (CONTEST_SCHEDULE[currentContest] || {}).name || currentContest;
  const score = qsoLog.reduce((s, q) => s + (q.points || 0), 0);
  // Téléchargement par navigation : le serveur pose déjà Content-Disposition
  // avec le bon nom de fichier, et le cookie de session part avec la requête.
  window.location.href = '/log/export/cabrillo';
  setTimeout(() => {
    notify(trF('📤 FICHIER CABRILLO GÉNÉRÉ\n\nConcours : {contest}\nQSOs : {n} — Score déclaré : {score} pts',
      {contest: nom, n: qsoLog.length, score: score}));
    remindSubmitLog(cfg);
  }, 400);
}

// Rappel + ouverture directe de la page de soumission — auto-remplie en CONFIG
// depuis le règlement du concours sélectionné (voir selectContest() côté
// logx_configuration.html), corrigeable manuellement si besoin. Un clic en
// moins qu'un simple rappel texte : le fichier vient d'être téléchargé, la
// page de dépôt s'ouvre directement dans un nouvel onglet pour le déposer.
function remindSubmitLog(cfg, opts){
  opts = opts || {};
  const submitUrl = (cfg && cfg.submit_url || '').trim() || opts.fallbackUrl || '';
  const submitDeadline = (cfg && cfg.submit_deadline || '').trim();
  if (!submitUrl){
    notify(trF('📭 Aucune URL de soumission connue pour ce concours — pense à vérifier le règlement et à renseigner le champ en CONFIG (section SCOREBOARD & SOUMISSION).'));
    return;
  }
  const deadlineLine = submitDeadline ? trF('\nDélai : {d}', {d: submitDeadline}) : '';
  const extraLine = opts.extraNote ? ('\n\n' + opts.extraNote) : '';
  notify(trF('📤 SOUMISSION DU LOG\n\nOuverture de la page de dépôt…{deadline}{extra}',
    {deadline: deadlineLine, extra: extraLine}));
  // Popup bloquée par le navigateur : window.open() renvoie null, on retombe
  // sur le lien cliquable déjà donné dans la notification texte ci-dessus.
  const w = window.open(submitUrl, '_blank', 'noopener');
  if (!w){
    notify(trF('⚠️ Le navigateur a bloqué l\'ouverture automatique — clique le lien : {url}', {url: submitUrl}));
  }
}

// ─── EXPORT ADIF ─────────────────────────────────────────────────────────────
// <BAND> attend un LIBELLÉ de l'énumération Band d'ADIF ('20m', '2m', '70cm'),
// jamais une fréquence. La bande interne du log étant la fréquence en MHz
// ('14', '144', '3.5'), elle doit être TRADUITE : coller un 'M' à la valeur
// interne produisait <BAND>14M / <BAND>144M, refusé par TQSL/LoTW, eQSL et
// Club Log sur les 20 bandes gérées.
// Table jumelle de logx_export.ADIF_BAND (version Python, /log/export/adif).
// Ne PAS réutiliser BAND_LABELS : c'est une table d'AFFICHAGE, dont deux
// entrées (24048 → '6mm', 47088 → '4mm') portent le nom d'usage et non le
// libellé ADIF officiel ('1.25cm' et '6mm').
const ADIF_BAND = {
  '1.8':'160m','3.5':'80m','7':'40m','10.1':'30m','14':'20m','18':'17m',
  '21':'15m','24':'12m','28':'10m','50':'6m','70':'4m','144':'2m',
  '432':'70cm','1296':'23cm','2320':'13cm','3400':'9cm','5760':'6cm',
  '10368':'3cm','24048':'1.25cm','47088':'6mm',
};
// Libellés ADIF officiels (ADIF 3.1.7, cf. logx_adif_enums.ADIF_BANDS). Un QSO
// IMPORTÉ conserve tel quel le libellé ADIF quand sa bande sort de notre table
// interne (60m, 2190m, 1mm… — voir logx_qsl._band_from_record) : il est alors
// DÉJÀ valide et doit ressortir intact, surtout pas suffixé ('1mmM').
const ADIF_BAND_OFFICIELLES = new Set([
  '2190m','630m','560m','160m','80m','60m','40m','30m','20m','17m','15m',
  '12m','10m','8m','6m','5m','4m','2m','1.25m','70cm','33cm','23cm','13cm',
  '9cm','6cm','3cm','1.25cm','6mm','4mm','2.5mm','2mm','1mm','submm',
]);
// Bande interne → libellé ADIF, '' si intraduisible (le champ est alors OMIS :
// une valeur hors énumération fait rejeter tout l'enregistrement).
function adifBandLabel(band){
  const raw = String(band == null ? '' : band).trim();
  if(!raw) return '';
  if(ADIF_BAND[raw]) return ADIF_BAND[raw];
  const bas = raw.toLowerCase();
  return ADIF_BAND_OFFICIELLES.has(bas) ? bas : '';
}
// Un champ ADIF : <NOM:longueur>valeur. Valeur vide = champ absent.
function adifField(name, value){
  const v = String(value == null ? '' : value).trim();
  return v ? `<${name}:${v.length}>${v} ` : '';
}

// Construit le texte ADIF pour une liste de QSO donnée — factorisé pour être
// réutilisé par l'export complet (exportADIF) et l'export filtré
// (fltExportFiltered), sans dupliquer le corps du générateur.
const ADIF_STD_TAGS = new Set(['CALL','QSO_DATE','TIME_ON','BAND','FREQ','MODE','RST_SENT',
  'RST_RCVD','STX_STRING','SRX_STRING','GRIDSQUARE','MY_GRIDSQUARE','STATION_CALLSIGN',
  'OPERATOR','CONTEST_ID','ADIF_VER','PROGRAMID']);

function buildAdifText(qsos){
  let adif = 'LogX AI — Export ADIF\n';
  adif += adifField('ADIF_VER', '3.1.4') + adifField('PROGRAMID', 'LogX AI') + '\n<EOH>\n\n';
  qsos.forEach(q=>{
    const date = String(q.date || '').replace(/-/g, '').slice(0, 8);
    const time = String(q.time || '').replace(/:/g, '').slice(0, 4).padEnd(4, '0');
    adif += adifField('CALL', String(q.call).toUpperCase());
    adif += adifField('QSO_DATE', date);
    adif += adifField('TIME_ON', time);
    adif += adifField('BAND', adifBandLabel(q.band));
    // FREQ : seulement si elle a réellement été relevée (CAT/saisie) — c'est
    // aussi le seul moyen, pour un importateur, de retrouver la bande d'un
    // QSO dont le libellé serait intraduisible.
    adif += adifField('FREQ', q.freq);
    adif += adifField('MODE', q.mode);
    adif += adifField('RST_SENT', q.rst_sent);
    adif += adifField('RST_RCVD', q.rst_rcvd);
    adif += adifField('STX_STRING', q.num_sent);
    adif += adifField('SRX_STRING', q.num_rcvd);
    adif += adifField('GRIDSQUARE', q.locator);
    adif += adifField('MY_GRIDSQUARE', q.my_locator || myLocator);
    // Multi-op : sans STATION_CALLSIGN/OPERATOR le log n'est attribuable ni à
    // la station ni à l'opérateur qui a fait le QSO.
    adif += adifField('STATION_CALLSIGN', String(q.my_call || myCall || '').toUpperCase());
    adif += adifField('OPERATOR', _resolveOperatorCallsign(q.operator));
    adif += adifField('CONTEST_ID', q.contest);
    // Champs ADIF personnalisés (voir editQSO/extra_fields) — ADIF_STD_TAGS
    // évite qu'un nom entré par erreur (ex. "CALL") ne duplique/contredise un
    // tag déjà émis ci-dessus.
    if(q.extra_fields){
      Object.entries(q.extra_fields).forEach(([name, value]) => {
        if(!ADIF_STD_TAGS.has(name)) adif += adifField(name, value);
      });
    }
    adif += '<EOR>\n';
  });
  return adif;
}

function downloadAdifBlob(adif, suffix){
  const blob = new Blob([adif],{type:'text/plain'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${myCall.replace('/','_')}_${suffix}.adif`;
  a.click();
}

function exportADIF(){
  const validQSOs = qsoLog.filter(isValidQSO);
  const skipped = qsoLog.length - validQSOs.length;
  if(skipped && !confirm(trF('⚠️ {n} QSO incomplet(s) seront ignorés dans l\'export ADIF.\n\nContinuer ?', {n: skipped}))) return;
  downloadAdifBlob(buildAdifText(validQSOs), 'log');
}

function exportCSV(){
  let csv = 'N°,Date,Heure,Indicatif,Bande,Mode,RST_env,N°_env,RST_recu,N°_recu,Locator,Distance_km,Points,Operateur\n';
  qsoLog.forEach((q,i)=>{
    csv += `${i+1},${q.date},${q.time},${q.call},${q.band},${q.mode},${q.rst_sent},${q.num_sent},${q.rst_rcvd},${q.num_rcvd||''},${q.locator||''},${q.dist||0},${q.points||0},${_resolveOperatorCallsign(q.operator)}\n`;
  });
  const blob = new Blob([csv],{type:'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${myCall.replace('/','_')}_log.csv`;
  a.click();
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
    // Même réponse /log/status : on en profite pour rafraîchir le badge de
    // vérification de version multi-op (voir updateVersionStatus()) sans
    // ajouter un second cycle de polling dédié.
    updateVersionStatus(data);
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
      out.push({call:q.call, src:'log', locator:q.locator, dup: usageMode !== 'simple' && isDup(q.call,currentBand)});
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
                locator:d.locator, dept:d.dept, dup: usageMode !== 'simple' && isDup(call,currentBand)});
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
    // c/loc/dept viennent de callDB (indicatifs importés d'ADIF, historique) —
    // données potentiellement non maîtrisées, échappées avant insertion. Pour
    // l'argument JS de onmousedown, on restreint l'indicatif aux caractères valides.
    const jsC = String(c || '').replace(/[^A-Za-z0-9/]/g, '');
    const locStr = loc ? `<span style="color:var(--accent2);font-size:14px;font-weight:700">${escHtml(loc)}</span>` : '';
    const deptStr = dept ? `<span style="color:var(--yellow);font-size:14px;font-weight:700">dpt${escHtml(dept)}</span>` : '';
    const cStr  = cname ? `<span style="color:var(--muted);font-size:14px">${escHtml(cname)}</span>` : '';
    return `<div class="ac-item${dup?' dupe-item':''}" data-call="${escHtml(c)}" onmousedown="selectAC('${jsC}')">`
      + `<span style="font-size:16px">${flag}</span>`
      + `<b class="ac-call${dup?' dupe-call':''}" style="${dup?'color:var(--red)':'color:var(--green)'}">${escHtml(c)}</b>`
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

  // ── Vérification doublon (hors concours : recontacter la même station sur
  // la même bande au fil des années est normal, pas un doublon à signaler) ──
  const warn  = document.getElementById('dupWarn');
  const input = document.getElementById('inputCall');
  if(usageMode !== 'simple' && isDup(call, currentBand)){
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
      out.push({call:q.call, locator:q.locator, src:'log', dup: usageMode !== 'simple' && isDup(q.call,currentBand)});
      if(out.length >= 12) return out;
    }
  }

  // 2. Base callDB
  for(const call in callDB){
    const d = callDB[call];
    if(d.locator && d.locator.toUpperCase().startsWith(prefix) && !seen.has(call)){
      seen.add(call);
      out.push({call, locator:d.locator, dept:d.dept||'', src:'db', dup: usageMode !== 'simple' && isDup(call,currentBand)});
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
    const deptStr = item.dept ? `<span style="color:var(--yellow);font-size:14px;font-weight:700">dpt${escHtml(item.dept)}</span>` : '';
    const locStr  = `<span style="color:var(--accent2);font-size:14px;font-weight:800">${escHtml(item.locator)}</span>`;
    return `<div class="ac-item${dup?' dupe-item':''}" data-idx="${idx}" onmousedown="selectLocAC(${idx})">`
      + `<span style="font-size:16px">${flag}</span>`
      + `<b style="font-size:19px;font-weight:900;min-width:110px;letter-spacing:1px;${dup?'color:var(--red)':'color:var(--green)'}">${escHtml(item.call)}</b>`
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
  // La BANDE courante part avec la consigne : le serveur tourne alors le rotor
  // de l'antenne active sur cette bande — et lui seul — avec son décalage
  // mécanique. Sans elle, une station à trois pylônes voyait toujours tourner
  // le même (revue 01/08/2026).
  fetch('/rotor/point', {method:'POST', headers:{'Content-Type':'application/json'},
                         body: JSON.stringify({azimuth: _lastCompassDeg,
                           bande: (typeof currentBand !== 'undefined') ? currentBand : undefined})})
    .then(r=>r.json()).then(d=>{
      notify(d.ok ? trF('🧭 Antenne pointée sur {deg}°', {deg: _lastCompassDeg}) : trF('❌ {err}', {err: d.error}));
    }).catch(()=>notify('Rotor injoignable.'));
}
function hideCompassInline(){
  const el = document.getElementById('compassInline');
  if(el) el.classList.remove('show');
}

// ─── CHAT MULTI-OPÉRATEUR ─────────────────────────────────────────────────────
let chatLastId = 0;

function startChat(){
  // Poll adaptatif : rapide (3s) quand le panneau chat est ouvert, ralenti
  // (15s) sinon — le point rouge de notification (renderChatMsg) continue de
  // fonctionner panneau fermé, juste avec une latence un peu plus longue.
  // Avant ce correctif : setInterval(pollChat, 3000) tournait à vie dès le
  // chargement de la page, panneau ouvert ou non — la requête la plus
  // fréquente du fichier avec rig/amp, même sur un poste où personne ne
  // regarde jamais le chat.
  // Reste aussi en cadence rapide en multi-op MÊME panneau fermé : c'est
  // justement l'état dans lequel la vue Partner doit rester réactive (bandeau
  // visible sans ouvrir le chat pendant un pile-up) — sans _isMultiOp() ici,
  // la saisie de l'autre opérateur ne se rafraîchirait qu'à 15s.
  adaptivePoll(pollChat, 3000, 15000, ()=>{
    const panel = document.getElementById('chatPanel');
    return !!(panel && panel.classList.contains('open')) || _isMultiOp();
  });
}

async function pollChat(){
  try{
    const r = await fetch('/chat/list?since=' + chatLastId);
    if(!r.ok) return;
    const d = await r.json();
    (d.messages || []).forEach(renderChatMsg);
    if(typeof d.last_id === 'number') chatLastId = d.last_id;
    renderPartnerTyping(d.typing || []);
  }catch(e){ /* serveur injoignable : on réessaiera */ }
}

function renderChatMsg(m){
  // Le conteneur des messages s'appelle chatBody dans l'HTML (pas chatBox —
  // ancien nom, l'id n'a jamais existé : le chat n'affichait rien du tout).
  const box = document.getElementById('chatBody');
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
  // Badge « non lus » sur l'en-tête si le panneau est fermé et que ce n'est
  // pas mon message (id chatUnread dans l'HTML — compteur, pas simple point).
  const panel = document.getElementById('chatPanel');
  const unread = document.getElementById('chatUnread');
  if(unread && panel && !panel.classList.contains('open') && !mine){
    unread.textContent = String((parseInt(unread.textContent, 10) || 0) + 1);
    unread.style.display = 'inline-block';
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

// ─── VUE PARTNER (saisie en direct, lecture seule) ───────────────────────────
// Un second opérateur (radioclub/expédition) voit ce que le runner tape dans
// le champ INDICATIF, en quasi temps réel. Réutilise le poll /chat/list déjà
// en place (adaptivePoll 3-15s, cf. startChat) plutôt qu'un nouveau
// mécanisme — pas de WebSocket, juste un état éphémère côté serveur (jamais
// persisté, contrairement aux messages de chat). Lecture seule : cette 1re
// version ne permet pas de « pousser » un indicatif corrigé vers le runner.
// Diffusion (côté runner) uniquement en multi-op — sur un poste solo, cette
// info n'intéresse personne et ne vaut pas le trafic réseau supplémentaire.
function _isMultiOp(){
  // Même définition que isMultiOp() dans logx_statusbar.js (exposée en
  // window.rcIsMultiOp) — on la réutilise pour ne pas faire vivre deux
  // implémentations séparées. Le repli ci-dessous (dupliqué intentionnellement)
  // ne sert que si ce fichier tournait sans logx_statusbar.js chargé — ce qui
  // n'arrive pas sur logx_logbook.html (statusbar inclus avant), mais évite
  // une dépendance dure entre les deux fichiers.
  if(typeof window.rcIsMultiOp === 'function') return window.rcIsMultiOp();
  try{
    const cfg = JSON.parse(localStorage.getItem('logx_config') || '{}');
    return cfg.usage_mode !== 'simple' && (cfg.operators || []).length > 1;
  }catch(e){ return false; }
}

let _typingTimer = null;
let _typingLastSent = 0;
const TYPING_MIN_INTERVAL_MS = 300;   // throttle (pas un debounce) : la frappe reste visible pendant la saisie, pas seulement à la pause

function _sendTyping(text){
  const opLbl = (document.getElementById('opCurrentLabel') || {}).textContent || myOp;
  fetch('/chat/typing', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ op: myOp, label: opLbl, band: currentBand, mode: currentMode, text })
  }).catch(()=>{});
}

function broadcastTyping(text){
  if(!_isMultiOp()) return;
  const now = Date.now();
  const elapsed = now - _typingLastSent;
  clearTimeout(_typingTimer);
  if(elapsed >= TYPING_MIN_INTERVAL_MS){
    _typingLastSent = now;
    _sendTyping(text);
  } else {
    _typingTimer = setTimeout(() => { _typingLastSent = Date.now(); _sendTyping(text); },
                              TYPING_MIN_INTERVAL_MS - elapsed);
  }
}

// Affiche la saisie des AUTRES opérateurs (jamais la sienne), visible même
// panneau CHAT fermé (bandeau discret au-dessus du corps du chat) — repéré
// d'un coup d'œil sans avoir à ouvrir le panneau pendant un pile-up.
function renderPartnerTyping(list){
  const box = document.getElementById('partnerTyping');
  if(!box) return;
  const others = (list || []).filter(t => t && t.op !== myOp && t.text);
  if(!others.length){
    box.style.display = 'none';
    box.innerHTML = '';
  } else {
    box.style.display = 'flex';
    box.innerHTML = others.map(t =>
      `<div class="partner-row"><span class="partner-op">${escHtml(t.label || t.op)}</span>`
      + `<span class="partner-ctx">${escHtml(t.band||'')}${t.band?' MHz':''}${t.mode?' · '+escHtml(t.mode):''}</span>`
      + `<span class="partner-text">${escHtml(t.text)}</span></div>`
    ).join('');
  }
  // Le bandeau change de hauteur avec son contenu — et il est VISIBLE (donc
  // occupe de la place dans .chat-panel, position:fixed) que le panneau CHAT
  // soit ouvert ou fermé : c'est même l'intérêt de la vue Partner (repérer la
  // saisie du runner sans ouvrir le chat). Recalculer la marge réservée à
  // CHAQUE changement de contenu, sans condition sur .open — sinon panneau
  // fermé, le bandeau grandit (jusqu'à ~110px) sans jamais agrandir l'espace
  // réservé sous le tableau, et chevauche les dernières lignes du log.
  const panel = document.getElementById('chatPanel');
  _reserveBottomSpace(panel, document.querySelector('.log-table-wrap'));
}

// Les panneaux CHAT et DÉCODEUR CW sont en position:fixed, ancrés bas-droite/
// bas-gauche — ils flottent donc AU-DESSUS du contenu défilant en dessous
// (dernier QSO saisis / tableau du log) au lieu de le pousser. Sans cette
// marge réservée, le panneau recouvre littéralement les dernières lignes,
// qui semblent alors "manquantes" — d'autant plus visible quand la fenêtre
// est basse (portable, /P) puisque .saisie-panel/.log-table-wrap défilent
// alors bien avant d'atteindre leur propre fin.
function _reserveBottomSpace(panel, scrollEl){
  if(!panel || !scrollEl) return;
  // RÉDUIT max-height (ne rajoute PAS de padding-bottom) : un padding-bottom
  // plus grand que la boîte la force à GRANDIR pour pouvoir le contenir —
  // par construction CSS, une boîte ne peut jamais être plus petite que ses
  // propres marges internes (padding+bordure), donc le padding « gagne »
  // sur toute hauteur/max-height qu'on lui impose par ailleurs (vérifié
  // empiriquement : max-height ET height explicites sont tous deux ignorés
  // dès que le padding-bottom les dépasse). Sur un conteneur flex:1 court
  // (ex: .saisie-secondary, coincé entre la saisie et le bas de colonne),
  // ça le fait déborder de SON PROPRE parent — et si ce parent scrolle
  // aussi (.saisie-panel), révéler le bas du conteneur reviendrait à faire
  // défiler la zone de SAISIE hors champ, interdit ici (cf. "ZONE
  // SECONDAIRE ... ne rogne jamais la saisie"). Réduire max-height n'a pas
  // ce problème : le contenu qui ne rentre plus scrolle via l'overflow-y:
  // auto déjà en place, sans jamais faire grandir le conteneur au-delà de
  // ce qu'il occupait chez son parent. Plancher à 0 (pas plus) : un
  // plancher plus haut forcerait un chevauchement PLUS GRAND avec le
  // panneau flottant dès que la place naturelle est juste inférieure à ce
  // plancher (vérifié empiriquement) — 0 laisse toujours la zone se réduire
  // exactement à ce qu'il faut pour ne jamais passer sous le panneau,
  // quitte à devenir minuscule (mais jamais négative/incohérente) quand la
  // fenêtre est vraiment trop basse pour tout afficher.
  scrollEl.style.maxHeight = 'none';           // repart d'un calcul flex propre avant de mesurer
  const naturalHeight = scrollEl.getBoundingClientRect().height;
  scrollEl.style.maxHeight = Math.max(0, naturalHeight - panel.offsetHeight) + 'px';
}

// Réserve l'espace du panneau CHAT (bas-droite, flottant sur .log-table-wrap
// — le seul panneau encore flottant depuis que CW/keyer vocal ont leur propre
// bandeau plein largeur .keyer-dock, 04/08/2026, qui n'a plus besoin de cette
// mécanique : il pousse .main dans le flux normal, il ne flotte plus dessus).
// Le plafond posé par _reserveBottomSpace() est une valeur ABSOLUE en pixels,
// mesurée à un instant donné : elle devient fausse dès que la mise en page
// bouge.
//
// DÉFAUT RÉEL, signalé par l'utilisateur puis reproduit à la mesure : l'appel
// ne se faisait qu'au DOMContentLoaded, donc AVANT que init() (async : config
// serveur, log, calldb) ait fini de peupler et d'afficher les panneaux. Le
// plafond était calculé sur une mise en page transitoire, puis gardé tel quel
// pour toute la session.
//
// Et aucun recalcul au redimensionnement : agrandir la fenêtre ne rendait
// jamais la hauteur gagnée.
function _majReservesBas(){
  _reserveBottomSpace(document.getElementById('chatPanel'),
                      document.querySelector('.log-table-wrap'));
}

function toggleChat(){
  const panel = document.getElementById('chatPanel');
  panel.classList.toggle('open');
  _reserveBottomSpace(panel, document.querySelector('.log-table-wrap'));
  if(panel.classList.contains('open')){
    const unread = document.getElementById('chatUnread');
    if(unread){ unread.style.display = 'none'; unread.textContent = '0'; }
    const body = document.getElementById('chatBody');
    if(body) body.scrollTop = body.scrollHeight;
    document.getElementById('chatInput').focus();
    // Poll immédiat à l'ouverture : le poll de fond peut être en cadence
    // ralentie (15s, panneau fermé) — ne pas attendre jusqu'à ce délai pour
    // afficher les messages reçus pendant que le panneau était fermé.
    pollChat();
  }
}

// ─── DÉCODEUR CW ─────────────────────────────────────────────────────────────
// Vit dans .keyer-dock (bandeau plein largeur sous .main, voir logx_logbook.html)
// depuis le 04/08/2026 — plus un panneau flottant, donc plus besoin de
// _reserveBottomSpace() ici : .keyer-dock pousse .main dans le flux normal
// au lieu de flotter par-dessus. pipeline DSP dans logx_cwdecoder.js, ce
// fichier ne fait que le brancher à l'UI (device picker, bouton start/stop,
// sortie texte défilante).
// Composant partagé radio 1 / radio 2 (SO2R Phase 2) : voir logx_cw_panel.js
// (chargé avant ce fichier) pour ce qui était ~90 lignes dupliquées ligne à
// ligne (même convention de duplication que cat_port/cat2_port ailleurs dans
// le projet, ici remplacée par UNE classe paramétrée par le suffixe d'id DOM
// — CwAudioDecoder reste réentrante, les deux décodeurs tournent toujours
// indépendamment et simultanément si besoin).
// Instanciation PARESSEUSE (pas au chargement du script) : de nombreux tests
// (test_notify_dynamic_i18n.py, test_rph_weekend_fallback.py, etc.) évaluent
// logx_logbook.js dans un moteur JS isolé, SANS logx_cw_panel.js — un
// `new CwPanel()` immédiat ferait échouer leur simple chargement du script
// (donc TOUTES leurs assertions, même sans aucun rapport avec le CW) avec
// une ReferenceError. La vraie page HTML charge bien logx_cw_panel.js avant
// logx_logbook.js, donc CwPanel est de toute façon déjà disponible au moment
// où un opérateur clique réellement sur le panneau — la paresse ne change
// rien en usage normal, elle protège seulement les harnais de test partiels.
let _cwPanelInstances = null;
function _cwPanel(suffix){
  if(!_cwPanelInstances) _cwPanelInstances = { '': new CwPanel(''), '2': new CwPanel('2') };
  return _cwPanelInstances[suffix];
}

// Wrappers globaux conservés tels quels (nom et arité inchangés) : le HTML
// (onclick="toggleCwPanel()" etc.) et tests/test_cw_panel_consolidation.py
// (qui vérifie qu'il n'existe qu'UNE SEULE déclaration de toggleCwDecoder)
// n'ont besoin de rien savoir de CwPanel.
function toggleCwPanel(){ return _cwPanel('').toggle(); }
function toggleCwPanel2(){ return _cwPanel('2').toggle(); }
function toggleCwDecoder(){ return _cwPanel('').toggleDecoder(); }
function toggleCwDecoder2(){ return _cwPanel('2').toggleDecoder(); }
function clearCwOutput(){ return _cwPanel('').clearOutput(); }
function clearCwOutput2(){ return _cwPanel('2').clearOutput(); }
function setCwFreq(freq){ _cwPanel('').setFreq(freq); }
function setCwFreq2(freq){ _cwPanel('2').setFreq(freq); }

// _cwOutText/_cwOutText2 : accesseurs de compatibilité vers l'état interne de
// CwPanel — tests/test_cw_panel_consolidation.py lit/écrit _cwOutText
// directement (écrit avant ce refactor, sur le comportement de
// clearCwOutput()) ; plutôt que de le réécrire pour un détail d'implémentation
// sans rapport avec ce qu'il vérifie réellement, ces deux variables globales
// historiques restent lisibles/inscriptibles et reflètent fidèlement
// this.outText de chaque instance. Object.defineProperty() elle-même
// n'instancie rien (la paresse de _cwPanel() est préservée).
Object.defineProperty(window, '_cwOutText', {
  get(){ return _cwPanel('').outText; },
  set(v){ _cwPanel('').outText = v; },
});
Object.defineProperty(window, '_cwOutText2', {
  get(){ return _cwPanel('2').outText; },
  set(v){ _cwPanel('2').outText = v; },
});

// Peuple un <select> d'entrées audio disponibles — générique, réutilisé par
// le décodeur CW ET l'enregistreur audio par QSO (voir plus haut). Les
// libellés des périphériques ne sont visibles qu'APRÈS une autorisation
// micro accordée (contrainte navigateur) : on la demande une fois ici juste
// pour peupler la liste, le flux est refermé aussitôt.
// `alreadyGranted` évite de rouvrir un DEUXIÈME flux micro concurrent quand
// l'appelant a DÉJÀ un flux ouvert avec la permission accordée (cas de
// startAudioRecorder juste après son propre getUserMedia) : la permission et
// les libellés sont globaux au navigateur, pas liés à un flux particulier —
// un second getUserMedia() ici serait un flux superflu, jamais fermé
// explicitement en cas d'erreur avant son propre stop().
async function loadAudioInputDevices(selectId, alreadyGranted){
  const sel = document.getElementById(selectId);
  if(!sel) return false;
  try{
    if(!alreadyGranted){
      const tmp = await navigator.mediaDevices.getUserMedia({audio:true});
      tmp.getTracks().forEach(t=>t.stop());
    }
    const devices = await navigator.mediaDevices.enumerateDevices();
    const inputs = devices.filter(d=>d.kind==='audioinput');
    sel.innerHTML = '<option value="">— périphérique par défaut —</option>'
      + inputs.map(d=>`<option value="${d.deviceId}">${escHtml(d.label||'Entrée audio')}</option>`).join('');
    return true;
  }catch(e){
    sel.innerHTML = '<option value="">Accès micro refusé</option>';
    return false;
  }
}
// Périphériques de SORTIE (émission RTTY/SSTV) : setSinkId (utilisé par
// txAudioPtt() pour router la lecture vers CE périphérique précis) n'existe
// que sur HTMLMediaElement, jamais directement sur AudioContext — d'où le
// test de support explicite, comme dans logx_ft8.html. Les libellés ne sont
// visibles qu'après une autorisation micro (même contrainte navigateur que
// pour les entrées, y compris pour lister des SORTIES) : `alreadyGranted`
// évite de redemander si l'appelant vient déjà d'obtenir la permission via
// loadAudioInputDevices() pour le même panneau.
async function loadAudioOutputDevices(selectId, alreadyGranted){
  const sel = document.getElementById(selectId);
  if(!sel) return false;
  if(!HTMLMediaElement.prototype.setSinkId){
    sel.innerHTML = '<option value="">Choix de sortie non supporté par ce navigateur</option>';
    sel.disabled = true;
    return false;
  }
  try{
    if(!alreadyGranted){
      const tmp = await navigator.mediaDevices.getUserMedia({audio:true});
      tmp.getTracks().forEach(t=>t.stop());
    }
    const devices = await navigator.mediaDevices.enumerateDevices();
    const outputs = devices.filter(d=>d.kind==='audiooutput');
    sel.innerHTML = '<option value="">— périphérique par défaut —</option>'
      + outputs.map(d=>`<option value="${d.deviceId}">${escHtml(d.label||'Sortie audio')}</option>`).join('');
    return true;
  }catch(e){
    sel.innerHTML = '<option value="">Accès micro refusé</option>';
    return false;
  }
}

// ─── TX audio générique (RTTY/SSTV) : PTT ON -> lecture -> PTT OFF ──────────
// Même modèle que logx_ft8.html (jouerForme+pttOn) — dupliqué ici plutôt que
// partagé entre pages : logx_ft8.html est une page <script> isolée (IIFE),
// aucun fichier JS commun entre les deux pour l'instant. PTT OFF dans un
// `finally` : même si la lecture audio plante en cours de route, la radio ne
// doit jamais rester bloquée en émission.
async function txAudioPtt(wave, sampleRate, outDeviceId){
  const pttOk = await fetch('/rig/ptt', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({on:true})}).then(r=>r.json()).then(d=>!!d.ok).catch(()=>false);
  if(!pttOk) return {ok:false, error:"PTT refusé — vérifie le pilotage radio (CONFIG)"};
  try{
    const ctx = new (window.AudioContext || window.webkitAudioContext)({sampleRate});
    const buf = ctx.createBuffer(1, wave.length, sampleRate);
    buf.copyToChannel(wave, 0);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    if(outDeviceId && HTMLMediaElement.prototype.setSinkId){
      // Route vers un périphérique de sortie précis : MediaStreamDestination
      // + <audio> caché (setSinkId n'existe que sur HTMLMediaElement, pas
      // directement sur AudioContext dans la plupart des navigateurs).
      const dest = ctx.createMediaStreamDestination();
      src.connect(dest);
      const audioEl = new Audio();
      audioEl.srcObject = dest.stream;
      await audioEl.setSinkId(outDeviceId);
      await audioEl.play();
      src.start();
      await new Promise(resolve => { src.onended = resolve; });
      audioEl.pause();
    } else {
      src.connect(ctx.destination);
      src.start();
      await new Promise(resolve => { src.onended = resolve; });
    }
    try{ ctx.close(); }catch(e){}
    return {ok:true};
  }catch(e){
    return {ok:false, error: e.message};
  } finally {
    fetch('/rig/ptt', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({on:false})}).catch(()=>{});
  }
}

// ─── TOGGLE JOUR/NUIT ────────────────────────────────────────────────────────
function toggleTheme(){
  const day = document.body.classList.toggle('day-mode');
  localStorage.setItem('rc_theme', day ? 'day' : 'night');
  document.getElementById('themeToggle').textContent = day ? '🌙' : '☀️';
  // Partagé au serveur : les autres postes ouvrant le lien multi-poste pour
  // la 1re fois hériteront de ce thème au lieu de retomber en mode nuit.
  fetch('/ui/theme', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({theme: day ? 'day' : 'night'})}).catch(()=>{});
}

function toggleShortcutsHelp(){
  document.getElementById('shortcutsOverlay').classList.toggle('show');
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
// Une fenêtre modale est-elle ouverte ? Sert à neutraliser les macros F1-F8 :
// en train d'éditer un QSO ou de relire le vérificateur, on ne veut surtout pas
// qu'une touche de fonction parte en émission. Mêmes boîtes que celles que la
// touche Échap referme, plus bas.
function _modaleOuverte(){
  const setup = document.getElementById('setupModal');
  if(setup && setup.style.display !== 'none' && setup.style.display !== '') return true;
  return ['editOverlay', 'shortcutsOverlay', 'validateOverlay',
          'awardsOverlay', 'importOverlay'].some(id => {
    const el = document.getElementById(id);
    return el && el.classList.contains('show');
  });
}

document.addEventListener('keydown', e => {
  // ─── F1 à F8 : les macros, au clavier ─────────────────────────────────────
  // Les boutons AFFICHENT « F1 »… « F8 » depuis toujours, mais seul le clic les
  // déclenchait : en run ou en pile-up, la main devait quitter le clavier pour
  // viser un bouton. C'est la fonction que N1MM, Win-Test et DXLog mettent en
  // avant en premier, et la première qu'un contesteur essaie.
  //
  // Volontairement actif MÊME quand le focus est dans un champ de saisie :
  // c'est tout l'intérêt — on tape l'indicatif, on envoie l'échange, on
  // continue de taper sans rien viser.
  //
  // preventDefault() n'est pas une politesse : dans un navigateur, F5 recharge
  // la page (perte de la saisie en cours EN PLEIN CONCOURS), F3 ouvre la
  // recherche, F1 l'aide et F6 la barre d'adresse. Sans lui, la moitié des
  // macros seraient inutilisables.
  //
  // On cherche la macro par son libellé de touche plutôt que par sa position :
  // l'utilisateur peut réaffecter la touche d'une macro (editMacro), et le
  // clavier doit suivre ce qu'il voit écrit sur le bouton.
  if(/^F[1-8]$/.test(e.key) && !e.ctrlKey && !e.altKey && !e.metaKey){
    e.preventDefault();
    if(!isSetupDone || _modaleOuverte()) return;
    const macros = getMacros();
    const idx = macros.findIndex(m => m && m.key === e.key);
    if(idx >= 0) copyMacro(idx);
    return;
  }
  // ─── Search & Pounce au clavier ───────────────────────────────────────────
  // Ctrl+↑ / Ctrl+↓ : sauter au spot suivant/précédent du band map, QSY compris
  // et indicatif pré-rempli. Ctrl+Entrée : noter la station en cours.
  // Ces trois gestes forment la boucle du S&P — balayer, noter, rappeler —
  // sans jamais quitter le clavier. Les flèches SEULES restent aux suggestions
  // d'indicatif et de locator, qu'on ne doit pas leur voler.
  if((e.ctrlKey || e.metaKey) && (e.key === 'ArrowUp' || e.key === 'ArrowDown')){
    e.preventDefault();
    if(isSetupDone && !_modaleOuverte()) bandmapSaut(e.key === 'ArrowDown' ? 1 : -1);
    return;
  }
  if((e.ctrlKey || e.metaKey) && e.key === 'Enter'){
    e.preventDefault();
    if(isSetupDone && !_modaleOuverte()) bandmapNoter();
    return;
  }
  // SO2R : Ctrl+Espace bascule l'émission sur l'autre radio. C'est LE geste
  // du SO2R, il doit être atteignable sans quitter le clavier ni regarder
  // l'écran — on appelle CQ d'un côté en cherchant de l'autre.
  if((e.ctrlKey || e.metaKey) && e.key === ' '){
    e.preventDefault();
    if(isSetupDone && !_modaleOuverte()) so2rBasculer();
    return;
  }
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
    // La fenêtre d'édition de QSO s'appelle editOverlay et s'ouvre/ferme par
    // la classe .show (pas editModal/style.display — ancien mécanisme disparu).
    const editOverlay = document.getElementById('editOverlay');
    if(editOverlay) editOverlay.classList.remove('show');
    const scOverlay = document.getElementById('shortcutsOverlay');
    if(scOverlay) scOverlay.classList.remove('show');
    const valOverlay = document.getElementById('validateOverlay');
    if(valOverlay) valOverlay.classList.remove('show');
    const awOverlay = document.getElementById('awardsOverlay');
    if(awOverlay) awOverlay.classList.remove('show');
    const impOverlay = document.getElementById('importOverlay');
    if(impOverlay) impOverlay.classList.remove('show');
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
  try{ cfg = JSON.parse(localStorage.getItem('logx_config')||'{}'); }catch(e){}

  applyUsageModeToLogbook(cfg.usage_mode);

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
  // LOGBOOK SIMPLE : un seul opérateur, point — le rôle auparavant tenu par
  // le champ CLUB ici (radio-club = plusieurs opérateurs qui se relaient) est
  // désormais assuré par le mode RADIOCLUB dédié (cf. logx_configuration.html).
  // RADIOCLUB : jusqu'à 40 opérateurs, pas de classification SO*/MO* EDI
  // pertinente ici — seul le nombre d'opérateurs déclarés compte.
  const isSingleOp = usageMode === 'simple'
    ? true
    : usageMode === 'radioclub'
    ? ops.length <= 1
    : (/^SO/i.test(cfg.section || '') || ops.length <= 1);
  if(ops.length){
    opEl.innerHTML = '<option value="">-- Sélectionne ton identifiant opérateur --</option>';
    ops.forEach((op, i) => {
      const val = `OP${i+1}`;
      const call = op.call || op.callsign || '';
      const lbl = call ? `${val} — ${call}${op.name?' ('+op.name+')':''}` : val;
      opEl.innerHTML += `<option value="${val}">${lbl}</option>`;
    });
    // Boutons OP du formulaire : régénérés depuis la config (jusqu'à 40 en
    // mode RADIOCLUB, la grille flex existante wrap automatiquement) — un
    // bouton par opérateur réellement configuré, plus de OP4/OP5 fantômes.
    const opPopupEl = document.getElementById('opPickerPopup');
    const activeOp = opPopupEl.querySelector('.op-btn.active')?.dataset.op || myOp;
    opPopupEl.innerHTML = ops.map((op, i) => {
      const val = `OP${i+1}`;
      const call = op.call || op.callsign || val;
      return `<button class="op-btn${val===activeOp?' active':''}" data-op="${val}" onclick="pickOp('${val}')">${escHtml(call)}</button>`;
    }).join('');
    _setCurrentOpLabel(activeOp);
  }
  // Masquer tout ce qui est multi-op en single-op : sélecteur d'opérateur,
  // classement par opérateur, chat inter-postes. L'opérateur reste OP1.
  const opGroup = document.getElementById('opCurrentBtn').closest('.field-group');
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

// ─── RACCOURCI BUREAU (premier lancement de l'exécutable figé) ───────────────
// GET /shortcut/status ne renvoie show:true que si is_frozen() ET qu'aucun
// marqueur .shortcut_offered n'existe encore (voir logx_shortcut.py) — donc
// systématiquement false en mode développeur (python logx_serveur.py), la
// bannière ne peut alors jamais s'afficher, comme voulu.
async function checkShortcutOffer(){
  try{
    const r = await fetch('/shortcut/status');
    const d = await r.json();
    if(d.show){
      const el = document.getElementById('shortcutOffer');
      if(el) el.classList.add('show');
    }
  }catch(e){ /* pas bloquant : au pire la bannière n'apparaît pas cette fois */ }
}

function hideShortcutOffer(){
  const el = document.getElementById('shortcutOffer');
  if(el) el.classList.remove('show');
}

// Clic "Oui" : le serveur crée réellement le raccourci (PowerShell/COM, voir
// logx_winshell.create_desktop_shortcut) ET pose le marqueur dans tous les
// cas — la bannière ne doit donc plus jamais réapparaître après ce clic,
// même si la création elle-même a échoué.
async function createDesktopShortcut(){
  hideShortcutOffer();
  try{
    const r = await fetch('/shortcut/create_desktop', {method:'POST'});
    const d = await r.json();
    if(d.ok) notify(trF('🖥️ Raccourci créé sur le bureau : {path}', {path: d.path}));
    else notify(trF('❌ Raccourci bureau : {err}', {err: d.message || d.error || trT('échec')}));
  }catch(e){ notify(trT('❌ Serveur injoignable pour créer le raccourci')); }
}

// Clic "Non merci" : ne crée rien, pose juste le marqueur pour ne plus
// jamais reproposer la bannière.
function dismissShortcutOffer(){
  hideShortcutOffer();
  fetch('/shortcut/dismiss', {method:'POST'}).catch(()=>{});
}

// ─── BROADCAST CHANNEL (sync multi-onglet) ────────────────────────────────────
let _bc = null;
function initBroadcastChannel(){
  if(!window.BroadcastChannel) return;
  _bc = new BroadcastChannel('logx_log');
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
    } else if(type === 'prefill_call'){
      // Émis par logx_panadapter.html au clic sur un repère de spot superposé
      // au spectre (fenêtre DÉTACHÉE, pas d'accès direct au DOM de cette page
      // — le QSY lui-même est déjà fait côté panadapter, /rig/qsy, avant ce
      // message ; ici on ne fait QUE remplir l'indicatif, même geste que
      // bandmapClick()). Ignoré si la fenêtre panadapter tourne seule et que
      // CETTE page n'a pas de champ de saisie affiché (impossible en usage
      // normal, mais évite un throw silencieux si le DOM a changé entretemps.
      const call = (data && data.call) || '';
      const inp = document.getElementById('inputCall');
      if(call && inp){ inp.value = call; onCallInput(); inp.focus(); }
    }
  };
}
function bcBroadcast(type, data){
  if(_bc) try{ _bc.postMessage({type, data}); }catch(e){}
}

// Re-rendre les boutons bande/mode quand la config change dans un autre onglet
window.addEventListener('storage', e => {
  if(e.key === 'logx_config'){
    renderBandButtons(currentContest);
    renderModeButtons(currentContest);
  }
  // Suivre le thème jour/nuit choisi dans un autre onglet (ex: logx_configuration.html)
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
  // Réserve dès le chargement l'espace occupé par les panneaux flottants
  // CHAT/CW (même repliés, ~36px) — cf. _reserveBottomSpace(). Le CW cible
  // .saisie-secondary (SA zone de scroll propre), pas .saisie-panel — voir
  // le commentaire de toggleCwPanel().
  _majReservesBas();
});

// Le calcul ci-dessus porte sur une mise en page ENCORE TRANSITOIRE : init()
// est asynchrone et continue de peupler/afficher des panneaux après le
// DOMContentLoaded. Un plafond en pixels absolus fige alors une valeur fausse
// pour toute la session (voir _majReservesBas). On refait donc le calcul une
// fois la page vraiment terminée, puis à chaque changement de taille.
window.addEventListener('load', () => {
  // Deux trames : la 1re laisse le navigateur appliquer la mise en page
  // finale, la 2de mesure dessus. Mesurer dans la 1re rendrait la valeur
  // d'avant — le défaut même qu'on corrige.
  requestAnimationFrame(() => requestAnimationFrame(_majReservesBas));
});

// Redimensionnement : sans ça, agrandir la fenêtre ne rendait jamais la
// hauteur gagnée (le plafond restait celui de l'ancienne taille), et la
// réduire laissait le panneau flottant recouvrir le contenu.
let _reservesTimer = null;
window.addEventListener('resize', () => {
  clearTimeout(_reservesTimer);
  // Groupé : un redimensionnement à la souris émet des dizaines
  // d'événements, et chaque recalcul force une mesure de mise en page.
  _reservesTimer = setTimeout(_majReservesBas, 150);
});

// CARTE QSO (Leaflet) : extraite vers logx_qso_map.js (EV-7 phase 2,
// 12e increment, docs/LogX_AI_PRD.md) -- chargee en <script> classique
// dans logx_logbook.html, portee globale partagee.

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
  loadScoringDefs();          // barèmes serveur (briques) — non bloquant
  await loadCallDB();
  await loadServerConfig();
  refreshCluster();
  setInterval(refreshCluster, 60000);
  prefillSetupFromConfig();
  checkShortcutOffer();       // bannière raccourci bureau — non bloquant, voir logx_shortcut.py
}

// SÉLECTEUR CONCOURS FONCTIONS : extrait vers logx_contest_picker.js
// (EV-7 phase 2, 10e incrément, docs/LogX_AI_PRD.md) — chargé en <script>
// classique dans logx_logbook.html, portée globale partagée.

// Panneau STATS (rythme QSO/heure, répartition bande/heure) : extrait vers
// logx_rate_panel.js (EV-7, docs/LogX_AI_PRD.md) — chargé en <script>
// classique dans logx_logbook.html, portée globale partagée.

