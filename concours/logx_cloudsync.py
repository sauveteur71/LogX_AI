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
"""
import glob
import json
import os
import re
import threading
import time
import concurrent.futures as _cf

SYNC_PREFIX = 'logx_cloudsync_'
_INSTANCE_ID_FILE = '.cloudsync_instance_id'
_STAMP_FILE = 'cloudsync_state.json'

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


def _safe(s):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', str(s or ''))[:24]


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
    return {'folder': folder, 'mode': mode, 'enabled': mode != 'off' and bool(folder),
            'my_file': f'{SYNC_PREFIX}{_safe(call)}_{_instance_id()}.json'}


def _read_qsos(path):
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _qso_key(q):
    """Clé d'identité d'un QSO pour la déduplication de fusion : indicatif +
    bande + mode + date + heure. Indépendante du réglage usage_mode (la dédup
    de add_qso_to_log est désactivée en mode 'simple', on ne peut donc pas s'y
    fier ici sous peine de duplication géométrique à chaque cycle de sync)."""
    q = q or {}
    return (str(q.get('call', '')).upper().strip(),
            str(q.get('band', '')).strip(),
            str(q.get('mode', '')).upper().strip(),
            str(q.get('date', '')).strip(),
            str(q.get('time', '')).strip())


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
    local = list(shared_log or [])

    # ── PUSH : ce poste réécrit UNIQUEMENT son propre fichier, jamais celui
    # d'un autre — aucune concurrence possible entre deux postes qui
    # synchroniseraient au même instant.
    try:
        from logx_storage import save_json_atomic
        save_json_atomic(my_path, local, compact=True)
    except Exception as e:
        return {'ok': False, 'error': f"Écriture impossible : {e}"}

    pulled = 0
    sources = 0
    if s['mode'] == 'full':
        import logx_http as http
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
        # nos insertions.
        with http.log_lock:
            seen = {_qso_key(q) for q in http.shared_log}
        pattern = os.path.join(s['folder'], SYNC_PREFIX + '*.json')
        for path in glob.glob(pattern):
            if os.path.abspath(path) == os.path.abspath(my_path):
                continue
            sources += 1
            for q in _read_qsos(path):
                k = _qso_key(q)
                if k in seen:
                    continue
                seen.add(k)
                ok, _info = http.add_qso_to_log(dict(q), force=False)
                if ok:
                    pulled += 1

    _stamp(s['folder'], len(local), pulled, sources)
    return {'ok': True, 'mode': s['mode'], 'pushed': len(local), 'pulled': pulled, 'sources': sources}


def _stamp(folder, pushed, pulled, sources):
    try:
        import datetime
        data = {'last': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
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
    if (_last_error['ts'] and s.get('enabled')
            and s.get('folder') == _last_error.get('folder')
            and s.get('mode') == _last_error.get('mode')):
        last_error = {'msg': _last_error['msg'], 'age_s': int(time.time() - _last_error['ts'])}
    return {'enabled': bool(s.get('enabled')), 'mode': s.get('mode', 'off'),
            'folder': s.get('folder', ''), 'last': last, 'other_installations': other_sources,
            'last_error': last_error}
