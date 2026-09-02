# -*- coding: utf-8 -*-
"""Fréquences d'activité EME par bande.

Le Doppler EME se calcule sur la fréquence RF RÉELLE, pas sur la fréquence
affichée par le CAT. Au-dessus de 1296 MHz, l'usage amateur passe quasi
systématiquement par transverter : le dial CAT lit alors une FI (souvent en
28 ou 144 MHz), pas la RF micro-ondes — d'où le drapeau `transverter`,
signalé au cockpit pour qu'il n'aille pas calculer un Doppler sur la FI.

SOURCES (relevé le 2026-09-01, plan de bandes IARU Région 1) :
  - VHF (50, 144 MHz) — "IARU Region 1 VHF band plan", effective déc. 2020 :
    https://www.iaru-r1.org/wp-content/uploads/2020/12/VHF-Bandplan.pdf
      "50,300-50,400 ... 50.310-320 EME center of activity"
      "144,100-144,150 MGM and Telegraphy ... 144.110-144-160 CW and MGM EME"
      (lu "144.110-144.160", tiret probable pour un point décimal)
  - UHF (432, 1296, 2320 MHz) — "IARU Region 1 UHF band plan", déc. 2020 :
    https://www.iaru-r1.org/wp-content/uploads/2021/03/UHF-Bandplan.pdf
      1296 MHz : "1296,000 - 1296,150 ... 1296.000 - 1296.025 Moonbounce"
      2320 MHz : "2320,000 -2320,800 ... 2320.000-2320.025 EME"
      432 MHz : ce PDF (édition courante 2020) NE PORTE PAS le mot "EME" —
      la valeur retenue ci-dessous vient d'une source IARU R1 secondaire
      (voir note 432 MHz plus bas), confiance moindre que les autres bandes.
  - SHF (3400, 5760, 10368, 24048 MHz) — "IARU Region 1 SHF band plan",
    déc. 2020 : https://www.iaru-r1.org/wp-content/uploads/2020/12/SHF-Bandplan.pdf
      3400 MHz : "3400,000 - 340,800 ... 3400.100 EME Centre of activity"
      5760 MHz : "5760.200 Narrow band center of activity" (pas de mot "EME"
      explicite — voir note ci-dessous)
      10368 MHz : "10.3682 Narrow band center of activity" (section exprimée
      en GHz dans ce tableau → lu 10368.2 MHz)
      24048 MHz : "24.0482 Narrow band centre of activity" (idem → 24048.2 MHz)
  - µWave (47088 MHz) — "IARU Region 1 µWave band plan", déc. 2020 :
    https://www.iaru-r1.org/wp-content/uploads/2020/12/%C2%B5W-Bandplan.pdf
      Segment "47.088 - 47.090" (GHz, colonne mal étiquetée "MHz" dans le
      PDF source) borné à 2700 Hz de largeur de bande max — pas de centre
      décimal publié pour ce segment.
  - Corroboration/complément (Murray Niman G6JYB, "Harmonised Frequencies
    for EME – Past, Present and Future", EME2012, IARU Region 1) :
    https://www.microwavers.org/eme2012/files/saturday/G6JYB_Harmonised-EME-Frequencies_EME2012.pdf
      Table 1 confirme 50 MHz (50.310-50.320), 144 MHz (CW 144.000-144.110 /
      MGM 144.110-144.160), 1296 MHz (1296.00-1296.025), 2320 MHz
      (2320.0-2320.025), 3400 MHz (3400.100) ; et donne, en l'absence de
      libellé "EME" officiel dans le plan IARU R1 courant :
        - 432 MHz : "CW: 432.000–432.025" (source citée : IARU Region 1 VHF
          Managers' Handbook v6)
        - 5760/10368/24048/47088 MHz : "No EME designation" dans le plan de
          bandes lui-même — confirme que ces 4 bandes n'ont PAS de libellé
          "EME" officiel, seulement un centre d'activité narrowband (ou,
          pour 47088, une désignation historique ponctuelle "47088").
  - Recoupement indépendant pour 5760/10368/24048 (NTMS Microwave Society,
    non-IARU) : 5760.200 MHz, 10368.200 MHz et 24048.200 MHz cités comme
    fréquences d'appel EME 6cm/3cm/1,2cm — concorde avec les centres
    narrowband officiels IARU R1 ci-dessus.

Notes de confiance (aucune valeur n'est inventée, mais toutes ne sont pas
sourcées à égalité) :
  - 50, 144, 1296, 2320, 3400 MHz : le mot "EME" (ou "Moonbounce") apparaît
    littéralement dans le plan de bandes IARU R1 en vigueur (2020). Confiance
    haute.
  - 432 MHz : PAS de libellé "EME" dans le plan de bandes IARU R1 courant ;
    valeur reprise d'une source secondaire IARU R1 (VHF Managers' Handbook
    v6, citée par G6JYB/EME2012). Confiance moyenne.
  - 5760, 10368, 24048 MHz : PAS de libellé "EME" dans le plan de bandes
    IARU R1 courant, seulement "narrow band centre of activity" — mais ce
    centre est confirmé comme fréquence d'appel EME par une source tierce
    indépendante (NTMS Microwave Society). Confiance moyenne.
  - 47088 MHz : aucune décimale de centre n'est publiée par l'IARU R1 pour
    cette bande (le plan de bandes ne fait que borner un segment étroit
    47088-47090 MHz). La valeur retenue est l'entier historiquement cité par
    G6JYB/EME2012 (colonnes Past/Present : "47088"/"47088.?") — PAS une
    décimale inventée. Confiance la plus faible du tableau.
"""

EME_ACTIVITE = {
    '50':    {'rf_mhz': 50.315,    'transverter': False, 'label': '6 m'},
    '144':   {'rf_mhz': 144.135,   'transverter': False, 'label': '2 m'},
    '432':   {'rf_mhz': 432.0125,  'transverter': False, 'label': '70 cm'},
    '1296':  {'rf_mhz': 1296.0125, 'transverter': False, 'label': '23 cm'},
    '2320':  {'rf_mhz': 2320.0125, 'transverter': True,  'label': '13 cm'},
    '3400':  {'rf_mhz': 3400.100,  'transverter': True,  'label': '9 cm'},
    '5760':  {'rf_mhz': 5760.200,  'transverter': True,  'label': '6 cm'},
    '10368': {'rf_mhz': 10368.200, 'transverter': True,  'label': '3 cm'},
    '24048': {'rf_mhz': 24048.200, 'transverter': True,  'label': '1,2 cm'},
    '47088': {'rf_mhz': 47088.000, 'transverter': True,  'label': '6 mm'},
}


def centre_rf_mhz(band):
    e = EME_ACTIVITE.get(str(band))
    return e['rf_mhz'] if e else None


def est_transverter(band):
    e = EME_ACTIVITE.get(str(band))
    return bool(e['transverter']) if e else False
