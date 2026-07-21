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
    with qtc_lock:
        return sum(q.get('count', 0) or 0 for q in qtc_log
                   if not contest_id or q.get('contest', '') in ('', contest_id))


def qtc_count_for_call(call, contest_id=''):
    """Total déjà échangé avec cette station (plafond règlement : 10)."""
    base = (call or '').upper().strip()
    with qtc_lock:
        return sum(q.get('count', 0) or 0 for q in qtc_log
                   if str(q.get('call', '')).upper().strip() == base
                   and (not contest_id or q.get('contest', '') in ('', contest_id)))


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
