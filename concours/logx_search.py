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

# Pages avec du contenu fonctionnel propre - exclut les fenêtres détachées
# (bande/mobile/panel/scope/wall), simples miroirs d'affichage sans nav
# commune ni contenu qui leur soit propre à indexer.
SEARCHABLE_PAGES = [
    'logx_configuration.html', 'logx_logbook.html', 'logx_chasse.html',
    'logx_departements.html', 'logx_calendrier.html', 'logx_ft8.html',
    'logx_websdr.html', 'logx_focus.html', 'logx_carte.html',
    'logx_propagation.html', 'logx_cw.html', 'logx_panadapter.html',
]

PAGE_LABELS = {
    'logx_configuration.html': 'CONFIGURATION',
    'logx_logbook.html': 'LOGBOOK',
    'logx_chasse.html': 'CHASSE',
    'logx_departements.html': 'CARTES',
    'logx_calendrier.html': 'CALENDRIER',
    'logx_ft8.html': 'FT8',
    'logx_websdr.html': 'WEBSDR',
    'logx_focus.html': 'FOCUS',
    'logx_carte.html': 'CARTE IA',
    'logx_propagation.html': 'PROPAG',
    'logx_cw.html': 'ÉCOLE CW',
    'logx_panadapter.html': 'PANADAPTER',
}

_SCRIPT_STYLE_RE = re.compile(r'<(script|style)\b[^>]*>.*?</\1>', re.IGNORECASE | re.DOTALL)
_COMMENT_RE = re.compile(r'<!--.*?-->', re.DOTALL)
_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')

# Classes de titre de section connues du projet (voir CLAUDE.md « design
# graphite & cuivre ») - une nouvelle classe de titre ajoutée à une future
# page doit être ajoutée ici pour rester cherchable par section plutôt que
# de retomber dans le fourre-tout "sans titre".
_HEADING_RE = re.compile(
    r'<(div|span|h[1-6])\b[^>]*\bclass="[^"]*\b(?:section-title|panel-title|'
    r'cat-modal-title|hub-card-title|hub-group-title|popup-title|edit-title|'
    r'macro-panel-title|grid-title|mini-title|coach-title)\b[^"]*"[^>]*>'
    r'(.*?)</\1>',
    re.IGNORECASE | re.DOTALL,
)


def _strip_tags(fragment):
    text = _TAG_RE.sub(' ', fragment)
    text = _html_mod.unescape(text)
    return _WS_RE.sub(' ', text).strip()


def _extract_sections(raw_html):
    """Découpe une page en sections {title, text} à partir des marqueurs de
    titre ci-dessus. Une page (ou un préambule avant le premier titre) sans
    marqueur retombe dans une section au titre vide plutôt que d'être
    perdue - elle reste cherchable par son texte, juste sans nom de section."""
    cleaned = _SCRIPT_STYLE_RE.sub(' ', raw_html)
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


def _snippet(text, query_lower, width=70):
    low = text.lower()
    idx = low.find(query_lower)
    if idx < 0:
        return text[:width].strip()
    start = max(0, idx - width // 2)
    end = min(len(text), idx + len(query_lower) + width // 2)
    prefix = '…' if start > 0 else ''
    suffix = '…' if end < len(text) else ''
    return (prefix + text[start:end].strip() + suffix)


def search(query, base_dir=None, limit=40, per_page_limit=8):
    """Cherche `query` (insensible à la casse, min. 2 caractères) dans le
    texte visible des pages listées dans SEARCHABLE_PAGES. Retourne une
    liste de résultats {page, page_label, title, snippet}, dans l'ordre des
    pages puis d'apparition dans la page."""
    query = (query or '').strip()
    if len(query) < 2:
        return []
    query_lower = query.lower()
    base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))

    results = []
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
            title_hit = query_lower in title.lower()
            if not title_hit and query_lower not in text.lower():
                continue
            results.append({
                'page': page,
                'page_label': PAGE_LABELS.get(page, page),
                'title': title,
                'snippet': _snippet(title if title_hit else text, query_lower),
            })
            page_hits += 1
            if len(results) >= limit:
                return results
    return results
