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

SYNC_PREFIX = 'logx_cloudsync_'
_INSTANCE_ID_FILE = '.cloudsync_instance_id'
_STAMP_FILE = 'cloudsync_state.json'


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


def sync_now(cfg, shared_log):
    """Synchronise selon le mode configuré. Retourne
    {'ok', 'mode', 'pushed', 'pulled', 'sources'} ou {'ok': False, 'error'}."""
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
        # 'seen' est amorcé avec les clés du log local et grossit à chaque
        # QSO importé — un même QSO présent dans plusieurs fichiers distants
        # (ou déjà local) n'est ajouté qu'une fois.
        seen = {_qso_key(q) for q in local}
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


def status(cfg=None):
    s = cloudsync_settings(cfg) if cfg is not None else {}
    last = {}
    try:
        if os.path.exists(_STAMP_FILE):
            with open(_STAMP_FILE, encoding='utf-8') as f:
                last = json.load(f) or {}
    except Exception:
        pass
    other_sources = 0
    if s.get('folder') and os.path.isdir(s['folder']):
        pattern = os.path.join(s['folder'], SYNC_PREFIX + '*.json')
        my_path = os.path.join(s['folder'], s.get('my_file', ''))
        other_sources = sum(1 for p in glob.glob(pattern) if os.path.abspath(p) != os.path.abspath(my_path))
    return {'enabled': bool(s.get('enabled')), 'mode': s.get('mode', 'off'),
            'folder': s.get('folder', ''), 'last': last, 'other_installations': other_sources}
