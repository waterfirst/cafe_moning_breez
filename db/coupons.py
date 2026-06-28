"""
db/coupons.py — 익명 쿠폰/스탬프

설계 원칙 (개인정보보호법 대응):
- 휴대폰번호·이름·이메일 등 개인식별정보를 절대 받지 않는다.
- 쿠폰코드는 무작위 문자열. 카페는 코드 소유자가 누구인지 알 수 없다.
- 따라서 이 데이터는 '개인정보'에 해당하지 않아 동의·파기 의무가 사실상 없다.
- 손님은 코드를 스크린샷 등으로 직접 보관(분실 시 복구 불가 — 이게 익명의 대가).
"""
import os
import secrets
import string
from datetime import datetime

import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from db.store import get_conn

REWARD_AT = 10   # 스탬프 10개 = 무료음료 1잔 (카페가 조정)

# 사람이 읽기 쉬운 문자만 (0/O, 1/I 등 혼동 제거)
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _gen_code():
    part = lambda n: "".join(secrets.choice(_ALPHABET) for _ in range(n))
    return f"{part(4)}-{part(4)}"


def issue_coupon():
    """새 익명 쿠폰 발급. 코드 반환."""
    con = get_conn()
    try:
        for _ in range(5):  # 충돌 시 재시도
            code = _gen_code()
            try:
                con.execute(
                    "INSERT INTO coupons(code, stamps, rewards, created_at) VALUES(?,0,0,?)",
                    (code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )
                con.commit()
                return code
            except Exception:
                continue
        raise RuntimeError("쿠폰 코드 생성 실패")
    finally:
        con.close()


def add_stamp(code, order_id=None):
    """
    쿠폰에 스탬프 +1. 보상 도달 시 자동 차감하고 무료음료 안내.
    반환: {"ok","stamps","reward_ready","reward_used","message"}
    존재하지 않는 코드면 ok=False.
    """
    code = (code or "").strip().upper()
    con = get_conn()
    try:
        row = con.execute("SELECT stamps, rewards FROM coupons WHERE code=?", (code,)).fetchone()
        if not row:
            return {"ok": False, "message": "존재하지 않는 쿠폰코드입니다."}

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stamps = row["stamps"] + 1
        reward_used = False

        if stamps >= REWARD_AT:
            stamps -= REWARD_AT
            reward_used = True
            con.execute(
                "UPDATE coupons SET stamps=?, rewards=rewards+1, last_used=? WHERE code=?",
                (stamps, now, code),
            )
            con.execute(
                "INSERT INTO coupon_logs(code, order_id, delta, at) VALUES(?,?,?,?)",
                (code, order_id, -REWARD_AT, now),
            )
        else:
            con.execute(
                "UPDATE coupons SET stamps=?, last_used=? WHERE code=?",
                (stamps, now, code),
            )

        con.execute(
            "INSERT INTO coupon_logs(code, order_id, delta, at) VALUES(?,?,?,?)",
            (code, order_id, 1, now),
        )
        con.commit()

        if reward_used:
            msg = f"🎉 무료음료 1잔! (스탬프 {REWARD_AT}개 달성). 남은 스탬프 {stamps}개"
        else:
            msg = f"스탬프 적립! 현재 {stamps}/{REWARD_AT}개"
        return {"ok": True, "stamps": stamps, "reward_ready": False,
                "reward_used": reward_used, "message": msg}
    finally:
        con.close()


def get_coupon(code):
    """쿠폰 현황 조회 (스탬프 수만. 개인정보 없음)."""
    code = (code or "").strip().upper()
    con = get_conn()
    try:
        row = con.execute(
            "SELECT code, stamps, rewards, created_at, last_used FROM coupons WHERE code=?",
            (code,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def stats():
    """
    재방문 분석 (익명 집계만).
    개인을 식별하지 않고 '재방문 쿠폰 비율' 같은 통계만 낸다.
    """
    con = get_conn()
    try:
        total = con.execute("SELECT COUNT(*) c FROM coupons").fetchone()["c"]
        # 2회 이상 적립된 쿠폰 = 재방문으로 간주
        repeat = con.execute(
            "SELECT COUNT(*) c FROM (SELECT code FROM coupon_logs WHERE delta=1 "
            "GROUP BY code HAVING COUNT(*)>=2)"
        ).fetchone()["c"]
        rewards = con.execute("SELECT COALESCE(SUM(rewards),0) s FROM coupons").fetchone()["s"]
        return {
            "total_coupons": total,
            "repeat_visitors": repeat,
            "repeat_rate": round(repeat / total * 100, 1) if total else 0,
            "rewards_given": rewards,
        }
    finally:
        con.close()
