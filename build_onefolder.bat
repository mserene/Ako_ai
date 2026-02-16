@echo off
setlocal

cd /d "%~dp0"

REM --- Ensure venv (Python 3.12 recommended) ---
if not exist ".venv\Scripts\python.exe" (
  echo [INFO] Creating venv...
  py -3.12 -m venv .venv 2>nul
  if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
  )
)

REM --- Install deps in venv ---
call ".venv\Scripts\activate"
python -m pip install -U pip setuptools wheel
python -m pip install -r requirements.txt

REM --- Clean output ---
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"

REM --- Build using spec (options must live in .spec) ---
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean "Ako-ai.spec"

echo.
echo Build done: dist\Ako-ai\Ako-ai.exe
endlocal
