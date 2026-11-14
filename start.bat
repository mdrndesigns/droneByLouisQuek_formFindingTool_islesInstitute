@echo off
rem Double-click to start DronePendantSpeakerTool on Windows. First run sets up .venv.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo First run: installing numpy, trimesh, manifold3d, lxml, networkx ...
  py -3 -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt || (echo Install failed. & pause & exit /b 1)
)
echo Starting at http://127.0.0.1:8766  (Ctrl-C to stop)
.venv\Scripts\python run.py
pause
