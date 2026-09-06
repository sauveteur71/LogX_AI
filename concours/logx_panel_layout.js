// EV-7 49e increment : RESERVE D'ESPACE BAS + TOGGLE CHAT (mise en page des
// panneaux flottants) -- extrait de logx_logbook.js (docs/LogX_AI_PRD.md).
// Charge en <script> classique dans logx_logbook.html, AVANT logx_logbook.js --
// portee globale partagee (logbook uniquement, comme avant l'extraction).
//
// Contient : _reserveBottomSpace() (reserve la place sous le tableau du log
// pour les panneaux position:fixed CHAT/CW), _majReservesBas() et toggleChat().
// Non appelees au TOP-LEVEL ; consommees par logx_partner_view.js /
// logx_sstv_panel.js / le coeur et un handler resize -- a l'usage.

// Les panneaux CHAT et DÉCODEUR CW sont en position:fixed, ancrés bas-droite/
// bas-gauche — ils flottent donc AU-DESSUS du contenu défilant en dessous
// (dernier QSO saisis / tableau du log) au lieu de le pousser. Sans cette
// marge réservée, le panneau recouvre littéralement les dernières lignes,
// qui semblent alors "manquantes" — d'autant plus visible quand la fenêtre
// est basse (portable, /P) puisque .saisie-panel/.log-table-wrap défilent
// alors bien avant d'atteindre leur propre fin.
function _reserveBottomSpace(panel, scrollEl){
  if(!panel || !scrollEl) return;
  // RÉDUIT max-height (ne rajoute PAS de padding-bottom) : un padding-bottom
  // plus grand que la boîte la force à GRANDIR pour pouvoir le contenir —
  // par construction CSS, une boîte ne peut jamais être plus petite que ses
  // propres marges internes (padding+bordure), donc le padding « gagne »
  // sur toute hauteur/max-height qu'on lui impose par ailleurs (vérifié
  // empiriquement : max-height ET height explicites sont tous deux ignorés
  // dès que le padding-bottom les dépasse). Sur un conteneur flex:1 court
  // (ex: .saisie-secondary, coincé entre la saisie et le bas de colonne),
  // ça le fait déborder de SON PROPRE parent — et si ce parent scrolle
  // aussi (.saisie-panel), révéler le bas du conteneur reviendrait à faire
  // défiler la zone de SAISIE hors champ, interdit ici (cf. "ZONE
  // SECONDAIRE ... ne rogne jamais la saisie"). Réduire max-height n'a pas
  // ce problème : le contenu qui ne rentre plus scrolle via l'overflow-y:
  // auto déjà en place, sans jamais faire grandir le conteneur au-delà de
  // ce qu'il occupait chez son parent. Plancher à 0 (pas plus) : un
  // plancher plus haut forcerait un chevauchement PLUS GRAND avec le
  // panneau flottant dès que la place naturelle est juste inférieure à ce
  // plancher (vérifié empiriquement) — 0 laisse toujours la zone se réduire
  // exactement à ce qu'il faut pour ne jamais passer sous le panneau,
  // quitte à devenir minuscule (mais jamais négative/incohérente) quand la
  // fenêtre est vraiment trop basse pour tout afficher.
  scrollEl.style.maxHeight = 'none';           // repart d'un calcul flex propre avant de mesurer
  const naturalHeight = scrollEl.getBoundingClientRect().height;
  scrollEl.style.maxHeight = Math.max(0, naturalHeight - panel.offsetHeight) + 'px';
}

// Réserve l'espace du panneau CHAT (bas-droite, flottant sur .log-table-wrap
// — le seul panneau encore flottant depuis que CW/keyer vocal ont leur propre
// bandeau plein largeur .keyer-dock, 04/08/2026, qui n'a plus besoin de cette
// mécanique : il pousse .main dans le flux normal, il ne flotte plus dessus).
// Le plafond posé par _reserveBottomSpace() est une valeur ABSOLUE en pixels,
// mesurée à un instant donné : elle devient fausse dès que la mise en page
// bouge.
//
// DÉFAUT RÉEL, signalé par l'utilisateur puis reproduit à la mesure : l'appel
// ne se faisait qu'au DOMContentLoaded, donc AVANT que init() (async : config
// serveur, log, calldb) ait fini de peupler et d'afficher les panneaux. Le
// plafond était calculé sur une mise en page transitoire, puis gardé tel quel
// pour toute la session.
//
// Et aucun recalcul au redimensionnement : agrandir la fenêtre ne rendait
// jamais la hauteur gagnée.
function _majReservesBas(){
  _reserveBottomSpace(document.getElementById('chatPanel'),
                      document.querySelector('.log-table-wrap'));
}

function toggleChat(){
  const panel = document.getElementById('chatPanel');
  panel.classList.toggle('open');
  _reserveBottomSpace(panel, document.querySelector('.log-table-wrap'));
  if(panel.classList.contains('open')){
    const unread = document.getElementById('chatUnread');
    if(unread){ unread.style.display = 'none'; unread.textContent = '0'; }
    const body = document.getElementById('chatBody');
    if(body) body.scrollTop = body.scrollHeight;
    document.getElementById('chatInput').focus();
    // Poll immédiat à l'ouverture : le poll de fond peut être en cadence
    // ralentie (15s, panneau fermé) — ne pas attendre jusqu'à ce délai pour
    // afficher les messages reçus pendant que le panneau était fermé.
    pollChat();
  }
}
