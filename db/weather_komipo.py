"""
db/weather_komipo.py — 한국중부발전 발전소 주변 기상 API 어댑터

⚠️ 이 소스는 '카페가 발전소 인근(보령/서천/세종/제주/인천)'일 때만 권장.
   - 일(日) 단위 데이터 (시간대별 아님)
   - 발전소 위치 기준 (카페가 멀면 부정확)
   - 일반 카페는 db/weather.py(기상청 단기예보)를 쓰는 게 낫다.

설정 (.cafe_config.json):
  weather_source : "komipo"  (이 소스를 쓰려면)
  komipo_service_key : 발급 인증키 (Decoding 키 권장)
  komipo_station : 발전본부 코드 (포털 '미리보기'에서 확인 필요)

stationName 코드는 API 참고문서에 있으나 현재 '복구중'.
→ 공공데이터포털 > 마이페이지 > 이 API > '미리보기'에서
   여러 코드를 넣어보고 응답이 오는 값을 찾으세요.
   (발전본부: 보령/신보령/신서천/세종/제주/인천)
"""
import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from db.store import get_conn

CONFIG_PATH = os.path.join(BASE_DIR, ".cafe_config.json")
URL = "http://apis.data.go.kr/B552521/weatherInfo/getData"


def _cfg(key, default=None):
    if os.environ.get(key.upper()):
        return os.environ[key.upper()]
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f).get(key.lower(), default)
    return default


def fetch_komipo_weather(date_ymd=None):
    """
    발전소 주변 기상 조회. 반환: {"cond","temp","humidity","rain"} 또는 None.
    cond 는 강수량 기반 추정(이 API는 하늘상태 코드를 안 줌):
      강수량>0 → Rain, 아니면 None(맑음/흐림 구분 불가)
    """
    key = _cfg("komipo_service_key")
    station = _cfg("komipo_station")
    if not key or not station:
        return None

    # 어제 데이터 (당일은 아직 집계 안 됐을 수 있음)
    if date_ymd is None:
        date_ymd = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    else:
        date_ymd = date_ymd.replace("-", "")

    try:
        q = urllib.parse.urlencode({
            "serviceKey": key,        # Decoding 키면 그대로, Encoding 키면 safe="%" 추가
            "stationName": station,
            "dataDate": date_ymd,
            "dataTerm": "DAILY",
        })
        req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": "cafe-os"})
        with urllib.request.urlopen(req, timeout=10) as r:
            xml = r.read().decode("utf-8")

        root = ET.fromstring(xml)
        item = root.find(".//item")
        if item is None:
            return None

        def g(tag):
            el = item.find(tag)
            return el.text if el is not None else None

        temp = g("qtep")        # 온도
        hum = g("qhmd")         # 습도
        rain = g("qarf")        # 강수량
        temp = float(temp) if temp not in (None, "") else None
        hum = float(hum) if hum not in (None, "") else None
        rain = float(rain) if rain not in (None, "") else 0.0

        cond = "Rain" if rain and rain > 0 else None
        return {"cond": cond, "temp": temp, "humidity": hum, "rain": rain}
    except Exception as e:
        print(f"[발전소날씨] 수집 실패: {e}")
        return None


def cache_komipo_weather():
    """발전소 기상을 weather_cache 에 저장."""
    w = fetch_komipo_weather()
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
