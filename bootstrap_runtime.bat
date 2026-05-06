@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem ============================================================
rem Ako runtime bootstrap v13
rem - First-run visible through VBS launcher.
rem - DOES NOT pip-install requirements.txt at user runtime.
rem   Reason: Ako-ai.exe is already built by PyInstaller.
rem - Prepares bundled Python only as a local runtime fallback.
rem - Checks/installs Ollama and pulls the model.
rem ============================================================

set "APP_NAME=Ako-ai"
set "MODEL_NAME=exaone3.5:7.8b"
set "SCRIPT_DIR=%~dp0"
set "RUNTIME_DIR=%LOCALAPPDATA%\Ako-ai\runtime"
set "PY_DIR=%RUNTIME_DIR%\python312"
set "PY_EXE=%PY_DIR%\python.exe"
set "TMP=%RUNTIME_DIR%\tmp"
set "TEMP=%RUNTIME_DIR%\tmp"
set "PY_ZIP_NAME=python-3.12.10-embed-amd64.zip"
set "PY_ZIP=%SCRIPT_DIR%runtime_assets\%PY_ZIP_NAME%"
set "LOG=%RUNTIME_DIR%\bootstrap_runtime.log"
set "FLAG=%RUNTIME_DIR%\bootstrap_ok.flag"
set "OLLAMA_EXE="
set "NO_PAUSE=0"

if /I "%~1"=="--no-pause" set "NO_PAUSE=1"

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" >nul 2>nul
if not exist "%TMP%" mkdir "%TMP%" >nul 2>nul

call :log INFO "Starting Ako runtime bootstrap v13"

call :prepare_python
if errorlevel 1 goto fail

call :check_ollama
if errorlevel 1 goto fail

call :ensure_ollama_server
if errorlevel 1 goto fail

call :check_model
if errorlevel 1 goto fail

> "%FLAG%" echo ok
call :log INFO "Runtime bootstrap completed"
exit /b 0

:prepare_python
call :log INFO "Checking bundled Python"

if exist "%PY_EXE%" (
    "%PY_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)" >nul 2>nul
    if not errorlevel 1 (
        call :log INFO "Bundled Python OK: %PY_EXE%"
        exit /b 0
    )
    call :log WARN "Existing bundled Python is invalid. Recreating."
    rmdir /s /q "%PY_DIR%" >nul 2>nul
)

if not exist "%PY_ZIP%" (
    call :log WARN "Bundled Python zip not found. Skipping bundled Python setup."
    call :log WARN "%PY_ZIP%"
    exit /b 0
)

call :log INFO "Extracting bundled Python zip"
if not exist "%PY_DIR%" mkdir "%PY_DIR%" >nul 2>nul

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%PY_ZIP%' -DestinationPath '%PY_DIR%' -Force" >>"%LOG%" 2>&1
if errorlevel 1 (
    call :log ERROR "Failed to extract Python zip"
    exit /b 1
)

if exist "%PY_DIR%\python312._pth" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p='%PY_DIR%\python312._pth'; (Get-Content -LiteralPath $p) -replace '^#import site','import site' | Set-Content -LiteralPath $p -Encoding ASCII" >>"%LOG%" 2>&1
)

"%PY_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)" >nul 2>nul
if errorlevel 1 (
    call :log ERROR "Extracted Python is not Python 3.12"
    "%PY_EXE%" --version >>"%LOG%" 2>&1
    exit /b 1
)

call :log INFO "Bundled Python ready"
exit /b 0

:check_ollama
call :log INFO "Checking Ollama"

for /f "delims=" %%P in ('where ollama 2^>nul') do (
    set "OLLAMA_EXE=%%P"
    goto ollama_found
)

if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
    goto ollama_found
)

call :log WARN "Ollama not found. Trying winget install."
winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements >>"%LOG%" 2>&1

for /f "delims=" %%P in ('where ollama 2^>nul') do (
    set "OLLAMA_EXE=%%P"
    goto ollama_found
)

if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
    goto ollama_found
)

call :log WARN "winget could not install Ollama. Trying direct download."
set "OLLAMA_INSTALLER=%RUNTIME_DIR%\OllamaSetup.exe"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%OLLAMA_INSTALLER%'" >>"%LOG%" 2>&1

if exist "%OLLAMA_INSTALLER%" (
    call :log INFO "Opening Ollama installer. Complete the installer, then this window will continue."
    start /wait "" "%OLLAMA_INSTALLER%"
)

for /f "delims=" %%P in ('where ollama 2^>nul') do (
    set "OLLAMA_EXE=%%P"
    goto ollama_found
)

if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
    goto ollama_found
)

call :log ERROR "Ollama is still not available."
call :log ERROR "Install Ollama manually from https://ollama.com/download and run Ako again."
exit /b 1

:ollama_found
call :log INFO "Ollama found: %OLLAMA_EXE%"
exit /b 0

:ensure_ollama_server
call :log INFO "Checking Ollama server"
"%OLLAMA_EXE%" list >nul 2>nul
if not errorlevel 1 (
    call :log INFO "Ollama server OK"
    exit /b 0
)

call :log WARN "Ollama server not responding. Starting ollama serve in background."
start "Ako Ollama Server" /min "%OLLAMA_EXE%" serve
timeout /t 5 /nobreak >nul

"%OLLAMA_EXE%" list >nul 2>nul
if errorlevel 1 (
    call :log ERROR "Ollama server did not respond."
    exit /b 1
)

call :log INFO "Ollama server started"
exit /b 0

:check_model
call :log INFO "Checking Ollama model: %MODEL_NAME%"

"%OLLAMA_EXE%" list | findstr /I /C:"%MODEL_NAME%" >nul 2>nul
if not errorlevel 1 (
    call :log INFO "Model already exists"
    exit /b 0
)

call :log INFO "Pulling Ollama model: %MODEL_NAME%"
call :log INFO "This can take a long time on first run."

"%OLLAMA_EXE%" pull "%MODEL_NAME%" >>"%LOG%" 2>&1
if errorlevel 1 (
    call :log ERROR "ollama pull failed: %MODEL_NAME%"
    exit /b 1
)

call :log INFO "Model ready"
exit /b 0

:log
set "LV=%~1"
set "MSG=%~2"
echo [%LV%] %MSG%
>>"%LOG%" echo [%DATE% %TIME%] [%LV%] %MSG%
exit /b 0

:fail
if exist "%FLAG%" del /q "%FLAG%" >nul 2>nul
call :log ERROR "Bootstrap failed"
if "%NO_PAUSE%"=="0" pause
exit /b 1
