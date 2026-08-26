# -*- coding: utf-8 -*-
"""FOCUS BANDE — « où devrais-je être maintenant ? », et tout sur la bande choisie.

DEMANDE UTILISATEUR : « je verrais bien une seconde page qui afficherait
l'ensemble des éléments que le programme a en sa possession lorsqu'une bande
est choisie : le cluster correspondant, les carrés locator pas faits, la
propagation de cette bande, les concours actifs à ce moment-là sur cette bande
et ce mode, les propositions de contact IA, la band map correspondante. »

Et le module complémentaire proposé en réponse : une bande d'en-tête qui CLASSE
TOUTES LES BANDES par opportunité. La page répond à « qu'y a-t-il sur 20 m ? » ;
le classement répond à « où devrais-je être ? » — c'est la question qui fait
gagner un concours, et aucune fenêtre par bande ne peut y répondre, même en en
ouvrant douze.

CE MODULE EST PUR : aucun accès réseau, aucun fichier. Tout entre par
paramètres, tout sort en dictionnaires. C'est ce qui le rend testable sur des
cas construits (bande fermée mais pleine de multiplicateurs, bande ouverte et
vide…) sans dépendre du cluster du jour.

POURQUOI UN SCORE EXPLIQUÉ, et pas seulement un chiffre : un classement qu'on
ne peut pas justifier ne sera pas suivi. Chaque bande sort avec le détail de ce
qui l'a fait monter — « 2 mults neufs · ouverture 78 · 6 spots » — pour que
l'opérateur puisse être en désaccord en connaissance de cause.
"""
import datetime
from logx_utils import utcnow

# ─── Poids du classement ─────────────────────────────────────────────────────
# Choisis pour que l'ORDRE DE GRANDEUR corresponde à ce qu'un opérateur fait
# spontanément : un multiplicateur neuf déplace, une bande ouverte sans rien
# dessus ne déplace pas, et un run en cours ne s'abandonne pas pour un spot.
POIDS_OUVERTURE = 0.45      # sur un score d'ouverture 0-100 -> 0-45 points
POIDS_MULT = 12.0           # par multiplicateur neuf spotté, plafonné
PLAFOND_MULTS = 4           # au-delà, la bande est déjà « à faire », inutile d'enfler
POIDS_SPOT = 6.0            # par station exploitable (pas déjà travaillée)
PLAFOND_SPOTS = 5
BONUS_RUN = 8.0             # on ne quitte pas un run qui marche
QSO_MINI_POUR_RUN = 5       # QSO dans la dernière heure définissant un « run »


# Bandes proposées par défaut, DANS L'ORDRE DES FRÉQUENCES.
#
# DEUX REPROCHES DE L'UTILISATEUR, tous deux fondés :
#   « pourquoi les bandes sont dans le désordre » — le bandeau était trié par
#   SCORE. Un classement se relit toutes les 15 s : les bandes changeaient donc
#   de place sous le doigt, et retrouver « le 20 m » demandait de lire les huit
#   étiquettes à chaque fois. L'ordre est maintenant celui des fréquences,
#   fixe ; le classement reste lisible par la barre de score et le liseré vert
#   de la meilleure bande.
#   « pourquoi il manque plusieurs bandes » — la liste venait des seules bandes
#   du concours actif. Hors concours, ou sur un concours à deux bandes, la page
#   devenait borgne : impossible d'aller voir ailleurs.
#
# Contenu : les bandes amateur FRANÇAISES que connaît la table de logx_awards
# (1,8 → 432 MHz). Les bandes hyperfréquences n'y sont pas découpées en
# segments ; elles apparaissent quand même si le concours les utilise ou si un
# spot y tombe (voir bandes_a_proposer).
#
# LE 4 m (70 MHz) A ÉTÉ RETIRÉ. Je l'avais mis en annonçant « tout le plan IARU
# région 1 » : il est bien attribué dans plusieurs pays de région 1 (G, OZ,
# OH…), mais PAS aux amateurs en France. Proposer une bande où l'utilisateur
# n'a pas le droit d'émettre, sur une page dont le rôle est justement de dire
# « va travailler là », est une faute. Elle reste atteignable par
# bandes_a_proposer si un spot y tombe ou si un concours l'utilise — ce qui
# couvre le cas de l'expédition dans un pays qui l'attribue.
#
# Le 60 m (5,3515-5,3665) est bien attribué en France, mais volontairement
# absent : segment de 15 kHz à puissance très réduite, aucun concours. Il
# apparaîtra de la même façon si un spot y tombe.
BANDES_STANDARD = ('1.8', '3.5', '7', '10.1', '14', '18', '21', '24', '28',
                   '50', '144', '432')

# Bandes WARC (30 · 17 · 12 m). Convention IARU : PAS DE CONCOURS dessus. Ce
# sont les bandes de repli du trafic courant pendant qu'une épreuve occupe tout
# le reste — raison même de la convention.
BANDES_WARC = ('10.1', '18', '24')


def _txt(v):
    return str(v if v is not None else '').strip()


def _bande(v):
    """Normalise une bande : '14', '14.0', 14 -> '14'."""
    s = _txt(v)
    if not s:
        return ''
    try:
        f = float(s)
    except ValueError:
        return s
    return str(int(f)) if f == int(f) else str(f)


def _parse_dt(date, heure):
    """'20260731' + '14:03' -> datetime, ou None. Tolère 'YYYY-MM-DD' et '1403'."""
    d, h = _txt(date), _txt(heure)
    d = d.replace('-', '').replace('/', '')
    h = h.replace(':', '')
    if len(d) != 8 or not d.isdigit():
        return None
    if len(h) < 4 or not h[:4].isdigit():
        return None
    try:
        return datetime.datetime(int(d[:4]), int(d[4:6]), int(d[6:8]),
                                 int(h[:2]), int(h[2:4]))
    except ValueError:
        return None


def ouverture_par_bande(regions):
    """{bande: (meilleur_score, [régions ouvertes])} depuis /data/openings.

    Une région liste ses `open_bands` et donne `best_band`/`best_score`. Le
    score n'est connu QUE pour la meilleure bande de la région : les autres
    bandes ouvertes comptent comme ouvertes sans chiffre. On leur attribue
    alors un score de présence, plus faible — sinon une bande ouverte partout
    mais jamais « la meilleure » finirait à zéro, ce qui est faux.
    """
    out = {}
    for r in (regions or []):
        if not isinstance(r, dict):
            continue
        nom = _txt(r.get('region_name')) or _txt(r.get('region'))
        meilleure = _bande(r.get('best_band'))
        try:
            score = float(r.get('best_score') or 0)
        except (TypeError, ValueError):
            score = 0.0
        for b in (r.get('open_bands') or []):
            bb = _bande(b)
            if not bb:
                continue
            s, noms = out.get(bb, (0.0, []))
            # 55 % du meilleur score de la région pour une bande ouverte sans
            # chiffre propre : ouverte, mais pas la meilleure porte d'entrée.
            val = score if bb == meilleure else score * 0.55
            out[bb] = (max(s, val), noms + [nom] if (nom and nom not in noms) else noms)
        if meilleure and meilleure not in out:
            out[meilleure] = (score, [nom] if nom else [])
    return out


def spots_par_bande(spots):
    """{bande: {'total', 'exploitables', 'mults'}} depuis /data/spots_ranked."""
    out = {}
    for s in (spots or []):
        if not isinstance(s, dict):
            continue
        b = _bande(s.get('band'))
        if not b:
            continue
        d = out.setdefault(b, {'total': 0, 'exploitables': 0, 'mults': 0})
        d['total'] += 1
        if s.get('already_done'):
            continue
        d['exploitables'] += 1
        if s.get('new_mult'):
            d['mults'] += 1
    return out


def qso_recents_par_bande(log, now=None, minutes=60):
    """{bande: nb de QSO des `minutes` dernières minutes} — détecte le run."""
    now = now or utcnow()
    limite = now - datetime.timedelta(minutes=minutes)
    out = {}
    for e in (log or []):
        if not isinstance(e, dict):
            continue
        dt = _parse_dt(e.get('date'), e.get('time'))
        if not dt or dt < limite or dt > now + datetime.timedelta(minutes=5):
            continue
        b = _bande(e.get('band'))
        if b:
            out[b] = out.get(b, 0) + 1
    return out


def concours_actifs(calendrier, bande='', mode='', now=None):
    """Concours EN COURS maintenant, filtrés sur la bande et le mode s'ils sont
    fournis. Le calendrier porte `bands` et `modes` par concours, donc la
    question « quels concours tournent là, sur 20 m SSB » se répond sans rien
    inventer.

    Une liste `bands`/`modes` VIDE veut dire « toutes » : c'est la convention du
    calendrier, et la traiter comme « aucune » ferait disparaître les concours
    les plus ouverts — exactement ceux qui intéressent.
    """
    now = now or utcnow()
    b, m = _bande(bande), _txt(mode).upper()
    out = []
    for c in (calendrier or []):
        if not isinstance(c, dict):
            continue
        debut = _parse_dt(c.get('date'), c.get('start_utc') or '0000')
        if not debut:
            continue
        try:
            duree = float(c.get('duration_h') or 0)
        except (TypeError, ValueError):
            duree = 0.0
        if duree <= 0:
            continue
        fin = debut + datetime.timedelta(hours=duree)
        if not (debut <= now <= fin):
            continue
        bandes = [_bande(x) for x in (c.get('bands') or []) if _bande(x)]
        modes = [_txt(x).upper() for x in (c.get('modes') or []) if _txt(x)]
        if b and bandes and b not in bandes:
            continue
        if m and modes and not _mode_compatible(m, modes):
            continue
        reste = (fin - now).total_seconds() / 3600.0
        out.append({
            'id': _txt(c.get('id')), 'name': _txt(c.get('name')),
            'bands': bandes, 'modes': modes,
            'heures_restantes': round(reste, 1),
            'exchange': _txt(c.get('exchange')),
        })
    out.sort(key=lambda x: x['heures_restantes'])
    return out


# Un concours « SSB » accepte un opérateur en PHONE, et réciproquement : les
# règlements écrivent tantôt l'un tantôt l'autre. Sans ça, choisir SSB dans la
# page ferait disparaître la moitié des concours phonie.
_FAMILLES = (
    {'SSB', 'PHONE', 'USB', 'LSB', 'FM', 'AM'},
    {'CW'},
    {'FT8', 'FT4', 'RTTY', 'PSK', 'DIGI', 'DIGITAL', 'MFSK', 'JT65', 'Q65'},
)


def _mode_compatible(mode, modes_concours):
    mode = _txt(mode).upper()
    modes_concours = [_txt(x).upper() for x in modes_concours]
    if mode in modes_concours:
        return True
    for fam in _FAMILLES:
        if mode in fam and any(x in fam for x in modes_concours):
            return True
    return False


def bandes_a_proposer(bandes_concours=(), spots=(), bande_demandee=''):
    """Toutes les bandes du sélecteur, DANS L'ORDRE DES FRÉQUENCES.

    Réunion de trois sources : le plan de bandes standard, celles du concours
    actif (qui peut en utiliser une hors table), et celles où un spot est
    tombé (hyperfréquences comprises). Plus la bande explicitement demandée —
    on peut vouloir regarder une bande que rien ne signale.
    """
    vues = list(BANDES_STANDARD)
    for src in (bandes_concours or ()), (b.get('band') for b in (spots or ())
                                         if isinstance(b, dict)):
        for b in src:
            bb = _bande(b)
            if bb and bb not in vues:
                vues.append(bb)
    bd = _bande(bande_demandee)
    if bd and bd not in vues:
        vues.append(bd)
    # Ordre des fréquences ; ce qui n'est pas numérique va à la fin, par nom.
    return sorted(vues, key=lambda x: (0, float(x)) if _est_nombre(x) else (1, x))


def classer_bandes(bandes, spots=(), regions=(), log=(), now=None,
                   bandes_concours=()):
    """Classe les bandes par opportunité MAINTENANT, la meilleure d'abord.

    Renvoie une liste de dictionnaires portant le score ET son détail, pour que
    la page puisse afficher « pourquoi » à côté de « où ».
    """
    now = now or utcnow()
    ouv = ouverture_par_bande(regions)
    sp = spots_par_bande(spots)
    qso = qso_recents_par_bande(log, now=now)

    out = []
    for brut in (bandes or []):
        b = _bande(brut)
        if not b:
            continue
        score_ouv, regions_ouvertes = ouv.get(b, (0.0, []))
        d = sp.get(b, {'total': 0, 'exploitables': 0, 'mults': 0})
        recents = qso.get(b, 0)

        pts_ouv = POIDS_OUVERTURE * score_ouv
        pts_mult = POIDS_MULT * min(d['mults'], PLAFOND_MULTS)
        pts_spot = POIDS_SPOT * min(d['exploitables'], PLAFOND_SPOTS)
        pts_run = BONUS_RUN if recents >= QSO_MINI_POUR_RUN else 0.0
        score = pts_ouv + pts_mult + pts_spot + pts_run

        motifs = []
        if d['mults']:
            motifs.append('%d mult%s neuf%s' % (d['mults'], 's' if d['mults'] > 1 else '',
                                                's' if d['mults'] > 1 else ''))
        if score_ouv > 0:
            motifs.append('ouverture %d' % round(score_ouv))
        if d['exploitables']:
            motifs.append('%d spot%s' % (d['exploitables'], 's' if d['exploitables'] > 1 else ''))
        if pts_run:
            motifs.append('run en cours (%d QSO/h)' % recents)
        if not motifs:
            motifs.append('rien de signalé')

        out.append({
            'band': b,
            'score': round(score, 1),
            'ouverture': round(score_ouv, 1),
            'regions_ouvertes': regions_ouvertes,
            'spots': d['total'],
            'spots_exploitables': d['exploitables'],
            'mults': d['mults'],
            'qso_derniere_heure': recents,
            'pourquoi': ' · '.join(motifs),
            # Bande utilisée par le concours en cours : la page la distingue,
            # sans la faire disparaître — on peut vouloir regarder ailleurs.
            'dans_concours': b in [_bande(x) for x in (bandes_concours or ())],
            'warc': b in BANDES_WARC,
        })
    # ORDRE DES FRÉQUENCES, pas du score. Un bandeau trié par score se
    # réordonne à chaque rafraîchissement : les bandes changent de place sous
    # le doigt et retrouver « le 20 m » demande de relire toutes les
    # étiquettes. Le classement reste lisible — barre de score, et `rang`
    # ci-dessous désigne la bande recommandée.
    out.sort(key=lambda x: (0, float(x['band'])) if _est_nombre(x['band'])
             else (1, x['band']))
    # LA BANDE RECOMMANDÉE NE PEUT PAS ÊTRE UNE WARC PENDANT UN CONCOURS.
    #
    # Mesuré avant correction : concours sur 14 MHz, 40 spots tombent sur 18
    # MHz, et la page collait le liseré vert sur le 17 m. Elle envoyait donc
    # l'opérateur faire des QSO de concours sur une bande où la convention IARU
    # les interdit — des points refusés au dépouillement, et un manquement aux
    # usages devant toute la bande.
    #
    # C'est la RECOMMANDATION qui est bridée, pas l'affichage : le 17 m reste
    # dans la liste avec son score et ses spots. Hors concours, aucune
    # restriction — c'est même une excellente bande, tranquille et ouverte.
    candidats = out
    if bandes_concours:
        hors_warc = [x for x in out if not x['warc']]
        if hors_warc:
            candidats = hors_warc
    if candidats:
        meilleur = max(candidats, key=lambda x: x['score'])
        for x in out:
            x['recommandee'] = (x is meilleur and meilleur['score'] > 0)
    return out


def _est_nombre(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def carres_a_faire_sur_la_bande(carres, bande=''):
    """Carrés déjà travaillés AILLEURS mais PAS sur cette bande.

    PREMIER JET FAUX, corrigé après essai sur les vraies données. Je croyais
    que /awards/carres renvoyait des carrés « manquants » portant `square`,
    `worked` et `band` ; il renvoie en fait les carrés TRAVAILLÉS, sous la
    forme {'g': 'JN18', 'n': 3, 'conf': False, 'bands': ['14','144']}. Mon
    filtre cherchait des clés inexistantes : la carte restait vide en
    permanence, sans erreur ni message.

    Il n'existe pas, côté serveur, de liste des carrés « jamais faits » — le
    panneau CARRÉS ENTENDUS du logbook la construit depuis les décodages
    WSJT-X, qui ne transitent pas par ici. On affiche donc ce que les données
    permettent réellement et qui a du sens en concours : un carré déjà dans le
    log sur une AUTRE bande est une cible immédiate sur celle-ci — l'opérateur
    sait que la station existe et qu'elle est à portée.
    """
    b = _bande(bande)
    out = []
    for c in (carres or []):
        if not isinstance(c, dict):
            continue
        carre = _txt(c.get('g') or c.get('square') or c.get('locator'))
        if not carre:
            continue
        bandes = [_bande(x) for x in (c.get('bands') or [])]
        if b and b in bandes:
            continue          # déjà fait sur CETTE bande : ce n'est plus une cible
        out.append({'square': carre, 'bandes': [x for x in bandes if x],
                    'confirmed': bool(c.get('conf') or c.get('confirmed'))})
    # Les carrés faits sur le plus de bandes d'abord : ce sont les stations les
    # plus actives, donc les plus faciles à retrouver sur une bande de plus.
    out.sort(key=lambda x: (-len(x['bandes']), x['square']))
    return out


def bande_depuis_freq(freq, bandes=()):
    """Bande la plus PROCHE de la fréquence, parmi celles connues.

    Pas de table en dur, et surtout pas de « fréquence ≥ nom de bande » : le
    432 commence à 430, son segment CW se perdrait. La fréquence arrive en kHz
    ou en MHz selon la source — même discrimination que
    logx_awards.mode_depuis_frequence.
    """
    try:
        v = float(freq or 0)
    except (TypeError, ValueError):
        return ''
    if v <= 0:
        return ''
    mhz = v / 1000.0 if v > 1000 else v
    best, ecart = '', None
    for b in (bandes or []):
        bb = _bande(b)
        try:
            val = float(bb)
        except (TypeError, ValueError):
            continue
        e = abs(mhz - val)
        if ecart is None or e < ecart:
            best, ecart = bb, e
    if not best:
        return ''
    return best if ecart <= max(2.0, float(best) * 0.12) else ''


def filtrer_par_mode(spots, mode='', mode_de_freq=None):
    """Ne garde que les spots du mode demandé. Mode vide = tout garder.

    LE MODE N'EST PAS DANS LE SPOT. Le cluster ne l'annonce pas de façon
    fiable : c'est ce qui faisait que changer CW/SSB ne changeait rien à la
    liste. On le DÉDUIT donc de la fréquence, via la même table que la
    réglette de bande (logx_awards.mode_depuis_frequence) — une seule source
    de vérité, sinon la réglette pourrait dessiner un segment CW là où le
    filtre compte du numérique.

    Un spot dont le mode ne peut pas être déduit est CONSERVÉ : mieux vaut une
    ligne de trop qu'une station manquée parce que sa fréquence sort des
    créneaux habituels.
    """
    m = _txt(mode).upper()
    if not m:
        return list(spots or [])
    if mode_de_freq is None:
        try:
            from logx_awards import mode_depuis_frequence as mode_de_freq
        except Exception:
            return list(spots or [])
    out = []
    for s in (spots or []):
        if not isinstance(s, dict):
            continue
        cat = _txt(s.get('mode')).upper() or _txt(mode_de_freq(s.get('freq'))).upper()
        if not cat or _mode_compatible(m, [cat]):
            out.append(s)
    return out


def score_ouverture_region(region, bande):
    """Score d'ouverture d'UNE région pour LA bande demandée.

    /data/openings ne chiffre que la MEILLEURE bande de chaque région. Afficher
    « · » pour toutes les autres — ce que faisait le premier jet — revient à
    lister sept régions ouvertes sans dire à quel point : l'information la plus
    utile de la carte manquait. On applique donc la même règle que le
    classement : score plein pour la meilleure bande, part réduite pour les
    autres bandes ouvertes.
    """
    if not isinstance(region, dict):
        return 0.0
    b = _bande(bande)
    try:
        score = float(region.get('best_score') or 0)
    except (TypeError, ValueError):
        score = 0.0
    if _bande(region.get('best_band')) == b:
        return round(score, 1)
    if b in [_bande(x) for x in (region.get('open_bands') or [])]:
        return round(score * 0.55, 1)
    return 0.0
