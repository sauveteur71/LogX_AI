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
// qsoLog, isValidQSO, myCall, myLocator, _resolveOperatorCallsign, confirm,
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
  'OPERATOR','CONTEST_ID','ADIF_VER','PROGRAMID']);

function buildAdifText(qsos){
  let adif = 'LogX AI — Export ADIF\n';
  adif += adifField('ADIF_VER', '3.1.4') + adifField('PROGRAMID', 'LogX AI') + '\n<EOH>\n\n';
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
    adif += adifField('MODE', q.mode);
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

function exportADIF(){
  const validQSOs = qsoLog.filter(isValidQSO);
  const skipped = qsoLog.length - validQSOs.length;
  if(skipped && !confirm(trF('⚠️ {n} QSO incomplet(s) seront ignorés dans l\'export ADIF.\n\nContinuer ?', {n: skipped}))) return;
  downloadAdifBlob(buildAdifText(validQSOs), 'log');
}

function exportCSV(){
  let csv = 'N°,Date,Heure,Indicatif,Bande,Mode,RST_env,N°_env,RST_recu,N°_recu,Locator,Distance_km,Points,Operateur\n';
  qsoLog.forEach((q,i)=>{
    csv += `${i+1},${q.date},${q.time},${q.call},${q.band},${q.mode},${q.rst_sent},${q.num_sent},${q.rst_rcvd},${q.num_rcvd||''},${q.locator||''},${q.dist||0},${q.points||0},${_resolveOperatorCallsign(q.operator)}\n`;
  });
  const blob = new Blob([csv],{type:'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${myCall.replace('/','_')}_log.csv`;
  a.click();
}
