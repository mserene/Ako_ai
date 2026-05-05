@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

set "APP_NAME=Ako-ai"
set "APP_EXE=Ako-ai.exe"
set "OLLAMA_MODEL=exaone3.5:7.8b"
set "SCRIPT_DIR=%~dp0"
set "RUNTIME_ROOT=%LOCALAPPDATA%\Ako-ai\runtime"
set "EMBED_PY_DIR=%RUNTIME_ROOT%\python312"
set "EMBED_PY=%EMBED_PY_DIR%\python.exe"
set "VENV_DIR=%RUNTIME_ROOT%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "REQ_FILE=%SCRIPT_DIR%requirements.txt"
set "PYTHON_EXE="
set "OLLAMA_EXE="
set "NO_PAUSE=0"
set "SKIP_VENV=0"
set "SKIP_MODEL=0"

REM --- Download URLs (embedded package = ~11MB, no admin needed) ---
set "EMBED_PY_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"

if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
if /I "%~2"=="--no-pause" set "NO_PAUSE=1"
if /I "%~1"=="--skip-venv" set "SKIP_VENV=1"
if /I "%~2"=="--skip-venv" set "SKIP_VENV=1"
if /I "%~1"=="--skip-model" set "SKIP_MODEL=1"
if /I "%~2"=="--skip-model" set "SKIP_MODEL=1"

if not exist "%REQ_FILE%" (
  if exist "%SCRIPT_DIR%runtime_requirements.txt" set "REQ_FILE=%SCRIPT_DIR%runtime_requirements.txt"
)

if not exist "%RUNTIME_ROOT%" mkdir "%RUNTIME_ROOT%" >nul 2>&1

set "LOG_FILE=%RUNTIME_ROOT%\bootstrap_runtime.log"
call :log "Starting Ako-ai runtime bootstrap. (v3 - embedded python)"
call :log "Install dir: %SCRIPT_DIR%"
call :log "Runtime dir: %RUNTIME_ROOT%"

echo.
echo [Ako-ai Runtime Setup]
echo 설치에 필요한 Python / venv / Ollama / 모델을 확인합니다.
echo.

REM ============================================================
REM  1) Python 3.12
REM     우선순위: 앱 전용 embedded Python > 시스템 Python
REM     설치 fallback: embedded Python zip (관리자 권한 불필요)
REM ============================================================
echo [1/4] Python 3.12 확인 중...
call :resolve_python

if "%PYTHON_EXE%"=="" (
  echo [INFO] Python 3.12를 찾지 못했습니다.
  echo [INFO] 앱 전용 Embedded Python 3.12를 설치합니다 ^(관리자 권한 불필요^)...
  call :install_embedded_python
  if errorlevel 1 goto :fail_python
  call :resolve_python
)

if "%PYTHON_EXE%"=="" goto :fail_python

call :is_python_312 "%PYTHON_EXE%"
if errorlevel 1 goto :fail_python_version

echo [OK] Python 3.12: %PYTHON_EXE%
call :log "Python 3.12 detected: %PYTHON_EXE%"

REM ============================================================
REM  2) Runtime venv
REM     LocalAppData 아래에 생성 → Program Files 권한 문제 없음
REM ============================================================
if "%SKIP_VENV%"=="1" (
  echo [SKIP] venv 생성/설치를 건너뜁니다.
  goto :after_venv
)

echo.
echo [2/4] Python venv 확인 중...

if exist "%VENV_PY%" (
  "%VENV_PY%" -V >nul 2>&1
  if errorlevel 1 (
    echo [WARN] 기존 runtime venv가 깨져있습니다. 다시 만듭니다.
    call :log "Broken venv found. Recreating."
    rmdir /s /q "%VENV_DIR%" >nul 2>&1
  )
)

if not exist "%VENV_PY%" (
  echo [INFO] runtime venv 생성: %VENV_DIR%
  "%PYTHON_EXE%" -m venv "%VENV_DIR%"
  if errorlevel 1 goto :fail_venv
)

if not exist "%VENV_PY%" goto :fail_venv

echo [INFO] pip 기본 패키지 업데이트 중...
"%VENV_PY%" -m pip install -U pip setuptools wheel
if errorlevel 1 goto :fail_pip

if exist "%REQ_FILE%" (
  echo [INFO] requirements 설치 중: %REQ_FILE%
  "%VENV_PY%" -m pip install -r "%REQ_FILE%"
  if errorlevel 1 goto :fail_requirements
) else (
  echo [WARN] requirements.txt를 찾지 못했습니다. venv만 생성합니다.
  call :log "requirements file not found. venv created only."
)

echo [OK] runtime venv 준비 완료: %VENV_PY%

:after_venv

REM ============================================================
REM  3) Ollama
REM ============================================================
echo.
echo [3/4] Ollama 확인 중...
call :resolve_ollama

if "%OLLAMA_EXE%"=="" (
  echo [INFO] Ollama가 없습니다. 자동 설치를 시도합니다.
  call :install_ollama
  if errorlevel 1 goto :fail_ollama
  call :resolve_ollama
)

if "%OLLAMA_EXE%"=="" goto :fail_ollama

echo [OK] Ollama: %OLLAMA_EXE%
call :log "Ollama detected: %OLLAMA_EXE%"

REM Ollama를 현재 프로세스 PATH에 추가
for %%D in ("%LocalAppData%\Programs\Ollama" "%ProgramFiles%\Ollama" "%ProgramFiles(x86)%\Ollama") do (
  if exist "%%~D\ollama.exe" set "PATH=%%~D;%PATH%"
)

call :ensure_ollama_server

REM ============================================================
REM  4) Ollama model
REM ============================================================
if "%SKIP_MODEL%"=="1" (
  echo [SKIP] Ollama 모델 다운로드를 건너뜁니다.
  goto :after_model
)

echo.
echo [4/4] Ollama 모델 확인 중: %OLLAMA_MODEL%
"%OLLAMA_EXE%" list 2>nul | findstr /I /C:"%OLLAMA_MODEL%" >nul 2>&1
if errorlevel 1 (
  echo [INFO] 모델 다운로드 중입니다. 시간이 오래 걸릴 수 있습니다: %OLLAMA_MODEL%
  "%OLLAMA_EXE%" pull "%OLLAMA_MODEL%"
  if errorlevel 1 goto :fail_model
) else (
  echo [OK] 모델 이미 있음: %OLLAMA_MODEL%
)

:after_model

call :write_runtime_env

echo.
echo [OK] Ako-ai 실행 준비 완료.
call :log "Runtime bootstrap completed successfully."
goto :success

REM ============================================================
REM  Functions
REM ============================================================

:log
>>"%LOG_FILE%" echo [%DATE% %TIME%] %~1
exit /b 0

REM ------------------------------------------------------------
REM  resolve_python
REM  우선순위:
REM    0) 앱 전용 Embedded Python (%RUNTIME_ROOT%\python312)
REM    1) py launcher (py -3.12)
REM    2) 레지스트리 (HKCU / HKLM / WOW6432Node)
REM    3) 일반 설치 경로
REM    4) PATH (WindowsApps alias 제외)
REM ------------------------------------------------------------
:resolve_python
set "PYTHON_EXE="

REM 0) 앱 전용 Embedded Python (가장 우선 - 항상 3.12, 정책 무관)
if exist "%EMBED_PY%" (
  "%EMBED_PY%" -c "import sys; assert sys.version_info[:2]==(3,12)" >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON_EXE=%EMBED_PY%"
    call :log "Using app-local embedded Python: %EMBED_PY%"
    goto :resolve_python_done
  )
)

REM 1) Python launcher (py.exe)
for /f "usebackq delims=" %%I in (`py -3.12 -c "import sys; print(sys.executable)" 2^>nul`) do (
  call :is_python_312 "%%~fI"
  if not errorlevel 1 (
    set "PYTHON_EXE=%%~fI"
    goto :resolve_python_done
  )
)

REM 2) 레지스트리 (PATH 없이 설치된 경우도 탐지)
for %%R in (
  "HKCU\Software\Python\PythonCore\3.12\InstallPath"
  "HKLM\SOFTWARE\Python\PythonCore\3.12\InstallPath"
  "HKLM\SOFTWARE\WOW6432Node\Python\PythonCore\3.12\InstallPath"
) do (
  for /f "tokens=2,*" %%A in ('reg query %%~R /ve 2^>nul ^| findstr /I "REG_SZ"') do (
    if exist "%%~B\python.exe" (
      call :is_python_312 "%%~B\python.exe"
      if not errorlevel 1 (
        set "PYTHON_EXE=%%~B\python.exe"
        goto :resolve_python_done
      )
    )
  )
)

REM 3) 일반 설치 경로
for %%P in (
  "%LocalAppData%\Programs\Python\Python312\python.exe"
  "%ProgramFiles%\Python312\python.exe"
  "%ProgramFiles(x86)%\Python312\python.exe"
  "C:\Python312\python.exe"
) do (
  if exist "%%~P" (
    call :is_python_312 "%%~P"
    if not errorlevel 1 (
      set "PYTHON_EXE=%%~P"
      goto :resolve_python_done
    )
  )
)

REM 4) PATH fallback (Microsoft Store alias 제외)
for %%C in (python python3) do (
  for /f "delims=" %%I in ('where %%C 2^>nul') do (
    echo "%%~fI" | findstr /I /C:"\WindowsApps\" >nul
    if errorlevel 1 (
      call :is_python_312 "%%~fI"
      if not errorlevel 1 (
        set "PYTHON_EXE=%%~fI"
        goto :resolve_python_done
      )
    ) else (
      echo [WARN] Microsoft Store Python alias 무시: %%~fI
      call :log "Ignored Microsoft Store Python alias: %%~fI"
    )
  )
)

:resolve_python_done
exit /b 0

REM ------------------------------------------------------------
REM  is_python_312  - 버전 번호만 확인 (venv/ensurepip 체크 제거)
REM  embedded Python에서는 bootstrap 전에 ensurepip import가 실패하므로
REM  버전 확인만으로 충분함.
REM ------------------------------------------------------------
:is_python_312
set "PY_MINOR="
for /f "usebackq delims=" %%V in (`"%~1" -c "import sys; print(str(sys.version_info[0])+'.'+str(sys.version_info[1]))" 2^>nul`) do (
  set "PY_MINOR=%%V"
)
if "%PY_MINOR%"=="3.12" exit /b 0
exit /b 1

REM ------------------------------------------------------------
REM  install_embedded_python
REM  python-3.12.x-embed-amd64.zip 다운로드 후:
REM    1) 압축 해제 → %EMBED_PY_DIR%
REM    2) python312._pth 패치 (import site 활성화)
REM    3) get-pip.py로 pip 설치
REM  관리자 권한 불필요 / winget 불필요 / 조직 정책 무관
REM ------------------------------------------------------------
:install_embedded_python
set "ZIP_TEMP=%TEMP%\python-3.12.10-embed-amd64.zip"
set "GETPIP_TEMP=%TEMP%\get-pip.py"

echo [INFO] Embedded Python 3.12 다운로드 중 (~11MB)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%EMBED_PY_URL%' -OutFile '%ZIP_TEMP%' -UseBasicParsing; exit 0 } catch { Write-Host ('다운로드 실패: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
  echo [ERROR] Embedded Python 다운로드 실패. 인터넷 연결을 확인해 주세요.
  call :log "ERROR: Embedded Python download failed."
  exit /b 1
)

if not exist "%EMBED_PY_DIR%" mkdir "%EMBED_PY_DIR%" >nul 2>&1

echo [INFO] 압축 해제 중: %EMBED_PY_DIR%
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Expand-Archive -Path '%ZIP_TEMP%' -DestinationPath '%EMBED_PY_DIR%' -Force; exit 0 } catch { Write-Host ('압축 해제 실패: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
  echo [ERROR] Embedded Python 압축 해제 실패.
  call :log "ERROR: Embedded Python extraction failed."
  exit /b 1
)

REM python312._pth 패치: '#import site' → 'import site'
REM 이 줄을 주석 해제해야 pip/venv가 site-packages를 인식함
echo [INFO] python312._pth 패치 중 (import site 활성화)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$f = '%EMBED_PY_DIR%\python312._pth'; if (Test-Path $f) { $c = Get-Content $f; $p = $c -replace '^#import site', 'import site'; Set-Content -Path $f -Value $p -Encoding ASCII; Write-Host 'OK' } else { Write-Host '[WARN] python312._pth not found. pip may not work correctly.' }"

REM get-pip.py 다운로드 및 pip 설치
echo [INFO] pip 설치 중 (get-pip.py)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%GET_PIP_URL%' -OutFile '%GETPIP_TEMP%' -UseBasicParsing; exit 0 } catch { Write-Host ('get-pip.py 다운로드 실패: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
  echo [ERROR] get-pip.py 다운로드 실패.
  call :log "ERROR: get-pip.py download failed."
  exit /b 1
)

"%EMBED_PY_DIR%\python.exe" "%GETPIP_TEMP%"
if errorlevel 1 (
  echo [ERROR] pip 설치 실패.
  call :log "ERROR: pip bootstrap via get-pip.py failed."
  exit /b 1
)

call :log "Embedded Python 3.12 installed: %EMBED_PY_DIR%"
echo [OK] Embedded Python 3.12 설치 완료.

REM 임시 파일 정리
del /f /q "%ZIP_TEMP%" >nul 2>&1
del /f /q "%GETPIP_TEMP%" >nul 2>&1

exit /b 0

REM ------------------------------------------------------------
:resolve_ollama
set "OLLAMA_EXE="
for /f "delims=" %%I in ('where ollama 2^>nul') do (
  if exist "%%~fI" (
    set "OLLAMA_EXE=%%~fI"
    goto :resolve_ollama_done
  )
)
if exist "%LocalAppData%\Programs\Ollama\ollama.exe" (
  set "OLLAMA_EXE=%LocalAppData%\Programs\Ollama\ollama.exe"
  goto :resolve_ollama_done
)
if exist "%ProgramFiles%\Ollama\ollama.exe" (
  set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"
  goto :resolve_ollama_done
)
if exist "%ProgramFiles(x86)%\Ollama\ollama.exe" (
  set "OLLAMA_EXE=%ProgramFiles(x86)%\Ollama\ollama.exe"
  goto :resolve_ollama_done
)
:resolve_ollama_done
exit /b 0

:install_ollama
echo [INFO] Ollama 설치 파일 다운로드 중...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $url='https://ollama.com/download/OllamaSetup.exe'; $out=Join-Path $env:TEMP 'OllamaSetup.exe'; Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing; $p=Start-Process -FilePath $out -ArgumentList '/S' -Wait -PassThru; if ($p.ExitCode -ne 0) { $p=Start-Process -FilePath $out -Wait -PassThru }; exit $p.ExitCode"
if errorlevel 1 exit /b 1
timeout /t 3 /nobreak >nul
exit /b 0

:ensure_ollama_server
"%OLLAMA_EXE%" list >nul 2>&1
if not errorlevel 1 exit /b 0

echo [INFO] Ollama 서버 시작 시도...
start "" /min "%OLLAMA_EXE%" serve

timeout /t 5 /nobreak >nul
"%OLLAMA_EXE%" list >nul 2>&1
if errorlevel 1 (
  echo [WARN] Ollama 서버 확인에 실패했습니다. 모델 다운로드 단계에서 다시 시도됩니다.
  call :log "Ollama server check failed after start attempt."
)
exit /b 0

:write_runtime_env
set "ENV_FILE=%RUNTIME_ROOT%\runtime_env.bat"
>"%ENV_FILE%" echo @echo off
>>"%ENV_FILE%" echo set "AKO_RUNTIME_ROOT=%RUNTIME_ROOT%"
>>"%ENV_FILE%" echo set "AKO_PYTHON_EXE=%PYTHON_EXE%"
>>"%ENV_FILE%" echo set "AKO_VENV_PY=%VENV_PY%"
>>"%ENV_FILE%" echo set "AKO_OLLAMA_EXE=%OLLAMA_EXE%"
>>"%ENV_FILE%" echo set "AKO_OLLAMA_MODEL=%OLLAMA_MODEL%"
>>"%ENV_FILE%" echo set "PATH=%LocalAppData%\Programs\Ollama;%ProgramFiles%\Ollama;%%PATH%%"

REM 앱 폴더에도 프록시 복사 (Program Files면 실패할 수 있으므로 에러 무시)
>"%SCRIPT_DIR%runtime_env.bat" echo @echo off 2>nul
>>"%SCRIPT_DIR%runtime_env.bat" echo call "%%LOCALAPPDATA%%\Ako-ai\runtime\runtime_env.bat" 2>nul

call :log "Runtime env written: %ENV_FILE%"
exit /b 0

REM ============================================================
REM  Error handlers
REM ============================================================
:fail_python
echo.
echo [ERROR] Python 3.12 설치/감지 실패.
echo 인터넷 연결을 확인하거나 Python 3.12를 수동 설치해 주세요:
echo   https://www.python.org/downloads/release/python-31210/
call :log "ERROR: Python 3.12 install/detect failed."
goto :failed

:fail_python_version
echo.
echo [ERROR] Python 3.12만 허용됩니다. 감지된 Python: %PYTHON_EXE%
call :log "ERROR: Wrong Python version detected: %PYTHON_EXE%"
goto :failed

:fail_venv
echo.
echo [ERROR] runtime venv 생성 실패: %VENV_DIR%
call :log "ERROR: venv creation failed."
goto :failed

:fail_pip
echo.
echo [ERROR] pip 업데이트 실패.
call :log "ERROR: pip update failed."
goto :failed

:fail_requirements
echo.
echo [ERROR] requirements 설치 실패.
echo 로그: %LOG_FILE%
call :log "ERROR: requirements install failed."
goto :failed

:fail_ollama
echo.
echo [ERROR] Ollama 설치/감지 실패.
echo 수동 설치 후 다시 실행해 주세요: https://ollama.com/download
call :log "ERROR: Ollama install/detect failed."
goto :failed

:fail_model
echo.
echo [ERROR] Ollama 모델 다운로드 실패: %OLLAMA_MODEL%
echo 인터넷 연결과 Ollama 실행 상태를 확인한 뒤 다시 실행해 주세요.
call :log "ERROR: Ollama model pull failed: %OLLAMA_MODEL%"
goto :failed

:failed
echo.
echo [FAIL] Ako-ai 실행 준비 실패.
echo 로그 파일: %LOG_FILE%
if "%NO_PAUSE%"=="0" pause
endlocal & exit /b 1

:success
if "%NO_PAUSE%"=="0" pause
endlocal & exit /b 0
