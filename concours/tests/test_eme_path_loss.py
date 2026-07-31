# -*- coding: utf-8 -*-
"""La perte de trajet EME : 123 dB de trop, et personne pour s'en apercevoir.

TROUVÉ EN CONFRONTANT logx_eme.py À LA FICHE EME DU SKILL, qui donne trois
valeurs de référence chiffrées : ~252 dB à 144 MHz, ~262 dB à 432 MHz,
~271 dB à 1296 MHz.

CE QUE FAISAIT LE CODE : il calculait la perte en espace libre sur un trajet
simple, puis la DOUBLAIT EN dB. Doubler des décibels revient à élever le
rapport de puissance au carré — ça ne décrit aucune physique. Mesuré :
374,6 dB à 144 MHz au lieu de 252. Et l'erreur croissait avec la fréquence
(+19 dB entre 144 et 432 MHz là où la réalité en donne 10), parce que la perte
variait comme f⁴ au lieu de f².

Le docstring appelait ça « le plancher théorique », en expliquant qu'il
n'incluait pas l'albédo lunaire. C'était une justification, pas une mesure : un
plancher trop haut de 123 dB n'est pas un plancher, c'est un chiffre qui dit
que l'EME est impossible. La Lune n'est pas un point qui réémet — elle a une
section efficace gigantesque, et c'est elle qui manquait.

CIRCONSTANCE ATTÉNUANTE, ET C'EN EST UNE VRAIE : la fonction n'avait AUCUN
APPELANT. Aucun utilisateur n'a jamais vu ce chiffre. C'était la seule des cinq
fonctions du module dans ce cas — les quatre autres (position lunaire, fenêtre
commune, lever/coucher, Doppler) sont bien câblées. Elle l'est maintenant aussi,
jointe au Doppler : une fonction juste que personne n'appelle finirait par
redevenir fausse sans que rien ne le dise.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_eme as eme   # noqa: E402

# Distance Terre-Lune moyenne. Les valeurs de référence de la fiche s'entendent
# à cette distance-là.
D_MOYENNE_KM = 384400.0


# ─── Les trois valeurs de référence ──────────────────────────────────────────

@pytest.mark.parametrize('freq_mhz,attendu_db', [
    (144, 252),
    (432, 262),
    (1296, 271),
])
def test_les_pertes_de_reference_sont_retrouvees(freq_mhz, attendu_db):
    """Tolérance 1 dB : la fiche donne des ordres (« ~252 dB »), et l'albédo
    radar lunaire varie selon les sources. Retrouver les TROIS à moins d'un dB
    avec un seul jeu de constantes est ce qui valide la formule."""
    v = eme.path_loss_db(D_MOYENNE_KM, freq_mhz)
    assert abs(v - attendu_db) <= 1.0, (freq_mhz, v, attendu_db)


def test_LA_LOI_EN_FREQUENCE_est_la_bonne():
    """LE test qui aurait attrapé le défaut sans connaître aucune valeur
    absolue. La perte EME varie comme f² (la section efficace de la Lune est
    fixe) : tripler la fréquence coûte ~9,5 dB. L'ancien calcul variait comme
    f⁴ et en donnait 19 — le double."""
    a = eme.path_loss_db(D_MOYENNE_KM, 144)
    b = eme.path_loss_db(D_MOYENNE_KM, 432)
    c = eme.path_loss_db(D_MOYENNE_KM, 1296)
    assert 9.0 <= b - a <= 10.0, (a, b)
    assert 9.0 <= c - b <= 10.0, (b, c)


def test_l_ancien_calcul_ne_peut_plus_revenir():
    """Garde-fou explicite : 2 × FSPL donnait 374,6 dB à 144 MHz."""
    assert eme.path_loss_db(D_MOYENNE_KM, 144) < 300


def test_l_ecart_perigee_apogee_ressort_du_calcul():
    """La fiche donne ~2 dB de mieux au périgée. Ce n'est pas une constante
    ajoutée : ça doit tomber tout seul de la distance."""
    perigee = eme.path_loss_db(356500, 144)
    apogee = eme.path_loss_db(406700, 144)
    assert 1.8 <= apogee - perigee <= 2.8, (perigee, apogee)


def test_la_perte_augmente_avec_la_distance():
    assert eme.path_loss_db(406700, 144) > eme.path_loss_db(356500, 144)


# ─── Entrées douteuses ───────────────────────────────────────────────────────

@pytest.mark.parametrize('d,f', [(0, 144), (-1, 144), (384400, 0), (384400, -3)])
def test_une_entree_absurde_ne_leve_pas(d, f):
    assert eme.path_loss_db(d, f) is None


# ─── Le câblage, pas seulement la fonction ───────────────────────────────────

def test_la_fonction_a_desormais_un_APPELANT():
    """C'était la seule fonction du module que personne n'appelait — d'où
    123 dB d'erreur passés inaperçus. Une fonction juste que personne n'appelle
    finit par redevenir fausse sans que rien ne le dise."""
    with open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8') as f:
        src = f.read()
    assert 'path_loss_db' in src


def test_les_constantes_du_reflecteur_sont_coherentes():
    """Rayon lunaire et albédo radar : ce sont eux qui portent tout le
    résultat, ils doivent rester lisibles et plausibles."""
    assert 1_730_000 <= eme.RAYON_LUNE_M <= 1_745_000
    assert 0.05 <= eme.ALBEDO_RADAR_LUNE <= 0.10
    # Section efficace = albédo × section géométrique.
    import math
    attendu = eme.ALBEDO_RADAR_LUNE * math.pi * eme.RAYON_LUNE_M ** 2
    assert abs(eme.SIGMA_LUNE_M2 - attendu) < 1.0
