# -*- coding: utf-8 -*-
"""Import ADIF (logx_import) : le log5 précédent poussait les QSO
importés dans une variable JS locale qui disparaissait au polling suivant
(jamais envoyé au serveur) — ce module est la persistance réelle, testée
sans aucun I/O (parse_adif_to_qsos/preview_import sont pures)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_import as imp

ADIF = (
    "En-tête de log ADIF\n<adif_ver:5>3.1.4<programid:12>LogX<EOH>\n"
    "<CALL:5>DL1AA<BAND:2>2m<MODE:3>SSB<QSO_DATE:8>20260710<TIME_ON:4>1230"
    "<GRIDSQUARE:6>JO40AA<MY_GRIDSQUARE:6>JN15XC<RST_SENT:2>59<RST_RCVD:2>59"
    "<STX_STRING:3>001<SRX_STRING:3>045<EOR>\n"
    "<CALL:5>F5XXX<BAND:3>20m<MODE:2>CW<QSO_DATE:8>20260711<TIME_ON:6>081500"
    "<RST_SENT:3>599<RST_RCVD:3>599<EOR>\n"
    "<CALL:0><BAND:2>2m<MODE:3>SSB<QSO_DATE:8>20260710<TIME_ON:4>0900<EOR>\n"  # sans indicatif
    "<CALL:5>G4ZZZ<MODE:3>SSB<QSO_DATE:8>20260710<TIME_ON:4>1000<EOR>\n"        # sans bande ni fréquence
)


def test_parse_adif_to_qsos_champs_de_base():
    qsos, errors = imp.parse_adif_to_qsos(ADIF)
    assert len(qsos) == 2   # les 2 records invalides sont en erreur, pas silencieusement ignorés
    assert len(errors) == 2
    q = qsos[0]
    assert q['call'] == 'DL1AA' and q['band'] == '144' and q['mode'] == 'SSB'
    assert q['date'] == '20260710' and q['time'] == '1230'
    assert q['locator'] == 'JO40AA' and q['my_locator'] == 'JN15XC'
    assert q['num_sent'] == '001' and q['num_rcvd'] == '045'
    assert q['points'] == 0 and q['source'] == 'adif_import'


def test_parse_adif_bande_depuis_le_libelle_adif():
    qsos, _ = imp.parse_adif_to_qsos(ADIF)
    assert qsos[1]['call'] == 'F5XXX' and qsos[1]['band'] == '14'   # '20m' -> '14' MHz


def test_parse_adif_time_on_6_chiffres_tronque_a_4():
    qsos, _ = imp.parse_adif_to_qsos(ADIF)
    assert qsos[1]['time'] == '0815'


def test_preview_import_tout_neuf():
    p = imp.preview_import(ADIF, existing_log=[])
    assert p['ok'] and p['total_in_file'] == 2 and p['new'] == 2 and p['duplicates'] == 0
    assert len(p['errors']) == 2
    assert len(p['sample']) == 2


def test_preview_import_detecte_les_doublons_exacts():
    existing = [{'call': 'DL1AA', 'band': '144', 'mode': 'SSB',
                'date': '20260710', 'time': '1230'}]
    p = imp.preview_import(ADIF, existing_log=existing)
    assert p['new'] == 1 and p['duplicates'] == 1


def test_preview_import_meme_indicatif_bande_mais_date_differente_pas_doublon():
    """Un import historique doit pouvoir coexister avec un QSO existant sur
    le même indicatif/bande à une AUTRE date — seule l'égalité exacte
    (date+heure incluses) est un doublon d'import."""
    existing = [{'call': 'DL1AA', 'band': '144', 'mode': 'SSB',
                'date': '20200101', 'time': '0000'}]
    p = imp.preview_import(ADIF, existing_log=existing)
    assert p['new'] == 2 and p['duplicates'] == 0


def test_commit_import_retourne_les_qso_neufs_avec_id():
    new_qsos, errors = imp.commit_import(ADIF, existing_log=[])
    assert len(new_qsos) == 2
    assert all('id' in q and 'server_time' in q for q in new_qsos)
    assert len(errors) == 2


def test_commit_import_exclut_les_doublons_deja_dans_le_log():
    existing = [{'call': 'F5XXX', 'band': '14', 'mode': 'CW',
                'date': '20260711', 'time': '0815'}]
    new_qsos, _ = imp.commit_import(ADIF, existing_log=existing)
    assert len(new_qsos) == 1 and new_qsos[0]['call'] == 'DL1AA'


def test_commit_import_dedoublonne_aussi_a_l_interieur_du_fichier():
    """Le fichier importé lui-même contient un doublon exact -> une seule
    des deux occurrences doit être ajoutée."""
    doubled = ADIF + ("<CALL:5>DL1AA<BAND:2>2m<MODE:3>SSB<QSO_DATE:8>20260710"
                      "<TIME_ON:4>1230<RST_SENT:2>59<RST_RCVD:2>59<EOR>\n")
    new_qsos, _ = imp.commit_import(doubled, existing_log=[])
    calls = [q['call'] for q in new_qsos]
    assert calls.count('DL1AA') == 1


def test_adif_vide_ou_invalide_ne_leve_jamais():
    assert imp.parse_adif_to_qsos('') == ([], [])
    p = imp.preview_import('texte quelconque sans balises', existing_log=[])
    assert p['ok'] and p['total_in_file'] == 0


# ─── Validation ADIF 3.1.7 officielle (bandes rares + modes non standards) ──

def test_bande_rare_via_freq_sans_champ_band_nest_plus_rejetee():
    """60m (5.06-5.45 MHz) n'est pas l'une des ~19 bandes internes de l'app
    (aucun concours géré ne l'utilise), mais un QSO FREQ=5.330 sans champ
    BAND doit rester importable — avant le correctif, le repli fréquence->
    bande (12 bandes de concours) ne reconnaissait pas cette plage et le
    record était rejeté pour bande "non reconnue"."""
    adif = ("<CALL:5>N0CDX<FREQ:5>5.330<MODE:2>CW<QSO_DATE:8>20260710"
           "<TIME_ON:4>1230<EOR>\n")
    qsos, errors = imp.parse_adif_to_qsos(adif)
    assert len(qsos) == 1 and not errors
    assert qsos[0]['band'] == '60m'


def test_mode_non_standard_signale_mais_pas_bloquant():
    adif = ("<CALL:5>DL1AA<BAND:2>2m<MODE:6>BIDULE<QSO_DATE:8>20260710"
           "<TIME_ON:4>1230<EOR>\n")
    p = imp.preview_import(adif, existing_log=[])
    assert p['new'] == 1 and not p['errors']   # importé quand même, pas une erreur
    assert any('BIDULE' in w for w in p['mode_warnings'])


def test_mode_standard_ne_genere_aucun_avertissement():
    qsos, _ = imp.parse_adif_to_qsos(ADIF)   # SSB + CW, tous deux standards
    p = imp.preview_import(ADIF, existing_log=[])
    assert p['mode_warnings'] == []


def test_mode_ft4_reconnu_meme_comme_mode_racine():
    """WSJT-X et la plupart des loggers réels mettent souvent MODE=FT4
    directement (plutôt que MODE=MFSK;SUBMODE=FT4, la forme stricte de la
    spec) — les deux doivent être acceptés sans avertissement."""
    adif = ("<CALL:5>DL1AA<BAND:2>2m<MODE:3>FT4<QSO_DATE:8>20260710"
           "<TIME_ON:4>1230<EOR>\n")
    p = imp.preview_import(adif, existing_log=[])
    assert p['mode_warnings'] == []
