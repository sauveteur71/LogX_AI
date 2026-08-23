# -*- coding: utf-8 -*-
"""Journal d'erreurs local : capture les exceptions non interceptées, aussi
bien dans le thread principal que dans les (nombreux) threads de fond de ce
projet — scoreboard/backup/cloudsync, écouteurs WSJT-X/ADIF-net, analyses IA
serveur, diagnostic réseau...

Sans ce module, l'exécutable PyInstaller (console=True, voir logx.spec) fait
juste flasher sa fenêtre puis se referme sur une exception non gérée dans le
thread principal — un testeur non technique n'a pas le temps de lire quoi que
ce soit. install() pose sys.excepthook (thread principal) et
threading.excepthook (threads secondaires, Python >= 3.8) pour que CHAQUE
exception non interceptée :
  - reste affichée sur stderr comme d'habitude (comportement par défaut
    conservé, on ne fait qu'ajouter, jamais remplacer silencieusement) ;
  - soit écrite dans errors.log, dans le dossier de données utilisateur
    (persiste après fermeture, contrairement à la console) ;
  - alimente un tampon mémoire des dernières erreurs, exposé par
    GET /debug/errors (voir logx_http.py) — consommé par le bouton
    "Signaler un problème" de la barre de statut (logx_statusbar.js).

En mode figé, une exception fatale du thread principal garde en plus la
fenêtre ouverte via input() : sans ça, Windows referme la console dès la fin
du process, avant que quiconque ait pu lire le message.
"""
import sys
import threading
import traceback
import datetime

from logx_bootstrap import user_data_dir, is_frozen

MAX_ERRORS = 50            # tampon mémoire ; le fichier disque n'a pas cette limite
_MAX_LOG_BYTES = 2_000_000  # au-delà, on retronque errors.log (évite une croissance infinie)

_lock = threading.Lock()
_errors = []  # dicts {ts, thread, type, message, traceback}, plus récent EN DERNIER


def log_path():
    """Chemin du fichier de journal, dans le dossier inscriptible de
    l'utilisateur (identique en dev et en exécutable figé — voir
    logx_bootstrap.user_data_dir, déjà utilisé ainsi par logx_update.py)."""
    import os
    return os.path.join(user_data_dir(), 'errors.log')


def _rotate_if_large(path):
    """Ne garde que la fin du fichier s'il devient trop gros — un journal qui
    grossit sans limite sur un poste laissé allumé des semaines n'est pas
    souhaitable, mais on privilégie la simplicité (pas de rotation par
    fichiers multiples, juste une troncature de la queue)."""
    import os
    try:
        if os.path.getsize(path) <= _MAX_LOG_BYTES:
            return
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            f.seek(max(0, os.path.getsize(path) - _MAX_LOG_BYTES // 2))
            tail = f.read()
        with open(path, 'w', encoding='utf-8') as f:
            f.write('(journal tronqué — entrées les plus anciennes supprimées)\n')
            f.write(tail)
    except Exception:
        pass  # la rotation ne doit jamais empêcher l'écriture de la nouvelle erreur


def _record(exc_type, exc_value, exc_tb, thread_name):
    """Ajoute une entrée au tampon mémoire ET au fichier disque. Ne lève
    jamais — un bug dans le journal d'erreurs lui-même ne doit pas empêcher le
    programme de continuer (ou pire, masquer l'erreur d'origine)."""
    # Construction DÉFENSIVE : une exception dont __str__ lève (args non
    # imprimables, objet en cours de finalisation à l'arrêt de l'interpréteur…)
    # ferait sinon PROPAGER _record, alors que le docstring promet une fonction
    # totale. traceback.format_exception appelle lui-même str(exc_value) — donc
    # peut lever aussi. Sans ça, _excepthook se referme sans rien afficher.
    try:
        tb_text = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    except Exception:
        tb_text = '(traceback illisible)'
    try:
        message = str(exc_value)
    except Exception:
        message = '(message illisible)'
    entry = {
        'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'thread': thread_name,
        'type': getattr(exc_type, '__name__', 'Exception') if exc_type else 'Exception',
        'message': message,
        'traceback': tb_text,
    }
    # Le verrou enveloppe AUSSI la rotation + l'écriture disque, pas seulement
    # le tampon mémoire : deux threads qui lèvent une exception au même
    # instant (scoreboard + backup, par ex.) écrivaient sinon dans errors.log
    # sans coordination — écritures entrelacées, ou pire, l'un tronque
    # (_rotate_if_large réécrit tout le fichier) pendant que l'autre y ajoute,
    # ce qui perd l'entrée en cours d'écriture.
    with _lock:
        _errors.append(entry)
        if len(_errors) > MAX_ERRORS:
            del _errors[:len(_errors) - MAX_ERRORS]
        try:
            path = log_path()
            _rotate_if_large(path)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f"\n=== {entry['ts']} — thread={thread_name} ===\n{tb_text}")
        except Exception:
            pass
    return entry


def get_recent_errors():
    """Copie des dernières erreurs (la plus récente en dernier), pour
    GET /debug/errors — jamais la liste interne directement (thread-safety)."""
    with _lock:
        return list(_errors)


def _excepthook(exc_type, exc_value, exc_tb):
    """sys.excepthook : thread principal uniquement. Un Ctrl+C (déjà géré
    proprement par le try/except KeyboardInterrupt de logx_serveur.py) ne
    doit pas polluer errors.log ni bloquer sur input()."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    _record(exc_type, exc_value, exc_tb, 'MainThread')
    sys.__excepthook__(exc_type, exc_value, exc_tb)  # conserve l'affichage stderr habituel
    if is_frozen():
        # Sans ce blocage, la fenêtre de LogXAI.exe se referme instantanément
        # (comportement Windows normal en fin de process) et le message
        # ci-dessus disparaît avant qu'un testeur ait pu le lire.
        try:
            input(f"\nLogX AI a rencontré une erreur fatale (détails ci-dessus et dans "
                  f"{log_path()}).\nAppuie sur Entrée pour fermer cette fenêtre... ")
        except Exception:
            pass


def _thread_excepthook(args):
    """threading.excepthook : threads secondaires. Ne bloque JAMAIS (le
    process continue de tourner normalement, seul ce thread meurt) — sert
    uniquement à ce que l'erreur ne disparaisse pas sans laisser de trace,
    ce qui arrivait avant : ces threads (scoreboard/backup/cloudsync/écouteurs
    WSJT-X et ADIF-net...) tournent en daemon=True, leur exception non
    interceptée n'était visible que quelques lignes en console, jamais
    persistée."""
    if args.exc_type is not None and issubclass(args.exc_type, SystemExit):
        return
    thread_name = args.thread.name if args.thread else '?'
    _record(args.exc_type, args.exc_value, args.exc_traceback, thread_name)
    threading.__excepthook__(args)  # conserve l'affichage stderr habituel


def install():
    """À appeler une seule fois, le plus tôt possible dans logx_serveur.py."""
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook
