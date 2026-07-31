# -*- coding: utf-8 -*-
"""Le verrou fantôme du téléchargement : la panne qui survivait au diagnostic.

CE QUE LE DIAGNOSTIC MULTI-AGENTS A PROUVÉ (31/07/2026), vérifié ligne à
ligne ensuite. start_download* posait status='downloading' puis refusait tout
nouvel appel tant que ce statut tenait. Or DEUX chemins pouvaient tuer le
thread SANS état terminal :

  1. les premières lignes de _do_download_via_network — user_data_dir(),
     os.makedirs, _ASSET_SUFFIX_BY_PLATFORM[platform] — et le scan pair-à-pair
     (ThreadPoolExecutor : « can't start new thread » sous famine) vivaient
     HORS de tout try, alors que le chemin direct est protégé de bout en bout ;
  2. Thread.start() lui-même peut lever sous famine de threads — et le statut
     venait d'être posé.

Dans les deux cas, AUCUN mécanisme ne réinitialisait jamais le 'downloading'
orphelin : LA MISE À JOUR ÉTAIT MORTE JUSQU'AU REDÉMARRAGE, sans un message.
Sur une expédition (quinze jours, rien de réparable sur place), c'est la panne
qu'on découvre le jour où on en a besoin. C'est aussi ce thread traînard qui
écrivait 'error' dans l'état tout neuf du test suivant — le flake à ~50 % par
passe de la suite locale.

Ces tests reproduisent CHAQUE mécanisme. Avant correctif, chacun laissait un
'downloading' éternel ; après, un état terminal est toujours posé et
l'orphelin s'auto-guérit.
"""
import os
import sys
import threading
import time
import types

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_update as upd   # noqa: E402


@pytest.fixture(autouse=True)
def _etat_neuf(monkeypatch, tmp_path):
    """Même isolement que test_update_integrity : état module remis à neuf,
    aucune écriture hors tmp_path, et jointure du thread au teardown."""
    monkeypatch.setattr(upd, '_download', {
        'status': 'idle', 'pct': 0, 'error': '', 'path': '',
        'verified': False, 'sha256': '', 'version': '',
        'via': 'direct', 'via_peer': '',
    })
    monkeypatch.setattr(upd, '_download_thread', None)
    monkeypatch.setattr(upd, 'user_data_dir', lambda: str(tmp_path))
    yield
    t = getattr(upd, '_download_thread', None)
    if t is not None and t.is_alive():
        t.join(timeout=30)
        assert not t.is_alive(), 'thread traînard — contaminerait la suite'


def _statut():
    return upd.get_download_status()


def _attendre_terminal(timeout=15):
    fin = time.time() + timeout
    while time.time() < fin:
        st = _statut()
        if st['status'] in ('done', 'error'):
            return st
        time.sleep(0.02)
    pytest.fail('aucun état terminal en %d s : le verrou fantôme est revenu'
                % timeout)


# ─── 1. Une exception en TÊTE du corps pose un état terminal ────────────────

def test_un_makedirs_qui_echoue_ne_laisse_PAS_de_downloading_eternel(monkeypatch, tmp_path):
    """LE mécanisme du flake. user_data_dir() pointe sur un FICHIER : le
    os.makedirs de la 1re ligne du corps lève. Avant correctif ces lignes
    étaient hors de tout try — le thread mourait, status restait 'downloading'
    pour toujours."""
    fichier = tmp_path / 'pas_un_dossier'
    fichier.write_text('x')
    monkeypatch.setattr(upd, 'user_data_dir', lambda: str(fichier))
    ok, _ = upd._demarrer_telechargement(
        upd._do_download_via_network,
        ('peer', ['192.0.2.1'], 'v1.0', upd._platform_key(), 'a' * 64, 0, []))
    assert ok
    st = _attendre_terminal()
    assert st['status'] == 'error'
    assert st['error'], st


def test_une_plateforme_inconnue_pose_un_etat_terminal():
    """_ASSET_SUFFIX_BY_PLATFORM['plateforme-inconnue'] est un KeyError — la
    3e ligne du corps, elle aussi hors try avant correctif."""
    ok, _ = upd._demarrer_telechargement(
        upd._do_download_via_network,
        ('peer', ['192.0.2.1'], 'v1.0', 'plateforme-inconnue', 'a' * 64, 0, []))
    assert ok
    st = _attendre_terminal()
    assert st['status'] == 'error'


def test_un_scan_qui_leve_pose_un_etat_terminal(monkeypatch):
    """scan_network_candidates utilise un ThreadPoolExecutor : sous famine de
    threads il lève RuntimeError — le scénario documenté de ce poste."""
    def boum(*a, **k):
        raise RuntimeError("can't start new thread")
    monkeypatch.setattr(upd, 'scan_network_candidates', boum)
    ok, _ = upd._demarrer_telechargement(
        upd._do_download_via_network,
        ('peer', ['192.0.2.1'], 'v1.0', upd._platform_key(), 'a' * 64, 0, []))
    assert ok
    st = _attendre_terminal()
    assert st['status'] == 'error'
    assert 'interrompu' in st['error'] or 'thread' in st['error'], st


# ─── 2. Thread.start() qui lève ─────────────────────────────────────────────

def test_un_start_qui_leve_sous_famine_pose_error_pas_downloading(monkeypatch):
    """RuntimeError « can't start new thread » APRÈS la pose du statut : avant
    correctif, le statut restait 'downloading' et plus rien ne repartait."""
    class ThreadFamine:
        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")

        def is_alive(self):
            return False

    monkeypatch.setattr(upd, 'threading',
                        types.SimpleNamespace(Thread=ThreadFamine,
                                              Lock=threading.Lock))
    ok, msg = upd._demarrer_telechargement(lambda: None, ())
    assert ok is False
    assert 'Impossible de démarrer' in msg
    assert _statut()['status'] == 'error'
    # Et le verrou n'est PAS resté fermé : un nouvel essai peut partir.
    assert upd._download_thread is None


# ─── 3. L'orphelin s'auto-guérit ────────────────────────────────────────────

def test_un_downloading_orphelin_est_gueri_et_le_suivant_PART(monkeypatch):
    """LE test central. On fabrique l'état exact que laissait le défaut :
    status='downloading', aucun thread vivant. Avant correctif, tout nouvel
    appel répondait « déjà en cours » pour l'éternité. Après, l'état cadavre
    est détecté et le téléchargement suivant démarre."""
    upd._download['status'] = 'downloading'
    monkeypatch.setattr(upd, '_download_thread', None)

    demarre = threading.Event()
    ok, msg = upd._demarrer_telechargement(lambda: demarre.set(), ())
    assert ok is True, msg
    assert demarre.wait(timeout=10), 'le téléchargement suivant n\'est pas parti'


def test_un_downloading_VIVANT_est_toujours_refuse():
    """Le miroir : l'auto-guérison ne doit pas casser l'idempotence. Un vrai
    téléchargement en cours refuse toujours le second."""
    tenir = threading.Event()
    ok, _ = upd._demarrer_telechargement(lambda: tenir.wait(timeout=20), ())
    assert ok is True
    try:
        ok2, msg2 = upd._demarrer_telechargement(lambda: None, ())
        assert ok2 is False
        assert 'déjà en cours' in msg2
    finally:
        tenir.set()


def test_l_orphelin_thread_mort_est_gueri():
    """Variante réaliste : le thread a existé puis est mort sans état terminal
    (c'est ce que produisait l'exception hors try)."""
    mort = threading.Thread(target=lambda: None, daemon=True)
    mort.start()
    mort.join(timeout=5)
    assert not mort.is_alive()
    upd._download['status'] = 'downloading'
    upd._download_thread = mort

    ok, _ = upd._demarrer_telechargement(lambda: None, ())
    assert ok is True


# ─── 4. Les messages de sonde distinguent les deux pannes ───────────────────

def test_pair_injoignable_et_pair_sans_asset_ont_des_messages_DIFFERENTS(monkeypatch):
    """_peer_get_json rend None sur toute erreur (poste éteint, délai 3 s
    dépassé sur un poste chargé — le cas multi-op réel). L'ancien message
    unique « aucun exécutable vérifié à servir » accusait le pair de ne rien
    avoir alors qu'il n'avait pas répondu : l'opérateur cherchait le problème
    sur le mauvais poste."""
    # Cas 1 : sonde muette (timeout / éteint) -> None
    monkeypatch.setattr(upd, '_peer_get_json', lambda *a, **k: None)
    upd._do_download_via_network('peer', ['192.0.2.1'], 'v1.0',
                                 upd._platform_key(), 'a' * 64, 0, [])
    err_injoignable = _statut()['error']
    assert 'injoignable' in err_injoignable, err_injoignable

    # Cas 2 : le pair répond, mais n'a rien à servir
    upd._download.update(status='idle', error='')
    monkeypatch.setattr(upd, '_peer_get_json',
                        lambda *a, **k: {'available': False})
    upd._do_download_via_network('peer', ['192.0.2.1'], 'v1.0',
                                 upd._platform_key(), 'a' * 64, 0, [])
    err_sans_asset = _statut()['error']
    assert 'aucun exécutable' in err_sans_asset, err_sans_asset

    assert err_injoignable != err_sans_asset


def test_meme_distinction_cote_passerelle(monkeypatch):
    monkeypatch.setattr(upd, '_peer_get_json', lambda *a, **k: None)
    upd._do_download_via_network('gateway', ['192.0.2.1'], 'v1.0',
                                 upd._platform_key(), 'a' * 64, 0, [])
    assert 'injoignable' in _statut()['error']


# ─── 5. Le nettoyage de l'état reste complet ────────────────────────────────

def test_l_auto_guerison_remet_tous_les_champs_a_neuf():
    """Le nouveau départ après guérison ne doit pas hériter du pct, du path ou
    du sha256 du cadavre."""
    upd._download.update(status='downloading', pct=73, path='/vieux',
                         sha256='beef', verified=True)
    upd._download_thread = None

    tenir = threading.Event()
    ok, _ = upd._demarrer_telechargement(lambda: tenir.wait(timeout=20), ())
    assert ok
    st = _statut()
    try:
        assert st['pct'] == 0 and st['path'] == '' and st['sha256'] == ''
        assert st['verified'] is False
    finally:
        tenir.set()
