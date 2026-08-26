# -*- coding: utf-8 -*-
"""Prédiction de passages satellite : AOS/LOS, élévation maximale, Doppler.

CE QUI MANQUAIT. LogX savait déjà NOMMER un satellite (logx_satellites.py, pour
l'export ADIF) et savait pointer un rotor en azimut ET en élévation
(logx_rotor.py). Entre les deux, rien : aucun moyen de savoir QUAND le
satellite passe ni OÙ pointer. Un opérateur devait ouvrir Gpredict à côté.

Tout le nécessaire était pourtant déjà là — pyephem est utilisé depuis
logx_eme.py pour la Lune, et il sait propager un TLE aussi bien qu'une
éphéméride lunaire.

─── LE TLE, ET POURQUOI IL EST TRAITÉ COMME UNE DONNÉE PÉRISSABLE ───────────

Un TLE (Two-Line Element) décrit l'orbite à un instant donné. Il se dégrade :
la référence est formelle — « les recharger souvent, sinon prédiction fausse ».
Ce module ne cache donc JAMAIS l'âge du jeu utilisé, et le sert avec la
prédiction plutôt que dans un coin de journal.

CONTRAINTE D'EXPÉDITION, qui commande toute la conception du cache : quinze
jours de trafic en continu, sans Internet garanti et sans rien de réparable sur
place. Trois conséquences :
  • le TLE est mis en cache SUR DISQUE, et un jeu périmé reste utilisable —
    une prédiction dégradée vaut infiniment mieux que pas de prédiction ;
  • l'âge est TOUJOURS remonté, pour que l'opérateur sache ce qu'il regarde ;
  • le rafraîchissement ne bloque jamais : c'est l'appelant qui décide quand
    aller sur le réseau, ce module ne fait que lire, écrire et calculer.

Les seuils d'ancienneté ci-dessous sont des étiquettes d'AFFICHAGE, pas de la
physique : aucune source ne donne « à partir de tant de jours la prédiction
est fausse », la dégradation étant continue et dépendante de l'orbite. Ils
servent à colorer un bandeau, jamais à refuser un calcul.
"""
import datetime
import json
import math
import os
from logx_utils import utcnow, as_naive_utc

try:
    import ephem
    HAS_EPHEM = True
except ImportError:
    HAS_EPHEM = False

C_LIGHT_MS = 299792458.0

# Groupe « amateur » de CelesTrak : la source usuelle, et elle ne contient que
# ce qui nous intéresse (une centaine d'objets au lieu de plusieurs milliers).
TLE_URL = 'https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=tle'
TLE_CACHE = 'tle_amateur.json'

# Étiquettes d'affichage — voir l'avertissement en tête de module.
AGE_FRAIS_JOURS = 3
AGE_VIEUX_JOURS = 14

_INDISPO = {'available': False,
            'error': "Bibliothèque 'ephem' non installée (pip install ephem)"}


def _chemin_cache(dossier=None):
    return os.path.join(dossier or os.path.dirname(os.path.abspath(__file__)),
                        TLE_CACHE)


# ─── Analyse d'un fichier TLE ────────────────────────────────────────────────

def parser_tle(texte):
    """Texte TLE brut -> {nom: [ligne1, ligne2]}.

    Format : trois lignes par objet — un nom, puis deux lignes commençant par
    '1 ' et '2 '. On valide ce préfixe plutôt que de découper par paquets de
    trois : un fichier tronqué en cours de téléchargement produirait sinon des
    orbites absurdes sans que rien ne le signale.
    """
    out = {}
    lignes = [l.rstrip() for l in (texte or '').splitlines()]
    lignes = [l for l in lignes if l.strip()]
    i = 0
    while i + 2 < len(lignes) + 1 and i + 2 <= len(lignes):
        nom, l1, l2 = lignes[i], lignes[i + 1], lignes[i + 2] if i + 2 < len(lignes) else ''
        if l1.startswith('1 ') and l2.startswith('2 '):
            out[nom.strip()] = [l1, l2]
            i += 3
        else:
            i += 1
    return out


def sauver_tle(jeux, dossier=None, quand=None):
    """Écrit le cache. L'horodatage est celui du TÉLÉCHARGEMENT, pas de
    l'époque des TLE : c'est lui qui dit depuis quand on n'a pas vu le réseau.
    """
    from logx_storage import save_json_atomic
    data = {'recupere': (quand or utcnow()).isoformat(),
            'source': TLE_URL, 'tle': jeux}
    save_json_atomic(_chemin_cache(dossier), data)
    return data


def charger_tle(dossier=None):
    """Cache disque, ou None. Ne lève jamais : sans TLE le reste du logiciel
    doit continuer de fonctionner."""
    try:
        with open(_chemin_cache(dossier), encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get('tle'), dict) and d['tle']:
            return d
    except Exception:
        pass
    return None


def age_tle(cache, maintenant=None):
    """{'jours', 'etat', 'recupere'} — 'etat' vaut frais / vieux / perime.

    Retourne None si le cache est absent ou son horodatage illisible : on ne
    prétend PAS connaître un âge qu'on ignore.
    """
    if not cache:
        return None
    try:
        # as_naive_utc : le cache DÉJÀ présent chez les utilisateurs porte un
        # horodatage sans fuseau, mais rien ne garantit qu'il en soit toujours
        # ainsi (fichier recopié d'une autre installation, écrit par une
        # version ultérieure...). Sans cette normalisation, un « +00:00 » ferait
        # lever TypeError à la soustraction ci-dessous — HORS du try, donc en
        # pleine figure de l'appelant.
        t = as_naive_utc(datetime.datetime.fromisoformat(str(cache.get('recupere'))))
    except (TypeError, ValueError):
        return None
    jours = ((maintenant or utcnow()) - t).total_seconds() / 86400.0
    if jours < AGE_FRAIS_JOURS:
        etat = 'frais'
    elif jours < AGE_VIEUX_JOURS:
        etat = 'vieux'
    else:
        etat = 'perime'
    return {'jours': round(jours, 1), 'etat': etat, 'recupere': cache.get('recupere')}


def rafraichir_tle(dossier=None, timeout=20, quand=None):
    """Télécharge le jeu TLE et met le cache à jour. {'ok', 'nb'|'error'}.

    NE REMPLACE JAMAIS UN CACHE VALIDE PAR DU VIDE. Un réseau captif — hôtel,
    partage de connexion, portail d'aéroport — répond 200 avec une page HTML :
    le téléchargement « réussit » et rend zéro satellite. Écraser le cache
    dans ce cas, c'est perdre en expédition la seule chose qui restait
    utilisable. On exige donc un jeu plausible avant d'écrire.

    L'appel réseau passe par fetch_url(), qui borne AUSSI la résolution DNS —
    sans quoi un DNS muet (le cas /P sans Internet) fige l'appelant bien
    au-delà du délai demandé.
    """
    from logx_utils import fetch_url
    try:
        texte = fetch_url(TLE_URL, timeout=timeout)
    except Exception as e:
        return {'ok': False, 'error': 'Réseau indisponible : %s' % e}
    if not texte:
        return {'ok': False, 'error': 'Aucune réponse de CelesTrak'}
    jeux = parser_tle(texte)
    if len(jeux) < 10:
        return {'ok': False,
                'error': 'Réponse inexploitable (%d satellite(s) lus) — cache '
                         'conservé' % len(jeux)}
    sauver_tle(jeux, dossier, quand)
    return {'ok': True, 'nb': len(jeux)}


def _corps(cache, nom):
    """Objet ephem pour ce satellite, ou None. La correspondance de nom est
    tolérante : CelesTrak écrit « AO-7 » mais aussi « AO-07 » selon les
    groupes, et l'utilisateur saisit ce qu'il voit sur AMSAT."""
    if not HAS_EPHEM or not cache:
        return None
    jeux = cache.get('tle') or {}
    cible = str(nom or '').upper().replace(' ', '').replace('-', '')
    for cle, paire in jeux.items():
        # Ignore toute entrée qui n'est pas une paire (l1, l2) : un cache recopié
        # ou écrit par une autre version peut contenir une chaîne ou une liste de
        # 3 lignes. charger_tle() promet de ne jamais lever — on saute, on ne
        # dépaquette pas à l'aveugle (sinon ValueError remonte à l'UI).
        if not (isinstance(paire, (list, tuple)) and len(paire) == 2):
            continue
        l1, l2 = paire
        if cle.upper().replace(' ', '').replace('-', '') == cible:
            try:
                return ephem.readtle(cle, l1, l2)
            except ValueError:
                return None
    return None


def satellites_connus(cache):
    return sorted((cache or {}).get('tle', {}))


# ─── Observateur ─────────────────────────────────────────────────────────────

def _observer(lat, lon, altitude_m=0, quand=None):
    obs = ephem.Observer()
    obs.lat = str(lat)
    obs.lon = str(lon)
    obs.elevation = altitude_m or 0
    # Pas de réfraction : on pointe une antenne sur la position GÉOMÉTRIQUE,
    # comme pour l'EME. La réfraction (~34' à l'horizon) fausserait un rotor.
    obs.pressure = 0
    obs.date = quand or utcnow()
    return obs


def position(cache, nom, lat, lon, altitude_m=0, quand=None):
    """Où pointer MAINTENANT : azimut, élévation, distance, vitesse radiale."""
    if not HAS_EPHEM:
        return dict(_INDISPO)
    sat = _corps(cache, nom)
    if sat is None:
        return {'available': False, 'error': 'Satellite inconnu du jeu TLE : %s' % nom}
    try:
        obs = _observer(lat, lon, altitude_m, quand)
        sat.compute(obs)
        el = math.degrees(float(sat.alt))
        return {
            'available': True,
            'az': round(math.degrees(float(sat.az)), 1),
            'el': round(el, 1),
            'visible': el > 0,
            'distance_km': round(sat.range / 1000.0, 1),
            'range_rate_ms': round(sat.range_velocity, 1),
        }
    except Exception as e:
        return {'available': False, 'error': str(e)}


def doppler_hz(range_rate_ms, freq_mhz):
    """Décalage Doppler sur une liaison SIMPLE (satellite -> station).

    PAS de facteur 2, contrairement à l'EME. En EME le signal fait l'aller ET
    le retour, il subit donc deux fois le décalage ; ici la liaison est
    directe. Recopier la formule EME donnerait le double — c'est le genre de
    détail qui ne se voit pas à l'écran et qui fait rater le correspondant.

    Convention de signe : à l'APPROCHE, la vitesse radiale est négative (la
    distance diminue) et la fréquence reçue est PLUS HAUTE que la nominale.
    """
    try:
        v = float(range_rate_ms)
        f = float(freq_mhz)
    except (TypeError, ValueError):
        return None
    if f <= 0:
        return None
    return round(-v / C_LIGHT_MS * (f * 1e6), 1)


# ─── Passages ────────────────────────────────────────────────────────────────

def _fenetre_heures(heures):
    """Durée de la fenêtre de passages (heures). Défaut 24 h SEULEMENT pour une
    valeur absente (None/'') — pas pour un 0 EXPLICITE : `float(heures or 24)`
    traitait 0 (falsy) comme 24, écrasant une demande de fenêtre nulle."""
    if heures is None or heures == '':
        return 24.0
    return float(heures)


def passages(cache, nom, lat, lon, altitude_m=0, heures=24,
             elevation_min=0.0, quand=None, maxi=20):
    """Passages à venir dans les `heures` qui suivent.

    `elevation_min` filtre sur l'élévation MAXIMALE du passage : la référence
    conseille de viser les passages hauts (> 20-30°), les rasants étant courts
    et bruités. Un passage rasant reste calculé, il est simplement écarté de la
    liste si l'opérateur a demandé mieux.
    """
    if not HAS_EPHEM:
        return dict(_INDISPO)
    sat = _corps(cache, nom)
    if sat is None:
        return {'available': False, 'error': 'Satellite inconnu du jeu TLE : %s' % nom}
    debut = quand or utcnow()
    fin = debut + datetime.timedelta(hours=_fenetre_heures(heures))
    obs = _observer(lat, lon, altitude_m, debut)
    out = []
    try:
        while len(out) < maxi:
            aos, az_aos, tca, el_max, los, az_los = obs.next_pass(sat)
            if aos is None or los is None or tca is None:
                break
            t_aos = aos.datetime()
            if t_aos > fin:
                break
            # Un satellite géostationnaire (QO-100) ne se lève ni ne se couche :
            # next_pass boucle. On sort dès que le temps n'avance plus.
            t_los = los.datetime()
            if t_los <= t_aos:
                break
            el_max_deg = math.degrees(float(el_max))
            if el_max_deg >= float(elevation_min or 0):
                out.append({
                    'aos_utc': t_aos.strftime('%Y-%m-%d %H:%M:%S'),
                    'los_utc': t_los.strftime('%Y-%m-%d %H:%M:%S'),
                    'tca_utc': tca.datetime().strftime('%Y-%m-%d %H:%M:%S'),
                    'az_aos': round(math.degrees(float(az_aos)), 1),
                    'az_los': round(math.degrees(float(az_los)), 1),
                    'el_max': round(el_max_deg, 1),
                    'duree_s': int((t_los - t_aos).total_seconds()),
                })
            # Avancer APRÈS le coucher, sinon next_pass rend le même passage.
            obs.date = ephem.Date(los + ephem.minute)
    except (ValueError, TypeError) as e:
        # ephem lève sur un satellite qui ne se lève jamais depuis ce QTH
        # (orbite trop basse en latitude) — ce n'est pas une erreur du logiciel.
        if not out:
            return {'available': True, 'passages': [], 'note': str(e)}
    return {'available': True, 'passages': out}


def prochain_passage(cache, nom, lat, lon, altitude_m=0, elevation_min=0.0,
                     quand=None):
    """Le prochain passage seulement — ce que la barre de statut affiche."""
    r = passages(cache, nom, lat, lon, altitude_m, heures=72,
                 elevation_min=elevation_min, quand=quand, maxi=1)
    if not r.get('available'):
        return r
    p = (r.get('passages') or [None])[0]
    return {'available': True, 'passage': p}
