# -*- coding: utf-8 -*-
"""Synchronisation QSL — upload des logs et import des confirmations.

Ferme la boucle QSL, comme Log4OM / HRD :
  - UPLOAD du log (ADIF) vers eQSL et ClubLog après un concours.
  - IMPORT des confirmations depuis LoTW (rapport ADIF, login/mot de passe —
    pas besoin de TQSL pour DESCENDRE les confirmations) → marque chaque QSO
    « confirmé » dans qsl_confirmations.json, exploité par radiocontest_awards.

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

CONFIRM_FILE = 'qsl_confirmations.json'
_lock = threading.Lock()

# ADIF band ('2m') → MHz ('144'), pour aligner les clés sur celles du log.
try:
    from radiocontest_export import ADIF_BAND
    _BAND_FROM_ADIF = {v: k for k, v in ADIF_BAND.items()}
except Exception:
    _BAND_FROM_ADIF = {}


def _ssl_ctx():
    try:
        from radiocontest_utils import SSL_CTX
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
    """Bande MHz ('144') depuis un record ADIF (BAND '2m' ou FREQ en MHz)."""
    b = (rec.get('BAND') or '').lower().strip()
    if b in _BAND_FROM_ADIF:
        return _BAND_FROM_ADIF[b]
    freq = rec.get('FREQ')
    if freq:
        try:
            mhz = float(freq)
            from radiocontest_scoring import _band_from_freq
            return _band_from_freq(mhz)
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
            from radiocontest_storage import save_json_atomic
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
        import radiocontest_awards as awards
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
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'RadioContestAI'})
        with urllib.request.urlopen(req, timeout=60, context=_ssl_ctx()) as r:
            body = r.read().decode('utf-8', 'replace')
    except Exception as e:
        return {'ok': False, 'error': f'LoTW injoignable : {e}'}
    if 'Username/password incorrect' in body or 'ARRL Logbook of the World' in body[:200] and '<' not in body[:5]:
        return {'ok': False, 'error': 'Identifiants LoTW refusés'}
    conf = parse_confirmations(body, 'lotw')
    total, added = merge_confirmations(conf)
    _stamp('lotw')
    return {'ok': True, 'service': 'LoTW', 'confirmed_downloaded': len(conf),
            'newly_added': added, 'total_confirmations': total}


# ─── eQSL / ClubLog : upload du log ──────────────────────────────────────────

def _multipart(fields, files):
    """Corps multipart/form-data. fields = {name:val}, files = {name:(fname,bytes)}."""
    boundary = '----RadioContestAI' + str(int(time.time() * 1000))
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
        'User-Agent': 'RadioContestAI'})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
        return r.read().decode('utf-8', 'replace')


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
    if 'error' in low or 'bad' in low or 'incorrect' in low:
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
        return {'ok': True, 'service': 'ClubLog', 'response': resp[:200].strip()}
    return {'ok': False, 'service': 'ClubLog', 'error': resp[:200].strip()}


# ─── ÉTAT / HORODATAGE ────────────────────────────────────────────────────────

_STAMP_FILE = 'qsl_sync.json'


def _stamp(action):
    try:
        import datetime
        data = {}
        if os.path.exists(_STAMP_FILE):
            with open(_STAMP_FILE, encoding='utf-8') as f:
                data = json.load(f) or {}
        data[action] = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')
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
    return {
        'eqsl': bool(s.get('eqsl_enabled')),
        'clublog': bool(s.get('clublog_enabled')),
        'lotw': bool(s.get('lotw_enabled')),
        'last': stamps,
        'confirmations': confirmations,
    }
