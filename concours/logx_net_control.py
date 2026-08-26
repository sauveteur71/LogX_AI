# -*- coding: utf-8 -*-
"""Contrôle de RÉSEAU dirigé (net control) — modèle serveur, tranche 1.

Trou identifié par la veille concurrentielle (docs/veille/opslog.md, 26/08/2026)
: le contrôle de réseau dirigé est un fort levier sur le marché francophone
(réseaux de clubs). Le concurrent le fait ; nous devons le faire, et plus
intuitivement (maquette validée #306).

CE MODULE gère la partie DURABLE : les réseaux (nets) et leur RÉPERTOIRE de
membres, plus la logique PURE de la file de passage du micro. Le branchement de
l'UI et le log dans le carnet UNIQUE (jamais un carnet par réseau — doctrine du
dépôt) viennent aux tranches suivantes.

Stockage DÉDIÉ (fichier JSON isolé de .server_config.json), même patron que
logx_operator_goals (#292) : un bug ici ne peut pas corrompre la config
principale. Toutes les fonctions CRUD sont PURES (data -> data), donc testables
sans I/O ; charger()/enregistrer() sont les seules à toucher le disque."""
import json
import threading

FICHIER = '.net_control.json'          # à côté de .server_config.json (cwd serveur)
_lock = threading.Lock()               # écriture disque (save_json_atomic)
_mut_lock = threading.Lock()           # sérialise les read-modify-write persistés

# Un membre du répertoire : indicatif + infos de courtoisie.
_MEMBRE_CHAMPS = ('nom', 'qth', 'locator')
# Un réseau : identité + réglages radio + répertoire.
_NET_TEXTE = ('nom', 'freq', 'mode', 'bande')


def normaliser_membre(brut):
    """Membre valide -> dict normalisé (call en MAJUSCULES) ; sinon None.
    Un membre SANS indicatif exploitable n'existe pas : on l'écarte plutôt que
    d'écrire une ligne fantôme dans le répertoire."""
    if not isinstance(brut, dict):
        return None
    call = str(brut.get('call', '') or '').strip().upper()
    if not call:
        return None
    m = {'call': call}
    for c in _MEMBRE_CHAMPS:
        m[c] = str(brut.get(c, '') or '')
    return m


def normaliser_net(brut, id_force=None):
    """Réseau normalisé : id (int), champs texte, roster nettoyé (membres
    invalides écartés, dédupliqués par indicatif)."""
    brut = brut if isinstance(brut, dict) else {}
    net = {}
    nid = id_force if id_force is not None else brut.get('id')
    try:
        net['id'] = int(nid)
    except (TypeError, ValueError):
        net['id'] = 0
    for c in _NET_TEXTE:
        net[c] = str(brut.get(c, '') or '')
    net['roster'] = _roster_propre(brut.get('roster'))
    return net


def _roster_propre(brut):
    """Liste de membres valides, dédupliquée par indicatif (le dernier gagne —
    une ré-insertion met à jour les infos)."""
    par_call = {}
    if isinstance(brut, list):
        for x in brut:
            m = normaliser_membre(x)
            if m:
                par_call[m['call']] = m
    return list(par_call.values())


def normaliser(brut):
    """Structure top-level toujours {'nets': [ ... ]}, chaque net normalisé.
    Toute entrée douteuse -> réseaux vides (jamais d'exception)."""
    nets = []
    if isinstance(brut, dict) and isinstance(brut.get('nets'), list):
        for n in brut['nets']:
            nets.append(normaliser_net(n))
    return {'nets': nets}


# ── I/O (les seules fonctions qui touchent le disque) ─────────────────────
def charger():
    """Réseaux persistés (normalisés). Fichier absent/illisible -> vide.
    Ne lève jamais."""
    try:
        with open(FICHIER, encoding='utf-8') as f:
            return normaliser(json.load(f))
    except (OSError, ValueError):
        return {'nets': []}


def enregistrer(brut):
    """Valide (normaliser) puis écrit ATOMIQUEMENT. Retourne l'état écrit."""
    import logx_storage
    data = normaliser(brut)
    logx_storage.save_json_atomic(FICHIER, data, lock=_lock)
    return data


# ── CRUD réseaux (PUR : data -> data) ─────────────────────────────────────
def _prochain_id(data):
    ids = [n['id'] for n in data.get('nets', []) if isinstance(n.get('id'), int)]
    return (max(ids) + 1) if ids else 1


def trouver_net(data, net_id):
    for n in data.get('nets', []):
        if n['id'] == net_id:
            return n
    return None


def creer_net(data, nom='', freq='', mode='', bande=''):
    """Crée un réseau avec un id unique croissant. Retourne (data, net)."""
    data = normaliser(data)
    net = normaliser_net({'nom': nom, 'freq': freq, 'mode': mode, 'bande': bande},
                         id_force=_prochain_id(data))
    data['nets'].append(net)
    return data, net


def maj_net(data, net_id, champs):
    """Met à jour les champs texte d'un réseau existant (id/roster inchangés)."""
    data = normaliser(data)
    net = trouver_net(data, net_id)
    if net and isinstance(champs, dict):
        for c in _NET_TEXTE:
            if c in champs:
                net[c] = str(champs[c] or '')
    return data


def supprimer_net(data, net_id):
    data = normaliser(data)
    data['nets'] = [n for n in data['nets'] if n['id'] != net_id]
    return data


# ── CRUD répertoire (PUR) ─────────────────────────────────────────────────
def ajouter_membre(data, net_id, membre):
    """Ajoute (ou met à jour) un membre du répertoire, dédupliqué par indicatif.
    Membre invalide (sans call) -> ignoré silencieusement."""
    data = normaliser(data)
    net = trouver_net(data, net_id)
    m = normaliser_membre(membre)
    if net is not None and m is not None:
        net['roster'] = [x for x in net['roster'] if x['call'] != m['call']]
        net['roster'].append(m)
    return data


def retirer_membre(data, net_id, call):
    data = normaliser(data)
    net = trouver_net(data, net_id)
    if net is not None:
        cible = str(call or '').strip().upper()
        net['roster'] = [x for x in net['roster'] if x['call'] != cible]
    return data


# ── Logique PURE de la file de passage du micro (session éphémère) ────────
# Une session = {'on_air': [call...], 'logged': [call...]}. 'on_air' est l'ordre
# de passage ; la 1re station est « au micro ». Rien n'est persisté ici : la
# session vit le temps du réseau (branchement en tranche 2).
def _session(s):
    s = s if isinstance(s, dict) else {}
    return {'on_air': list(s.get('on_air') or []), 'logged': list(s.get('logged') or [])}


def mettre_a_l_air(session, call):
    """Ajoute une station en fin de file (pas de doublon, insensible à la casse)."""
    s = _session(session)
    c = str(call or '').strip().upper()
    if c and c not in s['on_air']:
        s['on_air'].append(c)
    return s


def retirer_de_l_air(session, call):
    s = _session(session)
    c = str(call or '').strip().upper()
    s['on_air'] = [x for x in s['on_air'] if x != c]
    return s


def passer_au_suivant(session):
    """Renvoie la station au micro en fin de file (rotation)."""
    s = _session(session)
    if len(s['on_air']) > 1:
        s['on_air'].append(s['on_air'].pop(0))
    return s


def loguer_courant(session):
    """La station au micro quitte la file et passe dans 'logged' (le QSO réel
    dans le carnet unique = tranche 3)."""
    s = _session(session)
    if s['on_air']:
        s['logged'].append(s['on_air'].pop(0))
    return s


# ── Read-modify-write PERSISTÉS (pour les endpoints) ──────────────────────
# charger() -> mutation pure -> enregistrer(), le tout SÉRIALISÉ par _mut_lock
# (deux requêtes concurrentes ne s'écrasent pas). _mut_lock ≠ _lock (écriture
# disque) : pas de ré-entrance, pas d'interblocage.
def creer_persiste(nom='', freq='', mode='', bande=''):
    with _mut_lock:
        data, net = creer_net(charger(), nom, freq, mode, bande)
        enregistrer(data)
        return net


def maj_persiste(net_id, champs):
    with _mut_lock:
        data = maj_net(charger(), net_id, champs)
        enregistrer(data)
        return trouver_net(data, net_id)


def supprimer_persiste(net_id):
    with _mut_lock:
        enregistrer(supprimer_net(charger(), net_id))


def ajouter_membre_persiste(net_id, membre):
    with _mut_lock:
        data = ajouter_membre(charger(), net_id, membre)
        enregistrer(data)
        return trouver_net(data, net_id)


def retirer_membre_persiste(net_id, call):
    with _mut_lock:
        data = retirer_membre(charger(), net_id, call)
        enregistrer(data)
        return trouver_net(data, net_id)
