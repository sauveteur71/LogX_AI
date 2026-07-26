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


def _strip_stale_delta_versions():
    """Purge le marqueur '_v' des QSO fraîchement rechargés du disque.

    '_v' est posé par stamp_qso_version() directement sur le dict du QSO ;
    n'étant pas dans _CORE, il part dans la colonne extra de logx.db et dans
    shared_log.json à chaque save_log_to_disk(), puis est restauré tel quel au
    chargement. Or log_version repart de 0 à chaque démarrage (voir plus
    haut) : un '_v' hérité d'une session précédente est donc quasi toujours
    très SUPÉRIEUR à la version courante, et le filtre delta de /log/list
    (q.get('_v', 0) > since) ré-inclurait ces QSO dans CHAQUE réponse delta
    tant que log_version ne les a pas rattrapés — la synchro différentielle
    redeviendrait une retransmission quasi complète à chaque mutation,
    exactement ce qu'elle devait éliminer. SERVER_BOOT_ID ne protège pas de
    ça : il n'invalide que les curseurs CLIENT d'avant redémarrage, pas les
    '_v' périmés côté serveur. D'où cette purge systématique au chargement
    (qui assainit aussi les bases déjà polluées par les versions antérieures)."""
    for q in shared_log:
        if isinstance(q, dict):
            q.pop('_v', None)


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


def contest_actif(cfg):
    """Un concours est-il RÉELLEMENT sélectionné ? Source unique de vérité
    pour l'affichage des points/scores dans toutes les pages.

    Sans concours (mode 'simple', ou mode concours sans concours choisi), le
    moteur de scoring retombe sur le préréglage 'km' de REF_RPH — il produit
    donc des « points » (1 pt/km) parfaitement calculés mais qui ne veulent
    rien dire : aucun règlement ne les compte. Les afficher fait croire à un
    score. On s'appuie sur cfg_scope_id() plutôt que de retester
    usage_mode/contest page par page : c'est exactement la même question, et
    la dupliquer à la main est ce qui avait produit la dérive de
    CONTEST_FILTERS."""
    return bool(cfg_scope_id(cfg))


# ─── N° DE SÉRIE PAR BANDE (allocation serveur) ──────────────────────────────
# Avant : chaque poste incrémentait son propre compteur CÔTÉ CLIENT
# (logx_logbook.js:nextSerial, et un simple champ texte libre côté mobile) —
# deux postes qui loguent au même instant sur la même bande pouvaient émettre
# le MÊME numéro, aucune coordination réelle entre eux. Le serveur est
# désormais seul à distribuer un numéro (voir /log/next_serial), sous
# log_lock : deux requêtes concurrentes ne peuvent jamais recevoir la même
# valeur. Haute-eau MÉMOIRE SEULE (jamais persistée) : au redémarrage, on
# repart de shared_log (rechargé depuis le disque, la vraie source de
# vérité) — jamais en retard ni en double par rapport à ce qui est déjà
# loggué, même sans avoir gardé trace du dernier numéro distribué.
# Clé = (portée concours, bande) et PAS la bande seule : shared_log est un log
# GLOBAL où cohabitent le log simple et tous les concours/années (voir la
# section PORTÉE CONCOURS ci-dessus) — un compteur par bande seule ferait
# démarrer le concours suivant au max de TOUT l'historique de la bande
# (ex. 801 au lieu de 001), y compris sans redémarrage entre deux concours.
_serial_high_water = {}   # (scope_id, bande normalisée) -> dernier n° distribué


def _serial_max_used_locked(band_norm, scope_id=''):
    """Plus grand num_sent déjà loggué pour cette bande DANS LA PORTÉE
    concours donnée (même règle que logx_http._scope_filtered : scope_id non
    vide -> seuls les QSO dont qso_scope_id() correspond comptent ; scope_id
    vide = mode simple/aucun concours -> tout le log compte, comportement
    historique). Sans ce filtre, un concours précédent resté dans shared_log
    (comportement nominal : /log/archive ne purge que sur clear=true) ou un
    import ADIF avec STX dans le log perso faisait démarrer le concours
    suivant au max historique de la bande au lieu de 1 — numéro d'échange
    faux transmis sur l'air, sans aucun recours opérateur (champ readOnly,
    allocation serveur). L'ancien compteur client (logx_logbook.js:nextSerial)
    comptait sur /log/list DÉJÀ filtré par portée : il était implicitement
    scopé, l'allocation serveur doit l'être explicitement. Appelant
    responsable de tenir log_lock (factorisé entre allocate_next_serial/
    peek_next_serial, qui doivent lire exactement le même état)."""
    max_used = 0
    for q in shared_log:
        if str(q.get('band', '')).strip() != band_norm:
            continue
        if scope_id and qso_scope_id(q) != scope_id:
            continue
        try:
            n = int(str(q.get('num_sent', '')).strip())
        except (ValueError, TypeError):
            continue
        if n > max_used:
            max_used = n
    return max_used


def allocate_next_serial(band, scope_id=''):
    """Alloue (réserve) le prochain n° de série pour cette bande, dans la
    portée concours `scope_id` (cfg_scope_id de la config courante — chaque
    concours/édition repart de 1, voir _serial_max_used_locked). Un trou dans
    la séquence (réservation jamais suivie d'un /log/add, ex. saisie
    abandonnée) est toléré — comme l'était déjà l'ancien compteur côté client
    (voir logx_logbook.js:updateSerialDisplay, "ni revenir en arrière, même
    s'il y a un trou dans la séquence")."""
    band_norm = str(band or '').strip()
    key = (str(scope_id or ''), band_norm)
    with log_lock:
        nxt = max(_serial_max_used_locked(band_norm, key[0]), _serial_high_water.get(key, 0)) + 1
        _serial_high_water[key] = nxt
        return nxt


def peek_next_serial(band, scope_id=''):
    """Donne le n° qui SERAIT distribué par le prochain allocate_next_serial()
    pour cette bande et cette portée concours, SANS consommer le compteur.
    Sert à un simple aperçu d'affichage (mobile : rafraîchi à chaque
    changement de bande, après chaque QSO et au chargement de la page — bien
    plus souvent qu'un QSO n'est réellement soumis). Sans ce mode, chaque
    rafraîchissement d'écran brûlait un vrai numéro de série même si
    l'opérateur n'envoyait jamais le QSO correspondant (voir
    logx_mobile.html:refreshSuggestedSerial)."""
    band_norm = str(band or '').strip()
    key = (str(scope_id or ''), band_norm)
    with log_lock:
        return max(_serial_max_used_locked(band_norm, key[0]), _serial_high_water.get(key, 0)) + 1


# Verrou dédié à calldb.json : écrit depuis plusieurs threads
# (lookups HamQTH, imports, mises à jour navigateur).
calldb_lock = threading.Lock()

# ─── QTC (WAE) ───────────────────────────────────────────────────────────────
# Trafic QTC échangé : chaque QTC transféré vaut 1 point au WAE, à l'émetteur
# ET au récepteur (score = (QSO + QTC) × mults). Max 10 QTC (cumulés, émis +
# reçus) entre les deux mêmes stations sur tout le concours.
#
# Chaque élément de qtc_log est une SÉRIE QTC (un envoi/une réception groupée,
# comme sur l'air : « QTC 3/7 » = 3e série de cette station, 7 QTC dedans) :
#   {id, call, count, contest, date, time,       -> champs historiques (voir
#                                                    qtc_total/qtc_count_for_call)
#    direction: 'sent'|'recv', band, mode, series_number,
#    entries: [{time, call, nr}, ...]}            -> détail réglementaire WAE
#                                                    (1 à 10 QSO rapportés)
# 'entries' est absent sur les séries créées avant cette fonctionnalité (simple
# comptage) : qtc_total/qtc_count_for_call ne lisent que 'count'/'call' et
# restent donc valables sur les deux formats. L'export Cabrillo (logx_export)
# ignore en revanche les séries sans 'entries' — impossible de reconstituer le
# détail heure/indicatif/n° exigé par le format WAE-QTC a posteriori.
qtc_log = []
qtc_lock = threading.Lock()
QTC_FILE = 'qtc_log.json'
_qtc_next_id = 1   # prochain id de série à distribuer (voir next_qtc_id)


def load_qtc_from_disk():
    global _qtc_next_id
    try:
        if os.path.exists(QTC_FILE):
            with open(QTC_FILE, encoding='utf-8') as f:
                qtc_log[:] = json.load(f)
            # Rétro-compatibilité : les séries enregistrées avant l'ajout de la
            # saisie détaillée n'ont pas d'id — leur en attribuer un pour que
            # /qtc/delete puisse les cibler comme les nouvelles séries.
            # PREMIER passage : calculer le max des id déjà PRÉSENTS dans tout
            # le fichier avant d'en distribuer de nouveaux. Sans ce pré-calcul,
            # backfiller une entrée sans id avec le compteur courant peut lui
            # attribuer le MÊME id qu'une entrée plus loin dans le fichier qui
            # en a déjà un (ex. [sans id, sans id, id=2, sans id] : la 2e
            # entrée recevrait l'id 2 en avançant le compteur au fil de l'eau,
            # entrant en collision avec l'id=2 déjà fixé de la 3e entrée).
            max_existing_id = 0
            for q in qtc_log:
                qid = q.get('id')
                if qid:
                    try:
                        max_existing_id = max(max_existing_id, int(qid))
                    except (TypeError, ValueError):
                        pass
            next_id = max_existing_id + 1
            for q in qtc_log:
                if not q.get('id'):
                    q['id'] = next_id
                    next_id += 1
            _qtc_next_id = next_id
            print(f"[QTC] {sum(q.get('count', 0) for q in qtc_log)} QTC charges")
    except Exception as e:
        print(f"[QTC] Chargement impossible : {e}")


def next_qtc_id():
    """Alloue un id unique de série QTC (sous verrou — plusieurs postes
    peuvent enregistrer une série au même instant)."""
    global _qtc_next_id
    with qtc_lock:
        i = _qtc_next_id
        _qtc_next_id += 1
        return i


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


# ─── PLANNING DE ROULEMENT DES OPÉRATEURS (écran mural) ──────────────────────
# Roulement horaire des opérateurs : qui est censé être au micro/clavier à
# quelle heure, affiché sur l'écran mural (logx_wall.*). Outil INFORMATIF —
# aucun verrou opérationnel, un opérateur peut toujours logguer hors de son
# créneau (voir /shifts/add : un opérateur non qualifié pour le mode demandé
# reçoit un avertissement, jamais un refus). Calqué sur le modèle QTC
# ci-dessus : liste globale + verrou dédié + save/load JSON atomique + id
# auto-incrémenté.
#
# Chaque créneau : {id, call, name, date (YYYYMMDD, optionnel — absent = jour
# UTC courant au moment de l'affichage ; explicite seulement si le planning
# couvre plusieurs jours d'un concours), start (HH:MM), end (HH:MM), mode
# (optionnel, 'ssb'/'cw'/'digi' — sert uniquement à détecter une
# qualification manquante, voir /shifts/add), note (texte libre optionnel)}.
operator_shifts = []
shifts_lock = threading.Lock()
SHIFTS_FILE = 'operator_shifts.json'
_shifts_next_id = 1   # prochain id de créneau à distribuer (voir next_shift_id)


def load_shifts_from_disk():
    global _shifts_next_id
    try:
        if os.path.exists(SHIFTS_FILE):
            with open(SHIFTS_FILE, encoding='utf-8') as f:
                operator_shifts[:] = json.load(f)
            # Même logique de backfill que load_qtc_from_disk() : calculer le
            # max des id déjà présents AVANT d'en distribuer de nouveaux, pour
            # ne jamais entrer en collision avec un id existant plus loin dans
            # le fichier.
            max_existing_id = 0
            for s in operator_shifts:
                sid = s.get('id')
                if sid:
                    try:
                        max_existing_id = max(max_existing_id, int(sid))
                    except (TypeError, ValueError):
                        pass
            next_id = max_existing_id + 1
            for s in operator_shifts:
                if not s.get('id'):
                    s['id'] = next_id
                    next_id += 1
            _shifts_next_id = next_id
            print(f"[SHIFTS] {len(operator_shifts)} creneaux charges")
    except Exception as e:
        print(f"[SHIFTS] Chargement impossible : {e}")


def next_shift_id():
    """Alloue un id unique de créneau (sous verrou — plusieurs postes peuvent
    ajouter un créneau au même instant)."""
    global _shifts_next_id
    with shifts_lock:
        i = _shifts_next_id
        _shifts_next_id += 1
        return i


def save_shifts_to_disk():
    try:
        with shifts_lock:
            data = list(operator_shifts)
        save_json_atomic(SHIFTS_FILE, data)
    except Exception as e:
        print(f"[SHIFTS] Erreur sauvegarde : {e}")


def shifts_sorted():
    """Planning trié par heure de début. Clé (date, start) plutôt que 'start'
    seul : un créneau à date explicite (planning multi-jours) ne doit jamais
    se mélanger avec ceux du jour implicite courant. Les créneaux sans date
    explicite (le cas courant, un seul jour) se trient alors simplement entre
    eux par heure de début."""
    with shifts_lock:
        snap = list(operator_shifts)
    return sorted(snap, key=lambda s: (str(s.get('date', '') or ''),
                                        str(s.get('start', '') or '')))


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
            _strip_stale_delta_versions()
            print(f"[LOG] {len(shared_log)} QSO charges depuis {DB_FILE}")
            return
        if os.path.exists('shared_log.json'):
            with open('shared_log.json', 'r', encoding='utf-8') as f:
                shared_log[:] = json.load(f)
            _strip_stale_delta_versions()
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
