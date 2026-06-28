"""
db/weather.py — 기상청 단기예보 API 연동

수집 데이터: 기온, 습도, 강수형태, 하늘상태(맑음/구름/비/눈)
- 초단기실황(getUltraSrtNcst): 기온(T1H)·습도(REH)·강수형태(PTY) — 1시간 단위
- 단기예보(getVilageFcst): 하늘상태(SKY) — 3시간 단위

설정 (.cafe_config.json 또는 환경변수):
  KMA_SERVICE_KEY : 공공데이터포털 발급 키 (필수)
  CAFE_LAT, CAFE_LON : 카페 위경도 (없으면 서울시청 기본)

키 없으면 날씨 수집을 건너뛰고 None 반환 (앱은 정상 동작).
"""
import os
import json
import math
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from db.store import get_conn

CONFIG_PATH = os.path.join(BASE_DIR, ".cafe_config.json")
BASE_URL = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"

# 하늘상태/강수형태 코드 → 한글
SKY = {"1": "Clear", "3": "Clouds", "4": "Clouds"}  # 맑음/구름많음/흐림
PTY = {"0": None, "1": "Rain", "2": "Rain", "3": "Snow",
       "4": "Rain", "5": "Rain", "6": "Snow", "7": "Snow"}


def _cfg(key, default=None):
    if os.environ.get(key):
        return os.environ[key]
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f).get(key.lower(), default)
    return default


def latlon_to_grid(lat, lon):
    """위경도 → 기상청 격자 (nx, ny). 검증된 표준 LCC 변환."""
    RE, GRID = 6371.00877, 5.0
    SLAT1, SLAT2, OLON, OLAT, XO, YO = 30.0, 60.0, 126.0, 38.0, 43, 136
    D = math.pi / 180.0
    re = RE / GRID
    s1, s2, ol, oa = SLAT1 * D, SLAT2 * D, OLON * D, OLAT * D
    sn = math.log(math.cos(s1) / math.cos(s2)) / math.log(
        math.tan(math.pi*0.25 + s2*0.5) / math.tan(math.pi*0.25 + s1*0.5))
    sf = math.pow(math.tan(math.pi*0.25 + s1*0.5), sn) * math.cos(s1) / sn
    ro = re * sf / math.pow(math.tan(math.pi*0.25 + oa*0.5), sn)
    ra = re * sf / math.pow(math.tan(math.pi*0.25 + lat*D*0.5), sn)
    theta = lon * D - ol
    if theta > math.pi: theta -= 2*math.pi
    if theta < -math.pi: theta += 2*math.pi
    theta *= sn
    nx = int(ra*math.sin(theta) + XO + 0.5)
    ny = int(ro - ra*math.cos(theta) + YO + 0.5)
    return nx, ny


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "cafe-os"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_current_weather():
    """
    지금 시점 날씨 수집. 반환: {"cond","temp","humidity"} 또는 None(키 없거나 실패).
    cond: Clear/Clouds/Rain/Snow
    """
    key = _cfg("KMA_SERVICE_KEY")
    if not key:
        return None  # 키 없으면 조용히 건너뜀

    lat = float(_cfg("CAFE_LAT", 37.5665))
    lon = float(_cfg("CAFE_LON", 126.9780))
    nx, ny = latlon_to_grid(lat, lon)

    now = datetime.now()
    # 실황은 매시 40분 이후 제공 → 안전하게 1시간 전 기준
    base = now - timedelta(hours=1)
    base_date = base.strftime("%Y%m%d")
    base_time = base.strftime("%H00")

    result = {"cond": None, "temp": None, "humidity": None}

    # 1) 초단기실황: 기온·습도·강수형태
    try:
        q = urllib.parse.urlencode({
            "serviceKey": key, "dataType": "JSON", "numOfRows": 60,
            "pageNo": 1, "base_date": base_date, "base_time": base_time,
            "nx": nx, "ny": ny,
        }, safe="%")
        data = _get_json(f"{BASE_URL}/getUltraSrtNcst?{q}")
        items = data["response"]["body"]["items"]["item"]
        pty = "0"
        for it in items:
            cat, val = it["category"], it["obsrValue"]
            if cat == "T1H": result["temp"] = float(val)
            elif cat == "REH": result["humidity"] = float(val)
            elif cat == "PTY": pty = val
        # 강수 있으면 우선 (비/눈)
        if PTY.get(pty):
            result["cond"] = PTY[pty]
    except Exception as e:
        print(f"[날씨] 실황 수집 실패: {e}")

    # 2) 강수 없으면 단기예보로 하늘상태(맑음/구름)
    if not result["cond"]:
        try:
            # 단기예보 발표시각 (02,05,08,11,14,17,20,23)
            fb = _vilage_base(now)
            q = urllib.parse.urlencode({
                "serviceKey": key, "dataType": "JSON", "numOfRows": 300,
                "pageNo": 1, "base_date": fb[0], "base_time": fb[1],
                "nx": nx, "ny": ny,
            }, safe="%")
            data = _get_json(f"{BASE_URL}/getVilageFcst?{q}")
            items = data["response"]["body"]["items"]["item"]
            target = now.strftime("%H00")
            for it in items:
                if it["category"] == "SKY" and it["fcstTime"] >= target:
                    result["cond"] = SKY.get(it["fcstValue"], "Clouds")
                    break
        except Exception as e:
            print(f"[날씨] 예보 수집 실패: {e}")

    return result if result["cond"] or result["temp"] is not None else None


def _vilage_base(now):
    """단기예보 가장 최근 발표시각 계산."""
    hours = [2, 5, 8, 11, 14, 17, 20, 23]
    h = now.hour
    chosen = 23
    date = now
    for x in hours:
        if h >= x + 1:  # 발표 후 약 10분 뒤 제공, 안전하게 +1시간
            chosen = x
    if h < 3:  # 새벽이면 전날 23시
        date = now - timedelta(days=1)
        chosen = 23
    return date.strftime("%Y%m%d"), f"{chosen:02d}00"


def cache_weather():
    """
    현재 날씨를 weather_cache 에 저장 (cron/주기 호출용).
    주문 시 store.get_weather 가 이 캐시를 읽는다.
    """
    w = fetch_current_weather()
    if not w:
        return None
    now = datetime.now()
    con = get_conn()
    try:
        con.execute(
            """INSERT OR REPLACE INTO weather_cache(date_ymd, hour, cond, temp, fetched_at)
               VALUES(?,?,?,?,?)""",
            (now.strftime("%Y-%m-%d"), now.hour, w["cond"], w["temp"],
             now.strftime("%Y-%m-%d %H:%M:%S")),
        )
        con.commit()
        return w
    finally:
        con.close()
