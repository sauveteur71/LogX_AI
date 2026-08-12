# -*- coding: utf-8 -*-
"""Synchronisation QSL — upload des logs et import des confirmations.

Ferme la boucle QSL, comme Log4OM / HRD :
  - UPLOAD du log (ADIF) vers eQSL et ClubLog après un concours.
  - IMPORT des confirmations depuis LoTW (rapport ADIF, login/mot de passe —
    pas besoin de TQSL pour DESCENDRE les confirmations) → marque chaque QSO
    « confirmé » dans qsl_confirmations.json, exploité par logx_awards.

Tous les identifiants viennent de la config (côté serveur, jamais renvoyés au
client — comme QRZ/ON4KST). Chaque fonction réseau retourne un dict
{'ok': bool, ...} et n'échoue jamais par exception.

LoTW UPLOAD n'est pas géré ici (il exige la signature TQSL avec le certificat
de la station) ; on descend seulement les confirmations. eQSL/ClubLog upload
suffisent à publier le log.
"""
import json
import os
import re
import time
import threading
import urllib.request
import urllib.parse
import concurrent.futures as _cf
from logx_utils import utcnow

# Pool dédié : borne l'attente d'un urlopen() dont le timeout ne couvre pas la
# résolution DNS (getaddrinfo(), bloquante hors du socket — cf. logx_utils.fetch_url).
_NET_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=4, thread_name_prefix='qsl_net')

CONFIRM_FILE = 'qsl_confirmations.json'
_lock = threading.Lock()

# ADIF band ('2m') → MHz ('144'), pour aligner les clés sur celles du log.
try:
    from logx_export import ADIF_BAND
    _BAND_FROM_ADIF = {v: k for k, v in ADIF_BAND.items()}
except Exception:
    _BAND_FROM_ADIF = {}


def _ssl_ctx():
    try:
        from logx_utils import SSL_CTX
        return SSL_CTX
    except Exception:
        return None


# ─── IDENTIFIANTS ─────────────────────────────────────────────────────────────

def qsl_settings(cfg):
    """Identifiants des services QSL (config CLIENT puis config.json section
    'qsl'). Ne renvoie jamais rien au navigateur."""
    cfg = cfg or {}
    s = {
        'eqsl_user': (cfg.get('eqsl_user') or '').strip(),
        'eqsl_password': cfg.get('eqsl_password') or '',
        'clublog_email': (cfg.get('clublog_email') or '').strip(),
        'clublog_callsign': (cfg.get('clublog_callsign') or '').strip().upper(),
        'clublog_password': cfg.get('clublog_password') or '',
        'clublog_api_key': (cfg.get('clublog_api_key') or '').strip(),
        'lotw_user': (cfg.get('lotw_user') or '').strip().upper(),
        'lotw_password': cfg.get('lotw_password') or '',
        'qrzcq_callsign': (cfg.get('qrzcq_callsign') or '').strip().upper(),
        'qrzcq_api_key': (cfg.get('qrzcq_api_key') or '').strip(),
        'hrdlog_callsign': (cfg.get('hrdlog_callsign') or '').strip().upper(),
        'hrdlog_code': (cfg.get('hrdlog_code') or '').strip(),
    }
    if not any(s.values()):
        try:
            with open('config.json', encoding='utf-8') as f:
                q = (json.load(f).get('qsl', {}) or {})
            for k in s:
                s[k] = s[k] or q.get(k, '')
        except Exception:
            pass
    s['eqsl_enabled'] = bool(s['eqsl_user'] and s['eqsl_password'])
    s['clublog_enabled'] = bool(s['clublog_email'] and s['clublog_callsign']
                                and s['clublog_password'] and s['clublog_api_key'])
    s['lotw_enabled'] = bool(s['lotw_user'] and s['lotw_password'])
    s['qrzcq_enabled'] = bool(s['qrzcq_callsign'] and s['qrzcq_api_key'])
    s['hrdlog_enabled'] = bool(s['hrdlog_callsign'] and s['hrdlog_code'])
    return s


# ─── PARSEUR ADIF (import des confirmations) ─────────────────────────────────

# Un champ ADIF « <NAME:len:type> » OU une balise de contrôle « <EOR> / <EOH> »
# (ces dernières n'ont PAS de longueur — d'où le groupe optionnel).
_FIELD_RE = re.compile(r'<([A-Za-z0-9_]+)(?::(\d+)(?::[A-Za-z])?)?>', re.I)


def _parse_adif_records(text):
    """Découpe un ADIF en records (liste de dicts UPPERCASE→valeur).
    Ignore l'en-tête (avant <EOH>)."""
    if not text:
        return []
    up = text.upper()
    if '<EOH>' in up:
        text = text[up.index('<EOH>') + 5:]
    records = []
    cur = {}
    i = 0
    while i < len(text):
        m = _FIELD_RE.search(text, i)
        if not m:
            break
        name = m.group(1).upper()
        if m.group(2) is None:          # balise de contrôle sans longueur
            i = m.end()
            if name == 'EOR':
                if cur:
                    records.append(cur)
                cur = {}
            elif name == 'EOH':
                cur = {}
            continue
        length = int(m.group(2))
        start = m.end()
        cur[name] = text[start:start + length].strip()
        i = start + length
    if cur:
        records.append(cur)
    return records


def _band_from_record(rec):
    """Bande MHz ('144') depuis un record ADIF (BAND '2m' ou FREQ en MHz).
    Si BAND porte un libellé ADIF officiel absent de notre table interne
    (ADIF_BAND, ~19 bandes utiles aux concours gérés — 60m, 2190m... n'en
    font pas partie), il est retourné TEL QUEL plutôt que rejeté : le QSO
    reste importable même sans multiplicateur concours pour cette bande."""
    b = (rec.get('BAND') or '').lower().strip()
    if b in _BAND_FROM_ADIF:
        return _BAND_FROM_ADIF[b]
    freq = rec.get('FREQ')
    if freq:
        try:
            mhz = float(freq)
            from logx_scoring import _band_from_freq
            found = _band_from_freq(mhz)
            if found:
                return found
            # Repli sur la table officielle complète (33 bandes, voir
            # logx_adif_enums) : couvre les bandes rares que _band_from_freq
            # (12 bandes de concours) ne reconnaît pas — sans ce repli, un
            # QSO avec FREQ mais sans BAND sur une bande rare était rejeté à
            # tort ("bande... non reconnu") alors que sa fréquence est valide.
            from logx_adif_enums import band_from_freq as _band_from_freq_adif
            found = _band_from_freq_adif(mhz)
            if found:
                return found
        except Exception:
            pass
    return b


def _key_from_record(rec):
    call = (rec.get('CALL') or '').upper().strip()
    band = _band_from_record(rec)
    mode = (rec.get('SUBMODE') or rec.get('MODE') or '').upper().strip()
    if not call:
        return None
    return f"{call}|{band}|{mode}"


def parse_confirmations(adif_text, source='lotw'):
    """Extrait les QSO CONFIRMÉS d'un rapport ADIF (LoTW/eQSL).
    Retourne {clé: {source: date|True}} — clé alignée sur le log (CALL|MHz|MODE)."""
    out = {}
    for rec in _parse_adif_records(adif_text):
        rcvd = (rec.get('QSL_RCVD') or rec.get('LOTW_QSL_RCVD')
                or rec.get('EQSL_QSL_RCVD') or '').upper()
        # LoTW : un record dans lotwreport?qso_qsl=yes est déjà confirmé.
        confirmed = rcvd == 'Y' or (source == 'lotw' and rcvd in ('', 'Y'))
        if not confirmed:
            continue
        key = _key_from_record(rec)
        if not key:
            continue
        when = (rec.get('QSLRDATE') or rec.get('APP_LOTW_RXQSL')
                or rec.get('QSO_DATE') or True)
        out.setdefault(key, {})[source] = when
    return out


def merge_confirmations(new_conf):
    """Fusionne des confirmations dans qsl_confirmations.json (thread-safe).
    Retourne (total, ajoutés)."""
    with _lock:
        try:
            from logx_storage import save_json_atomic
        except Exception:
            save_json_atomic = None
        db = {}
        if os.path.exists(CONFIRM_FILE):
            try:
                with open(CONFIRM_FILE, encoding='utf-8') as f:
                    db = json.load(f) or {}
            except Exception:
                db = {}
        added = 0
        for key, srcs in new_conf.items():
            entry = db.setdefault(key, {})
            for s, v in srcs.items():
                if s not in entry:
                    added += 1
                entry[s] = v
        if save_json_atomic:
            save_json_atomic(CONFIRM_FILE, db, compact=True)
        else:
            with open(CONFIRM_FILE, 'w', encoding='utf-8') as f:
                json.dump(db, f, ensure_ascii=False)
    try:
        import logx_awards as awards
        awards.invalidate()
    except Exception:
        pass
    return len(db), added


# ─── LoTW : téléchargement des confirmations ─────────────────────────────────

def sync_lotw(cfg, since=None):
    """Descend le rapport des QSO confirmés LoTW et met à jour les
    confirmations. `since` = 'YYYY-MM-DD' (optionnel, limite la fenêtre)."""
    s = qsl_settings(cfg)
    if not s['lotw_enabled']:
        return {'ok': False, 'error': 'LoTW non configuré (CONFIG → QSL)'}
    params = {
        'login': s['lotw_user'], 'password': s['lotw_password'],
        'qso_query': '1', 'qso_qsl': 'yes',
    }
    if since:
        params['qso_qslsince'] = since
    url = 'https://lotw.arrl.org/lotwuser/lotwreport.adi?' + urllib.parse.urlencode(params)

    def _do():
        req = urllib.request.Request(url, headers={'User-Agent': 'LogXAI'})
        with urllib.request.urlopen(req, timeout=20, context=_ssl_ctx()) as r:
            return r.read().decode('utf-8', 'replace')

    try:
        body = _NET_EXECUTOR.submit(_do).result(timeout=23)
    except _cf.TimeoutError:
        return {'ok': False, 'error': 'LoTW injoignable : délai dépassé'}
    except Exception as e:
        return {'ok': False, 'error': f'LoTW injoignable : {e}'}
    # Détection d'échec sur un critère FIABLE : identifiants explicitement
    # refusés, OU absence de la balise ADIF <eoh> (tout rapport LoTW valide,
    # même vide, contient un en-tête ADIF terminé par <eoh>). L'ancien test
    # cherchait « ARRL Logbook of the World » dans body[:200] — or c'est aussi
    # la première ligne (« ...Status Report ») d'un téléchargement RÉUSSI, si
    # bien que toute synchro correcte était rejetée comme « identifiants refusés ».
    low = body.lower()
    if 'username/password incorrect' in low or '<eoh>' not in low:
        return {'ok': False, 'error': 'Identifiants LoTW refusés ou rapport illisible'}
    conf = parse_confirmations(body, 'lotw')
    total, added = merge_confirmations(conf)
    _stamp('lotw')
    return {'ok': True, 'service': 'LoTW', 'confirmed_downloaded': len(conf),
            'newly_added': added, 'total_confirmations': total}


# ─── eQSL / ClubLog : upload du log ──────────────────────────────────────────

def _multipart(fields, files):
    """Corps multipart/form-data. fields = {name:val}, files = {name:(fname,bytes)}."""
    boundary = '----LogXAI' + str(int(time.time() * 1000))
    parts = []
    for name, val in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{val}\r\n')
    body = ''.join(parts).encode('utf-8')
    for name, (fname, data) in files.items():
        head = (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                f'filename="{fname}"\r\nContent-Type: text/plain\r\n\r\n')
        body += head.encode('utf-8') + (data if isinstance(data, bytes) else data.encode('utf-8')) + b'\r\n'
    body += f'--{boundary}--\r\n'.encode('utf-8')
    return body, boundary


def _post(url, fields, files, timeout=60):
    body, boundary = _multipart(fields, files)
    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'User-Agent': 'LogXAI'})
    def _do():
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
            return r.read().decode('utf-8', 'replace')
    return _NET_EXECUTOR.submit(_do).result(timeout=timeout + 3)


def upload_eqsl(cfg, adif):
    s = qsl_settings(cfg)
    if not s['eqsl_enabled']:
        return {'ok': False, 'error': 'eQSL non configuré (CONFIG → QSL)'}
    try:
        resp = _post('https://www.eqsl.cc/qslcard/importADIF.cfm',
                     {'EQSL_USER': s['eqsl_user'], 'EQSL_PSWD': s['eqsl_password']},
                     {'Filename': ('log.adi', adif)})
    except Exception as e:
        return {'ok': False, 'error': f'eQSL injoignable : {e}'}
    low = resp.lower()
    # Un succès peut légitimement contenir le mot "error" (ex. "0 record(s)
    # had errors") — on ne rejette que sur des phrases d'échec SPÉCIFIQUES,
    # pas sur des mots isolés qui apparaissent aussi dans les messages de succès.
    failure_markers = ('password is incorrect', 'invalid eqsl user',
                        'account is not activ', 'unable to process')
    if any(m in low for m in failure_markers):
        return {'ok': False, 'service': 'eQSL',
                'error': re.sub(r'<[^>]+>', ' ', resp)[:200].strip()}
    _stamp('eqsl_upload')
    return {'ok': True, 'service': 'eQSL', 'response': re.sub(r'<[^>]+>', ' ', resp)[:200].strip()}


def upload_clublog(cfg, adif):
    s = qsl_settings(cfg)
    if not s['clublog_enabled']:
        return {'ok': False, 'error': 'ClubLog non configuré (email + indicatif + '
                                      'mot de passe + clé API dans CONFIG → QSL)'}
    try:
        resp = _post('https://clublog.org/putlogs.php',
                     {'email': s['clublog_email'], 'password': s['clublog_password'],
                      'callsign': s['clublog_callsign'], 'api': s['clublog_api_key']},
                     {'file': ('log.adi', adif)})
    except Exception as e:
        return {'ok': False, 'error': f'ClubLog injoignable : {e}'}
    if resp.strip().startswith('OK') or 'accepted' in resp.lower():
        _stamp('clublog_upload')
        return {'ok': True, 'service': 'ClubLog', 'response': re.sub(r'<[^>]+>', ' ', resp)[:200].strip()}
    return {'ok': False, 'service': 'ClubLog', 'error': re.sub(r'<[^>]+>', ' ', resp)[:200].strip()}


# ─── QRZCQ : upload du log (API JSON documentée, qrzcq.com/page/developers) ──

QRZCQ_UPLOAD_URL = 'https://ssl.qrzcq.com/api/logupload'


def upload_qrzcq(cfg, adif):
    s = qsl_settings(cfg)
    if not s['qrzcq_enabled']:
        return {'ok': False, 'error': 'QRZCQ non configuré (indicatif + clé API dans CONFIG → QSL)'}
    payload = json.dumps({'auth': {'call': s['qrzcq_callsign'], 'key': s['qrzcq_api_key']},
                          'data': {'adif': adif}}).encode('utf-8')
    req = urllib.request.Request(QRZCQ_UPLOAD_URL, data=payload, headers={
        'Content-Type': 'application/json', 'User-Agent': 'LogXAI'})
    def _do():
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx()) as r:
            return r.read().decode('utf-8', 'replace')
    try:
        resp_text = _NET_EXECUTOR.submit(_do).result(timeout=33)
    except _cf.TimeoutError:
        return {'ok': False, 'error': 'QRZCQ injoignable : délai dépassé'}
    except Exception as e:
        return {'ok': False, 'error': f'QRZCQ injoignable : {e}'}
    try:
        resp = json.loads(resp_text)
    except ValueError:
        return {'ok': False, 'service': 'QRZCQ', 'error': re.sub(r'<[^>]+>', ' ', resp_text)[:200].strip()}
    if str(resp.get('status', '')).upper() == 'OK':
        _stamp('qrzcq_upload')
        return {'ok': True, 'service': 'QRZCQ', 'response': resp.get('message', '')}
    return {'ok': False, 'service': 'QRZCQ',
           'error': resp.get('message') or re.sub(r'<[^>]+>', ' ', resp_text)[:200].strip()}


# ─── HRDLog.net : upload du log ───────────────────────────────────────────────
# Aucune documentation publique officielle (page autoupload.aspx = tutoriel
# GUI seulement, specs PDF décrites comme confidentielles). Implémenté à partir
# du code source réel de la librairie cliente open-source iw1qlh/HRDLOG-net-
# library (HrdProtocol.cs) : endpoint NewEntry.aspx, formulaire url-encodé
# Callsign/Code/App/ADIFData. L'API est CONÇUE PAR QSO UNIQUE (« New Entry »,
# pas de repli batch connu) — contrairement à eQSL/ClubLog/QRZCQ, l'upload
# envoie donc un POST par QSO, pas un fichier ADIF complet en un coup.

HRDLOG_HOSTS = ('robot.hrdlog.net', 'www.hrdlog.net')  # primaire, puis secours
_HRDLOG_INSERT_RE = re.compile(r'<insert>(\d+)</insert>', re.I)
_HRDLOG_ERROR_RE = re.compile(r'<error>(.*?)</error>', re.I | re.S)
# Coupe-circuit : sans lui, un envoi sans réseau (terrain /P, HRDLog en panne)
# retentait les 2 hôtes pour CHAQUE QSO restant — jusqu'à 150 QSO x 16s = 40 min
# de gel perçu sur une requête HTTP synchrone (POST /qsl/upload). Après N échecs
# consécutifs (signe clair d'absence réseau plutôt que de malchance répétée),
# on arrête net plutôt que de rejouer l'attente pour chaque QSO restant.
HRDLOG_FAIL_CIRCUIT = 5


def _single_qso_adif(qso, cfg):
    """Un seul enregistrement ADIF (réutilise le générateur existant plutôt
    que dupliquer le mapping de champs — on ne garde que le corps, sans
    l'en-tête <EOH> qui n'a pas de sens pour un envoi unitaire)."""
    import logx_export as export
    full = export.build_adif([qso], cfg)
    return full.split('<EOH>\n', 1)[1].strip()


def _hrdlog_post_one(host, callsign, code, adif_record, timeout=8):
    fields = {'Callsign': callsign, 'Code': code, 'App': 'LogXAI', 'ADIFData': adif_record}
    body = urllib.parse.urlencode(fields).encode('utf-8')
    req = urllib.request.Request(
        f'https://{host}/NewEntry.aspx', data=body,
        headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'LogXAI'})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
        return r.read().decode('utf-8', 'replace')


def upload_hrdlog(cfg, qsos):
    """Envoie chaque QSO individuellement (voir note ci-dessus). Retourne le
    compte envoyé/échoué plutôt qu'un simple ok/erreur binaire, puisqu'un
    échec partiel est le cas normal pour ce type d'API unitaire."""
    s = qsl_settings(cfg)
    if not s['hrdlog_enabled']:
        return {'ok': False, 'error': "HRDLog non configuré (indicatif + code d'upload dans CONFIG → QSL)"}
    qsos = qsos or []
    if not qsos:
        return {'ok': False, 'error': 'Aucun QSO à envoyer'}
    sent, failed, last_error = 0, 0, ''
    consecutive_fails = 0
    total = len(qsos)
    for idx, q in enumerate(qsos):
        record = _single_qso_adif(q, cfg)
        ok_one = False
        for host in HRDLOG_HOSTS:
            try:
                resp = _NET_EXECUTOR.submit(
                    _hrdlog_post_one, host, s['hrdlog_callsign'], s['hrdlog_code'], record
                ).result(timeout=11)
            except Exception as e:
                last_error = str(e)
                continue
            # Succès = <insert>1</insert> (compte réel d'enregistrements insérés,
            # PAS l'absence d'une balise <error> — vérifié en direct contre le
            # vrai serveur : des identifiants invalides renvoient <insert>0</insert>
            # SANS aucune balise <error>, ce qui aurait été pris pour un succès).
            m = _HRDLOG_INSERT_RE.search(resp)
            if m and m.group(1) != '0':
                ok_one = True
                break
            err_m = _HRDLOG_ERROR_RE.search(resp)
            if err_m:
                last_error = re.sub(r'<[^>]+>', ' ', err_m.group(1))[:200].strip()
            elif m:  # <insert>0</insert> sans <error> : rejet silencieux du serveur
                last_error = "Rejeté par HRDLog — vérifie l'indicatif et le code d'upload"
            else:
                last_error = re.sub(r'<[^>]+>', ' ', resp)[:200].strip() or 'Réponse HRDLog inattendue'
        if ok_one:
            sent += 1
            consecutive_fails = 0
        else:
            failed += 1
            consecutive_fails += 1
            if consecutive_fails >= HRDLOG_FAIL_CIRCUIT:
                remaining = total - (idx + 1)
                if remaining > 0:
                    failed += remaining
                    last_error = (f"Arrêt anticipé après {HRDLOG_FAIL_CIRCUIT} échecs "
                                  f"consécutifs ({remaining} QSO restant(s) non tenté(s)) — "
                                  "HRDLog probablement injoignable.")
                break
    if sent:
        _stamp('hrdlog_upload')
    return {'ok': sent > 0, 'service': 'HRDLog', 'sent': sent, 'failed': failed,
            'error': None if sent else (last_error or 'Aucun QSO accepté')}


# ─── Point d'entrée unifié — un service de plus = une entrée ici, pas une ────
# ─── nouvelle branche if/elif dans logx_http.py ──────────────────────

_ADIF_UPLOAD_HANDLERS = {
    'eqsl': upload_eqsl,
    'clublog': upload_clublog,
    'qrzcq': upload_qrzcq,
}


def upload_log(cfg, service, qsos):
    """Dispatch générique : construit l'ADIF une seule fois pour les services
    qui uploadent un fichier complet ; HRDLog reçoit la liste de QSO brute
    (son API est unitaire, voir upload_hrdlog)."""
    service = (service or '').lower()
    if service == 'hrdlog':
        return upload_hrdlog(cfg, qsos)
    handler = _ADIF_UPLOAD_HANDLERS.get(service)
    if not handler:
        return {'ok': False, 'error': f"Service inconnu ({service}) — attendu : "
                                      f"{', '.join(list(_ADIF_UPLOAD_HANDLERS) + ['hrdlog'])}"}
    import logx_export as export
    adif = export.build_adif(qsos, cfg)
    return handler(cfg, adif)


# ─── CLUB LOG LIVE STREAM (expédition : QSO poussés en temps réel) ────────────
# Format vérifié contre la doc officielle Club Log (clublog.freshdesk.com,
# "How To Upload QSOs In Real-Time") : POST https://clublog.org/realtime.php,
# corps url-encodé email/password/callsign/adif — le champ `adif` doit
# contenir EXACTEMENT UN enregistrement ADIF terminé par <EOR>, JAMAIS un
# lot ni l'en-tête <adif_ver>/<programid>/<EOH> qu'ajoute build_adif() (bug
# corrigé ici : l'ancien code envoyait le fichier complet avec en-tête, que
# Club Log n'attend pas pour cette route temps réel — voir _single_qso_adif).
# La clé API n'est PAS un paramètre de realtime.php (contrairement à
# putlogs.php/upload_clublog ci-dessus) ; conservée dans clublog_enabled
# uniquement pour ne pas dupliquer une seconde condition d'activation.
#
# « Un 403 doit arrêter immédiatement les tentatives suivantes, pas de retry
# agressif » (consigne explicite, cohérente avec le "throttle exists to
# prevent abuse" de la doc) : un disjoncteur mémoire s'arme dès le premier
# 403 et bloque tout nouvel essai tant que les identifiants ClubLog n'ont
# pas changé — sans lui, un identifiant invalide aurait autrement relancé
# une requête pour CHAQUE QSO restant du log (fire-and-forget, un thread par
# QSO ajouté), exactement le comportement que Club Log demande d'éviter.
_clublog_rt_breaker = {'tripped': False, 'creds_fp': None, 'reason': ''}
# Protège _clublog_rt_breaker : realtime_push() est appelé fire-and-forget
# depuis un thread PAR QSO ajouté (voir add_qso_to_log dans logx_http.py),
# donc potentiellement en concurrence. Lecture ET écriture (reset sur
# changement d'identifiants + vérif tripped) restent dans le MÊME bloc
# "with _clublog_rt_lock:" ci-dessous — jamais relâché entre les deux.
_clublog_rt_lock = threading.Lock()


def _clublog_creds_fp(s):
    return (s['clublog_email'], s['clublog_callsign'], s['clublog_password'], s['clublog_api_key'])


def realtime_push(cfg, qso):
    """Pousse UN QSO vers le flux temps réel Club Log (apparaît sur le live
    stream de l'expédition). Nécessite les identifiants ClubLog. Retourne
    {ok, ...} ; ne lève jamais (appel fire-and-forget, voir add_qso_to_log)."""
    s = qsl_settings(cfg)
    if not s['clublog_enabled']:
        return {'ok': False, 'error': 'ClubLog non configuré'}

    fp = _clublog_creds_fp(s)
    with _clublog_rt_lock:
        if _clublog_rt_breaker['creds_fp'] != fp:
            # Identifiants différents du dernier essai (nouveau réglage, ou
            # tout premier appel) : on redonne sa chance, le disjoncteur ne
            # doit pas bloquer indéfiniment un simple changement de mot de
            # passe/clé.
            _clublog_rt_breaker.update(tripped=False, creds_fp=fp, reason='')
        blocked, reason = _clublog_rt_breaker['tripped'], _clublog_rt_breaker['reason']
    if blocked:
        return {'ok': False, 'blocked': True,
                'error': f"ClubLog Live suspendu après un refus (HTTP 403) — {reason} "
                          "Corrige les identifiants ClubLog dans CONFIG pour réessayer."}

    try:
        record = _single_qso_adif(qso, cfg or {})
    except Exception as e:
        return {'ok': False, 'error': f'ADIF : {e}'}
    fields = {
        'email': s['clublog_email'], 'password': s['clublog_password'],
        'callsign': s['clublog_callsign'] or
                    ((cfg or {}).get('callsign_contest') or (cfg or {}).get('callsign') or '').upper(),
        'adif': record,
    }
    from logx_utils import post_url_form  # import local : mockable par les tests
    status, text = post_url_form('https://clublog.org/realtime.php', fields,
                                  timeout=20, headers={'User-Agent': 'LogXAI'})
    if status is None:
        return {'ok': False, 'error': 'ClubLog live injoignable (réseau)'}
    resp = (text or '')[:150].strip()
    if status == 403:
        with _clublog_rt_lock:
            _clublog_rt_breaker.update(tripped=True, creds_fp=fp, reason=resp or 'accès refusé')
        return {'ok': False, 'blocked': True,
                'error': f'ClubLog a refusé le flux temps réel (HTTP 403) : {resp}'}
    if status >= 400:
        return {'ok': False, 'error': f'ClubLog live a répondu HTTP {status} : {resp}'}
    ok = 'OK' in resp.upper() or 'ACCEPTED' in resp.upper() or resp == ''
    return {'ok': ok, 'response': resp}


# ─── ÉTAT / HORODATAGE ────────────────────────────────────────────────────────

_STAMP_FILE = 'qsl_sync.json'


def _stamp(action):
    with _lock:
        try:
            try:
                from logx_storage import save_json_atomic
            except Exception:
                save_json_atomic = None
            data = {}
            if os.path.exists(_STAMP_FILE):
                with open(_STAMP_FILE, encoding='utf-8') as f:
                    data = json.load(f) or {}
            data[action] = utcnow().strftime('%Y-%m-%d %H:%M')
            if save_json_atomic:
                save_json_atomic(_STAMP_FILE, data, compact=True)
            else:
                with open(_STAMP_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
        except Exception:
            pass


def qsl_status(cfg=None):
    """État de configuration + horodatage des dernières synchros."""
    s = qsl_settings(cfg) if cfg is not None else {}
    stamps = {}
    try:
        if os.path.exists(_STAMP_FILE):
            with open(_STAMP_FILE, encoding='utf-8') as f:
                stamps = json.load(f) or {}
    except Exception:
        pass
    confirmations = 0
    try:
        if os.path.exists(CONFIRM_FILE):
            with open(CONFIRM_FILE, encoding='utf-8') as f:
                confirmations = len(json.load(f) or {})
    except Exception:
        pass
    with _clublog_rt_lock:
        clublog_rt_blocked = _clublog_rt_breaker['tripped']
    return {
        'eqsl': bool(s.get('eqsl_enabled')),
        'clublog': bool(s.get('clublog_enabled')),
        'lotw': bool(s.get('lotw_enabled')),
        'qrzcq': bool(s.get('qrzcq_enabled')),
        'hrdlog': bool(s.get('hrdlog_enabled')),
        'last': stamps,
        'confirmations': confirmations,
        'clublog_realtime_blocked': clublog_rt_blocked,
    }
