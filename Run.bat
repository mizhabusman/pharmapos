@echo off
setlocal
REM ==============================================================
REM  Run.bat - one-click launcher for the Pharmacy Management app.
REM
REM  Builds the inventory database on first run, starts the backend
REM  (FastAPI) and frontend (Vite) each in their own window, then
REM  opens the app in the default browser.
REM
REM  Just double-click this file.
REM ==============================================================

set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"

REM --- Sanity check: Python virtual environment must exist ---
if not exist "%VENV_PY%" (
  echo [ERROR] Python virtual environment not found at:
  echo         %VENV_PY%
  echo         Create it and install backend\requirements.txt first.
  pause
  exit /b 1
)

REM --- First run: install frontend dependencies if missing ---
if not exist "%ROOT%frontend\node_modules" (
  echo [SETUP] Installing frontend dependencies ^(one time^)...
  pushd "%ROOT%frontend"
  call npm install
  popd
)

REM --- Build the inventory DB if the 'inventory' table isn't present ---
REM (checks the TABLE, not just the file, so a bills-only DB left behind by an
REM  early server start can't cause the build to be skipped -> empty store.)
"%VENV_PY%" -c "import sqlite3; sqlite3.connect(r'%ROOT%data\pharmacy_inventory.db').execute('SELECT 1 FROM inventory LIMIT 1')" 2>nul
if errorlevel 1 (
  echo [SETUP] Building inventory database from CSV...
  pushd "%ROOT%backend"
  "%VENV_PY%" scripts\db_setup.py
  popd
)

REM --- Start the backend (FastAPI on http://localhost:8000) ---
echo [START] Backend  -^> http://localhost:8000
start "Pharmacy Backend" /D "%ROOT%backend" cmd /k ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

REM --- Start the frontend (Vite dev server, pinned to :5173) ---
echo [START] Frontend -^> http://localhost:5173
start "Pharmacy Frontend" /D "%ROOT%frontend" cmd /k npm run dev -- --port 5173 --strictPort

REM --- Give the servers a few seconds, then open the browser ---
echo [WAIT]  Giving the servers a moment to start up...
timeout /t 6 /nobreak >nul
start "" http://localhost:5173

echo.
echo ==============================================================
echo  App launched. Two server windows are now open:
echo    - "Pharmacy Backend"  (close it to stop the API)
echo    - "Pharmacy Frontend" (close it to stop the web app)
echo  The app should open at http://localhost:5173
echo ==============================================================
endlocal
