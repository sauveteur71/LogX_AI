// EV-7 phase 2 (docs/LogX_AI_PRD.md) -- bloc RADIO CAT/AMPLI/ROTOR/WSJT-X
// extrait tel quel de logx_logbook.js (extraction MÉCANIQUE, pas le motif bus
// d'événements du pilote SCAN QSL PAPIER -- voir logx_scan_qsl.js). Analyse
// préalable (Workflow, 4 agents) : les 21 fonctions de ce bloc n'ont pour
// SEUL point d'entrée externe que des attributs onclick=/onchange= dans
// logx_logbook.html (jamais un appel JS direct du cœur) -- exactement le
// même motif que les incréments 1-9. Les entrelacements internes
// (applyWsjtxState() -> refreshPounce()/appliquerSuiviCarres(), etc.)
// restent des DEUX côtés dans CE fichier, donc ne comptent pas comme des
// dépendances cœur->optionnel.
//
// Seule dépendance réelle du cœur vers ce bloc : logx_logbook.js LIT les
// variables d'état rigState/rotorState (pas des appels de fonction) à 12
// endroits (bandmap, ESM, macros F1-F8, fréquence de saisie, boussole
// rotor...). 11 de ces 12 lectures étaient déjà défensivement gardées par
// `typeof rigState !== 'undefined'` (l'app tolère déjà nativement l'absence
// de CAT) ; la 12e (copyMacro(), logx_logbook.js) a reçu le même garde avant
// cette extraction. Aucune dépendance inverse (ce bloc ne lit jamais l'état
// du cœur en retour) -- ce n'est donc PAS un cas bidirectionnel comme
// CHAMPS ADIF PERSONNALISÉS (resté en cœur pour cette raison précise).
//
// adaptivePoll() (le polling adaptatif générique) reste dans logx_logbook.js
// -- pollChat() (cœur, chat multi-poste) le réutilise aussi (ligne ~6300),
// ce n'est pas un utilitaire propre à ce bloc. Ce fichier l'appelle donc en
// tant que fonction du cœur (sens optionnel->cœur, le sens autorisé -- comme
// notify()/renderLog() pour tous les autres fichiers extraits par EV-7).
//
// Bug préexistant trouvé PENDANT cette investigation, SANS RAPPORT avec
// l'extraction (ne pas confondre) : esmSend() (logx_logbook.js) utilise
// rigState.enabled comme condition de routage CW/voix, contrairement à
// updateKeyerPanels() juste à côté qui gère correctement le repli CW-sans-
// CAT. Non corrigé ici (hors périmètre de cette extraction mécanique) --
// signalé séparément à F4GLD.
//
// Dépend de globals restés dans logx_logbook.js : notify(), fetch, trF/trT,
// escHtml, currentMode, pickBand, currentBand, _currentVisibleBands,
// updateKeyerPanels, fetchLog, playBeep, window.rcAlert, window.rcSpeak,
// window.rcTtsEnabled, adaptivePoll.

// ─── RADIO CAT (rigctld) ─────────────────────────────────────────────────────
// Widget état radio (fréq/mode) + envoi CW des macros. Actif uniquement si le
// pilotage est activé dans CONFIG. Sondage doux (3 s) ; tolère l'absence de radio.
// Polling adaptatif (voir adaptivePoll() dans logx_logbook.js) : cadence
// rapide quand le matériel est actif, lente quand il est absent. Un poste
// sans radio/ampli/WSJT-X générait sinon ~1 400 requêtes de fond par heure
// (rig+amp+wsjtx à 3-4 s) alors que le serveur répond systématiquement
// enabled:false.
let rigState = {enabled:false, mode:'', freq_khz:0};

function refreshRig(){
  return fetch('/rig/state').then(r=>r.ok?r.json():null).then(applyRigState).catch(()=>{});
}

// Extrait de refreshRig() pour être réutilisable depuis refreshHardware()
// (poll groupé rig+amp+wsjtx+rotor en 1 requête, voir plus bas) — refreshRig()
// elle-même reste utilisable telle quelle pour un rafraîchissement ponctuel.
function applyRigState(d){
    const panel = document.getElementById('rigPanel');
    const freqBtn = document.getElementById('freqRigBtn');
    if(!d || !d.enabled){
      rigState.enabled=false; if(panel) panel.style.display='none'; if(freqBtn) freqBtn.style.display='none';
      if(typeof updateFreqLockIcon==='function') updateFreqLockIcon();   // masque le cadenas : plus de CAT
      return;
    }
    rigState.enabled = true;
    if(panel) panel.style.display = 'block';
    if(freqBtn) freqBtn.style.display = '';
    // Appelée ici, AVANT la branche d.ok/else : rigState.enabled vient de
    // passer à true dans les DEUX cas (CAT activé en CONFIG, que rigctld
    // réponde ou non -- get_state() peut renvoyer {enabled:true, ok:false}
    // si le port existe mais que la radio ne répond pas). Un appel
    // seulement dans le bloc d.ok laissait le cadenas périmé tant qu'aucun
    // poll réussi n'arrivait (trouvé par la revue adversariale du 08/08/2026).
    if(typeof updateFreqLockIcon==='function') updateFreqLockIcon();
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
}

function syncBandModeFromRig(freqKhz, mode){
  // Fréquence radio → bande interne (bornes larges pour les segments contest)
  const mhz = freqKhz / 1000;
  const BANDS = [[1.8,2,'1.8'],[3.5,4,'3.5'],[7,7.3,'7'],[14,14.35,'14'],
                 [21,21.45,'21'],[28,29.7,'28'],[50,54,'50'],[144,148,'144'],[430,440,'432']];
  for(const [lo,hi,b] of BANDS){
    if(mhz>=lo && mhz<=hi){
      if(typeof currentBand!=='undefined' && currentBand!==b && _currentVisibleBands.includes(b)){
        pickBand(b);
      }
      break;
    }
  }
}

function rigStopCW(){
  fetch('/rig/stop', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'}).catch(()=>{});
}

// ─── AMPLIFICATEUR HF (Elecraft KPA500/1500, Icom PW-1/PW2, SPE Expert) ──────
// Panneau compact : puissance/SWR/défaut affichés en direct + bascule
// standby/operate. Les champs varient selon la marque (logx_amp.py
// get_state()) : on prend le premier champ disponible dans un ordre de
// préférence (unités réelles d'abord, valeurs brutes constructeur ensuite).
let ampState = {enabled: false, operate: false};

function refreshAmp(){
  return fetch('/amp/state').then(r=>r.ok?r.json():null).then(applyAmpState).catch(()=>{});
}

// Extrait de refreshAmp() — voir applyRigState() plus haut pour le pourquoi.
function applyAmpState(d){
    const panel = document.getElementById('ampPanel');
    if(!d || !d.enabled){ ampState.enabled = false; if(panel) panel.style.display = 'none'; return; }
    ampState.enabled = true;
    if(panel) panel.style.display = 'block';
    const dot = document.getElementById('ampDot');
    const powerEl = document.getElementById('ampPower');
    const swrEl = document.getElementById('ampSwr');
    const faultEl = document.getElementById('ampFault');
    const btn = document.getElementById('ampOperateBtn');
    if(d.ok){
      ampState.operate = !!d.operate;
      powerEl.textContent = (d.power_w != null) ? `${Math.round(d.power_w)} W`
                          : (d.power_raw != null) ? `${d.power_raw} (brut)` : '— W';
      const swr = (d.swr != null) ? d.swr.toFixed(1)
                : (d.swr_ant != null) ? d.swr_ant.toFixed(1)
                : (d.swr_raw != null) ? `${d.swr_raw} (brut)` : '—';
      swrEl.textContent = `SWR ${swr}`;
      const faultTxt = d.alarm_label || d.warning_label || d.fault_label
                      || (d.fault_code ? `Défaut ${d.fault_code}` : '');
      faultEl.textContent = faultTxt ? `⚠ ${faultTxt}` : '';
      if(dot) dot.classList.add('on');
      if(btn){
        btn.textContent = ampState.operate ? 'OPERATE' : 'STANDBY';
        btn.style.borderColor = ampState.operate ? 'var(--green)' : 'var(--red)';
        btn.style.color = ampState.operate ? 'var(--green)' : 'var(--red)';
      }
    } else {
      powerEl.textContent = 'ampli injoignable';
      swrEl.textContent = '';
      faultEl.textContent = '';
      if(dot) dot.classList.remove('on');
    }
}

function toggleAmpOperate(){
  const target = !ampState.operate;
  fetch('/amp/operate', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({on: target})}).then(()=>refreshAmp()).catch(()=>{});
}

// ─── ROTOR (rotctld) ─────────────────────────────────────────────────────────
// Sonde l'état pour savoir si le pilotage est actif (affiche le bouton
// « pointer » sous la boussole) ; le pointage réel se fait à la demande.
let rotorState = {enabled:false};
function refreshRotor(){
  return fetch('/rotor/state').then(r=>r.ok?r.json():null).then(applyRotorState)
    .catch(()=>{ rotorState.enabled = false; });
}
function applyRotorState(d){
  rotorState.enabled = !!(d && d.enabled);
}

// ─── PONT WSJT-X (FT8/FT4) ───────────────────────────────────────────────────
// Indicateur de liaison + rafraîchissement du log quand un QSO est auto-loggé.
let _wsjtxLastTotal = -1;
// ═══ L'HORLOGE SANS INTERNET ═════════════════════════════════════════════════
// Sans NTP, l'horloge du PC dérive de quelques secondes par jour. Passé environ
// une seconde, les correspondants cessent de décoder tes appels FT8 — et rien
// ne te le dit : tu crois que la bande est fermée. La mesure est celle du
// consensus des stations reçues (voir logx_wsjtx.derive_horloge), gratuite et
// sans réseau. Aucune IA : il n'y a rien à faire rédiger sur un chiffre et un
// seuil.
function horlogeHtml(h){
  if(!h) return '';
  if(h.etat === 'aucune_mesure' || h.etat === 'peu_de_donnees') return '';
  const c = h.couleur === 'verte' ? 'var(--green)'
          : h.couleur === 'rouge' ? 'var(--red)' : 'var(--yellow)';
  const s = Number(h.secondes) || 0;
  const signe = s >= 0 ? '+' : '';
  // Le sens est démontré dans logx_wsjtx.py : un DT médian positif signifie que
  // MON horloge avance, et qu'il faut la reculer d'autant.
  const sens = s >= 0 ? trT('ton horloge avance') : trT('ton horloge retarde');
  const detail = trF('{sens} de {n} s — médiane sur {st} stations. Au-delà de ±1,2 s, '
                   + 'tes appels FT8 ne seront plus décodés en face.',
                   {sens: sens, n: Math.abs(s).toFixed(1), st: h.stations});
  return ` · <span style="color:${c}" title="${escHtml(detail)}">⏱ ${signe}${s.toFixed(1)} s</span>`;
}

let _wsjtxState = {enabled:false};
function refreshWsjtx(){
  return fetch('/wsjtx/state').then(r=>r.ok?r.json():null).then(applyWsjtxState).catch(()=>{});
}
// Alerte « DXCC/département manquant » façon GridTracker (voir d.missing,
// calculé côté serveur par logx_awards.spotted_new_ones sur les décodages
// FT8/FT4 récents) — notifiée UNE SEULE fois par indicatif/type via ce Set,
// même principe anti-répétition que les autres alertes de l'appli.
const _wsjtxAlerted = new Set();
// ── Interrupteur voix (🔊/🔇) pour les alertes FT8. Pilote rc_tts, le MÊME flag
// global que le bouton voix de la carte (window.rcTtsEnabled/rcSpeak dans
// logx_statusbar.js) : l'activer ici fait aussi parler le coach sur la carte, et
// inversement — un seul réglage « la station parle-t-elle ? » pour tout le poste.
function syncTtsLogBtn(){
  const b = document.getElementById('btnTtsLog');
  if(!b) return;
  const on = !!(window.rcTtsEnabled && window.rcTtsEnabled());
  b.textContent = on ? '🔊' : '🔇';
  b.style.color = on ? 'var(--accent2)' : 'var(--muted)';
}
function toggleTtsLog(){
  let on = false;
  try{ on = !(window.rcTtsEnabled && window.rcTtsEnabled()); localStorage.setItem('rc_tts', on ? '1' : '0'); }catch(e){}
  syncTtsLogBtn();
  // Confirmation PARLÉE au moment où l'on active (force=true, outrepasse le
  // garde) : sans retour audible, impossible de savoir si une voix est
  // seulement disponible sur ce poste.
  if(on){ try{ if(window.rcSpeak) window.rcSpeak(trF('Lecture vocale activée'), true); }catch(e){} }
  else { try{ if(window.speechSynthesis) speechSynthesis.cancel(); }catch(e){} }
}
try{ syncTtsLogBtn(); }catch(e){}
// Extrait de refreshWsjtx() — voir applyRigState() plus haut pour le pourquoi.
function applyWsjtxState(d){
    const el = document.getElementById('wsjtxWidget');
    _wsjtxState.enabled = !!(d && d.enabled);
    // Le panneau Wait-and-Pounce suit la liaison WSJT-X : sans elle, il n'a
    // rien à piloter. Rafraîchi ici plutôt que sur sa propre minuterie —
    // l'état matériel est déjà pollé, inutile d'ajouter un cycle.
    try{ refreshPounce(); }catch(e){}
    if(!el || !d || !d.enabled){ if(el) el.style.display='none'; return; }
    el.style.display = '';
    if(d.connected){
      // Le nom du logiciel RÉELLEMENT connecté. Le protocole UDP de WSJT-X est
      // aussi celui de JTDX et de MSHV : ils étaient déjà acceptés, mais le
      // widget affichait « WSJT-X » quoi qu'il arrive — un opérateur sous JTDX
      // ou MSHV ne pouvait pas savoir que sa liaison marchait.
      const soft = escHtml(d.soft || 'WSJT-X');
      el.innerHTML = `💻 ${soft} <b style="color:var(--green)">●</b> ${d.dial_mhz||''} MHz ${d.mode||''} · ${d.logged_total||0} auto-loggés`
                   + horlogeHtml(d.horloge);
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
    for(const m of (d.missing || [])){
      const key = m.call + '|' + m.type;
      if(_wsjtxAlerted.has(key)) continue;
      _wsjtxAlerted.add(key);
      const freqTxt = m.freq ? trF(' ({f} MHz)', {f: m.freq}) : '';
      const txt = trF('🆕 {call} décodé — {label}{freq}', {call: m.call, label: m.label, freq: freqTxt});
      notify(txt);
      // Alerte réglable par type (#5) : son choisi + voix selon le réglage du
      // type (ou la lecture auto globale 🔊). Le Set ci-dessus garantit une
      // seule fois par indicatif — en FT8 la station réapparaît toutes les 15 s.
      try{ if(window.rcAlert) window.rcAlert(m.type === 'dept' ? 'new_dept' : 'new_dxcc', txt); }catch(e){}
    }
    // BESOIN LoTW en direct : entité déjà travaillée mais pas confirmée LoTW
    // sur cette bande/mode. Distinct de « jamais contacté » ci-dessus (déjà
    // dédupliqué côté serveur), son plus grave, pastille 📡.
    for(const m of (d.lotw || [])){
      const key = m.call + '|lotw';
      if(_wsjtxAlerted.has(key)) continue;
      _wsjtxAlerted.add(key);
      const txt = trF('📡 {call} décodé — {label}', {call: m.call, label: m.label});
      notify(txt);
      try{ if(window.rcAlert) window.rcAlert('lotw_need', txt); }catch(e){}
    }
    appliquerSuiviCarres(d.carres);
}

// ─── LOCATOR TRACKER ─────────────────────────────────────────────────────────
// Les carrés QRA entendus en FT8/FT4, croisés avec le carnet. Le carré vient
// du décodage (« CQ F4ABC JN18 ») ; le serveur le mémorise tant que la station
// reste active, car les messages suivants (-15, RR73, 73) n'en portent pas.
//
// DEUX SONS DISTINCTS, parce que les deux cas n'appellent pas la même réaction
// (règle posée par l'utilisateur) :
//   • carré jamais travaillé À VIE, en plus d'être neuf pour le concours :
//     double intérêt, son plus aigu, et il est déjà remonté en tête côté
//     serveur ;
//   • carré neuf pour CE concours seulement : c'est un multiplicateur à faire,
//     il mérite un son, mais discret.
// Une seule alerte par carré et par bande : en FT8 la même station réapparaît
// toutes les 15 secondes, un son à chaque cycle rendrait le poste inutilisable.
const _carresAlertes = new Set();

// ─── WAIT-AND-POUNCE NIVEAU 2 : armer le coup ────────────────────────────────
// LogX demande à WSJT-X de PRÉPARER la réponse — indicatif rempli, décalage
// audio calé — exactement comme un double-clic sur la ligne du waterfall.
// RIEN NE PART SUR L'AIR de ce seul fait : l'émission reste sous le doigt de
// l'opérateur, qui appuie sur Enable TX. Le libellé et l'infobulle le disent,
// parce qu'un doute là-dessus est la pire chose possible.
async function armerReponse(call){
  if(!call) return;
  try{
    const r = await fetch('/wsjtx/repondre', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({call})});
    const d = await r.json();
    if(d.ok){
      notify(trF('▶ {call} armé dans WSJT-X — à toi d\'émettre', {call: d.call}));
      const b = document.getElementById('btnCouperWsjtx');
      if(b) b.style.display = '';
    } else {
      // Chaque refus dit POURQUOI : « rien ne se passe » après un clic est le
      // retour le plus décourageant qui soit.
      notify(trF('❌ {err}', {err: d.error || 'refus'}));
    }
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
}

// ─── WAIT-AND-POUNCE : l'écran des quatre niveaux ────────────────────────────
// Les niveaux 1 et 2 sont des COMPORTEMENTS permanents de cet écran (alerter,
// rendre les lignes cliquables) : ils vivent en localStorage, ils ne concernent
// que ce poste et n'ont rien à faire dans une session serveur. Les niveaux 3 et
// 4 sont une SESSION bornée dans le temps, partagée et surveillable depuis
// n'importe quel poste — c'est indispensable au niveau 4, où l'opérateur n'est
// pas devant la radio mais doit pouvoir regarder ce qu'elle fait.
const _POUNCE_CLE = 'logx_pounce_local';
let _pounceLocal = {n1: true, n2: true};
try{
  const brut = JSON.parse(localStorage.getItem(_POUNCE_CLE) || '{}');
  _pounceLocal = {n1: brut.n1 !== false, n2: brut.n2 !== false};
}catch(e){ /* stockage indisponible : on garde les valeurs par défaut */ }

function majPounceLocal(){
  const c1 = document.getElementById('pounceN1'), c2 = document.getElementById('pounceN2');
  if(c1) _pounceLocal.n1 = !!c1.checked;
  if(c2) _pounceLocal.n2 = !!c2.checked;
  try{ localStorage.setItem(_POUNCE_CLE, JSON.stringify(_pounceLocal)); }catch(e){}
}

function majPounceUI(){
  const n = parseInt((document.getElementById('pounceNiveau')||{}).value || '0', 10);
  const box = document.getElementById('pounceReglages');
  if(box) box.style.display = n ? '' : 'none';
  // L'avertissement n'apparaît QUE pour le niveau 4 : un avertissement
  // permanent finit par ne plus être lu du tout.
  const av = document.getElementById('pounceAvertN4');
  if(av) av.style.display = (n === 4) ? '' : 'none';
}

async function armerPounce(){
  const n = parseInt(document.getElementById('pounceNiveau').value || '0', 10);
  if(!n) return;
  const criteres = [];
  const m = {pcNouveauPays:'nouveau_pays', pcBesoinLotw:'besoin_lotw',
             pcCarreNeuf:'carre_neuf', pcNouveauMult:'nouveau_mult'};
  for(const id in m){ const el = document.getElementById(id); if(el && el.checked) criteres.push(m[id]); }
  const duree = parseInt(document.getElementById('pounceDuree').value || '30', 10);
  // Le niveau 4 demande une confirmation explicite. Ce n'est pas de la
  // paperasse : c'est le seul moment où l'opérateur décide que sa station
  // émettra en son nom sans qu'il la regarde.
  if(n === 4 && !confirm(trF('La station va émettre sans personne devant elle pendant {d} minutes.\n\nElle s\'arrêtera toute seule à la fin. Confirmer ?', {d: duree}))) return;
  try{
    const d = await fetch('/pounce/armer', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({niveau: n, criteres, duree_min: duree})}).then(r=>r.json());
    notify(d.ok ? trF('🎯 Appel automatique armé pour {d} min', {d: duree})
                : trF('❌ {err}', {err: d.error || 'refus'}));
    refreshPounce();
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
}

async function desarmerPounce(){
  try{
    await fetch('/pounce/desarmer', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    notify('⏹ Appel automatique arrêté');
    refreshPounce();
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
}

function _mmss(s){
  const m = Math.floor(s / 60);
  return m + ' min ' + String(s % 60).padStart(2, '0') + ' s';
}

async function refreshPounce(){
  const panneau = document.getElementById('pouncePanel');
  if(!panneau) return;
  panneau.style.display = _wsjtxState.enabled ? '' : 'none';
  if(!_wsjtxState.enabled) return;
  let d;
  try{ d = await fetch('/pounce/state').then(r=>r.json()); }catch(e){ return; }
  const c1 = document.getElementById('pounceN1'), c2 = document.getElementById('pounceN2');
  if(c1) c1.checked = _pounceLocal.n1;
  if(c2) c2.checked = _pounceLocal.n2;

  const min = document.getElementById('pounceMinuterie');
  const stop = document.getElementById('pounceBtnStop');
  const reglages = document.getElementById('pounceReglages');
  const sel = document.getElementById('pounceNiveau');
  if(d.active){
    // Session en cours : on montre la minuterie et le bouton d'arrêt, et on
    // masque les réglages — les changer sans désarmer donnerait l'illusion
    // qu'ils s'appliquent, alors que la session tourne sur ceux d'origine.
    if(min){ min.style.display=''; min.textContent = '⏱ ' + _mmss(d.restant_s); }
    if(stop) stop.style.display = '';
    if(reglages) reglages.style.display = 'none';
    if(sel){ sel.value = String(d.niveau); sel.disabled = true; }
  } else {
    // Le texte est VIDÉ, pas seulement masqué : sinon le prochain armement
    // ferait clignoter l'ancien décompte le temps d'un rafraîchissement.
    if(min){ min.style.display = 'none'; min.textContent = ''; }
    if(stop) stop.style.display = 'none';
    if(sel) sel.disabled = false;
    majPounceUI();
  }
  const etat = document.getElementById('pounceEtat');
  if(etat){
    etat.textContent = d.active
      ? trF('{n} appel(s) · en cours : {c}', {n: d.appels, c: d.appel_en_cours || '—'})
      : (d.motif_arret ? trF('arrêté : {m}', {m: d.motif_arret}) : '');
  }
  const jr = document.getElementById('pounceJournal');
  if(jr){
    jr.innerHTML = (d.journal || []).slice().reverse().map(j =>
      `<div>${escHtml(j.call)} <span style="opacity:.7">${escHtml(j.motif || '')}</span></div>`).join('');
  }
}

async function couperEmissionWsjtx(){
  try{
    const d = await fetch('/wsjtx/couper', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: '{}'}).then(r=>r.json());
    notify(d.ok ? '⏹ Émission coupée' : trF('❌ {err}', {err: d.error || 'refus'}));
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
}

function appliquerSuiviCarres(carres){
  const liste = document.getElementById('carresEntendus');
  const items = (carres || []).filter(c => c.interet > 0);
  if(liste){
    liste.innerHTML = items.length ? items.map(c => {
      const prio = c.interet === 2;
      // Clic = « armer le coup » (niveau 2), désactivable par la case du
      // panneau Wait-and-Pounce. L'indicatif est restreint aux caractères
      // d'indicatif avant d'entrer dans l'argument onclick : il vient d'un
      // décodage radio, donc d'une source non maîtrisée.
      const jsCall = String(c.call || '').replace(/[^A-Za-z0-9/]/g, '');
      const act = _pounceLocal.n2
        ? `onclick="armerReponse('${jsCall}')" style="display:flex;gap:8px;align-items:baseline;padding:2px 0;cursor:pointer" title="Préparer la réponse à ${escHtml(c.call || '')} dans WSJT-X — l'émission reste sous votre doigt"`
        : 'style="display:flex;gap:8px;align-items:baseline;padding:2px 0"';
      return `<div ${act}>
        <b style="color:${prio ? 'var(--red)' : 'var(--yellow)'}">${escHtml(c.grid)}</b>
        <span style="color:var(--text)">${escHtml(c.call || '')}</span>
        <span style="color:var(--muted);font-size:11px">${escHtml(c.libelle || '')}</span>
      </div>`;
    }).join('') : '';
    const box = document.getElementById('carresBox');
    if(box) box.style.display = items.length ? '' : 'none';
  }
  // Niveau 1 « signaler » décoché : la liste reste affichée, mais plus aucun
  // son ni notification. On marque quand même les carrés comme vus, sinon
  // rallumer la case ferait sonner d'un coup tout l'historique accumulé.
  for(const c of items){
    const cle = c.grid + '|' + (c.band || '');
    if(_carresAlertes.has(cle)) continue;
    _carresAlertes.add(cle);
    if(!_pounceLocal.n1) continue;
    if(c.interet === 2){
      const txt = trF('🔲 NOUVEAU CARRÉ {grid} — {call} (jamais travaillé)',
                      {grid: c.grid, call: c.call || ''});
      notify(txt);
      try{ if(window.rcAlert) window.rcAlert('new_grid', txt); }catch(e){}
    } else {
      const txt = trF('🔲 {grid} — {call} : carré neuf pour ce concours',
                      {grid: c.grid, call: c.call || ''});
      notify(txt);
      try{ if(window.rcAlert) window.rcAlert('mult', txt); }catch(e){}
    }
  }
}

// ─── ÉTAT MATÉRIEL GROUPÉ (rig+amp+wsjtx+rotor) ──────────────────────────────
// Les 4 panneaux ci-dessus étaient pollés séparément (3 requêtes à 3-4s de
// cadence + le rotor à 15s fixe, non adaptatif) : jusqu'à 4 connexions HTTP
// par cycle pour de petits payloads, un coût non négligeable si un antivirus
// (Web Shield ou équivalent) inspecte chaque connexion locale. /hardware/state
// les groupe en 1 requête ; refreshRig/Amp/Wsjtx/Rotor restent disponibles
// individuellement (ex. toggleAmpOperate rafraîchit juste l'ampli après un clic).
function refreshHardware(){
  return fetch('/hardware/state').then(r=>r.ok?r.json():null).then(d=>{
    if(!d) return;
    applyRigState(d.rig);
    applyAmpState(d.amp);
    applyWsjtxState(d.wsjtx);
    applyRotorState(d.rotor);
  }).catch(()=>{});
}
// adaptivePoll() (définie dans logx_logbook.js, voir l'en-tête de ce fichier)
// appelle refreshHardware() une 1re fois immédiatement — pas besoin d'un appel
// initial séparé, contrairement à l'ancien refreshRotor() qui utilisait
// setInterval (sans appel immédiat).
//
// EV-7 : setTimeout(...,0) plutôt qu'un appel direct ici -- ce fichier est
// chargé AVANT logx_logbook.js (comme tous les fichiers extraits EV-7), donc
// adaptivePoll() n'existe pas encore au moment où ce script s'exécute (un
// appel direct lève une ReferenceError, silencieuse au chargement de page :
// le polling matériel ne démarre jamais, sans aucune erreur visible dans les
// vérifications superficielles -- trouvé par la revue adversariale, confirmé
// en reproduisant le scénario en navigateur réel avant de fusionner). Le
// setTimeout retarde l'appel après l'exécution synchrone de TOUS les
// <script> classiques de la page, adaptivePoll() est alors définie.
setTimeout(function(){
  adaptivePoll(refreshHardware, 3000, 20000,
    ()=>rigState.enabled || ampState.enabled || _wsjtxState.enabled || rotorState.enabled);
}, 0);

