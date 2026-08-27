// ─── BANDEAUX DÉFILANTS — étape 2 : DÉFINITIONS concrètes ────────────────────
// Le framework (logx_bandeaux.js) fournit la MÉCANIQUE (registre, filtre, rendu
// XSS-safe). Ce fichier fournit le CONTENU : des bandeaux câblés sur la forme
// RÉELLE des endpoints du serveur. Chaque `construire(ctx, donnees)` est PUR —
// il transforme des données DÉJÀ récupérées par la page (aucun fetch ici) en
// items {texte, href?, title?}. Testé en V8 (tests/test_bandeaux_defs.py).
//
// RÈGLE DE CONTENU (F4GLD 26/08/2026) : diffuser du LIVE en priorité ;
// DXpéditions bornées aux 7 PROCHAINS JOURS. Une expédition ACTIVE (repérée sur
// le cluster) passe TOUJOURS, même si ses dates NG3K sont illisibles — le live
// prime. Une « à venir » n'entre que si elle commence dans la fenêtre.

(function(global){
  'use strict';

  var LB = global.LogxBandeaux;
  if(!LB || !LB.enregistrerBandeau){
    // Le framework doit être chargé AVANT ce fichier. Sans lui, on ne
    // s'enregistre pas plutôt que de planter la page.
    return;
  }

  var JOUR_MS = 86400000;

  // ── DXpéditions ≤ 7 jours (source : /data/dxpeditions_active) ───────────────
  // donnees.dxpeditions = { expeditions: [ {callsign, entity, dates, status,
  //   starts, ends, freq_khz, spot_band, spot_mode, worked_status, ...} ] }
  // status ∈ 'active' | 'upcoming' | 'ended' | 'unknown' (calculé côté serveur,
  // logx_dxpeditions.fetch_dxpeditions_chasse). starts/ends = ISO 'YYYY-MM-DD'
  // (ou null si dates NG3K illisibles).
  function _dxped(ctx, donnees){
    var src = donnees && donnees.dxpeditions;
    var expes = (src && src.expeditions) ? src.expeditions
              : (Array.isArray(src) ? src : []);
    var now = (ctx && ctx.maintenant != null) ? +ctx.maintenant : Date.now();
    var borne = now + 7 * JOUR_MS;

    var gardees = expes.filter(function(e){
      if(!e) return false;
      if(e.status === 'active') return true;      // LIVE maintenant — priorité absolue
      if(e.status === 'upcoming'){
        var deb = Date.parse(e.starts);
        if(isNaN(deb)) return false;              // pas de date lisible -> écartée (on n'invente pas)
        return deb <= borne;                      // commence dans ≤ 7 jours
      }
      return false;                               // ended / unknown : hors bandeau
    });

    return gardees.map(function(e){
      var actif = e.status === 'active';
      var tete = actif ? '● ' : '△ ';
      var call = e.callsign || '?';
      var lieu = e.entity || call;
      var bout;
      if(actif){
        bout = e.freq_khz
          ? ' · ' + (e.freq_khz / 1000).toFixed(3) + ' MHz'
              + (e.spot_band ? ' (' + e.spot_band + ')' : '')
          : ' · en cours';
      }else{
        bout = ' · ' + (e.dates || 'à venir');
      }
      var neuf = e.worked_status === 'new' ? ' · nouveau pays' : '';
      var item = {
        texte: tete + call + ' · ' + lieu + bout + neuf,
        href: 'logx_chasse.html',
        title: e.dates || ''
      };
      // Item ACTIF -> cliquable « fiche » : la page ouvre un popup (indicatif,
      // fréquence/bande/mode du cluster, QSY...). Les à-venir restent de simples
      // liens : on ne peut pas QSY sur une station pas encore active.
      if(actif){
        item.data = {
          fiche: '1',
          call: call,
          freq: e.freq_khz ? String(e.freq_khz) : '',   // 0/absent -> pas de fréquence (évite « QSY 0 kHz »)
          band: e.spot_band || '',
          mode: e.spot_mode || '',
          entity: e.entity || '',
          neuf: (e.worked_status === 'new') ? '1' : ''
        };
      }
      return item;
    });
  }

  // ── Propagation : bandes exploitables MAINTENANT (source : /data/propagation)
  // donnees.propagation = { etat_bandes: { bandes: [ {band, etat, score,
  //   raison} ], muf_mhz, soleil_deg } } — etat ∈ 'ouverte'|'possible'|
  //   'regional'|'fermee' (logx_paths.etat_bandes_hf). On ne montre que ce qui
  //   est réellement exploitable pour du DX (ouverte/possible) : pas de ligne
  //   morte quand tout est fermé.
  function _propag(ctx, donnees){
    var src = donnees && donnees.propagation;
    var eb = src && src.etat_bandes;
    var bandes = (eb && eb.bandes) ? eb.bandes : [];
    var ouvertes = bandes.filter(function(b){
      return b && (b.etat === 'ouverte' || b.etat === 'possible');
    });
    return ouvertes.map(function(b){
      var pastille = b.etat === 'ouverte' ? '● ' : '◐ ';
      return {
        texte: pastille + b.band + ' m · ' + b.etat,
        title: b.raison || ''
      };
    });
  }

  // ── Spots DX classés (source : /data/spots_ranked) ─────────────────────────
  // donnees.spots_ranked = { spots: [ {call, band, freq(kHz), mode, dx_country,
  //   new_mult, mult_type, credit_raison, credit_score, ...} ], meta } — top ~40
  //   déjà classés par VALEUR côté serveur (logx_scoring.build_ranked_spots). On
  //   montre les mieux classés, bornés pour ne pas noyer le ruban. Badge =
  //   credit_raison (texte serveur lisible : « Nouveau pays ! », « Nouvelle
  //   bande »…) quand credit_score > 0. Chaque item est cliquable (data-fiche)
  //   -> la page ouvre la fiche opérateur (même chemin que les DXpéditions).
  function _spots(ctx, donnees){
    var src = donnees && donnees.spots_ranked;
    var spots = (src && src.spots) ? src.spots
              : (Array.isArray(src) ? src : []);
    var out = [];
    for(var i = 0; i < spots.length && out.length < 15; i++){
      var s = spots[i];
      if(!s || !s.call) continue;
      var bits = [s.call];
      if(s.freq) bits.push((Number(s.freq) / 1000).toFixed(3) + ' MHz');   // 0/absent -> pas de fréquence
      if(s.band) bits.push(String(s.band).match(/m$/i) ? s.band : s.band + ' m');
      if(s.mode) bits.push(s.mode);
      var badge = (s.credit_score && s.credit_raison) ? ' · ' + s.credit_raison : '';
      out.push({
        texte: bits.join(' · ') + badge,
        title: s.dx_country || '',
        href: 'logx_chasse.html',
        data: {
          fiche: '1', call: s.call,
          freq: s.freq ? String(s.freq) : '',   // 0/absent -> pas de fréquence (évite « QSY 0 kHz »)
          band: s.band || '', mode: s.mode || '',
          entity: s.dx_country || '', neuf: ''
        }
      });
    }
    return out;
  }

  LB.enregistrerBandeau({
    id: 'dxped', cat: 'DX ≤7J', cls: 'rcb-dx', contextes: '*',
    construire: _dxped
  });
  LB.enregistrerBandeau({
    id: 'spots', cat: 'SPOTS DX', cls: 'rcb-spots', contextes: '*',
    construire: _spots
  });
  LB.enregistrerBandeau({
    id: 'propag', cat: 'PROPAG', cls: 'rcb-propag', contextes: '*',
    construire: _propag
  });

})(typeof window !== 'undefined' ? window : this);
