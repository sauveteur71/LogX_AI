# -*- coding: utf-8 -*-
"""Synchronisation MySQL partagée — 4e mécanisme multi-poste, aux côtés de
Cloud Sync (dossier de fichiers, logx_cloudsync.py) et de la synchro LAN
directe (logx_lan_sync.py). Cas d'usage visé (F4GLD, 06/08/2026) : un
radio-club où plusieurs opérateurs partagent EN QUASI TEMPS RÉEL un même log
de concours — mais fonctionne aussi bien pour simplement deux postes d'un
même radioamateur partageant le même log.

Chaque poste garde `shared_log` en mémoire comme aujourd'hui (AUCUN
changement aux ~660 endroits du code qui le lisent déjà) — ce module ajoute
seulement une tâche de fond qui pousse/tire périodiquement vers une table
MySQL partagée, exactement comme logx_cloudsync.py le fait déjà vers un
dossier de fichiers. Une vraie base transactionnelle simplifie nettement le
mécanisme par rapport à Cloud Sync :
  - authentification native (identifiants MySQL) — pas besoin de HMAC/secret
    d'équipe ni de protection anti-rejeu (voir la docstring de
    logx_cloudsync.py pour tout ce que ces deux points-là exigent en
    l'absence de vraie transaction) ;
  - écriture atomique par ligne (INSERT ... ON DUPLICATE KEY UPDATE, clé =
    id du QSO, même identité de fusion que Cloud Sync — id = Date.now() côté
    client, voir logx_storage.reserve_qso_id_locked) : MySQL garantit que
    l'écriture d'UNE ligne reste atomique (jamais de ligne à moitié écrite
    entre deux postes qui pushent au même instant) — mais PAS que deux postes
    visent forcément des lignes DIFFÉRENTES pour deux QSO différents, voir la
    limite assumée ci-dessous ;
  - une suppression se propage par une simple colonne `deleted_at` plutôt
    que des fichiers de tombstones séparés avec anti-résurrection.

Dépendance optionnelle `pymysql` (PAS dans la stdlib, contrairement au reste
du projet — voir requirements.txt) : import protégé par HAS_PYMYSQL, comme
HAS_PYSERIAL/HAS_CRYPTOGRAPHY/HAS_PAHO ailleurs dans ce projet. Son absence
ne doit jamais empêcher LogX AI de démarrer ni de fonctionner sans MySQL.

Limites assumées :
  - les horodatages `updated_at`/`deleted_at` sont posés côté CLIENT
    (time.time() du poste qui écrit), pas par MySQL (NOW() serveur) — une
    dérive d'horloge notable entre deux postes pourrait retarder la
    propagation d'une correction/suppression d'un cycle. Acceptable pour un
    radio-club sur le même réseau local (horloges généralement proches),
    documenté ici plutôt que "résolu" par une synchronisation d'horloge hors
    de portée de ce module ;
  - même choix d'architecture que logx_cloudsync.py, qui a EXACTEMENT la
    même limite et la documente tout aussi honnêtement plutôt que de
    prétendre le contraire : l'id du QSO est posé par le CLIENT (Date.now()
    en millisecondes) SANS aucun sel par poste ni coordination inter-poste —
    logx_storage.reserve_qso_id_locked ne garantit l'unicité que LOCALEMENT,
    par rapport au shared_log du poste qui écrit. Si deux postes PHYSIQUES
    différents créent chacun un QSO à la MÊME milliseconde, ils produisent le
    même id ; comme la table MySQL a id pour clé primaire, le second push
    écrase silencieusement le premier (data=VALUES(data)) — deux QSO réels
    distincts fusionnent alors en une seule ligne. Ce n'est PAS un cas où
    MySQL protège quoi que ce soit : la garantie d'atomicité ci-dessus porte
    sur l'écriture d'une ligne, pas sur le fait que deux QSO distincts
    obtiennent des lignes distinctes. Probabilité très faible en usage
    radio-club réel, non résolue ici — un changement de schéma d'id (salage
    par poste) toucherait aussi logx_cloudsync.py et est hors de portée de
    ce module."""
import json
import os
import threading
import time
import concurrent.futures as _cf

from logx_utils import utcnow, qso_key

try:
    import pymysql as _pymysql_mod
    HAS_PYMYSQL = True
except Exception:
    _pymysql_mod = None
    HAS_PYMYSQL = False

TABLE = 'logx_qso'
_STAMP_FILE = 'mysql_sync_state.json'
DEFAULT_PORT = 3306

# Même raisonnement que SYNC_TIMEOUT dans logx_cloudsync.py : une connexion
# MySQL peut rester bloquée bien au-delà de tout timeout socket si le serveur
# est injoignable via un chemin réseau anormal (DNS lent, pare-feu qui laisse
# traîner la connexion) — toute la synchronisation tourne donc dans un thread
# jetable dont on borne l'ATTENTE (SYNC_TIMEOUT côté appelant). Ça ne suffit
# PAS à soi seul : .result(timeout=SYNC_TIMEOUT) abandonne seulement l'ATTENTE
# du thread appelant, il n'annule jamais le worker en cours — un gel réseau
# SILENCIEUX survenant APRÈS l'établissement de la connexion (pare-feu qui
# laisse traîner la connexion TCP sans la couper) bloquerait alors
# cur.execute()/fetchall() indéfiniment, gardant _sync_serial_lock acquis
# pour toujours. D'où SOCKET_TIMEOUT ci-dessous, passé à pymysql en
# read_timeout/write_timeout : lui borne le SOCKET lui-même, pas seulement
# l'attente de l'appelant. Fixé légèrement SOUS SYNC_TIMEOUT pour que le
# socket lâche avant que l'appelant abandonne (sinon le worker resterait
# bloqué plus longtemps que ce que sync_now() a déjà signalé comme échoué).
SYNC_TIMEOUT = 12
CONNECT_TIMEOUT = 5
SOCKET_TIMEOUT = 10
_SYNC_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=3, thread_name_prefix='mysqlsync')

# Une seule synchronisation à la fois (même motif que _sync_serial_lock de
# logx_cloudsync.py) — évite que deux cycles concurrents (bouton "synchroniser
# maintenant" + boucle de fond) amorcent chacun leur propre vue de shared_log
# et réintroduisent un doublon transitoire.
_sync_serial_lock = threading.Lock()

_last_error = {'ts': 0, 'msg': '', 'host': '', 'database': ''}


def mysql_settings(cfg):
    cfg = cfg or {}
    mode = (cfg.get('mysql_mode') or 'off').strip().lower()
    if mode not in ('full', 'push', 'off'):
        mode = 'off'
    host = (cfg.get('mysql_host') or '').strip()
    database = (cfg.get('mysql_database') or '').strip()
    try:
        port = int(cfg.get('mysql_port') or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    call = cfg.get('callsign_contest') or cfg.get('callsign') or 'poste'
    return {
        'enabled': mode != 'off' and bool(host) and bool(database),
        'mode': mode,
        'host': host,
        'port': port,
        'user': (cfg.get('mysql_user') or '').strip(),
        'password': cfg.get('mysql_password') or '',
        'database': database,
        'source': f'{str(call).strip()[:24]}',
    }


def _connect(s, connect_timeout=CONNECT_TIMEOUT):
    if not HAS_PYMYSQL:
        raise RuntimeError("pymysql n'est pas installé — pip install pymysql")
    # read_timeout/write_timeout : sans eux pymysql laisse le socket sans
    # AUCUNE limite après la connexion (None par défaut) — voir le
    # commentaire sur SOCKET_TIMEOUT ci-dessus, un gel réseau après connexion
    # bloquerait sinon cur.execute()/fetchall() indéfiniment.
    return _pymysql_mod.connect(
        host=s['host'], port=s['port'], user=s['user'], password=s['password'],
        database=s['database'], connect_timeout=connect_timeout,
        read_timeout=SOCKET_TIMEOUT, write_timeout=SOCKET_TIMEOUT,
        autocommit=True, charset='utf8mb4')


def _ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id BIGINT PRIMARY KEY,
                data LONGTEXT NOT NULL,
                updated_at DOUBLE NOT NULL,
                deleted_at DOUBLE NULL,
                source VARCHAR(64) NOT NULL,
                INDEX idx_updated (updated_at),
                INDEX idx_deleted (deleted_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)


# ─── OCCUPATION DES BANDES (canal MySQL, distant temps réel) ─────────────────
# Table SÉPARÉE du log (une ligne par poste, clé = station/iid) — le sync du
# carnet n'est jamais touché. Upsert de son propre statut, lecture des autres.
OCC_TABLE = 'occupancy'


def _ensure_occ_schema(conn):
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {OCC_TABLE} (
                station VARCHAR(64) PRIMARY KEY,
                call VARCHAR(32),
                band VARCHAR(16),
                mode VARCHAR(16),
                ts DOUBLE NOT NULL,
                INDEX idx_ts (ts)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)


def _publier_occupation_mysql(conn, iid, statut):
    """Upsert du statut de CE poste (band/mode) — une ligne par station."""
    if not statut:
        return
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {OCC_TABLE} (station, call, band, mode, ts) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE call=VALUES(call), band=VALUES(band), "
            "mode=VALUES(mode), ts=VALUES(ts)",
            (iid, statut.get('call', ''), statut.get('band', ''),
             statut.get('mode', ''), statut.get('ts', 0) or 0))


def _lire_occupation_mysql(conn, my_iid):
    """Lit les statuts des AUTRES postes -> enregistrer_pair (occupation fusionnée)."""
    import logx_occupancy as occ
    with conn.cursor() as cur:
        cur.execute(f"SELECT station, call, band, mode, ts FROM {OCC_TABLE} "
                    "WHERE station <> %s", (my_iid,))
        for row in cur.fetchall():
            occ.enregistrer_pair({'station': row[0], 'call': row[1], 'band': row[2],
                                  'mode': row[3], 'ts': row[4]})


def test_connection(host, port, user, password, database):
    """Test ÉPHÉMÈRE (bouton CONFIG) : connecte, crée le schéma si absent,
    ferme — ne touche jamais à la synchronisation périodique."""
    if not HAS_PYMYSQL:
        return {'ok': False, 'error': "pymysql n'est pas installé sur ce poste "
                "— pip install pymysql"}
    if not host or not database:
        return {'ok': False, 'error': 'Hôte ou base de données manquant'}
    try:
        port = int(port or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    try:
        conn = _pymysql_mod.connect(host=host, port=port, user=user or '',
                                    password=password or '', database=database,
                                    connect_timeout=CONNECT_TIMEOUT, autocommit=True,
                                    charset='utf8mb4')
    except Exception as e:
        return {'ok': False, 'error': f"Connexion impossible à {host}:{port} : {e}"}
    try:
        _ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
            count = cur.fetchone()[0]
        return {'ok': True, 'qso_count': count}
    except Exception as e:
        return {'ok': False, 'error': f"Table {TABLE} inaccessible : {e}"}
    finally:
        conn.close()


def _qso_key(q):
    return qso_key(q)


def _load_stamp():
    try:
        if os.path.exists(_STAMP_FILE):
            with open(_STAMP_FILE, encoding='utf-8') as f:
                data = json.load(f) or {}
            return data
    except Exception:
        pass
    return {}


def _save_stamp(data):
    try:
        with open(_STAMP_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception:
        pass  # état advisoire — une écriture ratée dégrade la synchro,
              # jamais la disponibilité du serveur (même tolérance que
              # logx_cloudsync._stamp())


def sync_now(cfg, shared_log):
    """Synchronise selon le mode configuré. Retourne
    {'ok', 'mode', 'pushed', 'pulled', 'removed'} ou {'ok': False, 'error'}."""
    try:
        r = _SYNC_EXECUTOR.submit(_sync_now_blocking, cfg, shared_log).result(timeout=SYNC_TIMEOUT)
    except _cf.TimeoutError:
        r = {'ok': False, 'error': f"Serveur MySQL trop lent à répondre "
                f"(> {SYNC_TIMEOUT}s) — vérifie l'adresse/le pare-feu."}
    s = mysql_settings(cfg)
    if s.get('enabled'):
        if r.get('ok'):
            _last_error.update(ts=0, msg='', host='', database='')
        else:
            _last_error.update(ts=time.time(), msg=r.get('error', ''),
                               host=s.get('host', ''), database=s.get('database', ''))
    return r


def _sync_now_blocking(cfg, shared_log):
    with _sync_serial_lock:
        return _sync_now_locked(cfg, shared_log)


def _sync_now_locked(cfg, shared_log):
    s = mysql_settings(cfg)
    if not s['enabled']:
        return {'ok': False, 'error': 'Synchro MySQL désactivée ou incomplète (CONFIG)'}
    try:
        conn = _connect(s)
    except Exception as e:
        return {'ok': False, 'error': f"Connexion impossible à {s['host']}:{s['port']} : {e}"}
    try:
        _ensure_schema(conn)
        local = list(shared_log or [])
        now = time.time()

        # ── PUSH : chaque QSO local, INSERT ... ON DUPLICATE KEY UPDATE sur
        # id — comme logx_cloudsync réécrit tout son fichier à chaque cycle
        # (le log d'un contest tient sur quelques milliers de lignes, pas
        # besoin de suivi différentiel). La clause UPDATE ne touche PAS
        # deleted_at : ce poste garde encore ce QSO dans son shared_log local
        # (il n'a peut-être pas encore pull la suppression faite par un autre
        # poste), donc un push routinier ne doit jamais pouvoir écraser un
        # tombstone posé entre-temps par quelqu'un d'autre — ça ressusciterait
        # silencieusement une suppression et bloquerait sa propagation tant
        # que CE poste garde le QSO en mémoire. Il n'existe aucune
        # fonctionnalité de restauration d'un QSO supprimé ailleurs dans
        # l'appli : rien ne dépend d'un push qui réinitialiserait deleted_at.
        pushed = 0
        if local:
            with conn.cursor() as cur:
                for q in local:
                    qid = q.get('id')
                    if qid is None:
                        continue
                    cur.execute(
                        f"INSERT INTO {TABLE} (id, data, updated_at, deleted_at, source) "
                        f"VALUES (%s, %s, %s, NULL, %s) "
                        f"ON DUPLICATE KEY UPDATE data=VALUES(data), updated_at=VALUES(updated_at), "
                        f"source=VALUES(source)",
                        (int(qid), json.dumps(q), now, s['source']))
                    pushed += 1

        # ── Suppressions locales (logx_storage.deleted_qsos, même source que
        # logx_cloudsync) : marque deleted_at plutôt que DELETE — un DELETE
        # SQL perdrait la trace pour les autres postes qui n'ont pas encore
        # pull ce cycle-ci.
        import logx_storage as storage
        mem_deleted = {d.get('id') for d in list(storage.deleted_qsos)} - {None}
        if mem_deleted:
            with conn.cursor() as cur:
                for qid in mem_deleted:
                    cur.execute(
                        f"UPDATE {TABLE} SET deleted_at=%s WHERE id=%s AND deleted_at IS NULL",
                        (now, int(qid)))

        pulled = 0
        removed_count = 0
        if s['mode'] == 'full':
            stamp = _load_stamp()
            key = f"{s['host']}:{s['port']}/{s['database']}"
            last_pull = float(stamp.get(key, 0) or 0)
            import logx_http as http

            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, data, updated_at, deleted_at FROM {TABLE} "
                    f"WHERE updated_at > %s OR deleted_at > %s",
                    (last_pull, last_pull))
                rows = cur.fetchall()

            max_ts = last_pull
            deleted_rows = [r for r in rows if r[3] is not None]
            added_rows = [r for r in rows if r[3] is None]

            # Suppressions distantes d'abord (même ordre que logx_cloudsync :
            # une correction ET une suppression du même id dans le même cycle
            # doit gagner par la suppression, la plus sûre des deux).
            # Appariement par (id, clé call+band+mode+date+heure) — jamais par
            # id seul (même patron que logx_cloudsync._sync_now_locked /
            # remote_pairs) : l'id est Date.now() côté client SANS coordination
            # inter-poste (voir logx_storage.reserve_qso_id_locked, unicité
            # locale seulement), donc deux postes différents peuvent produire
            # le même id à la même milliseconde pour deux QSO distincts — une
            # suppression appliquée par id seul supprimerait alors à tort le
            # QSO LOCAL d'un poste qui n'a rien à voir. Une ligne dont le JSON
            # est corrompu/illisible ne supprime rien (cohérent avec le
            # traitement déjà tolérant des added_rows corrompues plus bas).
            if deleted_rows:
                remote_deleted_pairs = set()
                for r in deleted_rows:
                    try:
                        remote_deleted_pairs.add((int(r[0]), _qso_key(json.loads(r[1]))))
                    except Exception:
                        continue
                removed = []
                with http.log_lock:
                    keep = []
                    for q in http.shared_log:
                        if (q.get('id'), _qso_key(q)) in remote_deleted_pairs:
                            removed.append(q)
                        else:
                            keep.append(q)
                    if removed:
                        http.shared_log[:] = keep
                        storage.bump_log_version()
                        for q in removed:
                            storage.mark_qso_deleted(q.get('id'))
                if removed:
                    removed_count = len(removed)
                    # Suppressions venues de la base partagée : destruction
                    # voulue, donc consentement explicite (voir logx_storage).
                    http.save_log_to_disk(effacement_autorise=True)
                    for q in removed:
                        scan = q.get('qsl_scan')
                        if scan:
                            try:
                                import logx_qsl_scan as qslscan
                                qslscan.delete_scan(scan)
                            except Exception:
                                pass
                for r in deleted_rows:
                    max_ts = max(max_ts, float(r[2] or 0), float(r[3] or 0))

            if added_rows:
                with http.log_lock:
                    seen = {_qso_key(q) for q in http.shared_log}
                    local_ids = {q.get('id') for q in http.shared_log if q.get('id') is not None}
                for qid, raw, updated_at, _deleted_at in added_rows:
                    max_ts = max(max_ts, float(updated_at or 0))
                    qid = int(qid)
                    if qid in local_ids:
                        continue   # déjà présent localement (nous en sommes peut-être la source)
                    try:
                        q = json.loads(raw)
                    except Exception:
                        continue
                    k = _qso_key(q)
                    if k in seen:
                        continue
                    seen.add(k)
                    ok, _info = http.add_qso_to_log(dict(q), force=False)
                    if ok:
                        pulled += 1
                        local_ids.add(qid)

            stamp[key] = max_ts
            _save_stamp(stamp)

        # Occupation des bandes (canal MySQL, temps réel) : APRÈS le sync du log
        # (uniquement s'il a réussi), table SÉPARÉE, best-effort et ISOLÉE (jamais
        # d'exception vers le carnet). Même iid que les autres canaux
        # (cloudsync._instance_id) pour que LAN/Cloud/MySQL dédupliquent le poste.
        try:
            import logx_cloudsync as _cs
            import logx_occupancy as _occ
            _iid = _cs._instance_id()
            _ensure_occ_schema(conn)
            _publier_occupation_mysql(conn, _iid, _occ._mon_statut[0])
            if s['mode'] == 'full':
                _lire_occupation_mysql(conn, _iid)
        except Exception:
            pass

        _stamp_status(s['host'], s['database'], pushed, pulled)
        return {'ok': True, 'mode': s['mode'], 'pushed': pushed, 'pulled': pulled,
                'removed': removed_count}
    except Exception as e:
        return {'ok': False, 'error': f"Erreur de synchronisation MySQL : {e}"}
    finally:
        conn.close()


def _stamp_status(host, database, pushed, pulled):
    try:
        data = {'last': utcnow().strftime('%Y-%m-%d %H:%M'),
                'host': host, 'database': database, 'pushed': pushed, 'pulled': pulled}
        with open(_STAMP_FILE + '.status', 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception:
        pass


def status(cfg=None):
    s = mysql_settings(cfg) if cfg is not None else {}
    last = {}
    try:
        if os.path.exists(_STAMP_FILE + '.status'):
            with open(_STAMP_FILE + '.status', encoding='utf-8') as f:
                last = json.load(f) or {}
    except Exception:
        pass
    last_error = None
    if (_last_error['ts'] and s.get('enabled')
            and s.get('host') == _last_error.get('host')
            and s.get('database') == _last_error.get('database')):
        last_error = {'msg': _last_error['msg'], 'age_s': int(time.time() - _last_error['ts'])}
    return {'enabled': bool(s.get('enabled')), 'mode': s.get('mode', 'off'),
            'host': s.get('host', ''), 'database': s.get('database', ''),
            'last': last, 'last_error': last_error, 'has_pymysql': HAS_PYMYSQL}
