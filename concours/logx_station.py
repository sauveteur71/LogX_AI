# -*- coding: utf-8 -*-
"""La station physique : PLUSIEURS antennes, plusieurs rotors, plusieurs amplis.

POURQUOI CE MODULE (demande de F4GLD, 01/08/2026). Le logiciel supposait
partout « une seule » : quatre champs texte descriptifs (ant_hf, ant_144,
ant_432, ant_shf), UN rotor (rotor_host/rotor_port), UN ampli (amp_*). Or une
station sérieuse en a plusieurs — l'exemple donné : trois pylônes, trois
antennes différentes, trois rotors, à commander séparément.

LE MODÈLE RETENU (choisi par l'opérateur) : une liste d'ANTENNES, chacune
pouvant désigner SON rotor et SON ampli. C'est la structure réelle d'une
station à plusieurs pylônes — l'antenne est ce que l'opérateur choisit, le
rotor et l'ampli en découlent. Les rotors et amplis restent des listes à part :
un rotor qu'aucune antenne ne réclame reste pilotable à la main, et deux
antennes peuvent partager un même ampli (cas courant : un seul ampli commuté).

CONSÉQUENCE DE PILOTAGE, également choisie par l'opérateur : un clic sur un
spot ne fait tourner QUE le rotor de l'antenne active sur la bande courante.
Les autres pylônes ne bougent pas — indispensable en multi-opérateur, où un
second opérateur travaille une autre bande sur un autre pylône.

RIEN N'EST PERDU DES CONFIGURATIONS EXISTANTES : `charger()` reconstruit ces
listes depuis les anciens champs quand elles sont absentes (voir `_depuis_legacy`),
et l'ancien vocabulaire continue d'être servi pour les écrans qui n'ont pas
encore migré. Une configuration jamais touchée doit continuer de marcher à
l'identique — c'est la règle de ce dépôt pour tout changement de schéma.
"""
import math
import re

# Les bandes telles que le reste du logiciel les nomme (miroir de ALL_BANDS
# dans logx_logbook.js). Écrire une autre orthographe ici — « 10 » au lieu de
# « 10.1 » — rendrait une antenne invisible sur sa bande sans le moindre
# message : c'est le piège des listes tenues en double, déjà payé cher sur les
# identifiants de concours.
BANDES = ['1.8', '3.5', '7', '10.1', '14', '18', '21', '24', '28', '50', '70',
          '144', '432', '1296', '2320', '3400', '5760', '10368', '24048',
          '47088']

# Les quatre anciens champs et les bandes qu'ils couvraient implicitement.
_LEGACY_ANTENNES = [
    ('ant_hf', 'HF', ['1.8', '3.5', '7', '10.1', '14', '18', '21', '24', '28']),
    ('ant_144', '144 MHz', ['144']),
    ('ant_432', '432 MHz', ['432']),
    ('ant_shf', 'UHF/SHF', ['1296', '2320', '3400', '5760', '10368', '24048',
                            '47088']),
]

TYPES_ANTENNE = ('directive', 'omni', 'filaire', 'verticale', 'parabole')


def _slug(txt, defaut):
    s = re.sub(r'[^a-z0-9]+', '-', str(txt or '').lower()).strip('-')
    return s[:24] or defaut


def _ids_uniques(elements, prefixe):
    """Chaque élément reçoit un identifiant STABLE et unique.

    Stable, parce qu'une antenne est référencée par son rotor et par la bande
    qui l'a choisie : un identifiant qui changerait au prochain enregistrement
    romprait ces liens en silence. On dérive donc du nom, et on ne renumérote
    que les collisions.
    """
    vus = set()
    for i, e in enumerate(elements):
        base = str(e.get('id') or '').strip() or _slug(e.get('nom'), '%s%d' % (prefixe, i + 1))
        cand, n = base, 2
        while cand in vus:
            cand, n = '%s-%d' % (base, n), n + 1
        e['id'] = cand
        vus.add(cand)
    return elements


def _bandes_propres(v):
    """N'accepte que des bandes connues. Une bande inventée (faute de frappe
    dans un fichier édité à la main) est écartée plutôt que gardée : gardée,
    elle ferait croire à une couverture qui n'existe pas."""
    if isinstance(v, str):
        v = [x for x in re.split(r'[,;\s]+', v) if x]
    return [b for b in (str(x).strip() for x in (v or [])) if b in BANDES]


def _depuis_legacy(cfg):
    """Reconstruit les trois listes depuis l'ancienne configuration.

    Appelé UNIQUEMENT quand les listes neuves sont absentes : une station déjà
    migrée ne doit jamais voir ses anciens champs ressusciter par-dessus son
    travail.
    """
    antennes = []
    for champ, libelle, bandes in _LEGACY_ANTENNES:
        nom = str(cfg.get(champ) or '').strip()
        if not nom:
            continue
        antennes.append({'nom': nom, 'bandes': list(bandes),
                         'type': '', 'rotor_id': '', 'ampli_id': '',
                         'note': 'reprise du champ %s' % champ})

    rotors = []
    if cfg.get('rotor_enabled') or cfg.get('rotor_host'):
        rotors.append({'nom': 'Rotor', 'enabled': bool(cfg.get('rotor_enabled')),
                       'host': str(cfg.get('rotor_host') or '').strip(),
                       'port': cfg.get('rotor_port') or 4533,
                       'offset_deg': 0})

    amplis = []
    if cfg.get('amp_enabled') or cfg.get('amp_brand'):
        amplis.append({'nom': str(cfg.get('amp_brand') or 'Ampli').upper(),
                       'enabled': bool(cfg.get('amp_enabled')),
                       'brand': str(cfg.get('amp_brand') or '').strip().lower(),
                       'port': str(cfg.get('amp_port') or '').strip(),
                       'baudrate': cfg.get('amp_baudrate') or 0,
                       'civ_addr': cfg.get('amp_civ_addr') or ''})

    # Un seul rotor et un seul ampli repris : toutes les antennes en héritent.
    # C'est exactement ce que faisait le logiciel avant — le dire dans les
    # données plutôt que de le laisser implicite dans le code.
    if antennes and len(rotors) == 1:
        for a in antennes:
            a['rotor_id'] = 'rotor'
    if antennes and len(amplis) == 1:
        for a in antennes:
            a['ampli_id'] = _slug(amplis[0]['nom'], 'ampli1')
    return antennes, rotors, amplis


def charger(cfg):
    """Les trois listes normalisées, quelle que soit l'ancienneté de la config."""
    cfg = cfg or {}
    antennes = cfg.get('antennes')
    rotors = cfg.get('rotors')
    amplis = cfg.get('amplis')
    if not isinstance(antennes, list) or not isinstance(rotors, list) \
            or not isinstance(amplis, list):
        l_ant, l_rot, l_amp = _depuis_legacy(cfg)
        antennes = antennes if isinstance(antennes, list) else l_ant
        rotors = rotors if isinstance(rotors, list) else l_rot
        amplis = amplis if isinstance(amplis, list) else l_amp

    ant = []
    for a in antennes:
        if not isinstance(a, dict):
            continue
        ant.append({
            'id': str(a.get('id') or '').strip(),
            'nom': str(a.get('nom') or '').strip()[:60],
            'bandes': _bandes_propres(a.get('bandes')),
            'type': (str(a.get('type') or '').strip().lower()
                     if str(a.get('type') or '').strip().lower() in TYPES_ANTENNE else ''),
            'rotor_id': str(a.get('rotor_id') or '').strip(),
            'ampli_id': str(a.get('ampli_id') or '').strip(),
            'gain_dbi': a.get('gain_dbi'),
            'hauteur_m': a.get('hauteur_m'),
            'note': str(a.get('note') or '')[:120],
        })
    rot = []
    for r in rotors:
        if not isinstance(r, dict):
            continue
        try:
            port = int(r.get('port') or 4533)
        except (TypeError, ValueError):
            port = 4533
        try:
            offset = float(r.get('offset_deg') or 0)
        except (TypeError, ValueError):
            offset = 0.0
        rot.append({
            'id': str(r.get('id') or '').strip(),
            'nom': str(r.get('nom') or '').strip()[:40],
            'enabled': bool(r.get('enabled')),
            'host': str(r.get('host') or '').strip(),
            'port': port,
            # Décalage mécanique : un rotor dont le zéro n'est pas au nord.
            # Se règle une fois, s'oublie ensuite — mais sans lui, TOUT le
            # pointage automatique de ce pylône est faux du même angle.
            'offset_deg': offset,
        })
    amp = []
    for m in amplis:
        if not isinstance(m, dict):
            continue
        try:
            baud = int(m.get('baudrate') or 0)
        except (TypeError, ValueError):
            baud = 0
        amp.append({
            'id': str(m.get('id') or '').strip(),
            'nom': str(m.get('nom') or '').strip()[:40],
            'enabled': bool(m.get('enabled')),
            'brand': str(m.get('brand') or '').strip().lower(),
            'port': str(m.get('port') or '').strip(),
            'baudrate': baud,
            'civ_addr': str(m.get('civ_addr') or '').strip(),
        })
    return {'antennes': _ids_uniques(ant, 'ant'),
            'rotors': _ids_uniques(rot, 'rotor'),
            'amplis': _ids_uniques(amp, 'ampli')}


# ─── QUI SERT SUR CETTE BANDE ? ─────────────────────────────────────────────

def antennes_pour_bande(station, bande):
    """Les antennes déclarées sur cette bande, dans l'ordre de la liste."""
    b = str(bande or '').strip()
    return [a for a in (station or {}).get('antennes', []) if b in a['bandes']]


def antenne_active(station, bande, choix=None):
    """L'antenne à employer sur cette bande.

    `choix` : {bande: id_antenne} — le choix EXPLICITE de l'opérateur, qui
    prime toujours. Sans choix, la première antenne déclarée sur la bande.
    Rend None si aucune antenne ne couvre la bande : l'appelant doit alors se
    taire plutôt que d'en désigner une au hasard.
    """
    dispo = antennes_pour_bande(station, bande)
    if not dispo:
        return None
    voulu = str(((choix or {}).get(str(bande or '')) or '')).strip()
    if voulu:
        for a in dispo:
            if a['id'] == voulu:
                return a
    return dispo[0]


def _par_id(elements, eid):
    for e in elements or []:
        if e['id'] == eid:
            return e
    return None


def rotor_pour_bande(station, bande, choix=None):
    """Le rotor à faire tourner pour cette bande — celui de l'antenne active.

    C'est LA règle de pilotage retenue : un clic sur un spot ne commande que
    ce rotor-là. Rend None si l'antenne n'en a pas (antenne fixe) ou si aucune
    antenne ne couvre la bande — et dans ce cas rien ne doit tourner.
    """
    a = antenne_active(station, bande, choix)
    if not a or not a['rotor_id']:
        return None
    return _par_id((station or {}).get('rotors'), a['rotor_id'])


def ampli_pour_bande(station, bande, choix=None):
    a = antenne_active(station, bande, choix)
    if not a or not a['ampli_id']:
        return None
    return _par_id((station or {}).get('amplis'), a['ampli_id'])


def rotor_par_id(station, rotor_id):
    return _par_id((station or {}).get('rotors'), str(rotor_id or '').strip())


def _premier_rotor_actif(station):
    for r in (station or {}).get('rotors', []):
        if r.get('enabled') and r.get('host'):
            return r
    return None


def rotor_defaut(cfg, prefer_bandes=None):
    """LE rotor à commander quand aucun sélecteur n'est fourni — la SOURCE
    UNIQUE de /rotor/state, du bouton « pointer » et du suivi satellite.

    POURQUOI CETTE FONCTION EXISTE (revue du 01/08/2026) : le parc à plusieurs
    rotors était injoignable depuis l'interface. `logx_rotor.rotor_settings` ne
    lit QUE les anciens champs (rotor_host/rotor_enabled) et ignore la liste
    `rotors` ; une station configurée uniquement via le nouvel éditeur voyait
    donc son bouton « pointer » masqué et son décalage mécanique jamais
    appliqué. Tout le backend du jour était correct mais sans appelant qui
    l'atteigne — le piège même que ce chantier corrigeait ailleurs.

    Priorité : un rotor lié à l'une des `prefer_bandes` (le suivi satellite
    donne ['144','432']), sinon le premier rotor actif du parc, sinon l'ancien
    rotor unique (offset 0, aucun décalage à appliquer). Rend toujours un dict
    {enabled, host, port, offset_deg, nom, id, source} — `enabled` est vrai
    seulement si le rotor est activé ET a une adresse.
    """
    st = charger(cfg)
    r = None
    for b in (prefer_bandes or []):
        r = rotor_pour_bande(st, b, (cfg or {}).get('antenne_par_bande'))
        if r:
            break
    if r is None:
        r = _premier_rotor_actif(st)
    if r is not None:
        return {'enabled': bool(r['enabled'] and r['host']),
                'host': r['host'], 'port': r['port'],
                'offset_deg': r['offset_deg'], 'nom': r['nom'],
                'id': r['id'], 'source': 'parc'}
    import logx_rotor
    leg = logx_rotor.rotor_settings(cfg)
    return {'enabled': leg['enabled'], 'host': leg['host'], 'port': leg['port'],
            'offset_deg': 0.0, 'nom': 'Rotor', 'id': '', 'source': 'legacy'}


def ampli_par_id(station, ampli_id):
    return _par_id((station or {}).get('amplis'), str(ampli_id or '').strip())


def azimut_rotor(rotor, azimut_vrai):
    """L'azimut à ENVOYER au rotor, décalage mécanique compris.

    Un rotor dont le zéro n'est pas au nord doit recevoir un angle corrigé,
    sinon tout son pointage est faux du même écart — une erreur qu'on ne
    remarque qu'en ratant les DX faibles.
    """
    try:
        az = float(azimut_vrai)
        off = float((rotor or {}).get('offset_deg') or 0)
    except (TypeError, ValueError):
        return None
    # `float('nan')` et `float('inf')` NE LÈVENT PAS : sans ce contrôle,
    # `nan % 360` vaut nan et l'angle partirait tel quel au rotor. Troisième
    # occurrence du même piège dans ce dépôt (positions de suivi satellite,
    # fréquences d'écoute WebSDR, azimut ici) — il ne s'attrape qu'en le
    # cherchant, jamais par une exception.
    if not (math.isfinite(az) and math.isfinite(off)):
        return None
    return round((az - off) % 360, 1)


def resume(station):
    """Ce qu'il faut savoir d'un coup d'œil, pour un écran ou un prompt IA."""
    st = station or {}
    sans_bande = [a['nom'] for a in st.get('antennes', []) if not a['bandes']]
    orphelines = [a['nom'] for a in st.get('antennes', [])
                  if a['rotor_id'] and not rotor_par_id(st, a['rotor_id'])]
    couvertes = sorted({b for a in st.get('antennes', []) for b in a['bandes']},
                       key=lambda b: BANDES.index(b))
    return {
        'nb_antennes': len(st.get('antennes', [])),
        'nb_rotors': len(st.get('rotors', [])),
        'nb_amplis': len(st.get('amplis', [])),
        'bandes_couvertes': couvertes,
        # Deux incohérences qu'il vaut mieux dire que laisser découvrir le jour
        # du concours : une antenne sans bande ne sera jamais choisie, et un
        # rotor_id qui ne pointe sur rien ne fera jamais tourner quoi que ce soit.
        'antennes_sans_bande': sans_bande,
        'antennes_a_rotor_introuvable': orphelines,
    }
