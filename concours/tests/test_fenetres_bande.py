# -*- coding: utf-8 -*-
"""Fenêtres de surveillance par bande.

DEMANDE UTILISATEUR : « je veux surveiller simultanément toutes les bandes en
même temps comme je le fais en ce moment avec Logger32 ; je peux en ouvrir
autant que je veux pour voir ce qu'il se passe ».

CE QUI EST TESTÉ ICI, ET POURQUOI. La page elle-même est du HTML statique :
son rendu a été vérifié sur le serveur réel (spots injectés, badges comptés,
filtrage de bande confirmé). Ce que du code peut protéger durablement, c'est
l'annotation côté serveur — celle qui décide quel spot est un besoin DXCC — et
le câblage de la page : elle peut être parfaite et n'être ouverte par personne,
ou viser une variable de bandes qui n'existe pas.

CE SECOND POINT N'EST PAS THÉORIQUE : le premier jet de popoutBandes() visait
une variable `activeBands` inexistante, protégée par un `typeof … !==
'undefined'` qui retombait TOUJOURS sur une liste de bandes en dur — sans que
rien ne le signale. D'où le test qui exige la vraie variable.
"""
import os
import re
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_awards as aw   # noqa: E402

PAGE = os.path.join(CONCOURS, 'logx_bande.html')
JS = os.path.join(CONCOURS, 'logx_logbook.js')
HTML = os.path.join(CONCOURS, 'logx_logbook.html')


def _lire(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def _qso(call, band, mode, time='1200'):
    return {'call': call, 'band': band, 'mode': mode,
            'date': '2026-01-01', 'time': time}


@pytest.fixture
def sans_fichiers(monkeypatch):
    monkeypatch.setattr(aw, '_read_archives', lambda: [])
    monkeypatch.setattr(aw, '_read_qso_archive', lambda: [])

    def _conf(d):
        monkeypatch.setattr(aw, '_load_confirmations', lambda: d)
        aw.invalidate()
    return _conf


# ─── L'annotation : signaler sans filtrer ────────────────────────────────────

LOG = [_qso('W1ABC', '14', 'SSB')]


def test_annoter_ne_retire_AUCUN_spot(sans_fichiers):
    """Toute la raison d'être de ces fenêtres est la vue d'ensemble : masquer
    les spots sans intérêt DXCC priverait l'opérateur de ce qu'il vient
    regarder. On annote, on ne filtre pas — c'est ce qui distingue cette
    fonction de besoins_lotw_spottes()."""
    sans_fichiers({'W1ABC|14|SSB': {'lotw': True}})
    spots = [{'call': 'W1ABC', 'band': '14', 'mode': 'SSB'},
             {'call': 'JA1XYZ', 'band': '14', 'mode': 'FT8'},
             {'call': 'XX', 'band': '14', 'mode': 'SSB'}]
    aw.annoter_besoin_lotw(spots, LOG)
    assert len(spots) == 3, 'la liste doit rester entiere'
    assert all('lotw_need_ici' in s for s in spots)


def test_le_creneau_confirme_lotw_n_est_pas_un_besoin(sans_fichiers):
    sans_fichiers({'W1ABC|14|SSB': {'lotw': True}})
    spots = [{'call': 'W1ABC', 'band': '14', 'mode': 'SSB'}]
    aw.annoter_besoin_lotw(spots, LOG)
    assert spots[0]['lotw_need_ici'] is False


def test_une_confirmation_eQSL_laisse_le_besoin(sans_fichiers):
    """Même règle que l'alerte à la frappe : seul LoTW compte pour l'ARRL."""
    sans_fichiers({'W1ABC|14|SSB': {'eqsl': True}})
    spots = [{'call': 'W1ABC', 'band': '14', 'mode': 'SSB'}]
    aw.annoter_besoin_lotw(spots, LOG)
    assert spots[0]['lotw_need_ici'] is True


def test_un_indicatif_non_resolu_n_est_pas_signale(sans_fichiers):
    sans_fichiers({})
    spots = [{'call': 'X', 'band': '14', 'mode': 'SSB'}]
    aw.annoter_besoin_lotw(spots, LOG)
    assert spots[0]['lotw_need_ici'] is False


def test_le_carnet_n_est_lu_qu_une_fois_pour_toute_la_liste(sans_fichiers,
                                                            monkeypatch):
    """Ces fenêtres se rafraîchissent en continu, et il peut y en avoir dix
    ouvertes. Un parcours du carnet par spot rendrait l'ensemble inutilisable."""
    sans_fichiers({})
    appels = []
    vrai = aw.collect_all_qsos
    monkeypatch.setattr(aw, 'collect_all_qsos',
                        lambda *a, **k: appels.append(1) or vrai(*a, **k))
    spots = [{'call': c, 'band': '14', 'mode': 'SSB'}
             for c in ('W1ABC', 'JA1XYZ', 'VK3ZZZ', 'PY2AAA')]
    aw.annoter_besoin_lotw(spots, LOG)
    assert len(appels) == 1


def test_une_liste_vide_ne_leve_pas(sans_fichiers):
    sans_fichiers({})
    assert aw.annoter_besoin_lotw([], LOG) == []
    assert aw.annoter_besoin_lotw(None, LOG) is None


# ─── La page ─────────────────────────────────────────────────────────────────

def test_la_page_existe_et_filtre_sur_SA_bande():
    """Sans filtrage, dix fenêtres afficheraient dix fois la même liste — et
    tout l'intérêt d'une fenêtre par bande disparaîtrait."""
    src = _lire(PAGE)
    assert "params.get('band')" in src
    assert 'String(s.band) === bande' in src


def test_la_page_lit_le_theme_jour_nuit():
    """Les pages détachées n'incluent pas logx_statusbar.js : sans relecture
    explicite, une fenêtre ouverte en plein jour repasse en mode nuit alors
    que le logbook est en clair."""
    src = _lire(PAGE)
    assert "localStorage.getItem('rc_theme')" in src
    assert 'day-mode' in src


def test_la_page_refuse_de_s_ouvrir_en_file():
    """Ouverte par double-clic depuis l'explorateur, elle ne pourrait joindre
    aucun endpoint : mieux vaut le dire que d'afficher une liste vide."""
    assert "location.protocol === 'file:'" in _lire(PAGE)


def test_la_page_echappe_ce_qui_vient_du_cluster():
    """Les spots viennent d'Internet : un indicatif contenant du HTML
    exécuterait du script dans la fenêtre (même famille que la faille corrigée
    sur les versions de pairs en 0.9-beta5)."""
    src = _lire(PAGE)
    assert 'const esc =' in src
    for champ in ('s.call', 's.freq||', 's.dx_country'):
        assert 'esc(' + champ in src or 'esc(' + champ.rstrip('|') in src, champ


def test_la_page_ne_duplique_pas_la_saisie():
    """Lecture seule à dessein : y mettre l'enregistrement créerait deux
    endroits où loguer un QSO, donc deux vérités possibles."""
    src = _lire(PAGE)
    assert '/log/add' not in src


# ─── Le câblage ──────────────────────────────────────────────────────────────

def test_le_bouton_existe_et_appelle_la_fonction():
    assert 'popoutBandes()' in _lire(HTML)
    assert 'function popoutBandes(' in _lire(JS)


def test_les_bandes_viennent_de_la_VRAIE_variable():
    """LE défaut du premier jet : viser `activeBands`, qui n'existe pas. Le
    garde `typeof` retombait alors TOUJOURS sur une liste en dur, sans que
    rien ne le signale — l'opérateur aurait eu des fenêtres 1,8 MHz en
    concours THF."""
    src = _lire(JS)
    bloc = src[src.index('function popoutBandes('):]
    bloc = bloc[:bloc.index('\n}')]
    assert '_currentVisibleBands' in bloc
    assert 'activeBands' not in bloc
    assert re.search(r"\['1\.8'\s*,", bloc) is None, (
        'plus de liste de bandes en dur : elle ignorerait les cases de CONFIG')


def test_aucune_bande_active_le_DIT_au_lieu_d_ouvrir_au_hasard():
    src = _lire(JS)
    bloc = src[src.index('function popoutBandes('):]
    bloc = bloc[:bloc.index('\n}')]
    assert 'notify(' in bloc


def test_les_fenetres_ne_se_superposent_pas():
    """Ouvertes au même endroit, elles seraient indiscernables — l'opérateur
    croirait que le bouton n'a ouvert qu'une fenêtre."""
    src = _lire(JS)
    bloc = src[src.index('function popoutBandes('):]
    bloc = bloc[:bloc.index('\n}')]
    assert 'left=' in bloc and 'top=' in bloc


def test_chaque_bande_a_son_propre_nom_de_fenetre():
    """Un nom commun ferait que chaque ouverture RÉUTILISE la même fenêtre :
    on croirait que seule la dernière bande s'ouvre."""
    src = _lire(JS)
    bloc = src[src.index('function popoutBandes('):]
    bloc = bloc[:bloc.index('\n}')]
    assert "'rc_bande_'" in bloc


# ─── Réglette de fréquence ───────────────────────────────────────────────────
# Une liste dit QUI trafique ; une échelle montre OÙ l'activité se concentre et
# surtout où il reste un trou pour appeler. C'est l'information qu'une liste ne
# peut pas donner — et c'est ce que j'avais manqué en livrant des listes.

@pytest.mark.parametrize('bande,lo,hi,nb_seg', [
    ('1.8', 1.8, 2.0, 2),
    ('7', 7.0, 7.3, 3),
    ('14', 14.0, 14.35, 3),
    ('50', 50.0, 54.0, 2),
    ('144', 144.0, 148.0, 2),
])
def test_le_decoupage_des_bandes(bande, lo, hi, nb_seg):
    r = aw.segments_bande(bande)
    assert abs(r['lo'] - lo) < 1e-6 and abs(r['hi'] - hi) < 1e-6
    assert len(r['segments']) == nb_seg


def test_le_70cm_est_couvert_malgre_son_absence_de_la_table_CC():
    """La table du manuel CC User s'arrête au 222 MHz — elle vise l'Amérique du
    Nord. Le 70 cm est une bande de concours majeure en région 1 (Rallye des
    Points Hauts, National THF) : la laisser de côté rendrait la réglette
    inutilisable là où l'utilisateur trafique le plus."""
    r = aw.segments_bande('432')
    assert r is not None
    assert abs(r['lo'] - 430.0) < 1e-6, 'la bande commence a 430, pas a 432'
    assert [s['cat'] for s in r['segments']] == ['CW', 'PHONE']


def test_une_bande_nommee_au_dessus_de_sa_borne_basse():
    """DÉFAUT DE MON PREMIER JET : le filtre supposait que le nom de la bande
    EST sa fréquence basse. Vrai pour 14, 7, 144… mais pas pour le 432, qui
    commence à 430 — son segment CW disparaissait de la réglette."""
    assert aw.segments_bande('432')['segments'][0]['cat'] == 'CW'


def test_le_60m_ne_contamine_pas_le_40m():
    """5,260 MHz est plus proche de 7 MHz que de toute autre bande nommée : la
    tolérance basse doit rester assez serrée pour l'exclure."""
    seg = aw.segments_bande('7')['segments']
    assert all(s['lo'] >= 7.0 for s in seg)


def test_les_segments_adjacents_de_meme_categorie_fusionnent():
    """La table distingue SSB et FM (deux lignes PHONE qui se touchent) :
    les afficher séparément dessinerait une frontière que l'opérateur ne voit
    pas sur sa bande."""
    cats = [s['cat'] for s in aw.segments_bande('144')['segments']]
    assert cats == ['CW', 'PHONE'], 'SSB et FM doivent etre fusionnes'


def test_une_bande_inconnue_ne_leve_pas():
    for v in ('', None, 'abc', '999'):
        assert aw.segments_bande(v) is None


def test_la_reglette_partage_la_table_du_mode_par_frequence():
    """Une seule source de vérité : sinon la réglette pourrait dessiner un
    segment CW là où l'alerte compte un créneau numérique."""
    for s in aw.segments_bande('14')['segments']:
        milieu = (s['lo'] + s['hi']) / 2
        assert aw.mode_depuis_frequence(milieu) == s['cat']


def test_la_page_dessine_bien_la_reglette():
    src = _lire(PAGE)
    assert 'function dessinerRegle' in src and 'bande_segments' in src
    assert "class=\"seg seg-" in src or 'seg seg-' in src


def test_la_reglette_reste_affichee_quand_la_bande_est_vide():
    """Bande vide = bande ENTIÈREMENT libre. C'est une information, pas une
    absence d'information — et c'est le moment où l'échelle sert le plus."""
    src = _lire(PAGE)
    bloc = src[src.index("if(!spots.length){"):]
    bloc = bloc[:bloc.index('return;')]
    assert 'dessinerRegle' in bloc
