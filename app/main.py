"""
app/main.py — cafe-os FastAPI 본체
손님 주문(/), 손님 화면(/display), 주방 관리(/kitchen), API 포함.
관리 경로는 admin_token으로 보호.
"""
import os
import json
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates

import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from db.store import (
    init_db, save_order, set_status, get_today_board
)
from analytics import queries as Q

CONFIG_PATH = os.path.join(BASE_DIR, ".cafe_config.json")
QR_PATH = os.path.join(BASE_DIR, "qr_order.png")


def get_admin_token():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f).get("admin_token", "")
    return ""


app = FastAPI(title="cafe-os")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))
init_db()


def require_admin(token: str):
    """관리 경로 토큰 검증. 틀리면 403."""
    if token != get_admin_token() or not token:
        raise HTTPException(status_code=403, detail="관리자 토큰이 필요합니다")


# ── 손님: 주문 페이지 ────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def order_page(request: Request):
    # 실제 주문 UI는 기존 카페 주문 앱을 연결. 여기선 자리표시.
    return templates.TemplateResponse(request, "order.html")


@app.get("/qr")
def qr_image():
    if os.path.exists(QR_PATH):
        return FileResponse(QR_PATH, media_type="image/png")
    raise HTTPException(404, "QR 미생성")


# ── 손님: 번호판 (HDMI, 읽기 전용) ───────────────────────────
@app.get("/display", response_class=HTMLResponse)
def display(request: Request):
    return templates.TemplateResponse(request, "display.html")


# ── 주방: 관리창 (토큰 필요) ─────────────────────────────────
@app.get("/kitchen", response_class=HTMLResponse)
def kitchen(request: Request, token: str = Query("")):
    require_admin(token)
    return templates.TemplateResponse(request, "kitchen.html", {"token": token})


# ── API ──────────────────────────────────────────────────────
@app.get("/api/orders")
def api_orders():
    # 읽기는 공개(손님 번호판이 폴링). 단 민감정보는 안 내려감.
    return JSONResponse(get_today_board())


@app.post("/api/orders")
def api_create(payload: dict):
    """
    기존 주문 앱이 호출. payload 예:
    {"table_no":"2","items":[{"name":"카페모카","qty":1,"unit_price":5200,"options":"샷 추가"}]}
    """
    no = save_order(
        table_no=payload.get("table_no", ""),
        items=payload.get("items", []),
    )
    return {"ok": True, "order_no": no}


@app.post("/api/orders/{order_no}/done")
def api_done(order_no: int, token: str = Query("")):
    require_admin(token)         # 완료 처리는 사장만
    set_status(order_no, "done")
    return {"ok": True, "order_no": order_no, "status": "done"}


@app.post("/api/orders/{order_no}/pick")
def api_pick(order_no: int, token: str = Query("")):
    require_admin(token)
    set_status(order_no, "picked")
    return {"ok": True, "order_no": order_no, "status": "picked"}


# ── 분석 대시보드 (토큰 필요 — 매출은 사장만) ────────────────
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, token: str = Query("")):
    require_admin(token)
    return templates.TemplateResponse(request, "dashboard.html", {"token": token})


@app.get("/api/analytics")
def api_analytics(token: str = Query("")):
    require_admin(token)         # 매출 데이터는 사장만
    return JSONResponse({
        "summary": Q.today_summary(),
        "hourly": Q.today_hourly_menu(),
        "weekday": Q.by_weekday(),
        "weather": Q.by_weather(),
        "monthly": Q.sales_monthly(),
        "hour_avg": Q.by_hour_avg(),
    })
