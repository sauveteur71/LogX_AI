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
from collections import deque
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

# Verrou TX SERVEUR : posé par « Stop TX » (arrêt d'urgence), il bloque TOUTE
# nouvelle autorisation jusqu'à un réarmement HUMAIN explicite (unlock_tx).
# C'est le 'ptt_locked' que authorize_transmission relit avant le PTT.
_tx_locked = False

# Journal d'audit d'émission EN MÉMOIRE, borné et horodaté UTC — même parti-pris
# que logx_cw_journal (un journal d'émission n'a pas à survivre au redémarrage
# ni à grossir sans fin). Consultable via GET /tx/audit.
_AUDIT_MAX = 200
_audit = deque(maxlen=_AUDIT_MAX)


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
    # Source voix pour une émission PHONIE : 'wav' (slot pré-enregistré),
    # 'tts' (synthèse du texte) ou 'auto' (TTS si dispo, sinon WAV). Sans objet
    # pour le CW. Le « selon ce que je dispose » (IA cloud → Piper → voix locale)
    # est géré dans logx_voicekeyer.synthesize_to_wav.
    voice_source: str = 'auto'
    created_at: datetime.datetime = field(default_factory=_now)

    def is_valid(self, now=None) -> bool:
        """Non utilisé, non annulé (Stop TX), non expiré."""
        now = now or _now()
        return not self.used and not self.cancelled and now < self.expires_at


def create_tx_consent(operator_callsign, radio_id, frequency_hz, mode, power_w,
                      message, ptt_method='CAT', voice_source='auto', now=None) -> TxConsent:
    """Crée un consentement à partir de ce que l'humain vient de VOIR et de
    valider (aperçu de l'émission). `now` injectable pour les tests."""
    now = now or _now()
    return TxConsent(
        token=str(uuid4()), operator_callsign=str(operator_callsign or ''),
        radio_id=str(radio_id or ''), frequency_hz=int(frequency_hz),
        mode=str(mode or ''), power_w=float(power_w), message=str(message or ''),
        expires_at=now + datetime.timedelta(seconds=CONSENT_TTL_S),
        ptt_method=str(ptt_method or 'CAT'),
        voice_source=str(voice_source or 'auto'), created_at=now)


def voice_source_effectif(source, tts_dispo) -> str:
    """Résout la source voix EFFECTIVE d'une émission phonie (offline-first) :
      - 'wav'  -> 'wav' toujours (l'opérateur veut SA voix enregistrée) ;
      - 'tts'  -> 'tts' si un moteur de synthèse existe, sinon repli 'wav' ;
      - 'auto'/absent -> 'tts' si dispo, sinon 'wav'.
    `tts_dispo` : au moins un moteur TTS utilisable (IA cloud activée, Piper
    local, ou voix système) — calculé côté serveur depuis la config voice keyer.
    Le CHOIX du moteur parmi ceux disponibles est fait par synthesize_to_wav."""
    src = str(source or 'auto').lower()
    if src == 'wav':
        return 'wav'
    # 'tts' ou 'auto' : synthèse si possible, sinon repli hors-ligne sur le WAV.
    return 'tts' if tts_dispo else 'wav'


def register(consent) -> None:
    """Enregistre un consentement en attente (pour que Stop TX puisse l'annuler)."""
    with _lock:
        _consents[consent.token] = consent


def get(token):
    with _lock:
        return _consents.get(token)


def stop_tx() -> int:
    """« Stop TX » : ANNULE tous les consentements en attente, vide le registre
    ET pose le verrou TX serveur (aucune nouvelle autorisation avant un
    réarmement humain). Retourne le nombre annulé. Le côté appelant DOIT en plus
    couper le PTT matériel (cat.set_ptt(cfg, False))."""
    global _tx_locked
    with _lock:
        n = len(_consents)
        for c in _consents.values():
            c.cancelled = True
        _consents.clear()
        _tx_locked = True
    journal_audit({'event': 'TX_STOP', 'cancelled': n, 'human_action': 'STOP_TX'})
    return n


def lock_tx() -> None:
    """Pose le verrou TX serveur (bloque toute autorisation)."""
    global _tx_locked
    with _lock:
        _tx_locked = True


def unlock_tx() -> None:
    """Lève le verrou TX serveur — RÉARMEMENT HUMAIN explicite, jamais automatique."""
    global _tx_locked
    with _lock:
        _tx_locked = False


def is_tx_locked() -> bool:
    with _lock:
        return _tx_locked


def radio_state_from_cat(cat_state, consent, locked=None) -> dict:
    """Traduit l'état CAT RÉEL (cat.get_state : freq_hz/mode/ok/enabled) vers le
    dict que authorize_transmission relit juste avant le PTT.

    Décisions documentées (contraintes matérielles réelles) :
      - `cat_connected` : le CAT natif répond ET est activé (ok & enabled).
      - `frequency_hz`, `mode` : relus du poste, RÉELLEMENT re-vérifiés.
      - `power_w` : le CAT natif NE LIT PAS la puissance TX sur la plupart des
        transceivers — on reporte donc la valeur que l'humain a validée
        (impossible de détecter un changement de puissance par CAT ; limite
        assumée, tracée ici). Les autres contrôles restent stricts.
      - `ptt_locked` : verrou TX serveur (Stop TX). Si `locked` n'est pas fourni,
        on lit l'état courant du module.
    """
    if locked is None:
        locked = is_tx_locked()
    cat_state = cat_state or {}
    return {
        'cat_connected': bool(cat_state.get('ok') and cat_state.get('enabled')),
        'frequency_hz': cat_state.get('freq_hz'),
        'mode': cat_state.get('mode'),
        'power_w': consent.power_w,
        'ptt_locked': bool(locked),
    }


def journal_audit(entry) -> None:
    """Ajoute une entrée au journal d'audit d'émission. Horodate en UTC si absent.
    Ne lève JAMAIS (un défaut de journalisation ne doit pas casser une émission)."""
    try:
        e = dict(entry or {})
        e.setdefault('timestamp_utc', _now().strftime('%Y-%m-%dT%H:%M:%SZ'))
        _audit.append(e)
    except Exception:
        pass


def journal_copilote_emission(details) -> dict:
    """Grave une émission COPILOTE (FT8, chemin CLIENT) dans le journal d'audit.

    Les modes data (FT8) émettent CÔTÉ CLIENT (envoyerMessage) et ne passent PAS
    par authorize_transmission : sans cette trace, une émission automatique/
    copilote ne laisserait AUCUNE trace serveur, ce qui violerait le principe
    verrouillé « toute émission traçable ». Le client POSTe donc /tx/trace au
    moment EXACT du déclenchement (ÉMETTRE humain, ou expiration du délai sans
    annulation au niveau copilote_auto). `declencheur` distingue ces deux cas
    ('copilote' = confirmation manuelle, 'copilote_auto' = délai écoulé). Ne lève
    JAMAIS (une trace ratée ne doit pas casser une émission). Retourne l'entrée."""
    d = dict(details or {})
    decl = str(d.get('declencheur') or 'copilote')
    entry = {
        'event': 'TX_COPILOTE_EMISSION',
        'timestamp_utc': _now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'operator_callsign': str(d.get('operator_callsign') or ''),
        'radio_id': str(d.get('radio_id') or ''),        # DX visé, jamais l'humain
        'frequency_hz': d.get('frequency_hz'),
        'mode': str(d.get('mode') or ''),
        'message': str(d.get('message') or ''),
        'declencheur': decl,
        # Traçabilité : au niveau copilote_auto l'IA a déclenché après un délai ;
        # au niveau copilote c'est le geste ÉMETTRE. Dans les DEUX cas un humain a
        # armé le niveau et pouvait annuler (STOP TX) — d'où human_action présent.
        'human_action': 'AUTO_DELAY_ELAPSED' if decl == 'copilote_auto' else 'UI_CONFIRM_TX',
    }
    journal_audit(entry)   # horodate UTC + borne le journal ; ne lève jamais
    return entry


def journal_copilote_qso(details) -> dict:
    """Grave le LIEN entre la chaîne d'émissions copilote et le QSO RÉELLEMENT
    écrit au carnet. Posé au moment de l'écriture confirmée par l'humain (jamais
    de log sans geste) : l'audit montre alors, pour un même indicatif, les
    TX_COPILOTE_EMISSION puis ce TX_COPILOTE_QSO_LOGGED — la boucle
    consentement→émission→QSO est tracée de bout en bout. Ne lève JAMAIS."""
    d = dict(details or {})
    entry = {
        'event': 'TX_COPILOTE_QSO_LOGGED',
        'timestamp_utc': _now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'operator_callsign': str(d.get('operator_callsign') or ''),
        'radio_id': str(d.get('radio_id') or ''),        # DX loggé
        'band': str(d.get('band') or ''),
        'mode': str(d.get('mode') or ''),
        'rst_sent': str(d.get('rst_sent') or ''),
        'rst_rcvd': str(d.get('rst_rcvd') or ''),
        'locator': str(d.get('locator') or ''),
        'declencheur': str(d.get('declencheur') or 'copilote'),
        'human_action': 'QSO_LOGGED',
    }
    journal_audit(entry)
    return entry


def audit_entries(limite=50):
    """Les `limite` dernières entrées d'audit (la plus récente en dernier)."""
    try:
        n = max(0, min(_AUDIT_MAX, int(limite)))
    except (TypeError, ValueError):
        n = 50
    return list(_audit)[-n:]


def vider_audit() -> None:
    """Réinitialise le journal d'audit (tests / effacement éventuel)."""
    _audit.clear()


def emettre_message(famille, message, cw_send, voice_send) -> dict:
    """Envoie le CONTENU préparé selon la famille de mode, une fois le
    consentement ET le garde-fou validés :
      - 'cw'     -> cw_send(message)     (texte au keyer CW — gère son propre PTT)
      - 'phonie' -> voice_send(message)  (slot WAV au voice keyer — gère son PTT)

    `cw_send`/`voice_send` sont les émetteurs RÉELS injectés (wk.envoyer /
    vk.envoyer_message) : ce dispatch reste testable sans matériel. Refuse SANS
    rien émettre (fail-closed) une famille non gérée par « émission unique » ou
    un message vide. Les modes data (FT8/RTTY) sont déjà refusés en amont par le
    garde-fou et n'atteignent jamais ce point."""
    if not str(message or '').strip():
        return {'ok': False, 'error': "Message d'émission vide"}
    if famille == 'cw':
        return cw_send(message)
    if famille == 'phonie':
        return voice_send(message)
    return {'ok': False, 'error': "Mode hors « émission unique » (CW ou phonie)"}


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
