# -*- coding: utf-8 -*-
"""Cloud Sync — synchronisation du carnet entre plusieurs installations via
un dossier DÉJÀ synchronisé (Synology Drive / Dropbox / OneDrive...), sans
service hébergé ni compte à créer : le « cloud » est l'outil de sync de
fichiers que l'opérateur utilise déjà. logx_backup.py y écrit déjà
des instantanés horodatés à sens unique (sauvegarde/désastre) — ce module
ajoute un VRAI mécanisme de sync bidirectionnelle, mergée, entre plusieurs
postes qui pointent vers le même dossier.

3 niveaux (modèle explicitement recommandé par l'analyse concurrentielle
comme gabarit simple à reprendre) :
  - full : lit ET écrit — chaque poste voit les QSO des autres.
  - push : écrit seulement — utile pour un poste isolé qui alimente le
    dossier partagé sans avoir besoin des QSO des autres (liaison
    intermittente, poste de secours).
  - off  : désactivé (comportement actuel du reste de l'appli, inchangé).

Conception anti-collision : CHAQUE installation écrit UNIQUEMENT SON PROPRE
fichier (logx_cloudsync_<indicatif>_<id installation>.json), jamais
celui d'une autre — élimine toute course lecture-fusion-écriture entre deux
postes qui synchroniseraient au même instant. La fusion se fait à la LECTURE
(un poste en mode 'full' lit tous les fichiers des AUTRES installations et
réutilise la dédup native de add_qso_to_log — jamais de doublon, jamais
d'écrasement).

Propagation des SUPPRESSIONS et protection des CORRECTIONS (tombstones) :
une fusion purement additive ressuscitait tout QSO supprimé localement dès
qu'un fichier d'un autre poste le contenait encore (résurrection silencieuse
toutes les ~3 min), et ré-importait en DOUBLON — avec collision d'id —
l'ancienne version d'un QSO corrigé via /log/update (la clé de fusion
call+band+mode+date+heure diffère alors que l'id est identique). Deux
mécanismes, tous deux confinés à ce module :
  - chaque installation écrit AUSSI son propre fichier de tombstones
    (logx_cloudtomb_<indicatif>_<id installation>.json : liste de
    {'id', 'key', 'ts'}) pour ses suppressions individuelles
    (logx_storage.deleted_qsos) ; au pull, un QSO distant dont l'id est
    tombstoné n'est jamais ré-importé, et un tombstone distant dont l'id ET
    la clé correspondent à un QSO local le supprime (la suppression se
    propage au lieu que le QSO ressuscite). La double condition id+clé évite
    qu'une collision d'id (deux postes créant un QSO à la même milliseconde)
    supprime un QSO légitime, et un QSO ré-ajouté volontairement après
    suppression reçoit un id neuf, donc n'est jamais bloqué.
  - un QSO distant portant l'id d'un QSO déjà présent localement est ignoré :
    c'est l'ancienne version d'une correction faite ici (/log/update remplace
    EN PLACE, même id) — la ré-importer recréerait le doublon et la collision
    d'id.
Le préfixe des fichiers de tombstones est distinct de SYNC_PREFIX : les
anciennes versions du programme (glob sur logx_cloudsync_*) ne les lisent
jamais, et ils ne comptent pas comme « autres installations » dans status().

Anti-REJEU (au-delà de l'anti-falsification de la signature HMAC) : signer
uniquement 'data' protège contre un tiers SANS le secret d'équipe qui
forgerait un contenu, mais pas contre le REJEU d'un fichier ANCIEN mais
légitimement signé — un tiers ayant seulement un accès en ÉCRITURE au dossier
partagé (pas le secret) peut restaurer une ancienne version déjà signée via
l'historique de versions du dossier cloud, une sauvegarde, ou une copie de
conflit Synology/Dropbox, et _verify_signed() la validerait sans broncher
puisque sig(data) reste vrai indéfiniment. Des QSO supprimés (tombstonés)
peuvent alors réapparaître silencieusement si le fichier rejoué est antérieur
à leur suppression et que les tombstones correspondants ont depuis été purgés
(_MAX_SYNC_TOMBSTONES). Parade à deux étages, tous deux dans ce module :
  - la signature couvre maintenant 'saved_at' EN PLUS de 'data' (voir _sign) :
    un rejeu ne peut plus se faire passer pour plus récent qu'il ne l'est
    sans le secret ;
  - un suivi LOCAL (jamais dans le dossier partagé, voir _SEEN_STATE_FILE)
    mémorise par fichier distant le plus grand 'saved_at' déjà vu, et rejette
    tout fichier dont l'horodatage recule (voir _check_replay).
"""
import glob
import hashlib
import hmac
import json
import os
import threading
import time
import concurrent.futures as _cf
from logx_utils import utcnow, safe_filename, qso_key

SYNC_PREFIX = 'logx_cloudsync_'
# Tombstones de suppression : préfixe VOLONTAIREMENT hors du motif
# SYNC_PREFIX + '*' — un poste resté sur une ancienne version ne lira jamais
# ces fichiers comme des listes de QSO, et status() ne les comptera pas comme
# des installations supplémentaires.
TOMB_PREFIX = 'logx_cloudtomb_'
# Même borne que logx_storage._MAX_DELETED_TOMBSTONES : les suppressions
# individuelles sont rares, la liste persistée doit rester petite.
_MAX_SYNC_TOMBSTONES = 2000
# Plafonds défensifs contre un fichier logx_cloudsync_*/logx_cloudtomb_* forgé
# ou anormal déposé par un tiers ayant accès en écriture au dossier partagé
# (voir docstring « authentification de fichier » plus haut) : une réponse
# légitime tient sur quelques centaines de QSO/tombstones, jamais des
# millions — mitigation de dégât indépendante de la signature HMAC ci-dessous
# (utile même contre un coéquipier légitime dont le poste est compromis et
# qui connaît le secret).
MAX_SYNC_QSOS_PER_FILE = 5000
MAX_SYNC_FILE_BYTES = 5_000_000
_INSTANCE_ID_FILE = '.cloudsync_instance_id'
_STAMP_FILE = 'cloudsync_state.json'
# Suivi anti-rejeu : fichier LOCAL (jamais dans le dossier cloud partagé —
# voir _check_replay) mémorisant, par nom de fichier distant déjà lu, le plus
# grand 'saved_at' rencontré.
_SEEN_STATE_FILE = 'cloudsync_seen.json'

# Dernier échec de synchro (mémoire process, jamais persisté sur disque —
# comme le disjoncteur callbook) : la boucle de fond _cloudsync_loop
# (logx_serveur.py) n'affichait cet échec qu'en console serveur (print),
# jamais côté client. Rempli/vidé uniquement quand Cloud Sync est ACTIVÉ
# (voir sync_now ci-dessous) : un appel avec mode='off' n'est pas une panne
# réseau, juste une fonctionnalité inutilisée — ne doit jamais déclencher
# l'indicateur de dégradation.
# 'folder'/'mode' mémorisent la config qui a PRODUIT l'échec : status()
# ne le réaffiche que si la config actuelle est identique. Sans ça, l'échec
# restait un état fantôme après désactivation (mode='off', jamais revisité
# ici) ou après correction du dossier (nouveau dossier valide mais pas encore
# resynchronisé) — la pastille rouge persistait alors qu'aucune tentative
# n'avait échoué avec la config actuelle.
_last_error = {'ts': 0, 'msg': '', 'folder': '', 'mode': ''}
# Jusqu'à 3 sync_now_blocking concurrents sont explicitement autorisés (voir
# _SYNC_EXECUTOR) : sans ce verrou, les 4 assignations ci-dessous n'étaient
# PAS atomiques entre elles — deux sync_now() concurrentes (un échec, un
# succès) pouvaient entrelacer leurs écritures et produire un _last_error
# incohérent (ex. 'msg' d'un échec avec 'folder'/'mode' d'un autre run).
_last_error_lock = threading.Lock()


def _safe(s):
    return safe_filename(s, 24)


def _canonical(data):
    """Sérialisation stable (clés triées, séparateurs compacts) : produit les
    mêmes octets des deux côtés du HMAC, quel que soit l'ordre d'origine."""
    return json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _sign(data, saved_at, secret):
    """Signature HMAC-SHA256 couvrant 'data' ET 'saved_at' — pas seulement
    'data' (voir le paragraphe anti-rejeu de la docstring du module) : un
    fichier dont la signature ne porte que sur 'data' resterait valide pour
    toujours, quel que soit son âge."""
    return hmac.new(secret.encode('utf-8'),
                     _canonical({'data': data, 'saved_at': saved_at}),
                     hashlib.sha256).hexdigest()


def _verify_signed(raw, secret):
    """Extrait (liste_de_données, saved_at) d'un contenu JSON {'data': [...],
    'saved_at': <epoch>, 'sig': '<hmac>'} ou d'une liste brute (rétro-compat,
    fichiers écrits avant l'ajout de la signature). Retourne (None, None) si
    le contenu doit être rejeté : avec `secret` configuré, un fichier non
    signé ou dont la signature ne correspond pas est REJETÉ (pas seulement
    toléré) — la taille seule ne protège pas contre un fichier forgé au nom
    d'une autre installation, seule la signature le fait. Un fichier signé
    par une version du programme antérieure à l'ajout de saved_at (signature
    ne couvrant que 'data') est logé dans le même sac : sa signature ne
    correspond plus, il est réécrit au push suivant du poste qui l'a produit
    dès qu'il aura mis à jour.

    saved_at est le second ingrédient anti-rejeu (voir docstring du module) :
    la signature seule protège contre la FALSIFICATION (forger un contenu
    sans connaître le secret) mais pas contre le REJEU d'un ancien fichier
    légitimement signé — sig(data seul) resterait valide indéfiniment. En
    couvrant aussi saved_at, la signature garantit qu'un rejeu ne peut pas se
    faire passer pour plus récent qu'il ne l'est ; c'est _check_replay
    (appelé par _read_qsos/_read_tombstones) qui exploite ce saved_at
    AUTHENTIFIÉ pour rejeter un fichier dont l'horodatage recule par rapport
    au dernier connu pour ce même fichier."""
    if isinstance(raw, dict) and 'data' in raw:
        data, sig = raw.get('data'), raw.get('sig', '')
        saved_at = raw.get('saved_at')
        if not isinstance(saved_at, (int, float)) or isinstance(saved_at, bool):
            saved_at = None
        if secret and (not sig or not hmac.compare_digest(_sign(data, saved_at, secret), sig)):
            return None, None
        return (data if isinstance(data, list) else None), saved_at
    if isinstance(raw, list):
        if secret:
            return None, None  # secret configuré mais fichier legacy non signé
        return raw, None
    return None, None


def _instance_id():
    """Identifiant persistant de CETTE installation physique (pas de
    l'indicatif — deux postes de la même expédition peuvent partager
    l'indicatif, le nom de fichier doit rester unique par machine)."""
    try:
        if os.path.exists(_INSTANCE_ID_FILE):
            with open(_INSTANCE_ID_FILE, encoding='utf-8') as f:
                iid = f.read().strip()
                if iid:
                    return iid
    except Exception:
        pass
    import uuid
    iid = uuid.uuid4().hex[:8]
    try:
        with open(_INSTANCE_ID_FILE, 'w', encoding='utf-8') as f:
            f.write(iid)
    except Exception:
        pass
    return iid


def cloudsync_settings(cfg):
    cfg = cfg or {}
    folder = (cfg.get('cloudsync_folder') or cfg.get('backup_folder') or '').strip()
    mode = (cfg.get('cloudsync_mode') or 'off').strip().lower()
    if mode not in ('full', 'push', 'off'):
        mode = 'off'
    call = cfg.get('callsign_contest') or cfg.get('callsign') or 'poste'
    base = f'{_safe(call)}_{_instance_id()}'
    # Secret d'équipe optionnel (CONFIG, jamais transmis via le dossier cloud
    # lui-même — communiqué hors-bande, comme un mot de passe d'équipe) : sans
    # lui, la sync reste NON authentifiée (rétro-compatible), seuls les
    # plafonds de taille/nombre s'appliquent.
    secret = (cfg.get('cloudsync_secret') or '').strip()
    return {'folder': folder, 'mode': mode, 'enabled': mode != 'off' and bool(folder),
            'my_file': f'{SYNC_PREFIX}{base}.json',
            'my_tomb': f'{TOMB_PREFIX}{base}.json',
            'secret': secret}


# ── Anti-rejeu : état LOCAL, jamais dans le dossier cloud partagé ──────────
# (sinon un tiers ayant l'accès en écriture au dossier partagé pourrait aussi
# rejouer/effacer CET état, et se retrouver in fine à contrôler ce qu'il est
# censé contrer). Même emplacement/esprit que _STAMP_FILE et
# _INSTANCE_ID_FILE ci-dessus : un chemin relatif au répertoire de travail du
# serveur, propre à CETTE machine, jamais synchronisé. Clé = nom de fichier
# distant (logx_cloudsync_<indicatif>_<iid>.json ou logx_cloudtomb_*.json) —
# ce nom encode déjà indicatif + id d'installation, donc identifie le poste
# exactement comme le fait _safe()/base ailleurs dans ce module. Valeur = plus
# grand 'saved_at' (epoch secondes) authentifié déjà lu pour ce fichier.
_seen_lock = threading.Lock()
_seen_saved_at = None  # chargé paresseusement depuis _SEEN_STATE_FILE


def _load_seen():
    global _seen_saved_at
    if _seen_saved_at is not None:
        return _seen_saved_at
    data = {}
    try:
        if os.path.exists(_SEEN_STATE_FILE):
            with open(_SEEN_STATE_FILE, encoding='utf-8') as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                data = {str(k): float(v) for k, v in raw.items()
                        if isinstance(v, (int, float)) and not isinstance(v, bool)}
    except Exception:
        data = {}
    _seen_saved_at = data
    return _seen_saved_at


def _save_seen():
    try:
        with open(_SEEN_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_seen_saved_at or {}, f)
    except Exception:
        pass  # état advisoire — une écriture ratée dégrade la protection,
              # jamais la sync elle-même (même tolérance que _stamp())


# Tolérance de dérive d'horloge distante (poste de DXpédition sans NTP — voir
# logx_update.py) ou de saved_at non authentifié (secret d'équipe non
# configuré, voir _verify_signed) : sans ça, UN SEUL saved_at anormalement
# futur devient le plafond mémorisé À VIE dans cloudsync_seen.json et rejette
# comme « rejeu » toutes les écritures légitimes suivantes de ce poste une
# fois son horloge corrigée.
_MAX_CLOCK_SKEW = 3600


def _check_replay(basename, saved_at):
    """True si `saved_at` (authentifié par la signature — voir
    _verify_signed) du fichier `basename` est ANTÉRIEUR au plus grand déjà vu
    pour ce même fichier : c'est un REJEU (voir le paragraphe anti-rejeu de la
    docstring du module) à rejeter. saved_at=None (fichier signé avant
    l'ajout de ce champ, ou secret non configuré — voir _verify_signed) :
    aucune protection authentifiée possible pour ce fichier, jamais considéré
    comme un rejeu. Un saved_at anormalement futur (> _MAX_CLOCK_SKEW) n'est
    jamais mémorisé comme nouveau plafond — voir _MAX_CLOCK_SKEW."""
    if saved_at is None:
        return False
    with _seen_lock:
        seen = _load_seen()
        last = seen.get(basename)
        if last is not None and saved_at < last:
            return True
        if saved_at <= time.time() + _MAX_CLOCK_SKEW and (last is None or saved_at > last):
            seen[basename] = saved_at
            _save_seen()
        return False


def _read_qsos(path, secret=None):
    """Contenu d'un fichier logx_cloudsync_*.json — [] si absent, illisible,
    trop volumineux, non authentifié quand `secret` est configuré (voir
    _verify_signed), ou REJOUÉ (voir _check_replay)."""
    try:
        if os.path.getsize(path) > MAX_SYNC_FILE_BYTES:
            return []
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        return []
    data, saved_at = _verify_signed(raw, secret)
    if not isinstance(data, list):
        return []
    if _check_replay(os.path.basename(path), saved_at):
        return []
    return data[:MAX_SYNC_QSOS_PER_FILE]


def _read_tombstones(path, secret=None):
    """Liste des tombstones [{'id', 'key', 'ts'}, ...] d'un fichier
    logx_cloudtomb_*.json — [] si absent/illisible/trop volumineux/non
    authentifié/rejoué (même tolérance et mêmes protections que _read_qsos :
    un fichier corrompu ne doit jamais faire échouer la sync, mais un fichier
    forgé OU rejoué au nom d'une autre installation doit être rejeté dès
    qu'un secret est configuré)."""
    try:
        if os.path.getsize(path) > MAX_SYNC_FILE_BYTES:
            return []
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        return []
    data, saved_at = _verify_signed(raw, secret)
    if not isinstance(data, list):
        return []
    if _check_replay(os.path.basename(path), saved_at):
        return []
    data = data[:MAX_SYNC_QSOS_PER_FILE]
    return [t for t in data if isinstance(t, dict) and t.get('id') is not None]


def _write_signed(path, data, secret):
    """Écrit `data` (liste de QSO ou de tombstones), signé HMAC-SHA256 si un
    secret d'équipe est configuré ; format legacy (liste brute) inchangé sinon
    — rétro-compatible avec les postes non encore mis à jour. Le fichier signé
    porte aussi 'saved_at' (horodatage epoch de CETTE écriture), couvert par
    la signature (voir _sign) : c'est le prérequis de l'anti-rejeu (voir
    docstring du module et _check_replay). saved_at n'est ajouté que dans le
    cas signé : sans secret, rien n'authentifie de toute façon un horodatage —
    un tiers pourrait le forger librement, l'ajouter serait un faux sentiment
    de protection."""
    from logx_storage import save_json_atomic
    if secret:
        saved_at = time.time()
        payload = {'data': data, 'saved_at': saved_at, 'sig': _sign(data, saved_at, secret)}
    else:
        payload = data
    save_json_atomic(path, payload, compact=True)


def _qso_key(q):
    return qso_key(q)


# Le dossier cible est choisi par l'utilisateur et peut être un point de montage
# géré par un client de sync tiers (OneDrive Files On-Demand, Synology Drive en
# mode lecteur virtuel, Dropbox Smart Sync) : si un fichier n'est pas hydraté
# localement, open()/os.makedirs()/os.replace() dessus déclenchent un
# téléchargement réseau TRANSPARENT côté client de sync, SANS AUCUN timeout
# Python applicable (ce n'est pas un socket) — l'appel peut rester bloqué des
# minutes, voire indéfiniment si le poste distant est éteint. Toute la
# synchronisation (lecture ET écriture) tourne donc dans un thread jetable dont
# on borne l'ATTENTE : au-delà de SYNC_TIMEOUT, l'appelant (thread de la requête
# HTTP POST /cloudsync/now, ou le thread de fond périodique) est débloqué et
# reçoit une erreur claire plutôt qu'un gel sans fin — le thread abandonné, lui,
# continue seul et se termine de son côté sans jamais affecter l'appelant.
SYNC_TIMEOUT = 12
_SYNC_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=3, thread_name_prefix='cloudsync')

# Deux synchronisations peuvent réellement se CHEVAUCHER : POST /cloudsync/now
# (bouton « synchroniser maintenant », logx_http.py) pendant un cycle de
# _cloudsync_loop (logx_serveur.py), ou un worker abandonné après SYNC_TIMEOUT
# (dossier « à la demande » lent — le cas exact visé par le timeout) qui
# continue seul pendant que le cycle suivant démarre (le stamp de fin n'ayant
# jamais été écrit, due=True à la minute suivante). _SYNC_EXECUTOR autorise
# jusqu'à 3 _sync_now_blocking simultanés : sans sérialisation, chaque worker
# amorçait son 'seen' AVANT les insertions de l'autre et les deux tiraient le
# même QSO distant — doublon PERSISTANT en usage_mode 'simple', où
# add_qso_to_log ne refuse pas les doublons (par conception), jamais résorbé
# aux cycles suivants. Accessoirement, deux pushs simultanés faisaient aussi
# échouer os.replace sur le même fichier d'instance (WinError 5 observé).
# Ce verrou n'est pris que DANS le worker : l'attente de l'appelant reste
# bornée par SYNC_TIMEOUT, un worker bloqué par un dossier cloud gelé ne gèle
# toujours aucune requête HTTP.
_sync_serial_lock = threading.Lock()


def sync_now(cfg, shared_log):
    """Synchronise selon le mode configuré. Retourne
    {'ok', 'mode', 'pushed', 'pulled', 'sources'} ou {'ok': False, 'error'}."""
    try:
        r = _SYNC_EXECUTOR.submit(_sync_now_blocking, cfg, shared_log).result(timeout=SYNC_TIMEOUT)
    except _cf.TimeoutError:
        r = {'ok': False, 'error': f"Dossier de synchronisation trop lent à répondre "
                f"(> {SYNC_TIMEOUT}s) — probablement un dossier cloud non téléchargé "
                "localement (mode « à la demande »). Voir le guide utilisateur, "
                "section Dépannage."}
    # Enregistré seulement si Cloud Sync est réellement activé : un appel
    # désactivé (r['error'] = "désactivé...") n'est pas une dégradation
    # réseau à signaler — voir _last_error ci-dessus.
    s = cloudsync_settings(cfg)
    if s.get('enabled'):
        with _last_error_lock:
            if r.get('ok'):
                _last_error['ts'] = 0
                _last_error['msg'] = ''
                _last_error['folder'] = ''
                _last_error['mode'] = ''
            else:
                _last_error['ts'] = time.time()
                _last_error['msg'] = r.get('error', '')
                _last_error['folder'] = s.get('folder', '')
                _last_error['mode'] = s.get('mode', '')
    return r


def _sync_now_blocking(cfg, shared_log):
    # Une seule synchronisation à la fois (voir _sync_serial_lock ci-dessus) —
    # sérialise aussi le worker « abandonné » par un timeout de sync_now, qui
    # détient le verrou jusqu'à sa vraie fin.
    with _sync_serial_lock:
        return _sync_now_locked(cfg, shared_log)


def _sync_now_locked(cfg, shared_log):
    s = cloudsync_settings(cfg)
    if not s['enabled']:
        return {'ok': False, 'error': "Cloud Sync désactivé ou dossier non configuré (CONFIG)"}
    try:
        os.makedirs(s['folder'], exist_ok=True)
    except Exception as e:
        return {'ok': False, 'error': f"Dossier inaccessible : {e}"}

    my_path = os.path.join(s['folder'], s['my_file'])
    tomb_path = os.path.join(s['folder'], s['my_tomb'])
    local = list(shared_log or [])
    secret = s.get('secret') or ''

    # Contenu du push PRÉCÉDENT, lu AVANT réécriture : c'est la seule trace
    # complète (id + clé call/band/mode/date/heure) d'un QSO supprimé
    # localement depuis le dernier cycle — le QSO n'est plus dans shared_log
    # et logx_storage.deleted_qsos n'en mémorise que l'id.
    prev = _read_qsos(my_path, secret)

    # ── PUSH : ce poste réécrit UNIQUEMENT son propre fichier, jamais celui
    # d'un autre — aucune concurrence possible entre deux postes qui
    # synchroniseraient au même instant. Signé HMAC si un secret d'équipe est
    # configuré (voir docstring du module et _write_signed).
    try:
        _write_signed(my_path, local, secret)
    except Exception as e:
        return {'ok': False, 'error': f"Écriture impossible : {e}"}

    # ── TOMBSTONES (voir docstring du module) : sans eux, un QSO supprimé ici
    # ressuscitait au pull suivant depuis le fichier d'un autre poste, et la
    # suppression devenait définitivement impossible tant que la sync tournait.
    # Le fichier de tombstones de CE poste est persistant (il survit aux
    # redémarrages, contrairement à logx_storage.deleted_qsos, mémoire de
    # process) et n'est écrit que par ce poste — même anti-collision que
    # my_file. Seules les suppressions INDIVIDUELLES (/log/delete →
    # mark_qso_deleted) produisent un tombstone : les purges en masse (reset,
    # archive, changement de portée) passent par mark_hard_reset et ne doivent
    # JAMAIS se propager comme autant de suppressions chez les autres postes.
    import logx_storage as storage
    tombs = _read_tombstones(tomb_path, secret)
    tombs_dirty = False
    own_tomb_ids = {t.get('id') for t in tombs}
    mem_deleted = {d.get('id') for d in list(storage.deleted_qsos)} - {None}
    if mem_deleted:
        local_ids_now = {q.get('id') for q in local}
        for q in prev:
            qid = q.get('id')
            if (qid is not None and qid in mem_deleted
                    and qid not in local_ids_now and qid not in own_tomb_ids):
                tombs.append({'id': qid, 'key': list(_qso_key(q)), 'ts': time.time()})
                own_tomb_ids.add(qid)
                tombs_dirty = True

    pulled = 0
    removed_count = 0
    sources = 0
    if s['mode'] == 'full':
        import logx_http as http
        # Tombstones écrits par les AUTRES postes : leurs suppressions doivent
        # s'appliquer ici aussi, sinon ce poste re-pousserait indéfiniment le
        # QSO supprimé là-bas (et le ferait ressusciter partout).
        remote_tombs = []
        for tpath in glob.glob(os.path.join(s['folder'], TOMB_PREFIX + '*.json')):
            if os.path.abspath(tpath) == os.path.abspath(tomb_path):
                continue
            remote_tombs.extend(_read_tombstones(tpath, secret))
        # Suppression locale UNIQUEMENT sur id ET clé identiques : deux postes
        # peuvent créer deux QSO différents à la même milliseconde (id =
        # int(time*1000)) — l'id seul supprimerait alors un QSO légitime.
        remote_pairs = {(t.get('id'), tuple(t.get('key') or ())) for t in remote_tombs}
        # Blocage de ré-import par id seul (jamais par clé seule : un QSO
        # ré-ajouté volontairement après suppression a un id NEUF et ne doit
        # pas être bloqué) — l'union couvre les trois mémoires : suppressions
        # de cette session (deleted_qsos), tombstones persistés de ce poste
        # (survivent au redémarrage), tombstones des autres postes.
        blocked_ids = (own_tomb_ids | {t.get('id') for t in remote_tombs}
                       | mem_deleted) - {None}

        # Déduplication explicite AVANT insertion : on ne dépend plus du
        # comportement doublon de add_qso_to_log (sauté en mode 'simple').
        # 'seen' grossit à chaque QSO importé — un même QSO présent dans
        # plusieurs fichiers distants (ou déjà local) n'est ajouté qu'une fois.
        # Amorcé depuis le log VIVANT (http.shared_log, celui-là même où
        # add_qso_to_log insère), PAS depuis le snapshot 'local' : les
        # appelants figent leur copie AVANT d'appeler sync_now (logx_http
        # /cloudsync/now, logx_serveur _cloudsync_loop), donc ce snapshot peut
        # précéder les insertions d'une synchronisation qui vient de se
        # terminer — s'y fier ré-insérerait ces QSO fraîchement tirés. Lecture
        # sous log_lock puis RELÂCHÉ avant les insertions (add_qso_to_log
        # reprend log_lock lui-même, non réentrant) : _sync_serial_lock
        # garantit qu'aucune autre sync ne s'intercale entre cette lecture et
        # nos insertions. L'application des tombstones distants se fait dans
        # le MÊME verrou que la suppression + bump + tombstone local, comme le
        # handler /log/delete (un lecteur /log/list concurrent ne doit jamais
        # voir le QSO absent sans tombstone posé).
        removed = []
        with http.log_lock:
            if remote_pairs:
                keep = []
                for q in http.shared_log:
                    if (q.get('id'), _qso_key(q)) in remote_pairs:
                        removed.append(q)
                    else:
                        keep.append(q)
                if removed:
                    http.shared_log[:] = keep
                    storage.bump_log_version()
                    for q in removed:
                        storage.mark_qso_deleted(q.get('id'))
            seen = {_qso_key(q) for q in http.shared_log}
            local_ids = {q.get('id') for q in http.shared_log if q.get('id') is not None}
        if removed:
            removed_count = len(removed)
            http.save_log_to_disk()
            # Même nettoyage du scan QSL attaché que /log/delete : cette
            # suppression propagée ne doit pas laisser de fichier orphelin.
            for q in removed:
                scan = q.get('qsl_scan')
                if scan:
                    try:
                        import logx_qsl_scan as qslscan
                        qslscan.delete_scan(scan)
                    except Exception:
                        pass

        pattern = os.path.join(s['folder'], SYNC_PREFIX + '*.json')
        for path in glob.glob(pattern):
            if os.path.abspath(path) == os.path.abspath(my_path):
                continue
            sources += 1
            for q in _read_qsos(path, secret):
                k = _qso_key(q)
                if k in seen:
                    continue
                qid = q.get('id')
                if qid is not None and qid in local_ids:
                    # Même id déjà présent localement avec un autre contenu :
                    # c'est l'ancienne version d'un QSO CORRIGÉ ici via
                    # /log/update (remplacement en place, id conservé) restée
                    # dans le fichier d'un autre poste — la ré-importer
                    # recréerait un doublon avec collision d'id à chaque cycle.
                    continue
                if qid is not None and qid in blocked_ids:
                    # QSO supprimé (ici ou ailleurs) : jamais ré-importé. Si le
                    # blocage ne vient que de la mémoire de session
                    # (deleted_qsos, perdue au redémarrage), la copie distante
                    # fournit la clé complète : on persiste le tombstone pour
                    # que la suppression se propage et survive au redémarrage.
                    if qid not in own_tomb_ids:
                        tombs.append({'id': qid, 'key': list(k), 'ts': time.time()})
                        own_tomb_ids.add(qid)
                        tombs_dirty = True
                    continue
                seen.add(k)
                ok, _info = http.add_qso_to_log(dict(q), force=False)
                if ok:
                    pulled += 1
                    if qid is not None:
                        local_ids.add(qid)

    if tombs_dirty:
        if len(tombs) > _MAX_SYNC_TOMBSTONES:
            tombs = tombs[-_MAX_SYNC_TOMBSTONES:]
        try:
            _write_signed(tomb_path, tombs, secret)
        except Exception:
            pass  # réessayé au prochain cycle, deleted_qsos couvre la session

    _stamp(s['folder'], len(local), pulled, sources)
    return {'ok': True, 'mode': s['mode'], 'pushed': len(local), 'pulled': pulled,
            'removed': removed_count, 'sources': sources}


def _stamp(folder, pushed, pulled, sources):
    try:
        data = {'last': utcnow().strftime('%Y-%m-%d %H:%M'),
                'folder': folder, 'pushed': pushed, 'pulled': pulled, 'sources': sources}
        with open(_STAMP_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception:
        pass


# status() est devenu un chemin CHAUD avec GET /data/network_status (pollé
# toutes les 20 s par la barre de statut de CHAQUE page ouverte,
# logx_statusbar.js) : son comptage des autres installations (os.path.isdir +
# glob sur le dossier de sync) est la même I/O non bornée que celle qui a valu
# SYNC_TIMEOUT à sync_now. Sur un partage SMB/NAS injoignable — le cas EXACT
# que la pastille est censée signaler — os.path.isdir() bloque ~21 s (timeout
# SMB Windows, mesuré) dans le thread de la requête HTTP, et se re-déclenche
# à chaque poll dès que le cache négatif SMB expire : threads serveur gelés en
# continu (ThreadingHTTPServer sans plafond) précisément quand l'indicateur
# serait utile. Attention : cloudsync_settings() replie folder sur
# backup_folder, donc cette I/O s'exécute MÊME avec cloudsync_mode='off' si un
# dossier de sauvegarde NAS est configuré. Protection en deux volets :
#   - attente COURTE (STATUS_SCAN_TIMEOUT, pas SYNC_TIMEOUT) : une pastille
#     peut être en retard de quelques secondes, pas geler une requête 21 s ;
#   - vol unique + cache mémoire : un seul scan en cours par dossier ; si le
#     scan dépasse la borne, on répond la dernière valeur COMPLÈTE connue (ou
#     0) au lieu d'empiler un nouveau thread bloqué à chaque poll.
STATUS_SCAN_TIMEOUT = 2
_SCAN_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix='cloudsync-scan')
_scan_lock = threading.Lock()
_scan_cache = {'key': None, 'count': 0}       # dernier comptage COMPLET connu
_scan_flight = {'key': None, 'future': None}  # scan actuellement en vol


def _count_other_installations(folder, my_file):
    """Comptage BLOQUANT des fichiers de sync écrits par d'autres postes —
    exécuté uniquement dans _SCAN_EXECUTOR, jamais dans le thread d'une
    requête HTTP (voir commentaire STATUS_SCAN_TIMEOUT ci-dessus)."""
    if not (folder and os.path.isdir(folder)):
        return 0
    pattern = os.path.join(folder, SYNC_PREFIX + '*.json')
    my_path = os.path.join(folder, my_file or '')
    return sum(1 for p in glob.glob(pattern) if os.path.abspath(p) != os.path.abspath(my_path))


def _memorise_scan(fut, key):
    """Un scan abandonné par timeout finit quand même son travail tout seul :
    sa valeur nourrit le cache pour les polls suivants."""
    try:
        c = fut.result()
    except Exception:
        return
    with _scan_lock:
        _scan_cache['key'] = key
        _scan_cache['count'] = c


def _other_installations_bounded(s):
    """Version à attente bornée de _count_other_installations pour status()."""
    folder = s.get('folder') or ''
    if not folder:
        return 0
    key = (folder, s.get('my_file', ''))
    submitted = False
    with _scan_lock:
        fut = _scan_flight['future']
        if fut is None or fut.done() or _scan_flight['key'] != key:
            fut = _SCAN_EXECUTOR.submit(_count_other_installations, folder, s.get('my_file', ''))
            _scan_flight['future'] = fut
            _scan_flight['key'] = key
            submitted = True
    if submitted:
        # Hors du verrou : si le futur est déjà terminé, le callback s'exécute
        # immédiatement dans CE thread — sous _scan_lock ce serait un deadlock
        # (Lock non réentrant, _memorise_scan le reprend).
        fut.add_done_callback(lambda f, key=key: _memorise_scan(f, key))
    try:
        return fut.result(timeout=STATUS_SCAN_TIMEOUT)
    except Exception:
        with _scan_lock:
            if _scan_cache['key'] == key:
                return _scan_cache['count']
        return 0


def status(cfg=None):
    s = cloudsync_settings(cfg) if cfg is not None else {}
    last = {}
    try:
        if os.path.exists(_STAMP_FILE):
            with open(_STAMP_FILE, encoding='utf-8') as f:
                last = json.load(f) or {}
    except Exception:
        pass
    # I/O disque sur le dossier de sync à attente BORNÉE (voir
    # STATUS_SCAN_TIMEOUT ci-dessus) : status() tourne dans le thread des
    # requêtes HTTP et ne doit jamais rester suspendu au timeout SMB d'un
    # NAS tombé, sous peine de geler les pages qui le pollent.
    other_sources = _other_installations_bounded(s)
    # last_error n'est réaffiché que si : Cloud Sync est actuellement activé
    # ET la config actuelle (dossier + mode) est EXACTEMENT celle qui a
    # produit cet échec. Toute désactivation (mode='off') ou tout changement
    # de dossier/mode depuis l'échec (ex. correction du problème) le masque
    # immédiatement, sans attendre le prochain cycle de _cloudsync_loop —
    # évite l'état fantôme (voir commentaire sur _last_error ci-dessus).
    last_error = None
    with _last_error_lock:
        if (_last_error['ts'] and s.get('enabled')
                and s.get('folder') == _last_error.get('folder')
                and s.get('mode') == _last_error.get('mode')):
            last_error = {'msg': _last_error['msg'], 'age_s': int(time.time() - _last_error['ts'])}
    return {'enabled': bool(s.get('enabled')), 'mode': s.get('mode', 'off'),
            'folder': s.get('folder', ''), 'last': last, 'other_installations': other_sources,
            'last_error': last_error}
