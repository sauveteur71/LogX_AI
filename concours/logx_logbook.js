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
let serverCat2Enabled = false;

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
  _refreshScoreToggleBtn();
}

// #scoreVisibleToggle : point unique, appelé à la fois par
// applyUsageModeToLogbook() (changement de mode) et applyContestActifToLogbook()
// (rappelé à CHAQUE rafraîchissement de bannière, cf. commentaire sur ce
// dernier plus bas — même raison ici : un changement de concours qui ne
// passerait pas par applyUsageModeToLogbook() laisserait sinon ce bouton
// obsolète).
function _refreshScoreToggleBtn(){
  const btn = document.getElementById('scoreVisibleToggle');
  if(!btn) return;
  const pertinent = usageMode !== 'simple' && usageMode !== 'expedition' && !contestActif();
  btn.style.display = pertinent ? '' : 'none';
  const demandee = _scoreDemandee();
  btn.textContent = demandee ? '📊 SCORE ●' : '📊 SCORE ○';
  btn.style.color = demandee ? 'var(--green)' : 'var(--muted)';
  btn.style.borderColor = demandee ? 'var(--green)' : 'var(--border)';
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
// Le bandeau de score doit-il rester visible malgré bandeauxRythmeMasques() ?
// Clé dédiée (pas dans logx_config, même patron que rc_ui_mode/logx_activity :
// une clé racine indépendante n'est pas tributaire du cycle de saveConfig()).
function _scoreDemandee(){
  try{ return localStorage.getItem('logx_score_visible') === 'true'; }catch(e){ return false; }
}
function toggleScoreVisible(){
  try{ localStorage.setItem('logx_score_visible', _scoreDemandee() ? 'false' : 'true'); }catch(e){}
  applyUsageModeToLogbook(usageMode);
}

function bandeauxRythmeMasques(){
  // Expédition : ni score à suivre, ni temps restant, ni classement à
  // départager — on log en continu pendant des jours. Les 310 px mesurés que
  // ces bandeaux occupent manquent bien davantage à la saisie, surtout sur un
  // portable en /P.
  if (usageMode === 'simple' || usageMode === 'expedition') return true;
  // Hors concours actif, masqué PAR DÉFAUT (retour F4GLD 22/08/2026,
  // « épurer au maximum » — chantier page d'accueil par activité), sur
  // demande sinon (#scoreVisibleToggle). Même raisonnement déjà appliqué par
  // body.sans-concours (logx_logbook.html) au sous-ensemble PTS/SCORE TOTAL
  // — un « SCORE TOTAL » sans concours sélectionné laisse croire à un
  // classement qui n'existe pas — étendu ici au bandeau entier plutôt que
  // dupliqué une 2e fois avec une règle différente.
  if (!contestActif() && !_scoreDemandee()) return true;
  return false;
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
  // CSV « valide » = uniquement les QSO complets/validés (comme ADIF/Cabrillo),
  // à côté du CSV complet (brut, tous les QSO). Le libellé dit la distinction.
  apres.push(['📥', 'Exporter CSV valide (QSO validés)', 'exportCSVValide']);
  // Carte QSL papier : action légitime après avoir loggué des QSO même en
  // usage simple/DXpédition (envoyer une carte QSL est une pratique courante,
  // pas un outil de power-user) -- donc PAS dans MENU_LB_EXPERT_ONLY_FN.
  apres.push(['🖼️', 'CARTE QSL — designer imprimable', 'showQslCardDesigner']);
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
  _refreshScoreToggleBtn();   // échappatoire du masquage par défaut hors concours (voir bandeauxRythmeMasques())
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
let lastActQsoTotal = 0;

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
    // Export ADIF prêt-à-téléverser : POTA seulement (pas d'équivalent
    // documenté pour SOTA/IOTA/WWFF côté LogX AI pour l'instant).
    const eb = document.getElementById('actExportBtn');
    if(eb) eb.style.display = (activationProgram === 'POTA') ? '' : 'none';
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
    lastActQsoTotal = d.qso_total || 0;
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

// Export ADIF de l'activation POTA en cours, prêt à glisser-déposer sur la
// page « My Log Uploads » de pota.app. Pas d'upload automatique : POTA
// n'a pas d'API publique documentée pour ça (contrairement à LoTW/tqsl,
// cf. logx_awards.js) — ce bouton retire toute la friction qui PEUT
// l'être sans stocker d'identifiant de compte POTA : bon format ADIF, bon
// nom de fichier, et la page d'upload s'ouvre toute seule dans un nouvel
// onglet pour qu'il ne reste qu'à y glisser le fichier téléchargé.
function exportPotaAdif(){
  if(activationProgram !== 'POTA' || !myActivationRef) return;
  if(!lastActQsoTotal){
    notify('Aucun QSO enregistré pour ce parc : logue au moins un contact avant d’exporter.');
    return;
  }
  window.location.href = '/pota/export_adif';
  window.open('https://pota.app/#/user/logs', '_blank', 'noopener');
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
  'REF_CCD_JAN1': {start:'2026-01-03T13:00:00Z', end:'2026-01-03T17:00:00Z', dur:'4h',  email:'ccd@r-e-f.org'},
  'REF_CCD_JAN2': {start:'2026-01-03T13:00:00Z', end:'2026-01-03T17:00:00Z', dur:'4h',  email:'ccd@r-e-f.org'},
  'REF_CDF_HF_SSB': {start:'2026-03-28T14:00:00Z', end:'2026-03-29T14:00:00Z', dur:'24h', email:'logs@r-e-f.org'},
  'REF_CDF_HF_CW':  {start:'2026-03-28T14:00:00Z', end:'2026-03-29T14:00:00Z', dur:'24h', email:'logs@r-e-f.org'},
  'REF_NAT_THF':  {start:'2026-03-07T06:00:00Z', end:'2026-03-08T06:00:00Z', dur:'24h', email:'thf@r-e-f.org'},
  'CQ_WW_SSB':    {start:'2026-10-24T00:00:00Z', end:'2026-10-26T00:00:00Z', dur:'48h', email:'logcheck@cqww.com'},
  'CQ_WW_CW':     {start:'2026-11-28T00:00:00Z', end:'2026-11-30T00:00:00Z', dur:'48h', email:'logcheck@cqww.com'},
  'CQ_WPX_SSB':   {start:'2026-03-28T00:00:00Z', end:'2026-03-30T00:00:00Z', dur:'48h', email:'wpxlog@cqww.com'},
  'CQ_WPX_CW':    {start:'2026-05-30T00:00:00Z', end:'2026-06-01T00:00:00Z', dur:'48h', email:'wpxlog@cqww.com'},
  'ARRL_DX_SSB':  {start:'2026-02-21T00:00:00Z', end:'2026-02-23T00:00:00Z', dur:'48h', email:'contests@arrl.org'},
  'ARRL_DX_CW':   {start:'2026-03-07T00:00:00Z', end:'2026-03-09T00:00:00Z', dur:'48h', email:'contests@arrl.org'},
  'REF_IARU_TVA': {start:'2026-05-09T06:00:00Z', end:'2026-05-10T06:00:00Z', dur:'24h', email:'vhf@r-e-f.org'},
  'REF_IARU_50':  {start:'2026-05-09T06:00:00Z', end:'2026-05-10T06:00:00Z', dur:'24h', email:'vhf@r-e-f.org'},
  'REF_IARU_VHF': {start:'2026-07-04T06:00:00Z', end:'2026-07-05T06:00:00Z', dur:'24h', email:'vhf@r-e-f.org'},
  'REF_IARU_UHF': {start:'2026-07-04T06:00:00Z', end:'2026-07-05T06:00:00Z', dur:'24h', email:'uhf@r-e-f.org'},
  'REF_DDFM_50':  {start:'2026-06-20T06:00:00Z', end:'2026-06-20T10:00:00Z', dur:'4h',  email:'ddfm@r-e-f.org'},
  'F9NL':         {start:'2026-03-15T08:00:00Z', end:'2026-03-15T16:00:00Z', dur:'8h',  email:'logs@r-e-f.org'},
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
  // CQ WPX (règlement cqwpx.com/rules.htm) : points DOUBLÉS sur les bandes
  // basses 160/80/40 m (6/2/1 au lieu de 3/1/1) — miroir du fix serveur
  // (logx_definitions.py CQ_WPX_SSB/CW.scoring.bricks). Repli hors-ligne
  // uniquement : quand le serveur répond, calcPoints() utilise directement
  // les bricks transmis par /data/calendar (voir evalPointsFromDef ci-dessous).
  prefix_multiplier:         {points:[{bands:['1.8','3.5','7'], when:'different_continent', points:6},
                                      {bands:['1.8','3.5','7'], when:'same_country', points:{param:'points_same_country', default:1}},
                                      {bands:['1.8','3.5','7'], points:2},
                                      {when:'different_continent', points:{param:'points_dx', default:3}},
                                      {when:'same_country', points:{param:'points_same_country', default:1}},
                                      {points:{param:'points_same_continent', default:1}}]},
  prefix:                    {points:[{when:'different_continent', points:6},
                                      {when:'na_w_ve', points:2}, {points:1}]},
  power_state:               {points:[{points:{param:'points', default:3}}], validity:'is_na'},
  fd_class:                  {points:[{modes:['CW'], points:{param:'points_cw', default:2}},
                                      {modes:['FT8','FT4','RTTY','PSK'], points:{param:'points_digital', default:2}},
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
    myBase,
    dxCountry: dxInfo ? dxInfo.c : (dxBase.slice(0,2) || '??'),
    myCountry: myInfo ? myInfo.c : (myBase.slice(0,2) || 'F'),
    dxCont: (dxInfo && dxInfo.ct) || 'EU',
    myCont: (myInfo && myInfo.ct) || 'EU',
    // Miroir de logx_scoring.py:calc_qso_value dx_maritime_mobile — suffixe
    // '/MM' de l'indicatif BRUT (pas dxBase, qui l'a déjà retiré au même
    // titre que /P ou /QRP).
    dxMaritimeMobile: (callDX || '').trim().toUpperCase().endsWith('/MM'),
  };
}

// A05 (docs/FEUILLE_DE_ROUTE.md) : signale bruyamment un prédicat de barème
// inconnu du miroir JS au lieu de retomber en silence sur 'always' (= QSO
// toujours valide/plein pot) -- un score client faux EN DIRECT pendant un
// concours, sans rien pour le signaler, était le vrai défaut. `_predicatsInconnusVus`
// évite de spammer la console à chaque QSO pour le MÊME prédicat manquant.
const _predicatsInconnusVus = new Set();
function _signalerPredicatInconnu(nom){
  if (_predicatsInconnusVus.has(nom)) return;
  _predicatsInconnusVus.add(nom);
  console.error(`[SCORING] Prédicat de barème inconnu du miroir JS : '${nom}' — ` +
    'le score CLIENT peut être faux pour ce concours (le serveur, ' +
    'autoritaire, reste correct). Voir BRICK_PREDICATES (logx_logbook.js) ' +
    'et son équivalent PREDICATES (logx_scoring.py).');
  try{ _bandeauPredicatInconnu(nom); }catch(e){}
}
// Bandeau visuel, même mécanisme que _confirmDupBanner (pas de dépendance à
// une zone d'affichage du score précise, qui varie selon la page/le layout) :
// un texte discret mais visible tant qu'au moins un prédicat inconnu a été
// rencontré cette session, plutôt qu'un score qui a l'air normal.
// Drapeau dédié (pas un test getElementById()) : dans un DOM minimal/stub,
// getElementById() peut créer l'élément à la lecture -- un test sur son
// existence ne détecterait alors jamais "pas encore affiché".
let _bandeauPredicatInconnuAffiche = false;
function _bandeauPredicatInconnu(nom){
  if (_bandeauPredicatInconnuAffiche) return;   // déjà affiché, un seul suffit
  _bandeauPredicatInconnuAffiche = true;
  const el = document.createElement('div');
  el.id = 'scoringPredicatInconnuBanner';
  el.style.cssText = 'position:fixed;bottom:8px;right:8px;z-index:9999;' +
    'background:var(--red,#FF2D55);color:#fff;font-family:var(--font-mono,monospace);' +
    'font-size:11px;padding:6px 10px;border-radius:6px;max-width:320px;' +
    'box-shadow:0 2px 8px rgba(0,0,0,.3)';
  el.textContent = `⚠ Score affiché possiblement faux (barème '${nom}' non reconnu) — le score serveur reste correct`;
  (document.body || document.documentElement).appendChild(el);
}

const BRICK_PREDICATES = {
  always:              () => true,
  same_country:        x => x.dxCountry === x.myCountry,
  same_continent:      x => x.dxCont === x.myCont,
  different_continent: x => x.dxCont !== x.myCont,
  // CTY_PREFIX (logx_dxcc_lookup.js) distingue déjà France/DOM-TOM par
  // préfixe (c:'France' pour F/TM, c:'Martinique' pour FM, etc.) — un simple
  // /^F/ confondait les DOM-TOM avec la France métropolitaine (même bug que
  // le miroir serveur, logx_scoring.py PREDICATES.is_french). TK (Corse)
  // n'est pas dans cette table encore incomplète (voir finding dédié table
  // DXCC client) : repli explicite sur le préfixe pour ce seul cas.
  is_french:           x => x.dxCountry === 'France' || /^TK/.test(x.dxBase),
  // France métropolitaine + DOM-TOM (contrairement à is_french ci-dessus,
  // strictement métropole) — miroir de logx_scoring.py PREDICATES.
  // is_french_all/my_is_french_all (mêmes 13 entités DXCC : F/TK/FG/FM/FJ/
  // FS/FP/FY/FO/FK/FW/FH/FR). 9 des 13 sont dans CTY_PREFIX (logx_dxcc_lookup.js)
  // sous leur nom français (Martinique, Guadeloupe, Guyane fr....) ; TK/FJ/FS/FW
  // en sont absents (même lacune déjà documentée pour is_french/TK ci-dessus,
  // pas une régression de ce correctif) : repli explicite sur le préfixe,
  // même motif que TK dans is_french.
  is_french_all:       x => ['France','Martinique','Guadeloupe','Guyane fr.','La Réunion',
                             'Nvl-Calédonie','Polynésie fr.','St-Pierre-Miquelon','Mayotte']
                             .includes(x.dxCountry) || /^(TK|FJ|FS|FW)/.test(x.dxBase),
  my_is_french_all:    x => ['France','Martinique','Guadeloupe','Guyane fr.','La Réunion',
                             'Nvl-Calédonie','Polynésie fr.','St-Pierre-Miquelon','Mayotte']
                             .includes(x.myCountry) || /^(TK|FJ|FS|FW)/.test(x.myBase),
  is_maritime_mobile:  x => x.dxMaritimeMobile,
  is_na:               x => _NA_CALL_RE.test(x.dxBase),
  na_w_ve:             x => /^(W|K|N|VE|XE)/.test(x.dxBase),
  is_asia:             x => x.dxCont === 'AS',
  is_eu:               x => x.dxCont === 'EU',
};

// Évalue les points d'un QSO depuis un bloc scoring serveur.
// Retourne un nombre, ou null si le bloc est inexploitable (→ repli local).
function evalPointsFromDef(scoring, callDX, band, mode, dist, locDX, myLoc){
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
      if (!BRICK_PREDICATES[v]) _signalerPredicatInconnu(v);
      ok = (BRICK_PREDICATES[v] || BRICK_PREDICATES.always)(ctx);
    }
    if (!ok) return 0;
  }

  // Points fixes "même grand carré" (IARU)
  const ssp = bricks.same_square_points;
  if (ssp !== undefined && ssp !== null){
    const large = l => (l && l.length >= 4) ? l.slice(0,4).toUpperCase() : null;
    const mySq = large(myLoc || myLocator);
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
    // 'when' : un nom de prédicat, OU une liste combinée en ET logique (ex.
    // REF : ['my_is_french_all','is_french_all','same_continent']) — miroir
    // de logx_scoring.py:calc_qso_value. Le simple `BRICK_PREDICATES[rule.when]`
    // d'avant ce correctif indexait avec un TABLEAU converti en chaîne
    // ("a,b,c"), toujours absent de la table -> repli 'always' silencieux :
    // TOUTE règle à when combiné (le format des barèmes REF) était donc déjà
    // acquise sans condition, dès que bande/mode/prefix_in passaient.
    const whenList = Array.isArray(rule.when) ? rule.when : [rule.when || 'always'];
    const whenOk = whenList.every(w => {
      if (!BRICK_PREDICATES[w]) _signalerPredicatInconnu(w);
      return (BRICK_PREDICATES[w] || BRICK_PREDICATES.always)(ctx);
    });
    if (!whenOk) continue;
    let val = rule.points;
    if (val && typeof val === 'object') val = scoring[val.param] ?? val.default ?? 0;
    if (val === 'per_km') return dist;
    return (typeof val === 'number') ? val : 0;
  }
  return 0;
}

// myLoc (optionnel) : locator à utiliser pour la distance/le calcul, au lieu
// du global `myLocator` (position ACTUELLE de l'opérateur). Nécessaire pour
// recalculer le score d'un QSO déjà loggué avec SA position d'origine
// (q.my_locator) — sinon un rover/expédition qui change de locator en cours
// de concours voit son score rétroactivement faussé pour tous ses anciens
// QSO (voir updateStats()).
function calcPoints(locDX, band, callDX, mode, myLoc){
  const myLL = locLL(myLoc || myLocator);
  const dxLL = locDX ? locLL(locDX) : null;
  const dist = (myLL && dxLL) ? hav(myLL.lat,myLL.lon,dxLL.lat,dxLL.lon) : 0;

  // 1er choix : le barème du serveur (briques) — couvre TOUS les concours,
  // y compris ceux ajoutés par analyse IA, et ne requiert un locator que
  // pour les barèmes à distance
  const def = contestScoringDefs[currentContest];
  if (def){
    const pts = evalPointsFromDef(def, callDX, band, mode, dist, locDX, myLoc);
    if (pts !== null) return pts;
  }

  // ── Repli local historique (serveur injoignable) ──────────────────────────
  if(!myLL||!dxLL) return 0;

  // Scoring selon le concours actif
  const c = currentContest || '';

  // ── HF nord-américains : pts fixes par mode ───────────────────────────────
  if(['ARRL_FD','ARRL_DX_SSB','ARRL_DX_CW'].includes(c)){
    const NA_PFX = /^(W|K|N|AA|AB|AC|AD|AE|AF|AG|AH|AI|AJ|AK|WA|WB|WC|WD|WE|WF|WG|WH|WI|WJ|WK|WL|WM|WN|WO|WP|WQ|WR|WS|WT|WU|WV|WW|WX|WY|WZ|KA|KB|KC|KD|KE|KF|KG|KH|KI|KJ|KK|KL|KM|KN|KO|KP|KQ|KR|KS|KT|KU|KV|KW|KX|KY|KZ|NA|NB|NC|ND|NE|NF|NG|NH|NI|NJ|NK|NL|NM|NN|NO|NP|NQ|NR|NS|NT|NU|NV|NW|NX|NY|NZ|VE|VA|VO|VY)/i;
    // Station hors NA = 0 pt (les deux barèmes ci-dessous)
    if(callDX && !NA_PFX.test(callDX)) return 0;
    if(c === 'ARRL_FD'){
      // ARRL FD : SSB=1pt, CW=2pts, Digital=2pts
      const m = (mode||'SSB').toUpperCase();
      return m==='CW'?2 : (m==='FT8'||m==='FT4'||m==='RTTY'||m==='PSK')?2 : 1;
    }
    // ARRL DX (SSB/CW) : 3 points fixes par QSO, quel que soit le mode —
    // contrairement à ARRL FD, groupée à tort avec ce même barème par mode
    // avant ce correctif.
    return 3;
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

// QSO TIMER (updateQsoTimer) : extrait vers logx_outils_divers.js
// (EV-7 phase 2, 36e increment, docs/LogX_AI_PRD.md) -- charge en <script>
// classique dans logx_logbook.html, portee globale partagee. lastQsoTime
// reste ICI (ecrite par submitQSO(), coeur).

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

// FICHE CALLBOOK A LA FRAPPE (QRZ/HamQTH/HamDB) + statut a la frappe +
// historique "deja contacte" : extrait vers logx_callbook.js (EV-7 phase 2,
// 16e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

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

// ─── BAND MAP : SEARCH & POUNCE : extrait vers logx_bandmap_sp.js (EV-7
// phase 2, 28e increment, docs/LogX_AI_PRD.md) -- charge en <script>
// classique dans logx_logbook.html, portee globale partagee.

// FILTRE D'AFFICHAGE DES SPOTS + refreshBandMap() (_SF_CONTINENTS,
// toggleSpotFiltre, dessinerChipsFiltre, basculerContinent,
// majSpotFiltre, appliquerRetourFiltre, refreshBandMap) : extrait vers
// logx_filtre_spots.js (EV-7 phase 2, 33e increment,
// docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

// BANDSCOPE + WATERFALL (drawBandscope/toggleWaterfall/drawWaterfallRow) :
// extrait vers logx_bandscope_waterfall.js (EV-7 phase 2, 31e increment,
// docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

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

// KEYER VOCAL (phonie, slots DVK cote serveur) : extrait vers
// logx_voice_keyer.js (EV-7 phase 2, 20e increment,
// docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

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

// CALLBOT (macros vocales dynamiques) + ESM (Enter Sends Message) :
// extrait vers logx_esm_callbot.js (EV-7 phase 2, 19e increment,
// docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

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
  // Terminal CW : outil PROPRE au CW (comme les macros) — visible seulement en
  // mode CW (retour terrain F4GLD 24/08 : `expert-only` l'affichait en SSB,
  // « pas fonctionnel »). Le pounce/appel auto, lui, n'est pas un outil CW et
  // n'est pas gaté ici.
  const cwTerm=document.getElementById('cwTerminalPanel');
  if(cwTerm) cwTerm.style.display = cw ? '' : 'none';
  // Bouton d'ARRÊT CW : rafraîchi ICI, et pas seulement au sondage matériel.
  // updateKeyerPanels() est appelée à chaque changement de mode (sélecteur du
  // carnet comme suivi de la radio) ; sans cet appel, passer en CW laissait le
  // bouton caché jusqu'au prochain /hardware/state — jusqu'à 3 secondes
  // pendant lesquelles rien ne permet de couper une émission. Mesuré en
  // vérification navigateur (18/08/2026), pas supposé.
  if(typeof updateCwStopBtn === 'function') updateCwStopBtn();
  // DÉFAUT RÉEL CORRIGÉ ICI (F4GLD, 14/08/2026 : « j'ai désactivé tout le
  // keyer vocal mais il apparaît tout de même dans logbook ») : cette
  // condition ne regardait QUE le mode courant, jamais le réglage CONFIG
  // « KEYER VOCAL » (#voicekeyer_enabled) — le panneau réapparaissait donc
  // en SSB/FM même désactivé. Même patron de lecture que cat2_enabled
  // juste plus bas (localStorage.logx_config).
  let voicekeyerEnabled = true;
  try{
    const stored = JSON.parse(localStorage.getItem('logx_config')||'{}');
    voicekeyerEnabled = !!stored.voicekeyer_enabled;
  }catch(e){}
  // En RTTY comme en SSTV, ni les macros CW ni le keyer vocal n'ont de sens :
  // c'est le décodeur qui prend la place.
  if(voice) voice.style.display = (voicekeyerEnabled && !cw && !rtty && !sstv) ? '' : 'none';
  // Décodeur RTTY : extrait vers logx_rtty.html (fenêtre détachée, EV-7
  // phase 2 incrément B) -- plus de panneau à afficher/masquer ici, `rtty`
  // ne sert plus qu'à masquer voicePanel ci-dessus.
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
    let stored = {};
    try{ stored = JSON.parse(localStorage.getItem('logx_config')||'{}'); }catch(e){}
    const cat2Enabled = stored.cat2_enabled !== undefined && stored.cat2_enabled !== ''
      ? !!stored.cat2_enabled
      : (typeof serverCat2Enabled !== 'undefined' ? serverCat2Enabled : false);
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

// SO2R : bascule d'emission (so2rBasculer/so2rAfficher/so2rRafraichir/
// _so2rFocus) : extrait vers logx_outils_divers.js (EV-7 phase 2,
// 36e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique
// dans logx_logbook.html, portee globale partagee.

// PANNEAU DECODEUR + EMISSION RTTY : extrait vers logx_rtty_panel.js
// (EV-7 phase 2, 15e increment, docs/LogX_AI_PRD.md), puis vers sa PROPRE
// fenetre detachee logx_rtty.html (EV-7 phase 2, increment B, 11/08/2026) --
// plus aucun panneau/script RTTY dans logx_logbook.html.

// PANNEAU DECODEUR SSTV : extrait vers logx_sstv_panel.js (EV-7 phase 2,
// 14e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.
// Au démarrage on demande au SERVEUR quels messages existent : ils n'ont
// jamais été dans ce navigateur si l'opérateur les a enregistrés ailleurs.
voiceRefreshSlots();
renderVoiceDynPanel();
setTimeout(updateKeyerPanels, 300);
initAudioRecorderPanel();

// SAUVEGARDE IMMEDIATE (backupNow) : extraite vers logx_outils_divers.js
// (EV-7 phase 2, 36e increment, docs/LogX_AI_PRD.md) -- charge en <script>
// classique dans logx_logbook.html, portee globale partagee.

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
    // Purge des secrets avant réécriture : setupDone() (LOGBOOK) ne charge
    // pas logx_configuration.js, donc n'a pas accès à
    // _redactStaleSecretsInLocalStorage()/SECRET_CONFIG_FIELDS — un secret
    // en clair resté d'une VERSION ANTÉRIEURE du logiciel dans ce blob
    // survivrait sinon indéfiniment à ce ré-enregistrement. Liste dupliquée
    // volontairement (mêmes noms que SECRET_CONFIG_FIELDS dans
    // logx_configuration.js) : à tenir synchronisée si un champ secret y
    // est ajouté.
    ['api_key', 'clublog_api_key', 'clublog_password', 'eqsl_password',
     'lan_sync_token', 'lotw_password', 'on4kst_password', 'qrz_password',
     'qrzcq_api_key', 'hrdlog_code', 'qrz_logbook_key', 'sota_client_id',
     'cloudsync_secret', 'voicekeyer_ai_api_key', 'mysql_password',
     'relay_password', 'icomremote_password'].forEach(f => delete stored[f]);
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
  // Indicateur « OP : » — en single-op, montrer l'indicatif plutôt que « OP1 ».
  // #currentOp n'existe plus dans le HTML (retiré lors d'un refactor sans que
  // ce site soit mis à jour) : cette assignation non gardée plantait ici en
  // silence, coupant TOUT ce qui suit setupDone() -- startRefresh()/
  // startON4KSTReminder()/startChat()/fetchLog() ne s'exécutaient jamais.
  // _setCurrentOpLabel() ci-dessus a déjà le même garde-fou (if(cur) ...)
  // pour ce même id, ce site l'avait juste oublié.
  const curOpEl = document.getElementById('currentOp');
  if(curOpEl) curOpEl.textContent = _resolveOperatorCallsign(op || 'OP1') || op;
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
  if(!cd) return;

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

// DÉFAUT RÉEL, remonté par F4GLD (IC-7300 en CAT natif, 15/08/2026) : choisir
// une bande/un mode dans CES sélecteurs manuels ne pilotait JAMAIS la radio —
// seul un clic sur un spot du band map le faisait (bandmapClick() plus haut,
// via /rig/qsy). Le carnet changeait bien de bande/mode pour le SCORING/LOG,
// mais la radio elle-même restait où elle était. `opts.fromRig` distingue les
// DEUX appelants de pickBand()/pickMode() : un clic humain (pousse vers la
// radio) contre un rappel de syncBandModeFromRig() (logx_hardware_cat.js, la
// radio vient de nous dire où ELLE est déjà — repousser une commande QSY à ce
// moment-là créerait une boucle poll->QSY->poll inutile, voire nuisible si un
// autre logiciel pilote la même radio sur le bus CI-V).
// La table MODES_NUMERIQUES_PUISSANCE a été DÉPLACÉE dans
// concours/logx_puissance_auto.js, chargé par cette page et par la page FT8.
// Elle n'est pas redéclarée ici : un `const` de même nom masquerait la
// propriété posée sur window par le module, et on se retrouverait avec deux
// tables à tenir à jour — dont l'une, silencieusement, ne serait plus lue.
// ─── SOURCE DU QSO : radio pilotée, ou poste que le PC ne commande pas ─────
//
// Voir le commentaire du bloc #posteSourceGroup dans logx_logbook.html pour le
// POURQUOI. Ici, la mécanique.
//
// L'état est dans localStorage et non dans une variable de page : il doit
// survivre à un rechargement (une séquence FT8 dure des heures, et perdre le
// découplage en rafraîchissant la page enverrait un QSY inattendu au premier
// changement de bande).
//
// Nommage : « découplée » et non le mot interdit dans ce dépôt pour désigner
// une mise en marche (voir la fiche de vocabulaire radioamateur).
const CLE_SAISIE_DECOUPLEE = 'rc_saisie_decouplee';

// Lecture DÉFENSIVE : localStorage peut lever (navigation privée, quota,
// stockage bloqué par la politique du navigateur). En cas de doute on rend
// false, c'est-à-dire le comportement historique — jamais un découplage
// silencieux que l'opérateur n'aurait pas demandé.
function saisieDecoupleeActive(){
  try { return localStorage.getItem(CLE_SAISIE_DECOUPLEE) === '1'; }
  catch(e){ return false; }
}

function basculerSaisieDecouplee(){
  const neuf = !saisieDecoupleeActive();
  try { localStorage.setItem(CLE_SAISIE_DECOUPLEE, neuf ? '1' : '0'); }
  catch(e){ /* stockage indisponible : la bascule ne tiendra pas, tant pis —
               mieux vaut un bouton sans effet qu'une exception qui casse le
               reste du gestionnaire de clic. */ }
  majBoutonSaisieDecouplee();
}

const _ICO_RADIO_LIEE = '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="14" height="9" rx="1.3"/><line x1="4.5" y1="7" x2="8" y2="2"/><circle cx="6" cy="11.5" r="1.6"/><line x1="10" y1="10.5" x2="14" y2="10.5"/></svg>';
const _ICO_RADIO_LIBRE = '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="14" height="9" rx="1.3"/><line x1="4.5" y1="7" x2="8" y2="2"/><circle cx="6" cy="11.5" r="1.6"/><line x1="10" y1="10.5" x2="14" y2="10.5"/><line x1="2" y1="16" x2="16" y2="2"/></svg>';

// Le groupe entier est masqué sans CAT : sans radio pilotée il n'y a rien à
// découpler. L'ÉTAT, lui, est conservé — masquer n'est pas remettre à zéro.
function majBoutonSaisieDecouplee(){
  const grp = document.getElementById('posteSourceGroup');
  const btn = document.getElementById('posteSourceBtn');
  const ico = document.getElementById('posteSourceIco');
  const lab = document.getElementById('posteSourceLabel');
  const note = document.getElementById('posteSourceNote');
  if(!grp || !btn || !ico || !lab || !note) return;
  const catOn = (typeof rigState !== 'undefined') && rigState && rigState.enabled;
  grp.style.display = catOn ? '' : 'none';
  if(!catOn) return;
  const libre = saisieDecoupleeActive();
  btn.classList.toggle('decouple', libre);
  btn.setAttribute('aria-pressed', libre ? 'true' : 'false');
  // Icône par innerHTML (du SVG), libellé par textContent : mélanger les deux
  // sur le MÊME élément est le piège qui a effacé une icône en silence sur le
  // bouton QTC (voir CLAUDE.md). Ici l'icône a son span, le texte le sien.
  ico.innerHTML = libre ? _ICO_RADIO_LIBRE : _ICO_RADIO_LIEE;
  lab.textContent = libre ? 'AUTRE POSTE' : 'RADIO PILOTÉE';
  note.textContent = libre
    ? 'Ce que tu saisis ne touche plus la radio pilotée, et elle ne change '
      + 'plus ta bande ni ton mode. Pour noter un QSO fait sur un poste que '
      + 'le PC ne commande pas.'
    : 'La bande et le mode suivent la radio, et la pilotent quand tu les '
      + 'changes. Clique si ce QSO a été fait sur un autre poste.';
  btn.title = libre
    ? 'Saisie découplée de la radio — clique pour la relier à nouveau'
    : 'Saisie reliée à la radio — clique si ce QSO vient d\'un autre poste';
}

function _qsyVersRadio(){
  const rig = (typeof rigState !== 'undefined') ? rigState : {};
  if(!rig.enabled) return;
  // Le QSO en cours vient d'un poste que le PC ne commande pas : la saisie ne
  // doit RIEN envoyer à la radio pilotée. Placé avant tout calcul, et avant
  // _puissanceAutoVersRadio() en fin de fonction — qui écrirait sinon la
  // puissance TX de la radio pilotée d'après le mode d'un QSO fait ailleurs.
  if(saisieDecoupleeActive()) return;
  // Fréquence : celle déjà affichée dans le champ FRÉQUENCE (fréquence radio en
  // direct, saisie manuelle, ou valeur par défaut de la bande posée par
  // setFreqForBand() juste avant cet appel) — jamais une fréquence "magique"
  // par mode : la clause de repli du bug remonté ("elle devrait au moins
  // changer de mode") dit explicitement que changer le MODE sans déplacer la
  // fréquence est un correctif valable, alors qu'inventer une fréquence
  // d'appel par mode et par bande relève du plan de bande (variable selon
  // règlement/région) — hors de portée sûre d'un simple correctif CAT.
  const fEl = document.getElementById('inputFreq');
  const mhz = fEl ? parseFloat(fEl.value) : NaN;
  const freqKhz = (isFinite(mhz) && mhz > 0) ? Math.round(mhz * 1000)
                : (BAND_FREQ[currentBand] ? Math.round(parseFloat(BAND_FREQ[currentBand]) * 1000) : 0);
  if(!freqKhz) return;
  fetch('/rig/qsy', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({freq_khz: freqKhz, mode: currentMode})
  }).catch(()=>{});
  _puissanceAutoVersRadio();
}

// Puissance TX automatique par mode (protection du final en numérique) —
// réglage CONFIG > RADIO, DÉSACTIVÉ PAR DÉFAUT (aucun changement de
// comportement tant que l'opérateur ne l'a pas coché explicitement, voir
// CLAUDE.md section Intuitivité).
//
// La règle elle-même — table des modes numériques, clés de configuration,
// replis sûrs — vit maintenant dans concours/logx_puissance_auto.js, parce
// qu'elle doit servir AUSSI à la page FT8 : c'est elle qui émet réellement en
// FT8, et elle n'appliquait donc aucune protection. Deux copies de la table
// divergeraient au premier mode ajouté, en silence — un mode oublié d'un côté
// ne lève aucune erreur, il laisse simplement passer la pleine puissance.
function _puissanceAutoVersRadio(){
  if(typeof appliquerPuissanceAuto !== 'function') return;
  appliquerPuissanceAuto(currentMode);
}

function pickBand(band, opts){
  opts = opts || {};
  currentBand = band;
  _setCurrentBandLabel(band);
  hideBandPicker();
  setFreqForBand(currentBand);
  updateSerialDisplay();
  if(typeof refreshBandMap === 'function') refreshBandMap();  // spots de la nouvelle bande
  if(!opts.fromRig) _qsyVersRadio();   // choix manuel -> pilote la radio (voir commentaire ci-dessus)
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

// RST vs RS : en CW/RTTY/numérique le rapport officiel est à 3 chiffres
// (R + S + TONALITÉ, ex. « 599 ») ; en phonie (SSB/FM/AM) il n'a que 2
// chiffres (R + S, ex. « 59 ») — la tonalité n'a pas de sens sur une voix.
// Signalé par F4GLD (14/08/2026) : le champ restait figé sur « 59 » quel
// que soit le mode choisi.
const RST_MODES_3_CHIFFRES = ['CW', 'RTTY', 'FSK', 'FT8', 'FT4', 'PSK', 'PSK31',
  'JS8', 'MSK144', 'Q65', 'JT65', 'DIGITAL', 'DATA'];
function _rstParDefaut(mode){
  return RST_MODES_3_CHIFFRES.includes((mode || '').toUpperCase()) ? '599' : '59';
}
// N'écrase QUE si le champ contient encore une valeur par défaut non
// modifiée (« 59 » ou « 599 ») — jamais un rapport déjà saisi par l'opérateur.
function _adapterRSTAuMode(mode){
  const defaut = _rstParDefaut(mode);
  ['inputRSTsent', 'inputRSTrcvd'].forEach(function(id){
    const el = document.getElementById(id);
    if(el && (el.value === '59' || el.value === '599')) el.value = defaut;
  });
}

function pickMode(mode, opts){
  opts = opts || {};
  currentMode = mode;
  _setCurrentModeLabel(mode);
  hideModePicker();
  _adapterRSTAuMode(mode);
  if(!opts.fromRig){
    _qsyVersRadio();   // choix manuel -> pilote la radio (voir commentaire au-dessus de pickBand)
    // Mise à jour OPTIMISTE de rigState.mode, ICI et pas dans _qsyVersRadio()
    // (pickBand() aussi appelle _qsyVersRadio(), pour une bande seule -- y
    // remettre rigState.mode à currentMode à CE moment-là écraserait à tort
    // un mode radio réel encore inconnu/différent lors d'un simple
    // changement de bande, sans intention de mode de l'opérateur : régression
    // trouvée par tests/test_macro_cw_serie_bande.py, qui force rigState.mode
    // indépendamment de currentMode pour simuler une radio déjà en CW).
    // updateKeyerPanels() (panneau décodeur CW) et esmSend() (routage
    // CW/vocal de l'ESM, logx_esm_callbot.js) priorisent tous deux
    // rigState.mode sur currentMode dès qu'il est NON VIDE -- sans cette
    // ligne, choisir CW ici laisserait le panneau décodeur CW calé sur
    // l'ANCIEN mode radio (ex. USB) pendant tout le délai jusqu'au prochain
    // sondage matériel (adaptivePoll, jusqu'à ~3-4 s) : exactement le
    // symptôme « je suis en CW dans LOGBOOK mais le décodeur CW n'apparaît
    // plus » remonté par F4GLD (15/08/2026, lié au même bug que ce
    // correctif -- le mode manuel ne pilotait jamais la radio, donc
    // rigState.mode restait bloqué sur le vrai mode radio, resté inchangé
    // lui aussi). Le prochain sondage confirmera (ou corrigera, si la
    // commande a échoué) cette valeur.
    rigState.mode = mode;
  }
  // Appelée APRÈS la mise à jour optimiste ci-dessus (quand elle a lieu) :
  // lire rigState.mode AVANT l'aurait rouvert le même symptôme.
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
const ALL_BANDS = ['1.8','3.5','7','10.1','14','18','21','24','28','50','70','144','432','1296','2320','3400','5760','10368','24048','47088'];

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

// BAND_TOGGLE_KEY/MODE_TOGGLE_KEY/_resolveContestFilters() viennent de
// logx_contest_rules.js (partagé avec logx_configuration.js), chargé avant
// ce fichier — ne pas les redéclarer ici (collision de `const`).

// Bandes autorisées par concours, résolues via _resolveContestFilters()
// (logx_contest_rules.js), qui connaît les VRAIES clés d'édition (REF_CCD_JAN1,
// REF_MARCONI, REF_DDFM_50, REF_IARU_50...). Avant ce correctif (22/08/2026,
// chantier « page d'accueil par activité »), une table locale ne couvrait que
// des clés génériques (REF_CCD, REF_IARU_VHF...) absentes du catalogue réel —
// le sélecteur retombait sur ALL_BANDS (bandes HF comprises) pour la
// quasi-totalité des concours V/UHF réels. Table inverse triviale, clé toggle
// → valeur MHz (le sens contraire de BAND_TOGGLE_KEY).
const TOGGLE_KEY_TO_BAND = Object.fromEntries(
  Object.entries(BAND_TOGGLE_KEY).map(([mhz, key]) => [key, mhz])
);
function _bandsForContest(contest){
  const filters = _resolveContestFilters(contest);
  if (!filters || !filters.bands) return null;   // axe libre (CUSTOM, POTA/SOTA...) → repli ALL_BANDS
  return filters.bands.map(k => TOGGLE_KEY_TO_BAND[k]).filter(Boolean);
}

// Activité choisie sur logx_accueil.html (localStorage.logx_activity) --
// lecture minuscule et locale à ce fichier, pas partagée via
// logx_contest_rules.js : ce n'est pas une donnée de règlement de concours,
// juste un repli d'affichage pour le QSO occasionnel hors concours ci-dessous.
function _activiteEstVuhf(){
  try{ return localStorage.getItem('logx_activity') === 'vuhf'; }catch(e){ return false; }
}
// QSO occasionnel (hors concours) en activité V/UHF : 2 m/70 cm/23 cm « et ça
// suffit » (doctrine CLAUDE.md, retour F4GLD 22/08/2026) -- plutôt que
// ALL_BANDS (HF compris) quand aucun concours ne restreint rien. Reste
// filtrable comme les autres par les cases à cocher CONFIG (band_2m/70cm/23cm).
const VUHF_ACTIVITY_DEFAULT_BANDS = ['144', '432', '1296'];

// Bandes actuellement autorisées (concours + toggles) — utilisé par
// onFreqInput() pour valider une bascule automatique de bande, et par le
// popup de choix de bande (#bandPickerPopup) pour lister les alternatives.
let _currentVisibleBands = [];

function renderBandButtons(contest){
  // Bandes du concours (résolues via logx_contest_rules.js), filtrées par
  // les toggles de configuration
  const contestBands = _bandsForContest(contest)
    || (_activiteEstVuhf() ? VUHF_ACTIVITY_DEFAULT_BANDS : ALL_BANDS);

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

// Lien profond PROPAG (nav, .app-nav) : ouvre logx_propagation.html
// directement sur l'onglet BANDE ACTUELLE (« tout ce que le programme sait
// de la bande en cours : cluster, ouvertures, carrés à reprendre »), pré-
// réglé sur la bande EN COURS DE SAISIE ici plutôt que le dernier onglet
// consulté sur cette autre page — retour F4GLD 22/08/2026 (« lien profond
// propag »). `?band=` est lu en PRIORITÉ sur localStorage.rc_focus_band côté
// logx_propagation.html (voir ce fichier) : ne touche donc pas la
// préférence propre de cette page. Référencée par un typeof-guard dans
// .app-nav (motif déjà établi ailleurs, ex. rigState dans
// logx_esm_callbot.js) : la nav est identique sur 10 pages, seule celle-ci
// connaît `currentBand`.
function _navPropagContextuel(ev){
  if(ev) ev.preventDefault();
  window.location.href = 'logx_propagation.html?band=' + encodeURIComponent(currentBand) + '#propPane-focus';
}

// Correspondance mode affiché → clé toggle configuration
//
// Chaque mode qui a SA case en configuration pointe sur SA propre clé. Les
// rattachements (plusieurs modes → une seule clé) ne concernent que les codes
// de règlement SANS case dédiée : DIGI et FT2. C'est la règle à suivre pour
// tout ajout — un rattachement sur une clé qui existe par ailleurs rend la
// case correspondante inopérante, exactement le défaut corrigé le 18/08/2026
// pour JS8 / PSK / AM / D-STAR (4 cases présentes en configuration depuis
// l'origine, mais absentes d'ici : les cocher ne produisait aucun bouton, et
// PSK rattaché à mode_rtty faisait en plus décocher la case PSK au WWA alors
// que son règlement §5 autorise explicitement ce mode).
// MODE_TOGGLE_KEY vient désormais de logx_contest_rules.js (partagé avec
// logx_configuration.js, chargé avant ce fichier) — ne pas la redéclarer ici.

// Modes actuellement autorisés (concours + toggles) — utilisé par
// syncBandModeFromRig() (logx_hardware_cat.js) pour valider une bascule
// automatique de mode déclenchée par un changement fait SUR la radio, même
// principe que _currentVisibleBands pour les bandes.
let _currentVisibleModes = [];

function renderModeButtons(contest){
  const allModes = CONTEST_MODES[contest] || ['SSB','CW','FM','FT8'];
  // Modes affichés = modes explicitement activés par l'utilisateur en config,
  // sans se limiter à la liste par défaut du concours (ex: FT8 coché doit
  // apparaître même si le règlement du concours ne le propose pas par défaut).
  let cfgLocal = {};
  try{ cfgLocal = JSON.parse(localStorage.getItem('logx_config')||'{}'); }catch(e){}
  const toggles = cfgLocal.toggles || {};
  const hasModeTgls = Object.keys(toggles).some(k => k.startsWith('mode_'));
  // SSTV, AM, JS8, PSK et D-STAR n'apparaissent QUE si leur case est cochée en
  // configuration : aucun concours ne les propose par défaut, ce sont des modes
  // d'activité (dimanches SSTV/ISS, AM en trafic courant, D-STAR en relais).
  // Liste dérivée de MODE_TOGGLE_KEY, dont on écarte les codes de règlement
  // sans case dédiée (DIGI, FT2) qui feraient double emploi avec FT8 — ainsi
  // un mode ajouté à la table plus haut apparaît ici sans autre modification,
  // au lieu de rester invisible faute d'avoir pensé à cette 2e liste.
  const SANS_CASE_DEDIEE = ['DIGI', 'FT2'];
  const modes = hasModeTgls
    ? Object.keys(MODE_TOGGLE_KEY)
        .filter(m => !SANS_CASE_DEDIEE.includes(m))
        .filter(m => toggles[MODE_TOGGLE_KEY[m]] === true)
    : allModes;
  const finalModes = modes.length > 0 ? modes : allModes; // sécurité: tout afficher si rien de coché
  _currentVisibleModes = finalModes;
  const popup = document.getElementById('modePickerPopup');
  if(popup){
    popup.innerHTML = finalModes.map((m,i)=>
      `<button class="bm-btn${i===0?' active':''}" data-val="${m}" onclick="pickMode('${m}')">${m}</button>`
    ).join('');
  }
  currentMode = finalModes[0];
  _setCurrentModeLabel(currentMode);
  _adapterRSTAuMode(currentMode);
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
  // Reprendre la frappe rend obsolète un bandeau de confirmation doublon resté
  // ouvert d'une tentative précédente (chantier 2, audit accessibilité).
  if(typeof _cancelPendingDupConfirm === 'function') _cancelPendingDupConfirm();

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

// WIDGET TIME OF DAY (jour/nuit) + SAISIE/VALIDATION CHAMP LOCATOR :
// extrait vers logx_daynight.js (EV-7 phase 2, 18e increment,
// docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

function focusNext(id){
  document.getElementById(id)?.focus();
  document.getElementById(id)?.select();
}

// ─── BANDEAU DE CONFIRMATION DOUBLON (non bloquant) ──────────────────────────
// Remplace les dialogues confirm() natifs de submitQSO() (chantier 2, audit
// accessibilité 09/08/2026). Un tel dialogue gèle toute la page tant qu'on ne
// l'a pas fermé, et déplace le focus vers une boîte système hors du contrôle
// de l'app — gênant en pleine cadence de saisie (pile-up). Ce bandeau reste
// dans la page (le reste de l'UI reste utilisable), a de vrais <button>
// (tabulables, activables au clavier), et ne force jamais le focus hors du
// champ où l'opérateur se trouve : seul un clic ou une tabulation volontaire
// de l'opérateur l'atteint.
let _pendingDupConfirmResolve = null;

// yesLabel/noLabel : le bandeau est partagé par TOUTE la page logx_logbook.html
// (dup_finder, edit_qso, qtc, verif_panel, net_control, popout_selfspot,
// outils_autonomes, hardware_cat, export_adif, export_edi, bulk_resolve --
// un seul bandeau visible à la fois, cf. _cancelPendingDupConfirm ci-dessous),
// pas seulement le doublon QSO d'origine -- les libellés par défaut
// reproduisent exactement le comportement historique pour ne rien changer au
// seul appelant qui ne les précise pas (submitQSO()).
function _confirmDupBanner(message, yesLabel, noLabel){
  _cancelPendingDupConfirm();   // un bandeau resté ouvert d'une tentative précédente ne doit pas s'empiler
  return new Promise(resolve => {
    _pendingDupConfirmResolve = resolve;
    document.getElementById('dupConfirmMsg').textContent = message;
    document.getElementById('dupConfirmYesBtn').textContent = yesLabel || 'Enregistrer quand même';
    document.getElementById('dupConfirmNoBtn').textContent = noLabel || 'Annuler';
    document.getElementById('dupConfirmBanner').classList.add('show');
  });
}

function _resolveDupConfirm(result){
  document.getElementById('dupConfirmBanner').classList.remove('show');
  if(_pendingDupConfirmResolve){
    const r = _pendingDupConfirmResolve;
    _pendingDupConfirmResolve = null;
    r(result);
  }
}

// Appelé quand l'opérateur reprend la frappe (nouvel indicatif) sans avoir
// répondu au bandeau -- évite qu'une confirmation devienne obsolète/orpheline
// pendant qu'un autre QSO est en cours de saisie.
function _cancelPendingDupConfirm(){
  if(_pendingDupConfirmResolve) _resolveDupConfirm(false);
}

// Le locator correspondant est-il un champ OBLIGATOIRE (pas juste une donnée
// utile) pour le concours actif ? Uniquement les barèmes qui calculent des
// points à la distance (per_km -- km/km_x_locators/km_x_large_locator_squares,
// et tout barème serveur custom qui s'appuie sur la même brique) : sans
// locator, calcPoints() renvoie 0 pt de façon certaine, ce n'est donc pas une
// simple perte de confort comme pour un concours à points fixes. Dérivé du
// même barème serveur que calcPoints()/evalPointsFromDef() -- aucune liste
// de concours à maintenir à part.
function contestRequiresLocator(){
  if(!currentContest) return false;
  const def = contestScoringDefs[currentContest];
  if(!def) return false;
  const bricks = def.bricks || LEGACY_JS_BRICKS[def.type];
  return !!(bricks && Array.isArray(bricks.points) && bricks.points.some(r => r.points === 'per_km'));
}

// Aligne l'id du QSO local sur celui que le SERVEUR a réellement attribué.
// L'id proposé par le client (Date.now()) n'est qu'une suggestion : en cas de
// collision, reserve_qso_id_locked() (logx_http.py) en choisit un autre et,
// jusqu'à ce correctif, ne le disait pas. Le carnet client repartait alors avec
// un id qui n'existait nulle part côté serveur.
//
// Tolérant par conception : une réponse illisible, sans champ `id`, ou un
// serveur plus ancien laissent simplement l'id proposé en place — c'est le
// comportement d'avant, jamais une exception qui ferait échouer l'enregistrement
// d'un QSO déjà accepté par le serveur.
async function _adopterIdServeur(res, qso){
  try{
    const d = await res.json();
    if(d && d.id !== undefined && d.id !== null) qso.id = d.id;
  }catch(e){ /* réponse non JSON : on garde l'id proposé, comme avant */ }
}

// Collecte les champs SECONDAIRES des onglets de saisie (lot 2, sous-chantier A).
// Chaque valeur NON VIDE devient une clé du QSO — persistée telle quelle via le
// schéma ouvert de logx_storage (`extra`) ; l'export ADIF est le sous-chantier B.
// `tx_pwr` est converti en NOMBRE ; les autres restent des chaînes.
function collectExtraFields(){
  const out = {};
  const val = function(id){ const e = document.getElementById(id); return e ? String(e.value).trim() : ''; };
  const map = {
    inputEmail:'email', inputQslVia:'qsl_via', inputCqz:'cqz', inputItuz:'ituz',
    inputCnty:'cnty', inputPropMode:'prop_mode', inputOperatingLocation:'operating_location',
    inputFreqRx:'freq_rx', inputTimeOff:'time_off', inputMyRig:'my_rig', inputMyAntenna:'my_antenna',
  };
  Object.keys(map).forEach(function(id){ const v = val(id); if(v) out[map[id]] = v; });
  const pwr = val('inputTxPwr');
  if(pwr) out.tx_pwr = Number(pwr);
  return out;
}

// ── Références multiples (lot 3, sous-chantier A) ───────────────────────────
// Une activation peut cumuler plusieurs programmes (SOTA + POTA « two-fer ») :
// on stocke une LISTE {program, ref}. Rétro-compat mono-valué : la 1re ref reste
// my_sig/my_sig_info (ce que l'export ADIF actuel émet, tant que B ne généralise
// pas). mySigToRefs : reconstruit la liste depuis my_sig (à l'ÉDITION d'un vieux
// QSO). refsToMySig : recopie my_refs[0] -> my_sig (avant ENVOI/export).
function mySigToRefs(q){
  if((!q.my_refs || !q.my_refs.length) && q.my_sig){ q.my_refs = [{program:q.my_sig, ref:q.my_sig_info||''}]; }
  if((!q.refs || !q.refs.length) && q.sig){ q.refs = [{program:q.sig, ref:q.sig_info||''}]; }
  return q;
}
function refsToMySig(q){
  if(q.my_refs && q.my_refs.length){ q.my_sig = q.my_refs[0].program; q.my_sig_info = q.my_refs[0].ref; }
  if(q.refs && q.refs.length){ q.sig = q.refs[0].program; q.sig_info = q.refs[0].ref; }
  return q;
}
// Programmes proposés : source = logx_activation.PROGRAM_SPECS (jamais de mémoire).
const REF_PROGRAMS = ['POTA','SOTA','WWFF','IOTA','WCA','ARLHS'];
function collectRefs(containerId){
  const box = document.getElementById(containerId);
  if(!box) return [];
  const out = [];
  box.querySelectorAll('.ref-row').forEach(function(row){
    const prog = row.querySelector('.ref-prog');
    const ref = row.querySelector('.ref-val');
    const p = prog ? String(prog.value).trim() : '';
    const v = ref ? String(ref.value).trim().toUpperCase() : '';
    if(p && v) out.push({program:p, ref:v});
  });
  return out;
}
function addRefRow(containerId){
  const box = document.getElementById(containerId);
  if(!box) return;
  const row = document.createElement('div');
  row.className = 'ref-row';
  const opts = REF_PROGRAMS.map(function(p){ return '<option value="'+p+'">'+p+'</option>'; }).join('');
  row.innerHTML = '<select class="field-input field-compact ref-prog refdrop">'+opts+'</select>'+
    '<input type="text" class="field-input field-compact ref-val" placeholder="réf. (F/AB-123, FR-1234…)" autocomplete="off">'+
    '<button type="button" class="ref-del" title="Retirer cette référence">✕</button>';
  row.querySelector('.ref-del').addEventListener('click', function(){ row.remove(); });
  box.appendChild(row);
}

async function submitQSO(){
  const call = document.getElementById('inputCall').value.trim().toUpperCase();
  const rstSent = document.getElementById('inputRSTsent').value.trim() || _rstParDefaut(currentMode);
  const rstRcvd = document.getElementById('inputRSTrcvd').value.trim() || _rstParDefaut(currentMode);
  const numRcvdRaw = document.getElementById('inputNumRcvd').value.trim();
  const numRcvd = (currentExchange.pad_r === true && numRcvdRaw)
    ? String(parseInt(numRcvdRaw, 10) || 0).padStart(3, '0')
    : numRcvdRaw;
  const loc     = document.getElementById('inputLocator').value.trim().toUpperCase();
  const freq    = (document.getElementById('inputFreq')?.value || '').trim();

  // Seuls deux champs sont réellement indispensables à TOUT QSO : l'indicatif
  // et la fréquence (la bande en est déjà déduite automatiquement, voir
  // onFreqInput()/bandFromFreq() -- rien à valider ici, currentBand est déjà
  // à jour au moment de la soumission).
  if(!call){
    document.getElementById('inputCall')?.focus();
    notify('Indicatif manquant !');
    return;
  }
  if(!freq){
    document.getElementById('inputFreq')?.focus();
    notify('Fréquence manquante !');
    return;
  }
  if(loc && !validateLocator(loc)){
    document.getElementById('inputLocator').focus();
    notify('Locator invalide !\nFormat attendu : AA00AA  (ex: JN03QQ)');
    return;
  }
  // Locator vide : obligatoire pour les concours notés à la distance (sans
  // lui, calcPoints() renvoie 0 pt à coup sûr -- pas question de laisser
  // enregistrer un QSO qu'on sait déjà nul) ; simple avertissement sinon, le
  // QSO est quand même enregistré (0 pt). En mode expédition le champ est
  // masqué : pas d'avertissement, on enchaîne.
  if(!loc && !expeditionMode){
    if(contestRequiresLocator()){
      document.getElementById('inputLocator').focus();
      notify('⚠️ Locator obligatoire pour ce concours (score calculé à la distance) !');
      return;
    }
    notify('⚠️ Locator non renseigné !\nLe QSO va être enregistré sans locator (0 pt).');
  }

  // Vérification doublon — hors concours (logbook simple), recontacter la
  // même station sur la même bande au fil des années est normal, pas une erreur.
  if(usageMode !== 'simple' && isDup(call, currentBand, currentMode)){
    if(!(await _confirmDupBanner(trF('⚠️ {call} est déjà dans le log sur {band} MHz — enregistrer quand même ?', {call, band: currentBand})))) return;
  }

  // N° envoyé : auto-série (VHF) ou valeur du champ (FD classe, CQ WW zone, HF dept...)
  const numSentField = document.getElementById('inputNumSent').value.trim();
  const serial = currentExchange.auto_serial ? await nextSerial(currentBand) : numSentField;
  const dist = (loc && loc.length >= 6) ? calcDist(loc) : 0;
  const pts  = calcPoints(loc, currentBand, call, currentMode);

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
    // Commentaire libre : le seul de ces trois champs que l'annuaire ne peut
    // pas deviner. C'est ce qu'on relit six mois plus tard (« antenne
    // filaire », « premier QSO en CW », « QSL directe promise »).
    comment: (document.getElementById('inputComment')?.value || '').trim(),
    // Nom et QTH de l'annuaire : ils étaient récupérés, affichés à la frappe,
    // puis JETÉS ici même. callbookPourQso() les rend UNIQUEMENT s'ils
    // concernent l'indicatif effectivement enregistré (l'opérateur a pu
    // effacer et retaper depuis la consultation).
    // Aucun changement serveur n'est nécessaire : logx_storage range tout
    // champ hors colonnes structurées dans `extra` (voir son commentaire
    // ligne 34). L'export ADIF, lui, a fallu l'étendre — sans quoi la donnée
    // aurait été stockée mais absente du fichier remis à l'opérateur.
    ...(typeof callbookPourQso === 'function' ? callbookPourQso(call) : {}),
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

  // Champs secondaires des onglets (lot 2, sous-chantier A) : puissance, e-mail,
  // QSL via, zones, comté, prop_mode, lieu d'exploitation, fréq RX, heure de fin,
  // matériel, antenne. Fusionnés APRÈS l'activation pour ne rien écraser d'établi.
  Object.assign(qso, collectExtraFields());

  // Références multiples (lot 3) : la ref d'activation (my_sig, posée ci-dessus)
  // devient la 1re d'une LISTE, complétée par les références SUPPLÉMENTAIRES
  // saisies dans l'onglet (two-fer SOTA+POTA). refsToMySig garde ensuite
  // my_sig = my_refs[0] pour que l'export ADIF actuel reste identique.
  mySigToRefs(qso);
  const _myExtra = collectRefs('myRefsList');
  if(_myExtra.length) qso.my_refs = (qso.my_refs || []).concat(_myExtra);
  const _theirExtra = collectRefs('refsList');
  if(_theirExtra.length) qso.refs = (qso.refs || []).concat(_theirExtra);
  refsToMySig(qso);

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
      // Adopter l'id RÉELLEMENT attribué par le serveur AVANT le push : l'id
      // proposé ici (Date.now()) peut entrer en collision avec un QSO déjà
      // présent — typiquement juste après un import ADIF, dont les id sont
      // alloués en série à partir de l'horloge. reserve_qso_id_locked()
      // (logx_http.py) le remplace alors sans rien dire.
      // Sans cette ligne, le carnet client gardait un id fantôme : la fusion
      // delta de /log/list (indexById plus bas) ajoutait le QSO une SECONDE
      // fois, et undoLastQSO() (logx_edit_qso.js) envoyait
      // /log/delete/<id périmé> — supprimant un QSO du carnet historique
      // pendant que le QSO à annuler restait en place.
      await _adopterIdServeur(res, qso);
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
      // dupe assumé pour l'arbitre...) — bandeau non bloquant, pas de
      // confirm() natif (chantier 2, audit accessibilité 09/08/2026).
      const err = await res.json();
      const ex = err.existing || {};
      // Correctif passe de vérification (09/08/2026) : pour un concours à
      // réinitialisation quotidienne du doublon (WWA...), le serveur ne
      // signale plus 409 que pour un contact du MÊME JOUR (voir _find_dup()
      // dans logx_http.py) -- mais sans la date affichée ici, l'opérateur
      // ne pouvait pas distinguer "doublon aujourd'hui" (vrai doublon) d'un
      // vieux contact d'il y a des semaines, et pouvait renoncer à tort à
      // un QSO en réalité valide. fmtDate() vient de logx_callbook.js
      // (chargé avant ce fichier, portée globale partagée).
      const datePart = ex.date ? trF(' le {d}', {d: fmtDate(ex.date)}) : '';
      const atPart = ex.time ? trF(' à {t}', {t: ex.time}) : '';
      const byPart = ex.operator ? trF(' par {op}', {op: _resolveOperatorCallsign(ex.operator)}) : '';
      if(await _confirmDupBanner(trF('DOUBLON : {call} déjà contacté sur {band} MHz en {mode}{date}{at}{by} — enregistrer quand même ?',
                 {call: qso.call, band: qso.band, mode: qso.mode, date: datePart, at: atPart, by: byPart}))){
        const res2 = await fetch('/log/add', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({...qso, force:true})
        });
        if(res2.ok){
          // Même adoption d'id que sur le chemin nominal ci-dessus : un doublon
          // forcé est un QSO comme un autre côté serveur, il passe par la même
          // réservation d'id et court donc exactement le même risque.
          await _adopterIdServeur(res2, qso);
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
  document.getElementById('inputRSTsent').value = _rstParDefaut(currentMode);
  document.getElementById('inputRSTrcvd').value = _rstParDefaut(currentMode);
  document.getElementById('inputNumRcvd').value = '';
  document.getElementById('inputLocator').value = '';
  // Commentaire vidé comme les autres champs propres au QSO : le laisser
  // traînerait la remarque du contact précédent sur le suivant — pire qu'un
  // champ vide, puisque l'opérateur ne la relirait pas avant d'enregistrer.
  const _cm = document.getElementById('inputComment'); if(_cm) _cm.value = '';
  const _tr = document.getElementById('inputTheirRef'); if(_tr) _tr.value = '';
  setFreqForBand(currentBand);   // ré-affiche la fréquence d'appel/CAT de la bande
  document.getElementById('locHint').style.display = 'none';
  document.getElementById('dupWarn').classList.remove('show');
  document.getElementById('dupConfirmBanner').classList.remove('show');
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

// AUDIO BIP CONFIRMATION QSO (bipEnabled/initBipBtn/toggleBip) : extrait
// vers logx_outils_divers.js (EV-7 phase 2, 36e increment,
// docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

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
// A10 (docs/FEUILLE_DE_ROUTE.md) : score AUTORITAIRE (points × multiplicateurs
// distincts, logx_scoring.calc_total_score) reçu au dernier /log/list — le
// calcul LOCAL de updateStats() (somme des points par QSO, ci-dessous) ne
// tient jamais compte du multiplicateur, exactement le défaut qu'A05 avait
// déjà corrigé PAR QSO mais qui restait faux pour le TOTAL affiché. null
// tant qu'aucune réponse serveur n'est arrivée (page tout juste ouverte,
// hors-ligne) : repli sur le calcul local dans ce seul cas.
let _lastServerScore = null;

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

// BADGE VERSION RESEAU + MISE A JOUR VIA PASSERELLE/PAIR : extrait
// vers logx_version_badge.js (EV-7 phase 2, 35e increment,
// docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee. Les variables d'etat
// _myVersion/_lastServerVersion/_lastPeerList restent ICI (voir
// commentaire d'en-tete de logx_version_badge.js).

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

// ── PROPAGATION VOACAP (vrai moteur scientifique, cf. logx_voacap.py) ──────
// Point d'entrée léger : préremplit le DX depuis le champ indicatif en
// cours de saisie (#inputCall), jamais bloquant, jamais indispensable au
// chemin critique (bouton expert-only).
function openVoacapPanel(){
  const ov = document.getElementById('voacapOverlay');
  const dxField = document.getElementById('voacapDx');
  if(!ov || !dxField) return;
  const current = (document.getElementById('inputCall')||{}).value || '';
  dxField.value = current.trim().toUpperCase();
  ov.classList.add('show');
  document.getElementById('voacapInner').innerHTML = '';
  dxField.focus();
}

async function runVoacapCheck(){
  const inner = document.getElementById('voacapInner');
  const dx = (document.getElementById('voacapDx').value || '').trim();
  const mode = document.getElementById('voacapMode').value;
  const power = document.getElementById('voacapPower').value || '100';
  if(!dx){
    inner.innerHTML = '<div class="shortcuts-row"><span style="color:var(--red)">Indique un locator ou un indicatif</span></div>';
    return;
  }
  inner.innerHTML = '<div class="shortcuts-row"><span>⏳ Calcul VOACAP en cours (peut prendre quelques secondes)…</span></div>';
  let data;
  try{
    const res = await fetch(`/data/voacap?dx=${encodeURIComponent(dx)}&mode=${encodeURIComponent(mode)}&power=${encodeURIComponent(power)}`);
    data = await res.json();
  }catch(e){
    inner.innerHTML = '<div class="shortcuts-row"><span style="color:var(--red)">❌ Serveur injoignable</span></div>';
    return;
  }
  if(!data.ok){
    inner.innerHTML = `<div class="shortcuts-row"><span style="color:var(--red)">❌ ${escHtml(data.error||'Échec du calcul')}</span></div>`;
    return;
  }
  const relColor = (rel) => {
    if(rel == null) return 'var(--bg3)';
    if(rel >= 0.7) return 'var(--green)';
    if(rel >= 0.3) return 'var(--yellow)';
    if(rel > 0) return 'rgba(var(--accent-rgb),.35)';
    return 'var(--bg3)';
  };
  const hours = data.hours || [];
  const freqs = data.freqs_mhz || [];
  let head = '<div style="font-family:var(--font-mono);font-size:12px;color:var(--muted);margin-bottom:10px">'+
    `${data.distance_km} km · az ${data.azimuth_deg}° / retour ${data.back_azimuth_deg}° · SSN ${data.ssn} · ${data.month}/${data.year}`+
    '</div>';
  let table = '<table style="border-collapse:collapse;width:100%;font-family:var(--font-mono);font-size:11px">';
  table += '<tr><td style="padding:2px 4px;color:var(--muted)">MHz \\ h</td>' +
    hours.map(h=>`<td style="padding:2px 3px;text-align:center;color:var(--muted)">${h.hour}</td>`).join('') + '</tr>';
  freqs.forEach((f, fi) => {
    table += `<tr><td style="padding:2px 4px;color:var(--text)">${f}</td>`;
    hours.forEach(h => {
      const b = (h.bands||[])[fi] || {};
      const title = b.rel != null
        ? `${Math.round(b.rel*100)}% · SNR ${b.snr_db!=null?b.snr_db+' dB':'?'}${b.mode?' · '+b.mode:''}`
        : 'pas de donnée';
      table += `<td title="${title}" style="padding:3px;text-align:center;background:${relColor(b.rel)};border:1px solid var(--bg)">`+
        (b.rel != null ? Math.round(b.rel*100) : '·') + '</td>';
    });
    table += '</tr>';
  });
  table += '</table>';
  inner.innerHTML = head + table;
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
    // A10 : score autoritaire du serveur (points × multiplicateurs) —
    // toujours capturé, même sur une réponse 'delta', puisque le champ
    // 'score'/'total' du serveur porte déjà le LOG COMPLET, pas le delta
    // seul (voir commentaire logx_http.py:/log/list).
    if(data.score != null) _lastServerScore = data.score;
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

let _syncingOfflineQueue = false;
async function syncOfflineQueue(){
  // Verrou de réentrance : fetchLog() rappelle syncOfflineQueue() toutes les
  // 5s (setInterval) — si un /log/add prend plus de 5s à répondre, le tick
  // suivant relisait la MÊME file (encore non purgée) et renvoyait les mêmes
  // QSO en force:true (qui saute exprès la dédup côté serveur), les
  // dupliquant.
  if(_syncingOfflineQueue) return;
  let queue = [];
  try{ queue = JSON.parse(localStorage.getItem('rc_offline_queue')||'[]'); }catch(e){}
  if(!queue.length) return;
  _syncingOfflineQueue = true;
  try{
    const synced = [];
    for(const qso of queue){
      try{
        // force:true : ces QSO ont déjà été validés à la saisie (mode hors
        // ligne) — le contrôle de doublon ne doit pas les faire disparaître.
        const res = await fetch('/log/add', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({...qso, force:true})
        });
        if(res.ok){
          // Réaligner la copie du carnet local sur l'id réellement attribué.
          // La resynchronisation hors ligne est le cas le plus exposé à la
          // collision : tous les QSO de la file partent d'affilée, donc à
          // quelques millisecondes les uns des autres. Sans ça, le carnet
          // affiché gardait des id que le serveur n'a jamais retenus — et
          // « annuler » visait à côté (revue adversariale du lot, 18/08/2026).
          const d = await res.json().catch(() => null);
          if(d && d.id != null && d.id !== qso.id){
            const local = qsoLog.find(q => q.id === qso.id);
            if(local){ local.id = d.id; bcBroadcast('add', local); }
          }
          // synced garde l'id LOCAL : il sert à filtrer la file d'attente
          // ci-dessous, qui est indexée sur les id d'origine.
          synced.push(qso.id);
        }
      }catch(e){ break; } // serveur encore inaccessible
    }
    if(synced.length){
      const remaining = queue.filter(q => !synced.includes(q.id));
      localStorage.setItem('rc_offline_queue', JSON.stringify(remaining));
      console.log(`[SYNC] ${synced.length} QSO hors-ligne synchronisés`);
      document.getElementById('netStatus').textContent = `Connecté — ${synced.length} QSO hors-ligne resynchronisés`;
    }
  }finally{
    _syncingOfflineQueue = false;
  }
}

function backupLog(){
  if(!qsoLog.length) return;
  // Garde-fou client (miroir du _SEUIL_PERTE_MASSIVE serveur = 25) : ne pas
  // écraser le filet rc_log_backup avec un carnet BRUTALEMENT rétréci. fetchLog()
  // peut remplacer qsoLog par une liste complète PLUS COURTE (redémarrage /
  // boot-token périmé / chargement disque incomplet / perte massive) ; sans ce
  // contrôle, le tick suivant recopiait le carnet amputé PAR-DESSUS le backup
  // complet — le filet détruit précisément quand il sert.
  try{
    const prev = JSON.parse(localStorage.getItem('rc_log_backup') || 'null');
    if(Array.isArray(prev) && prev.length - qsoLog.length >= 25){
      console.warn('[backup] carnet rétréci de '+prev.length+' à '+qsoLog.length
        +' QSO — filet rc_log_backup PRÉSERVÉ (réponse serveur partielle ?)');
      return;
    }
  }catch(e){}
  const now = new Date();
  const hhmm = `${String(now.getUTCHours()).padStart(2,'0')}:${String(now.getUTCMinutes()).padStart(2,'0')}`;
  localStorage.setItem('rc_log_backup', JSON.stringify(qsoLog));
  localStorage.setItem('rc_log_backup_time', hhmm+' UTC');
  const el = document.getElementById('backupTime');
  if(el) el.textContent = `Backup: ${hhmm} UTC`;
}

// qsoLog reste [] tant que le 1er fetchLog() n'a pas abouti — si le réseau
// est indisponible au chargement (coupure /P), un rechargement de page
// faisait disparaître visuellement les QSO déjà loggués (pas de perte
// réelle — ils restent dans localStorage — mais un LOGBOOK qui semble vide
// pousse à ressaisir en double par panique). Repli : dernier backup complet
// (rc_log_backup, toutes les 5 min) fusionné avec la file hors-ligne pas
// encore synchronisée (rc_offline_queue, plus récente) — écrasé de toute
// façon dès que fetchLog() aboutit.
function _rehydrateQsoLogFromLocalStorage(){
  try{
    const backup = JSON.parse(localStorage.getItem('rc_log_backup')||'[]');
    if(!Array.isArray(backup) || !backup.length) return;
    let offline = [];
    try{ offline = JSON.parse(localStorage.getItem('rc_offline_queue')||'[]'); }catch(e2){}
    const byId = new Map(backup.map(q => [q.id, q]));
    for(const q of (Array.isArray(offline) ? offline : [])) byId.set(q.id, q);
    qsoLog = Array.from(byId.values());
    resetLogRenderWindow();
    renderLog();
  }catch(e){}
}

function startRefresh(){
  _rehydrateQsoLogFromLocalStorage();
  fetchLog();
  setInterval(fetchLog, 5000); // refresh toutes les 5 secondes
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
    const k = (x.call||'') + '|' + (x.band||'') + '|' + (x.mode||'');
    dupCounts.set(k, (dupCounts.get(k) || 0) + 1);
  });

  // `filtered` reste le résultat COMPLET du tri/filtre/recherche — seule la
  // tranche [0, logRenderLimit) part réellement dans le DOM (`visible`).
  const reversed = filtered.slice().reverse();
  const visible = reversed.slice(0, logRenderLimit);
  renderLogMoreBar(reversed.length - visible.length);

  if(!visible.length){
    // Log réellement vide (rien saisi) vs. filtre/recherche qui ne retourne
    // rien : deux causes différentes, deux messages différents (audit
    // intuitivité 13/08/2026 — un tableau blanc sans explication ressemble
    // à une page cassée, surtout pour un débutant qui vient de démarrer).
    const emptyMsg = qsoLog.length === 0
      ? 'Aucun QSO enregistré — remplis le formulaire ci-dessus et clique ENREGISTRER LE QSO.'
      : 'Aucun QSO ne correspond à ce filtre ou cette recherche.';
    tbody.innerHTML = `<tr><td colspan="13" style="text-align:center;padding:30px;color:var(--muted);font-family:var(--font-mono)">${emptyMsg}</td></tr>`;
    return;
  }

  tbody.innerHTML = visible.map((q,i)=>{
    const opColor = opColorAttr(q.operator);
    // LOGBOOK SIMPLE : retravailler un correspondant déjà eu (même indicatif +
    // même bande) est normal dans un log personnel — il n'y a pas de points à
    // perdre comme en concours. Barrer/griser la ligne dans ce cas n'indique
    // aucune erreur, ça rend juste illisible une vraie part de l'historique.
    const isDupQ = usageMode !== 'simple' && (dupCounts.get((q.call||'') + '|' + (q.band||'') + '|' + (q.mode||'')) || 0) > 1;
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
      <td class="td-op-col"><span class="td-op ${opColor.cls}" style="${opColor.style}">${escHtml(_resolveOperatorCallsign(q.operator))||'—'}</span></td>
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
// EV-7 : extrait vers logx_edit_qso.js (chargé en <script> classique avant ce
// fichier, même portée globale partagée). editQSO/saveEdit/deleteQSO/
// deleteQSOSilent/undoLastQSO + champs ADIF personnalisés y vivent désormais.

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
    const k = (q.call||'') + '|' + (q.band||'') + '|' + (q.mode||'');
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
      // q.my_locator (position réellement enregistrée AU MOMENT du QSO) —
      // sans ce repli, un rover/expédition changeant de locator en cours de
      // concours voyait tout son historique de score recalculé à tort avec
      // la position ACTUELLE (myLocator global).
      total += calcPoints(q.locator, q.band, q.call, q.mode, q.my_locator);
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
  // A10 : préférer le score AUTORITAIRE du serveur (points × multiplicateurs)
  // dès qu'il est connu — `total` (somme locale par QSO, ci-dessus) sous-
  // compte tout concours à multiplicateur (CQ WW, WPX, ARRL DX, REF...),
  // n'étant jamais mis à jour au-delà du 1er poll (page tout juste ouverte
  // ou hors-ligne).
  const scoreAffiche = _lastServerScore != null ? _lastServerScore : total;
  document.getElementById('sbTotal').textContent   = scoreAffiche.toLocaleString() + ' pts';
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

// ─── SOAPBOX PAR BANDE : extrait vers logx_soapbox.js (EV-7 phase 2,
// 29e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

// MACROS F1-F8 (DEFAULT_MACROS, getMacros/saveMacros, expandMacro,
// renderMacroPanel, copyMacro, editMacro) : extrait vers logx_macros.js
// (EV-7 phase 2, 32e increment, docs/LogX_AI_PRD.md) -- charge en
// <script> classique dans logx_logbook.html, portee globale partagee.
// Extraction NON CONTIGUE : voir l'en-tete de logx_macros.js -- les
// sections i18n et adaptivePoll() ci-dessous sont restees ici, dans le
// coeur, a leur emplacement d'origine.

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

// copyMacro() : extrait vers logx_macros.js avec le reste des MACROS
// F1-F8 (voir le pointeur plus haut) -- adaptivePoll() ci-dessous reste
// dans le coeur, sans rapport avec les macros.


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

// editMacro() : extrait vers logx_macros.js avec le reste des MACROS
// F1-F8 (voir le pointeur plus haut).


// ─── EXPORTS EDI + CABRILLO : extrait vers logx_export_edi.js (EV-7 phase 2,
// 25e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

// EXPORT ADIF + CSV : extrait vers logx_export_adif.js (EV-7 phase 2,
// 23e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique
// dans logx_logbook.html, portee globale partagee.

// RESOLUTION D'INDICATIF (HamQTH distant, cache cluster, calldb,
// autocomplete) : extrait vers logx_lookup.js (EV-7 phase 2, 17e
// increment, docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

// REVERSE LOOKUP LOCATOR -> INDICATIFS + COMPAS INLINE : extrait vers
// logx_locator_reverse.js (EV-7 phase 2, 21e increment,
// docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

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

// DECODEUR CW #2 (audio, wrappers toggleCwPanel*/loadAudioInputDevices/
// loadAudioOutputDevices) : extrait vers logx_cw_panel2_audio.js (EV-7
// phase 2, 30e increment, docs/LogX_AI_PRD.md) -- charge en <script>
// classique dans logx_logbook.html, portee globale partagee.

// ─── TX AUDIO GÉNÉRIQUE RTTY/SSTV : extrait vers logx_tx_audio.js (EV-7
// phase 2, 27e increment, docs/LogX_AI_PRD.md) -- charge en <script>
// classique dans logx_logbook.html, portee globale partagee.

// TOGGLE JOUR/NUIT + RACCOURCIS CLAVIER GLOBAUX : extrait vers
// logx_theme_shortcuts.js (EV-7 phase 2, 22e increment,
// docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

// ─── PRÉREMPLISSAGE MODAL + NOMS OPÉRATEURS ──────────────────────────────────
function prefillSetupFromConfig(){
  let cfg = {};
  try{ cfg = JSON.parse(localStorage.getItem('logx_config')||'{}'); }catch(e){}

  applyUsageModeToLogbook(cfg.usage_mode);

  // Pré-remplir indicatif et locator
  const callEl  = document.getElementById('setupCallsign');
  const locEl   = document.getElementById('setupLocator');
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
      const lbl = call ? `${escHtml(val)} — ${escHtml(call)}${op.name?' ('+escHtml(op.name)+')':''}` : escHtml(val);
      opEl.innerHTML += `<option value="${escHtml(val)}">${lbl}</option>`;
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
  // Colonne OP du tableau de QSO : même logique, un seul opérateur rend la
  // colonne redondante (bruit visuel). Classe posée sur le conteneur du
  // tableau plutôt que sur chaque <td> (régénérés à chaque renderLog()) —
  // masquage CSS pur, cf. règle .single-op-mode .th-op-col/.td-op-col.
  const logTableWrap = document.getElementById('logTableWrap');
  if(logTableWrap) logTableWrap.classList.toggle('single-op-mode', isSingleOp);
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

// RACCOURCI BUREAU (bandeau premier lancement) : extrait vers
// logx_shortcut_offer.js (EV-7 phase 2, 34e increment,
// docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

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
      // N'écrase le champ QUE s'il n'est pas en train d'être utilisé — sinon
      // un clic sur le panadapter pendant la frappe manuelle d'un indicatif
      // effaçait silencieusement ce que l'opérateur était en train de taper.
      if(call && inp && (document.activeElement !== inp || !inp.value)){
        inp.value = call; onCallInput(); inp.focus();
      }
    }
  };
}
function bcBroadcast(type, data){
  if(_bc) try{ _bc.postMessage({type, data}); }catch(e){}
}

// Re-rendre les boutons bande/mode quand la config change dans un autre onglet
window.addEventListener('storage', e => {
  if(e.key === 'logx_config'){
    // currentContest n'était JAMAIS réassignée ici (seulement à setupDone())
    // : un changement de concours fait dans un AUTRE onglet ne mettait donc
    // jamais à jour le picker bande/mode de ce LOGBOOK-ci.
    try{
      const cfg = JSON.parse(e.newValue || '{}');
      if(cfg.contest) currentContest = cfg.contest;
    }catch(e2){}
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
// intentionalNavigation n'était JAMAIS mise à true nulle part : le garde-fou
// ci-dessus affichait donc la confirmation "quitter la page ?" même pour un
// clic sur un lien de la barre de nav (CONFIG/CARTE IA/...), une navigation
// volontaire DANS l'appli — délégation sur .app-nav pour couvrir tous les
// liens sans avoir à toucher chacun.
document.addEventListener('click', e => {
  if(e.target.closest('.app-nav a')) intentionalNavigation = true;
});

window.addEventListener('DOMContentLoaded', () => {
  init(); // charge calldb.json + config serveur + cluster, puis prefillSetupFromConfig()
  renderMacroPanel();
  loadSoapbox();
  // so2rRafraichir() (logx_outils_divers.js) n'était appelée qu'après l'envoi
  // d'un message vocal — jamais au chargement de la page : l'indicateur SO2R
  // restait vide/périmé sur un poste déjà configuré tant qu'aucun message
  // vocal n'avait encore été envoyé.
  if(typeof so2rRafraichir === 'function') so2rRafraichir();
  if(typeof initCallDictation === 'function') initCallDictation();   // dictée vocale #inputCall (logx_voice_dictation.js) : affiche #callMicBtn seulement si SpeechRecognition est dispo
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
    serverCat2Enabled = !!cfg.cat2_enabled;
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

