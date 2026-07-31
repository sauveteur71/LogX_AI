# -*- coding: utf-8 -*-
"""Mode d'utilisation EFFECTIF — et ce qu'il change pour l'IA et le coach.

DEMANDE UTILISATEUR : « pourquoi l'IA met ça alors que je suis sans concours !
Il faut que le programme sache demander correctement les requêtes peu importe
l'IA que l'utilisateur aura choisie, et surtout qu'il s'adapte à l'utilisation
faite : logbook simple, concours ou expédition, ce ne sont pas les mêmes
besoins. »

CE QUI N'ALLAIT PAS. `usage_mode` existe dans la configuration depuis
longtemps, et il est lu par la sauvegarde, le stockage, le validateur et
l'écran mural — mais NI par logx_prompts.py, NI par logx_coach.py. L'assistant
et le coach ignoraient donc totalement dans quel mode l'opérateur travaille, et
parlaient concours en toutes circonstances.

DEUXIÈME CAUSE, plus sournoise : `contest_clock()` calculait l'horloge depuis
`contest_start_date`/`contest_end_date` SANS jamais vérifier qu'un concours est
réellement sélectionné. Les dates d'un concours précédent restent dans la
config ; l'horloge annonçait donc « départ dans 18,2 h » avec `contest: ''`,
et le coach enchaînait sur la checklist d'avant-concours.

MODE DÉCLARÉ ≠ MODE EFFECTIF. Le sélecteur vaut « CONCOURS » par défaut. Un
opérateur qui n'a jamais choisi de concours est donc en mode « contest »
déclaré alors qu'il fait du trafic courant. On rétrograde en « simple » : c'est
l'usage RÉEL qui doit piloter l'assistant, pas une case laissée telle quelle.
"""

MODES = ('simple', 'contest', 'expedition', 'radioclub')

# Ce que chaque mode attend de l'assistant. Sert à la fois au prompt système
# (pour cadrer l'IA, quel que soit le fournisseur choisi) et au coach.
BESOINS = {
    'simple': {
        'titre': 'LOGBOOK SIMPLE — chasse DX et trafic courant',
        'compte': ['les pays et carrés jamais travaillés (diplômes à vie)',
                   'la propagation et les ouvertures du moment',
                   'la confirmation des QSO (LoTW, eQSL, ClubLog)'],
        'ignore': ['le règlement, le score et les multiplicateurs de concours',
                   "l'heure de départ ou de fin d'une épreuve",
                   'la soumission de log et les délais associés'],
    },
    'contest': {
        'titre': 'CONCOURS — règlement, échange, score',
        'compte': ['le règlement et le barème de points',
                   'les multiplicateurs manquants',
                   'le rythme (QSO/h) et le choix de bande',
                   "le respect des fenêtres horaires et de l'off-time"],
        'ignore': ["les diplômes à vie, qui ne comptent pas pour l'épreuve"],
    },
    'expedition': {
        'titre': 'EXPÉDITION / PORTABLE — pile-up, autonomie, multi-poste',
        'compte': ['la gestion du pile-up et le rythme',
                   'les régions pas encore servies (répartition du trafic)',
                   "l'autonomie : batterie, météo, sécurité antenne",
                   'la coordination entre postes et opérateurs'],
        'ignore': ["le score d'un concours, sauf si une épreuve est en cours"],
    },
    'radioclub': {
        'titre': 'RADIOCLUB — postes multiples, opérateurs qui se relaient',
        'compte': ['le roulement des opérateurs et des postes',
                   'la cohérence du log partagé entre postes',
                   'la formation : expliquer ce qui est fait et pourquoi'],
        'ignore': [],
    },
}


def _txt(v):
    return str(v if v is not None else '').strip()


def concours_choisi(cfg):
    """Un concours est-il RÉELLEMENT sélectionné ?

    C'est le test qui manquait : les dates d'un concours précédent survivent
    dans la configuration, et suffisaient à faire parler l'horloge.
    """
    return bool(_txt((cfg or {}).get('contest')))


def mode_utilisation(cfg):
    """Mode EFFECTIF, celui qui doit piloter l'assistant et le coach."""
    m = _txt((cfg or {}).get('usage_mode')).lower()
    if m not in MODES:
        m = 'contest'          # valeur par défaut du sélecteur de CONFIG
    if m == 'contest' and not concours_choisi(cfg):
        return 'simple'
    return m


def parle_concours(cfg):
    """L'assistant a-t-il le droit de parler règlement, score, épreuve ?"""
    if not concours_choisi(cfg):
        return False
    return mode_utilisation(cfg) in ('contest', 'expedition', 'radioclub')


def bloc_prompt(cfg):
    """Bloc à insérer dans le prompt système, quel que soit le fournisseur.

    Écrit en langage clair plutôt qu'en drapeaux : un modèle suit mieux une
    consigne explicite qu'un booléen. Et surtout, la consigne NÉGATIVE est
    aussi importante que la positive — c'est elle qui empêche l'assistant de
    réclamer une checklist de concours à quelqu'un qui chasse le DX.
    """
    mode = mode_utilisation(cfg)
    b = BESOINS.get(mode, BESOINS['simple'])
    lignes = ['── MODE D\'UTILISATION : %s ──' % b['titre'], '']
    lignes.append("L'opérateur travaille dans ce mode. Ce qui compte pour lui :")
    lignes += ['  • ' + x for x in b['compte']]
    if b['ignore']:
        lignes.append('')
        lignes.append("N'ÉVOQUE PAS de toi-même :")
        lignes += ['  • ' + x for x in b['ignore']]
    lignes.append('')
    if parle_concours(cfg):
        lignes.append('Un concours EST sélectionné : %s.'
                      % _txt(cfg.get('contest')))
    else:
        lignes.append('AUCUN concours n\'est sélectionné. Ne parle donc ni '
                      'de règlement, ni de score, ni d\'heure de départ ou de '
                      'fin d\'épreuve, et ne propose pas de checklist '
                      'd\'avant-concours : il n\'y a pas d\'épreuve en cours.')
    return '\n'.join(lignes)
