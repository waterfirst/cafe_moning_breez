"""
analytics/queries.py — 분석 쿼리 모음
스키마의 비정규화 컬럼(date_ymd/hour/weekday)+인덱스 덕분에
전부 단순 GROUP BY로 고속 집계된다.

모든 함수는 dict/list 를 반환 → API/차트에서 바로 사용.
"""
import os
import sys
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from db.store import get_conn

WD_KR = ["월", "화", "수", "목", "금", "토", "일"]


def _today():
    return datetime.now().strftime("%Y-%m-%d")


# ── 1. 당일 시간대별 메뉴 통계 ───────────────────────────────
def today_hourly_menu(date_ymd=None):
    """
    오늘 시간대별로 어떤 메뉴가 몇 개 팔렸는지.
    반환: {"date","hours":[7..21],"menus":{메뉴명:[시간대별 수량]},"hour_total":[...]}
    """
    date_ymd = date_ymd or _today()
    con = get_conn()
    try:
        rows = con.execute(
            """SELECT hour, menu_name, SUM(qty) q
               FROM order_items WHERE date_ymd=?
               GROUP BY hour, menu_name ORDER BY hour""",
            (date_ymd,),
        ).fetchall()
        if not rows:
            return {"date": date_ymd, "hours": [], "menus": {}, "hour_total": []}

        hours = sorted({r["hour"] for r in rows})
        hidx = {h: i for i, h in enumerate(hours)}
        menus = {}
        for r in rows:
            menus.setdefault(r["menu_name"], [0] * len(hours))
            menus[r["menu_name"]][hidx[r["hour"]]] += r["q"]
        hour_total = [sum(menus[m][i] for m in menus) for i in range(len(hours))]
        return {"date": date_ymd, "hours": hours, "menus": menus, "hour_total": hour_total}
    finally:
        con.close()


def today_summary(date_ymd=None):
    """오늘 요약: 주문수, 매출, 객단가, 인기메뉴."""
    date_ymd = date_ymd or _today()
    con = get_conn()
    try:
        o = con.execute(
            "SELECT COUNT(*) cnt, COALESCE(SUM(total_amount),0) sales "
            "FROM orders WHERE date_ymd=?", (date_ymd,)
        ).fetchone()
        top = con.execute(
            """SELECT menu_name, SUM(qty) q FROM order_items WHERE date_ymd=?
               GROUP BY menu_name ORDER BY q DESC LIMIT 5""", (date_ymd,)
        ).fetchall()
        cnt, sales = o["cnt"], o["sales"]
        return {
            "date": date_ymd, "orders": cnt, "sales": sales,
            "avg_ticket": round(sales / cnt) if cnt else 0,
            "top_menus": [{"name": t["menu_name"], "qty": t["q"]} for t in top],
        }
    finally:
        con.close()


# ── 2. 매출 추이 (일/주/월) ──────────────────────────────────
def sales_daily(days=30):
    """최근 N일 일별 매출."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    con = get_conn()
    try:
        rows = con.execute(
            """SELECT date_ymd, COUNT(*) orders, COALESCE(SUM(total_amount),0) sales
               FROM orders WHERE date_ymd>=? GROUP BY date_ymd ORDER BY date_ymd""",
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def sales_monthly():
    """월별 매출."""
    con = get_conn()
    try:
        rows = con.execute(
            """SELECT substr(date_ymd,1,7) ym, COUNT(*) orders,
                      COALESCE(SUM(total_amount),0) sales
               FROM orders GROUP BY ym ORDER BY ym"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


# ── 3. 영향인자 분석 ─────────────────────────────────────────
def by_weekday():
    """요일별 평균 일매출/주문수."""
    con = get_conn()
    try:
        rows = con.execute(
            """SELECT weekday,
                      COUNT(DISTINCT date_ymd) days,
                      COUNT(*) orders,
                      COALESCE(SUM(total_amount),0) sales
               FROM orders GROUP BY weekday ORDER BY weekday"""
        ).fetchall()
        out = []
        for r in rows:
            days = r["days"] or 1
            out.append({
                "weekday": r["weekday"], "label": WD_KR[r["weekday"]],
                "avg_orders": round(r["orders"] / days, 1),
                "avg_sales": round(r["sales"] / days),
            })
        return out
    finally:
        con.close()


def by_weather():
    """날씨별 일평균 주문수/매출."""
    con = get_conn()
    try:
        rows = con.execute(
            """SELECT weather_cond,
                      COUNT(DISTINCT date_ymd) days,
                      COUNT(*) orders,
                      COALESCE(SUM(total_amount),0) sales
               FROM orders WHERE weather_cond IS NOT NULL
               GROUP BY weather_cond ORDER BY orders DESC"""
        ).fetchall()
        out = []
        for r in rows:
            days = r["days"] or 1
            out.append({
                "weather": r["weather_cond"],
                "avg_orders": round(r["orders"] / days, 1),
                "avg_sales": round(r["sales"] / days),
            })
        return out
    finally:
        con.close()


def by_hour_avg():
    """전체 기간 시간대별 평균 주문수 (피크타임 파악)."""
    con = get_conn()
    try:
        rows = con.execute(
            """SELECT hour, COUNT(*) orders, COUNT(DISTINCT date_ymd) days
               FROM orders GROUP BY hour ORDER BY hour"""
        ).fetchall()
        return [{"hour": r["hour"],
                 "avg_orders": round(r["orders"] / (r["days"] or 1), 1)}
                for r in rows]
    finally:
        con.close()
