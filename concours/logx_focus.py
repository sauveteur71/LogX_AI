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
            out[bb] = (max(s, val), noms + [nom] if nom not in noms else noms)
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
    now = now or datetime.datetime.utcnow()
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
    now = now or datetime.datetime.utcnow()
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


def classer_bandes(bandes, spots=(), regions=(), log=(), now=None):
    """Classe les bandes par opportunité MAINTENANT, la meilleure d'abord.

    Renvoie une liste de dictionnaires portant le score ET son détail, pour que
    la page puisse afficher « pourquoi » à côté de « où ».
    """
    now = now or datetime.datetime.utcnow()
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
        })
    # Score décroissant ; à égalité, la bande la plus basse d'abord (elle porte
    # en général plus loin la nuit, et c'est un ordre stable donc reproductible).
    out.sort(key=lambda x: (-x['score'], float(x['band']) if _est_nombre(x['band']) else 1e9))
    return out


def _est_nombre(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def carres_manquants(carres, bande=''):
    """Carrés locator entendus mais pas travaillés, filtrés sur la bande.

    `carres` vient de /awards/carres : chaque entrée porte le carré et, quand
    l'information existe, la bande où il a été entendu. Un carré SANS bande est
    conservé quelle que soit la bande demandée : il manque partout, et le
    masquer priverait l'opérateur de la cible.
    """
    b = _bande(bande)
    out = []
    for c in (carres or []):
        if not isinstance(c, dict):
            continue
        if c.get('worked') or c.get('done'):
            continue
        cb = _bande(c.get('band'))
        if b and cb and cb != b:
            continue
        out.append({'square': _txt(c.get('square') or c.get('locator') or c.get('grid')),
                    'band': cb, 'confirmed': bool(c.get('confirmed'))})
    return [x for x in out if x['square']]
