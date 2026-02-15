# Ako_ai (정리본)

## 핵심 실행

### 1) 텍스트 명령 테스트
```bash
python app.py --mode=actions --text "크롬 켜줘"
python app.py --mode=actions --text "오른쪽 위에 있는 닫기 눌러줘"
python app.py --mode=actions --text "유튜브 재생 눌러줘"
```

### 2) 음성(마이크)로 명령 실행
> 말하고 **잠깐 멈추면** 무음으로 인식 종료 → 텍스트 변환 → actions 실행

```bash
python app.py --mode=voice
```

웨이크워드(예: "아코")를 쓰면, 그 단어가 포함/시작할 때만 실행합니다.
```bash
python app.py --mode=voice --wake "아코"
```

마이크 장치 선택(기본 장치가 안 맞을 때)
```bash
python app.py --mode=voice --device 1
```

인식이 너무 빨리/늦게 끊기면 무음 설정을 조절합니다.
```bash
python app.py --mode=voice --silence 1.2 --thresh 0.010
```

## 의존성
- UI 클릭/OCR: `pyautogui`, `mss`, `pillow`, `pytesseract`, `numpy`
- 음성(STT): `sounddevice`, `faster-whisper` (+ 환경에 따라 torch/cuda)

예시:
```bash
pip install numpy pyautogui mss pillow pytesseract sounddevice faster-whisper
```

## 정리 포인트
- 배포 산출물(`dist/`, `build/`)과 빌드용 가상환경(`.venv_build/`), git 메타데이터(`.git/`)는 제거했습니다.
- 실제 소스 + 설정 파일만 남겨서 단계가 꼬이지 않게 했습니다.
