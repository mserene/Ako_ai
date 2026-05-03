AKO 로딩 화면 패치 사용법
=========================

이 압축파일은 MP4를 직접 재생하지 않고, MP4에서 뽑은 JPG 프레임을 Tkinter + Pillow로 보여주는 로딩 화면 패치입니다.

포함 파일
---------

- apply_loading_patch.py
  자동 패치 스크립트입니다.

- _patch_files/loading_overlay.py
  프레임 이미지 기반 로딩 화면 파일입니다.

- _patch_files/core/__init__.py
  core.config 삭제 후 생긴 오류를 막는 정리 버전입니다.

- assets/loading/frames/
  프레임 이미지가 들어갈 폴더입니다.

사용 순서
---------

1. 이 압축파일을 프로젝트 루트에 압축 해제하세요.

예:
D:\ms_ai\Ako_ai

2. PowerShell에서 프로젝트 루트로 이동하세요.

cd D:\ms_ai\Ako_ai

3. 자동 패치 실행:

python apply_loading_patch.py

4. 프레임 폴더 확인 및 기존 프레임 삭제:

mkdir assets\loading\frames -Force
Remove-Item assets\loading\frames\frame_*.jpg -ErrorAction SilentlyContinue

5. MP4에서 앞 5초만 프레임 추출:

ffmpeg -y -ss 0 -t 5 -i assets\loading\ako_loading.mp4 -vf "fps=24,scale=940:-2" -q:v 3 assets\loading\frames\frame_%03d.jpg

6. 실행 테스트:

python app.py --mode=gui

주의
----

원본 MP4가 1분 이상이면 전체를 프레임으로 뽑지 마세요.
로딩용으로는 5초 정도만 추천합니다.

이 방식은 cv2/opencv-python을 쓰지 않습니다.
Pillow만 사용합니다.
