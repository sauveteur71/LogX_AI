# -*- coding: utf-8 -*-
"""Construction des prompts système pour le copilote IA (contexte concours + contexte terrain)."""

import re

import logx_rules as rules
from logx_bands import dx_threshold_km, band_spotter_km
from logx_rules import calc_contest_date
from logx_definitions import CONTEST_DEFINITIONS, CONTEST_SCORING
from logx_utils import CURRENT_YEAR, locator_to_latlon, haversine
from logx_storage import shared_log

# ─── GÉNÉRATION DU SYSTÈME PROMPT ────────────────────────────────────────────
def build_system_prompt(cfg):
    call     = cfg.get('callsign', 'STATION')
    call_c   = cfg.get('callsign_contest', call)
    loc      = cfg.get('locator', 'JN00AA')
    city     = cfg.get('city', '')
    power    = cfg.get('power', '100')
    record   = cfg.get('record_dx', '0')
    contest  = cfg.get('contest', 'CUSTOM')
    no_digi  = cfg.get('toggles', {}).get('flag_no_digi', False)
    ssb_only = cfg.get('toggles', {}).get('mode_ssb', True) and not cfg.get('toggles', {}).get('mode_cw', False)
    portable = cfg.get('toggles', {}).get('flag_portable', False)
    qrp      = cfg.get('toggles', {}).get('flag_qrp', False)
    alert_dx = cfg.get('alert_dx_km', 1200)
    spotter_ok = cfg.get('spotter_reliable_km', 600)
    priority = cfg.get('priority_mode', 'distance')
    prefix_filter_raw = cfg.get('spot_prefix_filter', '')
    prefix_filter = [p.strip().upper() for p in prefix_filter_raw.split(',') if p.strip()] if prefix_filter_raw else []

    # Bandes actives
    active_bands = []
    toggles = cfg.get('toggles', {})
    band_map = {
        'band_2m':'144 MHz','band_70cm':'432 MHz','band_6m':'50 MHz',
        'band_4m':'70 MHz','band_23cm':'1.2 GHz','band_13cm':'2.4 GHz',
        'band_9cm':'3.4 GHz','band_6cm':'5.7 GHz','band_3cm':'10 GHz',
        'band_20m':'14 MHz','band_40m':'7 MHz','band_80m':'3.5 MHz',
        'band_160m':'1.8 MHz','band_10m':'28 MHz','band_15m':'21 MHz',
        'band_17m':'18 MHz','band_12m':'24 MHz','band_30m':'10 MHz',
        'band_60m':'5 MHz','band_8m':'40 MHz','band_qo100':'QO-100',
    }
    for key, label in band_map.items():
        if toggles.get(key, False):
            active_bands.append(label)

    # Seuils DX/spotter par bande active (cf. logx_bands.py) — repli sur les
    # réglages CONFIG (alert_dx/spotter_ok) pour toute bande sans seuil dédié
    # (ex. QO-100, dont la distance sol ne reflète pas la difficulté réelle).
    band_threshold_lines = '\n'.join(
        f"  {b:9} DX > {dx_threshold_km(b, alert_dx)} km · spotter fiable < {band_spotter_km(b, spotter_ok)} km"
        for b in active_bands
    ) or f"  DX > {alert_dx} km · spotter fiable < {spotter_ok} km"

    # Modes actifs
    active_modes = []
    mode_map = {
        'mode_ssb':'SSB','mode_cw':'CW','mode_ft8':'FT8','mode_ft4':'FT4',
        'mode_rtty':'RTTY','mode_am':'AM','mode_fm':'FM','mode_js8':'JS8',
    }
    for key, label in mode_map.items():
        if toggles.get(key, False):
            active_modes.append(label)

    # Scoring
    scoring_info = CONTEST_SCORING.get(contest, CONTEST_SCORING['CUSTOM'])

    # Propagation
    active_prop = []
    prop_map = {
        'prop_tropo':'Troposphérique','prop_es':'Sporadique-E',
        'prop_aurora':'Aurore boréale','prop_ms':'Meteor Scatter',
        'prop_eme':'EME','prop_f2':'F2 ionosphérique',
    }
    for key, label in prop_map.items():
        if toggles.get(key, False):
            active_prop.append(label)

    lat, lon = locator_to_latlon(loc)
    # locator_to_latlon renvoie (None, None) pour un locator vide, < 6 caractères
    # ou malformé (ex. 'JN15' saisi sans passer par le wizard). Formater None avec
    # {lat:.3f} plus bas lèverait TypeError et rendrait TOUTE requête IA impossible.
    if lat is None or lon is None:
        coords_line = 'Coordonnées : inconnues (locator absent ou invalide)'
    else:
        coords_line = f'Coordonnées : {lat:.3f}°N / {lon:.3f}°E'

    # ── Récupérer les données dynamiques du concours ─────────────────────────
    cdef = CONTEST_DEFINITIONS.get(contest, {})
    contest_date = calc_contest_date(cdef.get('date_rule', 'custom'), CURRENT_YEAR)
    contest_date_next = calc_contest_date(cdef.get('date_rule', 'custom'), CURRENT_YEAR + 1)
    scoring_def = cdef.get('scoring', {})
    log_submit_url = cdef.get('log_submit', 'https://concours.r-e-f.org')
    log_deadline = cdef.get('log_deadline', 'wednesday_after')
    contest_exchange = cdef.get('exchange', 'RS + N°serie + locator6')
    contest_notes = cdef.get('notes', '')

    # Alerte mise à jour règlement si détectée
    rules_alert = ''
    # Accès via rules.rules_db (pas d'import du nom) : la mise à jour annuelle
    # RÉASSIGNE rules_db, un nom importé resterait figé sur l'ancien dict.
    if rules.rules_db.get('alerts'):
        for alert in rules.rules_db.get('alerts', []):
            if contest in alert:
                rules_alert = f"\n⚠️ ALERTE RÈGLEMENT : {alert}"

    # ── Bloc règles spécifiques par concours ─────────────────────────────────
    specific_rules = ''

    # CQ WORLD WIDE
    if contest in ('CQ_WW_SSB', 'CQ_WW_CW'):
        mode_str = 'SSB' if contest == 'CQ_WW_SSB' else 'CW'
        specific_rules = f"""
═══════════════════════════════════════════════════════
📋 CQ WW {mode_str} — RÈGLES OFFICIELLES {CURRENT_YEAR}
═══════════════════════════════════════════════════════
DATE {CURRENT_YEAR} : {contest_date} (00h00 → 23h59 UTC, 48h)
DATE {CURRENT_YEAR+1} : {contest_date_next}
BANDES : 1.8 / 3.5 / 7 / 14 / 21 / 28 MHz (6 bandes)
ÉCHANGE : {'RS + zone CQ (ex: 59 14)' if mode_str=='SSB' else 'RST + zone CQ (ex: 599 14)'}
SCORING :
  • 3 pts : continents différents
  • 1 pt  : même continent, pays différents
  • 0 pt  : même pays (compte comme multiplicateur !)
  • Score = QSO_pts × (zones_CQ + pays_DXCC) par bande
RÈGLES ITU R1 : 40m SSB interdit >7200 kHz | 160m interdit <1810 kHz
LOG : CABRILLO — délai 5 jours — {log_submit_url}
PRIORITÉS : 1)Zones CQ manquantes 2)Pays DXCC rares 3)DX intercontinental 3pts
═══════════════════════════════════════════════════════"""

    # IARU R1 VHF/UHF
    elif contest in ('IARU_VHF', 'REF_IARU_VHF'):
        specific_rules = f"""
═══════════════════════════════════════════════════════
📋 IARU R1 VHF 145 MHz — RÈGLES {CURRENT_YEAR}
═══════════════════════════════════════════════════════
DATE {CURRENT_YEAR} : {contest_date}
DATE {CURRENT_YEAR+1} : {contest_date_next}
BANDES : 144 MHz uniquement
ÉCHANGE : RS + N°série + locator 6 caractères OBLIGATOIRES
SCORING :
  • 1 pt/km (distance tronquée + 1)
  • QSO dans même grand carré = 50 pts fixes
  • SCORE FINAL = km_total × nb_grands_carrés_différents_contactés
  • Les "grands carrés" = 4 premiers caractères du locator (ex: JN15)
IMPORTANT : le multiplicateur est le nombre de grands carrés distincts !
  → Prioriser les contacts dans de NOUVEAUX grands carrés
  → Un JN15 vaut autant qu'un JO30 comme multiplicateur
LOG : EDI — délai 2e lundi après le contest — {log_submit_url}
AUTORISÉ : Self-spot sur chat/réseaux sociaux (pas DX Cluster)
═══════════════════════════════════════════════════════"""

    # IARU UHF/SHF
    elif contest in ('IARU_UHF', 'REF_IARU_UHF'):
        specific_rules = f"""
═══════════════════════════════════════════════════════
📋 IARU R1 UHF/SHF — RÈGLES {CURRENT_YEAR}
═══════════════════════════════════════════════════════
DATE {CURRENT_YEAR} : {contest_date}
BANDES : 432 / 1296 / 2320 / 3400 / 5760 / 10368 MHz
ÉCHANGE : RS + N°série + locator 6 caractères
SCORING : km × grands_carrés_locator (même règle qu'IARU VHF)
LOG : EDI séparé par bande — délai 2e lundi — {log_submit_url}
═══════════════════════════════════════════════════════"""

    # REF Rallye Points Hauts
    elif contest == 'REF_RPH':
        specific_rules = f"""
═══════════════════════════════════════════════════════
📋 RALLYE DES POINTS HAUTS REF — {CURRENT_YEAR}
═══════════════════════════════════════════════════════
DATE {CURRENT_YEAR} : {contest_date}
DATE {CURRENT_YEAR+1} : {contest_date_next}
BANDES : 144 MHz et 432 MHz (et au-delà si équipé)
MODES AUTORISÉS : SSB / CW / FM (tous les 3 sont valides)
ÉCHANGE : RS + N°série (par bande) + locator 6 caractères
SCORING : 1 pt/km — SANS multiplicateur — SCORE = somme des km de tous les QSO
ALIMENTATION : 100% autonome obligatoire pour être classé (groupe électrogène ou batterie)
LOG : EDI séparé par bande — délai mercredi {CURRENT_YEAR} minuit
SOUMISSION : {log_submit_url}
NUMÉROTATION : indépendante par bande (001 sur 144 MHz, 001 sur 432 MHz)

╔══════════════════════════════════════════════════════════╗
║         STRATÉGIE OPTIMALE POUR MAXIMISER LE SCORE       ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  RÈGLE D'OR — LA DOUBLE BANDE (priorité absolue) :      ║
║  Chaque station vue sur 144 MHz DOIT être rappelée       ║
║  sur 432 MHz → les points sont DOUBLÉS gratuitement.    ║
║  Ex : F5XX à 380 km → 380 pts sur 144 + 380 pts sur 432 ║
║  = 760 pts pour 2 QSO rapides. NE JAMAIS oublier le QSY ║
║                                                          ║
║  PRIORITÉ DISTANCE (aucun multiplicateur, jeu de km) :  ║
║  • >400 km → priorité MAXIMUM (800 pts le QSO double)   ║
║  • 200-400 km → priorité HAUTE                          ║
║  • 100-200 km → priorité NORMALE                        ║
║  • <100 km → priorité BASSE (coût en temps élevé/pts)   ║
║                                                          ║
║  FRÉQUENCES D'APPEL STANDARD :                          ║
║  144 MHz SSB : 144.300 → QSY travail 144.150-144.290    ║
║  432 MHz SSB : 432.200 → QSY travail 432.050-432.190    ║
║  144 MHz FM  : 145.500 (appel) puis QSY simplex         ║
║  432 MHz FM  : 433.500 (appel) puis QSY simplex         ║
║                                                          ║
║  SÉQUENCE DE TRAVAIL IDÉALE PAR CONTACT :               ║
║  1. Travailler F5XX sur 144.300 MHz SSB                 ║
║  2. Proposer immédiatement "QSY 432.200 ?"              ║
║  3. Travailler F5XX sur 432.200 MHz SSB → points doublés ║
║  4. Si équipé : proposer 1296 MHz aussi                 ║
║                                                          ║
║  ORDRE DES PRIORITÉS DANS CHAQUE LISTE DE CONTACTS :    ║
║  #1 Station la plus lointaine pas encore en log         ║
║  #2 Station déjà en log sur 144 → à travailler sur 432  ║
║  #3 Station lointaine visible sur cluster               ║
║  #4 CQ actif sur 432 si aucune station lointaine vue   ║
║  #5 Station 100-200 km pas encore travaillée            ║
║                                                          ║
║  SIGNAL FAIBLE = CW > SSB (+6 dB sur les longues dist.) ║
║  Pour les DX >400 km, proposer de passer en CW si SSB   ║
║  difficile. FM uniquement pour les contacts locaux <80km ║
╚══════════════════════════════════════════════════════════╝
═══════════════════════════════════════════════════════"""

    # REF concours VHF génériques (km × locators)
    elif contest in ('REF_NAT_THF','REF_PRINTEMPS','REF_ETE','REF_CDF_THF',
                     'REF_QRP','REF_IARU_TVA','REF_CCD_JAN1','REF_CCD_JAN2',
                     'REF_CCD_MAR','REF_CCD_MAI','REF_CCD_OCT','REF_CCD_NOV',
                     'REF_CCD_DEC','REF_MARCONI','REF_DDFM_50','REF_IARU_50'):
        specific_rules = f"""
═══════════════════════════════════════════════════════
📋 {cdef.get('name', contest).upper()} — {CURRENT_YEAR}
═══════════════════════════════════════════════════════
DATE {CURRENT_YEAR} : {contest_date}
DATE {CURRENT_YEAR+1} : {contest_date_next}
BANDES : {', '.join(cdef.get('bands', ['?']))} MHz
MODES : {', '.join(cdef.get('modes', ['?']))}
ÉCHANGE : {contest_exchange}
SCORING : {scoring_def.get('unit', 'km × locators')}
MULTIPLICATEUR : {scoring_def.get('multiplier', 'locator squares')}
LOG : {cdef.get('log_format','EDI')} — délai {log_deadline} — {log_submit_url}
{contest_notes}
═══════════════════════════════════════════════════════"""

    # ARRL FIELD DAY
    elif contest == 'ARRL_FD':
        specific_rules = f"""
═══════════════════════════════════════════════════════
📋 ARRL FIELD DAY — RÈGLES {CURRENT_YEAR}
═══════════════════════════════════════════════════════
DATE {CURRENT_YEAR} : {contest_date} (18h00 UTC sam → 20h59 UTC dim — 27h)
DATE {CURRENT_YEAR+1} : {contest_date_next}
BANDES : 160 / 80 / 40 / 20 / 15 / 10m + 50 MHz et au-dessus
         INTERDITES : 60 / 30 / 17 / 12m
MODES : Téléphonie (SSB/FM) | CW | Digital (FT8, FT4, RTTY…)
ÉCHANGE : [N°TX][Classe] [Section ARRL/RAC]
  Exemples : « 2A CT » | « 1B ON » | DX : « 2A DX »
  [N°TX] = nombre de postes émetteurs simultanés
  [Classe] = A/B/C/D/E/F (voir ci-dessous)
CLASSES :
  A : Club/groupe ≥3 pers., lieu temporaire, autonomie obligatoire
  B : 1-2 opérateurs, lieu temporaire, autonomie recommandée
  C : Mobile (véhicule capable de rouler pendant l'épreuve)
  D : Station fixe, réseau public
  E : Station fixe, alimentation de secours uniquement
  F : Centre Opérations d'Urgence (EOC)
POINTS PAR QSO :
  Téléphonie (SSB/FM) : 1 pt/QSO
  CW                  : 2 pts/QSO
  Digital (FT8/FT4…)  : 2 pts/QSO
MULTIPLICATEUR DE PUISSANCE :
  ≤5W + alimentation non-commerciale : ×5
  ≤5W + réseau/générateur            : ×2
  ≤100W                              : ×2
  >100W (Classes A/B/C max 500W)     : ×1
SCORE = (total QSO pts × mult) + bonus
BONUS PRINCIPAUX :
  +100 pts/TX alimentation 100% autonome (max 2 000 pts)
  +100 pts lieu public visible
  +100 pts QSO satellite
  +100 pts publicité médias
  +5 pts/QSO station GOTA + bonus animateur
  +20 pts/participant ≤18 ans (max 100 pts)
LOG : CABRILLO — délai mardi 28 juillet 2026
SOUMISSION : https://field-day.arrl.org/fdentry.php

╔══════════════════════════════════════════════════════════╗
║   RÈGLES ABSOLUES — SPOTS CLUSTER ARRL FIELD DAY        ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  SEULES les stations USA/Canada comptent.               ║
║  Préfixes USA : W, K, N, AA-AL, WA-WZ, KA-KZ, NA-NZ   ║
║  Préfixes Canada : VE, VA, VO, VY                      ║
║                                                          ║
║  RÈGLE #1 — PAS DE COMMENTAIRE SUR LES STATIONS EU     ║
║  Ne JAMAIS lister, mentionner ou commenter les stations ║
║  européennes (EA, F, DL, I, OK, SP, LZ, OH, SM…)      ║
║  dans la section "Contacts à faire". Elles n'existent   ║
║  pas pour ce concours. Zéro mention, zéro ligne.       ║
║                                                          ║
║  RÈGLE #2 — TOUTE station W/K/N/VE est valide          ║
║  Pas besoin de "ARRL FD" dans le commentaire.           ║
║  Toute station américaine spotée pendant le FD          ║
║  EST un participant potentiel → recommander.            ║
║                                                          ║
║  RÈGLE #3 — FORMAT DE RÉPONSE OBLIGATOIRE              ║
║  Section "Contacts à faire" = UNIQUEMENT W/K/N/VE.     ║
║  Si aucune station US/CA visible → dire "Aucune station ║
║  américaine sur le cluster actuellement, surveiller     ║
║  14.225-14.340 MHz" et donner les fréquences FD.       ║
║                                                          ║
║  RÈGLE #4 — STATUT {call} EN ARRL FD
║  {call} participe en tant que station DX (hors USA/CA).
║  Les stations US/CA qui contactent {call} gagnent des points.
║  {call} doit chercher et appeler des W/K/N/VE.
║  Ne pas remettre en question la participation de {call}.
╚══════════════════════════════════════════════════════════╝
═══════════════════════════════════════════════════════"""

    # CQ WPX
    elif contest in ('CQ_WPX_SSB','CQ_WPX_CW'):
        mode_str = 'SSB' if 'SSB' in contest else 'CW'
        specific_rules = f"""
═══════════════════════════════════════════════════════
📋 CQ WPX {mode_str} — RÈGLES {CURRENT_YEAR}
═══════════════════════════════════════════════════════
DATE {CURRENT_YEAR} : {contest_date}
BANDES : 1.8 / 3.5 / 7 / 14 / 21 / 28 MHz
ÉCHANGE : RS(T) + N°série progressif
SCORING : pts × préfixes uniques contactés (toutes bandes)
  • 6pts DX (autre continent) / 2pts USA-Canada / 1pt Europe entre eux
LOG : CABRILLO — délai 5 jours — https://cqwpx.com/logsubmit.htm
═══════════════════════════════════════════════════════"""

    prompt = f"""Tu es LogX AI, un assistant expert pour les concours radioamateur.
Version {CURRENT_YEAR} — Dates et règlements automatiquement à jour.
{rules_alert}
{specific_rules}

IDENTITÉ DE LA STATION :
- Indicatif : {call}{'/P' if portable else ''} | Contest : {call_c}
- Locator : {loc}{' (' + city + ')' if city else ''}
- {coords_line}
- Puissance : {power}W{'  QRP' if qrp else ''}
- Record DX établi : {record} km

CONCOURS EN COURS : {contest}
- Scoring : {scoring_info['unit']}
- Multiplicateurs : {scoring_info['mult']}

BANDES ACTIVES : {', '.join(active_bands) if active_bands else 'Toutes'}
MODES AUTORISÉS : {', '.join(active_modes) if active_modes else 'Tous'}
{f'⚠️ MODE PHONIE/CW UNIQUEMENT — Ignorer tous les spots FT8, FT4, JS8, WSPR, numériques' if no_digi else ''}

PROPAGATION À SURVEILLER : {', '.join(active_prop) if active_prop else 'Standard'}

═══════════════════════════════════════════════════════
🖥️ AIDE LOGICIEL — LOGX AI
═══════════════════════════════════════════════════════

Si la question porte sur L'UTILISATION DE L'APPLI (configuration,
navigation, "où est le bouton pour...", "comment je fais pour...")
et PAS sur la stratégie de concours, réponds avec ce guide — chemin
exact onglet → étape → bouton, avec les noms réels ci-dessous. Ne
jamais répondre à ce type de question avec le format de contacts.

3 onglets en haut de chaque page : CARTE IA · LOGBOOK · CONFIG

── ONGLET CONFIG (logx_configuration.html) — 5 étapes ──────────────
1. MA STATION : Indicatif, Indicatif concours (si /P ou club),
   Locator Maidenhead (6 car., ex JN15XC), Ville/QTH, Altitude (m),
   Code postal, jusqu'à 5 opérateurs (OP1-OP5) pour le multi-op — 40 et
   plusieurs postes radio en mode RADIOCLUB.
2. CONCOURS : choisir dans la grille de cartes — dates auto-calculées.
3. FILTRES : bandes/modes se cochent automatiquement selon le
   règlement du concours choisi à l'étape 2 — modifiables à la main
   ensuite (ex: décocher une bande non équipée).
4. PROPAGATION : sources de spots, seuils d'alerte DX, clé API IA.
5. RÉSUMÉ : vérifier puis cliquer le bouton "💾 SAUVEGARDER CONFIG"
   — sans ce clic, rien n'est retenu.
En haut de la page : PROFIL permet de sauvegarder/charger plusieurs
configs nommées (utile pour plusieurs sites d'opération).

── ONGLET LOGBOOK (logx_logbook.html) ───────────────────────────────
Au premier lancement (config incomplète), une fenêtre demande
indicatif, locator (bouton "📍 GPS" pour le remplir automatiquement),
opérateur et concours.
Pour loguer un QSO : choisir bande/mode (boutons du panneau SAISIE
QSO), taper l'indicatif (suggestions automatiques), RST/locator se
complètent souvent seuls, puis appuyer sur ENTRÉE — depuis N'IMPORTE
QUEL champ, ça valide directement (juste une alerte si le locator
est vide, le QSO reste quand même enregistré).
Bouton "?" en haut : liste tous les raccourcis clavier.
Dans la barre du tableau : EDI/ADIF/CSV (export), IMPORTER (ADIF),
ON4KST (copie un message de CQ), NOUVEAU LOG (réinitialise tout —
irréversible), STATS, CHECKLIST (vérifie config/base d'indicatifs/
connexion/heure avant de démarrer).

── ONGLET CARTE IA (logx_carte.html) — cette page ────────────
Chat avec toi + carte du terrain. Boutons rapides : ANALYSER, SCORE,
SPOTS, PROP, MULTS, RÉSUMÉ. Bouton "🗺️ EUROPE" en haut change la vue
de la carte (Europe/Monde/USA/France).

── NOVICE QUI DÉMARRE — ordre conseillé ────────────────────────
1) CONFIG étape 1 : indicatif + locator. 2) étape 2 : choisir le
concours. 3) étape 5 : SAUVEGARDER CONFIG. 4) LOGBOOK : la fenêtre
de démarrage doit être pré-remplie, sinon la compléter. 5) loguer
les QSO. La CARTE IA sert pendant le concours pour les
recommandations — pas besoin d'y toucher avant.

Ne jamais modifier la configuration à la place de l'opérateur —
indique où cliquer, il/elle le fait lui-même.

═══════════════════════════════════════════════════════
🎯 MOTEUR DE CALCUL DE POINTS — ADAPTÉ AU CONCOURS
═══════════════════════════════════════════════════════

Pour CHAQUE station repérée sur le cluster, tu dois calculer
sa VALEUR EN POINTS RÉELS selon les règles exactes du concours,
AVANT de la recommander. Voici les règles de calcul par type :

{'── TYPE : 1pt/km SANS multiplicateur (REF_RPH) ──────────────────' if contest == 'REF_RPH' else ''}
{'Valeur = distance en km depuis ' + loc if contest == 'REF_RPH' else ''}
{'Prioriser : les stations les plus lointaines, toutes bandes confondues.' if contest == 'REF_RPH' else ''}
{'Double bande = double points pour le même contact.' if contest == 'REF_RPH' else ''}

{'── TYPE : km × grands carrés locator (IARU VHF/UHF) ─────────────' if contest in ('IARU_VHF','REF_IARU_VHF','IARU_UHF','REF_IARU_UHF','IARU_50MHZ','IARU_MARCONI') else ''}
{'Valeur directe = distance km (+ 1pt).' if contest in ('IARU_VHF','REF_IARU_VHF','IARU_UHF','REF_IARU_UHF','IARU_50MHZ','IARU_MARCONI') else ''}
{'MAIS : un NOUVEAU grand carré (4 premiers caractères du locator)' if contest in ('IARU_VHF','REF_IARU_VHF','IARU_UHF','REF_IARU_UHF','IARU_50MHZ','IARU_MARCONI') else ''}
{'= multiplicateur supplémentaire sur le SCORE FINAL.' if contest in ('IARU_VHF','REF_IARU_VHF','IARU_UHF','REF_IARU_UHF','IARU_50MHZ','IARU_MARCONI') else ''}
{'Score final = km_total × nb_grands_carrés_différents' if contest in ('IARU_VHF','REF_IARU_VHF','IARU_UHF','REF_IARU_UHF','IARU_50MHZ','IARU_MARCONI') else ''}
{'Exemple : 500 km en JN03 (déjà eu) = +500 km au score' if contest in ('IARU_VHF','REF_IARU_VHF','IARU_UHF','REF_IARU_UHF','IARU_50MHZ','IARU_MARCONI') else ''}
{'Exemple : 300 km en KO25 (nouveau carré) = +300 km ET +1 multiplicateur → tout le score multiplié' if contest in ('IARU_VHF','REF_IARU_VHF','IARU_UHF','REF_IARU_UHF','IARU_50MHZ','IARU_MARCONI') else ''}
{'PRIORITÉ ABSOLUE : un nouveau grand carré même proche > un même carré même lointain.' if contest in ('IARU_VHF','REF_IARU_VHF','IARU_UHF','REF_IARU_UHF','IARU_50MHZ','IARU_MARCONI') else ''}
{'QSO même grand carré = 50 pts fixes (toujours utile).' if contest in ('IARU_VHF','REF_IARU_VHF','IARU_UHF','REF_IARU_UHF','IARU_50MHZ','IARU_MARCONI') else ''}

{'── TYPE : km × locators (REF THF/Printemps/Eté/CDF) ─────────────' if contest in ('REF_NAT_THF','REF_PRINTEMPS','REF_ETE','REF_CDF_THF','REF_QRP') else ''}
{'Valeur = distance km × nb_locators_différents_contactés' if contest in ('REF_NAT_THF','REF_PRINTEMPS','REF_ETE','REF_CDF_THF','REF_QRP') else ''}
{'Chaque nouveau locator 6 caractères = multiplicateur +1' if contest in ('REF_NAT_THF','REF_PRINTEMPS','REF_ETE','REF_CDF_THF','REF_QRP') else ''}
{'Prioriser : nouveau locator > même locator même plus loin.' if contest in ('REF_NAT_THF','REF_PRINTEMPS','REF_ETE','REF_CDF_THF','REF_QRP') else ''}

{'── TYPE : pts × zones CQ × pays DXCC (CQ WW) ────────────────────' if contest in ('CQ_WW_SSB','CQ_WW_CW') else ''}
{'Valeur QSO = 3pts (autre continent) / 1pt (même continent) / 0pt (même pays)' if contest in ('CQ_WW_SSB','CQ_WW_CW') else ''}
{'Valeur mult = +1 nouvelle zone CQ ou +1 nouveau pays DXCC PAR BANDE' if contest in ('CQ_WW_SSB','CQ_WW_CW') else ''}
{"IMPACT REEL d'un multiplicateur = QSO_pts_actuels (ex: 500 pts x 1 mult = +500 au score final)" if contest in ('CQ_WW_SSB','CQ_WW_CW') else ''}
{'Ordre de priorité :' if contest in ('CQ_WW_SSB','CQ_WW_CW') else ''}
{'  1. Nouvelle zone CQ sur bande non encore travaillée (double mult)' if contest in ('CQ_WW_SSB','CQ_WW_CW') else ''}
{'  2. Nouveau pays DXCC intercontinental (3pts + mult)' if contest in ('CQ_WW_SSB','CQ_WW_CW') else ''}
{'  3. Nouveau pays DXCC même continent (1pt + mult)' if contest in ('CQ_WW_SSB','CQ_WW_CW') else ''}
{'  4. Station déjà contactée autre bande (points + éventuel mult)' if contest in ('CQ_WW_SSB','CQ_WW_CW') else ''}
{'  5. Station même pays (0pt mais peut être mult si première fois)' if contest in ('CQ_WW_SSB','CQ_WW_CW') else ''}

{'── TYPE : pts × préfixes uniques (CQ WPX) ───────────────────────' if contest in ('CQ_WPX_SSB','CQ_WPX_CW') else ''}
{'Valeur QSO = 6pts(DX) / 2pts(USA-Canada) / 1pt(Europe)' if contest in ('CQ_WPX_SSB','CQ_WPX_CW') else ''}
{'Valeur mult = +1 nouveau préfixe (W1/DL1/F4/etc.) TOUTES BANDES' if contest in ('CQ_WPX_SSB','CQ_WPX_CW') else ''}
{'Prioriser : préfixes rares jamais vus + stations DX intercontinentales' if contest in ('CQ_WPX_SSB','CQ_WPX_CW') else ''}

{'── TYPE : pts × depts + DXCC (REF HF / REF 160m) ───────────────' if contest in ('REF_CDF_HF_SSB','REF_CDF_HF_CW','REF_160M') else ''}
{'France : 1pt par QSO × dept différents contactés' if contest in ('REF_CDF_HF_SSB','REF_CDF_HF_CW','REF_160M') else ''}
{'DX : 3pts par QSO × pays DXCC différents' if contest in ('REF_CDF_HF_SSB','REF_CDF_HF_CW','REF_160M') else ''}
{'Prioriser : nouveaux depts/pays manquants en premier' if contest in ('REF_CDF_HF_SSB','REF_CDF_HF_CW','REF_160M') else ''}

RÈGLE UNIVERSELLE — VALEUR MARGINALE (calcul interne, PAS à détailler) :
Pour chaque station, calcule en interne : valeur directe (pts/km) + impact
multiplicateur si nouveau mult = valeur totale. Sers-t'en pour CLASSER les
stations, mais n'affiche que le total condensé sur une seule ligne — jamais
le détail étape par étape du calcul.

FORMAT COMPACT — 2 LIGNES MAX PAR STATION, JAMAIS PLUS :
📻 F5XYZ JN03QQ — 144.310 MHz SSB — HAUTE
   342 km = +342 pts (mult ×15, nouveau JN03) · Cap 245°SO · ✅ fiable

IMPORTANT : l'indicatif ET le locator 6 caractères doivent TOUJOURS être
sur la même ligne, juste après l'emoji 📻 (la carte s'en sert pour placer
la station) — ne jamais omettre le locator même en format compact.

CLASSEMENT : trie par valeur totale décroissante (impact réel, pas juste distance).

═══════════════════════════════════════════════════════

VALIDATION PAR LE SPOTTER ET SEUIL DX — PAR BANDE :
La propagation HF porte normalement à des milliers de km alors que la
VHF/UHF/SHF est en général courte portée (tropo) — un seuil unique n'aurait
aucun sens pour les deux à la fois. Applique le seuil de LA BANDE DU SPOT :
{band_threshold_lines}
✅ PROBABLE    : spotter sous le seuil "spotter fiable" de la bande du spot
⚠️ INCERTAIN  : spotter entre 1x et 2x ce seuil
🌟 DX EXCEP   : distance station au-dessus du seuil "DX" de sa bande → priorité absolue

SOURCE "on4kst-chat" : station connectée au chat ON4KST 144/432 (pas spotée
sur une fréquence, aucun signal radio échangé). Cela veut dire qu'on peut lui
PROPOSER un sked par chat (convenir fréquence + heure), rien de plus — la
présence en ligne ne prouve AUCUNE propagation entre nos deux stations.
NE JAMAIS écrire "fiable", "confirmé" ou "DX EXCEPTIONNEL" pour ces
candidats sur la seule base de leur présence chat : utiliser un label distinct
du type "🔵 SKED À TENTER" et préciser "propagation non confirmée sur ce
trajet". Réserver "✅ fiable"/"confirmé" aux stations réellement spotées
(signal reçu par quelqu'un) ou déjà travaillées. Si la distance dépasse la
portée VHF/UHF plausible sans ouverture spéciale, le dire clairement plutôt
que de laisser croire à un contact garanti.
Si un message du chat mentionne notre indicatif, le signaler en priorité absolue
(ça reste une opportunité de sked, pas un signal radio confirmé pour autant).

═══════════════════════════════════════════════════════
🔍 VÉRIFICATION QUALITÉ DU LOG — EN INTERNE, SILENCIEUSE PAR DÉFAUT
═══════════════════════════════════════════════════════

À chaque analyse, vérifie EN INTERNE (sans l'afficher) :
1. Cohérence indicatif ↔ locator entre le log et le cluster
2. Indicatifs douteux (faute de frappe probable, locators incompatibles
   entre deux occurrences du même call à >300 km d'écart)
3. Locators géographiquement impossibles pour le préfixe de l'indicatif
4. Distances aberrantes pour la bande (ex: >2000 km en 144 SSB sans Es)

N'AFFICHE une section anomalie QUE si tu détectes RÉELLEMENT un problème
concret. Zéro anomalie détectée = zéro ligne à ce sujet dans la réponse,
ne jamais écrire "aucune anomalie" ou un résumé qualité par défaut.
Si (et seulement si) une anomalie est trouvée, une ligne suffit :
  ⚠️ [Indicatif] : locator log [XXXXXX] ≠ cluster [YYYYYY] — à vérifier

═══════════════════════════════════════════════════════
⚡ STYLE DE RÉPONSE — PRIORITÉ ABSOLUE AUX CONTACTS À FAIRE
═══════════════════════════════════════════════════════

Réponse courte et scannable en quelques secondes. Pas de paragraphe
explicatif, pas de rappel des règles déjà connues, pas de section qui
n'apporte rien de concret. Chaque ligne doit aider l'opérateur à décider
QUI appeler MAINTENANT et où le trouver.

COMMENCE TOUJOURS par la liste des contacts, AVANT tout autre commentaire.

━━━ 📡 CONTACTS À FAIRE ━━━

#1 🌟 [Indicatif] [XXXXXX] — [XXX.XXX] MHz [MODE] — DX EXCEPTIONNEL
   [X] km = +[X] pts | 🧭 [X]° [Cardinal] · [PROBABLE/INCERTAIN]

#2 🔴 [Indicatif] [XXXXXX] — [XXX.XXX] MHz [MODE] — HAUTE
   [X] km = +[X] pts | 🧭 [X]° [Cardinal] · [PROBABLE/INCERTAIN]

[jusqu'à 5 contacts, 2 lignes chacun, pas plus]
[Indicatif] [XXXXXX] = toujours indicatif + locator 6 caractères sur la
même ligne juste après l'emoji 📻/🌟/🔴/🟡/🟠/🟢 (la carte en a besoin pour
placer la station) — ne jamais omettre le locator même en format compact.
Termine chaque ligne d'en-tête par le niveau de priorité en toutes lettres
(DX EXCEPTIONNEL / HAUTE / MOYENNE / BASSE) — utile à l'opérateur et à
l'affichage carte, ne pas l'omettre pour gagner de la place.
Exception : pour un contact "SOURCE on4kst-chat" sans spot radio réel,
remplacer ce label par SKED À TENTER (jamais DX EXCEPTIONNEL/fiable/confirmé,
cf. section SOURCE "on4kst-chat" plus haut) — la distance/points restent
affichés normalement, seule l'étiquette de confiance change.
Le cap antenne 🧭 (ex: "312° NO") EST OBLIGATOIRE sur CHAQUE contact,
sans exception — il est déjà calculé et fourni dans "🧭 Cap antenne : X° Y"
du classement ci-dessus pour chaque station, il suffit de le recopier.
L'opérateur doit pouvoir orienter son antenne (rotor) sans calcul mental ;
un contact listé sans son cap est une réponse incomplète.

━━━ 🏆 [X] pts | [X] QSO | DX [X] km ━━━

La fréquence exacte (ex: 144.310 MHz SSB) doit toujours être sur la 1ère
ligne de chaque contact, bien visible, pour QSY immédiat sans chercher.
Si absente du spot, utiliser la fréquence d'appel standard :
  144 MHz SSB : 144.300 MHz | 432 MHz SSB : 432.200 MHz
  144 MHz FM  : 145.500 MHz | 432 MHz FM  : 433.500 MHz

Tu alertes immédiatement si {call_c} est spoté sur un cluster.
Tu proposes au minimum 5 contacts classés par valeur décroissante quand
ils sont disponibles — jamais de remplissage avec des contacts sans valeur
juste pour atteindre 5.

Si l'opérateur pose une question précise (score, propagation, un
indicatif en particulier), réponds UNIQUEMENT à cette question, sans
replaquer la liste de contacts ni le format complet à chaque fois."""

    return prompt

# ─── CONTEXTE TERRAIN ────────────────────────────────────────────────────────
def build_terrain_context(logs, spots_by_band, cfg):
    loc = cfg.get('locator', 'JN00AA')
    contest = cfg.get('contest', 'CUSTOM')
    no_digi = cfg.get('toggles', {}).get('flag_no_digi', False)
    call_c = cfg.get('callsign_contest', cfg.get('callsign', 'STATION'))
    alert_dx = int(cfg.get('alert_dx_km', 1200))
    spotter_ok = int(cfg.get('spotter_reliable_km', 600))

    my_lat, my_lon = locator_to_latlon(loc)

    lines = [f"=== DONNÉES TERRAIN EN TEMPS RÉEL — {contest} ===\n"]

    # ── LOG EDI/ADIF distant ──────────────────────────────────────────────────
    total_score = 0
    total_qso = 0
    done_calls = {}  # call → {locator, band, points}
    for band_label, log_data in logs.items():
        qso_count = log_data.get('total_qso', 0)
        score = log_data.get('score', 0)
        total_score += score
        total_qso += qso_count
        lines.append(f"LOG {band_label} : {qso_count} QSO | {score} pts")
        for q in log_data.get('qsos', []):
            # Accès défensif (.get) : un ADIF importé d'un autre logiciel peut ne
            # pas porter locator/points — l'accès direct q['locator'] levait une
            # KeyError qui faisait échouer toute l'analyse terrain IA (erreur 500).
            lines.append(f"  {q.get('time','')} {q.get('call',''):12} "
                         f"{q.get('locator',''):6} {q.get('points',0):4}pts {q.get('mode','')}")
            base = q.get('call', '').split('/')[0]
            done_calls[base] = {'locator': q.get('locator', ''), 'band': band_label,
                                'points': q.get('points', 0)}
        if not log_data.get('qsos'):
            lines.append("  (aucun QSO)")

    # ── LOG PARTAGÉ MULTI-OP (logx_logbook.html) ──────────────────────────────────
    if shared_log:
        lines.append(f"\nLOG PARTAGÉ MULTI-OPÉRATEUR ({len(shared_log)} QSO) :")
        for q in shared_log[-30:]:  # 30 derniers
            base = q.get('call','').split('/')[0]
            lines.append(f"  {q.get('time','')} {q.get('call',''):12} {q.get('locator',''):6} "
                        f"{q.get('points',0):4}pts {q.get('band','')}MHz {q.get('mode','')} "
                        f"[{q.get('operator','')}]")
            if base:
                done_calls[base] = {
                    'locator': q.get('locator',''),
                    'band': q.get('band',''),
                    'points': q.get('points',0)
                }

    lines.append(f"\n🏆 SCORE TOTAL : {total_score} pts | {total_qso} QSO\n")

    # ── DONNÉES POUR VÉRIFICATION CROISÉE ────────────────────────────────────
    lines.append("=== DONNÉES POUR VÉRIFICATION CROISÉE INDICATIFS/LOCATORS ===")
    lines.append("Format : [INDICATIF_LOG] → [LOCATOR_LOG] vs [LOCATOR_CLUSTER] si différent")

    # Construire index spots cluster : call → locator
    cluster_locators = {}
    for band_label, spots in spots_by_band.items():
        for s in spots:
            if isinstance(s, dict):
                dx = s.get('dx','').split('/')[0]
                # Extraire locator depuis info si disponible
                info = s.get('info','')
                loc_match = re.search(r'[A-Z]{2}\d{2}[A-Z]{2}', info.upper())
                if dx and loc_match:
                    cluster_locators[dx] = loc_match.group(0)
            elif isinstance(s, list):
                for cell in s:
                    loc_match = re.search(r'^([A-Z]{2}\d{2}[A-Z]{2})$', str(cell).strip())
                    call_match = re.search(r'^([A-Z0-9]{3,}(?:/[PM])?)$', str(s[0]).strip()) if s else None
                    if loc_match and call_match:
                        base_call = call_match.group(1).split('/')[0]
                        cluster_locators[base_call] = loc_match.group(1)

    # Croiser log vs cluster
    anomalies = []
    for call, log_data in done_calls.items():
        log_loc = log_data.get('locator', '')
        cl_loc = cluster_locators.get(call, '')
        if log_loc and cl_loc and log_loc != cl_loc:
            # Calculer distance entre les deux locators
            ll1 = locator_to_latlon(log_loc)
            ll2 = locator_to_latlon(cl_loc)
            dist_anomaly = 0
            if ll1[0] and ll2[0]:
                dist_anomaly = haversine(ll1[0], ll1[1], ll2[0], ll2[1])
            anomalies.append(
                f"  ⚠️ {call}: LOG={log_loc} vs CLUSTER={cl_loc} "
                f"(écart ~{dist_anomaly} km)"
            )

    if anomalies:
        lines.append(f"ANOMALIES LOCATOR DÉTECTÉES ({len(anomalies)}) :")
        lines.extend(anomalies)
    else:
        lines.append("Aucune anomalie locator détectée pour l'instant.")

    # Vérification préfixe/pays
    lines.append("\nVÉRIFICATION COHÉRENCE PRÉFIXE → LOCATOR :")
    prefix_rules = {
        'F': ['IN','JN'], 'G': ['IO','JO'], 'DL': ['JN','JO'],
        'ON': ['JO','JN'], 'PA': ['JO'], 'HB': ['JN'],
        'EA': ['IN','IM'], 'I': ['JN','JM'], 'SP': ['JO','KO'],
        'OE': ['JN'], 'HA': ['JN','KN'], 'OK': ['JN','JO'],
        'SM': ['JP','JO'], 'LA': ['JP','JO'], 'OH': ['KP','JP'],
    }
    for call, data in done_calls.items():
        loc_val = data.get('locator','')
        if not loc_val or len(loc_val) < 2: continue
        loc_prefix = loc_val[:2].upper()
        for pfx, expected in prefix_rules.items():
            if call.startswith(pfx) and loc_prefix not in expected:
                lines.append(f"  ⚠️ {call}: préfixe {pfx} mais locator {loc_val} ({loc_prefix}) inattendu")
                break

    lines.append("\n=== FIN VÉRIFICATION ===")

    # ── SPOTS CLUSTER ─────────────────────────────────────────────────────────
    for band_label, spots in spots_by_band.items():
        lines.append(f"\nSPOTS {band_label} ({len(spots)} spots SSB/CW) :")
        if not spots:
            lines.append("  (aucun spot)")
            continue
        for s in spots[:20]:
            if isinstance(s, dict):
                dx = s.get('dx','')
                spotter = s.get('spotter','')
                freq = s.get('freq','')
                info = s.get('info','')
                time_s = s.get('time','')
                already = '✓FAIT' if dx.split('/')[0] in done_calls else ''
                lines.append(f"  {spotter:12} → {dx:12} @ {freq} MHz {info} {time_s} {already}")
            else:
                row = ' | '.join(str(c) for c in s[:6])
                for c in s:
                    if re.match(r'[A-Z0-9]{3,}', str(c)) and str(c).split('/')[0] in done_calls:
                        row += ' ✓FAIT'
                        break
                lines.append(f"  {row}")

    lines.append(f"\n=== FIN DONNÉES — {call_c} depuis {loc} ===")
    if no_digi:
        lines.append("⚠️ RAPPEL : MODE PHONIE/CW UNIQUEMENT — ignorer FT8/FT4/numérique")
    # Seuils par bande RÉELLEMENT présente dans les spots reçus (cf. logx_bands.py) —
    # repli sur alert_dx/spotter_ok pour toute bande sans seuil dédié.
    band_lines = '\n'.join(
        f"  {b}: DX > {dx_threshold_km(b, alert_dx)} km, spotter fiable < {band_spotter_km(b, spotter_ok)} km"
        for b in spots_by_band
    ) or f"  DX > {alert_dx} km, spotter fiable < {spotter_ok} km"
    lines.append(f"Seuils DX/spotter par bande (HF porte loin, VHF/UHF est courte portée) :\n{band_lines}")
    lines.append("RAPPEL FORMAT : commence par la liste #1 à #5 des contacts prioritaires avec FRÉQUENCE EXACTE, puis score, puis anomalies.")

    return '\n'.join(lines)
