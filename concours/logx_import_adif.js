// ─── IMPORT ADIF + EXPORT ON4KST (EV-7, docs/LogX_AI_PRD.md) ────────────────
// 7e incrément du refactor EV-7 : extrait tel quel de logx_logbook.js (aucune
// restructuration nécessaire). Import d'un fichier ADIF (aperçu serveur puis
// confirmation) et copie du message d'annonce ON4KST dans le presse-papier.
//
// Dépend de globals restés dans logx_logbook.js (portée globale partagée via
// <script> classique, voir logx_logbook.html) : escHtml(), notify(), trF(),
// trT(), fetchLog(), myCall, myLocator, currentBand, currentMode, BAND_FREQ.
//
// Aucune fonction de ce fichier n'est appelée depuis le cœur (renderLog(),
// la sauvegarde d'un QSO, l'init de page, les dispatchers auto-appelés) :
// triggerImport()/exportON4KST() ne sont déclenchés que par un clic (menu ou
// onclick HTML), confirmImportAdif()/closeImportOverlay() que par les
// boutons de la modale d'import elle-même. Le handler clavier global
// (RACCOURCIS CLAVIER, resté dans logx_logbook.js) fermait auparavant la
// modale d'import via un appel direct à closeImportOverlay() sur Échap —
// seul cas parmi les modales voisines (editOverlay, shortcutsOverlay,
// validateOverlay, awardsOverlay) à appeler une fonction plutôt que de
// retirer la classe .show inline. Remplacé par l'équivalent inline
// (`impOverlay.classList.remove('show')`, même geste que ses voisines) au
// moment de cette extraction : la seule différence de comportement est que
// _pendingImportText n'est plus remis à vide par Échap (sans conséquence —
// il est de toute façon réécrit à chaque nouvel aperçu, et le bouton
// CONFIRMER L'IMPORT, seul point d'entrée de confirmImportAdif(), n'est
// plus atteignable une fois la modale fermée).
// ─── IMPORT ADIF ──────────────────────────────────────────────────────────────
// Passe par le SERVEUR (/log/import_adif/preview puis /commit) — une version
// antérieure poussait les QSO importés directement dans la variable JS locale
// qsoLog, qui est ÉCRASÉE par le polling fetchLog() toutes les 5 s : les QSO
// importés disparaissaient silencieusement en quelques secondes, jamais
// persistés dans shared_log. Le dédoublonnage (par indicatif+bande+mode+
// date+heure exacts) se fait aussi côté serveur, contre le VRAI log partagé
// entre tous les postes, pas seulement le qsoLog de ce navigateur.
let _pendingImportText = '';
// Activité à affecter au lot importé (F4GLD 23/08) : un log externe d'événement
// spécial (TM6KJS…) arrive souvent sans CONTEST_ID -> non tagué. Saisi ici, il
// tague les QSO neufs sans concours propre (voir logx_import.commit_import).
let _importActivite = '';

function triggerImport(){
  const inp = document.createElement('input');
  inp.type = 'file'; inp.accept = '.adi,.adif,.ADI,.ADIF';
  inp.onchange = e => {
    const f = e.target.files[0]; if(!f) return;
    const reader = new FileReader();
    reader.onload = ev => previewImportAdif(ev.target.result);
    reader.readAsText(f, 'UTF-8');
  };
  inp.click();
}

async function previewImportAdif(text){
  const overlay = document.getElementById('importOverlay');
  const inner = document.getElementById('importInner');
  overlay.classList.add('show');
  inner.innerHTML = '<div class="shortcuts-row"><span>⏳ Analyse du fichier…</span></div>';
  document.getElementById('importConfirmBtn').disabled = true;
  try{
    const res = await fetch('/log/import_adif/preview', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({adif: text, activite: _importActivite}),
    });
    const p = await res.json();
    if(!p.ok){
      inner.innerHTML = `<div class="shortcuts-row"><span>❌ ${escHtml(p.error || 'Fichier illisible')}</span></div>`;
      return;
    }
    _pendingImportText = text;
    const rows = [];
    rows.push(`<div class="shortcuts-row"><span>📄 QSO valides dans le fichier</span><span>${p.total_in_file}</span></div>`);
    rows.push(`<div class="shortcuts-row"><span>✅ Nouveaux à importer</span><span style="color:var(--green)">${p.new}</span></div>`);
    rows.push(`<div class="shortcuts-row"><span>⏩ Déjà dans le log (doublons exacts)</span><span style="color:var(--muted)">${p.duplicates}</span></div>`);
    // Champ « affecter à une activité » : tague les QSO neufs sans concours
    // propre. onchange -> re-preview pour rafraîchir le compteur `to_tag`.
    rows.push('<div class="shortcuts-row" style="margin-top:10px;flex-direction:column;align-items:stretch;gap:4px">'
      + '<label for="importActivite" style="color:var(--muted)">🏷️ Affecter cet import à une activité '
      + '(concours ou indicatif spécial, ex. TM6KJS) — optionnel :</label>'
      + `<input id="importActivite" type="text" value="${escHtml(_importActivite)}" placeholder="ex. TM6KJS" `
      + 'style="padding:6px 8px;background:var(--bg2);color:inherit;border:1px solid var(--border);border-radius:6px;font-family:inherit" '
      + 'oninput="_importActivite=this.value.toUpperCase();this.value=_importActivite" '
      + 'onchange="previewImportAdif(_pendingImportText)"></div>');
    if(_importActivite && typeof p.to_tag === 'number'){
      rows.push(`<div class="shortcuts-row"><span>↳ QSO qui recevront le tag « ${escHtml(_importActivite)} »</span><span style="color:var(--accent)">${p.to_tag}</span></div>`);
    }
    if(p.errors && p.errors.length){
      rows.push(`<div class="shortcuts-row"><span>⚠️ Records ignorés</span><span style="color:var(--yellow)">${p.errors.length}</span></div>`);
    }
    if(p.mode_warnings && p.mode_warnings.length){
      // Informatif seulement : ces QSO SONT importés (déjà comptés dans
      // "Nouveaux à importer"), juste signalés pour vérification.
      p.mode_warnings.forEach(w => {
        rows.push(`<div class="shortcuts-row"><span style="color:var(--muted)">ℹ️ ${escHtml(w)}</span></div>`);
      });
    }
    if(p.sample && p.sample.length){
      rows.push('<div class="shortcuts-row" style="margin-top:8px"><span style="color:var(--muted)">Aperçu (5 premiers nouveaux QSO) :</span></div>');
      p.sample.forEach(q => {
        rows.push(`<div class="shortcuts-row"><span>${escHtml(q.call)} · ${escHtml(q.band)} MHz · ${escHtml(q.mode)}</span><span style="color:var(--muted)">${escHtml(q.date)} ${escHtml(q.time)}</span></div>`);
      });
    }
    inner.innerHTML = rows.join('');
    document.getElementById('importConfirmBtn').disabled = (p.new === 0);
  }catch(e){
    inner.innerHTML = `<div class="shortcuts-row"><span>❌ Serveur injoignable : ${e.message}</span></div>`;
  }
}

async function confirmImportAdif(){
  if(!_pendingImportText) return;
  const btn = document.getElementById('importConfirmBtn');
  btn.disabled = true; btn.textContent = '⏳ Import en cours…';
  try{
    const res = await fetch('/log/import_adif/commit', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({adif: _pendingImportText, activite: _importActivite}),
    });
    const r = await res.json();
    closeImportOverlay();
    if(r.ok){
      await fetchLog();   // rafraîchit immédiatement (sinon jusqu'à 5 s d'attente)
      const errPart = (r.errors && r.errors.length) ? trF('\n⚠️ {n} records ignorés', {n: r.errors.length}) : '';
      notify(trF('Import ADIF terminé :\n✅ {n} QSO importés{errPart}', {n: r.imported, errPart}));
    } else {
      notify(trF('❌ Import échoué : {err}', {err: r.error || trT('erreur inconnue')}));
    }
  }catch(e){
    notify(trF('❌ Import échoué : {err}', {err: e.message}));
  }finally{
    btn.textContent = "✅ CONFIRMER L'IMPORT";
  }
}

function closeImportOverlay(){
  document.getElementById('importOverlay').classList.remove('show');
  _pendingImportText = '';
  _importActivite = '';
}

// ─── EXPORT ON4KST ────────────────────────────────────────────────────────────
function exportON4KST(){
  const entered = (document.getElementById('inputFreq')?.value || '').trim();
  const freq = entered || BAND_FREQ[currentBand] || (currentBand+' MHz');
  const msg = `${myCall} ${myLocator} ${freq} ${currentMode||'SSB'} CQ RPH`;
  navigator.clipboard.writeText(msg).then(()=>{
    const btn = document.querySelector('[onclick="exportON4KST()"]');
    if(btn){ const orig=btn.textContent; btn.textContent='✅ Copié !'; setTimeout(()=>btn.textContent=orig,2000); }
  }).catch(()=>{ prompt(trT('Copier ce message ON4KST :'), msg); });
}
