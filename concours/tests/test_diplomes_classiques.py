# -*- coding: utf-8 -*-
"""Diplômes classiques : WAZ, WAC, WAS, DXCC Challenge, VUCC, CQ DX Field.

DEMANDE UTILISATEUR : « le logiciel prend les états US, est-ce qu'on a prévu
des statistiques ? » Le panneau ne calculait que le DXCC et les départements
français.

LE POINT QUI SÉPARE LES SIX : cinq d'entre eux se calculent RÉTROACTIVEMENT sur
le carnet déjà enregistré — l'entité, la zone CQ et le continent se déduisent
de l'indicatif via cty.dat, le champ et le carré du locator déjà stocké.
Vérifié sur le log réel de la station (9 483 QSO) : 166 entités, 35/40 zones,
6/6 continents, 101 champs, 707 carrés, 435 cases entité×bande.

Le WAS fait exception, et c'est structurel : **l'état US ne se déduit de rien**.
Le découpage géographique des préfixes américains a disparu depuis longtemps —
un W6 peut habiter n'importe quel état. Il faut donc que l'information soit
saisie (annuaire) ou importée (ADIF LoTW/ClubLog). D'où `was_data`, qui permet
de distinguer « aucun état contacté » de « l'information n'est pas là » : sans
lui, l'écran afficherait 0/50 à un opérateur ayant travaillé les 50 états.
"""
import os
import sys


CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_awards as aw      # noqa: E402
import logx_import as imp     # noqa: E402


def _qso(call, band='14', mode='SSB', **extra):
    q = {'call': call, 'band': band, 'mode': mode,
         'date': '2026-01-01', 'time': '1200'}
    q.update(extra)
    return q


def _resume(qsos, monkeypatch, confirmations=None):
    """award_summary sans toucher aux fichiers du poste (archives, QSL)."""
    monkeypatch.setattr(aw, '_read_archives', lambda: [])
    monkeypatch.setattr(aw, '_read_qso_archive', lambda: [])
    monkeypatch.setattr(aw, '_load_confirmations', lambda: confirmations or {})
    aw.invalidate()
    return aw.award_summary(qsos)


# ─── Ce qui se calcule sur le carnet existant ────────────────────────────────

def test_waz_compte_les_zones_cq_deduites_de_l_indicatif(monkeypatch):
    """Aucune saisie supplémentaire : la zone vient de cty.dat."""
    a = _resume([_qso('W1ABC'), _qso('JA1XYZ'), _qso('VK3ZZZ')], monkeypatch)
    assert a['waz']['total'] == 40
    assert a['waz']['worked'] >= 3
    assert len(a['waz']['missing']) == 40 - a['waz']['worked']


def test_waz_itu_compte_les_zones_itu_deduites_de_l_indicatif(monkeypatch):
    """Même principe que le WAZ (CQ), mais sur les 90 zones ITU (RSGB) --
    découpage différent du monde, même source cty.dat (logx_dxcc.lookup()
    remonte déjà itu_zone, ajout de l'analyse concurrentielle du 10/08/2026)."""
    a = _resume([_qso('W1ABC'), _qso('JA1XYZ'), _qso('VK3ZZZ')], monkeypatch)
    assert a['waz_itu']['total'] == 90
    assert a['waz_itu']['worked'] >= 3
    assert len(a['waz_itu']['missing']) == 90 - a['waz_itu']['worked']


def test_waz_itu_et_waz_cq_restent_deux_champs_distincts(monkeypatch):
    """Vérifié via logx_dxcc.lookup() directement (pas une supposition) :
    W1ABC=zone CQ 5/ITU 8, JA1XYZ=CQ 25/ITU 45, VK3ZZZ=CQ 30/ITU 59 -- les
    deux découpages ne coïncident jamais sur ces 3 indicatifs. Si un futur
    refactor confondait accidentellement les deux champs (ex. réassigner
    itu_zone = cq_zone), ce test doit le détecter."""
    import logx_dxcc as dxcc
    for call in ('W1ABC', 'JA1XYZ', 'VK3ZZZ'):
        info = dxcc.lookup(call)
        assert info['cq_zone'] != info['itu_zone'], call


def test_wac_exclut_l_antarctique(monkeypatch):
    """cty.dat connaît le continent AN, mais le WAC se compte sur 6. L'inclure
    ferait afficher « 7/6 » — une régression qu'un total en dur ne montre pas."""
    a = _resume([_qso('W1ABC'), _qso('JA1XYZ')], monkeypatch)
    assert a['wac']['total'] == 6
    assert 'AN' not in aw.WAC_CONTINENTS
    assert a['wac']['worked'] <= 6


def test_dxcc_challenge_compte_les_cases_entite_x_bande(monkeypatch):
    """Le Challenge, c'est une case par couple entité × bande : le même pays
    sur deux bandes compte double."""
    a = _resume([_qso('W1ABC', band='14'), _qso('W1ABC', band='7'),
                 _qso('W1ABC', band='14', mode='CW')], monkeypatch)
    assert a['dxcc_challenge']['worked'] == 2, 'une seule entite, deux bandes'


def test_le_challenge_ignore_les_bandes_hors_perimetre(monkeypatch):
    """160 à 6 m seulement : un QSO en 144 MHz ne fait pas une case."""
    a = _resume([_qso('W1ABC', band='144')], monkeypatch)
    assert a['dxcc_challenge']['worked'] == 0
    assert '144' not in aw.CHALLENGE_BANDS


def test_vucc_et_dx_field_viennent_du_locator(monkeypatch):
    """Le carré (4 car.) et le champ (2 car.) sortent du locator déjà stocké.
    Mesuré sur le log réel : les locators font 4, 6 ou 8 caractères, il faut
    donc tronquer et non exiger une longueur exacte."""
    a = _resume([_qso('W1ABC', locator='JN18'), _qso('W1ABC', locator='JN18CX'),
                 _qso('K5XYZ', locator='KN23ID78'), _qso('JA1X', locator='PM95')],
                monkeypatch)
    assert a['vucc']['worked'] == 3, 'JN18 vu deux fois ne compte qu une'
    assert a['dx_field']['worked'] == 3   # JN, KN, PM


def test_vucc_est_aussi_detaille_par_bande(monkeypatch):
    """Le VUCC s'obtient bande par bande (100 carrés en 6 m, en 2 m…), pas en
    total toutes bandes confondues."""
    # Heures distinctes À DESSEIN : collect_all_qsos dédoublonne sur
    # call+bande+mode+date+heure, et deux QSO identiques à ce détail près
    # seraient fusionnés — le test mesurerait alors le dédoublonnage, pas le
    # comptage par bande.
    a = _resume([_qso('W1ABC', band='50', locator='JN18', time='1200'),
                 _qso('W1ABC', band='144', locator='JN18', time='1300'),
                 _qso('W1ABC', band='144', locator='JN19', time='1400')],
                monkeypatch)
    assert a['vucc']['per_band'] == {'144': 2, '50': 1}


def test_un_locator_trop_court_ne_fabrique_pas_de_carre(monkeypatch):
    a = _resume([_qso('W1ABC', locator='J'), _qso('K5XYZ', locator='')],
                monkeypatch)
    assert a['vucc']['worked'] == 0
    assert a['dx_field']['worked'] == 0


def test_dxcc_expose_total_et_manquants_comme_les_autres_diplomes(monkeypatch):
    """Constat de l'audit de conformité du 15/08/2026 : le DXCC était le seul
    diplôme classique à ne renvoyer que worked/confirmed, sans 'total' ni
    'missing' -- contrairement au WAZ (zones manquantes), au WAC (continents
    manquants) et au WAS (états manquants). Même patron _paire() appliqué ici,
    sur la liste d'entités de logx_dxcc.list_entities() (même source cty.dat
    que dxcc_country, donc les noms se recoupent exactement)."""
    a = _resume([_qso('W1ABC'), _qso('JA1XYZ'), _qso('VK3ZZZ')], monkeypatch)
    assert a['dxcc']['worked'] == 3
    assert a['dxcc']['total'] is not None and a['dxcc']['total'] > 300
    assert isinstance(a['dxcc']['missing'], list) and a['dxcc']['missing']
    import logx_dxcc as dxcc
    for call in ('W1ABC', 'JA1XYZ', 'VK3ZZZ'):
        pays = dxcc.lookup(call)['country']
        assert pays not in a['dxcc']['missing'], 'deja travaillee, pas manquante'


# ─── Confirmé vs travaillé ───────────────────────────────────────────────────

def test_le_confirme_se_compte_separement(monkeypatch):
    """Un diplôme ne s'obtient que sur les QSO CONFIRMÉS : les deux compteurs
    doivent rester distincts sur tous les diplômes, pas seulement le DXCC."""
    conf = {'W1ABC|14|SSB': {'lotw': True}}
    a = _resume([_qso('W1ABC', locator='FN42'), _qso('JA1XYZ', locator='PM95')],
                monkeypatch, confirmations=conf)
    for cle in ('waz', 'waz_itu', 'wac', 'dx_field', 'vucc', 'dxcc_challenge'):
        assert a[cle]['confirmed'] < a[cle]['worked'], cle
        assert a[cle]['confirmed'] >= 1, cle


# ─── WAS : le cas à part ─────────────────────────────────────────────────────

def test_sans_etat_renseigne_on_le_DIT_au_lieu_d_afficher_zero(monkeypatch):
    """Sans ce drapeau, un opérateur ayant travaillé les 50 états verrait
    « 0/50 » et croirait à un bug de calcul. C'est la DONNÉE qui manque."""
    a = _resume([_qso('W1ABC'), _qso('K5XYZ')], monkeypatch)
    assert a['was']['worked'] == 0
    assert a['was_data'] is False


def test_was_compte_les_etats_quand_ils_sont_la(monkeypatch):
    a = _resume([_qso('W1ABC', state='MA'), _qso('K5XYZ', state='TX'),
                 _qso('N7QQQ', state='TX')], monkeypatch)
    assert a['was']['worked'] == 2 and a['was']['total'] == 50
    assert a['was_data'] is True
    assert 'MA' not in a['was']['missing'] and 'CA' in a['was']['missing']


def test_le_district_de_columbia_compte_pour_le_maryland(monkeypatch):
    """Le WAS se compte sur 50 états ; DC n'a pas de slot propre. Règle ARRL
    WAS vérifiée sur arrl.org/was (WAS Rules/Fees, section 3, 15/08/2026) :
    « The District of Columbia may be counted for Maryland. »

    AVANT ce correctif, le test encodait le comportement BUGUÉ comme s'il
    était voulu : un QSO state='DC' n'était crédité NULLE PART (ni DC, absent
    de US_STATES, ni MD) -- bug réel trouvé par l'audit de conformité du
    15/08/2026, pas seulement « DC ne compte pas double »."""
    assert 'DC' not in aw.US_STATES and len(aw.US_STATES) == 50
    a = _resume([_qso('W3ABC', state='DC')], monkeypatch)
    assert a['was']['worked'] == 1, 'DC doit crediter le Maryland'
    assert 'MD' not in a['was']['missing']


def test_dc_et_md_partagent_le_meme_slot_jamais_51_sur_50(monkeypatch):
    """Un contact avec DC et un autre avec MD créditent le MÊME état -- le
    compteur doit rester a 1/50, jamais 2/50 ni 51/50 au total du diplome."""
    a = _resume([_qso('W3ABC', state='DC'), _qso('W3DEF', state='MD')],
                monkeypatch)
    assert a['was']['worked'] == 1
    assert a['was']['total'] == 50


def test_une_valeur_d_etat_absurde_est_ignoree(monkeypatch):
    """Les états viennent d'annuaires en ligne : une province canadienne ou du
    texte libre ne doit pas gonfler le compteur."""
    a = _resume([_qso('VE3ABC', state='ON'), _qso('W1ABC', state='Massachusetts'),
                 _qso('K5XYZ', state='')], monkeypatch)
    assert a['was']['worked'] == 0


# ─── Remplir l'état du PASSÉ depuis un ADIF LoTW/ClubLog ─────────────────────

_ADIF = ('LoTW\n<EOH>\n'
         '<CALL:5>W1ABC<BAND:3>20M<MODE:3>SSB<QSO_DATE:8>20260101'
         '<TIME_ON:4>1200<STATE:2>MA<EOR>\n'
         '<CALL:5>K5XYZ<BAND:3>40M<MODE:2>CW<QSO_DATE:8>20260102'
         '<TIME_ON:4>1300<STATE:2>TX<EOR>\n'
         '<CALL:5>F6ABC<BAND:3>20M<MODE:3>SSB<QSO_DATE:8>20260104'
         '<TIME_ON:4>1500<EOR>\n')


def test_l_etat_est_indexe_par_INDICATIF_pas_par_QSO():
    """Choix central : l'état est une propriété de la STATION. Un seul record
    renseigne donc TOUS les QSO déjà faits avec cet indicatif, y compris sur
    d'autres bandes et à d'autres dates — là où une correspondance QSO par QSO
    exigerait que le rapport couvre exactement les mêmes contacts."""
    etats = imp.etats_depuis_adif(_ADIF)
    assert etats == {'W1ABC': 'MA', 'K5XYZ': 'TX'}

    log = [_qso('W1ABC', band='14'), _qso('W1ABC', band='7', mode='CW'),
           _qso('K5XYZ', band='7', mode='CW'), _qso('F6ABC')]
    remplis, calls = imp.appliquer_etats(log, etats)
    assert remplis == 3
    assert log[1]['state'] == 'MA', 'autre bande, autre date : renseigne aussi'
    assert 'state' not in log[3], 'station non-US : rien a poser'


def test_un_import_n_ecrase_JAMAIS_un_etat_deja_present():
    """Une valeur saisie ou confirmée vaut mieux qu'une valeur d'annuaire : un
    import ne doit pas pouvoir dégrader une donnée existante."""
    log = [_qso('W1ABC', state='CA')]
    remplis, _ = imp.appliquer_etats(log, {'W1ABC': 'MA'})
    assert remplis == 0 and log[0]['state'] == 'CA'


def test_l_enrichissement_ne_cree_aucun_QSO():
    """C'est commit_import qui ajoute des contacts. Mélanger les deux ferait
    entrer dans le carnet les QSO d'un simple rapport de confirmations."""
    log = [_qso('W1ABC')]
    imp.appliquer_etats(log, {'W1ABC': 'MA', 'K5XYZ': 'TX', 'N7QQQ': 'AZ'})
    assert len(log) == 1


def test_un_adif_illisible_ne_leve_pas():
    assert imp.etats_depuis_adif('n importe quoi') == {}
    assert imp.etats_depuis_adif('') == {}


# ─── Aller-retour ADIF ───────────────────────────────────────────────────────

def test_l_etat_survit_a_un_export_puis_reimport():
    """Sans la balise STATE à l'export, le WAS serait perdu au premier
    aller-retour ADIF — et l'utilisateur ne le verrait qu'après coup."""
    from logx_export import build_adif
    adif = build_adif([_qso('W1ABC', state='MA', locator='FN42')])
    assert '<STATE:2>MA' in adif.upper().replace('<STATE:2>', '<STATE:2>')
    relus, _ = imp.parse_adif_to_qsos(adif)
    assert relus and relus[0]['state'] == 'MA'


def test_un_qso_sans_etat_n_ecrit_pas_de_balise_vide():
    from logx_export import build_adif
    adif = build_adif([_qso('F6ABC', locator='JN18')])
    assert 'STATE' not in adif.upper()


# ─── Grille bande × mode : entités DXCC, pas seulement des QSO ───────────────
# La grille existait déjà (worked_matrix) mais ne comptait que des QSO. Or le
# nombre de QSO dit l'ACTIVITÉ sur une case, tandis que le nombre d'ENTITÉS dit
# l'AVANCEMENT du DXCC Challenge. Mesuré sur le log réel : 3 621 QSO en phonie
# 20 m pour 135 entités — le second chiffre est celui qui indique où il reste
# à faire.

def test_la_grille_compte_les_entites_pas_seulement_les_QSO(monkeypatch):
    monkeypatch.setattr(aw, '_read_archives', lambda: [])
    monkeypatch.setattr(aw, '_read_qso_archive', lambda: [])
    monkeypatch.setattr(aw, '_load_confirmations', lambda: {})
    aw.invalidate()
    # Trois QSO sur 20 m phonie, mais deux entités seulement.
    log = [_qso('W1ABC', '14', 'SSB', time='1200'),
           _qso('W2DEF', '14', 'SSB', time='1300'),
           _qso('JA1XYZ', '14', 'SSB', time='1400')]
    c = aw.worked_matrix(log)['grid']['14']['PHONE']
    assert c['qso'] == 3
    assert c['dxcc'] == 2, 'W1ABC et W2DEF sont la meme entite'


def test_seul_LoTW_compte_dans_la_colonne_confirmee(monkeypatch):
    """Même règle que les alertes : pour l'ARRL une confirmation eQSL ne vaut
    rien. Deux compteurs distincts, jamais un seul « confirmé » ambigu."""
    monkeypatch.setattr(aw, '_read_archives', lambda: [])
    monkeypatch.setattr(aw, '_read_qso_archive', lambda: [])
    monkeypatch.setattr(aw, '_load_confirmations', lambda: {
        'W1ABC|14|SSB': {'lotw': True},
        'JA1XYZ|14|SSB': {'eqsl': True},
    })
    aw.invalidate()
    log = [_qso('W1ABC', '14', 'SSB', time='1200'),
           _qso('JA1XYZ', '14', 'SSB', time='1400')]
    c = aw.worked_matrix(log)['grid']['14']['PHONE']
    assert c['confirmed'] == 2, 'les deux ont UNE confirmation'
    assert c['dxcc_lotw'] == 1, 'mais une seule est confirmee LoTW'


def test_les_DEUX_ecrans_annoncent_le_MEME_nombre_de_cases_Challenge(monkeypatch):
    """DÉFAUT ATTRAPÉ ICI. La grille comptait 454 cases là où le panneau
    Diplômes en annonçait 435 : elle incluait le 144, le 432 et une bande
    « 1mm » issue d'une saisie douteuse, qui n'entrent pas dans le Challenge
    ARRL (160 m à 6 m). Deux chiffres différents pour la même chose au même
    écran, c'est ce qui fait douter de tout le reste."""
    monkeypatch.setattr(aw, '_read_archives', lambda: [])
    monkeypatch.setattr(aw, '_read_qso_archive', lambda: [])
    monkeypatch.setattr(aw, '_load_confirmations', lambda: {})
    aw.invalidate()
    log = [_qso('W1ABC', '14', 'SSB', time='1200'),
           _qso('JA1XYZ', '7', 'CW', time='1300'),
           _qso('VK3ZZZ', '144', 'SSB', time='1400'),   # hors Challenge
           _qso('PY2AAA', '432', 'SSB', time='1500')]   # hors Challenge
    a = aw.award_summary(log)
    m = aw.worked_matrix(log)
    assert m['challenge'] == a['dxcc_challenge']['worked']
    assert m['challenge'] == 2, 'seuls le 20 m et le 40 m comptent'
