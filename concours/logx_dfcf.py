# -*- coding: utf-8 -*-
"""Référentiel COMPLET des forts/châteaux DFCF — recherche par référence ou par
nom, à partir des pages départementales officielles (dfcf.fr/listdept.htm ->
dept/dNN.html), agrégées.

La page index `listdept.htm` liste ~100 pages départementales. Chaque page place
TOUS ses châteaux dans UN seul gros `<td>` découpé par `<br>` (vérifié : d01.html
= 1 td utile, 58 lignes) — PAS une cellule par château. Les lignes sont
IRRÉGULIÈRES : séparateur tantôt tabulation, tantôt espaces multiples ; date
parfois en plage (« 10-23/12/2000 ») ; indicatif parfois collé à la commune
(« F5NLX/P(Marcorignan »). On ne peut donc PAS ancrer un regex sur la date.
Parseur DÉFENSIF par tokens (méthode F4GLD) : on repère l'INDICATIF par motif,
le nom est ce qui précède (hors date), la commune ce qui suit entre parenthèses ;
une ligne sans indicatif détecté est conservée en `reference_only` plutôt que
jetée. On agrège les 100 pages en UN catalogue, cache DISQUE (15 j) + TÂCHE DE
FOND (le 1er chargement fait ~100 requêtes — jamais à chaque lookup).

Droits : les données restent chez l'OM (téléchargement par SON instance + cache
local), jamais redistribuées dans le dépôt LogX. Pages en ISO-8859-1.
Coordonnées absentes de ces pages (nom + commune seulement) -> pas de nearby.
"""
import json
import re
import threading
import urllib.parse

DFCF_INDEX_URL = 'https://dfcf.fr/listdept.htm'
DFCF_BASE = 'https://dfcf.fr/'
CACHE_FILE = 'dfcf_chateaux.json'
MAX_AGE_DAYS = 15               # vérification des listes XOTA tous les 15 jours (F4GLD)

_state = {'by_code': {}, 'list': [], 'loading': False, 'loaded': False, 'error': None}
_lock = threading.Lock()

# REF = « DD-NNN » en tête de ligne (après collapse des espaces).
_REF_TOK = re.compile(r'^\d{2,3}-\d{3,4}$')
# Indicatif : préfixe (1-3 alnum) + chiffre + suffixe (1-4 alnum) + éventuels /X.
# (motif F4GLD) — sert à REPÉRER la colonne indicatif, pas de séparateur fixe.
_CALL_TOK = re.compile(r'^[A-Z0-9]{1,3}\d[A-Z0-9]{1,4}(?:/[A-Z0-9]+)*$', re.I)
# Date (simple « 08/01/00 » ou plage « 10-23/12/2000 ») — retirée du nom.
_DATE_TOK = re.compile(r'^\d{1,2}(?:-\d{1,2})?/\d{1,2}/\d{2,4}$')
# Code postal en fin de commune : « Culoz 01350 » -> commune + cp.
_CP_FIN = re.compile(r'^(.*?)[ \t]+(\d{4,5})$')


def _normaliser_code(ref):
    """Forme courte officielle « DD-NNN » : retire le préfixe DFCF optionnel et
    les espaces, garde les chiffres tels quels (la page ne zéro-padde pas)."""
    r = (ref or '').strip().upper().replace(' ', '')
    m = re.match(r'^(?:DFCF)?[- ]?(\d{2,3})[-.](\d{3,4})$', r)
    return '%s-%s' % (m.group(1), m.group(2)) if m else r


def _sans_html(s):
    """Retire les balises inline (<b>(réactivation)</b>…)."""
    return re.sub(r'<[^>]+>', '', s or '').strip()


def _parse_ligne(texte):
    """Une ligne de texte brute -> dict château, ou None si ce n'est pas une
    ligne de château (pas de réf en tête, ou réactivation sans vrai nom).

    DÉFENSIF : repère l'indicatif par motif (le nom est ce qui précède, hors
    date). Sans indicatif détecté, la ligne est CONSERVÉE (status
    `reference_only`) plutôt que jetée — on préfère une réf sans détail à une
    perte silencieuse."""
    t = ' '.join((texte or '').split())      # collapse tabs + espaces multiples
    if not t:
        return None
    toks = t.split(' ')
    # La 1re ligne d'une page colle l'en-tête (<TD>, titre) devant la réf :
    # on démarre au 1er token qui EST une réf, on jette ce qui précède.
    start = next((i for i, tk in enumerate(toks) if _REF_TOK.match(tk)), None)
    if start is None:
        return None
    ref = toks[start]
    reste = toks[start + 1:]
    call_i, call = None, ''
    for i, tok in enumerate(reste):
        cand = tok.split('(', 1)[0]          # indicatif parfois collé « F5NLX/P(Marcorignan »
        if _CALL_TOK.fullmatch(cand):
            call_i, call = i, cand
            break
    if call_i is None:
        nom_toks, tail, status = reste, '', 'reference_only'
    else:
        nom_toks = reste[:call_i]
        tail = ' '.join(reste[call_i:])
        status = 'official_validated'
    nom = ' '.join(tk for tk in nom_toks if not _DATE_TOK.match(tk)).strip()
    if not nom or (nom.startswith('(') and 'activ' in nom.lower()):
        return None                          # ligne « (réactivation) » : pas un nom
    commune, cp = '', ''
    if '(' in tail:
        loc = tail.split('(', 1)[1].rstrip(') ').strip()
        mcp = _CP_FIN.match(loc)
        commune, cp = (mcp.group(1).strip(), mcp.group(2)) if mcp else (loc, '')
    return {
        'code': _normaliser_code(ref),
        'name': nom,
        'region': commune,                   # alias pour le relevé générique (name · commune)
        'commune': commune,
        'cp': cp,
        'callsign': call,
        'status': status,
    }


def _parse(html):
    """Une page départementale (gros <td> découpé par <br>) -> liste de dicts.
    On coupe sur <br>, on retire les balises, on parse chaque ligne."""
    out = []
    for brut in re.split(r'<br\s*/?>', html or '', flags=re.I):
        rec = _parse_ligne(_sans_html(brut))
        if rec:
            out.append(rec)
    return out


def _dept_urls(index_html):
    """URLs absolues des pages départementales depuis listdept.htm (DOM inclus,
    dont le nom de fichier contient des espaces -> quotés)."""
    urls, seen = [], set()
    for m in re.finditer(r'href=["\']?([^"\'>]*dept/[^"\'>]+?\.html?)', index_html or '', re.I):
        rel = m.group(1).strip()
        if rel in seen:
            continue
        seen.add(rel)
        urls.append(DFCF_BASE + urllib.parse.quote(rel))
    return urls


def _fetch_txt(url):
    from logx_utils import fetch_url_binary
    raw = fetch_url_binary(url, timeout=20)
    return raw.decode('iso-8859-1', errors='replace') if raw else ''


def agreger_catalogue(fetch=_fetch_txt):
    """Télécharge l'index + chaque page départementale et agrège en UN catalogue
    (dédoublonné par référence — on garde la 1re occurrence = l'activation
    d'origine, pas les réactivations). `fetch` injectable pour les tests."""
    idx = fetch(DFCF_INDEX_URL)
    if not idx:
        return []
    by_code = {}
    for u in _dept_urls(idx):
        html = fetch(u)
        if not html:
            continue
        for rec in _parse(html):
            anc = by_code.get(rec['code'])
            # 1re occurrence = original ; mais on préfère une fiche complète
            # (official_validated) à un repli reference_only rencontré avant.
            if anc is None or (anc['status'] == 'reference_only'
                               and rec['status'] == 'official_validated'):
                by_code[rec['code']] = rec
    return list(by_code.values())


def _appliquer(items):
    with _lock:
        _state['by_code'] = {it['code']: it for it in items}
        _state['list'] = items
        _state['loaded'] = True
        _state['error'] = None


def _charger_worker():
    from logx_utils import atomic_write, age_days
    try:
        items = None
        a = age_days(CACHE_FILE)
        if a is not None and a < MAX_AGE_DAYS:
            try:
                with open(CACHE_FILE, encoding='utf-8') as f:
                    items = json.load(f)
            except Exception:
                items = None
        if not items:
            items = agreger_catalogue()
            if items:
                try:
                    atomic_write(CACHE_FILE, json.dumps(items, ensure_ascii=False))
                except Exception:
                    pass
        if items:
            _appliquer(items)
        else:
            _state['error'] = 'catalogue vide (réseau/format ?)'
    finally:
        _state['loading'] = False


def _charger():
    """Déclenche le chargement EN FOND une seule fois (le 1er appel revient tout
    de suite ; le catalogue apparaît quand le thread a fini — cache disque au
    2e démarrage). Non bloquant : le relevé de saisie est débounced."""
    if _state['loaded']:
        return
    with _lock:
        if _state['loading'] or _state['loaded']:
            return
        _state['loading'] = True
    threading.Thread(target=_charger_worker, daemon=True).start()


def get(code):
    """Réf. DFCF -> détails si présente dans le catalogue, sinon None (catalogue
    peut être en cours de chargement au 1er démarrage)."""
    _charger()
    return _state['by_code'].get(_normaliser_code(code))


def search(query, limit=25):
    _charger()
    q = (query or '').strip().lower()
    if not q:
        return []
    out = [it for it in _state['list']
           if q in it['code'].lower() or q in it['name'].lower()]
    return out[:limit]


def status():
    _charger()
    return {'ready': _state['loaded'], 'loading': _state['loading'],
            'count': len(_state['list']), 'error': _state['error'],
            'source': DFCF_INDEX_URL}
