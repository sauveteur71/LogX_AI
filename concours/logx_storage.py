# -*- coding: utf-8 -*-
"""Log partagé multi-opérateur : état en mémoire + persistance SQLite.

Architecture : shared_log (liste en mémoire) reste la source de vérité que
tous les modules consultent ; chaque save_log_to_disk() la réécrit dans
logx.db (table qso indexée indicatif/bande/mode, transactionnelle —
zéro risque de troncature) + un shared_log.json de secours lisible.
Migration one-shot : au premier démarrage sans base, shared_log.json est
importé. /log/reset ARCHIVE les QSO (table qso_archive) au lieu de les
perdre : l'historique multi-concours survit aux remises à zéro."""

import json
import os
import sqlite3
import threading
import uuid

DB_FILE = 'logx.db'
_db_lock = threading.Lock()

# Drapeau de sûreté : passé à True si le chargement du log échoue AU DÉMARRAGE
# alors que la base existe (verrou transitoire antivirus / Synology Drive, base
# momentanément illisible). Tant qu'il est vrai, save_log_to_disk() REFUSE
# d'écrire : sans ce garde-fou, le premier QSO saisi déclencherait un
# DELETE FROM qso + réécriture de shared_log.json avec un log vide, détruisant
# tout l'historique. On préfère bloquer la persistance (l'utilisateur relance
# une fois le verrou levé) plutôt que perdre les données.
load_failed = False

# Colonnes structurées (indexables) ; tout le reste du QSO va dans extra (JSON)
_CORE = ('id', 'call', 'band', 'mode', 'contest', 'date', 'time',
         'operator', 'points', 'locator')


def _db():
    conn = sqlite3.connect(DB_FILE)
    cols = ('rowid_pk INTEGER PRIMARY KEY AUTOINCREMENT, id INTEGER, call TEXT, '
            'band TEXT, mode TEXT, contest TEXT, date TEXT, time TEXT, '
            'operator TEXT, points REAL, locator TEXT, extra TEXT')
    conn.execute(f'CREATE TABLE IF NOT EXISTS qso ({cols})')
    conn.execute(f'CREATE TABLE IF NOT EXISTS qso_archive ({cols}, archived_at TEXT)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_qso_cbm ON qso(call, band, mode)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_qso_contest ON qso(contest)')
    return conn


def _row_from_qso(q):
    extra = {k: v for k, v in q.items() if k not in _CORE}
    return tuple(q.get(k) for k in _CORE) + (json.dumps(extra, ensure_ascii=False),)


def _qso_from_row(row):
    q = {k: row[i] for i, k in enumerate(_CORE) if row[i] is not None}
    try:
        q.update(json.loads(row[len(_CORE)] or '{}'))
    except Exception:
        pass
    return q

# ─── LOG PARTAGÉ MULTI-OPÉRATEUR ─────────────────────────────────────────────
shared_log = []        # log en mémoire partagé entre tous les postes
log_lock = threading.Lock()

# Compteur de fraîcheur : incrémenté à CHAQUE modification de shared_log
# (ajout/édition/suppression/import/reset). Permet à /log/list de répondre par
# un payload minimal si le client a déjà cette version au lieu de retransmettre
# tout le log à chaque poll de 5 s — avec un log de plusieurs milliers de QSO,
# ça représentait plusieurs Mo toutes les 5 s pour rien la plupart du temps
# (aucun changement entre deux polls successifs). Simple compteur, pas de
# verrou dédié : un += 1 sur un entier est atomique en pratique sous CPython
# (protégé par le GIL), et une imprécision occasionnelle ici ne coûterait
# qu'un rafraîchissement complet de plus — jamais une incohérence de données.
log_version = 0


def bump_log_version():
    """À appeler après TOUTE modification de shared_log."""
    global log_version
    log_version += 1
    return log_version

# ─── SYNCHRONISATION DIFFÉRENTIELLE DE /log/list (?since=) ───────────────────
# log_version (ci-dessus) dit SEULEMENT si quelque chose a changé. Ce qui suit
# permet de savoir QUOI a changé, pour que /log/list renvoie un delta (QSO
# ajoutés/modifiés + id supprimés depuis une version connue du client) au lieu
# de retransmettre tout shared_log à chaque poll — un simple compteur global
# ne suffit pas, il faut savoir QUELS QSO ont bougé à quelle version.

# Jeton unique par démarrage du serveur. log_version repart de 0 à chaque
# redémarrage (voir commentaire ci-dessus) : sans ce jeton, un ?since= client
# datant d'AVANT un redémarrage pourrait par coincidence retomber dans la
# nouvelle plage de versions (ex. since=5 encore valide après redémarrage) et
# faire croire à tort qu'aucun QSO plus ancien n'a changé, alors que shared_log
# a été rechargé depuis zéro. Le client doit renvoyer ce jeton avec son
# ?since= ; s'il ne correspond plus au jeton courant, ?since= est traité comme
# invalide (repli sur liste complète, toujours correcte).
SERVER_BOOT_ID = uuid.uuid4().hex

# Tombstones de suppression INDIVIDUELLE (/log/delete) : un QSO supprimé
# disparaît de shared_log, donc son '_v' (voir stamp_qso_version) ne suffit
# pas à prévenir un client qui l'a encore dans son cache local — il faut une
# trace explicite « cet id a disparu à telle version ». Bornée : les
# suppressions EN MASSE (reset, archive clear=true, changement de portée
# concours) passent par mark_hard_reset() plutôt que d'empiler un tombstone
# par QSO effacé (potentiellement tout un concours d'un coup).
deleted_qsos = []                  # [{'id': .., 'v': ..}, ...]
_MAX_DELETED_TOMBSTONES = 2000
hard_reset_version = 0             # un ?since= antérieur à cette version n'est plus fiable


def stamp_qso_version(qso):
    """Marque `qso` avec la version de log COURANTE — à appeler juste après
    bump_log_version() pour tout ajout/modification individuelle d'un QSO,
    afin que /log/list?since=N puisse ne renvoyer que les QSO plus récents que
    N sans retransmettre tout le log."""
    qso['_v'] = log_version
    return qso


def mark_qso_deleted(qso_id):
    """Tombstone pour UNE suppression individuelle de QSO (jamais pour un
    reset/clear en masse, voir mark_hard_reset)."""
    global deleted_qsos
    deleted_qsos.append({'id': qso_id, 'v': log_version})
    if len(deleted_qsos) > _MAX_DELETED_TOMBSTONES:
        deleted_qsos = deleted_qsos[-_MAX_DELETED_TOMBSTONES:]


def mark_hard_reset():
    """À appeler juste après un effacement en masse (reset, archive
    clear=true) OU un changement de portée concours (/config/save, qui change
    ce que le log filtré désigne SANS toucher un seul QSO) : tout ?since=
    antérieur à la version courante devient invalide, /log/list se replie
    alors sur la liste complète (déjà correcte) au lieu d'un delta muet."""
    global hard_reset_version
    hard_reset_version = log_version

# ─── PORTÉE CONCOURS (contest + année) ───────────────────────────────────────
# shared_log est UN SEUL log global (pas de fichier séparé par concours) : le
# log « simple » (usage perso) et chaque concours y cohabitent, distingués
# uniquement par le champ 'contest' de chaque QSO. Avant ces deux fonctions,
# tout le code qui voulait savoir « ce QSO appartient-il au concours actif ? »
# traitait un QSO SANS tag (contest == '' — import ADIF générique, WSJT-X sans
# concours actif, ancien log perso) comme un JOKER comptant pour N'IMPORTE
# QUEL concours (motif `q.get('contest','') in ('', contest_id)` répété dans
# 7 endroits indépendants) — ce qui faisait apparaître la carte/les stats
# entièrement « travaillées » dès la sélection d'un concours, avant même le
# premier QSO. Ces fonctions remplacent ce motif par une portée EXPLICITE
# 'contest_id#année' : un QSO non tagué ne compte plus JAMAIS pour un concours
# précis, et un même concours annuel ne se confond plus d'une année à l'autre
# (l'identifiant de concours lui-même, ex. 'REF_CDF_HF_SSB', ne porte pas
# l'année — logx_definitions.CONTEST_DEFINITIONS est un référentiel de RÈGLES,
# pas d'éditions datées).

def qso_scope_id(qso):
    """Portée d'un QSO déjà loggué, dérivée de SES PROPRES champs 'contest' et
    'date' (jamais de la config courante — un QSO importé ou loggué l'an
    dernier garde sa portée propre, indépendamment de ce qui est configuré
    maintenant). '' si non tagué à un concours (log simple, import générique,
    WSJT-X sans concours actif) : ces QSO ne doivent jamais matcher la portée
    d'un concours précis (voir active_scope_id)."""
    qso = qso or {}
    contest = str(qso.get('contest', '') or '').strip()
    if not contest:
        return ''
    date = str(qso.get('date', '') or '')
    year = date[:4] if len(date) >= 4 and date[:4].isdigit() else ''
    return f'{contest}#{year}' if year else contest


def active_scope_id(cfg):
    """Portée du concours actuellement configuré, même format que
    qso_scope_id() — l'année vient de contest_start_date (ou de l'année UTC en
    cours si absente). '' si aucun concours n'est sélectionné : dans ce cas
    les filtres 'travaillé'/'portée' ne doivent RIEN restreindre (comportement
    historique préservé quand la config est incomplète)."""
    cfg = cfg or {}
    contest = str(cfg.get('contest', '') or '').strip()
    if not contest:
        return ''
    start = str(cfg.get('contest_start_date', '') or '')
    year = start[:4] if len(start) >= 4 and start[:4].isdigit() else ''
    if not year:
        import datetime
        year = str(datetime.datetime.utcnow().year)
    return f'{contest}#{year}'


def cfg_scope_id(cfg):
    """Portée à utiliser pour filtrer shared_log/qtc_log selon la config
    courante. '' en mode 'simple' (jamais de filtrage — le logbook simple est
    le journal personnel complet, quel que soit le dernier concours resté en
    config), sinon active_scope_id(cfg) (elle-même '' si aucun concours n'est
    sélectionné, auquel cas rien n'est filtré non plus)."""
    if (cfg or {}).get('usage_mode') == 'simple':
        return ''
    return active_scope_id(cfg)


# Verrou dédié à calldb.json : écrit depuis plusieurs threads
# (lookups HamQTH, imports, mises à jour navigateur).
calldb_lock = threading.Lock()

# ─── QTC (WAE) ───────────────────────────────────────────────────────────────
# Trafic QTC échangé : chaque QTC transféré vaut 1 point au WAE
# (score = (QSO + QTC) × mults). Max 10 par station correspondante.
qtc_log = []           # [{call, count, contest, date, time}]
qtc_lock = threading.Lock()
QTC_FILE = 'qtc_log.json'


def load_qtc_from_disk():
    try:
        if os.path.exists(QTC_FILE):
            with open(QTC_FILE, encoding='utf-8') as f:
                qtc_log[:] = json.load(f)
            print(f"[QTC] {sum(q.get('count', 0) for q in qtc_log)} QTC charges")
    except Exception as e:
        print(f"[QTC] Chargement impossible : {e}")


def save_qtc_to_disk():
    try:
        with qtc_lock:
            data = list(qtc_log)
        save_json_atomic(QTC_FILE, data)
    except Exception as e:
        print(f"[QTC] Erreur sauvegarde : {e}")


def qtc_total(contest_id=''):
    """`contest_id` est une PORTÉE (voir active_scope_id) — un QTC non tagué
    ne compte jamais pour une portée précise."""
    with qtc_lock:
        return sum(q.get('count', 0) or 0 for q in qtc_log
                   if not contest_id or qso_scope_id(q) == contest_id)


def qtc_count_for_call(call, contest_id=''):
    """Total déjà échangé avec cette station (plafond règlement : 10).
    `contest_id` est une PORTÉE (voir active_scope_id)."""
    base = (call or '').upper().strip()
    with qtc_lock:
        return sum(q.get('count', 0) or 0 for q in qtc_log
                   if str(q.get('call', '')).upper().strip() == base
                   and (not contest_id or qso_scope_id(q) == contest_id))


def save_json_atomic(path, data, lock=None, compact=False):
    """Écriture JSON ATOMIQUE : fichier temporaire dans le même dossier puis
    os.replace — un crash ou une coupure en pleine écriture ne peut plus
    laisser un fichier tronqué. Thread-safe si un lock est fourni."""
    import tempfile

    def _write():
        target_dir = os.path.dirname(os.path.abspath(path)) or '.'
        fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + '.',
                                   suffix='.tmp', dir=target_dir)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                if compact:
                    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
                else:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    if lock is not None:
        with lock:
            _write()
    else:
        _write()


def save_log_to_disk():
    """Persiste le log : SQLite (transaction, primaire) + JSON de secours."""
    if load_failed:
        # Le chargement au démarrage a échoué avec une base existante : écrire
        # maintenant écraserait l'historique par le log (quasi) vide en mémoire.
        print("[LOG] Sauvegarde BLOQUÉE : chargement initial en échec — "
              "redémarre le logiciel une fois le verrou sur la base levé.")
        return
    try:
        with log_lock:
            data = list(shared_log)  # copie sous verrou
        with _db_lock:
            conn = _db()
            with conn:  # transaction : réécriture tout-ou-rien
                conn.execute('DELETE FROM qso')
                conn.executemany(
                    f"INSERT INTO qso ({','.join(_CORE)}, extra) "
                    f"VALUES ({','.join('?' * (len(_CORE) + 1))})",
                    [_row_from_qso(q) for q in data])
            conn.close()
        save_json_atomic('shared_log.json', data)
    except Exception as e:
        print(f"[LOG] Erreur sauvegarde : {e}")


def archive_current_log():
    """Copie les QSO courants dans qso_archive (appelé AVANT un reset) :
    une remise à zéro ne détruit plus jamais d'historique."""
    import datetime
    try:
        with log_lock:
            data = list(shared_log)
        if not data:
            return 0
        stamp = datetime.datetime.utcnow().isoformat()
        with _db_lock:
            conn = _db()
            with conn:
                conn.executemany(
                    f"INSERT INTO qso_archive ({','.join(_CORE)}, extra, archived_at) "
                    f"VALUES ({','.join('?' * (len(_CORE) + 2))})",
                    [_row_from_qso(q) + (stamp,) for q in data])
            conn.close()
        print(f"[LOG] {len(data)} QSO archives avant reset")
        return len(data)
    except Exception as e:
        print(f"[LOG] Archivage impossible : {e}")
        return 0


def load_log_from_disk():
    """Charge le log au démarrage : SQLite si présent, sinon migration
    one-shot depuis shared_log.json.

    Mutation EN PLACE (shared_log[:] = ...) et non réassignation : les autres
    modules importent shared_log par référence, une réassignation les laisserait
    pointer sur l'ancienne liste vide."""
    try:
        if os.path.exists(DB_FILE):
            with _db_lock:
                conn = _db()
                rows = conn.execute(
                    f"SELECT {','.join(_CORE)}, extra FROM qso ORDER BY rowid_pk"
                ).fetchall()
                conn.close()
            shared_log[:] = [_qso_from_row(r) for r in rows]
            print(f"[LOG] {len(shared_log)} QSO charges depuis {DB_FILE}")
            return
        if os.path.exists('shared_log.json'):
            with open('shared_log.json', 'r', encoding='utf-8') as f:
                shared_log[:] = json.load(f)
            print(f"[LOG] Migration one-shot : {len(shared_log)} QSO "
                  f"shared_log.json -> {DB_FILE}")
            save_log_to_disk()
    except Exception as e:
        print(f"[LOG] Impossible de charger le log : {e}")
        # Base présente mais illisible : on interdit toute réécriture destructive
        # jusqu'au prochain démarrage réussi (voir load_failed / save_log_to_disk).
        if os.path.exists(DB_FILE):
            global load_failed
            load_failed = True
            print(f"[LOG] ⚠ {DB_FILE} présent mais illisible — persistance "
                  f"GELÉE pour protéger l'historique. Ferme les programmes qui "
                  f"verrouillent le fichier (antivirus, sync) puis redémarre.")
