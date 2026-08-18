# -*- coding: utf-8 -*-
"""Sûreté d'émission FT8 : le PTT part-il toujours en OFF, et l'audio s'arrête-t-il ?

La revue adversariale du 18/08/2026 a relevé, à juste titre, que la partie la
plus DANGEREUSE du correctif précédent était livrée sans un seul test : quinze
tests couvraient l'horloge et le DT, zéro couvrait la chaîne PTT. Ce fichier
comble ce trou.

Ce qu'on cherche à empêcher, par ordre de gravité :
  1. une demande d'émission partie sans qu'aucun PTT OFF ne suive
     (émission continue non maîtrisée) ;
  2. une coupure annoncée à l'écran alors que l'audio continue d'être injecté
     dans la radio — sur un poste en VOX, cela suffit à le remettre en
     émission tout seul juste après notre PTT OFF ;
  3. une alarme rouge « la radio est peut-être encore en émission » affichée à
     quelqu'un qui n'a simplement pas configuré de pilotage radio. Une alarme
     qui crie pour rien finit par ne plus être lue — c'est ainsi qu'on rate la
     vraie.

Les fonctions sont EXTRAITES de logx_ft8.html et exécutées telles quelles :
aucune réécriture de la logique dans le test.
"""
import json
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT8_HTML = os.path.join(CONCOURS, 'logx_ft8.html')

py_mini_racer = pytest.importorskip('py_mini_racer')


def _lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def _extraire_fonction(src, nom):
    """Extrait la fonction par comptage d'accolades. Gère les deux formes
    présentes dans le fichier : `function nom(...)` et
    `window.nom = async function(...)` — oublier la seconde ferait échouer le
    test sur stopEmission, qui est justement l'une des plus importantes."""
    for motif in ('function ' + nom, 'window.' + nom + ' ='):
        debut = src.find(motif)
        if debut >= 0:
            break
    assert debut >= 0, f'fonction {nom} introuvable'
    debut = src.rfind('\n', 0, debut) + 1   # remonter en début de ligne
    prof, i = 0, src.index('{', debut)
    while True:
        if src[i] == '{':
            prof += 1
        elif src[i] == '}':
            prof -= 1
            if prof == 0:
                return src[debut:i + 1]
        i += 1


def _ctx(reponses):
    """Monte un environnement minimal et y injecte les VRAIES fonctions.

    `reponses` : liste de dicts renvoyés successivement par /rig/ptt, ou la
    chaîne 'reseau_ko' pour simuler un fetch qui lève."""
    src = _lire(FT8_HTML)
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var __appels = [];        // ce qui est réellement parti vers /rig/ptt
      var __alarme = '';
      var __stopVisible = false;
      var __reponses = [];
      var pttDemande = false, chienDeGardePtt = null;
      // setTimeout immédiat : py_mini_racer n'a pas de boucle d'événements, et
      // ce qu'on teste ici est l'ENCHAÎNEMENT des appels, pas leur cadence.
      function setTimeout(fn, ms){ fn(); return 0; }
      function clearTimeout(){}
      var console = { warn: function(){}, error: function(){} };
      function fetch(url, opt){
        var corps = JSON.parse((opt && opt.body) || '{}');
        __appels.push(corps.on);
        var rep = __reponses.shift();
        if(rep === 'reseau_ko') return Promise.reject(new Error('reseau'));
        return Promise.resolve({
          status: rep.status || 200,
          json: function(){ return Promise.resolve(rep); },
        });
      }
      function majBoutonStop(){ __stopVisible = pttDemande; }
      function alarmePtt(msg){ __alarme = msg || ''; }
      var document = { getElementById: function(){ return null; } };
    """)
    ctx.eval('__reponses = ' + json.dumps(reponses) + ';')
    ctx.eval(_extraire_fonction(src, 'pttOn'))
    ctx.eval(_extraire_fonction(src, 'relacherPtt'))
    return ctx


def _etat(ctx):
    return json.loads(ctx.eval(
        'JSON.stringify({appels: __appels, alarme: __alarme, '
        'pttDemande: pttDemande, stopVisible: __stopVisible})'))


# ─── 1. Le PTT OFF part TOUJOURS, quoi qu'ait répondu le serveur ────────────

def test_un_refus_du_serveur_declenche_quand_meme_un_relachement():
    """LE bug d'origine (F4GLD, 18/08/2026) : « PTT refusé » affiché ET
    l'émetteur bloqué en émission. Le serveur avait déjà commandé la radio
    avant de conclure à l'échec ; le logiciel sortait sans jamais relâcher."""
    ctx = _ctx([{'ok': False}, {'ok': True}])
    ctx.eval('var __fait = false; pttOn(true).then(function(){ __fait = true; });')
    assert ctx.eval('__fait') is True
    ctx.eval('var __r = null; relacherPtt(4).then(function(v){ __r = v; });')
    etat = _etat(ctx)
    assert etat['appels'] == [True, False], 'un PTT OFF doit suivre le PTT ON'
    assert ctx.eval('__r') is True
    assert etat['pttDemande'] is False
    assert etat['alarme'] == ''


def test_le_relachement_insiste_puis_alarme():
    """Un relâchement raté laisse la radio en l'air : on réessaie. Si rien n'y
    fait, l'alarme doit paraître — c'est le seul cas où elle est légitime."""
    ctx = _ctx([{'ok': False}] * 4)
    # On part d'une émission EN COURS : c'est l'état réel quand relacherPtt()
    # est appelé (pttOn(true) l'a posé). Sans ça le test vérifierait un
    # scénario qui ne se produit jamais.
    ctx.eval('pttDemande = true;')
    ctx.eval('var __r = null; relacherPtt(4).then(function(v){ __r = v; });')
    etat = _etat(ctx)
    assert etat['appels'] == [False] * 4, '4 tentatives attendues'
    assert ctx.eval('__r') is False
    assert 'PEUT-ÊTRE ENCORE EN ÉMISSION' in etat['alarme']
    assert etat['pttDemande'] is True, "l'état de sûreté doit rester levé"


def test_un_echec_reseau_ne_fait_pas_abandonner():
    """fetch qui lève ne prouve RIEN sur l'état de la radio : la requête a pu
    arriver. On réessaie, on n'abandonne pas."""
    ctx = _ctx(['reseau_ko', 'reseau_ko', {'ok': True}])
    ctx.eval('var __r = null; relacherPtt(4).then(function(v){ __r = v; });')
    assert ctx.eval('__r') is True
    assert _etat(ctx)['appels'] == [False, False, False]


# ─── 2. Pas d'alarme quand aucun PTT n'a jamais été commandé ────────────────

def test_pas_de_pilotage_radio_ne_declenche_aucune_alarme():
    """Le serveur répond non_engage : AUCUN pilote n'a été appelé, la radio
    n'a pas pu être mise en émission par nous. Avant correctif, ce cas — très
    courant, quiconque passe en émission au micro ou en VOX — produisait 4
    tentatives puis l'alarme rouge « coupe manuellement ». Terrifiant, et
    faux."""
    ctx = _ctx([{'ok': False, 'non_engage': True}])
    ctx.eval('var __r = null; relacherPtt(4).then(function(v){ __r = v; });')
    etat = _etat(ctx)
    assert ctx.eval('__r') is True
    assert etat['alarme'] == '', 'aucune alarme si la radio n\'a jamais été commandée'
    assert etat['appels'] == [False], 'une seule tentative suffit, insister est absurde'
    assert etat['pttDemande'] is False


# ─── 3. L'audio d'émission est réellement coupé ─────────────────────────────

def test_stop_emission_coupe_l_audio_avant_de_relacher_le_ptt():
    """Constat de revue : STOP relâchait le PTT et laissait la forme d'onde
    continuer à être jouée dans la carte son — donc dans l'entrée modulation
    du poste. L'écran annonçait « Émission coupée » pendant que le signal
    continuait, et sur un poste en VOX cela le remet en émission tout seul.

    L'ordre compte : l'audio D'ABORD, le PTT ensuite."""
    src = _lire(FT8_HTML)
    corps = _extraire_fonction(src, 'stopEmission')
    assert 'couperAudioTx()' in corps, 'stopEmission doit couper l\'audio'
    assert corps.index('couperAudioTx()') < corps.index('relacherPtt'), \
        "l'audio doit être coupé AVANT le relâchement du PTT"


def test_le_chien_de_garde_coupe_aussi_l_audio():
    """Même exigence pour le relâchement automatique : sinon le filet de
    sécurité laisse passer exactement ce qu'il doit retenir."""
    corps = _extraire_fonction(_lire(FT8_HTML), 'armerChienDeGarde')
    assert 'couperAudioTx()' in corps


def test_la_source_audio_est_bien_memorisee_pour_pouvoir_etre_coupee():
    """couperAudioTx() ne peut rien arrêter si jouerForme() ne lui laisse pas
    de prise sur la source en cours."""
    corps = _extraire_fonction(_lire(FT8_HTML), 'jouerForme')
    # Renommé le 18/08/2026 : la prise UNIQUE est devenue un ENSEMBLE. Une
    # seule variable était écrasée par une seconde émission programmée sur le
    # même créneau, et couperAudioTx() n abordait alors que la dernière onde.
    assert 'sourcesTxVivantes.add(src)' in corps


def test_echap_est_bien_cable_sur_la_coupure():
    """Même geste que le STOP CW du LOGBOOK : la revue de sûreté exige un
    raccourci, pas seulement un bouton."""
    src = _lire(FT8_HTML)
    assert re.search(r"key\s*===\s*'Escape'[^\n]*stopEmission|Escape[\s\S]{0,200}stopEmission", src)
