# TDS 데이터 예시: NexusBT에 넣는 데이터는 이렇게 생겼다

이 문서는 한국어 번역본이다. 정본은 영어판 `tds-examples.md`다.

TDS(NexusBT 데이터 표준) v1.4 기준 그림 설명서. 모든 숫자는 **모양을 보여 주기 위한 예시 값**이다(실제 시세·재무가 아님). 칼럼의 정식 정의는 `tds-v1.4.ko.md`(정본 `tds-v1.4.md`) 해당 절.

종목 열쇠는 `instrument_id`(예 `KR:005930` 삼성전자, `US:AAPL` 애플). 시각 칼럼은 모두 UTC.

---

## 0. 한눈에: 두 가지 넣는 방법

```
                ┌───────────────────────── 스냅숏 폴더 하나 = TDS 패키지 ─────────────────────────┐
  (가) 재료     │ bars(일봉) · corporate_actions(기업행동) · fundamentals_state(시점 재무)           │
  엔진이 계산   │ calendar_sessions(거래일) · delistings(상장폐지) · tradability_daily(정지·관리) │──▶ Pipeline이
                │ classifications(업종) · share_counts(주식 수) · fx_rates(환율)                    │    팩터 패널을 만듦
                ├────────────────────────────────────────────────────────────────────────────────┤
  (나) 완성본   │ feature_panels(만든 쪽이 계산한 종목 × 월 팩터 패널) · label_panels(정답 수익)       │──▶ Panel.<칼럼>으로
  바로 사용     │                                                                                │    바로 사용
                ├────────────────────────────────────────────────────────────────────────────────┤
  (다) 이벤트·   │ events(공시·실적 발표) · series_observations(거시 지표, 발표 시각·수정 이력)          │──▶ Events · Macro
  거시          └────────────────────────────────────────────────────────────────────────────────┘    블록
```

(가)와 (나)는 같이 쓸 수 있다. 기준 생산자의 스냅숏은 둘 다 들어 있다. 사용자가 원하는 "종목 × 기간 × 칼럼" 패널은 **(나)를 그대로 쓰거나, (가)로 엔진이 같은 모양을 만들어 내는 것**이다(4장).

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
├── delistings/part-00000.parquet
├── fundamentals_state/edition=strict/market=KR/part-00000.parquet
├── feature_panels/name=factor_pit_monthly/edition=strict/year=2024/part-00000.parquet
├── label_panels/name=label_monthly/year=2024/part-00000.parquet
├── events/event_type=earnings.prelim/part-00000.parquet   (v3.4에서 추가; 파티션 = 사건 종류)
└── series_observations/part-00000.parquet
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

### 2-3. `fundamentals_state` 시점 재무 — "이 값을 언제부터 알 수 있었나" 구간

| instrument_id | item | ts_known_from | ts_known_to | period_end | period_kind | value | strict_eligible |
|---|---|---|---|---|---|---|---|
| KR:005930 | net_income_ttm | 2023-11-14T07:00Z | 2024-01-31T07:00Z | 2023-09-30 | TTM | 9.0e12 | true |
| KR:005930 | net_income_ttm | 2024-01-31T07:00Z | 2024-04-30T07:00Z | 2023-12-31 | TTM | 1.5e13 | true |
| KR:005930 | equity | 2024-03-12T07:00Z | | 2023-12-31 | POINT | 3.6e14 | true |
| US:AAPL | revenue_ttm | 2024-02-02T21:30Z | 2024-05-02T21:30Z | 2023-12-30 | TTM | 3.86e11 | true |

- 2024-01-15에 판단하면 첫 줄(2023-09 기준)만 보인다. 2024-01-31 공시 뒤부터 둘째 줄로 바뀐다. **공시일 전에 그 분기 값이 새지 않는 것**이 이 표의 핵심이다.
- `strict_eligible = true`: 공시 원문에서 온 값(엄격판). 판매사 값으로 채운 칸은 비교판에만.

### 2-4. 그 밖의 재료 (모양만)

| 표 | 한 줄 예 |
|---|---|
| `calendar_sessions` | calendar_id XKRX · session_date 2024-03-29 · ts_open 2024-03-29T00:00Z · ts_close 06:30Z · session_kind regular |
| `delistings` | KR:999990 · last_trading_date 2019-07-10 · exit_date 2019-07-19 · delist_type performance · exit_value_status observed · ret_observed −0.95 |
| `tradability_daily` | KR:123456 · 2024-03-29 · status_known true · halted_full_day true · admin_status administrative |
| `classifications` | KR:005930 · scheme krx_sector · level 1 · code "IT" · effective_from 2000-01-01 · ts_known_from 2000-01-01 |
| `share_counts` | KR:005930 · count_kind listed · as_of_date 2023-12-31 · shares 5,969,782,550 · ts_available 2024-01-02T00:00Z |
| `fx_rates` | base USD · quote KRW · rate_kind fixing · obs_date 2024-03-29 · rate 1,346.8 · ts_available 2024-03-29T06:30Z |

---

## 3. 완성본 표 (나): 사용자가 원하는 "패널"

### 3-1. `feature_panels` (name = `factor_pit_monthly`) — 종목 × 월 × 팩터 칼럼

| instrument_id | period | as_of_date | ts_available | market_cap | per | pbr | roe_ttm | mom_12_1 | vol_1y | ret_1m | dps_ttm | … |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KR:005930 | 2024-03-01 | 2024-03-29 | 2024-04-01T00:00Z | 4.92e14 | 32.8 | 1.37 | 0.042 | 0.271 | 0.212 | 0.124 | 1,444 | … |
| KR:000660 | 2024-03-01 | 2024-03-29 | 2024-04-01T00:00Z | 1.33e14 | — | 2.11 | −0.162 | 0.884 | 0.341 | 0.198 | 1,200 | … |
| US:AAPL | 2024-03-01 | 2024-03-29 | 2024-04-01T13:30Z | 2.65e12 | 26.7 | 35.6 | 1.54 | 0.021 | 0.198 | −0.051 | 0.96 | … |
| KR:005930 | 2024-04-01 | 2024-04-30 | 2024-05-02T00:00Z | 4.69e14 | 31.3 | 1.31 | 0.042 | 0.233 | 0.215 | −0.047 | 1,444 | … |

- 한 행 = **한 종목의 한 달**. 칼럼 = 팩터(예: 엄격판 약 360칼럼). 칼럼 뜻은 `dictionary/columns`에 있다.
- `ts_available`: 이 행을 판단에 쓸 수 있는 첫 순간(월말 다음 거래일 개장). 엔진은 이보다 이른 판단에 이 행을 보여 주지 않는다.
- 빈칸(—)은 값 없음. 엔진은 0으로 채우지 않는다.
- 상장폐지된 종목도 폐지 전 달까지 행이 있다(생존 편향 없음).

### 3-2. `label_panels` (정답 수익) — 같은 모양 + 미래 수익

| instrument_id | period | fwd_ret_1m | entry_date | exit_date | ts_label_available |
|---|---|---|---|---|---|
| KR:005930 | 2024-03-01 | −0.047 | 2024-04-01 | 2024-04-30 | 2024-05-02T00:00Z |

- 정답은 `evaluate`의 채점에만 쓴다. 팩터 계산에 넣으면 엔진이 막는다(LabelLeakError).

---

## 4. 엔진이 만드는 패널 = 3-1과 같은 모양

(가) 재료만 넣어도 Pipeline이 같은 "종목 × 날짜 × 칼럼" 표를 만든다.

```python
pipe = nx.Pipeline({
    "per":      Price.market_cap.latest / Fund.net_income_ttm.latest,
    "roe":      Fund.net_income_ttm.latest / Fund.equity.latest,
    "mom_12_1": Returns(252).shift(21),
    "vol_1y":   AnnualizedVolatility(252),
}, screen=nx.universe())
nx.run_pipeline(pipe, start="2024-01-01", end="2024-04-30", freq="monthly")
```

| market | session_date | instrument_id | per | roe | mom_12_1 | vol_1y |
|---|---|---|---|---|---|---|
| KR | 2024-03-29 | KR:005930 | 32.8 | 0.042 | 0.271 | 0.212 |
| KR | 2024-03-29 | KR:000660 | — | −0.162 | 0.884 | 0.341 |
| US | 2024-03-29 | US:AAPL | 26.7 | 1.54 | 0.021 | 0.198 |

- 결과 표에는 `decision_ts` 칼럼도 있다(명세 3.5; 여기서는 줄임).
- (나)의 패널 칼럼을 그대로 쓰려면 `Panel.per.latest`처럼 부른다. (가)로 직접 계산한 값과 섞어 쓸 수 있다.

---

## 5. 이벤트·거시 (다) — v3.4

### 5-1. `events` 공시·실적 발표

| event_id | event_type | instrument_id | series_id | ts_event | ts_available | value | consensus | unit | source |
|---|---|---|---|---|---|---|---|---|---|
| ev-1001 | earnings.prelim | KR:005930 | | 2024-04-05T00:00Z | 2024-04-05T00:05Z | 6.6e12 | 5.4e12 | KRW (영업이익) | dart |
| ev-1002 | buyback.decision | KR:000660 | | 2024-03-20T07:30Z | 2024-03-20T07:31Z | 1.0e11 | | KRW | dart |
| ev-1003 | earnings.announcement | US:AAPL | | 2024-05-02T20:30Z | 2024-05-02T20:31Z | 1.53 | 1.50 | USD/주 (EPS) | sec |
| ev-1004 | macro.release | | US_CPI_YOY | 2024-03-12T12:30Z | 2024-03-12T12:30Z | 3.2 | 3.1 | % | bls |

칼럼 이름은 TDS v1.4 5.21 그대로다(종류 칼럼 이름은 `event_type`, 이름공간 있는 문자열). `instrument_id`·`issuer_id`·`series_id` 가운데 하나는 있어야 한다(없으면 경고 V041). 정정은 새 `event_id`.

쓰는 법: `Events.earnings.days_since()`(= `event_type` `earnings.announcement`), `Events.of("earnings.prelim").surprise`, 일정 `nx.on_event(Events.of("earnings.prelim"), delay=1)`.

### 5-2. `series_observations` 거시 지표 (발표 시각 + 수정 이력)

| series_id | obs_period_end | value | unit | ts_available | is_revision | consensus | frequency |
|---|---|---|---|---|---|---|---|
| KR_CPI_YOY | 2024-02-29 | 3.1 | % | 2024-03-06T23:00Z | false | | M |
| US_CPI_YOY | 2024-02-29 | 3.2 | % | 2024-03-12T12:30Z | false | 3.1 | M |
| US_GDP_QOQ | 2023-12-31 | 3.3 | % | 2024-01-25T13:30Z | false | 2.0 | Q |
| US_GDP_QOQ | 2023-12-31 | 3.4 | % | 2024-03-28T12:30Z | true | | Q |

- 2024-03-01에 판단하면 KR CPI는 1월 값까지만 보인다(2월 값은 3월 7일 발표).
- 미국 GDP 2023Q4는 1월 25일에는 3.3, 3월 28일 수정 뒤에는 3.4. 엔진은 그 시점에 알던 값을 준다.

쓰는 법: `Macro.series("US_CPI_YOY").latest`, `.obs(1)`(전 기간 값), `.age_days`, `.surprise`(consensus 있을 때), `vintage="first"`(첫 발표 판만), `nx.on_event(Macro.series("US_CPI_YOY").changed(), universe_scope="all")`.

---

## 6. 사용자 자신의 데이터 붙이기

```python
nx.dataset.from_parquet("my_sentiment.parquet", shape="panel",  key=("instrument_id","date"), known_on="published_at")
nx.dataset.from_parquet("my_events.parquet",    shape="events", ts_event="event_at", known_on="announced_at", name="my_events")
nx.dataset.from_parquet("my_macro.parquet",     shape="series", period_end="period_end", known_on="released_at", vintage="vintage", name="my_macro")
```

세 모양 모두 **"언제 알 수 있었나"(`known_on`) 칼럼이 필수**다. 없으면 `PointInTimeError`(E3, `layer: data`)로, 모양별 필수 칼럼(사건: `ts_event`와 종목·발행사·계열 id 가운데 하나, 계열: `period_end`·`value`)이 빠지면 `DatasetShapeError`(E47)로 어느 칼럼을 넣으면 되는지 알려 준다. 사건 표에 `event_type` 칼럼이 없으면 `name`이 사건 종류가 된다(명세 3.2).
