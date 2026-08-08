// EV-7 phase 2, 10e incrément (docs/LogX_AI_PRD.md) -- bloc SÉLECTEUR CONCOURS
// (UI de la modale de démarrage) extrait tel quel de logx_logbook.js
// (extraction MÉCANIQUE, pas le motif bus d'événements du pilote SCAN QSL
// PAPIER -- voir logx_scan_qsl.js). Analyse préalable (Workflow, cartographie
// + évaluation de 64 blocs) : ces 5 fonctions + le listener de fermeture
// n'ont qu'UN SEUL point d'entrée externe (csSetValue(), appelée par
// prefillSetupFromConfig() dans logx_logbook.js) et 2 attributs HTML
// (onclick="csToggle()", oninput="csFilter(this.value)" sur logx_logbook.html)
// -- exactement le même motif que les incréments 1-9 et RADIO CAT/AMPLI/
// ROTOR/WSJT-X.
//
// Dépendances LUES (jamais écrites par ce bloc) restant volontairement dans
// logx_logbook.js, portée globale partagée (même <script> classique) :
//   - CS_DATA (liste groupée des concours, section dédiée du fichier
//     principal) -- utilisée uniquement ici, mais classée comme DONNÉE et
//     non comme comportement, cohérent avec les extractions précédentes qui
//     laissent les tables de données au cœur.
//   - CONTEST_SCHEDULE -- PARTAGÉE avec d'autres parties de logx_logbook.js
//     (dates par défaut au chargement, nom du concours affiché en score) :
//     ne PAS la déplacer ici sous peine de casser ces autres usages.
//   - #setupContest, #setupCallsign... (éléments DOM du formulaire de
//     démarrage) : lus/écrits via getElementById, découplage déjà en place.
function csToggle(){
  const panel = document.getElementById('csPanel');
  const btn   = document.getElementById('csTrigger');
  const open  = panel.classList.toggle('open');
  btn.classList.toggle('open', open);
  if(open) { document.getElementById('csSearch').value=''; csFilter(''); document.getElementById('csSearch').focus(); }
}

function csFilter(q){
  const list = document.getElementById('csList');
  q = q.toLowerCase();
  list.innerHTML = CS_DATA.map(grp=>{
    const items = grp.items.filter(it=> !q || it.l.toLowerCase().includes(q) || it.v.toLowerCase().includes(q));
    if(!items.length) return '';
    return `<div class="cs-group">${grp.g}</div>`
      + items.map(it=>`<div class="cs-option${it.v===document.getElementById('setupContest').value?' cs-selected':''}" data-val="${it.v}" onclick="csSelect('${it.v}','${it.l.replace(/'/g,'&#39;')}')">${it.l}</div>`).join('');
  }).join('') || `<div class="cs-empty">Aucun concours trouvé</div>`;
}

function csSelect(val, lbl){
  document.getElementById('setupContest').value = val;
  const trigLbl = document.getElementById('csTriggerLabel');
  trigLbl.textContent = lbl;
  trigLbl.style.color = 'var(--accent2)';
  // Fermer le panneau
  const panel = document.getElementById('csPanel');
  const btn   = document.getElementById('csTrigger');
  panel.classList.remove('open');
  btn.classList.remove('open');
  // Mettre à jour les horaires du concours
  updateContestTiming(val);
}

function csSetValue(val){
  const flat = [];
  CS_DATA.forEach(grp => grp.items.forEach(it => flat.push(it)));
  const item = flat.find(it => it.v === val);
  if(item) csSelect(val, item.l);
}

function updateContestTiming(contestId){
  const box = document.getElementById('contestTimingBox');
  if(!box) return;
  const sched = CONTEST_SCHEDULE[contestId];
  if(!sched || !sched.start){
    box.style.display = 'none';
    return;
  }
  const fmtUTC = iso => {
    const d = new Date(iso);
    const j = d.toLocaleDateString('fr-FR',{weekday:'short',day:'2-digit',month:'2-digit',year:'numeric',timeZone:'UTC'});
    const h = d.toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit',timeZone:'UTC'});
    return `${j} ${h} UTC`;
  };
  const fmtLocal = iso => {
    const d = new Date(iso);
    const j = d.toLocaleDateString('fr-FR',{weekday:'short',day:'2-digit',month:'2-digit',year:'numeric',timeZone:'Europe/Paris'});
    const h = d.toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Paris'});
    const tz = new Intl.DateTimeFormat('fr-FR',{timeZone:'Europe/Paris',timeZoneName:'short'}).formatToParts(new Date(iso)).find(p=>p.type==='timeZoneName').value;
    return `${j} ${h} (${tz})`;
  };
  const startEl = document.getElementById('ctStartUTC');
  const startLocEl = document.getElementById('ctStartLocal');
  const endEl = document.getElementById('ctEndUTC');
  const endLocEl = document.getElementById('ctEndLocal');
  const durEl = document.getElementById('ctDuration');
  if(startEl) startEl.textContent = fmtUTC(sched.start);
  if(startLocEl) startLocEl.textContent = fmtLocal(sched.start);
  if(endEl) endEl.textContent = fmtUTC(sched.end);
  if(endLocEl) endLocEl.textContent = fmtLocal(sched.end);
  if(durEl) durEl.textContent = sched.dur;
  const emailRow = document.getElementById('ctEmailRow');
  const emailEl  = document.getElementById('ctEmail');
  if(emailRow && emailEl){
    if(sched.email){ emailEl.textContent = sched.email; emailEl.href = `mailto:${sched.email}`; emailRow.style.display = 'block'; }
    else emailRow.style.display = 'none';
  }
  box.style.display = 'block';
}

// Fermer le sélecteur concours si clic en dehors
document.addEventListener('click', e => {
  const panel = document.getElementById('csPanel');
  const trigger = document.getElementById('csTrigger');
  if(panel && trigger && !panel.contains(e.target) && !trigger.contains(e.target)){
    panel.classList.remove('open');
    trigger.classList.remove('open');
  }
});
