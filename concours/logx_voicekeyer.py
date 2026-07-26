# -*- coding: utf-8 -*-
"""Keyer vocal DYNAMIQUE : synthèse vocale hors-ligne (pyttsx3/SAPI5) de
messages contest avec indicatif/report insérés à la volée — l'équivalent
phonie des macros CW ({CALL}/{NR}, déjà évalués en direct et envoyés au
keyer de la radio en CW, voir copyMacro() dans logx_logbook.js).

Le keyer vocal existant (WAV pré-enregistrés, rejoués sur les haut-parleurs
du PC) ne fait ni insertion dynamique de l'indicatif ni émission radio. Ici :
  1. Le texte du message ({CALL}/{MYCALL}/{RST_SENT}/{RST_RCVD}/{NR}) est
     épelé phonétiquement (alphabet OACI) / chiffre par chiffre (convention
     radioamateur : « 59 » se dit « five nine », jamais « fifty-nine »).
  2. pyttsx3 (SAPI5 Windows, 100% hors-ligne, aucune clé/API réseau) le
     synthétise en WAV temporaire.
  3. Le PTT est activé via CAT (natif/TCI/rigctld — même mécanisme déjà
     utilisé pour le CW), le WAV est joué vers le PÉRIPHÉRIQUE AUDIO CHOISI
     en CONFIG (câble virtuel/interface dédiée vers l'entrée micro de la
     radio — JAMAIS les haut-parleurs de suivi de l'opérateur par défaut),
     puis le PTT est relâché.

Aucune fonction ici ne lève d'exception vers l'appelant HTTP : tout retourne
{'ok': bool, 'error'?: str}, comme le reste des modules radio du projet.
"""
import os
import tempfile
import threading
import wave

# Sérialise l'émission vocale : deux /rig/voice concurrents (double-clic macro,
# CQ relancé pendant sa lecture) jouaient leurs WAV en même temps et, surtout,
# le finally du premier terminé relâchait le PTT pendant que le second émettait.
_voice_lock = threading.Lock()

# ─── ÉPELLATION PHONÉTIQUE (alphabet OACI) ───────────────────────────────────
PHONETIC = {
    'A': 'Alpha', 'B': 'Bravo', 'C': 'Charlie', 'D': 'Delta', 'E': 'Echo',
    'F': 'Foxtrot', 'G': 'Golf', 'H': 'Hotel', 'I': 'India', 'J': 'Juliett',
    'K': 'Kilo', 'L': 'Lima', 'M': 'Mike', 'N': 'November', 'O': 'Oscar',
    'P': 'Papa', 'Q': 'Quebec', 'R': 'Romeo', 'S': 'Sierra', 'T': 'Tango',
    'U': 'Uniform', 'V': 'Victor', 'W': 'Whiskey', 'X': 'X-ray', 'Y': 'Yankee',
    'Z': 'Zulu',
    '0': 'Zero', '1': 'One', '2': 'Two', '3': 'Three', '4': 'Four',
    '5': 'Five', '6': 'Six', '7': 'Seven', '8': 'Eight', '9': 'Nine',
}
# Suffixes /P /M /MM /AM /QRP : dits comme un mot usuel plutôt qu'épelés
# lettre par lettre (convention radioamateur en phonie).
SUFFIX_WORDS = {
    'P': 'portable', 'M': 'mobile', 'MM': 'maritime mobile',
    'AM': 'aeronautical mobile', 'QRP': 'Q R P',
}


def spell_callsign(call):
    """'F4GLD/P' -> 'Foxtrot Four Golf Lima Delta portable'. '' si vide."""
    call = str(call or '').upper().strip()
    if not call:
        return ''
    base, _, suffix = call.partition('/')
    words = [PHONETIC.get(c, c) for c in base if c.isalnum()]
    if suffix:
        words.append(SUFFIX_WORDS.get(suffix)
                      or ' '.join(PHONETIC.get(c, c) for c in suffix if c.isalnum()))
    return ' '.join(words)


def spell_digits(s):
    """'59' -> 'Five Nine', '042' -> 'Zero Four Two' — chiffre par chiffre
    (et lettre par lettre si alphanumérique), convention radioamateur :
    évite l'ambiguïté à l'oreille d'un nombre dit en entier."""
    return ' '.join(PHONETIC.get(c, c) for c in str(s or '').strip().upper() if c.isalnum())


# ─── MACROS VOCALES (équivalent phonie des macros CW F1-F8) ─────────────────
VOICE_MACROS_DEFAULT = [
    {'key': 'V1', 'label': 'CQ', 'text': 'CQ Contest, {MYCALL}'},
    {'key': 'V2', 'label': 'RÉPONSE', 'text': '{CALL}'},
    {'key': 'V3', 'label': 'REPORT', 'text': '{RST_SENT}, {MYCALL}'},
    {'key': 'V4', 'label': 'MERCI', 'text': 'Thank you, {MYCALL}'},
]


def expand_voice_text(template, ctx):
    """{CALL}/{MYCALL} -> épelés phonétiquement ; {RST_SENT}/{RST_RCVD}/{NR}
    -> chiffres séparés. ctx : {'call','mycall','rst_sent','rst_rcvd','nr'}."""
    ctx = ctx or {}
    return (str(template or '')
            .replace('{CALL}', spell_callsign(ctx.get('call', '')))
            .replace('{MYCALL}', spell_callsign(ctx.get('mycall', '')))
            .replace('{RST_SENT}', spell_digits(ctx.get('rst_sent', '')))
            .replace('{RST_RCVD}', spell_digits(ctx.get('rst_rcvd', '')))
            .replace('{NR}', spell_digits(ctx.get('nr', ''))))


# ─── RÉGLAGES ─────────────────────────────────────────────────────────────────
def voicekeyer_settings(cfg):
    cfg = cfg or {}
    try:
        rate = int(cfg.get('voicekeyer_rate') or 175)
    except (TypeError, ValueError):
        rate = 175
    return {
        'enabled': bool(cfg.get('voicekeyer_enabled')),
        'device': cfg.get('voicekeyer_device', ''),
        'voice_id': cfg.get('voicekeyer_voice_id', ''),
        'rate': rate,
    }


def list_output_devices():
    """[{index, name}] périphériques de sortie audio disponibles (pour le
    select CONFIG) — liste vide si sounddevice/PortAudio indisponible,
    jamais d'exception."""
    try:
        import sounddevice as sd
        out = []
        for i, d in enumerate(sd.query_devices()):
            if d.get('max_output_channels', 0) > 0:
                out.append({'index': i, 'name': d.get('name') or f'Périphérique {i}'})
        return out
    except Exception:
        return []


def list_tts_voices():
    """[{id, name, lang}] voix SAPI5 installées (Windows) — liste vide si
    pyttsx3 indisponible, jamais d'exception."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        try:
            out = [{'id': v.id, 'name': v.name, 'lang': ','.join(v.languages or [])}
                   for v in engine.getProperty('voices')]
        finally:
            engine.stop()
        return out
    except Exception:
        return []


# ─── SYNTHÈSE + LECTURE ───────────────────────────────────────────────────────
def synthesize_to_wav(text, voice_id='', rate=175):
    """Génère un WAV temporaire via pyttsx3 (100% hors-ligne, SAPI5/Windows).
    Retourne le chemin du fichier, ou None si le moteur TTS est indisponible
    ou n'a produit aucun son exploitable."""
    text = (text or '').strip()
    if not text:
        return None
    try:
        import pyttsx3
    except Exception:
        return None
    fd, path = tempfile.mkstemp(suffix='.wav', prefix='rc_voice_')
    os.close(fd)
    try:
        engine = pyttsx3.init()
        try:
            if voice_id:
                engine.setProperty('voice', voice_id)
            engine.setProperty('rate', rate)
            engine.save_to_file(text, path)
            engine.runAndWait()
        finally:
            engine.stop()
        if os.path.getsize(path) < 100:      # WAV vide = échec silencieux SAPI5
            os.remove(path)
            return None
        return path
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        return None


def play_wav(path, device_index=None):
    """Joue un WAV vers le périphérique choisi (bloquant jusqu'à la fin —
    messages courts, quelques secondes). N'utilise PAS numpy (RawOutputStream
    + octets bruts) pour rester une dépendance légère."""
    import sounddevice as sd
    with wave.open(path, 'rb') as wf:
        dtype = {1: 'int8', 2: 'int16', 4: 'int32'}.get(wf.getsampwidth(), 'int16')
        stream = sd.RawOutputStream(
            samplerate=wf.getframerate(), channels=wf.getnchannels(), dtype=dtype,
            device=int(device_index) if device_index not in (None, '') else None)
        stream.start()
        try:
            chunk = wf.readframes(4096)
            while chunk:
                stream.write(chunk)
                chunk = wf.readframes(4096)
        finally:
            stream.stop()
            stream.close()


# ─── PTT (dispatch selon le mode CAT actif, même mécanisme que le CW) ────────
def _set_ptt(cfg, on):
    import logx_cat as cat
    cat_settings = cat.cat_settings(cfg)
    if cat_settings['enabled'] and cat_settings['mode'] == 'native':
        return cat.set_ptt(cfg, on)
    if cat_settings['enabled'] and cat_settings['mode'] == 'tci':
        import logx_tci as tci
        return tci.set_ptt(cfg, on)
    if cat_settings['enabled'] and cat_settings['mode'] == 'flrig':
        import logx_flrig as flrig
        settings = flrig.flrig_settings(cfg)
        return flrig.set_ptt(settings['host'], settings['port'], on)
    import logx_rig as rig
    rig_settings = rig.rig_settings(cfg)
    if rig_settings['enabled']:
        return rig.set_ptt(rig_settings['host'], rig_settings['port'], on)
    return {'ok': False, 'error': 'Pilotage radio désactivé (CONFIG)'}


def send_voice_message(cfg, text):
    """PTT ON -> synthèse + lecture -> PTT OFF, quel que soit le mode CAT
    actif. Ne lève jamais : {'ok': bool, 'error'?: str}."""
    settings = voicekeyer_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Keyer vocal désactivé (CONFIG)'}
    text = (text or '').strip()
    if not text:
        return {'ok': False, 'error': 'Message vide'}
    path = synthesize_to_wav(text, settings['voice_id'], settings['rate'])
    if not path:
        return {'ok': False, 'error': 'Synthèse vocale indisponible (moteur TTS)'}

    # Le WAV de synthèse est temporaire : emettre_wav() le supprime lui-même
    # après émission (supprimer_apres), y compris si la lecture échoue.
    return emettre_wav(cfg, path, settings['device'],
                       supprimer_apres=True, extra={'text': text})


def emettre_wav(cfg, path, device, supprimer_apres=False, extra=None):
    """PTT ON → lecture du WAV → PTT OFF vérifié. Séquence commune à la voix de
    synthèse (callbot) et aux messages enregistrés par l'opérateur : c'est le
    relâchement du PTT qui doit être identique dans les deux cas, pas seulement
    la lecture."""
    def _rm():
        if supprimer_apres:
            try:
                os.remove(path)
            except OSError:
                pass

    # Verrou : une seule émission vocale à la fois (voir _voice_lock).
    with _voice_lock:
        ptt_on = _set_ptt(cfg, True)
        if not ptt_on.get('ok'):
            _rm()
            return {'ok': False, 'error': f"PTT refusé : {ptt_on.get('error', '?')}"}
        result = {'ok': True}
        result.update(extra or {})
        try:
            play_wav(path, device)
        except Exception as e:
            result = {'ok': False, 'error': f'Lecture audio impossible : {e}'}
        finally:
            # Relâchement du PTT VÉRIFIÉ, avec une seconde tentative : un échec
            # silencieux laisserait la radio bloquée en émission continue
            # (risque matériel pour l'ampli/le transceiver).
            off = _set_ptt(cfg, False)
            if not off.get('ok'):
                off = _set_ptt(cfg, False)
            if not off.get('ok'):
                result['ok'] = False
                result['ptt_release_failed'] = True
                result['error'] = ("⚠ ÉCHEC DU RELÂCHEMENT PTT — la radio peut "
                                   "rester en émission ! " + str(off.get('error', '?')))
            _rm()
        return result


# ─── MESSAGES ENREGISTRÉS PAR L'OPÉRATEUR (DVK) ─────────────────────────────
# La voix de synthèse convient pour un indicatif dit machinalement, pas pour un
# CQ : en phonie, un concours de 24 h détruit la voix, et le DVK sert justement
# à rejouer SA PROPRE voix, enregistrée une fois, à la 900e répétition.
#
# Les messages vivent CÔTÉ SERVEUR et non dans le navigateur : ils étaient
# stockés en localStorage, donc perdus dès qu'on ouvrait le log depuis un autre
# poste — précisément ce que le multi-poste est censé éviter. Et surtout, ils
# étaient joués par `new Audio().play()`, c'est-à-dire vers la sortie par défaut
# du navigateur (les enceintes) et sans PTT : inaudibles pour le correspondant.
EMPLACEMENTS = ('V1', 'V2', 'V3', 'V4')
_DOSSIER = 'voice_messages'
# 10 Mo : très au-delà d'un message de quelques secondes en PCM 16 bits, assez
# bas pour qu'un envoi aberrant ne remplisse pas le disque d'une expédition.
TAILLE_MAX = 10 * 1024 * 1024


def _dossier():
    os.makedirs(_DOSSIER, exist_ok=True)
    return _DOSSIER


def chemin_emplacement(cle):
    """Chemin du WAV d'un emplacement, ou None si la clé n'est pas reconnue.

    La clé vient du réseau : elle est comparée à une liste FERMÉE plutôt que
    nettoyée. Un nom construit à partir d'une chaîne reçue (même « assainie »)
    finit tôt ou tard par écrire hors du dossier prévu."""
    if cle not in EMPLACEMENTS:
        return None
    return os.path.join(_dossier(), '%s.wav' % cle)


def enregistrer_message(cle, donnees_wav):
    """Écrit le WAV d'un emplacement. Refuse ce qui n'est pas un WAV lisible :
    un fichier illisible ne se découvrirait qu'au moment de le passer sur
    l'air, c'est-à-dire au pire moment."""
    chemin = chemin_emplacement(cle)
    if chemin is None:
        return {'ok': False, 'error': 'Emplacement inconnu : %s' % cle}
    if not donnees_wav:
        return {'ok': False, 'error': 'Message vide'}
    if len(donnees_wav) > TAILLE_MAX:
        return {'ok': False, 'error': 'Message trop long (%d Mo max)'
                                      % (TAILLE_MAX // (1024 * 1024))}
    tmp = chemin + '.tmp'
    try:
        with open(tmp, 'wb') as f:
            f.write(donnees_wav)
        with wave.open(tmp, 'rb') as wf:          # contrôle de lisibilité
            duree = wf.getnframes() / float(wf.getframerate() or 1)
        os.replace(tmp, chemin)                    # publication atomique
        return {'ok': True, 'slot': cle, 'seconds': round(duree, 2)}
    except Exception as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return {'ok': False, 'error': 'WAV illisible : %s' % e}


def supprimer_message(cle):
    chemin = chemin_emplacement(cle)
    if chemin is None:
        return {'ok': False, 'error': 'Emplacement inconnu'}
    try:
        os.remove(chemin)
    except OSError:
        pass
    return {'ok': True}


def messages_disponibles():
    """{clé: durée en secondes} pour les emplacements réellement enregistrés."""
    out = {}
    for cle in EMPLACEMENTS:
        chemin = chemin_emplacement(cle)
        if not chemin or not os.path.exists(chemin):
            continue
        try:
            with wave.open(chemin, 'rb') as wf:
                out[cle] = round(wf.getnframes() / float(wf.getframerate() or 1), 2)
        except Exception:
            out[cle] = 0
    return out


def envoyer_message(cfg, cle):
    """Passe sur l'air le message enregistré à cet emplacement."""
    settings = voicekeyer_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Keyer vocal désactivé (CONFIG)'}
    chemin = chemin_emplacement(cle)
    if chemin is None:
        return {'ok': False, 'error': 'Emplacement inconnu'}
    if not os.path.exists(chemin):
        return {'ok': False, 'error': 'Aucun message enregistré sur %s' % cle}
    return emettre_wav(cfg, chemin, settings['device'], extra={'slot': cle})
