# -*- coding: utf-8 -*-
"""Scans de cartes QSL papier attachés à un QSO — stockage simple sur disque
(dossier qsl_scans/), à ne pas confondre avec logx_qsl.py (services de
confirmation EN LIGNE : eQSL/ClubLog/QRZCQ/HRDLog/LoTW). Ici il s'agit d'une
photo/scan de carte papier, jointe manuellement par l'opérateur.

Ce module ne connaît PAS shared_log : comme logx_qsl.upload_log() qui reçoit
ses QSO en paramètre, il se contente de valider/écrire/effacer le fichier —
c'est l'appelant (logx_http.py, qui détient déjà log_lock) qui pose la
référence (chemin relatif) sur le QSO."""
import os
import time

SCANS_DIR = 'qsl_scans'

# Formats plausibles pour un scan de carte papier (scanner à plat ou photo
# téléphone) — volontairement restrictif, aucun exécutable/script.
ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf'}


def _safe_ext(filename):
    ext = os.path.splitext(str(filename or ''))[1].lower()
    return ext if ext in ALLOWED_EXT else None


def save_scan(qso_id, filename, data):
    """Écrit le scan sur disque, renvoie le chemin relatif (séparateur '/',
    pour un usage direct en URL/JSON) à poser sur le QSO. Lève ValueError si
    extension refusée ou fichier vide."""
    ext = _safe_ext(filename)
    if not ext:
        raise ValueError(f"Format de fichier non accepté ({filename!r}) — "
                         f"formats acceptés : {', '.join(sorted(ALLOWED_EXT))}")
    if not data:
        raise ValueError('Fichier vide')
    os.makedirs(SCANS_DIR, exist_ok=True)
    # Nom dérivé de l'id QSO + horodatage — JAMAIS le nom d'origine fourni par
    # le client (potentiellement piégé, cf. l'audit sécurité qui a déjà relevé
    # ce type de souci sur le service de fichiers statiques). La milliseconde
    # seule ne suffit pas à garantir l'unicité (deux uploads rapprochés — ex.
    # recto/verso d'une même carte — PEUVENT tomber sur la même milliseconde,
    # constaté en test) : on ajoute un suffixe croissant tant que le nom existe
    # déjà, pour ne JAMAIS écraser un scan précédent en silence.
    base_name = f"qso_{int(qso_id)}_{int(time.time() * 1000)}"
    name = f"{base_name}{ext}"
    path = os.path.join(SCANS_DIR, name)
    n = 1
    while os.path.exists(path):
        name = f"{base_name}_{n}{ext}"
        path = os.path.join(SCANS_DIR, name)
        n += 1
    with open(path, 'wb') as f:
        f.write(data)
    return f"{SCANS_DIR}/{name}"


def delete_scan(rel_path):
    """Supprime un ancien scan (remplacement par un nouveau) — silencieux si
    absent ou si le chemin ne pointe pas STRICTEMENT dans SCANS_DIR (défense
    en profondeur, même logique de confinement que Handler._resolve)."""
    rel_path = str(rel_path or '').replace('\\', '/')
    if not rel_path.startswith(SCANS_DIR + '/'):
        return
    try:
        base = os.path.realpath(SCANS_DIR)
        full = os.path.realpath(rel_path)
        if full.startswith(base + os.sep) and os.path.isfile(full):
            os.remove(full)
    except OSError:
        pass
