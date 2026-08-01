# -*- coding: utf-8 -*-
"""L'école de CW branchée sur la bande de ce soir.

CE QUI LA REND DIFFÉRENTE D'UN LOGICIEL D'ENTRAÎNEMENT MORSE. Les entraîneurs
classiques tirent des indicatifs au hasard dans un alphabet. Ici la matière
première est celle du poste : les indicatifs RÉELLEMENT présents dans l'index
de l'opérateur — son log, ses archives, sa base d'indicatifs, et MASTER.SCP
s'il l'a importé — et l'échange RÉELLEMENT demandé par le concours qu'il a
choisi. On s'entraîne donc sur ce qu'on va entendre, pas sur du bruit
statistique.

MESURÉ SUR LE POSTE avant d'écrire une ligne : 21 081 indicatifs dans l'index
fusionné, dont 3 954 déjà travaillés. `master_scp.json` est ABSENT — c'est un
import manuel, et l'étude qui promettait « 45 000 indicatifs déjà indexés » se
trompait. Le tirage ne suppose donc jamais sa présence.

RIEN NE PART SUR L'AIR. Le morse est généré dans le navigateur, dans le
casque. Ce module ne fait que composer la série et la corriger.

CE QUI EST HORS DE PORTÉE ICI, et assumé : juger la qualité de manipulation de
l'opérateur. On entraîne la COPIE (écouter et écrire juste), pas l'émission.
"""
import random
import re

# Un caractère dont la confusion à l'oreille est banale en CW. Sert au bilan :
# « tu rates 8 fois sur 10 le 5 et le 0 » vaut mieux que « 72 % de réussite ».
# Les paires sont celles dont les motifs ne diffèrent que par un élément, ou
# qui s'enchaînent en une suite longue et uniforme (les chiffres).
CONFUSIONS_CW = {
    '5': ['4', '6', 'H'], '0': ['9', '1', 'O', 'T'],
    '4': ['5', '3', 'V'], '6': ['5', '7', 'B'],
    'B': ['6', 'D'], 'D': ['B', 'N'], 'N': ['D', 'T', 'A'],
    'A': ['N', 'W', 'U'], 'U': ['A', 'V'], 'V': ['U', '4'],
    'S': ['H', 'I'], 'H': ['S', '5'], 'I': ['S', 'E'],
    'E': ['I', 'T'], 'T': ['E', 'N', 'M'], 'M': ['T', 'O'],
    'O': ['M', '0'], 'K': ['R', 'C'], 'R': ['K', 'L'],
    'W': ['A', 'J'], 'G': ['Q', 'Z'], 'Q': ['G', 'Y'],
}

# Ce qu'un opérateur tape dans le champ indicatif — barre oblique comprise
# (portable, /P, /QRP), qui est justement ce qui fait perdre du temps.
_RE_INDICATIF = re.compile(r'^[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,3}[A-Z](/[A-Z0-9]{1,4})?$')


def indicatifs_realistes(index, limite=400, alea=None):
    """Tire dans l'index du poste des indicatifs plausibles à l'oreille.

    PRIORITÉ AUX DÉJÀ TRAVAILLÉS : ce sont ceux qu'on réentendra, et leur
    présence dans le log prouve qu'ils existent vraiment. Les autres complètent
    quand l'historique est maigre (première installation).
    """
    rnd = alea or random
    travailles, connus = [], []
    for call, e in (index or {}).items():
        c = str(call or '').upper()
        if not _RE_INDICATIF.match(c):
            continue
        if (e or {}).get('qso_count', 0) > 0:
            travailles.append(c)
        else:
            connus.append(c)
    rnd.shuffle(travailles)
    rnd.shuffle(connus)
    # Deux tiers de déjà-travaillés quand il y en a assez : la série reste
    # familière sans devenir répétitive.
    cible_t = min(len(travailles), (limite * 2) // 3)
    out = travailles[:cible_t] + connus[:limite - cible_t]
    rnd.shuffle(out)
    return out[:limite]


def echange_attendu(cdef, numero, locator_moi='', dept_moi='', zone_moi=''):
    """Ce que la station d'en face ENVERRA, dans ce concours-là.

    On ne réinvente pas la grammaire des échanges : `exchange_wants` la lit
    déjà pour la validation du log, on s'appuie dessus. Un concours sans
    échange formel (UFT, rondes) rend juste le report.
    """
    from logx_callhistory import exchange_wants
    veut = exchange_wants(cdef or {})
    bouts = ['599']
    # `exchange_wants` ne renseigne QUE dept et locator — il n'a jamais porté
    # de clé 'num'. Une première version testait `veut.get('num')`, toujours
    # faux : l'entraînement omettait le numéro de série pour les VINGT-TROIS
    # concours qui en demandent un, dont le Championnat de France THF. On
    # s'entraînait donc sur un échange plus court que le vrai — exactement le
    # contraire du but. Le numéro se lit dans le texte de l'échange, seule
    # source qui le mentionne.
    if _demande_un_numero(cdef):
        bouts.append('%03d' % int(numero or 1))
    if veut.get('locator'):
        bouts.append(locator_moi or 'JN18AA')
    elif veut.get('dept'):
        bouts.append(dept_moi or '75')
    elif _RE_ZONE.search(str((cdef or {}).get('exchange', ''))):
        # CQ WW est le plus gros concours du monde et son échange est la zone
        # CQ, que `exchange_wants` ne connaît pas : sans ce cas, on
        # s'entraînerait sur « 599 » tout court pour l'épreuve la plus courue.
        bouts.append(str(zone_moi or 14))
    return ' '.join(bouts)


_RE_ZONE = re.compile(r'zone[_ ]?(cq|itu)', re.IGNORECASE)


# « N°serie », « N° série », « no serie », « serial »… : les définitions ont
# été écrites à la main sur plusieurs années, l'orthographe varie.
_RE_NUMERO = re.compile(r"(n[°o]?\.?\s*s[ée]rie|num[ée]ro\s*de\s*s[ée]rie|serial)",
                        re.IGNORECASE)


def _demande_un_numero(cdef):
    return bool(_RE_NUMERO.search(str((cdef or {}).get('exchange', ''))))


def serie(index, cdef=None, n=20, locators=None, depts=None, zone=None,
          alea=None):
    """Une série d'entraînement : n stations, chacune avec son échange.

    `locators`/`depts` : de quoi composer des échanges variés. Fournis par
    l'appelant (tirés du log réel) plutôt qu'inventés ici.
    """
    rnd = alea or random
    calls = indicatifs_realistes(index, limite=max(n * 3, 60), alea=rnd)
    if not calls:
        return []
    locs = list(locators or []) or ['JN18AA']
    dps = list(depts or []) or ['75']
    out = []
    for i in range(n):
        call = calls[i % len(calls)]
        out.append({
            'call': call,
            'echange': echange_attendu(cdef, i + 1, rnd.choice(locs),
                                       rnd.choice(dps), zone),
        })
    return out


def _distance_char(attendu, saisi):
    """Positions fautives, alignées par le début. Volontairement SIMPLE : on
    ne cherche pas la meilleure correspondance, on veut savoir QUELS
    caractères ont été mal copiés, ce qui suppose de comparer position à
    position comme le fait l'oreille."""
    a, s = str(attendu or '').upper(), str(saisi or '').upper()
    fautes = []
    for i in range(max(len(a), len(s))):
        ca = a[i] if i < len(a) else ''
        cs = s[i] if i < len(s) else ''
        if ca != cs:
            fautes.append({'position': i, 'attendu': ca, 'saisi': cs})
    return fautes


def corriger(serie_jouee, reponses):
    """Le bilan CHIFFRÉ d'une série : ce qui est raté, et sur quels caractères.

    Rend aussi `confusions` : les couples (attendu, saisi) qui sont des
    confusions CW connues. C'est ce qui permet de dire « tu rates 8 fois sur
    10 le 5 et le 0 » au lieu d'un pourcentage global qui n'apprend rien.
    """
    justes, details = 0, []
    par_caractere = {}
    confusions = {}
    for item, rep in zip(serie_jouee or [], reponses or []):
        attendu = str(item.get('call', '')).upper()
        saisi = str(rep or '').upper().strip()
        fautes = _distance_char(attendu, saisi)
        if not fautes:
            justes += 1
        else:
            for f in fautes:
                if f['attendu']:
                    par_caractere[f['attendu']] = par_caractere.get(f['attendu'], 0) + 1
                    if f['saisi'] and f['saisi'] in CONFUSIONS_CW.get(f['attendu'], []):
                        cle = '%s→%s' % (f['attendu'], f['saisi'])
                        confusions[cle] = confusions.get(cle, 0) + 1
        details.append({'attendu': attendu, 'saisi': saisi, 'juste': not fautes,
                        'fautes': fautes})
    total = len(details)
    return {
        'total': total,
        'justes': justes,
        'taux': round(100.0 * justes / total, 1) if total else 0.0,
        # Trié par nombre de ratés : le premier de la liste est ce qu'il faut
        # travailler ce soir.
        'par_caractere': sorted(par_caractere.items(), key=lambda kv: -kv[1]),
        'confusions': sorted(confusions.items(), key=lambda kv: -kv[1]),
        'details': details,
    }


def vitesse_suivante(wpm, taux, plancher=12, plafond=40):
    """La vitesse monte SEULE quand la copie est propre, et redescend quand
    elle décroche. Un entraîneur qui reste à la même vitesse n'entraîne rien ;
    un entraîneur qui monte trop vite décourage.

    Seuils choisis sur l'usage courant de l'entraînement CW : au-dessus de
    90 % la série est acquise, sous 60 % elle est subie.
    """
    w = int(wpm or plancher)
    if taux >= 90:
        w += 2
    elif taux >= 75:
        w += 1
    elif taux < 60:
        w -= 2
    return max(plancher, min(plafond, w))
