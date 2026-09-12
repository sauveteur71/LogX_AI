# -*- coding: utf-8 -*-
"""Questions sur le carnet -- C1 (cadrage docs/superpowers/specs/2026-09-11-
c1-requetes-langage-naturel-carnet.md, « logbook » validé par F4GLD le
11/09/2026). Incrément 1 : agrégats fixes, 0 jeton. Incrément 2 (12/09/2026,
décisions F4GLD) : palier IA complet en repli quand aucun motif fixe ne
matche -- voir la section dédiée plus bas dans ce fichier.

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


# ═══════════════════════════════════════════════════════════════════════════
# Palier IA (incrément 2, cadrage 12/09/2026 -- décisions F4GLD par question
# à choix) : activé pour toute question qui ne matche AUCUN motif fixe
# ci-dessus. Historique multi-tour REPORTÉ (chaque question reste
# indépendante, même périmètre que l'incrément 1 de ce point de vue).
#
# Le LLM ne reçoit JAMAIS le carnet brut ni un champ libre (commentaire/
# note de QSO) -- uniquement un DIGEST d'agrégats déjà calculés en Python à
# partir de champs structurés (indicatif/bande/mode/date/locator). Il ne
# fait que choisir/formuler parmi CES chiffres déjà vérifiés, jamais en
# recalculer un lui-même : élimine le risque d'halluciner un total ou une
# distance sur un échantillon tronqué du carnet, et rend inutile le patron
# `sanitize_external_text` (logx_prompts.py) employé ailleurs pour du texte
# EXTERNE non fiable (spot cluster, chat ON4KST) -- rien de tel n'entre
# jamais ici. La question elle-même (texte libre de l'opérateur) N'A PAS
# besoin d'être neutralisée : c'est un message utilisateur normal dans une
# conversation, pas une donnée externe qui usurperait une instruction.
#
# Portée délibérément « à vie » (archives + carnet courant fusionnés, via
# logx_awards.collect_all_qsos) plutôt que le carnet courant seul des
# topics fixes ci-dessus -- même distinction basique/IA déjà établie par
# Carte IA (palier « Basique » = carnet en cours, palier IA = « questions à
# vie »), pas une incohérence : c'est l'appelant (logx_http.py) qui choisit
# quelle vue passer à quelle fonction.
SYSTEME_IA = (
    "Tu réponds en français à UNE question sur le carnet de trafic d'un "
    "radioamateur, à partir UNIQUEMENT des chiffres déjà calculés fournis "
    "ci-dessous. Ne recalcule jamais un total ou une distance toi-même, "
    "n'invente aucun chiffre absent des données fournies -- si la question "
    "porte sur une donnée qui n'y figure pas, dis-le clairement plutôt que "
    "de deviner. Tu n'as aucun moyen d'enregistrer, modifier ou supprimer "
    "un QSO : tu réponds uniquement par du texte. Réponse courte (1 à 3 "
    "phrases), sans liste à puces sauf si la question porte sur plusieurs "
    "éléments distincts."
)


def _top_calls(log, n=5):
    compte = {}
    for q in log:
        c = str(q.get('call', '') or '').strip().upper()
        if not c:
            continue
        compte[c] = compte.get(c, 0) + 1
    tries = sorted(compte.items(), key=lambda kv: -kv[1])
    return [{'indicatif': c, 'qso': n_} for c, n_ in tries[:n]]


def _par_pays(log_enrichi, n=8):
    compte = {}
    for q in log_enrichi:
        p = q.get('dxcc_country')
        if not p:
            continue
        compte[p] = compte.get(p, 0) + 1
    tries = sorted(compte.items(), key=lambda kv: -kv[1])
    return dict(tries[:n])


def _qso_resume(q):
    return {'indicatif': q.get('call', '?'), 'date': _fmt_date(q.get('date', '')),
            'heure': q.get('time', '?') or '?', 'bande': q.get('band', '?') or '?',
            'mode': q.get('mode', '?') or '?'}


def _dx_resume(rec):
    return {'indicatif': rec.get('call', '?'), 'bande': rec.get('band', '?'),
            'mode': rec.get('mode', '?'), 'date': _fmt_date(rec.get('date', '')),
            'distance_km': round(rec.get('dist_km', 0))}


def digest(log_enrichi, my_locator=None):
    """Résumé BORNÉ et déterministe du carnet pour le palier IA -- voir la
    note en tête de cette section. `log_enrichi` : sortie de
    logx_awards.collect_all_qsos() (dxcc_country déjà résolu). Lecture
    seule (I2) : ne modifie jamais `log_enrichi`."""
    d = {
        'total_qso': total_qso(log_enrichi),
        'par_bande': par_bande(log_enrichi),
        'par_mode': par_mode(log_enrichi),
        'par_pays': _par_pays(log_enrichi),
        'plus_travailles': _top_calls(log_enrichi),
        'meilleur_dx': None,
    }
    dernier = dernier_qso(log_enrichi)
    premier = sorted(log_enrichi, key=_cle_tri_recence)[0] if log_enrichi else None
    d['dernier_qso'] = _qso_resume(dernier) if dernier else None
    d['premier_qso'] = _qso_resume(premier) if premier else None
    if my_locator:
        import logx_awards as awards
        rec = (awards.dx_records(my_locator, log_enrichi) or {}).get('overall')
        if rec:
            d['meilleur_dx'] = _dx_resume(rec)
    return d


def construire_prompt_utilisateur(question, d):
    """Message utilisateur envoyé au LLM : la question posée + le digest en
    texte structuré lisible (plus fiable à reformuler pour un modèle que du
    JSON imbriqué)."""
    lignes = ["DONNÉES DU CARNET (déjà calculées, ne rien recalculer) :",
              "- Total QSO : %d" % d['total_qso']]
    if d['par_bande']:
        lignes.append("- Par bande : " + ", ".join("%s=%d" % (k, v) for k, v in d['par_bande'].items()))
    if d['par_mode']:
        lignes.append("- Par mode : " + ", ".join("%s=%d" % (k, v) for k, v in d['par_mode'].items()))
    if d['par_pays']:
        lignes.append("- Par pays (les plus fréquents) : " +
                       ", ".join("%s=%d" % (k, v) for k, v in d['par_pays'].items()))
    if d['plus_travailles']:
        lignes.append("- Indicatifs les plus travaillés : " +
                       ", ".join("%s(%d)" % (x['indicatif'], x['qso']) for x in d['plus_travailles']))
    if d['dernier_qso']:
        q = d['dernier_qso']
        lignes.append("- Dernier QSO : %s le %s à %s (%s %s)" %
                       (q['indicatif'], q['date'], q['heure'], q['bande'], q['mode']))
    if d['premier_qso']:
        q = d['premier_qso']
        lignes.append("- Premier QSO du carnet : %s le %s (%s %s)" %
                       (q['indicatif'], q['date'], q['bande'], q['mode']))
    if d['meilleur_dx']:
        r = d['meilleur_dx']
        lignes.append("- Meilleur DX (distance) : %s le %s en %s %s, %d km" %
                       (r['indicatif'], r['date'], r['bande'], r['mode'], r['distance_km']))
    lignes.append("")
    lignes.append("QUESTION : " + str(question or '').strip())
    return "\n".join(lignes)
