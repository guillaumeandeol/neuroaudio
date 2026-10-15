#!/bin/bash
# Lance VegahSpatial (macOS / Linux). Premier lancement : crée .venv et installe les bibliothèques.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv || { echo "Python 3 est requis (https://www.python.org)"; read -p "Entrée pour fermer"; exit 1; }
  .venv/bin/pip install --upgrade pip >/dev/null
  .venv/bin/pip install -r requirements.txt || { echo "Échec de l'installation"; read -p "Entrée pour fermer"; exit 1; }
fi
exec .venv/bin/python -m vegah_spatial "$@"
