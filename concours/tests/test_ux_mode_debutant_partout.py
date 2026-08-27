# -*- coding: utf-8 -*-
"""Chantier « mode débutant/expert partout » : le bouton 🎚 de la barre de
statut (logx_statusbar.js) et le tag CSS .expert-only posé sur les réglages
avancés de logx_logbook.html / logx_logbook.js / logx_configuration.html.

Mécanisme réutilisé tel quel (déjà en place avant ce chantier, non retesté
ici) : logx_statusbar.js lit localStorage['rc_ui_mode'], et si === 'simple'
ajoute body.classList.add('simple-mode') + injecte la règle globale
« body.simple-mode .expert-only{display:none!important} ». Ce fichier vérifie
seulement que le NOUVEAU bouton de bascule existe et fonctionne, et que les
éléments avancés recensés portent bien la classe .expert-only (masquage CSS
pur — la fonction/l'endpoint sous-jacent restent toujours joignables).

Test textuel/structurel (lecture du fichier en Python, sans DOM ni
py_mini_racer), dans l'esprit de tests/test_release_ci_config.py.
"""
import os
import re

CONCOURS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATUSBAR_JS = os.path.join(CONCOURS_DIR, 'logx_statusbar.js')
LOGBOOK_HTML = os.path.join(CONCOURS_DIR, 'logx_logbook.html')
LOGBOOK_JS = os.path.join(CONCOURS_DIR, 'logx_logbook.js')
# EV-7 : la section IA de la modale VALIDATION (showValidation(), avec son
# expert-only) a été extraite vers ce fichier -- voir les 2 tests qui le
# lisent ci-dessous.
VERIF_PANEL_JS = os.path.join(CONCOURS_DIR, 'logx_verif_panel.js')
CONFIG_HTML = os.path.join(CONCOURS_DIR, 'logx_configuration.html')


def _lire(path):
    with open(path, encoding='utf-8') as f:
        src = f.read()
    # logx_configuration.html : script inline extrait vers
    # logx_configuration.js (10/08/2026).
    if path == CONFIG_HTML:
        js_path = os.path.join(CONCOURS_DIR, 'logx_configuration.js')
        if os.path.exists(js_path):
            with open(js_path, encoding='utf-8') as f:
                src += '\n' + f.read()
    return src


def _bloc_fonction(src, signature):
    """Corps de la fonction `signature` (ex. 'function toggleUiMode()'),
    délimité par comptage d'accolades — pour ne pas capturer les fonctions
    voisines ni les commentaires qui les précèdent."""
    deb = src.index(signature)
    ouv = src.index('{', deb)
    prof, i = 0, ouv
    while True:
        c = src[i]
        if c == '{':
            prof += 1
        elif c == '}':
            prof -= 1
            if prof == 0:
                return src[deb:i + 1]
        i += 1


# ── logx_statusbar.js : bouton 🎚 de bascule débutant/expert ────────────────

def test_statusbar_nouvel_item_present_et_bien_positionne():
    """L'item doit être inséré entre #rcsbUpdateItem et #rcsbReportItem (ordre
    demandé), et rester cliquable (curseur + title explicite) comme les
    autres items actionnables de la barre (#rcsbReportItem, #rcsbLayoutItem).
    (Ancre passée de #rcsbVersion à #rcsbUpdateItem après le retrait du tag de
    version installée — dédup, LOT 1 refonte cockpit.)"""
    src = _lire(STATUSBAR_JS)
    assert 'id="rcsbUiModeItem"' in src
    assert 'id="rcsbUiModeLabel"' in src
    i_avant = src.index('id="rcsbUpdateItem"')
    i_item = src.index('id="rcsbUiModeItem"')
    i_report = src.index('id="rcsbReportItem"')
    assert i_avant < i_item < i_report, (
        "l'item #rcsbUiModeItem doit être inséré entre #rcsbUpdateItem et "
        "#rcsbReportItem dans le template bar.innerHTML")
    bloc = src[i_item:i_item + 400]
    assert 'cursor:pointer' in bloc
    assert 'title="' in bloc


def test_statusbar_libelle_suit_rc_ui_mode_pas_lheuristique_du_callsign():
    """Le libellé doit refléter strictement localStorage['rc_ui_mode'] ===
    'simple' (uiModeIsSimple()), PAS l'heuristique getUiMode() de
    logx_configuration.html (callsign) : c'est ce choix qui est documenté
    comme délibéré dans le code, à ne pas régresser silencieusement."""
    src = _lire(STATUSBAR_JS)
    assert 'function uiModeIsSimple()' in src
    assert "localStorage.getItem('rc_ui_mode') === 'simple'" in src
    assert 'function refreshUiModeLabel()' in src
    assert "uiModeIsSimple() ? 'DÉBUTANT' : 'EXPERT'" in src
    corps = _bloc_fonction(src, 'function refreshUiModeLabel()')
    assert 'getUiMode' not in corps, (
        "refreshUiModeLabel() ne doit pas dupliquer l'heuristique "
        "getUiMode()/callsign de logx_configuration.html (le nom peut "
        "apparaître dans le commentaire qui PRÉCÈDE la fonction, c'est "
        "attendu — seul le CORPS de la fonction est vérifié ici)")


def test_statusbar_refresh_ui_mode_label_appelee_dans_boot_apres_insert():
    src = _lire(STATUSBAR_JS)
    i_boot = src.index('function boot()')
    bloc = src[i_boot:i_boot + 400]
    i_insert = bloc.index('insert();')
    i_refresh = bloc.index('refreshUiModeLabel();')
    assert i_insert < i_refresh, (
        "refreshUiModeLabel() doit être appelée APRÈS insert() dans boot() "
        "(le span #rcsbUiModeLabel n'existe pas avant)")


def test_statusbar_toggle_ui_mode_bascule_localstorage_et_recharge():
    src = _lire(STATUSBAR_JS)
    assert 'function toggleUiMode()' in src
    assert "localStorage.setItem('rc_ui_mode', uiModeIsSimple() ? 'expert' : 'simple')" in src
    i_toggle = src.index('function toggleUiMode()')
    bloc = src[i_toggle:i_toggle + 400]
    assert 'location.reload()' in bloc, (
        "toggleUiMode() doit recharger la page plutôt que réappliquer le "
        "masquage à chaud (garantit les éléments injectés dynamiquement ailleurs)")


def test_statusbar_clic_sur_litem_declenche_bien_toggle_ui_mode():
    src = _lire(STATUSBAR_JS)
    assert re.search(
        r"e\.target\.closest\('#rcsbUiModeItem'\)\)\s*toggleUiMode\(\)", src), (
        "le clic sur #rcsbUiModeItem doit appeler toggleUiMode() via "
        "l'écouteur délégué bar.addEventListener('click', ...)")


def test_statusbar_masquage_expert_only_reutilise_uiModeIsSimple():
    """Le mécanisme .expert-only existant (ligne ~679) n'a pas changé de
    comportement : il doit toujours passer par uiModeIsSimple(), réutilisée
    (pas dupliquée) par le libellé et le clic ci-dessus."""
    src = _lire(STATUSBAR_JS)
    assert "document.body.classList.add('simple-mode')" in src
    assert 'body.simple-mode .expert-only{display:none!important}' in src
    assert src.count('uiModeIsSimple()') >= 3, (
        "uiModeIsSimple() doit être réutilisée par le masquage, le libellé "
        "ET le toggle, pas réécrite à chaque endroit")


# ── logx_logbook.html : panneaux/modales/blocs avancés ──────────────────────

def _attribut_classe_id(src, class_attendue, id_attendu):
    """Vérifie que l'élément id_attendu porte exactement class_attendue,
    dans l'ordre class="..." puis id="..." utilisé partout dans ces fichiers."""
    motif = 'class="%s" id="%s"' % (class_attendue, id_attendu)
    return motif in src


def test_logbook_html_cw_panel2_est_expert_only():
    src = _lire(LOGBOOK_HTML)
    assert _attribut_classe_id(src, 'cw-panel expert-only', 'cwPanel2')


def test_logbook_html_filter_overlay_est_expert_only():
    src = _lire(LOGBOOK_HTML)
    assert _attribut_classe_id(src, 'shortcuts-overlay expert-only', 'filterOverlay')


def test_logbook_html_dup_overlay_est_expert_only():
    src = _lire(LOGBOOK_HTML)
    assert _attribut_classe_id(src, 'shortcuts-overlay expert-only', 'dupOverlay')


def test_logbook_html_bulk_resolve_overlay_est_expert_only():
    src = _lire(LOGBOOK_HTML)
    assert _attribut_classe_id(src, 'shortcuts-overlay expert-only', 'bulkResolveOverlay')


def test_logbook_html_net_overlay_est_expert_only():
    src = _lire(LOGBOOK_HTML)
    assert _attribut_classe_id(src, 'shortcuts-overlay expert-only', 'netOverlay')


def test_logbook_html_bm_filtre_est_expert_only():
    src = _lire(LOGBOOK_HTML)
    assert _attribut_classe_id(src, 'bm-filtre expert-only', 'bmFiltre')


def test_logbook_html_op_stats_bar_est_expert_only():
    src = _lire(LOGBOOK_HTML)
    assert _attribut_classe_id(src, 'op-stats-bar expert-only', 'opStatsBar')


def test_logbook_html_champs_adif_personnalises_expert_only_scan_qsl_reste_visible():
    """Seul le bloc CHAMPS ADIF PERSONNALISÉS (#editOverlay) doit être tagué
    — le bloc SCAN QSL PAPIER juste au-dessus partage la classe .edit-field
    mais doit rester visible en mode débutant."""
    src = _lire(LOGBOOK_HTML)
    assert re.search(
        r'<div class="edit-field expert-only"[^>]*>\s*'
        r'<div class="edit-lbl">CHAMPS ADIF PERSONNALISÉS</div>', src), (
        "le bloc CHAMPS ADIF PERSONNALISÉS doit porter class=\"edit-field expert-only\"")
    assert re.search(
        r'<div class="edit-field"[^>]*>\s*'
        r'<div class="edit-lbl">SCAN QSL PAPIER</div>', src), (
        "le bloc SCAN QSL PAPIER doit rester class=\"edit-field\" (SANS expert-only)")


# ── logx_logbook.js : entrées de menu + section IA de la modale VALIDATION ──

def test_logbookjs_menu_expert_only_fn_contient_les_4_fonctions_avancees():
    src = _lire(LOGBOOK_JS)
    assert ("const MENU_LB_EXPERT_ONLY_FN = new Set(['openFilterBuilder', "
            "'openDupFinder', 'openBulkResolve', 'openNetControl']);") in src


def test_logbookjs_build_lb_menu_applique_la_classe_expert_only():
    """buildLbMenu() (pas itemsMenuLogbook(), qui reste extraite telle quelle
    par tests/test_logbook_menu_debut_fin.py) doit construire class="...
    expert-only" pour tout data-fn présent dans MENU_LB_EXPERT_ONLY_FN."""
    src = _lire(LOGBOOK_JS)
    assert "MENU_LB_EXPERT_ONLY_FN.has(fn) ? 'expert-only' : ''" in src
    i_set = src.index('MENU_LB_EXPERT_ONLY_FN = new Set(')
    i_build = src.index('function buildLbMenu()')
    assert i_set < i_build, (
        "MENU_LB_EXPERT_ONLY_FN doit être défini avant buildLbMenu() qui l'utilise")


def test_logbookjs_itemsmenulogbook_forme_inchangee_pour_le_test_existant():
    """itemsMenuLogbook() elle-même ne doit PAS porter le tag expert-only —
    tests/test_logbook_menu_debut_fin.py l'extrait telle quelle via
    JSON.stringify() et ne doit pas voir sa forme changer."""
    src = _lire(LOGBOOK_JS)
    corps = _bloc_fonction(src, 'function itemsMenuLogbook(')
    assert 'expert-only' not in corps


def test_logbookjs_section_audit_ia_englobante_est_expert_only():
    """La classe expert-only doit être posée sur la <div class="shortcuts-row">
    ENGLOBANTE (bouton #aiAuditBtn + texte explicatif), pas sur le bouton
    seul — sinon le texte resterait affiché sans bouton en mode débutant.

    EV-7 : showValidation() (et sa section IA) vit désormais dans
    logx_verif_panel.js, plus dans logx_logbook.js."""
    src = _lire(VERIF_PANEL_JS)
    assert '<div class="shortcuts-row expert-only"' in src
    i_div = src.index('<div class="shortcuts-row expert-only"')
    i_btn = src.index('id="aiAuditBtn"')
    i_texte = src.index("l\\'IA relit le log et repère ce que les règles ne voient pas")
    assert i_div < i_btn < i_texte, (
        "le bouton #aiAuditBtn ET son texte explicatif doivent être dans la "
        "même <div class=\"shortcuts-row expert-only\"> englobante")


def test_logbookjs_controles_deterministes_validation_restent_visibles():
    """Les contrôles déterministes (comptage erreur/attention/info) au-dessus
    de la section IA ne doivent pas être masqués : seul l'ajout IA optionnel
    doit disparaître en mode débutant.

    EV-7 : showValidation() (et sa section IA) vit désormais dans
    logx_verif_panel.js, plus dans logx_logbook.js."""
    src = _lire(VERIF_PANEL_JS)
    i_head = src.index("QSO analysés")
    i_ai = src.index('<div class="shortcuts-row expert-only"')
    bloc_head = src[i_head:i_ai]
    assert 'expert-only' not in bloc_head


# ── logx_configuration.html : sections, form-grid, hub-cards ────────────────

def test_config_html_categories_avancees_sont_dans_expert_only_cats():
    """Depuis la refonte sidebar (08/08/2026), le hub de cartes a disparu —
    les catégories avancées sont marquées expert-only via _EXPERT_ONLY_CATS,
    lu par buildConfigSidebar() pour poser la classe sur chaque entrée de
    l'arborescence (générée en JS, donc pas de littéral class="...expert-only"
    à chercher dans le HTML statique comme avant — on vérifie directement la
    source unique de vérité). PowerGenius XL/ACOM fusionnés dans la catégorie
    'amp' le 15/08/2026 (rejet du schéma 6b/6c par F4GLD) : ce ne sont plus
    des catégories CONFIG_SECTIONS séparées, donc plus listées ici — leur
    masquage expert passe désormais par class="section expert-only" posée
    directement sur #ampPgxlFields/#ampAcomFields dans le HTML."""
    src = _lire(CONFIG_HTML)
    m = re.search(r"const _EXPERT_ONLY_CATS = new Set\(\[(.*?)\]\)", src)
    assert m, "_EXPERT_ONLY_CATS introuvable dans logx_configuration.html"
    cats = set(re.findall(r"'(\w+)'", m.group(1)))
    assert cats == {'relay', 'autostart', 'telemetry'}


def test_config_html_cat_civ_addr_field_est_expert_only():
    src = _lire(CONFIG_HTML)
    assert 'class="form-group expert-only" id="catCivAddrField" style="display:none"' in src


def test_config_html_cat_omnirig_flex_icomremote_fields_sont_expert_only():
    src = _lire(CONFIG_HTML)
    for field_id in ('catOmnirigFields', 'catFlexFields', 'catIcomRemoteFields'):
        motif = 'id="%s" class="form-grid expert-only"' % field_id
        assert motif in src, field_id


def test_config_html_section_so2r_deuxieme_radio_est_expert_only():
    """Le pilotage CAT de base (radio 1) n'est pas concerné : seul le bloc
    SO2R — DEUXIÈME RADIO doit être tagué."""
    src = _lire(CONFIG_HTML)
    assert re.search(
        r'<div class="section expert-only">.{0,700}?SO2R — DEUXIÈME RADIO',
        src, re.S)


def test_config_html_section_mysql_partage_est_expert_only():
    """Cloud Sync et Synchro LAN, juste au-dessus, doivent rester visibles
    (non vérifié ici, mais MYSQL PARTAGÉ doit lui être masqué)."""
    src = _lire(CONFIG_HTML)
    assert re.search(
        r'<div class="section expert-only">.{0,700}?MYSQL PARTAGÉ',
        src, re.S)


def test_config_html_section_mqtt_est_expert_only():
    src = _lire(CONFIG_HTML)
    assert re.search(
        r'<div class="section expert-only">.{0,700}?PUBLICATION MQTT',
        src, re.S)
