// EV-7 39e increment : SCORING PILOTE PAR LE SERVEUR (miroir client des briques)
// -- extrait de logx_logbook.js (docs/LogX_AI_PRD.md). Charge en <script>
// classique dans logx_logbook.html, AVANT logx_logbook.js -- portee globale
// partagee (comme tous les fichiers EV-7). Distinct de logx_scoring.py (serveur).
//
// Contient : loadScoringDefs (lit les definitions de /data/calendar), formatDepot
// (format de depot depuis le reglement), _brickCtx, _signalerPredicatInconnu /
// _bandeauPredicatInconnu, evalPointsFromDef, calcPoints, calcDist. AUCUNE n'est
// appelee au TOP-LEVEL de logbook.js. Dependances runtime : lookupDXCC
// (logx_dxcc_lookup.js), hav()/locLL() (coeur logbook.js) -- appels a l'usage,
// donc l'ordre relatif des <script> est indifferent.

// ─── SCORING PILOTÉ PAR LE SERVEUR (briques) ─────────────────────────────────
// Le logbook lit les définitions de scoring de /data/calendar (moteur à briques
// de logx_scoring.py) au lieu de dupliquer les barèmes en dur : tout
// concours de la base — y compris ceux analysés par l'IA — est scoré juste.
// La table codée en dur plus bas ne sert plus que de repli hors-ligne.
let contestScoringDefs = {};   // id concours → bloc scoring (type/params/bricks)
// Les règles de DÉPÔT du concours (format du fichier, adresse, date limite).
// Elles voyagent déjà dans /data/calendar mais n'étaient conservées nulle part :
// l'export retombait sur une liste d'identifiants écrite à la main.
let contestDepotDefs = {};     // id concours → {log_format, log_submit, log_deadline}

async function loadScoringDefs(){
  try{
    const res = await fetch('/data/calendar');
    const data = await res.json();
    (data.contests || []).forEach(c => {
      if (c.scoring) contestScoringDefs[c.id] = c.scoring;
      contestDepotDefs[c.id] = {log_format: c.log_format || '',
                                log_submit: c.log_submit || '',
                                log_deadline: c.log_deadline || ''};
    });
    console.log(`[SCORING] ${Object.keys(contestScoringDefs).length} barèmes chargés du serveur`);
  }catch(e){ console.warn('[SCORING] serveur indisponible, barèmes locaux :', e); }
}

// ── LE FORMAT DE DÉPÔT VIENT DU RÈGLEMENT, PAS D'UNE LISTE ÉCRITE À LA MAIN ──
// Le routage se faisait sur HF_CONTESTS, douze identifiants codés en dur, alors
// que VINGT-SIX définitions déclarent `log_format: 'CABRILLO'`. Mesuré sur la
// base livrée : dix-sept concours Cabrillo — WAEDC CW/SSB/RTTY, ARRL 10 m et
// 160 m, Russian DX, EU HF Championship, All Asian, Stew Perry, UBA, SP, HA,
// REF 160 m, les deux UFT Challenge — tombaient dans la branche EDI et
// n'obtenaient AUCUN fichier : « Aucun QSO VHF/UHF à exporter ». Au moment du
// dépôt, veille de date limite. Trois identifiants de cette liste n'existaient
// même pas (IARU_HF, WAE_CW, WAE_SSB : les vrais sont WAEDC_*).
const REPLI_FORMAT_DEPOT = {EDI: 'EDI', CABRILLO: 'CABRILLO', ADIF: 'ADIF'};

function formatDepot(contestId){
  const d = contestDepotDefs[contestId || currentContest] || {};
  const f = REPLI_FORMAT_DEPOT[String(d.log_format || '').toUpperCase()];
  if (f) return f;
  // Définition muette (3 sur 41) ou serveur injoignable au moment du clic :
  // on déduit des bandes RÉELLEMENT présentes dans le log plutôt que de
  // deviner d'après l'identifiant. L'EDI est le format des concours THF.
  return estConcoursThf() ? 'EDI' : 'CABRILLO';   // BANDES_THF, plus bas
}

// Presets points-only des types historiques — miroir de LEGACY_SCORING_PRESETS
// (logx_scoring.py), briques 'points'/'validity'/'same_square_points'.
const LEGACY_JS_BRICKS = {
  km:                        {points:[{points:'per_km'}]},
  km_x_locators:             {points:[{points:'per_km'}]},
  km_x_large_locator_squares:{points:[{points:'per_km'}], same_square_points:{param:'same_square_bonus', default:50}},
  zone_country_per_band:     {points:[{when:'same_country', points:{param:'points_same_country', default:0}},
                                      {when:'same_continent', points:{param:'points_same_continent', default:1}},
                                      {points:{param:'points_dx', default:3}}]},
  // CQ WPX (règlement cqwpx.com/rules.htm) : points DOUBLÉS sur les bandes
  // basses 160/80/40 m (6/2/1 au lieu de 3/1/1) — miroir du fix serveur
  // (logx_definitions.py CQ_WPX_SSB/CW.scoring.bricks). Repli hors-ligne
  // uniquement : quand le serveur répond, calcPoints() utilise directement
  // les bricks transmis par /data/calendar (voir evalPointsFromDef ci-dessous).
  prefix_multiplier:         {points:[{bands:['1.8','3.5','7'], when:'different_continent', points:6},
                                      {bands:['1.8','3.5','7'], when:'same_country', points:{param:'points_same_country', default:1}},
                                      {bands:['1.8','3.5','7'], points:2},
                                      {when:'different_continent', points:{param:'points_dx', default:3}},
                                      {when:'same_country', points:{param:'points_same_country', default:1}},
                                      {points:{param:'points_same_continent', default:1}}]},
  prefix:                    {points:[{when:'different_continent', points:6},
                                      {when:'na_w_ve', points:2}, {points:1}]},
  power_state:               {points:[{points:{param:'points', default:3}}], validity:'is_na'},
  fd_class:                  {points:[{modes:['CW'], points:{param:'points_cw', default:2}},
                                      {modes:['FT8','FT4','RTTY','PSK'], points:{param:'points_digital', default:2}},
                                      {points:{param:'points_phone', default:1}}], validity:'is_na'},
  dept_dxcc:                 {points:[{when:'is_french', points:1}, {points:3}]},
  summit_points:             {points:[{points:{param:'points', default:1}}]},
  park_points:               {points:[{points:{param:'points', default:1}}]},
  // World Wide Award (hamaward.cloud) : points fixes par mode — miroir de
  // LEGACY_SCORING_PRESETS['wwa_sprint'] (logx_scoring.py). validity.roster_check
  // n'est PAS vérifiable côté client (pas de re-fetch réseau à chaque frappe) :
  // retour optimiste ici, le serveur (need-list /data/spots_ranked) reste seul
  // juge de la validité réelle d'une station.
  wwa_sprint:                {points:[{modes:['CW'], points:10},
                                      {modes:['SSB','USB','LSB','FM'], points:5},
                                      {modes:['FT8','FT4','FT2'], points:2},
                                      {modes:['RTTY','PSK','DIGI'], points:5},
                                      {points:5}],
                              validity:{roster_check:'wwa'}},
};

const _NA_CALL_RE = /^(W|K|N|AA|AB|AC|AD|AE|AF|AG|AH|AI|AJ|AK|WA|WB|WC|WD|WE|WF|WG|WH|WI|WJ|WK|WL|WM|WN|WO|WP|WQ|WR|WS|WT|WU|WV|WW|WX|WY|WZ|KA|KB|KC|KD|KE|KF|KG|KH|KI|KJ|KK|KL|KM|KN|KO|KP|KQ|KR|KS|KT|KU|KV|KW|KX|KY|KZ|NA|NB|NC|ND|NE|NF|NG|NH|NI|NJ|NK|NL|NM|NN|NO|NP|NQ|NR|NS|NT|NU|NV|NW|NX|NY|NZ|VE|VA|VO|VY)/i;

function _brickCtx(callDX){
  const dxBase = (callDX || '').toUpperCase().split('/')[0];
  const myBase = (myCall || '').toUpperCase().split('/')[0];
  const dxInfo = lookupDXCC(dxBase), myInfo = lookupDXCC(myBase);
  return {
    dxBase,
    myBase,
    dxCountry: dxInfo ? dxInfo.c : (dxBase.slice(0,2) || '??'),
    myCountry: myInfo ? myInfo.c : (myBase.slice(0,2) || 'F'),
    dxCont: (dxInfo && dxInfo.ct) || 'EU',
    myCont: (myInfo && myInfo.ct) || 'EU',
    // Miroir de logx_scoring.py:calc_qso_value dx_maritime_mobile — suffixe
    // '/MM' de l'indicatif BRUT (pas dxBase, qui l'a déjà retiré au même
    // titre que /P ou /QRP).
    dxMaritimeMobile: (callDX || '').trim().toUpperCase().endsWith('/MM'),
  };
}

// A05 (docs/FEUILLE_DE_ROUTE.md) : signale bruyamment un prédicat de barème
// inconnu du miroir JS au lieu de retomber en silence sur 'always' (= QSO
// toujours valide/plein pot) -- un score client faux EN DIRECT pendant un
// concours, sans rien pour le signaler, était le vrai défaut. `_predicatsInconnusVus`
// évite de spammer la console à chaque QSO pour le MÊME prédicat manquant.
const _predicatsInconnusVus = new Set();
function _signalerPredicatInconnu(nom){
  if (_predicatsInconnusVus.has(nom)) return;
  _predicatsInconnusVus.add(nom);
  console.error(`[SCORING] Prédicat de barème inconnu du miroir JS : '${nom}' — ` +
    'le score CLIENT peut être faux pour ce concours (le serveur, ' +
    'autoritaire, reste correct). Voir BRICK_PREDICATES (logx_logbook.js) ' +
    'et son équivalent PREDICATES (logx_scoring.py).');
  try{ _bandeauPredicatInconnu(nom); }catch(e){}
}
// Bandeau visuel, même mécanisme que _confirmDupBanner (pas de dépendance à
// une zone d'affichage du score précise, qui varie selon la page/le layout) :
// un texte discret mais visible tant qu'au moins un prédicat inconnu a été
// rencontré cette session, plutôt qu'un score qui a l'air normal.
// Drapeau dédié (pas un test getElementById()) : dans un DOM minimal/stub,
// getElementById() peut créer l'élément à la lecture -- un test sur son
// existence ne détecterait alors jamais "pas encore affiché".
let _bandeauPredicatInconnuAffiche = false;
function _bandeauPredicatInconnu(nom){
  if (_bandeauPredicatInconnuAffiche) return;   // déjà affiché, un seul suffit
  _bandeauPredicatInconnuAffiche = true;
  const el = document.createElement('div');
  el.id = 'scoringPredicatInconnuBanner';
  el.style.cssText = 'position:fixed;bottom:8px;right:8px;z-index:9999;' +
    'background:var(--red,#FF2D55);color:#fff;font-family:var(--font-mono,monospace);' +
    'font-size:11px;padding:6px 10px;border-radius:6px;max-width:320px;' +
    'box-shadow:0 2px 8px rgba(0,0,0,.3)';
  el.textContent = `⚠ Score affiché possiblement faux (barème '${nom}' non reconnu) — le score serveur reste correct`;
  (document.body || document.documentElement).appendChild(el);
}

const BRICK_PREDICATES = {
  always:              () => true,
  same_country:        x => x.dxCountry === x.myCountry,
  same_continent:      x => x.dxCont === x.myCont,
  different_continent: x => x.dxCont !== x.myCont,
  // CTY_PREFIX (logx_dxcc_lookup.js) distingue déjà France/DOM-TOM par
  // préfixe (c:'France' pour F/TM, c:'Martinique' pour FM, etc.) — un simple
  // /^F/ confondait les DOM-TOM avec la France métropolitaine (même bug que
  // le miroir serveur, logx_scoring.py PREDICATES.is_french). TK (Corse)
  // n'est pas dans cette table encore incomplète (voir finding dédié table
  // DXCC client) : repli explicite sur le préfixe pour ce seul cas.
  is_french:           x => x.dxCountry === 'France' || /^TK/.test(x.dxBase),
  // France métropolitaine + DOM-TOM (contrairement à is_french ci-dessus,
  // strictement métropole) — miroir de logx_scoring.py PREDICATES.
  // is_french_all/my_is_french_all (mêmes 13 entités DXCC : F/TK/FG/FM/FJ/
  // FS/FP/FY/FO/FK/FW/FH/FR). 9 des 13 sont dans CTY_PREFIX (logx_dxcc_lookup.js)
  // sous leur nom français (Martinique, Guadeloupe, Guyane fr....) ; TK/FJ/FS/FW
  // en sont absents (même lacune déjà documentée pour is_french/TK ci-dessus,
  // pas une régression de ce correctif) : repli explicite sur le préfixe,
  // même motif que TK dans is_french.
  is_french_all:       x => ['France','Martinique','Guadeloupe','Guyane fr.','La Réunion',
                             'Nvl-Calédonie','Polynésie fr.','St-Pierre-Miquelon','Mayotte']
                             .includes(x.dxCountry) || /^(TK|FJ|FS|FW)/.test(x.dxBase),
  my_is_french_all:    x => ['France','Martinique','Guadeloupe','Guyane fr.','La Réunion',
                             'Nvl-Calédonie','Polynésie fr.','St-Pierre-Miquelon','Mayotte']
                             .includes(x.myCountry) || /^(TK|FJ|FS|FW)/.test(x.myBase),
  is_maritime_mobile:  x => x.dxMaritimeMobile,
  is_na:               x => _NA_CALL_RE.test(x.dxBase),
  na_w_ve:             x => /^(W|K|N|VE|XE)/.test(x.dxBase),
  is_asia:             x => x.dxCont === 'AS',
  is_eu:               x => x.dxCont === 'EU',
};

// Évalue les points d'un QSO depuis un bloc scoring serveur.
// Retourne un nombre, ou null si le bloc est inexploitable (→ repli local).
function evalPointsFromDef(scoring, callDX, band, mode, dist, locDX, myLoc){
  const bricks = scoring.bricks || LEGACY_JS_BRICKS[scoring.type];
  if (!bricks || !Array.isArray(bricks.points)) return null;
  const ctx = _brickCtx(callDX);

  // Brique validité : nom de prédicat, {prefix_in:[...]}, ou {roster_check:...}
  // (roster externe publié — ex. WWA — non vérifiable ici sans réseau : on
  // reste optimiste côté client, le serveur reste l'arbitre réel).
  const v = bricks.validity;
  if (v){
    let ok;
    if (typeof v === 'object' && v.prefix_in){
      ok = v.prefix_in.some(p => ctx.dxBase.startsWith(p.toUpperCase()));
    } else if (typeof v === 'object' && v.roster_check){
      ok = true;
    } else {
      if (!BRICK_PREDICATES[v]) _signalerPredicatInconnu(v);
      ok = (BRICK_PREDICATES[v] || BRICK_PREDICATES.always)(ctx);
    }
    if (!ok) return 0;
  }

  // Points fixes "même grand carré" (IARU)
  const ssp = bricks.same_square_points;
  if (ssp !== undefined && ssp !== null){
    const large = l => (l && l.length >= 4) ? l.slice(0,4).toUpperCase() : null;
    const mySq = large(myLoc || myLocator);
    if (mySq !== null && mySq === large(locDX)){
      return (typeof ssp === 'object') ? (scoring[ssp.param] ?? ssp.default ?? 50) : ssp;
    }
  }

  // Règles de points ordonnées : filtres bands/modes/prefix_in + prédicat when
  const bandNorm = String(band || '').replace(' MHz','').replace(' GHz','').trim();
  const modeNorm = String(mode || '').toUpperCase();
  for (const rule of bricks.points){
    if (rule.bands && !rule.bands.includes(bandNorm)) continue;
    if (rule.modes && !rule.modes.map(m => m.toUpperCase()).includes(modeNorm)) continue;
    if (rule.prefix_in && !rule.prefix_in.some(p => ctx.dxBase.startsWith(p.toUpperCase()))) continue;
    // 'when' : un nom de prédicat, OU une liste combinée en ET logique (ex.
    // REF : ['my_is_french_all','is_french_all','same_continent']) — miroir
    // de logx_scoring.py:calc_qso_value. Le simple `BRICK_PREDICATES[rule.when]`
    // d'avant ce correctif indexait avec un TABLEAU converti en chaîne
    // ("a,b,c"), toujours absent de la table -> repli 'always' silencieux :
    // TOUTE règle à when combiné (le format des barèmes REF) était donc déjà
    // acquise sans condition, dès que bande/mode/prefix_in passaient.
    const whenList = Array.isArray(rule.when) ? rule.when : [rule.when || 'always'];
    const whenOk = whenList.every(w => {
      if (!BRICK_PREDICATES[w]) _signalerPredicatInconnu(w);
      return (BRICK_PREDICATES[w] || BRICK_PREDICATES.always)(ctx);
    });
    if (!whenOk) continue;
    let val = rule.points;
    if (val && typeof val === 'object') val = scoring[val.param] ?? val.default ?? 0;
    if (val === 'per_km') return dist;
    return (typeof val === 'number') ? val : 0;
  }
  return 0;
}

// myLoc (optionnel) : locator à utiliser pour la distance/le calcul, au lieu
// du global `myLocator` (position ACTUELLE de l'opérateur). Nécessaire pour
// recalculer le score d'un QSO déjà loggué avec SA position d'origine
// (q.my_locator) — sinon un rover/expédition qui change de locator en cours
// de concours voit son score rétroactivement faussé pour tous ses anciens
// QSO (voir updateStats()).
function calcPoints(locDX, band, callDX, mode, myLoc){
  const myLL = locLL(myLoc || myLocator);
  const dxLL = locDX ? locLL(locDX) : null;
  const dist = (myLL && dxLL) ? hav(myLL.lat,myLL.lon,dxLL.lat,dxLL.lon) : 0;

  // 1er choix : le barème du serveur (briques) — couvre TOUS les concours,
  // y compris ceux ajoutés par analyse IA, et ne requiert un locator que
  // pour les barèmes à distance
  const def = contestScoringDefs[currentContest];
  if (def){
    const pts = evalPointsFromDef(def, callDX, band, mode, dist, locDX, myLoc);
    if (pts !== null) return pts;
  }

  // ── Repli local historique (serveur injoignable) ──────────────────────────
  if(!myLL||!dxLL) return 0;

  // Scoring selon le concours actif
  const c = currentContest || '';

  // ── HF nord-américains : pts fixes par mode ───────────────────────────────
  if(['ARRL_FD','ARRL_DX_SSB','ARRL_DX_CW'].includes(c)){
    const NA_PFX = /^(W|K|N|AA|AB|AC|AD|AE|AF|AG|AH|AI|AJ|AK|WA|WB|WC|WD|WE|WF|WG|WH|WI|WJ|WK|WL|WM|WN|WO|WP|WQ|WR|WS|WT|WU|WV|WW|WX|WY|WZ|KA|KB|KC|KD|KE|KF|KG|KH|KI|KJ|KK|KL|KM|KN|KO|KP|KQ|KR|KS|KT|KU|KV|KW|KX|KY|KZ|NA|NB|NC|ND|NE|NF|NG|NH|NI|NJ|NK|NL|NM|NN|NO|NP|NQ|NR|NS|NT|NU|NV|NW|NX|NY|NZ|VE|VA|VO|VY)/i;
    // Station hors NA = 0 pt (les deux barèmes ci-dessous)
    if(callDX && !NA_PFX.test(callDX)) return 0;
    if(c === 'ARRL_FD'){
      // ARRL FD : SSB=1pt, CW=2pts, Digital=2pts
      const m = (mode||'SSB').toUpperCase();
      return m==='CW'?2 : (m==='FT8'||m==='FT4'||m==='RTTY'||m==='PSK')?2 : 1;
    }
    // ARRL DX (SSB/CW) : 3 points fixes par QSO, quel que soit le mode —
    // contrairement à ARRL FD, groupée à tort avec ce même barème par mode
    // avant ce correctif.
    return 3;
  }

  // ── CQ WW : 0/1/3 pts selon continent ────────────────────────────────────
  if(['CQ_WW_SSB','CQ_WW_CW'].includes(c)){
    if(!callDX) return 3;
    const CONTINENT = {F:'EU',G:'EU',DL:'EU',ON:'EU',PA:'EU',W:'NA',K:'NA',N:'NA',VE:'NA',JA:'AS',PY:'SA',VK:'OC',ZS:'AF'};
    const pfx2 = (callDX||'').slice(0,2).toUpperCase();
    const pfx1 = (callDX||'').slice(0,1).toUpperCase();
    const myPfx = (myCall||'F').slice(0,1).toUpperCase();
    const dxCont = CONTINENT[pfx2]||CONTINENT[pfx1]||'EU';
    const myCont = CONTINENT[myPfx]||'EU';
    const myCtry = (myCall||'').slice(0,2).toUpperCase();
    const dxCtry = (callDX||'').slice(0,2).toUpperCase();
    if(myCtry===dxCtry) return 0;
    if(myCont===dxCont) return 1;
    return 3;
  }

  // ── CQ WPX : 2-6 pts selon continent ─────────────────────────────────────
  if(['CQ_WPX_SSB','CQ_WPX_CW'].includes(c)){
    if(!callDX) return 3;
    const CONT = {F:'EU',G:'EU',DL:'EU',ON:'EU',W:'NA',K:'NA',N:'NA',VE:'NA',JA:'AS',PY:'SA',VK:'OC',ZS:'AF'};
    const myCont = CONT[(myCall||'F').slice(0,1).toUpperCase()]||'EU';
    const dxCont = CONT[(callDX||'').slice(0,2).toUpperCase()]||CONT[(callDX||'').slice(0,1).toUpperCase()]||'EU';
    if(myCont!==dxCont) return 6;
    if(/^(W|K|N|VE|XE)/.test(callDX||'')) return 2;
    return 1;
  }

  // ── REF HF : 1pt franco / 3pts DX ────────────────────────────────────────
  if(['REF_CDF_HF_SSB','REF_CDF_HF_CW','IARU_HF'].includes(c)){
    if(!callDX) return 1;
    if(/^(F|TM)/.test(callDX||'')) return 1;
    return 3;
  }

  // ── VHF/UHF (REF RPH, IARU VHF, EU VHF) : 1pt/km ───────────────────────
  return dist;
}

function calcDist(locDX){
  const myLL = locLL(myLocator);
  const dxLL = locLL(locDX);
  if(!myLL||!dxLL) return 0;
  return hav(myLL.lat,myLL.lon,dxLL.lat,dxLL.lon);
}
