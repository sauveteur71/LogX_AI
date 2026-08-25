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


# ─── Import depuis d'AUTRES logiciels de log (N1MM+/Win-Test/DXLog/Log4OM) ────
# Objectif produit (07/08/2026) : abaisser le coût de changer de logiciel —
# le frein réel n'est presque jamais la qualité de LogX AI, c'est la peur de
# perdre son historique. Ces tests figent le comportement sur des exports
# construits pour reproduire des conventions RÉELLES de ces logiciels (pas
# des ADIF génériques déjà couverts plus haut).

def test_import_mode_ph_win_test_normalise_en_ssb():
    """"PH" (convention Cabrillo, reprise par certains exports Win-Test) doit
    être compris comme un synonyme de SSB — sinon le QSO importé porte un
    mode que le reste de l'appli (filtres bande/mode, scoring, export
    Cabrillo/ADIF) ne reconnaît pas comme de la phonie."""
    adif = ("<CALL:5>DL1AA<BAND:3>20m<MODE:2>PH<QSO_DATE:8>20260101"
            "<TIME_ON:4>1200<EOR>")
    qsos, errors = imp.parse_adif_to_qsos(adif)
    assert not errors
    assert qsos[0]['mode'] == 'SSB'


def test_import_mode_ph_ne_declenche_plus_lavertissement_mode_inconnu():
    """Corollaire du test précédent : une fois normalisé en SSB (mode ADIF
    officiel), ce QSO ne doit plus remonter dans mode_warnings — "PH" n'est
    plus un mode "inconnu", c'est un synonyme reconnu."""
    adif = ("<CALL:5>DL1AA<BAND:3>20m<MODE:2>PH<QSO_DATE:8>20260101"
            "<TIME_ON:4>1200<EOR>")
    p = imp.preview_import(adif, existing_log=[])
    assert p['mode_warnings'] == []


def test_import_dxlog_sans_tag_band_derive_depuis_freq():
    """DXLog.net (comme d'autres) peut exporter FREQ sans le tag BAND — déjà
    géré par _band_from_record (partagé avec logx_qsl), verrouillé ici du
    point de vue de l'import complet plutôt que de la seule fonction bande."""
    adif = ("<CALL:5>K1ABC<FREQ:6>14.250<MODE:3>SSB<QSO_DATE:8>20260101"
            "<TIME_ON:4>1500<EOR>")
    qsos, errors = imp.parse_adif_to_qsos(adif)
    assert not errors
    assert qsos[0]['band'] == '14'


def test_import_n1mm_tags_proprietaires_app_preserves_dans_extra_fields():
    """N1MM+ (et d'autres) ajoutent des tags APP_<PROGRAMME>_* propriétaires
    dans leurs exports ADIF — ni mappés vers un champ interne connu, ni
    perdus : préservés dans extra_fields pour un aller-retour fidèle."""
    adif = ("<CALL:4>W1AW<BAND:3>40m<MODE:2>CW<QSO_DATE:8>20260101"
            "<TIME_ON:4>0800<APP_N1MM_EXCHANGE1:3>599<APP_N1MM_RUN1RUN2:1>1"
            "<PROGRAMID:4>N1MM<EOR>")
    qsos, errors = imp.parse_adif_to_qsos(adif)
    assert not errors
    extras = qsos[0].get('extra_fields', {})
    assert extras.get('APP_N1MM_EXCHANGE1') == '599'
    assert extras.get('APP_N1MM_RUN1RUN2') == '1'
    # PROGRAMID est explicitement mappé (_TAGS_MAPPES) : jamais dupliqué
    # dans extra_fields.
    assert 'PROGRAMID' not in extras


def test_import_log4om_stx_srx_numeriques_sans_les_variantes_string():
    """Certains logiciels (dont Log4OM selon la config) exportent STX/SRX
    (entiers) plutôt que STX_STRING/SRX_STRING (texte) — les deux doivent
    être lus, pas seulement la variante _STRING déjà testée plus haut."""
    adif = ("<CALL:5>F4ABC<BAND:2>2m<MODE:3>SSB<QSO_DATE:8>20260101"
            "<TIME_ON:4>0900<STX:3>012<SRX:3>034<EOR>")
    qsos, errors = imp.parse_adif_to_qsos(adif)
    assert not errors
    assert qsos[0]['num_sent'] == '012' and qsos[0]['num_rcvd'] == '034'


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
    """60m (5.06-5.45 MHz) est désormais une BANDE INTERNE de plein droit ('5',
    décision F4GLD 25/08). Un QSO FREQ=5.330 sans champ BAND doit rester
    importable ET tomber sur la bande interne '5' (auparavant 60m n'était pas
    interne et ressortait en libellé ADIF brut '60m')."""
    adif = ("<CALL:5>N0CDX<FREQ:5>5.330<MODE:2>CW<QSO_DATE:8>20260710"
           "<TIME_ON:4>1230<EOR>\n")
    qsos, errors = imp.parse_adif_to_qsos(adif)
    assert len(qsos) == 1 and not errors
    assert qsos[0]['band'] == '5'


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


# ─── UNICITÉ DES id DE QSO (bug critique : import qui vole des id futurs) ────
# `q['id'] = int(now * 1000) + i` faisait consommer à un import de N QSO N
# millisecondes d'espace d'id, c'est-à-dire N/1000 SECONDES d'id FUTURS, dans
# le MÊME espace que l'allocateur des QSO saisis en direct. Conséquences
# vérifiées : /log/delete filtre `q['id'] != qso_id` et effaçait donc plusieurs
# QSO d'un coup ; /log/update remplace le PREMIER porteur de l'id et corrigeait
# un QSO qui n'avait rien à voir en laissant la vraie cible fausse ; et
# logx_cloudsync fusionne les logs des postes par id.

def _adif_bloc(prefixe, n, date='20260710'):
    """n records ADIF valides et tous distincts (pas de dédup parasite)."""
    out = []
    for i in range(n):
        call = f'{prefixe}{i:04d}'
        out.append(f"<CALL:{len(call)}>{call}<BAND:3>20m<MODE:2>CW"
                   f"<QSO_DATE:8>{date}<TIME_ON:6>{i // 3600:02d}"
                   f"{(i // 60) % 60:02d}{i % 60:02d}<EOR>")
    return '\n'.join(out) + '\n'


def test_import_ne_reutilise_jamais_un_id_deja_present_dans_le_log():
    """Un import précédent avait réservé 1 000 id (dont des id FUTURS) : le
    suivant doit numéroter AU-DESSUS, pas repartir de l'horloge."""
    import time as _t
    now_ms = int(_t.time() * 1000)
    deja = [{'call': f'W1A{i:04d}', 'band': '14', 'mode': 'CW',
             'date': '20200101', 'time': '0000', 'id': now_ms + i}
            for i in range(1000)]
    neufs, _ = imp.commit_import(_adif_bloc('K2B', 5), existing_log=deja)
    assert len(neufs) == 5
    assert min(q['id'] for q in neufs) > max(q['id'] for q in deja)


def test_deux_imports_successifs_ne_partagent_aucun_id():
    """Cas le plus banal qui soit : deux fichiers ADIF importés à la suite
    (deux sources différentes, ou une simple re-tentative). Avant le
    correctif, les deux blocs se recouvraient à ~90 % — collision GARANTIE,
    pas probabiliste, puisque les deux partent de l'horloge courante."""
    a, _ = imp.commit_import(_adif_bloc('F5A', 500), existing_log=[])
    b, _ = imp.commit_import(_adif_bloc('G3B', 500), existing_log=list(a))
    ids_a = {q['id'] for q in a}
    ids_b = {q['id'] for q in b}
    assert len(ids_a) == 500 and len(ids_b) == 500      # pas de doublon interne
    assert not (ids_a & ids_b), f"{len(ids_a & ids_b)} id en collision"


def test_import_numerote_sans_trou_malgre_les_doublons_ignores():
    """La numérotation suit le rang des QSO RETENUS, pas l'indice de boucle :
    les doublons sautés ne doivent pas creuser de trous d'id (c'est ce qui
    faisait consommer de l'espace d'id pour rien)."""
    adif = _adif_bloc('F5A', 4)
    deja = [{'call': 'F5A0001', 'band': '14', 'mode': 'CW',
             'date': '20260710', 'time': '0000'}]
    neufs, _ = imp.commit_import(adif, existing_log=deja)
    ids = sorted(q['id'] for q in neufs)
    assert len(neufs) == 3
    assert ids == list(range(ids[0], ids[0] + 3))


def test_qso_saisi_apres_un_import_ne_recoit_pas_un_id_deja_pris(monkeypatch):
    """Le geste inaugural typique — importer son carnet ADIF avant une
    expédition — réservait N ms d'id FUTURS. Tout QSO logué pendant cette
    fenêtre (ici l'`id: Date.now()` que les pages client envoient elles-mêmes)
    portait un id DÉJÀ attribué à un QSO importé : /log/delete sur ce QSO en
    effaçait deux, dont un QSO d'archive que personne n'avait demandé à
    supprimer, et le serveur répondait {'ok': True}."""
    import time as _t
    import logx_http as http
    now_ms = int(_t.time() * 1000)
    log = [{'call': f'F5A{i:04d}', 'band': '14', 'mode': 'CW', 'contest': '',
            'date': '20200101', 'time': '00:00', 'id': now_ms + i}
           for i in range(3000)]           # import de 3 000 QSO = 3 s d'id futurs
    monkeypatch.setattr(http, 'shared_log', log)
    monkeypatch.setattr(http, 'save_log_to_disk', lambda effacement_autorise=False: None)
    monkeypatch.setattr(http, 'current_config', {'usage_mode': 'simple'})
    ok, _info = http.add_qso_to_log({'call': 'G0LIVE', 'band': '14',
                                     'mode': 'SSB', 'contest': '',
                                     'date': '20260710', 'time': '12:00',
                                     'id': int(_t.time() * 1000)})
    assert ok
    live = next(q for q in log if q['call'] == 'G0LIVE')
    # La cause : l'id du QSO live n'est porté que par lui.
    assert sum(1 for q in log if q.get('id') == live['id']) == 1
    # La conséquence : /log/delete (même filtre que le handler) n'efface qu'un
    # seul QSO, et aucun QSO importé ne disparaît au passage.
    restant = [q for q in log if q.get('id') != live['id']]
    assert len(restant) == len(log) - 1
    # Et l'invariant global : aucun id dupliqué nulle part dans le log.
    ids = [q.get('id') for q in log]
    assert len(ids) == len(set(ids))
