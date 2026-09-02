// ─── Cockpit d'accueil « Que puis-je faire maintenant ? » ────────────────────
// Sur la page d'accueil, en plus des tuiles d'activité et du bouton « Reprendre »,
// un cockpit répond d'un coup d'œil : OPPORTUNITÉS (meilleures stations à
// travailler), PROGRESSION (diplômes), ÉTAT (station prête ?). LECTURE SEULE :
// agrège des endpoints EXISTANTS (/data/spots_ranked, /awards/summary,
// /hardware/state, /dxcc/status) — aucun moteur réécrit, rien n'est piloté.
// Les fonctions de mapping sont pures (testables) ; les chiffres viennent des
// endpoints (une seule vérité serveur).

(function(global){
  'use strict';

  var EMOJI = {atno: '🌟', new_band: '📻', new_mode: '🎚', new_grid: '🗺', needed_confirm: '📩'};

  function esc(s){
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // Top 3 opportunités (credit_score > 0), depuis /data/spots_ranked. Pur.
  function _opportunites(data){
    var spots = (data && data.spots) || [];
    return spots.filter(function(s){ return s && s.credit_score > 0; })
      .sort(function(a, b){ return b.credit_score - a.credit_score; })
      .slice(0, 3)
      .map(function(s){
        return {emoji: EMOJI[s.credit_classe] || '•',
                texte: (s.call || '') + ' — ' + (s.credit_raison || 'à travailler')};
      });
  }

  // Progression compacte depuis /awards/summary. Pur.
  function _progression(s){
    s = s || {};
    var out = [];
    if(s.dxcc && s.dxcc.worked != null){
      out.push({label: 'DXCC', valeur: s.dxcc.worked + (s.dxcc.total ? ' / ' + s.dxcc.total : '')});
    }
    if(s.departments && s.departments.metro_worked != null){
      out.push({label: 'Départements', valeur: s.departments.metro_worked + ' / ' + (s.departments.metro_total || '?')});
    }
    if(s.qso_total != null){
      out.push({label: 'QSO', valeur: String(s.qso_total)});
    }
    return out;
  }

  // État station (quelques voyants) depuis /hardware/state + /dxcc/status. Pur.
  function _etat(hw, dxcc){
    hw = hw || {}; dxcc = dxcc || {};
    var rig = hw.rig || {}; var w = hw.wsjtx || {};
    return [
      {nom: 'CAT', couleur: !rig.enabled ? 'muted' : (rig.ok ? 'green' : 'red')},
      {nom: 'FT8', couleur: !w.enabled ? 'muted' : (w.connected ? 'green' : 'yellow')},
      {nom: 'DXCC', couleur: dxcc.available ? 'green' : 'red'}
    ];
  }

  // Prochaines cibles (server /awards/prochaines_cibles) : liste {entity, slot}.
  function _rendreCibles(cibles){
    var el = document.getElementById('ckCibles');
    if(!el) return;
    cibles = cibles || [];
    el.innerHTML = cibles.length
      ? cibles.map(function(c){ return '<div class="ck-opp">🎯 <span>' + esc(c.entity) + '</span> · ' + esc(c.slot) + '</div>'; }).join('')
      : '<div class="ck-vide">Rien à recommander pour l\'instant.</div>';
  }

  function _rendre(opp, prog, etat){
    var eo = document.getElementById('ckOpp');
    if(eo){
      eo.innerHTML = opp.length
        ? opp.map(function(o){ return '<div class="ck-opp">' + o.emoji + ' <span>' + esc(o.texte) + '</span></div>'; }).join('')
        : '<div class="ck-vide">Pas d\'opportunité en direct.</div>';
    }
    var ep = document.getElementById('ckProg');
    if(ep){
      ep.innerHTML = prog.map(function(p){
        return '<div class="ck-prog"><span>' + esc(p.label) + '</span><b>' + esc(p.valeur) + '</b></div>';
      }).join('');
    }
    var ee = document.getElementById('ckEtat');
    if(ee){
      ee.innerHTML = etat.map(function(t){
        return '<div class="ck-etat"><span class="ck-dot" data-c="' + esc(t.couleur) + '"></span>' + esc(t.nom) + '</div>';
      }).join('');
    }
  }

  function charger(){
    function grab(u){ return fetch(u).then(function(r){ return r.ok ? r.json() : {}; }).catch(function(){ return {}; }); }
    Promise.all([grab('/data/spots_ranked'), grab('/awards/summary'),
                 grab('/hardware/state'), grab('/dxcc/status'),
                 grab('/awards/prochaines_cibles')])
      .then(function(v){
        _rendre(_opportunites(v[0]), _progression(v[1]), _etat(v[2], v[3]));
        _rendreCibles(v[4] && v[4].cibles);
      });
  }

  global.LogxCockpit = {
    charger: charger,
    _opportunites: _opportunites, _progression: _progression, _etat: _etat,
    _rendre: _rendre, _rendreCibles: _rendreCibles
  };

})(typeof window !== 'undefined' ? window : this);
