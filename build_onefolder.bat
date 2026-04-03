@echo off
setlocal

cd /d "%~dp0"

REM --- Ollama 설치 확인 및 자동 설치 ---
where ollama >nul 2>&1
if errorlevel 1 (
  echo [INFO] Ollama가 설치되어 있지 않아요. 자동으로 설치할게요...
  powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://ollama.com/install.sh' -OutFile '%TEMP%\ollama-install.ps1'"
  REM Windows installer 직접 다운로드
  powershell -NoProfile -Command ^
    "$url='https://ollama.com/download/OllamaSetup.exe'; $out='%TEMP%\OllamaSetup.exe'; Invoke-WebRequest -Uri $url -OutFile $out; Start-Process -FilePath $out -ArgumentList '/S' -Wait"
  echo [INFO] Ollama 설치 완료
) else (
  echo [INFO] Ollama 이미 설치됨
)

REM --- exaone 모델 확인 및 자동 다운로드 ---
ollama list 2>nul | findstr "exaone3.5" >nul 2>&1
if errorlevel 1 (
  echo [INFO] exaone3.5:7.8b 모델이 없어요. 다운로드할게요... (약 5GB, 시간이 걸려요)
  ollama pull exaone3.5:7.8b
  echo [INFO] 모델 다운로드 완료
) else (
  echo [INFO] exaone3.5:7.8b 모델 이미 있음
)

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
