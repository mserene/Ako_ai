@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "DIST_ROOT=dist"
set "APP_DIR=dist\Ako-ai"
set "APP_BACKUP=dist\Ako-ai_backup"
set "BUILD_OK=0"

set "PYTHON_EXE="
set "PY_RUN="
set "USE_EMBED_PY=0"

set "VENV_PY=.venv\Scripts\python.exe"
set "PY_EMBED_ZIP=installer_assets\python-3.12.10-embed-amd64.zip"
set "BUILD_PY_DIR=.build_runtime\python312"
set "BUILD_PY=%BUILD_PY_DIR%\python.exe"
set "GET_PIP_LOCAL=installer_assets\get-pip.py"
set "GET_PIP_CACHE=.build_runtime\get-pip.py"

REM Keep pip/cache/temp files inside the project folder.
REM This avoids Permission denied errors from broken %LOCALAPPDATA%\pip caches.
set "BUILD_TMP=%CD%\.build_runtime\tmp"
set "PIP_CACHE_DIR=%CD%\.build_runtime\pip_cache"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIP_FLAGS=--disable-pip-version-check --no-cache-dir"

echo [INFO] Starting Ako-ai developer build. ^(v8 runtime-file preflight + pip-cache fix^)
echo [INFO] This script builds dist\Ako-ai with PyInstaller.
echo [INFO] End users should run AkoSetup.exe, not this file.
echo.

if not exist ".build_runtime" mkdir ".build_runtime" >nul 2>&1
if not exist "%BUILD_TMP%" mkdir "%BUILD_TMP%" >nul 2>&1
if not exist "%PIP_CACHE_DIR%" mkdir "%PIP_CACHE_DIR%" >nul 2>&1
set "TMP=%BUILD_TMP%"
set "TEMP=%BUILD_TMP%"

REM ============================================================
REM 1) Prefer real system Python 3.12.
REM    If blocked/not installed, fall back to installer_assets Python embed zip.
REM ============================================================
echo [INFO] Checking system Python 3.12...
call :resolve_system_python

if not "%PYTHON_EXE%"=="" (
  echo [INFO] System Python 3.12 found: %PYTHON_EXE%
  call :prepare_venv
  if errorlevel 1 goto :fail
  set "PY_RUN=%VENV_PY%"
  goto :python_ready
)

echo [WARN] System Python 3.12 not found.
echo [INFO] Trying bundled Python embed zip fallback...
call :prepare_embedded_build_python
if errorlevel 1 goto :fail
set "PY_RUN=%BUILD_PY%"
set "USE_EMBED_PY=1"

:python_ready
echo [INFO] Build Python ready: %PY_RUN%
echo [INFO] Pip cache dir: %PIP_CACHE_DIR%
echo [INFO] Temp dir: %BUILD_TMP%
"%PY_RUN%" -V
if errorlevel 1 goto :fail

REM ============================================================
REM 2) Install build dependencies.
REM    Ollama/model are runtime bootstrap responsibilities, not build requirements.
REM ============================================================
echo.
echo [INFO] Installing/updating build tools...
"%PY_RUN%" -m pip install %PIP_FLAGS% -U pip setuptools wheel pyinstaller
if errorlevel 1 goto :fail

if exist "requirements.txt" (
  echo [INFO] Installing project dependencies from requirements.txt...
  "%PY_RUN%" -m pip install %PIP_FLAGS% -r requirements.txt
  if errorlevel 1 goto :fail
) else (
  echo [WARN] requirements.txt not found. Skipping project dependency install.
)

REM ============================================================
REM 3) Preflight: runtime files must exist before building.
REM    The installer copies dist\Ako-ai, so these files must be copied into dist.
REM ============================================================
echo.
echo [INFO] Checking runtime bootstrap source files...
if not exist "bootstrap_runtime.bat" (
  echo [ERROR] bootstrap_runtime.bat not found next to this build script.
  echo [ERROR] Put bootstrap_runtime.bat in the project root: %CD%
  echo [ERROR] Then run this build script again.
  goto :fail
)
if not exist "Ako-ai_launcher.bat" (
  echo [ERROR] Ako-ai_launcher.bat not found next to this build script.
  echo [ERROR] Put Ako-ai_launcher.bat in the project root: %CD%
  echo [ERROR] Then run this build script again.
  goto :fail
)

REM ============================================================
REM 4) Clean output with backup.
REM ============================================================
echo.
if exist "%APP_BACKUP%" rmdir /s /q "%APP_BACKUP%"
if exist "%APP_DIR%" (
  echo [INFO] Backing up old dist output.
  move "%APP_DIR%" "%APP_BACKUP%" >nul
)

if exist "build" rmdir /s /q "build"

REM ============================================================
REM 5) Build using PyInstaller spec.
REM ============================================================
if not exist "Ako-ai.spec" (
  echo [ERROR] Ako-ai.spec not found.
  goto :fail
)

echo [INFO] Running PyInstaller...
"%PY_RUN%" -m PyInstaller --noconfirm --clean "Ako-ai.spec"
if errorlevel 1 goto :fail

if not exist "%APP_DIR%\Ako-ai.exe" (
  echo [ERROR] Build finished but exe was not found.
  echo [ERROR] Expected: %APP_DIR%\Ako-ai.exe
  goto :fail
)

REM ============================================================
REM 6) Copy runtime bootstrap files into installer payload.
REM ============================================================
echo [INFO] Copying runtime bootstrap files into dist...
if exist "bootstrap_runtime.bat" (
  copy /Y "bootstrap_runtime.bat" "%APP_DIR%\bootstrap_runtime.bat" >nul
) else (
  echo [ERROR] bootstrap_runtime.bat not found.
  goto :fail
)

if exist "Ako-ai_launcher.bat" (
  copy /Y "Ako-ai_launcher.bat" "%APP_DIR%\Ako-ai_launcher.bat" >nul
) else (
  echo [ERROR] Ako-ai_launcher.bat not found.
  goto :fail
)

if exist "requirements.txt" copy /Y "requirements.txt" "%APP_DIR%\requirements.txt" >nul
if exist "runtime_requirements.txt" copy /Y "runtime_requirements.txt" "%APP_DIR%\runtime_requirements.txt" >nul

set "BUILD_OK=1"
goto :finalize

REM ============================================================
REM Functions
REM ============================================================

:resolve_system_python
set "PYTHON_EXE="

REM Python launcher first.
for /f "usebackq delims=" %%I in (`py -3.12 -c "import sys; print(sys.executable)" 2^>nul`) do (
  call :is_full_python_312 "%%~fI"
  if not errorlevel 1 (
    set "PYTHON_EXE=%%~fI"
    goto :resolve_system_python_done
  )
)

REM Registry paths.
for %%R in ("HKCU\Software\Python\PythonCore\3.12\InstallPath" "HKLM\SOFTWARE\Python\PythonCore\3.12\InstallPath" "HKLM\SOFTWARE\WOW6432Node\Python\PythonCore\3.12\InstallPath") do (
  for /f "tokens=2,*" %%A in ('reg query %%~R /ve 2^>nul ^| findstr /I "REG_SZ"') do (
    if exist "%%~B\python.exe" (
      call :is_full_python_312 "%%~B\python.exe"
      if not errorlevel 1 (
        set "PYTHON_EXE=%%~B\python.exe"
        goto :resolve_system_python_done
      )
    )
  )
)

REM Common paths.
for %%P in ("%LocalAppData%\Programs\Python\Python312\python.exe" "%ProgramFiles%\Python312\python.exe" "%ProgramFiles(x86)%\Python312\python.exe" "C:\Python312\python.exe") do (
  if exist "%%~P" (
    call :is_full_python_312 "%%~P"
    if not errorlevel 1 (
      set "PYTHON_EXE=%%~P"
      goto :resolve_system_python_done
    )
  )
)

REM PATH fallback. Reject Microsoft Store aliases.
for %%C in (python python3) do (
  for /f "delims=" %%I in ('where %%C 2^>nul') do (
    echo %%~fI | findstr /I /C:"\WindowsApps\python.exe" /C:"\WindowsApps\python3.exe" >nul
    if errorlevel 1 (
      call :is_full_python_312 "%%~fI"
      if not errorlevel 1 (
        set "PYTHON_EXE=%%~fI"
        goto :resolve_system_python_done
      )
    ) else (
      echo [WARN] Ignoring Microsoft Store Python alias: %%~fI
    )
  )
)

:resolve_system_python_done
exit /b 0

:is_full_python_312
REM Robust version check for a normal/full Python.
REM Do not parse localized/odd --version output; ask Python directly.
"%~1" -c "import sys, venv, ensurepip; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 exit /b 0
exit /b 1

:is_any_python_312
REM Robust version check for embedded Python.
REM First use sys.version_info. If -c is blocked for any weird embedded-state reason,
REM fall back to checking `python -V` text.
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 exit /b 0

set "PYVER_TMP=%TEMP%\ako_pyver_%RANDOM%_%RANDOM%.txt"
"%~1" -V > "%PYVER_TMP%" 2>&1
findstr /B /C:"Python 3.12." "%PYVER_TMP%" >nul 2>&1
if not errorlevel 1 (
  del "%PYVER_TMP%" >nul 2>&1
  exit /b 0
)
del "%PYVER_TMP%" >nul 2>&1
exit /b 1

:prepare_venv
if exist "%VENV_PY%" (
  "%VENV_PY%" -V >nul 2>&1
  if errorlevel 1 (
    echo [WARN] Existing .venv is broken. Recreating it.
    rmdir /s /q ".venv"
  )
)

if not exist "%VENV_PY%" (
  echo [INFO] Creating .venv using system Python...
  "%PYTHON_EXE%" -m venv .venv
)

if not exist "%VENV_PY%" (
  echo [ERROR] Failed to create .venv.
  exit /b 1
)
exit /b 0

:prepare_embedded_build_python
if not exist "%PY_EMBED_ZIP%" (
  echo [ERROR] Bundled Python zip not found: %PY_EMBED_ZIP%
  echo [ERROR] Put python-3.12.10-embed-amd64.zip in installer_assets, then run this again.
  exit /b 1
)

REM Always refresh the embedded build Python folder.
REM A previous failed/partial extraction can leave .build_runtime\python312 in a broken state,
REM so reusing it may falsely report "not Python 3.12".
echo [INFO] Refreshing bundled Python build runtime...
if exist "%BUILD_PY_DIR%" rmdir /s /q "%BUILD_PY_DIR%"
mkdir "%BUILD_PY_DIR%" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath '%CD%\%PY_EMBED_ZIP%' -DestinationPath '%CD%\%BUILD_PY_DIR%' -Force"
if errorlevel 1 (
  echo [ERROR] Failed to extract bundled Python zip.
  exit /b 1
)

if not exist "%BUILD_PY%" (
  echo [ERROR] Embedded python.exe not found after extraction: %BUILD_PY%
  echo [ERROR] Make sure installer_assets\python-3.12.10-embed-amd64.zip is the real Python embeddable ZIP, not the web installer.
  exit /b 1
)

call :patch_embedded_pth
if errorlevel 1 exit /b 1

call :is_any_python_312 "%BUILD_PY%"
if errorlevel 1 (
  echo [ERROR] Embedded Python could not be verified as Python 3.12: %BUILD_PY%
  echo [ERROR] Version output:
  "%BUILD_PY%" -V
  echo [ERROR] If this fails, delete .build_runtime and confirm the ZIP filename is exactly:
  echo [ERROR] installer_assets\python-3.12.10-embed-amd64.zip
  exit /b 1
)

call :ensure_embedded_pip
if errorlevel 1 exit /b 1

exit /b 0

:patch_embedded_pth
set "PTH_FILE=%BUILD_PY_DIR%\python312._pth"
if not exist "%PTH_FILE%" (
  echo [WARN] python312._pth not found. Continuing.
  exit /b 0
)

mkdir "%BUILD_PY_DIR%\Lib\site-packages" >nul 2>&1

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $pth='%CD%\%PTH_FILE%'; $lines=Get-Content -LiteralPath $pth; $out=@(); $hasSite=$false; $hasSP=$false; foreach($line in $lines){ if($line -match '^#import site'){ $out += 'import site'; $hasSite=$true } else { $out += $line; if($line -eq 'import site'){ $hasSite=$true }; if($line -ieq 'Lib\site-packages'){ $hasSP=$true } } }; if(-not $hasSP){ $out += 'Lib\site-packages' }; if(-not $hasSite){ $out += 'import site' }; Set-Content -LiteralPath $pth -Value $out -Encoding ASCII"
if errorlevel 1 (
  echo [ERROR] Failed to patch python312._pth.
  exit /b 1
)
exit /b 0

:ensure_embedded_pip
"%BUILD_PY%" -m pip --version >nul 2>&1
if not errorlevel 1 (
  echo [INFO] pip already available in embedded build Python.
  exit /b 0
)

echo [INFO] pip not found in embedded Python. Preparing pip...

if exist "%GET_PIP_LOCAL%" (
  echo [INFO] Using bundled get-pip.py: %GET_PIP_LOCAL%
  "%BUILD_PY%" "%GET_PIP_LOCAL%" %PIP_FLAGS%
  if errorlevel 1 (
    echo [ERROR] get-pip.py failed.
    exit /b 1
  )
  exit /b 0
)

echo [INFO] get-pip.py not found in installer_assets. Downloading get-pip.py...
if not exist ".build_runtime" mkdir ".build_runtime" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $ErrorActionPreference='Stop'; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%CD%\%GET_PIP_CACHE%' -UseBasicParsing"
if errorlevel 1 (
  echo [ERROR] Failed to download get-pip.py.
  echo [ERROR] For offline/policy-blocked PCs, download get-pip.py manually and put it here:
  echo [ERROR] installer_assets\get-pip.py
  echo [ERROR] URL: https://bootstrap.pypa.io/get-pip.py
  exit /b 1
)

"%BUILD_PY%" "%GET_PIP_CACHE%" %PIP_FLAGS%
if errorlevel 1 (
  echo [ERROR] get-pip.py failed.
  exit /b 1
)
exit /b 0

:fail
echo.
echo [ERROR] Build failed. Check the log above.
goto :finalize

:finalize
if "%BUILD_OK%"=="1" (
  if exist "%APP_BACKUP%" rmdir /s /q "%APP_BACKUP%"
  echo.
  echo [OK] Build done: %APP_DIR%\Ako-ai.exe
  if "%USE_EMBED_PY%"=="1" (
    echo [INFO] Build used embedded Python fallback from installer_assets.
  )
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
