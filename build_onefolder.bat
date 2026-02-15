@echo off
setlocal

REM --- ensure venv ---
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt

REM --- build (onedir recommended) ---
pyinstaller --noconfirm --clean --onedir --name "Ako-ai" --windowed app.py

echo.
echo Build done: dist\Ako-ai\Ako-ai.exe
endlocal
