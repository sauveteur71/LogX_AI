#!/usr/bin/env python3
"""
LogX AI - Recherche plein-texte dans les pages de l'application.

Répond au besoin « je cherche SSTV, je ne sais pas où c'est dans le
logiciel » (F4GLD, 07/08/2026) : indexe le texte visible (titres de
section/panneau + corps) des pages HTML de contenu et retourne, pour une
requête, les sections qui la mentionnent - page, titre de section, extrait.

Reconstruit à CHAQUE recherche plutôt que mis en cache : les pages font au
plus quelques centaines de Ko, une recherche manuelle occasionnelle ne
justifie pas la complexité (et les pièges) d'un cache à invalider quand un
fichier change. Voir CLAUDE.md pour la convention de nommage des classes de
titre (section-title, panel-title...) - ce module s'appuie dessus, pas sur
un vrai parseur DOM (aucune dépendance HTML tierce dans ce projet).
"""
import html as _html_mod
import os
import re
import unicodedata

# Pages avec du contenu fonctionnel propre - exclut les fenêtres détachées
# (bande/mobile/panel/scope/wall), simples miroirs d'affichage sans nav
# commune ni contenu qui leur soit propre à indexer.
SEARCHABLE_PAGES = [
    'logx_configuration.html', 'logx_logbook.html', 'logx_chasse.html',
    'logx_departements.html', 'logx_calendrier.html', 'logx_ft8.html',
    'logx_websdr.html', 'logx_carte.html',
    'logx_propagation.html', 'logx_cw.html', 'logx_panadapter.html',
    'logx_modes_numeriques.html', 'logx_rtty.html',
]

PAGE_LABELS = {
    'logx_configuration.html': 'CONFIGURATION',
    'logx_logbook.html': 'LOGBOOK',
    'logx_chasse.html': 'CHASSE',
    'logx_departements.html': 'CARTES',
    'logx_calendrier.html': 'CALENDRIER',
    'logx_ft8.html': 'FT8',
    'logx_websdr.html': 'WEBSDR',
    'logx_carte.html': 'CARTE IA',
    'logx_propagation.html': 'PROPAG',
    'logx_cw.html': 'ÉCOLE CW',
    'logx_panadapter.html': 'PANADAPTER',
    'logx_modes_numeriques.html': 'MODE NUMÉRIQUE',
    'logx_rtty.html': 'RTTY',
}

# Limite ACCEPTÉE (audit trouvabilité/intuitivité, 09/08/2026) : ce module
# indexe uniquement le HTML statique tel qu'écrit dans le fichier source. Il
# ne fait tourner AUCUN JavaScript, donc tout contenu généré/injecté au
# runtime - ex. les ~90 explications de CONFIG_HELP (logx_configuration.html)
# ou un libellé de bouton posé par `.textContent = '...'` depuis un .js
# (ex. logx_logbook.js) - est invisible à la recherche, y compris quand ce
# JS lui-même n'est PAS retiré par _SCRIPT_STYLE_RE (un <script> qui pose du
# texte ailleurs au chargement n'est jamais exécuté ici). Indexer du JS
# exécuté demanderait un vrai navigateur/moteur JS en arrière-plan à chaque
# recherche - disproportionné pour ce besoin (voir docstring de module).
# Choix assumé, pas un oubli : si un besoin futur en dépend, il faudra soit
# indexer un instantané rendu (ex. capturé une fois au build), soit accepter
# le coût d'un vrai rendu à la volée.
_SCRIPT_STYLE_RE = re.compile(r'<(script|style)\b[^>]*>.*?</\1>', re.IGNORECASE | re.DOTALL)
# Bloc de navigation principale (<nav class="app-nav">...</nav>) : identique
# sur les 11 pages qui le partagent (mêmes ~9-10 liens CONFIG/LOGBOOK/...).
# Sans exclusion, une recherche remonte 4-5 quasi-doublons du nav en tête de
# liste avant la vraie page qui parle du sujet (ex. search('FT8') noyait
# logx_ft8.html derrière les mentions de "FT8" dans le nav de chaque autre
# page) - aucune valeur de recherche, uniquement du bruit. Un seul bloc <nav>
# par page, jamais imbriqué (vérifié sur les 12 pages de SEARCHABLE_PAGES).
_NAV_RE = re.compile(r'<nav\b[^>]*>.*?</nav>', re.IGNORECASE | re.DOTALL)
_COMMENT_RE = re.compile(r'<!--.*?-->', re.DOTALL)
_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')

# Classes de titre de section connues du projet (voir CLAUDE.md « design
# graphite & cuivre ») - une nouvelle classe de titre ajoutée à une future
# page doit être ajoutée ici pour rester cherchable par section plutôt que
# de retomber dans le fourre-tout "sans titre".
_HEADING_RE = re.compile(
    r'<(div|span|h[1-6])\b[^>]*\bclass="[^"]*\b(?:section-title|panel-title|'
    r'cat-modal-title|config-sidebar-title|popup-title|edit-title|'
    r'macro-panel-title|grid-title|mini-title|coach-title)\b[^"]*"[^>]*>'
    r'(.*?)</\1>',
    re.IGNORECASE | re.DOTALL,
)

# Mots vides français courants (articles, prépositions, pronoms...) - une
# requête en langage naturel comme « faire du FT8 » matchait « du » (2
# lettres) comme sous-chaîne dans quasiment TOUTE section, faisant remonter
# des pages sans rapport devant la vraie page FT8 (constat réel en testant
# la recherche, pas une hypothèse). Filtrer ces mots-outils avant scoring -
# jamais avant le check de longueur min. de la requête, qui porte sur la
# requête brute. Volontairement minimal (pas de liste NLP exhaustive) : le
# but est d'écarter le bruit le plus flagrant, pas de faire du TAL.
_STOPWORDS_FR = frozenset((
    'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'au', 'aux',
    'et', 'ou', 'a', 'en', 'ce', 'cet', 'cette', 'ces', 'qui', 'que',
    'quoi', 'est', 'sont', 'mon', 'ma', 'mes', 'ton', 'ta', 'tes',
    'son', 'sa', 'ses', 'pour', 'dans', 'avec', 'sur', 'par', 'se',
    'comment',
))


def _keywords(query_words):
    """Retire les mots vides, sauf si ça viderait complètement la liste
    (requête composée uniquement de mots vides : mieux vaut chercher quand
    même sur ces mots que ne retourner aucun résultat)."""
    filtered = [w for w in query_words if w not in _STOPWORDS_FR]
    return filtered or query_words


def _strip_tags(fragment):
    text = _TAG_RE.sub(' ', fragment)
    text = _html_mod.unescape(text)
    return _WS_RE.sub(' ', text).strip()


def _normalize(text):
    """Insensible casse + accents : même normalisation que la fonction JS
    `_searchLocalHelp()` de logx_configuration.html (NFD puis suppression
    des marques diacritiques combinantes) - « reglement » doit retrouver
    « règlement » côté serveur comme côté assistant local. NFD décompose
    chaque caractère accentué en (base + marque combinante) ; on ne garde
    que la base (catégorie Unicode != 'Mn' = "Mark, nonspacing")."""
    decomposed = unicodedata.normalize('NFD', text.lower())
    return ''.join(c for c in decomposed if unicodedata.category(c) != 'Mn')


def _word_search(haystack_norm, word):
    """Position de la première occurrence de `word` comme mot ENTIER (pas
    sous-chaîne) dans `haystack_norm` (déjà normalisé), ou -1. Même
    correctif que `_wholeWordIncludes()` côté JS (logx_configuration.html,
    fonction voisine de _searchLocalHelp) : sans frontière de mot, le mot-clé
    "log" matcherait à l'intérieur de "logx" (présent dans quasiment toutes
    les pages via le nom du produit) et noierait les vraies mentions du mot
    sous du bruit - constat réel en testant « comment exporter mon log »,
    qui remontait la page d'accueil avant la vraie section d'export tant que
    la comparaison restait une sous-chaîne."""
    m = re.search(r'\b' + re.escape(word) + r'\b', haystack_norm)
    return m.start() if m else -1


def _extract_sections(raw_html):
    """Découpe une page en sections {title, text} à partir des marqueurs de
    titre ci-dessus. Une page (ou un préambule avant le premier titre) sans
    marqueur retombe dans une section au titre vide plutôt que d'être
    perdue - elle reste cherchable par son texte, juste sans nom de section.
    Le bloc <nav> (voir _NAV_RE) est retiré au même titre que <script>/
    <style> - dupliqué à l'identique sur presque toutes les pages, il ne
    ferait que polluer les résultats sans jamais être la bonne réponse."""
    cleaned = _SCRIPT_STYLE_RE.sub(' ', raw_html)
    cleaned = _NAV_RE.sub(' ', cleaned)
    cleaned = _COMMENT_RE.sub(' ', cleaned)
    matches = list(_HEADING_RE.finditer(cleaned))
    if not matches:
        return [{'title': '', 'text': _strip_tags(cleaned)}]

    sections = []
    intro_text = _strip_tags(cleaned[:matches[0].start()])
    if intro_text:
        sections.append({'title': '', 'text': intro_text})

    for i, m in enumerate(matches):
        title = _strip_tags(m.group(2))
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
        body_text = _strip_tags(cleaned[body_start:body_end])
        sections.append({'title': title, 'text': body_text})
    return sections


def _snippet(text, query_words, width=70):
    """Fenêtre de `width` caractères autour de la PREMIÈRE occurrence (dans
    l'ordre du texte) de n'importe lequel des `query_words` - recherche sur
    la version normalisée (accents/casse) mais découpe la fenêtre sur le
    texte ORIGINAL, pour un affichage fidèle. NFD ne fait que remplacer les
    caractères accentués français par leur équivalent sans accent un-pour-un
    (é -> e, etc.), donc les index restent alignés entre texte normalisé et
    texte d'origine pour l'usage de ce module."""
    norm = _normalize(text)
    best_idx, best_len = -1, 0
    for w in query_words:
        idx = _word_search(norm, w)
        if idx >= 0 and (best_idx < 0 or idx < best_idx):
            best_idx, best_len = idx, len(w)
    if best_idx < 0:
        return text[:width].strip()
    start = max(0, best_idx - width // 2)
    end = min(len(text), best_idx + best_len + width // 2)
    prefix = '…' if start > 0 else ''
    suffix = '…' if end < len(text) else ''
    return (prefix + text[start:end].strip() + suffix)


def search(query, base_dir=None, limit=40, per_page_limit=8):
    """Cherche `query` (insensible à la casse ET aux accents, min. 2
    caractères) dans le texte visible des pages listées dans
    SEARCHABLE_PAGES. La requête est tokénisée en mots (espaces) plutôt que
    comparée comme une seule sous-chaîne littérale, pour que le langage
    naturel (« comment exporter mon log ») retrouve les mêmes sections que
    le mot-clé seul (« exporter ») - correctif audit trouvabilité/
    intuitivité du 09/08/2026. Les mots vides français courants
    (_STOPWORDS_FR) sont écartés pour ne pas laisser un article comme « du »
    dominer le score. Chaque résultat est scoré par nombre de mots de la
    requête présents (un mot dans le TITRE de section pèse plus qu'un mot
    seulement présent dans le corps), et la liste finale est triée par
    score décroissant - stable à score égal, donc l'ordre pages/apparition
    d'origine sert de départage. Retourne une liste de résultats {page,
    page_label, title, snippet}."""
    query = (query or '').strip()
    if len(query) < 2:
        return []
    query_words = _normalize(query).split()
    if not query_words:
        return []
    query_words = _keywords(query_words)
    base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))

    # Poids : un mot-clé retrouvé dans le TITRE de section compte plus qu'un
    # mot retrouvé seulement dans le corps - une section dont le titre même
    # parle du sujet cherché est presque toujours la meilleure réponse.
    TITLE_WEIGHT = 3
    BODY_WEIGHT = 1

    scored = []
    for page in SEARCHABLE_PAGES:
        path = os.path.join(base_dir, page)
        try:
            with open(path, encoding='utf-8') as f:
                raw = f.read()
        except OSError:
            continue

        page_hits = 0
        for section in _extract_sections(raw):
            if page_hits >= per_page_limit:
                break
            title, text = section['title'], section['text']
            title_norm = _normalize(title)
            text_norm = _normalize(text)
            score = 0
            for w in query_words:
                if _word_search(title_norm, w) >= 0:
                    score += TITLE_WEIGHT
                if _word_search(text_norm, w) >= 0:
                    score += BODY_WEIGHT
            if score <= 0:
                continue
            title_hit = any(_word_search(title_norm, w) >= 0 for w in query_words)
            scored.append((score, {
                'page': page,
                'page_label': PAGE_LABELS.get(page, page),
                'title': title,
                'snippet': _snippet(title if title_hit else text, query_words),
            }))
            page_hits += 1

    # Tri stable : à score égal, conserve l'ordre pages (SEARCHABLE_PAGES)
    # puis apparition dans la page, comme avant l'ajout du score.
    scored.sort(key=lambda item: item[0], reverse=True)
    return [result for _, result in scored][:limit]
