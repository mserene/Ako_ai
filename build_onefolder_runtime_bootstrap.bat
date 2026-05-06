@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem ============================================================
rem Ako developer build v13 - Tkinter required
rem - Refuses python-*-embed-amd64.zip for PyInstaller.
rem - Ako GUI imports tkinter; Python embeddable ZIP has no Tk/Tcl.
rem - Use full Python 3.12 with tkinter, or portable full Python.
rem
rem Optional:
rem   set BUILD_PYTHON_EXE=D:\Tools\Python312\python.exe
rem ============================================================

set "SCRIPT_DIR=%~dp0"
set "DIST_DIR=%SCRIPT_DIR%dist\Ako-ai"
set "BUILD_VENV=%SCRIPT_DIR%.build_venv"
set "PIP_CACHE_DIR=%SCRIPT_DIR%.build_runtime\pip_cache"
set "TMP=%SCRIPT_DIR%.build_runtime\tmp"
set "TEMP=%SCRIPT_DIR%.build_runtime\tmp"
set "PYTHON_EXE="

echo [INFO] Starting Ako developer build. (v13 tkinter-required)
echo [INFO] Build Python must be full Python 3.12 with tkinter.
echo.

if not exist "%SCRIPT_DIR%.build_runtime" mkdir "%SCRIPT_DIR%.build_runtime" >nul 2>nul
if not exist "%TMP%" mkdir "%TMP%" >nul 2>nul
if not exist "%PIP_CACHE_DIR%" mkdir "%PIP_CACHE_DIR%" >nul 2>nul

call :find_python
if errorlevel 1 goto fail

call :verify_tkinter "%PYTHON_EXE%"
if errorlevel 1 goto fail

call :make_venv
if errorlevel 1 goto fail

call :install_build_deps
if errorlevel 1 goto fail

call :run_pyinstaller
if errorlevel 1 goto fail

call :copy_runtime_files
if errorlevel 1 goto fail

echo.
echo [OK] Build done: dist\Ako-ai\Ako-ai.exe
echo [INFO] Test it directly before making installer:
echo [INFO]   dist\Ako-ai\Ako-ai.exe
exit /b 0

:find_python
echo [INFO] Finding Python 3.12 with tkinter...

if defined BUILD_PYTHON_EXE (
    if exist "%BUILD_PYTHON_EXE%" (
        "%BUILD_PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=%BUILD_PYTHON_EXE%"
            echo [INFO] Using BUILD_PYTHON_EXE: %BUILD_PYTHON_EXE%
            exit /b 0
        )
    )
    echo [ERROR] BUILD_PYTHON_EXE is set but is not valid Python 3.12:
    echo [ERROR] %BUILD_PYTHON_EXE%
    exit /b 1
)

py -3.12 -c "import sys; print(sys.executable)" > "%TEMP%\ako_py_path.txt" 2>nul
if not errorlevel 1 (
    set /p PYTHON_EXE=<"%TEMP%\ako_py_path.txt"
    if defined PYTHON_EXE (
        echo [INFO] Found py -3.12: %PYTHON_EXE%
        exit /b 0
    )
)

for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | findstr /I "WindowsApps" >nul
    if errorlevel 1 (
        "%%P" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=%%P"
            echo [INFO] Found python: %%P
            exit /b 0
        )
    ) else (
        echo [WARN] Ignoring Microsoft Store Python alias: %%P
    )
)

for %%P in (
    "%LocalAppData%\Programs\Python\Python312\python.exe"
    "%ProgramFiles%\Python312\python.exe"
    "%ProgramFiles(x86)%\Python312\python.exe"
    "C:\Python312\python.exe"
) do (
    if exist "%%~P" (
        "%%~P" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=%%~P"
            echo [INFO] Found python: %%~P
            exit /b 0
        )
    )
)

echo [ERROR] Full Python 3.12 was not found.
echo.
echo [ERROR] Do NOT use installer_assets\python-3.12.10-embed-amd64.zip for building.
echo [ERROR] That embed ZIP has no tkinter/Tcl/Tk, so PyInstaller output will crash:
echo [ERROR] ModuleNotFoundError: No module named 'tkinter'
echo.
echo [INFO] Fix options:
echo [INFO] 1. Install full Python 3.12 from python.org with Tcl/Tk enabled.
echo [INFO] 2. Or extract portable full Python 3.12 and run:
echo [INFO]    set BUILD_PYTHON_EXE=D:\path\to\portable-python\python.exe
echo [INFO]    build_onefolder_runtime_bootstrap.bat
exit /b 1

:verify_tkinter
set "CANDIDATE=%~1"
echo [INFO] Verifying tkinter...
"%CANDIDATE%" -c "import tkinter; print('TK OK', tkinter.TkVersion)"
if errorlevel 1 (
    echo.
    echo [ERROR] This Python is 3.12, but tkinter is missing:
    echo [ERROR] %CANDIDATE%
    echo.
    echo [ERROR] This Python cannot build Ako GUI.
    echo [ERROR] Use full Python 3.12 with Tcl/Tk, not Python embeddable ZIP.
    exit /b 1
)
exit /b 0

:make_venv
echo [INFO] Creating build venv...
if exist "%BUILD_VENV%" rmdir /s /q "%BUILD_VENV%" >nul 2>nul

"%PYTHON_EXE%" -m venv "%BUILD_VENV%"
if errorlevel 1 (
    echo [ERROR] Failed to create build venv.
    exit /b 1
)

if not exist "%BUILD_VENV%\Scripts\python.exe" (
    echo [ERROR] Build venv python.exe was not created.
    exit /b 1
)

"%BUILD_VENV%\Scripts\python.exe" -c "import tkinter; print('VENV TK OK')"
if errorlevel 1 (
    echo [ERROR] tkinter is missing inside build venv.
    exit /b 1
)

exit /b 0

:install_build_deps
echo [INFO] Installing build dependencies...
"%BUILD_VENV%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel --no-cache-dir --cache-dir "%PIP_CACHE_DIR%"
if errorlevel 1 exit /b 1

if exist "%SCRIPT_DIR%requirements.txt" (
    "%BUILD_VENV%\Scripts\python.exe" -m pip install --no-cache-dir --cache-dir "%PIP_CACHE_DIR%" -r "%SCRIPT_DIR%requirements.txt"
    if errorlevel 1 exit /b 1
)

"%BUILD_VENV%\Scripts\python.exe" -m pip install --no-cache-dir --cache-dir "%PIP_CACHE_DIR%" pyinstaller
if errorlevel 1 exit /b 1

exit /b 0

:run_pyinstaller
echo [INFO] Running PyInstaller...

if exist "%SCRIPT_DIR%build" rmdir /s /q "%SCRIPT_DIR%build" >nul 2>nul
if exist "%SCRIPT_DIR%dist" rmdir /s /q "%SCRIPT_DIR%dist" >nul 2>nul

if exist "%SCRIPT_DIR%Ako-ai.spec" (
    "%BUILD_VENV%\Scripts\python.exe" -m PyInstaller "%SCRIPT_DIR%Ako-ai.spec" --noconfirm
) else (
    "%BUILD_VENV%\Scripts\python.exe" -m PyInstaller "%SCRIPT_DIR%app.py" --name "Ako-ai" --onedir --noconfirm --windowed
)

if errorlevel 1 (
    echo [ERROR] PyInstaller failed.
    exit /b 1
)

if not exist "%DIST_DIR%\Ako-ai.exe" (
    echo [ERROR] dist\Ako-ai\Ako-ai.exe was not created.
    exit /b 1
)

exit /b 0

:copy_runtime_files
echo [INFO] Copying runtime bootstrap files into dist...

if exist "%SCRIPT_DIR%bootstrap_runtime.bat" (
    copy /Y "%SCRIPT_DIR%bootstrap_runtime.bat" "%DIST_DIR%\bootstrap_runtime.bat" >nul
) else (
    echo [ERROR] bootstrap_runtime.bat not found in project root.
    exit /b 1
)

if exist "%SCRIPT_DIR%Ako-ai_launcher.bat" (
    copy /Y "%SCRIPT_DIR%Ako-ai_launcher.bat" "%DIST_DIR%\Ako-ai_launcher.bat" >nul
)

if exist "%SCRIPT_DIR%Ako-ai_launcher.vbs" (
    copy /Y "%SCRIPT_DIR%Ako-ai_launcher.vbs" "%DIST_DIR%\Ako-ai_launcher.vbs" >nul
)

if exist "%SCRIPT_DIR%requirements.txt" (
    copy /Y "%SCRIPT_DIR%requirements.txt" "%DIST_DIR%\requirements.txt" >nul
)

exit /b 0

:fail
echo.
echo [ERROR] Build failed. Check the log above.
echo.
pause
exit /b 1
