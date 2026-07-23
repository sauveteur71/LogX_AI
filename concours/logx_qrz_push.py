# -*- coding: utf-8 -*-
"""Push temps réel vers QRZ Logbook (logbook.qrz.com/api) — distinct de
logx_qrz.py (recherche d'indicatif via l'API XML xmldata.qrz.com, en
LECTURE seule) : ici on ÉCRIT dans le carnet QRZ de l'utilisateur après
chaque QSO validé.

Format vérifié contre la doc officielle QRZ (qrz.com/docs/logbook/
QRZLogbookAPI.html), pas deviné :
  - Endpoint unique : https://logbook.qrz.com/api (POST, un seul champ ADIF
    par appel, pas de batch).
  - Corps application/x-www-form-urlencoded : KEY=<clé>&ACTION=INSERT&
    ADIF=<un seul enregistrement ADIF terminé par <EOR>>.
  - Réponse elle-même application/x-www-form-urlencoded (PAS du JSON) :
    RESULT=OK|FAIL|REPLACE|AUTH, LOGID=<id>, COUNT=<0|1>, REASON=<erreur>.
  - User-Agent obligatoire et identifiable (la doc l'exige explicitement,
    "AppName/Version" recommandé, 128 caractères max) — voir logx_version.
  - Autres ACTION possibles (DELETE via LOGIDS=, FETCH, STATUS) : seul
    STATUS est exposé ici (test_connection), pour vérifier la clé sans
    insérer de QSO factice — INSERT/DELETE/FETCH réels ne sont pas
    nécessaires à l'auto-push demandé.

Clé API QRZ Logbook : nécessite un abonnement QRZ XML actif (Réglages du
compte -> Logbook Data -> API Key). Champ vide dans CONFIG = fonctionnalité
INACTIVE, comme les autres services d'upload (cf. logx_qsl.py)."""
import urllib.parse

from logx_version import APP_VERSION

QRZ_LOGBOOK_URL = 'https://logbook.qrz.com/api'
_USER_AGENT = f'LogXAI/{APP_VERSION}'  # identifiable, < 128 caractères (exigé par la doc QRZ)


def qrz_logbook_settings(cfg):
    """Réglages du push QRZ Logbook depuis la config CLIENT. `push_enabled`
    exige À LA FOIS la clé API ET le bouton dédié activé — comme
    clublog_live, la clé seule ne suffit pas à activer l'envoi automatique
    (l'utilisateur peut vouloir la garder pour un usage manuel plus tard)."""
    cfg = cfg or {}
    key = (cfg.get('qrz_logbook_key') or '').strip()
    push = str(cfg.get('qrz_logbook_push', '')) in ('1', 'true', 'True', 'on')
    return {'key': key, 'configured': bool(key), 'push_enabled': bool(key and push)}


def _parse_response(text):
    """RESULT=OK&LOGID=123&COUNT=1 (form-urlencoded, PAS du JSON) -> dict.
    parse_qsl garde l'ordre et tolère les valeurs vides (REASON absent)."""
    return dict(urllib.parse.parse_qsl(text or '', keep_blank_values=True))


def push_qso(cfg, qso):
    """Insère UN QSO dans le carnet QRZ Logbook (ACTION=INSERT). Ne lève
    jamais, renvoie {'ok': bool, ...} comme les autres fonctions réseau du
    projet (logx_qsl, logx_pota...)."""
    s = qrz_logbook_settings(cfg)
    if not s['configured']:
        return {'ok': False, 'error': 'QRZ Logbook non configuré (clé API manquante dans CONFIG → QSL)'}

    from logx_qsl import _single_qso_adif  # réutilise le même générateur mono-QSO que HRDLog
    try:
        record = _single_qso_adif(qso, cfg or {})
    except Exception as e:
        return {'ok': False, 'error': f'ADIF : {e}'}

    from logx_utils import post_url_form  # import local : mockable par les tests
    fields = {'KEY': s['key'], 'ACTION': 'INSERT', 'ADIF': record}
    status, text = post_url_form(QRZ_LOGBOOK_URL, fields, timeout=10,
                                  headers={'User-Agent': _USER_AGENT})
    if status is None:
        return {'ok': False, 'error': 'logbook.qrz.com injoignable (réseau)'}
    parsed = _parse_response(text)
    result = (parsed.get('RESULT') or '').upper()
    if result in ('OK', 'REPLACE'):
        return {'ok': True, 'result': result, 'logid': parsed.get('LOGID', '')}
    # AUTH = clé refusée, FAIL = doublon/erreur de contenu — distingués pour
    # que l'appelant sache s'il faut revoir la clé ou juste ignorer ce QSO.
    return {'ok': False, 'result': result or None,
            'error': parsed.get('REASON') or f'QRZ Logbook a refusé le QSO (RESULT={result or "?"})'}


def test_connection(cfg):
    """ACTION=STATUS : vérifie la clé sans insérer de QSO factice — pendant
    d'un bouton « Tester la connexion » comme pour rigctld/TCI ailleurs
    dans CONFIG."""
    s = qrz_logbook_settings(cfg)
    if not s['configured']:
        return {'ok': False, 'error': 'Clé API QRZ Logbook manquante'}
    from logx_utils import post_url_form
    status, text = post_url_form(
        QRZ_LOGBOOK_URL, {'KEY': s['key'], 'ACTION': 'STATUS'}, timeout=10,
        headers={'User-Agent': _USER_AGENT})
    if status is None:
        return {'ok': False, 'error': 'logbook.qrz.com injoignable (réseau)'}
    parsed = _parse_response(text)
    result = (parsed.get('RESULT') or '').upper()
    if result == 'OK':
        return {'ok': True, 'status': {k: v for k, v in parsed.items() if k != 'RESULT'}}
    return {'ok': False, 'error': parsed.get('REASON') or f'Clé refusée (RESULT={result or "?"})'}
