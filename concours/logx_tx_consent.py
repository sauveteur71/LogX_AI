# -*- coding: utf-8 -*-
"""Consentement d'émission « ÉMISSION UNIQUE » — couche d'AUTORISATION HUMAINE
au-dessus du garde-fou mode/bande (logx_tx_guard).

Politique (skill .claude/skills/tx-human-consent) : l'IA PRÉPARE une émission,
l'HUMAIN la déclenche. Un consentement est un jeton UNIQUE, à expiration RAPIDE
(30 s), à USAGE UNIQUE, invalidé au moindre changement radio (fréquence, mode,
puissance), exigeant un CAT confirmé et un PTT non verrouillé, annulable
immédiatement par « Stop TX ». Le contrôle est CÔTÉ BACKEND : juste avant le PTT,
on relit l'état radio RÉEL et on le compare au jeton.

Ce module ne DÉCLENCHE aucune émission — il autorise (ou refuse) et journalise.
Le déclenchement PTT réel reste au chemin appelant, APRÈS authorize_transmission()
ET après le garde-fou logx_tx_guard.tx_autorise().

Portée volontaire : « émission unique » uniquement. La « session limitée »
(FT8 semi-auto) viendra plus tard, après tests approfondis (désactivée par défaut).
"""
import datetime
import threading
from dataclasses import dataclass, field
from uuid import uuid4

_UTC = datetime.timezone.utc

# Durée de vie d'un consentement (secondes). Court exprès : l'humain vient de
# cliquer « Émettre maintenant », l'émission doit suivre immédiatement.
CONSENT_TTL_S = 30

# Registre des consentements EN ATTENTE (token -> TxConsent), protégé par un
# verrou : plusieurs requêtes HTTP peuvent y toucher. « Stop TX » le vide et
# annule tout ce qu'il contenait.
_lock = threading.Lock()
_consents = {}


def _now():
    return datetime.datetime.now(_UTC)


@dataclass
class TxConsent:
    """Autorisation d'UNE émission. Immuable dans ses paramètres radio ; seuls
    `used`/`cancelled` évoluent."""
    token: str
    operator_callsign: str
    radio_id: str
    frequency_hz: int
    mode: str
    power_w: float
    message: str
    expires_at: datetime.datetime
    used: bool = False
    cancelled: bool = False
    ptt_method: str = 'CAT'
    consent_mode: str = 'single_transmission'
    created_at: datetime.datetime = field(default_factory=_now)

    def is_valid(self, now=None) -> bool:
        """Non utilisé, non annulé (Stop TX), non expiré."""
        now = now or _now()
        return not self.used and not self.cancelled and now < self.expires_at


def create_tx_consent(operator_callsign, radio_id, frequency_hz, mode, power_w,
                      message, ptt_method='CAT', now=None) -> TxConsent:
    """Crée un consentement à partir de ce que l'humain vient de VOIR et de
    valider (aperçu de l'émission). `now` injectable pour les tests."""
    now = now or _now()
    return TxConsent(
        token=str(uuid4()), operator_callsign=str(operator_callsign or ''),
        radio_id=str(radio_id or ''), frequency_hz=int(frequency_hz),
        mode=str(mode or ''), power_w=float(power_w), message=str(message or ''),
        expires_at=now + datetime.timedelta(seconds=CONSENT_TTL_S),
        ptt_method=str(ptt_method or 'CAT'), created_at=now)


def register(consent) -> None:
    """Enregistre un consentement en attente (pour que Stop TX puisse l'annuler)."""
    with _lock:
        _consents[consent.token] = consent


def get(token):
    with _lock:
        return _consents.get(token)


def stop_tx() -> int:
    """« Stop TX » : ANNULE tous les consentements en attente et vide le registre.
    Retourne le nombre annulé. À câbler sur le bouton d'arrêt d'urgence global —
    doit AUSSI, côté appelant, couper le PTT et verrouiller les nouvelles
    émissions jusqu'à une nouvelle action humaine."""
    with _lock:
        n = len(_consents)
        for c in _consents.values():
            c.cancelled = True
        _consents.clear()
        return n


def _radio_val(radio_state, cle):
    """Lecture tolérante d'un état radio : dict OU objet à attributs."""
    if isinstance(radio_state, dict):
        return radio_state.get(cle)
    return getattr(radio_state, cle, None)


def authorize_transmission(consent, radio_state, ptt_method=None, now=None) -> dict:
    """Contrôle FINAL juste avant PTT : relit l'état radio RÉEL et le compare au
    jeton. Lève PermissionError / ConnectionError si quoi que ce soit cloche,
    sinon CONSOMME le jeton (usage unique) et retourne l'entrée de JOURNAL D'AUDIT.

    `radio_state` : dict ou objet exposant frequency_hz, mode, power_w,
    ptt_locked, cat_connected — l'état FRAIS du poste, relu du CAT."""
    now = now or _now()
    if not consent.is_valid(now=now):
        raise PermissionError("Autorisation TX absente, utilisée, annulée ou expirée")
    if not _radio_val(radio_state, 'cat_connected'):
        raise ConnectionError("État CAT non confirmé")
    if _radio_val(radio_state, 'ptt_locked'):
        raise PermissionError("PTT verrouillé par sécurité (Stop TX ?)")
    if _radio_val(radio_state, 'frequency_hz') != consent.frequency_hz:
        raise PermissionError("Fréquence TX modifiée depuis l'autorisation")
    if _radio_val(radio_state, 'mode') != consent.mode:
        raise PermissionError("Mode radio modifié depuis l'autorisation")
    if _radio_val(radio_state, 'power_w') != consent.power_w:
        raise PermissionError("Puissance TX modifiée depuis l'autorisation")
    # OK : consommé une fois pour toutes, retiré du registre, journalisé.
    consent.used = True
    with _lock:
        _consents.pop(consent.token, None)
    return _audit_entry(consent, ptt_method or consent.ptt_method, now)


def _audit_entry(consent, ptt_method, now) -> dict:
    """Entrée de journal d'audit (UTC). Le jeton n'est PAS journalisé en clair."""
    return {
        'event': 'TX_AUTHORIZED_AND_EXECUTED',
        'timestamp_utc': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'operator_callsign': consent.operator_callsign,
        'radio_id': consent.radio_id,
        'frequency_hz': consent.frequency_hz,
        'mode': consent.mode,
        'power_w': consent.power_w,
        'message': consent.message,
        'ptt_method': ptt_method,
        'consent_token': 'redacted',
        'consent_mode': consent.consent_mode,
        'human_action': 'UI_CONFIRM_TX',
    }
