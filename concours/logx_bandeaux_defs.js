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

  // ── Libellé de bande LISIBLE ───────────────────────────────────────────────
  // Les endpoints envoient la bande en CLÉ INTERNE = MHz ('7', '14', '21' —
  // logx_paths.etat_bandes_hf, logx_scoring._band_from_freq), PAS en mètres.
  // Défaut corrigé (signalé par plusieurs utilisateurs, 23/10/2026) : la clé
  // était affichée suivie de « m » -> « 21 m », « 28 m », bandes inexistantes,
  // et « 10 m » pour 10 MHz qui est en réalité la bande des 30 m. Table reprise
  // de BAND_LABELS (logx_logbook.js), + '10' (clé de logx_paths pour 30 m) et
  // '5' (60 m, clé de _band_from_freq). Une valeur déjà en mètres/cm ('20m')
  // est gardée telle quelle ; une clé inconnue est montrée en MHz (on n'invente
  // pas de longueur d'onde).
  var LIB_BANDES = {
    '1.8':'160 m', '3.5':'80 m', '5':'60 m', '7':'40 m', '10':'30 m', '10.1':'30 m',
    '14':'20 m', '18':'17 m', '21':'15 m', '24':'12 m', '28':'10 m',
    '50':'6 m', '70':'4 m', '144':'2 m', '432':'70 cm', '1296':'23 cm',
    '2320':'13 cm', '3400':'9 cm', '5760':'6 cm', '10368':'3 cm',
    '24048':'1,2 cm', '47088':'6 mm'
  };
  function _libBande(b){
    var s = String(b == null ? '' : b).trim();
    if(!s) return '';
    var m = s.match(/^(\d+(?:[.,]\d+)?)\s*(m|cm|mm)$/i);
    if(m) return m[1] + ' ' + m[2].toLowerCase();       // déjà une longueur d'onde
    if(LIB_BANDES[s]) return LIB_BANDES[s];
    var f = parseFloat(s.replace(',', '.'));
    if(!isNaN(f)){
      for(var k in LIB_BANDES){ if(parseFloat(k) === f) return LIB_BANDES[k]; }   // '7.0' == '7'
      return s + ' MHz';
    }
    return s;                                            // 'HF' & co : tel quel
  }
  // Exposé pour les autres modules (filtre de bandes de CHASSE) : une seule
  // table de libellés plutôt qu'une copie par page.
  LB.libBande = _libBande;

  // Type de multiplicateur (identifiant INTERNE de logx_scoring : 'zone_cq',
  // 'grand_carre'…) -> libellé lisible. Inconnu -> underscores remplacés.
  var LIB_MULTS = {
    locator:'locator', grand_carre:'grand carré', zone_cq:'zone CQ', zone_itu:'zone ITU',
    dxcc:'pays DXCC', prefix:'préfixe', dept_dxcc:'département/pays',
    section_na:'section ARRL', etat_province:'état/province', comte_ha:'comté HA'
  };
  function _libMult(t){
    var s = String(t == null ? '' : t);
    return LIB_MULTS[s] || s.replace(/_/g, ' ');
  }

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
              + (e.spot_band ? ' (' + _libBande(e.spot_band) + ')' : '')
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
    // ADAPTATION BANDE : la bande en cours de saisie (ctx.band) passe EN TÊTE et
    // est marquée « ta bande ». Comparaison sur le LIBELLÉ normalisé : la page
    // donne currentBand en clé MHz ('14', '10.1') comme le serveur ('14', '10'),
    // et '20m' reste accepté -> '14' = '20m' = '20 m'.
    var courante = (ctx && ctx.band != null) ? _libBande(ctx.band) : '';
    var items = ouvertes.map(function(b){
      var lib = _libBande(b.band);
      var est = !!courante && lib === courante;
      var pastille = b.etat === 'ouverte' ? '● ' : '◐ ';
      return {
        _c: est,
        texte: (est ? '▸ ' : '') + pastille + lib + ' · ' + b.etat + (est ? ' · ta bande' : ''),
        title: b.raison || ''
      };
    });
    // href : un clic mène à la page PROPAG (sans href, le lien '#' renvoyait
    // en haut de la page de saisie).
    var tete = [], reste = [];
    items.forEach(function(it){ (it._c ? tete : reste).push({ texte: it.texte, title: it.title, href: 'logx_propagation.html' }); });
    return tete.concat(reste);   // bande courante d'abord, reste dans l'ordre d'origine
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
      if(s.band) bits.push(_libBande(s.band));
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
    id: 'dxped', cat: 'DX ≤7J', cls: 'rcb-dx', contextes: ['hf'],
    construire: _dxped
  });
  // ── Multiplicateurs à chercher (CONCOURS uniquement) ───────────────────────
  // Réutilise /data/spots_ranked (déjà classé côté serveur), filtré aux spots
  // marqués new_mult=true : les NOUVEAUX multiplicateurs repérés sur le cluster.
  // contextes:['concours'] -> n'apparaît qu'en mode concours (doctrine : « le
  // score/mult n'a rien à faire à l'écran hors concours »). Item cliquable ->
  // fiche (même chemin que spots/DXpéditions).
  function _mults(ctx, donnees){
    var src = donnees && donnees.spots_ranked;
    var spots = (src && src.spots) ? src.spots
              : (Array.isArray(src) ? src : []);
    var out = [];
    for(var i = 0; i < spots.length && out.length < 12; i++){
      var s = spots[i];
      if(!s || !s.call || !s.new_mult) continue;   // uniquement les NOUVEAUX multiplicateurs
      var bits = [s.call];
      if(s.mult_type) bits.push(_libMult(s.mult_type));
      if(s.freq) bits.push((Number(s.freq) / 1000).toFixed(3) + ' MHz');
      if(s.band) bits.push(_libBande(s.band));
      out.push({
        texte: '★ ' + bits.join(' · '),
        title: s.dx_country || '',
        href: 'logx_chasse.html',
        data: {
          fiche: '1', call: s.call,
          freq: s.freq ? String(s.freq) : '',
          band: s.band || '', mode: s.mode || '',
          entity: s.dx_country || '', neuf: ''
        }
      });
    }
    return out;
  }

  LB.enregistrerBandeau({
    id: 'spots', cat: 'SPOTS DX', cls: 'rcb-spots', contextes: '*',
    construire: _spots
  });
  LB.enregistrerBandeau({
    id: 'mults', cat: 'MULTS', cls: 'rcb-mults', contextes: ['concours'],
    construire: _mults
  });
  LB.enregistrerBandeau({
    id: 'propag', cat: 'PROPAG', cls: 'rcb-propag', contextes: ['hf'],
    construire: _propag
  });

})(typeof window !== 'undefined' ? window : this);
