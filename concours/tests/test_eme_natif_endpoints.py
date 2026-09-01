# -*- coding: utf-8 -*-
"""Endpoints EME natif (Tâche 7) : GET /eme/audio-devices, POST /eme/moteur.

Ces routes vivent dans do_GET/do_POST (Handler), qui exigent une vraie
connexion socket (self.headers, self.rfile, _require_auth...) — les lancer
via un serveur live serait une source de flakiness (cf. CLAUDE.md, déjà
rencontré avec test_theme_inline.py). On teste donc les fonctions AGRÉGAT
sous-jacentes (_eme_audio_devices_dict / _eme_moteur_action), exactement le
même motif que _eme_cockpit_dict (testé directement dans
test_eme_cockpit.py, jamais via le handler HTTP)."""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as H          # noqa: E402
import logx_q65_natif as q65n  # noqa: E402


# ─── GET /eme/audio-devices (via _eme_audio_devices_dict) ──────────────────

def test_audio_devices_forme_nominale(monkeypatch):
    monkeypatch.setattr(q65n, 'lister_peripheriques_entree', lambda: [
        {'index': 0, 'nom': 'Micro USB', 'canaux': 2, 'freq_defaut': 48000},
    ])
    d = H._eme_audio_devices_dict()
    assert d == {'devices': [
        {'index': 0, 'nom': 'Micro USB', 'canaux': 2, 'freq_defaut': 48000},
    ]}


def test_audio_devices_liste_vide_sans_peripherique(monkeypatch):
    monkeypatch.setattr(q65n, 'lister_peripheriques_entree', lambda: [])
    assert H._eme_audio_devices_dict() == {'devices': []}


def test_audio_devices_ne_plante_pas_si_sounddevice_absent(monkeypatch):
    """sounddevice est optionnel (import paresseux) : une levée (wheel
    PortAudio absent/casse) ne doit jamais faire tomber l'endpoint — il doit
    répondre une liste vide + une erreur lisible (le natif est opt-in)."""
    def _boom():
        raise RuntimeError('PortAudio introuvable')
    monkeypatch.setattr(q65n, 'lister_peripheriques_entree', _boom)
    d = H._eme_audio_devices_dict()
    assert d['devices'] == []
    assert 'PortAudio introuvable' in d['error']


# ─── POST /eme/moteur (via _eme_moteur_action) ──────────────────────────────

def test_moteur_action_start_appelle_demarrer_moteur(monkeypatch):
    # NOTE (piège déjà documenté dans test_eme_cockpit.py) : ne PAS écrire
    # `vus.setdefault(...) or {...}` — setdefault() renvoie la valeur stockée,
    # qui est truthy pour un cfg non vide, donc `or` ne retomberait jamais
    # sur le second membre. Capture puis retour explicite, sans piège.
    vus = {}

    def _faux_demarrer(cfg):
        vus['cfg'] = cfg
        return {'ok': True}
    monkeypatch.setattr(q65n, 'demarrer_moteur', _faux_demarrer)
    cfg = {'eme': {'audio_device': 3}}
    d = H._eme_moteur_action('start', cfg)
    assert d == {'ok': True}
    assert vus['cfg'] is cfg


def test_moteur_action_stop_appelle_arreter_moteur(monkeypatch):
    appele = []
    monkeypatch.setattr(q65n, 'arreter_moteur', lambda: appele.append(True) or {'ok': True})
    d = H._eme_moteur_action('stop', {})
    assert d == {'ok': True}
    assert appele == [True]


def test_moteur_action_inconnue_renvoie_une_erreur(monkeypatch):
    d = H._eme_moteur_action('vole', {})
    assert d['ok'] is False
    assert 'error' in d


def test_moteur_action_start_echec_materiel_renvoie_erreur_claire(monkeypatch):
    """Le démarrage peut échouer (carte son absente/échec sounddevice) : le
    endpoint doit rendre un {'ok': False, 'error': ...} exploitable côté UI,
    jamais planter le handler."""
    def _boom(cfg):
        raise RuntimeError('carte son absente')
    monkeypatch.setattr(q65n, 'demarrer_moteur', _boom)
    d = H._eme_moteur_action('start', {})
    assert d['ok'] is False
    assert 'carte son absente' in d['error']


# ─── Câblage réel dans le routeur (preuve structurelle, pas juste des mocks
# des fonctions agrégat elles-mêmes) ────────────────────────────────────────

def test_routeur_get_appelle_bien_l_agregat_audio_devices():
    """Filet structurel : le routeur GET doit exposer EXACTEMENT le chemin
    '/eme/audio-devices' et passer par _eme_audio_devices_dict (pas
    réimplémenter la logique inline), sinon les tests ci-dessus ne
    prouveraient rien sur le vrai chemin HTTP. Comparaison exacte (pas juste
    une sous-chaîne) : un chemin voisin comme '/eme/audio-devices-x' ne doit
    pas satisfaire ce test."""
    import inspect
    src = inspect.getsource(H.Handler._do_GET_impl)
    assert "if path == '/eme/audio-devices':" in src
    assert '_eme_audio_devices_dict(' in src


def test_routeur_post_appelle_bien_l_agregat_moteur():
    import inspect
    src = inspect.getsource(H.Handler._do_POST_impl)
    assert "if self.path == '/eme/moteur':" in src
    assert '_eme_moteur_action(' in src
