// EV-7 phase 2 (docs/LogX_AI_PRD.md) -- 23e increment : EXPORT ADIF + CSV,
// extrait tel quel de logx_logbook.js. Charge en <script> classique dans
// logx_logbook.html AVANT logx_logbook.js, portee globale partagee (meme
// convention que les 22 increments precedents). Candidat identifie par un
// 2e inventaire Workflow complet (le 1er, au 16e increment, avait epuise ses
// candidats FAIBLE) -- voir memoire projet inventaire-ev7-23e-2026-08-09.md.
//
// Contenu : ADIF_BAND/ADIF_BAND_OFFICIELLES (tables), adifBandLabel(),
// adifField(), ADIF_STD_TAGS, buildAdifText(), downloadAdifBlob(),
// exportADIF(), exportCSV().
//
// Grep exhaustif fait AVANT extraction : aucun appel top-level restant dans
// logx_logbook.js ne depend d'un symbole de ce fichier. Les seuls sites
// d'usage externes sont : itemsMenuLogbook() (logx_logbook.js, dispatch
// generique window[fn]() du menu, en corps de fonction) et
// logx_filter_builder.js (deja extrait, fltExportFiltered() appelle
// downloadAdifBlob(buildAdifText(qsos), 'filtre') en corps de fonction --
// les deux symboles utilises restent ensemble dans CE fichier, donc aucune
// dependance croisee introduite).
//
// ATTENTION distincte de ADIF_BAND (Python, logx_export.py) : c'est une
// table JUMELLE en JS, PAS le meme objet -- un correctif d'une doit se
// refleter dans l'autre (voir le commentaire d'origine sur adifBandLabel()).
// Ne pas confondre non plus avec BAND_LABELS (table d'AFFICHAGE, restee
// dans logx_logbook.js) : deux entrees y portent le nom d'usage et non le
// libelle ADIF officiel.
//
// Dependance optionnel->coeur (sens autorise, fonctions seulement) :
// qsoLog, isValidQSO, myCall, myLocator, _resolveOperatorCallsign,
// _confirmDupBanner (bandeau non bloquant, definie dans logx_logbook.js),
// trF, notify.

// ─── EXPORT ADIF ─────────────────────────────────────────────────────────────
// <BAND> attend un LIBELLÉ de l'énumération Band d'ADIF ('20m', '2m', '70cm'),
// jamais une fréquence. La bande interne du log étant la fréquence en MHz
// ('14', '144', '3.5'), elle doit être TRADUITE : coller un 'M' à la valeur
// interne produisait <BAND>14M / <BAND>144M, refusé par TQSL/LoTW, eQSL et
// Club Log sur les 20 bandes gérées.
// Table jumelle de logx_export.ADIF_BAND (version Python, /log/export/adif).
// Ne PAS réutiliser BAND_LABELS : c'est une table d'AFFICHAGE, dont deux
// entrées (24048 → '6mm', 47088 → '4mm') portent le nom d'usage et non le
// libellé ADIF officiel ('1.25cm' et '6mm').
const ADIF_BAND = {
  '1.8':'160m','3.5':'80m','7':'40m','10.1':'30m','14':'20m','18':'17m',
  '21':'15m','24':'12m','28':'10m','50':'6m','70':'4m','144':'2m',
  '432':'70cm','1296':'23cm','2320':'13cm','3400':'9cm','5760':'6cm',
  '10368':'3cm','24048':'1.25cm','47088':'6mm',
};
// Libellés ADIF officiels (ADIF 3.1.7, cf. logx_adif_enums.ADIF_BANDS). Un QSO
// IMPORTÉ conserve tel quel le libellé ADIF quand sa bande sort de notre table
// interne (60m, 2190m, 1mm… — voir logx_qsl._band_from_record) : il est alors
// DÉJÀ valide et doit ressortir intact, surtout pas suffixé ('1mmM').
const ADIF_BAND_OFFICIELLES = new Set([
  '2190m','630m','560m','160m','80m','60m','40m','30m','20m','17m','15m',
  '12m','10m','8m','6m','5m','4m','2m','1.25m','70cm','33cm','23cm','13cm',
  '9cm','6cm','3cm','1.25cm','6mm','4mm','2.5mm','2mm','1mm','submm',
]);
// Bande interne → libellé ADIF, '' si intraduisible (le champ est alors OMIS :
// une valeur hors énumération fait rejeter tout l'enregistrement).
function adifBandLabel(band){
  const raw = String(band == null ? '' : band).trim();
  if(!raw) return '';
  if(ADIF_BAND[raw]) return ADIF_BAND[raw];
  const bas = raw.toLowerCase();
  return ADIF_BAND_OFFICIELLES.has(bas) ? bas : '';
}
// Un champ ADIF : <NOM:longueur>valeur. Valeur vide = champ absent.
function adifField(name, value){
  const v = String(value == null ? '' : value).trim();
  return v ? `<${name}:${v.length}>${v} ` : '';
}

// Construit le texte ADIF pour une liste de QSO donnée — factorisé pour être
// réutilisé par l'export complet (exportADIF) et l'export filtré
// (fltExportFiltered), sans dupliquer le corps du générateur.
const ADIF_STD_TAGS = new Set(['CALL','QSO_DATE','TIME_ON','BAND','FREQ','MODE','RST_SENT',
  'RST_RCVD','STX_STRING','SRX_STRING','GRIDSQUARE','MY_GRIDSQUARE','STATION_CALLSIGN',
  'OPERATOR','CONTEST_ID','ADIF_VER','PROGRAMID',
  // Sous-chantier B : alignés sur logx_export._ADIF_STD_TAGS (jumeaux).
  'NAME','QTH','STATE','COMMENT','DISTANCE','PROP_MODE','SAT_NAME',
  // SUBMODE VOLONTAIREMENT absent : buildAdifText ne l'émet que pour FT2
  // (MODE=MFSK+SUBMODE=FT2) ; l'inscrire ici faisait sauter un SUBMODE=JS8/FT4
  // conservé dans extra_fields -> perte au re-export (correctif de revue).
  'MY_SIG','MY_SIG_INFO','SIG','SIG_INFO',
  // Lot 2 : clés de la refonte de saisie (A).
  'TX_PWR','FREQ_RX','CQZ','ITUZ','CNTY','EMAIL','QSL_VIA','ANT_AZ','TIME_OFF',
  'QSL_SENT','LOTW_QSL_SENT','EQSL_QSL_SENT','APP_LOGX_OPERATING',
  // Lot 3 : tags dédiés multi-références (two-fer).
  'SOTA_REF','MY_SOTA_REF','POTA_REF','MY_POTA_REF','WWFF_REF','MY_WWFF_REF',
  'IOTA','MY_IOTA']);

// Tag ADIF DÉDIÉ par programme d'activation (spec ADIF 3.1.5, adif.org/315 :
// SOTA_REF/POTA_REF/WWFF_REF et IOTA — ce dernier SANS suffixe _REF). Jumeau
// de logx_activation.ADIF_PROGRAM_TAGS (Python, source unique) : la parité est
// figée par tests/test_adif_refs_multiples.py. ARLHS/WCA : pas de tag dédié
// -> mécanisme générique SIG (my_refs[0]), aucun tag inventé.
const REF_ADIF_TAGS = {POTA:'POTA_REF', SOTA:'SOTA_REF', WWFF:'WWFF_REF', IOTA:'IOTA'};

// Références (programme, ref) à émettre en tags dédiés. Préfère la LISTE
// multi-références (my_refs/refs, posée par la refonte de saisie A) ; à défaut
// retombe sur la paire mono-valuée SIG/SIG_INFO (QSO anciens).
function _refsPourExport(q, cleListe, cleSig, cleInfo){
  const liste = q[cleListe];
  if(Array.isArray(liste) && liste.length){
    return liste.filter(r=>r).map(r=>[String(r.program||'').toUpperCase().trim(), String(r.ref||'').trim()]);
  }
  const prog = String(q[cleSig]||'').toUpperCase().trim();
  return prog ? [[prog, String(q[cleInfo]||'').trim()]] : [];
}

function buildAdifText(qsos){
  let adif = 'LogX AI — Export ADIF\n';
  // ADIF_VER : 3.1.7, version stable actuellement publiée sur adif.org
  // (« Released ADIF Version 3.1.7 », 2026-03-22) — jumeau de la même
  // correction côté serveur (logx_export.build_adif), même table ADIF_BAND
  // ci-dessus déjà alignée sur cette version.
  adif += adifField('ADIF_VER', '3.1.7') + adifField('PROGRAMID', 'LogX AI') + '\n<EOH>\n\n';
  qsos.forEach(q=>{
    const date = String(q.date || '').replace(/-/g, '').slice(0, 8);
    const time = String(q.time || '').replace(/:/g, '').slice(0, 4).padEnd(4, '0');
    adif += adifField('CALL', String(q.call).toUpperCase());
    adif += adifField('QSO_DATE', date);
    adif += adifField('TIME_ON', time);
    adif += adifField('BAND', adifBandLabel(q.band));
    // FREQ : seulement si elle a réellement été relevée (CAT/saisie) — c'est
    // aussi le seul moyen, pour un importateur, de retrouver la bande d'un
    // QSO dont le libellé serait intraduisible.
    adif += adifField('FREQ', q.freq);
    // FT2 = sous-mode EXPÉRIMENTAL de MFSK : WSJT-X ne liste pas FT2, on exporte
    // MODE=MFSK + SUBMODE=FT2 — JAMAIS MODE=FT2 (sinon ADIF invalide / illisible
    // par un logiciel tiers). Terrain FT2 Phase 1 (F4GLD).
    if(String(q.mode || '').toUpperCase() === 'FT2'){
      adif += adifField('MODE', 'MFSK') + adifField('SUBMODE', 'FT2');
    } else {
      adif += adifField('MODE', q.mode);
    }
    adif += adifField('RST_SENT', q.rst_sent);
    adif += adifField('RST_RCVD', q.rst_rcvd);
    adif += adifField('STX_STRING', q.num_sent);
    adif += adifField('SRX_STRING', q.num_rcvd);
    adif += adifField('GRIDSQUARE', q.locator);
    adif += adifField('MY_GRIDSQUARE', q.my_locator || myLocator);
    // Multi-op : sans STATION_CALLSIGN/OPERATOR le log n'est attribuable ni à
    // la station ni à l'opérateur qui a fait le QSO.
    adif += adifField('STATION_CALLSIGN', String(q.my_call || myCall || '').toUpperCase());
    adif += adifField('OPERATOR', _resolveOperatorCallsign(q.operator));
    adif += adifField('CONTEST_ID', q.contest);
    // Sous-chantier B (lot 1) : tags que le serveur (build_adif) émet et que
    // l'export CLIENT omettait -> perte de données à l'export déclenché côté
    // client. Mêmes champs, même ordre que logx_export.build_adif (jumeaux).
    adif += adifField('NAME', q.name);
    adif += adifField('QTH', q.qth);
    adif += adifField('STATE', q.state);
    adif += adifField('COMMENT', q.comment);
    adif += adifField('DISTANCE', q.dist);
    adif += adifField('PROP_MODE', q.prop_mode);
    adif += adifField('SAT_NAME', q.sat_name);
    adif += adifField('MY_SIG', q.my_sig);
    adif += adifField('MY_SIG_INFO', q.my_sig_info);
    adif += adifField('SIG', q.sig);
    adif += adifField('SIG_INFO', q.sig_info);
    // Sous-chantier B (lot 2) : clés posées par la refonte de saisie (A) —
    // mêmes tags que logx_export.build_adif. operating_location -> APP_LOGX_OPERATING.
    adif += adifField('TX_PWR', q.tx_pwr);
    adif += adifField('FREQ_RX', q.freq_rx);
    adif += adifField('CQZ', q.cqz);
    adif += adifField('ITUZ', q.ituz);
    adif += adifField('CNTY', q.cnty);
    adif += adifField('EMAIL', q.email);
    adif += adifField('QSL_VIA', q.qsl_via);
    adif += adifField('ANT_AZ', q.ant_az);
    adif += adifField('TIME_OFF', q.time_off);
    adif += adifField('QSL_SENT', q.qsl_sent);
    adif += adifField('LOTW_QSL_SENT', q.lotw_qsl_sent);
    adif += adifField('EQSL_QSL_SENT', q.eqsl_qsl_sent);
    adif += adifField('APP_LOGX_OPERATING', q.operating_location);
    // Lot 3 : tags ADIF dédiés par programme, émis depuis la liste multi-
    // références pour ne pas perdre le 2e programme d'un two-fer SOTA+POTA.
    _refsPourExport(q, 'my_refs', 'my_sig', 'my_sig_info').forEach(([prog, ref]) => {
      const tag = REF_ADIF_TAGS[prog]; if(tag && ref) adif += adifField('MY_' + tag, ref);
    });
    _refsPourExport(q, 'refs', 'sig', 'sig_info').forEach(([prog, ref]) => {
      const tag = REF_ADIF_TAGS[prog]; if(tag && ref) adif += adifField(tag, ref);
    });
    // Champs ADIF personnalisés (voir editQSO/extra_fields) — ADIF_STD_TAGS
    // évite qu'un nom entré par erreur (ex. "CALL") ne duplique/contredise un
    // tag déjà émis ci-dessus.
    if(q.extra_fields){
      Object.entries(q.extra_fields).forEach(([name, value]) => {
        if(!ADIF_STD_TAGS.has(name)) adif += adifField(name, value);
      });
    }
    adif += '<EOR>\n';
  });
  return adif;
}

function downloadAdifBlob(adif, suffix){
  const blob = new Blob([adif],{type:'text/plain'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${myCall.replace('/','_')}_${suffix}.adif`;
  a.click();
}

async function exportADIF(){
  const act = _activeActivity();
  const scope = act ? await _demanderPerimetre(act) : null;
  const base = scope ? qsoLog.filter(scope.match) : qsoLog;
  const validQSOs = base.filter(isValidQSO);
  const skipped = base.length - validQSOs.length;
  if(skipped && !(await _confirmDupBanner(trF('⚠️ {n} QSO incomplet(s) seront ignorés dans l\'export ADIF.\n\nContinuer ?', {n: skipped}), 'Continuer', 'Annuler'))) return;
  downloadAdifBlob(buildAdifText(validQSOs), scope ? ('log_' + _safeSuffixe(scope.suffixe)) : 'log');
}

// Échappement CSV (RFC 4180) : un champ contenant une virgule, un guillemet ou
// un retour-ligne est entouré de guillemets (guillemets internes doublés) ;
// undefined/null -> '' (jamais le texte « undefined »). Sans ça, une virgule
// dans un champ (échange, locator, opérateur) décalait toutes les colonnes.
function _csvField(v){
  const s = (v === undefined || v === null) ? '' : String(v);
  return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

const _CSV_HEADER = 'N°,Date,Heure,Indicatif,Bande,Mode,RST_env,N°_env,RST_recu,N°_recu,Locator,Distance_km,Points,Operateur';

function _csvBaseRow(q, i){
  return [i + 1, q.date, q.time, q.call, q.band, q.mode, q.rst_sent, q.num_sent,
          q.rst_rcvd, q.num_rcvd, q.locator, (q.dist || 0), (q.points || 0),
          _resolveOperatorCallsign(q.operator)];
}

function _downloadCsv(csv, suffixe){
  // BOM UTF-8 (﻿) : sans lui, Excel lit le CSV en ANSI et corrompt les
  // accents (N°, Scoré, Échange reçu…). charset=utf-8 par cohérence.
  const blob = new Blob(['﻿' + csv], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${myCall.replace('/','_')}_${suffixe}.csv`;
  a.click();
}

// ─── Filtre d'export par ACTIVITÉ (concours actif ou activation POTA/SOTA) ───
// Chaque QSO est déjà tagué à la source (submitQSO : q.contest, q.my_sig/
// q.my_sig_info). On étend ici la logique scopée de Cabrillo/EDI/POTA à TOUS les
// exports : si une activité est en cours, on propose « tout le carnet » OU
// « l'activité en cours ». Renvoie {label, suffixe, match} ou null (pas d'activité).
//
// _CONTEST_DEFAUT : valeur de REPLI de currentContest quand aucun concours n'est
// configuré (logx_logbook.js : `window._initContest || 'REF_RPH'`). Ce n'est PAS
// une activité délibérément choisie — on la traite comme « aucune activité » pour
// ne PAS imposer un dialogue de périmètre à chaque export du quotidien.
const _CONTEST_DEFAUT = 'REF_RPH';

function _activeActivity(){
  if(typeof activationProgram !== 'undefined' && activationProgram
     && typeof myActivationRef !== 'undefined' && myActivationRef){
    const prog = String(activationProgram).toUpperCase(), ref = String(myActivationRef);
    return { label: prog + ' ' + ref, suffixe: prog + '_' + ref,
             match: q => String(q.my_sig || '').toUpperCase() === prog
                         && String(q.my_sig_info || '') === ref };
  }
  if(typeof currentContest !== 'undefined' && currentContest && currentContest !== _CONTEST_DEFAUT){
    const c = String(currentContest);
    return { label: c, suffixe: c, match: q => String(q.contest || '') === c };
  }
  return null;
}

function _safeSuffixe(s){ return String(s || '').replace(/[^A-Za-z0-9_-]+/g, '_'); }

// Demande le périmètre à l'opérateur pour une activité DÉJÀ détectée (act non
// null) : renvoie l'activité (avec .match) pour « activité seule », ou null pour
// « tout le carnet ». Appelée UNIQUEMENT si _activeActivity() a renvoyé non-null,
// pour qu'un export sans activité reste 100 % synchrone (aucun await atteint).
async function _demanderPerimetre(act){
  const seule = await _confirmDupBanner(
    trF('Une activité est en cours : « {a} ».\n\nQue veux-tu exporter ?\n\n'
        + 'OK = uniquement « {a} »   ·   Annuler = tout le carnet.', {a: act.label}),
    trT('Activité en cours'), trT('Tout le carnet'));
  return seule ? act : null;
}

// Builders CSV SYNCHRONES (testables) — la sélection du périmètre (dialogue) est
// gérée par les fonctions export* async ci-dessous.
function _csvComplet(src){
  let csv = _CSV_HEADER + ',Complet,Scoré,Concours,Echange_reçu_brut\n';
  src.forEach((q,i)=>{
    const row = _csvBaseRow(q, i).concat([
      isValidQSO(q) ? 'oui' : 'non',
      ((q.points || 0) > 0) ? 'oui' : 'non',
      q.contest, q.num_rcvd]);
    csv += row.map(_csvField).join(',') + '\n';
  });
  return csv;
}

function _csvValide(src){
  let csv = _CSV_HEADER + '\n';
  src.filter(isValidQSO).forEach((q,i)=>{
    csv += _csvBaseRow(q, i).map(_csvField).join(',') + '\n';
  });
  return csv;
}

// CSV COMPLET (diagnostic / récupération) : TOUS les QSO, même incomplets ou
// invalides, + 4 champs diagnostic DÉRIVÉS (décision F4GLD 23/08). raw_exchange
// = échange reçu brut ; parsed_exchange et le statut de validation détaillé
// restent à ajouter quand le parseur d'échange par profil sera en place.
async function exportCSV(){
  const act = _activeActivity();
  const scope = act ? await _demanderPerimetre(act) : null;
  const src = scope ? qsoLog.filter(scope.match) : qsoLog;
  _downloadCsv(_csvComplet(src), scope ? ('log_' + _safeSuffixe(scope.suffixe)) : 'log');
}

// CSV VALIDE (soumission / partage) : uniquement les QSO complets et validés
// (même filtre isValidQSO que l'export ADIF), colonnes propres (sans les champs
// de diagnostic du CSV complet). Distinct du CSV complet, comme ADIF/Cabrillo.
async function exportCSVValide(){
  const act = _activeActivity();
  const scope = act ? await _demanderPerimetre(act) : null;
  const src = scope ? qsoLog.filter(scope.match) : qsoLog;
  _downloadCsv(_csvValide(src), scope ? ('log_valide_' + _safeSuffixe(scope.suffixe)) : 'log_valide');
}
