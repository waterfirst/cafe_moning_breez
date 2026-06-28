#!/usr/bin/env bash
# cafe-os 실행 (맥 / 리눅스)
set -e
cd "$(dirname "$0")"

echo "☕ cafe-os 를 시작합니다..."

if ! command -v python3 &>/dev/null; then
    echo "[오류] python3 가 필요합니다. https://www.python.org 에서 설치하세요."
    exit 1
fi

echo "필요한 라이브러리 확인 중..."
pip3 install -q fastapi "uvicorn[standard]" jinja2 qrcode pillow

python3 run.py
