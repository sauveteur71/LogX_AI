# -*- coding: utf-8 -*-
"""Log partagé multi-opérateur : état en mémoire + persistance SQLite.

Architecture : shared_log (liste en mémoire) reste la source de vérité que
tous les modules consultent ; save_log_to_disk() la persiste dans logx.db
(table qso indexée indicatif/bande/mode, transactionnelle — zéro risque de
troncature) + un shared_log.json de secours lisible. L'écriture est
INCRÉMENTALE : seuls les QSO réellement ajoutés/corrigés/supprimés partent sur
le disque (voir la section PERSISTANCE INCRÉMENTALE plus bas).
Migration one-shot : au premier démarrage sans base, shared_log.json est
importé. /log/reset ARCHIVE les QSO (table qso_archive) au lieu de les
perdre : l'historique multi-concours survit aux remises à zéro."""

import json
import os
import sqlite3
import threading
import time
import uuid
from logx_utils import utcnow

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


# Bornes de l'entier signé 64 bits : au-delà, sqlite3 lève OverflowError
# (« Python int too large to convert to SQLite INTEGER ») au moment du bind.
_INT64_MIN, _INT64_MAX = -2 ** 63, 2 ** 63 - 1


def _sqlite_safe(value):
    """Rend `value` LIABLE par sqlite3, quoi qu'elle contienne.

    sqlite3 n'accepte que None / str / bytes / int 64 bits / float : tout le
    reste (liste, dict, entier hors 64 bits, objet) fait lever le bind. Or
    save_log_to_disk() écrit les 10 colonnes _CORE telles quelles, et RIEN sur
    le chemin d'écriture ne normalisait leur type — /log/add ne vérifie que la
    présence de 'call', /log/update ne vérifie rien, et le champ 'contest' des
    QSO fabriqués côté SERVEUR (logx_adifnet.qso_from_contactinfo,
    logx_wsjtx) est hérité tel quel de current_config, lui-même remplacé sans
    validation par /config/save. Un SEUL QSO ainsi malformé faisait échouer
    l'executemany, donc annuler la transaction ET sauter le shared_log.json de
    secours : la persistance restait gelée jusqu'au redémarrage alors que le
    client continuait de recevoir 200 {'ok': true} — tout ce qui était loggué
    ensuite était perdu à la coupure suivante (et archive_current_log(), qui
    passe par ici aussi, renvoyait 0 : un /log/reset effaçait alors le log sans
    l'avoir archivé). Dégrader une valeur aberrante en texte est toujours
    préférable à perdre le carnet."""
    if value is None or isinstance(value, (str, bytes, float, bool)):
        return value
    if isinstance(value, int):
        return value if _INT64_MIN <= value <= _INT64_MAX else str(value)
    if isinstance(value, (list, tuple, dict)):
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            pass
    return str(value)


def _row_from_qso(q):
    extra = {k: v for k, v in q.items() if k not in _CORE}
    # default=str sur extra pour la même raison : un objet non sérialisable
    # glissé dans un champ annexe ferait lever json.dumps ICI, donc gèlerait
    # l'écriture exactement comme un bind impossible.
    return (tuple(_sqlite_safe(q.get(k)) for k in _CORE)
            + (json.dumps(extra, ensure_ascii=False, default=str),))


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
# Bornée très large : un dict {id, v} pèse quelques dizaines d'octets, même
# 200000 tombstones restent négligeables (quelques Mo) sur une session de 15
# jours -- l'ancienne borne de 2000 pouvait être atteinte par des suppressions
# répétées et violait alors l'invariant "un id supprimé n'est jamais recyclé"
# documenté juste au-dessus.
_MAX_DELETED_TOMBSTONES = 200_000
hard_reset_version = 0             # un ?since= antérieur à cette version n'est plus fiable

# ─── ID DE QSO : ALLOCATEUR UNIQUE ───────────────────────────────────────────
# L'id est la CLÉ D'IDENTITÉ du QSO dans tout le programme, et aucun de ces
# chemins ne sait départager deux porteurs du même id :
#   /log/delete  garde `[q for q in shared_log if q['id'] != qso_id]` — effacer
#                UN QSO en efface silencieusement plusieurs ;
#   /log/update  remplace le PREMIER porteur trouvé — la correction écrase un
#                QSO qui n'a rien à voir et la cible réelle reste fausse ;
#   logx_cloudsync fusionne les logs des postes par id (local_ids/blocked_ids).
#
# Un int(time.time() * 1000) isolé NE SUFFIT PAS. L'import ADIF doit numéroter
# N QSO d'un coup : en partant de l'horloge il consommait N millisecondes, donc
# N/1000 SECONDES d'id FUTURS (17 000 QSO importés = 17 s pendant lesquelles
# tout QSO saisi recevait un id déjà porté par un QSO importé ; et deux imports
# à une seconde d'intervalle se recouvraient à ~90 %, collision GARANTIE et non
# probabiliste). D'où cet allocateur : le prochain id est toujours strictement
# supérieur à tous les id déjà connus — QSO en mémoire, tombstones de
# suppression (ne jamais recycler un id : logx_cloudsync bloque le ré-import
# par id) et ids déjà distribués. Même motif que next_qtc_id()/next_shift_id().
_qso_id_high_water = 0


def next_free_qso_id(used_ids, now_ms=None):
    """Premier id libre : strictement supérieur à tous les `used_ids` fournis
    et jamais inférieur à l'horodatage courant en millisecondes (les id restent
    croissants dans le temps et restent lisibles comme une date).

    Fonction PURE : c'est le noyau partagé avec logx_import.commit_import(),
    qui travaille sur un instantané du log sans connaître shared_log."""
    top = (int(time.time() * 1000) if now_ms is None else int(now_ms)) - 1
    for v in used_ids:
        try:
            iv = int(v)
        except (TypeError, ValueError):
            continue          # id absent ou illisible : ne contraint rien
        if iv > top:
            top = iv
    return top + 1


def _used_qso_ids(log):
    """Id déjà pris : ceux du log ET ceux sous tombstone (un id supprimé ne
    doit jamais être recyclé — logx_cloudsync bloque le ré-import par id, un
    QSO neuf qui hériterait d'un id enterré serait écarté à tort par les
    autres postes). Parcours direct, sans copie : appelé sous log_lock, donc
    aucune mutation concurrente possible."""
    used = set()
    for source in (log, deleted_qsos):
        for item in source:
            try:
                used.add(int(item.get('id')))
            except (TypeError, ValueError, AttributeError):
                continue
    return used


def allocate_qso_ids_locked(count=1, log=None, now_ms=None):
    """Alloue `count` id de QSO CONSÉCUTIFS et libres, et retourne la liste.

    À APPELER AVEC log_lock DÉJÀ TENU (ne le reprend pas : Lock non réentrant,
    cf. save_log_to_disk), et le verrou doit couvrir l'allocation ET l'insertion
    dans le log — sinon deux insertions concurrentes lisent le même maximum et
    reçoivent le même id. `log` est explicite (défaut shared_log) parce que
    logx_http en détient sa propre référence."""
    global _qso_id_high_water
    used = _used_qso_ids(shared_log if log is None else log)
    used.add(_qso_id_high_water)
    start = next_free_qso_id(used, now_ms)
    n = max(0, int(count))
    if n:
        _qso_id_high_water = start + n - 1
    return list(range(start, start + n))


def reserve_qso_id_locked(proposed=None, log=None, now_ms=None):
    """Id à donner à un QSO qui en propose déjà un (les pages client envoient
    un `id: Date.now()`, et logx_cloudsync réinsère les QSO d'un autre poste EN
    CONSERVANT leur id : c'est son identité de fusion). On garde `proposed`
    tant qu'il est réellement LIBRE ; sinon on en alloue un neuf plutôt que de
    laisser deux QSO partager une clé d'identité. Mêmes règles de verrou que
    allocate_qso_ids_locked()."""
    try:
        pid = int(proposed)
    except (TypeError, ValueError):
        pid = None
    if pid is not None and pid not in _used_qso_ids(shared_log if log is None else log):
        return pid
    return allocate_qso_ids_locked(1, log, now_ms)[0]


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
        # Ne devrait jamais se produire en usage normal ; si ça arrive, le
        # dire au lieu de recycler un id silencieusement.
        print(f"[LOG] ATTENTION : {len(deleted_qsos)} tombstones de "
              f"suppression -- des id supprimés redeviennent recyclables.")
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
        year = str(utcnow().year)
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
qtc_lock = threading.RLock()
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


# ─── PERSISTANCE INCRÉMENTALE ────────────────────────────────────────────────
# save_log_to_disk() est appelée UNE FOIS PAR QSO : /log/add (dans le thread de
# la requête, AVANT que la réponse HTTP ne parte), /log/update, /log/delete,
# /qsl_scan/upload, et une fois par QSO tiré par Cloud Sync (logx_cloudsync
# appelle add_qso_to_log en boucle). Elle faisait un DELETE FROM qso + la
# RÉINSERTION DE TOUT LE CARNET, puis réécrivait intégralement shared_log.json :
# le coût d'UN QSO était linéaire en taille du carnet, donc le coût cumulé
# QUADRATIQUE. Mesuré (POST /log/add réel, SSD local) :
#
#     carnet      0 QSO ->    10 ms
#     carnet 20 000 QSO ->   487 ms
#     carnet 40 000 QSO -> 1 013 ms   (shared_log.json = 14,7 Mo)
#     carnet 80 000 QSO -> 2 089 ms   (shared_log.json = 29,4 Mo)
#
# Exactement le motif de dérive lente redouté en expédition : parfaitement
# fluide au démarrage, 2 secondes de gel de l'interface par QSO au bout de dix
# jours de pile-up, sur un site où rien n'est réparable — et de l'ordre du
# téraoctet réellement écrit sur le support pour 80 000 QSO loggués. Un
# rattrapage Cloud Sync de 500 QSO sur un carnet de 20 000 mesurait 232 s et
# 4,55 Go écrits, pour 500 QSO récupérés.
#
# On tient donc un MIROIR de ce qui est réellement sur le disque, et on n'écrit
# que la différence. Le miroir ne vaut que pour LA base à laquelle il
# correspond : tout changement de dossier de travail, disparition du fichier ou
# erreur d'écriture le fait oublier, et la sauvegarde suivante réécrit tout.
_disk_path = None      # chemin ABSOLU de la base décrite par le miroir
_disk_ids = set()      # ids (tels que stockés) présents dans la table qso
_disk_version = None   # log_version dont l'état est déjà écrit ; None = inconnu
_disk_pending = 0      # QSO écrits en delta depuis la dernière réécriture complète

# Réécriture COMPLÈTE (base + shared_log.json) tous les len(log)//200 QSO
# touchés. Deux raisons, et une propriété :
#   - shared_log.json ne peut PAS être écrit en delta (c'est un tableau JSON
#     réécrit d'un bloc) ; c'est un secours LISIBLE, pas la source de vérité
#     (logx.db, transactionnelle, reste à jour au QSO près à chaque instant, et
#     logx_backup.run_backup écrit de toute façon son propre JSON depuis la
#     mémoire). Le rafraîchir périodiquement suffit ;
#   - filet de sécurité : si un futur chemin de mutation oubliait son
#     stamp_qso_version(), la réécriture complète répare l'écart au lieu de le
#     laisser s'installer.
# Propriété : l'intervalle étant proportionnel à la taille du carnet, le coût
# AMORTI par QSO reste constant au lieu de croître linéairement — le volume
# total écrit sur une expédition redevient linéaire (quelques Go) au lieu de
# quadratique (~1,8 To). Sous 200 QSO, comportement identique à l'ancien :
# chaque sauvegarde réécrit tout (c'est instantané à cette taille).
_RESYNC_DIVISOR = 200


def _forget_disk_state():
    """Le miroir ne décrit plus le disque : tout réécrire au prochain passage."""
    global _disk_path, _disk_ids, _disk_version, _disk_pending
    _disk_path, _disk_ids, _disk_version, _disk_pending = None, set(), None, 0


def _disk_key(qso):
    """Clé de ligne = l'id du QSO TEL QU'IL EST STOCKÉ (voir _sqlite_safe : une
    valeur aberrante est dégradée en texte), pour que le WHERE id=? d'un UPDATE
    ou d'un DELETE retombe exactement sur la valeur écrite."""
    return _sqlite_safe(qso.get('id'))


def _plan_ecriture(data, base_version):
    """(à_insérer, à_mettre_à_jour, ids_supprimés, ids_courants), ou None s'il
    faut réécrire tout le carnet. Appelant responsable de tenir _db_lock.

    UNE SEULE passe sur le carnet, à deux accès de dictionnaire par QSO : c'est
    tout ce qui reste de linéaire dans une sauvegarde, et ça doit le rester
    (c'est le chemin parcouru à chaque QSO d'un pile-up)."""
    if base_version is None:
        return None                     # état du disque inconnu
    ids_now, a_inserer, a_majour = set(), [], []
    for q in data:
        k = q.get('id')
        if type(k) is not int or not (_INT64_MIN <= k <= _INT64_MAX):
            # Cas rare (id absent, ou valeur que _sqlite_safe dégrade avant de
            # l'écrire) : on repasse par la clé exacte telle que stockée.
            k = _disk_key(q)
            if k is None:
                return None             # QSO sans id : aucune ligne à cibler
        ids_now.add(k)
        if k in _disk_ids:
            # Les QSO modifiés sont ceux estampillés depuis la dernière
            # écriture — le même marqueur '_v' que la synchro différentielle de
            # /log/list, posé par stamp_qso_version() sous log_lock à CHAQUE
            # mutation individuelle.
            if (q.get('_v') or 0) > base_version:
                a_majour.append((q, k))
        else:
            a_inserer.append(q)
    if len(ids_now) != len(data):
        return None                     # ids dupliqués : un UPDATE ... WHERE id=?
                                        # toucherait plusieurs QSO à la fois
    supprimes = _disk_ids - ids_now
    touches = len(a_inserer) + len(a_majour) + len(supprimes)
    if _disk_pending + touches >= max(1, len(data) // _RESYNC_DIVISOR):
        return None                     # résynchronisation complète amortie
    return a_inserer, a_majour, supprimes, ids_now


def _ecrire_tout(data, version_now):
    """Réécriture complète : base + shared_log.json de secours."""
    global _disk_path, _disk_ids, _disk_version, _disk_pending
    conn = _db()
    try:
        with conn:  # transaction : réécriture tout-ou-rien
            conn.execute('DELETE FROM qso')
            conn.executemany(
                f"INSERT INTO qso ({','.join(_CORE)}, extra) "
                f"VALUES ({','.join('?' * (len(_CORE) + 1))})",
                [_row_from_qso(q) for q in data])
    finally:
        conn.close()
    save_json_atomic('shared_log.json', data)
    _disk_path = os.path.abspath(DB_FILE)
    _disk_ids = {_disk_key(q) for q in data}
    _disk_version = version_now
    _disk_pending = 0


def _ecrire_delta(data, version_now, plan):
    """N'écrit QUE les QSO ajoutés/corrigés/supprimés (une transaction, comme
    la réécriture complète : tout-ou-rien)."""
    global _disk_ids, _disk_version, _disk_pending
    a_inserer, a_majour, supprimes, ids_now = plan
    conn = _db()
    try:
        with conn:
            if supprimes:
                conn.executemany('DELETE FROM qso WHERE id=?',
                                 [(k,) for k in supprimes])
            if a_majour:
                conn.executemany(
                    f"UPDATE qso SET {'=?, '.join(_CORE)}=?, extra=? WHERE id=?",
                    [_row_from_qso(q) + (k,) for q, k in a_majour])
            if a_inserer:
                conn.executemany(
                    f"INSERT INTO qso ({','.join(_CORE)}, extra) "
                    f"VALUES ({','.join('?' * (len(_CORE) + 1))})",
                    [_row_from_qso(q) for q in a_inserer])
    finally:
        conn.close()
    _disk_ids = ids_now
    _disk_version = version_now
    _disk_pending += len(a_inserer) + len(a_majour) + len(supprimes)


def save_log_to_disk():
    """Persiste le log : SQLite (transaction, primaire) + JSON de secours.

    Écriture INCRÉMENTALE (voir la section PERSISTANCE INCRÉMENTALE ci-dessus) :
    au retour, logx.db contient TOUJOURS l'intégralité du carnet — rien n'est
    différé, seul le travail inutile est supprimé."""
    if load_failed:
        # Le chargement au démarrage a échoué avec une base existante : écrire
        # maintenant écraserait l'historique par le log (quasi) vide en mémoire.
        print("[LOG] Sauvegarde BLOQUÉE : chargement initial en échec — "
              "redémarre le logiciel une fois le verrou sur la base levé.")
        return
    try:
        with log_lock:
            data = list(shared_log)  # copie sous verrou
            version_now = log_version
        with _db_lock:
            if _disk_path != os.path.abspath(DB_FILE) or not os.path.exists(DB_FILE):
                _forget_disk_state()   # autre base, ou base disparue sous nos pieds
            elif _disk_version is not None and version_now < _disk_version:
                # Instantané plus ancien que ce qui est déjà écrit : une autre
                # requête (ThreadingHTTPServer) a persisté entretemps un état
                # PLUS récent, qui contient forcément notre propre mutation.
                # Sans ce garde-fou, notre liste d'ids périmée ferait supprimer
                # de la base les QSO ajoutés par l'autre thread.
                return
            plan = _plan_ecriture(data, _disk_version)
            if plan is None:
                _ecrire_tout(data, version_now)
            else:
                _ecrire_delta(data, version_now, plan)
    except Exception as e:
        # État du disque devenu incertain : la prochaine sauvegarde réécrit tout
        # plutôt que d'empiler un delta sur une base dont on ne sait plus rien.
        # SOUS _db_lock (déjà relâché par le `with` pendant la remontée de
        # l'exception) : le miroir ne doit jamais être vidé pendant qu'un autre
        # thread est en train de calculer son delta contre lui.
        with _db_lock:
            _forget_disk_state()
        print(f"[LOG] Erreur sauvegarde : {e}")


def archive_current_log():
    """Copie les QSO courants dans qso_archive (appelé AVANT un reset) :
    une remise à zéro ne détruit plus jamais d'historique."""
    try:
        with log_lock:
            data = list(shared_log)
        if not data:
            return 0
        stamp = utcnow().isoformat()
        with _db_lock:
            conn = _db()
            try:
                with conn:
                    conn.executemany(
                        f"INSERT INTO qso_archive ({','.join(_CORE)}, extra, archived_at) "
                        f"VALUES ({','.join('?' * (len(_CORE) + 2))})",
                        [_row_from_qso(q) + (stamp,) for q in data])
            finally:
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
    global _disk_path, _disk_ids, _disk_version, _disk_pending
    try:
        _forget_disk_state()   # on ne sait rien du disque tant qu'on n'a pas lu
        if os.path.exists(DB_FILE):
            with _db_lock:
                conn = _db()
                rows = conn.execute(
                    f"SELECT {','.join(_CORE)}, extra FROM qso ORDER BY rowid_pk"
                ).fetchall()
                conn.close()
            shared_log[:] = [_qso_from_row(r) for r in rows]
            _strip_stale_delta_versions()
            # La mémoire vient d'être remplie DEPUIS la base : le miroir de
            # persistance incrémentale est exact, la première sauvegarde de la
            # session n'aura que le premier QSO à écrire (et non tout le carnet).
            _disk_path = os.path.abspath(DB_FILE)
            _disk_ids = {_disk_key(q) for q in shared_log}
            _disk_version = log_version
            _disk_pending = 0
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
        # Base OU sauvegarde JSON déjà présente sur disque mais illisible
        # (verrou transitoire antivirus / Synology Drive, JSON tronqué...) :
        # dans les DEUX cas un historique existe et n'a pas pu être lu --
        # on interdit toute réécriture destructive jusqu'au prochain démarrage
        # réussi (voir load_failed / save_log_to_disk), plutôt que de repartir
        # sur un shared_log vide qui écraserait cet historique.
        if os.path.exists(DB_FILE) or os.path.exists('shared_log.json'):
            global load_failed
            load_failed = True
            print(f"[LOG] ⚠ données présentes sur disque mais illisibles — "
                  f"persistance GELÉE pour protéger l'historique. Ferme les "
                  f"programmes qui verrouillent le fichier (antivirus, sync) "
                  f"puis redémarre.")
