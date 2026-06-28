-- cafe-os 데이터베이스 스키마 v1
-- 설계 원칙: 메뉴를 행으로 분리(order_items), 분석 가속용 비정규화 컬럼,
--            날씨는 주문 시점에 저장(소급 불가)

-- ── 메뉴 마스터 ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS menus (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    category    TEXT,                       -- 커피/논커피/디저트 등
    base_price  INTEGER NOT NULL DEFAULT 0,
    active      INTEGER NOT NULL DEFAULT 1, -- 1=판매중 0=단종
    created_at  TEXT DEFAULT (datetime('now','localtime'))
);

-- ── 주문 헤더 ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no     INTEGER NOT NULL,          -- 그날 순번 (자정 리셋)
    table_no     TEXT,
    status       TEXT NOT NULL DEFAULT 'waiting',  -- waiting|done|picked|canceled
    total_amount INTEGER NOT NULL DEFAULT 0,

    ordered_at   TEXT NOT NULL,             -- 'YYYY-MM-DD HH:MM:SS' 정밀
    done_at      TEXT,                      -- 제조완료 시각
    picked_at    TEXT,                      -- 수령 시각

    -- 분석 가속용 비정규화 (ordered_at 에서 파생, 저장 시 채움)
    date_ymd     TEXT NOT NULL,             -- '2026-06-28'
    hour         INTEGER NOT NULL,          -- 0~23
    weekday      INTEGER NOT NULL,          -- 0=월 ... 6=일

    -- 주문 시점 날씨 (나중에 소급 불가 → 지금 저장)
    weather_cond TEXT,                      -- Clear/Rain/Clouds ...
    temp         REAL                       -- 섭씨
);

CREATE INDEX IF NOT EXISTS idx_orders_date    ON orders(date_ymd);
CREATE INDEX IF NOT EXISTS idx_orders_hour    ON orders(hour);
CREATE INDEX IF NOT EXISTS idx_orders_weekday ON orders(weekday);
CREATE INDEX IF NOT EXISTS idx_orders_status  ON orders(status);

-- ── 주문 상세 (메뉴별 1행) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS order_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_name   TEXT NOT NULL,              -- 단종돼도 기록 보존 위해 이름 저장
    qty         INTEGER NOT NULL DEFAULT 1,
    unit_price  INTEGER NOT NULL DEFAULT 0,
    line_amount INTEGER NOT NULL DEFAULT 0, -- qty * unit_price
    options     TEXT,                       -- '얼음 적게, 샷 추가'

    -- 분석 가속용 (헤더에서 복사 → 조인 없이 메뉴 통계 가능)
    date_ymd    TEXT NOT NULL,
    hour        INTEGER NOT NULL,
    weekday     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_menu ON order_items(menu_name);
CREATE INDEX IF NOT EXISTS idx_items_date ON order_items(date_ymd);
CREATE INDEX IF NOT EXISTS idx_items_hour ON order_items(hour);

-- ── 날씨 캐시 (외부 API 호출 절약) ───────────────────────────
CREATE TABLE IF NOT EXISTS weather_cache (
    date_ymd  TEXT NOT NULL,
    hour      INTEGER NOT NULL,
    cond      TEXT,
    temp      REAL,
    fetched_at TEXT DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (date_ymd, hour)
);

-- ── 익명 쿠폰/스탬프 (개인정보 미수집) ───────────────────────
-- 핵심: code 는 무작위 문자열. 누구 것인지 카페는 모른다.
-- 휴대폰번호·이름 등 개인식별정보를 일절 저장하지 않는다.
CREATE TABLE IF NOT EXISTS coupons (
    code       TEXT PRIMARY KEY,           -- 'ABCD-1234' 무작위 발급
    stamps     INTEGER NOT NULL DEFAULT 0, -- 적립 스탬프 수
    rewards    INTEGER NOT NULL DEFAULT 0, -- 사용한 무료음료 수
    created_at TEXT NOT NULL,
    last_used  TEXT                        -- 마지막 적립 시각(재방문 판단용)
    -- ⚠ 여기에 phone, name 등 개인정보 컬럼을 절대 추가하지 말 것
);

-- 쿠폰-주문 연결 (어떤 주문에서 적립됐는지. 개인정보 아님)
CREATE TABLE IF NOT EXISTS coupon_logs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    code      TEXT NOT NULL REFERENCES coupons(code),
    order_id  INTEGER REFERENCES orders(id),
    delta     INTEGER NOT NULL,            -- +1 적립 / -10 보상사용
    at        TEXT NOT NULL
);

-- ── 스키마 버전 (향후 마이그레이션 관리) ─────────────────────
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('version', '2');
