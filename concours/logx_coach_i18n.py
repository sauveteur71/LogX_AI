# -*- coding: utf-8 -*-
"""Localisation des textes DÉTERMINISTES du coach (logx_coach.py).

Le coach produit des phrases interpolées (nombres, bandes, %) que le moteur
i18n du navigateur (correspondance de texte source) ne peut pas traduire.
On centralise ici des TEMPLATES à clés + placeholders, traduits à l'émission
selon la langue demandée (query ?lang= sur /coach/state).

Le FRANÇAIS reste la source de vérité : toute clé absente d'une langue
retombe sur le français. Les langues traduites à la main correspondent à
celles de logx_i18n.js (en/de/es/it/pt/nl/pl) ; « auto » et toute
autre valeur ⇒ français (le navigateur traduit alors la page lui-même).

Usage : t(lang, 'hint_silence', min=15)  →  chaîne formatée.
Les placeholders utilisent la syntaxe str.format : {min}, {h:.0f}, {r10}…
"""

# ─── FRANÇAIS — SOURCE DE VÉRITÉ (doit reproduire l'ancien texte à l'identique) ─
_FR = {
    # Plan de bande (band_plan → reason)
    'band_open': "ouverte à cette heure",
    'band_closed': "hors créneau de propagation",
    'mult_suffix': " — mult ×{w}",
    'band_contest': "bande du concours",
    'band_es': "SPORADIQUE-E ACTIF — fonce",
    'band_tropo': "tropo actif — tente les distances",
    # Conseils (build_hints → text)
    'hint_checklist': "Départ dans {h:.0f} h — passe la CHECKLIST du logbook "
                      "(bouton ✅) : config, heure synchronisée, postes connectés.",
    'hint_finished_base': "Concours terminé — exporte ton log (📥 dans le LOGBOOK) et envoie-le",
    'hint_finished_deadline': " (deadline : {deadline})",
    'hint_finished_submit': " → {submit}",
    'hint_no_contest': "Aucun concours actif configuré — passe par CONFIG "
                       "pour choisir le concours et ses dates.",
    'hint_silence': "Aucun QSO depuis {min} min — change de bande ou de "
                    "fréquence, lance appel, ou va chercher les spots classés.",
    'hint_rate_drop': "Rythme en baisse : {last_h} QSO sur la dernière heure "
                      "contre {rate:.0f}/h de moyenne — change quelque chose "
                      "(bande, cap d'antenne, recherche→appel).",
    'hint_optime_over': "Budget d'opération épuisé ({max_op} h max) — toute "
                        "heure supplémentaire peut invalider ton log.",
    'hint_optime_plan': "Il te reste {op_left:.0f} h d'opération autorisées pour "
                        "{remaining:.0f} h de concours — planifie {pause:.0f} h "
                        "de pause dans les creux (pauses de 60 min minimum).",
    'hint_qtc_done': "QTC échangés : {qtc} (+{qtc} pts au score final). ",
    'hint_qtc_todo': "Pense aux QTC : chaque QTC transféré vaut 1 point ",
    'hint_qtc_tail': "Max 10 par station — autant que des QSO gratuits.",
    'hint_best_band': "{band} MHz est ouverte ET compte ses mults ×{w} — c'est "
                      "la bande la plus rentable à cette heure.",
    'hint_endgame': "Dernières {remaining:.1f} h : un multiplicateur nouveau vaut "
                    "plus que des QSO en série — chasse les mults manquants "
                    "dans les spots PRIORITÉ MAX.",
    'hint_last_hour': "Dernière heure — logge tout, on trie après.",
    # Cibles jamais travaillées à VIE, spottées sur le cluster (spotted_new_ones)
    'hint_new_dxcc': "🌍 NOUVEAU PAYS jamais travaillé : {label} — {call}{freq_txt} "
                     "spotté, appelle-le !",
    'hint_new_dept': "🇫🇷 NOUVEAU DÉPARTEMENT jamais travaillé : {label} — {call}"
                     "{freq_txt} spotté, appelle-le !",
    # Prévision Es / aurora (es_aurora_forecast → text)
    'es_confirmed': "⚡ SPORADIQUE-E CONFIRMÉ (DXMaps) — surveille 6 m puis 2 m, "
                    "les ouvertures montent en fréquence.",
    'es_probable': "🌤 Es PROBABLE (saison + créneau {h}h UTC) — garde un œil "
                   "sur 50.150-50.300, ça peut ouvrir d'un coup vers 800-2000 km.",
    'es_possible': "Saison Es : ouverture possible à tout moment sur 6 m, "
                   "pics probables en matinée et fin d'après-midi (UTC).",
    'aurora_vhf_storm': "🔴 K={k:.0f} ORAGE GÉOMAGNÉTIQUE — ",
    'aurora_vhf_mild': "🟡 K={k:.0f} — ",
    'aurora_vhf_tail': "aurora VHF possible : antennes vers le NORD sur 2 m "
                       "(signaux 'raspy', polarisation aléatoire).",
    'aurora_hf': "🟡 K={k:.0f} — perturbation géomagnétique : HF bandes hautes "
                 "(14/21/28) dégradées, privilégie les bandes basses.",
    # Run vs Search & Pounce (run_sp_recommendation → reason)
    'sp_start': "Début de course : chasse les spots pour amorcer le log, "
                "tu passeras en RUN quand ça mord.",
    'run_hot': "{r10}/h sur 10 min — la fréquence tourne, reste en RUN (appel CQ).",
    'sp_drop': "Rate en chute ({r10}/h contre {r60}/h) et {mults} nouveaux mults "
               "sur le cluster — passe en Search & Pounce.",
    'change_band': "{r10}/h et aucun mult spotté — change de bande "
                   "(regarde le plan de bande et la MUF).",
    'run_stable': "Rate stable ({r10}/h) — garde la fréquence.",
    'sp_soft': "Rate mou ({r10}/h) — alterne : un tour de cluster puis "
               "retour en appel.",
    # Réponses HORS-LIGNE du chat (answer_text) : le coach déterministe répond
    # aux boutons rapides quand l'IA est injoignable (expédition sans internet).
    'off_score': "🏆 {qso} QSO — {score} points",
    'off_score_m': " (avec multiplicateurs : {score_m} pts, {nmults} mults)",
    'off_depts': " · {ndept} département(s)",
    'off_clock_run': "⏱ reste {h} h ({pct} %)",
    'off_clock_before': "⏳ départ dans {h} h",
    'off_clock_done': "🏁 concours terminé — pense à exporter et déposer",
    'off_no_contest': "Aucun concours actif — choisis-le dans CONFIG",
    'off_rate': "📈 {last_h} QSO sur la dernière heure",
    'off_rate_avg': " · moyenne {avg}/h",
    'off_silence': " · silence radio depuis {min} min",
    'off_bands_head': "📶 Bandes maintenant (du plus rentable au moins) :",
    'off_band_row': "• {band} MHz — {reason}",
    'off_bands_none': "Aucune bande configurée pour ce concours.",
    'off_mults_head': "🎯 {nmults} multiplicateur(s) confirmé(s), score avec mults : {score_m} pts.",
    'off_mults_none': "🎯 Aucun multiplicateur confirmé pour l'instant.",
    'off_byband_head': "Par bande : {rows}",
    'off_mults_hint': "Pour voir les mults qui MANQUENT, il faut le cluster (retour en ligne).",
    'off_spots_na': "⚠ Hors-ligne : impossible de vérifier tes spots (cluster / PSK / RBN sans réseau). "
                    "Je peux te donner 🏆 Score, 📶 Prop, 🎯 Mults et 📋 Résumé.",
    # Projection de fin de concours (answer_text) : extrapolation à rythme
    # constant, volontairement PROSPECTIVE (contrairement aux autres off_*).
    'off_proj_no_run': "⏱ Projection disponible seulement pendant un concours en cours.",
    'off_proj_not_enough': "📊 Pas encore assez de QSO pour une projection fiable — reviens un peu plus tard.",
    'off_proj_qso': "📊 À ce rythme (~{rate}/h) : ~{qso} QSO en fin de concours",
    'off_proj_score': " — score estimé : ~{score} pts",
    'off_proj_caveat': " (estimation à rythme constant — les multiplicateurs restants se raréfient "
                       "généralement en fin de concours, le score final t'appartient).",
    # Nudges IA événementiels (coach_nudge) : UNE phrase d'action en toast.
    'nudge_new_dxcc': "🌍 {label} jamais fait à vie ET spotté ({call}{freq_txt}) — appelle-le !",
    'nudge_new_dept': "🇫🇷 {label} jamais fait à vie ET spotté ({call}{freq_txt}) — appelle-le !",
    'nudge_rate': "Rythme effondré : {last_h} QSO sur la dernière heure contre {avg}/h de moyenne — "
                  "change de bande, de cap, ou passe en recherche.",
    'nudge_silence': "Silence radio depuis {min} min — lance un appel ou va chercher les mults spottés.",
}

# ─── LANGUES TRADUITES À LA MAIN (jargon radioamateur respecté) ────────────────
# Chaque table est un sous-ensemble de _FR ; les clés absentes retombent sur _FR.
_EN = {
    'band_open': 'open at this hour',
    'band_closed': 'outside the propagation window',
    'mult_suffix': ' — mult ×{w}',
    'band_contest': 'contest band',
    'band_es': 'SPORADIC-E ACTIVE — go for it',
    'band_tropo': 'tropo active — try the distance',
    'hint_checklist': 'Start in {h:.0f} h — run the logbook CHECKLIST (✅ button): config, clock synced, rigs connected.',
    'hint_finished_base': 'Contest over — export your log (📥 in the LOGBOOK) and submit it',
    'hint_finished_deadline': ' (deadline: {deadline})',
    'hint_finished_submit': ' → {submit}',
    'hint_no_contest': 'No active contest configured — go through CONFIG to pick the contest and its dates.',
    'hint_silence': 'No QSO for {min} min — change band or frequency, start calling CQ, or go hunt the ranked spots.',
    'hint_rate_drop': 'Rate dropping: {last_h} QSO over the last hour vs {rate:.0f}/h average — change something (band, antenna heading, S&P→RUN).',
    'hint_optime_over': 'Operating budget used up ({max_op} h max) — any extra hour could invalidate your log.',
    'hint_optime_plan': 'You have {op_left:.0f} h of operating left for {remaining:.0f} h of contest — plan {pause:.0f} h of breaks in the lulls (breaks of 60 min minimum).',
    'hint_qtc_done': 'QTC exchanged: {qtc} (+{qtc} pts to final score). ',
    'hint_qtc_todo': 'Think about QTC: each QTC transferred is worth 1 point ',
    'hint_qtc_tail': 'Max 10 per station — as good as free QSO.',
    'hint_best_band': "{band} MHz is open AND its mults ×{w} count — it's the most rewarding band at this hour.",
    'hint_endgame': 'Last {remaining:.1f} h: a new multiplier is worth more than a string of QSO — hunt the missing mults in the MAX PRIORITY spots.',
    'hint_last_hour': 'Last hour — log everything, sort it out later.',
    'hint_new_dxcc': '🌍 NEW COUNTRY never worked: {label} — {call}{freq_txt} spotted, call it!',
    'hint_new_dept': '🇫🇷 NEW DEPARTMENT never worked: {label} — {call}{freq_txt} spotted, call it!',
    'es_confirmed': '⚡ SPORADIC-E CONFIRMED (DXMaps) — watch 6 m then 2 m, openings climb in frequency.',
    'es_probable': '🌤 Es LIKELY (season + {h}h UTC window) — keep an eye on 50.150-50.300, it can open suddenly toward 800-2000 km.',
    'es_possible': 'Es season: opening possible any time on 6 m, peaks likely in the morning and late afternoon (UTC).',
    'aurora_vhf_storm': '🔴 K={k:.0f} GEOMAGNETIC STORM — ',
    'aurora_vhf_mild': '🟡 K={k:.0f} — ',
    'aurora_vhf_tail': "aurora VHF possible: antennas toward NORTH on 2 m (signals 'raspy', random polarization).",
    'aurora_hf': '🟡 K={k:.0f} — geomagnetic disturbance: HF high bands (14/21/28) degraded, favor the low bands.',
    'sp_start': "Race start: hunt the spots to prime the log, you'll switch to RUN once it bites.",
    'run_hot': '{r10}/h over 10 min — the frequency is producing, stay in RUN (call CQ).',
    'sp_drop': 'Rate falling ({r10}/h vs {r60}/h) and {mults} new mults on the cluster — switch to Search & Pounce.',
    'change_band': '{r10}/h and no mult spotted — change band (check the band plan and the MUF).',
    'run_stable': 'Rate stable ({r10}/h) — hold the frequency.',
    'sp_soft': 'Rate soft ({r10}/h) — alternate: one sweep of the cluster then back to calling.',
    'off_score': '🏆 {qso} QSO — {score} points',
    'off_score_m': ' (with multipliers: {score_m} pts, {nmults} mults)',
    'off_depts': ' · {ndept} department(s)',
    'off_clock_run': '⏱ {h} h left ({pct} %)',
    'off_clock_before': '⏳ start in {h} h',
    'off_clock_done': '🏁 contest over — remember to export and submit',
    'off_no_contest': 'No active contest — pick it in CONFIG',
    'off_rate': '📈 {last_h} QSO in the last hour',
    'off_rate_avg': ' · {avg}/h average',
    'off_silence': ' · radio silence for {min} min',
    'off_bands_head': '📶 Bands right now (most to least rewarding):',
    'off_band_row': '• {band} MHz — {reason}',
    'off_bands_none': 'No band configured for this contest.',
    'off_mults_head': '🎯 {nmults} multiplier(s) confirmed, score with mults: {score_m} pts.',
    'off_mults_none': '🎯 No multiplier confirmed yet.',
    'off_byband_head': 'By band: {rows}',
    'off_mults_hint': 'To see the mults you are MISSING you need the cluster (back online).',
    'off_spots_na': '⚠ Offline: cannot check your spots (cluster / PSK / RBN need the network). '
                    'I can give you 🏆 Score, 📶 Prop, 🎯 Mults and 📋 Summary.',
    'off_proj_no_run': '⏱ Projection only available during a running contest.',
    'off_proj_not_enough': '📊 Not enough QSO yet for a reliable projection — check back a bit later.',
    'off_proj_qso': '📊 At this rate (~{rate}/h): ~{qso} QSO by the end of the contest',
    'off_proj_score': ' — estimated score: ~{score} pts',
    'off_proj_caveat': ' (constant-rate estimate — remaining multipliers usually get scarcer '
                       'toward the end, the final score is up to you).',
    'nudge_new_dxcc': '🌍 {label} never worked AND spotted now ({call}{freq_txt}) — call it!',
    'nudge_new_dept': '🇫🇷 {label} never worked AND spotted ({call}{freq_txt}) — call it!',
    'nudge_rate': 'Rate collapsed: {last_h} QSO in the last hour vs {avg}/h average — '
                  'change band, heading, or switch to search.',
    'nudge_silence': 'Radio silent for {min} min — call CQ or go hunt the spotted mults.',
}

_DE = {
    'band_open': 'zu dieser Zeit offen',
    'band_closed': 'außerhalb des Ausbreitungsfensters',
    'mult_suffix': ' — Mult ×{w}',
    'band_contest': 'Contest-Band',
    'band_es': 'SPORADIC-E AKTIV — voll drauf',
    'band_tropo': 'Tropo aktiv — versuch die Weiten',
    'hint_checklist': 'Start in {h:.0f} h — geh die CHECKLISTE im Logbuch durch (Button ✅): Konfiguration, Zeit synchronisiert, Geräte verbunden.',
    'hint_finished_base': 'Contest beendet — exportiere dein Log (📥 im LOGBUCH) und reiche es ein',
    'hint_finished_deadline': ' (Deadline: {deadline})',
    'hint_finished_submit': ' → {submit}',
    'hint_no_contest': 'Kein aktiver Contest konfiguriert — geh über KONFIGURATION, um den Contest und seine Daten festzulegen.',
    'hint_silence': 'Kein QSO seit {min} min — wechsle Band oder Frequenz, ruf CQ oder such nach den eingestuften Spots.',
    'hint_rate_drop': 'Rate sinkt: {last_h} QSO in der letzten Stunde gegenüber {rate:.0f}/h im Schnitt — änder etwas (Band, Antennenrichtung, Search→CQ).',
    'hint_optime_over': 'Betriebszeit aufgebraucht ({max_op} h max) — jede weitere Stunde kann dein Log ungültig machen.',
    'hint_optime_plan': 'Dir bleiben {op_left:.0f} h erlaubte Betriebszeit für {remaining:.0f} h Contest — plan {pause:.0f} h Pause in den Flauten (Pausen mindestens 60 min).',
    'hint_qtc_done': 'QTC ausgetauscht: {qtc} (+{qtc} Pkt. zum Endergebnis). ',
    'hint_qtc_todo': 'Denk an die QTC: jedes übertragene QTC bringt 1 Punkt ',
    'hint_qtc_tail': 'Max 10 pro Station — quasi kostenlose QSO.',
    'hint_best_band': '{band} MHz ist offen UND zählt seine Mults ×{w} — das ist zu dieser Zeit das lohnendste Band.',
    'hint_endgame': 'Letzte {remaining:.1f} h: ein neuer Multiplikator ist mehr wert als QSO am Fließband — jag die fehlenden Mults in den Spots MAX PRIORITY.',
    'hint_last_hour': 'Letzte Stunde — logg alles, aussortiert wird später.',
    'hint_new_dxcc': '🌍 NEUES LAND, nie gearbeitet: {label} — {call}{freq_txt} gespottet, ruf es!',
    'hint_new_dept': '🇫🇷 NEUES DEPARTEMENT, nie gearbeitet: {label} — {call}{freq_txt} gespottet, ruf es!',
    'es_confirmed': '⚡ SPORADIC-E BESTÄTIGT (DXMaps) — beobachte 6 m, dann 2 m, die Öffnungen steigen in der Frequenz.',
    'es_probable': '🌤 Es WAHRSCHEINLICH (Saison + Fenster {h}h UTC) — behalt 50.150-50.300 im Auge, kann schlagartig Richtung 800-2000 km aufgehen.',
    'es_possible': 'Es-Saison: Öffnung jederzeit möglich auf 6 m, Spitzen wahrscheinlich am Vormittag und am späten Nachmittag (UTC).',
    'aurora_vhf_storm': '🔴 K={k:.0f} GEOMAGNETISCHER STURM — ',
    'aurora_vhf_mild': '🟡 K={k:.0f} — ',
    'aurora_vhf_tail': "Aurora VHF möglich: Antennen Richtung NORDEN auf 2 m (Signale 'raspy', zufällige Polarisation).",
    'aurora_hf': '🟡 K={k:.0f} — geomagnetische Störung: hohe HF-Bänder (14/21/28) beeinträchtigt, bevorzuge die niedrigen Bänder.',
    'sp_start': 'Rennstart: jag die Spots, um das Log anzukurbeln, du gehst auf RUN, sobald es beißt.',
    'run_hot': '{r10}/h in 10 min — die Frequenz läuft, bleib auf RUN (CQ-Ruf).',
    'sp_drop': 'Rate im Sturzflug ({r10}/h gegenüber {r60}/h) und {mults} neue Mults im Cluster — geh auf Search & Pounce.',
    'change_band': '{r10}/h und kein Mult gespottet — wechsle das Band (schau auf den Bandplan und die MUF).',
    'run_stable': 'Rate stabil ({r10}/h) — halt die Frequenz.',
    'sp_soft': 'Rate lasch ({r10}/h) — wechsle ab: eine Runde durchs Cluster, dann zurück zum CQ-Ruf.',
}

_ES = {
    'band_open': 'abierta a esta hora',
    'band_closed': 'fuera de ventana de propagación',
    'mult_suffix': ' — mult ×{w}',
    'band_contest': 'banda del concurso',
    'band_es': 'ESPORÁDICA-E ACTIVA — a por ella',
    'band_tropo': 'tropo activo — prueba las distancias',
    'hint_checklist': 'Salida en {h:.0f} h — repasa la CHECKLIST del logbook (botón ✅): configuración, hora sincronizada, equipos conectados.',
    'hint_finished_base': 'Concurso terminado — exporta tu log (📥 en el LOGBOOK) y envíalo',
    'hint_finished_deadline': ' (fecha límite: {deadline})',
    'hint_finished_submit': ' → {submit}',
    'hint_no_contest': 'Ningún concurso activo configurado — entra en CONFIG para elegir el concurso y sus fechas.',
    'hint_silence': 'Ningún QSO desde hace {min} min — cambia de banda o de frecuencia, lanza llamada, o busca los spots clasificados.',
    'hint_rate_drop': 'Ritmo a la baja: {last_h} QSO en la última hora frente a {rate:.0f}/h de media — cambia algo (banda, orientación de antena, búsqueda→llamada).',
    'hint_optime_over': 'Presupuesto de operación agotado ({max_op} h máx) — cada hora adicional puede invalidar tu log.',
    'hint_optime_plan': 'Te quedan {op_left:.0f} h de operación autorizadas para {remaining:.0f} h de concurso — planifica {pause:.0f} h de pausa en los valles (pausas de 60 min mínimo).',
    'hint_qtc_done': 'QTC intercambiados: {qtc} (+{qtc} pts al puntaje final). ',
    'hint_qtc_todo': 'Piensa en los QTC: cada QTC transferido vale 1 punto ',
    'hint_qtc_tail': 'Máx 10 por estación — tantos como QSO gratis.',
    'hint_best_band': '{band} MHz está abierta Y cuenta sus mults ×{w} — es la banda más rentable a esta hora.',
    'hint_endgame': 'Últimas {remaining:.1f} h: un multiplicador nuevo vale más que QSO en serie — caza los mults que faltan en los spots MAX PRIORITY.',
    'hint_last_hour': 'Última hora — loguea todo, ya clasificamos después.',
    'hint_new_dxcc': '🌍 NUEVO PAÍS nunca trabajado: {label} — {call}{freq_txt} spoteado, ¡llámalo!',
    'hint_new_dept': '🇫🇷 NUEVO DEPARTAMENTO nunca trabajado: {label} — {call}{freq_txt} spoteado, ¡llámalo!',
    'es_confirmed': '⚡ ESPORÁDICA-E CONFIRMADA (DXMaps) — vigila 6 m y luego 2 m, las aperturas suben en frecuencia.',
    'es_probable': '🌤 Es PROBABLE (temporada + ventana {h}h UTC) — no pierdas de vista 50.150-50.300, puede abrir de golpe hacia 800-2000 km.',
    'es_possible': 'Temporada de Es: apertura posible en cualquier momento en 6 m, picos probables por la mañana y al final de la tarde (UTC).',
    'aurora_vhf_storm': '🔴 K={k:.0f} TORMENTA GEOMAGNÉTICA — ',
    'aurora_vhf_mild': '🟡 K={k:.0f} — ',
    'aurora_vhf_tail': "aurora VHF posible: antenas hacia el NORTE en 2 m (señales 'raspy', polarización aleatoria).",
    'aurora_hf': '🟡 K={k:.0f} — perturbación geomagnética: HF bandas altas (14/21/28) degradadas, prioriza las bandas bajas.',
    'sp_start': 'Inicio de carrera: caza los spots para arrancar el log, pasarás a RUN cuando pique.',
    'run_hot': '{r10}/h en 10 min — la frecuencia gira, quédate en RUN (llamada CQ).',
    'sp_drop': 'Rate en caída ({r10}/h frente a {r60}/h) y {mults} nuevos mults en el cluster — pasa a Search & Pounce.',
    'change_band': '{r10}/h y ningún mult spotado — cambia de banda (mira el plan de banda y la MUF).',
    'run_stable': 'Rate estable ({r10}/h) — mantén la frecuencia.',
    'sp_soft': 'Rate flojo ({r10}/h) — alterna: una vuelta al cluster y luego vuelta a la llamada.',
}

_IT = {
    'band_open': "aperta a quest'ora",
    'band_closed': 'fuori dalla finestra di propagazione',
    'mult_suffix': ' — mult ×{w}',
    'band_contest': 'banda del contest',
    'band_es': 'SPORADIC-E ATTIVO — vai',
    'band_tropo': 'tropo attivo — tenta le distanze',
    'hint_checklist': 'Partenza tra {h:.0f} h — fai la CHECKLIST del logbook (pulsante ✅): configurazione, ora sincronizzata, apparati connessi.',
    'hint_finished_base': 'Contest terminato — esporta il tuo log (📥 nel LOGBOOK) e invialo',
    'hint_finished_deadline': ' (scadenza: {deadline})',
    'hint_finished_submit': ' → {submit}',
    'hint_no_contest': 'Nessun contest attivo configurato — passa da CONFIG per scegliere il contest e le sue date.',
    'hint_silence': 'Nessun QSO da {min} min — cambia banda o frequenza, lancia un CQ, o vai a cercare gli spot classificati.',
    'hint_rate_drop': "Ritmo in calo: {last_h} QSO nell'ultima ora contro {rate:.0f}/h di media — cambia qualcosa (banda, puntamento antenna, ricerca→CQ).",
    'hint_optime_over': 'Budget di operazione esaurito ({max_op} h max) — ogni ora in più può invalidare il tuo log.',
    'hint_optime_plan': 'Ti restano {op_left:.0f} h di operazione autorizzate per {remaining:.0f} h di contest — pianifica {pause:.0f} h di pausa nei momenti morti (pause di almeno 60 min).',
    'hint_qtc_done': 'QTC scambiati: {qtc} (+{qtc} pt al punteggio finale). ',
    'hint_qtc_todo': 'Pensa ai QTC: ogni QTC trasferito vale 1 punto ',
    'hint_qtc_tail': 'Max 10 per stazione — tanti quanti dei QSO gratis.',
    'hint_best_band': "{band} MHz è aperta E conta i suoi mults ×{w} — è la banda più redditizia a quest'ora.",
    'hint_endgame': 'Ultime {remaining:.1f} h: un nuovo moltiplicatore vale più di una serie di QSO — caccia i mults mancanti negli spot PRIORITÀ MAX.',
    'hint_last_hour': 'Ultima ora — logga tutto, si filtra dopo.',
    'hint_new_dxcc': '🌍 NUOVO PAESE mai lavorato: {label} — {call}{freq_txt} spottato, chiamalo!',
    'hint_new_dept': '🇫🇷 NUOVO DIPARTIMENTO mai lavorato: {label} — {call}{freq_txt} spottato, chiamalo!',
    'es_confirmed': '⚡ SPORADIC-E CONFERMATO (DXMaps) — sorveglia i 6 m poi i 2 m, le aperture salgono in frequenza.',
    'es_probable': "🌤 Es PROBABILE (stagione + finestra {h}h UTC) — tieni d'occhio 50.150-50.300, può aprirsi di colpo verso 800-2000 km.",
    'es_possible': 'Stagione Es: apertura possibile in qualsiasi momento sui 6 m, picchi probabili al mattino e nel tardo pomeriggio (UTC).',
    'aurora_vhf_storm': '🔴 K={k:.0f} TEMPESTA GEOMAGNETICA — ',
    'aurora_vhf_mild': '🟡 K={k:.0f} — ',
    'aurora_vhf_tail': "aurora VHF possibile: antenne verso NORD sui 2 m (segnali 'raspy', polarizzazione casuale).",
    'aurora_hf': '🟡 K={k:.0f} — perturbazione geomagnetica: HF bande alte (14/21/28) degradate, privilegia le bande basse.',
    'sp_start': 'Inizio gara: caccia gli spot per avviare il log, passerai in RUN quando morde.',
    'run_hot': '{r10}/h su 10 min — la frequenza gira, resta in RUN (chiamata CQ).',
    'sp_drop': 'Rate in caduta ({r10}/h contro {r60}/h) e {mults} nuovi mults sul cluster — passa in Search & Pounce.',
    'change_band': '{r10}/h e nessun mult spottato — cambia banda (guarda il piano di banda e la MUF).',
    'run_stable': 'Rate stabile ({r10}/h) — mantieni la frequenza.',
    'sp_soft': 'Rate fiacco ({r10}/h) — alterna: un giro di cluster poi ritorno alla chiamata.',
}

_PT = {
    'band_open': 'aberta a esta hora',
    'band_closed': 'fora da janela de propagação',
    'mult_suffix': ' — mult ×{w}',
    'band_contest': 'banda do concurso',
    'band_es': 'SPORADIC-E ATIVO — avança',
    'band_tropo': 'tropo ativo — tenta as distâncias',
    'hint_checklist': 'Início em {h:.0f} h — passa pela CHECKLIST do logbook (botão ✅): configuração, hora sincronizada, equipamentos ligados.',
    'hint_finished_base': 'Concurso terminado — exporta o teu log (📥 no LOGBOOK) e envia-o',
    'hint_finished_deadline': ' (prazo: {deadline})',
    'hint_finished_submit': ' → {submit}',
    'hint_no_contest': 'Nenhum concurso ativo configurado — passa por CONFIG para escolher o concurso e as suas datas.',
    'hint_silence': 'Nenhum QSO há {min} min — muda de banda ou de frequência, lança CQ, ou vai buscar os spots classificados.',
    'hint_rate_drop': 'Ritmo a descer: {last_h} QSO na última hora contra {rate:.0f}/h de média — muda algo (banda, direção da antena, procura→chamada).',
    'hint_optime_over': 'Tempo de operação esgotado ({max_op} h máx) — qualquer hora adicional pode invalidar o teu log.',
    'hint_optime_plan': 'Restam-te {op_left:.0f} h de operação autorizadas para {remaining:.0f} h de concurso — planeia {pause:.0f} h de pausa nos períodos calmos (pausas de 60 min no mínimo).',
    'hint_qtc_done': 'QTC trocados: {qtc} (+{qtc} pts na pontuação final). ',
    'hint_qtc_todo': 'Pensa nos QTC: cada QTC transferido vale 1 ponto ',
    'hint_qtc_tail': 'Máx 10 por estação — tantos como QSO grátis.',
    'hint_best_band': '{band} MHz está aberta E conta os seus mults ×{w} — é a banda mais rentável a esta hora.',
    'hint_endgame': 'Últimas {remaining:.1f} h: um multiplicador novo vale mais que QSO em série — caça os mults em falta nos spots PRIORIDADE MÁX.',
    'hint_last_hour': 'Última hora — regista tudo, filtra-se depois.',
    'hint_new_dxcc': '🌍 NOVO PAÍS nunca trabalhado: {label} — {call}{freq_txt} spotado, chama-o!',
    'hint_new_dept': '🇫🇷 NOVO DEPARTAMENTO nunca trabalhado: {label} — {call}{freq_txt} spotado, chama-o!',
    'es_confirmed': '⚡ SPORADIC-E CONFIRMADO (DXMaps) — vigia 6 m depois 2 m, as aberturas sobem em frequência.',
    'es_probable': '🌤 Es PROVÁVEL (época + janela {h}h UTC) — fica atento a 50.150-50.300, pode abrir de repente para 800-2000 km.',
    'es_possible': 'Época de Es: abertura possível a qualquer momento em 6 m, picos prováveis de manhã e ao fim da tarde (UTC).',
    'aurora_vhf_storm': '🔴 K={k:.0f} TEMPESTADE GEOMAGNÉTICA — ',
    'aurora_vhf_mild': '🟡 K={k:.0f} — ',
    'aurora_vhf_tail': "aurora VHF possível: antenas para NORTE em 2 m (sinais 'raspy', polarização aleatória).",
    'aurora_hf': '🟡 K={k:.0f} — perturbação geomagnética: HF bandas altas (14/21/28) degradadas, privilegia as bandas baixas.',
    'sp_start': 'Início da corrida: caça os spots para arrancar o log, passas para RUN quando começar a morder.',
    'run_hot': '{r10}/h em 10 min — a frequência roda, fica em RUN (chamada CQ).',
    'sp_drop': 'Rate em queda ({r10}/h contra {r60}/h) e {mults} novos mults no cluster — passa para Search & Pounce.',
    'change_band': '{r10}/h e nenhum mult spotado — muda de banda (olha o plano de banda e a MUF).',
    'run_stable': 'Rate estável ({r10}/h) — mantém a frequência.',
    'sp_soft': 'Rate fraco ({r10}/h) — alterna: uma volta ao cluster depois regressa à chamada.',
}

_NL = {
    'band_open': 'open op dit uur',
    'band_closed': 'buiten propagatievenster',
    'mult_suffix': ' — mult ×{w}',
    'band_contest': 'contestband',
    'band_es': 'SPORADISCHE-E ACTIEF — ga ervoor',
    'band_tropo': 'tropo actief — probeer de afstanden',
    'hint_checklist': 'Start over {h:.0f} u — loop de CHECKLIST van het logboek door (knop ✅): configuratie, tijd gesynchroniseerd, stations verbonden.',
    'hint_finished_base': 'Contest afgelopen — exporteer je log (📥 in het LOGBOOK) en stuur hem op',
    'hint_finished_deadline': ' (deadline: {deadline})',
    'hint_finished_submit': ' → {submit}',
    'hint_no_contest': 'Geen actieve contest geconfigureerd — ga via CONFIG om de contest en de datums te kiezen.',
    'hint_silence': 'Geen QSO sinds {min} min — wissel van band of frequentie, roep CQ, of ga de gerangschikte spots halen.',
    'hint_rate_drop': 'Tempo daalt: {last_h} QSO in het laatste uur tegenover {rate:.0f}/u gemiddeld — verander iets (band, antennerichting, zoeken→roepen).',
    'hint_optime_over': 'Operatietijd op ({max_op} u max) — elk extra uur kan je log ongeldig maken.',
    'hint_optime_plan': 'Je hebt nog {op_left:.0f} u toegestane operatietijd voor {remaining:.0f} u contest — plan {pause:.0f} u pauze in de dalmomenten (pauzes van minimaal 60 min).',
    'hint_qtc_done': 'QTC uitgewisseld: {qtc} (+{qtc} pt in de eindscore). ',
    'hint_qtc_todo': "Denk aan de QTC's: elke overgedragen QTC is 1 punt waard ",
    'hint_qtc_tail': "Max 10 per station — net zoveel als gratis QSO's.",
    'hint_best_band': '{band} MHz is open EN telt zijn mults ×{w} — dit is de meest lonende band op dit uur.',
    'hint_endgame': "Laatste {remaining:.1f} u: een nieuwe multiplier is meer waard dan QSO's op een rij — jaag op de ontbrekende mults in de spots MAX PRIORITEIT.",
    'hint_last_hour': 'Laatste uur — log alles, sorteren doen we later.',
    'hint_new_dxcc': '🌍 NIEUW LAND nooit gewerkt: {label} — {call}{freq_txt} gespot, roep het!',
    'hint_new_dept': '🇫🇷 NIEUW DEPARTEMENT nooit gewerkt: {label} — {call}{freq_txt} gespot, roep het!',
    'es_confirmed': '⚡ SPORADISCHE-E BEVESTIGD (DXMaps) — houd 6 m en dan 2 m in de gaten, de openingen stijgen in frequentie.',
    'es_probable': '🌤 Es WAARSCHIJNLIJK (seizoen + venster {h}u UTC) — houd 50.150-50.300 in het oog, het kan ineens opengaan richting 800-2000 km.',
    'es_possible': 'Es-seizoen: opening mogelijk op elk moment op 6 m, pieken waarschijnlijk in de ochtend en laat in de namiddag (UTC).',
    'aurora_vhf_storm': '🔴 K={k:.0f} GEOMAGNETISCHE STORM — ',
    'aurora_vhf_mild': '🟡 K={k:.0f} — ',
    'aurora_vhf_tail': "aurora op VHF mogelijk: antennes naar het NOORDEN op 2 m (signalen 'raspy', willekeurige polarisatie).",
    'aurora_hf': '🟡 K={k:.0f} — geomagnetische verstoring: HF hoge banden (14/21/28) verzwakt, geef voorrang aan de lage banden.',
    'sp_start': 'Start van de wedstrijd: jaag op de spots om het log op gang te brengen, ga naar RUN zodra het aanslaat.',
    'run_hot': '{r10}/u over 10 min — de frequentie draait, blijf in RUN (CQ roepen).',
    'sp_drop': 'Rate daalt ({r10}/u tegenover {r60}/u) en {mults} nieuwe mults op het cluster — ga over op Search & Pounce.',
    'change_band': '{r10}/u en geen enkele mult gespot — wissel van band (bekijk het bandplan en de MUF).',
    'run_stable': 'Rate stabiel ({r10}/u) — houd de frequentie.',
    'sp_soft': 'Rate zwak ({r10}/u) — wissel af: een rondje cluster en dan terug naar CQ roepen.',
}

_PL = {
    'band_open': 'otwarte o tej porze',
    'band_closed': 'poza oknem propagacji',
    'mult_suffix': ' — mnożnik ×{w}',
    'band_contest': 'pasmo zawodów',
    'band_es': 'SPORADIC-E AKTYWNE — dawaj',
    'band_tropo': 'tropo aktywne — próbuj dystansów',
    'hint_checklist': 'Start za {h:.0f} h — przejdź LISTĘ KONTROLNĄ logbooka (przycisk ✅): konfiguracja, zsynchronizowany czas, podłączone urządzenia.',
    'hint_finished_base': 'Zawody zakończone — wyeksportuj log (📥 w LOGBOOK) i wyślij go',
    'hint_finished_deadline': ' (termin: {deadline})',
    'hint_finished_submit': ' → {submit}',
    'hint_no_contest': 'Brak skonfigurowanych aktywnych zawodów — wejdź w CONFIG, aby wybrać zawody i ich daty.',
    'hint_silence': 'Brak QSO od {min} min — zmień pasmo lub częstotliwość, nadaj wywołanie albo poszukaj sklasyfikowanych spotów.',
    'hint_rate_drop': 'Tempo spada: {last_h} QSO w ostatniej godzinie wobec średnio {rate:.0f}/h — zmień coś (pasmo, kierunek anteny, nasłuch→wywołanie).',
    'hint_optime_over': 'Budżet czasu pracy wyczerpany (maks. {max_op} h) — każda dodatkowa godzina może unieważnić twój log.',
    'hint_optime_plan': 'Zostało ci {op_left:.0f} h dozwolonej pracy na {remaining:.0f} h zawodów — zaplanuj {pause:.0f} h przerwy w martwych okresach (przerwy min. 60 min).',
    'hint_qtc_done': 'Wymienione QTC: {qtc} (+{qtc} pkt do wyniku końcowego). ',
    'hint_qtc_todo': 'Pamiętaj o QTC: każde przekazane QTC to 1 punkt ',
    'hint_qtc_tail': 'Maks. 10 na stację — tyle samo co darmowe QSO.',
    'hint_best_band': '{band} MHz jest otwarte ORAZ liczy swoje mnożniki ×{w} — to najbardziej opłacalne pasmo o tej porze.',
    'hint_endgame': 'Ostatnie {remaining:.1f} h: nowy mnożnik jest wart więcej niż seria QSO — poluj na brakujące mnożniki w spotach MAKS. PRIORYTET.',
    'hint_last_hour': 'Ostatnia godzina — loguj wszystko, posortujemy później.',
    'hint_new_dxcc': '🌍 NOWY KRAJ nigdy niepracowany: {label} — {call}{freq_txt} zaspotowany, wywołaj go!',
    'hint_new_dept': '🇫🇷 NOWY DEPARTAMENT nigdy niepracowany: {label} — {call}{freq_txt} zaspotowany, wywołaj go!',
    'es_confirmed': '⚡ SPORADIC-E POTWIERDZONE (DXMaps) — obserwuj 6 m, potem 2 m, otwarcia wędrują w górę częstotliwości.',
    'es_probable': '🌤 Es PRAWDOPODOBNE (sezon + okno {h}h UTC) — miej oko na 50.150-50.300, może otworzyć się nagle na 800-2000 km.',
    'es_possible': 'Sezon Es: otwarcie możliwe w każdej chwili na 6 m, szczyty prawdopodobne rano i późnym popołudniem (UTC).',
    'aurora_vhf_storm': '🔴 K={k:.0f} BURZA GEOMAGNETYCZNA — ',
    'aurora_vhf_mild': '🟡 K={k:.0f} — ',
    'aurora_vhf_tail': "możliwa aurora VHF: anteny na PÓŁNOC na 2 m (sygnały 'raspy', przypadkowa polaryzacja).",
    'aurora_hf': '🟡 K={k:.0f} — zaburzenie geomagnetyczne: górne pasma HF (14/21/28) osłabione, stawiaj na pasma niskie.',
    'sp_start': 'Początek biegu: poluj na spoty, aby rozkręcić log, przejdziesz w RUN, gdy zacznie brać.',
    'run_hot': '{r10}/h w 10 min — częstotliwość kręci się, zostań w RUN (wywołanie CQ).',
    'sp_drop': 'Rate spada ({r10}/h wobec {r60}/h) i {mults} nowych mnożników na klastrze — przejdź na Search & Pounce.',
    'change_band': '{r10}/h i żadnego zaspotowanego mnożnika — zmień pasmo (sprawdź bandplan i MUF).',
    'run_stable': 'Rate stabilny ({r10}/h) — trzymaj częstotliwość.',
    'sp_soft': 'Rate słaby ({r10}/h) — na przemian: obrót po klastrze, potem powrót do wywołania.',
}

LANG_TABLES = {
    'fr': _FR, 'en': _EN, 'de': _DE, 'es': _ES,
    'it': _IT, 'pt': _PT, 'nl': _NL, 'pl': _PL,
}


def t(lang, key, **params):
    """Template localisé formaté. Retombe sur le français si la langue ou la
    clé manque ; ne lève jamais (un template cassé retourne le texte brut)."""
    table = LANG_TABLES.get(lang) or _FR
    tpl = table.get(key)
    if tpl is None:
        tpl = _FR.get(key, '')
    try:
        return tpl.format(**params)
    except (KeyError, IndexError, ValueError, TypeError):
        # Placeholder inattendu OU type incompatible (ex. None sur un spec
        # numérique '{n:d}' → TypeError) : on tente le FR, sinon le brut.
        # TypeError doit être attrapé ici sinon le contrat « ne lève jamais »
        # de la docstring est violé.
        try:
            return _FR.get(key, tpl).format(**params)
        except (KeyError, IndexError, ValueError, TypeError):
            return tpl
