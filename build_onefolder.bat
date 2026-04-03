@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "DIST_ROOT=dist"
set "APP_DIR=dist\Ako-ai"
set "APP_BACKUP=dist\Ako-ai_backup"
set "BUILD_OK=0"
set "PYTHON_EXE="

REM --- Ollama 설치 확인 및 자동 설치 ---
where ollama >nul 2>&1
if errorlevel 1 (
  echo [INFO] Ollama가 설치되어 있지 않아요. 자동으로 설치할게요...
  powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://ollama.com/install.sh' -OutFile '%TEMP%\ollama-install.ps1'"
  REM Windows installer 직접 다운로드
  powershell -NoProfile -Command ^
    "$url='https://ollama.com/download/OllamaSetup.exe'; $out='%TEMP%\OllamaSetup.exe'; Invoke-WebRequest -Uri $url -OutFile $out; Start-Process -FilePath $out -ArgumentList '/S' -Wait"
  if errorlevel 1 (
    echo [ERROR] Ollama 설치 중 문제가 발생했습니다.
    goto :fail
  )
  echo [INFO] Ollama 설치 완료
) else (
  echo [INFO] Ollama 이미 설치됨
)

REM --- exaone 모델 확인 및 자동 다운로드 ---
ollama list 2>nul | findstr "exaone3.5" >nul 2>&1
if errorlevel 1 (
  echo [INFO] exaone3.5:7.8b 모델이 없어요. 다운로드할게요... (약 5GB, 시간이 걸려요)
  ollama pull exaone3.5:7.8b
  if errorlevel 1 (
    echo [ERROR] 모델 다운로드 실패
    goto :fail
  )
  echo [INFO] 모델 다운로드 완료
) else (
  echo [INFO] exaone3.5:7.8b 모델 이미 있음
)

REM --- Python 설치 확인 및 자동 설치 ---
where py >nul 2>&1
if not errorlevel 1 (
  set "PYTHON_EXE=py -3.12"
) else (
  where python >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON_EXE=python"
  ) else (
    echo [INFO] Python이 설치되어 있지 않아요. 자동 설치를 시도합니다...

    where winget >nul 2>&1
    if not errorlevel 1 (
      winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    ) else (
      echo [INFO] winget 이 없어 Python 공식 설치 파일로 진행합니다...
      powershell -NoProfile -Command ^
        "$url='https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'; $out='%TEMP%\python-installer.exe'; Invoke-WebRequest -Uri $url -OutFile $out; Start-Process -FilePath $out -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Wait"
    )

    if errorlevel 1 (
      echo [ERROR] Python 자동 설치 실패
      goto :fail
    )

    REM 설치 직후 PATH 갱신 전을 대비한 기본 경로 체크
    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
      set "PYTHON_EXE=\"%LocalAppData%\Programs\Python\Python312\python.exe\""
    ) else if exist "%ProgramFiles%\Python312\python.exe" (
      set "PYTHON_EXE=\"%ProgramFiles%\Python312\python.exe\""
    ) else (
      where py >nul 2>&1
      if not errorlevel 1 (
        set "PYTHON_EXE=py -3.12"
      ) else (
        where python >nul 2>&1
        if not errorlevel 1 (
          set "PYTHON_EXE=python"
        )
      )
    )
  )
)

if "%PYTHON_EXE%"=="" (
  echo [ERROR] Python 실행 파일을 찾지 못했습니다.
  goto :fail
)

REM --- Ensure venv (Python 3.12 recommended) ---
if not exist ".venv\Scripts\python.exe" (
  echo [INFO] Creating venv...
  %PYTHON_EXE% -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Python 가상환경 생성 실패
  goto :fail
)

REM --- Install deps in venv ---
call ".venv\Scripts\activate"
if errorlevel 1 (
  echo [ERROR] 가상환경 활성화 실패
  goto :fail
)

python -m pip install -U pip setuptools wheel
if errorlevel 1 goto :fail

python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

REM --- Clean output (기존 dist는 백업 후 빌드 실패 시 복구) ---
if exist "%APP_BACKUP%" rmdir /s /q "%APP_BACKUP%"
if exist "%APP_DIR%" (
  echo [INFO] 기존 결과물을 백업합니다: %APP_DIR% -> %APP_BACKUP%
  move "%APP_DIR%" "%APP_BACKUP%" >nul
)

if exist "build" rmdir /s /q "build"

REM --- Build using spec (options must live in .spec) ---
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean "Ako-ai.spec"
if errorlevel 1 goto :fail

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

:fail
echo.
echo [ERROR] 빌드에 실패했습니다. 위 로그를 확인하세요.
goto :finalize

:end
echo.
pause
endlocal
