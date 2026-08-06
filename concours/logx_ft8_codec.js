// ─── CODEC FT8 (empaquetage/CRC/LDPC/Costas) — DANS LE NAVIGATEUR ────────────
// Même choix architectural que le décodeur RTTY (logx_rttydecoder.js) et CW :
// rien à installer côté serveur, ça marche sur un poste secondaire qui n'a
// que le navigateur. Ce fichier ne contient QUE le protocole (bits <-> texte,
// bits <-> symboles) — la capture/synthèse audio est dans logx_ft8_dsp.js.
//
// Les CONSTANTES DE PROTOCOLE ci-dessous (motif Costas, table de Gray,
// polynôme CRC-14, matrices LDPC(174,91)) sont des paramètres FIXES de la
// norme FT8 elle-même (publiée dans Franke/Somerville/Taylor, "The FT4 and
// FT8 Communication Protocols", QEX juillet/août 2020) — pas un choix
// d'implémentation. Elles sont reprises telles quelles depuis l'implémentation
// de référence open-source kgoba/ft8_lib (licence MIT, Kārlis Goba YL3JG,
// https://github.com/kgoba/ft8_lib) : toute implémentation FT8 correcte, quel
// que soit le langage, utilise EXACTEMENT ces mêmes tables — c'est ce qui
// permet l'interopérabilité avec WSJT-X/JTDX/MSHV sur l'air. Le CODE autour
// (structures de données, boucles, nommage) est une réécriture originale en
// JavaScript, pas une traduction ligne à ligne du C.

// ─── Constantes de temporisation/constellation ───────────────────────────────
const FT8_SYMBOL_PERIOD = 0.160;   // durée d'un symbole (s)
const FT8_SLOT_TIME = 15.0;        // durée d'un créneau d'émission (s)
const FT8_TONE_SPACING = 1 / FT8_SYMBOL_PERIOD; // 6.25 Hz
const FT8_ND = 58;                 // symboles de données
const FT8_NN = 79;                 // symboles totaux (3x7 synchro + 58 données)
const FT8_LENGTH_SYNC = 7;
const FT8_NUM_SYNC = 3;
const FT8_SYNC_OFFSET = 36;        // écart entre débuts de groupes de synchro

const FTX_LDPC_N = 174;            // bits codés (payload + CRC + parité)
const FTX_LDPC_K = 91;             // bits utiles (77 payload + 14 CRC)
const FTX_LDPC_M = 83;             // bits de parité

const FT8_CRC_POLYNOMIAL = 0x2757; // CRC-14 (sans le 1 de tête MSB)
const FT8_CRC_WIDTH = 14;

// Motif Costas 7x7 (synchronisation), utilisé 3 fois (début/milieu/fin trame)
const FT8_COSTAS_PATTERN = [3, 1, 4, 0, 6, 5, 2];

// Table de Gray (3 bits -> indice de ton 0..7) et son inverse (ton -> 3 bits)
const FT8_GRAY_MAP = [0, 1, 3, 2, 5, 6, 4, 7];
const FT8_GRAY_MAP_INV = (function(){
  const inv = new Array(8);
  for(let i = 0; i < 8; i++) inv[FT8_GRAY_MAP[i]] = i;
  return inv;
})();

// ─── Tables de caractères (voir ft8/text.h de ft8_lib) ───────────────────────
const FT8_CHAR_TABLE_FULL = ' 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ+-./?';               // 42
const FT8_CHAR_TABLE_ALPHANUM_SPACE_SLASH = ' 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/';    // 38
const FT8_CHAR_TABLE_ALPHANUM_SPACE = ' 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';            // 37
const FT8_CHAR_TABLE_LETTERS_SPACE = ' ABCDEFGHIJKLMNOPQRSTUVWXYZ';                       // 27
const FT8_CHAR_TABLE_ALPHANUM = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';                   // 36
const FT8_CHAR_TABLE_NUMERIC = '0123456789';                                              // 10

function nchar(c, table){ return table.indexOf(c); }
function charn(n, table){ return (n >= 0 && n < table.length) ? table[n] : '?'; }

// ─── Matrice génératrice LDPC(174,91) — 83 lignes x 12 octets (91 bits utiles
// empaquetés MSB en premier, complétés à 96 bits). parité[j] = XOR des bits
// utiles i pour lesquels le bit i de la ligne j vaut 1 (code systématique :
// codeword = [91 bits utiles][83 bits de parité]).
// Source : kFTX_LDPC_generator dans kgoba/ft8_lib ft8/constants.c (MIT).
const FT8_LDPC_GENERATOR = [
  [0x83, 0x29, 0xce, 0x11, 0xbf, 0x31, 0xea, 0xf5, 0x09, 0xf2, 0x7f, 0xc0],
  [0x76, 0x1c, 0x26, 0x4e, 0x25, 0xc2, 0x59, 0x33, 0x54, 0x93, 0x13, 0x20],
  [0xdc, 0x26, 0x59, 0x02, 0xfb, 0x27, 0x7c, 0x64, 0x10, 0xa1, 0xbd, 0xc0],
  [0x1b, 0x3f, 0x41, 0x78, 0x58, 0xcd, 0x2d, 0xd3, 0x3e, 0xc7, 0xf6, 0x20],
  [0x09, 0xfd, 0xa4, 0xfe, 0xe0, 0x41, 0x95, 0xfd, 0x03, 0x47, 0x83, 0xa0],
  [0x07, 0x7c, 0xcc, 0xc1, 0x1b, 0x88, 0x73, 0xed, 0x5c, 0x3d, 0x48, 0xa0],
  [0x29, 0xb6, 0x2a, 0xfe, 0x3c, 0xa0, 0x36, 0xf4, 0xfe, 0x1a, 0x9d, 0xa0],
  [0x60, 0x54, 0xfa, 0xf5, 0xf3, 0x5d, 0x96, 0xd3, 0xb0, 0xc8, 0xc3, 0xe0],
  [0xe2, 0x07, 0x98, 0xe4, 0x31, 0x0e, 0xed, 0x27, 0x88, 0x4a, 0xe9, 0x00],
  [0x77, 0x5c, 0x9c, 0x08, 0xe8, 0x0e, 0x26, 0xdd, 0xae, 0x56, 0x31, 0x80],
  [0xb0, 0xb8, 0x11, 0x02, 0x8c, 0x2b, 0xf9, 0x97, 0x21, 0x34, 0x87, 0xc0],
  [0x18, 0xa0, 0xc9, 0x23, 0x1f, 0xc6, 0x0a, 0xdf, 0x5c, 0x5e, 0xa3, 0x20],
  [0x76, 0x47, 0x1e, 0x83, 0x02, 0xa0, 0x72, 0x1e, 0x01, 0xb1, 0x2b, 0x80],
  [0xff, 0xbc, 0xcb, 0x80, 0xca, 0x83, 0x41, 0xfa, 0xfb, 0x47, 0xb2, 0xe0],
  [0x66, 0xa7, 0x2a, 0x15, 0x8f, 0x93, 0x25, 0xa2, 0xbf, 0x67, 0x17, 0x00],
  [0xc4, 0x24, 0x36, 0x89, 0xfe, 0x85, 0xb1, 0xc5, 0x13, 0x63, 0xa1, 0x80],
  [0x0d, 0xff, 0x73, 0x94, 0x14, 0xd1, 0xa1, 0xb3, 0x4b, 0x1c, 0x27, 0x00],
  [0x15, 0xb4, 0x88, 0x30, 0x63, 0x6c, 0x8b, 0x99, 0x89, 0x49, 0x72, 0xe0],
  [0x29, 0xa8, 0x9c, 0x0d, 0x3d, 0xe8, 0x1d, 0x66, 0x54, 0x89, 0xb0, 0xe0],
  [0x4f, 0x12, 0x6f, 0x37, 0xfa, 0x51, 0xcb, 0xe6, 0x1b, 0xd6, 0xb9, 0x40],
  [0x99, 0xc4, 0x72, 0x39, 0xd0, 0xd9, 0x7d, 0x3c, 0x84, 0xe0, 0x94, 0x00],
  [0x19, 0x19, 0xb7, 0x51, 0x19, 0x76, 0x56, 0x21, 0xbb, 0x4f, 0x1e, 0x80],
  [0x09, 0xdb, 0x12, 0xd7, 0x31, 0xfa, 0xee, 0x0b, 0x86, 0xdf, 0x6b, 0x80],
  [0x48, 0x8f, 0xc3, 0x3d, 0xf4, 0x3f, 0xbd, 0xee, 0xa4, 0xea, 0xfb, 0x40],
  [0x82, 0x74, 0x23, 0xee, 0x40, 0xb6, 0x75, 0xf7, 0x56, 0xeb, 0x5f, 0xe0],
  [0xab, 0xe1, 0x97, 0xc4, 0x84, 0xcb, 0x74, 0x75, 0x71, 0x44, 0xa9, 0xa0],
  [0x2b, 0x50, 0x0e, 0x4b, 0xc0, 0xec, 0x5a, 0x6d, 0x2b, 0xdb, 0xdd, 0x00],
  [0xc4, 0x74, 0xaa, 0x53, 0xd7, 0x02, 0x18, 0x76, 0x16, 0x69, 0x36, 0x00],
  [0x8e, 0xba, 0x1a, 0x13, 0xdb, 0x33, 0x90, 0xbd, 0x67, 0x18, 0xce, 0xc0],
  [0x75, 0x38, 0x44, 0x67, 0x3a, 0x27, 0x78, 0x2c, 0xc4, 0x20, 0x12, 0xe0],
  [0x06, 0xff, 0x83, 0xa1, 0x45, 0xc3, 0x70, 0x35, 0xa5, 0xc1, 0x26, 0x80],
  [0x3b, 0x37, 0x41, 0x78, 0x58, 0xcc, 0x2d, 0xd3, 0x3e, 0xc3, 0xf6, 0x20],
  [0x9a, 0x4a, 0x5a, 0x28, 0xee, 0x17, 0xca, 0x9c, 0x32, 0x48, 0x42, 0xc0],
  [0xbc, 0x29, 0xf4, 0x65, 0x30, 0x9c, 0x97, 0x7e, 0x89, 0x61, 0x0a, 0x40],
  [0x26, 0x63, 0xae, 0x6d, 0xdf, 0x8b, 0x5c, 0xe2, 0xbb, 0x29, 0x48, 0x80],
  [0x46, 0xf2, 0x31, 0xef, 0xe4, 0x57, 0x03, 0x4c, 0x18, 0x14, 0x41, 0x80],
  [0x3f, 0xb2, 0xce, 0x85, 0xab, 0xe9, 0xb0, 0xc7, 0x2e, 0x06, 0xfb, 0xe0],
  [0xde, 0x87, 0x48, 0x1f, 0x28, 0x2c, 0x15, 0x39, 0x71, 0xa0, 0xa2, 0xe0],
  [0xfc, 0xd7, 0xcc, 0xf2, 0x3c, 0x69, 0xfa, 0x99, 0xbb, 0xa1, 0x41, 0x20],
  [0xf0, 0x26, 0x14, 0x47, 0xe9, 0x49, 0x0c, 0xa8, 0xe4, 0x74, 0xce, 0xc0],
  [0x44, 0x10, 0x11, 0x58, 0x18, 0x19, 0x6f, 0x95, 0xcd, 0xd7, 0x01, 0x20],
  [0x08, 0x8f, 0xc3, 0x1d, 0xf4, 0xbf, 0xbd, 0xe2, 0xa4, 0xea, 0xfb, 0x40],
  [0xb8, 0xfe, 0xf1, 0xb6, 0x30, 0x77, 0x29, 0xfb, 0x0a, 0x07, 0x8c, 0x00],
  [0x5a, 0xfe, 0xa7, 0xac, 0xcc, 0xb7, 0x7b, 0xbc, 0x9d, 0x99, 0xa9, 0x00],
  [0x49, 0xa7, 0x01, 0x6a, 0xc6, 0x53, 0xf6, 0x5e, 0xcd, 0xc9, 0x07, 0x60],
  [0x19, 0x44, 0xd0, 0x85, 0xbe, 0x4e, 0x7d, 0xa8, 0xd6, 0xcc, 0x7d, 0x00],
  [0x25, 0x1f, 0x62, 0xad, 0xc4, 0x03, 0x2f, 0x0e, 0xe7, 0x14, 0x00, 0x20],
  [0x56, 0x47, 0x1f, 0x87, 0x02, 0xa0, 0x72, 0x1e, 0x00, 0xb1, 0x2b, 0x80],
  [0x2b, 0x8e, 0x49, 0x23, 0xf2, 0xdd, 0x51, 0xe2, 0xd5, 0x37, 0xfa, 0x00],
  [0x6b, 0x55, 0x0a, 0x40, 0xa6, 0x6f, 0x47, 0x55, 0xde, 0x95, 0xc2, 0x60],
  [0xa1, 0x8a, 0xd2, 0x8d, 0x4e, 0x27, 0xfe, 0x92, 0xa4, 0xf6, 0xc8, 0x40],
  [0x10, 0xc2, 0xe5, 0x86, 0x38, 0x8c, 0xb8, 0x2a, 0x3d, 0x80, 0x75, 0x80],
  [0xef, 0x34, 0xa4, 0x18, 0x17, 0xee, 0x02, 0x13, 0x3d, 0xb2, 0xeb, 0x00],
  [0x7e, 0x9c, 0x0c, 0x54, 0x32, 0x5a, 0x9c, 0x15, 0x83, 0x6e, 0x00, 0x00],
  [0x36, 0x93, 0xe5, 0x72, 0xd1, 0xfd, 0xe4, 0xcd, 0xf0, 0x79, 0xe8, 0x60],
  [0xbf, 0xb2, 0xce, 0xc5, 0xab, 0xe1, 0xb0, 0xc7, 0x2e, 0x07, 0xfb, 0xe0],
  [0x7e, 0xe1, 0x82, 0x30, 0xc5, 0x83, 0xcc, 0xcc, 0x57, 0xd4, 0xb0, 0x80],
  [0xa0, 0x66, 0xcb, 0x2f, 0xed, 0xaf, 0xc9, 0xf5, 0x26, 0x64, 0x12, 0x60],
  [0xbb, 0x23, 0x72, 0x5a, 0xbc, 0x47, 0xcc, 0x5f, 0x4c, 0xc4, 0xcd, 0x20],
  [0xde, 0xd9, 0xdb, 0xa3, 0xbe, 0xe4, 0x0c, 0x59, 0xb5, 0x60, 0x9b, 0x40],
  [0xd9, 0xa7, 0x01, 0x6a, 0xc6, 0x53, 0xe6, 0xde, 0xcd, 0xc9, 0x03, 0x60],
  [0x9a, 0xd4, 0x6a, 0xed, 0x5f, 0x70, 0x7f, 0x28, 0x0a, 0xb5, 0xfc, 0x40],
  [0xe5, 0x92, 0x1c, 0x77, 0x82, 0x25, 0x87, 0x31, 0x6d, 0x7d, 0x3c, 0x20],
  [0x4f, 0x14, 0xda, 0x82, 0x42, 0xa8, 0xb8, 0x6d, 0xca, 0x73, 0x35, 0x20],
  [0x8b, 0x8b, 0x50, 0x7a, 0xd4, 0x67, 0xd4, 0x44, 0x1d, 0xf7, 0x70, 0xe0],
  [0x22, 0x83, 0x1c, 0x9c, 0xf1, 0x16, 0x94, 0x67, 0xad, 0x04, 0xb6, 0x80],
  [0x21, 0x3b, 0x83, 0x8f, 0xe2, 0xae, 0x54, 0xc3, 0x8e, 0xe7, 0x18, 0x00],
  [0x5d, 0x92, 0x6b, 0x6d, 0xd7, 0x1f, 0x08, 0x51, 0x81, 0xa4, 0xe1, 0x20],
  [0x66, 0xab, 0x79, 0xd4, 0xb2, 0x9e, 0xe6, 0xe6, 0x95, 0x09, 0xe5, 0x60],
  [0x95, 0x81, 0x48, 0x68, 0x2d, 0x74, 0x8a, 0x38, 0xdd, 0x68, 0xba, 0xa0],
  [0xb8, 0xce, 0x02, 0x0c, 0xf0, 0x69, 0xc3, 0x2a, 0x72, 0x3a, 0xb1, 0x40],
  [0xf4, 0x33, 0x1d, 0x6d, 0x46, 0x16, 0x07, 0xe9, 0x57, 0x52, 0x74, 0x60],
  [0x6d, 0xa2, 0x3b, 0xa4, 0x24, 0xb9, 0x59, 0x61, 0x33, 0xcf, 0x9c, 0x80],
  [0xa6, 0x36, 0xbc, 0xbc, 0x7b, 0x30, 0xc5, 0xfb, 0xea, 0xe6, 0x7f, 0xe0],
  [0x5c, 0xb0, 0xd8, 0x6a, 0x07, 0xdf, 0x65, 0x4a, 0x90, 0x89, 0xa2, 0x00],
  [0xf1, 0x1f, 0x10, 0x68, 0x48, 0x78, 0x0f, 0xc9, 0xec, 0xdd, 0x80, 0xa0],
  [0x1f, 0xbb, 0x53, 0x64, 0xfb, 0x8d, 0x2c, 0x9d, 0x73, 0x0d, 0x5b, 0xa0],
  [0xfc, 0xb8, 0x6b, 0xc7, 0x0a, 0x50, 0xc9, 0xd0, 0x2a, 0x5d, 0x03, 0x40],
  [0xa5, 0x34, 0x43, 0x30, 0x29, 0xea, 0xc1, 0x5f, 0x32, 0x2e, 0x34, 0xc0],
  [0xc9, 0x89, 0xd9, 0xc7, 0xc3, 0xd3, 0xb8, 0xc5, 0x5d, 0x75, 0x13, 0x00],
  [0x7b, 0xb3, 0x8b, 0x2f, 0x01, 0x86, 0xd4, 0x66, 0x43, 0xae, 0x96, 0x20],
  [0x26, 0x44, 0xeb, 0xad, 0xeb, 0x44, 0xb9, 0x46, 0x7d, 0x1f, 0x42, 0xc0],
  [0x60, 0x8c, 0xc8, 0x57, 0x59, 0x4b, 0xfb, 0xb5, 0x5d, 0x69, 0x60, 0x00],
];

// Table de contrôle de parité LDPC(174,91) — 83 lignes, chaque ligne indique
// les indices (origine 1, 0 = case vide) des bits du mot de code de 174 bits
// qui doivent s'annuler par XOR (une équation de parité).
// Source : kFTX_LDPC_Nm dans kgoba/ft8_lib ft8/constants.c (MIT).
const FT8_LDPC_NM = [
  [4, 31, 59, 91, 92, 96, 153], [5, 32, 60, 93, 115, 146, 0], [6, 24, 61, 94, 122, 151, 0],
  [7, 33, 62, 95, 96, 143, 0], [8, 25, 63, 83, 93, 96, 148], [6, 32, 64, 97, 126, 138, 0],
  [5, 34, 65, 78, 98, 107, 154], [9, 35, 66, 99, 139, 146, 0], [10, 36, 67, 100, 107, 126, 0],
  [11, 37, 67, 87, 101, 139, 158], [12, 38, 68, 102, 105, 155, 0], [13, 39, 69, 103, 149, 162, 0],
  [8, 40, 70, 82, 104, 114, 145], [14, 41, 71, 88, 102, 123, 156], [15, 42, 59, 106, 123, 159, 0],
  [1, 33, 72, 106, 107, 157, 0], [16, 43, 73, 108, 141, 160, 0], [17, 37, 74, 81, 109, 131, 154],
  [11, 44, 75, 110, 121, 166, 0], [45, 55, 64, 111, 130, 161, 173], [8, 46, 71, 112, 119, 166, 0],
  [18, 36, 76, 89, 113, 114, 143], [19, 38, 77, 104, 116, 163, 0], [20, 47, 70, 92, 138, 165, 0],
  [2, 48, 74, 113, 128, 160, 0], [21, 45, 78, 83, 117, 121, 151], [22, 47, 58, 118, 127, 164, 0],
  [16, 39, 62, 112, 134, 158, 0], [23, 43, 79, 120, 131, 145, 0], [19, 35, 59, 73, 110, 125, 161],
  [20, 36, 63, 94, 136, 161, 0], [14, 31, 79, 98, 132, 164, 0], [3, 44, 80, 124, 127, 169, 0],
  [19, 46, 81, 117, 135, 167, 0], [7, 49, 58, 90, 100, 105, 168], [12, 50, 61, 118, 119, 144, 0],
  [13, 51, 64, 114, 118, 157, 0], [24, 52, 76, 129, 148, 149, 0], [25, 53, 69, 90, 101, 130, 156],
  [20, 46, 65, 80, 120, 140, 170], [21, 54, 77, 100, 140, 171, 0], [35, 82, 133, 142, 171, 174, 0],
  [14, 30, 83, 113, 125, 170, 0], [4, 29, 68, 120, 134, 173, 0], [1, 4, 52, 57, 86, 136, 152],
  [26, 51, 56, 91, 122, 137, 168], [52, 84, 110, 115, 145, 168, 0], [7, 50, 81, 99, 132, 173, 0],
  [23, 55, 67, 95, 172, 174, 0], [26, 41, 77, 109, 141, 148, 0], [2, 27, 41, 61, 62, 115, 133],
  [27, 40, 56, 124, 125, 126, 0], [18, 49, 55, 124, 141, 167, 0], [6, 33, 85, 108, 116, 156, 0],
  [28, 48, 70, 85, 105, 129, 158], [9, 54, 63, 131, 147, 155, 0], [22, 53, 68, 109, 121, 174, 0],
  [3, 13, 48, 78, 95, 123, 0], [31, 69, 133, 150, 155, 169, 0], [12, 43, 66, 89, 97, 135, 159],
  [5, 39, 75, 102, 136, 167, 0], [2, 54, 86, 101, 135, 164, 0], [15, 56, 87, 108, 119, 171, 0],
  [10, 44, 82, 91, 111, 144, 149], [23, 34, 71, 94, 127, 153, 0], [11, 49, 88, 92, 142, 157, 0],
  [29, 34, 87, 97, 147, 162, 0], [30, 50, 60, 86, 137, 142, 162], [10, 53, 66, 84, 112, 128, 165],
  [22, 57, 85, 93, 140, 159, 0], [28, 32, 72, 103, 132, 166, 0], [28, 29, 84, 88, 117, 143, 150],
  [1, 26, 45, 80, 128, 147, 0], [17, 27, 89, 103, 116, 153, 0], [51, 57, 98, 163, 165, 172, 0],
  [21, 37, 73, 138, 152, 169, 0], [16, 47, 76, 130, 137, 154, 0], [3, 24, 30, 72, 104, 139, 0],
  [9, 40, 90, 106, 134, 151, 0], [15, 58, 60, 74, 111, 150, 163], [18, 42, 79, 144, 146, 152, 0],
  [25, 38, 65, 99, 122, 160, 0], [17, 42, 75, 129, 170, 172, 0],
];

// Correspondance inverse : pour chaque bit du mot de code (174, origine 1),
// les 3 équations de parité (indices dans FT8_LDPC_NM, origine 1) qui le
// concernent. Source : kFTX_LDPC_Mn (kgoba/ft8_lib ft8/constants.c, MIT).
const FT8_LDPC_MN = [
  [16, 45, 73], [25, 51, 62], [33, 58, 78], [1, 44, 45], [2, 7, 61], [3, 6, 54], [4, 35, 48],
  [5, 13, 21], [8, 56, 79], [9, 64, 69], [10, 19, 66], [11, 36, 60], [12, 37, 58], [14, 32, 43],
  [15, 63, 80], [17, 28, 77], [18, 74, 83], [22, 53, 81], [23, 30, 34], [24, 31, 40], [26, 41, 76],
  [27, 57, 70], [29, 49, 65], [3, 38, 78], [5, 39, 82], [46, 50, 73], [51, 52, 74], [55, 71, 72],
  [44, 67, 72], [43, 68, 78], [1, 32, 59], [2, 6, 71], [4, 16, 54], [7, 65, 67], [8, 30, 42],
  [9, 22, 31], [10, 18, 76], [11, 23, 82], [12, 28, 61], [13, 52, 79], [14, 50, 51], [15, 81, 83],
  [17, 29, 60], [19, 33, 64], [20, 26, 73], [21, 34, 40], [24, 27, 77], [25, 55, 58], [35, 53, 66],
  [36, 48, 68], [37, 46, 75], [38, 45, 47], [39, 57, 69], [41, 56, 62], [20, 49, 53], [46, 52, 63],
  [45, 70, 75], [27, 35, 80], [1, 15, 30], [2, 68, 80], [3, 36, 51], [4, 28, 51], [5, 31, 56],
  [6, 20, 37], [7, 40, 82], [8, 60, 69], [9, 10, 49], [11, 44, 57], [12, 39, 59], [13, 24, 55],
  [14, 21, 65], [16, 71, 78], [17, 30, 76], [18, 25, 80], [19, 61, 83], [22, 38, 77], [23, 41, 50],
  [7, 26, 58], [29, 32, 81], [33, 40, 73], [18, 34, 48], [13, 42, 64], [5, 26, 43], [47, 69, 72],
  [54, 55, 70], [45, 62, 68], [10, 63, 67], [14, 66, 72], [22, 60, 74], [35, 39, 79], [1, 46, 64],
  [1, 24, 66], [2, 5, 70], [3, 31, 65], [4, 49, 58], [1, 4, 5], [6, 60, 67], [7, 32, 75],
  [8, 48, 82], [9, 35, 41], [10, 39, 62], [11, 14, 61], [12, 71, 74], [13, 23, 78], [11, 35, 55],
  [15, 16, 79], [7, 9, 16], [17, 54, 63], [18, 50, 57], [19, 30, 47], [20, 64, 80], [21, 28, 69],
  [22, 25, 43], [13, 22, 37], [2, 47, 51], [23, 54, 74], [26, 34, 72], [27, 36, 37], [21, 36, 63],
  [29, 40, 44], [19, 26, 57], [3, 46, 82], [14, 15, 58], [33, 52, 53], [30, 43, 52], [6, 9, 52],
  [27, 33, 65], [25, 69, 73], [38, 55, 83], [20, 39, 77], [18, 29, 56], [32, 48, 71], [42, 51, 59],
  [28, 44, 79], [34, 60, 62], [31, 45, 61], [46, 68, 77], [6, 24, 76], [8, 10, 78], [40, 41, 70],
  [17, 50, 53], [42, 66, 68], [4, 22, 72], [36, 64, 81], [13, 29, 47], [2, 8, 81], [56, 67, 73],
  [5, 38, 50], [12, 38, 64], [59, 72, 80], [3, 26, 79], [45, 76, 81], [1, 65, 74], [7, 18, 77],
  [11, 56, 59], [14, 39, 54], [16, 37, 66], [10, 28, 55], [15, 60, 70], [17, 25, 82], [20, 30, 31],
  [12, 67, 68], [23, 75, 80], [27, 32, 62], [24, 69, 75], [19, 21, 71], [34, 53, 61], [35, 46, 47],
  [33, 59, 76], [40, 43, 83], [41, 42, 63], [49, 75, 83], [20, 44, 48], [42, 49, 57],
];

// Nombre de termes réellement utilisés sur chacune des 83 lignes de
// FT8_LDPC_NM (6 ou 7 — le 7e élément vaut 0/inutilisé quand la ligne n'a que
// 6 termes). Source : kFTX_LDPC_Num_rows (kgoba/ft8_lib ft8/constants.c, MIT).
const FT8_LDPC_NUM_ROWS = [
  7, 6, 6, 6, 7, 6, 7, 6, 6, 7, 6, 6, 7, 7, 6, 6,
  6, 7, 6, 7, 6, 7, 6, 6, 6, 7, 6, 6, 6, 7, 6, 6,
  6, 6, 7, 6, 6, 6, 7, 7, 6, 6, 6, 6, 7, 7, 6, 6,
  6, 6, 7, 6, 6, 6, 7, 6, 6, 6, 6, 7, 6, 6, 6, 7,
  6, 6, 6, 7, 7, 6, 6, 7, 6, 6, 6, 6, 6, 6, 6, 7,
  6, 6, 6,
];

// ─── CRC-14 (ftx_compute_crc de ft8/crc.c, division modulo-2 bit à bit) ──────
function ft8Crc(bytes, numBits){
  const TOPBIT = 1 << (FT8_CRC_WIDTH - 1);
  let remainder = 0, idxByte = 0;
  for(let idxBit = 0; idxBit < numBits; idxBit++){
    if(idxBit % 8 === 0){
      remainder ^= (bytes[idxByte] << (FT8_CRC_WIDTH - 8));
      idxByte++;
    }
    if(remainder & TOPBIT) remainder = ((remainder << 1) ^ FT8_CRC_POLYNOMIAL) & 0xFFFF;
    else remainder = (remainder << 1) & 0xFFFF;
  }
  return remainder & ((TOPBIT << 1) - 1);
}

// payload77 : Uint8Array(10), 77 bits utiles (les 3 derniers bits de l'octet
// 9 et l'octet suivant ne sont pas utilisés par le payload lui-même).
// Retourne a91 : Uint8Array(12), 91 bits (77 payload + 14 CRC).
function ft8AddCrc(payload77){
  const a91 = new Uint8Array(12);
  for(let i = 0; i < 10; i++) a91[i] = payload77[i];
  a91[9] &= 0xF8;   // efface 3 bits après le payload (77..79) pour arriver à 82 bits
  a91[10] = 0;
  const checksum = ft8Crc(a91, 96 - 14); // CRC sur 82 bits (77 + 5 zéros)
  a91[9] |= (checksum >> 11) & 0xFF;
  a91[10] = (checksum >> 3) & 0xFF;
  a91[11] = (checksum << 5) & 0xFF;
  return a91;
}

function ft8ExtractCrc(a91){
  return ((a91[9] & 0x07) << 11) | (a91[10] << 3) | (a91[11] >> 5);
}

// ─── Empaquetage/dépaquetage LDPC(174,91) ────────────────────────────────────
// bits91 : tableau de 91 valeurs 0/1. Retourne un tableau de 174 valeurs 0/1
// (91 bits utiles suivis de 83 bits de parité).
function ft8LdpcEncode(bits91){
  const codeword = bits91.slice(0, 91);
  for(let j = 0; j < FTX_LDPC_M; j++){
    let parity = 0;
    const row = FT8_LDPC_GENERATOR[j];
    for(let i = 0; i < FTX_LDPC_K; i++){
      const byte = row[i >> 3];
      const bit = (byte >> (7 - (i & 7))) & 1;
      if(bit) parity ^= bits91[i];
    }
    codeword.push(parity);
  }
  return codeword;
}

// Nombre d'équations de parité NON satisfaites (0 = mot de code valide).
function ft8LdpcCheckErrors(codeword174){
  let errors = 0;
  for(let m = 0; m < FTX_LDPC_M; m++){
    let x = 0;
    const numRows = FT8_LDPC_NUM_ROWS[m];
    const row = FT8_LDPC_NM[m];
    for(let i = 0; i < numRows; i++) x ^= codeword174[row[i] - 1];
    if(x !== 0) errors++;
  }
  return errors;
}

// Approximations rationnelles de tanh/atanh (mêmes fractions que ft8_lib,
// fast_tanh/fast_atanh de ft8/ldpc.c) — évitent Math.tanh en boucle serrée
// tout en restant fidèles au comportement numérique de référence.
function ft8FastTanh(x){
  if(x < -4.97) return -1.0;
  if(x > 4.97) return 1.0;
  const x2 = x * x;
  const a = x * (945.0 + x2 * (105.0 + x2));
  const b = 945.0 + x2 * (420.0 + x2 * 15.0);
  return a / b;
}
function ft8FastAtanh(x){
  const x2 = x * x;
  const a = x * (945.0 + x2 * (-735.0 + x2 * 64.0));
  const b = (945.0 + x2 * (-1050.0 + x2 * 225.0));
  return a / b;
}

// Décodage par propagation de croyance (portage de bp_decode, ft8/ldpc.c).
// llr174 : 174 vraisemblances log — CONVENTION (alignée sur le sens du test
// `(l>0)?1:0` du code source, pas sur le commentaire d'en-tête du fichier
// d'origine qui prête à confusion) : llr > 0 pousse le bit décodé vers 1,
// llr < 0 pousse vers 0. maxIters : nombre d'itérations max (20 dans ft8_lib).
// Retourne {bits: [174 x 0/1], errors: nombre d'équations de parité en échec
// sur le MEILLEUR résultat rencontré (0 = décodage réussi)}.
function ft8BpDecode(llr174, maxIters){
  const N = FTX_LDPC_N, M = FTX_LDPC_M;
  const tov = [];
  for(let n = 0; n < N; n++) tov.push([0, 0, 0]);
  const toc = [];
  for(let m = 0; m < M; m++) toc.push(new Array(7).fill(0));

  let minErrors = M;
  let bestPlain = null;
  const plain = new Array(N).fill(0);

  for(let iter = 0; iter < maxIters; iter++){
    let plainSum = 0;
    for(let n = 0; n < N; n++){
      const v = (llr174[n] + tov[n][0] + tov[n][1] + tov[n][2]) > 0 ? 1 : 0;
      plain[n] = v;
      plainSum += v;
    }
    if(plainSum === 0) break; // convergé vers tout-zéro (interdit par construction)

    const errors = ft8LdpcCheckErrors(plain);
    if(errors < minErrors){
      minErrors = errors;
      bestPlain = plain.slice();
      if(errors === 0) break;
    }

    // Messages bits -> nœuds de contrôle
    for(let m = 0; m < M; m++){
      const numRows = FT8_LDPC_NUM_ROWS[m];
      const rowNm = FT8_LDPC_NM[m];
      for(let nIdx = 0; nIdx < numRows; nIdx++){
        const n = rowNm[nIdx] - 1;
        let Tnm = llr174[n];
        const mn = FT8_LDPC_MN[n];
        for(let mIdx = 0; mIdx < 3; mIdx++){
          if((mn[mIdx] - 1) !== m) Tnm += tov[n][mIdx];
        }
        toc[m][nIdx] = ft8FastTanh(-Tnm / 2);
      }
    }

    // Messages nœuds de contrôle -> bits
    for(let n = 0; n < N; n++){
      const mn = FT8_LDPC_MN[n];
      for(let mIdx = 0; mIdx < 3; mIdx++){
        const m = mn[mIdx] - 1;
        let Tmn = 1.0;
        const numRows = FT8_LDPC_NUM_ROWS[m];
        const rowNm = FT8_LDPC_NM[m];
        for(let nIdx = 0; nIdx < numRows; nIdx++){
          if((rowNm[nIdx] - 1) !== n) Tmn *= toc[m][nIdx];
        }
        tov[n][mIdx] = -2 * ft8FastAtanh(Tmn);
      }
    }
  }

  return { bits: bestPlain || plain, errors: minErrors };
}

// ─── Symboles <-> bits (Gray, motif Costas, structure S D1 S D2 S) ───────────
// codeword174 (0/1) -> 79 tons (0..7), motif complet prêt à moduler.
function ft8CodewordToSymbols(codeword174){
  const symbols = new Array(FT8_NN);
  for(let i = 0; i < FT8_LENGTH_SYNC; i++) symbols[i] = FT8_COSTAS_PATTERN[i];
  for(let i = 0; i < FT8_LENGTH_SYNC; i++) symbols[FT8_SYNC_OFFSET + i] = FT8_COSTAS_PATTERN[i];
  for(let i = 0; i < FT8_LENGTH_SYNC; i++) symbols[2 * FT8_SYNC_OFFSET + i] = FT8_COSTAS_PATTERN[i];

  let bitIdx = 0;
  function writeDataBlock(startSym, count){
    for(let s = 0; s < count; s++){
      const b0 = codeword174[bitIdx], b1 = codeword174[bitIdx + 1], b2 = codeword174[bitIdx + 2];
      bitIdx += 3;
      const v = (b0 << 2) | (b1 << 1) | b2;
      symbols[startSym + s] = FT8_GRAY_MAP[v];
    }
  }
  writeDataBlock(FT8_LENGTH_SYNC, 29);                   // D1 : symboles 7..35
  writeDataBlock(FT8_SYNC_OFFSET + FT8_LENGTH_SYNC, 29); // D2 : symboles 43..71
  return symbols;
}

// 79 tons -> 174 bits codés (ignore les 3 groupes de synchro). Inverse exact
// de ft8CodewordToSymbols côté données — utilisé une fois la synchro trouvée
// et les tons de données extraits proprement (voir logx_ft8_dsp.js).
function ft8SymbolsToCodeword(symbols79){
  const bits = new Array(174);
  let bitIdx = 0;
  function readDataBlock(startSym, count){
    for(let s = 0; s < count; s++){
      const tone = symbols79[startSym + s];
      const v = FT8_GRAY_MAP_INV[tone];
      bits[bitIdx++] = (v >> 2) & 1;
      bits[bitIdx++] = (v >> 1) & 1;
      bits[bitIdx++] = v & 1;
    }
  }
  readDataBlock(FT8_LENGTH_SYNC, 29);
  readDataBlock(FT8_SYNC_OFFSET + FT8_LENGTH_SYNC, 29);
  return bits;
}

// ─── Empaquetage/dépaquetage des messages (types 1/2 standard, 4 non-standard,
// 0.0 texte libre) — portage de ft8/message.c (ftx_message_encode_std/
// encode_nonstd/encode_free et leurs inverses). Voir ft8/text.h pour les
// tables de caractères et NTOKENS/MAX22/MAXGRID4 pour les seuils d'encodage.
const FT8_NTOKENS = 2063592;
const FT8_MAX22 = 4194304;
const FT8_MAXGRID4 = 32400;

function ft8IsDigit(c){ return c >= '0' && c <= '9'; }
function ft8IsLetter(c){ return c >= 'A' && c <= 'Z'; }
function ft8IsSpace(c){ return c === ' ' || c === undefined || c === ''; }
function ft8InRange(c, lo, hi){ return c >= lo && c <= hi; }
function ft8TrimTrailingSpaces(s){ return s.replace(/\s+$/, ''); }

// Table de hachage indicatif <-> code (persiste le temps de la page ; se
// re-remplit à chaque indicatif entendu, comme WSJT-X — un hash jamais
// rencontré ne peut structurellement pas être résolu, ce n'est pas un bug).
function ft8CreateHashTable(){
  return { byN22: new Map() };
}
function ft8HashSaveCallsign(table, callsign){
  // n58 doit être calculé en précision arbitraire (BigInt) : 38^11 dépasse
  // largement 2^53, la limite des entiers JS "safe" en Number classique.
  let n58 = 0n;
  const src = (callsign[0] === '<') ? callsign.slice(1) : callsign;
  let i = 0;
  for(; i < 11 && i < src.length; i++){
    const j = nchar(src[i], FT8_CHAR_TABLE_ALPHANUM_SPACE_SLASH);
    if(j < 0) break;
    n58 = (n58 * 38n) + BigInt(j);
  }
  for(; i < 11; i++) n58 = n58 * 38n; // complète avec des espaces (index 0)
  const MASK64 = 0xFFFFFFFFFFFFFFFFn;
  const product = (47055833459n * n58) & MASK64; // reproduit le débordement uint64_t du C
  const n22 = Number((product >> 42n) & 0x3FFFFFn);
  table.byN22.set(n22, callsign);
  return n22;
}
function ft8HashLookup22(table, n22){
  return table.byN22.get(n22) || null;
}

// pack_basecall : indicatif standard (préfixe 1-2 car., 1 chiffre de zone,
// suffixe 1-3 lettres) -> entier, ou -1 si non standard.
function ft8PackBasecall(callsign){
  const length = callsign.length;
  if(length <= 2) return -1;
  let c6 = '      '.split('');

  if(callsign.startsWith('3DA0') && length > 4 && length <= 7){
    c6 = ('3D0' + callsign.slice(4)).padEnd(6, ' ').split('');
  } else if(callsign.startsWith('3X') && ft8IsLetter(callsign[2]) && length <= 7){
    c6 = ('Q' + callsign.slice(2)).padEnd(6, ' ').split('');
  } else if(ft8IsDigit(callsign[2]) && length <= 6){
    c6 = callsign.padEnd(6, ' ').split('');
  } else if(ft8IsDigit(callsign[1]) && length <= 5){
    c6 = (' ' + callsign).padEnd(6, ' ').split('');
  } else {
    return -1;
  }

  const i0 = nchar(c6[0], FT8_CHAR_TABLE_ALPHANUM_SPACE);
  const i1 = nchar(c6[1], FT8_CHAR_TABLE_ALPHANUM);
  const i2 = nchar(c6[2], FT8_CHAR_TABLE_NUMERIC);
  const i3 = nchar(c6[3], FT8_CHAR_TABLE_LETTERS_SPACE);
  const i4 = nchar(c6[4], FT8_CHAR_TABLE_LETTERS_SPACE);
  const i5 = nchar(c6[5], FT8_CHAR_TABLE_LETTERS_SPACE);
  if(i0 < 0 || i1 < 0 || i2 < 0 || i3 < 0 || i4 < 0 || i5 < 0) return -1;

  let n = i0;
  n = n * 36 + i1;
  n = n * 10 + i2;
  n = n * 27 + i3;
  n = n * 27 + i4;
  n = n * 27 + i5;
  return n;
}

// Détecte "CQ nnn" (3 chiffres) ou "CQ a[bcd]" (1-4 lettres) après "CQ ".
// Retourne {v} si trouvé, sinon null.
function ft8ParseCqModifier(rest){
  let nnum = 0, nlet = 0, m = 0;
  for(let i = 0; i < rest.length && i < 5; i++){
    const c = rest[i];
    if(ft8IsSpace(c) || c === '') break;
    if(ft8IsDigit(c)) nnum++;
    else if(ft8IsLetter(c)){ nlet++; m = 27 * m + (c.charCodeAt(0) - 65 + 1); }
    else return null;
  }
  if(nnum === 3 && nlet === 0) return parseInt(rest.slice(0, 3), 10);
  if(nnum === 0 && nlet >= 1 && nlet <= 4) return 1000 + m;
  return null;
}

// pack28 : jeton spécial / indicatif standard / hash 22 bits -> {n28, ip}
function ft8Pack28(callsign, hashTable){
  if(callsign === 'DE') return { n28: 0, ip: 0 };
  if(callsign === 'QRZ') return { n28: 1, ip: 0 };
  if(callsign === 'CQ') return { n28: 2, ip: 0 };

  if(callsign.startsWith('CQ ') && callsign.length < 8){
    const v = ft8ParseCqModifier(callsign.slice(3));
    if(v === null) return null;
    return { n28: 3 + v, ip: 0 };
  }

  let ip = 0, base = callsign;
  if(callsign.endsWith('/P') || callsign.endsWith('/R')){
    ip = 1;
    base = callsign.slice(0, -2);
  }

  const n28std = ft8PackBasecall(base);
  if(n28std >= 0){
    if(hashTable) ft8HashSaveCallsign(hashTable, callsign);
    return { n28: FT8_NTOKENS + FT8_MAX22 + n28std, ip };
  }

  const length = callsign.length;
  if(length >= 3 && length <= 11){
    const n22 = hashTable ? ft8HashSaveCallsign(hashTable, callsign) : 0;
    return { n28: FT8_NTOKENS + n22, ip: 0 };
  }
  return null;
}

// unpack28 : inverse de pack28 -> texte indicatif (ou jeton)
function ft8Unpack28(n28, ip, i3, hashTable){
  if(n28 < FT8_NTOKENS){
    if(n28 === 0) return 'DE';
    if(n28 === 1) return 'QRZ';
    if(n28 === 2) return 'CQ';
    if(n28 <= 1002) return 'CQ ' + String(n28 - 3).padStart(3, '0');
    if(n28 <= 532443){
      let n = n28 - 1003;
      const aaaa = [0, 0, 0, 0];
      for(let i = 3; i >= 0; i--){ aaaa[i] = charn(n % 27, FT8_CHAR_TABLE_LETTERS_SPACE); n = Math.floor(n / 27); }
      return 'CQ ' + ft8TrimTrailingSpaces(aaaa.join('')).replace(/^\s+/, '');
    }
    return null;
  }

  const n = n28 - FT8_NTOKENS;
  if(n < FT8_MAX22){
    const found = hashTable ? ft8HashLookup22(hashTable, n) : null;
    return found ? ('<' + found + '>') : '<...>';
  }

  let m = n - FT8_MAX22;
  const c = [0, 0, 0, 0, 0, 0];
  c[5] = charn(m % 27, FT8_CHAR_TABLE_LETTERS_SPACE); m = Math.floor(m / 27);
  c[4] = charn(m % 27, FT8_CHAR_TABLE_LETTERS_SPACE); m = Math.floor(m / 27);
  c[3] = charn(m % 27, FT8_CHAR_TABLE_LETTERS_SPACE); m = Math.floor(m / 27);
  c[2] = charn(m % 10, FT8_CHAR_TABLE_NUMERIC); m = Math.floor(m / 10);
  c[1] = charn(m % 36, FT8_CHAR_TABLE_ALPHANUM); m = Math.floor(m / 36);
  c[0] = charn(m % 37, FT8_CHAR_TABLE_ALPHANUM_SPACE);
  let callsign = c.join('');

  let result;
  if(callsign.startsWith('3D0') && callsign[3] !== ' '){
    result = '3DA0' + ft8TrimTrailingSpaces(callsign.slice(3).replace(/^\s+/, ''));
  } else if(callsign[0] === 'Q' && ft8IsLetter(callsign[1])){
    result = '3X' + ft8TrimTrailingSpaces(callsign.slice(1).replace(/^\s+/, ''));
  } else {
    result = ft8TrimTrailingSpaces(callsign.replace(/^\s+/, ''));
  }
  if(result.length < 3) return null;

  if(ip !== 0){
    if(i3 === 1) result += '/R';
    else if(i3 === 2) result += '/P';
    else return null;
  }
  if(hashTable) ft8HashSaveCallsign(hashTable, result);
  return result;
}

// packgrid : locator Maidenhead 4 car. / report / RRR / RR73 / 73 -> 16 bits
// (retourne {value, ir} ; ir=1 si le champ commence par "R " — accusé de
// réception d'un report avant de préciser le sien).
function ft8PackGrid(extra){
  if(!extra) return { value: FT8_MAXGRID4 + 1, ir: 0 };
  if(extra === 'RRR') return { value: FT8_MAXGRID4 + 2, ir: 0 };
  if(extra === 'RR73') return { value: FT8_MAXGRID4 + 3, ir: 0 };
  if(extra === '73') return { value: FT8_MAXGRID4 + 4, ir: 0 };

  if(extra.length === 4 && ft8InRange(extra[0], 'A', 'R') && ft8InRange(extra[1], 'A', 'R')
     && ft8IsDigit(extra[2]) && ft8IsDigit(extra[3])){
    let v = extra.charCodeAt(0) - 65;
    v = v * 18 + (extra.charCodeAt(1) - 65);
    v = v * 10 + (extra.charCodeAt(2) - 48);
    v = v * 10 + (extra.charCodeAt(3) - 48);
    return { value: v, ir: 0 };
  }

  const withR = extra[0] === 'R';
  const rptStr = withR ? extra.slice(1) : extra;
  const dd = ft8DdToInt(rptStr);
  if(dd === null) return { value: FT8_MAXGRID4 + 1, ir: 0 };
  return { value: FT8_MAXGRID4 + 35 + dd, ir: withR ? 1 : 0 };
}

// unpackgrid : inverse de packgrid
function ft8UnpackGrid(value, ir){
  if(value <= FT8_MAXGRID4){
    let n = value;
    const d3 = n % 10; n = Math.floor(n / 10);
    const d2 = n % 10; n = Math.floor(n / 10);
    const l1 = n % 18; n = Math.floor(n / 18);
    const l0 = n % 18;
    const grid = String.fromCharCode(65 + l0) + String.fromCharCode(65 + l1) + d2 + d3;
    return (ir > 0) ? ('R ' + grid) : grid;
  }
  const irpt = value - FT8_MAXGRID4;
  if(irpt === 1) return '';
  if(irpt === 2) return 'RRR';
  if(irpt === 3) return 'RR73';
  if(irpt === 4) return '73';
  const dd = irpt - 35;
  return (ir > 0 ? 'R' : '') + ft8IntToDd(dd);
}

// "+dd"/"-dd" (2 ou 3 chiffres) -> entier signé. null si pas un report valide.
function ft8DdToInt(str){
  if(!str) return null;
  let sign = 1, idx = 0;
  if(str[0] === '-'){ sign = -1; idx = 1; }
  else if(str[0] === '+'){ sign = 1; idx = 1; }
  const digits = str.slice(idx);
  if(!/^\d{1,3}$/.test(digits)) return null;
  return sign * parseInt(digits, 10);
}
function ft8IntToDd(value){
  const sign = value < 0 ? '-' : '+';
  return sign + String(Math.abs(value)).padStart(2, '0');
}

// ─── Message type 1/2 (standard) : indicatif+indicatif+report/grid ──────────
// Retourne payload77 (Uint8Array(10)) ou null si l'un des indicatifs ne peut
// pas être empaqueté.
function ft8EncodeStdMessage(callTo, callDe, extra, hashTable){
  const a = ft8Pack28(callTo, hashTable);
  const b = ft8Pack28(callDe, hashTable);
  if(!a || !b) return null;

  let i3 = 1;
  if(callTo.endsWith('/P') || callDe.endsWith('/P')){
    i3 = 2;
    if(callTo.endsWith('/R') || callDe.endsWith('/R')) return null; // suffixe incompatible
  }

  const grid = ft8PackGrid(extra);
  let n29a = (a.n28 << 1) | a.ip;
  let n29b = (b.n28 << 1) | b.ip;
  if(callTo.endsWith('/R')) n29a |= 1;
  else if(callTo.endsWith('/P')){ n29a |= 1; i3 = 2; }

  const igrid4 = grid.value | (grid.ir ? 0x8000 : 0);
  const payload = new Uint8Array(10);
  payload[0] = (n29a >>> 21) & 0xFF;
  payload[1] = (n29a >>> 13) & 0xFF;
  payload[2] = (n29a >>> 5) & 0xFF;
  payload[3] = ((n29a << 3) & 0xFF) | ((n29b >>> 26) & 0x07);
  payload[4] = (n29b >>> 18) & 0xFF;
  payload[5] = (n29b >>> 10) & 0xFF;
  payload[6] = (n29b >>> 2) & 0xFF;
  payload[7] = ((n29b << 6) & 0xFF) | ((igrid4 >>> 10) & 0x3F);
  payload[8] = (igrid4 >>> 2) & 0xFF;
  payload[9] = ((igrid4 << 6) & 0xFF) | (i3 << 3);
  return payload;
}

function ft8DecodeStdMessage(payload77, hashTable){
  let n29a = (payload77[0] << 21) | (payload77[1] << 13) | (payload77[2] << 5) | (payload77[3] >>> 3);
  let n29b = ((payload77[3] & 0x07) << 26) | (payload77[4] << 18) | (payload77[5] << 10)
             | (payload77[6] << 2) | (payload77[7] >>> 6);
  n29a = n29a >>> 0; n29b = n29b >>> 0;
  const ir = (payload77[7] & 0x20) >>> 5;
  let igrid4 = ((payload77[7] & 0x1F) << 10) | (payload77[8] << 2) | (payload77[9] >>> 6);
  const i3 = (payload77[9] >>> 3) & 0x07;

  const callTo = ft8Unpack28(n29a >>> 1, n29a & 1, i3, hashTable);
  const callDe = ft8Unpack28(n29b >>> 1, n29b & 1, i3, hashTable);
  if(callTo === null || callDe === null) return null;
  const extra = ft8UnpackGrid(igrid4, ir);
  return { callTo, callDe, extra, i3 };
}

// ─── Message type 0.0 : texte libre (jusqu'à 13 caractères, base 42) ────────
function ft8EncodeFreeText(text){
  if(text.length > 13) return null;
  const b71 = new Array(9).fill(0);
  for(let idx = 0; idx < 13; idx++){
    const c = idx < text.length ? text[idx] : ' ';
    const cid = nchar(c, FT8_CHAR_TABLE_FULL);
    if(cid < 0) return null;
    let rem = cid;
    for(let i = 8; i >= 0; i--){
      rem += b71[i] * 42;
      b71[i] = rem & 0xFF;
      rem = rem >>> 8;
    }
  }
  // Décale de 1 bit vers la gauche pour aligner à droite dans les 9 octets
  // (ftx_message_encode_telemetry), puis i3.n3 = 0.0 (octet 9 = 0).
  const payload = new Uint8Array(10);
  let carry = 0;
  for(let i = 8; i >= 0; i--){
    payload[i] = ((b71[i] << 1) | (carry >>> 7)) & 0xFF;
    carry = b71[i] & 0x80;
  }
  payload[9] = 0;
  return payload;
}

function ft8DecodeFreeText(payload77){
  const b71 = new Array(9).fill(0);
  let carry = 0;
  for(let i = 0; i < 9; i++){
    b71[i] = ((carry << 7) | (payload77[i] >>> 1)) & 0xFF;
    carry = payload77[i] & 0x01;
  }
  const chars = new Array(13);
  for(let idx = 12; idx >= 0; idx--){
    let rem = 0;
    for(let i = 0; i < 9; i++){
      rem = (rem << 8) | b71[i];
      b71[i] = Math.floor(rem / 42);
      rem = rem % 42;
    }
    chars[idx] = charn(rem, FT8_CHAR_TABLE_FULL);
  }
  return ft8TrimTrailingSpaces(chars.join('').replace(/^\s+/, ''));
}

// ─── API haut niveau : texte <-> 79 symboles ─────────────────────────────────
// Détermine automatiquement le type (standard "TO DE EXTRA" / texte libre en
// repli), encode, ajoute le CRC, encode LDPC, mappe en symboles.
function ft8EncodeMessage(text, hashTable){
  const parts = text.trim().split(/\s+/);
  let payload = null;
  if(parts.length >= 2 && parts.length <= 3){
    const [callTo, callDe, extra] = parts;
    payload = ft8EncodeStdMessage(callTo, callDe, extra || '', hashTable);
  }
  if(!payload) payload = ft8EncodeFreeText(text.trim().toUpperCase());
  if(!payload) return null;

  const bits77 = [];
  for(let i = 0; i < 77; i++) bits77.push((payload[i >> 3] >> (7 - (i & 7))) & 1);
  const a91 = ft8AddCrc(payload);
  const bits91 = [];
  for(let i = 0; i < 91; i++) bits91.push((a91[i >> 3] >> (7 - (i & 7))) & 1);
  const codeword174 = ft8LdpcEncode(bits91);
  return { payload, symbols: ft8CodewordToSymbols(codeword174) };
}

// symbols79 : 79 tons entiers 0..7 (déjà synchronisés — la recherche de
// synchro Costas est côté DSP). Retourne le texte décodé, ou null si le CRC
// ou le LDPC échouent (signal trop faible / mauvaise synchro).
function ft8DecodeSymbols(symbols79, hashTable, maxIters){
  const codeword174 = ft8SymbolsToCodeword(symbols79);
  // Décision dure directe (pas de vraisemblance souple ici : le DSP fournit
  // déjà des tons "durs" via ft8SymbolsToCodeword). Convention : bit 1 -> LLR
  // positif (voir ft8BpDecode) — cf. ft8DecodeSoftSymbols pour la variante à
  // vraisemblances réelles utilisée par le pipeline audio.
  const llr = codeword174.map(b => (b ? 4.0 : -4.0));
  return ft8DecodeLlr(llr, hashTable, maxIters);
}

// Variante à vraisemblances réelles (softbits), utilisée par le pipeline
// audio (logx_ft8_dsp.js) où l'amplitude du ton porte l'information de
// confiance — nettement plus robuste au bruit qu'une décision dure.
function ft8DecodeLlr(llr174, hashTable, maxIters){
  const { bits, errors } = ft8BpDecode(llr174, maxIters || 20);
  if(errors !== 0) return null;

  const a91 = new Uint8Array(12);
  for(let i = 0; i < 91; i++) if(bits[i]) a91[i >> 3] |= (1 << (7 - (i & 7)));
  const payload = a91.slice(0, 10);
  const crcExpected = ft8ExtractCrc(a91);
  const payloadForCrc = new Uint8Array(12);
  for(let i = 0; i < 10; i++) payloadForCrc[i] = payload[i];
  payloadForCrc[9] &= 0xF8;
  payloadForCrc[10] = 0;
  const crcActual = ft8Crc(payloadForCrc, 96 - 14);
  if(crcActual !== crcExpected) return null;

  const i3 = (payload[9] >>> 3) & 0x07;
  if(i3 === 1 || i3 === 2){
    const std = ft8DecodeStdMessage(payload, hashTable);
    if(!std) return null;
    return [std.callTo, std.callDe, std.extra].filter(s => s !== '').join(' ');
  }
  if(i3 === 0){
    return ft8DecodeFreeText(payload);
  }
  return null; // types 3/4/5 (RTTY roundup, non-standard, WWROF) non gérés pour l'instant
}

if(typeof module !== 'undefined' && module.exports){
  module.exports = {
    FT8_SYMBOL_PERIOD, FT8_SLOT_TIME, FT8_TONE_SPACING, FT8_ND, FT8_NN,
    FT8_LENGTH_SYNC, FT8_NUM_SYNC, FT8_SYNC_OFFSET, FTX_LDPC_N, FTX_LDPC_K, FTX_LDPC_M,
    FT8_COSTAS_PATTERN, FT8_GRAY_MAP, FT8_GRAY_MAP_INV,
    ft8Crc, ft8AddCrc, ft8ExtractCrc, ft8LdpcEncode, ft8LdpcCheckErrors, ft8BpDecode,
    ft8CodewordToSymbols, ft8SymbolsToCodeword,
    ft8CreateHashTable, ft8Pack28, ft8Unpack28, ft8PackGrid, ft8UnpackGrid,
    ft8EncodeStdMessage, ft8DecodeStdMessage, ft8EncodeFreeText, ft8DecodeFreeText,
    ft8EncodeMessage, ft8DecodeSymbols, ft8DecodeLlr,
  };
}
