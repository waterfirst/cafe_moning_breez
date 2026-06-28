"""
cafe-os 데이터 계층.
주문 저장 시 분석용 비정규화 컬럼과 날씨를 함께 기록한다.

기존 FastAPI 주문 처리부에서:
    from db.store import save_order
    order_no = save_order(
        table_no="2",
        items=[
            {"name": "카페모카", "qty": 1, "unit_price": 4800, "options": "샷 추가"},
            {"name": "바닐라라떼", "qty": 1, "unit_price": 5200, "options": ""},
        ],
    )
"""
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db", "cafe.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "db", "schema.sql")


def get_conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    """앱 시작 시 1회 호출. 스키마 생성(멱등)."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = get_conn()
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        con.executescript(f.read())
    con.commit()
    con.close()


def _next_order_no(con, date_ymd):
    row = con.execute(
        "SELECT MAX(order_no) AS m FROM orders WHERE date_ymd=?", (date_ymd,)
    ).fetchone()
    return (row["m"] or 0) + 1


def save_order(table_no="", items=None, weather=None):
    """
    주문 저장 + 번호 발번. 발번된 order_no 반환.

    items: [{"name","qty","unit_price","options"(선택)}, ...]
    weather: {"cond": "Rain", "temp": 18.5} (선택, 없으면 get_weather로 채움)
    """
    items = items or []
    now = datetime.now()
    date_ymd = now.strftime("%Y-%m-%d")
    hour = now.hour
    weekday = now.weekday()  # 0=월
    ordered_at = now.strftime("%Y-%m-%d %H:%M:%S")

    if weather is None:
        weather = get_weather(date_ymd, hour) or {}

    total = sum(int(it.get("qty", 1)) * int(it.get("unit_price", 0)) for it in items)

    con = get_conn()
    try:
        no = _next_order_no(con, date_ymd)
        cur = con.execute(
            """INSERT INTO orders
               (order_no, table_no, status, total_amount, ordered_at,
                date_ymd, hour, weekday, weather_cond, temp)
               VALUES (?,?, 'waiting', ?,?, ?,?,?, ?,?)""",
            (no, table_no, total, ordered_at, date_ymd, hour, weekday,
             weather.get("cond"), weather.get("temp")),
        )
        order_id = cur.lastrowid
        for it in items:
            qty = int(it.get("qty", 1))
            unit = int(it.get("unit_price", 0))
            con.execute(
                """INSERT INTO order_items
                   (order_id, menu_name, qty, unit_price, line_amount, options,
                    date_ymd, hour, weekday)
                   VALUES (?,?,?,?,?,?, ?,?,?)""",
                (order_id, it.get("name", "?"), qty, unit, qty * unit,
                 it.get("options", ""), date_ymd, hour, weekday),
            )
        con.commit()
        return no
    finally:
        con.close()


def set_status(order_no, status, date_ymd=None):
    """status: done|picked|canceled"""
    date_ymd = date_ymd or datetime.now().strftime("%Y-%m-%d")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    col = {"done": "done_at", "picked": "picked_at"}.get(status)
    con = get_conn()
    try:
        if col:
            con.execute(
                f"UPDATE orders SET status=?, {col}=? WHERE order_no=? AND date_ymd=?",
                (status, ts, int(order_no), date_ymd),
            )
        else:
            con.execute(
                "UPDATE orders SET status=? WHERE order_no=? AND date_ymd=?",
                (status, int(order_no), date_ymd),
            )
        con.commit()
    finally:
        con.close()


def get_today_board():
    """오늘 주문 + 메뉴 요약 (화면용). 최신순."""
    date_ymd = datetime.now().strftime("%Y-%m-%d")
    con = get_conn()
    try:
        orders = con.execute(
            """SELECT id, order_no, table_no, status, total_amount,
                      ordered_at, done_at, picked_at
               FROM orders WHERE date_ymd=? ORDER BY id DESC""",
            (date_ymd,),
        ).fetchall()
        result = []
        for o in orders:
            its = con.execute(
                "SELECT menu_name, qty, options FROM order_items WHERE order_id=?",
                (o["id"],),
            ).fetchall()
            menu_str = ", ".join(f"{i['menu_name']}x{i['qty']}" for i in its)
            d = dict(o)
            d["menu"] = menu_str
            d["total"] = f"{o['total_amount']:,}원" if o["total_amount"] else ""
            result.append(d)
        return result
    finally:
        con.close()


def get_weather(date_ymd, hour):
    """날씨 캐시 조회. 없으면 None (외부 API 연동은 weather.py에서)."""
    con = get_conn()
    try:
        row = con.execute(
            "SELECT cond, temp FROM weather_cache WHERE date_ymd=? AND hour=?",
            (date_ymd, hour),
        ).fetchone()
        return {"cond": row["cond"], "temp": row["temp"]} if row else None
    finally:
        con.close()
