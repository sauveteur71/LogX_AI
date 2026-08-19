# -*- coding: utf-8 -*-
"""FT8 : ne jamais émettre dans le créneau de la station qu'on appelle.

Signalé en trafic réel (19/08/2026) : « si je n'envoie pas la trame tout de
suite en réponse, l'émission part en même temps que l'autre station émet au
lieu de passer un tour ».

C'était exact, et c'était un vrai défaut. En FT8 une station émet toujours sur
la MÊME moitié du cycle de 30 s ; répondre, c'est émettre sur l'autre moitié.
Or envoyerMessage() programmait sur `Math.ceil(now/15000)*15000` — LE PROCHAIN
CRÉNEAU QUEL QU'IL SOIT. Répondre sans tarder tombait juste PAR HASARD, parce
que le prochain créneau se trouvait être le bon. Répondre une seconde trop tard
le faisait tomber sur le créneau du correspondant : on émettait par-dessus lui,
aucun des deux n'entendait l'autre, et rien à l'écran ne l'expliquait.

Aucun réglage n'est nécessaire : la bonne parité se DÉDUIT du créneau où la
station a été entendue.

Ces tests exécutent les fonctions RÉELLEMENT extraites de logx_ft8.html — pas
une réécriture, qui ne contraindrait qu'elle-même.
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT8_HTML = os.path.join(CONCOURS, 'logx_ft8.html')

py_mini_racer = pytest.importorskip('py_mini_racer')

SLOT = 15000


def _lire():
    with open(FT8_HTML, encoding='utf-8') as f:
        return f.read()


def _extraire_fonction(src, nom):
    """Comptage d'accolades — une regex non gloutonne s'arrêterait à la
    première accolade fermante imbriquée."""
    debut = src.index('function ' + nom)
    prof, i = 0, src.index('{', debut)
    while True:
        if src[i] == '{':
            prof += 1
        elif src[i] == '}':
            prof -= 1
            if prof == 0:
                return src[debut:i + 1]
        i += 1


@pytest.fixture
def page():
    """Socle minimal : le seul élément de page dont ces fonctions dépendent est
    le champ du message. Tout le reste est la vraie logique du fichier livré."""
    src = _lire()
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
    var __champTx = {value: ''};
    var document = {getElementById: function(id){
      return (id === 'txText') ? __champTx : null;
    }};
    var correspondant = null;
    """)
    for nom in ('pariteDuCreneau', 'destinataireDuChamp',
                'retenirPariteCorrespondant', 'creneauDEmission'):
        ctx.eval(_extraire_fonction(src, nom))
    return ctx


def _selectionner(page, call, slot_entendu):
    """Reproduit ce que fait un clic sur un décodage : le champ contient la
    réponse préparée, et on retient la parité du créneau où la station a émis."""
    page.eval('__champTx.value = %r;' % ('%s F4GLD JN15' % call))
    page.eval('retenirPariteCorrespondant(%d);' % slot_entendu)


def _plan(page, maintenant, texte):
    page.eval('var __p = creneauDEmission(%d, %r);' % (maintenant, texte))
    return (page.eval('__p.creneau'), page.eval('__p.tourPasse'))


# ═══════════════════════════════════════════════════════════════════════════
# §1. LE DÉFAUT SIGNALÉ
# ═══════════════════════════════════════════════════════════════════════════

def test_repondre_TARD_passe_un_tour_au_lieu_d_emettre_par_dessus(page):
    """LE cas signalé. La station a émis dans le créneau 0 (pair). On doit
    répondre sur un créneau IMPAIR. Si l'opérateur laisse filer et clique à
    16 s, le prochain créneau est 30000 — PAIR, celui du correspondant.

    Avant correction, la trame partait là : les deux stations émettaient
    ensemble. Maintenant on attend 45000."""
    _selectionner(page, 'F4ABC', slot_entendu=0)
    creneau, tour_passe = _plan(page, 16000, 'F4ABC F4GLD JN15')
    assert creneau == 45000, (
        'émission programmée à %d, soit le créneau de F4ABC' % creneau)
    assert tour_passe is True, "l'écran doit pouvoir dire qu'un tour est passé"


def test_repondre_TOT_ne_passe_aucun_tour(page):
    """Le pendant : répondre dans la foulée doit rester immédiat. Un correctif
    qui ferait attendre tout le monde serait pire que le défaut."""
    _selectionner(page, 'F4ABC', slot_entendu=0)
    creneau, tour_passe = _plan(page, 2000, 'F4ABC F4GLD JN15')
    assert creneau == 15000, creneau
    assert tour_passe is False


@pytest.mark.parametrize('slot_entendu,attendu', [
    (0, 1), (15000, 0), (30000, 1), (45000, 0),
    (7 * 24 * 3600 * 1000, 1),          # très loin de l'origine des temps
])
def test_on_emet_toujours_sur_la_moitie_de_cycle_opposee(page, slot_entendu,
                                                         attendu):
    """La propriété de fond, quelle que soit la moitié où la station est
    entendue et quel que soit l'instant du clic."""
    _selectionner(page, 'F4ABC', slot_entendu=slot_entendu)
    for retard in range(0, 60000, 3000):
        creneau, _ = _plan(page, slot_entendu + retard, 'F4ABC F4GLD JN15')
        parite = (creneau // SLOT) % 2
        assert parite == attendu, (
            'entendue au créneau %d, clic à +%d ms -> émission au créneau %d '
            '(parité %d), attendu %d'
            % (slot_entendu, retard, creneau, parite, attendu))


def test_jamais_le_meme_creneau_que_le_correspondant(page):
    """Formulation directe de ce qu'il ne faut pas faire, sur un balayage fin
    de l'instant du clic — une seconde de décalage suffisait à basculer."""
    _selectionner(page, 'F4ABC', slot_entendu=0)
    pariteCorr = 0
    for maintenant in range(0, 60000, 500):
        creneau, _ = _plan(page, maintenant, 'F4ABC F4GLD JN15')
        assert (creneau // SLOT) % 2 != pariteCorr, (
            'clic à %d ms -> créneau %d, celui du correspondant' % (maintenant,
                                                                    creneau))


# ═══════════════════════════════════════════════════════════════════════════
# §2. NE PAS IMPOSER UNE PARITÉ QUI N'A PAS LIEU D'ÊTRE
# ═══════════════════════════════════════════════════════════════════════════

def test_sans_correspondant_le_comportement_d_origine_est_intact(page):
    """Message saisi à la main, aucune station sélectionnée : on part au
    prochain créneau, comme avant. Le correctif ne doit rien changer là."""
    creneau, tour_passe = _plan(page, 16000, 'CQ F4GLD JN15')
    assert creneau == 30000, creneau
    assert tour_passe is False


def test_un_appel_CQ_n_est_adresse_a_personne(page):
    """Après avoir travaillé une station, appeler CQ ne doit pas rester
    prisonnier de SA parité : un CQ n'est adressé à personne, et l'opérateur
    choisit librement son tour."""
    _selectionner(page, 'F4ABC', slot_entendu=0)
    page.eval("__champTx.value = 'CQ F4GLD JN15';")
    page.eval('retenirPariteCorrespondant(0);')
    creneau, tour_passe = _plan(page, 16000, 'CQ F4GLD JN15')
    assert creneau == 30000, creneau
    assert tour_passe is False


def test_la_parite_ne_s_applique_pas_a_une_AUTRE_station(page):
    """L'opérateur a sélectionné F4ABC, puis réécrit le champ pour appeler
    quelqu'un d'autre. Imposer la parité de F4ABC à un message qui ne lui est
    pas adressé ferait attendre sans aucune raison."""
    _selectionner(page, 'F4ABC', slot_entendu=0)
    creneau, tour_passe = _plan(page, 16000, 'DL1XYZ F4GLD JN15')
    assert creneau == 30000, creneau
    assert tour_passe is False


def test_la_marge_avant_emission_est_conservee(page):
    """Moins d'une seconde ne suffit pas à préparer PTT + lecture audio : le
    créneau suivant est sauté. Cette règle préexistait et ne doit pas avoir été
    perdue en ajoutant la parité."""
    creneau, _ = _plan(page, 14500, 'CQ F4GLD JN15')
    assert creneau == 30000, (
        '500 ms de marge : le créneau 15000 est inatteignable, %d' % creneau)


# ═══════════════════════════════════════════════════════════════════════════
# §3. LA MÉMOIRE DE PARITÉ
# ═══════════════════════════════════════════════════════════════════════════

def test_la_parite_retenue_est_celle_du_destinataire_prepare(page):
    """On ne réécrit pas une deuxième règle pour trouver le destinataire : le
    premier jeton du message préparé EST le destinataire, par construction du
    protocole. Ce fichier a déjà produit trois défauts par duplication d'une
    même règle."""
    _selectionner(page, 'IK2VFR', slot_entendu=15000)
    assert page.eval('correspondant.call') == 'IK2VFR'
    assert page.eval('correspondant.parite') == 1


def test_une_station_qui_reemet_rafraichit_sa_parite(page):
    """Si elle change de moitié de cycle en cours de QSO — rare, mais alors
    c'est NOUS qui deviendrions le brouilleur."""
    _selectionner(page, 'F4ABC', slot_entendu=0)
    assert page.eval('correspondant.parite') == 0
    # Le rafraîchissement vit dans ajouterDecodage ; on vérifie ici que la
    # structure de données le permet et que creneauDEmission en tient compte.
    page.eval('correspondant.parite = 1;')
    creneau, _ = _plan(page, 2000, 'F4ABC F4GLD JN15')
    assert (creneau // SLOT) % 2 == 0, (
        'la parité rafraîchie doit être prise en compte : créneau %d' % creneau)


def test_ajouterDecodage_rafraichit_bien_la_parite_du_correspondant():
    """Le test précédent porte sur la structure ; celui-ci vérifie que la page
    fait RÉELLEMENT le rafraîchissement — sans quoi la structure ne servirait
    à rien."""
    corps = _extraire_fonction(_lire(), 'ajouterDecodage')
    # Dépouiller les commentaires : un test qui cherche un identifiant dans du
    # texte brut est satisfait par le pavé qui l'EXPLIQUE.
    sans_com = '\n'.join(l for l in corps.split('\n')
                         if not l.strip().startswith('//'))
    assert 'correspondant.parite = pariteDuCreneau(slotMs)' in sans_com, (
        'ajouterDecodage ne rafraîchit pas la parité de la station suivie')
    assert 'correspondant && call === correspondant.call' in sans_com, (
        'le rafraîchissement doit être limité à la station suivie')


def test_le_double_clic_transmet_le_creneau_entendu():
    """Sans le créneau, le double-clic — le geste le plus courant — n'aurait
    aucune parité à respecter et le défaut resterait entier sur ce chemin."""
    src = _lire()
    # On vise le SITE D'APPEL, pas la chaîne n'importe où : la DÉCLARATION
    # « function repondreEtEnvoyer(text, slotMs) » contient exactement la même
    # sous-chaîne, et un test qui la cherchait globalement restait vert alors
    # que le double-clic ne transmettait plus rien. Trouvé par contre-épreuve,
    # c'est le piège « présence au lieu de structure » déjà payé plusieurs fois
    # dans ce dépôt.
    i = src.index("tr.addEventListener('dblclick'")
    appel = src[i:i + 200]
    assert 'slotMs' in appel, (
        'le double-clic sur un décodage doit transmettre son créneau : %r'
        % appel[:160])
    corps = _extraire_fonction(src, 'repondreEtEnvoyer')
    # Le paramètre s'appelle slotEntendu depuis la fusion du séquenceur : les
    # deux branches avaient ajouté ce même paramètre pour deux usages de la
    # même donnée (parité du séquenceur / mémoire du chemin manuel), et il a
    # été unifié plutôt que dédoublé.
    assert 'retenirPariteCorrespondant(slotEntendu)' in corps, corps[:300]


def test_le_double_clic_n_appelle_proposerReponse_qu_une_fois():
    """repondreEtEnvoyer fait DÉJÀ préparation + affichage, et son chemin
    « RRR »/« 73 » appelle offrirLogQso. Doubler l'appel proposerait deux fois
    d'enregistrer le même QSO — défaut introduit puis retiré pendant ce
    correctif."""
    src = _lire()
    i = src.index("tr.addEventListener('dblclick'")
    zone = src[i:i + 200]
    assert 'proposerReponse' not in zone, (
        'le gestionnaire de double-clic ne doit pas rappeler proposerReponse : '
        '%r' % zone[:160])


def test_l_ecran_dit_quand_un_tour_est_passe():
    """Un tour passé ressemble à un blocage : l'opérateur clique, et il ne se
    passe rien pendant 30 s. Il faut le dire."""
    src = _lire()
    # On ancre sur le MESSAGE et on vérifie qu'il est bien conditionné, plutôt
    # que de fixer une fenêtre de caractères après `plan.tourPasse` : depuis la
    # fusion du séquenceur, une branche `creneauImpose` s'intercale entre les
    # deux et la fenêtre ne les contenait plus tous les deux.
    i = src.index('un tour passé')
    zone = src[max(0, i - 300):i + 200]
    assert 'tourPasse' in zone, (
        "le message doit être conditionné à un tour réellement passé : %r"
        % zone[-260:])
    assert 'correspondant.call' in zone, (
        "le message doit nommer la station concernée : %r" % zone[-260:])
