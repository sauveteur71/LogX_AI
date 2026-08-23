# -*- coding: utf-8 -*-
"""Historique d'indicatifs — Super Check Partial (SCP) à la N1MM.

Fusionne plusieurs sources en un index  indicatif → {dept, locator, qso_count,
last_date}  pour :
  - l'AUTOCOMPLÉTION de l'indicatif à la saisie (préfixe ou fragment),
  - le PRÉ-REMPLISSAGE de l'échange attendu : département (concours REF HF,
    scoring dept_dxcc) ou locator (concours THF, scoring km × locators).

Sources, de la moins à la plus fiable (la plus fiable écrase) :
  0. master_scp.json      : MASTER.SCP importé (N1MM, jusqu'à ~45 000
                            indicatifs de concours dans le monde entier —
                            existence seule, aucun dept/locator connu, donc
                            jamais prioritaire : voir import_master_scp())
  1. calldb.json 'calls'  : base REF/QRZ (~19 000 indicatifs, dept + locator)
  2. archives/*/log.json  : concours archivés (QSO réellement faits)
  3. shared_log           : log actif (le plus récent)

L'index est un cache mémoire reconstruit au plus toutes les TTL secondes ;
update_from_qso() l'enrichit au fil de l'eau à chaque QSO loggé (pas
d'attente du TTL pour resuggérer une station qu'on vient de travailler).

Un 5e fichier, call_history_n1mm.json (import Call History au format N1MM,
voir import_call_history_n1mm()), est délibérément tenu À L'ÉCART de cet
index fusionné : il est PROPRE À CHAQUE CONCOURS (l'échange attendu d'un
indicatif — département/zone/section — change d'un concours à l'autre),
alors que l'index ci-dessus est global et partagé par tous. Il est surclassé
à la LECTURE (lookup/suggest/export_index, paramètre `contest`) plutôt que
mélangé dans le cache — voir _ch_slice().
"""
import json
import os
import re
import threading
import time

TTL = 300          # s — reconstruction complète au plus toutes les 5 min
MAX_SUGGEST = 20
MASTER_SCP_FILE = 'master_scp.json'            # liste d'indicatifs MASTER.SCP importée
CALL_HISTORY_FILE = 'call_history_n1mm.json'   # {concours: {indicatif: {...}}} importé
# Un vrai MASTER.SCP/Call History pèse quelques dizaines de milliers de
# lignes ; le corps HTTP est déjà plafonné à 32 Mo par do_POST (logx_http.py),
# donc pas besoin d'un MAX_IMPORT_BYTES redondant — la faille non couverte
# par ce plafond est le NOMBRE de lignes (32 Mo peuvent contenir des millions
# de lignes très courtes), d'où cette borne dédiée.
MAX_IMPORT_LINES = 200_000

_index = {}        # CALL -> {'dept','locator','qso_count','last_date'}
_built_at = 0.0
_lock = threading.Lock()

# Verrous DÉDIÉS au cycle lire-fusionner-écrire de master_scp.json et de
# call_history_n1mm.json (un par fichier, distincts de _lock ci-dessus qui ne
# protège que l'index mémoire) — voir import_master_scp()/
# import_call_history_n1mm(). Sans eux, deux imports concurrents pouvaient
# lire le MÊME état existant avant que l'un des deux n'écrive : le second
# écrasait alors intégralement le travail du premier, silencieusement (les
# deux appels renvoient ok=True), et sur Windows le double os.replace()
# concurrent pouvait même lever un PermissionError (WinError 5).
_master_scp_lock = threading.Lock()
_ch_io_lock = threading.Lock()

_LOC_RE = re.compile(r'^[A-R]{2}[0-9]{2}([A-X]{2})?$', re.I)
# Un vrai indicatif contient TOUJOURS au moins un chiffre (préfixe + chiffre +
# suffixe) — le lookahead écarte les mots ordinaires qu'un fichier tiers mal
# formé pourrait faire passer pour un indicatif (ex. un commentaire sans '#').
_CALL_TOKEN_RE = re.compile(r'^(?=.*\d)(?=.*[A-Z])[A-Z0-9/]{2,15}$')


def _norm_loc(loc):
    loc = str(loc or '').strip().upper()
    return loc if _LOC_RE.match(loc) else None


def _entry(call):
    return _index.setdefault(call, {
        'dept': None, 'locator': None, 'qso_count': 0, 'last_date': None,
    })


def _feed(call, dept=None, locator=None, count=0, date=None):
    """Fusionne une observation dans l'index. Les champs non vides ÉCRASENT
    (les sources sont parcourues de la moins à la plus fiable)."""
    call = str(call or '').strip().upper()
    if len(call) < 3 or not re.match(r'^[A-Z0-9/]+$', call):
        return
    call = call.split('/')[0] if '/' in call and len(call.split('/')[0]) >= 3 else call
    e = _entry(call)
    dept = str(dept or '').strip()
    if dept:
        e['dept'] = dept
    loc = _norm_loc(locator)
    if loc:
        e['locator'] = loc
    e['qso_count'] += count
    d = str(date or '').strip()
    if d and (e['last_date'] is None or d > e['last_date']):
        e['last_date'] = d


def _feed_qso(q):
    """Observation depuis un QSO réel : le locator reçu fait foi ; le
    département vient de l'échange seulement si le concours de CE QSO
    attend un département (même collision zone/série évitée que pour
    parse_n1mm_call_history, voir dept_applicable)."""
    dept = None
    try:
        from logx_departments import dept_from_exchange
        from logx_definitions import CONTEST_DEFINITIONS
        cdef = CONTEST_DEFINITIONS.get(str(q.get('contest', '')).strip().upper(), {})
        if exchange_wants(cdef)['dept']:
            dept = dept_from_exchange(str(q.get('num_rcvd', '')))
    except Exception:
        pass
    _feed(q.get('call'), dept=dept, locator=q.get('locator'),
          count=1, date=q.get('date'))


def _load_master_scp():
    """MASTER.SCP importé (voir import_master_scp) : juste des indicatifs
    bruts, sans dept/locator — chargé EN PREMIER (source la plus large mais
    la moins informative) pour que calldb.json/archives/log, qui apportent du
    vrai dept/locator, l'enrichissent ensuite sans jamais être écrasés par
    lui (_feed() sans dept/locator ne touche pas des champs déjà remplis)."""
    try:
        with open(MASTER_SCP_FILE, encoding='utf-8') as f:
            calls = (json.load(f) or {}).get('calls', [])
        for call in calls:
            _feed(call)
    except Exception:
        pass


def _load_calldb():
    try:
        with open('calldb.json', encoding='utf-8') as f:
            calls = (json.load(f) or {}).get('calls', {})
        for call, info in calls.items():
            if isinstance(info, dict):
                _feed(call, dept=info.get('dept'), locator=info.get('locator'))
    except Exception:
        pass


def _load_archives():
    try:
        from logx_archive import ARCHIVE_DIR
        if not os.path.isdir(ARCHIVE_DIR):
            return
        for name in os.listdir(ARCHIVE_DIR):
            logp = os.path.join(ARCHIVE_DIR, name, 'log.json')
            if not os.path.isfile(logp):
                continue
            try:
                with open(logp, encoding='utf-8') as f:
                    for q in json.load(f) or []:
                        _feed_qso(q)
            except Exception:
                continue
    except Exception:
        pass


def _load_qso_archive():
    """Table SQLite qso_archive : QSO archivés par /log/reset AVANT la
    création du dossier archives/ — l'autre moitié de l'historique."""
    try:
        import sqlite3
        if not os.path.isfile('logx.db'):
            return
        con = sqlite3.connect('logx.db')
        try:
            rows = con.execute(
                'SELECT call, locator, date, extra FROM qso_archive').fetchall()
        except Exception:
            rows = []
        finally:
            con.close()
        for call, locator, date, extra in rows:
            num_rcvd = ''
            try:
                num_rcvd = (json.loads(extra or '{}') or {}).get('num_rcvd', '')
            except Exception:
                pass
            _feed_qso({'call': call, 'locator': locator, 'date': date,
                       'num_rcvd': num_rcvd})
    except Exception:
        pass


# ─── IMPORT MASTER.SCP (Super Check Partial N1MM) ────────────────────────────
# MASTER.SCP : fichier texte public (n1mm.hamdocs.com, entre autres sources),
# un indicatif de concours PAR LIGNE, sans metadata — juste "cette station a
# déjà été entendue en concours quelque part dans le monde". Aucune info
# dept/locator dedans (contrairement à calldb.json), donc aucune valeur
# ajoutée pour le pré-remplissage d'échange, mais un fragment/préfixe qui ne
# matche RIEN dans calldb.json/l'historique local peut quand même matcher un
# indicatif MASTER.SCP réel — utile en check partial pur (SCP).

def parse_master_scp(text):
    """Parse un fichier MASTER.SCP -> liste d'indicatifs valides, dédupliqués,
    triés. Format attendu : un indicatif par ligne, rien d'autre — mais un
    fichier tiers n'est jamais garanti impeccable (ligne vide, commentaire
    fortuit, espace de fin...), donc tout ce qui ne ressemble pas à un
    indicatif est silencieusement écarté plutôt que de faire échouer tout
    l'import pour une poignée de lignes suspectes."""
    calls = set()
    for n, line in enumerate(str(text or '').splitlines()):
        if n >= MAX_IMPORT_LINES:
            break
        c = line.strip().upper()
        if not c or c.startswith('#') or c.startswith(';'):
            continue
        c = c.split()[0]   # au cas où un commentaire suivrait sur la même ligne
        if _CALL_TOKEN_RE.match(c):
            calls.add(c)
    return sorted(calls)


def import_master_scp(text):
    """Importe un fichier MASTER.SCP : FUSIONNE avec ce qui est déjà en place
    (jamais un remplacement pur — un import partiel ou un ancien fichier ne
    doit pas faire régresser la base déjà enrichie), persiste, puis invalide
    le cache mémoire pour que les nouveaux indicatifs soient pris en compte
    dès la prochaine requête (au lieu d'attendre le TTL de 5 min).

    Le cycle lecture-fusion-écriture est intégralement protégé par
    _master_scp_lock (voir sa définition) : sans ça, deux imports concurrents
    (ex. deux onglets CONFIG ouverts) pouvaient chacun lire le fichier AVANT
    que l'autre n'écrive, puis se marcher dessus à l'écriture — celui qui
    écrit en second efface le travail du premier sans que rien ne le signale
    (les deux appels renvoient ok=True)."""
    new_calls = parse_master_scp(text)
    if not new_calls:
        return {'ok': False, 'error': "Aucun indicatif valide trouvé dans le fichier."}
    from logx_storage import save_json_atomic
    with _master_scp_lock:
        existing = set()
        if os.path.isfile(MASTER_SCP_FILE):
            try:
                with open(MASTER_SCP_FILE, encoding='utf-8') as f:
                    existing = set((json.load(f) or {}).get('calls', []))
            except Exception:
                existing = set()
        added = len(set(new_calls) - existing)
        merged = sorted(existing | set(new_calls))
        save_json_atomic(MASTER_SCP_FILE, {'calls': merged, 'count': len(merged)}, compact=True)
    global _built_at
    with _lock:
        _built_at = 0.0     # force la reconstruction complète au prochain accès
    return {'ok': True, 'imported': len(new_calls), 'added': added, 'total': len(merged)}


# Source publique de référence (celle-là même que N1MM+/Win-Test utilisent par
# défaut) : un fichier stable, une seule URL, maintenue à jour par la
# communauté — contrairement au Call History (propre à chaque concours,
# distribué par l'organisateur à une URL différente à chaque fois, donc pas
# de source unique automatisable ici, voir import_call_history_n1mm()).
MASTER_SCP_URL = 'http://www.supercheckpartial.com/MASTER.SCP'


def fetch_and_import_master_scp():
    """Télécharge MASTER.SCP depuis la source publique de référence et
    l'importe (voir import_master_scp) — bouton « Mettre à jour depuis
    Internet », alternative à l'upload manuel pour qui n'a pas déjà le
    fichier sous la main. Import local : mockable par les tests."""
    from logx_utils import fetch_url
    text = fetch_url(MASTER_SCP_URL, timeout=30)
    if text is None:
        return {'ok': False, 'error': 'supercheckpartial.com injoignable (réseau)'}
    return import_master_scp(text)


# ─── VÉRIFICATION N+1 (frappe légèrement fausse) ─────────────────────────────
# Comme le "busted call check" des gros loggers de concours : une distance de
# Damerau-Levenshtein de 1 entre l'indicatif tapé et un indicatif CONNU
# (calldb + MASTER.SCP + archives + log) rattrape une lettre en trop/en
# moins/substituée, ou deux lettres inversées à la frappe.

def _one_edit_away(a, b):
    """True si la distance de Damerau-Levenshtein entre `a` et `b` vaut
    EXACTEMENT 1 (substitution, insertion, suppression ou transposition de
    deux lettres adjacentes) — False si déjà identique (0) ou plus éloigné
    (>= 2). Vérification en O(n), pas la programmation dynamique complète
    O(n×m) : inutile ici (indicatifs courts, index pouvant compter des
    dizaines de milliers d'entrées à comparer)."""
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diffs = [i for i in range(la) if a[i] != b[i]]
        if len(diffs) == 1:
            return True
        if len(diffs) == 2:
            i, j = diffs
            return j == i + 1 and a[i] == b[j] and a[j] == b[i]
        return False
    # Longueurs différentes d'exactement 1 : insertion/suppression — on
    # aligne les deux chaînes en sautant AU PLUS UNE fois un caractère de la
    # plus longue (algorithme classique de "one edit distance").
    if la > lb:
        a, b = b, a
        la, lb = lb, la
    i = j = 0
    skipped = False
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
        else:
            if skipped:
                return False
            skipped = True
            j += 1
    return True


def near_matches(call, shared_log=None, limit=5):
    """Indicatifs connus à distance de Damerau-Levenshtein == 1 de `call` —
    ignoré si `call` est DÉJÀ un indicatif connu (rien à corriger) ou trop
    court (le bruit dépasserait vite l'utilité en dessous de 3 caractères).
    Triés comme suggest() : déjà travaillés d'abord, puis alphabétique."""
    call = str(call or '').strip().upper()
    if len(call) < 3:
        return []
    idx = build_index(shared_log)
    if call in idx:
        return []
    with _lock:
        _items = list(idx.items())   # instantané sous verrou (voir export_index)
    out = []
    for other, e in _items:
        if abs(len(other) - len(call)) > 1:
            continue
        if _one_edit_away(call, other):
            out.append({'call': other, 'dept': e['dept'], 'locator': e['locator'],
                        'qso_count': e['qso_count'], 'worked': e['qso_count'] > 0})
    out.sort(key=lambda c: (-c['qso_count'], c['call']))
    return out[:limit]


# ─── IMPORT CALL HISTORY (format N1MM) ───────────────────────────────────────
# Format documenté publiquement sur n1mmwp.hamdocs.com/setup/call-history/ :
# texte délimité par virgule (ou point-virgule), ORDRE DE COLONNES PAR DÉFAUT
#   Call,Name,Loc1,Loc2,Sect,State,CK,BirthDate,Exch1,Misc,Power,CqZone,
#   ITUZone,UserText,LastUpdateNote
# surchageable par une ligne directive « !!Order!!,Call,Name,... » (le
# fichier peut en contenir plusieurs, l'ordre change à partir de là). Les
# lignes vides ou commençant par '#' sont des commentaires. Seules deux
# directives affectent les champs que LogX exploite et sont honorées :
#   !!MapStateToSect!! : Sect vide -> recopie State
#   !!FourCharGridSq!! : tronque Loc1/Loc2 à 4 caractères
# Les autres directives connues (!!Validate50State!!, !!NoLoc2AltGrid!!,
# !!MapOnSection!!, !!ValidateArrlSection!!, !!AppendUserText!!/
# !!NoAppendUserText!!) pilotent une validation US/section ARRL sans
# équivalent dans LogX : reconnues (pas une erreur de parsing) mais sans effet.
#
# Contrairement à MASTER.SCP, ce fichier est PROPRE À UN CONCOURS (l'échange
# attendu — département/section/zone — n'est pas le même d'un concours à
# l'autre pour la même station) : voir _ch_slice()/import_call_history_n1mm().

_CH_DEFAULT_ORDER = ('call', 'name', 'loc1', 'loc2', 'sect', 'state', 'ck',
                     'birthdate', 'exch1', 'misc', 'power', 'cqzone',
                     'ituzone', 'usertext', 'lastupdatenote')

_ch_cache = None        # dict {CONCOURS: {CALL: {...}}} — cache mémoire du fichier
_ch_cache_mtime = None  # invalidé par comparaison de mtime, pas de TTL (fichier stable)


def _ch_split(line):
    """Sépare une ligne : virgule par défaut, point-virgule si la ligne en
    contient davantage (les deux sont acceptés par le format N1MM)."""
    return line.split(';') if line.count(';') > line.count(',') else line.split(',')


def parse_n1mm_call_history(text, contest=None):
    """Parse un fichier Call History au format N1MM -> (dict {indicatif:
    {dept?,locator?,name?,section?,zone?}}, erreurs). Jamais d'exception :
    une ligne illisible est comptée en erreur et ignorée, pas bloquante pour
    le reste du fichier (fichier tiers, pas garanti impeccable).

    `contest`, s'il est fourni, détermine si Exch1 doit être interprété comme
    un département REF (voir plus bas) — sans lui (ou pour un concours qui
    n'a pas d'échange département), Exch1 n'est jamais interprété."""
    from logx_import import _clean_text
    from logx_departments import dept_from_exchange
    from logx_definitions import CONTEST_DEFINITIONS

    # Exch1 est le champ GÉNÉRIQUE "échange attendu" du format N1MM — son sens
    # dépend entièrement du concours (n° de département REF, zone CQ, numéro
    # de série...). dept_from_exchange() accepte tout jeton à 2 chiffres
    # 01-95, ce qui recouvre aussi des zones CQ/ITU ou des numéros de série
    # d'autres concours : ne l'appliquer QUE si le concours ciblé est
    # effectivement un concours à échange département REF (dept_dxcc), sinon
    # un import CQ_WW/IARU/... avec des indicatifs étrangers produirait de
    # faux départements français (bug vérifié : Exch1='14' -> dept 'Calvados'
    # alors que 14 est en réalité une zone CQ).
    cdef = CONTEST_DEFINITIONS.get(str(contest or '').strip().upper(), {})
    dept_applicable = exchange_wants(cdef)['dept']

    order = _CH_DEFAULT_ORDER
    map_state_to_sect = False
    four_char_grid = False
    out = {}
    errors = []
    for i, raw in enumerate(str(text or '').splitlines()):
        if i >= MAX_IMPORT_LINES:
            errors.append(f"Import interrompu au-delà de {MAX_IMPORT_LINES} lignes")
            break
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('!!'):
            fields = [f.strip() for f in _ch_split(line)]
            directive = fields[0].strip('!').strip().upper()
            if directive == 'ORDER':
                cols = [c.strip('!').strip().lower() for c in fields[1:] if c.strip()]
                if cols:
                    order = cols
            elif directive == 'MAPSTATETOSECT':
                map_state_to_sect = True
            elif directive == 'FOURCHARGRIDSQ':
                four_char_grid = True
            # autre directive connue (validation US/ARRL) : sans effet ici
            continue
        cells = _ch_split(line)
        row = {}
        for idx, col in enumerate(order):
            if idx >= len(cells):
                break
            row[col] = cells[idx].strip()
        call = row.get('call', '').upper().strip()
        if not call or not _CALL_TOKEN_RE.match(call):
            errors.append(f"Ligne {i + 1} ignorée (indicatif manquant/invalide)")
            continue
        entry = {}
        name = _clean_text(row.get('name', ''))
        if name:
            entry['name'] = name
        sect = row.get('sect', '')
        if map_state_to_sect and not sect:
            sect = row.get('state', '')
        if sect:
            entry['section'] = _clean_text(sect)
        loc = row.get('loc1', '') or row.get('loc2', '')
        if four_char_grid:
            loc = loc[:4]
        norm_loc = _norm_loc(loc)
        if norm_loc:
            entry['locator'] = norm_loc
        # dept_from_exchange y reconnaît un département REF s'il y en a un
        # (réutilise le même parseur que pour un échange REÇU en direct, voir
        # _feed_qso ci-dessus) — mais SEULEMENT si `contest` est bien un
        # concours à échange département (voir dept_applicable plus haut).
        if dept_applicable:
            dept = dept_from_exchange(row.get('exch1', ''))
            if dept:
                entry['dept'] = dept
        cqzone = row.get('cqzone', '').strip()
        if cqzone:
            entry['zone'] = _clean_text(cqzone)
        if entry:
            out[call] = entry
    return out, errors


def _load_call_history_store():
    """Charge le fichier Call History importé, mis en cache par DATE DE
    MODIFICATION (pas par TTL comme l'index général : ce fichier ne change
    qu'à un import manuel explicite, comparer le mtime suffit et évite une
    reconstruction inutile à chaque requête)."""
    global _ch_cache, _ch_cache_mtime
    try:
        mtime = os.path.getmtime(CALL_HISTORY_FILE)
    except OSError:
        return {}
    if _ch_cache is not None and mtime == _ch_cache_mtime:
        return _ch_cache
    try:
        with open(CALL_HISTORY_FILE, encoding='utf-8') as f:
            data = json.load(f) or {}
    except Exception:
        data = {}
    _ch_cache = data
    _ch_cache_mtime = mtime
    return _ch_cache


def _ch_slice(contest):
    """Sous-ensemble {indicatif: {...}} du Call History importé pour CE
    concours — {} si aucun concours donné ou rien d'importé pour lui."""
    contest = str(contest or '').strip().upper()
    if not contest:
        return {}
    return _load_call_history_store().get(contest, {})


def call_history_count(contest):
    """Nombre de fiches Call History importées pour ce concours (statut
    affiché en CONFIG) — API publique équivalente à len(_ch_slice(contest))."""
    return len(_ch_slice(contest))


def _apply_call_history(entry, ch_entry):
    """Surclasse `entry` (dict dept/locator déjà construit, index général ou
    nouvelle entrée) avec les champs du Call History N1MM : PLUS SPÉCIFIQUE À
    CE CONCOURS que calldb.json, donc prioritaire ici. Ne modifie jamais
    `entry` en place (retourné tel quel si `ch_entry` est vide)."""
    if not ch_entry:
        return entry
    merged = dict(entry)
    for k in ('dept', 'locator', 'name', 'section', 'zone'):
        if ch_entry.get(k):
            merged[k] = ch_entry[k]
    return merged


def import_call_history_n1mm(contest, text):
    """Importe un fichier Call History N1MM pour UN concours donné : fusionné
    avec ce qui existe déjà pour CE concours (jamais un remplacement pur —
    mêmes règles que import_master_scp), les autres concours restent
    intacts. Les entrées déjà présentes pour ce concours sont écrasées par le
    nouveau fichier (import répété = mise à jour, pas un doublon qui
    s'accumule).

    Le cycle lecture-fusion-écriture est intégralement protégé par
    _ch_io_lock (mêmes raisons que import_master_scp/_master_scp_lock) : sans
    ça, deux imports concurrents (même sur DEUX concours différents, puisque
    c'est le même fichier store qui est lu-fusionné-écrit) pouvaient se
    marcher dessus et perdre l'un des deux jeux de fiches importées."""
    contest = str(contest or '').strip().upper()
    if not contest:
        return {'ok': False, 'error': "Concours manquant."}
    parsed, errors = parse_n1mm_call_history(text, contest)
    if not parsed:
        return {'ok': False, 'error': "Aucune entrée valide trouvée dans le fichier.",
                'errors': errors}
    from logx_storage import save_json_atomic
    global _ch_cache, _ch_cache_mtime
    with _ch_io_lock:
        store = _load_call_history_store()
        store = {k: dict(v) for k, v in store.items()}   # copie : ne pas modifier le cache en place
        slice_ = dict(store.get(contest, {}))
        slice_.update(parsed)
        store[contest] = slice_
        save_json_atomic(CALL_HISTORY_FILE, store, compact=True)
        _ch_cache = None    # invalide le cache mémoire (rechargé au prochain accès, via mtime)
        _ch_cache_mtime = None
    return {'ok': True, 'imported': len(parsed), 'total_for_contest': len(slice_),
            'errors': errors}


def build_index(shared_log=None, force=False):
    """(Re)construit l'index si le TTL est écoulé. Thread-safe."""
    global _built_at
    with _lock:
        if not force and _index and time.time() - _built_at < TTL:
            return _index
        _index.clear()
        _load_master_scp()                   # indicatifs bruts, la source la moins spécifique
        _load_calldb()                       # base large, la moins fraîche
        _load_qso_archive()                  # anciens QSO (table SQLite)
        _load_archives()                     # QSO réels archivés (dossiers)
        for q in (shared_log or []):         # log actif = le plus frais
            _feed_qso(q)
        _built_at = time.time()
        return _index


def update_from_qso(qso):
    """Enrichit l'index à chaud quand un QSO vient d'être loggé."""
    with _lock:
        if _index:
            _feed_qso(qso)


def suggest(fragment, shared_log=None, limit=12, contest=None):
    """Suggestions SCP : d'abord les indicatifs qui COMMENCENT par le
    fragment, puis ceux qui le CONTIENNENT (check partial classique), puis —
    si `contest` est fourni — les indicatifs connus SEULEMENT via le Call
    History importé pour ce concours (jamais travaillés, absents de
    calldb/MASTER.SCP/l'historique). Tri : déjà travaillés d'abord
    (qso_count), puis alphabétique. `contest` surclasse aussi dept/locator
    des indicatifs déjà trouvés avec les données propres à ce concours."""
    fragment = str(fragment or '').strip().upper()
    if len(fragment) < 2:
        return []
    idx = build_index(shared_log)
    with _lock:
        _items = list(idx.items())   # instantané sous verrou : évite 'dictionary changed size' si un QSO est logué en concurrence (update_from_qso)
    ch_slice = _ch_slice(contest)
    starts, contains = [], []
    for call, e in _items:
        if call.startswith(fragment):
            starts.append((call, e))
        elif fragment in call:
            contains.append((call, e))
    key = lambda ce: (-ce[1]['qso_count'], ce[0])
    starts.sort(key=key)
    contains.sort(key=key)
    ch_only = []
    if ch_slice:
        seen = {c for c, _ in _items}
        for call, fields in ch_slice.items():
            if call in seen or not (call.startswith(fragment) or fragment in call):
                continue
            ch_only.append((call, {'dept': None, 'locator': None,
                                    'qso_count': 0, 'last_date': None}))
        ch_only.sort(key=key)
    out = []
    for call, e in (starts + contains + ch_only)[:min(limit, MAX_SUGGEST)]:
        merged = _apply_call_history(e, ch_slice.get(call)) if ch_slice else e
        item = {'call': call, 'dept': merged['dept'], 'locator': merged['locator'],
                'qso_count': e['qso_count'], 'last_date': e['last_date'],
                'worked': e['qso_count'] > 0}
        if merged.get('name'):
            item['name'] = merged['name']
        if merged.get('section'):
            item['section'] = merged['section']
        if merged.get('zone'):
            item['zone'] = merged['zone']
        out.append(item)
    return out


def lookup(call, shared_log=None, contest=None):
    """Fiche exacte d'un indicatif (None si inconnu ET absent du Call History
    de `contest`). `contest`, s'il est fourni, surclasse dept/locator avec le
    Call History N1MM importé pour ce concours précis, et suffit à lui seul
    à faire exister la fiche (station jamais travaillée mais présente dans le
    fichier Call History du concours en cours)."""
    call = str(call or '').strip().upper()
    if len(call) < 3:
        return None
    e = build_index(shared_log).get(call)
    ch_entry = _ch_slice(contest).get(call) if contest else None
    if not e and not ch_entry:
        return None
    base = e or {'dept': None, 'locator': None, 'qso_count': 0, 'last_date': None}
    merged = _apply_call_history(base, ch_entry)
    out = {'call': call, 'dept': merged['dept'], 'locator': merged['locator'],
           'qso_count': base['qso_count'], 'last_date': base['last_date'],
           'worked': base['qso_count'] > 0}
    if merged.get('name'):
        out['name'] = merged['name']
    if merged.get('section'):
        out['section'] = merged['section']
    if merged.get('zone'):
        out['zone'] = merged['zone']
    return out


def export_index(shared_log=None, contest=None):
    """Index complet sérialisable pour le client (GET /call/index) — même
    forme que calldb.json ('calls' + 'depts') pour remplacer sa source sans
    changer le rendu, enrichie de qso_count/worked/last_date (historique).
    `contest`, s'il est fourni, surclasse dept/locator/name/section avec le
    Call History N1MM importé pour ce concours et ajoute les indicatifs qui
    n'existent QUE dans ce fichier (jamais travaillés par ailleurs)."""
    idx = build_index(shared_log)
    with _lock:
        _items = list(idx.items())   # instantané sous verrou (voir suggest)
    ch_slice = _ch_slice(contest)
    calls = {}
    for call, e in _items:
        merged = _apply_call_history(e, ch_slice.get(call)) if ch_slice else e
        c = {}
        if merged.get('dept'):
            c['dept'] = merged['dept']
        if merged.get('locator'):
            c['locator'] = merged['locator']
        if e['qso_count']:
            c['qso_count'] = e['qso_count']
            c['worked'] = True
        if e['last_date']:
            c['last_date'] = e['last_date']
        if merged.get('name'):
            c['name'] = merged['name']
        if merged.get('section'):
            c['section'] = merged['section']
        if merged.get('zone'):
            c['zone'] = merged['zone']
        calls[call] = c
    for call, fields in ch_slice.items():
        if call in calls:
            continue
        c = {}
        if fields.get('dept'):
            c['dept'] = fields['dept']
        if fields.get('locator'):
            c['locator'] = fields['locator']
        if fields.get('name'):
            c['name'] = fields['name']
        if fields.get('section'):
            c['section'] = fields['section']
        if fields.get('zone'):
            c['zone'] = fields['zone']
        calls[call] = c
    depts = {}
    try:
        from logx_departments import DEPARTMENTS
        depts = DEPARTMENTS
    except Exception:
        pass
    return {'calls': calls, 'depts': depts, 'count': len(calls)}


def exchange_wants(cdef):
    """Ce que l'échange du concours attend, d'après la définition :
    {'dept': bool, 'locator': bool} — pilote le pré-remplissage client."""
    ex = str((cdef or {}).get('exchange', '')).lower()
    stype = str(((cdef or {}).get('scoring', {}) or {}).get('type', ''))
    return {
        'dept': 'dept' in ex or stype == 'dept_dxcc',
        'locator': 'locator' in ex or stype in ('km_x_locators', 'km_x_large_locator_squares'),
    }
