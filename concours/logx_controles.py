# -*- coding: utf-8 -*-
"""IA-1 — contrôles de cohérence DÉTERMINISTES, indépendants de l'activité.

Chaque fonction reçoit un QSO (dict interne du log) et rend soit
(level, code, msg) — un finding au format attendu par logx_validator._f — soit
None si tout va bien ou si le cas est trop ambigu pour trancher sans faux
positif. Fonctions PURES : aucune I/O, aucune horloge en dur (la date du jour
est injectée). Valeurs de domaine tirées des tables déjà sourcées du dépôt.
"""
import re

from logx_scoring import _band_from_freq   # '14.075'/'14075' -> bande interne '14'
from logx_activation import PROGRAM_SPECS, validate_ref

# Modes WSJT-X à rapport de signal en dB (SNR), PAS en RST : un « 59 »/« 599 »
# y trahit un RST par défaut oublié. Source : WSJT-X User Guide (§ Reporting,
# le rapport échangé est le S/N en dB). Liste restreinte aux modes que LogX
# manipule / qu'un import ADIF peut porter.
_MODES_RAPPORT_DB = {'FT8', 'FT4', 'FT2', 'JT65', 'JT9', 'JT4', 'FST4',
                     'FST4W', 'Q65', 'MSK144', 'JS8', 'WSPR'}
# 2-3 chiffres nus : allure d'un RST (59/599). Un rapport dB porte un signe
# (« -12 », « +03 ») ou n'est pas de cette forme -> non signalé.
_RST_STYLE_RE = re.compile(r'^\d{2,3}$')


def controle_freq_bande(q):
    """Fréquence loguée incohérente avec la bande loguée. Silencieux si freq
    absente ou hors de toute bande connue (on ne signale pas l'indécidable)."""
    freq = str(q.get('freq', '') or '').strip()
    if not freq:
        return None
    bande_calc = _band_from_freq(freq)
    bande_log = str(q.get('band', '') or '').strip()
    if bande_calc and bande_log and bande_calc != bande_log:
        # Pas d'unité codée en dur dans le libellé : `freq` peut être en MHz
        # ('14.075') ou en kHz ('14075') — _band_from_freq gère les deux, mais
        # une étiquette « MHz » serait fausse pour une valeur en kHz.
        return ('attention', 'freq_bande_incoherente',
                f"Fréquence {freq} incohérente avec la bande {bande_log} MHz "
                f"(attendu bande {bande_calc})")
    return None


def controle_date_future(q, maintenant_utc):
    """Date de QSO postérieure au jour UTC courant (`maintenant_utc` = 'YYYYMMDD')."""
    date = re.sub(r'\D', '', str(q.get('date', '') or ''))
    if len(date) == 8 and date > str(maintenant_utc):
        return ('attention', 'date_future',
                f"Date {date} postérieure à aujourd'hui ({maintenant_utc})")
    return None


def controle_heure_fin(q):
    """Heure de fin (time_off) antérieure à l'heure de début (time), même date.
    Niveau info : un QSO chevauchant minuit UTC produit légitimement ce cas —
    rare, faible enjeu, non alarmant. Compare HHMM numériquement."""
    t_on = re.sub(r'\D', '', str(q.get('time', '') or ''))[:4]
    t_off = re.sub(r'\D', '', str(q.get('time_off', '') or ''))[:4]
    if len(t_on) == 4 and len(t_off) == 4 and int(t_off) < int(t_on):
        return ('info', 'heure_fin_avant_debut',
                f"Heure de fin {t_off} avant l'heure de début {t_on}")
    return None


def _mode_effectif(q):
    """Mode réellement utilisé : le SOUS-MODE prime quand il est renseigné
    (FT4/JS8 sont logués MODE=MFSK + SUBMODE=FT4 selon la norme ADIF). Le
    sous-mode peut vivre en clé `submode` ou, pour un QSO importé, dans
    extra_fields['SUBMODE']."""
    sub = str(q.get('submode', '') or '').upper().strip()
    if not sub:
        sub = str((q.get('extra_fields') or {}).get('SUBMODE', '') or '').upper().strip()
    return sub or str(q.get('mode', '') or '').upper().strip()


def controle_rst_mode(q):
    """RST de style 59/599 sur un mode à rapport dB (FT8…) : probable défaut
    oublié. Conservateur : ne signale que ce cas net, jamais l'inverse. Tient
    compte du sous-mode (FT4/JS8 en MODE=MFSK)."""
    mode = _mode_effectif(q)
    if mode not in _MODES_RAPPORT_DB:
        return None
    for champ in ('rst_sent', 'rst_rcvd'):
        val = str(q.get(champ, '') or '').strip()
        if val and _RST_STYLE_RE.match(val):
            return ('info', 'rst_incoherent_mode',
                    f"RST {val} en {mode} : ce mode se rapporte en dB (ex. -12), "
                    f"pas en 59/599")
    return None


def controle_activation_ref(q):
    """Références d'activation : programme déclaré sans référence, ou référence
    au mauvais format. Côté station (my_sig) = attention ; côté correspondant
    (sig) = info (on subit la réf de l'autre). Réutilise PROGRAM_SPECS."""
    out = []
    for prog_key, info_key, niveau, prefixe in (
            ('my_sig', 'my_sig_info', 'attention', 'Ma référence'),
            ('sig', 'sig_info', 'info', 'Référence correspondant')):
        prog = str(q.get(prog_key, '') or '').upper().strip()
        ref = str(q.get(info_key, '') or '').strip()
        if not prog or prog not in PROGRAM_SPECS:
            continue
        if not ref:
            out.append((niveau, 'activation_sans_ref',
                        f"{prefixe} : programme {prog} déclaré sans référence"))
        elif not validate_ref(prog, ref):
            out.append((niveau, 'ref_format_invalide',
                        f"{prefixe} {prog} « {ref} » : format invalide"))
    return out


def controles_coherence(q, maintenant_utc):
    """Tous les findings de cohérence pour un QSO (liste de (level, code, msg))."""
    res = []
    for f in (controle_freq_bande(q), controle_date_future(q, maintenant_utc),
              controle_heure_fin(q), controle_rst_mode(q)):
        if f:
            res.append(f)
    res.extend(controle_activation_ref(q))
    return res
