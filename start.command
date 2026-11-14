#!/bin/bash
# Double-click to start DronePendantSpeakerTool. First run sets up a private Python environment in .venv.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "First run: creating .venv and installing numpy, trimesh, manifold3d, lxml, networkx ..."
  python3 -m venv .venv || { echo "Could not create .venv"; read -r -p "Press Return to close."; exit 1; }
  .venv/bin/python -m pip install --upgrade pip -q
  .venv/bin/python -m pip install -r requirements.txt || { echo "Install failed - see the error above."; read -r -p "Press Return to close."; exit 1; }
fi
echo "Starting at http://127.0.0.1:8766  (Ctrl-C to stop)"
.venv/bin/python run.py
read -r -p "Stopped. Press Return to close."
