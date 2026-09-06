// EV-7 50e increment : BROADCAST CHANNEL (sync multi-onglet) -- extrait de
// logx_logbook.js (docs/LogX_AI_PRD.md). Charge en <script> classique dans
// logx_logbook.html, AVANT logx_logbook.js -- portee globale partagee
// (logbook uniquement, comme avant l'extraction).
//
// Contient : l'etat _bc, initBroadcastChannel() (ouvre le canal 'logx_log' +
// applique les messages recus) et bcBroadcast() (diffuse un message aux autres
// onglets). Consommees par le coeur (DOMContentLoaded, submitQSO) et par
// logx_edit_qso.js / logx_net_control.js / logx_verif_panel.js, a l'usage.
// Le handler window 'storage' (autre voie de sync) reste dans le coeur.

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
    } else if(type === 'update'){
      // Édition d'un QSO sur un autre poste : on remplace l'entrée locale.
      const i = qsoLog.findIndex(q => q.id === data.id);
      if(i >= 0){
        qsoLog[i] = data;
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
