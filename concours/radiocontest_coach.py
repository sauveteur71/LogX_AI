# -*- coding: utf-8 -*-
"""Coach de stratégie de concours — couche temporelle et objectifs.

Tout est DÉTERMINISTE (aucun appel IA) : horloge du concours, rythme QSO/h,
plan de bande selon l'heure et le barème, budget d'opération (off-time),
rappels spécifiques au règlement (QTC, mults pondérés, fin de course).
L'IA n'intervient qu'en aval : /coach/state expose aussi un 'coach_prompt'
prêt à envoyer à /proxy/ai pour un conseil narratif.

L'horloge s'appuie sur les dates du concours ACTIF dans config.json
(remplies par l'assistant de configuration) — pas sur date_rule, que
l'utilisateur peut avoir surchargé.
"""
import datetime

from radiocontest_definitions import CONTEST_DEFINITIONS

HF_BANDS = ('1.8', '3.5', '7', '14', '21', '28')


# ─── HORLOGE DU CONCOURS ─────────────────────────────────────────────────────

def _parse_dt(date_str, time_str):
    """'20260801'/'2026-08-01' + '1200'/'12:00' → datetime UTC naïf, None si invalide."""
    d = (date_str or '').replace('-', '').strip()
    t = (time_str or '').replace(':', '').strip() or '0000'
    try:
        return datetime.datetime.strptime(f"{d}{t[:4]}", '%Y%m%d%H%M')
    except (ValueError, TypeError):
        return None


def contest_clock(cfg, cdef=None, now=None):
    """État temporel du concours actif : avant / en_cours / termine.
    Lit la config CLIENT (plate : contest, contest_start_date, contest_end_date,
    contest_end_utc) ; l'heure de départ vient de la définition (start_utc).
    Retourne un dict toujours exploitable, même sans config complète."""
    now = now or datetime.datetime.utcnow()
    cfg = cfg or {}
    cdef = cdef or {}
    contest_id = cfg.get('contest', '') if isinstance(cfg.get('contest'), str) else ''
    start = _parse_dt(cfg.get('contest_start_date', ''), cdef.get('start_utc', ''))
    end = _parse_dt(cfg.get('contest_end_date', ''), cfg.get('contest_end_utc', ''))
    clock = {
        'contest_id': contest_id,
        'contest_name': cdef.get('name', contest_id),
        'now_utc': now.strftime('%Y-%m-%d %H:%M'),
        'status': 'inconnu',
        'start_utc': start.strftime('%Y-%m-%d %H:%M') if start else None,
        'end_utc': end.strftime('%Y-%m-%d %H:%M') if end else None,
    }
    if not start or not end:
        return clock
    if end <= start:  # fin le lendemain saisie sans changer la date
        end += datetime.timedelta(days=1)
    total_h = (end - start).total_seconds() / 3600
    clock['duration_h'] = round(total_h, 1)
    if now < start:
        clock['status'] = 'avant'
        clock['starts_in_h'] = round((start - now).total_seconds() / 3600, 1)
    elif now >= end:
        clock['status'] = 'termine'
        clock['ended_h_ago'] = round((now - end).total_seconds() / 3600, 1)
    else:
        clock['status'] = 'en_cours'
        elapsed = (now - start).total_seconds() / 3600
        clock['elapsed_h'] = round(elapsed, 2)
        clock['remaining_h'] = round(total_h - elapsed, 2)
        clock['pct_done'] = round(100 * elapsed / total_h) if total_h else 0
    return clock


# ─── STATISTIQUES DU LOG ─────────────────────────────────────────────────────

def _entry_dt(entry):
    """Timestamp UTC d'une entrée du log partagé (date '20260704' + time '14:03')."""
    return _parse_dt(entry.get('date', ''), entry.get('time', ''))


def log_stats(shared_log, contest_id='', clock=None, now=None):
    """Rythme et répartition : QSO/h global, dernière heure, silence radio,
    heures opérées (pour le budget off-time), répartition par bande."""
    now = now or datetime.datetime.utcnow()
    entries = [e for e in (shared_log or [])
               if not contest_id or e.get('contest', '') in ('', contest_id)]
    stats = {
        'qso_total': len(entries),
        'score': sum(e.get('points', 0) or 0 for e in entries),
        'by_band': {},
        'qso_last_hour': 0,
        'qso_last_10min': 0,
        'rate_avg': None,
        'minutes_since_last': None,
        'hours_operated': 0,
    }
    hours_seen = set()
    last_dt = None
    for e in entries:
        band = str(e.get('band', '?'))
        stats['by_band'][band] = stats['by_band'].get(band, 0) + 1
        dt = _entry_dt(e)
        if not dt:
            continue
        hours_seen.add(dt.strftime('%Y%m%d%H'))
        age_s = (now - dt).total_seconds()
        if age_s <= 3600:
            stats['qso_last_hour'] += 1
        if age_s <= 600:
            stats['qso_last_10min'] += 1
        if last_dt is None or dt > last_dt:
            last_dt = dt
    # Rate meter : 10 min glissantes extrapolées en QSO/h + 60 min glissantes
    stats['rate_10min'] = stats['qso_last_10min'] * 6
    stats['rate_60min'] = stats['qso_last_hour']
    stats['hours_operated'] = len(hours_seen)
    if last_dt:
        stats['minutes_since_last'] = int((now - last_dt).total_seconds() // 60)
    if clock and clock.get('status') == 'en_cours' and clock.get('elapsed_h', 0) > 0.25:
        stats['rate_avg'] = round(stats['qso_total'] / clock['elapsed_h'], 1)
    return stats


# ─── PLAN DE BANDE ───────────────────────────────────────────────────────────

def _hf_bands_for_hour(hour_utc):
    """Heuristique propagation HF Europe : bandes ouvertes selon l'heure UTC."""
    if 21 <= hour_utc or hour_utc < 4:      # nuit
        return ['1.8', '3.5', '7']
    if 4 <= hour_utc < 7 or 17 <= hour_utc < 21:  # grey line / transition
        return ['3.5', '7', '14']
    return ['14', '21', '28']               # plein jour


def band_plan(cdef, clock, dxmaps=None, now=None):
    """Bandes recommandées MAINTENANT, pondérées par le barème du concours.
    Retourne [{band, weight, reason}] trié par intérêt décroissant."""
    now = now or datetime.datetime.utcnow()
    bands = [str(b) for b in (cdef or {}).get('bands', [])]
    if not bands:
        return []
    bricks = ((cdef or {}).get('scoring', {}) or {}).get('bricks', {}) or {}
    weights = {str(k): v for k, v in (bricks.get('mult_weight_by_band') or {}).items()}

    plan = []
    if any(b in HF_BANDS for b in bands):
        open_now = _hf_bands_for_hour(now.hour)
        for b in bands:
            if b not in HF_BANDS:
                continue
            w = weights.get(b, 1)
            is_open = b in open_now
            score = (10 if is_open else 0) + w
            reason = 'ouverte à cette heure' if is_open else 'hors créneau de propagation'
            if w > 1:
                reason += f" — mult ×{w}"
            plan.append({'band': b, 'score': score, 'weight': w,
                         'open': is_open, 'reason': reason})
    else:  # VHF+ : la bande principale reste reine, Es/tropo en bonus
        es = bool((dxmaps or {}).get('es_active'))
        tropo = bool((dxmaps or {}).get('tropo_active'))
        for b in bands:
            reason = 'bande du concours'
            score = 5
            if es and b in ('50', '144'):
                score, reason = 12, 'SPORADIQUE-E ACTIF — fonce'
            elif tropo:
                score, reason = 10, 'tropo actif — tente les distances'
            plan.append({'band': b, 'score': score, 'weight': 1,
                         'open': True, 'reason': reason})
    plan.sort(key=lambda p: -p['score'])
    return plan


# ─── CONSEILS DÉTERMINISTES ──────────────────────────────────────────────────

def build_hints(cdef, clock, stats, plan):
    """Conseils actionnables, du plus urgent au moins urgent.
    level : 'alerte' (agir maintenant) / 'action' / 'info'."""
    hints = []
    cdef = cdef or {}
    status = clock.get('status')

    if status == 'avant':
        h = clock.get('starts_in_h')
        if h is not None and h <= 48:
            hints.append({'level': 'info', 'icon': '⏳',
                          'text': f"Départ dans {h:.0f} h — passe la CHECKLIST du logbook "
                                  f"(bouton ✅) : config, heure synchronisée, postes connectés."})
        return hints

    if status == 'termine':
        deadline = cdef.get('log_deadline', '')
        submit = cdef.get('log_submit', '')
        txt = "Concours terminé — exporte ton log (📥 dans le LOGBOOK) et envoie-le"
        if deadline:
            txt += f" (deadline : {deadline})"
        if submit:
            txt += f" → {submit}"
        hints.append({'level': 'alerte', 'icon': '📤', 'text': txt})
        return hints

    if status != 'en_cours':
        hints.append({'level': 'info', 'icon': '⚙️',
                      'text': "Aucun concours actif configuré — passe par CONFIG "
                              "pour choisir le concours et ses dates."})
        return hints

    # ── En cours ─────────────────────────────────────────────────────────────
    remaining = clock.get('remaining_h', 0)

    # Silence radio
    silent = stats.get('minutes_since_last')
    if silent is not None and silent >= 15:
        hints.append({'level': 'alerte', 'icon': '🔇',
                      'text': f"Aucun QSO depuis {silent} min — change de bande ou de "
                              f"fréquence, lance appel, ou va chercher les spots classés."})

    # Rythme
    rate = stats.get('rate_avg')
    last_h = stats.get('qso_last_hour', 0)
    if rate and last_h < rate * 0.5 and stats.get('qso_total', 0) >= 10:
        hints.append({'level': 'action', 'icon': '📉',
                      'text': f"Rythme en baisse : {last_h} QSO sur la dernière heure "
                              f"contre {rate:.0f}/h de moyenne — change quelque chose "
                              f"(bande, cap d'antenne, recherche→appel)."})

    # Budget d'opération (off-time WAE : 36 h sur 48)
    max_op = cdef.get('op_time_max_h')
    if max_op:
        op_left = max_op - stats.get('hours_operated', 0)
        if op_left <= 0:
            hints.append({'level': 'alerte', 'icon': '⛔',
                          'text': f"Budget d'opération épuisé ({max_op} h max) — toute "
                                  f"heure supplémentaire peut invalider ton log."})
        elif op_left < remaining:
            hints.append({'level': 'action', 'icon': '⏸️',
                          'text': f"Il te reste {op_left:.0f} h d'opération autorisées pour "
                                  f"{remaining:.0f} h de concours — planifie "
                                  f"{remaining - op_left:.0f} h de pause dans les creux "
                                  f"(pauses de 60 min minimum)."})

    # QTC (WAE) — compteur réel depuis le logbook (bouton ✉ QTC)
    if cdef.get('qtc'):
        qtc = stats.get('qtc_total', 0)
        hints.append({'level': 'action', 'icon': '📨',
                      'text': (f"QTC échangés : {qtc} (+{qtc} pts au score final). " if qtc else
                               "Pense aux QTC : chaque QTC transféré vaut 1 point ") +
                              "Max 10 par station — autant que des QSO gratuits."})

    # Bande la plus payante maintenant
    if plan:
        best = plan[0]
        if best.get('weight', 1) > 1 and best.get('open'):
            hints.append({'level': 'action', 'icon': '🎯',
                          'text': f"{best['band']} MHz est ouverte ET compte ses mults "
                                  f"×{best['weight']} — c'est la bande la plus rentable "
                                  f"à cette heure."})

    # Fin de course : chasse aux mults
    bricks = (cdef.get('scoring', {}) or {}).get('bricks', {}) or {}
    has_mult = bool(bricks.get('multiplier')) or bool(bricks.get('mult_weight_by_band'))
    if remaining <= 2 and has_mult:
        hints.append({'level': 'action', 'icon': '🏁',
                      'text': f"Dernières {remaining:.1f} h : un multiplicateur nouveau vaut "
                              f"plus que des QSO en série — chasse les mults manquants "
                              f"dans les spots PRIORITÉ MAX."})
    elif remaining <= 1:
        hints.append({'level': 'info', 'icon': '🏁',
                      'text': "Dernière heure — logge tout, on trie après."})

    return hints


# ─── MULTIPLICATEUR PAR ÉCHANGE (EUHFC) ──────────────────────────────────────

def exchange_mult_stats(cdef, shared_log, contest_id):
    """Décompte EXACT du multiplicateur 'exchange_distinct' depuis le log :
    valeurs à 2 chiffres distinctes reçues, une fois par bande (EUHFC §6).
    Retourne {'mults': N, 'score_est': pts × N} ou None si non applicable."""
    import re as _re
    mult = ((cdef.get('scoring', {}) or {}).get('bricks', {}) or {}).get('multiplier')
    if not (isinstance(mult, dict) and mult.get('kind') == 'exchange_distinct'):
        return None
    seen = set()
    pts = 0
    for q in shared_log or []:
        if contest_id and q.get('contest', '') not in ('', contest_id):
            continue
        pts += q.get('points', 0) or 0
        m = _re.search(r'(\d{2})\s*$', str(q.get('num_rcvd', '')).strip())
        if m:
            seen.add((str(q.get('band', '')), m.group(1)))
    return {'mults': len(seen), 'score_est': pts * max(len(seen), 1)}


# ─── PRÉVISION SPORADIQUE-E / AURORA (VHF) ───────────────────────────────────

def es_aurora_forecast(cdef, dxmaps=None, k_index=None, now=None):
    """Prévision VHF, distincte du CONFIRMÉ (DXMaps).
    - Es : heuristique saisonnière (mai-août, pics matin ~08-11 et soir ~17-21 UTC)
      sur 6 m et 2 m.
    - Aurora : dérivée de l'indice K (>=5 = orage géomagnétique → aurora VHF).
    Retourne une liste de dicts {kind, level, text} ou []."""
    now = now or datetime.datetime.utcnow()
    bands = [str(b) for b in (cdef or {}).get('bands', [])]
    is_vhf = any(b in ('50', '70', '144') for b in bands)
    out = []

    # ── Sporadique-E : saison + créneaux horaires ──
    if is_vhf and now.month in (5, 6, 7, 8):   # cœur de la saison Es en Europe
        h = now.hour
        peak = (8 <= h <= 11) or (17 <= h <= 21)   # doubles pics matin/soir
        es_confirmed = bool((dxmaps or {}).get('es_active'))
        if es_confirmed:
            out.append({'kind': 'es', 'level': 'confirme',
                        'text': "⚡ SPORADIQUE-E CONFIRMÉ (DXMaps) — surveille 6 m puis 2 m, "
                                "les ouvertures montent en fréquence."})
        elif peak:
            out.append({'kind': 'es', 'level': 'probable',
                        'text': f"🌤 Es PROBABLE (saison + créneau {h}h UTC) — garde un œil "
                                f"sur 50.150-50.300, ça peut ouvrir d'un coup vers 800-2000 km."})
        else:
            out.append({'kind': 'es', 'level': 'possible',
                        'text': "Saison Es : ouverture possible à tout moment sur 6 m, "
                                "pics probables en matinée et fin d'après-midi (UTC)."})

    # ── Aurora : indice K ──
    try:
        k = float(k_index) if k_index not in (None, '') else None
    except (ValueError, TypeError):
        k = None
    if k is not None:
        if k >= 7:
            out.append({'kind': 'aurora', 'level': 'fort',
                        'text': f"🔴 K={k:.0f} ORAGE GÉOMAGNÉTIQUE — aurora VHF probable "
                                f"(antennes vers le NORD, signaux 'raspy'), mais HF bandes "
                                f"hautes perturbées."})
        elif k >= 5:
            out.append({'kind': 'aurora', 'level': 'possible',
                        'text': f"🟡 K={k:.0f} — aurora VHF possible, tente le nord sur 2 m "
                                f"(polarisation aléatoire)."})
    return out


# ─── RUN vs SEARCH & POUNCE ──────────────────────────────────────────────────

def run_sp_recommendation(clock, stats, mult_spots_count=None):
    """Recommandation de mode d'opération, avec justification courte.
    RUN = lancer appel CQ (rendement quand ça tourne) ;
    S&P = chasser les spots (rendement quand le rate tombe et que des
    multiplicateurs sont disponibles sur le cluster)."""
    if clock.get('status') != 'en_cours':
        return None
    r10 = stats.get('rate_10min') or 0
    r60 = stats.get('rate_60min') or 0
    mults = mult_spots_count if mult_spots_count is not None else 0
    if stats.get('qso_total', 0) < 5:
        return {'mode': 'S&P', 'reason': "Début de course : chasse les spots pour "
                                         "amorcer le log, tu passeras en RUN quand ça mord."}
    if r10 >= max(r60, 30):
        return {'mode': 'RUN', 'reason': f"{r10}/h sur 10 min — la fréquence tourne, "
                                         f"reste en RUN (appel CQ)."}
    if r10 < r60 * 0.6 and mults >= 3:
        return {'mode': 'S&P', 'reason': f"Rate en chute ({r10}/h contre {r60}/h) et "
                                         f"{mults} nouveaux mults sur le cluster — "
                                         f"passe en Search & Pounce."}
    if r10 <= 6 and mults == 0:
        return {'mode': 'CHANGE', 'reason': f"{r10}/h et aucun mult spotté — change de "
                                            f"bande (regarde le plan de bande et la MUF)."}
    if r10 >= r60:
        return {'mode': 'RUN', 'reason': f"Rate stable ({r10}/h) — garde la fréquence."}
    return {'mode': 'S&P', 'reason': f"Rate mou ({r10}/h) — alterne : un tour de "
                                     f"cluster puis retour en appel."}


# ─── PROMPT POUR LE CONSEIL IA ───────────────────────────────────────────────

def build_coach_prompt(cdef, clock, stats, plan, hints):
    """Contexte compact pour un conseil stratégique narratif via /proxy/ai."""
    lines = ["CONSEIL STRATÉGIQUE DEMANDÉ — voici l'état exact du concours :", ""]
    lines.append(f"Concours : {clock.get('contest_name') or clock.get('contest_id') or '?'}")
    if clock.get('status') == 'en_cours':
        lines.append(f"Temps : {clock['elapsed_h']:.1f} h faites, "
                     f"{clock['remaining_h']:.1f} h restantes ({clock['pct_done']}%)")
    else:
        lines.append(f"Statut : {clock.get('status')}")
    lines.append(f"Log : {stats['qso_total']} QSO, {stats['score']} pts"
                 + (f", moyenne {stats['rate_avg']}/h" if stats.get('rate_avg') else '')
                 + f", dernière heure {stats.get('qso_last_hour', 0)} QSO")
    if stats.get('exchange_mults') is not None:
        lines.append(f"Multiplicateurs (échanges distincts/bande) : "
                     f"{stats['exchange_mults']} → score estimé "
                     f"{stats.get('score_with_mults', 0)} pts")
    if stats.get('departments') is not None:
        lines.append(f"Départements français reçus : {stats['departments']} "
                     f"(multiplicateur REF, + DXCC)")
    if stats.get('by_band'):
        rep = ', '.join(f"{b}: {n}" for b, n in sorted(stats['by_band'].items()))
        lines.append(f"Par bande : {rep}")
    if plan:
        lines.append("Plan de bande maintenant : "
                     + ' | '.join(f"{p['band']} MHz ({p['reason']})" for p in plan[:3]))
    if hints:
        lines.append("Constats du coach : "
                     + ' / '.join(h['text'] for h in hints[:4]))
    lines.append("")
    lines.append("Donne 3 ACTIONS CONCRÈTES et immédiates pour maximiser le score, "
                 "en tenant compte du barème exact de ce concours. Sois bref et directif.")
    return '\n'.join(lines)


# ─── POINT D'ENTRÉE ──────────────────────────────────────────────────────────

def build_coach_state(cfg, shared_log, dxmaps=None, now=None, mult_spots_count=None,
                      k_index=None):
    """État complet du coach — JSON structuré pour le front, sans appel IA.
    mult_spots_count : nombre de « nouveau mult » actuellement spottés
    (fourni par le serveur depuis les caches cluster, pour la reco Run/S&P)."""
    now = now or datetime.datetime.utcnow()
    contest_id = (cfg or {}).get('contest', '')
    cdef = CONTEST_DEFINITIONS.get(contest_id, {}) if isinstance(contest_id, str) else {}
    clock = contest_clock(cfg, cdef, now)
    stats = log_stats(shared_log, clock['contest_id'], clock, now)
    if cdef.get('qtc'):
        from radiocontest_storage import qtc_total
        stats['qtc_total'] = qtc_total(clock['contest_id'])
    # Multiplicateur département (concours REF « dept_dxcc ») : compté depuis
    # les échanges reçus (le département n'est pas dans l'indicatif métropolitain).
    scoring_type = (cdef.get('scoring', {}) or {}).get('type', '')
    if scoring_type == 'dept_dxcc':
        from radiocontest_departments import department_mult_count
        depts = department_mult_count(shared_log, clock['contest_id'])
        stats['departments'] = len(depts)
        stats['departments_list'] = sorted(depts)
    ex_mults = exchange_mult_stats(cdef, shared_log, clock['contest_id'])
    if ex_mults:
        stats['exchange_mults'] = ex_mults['mults']
        stats['score_with_mults'] = ex_mults['score_est']
    plan = band_plan(cdef, clock, dxmaps, now)
    hints = build_hints(cdef, clock, stats, plan)
    run_sp = run_sp_recommendation(clock, stats, mult_spots_count)
    vhf_forecast = es_aurora_forecast(cdef, dxmaps, k_index, now)
    return {
        'clock': clock,
        'stats': stats,
        'band_plan': plan,
        'hints': hints,
        'run_sp': run_sp,
        'vhf_forecast': vhf_forecast,
        'mult_spots_count': mult_spots_count,
        'coach_prompt': build_coach_prompt(cdef, clock, stats, plan, hints),
    }
