# -*- coding: utf-8 -*-
"""Questions déterministes sur le carnet -- C1, incrément 1 (cadrage
docs/superpowers/specs/2026-09-11-c1-requetes-langage-naturel-carnet.md,
« logbook » validé par F4GLD le 11/09/2026).

0 jeton, 0 appel LLM : même raisonnement que le palier « Basique » de Carte
IA (logx_carte.html, AI_TIER_BASIQUE_TOPICS) -- un jeu FIXE de questions
calculables directement en Python, pas une tentative de comprendre du texte
libre arbitraire sans modèle. `extraire_indicatif_deja_travaille` est le
seul point d'entrée en texte libre : un motif étroit (« travaillé » suivi
d'un token en forme d'indicatif), documenté comme tel, jamais présenté
comme une compréhension générale du langage -- toute formulation qui ne
matche pas ce motif reçoit un repli explicite côté appelant, jamais une
tentative de deviner.

Invariant I2 (0 écriture QSO par le LLM) : aucune fonction ici ne modifie
jamais le log qu'on lui passe -- lecture seule, verrouillée par un test
dédié (test_aucune_fonction_ne_modifie_le_log, test_carnet_questions.py)."""
import re

TOPICS = ('total', 'par_bande', 'par_mode', 'dernier', 'deja_travaille')


def total_qso(log):
    return len(log)


def par_bande(log):
    compte = {}
    for q in log:
        b = str(q.get('band', '') or '?').strip() or '?'
        compte[b] = compte.get(b, 0) + 1
    return dict(sorted(compte.items(), key=lambda kv: -kv[1]))


def par_mode(log):
    compte = {}
    for q in log:
        m = str(q.get('mode', '') or '?').strip().upper() or '?'
        compte[m] = compte.get(m, 0) + 1
    return dict(sorted(compte.items(), key=lambda kv: -kv[1]))


def _cle_tri_recence(q):
    return (str(q.get('date', '') or ''), str(q.get('time', '') or ''))


def deja_travaille(log, indicatif):
    """QSO avec cet indicatif (casse/espaces ignorés), du plus récent au
    plus ancien (date puis heure)."""
    cible = str(indicatif or '').strip().upper()
    if not cible:
        return []
    trouves = [q for q in log if str(q.get('call', '') or '').strip().upper() == cible]
    return sorted(trouves, key=_cle_tri_recence, reverse=True)


def dernier_qso(log):
    if not log:
        return None
    return sorted(log, key=_cle_tri_recence, reverse=True)[0]


def qso_sur_periode(log, date_debut, date_fin):
    """date_debut/date_fin au format YYYYMMDD, bornes incluses."""
    return [q for q in log if date_debut <= str(q.get('date', '') or '') <= date_fin]


def _fmt_date(d):
    d = str(d or '')
    if len(d) == 8:
        return '%s/%s/%s' % (d[6:8], d[4:6], d[0:4])
    return d or '?'


def repondre(log, topic, params=None):
    """Dispatch question rapide -> texte français prêt à afficher. Lève
    ValueError sur un topic inconnu -- TOPICS liste exhaustivement ce que
    l'UI peut proposer, voir test_repondre_couvre_tous_les_topics_declares."""
    params = params or {}
    if topic == 'total':
        n = total_qso(log)
        return ("%d QSO au total dans le carnet." % n) if n else "Le carnet est vide pour l'instant."
    if topic == 'par_bande':
        d = par_bande(log)
        if not d:
            return "Le carnet est vide pour l'instant."
        return " · ".join("%s : %d" % (b, n) for b, n in d.items())
    if topic == 'par_mode':
        d = par_mode(log)
        if not d:
            return "Le carnet est vide pour l'instant."
        return " · ".join("%s : %d" % (m, n) for m, n in d.items())
    if topic == 'dernier':
        q = dernier_qso(log)
        if not q:
            return "Aucun QSO dans le carnet pour l'instant."
        return "Dernier QSO : %s le %s à %s (%s %s)." % (
            q.get('call', '?'), _fmt_date(q.get('date', '')),
            q.get('time', '?'), q.get('band', '?'), q.get('mode', '?'))
    if topic == 'deja_travaille':
        indicatif = str(params.get('indicatif', '') or '').strip().upper()
        trouves = deja_travaille(log, indicatif)
        if not trouves:
            return "Aucun QSO trouvé avec %s." % (indicatif or '(indicatif vide)')
        dernier = trouves[0]
        return "%s : %d QSO, le dernier le %s en %s %s." % (
            indicatif, len(trouves), _fmt_date(dernier.get('date', '')),
            dernier.get('band', '?'), dernier.get('mode', '?'))
    raise ValueError("question inconnue : %r" % topic)


# ─── Motif étroit de texte libre : « (a-t-on) ... travaillé ... <INDICATIF> » ─
_RE_TRAVAILLE = re.compile(r'travaill\w*', re.IGNORECASE)
_RE_INDICATIF = re.compile(r'\b[A-Za-z]{1,2}\d[A-Za-z0-9]{0,4}(?:/[A-Za-z0-9]{1,4})?\b')
_FENETRE = 40   # caractères examinés après le stem "travaill*"


def extraire_indicatif_deja_travaille(texte):
    """Reconnaît UNIQUEMENT « ... travaillé ... <INDICATIF> » -- pas un
    parseur NLP général. Renvoie l'indicatif en majuscules, ou None si le
    texte ne contient pas ce motif précis (stem « travaill » suivi, à moins
    de _FENETRE caractères, d'un token en forme d'indicatif)."""
    texte = texte or ''
    m = _RE_TRAVAILLE.search(texte)
    if not m:
        return None
    fenetre = texte[m.end():m.end() + _FENETRE]
    m2 = _RE_INDICATIF.search(fenetre)
    if not m2:
        return None
    return m2.group(0).upper()
