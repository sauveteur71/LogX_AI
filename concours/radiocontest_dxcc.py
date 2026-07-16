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
    country, cont, cq, itu, primary = base
    m_cq = re.search(r'\((\d+)\)', alias)
    m_itu = re.search(r'\[(\d+)\]', alias)
    if m_cq:
        cq = int(m_cq.group(1))
    if m_itu:
        itu = int(m_itu.group(1))
    key = re.sub(r'[\(\[<{].*', '', alias).strip()
    return key, (country, cont, cq, itu, primary)


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
            base = (country, cont, cq, itu, primary)
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
            'itu_zone': t[3], 'prefix': t[4]}


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
