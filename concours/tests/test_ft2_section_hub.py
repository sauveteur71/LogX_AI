# -*- coding: utf-8 -*-
"""Section FT2 — Decodium 4.0 du hub MODE NUMÉRIQUE (Phase 4, aucune émission).

FT2 est un mode EXPÉRIMENTAL, profil SÉPARÉ servi par /freq/ft2 (jamais mêlé au
plan de bande IARU). En Phase 4 la section n'expose qu'une action réellement
fonctionnelle : le QSY (RX seul, /rig/qsy sans 'mode' -> le poste garde son mode
data). L'émission FT2 passe par Decodium (UDP) et n'est PAS câblée ici : les
boutons « Préparer/Appeler FT2 » sont présents mais DÉSACTIVÉS (câblage Phase 5,
essai on-air supervisé). Ces tests structurels verrouillent les propriétés de
SÛRETÉ ; la vérification visuelle (2 thèmes) et l'essai radio restent manuels.
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_modes_numeriques.html'), encoding='utf-8').read()


def _corps_fonction(src, nom):
    """Extrait le corps de `function nom(...){ ... }` par comptage d'accolades."""
    i = src.index('function ' + nom)
    j = src.index('{', i)
    prof, k = 0, j
    while k < len(src):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[j:k + 1]
        k += 1
    raise AssertionError('corps de %s introuvable' % nom)


def _tag_avec_id(src, ident):
    """Le texte de la balise ouvrante portant id="ident" (jusqu'au premier >)."""
    i = src.index('id="' + ident + '"')
    deb = src.rfind('<', 0, i)
    fin = src.index('>', i)
    return src[deb:fin + 1]


def test_route_freq_ft2_declaree():
    src = open(os.path.join(BASE, 'logx_http.py'), encoding='utf-8').read()
    assert "path == '/freq/ft2'" in src, "route GET /freq/ft2 absente"
    assert 'ft2_decodium()' in src, "l'endpoint doit renvoyer ft2_decodium()"


def test_section_ft2_cablee_sur_profil_separe():
    # La section charge le profil SÉPARÉ, pas la table de bande générique.
    assert "fetch('/freq/ft2')" in HTML, "la section doit charger /freq/ft2"
    for anchor in ('id="ft2Panel"', 'id="ft2Band"', 'id="ft2Freq"', 'id="ft2Go"', 'ft2Aller()'):
        assert anchor in HTML, "élément FT2 manquant : %s" % anchor
    # Jamais un profil global nommé « FT2 » (décision F4GLD) : c'est bien
    # l'étiquette expérimentale Decodium qui est affichée.
    assert 'EXPÉRIMENTAL' in HTML


def test_bandeau_avertissement_rendu_depuis_le_profil():
    # Le bandeau existe et est alimenté par avertissements[] du profil (toujours
    # visible : c'est un choix explicite, pas un repli).
    assert 'id="ft2Warn"' in HTML
    corps = _corps_fonction(HTML, 'ft2Init')
    assert '.avertissements' in corps, "le bandeau doit être rempli depuis avertissements[]"
    assert 'ft2Warn' in corps and 'innerHTML' in corps


def test_boutons_emission_desactives_en_phase4():
    # PROPRIÉTÉ DE SÛRETÉ : en Phase 4 rien ne peut émettre — les deux boutons
    # d'émission portent l'attribut `disabled` dans leur balise même.
    for ident in ('ft2Prep', 'ft2Call'):
        tag = _tag_avec_id(HTML, ident)
        assert 'disabled' in tag, "le bouton %s doit être désactivé en Phase 4 : %s" % (ident, tag)


def _sans_commentaires(js):
    """Retire les commentaires // en fin de ligne (immunise les tests contre le
    texte explicatif — piège documenté : un commentaire satisfait une recherche)."""
    return '\n'.join(re.sub(r'//.*$', '', ligne) for ligne in js.splitlines())


def test_qsy_ft2_rx_seul_sans_mode_ni_emission():
    # PROPRIÉTÉ DE SÛRETÉ : le QSY FT2 règle la fréquence SANS 'mode' (le poste
    # garde son mode data) et n'appelle AUCUN endpoint d'émission.
    corps = _sans_commentaires(_corps_fonction(HTML, 'ft2Aller'))
    assert "fetch('/rig/qsy'" in corps, "le QSY doit passer par /rig/qsy"
    # Le payload envoyé = {freq_khz: ...} et RIEN d'autre — surtout pas de 'mode'
    # (structure exigée, pas simple présence) : on isole l'objet JSON.stringify.
    m = re.search(r"JSON\.stringify\((\{[^}]*\})\)", corps)
    assert m, "payload QSY doit être un objet JSON.stringify({...})"
    payload = m.group(1)
    assert 'freq_khz' in payload, "le QSY doit régler freq_khz"
    assert 'mode' not in payload, "le QSY FT2 ne doit PAS forcer de mode poste : %s" % payload
    # aucun chemin d'émission depuis le QSY
    for tx in ("/rig/cw", "/rig/tx", "/wsjtx/repondre", "envoyer_reply"):
        assert tx not in corps, "le QSY FT2 ne doit appeler aucune émission (%s)" % tx


def test_aucune_emission_automatique_dans_la_section():
    # Aucune émission auto : la section ne poste que /rig/qsy (RX). Nul appel à
    # un endpoint d'émission dans tout le bloc FT2 (Phase 5 = câblage supervisé).
    # On borne la recherche à la zone FT2 pour ne pas capter le QSY générique.
    deb = HTML.index('Section FT2')
    zone = HTML[deb:]
    assert "fetch('/rig/cw'" not in zone
    assert "fetch('/wsjtx/repondre'" not in zone
