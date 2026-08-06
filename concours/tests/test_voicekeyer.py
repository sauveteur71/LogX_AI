# -*- coding: utf-8 -*-
"""Tests du keyer vocal dynamique (logx_voicekeyer) : épellation
phonétique, expansion de macros, orchestration PTT+lecture. Jamais de vrai
TTS/audio/CAT dans ces tests — tout est mocké, seule la logique est testée."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_voicekeyer as vk


# ─── Épellation phonétique ────────────────────────────────────────────────────

def test_spell_callsign_simple():
    assert vk.spell_callsign('F4GLD') == 'Foxtrot Four Golf Lima Delta'


def test_spell_callsign_minuscules():
    assert vk.spell_callsign('f4gld') == 'Foxtrot Four Golf Lima Delta'


def test_spell_callsign_suffixe_connu():
    # Le « / » se dit maintenant « stroke » AVANT le mot du suffixe.
    assert vk.spell_callsign('F4GLD/P') == 'Foxtrot Four Golf Lima Delta stroke portable'
    assert vk.spell_callsign('F4GLD/QRP') == 'Foxtrot Four Golf Lima Delta stroke Q R P'


def test_spell_callsign_suffixe_inconnu_epele():
    assert vk.spell_callsign('F4GLD/5') == 'Foxtrot Four Golf Lima Delta stroke Five'


def test_spell_callsign_prefixe_stroke():
    # Préfixe DX : « DL/ON4DRT » -> le « / » se dit, aucun mot de suffixe.
    assert vk.spell_callsign('DL/ON4DRT') == \
        'Delta Lima stroke Oscar November Four Delta Romeo Tango'


def test_spell_callsign_prefixe_ET_suffixe():
    # DEUX « / » : préfixe portable. C'est le cas que l'ancienne version
    # (partition sur un seul « / ») escamotait en silence.
    assert vk.spell_callsign('F/DL1UTY/P') == \
        'Foxtrot stroke Delta Lima One Uniform Tango Yankee stroke portable'


def test_spell_callsign_stroke_toujours_international_meme_pour_station_francaise():
    # « stroke » est le mot international, jamais traduit en « barre » --
    # même pour un indicatif français (retour F4GLD 04/08/2026 : entendu
    # « barre » au lieu de « stroke » pour MYCALL=F4GLD/P, jamais ainsi en
    # vrai sur l'air).
    assert vk.spell_callsign('F4GLD/P') == 'Foxtrot Four Golf Lima Delta stroke portable'


def test_spell_callsign_vide():
    assert vk.spell_callsign('') == ''
    assert vk.spell_callsign(None) == ''


def test_spell_digits_report():
    assert vk.spell_digits('59') == 'Five Nine'
    assert vk.spell_digits('599') == 'Five Nine Nine'


def test_spell_digits_serie_avec_zero():
    assert vk.spell_digits('042') == 'Zero Four Two'


def test_spell_digits_vide():
    assert vk.spell_digits('') == ''
    assert vk.spell_digits(None) == ''


# ─── Expansion des macros vocales ────────────────────────────────────────────

def test_expand_voice_text_call_et_mycall():
    ctx = {'call': 'DL1AA', 'mycall': 'F4GLD'}
    out = vk.expand_voice_text('{CALL} de {MYCALL}', ctx)
    assert out == 'Delta Lima One Alpha Alpha de Foxtrot Four Golf Lima Delta'


def test_expand_voice_text_report_et_serie():
    # Sans indicatif de correspondant -> anglais international, EN TOUTES LETTRES.
    ctx = {'rst_sent': '59', 'nr': '001'}
    out = vk.expand_voice_text('{RST_SENT} {NR}', ctx)
    assert out == 'fifty-nine zero zero one'


# ─── Nombres en toutes lettres (le cœur de la demande) ──────────────────────

def test_number_to_words_anglais():
    cas = {0: 'zero', 5: 'five', 15: 'fifteen', 20: 'twenty', 42: 'forty-two',
           59: 'fifty-nine', 73: 'seventy-three', 100: 'one hundred',
           599: 'five hundred ninety-nine', 2024: 'two thousand twenty-four'}
    for n, mot in cas.items():
        assert vk.number_to_words(n, 'en') == mot, n


def test_number_to_words_francais_cas_piegeux():
    cas = {0: 'zéro', 16: 'seize', 21: 'vingt et un', 22: 'vingt-deux',
           59: 'cinquante-neuf', 60: 'soixante', 61: 'soixante et un',
           70: 'soixante-dix', 71: 'soixante et onze', 72: 'soixante-douze',
           76: 'soixante-seize', 77: 'soixante-dix-sept', 80: 'quatre-vingts',
           81: 'quatre-vingt-un', 90: 'quatre-vingt-dix', 91: 'quatre-vingt-onze',
           99: 'quatre-vingt-dix-neuf', 73: 'soixante-treize', 100: 'cent',
           200: 'deux cents', 201: 'deux cent un',
           599: 'cinq cent quatre-vingt-dix-neuf', 1000: 'mille',
           2024: 'deux mille vingt-quatre'}
    for n, mot in cas.items():
        assert vk.number_to_words(n, 'fr') == mot, n


def test_number_to_words_allemand_cas_pieges():
    """Retour F4GLD 04/08/2026 : un indicatif DL doit s'entendre en
    allemand — unité-puis-dizaine inversées (« einundzwanzig »), mots
    composés SANS espace (contrairement au français/anglais)."""
    cas = {0: 'null', 1: 'eins', 12: 'zwölf', 16: 'sechzehn',
           20: 'zwanzig', 21: 'einundzwanzig', 22: 'zweiundzwanzig',
           59: 'neunundfünfzig', 73: 'dreiundsiebzig',
           100: 'einhundert', 101: 'einhunderteins',
           200: 'zweihundert', 599: 'fünfhundertneunundneunzig',
           1000: 'eintausend', 2024: 'zweitausendvierundzwanzig'}
    for n, mot in cas.items():
        assert vk.number_to_words(n, 'de') == mot, n


def test_number_to_words_italien_cas_pieges():
    """Élision devant 1/8 (ventuno, ventotto — pas venti-uno) et accent sur
    les combinaisons en 3 (ventitré) : les deux pièges classiques de
    l'italien parlé/écrit."""
    cas = {0: 'zero', 8: 'otto', 20: 'venti', 21: 'ventuno', 22: 'ventidue',
           23: 'ventitré', 28: 'ventotto', 29: 'ventinove',
           33: 'trentatré', 59: 'cinquantanove', 73: 'settantatré',
           81: 'ottantuno', 88: 'ottantotto', 100: 'cento', 101: 'centouno',
           200: 'duecento', 599: 'cinquecentonovantanove',
           1000: 'mille', 2024: 'duemilaventiquattro'}
    for n, mot in cas.items():
        assert vk.number_to_words(n, 'it') == mot, n


def test_number_to_words_espagnol_cas_pieges():
    """16-29 sont des mots fusionnés (dieciséis, veintiuno) ; 30+ garde « y »
    et des espaces (cincuenta y nueve) — deux régimes différents dans la
    même langue. « cien » pile, « ciento » dès qu'un reste suit."""
    cas = {0: 'cero', 16: 'dieciséis', 20: 'veinte', 21: 'veintiuno',
           23: 'veintitrés', 29: 'veintinueve', 30: 'treinta',
           31: 'treinta y uno', 59: 'cincuenta y nueve', 73: 'setenta y tres',
           99: 'noventa y nueve', 100: 'cien', 101: 'ciento uno',
           200: 'doscientos', 500: 'quinientos', 599: 'quinientos noventa y nueve',
           900: 'novecientos', 1000: 'mil', 2024: 'dos mil veinticuatro'}
    for n, mot in cas.items():
        assert vk.number_to_words(n, 'es') == mot, n


def test_number_to_words_portugais_cas_pieges():
    """« e » de liaison partout (vinte e um, cinquenta e nove), mais
    SEULEMENT si le reste après les milliers est < 100 (mil duzentos,
    SANS « e » ; mil e um, AVEC) — la seule langue ici où le séparateur
    dépend de la valeur, pas seulement de la langue."""
    cas = {0: 'zero', 16: 'dezesseis', 20: 'vinte', 21: 'vinte e um',
           59: 'cinquenta e nove', 73: 'setenta e três',
           100: 'cem', 101: 'cento e um', 200: 'duzentos', 500: 'quinhentos',
           599: 'quinhentos e noventa e nove', 900: 'novecentos',
           1000: 'mil', 1001: 'mil e um', 1200: 'mil duzentos',
           2024: 'dois mil e vinte e quatro'}
    for n, mot in cas.items():
        assert vk.number_to_words(n, 'pt') == mot, n


def test_number_to_words_neerlandais_cas_pieges():
    """Unité-puis-dizaine inversées comme l'allemand ; tréma orthographique
    obligatoire sur « tweeën-»/« drieën- » (2 et 3 se terminent par une
    voyelle), absent pour tous les autres chiffres (vierentwintig, pas de
    tréma car « vier » se termine par une consonne)."""
    cas = {0: 'nul', 1: 'een', 20: 'twintig', 21: 'eenentwintig',
           22: 'tweeëntwintig', 23: 'drieëntwintig', 24: 'vierentwintig',
           59: 'negenenvijftig', 73: 'drieënzeventig',
           100: 'honderd', 101: 'honderdeen', 200: 'tweehonderd',
           599: 'vijfhonderdnegenennegentig', 1000: 'duizend',
           2024: 'tweeduizendvierentwintig'}
    for n, mot in cas.items():
        assert vk.number_to_words(n, 'nl') == mot, n


def test_number_to_words_japonais_cas_pieges():
    """Rōmaji (écriture latine) — changements euphoniques IRRÉGULIERS aux
    centaines/milliers (san+hyaku -> sanbyaku, roku+hyaku -> roppyaku,
    hachi+hyaku -> happyaku, hachi+sen -> hassen), pas une simple
    concaténation mécanique."""
    cas = {0: 'zero', 1: 'ichi', 10: 'juu', 11: 'juuichi', 19: 'juukyuu',
           20: 'nijuu', 21: 'nijuuichi', 59: 'gojuukyuu', 73: 'nanajuusan',
           100: 'hyaku', 101: 'hyakuichi', 200: 'nihyaku', 300: 'sanbyaku',
           600: 'roppyaku', 800: 'happyaku',
           599: 'gohyakukyuujuukyuu', 1000: 'sen', 2000: 'nisen',
           3000: 'sanzen', 8000: 'hassen', 2024: 'nisennijuuyon'}
    for n, mot in cas.items():
        assert vk.number_to_words(n, 'ja') == mot, n


def test_spell_number_zeros_de_tete_et_alphanumerique():
    assert vk.spell_number('59', 'fr') == 'cinquante-neuf'
    assert vk.spell_number('001', 'fr') == 'zéro zéro un'
    assert vk.spell_number('042', 'fr') == 'zéro quarante-deux'
    assert vk.spell_number('001', 'en') == 'zero zero one'
    assert vk.spell_number('00', 'fr') == 'zéro zéro'
    assert vk.spell_number('3A', 'en') == 'Three Alpha'   # non numérique -> phonétique
    assert vk.spell_number('', 'fr') == ''
    assert vk.spell_number('059', 'de') == 'null neunundfünfzig'


# ─── Langue et remerciement dérivés de l'indicatif ──────────────────────────

def _mock_country(monkeypatch, name):
    import logx_dxcc as dxcc
    monkeypatch.setattr(dxcc, 'lookup', lambda call: {'country': name} if call else None)


def test_lang_for_call_par_pays(monkeypatch):
    """lang_for_call() couvre désormais fr/ja/de/it/es/pt/nl (avec système de
    nombres complet pour fr/de seulement — voir _BELOW_1000_BY_LANG), 'en'
    en repli pour tout le reste, y compris un pays non identifié."""
    cas = [('France', 'F5ABC', 'fr'), ('Fed. Rep. of Germany', 'DL1AA', 'de'),
           ('Japan', 'JA1XYZ', 'ja'), ('Italy', 'IZ1ABC', 'it'),
           ('Spain', 'EA1ABC', 'es'), ('Brazil', 'PY1ABC', 'pt'),
           ('Netherlands', 'PA1ABC', 'nl'), ('United States', 'W1AW', 'en')]
    for pays, call, attendu in cas:
        _mock_country(monkeypatch, pays)
        assert vk.lang_for_call(call) == attendu, pays
    _mock_country(monkeypatch, '')
    assert vk.lang_for_call('X') == 'en'


def test_thanks_word_par_pays(monkeypatch):
    for pays, mot in [('France', 'merci'), ('Japan', 'arigato'),
                      ('Fed. Rep. of Germany', 'danke'), ('Italy', 'grazie'),
                      ('Spain', 'gracias'), ('Brazil', 'obrigado'),
                      ('United States', 'thanks')]:
        _mock_country(monkeypatch, pays)
        assert vk.thanks_word('CALL') == mot, pays
    _mock_country(monkeypatch, 'Mongolia')
    assert vk.thanks_word('JT1X') == ''          # pas de mot dédié -> juste 73


def test_closing_73_selon_indicatif(monkeypatch):
    _mock_country(monkeypatch, 'France')
    assert vk.closing_73({'call': 'F5ABC'}) == 'soixante-treize merci'
    _mock_country(monkeypatch, 'Japan')
    assert vk.closing_73({'call': 'JA1XYZ'}) == 'nanajuusan arigato'
    _mock_country(monkeypatch, 'Mongolia')
    assert vk.closing_73({'call': 'JT1X'}) == 'seventy-three'   # 73 seul si pas de mot


def test_expand_report_reste_toujours_en_anglais_meme_pour_station_F(monkeypatch):
    """Retour F4GLD 04/08/2026 : « pour les rapports 59 ou 58 ou 44, toujours
    passer ces chiffres en anglais » — l'échange (RST_SENT/RST_RCVD/NR) ne
    suit PLUS la langue du correspondant, contrairement à la clôture {TNX}
    (73 + remerciement) qui reste localisée, elle."""
    _mock_country(monkeypatch, 'France')
    ctx = {'call': 'F5ABC', 'rst_sent': '59', 'mycall': 'F4GLD'}
    out = vk.expand_voice_text('{CALL} {RST_SENT} {TNX}', ctx)
    assert 'Foxtrot Five Alpha Bravo Charlie' in out    # indicatif phonétique international
    assert 'fifty-nine' in out                           # report TOUJOURS en anglais
    assert 'cinquante-neuf' not in out
    assert out.endswith('soixante-treize merci')          # clôture 73 + merci : reste localisée


def test_expand_voice_text_mycall_suffixe_reste_en_stroke_meme_en_francais(monkeypatch):
    """Reproduction exacte du bouton « Tester » de CONFIG (retour F4GLD
    04/08/2026) : MYCALL=F4GLD/P dérive la langue française (F4GLD -> France)
    pour les NOMBRES, mais le « / » doit rester « stroke » (mot international,
    jamais traduit) même si le message entier est par ailleurs en français."""
    _mock_country(monkeypatch, 'France')
    out = vk.expand_voice_text('{MYCALL}', {'mycall': 'F4GLD/P'})
    assert out == 'Foxtrot Four Golf Lima Delta stroke portable'


def test_expand_report_allemand_pour_station_DL(monkeypatch):
    """Retour F4GLD 04/08/2026 : un indicatif allemand adapte le connecteur
    ({DE} -> « von ») et la clôture (73 + danke), mais PAS le report
    d'échange lui-même — { RST_SENT} reste « fifty-nine », jamais
    « neunundfünfzig » (retour F4GLD suivant : les rapports restent
    toujours en anglais, pour rester simples et sans ambiguïté)."""
    _mock_country(monkeypatch, 'Fed. Rep. of Germany')
    ctx = {'call': 'DL1AA', 'mycall': 'F4GLD', 'rst_sent': '59'}
    out = vk.expand_voice_text('{CALL} {DE} {MYCALL}, {RST_SENT} {TNX}', ctx)
    assert ' von ' in out
    assert 'fifty-nine' in out and 'neunundfünfzig' not in out
    assert out.endswith('dreiundsiebzig danke')          # clôture 73 : reste localisée


def test_expand_voice_text_placeholders_manquants_deviennent_vides():
    out = vk.expand_voice_text('CQ {MYCALL}', {})
    assert out == 'CQ '


def test_expand_voice_text_de_localise_selon_la_langue(monkeypatch):
    """{DE} suit la langue du message ('de'/'from'), CONTRAIREMENT à
    « stroke » (toujours international) — retour F4GLD 04/08/2026 : le
    bouton Tester de CONFIG figeait « de » même en anglais."""
    _mock_country(monkeypatch, 'France')
    assert vk.expand_voice_text('{DE}', {'call': 'F5ABC'}) == 'de'
    _mock_country(monkeypatch, 'United States')
    assert vk.expand_voice_text('{DE}', {'call': 'W1AW'}) == 'from'
    _mock_country(monkeypatch, 'Fed. Rep. of Germany')
    assert vk.expand_voice_text('{DE}', {'call': 'DL1AA'}) == 'von'
    for pays, call, mot in [('Italy', 'IZ1ABC', 'da'), ('Spain', 'EA1ABC', 'de'),
                             ('Brazil', 'PY1ABC', 'de'), ('Netherlands', 'PA1ABC', 'van'),
                             ('Japan', 'JA1XYZ', 'kara')]:
        _mock_country(monkeypatch, pays)
        assert vk.expand_voice_text('{DE}', {'call': call}) == mot, pays
    # Sans indicatif connu -> anglais international par défaut.
    assert vk.expand_voice_text('{DE}', {}) == 'from'


def test_voice_macros_default_ont_les_champs_attendus():
    for m in vk.VOICE_MACROS_DEFAULT:
        assert {'key', 'label', 'text'} <= set(m)


# ─── Réglages ─────────────────────────────────────────────────────────────────

def test_voicekeyer_settings_defaut():
    s = vk.voicekeyer_settings({})
    assert s['enabled'] is False and s['rate'] == 175 and s['device'] == ''


def test_voicekeyer_settings_personnalises():
    s = vk.voicekeyer_settings({'voicekeyer_enabled': True, 'voicekeyer_device': '3',
                                 'voicekeyer_voice_id': 'xyz', 'voicekeyer_rate': '150'})
    assert s == {'enabled': True, 'device': '3', 'voice_id': 'xyz', 'rate': 150,
                 'ai': {'enabled': False, 'provider': 'elevenlabs', 'api_key': '', 'voice_id': ''},
                 'piper': {'enabled': False, 'exe': 'piper', 'model': ''}}


def test_voicekeyer_settings_rate_invalide_retombe_sur_defaut():
    assert vk.voicekeyer_settings({'voicekeyer_rate': 'abc'})['rate'] == 175


# ─── Listes (jamais d'exception si moteur/peripherique indisponible) ────────

def test_list_output_devices_ne_plante_pas():
    assert isinstance(vk.list_output_devices(), list)


def test_list_tts_voices_ne_plante_pas():
    assert isinstance(vk.list_tts_voices(), list)


# ─── Orchestration send_voice_message (PTT + synthèse + lecture, tout mocké) ──

def test_send_voice_message_desactive():
    r = vk.send_voice_message({}, 'CQ test')
    assert not r['ok'] and 'désactivé' in r['error'].lower()


def test_send_voice_message_texte_vide():
    r = vk.send_voice_message({'voicekeyer_enabled': True}, '  ')
    assert not r['ok'] and 'vide' in r['error'].lower()


def test_send_voice_message_synthese_indisponible(monkeypatch):
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: None)
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test')
    assert not r['ok'] and 'synthèse' in r['error'].lower()


def test_send_voice_message_ptt_refuse(monkeypatch, tmp_path):
    fake_wav = tmp_path / 'x.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: {'ok': False, 'error': 'radio injoignable'})
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test')
    assert not r['ok'] and 'PTT refusé' in r['error']
    assert not fake_wav.exists()   # le WAV temporaire est nettoyé même en échec


def test_send_voice_message_chemin_complet(monkeypatch, tmp_path):
    fake_wav = tmp_path / 'y.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    ptt_calls = []
    played = []
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: ptt_calls.append(on) or {'ok': True})
    monkeypatch.setattr(vk, 'play_wav', lambda path, device=None: played.append(path))
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test')
    assert r['ok'] and r['text'] == 'CQ test'
    assert ptt_calls == [True, False]     # PTT activé puis relâché, dans cet ordre
    assert played == [str(fake_wav)]
    assert not fake_wav.exists()           # nettoyage du WAV temporaire


def test_send_voice_message_erreur_lecture_relache_quand_meme_le_ptt(monkeypatch, tmp_path):
    fake_wav = tmp_path / 'z.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    ptt_calls = []
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: ptt_calls.append(on) or {'ok': True})
    def boom(path, device=None):
        raise RuntimeError('périphérique audio indisponible')
    monkeypatch.setattr(vk, 'play_wav', boom)
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test')
    assert not r['ok'] and 'Lecture audio' in r['error']
    assert ptt_calls == [True, False]      # le PTT est bien relâché même après l'erreur


# ─── skip_ptt : bouton "Tester" de CONFIG, prévisualisation sans radio ────────
# Retour F4GLD 04/08/2026 : le test échouait systématiquement tant que le
# pilotage CAT n'était pas configuré, alors que l'opérateur veut juste
# vérifier le périphérique audio/la voix choisis.

def test_send_voice_message_skip_ptt_fonctionne_sans_pilotage_configure(monkeypatch, tmp_path):
    """Le PTT ne doit MEME PAS être tenté : _set_ptt ne doit jamais être
    appelé, contrairement au chemin normal (test_send_voice_message_ptt_refuse
    ci-dessus, qui échoue precisement quand _set_ptt échoue)."""
    fake_wav = tmp_path / 'skip.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    ptt_calls = []
    played = []
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt',
        lambda cfg, on: ptt_calls.append(on) or (_ for _ in ()).throw(
            AssertionError('_set_ptt ne doit jamais être appelé avec skip_ptt=True')))
    monkeypatch.setattr(vk, 'play_wav', lambda path, device=None: played.append(path))
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test', skip_ptt=True)
    assert r['ok'] and r['text'] == 'CQ test'
    assert ptt_calls == []                 # jamais appelé
    assert played == [str(fake_wav)]
    assert not fake_wav.exists()


def test_send_voice_message_skip_ptt_par_defaut_faux():
    """skip_ptt doit être opt-in explicite — le déclenchement réel depuis le
    logbook (envoyer_message()/send_voice_message() sans l'argument) doit
    conserver l'exigence PTT à l'identique, sinon un message pourrait
    sembler "envoyé" sans que la radio ait réellement transmis."""
    import inspect
    sig = inspect.signature(vk.send_voice_message)
    assert sig.parameters['skip_ptt'].default is False


def test_send_voice_message_skip_ptt_erreur_lecture_pas_de_ptt_release(monkeypatch, tmp_path):
    """Si la lecture échoue avec skip_ptt=True, aucune tentative de
    relâchement PTT ne doit avoir lieu (rien n'a été engagé)."""
    fake_wav = tmp_path / 'skip_err.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    ptt_calls = []
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: ptt_calls.append(on) or {'ok': True})
    def boom(path, device=None):
        raise RuntimeError('périphérique audio indisponible')
    monkeypatch.setattr(vk, 'play_wav', boom)
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test', skip_ptt=True)
    assert not r['ok'] and 'Lecture audio' in r['error']
    assert ptt_calls == []


# ─── Dispatch PTT selon le mode CAT actif ─────────────────────────────────────

def test_set_ptt_dispatch_natif(monkeypatch):
    import logx_cat as cat
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'native'})
    monkeypatch.setattr(cat, 'set_ptt', lambda cfg, on: {'ok': True, 'via': 'native', 'on': on})
    r = vk._set_ptt({}, True)
    assert r == {'ok': True, 'via': 'native', 'on': True}


def test_set_ptt_dispatch_tci(monkeypatch):
    import logx_cat as cat
    import logx_tci as tci
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'tci'})
    monkeypatch.setattr(tci, 'set_ptt', lambda cfg, on: {'ok': True, 'via': 'tci', 'on': on})
    r = vk._set_ptt({}, False)
    assert r == {'ok': True, 'via': 'tci', 'on': False}


def test_set_ptt_dispatch_flrig(monkeypatch):
    import logx_cat as cat
    import logx_flrig as flrig
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'flrig'})
    monkeypatch.setattr(flrig, 'flrig_settings', lambda cfg: {'host': 'h', 'port': 12345})
    monkeypatch.setattr(flrig, 'set_ptt', lambda host, port, on: {'ok': True, 'via': 'flrig', 'host': host})
    r = vk._set_ptt({}, True)
    assert r == {'ok': True, 'via': 'flrig', 'host': 'h'}


def test_set_ptt_dispatch_rigctld(monkeypatch):
    import logx_cat as cat
    import logx_rig as rig
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': False, 'mode': 'native'})
    monkeypatch.setattr(rig, 'rig_settings', lambda cfg: {'enabled': True, 'host': 'h', 'port': 1})
    monkeypatch.setattr(rig, 'set_ptt', lambda host, port, on: {'ok': True, 'via': 'rigctld', 'host': host})
    r = vk._set_ptt({}, True)
    assert r == {'ok': True, 'via': 'rigctld', 'host': 'h'}


def test_set_ptt_dispatch_omnirig(monkeypatch):
    import logx_cat as cat
    import logx_omnirig as omnirig
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'omnirig'})
    monkeypatch.setattr(omnirig, 'set_ptt', lambda cfg, on: {'ok': True, 'via': 'omnirig', 'on': on})
    r = vk._set_ptt({}, True)
    assert r == {'ok': True, 'via': 'omnirig', 'on': True}


def test_set_ptt_dispatch_flex(monkeypatch):
    import logx_cat as cat
    import logx_flexradio as flexradio
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'flex'})
    monkeypatch.setattr(flexradio, 'set_ptt', lambda cfg, on: {'ok': True, 'via': 'flex', 'on': on})
    r = vk._set_ptt({}, False)
    assert r == {'ok': True, 'via': 'flex', 'on': False}


def test_set_ptt_dispatch_icom_remote(monkeypatch):
    import logx_cat as cat
    import logx_icomremote as icomremote
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'icom_remote'})
    monkeypatch.setattr(icomremote, 'set_ptt', lambda cfg, on: {'ok': True, 'via': 'icom_remote', 'on': on})
    r = vk._set_ptt({}, True)
    assert r == {'ok': True, 'via': 'icom_remote', 'on': True}


# ─── set_ptt() : alias public, utilisé par le décodeur FT8 natif (/rig/ptt) ──

def test_set_ptt_public_delegue_au_meme_dispatch(monkeypatch):
    """set_ptt() (public, appelé par /rig/ptt dans logx_http.py — la radio ne
    sait rien du protocole FT8, LogX AI doit commander le PTT lui-même
    autour de la lecture) doit être un simple alias de _set_ptt, pas une
    logique parallèle qui pourrait diverger."""
    appels = []
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: appels.append(on) or {'ok': True, 'on': on})
    r = vk.set_ptt({'x': 1}, True)
    assert r == {'ok': True, 'on': True}
    assert appels == [True]


# ─── voicekeyer_settings() : sous-dict 'ai' ───────────────────────────────────

def test_voicekeyer_settings_ai_par_defaut_desactivee():
    s = vk.voicekeyer_settings({'voicekeyer_enabled': True})
    assert s['ai'] == {'enabled': False, 'provider': 'elevenlabs', 'api_key': '', 'voice_id': ''}


def test_voicekeyer_settings_ai_configuree():
    s = vk.voicekeyer_settings({
        'voicekeyer_ai_enabled': True, 'voicekeyer_ai_provider': 'elevenlabs',
        'voicekeyer_ai_api_key': 'sk-abc', 'voicekeyer_ai_voice_id': 'v123'})
    assert s['ai'] == {'enabled': True, 'provider': 'elevenlabs',
                       'api_key': 'sk-abc', 'voice_id': 'v123'}


# ─── synthesize_to_wav_ai() : dispatch fournisseur + cache ────────────────────
# Jamais de vrai appel réseau ici : AI_PROVIDERS['elevenlabs'] est monkeypatché.
# Le cache vit dans _AI_CACHE_DIR (relatif) — TOUJOURS redirigé vers tmp_path
# dans ces tests (voir piege-tests-ecrivent-dans-le-depot en mémoire projet :
# des tests qui écrivent dans concours/ sont un vrai bug, pas un détail).

def test_synthesize_to_wav_ai_provider_inconnu_rend_none(monkeypatch, tmp_path):
    monkeypatch.setattr(vk, '_AI_CACHE_DIR', str(tmp_path / 'cache'))
    assert vk.synthesize_to_wav_ai('CQ test', 'provider_bidon', 'sk-abc', 'v1') is None


def test_synthesize_to_wav_ai_sans_cle_rend_none(monkeypatch, tmp_path):
    monkeypatch.setattr(vk, '_AI_CACHE_DIR', str(tmp_path / 'cache'))
    assert vk.synthesize_to_wav_ai('CQ test', 'elevenlabs', '', 'v1') is None


def test_synthesize_to_wav_ai_sans_voice_id_rend_none(monkeypatch, tmp_path):
    monkeypatch.setattr(vk, '_AI_CACHE_DIR', str(tmp_path / 'cache'))
    assert vk.synthesize_to_wav_ai('CQ test', 'elevenlabs', 'sk-abc', '') is None


def _fake_pcm(n_frames=4000):
    # PCM 16 bits mono : n_frames * 2 octets, valeurs arbitraires mais non
    # nulles pour que ce ne soit pas juste un silence.
    return bytes((i % 200) for i in range(n_frames * 2))


def test_synthesize_to_wav_ai_cache_miss_appelle_le_fournisseur_et_peuple_le_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(vk, '_AI_CACHE_DIR', str(tmp_path / 'cache'))
    calls = []
    def fake_provider(api_key, voice_id, text, timeout):
        calls.append((api_key, voice_id, text))
        return _fake_pcm()
    monkeypatch.setitem(vk.AI_PROVIDERS, 'elevenlabs', fake_provider)

    path = vk.synthesize_to_wav_ai('CQ Contest, F4GLD', 'elevenlabs', 'sk-abc', 'v1')
    assert path and os.path.exists(path)
    assert calls == [('sk-abc', 'v1', 'CQ Contest, F4GLD')]

    cache_path = vk._ai_cache_path('elevenlabs', 'v1', 'CQ Contest, F4GLD')
    assert os.path.exists(cache_path)
    assert path != cache_path            # copie jetable, jamais le fichier de cache lui-même
    import wave
    with wave.open(path, 'rb') as wf:
        assert wf.getnchannels() == 1 and wf.getframerate() == 24000


def test_synthesize_to_wav_ai_cache_hit_ne_rappelle_jamais_le_fournisseur(monkeypatch, tmp_path):
    monkeypatch.setattr(vk, '_AI_CACHE_DIR', str(tmp_path / 'cache'))
    def boom(*a, **k):
        raise AssertionError('le fournisseur ne doit pas être rappelé sur un cache hit')
    monkeypatch.setitem(vk.AI_PROVIDERS, 'elevenlabs', boom)

    cache_path = vk._ai_cache_path('elevenlabs', 'v1', 'CQ Contest, F4GLD')
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    vk._write_wav_from_pcm(cache_path, _fake_pcm())
    cache_mtime = os.path.getmtime(cache_path)

    path = vk.synthesize_to_wav_ai('CQ Contest, F4GLD', 'elevenlabs', 'sk-abc', 'v1')
    assert path and path != cache_path
    assert os.path.getmtime(cache_path) == cache_mtime   # jamais réécrit


def test_synthesize_to_wav_ai_echec_fournisseur_rend_none_et_ne_cree_pas_le_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(vk, '_AI_CACHE_DIR', str(tmp_path / 'cache'))
    monkeypatch.setitem(vk.AI_PROVIDERS, 'elevenlabs', lambda *a, **k: None)

    path = vk.synthesize_to_wav_ai('CQ test', 'elevenlabs', 'sk-abc', 'v1')
    assert path is None
    assert not os.path.exists(vk._ai_cache_path('elevenlabs', 'v1', 'CQ test'))


# ─── synthesize_to_wav() : priorité IA + repli local silencieux ───────────────
# Un vrai pyttsx3/SAPI5 n'est PAS mocké ailleurs dans ce fichier (les tests
# send_voice_message monkeypatchent synthesize_to_wav ENTIÈREMENT) — ici on a
# besoin du VRAI corps de la fonction pour tester le dispatch IA -> local, donc
# on injecte un faux module pyttsx3 dans sys.modules : rapide, silencieux,
# fonctionne même sur une machine sans moteur SAPI5 installé (CI Linux/macOS).
class _FakePyttsx3Engine:
    def __init__(self):
        self._voice = None
        self._rate = None
    def getProperty(self, name):
        return [] if name == 'voices' else None
    def setProperty(self, name, val):
        pass
    def save_to_file(self, text, path):
        with open(path, 'wb') as f:
            f.write(b'RIFF....WAVEfmt ' + b'\x00' * 100)   # > 100 octets : passe le controle anti-echec-silencieux
    def runAndWait(self):
        pass
    def stop(self):
        pass


def _install_fake_pyttsx3(monkeypatch):
    import sys as _sys
    import types as _types
    fake = _types.ModuleType('pyttsx3')
    fake.init = lambda: _FakePyttsx3Engine()
    monkeypatch.setitem(_sys.modules, 'pyttsx3', fake)


def test_synthesize_to_wav_sans_ai_ne_touche_jamais_synthesize_to_wav_ai(monkeypatch):
    """Comportement inchangé pour tout appelant existant qui n'a jamais
    connu ce paramètre (contrat rétro-compatible)."""
    def boom(*a, **k):
        raise AssertionError('synthesize_to_wav_ai ne doit pas être appelé sans ai=')
    monkeypatch.setattr(vk, 'synthesize_to_wav_ai', boom)
    monkeypatch.setattr(vk, '_voice_id_for_lang', lambda engine, lang: None)
    _install_fake_pyttsx3(monkeypatch)
    path = vk.synthesize_to_wav('CQ test')     # pas de kwarg ai= du tout
    assert path and os.path.exists(path)


def test_synthesize_to_wav_ai_desactivee_ne_lappelle_pas(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('synthesize_to_wav_ai ne doit pas être appelé si ai.enabled est faux')
    monkeypatch.setattr(vk, 'synthesize_to_wav_ai', boom)
    monkeypatch.setattr(vk, '_voice_id_for_lang', lambda engine, lang: None)
    _install_fake_pyttsx3(monkeypatch)
    path = vk.synthesize_to_wav('CQ test', ai={'enabled': False})
    assert path and os.path.exists(path)


def test_synthesize_to_wav_essaie_lia_en_priorite(monkeypatch, tmp_path):
    fake_ai_wav = tmp_path / 'ai.wav'
    fake_ai_wav.write_bytes(b'RIFF....WAVEfmt ' + b'\x00' * 100)
    monkeypatch.setattr(vk, 'synthesize_to_wav_ai', lambda *a, **k: str(fake_ai_wav))
    path = vk.synthesize_to_wav('CQ test', ai={'enabled': True, 'provider': 'elevenlabs',
                                               'api_key': 'sk-abc', 'voice_id': 'v1'})
    assert path == str(fake_ai_wav)


def test_synthesize_to_wav_repli_local_silencieux_si_lia_echoue(monkeypatch, capsys):
    """C'est LE point central de la fonctionnalité : un fournisseur IA
    injoignable/mal configuré ne doit JAMAIS empêcher le keyer vocal de
    fonctionner — le concours ne dépend jamais du réseau (retour F4GLD
    04/08/2026)."""
    monkeypatch.setattr(vk, 'synthesize_to_wav_ai', lambda *a, **k: None)
    monkeypatch.setattr(vk, '_voice_id_for_lang', lambda engine, lang: None)
    _install_fake_pyttsx3(monkeypatch)
    path = vk.synthesize_to_wav('CQ test', ai={'enabled': True, 'provider': 'elevenlabs',
                                               'api_key': 'sk-abc', 'voice_id': 'v1'})
    assert path and os.path.exists(path)
    assert 'Voix IA indisponible' in capsys.readouterr().out


def test_set_ptt_dispatch_rien_active(monkeypatch):
    import logx_cat as cat
    import logx_rig as rig
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': False, 'mode': 'native'})
    monkeypatch.setattr(rig, 'rig_settings', lambda cfg: {'enabled': False, 'host': '', 'port': 0})
    r = vk._set_ptt({}, True)
    assert not r['ok'] and 'désactivé' in r['error'].lower()


# ─── voicekeyer_settings() : sous-dict 'piper' ────────────────────────────────

def test_voicekeyer_settings_piper_par_defaut_desactive():
    s = vk.voicekeyer_settings({'voicekeyer_enabled': True})
    assert s['piper'] == {'enabled': False, 'exe': 'piper', 'model': ''}


def test_voicekeyer_settings_piper_configure():
    s = vk.voicekeyer_settings({
        'voicekeyer_piper_enabled': True, 'voicekeyer_piper_exe': 'C:\\piper\\piper.exe',
        'voicekeyer_piper_model': 'C:\\piper\\voices\\fr_FR-siwis-medium.onnx'})
    assert s['piper'] == {'enabled': True, 'exe': 'C:\\piper\\piper.exe',
                          'model': 'C:\\piper\\voices\\fr_FR-siwis-medium.onnx'}


# ─── synthesize_to_wav_piper() : sous-processus, jamais d'exception ───────────
# Jamais de vrai Piper installé dans ces tests : subprocess.run est monkeypatché.

def test_synthesize_to_wav_piper_sans_modele_rend_none_sans_lancer_de_processus(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('subprocess.run ne doit pas être appelé sans modèle configuré')
    monkeypatch.setattr(vk.subprocess, 'run', boom)
    assert vk.synthesize_to_wav_piper('CQ test', 'piper', '') is None


def test_synthesize_to_wav_piper_succes(monkeypatch, tmp_path):
    captured = {}
    def fake_run(cmd, input=None, capture_output=None, timeout=None):
        captured['cmd'] = cmd
        captured['input'] = input
        # Piper écrit le WAV à l'emplacement --output_file passé par la fonction.
        out_path = cmd[cmd.index('--output_file') + 1]
        with open(out_path, 'wb') as f:
            f.write(b'RIFF....WAVEfmt ' + b'\x00' * 100)
        class R: returncode = 0
        return R()
    monkeypatch.setattr(vk.subprocess, 'run', fake_run)

    path = vk.synthesize_to_wav_piper('CQ Contest, F4GLD', 'piper', str(tmp_path / 'fr.onnx'))
    assert path and os.path.exists(path)
    assert captured['input'] == 'CQ Contest, F4GLD'.encode('utf-8')
    assert '--model' in captured['cmd'] and str(tmp_path / 'fr.onnx') in captured['cmd']


def test_synthesize_to_wav_piper_echec_retour_non_zero_rend_none(monkeypatch, tmp_path):
    def fake_run(cmd, input=None, capture_output=None, timeout=None):
        class R: returncode = 1
        return R()
    monkeypatch.setattr(vk.subprocess, 'run', fake_run)
    assert vk.synthesize_to_wav_piper('CQ test', 'piper', str(tmp_path / 'fr.onnx')) is None


def test_synthesize_to_wav_piper_executable_introuvable_rend_none(monkeypatch, tmp_path):
    def fake_run(cmd, input=None, capture_output=None, timeout=None):
        raise FileNotFoundError('piper introuvable')
    monkeypatch.setattr(vk.subprocess, 'run', fake_run)
    assert vk.synthesize_to_wav_piper('CQ test', 'piper', str(tmp_path / 'fr.onnx')) is None


def test_synthesize_to_wav_piper_timeout_rend_none(monkeypatch, tmp_path):
    def fake_run(cmd, input=None, capture_output=None, timeout=None):
        raise vk.subprocess.TimeoutExpired(cmd, timeout)
    monkeypatch.setattr(vk.subprocess, 'run', fake_run)
    assert vk.synthesize_to_wav_piper('CQ test', 'piper', str(tmp_path / 'fr.onnx')) is None


# ─── synthesize_to_wav() : Piper entre l'IA cloud et la voix locale ──────────

def test_synthesize_to_wav_piper_desactive_ne_lappelle_pas(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('synthesize_to_wav_piper ne doit pas être appelé si piper.enabled est faux')
    monkeypatch.setattr(vk, 'synthesize_to_wav_piper', boom)
    monkeypatch.setattr(vk, '_voice_id_for_lang', lambda engine, lang: None)
    _install_fake_pyttsx3(monkeypatch)
    path = vk.synthesize_to_wav('CQ test', piper={'enabled': False})
    assert path and os.path.exists(path)


def test_synthesize_to_wav_essaie_piper_apres_lia(monkeypatch, tmp_path):
    def boom_ai(*a, **k):
        raise AssertionError('ne doit pas être appelé : ai.enabled est faux ici')
    monkeypatch.setattr(vk, 'synthesize_to_wav_ai', boom_ai)
    fake_piper_wav = tmp_path / 'piper.wav'
    fake_piper_wav.write_bytes(b'RIFF....WAVEfmt ' + b'\x00' * 100)
    monkeypatch.setattr(vk, 'synthesize_to_wav_piper', lambda *a, **k: str(fake_piper_wav))
    path = vk.synthesize_to_wav('CQ test', piper={'enabled': True, 'exe': 'piper', 'model': 'x.onnx'})
    assert path == str(fake_piper_wav)


def test_synthesize_to_wav_repli_local_silencieux_si_piper_echoue(monkeypatch, capsys):
    """Même garantie que pour la voix IA cloud (voir
    test_synthesize_to_wav_repli_local_silencieux_si_lia_echoue) : Piper mal
    installé/configuré ne doit jamais empêcher le keyer vocal de fonctionner."""
    monkeypatch.setattr(vk, 'synthesize_to_wav_piper', lambda *a, **k: None)
    monkeypatch.setattr(vk, '_voice_id_for_lang', lambda engine, lang: None)
    _install_fake_pyttsx3(monkeypatch)
    path = vk.synthesize_to_wav('CQ test', piper={'enabled': True, 'exe': 'piper', 'model': 'x.onnx'})
    assert path and os.path.exists(path)
    assert 'Piper indisponible' in capsys.readouterr().out


# ─── expand_voice_segments() : synthèse MULTI-VOIX ────────────────────────────
# Retour F4GLD 04/08/2026 : une voix française unique pour tout le message
# lisait "fifty-nine" avec un accent français — la solution retenue est de
# synthétiser chaque segment de langue différente séparément (voir
# send_voice_message(segments=...)), donc de d'abord DÉCOUPER le message.

def test_expand_voice_segments_indicatif_allemand_quatre_segments(monkeypatch):
    """Reproduction exacte du cas signalé : {CALL} {DE} {MYCALL}, {RST_SENT}
    {TNX} avec un correspondant allemand -> alternance anglais/allemand,
    JAMAIS un seul segment fourre-tout."""
    _mock_country(monkeypatch, 'Fed. Rep. of Germany')
    segs = vk.expand_voice_segments('{CALL} {DE} {MYCALL}, {RST_SENT} {TNX}',
                                    {'call': 'DL1AA', 'mycall': 'F4GLD', 'rst_sent': '59'})
    assert segs == [
        ('Delta Lima One Alpha Alpha ', 'en'),
        ('von', 'de'),
        (' Foxtrot Four Golf Lima Delta, fifty-nine ', 'en'),
        ('dreiundsiebzig danke', 'de'),
    ]


def test_expand_voice_segments_sans_placeholder_un_seul_segment_anglais():
    assert vk.expand_voice_segments('CQ Contest, F4GLD', {}) == \
        [('CQ Contest, F4GLD', 'en')]


def test_expand_voice_segments_fusionne_les_segments_adjacents_meme_langue(monkeypatch):
    """{DE} et {TNX} sont tous les deux dans la langue dérivée et directement
    accolés (aucun texte littéral entre les deux) : ils doivent former UN
    SEUL segment, pas deux (évite un aller-retour de voix inutile pour
    rien). Le texte littéral, lui, reste toujours 'en' (voir docstring de
    expand_voice_segments) — un espace entre deux placeholders 'fr' casse
    donc la fusion, ce n'est pas un bug."""
    _mock_country(monkeypatch, 'France')
    segs = vk.expand_voice_segments('{DE}{TNX}', {'call': 'F5ABC'})
    assert len(segs) == 1 and segs[0][1] == 'fr'


def test_expand_voice_segments_reponse_reste_un_seul_segment_anglais(monkeypatch):
    """La macro RÉPONSE ('{CALL}') est déjà un seul segment 'en' que le
    correspondant soit français ou non — {CALL} n'est jamais localisé."""
    _mock_country(monkeypatch, 'France')
    assert vk.expand_voice_segments('{CALL}', {'call': 'F5ABC'}) == \
        [('Foxtrot Five Alpha Bravo Charlie', 'en')]


# ─── _voice_matches_lang() / résolution de voix par segment ──────────────────

class _FakeVoice:
    def __init__(self, id_, name, languages=None):
        self.id = id_
        self.name = name
        self.languages = languages or []


class _FakeEngineMultiVoix:
    """Moteur SAPI factice avec DEUX voix installées (française et
    anglaise), pour vérifier que le bon segment reçoit la bonne voix —
    sans dépendre d'un vrai moteur multilingue sur la machine de test."""
    def __init__(self):
        self._voice = None
        self._voices = [
            _FakeVoice('HKEY\\...\\FR-Hortense', 'Microsoft Hortense Desktop - French'),
            _FakeVoice('HKEY\\...\\EN-Zira', 'Microsoft Zira Desktop - English (United States)'),
        ]
        self.saved_with_voice = []
    def getProperty(self, name):
        if name == 'voices':
            return self._voices
        return self._voice
    def setProperty(self, name, val):
        if name == 'voice':
            self._voice = val
    def save_to_file(self, text, path):
        self.saved_with_voice.append((text, self._voice))
        with open(path, 'wb') as f:
            f.write(b'RIFF....WAVEfmt ' + b'\x00' * 100)
    def runAndWait(self):
        pass
    def stop(self):
        pass


def _install_fake_pyttsx3_multivoix(monkeypatch):
    import sys as _sys
    import types as _types
    engine = _FakeEngineMultiVoix()
    fake = _types.ModuleType('pyttsx3')
    fake.init = lambda: engine
    monkeypatch.setitem(_sys.modules, 'pyttsx3', fake)
    return engine


def test_voice_matches_lang_vrai_si_la_voix_correspond():
    engine = _FakeEngineMultiVoix()
    assert vk._voice_matches_lang(engine, 'HKEY\\...\\FR-Hortense', 'fr') is True


def test_voice_matches_lang_faux_si_la_voix_est_dune_autre_langue():
    engine = _FakeEngineMultiVoix()
    assert vk._voice_matches_lang(engine, 'HKEY\\...\\FR-Hortense', 'en') is False


def test_voice_matches_lang_vrai_sans_langue_demandee():
    engine = _FakeEngineMultiVoix()
    assert vk._voice_matches_lang(engine, 'HKEY\\...\\FR-Hortense', '') is True


def test_synthesize_to_wav_ignore_la_voix_config_si_elle_ne_correspond_pas_a_la_langue(monkeypatch):
    """LE cœur du correctif : une voix française configurée en CONFIG ne
    doit PAS servir à lire un segment 'en' quand une voix anglaise est
    installée — retour F4GLD 04/08/2026 (« fifty-nine » lu à la française)."""
    engine = _install_fake_pyttsx3_multivoix(monkeypatch)
    vk.synthesize_to_wav('fifty-nine', voice_id='HKEY\\...\\FR-Hortense', lang='en')
    assert engine.saved_with_voice[-1][1] == 'HKEY\\...\\EN-Zira'


def test_synthesize_to_wav_utilise_la_voix_config_si_elle_correspond(monkeypatch):
    engine = _install_fake_pyttsx3_multivoix(monkeypatch)
    vk.synthesize_to_wav('von', voice_id='HKEY\\...\\FR-Hortense', lang='fr')
    assert engine.saved_with_voice[-1][1] == 'HKEY\\...\\FR-Hortense'


def test_synthesize_to_wav_repli_sur_voix_config_si_aucune_voix_ne_correspond_a_la_langue(monkeypatch):
    """Aucune voix japonaise installée : mieux vaut la voix française
    configurée (même mal assortie) qu'un silence complet."""
    engine = _install_fake_pyttsx3_multivoix(monkeypatch)
    vk.synthesize_to_wav('kara', voice_id='HKEY\\...\\FR-Hortense', lang='ja')
    assert engine.saved_with_voice[-1][1] == 'HKEY\\...\\FR-Hortense'


# ─── send_voice_message(segments=...) : synthèse + lecture MULTI-VOIX ────────

def test_send_voice_message_segments_synthetise_et_joue_chaque_segment_dans_lordre(monkeypatch, tmp_path):
    calls = []
    def fake_synth(text, voice_id='', rate=175, lang='', ai=None, piper=None):
        p = tmp_path / f'{lang}_{len(calls)}.wav'
        p.write_bytes(b'RIFF....WAVEfmt ')
        calls.append((text, lang))
        return str(p)
    played = []
    ptt_calls = []
    monkeypatch.setattr(vk, 'synthesize_to_wav', fake_synth)
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: ptt_calls.append(on) or {'ok': True})
    monkeypatch.setattr(vk, 'play_wav', lambda path, device=None: played.append(path))

    segments = [('Delta Lima One Alpha Alpha ', 'en'), ('von', 'de'),
               (' Foxtrot Four Golf Lima Delta, fifty-nine ', 'en'),
               ('dreiundsiebzig danke', 'de')]
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'texte complet affiché',
                              segments=segments)
    assert r['ok'] and r['text'] == 'texte complet affiché'
    assert [lang for _, lang in calls] == ['en', 'de', 'en', 'de']
    assert len(played) == 4                # un play_wav() par segment, dans l'ordre
    assert ptt_calls == [True, False]       # UNE SEULE prise de PTT pour tout le message
    for p in played:
        assert not os.path.exists(p)        # tous les WAV temporaires nettoyés


def test_send_voice_message_segments_echec_dun_segment_nettoie_les_precedents(monkeypatch, tmp_path):
    """Si le 2e segment échoue, le WAV déjà synthétisé pour le 1er ne doit
    pas traîner sur le disque."""
    made = []
    def fake_synth(text, voice_id='', rate=175, lang='', ai=None, piper=None):
        if lang == 'de':
            return None
        p = tmp_path / f'seg_{len(made)}.wav'
        p.write_bytes(b'RIFF....WAVEfmt ')
        made.append(str(p))
        return str(p)
    monkeypatch.setattr(vk, 'synthesize_to_wav', fake_synth)

    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'texte',
                              segments=[('abc', 'en'), ('von', 'de')])
    assert not r['ok'] and 'indisponible' in r['error'].lower()
    for p in made:
        assert not os.path.exists(p)


def test_send_voice_message_sans_segments_comportement_inchange(monkeypatch, tmp_path):
    """Omettre `segments` (appelants existants, jamais mis à jour) doit
    rester STRICTEMENT identique à avant ce correctif."""
    fake_wav = tmp_path / 'single.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    played = []
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: {'ok': True})
    monkeypatch.setattr(vk, 'play_wav', lambda path, device=None: played.append(path))
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test')
    assert r['ok'] and played == [str(fake_wav)]


# ─── emettre_wav_multi() : lecture séquentielle sous un seul PTT ─────────────

def test_emettre_wav_multi_joue_tout_sous_un_seul_ptt(monkeypatch, tmp_path):
    a, b = tmp_path / 'a.wav', tmp_path / 'b.wav'
    a.write_bytes(b'RIFF....WAVEfmt ')
    b.write_bytes(b'RIFF....WAVEfmt ')
    played = []
    ptt_calls = []
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: ptt_calls.append(on) or {'ok': True})
    monkeypatch.setattr(vk, 'play_wav', lambda path, device=None: played.append(path))
    r = vk.emettre_wav_multi({}, [str(a), str(b)], None, supprimer_apres=True)
    assert r['ok']
    assert played == [str(a), str(b)]
    assert ptt_calls == [True, False]
    assert not a.exists() and not b.exists()


def test_emettre_wav_delegue_a_emettre_wav_multi(monkeypatch, tmp_path):
    """emettre_wav() (1 seul fichier) doit rester identique à son ancien
    comportement — non-régression après son refactor en fine couche
    au-dessus de emettre_wav_multi()."""
    fake_wav = tmp_path / 'x.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    played = []
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: {'ok': True})
    monkeypatch.setattr(vk, 'play_wav', lambda path, device=None: played.append(path))
    r = vk.emettre_wav({}, str(fake_wav), None, supprimer_apres=True)
    assert r['ok'] and played == [str(fake_wav)] and not fake_wav.exists()


# ─── _trim_silence_wav() : rogne le silence de tête/fin d'un clip TTS ────────
# Corrige les 2 pauses parasites entourant {DE} en synthèse multi-segments
# (chaque segment est un WAV séparé, joué à la suite — voir emettre_wav_multi
# et le docstring de _trim_silence_wav) — retour F4GLD 04/08/2026.

import wave as _wave_mod


def _ecrire_wav(path, frames, framerate=16000, sampwidth=2, nchannels=1):
    with _wave_mod.open(str(path), 'wb') as wf:
        wf.setnchannels(nchannels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(framerate)
        wf.writeframes(frames)


def _lire_wav_amplitudes(path):
    import array
    with _wave_mod.open(str(path), 'rb') as wf:
        raw = wf.readframes(wf.getnframes())
    a = array.array('h')
    a.frombytes(raw)
    return list(a)


def test_trim_silence_wav_rogne_le_silence_de_tete_et_fin(tmp_path):
    """500 échantillons de silence + 1000 de "son" (amplitude max) + 500 de
    silence -> après rognage, quasi plus de silence de tête/fin (juste la
    petite marge anti-clic), le son central reste intact."""
    p = tmp_path / 'clip.wav'
    silence = bytes(2 * 500)          # int16 = 0 -> silence
    son = (30000).to_bytes(2, 'little', signed=True) * 1000
    _ecrire_wav(p, silence + son + silence)
    avant = _lire_wav_amplitudes(p)
    assert len(avant) == 2000

    vk._trim_silence_wav(p)
    apres = _lire_wav_amplitudes(p)
    assert len(apres) < len(avant), 'le silence aurait du etre rogne'
    assert 30000 in apres, 'le son au centre ne doit jamais etre coupe'
    # Marge de 25ms par defaut a 16000 Hz = 400 echantillons de chaque cote
    # au maximum garde autour du son detecte -> largement moins que les 2000
    # d'origine (2 x 500 de silence), mais le son central (1000) reste entier.
    assert len(apres) < 2000
    assert len(apres) >= 1000


def test_trim_silence_wav_fichier_entierement_silencieux_ne_plante_pas(tmp_path):
    p = tmp_path / 'silence.wav'
    _ecrire_wav(p, bytes(2 * 1000))
    taille_avant = p.stat().st_size
    vk._trim_silence_wav(p)   # ne doit jamais lever
    assert p.stat().st_size == taille_avant, 'rien a rogner : fichier inchange'


def test_trim_silence_wav_fichier_illisible_ne_plante_pas(tmp_path):
    p = tmp_path / 'pas_un_wav.wav'
    p.write_bytes(b'ceci n est pas un wav valide')
    vk._trim_silence_wav(p)   # ne doit jamais lever
    assert p.read_bytes() == b'ceci n est pas un wav valide', 'fichier illisible : inchange'


def test_trim_silence_wav_deja_sans_silence_ne_touche_a_rien(tmp_path):
    """Signal qui commence et finit déjà par du son (pas de silence à
    rogner) : le fichier ne doit pas être réécrit inutilement."""
    p = tmp_path / 'plein.wav'
    son = (30000).to_bytes(2, 'little', signed=True) * 200
    _ecrire_wav(p, son)
    avant = p.read_bytes()
    vk._trim_silence_wav(p)
    assert p.read_bytes() == avant


def test_synthesize_to_wav_rogne_le_silence_pyttsx3(monkeypatch, tmp_path):
    """synthesize_to_wav() (chemin pyttsx3) doit appeler _trim_silence_wav()
    sur le fichier produit — garde-fou de câblage : facile d'ajouter un
    nouveau moteur/retour sans reporter l'appel."""
    appeles = []
    monkeypatch.setattr(vk, '_trim_silence_wav', lambda path: appeles.append(path))

    class _FakeEngine:
        def setProperty(self, *a, **k): pass
        def getProperty(self, *a, **k): return []
        def save_to_file(self, text, path):
            with open(path, 'wb') as f:
                f.write(b'x' * 200)   # > 100 octets -> pas traite comme un echec SAPI5
        def runAndWait(self): pass
        def stop(self): pass

    import types
    fake_pyttsx3 = types.SimpleNamespace(init=lambda: _FakeEngine())
    monkeypatch.setitem(sys.modules, 'pyttsx3', fake_pyttsx3)

    path = vk.synthesize_to_wav('test', ai={'enabled': False}, piper={'enabled': False})
    assert path is not None
    assert appeles == [path]
    os.remove(path)
