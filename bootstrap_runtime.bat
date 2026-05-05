@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem ============================================================
rem Ako runtime bootstrap v10
rem - First-run friendly: creates bootstrap_ok.flag on success.
rem - ASCII-only BAT to avoid CMD encoding/parsing issues.
rem - Uses bundled Python embed zip first.
rem - Prepares pip/packages for runtime.
rem - Checks Ollama and model.
rem ============================================================

set "APP_NAME=Ako-ai"
set "MODEL_NAME=exaone3.5:7.8b"
set "SCRIPT_DIR=%~dp0"
set "RUNTIME_DIR=%LOCALAPPDATA%\Ako-ai\runtime"
set "PY_DIR=%RUNTIME_DIR%\python312"
set "PY_EXE=%PY_DIR%\python.exe"
set "PIP_CACHE_DIR=%RUNTIME_DIR%\pip_cache"
set "TMP=%RUNTIME_DIR%\tmp"
set "TEMP=%RUNTIME_DIR%\tmp"
set "PY_ZIP_NAME=python-3.12.10-embed-amd64.zip"
set "PY_ZIP=%SCRIPT_DIR%runtime_assets\%PY_ZIP_NAME%"
set "GET_PIP_ASSET=%SCRIPT_DIR%runtime_assets\get-pip.py"
set "GET_PIP=%RUNTIME_DIR%\get-pip.py"
set "LOG=%RUNTIME_DIR%\bootstrap_runtime.log"
set "FLAG=%RUNTIME_DIR%\bootstrap_ok.flag"
set "NO_PAUSE=0"

if /I "%~1"=="--no-pause" set "NO_PAUSE=1"

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" >nul 2>nul
if not exist "%TMP%" mkdir "%TMP%" >nul 2>nul
if not exist "%PIP_CACHE_DIR%" mkdir "%PIP_CACHE_DIR%" >nul 2>nul

call :log INFO "Starting Ako runtime bootstrap v10"

call :prepare_python
if errorlevel 1 goto fail

call :prepare_pip
if errorlevel 1 goto fail

call :install_requirements
if errorlevel 1 goto fail

call :check_ollama
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
    call :log ERROR "Bundled Python zip not found: %PY_ZIP%"
    exit /b 1
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

:prepare_pip
call :log INFO "Checking pip"
"%PY_EXE%" -m pip --version >nul 2>nul
if not errorlevel 1 (
    call :log INFO "pip OK"
    exit /b 0
)

call :log INFO "Installing pip"

if exist "%GET_PIP_ASSET%" (
    copy /Y "%GET_PIP_ASSET%" "%GET_PIP%" >nul 2>nul
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%GET_PIP%'" >>"%LOG%" 2>&1
)

if not exist "%GET_PIP%" (
    call :log ERROR "get-pip.py not found and could not be downloaded"
    exit /b 1
)

"%PY_EXE%" "%GET_PIP%" --no-warn-script-location --no-cache-dir >>"%LOG%" 2>&1
if errorlevel 1 (
    call :log ERROR "pip install failed"
    exit /b 1
)

"%PY_EXE%" -m pip --version >nul 2>nul
if errorlevel 1 (
    call :log ERROR "pip still not available"
    exit /b 1
)

call :log INFO "pip ready"
exit /b 0

:install_requirements
if not exist "%SCRIPT_DIR%requirements.txt" (
    call :log WARN "requirements.txt not found. Skipping package install."
    exit /b 0
)

call :log INFO "Installing Python requirements"
"%PY_EXE%" -m pip install --no-cache-dir --cache-dir "%PIP_CACHE_DIR%" -r "%SCRIPT_DIR%requirements.txt" >>"%LOG%" 2>&1
if errorlevel 1 (
    call :log ERROR "requirements install failed"
    exit /b 1
)

call :log INFO "requirements installed"
exit /b 0

:check_ollama
call :log INFO "Checking Ollama"
where ollama >nul 2>nul
if not errorlevel 1 (
    call :log INFO "Ollama found in PATH"
    exit /b 0
)

if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
    call :log INFO "Ollama found in LocalAppData"
    exit /b 0
)

call :log ERROR "Ollama not found"
call :log ERROR "Install Ollama manually from https://ollama.com/download"
exit /b 1

:check_model
call :log INFO "Checking Ollama model: %MODEL_NAME%"
ollama list | findstr /I /C:"%MODEL_NAME%" >nul 2>nul
if not errorlevel 1 (
    call :log INFO "Model already exists"
    exit /b 0
)

call :log INFO "Pulling Ollama model: %MODEL_NAME%"
ollama pull "%MODEL_NAME%" >>"%LOG%" 2>&1
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
