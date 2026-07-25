# -*- coding: utf-8 -*-
"""Sauvegarde du carnet — copie horodatée vers un dossier (cloud/NAS).

En plus des archives par concours, ce module copie régulièrement le log
complet (logx.db + shared_log.json + un export ADIF ré-importable)
vers un dossier configurable — typiquement un dossier synchronisé
Synology Drive / Dropbox / OneDrive → sauvegarde « cloud » sans dépendre
d'un service en ligne ni d'identifiants.

Rétention : garde les N sauvegardes les plus récentes. Déterministe et
testable ; ne lève jamais d'exception (retourne un dict d'état).
"""
import json
import os
import shutil
import datetime
import glob

KEEP = 20                 # nombre de sauvegardes conservées


def _copy_atomic(src, dst):
    """Copie via un .tmp puis os.replace (même motif que save_json_atomic de
    logx_storage) : un arrêt en pleine copie — fermeture de l'appli (le thread
    backup est daemon), arrêt Windows — ne peut plus laisser un fichier
    TRONQUÉ sous un nom de sauvegarde légitime, qui deviendrait « la
    sauvegarde la plus récente » et repousserait un bon backup vers la
    limite de rétention KEEP."""
    tmp = dst + '.tmp'
    try:
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _write_atomic(dst, text, newline=None):
    """Écriture texte ATOMIQUE (.tmp + os.replace) — même raison que
    _copy_atomic : jamais de backup tronqué portant un nom légitime."""
    tmp = dst + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8', newline=newline) as f:
            f.write(text)
        os.replace(tmp, dst)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def backup_settings(cfg):
    cfg = cfg or {}
    return {
        'folder': (cfg.get('backup_folder') or '').strip(),
        'enabled': bool((cfg.get('backup_folder') or '').strip()),
        'interval_min': int(cfg.get('backup_interval', 15) or 15),
    }


def run_backup(cfg, shared_log=None):
    """Écrit une sauvegarde horodatée dans backup_folder. Retourne
    {ok, folder, files, when} ou {ok: False, error}."""
    s = backup_settings(cfg)
    folder = s['folder']
    if not folder:
        return {'ok': False, 'error': 'Aucun dossier de sauvegarde configuré (CONFIG)'}
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        return {'ok': False, 'error': f'Dossier inaccessible : {e}'}

    now = datetime.datetime.utcnow()
    stamp = now.strftime('%Y%m%d-%H%M%S')
    call = (cfg or {}).get('callsign_contest') or (cfg or {}).get('callsign') or 'LOG'
    base = f'logx_{_safe(call)}_{stamp}'
    written = []
    try:
        # 1) SQLite (source de vérité) si présent — copie SOUS _db_lock :
        # save_log_to_disk() (appelé par le thread HTTP à chaque /log/add)
        # réécrit la base par DELETE FROM qso + INSERT dans une transaction ;
        # une copie sans verrou tombant dans cette fenêtre capture le fichier
        # en plein milieu de transaction, SANS son journal de rollback — le
        # .db sauvegardé peut être corrompu ou vide de QSO, alors que c'est
        # LE fichier présenté comme source de vérité (et le seul compté par
        # status() dans backups_kept).
        if os.path.isfile('logx.db'):
            import logx_storage as storage
            dst = os.path.join(folder, base + '.db')
            with storage._db_lock:
                _copy_atomic('logx.db', dst)
            written.append(os.path.basename(dst))
        # 2) shared_log.json (lisible) ou depuis shared_log en mémoire
        if shared_log is not None:
            dst = os.path.join(folder, base + '.json')
            _write_atomic(dst, json.dumps(list(shared_log),
                                          ensure_ascii=False, indent=1))
            written.append(os.path.basename(dst))
        elif os.path.isfile('shared_log.json'):
            dst = os.path.join(folder, base + '.json')
            _copy_atomic('shared_log.json', dst)
            written.append(os.path.basename(dst))
        # 3) Export ADIF ré-importable partout
        try:
            import logx_export as export
            qsos = list(shared_log) if shared_log is not None else _load_json('shared_log.json')
            if qsos:
                adif = export.build_adif(qsos, cfg or {})
                dst = os.path.join(folder, base + '.adi')
                _write_atomic(dst, adif, newline='')
                written.append(os.path.basename(dst))
        except Exception:
            pass
    except Exception as e:
        return {'ok': False, 'error': f'Écriture impossible : {e}'}

    _prune(folder)
    _stamp(folder, now, written)
    return {'ok': True, 'folder': folder, 'files': written,
            'when': now.strftime('%Y-%m-%d %H:%M')}


def _safe(s):
    import re
    return re.sub(r'[^A-Za-z0-9_.-]', '_', str(s or ''))[:24]


def _load_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _prune(folder):
    """Ne garde que les KEEP jeux de sauvegarde les plus récents (par base).

    Tri par l'horodatage en fin de nom (logx_{indicatif}_{AAAAMMJJ-HHMMSS}),
    jamais par le nom complet : l'indicatif précède l'horodatage, et un tri
    lexicographique du nom entier n'est chronologique que si l'indicatif ne
    change jamais. Après un retour d'indicatif concours vers l'indicatif
    personnel (ex. TM5X -> F4GLD, qui trie avant), chaque sauvegarde neuve
    serait sinon détruite dès son écriture tant qu'il reste KEEP vieux jeux.
    """
    try:
        bases = sorted({os.path.basename(p).rsplit('.', 1)[0]
                        for p in glob.glob(os.path.join(folder, 'logx_*'))},
                       key=lambda b: (b.rsplit('_', 1)[-1], b))
        for base in bases[:-KEEP]:
            for p in glob.glob(os.path.join(folder, base + '.*')):
                try:
                    os.remove(p)
                except Exception:
                    pass
    except Exception:
        pass


_STAMP = 'backup_state.json'


def _stamp(folder, now, files):
    try:
        data = {'last': now.strftime('%Y-%m-%d %H:%M'), 'folder': folder,
                'files': files}
        _write_atomic(_STAMP, json.dumps(data))
    except Exception:
        pass


def status(cfg=None):
    s = backup_settings(cfg) if cfg is not None else {}
    last = {}
    try:
        if os.path.exists(_STAMP):
            with open(_STAMP, encoding='utf-8') as f:
                last = json.load(f) or {}
    except Exception:
        pass
    count = 0
    if s.get('folder') and os.path.isdir(s['folder']):
        count = len(glob.glob(os.path.join(s['folder'], 'logx_*.db')))
    return {'enabled': bool(s.get('enabled')), 'folder': s.get('folder', ''),
            'interval_min': s.get('interval_min', 15), 'last': last,
            'backups_kept': count}
