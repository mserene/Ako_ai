@echo off
setlocal

REM one-folder build for ako_ai
REM 빌드 전에 현재 파이썬 환경에 의존성 설치가 필요합니다:
REM   python -m pip install pyinstaller mss numpy pyautogui pillow pytesseract
REM 그리고 tools\tesseract\ 아래에 tesseract.exe + tessdata(eng/kor traineddata)를 넣어주세요.

python -m PyInstaller --clean --noconfirm .\ako_ai.spec

echo.
echo [DONE] dist\ako_ai\ako_ai.exe 생성 완료
endlocal
