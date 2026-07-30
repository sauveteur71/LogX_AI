# -*- coding: utf-8 -*-
"""Qui utilise LoTW ? — liste publique de l'ARRL, mise en cache localement.

À QUOI ÇA SERT, et pourquoi c'est le complément direct des alertes de besoin
LoTW (voir logx_awards.besoin_lotw) : inutile d'alerter sur une station qui
n'uploade jamais vers LoTW, le QSO ne sera JAMAIS confirmé et ne comptera
jamais pour le DXCC. Colorer les indicatifs des utilisateurs LoTW transforme
une liste de spots en liste de cibles réellement utiles.

La date du dernier upload compte autant que la présence dans la liste : un
indicatif dont le dernier envoi remonte à 2008 est un utilisateur LoTW sur le
papier seulement. D'où last_upload(), et l'idée d'« actif depuis N années ».

SOURCE : https://lotw.arrl.org/lotw-user-activity.csv — une ligne par
indicatif, `CALL,AAAA-MM-JJ,HH:MM:SS`. Mesuré le 30/07/2026 : 233 627
indicatifs, 6,2 Mo.

MÊME MODÈLE QUE cty.dat (logx_dxcc.update_cty_if_stale) : validation stricte
avant de remplacer le cache, écriture atomique, et hors réseau on conserve
silencieusement le fichier actuel — un poste en expédition sans internet doit
continuer de fonctionner avec la liste qu'il a.

EMPREINTE MÉMOIRE : la table est chargée UNE fois et ne grandit plus ensuite.
C'est un coût constant, pas une fuite — distinction qui compte sur une
expédition de 15 jours en continu, où seule une croissance sans fin est
dangereuse. Le chiffre mesuré figure dans le test.
"""
import os
import threading
import time

LOTW_URL = 'https://lotw.arrl.org/lotw-user-activity.csv'
LOTW_FILE = 'lotw_users.csv'

# 7 jours : l'ARRL republie en continu, mais un utilisateur qui commence à
# uploader n'a pas besoin d'être connu à l'heure près. Rafraîchir plus souvent
# coûterait 6 Mo à chaque fois pour un gain nul.
MAX_AGE_DAYS = 7

_users = {}          # INDICATIF -> 'AAAA-MM-JJ' (dernier upload)
_loaded = False
_lock = threading.Lock()


def _age_days(path=LOTW_FILE):
    if not os.path.exists(path):
        return None
    return (time.time() - os.path.getmtime(path)) / 86400


def _looks_valid(content):
    """Garde-fou avant de remplacer le cache : jamais une page d'erreur HTML
    ou un fichier tronqué à la place de la liste."""
    if not content or len(content) < 500000:
        return False
    if '<html' in content[:2000].lower():
        return False
    # Au moins une ligne bien formée « INDICATIF,date,heure » dans l'en-tête
    # du fichier — un CSV d'une autre nature échouerait ici.
    for ligne in content.splitlines()[:50]:
        bouts = ligne.split(',')
        if len(bouts) >= 2 and bouts[0].strip() and len(bouts[1].strip()) == 10:
            return True
    return False


def _parse(content):
    """CSV -> {INDICATIF: 'AAAA-MM-JJ'}.

    Les dates sont PARTAGÉES entre entrées (`sys.intern`) : 233 627 lignes ne
    portent que 8 213 dates distinctes, mais un str.strip() fabrique un nouvel
    objet à chaque ligne. Mesuré : la table passe de 33,4 Mo à 18,5 Mo. Gratuit,
    et ça compte sur le portable d'une expédition où le logiciel tourne 15
    jours d'affilée.
    """
    import sys as _sys
    out = {}
    for ligne in content.splitlines():
        bouts = ligne.split(',')
        if len(bouts) < 2:
            continue
        call = bouts[0].strip().upper()
        if call:
            out[call] = _sys.intern(bouts[1].strip())
    return out


def load(path=LOTW_FILE):
    """Charge le cache en mémoire (une seule fois). Sans fichier : table vide,
    et is_lotw_user() renverra None partout — « on ne sait pas », ce qui n'est
    PAS la même chose que « n'utilise pas LoTW »."""
    global _loaded
    with _lock:
        if _loaded:
            return _users
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                _users.update(_parse(f.read()))
            print(f'[LoTW] {len(_users)} utilisateurs charges')
        except Exception:
            pass
        _loaded = True
    return _users


def disponible():
    """La liste est-elle chargée ? Sert à distinguer « pas utilisateur LoTW »
    de « liste pas encore téléchargée » — sans ça l'interface colorerait tout
    le monde en « non-utilisateur » au premier lancement."""
    load()
    return bool(_users)


def is_lotw_user(call):
    """True / False / None si la liste n'est pas disponible.

    Le None est délibéré : afficher « n'utilise pas LoTW » alors qu'on n'a
    simplement pas la liste ferait passer à côté de vrais contacts.
    """
    if not disponible():
        return None
    return _base(call) in _users


def last_upload(call):
    """'AAAA-MM-JJ' du dernier upload, ou '' si inconnu."""
    if not disponible():
        return ''
    return _users.get(_base(call), '')


def _base(call):
    """Indicatif de base : la liste ARRL contient surtout des indicatifs nus,
    alors qu'un spot porte souvent un suffixe (/P, /MM, /QRP). On essaie tel
    quel d'abord — certains indicatifs portables SONT dans la liste (ex.
    2A/DJ6AU, vu dans le fichier) — puis on retombe sur la racine."""
    c = str(call or '').upper().strip()
    if not c:
        return ''
    if c in _users:
        return c
    if '/' in c:
        bouts = [b for b in c.split('/') if b]
        if bouts:
            # Le plus long morceau est l'indicatif dans « F/DJ6AU » comme dans
            # « DJ6AU/P » : un préfixe pays ou un suffixe /P est toujours plus
            # court que l'indicatif lui-même.
            return max(bouts, key=len)
    return c


def update_if_stale(max_age_days=MAX_AGE_DAYS, force=False):
    """Retélécharge la liste si le cache a plus de N jours. Retourne True si
    le fichier a été remplacé. Ne lève jamais : sans réseau, on garde ce
    qu'on a."""
    age = _age_days()
    if not force and age is not None and age < max_age_days:
        return False
    try:
        from logx_utils import fetch_url
        data = fetch_url(LOTW_URL, timeout=60)
    except Exception:
        data = None
    if not _looks_valid(data or ''):
        if age is not None:
            print('[LoTW] Mise a jour impossible (reseau/contenu) - '
                  f'liste actuelle conservee (age {age:.0f} j)')
        return False
    import tempfile
    dossier = os.path.dirname(os.path.abspath(LOTW_FILE)) or '.'
    fd, tmp = tempfile.mkstemp(prefix='lotw.', suffix='.tmp', dir=dossier)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            f.write(data)
        os.replace(tmp, LOTW_FILE)
    except Exception as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        print(f'[LoTW] Ecriture impossible: {e}')
        return False
    # Rechargement à chaud, comme cty.dat : le dict est muté en place, les
    # imports par référence restent valides.
    global _loaded
    with _lock:
        _users.clear()
        _users.update(_parse(data))
        _loaded = True
    print(f'[LoTW] Liste mise a jour : {len(_users)} utilisateurs')
    return True


def annoter(spots):
    """Ajoute 'lotw' (bool|None) et 'lotw_last' (date) à une liste de spots.

    Fait en une passe pour toute la liste : la table est un dict, mais le
    parcours des spots et la normalisation des indicatifs ne sont pas gratuits
    sur plusieurs centaines de lignes rafraîchies en continu.
    """
    dispo = disponible()
    for s in (spots or []):
        call = s.get('call') or s.get('dx') or ''
        if not dispo:
            s['lotw'] = None
            s['lotw_last'] = ''
            continue
        base = _base(call)
        s['lotw'] = base in _users
        s['lotw_last'] = _users.get(base, '')
    return spots
