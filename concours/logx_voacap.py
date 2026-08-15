"""Prédiction de propagation HF point-à-point via le vrai moteur VOACAP
(NTIA/ITS, voacapl.exe compilé depuis les sources officielles -- voir
concours/voacap/win64/). Windows uniquement pour l'instant (binaire natif
vendu dans le dépôt) ; voacap_available() renvoie False ailleurs.

Contrairement à logx_paths.py (heuristique solaire/MUF simplifiée), ce
module lance un calcul scientifique complet : ionosphère CCIR, pertes de
trajet, probabilité de fiabilité par heure/fréquence.
"""
import os
import platform
import re
import shutil
import subprocess
import threading
import time
import uuid

from logx_utils import bearing, haversine
from logx_clusters import get_ssn_cached, get_solar_cached, sfi_to_ssn_fallback
import logx_bootstrap


def _resolve_voacap_root():
    """voacapl.exe ecrit TOUJOURS son sous-dossier run/ (gain01.dat,
    gain02.dat, nos .dat/.out) sous le repertoire racine qu'on lui passe en
    argument -- confirme empiriquement, aucun moyen de le rediriger
    ailleurs. En mode PyInstaller fige, resource_dir() (sys._MEIPASS) est en
    lecture seule (voir logx_bootstrap.py) : y placer la racine ferait
    echouer l'ecriture de run/ des le premier calcul. On copie donc l'arbre
    voacap/ vers le dossier utilisateur inscriptible au premier lancement
    fige -- meme pattern que _SEED_FILES dans logx_bootstrap.py, adapte a
    un dossier entier plutot qu'a des fichiers plats."""
    src_root = os.path.join(logx_bootstrap.resource_dir(), 'voacap', 'win64')
    if not logx_bootstrap.is_frozen():
        return src_root
    dst_root = os.path.join(logx_bootstrap.user_data_dir(), 'voacap', 'win64')
    if not os.path.isdir(dst_root) and os.path.isdir(src_root):
        try:
            shutil.copytree(src_root, dst_root)
        except OSError:
            return src_root  # repli sur la racine embarquee (echouera si vraiment lecture seule, mais rien de mieux a faire)
    return dst_root if os.path.isdir(dst_root) else src_root


_VOACAP_ROOT = _resolve_voacap_root()
_VOACAP_EXE = os.path.join(_VOACAP_ROOT, 'voacapl.exe')
_ITSHFBC = os.path.join(_VOACAP_ROOT, 'itshfbc')
_RUN_DIR = os.path.join(_ITSHFBC, 'run')

# gain01.dat/gain02.dat sont des noms FIXES que voacapl.exe régénère lui-même
# à chaque calcul dans <root>/run/ (aucun moyen de les personnaliser par
# appel -- confirmé en lisant decred.for) : deux calculs concurrents
# écraseraient les fichiers l'un de l'autre en plein calcul. D'où ce verrou
# global -- un seul calcul VOACAP à la fois, quel que soit l'appelant.
_lock = threading.Lock()

# Seuil de SNR requis par mode -- VOACAP ne connaît pas nativement les modes
# amateurs, seulement un REQ.SNR generique (carte SYSTEM, en dB-Hz) compare
# a son propre SNR predit pour calculer le REL% affiche. Valeurs CW/SSB
# reverifiees le 15/08/2026 contre TROIS pages officielles voacap.com (les
# anciennes, CW=6/SSB=24, etaient nettement sous-evaluees et gonflaient
# artificiellement le REL% affiche a l'operateur) :
#   - https://www.voacap.com/2023/understanding/rel.html : "As a rule of
#     thumb ... for CW the REQ.SNR can be, say, 19/24 and for SSB, 45."
#   - https://www.voacap.com/2023/understanding/10mistakes.html : "a common
#     start value for CW is 19/24, 40 for SSB" -- confirme la fourchette
#     19-24 pour CW, mais donne 40 (pas 45) pour SSB.
#   - https://voacap.blogspot.com/2018/04/minor-changes-in-reqsnr-values-and-new.html
#     (blog officiel VOACAP) : formule REQ.SNR[dB-Hz] = SNR[dB] +
#     10*log10(BW), table de seuils K1JT (2500 Hz) -> CW = -15 dB -> 19
#     dB-Hz (concorde), SSB = 10 dB -> 44 dB-Hz -- l'auteur juge lui-meme
#     ce +10 dB "trop pessimiste" pour SSB et evoque 38 dB-Hz (5 dB/2100 Hz)
#     comme alternative plus proche des pratiques etablies, SANS l'adopter
#     officiellement.
# CW=19 est donc solidement corrobore par les 3 sources (borne basse de
# 19/24). Pour SSB, les valeurs officielles vont de 40 a 45 (jamais 38 --
# ce chiffre, propose par l'audit, vient d'une hypothese perso non retenue
# du blog, pas de la doc). Retenu : 45, regle du pouce de la page
# specifiquement dediee au calcul du REL% (rel.html, la plus directement
# pertinente pour ce bug).
# DIGITAL reste volontairement PRUDENT (pas les -21 dB de decodage FT8 en
# conditions extremes -- non concerne par cet audit) pour rester une
# estimation comparative de bande/heure utile, pas une promesse de decodage.
REQUIRED_SNR_DB = {'CW': 19.0, 'SSB': 45.0, 'DIGITAL': 10.0}

# 80/40/30/20/17/15/12/10m -- 8 des 11 emplacements FREQUENCY disponibles.
HAM_BANDS_MHZ = [3.5, 7.0, 10.1, 14.0, 18.1, 21.0, 24.9, 28.0]

_DEFAULT_ANTENNA = 'default/swwhip.voa'  # antenne fouet HF omnidirectionnelle
                                          # modeste -- défaut réaliste pour
                                          # deux stations radioamateur, pas
                                          # le réseau rideau 17 dBi de la
                                          # VOA (const17.voa, gardé comme
                                          # référence de test mais jamais
                                          # utilisé comme défaut ici).


def voacap_available():
    return platform.system() == 'Windows' and os.path.isfile(_VOACAP_EXE)


def _fit_field(val, width, max_dec):
    """Formate un nombre dans un champ Fortran de largeur fixe, en réduisant
    les décimales si besoin (ex. SSN=110 ne rentre pas en F5.2 mais rentre
    en F5.1 : '110.0'). Fortran accepte un nombre de décimales inférieur à
    celui déclaré dans le FORMAT tant qu'un point décimal explicite est
    présent -- confirmé en testant contre le vrai binaire."""
    for d in range(max_dec, -1, -1):
        s = f"{val:{width}.{d}f}"
        if len(s) == width:
            return s
    raise ValueError(f"valeur {val} trop grande pour un champ de {width} caracteres")


def _fit_int(val, width):
    s = f"{int(round(val)):{width}d}"
    if len(s) != width:
        raise ValueError(f"entier {val} trop grand pour un champ de {width} caracteres")
    return s


def _card(name, *parts):
    return name.ljust(10) + "".join(parts)


def _lat_dir(lat):
    return 'N' if lat >= 0 else 'S'


def _lon_dir(lon):
    return 'E' if lon >= 0 else 'W'


def _antenna_card(iat, iantr, power_kw, antfile=_DEFAULT_ANTENNA):
    return _card(
        "ANTENNA",
        _fit_int(iat, 5), _fit_int(iantr, 5), _fit_int(2, 5), _fit_int(30, 5),
        _fit_field(0.0, 10, 3), " ", f"{antfile:<21s}", " ",
        _fit_field(0.0, 5, 1), _fit_field(power_kw, 10, 4),
    )


def build_dat(tx_lat, tx_lon, rx_lat, rx_lon, month, year, ssn, freqs_mhz,
              power_w=100.0, mode='SSB', tx_label='TX', rx_label='RX'):
    """Construit le contenu d'un fichier .DAT VOACAP (format à colonnes
    fixes -- chaque largeur de champ a été vérifiée empiriquement contre le
    vrai binaire compilé, pas déduite des seules FORMAT Fortran)."""
    if len(freqs_mhz) > 11:
        raise ValueError("VOACAP n'accepte que 11 frequences au maximum par calcul")
    freqs = (list(freqs_mhz) + [0.0] * 11)[:11]
    required_snr_db = REQUIRED_SNR_DB.get(mode, REQUIRED_SNR_DB['SSB'])

    lines = [
        _card("COMMENT", "Genere par LogX AI"),
        "LINEMAX      55       number of lines-per-page",
        _card("COEFFS", "CCIR"),
        _card("TIME", _fit_int(1, 5), _fit_int(24, 5), _fit_int(1, 5), _fit_int(1, 5)),
        _card("MONTH", _fit_int(year, 5), _fit_field(float(month), 5, 2)),
        _card("SUNSPOT", _fit_field(ssn, 5, 2)),
        _card("LABEL", f"{tx_label[:20]:<20s}{rx_label[:20]:<20s}"),
        _card(
            "CIRCUIT",
            _fit_field(abs(tx_lat), 5, 2), _lat_dir(tx_lat),
            _fit_field(abs(tx_lon), 9, 2), _lon_dir(tx_lon),
            _fit_field(abs(rx_lat), 9, 2), _lat_dir(rx_lat),
            _fit_field(abs(rx_lon), 9, 2), _lon_dir(rx_lon),
            "    ", _fit_int(0, 5),
        ),
        _card(
            "SYSTEM",
            _fit_field(1.0, 5, 2), _fit_field(145.0, 5, 0), _fit_field(3.0, 5, 2),
            _fit_field(90.0, 5, 0), _fit_field(required_snr_db, 5, 2),
            _fit_field(3.0, 5, 2), _fit_field(0.10, 5, 2),
        ),
        _card("FPROB", "1.00 1.00 1.00 0.00"),
        _antenna_card(1, 1, power_w / 1000.0),
        _antenna_card(2, 2, 0.0),
        _card("FREQUENCY", "".join(_fit_field(f, 5, 2) for f in freqs)),
        _card("METHOD", _fit_int(30, 5), _fit_int(0, 5)),
        "EXECUTE",
        "QUIT",
    ]
    return "\r\n".join(lines) + "\r\n"


_TOKEN_RE = re.compile(r'\S+')


def _row_tokens(line, n):
    return line.split()[:n]


def _row_tokens_by_span(line, spans, n):
    # Le champ MODE peut contenir un espace interne (ex. "4 E" = 4 sauts,
    # couche E) : un simple split() y fusionne/decale les colonnes. On
    # decoupe donc a la position exacte (span) deduite de la ligne REL
    # (jamais ambigue -- ses valeurs n'ont jamais d'espace interne).
    return [line[s:e].strip() for s, e in spans[:n]]


def _parse_out(content, freqs_mhz):
    n = len(freqs_mhz)
    hours = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\r")
        if line.rstrip().endswith("FREQ"):
            toks = line.split()
            try:
                hour = int(float(toks[0]))
            except ValueError:
                i += 1
                continue
            # MUFday et "S DBW" (signal recu median, dBW) sont deja presentes
            # dans la sortie brute de voacapl.exe (voir _REAL_OUT_EXCERPT dans
            # tests/test_voacap.py) mais n'etaient jusqu'ici jamais recherchees
            # -- silencieusement perdues. "S DBW" (avec l'espace interne) est
            # distinguee de "N DBW" (bruit, non extrait ici, hors demande) en
            # matchant le suffixe complet plutot que le seul mot "DBW".
            raw = {"MODE": None, "REL": None, "SNR": None, "MUFday": None, "S DBW": None}
            j = i + 1
            while j < len(lines) and j < i + 25:
                bline = lines[j].rstrip("\r").rstrip()
                for key in raw:
                    if bline.endswith(key):
                        raw[key] = bline
                j += 1
                if bline.endswith("REL"):
                    break

            block = {}
            spans = [m.span() for m in _TOKEN_RE.finditer(raw['REL'])][:n] if raw['REL'] else []
            block['REL'] = _row_tokens(raw['REL'], n) if raw['REL'] else None
            block['SNR'] = _row_tokens(raw['SNR'], n) if raw['SNR'] else None
            block['MODE'] = _row_tokens_by_span(raw['MODE'], spans, n) if raw['MODE'] and spans else None
            block['MUFday'] = _row_tokens(raw['MUFday'], n) if raw['MUFday'] else None
            block['SDBW'] = _row_tokens(raw['S DBW'], n) if raw['S DBW'] else None

            bands = []
            for k, f in enumerate(freqs_mhz):
                def _get(arr, conv):
                    if not arr or k >= len(arr):
                        return None
                    v = arr[k]
                    if v == '-' or v == '':
                        return None
                    try:
                        return conv(v)
                    except ValueError:
                        return None
                bands.append({
                    'freq_mhz': f,
                    'rel': _get(block['REL'], float),
                    'snr_db': _get(block['SNR'], float),
                    'mode': _get(block['MODE'], str),
                    # Fraction (0-1) des jours du mois ou la MUF atteint/depasse
                    # cette frequence -- pas une reliabilite de circuit (REL).
                    'muf_day': _get(block['MUFday'], float),
                    # Puissance de signal recue mediane predite, en dBW.
                    'sdbw': _get(block['SDBW'], float),
                })
            hours.append({'hour': hour, 'bands': bands})
            i = j
        else:
            i += 1
    return hours


def resolve_ssn():
    """SSN mensuel lisse pour VOACAP, avec repli : NOAA/SWPC (source
    primaire) -> conversion depuis le SFI N0NBH deja en cache (repli) ->
    None si aucune donnee solaire n'est disponible (ne JAMAIS inventer une
    valeur -- une fausse SSN produirait une prediction fausse en silence)."""
    ssn_data = get_ssn_cached()
    if ssn_data.get('ssn_smoothed') is not None:
        return ssn_data['ssn_smoothed']
    solar = get_solar_cached()
    if solar.get('sfi'):
        return sfi_to_ssn_fallback(solar['sfi'])
    return None


def predict(tx_lat, tx_lon, rx_lat, rx_lon, month=None, year=None, ssn=None,
            freqs_mhz=None, power_w=100.0, mode='SSB',
            tx_label='TX', rx_label='RX', timeout=60):
    if not voacap_available():
        return {'ok': False, 'error': "Moteur VOACAP indisponible sur cette plateforme (Windows uniquement)."}

    now = time.gmtime()
    month = month or now.tm_mon
    year = year or now.tm_year
    freqs_mhz = freqs_mhz or HAM_BANDS_MHZ

    if ssn is None:
        ssn = resolve_ssn()
    if ssn is None:
        return {'ok': False, 'error': "Aucune donnee d'activite solaire disponible (NOAA/SWPC et repli SFI injoignables) : impossible de calculer une prediction VOACAP fiable."}
    # sfi_to_ssn_fallback() ne renvoie pas une valeur arrondie (contrairement
    # au SSN NOAA deja arrondi a 1 decimale dans fetch_ssn()) -- uniformise
    # ici quelle que soit la source, plutot que de laisser fuiter un float
    # a 14 decimales jusque dans l'affichage.
    ssn = round(ssn, 1)

    dat_content = build_dat(
        tx_lat, tx_lon, rx_lat, rx_lon, month, year, ssn, freqs_mhz,
        power_w=power_w, mode=mode, tx_label=tx_label, rx_label=rx_label,
    )

    os.makedirs(_RUN_DIR, exist_ok=True)
    token = uuid.uuid4().hex[:12]
    dat_name = f"lx_{token}.dat"
    out_name = f"lx_{token}.out"
    dat_path = os.path.join(_RUN_DIR, dat_name)
    out_path = os.path.join(_RUN_DIR, out_name)

    with _lock:
        try:
            with open(dat_path, "w", newline="") as f:
                f.write(dat_content)
            r = subprocess.run(
                [_VOACAP_EXE, _ITSHFBC, dat_name, out_name],
                capture_output=True, text=True, cwd=_RUN_DIR, timeout=timeout,
            )
            if r.returncode != 0 or not os.path.isfile(out_path):
                return {'ok': False, 'error': f"Echec du calcul VOACAP (code {r.returncode}): {r.stderr.strip()[:300]}"}
            with open(out_path, "r", errors="replace") as f:
                out_content = f.read()
        finally:
            for p in (dat_path, out_path,
                      os.path.join(_RUN_DIR, "gain01.dat"),
                      os.path.join(_RUN_DIR, "gain02.dat")):
                try:
                    os.remove(p)
                except OSError:
                    pass

    hours = _parse_out(out_content, freqs_mhz)
    if not hours:
        return {'ok': False, 'error': "Le moteur VOACAP n'a produit aucun resultat exploitable."}

    dist_km = haversine(tx_lat, tx_lon, rx_lat, rx_lon)
    az = bearing(tx_lat, tx_lon, rx_lat, rx_lon)
    back_az = bearing(rx_lat, rx_lon, tx_lat, tx_lon)

    return {
        'ok': True,
        'distance_km': round(dist_km, 1),
        'azimuth_deg': round(az, 1),
        'back_azimuth_deg': round(back_az, 1),
        'ssn': ssn,
        'month': month,
        'year': year,
        'mode': mode,
        'power_w': power_w,
        'freqs_mhz': freqs_mhz,
        'hours': hours,
    }
