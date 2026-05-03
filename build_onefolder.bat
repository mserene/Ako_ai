@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "DIST_ROOT=dist"
set "APP_DIR=dist\Ako-ai"
set "APP_BACKUP=dist\Ako-ai_backup"
set "BUILD_OK=0"
set "PYTHON_EXE="
set "VENV_PY=.venv\Scripts\python.exe"
set "OLLAMA_MODEL=exaone3.5:7.8b"

echo [INFO] Starting Ako-ai build.

REM --- Check or install Ollama ---
where ollama >nul 2>&1
if errorlevel 1 (
  echo [INFO] Ollama not found. Installing Ollama...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$url='https://ollama.com/download/OllamaSetup.exe'; $out=Join-Path $env:TEMP 'OllamaSetup.exe'; Invoke-WebRequest -Uri $url -OutFile $out; $p=Start-Process -FilePath $out -ArgumentList '/S' -Wait -PassThru; exit $p.ExitCode"
  if errorlevel 1 (
    echo [ERROR] Ollama install failed.
    goto :fail
  )
  echo [INFO] Ollama install done.
) else (
  echo [INFO] Ollama already installed.
)

REM --- Check or pull Ollama model ---
ollama list 2>nul | findstr /I /C:"%OLLAMA_MODEL%" >nul 2>&1
if errorlevel 1 (
  echo [INFO] Pulling %OLLAMA_MODEL%. This may take a while.
  ollama pull %OLLAMA_MODEL%
  if errorlevel 1 (
    echo [ERROR] Ollama model pull failed.
    goto :fail
  )
  echo [INFO] Ollama model pull done.
) else (
  echo [INFO] Ollama model already exists: %OLLAMA_MODEL%
)

REM --- Resolve Python ---
call :resolve_python

if "%PYTHON_EXE%"=="" (
  echo [INFO] Python 3.12 not found. Trying to install Python 3.12...
  call :install_python_312
  if errorlevel 1 (
    echo [ERROR] Python install failed.
    goto :fail
  )
  call :resolve_python
)

if "%PYTHON_EXE%"=="" (
  echo [ERROR] Python executable not found.
  goto :fail
)

call :is_python_312 "%PYTHON_EXE%"
if errorlevel 1 (
  echo [WARN] Detected Python is not 3.12: %PYTHON_EXE%
  echo [WARN] Build will continue with detected Python.
) else (
  echo [INFO] Python 3.12 detected: %PYTHON_EXE%
)

REM --- Ensure venv ---
if exist "%VENV_PY%" (
  "%VENV_PY%" -V >nul 2>&1
  if errorlevel 1 (
    echo [WARN] Existing .venv is broken. Recreating it.
    rmdir /s /q ".venv"
  )
)

if not exist "%VENV_PY%" (
  echo [INFO] Creating .venv...
  "%PYTHON_EXE%" -m venv .venv
)

if not exist "%VENV_PY%" (
  echo [ERROR] Failed to create .venv.
  goto :fail
)

REM --- Install dependencies ---
echo [INFO] Installing dependencies...
"%VENV_PY%" -m pip install -U pip setuptools wheel
if errorlevel 1 goto :fail

"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

REM --- Clean output with backup ---
if exist "%APP_BACKUP%" rmdir /s /q "%APP_BACKUP%"
if exist "%APP_DIR%" (
  echo [INFO] Backing up old dist output.
  move "%APP_DIR%" "%APP_BACKUP%" >nul
)

if exist "build" rmdir /s /q "build"

REM --- Build using spec ---
if not exist "Ako-ai.spec" (
  echo [ERROR] Ako-ai.spec not found.
  goto :fail
)

echo [INFO] Running PyInstaller...
"%VENV_PY%" -m PyInstaller --noconfirm --clean "Ako-ai.spec"
if errorlevel 1 goto :fail

if not exist "%APP_DIR%\Ako-ai.exe" (
  echo [ERROR] Build finished but exe was not found.
  echo [ERROR] Expected: %APP_DIR%\Ako-ai.exe
  goto :fail
)

set "BUILD_OK=1"

:finalize
if "%BUILD_OK%"=="1" (
  if exist "%APP_BACKUP%" rmdir /s /q "%APP_BACKUP%"
  echo.
  echo [OK] Build done: %APP_DIR%\Ako-ai.exe
  goto :end
)

if exist "%APP_BACKUP%" (
  echo [WARN] Build failed. Restoring previous dist output.
  if not exist "%DIST_ROOT%" mkdir "%DIST_ROOT%"
  move "%APP_BACKUP%" "%APP_DIR%" >nul
)

goto :end

:resolve_python
set "PYTHON_EXE="

REM 1) Common Python 3.12 paths
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
  goto :resolve_python_done
)

if exist "%ProgramFiles%\Python312\python.exe" (
  set "PYTHON_EXE=%ProgramFiles%\Python312\python.exe"
  goto :resolve_python_done
)

REM 2) Python launcher
for /f "usebackq delims=" %%I in (`py -3.12 -c "import sys; print(sys.executable)" 2^>nul`) do (
  if exist "%%~fI" (
    set "PYTHON_EXE=%%~fI"
    goto :resolve_python_done
  )
)

REM 3) PATH python fallback
for /f "delims=" %%I in ('where python 2^>nul') do (
  set "PYTHON_EXE=%%~fI"
  goto :resolve_python_done
)

:resolve_python_done
exit /b 0

:install_python_312
where winget >nul 2>&1
if not errorlevel 1 (
  winget install -e --id Python.Python.3.12 --version 3.12.10 --accept-package-agreements --accept-source-agreements
  call :resolve_python
  if not "%PYTHON_EXE%"=="" (
    call :is_python_312 "%PYTHON_EXE%"
    if not errorlevel 1 exit /b 0
  )
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$url='https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'; $out=Join-Path $env:TEMP 'python-3.12.10-amd64.exe'; Invoke-WebRequest -Uri $url -OutFile $out; $p=Start-Process -FilePath $out -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1' -Wait -PassThru; exit $p.ExitCode"
if errorlevel 1 exit /b 1

call :resolve_python
if "%PYTHON_EXE%"=="" exit /b 1
exit /b 0

:is_python_312
set "PY_MINOR="
for /f "usebackq delims=" %%V in (`"%~1" -c "import sys; print(str(sys.version_info[0])+'.'+str(sys.version_info[1]))" 2^>nul`) do (
  set "PY_MINOR=%%V"
)

if "%PY_MINOR%"=="3.12" exit /b 0
exit /b 1

:fail
echo.
echo [ERROR] Build failed. Check the log above.
goto :finalize

:finalize
if "%BUILD_OK%"=="1" (
  if exist "%APP_BACKUP%" rmdir /s /q "%APP_BACKUP%"
  echo.
  echo [OK] Build done: %APP_DIR%\Ako-ai.exe
  goto :end
)

if exist "%APP_BACKUP%" (
  echo [WARN] Build failed. Restoring previous dist output.
  if not exist "%DIST_ROOT%" mkdir "%DIST_ROOT%"
  move "%APP_BACKUP%" "%APP_DIR%" >nul
)

goto :end

:end
echo.
pause
endlocal