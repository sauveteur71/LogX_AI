// Carte de sortie XOTA — rendu canvas HORS-LIGNE (aucune tuile externe) d'une
// « carte de sortie » partageable en PNG. La carte Leaflet interactive du
// logbook (logx_qso_map.js) reste inchangée : ceci est un rendu DIFFÉRENT,
// dédié au partage, insensible au blocage antivirus (pas de requête réseau au
// dessin). Charge AVANT logx_logbook.js ; ne s'exécute qu'à l'appel, lit
// qsoLog/locLL/myLocator/myCall en toute sécurité (même garantie d'ordre que
// logx_qso_map.js).
//
// Ce fichier expose window.LogxCarteSortie. Les fonctions PURES ci-dessous
// (projection, filtre, position, stats, couleur) sont testées hors DOM
// (py_mini_racer) ; le dessin canvas et l'export PNG (imperatifs, non
// testables en unitaire) viennent après.
(function(){
  'use strict';

  // Palette par bande, alignée sur logx_qso_map.js (BAND_COLORS) pour que la
  // carte de sortie et la carte du logbook parlent le même langage couleur.
  const BAND_COLORS = {
    '1.8':'#FF2D55','3.5':'#FF6B35','7':'#FF9F0A','14':'#FFD60A','21':'#34C759',
    '28':'#00C7BE','50':'#00D4FF','70':'#40C8FF','144':'#BF5AF2','432':'#FF8C00',
    '1296':'#FF2D55','2320':'#00FF88','3400':'#E040FB','default':'#AAAAAA',
  };
  function couleurBande(band){ return BAND_COLORS[band] || BAND_COLORS['default']; }

  // Projection équirectangulaire : lon∈[-180,180]→x∈[0,w], lat∈[90,-90]→y∈[0,h].
  // Trivialement inversible et sans dépendance — le fond de carte embarqué est
  // dessiné dans la MÊME projection, donc rayons et côtes coïncident.
  function projeterEquirect(lat, lon, w, h){
    const x = (Number(lon) + 180) / 360 * w;
    const y = (90 - Number(lat)) / 180 * h;
    return { x: x, y: y };
  }

  // Un QSO appartient-il à CETTE sortie (programme + référence que J'ACTIVE) ?
  // Compare my_sig/my_sig_info (posés par le mode portable). Insensible à la
  // casse (les réf. SOTA/POTA sont normalisées en majuscules).
  function matchSortie(qso, prog, ref){
    if(!qso) return false;
    const p = String(prog || '').toUpperCase();
    const r = String(ref || '').toUpperCase();
    return String(qso.my_sig || '').toUpperCase() === p
        && String(qso.my_sig_info || '').toUpperCase() === r;
  }

  // Position d'une station contactée, pour la tracer :
  //   - locator Maidenhead ≥ 6 → position PRÉCISE (approx:false) ;
  //   - sinon indicatif → centroïde DXCC (approx:true, cty.dat via /dxcc/positions) ;
  //   - sinon null (impossible à placer, ex. indicatif inconnu sans locator).
  // locResolver(locator)->{lat,lon}|null (locLL côté page) ; dxccPos = map
  // {INDICATIF:{lat,lon,country}} renvoyée par l'endpoint serveur.
  function positionStation(qso, dxccPos, locResolver){
    if(!qso) return null;
    const loc = String(qso.locator || '');
    if(loc.length >= 6 && typeof locResolver === 'function'){
      const ll = locResolver(loc);
      if(ll && ll.lat != null && ll.lon != null){
        return { lat: ll.lat, lon: ll.lon, approx: false, source: 'locator' };
      }
    }
    const call = String(qso.call || '').toUpperCase();
    const p = dxccPos && dxccPos[call];
    if(p && p.lat != null && p.lon != null){
      return { lat: p.lat, lon: p.lon, approx: true, source: 'indicatif' };
    }
    return null;
  }

  // Statistiques du bandeau : nb QSO, nb pays DISTINCTS, bandes triées.
  // paysDe(qso)->pays (chaîne) ; '' ou absent = pays inconnu (non compté).
  // Le tri des bandes est NUMÉRIQUE (14 avant 144, pas l'ordre lexical).
  function statsSortie(qsos, paysDe){
    const liste = qsos || [];
    const pays = new Set();
    const bandes = new Set();
    liste.forEach(function(q){
      if(typeof paysDe === 'function'){
        const c = paysDe(q);
        if(c) pays.add(c);
      }
      if(q && q.band) bandes.add(String(q.band));
    });
    const bandesTri = Array.from(bandes).sort(function(a, b){
      return parseFloat(a) - parseFloat(b);
    });
    return { nQso: liste.length, nPays: pays.size, bandes: bandesTri };
  }

  window.LogxCarteSortie = {
    couleurBande: couleurBande,
    projeterEquirect: projeterEquirect,
    matchSortie: matchSortie,
    positionStation: positionStation,
    statsSortie: statsSortie,
    _BAND_COLORS: BAND_COLORS,
  };
})();
