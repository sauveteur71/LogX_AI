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


def controle_freq_bande(q):
    """Fréquence loguée incohérente avec la bande loguée. Silencieux si freq
    absente ou hors de toute bande connue (on ne signale pas l'indécidable)."""
    freq = str(q.get('freq', '') or '').strip()
    if not freq:
        return None
    bande_calc = _band_from_freq(freq)
    bande_log = str(q.get('band', '') or '').strip()
    if bande_calc and bande_log and bande_calc != bande_log:
        return ('attention', 'freq_bande_incoherente',
                f"Fréquence {freq} MHz incohérente avec la bande {bande_log} "
                f"(attendu {bande_calc})")
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
