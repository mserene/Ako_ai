# Ako 배포(Windows) 가이드

## 목표
사용자는 `Ako-ai.exe`만 실행하면:
1) GUI가 즉시 뜸
2) 음성 인식을 켜면 필요한 STT 모델이 자동 다운로드됨 (처음 1회)
3) 이후엔 캐시된 모델을 사용

> 주의: STT 모델(예: small)은 용량이 큽니다. 첫 다운로드는 시간이 걸릴 수 있어요.

## 빌드(개발자 PC)
### 1) 가상환경
```bat
python -m venv .venv
.venv\Scripts\activate
```

### 2) 의존성 설치
```bat
pip install -r requirements.txt
```

### 3) 빌드
```bat
build_onefolder.bat
```

빌드 결과:
- `dist\Ako-ai\Ako-ai.exe`
