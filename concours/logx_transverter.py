# -*- coding: utf-8 -*-
"""Transverters : convertir la fréquence FI lue sur la radio en fréquence RÉELLE.

Au-dessus de 1296 MHz, on ne travaille pas en direct : un transverter convertit
une bande FI que la radio sait traiter (144 ou 432 MHz le plus souvent) vers la
bande hyper réelle. La radio AFFICHE donc 144,100 MHz alors que le signal part
à 1296,100 MHz.

Sans conversion, tout ce qui dépend de la fréquence est faux au même moment :
la bande déduite est 144 au lieu de 1296, le QSO est loggué sur la mauvaise
bande, le band map filtre sur la mauvaise plage, le QSY envoie la radio à côté,
et le fichier EDI part avec une bande erronée — c'est-à-dire un log invalide
pour le Rallye des Points Hauts, le National THF ou le Challenge THF, qui sont
précisément les concours visés.

Les bandes jusqu'à 47 GHz étaient déjà déclarées partout dans le logiciel
(CONFIG, band map, EDI) ; il ne manquait que cette table et son application aux
deux points de passage de la fréquence (lecture d'état et QSY).

Tout est en fonctions PURES (aucun accès à la config globale, aucune E/S) pour
rester testable sans radio ni serveur.
"""

# Limites de bande en MHz — même vocabulaire de clés que le band map côté
# navigateur (_BM_RANGE dans logx_logbook.js) : la clé EST le libellé de bande
# utilisé dans le log, pas une valeur décorative.
# BORNES 6 m ET 2 m CORRIGÉES : elles décrivaient la région 2 (50-54 et
# 144-148) alors que l'allocation est 50-52 et 144-146 en France / région 1.
# Deux tables du MÊME logiciel décrivaient donc les mêmes bandes différemment
# — la table de logx_awards vient d'être corrigée sur ce point, et c'est
# exactement ainsi qu'était né le bug d'unités kHz/MHz du band map : deux
# sources qui ne s'accordent pas. Un test croisé (tests/test_plan_bandes_
# iaru_r1.py) les compare désormais l'une à l'autre.
#
# Le 4 m est CONSERVÉ ici alors qu'il n'est pas attribué en France : c'est la
# table des transverters, et un opérateur qui monte un transverter 4 m le fait
# pour trafiquer là où la bande existe (G, OZ, OH…) ou en expédition. Ce
# fichier décrit un montage, pas un droit d'émettre.
BANDES_MHZ = {
    '50': (50.0, 52.0),      # France / région 1 (50-54 en région 2)
    '70': (70.0, 70.5),      # non attribué en France — voir ci-dessus
    '144': (144.0, 146.0),   # région 1 (144-148 en région 2)
    '432': (430.0, 440.0),
    '1296': (1240.0, 1300.0),
    '2320': (2300.0, 2450.0),
    '3400': (3400.0, 3475.0),
    '5760': (5650.0, 5925.0),
    '10368': (10000.0, 10500.0),
    '24048': (24000.0, 24250.0),
    '47088': (47000.0, 47200.0),
}

def _mhz(v):
    try:
        return float(str(v).replace(',', '.'))
    except (TypeError, ValueError):
        return None


def normaliser(entree):
    """Une entrée de config brute → dict exploitable, ou None si inutilisable.

    Forme attendue : {'if': '144', 'rf': '1296', 'lo_mhz': 1152, 'enabled': True}
    `lo_mhz` est FACULTATIF : sans lui, le décalage se déduit du début des deux
    bandes (144 → 1296 donne 1152 MHz), ce qui couvre les montages courants.
    On le garde explicite pour les transverters dont l'oscillateur ne fait pas
    coïncider les débuts de bande — ils existent, et deviner à leur place
    produirait un log faux sans le moindre message.
    """
    if not isinstance(entree, dict):
        return None
    fi = str(entree.get('if', '')).strip()
    rf = str(entree.get('rf', '')).strip()
    if fi not in BANDES_MHZ or rf not in BANDES_MHZ:
        return None
    if fi == rf:
        return None
    lo = _mhz(entree.get('lo_mhz'))
    if lo is None:
        # Le décalage se déduit des clés de bande, PAS des bords d'allocation.
        # La clé EST la fréquence nominale du montage : un transverter 144 →
        # 1296 a un oscillateur à 1152 MHz et fait correspondre 144,000 à
        # 1296,000. Prendre le bord d'allocation (1240 MHz pour la bande 23 cm)
        # donnerait 1096 MHz et placerait tout le trafic 56 MHz trop bas —
        # dans la bonne bande, donc sans erreur visible, mais avec une
        # fréquence fausse dans le log et dans le fichier EDI.
        lo = _mhz(rf) - _mhz(fi)
    fi_lo, fi_hi = BANDES_MHZ[fi]
    return {
        'if': fi,
        'rf': rf,
        'lo_mhz': lo,
        'enabled': bool(entree.get('enabled', True)),
        'label': str(entree.get('label', '') or '%s → %s MHz' % (fi, rf)),
        # Plages en Hz, pré-calculées : la conversion tourne à chaque sondage
        # de l'état radio.
        'fi_hz': (int(fi_lo * 1e6), int(fi_hi * 1e6)),
        'rf_hz': (int((fi_lo + lo) * 1e6), int((fi_hi + lo) * 1e6)),
        'offset_hz': int(lo * 1e6),
    }


def transverters(cfg):
    """Liste normalisée des transverters ACTIFS de la config."""
    brut = (cfg or {}).get('transverters') or []
    if not isinstance(brut, (list, tuple)):
        return []
    out = []
    for e in brut:
        n = normaliser(e)
        if n and n['enabled']:
            out.append(n)
    return out


def erreurs_config(brut):
    """Contrôles à la sauvegarde. Retourne une liste de messages (vide = ok).

    Le contrôle qui compte est le recouvrement de FI : deux transverters actifs
    branchés sur la même bande FI rendent la conversion AMBIGUË (144,100 MHz
    veut-il dire 1296,100 ou 2320,100 ?). Aucune règle de départage ne serait
    honnête ici — physiquement, un seul peut être connecté à la fois. On refuse
    plutôt que de choisir au hasard et de produire un log faux en silence.
    """
    msgs = []
    vus = {}
    for i, e in enumerate(brut or []):
        n = normaliser(e)
        if n is None:
            msgs.append("Transverter %d : bande FI ou bande RF inconnue." % (i + 1))
            continue
        if not n['enabled']:
            continue
        if n['if'] in vus:
            msgs.append(
                "Deux transverters actifs sur la FI %s MHz (%s et %s) : la fréquence "
                "lue sur la radio serait ambiguë. Un seul peut être branché à la fois "
                "— désactive l'autre." % (n['if'], vus[n['if']], n['label']))
        else:
            vus[n['if']] = n['label']
        if n['offset_hz'] <= 0:
            msgs.append("Transverter %s : l'oscillateur local doit être positif "
                        "(la bande RF est au-dessus de la FI)." % n['label'])
    return msgs


def rf_depuis_fi(freq_hz, cfg):
    """Fréquence lue sur la radio → fréquence RÉELLE sur l'air.

    Retourne la fréquence inchangée si aucun transverter ne couvre cette FI :
    une station sans transverter, ou en train de trafiquer sur la bande FI
    elle-même, ne doit rien voir changer.
    """
    try:
        f = int(freq_hz)
    except (TypeError, ValueError):
        return freq_hz
    for t in transverters(cfg):
        lo, hi = t['fi_hz']
        if lo <= f <= hi:
            return f + t['offset_hz']
    return f


def fi_depuis_rf(freq_hz, cfg):
    """Fréquence RÉELLE visée → fréquence à envoyer à la radio (QSY).

    Exactement l'inverse de rf_depuis_fi() : sans elle, un QSY vers 1296,200
    enverrait la radio à 1296,200 — hors de sa couverture, donc un refus ou,
    pire, un déplacement silencieux au bord de bande.
    """
    try:
        f = int(freq_hz)
    except (TypeError, ValueError):
        return freq_hz
    for t in transverters(cfg):
        lo, hi = t['rf_hz']
        if lo <= f <= hi:
            return f - t['offset_hz']
    return f


def bande_depuis_hz(freq_hz):
    """Fréquence RÉELLE (Hz) → clé de bande, '' si hors bande connue."""
    try:
        mhz = float(freq_hz) / 1e6
    except (TypeError, ValueError):
        return ''
    for cle, (lo, hi) in BANDES_MHZ.items():
        if lo <= mhz <= hi:
            return cle
    return ''
