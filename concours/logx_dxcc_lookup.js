// EV-7 phase 2, 11e increment (docs/LogX_AI_PRD.md) -- table des prefixes
// DXCC + lookupDXCC() extraits tels quels de logx_logbook.js (extraction
// MECANIQUE, pas le motif bus d'evenements du pilote SCAN QSL PAPIER -- voir
// logx_scan_qsl.js). Analyse prealable (Workflow, cartographie + evaluation
// de 64 blocs) : bloc AUTONOME (IIFE auto-suffisante, zero dependance
// sortante) avec 4 appelants internes simples (badge pays du callsign,
// autocomplete, calcul de score/zone CQ) -- tous en LECTURE PURE, aucun
// n'execute au chargement du script (toujours a l'interieur d'une fonction
// appelee plus tard), donc aucun souci d'ordre de <script> malgre ce fichier
// charge AVANT logx_logbook.js.

// ─── TABLE PRÉFIXES DXCC ─────────────────────────────────────────────────────
// Clé = préfixe (le plus long match gagne), valeur = {c:pays, ct:continent, cq:zone, flag:emoji}
const CTY_PREFIX = (function(){
  const EU14={ct:'EU',cq:14}, EU15={ct:'EU',cq:15}, EU16={ct:'EU',cq:16};
  const EU18={ct:'EU',cq:18}, EU20={ct:'EU',cq:20}, EU40={ct:'EU',cq:40};
  const NA5={ct:'NA',cq:5}, NA8={ct:'NA',cq:8};
  return {
    // ── France & DOM-TOM ──
    'F'  :{...EU14,c:'France',flag:'🇫🇷'},    'TM':{...EU14,c:'France',flag:'🇫🇷'},
    'FM' :{...NA8, c:'Martinique',flag:'🇲🇶'}, 'FG':{...NA8, c:'Guadeloupe',flag:'🇬🇵'},
    'FY' :{ct:'SA',cq:9,c:'Guyane fr.',flag:'🇬🇫'},
    'FR' :{ct:'AF',cq:39,c:'La Réunion',flag:'🇷🇪'},
    'FK' :{ct:'OC',cq:28,c:'Nvl-Calédonie',flag:'🇳🇨'},
    'FO' :{ct:'OC',cq:31,c:'Polynésie fr.',flag:'🇵🇫'},
    'FP' :{...NA5, c:'St-Pierre-Miquelon',flag:'🇵🇲'},
    'FH' :{ct:'AF',cq:39,c:'Mayotte',flag:'🇾🇹'},
    // ── Europe Occidentale ──
    'G'  :{...EU14,c:'Angleterre',flag:'🏴󠁧󠁢󠁥󠁮󠁧󠁿'}, 'GW':{...EU14,c:'Pays de Galles',flag:'🏴󠁧󠁢󠁷󠁬󠁳󠁿'},
    'GM' :{...EU14,c:'Écosse',flag:'🏴󠁧󠁢󠁳󠁣󠁴󠁿'},    'GI':{...EU14,c:'Irlande du Nord',flag:'🇬🇧'},
    'GD' :{...EU14,c:'Île de Man',flag:'🇮🇲'},   'GJ':{...EU14,c:'Jersey',flag:'🇯🇪'},
    'GU' :{...EU14,c:'Guernesey',flag:'🇬🇬'},
    'PA' :{...EU14,c:'Pays-Bas',flag:'🇳🇱'},    'PI':{...EU14,c:'Pays-Bas',flag:'🇳🇱'},
    'ON' :{...EU14,c:'Belgique',flag:'🇧🇪'},    'OO':{...EU14,c:'Belgique',flag:'🇧🇪'},
    'LX' :{...EU14,c:'Luxembourg',flag:'🇱🇺'},
    'HB9':{...EU14,c:'Suisse',flag:'🇨🇭'},      'HB':{...EU14,c:'Suisse',flag:'🇨🇭'},
    'HB0':{...EU14,c:'Liechtenstein',flag:'🇱🇮'},
    'DL' :{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DA' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DB':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DC' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DD':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DE' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DF':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DG' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DH':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DJ' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DK':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DM' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DO':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'DQ' :{...EU14,c:'Allemagne',flag:'🇩🇪'}, 'DR':{...EU14,c:'Allemagne',flag:'🇩🇪'},
    'OE' :{...EU15,c:'Autriche',flag:'🇦🇹'},
    'CT' :{...EU14,c:'Portugal',flag:'🇵🇹'},   'CT3':{ct:'AF',cq:33,c:'Madère',flag:'🇵🇹'},
    'CU' :{...EU14,c:'Açores',flag:'🇵🇹'},
    'EA' :{...EU14,c:'Espagne',flag:'🇪🇸'},    'EH':{...EU14,c:'Espagne',flag:'🇪🇸'},
    'EA6':{...EU14,c:'Baléares',flag:'🇪🇸'},   'EA8':{ct:'AF',cq:33,c:'Canaries',flag:'🇮🇨'},
    'EI' :{...EU14,c:'Irlande',flag:'🇮🇪'},    'EJ':{...EU14,c:'Irlande',flag:'🇮🇪'},
    // ── Scandinavie ──
    'SM' :{...EU18,c:'Suède',flag:'🇸🇪'},    'SA':{...EU18,c:'Suède',flag:'🇸🇪'},
    'SB' :{...EU18,c:'Suède',flag:'🇸🇪'},    'SC':{...EU18,c:'Suède',flag:'🇸🇪'},
    'SE' :{...EU18,c:'Suède',flag:'🇸🇪'},    'SF':{...EU18,c:'Suède',flag:'🇸🇪'},
    'SG' :{...EU18,c:'Suède',flag:'🇸🇪'},    'SH':{...EU18,c:'Suède',flag:'🇸🇪'},
    'SI' :{...EU18,c:'Suède',flag:'🇸🇪'},    'SJ':{...EU18,c:'Suède',flag:'🇸🇪'},
    'SK' :{...EU18,c:'Suède',flag:'🇸🇪'},    'SL':{...EU18,c:'Suède',flag:'🇸🇪'},
    'LA' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LB':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'LC' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LD':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'LE' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LF':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'LG' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LH':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'LI' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LJ':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'LK' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LL':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'LM' :{...EU18,c:'Norvège',flag:'🇳🇴'},   'LN':{...EU18,c:'Norvège',flag:'🇳🇴'},
    'OH' :{...EU18,c:'Finlande',flag:'🇫🇮'},  'OH0':{...EU18,c:'Åland',flag:'🇫🇮'},
    'OZ' :{...EU14,c:'Danemark',flag:'🇩🇰'},
    'OY' :{...EU18,c:'Féroé',flag:'🇫🇴'},
    'TF' :{...EU40,c:'Islande',flag:'🇮🇸'},
    'JW' :{...EU40,c:'Svalbard',flag:'🇸🇯'},   'JX':{...EU40,c:'Jan Mayen',flag:'🇸🇯'},
    // ── Europe de l'Est ──
    'SP' :{...EU15,c:'Pologne',flag:'🇵🇱'},    'SN':{...EU15,c:'Pologne',flag:'🇵🇱'},
    'SO' :{...EU15,c:'Pologne',flag:'🇵🇱'},    'SQ':{...EU15,c:'Pologne',flag:'🇵🇱'},
    'SR' :{...EU15,c:'Pologne',flag:'🇵🇱'},
    'OK' :{...EU15,c:'Rép. Tchèque',flag:'🇨🇿'}, 'OL':{...EU15,c:'Rép. Tchèque',flag:'🇨🇿'},
    'OM' :{...EU15,c:'Slovaquie',flag:'🇸🇰'},
    'HA' :{...EU15,c:'Hongrie',flag:'🇭🇺'},    'HG':{...EU15,c:'Hongrie',flag:'🇭🇺'},
    'YU' :{...EU15,c:'Serbie',flag:'🇷🇸'},     'YT':{...EU15,c:'Serbie',flag:'🇷🇸'},
    '9A' :{...EU15,c:'Croatie',flag:'🇭🇷'},
    'S5' :{...EU15,c:'Slovénie',flag:'🇸🇮'},
    'E7' :{...EU15,c:'Bosnie-Herzégovine',flag:'🇧🇦'},
    'Z3' :{...EU15,c:'Macédoine du Nord',flag:'🇲🇰'},
    'ZA' :{...EU15,c:'Albanie',flag:'🇦🇱'},
    'SV' :{...EU20,c:'Grèce',flag:'🇬🇷'},      'SV9':{...EU20,c:'Crète',flag:'🇬🇷'},
    'SV5':{...EU20,c:'Dodécanèse',flag:'🇬🇷'},
    'LZ' :{...EU20,c:'Bulgarie',flag:'🇧🇬'},
    'YO' :{...EU20,c:'Roumanie',flag:'🇷🇴'},   'YP':{...EU20,c:'Roumanie',flag:'🇷🇴'},
    'IT9':{...EU15,c:'Sicile',flag:'🇮🇹'},     'IS':{...EU15,c:'Sardaigne',flag:'🇮🇹'},
    'I'  :{...EU15,c:'Italie',flag:'🇮🇹'},
    'ES' :{...EU15,c:'Estonie',flag:'🇪🇪'},
    'YL' :{...EU15,c:'Lettonie',flag:'🇱🇻'},
    'LY' :{...EU15,c:'Lituanie',flag:'🇱🇹'},
    'EU' :{...EU16,c:'Biélorussie',flag:'🇧🇾'}, 'EV':{...EU16,c:'Biélorussie',flag:'🇧🇾'},
    'EW' :{...EU16,c:'Biélorussie',flag:'🇧🇾'},
    'UR' :{...EU16,c:'Ukraine',flag:'🇺🇦'},    'UT':{...EU16,c:'Ukraine',flag:'🇺🇦'},
    'UZ' :{...EU16,c:'Ukraine',flag:'🇺🇦'},
    'UA' :{...EU16,c:'Russie',flag:'🇷🇺'},     'R':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RA' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RB':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RC' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RD':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RE' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RF':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RG' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RK':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RL' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RM':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RN' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RO':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RP' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RQ':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RU' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RV':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RW' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RX':{...EU16,c:'Russie',flag:'🇷🇺'},
    'RY' :{...EU16,c:'Russie',flag:'🇷🇺'},     'RZ':{...EU16,c:'Russie',flag:'🇷🇺'},
    '3A' :{...EU14,c:'Monaco',flag:'🇲🇨'},
    // ── Proche-Orient / Asie ──
    'TA' :{ct:'AS',cq:20,c:'Turquie',flag:'🇹🇷'},
    '4X' :{ct:'AS',cq:20,c:'Israël',flag:'🇮🇱'},   '4Z':{ct:'AS',cq:20,c:'Israël',flag:'🇮🇱'},
    '5B' :{ct:'AS',cq:20,c:'Chypre',flag:'🇨🇾'},
    'EK' :{ct:'AS',cq:21,c:'Arménie',flag:'🇦🇲'},
    'JA' :{ct:'AS',cq:25,c:'Japon',flag:'🇯🇵'},
    'BY' :{ct:'AS',cq:24,c:'Chine',flag:'🇨🇳'},    'BD':{ct:'AS',cq:24,c:'Chine',flag:'🇨🇳'},
    'HL' :{ct:'AS',cq:25,c:'Corée du Sud',flag:'🇰🇷'},
    // ── Amérique du Nord ──
    'W'  :{...NA5,c:'États-Unis',flag:'🇺🇸'}, 'K':{...NA5,c:'États-Unis',flag:'🇺🇸'},
    'N'  :{...NA5,c:'États-Unis',flag:'🇺🇸'},
    'VE' :{...NA5,c:'Canada',flag:'🇨🇦'},    'VA':{...NA5,c:'Canada',flag:'🇨🇦'},
    'VO' :{...NA5,c:'Canada',flag:'🇨🇦'},    'VY':{...NA5,c:'Canada',flag:'🇨🇦'},
    'XE' :{ct:'NA',cq:6,c:'Mexique',flag:'🇲🇽'},
    // ── Amérique du Sud ──
    'PY' :{ct:'SA',cq:11,c:'Brésil',flag:'🇧🇷'},
    'LU' :{ct:'SA',cq:13,c:'Argentine',flag:'🇦🇷'},
    'CE' :{ct:'SA',cq:12,c:'Chili',flag:'🇨🇱'},
    // ── Océanie ──
    'VK' :{ct:'OC',cq:29,c:'Australie',flag:'🇦🇺'},
    'ZL' :{ct:'OC',cq:32,c:'Nouvelle-Zélande',flag:'🇳🇿'},
    // ── Afrique ──
    'ZS' :{ct:'AF',cq:38,c:'Afrique du Sud',flag:'🇿🇦'},
  };
})();

// Retourne {c, ct, cq, flag} pour un indicatif, ou null
function lookupDXCC(call){
  if(!call) return null;
  const c = call.toUpperCase().split('/')[0];
  // Essai du préfixe le plus long vers le plus court (max 4 chars)
  for(let len = Math.min(c.length, 4); len >= 1; len--){
    const pfx = c.slice(0, len);
    if(CTY_PREFIX[pfx]) return CTY_PREFIX[pfx];
  }
  return null;
}
