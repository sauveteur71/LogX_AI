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

from logx_definitions import CONTEST_DEFINITIONS
from logx_coach_i18n import t
from logx_storage import qso_scope_id, active_scope_id, cfg_scope_id
from logx_utils import utcnow

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
    now = now or utcnow()
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
    # AUCUN CONCOURS SÉLECTIONNÉ : on s'arrête là, sans regarder les dates.
    #
    # DÉFAUT SIGNALÉ PAR L'UTILISATEUR : « pourquoi l'IA met ça alors que je
    # suis sans concours ! » Les dates d'un concours PRÉCÉDENT survivent dans
    # la configuration ; l'horloge les lisait sans vérifier qu'une épreuve est
    # réellement choisie, annonçait « départ dans 18,2 h », et le coach
    # enchaînait sur la checklist d'avant-concours. Le contenu était cohérent,
    # il ne portait simplement sur rien.
    if not contest_id.strip():
        clock['status'] = 'sans_concours'
        return clock
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


# 72 h : plus long que le plus long des concours (48 h pour un CQ WW), assez
# court pour que la série reste minuscule. Voir hourly_rate_series.
HEURES_RYTHME_MAX = 72


def hourly_rate_series(entries, heures_max=HEURES_RYTHME_MAX):
    """Nombre de QSO par heure UTC sur les `heures_max` dernières heures d'activité
    — les heures sans QSO comptent 0 (pas de trou dans un graphe de rythme),
    contrairement aux compteurs glissants qso_last_hour/qso_last_10min qui ne
    montrent que l'instant présent.

    LA BORNE N'EST PAS COSMÉTIQUE. Sans elle, la série allait du PREMIER au
    DERNIER QSO du log : sur un carnet de vie entière commencé en 2011, cela
    fait 131 104 tranches horaires, presque toutes à zéro. `/coach/state` pesait
    alors 5,5 Mo — et le panneau coach détachable l'interroge TOUTES LES 15 s,
    soit 22 Mo par minute à sérialiser puis à analyser dans le navigateur, en
    permanence. Pour une donnée qu'aucune page n'affiche aujourd'hui.

    Mesuré sur le log réel de ce poste : 131 104 tranches -> 72.
    """
    buckets = {}
    for e in entries:
        dt = _entry_dt(e)
        if not dt:
            continue
        key = dt.replace(minute=0, second=0, microsecond=0)
        buckets[key] = buckets.get(key, 0) + 1
    if not buckets:
        return []
    end = max(buckets)
    # On coupe par le DÉBUT : un graphe de rythme se lit vers le présent, et
    # c'est la dernière heure qui intéresse l'opérateur, pas la première.
    start = max(min(buckets), end - datetime.timedelta(hours=max(1, int(heures_max)) - 1))
    series = []
    cur = start
    while cur <= end:
        series.append({'hour': cur.strftime('%Y-%m-%d %H:00'), 'count': buckets.get(cur, 0)})
        cur += datetime.timedelta(hours=1)
    return series


def log_stats(shared_log, contest_id='', clock=None, now=None):
    """Rythme et répartition : QSO/h global, dernière heure, silence radio,
    heures opérées (pour le budget off-time), répartition par bande.
    `contest_id` est une PORTÉE (voir logx_storage.active_scope_id), pas le nom
    brut du concours — un QSO non tagué ne compte jamais pour une portée précise."""
    now = now or utcnow()
    entries = [e for e in (shared_log or [])
               if not contest_id or qso_scope_id(e) == contest_id]
    stats = {
        'qso_total': len(entries),
        'score': sum(e.get('points', 0) or 0 for e in entries),
        'by_band': {},
        'qso_last_hour': 0,
        'qso_last_10min': 0,
        'rate_avg': None,
        'minutes_since_last': None,
        'hours_operated': 0,
        'hourly_rate': hourly_rate_series(entries),
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


# ─── RÈGLE DES 10 MINUTES (MULTI-SINGLE) ─────────────────────────────────────

DEFAULT_BAND_CHANGE_RULE_MIN = 10


def band_change_timer(shared_log, contest_id='', now=None,
                      rule_minutes=DEFAULT_BAND_CHANGE_RULE_MIN):
    """Compte à rebours de la « règle des 10 minutes » (Multi-Single CQ WW et
    règlements similaires) : un changement de bande n'est autorisé qu'une fois
    toutes les `rule_minutes` minutes. Le compte à rebours démarre au premier
    QSO loggué sur une bande DIFFÉRENTE de la précédente — un vrai changement,
    jamais le tout premier QSO du concours (aucune contrainte ne s'applique
    tant qu'aucun changement n'a encore eu lieu : `ready`=True, changed_at=None).
    `contest_id` est une PORTÉE (voir logx_storage.active_scope_id), pas le nom
    brut du concours. Déterministe, aucun appel réseau.

    NB : le champ `time` d'un QSO n'a qu'une précision à la minute — l'instant
    exact du changement (et donc le compte à rebours) peut dériver de quelques
    dizaines de secondes, sans conséquence pour un simple indicateur."""
    now = now or utcnow()
    entries = [e for e in (shared_log or [])
               if not contest_id or qso_scope_id(e) == contest_id]
    dated = []
    for e in entries:
        dt = _entry_dt(e)
        if dt:
            dated.append((dt, str(e.get('band', '?'))))
    dated.sort(key=lambda x: x[0])

    base = {'current_band': None, 'changed_at': None, 'elapsed_s': None,
            'remaining_s': 0, 'ready': True, 'rule_minutes': rule_minutes}
    if not dated:
        return base

    current_band = dated[-1][1]
    changed_at = None
    for i in range(1, len(dated)):
        if dated[i][1] != dated[i - 1][1]:
            changed_at = dated[i][0]
    if changed_at is None:
        return {**base, 'current_band': current_band}

    elapsed_s = (now - changed_at).total_seconds()
    remaining_s = max(0, rule_minutes * 60 - elapsed_s)
    return {
        'current_band': current_band,
        'changed_at': changed_at.strftime('%Y-%m-%d %H:%M:%S'),
        'elapsed_s': int(elapsed_s),
        'remaining_s': int(remaining_s),
        'ready': remaining_s <= 0,
        'rule_minutes': rule_minutes,
    }


# ─── PLAN DE BANDE ───────────────────────────────────────────────────────────

def _hf_bands_for_hour(hour_utc):
    """Heuristique propagation HF Europe : bandes ouvertes selon l'heure UTC."""
    if 21 <= hour_utc or hour_utc < 4:      # nuit
        return ['1.8', '3.5', '7']
    if 4 <= hour_utc < 7 or 17 <= hour_utc < 21:  # grey line / transition
        return ['3.5', '7', '14']
    return ['14', '21', '28']               # plein jour


def band_plan(cdef, clock, dxmaps=None, now=None, lang='fr'):
    """Bandes recommandées MAINTENANT, pondérées par le barème du concours.
    Retourne [{band, weight, reason}] trié par intérêt décroissant."""
    now = now or utcnow()
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
            reason = t(lang, 'band_open') if is_open else t(lang, 'band_closed')
            if w > 1:
                reason += t(lang, 'mult_suffix', w=w)
            plan.append({'band': b, 'score': score, 'weight': w,
                         'open': is_open, 'reason': reason})
    else:  # VHF+ : la bande principale reste reine, Es/tropo en bonus
        es = bool((dxmaps or {}).get('es_active'))
        tropo = bool((dxmaps or {}).get('tropo_active'))
        for b in bands:
            reason = t(lang, 'band_contest')
            score = 5
            if es and b in ('50', '144'):
                score, reason = 12, t(lang, 'band_es')
            elif tropo:
                score, reason = 10, t(lang, 'band_tropo')
            plan.append({'band': b, 'score': score, 'weight': 1,
                         'open': True, 'reason': reason})
    plan.sort(key=lambda p: -p['score'])
    return plan


# ─── CONSEILS DÉTERMINISTES ──────────────────────────────────────────────────

def build_hints(cdef, clock, stats, plan, lang='fr'):
    """Conseils actionnables, du plus urgent au moins urgent.
    level : 'alerte' (agir maintenant) / 'action' / 'info'."""
    hints = []
    cdef = cdef or {}
    status = clock.get('status')

    # Pas de concours choisi : aucun conseil d'épreuve n'a de sens. Le coach
    # se tait ici plutôt que d'inventer un contexte — la carte IA et les
    # suggestions « jamais travaillé » restent, elles, pertinentes en trafic
    # courant.
    if status == 'sans_concours':
        return hints

    if status == 'avant':
        h = clock.get('starts_in_h')
        if h is not None and h <= 48:
            hints.append({'level': 'info', 'icon': '⏳',
                          'text': t(lang, 'hint_checklist', h=h)})
        return hints

    if status == 'termine':
        deadline = cdef.get('log_deadline', '')
        submit = cdef.get('log_submit', '')
        txt = t(lang, 'hint_finished_base')
        if deadline:
            txt += t(lang, 'hint_finished_deadline', deadline=deadline)
        if submit:
            txt += t(lang, 'hint_finished_submit', submit=submit)
        hints.append({'level': 'alerte', 'icon': '📤', 'text': txt})
        return hints

    if status != 'en_cours':
        hints.append({'level': 'info', 'icon': '⚙️',
                      'text': t(lang, 'hint_no_contest')})
        return hints

    # ── En cours ─────────────────────────────────────────────────────────────
    remaining = clock.get('remaining_h', 0)

    # Silence radio
    silent = stats.get('minutes_since_last')
    if silent is not None and silent >= 15:
        hints.append({'level': 'alerte', 'icon': '🔇',
                      'text': t(lang, 'hint_silence', min=silent)})

    # Rythme
    rate = stats.get('rate_avg')
    last_h = stats.get('qso_last_hour', 0)
    if rate and last_h < rate * 0.5 and stats.get('qso_total', 0) >= 10:
        hints.append({'level': 'action', 'icon': '📉',
                      'text': t(lang, 'hint_rate_drop', last_h=last_h, rate=rate)})

    # Budget d'opération (off-time WAE : 36 h sur 48)
    max_op = cdef.get('op_time_max_h')
    if max_op:
        op_left = max_op - stats.get('hours_operated', 0)
        if op_left <= 0:
            hints.append({'level': 'alerte', 'icon': '⛔',
                          'text': t(lang, 'hint_optime_over', max_op=max_op)})
        elif op_left < remaining:
            hints.append({'level': 'action', 'icon': '⏸️',
                          'text': t(lang, 'hint_optime_plan', op_left=op_left,
                                    remaining=remaining, pause=remaining - op_left)})

    # QTC (WAE) — compteur réel depuis le logbook (bouton ✉ QTC)
    if cdef.get('qtc'):
        qtc = stats.get('qtc_total', 0)
        txt = t(lang, 'hint_qtc_done', qtc=qtc) if qtc else t(lang, 'hint_qtc_todo')
        txt += t(lang, 'hint_qtc_tail')
        hints.append({'level': 'action', 'icon': '📨', 'text': txt})

    # Bande la plus payante maintenant
    if plan:
        best = plan[0]
        if best.get('weight', 1) > 1 and best.get('open'):
            hints.append({'level': 'action', 'icon': '🎯',
                          'text': t(lang, 'hint_best_band',
                                    band=best['band'], w=best['weight'])})

    # Fin de course : chasse aux mults
    bricks = (cdef.get('scoring', {}) or {}).get('bricks', {}) or {}
    has_mult = bool(bricks.get('multiplier')) or bool(bricks.get('mult_weight_by_band'))
    if remaining <= 2 and has_mult:
        hints.append({'level': 'action', 'icon': '🏁',
                      'text': t(lang, 'hint_endgame', remaining=remaining)})
    elif remaining <= 1:
        hints.append({'level': 'info', 'icon': '🏁',
                      'text': t(lang, 'hint_last_hour')})

    return hints


# ─── MULTIPLICATEUR PAR ÉCHANGE (EUHFC) ──────────────────────────────────────

def exchange_mult_stats(cdef, shared_log, contest_id):
    """Décompte EXACT du multiplicateur 'exchange_distinct' depuis le log :
    valeurs à 2 chiffres distinctes reçues, une fois par bande (EUHFC §6).
    Retourne {'mults': N, 'score_est': pts × N} ou None si non applicable.
    `contest_id` est une PORTÉE (voir logx_storage.active_scope_id)."""
    import re as _re
    mult = ((cdef.get('scoring', {}) or {}).get('bricks', {}) or {}).get('multiplier')
    if not (isinstance(mult, dict) and mult.get('kind') == 'exchange_distinct'):
        return None
    seen = set()
    pts = 0
    for q in shared_log or []:
        if contest_id and qso_scope_id(q) != contest_id:
            continue
        pts += q.get('points', 0) or 0
        m = _re.search(r'(\d{2})\s*$', str(q.get('num_rcvd', '')).strip())
        if m:
            seen.add((str(q.get('band', '')), m.group(1)))
    return {'mults': len(seen), 'score_est': pts * max(len(seen), 1)}


# ─── PRÉVISION SPORADIQUE-E / AURORA (VHF) ───────────────────────────────────

def es_aurora_forecast(cdef, dxmaps=None, k_index=None, now=None, lang='fr'):
    """Prévision VHF, distincte du CONFIRMÉ (DXMaps).
    - Es : heuristique saisonnière (mai-août, pics matin ~08-11 et soir ~17-21 UTC)
      sur 6 m et 2 m.
    - Aurora : dérivée de l'indice K (>=5 = orage géomagnétique → aurora VHF).
    Retourne une liste de dicts {kind, level, text} ou []."""
    now = now or utcnow()
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
                        'text': t(lang, 'es_confirmed')})
        elif peak:
            out.append({'kind': 'es', 'level': 'probable',
                        'text': t(lang, 'es_probable', h=h)})
        else:
            out.append({'kind': 'es', 'level': 'possible',
                        'text': t(lang, 'es_possible')})

    # ── Aurora : indice K ──
    try:
        k = float(k_index) if k_index not in (None, '') else None
    except (ValueError, TypeError):
        k = None
    if k is not None and k >= 5:
        if is_vhf:
            lvl = 'fort' if k >= 7 else 'possible'
            prefix = t(lang, 'aurora_vhf_storm', k=k) if k >= 7 else t(lang, 'aurora_vhf_mild', k=k)
            out.append({'kind': 'aurora', 'level': lvl,
                        'text': prefix + t(lang, 'aurora_vhf_tail')})
        elif k >= 6:
            # Concours HF : l'aurora ne se travaille pas, mais elle DÉGRADE la HF
            out.append({'kind': 'aurora', 'level': 'info',
                        'text': t(lang, 'aurora_hf', k=k)})
    return out


# ─── RUN vs SEARCH & POUNCE ──────────────────────────────────────────────────

def run_sp_recommendation(clock, stats, mult_spots_count=None, lang='fr'):
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
        return {'mode': 'S&P', 'reason': t(lang, 'sp_start')}
    if r10 >= max(r60, 30):
        return {'mode': 'RUN', 'reason': t(lang, 'run_hot', r10=r10)}
    if r10 < r60 * 0.6 and mults >= 3:
        return {'mode': 'S&P', 'reason': t(lang, 'sp_drop', r10=r10, r60=r60, mults=mults)}
    if r10 <= 6 and mults == 0:
        return {'mode': 'CHANGE', 'reason': t(lang, 'change_band', r10=r10)}
    if r10 >= r60:
        return {'mode': 'RUN', 'reason': t(lang, 'run_stable', r10=r10)}
    return {'mode': 'S&P', 'reason': t(lang, 'sp_soft', r10=r10)}


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


# ─── DÉBRIEF POST-CONCOURS ───────────────────────────────────────────────────

def build_debrief(cfg, shared_log, now=None):
    """Statistiques DÉTERMINISTES du concours écoulé + prompt prêt pour un
    débrief narratif par l'IA (/proxy/ai côté client).
    Retourne {'stats': {...}, 'debrief_prompt': str}."""
    now = now or utcnow()
    cfg = cfg or {}
    contest_id = cfg.get('contest', '') if isinstance(cfg.get('contest'), str) else ''
    cdef = CONTEST_DEFINITIONS.get(contest_id, {})
    clock = contest_clock(cfg, cdef, now)
    scope_id = cfg_scope_id(cfg)
    entries = [e for e in (shared_log or [])
               if not scope_id or qso_scope_id(e) == scope_id]

    from logx_utils import locator_to_latlon, haversine
    my_loc = str(cfg.get('locator', '')).strip().upper()
    my_lat, my_lon = locator_to_latlon((my_loc + 'MM')[:6]) if len(my_loc) >= 4 else (None, None)

    per_hour = {}                  # 'JJ HHh' -> n QSO
    per_band = {}                  # bande -> {qso, km, best_km, best_call, locators}
    timeline = []                  # datetimes triés pour les silences
    score = 0
    for e in entries:
        score += e.get('points', 0) or 0
        dt = _entry_dt(e)
        if dt:
            timeline.append(dt)
            per_hour[dt.strftime('%d/%m %Hh')] = per_hour.get(dt.strftime('%d/%m %Hh'), 0) + 1
        b = str(e.get('band', '?'))
        pb = per_band.setdefault(b, {'qso': 0, 'km': 0, 'best_km': 0,
                                     'best_call': '', 'locators': set()})
        pb['qso'] += 1
        loc = str(e.get('locator', '')).strip().upper()
        if loc and len(loc) >= 4:
            pb['locators'].add(loc[:4])
            if my_lat is not None:
                lat, lon = locator_to_latlon((loc + 'MM')[:6])
                if lat is not None:
                    km = haversine(my_lat, my_lon, lat, lon)
                    pb['km'] += km
                    if km > pb['best_km']:
                        pb['best_km'], pb['best_call'] = km, str(e.get('call', ''))

    # Silences > 30 min pendant le concours
    timeline.sort()
    silences = []
    for a, b in zip(timeline, timeline[1:]):
        gap = (b - a).total_seconds() / 60
        if gap >= 30:
            silences.append({'from': a.strftime('%d/%m %H:%M'),
                             'to': b.strftime('%d/%m %H:%M'), 'min': int(gap)})

    hours_sorted = sorted(per_hour.items(), key=lambda kv: -kv[1])
    stats = {
        'contest': contest_id,
        'contest_name': cdef.get('name', contest_id),
        'status': clock.get('status'),
        'qso_total': len(entries),
        'score': score,
        'per_hour': per_hour,
        'best_hours': hours_sorted[:3],
        'worst_hours': hours_sorted[-3:] if len(hours_sorted) > 3 else [],
        'per_band': {b: {**v, 'locators': len(v['locators'])}
                     for b, v in per_band.items()},
        'silences': silences[:10],
        'departments': None,
    }
    # Départements travaillés (concours REF à mult département)
    if ((cdef.get('scoring', {}) or {}).get('type', '')) == 'dept_dxcc':
        try:
            from logx_departments import department_mult_count
            depts = department_mult_count(shared_log, scope_id)
            stats['departments'] = len(depts)
        except Exception:
            pass

    # ── Prompt de débrief pour l'IA ──
    lines = ["DÉBRIEF POST-CONCOURS DEMANDÉ — voici le déroulé exact :", ""]
    lines.append(f"Concours : {stats['contest_name']} — {stats['qso_total']} QSO, "
                 f"{score} pts (statut : {clock.get('status')})")
    for b, v in sorted(stats['per_band'].items()):
        seg = f"{b} MHz : {v['qso']} QSO, {v['locators']} carrés locator"
        if v['km']:
            seg += f", {v['km']} km cumulés, ODX {v['best_km']} km ({v['best_call']})"
        lines.append(seg)
    if stats['departments'] is not None:
        lines.append(f"Départements travaillés : {stats['departments']} (mult REF)")
    if hours_sorted:
        lines.append("Meilleures heures : "
                     + ', '.join(f"{h} ({n} QSO)" for h, n in stats['best_hours']))
        if stats['worst_hours']:
            lines.append("Heures creuses : "
                         + ', '.join(f"{h} ({n} QSO)" for h, n in stats['worst_hours']))
    if silences:
        lines.append("Silences radio ≥ 30 min : "
                     + ' / '.join(f"{s['from']}→{s['to']} ({s['min']} min)"
                                  for s in silences[:6]))
    lines.append("")
    lines.append("Fais le débrief de ma participation : 1) trois points forts, "
                 "2) trois axes d'amélioration CONCRETS pour la prochaine édition "
                 "(bandes, horaires, stratégie RUN/S&P, cap d'antenne), "
                 "3) ce qui m'a coûté le plus de points. Sois direct et précis, "
                 "en t'appuyant sur les chiffres ci-dessus et le barème du concours.")
    return {'stats': stats, 'debrief_prompt': '\n'.join(lines)}


# ─── POINT D'ENTRÉE ──────────────────────────────────────────────────────────

def build_coach_state(cfg, shared_log, dxmaps=None, now=None, mult_spots_count=None,
                      k_index=None, lang='fr'):
    """État complet du coach — JSON structuré pour le front, sans appel IA.
    mult_spots_count : nombre de « nouveau mult » actuellement spottés
    (fourni par le serveur depuis les caches cluster, pour la reco Run/S&P).
    lang : langue des textes du coach (hints/reasons/forecasts) ; 'fr' par
    défaut. Le coach_prompt reste en français (le LLM répond dans la langue
    voulue via la directive du prompt système côté client)."""
    now = now or utcnow()
    contest_id = (cfg or {}).get('contest', '')
    cdef = CONTEST_DEFINITIONS.get(contest_id, {}) if isinstance(contest_id, str) else {}
    clock = contest_clock(cfg, cdef, now)
    # Portée QSO (contest+année, voir logx_storage.active_scope_id) : à utiliser
    # pour tout ce qui COMPTE des QSO du concours actif — clock['contest_id']
    # reste le nom brut (recherche de règles CONTEST_DEFINITIONS, affichage).
    scope_id = cfg_scope_id(cfg)
    stats = log_stats(shared_log, scope_id, clock, now)
    if cdef.get('qtc'):
        from logx_storage import qtc_total
        stats['qtc_total'] = qtc_total(scope_id)
    # Multiplicateur département (concours REF « dept_dxcc ») : compté depuis
    # les échanges reçus (le département n'est pas dans l'indicatif métropolitain).
    scoring_type = (cdef.get('scoring', {}) or {}).get('type', '')
    if scoring_type == 'dept_dxcc':
        from logx_departments import department_mult_count
        depts = department_mult_count(shared_log, scope_id)
        stats['departments'] = len(depts)
        stats['departments_list'] = sorted(depts)
    ex_mults = exchange_mult_stats(cdef, shared_log, scope_id)
    if ex_mults:
        stats['exchange_mults'] = ex_mults['mults']
        stats['score_with_mults'] = ex_mults['score_est']
    plan = band_plan(cdef, clock, dxmaps, now, lang)
    hints = build_hints(cdef, clock, stats, plan, lang)
    run_sp = run_sp_recommendation(clock, stats, mult_spots_count, lang)
    vhf_forecast = es_aurora_forecast(cdef, dxmaps, k_index, now, lang)
    # Règle des 10 minutes (multi-op M/S type CQ WW / CQ WPX) : seuls les
    # concours dont la définition porte explicitement `band_change_rule_min`
    # (voir logx_definitions.CONTEST_DEFINITIONS) appliquent réellement cette
    # contrainte — la plupart des concours (REF, EUHFC, WWA...) n'ont AUCUNE
    # règle de ce type. Avant ce correctif, band_change_timer() était appelé
    # pour N'IMPORTE QUEL concours multi-op : un faux compte à rebours de
    # 10 min s'affichait même là où les changements de bande sont libres. Le
    # tri "multi-op ou pas" reste un choix d'AFFICHAGE laissé au front (cf.
    # logx_statusbar.js) ; ici on ne calcule même pas si la règle ne s'applique
    # pas au concours actif.
    rule_minutes = cdef.get('band_change_rule_min')
    band_change = band_change_timer(shared_log, scope_id, now, rule_minutes) if rule_minutes else None
    return {
        'clock': clock,
        'stats': stats,
        'band_plan': plan,
        'hints': hints,
        'run_sp': run_sp,
        'vhf_forecast': vhf_forecast,
        'mult_spots_count': mult_spots_count,
        'band_change': band_change,
        'coach_prompt': build_coach_prompt(cdef, clock, stats, plan, hints),
    }
