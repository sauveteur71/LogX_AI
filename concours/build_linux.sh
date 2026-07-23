#!/bin/bash
# ============================================================
#  LogX AI - Construction de l'executable Linux
#  Produit : dist/LogXAI (autonome, sans Python)
#  A LANCER SOUS LINUX (PyInstaller ne cross-compile pas).
#  Fonctionne aussi sur Raspberry Pi (build sur le Pi lui-meme).
# ============================================================
set -e
cd "$(dirname "$0")"

echo "[1/4] Vérification de Python 3..."
command -v python3 >/dev/null 2>&1 || { echo "Python 3 requis : sudo apt install python3 python3-pip"; exit 1; }

echo "[2/4] Installation des dépendances (requirements.txt)..."
# Indispensable AVANT PyInstaller : il n'embarque que les bibliothèques
# importables au moment du build. Sans cette étape, un poste frais produit
# un binaire sans CAT série, sans keyer vocal, sans EME — silencieusement.
# (sounddevice a besoin de la lib système PortAudio : sudo apt install libportaudio2)
python3 -m pip install --quiet -r requirements.txt

echo "[3/4] Installation de PyInstaller si nécessaire..."
python3 -m pip install --quiet --upgrade pyinstaller

echo "[4/4] Construction de l'exécutable..."
python3 -m PyInstaller --noconfirm --clean logx.spec

echo
if [ -f "dist/LogXAI" ]; then
  chmod +x dist/LogXAI
  echo "============================================================"
  echo "  OK ! Exécutable prêt : dist/LogXAI"
  echo "  Lance-le avec :  ./dist/LogXAI"
  echo "  (le navigateur s'ouvre tout seul sur la configuration)"
  echo "============================================================"
else
  echo "[ERREUR] La construction a échoué. Vérifie les messages ci-dessus."
fi
