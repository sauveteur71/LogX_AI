# -*- coding: utf-8 -*-
"""Filtres d'affichage des spots — décider ce qu'on VOIT, pas ce qui vaut des points.

POURQUOI FILTRER ALORS QU'IL Y A DÉJÀ UN CLASSEMENT. build_ranked_spots trie
les spots par valeur et /data/spots_ranked n'en renvoie que 40. Un samedi de
CQ WW, le cluster en débite plusieurs centaines : les 40 qui passent la coupe
peuvent très bien être 40 spots postés depuis le Japon, à propos de liaisons
qui n'existent pas depuis la France. Trier ne suffit pas dès lors qu'on coupe
— il faut écarter AVANT la coupe. C'est la raison d'être de ce module, et
c'est ce que fait SET/FILTER sur un cluster CC.

CE QU'ON NE FILTRE PAS, ET POURQUOI. Pas de « spotteur à moins de N km ».
cty.dat donne la position du PAYS, pas de la station : W1AW et W6XX rendent
tous deux 37.6 / -91.87, le centre géographique des États-Unis. Un tel filtre
mettrait Boston et San Diego à distance identique de la France — il aurait
l'air de fonctionner et se tromperait de 4 000 km. Le continent, lui, est une
donnée sûre, et c'est déjà le bon critère : ce qu'un EU entend ressemble à ce
que j'entends, ce qu'un JA entend, non.

LES ALERTES NE SONT PAS FILTRÉES, et c'est délibéré. Les deux erreurs n'ont
pas le même coût : une alerte de trop coûte trois secondes, une 3Y0 manquée
parce que seul un W l'avait spottée ne se rattrape pas. Un spot retenu par une
règle d'alerte traverse donc le filtre, marqué 'hors_filtre' — il est visible,
et on voit pourquoi il est là. Sans ce repêchage, une alerte pourrait sonner
pour un spot introuvable dans la liste, ce qui est la meilleure façon de faire
désactiver les alertes.

TOUJOURS ANNONCER CE QU'ON CACHE. filtrer() rend le compte de ce que chaque
critère a écarté, pour que l'écran puisse l'afficher. Un filtre silencieux,
c'est la station rare du week-end qui disparaît sans que personne ne sache
qu'elle est passée.
"""

# Ordre d'affichage : les continents d'où viennent réellement les spots en
# premier. AN (Antarctique) est un vrai continent cty.dat, rare mais pas
# théorique — une base antarctique spotte comme tout le monde.
CONTINENTS = ('EU', 'NA', 'SA', 'AS', 'AF', 'OC', 'AN')

# Un critère vide = joker, jamais « ne rien montrer ». Même convention que
# logx_alerts.evaluate_rule : c'est ce que l'opérateur attend d'un filtre
# qu'il n'a pas encore réglé.
DEFAUTS = {
    'spotter_continents': [],     # [] = tous les spotteurs
    'dx_continents': [],          # [] = toutes les stations DX
    'masquer_deja_faits': False,
    'seulement_lotw': False,
    'seulement_besoins': False,
}

# Libellés des critères, pour que l'écran puisse dire CE QUI a masqué et pas
# seulement combien. Les clés sont celles de comptes['par_critere'].
LIBELLES = {
    'spotter_continents': 'continent du spotteur',
    'dx_continents': 'continent de la station',
    'masquer_deja_faits': 'déjà travaillés',
    'seulement_lotw': 'non-utilisateurs LoTW',
    'seulement_besoins': 'pas un besoin DXCC',
}


def reglages_valides(brut):
    """Normalise ce qui vient de la config (ou d'une requête) en réglages sûrs.

    Tolère None, un type inattendu, un continent inconnu, la casse. Un réglage
    illisible doit dégrader vers « ne filtre rien » : perdre un filtre est
    bénin, masquer des spots par accident ne l'est pas.
    """
    r = dict(DEFAUTS)
    if not isinstance(brut, dict):
        return r
    for cle in ('spotter_continents', 'dx_continents'):
        v = brut.get(cle)
        if isinstance(v, str):
            v = [x for x in v.replace(';', ',').split(',')]
        if not isinstance(v, (list, tuple)):
            continue
        propres = []
        for c in v:
            c = str(c or '').strip().upper()
            if c in CONTINENTS and c not in propres:
                propres.append(c)
        # Tout cocher revient à ne rien filtrer : on le ramène au cas joker
        # pour que l'écran n'annonce pas un filtre actif qui ne retire rien.
        r[cle] = [] if len(propres) == len(CONTINENTS) else propres
    for cle in ('masquer_deja_faits', 'seulement_lotw', 'seulement_besoins'):
        r[cle] = bool(brut.get(cle, False))
    return r


def actif(reglages):
    """Un filtre est-il réellement en train de retirer quelque chose ?"""
    r = reglages_valides(reglages)
    return bool(r['spotter_continents'] or r['dx_continents'] or
                r['masquer_deja_faits'] or r['seulement_lotw'] or
                r['seulement_besoins'])


def continent_spotteur(spot):
    """Continent du spotteur, '' si indéterminable.

    Volontairement tolérant : un spot sans spotteur (source qui ne le donne
    pas) rend '', et un continent vide ne sera JAMAIS masqué par le filtre.
    Filtrer sur une donnée absente reviendrait à punir la source la plus
    pauvre, pas le spot le moins pertinent.
    """
    deja = str(spot.get('spotter_continent') or '').strip().upper()
    if deja:
        return deja
    call = str(spot.get('spotter') or '').strip().upper()
    if len(call) < 3:
        return ''
    try:
        import logx_dxcc as dxcc
        return str((dxcc.lookup(call) or {}).get('continent') or '')
    except Exception:
        return ''


def _rejet(spot, r):
    """Le critère qui écarte ce spot, ou None s'il passe. Un seul motif rendu
    (le premier) : l'écran compte des spots masqués, pas des raisons cumulées."""
    if r['spotter_continents']:
        c = continent_spotteur(spot)
        # '' = spotteur inconnu : on garde. Voir continent_spotteur().
        if c and c not in r['spotter_continents']:
            return 'spotter_continents'
    if r['dx_continents']:
        c = str(spot.get('dx_continent') or '').strip().upper()
        if c and c not in r['dx_continents']:
            return 'dx_continents'
    if r['masquer_deja_faits'] and spot.get('already_done'):
        return 'masquer_deja_faits'
    if r['seulement_lotw']:
        # lotw vaut True / False / None. None = liste pas encore téléchargée
        # ou indicatif absent : « on ne sait pas » n'est pas « non ». Masquer
        # sur une inconnue effacerait la moitié du cluster le premier jour,
        # avant que lotw-user-activity.csv soit arrivé.
        if spot.get('lotw') is False:
            return 'seulement_lotw'
    if r['seulement_besoins'] and spot.get('lotw_need_ici') is False:
        return 'seulement_besoins'
    return None


def filtrer(spots, reglages, calls_alertes=()):
    """Applique le filtre. Retourne (gardés, comptes).

    'gardés' conserve l'ordre d'entrée (donc le classement par valeur). Les
    spots repêchés par une alerte y figurent avec hors_filtre=True.

    'comptes' : {'total', 'gardes', 'masques', 'repeches', 'par_critere'}.
    """
    spots = list(spots or [])
    comptes = {'total': len(spots), 'gardes': len(spots), 'masques': 0,
               'repeches': 0, 'par_critere': {}}
    r = reglages_valides(reglages)
    if not actif(r):
        return spots, comptes

    proteges = {str(c or '').upper() for c in (calls_alertes or []) if c}
    gardes = []
    for s in spots:
        motif = None
        try:
            motif = _rejet(s, r)
        except Exception:
            motif = None       # un spot biscornu s'affiche, il ne disparaît pas
        if motif is None:
            s.pop('hors_filtre', None)
            gardes.append(s)
            continue
        if str(s.get('call') or '').upper() in proteges:
            s['hors_filtre'] = True
            comptes['repeches'] += 1
            gardes.append(s)
            continue
        comptes['par_critere'][motif] = comptes['par_critere'].get(motif, 0) + 1
        comptes['masques'] += 1
    comptes['gardes'] = len(gardes)
    return gardes, comptes


def resume(comptes):
    """Phrase courte pour l'écran, '' s'il n'y a rien à dire.

    Le compte de masqués est la seule chose qui empêche un filtre d'être un
    piège : sans lui, une liste vide veut dire à la fois « rien ne passe » et
    « le cluster est muet », qui appellent des réactions opposées.
    """
    if not comptes or not comptes.get('masques'):
        return ''
    n = comptes['masques']
    txt = '%d spot%s masqué%s' % (n, 's' if n > 1 else '', 's' if n > 1 else '')
    if comptes.get('repeches'):
        txt += ' — %d gardé%s par une alerte' % (
            comptes['repeches'], 's' if comptes['repeches'] > 1 else '')
    return txt
