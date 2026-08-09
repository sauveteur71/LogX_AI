// ─── SCAN QSL PAPIER (EV-7 phase 2, docs/LogX_AI_PRD.md) ─────────────────────
// PREMIER PILOTE du bus d'événements EV-7 — différent des 9 incréments
// précédents (copié-collé strict d'un bloc autonome, appelé UNIQUEMENT par un
// onclick HTML ou par une chaîne de menu). Ici, le point d'entrée
// (editQSO(), fonction du cœur — ouvrir la modale d'édition d'un QSO — voir
// logx_logbook.js) avait besoin d'appeler CE module directement pour afficher
// le scan déjà attaché. Plutôt que de laisser cet appel dur (dépendance
// cœur→optionnel, l'erreur déjà trouvée et corrigée au 2e incrément avec le
// moteur de filtre), editQSO() se contente maintenant d'émettre l'événement
// DOM `logx:qso-editing-opened` (detail: {qso}) ; ce module s'y abonne pour
// peupler sa propre UI. Le cœur ne sait plus que ce module existe.
//
// Sens du flux : UNIQUEMENT du cœur vers ce module (editQSO() → événement →
// ce module). saveEdit() (cœur, sauvegarde du QSO édité) ne lit JAMAIS
// qsl_scan en retour — c'est uploadQslScan() qui persiste directement au
// serveur (POST /qsl_scan/upload) et met à jour qsoLog localement, sans
// passer par le flux d'enregistrement du formulaire d'édition. C'est cette
// absence de dépendance retour qui rend ce bloc éligible à un premier pilote
// SANS avoir à inventer un mécanisme d'échange bidirectionnel — voir le
// commentaire dans logx_logbook.js au point d'écoute pour le cas contraire
// (CHAMPS ADIF PERSONNALISÉS, resté dans le cœur pour cette raison précise).
//
// Dépend de globals restés dans logx_logbook.js : notify(), renderLog(),
// qsoLog.
document.addEventListener('logx:qso-editing-opened', e => {
  _renderEditQslScan(e.detail.qso.qsl_scan);
});

function _renderEditQslScan(path){
  const empty = document.getElementById('editQslScanEmpty');
  const link = document.getElementById('editQslScanLink');
  const thumb = document.getElementById('editQslScanThumb');
  if(!empty || !link || !thumb) return;
  if(path){
    const url = '/' + path;
    const isImg = /\.(jpe?g|png|gif|webp)$/i.test(path);
    link.href = url;
    thumb.src = isImg ? url : '/logx_icon.svg';   // repli : pas d'aperçu pour un PDF
    thumb.title = isImg ? 'Voir le scan en grand' : 'Ouvrir le PDF';
    thumb.alt = 'Scan de la carte QSL attachée';
    link.style.display = 'inline-block';
    empty.style.display = 'none';
  } else {
    link.style.display = 'none';
    empty.style.display = 'inline';
  }
}

async function uploadQslScan(){
  const id = parseInt(document.getElementById('editId').value, 10);
  const input = document.getElementById('editQslScanFile');
  const status = document.getElementById('editQslScanStatus');
  const file = input && input.files && input.files[0];
  if(!file || !id) return;
  if(status){ status.textContent = '⏳ envoi…'; status.style.color = 'var(--muted)'; }
  try{
    const fd = new FormData();
    fd.append('qso_id', String(id));
    fd.append('file', file);
    // Pas de Content-Type manuel : le navigateur pose la frontière multipart lui-même.
    const r = await fetch('/qsl_scan/upload', {method:'POST', body: fd});
    const d = await r.json();
    if(d.ok){
      const q = qsoLog.find(x => x.id === id);
      if(q) q.qsl_scan = d.qsl_scan;
      _renderEditQslScan(d.qsl_scan);
      if(status){ status.textContent = '✅ scan attaché'; status.style.color = 'var(--green)'; }
      notify('✅ Scan QSL attaché');
      renderLog();
    } else {
      if(status){ status.textContent = '❌ ' + (d.error || 'échec'); status.style.color = 'var(--red)'; }
    }
  }catch(e){
    if(status){ status.textContent = '❌ serveur injoignable'; status.style.color = 'var(--red)'; }
  }
  input.value = '';
}
