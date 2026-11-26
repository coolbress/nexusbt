# TDS 데이터 예시: NexusBT에 넣는 데이터는 이렇게 생겼다

이 문서는 한국어 번역본이다. 정본은 영어판 `tds-examples.md`다.

TDS(NexusBT 데이터 표준) v1.4 기준 그림 설명서. 모든 숫자는 **모양을 보여 주기 위한 예시 값**이다(실제 시세·재무가 아님). 칼럼의 정식 정의는 `tds-v1.4.ko.md`(정본 `tds-v1.4.md`) 해당 절.

종목 열쇠는 `instrument_id`(예 `KR:005930` 삼성전자, `US:AAPL` 애플). 시각 칼럼은 모두 UTC.

---

## 0. 한눈에

```
                ┌──────────────── 스냅숏 폴더 하나 = TDS 패키지 ────────────────┐
  (가) 재료     │ bars(일봉) · corporate_actions(기업행동)                         │
  엔진이 계산   │ calendar_sessions(거래일) · delistings(상장폐지)                 │──▶ Pipeline
                │ tradability_daily(정지·관리)                                     │
                │ fx_rates(환율)                                                   │
                └──────────────────────────────────────────────────────────────────┘
```

---

## 1. 폴더 모양 (스냅숏 = 패키지)

```
snapshots/2026-11-02_buildK/
├── tds.json                                   ← 목록 + 해시 (이것이 있어야 패키지)
├── instruments/part-00000.parquet
├── calendar_sessions/part-00000.parquet
├── bars/freq=1d/market=KR/year=2024/part-00000.parquet
├── bars/freq=1d/market=US/year=2024/part-00000.parquet
├── corporate_actions/part-00000.parquet
└── delistings/part-00000.parquet
```

엔진은 이 폴더 경로 하나만 받는다: `nx.open("snapshots/2026-11-02_buildK")`.

---

## 2. 재료 표 (가)

### 2-1. `bars` 일봉 — 종목 × 거래일, 원가격

| instrument_id | session_date | open | high | low | close | volume | value_traded | obs_status |
|---|---|---|---|---|---|---|---|---|
| KR:005930 | 2024-03-28 | 80,800 | 81,900 | 80,500 | 81,700 | 18,231,000 | 1.48e12 | traded |
| KR:005930 | 2024-03-29 | 81,900 | 82,600 | 81,300 | 82,400 | 15,904,000 | 1.30e12 | traded |
| KR:000660 | 2024-03-29 | 179,000 | 184,500 | 178,200 | 183,000 | 4,512,000 | 8.22e11 | traded |
| KR:123456 | 2024-03-29 | | | | | 0 | 0 | halted |
| US:AAPL | 2024-03-28 | 171.75 | 172.23 | 170.51 | 171.48 | 65,672,700 | 1.13e10 | traded |

- 가격은 **원가격**(조정 안 함). 분할·배당 조정은 엔진이 기업행동 표로 그때그때 계산한다(미래 조정이 과거에 새지 않게).
- 거래정지일은 행은 있고 가격은 빈칸(`halted`).

### 2-2. `corporate_actions` 기업행동 — 사건 한 줄

| event_id | instrument_id | kind | ex_date | record_date | cash_per_share | ratio_num | ratio_den | ts_announced |
|---|---|---|---|---|---|---|---|---|
| ca-0001 | KR:005930 | split | 2018-05-04 | 2018-05-03 | | 50 | 1 | 2018-01-31T07:30Z |
| ca-0002 | KR:005930 | cash_dividend | 2023-12-27 | 2023-12-28 | 361 | | | 2023-11-03T07:00Z |
| ca-0003 | US:AAPL | split | 2020-08-31 | 2020-08-24 | | 4 | 1 | 2020-07-30T20:30Z |
| ca-0004 | US:AAPL | cash_dividend | 2024-02-09 | 2024-02-12 | 0.24 | | | 2024-02-01T21:30Z |

- 분할은 **정수 비율**(50 : 1)로. 소수 비율만 있는 데이터는 사용자가 설정에서 허용해야 받는다(v3.4).
- 배당은 **원금액**(분할로 조정하지 않은 그때 금액).
- 공개 시각은 `ts_announced`(사건 공개)와 `ts_terms_available`(금액·비율 확정, 빈칸이면 `ts_announced`와 같음). 그 밖의 필수 칼럼(`ts_effective`, `pay_date_status`, `affects`, `factor_method`, `status`)은 표에서 줄였다(TDS 5.11).

### 2-4. 그 밖의 재료 (모양만)

| 표 | 한 줄 예 |
|---|---|
| `calendar_sessions` | calendar_id XKRX · session_date 2024-03-29 · ts_open 2024-03-29T00:00Z · ts_close 06:30Z · session_kind regular |
| `delistings` | KR:999990 · last_trading_date 2019-07-10 · exit_date 2019-07-19 · delist_type performance · exit_value_status observed · ret_observed −0.95 |
| `tradability_daily` | KR:123456 · 2024-03-29 · status_known true · halted_full_day true · admin_status administrative |
| `fx_rates` | base USD · quote KRW · rate_kind fixing · obs_date 2024-03-29 · rate 1,346.8 · ts_available 2024-03-29T06:30Z |

---

## 3. 거래 밖의 값

거래 밖의 값(재무, 주식 수, 업종 코드, 유니버스, 사건, 거시 계열)은 사용자의 것이고, 값 표 셋에 담긴다(`tds-v1.4.ko.md` 5.28, 엔진 명세서 5.3.5). 파일 하나는 시장 하나, 항목 하나의 행을 담는다. 폴더 이름이 둘을 말하므로(`market=`, `item=`) 행에는 `instrument_id`, `date`, `value`만 있다. 사용자는 `instrument_id`를 `symbol`로 만나고, 항목을 `nx.Item.<name>`으로 읽는다.

### 3-1. `values` — 종목·날짜별

`values/market=KR/item=per/part-00000.parquet`

| instrument_id | date | value |
|---|---|---|
| KR:005930 | 2024-03-14 | 12.4 |
| KR:005930 | 2024-05-16 | 13.1 |
| KR:000660 | 2024-03-14 | |

- `date`는 값이 발표된 날, 그 시장의 현지 날짜다. 거래일이 아니어도 된다(토요일 날짜의 값은 다음 거래일부터 쓴다).
- KR:000660의 빈 `value`는 그날부터 그 종목의 `per`를 끝낸다(이월이 멈춘다).

### 3-2. `market_values` — 시장 전체에 하나, 날짜별

`market_values/market=KR/item=base_rate/part-00000.parquet`

| date | value |
|---|---|
| 2024-01-11 | 3.50 |
| 2024-10-11 | 3.25 |

### 3-3. `symbol_values` — 종목별, 날짜 없음

`symbol_values/market=KR/item=sector/part-00000.parquet`

| instrument_id | value |
|---|---|
| KR:005930 | 1 |
| KR:000660 | 1 |
| KR:123456 | 2 |

- 코드도 숫자다(`nx.Item.sector.eq(1)`). `1`이 무엇인지는 사용자의 것이다.

### 3-4. 항목 선언 (선택)

`tds.json`에서 데이터셋의 `params.items`가 항목의 종류와 이월을 선언할 수 있다:

```json
"params": {"items": {"shares_out": {"kind": "share_count"},
                     "dps": {"kind": "per_share", "carry": "none"}}}
```

- `kind`: `per_share` 또는 `share_count` — 엔진이 뒤의 분할로 값을 다시 맞춘다.
- `carry`: `to_end`(기본), 세션 수 N, `none`, `next_listing`.
