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
