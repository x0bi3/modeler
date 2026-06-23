@echo off
REM AIO Modeler launcher.  Uses the project-local venv (.venv) and binds to
REM port 8767 so it doesn't collide with Mover (8766) or Teams (8080).
cd /d "%~dp0"
echo Starting AIO Modeler on http://127.0.0.1:8767/
start "" http://127.0.0.1:8767/
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8767 --reload
