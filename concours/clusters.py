# -*- coding: utf-8 -*-
"""Sources de spots : clusters DX (F5LEN, DXSummit, DXWatch, telnet, ON4KST...), propagation NOAA/DXMaps, lookups HamQTH/3830."""

import json
import os
import re
import time
import socket

from utils import MODES_NUMERIQUES, fetch_url, is_digital_mode, locator_to_latlon

# ─── CORRESPONDANCE BANDES → CLUSTERS ────────────────────────────────────────
CLUSTER_MAP = {
    '144': [
        'http://cluster.f5len.org/index.php?what=144',
        'http://www.dxsummit.fi/api/v1/spots?include=VHF&limit=50',
    ],
    '432': [
        'http://cluster.f5len.org/index.php?what=432',
        'http://www.dxsummit.fi/api/v1/spots?include=432MHz&limit=50',
    ],
    '50':  ['http://cluster.f5len.org/index.php?what=50'],
    '1296':['http://cluster.f5len.org/index.php?what=1296'],
    'HF':  [
        'http://www.dxsummit.fi/api/v1/spots?limit=100',
        'http://dxwatch.com:8010/dxsd1/dxsd1.php?f=0',
    ],
}

PROPAGATION_SOURCES = {
    'Troposphérique':  'http://tropo.f5len.org/forecasts-for-europe/',
    'Sporadique-E':    'http://www.dxmaps.com/spots/map.php',
    'F2 (ionosphérique)': 'https://www.bandconditions.com/',
    'NOAA K-index':    'https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json',
}

# ─── FETCH CLUSTERS ──────────────────────────────────────────────────────────
# ─── CACHE SPOTS GLOBAL (accessible par /log/status) ─────────────────────────
SPOTS_CACHE = {}   # band → [{ call, locator, freq, spotter, time, source }]

def _normalize_spot(call='', locator='', freq=0.0, spotter='', time_str='', info='', source=''):
    """Retourne un dict de spot normalisé avec coordonnées si locator disponible."""
    # Défense contre les None explicites (ex: champ JSON null) — le défaut de paramètre
    # ne s'applique pas si None est passé explicitement, d'où le crash sur info[:60]
    call = call or ''
    locator = locator or ''
    spotter = spotter or ''
    info = info or ''
    source = source or ''
    loc = locator.upper()[:6] if locator else ''
    # Calculer lat/lon depuis le locator pour l'affichage carte
    lat, lon = None, None
    if loc and len(loc) >= 4:
        try:
            lt, ln = locator_to_latlon(loc)
            if lt is not None:
                lat, lon = round(lt, 3), round(ln, 3)
        except Exception:
            pass
    spot = {
        'call':    call.upper().split('/')[0].strip(),
        'dx':      call.upper().split('/')[0].strip(),  # alias pour compatibilité carte
        'locator': loc,
        'freq':    float(freq) if freq else 0.0,
        'spotter': spotter.upper(),
        'time':    str(time_str)[:5],
        'info':    info[:60],
        'source':  source,
        'country': '',
    }
    if lat is not None:
        spot['lat'] = lat
        spot['lon'] = lon
    return spot

# ── CLUSTER F5LEN (principal cluster VHF français) ───────────────────────────
def fetch_cluster_f5len(band, filter_digital=True):
    url = f"http://cluster.f5len.org/index.php?what={band}"
    content = fetch_url(url)
    if not content:
        return []
    spots = []
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', content, re.DOTALL|re.IGNORECASE)
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL|re.IGNORECASE)
        cells = [re.sub(r'<[^>]+>','',c).strip() for c in cells]
        cells = [c for c in cells if c]
        if len(cells) >= 3 and re.match(r'[A-Z0-9]{3,}', cells[0] if cells else ''):
            if filter_digital and is_digital_mode(' '.join(cells)):
                continue
            spots.append(cells)
    return spots[:30]

def fetch_dxsummit(band_type='VHF', filter_digital=True):
    # DXSummit API : VHF = OK, HF → on fetch les bandes HF individuellement
    if band_type == 'HF':
        return fetch_dxsummit_hf(filter_digital)
    url = f"http://www.dxsummit.fi/api/v1/spots?include={band_type}&limit=50"
    content = fetch_url(url)
    if not content:
        return []
    try:
        data = json.loads(content)
        spots = []
        items = data if isinstance(data, list) else data.get('spots', [])
        for s in items:
            freq = float(s.get('frequency', s.get('freq', 0)))
            # L'API DXSummit renvoie la fréquence en kHz (ex: 144260.1) — nos
            # bandes VHF/UHF sont toujours < 1000 en MHz, donc toute valeur
            # au-dessus indique du kHz non converti.
            if freq > 1000:
                freq = freq / 1000
            info = str(s.get('mode', s.get('info', ''))).upper()
            if filter_digital and is_digital_mode(info):
                continue
            spots.append({
                'spotter': s.get('de_call', s.get('spotter_callsign', s.get('spotter', ''))),
                'dx':      s.get('dx_call', s.get('dx_callsign', s.get('dx', ''))),
                'freq':    freq,
                'info':    s.get('info', s.get('comment', '')),
                'time':    s.get('time', s.get('utc', '')),
            })
        return spots[:25]
    except:
        return []

def fetch_dxsummit_hf(filter_digital=True):
    """Fetch spots HF depuis DXSummit via HTTP (HTTPS bloqué sur ce réseau)."""
    hf_bands_mhz = ['14MHz','7MHz','21MHz','28MHz','3.5MHz','1.8MHz','50MHz']
    all_spots = []
    seen = set()
    for band_mhz in hf_bands_mhz:
        # HTTP (pas HTTPS) — le serveur DXSummit accepte les deux
        url = f"http://www.dxsummit.fi/api/v1/spots?include={band_mhz}&limit=25"
        content = fetch_url(url, timeout=8)
        if not content:
            continue
        try:
            data = json.loads(content)
            items = data if isinstance(data, list) else data.get('spots', [])
            for s in items:
                freq = float(s.get('frequency', s.get('freq', 0)))
                info = str(s.get('mode', s.get('info', ''))).upper()
                if filter_digital and is_digital_mode(info):
                    continue
                # API DXSummit : dx_call = station DX, de_call = spotter
                dx = s.get('dx_call', s.get('dx_callsign', s.get('dx', '')))
                spotter = s.get('de_call', s.get('spotter_callsign', s.get('spotter', '')))
                key = f"{dx}_{freq}"
                if key in seen or not dx:
                    continue
                seen.add(key)
                # DXSummit longitude : convention inversée (East = négatif) → inverser
                raw_lat = s.get('dx_latitude')
                raw_lon = s.get('dx_longitude')
                spot_lat = float(raw_lat) if raw_lat is not None else None
                spot_lon = -float(raw_lon) if raw_lon is not None else None
                all_spots.append({
                    'spotter': spotter,
                    'dx':      dx,
                    'freq':    freq,
                    'info':    str(s.get('info', s.get('comment', s.get('mode', '')))),
                    'time':    str(s.get('time', s.get('utc', ''))),
                    'lat':     spot_lat,
                    'lon':     spot_lon,
                    'country': s.get('dx_country', ''),
                })
        except Exception as e:
            print(f"[DXSUMMIT-HF] parse error {band_mhz}: {e}")
            continue
    print(f"[DXSUMMIT-HF] {len(all_spots)} spots HF (HTTP)")
    return all_spots[:80]

def fetch_dxwatch_hf(filter_digital=True):
    """DXWatch API HF — HTTP port 8010, bandes 1.8–29.7 MHz."""
    spots = []
    seen = set()
    # Essaie plusieurs endpoints DXWatch
    urls = [
        'http://dxwatch.com:8010/dxsd1/dxsd1.php?f=0&c=100',
        'http://www.dxwatch.com:8010/dxsd1/dxsd1.php?f=0&c=100',
    ]
    for url in urls:
        try:
            content = fetch_url(url, timeout=10)
            if not content:
                continue
            # Format DX Spider texte : "DX de SPOTTER:  FREQ   CALL   INFO  UTCZ"
            rows = re.findall(
                r'DX de\s+([\w/]+)\s*:\s*([\d.]+)\s+([\w/]+)\s*(.*?)\s+(\d{4})Z',
                content, re.IGNORECASE
            )
            for spotter, freq_str, call, info, t in rows:
                try:
                    freq_f = float(freq_str)
                except:
                    continue
                # HF uniquement : 1.8 à 29.7 MHz (inclut 10m/6m)
                if not (1.8 <= freq_f <= 54.0):
                    continue
                if filter_digital and is_digital_mode(info):
                    continue
                key = f"{call}|{freq_f}"
                if key in seen:
                    continue
                seen.add(key)
                spots.append({
                    'spotter': spotter.upper(),
                    'dx':      call.upper(),
                    'freq':    freq_f,
                    'info':    info.strip()[:60],
                    'time':    t + 'Z',
                })
            if spots:
                print(f"[DXWATCH-HF] {url} → {len(spots)} spots HF")
                break
        except Exception as e:
            print(f"[DXWATCH-HF] {url} → erreur: {e}")
            continue

    # Fallback : parser le format HTML si le format texte n'a rien retourné
    if not spots:
        try:
            content = fetch_url('http://dxwatch.com:8010/dxsd1/dxsd1.php?f=0&c=100', timeout=10)
            if content:
                # Essai format JSON
                try:
                    data = json.loads(content)
                    items = data if isinstance(data, list) else data.get('s', data.get('spots', []))
                    for s in (items if isinstance(items, list) else []):
                        freq_f = float(s[1]) if isinstance(s, list) and len(s) > 1 else float(s.get('fr', s.get('freq', 0)))
                        if not (1.8 <= freq_f <= 54.0):
                            continue
                        call = (s[2] if isinstance(s, list) else s.get('dx', '')).upper()
                        info = (s[4] if isinstance(s, list) and len(s) > 4 else s.get('rm', '')).strip()
                        if filter_digital and is_digital_mode(info):
                            continue
                        spotter = (s[0] if isinstance(s, list) else s.get('de', '')).upper()
                        t = (s[5] if isinstance(s, list) and len(s) > 5 else s.get('ut', ''))
                        key = f"{call}|{freq_f}"
                        if key not in seen:
                            seen.add(key)
                            spots.append({'spotter': spotter, 'dx': call, 'freq': freq_f, 'info': info, 'time': str(t)})
                    print(f"[DXWATCH-HF-JSON] {len(spots)} spots")
                except:
                    pass
        except Exception as e:
            print(f"[DXWATCH-HF-fallback] {e}")

    return spots[:60]

def fetch_f5len_hf(filter_digital=True):
    """Fetch spots HF depuis F5LEN Webcluster — bandes 14/21/28/7/3.5 MHz."""
    hf_bands = [14, 21, 28, 7]
    all_spots = []
    seen = set()
    for band in hf_bands:
        url = f"http://cluster.f5len.org/index.php?what={band}"
        content = fetch_url(url)
        if not content:
            continue
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', content, re.DOTALL|re.IGNORECASE)
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL|re.IGNORECASE)
            cells = [re.sub(r'<[^>]+>','',c).strip() for c in cells]
            cells = [c for c in cells if c]
            if len(cells) >= 3 and re.match(r'[A-Z0-9]{3,}', cells[0] if cells else ''):
                if filter_digital and is_digital_mode(' '.join(cells)):
                    continue
                key = cells[0] + '|' + (cells[1] if len(cells)>1 else '')
                if key not in seen:
                    seen.add(key)
                    all_spots.append(cells)
    print(f"[F5LEN-HF] {len(all_spots)} spots HF")
    return all_spots[:40]

# ── DX SPIDER TELNET (cluster standard) ──────────────────────────────────────
# Nœuds publics DX Spider — le premier qui répond est utilisé
DX_SPIDER_NODES = [
    ('dxc.ve7cc.net',      7300),
    ('telnet.dxsummit.fi', 7300),
    ('cluster.dx.fi',      7300),
    ('dx.maritimecontestclub.ca', 7300),
]

def fetch_telnet_cluster(callsign='F4GLD', filter_digital=True, max_spots=60, timeout=8):
    """Connexion telnet à un nœud DX Spider — récupère les derniers spots."""
    spots = []
    for host, port in DX_SPIDER_NODES:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((host, port))
            # Lire le prompt de bienvenue
            buf = b''
            deadline = time.time() + 4
            while time.time() < deadline:
                try:
                    chunk = s.recv(1024)
                    if not chunk:
                        break
                    buf += chunk
                    if b'login' in buf.lower() or b'call' in buf.lower() or b'>' in buf:
                        break
                except socket.timeout:
                    break
            # Envoyer l'indicatif
            s.sendall((callsign + '\r\n').encode())
            time.sleep(1.0)
            # Demander les derniers spots HF
            s.sendall(b'sh/dx/60\r\n')
            # Lire la réponse
            raw = b''
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    raw += chunk
                except socket.timeout:
                    break
            s.sendall(b'bye\r\n')
            s.close()

            # Parser les spots DX Spider : "DX de SPOTTER:  FREQ   CALL   INFO  UTC"
            text = raw.decode('utf-8', errors='replace')
            rows = re.findall(
                r'DX de\s+([\w/]+)\s*:\s*([\d.]+)\s+([\w/]+)\s*(.*?)\s+(\d{4})Z',
                text, re.IGNORECASE
            )
            for spotter, freq_str, call, info, t in rows:
                freq = float(freq_str)
                if filter_digital and is_digital_mode(info):
                    continue
                spots.append({
                    'spotter': spotter.upper(),
                    'dx':      call.upper(),
                    'freq':    freq,
                    'info':    info.strip()[:60],
                    'time':    t + 'Z',
                    'source':  host,
                })
            if spots:
                print(f"[TELNET] {host}:{port} → {len(spots)} spots")
                break  # premier nœud qui répond suffit
            else:
                print(f"[TELNET] {host}:{port} → 0 spots (essai suivant)")
        except Exception as e:
            print(f"[TELNET] {host}:{port} → erreur: {e}")
            continue

    return spots[:max_spots]

# ── ON4KST CHAT (telnet, compte requis) ───────────────────────────────────────
# Accès réservé aux radioamateurs, identifiant + mot de passe personnels.
# Protocole confirmé jusqu'au prompt "Password:" ; le comportement après
# connexion (sélection de salon, format des messages) sera affiné une fois
# testé avec de vrais identifiants — d'où le mode diagnostic ci-dessous, qui
# capture la réponse brute du serveur sans jamais exposer le mot de passe.
def fetch_on4kst_raw(callsign, password, host='www.on4kst.org', port=23000, timeout=10,
                     chat=None, command=None, read_wait=6):
    """
    Connexion telnet à ON4KST : login + password, puis optionnellement
    sélection d'un salon (chat='2' pour 144/432 MHz) et envoi d'une commande.
    Ne renvoie QUE la sortie du serveur (jamais le mot de passe).
    Retourne {'ok': bool, 'raw': str, 'error': str|None}.
    """
    # Espaces/retours parasites en début-fin (copier-coller) : quasi toujours
    # accidentels dans un mot de passe — ON4KST rejette sinon sur la longueur.
    password = (password or '').strip()
    if not callsign or not password:
        return {'ok': False, 'raw': '', 'error': 'Identifiant ou mot de passe ON4KST manquant'}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))

        def read_until(patterns, max_wait=6):
            buf = b''
            deadline = time.time() + max_wait
            while time.time() < deadline:
                try:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                    low = buf.lower()
                    if patterns and any(p in low for p in patterns):
                        break
                except socket.timeout:
                    break
            return buf.decode('utf-8', errors='replace')

        banner = read_until([b'login'])
        s.sendall((callsign.strip() + '\r\n').encode())
        pwd_prompt = read_until([b'password'])
        s.sendall((password + '\r\n').encode())
        # Menu de sélection du salon (ou message d'erreur de login)
        after_login = read_until([b'choice', b'invalid', b'bad password'])

        raw = banner + pwd_prompt + after_login
        login_failed = any(kw in raw.lower() for kw in ('invalid', 'incorrect', 'bad password', 'denied', 'refused'))
        if login_failed:
            s.close()
            return {'ok': False, 'raw': raw, 'error': 'Identifiants refusés par ON4KST'}

        if chat:
            s.sendall((str(chat).strip() + '\r\n').encode())
            raw += read_until([], max_wait=read_wait)
        if command:
            cmds = command if isinstance(command, (list, tuple)) else [command]
            for c in cmds:
                s.sendall((c.strip() + '\r\n').encode())
                raw += read_until([], max_wait=read_wait)

        try:
            s.sendall(b'/quit\r\n')
            s.close()
        except Exception:
            pass
        return {'ok': True, 'raw': raw, 'error': None}
    except Exception as e:
        return {'ok': False, 'raw': '', 'error': str(e)}

# Cache ON4KST : une connexion telnet toutes les 4 min maximum — le chat est
# un service communautaire gratuit, on ne le martèle pas à chaque refresh.
_on4kst_cache = {'ts': 0, 'data': None}
ON4KST_CACHE_TTL = 240

def fetch_on4kst_data(callsign, password, chat='2'):
    """
    Récupère depuis le chat ON4KST (salon 2 = 144/432 MHz) :
      - users    : stations connectées [{call, locator, name, present}]
      - messages : derniers messages   [{time, call, text}]
    'present' = False si l'indicatif est entre parenthèses (absent du clavier).
    Résultat mis en cache ON4KST_CACHE_TTL secondes.
    """
    now = time.time()
    if _on4kst_cache['data'] is not None and (now - _on4kst_cache['ts']) < ON4KST_CACHE_TTL:
        return _on4kst_cache['data']

    result = {'users': [], 'messages': [], 'error': None}
    r = fetch_on4kst_raw(callsign, password, chat=chat,
                         command=['/SHOW USER', '/SHOW MSG 25'], read_wait=7)
    if not r['ok']:
        result['error'] = r['error']
        return result  # pas de mise en cache d'un échec : on retentera

    seen_users = set()
    for line in r['raw'].splitlines():
        line = line.strip()
        # Message : "0630Z F5JMI Pat 144/432/1296> bonjour ..."
        m_msg = re.match(r'^(\d{4})Z\s+([A-Z0-9/\-]{3,})\s+([^>]*)>\s*(.*)$', line)
        if m_msg:
            text = m_msg.group(4).strip()
            # Messages vides = artefacts de notre propre connexion telnet
            if m_msg.group(2) != 'SERVER' and text:
                result['messages'].append({
                    'time': m_msg.group(1) + 'Z',
                    'call': m_msg.group(2),
                    'text': text[:120],
                })
            continue
        # User : "CALLSIGN   JN15XC Nom..." — parenthèses = absent du clavier
        m_usr = re.match(r'^(\()?([A-Z0-9/\-]{3,})\)?\s+([A-R]{2}\d{2}[A-X]{2})\s*(.*)$', line)
        if m_usr:
            absent, call, loc, name = m_usr.groups()
            if call not in seen_users:
                seen_users.add(call)
                result['users'].append({
                    'call': call, 'locator': loc,
                    'name': name.strip()[:30],
                    'present': not bool(absent),
                })

    _on4kst_cache['ts'] = now
    _on4kst_cache['data'] = result
    print(f"[ON4KST] {len(result['users'])} stations connectées, {len(result['messages'])} messages")
    return result

# ── DXWATCH (spots VHF/UHF avec locators) ────────────────────────────────────
def fetch_dxwatch_vhf(filter_digital=True):
    """DXWatch : API VHF — retourne spots avec locator quand disponible."""
    spots = []
    try:
        content = fetch_url('http://dxwatch.com:8010/dxsd1/dxsd1.php?f=0&v=VHF&t=1', timeout=8)
        if not content:
            return spots
        # Format : DX de SPOTTER: FREQ CALL INFO UTC
        rows = re.findall(
            r'DX de\s+([\w/]+)\s*:\s*([\d.]+)\s+([\w/]+)\s+(.*?)\s+(\d{4})Z',
            content, re.IGNORECASE
        )
        for spotter, freq, call, info, t in rows:
            if filter_digital and is_digital_mode(info):
                continue
            freq_f = float(freq)
            # 144–146, 432–438, 1240–1300 MHz
            if not (144 <= freq_f <= 146 or 432 <= freq_f <= 438 or 1240 <= freq_f <= 1300):
                continue
            # Extraire locator depuis info (ex: JN15XC). Si deux locators sont
            # présents (spotter + DX), le DX est presque toujours le dernier.
            loc_matches = re.findall(r'\b([A-R]{2}[0-9]{2}[A-X]{2})\b', info.upper())
            loc = loc_matches[-1] if loc_matches else ''
            spots.append(_normalize_spot(call, loc, freq_f, spotter, t+'Z', info, 'dxwatch'))
        print(f"[DXWATCH] {len(spots)} spots VHF")
    except Exception as e:
        print(f"[DXWATCH] Erreur: {e}")
    return spots[:20]

# ── HAMQTH SPOTS (API XML avec locators) ──────────────────────────────────────
def fetch_hamqth_spots(filter_digital=True):
    """HamQTH DX lite : API XML — très bons locators, toutes bandes."""
    spots = []
    try:
        content = fetch_url('https://www.hamqth.com/dxlite.php', timeout=8)
        if not content:
            return spots
        rows = re.findall(r'<spot>(.*?)</spot>', content, re.DOTALL)
        for row in rows:
            def tag(t): m = re.search(fr'<{t}>(.*?)</{t}>', row); return m.group(1).strip() if m else ''
            freq_s = tag('freq')
            try: freq_f = float(freq_s)
            except: continue
            if not (144 <= freq_f <= 146 or 432 <= freq_f <= 438 or 1240 <= freq_f <= 1300):
                continue
            info = tag('remarks')
            if filter_digital and is_digital_mode(info):
                continue
            call    = tag('dx')
            spotter = tag('de')
            t       = tag('time')
            # Si deux locators apparaissent dans le commentaire (spotter + DX),
            # le DX est presque toujours le dernier.
            loc_ms  = re.findall(r'\b([A-R]{2}[0-9]{2}[A-X]{2})\b', info.upper())
            loc     = loc_ms[-1] if loc_ms else ''
            spots.append(_normalize_spot(call, loc, freq_f, spotter, t, info, 'hamqth'))
        print(f"[HAMQTH] {len(spots)} spots VHF")
    except Exception as e:
        print(f"[HAMQTH] Erreur: {e}")
    return spots[:20]

# ── HAMSPIRIT.DE (cluster VHF allemand/suisse, excellent pour DX vers JN15) ──
def fetch_hamspirit_vhf(band_mhz=144, filter_digital=True):
    """Hamspirit.de : cluster VHF/UHF allemand — proximité géographique idéale."""
    spots = []
    try:
        url = f'https://www.hamspirit.de/dxspot/dx.php?mode=spots&band={band_mhz}'
        content = fetch_url(url, timeout=8)
        if not content:
            return spots
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', content, re.DOTALL|re.IGNORECASE)
        for row in rows:
            cells = [re.sub(r'<[^>]+>','',c).strip()
                     for c in re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL|re.IGNORECASE)]
            cells = [c for c in cells if c]
            if len(cells) < 4:
                continue
            info = ' '.join(cells)
            if filter_digital and is_digital_mode(info):
                continue
            call_m = re.search(r'\b([A-Z0-9]{3,}(?:/[A-Z0-9]+)?)\b', info)
            if not call_m:
                continue
            call = call_m.group(1)
            # Si deux locators apparaissent (spotter + DX), le DX est presque
            # toujours le dernier.
            loc_ms = re.findall(r'\b([A-R]{2}[0-9]{2}[A-X]{2})\b', info.upper())
            loc = loc_ms[-1] if loc_ms else ''
            freq_m = re.search(r'(\d{3,4}[\.,]\d{1,3})', info)
            try: freq = float(freq_m.group(1).replace(',','.')) if freq_m else float(band_mhz)
            except: freq = float(band_mhz)
            spots.append(_normalize_spot(call, loc, freq, cells[0] if cells else '', '', info, 'hamspirit'))
        print(f"[HAMSPIRIT] {band_mhz} MHz: {len(spots)} spots")
    except Exception as e:
        print(f"[HAMSPIRIT] Erreur: {e}")
    return spots[:15]

# ── DXMAPS VHF SPOTS (carte propagation — locators précis) ───────────────────
def fetch_dxmaps_spots_vhf(filter_digital=True):
    """DXMaps : spots VHF avec locators extraits de la carte de propagation."""
    spots = []
    try:
        # API JSON non officielle DXMaps (spots bruts avec QRA locator)
        content = fetch_url('https://www.dxmaps.com/spots/mapg.php?Lan=E&Frec=144&ML=M&Map=EU&noimage=1', timeout=10)
        if not content:
            return spots
        # Extraire les lignes de spots DXMaps format: DX:CALL QRA:LOC via SPOTTER
        matches = re.findall(
            r'DX:([A-Z0-9/]+)\s+QRA:([A-R]{2}[0-9]{2}[A-X]{0,2})',
            content, re.IGNORECASE
        )
        for call, loc in matches:
            if filter_digital:
                continue  # DXMaps ne donne pas le mode
            spots.append(_normalize_spot(call, loc, 144.0, '', '', '', 'dxmaps'))
        # Fallback : chercher paires CALL + LOC proches
        if not spots:
            calls = re.findall(r'\b([A-Z][A-Z0-9]{1,2}[0-9][A-Z]{1,3}(?:/P)?)\b', content)
            locs  = re.findall(r'\b([A-R]{2}[0-9]{2}[A-X]{2})\b', content.upper())
            for i, (c, l) in enumerate(zip(calls[:15], locs[:15])):
                spots.append(_normalize_spot(c, l, 144.0, '', '', '', 'dxmaps'))
        print(f"[DXMAPS SPOTS] {len(spots)} spots extraits")
    except Exception as e:
        print(f"[DXMAPS SPOTS] Erreur: {e}")
    return spots[:15]

# ── FUSION DE TOUS LES SPOTS VHF ─────────────────────────────────────────────
def fetch_all_vhf_spots(band_mhz=144, filter_digital=True):
    """Agrège tous les clusters disponibles pour la bande donnée."""
    all_spots = []
    seen_calls = set()

    sources = [
        ('f5len',      fetch_cluster_f5len(band_mhz, filter_digital)),
        ('dxsummit',   fetch_dxsummit('VHF', filter_digital)),
        ('dxwatch',    fetch_dxwatch_vhf(filter_digital)),
        ('hamqth',     fetch_hamqth_spots(filter_digital)),
        ('hamspirit',  fetch_hamspirit_vhf(band_mhz, filter_digital)),
        ('dxmaps',     fetch_dxmaps_spots_vhf(filter_digital)),
    ]

    for src_name, raw_spots in sources:
        for s in raw_spots:
            # Normaliser selon la source
            if isinstance(s, list):
                info_str = ' '.join(s[4:]) if len(s)>4 else ''
                try: freq_v = float(re.sub(r'[^\d.]', '', s[1])) if len(s)>1 else float(band_mhz)
                except: freq_v = float(band_mhz)
                # Certains commentaires VHF/Es contiennent DEUX locators (grille du
                # spotter D'ABORD, puis celle de la station DX — convention courante
                # pour juger le trajet). re.search() prenait le premier trouvé, donc
                # souvent celui du spotter au lieu du DX → point placé au mauvais
                # endroit sur la carte. On prend le DERNIER match trouvé.
                loc_all = re.findall(r'\b([A-R]{2}[0-9]{2}[A-X]{2})\b', info_str.upper())
                s = _normalize_spot(
                    call=s[0] if len(s)>0 else '',
                    locator=loc_all[-1] if loc_all else '',
                    freq=freq_v,
                    spotter=s[2] if len(s)>2 else '',
                    time_str=s[3] if len(s)>3 else '',
                    info=info_str,
                    source=src_name
                )
            elif isinstance(s, dict) and 'dx' in s:
                # format dxsummit — même souci que ci-dessus : si le commentaire
                # contient le locator du spotter ET celui du DX, le DX est
                # presque toujours le dernier trouvé.
                loc_ms = re.findall(r'\b([A-R]{2}[0-9]{2}[A-X]{2})\b', str(s.get('info','')).upper())
                s = _normalize_spot(
                    call=s.get('dx',''),
                    locator=loc_ms[-1] if loc_ms else '',
                    freq=s.get('freq',float(band_mhz)),
                    spotter=s.get('spotter',''),
                    time_str=s.get('time',''),
                    info=s.get('info',''),
                    source=src_name
                )

            call = s.get('call','')
            if not call or len(call) < 3:
                continue
            # Dédoublonner : garder le spot avec locator si possible
            if call not in seen_calls:
                seen_calls.add(call)
                all_spots.append(s)
            else:
                # Mettre à jour si le nouveau spot a un locator et l'ancien non
                for ex in all_spots:
                    if ex['call'] == call and not ex['locator'] and s.get('locator'):
                        ex.update(s)
                        break

    return all_spots

# ─── FETCH LOG ───────────────────────────────────────────────────────────────
def fetch_log_edi(url, filter_digital=True):
    if not url:
        return {'qsos': [], 'score': 0, 'total_qso': 0, 'error': 'URL non configurée'}
    content = fetch_url(url)
    if not content:
        return {'qsos': [], 'score': 0, 'total_qso': 0, 'error': 'Inaccessible'}
    qsos = []
    score = 0
    in_qso = False
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('[QSOrecords'):
            in_qso = True
            continue
        if in_qso and line and not line.startswith('['):
            parts = line.split(';')
            if len(parts) >= 10:
                try:
                    mode = parts[12].strip().upper() if len(parts) > 12 else 'SSB'
                    if filter_digital and mode in MODES_NUMERIQUES:
                        continue
                    pts = int(parts[10]) if len(parts) > 10 and parts[10].strip().isdigit() else 0
                    qsos.append({
                        'date': parts[0], 'time': parts[1],
                        'call': parts[2].strip(), 'locator': parts[9].strip(),
                        'points': pts, 'mode': mode or 'SSB',
                    })
                    score += pts
                except:
                    pass
    return {'qsos': qsos, 'score': score, 'total_qso': len(qsos)}

def fetch_log_adif(url, filter_digital=True):
    if not url:
        return {'qsos': [], 'score': 0, 'total_qso': 0}
    content = fetch_url(url)
    if not content:
        return {'qsos': [], 'score': 0, 'total_qso': 0}
    qsos = []
    records = re.split(r'<EOR>', content, flags=re.IGNORECASE)
    for rec in records:
        call_m = re.search(r'<CALL:\d+>([^\s<]+)', rec, re.IGNORECASE)
        loc_m  = re.search(r'<GRIDSQUARE:\d+>([A-Z0-9]+)', rec, re.IGNORECASE)
        mode_m = re.search(r'<MODE:\d+>([^\s<]+)', rec, re.IGNORECASE)
        freq_m = re.search(r'<FREQ:\d+>([\d.]+)', rec, re.IGNORECASE)
        if call_m:
            mode = mode_m.group(1).upper() if mode_m else 'SSB'
            if filter_digital and mode in MODES_NUMERIQUES:
                continue
            qsos.append({
                'call': call_m.group(1),
                'locator': loc_m.group(1) if loc_m else '',
                'mode': mode,
                'freq': freq_m.group(1) if freq_m else '',
                'points': 0,
            })
    return {'qsos': qsos, 'score': 0, 'total_qso': len(qsos)}


# ─── MODULE 1 : NOAA K-INDEX (Géomagnétisme / Aurore) ───────────────────────
def fetch_noaa_kindex():
    try:
        content = fetch_url('http://services.swpc.noaa.gov/products/noaa-planetary-k-index.json', timeout=8)
        if not content: return None
        data = json.loads(content)
        # Dernière valeur : [datetime, K-index]
        recent = [d for d in data if len(d) >= 2][-3:]
        k_values = []
        for entry in recent:
            try:
                k_values.append(float(entry[1]))
            except: pass
        if not k_values: return None
        k_current = k_values[-1]
        k_max = max(k_values)
        status = 'CALME' if k_current < 3 else 'MODÉRÉ' if k_current < 5 else '⚡ PERTURBÉ' if k_current < 7 else '🔴 TEMPÊTE'
        aurora = k_current >= 5
        return {
            'k_index': k_current,
            'k_max_3h': k_max,
            'status': status,
            'aurora_possible': aurora,
            'summary': f"K={k_current} ({status}){' — Aurore boréale possible sur 144 MHz !' if aurora else ''}"
        }
    except Exception as e:
        print(f"[NOAA] Erreur: {e}")
        return None

# ─── MODULE 2 : DXMAPS (Propagation VHF visuelle) ───────────────────────────
def fetch_dxmaps_vhf():
    try:
        # DXMaps API spots VHF
        content = fetch_url('https://www.dxmaps.com/spots/mapg.php?Lan=E&Frec=144&ML=M&Map=EU', timeout=10)
        if not content: return None
        # Extraire les spots du HTML
        spots = []
        rows = re.findall(r'(\w{3,})\s+→\s+(\w{3,}).*?(\d{3,4})\s*km', content)
        for r in rows[:10]:
            spots.append({'spotter': r[0], 'dx': r[1], 'dist': r[2]})
        # Chercher mentions Es / Tropo
        content_up = content.upper()
        es_active = 'SPORADIC' in content_up or 'ES ' in content_up or 'E-SKIP' in content_up
        tropo_active = 'TROPO' in content_up or 'DUCTING' in content_up
        return {
            'spots': spots,
            'es_active': es_active,
            'tropo_active': tropo_active,
            'summary': f"DXMaps VHF : {'⚡ SPORADIC-E ACTIF' if es_active else ''} {'🌊 TROPO ACTIF' if tropo_active else ''} {len(spots)} spots trouvés"
        }
    except Exception as e:
        print(f"[DXMAPS] Erreur: {e}")
        return None

# ─── MODULE 4 : 3830SCORES (Classement concurrent) ──────────────────────────
def fetch_3830_scores(contest_id, callsign):
    try:
        # 3830scores.com utilise des noms de contests spécifiques
        contest_map = {
            'REF_RPH': 'REF-Points-Hauts',
            'REF_NAT_THF': 'REF-National-THF',
            'REF_IARU_VHF': 'IARU-VHF',
            'CQ_WW_SSB': 'CQ-WW-SSB',
            'CQ_WW_CW': 'CQ-WW-CW',
            'CQ_WPX_SSB': 'CQ-WPX-SSB',
        }
        contest_name = contest_map.get(contest_id, '')
        if not contest_name:
            return None
        url = f'https://www.3830scores.com/{contest_name}/'
        content = fetch_url(url, timeout=10)
        if not content: return None
        # Extraire scores du tableau HTML
        scores = []
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', content, re.DOTALL|re.IGNORECASE)
        for row in rows[:20]:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL|re.IGNORECASE)
            cells = [re.sub(r'<[^>]+>','',c).strip() for c in cells]
            cells = [c for c in cells if c]
            if len(cells) >= 3:
                scores.append(cells[:5])
        # Chercher notre callsign
        our_rank = None
        our_score_data = None
        call_base = callsign.split('/')[0].upper()
        for i, row in enumerate(scores):
            if any(call_base in str(c).upper() for c in row):
                our_rank = i + 1
                our_score_data = row
                break
        return {
            'contest': contest_name,
            'top_scores': scores[:10],
            'our_rank': our_rank,
            'our_data': our_score_data,
            'summary': f"3830Scores : {len(scores)} stations listées" +
                      (f" — Nous sommes #{our_rank}" if our_rank else "")
        }
    except Exception as e:
        print(f"[3830] Erreur: {e}")
        return None

# ─── MODULE 5 : HAMQTH (Lookup indicatif inconnu) ───────────────────────────
def lookup_hamqth(callsign, session_id=None):
    try:
        # HamQTH API libre (sans clé pour lookup basique)
        url = f'https://www.hamqth.com/dxlite.php?q={callsign}'
        content = fetch_url(url, timeout=8)
        if not content: return None
        # Parser XML simple
        grid = re.search(r'<grid>([^<]+)</grid>', content)
        country = re.search(r'<country>([^<]+)</country>', content)
        adif = re.search(r'<adif>([^<]+)</adif>', content)
        continent = re.search(r'<continent>([^<]+)</continent>', content)
        if grid or country:
            result = {
                'call': callsign,
                'locator': grid.group(1) if grid else '',
                'country': country.group(1) if country else '',
                'adif': adif.group(1) if adif else '',
                'continent': continent.group(1) if continent else '',
            }
            print(f"[HAMQTH] {callsign} → {result}")
            return result
        return None
    except Exception as e:
        print(f"[HAMQTH] Erreur {callsign}: {e}")
        return None

def enrich_unknown_calls(done_calls, calldb_path):
    """Cherche sur HamQTH les indicatifs absents de la base locale"""
    if not os.path.exists(calldb_path):
        return {}
    try:
        with open(calldb_path, 'r', encoding='utf-8') as f:
            db = json.load(f)
        calls_db = db.get('calls', {})
        enriched = {}
        count = 0
        for call in list(done_calls.keys())[:5]:  # max 5 lookups par refresh
            base = call.split('/')[0].upper()
            if base not in calls_db or not calls_db[base].get('locator'):
                result = lookup_hamqth(base)
                if result and result.get('locator'):
                    calls_db[base] = {
                        'locator': result['locator'],
                        'country': result.get('country',''),
                        'continent': result.get('continent',''),
                    }
                    enriched[base] = result
                    count += 1
        if count > 0:
            db['calls'] = calls_db
            with open(calldb_path, 'w', encoding='utf-8') as f:
                json.dump(db, f, ensure_ascii=False, separators=(',',':'))
            print(f"[HAMQTH] {count} indicatifs enrichis dans calldb.json")
        return enriched
    except Exception as e:
        print(f"[HAMQTH] Erreur enrichissement: {e}")
        return {}
