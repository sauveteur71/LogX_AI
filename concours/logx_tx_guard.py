# -*- coding: utf-8 -*-
"""Garde-fou d'émission TX unifié (CW + phonie).

Généralise le garde-fou CW (F4GLD 23/08/2026, Phase 1 keyer CW natif) à toute
émission déclenchée par macro. Mêmes principes, refus BLOQUANT (jamais un simple
avertissement) :

  1. TX-ENABLE MAÎTRE : le client doit ARMER explicitement (`armed`). Désarmé par
     défaut -> aucune émission par inadvertance (Échap réflexe, macro cliquée…).
  2. MODE selon la FAMILLE demandée :
       - 'cw'     : refuse si le mode connu n'est PAS un mode CW.
       - 'phonie' : refuse si le mode connu est CW ou un mode DATA/numérique
                    (RTTY/FSK/DATA*/PKT*/FT8…). LSB/USB/AM/FM/inconnu -> OK.
     Mode inconnu (champ vide, pas de CAT) -> on ne bloque pas sur ce seul
     critère, l'arme reste requise.
  3. HORS PLAN DE BANDE : si la fréquence est CONNUE (CAT) et hors de toute bande
     amateur, on refuse. Fréquence inconnue -> on NE bloque PAS sur ce critère.

Le garde-fou valide le mode et la fréquence qui seront réellement TRANSMIS — le
VFO TX en split/cross-mode. Le client envoie ces valeurs. Fonction PURE (aucune
I/O radio), testable sans poste ni serveur. Écrire ce garde-fou n'émet rien.
"""


def est_mode_cw(mode):
    """True pour tout mode CW du poste : CW, CWR, CW-R, CW-U, CW-L, CW-N…"""
    m = str(mode or '').upper().replace('_', '-').strip()
    return m.startswith('CW')


# Marqueurs des modes DATA/numériques tels que RAPPORTÉS PAR LE POSTE (chaînes
# CAT). Sourcés du vocabulaire de logx_cat.py — jamais inventés de mémoire :
#   - RTTY / FSK : MODE_RTTY_PAR_MARQUE (logx_cat.py) et tables ASCII des modes
#     ('RTTY-LSB', 'FSK', 'RTTY-USB'…).
#   - PKT* (PKTUSB/PKTLSB/PKTFM/PKTAM) : CivRadio.set_mode (logx_cat.py).
#   - DATA* (DATA-USB/DATA/DATA-REV) : tables ASCII des modes ('C' = DATA-USB).
#   - DIG/DIGI : MODES_NUMERIQUES (logx_cat.py).
# Les NOMS LOGIQUES numériques (FT8, PSK, JT65…) sont couverts en plus via
# logx_cat.MODES_NUMERIQUES, au cas où le client enverrait un mode du carnet
# plutôt qu'une chaîne du poste.
_MARQUEURS_DATA = ('RTTY', 'FSK', 'PKT', 'DATA', 'DIG')


def est_mode_data(mode):
    """True si `mode` désigne un mode DATA/numérique — on n'y émet pas de voix.

    Accepte aussi bien une chaîne rapportée par le poste (DATA-USB, PKTUSB…)
    qu'un nom logique du carnet (FT8, PSK…)."""
    m = str(mode or '').upper().replace('_', '-').strip()
    if not m:
        return False
    if any(marqueur in m for marqueur in _MARQUEURS_DATA):
        return True
    try:
        import logx_cat
        if m in logx_cat.MODES_NUMERIQUES:
            return True
    except Exception:
        # Repli sûr : sans logx_cat, les marqueurs de chaîne ci-dessus couvrent
        # déjà les créneaux data réels du poste ; on n'AUTORISE jamais à tort la
        # voix -> au pire un nom logique isolé (FT8) passe, l'arme reste requise.
        pass
    return False


def tx_autorise(payload, famille):
    """Autorise (ou non) une émission de la `famille` donnée ('cw' | 'phonie').

    `payload` : le dict de la requête (au moins {armed, mode}, éventuellement
    {freq_khz}) — mode/fréquence du VFO qui ÉMET. Retourne (ok: bool, raison:
    str) ; `raison` est vide si autorisé, sinon un message prêt à afficher."""
    if not isinstance(payload, dict):
        return False, "Requête d'émission invalide."
    if not payload.get('armed'):
        return False, ("TX non armé — arme l'émission (interrupteur maître) "
                       "avant d'émettre.")
    mode = payload.get('mode', '')
    if famille == 'cw':
        if mode and not est_mode_cw(mode):
            return False, (f"Le poste est en « {mode} » — passe-le en CW "
                           "avant d'émettre du CW.")
    elif famille == 'phonie':
        if mode and (est_mode_cw(mode) or est_mode_data(mode)):
            return False, (f"Le poste est en « {mode} » — passe-le en phonie "
                           "(SSB/FM/AM) avant d'émettre de la voix.")
    else:
        return False, f"Famille d'émission inconnue : « {famille} »."
    freq = payload.get('freq_khz')
    if freq not in (None, ''):
        import logx_frequences as freq_mod
        if freq_mod.en_bande_amateur(freq) is False:
            return False, (f"Fréquence {freq} kHz hors des bandes amateur — "
                           "vérifie le VFO avant d'émettre.")
    return True, ''
