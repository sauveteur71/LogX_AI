# -*- coding: utf-8 -*-
"""Suivi de diplômes & historique — le « carnet de trafic permanent ».

Contrairement au scoring (qui ne compte QUE le concours en cours), ce module
raisonne sur TOUTE la vie de la station : log actif + dossiers archives/ +
table SQLite qso_archive. Il fournit :

  - history(call)      : tous les QSO passés avec une station (panneau
                         « déjà contacté » à la frappe).
  - award_summary()    : tableau de bord travaillé / confirmé par diplôme
                         (DXCC pays, départements REF, continents, zones CQ).
  - new_one(call,band) : « nouveau pays / nouveau département » à VIE (pas
                         seulement dans le concours) — alerte pendant le trafic.

Le statut « confirmé » vient de qsl_confirmations.json (rempli par
logx_qsl à partir de LoTW / eQSL / ClubLog). Absent ⇒ 0 confirmé,
le reste fonctionne quand même (travaillé/manquant).
"""
import datetime
import json
import os
import threading
import time
from logx_utils import utcnow

TTL = 120
_cache = {'qsos': None, 'at': 0.0}
_lock = threading.Lock()

CONFIRM_FILE = 'qsl_confirmations.json'


# ─── COLLECTE DE TOUS LES QSO (log + archives + qso_archive) ──────────────────

def _dedup_key(q):
    return (str(q.get('call', '')).upper().strip(), str(q.get('band', '')),
            str(q.get('mode', '')).upper(), str(q.get('date', '')),
            str(q.get('time', '')))


def _read_archives():
    out = []
    try:
        from logx_archive import ARCHIVE_DIR
        if os.path.isdir(ARCHIVE_DIR):
            for name in os.listdir(ARCHIVE_DIR):
                logp = os.path.join(ARCHIVE_DIR, name, 'log.json')
                if os.path.isfile(logp):
                    try:
                        with open(logp, encoding='utf-8') as f:
                            for q in json.load(f) or []:
                                q.setdefault('_src', name)
                                out.append(q)
                    except Exception:
                        continue
    except Exception:
        pass
    return out


def _read_qso_archive():
    out = []
    try:
        import sqlite3
        if not os.path.isfile('logx.db'):
            return out
        con = sqlite3.connect('logx.db')
        try:
            rows = con.execute('SELECT call, band, mode, contest, date, time, '
                               'locator, extra FROM qso_archive').fetchall()
        except Exception:
            rows = []
        finally:
            con.close()
        for call, band, mode, contest, date, tm, locator, extra in rows:
            q = {'call': call, 'band': band, 'mode': mode, 'contest': contest,
                 'date': date, 'time': tm, 'locator': locator, '_src': 'qso_archive'}
            try:
                q.update(json.loads(extra or '{}') or {})
            except Exception:
                pass
            out.append(q)
    except Exception:
        pass
    return out


def collect_all_qsos(shared_log=None, force=False):
    """Tous les QSO de la station, dédupliqués, enrichis (pays/continent/dept).
    Caché TTL secondes ; invalidé par invalidate()."""
    with _lock:
        if not force and _cache['qsos'] is not None and time.time() - _cache['at'] < TTL:
            base = _cache['qsos']
        else:
            raw = []
            raw.extend(_read_qso_archive())     # anciens (moins prioritaires)
            raw.extend(_read_archives())
            seen, base = set(), []
            for q in raw:
                k = _dedup_key(q)
                if k in seen:
                    continue
                seen.add(k)
                base.append(_enrich(dict(q)))
            _cache['qsos'] = base
            _cache['at'] = time.time()
        # Le log actif est TOUJOURS ajouté frais (jamais mis en cache figé)
        seen = {_dedup_key(q) for q in base}
        merged = list(base)
        for q in (shared_log or []):
            k = _dedup_key(q)
            if k not in seen:
                seen.add(k)
                merged.append(_enrich(dict(q)))
        return merged


def invalidate():
    with _lock:
        _cache['qsos'] = None


_calldb = None


def _enrich(q):
    """Ajoute dxcc_country / continent / cq_zone / dept à un QSO."""
    global _calldb
    call = str(q.get('call', '')).upper().strip()
    base = call.split('/')[0] if '/' in call else call
    try:
        import logx_dxcc as dxcc
        info = dxcc.lookup(base) or {}
        q['dxcc_country'] = info.get('country')
        q['continent'] = info.get('continent')
        q['cq_zone'] = info.get('cq_zone')
    except Exception:
        q.setdefault('dxcc_country', None)
    try:
        from logx_departments import dept_for_qso, _load_calldb
        if _calldb is None:
            _calldb = _load_calldb()
        q['dept'] = dept_for_qso(q, _calldb)
    except Exception:
        q.setdefault('dept', None)
    return q


# ─── CONFIRMATIONS (LoTW / eQSL / ClubLog) ───────────────────────────────────

def _load_confirmations():
    try:
        with open(CONFIRM_FILE, encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _confirm_key(q):
    return f"{str(q.get('call','')).upper().strip()}|{q.get('band','')}|{str(q.get('mode','')).upper()}"


# ─── HISTORIQUE D'UNE STATION (panneau « déjà contacté ») ─────────────────────

def history(call, shared_log=None, limit=15):
    """Tous les QSO passés avec `call` (plus récents d'abord), avec statut
    confirmé. Retourne {call, count, confirmed, qsos:[...], bands, first, last}."""
    call = str(call or '').upper().strip()
    if len(call) < 3:
        return {'call': call, 'count': 0, 'qsos': []}
    base_target = call.split('/')[0] if '/' in call else call
    conf = _load_confirmations()
    rows = []
    for q in collect_all_qsos(shared_log):
        c = str(q.get('call', '')).upper().strip()
        if c != call and c.split('/')[0] != base_target:
            continue
        is_conf = bool(conf.get(_confirm_key(q)))
        rows.append({
            'date': q.get('date', ''), 'time': q.get('time', ''),
            'band': str(q.get('band', '')), 'mode': str(q.get('mode', '')),
            'contest': q.get('contest', ''), 'locator': q.get('locator', ''),
            'dept': q.get('dept'), 'confirmed': is_conf,
        })
    rows.sort(key=lambda r: (r['date'], r['time']), reverse=True)
    bands = sorted({r['band'] for r in rows if r['band']})
    dates = sorted(r['date'] for r in rows if r['date'])
    country = None
    dept = None
    for q in collect_all_qsos(shared_log):
        if str(q.get('call', '')).upper().split('/')[0] == base_target:
            country = country or q.get('dxcc_country')
            dept = dept or q.get('dept')
    return {
        'call': call, 'count': len(rows),
        'confirmed': sum(1 for r in rows if r['confirmed']),
        'bands': bands, 'country': country, 'dept': dept,
        'first': dates[0] if dates else None,
        'last': dates[-1] if dates else None,
        'qsos': rows[:limit],
    }


# ─── DÉTECTION « NOUVEAU À VIE » (pays / département) ─────────────────────────

def new_one(call, band='', mode='', shared_log=None):
    """Un QSO avec `call` sur `band` apporterait-il un NOUVEAU pays ou
    département jamais contacté (à vie) ? Renvoie une liste de dicts
    {type, scope, label} — vide si rien de neuf."""
    call = str(call or '').upper().strip()
    if len(call) < 3:
        return []
    base = call.split('/')[0] if '/' in call else call
    try:
        import logx_dxcc as dxcc
        info = dxcc.lookup(base) or {}
    except Exception:
        info = {}
    country = info.get('country')

    worked_countries, worked_ctry_band = set(), set()
    worked_depts = set()
    q_dept = None
    for q in collect_all_qsos(shared_log):
        c = q.get('dxcc_country')
        if c:
            worked_countries.add(c)
            worked_ctry_band.add((c, str(q.get('band', ''))))
        if q.get('dept'):
            worked_depts.add(q['dept'])
        if str(q.get('call', '')).upper().split('/')[0] == base and q.get('dept'):
            q_dept = q_dept or q['dept']

    out = []
    if country and country not in worked_countries:
        out.append({'type': 'dxcc', 'scope': 'atlantic',
                    'label': f"NOUVEAU PAYS : {country} (jamais contacté)"})
    elif country and band and (country, str(band)) not in worked_ctry_band:
        out.append({'type': 'dxcc', 'scope': 'band',
                    'label': f"{country} nouveau sur {band} MHz"})
    # Département connu de la station (via calldb) et jamais contacté
    if not q_dept:
        try:
            from logx_departments import _load_calldb, DEPARTMENTS
            entry = (_load_calldb() or {}).get(base, {})
            d = entry.get('dept')
            if d in DEPARTMENTS:
                q_dept = d
        except Exception:
            pass
    if q_dept and q_dept not in worked_depts:
        try:
            from logx_departments import DEPARTMENTS
            nm = DEPARTMENTS.get(q_dept, '')
        except Exception:
            nm = ''
        out.append({'type': 'dept', 'scope': 'atlantic',
                    'label': f"NOUVEAU DÉPARTEMENT : {q_dept} {nm}"})
    return out


# ─── BESOINS LoTW PAR CRÉNEAU ENTITÉ × BANDE × MODE ──────────────────────────
# DEMANDE UTILISATEUR, mot pour mot : « même si je les ai contactés ça
# m'apporte rien, je veux une alerte jusqu'à ce que j'aie le DXCC confirmé par
# LoTW et pas autre chose, car ça n'a pas de valeur ».
#
# C'est un CHANGEMENT DE CRITÈRE, pas un affichage de plus. new_one() ci-dessus
# répond à « jamais CONTACTÉ » ; ici on répond à « pas encore CONFIRMÉ PAR
# LoTW », ce qui est la seule chose que l'ARRL accepte. Un QSO confirmé par
# eQSL ou par carte papier reste donc un BESOIN pour ce calcul — d'où le
# filtrage explicite sur la source, et pas un simple « il y a une
# confirmation ».
#
# Second changement : l'axe MODE. new_one() ne connaît que (entité, bande) ;
# le DXCC se poursuit par créneau entité × bande × mode (CW / Phonie /
# Numérique), et c'est à ce grain que se décide un appel.

LOTW_SOURCE = 'lotw'


def _creneaux_confirmes_lotw(qsos, conf):
    """{(entité, bande, catégorie de mode)} confirmés PAR LoTW uniquement."""
    out = set()
    for q in qsos:
        srcs = conf.get(_confirm_key(q)) or {}
        if not srcs.get(LOTW_SOURCE):
            continue
        pays = q.get('dxcc_country')
        if pays:
            out.add((pays, str(q.get('band', '')), _mode_category(q.get('mode'))))
    return out


def besoin_lotw(call, band='', mode='', shared_log=None):
    """Ce QSO comblerait-il un créneau entité×bande×mode non confirmé LoTW ?

    Retourne {'besoin': bool, 'country', 'band', 'mode_cat', 'label', 'raison'}
    — 'raison' vaut 'jamais_confirme' si l'entité n'est confirmée LoTW sur
    AUCUNE bande/mode (le plus intéressant), 'creneau' si elle l'est ailleurs
    mais pas ici.
    """
    call = str(call or '').upper().strip()
    if len(call) < 3:
        return {'besoin': False}
    base = call.split('/')[0] if '/' in call else call
    try:
        import logx_dxcc as dxcc
        pays = (dxcc.lookup(base) or {}).get('country')
    except Exception:
        pays = None
    if not pays:
        return {'besoin': False}

    cat = _mode_category(mode, freq_mhz=None)
    b = str(band or '')
    conf = _load_confirmations()
    creneaux = _creneaux_confirmes_lotw(collect_all_qsos(shared_log), conf)
    if (pays, b, cat) in creneaux:
        return {'besoin': False, 'country': pays, 'band': b, 'mode_cat': cat}

    jamais = not any(c[0] == pays for c in creneaux)
    label = (f"{pays} — JAMAIS confirmé LoTW" if jamais
             else f"{pays} — pas confirmé LoTW en {cat} sur {b} MHz")
    return {'besoin': True, 'country': pays, 'band': b, 'mode_cat': cat,
            'raison': 'jamais_confirme' if jamais else 'creneau',
            'label': label}


def carres_travailles(shared_log=None, bande=''):
    """Carrés QRA (4 caractères) travaillés, pour la carte VUCC.

    Retourne {'squares': [{'g','n','conf','bands'}], 'total', 'confirmed'} —
    `g` le carré, `n` le nombre de QSO, `conf` s'il est confirmé, `bands` les
    bandes où il a été travaillé.

    LE COMPTE PAR CARRÉ N'EST PAS DÉCORATIF : sur la carte, un carré touché une
    seule fois et un carré travaillé cinquante fois se ressemblent. Pour un
    collectionneur de carrés, le premier est le plus fragile — c'est celui dont
    la confirmation manque le plus souvent.

    Le filtre `bande` sert au VUCC, qui s'obtient bande par bande (100 carrés
    en 6 m, en 2 m…) et jamais toutes bandes confondues.
    """
    conf = _load_confirmations()
    par_carre = {}
    factices = 0
    for q in collect_all_qsos(shared_log):
        b = str(q.get('band', '') or '')
        if bande and b != str(bande):
            continue
        if _locator_factice(q.get('locator')):
            factices += 1
            continue
        g = _grid(q, 4)
        if not g:
            continue
        e = par_carre.setdefault(g, {'g': g, 'n': 0, 'conf': False, 'bands': set()})
        e['n'] += 1
        e['bands'].add(b)
        if conf.get(_confirm_key(q)):
            e['conf'] = True
    carres = [{'g': e['g'], 'n': e['n'], 'conf': e['conf'],
               'bands': sorted(e['bands'], key=_band_sort_key)}
              for e in par_carre.values()]
    carres.sort(key=lambda x: x['g'])
    return {'squares': carres, 'total': len(carres),
            'confirmed': sum(1 for c in carres if c['conf']),
            # Signalé, jamais masqué : l'opérateur doit savoir qu'une part de
            # son carnet ne porte pas de position exploitable, et pouvoir la
            # corriger. Le taire donnerait un compte de carrés inexpliqué.
            'locators_factices': factices}


def suivi_carres(entendus, shared_log=None, scope_id='', bande=''):
    """Locator tracker : parmi les stations ENTENDUES, lesquelles apportent un
    carré neuf ? Retourne la liste annotée, les plus intéressantes en tête.

    LA RÈGLE, telle que l'utilisateur l'a tranchée. En concours, l'alerte porte
    sur la DURÉE DU CONCOURS : un carré travaillé en 2019 reste un
    multiplicateur à faire ce week-end, donc il sonne. Mais celui qui est en
    plus absent du carnet À VIE vaut double — multiplicateur ET carré neuf pour
    les diplômes — et passe devant les autres.

    Hors concours (scope_id vide), la seule question qui vaille est « l'ai-je à
    vie ? » : les deux référentiels se confondent alors, et rien ne remonte
    artificiellement.

    Trois niveaux dans 'interet' :
      2  neuf pour le concours ET jamais travaillé à vie   -> priorité
      1  neuf pour le concours seulement                   -> multiplicateur
      0  déjà fait                                         -> silencieux
    """
    qsos = collect_all_qsos(shared_log)
    a_vie, dans_scope = set(), set()
    for q in qsos:
        g = _grid(q, 4)
        if not g:
            continue
        a_vie.add(g)
        if scope_id and qso_scope_id_safe(q) == scope_id:
            dans_scope.add(g)
    # Sans concours actif, « déjà fait » veut dire « déjà fait à vie ».
    deja = dans_scope if scope_id else a_vie

    out = []
    for e in (entendus or []):
        g = str(e.get('grid') or '').strip().upper()[:4]
        if not g or _locator_factice(e.get('grid')):
            continue
        if bande and str(e.get('band', '')) != str(bande):
            continue
        neuf_ici = g not in deja
        neuf_a_vie = g not in a_vie
        if not neuf_ici:
            interet = 0
        elif neuf_a_vie:
            interet = 2
        else:
            interet = 1
        out.append(dict(e, grid=g, interet=interet,
                        neuf_a_vie=neuf_a_vie,
                        libelle=('NOUVEAU CARRÉ — jamais travaillé' if interet == 2
                                 else 'carré neuf pour ce concours' if interet == 1
                                 else '')))
    # Les plus intéressants en tête : sur 30 à 50 décodages toutes les 15 s,
    # l'opérateur ne lit que le haut de la liste.
    out.sort(key=lambda x: -x['interet'])
    return out


def qso_scope_id_safe(q):
    """qso_scope_id() de logx_storage, sans faire dépendre tout ce module de
    son import — logx_awards est chargé très tôt et par des outils qui n'ont
    pas besoin du stockage."""
    try:
        from logx_storage import qso_scope_id
        return qso_scope_id(q)
    except Exception:
        return ''


def annoter_besoin_lotw(spots, shared_log=None):
    """Pose 'lotw_need_ici' (bool) sur chaque spot, SANS filtrer la liste.

    Pendant que besoins_lotw_spottes() répond à « que dois-je appeler ? », ici
    on répond à « lesquels, dans ce que j'affiche déjà, valent un appel ? ».
    Les fenêtres de surveillance par bande montrent TOUT ce qui est spotté —
    masquer le reste priverait l'opérateur de la vue d'ensemble qu'il est
    justement venu chercher.

    Un seul parcours du carnet pour toute la liste, même raison que le calcul
    groupé ci-dessous : ces fenêtres se rafraîchissent en continu.
    """
    if not spots:
        return spots
    conf = _load_confirmations()
    creneaux = _creneaux_confirmes_lotw(collect_all_qsos(shared_log), conf)
    try:
        import logx_dxcc as dxcc
    except Exception:
        for s in spots:
            s['lotw_need_ici'] = False
        return spots
    for s in spots:
        call = str(s.get('call') or s.get('dx') or '').upper().strip()
        base = call.split('/')[0] if '/' in call else call
        pays = (dxcc.lookup(base) or {}).get('country') if len(base) >= 3 else None
        if not pays:
            s['lotw_need_ici'] = False
            continue
        cle = (pays, str(s.get('band', '') or ''), _mode_category(s.get('mode'), s.get('freq')))
        s['lotw_need_ici'] = cle not in creneaux
    return spots


def besoins_lotw_spottes(spots, shared_log=None, max_n=20):
    """Parmi les stations spottées, celles qui comblent un créneau non confirmé
    LoTW. Le calcul lourd (parcours du log + confirmations) est fait UNE fois
    pour toute la liste : appeler besoin_lotw() par spot relirait le carnet
    entier à chaque ligne — quelques centaines de spots suffisent à rendre la
    page inutilisable.
    """
    conf = _load_confirmations()
    qsos = collect_all_qsos(shared_log)
    creneaux = _creneaux_confirmes_lotw(qsos, conf)
    pays_confirmes = {c[0] for c in creneaux}
    try:
        import logx_dxcc as dxcc
    except Exception:
        return []
    out, vus = [], set()
    for s in (spots or []):
        call = str(s.get('call') or s.get('dx') or '').upper().strip()
        if len(call) < 3:
            continue
        base = call.split('/')[0] if '/' in call else call
        pays = (dxcc.lookup(base) or {}).get('country')
        if not pays:
            continue
        b = str(s.get('band', '') or '')
        cat = _mode_category(s.get('mode'), s.get('freq'))
        if (pays, b, cat) in creneaux:
            continue
        cle = (call, b, cat)
        if cle in vus:
            continue
        vus.add(cle)
        jamais = pays not in pays_confirmes
        out.append({'call': call, 'country': pays, 'band': b, 'mode_cat': cat,
                    'freq': s.get('freq'),
                    'raison': 'jamais_confirme' if jamais else 'creneau',
                    'label': (f"{pays} — JAMAIS confirmé LoTW" if jamais
                              else f"{pays} — manque en {cat} sur {b} MHz")})
        if len(out) >= max_n:
            break
    # Les entités jamais confirmées d'abord : c'est là que se joue le DXCC.
    out.sort(key=lambda x: 0 if x['raison'] == 'jamais_confirme' else 1)
    return out


def besoins_lotw_decodes(decodes, exclure=(), shared_log=None, max_n=12):
    """Parmi les stations DÉCODÉES en direct (FT8/FT4), celles qui comblent un
    créneau entité×bande×mode non confirmé LoTW — l'alerte « new one » façon
    JTAlert, mais sur le critère FORT posé par l'utilisateur : pas « jamais
    contacté » (déjà couvert par spotted_new_ones/st['missing']), mais « pas
    encore confirmé LoTW », la seule confirmation qui compte pour le DXCC.

    `exclure` : indicatifs déjà signalés autrement sur les mêmes décodages
    (typiquement les 'call' de st['missing']). Une station JAMAIS travaillée est
    aussi jamais confirmée LoTW : sans ce filtre elle sonnerait DEUX fois, une
    fois « nouveau pays » et une fois « pas confirmé LoTW ». Le plus fort
    (jamais travaillé) l'emporte, on retire donc ces indicatifs d'ici.

    Réutilise besoins_lotw_spottes() : le calcul lourd (parcours du carnet +
    confirmations) y est déjà fait une seule fois pour toute la liste.
    """
    spots = [{'call': d.get('call'), 'band': d.get('band'),
              'mode': d.get('mode'), 'freq': d.get('freq_mhz')}
             for d in (decodes or []) if d.get('call')]
    if not spots:
        return []
    exclus = {str(c).upper().strip() for c in (exclure or ()) if c}
    # On demande large (max_n + exclus) avant filtrage, pour ne pas se retrouver
    # sous max_n uniquement parce que des entrées exclues ont mangé le quota.
    brut = besoins_lotw_spottes(spots, shared_log, max_n=max_n + len(exclus))
    return [o for o in brut if o.get('call') not in exclus][:max_n]


# ─── CIBLES PROACTIVES (jamais travaillées à VIE, spottées maintenant) ───────

def spotted_new_ones(shared_log, spots_by_label=None, max_n=8):
    """Parmi les stations actuellement SPOTTÉES sur le cluster, celles qui
    apporteraient un pays (DXCC) ou un département français JAMAIS travaillé
    À VIE (pas seulement dans le concours en cours — pour ça, voir
    logx_countries.country_targets/logx_departments.department_
    targets, qui restent scopés au concours actif). Suggestions poussées
    PROACTIVEMENT par le coach (/coach/state), sans action de l'utilisateur.
    Le pays se déduit directement du préfixe (cty.dat, aucun réseau) ; le
    département d'un correspondant français vient de calldb (déjà indexé par
    logx_callhistory.build_index), pas de lookup réseau non plus."""
    import logx_dxcc as dxcc
    qsos = collect_all_qsos(shared_log)
    worked_countries = {q['dxcc_country'] for q in qsos if q.get('dxcc_country')}
    worked_depts = {q['dept'] for q in qsos if q.get('dept')}

    from logx_callhistory import build_index
    idx = build_index(shared_log)

    spotted = {}
    for label, spots in (spots_by_label or {}).items():
        for sp in spots or []:
            if isinstance(sp, dict):
                c = str(sp.get('dx') or sp.get('call') or '')
                freq = sp.get('freq', '')
            else:
                c = str(sp[0]) if sp else ''
                freq = sp[1] if len(sp) > 1 else ''
            c = c.strip().upper()
            base = c.split('/')[0] if '/' in c and len(c.split('/')[0]) >= 3 else c
            if len(base) >= 3 and base not in spotted:
                spotted[base] = {'freq': freq, 'band': label}

    out = []
    for call, data in spotted.items():
        info = None
        try:
            info = dxcc.lookup(call)
        except Exception:
            pass
        country = (info or {}).get('country')
        if country and country not in worked_countries:
            out.append({'type': 'dxcc', 'call': call, 'label': country, **data})
            continue    # un seul type de nouveauté par spot (évite le bruit)
        dept = (idx.get(call) or {}).get('dept')
        if dept and dept not in worked_depts:
            try:
                from logx_departments import DEPARTMENTS
                name = DEPARTMENTS.get(dept, '')
            except Exception:
                name = ''
            out.append({'type': 'dept', 'call': call,
                       'label': f'{dept} {name}'.strip(), **data})
    out.sort(key=lambda t: t['call'])
    return out[:max_n]


# ─── TABLEAU DE BORD DIPLÔMES ─────────────────────────────────────────────────

# ─── RÉFÉRENTIELS DES DIPLÔMES CLASSIQUES ────────────────────────────────────

# WAS (Worked All States, ARRL) — les 50 états. Le district de Columbia n'en
# fait PAS partie : le WAS se compte sur 50, DC est rattaché au Maryland pour
# ce diplôme. Un état ne se déduit JAMAIS de l'indicatif (un W6 peut habiter
# n'importe où depuis la fin du découpage géographique des préfixes) : il vient
# du champ ADIF STATE, de l'annuaire, ou d'une confirmation LoTW.
US_STATES = (
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
)

# WAZ (Worked All Zones, CQ) — 40 zones CQ, déduites de l'indicatif via cty.dat.
WAZ_TOTAL = 40

# WAC (Worked All Continents, IARU) — 6 continents. L'Antarctique (AN) figure
# dans cty.dat mais ne compte PAS pour le WAC : l'inclure ferait afficher 7/6.
WAC_CONTINENTS = ('AF', 'AS', 'EU', 'NA', 'OC', 'SA')

# DXCC Challenge (ARRL) — une « case » par couple entité × bande, sur les
# bandes 160 à 6 m, WARC comprises. Clés en MHz : c'est le format réellement
# stocké dans le log (mesuré : '14', '7', '3.5', '144'...), pas en longueur
# d'onde. Le 2 m et au-dessus n'entrent pas dans le Challenge.
CHALLENGE_BANDS = ('1.8', '3.5', '7', '10.1', '14', '18', '21', '24', '28', '50')


# Locators « par défaut » écrits par certains logiciels quand la case est
# restée vide. Ce sont des chaînes Maidenhead PARFAITEMENT VALIDES — d'où le
# fait que rien ne les signale — mais elles ne décrivent aucune position.
#
# TROUVÉ DANS LE LOG RÉEL de la station en préparant la carte des carrés :
# JJ00AA y figure 300 fois, sur des QSO avec la Russie, la France, l'Ukraine,
# l'Angleterre… soit 3,2 % du carnet. JJ00 se situe à 0° N, 0° E, en plein
# golfe de Guinée : ces contacts calculaient une distance moyenne de 5 032 km,
# et une station japonaise y était annoncée à 5 032 km au lieu de ~9 500.
#
# Ces QSO restent au log — ce sont de vrais contacts, seule leur POSITION est
# fausse. Ils sont simplement écartés des diplômes de carrés, où les compter
# reviendrait à revendiquer un carré jamais travaillé, et signalés en clair
# plutôt que retirés en silence.
LOCATORS_FACTICES = frozenset({'JJ00AA', 'AA00AA', 'AA00', 'JJ00'})


def _locator_factice(loc):
    l = str(loc or '').strip().upper()
    return l in LOCATORS_FACTICES


def _grid(q, n):
    """Les n premiers caractères du locator, en majuscules, ou ''.

    n=2 -> le CHAMP QRA (CQ DX Field) ; n=4 -> le CARRÉ (VUCC).
    Mesuré sur le log réel : les locators font 4, 6 ou 8 caractères, donc on
    tronque au lieu d'exiger une longueur exacte.
    """
    loc = str(q.get('locator') or '').strip().upper()
    if _locator_factice(loc):
        return ''
    return loc[:n] if len(loc) >= n else ''


def _paire(worked, confirmed, total=None, manquants=None):
    """Forme commune à tous les diplômes : travaillé / confirmé / reste."""
    out = {'worked': len(worked), 'confirmed': len(confirmed)}
    if total is not None:
        out['total'] = total
    if manquants is not None:
        out['missing'] = manquants
    return out


def award_summary(shared_log=None):
    """Travaillé / confirmé par diplôme, sur toute la vie de la station."""
    conf = _load_confirmations()
    qsos = collect_all_qsos(shared_log)

    countries_w, countries_c = set(), set()
    depts_w, depts_c = set(), set()
    conts, zones = set(), set()
    per_band = {}          # bande -> {qso, dxcc:set}
    total_conf = 0
    # Diplômes classiques, tous comptés en travaillé ET confirmé. Sauf le WAS,
    # tous se calculent RÉTROACTIVEMENT sur le carnet existant : l'entité, la
    # zone et le continent se déduisent de l'indicatif (cty.dat), le champ et
    # le carré du locator déjà enregistré. Le WAS fait exception — l'état ne se
    # déduit de rien, il doit avoir été saisi ou importé (voir US_STATES).
    zones_w, zones_c = set(), set()
    conts_w, conts_c = set(), set()
    states_w, states_c = set(), set()
    fields_w, fields_c = set(), set()          # champs QRA (CQ DX Field)
    squares_w, squares_c = set(), set()        # carrés QRA (VUCC)
    squares_par_bande = {}                     # bande -> set de carrés
    challenge_w, challenge_c = set(), set()    # couples (entité, bande)
    for q in qsos:
        is_conf = bool(conf.get(_confirm_key(q)))
        total_conf += 1 if is_conf else 0
        c = q.get('dxcc_country')
        b = str(q.get('band', '?'))
        if c:
            countries_w.add(c)
            if is_conf:
                countries_c.add(c)
            if b in CHALLENGE_BANDS:
                challenge_w.add((c, b))
                if is_conf:
                    challenge_c.add((c, b))
        d = q.get('dept')
        if d:
            depts_w.add(d)
            if is_conf:
                depts_c.add(d)
        if q.get('continent'):
            conts.add(q['continent'])
            if q['continent'] in WAC_CONTINENTS:
                conts_w.add(q['continent'])
                if is_conf:
                    conts_c.add(q['continent'])
        if q.get('cq_zone'):
            zones.add(q['cq_zone'])
            zones_w.add(str(q['cq_zone']))
            if is_conf:
                zones_c.add(str(q['cq_zone']))
        st = str(q.get('state') or '').strip().upper()
        if st in US_STATES:
            states_w.add(st)
            if is_conf:
                states_c.add(st)
        champ = _grid(q, 2)
        if champ:
            fields_w.add(champ)
            if is_conf:
                fields_c.add(champ)
        carre = _grid(q, 4)
        if carre:
            squares_w.add(carre)
            squares_par_bande.setdefault(b, set()).add(carre)
            if is_conf:
                squares_c.add(carre)
        pb = per_band.setdefault(b, {'qso': 0, 'dxcc': set()})
        pb['qso'] += 1
        if c:
            pb['dxcc'].add(c)

    try:
        from logx_departments import METRO, DOM, DEPARTMENTS
        metro_missing = [d for d in METRO if d not in depts_w]
        dom_missing = [d for d in DOM if d not in depts_w]
    except Exception:
        METRO, DOM, DEPARTMENTS = [], [], {}
        metro_missing, dom_missing = [], []

    return {
        'qso_total': len(qsos),
        'confirmed_total': total_conf,
        'has_confirmations': bool(conf),
        'dxcc': {'worked': len(countries_w), 'confirmed': len(countries_c)},
        'departments': {
            'metro_worked': len([d for d in depts_w if d in METRO]),
            'metro_total': len(METRO),
            'metro_confirmed': len([d for d in depts_c if d in METRO]),
            'dom_worked': len([d for d in depts_w if d in DOM]),
            'missing': (metro_missing + dom_missing)[:40],
        },
        'continents': sorted(conts),
        'cq_zones': sorted(zones),
        'per_band': {b: {'qso': v['qso'], 'dxcc': len(v['dxcc'])}
                     for b, v in sorted(per_band.items())},
        # ── Diplômes classiques ──────────────────────────────────────────────
        'waz': _paire(zones_w, zones_c, WAZ_TOTAL,
                      sorted((str(z) for z in range(1, WAZ_TOTAL + 1)
                              if str(z) not in zones_w), key=int)),
        'wac': _paire(conts_w, conts_c, len(WAC_CONTINENTS),
                      [c for c in WAC_CONTINENTS if c not in conts_w]),
        'was': _paire(states_w, states_c, len(US_STATES),
                      [s for s in US_STATES if s not in states_w]),
        # Le WAS n'a de sens que si l'état est renseigné quelque part : sans
        # cette information, afficher « 0/50 » laisserait croire à un carnet
        # vide alors que c'est la DONNÉE qui manque, pas les contacts.
        'was_data': bool(states_w),
        'dx_field': _paire(fields_w, fields_c),
        'vucc': dict(_paire(squares_w, squares_c),
                     per_band={b: len(s) for b, s in sorted(squares_par_bande.items())}),
        'dxcc_challenge': _paire(challenge_w, challenge_c),
    }


# ─── WORKED MATRIX (grille bande × CW/Phone/Digital) ─────────────────────────

# Créneaux bande/mode par FRÉQUENCE, repris de la table publiée dans le manuel
# CC User (annexe C, « Filtering band/mode segments (slots) on a CC Cluster »).
# Bornes en kHz : (début, fin, catégorie).
#
# POURQUOI LA FRÉQUENCE ET PAS LE MODE ANNONCÉ. Le manuel l'explique, et c'est
# la raison pour laquelle CC Cluster filtre ainsi depuis toujours : « beaucoup
# de spots DX n'indiquent pas le mode réellement utilisé, mais TOUS indiquent
# la fréquence — c'est un champ obligatoire de tout spot valide ».
#
# DÉFAUT RÉEL QUE ÇA CORRIGE ICI : _mode_category() renvoyait DIGITAL pour un
# mode absent, vide ou inconnu. Un DX en CW spotté sans champ mode — cas
# courant sur le cluster — était donc compté comme un créneau NUMÉRIQUE, et
# l'alerte « pas confirmé LoTW en CW » ne se déclenchait jamais pour lui.
# ─── LES FRÉQUENCES D'APPEL NUMÉRIQUES, D'ABORD ──────────────────────────────
#
# DÉFAUT RÉEL QUE CE BLOC CORRIGE, mesuré : FT8 était classé PHONE sur 6 m, 2 m
# et 70 cm, et CW sur 160, 80 et 12 m — six bandes sur douze. L'utilisateur
# demandait « si je passe en SSB je veux voir QUE les spots SSB » : sur 2 m, le
# filtre SSB lui servait du FT8.
#
# POURQUOI UN DÉCOUPAGE PAR PLAGES NE PEUT PAS Y ARRIVER. Le plan de bandes
# officiel et l'usage réel ne coïncident PAS. 144,174 MHz tombe dans le segment
# « SSB » du plan IARU R1 ; c'est pourtant la fréquence FT8 du 2 m, la même
# partout dans le monde. Idem 50,313 · 432,174 · 7,074. Les conventions FT8/FT4
# se sont installées là où il restait de la place, sans redécoupage du plan.
#
# Ces créneaux sont donc consultés AVANT le plan de bandes. Ils sont étroits
# (le signal occupe les 3 kHz au-dessus de la fréquence affichée) et identiques
# dans les trois régions UIT — c'est tout l'intérêt de la convention.
_APPELS_NUMERIQUES_KHZ = (
    # FT8 — de loin le plus utilisé
    1840, 3573, 5357, 7074, 10136, 14074, 18100, 21074, 24915, 28074,
    50313, 144174, 432174,
    # FT4
    3575, 7047.5, 10140, 14080, 18104, 21140, 24919, 28180, 50318,
    # JS8Call
    1842, 3578, 7078, 14078, 21078, 24922, 28078,
    # WSPR (balises de propagation : très faible puissance, jamais de la phonie)
    1836.6, 3568.6, 7038.6, 10138.7, 14095.6, 18104.6, 21094.6, 24924.6,
    28124.6, 50293,
)
_LARGEUR_NUMERIQUE_KHZ = 3.0   # le signal occupe le haut de la fréquence affichée
_MARGE_NUMERIQUE_KHZ = 0.5     # tolérance sur une fréquence de spot arrondie


# ─── LE PLAN DE BANDES ───────────────────────────────────────────────────────
#
# Quatrième champ : la plage est-elle dans l'allocation FRANÇAISE (ANFR) ?
#
# POURQUOI CE DRAPEAU. La table venait de l'annexe C du manuel CC Cluster,
# pensée pour l'AMÉRIQUE DU NORD : elle décrit le 40 m jusqu'à 7,300, le 80 m
# jusqu'à 4,000, le 2 m jusqu'à 148, et contient une bande 222 MHz qui
# N'EXISTE PAS en région 1. Un opérateur français y lisait des segments où il
# n'a pas le droit d'émettre — et un clic sur un spot à 7,250 commandait un QSY
# hors bande.
#
# Les deux usages n'ont pas le même besoin, d'où le drapeau plutôt qu'une coupe
# franche :
#   - CLASSER un spot (mode_depuis_frequence) : toute la table. Une station
#     américaine à 7,250 fait bien de la phonie, et le dire est utile.
#   - DESSINER la bande de l'opérateur (segments_bande) : la part française
#     seulement. La réglette montre où l'on peut travailler, pas où d'autres
#     travaillent.
#
# ─── PROVENANCE (à lire avant toute modification de la table) ────────────────
#
# DEUX CHOSES DIFFÉRENTES SONT MÉLANGÉES DANS CHAQUE LIGNE, et il faut le
# savoir pour la mettre à jour correctement :
#
#   1. LES BORNES D'ALLOCATION (où l'on a le droit d'émettre) — RÉGLEMENTAIRE.
#      Autorité : ANFR / TNRBF, arrêté du 21 septembre 2000 modifié. C'est ce
#      qui fixe 430-440 MHz en France, 144-146, 50-52, 1240-1300…
#      Le drapeau `fr` de chaque ligne relève de CETTE catégorie.
#      Dernière modification connue : TNRBF, modification du 26 mai 2026
#      (anfr.fr/fileadmin/TNRBF/2026/) — à reconsulter avant toute reprise, le
#      tableau évolue plusieurs fois par an.
#
#   2. LE DÉCOUPAGE PAR MODE (CW / numérique / phonie) — PAS RÉGLEMENTAIRE.
#      C'est une convention IARU. Autorité : plan de bandes IARU Région 1.
#      Les valeurs ci-dessous viennent de l'annexe C du manuel CC Cluster,
#      corrigée aux bornes françaises le 31/07/2026 — elles ne sont donc PAS
#      issues du document IARU, et c'est leur faiblesse connue.
#
# SOURCE NORMATIVE POUR (2), à utiliser lors d'une reprise sérieuse :
#   IARU-R1 VHF/UHF/SHF Committee C5 — VHF and up band planning
#   https://www.iaru-r1.org/about-us/committees-and-working-groups/
#           vhf-uhf-shf-committee-c5/vhf-up-bandplanning/
#   Les plans y sont publiés SANS les notes de bas de page, or ce sont les
#   notes qui portent l'essentiel : segments à bande étroite des bandes
#   hautes, fréquences d'appel, statut des balises. Elles sont dans le
#   IARU Region 1 VHF Handbook V9.00 (novembre 2020) — vérifier s'il existe
#   une version postérieure à la conférence de Zlatibor.
#
# TROIS PIÈGES SIGNALÉS PAR L'OPÉRATEUR, à traiter AVANT d'étendre la table :
#
#   a) PAR RÉGION. IARU R1 ≠ R2 ≠ R3. Ce logiciel sert à l'international (huit
#      langues, concours ARRL et CQ intégrés). La clé devra devenir
#      (région, bande) et non (bande). Le drapeau `fr` booléen actuel est un
#      marqueur binaire de fortune, pas un axe de région : il dit « France ou
#      pas », ce qui suffit aujourd'hui et ne suffira plus.
#
#   b) LE 23 cm : la décision est tombée. ECC/DEC/(25)01, approuvée le
#      27 juin 2025, impose des LIMITES DE PUISSANCE par sous-bande entre 1258
#      et 1300 MHz pour protéger les récepteurs Galileo. Elle ne redécoupe pas
#      la bande — c'est une contrainte d'un autre ordre qu'un segment de mode.
#      Voir logx_bandplan_vhf.CONTRAINTES_23CM.
#
#   c) AUCUN FORMAT LISIBLE PAR MACHINE n'existe côté IARU. La saisie se fera
#      depuis le PDF, à la main. Chaque ligne ajoutée devra porter le document,
#      sa version et la date de conférence dont elle sort — c'est ce qui
#      permettra de rejouer la vérification dans deux ans plutôt que de tout
#      re-sourcer.
#
# RÈGLE QUI A COÛTÉ QUATRE CHANTIERS LE 31/07/2026 : ne jamais affiner ce
# découpage de mémoire. Une table de domaine vraisemblable et fausse ne fait
# tomber aucun test.
_CRENEAUX_KHZ = (
    #  de      à       catégorie   France
    (1800,   1810,   'CW',      False),  # 160 m France : 1810-1850
    (1810,   1850,   'CW',      True),
    (1850,   2000,   'PHONE',   False),  # région 2
    (3500,   3580,   'CW',      True),
    (3580,   3700,   'DIGITAL', True),
    (3700,   3800,   'PHONE',   True),   # 80 m France : 3500-3800
    (3800,   4000,   'PHONE',   False),  # région 2
    (5260,   5351.5, 'PHONE',   False),  # 60 m France : 5351,5-5366,5 seulement
    (5351.5, 5366.5, 'PHONE',   True),
    (5366.5, 5405,   'PHONE',   False),
    (7000,   7040,   'CW',      True),
    (7040,   7100,   'DIGITAL', True),
    (7100,   7200,   'PHONE',   True),   # 40 m France : 7000-7200
    (7200,   7300,   'PHONE',   False),  # région 2
    (10100,  10130,  'CW',      True),   # 30 m : CW et data UNIQUEMENT,
    (10130,  10150,  'DIGITAL', True),   #        jamais de phonie
    (14000,  14070,  'CW',      True),
    (14070,  14150,  'DIGITAL', True),
    (14150,  14350,  'PHONE',   True),
    (18068,  18100,  'CW',      True),
    (18100,  18110,  'DIGITAL', True),
    (18110,  18168,  'PHONE',   True),
    (21000,  21070,  'CW',      True),
    (21070,  21200,  'DIGITAL', True),
    (21200,  21450,  'PHONE',   True),
    (24890,  24920,  'CW',      True),
    (24920,  24930,  'DIGITAL', True),
    (24930,  24990,  'PHONE',   True),
    (28000,  28070,  'CW',      True),
    (28070,  28300,  'DIGITAL', True),
    (28300,  29700,  'PHONE',   True),
    (50000,  50080,  'CW',      True),
    (50080,  50500,  'PHONE',   True),
    (50500,  52000,  'PHONE',   True),   # 6 m France : 50-52
    (52000,  54000,  'PHONE',   False),  # région 2
    # 4 m (70 MHz) : attribué dans plusieurs pays de région 1 (G, OZ, OH...),
    # PAS aux amateurs en France. Classé, jamais proposé.
    (70000,  70650,  'PHONE',   False),
    (144000, 144100, 'CW',      True),
    (144100, 144500, 'PHONE',   True),
    (144500, 146000, 'PHONE',   True),   # 2 m région 1 : 144-146
    (146000, 148000, 'PHONE',   False),  # région 2
    # 222 MHz : bande de région 2 uniquement, elle n'existe pas en Europe.
    (220000, 221000, 'CW',      False),
    (222000, 224000, 'PHONE',   False),
    # 70 cm : ABSENT de la table CC User, qui s'arrête au 222 MHz. C'est
    # pourtant une bande de concours majeure en région 1 — Rallye des Points
    # Hauts, National THF, Challenge THF. Bornes reprises de
    # logx_transverter.BANDES_MHZ (430-440, déjà utilisées par le pilotage
    # radio du logiciel) et coupure étroite/large à 432.100, la limite
    # universellement retenue en région 1. Signalé ici parce que ce couple de
    # lignes ne vient PAS de la source citée pour le reste.
    (430000, 432100, 'CW',      True),
    (432100, 440000, 'PHONE',   True),
)


def mode_depuis_frequence(freq_mhz):
    """Catégorie de mode déduite de la fréquence, ou '' hors des créneaux.

    Sert de REPLI quand le spot n'annonce pas son mode — jamais à écraser un
    mode explicitement annoncé, qui reste plus fiable qu'un découpage par
    plage (rien n'interdit un QSO CW dans un segment phonie).
    """
    try:
        v = float(freq_mhz)
    except (TypeError, ValueError):
        return ''
    # Selon la source, un spot arrive en MHz (14.074) ou déjà en kHz (14074).
    # Le seuil discrimine sans ambiguïté sur les bandes amateur : aucune n'est
    # à la fois > 1000 MHz et < 1000 kHz. (Premier jet : je multipliais par
    # 1000 une valeur déjà en kHz, ce qui envoyait 14074 à 14 074 000 kHz —
    # hors table, donc aucun mode déduit. Attrapé par le test.)
    khz = v if v > 1000 else v * 1000.0
    # Les fréquences d'appel numériques D'ABORD : elles tombent souvent dans un
    # segment que le plan de bandes déclare « phonie » (144,174 · 50,313 ·
    # 432,174 · 7,074). Voir _APPELS_NUMERIQUES_KHZ.
    for f in _APPELS_NUMERIQUES_KHZ:
        if f - _MARGE_NUMERIQUE_KHZ <= khz <= f + _LARGEUR_NUMERIQUE_KHZ:
            return 'DIGITAL'
    for lo, hi, cat, _fr in _CRENEAUX_KHZ:
        if lo <= khz < hi:
            return cat
    return ''


def hors_bande_france(freq_mhz):
    """True si cette fréquence est en dehors des bandes amateur françaises.

    Sert à MARQUER un spot, jamais à le masquer : entendre une station hors de
    sa propre allocation est courant et instructif (une station de région 2 à
    7,250 MHz est parfaitement en règle chez elle). Ce qui ne l'est pas, c'est
    de lui répondre — ou de laisser un clic commander le QSY sans rien dire.

    Renvoie False quand la fréquence est inexploitable ou inconnue : on ne
    signale que ce dont on est sûr.
    """
    try:
        v = float(freq_mhz)
    except (TypeError, ValueError):
        return False
    if not v:
        return False
    khz = v if v > 1000 else v * 1000.0
    for lo, hi, _cat, fr in _CRENEAUX_KHZ:
        if lo <= khz < hi:
            return not fr
    return False


def segments_bande(band):
    """Découpage CW / numérique / phonie d'une bande, en MHz.

    Retourne {'lo','hi','segments':[{'lo','hi','cat'}]} ou None si la bande
    n'est pas connue. Dérivé de _CRENEAUX_KHZ — la MÊME table que le mode
    déduit de la fréquence, pour qu'une réglette de bande et une alerte ne
    puissent jamais désigner des segments différents.

    Sert à dessiner l'échelle des fenêtres de surveillance : voir où se
    concentre l'activité, et surtout où il reste un trou pour appeler.
    """
    try:
        centre = float(band)
    except (TypeError, ValueError):
        return None
    # La « bande » est nommée par sa fréquence basse en MHz dans tout le
    # logiciel ('14', '3.5', '144')… SAUF le 70 cm, nommé 432 alors qu'il
    # commence à 430. D'où une tolérance BASSE proportionnelle (0,5 %) plutôt
    # qu'un plancher strict : sans elle, le segment CW 430-432,1 disparaissait
    # de la réglette 432 — constaté en vérifiant les bandes une par une.
    # La tolérance haute (12 %) sépare 14 de 18, et 24 de 28 ; la basse reste
    # assez serrée pour que le 60 m (5260) n'entre pas dans la bande 7 MHz.
    #
    # `fr` FILTRE ICI, et seulement ici : la réglette dessine la bande sur
    # laquelle l'opérateur peut travailler. Elle s'arrêtait à 7,300 · 4,000 ·
    # 148 MHz — les bornes nord-américaines de la table d'origine — en montrant
    # à un Français des centaines de kHz où il n'a pas le droit d'émettre.
    khz = centre * 1000.0
    seg = [(lo, hi, cat) for lo, hi, cat, fr in _CRENEAUX_KHZ
           if fr and khz * 0.995 <= lo < khz + max(1000.0, khz * 0.12)]
    if not seg:
        # AU-DESSUS DE 440 MHz, la table ci-dessus n'a rien : on passe au plan
        # IARU R1 (logx_bandplan_vhf), qui couvre 23 cm à 241 GHz.
        #
        # LA CONVERSION EST UNE PERTE ASSUMÉE. Ce plan distingue ATV, satellite,
        # balises exclusives, largeurs maximales ; la réglette ne sait colorer
        # que CW / numérique / phonie. Les segments sans équivalent (ATV,
        # satellite) sont ÉCARTÉS plutôt que rangés de force dans « phonie » :
        # mieux vaut un trou dans la réglette qu'une couleur qui ment.
        try:
            import logx_bandplan_vhf as _bp
        except ImportError:
            return None
        rich = _bp.segments(str(int(centre)) if centre == int(centre) else str(centre))
        seg = []
        for s in rich:
            cat = _bp.categorie_affichage(s['mode'])
            if cat:
                seg.append((s['lo_mhz'] * 1000.0, s['hi_mhz'] * 1000.0, cat))
        if not seg:
            return None
    # Fusion des segments ADJACENTS de même catégorie : la table distingue
    # SSB et FM (deux lignes « PHONE » qui se touchent), or les afficher
    # séparément dessinerait une frontière là où l'opérateur n'en voit aucune.
    fusion = []
    for lo, hi, cat in seg:
        if fusion and fusion[-1][2] == cat and fusion[-1][1] == lo:
            fusion[-1] = (fusion[-1][0], hi, cat)
        else:
            fusion.append((lo, hi, cat))
    return {
        'lo': fusion[0][0] / 1000.0,
        'hi': fusion[-1][1] / 1000.0,
        'segments': [{'lo': lo / 1000.0, 'hi': hi / 1000.0, 'cat': cat}
                     for lo, hi, cat in fusion],
    }


def _mode_category(mode, freq_mhz=None):
    """Classe un mode dans une des 3 catégories usuelles des diplômes DXCC/WAS.

    `freq_mhz` sert de repli quand le mode est absent ou non reconnu — voir
    _CRENEAUX_KHZ. Sans lui, l'ancien comportement (tout inconnu -> DIGITAL)
    est conservé, pour ne pas changer le sens des appels qui n'ont pas de
    fréquence sous la main (un QSO du carnet en a toujours un, un mode).
    """
    m = str(mode or '').upper()
    if m == 'CW':
        return 'CW'
    if m in ('SSB', 'USB', 'LSB', 'AM', 'FM'):
        return 'PHONE'
    if m in ('FT8', 'FT4', 'JS8', 'RTTY', 'PSK', 'PSK31', 'MFSK', 'JT65',
             'JT9', 'OLIVIA', 'DATA', 'DIGI', 'DIGITAL'):
        return 'DIGITAL'
    # Mode absent ou inconnu : la fréquence tranche mieux qu'un défaut arbitraire.
    if freq_mhz is not None:
        cat = mode_depuis_frequence(freq_mhz)
        if cat:
            return cat
    return 'DIGITAL'


def _band_sort_key(b):
    try:
        return float(b)
    except (TypeError, ValueError):
        return 9999.0


def worked_matrix(shared_log=None, scope_id=''):
    """Grille bande × catégorie de mode : nb de QSO travaillés/confirmés par
    case. Par défaut sur toute la vie de la station (comme award_summary),
    utile pour visualiser d'un coup d'œil les cases DXCC/WAS encore vides.

    scope_id (optionnel, même format que qso_scope_id()/active_scope_id() de
    logx_storage.py, ex. 'CQ_WW_SSB#2026') restreint la grille aux QSO de CE
    concours précis — utile en cours d'épreuve pour voir d'un coup d'œil quelles
    cases bande/mode restent à couvrir DANS le concours actif, plutôt que le
    total historique de la station qui n'aide pas à décider où aller maintenant."""
    conf = _load_confirmations()
    qsos = collect_all_qsos(shared_log)
    if scope_id:
        from logx_storage import qso_scope_id
        qsos = [q for q in qsos if qso_scope_id(q) == scope_id]
    cats = ('CW', 'PHONE', 'DIGITAL')
    grid = {}
    # Entités DXCC par case, en plus du simple compte de QSO.
    #
    # POURQUOI LES DEUX. Le nombre de QSO dit l'ACTIVITÉ sur une case ; le
    # nombre d'ENTITÉS dit l'AVANCEMENT du DXCC Challenge, qui se compte en
    # couples entité × bande et se moque de savoir si on a fait dix QSO ou un
    # seul avec le même pays. Une case à 900 QSO et 12 entités est une case
    # d'habitué ; une case à 12 QSO et 12 entités est une case de chasseur.
    #
    # Et la confirmation LoTW est comptée à part : pour l'ARRL, une
    # confirmation eQSL ou papier ne vaut rien — voir besoin_lotw().
    entites = {}       # bande -> cat -> set d'entités
    entites_lotw = {}  # idem, confirmées LoTW seulement
    for q in qsos:
        b = str(q.get('band', '?'))
        cat = _mode_category(q.get('mode', ''))
        cell = grid.setdefault(b, {c: {'qso': 0, 'confirmed': 0} for c in cats})[cat]
        cell['qso'] += 1
        srcs = conf.get(_confirm_key(q)) or {}
        if srcs:
            cell['confirmed'] += 1
        pays = q.get('dxcc_country')
        if pays:
            entites.setdefault(b, {}).setdefault(cat, set()).add(pays)
            if srcs.get(LOTW_SOURCE):
                entites_lotw.setdefault(b, {}).setdefault(cat, set()).add(pays)
    for b, cols in grid.items():
        for c in cats:
            cols[c]['dxcc'] = len(entites.get(b, {}).get(c, ()))
            cols[c]['dxcc_lotw'] = len(entites_lotw.get(b, {}).get(c, ()))
    bands = sorted(grid.keys(), key=_band_sort_key)
    return {
        'bands': bands, 'categories': list(cats),
        'grid': {b: grid[b] for b in bands},
        'totals': {c: sum(grid[b][c]['qso'] for b in bands) for c in cats},
        # Cases du DXCC Challenge : une par couple entité × bande, toutes
        # catégories de mode confondues (l'ARRL ne distingue pas le mode pour
        # le Challenge, contrairement au DXCC par mode).
        #
        # RESTREINT À CHALLENGE_BANDS, comme award_summary()['dxcc_challenge'].
        # Sans ce filtre, cette grille annonçait 454 cases là où le panneau
        # Diplômes en annonçait 435 : elle comptait le 144, le 432 et une bande
        # « 1mm » issue d'une saisie douteuse, qui n'entrent pas dans le
        # Challenge. Deux chiffres différents pour la même chose au même écran,
        # c'est le genre d'incohérence qui fait douter de tout le reste.
        'challenge': sum(len(set().union(*cols.values())) if cols else 0
                         for b, cols in entites.items() if b in CHALLENGE_BANDS),
        'challenge_lotw': sum(len(set().union(*cols.values())) if cols else 0
                              for b, cols in entites_lotw.items()
                              if b in CHALLENGE_BANDS),
    }


# ─── RECORD DX (remplace l'ancien champ manuel record_dx) ────────────────────
# Un chiffre unique saisi à la main n'a pas de sens pour un opérateur
# multi-bandes : 3000 km est banal en HF, exceptionnel en VHF/UHF (le même
# défaut que corrigeait déjà logx_bands.py pour les seuils d'alerte). Calculé
# depuis le vrai locator de chaque QSO archivé (haversine), jamais déclaratif.

def dx_records(my_locator, shared_log=None):
    """Plus grande distance (km) travaillée PAR BANDE, sur toute la vie de la
    station. Renvoie {'overall': {...} | None, 'by_band': {bande: {...}}}.

    Filtre les distances IMPLAUSIBLES pour la bande (locator erroné, mauvais
    libellé de bande dans une archive ancienne, EME mal étiqueté...) avec le
    même plafond déjà utilisé pour écarter les spots aberrants — cf. le cas
    réel documenté dans logx_scoring.py : « FK8HA à 17 014 km en 144 MHz »
    proposé à l'agent avant ce garde-fou. Sans lui, un "record" himalayen
    en UHF serait affiché tel quel, ce qui n'inspirerait pas confiance dans
    un chiffre calculé automatiquement."""
    from logx_utils import haversine, locator_to_latlon
    from logx_scoring import _MAX_PLAUSIBLE_KM
    my_ll = locator_to_latlon(my_locator or '')
    if not my_ll[0]:
        return {'overall': None, 'by_band': {}}

    best = {}  # bande -> {call, locator, dist_km, date, mode}
    for q in collect_all_qsos(shared_log):
        loc = q.get('locator', '')
        if not loc:
            continue
        dx_ll = locator_to_latlon(loc)
        if not dx_ll[0]:
            continue
        dist = haversine(my_ll[0], my_ll[1], dx_ll[0], dx_ll[1])
        band = str(q.get('band', '?'))
        cap = _MAX_PLAUSIBLE_KM.get(band)
        if cap and dist > cap:
            continue
        cur = best.get(band)
        if not cur or dist > cur['dist_km']:
            best[band] = {'call': q.get('call', ''), 'locator': loc, 'dist_km': dist,
                          'date': q.get('date', ''), 'mode': q.get('mode', '')}

    bands = sorted(best.keys(), key=_band_sort_key)
    overall = max(best.values(), key=lambda r: r['dist_km']) if best else None
    if overall:
        overall = {**overall, 'band': next(b for b in bands if best[b] is overall)}
    return {'overall': overall, 'by_band': {b: best[b] for b in bands}}


# ─── ACTIVITÉ PAR JOUR (vue statistique légère, écran Diplômes) ──────────────

def activity_by_day(shared_log=None, days=30):
    """Nombre de QSO par jour sur les `days` derniers jours (vie entière).
    Réutilise collect_all_qsos() déjà chargé pour award_summary/dx_records —
    aucun nouveau parcours de fichiers. Fenêtre ancrée sur AUJOURD'HUI (pas la
    dernière date de QSO) : reste lisible même après une pause dans le trafic,
    plutôt que de figer sur une activité vieille de plusieurs mois."""
    counts = {}
    for q in collect_all_qsos(shared_log):
        d = str(q.get('date', ''))
        if len(d) == 8 and d.isdigit():
            counts[d] = counts.get(d, 0) + 1
    days = max(1, int(days))
    end = utcnow()
    out = []
    for i in range(days - 1, -1, -1):
        d = (end - datetime.timedelta(days=i)).strftime('%Y%m%d')
        out.append({'date': d, 'qso': counts.get(d, 0)})
    return out
