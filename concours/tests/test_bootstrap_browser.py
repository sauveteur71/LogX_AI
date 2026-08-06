# -*- coding: utf-8 -*-
"""Ouverture du navigateur en mode « application » (--app=, sans barre
d'adresse ni onglets) au démarrage — logx_bootstrap.open_browser_app_mode()
et _find_app_mode_browser(). subprocess.Popen/webbrowser.open sont
monkeypatchés : aucun vrai navigateur n'est lancé pendant les tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_bootstrap as boot


def test_open_browser_app_mode_lance_chrome_avec_les_bons_arguments(monkeypatch):
    appels = []
    monkeypatch.setattr(boot.subprocess, 'Popen', lambda args: appels.append(args))
    monkeypatch.setattr(boot.webbrowser, 'open', lambda url: appels.append(('webbrowser', url)))

    ok = boot.open_browser_app_mode('http://127.0.0.1:8080/logx_logbook.html',
                                     find_browser=lambda: r'C:\fake\chrome.exe')

    assert ok is True
    assert len(appels) == 1
    args = appels[0]
    assert args[0] == r'C:\fake\chrome.exe'
    assert '--start-maximized' in args
    assert '--app=http://127.0.0.1:8080/logx_logbook.html' in args


def test_open_browser_app_mode_replie_sur_webbrowser_si_aucun_navigateur_trouve(monkeypatch):
    appels = []
    monkeypatch.setattr(boot.subprocess, 'Popen', lambda args: appels.append(('popen', args)))
    monkeypatch.setattr(boot.webbrowser, 'open', lambda url: appels.append(('webbrowser', url)))

    ok = boot.open_browser_app_mode('http://127.0.0.1:8080/logx_logbook.html',
                                     find_browser=lambda: None)

    assert ok is False
    assert appels == [('webbrowser', 'http://127.0.0.1:8080/logx_logbook.html')]


def test_open_browser_app_mode_replie_sur_webbrowser_si_lancement_echoue(monkeypatch):
    """Exécutable trouvé mais illançable (permissions, binaire cassé...) —
    ne doit jamais empêcher l'ouverture du navigateur par un autre chemin."""
    appels = []

    def popen_qui_echoue(args):
        raise OSError('permission denied')
    monkeypatch.setattr(boot.subprocess, 'Popen', popen_qui_echoue)
    monkeypatch.setattr(boot.webbrowser, 'open', lambda url: appels.append(url))

    ok = boot.open_browser_app_mode('http://127.0.0.1:8080/logx_logbook.html',
                                     find_browser=lambda: '/fake/chrome')

    assert ok is False
    assert appels == ['http://127.0.0.1:8080/logx_logbook.html']


def test_open_browser_app_mode_sans_find_browser_utilise_la_detection_reelle(monkeypatch):
    """Sans find_browser explicite, la fonction retombe sur
    _find_app_mode_browser() — vérifié en le monkeypatchant au niveau module,
    pas en dépendant d'une vraie installation Chrome/Edge sur la machine CI."""
    appels = []
    monkeypatch.setattr(boot, '_find_app_mode_browser', lambda: '/detected/chrome')
    monkeypatch.setattr(boot.subprocess, 'Popen', lambda args: appels.append(args))
    monkeypatch.setattr(boot.webbrowser, 'open', lambda url: appels.append(('webbrowser', url)))

    boot.open_browser_app_mode('http://x')

    assert appels[0][0] == '/detected/chrome'


def test_find_app_mode_browser_via_which(monkeypatch):
    monkeypatch.setattr(boot.shutil, 'which',
                         lambda nom: r'C:\PATH\chrome.exe' if nom == 'chrome' else None)
    assert boot._find_app_mode_browser() == r'C:\PATH\chrome.exe'


def test_find_app_mode_browser_via_chemins_windows_connus(monkeypatch):
    """CI tourne sous Linux : os.path.join('C:\\...', 'Microsoft\\Edge\\...')
    n'y assemble PAS avec des antislashs comme sous Windows (POSIX ne les
    traite pas comme séparateurs). `cible` est donc calculée avec le MÊME
    os.path.join que le code testé plutôt qu'écrite en dur avec des
    antislashs littéraux — sinon le test ne passe que sous Windows, trouvé
    en CI (Linux), pas en local."""
    monkeypatch.setattr(boot.shutil, 'which', lambda nom: None)
    monkeypatch.setattr(boot.sys, 'platform', 'win32')
    monkeypatch.setenv('PROGRAMFILES', r'C:\Program Files')
    monkeypatch.setenv('PROGRAMFILES(X86)', r'C:\Program Files (x86)')
    monkeypatch.setenv('LOCALAPPDATA', r'C:\Users\test\AppData\Local')
    cible = os.path.join(r'C:\Program Files (x86)', r'Microsoft\Edge\Application\msedge.exe')
    monkeypatch.setattr(boot.os.path, 'isfile', lambda p: p == cible)

    assert boot._find_app_mode_browser() == cible


def test_find_app_mode_browser_absent_partout(monkeypatch):
    monkeypatch.setattr(boot.shutil, 'which', lambda nom: None)
    monkeypatch.setattr(boot.sys, 'platform', 'win32')
    monkeypatch.setattr(boot.os.path, 'isfile', lambda p: False)

    assert boot._find_app_mode_browser() is None


def test_start_network_diagnosis_utilise_le_mode_application(monkeypatch):
    """Bout en bout : start_network_diagnosis(then_open_browser=True) doit
    appeler open_browser_app_mode(), pas webbrowser.open() directement —
    régression du correctif (avant, le timer appelait webbrowser.open() en
    dur, jamais le mode application)."""
    appels = []
    monkeypatch.setattr(boot, 'pick_fastest_host', lambda port: ('127.0.0.1', 5.0, False))
    monkeypatch.setattr(boot, 'page_de_demarrage', lambda: '/logx_logbook.html')
    monkeypatch.setattr(boot, 'open_browser_app_mode',
                         lambda url, find_browser=None: appels.append(url))

    class TimerImmediat:
        """threading.Timer factice qui exécute la fonction tout de suite,
        synchrone — start_network_diagnosis() fait `import threading` en
        LOCAL dans son corps, mais récupère le même module mis en cache par
        sys.modules : patcher 'threading.Timer' globalement suffit."""
        def __init__(self, delay, fn):
            self.fn = fn
        def start(self):
            self.fn()
    monkeypatch.setattr('threading.Timer', TimerImmediat)

    boot.start_network_diagnosis(8080, delay=0, then_open_browser=True)

    assert appels == ['http://127.0.0.1:8080/logx_logbook.html']
