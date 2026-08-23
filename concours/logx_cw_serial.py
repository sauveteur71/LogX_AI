# -*- coding: utf-8 -*-
"""Keyer CW par ligne série DTR/RTS (keyer CW Phase 3, F4GLD 23/08).

Manipulation CW en pilotant une ligne série (DTR ou RTS) via une interface
transistor/opto — le montage le plus répandu et le repli idéal quand aucun
WinKeyer n'est branché. Le TIMING est généré par le PC (contrairement au
WinKeyer qui le tient lui-même).

Ce module, ÉTAPE 3A, ne contient QUE le cœur PUR et testable :
  - la table Morse (standard UIT-R M.1677) ;
  - keying_sequence(text, wpm) : la suite d'événements (down: bool, durée_ms)
    qui réalise le Morse en temps réel (référence PARIS), SANS toucher le
    matériel.
L'étape 3B branchera la couche matérielle (bascule réelle de DTR/RTS + attente)
et le routage /rig/cw ; l'essai on-air restera la manip supervisée de F4GLD.
"""

# Table Morse UIT-R M.1677-1 (lettres, chiffres, ponctuation courante). Valeurs
# de domaine SOURCÉES (standard), pas inventées. Un caractère absent est ignoré
# (jamais un keying aberrant sur l'air).
MORSE = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
    'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
    'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
    'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
    'Y': '-.--', 'Z': '--..',
    '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-',
    '5': '.....', '6': '-....', '7': '--...', '8': '---..', '9': '----.',
    '.': '.-.-.-', ',': '--..--', '?': '..--..', '/': '-..-.', '=': '-...-',
    '+': '.-.-.', '-': '-....-', '(': '-.--.', ')': '-.--.-', ':': '---...',
    "'": '.----.', '"': '.-..-.', '@': '.--.-.', '!': '-.-.--', '&': '.-...',
    ';': '-.-.-.', '$': '...-..-',
}

# Prosignes usuels (envoyés collés, sans espace inter-caractère interne). Écrits
# entre chevrons dans le texte : <AR>, <SK>, <BT>, <KN>, <AS>, <VE>.
PROSIGNES = {
    'AR': '.-.-.', 'SK': '...-.-', 'BT': '-...-', 'KN': '-.--.',
    'AS': '.-...', 'VE': '...-.',
}


def dit_ms(wpm):
    """Durée d'un point en ms pour `wpm` mots/min (référence PARIS : 1200/wpm)."""
    wpm = max(1, int(wpm))
    return 1200.0 / wpm


def _tokens(text):
    """Découpe le texte en tokens Morse : prosignes <XX> d'un bloc, sinon
    caractères un à un. Les espaces séparent les mots (token None)."""
    s = str(text or '').upper()
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == ' ':
            out.append(None)                     # séparateur de mot
            i += 1
        elif c == '<':
            j = s.find('>', i)
            nom = s[i + 1:j] if j != -1 else ''
            if j != -1 and nom in PROSIGNES:
                out.append(('prosigne', PROSIGNES[nom]))
                i = j + 1
            else:
                i += 1                           # '<' isolé : ignoré
        elif c in MORSE:
            out.append(('char', MORSE[c]))
            i += 1
        else:
            i += 1                               # caractère non manipulable : ignoré
        # Nota : on n'émet jamais rien pour un caractère absent de la table.
    return out


def keying_sequence(text, wpm):
    """Suite d'événements (down: bool, durée_ms: float) manipulant `text` en
    Morse à `wpm` (PARIS). PURE : ne touche aucun matériel.

    Temps standard : point = 1 dit, trait = 3 dit, gap intra-caractère = 1 dit,
    gap inter-caractère = 3 dit, gap inter-mot = 7 dit."""
    dit = dit_ms(wpm)
    seq = []
    prev_symbole = False   # a-t-on déjà émis un caractère/prosigne dans ce mot ?
    for tok in _tokens(text):
        if tok is None:                          # séparateur de mot
            if prev_symbole:
                seq.append((False, 7 * dit))     # gap inter-mot
                prev_symbole = False
            continue
        _, pattern = tok
        if prev_symbole:
            seq.append((False, 3 * dit))         # gap inter-caractère
        prev_symbole = True
        for k, el in enumerate(pattern):
            if k > 0:
                seq.append((False, dit))         # gap intra-caractère
            seq.append((True, dit if el == '.' else 3 * dit))
    return seq


def duree_totale_ms(text, wpm):
    """Durée totale de l'émission (somme des événements) — utile pour un
    timeout/estimation, sans manipuler quoi que ce soit."""
    return sum(d for _, d in keying_sequence(text, wpm))


# ─── ÉTAPE 3B : couche matérielle (bascule réelle DTR/RTS) ────────────────────
# Le keying série est PILOTÉ PAR LE PC et BLOQUANT (boucle de sleeps) : il tourne
# donc dans un THREAD, la requête HTTP revient tout de suite (fire-and-forget,
# comme le WinKeyer). Un Event d'arrêt coupe la boucle et RELÂCHE toujours la clé
# (key up). Écrire ce code n'émet rien ; l'essai on-air reste supervisé.
import threading  # noqa: E402

WPM_MIN, WPM_MAX = 5, 99

_lock = threading.Lock()
_stop = threading.Event()
_thread = None
_port = None
_port_nom = None


def _int(v, defaut):
    try:
        return int(v)
    except (TypeError, ValueError):
        return defaut


def parametres(cfg):
    cfg = cfg or {}
    line = str(cfg.get('cw_serial_line', 'DTR') or 'DTR').upper()
    if line not in ('DTR', 'RTS'):
        line = 'DTR'
    return {
        'enabled': str(cfg.get('cw_serial_enabled', '')).strip() not in ('', '0', 'False', 'false'),
        'port': str(cfg.get('cw_serial_port', '') or '').strip(),
        'line': line,
        'wpm': max(WPM_MIN, min(WPM_MAX, _int(cfg.get('cw_serial_wpm', 22), 22))),
    }


def _set_ligne(port, line, down):
    """Positionne la ligne (RTS ou DTR) : down=True => clé enfoncée (ligne
    haute), montage transistor/opto standard actif-haut."""
    if line == 'RTS':
        port.rts = bool(down)
    else:
        port.dtr = bool(down)


def _executer(port, line, seq, stop, sleep):
    """Boucle de manipulation — TESTABLE : `sleep(sec)` doit renvoyer True si
    l'arrêt a été demandé pendant l'attente (attente interruptible ; en prod
    c'est Event.wait). La clé est TOUJOURS relâchée en sortie (key up), même
    sur arrêt, exception ou fin normale."""
    try:
        for down, ms in seq:
            if stop.is_set():
                break
            _set_ligne(port, line, down)
            if sleep(ms / 1000.0):        # interrompu pendant l'attente ?
                break
    finally:
        try:
            _set_ligne(port, line, False)  # KEY UP impératif
        except Exception:
            pass


def _ouvrir_port(nom):
    """Ouvre le port série avec les lignes BASSES (jamais keyer à l'ouverture).
    Isolé pour être remplacé par un faux port dans les tests."""
    import serial as _pyserial
    s = _pyserial.Serial()
    s.port = nom
    s.rts = False
    s.dtr = False
    s.timeout = 1.0
    s.open()
    return s


def _ouvrir_locked(nom_port):
    global _port, _port_nom
    if _port is not None and _port_nom == nom_port:
        return None
    _fermer_locked()
    try:
        _port = _ouvrir_port(nom_port)
    except Exception as e:
        _port = None
        return "Port %s inutilisable (%s)" % (nom_port, e)
    _port_nom = nom_port
    return None


def _fermer_locked():
    global _port, _port_nom
    if _port is not None:
        try:
            _set_ligne(_port, 'DTR', False)
            _set_ligne(_port, 'RTS', False)
            _port.close()
        except Exception:
            pass
    _port = None
    _port_nom = None


def _arreter_locked():
    _stop.set()
    t = _thread
    if t is not None and t.is_alive():
        t.join(timeout=2.0)   # laisse le finally relâcher la clé


def envoyer(cfg, texte):
    """Manipule `texte` en tâche de fond (retour immédiat). Ne lève jamais."""
    p = parametres(cfg)
    if not p['enabled']:
        return {'ok': False, 'error': 'Keyer série désactivé (CONFIG)'}
    if not p['port']:
        return {'ok': False, 'error': 'Port du keyer série non renseigné (CONFIG)'}
    seq = keying_sequence(texte, p['wpm'])
    if not seq:
        return {'ok': False, 'error': 'Rien à manipuler (texte vide après filtrage)'}
    global _thread
    with _lock:
        _arreter_locked()                      # stoppe une manip précédente
        err = _ouvrir_locked(p['port'])
        if err:
            return {'ok': False, 'error': err}
        _stop.clear()
        _thread = threading.Thread(
            target=_executer, args=(_port, p['line'], seq, _stop, _stop.wait), daemon=True)
        _thread.start()
    return {'ok': True, 'text': str(texte or ''), 'wpm': p['wpm']}


def arreter(cfg):
    """Coupe immédiatement la manip en cours (Esc/STOP). La clé est relâchée."""
    with _lock:
        _arreter_locked()
    return {'ok': True}


def tester(cfg):
    """Ouvre le port pour valider la config (bouton CONFIG)."""
    p = parametres(cfg)
    if not p['port']:
        return {'ok': False, 'error': 'Port non renseigné'}
    with _lock:
        err = _ouvrir_locked(p['port'])
    if err:
        return {'ok': False, 'error': err}
    return {'ok': True, 'line': p['line']}
