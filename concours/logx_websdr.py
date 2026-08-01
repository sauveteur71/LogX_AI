# -*- coding: utf-8 -*-
"""Annuaire WebSDR vivant : ~850 récepteurs, leur état en direct, et le lien
fréquence qui en fait un outil de contest.

CE QUE LA VERSION PRÉCÉDENTE ÉTAIT : sept stations écrites en dur, vérifiées à
la main (elles survivent, versées dans la couche curée avec leurs notes). CE
QUE LES MESURES ONT MONTRÉ (01/08/2026, sondes réelles sur les neuf sources
fournies par l'opérateur) :

  - LA COUCHE VIVANTE : la liste KiwiSDR de Pierre Ynard (rx.linkfanel.net,
    licence GPLv3+, régénérée toutes les ~2 minutes depuis les annonces
    volontaires des propriétaires). UN SEUL fichier JS = l'état de TOUT le
    parc : 834 récepteurs mesurés, 100 % avec GPS, occupation en direct
    (users/users_max), SNR mesuré, uptime. Conséquence décisive : vérifier
    « que les stations fonctionnent » ne demande AUCUNE sonde vers les
    récepteurs eux-mêmes — on télécharge une liste faite pour ça, à un rythme
    poli (15 min), et personne n'est martelé.
  - LA COUCHE CURÉE (websdr_cures.json, embarquée) : stations extraites des
    listes françaises et européennes fournies (REF, F5KIA, PDF dxrn, quelques
    WebSDR classiques dont Twente) + les sept historiques, provenance PAR
    ENTRÉE. Le tri est éditorial et assumé : sur 127 extraites, 95 étaient
    mortes — le PDF européen date de 2018, la mortalité des hôtes dyndns est
    massive. Ne sont embarquées que les joignables du jour de l'extraction et
    TOUTES les françaises (une station FR éteinte peut revenir, et c'est le
    public de ce logiciel).
  - abandonné en connaissance de cause : le flux interne de websdr.org (XHR
    non documenté, 404 sur toutes les formes essayées) — les classiques
    passent par la couche curée, sondés doucement.

LE CACHE SUIT LE MOTIF TLE (logx_sat_passes, même contrainte d'expédition) :
sur disque, âge toujours remonté, et JAMAIS écrasé par une réponse
inexploitable — un portail captif répond 200 avec sa page de connexion, y
perdre le dernier état connu serait le seul vrai échec possible.

LES URL D'ÉCOUTE : un KiwiSDR s'ouvre directement sur une fréquence — syntaxe
VÉRIFIÉE sur la doc officielle (kiwisdr.com/info : « mykiwi/?f=7021.3cw »,
kHz + mode collé). C'est ce qui transforme l'annuaire en outil de contest :
s'écouter sur le récepteur au meilleur SNR proche du QTH, ou écouter un spot
depuis un récepteur proche du DX. Pour les WebSDR classiques, le paramètre
`?tune=` est une CONVENTION D'USAGE non vérifiable sur une doc officielle
(traité en JS côté récepteur) : au pire, le récepteur s'ouvre sur sa fréquence
par défaut — le lien reste utilisable.
"""
import json
import math
import os
import re
import threading

from logx_utils import locator_to_latlon, haversine, bearing

KIWI_URL = 'http://rx.linkfanel.net/kiwisdr_com.js'
KIWI_CACHE = 'websdr_kiwis.json'          # gitignoré : donnée vivante
CURES_FICHIER = 'websdr_cures.json'       # embarqué : sélection éditoriale
ETAT_CURES_CACHE = 'websdr_etat_cures.json'   # gitignoré : sondes

# Étiquettes d'affichage de l'âge du jeu — le fichier source est régénéré
# toutes les ~2 min ; au-delà, on n'a plus un état, on a un souvenir. Jamais
# utilisées pour refuser de servir (contrainte d'expédition).
AGE_FRAIS_S = 30 * 60
AGE_VIEUX_S = 6 * 3600

_lock = threading.Lock()


def _chemin(nom, dossier=None):
    return os.path.join(dossier or os.path.dirname(os.path.abspath(__file__)), nom)


# ─── Couche vivante : les KiwiSDR de linkfanel ──────────────────────────────

def parser_kiwis(texte_js):
    """Le fichier est du JS (`var kiwisdr_com = [...]`), pas du JSON strict :
    virgule finale tolérée (le premier essai de parse a échoué dessus, mesuré).
    Rend une liste NORMALISÉE — on ne garde que ce que la page consomme, pas
    les 40 champs de télémétrie."""
    t = texte_js or ''
    i, j = t.find('['), t.rfind(']')
    if i < 0 or j <= i:
        return []
    brut = re.sub(r',\s*\]', ']', t[i:j + 1])
    try:
        data = json.loads(brut)
    except ValueError:
        return []
    out = []
    for d in data:
        if not isinstance(d, dict):
            continue
        gps = str(d.get('gps') or '')
        m = re.match(r'\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?', gps)
        lat = lon = None
        if m:
            try:
                lat, lon = float(m.group(1)), float(m.group(2))
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    lat = lon = None
            except ValueError:
                lat = lon = None
        try:
            users = int(d.get('users') or 0)
            users_max = int(d.get('users_max') or 0)
        except (TypeError, ValueError):
            users, users_max = 0, 0
        # snr : « 41,38 » = deux mesures. On garde la SECONDE quand elle
        # existe : recoupé sur plusieurs entrées du fichier, la première
        # couvre tout le spectre, la seconde la partie haute — c'est celle qui
        # renseigne un opérateur HF.
        snr = None
        ms = re.findall(r'-?\d+', str(d.get('snr') or ''))
        if ms:
            try:
                snr = int(ms[-1])
            except ValueError:
                snr = None
        out.append({
            'type': 'kiwi',
            'nom': str(d.get('name') or '')[:160],
            'url': str(d.get('url') or '').strip(),
            'lat': lat, 'lon': lon,
            'lieu': str(d.get('loc') or '')[:120],
            'grid': str(d.get('grid') or '')[:8],
            'antenne': str(d.get('antenna') or '')[:120],
            'users': users, 'users_max': users_max,
            'snr': snr,
            'en_ligne': str(d.get('offline', 'no')).lower() != 'yes',
            'bandes': str(d.get('bands') or ''),
        })
    return [s for s in out if s['url'].startswith('http')]


def rafraichir_kiwis(dossier=None, timeout=25):
    """Télécharge la liste et met le cache à jour. {'ok', 'nb'|'error'}.
    NE REMPLACE JAMAIS un cache valide par du vide — même garde que les TLE :
    un portail captif « réussit » avec zéro récepteur."""
    from logx_utils import fetch_url
    from logx_storage import save_json_atomic
    import datetime
    try:
        texte = fetch_url(KIWI_URL, timeout=timeout)
    except Exception as e:
        return {'ok': False, 'error': 'Réseau indisponible : %s' % e}
    stations = parser_kiwis(texte)
    if len(stations) < 50:
        return {'ok': False,
                'error': 'Réponse inexploitable (%d récepteur(s) lus) — cache '
                         'conservé' % len(stations)}
    save_json_atomic(_chemin(KIWI_CACHE, dossier), {
        'recupere': datetime.datetime.utcnow().isoformat(),
        'source': KIWI_URL, 'stations': stations})
    return {'ok': True, 'nb': len(stations)}


def charger_kiwis(dossier=None):
    try:
        with open(_chemin(KIWI_CACHE, dossier), encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict) and d.get('stations'):
            return d
    except Exception:
        pass
    return None


def age_kiwis(cache, maintenant=None):
    """{'secondes','etat','recupere'} ou None si inconnu — on ne prétend pas
    connaître un âge qu'on ignore."""
    import datetime
    if not cache:
        return None
    try:
        t = datetime.datetime.fromisoformat(str(cache.get('recupere')))
    except (TypeError, ValueError):
        return None
    s = ((maintenant or datetime.datetime.utcnow()) - t).total_seconds()
    etat = ('frais' if s < AGE_FRAIS_S else
            'vieux' if s < AGE_VIEUX_S else 'perime')
    return {'secondes': int(s), 'etat': etat, 'recupere': cache.get('recupere')}


# ─── Couche curée : la sélection éditoriale embarquée ───────────────────────

def stations_curees(dossier=None):
    try:
        with open(_chemin(CURES_FICHIER, dossier), encoding='utf-8') as f:
            d = json.load(f)
        return list(d.get('stations') or [])
    except Exception:
        return []


# Pool DÉDIÉ à la sonde — le point le plus important de ce module pour une
# expédition. fetch_url() partage UN pool de 8 threads avec tout le reste de
# l'application (cluster, QRZ, solaire, POTA, mises à jour) et son
# `.result(timeout)` ne débloque que l'APPELANT : le thread abandonné, lui,
# continue. Or un serveur qui envoie un octet toutes les 0,4 s réarme le
# timeout de socket à chaque octet — `resp.read()` ne rend JAMAIS la main et
# le worker est perdu définitivement. Les 43 stations curées sont exactement
# le terrain de ce piège : des hôtes bénévoles, souvent moribonds, sondés
# toutes les heures. Une seule d'entre elles suffisait à vider le pool commun
# en huit heures et à éteindre TOUT le réseau de l'application — sur 360 h
# non-stop, une certitude, pas un risque.
_SONDE_EXECUTOR = None


def _executeur_sonde():
    global _SONDE_EXECUTOR
    with _lock:
        if _SONDE_EXECUTOR is None:
            import concurrent.futures as _cf
            _SONDE_EXECUTOR = _cf.ThreadPoolExecutor(
                max_workers=4, thread_name_prefix='sonde_websdr')
    return _SONDE_EXECUTOR


def _sonde_http(url, timeout=8, max_octets=4096):
    """« Ce récepteur répond-il ? » — en socket brut, et borné POUR DE BON.

    Pourquoi pas urllib : `resp.read(n)` boucle en interne jusqu'à obtenir ses
    n octets, donc un débit au goutte-à-goutte le fait durer des heures sans
    qu'aucune échéance ne soit consultée. `recv()` rend la main dès qu'un
    octet arrive : la date limite est donc vérifiée à CHAQUE tour, et un hôte
    pathologique ne peut plus retenir le thread.

    Rend (vivant, empreinte) — l'empreinte des premiers octets sert à
    reconnaître un portail captif, qui répond la MÊME page à toutes les URL.
    """
    import hashlib
    import socket
    import time as _t
    from urllib.parse import urlsplit
    # Schéma EXIGÉ, jamais deviné. La première version préfixait « http:// »
    # quand l'URL n'avait pas de « // » — ce qui transformait
    # « javascript:alert(1) » en URL http et court-circuitait ce contrôle même.
    u = urlsplit(str(url or '').strip())
    if u.scheme not in ('http', 'https'):
        return False, ''
    hote = u.hostname or ''
    if not hote:
        return False, ''
    try:
        port = u.port or (443 if u.scheme == 'https' else 80)
    except ValueError:
        return False, ''         # port non numérique : URL inexploitable
    if not (0 < port < 65536):
        return False, ''
    chemin = u.path or '/'
    fin = _t.monotonic() + timeout
    s = None
    try:
        s = socket.create_connection((hote, port), timeout=timeout)
        if u.scheme == 'https':
            from logx_utils import SSL_CTX
            s = SSL_CTX.wrap_socket(s, server_hostname=hote)
        s.sendall(('GET %s HTTP/1.0\r\nHost: %s\r\n'
                   'User-Agent: Mozilla/5.0 (compatible; LogXAI/2.0)\r\n'
                   'Connection: close\r\n\r\n'
                   % (chemin, u.netloc)).encode('ascii', 'ignore'))
        morceaux, total = [], 0
        while total < max_octets:
            reste = fin - _t.monotonic()
            if reste <= 0:
                break                      # date limite : on garde ce qu'on a
            s.settimeout(min(reste, 2.0))
            # Le délai qui expire n'est PAS un échec : c'est la fin de la
            # lecture. Laisser l'exception remonter jetait tout le déjà-lu et
            # déclarait mort un récepteur lent qui avait pourtant répondu
            # « HTTP/1.1 200 OK » — mesuré : la ligne de statut était en main,
            # le verdict était quand même False.
            try:
                bloc = s.recv(min(1024, max_octets - total))
            except socket.timeout:
                break
            except OSError:
                break                      # connexion coupée en cours de route
            if not bloc:
                break
            morceaux.append(bloc)
            total += len(bloc)
        brut = b''.join(morceaux)
    except Exception:
        return False, ''
    finally:
        if s is not None:
            try:
                s.close()
            except Exception:
                pass
    if not brut.startswith(b'HTTP/'):
        return False, ''
    try:
        code = int(brut.split(b' ')[1][:3])
    except (IndexError, ValueError):
        return False, ''
    # 2xx/3xx = vivant ; 401/403 = un serveur répond bel et bien (certains
    # récepteurs sont protégés par mot de passe). Le reste est compté mort.
    vivant = 200 <= code < 400 or code in (401, 403)
    # L'empreinte ne vaut QUE si on a capturé assez de page. Un hôte lent ne
    # livre que sa ligne de statut avant l'échéance : plusieurs d'entre eux
    # donneraient des empreintes identiques et déclencheraient à tort la
    # détection de portail captif — mesuré sur huit passes de sonde contre des
    # hôtes au goutte-à-goutte. Une page de connexion, elle, fait des kilo-
    # octets et dépasse largement ce seuil.
    empreinte = (hashlib.sha256(brut).hexdigest()[:16]
                 if len(brut) >= 200 else '')
    return vivant, empreinte


def sonder_cures(dossier=None, timeout=8):
    """Sonde DOUCE des stations curées : une requête par station, UNE passe —
    l'appelant (tâche de fond) décide du rythme, jamais plus d'une fois par
    heure. Les kiwis de linkfanel ne sont PAS sondés : leur état vient déjà du
    fichier central, les sonder serait du martèlement sans information neuve.

    LE RÉSULTAT N'ÉCRASE JAMAIS L'ÉTAT CONNU S'IL EST INEXPLOITABLE — même
    garde que le cache des kiwis et que les TLE. Deux cas mesurés en revue :
    plus de réseau du tout (toutes les sondes échouent : ce n'est pas « les 43
    stations sont mortes cette heure-ci »), et le portail captif d'hôtel, qui
    répond 200 avec SA page de connexion à toutes les URL — il marquerait 43
    stations mortes comme vivantes, et « écouter ce spot » enverrait
    l'opérateur sur un récepteur éteint.
    """
    from logx_storage import save_json_atomic
    import datetime
    urls = [s['url'] for s in stations_curees(dossier) if s.get('url')]
    if not urls:
        return {'ok': False, 'error': 'aucune station curée'}
    ex = _executeur_sonde()
    futs = {u: ex.submit(_sonde_http, u, timeout) for u in urls}
    etat, empreintes = {}, {}
    for u, f in futs.items():
        try:
            # +3 s : la même marge que fetch_url. Un thread qui dépasse est
            # abandonné — mais dans NOTRE pool, jamais dans le pool commun.
            vivant, emp = f.result(timeout=timeout + 3)
        except Exception:
            vivant, emp = False, ''
        etat[u] = vivant
        if emp:
            empreintes[u] = emp
    vivantes = sum(1 for v in etat.values() if v)
    ancien = _etat_cures(dossier)
    if not vivantes and (ancien or {}).get('etat'):
        return {'ok': False, 'nb': 0,
                'error': 'aucune station joignable (réseau coupé ?) — '
                         'état précédent conservé'}
    # Portail captif : la même page rendue pour au moins la moitié des URL
    # vivantes. Deux récepteurs distincts n'ont aucune raison d'octet pour
    # octet servir le même début de page.
    if empreintes:
        from collections import Counter
        _, combien = Counter(empreintes.values()).most_common(1)[0]
        if combien >= max(3, len(empreintes) // 2):
            return {'ok': False, 'nb': vivantes,
                    'error': 'la même page pour %d récepteurs (portail '
                             'captif ?) — état précédent conservé' % combien}
    save_json_atomic(_chemin(ETAT_CURES_CACHE, dossier), {
        'sonde': datetime.datetime.utcnow().isoformat(), 'etat': etat})
    return {'ok': True, 'nb': len(etat), 'vivantes': vivantes}


def _etat_cures(dossier=None):
    try:
        with open(_chemin(ETAT_CURES_CACHE, dossier), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


# ─── L'annuaire fusionné ────────────────────────────────────────────────────

def _url_cle(url):
    """Clé de déduplication : hôte:port, insensible au schéma et au / final.
    Un kiwi français curé est aussi dans linkfanel — deux entrées pour le même
    récepteur feraient deux marqueurs superposés sur la carte."""
    u = re.sub(r'^https?://', '', str(url or '').strip().lower())
    return u.rstrip('/')


def _qualite_kiwi(s):
    """Départage deux annonces du MÊME récepteur : on préfère celle qui sait
    des choses (position, SNR, occupation) et qui se dit en ligne. Aucun
    horodatage par entrée dans le flux : impossible de prendre « la plus
    récente », on prend donc la mieux renseignée."""
    return (1 if s.get('en_ligne') else 0,
            1 if s.get('lat') is not None else 0,
            1 if s.get('snr') is not None else 0,
            1 if s.get('users_max') else 0)


def annuaire(cfg=None, dossier=None):
    """La liste fusionnée + l'âge du jeu vivant. Distance et azimut depuis le
    locator config quand il existe — c'est ce qui permet « le meilleur
    récepteur PRÈS DE CHEZ MOI », le geste contest."""
    kiwis_cache = charger_kiwis(dossier)
    bruts = [s for s in ((kiwis_cache or {}).get('stations') or [])
             if isinstance(s, dict)]
    # Le flux linkfanel contient de VRAIS doublons — mesuré le 01/08/2026 sur
    # le fichier du jour : trois paires d'URL identiques, dont un récepteur
    # annoncé deux fois avec des états divergents (SNR 20 et 19, occupation
    # 2/3 et 1/3). Sans ce tri, deux marqueurs superposés sur la carte et deux
    # lignes contradictoires dans la liste, dont une périmée : l'opérateur
    # peut choisir celle qui annonce une place libre alors qu'il n'y en a
    # plus. On garde l'entrée la mieux renseignée (SNR connu, puis en ligne).
    par_url = {}
    for s in bruts:
        cle = _url_cle(s.get('url'))
        garde = par_url.get(cle)
        if garde is None or _qualite_kiwi(s) > _qualite_kiwi(garde):
            par_url[cle] = s
    kiwis = list(par_url.values())
    vus = set(par_url)

    etat_sonde = (_etat_cures(dossier) or {}).get('etat') or {}
    cures = []
    for s in stations_curees(dossier):
        if _url_cle(s.get('url')) in vus:
            continue                     # déjà dans la couche vivante
        # Position : locator d'abord (c'est ce que publient les pages des
        # récepteurs), lat/lon directes en repli — certaines sources donnent
        # des coordonnées sans grille, et une station sans position ne serait
        # ni sur la carte ni éligible à « écouter ce spot ».
        lat = lon = None
        loc = s.get('locator') or ''
        if loc:
            lat, lon = locator_to_latlon(loc)
        if lat is None:
            try:
                lat, lon = float(s['lat']), float(s['lon'])
                if not (math.isfinite(lat) and math.isfinite(lon)
                        and -90 <= lat <= 90 and -180 <= lon <= 180):
                    lat = lon = None
            except (KeyError, TypeError, ValueError):
                lat = lon = None
        cures.append({
            'type': s.get('type') or 'websdr',
            'nom': s.get('nom', ''), 'url': s.get('url', ''),
            'lat': lat, 'lon': lon,
            'lieu': s.get('lieu', ''), 'grid': loc,
            'antenne': '', 'users': None, 'users_max': None, 'snr': None,
            'en_ligne': etat_sonde.get(s.get('url', '')),   # None = pas sondé
            'bandes': s.get('bandes', ''),
            'pays': s.get('pays', ''),
            'provenance': s.get('provenance', ''),
            'note': s.get('note', ''),
        })

    stations = kiwis + cures

    # Distance/azimut depuis le QTH — les MÊMES fonctions que le reste de
    # l'app (haversine/bearing de logx_utils), pas une réimplémentation.
    mlat, mlon = locator_to_latlon((cfg or {}).get('locator', '') or '')
    if mlat is not None:
        for s in stations:
            if s.get('lat') is not None:
                s['dist_km'] = haversine(mlat, mlon, s['lat'], s['lon'])
                s['azimut'] = bearing(mlat, mlon, s['lat'], s['lon'])

    return {'stations': stations,
            'age': age_kiwis(kiwis_cache),
            'nb_kiwis': len(kiwis), 'nb_cures': len(cures)}


# ─── L'URL d'écoute : le geste contest ──────────────────────────────────────

_MODES_KIWI = {'USB': 'usb', 'LSB': 'lsb', 'CW': 'cw', 'CW-R': 'cwn',
               'AM': 'am', 'FM': 'nbfm', 'FT8': 'usb',
               'FT4': 'usb', 'DIGITAL': 'usb', 'RTTY': 'usb'}


def url_ecoute(station, freq_khz=None, mode=''):
    """URL du récepteur, ouvrant si possible sur la fréquence demandée.

    KiwiSDR : « url/?f=7021.3cw » — kHz + mode collé, syntaxe VÉRIFIÉE sur la
    doc officielle (kiwisdr.com/info). « SSB » est traduit LSB/USB par la
    fréquence, même convention que le pilotage CAT (logx_cat.normaliser_mode :
    LSB sous 10 MHz, USB au-dessus — le numérique reste USB via _MODES_KIWI).

    WebSDR classique : « ?tune=7021cw » — convention d'usage NON vérifiable
    sur une doc officielle (traitée en JS par le récepteur) : au pire il
    s'ouvre sur sa fréquence par défaut, le lien reste bon.
    """
    url = str((station or {}).get('url') or '').strip().rstrip('/')
    # Le schéma est vérifié ICI, pas seulement à l'entrée du parseur : la
    # couche curée est un fichier JSON qu'on peut éditer à la main, et une URL
    # « javascript:… » rendue dans un href serait exécutable au clic.
    if not re.match(r'(?i)^https?://', url):
        return ''
    try:
        khz = float(freq_khz) if freq_khz else None
    except (TypeError, ValueError):
        khz = None
    # isfinite : float('nan') passe les deux tests de signe sans erreur et
    # produirait « ?f=nanusb ». Le même piège avait été attrapé sur les
    # positions du rotor — une valeur non finie n'est pas une fréquence.
    if khz is None or not math.isfinite(khz) or khz <= 0:
        return url
    m = str(mode or '').upper().strip()
    if m in ('SSB', 'PHONE', ''):
        m = 'LSB' if khz < 10000 else 'USB'
    suffixe = _MODES_KIWI.get(m, 'usb')
    if (station or {}).get('type') == 'kiwi':
        return '%s/?f=%.1f%s' % (url, khz, suffixe)
    return '%s/?tune=%d%s' % (url, int(khz), suffixe)


def meilleur_recepteur(stations, pres_de=None, max_km=1500):
    """Le récepteur au meilleur SNR parmi ceux proches d'un point — le cœur
    de « s'écouter » : entendre SON propre signal exige un récepteur assez
    proche pour être dans la zone de skip courte ou l'onde de sol.

    `pres_de` = (lat, lon) ou None (alors : proche du QTH, champ dist_km déjà
    calculé par annuaire()). Ne considère que les récepteurs EN LIGNE avec de
    la place. Rend None si rien ne convient — l'appelant affiche pourquoi.

    DEUX GESTES, DEUX TRIS — un test l'a attrapé avant la mise en service :
      - « s'écouter » (pres_de=None) : tout récepteur du rayon entend ma
        station, autant prendre le MEILLEUR SNR ;
      - « écouter ce spot » (pres_de=position du DX) : la PROXIMITÉ prime —
        un excellent récepteur à 1100 km du DX n'entend pas ce que le DX
        entend ; le SNR ne départage qu'à distance comparable (tranches de
        200 km).
    """
    candidats = []
    for s in stations or []:
        if not s.get('en_ligne'):
            continue
        um = s.get('users_max')
        if um is not None and s.get('users') is not None and s['users'] >= um:
            continue                     # complet : inutilisable maintenant
        if pres_de is not None:
            if s.get('lat') is None:
                continue
            d = haversine(pres_de[0], pres_de[1], s['lat'], s['lon'])
        else:
            d = s.get('dist_km')
            if d is None:
                continue
        if d > max_km:
            continue
        snr = s.get('snr') if s.get('snr') is not None else -1
        candidats.append((d, snr, s))
    if not candidats:
        return None
    if pres_de is not None:
        candidats.sort(key=lambda x: (x[0] // 200, -x[1], x[0]))
    else:
        candidats.sort(key=lambda x: (-x[1], x[0]))
    return candidats[0][2]


def list_websdr():
    """Compatibilité : l'ancien contrat (liste plate) sur les données neuves.
    Conservée parce qu'un client ou un test peut encore l'appeler — elle rend
    désormais la couche curée."""
    return [dict(s) for s in stations_curees()]
