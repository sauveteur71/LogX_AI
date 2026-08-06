# -*- coding: utf-8 -*-
"""Télémétrie d'usage anonyme — un heartbeat QUOTIDIEN minimal (identifiant
d'installation aléatoire, version, OS) pour mesurer l'usage réel du
logiciel. JAMAIS de callsign, de QSO, de chemin local ou de toute autre
donnée identifiante — voir build_payload() ci-dessous pour la liste EXACTE
et exhaustive de ce qui part.

Décision F4GLD (06/08/2026) : activée par défaut, désactivable en un clic
dans CONFIG (opt-out, contrairement à tous les autres toggles réseau de ce
projet — scoreboard/ClubLog Live/RBN — qui sont désactivés par défaut).
Conforme à la règle du PRD (docs/LogX_AI_PRD.md:324) « pas de télémétrie
cachée » : le toggle est visible en CONFIG, ce module documente en clair
ce qui est envoyé, et — aucune infrastructure serveur n'existe encore côté
projet pour recevoir ce heartbeat — `telemetry_endpoint` est VIDE par
défaut : send_heartbeat() ne tente alors AUCUNE requête réseau, à brancher
dès qu'une destination existera."""
import json
import os
import platform
import uuid

from logx_utils import post_url_json, utcnow
from logx_version import APP_VERSION

_STAMP_FILE = 'telemetry_sync.json'
_ID_FILE = 'telemetry_id.json'
_INTERVAL_S = 24 * 3600


def telemetry_settings(cfg):
    """Contrairement aux autres toggles réseau de ce projet (absence de champ
    == désactivé), celui-ci est ACTIVÉ par défaut : `cfg.get(..., True)`
    couvre les 3 cas — champ absent (config antérieure à cette fonctionnalité,
    ou jamais ouvert CONFIG) -> True -> activé ; sauvegardé `True` -> pareil ;
    sauvegardé `False` (l'opérateur a explicitement coupé le toggle) ->
    str(False) == 'False', absent de la liste acceptée -> désactivé."""
    cfg = cfg or {}
    return {
        'enabled': str(cfg.get('telemetry_enabled', True)) in ('1', 'true', 'True', 'on'),
        'endpoint': (cfg.get('telemetry_endpoint') or '').strip(),
    }


def _install_id():
    """Jeton ALÉATOIRE persistant, jamais dérivé du callsign ni de rien
    d'identifiant — sert seulement à compter des postes distincts, jamais à
    savoir qui ils sont. Généré une fois, conservé localement."""
    try:
        if os.path.exists(_ID_FILE):
            with open(_ID_FILE, encoding='utf-8') as f:
                data = json.load(f) or {}
            if data.get('id'):
                return data['id']
    except Exception:
        pass
    new_id = uuid.uuid4().hex
    try:
        with open(_ID_FILE, 'w', encoding='utf-8') as f:
            json.dump({'id': new_id}, f)
    except Exception:
        pass
    return new_id


def build_payload():
    """Le contenu ENVOYÉ, dans son intégralité — ces 3 clés sont les SEULES
    que ce module construit, jamais rien d'autre : un jeton aléatoire
    d'installation (pas un callsign), la version du logiciel, le nom du
    système d'exploitation (`platform.system()` — 'Windows'/'Linux'/'Darwin',
    jamais `platform.node()`/hostname, jamais `release()`/version détaillée
    du système qui pourrait aider à identifier un poste précis)."""
    return {
        'install_id': _install_id(),
        'version': APP_VERSION,
        'os': platform.system(),
    }


def status():
    last = {}
    try:
        if os.path.exists(_STAMP_FILE):
            with open(_STAMP_FILE, encoding='utf-8') as f:
                last = json.load(f) or {}
    except Exception:
        pass
    return {'last': last}


def _stamp():
    try:
        tmp = _STAMP_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'last': utcnow().strftime('%Y-%m-%d %H:%M')}, f)
        os.replace(tmp, _STAMP_FILE)
    except Exception:
        pass


def heartbeat_due(last_stamp, now):
    """Fonction PURE (testable sans horloge réelle) : True si aucun envoi
    encore fait, ou si le dernier envoi remonte à >= _INTERVAL_S (24h, avec
    une petite marge pour absorber le jitter de la boucle de fond qui
    vérifie toutes les 60s comme les autres tâches périodiques de
    logx_serveur.py)."""
    if not last_stamp:
        return True
    try:
        import datetime as _dt
        age = (now - _dt.datetime.strptime(last_stamp, '%Y-%m-%d %H:%M')).total_seconds()
        return age >= _INTERVAL_S - 300
    except Exception:
        return True


def send_heartbeat(cfg):
    """Envoie le heartbeat si activé ET qu'une destination est configurée.
    Sans destination (valeur par défaut — aucune infrastructure serveur
    n'existe encore pour la recevoir), ne tente AUCUNE requête réseau :
    `skipped` distingue ce cas d'un vrai échec réseau."""
    s = telemetry_settings(cfg)
    if not s['enabled']:
        return {'ok': False, 'error': 'Télémétrie désactivée (CONFIG)'}
    if not s['endpoint']:
        return {'ok': False, 'error': 'Aucune destination configurée', 'skipped': True}
    status_code, resp = post_url_json(s['endpoint'], build_payload(), timeout=10,
                                      headers={'User-Agent': 'LogXAI'})
    if status_code is None:
        return {'ok': False, 'error': 'Destination injoignable'}
    if status_code >= 400:
        return {'ok': False, 'error': f'Destination a répondu HTTP {status_code} : '
                                      f'{(resp or "")[:200].strip()}'}
    _stamp()
    return {'ok': True}
