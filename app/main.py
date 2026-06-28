"""
app/main.py — cafe-os FastAPI 본체
손님 주문(/), 손님 화면(/display), 주방 관리(/kitchen), API 포함.
관리 경로는 admin_token으로 보호.
"""
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_PATH = Path(BASE_DIR)
sys.path.insert(0, BASE_DIR)
load_dotenv(BASE_PATH / ".env")

from db.store import get_today_board, init_db, save_order, set_status
from analytics import queries as Q

CONFIG_PATH = os.path.join(BASE_DIR, ".cafe_config.json")
QR_PATH = os.path.join(BASE_DIR, "qr_order.png")
ORDER_DATA_DIR = BASE_PATH / "data" / "orders"


CATEGORIES = [
    {"id": "coffee", "name": "커피", "hint": "아메리카노, 라떼"},
    {"id": "noncoffee", "name": "논커피", "hint": "초콜릿, 버블티"},
    {"id": "blended", "name": "블렌디드", "hint": "스무디, 쉐이크"},
    {"id": "ade", "name": "에이드·주스", "hint": "과일 음료"},
    {"id": "tea", "name": "티", "hint": "허브티, 밀크티"},
]

MENU = [
    {"id": "americano", "category": "coffee", "name": "아메리카노", "price": 3200, "badge": "기본"},
    {"id": "mild-coffee", "category": "coffee", "name": "달달커피", "price": 3200, "badge": "달콤"},
    {"id": "hazelnut-americano", "category": "coffee", "name": "헤이즐넛 아메리카노", "price": 3900, "badge": "향긋"},
    {"id": "white-americano", "category": "coffee", "name": "꿀화이트 아메리카노", "price": 3900, "badge": "꿀"},
    {"id": "coldbrew", "category": "coffee", "name": "콜드브루", "price": 4200, "badge": "ICE"},
    {"id": "cafe-latte", "category": "coffee", "name": "카페라떼", "price": 4200, "badge": "인기"},
    {"id": "vanilla-latte", "category": "coffee", "name": "바닐라라떼", "price": 4500, "badge": "부드러움"},
    {"id": "black-sugar-coldbrew", "category": "coffee", "name": "흑당 콜드브루", "price": 4500, "badge": "달콤"},
    {"id": "cafe-mocha", "category": "coffee", "name": "카페모카", "price": 4500, "badge": "초코"},
    {"id": "affogato", "category": "coffee", "name": "아포가토", "price": 4700, "badge": "디저트"},
    {"id": "signature-latte", "category": "coffee", "name": "시그니처 라떼", "price": 4700, "badge": "추천"},
    {"id": "mint-mocha", "category": "coffee", "name": "민트모카", "price": 4900, "badge": "민트"},
    {"id": "milk-sunrise-latte", "category": "noncoffee", "name": "흑당라떼", "price": 3900, "badge": "라떼"},
    {"id": "grain-latte", "category": "noncoffee", "name": "미숫가루라떼", "price": 3900, "badge": "고소"},
    {"id": "chocolate", "category": "noncoffee", "name": "초콜릿", "price": 4200, "badge": "초코"},
    {"id": "dalgona-latte", "category": "noncoffee", "name": "달고나라떼", "price": 4200, "badge": "달고나"},
    {"id": "matcha-latte", "category": "noncoffee", "name": "말차라떼", "price": 4500, "badge": "녹차"},
    {"id": "toffee-latte", "category": "noncoffee", "name": "토피넛라떼", "price": 4500, "badge": "고소"},
    {"id": "strawberry-latte", "category": "noncoffee", "name": "딸기듬뿍라떼", "price": 4500, "badge": "과일"},
    {"id": "strawberry-chocolate", "category": "noncoffee", "name": "딸기초코라떼", "price": 4700, "badge": "달콤"},
    {"id": "bubble-black-sugar", "category": "noncoffee", "name": "버블 흑당라떼", "price": 5100, "badge": "버블"},
    {"id": "peach-mango-blended", "category": "blended", "name": "과일 플랫치노", "price": 3900, "badge": "ICE"},
    {"id": "milk-flatccino", "category": "blended", "name": "밀크 플랫치노", "price": 4700, "badge": "크림"},
    {"id": "yogurt-flatccino", "category": "blended", "name": "요거트 플랫치노", "price": 4900, "badge": "상큼"},
    {"id": "milkshake", "category": "blended", "name": "밀크쉐이크", "price": 4900, "badge": "쉐이크"},
    {"id": "choco-cookie-shake", "category": "blended", "name": "초코쿠키쉐이크", "price": 5100, "badge": "쿠키"},
    {"id": "strawberry-matcha-shake", "category": "blended", "name": "딸기쉐이크", "price": 5400, "badge": "딸기"},
    {"id": "cleanse-juice", "category": "ade", "name": "클렌즈주스", "price": 4200, "badge": "주스"},
    {"id": "ade-citron-grapefruit", "category": "ade", "name": "에이드", "price": 4700, "badge": "탄산"},
    {"id": "fruit-juice", "category": "ade", "name": "딸기주스", "price": 4900, "badge": "생과일"},
    {"id": "mix-juice", "category": "ade", "name": "믹스주스", "price": 5400, "badge": "든든"},
    {"id": "chamomile", "category": "tea", "name": "캐모마일", "price": 3200, "badge": "허브"},
    {"id": "earl-grey", "category": "tea", "name": "얼그레이", "price": 3200, "badge": "홍차"},
    {"id": "iced-tea", "category": "tea", "name": "아이스티", "price": 3200, "badge": "ICE"},
    {"id": "peach-iced-tea", "category": "tea", "name": "아샷추", "price": 3700, "badge": "샷추가"},
    {"id": "peach-mango-iced-tea", "category": "tea", "name": "아망추", "price": 4200, "badge": "망고"},
    {"id": "black-herbal-tea", "category": "tea", "name": "쌍화차", "price": 4500, "badge": "따뜻"},
    {"id": "citron-tea", "category": "tea", "name": "유자차", "price": 4500, "badge": "상큼"},
    {"id": "lemon-ginger-tea", "category": "tea", "name": "레몬차", "price": 4500, "badge": "생강"},
    {"id": "bokbunja-vin-chaud", "category": "tea", "name": "복분자뱅쇼", "price": 4900, "badge": "스페셜"},
    {"id": "royal-milk-tea", "category": "tea", "name": "로열밀크티", "price": 4900, "badge": "밀크티"},
]


class LocalOrderItem(BaseModel):
    menu_id: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1, le=20)


class LocalOrderRequest(BaseModel):
    items: list[LocalOrderItem] = Field(min_length=1)
    customer_name: str = Field(default="자리 미선택", max_length=30)
    note: str = Field(default="", max_length=120)


def get_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_admin_token():
    return get_config().get("admin_token", "")


def format_won(value: int) -> str:
    return f"{value:,}원"


def today_string() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_menu_item(menu_id: str) -> dict[str, Any]:
    for item in MENU:
        if item["id"] == menu_id:
            return item
    raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다")


def daily_order_path(date_text: str) -> Path:
    return ORDER_DATA_DIR / f"{date_text}.json"


def read_daily_orders(date_text: str) -> list[dict[str, Any]]:
    path = daily_order_path(date_text)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def write_daily_orders(date_text: str, orders: list[dict[str, Any]]) -> Path:
    ORDER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = daily_order_path(date_text)
    path.write_text(json.dumps(orders, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def append_daily_order(record: dict[str, Any]) -> Path:
    orders = read_daily_orders(record["date"])
    orders.append(record)
    return write_daily_orders(record["date"], orders)


def build_daily_report(date_text: str) -> dict[str, Any]:
    orders = read_daily_orders(date_text)
    item_stats: dict[str, dict[str, Any]] = {}
    revenue = 0
    item_count = 0
    for order in orders:
        revenue += order["total"]
        item_count += order["item_count"]
        for item in order["items"]:
            stat = item_stats.setdefault(item["name"], {"name": item["name"], "quantity": 0, "sales": 0})
            stat["quantity"] += item["quantity"]
            stat["sales"] += item["line_total"]
    top_items = sorted(item_stats.values(), key=lambda v: (v["quantity"], v["sales"]), reverse=True)
    return {
        "date": date_text,
        "order_count": len(orders),
        "item_count": item_count,
        "revenue": revenue,
        "revenue_label": format_won(revenue),
        "top_items": top_items[:10],
        "orders": orders,
        "json_path": str(daily_order_path(date_text)),
    }


def telegram_config() -> tuple[str, str]:
    cfg = get_config()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or cfg.get("telegram_bot_token", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip() or cfg.get("telegram_chat_id", "")
    if not token or not chat_id:
        raise HTTPException(status_code=503, detail="텔레그램 설정이 필요합니다")
    return token, chat_id


def send_telegram_message(text: str) -> None:
    token, chat_id = telegram_config()
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = UrlRequest(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            if response.status >= 400:
                raise HTTPException(status_code=502, detail="텔레그램 발송 실패")
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"텔레그램 오류: HTTP {exc.code}") from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail=f"텔레그램 연결 오류: {exc.reason}") from exc


def send_telegram_document(path: Path, caption: str) -> None:
    token, chat_id = telegram_config()
    boundary = f"----cafe-os-{uuid.uuid4().hex}"
    body = b"".join(
        [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n".encode("utf-8"),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode("utf-8"),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{path.name}\"\r\nContent-Type: application/json\r\n\r\n".encode("utf-8"),
            path.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    request = UrlRequest(
        f"https://api.telegram.org/bot{token}/sendDocument",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status >= 400:
                raise HTTPException(status_code=502, detail="텔레그램 파일 발송 실패")
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"텔레그램 오류: HTTP {exc.code}") from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail=f"텔레그램 연결 오류: {exc.reason}") from exc


app = FastAPI(title="cafe-os")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "app", "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))
init_db()


def require_admin(token: str):
    """관리 경로 토큰 검증. 틀리면 403."""
    if token != get_admin_token() or not token:
        raise HTTPException(status_code=403, detail="관리자 토큰이 필요합니다")


@app.get("/", response_class=HTMLResponse)
def order_page(request: Request):
    return templates.TemplateResponse(
        request,
        "order.html",
        {"menu": MENU, "categories": CATEGORIES, "format_won": format_won},
    )


@app.get("/qr")
def qr_image():
    if os.path.exists(QR_PATH):
        return FileResponse(QR_PATH, media_type="image/png")
    raise HTTPException(404, "QR 미생성")


@app.get("/display", response_class=HTMLResponse)
def display(request: Request):
    return templates.TemplateResponse(request, "display.html")


@app.get("/kitchen", response_class=HTMLResponse)
def kitchen(request: Request, token: str = Query("")):
    require_admin(token)
    return templates.TemplateResponse(request, "kitchen.html", {"token": token})


@app.get("/api/orders")
def api_orders():
    return JSONResponse(get_today_board())


@app.post("/api/orders")
def api_create(payload: dict):
    no = save_order(
        table_no=payload.get("table_no", ""),
        items=payload.get("items", []),
    )
    return {"ok": True, "order_no": no}


@app.post("/api/v1/orders")
def api_local_order(order: LocalOrderRequest, request: Request):
    now = datetime.now()
    date_text = now.strftime("%Y-%m-%d")
    ordered_time = now.strftime("%H:%M")
    total = 0
    item_count = 0
    saved_items = []
    db_items = []

    for order_item in order.items:
        menu_item = get_menu_item(order_item.menu_id)
        line_total = menu_item["price"] * order_item.quantity
        total += line_total
        item_count += order_item.quantity
        saved_items.append(
            {
                "menu_id": menu_item["id"],
                "category": menu_item["category"],
                "name": menu_item["name"],
                "quantity": order_item.quantity,
                "unit_price": menu_item["price"],
                "line_total": line_total,
            }
        )
        db_items.append(
            {
                "name": menu_item["name"],
                "qty": order_item.quantity,
                "unit_price": menu_item["price"],
                "options": order.note or "",
            }
        )

    order_no = save_order(table_no=order.customer_name or "자리 미선택", items=db_items)
    record = {
        "order_id": uuid.uuid4().hex[:12],
        "order_no": order_no,
        "date": date_text,
        "ordered_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "seat": order.customer_name or "자리 미선택",
        "options": order.note or "기본",
        "items": saved_items,
        "item_count": item_count,
        "total": total,
        "total_label": format_won(total),
        "client_host": request.client.host if request.client else "unknown",
    }
    json_path = append_daily_order(record)

    menu_line = ", ".join(f"{item['name']}x{item['quantity']}" for item in saved_items)
    message = "\n".join(
        [
            f"☕ 주문 #{order_no}",
            f"{ordered_time} | {record['seat']}",
            menu_line,
            f"합계 {record['total_label']}",
            f"옵션 {record['options']}",
        ]
    )
    try:
        send_telegram_message(message)
    except HTTPException as exc:
        # 텔레그램 미설정 카페도 번호판/주방/분석은 계속 동작해야 한다.
        if exc.status_code != 503:
            raise

    return {
        "status": "sent",
        "order_no": order_no,
        "item_count": item_count,
        "total": total,
        "total_label": format_won(total),
        "json_path": str(json_path),
    }


@app.get("/api/v1/reports/daily")
def daily_report(date: str | None = None):
    return build_daily_report(date or today_string())


@app.post("/api/v1/reports/daily/send")
def send_daily_report(date: str | None = None):
    date_text = date or today_string()
    report = build_daily_report(date_text)
    path = daily_order_path(date_text)
    if not path.exists():
        write_daily_orders(date_text, [])
    caption = f"일일 주문 통계 {date_text}\n주문 {report['order_count']}건 / 메뉴 {report['item_count']}개\n매출 {report['revenue_label']}"
    send_telegram_document(path, caption)
    return {"status": "sent", "date": date_text, "json_path": str(path)}


@app.post("/api/orders/{order_no}/done")
def api_done(order_no: int, token: str = Query("")):
    require_admin(token)
    set_status(order_no, "done")
    return {"ok": True, "order_no": order_no, "status": "done"}


@app.post("/api/orders/{order_no}/pick")
def api_pick(order_no: int, token: str = Query("")):
    require_admin(token)
    set_status(order_no, "picked")
    return {"ok": True, "order_no": order_no, "status": "picked"}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, token: str = Query("")):
    require_admin(token)
    return templates.TemplateResponse(request, "dashboard.html", {"token": token})


@app.get("/api/analytics")
def api_analytics(token: str = Query("")):
    require_admin(token)
    return JSONResponse({
        "summary": Q.today_summary(),
        "hourly": Q.today_hourly_menu(),
        "weekday": Q.by_weekday(),
        "weather": Q.by_weather(),
        "monthly": Q.sales_monthly(),
        "hour_avg": Q.by_hour_avg(),
    })
