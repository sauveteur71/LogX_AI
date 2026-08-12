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
import threading

CTY_FILE = 'cty.dat'

# prefix → (country, continent, cq_zone, itu_zone, primary_prefix)
_PREFIXES = {}
# indicatif exact → idem (entrées =CALL)
_EXACT = {}
_loaded = False


def _parse_alias(alias, base):
    """'UA9(17)[30]' → clé 'UA9' + zones/position/continent dérogatoires
    appliqués à base. Formats gérés : (cq), [itu], <lat/lon>, {cont}."""
    country, cont, cq, itu, primary, lat, lon = base
    m_cq = re.search(r'\((\d+)\)', alias)
    m_itu = re.search(r'\[(\d+)\]', alias)
    m_geo = re.search(r'<([\-\d.]+)/([\-\d.]+)>', alias)
    m_cont = re.search(r'\{(\w+)\}', alias)
    if m_cq:
        cq = int(m_cq.group(1))
    if m_itu:
        itu = int(m_itu.group(1))
    if m_geo:
        try:
            lat, lon = float(m_geo.group(1)), -float(m_geo.group(2))
        except ValueError:
            pass
    if m_cont:
        cont = m_cont.group(1)
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
    new_prefixes, new_exact = {}, {}
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
                    new_exact[key.upper()] = val
                else:
                    key, val = _parse_alias(alias, base)
                    if key:
                        new_prefixes[key.upper()] = val
        # Bascule ATOMIQUE : une simple réaffectation de nom global est une
        # opération indivisible sous le GIL (STORE_GLOBAL). Un thread lecteur
        # concurrent qui fait `_PREFIXES.get(...)` voit soit l'ANCIENNE table
        # complète, soit la NOUVELLE table complète — jamais un état vide ou
        # partiel, contrairement à clear()+update() qui laisse une fenêtre
        # entre les deux appels. Aucun autre module n'importe _PREFIXES/_EXACT
        # par référence (vérifié par grep) : la réaffectation ne casse aucun
        # alias externe.
        global _PREFIXES, _EXACT
        _PREFIXES = new_prefixes
        _EXACT = new_exact
        print(f"[DXCC] {len(_PREFIXES)} prefixes + {len(_EXACT)} indicatifs exacts (cty.dat)")
    except Exception as e:
        print(f"[DXCC] Erreur de chargement {path}: {e}")
    with _lookup_cache_lock:
        _lookup_cache.clear()   # la table de préfixes a changé : cache obsolète
    _loaded = True


# Cache de résolution indicatif → entité : lookup() est appelé PAR QSO à chaque
# frappe (/log/check) et à chaque poll (build_ranked_spots, validateur, diplômes,
# carte…). Le matching de préfixe se refaisait à chaque fois pour les mêmes
# indicatifs. Vidé au (re)chargement de cty.dat (voir load_cty / update_cty).
_lookup_cache = {}
_MISS = object()
# lookup() (thread HTTP appelant) et load_cty() (thread de fond de mise à
# jour cty.dat, voir update_cty_if_stale) accèdent tous deux à _lookup_cache
# sans coordination avant ce verrou : un lookup() en vol pendant un clear()
# pouvait réinsérer une entrée calculée depuis les ANCIENNES tables juste
# après le vidage, la figeant dans le cache fraîchement vidé jusqu'au
# prochain rechargement (jusqu'à 30 j, voir CTY_MAX_AGE_DAYS).
_lookup_cache_lock = threading.Lock()


def lookup(callsign):
    """Indicatif → {'country', 'continent', 'cq_zone', 'itu_zone', 'prefix'}
    ou None si inconnu. Le /P, /QRP... est ignoré ; F/ON4ABC → préfixe F.
    Résultat mémoïsé (cache vidé à chaque rechargement de cty.dat)."""
    if not _loaded:
        load_cty()
    if not callsign:
        return None
    call = callsign.upper().strip()
    with _lookup_cache_lock:
        cached = _lookup_cache.get(call, _MISS)
        if cached is not _MISS:
            return cached
        r = _lookup_compute(call)
        _lookup_cache[call] = r
        return r


def _lookup_compute(call):
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
    from logx_utils import age_days, fetch_url
    age = age_days(CTY_FILE)
    if not force and age is not None and age < max_age_days:
        return False
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
    # Rechargement à chaud : load_cty() reconstruit les tables dans des dicts
    # locaux puis bascule _PREFIXES/_EXACT par réaffectation atomique — pas
    # besoin de clear() préalable (qui viderait la table AVANT que la
    # nouvelle soit prête) ni de remettre _loaded à False (un thread lecteur
    # concurrent passant par lookup() déclencherait alors lui-même un second
    # load_cty() réentrant sur les mêmes dicts pendant la fenêtre de mise à
    # jour). load_cty() se suffit à lui-même.
    load_cty()
    # world_countries.geojson ne change pas, mais la correspondance
    # préfixe->entité DXCC qu'il matérialise (entity_to_feature_id) dépend de
    # cty.dat — sans invalider ce cache, la carte du monde gardait l'ancienne
    # correspondance jusqu'au redémarrage du process, alors que c'est
    # justement ce que ce module documente comme le déclencheur attendu.
    try:
        import logx_worldmap
        logx_worldmap.invalidate_cache()
    except Exception:
        pass
    print("[DXCC] cty.dat mis a jour"
          + (f" (l'ancien avait {age:.0f} j)" if age is not None else " (nouveau)"))
    return True


# Entités marquées '*' dans cty.dat = ajouts WAE, PAS des entités DXCC à part
# entière (Sicile, Italie africaine, Turquie d'Europe…). Pour la « chasse aux
# pays DXCC » on les replie sur leur entité parente. (Le scoring CQ WW, lui,
# les compte séparément : il continue d'utiliser country_key, inchangé.)
_WAE_PARENT = {
    'IT9': 'I', 'IG9': 'I', 'IH9': 'I',   # Sicile / Italie africaine -> Italie
    'TA1': 'TA',                           # Turquie d'Europe -> Turquie
    'GM/s': 'GM', 'JW/b': 'JW', '4U1V': 'OE',
}


def dxcc_entity_key(callsign):
    """Comme country_key, mais replie les entités WAE sur leur entité DXCC
    parente. À utiliser pour la CHASSE AUX PAYS (≠ multiplicateur CQ WW)."""
    k = country_key(callsign)
    return _WAE_PARENT.get(k, k)


def list_entities():
    """Liste dédupliquée des entités DXCC (une par pays), pour la chasse aux
    pays des concours internationaux. Chaque entité :
    {'prefix'(primaire), 'country'(EN), 'continent', 'lat', 'lon'}.
    Les ajouts WAE (Sicile…) sont exclus : ce ne sont pas des entités DXCC."""
    if not _loaded:
        load_cty()
    seen = {}
    for t in _PREFIXES.values():
        primary = t[4]
        if primary and primary not in seen and primary not in _WAE_PARENT:
            seen[primary] = {'prefix': primary, 'country': t[0],
                             'continent': t[1], 'lat': t[5], 'lon': t[6]}
    return sorted(seen.values(), key=lambda e: (e['continent'] or 'ZZ', e['country']))


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


def verifier_zone_cq(callsign, valeur_recue):
    """Compare la zone CQ SAISIE à celle attendue de cty.dat pour cet indicatif —
    garde-fou contre le multiplicateur FANTÔME (une zone bustée compte comme mult,
    puis est retirée au checking : pénalité nette). La zone vient de lookup(), qui
    honore les dérogations « (zz) » par préfixe ET les entrées exactes « =CALL »
    de cty.dat — jamais une table de zones codée en dur.

    Retourne {match, expected, entity, entered} :
      - match=True  : la zone saisie correspond à l'attendu ;
      - match=False : désaccord (candidat mult fantôme) → l'IA peut trancher ;
      - match=None  : indicatif inconnu ou valeur vide/non comparable → AUCUNE
                      alerte (ne jamais crier sur ce qu'on ne sait pas vérifier).
    """
    entered = str(valeur_recue or '').strip()
    r = lookup(callsign)
    if not r or not r.get('cq_zone') or not entered:
        return {'match': None, 'expected': (r or {}).get('cq_zone'),
                'entity': (r or {}).get('country'), 'entered': entered}
    expected = str(r['cq_zone']).strip()
    if entered.isdigit() and expected.isdigit():
        match = int(entered) == int(expected)
    else:
        match = entered.upper() == expected.upper()
    return {'match': match, 'expected': expected,
            'entity': r.get('country'), 'entered': entered}
