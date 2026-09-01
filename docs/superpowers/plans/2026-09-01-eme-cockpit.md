# Section EME — Tranche 1 (cockpit + suivi lunaire) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter à LogX AI une page cockpit EME (position Lune, Doppler, décodages Q65/JT65, état rig) et un suivi lunaire automatique du rotor, en réutilisant l'existant.

**Architecture:** Un module de suivi `logx_moon_track.py` calqué sur `logx_sat_track.py` (boucle thread → rotor, sécurités reprises). Un agrégateur `_eme_cockpit_dict()` compose les briques déjà présentes (`logx_eme` position/Doppler via `ephem`, `logx_wsjtx.recent_decodes` filtré Q65/JT65, état du suivi). Une page `logx_eme.html` poll un seul endpoint. Aucune dépendance neuve, aucune table SQL.

**Tech Stack:** Python 3 `http.server` (`concours/logx_http.py`), `ephem` (déjà là), HTML/JS vanilla, `pytest`, `py_mini_racer` pour le JS.

**Spec:** `docs/superpowers/specs/2026-09-01-eme-cockpit-design.md`

## Global Constraints

- **Contre-épreuve par mutation OBLIGATOIRE** après chaque test vert : remettre le défaut → le test doit ROUGIR → restaurer → contrôler l'empreinte md5. Un test vert du premier coup ne prouve rien sans témoin.
- **Rotor/radio/Lune réels NON testables côté agent** : les bancs SIMULENT le rotor (faux enregistrant les consignes) et la Lune (séquence de positions). Le pointage réel se valide en station — ne jamais l'annoncer « traité » sans mesure.
- **Vocabulaire visible** : « portable »/« expédition », JAMAIS « activation »/« activateur ».
- **i18n** : toute chaîne visible neuve passe par `Tf(...)` (`logx_i18n`) ; un test `test_i18n_dialogues` bloque les chaînes brutes.
- **Valeurs de domaine sourcées** : les fréquences d'activité EME viennent du plan de bandes IARU R1 (source citée), jamais devinées ; marqueur `VALEUR À SOURCER` tant que non sourcé.
- **Carnet unique** : aucune table `eme_*`. Un QSO EME reste un QSO du carnet chronologique unique.
- **Branche** : `feat/eme-cockpit` (déjà créée, off `main`).
- **Endpoints** : idiome `self._json(dict, status)`, config via `self._cfg_snapshot()`, POST body `json.loads(body)`.
- `moon_position()` renvoie la clé **`alt`** (pas `el`), `az`, `distance_km`, `phase_pct`, `visible`.

---

### Task 1 : `logx_moon_track.py` — boucle de suivi lunaire + état

**Files:**
- Create: `concours/logx_moon_track.py`
- Test: `concours/tests/test_moon_track.py`

**Interfaces:**
- Consumes : `logx_eme.moon_position(lat, lon, elevation_m, when) -> {available, az, alt, visible, distance_km, phase_pct}` ; `logx_rotor.set_position(host, port, az, el, proto)`, `get_position(host, port, proto)`, `stop(host, port, proto)` ; `logx_station.azimut_rotor(offset, az_vrai) -> az|None`.
- Produces : `etat_suivi_lune() -> dict` (JSON-safe) ; `ecart_azimut(a, b) -> float|None` ; `_boucle_suivi_lune(host, port, lat, lon, alt_m, stop_ev, cadence_s=CADENCE_S, duree_max_s=DUREE_MAX_S, deadband_deg=DEADBAND_DEG, offset_az=0.0, proto='rotctld')` ; constantes `DEADBAND_DEG=4.0`, `CADENCE_S=10.0`, `DUREE_MAX_S=8*3600`, `ECHECS_ROTOR_MAX=3`, `TOURS_ENTRE_LECTURES=5` ; état module `_track`, `_track_thread`, `_stop_courant`, `_lock`.

- [ ] **Step 1 : Écrire le squelette du module (état + helpers, PAS la boucle)**

Créer `concours/logx_moon_track.py` :

```python
# -*- coding: utf-8 -*-
"""Suivi rotor de la Lune (EME) : le fil entre l'éphéméride lunaire et l'antenne.

Calqué sur logx_sat_track.py, mais la Lune est un cas plus simple : elle bouge
~0,5°/min (pas de course au TCA, pas de pré-pointage d'un azimut de lever, pas
de TLE). logx_eme.moon_position() dit OÙ elle est, logx_rotor sait POINTER.
Toutes les sécurités de sat_track sont reprises : Event PAR suivi, auto-guérison
de l'orphelin, bande morte, échecs rotor bornés, corps enveloppé (état terminal
garanti), aucun appel réseau dans le handler HTTP (la boucle écrit _track, le
endpoint LIT).
"""
import math
import threading
import time

import logx_eme as eme
import logx_rotor as rotor
import logx_station as station
from logx_utils import locator_to_latlon

DEADBAND_DEG = 4.0
CADENCE_S = 10.0            # la Lune bouge ~0,5°/min : rafraîchir plus vite n'apporte rien
DUREE_MAX_S = 8 * 3600     # session EME longue ; plafond de sécurité (la boucle s'arrête au coucher)
ECHECS_ROTOR_MAX = 3
TOURS_ENTRE_LECTURES = 5

_lock = threading.Lock()
_stop_courant = None
_track = {
    'actif': False, 'phase': 'inactif', 'message': '', 'note': '',
    'cible_az': None, 'cible_el': None, 'rotor_az': None, 'rotor_el': None,
    'envois': 0, 'visible': False,
}
_track_thread = None


def etat_suivi_lune():
    """État courant, JSON-safe, sans aucun appel réseau."""
    with _lock:
        return dict(_track)


def ecart_azimut(a, b):
    """Écart angulaire le plus court entre deux azimuts, en degrés.
    |359° − 1°| vaut 2°, pas 358°."""
    try:
        d = abs(float(a) - float(b)) % 360.0
    except (TypeError, ValueError):
        return None
    return min(d, 360.0 - d)


def _fin(phase, message=''):
    with _lock:
        _track.update(actif=False, phase=phase, message=message)
```

- [ ] **Step 2 : Écrire le test de `ecart_azimut` (test qui doit d'abord échouer si la fonction manque)**

Créer `concours/tests/test_moon_track.py` :

```python
# -*- coding: utf-8 -*-
"""Suivi rotor de la Lune : chaque sécurité prouvée, rotor et Lune SIMULÉS.

Le rotor réel n'est pas testable côté agent : le faux enregistre les consignes,
on vérifie ce qui part réellement vers la mécanique. La Lune est une séquence de
positions (az, alt) — pas d'attente du vrai ciel ni d'ephem."""
import math
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_moon_track as mt   # noqa: E402


def test_ecart_azimut_passe_par_le_plus_court_chemin():
    assert mt.ecart_azimut(359, 1) == 2
    assert mt.ecart_azimut(1, 359) == 2
    assert mt.ecart_azimut(0, 180) == 180
    assert mt.ecart_azimut(90, 90) == 0
    assert mt.ecart_azimut('a', 1) is None
```

- [ ] **Step 3 : Lancer le test, vérifier qu'il PASSE (helper déjà écrit au step 1)**

Run: `python -m pytest concours/tests/test_moon_track.py::test_ecart_azimut_passe_par_le_plus_court_chemin -v`
Expected: PASS.

Contre-épreuve : dans `logx_moon_track.py`, remplacer `return min(d, 360.0 - d)` par `return d` → relancer → le cas `ecart_azimut(359,1)` doit ROUGIR (donnerait 358). Restaurer, vérifier md5 inchangé.

- [ ] **Step 4 : Écrire les bancs FauxRotor / FauxLune + le lanceur déterministe**

Ajouter dans `concours/tests/test_moon_track.py` :

```python
class FauxRotor:
    """Enregistre les consignes. Peut être rendu muet (panne)."""
    def __init__(self):
        self.consignes = []
        self.stops = 0
        self.panne = False

    def set_position(self, host, port, az, el=0, proto='rotctld'):
        if self.panne:
            return {'ok': False, 'error': 'rotctld injoignable (panne simulée)'}
        self.consignes.append((round(float(az), 1), round(float(el), 1)))
        return {'ok': True, 'azimuth': round(float(az), 1), 'elevation': round(float(el), 1)}

    def get_position(self, host, port, proto='rotctld'):
        if self.panne:
            return {'ok': False, 'error': 'rotctld injoignable (panne simulée)'}
        az, el = self.consignes[-1] if self.consignes else (0.0, 0.0)
        return {'ok': True, 'azimuth': az, 'elevation': el}

    def stop(self, host, port, proto='rotctld'):
        self.stops += 1
        return {'ok': True}


class FauxLune:
    """Séquence de positions lunaires (az, alt) ; None = indisponible. La
    dernière se répète."""
    def __init__(self, sequence):
        self.seq = list(sequence)
        self.i = 0

    def moon_position(self, lat, lon, elevation_m=0, when=None):
        p = self.seq[min(self.i, len(self.seq) - 1)]
        self.i += 1
        if p is None:
            return {'available': False, 'error': 'position indisponible (test)'}
        az, alt = p
        return {'available': True, 'az': az, 'alt': alt, 'visible': alt > 0,
                'distance_km': 384000.0, 'phase_pct': 50.0}


@pytest.fixture(autouse=True)
def _etat_neuf(monkeypatch):
    monkeypatch.setattr(mt, '_track', {
        'actif': False, 'phase': 'inactif', 'message': '', 'note': '',
        'cible_az': None, 'cible_el': None, 'rotor_az': None, 'rotor_el': None,
        'envois': 0, 'visible': False,
    })
    monkeypatch.setattr(mt, '_track_thread', None)
    monkeypatch.setattr(mt, '_stop_courant', None)
    yield


def _rotor(monkeypatch):
    faux = FauxRotor()
    monkeypatch.setattr(mt.rotor, 'set_position', faux.set_position)
    monkeypatch.setattr(mt.rotor, 'get_position', faux.get_position)
    monkeypatch.setattr(mt.rotor, 'stop', faux.stop)
    return faux


def _lune(monkeypatch, sequence):
    faux = FauxLune(sequence)
    monkeypatch.setattr(mt.eme, 'moon_position', faux.moon_position)
    return faux


def _lancer(sequence, monkeypatch, cadence=0.01, duree_max=30, deadband=mt.DEADBAND_DEG):
    """Exécute la boucle DANS le thread de test (déterministe)."""
    import threading as _th
    rot = _rotor(monkeypatch)
    _lune(monkeypatch, sequence)
    ev = _th.Event()
    mt._track.update(actif=True, phase='suivi')
    mt._boucle_suivi_lune('h', 1, 45.0, 4.0, 0, ev,
                          cadence_s=cadence, duree_max_s=duree_max, deadband_deg=deadband)
    return rot
```

- [ ] **Step 5 : Écrire les tests de comportement de la boucle (échoueront : boucle absente)**

Ajouter dans `concours/tests/test_moon_track.py` :

```python
def test_suit_la_lune_puis_s_arrete_au_coucher(monkeypatch):
    # Montée puis descente sous l'horizon.
    seq = [(180, 10), (185, 25), (200, 45), (215, 20), (230, -2)]
    rot = _lancer(seq, monkeypatch)
    assert rot.consignes, 'aucune consigne pendant la visibilité'
    assert rot.stops >= 1, 'rotor non stoppé au coucher'
    etat = mt.etat_suivi_lune()
    assert etat['actif'] is False
    assert etat['phase'] == 'fini'
    assert 'couch' in etat['message'].lower()


def test_jamais_d_elevation_negative_envoyee(monkeypatch):
    seq = [(180, 30), (185, 0.4), (190, -3)]
    rot = _lancer(seq, monkeypatch, deadband=0.1)
    for az, el in rot.consignes:
        assert el >= 0, rot.consignes


def test_la_bande_morte_evite_les_micro_corrections(monkeypatch):
    seq = [(180.0 + i * 0.3, 30.0 + i * 0.2) for i in range(10)] + [(183, -1)]
    rot = _lancer(seq, monkeypatch)
    assert len(rot.consignes) == 1, rot.consignes


def test_un_vrai_deplacement_traverse_la_bande_morte(monkeypatch):
    seq = [(180, 30), (190, 40), (183, -1)]
    rot = _lancer(seq, monkeypatch)
    assert len(rot.consignes) == 2, rot.consignes


def test_le_passage_au_nord_est_signale(monkeypatch):
    seq = [(350, 30), (10, 40), (15, -1)]
    _lancer(seq, monkeypatch, deadband=4.0)
    assert 'tour complet' in (mt.etat_suivi_lune().get('note') or ''), mt.etat_suivi_lune()


def test_la_duree_maximale_arrete_le_suivi(monkeypatch):
    seq = [(180, 30)] * 10000
    rot = _lancer(seq, monkeypatch, cadence=0.001, duree_max=0.05)
    etat = mt.etat_suivi_lune()
    assert etat['phase'] == 'fini'
    assert 'maximale' in etat['message']
    assert rot.stops >= 1


def test_trois_echecs_rotor_consecutifs_arretent_avec_message(monkeypatch):
    import threading as _th
    rot = _rotor(monkeypatch)
    rot.panne = True
    _lune(monkeypatch, [(180 + i * 10, 30) for i in range(50)])
    mt._track.update(actif=True)
    mt._boucle_suivi_lune('h', 1, 45.0, 4.0, 0, _th.Event(), cadence_s=0.01, duree_max_s=30)
    etat = mt.etat_suivi_lune()
    assert etat['phase'] == 'erreur'
    assert 'injoignable' in etat['message']


def test_une_ephemeride_indisponible_pose_un_etat_terminal(monkeypatch):
    rot = _lancer([(180, 30), None], monkeypatch)
    etat = mt.etat_suivi_lune()
    assert etat['phase'] == 'erreur'
    assert rot.stops >= 1


def test_une_exception_dans_le_corps_pose_TOUJOURS_un_etat_terminal(monkeypatch):
    import threading as _th
    _rotor(monkeypatch)

    def boum(*a, **k):
        raise RuntimeError('exception arbitraire (test)')
    monkeypatch.setattr(mt.eme, 'moon_position', boum)
    mt._track.update(actif=True)
    mt._boucle_suivi_lune('h', 1, 45.0, 4.0, 0, _th.Event(), cadence_s=0.01, duree_max_s=30)
    etat = mt.etat_suivi_lune()
    assert etat['actif'] is False
    assert etat['phase'] == 'erreur'
    assert 'interrompu' in etat['message']


def test_l_etat_est_serialisable_JSON(monkeypatch):
    import json
    _lancer([(180, 30), (185, -1)], monkeypatch)
    json.dumps(mt.etat_suivi_lune(), allow_nan=False)   # ne doit pas lever
```

- [ ] **Step 6 : Lancer les tests, vérifier qu'ils ÉCHOUENT (boucle absente)**

Run: `python -m pytest concours/tests/test_moon_track.py -v`
Expected: FAIL — `AttributeError: module 'logx_moon_track' has no attribute '_boucle_suivi_lune'`.

- [ ] **Step 7 : Implémenter la boucle (`_boucle_suivi_lune` + corps)**

Ajouter dans `concours/logx_moon_track.py` :

```python
def _boucle_suivi_lune(host, port, lat, lon, alt_m, stop_ev,
                       cadence_s=CADENCE_S, duree_max_s=DUREE_MAX_S,
                       deadband_deg=DEADBAND_DEG, offset_az=0.0, proto='rotctld'):
    """Corps enveloppé de bout en bout : quoi qu'il arrive, un état terminal est
    posé (leçon du verrou fantôme). `stop_ev` est PROPRE à ce suivi."""
    try:
        _boucle_suivi_lune_corps(host, port, lat, lon, alt_m, stop_ev,
                                 cadence_s, duree_max_s, deadband_deg, offset_az, proto)
    except Exception as e:
        try:
            rotor.stop(host, port, proto=proto)
        except Exception:
            pass
        _fin('erreur', 'Suivi interrompu : %s' % e)


def _boucle_suivi_lune_corps(host, port, lat, lon, alt_m, stop_ev,
                             cadence_s, duree_max_s, deadband_deg, offset_az, proto):
    debut = time.monotonic()
    vu_au_dessus = False
    echecs = 0
    derniere_consigne = None
    tours = 0
    lecture_az = lecture_el = None

    while True:
        if stop_ev.is_set():
            rotor.stop(host, port, proto=proto)
            _fin('fini', "Arrêté par l'opérateur.")
            return
        if time.monotonic() - debut > duree_max_s:
            rotor.stop(host, port, proto=proto)
            _fin('fini', 'Durée maximale de suivi atteinte (%d h) — arrêt '
                         'automatique.' % (duree_max_s // 3600))
            return

        pos = eme.moon_position(lat, lon, alt_m)
        if not pos.get('available'):
            rotor.stop(host, port, proto=proto)
            _fin('erreur', pos.get('error', 'Position de la Lune indisponible.'))
            return

        el = pos['alt']
        visible = el > 0
        note = ''

        if visible:
            vu_au_dessus = True
            cible_az, cible_el = pos['az'], max(0.0, el)
            phase = 'suivi'
        elif vu_au_dessus:
            rotor.stop(host, port, proto=proto)
            _fin('fini', 'Lune couchée — fin de fenêtre.')
            return
        else:
            # Défensif : le démarrage est refusé sous l'horizon, on n'attend pas.
            rotor.stop(host, port, proto=proto)
            _fin('fini', 'Lune sous l\'horizon.')
            return

        envoyer = derniere_consigne is None
        if not envoyer:
            d_az = ecart_azimut(cible_az, derniere_consigne[0])
            d_el = abs(cible_el - derniere_consigne[1])
            envoyer = (d_az is not None and d_az > deadband_deg) or d_el > deadband_deg
            if envoyer and abs(float(cible_az) - derniere_consigne[0]) > 180:
                note = ('Passage de la Lune au nord : un rotor sans '
                        'chevauchement fait un tour complet ici.')

        envoi_ok = None
        if envoyer:
            if stop_ev.is_set():
                continue
            az_envoi = station.azimut_rotor({'offset_deg': offset_az}, cible_az)
            if az_envoi is None:
                az_envoi = cible_az
            r = rotor.set_position(host, port, az_envoi, cible_el, proto=proto)
            if r.get('ok'):
                echecs = 0
                derniere_consigne = (cible_az, cible_el)
                envoi_ok = r
            else:
                echecs += 1
                if echecs >= ECHECS_ROTOR_MAX:
                    rotor.stop(host, port, proto=proto)
                    _fin('erreur', 'Rotor injoignable (%d échecs consécutifs) — %s'
                         % (echecs, r.get('error', '')))
                    return

        tours += 1
        if tours % TOURS_ENTRE_LECTURES == 0:
            lu = rotor.get_position(host, port, proto=proto)
            if lu.get('ok') and math.isfinite(lu['azimuth']) and math.isfinite(lu['elevation']):
                lecture_az, lecture_el = lu['azimuth'], lu['elevation']

        with _lock:
            maj = {'phase': phase, 'visible': visible, 'note': note,
                   'cible_az': round(float(cible_az), 1),
                   'cible_el': round(float(cible_el), 1)}
            if envoi_ok is not None:
                maj['envois'] = _track['envois'] + 1
            if lecture_az is not None:
                maj['rotor_az'], maj['rotor_el'] = lecture_az, lecture_el
            elif envoi_ok is not None:
                maj['rotor_az'] = envoi_ok['azimuth']
                maj['rotor_el'] = envoi_ok['elevation']
            _track.update(maj)

        if stop_ev.wait(cadence_s):
            continue
```

- [ ] **Step 8 : Lancer tous les tests de la boucle, vérifier qu'ils PASSENT**

Run: `python -m pytest concours/tests/test_moon_track.py -v`
Expected: tous PASS.

- [ ] **Step 9 : Contre-épreuve par mutation (3 mutations ciblées)**

Pour CHAQUE mutation : appliquer → relancer → vérifier que le test nommé ROUGIT → restaurer → `md5sum concours/logx_moon_track.py` doit revenir à l'empreinte d'origine (la noter avant).
1. `max(0.0, el)` → `el` : `test_jamais_d_elevation_negative_envoyee` doit rougir.
2. supprimer le bloc `elif vu_au_dessus:` (retour au coucher) : `test_suit_la_lune_puis_s_arrete_au_coucher` doit rougir.
3. `if echecs >= ECHECS_ROTOR_MAX` → `if False` : `test_trois_echecs_rotor_consecutifs_arretent_avec_message` doit boucler/rougir (borne le test avec `duree_max` court si besoin).

- [ ] **Step 10 : Commit**

```bash
git add concours/logx_moon_track.py concours/tests/test_moon_track.py
git commit -m "feat(eme): boucle de suivi lunaire du rotor (calquee sur sat_track)"
```

---

### Task 2 : `logx_moon_track.py` — démarrage/arrêt (refus synchrones + anti-orphelin)

**Files:**
- Modify: `concours/logx_moon_track.py` (ajout de `demarrer_suivi_lune`, `arreter_suivi_lune`)
- Test: `concours/tests/test_moon_track.py` (ajout)

**Interfaces:**
- Consumes : `logx_station.rotor_defaut(cfg, prefer_bandes=['144','432','1296']) -> {enabled, host, port, proto, offset_deg}` ; `logx_eme.HAS_EPHEM` ; `logx_eme.moon_position`, `logx_eme.moon_rise_set(...) -> {available, rise_utc, set_utc}` ; `locator_to_latlon(loc) -> (lat, lon)|(None, None)`.
- Produces : `demarrer_suivi_lune(cfg) -> (ok: bool, message: str)` ; `arreter_suivi_lune() -> (ok, message)`.

- [ ] **Step 1 : Écrire les tests de refus + anti-orphelin (échoueront : fonctions absentes)**

Ajouter dans `concours/tests/test_moon_track.py` :

```python
CFG = {'rotor_enabled': True, 'rotor_host': '127.0.0.1', 'rotor_port': 4533,
       'locator': 'JN15XC', 'altitude': 0}


def _prets(monkeypatch, visible=True):
    rot = _rotor(monkeypatch)
    monkeypatch.setattr(mt.eme, 'HAS_EPHEM', True)
    monkeypatch.setattr(mt.eme, 'moon_position', lambda lat, lon, alt=0, when=None: {
        'available': True, 'az': 180.0, 'alt': 30.0 if visible else -30.0,
        'visible': visible, 'distance_km': 384000.0, 'phase_pct': 50.0})
    monkeypatch.setattr(mt.eme, 'moon_rise_set', lambda lat, lon, alt=0, when=None: {
        'available': True, 'rise_utc': '2026/9/1 21:14:00', 'set_utc': '2026/9/2 06:02:00'})
    return rot


def test_refus_si_ephem_absent(monkeypatch):
    _prets(monkeypatch)
    monkeypatch.setattr(mt.eme, 'HAS_EPHEM', False)
    ok, msg = mt.demarrer_suivi_lune(CFG)
    assert ok is False and 'ephem' in msg.lower()


def test_refus_si_rotor_desactive(monkeypatch):
    _prets(monkeypatch)
    ok, msg = mt.demarrer_suivi_lune(dict(CFG, rotor_enabled=False))
    assert ok is False and 'CONFIG' in msg


def test_refus_si_locator_absent(monkeypatch):
    _prets(monkeypatch)
    ok, msg = mt.demarrer_suivi_lune(dict(CFG, locator=''))
    assert ok is False and 'ocator' in msg


def test_refus_si_lune_sous_l_horizon_avec_heure_de_lever(monkeypatch):
    _prets(monkeypatch, visible=False)
    ok, msg = mt.demarrer_suivi_lune(CFG)
    assert ok is False
    assert '21:14' in msg   # l'heure du prochain lever, pour savoir quand revenir


def test_refus_si_rotor_ne_repond_pas(monkeypatch):
    rot = _prets(monkeypatch)
    rot.panne = True
    ok, msg = mt.demarrer_suivi_lune(CFG)
    assert ok is False and 'injoignable' in msg


def test_un_suivi_VIVANT_refuse_le_second(monkeypatch):
    _prets(monkeypatch)
    ok, msg = mt.demarrer_suivi_lune(CFG)
    assert ok is True, msg
    ok2, msg2 = mt.demarrer_suivi_lune(CFG)
    assert ok2 is False and 'déjà en cours' in msg2
    mt.arreter_suivi_lune()


def test_un_suivi_ORPHELIN_est_gueri_et_le_second_part(monkeypatch):
    _prets(monkeypatch)
    mt._track['actif'] = True
    mt._track_thread = None
    ok, msg = mt.demarrer_suivi_lune(CFG)
    assert ok is True, msg
    mt.arreter_suivi_lune()


def test_les_NaN_du_rotor_ne_partent_pas_dans_le_JSON(monkeypatch):
    import json
    _prets(monkeypatch)
    monkeypatch.setattr(mt.rotor, 'get_position',
                        lambda h, p, proto='rotctld': {'ok': True, 'azimuth': float('nan'),
                                                       'elevation': float('inf')})
    monkeypatch.setattr(mt, '_boucle_suivi_lune', lambda *a, **k: None)
    ok, msg = mt.demarrer_suivi_lune(CFG)
    assert ok, msg
    etat = mt.etat_suivi_lune()
    assert etat['rotor_az'] is None and etat['rotor_el'] is None
    json.dumps(etat, allow_nan=False)
    mt.arreter_suivi_lune()
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `python -m pytest concours/tests/test_moon_track.py -k "refus or suivi or NaN" -v`
Expected: FAIL — `demarrer_suivi_lune` absent.

- [ ] **Step 3 : Implémenter `demarrer_suivi_lune` / `arreter_suivi_lune`**

Ajouter dans `concours/logx_moon_track.py` :

```python
def demarrer_suivi_lune(cfg):
    """Démarre le suivi lunaire. (ok, message) — refus SYNCHRONES : tout ce qui
    peut être vérifié avant de lancer le thread l'est ici, pour que l'opérateur
    ait la raison sous les yeux immédiatement."""
    global _track_thread, _stop_courant

    if not eme.HAS_EPHEM:
        return False, ("Bibliothèque 'ephem' non installée (pip install ephem) — "
                       'position de la Lune indisponible.')

    rs = station.rotor_defaut(cfg, prefer_bandes=['144', '432', '1296'])
    if not rs['enabled']:
        return False, ('Rotor non activé — voir CONFIG, section rotor '
                       '(mode expert).')

    lat, lon = locator_to_latlon((cfg or {}).get('locator', '') or '')
    if lat is None:
        return False, 'Locator manquant ou invalide (page CONFIG).'
    alt_m = (cfg or {}).get('altitude', 0) or 0

    pos = eme.moon_position(lat, lon, alt_m)
    if not pos.get('available'):
        return False, pos.get('error', 'Position de la Lune indisponible.')
    if not pos.get('visible'):
        info = eme.moon_rise_set(lat, lon, alt_m)
        lever = (info.get('rise_utc') if info.get('available') else None) or '?'
        return False, ("La Lune est sous l'horizon — prochain lever : %s UTC." % lever)

    r = rotor.get_position(rs['host'], rs['port'], proto=rs.get('proto', 'rotctld'))
    if not r.get('ok'):
        return False, r.get('error', 'Rotor injoignable.')

    with _lock:
        if _track['actif']:
            if _track_thread is not None and _track_thread.is_alive():
                return False, 'Un suivi lunaire est déjà en cours.'
            _track.update(actif=False, phase='erreur',
                          message='Suivi précédent interrompu sans état terminal '
                                  '— réinitialisé automatiquement.')
        ev = threading.Event()
        t = threading.Thread(
            target=_boucle_suivi_lune,
            args=(rs['host'], rs['port'], lat, lon, alt_m, ev),
            kwargs={'duree_max_s': DUREE_MAX_S, 'offset_az': rs['offset_deg'],
                    'proto': rs.get('proto', 'rotctld')},
            daemon=True)
        _track.update(actif=True, phase='suivi', message='', note='',
                      cible_az=None, cible_el=None,
                      rotor_az=r['azimuth'] if math.isfinite(r['azimuth']) else None,
                      rotor_el=r['elevation'] if math.isfinite(r['elevation']) else None,
                      envois=0, visible=True)
        try:
            t.start()
        except Exception as e:
            _track.update(actif=False, phase='erreur',
                          message='Impossible de démarrer le suivi : %s' % e)
            _track_thread = None
            return False, 'Impossible de démarrer le suivi : %s' % e
        _track_thread = t
        _stop_courant = ev
    return True, ''


def arreter_suivi_lune():
    """Demande d'arrêt du suivi courant — la boucle s'arrête immédiatement (elle
    dort sur cet Event) et stoppe le rotor."""
    with _lock:
        ev = _stop_courant
    if ev is not None:
        ev.set()
    return True, ''
```

- [ ] **Step 4 : Lancer, vérifier que tout PASSE**

Run: `python -m pytest concours/tests/test_moon_track.py -v`
Expected: tous PASS. (Le fixture `_etat_neuf` remet l'état ; un `mt.arreter_suivi_lune()` conclut les suivis lancés.)

- [ ] **Step 5 : Contre-épreuve par mutation (2 mutations)**

1. `if not pos.get('visible'):` → `if False:` : `test_refus_si_lune_sous_l_horizon_avec_heure_de_lever` doit rougir.
2. `if _track_thread is not None and _track_thread.is_alive():` → `if _track['actif']:` (retour du verrou fantôme) : `test_un_suivi_ORPHELIN_est_gueri_et_le_second_part` doit rougir. Restaurer, vérifier md5.

- [ ] **Step 6 : Commit**

```bash
git add concours/logx_moon_track.py concours/tests/test_moon_track.py
git commit -m "feat(eme): demarrage/arret du suivi lunaire (refus synchrones, anti-orphelin)"
```

---

### Task 3 : `logx_wsjtx.eme_decodes()` — relais filtré Q65/JT65

**Files:**
- Modify: `concours/logx_wsjtx.py` (ajout de `eme_decodes`, `EME_MODES`)
- Test: `concours/tests/test_eme_decodes.py`

**Interfaces:**
- Consumes : `logx_wsjtx.recent_decodes(max_age) -> [ {call, band, freq_mhz, mode, message, snr, last_seen, ...} ]`.
- Produces : `eme_decodes(max_age=_DECODE_TTL) -> [même forme, filtré mode ∈ EME_MODES]` ; `EME_MODES = frozenset({'Q65', 'JT65'})`.

- [ ] **Step 1 : Écrire le test (échouera : `eme_decodes` absent)**

Créer `concours/tests/test_eme_decodes.py` :

```python
# -*- coding: utf-8 -*-
"""Le relais EME ne garde que les décodages Q65/JT65 (pas FT8/FT4)."""
import os
import sys
import time

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_wsjtx as w   # noqa: E402


def _peupler(monkeypatch, modes):
    now = time.time()
    faux = [{'call': 'STA%d' % i, 'band': '432', 'freq_mhz': 432.07,
             'mode': m, 'message': 'CQ STA%d IO91' % i, 'snr': -22,
             'last_seen': now} for i, m in enumerate(modes)]
    monkeypatch.setattr(w, 'recent_decodes', lambda max_age=w._DECODE_TTL: faux)


def test_garde_Q65_et_JT65_exclut_FT8_FT4(monkeypatch):
    _peupler(monkeypatch, ['Q65', 'FT8', 'JT65', 'FT4', 'q65'])
    modes = {d['mode'].upper() for d in w.eme_decodes()}
    assert modes == {'Q65', 'JT65'}, modes


def test_liste_vide_si_aucun_mode_EME(monkeypatch):
    _peupler(monkeypatch, ['FT8', 'FT4'])
    assert w.eme_decodes() == []
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `python -m pytest concours/tests/test_eme_decodes.py -v`
Expected: FAIL — `module 'logx_wsjtx' has no attribute 'eme_decodes'`.

- [ ] **Step 3 : Implémenter `eme_decodes`**

Ajouter dans `concours/logx_wsjtx.py` (près de `recent_decodes`, après sa définition) :

```python
# Modes EME faible-signal relayés au cockpit EME. Le pont est mode-agnostique
# (parse_message lit le champ mode tel quel) : Q65/JT65 transitent déjà, il
# suffit de les DISTINGUER de FT8/FT4 côté vue.
EME_MODES = frozenset({'Q65', 'JT65'})


def eme_decodes(max_age=_DECODE_TTL):
    """Décodages récents en mode EME (Q65/JT65) uniquement — vue consommée par
    le cockpit EME. S'appuie sur recent_decodes() (cache + purge déjà gérés)."""
    return [d for d in recent_decodes(max_age)
            if str(d.get('mode', '')).upper() in EME_MODES]
```

- [ ] **Step 4 : Lancer, vérifier que ça PASSE**

Run: `python -m pytest concours/tests/test_eme_decodes.py -v`
Expected: PASS.

- [ ] **Step 5 : Contre-épreuve par mutation**

`in EME_MODES` → `not in EME_MODES` : `test_garde_Q65_et_JT65_exclut_FT8_FT4` doit rougir (renverrait FT8/FT4). Restaurer, vérifier md5.

- [ ] **Step 6 : Commit**

```bash
git add concours/logx_wsjtx.py concours/tests/test_eme_decodes.py
git commit -m "feat(eme): relais des decodages Q65/JT65 (eme_decodes filtre par mode)"
```

---

### Task 4 : `logx_eme_bandplan.py` — fréquences d'activité EME sourcées IARU R1

**Files:**
- Create: `concours/logx_eme_bandplan.py`
- Test: `concours/tests/test_eme_bandplan.py`

**Interfaces:**
- Produces : `EME_ACTIVITE -> dict[str, {'rf_mhz': float, 'transverter': bool, 'label': str}]` clés = bandes internes ('50','144','432','1296','2320','3400','5760','10368','24048','47088') ; `centre_rf_mhz(band) -> float|None` ; `est_transverter(band) -> bool`.

> **Sourcing OBLIGATOIRE avant de figer les valeurs.** Récupérer le plan de bandes **IARU Région 1** (VHF/UHF : `https://www.iaru-r1.org/reference/band-plans/` puis micro-ondes) et relever les centres d'activité EME. Citer l'URL exacte en tête du fichier. Tant qu'une valeur n'est pas confirmée par la source, la laisser marquée `# VALEUR À SOURCER` et NE PAS l'inventer. Repères non confirmés fournis par F4GLD (à re-vérifier, pas à recopier tels quels) : 50.190 / 144.100–144.150 / 432.065 / 1296.065 / 2320.065 MHz. Au-dessus de 1296, `transverter=True` (dial CAT = FI, pas la RF).

- [ ] **Step 1 : Sourcer les fréquences (recherche web, PAS d'invention)**

Récupérer le plan de bandes IARU R1 VHF/UHF/micro-ondes. Noter, pour chaque bande EME, le centre d'activité et l'URL. Consigner la source.

- [ ] **Step 2 : Écrire le test de structure (échouera : module absent)**

Créer `concours/tests/test_eme_bandplan.py` :

```python
# -*- coding: utf-8 -*-
"""Le plan de bandes EME : bandes attendues, RF plausibles, transverter cohérent."""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_eme_bandplan as bp   # noqa: E402

BANDES = ['50', '144', '432', '1296', '2320', '3400', '5760', '10368', '24048', '47088']


def test_toutes_les_bandes_EME_sont_couvertes():
    for b in BANDES:
        assert b in bp.EME_ACTIVITE, b
        assert bp.centre_rf_mhz(b) is not None


def test_la_RF_est_dans_la_bande():
    # La RF d'activité tombe dans ±20 % de la fréquence nominale de la bande.
    for b in BANDES:
        rf = bp.centre_rf_mhz(b)
        nominal = float(b)
        assert 0.8 * nominal <= rf <= 1.2 * nominal, (b, rf)


def test_au_dessus_de_1296_c_est_du_transverter():
    for b in ['2320', '3400', '5760', '10368', '24048', '47088']:
        assert bp.est_transverter(b) is True, b
    assert bp.est_transverter('144') is False
    assert bp.est_transverter('432') is False


def test_bande_inconnue_rend_None():
    assert bp.centre_rf_mhz('7') is None
    assert bp.est_transverter('7') is False
```

- [ ] **Step 3 : Lancer, vérifier l'échec**

Run: `python -m pytest concours/tests/test_eme_bandplan.py -v`
Expected: FAIL — module absent.

- [ ] **Step 4 : Implémenter le module avec les valeurs SOURCÉES au step 1**

Créer `concours/logx_eme_bandplan.py` (remplacer chaque `rf_mhz` par la valeur sourcée ; l'exemple ci-dessous porte les repères NON confirmés de F4GLD — à corriger depuis l'IARU R1) :

```python
# -*- coding: utf-8 -*-
"""Fréquences d'activité EME par bande.

SOURCE : plan de bandes IARU Région 1 — <URL EXACTE À CITER au step 1>.
Le Doppler EME se calcule sur la fréquence RF RÉELLE. Au-dessus de 1296 MHz,
l'usage passe par transverter : le dial CAT est alors une FI, pas la RF —
d'où le drapeau `transverter`, signalé au cockpit.
"""

EME_ACTIVITE = {
    '50':    {'rf_mhz': 50.190,    'transverter': False, 'label': '6 m'},     # VALEUR À SOURCER
    '144':   {'rf_mhz': 144.120,   'transverter': False, 'label': '2 m'},     # VALEUR À SOURCER
    '432':   {'rf_mhz': 432.065,   'transverter': False, 'label': '70 cm'},   # VALEUR À SOURCER
    '1296':  {'rf_mhz': 1296.065,  'transverter': False, 'label': '23 cm'},   # VALEUR À SOURCER
    '2320':  {'rf_mhz': 2320.065,  'transverter': True,  'label': '13 cm'},   # VALEUR À SOURCER
    '3400':  {'rf_mhz': 3400.100,  'transverter': True,  'label': '9 cm'},    # VALEUR À SOURCER
    '5760':  {'rf_mhz': 5760.100,  'transverter': True,  'label': '6 cm'},    # VALEUR À SOURCER
    '10368': {'rf_mhz': 10368.100, 'transverter': True,  'label': '3 cm'},    # VALEUR À SOURCER
    '24048': {'rf_mhz': 24048.100, 'transverter': True,  'label': '1,2 cm'},  # VALEUR À SOURCER
    '47088': {'rf_mhz': 47088.100, 'transverter': True,  'label': '6 mm'},    # VALEUR À SOURCER
}


def centre_rf_mhz(band):
    e = EME_ACTIVITE.get(str(band))
    return e['rf_mhz'] if e else None


def est_transverter(band):
    e = EME_ACTIVITE.get(str(band))
    return bool(e['transverter']) if e else False
```

- [ ] **Step 5 : Lancer, vérifier que ça PASSE**

Run: `python -m pytest concours/tests/test_eme_bandplan.py -v`
Expected: PASS.

- [ ] **Step 6 : Commit**

```bash
git add concours/logx_eme_bandplan.py concours/tests/test_eme_bandplan.py
git commit -m "feat(eme): plan de bandes EME (frequences d'activite IARU R1, drapeau transverter)"
```

---

### Task 5 : Agrégateur `_eme_cockpit_dict()` + endpoints `/eme/cockpit` et `/moon/track/*`

**Files:**
- Modify: `concours/logx_http.py` (fonction `_eme_cockpit_dict` près de `_wsjtx_state_dict` l.2062 ; routes GET près de `/data/eme_moon` l.3774 et `/rotor/state` l.5327 ; route POST près de `/rotor/point` l.7471)
- Test: `concours/tests/test_eme_cockpit.py`

**Interfaces:**
- Consumes : `logx_eme.moon_position/doppler_shift_hz/moon_rise_set/common_window` ; `logx_eme_bandplan.centre_rf_mhz/est_transverter` ; `logx_wsjtx.eme_decodes` ; `logx_moon_track.etat_suivi_lune` ; `_wsjtx_state_dict(cfg_snap)` (état rig/WSJT-X existant) ; `locator_to_latlon`.
- Produces : `_eme_cockpit_dict(cfg_snap, band, dx_locator='') -> dict` avec clés `band, rf_mhz, transverter, moon{az,alt,distance_km,phase_pct,visible}, doppler_hz, rise_utc, set_utc, window[], decodes[], track{}, rig{dial_mhz,mode,connected}`. Endpoints : `GET /eme/cockpit?band=&dx_locator=`, `POST /moon/track/start`, `POST /moon/track/stop`, `GET /moon/track/state`.

- [ ] **Step 1 : Écrire le test de l'agrégateur (échouera : fonction absente)**

Créer `concours/tests/test_eme_cockpit.py` :

```python
# -*- coding: utf-8 -*-
"""L'agrégat /eme/cockpit compose les briques existantes, sans logique neuve."""
import json
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as H   # noqa: E402

CFG = {'locator': 'JN15XC', 'altitude': 100}


def _mock(monkeypatch):
    monkeypatch.setattr(H, '_wsjtx_state_dict',
                        lambda cfg: {'dial_mhz': 432.07, 'mode': 'Q65', 'connected': True})
    import logx_eme as eme
    import logx_wsjtx as w
    import logx_moon_track as mt
    monkeypatch.setattr(eme, 'moon_position', lambda *a, **k: {
        'available': True, 'az': 187.3, 'alt': 34.0, 'visible': True,
        'distance_km': 384210.0, 'phase_pct': 61.0})
    monkeypatch.setattr(eme, 'doppler_shift_hz', lambda *a, **k: {
        'available': True, 'doppler_hz': -412.0, 'range_rate_ms': 143.0})
    monkeypatch.setattr(eme, 'moon_rise_set', lambda *a, **k: {
        'available': True, 'rise_utc': '2026/9/1 20:10:00', 'set_utc': '2026/9/2 05:40:00'})
    monkeypatch.setattr(w, 'eme_decodes', lambda max_age=300: [
        {'call': 'DL7APV', 'mode': 'Q65', 'freq_mhz': 432.071, 'snr': -24,
         'message': 'CQ DL7APV JO62', 'band': '432', 'last_seen': 0}])
    monkeypatch.setattr(mt, 'etat_suivi_lune', lambda: {
        'actif': True, 'phase': 'suivi', 'cible_az': 187.0, 'cible_el': 34.0,
        'rotor_az': 186.0, 'rotor_el': 33.0, 'visible': True, 'note': '', 'envois': 3})


def test_l_agregat_compose_toutes_les_briques(monkeypatch):
    _mock(monkeypatch)
    d = H._eme_cockpit_dict(CFG, '432')
    assert d['band'] == '432'
    assert d['rf_mhz'] == 432.065           # depuis le plan de bandes
    assert d['transverter'] is False
    assert d['moon']['az'] == 187.3 and d['moon']['visible'] is True
    assert d['doppler_hz'] == -412.0
    assert d['rise_utc'].endswith('20:10:00')
    assert d['decodes'][0]['call'] == 'DL7APV'
    assert d['track']['phase'] == 'suivi'
    assert d['rig']['mode'] == 'Q65'
    json.dumps(d, allow_nan=False)           # JSON-safe


def test_le_doppler_est_calcule_sur_la_RF_pas_le_dial(monkeypatch):
    _mock(monkeypatch)
    vus = {}
    import logx_eme as eme
    monkeypatch.setattr(eme, 'doppler_shift_hz',
                        lambda lat, lon, freq_mhz, *a, **k: vus.setdefault('f', freq_mhz)
                        or {'available': True, 'doppler_hz': 0.0, 'range_rate_ms': 0.0})
    H._eme_cockpit_dict(CFG, '2320')
    assert vus['f'] == 2320.065              # RF du plan, pas un dial/FI


def test_locator_absent_ne_plante_pas(monkeypatch):
    _mock(monkeypatch)
    d = H._eme_cockpit_dict({'locator': ''}, '144')
    assert d['moon'] is None or d['moon'] == {} or 'error' in d
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `python -m pytest concours/tests/test_eme_cockpit.py -v`
Expected: FAIL — `_eme_cockpit_dict` absent.

- [ ] **Step 3 : Implémenter `_eme_cockpit_dict`**

Ajouter dans `concours/logx_http.py` juste après `_wsjtx_state_dict` (l.2062) :

```python
def _eme_cockpit_dict(cfg_snap, band, dx_locator=''):
    """Agrégat du cockpit EME : compose les briques EXISTANTES (position Lune,
    Doppler sur la RF, décodages Q65/JT65, état du suivi lunaire, état rig). Une
    seule requête à poller côté page. AUCUNE logique métier neuve ici."""
    import logx_eme as eme
    import logx_eme_bandplan as bandplan
    import logx_wsjtx as wsjtx
    import logx_moon_track as moon_track
    from logx_utils import locator_to_latlon

    band = str(band or '144')
    rf_mhz = bandplan.centre_rf_mhz(band)
    lat, lon = locator_to_latlon((cfg_snap or {}).get('locator', '') or '')
    alt_m = (cfg_snap or {}).get('altitude', 0) or 0

    moon = doppler = None
    rise = setg = None
    window = []
    if lat is not None:
        m = eme.moon_position(lat, lon, alt_m)
        moon = m if m.get('available') else {'error': m.get('error', '')}
        if rf_mhz:
            dp = eme.doppler_shift_hz(lat, lon, rf_mhz, alt_m)
            doppler = dp.get('doppler_hz') if dp.get('available') else None
        rs = eme.moon_rise_set(lat, lon, alt_m)
        if rs.get('available'):
            rise, setg = rs.get('rise_utc'), rs.get('set_utc')
        dxlat, dxlon = locator_to_latlon((dx_locator or '').strip())
        if dxlat is not None:
            cw = eme.common_window(lat, lon, dxlat, dxlon)
            window = cw.get('windows', []) if cw.get('available') else []

    return {
        'band': band,
        'rf_mhz': rf_mhz,
        'transverter': bandplan.est_transverter(band),
        'moon': moon,
        'doppler_hz': doppler,
        'rise_utc': rise,
        'set_utc': setg,
        'window': window,
        'decodes': wsjtx.eme_decodes(),
        'track': moon_track.etat_suivi_lune(),
        'rig': _wsjtx_state_dict(cfg_snap),
    }
```

- [ ] **Step 4 : Lancer, vérifier que ça PASSE**

Run: `python -m pytest concours/tests/test_eme_cockpit.py -v`
Expected: PASS.

- [ ] **Step 5 : Câbler les routes (GET `/eme/cockpit`, `/moon/track/state` ; POST `/moon/track/start|stop`)**

Dans `do_GET` de `concours/logx_http.py`, près de `if path == '/data/eme_moon':` (l.3774) :

```python
        if path == '/eme/cockpit':
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            band = (q.get('band', ['144'])[0])
            dxloc = (q.get('dx_locator', [''])[0])
            self._json(_eme_cockpit_dict(self._cfg_snapshot(), band, dxloc))
            return
        if path == '/moon/track/state':
            import logx_moon_track as moon_track
            self._json(moon_track.etat_suivi_lune())
            return
```

Dans `do_POST`, près de `if self.path in ('/rotor/point', '/rotor/stop'):` (l.7471) :

```python
        if self.path in ('/moon/track/start', '/moon/track/stop'):
            import logx_moon_track as moon_track
            if self.path == '/moon/track/start':
                ok, msg = moon_track.demarrer_suivi_lune(self._cfg_snapshot())
            else:
                ok, msg = moon_track.arreter_suivi_lune()
            self._json({'ok': ok, 'error': ('' if ok else msg), 'message': msg},
                       200 if ok else 400)
            return
```

- [ ] **Step 6 : Test de fumée du serveur (import + routes présentes)**

Run: `python -c "import sys; sys.path.insert(0,'concours'); import logx_http; assert hasattr(logx_http,'_eme_cockpit_dict'); print('OK')"`
Expected: `OK` (aucune erreur d'import — vérifie que les ajouts ne cassent pas le module de 9000 lignes).

Puis vérifier que la CI schema/harnais mock passe : `python -m pytest concours/tests/test_eme_cockpit.py concours/tests/test_moon_track.py concours/tests/test_eme_decodes.py -v`.

- [ ] **Step 7 : Contre-épreuve par mutation**

Dans `_eme_cockpit_dict`, `eme.doppler_shift_hz(lat, lon, rf_mhz, alt_m)` → `...(lat, lon, float(band), alt_m)` (dial au lieu de RF) : `test_le_doppler_est_calcule_sur_la_RF_pas_le_dial` doit rougir. Restaurer, vérifier md5.

- [ ] **Step 8 : Commit**

```bash
git add concours/logx_http.py concours/tests/test_eme_cockpit.py
git commit -m "feat(eme): agregat /eme/cockpit + endpoints /moon/track/start|stop|state"
```

---

### Task 6 : `logx_eme.html` — page cockpit EME

**Files:**
- Create: `concours/logx_eme.html`
- Test: `concours/tests/test_eme_page.py` (py_mini_racer, logique JS pure)

**Interfaces:**
- Consumes : endpoint `GET /eme/cockpit?band=&dx_locator=`, `POST /moon/track/start|stop`. Fonction JS pure testée : `formatDecode(d) -> string` et `dopplerLabel(hz) -> string`.
- Produces : page statique servie par `do_GET` static (`logx_http.py:8810`), aucune inscription à modifier.

- [ ] **Step 1 : Écrire la page (gabarit standard + panneaux + polling)**

Créer `concours/logx_eme.html`. Reprendre le `<head>` d'une page existante (`logx_propagation.html:1-50`) : `<meta charset>`, viewport, `<title>LogX AI — EME</title>`, `<link rel="icon" href="/logx_icon.svg">`, **`<link rel="stylesheet" href="logx_theme.css">`**, `<script src="logx_theme_guard.js"></script>`. Corps : `<header>` + `<nav class="app-nav">` (copié d'une page voisine, l'entrée EME sera ajoutée en Task 7), panneaux `LUNE`, `RIG`, `DÉCODAGES Q65/JT65`, `SUIVI LUNE`, sélecteur de bande. En pied : `<script src="logx_statusbar.js">`, `<script src="logx_i18n.js">`. Utiliser les variables de thème `var(--bg/--bg2/--text/--accent/--green/--red/--muted)`. Densité : conteneurs scrollables en `align-items:flex-start`. **Toute chaîne visible via `Tf('...')`.** Aucun emoji d'icône neuf (SVG monochrome `stroke="currentColor"` si besoin ; les points d'état 🟢🔴 deviennent des `<span>` ronds `var(--green)`/`var(--red)`). Vocabulaire **portable/expédition**.

Fonctions JS pures à isoler (pour le test) dans un `<script>` en tête, définies sur `window` :

```html
<script>
// Fonctions pures, testables hors DOM (py_mini_racer).
function dopplerLabel(hz) {
  if (hz === null || hz === undefined) return '—';
  var s = hz > 0 ? '+' : '';
  return s + Math.round(hz) + ' Hz';
}
function formatDecode(d) {
  // "DL7APV  -24 dB  Q65  432.071" — compact, une ligne par station entendue.
  return [d.call, (d.snr >= 0 ? '+' : '') + d.snr + ' dB', d.mode,
          (d.freq_mhz || '').toString()].join('  ');
}
if (typeof window !== 'undefined') { window.dopplerLabel = dopplerLabel; window.formatDecode = formatDecode; }
</script>
```

Le polling : `setInterval` toutes les 3 s → `fetch('/eme/cockpit?band='+bande+'&dx_locator='+dx)` → remplir les panneaux. Boutons SUIVI : `fetch('/moon/track/start', {method:'POST'})` / `/moon/track/stop`, afficher `message` en cas de refus (Lune sous l'horizon, rotor injoignable…). Repli du panneau décodages si `rig.connected` est faux : afficher la marche à suivre (WSJT-X → Réglages → Rapports → serveur UDP = ce PC, port 2237, mode Q65/JT65). Bandeau « dial CAT = FI » si `transverter` est vrai.

- [ ] **Step 2 : Écrire le test py_mini_racer (échouera : page/fonctions absentes)**

Créer `concours/tests/test_eme_page.py` (calquer l'entête sur un test py_mini_racer existant du dépôt, ex. un `test_*_split.py` qui charge un `<script>`) :

```python
# -*- coding: utf-8 -*-
"""Fonctions JS pures du cockpit EME (hors DOM)."""
import os
import re
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(CONCOURS, 'logx_eme.html')


def _extraire_script(html, marqueur):
    # Le premier <script> contenant le marqueur (fonctions pures).
    for m in re.finditer(r'<script>(.*?)</script>', html, re.S):
        if marqueur in m.group(1):
            return m.group(1)
    raise AssertionError('script pur introuvable')


@pytest.fixture(scope='module')
def ctx():
    from py_mini_racer import py_mini_racer
    with open(PAGE, encoding='utf-8') as f:
        html = f.read()
    js = _extraire_script(html, 'function dopplerLabel')
    c = py_mini_racer.MiniRacer()
    c.eval('var window = {};')
    c.eval(js)
    return c


def test_dopplerLabel_signe_et_arrondi(ctx):
    assert ctx.eval('dopplerLabel(-412.4)') == '-412 Hz'
    assert ctx.eval('dopplerLabel(37.8)') == '+38 Hz'
    assert ctx.eval('dopplerLabel(null)') == '—'


def test_formatDecode_ligne_compacte(ctx):
    ligne = ctx.eval("formatDecode({call:'DL7APV', snr:-24, mode:'Q65', freq_mhz:432.071})")
    assert 'DL7APV' in ligne and '-24 dB' in ligne and 'Q65' in ligne


def test_la_page_charge_le_theme_et_le_garde(ctx):
    with open(PAGE, encoding='utf-8') as f:
        html = f.read()
    assert 'logx_theme.css' in html
    assert 'logx_theme_guard.js' in html
    # Vocabulaire : pas d'"activation"/"activateur" en texte visible.
    assert 'activateur' not in html.lower()
```

- [ ] **Step 3 : Lancer, vérifier l'échec puis la réussite**

Run: `python -m pytest concours/tests/test_eme_page.py -v`
Expected: d'abord FAIL (page absente), puis PASS une fois `logx_eme.html` écrit.

- [ ] **Step 4 : Contre-épreuve par mutation**

Dans `logx_eme.html`, `hz > 0 ? '+' : ''` → `hz > 0 ? '' : ''` : `test_dopplerLabel_signe_et_arrondi` doit rougir (perd le `+`). Restaurer, vérifier md5.

- [ ] **Step 5 : Vérifier l'absence de chaîne brute (i18n) et de `<svg>` non dimensionné**

Run: `python -m pytest concours/tests/test_i18n_dialogues.py -v` (doit rester vert). Recenser les `<svg>` de la page : chacun doit avoir `width=`/`height=` ou une règle CSS scopée (piège documenté dans CLAUDE.md).

- [ ] **Step 6 : Commit**

```bash
git add concours/logx_eme.html concours/tests/test_eme_page.py
git commit -m "feat(eme): page cockpit logx_eme.html (Lune, Doppler, decodages Q65/JT65, suivi)"
```

---

### Task 7 : Entrée de navigation « EME » dans le menu Outils

**Files:**
- Modify: toutes les pages portant `<nav class="app-nav">` (menu `#navToolsMenu`) — insertion identique par script
- Test: `concours/tests/test_nav_eme.py`

**Interfaces:**
- Consumes : le bloc `#navToolsMenu` existant (mêmes entrées sur chaque page : SANTÉ STATION, PLAN DE SESSION, MODE NUMÉRIQUE…).
- Produces : un lien `<a href="logx_eme.html">…EME…</a>` dans le menu Outils de chaque page qui le porte.

- [ ] **Step 1 : Recenser les pages cibles**

Run: `grep -rl "navToolsMenu" concours/*.html`
Noter la liste exacte. Repérer sur UNE page le motif précis d'une entrée du menu Outils (ex. l'entrée WEBSDR) pour calquer l'insertion.

- [ ] **Step 2 : Écrire le test de cohérence (échouera : entrée absente)**

Créer `concours/tests/test_nav_eme.py` :

```python
# -*- coding: utf-8 -*-
"""L'entrée EME est présente dans le menu Outils de TOUTES les pages qui le portent."""
import glob
import os

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pages_avec_menu_outils():
    out = []
    for p in glob.glob(os.path.join(CONCOURS, '*.html')):
        with open(p, encoding='utf-8') as f:
            if 'navToolsMenu' in f.read():
                out.append(p)
    return out


def test_toutes_les_pages_a_menu_outils_ont_l_entree_EME():
    manquantes = []
    for p in _pages_avec_menu_outils():
        with open(p, encoding='utf-8') as f:
            if 'logx_eme.html' not in f.read():
                manquantes.append(os.path.basename(p))
    assert not manquantes, 'pages sans entrée EME : %s' % manquantes


def test_il_y_a_bien_des_pages_a_menu_outils():
    # Garde-fou : si le sélecteur ne trouve rien, le test ci-dessus est vacant.
    assert _pages_avec_menu_outils()
```

- [ ] **Step 3 : Lancer, vérifier l'échec**

Run: `python -m pytest concours/tests/test_nav_eme.py -v`
Expected: `test_toutes_les_pages...` FAIL (entrée absente partout).

- [ ] **Step 4 : Insérer l'entrée EME par script (substitution exacte, un passage)**

Écrire un script Python jetable qui, pour chaque page listée au step 1, insère l'entrée EME juste après une entrée repère stable du menu Outils (ex. après l'entrée WEBSDR). Libellé « EME » + icône SVG monochrome `stroke="currentColor"` (dimensionnée `width=15 height=15`), dans le même moule que les entrées voisines. Insertion IDEMPOTENTE (ne pas ré-insérer si `logx_eme.html` déjà présent). Ne PAS utiliser d'agents parallèles (fichiers partagés) — un seul passage séquentiel.

- [ ] **Step 5 : Lancer, vérifier que tout PASSE**

Run: `python -m pytest concours/tests/test_nav_eme.py -v`
Expected: PASS.

- [ ] **Step 6 : Contre-épreuve**

Retirer l'entrée d'UNE page à la main → `test_toutes_les_pages...` doit rougir en nommant cette page → remettre. (Prouve que le test n'est pas vacant.)

- [ ] **Step 7 : Vérifier la non-régression de la navigation existante**

Run: `python -m pytest concours/tests/ -k "nav or statusbar" -v` (les tests de nav existants doivent rester verts).

- [ ] **Step 8 : Commit**

```bash
git add concours/*.html concours/tests/test_nav_eme.py
git commit -m "feat(eme): entree EME dans le menu Outils de toutes les pages"
```

---

## Self-Review

**Spec coverage :**
- Page cockpit EME → Task 6. Suivi lunaire rotor → Tasks 1-2. Relais Q65/JT65 → Task 3. Doppler par bande 144→47 GHz + transverter/FI → Task 4 + Task 5. Agrégat un-seul-poll → Task 5. Entrée nav → Task 7. Pas de Skyfield / pas de SQL → aucune tâche n'en ajoute (vérifié). Carnet unique → aucun `eme_*` (les QSO EME restent auto-loggés par le pont existant, hors périmètre de code neuf). ✅ couvert.
- Gestion d'erreurs (spec §4) : horizon → Task 2 ; rotor 3 échecs → Task 1 ; ephem absent → Task 2 ; WSJT-X non connecté → Task 6 (repli page) ; NaN rotor → Tasks 1-2 ; transverter FI → Tasks 4-6. ✅
- Tests non-testables déclarés (spec §5) : rotor/Lune simulés partout ; validation station notée, jamais annoncée traitée. ✅

**Placeholder scan :** le seul marqueur restant est `VALEUR À SOURCER` sur les fréquences EME (Task 4) — VOLONTAIRE (règle projet : sourcer, pas inventer), avec l'étape de sourcing explicite en Task 4 Step 1. Aucun autre TODO/TBD.

**Type consistency :** `etat_suivi_lune()`, `_boucle_suivi_lune(...)`, `demarrer_suivi_lune(cfg)`, `arreter_suivi_lune()`, `eme_decodes(max_age)`, `centre_rf_mhz(band)`, `est_transverter(band)`, `_eme_cockpit_dict(cfg_snap, band, dx_locator)` — noms et signatures identiques entre définition (Tasks 1-5) et consommation (Task 5-6). `moon_position` lu via clé `alt` partout (jamais `el`). ✅

## Note de séquencement

Tasks 1→2→3→4 sont indépendantes deux à deux SAUF que Task 5 consomme 1-4 ; Task 6 consomme 5 ; Task 7 consomme 6 (la page doit exister avant d'ajouter son lien). Ordre d'exécution : 1, 2, 3, 4, 5, 6, 7.
