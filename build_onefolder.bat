@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"
chcp 65001 >nul

set "DIST_ROOT=dist"
set "APP_DIR=dist\Ako-ai"
set "APP_BACKUP=dist\Ako-ai_backup"
set "BUILD_OK=0"
set "PYTHON_EXE="
set "VENV_PY=.venv\Scripts\python.exe"
set "OLLAMA_MODEL=exaone3.5:7.8b"

REM --- Ollama 설치 확인 및 자동 설치 ---
where ollama >nul 2>&1
if errorlevel 1 (
  echo [INFO] Ollama가 설치되어 있지 않아요. 자동으로 설치할게요...
  powershell -NoProfile -Command ^
    "$url='https://ollama.com/download/OllamaSetup.exe'; $out='%TEMP%\OllamaSetup.exe'; Invoke-WebRequest -Uri $url -OutFile $out; $p=Start-Process -FilePath $out -ArgumentList '/S' -Wait -PassThru; exit $p.ExitCode"
  if errorlevel 1 (
    echo [ERROR] Ollama 설치 중 문제가 발생했습니다.
    goto :fail
  )
  echo [INFO] Ollama 설치 완료
) else (
  echo [INFO] Ollama 이미 설치됨
)

REM --- exaone 모델 확인 및 자동 다운로드 ---
ollama list 2>nul | findstr /I /C:"%OLLAMA_MODEL%" >nul 2>&1
if errorlevel 1 (
  echo [INFO] %OLLAMA_MODEL% 모델이 없어요. 다운로드할게요... (약 5GB, 시간이 걸려요)
  ollama pull %OLLAMA_MODEL%
  if errorlevel 1 (
    echo [ERROR] 모델 다운로드 실패
    goto :fail
  )
  echo [INFO] 모델 다운로드 완료
) else (
  echo [INFO] %OLLAMA_MODEL% 모델 이미 있음
)

REM --- Python 설치 확인 및 자동 설치 ---
call :resolve_python

if "%PYTHON_EXE%"=="" (
  echo [INFO] Python 3.12를 찾지 못했어요. 자동 설치를 시도합니다...
  call :install_python_312
  if errorlevel 1 (
    echo [ERROR] Python 자동 설치 실패
    goto :fail
  )
  call :resolve_python
)

if "%PYTHON_EXE%"=="" (
  echo [ERROR] Python 실행 파일을 찾지 못했습니다.
  goto :fail
)

call :is_python_312 "%PYTHON_EXE%"
if errorlevel 1 (
  echo [WARN] 현재 Python은 3.12가 아닙니다. 감지된 Python으로 계속 진행합니다: %PYTHON_EXE%
)

REM --- Ensure venv ---
if exist "%VENV_PY%" (
  "%VENV_PY%" -V >nul 2>&1
  if errorlevel 1 (
    echo [WARN] 기존 .venv 가 손상되어 다시 생성합니다.
    rmdir /s /q ".venv"
  )
)

if not exist "%VENV_PY%" (
  echo [INFO] Creating venv...
  "%PYTHON_EXE%" -m venv .venv
)

if not exist "%VENV_PY%" (
  echo [ERROR] Python 가상환경 생성 실패
  goto :fail
)

REM --- Install deps in venv ---
echo [INFO] 의존성 설치/확인 중...
"%VENV_PY%" -m pip install -U pip setuptools wheel
if errorlevel 1 goto :fail

"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

REM --- Clean output (기존 dist는 백업 후 빌드 실패 시 복구) ---
if exist "%APP_BACKUP%" rmdir /s /q "%APP_BACKUP%"
if exist "%APP_DIR%" (
  echo [INFO] 기존 결과물을 백업합니다: %APP_DIR% ^> %APP_BACKUP%
  move "%APP_DIR%" "%APP_BACKUP%" >nul
)

if exist "build" rmdir /s /q "build"

REM --- Build using spec (options must live in .spec) ---
if not exist "Ako-ai.spec" (
  echo [ERROR] Ako-ai.spec 파일을 찾지 못했습니다.
  goto :fail
)

echo [INFO] PyInstaller 빌드 중...
"%VENV_PY%" -m PyInstaller --noconfirm --clean "Ako-ai.spec"
if errorlevel 1 goto :fail

if not exist "%APP_DIR%\Ako-ai.exe" (
  echo [ERROR] 빌드는 끝났지만 exe를 찾지 못했습니다: %APP_DIR%\Ako-ai.exe
  goto :fail
)

set "BUILD_OK=1"

:finalize
if "%BUILD_OK%"=="1" (
  if exist "%APP_BACKUP%" rmdir /s /q "%APP_BACKUP%"
  echo.
  echo [INFO] Build done: %APP_DIR%\Ako-ai.exe
  goto :end
)

if exist "%APP_BACKUP%" (
  echo [WARN] 빌드 실패: 이전 dist 결과물을 복구합니다.
  if not exist "%DIST_ROOT%" mkdir "%DIST_ROOT%"
  move "%APP_BACKUP%" "%APP_DIR%" >nul
)

goto :end

:resolve_python
set "PYTHON_EXE="

REM 1) 흔한 설치 경로 우선 확인
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
  goto :resolve_python_done
)
if exist "%ProgramFiles%\Python312\python.exe" (
  set "PYTHON_EXE=%ProgramFiles%\Python312\python.exe"
  goto :resolve_python_done
)

REM 2) py launcher가 3.12를 찾는지 확인
for /f "usebackq delims=" %%I in (`py -3.12 -c "import sys; print(sys.executable)" 2^>nul`) do (
  if exist "%%~fI" (
    set "PYTHON_EXE=%%~fI"
    goto :resolve_python_done
  )
)

REM 3) PATH 의 python 확인
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
    if not errorlevel 1 (
      exit /b 0
    )
  )
  echo [WARN] winget 설치가 정책/환경 문제로 완료되지 않았습니다. python.org 설치로 진행합니다...
)

powershell -NoProfile -Command ^
  "$url='https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'; $out='%TEMP%\python-installer.exe'; Invoke-WebRequest -Uri $url -OutFile $out; $p=Start-Process -FilePath $out -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1' -Wait -PassThru; exit $p.ExitCode"
if errorlevel 1 (
  echo [WARN] 무인 설치 실패. 설치 UI를 열어 다시 시도합니다...
  powershell -NoProfile -Command ^
    "$out='%TEMP%\python-installer.exe'; if (-not (Test-Path $out)) { $url='https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'; Invoke-WebRequest -Uri $url -OutFile $out }; $p=Start-Process -FilePath $out -ArgumentList 'InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1' -Wait -PassThru; exit $p.ExitCode"
  if errorlevel 1 exit /b 1
)

call :resolve_python
if "%PYTHON_EXE%"=="" exit /b 1
exit /b 0

:is_python_312
set "PY_MINOR="
for /f "usebackq delims=" %%V in (`"%~1" -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2^>nul`) do (
  set "PY_MINOR=%%V"
)
if "%PY_MINOR%"=="3.12" exit /b 0
exit /b 1

:fail
echo.
echo [ERROR] 빌드에 실패했습니다. 위 로그를 확인하세요.
goto :finalize

:end
echo.
pause
endlocal
