# cafe-os

소규모 카페를 위한 QR 주문, 주문 모니터링, 주방 처리, 매출 분석 프로그램입니다.
카페 주인이 노트북에서 실행하고, 손님은 테이블 QR 코드로 주문합니다.

## 운영 흐름

1. 테이블마다 주문 QR 코드를 붙입니다.
2. 손님은 QR 코드로 주문 화면에 접속합니다.
3. 주문이 들어오면 주문 모니터링 창에 주문번호와 메뉴가 표시됩니다.
4. 주방은 태블릿에서 주문을 확인하고 완료 버튼을 누릅니다.
5. 영업 종료 후 매출 분석 프로그램에서 일별 매출과 메뉴 통계를 확인합니다.

## 처음 설치

Windows PowerShell을 열고 아래 명령을 실행합니다.

```powershell
cd D:\nakcho\python
git clone -b claude/cafe-os-project-overview-08rh6v https://github.com/waterfirst/cafe_moning_breez.git cafe-os
cd cafe-os
pip install -r requirements.txt
```

이미 `cafe-os` 폴더가 있으면 새로 clone하지 말고 업데이트만 합니다.

```powershell
cd D:\nakcho\python\cafe-os
git pull origin claude/cafe-os-project-overview-08rh6v
pip install -r requirements.txt
```

## 실행 방법

기존 주문앱이 `8000` 포트를 사용 중이면 `cafe-os`는 `8002` 포트로 실행합니다.

```powershell
cd D:\nakcho\python\cafe-os
$env:CAFE_PORT=8002
python run.py
```

실행하면 브라우저 창이 열리고, PowerShell 실행 창에 관리자 토큰과 접속 주소가 출력됩니다.
관리자 토큰은 GitHub나 문서에 적지 말고 실행 창에 나온 값을 그대로 사용합니다.

## 실행 후 사용하는 4개 화면

아래 IP는 예시입니다. 실제 IP는 `python run.py` 실행 창에 출력되는 주소를 사용합니다.

| 용도 | 주소 |
| --- | --- |
| 주문자 주문 화면 | `http://192.168.0.40:8002/` |
| 주문 모니터링 창 | `http://192.168.0.40:8002/display` |
| 주방/관리자 태블릿 | `http://192.168.0.40:8002/kitchen?token=실행창에_출력된_관리자토큰` |
| 매출 분석 프로그램 | `http://127.0.0.1:8002/dashboard?token=실행창에_출력된_관리자토큰` |

권장 배치:

- 노트북 또는 큰 모니터: 주문 모니터링 창
- 주방 태블릿: 주방/관리자 태블릿
- 카페 주인 노트북: 매출 분석 프로그램
- 테이블 QR: 주문자 주문 화면

## QR 코드 사용

`python run.py`를 실행하면 `qr_order.png`가 자동 생성됩니다.
이 QR 이미지를 출력해서 테이블마다 붙이면 손님이 바로 주문 화면으로 들어올 수 있습니다.

노트북 IP가 바뀌면 QR 주소도 바뀔 수 있습니다. 와이파이를 바꾸거나 공유기를 바꾼 뒤에는 `python run.py`를 다시 실행하고 새 QR을 확인합니다.

## 주문 테스트

주문이 번호판에 뜨는지 확인하려면 새 PowerShell 창에서 아래 명령을 실행합니다.

```powershell
$body = '{"table_no":"3","items":[{"name":"아메리카노","qty":1,"unit_price":4000}]}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
Invoke-RestMethod -Uri "http://192.168.0.40:8002/api/orders" -Method Post -ContentType "application/json; charset=utf-8" -Body $bytes
```

정상이라면 주문 모니터링 창에 주문번호가 표시됩니다.
주방 태블릿에서 `제조완료`, `픽업완료`를 누르면 상태가 바뀝니다.

## 매출 분석

매출 분석 프로그램은 관리자 토큰이 필요합니다.

```text
http://127.0.0.1:8002/dashboard?token=실행창에_출력된_관리자토큰
```

확인 가능한 내용:

- 당일 주문 수
- 당일 매출
- 메뉴별 판매량
- 시간대별 주문 흐름
- 요일/월별 매출 분석
- 날씨와 매출 관계 분석

## 데이터 저장

주문 데이터는 로컬 노트북에 저장됩니다.

```text
db/cafe.db                 SQLite 원본 DB
data/orders/YYYY-MM-DD.json 일별 주문 JSON
```

GitHub에는 프로그램 코드와 문서만 올립니다.
토큰, 원본 주문 DB, 일별 주문 JSON은 개인정보와 영업 데이터가 될 수 있으므로 공개 저장소에 올리지 않습니다.

GitHub에 올려도 되는 데이터:

- 개인정보가 제거된 일별 매출 요약
- 메뉴별 판매 수량 요약
- 시간대별 주문 수 요약

## 주요 폴더

```text
cafe-os/
├─ app/              FastAPI 화면/API
├─ app/templates/    주문, 모니터링, 주방, 분석 HTML
├─ app/static/       CSS/JS
├─ db/               SQLite 저장 로직
├─ analytics/        매출 분석 쿼리
├─ docs/             운영 문서
├─ run.py            실행 프로그램
└─ requirements.txt  설치 패키지
```

## 문제 해결

`/display`가 404로 나오는 경우:

- `8000` 포트의 기존 주문앱을 보고 있을 가능성이 큽니다.
- `http://192.168.0.40:8002/display`처럼 `8002` 주소로 접속합니다.

주방/분석 화면이 403으로 나오는 경우:

- 관리자 토큰이 없거나 틀렸습니다.
- `python run.py` 실행 창에 나온 토큰을 다시 붙입니다.

한글 주문 테스트가 깨지는 경우:

- PowerShell에서 UTF-8 bytes로 보내야 합니다.
- 위의 주문 테스트 명령을 그대로 사용합니다.

포트가 이미 사용 중인 경우:

```powershell
$env:CAFE_PORT=8003
python run.py
```

## 보안 주의

- 공유기 포트포워딩은 켜지 않습니다.
- 같은 카페 와이파이 안에서만 사용합니다.
- 관리자 토큰과 텔레그램 토큰은 GitHub에 올리지 않습니다.
- `.cafe_config.json`, `.env`, `db/cafe.db`, `data/orders/`, `qr_order.png`는 커밋하지 않습니다.
