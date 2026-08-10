// ─── RE-RÉSOLUTION EN MASSE (EV-7, docs/LogX_AI_PRD.md) ─────────────────────
// Extrait hors du monolithe logx_logbook.js (chantier EV-7, même logique que
// logx_filter_builder.js/logx_dup_finder.js à côté). Lance/suit le job de
// fond côté serveur (logx_callbook.bulk_resolve_start) : une seule requête
// réseau par indicatif DISTINCT, jamais une par QSO — voir le module serveur
// pour le détail. Le job continue même si cette popup est fermée
// (bulkResolveRunning/_bulkResolvePoll ne sont que le reflet local de l'état
// serveur, pas la source de vérité) — la rouvrir le retrouve. Dépend de
// matchesAdvancedFilter()/advancedFilter (logx_logbook.js, moteur du filtre
// avancé — voir logx_filter_builder.js pour l'UI du popup qui le compose)
// pour le mode "restreindre au filtre actif" — accès en portée globale,
// comme tout le JS classique de ce projet (pas de module ES).
let bulkResolveRunning = false;
let _bulkResolvePoll = null;

async function openBulkResolve(){
  const filteredCount = advancedFilter ? qsoLog.filter(q => matchesAdvancedFilter(q, advancedFilter)).length : 0;
  document.getElementById('brsFilteredCount').textContent = filteredCount;
  document.getElementById('brsScopeFiltered').disabled = !advancedFilter;
  if(!advancedFilter) document.getElementById('brsScopeAll').checked = true;
  // État par défaut "au repos" posé AVANT le fetch de statut, pas seulement
  // dans sa branche de succès : sans ça, un fetch en échec (réseau, serveur
  // pas encore redémarré après un déploiement) laissait la popup afficher un
  // reliquat d'un run précédent au lieu de repartir propre — trouvé en
  // vérification navigateur, pas en écrivant le code.
  bulkResolveRunning = false;
  document.getElementById('brsStartBtn').disabled = false;
  document.getElementById('brsBarWrap').classList.remove('show');
  document.getElementById('brsStatus').textContent = '';
  document.getElementById('bulkResolveOverlay').classList.add('show');
  try{
    const st = await fetch('/log/bulk_resolve/status').then(r=>r.json());
    if(st.running){
      bulkResolveRunning = true;
      document.getElementById('brsStartBtn').disabled = true;
      document.getElementById('brsBarWrap').classList.add('show');
      if(!_bulkResolvePoll) _bulkResolvePoll = setInterval(pollBulkResolve, 1000);
      pollBulkResolve();
    }
  }catch(e){}
}

function closeBulkResolve(){
  document.getElementById('bulkResolveOverlay').classList.remove('show');
}

async function startBulkResolve(){
  const useFiltered = document.getElementById('brsScopeFiltered').checked && advancedFilter;
  const overwrite = document.getElementById('brsOverwrite').checked;
  const ids = useFiltered ? qsoLog.filter(q => matchesAdvancedFilter(q, advancedFilter)).map(q=>q.id) : null;
  if(useFiltered && !ids.length){ notify('Aucun QSO dans le filtre actif.'); return; }
  if(!(await _confirmDupBanner(trF('Lancer la re-résolution sur {n} ? Une requête réseau par indicatif distinct.',
              {n: ids ? ids.length + ' QSO' : 'tout le log'}), 'Lancer', 'Annuler'))) return;

  document.getElementById('brsStartBtn').disabled = true;
  bulkResolveRunning = true;
  document.getElementById('brsBarWrap').classList.add('show');
  document.getElementById('brsBar').style.width = '0%';
  document.getElementById('brsStatus').textContent = 'Démarrage…';

  let started;
  try{
    started = await fetch('/log/bulk_resolve/start', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ids, overwrite})}).then(r=>r.json());
  }catch(e){
    document.getElementById('brsStatus').textContent = 'Serveur injoignable.';
    bulkResolveRunning = false;
    document.getElementById('brsStartBtn').disabled = false;
    return;
  }
  if(!started.ok){
    document.getElementById('brsStatus').textContent = started.error || 'Échec du démarrage.';
    bulkResolveRunning = false;
    document.getElementById('brsStartBtn').disabled = false;
    return;
  }

  if(!_bulkResolvePoll) _bulkResolvePoll = setInterval(pollBulkResolve, 1000);
  pollBulkResolve();
}

async function pollBulkResolve(){
  let st;
  try{
    st = await fetch('/log/bulk_resolve/status').then(r=>r.json());
  }catch(e){ return; }
  const pct = st.total ? Math.round(100 * st.done / st.total) : 0;
  const bar = document.getElementById('brsBar');
  if(bar) bar.style.width = pct + '%';
  const statusEl = document.getElementById('brsStatus');
  if(st.running){
    if(statusEl) statusEl.textContent = trF('{d} / {t} indicatifs interrogés…', {d: st.done, t: st.total});
  } else {
    if(_bulkResolvePoll){ clearInterval(_bulkResolvePoll); _bulkResolvePoll = null; }
    bulkResolveRunning = false;
    const btn = document.getElementById('brsStartBtn');
    if(btn) btn.disabled = false;
    if(statusEl) statusEl.textContent = trF('Terminé — {u} QSO mis à jour, {e} indicatif(s) introuvable(s).',
      {u: st.updated, e: st.errors});
    fetchLog();   // recharge le log réel : locator/état mis à jour côté serveur
  }
}
