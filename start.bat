@echo off
chcp 65001 >nul
title cafe-os
echo.
echo  ☕ cafe-os 를 시작합니다...
echo.

REM 파이썬 설치 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo  [오류] 파이썬이 설치되어 있지 않습니다.
    echo  https://www.python.org 에서 Python 3.10 이상을 설치하세요.
    echo  설치 시 "Add Python to PATH" 체크 필수!
    pause
    exit /b
)

REM 최초 1회 라이브러리 설치 (이미 있으면 빠르게 통과)
echo  필요한 라이브러리 확인 중...
pip install -q fastapi "uvicorn[standard]" jinja2 qrcode pillow

REM 실행
python run.py
pause
