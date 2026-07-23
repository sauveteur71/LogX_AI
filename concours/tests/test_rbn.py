# -*- coding: utf-8 -*-
"""Tests logx_rbn : parseur (déterministe, sans réseau — déjà en partie couvert
par test_propagation_plus.py) + comportement réseau de where_heard() simulé
par un faux socket (jamais de vraie connexion telnet dans les tests)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_rbn as rbn


# ─── parse_rbn (parseur pur) ─────────────────────────────────────────────────

def test_parse_rbn_dedoublonne_meme_spotter_meme_frequence():
    txt = ('DX de DL0ABC-#:  14025.0  F6KQJ  CW  22 dB  28 wpm  CQ  1432Z\n'
           'DX de DL0ABC-#:  14025.0  F6KQJ  CW  22 dB  28 wpm  CQ  1433Z\n')
    sp = rbn.parse_rbn(txt, 'F6KQJ')
    assert len(sp) == 1  # même (spotter, fréquence arrondie) -> une seule entrée


def test_parse_rbn_wpm_absent_donne_none():
    # Format valide sans le groupe optionnel "NN wpm"
    txt = 'DX de DL0ABC-#:  14025.0  F6KQJ  CW  22 dB  CQ  1432Z\n'
    sp = rbn.parse_rbn(txt, 'F6KQJ')
    assert len(sp) == 1 and sp[0]['wpm'] is None


def test_parse_rbn_trie_par_snr_decroissant():
    txt = ('DX de A-#:  14025.0  F6KQJ  CW  5 dB  20 wpm  CQ  1432Z\n'
           'DX de B-#:  14026.0  F6KQJ  CW  30 dB  20 wpm  CQ  1432Z\n'
           'DX de C-#:  14027.0  F6KQJ  CW  15 dB  20 wpm  CQ  1432Z\n')
    sp = rbn.parse_rbn(txt, 'F6KQJ')
    assert [s['snr'] for s in sp] == [30, 15, 5]


def test_parse_rbn_indicatif_avec_indicatif_portable():
    # La station spottée peut apparaître avec un suffixe (ex: /P) : on compare
    # sur la base (avant le premier '/'), comme le reste du projet.
    txt = 'DX de DL0ABC-#:  14025.0  F6KQJ/P  CW  22 dB  28 wpm  CQ  1432Z\n'
    sp = rbn.parse_rbn(txt, 'F6KQJ')
    assert len(sp) == 1


# ─── where_heard : jamais de vraie connexion réseau dans les tests ───────────

class _FakeRefusedSocket:
    """Simule un port 7000 bloqué (refus de connexion immédiat) — le cas
    fréquent en wifi d'hôtel/4G restrictif que le module ne peut PAS
    contourner en HTTP (voir docstring de logx_rbn : aucun repli HTTP fiable
    et documenté n'existe chez RBN)."""
    def __init__(self, *a, **k):
        pass

    def settimeout(self, t):
        pass

    def connect(self, addr):
        raise ConnectionRefusedError(10061, 'Blocage réseau simulé')

    def close(self):
        pass


def _reset_cache():
    with rbn._lock:
        rbn._cache.update(ts=0, data=None, call='')


def test_where_heard_ne_leve_jamais_si_le_port_est_bloque(monkeypatch):
    monkeypatch.setattr(rbn.socket, 'socket', lambda *a, **k: _FakeRefusedSocket())
    _reset_cache()
    res = rbn.where_heard('F4GLD', timeout=1)
    assert res['ok'] is False
    assert 'error' in res and res['error']  # message non vide, jamais d'exception


class _FakeBlockingSocket:
    """Simule le cas visé par l'exécuteur (voir docstring de logx_rbn) : une
    résolution DNS/connexion qui ne répond jamais (réseau captif, 4G qui
    droppe silencieusement) — connect() bloque plus longtemps que le budget
    total `timeout + 3` accordé par where_heard() à Future.result(). Ça doit
    déclencher un vrai `_cf.TimeoutError` sur .result(), pas une exception
    remontée depuis le socket lui-même."""
    def __init__(self, *a, **k):
        pass

    def settimeout(self, t):
        pass

    def connect(self, addr):
        time.sleep(3.3)

    def recv(self, n):
        return b''

    def sendall(self, data):
        pass

    def close(self):
        pass


def test_where_heard_message_specifique_si_timeout_reel_depasse(monkeypatch):
    """connect() bloque au-delà de `timeout + 3` (le budget accordé à
    Future.result()) -> branche `except _cf.TimeoutError`, pas la branche
    `except Exception` générique : le message doit rester celui, actionnable,
    qui mentionne le port 7000 et l'absence d'alternative HTTP chez RBN."""
    monkeypatch.setattr(rbn.socket, 'socket', lambda *a, **k: _FakeBlockingSocket())
    _reset_cache()
    res = rbn.where_heard('F4GLD', timeout=0.1)  # budget total : 0.1+3 = 3.1s
    assert res['ok'] is False
    assert '7000' in res['error']
    assert 'HTTP' in res['error']
    _reset_cache()


def test_where_heard_indicatif_vide():
    _reset_cache()
    res = rbn.where_heard('', timeout=1)
    assert res == {'ok': False, 'error': 'Indicatif station non défini'}


def test_where_heard_utilise_le_cache_dans_la_fenetre_ttl(monkeypatch):
    """Deux appels rapprochés avec le même indicatif ne doivent PAS déclencher
    deux connexions réseau — le cache (CACHE_S) évite de marteler RBN."""
    calls = {'n': 0}

    class _CountingSocket(_FakeRefusedSocket):
        def connect(self, addr):
            calls['n'] += 1
            raise ConnectionRefusedError(10061, 'Blocage réseau simulé')

    monkeypatch.setattr(rbn.socket, 'socket', lambda *a, **k: _CountingSocket())
    _reset_cache()
    # Le premier appel échoue réseau -> pas mis en cache (seul un résultat 'ok'
    # est mis en cache, voir where_heard) : on force donc directement l'entrée
    # de cache pour vérifier la relecture, sans dépendre du réseau simulé.
    with rbn._lock:
        rbn._cache.update(ts=time.time(), call='F4GLD',
                           data={'ok': True, 'call': 'F4GLD', 'count': 0,
                                 'spots': [], 'best_snr': None, 'bands': []})
    res = rbn.where_heard('F4GLD', timeout=1)
    assert res['ok'] is True
    assert calls['n'] == 0  # aucune connexion : servi depuis le cache
    _reset_cache()
