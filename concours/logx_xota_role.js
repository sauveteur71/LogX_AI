// ─── MODE DE SESSION XOTA : chasseur / portable / les deux ────────────────────
// L'opérateur change de rôle d'une session à l'autre : un jour au sommet
// (portable), le lendemain au shack (chasse), le surlendemain les deux (S2S).
// Un réglage FIGÉ dans CONFIG demanderait trop de clics -> le rôle se choisit
// à l'accueil ET se rebascule en un geste depuis le haut du logbook, et il
// SE SOUVIENT du dernier choix (défaut).
//
// Module PUR et partagé (accueil + logbook), logique testable sans DOM :
//   - roles internes 'chasse' | 'portable' | 'mixte' (vocabulaire du dépôt :
//     jamais « activateur » en texte visible -> libellé « Portable ») ;
//   - roleConfig(role) -> {chasse:bool, portable:bool} pilote la visibilité des
//     panneaux/champs et les exports du logbook.

(function(global){
  'use strict';

  var CLE = 'logx_xota_role';
  var DEFAUT = 'mixte';                        // ne rien cacher tant qu'aucun choix
  var VALIDES = { chasse: 1, portable: 1, mixte: 1 };

  // Métadonnées d'affichage (tuiles accueil + bascule logbook). L'icône reste
  // un emoji simple, choisi par F4GLD ; convertible en SVG plus tard.
  var ROLES = [
    { id: 'chasse',   icone: '🎯', label: 'Chasseur', hint: 'chasse — depuis le shack' },
    { id: 'portable', icone: '🏕️', label: 'Portable', hint: 'expédition — au sommet/parc' },
    { id: 'mixte',    icone: '⚡', label: 'Les deux',  hint: 'complet — S2S / P2P' },
  ];

  function normaliser(r){
    r = (r || '').toString().trim().toLowerCase();
    return VALIDES[r] ? r : null;
  }

  // Rôle courant (dernier choisi, sinon défaut). Tolérant si localStorage absent.
  function getRole(){
    try{ return normaliser(global.localStorage && global.localStorage.getItem(CLE)) || DEFAUT; }
    catch(e){ return DEFAUT; }
  }

  // Persiste le choix (mémorisation). Renvoie le rôle réellement retenu.
  function setRole(r){
    var v = normaliser(r) || DEFAUT;
    try{ global.localStorage && global.localStorage.setItem(CLE, v); }catch(e){}
    return v;
  }

  // Ce que le rôle ALLUME. chasse -> champ réf. correspondant + points/exports de
  // chasse ; portable -> setup expédition + avancement + export prêt-à-téléverser ;
  // mixte -> les deux (S2S/P2P mis en valeur).
  function roleConfig(role){
    role = normaliser(role) || DEFAUT;
    return {
      chasse:   role === 'chasse'   || role === 'mixte',
      portable: role === 'portable' || role === 'mixte',
    };
  }

  function labelDe(role){
    role = normaliser(role) || DEFAUT;
    for(var i = 0; i < ROLES.length; i++){ if(ROLES[i].id === role) return ROLES[i].label; }
    return role;
  }

  global.LogxXotaRole = {
    CLE: CLE, DEFAUT: DEFAUT, ROLES: ROLES,
    normaliser: normaliser, getRole: getRole, setRole: setRole,
    roleConfig: roleConfig, labelDe: labelDe,
  };
  if(typeof module !== 'undefined' && module.exports) module.exports = global.LogxXotaRole;

})(typeof window !== 'undefined' ? window : this);
