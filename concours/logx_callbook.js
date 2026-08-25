// EV-7 phase 2, 16e increment (docs/LogX_AI_PRD.md) -- fiche CALLBOOK a la
// frappe (QRZ/HamQTH/HamDB, statut a la frappe, historique "deja contacte")
// extrait tel quel de logx_logbook.js (extraction MECANIQUE). Charge en
// <script> classique dans logx_logbook.html, AVANT logx_logbook.js (portee
// globale partagee).
//
// Etat interne prive au bloc (grep exhaustif sur tout le depot) :
// _checkTimer/_checkSeq, _qrzTimer/_qrzSeq, _stateAnnuaire,
// CALLBOOK_SOURCE_LABEL, _prevTimer/_prevSeq -- SAUF _stateAnnuaire, lu (pas
// ecrit) depuis submitQSO() dans logx_logbook.js (reste dans ce fichier),
// portee globale partagee, corps de fonction uniquement -- sans risque
// d'ordre de <script>.
//
// 3 points d'entree, tous appeles depuis logx_logbook.js (jamais cables en
// HTML directement) : lookupQRZ(call)/checkCallStatus(call)/
// checkPrevQsos(call), tous les 3 appeles ensemble a la frappe de
// l'indicatif (onLocatorInput()/oninput du champ indicatif, reste dans
// logx_logbook.js).
//
// fmtDate(d) est aussi consommee par logx_awards.js (deja un fichier EV-7
// extrait, 4e increment) -- portee globale partagee, uniquement a
// l'interieur de corps de fonction cote logx_awards.js, ordre de <script>
// entre les deux fichiers extraits sans importance.

// ─── STATUT À LA FRAPPE (serveur) ────────────────────────────────────────────
// GET /log/check : nouveau / doublon / nouveau_mult, évalué par le MOTEUR DE
// SCORING contre le log partagé multi-op (pas seulement le log local).
let _checkTimer = null;
let _checkSeq = 0;

// ─── FICHE CALLBOOK (à la frappe) ────────────────────────────────────────────
// Affiche nom / QTH / locator du correspondant, en cascade QRZ (si identifiants
// configurés) -> HamQTH -> HamDB (côté serveur, logx_callbook.py).
// Debounce plus long (600 ms) : une requête réseau par indicatif fini.
let _qrzTimer = null, _qrzSeq = 0;
// Dernier état US rapporté par l'annuaire, avec l'indicatif auquel il se
// rapporte ({call, state}). L'indicatif est conservé À DESSEIN : la réponse
// arrive en différé, et sans cette vérification l'état d'une station
// précédente se retrouverait collé au QSO en cours de saisie.
let _stateAnnuaire = null;
const CALLBOOK_SOURCE_LABEL = {hamqth: 'HamQTH', hamdb: 'HamDB'};  // QRZ = pas de tag (source par défaut)

// Dernière fiche d'annuaire reçue, CONSERVÉE pour l'enregistrement du QSO.
// Jusqu'ici, nom et QTH étaient récupérés, affichés à la frappe… puis JETÉS :
// seuls le locator et l'état US survivaient à l'enregistrement. Un opérateur
// qui relit son carnet six mois plus tard n'avait donc plus aucune trace de
// QUI il avait contacté — alors que l'information avait bel et bien transité.
//
// L'indicatif est mémorisé AVEC la fiche, et revérifié à l'enregistrement :
// sans ça, une fiche encore affichée pour un indicatif abandonné (l'opérateur
// efface et retape) serait attachée au mauvais QSO. Même raison d'être que le
// jeton _qrzSeq qui protège déjà l'AFFICHAGE des réponses tardives.
let _callbookCourant = null;

// Lue par submitQSO() (logx_logbook.js). Rend {} si la fiche mémorisée ne
// correspond pas à l'indicatif en cours d'enregistrement — jamais une donnée
// approximative : mieux vaut un champ vide qu'un nom faux dans le carnet.
function callbookPourQso(call){
  const c = String(call || '').trim().toUpperCase();
  if(!_callbookCourant || !c || _callbookCourant.call !== c) return {};
  const out = {};
  if(_callbookCourant.name) out.name = _callbookCourant.name;
  if(_callbookCourant.qth) out.qth = _callbookCourant.qth;
  if(_callbookCourant.country) out.country = _callbookCourant.country;
  return out;
}

function lookupQRZ(call){
  clearTimeout(_qrzTimer);
  const row = document.getElementById('qrzInfoRow');
  const el = document.getElementById('qrzInfo');
  const photo = document.getElementById('qrzPhoto');
  if(!el || !row) return;
  if(!call || call.length < 3){ row.style.display = 'none'; return; }
  const seq = ++_qrzSeq;
  _qrzTimer = setTimeout(async () => {
    try{
      const r = await fetch('/qrz/lookup?call=' + encodeURIComponent(call));
      if(!r.ok || seq !== _qrzSeq) return;
      const d = await r.json();
      if(!d.ok){ row.style.display = 'none'; return; }
      // Mémoriser AVANT l'affichage : ce sont les mêmes données, mais elles
      // doivent désormais survivre à l'enregistrement (voir _callbookCourant).
      // On garde les valeurs BRUTES, non échappées : l'échappement ci-dessous
      // ne concerne que l'injection en innerHTML. Le carnet, lui, stocke du
      // texte — et l'export ADIF ré-échappe selon ses propres règles.
      _callbookCourant = {
        call: String(call || '').trim().toUpperCase(),
        name: d.name || '', qth: d.qth || '', country: d.country || '',
      };
      // Données d'annuaires en ligne tiers (QRZ/HamQTH/HamDB) : origine Internet
      // hors du contrôle de l'utilisateur → échappées avant insertion en innerHTML
      // (un champ QTH contenant du HTML exécuterait sinon du script à la frappe).
      const bits = [];
      if(d.name) bits.push('👤 ' + escHtml(d.name));
      if(d.qth)  bits.push('📍 ' + escHtml(d.qth));
      if(d.grid) bits.push('🗺 ' + escHtml(d.grid));
      if(d.country && !d.qth) bits.push(escHtml(d.country));
      const sourceLabel = CALLBOOK_SOURCE_LABEL[d.source];
      if(sourceLabel) bits.push('· ' + escHtml(sourceLabel));
      el.innerHTML = bits.join(' · ');
      // Photo (QRZ uniquement, comptes abonnés) : `.src` n'exécute jamais de
      // script même sur une URL malveillante, mais on revérifie quand même le
      // schéma ici — défense en profondeur, le serveur (logx_qrz.py) filtre déjà.
      if(photo){
        if(d.image && /^https?:\/\//i.test(d.image)){
          photo.onerror = () => { photo.style.display = 'none'; };   // lien mort (ex. QRZ ayant retiré la fiche depuis)
          photo.src = d.image;
          photo.style.display = 'block';
        } else {
          photo.style.display = 'none';
          photo.src = '';
        }
      }
      row.style.display = (bits.length || (photo && photo.style.display === 'block')) ? 'flex' : 'none';
      // Pré-remplit le locator s'il est vide et que la source en connaît un
      const locInput = document.getElementById('inputLocator');
      if(locInput && !locInput.value && d.grid && d.grid.length >= 4){
        locInput.value = d.grid;
        onLocatorInput();
      }
      // Pré-remplit le PRÉNOM s'il est vide et que la source en connaît un (QRZ ;
      // HamQTH renvoie ''). TOUJOURS corrigeable, et l'édition manuelle enrichit
      // la base interne à l'enregistrement (source de prénom hors QRZ).
      const nameInput = document.getElementById('inputName');
      if(nameInput && !nameInput.value && d.name){ nameInput.value = d.name; }
      // État US retenu pour le QSO : c'est la SEULE source à la saisie, l'état
      // ne se déduisant pas de l'indicatif (un W6 peut habiter n'importe où).
      // Mémorisé avec l'indicatif auquel il se rapporte : sans ça, un état
      // resté d'une frappe précédente serait recopié sur le QSO suivant.
      _stateAnnuaire = (d.state && /^[A-Z]{2}$/.test(String(d.state).toUpperCase()))
        ? {call: call, state: String(d.state).toUpperCase()} : null;
    }catch(e){ /* réseau callbook indispo : rien */ }
  }, 600);
}

function checkCallStatus(call){
  clearTimeout(_checkTimer);
  const badge = document.getElementById('callStatusBadge');
  if(!badge) return;
  if(!call || call.length < 3){ badge.style.display = 'none'; return; }
  const seq = ++_checkSeq;
  _checkTimer = setTimeout(async () => {
    try{
      const r = await fetch(`/log/check?call=${encodeURIComponent(call)}` +
                            `&band=${encodeURIComponent(currentBand || '')}` +
                            `&mode=${encodeURIComponent(currentMode || '')}`);
      if(!r.ok || seq !== _checkSeq) return;   // réponse périmée : ignorer
      const st = await r.json();
      if(st.status === 'inconnu'){ badge.style.display = 'none'; return; }
      const styles = {
        doublon:      ['⚠️ DOUBLON sur cette bande', 'var(--red)'],
        nouveau_mult: ['📈 NOUVEAU MULTIPLICATEUR' + (st.mult_type ? ' (' + st.mult_type + ')' : ''), 'var(--green)'],
        nouveau:      ['✔ nouveau' + (st.points ? ' · ' + st.points + ' pt' + (st.points > 1 ? 's' : '') : ''), 'var(--accent2)'],
      };
      const [txt, col] = styles[st.status] || styles.nouveau;
      badge.textContent = txt;
      badge.style.color = col;
      badge.style.border = '1px solid ' + col;
      badge.style.display = 'block';
      badge.title = st.explanation || '';
    }catch(e){ /* hors ligne : badge local dupWarn suffit */ }
  }, 250);
}

// ─── « DÉJÀ CONTACTÉ » (historique station, tous concours) ───────────────────
// À la frappe d'un indicatif, montre tous les QSO passés avec cette station
// (dates, bandes, confirmé LoTW) + alerte « NOUVEAU PAYS/DÉPARTEMENT » à vie —
// façon fiche « previous contacts » de Log4OM / HRD.
let _prevTimer = null, _prevSeq = 0;

function checkPrevQsos(call){
  clearTimeout(_prevTimer);
  const el = document.getElementById('prevQsos');
  if(!el) return;
  if(!call || call.length < 3){ el.style.display = 'none'; renderLotwGrid(null); return; }
  const seq = ++_prevSeq;
  _prevTimer = setTimeout(async () => {
    try{
      const r = await fetch(`/call/history?call=${encodeURIComponent(call)}` +
                            `&band=${encodeURIComponent(currentBand || '')}` +
                            `&mode=${encodeURIComponent(currentMode || '')}`);
      if(!r.ok || seq !== _prevSeq) return;
      const d = await r.json();
      renderLotwGrid(d.lotw_grid);
      const parts = [];
      // Alerte « nouveau à vie » (pays / département jamais contacté)
      (d.new_one || []).forEach(n => {
        parts.push(`<div style="color:var(--green);font-weight:700">🌟 ${n.label}</div>`);
      });
      // Besoin LoTW : « pas confirmé LoTW » n'est PAS « jamais contacté ». Un
      // pays travaillé dix fois mais jamais confirmé ne compte toujours pas
      // pour le DXCC — et une confirmation eQSL ou papier n'y change rien.
      // L'entité jamais confirmée nulle part passe en rouge : c'est celle qui
      // fait avancer le compteur.
      if(d.lotw_need && d.lotw_need.besoin){
        const jamais = d.lotw_need.raison === 'jamais_confirme';
        parts.push(`<div style="color:${jamais ? 'var(--red)' : 'var(--accent2)'};font-weight:700">` +
                   `${jamais ? '📛' : '📻'} ${escHtml(d.lotw_need.label)}</div>`);
      }
      // État US / province canadienne, quand on la connaît (même champ ADIF
      // STATE des deux côtés de la frontière).
      if(d.state){
        parts.push(`<div style="color:var(--muted)">🏛 ${escHtml(d.state)}</div>`);
      }
      // Utilisateur LoTW. Décisif juste au-dessus de l'alerte « pas confirmé
      // LoTW » : si le correspondant n'uploade pas, le créneau ne se comblera
      // jamais avec lui. `undefined`/null = liste pas encore téléchargée, on
      // n'affiche RIEN plutôt que d'annoncer « n'utilise pas LoTW » à tort.
      if(d.lotw_user === true){
        const depuis = d.lotw_last ? ` · dernier envoi ${escHtml(d.lotw_last)}` : '';
        parts.push(`<div style="color:var(--green)">✅ LoTW${depuis}</div>`);
      } else if(d.lotw_user === false){
        parts.push(`<div style="color:var(--muted)">🚫 pas sur LoTW — ne sera jamais confirmé</div>`);
      }
      if(d.count > 0){
        const conf = d.confirmed ? ` · <span style="color:var(--green)">${d.confirmed} confirmé${d.confirmed>1?'s':''}</span>` : '';
        const bands = d.bands && d.bands.length ? ` sur ${escHtml(d.bands.join('/'))} MHz` : '';
        parts.push(`<div><b style="color:var(--accent2)">${d.count} QSO</b>${bands}${conf}` +
                   (d.last ? ` · dernier ${fmtDate(d.last)}` : '') + '</div>');
        // Les 3 plus récents
        d.qsos.slice(0,3).forEach(q => {
          parts.push(`<div style="opacity:.75">${fmtDate(q.date)} — ${escHtml(q.band)} MHz ${escHtml(q.mode)}` +
                     `${q.contest ? ' · ' + escHtml(q.contest.replace(/_/g,' ')) : ''}` +
                     `${q.confirmed ? ' ✅' : ''}</div>`);
        });
      } else if(!(d.new_one||[]).length){
        parts.push(`<span style="color:var(--muted)">jamais contacté</span>`);
      }
      el.innerHTML = parts.join('');
      el.style.display = parts.length ? 'block' : 'none';
    }catch(e){ el.style.display = 'none'; renderLotwGrid(null); }
  }, 350);
}

// Mini-grille bande×mode LoTW (logx_awards.lotw_grid) : vue d'ensemble en un
// coup d'œil de l'entité en cours de saisie, complément visuel à l'alerte
// texte 📻/📛 ci-dessus (qui ne porte que sur LE créneau bande/mode courant).
// Bandes/modes/statuts viennent tous d'un jeu fixe côté serveur (jamais de
// texte libre d'annuaire tiers ici) -- pas d'échappement nécessaire.
const LOTW_GRID_MODE_LABEL = {CW: 'CW', PHONE: 'PH', DIGITAL: 'DG'};
const LOTW_GRID_STATUS_COLOR = {confirmed: 'var(--green)', worked: 'var(--accent2)', none: 'transparent'};
const LOTW_GRID_STATUS_LABEL = {confirmed: 'confirmé LoTW', worked: 'travaillé, pas confirmé LoTW', none: 'jamais travaillé'};

function renderLotwGrid(g){
  const wrap = document.getElementById('lotwGrid');
  if(!wrap) return;
  if(!g || !g.active){ wrap.style.display = 'none'; return; }
  const modes = g.modes || [];
  let html = `<div style="font-size:9px;color:var(--muted);letter-spacing:.5px;margin-bottom:3px">${escHtml(g.country || '')}</div>`;
  html += '<div style="display:flex;gap:2px;margin-left:32px">' +
    modes.map(m => `<span style="display:inline-block;width:16px;font-size:9px;color:var(--muted);text-align:center">${LOTW_GRID_MODE_LABEL[m] || m}</span>`).join('') +
    '</div>';
  (g.bands || []).forEach(b => {
    const row = g.grid && g.grid[b] ? g.grid[b] : {};
    html += '<div style="display:flex;align-items:center;gap:2px">' +
      `<span style="display:inline-block;width:30px;font-size:9px;color:var(--muted);text-align:right;margin-right:2px">${b}</span>` +
      modes.map(m => {
        const st = row[m] || 'none';
        const bg = LOTW_GRID_STATUS_COLOR[st] || 'transparent';
        const bd = st === 'none' ? '1px solid var(--border)' : '1px solid transparent';
        return `<span title="${b} MHz ${LOTW_GRID_MODE_LABEL[m] || m} : ${LOTW_GRID_STATUS_LABEL[st] || st}" ` +
               `style="display:inline-block;width:16px;height:12px;background:${bg};border:${bd};border-radius:2px"></span>`;
      }).join('') + '</div>';
  });
  wrap.innerHTML = html;
  wrap.style.display = 'block';
}

function fmtDate(d){
  d = String(d || '');
  return d.length === 8 ? `${d.slice(6,8)}/${d.slice(4,6)}/${d.slice(0,4)}` : d;
}
