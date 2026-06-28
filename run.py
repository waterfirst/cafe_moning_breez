"""
cafe-os 자동 런처
포크한 카페가 이 파일 하나만 실행하면:
  1. 노트북 LAN IP 자동 탐지
  2. 첫 실행 시 관리자 토큰 자동 생성 (.cafe_config.json)
  3. 손님 주문용 QR 코드 자동 생성 (qr_order.png)
  4. FastAPI 서버 기동
  5. 손님 화면(/display)·주방 화면(/kitchen) 브라우저 자동 오픈

사용법:
  python run.py
  또는 윈도우면  start.bat  더블클릭
"""
import os
import sys
import json
import socket
import secrets
import threading
import webbrowser
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, ".cafe_config.json")
QR_PATH = os.path.join(BASE_DIR, "qr_order.png")
PORT = int(os.environ.get("CAFE_PORT", "8000"))


def get_lan_ip():
    """노트북의 LAN IP 자동 탐지 (인터넷 없어도 동작)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # 실제 전송 X, 라우팅만 확인
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def load_or_create_config():
    """첫 실행이면 관리자 토큰 생성. 이후엔 기존 것 재사용."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    cfg = {
        "admin_token": secrets.token_urlsafe(16),  # 주방/관리 화면 접근 키
        "cafe_name": "우리 카페",
        "weather_source": "kma",        # 기상청 단기예보 (전주 등 전국)
        "cafe_lat": 35.8242,            # 카페 위도 (기본: 전주시청)
        "cafe_lon": 127.1480,           # 카페 경도
        "kma_service_key": "",         # 공공데이터포털 기상청 키 (날씨 분석 시 입력)
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


def make_qr(url):
    """손님 주문 URL → QR 이미지 파일."""
    try:
        import qrcode
        img = qrcode.make(url)
        img.save(QR_PATH)
        return True
    except Exception as e:
        print(f"[경고] QR 생성 실패(qrcode 미설치?): {e}")
        return False


def open_browsers(ip, token):
    """서버 뜬 뒤 관리 화면 자동 오픈 (손님 화면은 HDMI에 띄움)."""
    time.sleep(2.0)
    base = f"http://{ip}:{PORT}"
    webbrowser.open(f"{base}/display")                       # 손님 모니터(HDMI)
    webbrowser.open(f"{base}/kitchen?token={token}")         # 주방 관리창


def weather_loop():
    """30분마다 날씨 수집해서 캐시. 키 없으면 조용히 쉼.
    config의 weather_source 로 소스 선택: 'kma'(기본,기상청) / 'komipo'(발전소)"""
    source = "kma"
    cfg_path = os.path.join(BASE_DIR, ".cafe_config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                source = json.load(f).get("weather_source", "kma")
        except Exception:
            pass

    try:
        if source == "komipo":
            from db.weather_komipo import cache_komipo_weather as cache_fn
        else:
            from db.weather import cache_weather as cache_fn
    except Exception:
        return

    while True:
        try:
            w = cache_fn()
            if w:
                print(f"[날씨/{source}] 수집: {w.get('cond')} {w.get('temp')}도")
        except Exception as e:
            print(f"[날씨] 수집 오류: {e}")
        time.sleep(1800)  # 30분


def main():
    ip = get_lan_ip()
    cfg = load_or_create_config()
    token = cfg["admin_token"]
    order_url = f"http://{ip}:{PORT}/"

    make_qr(order_url)

    print("=" * 52)
    print(f"  ☕ cafe-os 시작  ({cfg['cafe_name']})")
    print("=" * 52)
    print(f"  손님 주문 주소 : {order_url}")
    print(f"  QR 코드 파일   : {QR_PATH}")
    print(f"     → 이 QR을 인쇄해 테이블에 붙이세요")
    print(f"  손님 화면(HDMI): http://{ip}:{PORT}/display")
    print(f"  주방 관리창    : http://{ip}:{PORT}/kitchen?token={token}")
    print(f"  관리자 토큰    : {token}")
    print("-" * 52)
    print("  ⚠ 공유기 포트포워딩을 켜지 마세요 (외부 노출 위험)")
    print("  ⚠ 종료하려면 이 창에서 Ctrl+C")
    print("=" * 52)

    threading.Thread(target=open_browsers, args=(ip, token), daemon=True).start()
    threading.Thread(target=weather_loop, daemon=True).start()

    import uvicorn
    # 0.0.0.0 = 같은 와이파이의 손님 폰이 접속 가능해야 하므로 필요.
    # 단, 관리 경로는 토큰으로 보호됨.
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, log_level="warning")


if __name__ == "__main__":
    # app 패키지 import 가능하도록 루트를 path에 추가
    sys.path.insert(0, BASE_DIR)
    main()
