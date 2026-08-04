# -*- coding: utf-8 -*-
"""Keyer vocal DYNAMIQUE : synthèse vocale hors-ligne (pyttsx3/SAPI5) de
messages contest avec indicatif/report insérés à la volée — l'équivalent
phonie des macros CW ({CALL}/{NR}, déjà évalués en direct et envoyés au
keyer de la radio en CW, voir copyMacro() dans logx_logbook.js).

Le keyer vocal existant (WAV pré-enregistrés, rejoués sur les haut-parleurs
du PC) ne fait ni insertion dynamique de l'indicatif ni émission radio. Ici :
  1. Le texte du message est développé : l'indicatif ({CALL}/{MYCALL}) est épelé
     en alphabet phonétique INTERNATIONAL (OACI, compris de tous), le report et
     les séries ({RST_SENT}/{RST_RCVD}/{NR}) sont dits EN TOUTES LETTRES dans la
     langue dérivée de l'indicatif du correspondant (« cinquante-neuf » pour une
     station F, « fifty-nine » sinon), et {TNX} clôt par « 73 » suivi d'un
     remerciement dans la langue du correspondant (merci / arigato / thanks…).
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

# Le « / » d'un indicatif se PRONONCE : « stroke » à la radio (le mot
# international), « barre » en français. Un indicatif peut en porter DEUX
# (préfixe ET suffixe : F/DL1UTY/P), d'où le découpage sur chaque « / » plutôt
# qu'un seul partition() — l'ancienne version fondait préfixe et suffixe et,
# comme elle filtrait sur isalnum(), faisait DISPARAÎTRE le « / » en silence.
_STROKE = {'en': 'stroke', 'fr': 'barre'}


def spell_callsign(call, lang='en'):
    """Indicatif épelé en alphabet OACI, « / » prononcé (« stroke »/« barre ») :
    'F4GLD/P'    -> 'Foxtrot Four Golf Lima Delta stroke portable'
    'F/DL1UTY/P' -> 'Foxtrot stroke Delta Lima One Uniform Tango Yankee stroke portable'
    'DL/ON4DRT'  -> 'Delta Lima stroke Oscar November Four Delta Romeo Tango'
    '' si vide."""
    call = str(call or '').upper().strip()
    if not call:
        return ''
    stroke = _STROKE.get(lang, 'stroke')
    segs = [s for s in call.split('/') if s]
    words = []
    for i, seg in enumerate(segs):
        if i:
            words.append(stroke)                       # chaque « / » est dit
            # Un suffixe usuel en fin d'indicatif est dit comme un mot
            # ('portable') plutôt qu'épelé ('Papa') — mais toujours APRÈS son
            # « stroke », comme on l'entend sur l'air (« stroke portable »).
            if i == len(segs) - 1 and seg in SUFFIX_WORDS:
                words.append(SUFFIX_WORDS[seg])
                continue
        words.extend(PHONETIC.get(c, c) for c in seg if c.isalnum())
    return ' '.join(words)


def spell_digits(s):
    """'59' -> 'Five Nine', '042' -> 'Zero Four Two' — chiffre par chiffre
    (et lettre par lettre si alphanumérique). Reste disponible, mais le report
    est désormais dit EN TOUTES LETTRES (voir spell_number)."""
    return ' '.join(PHONETIC.get(c, c) for c in str(s or '').strip().upper() if c.isalnum())


# ─── NOMBRES EN TOUTES LETTRES, SELON LA LANGUE ──────────────────────────────
# « 59 » se dit « cinquante-neuf » / « fifty-nine » (plus clair et naturel que
# l'épellation chiffre par chiffre), et la langue DÉRIVE de l'indicatif du
# correspondant (français pour une station F, anglais — langue internationale du
# trafic — sinon). Nombres cardinaux standard 0-9999 (métropole pour le français :
# soixante-dix / quatre-vingts / quatre-vingt-dix).
_EN_ONES = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
            'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen',
            'sixteen', 'seventeen', 'eighteen', 'nineteen']
_EN_TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy',
            'eighty', 'ninety']
_FR_ONES = ['zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit',
            'neuf', 'dix', 'onze', 'douze', 'treize', 'quatorze', 'quinze', 'seize',
            'dix-sept', 'dix-huit', 'dix-neuf']


def _en_below_100(n):
    if n < 20:
        return _EN_ONES[n]
    t, u = divmod(n, 10)
    return _EN_TENS[t] + ('-' + _EN_ONES[u] if u else '')


def _en_below_1000(n):
    if n < 100:
        return _en_below_100(n)
    h, r = divmod(n, 100)
    return _EN_ONES[h] + ' hundred' + (' ' + _en_below_100(r) if r else '')


def _fr_below_100(n):
    if n < 20:
        return _FR_ONES[n]
    t, u = divmod(n, 10)
    if t == 7:                                    # 70-79 : soixante + (dix..dix-neuf)
        return 'soixante' + (' et ' if u == 1 else '-') + _FR_ONES[10 + u]
    if t == 9:                                    # 90-99 : quatre-vingt + (dix..dix-neuf)
        return 'quatre-vingt-' + _FR_ONES[10 + u]
    if t == 8:                                    # 80 quatre-vingtS, 81-89 quatre-vingt-…
        return 'quatre-vingt' + ('-' + _FR_ONES[u] if u else 's')
    base = {2: 'vingt', 3: 'trente', 4: 'quarante', 5: 'cinquante', 6: 'soixante'}[t]
    if u == 0:
        return base
    if u == 1:
        return base + ' et un'                    # vingt et un … soixante et un
    return base + '-' + _FR_ONES[u]


def _fr_below_1000(n):
    if n < 100:
        return _fr_below_100(n)
    h, r = divmod(n, 100)
    if h == 1:
        s = 'cent'
    else:
        s = _FR_ONES[h] + ' cent' + ('s' if r == 0 else '')   # deux centS, mais deux cent un
    return s + (' ' + _fr_below_100(r) if r else '')


def number_to_words(n, lang='en'):
    """Entier 0-9999 -> mots. lang 'fr' ou 'en' (défaut). Au-delà de 9999,
    l'appelant retombe sur l'épellation chiffre par chiffre."""
    n = int(n)
    below = _fr_below_1000 if lang == 'fr' else _en_below_1000
    if n < 1000:
        return below(n)
    th, r = divmod(n, 1000)
    if lang == 'fr':
        s = 'mille' if th == 1 else below(th) + ' mille'
    else:
        s = below(th) + ' thousand'
    return s + (' ' + below(r) if r else '')


def spell_number(s, lang='en'):
    """Report/série EN TOUTES LETTRES : '59' -> 'cinquante-neuf'/'fifty-nine'.
    Les zéros de tête d'une série paddée sont dits ('001' -> 'zéro zéro un',
    '042' -> 'zéro quarante-deux'), convention concours. Une valeur non
    purement numérique (zone/classe alphanumérique) retombe sur l'épellation."""
    s = str(s or '').strip()
    if not s:
        return ''
    if not s.isdigit():
        return spell_digits(s)
    lead = len(s) - len(s.lstrip('0'))
    core = s.lstrip('0')
    zero = 'zéro' if lang == 'fr' else 'zero'
    parts = [zero] * lead
    if core:
        n = int(core)
        parts.append(number_to_words(n, lang) if n <= 9999 else spell_digits(core))
    return ' '.join(parts)


# ─── LANGUE DÉRIVÉE DE L'INDICATIF + REMERCIEMENT DE CLÔTURE ──────────────────
# Entités DXCC francophones (cty.dat) où le report se dit en français ; partout
# ailleurs, anglais (langue internationale du trafic).
_FRENCH_ENTITIES = ('france', 'corsica', 'guadeloupe', 'martinique', 'reunion',
                    'caledonia', 'polynesia', 'mayotte', 'wallis', 'miquelon',
                    'martin', 'barthelemy', 'kerguelen')

# Remerciement de clôture ({TNX}) dans la langue du correspondant. Jeu volontai-
# rement RESTREINT aux mots qu'une voix SAPI rend correctement (les exemples
# demandés : merci / arigato / thanks, plus les voisins européens courants).
_THANKS_BY_COUNTRY = (
    (_FRENCH_ENTITIES, 'merci'),
    (('japan',), 'arigato'),
    (('germany', 'austria', 'switzerland'), 'danke'),
    (('italy', 'sardinia'), 'grazie'),
    (('spain', 'balearic', 'canary'), 'gracias'),
    (('portugal', 'azores', 'madeira', 'brazil'), 'obrigado'),
    (('netherlands',), 'dank u'),
)
_ENGLISH_ENTITIES = ('united states', 'canada', 'england', 'scotland', 'wales',
                     'ireland', 'australia', 'new zealand', 'south africa')


def _country(call):
    try:
        import logx_dxcc as dxcc
        return ((dxcc.lookup(call) or {}).get('country') or '')
    except Exception:
        return ''


def lang_for_call(call):
    """'fr' si l'indicatif est une entité française, sinon 'en'. Gouverne la
    langue des NOMBRES dits en toutes lettres."""
    c = _country(call).lower()
    return 'fr' if any(k in c for k in _FRENCH_ENTITIES) else 'en'


def message_lang(ctx):
    ctx = ctx or {}
    return lang_for_call(ctx.get('call') or ctx.get('mycall') or '')


def thanks_word(call):
    """Mot de remerciement dans la langue du pays de l'indicatif — '' si aucun
    mot dédié (on ne dira alors que « 73 »)."""
    c = _country(call).lower()
    if not c:
        return ''
    for keys, word in _THANKS_BY_COUNTRY:
        if any(k in c for k in keys):
            return word
    return 'thanks' if any(k in c for k in _ENGLISH_ENTITIES) else ''


def closing_73(ctx):
    """{TNX} -> « soixante-treize merci » / « seventy-three arigato »… : 73 dans
    la langue des nombres + un remerciement dans la langue du correspondant."""
    ctx = ctx or {}
    seventythree = spell_number('73', message_lang(ctx))
    tnx = thanks_word(ctx.get('call') or '')
    return (seventythree + ' ' + tnx) if tnx else seventythree


# ─── MACROS VOCALES (équivalent phonie des macros CW F1-F8) ─────────────────
VOICE_MACROS_DEFAULT = [
    {'key': 'V1', 'label': 'CQ', 'text': 'CQ Contest, {MYCALL}'},
    {'key': 'V2', 'label': 'RÉPONSE', 'text': '{CALL}'},
    {'key': 'V3', 'label': 'REPORT', 'text': '{RST_SENT}, {MYCALL}'},
    {'key': 'V4', 'label': '73 + MERCI', 'text': '{TNX}, {MYCALL}'},
]


def expand_voice_text(template, ctx):
    """Développe les variables d'une macro vocale. ctx :
    {'call','mycall','rst_sent','rst_rcvd','nr'}.
      {CALL}/{MYCALL} -> alphabet phonétique INTERNATIONAL (compris de tous) ;
      {RST_SENT}/{RST_RCVD}/{NR} -> EN TOUTES LETTRES dans la langue dérivée de
        l'indicatif (F -> « cinquante-neuf », sinon « fifty-nine ») ;
      {TNX} -> « 73 » + remerciement dans la langue du correspondant ;
      {73} -> « soixante-treize »/« seventy-three »."""
    ctx = ctx or {}
    lang = message_lang(ctx)
    return (str(template or '')
            .replace('{CALL}', spell_callsign(ctx.get('call', ''), lang))
            .replace('{MYCALL}', spell_callsign(ctx.get('mycall', ''), lang))
            .replace('{RST_SENT}', spell_number(ctx.get('rst_sent', ''), lang))
            .replace('{RST_RCVD}', spell_number(ctx.get('rst_rcvd', ''), lang))
            .replace('{NR}', spell_number(ctx.get('nr', ''), lang))
            .replace('{TNX}', closing_73(ctx))
            .replace('{73}', spell_number('73', lang)))


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
def _voice_id_for_lang(engine, lang):
    """id d'une voix SAPI installée correspondant à la langue ('fr'/'en'), ou
    None. Rend « cinquante-neuf, merci » naturel avec une VRAIE voix française."""
    hints = {'fr': ('french', 'français', 'francais', 'fr-', 'fr_', 'fra'),
             'en': ('english', 'en-', 'en_', 'enu', 'eng')}.get(lang or '', ())
    if not hints:
        return None
    try:
        for v in engine.getProperty('voices'):
            hay = (str(v.id) + ' ' + str(v.name) + ' '
                   + ','.join(v.languages or [])).lower()
            if any(h in hay for h in hints):
                return v.id
    except Exception:
        pass
    return None


def synthesize_to_wav(text, voice_id='', rate=175, lang=''):
    """Génère un WAV temporaire via pyttsx3 (100% hors-ligne, SAPI5/Windows).
    Retourne le chemin du fichier, ou None si le moteur TTS est indisponible
    ou n'a produit aucun son exploitable. `lang` : préfère une voix de cette
    langue pour un rendu naturel ; le voice_id explicite (CONFIG) prime."""
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
            vid = voice_id or _voice_id_for_lang(engine, lang)
            if vid:
                engine.setProperty('voice', vid)
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


def send_voice_message(cfg, text, lang='', skip_ptt=False):
    """PTT ON -> synthèse + lecture -> PTT OFF, quel que soit le mode CAT
    actif. `lang` : préfère une voix SAPI de cette langue (voir expand_voice_text
    / message_lang). `skip_ptt` : n'engage jamais le PTT — réservé au bouton
    « Tester » de CONFIG (indicatif fictif), pour prévisualiser le périphérique/
    la voix choisis SANS exiger que le pilotage radio soit déjà configuré (voir
    emettre_wav). Ne lève jamais : {'ok': bool, 'error'?: str}."""
    settings = voicekeyer_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Keyer vocal désactivé (CONFIG)'}
    text = (text or '').strip()
    if not text:
        return {'ok': False, 'error': 'Message vide'}
    path = synthesize_to_wav(text, settings['voice_id'], settings['rate'], lang)
    if not path:
        return {'ok': False, 'error': 'Synthèse vocale indisponible (moteur TTS)'}

    # Le WAV de synthèse est temporaire : emettre_wav() le supprime lui-même
    # après émission (supprimer_apres), y compris si la lecture échoue.
    return emettre_wav(cfg, path, settings['device'],
                       supprimer_apres=True, extra={'text': text}, skip_ptt=skip_ptt)


def emettre_wav(cfg, path, device, supprimer_apres=False, extra=None, skip_ptt=False):
    """PTT ON → lecture du WAV → PTT OFF vérifié. Séquence commune à la voix de
    synthèse (callbot) et aux messages enregistrés par l'opérateur : c'est le
    relâchement du PTT qui doit être identique dans les deux cas, pas seulement
    la lecture.

    `skip_ptt=True` : ne touche jamais au PTT (ni ON ni OFF) — utilisé
    UNIQUEMENT par le test CONFIG (indicatif fictif « F8TEST »->
    /rig/voice avec skip_ptt) pour permettre de prévisualiser le
    périphérique audio/la voix choisis même sans pilotage radio configuré
    (retour F4GLD 04/08/2026 : le test échouait systématiquement avec
    « Pilotage radio désactivé » tant que CAT n'était pas réglé, alors que
    l'opérateur voulait juste vérifier le son). En émission réelle
    (send_voice_message() depuis le logbook, skip_ptt jamais positionné),
    le PTT reste obligatoire — sans lui la radio ne transmet pas, jouer le
    son quand même donnerait une fausse impression de message envoyé."""
    def _rm():
        if supprimer_apres:
            try:
                os.remove(path)
            except OSError:
                pass

    # Verrou : une seule émission vocale à la fois (voir _voice_lock).
    with _voice_lock:
        if not skip_ptt:
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
            if not skip_ptt:
                # Relâchement du PTT VÉRIFIÉ, avec une seconde tentative : un
                # échec silencieux laisserait la radio bloquée en émission
                # continue (risque matériel pour l'ampli/le transceiver).
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
