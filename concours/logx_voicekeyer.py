# -*- coding: utf-8 -*-
"""Keyer vocal DYNAMIQUE : synthèse vocale hors-ligne (pyttsx3/SAPI5) de
messages contest avec indicatif/report insérés à la volée — l'équivalent
phonie des macros CW ({CALL}/{NR}, déjà évalués en direct et envoyés au
keyer de la radio en CW, voir copyMacro() dans logx_logbook.js).

Le keyer vocal existant (WAV pré-enregistrés, rejoués sur les haut-parleurs
du PC) ne fait ni insertion dynamique de l'indicatif ni émission radio. Ici :
  1. Le texte du message est développé : l'indicatif ({CALL}/{MYCALL}) est
     épelé en alphabet phonétique INTERNATIONAL (OACI — Alpha/Bravo/…/Zero/
     One/…/Nine, compris de tous, JAMAIS traduit, voir spell_callsign), le
     report et les séries ({RST_SENT}/{RST_RCVD}/{NR}) sont dits EN TOUTES
     LETTRES TOUJOURS EN ANGLAIS (« fifty-nine », jamais « cinquante-neuf »
     — retour F4GLD 04/08/2026 : l'échange doit rester simple et sans
     ambiguïté, quelle que soit la langue du correspondant), {DE} adapte le
     connecteur (« de »/« von »/« da »/« van »/« kara »/« from ») et {TNX}
     clôt par « 73 » suivi d'un remerciement DANS LA LANGUE du correspondant
     (merci/arigato/danke/grazie/gracias/obrigado/dank u/thanks — cette
     clôture de politesse n'est pas une donnée d'échange, elle reste
     localisée ; fr/de/it/es/pt/nl/ja ont un système de nombres complet
     dédié pour ce « 73 » de clôture, voir lang_for_call/number_to_words).

     ATTENTION PRONONCIATION (retour F4GLD 04/08/2026, ex. « nine » se
     prononce /naɪn/) : ceci reste du TEXTE BRUT envoyé à un SEUL moteur
     TTS pour tout le message — pas de balisage par mot ("SSML") indiquant
     à la voix de changer de langue au milieu de la phrase. Si le moteur
     choisit une voix allemande/italienne/etc. (pour le « 73 » de clôture
     par ex.), les mots ANGLAIS internationaux mélangés dans la MÊME phrase
     (alphabet OACI, chiffres d'échange, « stroke ») risquent d'être lus
     avec les règles de prononciation de CETTE langue, pas l'anglais
     correct — limitation connue de pyttsx3/SAPI5 et Piper en usage simple
     (texte -> audio), pas quelque chose qu'un correctif ici peut garantir
     sans passer par du SSML par mot (hors périmètre actuel).
  2. Synthèse en WAV temporaire, avec 3 moteurs possibles par ordre de
     préférence (chacun optionnel, retombe silencieusement sur le suivant) :
       a. Voix IA cloud (ElevenLabs) si activée en CONFIG — la plus naturelle,
          mais nécessite un abonnement ET une connexion réseau (voir
          synthesize_to_wav_ai) ;
       b. Piper (rhasspy/piper) si activé — moteur NEURONAL 100% hors-ligne,
          nettement plus naturel que SAPI5 et SANS abonnement (retour F4GLD
          04/08/2026 : ElevenLabs jugé impayable, Piper choisi comme
          alternative) — installé et invoqué en sous-processus, un modèle de
          voix .onnx téléchargé une fois (voir synthesize_to_wav_piper) ;
       c. pyttsx3 (SAPI5 Windows) en dernier recours — toujours disponible
          sans rien installer, garantit que le keyer vocal fonctionne même si
          aucun des deux moteurs ci-dessus n'est configuré/joignable.
     Un concours de 24-48h ne doit jamais dépendre d'un service externe pour
     dire un indicatif — chaque moteur au-dessus de SAPI5 est un essai,
     jamais un point de panne.
  3. Le PTT est activé via CAT (natif/TCI/rigctld — même mécanisme déjà
     utilisé pour le CW), le WAV est joué vers le PÉRIPHÉRIQUE AUDIO CHOISI
     en CONFIG (câble virtuel/interface dédiée vers l'entrée micro de la
     radio — JAMAIS les haut-parleurs de suivi de l'opérateur par défaut),
     puis le PTT est relâché.

Aucune fonction ici ne lève d'exception vers l'appelant HTTP : tout retourne
{'ok': bool, 'error'?: str}, comme le reste des modules radio du projet.
"""
import array
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import threading
import urllib.parse
import wave

# Sérialise l'émission vocale : deux /rig/voice concurrents (double-clic macro,
# CQ relancé pendant sa lecture) jouaient leurs WAV en même temps et, surtout,
# le finally du premier terminé relâchait le PTT pendant que le second émettait.
_voice_lock = threading.Lock()

_ai_cache_lock = threading.Lock()  # protège le check-then-write du cache IA (voir synthesize_to_wav_ai)

_dvk_lock = threading.Lock()

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

# Le « / » d'un indicatif se PRONONCE « stroke » à la radio — TOUJOURS, y
# compris entre francophones : c'est le mot international, jamais traduit sur
# l'air (comme l'alphabet OACI lui-même, jamais francisé). Une version
# antérieure le traduisait en « barre » dès que la langue du message était le
# français (dérivée du pays du correspondant) — ce qui faisait dire « barre »
# pour un banal MYCALL=F4GLD/P en test, jamais entendu ainsi en vrai sur l'air
# (retour F4GLD 04/08/2026 : « il devrait dire stroke »). Un indicatif peut
# porter DEUX « / » (préfixe ET suffixe : F/DL1UTY/P), d'où le découpage sur
# chaque « / » plutôt qu'un seul partition() — l'ancienne version fondait
# préfixe et suffixe et, comme elle filtrait sur isalnum(), faisait
# DISPARAÎTRE le « / » en silence.
STROKE_WORD = 'stroke'


def spell_callsign(call):
    """Indicatif épelé en alphabet OACI, « / » toujours prononcé « stroke » :
    'F4GLD/P'    -> 'Foxtrot Four Golf Lima Delta stroke portable'
    'F/DL1UTY/P' -> 'Foxtrot stroke Delta Lima One Uniform Tango Yankee stroke portable'
    'DL/ON4DRT'  -> 'Delta Lima stroke Oscar November Four Delta Romeo Tango'
    '' si vide."""
    call = str(call or '').upper().strip()
    if not call:
        return ''
    segs = [s for s in call.split('/') if s]
    words = []
    for i, seg in enumerate(segs):
        if i:
            words.append(STROKE_WORD)                  # chaque « / » est dit
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


# Allemand — implémenté en entier (demande explicite F4GLD 04/08/2026 : un
# indicatif DL doit s'entendre en allemand, pas juste son mot de remerciement
# de clôture comme avant). Unité-puis-dizaine inversées ("einundzwanzig" =
# un-et-vingt) et mots composés SANS espace, comme à l'écrit/l'oral allemand.
_DE_ONES = ['null', 'eins', 'zwei', 'drei', 'vier', 'fünf', 'sechs', 'sieben',
            'acht', 'neun', 'zehn', 'elf', 'zwölf', 'dreizehn', 'vierzehn',
            'fünfzehn', 'sechzehn', 'siebzehn', 'achtzehn', 'neunzehn']
_DE_TENS = ['', '', 'zwanzig', 'dreißig', 'vierzig', 'fünfzig', 'sechzig',
            'siebzig', 'achtzig', 'neunzig']


def _de_below_100(n):
    if n < 20:
        return _DE_ONES[n]
    t, u = divmod(n, 10)
    if u == 0:
        return _DE_TENS[t]
    return ('ein' if u == 1 else _DE_ONES[u]) + 'und' + _DE_TENS[t]


def _de_below_1000(n):
    if n < 100:
        return _de_below_100(n)
    h, r = divmod(n, 100)
    return ('ein' if h == 1 else _DE_ONES[h]) + 'hundert' + (_de_below_100(r) if r else '')


# Italien — mots composés SANS espace comme l'allemand ; élision de la
# voyelle finale de la dizaine devant 1/8 (ventuno, pas venti-uno ; ventotto,
# pas venti-otto) et accent sur les combinaisons en 3 (ventitré).
_IT_ONES = ['zero', 'uno', 'due', 'tre', 'quattro', 'cinque', 'sei', 'sette',
            'otto', 'nove', 'dieci', 'undici', 'dodici', 'tredici', 'quattordici',
            'quindici', 'sedici', 'diciassette', 'diciotto', 'diciannove']
_IT_TENS = ['', '', 'venti', 'trenta', 'quaranta', 'cinquanta', 'sessanta',
            'settanta', 'ottanta', 'novanta']


def _it_below_100(n):
    if n < 20:
        return _IT_ONES[n]
    t, u = divmod(n, 10)
    tens = _IT_TENS[t]
    if u == 0:
        return tens
    if u in (1, 8):
        tens = tens[:-1]                              # élision : vent(i) + uno/otto
    return tens + ('tré' if u == 3 else _IT_ONES[u])  # accent : ventitré


def _it_below_1000(n):
    if n < 100:
        return _it_below_100(n)
    h, r = divmod(n, 100)
    prefix = 'cento' if h == 1 else _IT_ONES[h] + 'cento'
    return prefix + (_it_below_100(r) if r else '')


# Espagnol — CONTRAIREMENT à l'allemand/italien, les dizaines à partir de 30
# gardent un « y » et des espaces ("cincuenta y nueve") ; seuls 16-29 sont
# des mots fusionnés (dieciséis, veintiuno). « cien » (100 pile) devient
# « ciento » dès qu'un reste suit (ciento uno). « quinientos »/« novecientos »
# sont irréguliers (pas cinco-/nueve-cientos).
_ES_ONES = ['cero', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete',
            'ocho', 'nueve', 'diez', 'once', 'doce', 'trece', 'catorce', 'quince',
            'dieciséis', 'diecisiete', 'dieciocho', 'diecinueve']
_ES_TWENTIES = ['veinte', 'veintiuno', 'veintidós', 'veintitrés', 'veinticuatro',
                'veinticinco', 'veintiséis', 'veintisiete', 'veintiocho', 'veintinueve']
_ES_TENS = ['', '', 'veinte', 'treinta', 'cuarenta', 'cincuenta', 'sesenta',
            'setenta', 'ochenta', 'noventa']
_ES_HUNDREDS = ['', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos',
                'quinientos', 'seiscientos', 'setecientos', 'ochocientos', 'novecientos']


def _es_below_100(n):
    if n < 20:
        return _ES_ONES[n]
    if n < 30:
        return _ES_TWENTIES[n - 20]
    t, u = divmod(n, 10)
    return _ES_TENS[t] if u == 0 else _ES_TENS[t] + ' y ' + _ES_ONES[u]


def _es_below_1000(n):
    if n < 100:
        return _es_below_100(n)
    h, r = divmod(n, 100)
    if h == 1 and r == 0:
        return 'cien'
    return _ES_HUNDREDS[h] if r == 0 else _ES_HUNDREDS[h] + ' ' + _es_below_100(r)


# Portugais — même famille que l'espagnol (« e » au lieu de « y »), mais
# « cem » (100 pile) devient « cento » dès qu'un reste < 100 suit ; le
# séparateur avec les milliers est « e » seulement si le reste est < 100
# (mil cento e um, mais mil duzentos SANS « e »). Orthographe brésilienne
# retenue pour 16/17/19 (dezesseis/dezessete/dezenove) — un seul dialecte
# encodé, le regroupement pays ne distingue pas Portugal/Brésil.
_PT_ONES = ['zero', 'um', 'dois', 'três', 'quatro', 'cinco', 'seis', 'sete',
            'oito', 'nove', 'dez', 'onze', 'doze', 'treze', 'catorze', 'quinze',
            'dezesseis', 'dezessete', 'dezoito', 'dezenove']
_PT_TENS = ['', '', 'vinte', 'trinta', 'quarenta', 'cinquenta', 'sessenta',
            'setenta', 'oitenta', 'noventa']
_PT_HUNDREDS = ['', 'cento', 'duzentos', 'trezentos', 'quatrocentos',
                'quinhentos', 'seiscentos', 'setecentos', 'oitocentos', 'novecentos']


def _pt_below_100(n):
    if n < 20:
        return _PT_ONES[n]
    t, u = divmod(n, 10)
    return _PT_TENS[t] if u == 0 else _PT_TENS[t] + ' e ' + _PT_ONES[u]


def _pt_below_1000(n):
    if n < 100:
        return _pt_below_100(n)
    h, r = divmod(n, 100)
    if h == 1 and r == 0:
        return 'cem'
    return _PT_HUNDREDS[h] if r == 0 else _PT_HUNDREDS[h] + ' e ' + _pt_below_100(r)


# Néerlandais — même schéma que l'allemand (unité-puis-dizaine inversées,
# mots composés SANS espace) : « negenenvijftig » = neuf-et-cinquante = 59.
_NL_ONES = ['nul', 'een', 'twee', 'drie', 'vier', 'vijf', 'zes', 'zeven',
            'acht', 'negen', 'tien', 'elf', 'twaalf', 'dertien', 'veertien',
            'vijftien', 'zestien', 'zeventien', 'achttien', 'negentien']
_NL_TENS = ['', '', 'twintig', 'dertig', 'veertig', 'vijftig', 'zestig',
            'zeventig', 'tachtig', 'negentig']


def _nl_below_100(n):
    if n < 20:
        return _NL_ONES[n]
    t, u = divmod(n, 10)
    if u == 0:
        return _NL_TENS[t]
    unit = 'een' if u == 1 else _NL_ONES[u]
    # Tréma orthographique néerlandais : "tweeën-"/"drieën-", jamais "tweeen-"
    # ("twee"/"drie" se terminent par une voyelle — sans le tréma sur le e du
    # lien "en", trois voyelles se suivraient). Inutile pour les autres
    # chiffres (vier/vijf/zes/zeven/acht/negen/een se terminent par une
    # consonne, "en" simple suffit).
    link = 'ën' if u in (2, 3) else 'en'
    return unit + link + _NL_TENS[t]


def _nl_below_1000(n):
    if n < 100:
        return _nl_below_100(n)
    h, r = divmod(n, 100)
    prefix = 'honderd' if h == 1 else _NL_ONES[h] + 'honderd'
    return prefix + (_nl_below_100(r) if r else '')


# Japonais (rōmaji — écriture latine, pas de kanji/kana : la synthèse vocale
# lit du texte, pas des idéogrammes). Système multiplicatif base 10 avec
# changements euphoniques IRRÉGULIERS aux centaines/milliers (san+hyaku ->
# "sanbyaku", pas "sanhyaku" ; roku+hyaku -> "roppyaku" ; hachi+hyaku ->
# "happyaku" ; san+sen -> "sanzen" ; hachi+sen -> "hassen") — encodés en
# table plutôt que dérivés, plus sûr qu'une règle générale à exceptions.
# ATTENTION PRONONCIATION (retour F4GLD 04/08/2026) : ceci ne sonnera
# juste que si une VRAIE voix japonaise est installée — voir la note dans
# le docstring du module et _voice_id_for_lang().
_JA_ONES = ['zero', 'ichi', 'ni', 'san', 'yon', 'go', 'roku', 'nana', 'hachi', 'kyuu']
_JA_TENS_PREFIX = {2: 'ni', 3: 'san', 4: 'yon', 5: 'go', 6: 'roku', 7: 'nana',
                   8: 'hachi', 9: 'kyuu'}
_JA_HUNDREDS_WORD = {1: 'hyaku', 2: 'nihyaku', 3: 'sanbyaku', 4: 'yonhyaku',
                     5: 'gohyaku', 6: 'roppyaku', 7: 'nanahyaku', 8: 'happyaku',
                     9: 'kyuuhyaku'}
_JA_THOUSANDS_WORD = {1: 'sen', 2: 'nisen', 3: 'sanzen', 4: 'yonsen', 5: 'gosen',
                      6: 'rokusen', 7: 'nanasen', 8: 'hassen', 9: 'kyuusen'}


def _ja_below_100(n):
    if n < 10:
        return _JA_ONES[n]
    t, u = divmod(n, 10)
    tens = 'juu' if t == 1 else _JA_TENS_PREFIX[t] + 'juu'
    return tens + (_JA_ONES[u] if u else '')


def _ja_below_1000(n):
    if n < 100:
        return _ja_below_100(n)
    h, r = divmod(n, 100)
    return _JA_HUNDREDS_WORD[h] + (_ja_below_100(r) if r else '')


# Une langue sans système de nombres écrit ici retombe sur l'anglais plutôt
# que de planter : {TNX}/thanks_word() dit déjà le bon mot dans TOUTES les
# langues de _LANG_AND_THANKS_BY_COUNTRY, seuls les NOMBRES d'une langue pas
# encore ajoutée à ce dict retomberaient sur l'anglais (aucune pour l'instant
# — fr/de/it/es/pt/nl/ja sont toutes couvertes, 04/08/2026).
_BELOW_1000_BY_LANG = {'fr': _fr_below_1000, 'de': _de_below_1000,
                       'it': _it_below_1000, 'es': _es_below_1000,
                       'pt': _pt_below_1000, 'nl': _nl_below_1000,
                       'ja': _ja_below_1000}

# Mot des milliers (ex. « mille »/« tausend »/« mila »…) par langue, en
# fonction du multiplicateur (1-9 — le contrat de number_to_words() s'arrête
# à 9999). Le français/anglais/espagnol/portugais gardent un espace avant le
# reste ; l'allemand/italien/néerlandais/japonais agglutinent SANS espace,
# comme à l'écrit dans ces langues — _NO_SPACE_JOIN_LANGS encode lesquelles.
_THOUSAND_WORD_BY_LANG = {
    'fr': lambda th, below: 'mille' if th == 1 else below(th) + ' mille',
    'de': lambda th, below: ('ein' if th == 1 else below(th)) + 'tausend',
    'it': lambda th, below: 'mille' if th == 1 else below(th) + 'mila',
    'es': lambda th, below: 'mil' if th == 1 else below(th) + ' mil',
    'pt': lambda th, below: 'mil' if th == 1 else below(th) + ' mil',
    'nl': lambda th, below: 'duizend' if th == 1 else below(th) + 'duizend',
    'ja': lambda th, below: _JA_THOUSANDS_WORD[th],
}
_NO_SPACE_JOIN_LANGS = ('de', 'it', 'nl', 'ja')


def number_to_words(n, lang='en'):
    """Entier 0-9999 -> mots. lang : fr/de/it/es/pt/nl/ja ont un système
    complet, tout le reste (dont 'en') retombe sur l'anglais. Au-delà de
    9999, l'appelant retombe sur l'épellation chiffre par chiffre."""
    n = int(n)
    below = _BELOW_1000_BY_LANG.get(lang, _en_below_1000)
    if n < 1000:
        return below(n)
    th, r = divmod(n, 1000)
    thousand_word = _THOUSAND_WORD_BY_LANG.get(lang)
    s = thousand_word(th, below) if thousand_word else below(th) + ' thousand'
    if not r:
        return s
    # Portugais : « e » seulement si le reste est < 100 (mil cento e um, mais
    # mil duzentos SANS « e ») — le seul cas où le séparateur dépend du reste,
    # pas seulement de la langue.
    if lang == 'pt':
        return s + ((' e ' if r < 100 else ' ') + below(r))
    sep = '' if lang in _NO_SPACE_JOIN_LANGS else ' '
    return s + sep + below(r)


_ZERO_BY_LANG = {'fr': 'zéro', 'de': 'null', 'it': 'zero', 'es': 'cero',
                 'pt': 'zero', 'nl': 'nul', 'ja': 'zero'}


def spell_number(s, lang='en'):
    """Report/série EN TOUTES LETTRES : '59' -> 'cinquante-neuf'/'neunundfünfzig'
    /'fifty-nine'. Les zéros de tête d'une série paddée sont dits ('001' ->
    'zéro zéro un', '042' -> 'zéro quarante-deux'), convention concours. Une
    valeur non purement numérique (zone/classe alphanumérique) retombe sur
    l'épellation."""
    s = str(s or '').strip()
    if not s:
        return ''
    if not s.isdigit():
        return spell_digits(s)
    lead = len(s) - len(s.lstrip('0'))
    core = s.lstrip('0')
    zero = _ZERO_BY_LANG.get(lang, 'zero')
    parts = [zero] * lead
    if core:
        n = int(core)
        parts.append(number_to_words(n, lang) if n <= 9999 else spell_digits(core))
    return ' '.join(parts)


# ─── LANGUE DÉRIVÉE DE L'INDICATIF + REMERCIEMENT DE CLÔTURE ──────────────────
# Entités DXCC francophones (cty.dat) où le report se dit en français ; partout
# ailleurs, anglais (langue internationale du trafic) PAR DÉFAUT — sauf les
# groupes ci-dessous, chacun associé à son code langue ET son mot de
# remerciement ({TNX}) en un seul endroit (avant, ces deux informations
# vivaient dans deux tables séparées mais alignées à la main — un oubli d'un
# côté aurait pu les faire diverger en silence).
_FRENCH_ENTITIES = ('france', 'corsica', 'guadeloupe', 'martinique', 'reunion',
                    'caledonia', 'polynesia', 'mayotte', 'wallis', 'miquelon',
                    'martin', 'barthelemy', 'kerguelen')

# (mots-clés pays en minuscules, code langue, mot de remerciement {TNX}).
# Le mot de remerciement reste volontairement RESTREINT aux mots qu'une voix
# SAPI rend correctement. Le système de NOMBRES complet n'existe que pour
# fr/de (voir _BELOW_1000_BY_LANG) — les autres langues ici retombent sur les
# nombres anglais (number_to_words), mais disent déjà le bon {TNX}/{DE}.
_LANG_AND_THANKS_BY_COUNTRY = (
    (_FRENCH_ENTITIES, 'fr', 'merci'),
    (('japan',), 'ja', 'arigato'),
    (('germany', 'austria', 'switzerland'), 'de', 'danke'),
    (('italy', 'sardinia'), 'it', 'grazie'),
    (('spain', 'balearic', 'canary'), 'es', 'gracias'),
    (('portugal', 'azores', 'madeira', 'brazil'), 'pt', 'obrigado'),
    (('netherlands',), 'nl', 'dank u'),
)
# thanks_word() est plus PRUDENT que lang_for_call() : un pays non identifié
# retombe sur 'en' pour les NOMBRES (il faut bien dire quelque chose), mais ne
# dit AUCUN mot de remerciement improvisé — seuls ces pays précis disent
# « thanks » explicitement, le reste se tait plutôt que de présumer l'anglais.
_ENGLISH_ENTITIES = ('united states', 'canada', 'england', 'scotland', 'wales',
                     'ireland', 'australia', 'new zealand', 'south africa')


def _country(call):
    try:
        import logx_dxcc as dxcc
        return ((dxcc.lookup(call) or {}).get('country') or '')
    except Exception:
        return ''


def lang_for_call(call):
    """Code langue à 2 lettres dérivé du PAYS de l'indicatif (fr/ja/de/it/es/
    pt/nl si l'entité est reconnue dans _LANG_AND_THANKS_BY_COUNTRY, sinon
    'en' — anglais, langue internationale du trafic, aussi le repli par
    défaut pour un pays non identifié). Gouverne la langue des NOMBRES dits
    en toutes lettres (voir number_to_words) et du connecteur {DE}."""
    c = _country(call).lower()
    for keys, lang, _ in _LANG_AND_THANKS_BY_COUNTRY:
        if any(k in c for k in keys):
            return lang
    return 'en'


def message_lang(ctx):
    ctx = ctx or {}
    return lang_for_call(ctx.get('call') or ctx.get('mycall') or '')


def thanks_word(call):
    """Mot de remerciement dans la langue du pays de l'indicatif — '' si aucun
    mot dédié NI anglais reconnu (pays non identifié : on ne dira alors que
    « 73 », jamais un « thanks » présomptueux — voir _ENGLISH_ENTITIES)."""
    c = _country(call).lower()
    if not c:
        return ''
    for keys, _, word in _LANG_AND_THANKS_BY_COUNTRY:
        if any(k in c for k in keys):
            return word
    return 'thanks' if any(k in c for k in _ENGLISH_ENTITIES) else ''


# Connecteur {DE} ("F4GLD DE W1AW" -> "... from W1AW"/"... de W1AW"/"...
# von W1AW"...), English par défaut. 'ja' est un choix approximatif : le
# japonais est une langue à POSTPOSITIONS (« kara » se dirait APRÈS le nom,
# pas au même endroit qu'un « from » anglais) — restructurer toute la phrase
# est hors de portée de ce simple remplacement de mot, mais un mot japonais
# reste plus proche du sens qu'un « from » anglais laissé tel quel.
_DE_CONNECTOR_BY_LANG = {'fr': 'de', 'de': 'von', 'it': 'da', 'es': 'de',
                         'pt': 'de', 'nl': 'van', 'ja': 'kara'}


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
      {RST_SENT}/{RST_RCVD}/{NR} -> EN TOUTES LETTRES TOUJOURS EN ANGLAIS
        (« fifty-nine », jamais « cinquante-neuf »/« neunundfünfzig »…),
        quelle que soit la langue dérivée de l'indicatif — retour F4GLD
        04/08/2026 : l'échange (le report/la série) doit rester simple et
        sans ambiguïté, la convention terrain donne toujours ces chiffres
        en anglais même entre deux stations de même langue ;
      {DE} -> « de »/« from »/« von »… dans la langue dérivée — contrairement
        à « stroke » (toujours international, jamais traduit), c'est un mot
        de la PHRASE elle-même, dit naturellement dans sa propre langue en
        phonie (retour F4GLD 04/08/2026 : « de » figé en dur ne devenait
        jamais « from » même quand le reste du message était en anglais) ;
      {TNX} -> « 73 » + remerciement dans la langue du correspondant (le
        « 73 » de politesse en clôture n'est PAS un report d'échange, il
        reste localisé — voir closing_73) ;
      {73} -> idem, hors clôture ({TNX} l'inclut déjà)."""
    ctx = ctx or {}
    lang = message_lang(ctx)
    return (str(template or '')
            .replace('{CALL}', spell_callsign(ctx.get('call', '')))
            .replace('{MYCALL}', spell_callsign(ctx.get('mycall', '')))
            .replace('{RST_SENT}', spell_number(ctx.get('rst_sent', ''), 'en'))
            .replace('{RST_RCVD}', spell_number(ctx.get('rst_rcvd', ''), 'en'))
            .replace('{NR}', spell_number(ctx.get('nr', ''), 'en'))
            .replace('{DE}', _DE_CONNECTOR_BY_LANG.get(lang, 'from'))
            .replace('{TNX}', closing_73(ctx))
            .replace('{73}', spell_number('73', lang)))


_PLACEHOLDER_RE = re.compile(r'\{[A-Z_0-9]+\}')


def expand_voice_segments(template, ctx):
    """Comme expand_voice_text(), mais rend une liste [(texte, langue), ...]
    au lieu d'une chaîne unique — un segment par « zone de langue » du
    message, pour la synthèse MULTI-VOIX (voir send_voice_message()).

    Une voix SAPI/Piper UNIQUE pour tout le message lisait l'alphabet OACI/
    « fifty-nine » (toujours censés être en anglais, voir expand_voice_text)
    avec l'ACCENT de la voix locale choisie pour {DE}/{TNX} — retour F4GLD
    04/08/2026, ex. « fifty-nine » prononcé à la française. Ici, le texte
    littéral du template et {CALL}/{MYCALL}/{RST_SENT}/{RST_RCVD}/{NR}
    restent TOUJOURS étiquetés 'en' (jargon international/donnée d'échange,
    jamais concerné par la langue dérivée) ; seuls {DE}/{TNX}/{73} portent
    la langue dérivée de l'indicatif. Les segments adjacents de même langue
    sont fusionnés (évite des allers-retours de voix inutiles pour du texte
    littéral collé à un segment anglais, ex. la virgule après {MYCALL})."""
    ctx = ctx or {}
    lang = message_lang(ctx)
    values = {
        '{CALL}': (spell_callsign(ctx.get('call', '')), 'en'),
        '{MYCALL}': (spell_callsign(ctx.get('mycall', '')), 'en'),
        '{RST_SENT}': (spell_number(ctx.get('rst_sent', ''), 'en'), 'en'),
        '{RST_RCVD}': (spell_number(ctx.get('rst_rcvd', ''), 'en'), 'en'),
        '{NR}': (spell_number(ctx.get('nr', ''), 'en'), 'en'),
        '{DE}': (_DE_CONNECTOR_BY_LANG.get(lang, 'from'), lang),
        '{TNX}': (closing_73(ctx), lang),
        '{73}': (spell_number('73', lang), lang),
    }
    text = str(template or '')
    raw = []
    pos = 0
    for m in _PLACEHOLDER_RE.finditer(text):
        if m.start() > pos:
            raw.append((text[pos:m.start()], 'en'))
        raw.append(values.get(m.group(0), (m.group(0), 'en')))
        pos = m.end()
    if pos < len(text):
        raw.append((text[pos:], 'en'))
    merged = []
    for t, l in raw:
        if merged and merged[-1][1] == l:
            merged[-1] = (merged[-1][0] + t, l)
        else:
            merged.append((t, l))
    return merged


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
        # Voix IA cloud (optionnelle) : voir synthesize_to_wav() / AI_PROVIDERS.
        # Un provider vide retombe sur 'elevenlabs' — le seul supporté pour
        # l'instant, mais le champ existe déjà pour ne pas migrer la config
        # au jour où un 2e fournisseur est ajouté.
        'ai': {
            'enabled': bool(cfg.get('voicekeyer_ai_enabled')),
            'provider': cfg.get('voicekeyer_ai_provider') or 'elevenlabs',
            'api_key': cfg.get('voicekeyer_ai_api_key', ''),
            'voice_id': cfg.get('voicekeyer_ai_voice_id', ''),
        },
        # Piper (rhasspy/piper) : moteur neuronal LOCAL, hors-ligne, sans
        # abonnement — voir synthesize_to_wav_piper(). 'exe' vide retombe sur
        # 'piper' (nom de commande, suppose Piper sur le PATH) ; 'model' est
        # le chemin d'un fichier de voix .onnx téléchargé une fois par
        # l'opérateur (rhasspy/piper-voices sur Hugging Face).
        'piper': {
            'enabled': bool(cfg.get('voicekeyer_piper_enabled')),
            'exe': cfg.get('voicekeyer_piper_exe') or 'piper',
            'model': cfg.get('voicekeyer_piper_model', ''),
        },
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


# ─── VOIX IA CLOUD (optionnelle) ──────────────────────────────────────────────
# Rendu nettement plus naturel qu'une voix SAPI5 locale, mais dépend du réseau
# et d'une clé API — ce que le keyer vocal a toujours explicitement évité
# (« aucun réseau », voir l'en-tête de ce fichier), parce qu'un concours de
# 24-48h ne doit jamais dépendre d'internet pour dire un indicatif. On ne
# remplace donc PAS la voix locale : ceci est un ESSAI, avec repli automatique
# et silencieux sur pyttsx3 si le fournisseur est injoignable, la clé absente/
# invalide, ou le timeout dépassé (retour F4GLD 04/08/2026).
#
# Cache par texte EXACT (hash du triplet fournisseur/voix/texte) : un message
# fixe (CQ, qui ne varie jamais dans le concours) ou une station déjà
# travaillée ne refait jamais l'appel réseau ni son coût. Le cache n'est
# jamais purgé (quelques dizaines de Ko par entrée, un contest ne produit pas
# assez d'indicatifs DISTINCTS pour que ça pèse sur le disque).
_AI_CACHE_DIR = 'voice_ai_cache'
_AI_TIMEOUT = 10


def _ai_cache_dir():
    os.makedirs(_AI_CACHE_DIR, exist_ok=True)
    return _AI_CACHE_DIR


def _ai_cache_path(provider, voice_id, text):
    key = f'{provider}|{voice_id}|{text}'.encode('utf-8')
    return os.path.join(_ai_cache_dir(), hashlib.sha256(key).hexdigest() + '.wav')


def _elevenlabs_pcm(api_key, voice_id, text, timeout):
    """PCM 16 bits mono 24 kHz brut (pas de dépendance de décodage MP3/ffmpeg
    à ajouter au projet), ou None si injoignable/clé invalide/erreur HTTP."""
    import logx_utils as utils
    vid = urllib.parse.quote(str(voice_id or '').strip(), safe='')
    url = f'https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=pcm_24000'
    status, data = utils.post_url_json_binary(
        url, {'text': text, 'model_id': 'eleven_turbo_v2_5'}, timeout=timeout,
        headers={'xi-api-key': api_key, 'Accept': 'audio/*'})
    if status != 200 or not data:
        return None
    return data


AI_PROVIDERS = {'elevenlabs': _elevenlabs_pcm}


def _write_wav_from_pcm(path, pcm_bytes, sample_rate=24000):
    tmp = path + '.tmp'
    with wave.open(tmp, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # 16 bits
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    os.replace(tmp, path)           # publication atomique, même schéma que enregistrer_message()


def synthesize_to_wav_ai(text, provider, api_key, voice_id, timeout=_AI_TIMEOUT):
    """Synthèse via un fournisseur IA cloud, avec cache par texte exact.
    Retourne TOUJOURS une COPIE jetable du fichier de cache (jamais le fichier
    de cache lui-même) — l'appelant peut la supprimer après lecture sans
    affecter les prochains appels. None si indisponible pour quelque raison
    que ce soit (réseau, clé, timeout, provider inconnu) : ne lève jamais."""
    if provider not in AI_PROVIDERS or not api_key or not str(voice_id or '').strip():
        return None
    cache_path = _ai_cache_path(provider, voice_id, text)
    with _ai_cache_lock:
        if not os.path.exists(cache_path):
            try:
                pcm = AI_PROVIDERS[provider](api_key, voice_id, text, timeout)
                if not pcm:
                    return None
                _write_wav_from_pcm(cache_path, pcm)
            except Exception:
                return None
    fd, tmp_path = tempfile.mkstemp(suffix='.wav', prefix='rc_voice_ai_')
    os.close(fd)
    try:
        shutil.copyfile(cache_path, tmp_path)
        return tmp_path
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return None


# ─── PIPER (moteur neuronal local, hors-ligne, sans abonnement) ──────────────
# https://github.com/rhasspy/piper — installé et invoqué à part (sous-processus,
# comme sounddevice/pyttsx3 s'appuient sur PortAudio/SAPI5), PAS un paquet pip
# de ce projet : l'opérateur installe `piper-tts` (fournit la commande `piper`)
# et télécharge UNE FOIS un modèle de voix .onnx (rhasspy/piper-voices sur
# Hugging Face) — indiqué en CONFIG. Choisi par F4GLD (04/08/2026) à la place
# d'un fournisseur cloud payant (ElevenLabs) : rendu neuronal nettement plus
# naturel que SAPI5, mais SANS abonnement ni dépendance réseau à l'usage.
_PIPER_TIMEOUT = 15


def synthesize_to_wav_piper(text, exe, model, timeout=_PIPER_TIMEOUT):
    """Synthèse via Piper (sous-processus). Retourne le chemin d'un WAV
    temporaire, ou None si indisponible pour quelque raison que ce soit
    (exécutable introuvable, modèle non configuré, timeout, sortie vide) —
    ne lève jamais. L'appelant retombe alors sur pyttsx3 (SAPI5)."""
    exe = str(exe or '').strip() or 'piper'
    model = str(model or '').strip()
    if not model:
        return None
    fd, path = tempfile.mkstemp(suffix='.wav', prefix='rc_voice_piper_')
    os.close(fd)
    try:
        result = subprocess.run(
            [exe, '--model', model, '--output_file', path],
            input=text.encode('utf-8'), capture_output=True, timeout=timeout)
        if result.returncode != 0 or os.path.getsize(path) < 100:
            os.remove(path)
            return None
        return path
    except Exception:
        # FileNotFoundError (exe absent du PATH), TimeoutExpired, modèle
        # invalide (Piper écrit alors un WAV vide ou rien du tout)...
        try:
            os.remove(path)
        except OSError:
            pass
        return None


# ─── SYNTHÈSE + LECTURE ───────────────────────────────────────────────────────
# Partagé par _voice_id_for_lang() (repli auto) ET _voice_matches_lang()
# (la voix CONFIG convient-elle à CE segment ?) — voir synthesize_to_wav().
_LANG_VOICE_HINTS = {
    'fr': ('french', 'français', 'francais', 'fr-', 'fr_', 'fra'),
    'en': ('english', 'en-', 'en_', 'enu', 'eng'),
    'de': ('german', 'deutsch', 'de-', 'de_', 'deu'),
    'it': ('italian', 'italiano', 'it-', 'it_', 'ita'),
    'es': ('spanish', 'español', 'espanol', 'es-', 'es_', 'esp'),
    'pt': ('portuguese', 'português', 'portugues', 'pt-', 'pt_', 'por'),
    'nl': ('dutch', 'nederlands', 'nl-', 'nl_', 'nld'),
    'ja': ('japanese', 'ja-', 'ja_', 'jpn'),
}


def _voice_id_for_lang(engine, lang):
    """id d'une voix SAPI installée correspondant à la langue (fr/en/de…), ou
    None si aucune voix de cette langue n'est installée (repli sur la voix
    par défaut du moteur — aucune erreur, juste moins naturel). Rend
    « cinquante-neuf, merci »/« neunundfünfzig, danke » naturel avec une
    VRAIE voix de la langue plutôt qu'une voix anglaise par défaut."""
    hints = _LANG_VOICE_HINTS.get(lang or '', ())
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


def _voice_matches_lang(engine, voice_id, lang):
    """True si la voix CONFIG (`voice_id`) correspond déjà à `lang` — pour ne
    PAS l'utiliser sur un segment d'une AUTRE langue (retour F4GLD
    04/08/2026 : une voix française configurée en CONFIG lisait « fifty-nine »
    avec un accent français, l'anglais international étant censé rester
    prononcé correctement quel que soit le reste du message). Sans langue
    demandée, ou langue sans indices connus, ou voix introuvable dans la
    liste : on ne bloque pas, la voix configurée est acceptée telle quelle."""
    if not lang:
        return True
    hints = _LANG_VOICE_HINTS.get(lang, ())
    if not hints:
        return True
    try:
        for v in engine.getProperty('voices'):
            if str(v.id) == str(voice_id):
                hay = (str(v.id) + ' ' + str(v.name) + ' '
                       + ','.join(v.languages or [])).lower()
                return any(h in hay for h in hints)
    except Exception:
        pass
    return True


def _trim_silence_wav(path, seuil_fraction=0.02, marge_ms=25):
    """Rogne le silence en tête et en fin d'un WAV, EN PLACE — les moteurs TTS
    (SAPI5/Piper/ElevenLabs) laissent chacun un blanc de tête/fin variable.
    Invisible sur une synthèse ISOLÉE, mais send_voice_message(segments=...)
    joue plusieurs clips l'un après l'autre (emettre_wav_multi) : ces blancs
    s'additionnent à CHAQUE frontière de segment et s'entendent comme une
    pause parasite entre deux mots pourtant censés s'enchaîner — ex. le
    connecteur {DE}, isolé dans son propre segment de langue, entouré de
    deux coupures audibles (retour F4GLD 04/08/2026).

    seuil_fraction : fraction de l'amplitude MAX du fichier en-dessous de
    laquelle un échantillon compte comme silence — un seuil ABSOLU ne
    marcherait pas, le niveau de sortie varie d'un moteur/d'une voix à
    l'autre. marge_ms : laissé de part et d'autre du son détecté pour ne
    jamais couper l'attaque/la chute d'un mot (rogner à zéro ferait un clic
    audible). Écriture sur un fichier temporaire puis remplacement
    atomique (os.replace) : jamais de fichier tronqué/corrompu si l'écriture
    est interrompue en cours de route. N'échoue jamais silencieusement côté
    appelant : fichier illisible, compressé, ou entièrement silencieux ->
    ne touche à rien (le WAV d'origine, non rogné, reste utilisable)."""
    # str() : wave.open() (Python 3.13) n'accepte QUE str ou un objet fichier
    # déjà ouvert — pas les chemins pathlib.Path (os.PathLike générique),
    # contrairement à builtins.open(). Piégé par les tests (tmp_path / '...'
    # est un Path) ; les appelants réels de ce module passent déjà des str
    # (tempfile.mkstemp()), mais autant rester robuste aux deux.
    path = str(path)
    try:
        with wave.open(path, 'rb') as wf:
            n = wf.getnframes()
            sampwidth = wf.getsampwidth()
            nchannels = wf.getnchannels()
            framerate = wf.getframerate()
            comptype = wf.getcomptype()
            raw = wf.readframes(n)
    except (wave.Error, OSError, EOFError):
        return
    if comptype != 'NONE' or sampwidth not in (1, 2, 4) or n == 0 or nchannels < 1:
        return   # PCM non compressé seulement — sinon on ne sait pas interpréter les octets

    typecode = {1: 'b', 2: 'h', 4: 'i'}[sampwidth]
    try:
        samples = array.array(typecode)
        samples.frombytes(raw)
    except ValueError:
        return   # taille incohérente (fichier tronqué) : on ne touche à rien
    if not samples:
        return
    pic = max(abs(s) for s in samples)
    if pic == 0:
        return   # silence total : rien à rogner, rien à jouer de toute façon
    seuil = max(1, int(pic * seuil_fraction))

    # Un "sample" par canal ; on travaille par FRAME (tous canaux confondus)
    # pour ne jamais couper au milieu d'une frame stéréo.
    n_frames = len(samples) // nchannels

    def frame_actif(i):
        base = i * nchannels
        return any(abs(samples[base + c]) >= seuil for c in range(nchannels))

    debut = 0
    while debut < n_frames and not frame_actif(debut):
        debut += 1
    fin = n_frames - 1
    while fin > debut and not frame_actif(fin):
        fin -= 1
    if debut >= fin:
        return   # rien d'exploitable détecté (silence quasi total) : on laisse tel quel

    marge = int(framerate * marge_ms / 1000)
    debut = max(0, debut - marge)
    fin = min(n_frames - 1, fin + marge)
    if debut == 0 and fin == n_frames - 1:
        return   # déjà rien à rogner

    trimmed = samples[debut * nchannels:(fin + 1) * nchannels]

    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.wav', dir=os.path.dirname(path) or None)
    os.close(tmp_fd)
    try:
        with wave.open(tmp_path, 'wb') as wf:
            wf.setnchannels(nchannels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(framerate)
            wf.writeframes(trimmed.tobytes())
        os.replace(tmp_path, path)
    except OSError:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def synthesize_to_wav(text, voice_id='', rate=175, lang='', ai=None, piper=None):
    """Génère un WAV temporaire, ou None si aucune synthèse n'a produit de son
    exploitable. `lang` : voix à utiliser pour CE texte précis. Le voice_id
    explicite (CONFIG) prime SEULEMENT s'il correspond à `lang` (voir
    _voice_matches_lang) — sinon une voix installée pour `lang` est
    préférée automatiquement (retour F4GLD 04/08/2026 : une voix française
    configurée ne doit jamais lire un segment anglais avec un accent
    français ; voir send_voice_message(segments=...) pour la synthèse
    multi-voix d'un même message).

    Trois moteurs par ordre de préférence, chacun optionnel et silencieux à
    l'échec (voir le docstring du module) :
      1. `ai` (dict, voir voicekeyer_settings()['ai']) : voix IA cloud
         (ElevenLabs) si activée et configurée ;
      2. `piper` (dict, voir voicekeyer_settings()['piper']) : Piper, moteur
         neuronal local hors-ligne, si activé et configuré ;
      3. pyttsx3 (SAPI5/Windows) — toujours tenté en dernier recours.
    Omis/vide = comportement inchangé (voix locale uniquement), pour ne rien
    casser des appelants existants."""
    text = (text or '').strip()
    if not text:
        return None
    ai = ai or {}
    if ai.get('enabled'):
        path = synthesize_to_wav_ai(text, ai.get('provider') or 'elevenlabs',
                                    ai.get('api_key', ''), ai.get('voice_id', ''))
        if path:
            _trim_silence_wav(path)
            return path
        print('[VOICEKEYER] Voix IA indisponible, repli sur Piper/voix locale')
    piper = piper or {}
    if piper.get('enabled'):
        path = synthesize_to_wav_piper(text, piper.get('exe') or 'piper', piper.get('model', ''))
        if path:
            _trim_silence_wav(path)
            return path
        print('[VOICEKEYER] Piper indisponible, repli sur la voix locale SAPI5')
    try:
        import pyttsx3
    except Exception:
        return None
    fd, path = tempfile.mkstemp(suffix='.wav', prefix='rc_voice_')
    os.close(fd)
    try:
        engine = pyttsx3.init()
        try:
            if voice_id and _voice_matches_lang(engine, voice_id, lang):
                vid = voice_id
            else:
                vid = _voice_id_for_lang(engine, lang) or voice_id
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
        _trim_silence_wav(path)
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
    if cat_settings['enabled'] and cat_settings['mode'] == 'omnirig':
        import logx_omnirig as omnirig
        return omnirig.set_ptt(cfg, on)
    if cat_settings['enabled'] and cat_settings['mode'] == 'flex':
        import logx_flexradio as flexradio
        return flexradio.set_ptt(cfg, on)
    if cat_settings['enabled'] and cat_settings['mode'] == 'icom_remote':
        import logx_icomremote as icomremote
        return icomremote.set_ptt(cfg, on)
    import logx_rig as rig
    rig_settings = rig.rig_settings(cfg)
    if rig_settings['enabled']:
        return rig.set_ptt(rig_settings['host'], rig_settings['port'], on)
    return {'ok': False, 'error': 'Pilotage radio désactivé (CONFIG)'}


def set_ptt(cfg, on):
    """PTT explicite pour un appelant externe au keyer vocal (ex. le
    décodeur FT8 natif, logx_ft8.html : la radio ignore tout du protocole
    FT8, seul le ton audio compte, donc PTT doit être commandé autour de la
    lecture, comme pour un micro externe). Simple alias public de _set_ptt :
    même dispatch natif/TCI/flrig/rigctld, rien d'autre — évite d'exposer
    (ou de dupliquer) un symbole préfixé _ hors de ce module."""
    return _set_ptt(cfg, on)


def _synthese_indisponible_message(settings):
    moteurs_essayes = ['IA'] * settings['ai']['enabled'] + ['Piper'] * settings['piper']['enabled']
    if moteurs_essayes:
        return 'Synthèse vocale indisponible (%s et voix locale tous en échec)' % '/'.join(moteurs_essayes)
    return 'Synthèse vocale indisponible (moteur TTS)'


def send_voice_message(cfg, text, lang='', skip_ptt=False, segments=None):
    """PTT ON -> synthèse + lecture -> PTT OFF, quel que soit le mode CAT
    actif. `lang` : préfère une voix SAPI de cette langue (voir expand_voice_text
    / message_lang). `skip_ptt` : n'engage jamais le PTT — réservé au bouton
    « Tester » de CONFIG (indicatif fictif), pour prévisualiser le périphérique/
    la voix choisis SANS exiger que le pilotage radio soit déjà configuré (voir
    emettre_wav).

    `segments` (optionnel, liste [(texte, langue), ...] — voir
    expand_voice_segments()) : si fourni, CHAQUE segment est synthétisé avec
    sa PROPRE voix puis tous joués en séquence sous UNE SEULE prise de PTT —
    évite qu'une voix unique (ex. française, choisie pour {DE}/{TNX}) lise
    un mot anglais international (ex. « fifty-nine ») avec son accent
    (retour F4GLD 04/08/2026). Omis/None = comportement inchangé (une seule
    synthèse, `text`/`lang` à plat), pour ne rien casser des appelants
    existants. Ne lève jamais : {'ok': bool, 'error'?: str}."""
    settings = voicekeyer_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Keyer vocal désactivé (CONFIG)'}
    text = (text or '').strip()
    if not text:
        return {'ok': False, 'error': 'Message vide'}

    if segments:
        paths = []
        for seg_text, seg_lang in segments:
            seg_text = (seg_text or '').strip()
            if not seg_text:
                continue
            p = synthesize_to_wav(seg_text, settings['voice_id'], settings['rate'], seg_lang,
                                  settings['ai'], settings['piper'])
            if not p:
                for existing in paths:
                    try:
                        os.remove(existing)
                    except OSError:
                        pass
                return {'ok': False, 'error': _synthese_indisponible_message(settings)}
            paths.append(p)
        if not paths:
            return {'ok': False, 'error': 'Message vide'}
        # Les WAV de synthèse sont temporaires : emettre_wav_multi() les
        # supprime lui-même après émission (supprimer_apres), y compris si
        # la lecture échoue en cours de route.
        return emettre_wav_multi(cfg, paths, settings['device'],
                                 supprimer_apres=True, extra={'text': text}, skip_ptt=skip_ptt)

    path = synthesize_to_wav(text, settings['voice_id'], settings['rate'], lang,
                             settings['ai'], settings['piper'])
    if not path:
        return {'ok': False, 'error': _synthese_indisponible_message(settings)}

    # Le WAV de synthèse est temporaire : emettre_wav() le supprime lui-même
    # après émission (supprimer_apres), y compris si la lecture échoue.
    return emettre_wav(cfg, path, settings['device'],
                       supprimer_apres=True, extra={'text': text}, skip_ptt=skip_ptt)


def emettre_wav_multi(cfg, paths, device, supprimer_apres=False, extra=None, skip_ptt=False):
    """Comme emettre_wav(), mais joue PLUSIEURS WAV en SÉQUENCE sous UNE
    SEULE prise de PTT (voir send_voice_message(segments=...)) — chaque
    segment peut avoir son propre débit d'échantillonnage/sa propre voix,
    play_wav() lit celui du fichier à chaque appel, aucun ré-échantillonnage
    ni concaténation binaire nécessaire.

    `skip_ptt=True` : ne touche jamais au PTT (ni ON ni OFF) — voir
    emettre_wav(). En émission réelle, le PTT reste obligatoire."""
    def _rm():
        if supprimer_apres:
            for p in paths:
                try:
                    os.remove(p)
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
            for p in paths:
                play_wav(p, device)
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


def emettre_wav(cfg, path, device, supprimer_apres=False, extra=None, skip_ptt=False):
    """PTT ON → lecture du WAV → PTT OFF vérifié. Séquence commune à la voix de
    synthèse (callbot) et aux messages enregistrés par l'opérateur : c'est le
    relâchement du PTT qui doit être identique dans les deux cas, pas seulement
    la lecture. Délègue à emettre_wav_multi() (un seul segment) — voir son
    docstring et celui de send_voice_message(segments=...) pour la synthèse
    multi-voix d'un même message.

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
    return emettre_wav_multi(cfg, [path], device, supprimer_apres, extra, skip_ptt)


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
    with _dvk_lock:
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
    with _dvk_lock:
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
