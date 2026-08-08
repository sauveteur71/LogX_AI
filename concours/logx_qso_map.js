// EV-7 phase 2, 12e increment (docs/LogX_AI_PRD.md) -- carte QSO (Leaflet)
// extraite telle quelle de logx_logbook.js (extraction MECANIQUE, pas le
// motif bus d'evenements du pilote SCAN QSL PAPIER -- voir logx_scan_qsl.js).
// Analyse prealable (Workflow, cartographie + evaluation de 64 blocs) : bloc
// NET et COMPLET -- etat interne (qsoMap/homeMarker/mapLayers) jamais lu
// ailleurs dans logx_logbook.js, un seul point d'entree externe
// (refreshMapLayers(), appele depuis renderLog() quand la carte est visible ;
// toggleMapView() via onclick="toggleMapView()" dans logx_logbook.html, seul
// site HTML -- non touche par cette extraction). Depend de la bibliotheque
// Leaflet globale (L, chargee via CDN dans le <head> de logx_logbook.html,
// AVANT tous les <script> locaux) et de locLL()/escHtml()/BAND_LABELS/
// qsoLog/myLocator/myCall, tous definis plus haut dans logx_logbook.js mais
// lus uniquement a l'interieur du corps des fonctions -- jamais au
// chargement du script -- donc aucun souci d'ordre malgre ce fichier charge
// AVANT logx_logbook.js.

// ─── CARTE QSO (Leaflet) ──────────────────────────────────────────────────────
let qsoMap = null;
let homeMarker = null;
let mapLayers = [];   // markers + polylines dynamiques

const BAND_COLORS = {
  '1.8':   '#FF2D55',  // 160m rouge
  '3.5':   '#FF6B35',  // 80m  orange-rouge
  '7':     '#FF9F0A',  // 40m  orange
  '14':    '#FFD60A',  // 20m  jaune
  '21':    '#34C759',  // 15m  vert
  '28':    '#00C7BE',  // 10m  cyan-vert
  '50':    '#00D4FF',  // 6m   cyan
  '70':    '#40C8FF',  // 4m   bleu clair
  '144':   '#BF5AF2',  // 2m   violet
  '432':   '#FF8C00',  // 70cm orange-foncé
  '1296':  '#FF2D55',  // 23cm rose
  '2320':  '#00FF88',  // 13cm vert fluo
  '3400':  '#E040FB',  // 9cm  magenta
  'default':'#AAAAAA',
};

function initMap(){
  if(qsoMap) return;
  const homeLL = locLL(myLocator);
  const center = homeLL ? [homeLL.lat, homeLL.lon] : [46.5, 2.5];
  qsoMap = L.map('qsoMap', {zoomControl:true}).setView(center, 7);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
    attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom:14,
  }).addTo(qsoMap);
  // Marqueur station home
  if(homeLL){
    homeMarker = L.circleMarker([homeLL.lat, homeLL.lon],{
      radius:11, fillColor:'#FFD60A', color:'#000', weight:2,
      fillOpacity:1, zIndexOffset:1000,
    }).bindPopup(`<b>${escHtml(myCall)}</b><br>📍 ${escHtml(myLocator)}<br>Station HOME`).addTo(qsoMap);
  }
}

function refreshMapLayers(){
  if(!qsoMap) return;
  mapLayers.forEach(l => l.remove());
  mapLayers = [];
  const homeLL = locLL(myLocator);

  // Séparer contacts avec/sans locator
  const seen = {};
  const toPlot = [];
  let noLocCount = 0;
  qsoLog.slice().reverse().forEach(q => {
    if(!q.locator || q.locator.length < 6){ noLocCount++; return; }
    const key = q.call + '|' + q.locator;
    if(!seen[key]){ seen[key] = true; toPlot.push(q); }
  });

  toPlot.forEach(q => {
    const dxLL = locLL(q.locator);
    if(!dxLL) return;
    const col = BAND_COLORS[q.band] || BAND_COLORS['default'];
    const bandLabel = BAND_LABELS[q.band] || q.band + ' MHz';
    if(homeLL){
      const line = L.polyline([[homeLL.lat,homeLL.lon],[dxLL.lat,dxLL.lon]],{
        color:col, weight:1.8, opacity:.6, dashArray:'5 4',
      }).addTo(qsoMap);
      mapLayers.push(line);
    }
    const m = L.circleMarker([dxLL.lat,dxLL.lon],{
      radius:8, fillColor:col, color:'#000', weight:1.5, fillOpacity:.9,
    }).bindPopup(
      `<div style="font-family:monospace;font-size:14px;line-height:1.7">` +
      `<b style="font-size:15px">${escHtml(q.call)}</b><br>` +
      `📍 ${escHtml(q.locator)}<br>` +
      `📡 ${bandLabel} — ${escHtml(q.mode)}<br>` +
      `📏 ${q.dist||'?'} km — 🏆 ${q.points||0} pts` +
      `</div>`
    ).addTo(qsoMap);
    mapLayers.push(m);
  });

  let noLocInfo = document.getElementById('mapNoLocInfo');
  if(!noLocInfo){
    noLocInfo = document.createElement('div');
    noLocInfo.id = 'mapNoLocInfo';
    noLocInfo.style.cssText = 'position:absolute;bottom:10px;left:50%;transform:translateX(-50%);' +
      'background:rgba(0,0,0,.7);color:#aaa;font-size:14px;padding:4px 12px;border-radius:20px;z-index:999;pointer-events:none';
    document.getElementById('mapWrap').style.position = 'relative';
    document.getElementById('mapWrap').appendChild(noLocInfo);
  }
  noLocInfo.textContent = noLocCount > 0
    ? `⚠️ ${noLocCount} contact${noLocCount>1?'s':''} sans locator non affiché${noLocCount>1?'s':''}`
    : '';
  noLocInfo.style.display = noLocCount > 0 ? 'block' : 'none';
}

function toggleMapView(){
  const tableWrap = document.getElementById('logTableWrap');
  const mapWrap   = document.getElementById('mapWrap');
  const btn       = document.getElementById('mapToggleBtn');
  const showMap   = !mapWrap.classList.contains('visible');
  if(showMap){
    tableWrap.style.display = 'none';
    mapWrap.classList.add('visible');
    btn.classList.add('active');
    btn.textContent = '📋 TABLEAU';
    initMap();
    refreshMapLayers();
    setTimeout(() => qsoMap && qsoMap.invalidateSize(), 120);
  } else {
    mapWrap.classList.remove('visible');
    tableWrap.style.display = '';
    btn.classList.remove('active');
    btn.textContent = '🗺️ CARTE';
  }
}
