# -*- coding: utf-8 -*-
"""Tests du module VOACAP (logx_voacap) -- generateur de fichier .DAT
(format Fortran a colonnes fixes) + parseur de sortie .OUT, tous testables
sans le binaire (portable, la CI n'est pas forcement Windows). Un test
d'integration reel avec voacapl.exe est ajoute a part, protege par
voacap_available() (silencieusement saute hors Windows / sans le binaire
vendu)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_voacap as v


# ═══════════════════════════════════════════════════════════════════════════
# build_dat() -- alignement des colonnes Fortran (format le plus fragile :
# une seule colonne decalee et voacapl.exe echoue silencieusement ou lit
# une valeur fausse sans jamais lever d'erreur).
# ═══════════════════════════════════════════════════════════════════════════

def _lines(dat):
    return dat.split("\r\n")[:-1]  # dernier element = chaine vide apres le dernier \r\n


def test_build_dat_toutes_les_lignes_utilisent_crlf():
    dat = v.build_dat(48.85, 2.35, 40.71, -74.00, 8, 2026, 100.0, v.HAM_BANDS_MHZ)
    assert dat.endswith("\r\n")
    assert "\n\n" not in dat.replace("\r\n", "\n")  # pas de \n nu (Unix) mele au \r\n


def test_build_dat_circuit_card_colonnes_exactes():
    dat = v.build_dat(48.85, 2.35, -33.87, 151.21, 8, 2026, 100.0, [14.0])
    circuit = next(l for l in _lines(dat) if l.startswith("CIRCUIT"))
    # Formats Fortran verifies empiriquement contre le vrai binaire :
    # 10X,F5.2,A1,3(F9.2,A1),4X,I5
    assert circuit[10:15] == "48.85"
    assert circuit[15] == "N"
    assert circuit[16:25] == "     2.35"
    assert circuit[25] == "E"
    assert circuit[26:35] == "    33.87"
    assert circuit[35] == "S"
    assert circuit[36:45] == "   151.21"
    assert circuit[45] == "E"
    assert circuit[50:55] == "    0"


def test_build_dat_circuit_hemispheres_sud_ouest():
    dat = v.build_dat(-33.87, 151.21, 48.85, 2.35, 1, 2026, 50.0, [14.0])
    circuit = next(l for l in _lines(dat) if l.startswith("CIRCUIT"))
    assert circuit[15] == "S"   # TX latitude negative -> S
    assert circuit[25] == "E"   # TX longitude positive -> E
    lon_dir_rx = circuit[45]
    assert lon_dir_rx == "E"   # RX (Paris) longitude positive -> E


def test_build_dat_antenna_card_puissance_et_fichier():
    dat = v.build_dat(48.85, 2.35, 40.71, -74.00, 8, 2026, 100.0, [14.0], power_w=100.0)
    ant_lines = [l for l in _lines(dat) if l.startswith("ANTENNA")]
    assert len(ant_lines) == 2
    # ANTENNA TX : IAT=1, iantr=1, puissance en kW (100W = 0.1000 kW)
    assert ant_lines[0][10:15] == "    1"
    assert ant_lines[0][15:20] == "    1"
    assert "0.1000" in ant_lines[0]
    assert "default/swwhip.voa" in ant_lines[0]
    # ANTENNA RX : IAT=2, iantr=2, puissance non pertinente -> 0
    assert ant_lines[1][10:15] == "    2"
    assert ant_lines[1][15:20] == "    2"
    assert ant_lines[1].rstrip().endswith("0.0000")


def test_build_dat_frequency_card_ordre_preserve():
    freqs = [3.5, 7.0, 10.1, 14.0, 18.1, 21.0, 24.9, 28.0]
    dat = v.build_dat(48.85, 2.35, 40.71, -74.00, 8, 2026, 100.0, freqs)
    freq_line = next(l for l in _lines(dat) if l.startswith("FREQUENCY"))
    # Chaque valeur occupe exactement 5 caracteres (F5.2) -- verifie ici
    # colonne par colonne car deux valeurs >=10 MHz adjacentes se "collent"
    # sans espace separateur (piege reel rencontre en testant le vrai .out).
    chunk = freq_line[10:10 + 5 * len(freqs)]
    parsed = [float(chunk[i:i + 5]) for i in range(0, len(chunk), 5)]
    assert parsed == freqs


def test_build_dat_rejette_plus_de_onze_frequences():
    import pytest
    with pytest.raises(ValueError):
        v.build_dat(48.85, 2.35, 40.71, -74.00, 8, 2026, 100.0, [float(x) for x in range(12)])


def test_build_dat_snr_requis_varie_selon_le_mode():
    dat_cw = v.build_dat(48.85, 2.35, 40.71, -74.00, 8, 2026, 100.0, [14.0], mode='CW')
    dat_ssb = v.build_dat(48.85, 2.35, 40.71, -74.00, 8, 2026, 100.0, [14.0], mode='SSB')
    sys_cw = next(l for l in _lines(dat_cw) if l.startswith("SYSTEM"))
    sys_ssb = next(l for l in _lines(dat_ssb) if l.startswith("SYSTEM"))
    assert sys_cw != sys_ssb
    assert str(v.REQUIRED_SNR_DB['CW']) in sys_cw or f"{v.REQUIRED_SNR_DB['CW']:.0f}" in sys_cw


def test_fit_field_reduit_les_decimales_si_ca_ne_rentre_pas():
    # SSN=110 ne rentre pas en F5.2 ("110.00" = 6 caracteres) mais rentre
    # en F5.1 ("110.0" = 5) -- Fortran accepte un nombre de decimales
    # inferieur a celui declare tant qu'un point explicite est present.
    assert v._fit_field(110.0, 5, 2) == "110.0"
    assert len(v._fit_field(110.0, 5, 2)) == 5
    assert v._fit_field(1.0, 5, 2) == " 1.00"


def test_fit_field_leve_si_valeur_impossible_a_faire_rentrer():
    import pytest
    with pytest.raises(ValueError):
        v._fit_field(999999.0, 5, 2)  # 6 chiffres : ne rentre meme pas a 0 decimale


# ═══════════════════════════════════════════════════════════════════════════
# _parse_out() -- sur un extrait REEL de sortie voacapl.exe (capture figee),
# pas un texte reconstruit a la main : couvre le piege "4 E" (mode avec
# espace interne, casse un split() naif et decale les colonnes suivantes).
# ═══════════════════════════════════════════════════════════════════════════

_REAL_OUT_EXCERPT = (
    "     CCIR Coefficients        ~METHOD 30   VOACAP L 16.1207W  PAGE   1\r\n"
    "\r\n"
    "  Aug    2026          SSN = 110.                Minimum Angle= 3.000 degrees\r\n"
    "  Paris               New York              AZIMUTHS          N. MI.      KM\r\n"
    "  48.85 N    2.35 E - 40.71 N   74.00 W    291.79   53.71    3151.6   5836.2\r\n"
    "\r\n"
    "  10.0 17.3  3.5  7.0 10.1 14.0 18.1 21.0 24.9 28.0  0.0  0.0  0.0 FREQ\r\n"
    "        2F2  4 E  3F2  3F2  2F2  2F2  2F2  2F2  2F2   -    -    -  MODE  \r\n"
    "        9.3  3.9 13.5 11.3  4.5  9.3  9.3  9.3  9.3   -    -    -  TANGLE\r\n"
    "       20.9 19.8 21.0 20.6 20.2 20.9 20.9 20.9 20.9   -    -    -  DELAY \r\n"
    "        431   93  323  280  293  431  431  431  431   -    -    -  V HITE\r\n"
    "       0.50 1.00 0.99 0.88 0.82 0.42 0.18 0.03 0.00   -    -    -  MUFday\r\n"
    "        176  270  187  171  171  181  203  250  302   -    -    -  LOSS  \r\n"
    "        -23 -132  -43  -22  -16  -27  -48  -94 -145   -    -    -  DBU   \r\n"
    "       -156 -250 -167 -151 -151 -161 -183 -230 -282   -    -    -  S DBW \r\n"
    "       -171 -149 -157 -163 -168 -171 -173 -175 -177   -    -    -  N DBW \r\n"
    "         15 -101  -10   12   17   11  -10  -55 -106   -    -    -  SNR   \r\n"
    "         18  123   33   16   16   22   42   88  139   -    -    -  RPWRG \r\n"
    "       0.66 0.00 0.02 0.63 0.70 0.59 0.22 0.00 0.00   -    -    -  REL   \r\n"
)

_FREQS = [3.5, 7.0, 10.1, 14.0, 18.1, 21.0, 24.9, 28.0]


def test_parse_out_extrait_heure_et_bandes():
    hours = v._parse_out(_REAL_OUT_EXCERPT, _FREQS)
    assert len(hours) == 1
    assert hours[0]['hour'] == 10
    assert len(hours[0]['bands']) == len(_FREQS)


def test_parse_out_valeurs_rel_snr_correctes():
    hours = v._parse_out(_REAL_OUT_EXCERPT, _FREQS)
    bands = {b['freq_mhz']: b for b in hours[0]['bands']}
    assert bands[3.5]['rel'] == 0.66
    assert bands[3.5]['snr_db'] == 15.0
    assert bands[28.0]['rel'] == 0.0
    assert bands[28.0]['snr_db'] == -55.0


def test_parse_out_mode_avec_espace_interne_pas_decale():
    # Piege reel : "4 E" (4 sauts, couche E) contient un espace interne.
    # Un split() naif le casse en 2 tokens et decale TOUTES les colonnes
    # suivantes de la ligne MODE. Le parseur doit s'aligner sur les
    # positions de la ligne REL (jamais ambigue) plutot que sur split().
    hours = v._parse_out(_REAL_OUT_EXCERPT, _FREQS)
    bands = {b['freq_mhz']: b for b in hours[0]['bands']}
    assert bands[3.5]['mode'] == '2F2'
    assert bands[7.0]['mode'] == '4 E'   # la valeur a espace interne elle-meme
    assert bands[10.1]['mode'] == '3F2'  # colonne SUIVANTE : doit rester alignee
    assert bands[28.0]['mode'] == '2F2'  # derniere colonne : verifie l'absence de decalage cumule


def test_parse_out_contenu_vide_ne_leve_pas():
    assert v._parse_out("", _FREQS) == []


def test_parse_out_freq_line_sans_bloc_complet_ignoree():
    # Une ligne FREQ sans les lignes REL/SNR/MODE qui suivent (fichier
    # tronque) ne doit pas planter -- juste produire des valeurs None.
    partial = "   1.0 16.3  3.5  7.0  0.0  0.0  0.0  0.0  0.0  0.0  0.0  0.0  0.0 FREQ\r\n"
    hours = v._parse_out(partial, [3.5, 7.0])
    assert len(hours) == 1
    assert all(b['rel'] is None for b in hours[0]['bands'])


# ═══════════════════════════════════════════════════════════════════════════
# resolve_ssn() -- repli NOAA -> SFI, sans jamais inventer de valeur.
# ═══════════════════════════════════════════════════════════════════════════

def test_resolve_ssn_utilise_le_smoothed_ssn_en_priorite(monkeypatch):
    monkeypatch.setattr(v, 'get_ssn_cached', lambda: {'ssn_smoothed': 123.4})
    monkeypatch.setattr(v, 'get_solar_cached', lambda: {'sfi': '999'})  # ne doit pas etre utilise
    assert v.resolve_ssn() == 123.4


def test_resolve_ssn_repli_sur_sfi_si_noaa_indisponible(monkeypatch):
    monkeypatch.setattr(v, 'get_ssn_cached', lambda: {})
    monkeypatch.setattr(v, 'get_solar_cached', lambda: {'sfi': '150'})
    result = v.resolve_ssn()
    assert result == v.sfi_to_ssn_fallback('150')
    assert result is not None


def test_resolve_ssn_none_si_aucune_donnee_solaire():
    # Aucune valeur inventee : si NOAA et le repli SFI sont tous deux
    # indisponibles, resolve_ssn() doit renvoyer None (predict() refuse
    # alors le calcul plutot que produire une prediction fausse en silence).
    import logx_voacap as v2
    orig_ssn, orig_solar = v2.get_ssn_cached, v2.get_solar_cached
    try:
        v2.get_ssn_cached = lambda: {}
        v2.get_solar_cached = lambda: {}
        assert v2.resolve_ssn() is None
    finally:
        v2.get_ssn_cached, v2.get_solar_cached = orig_ssn, orig_solar


def test_predict_sans_ssn_disponible_renvoie_erreur_claire(monkeypatch):
    monkeypatch.setattr(v, 'voacap_available', lambda: True)
    monkeypatch.setattr(v, 'resolve_ssn', lambda: None)
    result = v.predict(48.85, 2.35, 40.71, -74.00)
    assert result['ok'] is False
    assert 'error' in result


def test_predict_indisponible_hors_windows(monkeypatch):
    monkeypatch.setattr(v, 'voacap_available', lambda: False)
    result = v.predict(48.85, 2.35, 40.71, -74.00)
    assert result['ok'] is False


# ═══════════════════════════════════════════════════════════════════════════
# Integration reelle -- protegee, sautee silencieusement si le binaire
# vendu n'est pas present sur cette machine (CI non-Windows notamment).
# ═══════════════════════════════════════════════════════════════════════════

def test_predict_reel_avec_le_vrai_binaire():
    if not v.voacap_available():
        import pytest
        pytest.skip("voacapl.exe non disponible sur cette plateforme")
    result = v.predict(
        tx_lat=48.85, tx_lon=2.35, rx_lat=40.71, rx_lon=-74.00,
        month=8, year=2026, ssn=110.0, mode='CW',
        freqs_mhz=[7.0, 14.0, 21.0], tx_label='Paris', rx_label='New York',
    )
    assert result['ok'] is True
    assert 5000 < result['distance_km'] < 6500
    assert len(result['hours']) == 24
    assert all(0 <= b['rel'] <= 1 for h in result['hours'] for b in h['bands'] if b['rel'] is not None)


def test_predict_reel_arrondit_le_ssn_resolu_automatiquement():
    # Piege vu en verification navigateur reelle : sans ssn= explicite,
    # resolve_ssn() peut passer par sfi_to_ssn_fallback() (repli SFI, non
    # arrondi) et faire fuiter un float a 14 decimales jusque dans le
    # panneau LOGBOOK ("SSN 41.62087912087912"). Verifie ici sur le vrai
    # chemin de resolution automatique, pas seulement avec ssn= fourni.
    if not v.voacap_available():
        import pytest
        pytest.skip("voacapl.exe non disponible sur cette plateforme")
    # get_ssn_cached()/get_solar_cached() sont volontairement non bloquants
    # (rafraichissement en tache de fond) -- le cache est donc TOUJOURS
    # froid au tout debut d'un process pytest isole. On force ici un
    # remplissage synchrone (memes fonctions que le rafraichissement de
    # fond utilise) pour rendre le test deterministe plutot que de le
    # laisser se sauter silencieusement a chaque execution.
    from logx_clusters import fetch_ssn, fetch_solar_data
    fetch_ssn()
    fetch_solar_data()
    ssn = v.resolve_ssn()
    if ssn is None:
        import pytest
        pytest.skip("aucune donnee solaire disponible (reseau indisponible)")
    result = v.predict(tx_lat=48.85, tx_lon=2.35, rx_lat=40.71, rx_lon=-74.00, freqs_mhz=[14.0])
    if result['ok']:
        assert result['ssn'] == round(result['ssn'], 1)
