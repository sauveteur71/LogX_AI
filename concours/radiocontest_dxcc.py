# -*- coding: utf-8 -*-
"""Base DXCC hors ligne — parseur cty.dat (AD1C, country-files.com).

Attribue pays / continent / zones CQ-ITU à un indicatif SANS réseau, par
correspondance de préfixe le plus long (avec surcharges d'indicatifs exacts
« =CALL » et zones dérogatoires « (zz) [ii] » du format cty.dat).
Chargée une fois au démarrage ; c'est la même base que N1MM/DXLog.

Format d'une entrée cty.dat :
  Nom du pays:  CQ:  ITU:  Cont:  lat:  lon:  UTC:  Préfixe_principal:
      pfx1,pfx2(24)[61],=INDICATIF_EXACT,...;
"""
import os
import re

CTY_FILE = 'cty.dat'

# prefix → (country, continent, cq_zone, itu_zone, primary_prefix)
_PREFIXES = {}
# indicatif exact → idem (entrées =CALL)
_EXACT = {}
_loaded = False


def _parse_alias(alias, base):
    """'UA9(17)[30]' → clé 'UA9' + zones dérogatoires appliquées à base."""
    country, cont, cq, itu, primary, lat, lon = base
    m_cq = re.search(r'\((\d+)\)', alias)
    m_itu = re.search(r'\[(\d+)\]', alias)
    if m_cq:
        cq = int(m_cq.group(1))
    if m_itu:
        itu = int(m_itu.group(1))
    key = re.sub(r'[\(\[<{].*', '', alias).strip()
    return key, (country, cont, cq, itu, primary, lat, lon)


def load_cty(path=None):
    """Charge cty.dat. Silencieusement dégradé si absent (repli heuristique)."""
    global _loaded
    path = path or CTY_FILE
    if not os.path.exists(path):
        print(f"[DXCC] {path} absent — repli heuristique préfixes")
        _loaded = True
        return
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            content = f.read()
        for entry in content.split(';'):
            entry = entry.strip()
            if not entry:
                continue
            head, _, aliases = entry.partition('\n')
            fields = [x.strip() for x in head.split(':')]
            if len(fields) < 8:
                continue
            country = fields[0]
            try:
                cq, itu = int(fields[1]), int(fields[2])
            except ValueError:
                continue
            cont = fields[3]
            primary = fields[7].lstrip('*')  # * = entité hors liste DXCC (WAE)
            # Centroïde du pays — ATTENTION convention cty.dat : longitude
            # POSITIVE = OUEST, on la remet en positif-Est.
            try:
                lat, lon = float(fields[4]), -float(fields[5])
            except ValueError:
                lat = lon = None
            base = (country, cont, cq, itu, primary, lat, lon)
            for alias in aliases.replace('\n', '').split(','):
                alias = alias.strip()
                if not alias:
                    continue
                if alias.startswith('='):
                    key, val = _parse_alias(alias[1:], base)
                    _EXACT[key.upper()] = val
                else:
                    key, val = _parse_alias(alias, base)
                    if key:
                        _PREFIXES[key.upper()] = val
        print(f"[DXCC] {len(_PREFIXES)} prefixes + {len(_EXACT)} indicatifs exacts (cty.dat)")
    except Exception as e:
        print(f"[DXCC] Erreur de chargement {path}: {e}")
    _loaded = True


def lookup(callsign):
    """Indicatif → {'country', 'continent', 'cq_zone', 'itu_zone', 'prefix'}
    ou None si inconnu. Le /P, /QRP... est ignoré ; F/ON4ABC → préfixe F."""
    if not _loaded:
        load_cty()
    if not callsign:
        return None
    call = callsign.upper().strip()
    # Indicatif exact d'abord (ex: =4U1ITU)
    if call in _EXACT:
        return _as_dict(_EXACT[call])
    # Gestion des barres : garder la partie la plus significative
    if '/' in call:
        parts = [p for p in call.split('/') if p and p not in
                 ('P', 'M', 'MM', 'AM', 'QRP', 'A') and not p.isdigit()]
        # F/ON4ABC : le préfixe hôte (le plus court) prime s'il matche seul
        parts.sort(key=len)
        for p in parts:
            r = _longest_prefix(p)
            if r:
                return r
        return None
    return _longest_prefix(call)


def _longest_prefix(call):
    for length in range(min(len(call), 7), 0, -1):
        hit = _PREFIXES.get(call[:length])
        if hit:
            return _as_dict(hit)
    return None


def _as_dict(t):
    return {'country': t[0], 'continent': t[1], 'cq_zone': t[2],
            'itu_zone': t[3], 'prefix': t[4], 'lat': t[5], 'lon': t[6]}


# ─── MISE À JOUR AUTOMATIQUE ─────────────────────────────────────────────────
CTY_URL = 'https://www.country-files.com/cty/cty.dat'
CTY_MAX_AGE_DAYS = 30


def _cty_age_days(path=None):
    """Âge du fichier en jours, None s'il n'existe pas."""
    import time
    path = path or CTY_FILE
    if not os.path.exists(path):
        return None
    return (time.time() - os.path.getmtime(path)) / 86400


def _looks_valid_cty(content):
    """Garde-fou avant de remplacer la base : jamais un fichier corrompu
    ou une page d'erreur à la place de cty.dat."""
    if not content or len(content) < 50000:
        return False
    if 'France' not in content or 'United States' not in content:
        return False
    return content.count(';') > 300


def update_cty_if_stale(max_age_days=CTY_MAX_AGE_DAYS, force=False):
    """Rafraîchit cty.dat depuis country-files.com s'il a plus de N jours
    (AD1C le met à jour plusieurs fois par mois avant les gros concours).
    Validation stricte avant remplacement, écriture atomique, rechargement
    à chaud. Sans réseau : conserve silencieusement le fichier actuel."""
    age = _cty_age_days()
    if not force and age is not None and age < max_age_days:
        return False
    from radiocontest_utils import fetch_url
    data = fetch_url(CTY_URL, timeout=30)
    if not _looks_valid_cty(data or ''):
        if age is not None:
            print("[DXCC] Mise a jour cty.dat impossible (reseau/contenu) - "
                  f"fichier actuel conserve (age {age:.0f} j)")
        return False
    import tempfile
    target_dir = os.path.dirname(os.path.abspath(CTY_FILE)) or '.'
    fd, tmp = tempfile.mkstemp(prefix='cty.', suffix='.tmp', dir=target_dir)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            f.write(data)
        os.replace(tmp, CTY_FILE)
    except Exception as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        print(f"[DXCC] Ecriture cty.dat impossible: {e}")
        return False
    # Rechargement à chaud (les dicts sont mutés en place, les imports
    # par référence restent valides)
    _PREFIXES.clear()
    _EXACT.clear()
    global _loaded
    _loaded = False
    load_cty()
    print(f"[DXCC] cty.dat mis a jour"
          + (f" (l'ancien avait {age:.0f} j)" if age is not None else " (nouveau)"))
    return True


def country_key(callsign):
    """Clé pays stable pour les sets de multiplicateurs DXCC ('K', 'DL'...).
    Repli : 2 premiers caractères (ancien comportement) si inconnu."""
    r = lookup(callsign)
    if r:
        return r['prefix']
    base = (callsign or '').split('/')[0].upper()
    return base[:2] if base else '??'


def continent(callsign, default='EU'):
    """Continent ('EU','AS','NA','SA','AF','OC','AN') avec repli explicite."""
    r = lookup(callsign)
    return r['continent'] if r else default


def cq_zone(callsign):
    r = lookup(callsign)
    return r['cq_zone'] if r else None
