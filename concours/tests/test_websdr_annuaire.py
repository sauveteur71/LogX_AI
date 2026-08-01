# -*- coding: utf-8 -*-
"""L'annuaire WebSDR refondu : la couche vivante, la curée, et l'URL d'écoute.

L'ÉCHANTILLON DE TEST EST RÉEL — trois entrées recopiées du vrai fichier de
rx.linkfanel.net le 01/08/2026, en-tête et virgule finale JS compris. La leçon
des TLE tapés de mémoire (checksum faux, douze tests tombés d'un coup) vaut
pour tout format tiers : on ne teste pas contre ce qu'on croit que la source
produit, on teste contre ce qu'elle a produit.

CE QUI EST TESTÉ EN PRIORITÉ : les gardes qui protègent l'EXPÉDITION — le
cache jamais écrasé par une réponse de portail captif, l'âge jamais menti — et
l'URL d'écoute, parce qu'une syntaxe fausse enverrait l'opérateur sur un
récepteur ouvert à la mauvaise fréquence sans qu'aucun message ne le dise.
"""
import json
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_websdr as ws   # noqa: E402

# Trois entrées RÉELLES du fichier linkfanel (01/08/2026), avec l'en-tête JS
# et la virgule finale — le format exact, pas une idéalisation.
ECHANTILLON = '''// KiwiSDR.com receiver list for dyatlov map maker
// Automatically generated from http://kiwisdr.com/public/

var kiwisdr_com =
[
\t{
\t\t"updated":"Saturday, 01-Aug-2026 04:29:49 GMT",
\t\t"id":"ec24b8cfd0db",
\t\t"status":"active",
\t\t"offline":"no",
\t\t"name":"80m Dipole | Chichester UK",
\t\t"url":"http://g8ure.ddns.net:8075",
\t\t"gps":"(50.85, -0.66)",
\t\t"loc":"Chichester UK",
\t\t"users":"3",
\t\t"users_max":"8",
\t\t"snr":"41,38",
\t\t"antenna":"80m Dipole",
\t\t"bands":"0-30000000"
\t},
\t{
\t\t"offline":"no",
\t\t"name":"AutreRadioAutreCulture 1 | TREMOLAT (24), FRANCE",
\t\t"url":"http://sdr.autreradioautreculture.com:8073",
\t\t"gps":"(44.869416, 0.835143)",
\t\t"loc":"TREMOLAT (24), FRANCE",
\t\t"users":"1",
\t\t"users_max":"6",
\t\t"snr":"44,37",
\t\t"antenna":"",
\t\t"bands":"0-30000000"
\t},
\t{
\t\t"offline":"yes",
\t\t"name":"KiwiSDR with Dipole | Szekesfehervar, Hungary",
\t\t"url":"http://kiwisdr.dfm.hu",
\t\t"gps":"(47.151966, 18.390057)",
\t\t"loc":"Szekesfehervar/Maroshegy, Hungary",
\t\t"users":"1",
\t\t"users_max":"8",
\t\t"snr":"35,37",
\t\t"antenna":"Dipole",
\t\t"bands":"0-30000000"
\t},
]
'''


# ─── Le parseur, sur le format réel ─────────────────────────────────────────

def test_le_parseur_lit_le_format_reel_virgule_finale_comprise():
    """La virgule finale JS avait fait échouer json.loads au premier essai —
    mesuré sur le vrai fichier."""
    s = ws.parser_kiwis(ECHANTILLON)
    assert len(s) == 3


def test_les_champs_sont_normalises():
    s = ws.parser_kiwis(ECHANTILLON)
    fr = [x for x in s if 'TREMOLAT' in x['nom']][0]
    assert fr['url'] == 'http://sdr.autreradioautreculture.com:8073'
    assert abs(fr['lat'] - 44.869416) < 1e-6
    assert abs(fr['lon'] - 0.835143) < 1e-6
    assert fr['users'] == 1 and fr['users_max'] == 6
    assert fr['en_ligne'] is True
    assert fr['type'] == 'kiwi'


def test_le_snr_garde_la_seconde_mesure():
    """« 41,38 » = deux mesures ; la seconde couvre la partie haute du
    spectre, celle qui renseigne un opérateur HF."""
    s = ws.parser_kiwis(ECHANTILLON)
    assert [x['snr'] for x in s] == [38, 37, 37]


def test_offline_yes_est_hors_ligne():
    s = ws.parser_kiwis(ECHANTILLON)
    hu = [x for x in s if 'Hungary' in x['nom']][0]
    assert hu['en_ligne'] is False


@pytest.mark.parametrize('gps', ['', 'n/a', '(999, 0)', '(50, 999)', 'GPS'])
def test_un_gps_invalide_donne_None_pas_un_point_faux(gps):
    txt = ECHANTILLON.replace('"(50.85, -0.66)"', json.dumps(gps))
    s = ws.parser_kiwis(txt)
    uk = [x for x in s if 'Chichester' in x['nom']][0]
    assert uk['lat'] is None and uk['lon'] is None


@pytest.mark.parametrize('texte', ['', None, '<html>Portail captif</html>',
                                   'var kiwisdr_com = pas du json'])
def test_une_reponse_inexploitable_rend_une_liste_vide(texte):
    assert ws.parser_kiwis(texte) == []


# ─── Le cache : jamais écrasé par du vide (contrainte d'expédition) ─────────

def _cache_valide(tmp_path):
    stations = ws.parser_kiwis(ECHANTILLON)
    from logx_storage import save_json_atomic
    save_json_atomic(str(tmp_path / ws.KIWI_CACHE), {
        'recupere': '2026-08-01T08:00:00', 'stations': stations})
    return stations


def test_un_portail_captif_n_ecrase_PAS_le_cache(tmp_path, monkeypatch):
    avant = _cache_valide(tmp_path)
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url',
                        lambda *a, **k: '<html>Connectez-vous</html>')
    r = ws.rafraichir_kiwis(str(tmp_path))
    assert r['ok'] is False
    assert ws.charger_kiwis(str(tmp_path))['stations'] == avant


def test_une_liste_anormalement_courte_est_refusee(tmp_path, monkeypatch):
    """Trois récepteurs quand le parc en compte ~850, c'est une réponse
    tronquée en plein téléchargement — pas un état du monde."""
    _cache_valide(tmp_path)
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: ECHANTILLON)
    r = ws.rafraichir_kiwis(str(tmp_path))
    assert r['ok'] is False and 'conservé' in r['error']


def test_un_reseau_mort_conserve_le_cache(tmp_path, monkeypatch):
    avant = _cache_valide(tmp_path)
    import logx_utils

    def boum(*a, **k):
        raise OSError('DNS muet')
    monkeypatch.setattr(logx_utils, 'fetch_url', boum)
    r = ws.rafraichir_kiwis(str(tmp_path))
    assert r['ok'] is False
    assert ws.charger_kiwis(str(tmp_path))['stations'] == avant


def test_l_age_est_calcule_ou_dit_inconnu():
    import datetime
    c = {'recupere': '2026-08-01T08:00:00', 'stations': [1]}
    a = ws.age_kiwis(c, maintenant=datetime.datetime(2026, 8, 1, 8, 10))
    assert a['secondes'] == 600 and a['etat'] == 'frais'
    a = ws.age_kiwis(c, maintenant=datetime.datetime(2026, 8, 1, 20, 0))
    assert a['etat'] == 'perime'
    assert ws.age_kiwis(None) is None
    assert ws.age_kiwis({'recupere': 'n importe quoi'}) is None


# ─── L'annuaire fusionné ────────────────────────────────────────────────────

def test_la_dedup_est_insensible_au_schema_et_au_slash():
    assert ws._url_cle('http://a.b:8073/') == ws._url_cle('https://A.B:8073')


def test_un_kiwi_cure_deja_dans_la_couche_vivante_n_apparait_qu_une_fois(tmp_path, monkeypatch):
    _cache_valide(tmp_path)
    monkeypatch.setattr(ws, 'stations_curees', lambda dossier=None: [
        {'nom': 'Doublon', 'url': 'http://sdr.autreradioautreculture.com:8073/',
         'type': 'kiwi', 'pays': 'FR'}])
    a = ws.annuaire({}, str(tmp_path))
    urls = [ws._url_cle(s['url']) for s in a['stations']]
    assert urls.count(ws._url_cle('http://sdr.autreradioautreculture.com:8073')) == 1


def test_la_distance_et_l_azimut_viennent_du_locator_config(tmp_path):
    _cache_valide(tmp_path)
    a = ws.annuaire({'locator': 'JN15XC'}, str(tmp_path))
    fr = [s for s in a['stations'] if 'TREMOLAT' in s['nom']][0]
    # Trémolat (Dordogne) est à quelques centaines de km de la Haute-Loire.
    assert 100 < fr['dist_km'] < 600
    assert 0 <= fr['azimut'] < 360


def test_sans_locator_pas_de_distance_mais_pas_d_erreur(tmp_path):
    _cache_valide(tmp_path)
    a = ws.annuaire({}, str(tmp_path))
    assert a['stations']
    assert all('dist_km' not in s for s in a['stations'])


def test_une_station_curee_se_place_par_locator_OU_par_lat_lon(tmp_path, monkeypatch):
    """Défaut trouvé en contrôlant le fichier livré : AUCUNE des 43 entrées
    curées n'avait de position, donc aucune n'apparaissait sur la carte ni ne
    pouvait être choisie comme « récepteur proche du DX ». Les pages des
    récepteurs publient tantôt une grille, tantôt des coordonnées : les deux
    doivent marcher — et une coordonnée aberrante ne doit RIEN placer plutôt
    que d'envoyer l'opérateur écouter à l'autre bout du monde."""
    _cache_valide(tmp_path)
    monkeypatch.setattr(ws, 'stations_curees', lambda dossier=None: [
        {'nom': 'PAR_LOCATOR', 'url': 'http://a.test:8901', 'type': 'websdr',
         'locator': 'JO32KF'},
        {'nom': 'PAR_LATLON', 'url': 'http://b.test:8901', 'type': 'websdr',
         'lat': 48.85, 'lon': 2.35},
        {'nom': 'LATITUDE_ABERRANTE', 'url': 'http://c.test:8901',
         'type': 'websdr', 'lat': 999, 'lon': 2.35},
        {'nom': 'LATLON_TEXTE', 'url': 'http://d.test:8901', 'type': 'websdr',
         'lat': 'quarante-huit', 'lon': 'deux'},
        {'nom': 'SANS_POSITION', 'url': 'http://e.test:8901', 'type': 'websdr'},
    ])
    par_nom = {s['nom']: s for s in ws.annuaire({'locator': 'JN15XC'},
                                               str(tmp_path))['stations']}
    assert par_nom['PAR_LOCATOR']['lat'] is not None
    assert par_nom['PAR_LATLON']['lat'] == 48.85
    assert par_nom['PAR_LATLON']['dist_km'] > 0
    for muet in ('LATITUDE_ABERRANTE', 'LATLON_TEXTE', 'SANS_POSITION'):
        assert par_nom[muet]['lat'] is None, muet
        assert 'dist_km' not in par_nom[muet], muet


def test_l_annuaire_est_serialisable_JSON(tmp_path):
    _cache_valide(tmp_path)
    json.dumps(ws.annuaire({'locator': 'JN15XC'}, str(tmp_path)),
               allow_nan=False)


def test_la_couche_curee_embarquee_est_saine():
    """Le fichier websdr_cures.json est suivi par git : chaque entrée doit
    porter URL et provenance — c'est le contrat de traçabilité du projet."""
    cures = ws.stations_curees()
    assert len(cures) >= 30
    for s in cures:
        assert s.get('url', '').startswith('http'), s
        assert s.get('provenance'), 'entrée sans provenance : %r' % s.get('nom')
    # Les françaises y sont — c'est le public du logiciel.
    assert sum(1 for s in cures if s.get('pays') == 'FR') >= 5


# ─── L'URL d'écoute ─────────────────────────────────────────────────────────

KIWI = {'type': 'kiwi', 'url': 'http://k.example:8073'}
CLASSIQUE = {'type': 'websdr', 'url': 'http://w.example:8901/'}


def test_kiwi_syntaxe_officielle_kHz_et_mode_colle():
    """« mykiwi/?f=7021.3cw » — vérifiée sur kiwisdr.com/info."""
    assert ws.url_ecoute(KIWI, 7021.3, 'CW') == 'http://k.example:8073/?f=7021.3cw'


def test_SSB_devient_LSB_ou_USB_selon_la_frequence():
    """Même convention que le pilotage CAT : LSB sous 10 MHz, USB au-dessus."""
    assert ws.url_ecoute(KIWI, 3750, 'SSB').endswith('?f=3750.0lsb')
    assert ws.url_ecoute(KIWI, 14250, 'SSB').endswith('?f=14250.0usb')


def test_le_numerique_reste_USB_meme_sous_10_MHz():
    """Le piège corrigé avant-hier dans le CAT : FT8 sur 40 m est en USB."""
    assert ws.url_ecoute(KIWI, 7074, 'FT8').endswith('?f=7074.0usb')


def test_websdr_classique_convention_tune():
    assert ws.url_ecoute(CLASSIQUE, 7021.3, 'CW') == 'http://w.example:8901/?tune=7021cw'


def test_sans_frequence_l_url_est_rendue_telle_quelle():
    assert ws.url_ecoute(KIWI) == 'http://k.example:8073'
    assert ws.url_ecoute(KIWI, 0) == 'http://k.example:8073'
    assert ws.url_ecoute(KIWI, 'abc') == 'http://k.example:8073'


def test_une_station_sans_url_rend_vide():
    assert ws.url_ecoute({}) == ''
    assert ws.url_ecoute(None) == ''


# ─── Le meilleur récepteur (« s'écouter ») ──────────────────────────────────

def _st(nom, snr, dist, en_ligne=True, users=0, users_max=8):
    return {'nom': nom, 'url': 'http://%s:8073' % nom, 'type': 'kiwi',
            'snr': snr, 'dist_km': dist, 'en_ligne': en_ligne,
            'users': users, 'users_max': users_max, 'lat': 45.0, 'lon': 3.0}


def test_le_meilleur_est_le_SNR_le_plus_haut_dans_le_rayon():
    s = ws.meilleur_recepteur([_st('a', 20, 100), _st('b', 45, 300),
                               _st('c', 50, 2000)])
    assert s['nom'] == 'b'   # c a le meilleur SNR mais est hors rayon


def test_un_recepteur_COMPLET_n_est_jamais_suggere():
    """Suggérer un récepteur plein enverrait l'opérateur sur une page qui le
    refuse — en plein contest."""
    s = ws.meilleur_recepteur([_st('plein', 60, 100, users=8, users_max=8),
                               _st('libre', 30, 200)])
    assert s['nom'] == 'libre'


def test_un_recepteur_hors_ligne_n_est_jamais_suggere():
    s = ws.meilleur_recepteur([_st('mort', 60, 100, en_ligne=False),
                               _st('vivant', 30, 200)])
    assert s['nom'] == 'vivant'


def test_rien_dans_le_rayon_rend_None_pas_le_moins_pire():
    assert ws.meilleur_recepteur([_st('loin', 50, 8000)]) is None
    assert ws.meilleur_recepteur([]) is None
    assert ws.meilleur_recepteur(None) is None


def test_pres_d_un_POINT_pour_ecouter_un_spot():
    """« Écouter ce spot » : le récepteur proche du DX, pas du QTH."""
    a = _st('pres-du-dx', 30, 9999)
    a['lat'], a['lon'] = 52.0, 13.0        # Berlin
    b = _st('pres-de-moi', 50, 10)
    b['lat'], b['lon'] = 45.0, 3.0
    s = ws.meilleur_recepteur([a, b], pres_de=(52.5, 13.4))
    assert s['nom'] == 'pres-du-dx'
