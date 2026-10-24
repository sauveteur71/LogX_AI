// ─── ZONE CQ REÇUE PRÉ-REMPLIE (CQ WW) ───────────────────────────────────────
// Demande F4GLD (24/10/2026) : « sur le concours actuel, quand je rentre un
// indicatif, j'aimerais que la zone reçue se remplisse automatiquement ».
//
// Source : /exchange/check?kind=cq_zone (logx_dxcc.verifier_zone_cq), qui rend
// la zone ATTENDUE d'après cty.dat — y compris les dérogations « (zz) » par
// préfixe et les entrées exactes « =CALL ». C'est la MÊME source que le
// garde-fou « mult fantôme » (checkExchangeZone) : aucune table de zones ici.
//
// RÈGLES (le log doit garder ce que l'opérateur a RÉELLEMENT reçu) :
//  - seulement pour un échange de type zone CQ (currentExchange.check) ;
//  - n'écrit QUE dans un champ vide, ou qui contient encore la valeur qu'on y
//    a mise nous-mêmes (l'indicatif a été corrigé) — JAMAIS par-dessus une
//    zone tapée par l'opérateur ;
//  - la valeur pré-remplie est affichée en italique atténué (classe
//    .zone-auto) jusqu'à ce que l'opérateur y touche : une station dans un
//    pays à cheval sur plusieurs zones (USA, Russie, Canada, Australie…) ou
//    en /P, /MM peut passer une autre zone — il suffit alors de la retaper ;
//  - une réponse réseau arrivée après un changement d'indicatif est ignorée.
// Hors chemin critique : si ce fichier ne charge pas, la saisie est inchangée.

(function(global){
  'use strict';

  var _deb = null;
  var CLASSE = 'zone-auto';

  function _champ(){ return document.getElementById('inputNumRcvd'); }
  function _indicatif(){
    var c = document.getElementById('inputCall');
    return c ? String(c.value || '').trim().toUpperCase() : '';
  }
  function _actif(){
    var ex = global.currentExchange;
    try{ if(typeof currentExchange !== 'undefined') ex = currentExchange; }catch(e){}
    return !!(ex && ex.check === 'cq_zone');
  }

  // Le champ peut-il recevoir une valeur automatique ?
  function _libre(z){
    var v = String(z.value || '').trim();
    return v === '' || (z.dataset.zoneAuto != null && v === z.dataset.zoneAuto);
  }

  function _effacerAuto(z){
    if(!z) return;
    if(z.dataset.zoneAuto != null && String(z.value || '').trim() === z.dataset.zoneAuto) z.value = '';
    delete z.dataset.zoneAuto;
    z.classList.remove(CLASSE);
  }

  function _appliquer(call, attendue){
    var z = _champ();
    if(!z || !_actif()) return false;
    if(call !== _indicatif()) return false;          // l'indicatif a changé entre-temps
    if(!_libre(z)) return false;                      // zone tapée par l'opérateur : on n'y touche pas
    if(!attendue){ _effacerAuto(z); return false; }   // indicatif inconnu : pas de valeur inventée
    z.value = String(attendue);
    z.dataset.zoneAuto = String(attendue);
    z.classList.add(CLASSE);
    z.title = "Zone pré-remplie d'après cty.dat — retape-la si la station en passe une autre";
    return true;
  }

  function preremplir(){
    var z = _champ();
    if(!z || !_actif()) return;
    var call = _indicatif();
    if(call.length < 3){ if(_libre(z)) _effacerAuto(z); return; }
    if(!_libre(z)) return;
    fetch('/exchange/check?kind=cq_zone&call=' + encodeURIComponent(call) + '&value=')
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){ _appliquer(call, d && d.expected); })
      .catch(function(){});
  }

  function _brancher(){
    var c = document.getElementById('inputCall');
    var z = _champ();
    if(!c || !z) return;
    c.addEventListener('input', function(){
      if(_deb) clearTimeout(_deb);
      _deb = setTimeout(preremplir, 350);
    });
    // L'opérateur tape lui-même la zone : elle devient « reçue », plus « auto ».
    z.addEventListener('input', function(){
      delete z.dataset.zoneAuto;
      z.classList.remove(CLASSE);
    });
  }

  global.LogxZoneAuto = { preremplir: preremplir, _appliquer: _appliquer, _libre: _libre,
                          _effacerAuto: _effacerAuto, _brancher: _brancher };
  if(typeof document !== 'undefined' && typeof fetch === 'function'){
    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _brancher);
    else _brancher();
  }
})(typeof window !== 'undefined' ? window : this);
