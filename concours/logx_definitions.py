# -*- coding: utf-8 -*-
"""Données de référence des concours : définitions, scoring, URLs de règlements.

En plus de la base codée ci-dessous, les concours ajoutés via l'extraction IA
de règlement (Phase 3) — toujours après relecture humaine — sont persistés
dans custom_contests.json et fusionnés au chargement du module."""

import json
import os


# ─── BASE DE DONNÉES RÈGLEMENTS (structure de référence) ─────────────────────
# Chaque concours a : règles de calcul de dates, URLs de vérification, scoring
CONTEST_DEFINITIONS = {

    # ════════════════════════════════════════════════════════════
    # REF — CALENDRIER FRANCE
    # ════════════════════════════════════════════════════════════
    'REF_RPH': {
        'name': 'Rallye des Points Hauts',
        'organizer': 'REF',
        'check_url': 'https://concours.r-e-f.org/calendrier/calendrier.php',
        'rules_url': 'https://concours.r-e-f.org/reglements/actuels/reg_rph_fr_20250312.pdf',
        'date_rule': 'first_saturday_july',
        'duration_h': 24,
        'start_utc': '14:00',
        'bands': ['144','432'],
        'modes': ['SSB'],
        'exchange': 'RS + N°serie + locator6',
        'scoring': {'type':'km','multiplier':None,'unit':'1 pt/km'},
        'log_format': 'EDI',
        'log_deadline': 'wednesday_after',
        'log_submit': 'https://concours.r-e-f.org',
        'serial_per_band': True,
        'portable_required': True,
        'notes': 'Alimentation 100% autonome obligatoire. NO-DIGI. SSB uniquement.',
    },
    'REF_NAT_THF': {
        'name': 'National THF — Trophée F3SK',
        'organizer': 'REF',
        'check_url': 'https://concours.r-e-f.org/calendrier/calendrier.php',
        'rules_url': 'https://concours.r-e-f.org/reglements/actuels/reg_natthf_fr_20250312.pdf',
        'date_rule': 'first_saturday_march_14h',
        'duration_h': 24,
        'bands': ['144','432','1296','2320','3400','5760','10368'],
        'modes': ['SSB','CW','FM'],
        'exchange': 'RS + N°serie + locator6',
        'scoring': {'type':'km_x_locators','multiplier':'locator_squares','unit':'km × locators'},
        'log_format': 'EDI',
        'log_deadline': 'wednesday_after',
        'log_submit': 'https://concours.r-e-f.org',
    },
    'REF_PRINTEMPS': {
        'name': 'Concours du Printemps',
        'organizer': 'REF',
        'check_url': 'https://concours.r-e-f.org/calendrier/calendrier.php',
        'rules_url': 'https://concours.r-e-f.org/reglements/actuels/reg_printemps_fr_20250312.pdf',
        'date_rule': 'first_saturday_may',
        'duration_h': 24, 'start_utc': '14:00',
        'bands': ['144','432','1296','2320','3400','5760','10368'],
        'modes': ['SSB','CW','FM'],
        'exchange': 'RS + N°serie + locator6',
        'scoring': {'type':'km_x_locators','multiplier':'locator_squares','unit':'km × locators'},
        'log_format': 'EDI', 'log_deadline': 'wednesday_after',
    },
    'REF_ETE': {
        'name': "Concours d'Été",
        'organizer': 'REF',
        'check_url': 'https://concours.r-e-f.org/calendrier/calendrier.php',
        'rules_url': 'https://concours.r-e-f.org/reglements/actuels/reg_ete_fr_20250312.pdf',
        'date_rule': 'first_saturday_august',
        'duration_h': 24, 'start_utc': '14:00',
        'bands': ['144','432','1296','2320','3400','5760','10368'],
        'modes': ['SSB','CW','FM'],
        'exchange': 'RS + N°serie + locator6',
        'scoring': {'type':'km_x_locators','multiplier':'locator_squares','unit':'km × locators'},
        'log_format': 'EDI', 'log_deadline': 'wednesday_after',
    },
    'REF_CDF_THF': {
        'name': 'Championnat de France THF',
        'organizer': 'REF',
        'check_url': 'https://concours.r-e-f.org/calendrier/calendrier.php',
        'rules_url': 'https://concours.r-e-f.org/reglements/actuels/reg_cdfthf_fr_20251222.pdf',
        'date_rule': 'first_saturday_june',
        'duration_h': 24, 'start_utc': '14:00',
        'bands': ['144','432','1296','2320','3400','5760','10368'],
        'modes': ['SSB','CW','FM'],
        'exchange': 'RS + N°serie + locator6',
        'scoring': {'type':'km_x_locators','multiplier':'locator_squares','unit':'km × locators'},
        'log_format': 'EDI', 'log_deadline': 'wednesday_after',
    },
    'REF_QRP': {
        'name': "Bol d'Or des QRP — Trophée F8BO",
        'organizer': 'REF',
        'check_url': 'https://concours.r-e-f.org/calendrier/calendrier.php',
        'rules_url': 'https://concours.r-e-f.org/reglements/actuels/reg_qrp_fr_20250312.pdf',
        'date_rule': 'third_saturday_july',
        'duration_h': 24, 'start_utc': '14:00',
        'bands': ['144','432','1296','2320','3400','5760','10368'],
        'modes': ['SSB','CW'],
        'exchange': 'RS + N°serie + locator6',
        'scoring': {'type':'km_x_locators','multiplier':'locator_squares','unit':'km × locators'},
        'log_format': 'EDI', 'log_deadline': 'wednesday_after',
        'notes': 'QRP uniquement : max 5W',
    },
    'REF_160M': {
        'name': 'REF 160m — Trophée F8EX',
        'organizer': 'REF',
        'check_url': 'https://concours.r-e-f.org/calendrier/calendrier.php',
        'rules_url': 'https://concours.r-e-f.org/reglements/actuels/reg_ref160_fr_20250312.pdf',
        'date_rule': 'third_saturday_november_17h',
        'duration_h': 7, 'start_utc': '17:00',
        'bands': ['1.8'],
        'modes': ['SSB','CW'],
        'exchange': 'RS + N°serie + dept',
        'scoring': {'type':'dept_dxcc','multiplier':'depts+DXCC','unit':'pts × depts+DXCC'},
        'log_format': 'CABRILLO', 'log_deadline': '5_days_after',
    },
    'REF_CDF_HF_SSB': {
        'name': 'Championnat de France HF Téléphonie',
        'organizer': 'REF',
        'check_url': 'https://concours.r-e-f.org/calendrier/calendrier.php',
        'rules_url': 'https://concours.r-e-f.org/reglements/actuels/reg_cdfhf_fr_20251117.pdf',
        'date_rule': 'third_saturday_february',
        'duration_h': 36, 'start_utc': '06:00',
        'bands': ['3.5','7','14','21','28'],
        'modes': ['SSB'],
        'exchange': 'RS + N°serie + dept',
        'cabrillo_name': 'REF-SSB',
        'cabrillo_exchange': ['rst', 'exch'],
        'scoring': {'type':'dept_dxcc','multiplier':'depts+DXCC','unit':'pts × depts+DXCC'},
        'log_format': 'CABRILLO',
    },
    'REF_CDF_HF_CW': {
        'name': 'Championnat de France HF Télégraphie',
        'organizer': 'REF',
        'check_url': 'https://concours.r-e-f.org/calendrier/calendrier.php',
        'rules_url': 'https://concours.r-e-f.org/reglements/actuels/reg_cdfhf_fr_20251117.pdf',
        'date_rule': 'fourth_saturday_january',
        'duration_h': 36, 'start_utc': '06:00',
        'bands': ['3.5','7','14','21','28'],
        'modes': ['CW'],
        'exchange': 'RST + N°serie + dept',
        'cabrillo_name': 'REF-CW',
        'cabrillo_exchange': ['rst', 'exch'],
        'scoring': {'type':'dept_dxcc','multiplier':'depts+DXCC','unit':'pts × depts+DXCC'},
        'log_format': 'CABRILLO',
    },

    # ════════════════════════════════════════════════════════════
    # IARU REGION 1 — VHF/UHF
    # ════════════════════════════════════════════════════════════
    'IARU_VHF': {
        'name': 'IARU R1 VHF 145 MHz',
        'organizer': 'IARU-R1',
        'check_url': 'https://www.iaru-r1.org/on-the-air/contests/',
        'rules_url': 'https://www.iaru-r1.org/wp-content/uploads/2024/02/Rules-IARU-R1-VHF-up-Contests.pdf',
        'date_rule': 'first_saturday_september',
        'duration_h': 24, 'start_utc': '14:00',
        'bands': ['144'],
        'modes': ['SSB','CW','FM'],
        'exchange': 'RS + N°serie + locator6 (6 car OBLIGATOIRES)',
        'scoring': {
            'type': 'km_x_large_locator_squares',
            'multiplier': 'large_locator_squares_4char',
            'unit': 'total_km × nb_grands_carrés_locator',
            'same_square_bonus': 50,
            'note': 'QSO même grand carré = 50 pts. Score = km_total × nb_grands_carrés_différents',
        },
        'log_format': 'EDI',
        'log_deadline': 'second_monday_after',
        'log_submit': 'https://iaru.oevsv.at/',
        'self_spot_allowed': True,
        'notes': 'Self-spot autorisé sauf sur DX Cluster. Correction post-contest interdite.',
    },
    'IARU_UHF': {
        'name': 'IARU R1 UHF/SHF',
        'organizer': 'IARU-R1',
        'check_url': 'https://www.iaru-r1.org/on-the-air/contests/',
        'rules_url': 'https://www.iaru-r1.org/wp-content/uploads/2024/02/Rules-IARU-R1-VHF-up-Contests.pdf',
        'date_rule': 'first_saturday_october',
        'duration_h': 24, 'start_utc': '14:00',
        'bands': ['432','1296','2320','3400','5760','10368'],
        'modes': ['SSB','CW','FM'],
        'exchange': 'RS + N°serie + locator6',
        'scoring': {
            'type': 'km_x_large_locator_squares',
            'multiplier': 'large_locator_squares_4char',
            'unit': 'total_km × nb_grands_carrés_locator',
            'same_square_bonus': 50,
        },
        'log_format': 'EDI',
        'log_deadline': 'second_monday_after',
        'log_submit': 'https://iaru.oevsv.at/',
    },
    'IARU_50MHZ': {
        'name': 'IARU R1 50 MHz — Mémorial F8SH',
        'organizer': 'IARU-R1 / REF',
        'check_url': 'https://concours.r-e-f.org/calendrier/calendrier.php',
        'rules_url': 'https://concours.r-e-f.org/reglements/actuels/reg_iaru50_fr_20250312.pdf',
        'date_rule': 'third_saturday_june',
        'duration_h': 24, 'start_utc': '14:00',
        'bands': ['50'],
        'modes': ['SSB','CW'],
        'exchange': 'RS + N°serie + locator6',
        'scoring': {
            'type': 'km_x_large_locator_squares',
            'multiplier': 'large_locator_squares_4char',
            'unit': 'total_km × nb_grands_carrés_locator',
        },
        'log_format': 'EDI',
        'log_deadline': 'second_monday_after',
        'log_submit': 'https://iaru.oevsv.at/',
    },
    'IARU_MARCONI': {
        'name': 'Marconi Memorial — IARU R1 VHF CW',
        'organizer': 'IARU-R1 / REF',
        'check_url': 'https://concours.r-e-f.org/calendrier/calendrier.php',
        'rules_url': 'https://concours.r-e-f.org/reglements/actuels/reg_marconi_fr_20250312.pdf',
        'date_rule': 'first_saturday_november',
        'duration_h': 24, 'start_utc': '14:00',
        'bands': ['144'],
        'modes': ['CW'],
        'exchange': 'RST + N°serie + locator6',
        'scoring': {
            'type': 'km_x_large_locator_squares',
            'multiplier': 'large_locator_squares_4char',
            'unit': 'total_km × nb_grands_carrés_locator',
        },
        'log_format': 'EDI',
        'log_deadline': 'second_monday_after',
        'log_submit': 'https://iaru.oevsv.at/',
        'notes': 'CW UNIQUEMENT',
    },

    # ════════════════════════════════════════════════════════════
    # CQ WORLD WIDE
    # ════════════════════════════════════════════════════════════
    'CQ_WW_SSB': {
        'name': 'CQ World Wide DX — SSB',
        'organizer': 'CQ Magazine / WWROF',
        'check_url': 'https://cqww.com/rules.htm',
        'rules_url': 'https://cqww.com/rules.htm',
        'date_rule': 'last_full_weekend_october',
        'duration_h': 48, 'start_utc': '00:00',
        'bands': ['1.8','3.5','7','14','21','28'],
        'modes': ['SSB'],
        'exchange': 'RS + zone_CQ (ex: 59 14)',
        'cabrillo_name': 'CQ-WW-SSB',
        'cabrillo_exchange': ['rst', 'exch'],
        'scoring': {
            'type': 'zone_country_per_band',
            'points_dx': 3, 'points_same_continent': 1, 'points_same_country': 0,
            'multiplier': 'zones_CQ + pays_DXCC par bande',
            'unit': 'QSO_pts × (zones_CQ + DXCC)',
            'note': '3pts=continents différents / 1pt=même continent diff pays / 0pt=même pays (mais mult!)',
        },
        'log_format': 'CABRILLO',
        'log_deadline': '5_days_after',
        'log_submit': 'https://cqww.com/logcheck/',
        'itu_r1_notes': '40m SSB interdit >7200 kHz. 160m interdit <1810 kHz.',
        'categories': 'SO-HP(1500W) SO-LP(100W) SO-QRP(5W) SO-Assisted MS M2 MM',
        'notes': 'Auto-spotting interdit en SO. Audio recording obligatoire si top-5.',
        # Catégorie Multi-Single (et assimilées) : un seul changement de bande
        # autorisé toutes les 10 min (sauf pour travailler un nouveau mult) —
        # règle absente pour la plupart des autres concours de cette base, ne
        # PAS généraliser (cf. logx_coach.build_coach_state, gate sur ce champ).
        'band_change_rule_min': 10,
    },
    'CQ_WW_CW': {
        'name': 'CQ World Wide DX — CW',
        'organizer': 'CQ Magazine / WWROF',
        'check_url': 'https://cqww.com/rules.htm',
        'rules_url': 'https://cqww.com/rules.htm',
        'date_rule': 'last_full_weekend_november',
        'duration_h': 48, 'start_utc': '00:00',
        'bands': ['1.8','3.5','7','14','21','28'],
        'modes': ['CW'],
        'exchange': 'RST + zone_CQ (ex: 599 14)',
        'cabrillo_name': 'CQ-WW-CW',
        'cabrillo_exchange': ['rst', 'exch'],
        'scoring': {
            'type': 'zone_country_per_band',
            'points_dx': 3, 'points_same_continent': 1, 'points_same_country': 0,
            'multiplier': 'zones_CQ + pays_DXCC par bande',
            'unit': 'QSO_pts × (zones_CQ + DXCC)',
        },
        'log_format': 'CABRILLO',
        'log_deadline': '5_days_after',
        'log_submit': 'https://cqww.com/logcheck/',
        'itu_r1_notes': '160m interdit <1810 kHz.',
        'band_change_rule_min': 10,   # même règle M/S que CQ_WW_SSB
    },

    # ── World Wide Award (hamaward.cloud) ──────────────────────────────────
    # PAS un concours classique : les hunters ne marquent des points qu'en
    # contactant l'une des stations spéciales inscrites pour l'édition (ex.
    # II1WWA) — roster public tenu à jour par logx_wwa.py, aucune donnée ici.
    # 'date_rule': 'permanent' explicite ci-dessous (et non une grammaire
    # "Nème weekend du mois", que cette fenêtre fixe ne suit pas) : c'est
    # EXACTEMENT le repli déjà appliqué par calc_contest_date/get_next_
    # contest_date via cdef.get('date_rule', 'permanent') quand la clé est
    # absente (logx_rules.py) — la rendre explicite satisfait le schema
    # (date_rule requis) sans changer le calcul : le calendrier affiche
    # "Permanent", dates à saisir à la main à l'étape FILTRES comme pour un
    # concours personnalisé, sans impact sur le scoring/need-list.
    # Pas de 'duration_h' : ce champ modélise la durée d'une SESSION de
    # concours (24-48h, compte à rebours du coach) — non pertinent pour une
    # fenêtre d'un mois/d'une semaine sans session continue, et rien dans le
    # code ne lit duration_h pour WWA (cdef.get('date_rule') ne matchant
    # jamais un format de date calendaire, le calcul de fin côté client
    # dans logx_configuration.html:serverContestDates() ne s'exécute jamais
    # pour ce concours). Voir 'notes' ci-dessous pour la fenêtre réelle.
    'WWA_2027_JAN': {
        'name': 'World Wide Award — janvier',
        'organizer': 'HamAward (Ham Innovation Group)',
        'check_url': 'https://hamaward.cloud/wwa',
        'rules_url': 'https://hamaward.cloud/wwa/rules',
        'date_rule': 'permanent',
        'start_utc': '00:00',   # fenêtre réelle : 1er → 31 janvier (31 jours)
        'bands': ['3.5','7','10.1','14','18','21','24','28'],
        'modes': ['SSB','CW','FT8','FT4','FT2','RTTY','PSK'],
        'exchange': 'RS/RST (aucun n° de série, règlement §3)',
        'scoring': {
            'type': 'wwa_sprint',
            'multiplier': None,
            'unit': '10pts CW / 5pts SSB / 2pts FT8-FT4-FT2 / 5pts RTTY-PSK, par station spéciale',
            'note': 'Points uniquement si la station travaillée figure au roster WWA de cette édition '
                    '(logx_wwa.py) — sinon 0 pt. 1 QSO valable/jour/bande/mode par station.',
        },
        'log_format': '', 'log_deadline': '', 'log_submit': '',
        'notes': "Award délivré automatiquement par hamaward.cloud (pas de soumission de log). "
                 "LogX AI n'estime le score que localement pour prioriser les contacts — "
                 "le classement officiel reste calculé par la plateforme WWA elle-même.",
    },
    'WWA_2027_JUL': {
        'name': 'World Wide Award — Sprint',
        'organizer': 'HamAward (Ham Innovation Group)',
        'check_url': 'https://hamaward.cloud/wwa',
        'rules_url': 'https://hamaward.cloud/wwa/rules',
        'date_rule': 'permanent',
        'start_utc': '00:00',   # fenêtre réelle : 28 juin → 4 juillet (7 jours)
        'bands': ['3.5','7','10.1','14','18','21','24','28'],
        'modes': ['SSB','CW','FT8','FT4','FT2','RTTY','PSK'],
        'exchange': 'RS/RST (aucun n° de série, règlement §3)',
        'scoring': {
            'type': 'wwa_sprint',
            'multiplier': None,
            'unit': '10pts CW / 5pts SSB / 2pts FT8-FT4-FT2 / 5pts RTTY-PSK, par station spéciale',
            'note': 'Points uniquement si la station travaillée figure au roster WWA de cette édition '
                    '(logx_wwa.py) — sinon 0 pt. 1 QSO valable/jour/bande/mode par station.',
        },
        'log_format': '', 'log_deadline': '', 'log_submit': '',
        'notes': "Award délivré automatiquement par hamaward.cloud (pas de soumission de log). "
                 "LogX AI n'estime le score que localement pour prioriser les contacts — "
                 "le classement officiel reste calculé par la plateforme WWA elle-même.",
    },
    'CQ_WPX_SSB': {
        'name': 'CQ WPX — SSB',
        'organizer': 'CQ Magazine',
        'check_url': 'https://cqwpx.com/',
        'rules_url': 'https://cqwpx.com/rules.htm',
        'date_rule': 'last_full_weekend_march',
        'duration_h': 48, 'start_utc': '00:00',
        'bands': ['1.8','3.5','7','14','21','28'],
        'modes': ['SSB'],
        'exchange': 'RS + N°serie (ex: 59 001)',
        'cabrillo_name': 'CQ-WPX-SSB',
        'cabrillo_exchange': ['rst', 'exch'],
        'scoring': {
            'type': 'prefix_multiplier',
            'points_dx': 3, 'points_same_continent': 1, 'points_same_country': 1,
            'multiplier': 'préfixes_uniques tous_bandes_confondus',
            'unit': 'QSO_pts × préfixes_uniques',
        },
        'log_format': 'CABRILLO', 'log_deadline': '7_days_after',
        'log_submit': 'https://cqwpx.com/logcheck/',
        'band_change_rule_min': 10,   # règle M/S 10 min, identique à CQ WW
    },
    'CQ_WPX_CW': {
        'name': 'CQ WPX — CW',
        'organizer': 'CQ Magazine',
        'check_url': 'https://cqwpx.com/',
        'rules_url': 'https://cqwpx.com/rules.htm',
        'date_rule': 'last_full_weekend_may',
        'duration_h': 48, 'start_utc': '00:00',
        'bands': ['1.8','3.5','7','14','21','28'],
        'modes': ['CW'],
        'exchange': 'RST + N°serie (ex: 599 001)',
        'cabrillo_name': 'CQ-WPX-CW',
        'cabrillo_exchange': ['rst', 'exch'],
        'scoring': {
            'type': 'prefix_multiplier',
            'points_dx': 3, 'points_same_continent': 1, 'points_same_country': 1,
            'multiplier': 'préfixes_uniques tous_bandes_confondus',
            'unit': 'QSO_pts × préfixes_uniques',
        },
        'log_format': 'CABRILLO', 'log_deadline': '7_days_after',
        'log_submit': 'https://cqwpx.com/logcheck/',
        'band_change_rule_min': 10,   # règle M/S 10 min, identique à CQ WW
    },
    'ARRL_DX_SSB': {
        'name': 'ARRL DX — SSB',
        'organizer': 'ARRL',
        'check_url': 'https://www.arrl.org/arrl-dx',
        'rules_url': 'https://www.arrl.org/arrl-dx',
        'date_rule': 'third_full_weekend_march',
        'duration_h': 48, 'start_utc': '00:00',
        'bands': ['1.8','3.5','7','14','21','28'],
        'modes': ['SSB'],
        'exchange': 'RS + état/province (W/VE) ou RS + power (DX)',
        'cabrillo_name': 'ARRL-DX-SSB',
        'cabrillo_exchange': ['rst', 'exch'],
        'scoring': {
            'type': 'power_state',
            'points': 3,
            'multiplier': 'états_US + provinces_Canada par bande',
            'unit': '3pts × états/provinces par bande',
        },
        'log_format': 'CABRILLO', 'log_deadline': '5_days_after',
        'log_submit': 'http://arrl.org/arrl-contest-log-submission',
    },
    'ARRL_DX_CW': {
        'name': 'ARRL DX — CW',
        'organizer': 'ARRL',
        'check_url': 'https://www.arrl.org/arrl-dx',
        'rules_url': 'https://www.arrl.org/arrl-dx',
        'date_rule': 'second_full_weekend_february',
        'duration_h': 48, 'start_utc': '00:00',
        'bands': ['1.8','3.5','7','14','21','28'],
        'modes': ['CW'],
        'exchange': 'RST + état/province (W/VE) ou RST + power (DX)',
        'cabrillo_name': 'ARRL-DX-CW',
        'cabrillo_exchange': ['rst', 'exch'],
        'scoring': {
            'type': 'power_state',
            'points': 3,
            'multiplier': 'états_US + provinces_Canada par bande',
            'unit': '3pts × états/provinces par bande',
        },
        'log_format': 'CABRILLO', 'log_deadline': '5_days_after',
        'log_submit': 'http://arrl.org/arrl-contest-log-submission',
    },
    'ARRL_FD': {
        'name': 'ARRL Field Day',
        'organizer': 'ARRL',
        'check_url': 'https://www.arrl.org/field-day',
        'rules_url': 'https://www.arrl.org/field-day-rules',
        'date_rule': 'last_full_weekend_june',
        'duration_h': 27, 'start_utc': '18:00',
        'bands': ['1.8','3.5','7','14','21','28','50'],
        'modes': ['SSB','CW','FT8','FT4','RTTY'],
        'exchange': '[N°TX][Classe] [Section] — ex: 2A CT | DX: 2A DX',
        'cabrillo_name': 'ARRL-FIELD-DAY',
        'cabrillo_exchange': ['exch'],
        'scoring': {
            'type': 'fd_class',
            'points_phone': 1, 'points_cw': 2, 'points_digital': 2,
            'mult_qrp_non_commercial': 5, 'mult_qrp_commercial': 2,
            'mult_100w': 2, 'mult_hp': 1,
            'unit': 'QSO_pts × mult_puissance + bonus',
            'mult': 'puissance (×1/×2/×5)',
            'bonus': '+100pts/TX alimentation autonome (max 2000) | +100 lieu public | +100 satellite',
        },
        'log_format': 'CABRILLO',
        'log_deadline': 'Mardi 28 juillet (28 days after)',
        'log_submit': 'https://field-day.arrl.org/fdentry.php',
        'categories': 'A=club portable 3+ | B=1-2 pers portable | C=mobile | D=fixe | E=fixe QRP | F=EOC',
        'notes': 'Classe A (3+ pers.) recommandée. 160/80/40/20/15/10m + 50MHz+. Pas 60/30/17/12m.',
    },
    'SOTA': {
        'name': 'Summits on the Air',
        'organizer': 'SOTA',
        'check_url': 'https://www.sota.org.uk',
        'rules_url': 'https://www.sota.org.uk/Joining-In/General-Rules',
        'date_rule': 'permanent',
        'bands': ['all'], 'modes': ['all'],
        'exchange': 'indicatif + référence sommet',
        'scoring': {'type':'summit_points','unit':'pts selon altitude du sommet'},
        'log_format': 'ADIF', 'log_submit': 'https://sota.org.uk',
    },
    'POTA': {
        'name': 'Parks on the Air',
        'organizer': 'POTA',
        'check_url': 'https://parksontheair.com',
        'rules_url': 'https://parksontheair.com/rules/',
        'date_rule': 'permanent',
        'bands': ['all'], 'modes': ['all'],
        'exchange': 'indicatif + référence parc',
        'scoring': {'type':'park_points','unit':'1pt par parc activé'},
        'log_format': 'ADIF', 'log_submit': 'https://pota.app',
    },

    # ════════════════════════════════════════════════════════════
    # EUROPE & MONDE (ajoutés Phase 4 — dates recoupées WA7BNM 2026 ;
    # les barèmes marqués "à confirmer" peuvent être affinés en un clic
    # via 🤖 ANALYSER UN RÈGLEMENT dans la config)
    # ════════════════════════════════════════════════════════════
    'WAEDC_SSB': {
        'name': 'WAE DX Contest — SSB',
        'organizer': 'DARC',
        'check_url': 'https://www.darc.de/der-club/referate/conteste/wae-dx-contest/en/',
        'rules_url': 'https://www.darc.de/der-club/referate/conteste/wae-dx-contest/en/wae-rules/',
        'date_rule': 'second_full_weekend_september',
        'duration_h': 48, 'start_utc': '00:00',
        'bands': ['3.5','7','14','21','28'], 'modes': ['SSB'],
        'exchange': 'RS + N°serie (QTC : heure/indicatif/n°)',
        'cabrillo_name': 'WAE-DC-SSB',
        'cabrillo_exchange': ['rst', 'exch'],
        'scoring': {
            'bricks': {
                'points': [{'when':'always','points':1}],
                'multiplier': {'kind':'zone_dxcc'},
                'validity': 'different_continent',
                'validity_fail_explanation': 'Station {dx_base} en Europe — QSO non valable en WAE (EU↔DX uniquement)',
                'mult_weight_by_band': {'3.5':4, '7':3, '14':2, '21':2, '28':2},
            },
            'unit': '(QSOs + QTCs) × mults pondérés par bande',
            'note': '1 pt émetteur + 1 pt récepteur par QTC transféré — saisie détaillée '
                    'et export Cabrillo via le bouton ✉ QTC du logbook (voir logx_export.build_cabrillo).',
        },
        'log_format': 'CABRILLO', 'log_deadline': '7_days_after',
        'op_time_max_h': 36, 'off_time_min_min': 60, 'qtc': True,
        'notes': 'Europe contacte hors-Europe uniquement. Single-OP : 36 h sur 48. Max 10 QTC par station.',
    },
    'WAEDC_RTTY': {
        'name': 'WAE DX Contest — RTTY',
        'organizer': 'DARC',
        'check_url': 'https://www.darc.de/der-club/referate/conteste/wae-dx-contest/en/',
        'rules_url': 'https://www.darc.de/der-club/referate/conteste/wae-dx-contest/en/wae-rules/',
        'date_rule': 'second_full_weekend_november',
        'duration_h': 48, 'start_utc': '00:00',
        'bands': ['3.5','7','14','21','28'], 'modes': ['RTTY'],
        'exchange': 'RST + N°serie (QTC entre continents différents)',
        'cabrillo_name': 'WAE-DC-RTTY',
        'cabrillo_exchange': ['rst', 'exch'],
        'scoring': {
            'bricks': {
                'points': [{'when':'always','points':1}],
                'multiplier': {'kind':'zone_dxcc'},
                'mult_weight_by_band': {'3.5':4, '7':3, '14':2, '21':2, '28':2},
            },
            'unit': '(QSOs + QTCs) × mults pondérés par bande',
            'note': 'RTTY : pas de restriction continentale sur les QSO (contrairement à CW/SSB). '
                    'QTC uniquement entre continents différents — saisie/export via le bouton ✉ QTC du logbook.',
        },
        'log_format': 'CABRILLO', 'log_deadline': '7_days_after',
        'op_time_max_h': 36, 'off_time_min_min': 60, 'qtc': True,
    },
    'UBA_DX_SSB': {
        'name': 'UBA DX Contest — SSB',
        'organizer': 'UBA',
        'check_url': 'https://www.uba.be/en/hf/contest-rules',
        'rules_url': 'https://www.uba.be/en/hf/contest-rules/uba-dx-contest',
        'date_rule': 'last_full_weekend_january_13h',
        'duration_h': 24, 'start_utc': '13:00',
        'bands': ['3.5','7','14','21','28'], 'modes': ['SSB'],
        'exchange': 'RS + N°serie (stations ON : + province)',
        'scoring': {
            'bricks': {
                'points': [
                    {'prefix_in': ['ON','OO','OP','OQ','OR','OS','OT'], 'points': 10},
                    {'when': 'same_continent', 'points': 3},
                    {'when': 'always', 'points': 1},
                ],
                'multiplier': {'kind': 'zone_dxcc'},
            },
            'unit': 'pts × (provinces belges + préfixes ON + pays EU)',
            'note': 'Multiplicateurs réels : provinces belges + préfixes ON + pays EU par bande — approximés par zone/DXCC.',
        },
        'log_format': 'CABRILLO', 'log_deadline': 'second_monday_after',
        'notes': 'Stations belges = 10 pts, gros trafic ON garanti.',
    },
    'UBA_DX_CW': {
        'name': 'UBA DX Contest — CW',
        'organizer': 'UBA',
        'check_url': 'https://www.uba.be/en/hf/contest-rules',
        'rules_url': 'https://www.uba.be/en/hf/contest-rules/uba-dx-contest',
        'date_rule': 'last_full_weekend_february_13h',
        'duration_h': 24, 'start_utc': '13:00',
        'bands': ['3.5','7','14','21','28'], 'modes': ['CW'],
        'exchange': 'RST + N°serie (stations ON : + province)',
        'scoring': {
            'bricks': {
                'points': [
                    {'prefix_in': ['ON','OO','OP','OQ','OR','OS','OT'], 'points': 10},
                    {'when': 'same_continent', 'points': 3},
                    {'when': 'always', 'points': 1},
                ],
                'multiplier': {'kind': 'zone_dxcc'},
            },
            'unit': 'pts × (provinces belges + préfixes ON + pays EU)',
        },
        'log_format': 'CABRILLO', 'log_deadline': 'second_monday_after',
    },
    'EU_HF_CHAMP': {
        # Recoupé le 16/07/2026 avec le PDF officiel 2026 (règles mises à jour
        # le 30/06/2026) via 🤖 ANALYSER UN RÈGLEMENT — anciennes URLs lea.hamradio.si en 404.
        'name': 'European HF Championship',
        'organizer': 'Slovenia Contest Club',
        'check_url': 'https://euhf.s5cc.eu/',
        'rules_url': 'https://euhf.s5cc.eu/rules/euhfc_rules_latest.pdf',
        'date_rule': 'first_saturday_august_12h',
        'duration_h': 12, 'start_utc': '12:00',
        'bands': ['1.8','3.5','7','14','21','28'], 'modes': ['SSB','CW'],
        'exchange': 'RS(T) + 2 derniers chiffres de l\'année de 1re licence de l\'opérateur',
        'scoring': {
            'bricks': {
                'points': [{'when':'always','points':1}],
                'validity': 'is_eu',
                'validity_fail_explanation': 'Station {dx_base} hors Europe — seuls les QSO avec l\'Europe comptent en EUHFC',
                'multiplier': {'kind': 'exchange_distinct'},
            },
            'unit': 'QSO × années de 1re licence distinctes par bande',
            'note': 'Multiplicateur = nombres à 2 chiffres distincts reçus en échange, une fois par bande '
                    'tous modes confondus — inconnaissable au spot, décompte exact sur le log (coach).',
        },
        'log_format': 'CABRILLO', 'log_deadline': '48_hours_after',
        'notes': 'Concours européen — 12 h intenses (12:00–24:00 UTC), une seule journée. Single-Op uniquement. '
                 'Self-spotting autorisé (règles 2026). Max 10 changements bande/mode par heure (sauf cat. UNLIMITED). '
                 'Log sous 48 h (lundi 23h59 UTC), upload web uniquement.',
    },
    'RUSSIAN_DX': {
        'name': 'Russian DX Contest',
        'organizer': 'SRR',
        'check_url': 'https://www.rdxc.org',
        'rules_url': 'https://www.rdxc.org/asp/pages/rulesg.asp',
        'date_rule': 'third_saturday_march_12h',
        'duration_h': 24, 'start_utc': '12:00',
        'bands': ['1.8','3.5','7','14','21','28'], 'modes': ['SSB','CW'],
        'exchange': 'RS(T) + N°serie (stations russes : + oblast 2 lettres)',
        'scoring': {
            'bricks': {
                'points': [
                    {'prefix_in': ['R','UA','UB','UC','UD','UE','UF','UG','UH','UI'], 'points': 10},
                    {'when': 'same_country', 'points': 2},
                    {'when': 'same_continent', 'points': 3},
                    {'when': 'always', 'points': 5},
                ],
                'multiplier': {'kind': 'zone_dxcc'},
            },
            'unit': 'pts × (oblasts + DXCC) par bande',
        },
        'log_format': 'CABRILLO', 'log_deadline': '14 jours',
        'notes': 'Stations russes = 10 pts. Mults réels : oblasts + pays DXCC par bande.',
    },
    'SP_DX': {
        'name': 'SP DX Contest',
        'organizer': 'PZK (Pologne)',
        'check_url': 'https://spdxcontest.pzk.org.pl',
        'rules_url': 'https://spdxcontest.pzk.org.pl',
        'date_rule': 'first_full_weekend_april',
        'duration_h': 24, 'start_utc': '15:00',
        'bands': ['1.8','3.5','7','14','21','28'], 'modes': ['SSB','CW'],
        'exchange': 'RS(T) + N°serie (stations SP : + province 1 lettre)',
        'scoring': {
            'bricks': {
                'points': [{'when':'always','points':3}],
                'multiplier': {'kind':'zone_dxcc'},
                'validity': {'prefix_in': ['SP','SQ','SN','SO','SR','HF','3Z']},
                'validity_fail_explanation': 'Station {dx_base} hors Pologne — seuls les contacts SP comptent',
            },
            'unit': '3 pts × provinces SP par bande',
            'note': 'Hors Pologne : seuls les QSO avec des stations SP comptent. Mults réels : 16 provinces polonaises.',
        },
        'log_format': 'CABRILLO', 'log_deadline': '7_days_after',
    },
    'HA_DX': {
        'name': 'HA DX Contest',
        'organizer': 'MRASZ (Hongrie)',
        'check_url': 'https://ha-dx.com',
        'rules_url': 'https://ha-dx.com/en/contest-rules',
        'date_rule': 'third_full_weekend_january',
        'duration_h': 24, 'start_utc': '12:00',
        'bands': ['1.8','3.5','7','14','21','28'], 'modes': ['SSB','CW'],
        'exchange': 'RS(T) + N°serie (stations HA : + comté 2 lettres)',
        'scoring': {
            'bricks': {
                'points': [
                    {'prefix_in': ['HA','HG'], 'points': 6},
                    {'when': 'same_continent', 'points': 1},
                    {'when': 'always', 'points': 3},
                ],
                'multiplier': {'kind': 'zone_dxcc'},
            },
            'unit': 'pts × (comtés HA + DXCC) par bande',
            'note': 'Barème approximatif — à confirmer via 🤖 analyse du règlement.',
        },
        'log_format': 'CABRILLO', 'log_deadline': '7_days_after',
    },
    'ALL_ASIAN_CW': {
        'name': 'All Asian DX Contest — CW',
        'organizer': 'JARL',
        'check_url': 'https://www.jarl.org/English/4_Library/A-4-3_Contests/AA_rule.htm',
        'rules_url': 'https://www.jarl.org/English/4_Library/A-4-3_Contests/AA_rule.htm',
        'date_rule': 'third_saturday_june_00h',
        'duration_h': 48, 'start_utc': '00:00',
        'bands': ['1.8','3.5','7','14','21','28'], 'modes': ['CW'],
        'exchange': 'RST + âge de l\'opérateur (YL : 00)',
        'scoring': {
            'bricks': {
                'points': [
                    {'bands': ['1.8'], 'points': 3},
                    {'bands': ['3.5'], 'points': 2},
                    {'when': 'always', 'points': 1},
                ],
                'multiplier': {'kind': 'prefix'},
                'validity': 'is_asia',
                'validity_fail_explanation': 'Station {dx_base} hors Asie — seuls les contacts asiatiques comptent',
            },
            'unit': 'pts × préfixes asiatiques par bande',
        },
        'log_format': 'CABRILLO', 'log_deadline': '30 jours',
        'notes': 'Échange original : l\'âge de l\'opérateur. Bandes basses bonifiées.',
    },
    'ALL_ASIAN_SSB': {
        'name': 'All Asian DX Contest — SSB',
        'organizer': 'JARL',
        'check_url': 'https://www.jarl.org/English/4_Library/A-4-3_Contests/AA_rule.htm',
        'rules_url': 'https://www.jarl.org/English/4_Library/A-4-3_Contests/AA_rule.htm',
        'date_rule': 'first_full_weekend_september',
        'duration_h': 48, 'start_utc': '00:00',
        'bands': ['3.5','7','14','21','28'], 'modes': ['SSB'],
        'exchange': 'RS + âge de l\'opérateur (YL : 00)',
        'scoring': {
            'bricks': {
                'points': [
                    {'bands': ['3.5'], 'points': 2},
                    {'when': 'always', 'points': 1},
                ],
                'multiplier': {'kind': 'prefix'},
                'validity': 'is_asia',
                'validity_fail_explanation': 'Station {dx_base} hors Asie — seuls les contacts asiatiques comptent',
            },
            'unit': 'pts × préfixes asiatiques par bande',
        },
        'log_format': 'CABRILLO', 'log_deadline': '30 jours',
    },
    'STEW_PERRY': {
        'name': 'Stew Perry Topband Challenge',
        'organizer': 'Boring ARC',
        'check_url': 'https://www.kkn.net/stew/',
        'rules_url': 'https://www.kkn.net/stew/',
        'date_rule': 'third_saturday_december_15h',
        'duration_h': 24, 'start_utc': '15:00',
        'bands': ['1.8'], 'modes': ['CW'],
        'exchange': 'grand carré locator (4 caractères)',
        'scoring': {
            'bricks': {
                'points': [{'when':'always','points':'per_km'}],
                'multiplier': None,
                'priority_thresholds': [[3000,1],[1500,2],[500,3]],
                'priority_default': 4,
                'explain_direct': '{dist_km} km sur 160m — pts selon distance entre carrés',
            },
            'unit': 'pts par distance (1 pt + 1/500 km)',
            'note': 'Barème réel : 1 pt + 1 par tranche de 500 km entre grands carrés — le classement par distance du moteur reste correct.',
        },
        'log_format': 'CABRILLO', 'log_deadline': '14 jours',
        'notes': 'Édition principale en décembre ; échauffements (Pre-Stew) en mars/juin/octobre. 100% 160m.',
    },
    'ARRL_10M': {
        'name': 'ARRL 10-Meter Contest',
        'organizer': 'ARRL',
        'check_url': 'https://www.arrl.org/10-meter',
        'rules_url': 'https://www.arrl.org/10-meter',
        'date_rule': 'second_full_weekend_december',
        'duration_h': 48, 'start_utc': '00:00',
        'bands': ['28'], 'modes': ['SSB','CW'],
        'exchange': 'RS(T) + état/province (W/VE) ou N°serie',
        'cabrillo_name': 'ARRL-10-METER',
        'cabrillo_exchange': ['rst', 'exch'],
        'scoring': {
            'bricks': {
                'points': [
                    {'modes': ['CW'], 'points': 4},
                    {'when': 'always', 'points': 2},
                ],
                'multiplier': {'kind':'zone_dxcc'},
            },
            'unit': 'pts × (états + provinces + DXCC)',
            'note': 'CW = 4 pts, SSB = 2 pts. Au spot (mode inconnu) le moteur compte 2 pts ; le logbook applique le vrai barème.',
        },
        'log_format': 'CABRILLO', 'log_deadline': '7_days_after',
        'notes': '100% 28 MHz — dépend fortement de la propagation F2/Es.',
    },
    'ARRL_160M': {
        'name': 'ARRL 160-Meter Contest',
        'organizer': 'ARRL',
        'check_url': 'https://www.arrl.org/160-meter',
        'rules_url': 'https://www.arrl.org/160-meter',
        'date_rule': 'first_saturday_december_22h',
        'duration_h': 42, 'start_utc': '22:00',
        'bands': ['1.8'], 'modes': ['CW'],
        'exchange': 'RST (+ section ARRL pour W/VE)',
        'cabrillo_name': 'ARRL-160-METER',
        'cabrillo_exchange': ['rst', 'exch'],
        'scoring': {
            'bricks': {
                'points': [{'when':'always','points':5}],
                'multiplier': {'kind':'na_section'},
                'validity': 'is_na',
                'validity_fail_explanation': 'Station {dx_base} hors W/VE — seuls les contacts W/VE comptent (DX)',
            },
            'unit': '5 pts × sections ARRL',
        },
        'log_format': 'CABRILLO', 'log_deadline': '7_days_after',
        'notes': 'ATTENTION : départ réel le VENDREDI 22:00 UTC (la date affichée est le samedi — grammaire de dates limitée au sam/dim).',
    },

    # ── CWops (CW Operators' Club) ────────────────────────────────────────────
    # Mini-test hebdomadaire de 60 min, 4 sessions/semaine (mer+jeu UTC) — AUCUNE
    # grammaire date_rule existante ne sait exprimer une récurrence hebdomadaire
    # (seulement 'permanent' ou 'Nème {samedi|dimanche} du mois' ou 'Nème weekend
    # complet du mois' — cf. contest_schema.json). Même repli que WWA_2027_JAN/
    # JUL plus haut : 'permanent' explicite + horaire réel documenté en 'notes'.
    # duration_h=1 reste pertinent ici (contrairement à WWA) car chaque SESSION
    # individuelle dure réellement 60 min.
    # Règles vérifiées le 25/07/2026 par fetch direct de cwops.org/cwops-tests/,
    # recoupé par une recherche web indépendante (jours/heures, bandes, exchange,
    # scoring concordants sur les deux sources).
    'CWOPS_CWT': {
        'name': 'CWops Mini-Test (CWT)',
        'organizer': "CWops (CW Operators' Club)",
        'check_url': 'https://cwops.org/cwops-tests/',
        'rules_url': 'https://cwops.org/cwops-tests/',
        'date_rule': 'permanent',
        'start_utc': '13:00',   # 1re des 4 sessions seulement — horaire complet réel en 'notes'
        'bands': ['1.8','3.5','7','14','21','28'], 'modes': ['CW'],
        'exchange': "Prénom + N° membre CWops (non-membres : prénom + état/province ou indicatif "
                    'pays DXCC ; étudiants CW Academy : prénom + "CWA")',
        'scoring': {
            'bricks': {
                'points': [{'when': 'always', 'points': 1}],
                'multiplier': {'kind': 'exchange_distinct'},
            },
            'unit': '1 pt/QSO (1x par bande) × indicatifs uniques travaillés',
            'note': "Multiplicateur réel = nombre d'indicatifs UNIQUES travaillés sur toute la session "
                    "(pas par bande) — exchange_distinct est l'approximation la plus proche disponible "
                    "dans le moteur à briques (compte par bande) ; décompte exact fait sur le log (coach).",
        },
        'log_format': '', 'log_deadline': '48_hours_after',
        'log_submit': 'https://www.3830scores.com/',
        'categories': "Toutes catégories (QRP/LP/HP), ouvert aux non-membres — pas de restriction de participation",
        'notes': "4 sessions hebdomadaires de 60 min : mercredi 13h00-14h00 UTC, mercredi 19h00-20h00 UTC, "
                 "jeudi 03h00-04h00 UTC, jeudi 07h00-08h00 UTC (horaire réel — 'permanent' ci-dessus est un "
                 "repli technique de date_rule, pas la vraie règle). Pas de log Cabrillo formel à soumettre : "
                 "simple claim de score par session sur 3830scores.com (une session = un formulaire séparé, "
                 "identifié CWT-1300/CWT-1900/CWT-0300/CWT-0700). Bandes non-WARC uniquement (pas de 30/17/12m).",
    },

    # ── UFT — Challenges saisonniers (hiver / été) ────────────────────────────
    # Distincts de UFT_RENCONTRES (1er weekend complet de décembre — présent
    # seulement dans CONTEST_SCORING legacy, pas ici) : ce sont des défis
    # d'ACTIVITÉ CUMULATIVE sur plusieurs semaines, pas une session continue —
    # même situation que WWA_2027_* : 'permanent' (fenêtre réelle en 'notes'),
    # aucune grammaire date_rule ne sachant exprimer "1er juillet→31 août" ni
    # "1er dimanche de février→dimanche suivant", et duration_h (max 48h dans
    # le schéma) ne peut de toute façon pas encoder plusieurs semaines.
    # Sources : pages officielles uft.net (fetch direct le 25/07/2026). Cf.
    # HYPOTHÈSES explicites en 'notes'/'scoring.note' pour ce qui n'a PAS pu
    # être confirmé avec certitude (barème point-par-bande complet, mode exact
    # autorisé) — pages sans tableau exploitable ni PDF de règlement trouvé.
    'UFT_CHALLENGE_ETE': {
        'name': "Challenge d'été F5CED",
        'organizer': 'UFT',
        'check_url': 'https://www.uft.net/activites-et-concours/challenge-dete-f5ced/',
        'rules_url': 'https://www.uft.net/activites-et-concours/challenge-dete-f5ced/',
        'date_rule': 'permanent',
        'start_utc': '00:00',   # fenêtre réelle : 1er juillet → 31 août (62 jours), 00h00→23h59 UTC
        'bands': ['1.8','3.5','7','10.1','14','18','21','24','28','50','144'],
        'modes': ['CW'],
        'exchange': "RST (pas d'échange contest formel — trafic normal/rondes/skeds comptabilisé ; "
                    "l'UFT recoupe le statut membre/non-membre sur le log soumis, pas via un code transmis)",
        'scoring': {
            'bricks': {
                'points': [
                    {'prefix_in': ['F8UFT'], 'points': 4},
                    {'when': 'different_continent', 'points': 4},
                    {'when': 'always', 'points': 2},
                ],
                'multiplier': None,
            },
            'unit': 'pts variables par bande × distance, doublés sur QSO avec F8UFT',
            'note': "HYPOTHÈSE — barème complet non confirmé avec certitude (page web sans tableau "
                    "exploitable, pas de PDF de règlement trouvé). Ancres réelles relevées sur uft.net : "
                    "3,5MHz Europe-Europe = 2 pts, 1,8MHz Europe-DX autre continent = 6 pts ; le vrai "
                    "barème croît sur les bandes basses et selon la distance/le continent. Les valeurs "
                    "2/4 ci-dessus sont une APPROXIMATION prudente pour la priorisation du coach — PAS le "
                    "score officiel. Règle confirmée et modélisée fidèlement : tout QSO avec F8UFT double "
                    "les points.",
        },
        'log_format': 'CABRILLO', 'log_deadline': '8_days_after',
        'log_submit': 'commission-concours@uft.net',
        'notes': "Défi d'activité cumulatif du 1er juillet au 31 août, PAS une session continue. Mode CW "
                 "supposé par analogie avec la vocation de l'UFT et les autres entrées UFT de cette base "
                 "(F9NL, UFT_RENCONTRES) — NON re-confirmé mot pour mot sur cette page précise (le texte "
                 "dit seulement 'tous les QSO sont autorisés'), À VÉRIFIER avant tout usage compétitif "
                 "sérieux. Bandes déduites du tableau de scoring du règlement ('1,8 / 3,5 à 10 / 14 à 28 / "
                 "50 / 144 / 432 et plus MHz') — plage large, pas de restriction de bande annoncée.",
    },
    'UFT_CHALLENGE_HIVER': {
        'name': "Challenge d'hiver UFT",
        'organizer': 'UFT',
        'check_url': 'https://www.uft.net/activites-et-concours/challenge-dhiver-uft/',
        'rules_url': 'https://www.uft.net/activites-et-concours/challenge-dhiver-uft/',
        'date_rule': 'permanent',
        'start_utc': '00:00',   # fenêtre réelle 2026 : dim. 1er février 00h00 → dim. 8 février 23h59 UTC (8 j.)
        'bands': ['1.8','3.5','7','10.1','14','18','21','24','28','50','144'],
        'modes': ['CW'],
        'exchange': "RST (pas d'échange contest formel — trafic normal/rondes/skeds comptabilisé ; "
                    "l'UFT recoupe le statut membre/non-membre sur le log soumis, pas via un code transmis)",
        'scoring': {
            'bricks': {
                'points': [
                    {'prefix_in': ['F8UFT'], 'points': 4},
                    {'when': 'different_continent', 'points': 4},
                    {'when': 'always', 'points': 2},
                ],
                'multiplier': None,
            },
            'unit': 'pts variables par bande × distance (2-10 même continent / 3-15 autre continent selon '
                    'la bande), doublés sur QSO avec F8UFT',
            'note': "HYPOTHÈSE — barème complet non confirmé avec certitude (page web sans tableau "
                    "exploitable, pas de PDF de règlement trouvé). Plage annoncée sur uft.net : 2 à 10 pts "
                    "même continent, 3 à 15 pts autre continent selon la bande (1,8→432MHz). Les valeurs "
                    "2/4 ci-dessus sont une APPROXIMATION prudente pour la priorisation du coach — PAS le "
                    "score officiel. Règle confirmée et modélisée fidèlement : tout QSO avec F8UFT double "
                    "les points.",
        },
        'log_format': 'CABRILLO', 'log_deadline': '8_days_after',
        'log_submit': 'commission-concours@uft.net',
        'notes': "Défi d'activité cumulatif sur 8 jours (chaque année en février ; 2026 : dimanche 1er → "
                 "dimanche 8 février, 00h00→23h59 UTC), PAS une session continue. Mode CW supposé par "
                 "analogie avec la vocation de l'UFT et les autres entrées UFT de cette base (F9NL, "
                 "UFT_RENCONTRES) — NON re-confirmé mot pour mot sur cette page précise, À VÉRIFIER avant "
                 "tout usage compétitif sérieux. Bandes déduites du tableau de scoring du règlement "
                 "('1,8 / 3,5 à 10 / 14 à 28 / 50 / 144 / 432 et plus MHz'). Logiciel dédié fourni par "
                 "l'UFT (génère aussi un export ADIF) en plus du format Cabrillo standard.",
    },
}

# ─── CONCOURS PERSONNALISÉS (extraction IA + relecture humaine, Phase 3) ─────
CUSTOM_CONTESTS_FILE = 'custom_contests.json'
CUSTOM_CONTEST_IDS = set()   # ids issus de custom_contests.json (pour badges UI)

def load_custom_contests():
    """Fusionne les concours validés par relecture humaine dans la base.
    Appelé au chargement du module — la base fusionnée est ensuite vue par
    tout le monde (calendrier, scoring, prompts) sans traitement spécial."""
    try:
        if not os.path.exists(CUSTOM_CONTESTS_FILE):
            return
        with open(CUSTOM_CONTESTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for cid, entry in data.items():
            cdef = entry.get('definition', entry)  # tolère les 2 formats
            CONTEST_DEFINITIONS[cid] = cdef
            CUSTOM_CONTEST_IDS.add(cid)
        if CUSTOM_CONTEST_IDS:
            print(f"[CUSTOM] {len(CUSTOM_CONTEST_IDS)} concours personnalisés chargés "
                  f"depuis {CUSTOM_CONTESTS_FILE}")
    except Exception as e:
        print(f"[CUSTOM] Erreur chargement {CUSTOM_CONTESTS_FILE}: {e}")

def save_custom_contest(cid, definition, meta=None):
    """Enregistre un concours validé (relecture humaine faite) dans le fichier
    et la base en mémoire. Refuse d'écraser un concours de la base codée.
    Retourne (ok, message)."""
    if cid in CONTEST_DEFINITIONS and cid not in CUSTOM_CONTEST_IDS:
        return False, f"'{cid}' existe déjà dans la base intégrée — choisis un autre id"
    data = {}
    try:
        if os.path.exists(CUSTOM_CONTESTS_FILE):
            with open(CUSTOM_CONTESTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
    except Exception:
        data = {}
    data[cid] = {'definition': definition, **(meta or {})}
    from logx_storage import save_json_atomic
    save_json_atomic(CUSTOM_CONTESTS_FILE, data)
    CONTEST_DEFINITIONS[cid] = definition
    CUSTOM_CONTEST_IDS.add(cid)
    print(f"[CUSTOM] Concours '{cid}' enregistré ({definition.get('name','')})")
    return True, f"Concours '{cid}' enregistré"

def delete_custom_contest(cid):
    """Supprime un concours personnalisé (jamais un concours intégré)."""
    if cid not in CUSTOM_CONTEST_IDS:
        return False, f"'{cid}' n'est pas un concours personnalisé"
    try:
        data = {}
        if os.path.exists(CUSTOM_CONTESTS_FILE):
            with open(CUSTOM_CONTESTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        data.pop(cid, None)
        from logx_storage import save_json_atomic
        save_json_atomic(CUSTOM_CONTESTS_FILE, data)
    except Exception as e:
        return False, f"Erreur fichier : {e}"
    CONTEST_DEFINITIONS.pop(cid, None)
    CUSTOM_CONTEST_IDS.discard(cid)
    return True, f"Concours '{cid}' supprimé"

load_custom_contests()

# ─── SCORING PAR CONCOURS ────────────────────────────────────────────────────
CONTEST_SCORING = {
    # ── REF 2026 ──────────────────────────────────────────────────────────────
    'REF_CHALLENGE_THF': {'type':'km_x_loc','unit':'1pt/km x locators (cumulatif annuel)','mult':'locators','bands':'144MHz-47GHz','modes':'SSB CW FM DIGI'},
    'REF_CCD_JAN1':  {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'432 1296 2320MHz','modes':'SSB CW FM'},
    'REF_CCD_JAN2':  {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'144MHz','modes':'SSB CW FM'},
    'REF_CDF_HF_CW': {'type':'dept_dxcc','unit':'pts x depts + DXCC','mult':'depts+DXCC','bands':'3.5 7 14 21 28MHz','modes':'CW'},
    'REF_CCD_FEV1':  {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'432 1296 2320MHz','modes':'SSB CW FM'},
    'REF_CCD_FEV2':  {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'144MHz','modes':'SSB CW FM'},
    'REF_CDF_HF_SSB':{'type':'dept_dxcc','unit':'pts x depts + DXCC','mult':'depts+DXCC','bands':'3.5 7 14 21 28MHz','modes':'SSB'},
    'REF_NAT_THF':   {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'144MHz-47GHz','modes':'SSB CW FM'},
    'REF_CCD_MAR':   {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'144MHz','modes':'SSB CW FM'},
    'REF_NAT_TVA':   {'type':'tva','unit':'pts x relais TVA','mult':'relais TVA','bands':'438MHz+ TVA','modes':'FM ATV'},
    'REF_CCD_AVR_CW':{'type':'km_x_loc','unit':'1pt/km x locators CW','mult':'locators','bands':'144MHz','modes':'CW'},
    'REF_PRINTEMPS': {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'144MHz-47GHz','modes':'SSB CW FM'},
    'REF_CCD_MAI':   {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'432 1296 2320MHz','modes':'SSB CW FM'},
    'REF_CDF_THF':   {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'144MHz-47GHz','modes':'SSB CW FM'},
    'REF_IARU_TVA':  {'type':'tva','unit':'pts x relais TVA','mult':'relais TVA','bands':'438MHz+ TVA','modes':'FM ATV'},
    'REF_DDFM_50':   {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'50MHz','modes':'SSB CW FM'},
    'REF_IARU_50':   {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'50MHz','modes':'SSB CW'},
    'REF_RPH':       {'type':'km','unit':'1pt/km SANS multiplicateur - SSB uniquement','mult':'none','bands':'144MHz-47GHz','modes':'SSB'},
    'REF_QRP':       {'type':'km_x_loc','unit':'1pt/km x locators - QRP 5W max','mult':'locators','bands':'144MHz-47GHz','modes':'SSB CW'},
    'REF_ETE':       {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'144MHz-47GHz','modes':'SSB CW FM'},
    'REF_F8TD':      {'type':'km_x_loc','unit':'1pt/km x locators SHF','mult':'locators','bands':'1296MHz-47GHz','modes':'SSB CW'},
    'REF_IARU_VHF':  {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'144MHz','modes':'SSB CW'},
    'REF_CDF_TVA':   {'type':'tva','unit':'pts x relais TVA','mult':'relais TVA','bands':'438MHz+ TVA','modes':'FM ATV'},
    'REF_IARU_UHF':  {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'432MHz-47GHz','modes':'SSB CW'},
    'REF_CCD_OCT':   {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'432 1296 2320MHz','modes':'SSB CW FM'},
    'REF_MARCONI':   {'type':'km_x_loc','unit':'1pt/km x locators CW','mult':'locators','bands':'144MHz','modes':'CW'},
    'REF_160M':      {'type':'dept_dxcc','unit':'pts x depts francais + DXCC','mult':'depts+DXCC','bands':'1.8MHz','modes':'SSB CW'},
    'REF_CCD_NOV':   {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'144MHz','modes':'SSB CW FM'},
    'REF_CCD_DEC':   {'type':'km_x_loc','unit':'1pt/km x locators','mult':'locators','bands':'144MHz','modes':'SSB CW FM'},
    'REF_CCD_DEC_CW':{'type':'km_x_loc','unit':'1pt/km x locators CW','mult':'locators','bands':'144MHz','modes':'CW'},
    'REF_NAT_TVA_DEC':{'type':'tva','unit':'pts x relais TVA','mult':'relais TVA','bands':'438MHz+ TVA','modes':'FM ATV'},
    # ── Autres francais ───────────────────────────────────────────────────────
    'F9NL':           {'type':'dept_dxcc','unit':'pts x depts + DXCC CW','mult':'depts+DXCC','bands':'HF','modes':'CW'},
    'UFT_RENCONTRES': {'type':'dept','unit':'pts x depts CW','mult':'depts','bands':'HF','modes':'CW'},
    # ── Internationaux ────────────────────────────────────────────────────────
    'CQ_WW_SSB':  {
        'type':'zone_country',
        'unit':'3pts (DX continent) / 1pt (même continent diff pays) / 0pt (même pays) × zones CQ × pays DXCC PAR BANDE',
        'mult':'zones_CQ + pays_DXCC par bande',
        'bands':'1.8 3.5 7 14 21 28MHz',
        'modes':'SSB',
        'exchange':'RS + zone CQ (ex: 59 14)',
        'dates_2026':'SSB: 24-25 octobre 2026 00h00-23h59 UTC',
        'log_format':'CABRILLO',
        'deadline':'5 jours après le contest',
        'categories':'SO-HP(1500W) SO-LP(100W) SO-QRP(5W) SO-Assisted MS M2 MM',
        'notes':'ITU R1: pas de TX >7200kHz en 40m SSB. Pas de TX <1810kHz en 160m. Auto-spoting interdit en SO.',
        'url':'https://cqww.com/rules.htm',
    },
    'CQ_WW_CW':   {
        'type':'zone_country',
        'unit':'3pts (DX continent) / 1pt (même continent diff pays) / 0pt (même pays) × zones CQ × pays DXCC PAR BANDE',
        'mult':'zones_CQ + pays_DXCC par bande',
        'bands':'1.8 3.5 7 14 21 28MHz',
        'modes':'CW',
        'exchange':'RST + zone CQ (ex: 599 14)',
        'dates_2026':'CW: 28-29 novembre 2026 00h00-23h59 UTC',
        'log_format':'CABRILLO',
        'deadline':'5 jours après le contest',
        'categories':'SO-HP(1500W) SO-LP(100W) SO-QRP(5W) SO-Assisted MS M2 MM',
        'notes':'ITU R1: pas de TX <1810kHz en 160m. Auto-spotting interdit en SO.',
        'url':'https://cqww.com/rules.htm',
    },
    'CQ_WPX_SSB': {'type':'prefix','unit':'pts x prefixes uniques','mult':'prefixes','bands':'HF','modes':'SSB'},
    'CQ_WPX_CW':  {'type':'prefix','unit':'pts x prefixes uniques','mult':'prefixes','bands':'HF','modes':'CW'},
    'ARRL_DX_SSB':{'type':'power','unit':'3pts x etats/provinces US-Canada','mult':'states','bands':'HF','modes':'SSB'},
    'ARRL_DX_CW': {'type':'power','unit':'3pts x etats/provinces US-Canada','mult':'states','bands':'HF','modes':'CW'},
    'ARRL_FD':    {'type':'fd_class','unit':'QSO_pts × mult_puissance + bonus','mult':'puissance ×1/×2/×5','bands':'HF+50MHz','modes':'SSB/CW/Digital'},
    'SOTA':        {'type':'summit','unit':'pts sommets actives/chasses','mult':'none','bands':'Toutes','modes':'Tous'},
    'POTA':        {'type':'park','unit':'pts parcs actives/chasses','mult':'none','bands':'Toutes','modes':'Tous'},
    'CUSTOM':      {'type':'custom','unit':'a definir','mult':'custom','bands':'Au choix','modes':'Au choix'},
}


def get_scoring_info(contest_id):
    """Résumé de scoring pour un concours, à utiliser par logx_prompts.py
    (remplace CONTEST_SCORING.get(contest, CONTEST_SCORING['CUSTOM'])).

    CONTEST_SCORING ci-dessus est une table LEGACY écrite à la main qui ne
    couvre que 18 des 40 concours de CONTEST_DEFINITIONS — chaque concours
    manquant retombait sur CONTEST_SCORING['CUSTOM'] ('a definir'/'custom'),
    silencieusement transmis à l'IA comme si c'était la vraie règle. Chaque
    entrée de CONTEST_DEFINITIONS porte pourtant déjà un dict 'scoring' à
    jour : on le préfère désormais dès que CONTEST_SCORING ne connaît pas
    l'id, au lieu de retomber sur CUSTOM.

    logx_prompts.py n'utilise que les clés 'unit' et 'mult' du résultat :
    ce sont donc les deux seules clés dont l'absence doit être couverte par
    un repli explicite ici — le format réel des dicts 'scoring' de
    CONTEST_DEFINITIONS n'étant pas garanti homogène (ex. CQ_WW_SSB y
    expose 'multiplier', pas 'mult'), on lit ces clés telles quelles au
    lieu de supposer une structure non vérifiée.
    """
    if contest_id in CONTEST_SCORING:
        return CONTEST_SCORING[contest_id]
    cdef = CONTEST_DEFINITIONS.get(contest_id) or {}
    sc = cdef.get('scoring') or {}
    if sc:
        return {
            'type': sc.get('type', 'custom'),
            'unit': sc.get('unit', sc.get('note', 'voir règlement')),
            'mult': sc.get('mult') or sc.get('multiplier') or 'voir règlement',
            'bands': sc.get('bands', ' '.join(cdef.get('bands', [])) or 'Au choix'),
            'modes': sc.get('modes', ' '.join(cdef.get('modes', [])) or 'Au choix'),
        }
    return CONTEST_SCORING['CUSTOM']


# ─── MODULE 3 : RÈGLEMENT PDF REF (Lecture automatique) ─────────────────────
CONTEST_RULES_URLS = {
    'REF_RPH':       'https://concours.r-e-f.org/reglements/actuels/reg_rph_fr_20250312.pdf',
    'REF_NAT_THF':   'https://concours.r-e-f.org/reglements/actuels/reg_natthf_fr_20250312.pdf',
    'REF_PRINTEMPS': 'https://concours.r-e-f.org/reglements/actuels/reg_printemps_fr_20250312.pdf',
    'REF_ETE':       'https://concours.r-e-f.org/reglements/actuels/reg_ete_fr_20250312.pdf',
    'REF_CDF_THF':   'https://concours.r-e-f.org/reglements/actuels/reg_cdfthf_fr_20251222.pdf',
    'REF_IARU_VHF':  'https://concours.r-e-f.org/reglements/actuels/reg_iaruvhf_fr_20250312.pdf',
    'REF_IARU_UHF':  'https://concours.r-e-f.org/reglements/actuels/reg_iaruuhf_fr_20250312.pdf',
    'REF_QRP':       'https://concours.r-e-f.org/reglements/actuels/reg_qrp_fr_20250312.pdf',
    'REF_160M':      'https://concours.r-e-f.org/reglements/actuels/reg_ref160_fr_20250312.pdf',
    'REF_CCD_JAN1':  'https://concours.r-e-f.org/reglements/actuels/reg_ccdthf_fr_20260429.pdf',
    'REF_MARCONI':   'https://concours.r-e-f.org/reglements/actuels/reg_marconi_fr_20250312.pdf',
    'REF_DDFM_50':   'https://concours.r-e-f.org/reglements/actuels/reg_ddfm50_fr_20250312.pdf',
}
