# -*- coding: utf-8 -*-
"""Départements français — multiplicateur des concours REF (hors ligne).

Un indicatif métropolitain N'ENCODE PAS le département : il est transmis dans
l'ÉCHANGE (ex. « 59 042 » → dept 042). L'outre-mer, lui, est dérivable du
préfixe (et déjà distingué par cty.dat comme entités DXCC séparées).

Ce module fournit :
- DEPARTMENTS : n° → nom (métropole + Corse + DOM), pour valider/afficher ;
- dept_from_exchange() : extrait le n° de département d'un échange reçu ;
- department_mult_count() : compte les départements DISTINCTS reçus (le vrai
  multiplicateur des concours REF « dept_dxcc », inconnaissable au spot).
"""
import re

# Départements métropolitains 01-95 + Corse (2A/2B) + Île-de-France + DOM 971-976
DEPARTMENTS = {
    '01': 'Ain', '02': 'Aisne', '03': 'Allier', '04': 'Alpes-de-Hte-Provence',
    '05': 'Hautes-Alpes', '06': 'Alpes-Maritimes', '07': 'Ardèche', '08': 'Ardennes',
    '09': 'Ariège', '10': 'Aube', '11': 'Aude', '12': 'Aveyron',
    '13': 'Bouches-du-Rhône', '14': 'Calvados', '15': 'Cantal', '16': 'Charente',
    '17': 'Charente-Maritime', '18': 'Cher', '19': 'Corrèze', '2A': 'Corse-du-Sud',
    '2B': 'Haute-Corse', '21': "Côte-d'Or", '22': "Côtes-d'Armor", '23': 'Creuse',
    '24': 'Dordogne', '25': 'Doubs', '26': 'Drôme', '27': 'Eure', '28': 'Eure-et-Loir',
    '29': 'Finistère', '30': 'Gard', '31': 'Haute-Garonne', '32': 'Gers', '33': 'Gironde',
    '34': 'Hérault', '35': 'Ille-et-Vilaine', '36': 'Indre', '37': 'Indre-et-Loire',
    '38': 'Isère', '39': 'Jura', '40': 'Landes', '41': 'Loir-et-Cher', '42': 'Loire',
    '43': 'Haute-Loire', '44': 'Loire-Atlantique', '45': 'Loiret', '46': 'Lot',
    '47': 'Lot-et-Garonne', '48': 'Lozère', '49': 'Maine-et-Loire', '50': 'Manche',
    '51': 'Marne', '52': 'Haute-Marne', '53': 'Mayenne', '54': 'Meurthe-et-Moselle',
    '55': 'Meuse', '56': 'Morbihan', '57': 'Moselle', '58': 'Nièvre', '59': 'Nord',
    '60': 'Oise', '61': 'Orne', '62': 'Pas-de-Calais', '63': 'Puy-de-Dôme',
    '64': 'Pyrénées-Atlantiques', '65': 'Hautes-Pyrénées', '66': 'Pyrénées-Orientales',
    '67': 'Bas-Rhin', '68': 'Haut-Rhin', '69': 'Rhône', '70': 'Haute-Saône',
    '71': 'Saône-et-Loire', '72': 'Sarthe', '73': 'Savoie', '74': 'Haute-Savoie',
    '75': 'Paris', '76': 'Seine-Maritime', '77': 'Seine-et-Marne', '78': 'Yvelines',
    '79': 'Deux-Sèvres', '80': 'Somme', '81': 'Tarn', '82': 'Tarn-et-Garonne',
    '83': 'Var', '84': 'Vaucluse', '85': 'Vendée', '86': 'Vienne', '87': 'Haute-Vienne',
    '88': 'Vosges', '89': 'Yonne', '90': 'Territoire de Belfort', '91': 'Essonne',
    '92': 'Hauts-de-Seine', '93': 'Seine-St-Denis', '94': 'Val-de-Marne', '95': "Val-d'Oise",
    '971': 'Guadeloupe', '972': 'Martinique', '973': 'Guyane', '974': 'La Réunion',
    '975': 'St-Pierre-et-Miquelon', '976': 'Mayotte',
}


def _is_rst(tok):
    """Un token ressemble-t-il à un RST ('59', '599', '55'...) ? readability
    1-5, strength 1-9, tonalité 9 optionnelle. Sert à ne pas prendre le '59'
    d'un RST pour le département Nord."""
    return bool(re.fullmatch(r'[1-5][1-9]9?', tok))


def dept_from_exchange(num_rcvd):
    """Extrait le n° de département d'un échange reçu. Ambiguïté RST/département
    (le RST '599' contient '59') levée en RETIRANT le RST de tête, puis en
    lisant le département dans le reste ('599 042' → 04, '59 075' → Ardèche,
    '2A 015' → 2A). '' si aucun département fiable."""
    s = str(num_rcvd or '').upper()
    m = re.search(r'\b(2[AB])\b', s)
    if m and m.group(1) in DEPARTMENTS:
        return m.group(1)
    toks = re.findall(r'\d{2,3}', s)
    if toks and _is_rst(toks[0]):
        toks = toks[1:]              # jette le RST de tête
    for tok in toks:
        if tok in DEPARTMENTS:       # DOM 971-976
            return tok
        d2 = tok[:2]
        if d2 in DEPARTMENTS:
            return d2
    return ''


def department_mult_count(shared_log, contest_id=''):
    """Nombre de départements français DISTINCTS reçus dans les échanges du log
    — le vrai multiplicateur « dept » des concours REF. Retourne un set de n°."""
    depts = set()
    for q in shared_log or []:
        if contest_id and q.get('contest', '') not in ('', contest_id):
            continue
        d = dept_from_exchange(q.get('num_rcvd', ''))
        if d:
            depts.add(d)
    return depts
