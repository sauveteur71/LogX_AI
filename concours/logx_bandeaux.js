// ─── Framework des BANDEAUX DÉFILANTS (ticker HUD) — étape 1 ─────────────────
// Feature F4GLD 26/08/2026 : un ruban défilant d'info AMBIANTE, CONFIGURABLE
// (l'opérateur choisit quels bandeaux voir) et ADAPTÉ À L'ACTIVITÉ (chaque
// page/activité porte son bandeau ; contenu calé sur bande/mode/concours).
//
// CE FICHIER = la MÉCANIQUE PURE, testée en V8 (voir tests/test_bandeaux.py) :
// registre, disponibilité par activité, filtrage live/7-jours, rendu HTML,
// config persistée. Les SOURCES de données réelles (cluster, POTA/SOTA, PSK,
// satellites, calendrier, moteur de score) sont branchées par les pages aux
// étapes 2-3 — jamais ici.
//
// RÈGLES (F4GLD) : diffuser du LIVE en priorité ; DXpéditions filtrées aux
// 7 PROCHAINS JOURS (filtrerExpeditions). GARDE-FOUS (maître-mot « intuitif ») :
// jamais le chemin critique dans le ticker ; pause au survol + items cliquables
// (côté CSS/HTML de la page) ; prefers-reduced-motion arrête le défilement.

(function(global){
  'use strict';

  // Registre : def de bandeau = { id, cat, cls, ico, contextes, construire }.
  //  - contextes : '*' (partout) ou liste d'activités où le bandeau a un sens.
  //  - construire(ctx, donnees) -> [ {texte} | {html, href?, title?} ] : les
  //    items à afficher, CALÉS sur le contexte {activite, band, mode, ...}.
  const REGISTRE = {};

  function enregistrerBandeau(def){
    if(def && def.id) REGISTRE[def.id] = def;
    return def;
  }

  // Bandeaux qui ONT UN SENS pour cette activité (avant tout choix opérateur).
  function bandeauxDisponibles(activite, registre){
    registre = registre || REGISTRE;
    return Object.keys(registre).filter(function(id){
      const c = registre[id].contextes;
      return c === '*' || (Array.isArray(c) && c.indexOf(activite) >= 0);
    });
  }

  // ── RÈGLE DE CONTENU (F4GLD) : ne garder que les DXpéditions des `jours`
  //    prochains jours. Une expé est retenue si elle est EN COURS (debut <= now
  //    <= fin) OU commence dans la fenêtre [now, now + jours]. Date illisible ->
  //    écartée (on n'invente pas de date). Déjà terminée -> écartée.
  function filtrerExpeditions(expes, maintenant, jours){
    jours = (jours == null) ? 7 : jours;
    const now = +maintenant;
    const borneFin = now + jours * 86400000;
    return (expes || []).filter(function(e){
      const deb = Date.parse(e.debut);
      if(isNaN(deb)) return false;
      const finE = e.fin ? Date.parse(e.fin) : deb;
      const finReelle = isNaN(finE) ? deb : finE;
      if(finReelle < now) return false;          // déjà finie
      return deb <= borneFin;                     // commence (ou a commencé) dans la fenêtre
    });
  }

  // ── Config persistée (localStorage) : bandeaux actifs PAR ACTIVITÉ + masque.
  const CLE = 'rc_bandeaux';
  function chargerConfig(){
    try{ return JSON.parse(localStorage.getItem(CLE)) || {}; }
    catch(e){ return {}; }
  }
  function enregistrerConfig(cfg){
    try{ localStorage.setItem(CLE, JSON.stringify(cfg || {})); }catch(e){}
  }
  // Bandeaux actifs pour une activité : choix persisté de l'opérateur, sinon
  // repli sur les défauts de l'activité (doctrine « l'axe = l'activité »).
  function bandeauxActifs(activite, defauts){
    const cfg = chargerConfig();
    if(cfg.parActivite && cfg.parActivite[activite]) return cfg.parActivite[activite];
    return (defauts && defauts[activite]) || [];
  }

  // ── Rendu (PUR) -> chaîne HTML du ticker. esc() protège tout champ réseau
  //    passé en {texte}. Un item {html} est réputé DÉJÀ construit sûr par son
  //    `construire` (qui doit esc() ses propres champs bruts).
  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function rendreTicker(ids, ctx, donnees, registre){
    registre = registre || REGISTRE;
    ctx = ctx || {};
    return (ids || []).map(function(id){
      const def = registre[id];
      if(!def) return '';
      let items = [];
      try{ items = (def.construire ? def.construire(ctx, donnees) : []) || []; }
      catch(e){ items = []; }
      if(!items.length) return '';                // pas de LIVE -> pas de ligne morte
      const cells = items.map(function(it){
        const contenu = (it.html != null) ? it.html : esc(it.texte);
        return '<a class="rcb-item" href="' + esc(it.href || '#')
             + '" title="' + esc(it.title || '') + '">' + contenu + '</a>';
      }).join('');
      // bloc dupliqué -> boucle CSS translateX(-50%) sans couture
      return '<div class="rcb-row"><span class="rcb-cat ' + esc(def.cls || '') + '">'
           + esc(def.cat) + '</span><div class="rcb-track"><div class="rcb-move">'
           + cells + cells + '</div></div></div>';
    }).filter(Boolean).join('');
  }

  const API = {
    enregistrerBandeau: enregistrerBandeau,
    bandeauxDisponibles: bandeauxDisponibles,
    filtrerExpeditions: filtrerExpeditions,
    chargerConfig: chargerConfig,
    enregistrerConfig: enregistrerConfig,
    bandeauxActifs: bandeauxActifs,
    rendreTicker: rendreTicker,
    esc: esc,
    REGISTRE: REGISTRE,
  };
  global.LogxBandeaux = API;
  if(typeof module !== 'undefined' && module.exports) module.exports = API;

})(typeof window !== 'undefined' ? window : this);
