# -*- coding: utf-8 -*-
"""Référentiel PARTIEL des forts/châteaux DFCF VALIDÉS — recherche par référence
ou par nom, à partir de la page officielle des validations mensuelles
dfcf.fr/valide.html.

⚠️ CONTRAIREMENT à POTA/SOTA/WWFF/IOTA/WCA (bases COMPLÈTES), c'est la liste des
références RÉCEMMENT VALIDÉES (statut « official_validated »), PAS le catalogue
complet des châteaux — cf. docs/XOTA_DATA_STATUS.md. Une référence DFCF absente
d'ici n'est donc PAS invalide : elle peut être valide mais hors de la période
publiée. Le nom du site vient de la page (donnée officielle), la commune/CP en
bonus ; aucune coordonnée (à enrichir plus tard depuis une base patrimoniale —
jamais présentée comme officielle).

Format vérifié en direct (31/08/2026) : page en ISO-8859-1, lignes séparées par
<br>, champs séparés par TABULATION —
  REF<tab>NOM<tab>DATE<tab>INDICATIF<tab>(COMMUNE<tab>CP)
ex. « 11-104<tab>Gléon Berty<tab>02/01/2026<tab>F5NLX/P<tab>(Marcorignan<tab>11120) ».
"""
import re
import threading
import time

DFCF_VALIDE_URL = 'https://www.dfcf.fr/valide.html'
_CACHE_TTL = 7 * 24 * 3600           # hebdo (la page est mise à jour en fin de mois)
_cache = {'by_code': {}, 'list': [], 'ts': 0, 'error': None}
_lock = threading.Lock()

# Une ligne validée. La commune/CP (entre parenthèses) est OPTIONNELLE. L'indicatif
# s'arrête au '<' (début du <br>) ou à la tabulation suivante.
_LIGNE = re.compile(
    r'(?P<code>\d{2,3}-\d{3,4})\t(?P<name>[^\t\r\n]+?)\t'
    r'(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\t(?P<call>[^\t<\r\n]+)'
    r'(?:\t\((?P<commune>[^\t]+?)\t(?P<cp>\d{4,5})\))?')


def _normaliser_code(ref):
    """Ramène une référence DFCF à la forme courte officielle « DD-NNN » utilisée
    par valide.html : retire le préfixe DFCF optionnel et les espaces, garde les
    chiffres TELS QUELS (pas de zéro-padding — la page n'en met pas). Une réf.
    non reconnue est renvoyée en majuscules sans espace (repli)."""
    r = (ref or '').strip().upper().replace(' ', '')
    m = re.match(r'^(?:DFCF)?[- ]?(\d{2,3})[-.](\d{3,4})$', r)
    return '%s-%s' % (m.group(1), m.group(2)) if m else r


def _sans_html(s):
    """Retire les balises inline (<b>(réactivation)</b>…) présentes dans certains
    noms de la page, sinon le relevé afficherait le balisage brut."""
    return re.sub(r'<[^>]+>', '', s or '').strip()


def _parse(html):
    out = []
    for m in _LIGNE.finditer(html):
        commune = _sans_html(m.group('commune'))
        out.append({
            'code': _normaliser_code(m.group('code')),
            'name': _sans_html(m.group('name')),
            'region': commune,               # alias pour le relevé générique (name · commune)
            'commune': commune,
            'cp': (m.group('cp') or '').strip(),
            'date': m.group('date'),
            'activator': (m.group('call') or '').strip(),
            'status': 'official_validated',      # figure sur la page des validations
        })
    return out


def _charger():
    """Cache mémoire hebdo. Dégrade proprement : sur échec réseau/format, garde
    le dernier résultat connu plutôt que de vider la base."""
    if _cache['list'] and time.time() - _cache['ts'] < _CACHE_TTL:
        return
    from logx_utils import fetch_url_binary
    raw = fetch_url_binary(DFCF_VALIDE_URL, timeout=20)
    if not raw:
        _cache['error'] = 'réseau'
        return
    # Page FR en ISO-8859-1 (latin-1) : NE PAS décoder en UTF-8 (mojibake sur les
    # accents des noms de châteaux). Vérifié en direct.
    items = _parse(raw.decode('iso-8859-1', errors='replace'))
    if not items:                     # page vide / mise en page changée -> on garde l'ancien cache
        _cache['error'] = 'aucune référence trouvée (format de page changé ?)'
        return
    with _lock:
        _cache['by_code'] = {it['code']: it for it in items}
        _cache['list'] = items
        _cache['ts'] = time.time()
        _cache['error'] = None


def get(code):
    """Réf. DFCF -> détails SI elle figure dans les validées publiées, sinon None
    (absence ≠ invalidité : peut être valide hors période publiée)."""
    _charger()
    return _cache['by_code'].get(_normaliser_code(code))


def search(query, limit=25):
    """Recherche par code OU par nom de château (validés publiés seulement)."""
    _charger()
    q = (query or '').strip().lower()
    if not q:
        return []
    out = [it for it in _cache['list']
           if q in it['code'].lower() or q in it['name'].lower()]
    return out[:limit]


def status():
    _charger()
    return {'ready': bool(_cache['list']), 'count': len(_cache['list']),
            'error': _cache['error'], 'source': DFCF_VALIDE_URL,
            'partiel': True}          # liste des VALIDÉS, pas le catalogue complet
