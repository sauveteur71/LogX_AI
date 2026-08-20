// Réglages à faire SUR LE POSTE pour le FT8, par marque et par modèle.
//
// POURQUOI CE FICHIER. La page FT8 donnait une liste de conseils génériques,
// repliée, à 90 lignes du panneau d'émission. Elle ne savait pas quel poste
// l'opérateur avait déclaré, alors que la configuration le sait. Un débutant
// lisait « mets ton poste en mode données » sans savoir où appuyer.
//
// RÈGLE DE CONSTITUTION, sans exception : chaque ligne porte sa SOURCE et une
// CITATION vérifiable. Rien ici n'a été écrit de mémoire. Un chemin de menu
// faux s'entend sur l'air, et sur un réglage de niveau il peut abîmer un étage
// final — c'est le seul domaine du logiciel où une approximation se paie en
// matériel et en brouillage des voisins de fréquence.
//
// CE QUI N'EST PAS COUVERT est dit comme tel. Un modèle absent de la table ne
// reçoit que le socle universel, avec la mention explicite qu'aucune source
// propre à ce poste n'a été trouvée. Extrapoler d'un IC-7300 vers un IC-7610
// serait précisément l'invention qu'on s'interdit : leurs menus diffèrent
// réellement (DATA MOD contre DATA1/2/3 MOD, et pas les mêmes défauts d'usine).
'use strict';

// ─── SOCLE UNIVERSEL — guide utilisateur OFFICIEL de WSJT-X, version 2.7.0 ───
//
// Vérifié en extrayant le PDF officiel (105 pages) et en cherchant chaque
// citation mot à mot. Deux constats de cette lecture méritent d'être connus :
//
//  1. Le mot « ALC » n'apparaît NULLE PART dans le guide. Les seules
//     occurrences trouvées étaient à l'intérieur de « calculated ». La consigne
//     « ALC à zéro », très répandue, ne vient donc PAS de WSJT-X : on ne la lui
//     attribue pas. Le guide donne un critère différent — et meilleur, parce
//     qu'il se lit au wattmètre et vaut donc aussi quand le poste est commuté
//     par VOX : descendre le niveau jusqu'à ce que la puissance HF commence
//     tout juste à baisser.
//  2. Le guide ne demande de couper NI le compresseur, NI le processeur de
//     parole, NI l'égaliseur, NI le NB du poste. Son « NB » est le noise
//     blanker LOGICIEL de WSJT-X, réglé en pourcentage. Le seul traitement de
//     réception qu'il demande de toucher est l'AGC.
const REGLAGES_UNIVERSELS = [
  {
    cle: 'mode',
    intitule: 'Mode du poste',
    valeur: 'USB — ou le mode données du poste (USB-D, DATA-USB, USB-DATA…) '
          + "s'il en a un, parce que c'est lui qui active l'entrée audio arrière.",
    detail: "Y compris sur 40, 80 et 160 m, où la phonie se fait en LSB : le FT8 "
          + 'est toujours en bande latérale supérieure.',
    source: 'Guide WSJT-X 2.7.0, §5 Transceiver Setup',
    url: 'https://wsjt.sourceforge.io/wsjtx-doc/wsjtx-main-2.7.0.html#TRANSCEIVER',
    citation: 'Be sure your transceiver is set to USB (or USB Data) mode.',
  },
  {
    cle: 'niveau',
    intitule: "Niveau d'émission",
    valeur: 'Descends le curseur NIVEAU TX de cette page jusqu\'à ce que la '
          + 'puissance HF de ton poste commence tout juste à baisser. '
          + "C'est le bon niveau d'excitation audio.",
    detail: "Ce critère se lit au wattmètre, donc il marche aussi si ton poste "
          + "est commuté par VOX. Repère : à ce point l'ALC ne doit pratiquement "
          + 'plus dévier — les constructeurs disent la même chose autrement '
          + '(Kenwood : « 2 à 3 points » d\'ALC ; Icom : « within the ALC zone »). '
          + "Tous décrivent le même point : le SEUIL où l'ALC commence à agir.",
    source: 'Guide WSJT-X 2.7.0, §5 Transmitter Audio Level',
    url: 'https://wsjt.sourceforge.io/wsjtx-doc/wsjtx-main-2.7.0.html#TRANSCEIVER',
    citation: 'Adjust the Pwr slider (at right edge of main window) downward from '
            + 'its maximum until the RF output from your transmitter falls slightly.',
  },
  {
    cle: 'filtre',
    intitule: 'Filtre de réception',
    valeur: 'Le plus large disponible, centré — jusqu\'à environ 5 kHz.',
    detail: "Un signal FT8 n'occupe qu'une cinquantaine de hertz, mais des "
          + 'dizaines de stations se répartissent dans la fenêtre. Avec un '
          + 'filtre SSB ordinaire on plafonne vers 2,7 kHz.',
    source: 'Guide WSJT-X 2.7.0, liste de contrôle avant le premier QSO',
    url: 'https://wsjt.sourceforge.io/wsjtx-doc/wsjtx-main-2.7.0.html#_pre_qso_checklist',
    citation: 'Radio filters centered and set to widest available passband (up to 5 kHz).',
  },
  {
    cle: 'agc',
    intitule: 'AGC',
    valeur: "Coupé — ou, à défaut, gain HF réduit pour limiter l'action de l'AGC.",
    detail: "C'est le SEUL traitement de réception que le guide officiel demande "
          + 'de toucher.',
    source: 'Guide WSJT-X 2.7.0, §5 Transceiver Setup',
    url: 'https://wsjt.sourceforge.io/wsjtx-doc/wsjtx-main-2.7.0.html#TRANSCEIVER',
    citation: 'It is usually best to turn AGC off or reduce the RF gain control '
            + 'to minimize AGC action.',
  },
  {
    cle: 'puissance',
    intitule: "Puissance d'émission",
    valeur: 'Réduite. Le FT8 émet à 100 % du cycle de service pendant 12,6 s '
          + "d'affilée, ce que la phonie et la CW ne font jamais.",
    detail: "Le guide officiel ne donne AUCUNE valeur en watts — il dit seulement "
          + 'que le QRP est la norme en HF. La fourchette de 30 à 50 W souvent '
          + "citée est un usage courant, pas une prescription du guide.",
    source: 'Guide WSJT-X 2.7.0, liste de contrôle avant le premier QSO',
    url: 'https://wsjt.sourceforge.io/wsjtx-doc/wsjtx-main-2.7.0.html#_pre_qso_checklist',
    citation: 'Under most HF propagation conditions, QRP is the norm.',
  },
];

// ─── PAR MODÈLE — manuels constructeurs, chemins de menu exacts ──────────────
const REGLAGES_PAR_MODELE = {
  'IC-7300': [
    { intitule: 'Mode', valeur: 'USB-D (mode données de la SSB).',
      source: 'Manuel IC-7300, « Data mode (AFSK) operation »',
      url: 'https://www.manualslib.com/manual/1106166/Icom-Ic-7300.html?page=65',
      citation: 'Set the data operating mode to LSB-D, USB-D, AM-D or FM-D.' },
    { intitule: 'Source de modulation', alerte: true,
      valeur: 'MENU > SET > Connectors > DATA MOD → USB. '
            + "Défaut d'usine : ACC — à changer si l'audio arrive par le câble USB.",
      source: 'Manuel IC-7300, Set mode > Connectors',
      url: 'https://www.manualslib.com/manual/1106166/Icom-Ic-7300.html?page=123',
      citation: 'Selects the connector(s) to input the modulation signal when '
              + 'the data mode is ON.' },
    { intitule: "Niveau d'entrée audio USB",
      valeur: "MENU > SET > Connectors > USB MOD Level. Plage 0 à 100 %, défaut 50 %.",
      source: 'Manuel IC-7300, Set mode > Connectors',
      url: 'https://www.manualslib.com/manual/1106166/Icom-Ic-7300.html?page=122',
      citation: 'USB MOD Level Sets the modulation input level of [USB]. Range: 0 ~ 100%' },
    { intitule: 'Commutation par le port USB',
      valeur: 'USB SEND sur DTR ou RTS — le MÊME signal que celui choisi dans le '
            + 'logiciel, sinon le poste ne passe jamais en émission.',
      source: 'Icom, « Tips for the USB port settings » (IC-7100/7300/7851/9100)',
      url: 'https://www.manualslib.com/manual/2338919/Icom-Ic-7100.html?page=4',
      citation: 'set either the "DTR" or "RTS" items in the transceiver Set mode '
              + 'settings of "USB SEND,"' },
  ],
  'IC-705': [
    { intitule: 'Source de modulation',
      valeur: 'MENU > SET > Connectors > MOD Input > DATA MOD. '
            + "Défaut d'usine : USB — déjà correct pour le FT8 par câble USB.",
      source: 'Manuel IC-705, Set mode > Connectors',
      url: 'https://www.manualslib.com/manual/1875929/Icom-Ic-705.html?page=66',
      citation: 'In the SSB, AM, or FM mode, selects the connector(s) to input '
              + 'the modulation signal when the Data mode is OFF, or ON.' },
    { intitule: "Niveau d'entrée audio USB",
      valeur: 'MENU > SET > Connectors > MOD Input > USB MOD Level. Défaut 50 %.',
      source: 'Manuel IC-705, Set mode > Connectors',
      url: 'https://www.manualslib.com/manual/1875929/Icom-Ic-705.html?page=66',
      citation: 'USB MOD Level WLAN MOD Level Sets the modulation input level of '
              + 'each interface.' },
    { intitule: 'Commutation par le port USB', alerte: true,
      valeur: 'MENU > SET > Connectors > USB SEND/Keying > USB SEND. Défaut OFF — '
            + 'à régler. Le poste présente DEUX ports COM : USB (A) et USB (B).',
      source: 'Manuel IC-705, Set mode > Connectors',
      url: 'https://www.manualslib.com/manual/1875929/Icom-Ic-705.html?page=67',
      citation: 'USB SEND Sets the USB terminal of the transceiver to receive the '
              + 'SEND signal from the software on the PC.' },
  ],
  'IC-9700': [
    { intitule: 'Source de modulation', alerte: true,
      valeur: 'MENU > SET > Connectors > MOD Input > DATA MOD. '
            + "Défaut d'usine : ACC — à changer si l'audio arrive par le câble USB.",
      source: 'Manuel IC-9700, Set mode > Connectors',
      url: 'https://www.manualslib.com/manual/1555693/Icom-Ic-9700.html?page=67',
      citation: 'In the SSB, AM, or FM mode, selects the connector(s) to input '
              + 'the modulation signal when the data mode is OFF, or ON.' },
    { intitule: "Niveau d'entrée audio USB",
      valeur: 'MENU > SET > Connectors > MOD Input > USB MOD Level. Défaut 50 %.',
      source: 'Manuel IC-9700, Set mode > Connectors',
      url: 'https://www.manualslib.com/manual/1555693/Icom-Ic-9700.html?page=67',
      citation: 'ACC MOD Level USB MOD Level LAN MOD Level Sets the modulation '
              + 'input level of each interface.' },
    { intitule: 'Commutation par le port USB',
      valeur: 'MENU > SET > Connectors > USB SEND/Keying > USB SEND. Défaut OFF.',
      source: 'Manuel IC-9700, Set mode > Connectors',
      url: 'https://www.manualslib.com/manual/1555693/Icom-Ic-9700.html?page=67',
      citation: 'USB SEND Sets the USB terminal of the transceiver to receive the '
              + 'SEND signal from the software on the PC.' },
  ],
  'IC-7610': [
    { intitule: 'Mode',
      valeur: "Toucher [DATA] dans l'écran MODE. Le poste a trois modes données : "
            + 'DATA1, DATA2, DATA3.',
      source: 'Manuel IC-7610',
      url: 'https://www.manualslib.com/manual/1313711/Icom-Ic-7610.html?page=58',
      citation: 'Touching the [DATA] key in the MODE screen activates the data mode' },
    { intitule: 'Source de modulation',
      valeur: 'MENU > SET > Connectors > MOD Input > DATA1 MOD (ou DATA2/DATA3 '
            + "selon le mode utilisé) → USB. Défauts d'usine : ACC pour DATA1, "
            + 'USB pour DATA2, MIC+USB pour DATA3.',
      source: 'Manuel IC-7610',
      url: 'https://www.manualslib.com/manual/1313711/Icom-Ic-7610.html?page=58',
      citation: 'It automatically sets the modulation input to the "MIC," "ACC," '
              + '"MIC, ACC," "USB," "MIC, USB" or "LAN" connector(s)' },
    { intitule: 'Compresseur de parole',
      valeur: "Rien à faire : le passage en mode DATA le désactive tout seul, et "
            + "verrouille la bande passante d'émission sur 300–2700 Hz.",
      source: 'Manuel IC-7610',
      url: 'https://www.manualslib.com/manual/1313711/Icom-Ic-7610.html?page=58',
      citation: '(Disables the Speech Compressor)' },
  ],
  'FT-991A': [
    { intitule: 'Mode', valeur: 'DATA-USB — le repère « D-U » apparaît à l\'écran. '
            + 'Touche MODE, puis la touche correspondante sur l\'écran.',
      source: 'Manuel FT-991A, « DATA (PSK) Operation »',
      url: 'https://www.manualslib.com/manual/2717394/Yaesu-Ft-991a.html?page=125',
      citation: 'Press the MODE button, and then touch the corresponding key on '
              + 'the LCD to select the DATA-USB operating mode.' },
    { intitule: 'Menu 070 DATA IN SELECT', alerte: true,
      valeur: 'REAR — et surtout PAS « MIC », malgré ce qu\'affiche le tableau '
            + 'récapitulatif du manuel.',
      detail: 'Chez Yaesu, « REAR » ne désigne pas la prise arrière en cuivre mais '
            + 'TOUTE source autre que le micro de façade — codec USB interne '
            + 'compris. La preuve est dans le manuel lui-même : il écrit que le '
            + "menu 072 n'agit QUE si 070 vaut REAR. Régler 072 sur USB en "
            + 'laissant 070 sur MIC serait donc sans effet, et le poste resterait '
            + 'sourd au signal du PC. La ligne du tableau se réfute toute seule.',
      source: 'Manuel FT-991A, description du menu 072',
      url: 'https://www.manualslib.com/manual/2717394/Yaesu-Ft-991a.html?page=137',
      citation: "Selects the input jack of the data signal when '070 DATA IN "
              + "SELECT' is set to 'REAR'." },
    { intitule: 'Menu 072 DATA PORT SELECT',
      valeur: "USB (défaut d'usine : DATA). Route les données par le port USB "
            + 'plutôt que par la prise arrière RTTY/DATA.',
      source: 'Manuel FT-991A, menu 072',
      url: 'https://www.manualslib.com/manual/2717394/Yaesu-Ft-991a.html?page=137',
      citation: "Selects the input jack of the data signal when '070 DATA IN "
              + "SELECT' is set to 'REAR'." },
    { intitule: 'Menu 071 DATA PTT SELECT',
      valeur: 'DAKY, ou RTS selon la configuration du port virtuel. '
            + "Défaut d'usine : DAKY.",
      source: 'Manuel FT-991A, menu 071',
      url: 'https://www.manualslib.com/manual/2717394/Yaesu-Ft-991a.html?page=136',
      citation: 'Selects the PTT control method during the sending/receiving of data.' },
    { intitule: 'Menu 073 DATA OUT LEVEL',
      valeur: 'Niveau audio envoyé au PC, 0 à 100, défaut 50.',
      source: 'Manuel FT-991A, menu 073',
      url: 'https://www.manualslib.com/manual/2717394/Yaesu-Ft-991a.html?page=137',
      citation: 'Sets the output level during the sending/receiving of data '
              + '(PSK31, SSTV, etc.).' },
  ],
  'FT-991': [
    { intitule: 'Mode', valeur: 'DATA-USB. Touche MODE, puis la touche '
            + "correspondante sur l'écran.",
      source: 'Manuel FT-991, « Data Mode »',
      url: 'https://www.manualslib.com/manual/873378/Yaesu-Ft-991.html?page=121',
      citation: 'Press the MODE button, and then touch the corresponding key on '
              + 'the LCD to select the DATA-USB operating mode.' },
    { intitule: 'Menu 070 DATA IN SELECT', alerte: true,
      valeur: 'REAR — et surtout PAS « MIC », malgré le tableau du manuel. '
            + 'Même raisonnement que sur le FT-991A : le menu 072 ne fait rien '
            + 'si 070 est sur MIC.',
      source: 'Manuel FT-991, menu 072',
      url: 'https://www.manualslib.com/manual/873378/Yaesu-Ft-991.html?page=133',
      citation: 'Selects the input jack of the data signal' },
    { intitule: 'Menu 072 DATA PORT SELECT',
      valeur: "USB (défaut d'usine : DATA).",
      source: 'Manuel FT-991, menu 072',
      url: 'https://www.manualslib.com/manual/873378/Yaesu-Ft-991.html?page=133',
      citation: 'Selects the input jack of the data signal' },
    { intitule: 'Menu 071 DATA PTT SELECT',
      valeur: "DAKY ou RTS. Défaut d'usine : DAKY.",
      source: 'Manuel FT-991, menu 071',
      url: 'https://www.manualslib.com/manual/873378/Yaesu-Ft-991.html?page=133',
      citation: 'Sets the PTT control during the sending/receiving of data' },
  ],
  'FT-891': [
    { intitule: 'Mode', valeur: 'DATA. Appui long (1 s) sur [BAND (MODE)], puis '
            + 'rotation du bouton DIAL.',
      source: 'Manuel FT-891',
      url: 'https://www.manualslib.com/manual/1245226/Yaesu-Ft-891.html?page=67',
      citation: 'Rotate the DIAL knob to select the "DATA" mode.' },
  ],
  'TS-590SG': [
    { intitule: 'Mode', valeur: 'Touche [DATA] — elle bascule USB ↔ USB-DATA.',
      source: 'Manuel TS-590SG',
      url: 'https://www.kenwood.com/usa/Support/pdf/B5A-0180-00.pdf',
      citation: '[DATA] Press to select a Data mode (LSB/ LSB-DATA, USB/ USB-DATA, '
              + 'FM/ FM-DATA, or AM-DATA)' },
    { intitule: 'Source de modulation', alerte: true,
      valeur: 'Menu No. 69 → USB. Défaut : ACC2 — à changer.',
      source: 'Kenwood, notice officielle « TS-590G FT8 settings »',
      url: 'https://www.kenwood.com/i/products/info/amateur/ts_590g/pdf/ts590_g_ft8_settings_en.pdf',
      citation: 'TS-590SG: In Menu No.69, select "USB". (The default is "ACC2".)' },
    { intitule: "Niveau d'entrée audio",
      valeur: 'Menu No. 71, plage 0 à 9, défaut 4. En DERNIER recours seulement : '
            + "Kenwood demande d'abord d'agir sur le niveau du logiciel, puis sur "
            + 'les réglages son du PC.',
      source: 'Kenwood, notice officielle « TS-590G FT8 settings »',
      url: 'https://www.kenwood.com/i/products/info/amateur/ts_590g/pdf/ts590_g_ft8_settings_en.pdf',
      citation: 'TS-590S: In Menu No.64, adjust in the range of "0" ~ "9". '
              + '(The default is "4".)' },
    { intitule: 'Largeur de filtre en SSB-DATA',
      valeur: 'Menu No. 29 : passer de « 2 » (WIDTH/SHIFT) à « 1 » (HI/LO) pour '
            + "disposer d'une bande passante jusqu'à 5 kHz. Le TS-590S, lui, ne "
            + 'peut PAS changer ce réglage.',
      source: 'Kenwood, notice officielle « TS-590G FT8 settings »',
      url: 'https://www.kenwood.com/i/products/info/amateur/ts_590g/pdf/ts590_g_ft8_settings_en.pdf',
      citation: 'should be changed in Menu No.29 from "2"(WIDTH/SHIFT: default) to '
              + '"1 (HI/LO) to obtain sufficient RX bandwidth of up to 5kHz' },
    { intitule: 'Processeur de parole', alerte: true,
      valeur: "À couper UNE FOIS DÉJÀ en mode DATA : son état est mémorisé "
            + 'séparément du mode SSB normal. Le couper en SSB ne le coupe pas en '
            + 'SSB-DATA.',
      source: 'Kenwood TS-590SG, manuel détaillé',
      url: 'https://www.kenwood.com/i/products/info/amateur/pdf/TS-590SG_IDM.pdf',
      citation: 'In SSB-DATA, AM-DATA and FM-DATA modes, the On/Off settings of '
              + 'the speech processor and the settings of DSP filters are stored '
              + 'independently' },
    { intitule: 'Émettre sans pilotage CAT',
      valeur: 'Menu 76 « DATA VOX » sur ON : le poste passe en émission tout seul '
            + "sur l'audio venant du PC.",
      source: 'Kenwood TS-590SG, manuel détaillé',
      url: 'https://www.kenwood.com/i/products/info/amateur/pdf/TS-590SG_IDM.pdf',
      citation: 'Setting the "DATA VOX" function to ON in Menu 76 enables '
              + 'transmission automatically according to the audio input from the PC.' },
  ],
  'TS-590S': [
    { intitule: 'Source de modulation', alerte: true,
      valeur: 'Menu No. 63 → USB. Défaut : ACC2 — à changer.',
      source: 'Kenwood, notice officielle « TS-590G FT8 settings »',
      url: 'https://www.kenwood.com/i/products/info/amateur/ts_590g/pdf/ts590_g_ft8_settings_en.pdf',
      citation: 'TS-590S: In Menu No.63, select "USB". (The default is "ACC2".)' },
    { intitule: "Niveau d'entrée audio",
      valeur: 'Menu No. 64, plage 0 à 9, défaut 4.',
      source: 'Kenwood, notice officielle « TS-590G FT8 settings »',
      url: 'https://www.kenwood.com/i/products/info/amateur/ts_590g/pdf/ts590_g_ft8_settings_en.pdf',
      citation: 'TS-590S: In Menu No.64, adjust in the range of "0" ~ "9". '
              + '(The default is "4".)' },
  ],
  'TS-890S': [
    { intitule: 'Mode et source de modulation',
      valeur: "Maintenir [DATA] pour afficher l'écran de source audio ; presser "
            + '[DATA] pour activer le mode données. Vérifier « Rear » sous '
            + '« Audio Input », puis choisir « USB Audio » (valeur par défaut).',
      source: 'Kenwood, notice officielle « TS-890S FT8 settings »',
      url: 'https://www.kenwood.com/i/products/info/amateur/ts_890/pdf/ts890_ft8_settings_en.pdf',
      citation: 'Check the "Rear" setting under "Audio Input" for "DATA SEND (PF)" '
              + 'under "TX Method". Select "USB Audio" (default).' },
    { intitule: 'Largeur de filtre en SSB-DATA',
      valeur: 'Menu [6-12] → « High & Low Cut », pour couper dans la plage '
            + '0–5000 Hz comme en SSB.',
      source: 'Kenwood, notice officielle « TS-890S FT8 settings »',
      url: 'https://www.kenwood.com/i/products/info/amateur/ts_890/pdf/ts890_ft8_settings_en.pdf',
      citation: 'Configure the DSP filter control method in Menu [6-12] "Filter '
              + 'Control in SSB-DATA mode (High/Low and Shift/Width)". Select '
              + '"High & Low Cut"' },
    { intitule: "Niveau d'entrée audio",
      valeur: 'Menu [7-06] « USB: Audio Input Level », si les réglages son du PC '
            + 'ne suffisent pas.',
      source: 'Kenwood, notice officielle « TS-890S FT8 settings »',
      url: 'https://www.kenwood.com/i/products/info/amateur/ts_890/pdf/ts890_ft8_settings_en.pdf',
      citation: 'adjust the audio input level to the TS-890S in Menu [7-06] '
              + '"USB: Audio Input Level".' },
  ],
};

// ─── PAR MARQUE — vaut pour tous les postes de la marque ─────────────────────
const REGLAGES_PAR_MARQUE = {
  icom: [
    { intitule: 'CI-V Transceive', alerte: true,
      valeur: 'À DÉSACTIVER dans le menu du poste. Actif par défaut sur la '
            + 'plupart des Icom, il fait émettre au poste du trafic CAT non '
            + 'sollicité qui perturbe le pilotage par le PC.',
      detail: "C'est la seule prescription nominative par marque de tout le guide "
            + 'WSJT-X — et il ne donne pas le chemin de menu.',
      source: 'Guide WSJT-X 2.7.0, FAQ',
      url: 'https://wsjt.sourceforge.io/wsjtx-doc/wsjtx-main-2.7.0.html#FAQ',
      citation: 'By default, most Icom transceivers have CI-V Transceive Mode '
              + "enabled. [...] Disable this option in the rig's menu." },
  ],
  xiegu: [],
  yaesu: [],
  kenwood: [],
  elecraft: [],
};

// Normalise un nom de modèle pour la recherche : les listes de CONFIG écrivent
// « IC-7300 », mais rien ne garantit la casse ni les espaces d'une saisie
// future. On compare sur une forme réduite plutôt que sur l'égalité stricte.
function _clefModele(modele){
  return String(modele || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
}

const _INDEX_MODELES = (function(){
  const idx = {};
  for(const nom in REGLAGES_PAR_MODELE){
    idx[_clefModele(nom)] = {nom: nom, lignes: REGLAGES_PAR_MODELE[nom]};
  }
  return idx;
})();

// Rend TOUT ce qu'on sait pour ce poste, et dit explicitement ce qu'on ignore.
// `couvert` vaut false quand aucune source propre au modèle n'a été trouvée :
// l'écran doit alors le DIRE, au lieu de laisser croire que le socle universel
// est un réglage propre au poste.
function reglagesPoste(marque, modele){
  const trouve = _INDEX_MODELES[_clefModele(modele)];
  return {
    marque: String(marque || ''),
    modele: String(modele || ''),
    couvert: !!trouve,
    universels: REGLAGES_UNIVERSELS,
    modeleLignes: trouve ? trouve.lignes : [],
    marqueLignes: REGLAGES_PAR_MARQUE[String(marque || '').toLowerCase()] || [],
  };
}

window.REGLAGES_UNIVERSELS = REGLAGES_UNIVERSELS;
window.REGLAGES_PAR_MODELE = REGLAGES_PAR_MODELE;
window.REGLAGES_PAR_MARQUE = REGLAGES_PAR_MARQUE;
window.reglagesPoste = reglagesPoste;
