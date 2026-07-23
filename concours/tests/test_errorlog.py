# -*- coding: utf-8 -*-
"""Tests de logx_errorlog.py — journal d'erreurs local (sys.excepthook +
threading.excepthook) qui alimente GET /debug/errors (voir
tests/test_errors_http.py pour le pendant HTTP). Sans ces tests, une
régression silencieuse (ex. tampon jamais borné, ou input() bloquant même
hors mode figé) ne serait remarquée qu'en usage réel — bien trop tard pour
un mécanisme dont le seul but est de survivre à un crash."""
import builtins
import os
import sys
import threading
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_errorlog as errlog


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Redirige le fichier de journal vers tmp_path et vide le tampon mémoire
    avant/après chaque test — sinon les tests polluent errors.log réel du
    poste ET se contaminent entre eux via le tampon module-level."""
    monkeypatch.setattr(errlog, 'user_data_dir', lambda: str(tmp_path))
    monkeypatch.setattr(errlog, '_errors', [])
    yield
    monkeypatch.setattr(errlog, '_errors', [])


def _make_exc(msg='boom'):
    try:
        raise ValueError(msg)
    except ValueError:
        return sys.exc_info()


# ─── _record / get_recent_errors ─────────────────────────────────────────────

def test_record_alimente_le_tampon_et_le_fichier(tmp_path):
    exc_type, exc_value, exc_tb = _make_exc('panne réseau')
    errlog._record(exc_type, exc_value, exc_tb, 'MainThread')

    errors = errlog.get_recent_errors()
    assert len(errors) == 1
    assert errors[0]['type'] == 'ValueError'
    assert errors[0]['message'] == 'panne réseau'
    assert errors[0]['thread'] == 'MainThread'
    assert 'Traceback' in errors[0]['traceback']

    assert os.path.exists(errlog.log_path())
    content = open(errlog.log_path(), encoding='utf-8').read()
    assert 'panne réseau' in content


def test_ecriture_disque_protegee_par_le_meme_verrou_que_le_tampon(monkeypatch):
    """Reproduction concrète du problème [MEDIUM] de la revue du commit
    a1bc360 : le `with _lock:` d'origine n'enveloppait que l'append au
    tampon mémoire, PAS _rotate_if_large()+l'écriture disque — deux threads
    en exception simultanée pouvaient donc entrelacer leurs écritures dans
    errors.log (ou l'un tronquer le fichier pendant que l'autre y écrit).
    On vérifie ici que _lock est bien tenu à CHAQUE ouverture du fichier de
    journal déclenchée par _record() (lecture de rotation, réécriture
    tronquée, et ajout final) — sans le fix, ce test observe `False`."""
    monkeypatch.setattr(errlog, '_MAX_LOG_BYTES', 50)
    target = errlog.log_path()
    # Fichier déjà gros : force _rotate_if_large() à réellement lire+réécrire
    # (pas seulement à faire un os.path.getsize() qui échoue sur fichier absent).
    with open(target, 'w', encoding='utf-8') as f:
        f.write('X' * 500)

    lock_held_at_open = []
    real_open = builtins.open

    def _spy_open(file, *args, **kwargs):
        if str(file) == target:
            lock_held_at_open.append(errlog._lock.locked())
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', _spy_open)

    exc_type, exc_value, exc_tb = _make_exc('concurrence')
    errlog._record(exc_type, exc_value, exc_tb, 'MainThread')

    # 3 ouvertures attendues : lecture pour rotation, réécriture tronquée,
    # ajout de la nouvelle entrée — TOUTES doivent se produire verrou tenu.
    assert len(lock_held_at_open) == 3, lock_held_at_open
    assert all(lock_held_at_open), (
        "une opération disque a eu lieu HORS du verrou _lock — voir "
        "_record() dans logx_errorlog.py")


def test_get_recent_errors_renvoie_une_copie_pas_la_liste_interne():
    exc_type, exc_value, exc_tb = _make_exc()
    errlog._record(exc_type, exc_value, exc_tb, 'MainThread')
    errors = errlog.get_recent_errors()
    errors.append({'fake': True})
    assert len(errlog.get_recent_errors()) == 1  # mutation externe sans effet


def test_tampon_borne_a_max_errors():
    for i in range(errlog.MAX_ERRORS + 10):
        exc_type, exc_value, exc_tb = _make_exc(f'erreur {i}')
        errlog._record(exc_type, exc_value, exc_tb, 'MainThread')
    errors = errlog.get_recent_errors()
    assert len(errors) == errlog.MAX_ERRORS
    # Les plus ANCIENNES sont supprimées en premier : la dernière entrée du
    # tampon doit être la toute dernière erreur enregistrée.
    assert errors[-1]['message'] == f'erreur {errlog.MAX_ERRORS + 9}'


def test_record_ne_leve_jamais_meme_si_lecriture_disque_echoue(monkeypatch):
    """Un dossier de données inaccessible ne doit pas faire disparaître
    l'erreur d'origine derrière une exception du journal lui-même."""
    monkeypatch.setattr(errlog, 'log_path', lambda: '/chemin/inexistant/errors.log')
    exc_type, exc_value, exc_tb = _make_exc()
    entry = errlog._record(exc_type, exc_value, exc_tb, 'MainThread')  # ne doit pas lever
    assert entry['message'] == 'boom'
    assert len(errlog.get_recent_errors()) == 1


# ─── _excepthook (thread principal) ──────────────────────────────────────────

def test_excepthook_ignore_keyboardinterrupt(monkeypatch):
    called = {'n': 0}
    monkeypatch.setattr(sys, '__excepthook__', lambda *a: called.__setitem__('n', called['n'] + 1))
    try:
        raise KeyboardInterrupt()
    except KeyboardInterrupt:
        exc_type, exc_value, exc_tb = sys.exc_info()
    errlog._excepthook(exc_type, exc_value, exc_tb)
    assert called['n'] == 1          # affichage stderr habituel conservé
    assert errlog.get_recent_errors() == []   # mais rien enregistré


def test_excepthook_enregistre_et_naffiche_pas_input_hors_mode_fige(monkeypatch):
    monkeypatch.setattr(errlog, 'is_frozen', lambda: False)
    monkeypatch.setattr(sys, '__excepthook__', lambda *a: None)
    called = {'n': 0}
    monkeypatch.setattr(builtins, 'input', lambda *a, **k: called.__setitem__('n', called['n'] + 1))
    exc_type, exc_value, exc_tb = _make_exc('crash dev')
    errlog._excepthook(exc_type, exc_value, exc_tb)
    assert len(errlog.get_recent_errors()) == 1
    assert called['n'] == 0   # pas de blocage en mode développeur


def test_excepthook_attend_une_touche_en_mode_fige(monkeypatch):
    """C'est ce qui garde la fenêtre de LogXAI.exe ouverte après un crash
    fatal : sans ça, Windows referme la console avant que le testeur ait pu
    lire quoi que ce soit."""
    monkeypatch.setattr(errlog, 'is_frozen', lambda: True)
    monkeypatch.setattr(sys, '__excepthook__', lambda *a: None)
    called = {'n': 0}
    monkeypatch.setattr(builtins, 'input', lambda *a, **k: called.__setitem__('n', called['n'] + 1))
    exc_type, exc_value, exc_tb = _make_exc('crash fige')
    errlog._excepthook(exc_type, exc_value, exc_tb)
    assert called['n'] == 1


# ─── _thread_excepthook (threads de fond) ────────────────────────────────────

def _fake_thread_args(exc_type, exc_value, exc_tb, thread_name='WorkerThread'):
    fake_thread = threading.Thread(name=thread_name)
    return types.SimpleNamespace(exc_type=exc_type, exc_value=exc_value,
                                  exc_traceback=exc_tb, thread=fake_thread)


def test_thread_excepthook_enregistre_avec_le_nom_du_thread(monkeypatch):
    monkeypatch.setattr(threading, '__excepthook__', lambda a: None)
    exc_type, exc_value, exc_tb = _make_exc('thread mort')
    args = _fake_thread_args(exc_type, exc_value, exc_tb, 'ScoreboardLoop')
    errlog._thread_excepthook(args)
    errors = errlog.get_recent_errors()
    assert len(errors) == 1
    assert errors[0]['thread'] == 'ScoreboardLoop'
    assert errors[0]['message'] == 'thread mort'


def test_thread_excepthook_ignore_systemexit(monkeypatch):
    monkeypatch.setattr(threading, '__excepthook__', lambda a: None)
    try:
        raise SystemExit(0)
    except SystemExit:
        exc_type, exc_value, exc_tb = sys.exc_info()
    args = _fake_thread_args(exc_type, exc_value, exc_tb)
    errlog._thread_excepthook(args)
    assert errlog.get_recent_errors() == []


# ─── _rotate_if_large ─────────────────────────────────────────────────────────

def test_rotate_if_large_tronque_les_gros_fichiers(tmp_path, monkeypatch):
    monkeypatch.setattr(errlog, '_MAX_LOG_BYTES', 100)
    path = tmp_path / 'errors.log'
    path.write_text('X' * 500 + 'FIN_DU_FICHIER', encoding='utf-8')
    errlog._rotate_if_large(str(path))
    content = path.read_text(encoding='utf-8')
    assert len(content) < 500
    assert content.endswith('FIN_DU_FICHIER')   # la fin (plus récente) est conservée


def test_rotate_if_large_ne_touche_pas_un_petit_fichier(tmp_path, monkeypatch):
    monkeypatch.setattr(errlog, '_MAX_LOG_BYTES', 100)
    path = tmp_path / 'errors.log'
    original = 'petit contenu'
    path.write_text(original, encoding='utf-8')
    errlog._rotate_if_large(str(path))
    assert path.read_text(encoding='utf-8') == original


# ─── install() ────────────────────────────────────────────────────────────────

def test_install_pose_les_deux_hooks(monkeypatch):
    # Restaure les hooks d'origine après le test — install() mute un état
    # global du process, une fuite ici perturberait tout le reste de la suite.
    orig_sys_hook = sys.excepthook
    orig_thread_hook = threading.excepthook
    try:
        errlog.install()
        assert sys.excepthook is errlog._excepthook
        assert threading.excepthook is errlog._thread_excepthook
    finally:
        sys.excepthook = orig_sys_hook
        threading.excepthook = orig_thread_hook
