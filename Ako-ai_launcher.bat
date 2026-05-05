@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM This launcher makes installed Ako-ai self-healing.
REM It checks Python/venv/Ollama/model first, then starts Ako-ai.exe.

call "%~dp0bootstrap_runtime.bat" --no-pause
if errorlevel 1 (
  echo.
  echo [ERROR] Ako-ai 실행 준비에 실패했습니다.
  echo 설치 폴더의 bootstrap_runtime.bat를 직접 실행해서 로그를 확인해 주세요.
  pause
  exit /b 1
)

if exist "%LOCALAPPDATA%\Ako-ai\runtime\runtime_env.bat" call "%LOCALAPPDATA%\Ako-ai\runtime\runtime_env.bat"

if not exist "%~dp0Ako-ai.exe" (
  echo [ERROR] Ako-ai.exe를 찾지 못했습니다.
  pause
  exit /b 1
)

start "" "%~dp0Ako-ai.exe"
endlocal
