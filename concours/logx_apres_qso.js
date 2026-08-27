// ─── Récap « APRÈS LE QSO » (copilote IA, boucle de gratification) ────────────
// Juste après l'enregistrement d'un QSO, une pastille non-modale dit ce que CE
// QSO A APPORTÉ (nouveau pays / nouvelle bande / nouveau département) et ce qui
// RESTE À CONFIRMER (LoTW). C'est la boucle de gratification : voir sa
// progression à chaque contact donne une raison de revenir.
//
// UNE SEULE VÉRITÉ : « ce qu'un QSO apporte » est déjà calculé par le moteur
// awards, exposé par /call/history (new_one, lotw_need) — le même contrat que le
// panneau PRÉ-QSO (checkPrevQsos). Ce module ne RECALCULE rien, il rejoue ce
// contrat APRÈS coup.
//
// GARDE-FOUS (doctrine F4GLD) : lecture seule (aucune écriture au log), non-modal
// (ne vole pas le focus, comme la pastille busted), SILENCIEUX si le QSO
// n'apporte rien (pas de bruit sur un doublon), jamais sur le chemin critique.

(function(global){
  'use strict';

  var _gen = 0;         // jeton anti-course (même garde que _bcGen du filet busted)
  var _restant = 0;     // la pastille s'efface après quelques QSO (série)

  function esc(s){
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // Traduit la réponse /call/history en { gains[], aconf[] }. Fonction pure.
  //   new_one : [{type:'dxcc'|'dept', scope:'atlantic'|'band', label}]  (déjà FR)
  //   lotw_need : {besoin, label, ...}
  function _evaluer(hist){
    var gains = [];
    var no = (hist && hist.new_one) || [];
    for(var i = 0; i < no.length; i++){
      var it = no[i];
      if(!it) continue;
      var emoji = it.type === 'dxcc' ? (it.scope === 'band' ? '📻' : '🌟')
                : it.type === 'dept' ? '📍' : '✨';
      gains.push({emoji: emoji, label: it.label || ''});
    }
    var aconf = [];
    if(hist && hist.lotw_need && hist.lotw_need.besoin){
      aconf.push(hist.lotw_need.label || 'LoTW non confirmé');
    }
    return {gains: gains, aconf: aconf};
  }

  // Affiche la pastille. SILENCIEUSE si rien à dire (doublon) : ni gain ni « à
  // confirmer » -> on cache, pas de bruit.
  function _rendre(ev){
    var zone = document.getElementById('apresQsoPastille');
    if(!zone) return;
    var gains = (ev && ev.gains) || [];
    var aconf = (ev && ev.aconf) || [];
    if(!gains.length && !aconf.length){
      zone.style.display = 'none';
      zone.innerHTML = '';
      return;
    }
    var html = '<span class="aq-titre">✓ QSO enregistré</span>';
    if(gains.length){
      html += '<span class="aq-gains">' + gains.map(function(g){
        return '<span class="aq-gain">' + (g.emoji || '✨') + ' ' + esc(g.label) + '</span>';
      }).join('') + '</span>';
    }
    if(aconf.length){
      html += '<span class="aq-aconf">À confirmer : ' + aconf.map(esc).join(' · ') + '</span>';
    }
    html += '<button type="button" class="aq-close" onclick="LogxApresQso.fermer()" aria-label="Fermer">✕</button>';
    zone.innerHTML = html;
    zone.style.display = 'flex';
    _restant = 3;         // survit à ~3 QSO puis s'efface seule (voir vieillir)
  }

  // Rejoue le contrat /call/history pour le QSO qu'on vient de loguer.
  function montrer(qso){
    if(!qso || !qso.call) return;
    var gen = ++_gen;
    var url = '/call/history?call=' + encodeURIComponent(qso.call)
      + '&band=' + encodeURIComponent(qso.band || '')
      + '&mode=' + encodeURIComponent(qso.mode || '');
    fetch(url).then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        if(gen !== _gen) return;    // un QSO plus récent a pris le relai
        if(!d) return;
        _rendre(_evaluer(d));
      }).catch(function(){});       // récap optionnel : jamais d'erreur visible
  }

  function fermer(){
    var zone = document.getElementById('apresQsoPastille');
    if(zone){ zone.style.display = 'none'; zone.innerHTML = ''; }
    _restant = 0;
  }

  // Sans action, la pastille s'efface au bout de quelques QSO : elle ne doit pas
  // rester en travers de l'écran pendant une série (même choix que le busted).
  function vieillir(){
    if(_restant > 0 && --_restant <= 0) fermer();
  }

  global.LogxApresQso = {
    montrer: montrer, fermer: fermer, vieillir: vieillir,
    _evaluer: _evaluer, _rendre: _rendre
  };

})(typeof window !== 'undefined' ? window : this);
