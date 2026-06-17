---
name: toss-execution
description: 토스 증권 Open API 연동 및 주문 실행 빌더. TossRESTClient(인증/시세/보유/캔들/주문)와 order_manager를 다루며, 토스 API의 까다로운 제약(단일토큰·IP 허용목록·재시도·DRY_RUN)을 안전하게 처리한다.
user_invocable: true
---

# /toss-execution - 토스 API · 주문 실행 빌더

## 역할
`execution/toss_rest.py`(TossRESTClient)와 `execution/order_manager.py`를 생성/수정한다.
토스 Open API 호출, 주문 실행, 안전장치를 담당한다.

## 토스 Open API 핵심 (https://openapi.tossinvest.com)
- **인증**: OAuth2 client_credentials, `POST /oauth2/token` (**form-urlencoded**, `client_id`/`client_secret`) → `access_token`(~24h)
- **헤더**: 전부 `Authorization: Bearer`. 주문/보유/주문조회는 추가로 `X-Tossinvest-Account: {accountSeq}` (accountSeq는 `/api/v1/accounts`로 자동 조회)
- **주문**: `POST /api/v1/orders` — KR/US 단일 엔드포인트. `symbol`(KR 6자리/US 티커), `side`(BUY/SELL), `orderType`(LIMIT/MARKET), `quantity`/`price`(문자열), `clientOrderId`(멱등키)
- **조회**: `/api/v1/holdings`(보유, `X-Tossinvest-Account` 필요), `/api/v1/prices?symbols=`(현재가, 콤마구분), `/api/v1/candles?symbol=&interval=1d&count=`(차트 OHLC)
- **모든 숫자 필드는 문자열**

## 반드시 지킬 제약 (실전에서 겪은 함정)
1. **단일 활성 토큰**: 토스는 client당 활성 토큰이 1개. 외부에서 새 토큰을 발급하면 기존 토큰이 무효화된다 → **401 발생 시 토큰 버리고 재발급 후 재시도** (GET 메서드의 retry 루프에서 `if attempt>0: self.token=None`).
2. **IP 허용목록**: 키는 IP allowlist 방식. 403 `access_denied: IP address not allowed`는 코드가 아니라 IP 문제(VPN/IP 변경). 운영 호스트 공인 IP를 토스 콘솔에 등록해야 함.
3. **간헐적 빈 응답**: 토스가 가끔 빈 body를 줘 JSON 파싱 실패 → **GET 호출 1회 재시도**(`raise_for_status` + `time.sleep(0.5)`).
4. **live 키 = 실거래**: 주문 경로는 `DRY_RUN` 게이트 뒤에 둔다.

## TossRESTClient 패턴
```python
def _ensure_token(self):       # 만료 60초 전 갱신, form-urlencoded
def _headers(self, with_account=False):  # Bearer + 선택적 X-Tossinvest-Account
def _ensure_account_seq(self): # 설정 없으면 /api/v1/accounts 첫 계좌 자동
# GET 메서드는 2회 retry + 401시 토큰 재발급:
for attempt in range(2):
    if attempt > 0: self.token = None
    try: resp = requests.get(...); resp.raise_for_status(); return resp.json()
    except Exception as e: last_error=str(e); time.sleep(0.5)
```
공개 인터페이스(키움 호환): `order_kr_stock`, `order_us_stock`, `get_balance`, `get_current_price_kr`, `get_prices`, `get_candles`. KR/US 주문은 내부 `_create_order`로 위임(토스는 단일 엔드포인트).

## order_manager 안전 규칙
- `DRY_RUN`이면 주문 미실행(로그만)
- 일일 거래 한도(`MAX_DAILY_TRADES`), 수량>0 검증
- 전략 실행 시: **코어 수량 밑으로 매도 금지**, **지정가만**, 멱등키(`clientOrderId`)

## 절대 규칙
- 토큰/계좌 키 노출 금지(`settings` 경유)
- GET은 401-재발급 + 빈응답 재시도 적용 (`get_current_price_kr`/`get_prices`도 동일하게 견고화)
- 주문은 DRY_RUN·한도·코어보호·지정가 준수
- 변경 후 `/runner`로 실제 토스 호출(읽기 전용: token→accounts→prices)까지 검증
