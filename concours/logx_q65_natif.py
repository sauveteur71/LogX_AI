# -*- coding: utf-8 -*-
"""Décodage Q65 EME natif (hors-ligne) : capture carte son → segments 12 kHz
alignés UTC → jt9 embarqué → décodages au format cockpit. N'émet JAMAIS ;
réception seule (l'émission relèverait du skill tx-human-consent)."""
import re
import time

import logx_wsjtx as wsjtx

# Ligne stdout jt9 : "HHMM SNR DT FREQ :  message ... qN"
_LIGNE = re.compile(
    r'^\s*\d{4}\s+(-?\d+)\s+([\d.+-]+)\s+(\d+)\s+:\s+(.*?)\s+q\S*\s*$'
)


def parse_jt9_stdout(stdout, *, freq_mhz=0.0, band='', my_call='', now=None):
    """Transforme le stdout d'un décodage jt9 Q65 en liste de décodages
    normalisés (mêmes clés que wsjtx.eme_decodes()). Ignore <DecodeFinished>
    et toute ligne hors-format. Réutilise extract_calls/extract_grid de
    logx_wsjtx (cohérence avec le chemin UDP, piège RR73 déjà géré)."""
    if now is None:
        now = time.time()
    out = []
    for ligne in (stdout or '').splitlines():
        m = _LIGNE.match(ligne)
        if not m:
            continue
        snr, dt, dfreq, message = m.groups()
        message = message.strip()
        calls = wsjtx.extract_calls(message, my_call)
        out.append({
            'call': calls[0] if calls else '',
            'grid': wsjtx.extract_grid(message),
            'mode': 'Q65',
            'message': message,
            'snr': int(snr),
            'dt': float(dt),
            'delta_hz': int(dfreq),
            'freq_mhz': freq_mhz,
            'band': band,
            'last_seen': now,
        })
    return out
