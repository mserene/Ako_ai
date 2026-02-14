@echo off
setlocal

REM 가상환경 권장: python -m venv .venv && .venv\Scripts\activate
REM 1) 빌드 도구 설치
python -m pip install --upgrade pip
python -m pip install pyinstaller

REM 2) 런타임 의존성 설치(개발 머신에서만)
python -m pip install mss numpy pyautogui winrt-runtime winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging

REM 3) 빌드(one-folder)
pyinstaller --noconfirm --clean ako_ai.spec

echo.
echo Done. dist\ako_ai\ako_ai.exe 를 배포하면 됩니다.
endlocal
