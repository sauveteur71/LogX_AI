# -*- coding: utf-8 -*-
"""Filtre « Ce que je chasse » de la page CHASSE : famille de mode + bandes.

Demande F4GLD (28/10/2026) : choisir CW / Phonie / Data et les bandes sur
lesquelles on veut des propositions. Le classement d'un spot dans une famille
est fait ICI, côté serveur, et UNE seule fois : chaque endpoint de spots
(need-list, POTA, SOTA, WWFF) annote `mode_cat`, et le navigateur ne fait que
comparer cette étiquette au choix de l'opérateur — aucune table de modes
dupliquée en JavaScript (piège documenté du dépôt).

Sources réutilisées, aucune liste inventée :
  - logx_cat.MODES_NUMERIQUES / MODES_PHONIE : vocabulaire déjà utilisé pour
    commander la radio ;
  - logx_awards.mode_depuis_frequence : repli par plan de bande quand le spot
    n'annonce pas son mode (renvoie 'CW' / 'PHONE' / 'DIGITAL').
"""

CATEGORIES = ('cw', 'phonie', 'data')

# Compléments au vocabulaire de logx_cat (qui raisonne en modes de COMMANDE
# radio) : les libellés que les sources de spots annoncent réellement.
_CW = frozenset(('CW', 'CW-R'))
_PHONIE_EN_PLUS = frozenset(('USB', 'LSB', 'FM', 'AM', 'DV', 'DSTAR', 'DMR',
                             'C4FM', 'FUSION', 'SSTV'))
_DATA_EN_PLUS = frozenset(('RTTY', 'FSK', 'FT8', 'FT4', 'PKT', 'PACKET',
                           'VARAC', 'OLIVIA', 'HELL', 'MT63', 'THOR'))
_DEPUIS_PLAN = {'CW': 'cw', 'PHONE': 'phonie', 'DIGITAL': 'data'}


def categorie_mode(mode, freq_khz=None):
    """'cw' | 'phonie' | 'data' | '' (inconnu).

    Le mode ANNONCÉ prime ; s'il est absent ou inconnu, la fréquence décide
    via le plan de bande. Une fréquence hors plan et sans mode -> ''."""
    from logx_cat import MODES_NUMERIQUES, MODES_PHONIE
    m = str(mode or '').upper().strip().replace('_', '-')
    if m:
        if m in _CW:
            return 'cw'
        if m in MODES_PHONIE or m in _PHONIE_EN_PLUS:
            return 'phonie'
        if m in MODES_NUMERIQUES or m in _DATA_EN_PLUS or m.startswith('PSK'):
            return 'data'
    if freq_khz:
        try:
            from logx_awards import mode_depuis_frequence
            return _DEPUIS_PLAN.get(mode_depuis_frequence(freq_khz), '')
        except Exception:
            return ''
    return ''


def annoter(spots):
    """Pose `mode_cat` sur chaque spot (dict), en place. Renvoie la liste."""
    for s in spots or []:
        if isinstance(s, dict):
            s['mode_cat'] = categorie_mode(s.get('mode'), s.get('freq'))
    return spots


def lire_choix(qs):
    """(bandes, categories) depuis la query-string déjà parsée (parse_qs).

    `bands=7,14` (ou l'ancien `band=7`, Band Map) et `modes=cw,phonie`.
    Valeurs inconnues ignorées ; ensemble vide = « tout »."""
    def _liste(cle):
        brut = ','.join(qs.get(cle, []))
        return {v.strip() for v in brut.split(',') if v.strip()}
    bandes = _liste('bands') | _liste('band')
    cats = {c.lower() for c in _liste('modes')} & set(CATEGORIES)
    return bandes, cats


def garder(spot, bandes, cats):
    """True si le spot correspond au choix (ensembles vides = pas de filtre).

    Un spot de catégorie inconnue est ÉCARTÉ dès qu'un filtre de mode est
    actif : le montrer dans « CW » sans savoir s'il est en CW tromperait."""
    if bandes:
        from logx_scoring import _band_from_freq
        b = str(spot.get('band', '') or '')
        if b not in bandes and _band_from_freq(spot.get('freq', '')) not in bandes:
            return False
    if cats and spot.get('mode_cat', '') not in cats:
        return False
    return True


def filtrer(spots, bandes, cats):
    return [s for s in (spots or []) if garder(s, bandes, cats)]
