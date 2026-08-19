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
import re
import shutil
import glob
from logx_utils import utcnow, safe_filename

KEEP = 20                 # nombre de sauvegardes conservées

# Nom d'un JEU de sauvegarde : logx_{indicatif}_{AAAAMMJJ-HHMMSS}. Seuls ces
# noms-là sont soumis à la rotation (voir _prune).
_BASE_RE = re.compile(r'^logx_.*_\d{8}-\d{6}$')


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


DOSSIER_DEFAUT = 'sauvegardes'


def dossier_par_defaut():
    """Où l'on sauvegarde quand CONFIG ne désigne aucun dossier.

    Sous-dossier du dossier de données (celui qui contient déjà `logx.db`),
    donc toujours accessible en écriture et emporté par la consigne du guide
    « sauvegarder = copier ce dossier »."""
    return os.path.abspath(DOSSIER_DEFAUT)


def backup_settings(cfg):
    """La sauvegarde tourne TOUJOURS, dossier configuré ou non.

    DÉFAUT RÉEL, le 19/08/2026 : F4GLD a perdu 9 871 QSO (2011-2026) et aucune
    sauvegarde n'existait, parce que `backup_folder` était vide — il l'est à
    l'installation, et le logiciel ne l'a jamais réclamé. Rendre l'utilisateur
    responsable d'un réglage qu'il ne sait pas devoir faire, c'est exactement
    la faute que le principe du dépôt interdit : le meilleur réglage est celui
    qu'on n'a pas à faire. On sauvegarde donc dès le premier lancement, et le
    champ CONFIG ne sert plus qu'à DÉPLACER les sauvegardes.

    🚨 Le repli est calculé ICI et n'est JAMAIS réécrit dans la configuration.
    C'est délibéré : `logx_cloudsync.cloudsync_settings()` replie son propre
    dossier sur `cfg['backup_folder']`, et le commentaire de
    `logx_cloudsync.py` (STATUS_SCAN_TIMEOUT) documente que ce repli déclenche
    des I/O de scan **même avec `cloudsync_mode='off'`**. Écrire le défaut dans
    la config réveillerait donc une synchro que personne n'a demandée. Le
    défaut doit rester une valeur RÉSOLUE, pas une valeur STOCKÉE.

    `par_defaut` dit lequel des deux cas s'applique, pour que l'interface
    puisse continuer à recommander un dossier EXTERNE : ce repli protège du
    sinistre qui s'est réellement produit (carnet vidé, dossier intact), pas
    de la perte du disque."""
    cfg = cfg or {}
    choisi = (cfg.get('backup_folder') or '').strip()
    return {
        'folder': choisi or dossier_par_defaut(),
        'enabled': True,
        'par_defaut': not choisi,
        'interval_min': int(cfg.get('backup_interval', 15) or 15),
    }


def run_backup(cfg, shared_log=None):
    """Écrit une sauvegarde horodatée dans backup_folder. Retourne
    {ok, folder, files, when} ou {ok: False, error}."""
    s = backup_settings(cfg)
    folder = s['folder']
    if not folder:
        # Injoignable en principe : backup_settings replie toujours sur
        # dossier_par_defaut(). Garde-fou conservé pour qu'un futur remaniement
        # du repli échoue bruyamment au lieu d'écrire à la racine.
        return {'ok': False, 'error': 'Aucun dossier de sauvegarde résolu (bug interne)'}
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        return {'ok': False, 'error': f'Dossier inaccessible : {e}'}

    now = utcnow()
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
    return safe_filename(s, 24)


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

    N'élague QUE les noms de jeux de sauvegarde (_BASE_RE), jamais tout
    'logx_*' : ce dossier est AUSSI, par défaut, le dossier Cloud Sync
    (cloudsync_settings replie cloudsync_folder sur backup_folder — « vide =
    même dossier que SAUVEGARDE » dans CONFIG). Il contient alors
    logx_cloudsync_{indicatif}_{id installation}.json et
    logx_cloudtomb_{indicatif}_{id installation}.json, qui matchent 'logx_*'
    mais se terminent par l'identifiant d'installation (uuid4().hex[:8]) et
    non par un horodatage : un id commençant par un chiffre bas triait AVANT
    tout horodatage « 2026… » et ces deux fichiers étaient détruits à chaque
    cycle dès qu'il y avait plus de KEEP jeux. Or le fichier de tombstones est
    la SEULE trace persistante des suppressions individuelles
    (logx_storage.deleted_qsos est en mémoire de process) : le supprimer fait
    RESSUSCITER les QSO supprimés au premier redémarrage, depuis le fichier
    d'un autre poste — précisément la panne que ce mécanisme existe pour
    empêcher. Même quand l'id survit au tri, ces fichiers consommaient 2 des
    KEEP emplacements de rétention (18 vraies sauvegardes au lieu de 20).
    """
    try:
        bases = sorted({b for b in (os.path.basename(p).rsplit('.', 1)[0]
                                    for p in glob.glob(
                                        os.path.join(folder, 'logx_*')))
                        if _BASE_RE.match(b)},
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
            'par_defaut': bool(s.get('par_defaut')),
            'interval_min': s.get('interval_min', 15), 'last': last,
            'backups_kept': count}
