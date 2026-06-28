# cafe-os

소규모 카페를 위한 오픈 주문·분석 시스템. POS 없이 노트북 1대로 운영.

QR 주문(기존 FastAPI) → 주문 표시(손님/주방) → 매출·메뉴·날씨 분석 → 재료 준비 예측

## 왜 만드나
프랜차이즈가 아닌 소규모 카페는 비싼 POS·분석 솔루션을 쓰기 어렵다.
노트북 + 모니터만으로 주문 표시부터 1년 데이터 기반 준비 예측까지 한다.

## 구조 (모노레포)
```
cafe-os/
├─ app/         주문 표시 (FastAPI 라우터 + HTML 화면)
│   ├─ display_routes.py   /display(손님), /kitchen(주방), /api
│   └─ templates/
├─ analytics/   분석 도구 (pandas + 차트, 추후)
├─ db/          데이터 계층 ★핵심
│   ├─ schema.sql   테이블 정의
│   ├─ store.py     저장/조회 (분석 대비 비정규화 구조)
│   └─ cafe.db      (자동 생성)
├─ docs/        사장님용 설치 가이드
└─ README.md
```

## 데이터 설계 핵심
- **메뉴를 행으로 분리** (`order_items`): 시간대별 메뉴 통계의 전제
- **비정규화 컬럼** (`date_ymd`,`hour`,`weekday`): 인덱스 + 단순 GROUP BY로 고속 집계
  - 검증: 1.5만 주문에서 분석 쿼리 전부 20ms 이하
- **날씨를 주문 시점에 저장**: 과거 날씨는 소급 불가하므로 그때그때 기록
- **메뉴명을 order_items에 텍스트로 보존**: 메뉴 단종돼도 과거 기록 유지

## 로드맵
- [x] **1단계** 스키마 설계 + 저장 계층 (현재)
- [ ] **2단계** 주문 표시 시스템 (손님 번호판 / 주방 관리창)
- [ ] **3단계** 분석 대시보드
  - 당일 시간대별 메뉴 통계
  - 매출 (일/주/월)
  - 영향인자 분석 (날씨·요일·월)
- [ ] **4단계** 재료 준비 예측 (1년 데이터 기반)
- [ ] **5단계** 비기술자용 원클릭 설치 (.bat/.sh → 추후 exe/docker)

## 라이선스
현재 All Rights Reserved (추후 유료화 모델 확정 후 BSL 등 적용 예정).
무단 상업적 재배포 불가.

## 연동 (기존 FastAPI 앱)
```python
from db.store import init_db, save_order
init_db()  # 앱 시작 시 1회

# 주문 접수 지점에서:
order_no = save_order(
    table_no="2",
    items=[
        {"name":"카페모카","qty":1,"unit_price":5200,"options":"샷 추가"},
        {"name":"바닐라라떼","qty":1,"unit_price":5200},
    ],
)
```
