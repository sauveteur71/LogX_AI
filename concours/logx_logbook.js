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
  _majDeptGrid();   // grille départements visible seulement si l'échange reçu est un dept
}

// Champ ciblé par la grille au contexte courant : #inputNumRcvd (échange-
// département) OU #inputDept (override VHF/UHF). '' = grille cachée.
let _deptCibleId = '';
function _deptEstVhf(){
  // BANDES_THF = liste canonique VHF/UHF/SHF de la page. try/catch : le const
  // peut être en zone morte si _majDeptGrid est appelée très tôt (robustesse).
  try{ return BANDES_THF.indexOf(currentBand) !== -1; }catch(e){ return false; }
}
// Grille départements 00–99 : clic direct -> remplit le champ CIBLE. En échange-
// département c'est #inputNumRcvd (le dept EST l'échange) ; en VHF/UHF c'est
// #inputDept (override qui PRIME sur le locator, jamais la série).
function pickDept(code){
  if(!_deptCibleId) return;
  const f = document.getElementById(_deptCibleId);
  if(!f) return;
  f.value = code;
  if(_deptCibleId === 'inputNumRcvd' && typeof checkExchangeZone === 'function') checkExchangeZone();
  if(window.LogxDeptGrid) LogxDeptGrid.surligner(document.getElementById('deptGrid'), code);
  f.focus();
}
function _majDeptGrid(){
  const wrap = document.getElementById('deptGridWrap');
  const grid = document.getElementById('deptGrid');
  const deptGrp = document.getElementById('inputDeptGroup');
  if(!wrap || !grid || !window.LogxDeptGrid) return;
  LogxDeptGrid.render(grid, pickDept);                              // construit une fois (idempotent)
  _deptCibleId = LogxDeptGrid.champCible(currentExchange.label_r, _deptEstVhf());
  wrap.style.display = _deptCibleId ? '' : 'none';
  if(deptGrp) deptGrp.style.display = (_deptCibleId === 'inputDept') ? '' : 'none';
  const f = _deptCibleId ? document.getElementById(_deptCibleId) : null;
  if(f){
    LogxDeptGrid.surligner(grid, f.value);                         // reflète le dept courant
    if(!f._deptGridLie){                                           // écouteur posé une seule fois
      f._deptGridLie = true;
      f.addEventListener('input', function(){ LogxDeptGrid.surligner(grid, f.value); });
    }
  }
  if(_deptCibleId) _rafraichirDeptTravailles();                    // colore fait / à faire (mult)
}
// Colore la grille : départements DÉJÀ travaillés estompés, à faire visibles
// (aide au multiplicateur). Lecture seule (/data/departments_worked), aucune
// incidence sur le score. N'interroge le serveur QUE si la grille est visible.
function _rafraichirDeptTravailles(){
  if(!_deptCibleId || !window.LogxDeptGrid) return;
  const grid = document.getElementById('deptGrid');
  if(!grid) return;
  fetch('/data/departments_worked')
    .then(function(r){ return r.json(); })
    .then(function(d){ if(d && Array.isArray(d.worked)) LogxDeptGrid.marquerTravailles(grid, d.worked); })
    .catch(function(){});
}

// ─── MODE EXPEDITION : extrait vers logx_expedition_mode.js (EV-7 45e increment,
// docs/LogX_AI_PRD.md) -- charge en <script> classique dans logx_logbook.html
// AVANT logx_logbook.js, portee globale partagee (etat expeditionMode + apply).

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
                 // PAS dans MENU_LB_EXPERT_ONLY_FN (comme showRatePanel/showAwards
                 // au-dessus) : la sûreté n'est pas une fonction avancée, un
                 // débutant qui supprime un QSO par erreur doit pouvoir se
                 // rattraper aussi facilement qu'un habitué.
                 ['🗑️', 'CORBEILLE — restaurer un QSO supprimé', 'showCorbeille'],
                 // C1 incr. 1 (cadrage docs/superpowers/specs/2026-09-11-c1-
                 // requetes-langage-naturel-carnet.md) : accessible à tous,
                 // même raisonnement que CORBEILLE juste au-dessus -- consulter
                 // son propre carnet n'a rien d'une fonction avancée.
                 ['❓', 'QUESTIONS SUR LE CARNET', 'showCarnetQuestions'],
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

// ── CORBEILLE DE QSO (incident du 19/08/2026 : 248 QSO supprimés récupérés à
// la main par carving SQLite) — GET /log/corbeille + POST /log/corbeille/restore
// (concours/logx_corbeille.py). PAS expert-only (voir itemsMenuLogbook) : la
// sûreté d'un débutant compte plus qu'une case de moins dans le menu.
function _cbEsc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

// Texte « il y a … » à partir de deux epochs SECONDES — PURE, testée en V8
// sans DOM ni fetch (comme _bloc_menu ailleurs dans ce fichier).
function _cbAge(deletedAtS, nowS){
  const s = nowS - deletedAtS;
  if(s < 3600) return 'il y a ' + Math.max(1, Math.round(s / 60)) + ' min';
  if(s < 86400) return 'il y a ' + Math.round(s / 3600) + ' h';
  return 'il y a ' + Math.round(s / 86400) + ' j';
}

// Rendu PUR de la liste (entrées déjà résumées par le serveur, voir
// logx_corbeille.resume) — testable sans DOM.
function renderCorbeilleList(entries, nowS){
  entries = entries || []; nowS = nowS == null ? (Date.now() / 1000) : nowS;
  if(!entries.length) return '<div class="cb-empty">Corbeille vide.</div>';
  return entries.map(e =>
    '<div class="cb-row">'
    + '<span class="cb-call">' + _cbEsc(e.call || '?') + '</span>'
    + '<span>' + _cbEsc(e.band || '') + '</span>'
    + '<span>' + _cbEsc(e.mode || '') + '</span>'
    + '<span class="cb-age">' + _cbAge(e.deleted_at, nowS) + '</span>'
    + '<button type="button" class="cb-restore" onclick="restaurerCorbeilleQso(' + JSON.stringify(String(e.id)) + ')">↺ RESTAURER</button>'
    + '</div>'
  ).join('');
}

async function _cbCharger(){
  const box = document.getElementById('cbList');
  if(!box) return;
  try{
    const r = await fetch('/log/corbeille');
    const d = await r.json();
    box.innerHTML = renderCorbeilleList(d.entries || []);
  }catch(e){
    box.innerHTML = '<div class="cb-empty">⚠ Impossible de charger la corbeille.</div>';
  }
}

function showCorbeille(){
  const ov = document.getElementById('corbeilleOverlay');
  if(!ov) return;
  ov.classList.add('show');
  document.getElementById('cbList').innerHTML = '<div class="cb-empty">Chargement…</div>';
  _cbCharger();
}
function closeCorbeille(){
  const ov = document.getElementById('corbeilleOverlay');
  if(ov) ov.classList.remove('show');
}

async function restaurerCorbeilleQso(idStr){
  const id = parseInt(idStr, 10);
  if(!id) return;
  try{
    const r = await fetch('/log/corbeille/restore', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id: id})
    });
    const d = await r.json();
    if(!d.ok){ alert(trF('Restauration impossible : {err}', {err: d.error || '?'})); return; }
    await _cbCharger();     // la liste reflète tout de suite le retrait
    if(typeof fetchLog === 'function') fetchLog();   // le QSO restauré réapparaît dans le carnet
  }catch(e){
    alert(trT('Serveur injoignable — réessaie.'));
  }
}

// ─── QUESTIONS SUR LE CARNET (C1) ────────────────────────────────────────────
// docs/superpowers/specs/2026-09-11-c1-requetes-langage-naturel-carnet.md.
// Boutons rapides (incr. 1) : 0 jeton, 0 appel LLM. Question libre
// (incr. 2) : palier IA si aucun motif fixe ne matche côté serveur.
// Historique multi-tour (incr. 3, 12/09/2026) : le CLIENT porte
// carnetHistorique -- même patron que conversationHistory de Carte IA
// (logx_carte.html), mais sans persistance localStorage (portée : la
// session de page en cours, remise à zéro explicite via le bouton dédié).
// Le serveur reste sans état -- il revalide/borne cet historique à chaque
// appel (logx_carnet_questions.valider_historique), jamais une confiance
// aveugle dans ce qu'envoie le client. Dans tous les cas la réponse est du
// texte simple assignée via textContent, jamais innerHTML -- rien à
// composer côté client.
let carnetHistorique = [];
const CARNET_HISTORIQUE_MAX = 20;   // 10 tours -- même borne que le serveur

function showCarnetQuestions(){
  const ov = document.getElementById('carnetQuestionsOverlay');
  if(!ov) return;
  ov.classList.add('show');
}
function closeCarnetQuestions(){
  const ov = document.getElementById('carnetQuestionsOverlay');
  if(ov) ov.classList.remove('show');
}

async function poserQuestionCarnet(topic){
  const box = document.getElementById('qcReponse');
  if(!box) return;
  box.className = 'qc-reponse';
  box.textContent = 'Recherche…';
  const params = new URLSearchParams({topic: topic});
  if(topic === 'deja_travaille'){
    const input = document.getElementById('qcIndicatifInput');
    params.set('indicatif', (input && input.value || '').trim());
  }
  try{
    const r = await fetch('/log/question?' + params.toString());
    const d = await r.json();
    if(!d.ok){
      box.className = 'qc-reponse qc-erreur';
      box.textContent = d.error || 'Question sans réponse.';
      return;
    }
    box.textContent = d.reponse;
  }catch(e){
    box.className = 'qc-reponse qc-erreur';
    box.textContent = trT('Serveur injoignable — réessaie.');
  }
}

// ─── Question libre (C1, incréments 2 et 3) ─────────────────────────────────
// Aucun motif fixe reconnu côté serveur -> palier IA (jeton). POST (pas
// GET) depuis l'incr. 3 : porte carnetHistorique, une forme impraticable en
// query string. Même réponse texte assignée via textContent que
// poserQuestionCarnet() ci-dessus.
async function poserQuestionLibreCarnet(){
  const input = document.getElementById('qcLibreInput');
  const texte = (input && input.value || '').trim();
  if(!texte) return;
  const box = document.getElementById('qcReponse');
  if(!box) return;
  box.className = 'qc-reponse';
  box.textContent = 'Recherche… (appel IA, ça peut prendre quelques secondes)';
  try{
    const r = await fetch('/log/question', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({texte: texte, historique: carnetHistorique})
    });
    const d = await r.json();
    if(!d.ok){
      box.className = 'qc-reponse qc-erreur';
      box.textContent = d.error || 'Question sans réponse.';
      return;
    }
    box.textContent = d.reponse;
    input.value = '';
    // Seul un vrai tour IA alimente la conversation -- une réponse
    // déterministe (topic !== 'ia', ex. "déjà travaillé" reconnu dans le
    // texte libre) n'a pas de raison de peser sur le contexte multi-tour.
    if(d.topic === 'ia'){
      carnetHistorique.push({role: 'user', content: texte});
      carnetHistorique.push({role: 'assistant', content: d.reponse});
      if(carnetHistorique.length > CARNET_HISTORIQUE_MAX){
        carnetHistorique = carnetHistorique.slice(-CARNET_HISTORIQUE_MAX);
      }
    }
    majIndicateurConversationCarnet();
  }catch(e){
    box.className = 'qc-reponse qc-erreur';
    box.textContent = trT('Serveur injoignable — réessaie.');
  }
}

function reinitialiserConversationCarnet(){
  carnetHistorique = [];
  majIndicateurConversationCarnet();
}

// Visibilité de l'état de conversation -- intuitivité : sans indice, rien
// ne dit à l'opérateur qu'une question de suivi ("et en CW ?") va réutiliser
// le contexte précédent plutôt que repartir de zéro.
function majIndicateurConversationCarnet(){
  const btn = document.getElementById('qcResetBtn');
  if(!btn) return;
  const tours = carnetHistorique.length / 2;
  btn.hidden = tours === 0;
  btn.textContent = tours > 0
    ? 'Nouvelle conversation (' + tours + ' tour' + (tours > 1 ? 's' : '') + ')'
    : '';
}

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
const ACT_MIN = {POTA:10, SOTA:4, IOTA:1, WWFF:44, ARLHS:2, WCA:50, LLOTA:10};
let activationProgram = '';
let myActivationRef = '';
let activationTimer = null;
let lastActQsoTotal = 0;

// Mode chasseur (réglé dans CONFIG) : quand actif, le champ « réf. correspondant »
// reste disponible dans la saisie même hors activation, pour logger un sommet/parc
// chassé (la réf part sur le QSO -> sig/sig_info).
function chaserModeActif(){
  // Piloté d'abord par le MODE DE SESSION XOTA choisi à l'accueil (chasse/mixte
  // -> champ réf. correspondant visible). Repli sur l'ancien réglage CONFIG
  // chaser_mode pour rétro-compat si le module n'est pas chargé.
  try{
    if(window.LogxXotaRole) return !!LogxXotaRole.roleConfig(LogxXotaRole.getRole()).chasse;
  }catch(e){}
  try{ return JSON.parse(localStorage.getItem('logx_config')||'{}').chaser_mode === 'oui'; }
  catch(e){ return false; }
}

function applyActivationMode(program, ref){
  activationProgram = (program||'').toUpperCase();
  myActivationRef = (ref||'').trim().toUpperCase();
  const on = !!(activationProgram && myActivationRef);
  const bar = document.getElementById('activationBar');
  const trg = document.getElementById('theirRefGroup');
  if(bar) bar.style.display = on ? '' : 'none';
  // En activation : le programme du correspondant suit celui que J'active (S2S).
  const tp = document.getElementById('theirRefProg');
  if(tp && on && activationProgram) tp.value = activationProgram;
  // Reste visible si activation OU mode chasseur (sinon masqué, saisie compacte).
  if(trg) trg.style.display = (on || chaserModeActif()) ? '' : 'none';
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
  // Points de chasse indicatifs : même visibilité que la réf. correspondant.
  sotaPointsHint();
  refreshSotaPoints();
  majExportSotaVisible();
}

// ─── ACTIVATION SOTA/XOTA (points de chasse, role, refresh, export POTA) :
// extrait vers logx_activation_ui.js (EV-7 38e increment, docs/LogX_AI_PRD.md)
// -- charge en <script> classique dans logx_logbook.html AVANT logx_logbook.js,
// portee globale partagee.

// nextRPHWeekendUTC : extrait vers logx_clock.js (EV-7 52e increment) -- charge
// avant logx_logbook.js. CONTEST_SCHEDULE ci-dessous l'utilise comme global.

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

// ─── SELECTEUR CONCOURS : donnees CS_DATA extraites vers logx_cs_data.js (EV-7
// 51e increment, docs/LogX_AI_PRD.md) -- chargees en <script> AVANT logx_logbook.js.

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
  // Les groupes vides sont IGNORÉS, pas traités comme « matche tout » : sinon
  // un seul groupe vide (fltAddGroup pousse `[]`) forcerait le match de tout le
  // log via le OU entre groupes (some), annulant en silence les conditions des
  // autres groupes. Plus aucun groupe peuplé -> aucun critère -> pas de filtre
  // (état par défaut {groups:[[]]} : tout matche, comportement voulu).
  const peuples = tree.groups.filter(group => group.length);
  if(!peuples.length) return true;
  return peuples.some(group => group.every(cond => matchesFilterCondition(q, cond)));
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

// ─── SCORING PILOTE PAR LE SERVEUR : extrait vers logx_scoring_client.js
// (EV-7 39e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique
// dans logx_logbook.html AVANT logx_logbook.js, portee globale partagee.

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

// ─── ENREGISTREUR AUDIO PAR QSO : extrait vers logx_audio_recorder.js
// (EV-7 37e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique
// dans logx_logbook.html AVANT logx_logbook.js, portee globale partagee.

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
// getContestEndUTC/getContestStartUTC : extraits vers logx_clock.js (EV-7 48e
// increment) -- charges avant logx_logbook.js. L'etat contestEndUTC/contestStartUTC
// (ci-dessous) reste ici, initialise via ces fonctions globales.
let contestEndUTC   = getContestEndUTC();
let contestStartUTC = getContestStartUTC();
// ─── HORLOGE + COMPTE A REBOURS (affichage) : extrait vers logx_clock.js (EV-7
// 47e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html AVANT logx_logbook.js, portee globale partagee. Le cablage
// setInterval(updateClockAndCountdown) reste ci-dessous (etat contest local).
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
  if(typeof _majDeptGrid === 'function') _majDeptGrid();   // VHF/UHF : (dé)montre l'override dept
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
    if(typeof _majDeptGrid === 'function') _majDeptGrid();   // VHF/UHF : (dé)montre l'override dept
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

// Activité « activation portable » (id `iota_pota` : POTA/SOTA/WWFF/châteaux…).
// QSO occasionnel hors concours : bandes déca SSB/CW courantes + V/UHF portable,
// plutôt que ALL_BANDS (micro-ondes rares sur le terrain). Même principe que le
// repli V/UHF ci-dessus ; reste filtrable par les toggles CONFIG.
function _activiteEstXota(){
  try{ return localStorage.getItem('logx_activity') === 'iota_pota'; }catch(e){ return false; }
}
const XOTA_ACTIVITY_DEFAULT_BANDS = ['7', '14', '21', '28', '50', '144', '432'];

// Bandes actuellement autorisées (concours + toggles) — utilisé par
// onFreqInput() pour valider une bascule automatique de bande, et par le
// popup de choix de bande (#bandPickerPopup) pour lister les alternatives.
let _currentVisibleBands = [];
// Bandes ajoutées manuellement via « + autres… » cette session (hors défaut
// d'activité) : mémoire VOLATILE (perdue au rechargement / changement d'activité),
// choix F4GLD « reste la session ». Un règlement de concours reste prioritaire :
// ces bandes ne l'élargissent JAMAIS (voir renderBandButtons).
let _bandesAjoutees = [];

// « + autres… » : révèle TOUTES les bandes dans le sélecteur pour en ajouter une
// hors du défaut d'activité (« masquer ≠ bloquer »). Choisir une bande ici
// l'ajoute à la session via _ajouterBande().
function _revelerToutesBandes(){
  const popup = document.getElementById('bandPickerPopup');
  if(!popup) return;
  popup.innerHTML = ALL_BANDS.map(b =>
    `<button type="button" class="bm-btn${b===currentBand?' active':''}" data-val="${b}" onclick="_ajouterBande('${b}')">${BAND_LABELS[b]||b+' MHz'}</button>`
  ).join('');
}
function _ajouterBande(band){
  if(_bandesAjoutees.indexOf(band) < 0) _bandesAjoutees.push(band);
  renderBandButtons(currentContest);   // reconstruit le sélecteur, bande incluse
  pickBand(band);                       // et la sélectionne tout de suite
}

function renderBandButtons(contest){
  // Bandes du concours (résolues via logx_contest_rules.js), filtrées par
  // les toggles de configuration
  const _contestFilter = _bandsForContest(contest);
  let contestBands = _contestFilter
    || (_activiteEstVuhf() ? VUHF_ACTIVITY_DEFAULT_BANDS
        : _activiteEstXota() ? XOTA_ACTIVITY_DEFAULT_BANDS
        : ALL_BANDS);
  // Bandes ajoutées à la volée (« + autres… ») : union HORS concours seulement.
  // Un règlement de concours (contestFilter truthy) reste prioritaire, jamais élargi.
  if(!_contestFilter && _bandesAjoutees.length)
    contestBands = ALL_BANDS.filter(b => contestBands.indexOf(b) >= 0 || _bandesAjoutees.indexOf(b) >= 0);

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
    let _html = visibleBands.map(b =>
      `<button class="bm-btn${b===visibleBands[0]?' active':''}" data-val="${b}" onclick="pickBand('${b}')">${BAND_LABELS[b]||b+' MHz'}</button>`
    ).join('');
    // Hors concours, s'il reste des bandes non affichées : « + autres… » pour en
    // ajouter une à la session (« masquer ≠ bloquer »). Absent en concours (règles).
    if(!_contestFilter && visibleBands.length < ALL_BANDS.length)
      _html += `<button type="button" class="bm-btn bm-more" onclick="_revelerToutesBandes()" title="Ajouter une autre bande à la session">+ autres…</button>`;
    popup.innerHTML = _html;
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

// focusNext() consolide dans logx_lookup.js (EV-7 55e incr.) -- son unique
// appelant selectAC() y vit, aucune autre reference dans le depot.

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
    inputFreqRx:'freq_rx', inputMyRig:'my_rig', inputMyAntenna:'my_antenna',
    inputQslSent:'qsl_sent', inputLotwSent:'lotw_qsl_sent', inputEqslSent:'eqsl_qsl_sent',
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
const REF_PROGRAMS = ['POTA','SOTA','WWFF','IOTA','WCA','ARLHS','LLOTA'];
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
  const wrap = document.createElement('div');   // ligne + info sommet dessous
  wrap.className = 'ref-wrap';
  const row = document.createElement('div');
  row.className = 'ref-row';
  const opts = REF_PROGRAMS.map(function(p){ return '<option value="'+p+'">'+p+'</option>'; }).join('');
  row.innerHTML = '<select class="field-input field-compact ref-prog refdrop">'+opts+'</select>'+
    '<input type="text" class="field-input field-compact ref-val" placeholder="réf. (F/AB-123, FR-1234…)" autocomplete="off">'+
    '<button type="button" class="ref-del" title="Retirer cette référence">✕</button>';
  const info = document.createElement('div');   // « Scafell Pike · 978 m · 10 pts »
  info.className = 'ref-info';
  info.hidden = true;
  var _refresh = function(){ if(typeof renderActivityTags === 'function') renderActivityTags(); };
  row.querySelector('.ref-del').addEventListener('click', function(){ wrap.remove(); _refresh(); });
  row.querySelector('.ref-val').addEventListener('change', _refresh);   // ref saisie -> tag SOTA/POTA en aperçu
  // Changer de programme relance le relevé (via un input synthétique sur la réf).
  row.querySelector('.ref-prog').addEventListener('change', function(){
    var rv = row.querySelector('.ref-val');
    if(rv) rv.dispatchEvent(new Event('input'));
  });
  wrap.appendChild(row); wrap.appendChild(info);
  box.appendChild(wrap);
  // Relevé du sommet/parc sous la ligne (SOTA/POTA/WWFF/IOTA) — lecture seule.
  if(window.LogxRefInfo){
    LogxRefInfo.attacher(row.querySelector('.ref-val'),
      function(){ var s = row.querySelector('.ref-prog'); return s ? s.value : ''; }, info);
  }
}

// Auto-remplissage éditable (lot 5, sous-chantier A). PERSISTE l'azimut (bearing,
// jusqu'ici affiché à la boussole mais jamais stocké) et remplit pays/continent/
// zone CQ depuis l'indicatif (lookupDXCC), SANS écraser une saisie manuelle. Le
// numéro DXCC et la zone ITU viennent du serveur (cty.dat) -> sous-chantier B.
function autoFillQso(q){
  if(q.locator && typeof bearing === 'function'){
    const az = bearing(q.locator);
    if(az != null && !isNaN(az)) q.ant_az = Math.round(az);
  }
  if(q.call && typeof lookupDXCC === 'function'){
    const d = lookupDXCC(q.call);
    if(d){
      if(!q.country && d.c) q.country = d.c;
      if(!q.cont && d.ct) q.cont = d.ct;
      if(!q.cqz && d.cq != null) q.cqz = String(d.cq);
    }
  }
  return q;
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
    // Département correspondant SAISI (override VHF/UHF) : prime sur le locator
    // dans dept_for_qso (serveur). Vide -> champ absent, comportement inchangé.
    dept: ((document.getElementById('inputDept')?.value || '').trim().toUpperCase() || undefined),
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
  // Le PRÉNOM du champ éditable PRIME sur l'annuaire (spread ci-dessus) :
  // l'opérateur a pu le corriger. Vide -> on garde ce que l'annuaire a fourni.
  const nameManuel = (document.getElementById('inputName')?.value || '').trim();
  if(nameManuel) qso.name = nameManuel;

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
  }
  // Réf. du correspondant (chasse SOTA/POTA, ou P2P/S2S en activation) : toujours
  // enregistrée si présente, INDÉPENDAMMENT du mode activation — un chasseur pur
  // la logge aussi (sig/sig_info -> comptage de ses chasses).
  const _tr = (document.getElementById('inputTheirRef')?.value || '').trim().toUpperCase();
  if(_tr){
    const _tp = (document.getElementById('theirRefProg')?.value || activationProgram || 'SOTA').toUpperCase();
    qso.sig = _tp; qso.sig_info = _tr;
  }

  // Champs secondaires des onglets (lot 2, sous-chantier A) : puissance, e-mail,
  // QSL via, zones, comté, prop_mode, lieu d'exploitation, fréq RX, heure de fin,
  // matériel, antenne. Fusionnés APRÈS l'activation pour ne rien écraser d'établi.
  Object.assign(qso, collectExtraFields());

  // Heure de fin (time_off) AUTOMATIQUE : plus de saisie manuelle. Un QSO de
  // concours est instantané -> fin = début (heure du QSO), en chiffres nus
  // (« 12:15 » -> « 1215 ») comme TIME_ON à l'export et comme le format attendu
  // par le contrôle de cohérence. time_off reste une clé interne exportée
  // (symétrie ADIF) ; seule la frappe disparaît. Demande F4GLD.
  qso.time_off = qso.time.replace(':', '');

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

  // Tags multi-activité (lot 4) : AUTO dérivés du QSO (mode, QRP, références,
  // lieu, propagation) UNION les tags MANUELS de l'opérateur. Orthogonal au
  // concours ; cherchable dans le carnet.
  if(typeof deriveActivityTags === 'function'){
    const _tags = mergeTags(deriveActivityTags(qso), (typeof getManualTags === 'function' ? getManualTags() : []));
    if(_tags.length) qso.activity_tags = _tags;
  }

  // Auto-remplissage éditable (lot 5) : azimut persisté + pays/continent/zone CQ
  // depuis l'indicatif, sans écraser ce que l'opérateur a saisi à la main.
  autoFillQso(qso);

  // Mise à jour automatique de la base si nouvelles infos (locator ET/OU prénom :
  // le prénom saisi/corrigé enrichit la base interne -> source de prénom hors QRZ,
  // réutilisée au prochain QSO avec ce correspondant).
  if(loc || nameManuel) updateCallDB(call, loc, null, nameManuel);

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
      // Copilote : re-valider le log en tâche de fond (badge discret). Jamais
      // de correction auto — juste signaler. Debounce côté module.
      try{ if(window.LogxValidationLive) LogxValidationLive.rafraichir(); }catch(e){}
      try{ updateLastQso(qso); }catch(e){}
      if(activationProgram) refreshActivation();   // MAJ immédiate du compteur d'activation
      playBeep(880, 80);
      vieillirPastilleBusted();      // la pastille du QSO précédent vieillit
      verifierIndicatifApres(qso);   // filet anti-busted call, APRÈS coup
      // Récap « après-QSO » : ce que ce QSO apporte (nouveau pays/bande, à
      // confirmer LoTW) — boucle de gratification, lecture seule, non-modal.
      try{ if(window.LogxApresQso){ LogxApresQso.vieillir(); LogxApresQso.montrer(qso); } }catch(e){}
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
  const _dp = document.getElementById('inputDept'); if(_dp) _dp.value = '';   // override dept : propre au contact
  if(window.LogxDeptGrid) LogxDeptGrid.surligner(document.getElementById('deptGrid'), '');   // grille : plus rien de sélectionné
  if(typeof _rafraichirDeptTravailles === 'function') _rafraichirDeptTravailles();   // QSO loggué -> maj fait/à faire
  // Champs par-QSO des onglets (lot 2-4) : vidés comme les autres champs propres
  // au contact. Les champs de MA station (puissance, matériel, antenne, lieu,
  // mes références) PERSISTENT d'un QSO à l'autre -- on ne les touche pas ici.
  ['inputEmail','inputQslVia','inputCqz','inputItuz','inputCnty','inputFreqRx','inputPropMode']
    .forEach(function(id){ var e=document.getElementById(id); if(e) e.value=''; });
  var _refsCorr = document.getElementById('refsList'); if(_refsCorr) _refsCorr.innerHTML='';   // réf. correspondant (S2S/P2P)
  if(typeof resetManualTags === 'function') resetManualTags();   // tags manuels : per-QSO
  // Commentaire vidé comme les autres champs propres au QSO : le laisser
  // traînerait la remarque du contact précédent sur le suivant — pire qu'un
  // champ vide, puisque l'opérateur ne la relirait pas avant d'enregistrer.
  const _cm = document.getElementById('inputComment'); if(_cm) _cm.value = '';
  const _tr = document.getElementById('inputTheirRef'); if(_tr) _tr.value = '';
  const _trp2 = document.getElementById('theirRefPoints'); if(_trp2){ _trp2.hidden = true; _trp2.textContent = ''; }
  if(typeof refreshSotaPoints === 'function') refreshSotaPoints();   // QSO loggué -> maj du total de chasse indicatif
  const _nm = document.getElementById('inputName'); if(_nm) _nm.value = '';   // prénom : propre au contact
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
    // Recherche : indicatif, locator, ET tags multi-activité (lot 6) — retrouver
    // un QSO par « SOTA », « QRP », « FT8 »… sans dupliquer le contact.
    if(search && !(q.call||'').includes(search) && !(q.locator||'').includes(search)
       && !(q.activity_tags||[]).join(' ').toUpperCase().includes(search)) return false;
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
    tbody.innerHTML = `<tr><td colspan="12" style="text-align:center;padding:30px;color:var(--muted);font-family:var(--font-mono)">${emptyMsg}</td></tr>`;
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
      <td class="td-time">${escHtml(q.time)||'—'}</td>
      <td class="td-call">${incomplete?'<span class="incomplete-flag" title="QSO incomplet — champ(s) manquant(s), à corriger">⚠️</span> ':''}${escHtml(q.call)||'—'}${q.qsl_scan?` <span title="Scan QSL attaché">📎</span>`:''}</td>
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

// ─── BARRES DE STATS (classement operateurs + recap par bande) : extraites vers
// logx_stats_bars.js (EV-7 43e increment, docs/LogX_AI_PRD.md) -- chargees en
// <script> classique dans logx_logbook.html AVANT logx_logbook.js, portee globale.

// ─── GRAPHE QSO/HEURE (sparkline SVG inline) : extrait vers logx_hour_chart.js
// (EV-7 41e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html AVANT logx_logbook.js, portee globale partagee.

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
//
// EV-7 — trT/trF/notify RESTENT ICI (cœur), extraction ÉCARTÉE (2026-09-08).
// Tentée au 55e incrément puis abandonnée : ce sont des primitives appelées
// partout, et au moins HUIT harnais de test construisent leur propre chaîne
// logx_logbook.js et exercent un chemin qui appelle notify() (souvent sans
// nommer trT/trF/notify, donc invisibles à un grep du symbole) —
// test_notify_dynamic_i18n, test_export_edi_num_sent, test_logbook_render_window_reset,
// test_qsl_card_designer, test_qso_champs_obligatoires, test_qtc_panel_js,
// test_undo_last_qso_id_adopte, test_audio_recorder_client. Les sortir casse
// chacun (ReferenceError: notify is not defined) et impose d'ajouter le
// nouveau fichier à chaque chaîne, avec fragilité permanente pour tout futur
// test. Valeur (≈30 lignes) sans rapport avec le coût/risque : c'est de
// l'infrastructure de cœur, comme adaptivePoll()/playBeep(). Ne pas retenter.
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

// ─── CHAT MULTI-OPERATEUR : extrait vers logx_chat.js (EV-7 40e increment,
// docs/LogX_AI_PRD.md) -- charge en <script> classique dans logx_logbook.html
// AVANT logx_logbook.js, portee globale partagee.

// ─── VUE PARTNER (saisie en direct) : extraite vers logx_partner_view.js (EV-7
// 46e increment, docs/LogX_AI_PRD.md) -- chargee en <script> classique dans
// logx_logbook.html AVANT logx_logbook.js, portee globale partagee.

// ─── RESERVE D'ESPACE BAS + TOGGLE CHAT : extraits vers logx_panel_layout.js
// (EV-7 49e increment, docs/LogX_AI_PRD.md) -- charges en <script> classique
// dans logx_logbook.html AVANT logx_logbook.js, portee globale partagee.

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

// ─── PREREMPLISSAGE MODAL + NOMS OPERATEURS : extrait vers logx_prefill_setup.js
// (EV-7 42e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html AVANT logx_logbook.js, portee globale partagee.

// ─── ALERTE DOUBLE-BANDE + RAPPEL ON4KST : extraits vers logx_alertes_rappels.js
// (EV-7 44e increment, docs/LogX_AI_PRD.md) -- charges en <script> classique dans
// logx_logbook.html AVANT logx_logbook.js, portee globale partagee.

// RACCOURCI BUREAU (bandeau premier lancement) : extrait vers
// logx_shortcut_offer.js (EV-7 phase 2, 34e increment,
// docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html, portee globale partagee.

// ─── BROADCAST CHANNEL (sync multi-onglet) : coeur extrait vers logx_broadcast.js
// (EV-7 50e increment, docs/LogX_AI_PRD.md) -- charge en <script> classique dans
// logx_logbook.html AVANT logx_logbook.js. Le handler 'storage' reste ci-dessous.

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
  // Relevé du sommet/parc sous la réf. du correspondant (chasse, ou S2S/P2P) :
  // le programme vient du sélecteur #theirRefProg (repli sur ce que j'active,
  // puis SOTA). Lecture seule.
  if(window.LogxRefInfo){
    LogxRefInfo.attacher(document.getElementById('inputTheirRef'),
      function(){ var s = document.getElementById('theirRefProg'); return (s && s.value) || activationProgram || 'SOTA'; },
      document.getElementById('theirRefInfo'));
  }
  // Changer le programme du correspondant relance le relevé.
  var _trp = document.getElementById('theirRefProg');
  if(_trp) _trp.addEventListener('change', function(){
    var i = document.getElementById('inputTheirRef'); if(i) i.dispatchEvent(new Event('input'));
    sotaPointsHint();
  });
  // Indice points de chasse indicatifs : suit la saisie de la réf. correspondant.
  var _itr = document.getElementById('inputTheirRef');
  if(_itr){ _itr.addEventListener('input', sotaPointsHint); _itr.addEventListener('change', sotaPointsHint); }
  // Mode chasseur (CONFIG) : le champ réf. correspondant reste visible même hors
  // activation, pour logger les sommets/parcs qu'on chasse.
  if(chaserModeActif()){
    var _trg = document.getElementById('theirRefGroup'); if(_trg) _trg.style.display = '';
    refreshSotaPoints();   // affiche d'emblée les totaux de chasse
    majExportSotaVisible();   // et les boutons d'export sotadata
  }
  if(window.LogxXotaRole){
    renderXotaRoleSwitch();   // bascule de mode de session toujours visible en tête de saisie
  }
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

