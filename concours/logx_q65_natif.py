# -*- coding: utf-8 -*-
"""Décodage Q65 EME natif (hors-ligne) : capture carte son → segments 12 kHz
alignés UTC → jt9 embarqué → décodages au format cockpit. N'émet JAMAIS ;
réception seule (l'émission relèverait du skill tx-human-consent)."""
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
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


def _env_avec_libs(jt9_path):
    """Environnement du sous-processus jt9, avec le dossier du binaire ajouté au
    chemin de recherche des bibliothèques dynamiques. Nécessaire pour le binaire
    embarqué (Tâche 8) : jt9 et ses dépendances (fftw3f, libgfortran…) vivent
    ensemble dans vendor/jt9/, et il faut que jt9 les y trouve — y compris dans
    l'exécutable PyInstaller GELÉ, qui réinitialise LD_LIBRARY_PATH pour les
    processus fils (sans ceci, jt9 ne trouverait pas ses .so une fois figé).
    Sous Windows, les DLL voisines de l'exe sont trouvées d'office : rien à
    faire. Inoffensif quand jt9 vient du PATH (deps résolues par le système)."""
    env = os.environ.copy()
    if os.name == 'nt':
        return env
    var = 'DYLD_LIBRARY_PATH' if sys.platform == 'darwin' else 'LD_LIBRARY_PATH'
    d = os.path.dirname(os.path.abspath(jt9_path))
    ancien = env.get(var, '')
    env[var] = d + (os.pathsep + ancien if ancien else '')
    return env


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
    # PAS de -q : dans jt9 VANILLA (celui embarqué en release), « -q » (quiet)
    # supprime aussi l'écriture des décodages sur stdout — jt9 tourne mais ne
    # renvoie rien à parser (mesuré sur les 3 OS en CI). Le fork « Improved »
    # les imprimait malgré -q, d'où le piège masqué en local. Le parser ignore
    # déjà la ligne <DecodeFinished>, donc on la laisse s'afficher.
    argv = [jt9_path, '-3', '-p', str(int(tr_period)), '-b', submode,
            '-a', tmp, wav_path]
    if ap:
        for flag, cle in (('-c', 'my_call'), ('-G', 'my_grid'),
                          ('-x', 'his_call'), ('-g', 'his_grid'),
                          ('-Q', 'qso_prog')):
            if ap.get(cle) not in (None, ''):
                argv += [flag, str(ap[cle])]
    try:
        res = subprocess.run(argv, capture_output=True, text=True,
                             timeout=timeout, cwd=tmp,
                             env=_env_avec_libs(jt9_path))
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


# --- Orchestrateur : boucle capture -> décodage -> cache TTL ---------------
#
# `FluxCapture.on_fenetre` (voir `_cb` ci-dessus) s'exécute DANS le callback
# temps réel de PortAudio : y appeler `_traiter_fenetre` (écriture WAV +
# sous-processus jt9, potentiellement plusieurs secondes) provoquerait des
# pertes d'échantillons/xruns côté carte son. On découple donc capture et
# décodage par une file : `on_fenetre` ne fait qu'un `put` non bloquant, un
# thread worker dédié dépile et traite chaque fenêtre l'une après l'autre.
_queue = queue.Queue()
_SENTINELLE = object()          # marqueur d'arrêt du worker (identité, pas valeur)

_cache = []                     # décodages récents (liste de dicts)
_cache_lock = threading.Lock()

_flux = None                    # FluxCapture actif, ou None si moteur arrêté
_worker = None                  # thread worker actif, ou None si moteur arrêté
# Finding M1 (revue finale) : demarrer_moteur/arreter_moteur faisaient un
# test-puis-assigne (`if _flux is not None: ...` puis `_flux, _worker = ...`)
# SANS verrou. Sous logx_http.py (serveur HTTP threadé), deux requêtes
# POST /eme/moteur {action:'start'} concurrentes peuvent toutes deux lire
# `_flux is None` avant qu'aucune n'ait eu le temps d'assigner — chacune
# ouvre alors SON PROPRE FluxCapture/worker, et un seul survit dans les
# globals (l'autre devient un flux/thread orphelin, jamais arrêté par
# arreter_moteur). Un `threading.Lock` de module protège tout le corps des
# deux fonctions (check-and-set + assignation des globals inclus).
_moteur_lock = threading.Lock()


def _traiter_fenetre(echantillons, t_debut, cfg):
    """Traite UNE fenêtre déjà captée : écrit un WAV 12 kHz temporaire, lance
    jt9 dessus, et ajoute les décodages obtenus au cache. Appelée soit
    directement (tests, sans matériel), soit par le worker ci-dessous —
    jamais depuis le callback audio temps réel (voir note plus haut).

    Le dossier temporaire est créé ET nettoyé ICI (bloc `finally`) : comme
    `data_path` est fourni explicitement à `decoder_wav`, celui-ci considère
    qu'il appartient à l'appelant et ne le supprime PAS (comportement fixé
    Tâche 2 : nettoyage seulement si le dossier est créé en interne). Sans ce
    nettoyage, chaque fenêtre (une toutes les tr_period secondes) laisserait
    un dossier orphelin — fuite disque garantie sur une session EME longue."""
    eme = (cfg or {}).get('eme', {}) or {}
    submode = eme.get('submode', 'A')
    band = eme.get('band', '')
    rf = float(eme.get('rf_mhz', 0.0) or 0.0)
    tmpdir = tempfile.mkdtemp(prefix='logx_q65_')
    try:
        wav = os.path.join(tmpdir, 'seg.wav')
        ecrire_wav_12k(wav, echantillons)
        decs = decoder_wav(wav, submode=submode,
                            tr_period=int(eme.get('tr_period', 60)),
                            jt9_path=eme.get('jt9_path'), data_path=tmpdir,
                            freq_mhz=rf, band=band)
        with _cache_lock:
            _cache.extend(decs)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def decodes_natifs(max_age=wsjtx._DECODE_TTL):
    """Décodages Q65 natifs récents (mêmes clés que wsjtx.eme_decodes()).
    Purge les entrées plus vieilles que `max_age` AVANT de retourner la vue
    (même logique que recent_decodes() côté pont WSJT-X : lecture et purge
    dans le même verrou, jamais relâché entre les deux)."""
    limite = time.time() - max_age
    with _cache_lock:
        _cache[:] = [d for d in _cache if d.get('last_seen', 0) >= limite]
        return list(_cache)


def _boucle_worker(cfg):
    """Corps du thread worker : dépile les fenêtres une par une et les
    traite séquentiellement. Une fenêtre qui plante (jt9 absent, wav
    corrompu, timeout...) NE DOIT PAS tuer le worker : une session EME dure
    des heures, une erreur isolée sur une fenêtre ne doit pas priver toutes
    les suivantes de décodage."""
    while True:
        item = _queue.get()
        if item is _SENTINELLE:
            break
        echantillons, t_debut = item
        try:
            _traiter_fenetre(echantillons, t_debut, cfg)
        except Exception as e:
            print("[Q65-NATIF] fenêtre ignorée après erreur : %s" % e)


def demarrer_moteur(cfg):
    """Démarre la capture (FluxCapture) et le worker de décodage. Réentrant :
    un second appel alors que le moteur tourne déjà ne relance rien et
    répond `{'ok': True, 'deja': True}`.

    RULING (revue Tâche 5, durci Tâche 7) : les globals `_flux`/`_worker` ne
    sont assignés qu'APRÈS un `FluxCapture.demarrer()` réussi. Si la carte
    son est absente ou que sounddevice échoue, le worker déjà démarré est
    arrêté proprement (sentinelle + join) et RIEN n'est laissé assigné —
    l'état est comme si `demarrer_moteur` n'avait jamais été appelé, pour
    qu'un appel suivant retente pour de vrai au lieu de répondre `deja: True`
    sur un fantôme."""
    global _flux, _worker
    with _moteur_lock:
        if _flux is not None:
            return {'ok': True, 'deja': True}
        eme = (cfg or {}).get('eme', {}) or {}
        worker = threading.Thread(target=_boucle_worker, args=(cfg,),
                                  daemon=True, name='q65-natif-worker')
        worker.start()
        # cfg.eme.audio_device vient d'un <select> HTML (chaîne, potentiellement
        # vide) — même convention que logx_voicekeyer.play_wav : une chaîne vide
        # devient None (périphérique par défaut), une chaîne numérique devient un
        # entier. Sans cette normalisation, sounddevice recevrait device=''.
        idx_brut = eme.get('audio_device')
        idx = int(idx_brut) if idx_brut not in (None, '') else None
        tr_period = int(eme.get('tr_period', 60))
        # on_fenetre s'exécute dans le callback PortAudio : UNIQUEMENT un put
        # non bloquant, aucun traitement lourd ici (voir note en tête de section).
        flux = FluxCapture(idx, lambda ech, t: _queue.put((ech, t)),
                           tr_period=tr_period)
        try:
            flux.demarrer()
        except Exception as e:
            _queue.put(_SENTINELLE)
            worker.join(timeout=2.0)
            return {'ok': False, 'error': str(e)}
        _flux, _worker = flux, worker
        return {'ok': True}


def arreter_moteur():
    """Arrête le flux de capture puis le worker (sentinelle + join borné), et
    vide le cache. Réentrant : un appel sans moteur démarré ne plante pas —
    utilisé en début de test pour repartir d'un état propre."""
    global _flux, _worker
    with _moteur_lock:
        if _flux is not None:
            _flux.arreter()
            _flux = None
        if _worker is not None:
            _queue.put(_SENTINELLE)
            _worker.join(timeout=2.0)
            _worker = None
    with _cache_lock:
        _cache.clear()
    return {'ok': True}
