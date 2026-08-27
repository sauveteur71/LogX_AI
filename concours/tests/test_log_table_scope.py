# -*- coding: utf-8 -*-
"""En-têtes du tableau LOG : scope="col" (WCAG 1.3.1 Info & Relationships).

Audit `tables` (skill mgifford) : les 13 `<th>` du `<thead>` de `.log-table`
(le tableau des QSO, cœur du carnet) n'avaient pas de `scope` — un lecteur
d'écran n'associe alors pas chaque cellule à son en-tête de colonne. On ajoute
`scope="col"` (en-têtes de colonne). Aucun changement visuel.

Les tables heatmap band×heure (`.band-stats-table`/`#hourTable`, en-têtes en
`<td>` générés en JS) sont un suivi séparé (plus nuancé : scope col ET row).
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(BASE, 'logx_logbook.html')


def _thead_log():
    """Le <thead> de la table .log-table."""
    html = open(HTML, encoding='utf-8').read()
    m = re.search(r'<table class="log-table">\s*<thead>(.*?)</thead>', html, re.S)
    assert m, '<thead> de .log-table introuvable'
    return m.group(1)


def test_tous_les_th_du_log_ont_scope_col():
    thead = _thead_log()
    ths = re.findall(r'<th\b[^>]*>', thead)
    assert len(ths) >= 10, f'trop peu de <th> trouvés ({len(ths)}) — sélecteur cassé ?'
    manquants = [t for t in ths if 'scope="col"' not in t]
    assert not manquants, f'{len(manquants)} <th> sans scope=col : {manquants[:3]}'
