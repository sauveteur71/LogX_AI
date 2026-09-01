# -*- coding: utf-8 -*-
"""Décodage Q65 EME natif (hors-ligne) : capture carte son → segments 12 kHz
alignés UTC → jt9 embarqué → décodages au format cockpit. N'émet JAMAIS ;
réception seule (l'émission relèverait du skill tx-human-consent)."""
import os
import re
import shutil
import subprocess
import tempfile
import time
import wave

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


def resoudre_jt9(cfg=None):
    """Détermine le chemin absolu du binaire jt9 à utiliser, par ordre de
    priorité : config `eme.jt9_path` explicite > binaire embarqué
    (concours/vendor/jt9/<os>/jt9[.exe], livré Tâche 8) > jt9/jt9.exe trouvé
    sur le PATH. Lève FileNotFoundError explicite si aucun des trois."""
    p = ((cfg or {}).get('eme', {}) or {}).get('jt9_path')
    if p and os.path.isfile(p):
        return p
    # Binaire embarqué (Task 8) : concours/vendor/jt9/<os>/jt9[.exe]
    ici = os.path.dirname(os.path.abspath(__file__))
    for nom in ('jt9.exe', 'jt9'):
        cand = os.path.join(ici, 'vendor', 'jt9', nom)
        if os.path.isfile(cand):
            return cand
    trouve = shutil.which('jt9') or shutil.which('jt9.exe')
    if trouve:
        return trouve
    raise FileNotFoundError(
        "jt9 introuvable : renseigne eme.jt9_path dans config.json, "
        "installe WSJT-X, ou fournis le binaire embarqué."
    )


def decoder_wav(wav_path, *, submode='A', tr_period=60, jt9_path=None,
                 data_path=None, ap=None, freq_mhz=0.0, band='', timeout=55.0):
    """Lance jt9 en sous-processus sur un fichier .wav (déjà capturé/aligné
    UTC en amont) et retourne les décodages Q65 normalisés. `ap` (décodage
    assisté, optionnel) porte 'my_call'/'my_grid'/'his_call'/'his_grid'/
    'qso_prog', traduits en flags -c/-G/-x/-g/-Q. Réception seule : ne
    déclenche jamais d'émission."""
    jt9_path = jt9_path or resoudre_jt9()
    # `tmp` sert à la fois de dossier de données jt9 (-a) ET de répertoire
    # courant du sous-processus (cwd=tmp) : jt9 y écrit ses fichiers de
    # travail (avemsg.txt/decoded.txt/red.dat/…) INDÉPENDAMMENT du flag -a,
    # donc dans le cwd — sans cwd=tmp ils atterriraient dans le dossier du
    # serveur appelant (Tâche 5). On ne supprime QUE le dossier créé en
    # interne : un data_path fourni par l'appelant lui appartient.
    tmp = data_path or tempfile.mkdtemp(prefix='logx_q65_')
    ephemere = data_path is None
    argv = [jt9_path, '-3', '-p', str(int(tr_period)), '-b', submode,
            '-q', '-a', tmp, wav_path]
    if ap:
        for flag, cle in (('-c', 'my_call'), ('-G', 'my_grid'),
                          ('-x', 'his_call'), ('-g', 'his_grid'),
                          ('-Q', 'qso_prog')):
            if ap.get(cle) not in (None, ''):
                argv += [flag, str(ap[cle])]
    try:
        res = subprocess.run(argv, capture_output=True, text=True,
                             timeout=timeout, cwd=tmp)
        return parse_jt9_stdout(res.stdout, freq_mhz=freq_mhz, band=band)
    finally:
        if ephemere:
            shutil.rmtree(tmp, ignore_errors=True)


def bornes_fenetre(now, tr_period=60):
    """Début/fin (epoch) de la fenêtre T/R alignée contenant `now`.
    Exemple : tr_period=60 s → fenêtre alignée sur la minute UTC pleine."""
    tr = int(tr_period)
    debut = (int(now) // tr) * tr
    return float(debut), float(debut + tr)


def ecrire_wav_12k(path, echantillons):
    """WAV PCM 16 bit mono 12 kHz — format d'entrée attendu par jt9.
    Args:
        path : chemin absolu du fichier WAV à créer.
        echantillons : octets int16 little-endian (bytes)."""
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(12000)
        w.writeframes(echantillons)


def _sd():
    """Import PARESSEUX de sounddevice (PortAudio) : le natif est opt-in,
    un wheel PortAudio absent ou cassé sur la plateforme ne doit jamais
    empêcher l'import de ce module (voir test_module_importe_sans_sounddevice)."""
    import sounddevice as sd
    return sd


def lister_peripheriques_entree():
    """Périphériques d'ENTRÉE audio disponibles pour la capture EME :
    [{'index', 'nom', 'canaux', 'freq_defaut'}]. Réception seule — ne liste
    délibérément pas les périphériques de sortie (aucun usage d'émission ici)."""
    sd = _sd()
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d.get('max_input_channels', 0) > 0:
            out.append({'index': i, 'nom': d['name'],
                        'canaux': d['max_input_channels'],
                        'freq_defaut': int(d.get('default_samplerate', 0))})
    return out


class FluxCapture:
    """Capte une entrée audio en 12 kHz mono et livre des fenêtres T/R
    complètes à `on_fenetre`. Ne fait AUCUN décodage lui-même — seul le
    découpage temporel (bornes_fenetre) et l'accumulation d'échantillons
    sont de son ressort. Réception seule : aucun flux de sortie, aucun PTT."""

    def __init__(self, device_index, on_fenetre, tr_period=60):
        self.device_index = device_index
        self.on_fenetre = on_fenetre
        self.tr_period = tr_period
        self._stream = None
        self._buf = bytearray()
        self._fenetre = None

    def demarrer(self):
        """Ouvre le flux d'entrée 12 kHz mono int16 et démarre la capture.
        Le callback PortAudio (_cb) tourne dans un thread dédié à sounddevice."""
        sd = _sd()
        self._stream = sd.RawInputStream(
            samplerate=12000, channels=1, dtype='int16',
            device=self.device_index, callback=self._cb)
        self._stream.start()

    def _cb(self, indata, frames, time_info, status):
        """Callback PortAudio : accumule les échantillons dans le tampon
        courant et, dès que l'horodatage franchit la borne de fenêtre T/R,
        livre le tampon PRÉCÉDENT (fenêtre complète) à on_fenetre avant de
        repartir sur un tampon vide."""
        now = time.time()
        deb, _ = bornes_fenetre(now, self.tr_period)
        if self._fenetre is None:
            self._fenetre = deb
        if deb != self._fenetre:                 # fenêtre terminée
            self.on_fenetre(bytes(self._buf), self._fenetre)
            self._buf = bytearray()
            self._fenetre = deb
        self._buf += bytes(indata)

    def arreter(self):
        """Arrête et referme le flux de capture (idempotent)."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
