# NexusBT 데이터 표준 (TDS) v1 — 엔진 입력 형식 명세, 문서 판 v1.4 (2026-10-28)

이 문서는 한국어 번역본이다. 정본은 영어판 `tds-v1.4.md`다.

> 상태: **초안(draft) → RC → 1.0** 중 **초안**. 표준 판 문자열은 `tds_version = "1.0"` 그대로이고(문법 `MAJOR.MINOR`), 배포 상태는 저장소 태그·문서 머리로만 표시한다(10.5 졸업 조건).
> 판 이력: v1(2026-10-27 초안) → **v1.1**(2026-10-28): 3자 검토(Opus 5.5 · Fable 5.1 · GPT-6.1 Sol xhigh, `review/consensus.md`)의 P0·P1·값싼 P2 반영 — 해시 셋(물리·값·의미)과 언어 무관 정규 직렬화, `classifications` 열쇠에 `level`·`edition`, 두 시간축 직사각형 조회와 이름 일관성(`instrument_symbols.ts_known_to`), 기업행동 해석 절차, 자격 결측 = 거짓, 프로필 판과 검사 세 결과, `producer.hints`, 경로 안전, 실행 안 된 스키마 `experimental`, `minimal-daily`는 분석만, 변경 요약은 15장.
> 판 이력(이어서): **v1.2**(2026-10-28): 시중 엔진 해부(`teardown/MATRIX.md`, 번호 `[V31-NN]`) 반영 — 정확한 분할 비율 `ratio_num/ratio_den`, 폐지 분배 포함 여부, 거래량 단위 검사, 가격 격자와 `market_rules` 데이터셋, 파일 단위 값 해시, 지수 가중 방식. 모두 선택 칼럼·데이터셋·경고라 `tds_version`은 `"1.0"` 그대로(16장).
> 판 이력(이어서): **v1.3**(2026-10-28): 3자 검토 3라운드(`review/consensus-r3.md`, 번호 `[R3-NN]`) 반영 — 기업행동 해석의 존재 시각/조건 시각 분리(5.11), 종료가치 세 기준(5.13), 가격 비교 좌표 = 시장 최소 단위 정수(5.27), 스냅숏 불변성(복제 우선·읽기 전용·원자 게시, 4.1), `files[].value_sha256`은 조언용(4.2), 잘못된 정확 비율의 소비자 거절(5.11), K1 권장 id 예시 고침. 해석 문장 고침과 예시·권고뿐이라 `tds_version`은 `"1.0"` 그대로(17장).
> 판 이력(이어서): **v1.4**(2026-10-28): 3자 검토 4라운드 + 사용자 결정 2026-10-28(번호 `[R4F-NN]`) — 주식 수를 바꾸는 기업행동은 `ratio_num/ratio_den`이 **필수(MUST)**, 없으면 검사기 오류 A010(E); 소비자가 f64에서 비율을 추론하는 길은 없앰(사용자 설정으로 십진 리터럴을 쓰는 경우만, 경고와 기록); 폐지 분배 포함 여부 null의 해석 = 두 번 세지 않는 보수 쪽; 사건 표 `series_id`·`consensus`, 거시 계열 `consensus`·`frequency`와 첫 발표 판 정의. 초안이라 `tds_version`은 `"1.0"` 그대로(18장).
> 관계: 이 문서는 엔진 명세서 v3.4(`engine-spec-v3.4-2026-10-28.md`) **4장이 참조하는 입력 정본**이다. 둘이 다르면 입력 형식은 이 문서가 맞다(차이 목록은 12장). 사용자 결정(설계 문서 9.0)은 이 문서보다 우선한다.
> 공개: 이 표준과 검사기(`nexusbt-tds`, import `nexusbt_tds`, 명령 `tds`)는 공개(Apache-2.0)다. 작업판 11장(생산자별 대응)은 표준의 규범이 아니라서 이 공개판에 넣지 않았다.
> 예시: 엔진이 읽는 모든 데이터셋(사건·거시 계열 포함)의 예시 행은 `tds-examples.md`(같은 폴더)에 있다.
> 표기: [확인] = 이번에 원문을 열어 확인함. [미확인] = 기억·2차 자료에 기댐, 구현 전에 원문 확인 필요. [추] = 추정. [결정] = 이 문서가 정한 것.

## 목차

0. 한 장 요약
1. 조사: 다른 엔진·공급사·표준은 입력 자료를 어떻게 정하나
2. TDS v1의 목표와 핵심 결정 (K1~K12)
3. 공통 규칙 (형, 이름, 시각, 단위, 결측, 열쇠, 파티션, 물리 형식)
4. 패키지 구조와 매니페스트 `tds.json`
5. 데이터셋 종류 (표마다 칼럼·형·열쇠·정렬·파티션·시점 의미·검사)
6. 시점(PIT) 의미 규범
7. 프로필 (작은 사용자부터 전체까지)
8. 적합성 검사기 (CLI, 검사 단계, 오류 코드)
9. 가져오기 어댑터 (zipline, LEAN, Nautilus, Databento DBN, CSV 등)
10. 버전과 진화 규칙
11. (공개판에서 뺌)
12. 엔진 명세서 4장과 맞춤 (차이 목록)
13. 열린 질문
14. 출처
15. v1 → v1.1 변경 요약 (3자 검토 반영)
16. v1.1 → v1.2 변경 요약 (시중 엔진 해부 반영)
17. v1.2 → v1.3 변경 요약 (3자 검토 3라운드 반영)
18. v1.3 → v1.4 변경 요약 (3자 검토 4라운드 + 사용자 결정)

---

## 0. 한 장 요약

**무엇인가.** TDS는 "엔진이 읽는 자료 폴더 하나"의 공개 형식이다. 폴더 안에는 매니페스트 `tds.json` 하나와 Parquet 파일들이 있다. 이 형식만 지키면 어떤 생산자(자료 저장소의 내보내기, 개인의 CSV 가져오기, zipline 묶음·LEAN 폴더·Nautilus 카탈로그·Databento 파일에서 옮긴 것)든 엔진은 똑같이 읽는다. 자료 준비와 엔진은 이 형식으로만 만난다.

**핵심 결정 (자세한 이유는 2장).**

| # | 결정 | 한 줄 이유 |
|---|---|---|
| K1 | 공개 열쇠 = `instrument_id` 문자열. 만든 쪽이 정하는 **불투명하고 재사용하지 않는** id. 기호(티커)·FIGI·ISIN·PERMNO는 별도 표(`instrument_symbols`, `instrument_xref`)에 기간과 함께 | 티커는 바뀌고 재사용된다. FIGI·ISIN은 옛 상장폐지 종목·한국에서 빠짐이 많다. CRSP PERMNO·Sharadar permaticker와 같은 생각 |
| K2 | 모든 시각은 UTC 순간값 `timestamp[unit, tz="UTC"]`. 틱·호가 계열은 `ns`, 나머지는 `us`. 현지 날짜(`session_date` 등)는 `date32` 이름표일 뿐 | Parquet `isAdjustedToUTC=true`가 순간값을 뜻함. Nautilus·Databento가 ns. DuckDB 기본 TIMESTAMPTZ는 us |
| K3 | 모든 관측에 **공개 시각** `ts_available`(칼럼 또는 매니페스트의 유도 규칙). 사건 시각 `ts_event`와 따로 | 엔진 불변식 INV-01(`ts_available <= decision_ts`)을 자료 형식 수준에서 강제 |
| K4 | 가격은 **원가격**(raw)을 저장한다. 조정은 `corporate_actions` 사건 표가 원본이고, 누적 계수는 **상장 첫 세션 = 1.0인 앞으로 누적**(forward-cumulative) | 뒤에서 앞으로 맞추는 계수(LEAN·Yahoo 수정종가)는 새 사건마다 과거 전체를 다시 쓴다 → 바뀌지 않는 파티션·해시가 깨진다 |
| K5 | 재무는 두 층: 원 사건 `fundamentals_events`(사실마다 공개 시각·출처·버전) + 해석 상태 구간 `fundamentals_state`(`[ts_known_from, ts_known_to)`, 겹침 없음, 판(edition)별) | 엔진은 회계 기간 선택 규칙을 다시 만들지 않는다(9.0 Q24). Qlib PIT·Sharadar AR/MR의 장단점을 함께 반영 |
| K6 | 바뀌는 분류·유니버스·식별자는 **두 시간축**: 효력 기간(`effective_from/to`)과 알게 된 시각(`ts_known_from/to`) | "그때 그 분류였다"와 "그때 그걸 알았다"는 다르다 (나중에 채운 업종 이력의 backfill 문제) |
| K7 | 가격 수: 일봉·사건 금액 = `float64`, 틱·호가 = `int64` 고정소수점(데이터셋별 지수, 기본 1e-9) | 호가 수준은 값이 정확히 같아야 같은 수준이다(Databento 1e-9). 일봉은 float64면 충분하고 다루기 쉽다 |
| K8 | 패키지 = 폴더 + `tds.json`(Frictionless Data Package v2에서 **영감을 받은** 뼈대; Data Package의 `resources` 구조를 그대로 구현하지는 않는다 — v1.1 문구 고침). 파일마다 sha256·행 수·통계, 데이터셋마다 값 해시·적용 범위, 패키지마다 물리·값·의미 해시 | Frictionless 도구와 생각을 맞추되 Arrow 형과 시점 규칙은 TDS가 정함 |
| K9 | **프로필**(판 붙음, `@1.0`): `tds:minimal-daily`(표 2개, 분석용)부터 `tds:equity-daily-research`·`tds:l3-book`(experimental)까지. 패키지는 지키는 프로필을 선언하고 검사기가 세 결과(선언·검사 단계·결과)로 확인. 소비자 지원은 소비자가 밝힘 | 작은 사용자는 표 2~4개로 시작 |
| K10 | 버전: 표준 `MAJOR.MINOR`, 데이터셋 스키마마다 `MAJOR.MINOR`. 선택 칼럼·열린 열거값 추가 = MINOR, 그 밖 = MAJOR. 읽는 쪽은 모르는 칼럼을 무시 | Avro/Confluent의 호환 규칙과 SchemaVer의 생각을 단순화 |
| K11 | 결정적 쓰기: 같은 내용이면 같은 바이트, 같은 값 해시(4.5 정규 직렬화 — 쓰기 도구·언어와 무관). 파일·행 정렬, row group 경계 고정 | 엔진 INV-09, 생산자 빌드 지문 원칙과 같다 |
| K12 | 적합성 검사기 `tds check`: 단계 3개(`manifest` / `schema` / `full`), 오류 코드 `TDS-<영역><번호>`, JSON 출력 | 엔진 `SnapshotError`(E14)는 이 코드를 그대로 싣는다 |

**지금 할 일과의 관계.** v1 엔진은 그래프가 쓰는 기능에 필요한 데이터셋만 요구한다(가장 넓게는 `tds:equity-daily-research` + `panels` + `pit-fundamentals`: 주식 일봉 + 재무 + 패널). 나머지(분봉·틱·호가·선물·옵션·코인)는 표 모양을 **실험 판**(`experimental`)으로 정해 두고, 무손실 가져오기와 재생 고정 사례가 생긴 뒤 stable로 올린다(v1.1; v1의 "바꾸지 않고 쓴다" 약속은 너무 일렀다).

---

## 1. 조사: 다른 엔진·공급사·표준은 입력 자료를 어떻게 정하나

### 1.1 엔진

| 대상 | 입력 자료 모양 | TDS가 가져올 것 / 피할 것 |
|---|---|---|
| **zipline-reloaded 묶음(bundle)** | `ingest(environ, asset_db_writer, minute_bar_writer, daily_bar_writer, adjustment_writer, calendar, start_session, end_session, cache, show_progress, output_dir)` [확인]. 일봉·분봉은 bcolz(가격 ×1000을 uint32로, 엔진 E0 문서 5.2), 분봉은 세션 사이 0으로 채움 [확인]. 조정 SQLite: `splits`·`mergers`(sid, effective_date, ratio), `dividends`(sid, ex_date, declared_date, pay_date, record_date, amount), `stock_dividends`(+ payment_sid, ratio) [확인]. 배당 비율 = `1 − 배당 / 배당락 전 세션 종가` [확인]. 종목 DB: equities(symbol, asset_name, start_date, end_date, first_traded, auto_close_date, exchange), futures(root_symbol, notice_date, expiration_date, tick_size, multiplier …), exchanges(exchange, canonical_name, country_code) [확인]. `csvdir` 묶음은 `date,open,high,low,close,volume,dividend,split` [확인] | 가져옴: 원가격 + 사건 표 + 엔진이 계수 계산, 배당 계수 정의(TDS도 같은 식). 피함: 정수 sid를 파일 열쇠로 씀(재매김 때 깨짐), uint32 가격 한계, 공개 시각 없음(분할·배당이 사건일에 바로 알려진 것으로 가정), 세션 달력을 묶음 밖 이름(`NYSE`)에 기댐 |
| **QuantConnect LEAN 자료 폴더** | `<securityType>/<market>/<resolution>/<ticker>/<date>_<tickType>.zip`(틱·초·분), `<securityType>/<market>/<resolution>/<ticker>.zip`(시·일). 머리줄 없는 CSV, 첫 칸이 시각: 분 이하는 "그 파일 날짜 자정부터의 밀리초", 시·일은 `YYYYMMDD HH:mm`, **봉 시각은 시작 시각**, 시간대는 `market-hours-database.json`의 data time zone [확인]. 미국 주식·주식 옵션·지수 옵션 가격은 ×10,000 정수(deci-cents) [확인]. 분봉 칼럼 time, open, high, low, close, volume; 호가 봉은 bid OHLC, bid size, ask OHLC, ask size; 호가 틱은 한쪽만 채우고 다른 쪽 0 [확인]. 거래가 없는 구간은 행이 없음 [확인]. 계수 파일 `factor_files/<ticker>.csv`(날짜, 가격 계수, 분할 계수, 기준 가격)와 맵 파일 `map_files/<ticker>.csv`(날짜, 그때 티커, 거래소)로 조정·티커 변경·상장폐지를 표시 [미확인: 칼럼 순서·최신 판 형식] | 가져옴: 계수와 맵을 원가격과 따로 둠, 시간대를 시장 메타로 분리, 옵션 경로에 행사 방식·권리·행사가. 피함: 뒤에서 앞으로 맞춘 계수(최근 = 1, 새 사건마다 과거가 바뀜), 파일 이름이 티커(재사용·변경 때 맵 파일 필요), 봉 시각 = 시작(공개 시각 실수 유도), 공개 시각 없음 |
| **NautilusTrader** | 자료형: `Bar`, `QuoteTick`, `TradeTick`, `OrderBookDelta(s)`, `OrderBookDepth`, `InstrumentStatus`, `InstrumentClose`, `MarkPriceUpdate`, `FundingRateUpdate` [확인]. 시각 두 개 `ts_event`(사건, 거래소 시각)·`ts_init`(Nautilus가 객체를 만든 시각), 둘 다 유닉스 ns; 백테스트는 `ts_init` 안정 정렬로 재생 [확인]. `BarType` 문자열 `{instrument_id}-{step}-{aggregation}-{price_type}-{INTERNAL|EXTERNAL}`, 예 `AAPL.XNAS-5-MINUTE-LAST-INTERNAL`; price_type LAST/BID/ASK/MID; 봉 `ts_event`는 기본이 **닫는 시각**, 구간은 LEFT_OPEN(시작 제외, 끝 포함) [확인]. `ParquetDataCatalog`: `data/<type>/<identifier>/{start}_{end}.parquet`, 겹치는 쓰기는 기본 `OSError`, 종목 정의는 종목 클래스별 폴더(`data/equity/` 등), 순간값은 `Timestamp(Nanosecond, "UTC")` [확인]. 가격 고정소수점·정밀도 메타 방식 [미확인] | 가져옴: 사건 시각과 받은 시각 분리, 봉 시각 = 닫는 시각, 봉 종류 문자열의 구성 요소(주기·집계·가격 종류·출처), 파일별 시간 범위 이름과 겹침 금지. TDS 틱 표는 Nautilus 자료형과 칼럼이 1:1로 대응하게 정함(9장) |
| **vectorbt** | 넓은 pandas 표(행 = 시각 색인, 열 = 종목), 가격·신호를 같은 모양으로 맞춰 넣음 [미확인: 이번에 문서 열지 않음, 엔진 조사 문서 출처] | 엔진 안 메모리 모양으로는 좋지만 저장 형식으로는 피함(종목 수명·결측 이유·시점 정보가 없어짐). TDS → 넓은 표 내보내기만 제공 |
| **Qlib** | `calendars/day.txt`(한 줄에 날짜 하나), `instruments/all.txt`(`SYMBOL<TAB>start<TAB>end`), `features/<sym>/<field>.day.bin` = 머리 없는 little-endian float32, **첫 값 = 그 자료 첫 날짜의 달력 위치**, 뒤는 달력에 맞춘 값(빈 날 NaN) [확인]. 필수 칼럼 open, close, high, low, volume, factor; 가격·거래량은 **조정된 값**, `factor = 조정가 / 원가`, 첫 거래일 가격을 1로 정규화 [확인]. PIT 재무: `XXX_q.data`/`XXX_a.data` 행 = (date=공개일, period=기간 정수 200704처럼, value, _next=같은 기간 다음 정정본의 바이트 위치) + `.index`; 정정은 덮어쓰지 않고 새 행 [확인] | 가져옴: 달력이 축이고 자료는 달력 위치로 맞춤(엔진 메모리 안 밀집 색인), PIT = "정정은 새 행 + 공개일". 피함: float32 가격(한국 원화 큰 값·미국 BRK.A 정밀도 손실, 기준 생산자가 이미 겪음), 조정된 가격만 저장, 공개 시각이 날짜뿐 |
| **hftbacktest** | numpy 구조 배열 8칸: `ev`(u64 사건 플래그), `exch_ts`(i64), `local_ts`(i64), `px`(f64), `qty`(f64), `order_id`(u64, L3), `ival`(i64), `fval`(f64) [확인]. 플래그 BUY/SELL, DEPTH/TRADE, EXCH_EVENT(거래소 시각 순으로 처리), LOCAL_EVENT(로컬 시각 순으로 처리); `exch_ts <= local_ts`이어야 하고 음수 지연은 고쳐야 함 [확인]. 예시는 ns [확인] | 가져옴: 거래소 시각과 받은 시각을 둘 다 필수로, 지연 모형의 입력이 됨; "받은 시각 < 사건 시각"을 검사 항목으로 |
| **backtrader** | `GenericCSVData`: datetime, open, high, low, close, volume, openinterest 칸 번호를 지정(-1 = 없음) [미확인] | CSV 어댑터의 "칼럼 대응 파일" 방식만 참고 |
| **ArcticDB** | 라이브러리 안 심볼마다 버전이 붙는 DataFrame(시각 색인), 스냅숏, append/update, LMDB·S3 저장 [미확인: 이번에 문서 열지 않음] | 저장 엔진은 쓰지 않음(기준 생산자가 검토해 기각). "버전 + 스냅숏 이름"을 매니페스트의 `snapshot_id`·`parent_snapshot_id`로 반영 |

### 1.2 자료 공급사·관례

| 대상 | 모양 | TDS가 가져올 것 |
|---|---|---|
| **Databento DBN** | 스키마: MBO(L3), MBP-10(L2), MBP-1·TBBO·BBO·Trades(L1), OHLCV(L0), Definition, Statistics, Status, Imbalance, 그리고 기업행동·조정 계수·종목 마스터 참조 스키마 [확인]. 모든 레코드 머리 16바이트: `length`, `rtype`, `publisher_id`, `instrument_id`, `ts_event`(ns) [확인]. 가격 = 부호 있는 정수, 1 단위 = 1e-9; 없음 = `INT64_MAX`; 시각 `ts_event`(매칭 엔진 도착), `ts_recv`(Databento 수신, UTC 동기, 종목별 단조), `ts_in_delta`; 없음 시각 = `UINT64_MAX` [확인]. `action` A/M/C/R/T/F/N, `side` A/B/N, `flags` 비트(F_LAST 128, F_TOB 64, F_SNAPSHOT 32, F_MBP 16, F_BAD_TS_RECV 8, F_MAYBE_BAD_BOOK 4) [확인]. 메타데이터: schema, stype_in/stype_out, 기호 대응(raw_symbol ↔ 기간별 출력 기호), 버전 1/2/3 [확인]. 기호 체계 raw_symbol / instrument_id(게시자가 정함, **날마다 다시 매기는 곳도 있음**) / parent(`ES.FUT`) / continuous(`ES.c.0` 달력, `.n.` 미결제약정, `.v.` 거래량 순위; 가격은 조정 안 함) [확인]. OHLCV `ts_event` = **구간 시작(포함)**, 거래 없으면 행 없음, `ohlcv-1d`는 **UTC 날짜 기준**이라 거래소 세션과 다를 수 있음 [확인] | 틱·호가 칼럼(action·side·flags 값 그대로), 가격 1e-9 고정소수점, `ts_recv`를 공개 시각으로, 연속 계약 = 규칙 이름 + 순위로 정의하고 가격은 조정 안 함, 종목 id와 기호를 기간으로 대응. 주의: UTC 일봉을 세션 일봉으로 쓰면 안 됨(가져오기에서 경고) |
| **Polygon → Massive 평면 파일** | S3 경로 `us_stocks_sip/day_aggs_v1/...`, 일봉 칼럼 ticker, volume, open, close, high, low, `window_start`(유닉스 ns, 봉 시작), transactions; 그날 파일은 다음 날 오전 11시(동부)쯤 나옴 [확인] | 가져오기 어댑터 대상(티커 → id 대응은 기호 이력 필요). "다음 날 11시에 나옴" 같은 배포 지연은 `ts_available` 규칙의 예 |
| **kdb+/tick 관례** | 표 `trade:([]time;sym;price;size)`, `quote`, 날짜 파티션 + 종목·시각 정렬 + `p#`(parted) 속성, 반복 문자열 `sym` 열거, 하루 단위로 메모리 → 디스크 [미확인: 일반 지식] | 틱 파티션 = 날짜, 파일 안 정렬 = (종목, 시각, 순번), 반복 문자열 사전 인코딩 |
| **CRSP / Compustat** | 증권 id PERMNO(재사용 안 함), 회사 id PERMCO; 상장폐지 코드(첫 자리: 2 합병, 3 거래소 이동, 4 청산, 5 퇴출…)와 상장폐지 수익률 DLRET [미확인: 세부 코드]. 2025년부터 새 형식 CIZ만 갱신(2024-12 자료가 옛 SIZ 마지막), 새 형식에 상장폐지·분배·주식 코드 플래그가 더해짐 [확인]. CCM 연결표: GVKEY ↔ PERMNO를 기간(LINKDT~LINKENDDT)·연결 종류(LINKTYPE, L로 시작)·주 연결(LINKPRIM P/C)로 [확인: 2차 자료] | 증권 id와 회사 id 분리, 기간이 있는 연결표(`instrument_xref`), 상장폐지를 사건 + 종료 수익률로(라벨이 아니라), 종료 유형 코드에 CRSP 대응 칼럼(선택) |
| **Sharadar (SF1·SEP·ACTIONS·TICKERS)** | 재무 차원 6개 = (AR 처음 보고 / MR 최근 정정) × (Q / Y / T) [확인: 2차 자료]. `datekey`(제출일)를 공개일로 씀(기준 생산자의 `available_date`) [확인: 생산자 코드]. SEP `closeunadj` 원종가, `close` 분할 조정, `closeadj` 분할 + 배당 조정 [확인: 생산자 코드]. ACTIONS 배당 금액은 분할 조정된 값[확인: 생산자 코드]. TICKERS `permaticker` 안정 id [확인: 생산자 코드] | "처음 보고(AR)"와 "최근 정정(MR)"의 구분 = TDS 판(edition)·정정 사건 모형. 공급사 배당은 원금액으로 되돌려 저장 |

### 1.3 식별자·코드 표준

| 표준 | 내용 | TDS 쓰임 |
|---|---|---|
| **FIGI / OpenFIGI** | 단계: share class FIGI(나라 넘어) > composite FIGI(나라) > FIGI(거래소) [확인: 2차 자료]. 한 번 주면 바꾸지 않는다고 함 [확인: openfigi.com]. 12자리, `BBG` 접두, 모음 없음, 검사 숫자 [미확인] | `instrument_xref`의 `figi`, `figi_composite`, `figi_share_class`. 공개 열쇠로는 쓰지 않음(옛 상장폐지·한국 빈칸) |
| **ISIN (ISO 6166)** | 12자리: 나라 2자 + 9자 + 검사 숫자 [미확인: 표준 원문] | `instrument_xref.isin`. 한국은 `KR7` + 종목코드 + … 꼴이라 연결에 유용 [미확인] |
| **MIC (ISO 10383)** | 4자리. 운영 MIC(OPRT)와 세그먼트 MIC(SGMT, 부모 운영 MIC에 연결) [확인]. XNAS는 운영, XNGS·XNCM 등은 세그먼트 [확인: 2차 자료]. XKRX·XNYS [미확인: 목록 대조], KOSDAQ의 세그먼트 코드(XKOS로 알고 있음) [미확인] | `instruments.venue_mic`(세그먼트 허용) + `operating_mic`. 달력 id는 MIC를 우선 씀 |
| **ISO 4217** | 통화 3자리, 보조 단위 자리수(KRW 0, USD 2, JPY 0) [미확인: 표 대조] | 모든 통화 칼럼. 코인 등 ISO 밖 통화는 매니페스트 `currencies`에 선언(4.3) |
| **ISO 8601 / RFC 3339** | 날짜·시각 글 표현 | 매니페스트·CSV의 글 시각은 RFC 3339 `Z` 끝(예 `2026-10-27T06:30:00Z`), 날짜는 `YYYY-MM-DD` |

### 1.4 저장 형식, 패키지, 스키마 진화

| 대상 | 내용 | TDS 결정 |
|---|---|---|
| **Parquet 논리형** | TIMESTAMP의 `isAdjustedToUTC=true`는 "시간선 위 한 순간", false는 "현지 벽시계 값(순간을 정하지 못함)"; 단위 MILLIS/MICROS/NANOS [확인]. DECIMAL은 int32(정밀도 ≤9)·int64(≤18)·고정 길이·가변 바이트 [확인]. STRING은 BYTE_ARRAY의 UTF-8 [확인] | 순간값은 모두 `isAdjustedToUTC=true`(Arrow `tz="UTC"`). 벽시계 시각 칼럼 금지. INT96 금지(옛 Spark 방식, 시간대 표시 없음 [미확인: 공식 폐기 문구]) |
| **row group 크기** | Parquet 문서는 큰 row group(512MB~1GB), 페이지 8KB를 권함(HDFS 순차 읽기 기준) [확인] | TDS는 가지치기를 위해 일간 표는 약 1개월분(한 시장 약 20만 행), 틱 표는 64~256MB를 권함. 권고이지 검사 대상 아님 |
| **Arrow** | timestamp 형에 tz가 있으면 값은 UTC 기준 epoch [미확인: Schema.fbs 문구]. dictionary 인코딩은 같은 논리형의 물리 표현 | dictionary 문자열과 일반 문자열을 같은 논리형으로 취급(검사기·해시 모두) |
| **Frictionless Data Package v2** | 필수 `resources`(1개 이상); 권장 `name`(소문자·숫자·`.-_`, 바뀌지 않게), `id`(UUID/DOI 등), `licenses`; 선택 `$schema`(2.0 프로필), `version`(semver 권장), `created`(RFC 3339), `contributors`, `sources` [확인]. 자원(path·hash·bytes·schema)과 Table Schema(fields·primaryKey·foreignKeys·missingValues)는 별도 명세 [확인: 위치만] | `tds.json`은 Data Package v2와 같은 위 단계 칼럼을 쓰고 TDS 고유 정보는 `tds` 블록에. 자원 해시 문자열 형식 `sha256:<hex>` [미확인: v2 hash 문법] |
| **SchemaVer (Snowplow)** | MODEL-REVISION-ADDITION. 깨지는 변경은 앞자리, 깨지지 않는 변경은 뒷자리; "깨짐"이 저장소에 따라 다를 수 있음(필수 → 선택이 Redshift에선 깨짐) [확인] | TDS는 두 자리(MAJOR.MINOR)로 줄이고, "깨짐"을 **읽는 쪽 기준**으로 정의(10장) |
| **Avro / Confluent 호환 규칙** | BACKWARD(새 읽기가 옛 자료 읽음), FORWARD(옛 읽기가 새 자료 읽음), FULL [미확인: 이번 조사에서 원문 못 엶] | 같은 MAJOR 안에서는 FULL 호환을 목표: 칼럼은 선택으로만 더하고, 읽는 쪽은 모르는 칼럼을 무시 |

### 1.5 조사에서 뽑은 설계 교훈

1. **사건 시각과 공개 시각을 모두 가진 형식은 틱 쪽뿐이다**(Nautilus `ts_event/ts_init`, Databento `ts_event/ts_recv`, hftbacktest `exch_ts/local_ts`). 일봉·재무 쪽 형식(zipline, LEAN, Qlib bin)은 공개 시각이 없다. TDS는 틱의 이 생각을 모든 자료로 넓힌다(K3).
2. **봉 시각 관례가 갈린다**: LEAN·Databento·Massive는 시작, Nautilus는 닫는 시각. 시작 시각을 공개 시각처럼 쓰면 미래 정보 실수가 난다. TDS는 `ts_start`와 `ts_end`를 둘 다 두고, 기본 공개 시각은 `ts_end`.
3. **조정 계수의 기준점이 갈린다**: LEAN(최근 = 1, 뒤로), Qlib(첫날 = 1), zipline(사건 표만, 엔진이 계산), Sharadar(조정 가격 칼럼). 바뀌지 않는 파일과 해시를 원하면 "첫날 = 1, 앞으로 누적"만 맞다(K4).
4. **식별자**: 성숙한 자료(CRSP, Sharadar, Databento 기호 대응)는 모두 "안정 id + 기간이 있는 기호 대응"이다. 날마다 바뀌는 게시자 id(Databento 일부)·재사용되는 티커는 열쇠가 될 수 없다.
5. **PIT 재무**: Qlib(정정 = 새 행 + 공개일)과 Sharadar(AR/MR 두 판)를 합치면 "사실 사건 표 + 판별 상태 구간"이 된다(K5). 상태 구간은 엔진 조회를 `searchsorted` 한 번으로 만든다(명세서 5.3.5).
6. **고정소수점**: 호가 재구성은 가격 수준의 정확한 같음이 필요하다(Databento·Nautilus 모두 정수). 일봉 연구는 float64가 쉽고 충분하다(K7).
7. **패키지 메타**: Nautilus의 "파일 이름 = 시간 범위 + 겹침 금지", Frictionless의 "자원 목록 + 해시 + 스키마", 기준 생산자 스냅숏 매니페스트의 "빌드 run id + 파일 sha256"을 합친다(K8).

---

## 2. TDS v1의 목표와 핵심 결정

### 2.1 목표와 범위

- **목표**: (1) 자료를 만드는 쪽과 엔진을 완전히 떼어 놓는다. (2) 누구든 이 형식을 지키면 자기 자료로 엔진을 쓸 수 있다. (3) 형식만 보고도 "언제 무엇을 알 수 있었나"가 결정된다. (4) 같은 내용이면 같은 해시.
- **v1에서 엔진이 쓰는 것**: 한국·미국 주식 일봉 연구(`tds:equity-daily-research`).
- **v1에서 모양만 정하는 것**: 분봉·시간봉, 체결, 호가 L1, 호가 L2/L3, 선물(계약·롤), 옵션(계약·체인·그릭 입력), 코인(24/7, 자금조달료), 외환, 대체·사건 자료.
- **하지 않는 것**: 저장 엔진(DuckDB·ArcticDB 등) 지정, 수집·정제 방법, 비용 표(엔진 자원 파일, 명세서 4.17), 엔진의 실행 기록 형식(명세서 5.9).

### 2.2 결정 K1~K12 (이유와 버린 대안)

**K1. 공개 열쇠 = `instrument_id`(불투명, 재사용 안 함).**
- 형식: `^[A-Z0-9][A-Z0-9_]{0,15}:[A-Za-z0-9._\-/^=+]{1,64}$` (이름공간 `:` 지역 id). 이름공간은 매니페스트 `id_namespaces`에 설명과 함께 선언한다. 소비자는 id를 **해석하지 않는다**(불투명).
- 규칙: (a) 한 패키지 안에서 한 id는 한 거래 대상 하나(같은 거래소의 같은 주식 종류 한 줄, 선물 한 월물, 옵션 한 계약, 코인 거래쌍 한 거래소). (b) 티커가 바뀌어도 id는 그대로. (c) **한 번 쓴 id는 다른 대상에 다시 주지 않는다**(패키지 판이 바뀌어도). (d) 회사 합병 등으로 새 증권이 생기면 새 id.
- 기준 생산자의 id(`KR:005930`, `US:AAPL`, 재사용 처리된 `US:ECHO2`)는 이 규칙을 이미 만족한다.
- 작은 사용자 권장: `<MIC>:<티커>_<첫 상장일 YYYYMMDD>`(예 `XNAS:AAPL_19801212`; v1.2 예시 `XNAS:AAPL:19801212`는 지역 부분에 `:`가 들어가 위 형식을 어겼다 — 정규식은 그대로 두고 예시를 고침, 이름공간 분리를 모호하게 하지 않으려고 [v1.3, R3-28]) 또는 FIGI가 있으면 `FIGI:<값>`. 티커만 쓰는 `<MIC>:<티커>`는 티커 재사용(흔함)에서 K1(c)를 깨기 쉬워 권하지 않는다 [v1.1, RV-Q04]. 검사기는 `instrument_symbols` 기간 겹침으로만 확인한다.
- 단면 동률은 `instrument_id` 정렬로 깨지므로 **id 체계를 바꾸면 동률 결과가 바뀔 수 있다**(의도된 결정적 규칙).
- 버린 대안: FIGI를 열쇠로(옛 상장폐지·한국 빈칸, 유료 자료 없이 과거 대응이 어려움), ISIN(종목 전환·재발행, 미국 옛 자료 빈칸), 정수 sid(스냅숏마다 바뀜, 명세서 4.2가 이미 금지).
- 명세서의 `security_id`라는 이름은 `instrument_id`로 바꾼다(선물·옵션·코인·외환에도 맞는 말; Nautilus·Databento·FIX 용어). 엔진 사용자 API도 별칭 없이 `instrument_id` 하나만 쓴다(v1.1, 13장 Q1 닫힘). 다른 이름은 가져오기 대응(9장)에서만 바꾼다.
- 회사 묶음: `issuer_id`(선택, 불투명). 생산자의 회사 id(한국 DART 회사코드, 미국 CIK 등)가 여기에 들어간다.

**K2. 시각 = UTC 순간값, 단위는 데이터셋 종류가 정함.**
- 순간 칼럼 이름은 `ts_` 로 시작하고 형은 `timestamp[us, tz="UTC"]` 또는 `timestamp[ns, tz="UTC"]`. 어느 단위인지는 데이터셋 종류마다 하나로 정해져 있다(고르는 자유 없음 → 해시·결정성 보장).
  - `ns`: `trades`, `quotes`, `book_deltas`, `book_snapshots`, `trading_status_events`, 그리고 주기 1초 미만 `bars`.
  - `us`: 나머지 전부(일봉·분봉 포함).
- 현지 날짜는 `date32`, 이름 끝이 `_date` 또는 `_on`(예외: `period_end`, `period_start`, `effective_from/to`). 날짜는 이름표이고 시각을 대신하지 않는다.
- 현지 벽시계 시각(시간대 없는 timestamp) 칼럼은 금지. 시간대가 필요한 계산(세션 개장·마감)은 `calendar_sessions`가 UTC 순간값으로 이미 풀어 둔다.
- ns int64 범위는 1677~2262년이라 금융 자료에 충분하다.

**K3. 공개 시각 `ts_available`이 모든 관측에 있다.**
- 관측 표는 `ts_available` 칼럼을 갖거나, 매니페스트에 **유도 규칙**(6.2의 규칙 이름)을 선언한다. 검사기·엔진은 규칙을 칼럼으로 펼쳐 같은 뜻으로 쓴다.
- 엔진 규칙은 하나: 관측 x는 `ts_available(x) <= decision_ts`일 때만 쓴다(명세서 INV-01).
- 날짜만 아는 공개(`known_on`)는 만든 쪽이 시각으로 바꿔 내보낸다. 기본 규칙 `next_session_open(known_on)` = 그 시장에서 `known_on` 다음 첫 세션의 `ts_open`(명세서 5.1.4와 같음).

**K4. 원가격 + 사건 표 + 앞으로 누적 계수.**
- `bars`의 가격은 원가격(그날 실제로 거래된 가격, 현지 통화). 조정 가격만 가진 사용자는 `tds:minimal-daily` 프로필에서만 허용되고 `price_basis`를 선언해야 한다(7장).
- 조정의 원본은 `corporate_actions`의 사건마다 가격 배수 `price_factor`(m_e)와 주식 수 배수 `share_factor`(q_e). 수량 효과는 `share_factor`로 **명시**하고, 소비자는 분할류가 아닌 사건에서 가격 계수의 역수로 수량을 추론하지 않는다(5.11 해석 절차) [v1.1].
- 누적 계수 `cum_factor_split`, `cum_factor_total`(bars의 **선택** 칼럼, 어느 프로필에서도 필수 아님): `C[s] = Π_{e ≤ s} m_e`(정정 사슬마다 최신판 하나), 상장 첫 세션 = 1.0. 새 자료를 뒤에 붙여도 옛 행의 값은 바뀌지 않는다. 과거 사건이 늦게 발견되면 그 뒤 행만 바뀐다.
- 역분할 때문에 `C`는 단조가 아니다. 검사는 "사건 ↔ 계수 대조"(A001).
- 공개 시각: 계수는 사건의 `ts_effective`에 효력이 생기지만, 금액·비율이 늦게 공개된 사건(한국 옛 배당)은 사건의 `ts_terms_available`로 소비자가 대기 처리한다(명세서 5.3.4; v1의 `ts_amount_available`은 오기였다). 그래서 계수 칼럼만으로 미래 정보 없는 조정을 할 수 없는 칸이 있다는 것을 표준에 적는다(5.11).

**K5. 재무 = 사실 사건 + 해석 상태 구간.**
- `fundamentals_events`: 공시 숫자 하나 = 한 행(정정은 새 행). 출처·문서 id·공개 시각·기록 시각.
- `fundamentals_state`: 만든 쪽이 정한 해석 규칙(기간 선택·TTM·출처 우선순위·엄격판 자격)으로 계산한 "그때 쓸 값"의 구간. `(edition, instrument_id, item)`마다 `[ts_known_from, ts_known_to)`가 겹치지 않는다.
- 엔진은 상태 표만 조회한다. 사건 표는 설명(`nx.explain`)·감사용.
- 작은 사용자는 상태 표만 내도 된다(`lineage_id` 등은 선택).

**K6. 바뀌는 속성은 두 시간축.**
- 효력 기간 `effective_from`/`effective_to`(세상에서 그 상태였던 기간, 날짜 또는 순간)와 앎 기간 `ts_known_from`/`ts_known_to`(그 기록을 믿고 쓸 수 있던 기간).
- 판단 시각 t에서 쓰는 행: `ts_known_from <= t < ts_known_to` 그리고 효력 기간이 t(또는 질의한 날짜)를 포함.
- 조회는 **직사각형**이다: 앎 조건과 효력 조건을 함께 만족하는 행(6.3). 앎 시각 최대 행을 먼저 고르고 효력을 확인하면 안 된다(미리 발표된 미래 효력 행이 현재 행을 가림).
- 두 시간축 표(`classifications`, `universe_membership`, `instrument_symbols`)는 같은 이름 쌍을 쓴다: 효력 `effective_from`/`effective_to`(`instrument_symbols`는 v1 이름 `valid_from`/`valid_to`를 유지하되 뜻이 같다고 명시), 앎 `ts_known_from`/`ts_known_to` [v1.1].
- 앎 기간을 모르는 자료(대부분의 분류 이력)는 `ts_known_from = effective_from의 순간값`으로 둘 수 있으나 `pit_quality = backfilled`를 선언해야 한다(행 칼럼이 있으면 행 단위, 없으면 데이터셋 단위). **strict 판 조회는 행 단위 `backfilled` 행을 넣지 않는다**; 행 단위 품질이 없는 데이터셋 단위 `backfilled`/`mixed`는 소비자가 경고만 한다(6.5) [v1.1].

**K7. 수의 형.**
- 일봉·사건 금액·재무 값: `float64`. NaN·Inf 금지(결측은 null).
- 틱·호가 가격·수량: `int64` 고정소수점. 데이터셋 매니페스트 `price_exponent`(기본 −9), `size_exponent`(기본 0; 코인은 보통 −8). 값 = 정수 × 10^지수. 없음은 null(Databento `INT64_MAX` 대신).
- 거래량(봉): `float64`(코인 소수 수량, 조정 거래량을 함께 다루려고). 주식은 정수 값이어야 한다(검사 V010, 경고).
- 비율·계수: `float64`. 개수: `int64`. 순번: `int64`(uint64는 일부 도구가 못 읽음).

**K8. 패키지 = 폴더 + `tds.json`.** 4장.

**K9. 프로필.** 7장.

**K10. 버전.** 10장.

**K11. 결정적 쓰기.**
- 파일 안 행 정렬 = 데이터셋의 `sort` 열쇠(5장 각 표). 파일 이름 고정 규칙(4.2). row group 경계는 행 수 기준 고정값(매니페스트에 기록). Parquet 메타데이터에 쓴 시각을 넣지 않는다. 압축 zstd(수준 3 권장), 통계 켬, 페이지 색인 켬.
- 값 해시(4.5)는 물리 선택(압축·row group·dictionary 여부)과 쓰기 도구·언어와 무관하다.

**K12. 적합성 검사기.** 8장.

---

## 3. 공통 규칙

### 3.1 이름

- 칼럼 이름: 소문자 snake_case, ASCII. 예약 접두사: `ts_`(순간값), `x_<이름공간>_`(만든 쪽 확장 칼럼, 예 `x_ex_kr_base_close`). 확장 칼럼은 검사기가 형만 보고 뜻은 보지 않는다.
- 데이터셋 종류 이름 = 폴더 이름(5장 제목). 같은 종류를 여러 개 둘 때는 매니페스트에서 `name`을 따로 주고 `kind`로 종류를 밝힌다(예 `bars` 종류의 `bars_1d`, `bars_1m`).

### 3.2 Arrow 형 (논리형)

| TDS 형 이름 | Arrow | 비고 |
|---|---|---|
| id | `string` | dictionary<int32, string>도 같은 논리형으로 인정 |
| code | `string` | 열거값. 닫힌 열거(목록 밖 = 오류)와 열린 열거(목록 밖 = 경고 + `other`로 읽음)를 5장에 표시 |
| date | `date32` | |
| ts_us | `timestamp[us, tz="UTC"]` | |
| ts_ns | `timestamp[ns, tz="UTC"]` | |
| f64 | `float64` | NaN·±Inf 금지 |
| fixed | `int64` | 고정소수점, 지수는 매니페스트 |
| i8/i16/i32/i64 | 부호 있는 정수 | |
| bool | `bool` | |
| json | `string` | RFC 8259 JSON 글. 사건 자료의 남는 필드용, 열쇠·필터 칼럼에 쓰지 않음 |
| list<code> | `list<string>` | 거래 조건 코드 등 |

### 3.3 결측과 null

- 결측은 Parquet null 하나뿐. NaN·0·빈 문자열·`-1`을 결측 표시로 쓰지 않는다(S009).
- 각 칼럼은 `null 허용` 여부가 정해져 있다. 허용 안 되는 칼럼에 null이 있으면 S003.
- "모름"과 "없음"이 다르면 상태 칼럼으로 구분한다(예 `tradability_daily.status_known`, `bars.obs_status`, `corporate_actions.pay_date_status`).

### 3.4 단위와 통화

- 단위 어휘(`unit`): `ccy`(통화 금액; 통화는 같은 행의 `currency` 칼럼 또는 종목 통화), `LCY`(그 종목의 거래 통화), `shares`, `contracts`, `ratio`(1 = 100%), `bp`, `count`, `days`, `index_points`, `price`(그 종목 가격 단위), `none`. `pct`는 쓰지 않는다(비율은 ratio로).
- 통화 코드: ISO 4217 알파 3자. ISO 밖 통화(코인 BTC·USDT 등)는 매니페스트 `currencies`에 `{"code","kind":"crypto|other","decimals"}`로 선언해야 한다(R004).
- 큰 재무 값의 배율: `scale`(int8, 값 × 10^scale이 실제 금액). 기본 0.
- **거래량 단위** [v1.2, V31-16]: 주식 `volume`은 주 수, 파생은 계약 수다. 거래소·공급사의 묶음 단위(100주, 천 주)로 담으면 안 된다(원래 금지였으나 검사가 없었음 → V011 경고 추가). `value_traded`가 있으면 검사기가 `R = median(value_traded / (volume × (high + low + close)/3))`를 종목·연도마다 계산해 [0.5, 2] 밖이면 V011(건수·R 값, 힌트 "volume may be in lots"). 없으면 `tds check` 요약에 "volume unit unverified".

### 3.5 열쇠, 정렬, 유일성

- 데이터셋마다 `key`(유일해야 하는 칼럼 묶음)와 `sort`(파일 안 행 순서)가 정해져 있다(5장). 매니페스트에도 적는다.
- 파티션 칼럼은 열쇠의 일부일 수 있다. 정렬은 파티션 안에서만 요구한다. 파일이 여러 개인 파티션은 파일 이름 순서로 이어 붙인 결과가 정렬되어 있어야 한다(K002).
- 열쇠 유일 검사는 데이터셋 전체에서 한다(K001).

### 3.6 파티션과 파일

- Hive 방식 `key=value` 폴더. 파티션 칼럼 값은 **파일 안에 저장하지 않는다**(경로에서 읽는다). 값 해시·검사는 파티션 칼럼을 경로 값으로 채운 논리 표로 한다. [결정; 반대 관례와의 충돌은 13장 Q9]
- 파티션 값의 형은 데이터셋 스키마에 적는다(예 `year` = i16, `date` = date32, `market` = code).
- 파일 이름: `part-<5자리 순번>.parquet`(예 `part-00000.parquet`). 틱 자료처럼 시간 범위로 나누는 표는 `<ts_min>_<ts_max>.parquet`(Nautilus식, RFC 3339 시각에서 `:`과 `.`을 `-`로)를 써도 된다. 같은 파티션 안 파일의 시간 범위는 겹치면 안 된다(K004).
- 작은 표(종목 마스터 등)는 파티션 없이 `<dataset>/part-00000.parquet`.

### 3.7 Parquet 물리 규칙 (권고와 필수)

| 항목 | 규칙 |
|---|---|
| 형식 판 | Parquet 2.6 이상 논리형(ns 시각 필요). INT96 금지 (필수) |
| 압축 | zstd 권장. 해시는 압축과 무관 |
| 통계 | 칼럼 통계 필수(가지치기와 검사기 `schema` 단계가 씀). 페이지 색인 권장 |
| row group | 일간 표 약 1개월분, 틱 표 64~256MB 권장 |
| dictionary | 반복 문자열(id, code) 권장 |
| 블룸 필터 | 틱 표 `instrument_id`에 선택 |
| 키-값 메타 | Parquet 파일 메타에 `tds.dataset`, `tds.schema_version`을 넣는다(필수). 쓴 시각은 넣지 않는다 |
| 쓰기 도구 | 매니페스트 `writer`에 이름·판 기록 |

### 3.8 시장(market)

- 시장 = 달력 하나, 기본 통화 하나, 기본 시간대 하나를 가진 묶음. 매니페스트 `markets`에 선언한다(예 `KR`: XKRX, KRW, Asia/Seoul; `US`: XNYS, USD, America/New_York; `CRYPTO`: `CRYPTO-UTC`, USD, UTC).
- 시장 코드는 파티션(`market=`)과 엔진 슬리브(명세서 1.2)의 단위다. 한 종목은 한 시장에 속한다(`instruments.market`).
- 시장의 **완결 워터마크**(`complete_through`): 그 시각까지의 자료는 다 들어 있다는 약속. 엔진 `live`는 이 뒤 세션을 체결에 쓰지 않는다(명세서 4.3).

---

## 4. 패키지 구조와 매니페스트 `tds.json`

### 4.1 폴더 모양

패키지 하나 = 바뀌지 않는 폴더 하나(스냅숏).

**생산자 고유 패키지와 불변성** [v1.2, V31-PUB-01]:
- 패키지는 생산자의 빌드가 **직접** 만들어도 된다(따로 내보내기·변환 층 없이). 예: 생산자 DB 안에 TDS 데이터셋과 이름·칼럼·형·열거가 똑같은 표를 두고, 빌드를 바꿔 끼우는 단계에서 스냅숏 폴더를 이 장의 Parquet 배치 + `tds.json`(해시 포함)으로 쓴다. 어떻게 만들었든 표준이 보는 것은 결과 폴더뿐이다.
- **불변성은 스냅숏 폴더마다** 선다: 한 번 게시한 `<snapshot_id>/` 폴더의 파일 내용·`tds.json`은 바뀌지 않는다. 바꾸려면 새 `snapshot_id`의 새 폴더를 쓴다.
- 파티션 파일은 **복제(copy-on-write clone)·하드 링크·패키지 안 내용 주소 저장**이어도 된다: 앞 스냅숏과 파일 sha256(`files[].sha256`)이 같은 파티션은 새로 쓰지 않고 재사용할 수 있다(디스크 절약). **복제를 먼저 권한다**(APFS `clonefile`, Linux reflink): 한쪽을 실수로 고쳐도 다른 스냅숏이 함께 바뀌지 않는다. 복제가 안 되는 파일 시스템에서만 하드 링크를 쓰고, 그때 게시 파일은 읽기 전용으로 둔다 [v1.3, R3-16]. 내용을 정하는 것은 경로·inode가 아니라 **해시**다 — 물리 해시는 경로와 파일 sha256으로, 값·의미 해시는 4.5 정규 직렬화로 그대로 계산하므로 해시 규칙은 바뀌지 않는다. 그래서 생산자는 **게시한 파일을 절대 제자리에서 고치지 않는다**(MUST; 하드 링크면 두 스냅숏이 함께 바뀌어 불변성이 깨짐; 지울 때는 링크 수가 0이 될 때만 사라짐). 바뀐 파티션은 새 파일로만 쓴다.
- **게시 절차** [v1.3, R3-16]: 준비 폴더에 다 쓰고 → 검사(`tds check`) → 게시 파일을 읽기 전용으로(SHOULD, `chmod a-w`) → 최신 표시(`LATEST` 같은 배포 관례)를 원자적으로 바꾼다. 실패하면 최신 표시를 바꾸지 않는다. 링크를 쓰는 생산자는 공유 파일(링크 수 > 1)의 sha256을 앞 `tds.json`과 대조하는 것을 권한다. 내용 주소 저장은 패키지 안 경로이거나 링크·복제로 들어와야 하고, 패키지 밖을 가리키는 심볼릭 링크는 여전히 금지(M012).
- **소비자의 파일 신원 확인**(권고): 소비자는 sha256을 확인한 파일마다 `(dev, inode, size, mtime_ns)`를 기록하고 다르면 다시 계산할 수 있다. 신원 확인은 우연한 수정 방어이고 암호학적 증명이 아니다(`full` 검사가 모든 바이트를 본다).
- **소비자는 패키지에 쓰기 권한을 요구하지 않는다**: 검사기·엔진은 패키지를 읽기만 하고, 캐시·도장·핀은 패키지 밖(소비자 쪽 폴더)에 둔다. 읽기 전용 마운트·하드 링크 파일에서 그대로 돌아야 한다.
- 시간 여행 표 형식(DuckLake·Iceberg 등)을 패키지 대신 쓰지 않는 이유: 소비자를 한 카탈로그 형식에 묶고 패키지가 자기 완결 폴더가 아니게 되며, "그때 표에 있던 것"(거래 시각)은 "그때 알 수 있던 것"(`ts_available`, 6장)이 아니기 때문이다. 생산자가 내부에서 그런 형식(거래·동시성·스키마 진화·보관의 장점)을 쓰는 것은 자유이고, 표준이 보는 것은 게시된 패키지뿐이다 [v1.3]. 시점은 표준의 공개 시각 칼럼이 정하고, 스냅숏은 재현 단위일 뿐이다.

```
<package>/
  tds.json                                   매니페스트 (필수)
  dictionary/columns/part-00000.parquet      칼럼 사전 (feature_panels·fundamentals 항목이 있으면 필수)
  dictionary/items/part-00000.parquet        재무 항목 사전 (fundamentals가 있으면 필수)
  dictionary/codes/part-00000.parquet        열린 열거값의 뜻 (선택)
  instruments/part-00000.parquet             (필수)
  instrument_symbols/part-00000.parquet
  instrument_xref/part-00000.parquet
  calendar_sessions/part-00000.parquet
  calendar_segments/part-00000.parquet
  bars/freq=1d/market=KR/year=2024/part-00000.parquet
  bars/freq=1m/market=US/date=2024-01-02/part-00000.parquet
  tradability_daily/market=KR/year=2024/part-00000.parquet
  market_rules/part-00000.parquet           (선택, v1.2)
  corporate_actions/part-00000.parquet
  delistings/part-00000.parquet
  share_counts/market=US/part-00000.parquet
  fx_rates/part-00000.parquet
  fundamentals_events/market=KR/part-00000.parquet ...
  fundamentals_state/edition=strict/market=KR/part-00000.parquet
  classifications/part-00000.parquet
  universe_membership/part-00000.parquet
  eligibility_daily/market=KR/year=2024/part-00000.parquet
  feature_panels/name=factor_pit_monthly/edition=strict/year=2024/part-00000.parquet
  label_panels/name=label_monthly/year=2024/part-00000.parquet
  trades/venue=XNAS/date=2024-01-02/<ts_min>_<ts_max>.parquet          (틱, 선택)
  ...
```

- 매니페스트에 없는 파일은 패키지의 일부가 아니다(검사기 M005 경고, 엔진은 읽지 않음).
- 패키지를 옮겨도 경로는 `tds.json` 기준 상대 경로라 그대로 맞다.
- 배포 관례(최신 표시 `LATEST`, 고정 목록 `PINS`, 보관 개수)는 표준 밖이다. 생산자 관례로 남는다(명세서 4.1 그대로).

### 4.2 `tds.json` 칼럼

```json
{
  "$schema": "tds/schemas/1.0/tds.schema.json",
  "tds_version": "1.0",
  "name": "example-kr-us-equity",
  "id": "urn:uuid:6f1c…",
  "version": "20261027-143144",
  "snapshot_id": "20261027-143144",
  "parent_snapshot_id": "20261026-204108",
  "created": "2026-10-27T06:05:46Z",
  "title": "Example KR+US equities",
  "licenses": [{"name": "proprietary"}],
  "producer": {"name": "example-producer", "version": "build-I", "commit": "0000000",
               "checks": {"passed": 92, "total": 92},
               "hints": {"TDS-A001": "rebuild cum factors from corporate_actions (export step 'factors')",
                         "fallback:F-01": "open/high/low not yet exported for this market"}},
  "profiles": ["tds:equity-daily-core@1.0", "tds:equity-daily-research@1.0", "tds:pit-fundamentals@1.0"],
  "id_namespaces": {
    "KR": "KR listed securities: 6-char KRX short code (+ suffix on reuse); never reused",
    "US": "US securities: ticker at first listing (+ digit on reuse, us-identity-v1); never reused",
    "IDX": "benchmark indices"
  },
  "currencies": [],
  "markets": {
    "KR": {"calendar_id": "XKRX", "currency": "KRW", "timezone": "Asia/Seoul",
           "complete_through_session": "2026-10-27", "complete_through": "2026-10-27T06:30:00Z"},
    "US": {"calendar_id": "XNYS", "currency": "USD", "timezone": "America/New_York",
           "complete_through_session": "2026-10-26", "complete_through": "2026-10-26T20:00:00Z"}
  },
  "editions": {"default": "strict",
               "values": {"strict": "filing-sourced lineage only (strict-by-column-v1)",
                          "compare": "vendor values allowed (comparison)"}},
  "policies": {"fundamentals_resolution": "fund-resolution-v1", "delisting": "exit-value-v1",
               "adjustment": "adj-forward-cum-v1", "eligibility": "investable-v1",
               "availability_default": "next_session_open"},
  "roll_rules": {},
  "datasets": [
    {"name": "bars_1d", "kind": "bars", "schema_version": "1.0", "path": "bars/freq=1d",
     "partitioning": [{"name": "freq", "type": "code"}, {"name": "market", "type": "code"}, {"name": "year", "type": "i16"}],
     "key": ["instrument_id", "session_date"], "sort": ["session_date", "instrument_id"],
     "params": {"freq": "1d", "price_basis": "raw", "density": "dense", "bar_time": "session"},
     "availability": {"rule": "ts_end"},
     "pit_quality": "native",
     "rows": 60700000, "value_sha256": "…",
     "coverage": {"instruments": 27627, "ts_min": "1995-05-02", "ts_max": "2026-10-27",
                  "by_market": {"KR": {"instruments": 5495, "first": "1995-05-02", "last": "2026-10-27", "rows": 15700000}}},
     "columns": [{"name": "instrument_id", "type": "id", "nullable": false}, "…"],
     "files": [{"path": "bars/freq=1d/market=KR/year=1995/part-00000.parquet", "rows": 123456, "bytes": 4567890,
                "sha256": "…", "stats": {"session_date": ["1995-05-02", "1995-12-28"]}}]}
  ],
  "hashes": {"physical_sha256": "…", "value_sha256": "…", "semantic_sha256": "…", "hash_spec": "tds-hash-1"},
  "writer": {"name": "pyarrow", "version": "26.0.0", "row_group_rows": 200000}
}
```

| 칼럼 | 필수 | 뜻 |
|---|---|---|
| `tds_version` | ○ | 표준 판 `MAJOR.MINOR` |
| `name`, `id`, `version`, `created` | name·created ○ | Data Package v2와 같은 뜻. `version` = 패키지 판(예: snapshot_id) |
| `snapshot_id`, `parent_snapshot_id` | ○ / 선택 | 바뀌지 않는 판 id. 이전 판(차이 계산용) |
| `producer` | ○ | 만든 도구·판·커밋·검사 결과. 선택 `hints`: `{"<TDS 코드>" 또는 "fallback:<id>": "문장"}` — 소비자가 그 코드의 오류·경고에 붙여 보이는 생산자 쪽 고치는 법(소비자는 특정 생산자를 알지 않는다) [v1.1, MINOR 추가] |
| `profiles` | ○ | 이 패키지가 지킨다고 선언한 프로필과 판(`tds:<이름>@<MAJOR.MINOR>`, 7장; `@` 없으면 `@1.0`). 검사기가 확인 |
| `id_namespaces` | ○ | 쓰인 id 이름공간과 설명 |
| `currencies` | 선택 | ISO 4217 밖 통화 선언 |
| `markets` | ○ | 3.8. 워터마크 필드(`complete_through_session`·`complete_through`)는 매 게시마다 바뀌므로 소비자의 파티션 캐시 열쇠에는 안정 필드(`calendar_id`·`currency`·`timezone`)만 쓰기를 권한다 [v1.3, R3-04] |
| `editions` | 판을 쓰는 표가 있으면 ○ | 판 이름과 뜻, 기본 판 |
| `policies` | 선택 | 만든 쪽 규칙 이름과 판(엔진 실행 기록에 그대로 남음) |
| `roll_rules` | 선물 연속 계약이 있으면 ○ | 5.22 |
| `datasets[]` | ○ | 데이터셋마다: `name`, `kind`, `schema_version`, `path`, `partitioning`, `key`, `sort`, `params`(종류별 매개변수), `availability`(6.2 규칙 또는 `{"column": "ts_available"}`), `pit_quality`(`native` / `backfilled` / `mixed`), `rows`, `value_sha256`, `coverage`, `columns`(이름·형·null·단위·설명), `files[]`(경로·행·바이트·sha256·주요 칼럼 최소/최대·**선택 `value_sha256`** — 그 파일 행만으로 4.5 정규 값 직렬화를 한 값 해시, 파티션 칼럼 포함; 소비자 쪽 조언용 — 이 값은 H004 경고 수준이라 틀려도 패키지가 막히지 않으므로 소비자는 검증하지 않은 `value_sha256`을 캐시 신원으로 쓰지 않는다; 파티션 단위 캐시 신원은 파일 `sha256`이 정한다 [v1.2, V31-12; v1.3, R3-04]). **경로 안전**: 모든 `path`는 패키지 폴더 기준 상대 경로이고 `..`·절대 경로·밖으로 나가는 심볼릭 링크 금지(M012), 같은 파일 경로가 두 번 나오면 안 됨(M013) [v1.1] |
| `hashes` | ○ | 4.5(`physical_sha256`, `value_sha256`, `semantic_sha256`, `hash_spec`) |
| `writer` | ○ | 쓰기 도구, row group 행 수 |

### 4.3 적용 범위(coverage) 블록

데이터셋마다 다음을 적는다. 엔진은 이것으로 "이 기간에 이 자료가 있나"를 실행 전에 알려 준다(명세서 R-22 경고와 연결).

- `instruments`: 서로 다른 `instrument_id` 수.
- `ts_min`, `ts_max`(또는 날짜): 자료가 덮는 범위.
- `by_market`: 시장별 같은 값과 행 수.
- 선택 `by_item`: 재무·패널 칼럼별 첫 해·채움 비율(분자/분모로).

### 4.4 칼럼 사전 (`dictionary/`)

| 데이터셋 | 열쇠 | 칼럼 |
|---|---|---|
| `dictionary/columns` | (`dataset`, `column`) | `dataset`, `column`, `type`, `unit`, `currency_source`(`column:<이름>` / `instrument` / `fixed:<코드>` / null), `scale`, `freq`(daily/monthly/event/…), `edition_class`(strict 자격 규칙 이름), `start_by_market`(json), `description`, `alias_of`, `std_name`(TDS 표준 항목과 같으면 그 이름), `is_label`(bool; 참이면 판단 입력 금지) |
| `dictionary/items` | `item` | `item`, `std_item`(5.17 핵심 항목 이름 또는 null), `statement`(IS/BS/CF/other), `flow_or_stock`(flow/stock), `unit`, `description`, `source_concepts`(json: XBRL 개념 등) |
| `dictionary/codes` | (`field`, `code`) | `field`, `code`, `label`, `description`, `maps_to`(닫힌 TDS 열거로 읽을 때의 값) |

### 4.5 해시 (`hash_spec = "tds-hash-1"`) [v1.1, RV-C10]

세 해시를 따로 둔다. v1의 "논리 해시 = Arrow IPC 바이트"는 Arrow 구현·판·버퍼 정렬에 따라 달라져 다른 언어의 생산자가 같은 값을 낼 수 없었으므로 1.0 전에 바꿨다.

- **파일 해시**: 파일 바이트의 sha256(소문자 hex).
- **물리 해시** `physical_sha256` = sha256(경로 오름차순으로 `"{path}\t{sha256}\n"`을 이은 바이트). 파일 무결성만 뜻한다.
- **데이터셋 값 해시** `value_sha256` — **정규 값 직렬화**(어떤 언어·라이브러리로도 같은 바이트):
  1. 파티션 칼럼을 경로 값으로 채운 논리 표를 만든다(dictionary는 값으로 풀기). 칼럼 순서 = 스키마 파일 순서(선언 순서), 그다음 `x_` 확장 칼럼을 이름 오름차순.
  2. 행 정렬 = `key` 칼럼 오름차순(값 비교 규칙: 수는 수 크기, 문자열은 UTF-8 바이트 사전순, null이 가장 앞), 같으면 나머지 칼럼을 같은 규칙으로.
  3. 머리 바이트: `b"TDSV1\n"` + 칼럼마다 `이름(UTF-8) + b"\t" + 형 태그 + b"\n"` + `b"\n"`.
  4. 행마다 칼럼 순서대로 **칸 바이트**: null이면 `0x00` 한 바이트(값 없음). 아니면 `0x01` + 값 바이트: `bool` 1바이트(0/1); `i8/i16/i32/i64`는 int64로 넓혀 8바이트 little-endian; `f64`는 IEEE-754 비트 8바이트 little-endian(−0.0은 +0.0으로 정규화; NaN은 S009로 이미 금지); `date`는 int32 epoch 일수 4바이트 LE; `ts_us`/`ts_ns`는 int64 그 단위 8바이트 LE(단위는 데이터셋 종류가 정함, K2); `string`/`id`/`code`는 길이 u32 LE + UTF-8 바이트(NFC 정규화 가정, 검사기가 비NFC를 W로); `fixed`(int64 고정소수)는 int64 8바이트; `list<T>`는 원소 수 u32 LE + 원소 칸 바이트들.
  5. 머리 + 모든 행 바이트를 이어 sha256(스트리밍).
- **패키지 값 해시** `value_sha256` = sha256(데이터셋 이름 오름차순 `"{name}\t{value_sha256}\n"`).
- **패키지 의미 해시** `semantic_sha256` = sha256(정규 JSON{`tds_version`, `hash_spec`, 데이터셋마다 {`name`, `kind`, `schema_version`, `value_sha256`, `params`, `availability`, `pit_quality`, `key`, 칼럼의 단위·`price_exponent`·`size_exponent`}, `markets`, `id_namespaces`, `editions`, `policies`, `currencies`, `roll_rules`, `profiles`}). 정규 JSON = 키 오름차순, 공백 없음, UTF-8, 수는 최단 왕복 표기. 같은 Parquet라도 공개 규칙·지수·정책·시장·판·프로필 선언이 바뀌면 의미 해시가 바뀐다. `producer`·`created`·`writer`·`coverage`·`files`·`title`은 넣지 않는다.
- **소비자 쓰임**: 엔진의 캐시·판단 기록·재실행은 **의미 해시**를 "같은 자료"의 정의로 쓴다. 물리 해시는 파일이 바뀌지 않았음을 확인하는 데만.
- **시험 벡터**: 표준과 함께 `conformance/hash-vectors.json`(작은 표 10개: 모든 형, null, −0.0, 빈 문자열, 비ASCII, 파티션 칼럼, 정렬 동률; 기대 바이트 열의 hex와 sha256)을 배포한다. 독립 구현은 이 벡터와 일치해야 한다(10.5 졸업 조건).

---

## 5. 데이터셋 종류

표 읽는 법: **형**은 3.2의 이름. **null**: 아니오 = 필수 값. **열쇠·정렬·파티션**은 표 머리에. "검사"는 8장 오류 코드.

### 5.1 `instruments` (종목 마스터) — 모든 프로필 필수

열쇠 `instrument_id`. 정렬 `instrument_id`. 파티션 없음(필요하면 `asset_class=`).

| 칼럼 | 형 | null | 뜻 |
|---|---|---|---|
| instrument_id | id | 아니오 | K1 |
| asset_class | code(닫힘) | 아니오 | `equity`, `etf`, `fund`, `index`, `future`, `option`, `crypto_spot`, `crypto_perp`, `crypto_future`, `fx_spot`, `bond`, `rate`, `other` |
| category | code(열림) | 예 | 주식 종류: `common`, `preferred`, `adr`, `reit`, `spac`, `unit`, `warrant`, `right`, `closed_end_fund`, `other` |
| market | code | 아니오 | 매니페스트 `markets`의 키 |
| venue_mic | code | 예 | 주 거래 장소 MIC(세그먼트 허용) |
| operating_mic | code | 예 | 운영 MIC |
| calendar_id | id | 아니오 | `calendar_sessions.calendar_id` |
| currency | code | 아니오 | 거래 통화(ISO 4217 또는 선언 통화) |
| issuer_id | id | 예 | 회사 묶음(불투명) |
| name | string | 예 | 현재 이름(이력은 `instrument_symbols`) |
| listed_on | date | 아니오 | 첫 세션(이 패키지가 아는 범위; 자료 시작보다 이른 상장은 자료 첫 세션 + `listed_on_censored = true`) |
| listed_on_censored | bool | 예 | 참 = 실제 상장은 더 이름 |
| last_session | date | 예 | 마지막 가격 세션(상장 중이면 null) |
| delisted_on | date | 예 | 원장 퇴출일(`delistings`와 같아야 함, R008) |
| lot_size | f64 | 아니오 | 주문 최소 단위(주·계약·코인). 기본 1 |
| tick_size | f64 | 예 | 고정 호가 단위. 가격대별이면 null + `tick_rule_id` |
| tick_rule_id | id | 예 | 가격대별 호가 단위 규칙(`market_rules.rule_id`, 5.27; v1.2에서 정의) [V31-05] |
| multiplier | f64 | 아니오 | 계약 승수. 주식 1.0 |
| price_precision | i8 | 예 | 가격 소수 자리(틱 자료 검사용) |
| size_precision | i8 | 예 | 수량 소수 자리 |
| underlying_instrument_id | id | 예 | 파생상품의 기초 |
| root | string | 예 | 선물·옵션 상품 줄기(예 `ES`, `AAPL`) |
| ts_expiry | ts_us | 예 | 만기 순간(선물·옵션) |
| ts_last_trade | ts_us | 예 | 마지막 거래 순간 |
| first_notice_date | date | 예 | 선물 첫 통지일 |
| settlement_type | code | 예 | `cash` / `physical` |
| strike | f64 | 예 | 행사가(가격 단위) |
| option_right | code | 예 | `call` / `put` |
| exercise_style | code | 예 | `american` / `european` / `bermudan` |
| base_currency, quote_currency | code | 예 | 코인·외환 쌍 |
| settlement_currency | code | 예 | 선물·무기한 계약 결제 통화 |
| is_inverse | bool | 예 | 역방향 계약(코인) |
| index_kind | code | 예 | `TR`(배당 포함) / `PR`(가격) / `NTR` — `asset_class = index`일 때 |
| index_weighting | code(열림) | 예 | 지수 가중 방식 `cap` / `float_cap` / `equal` / `price` / `other` — `asset_class = index`일 때. 소비자는 벤치마크 비교에 표시한다 [v1.2, V31-15] |
| is_synthetic | bool | 아니오 | 참 = 실제 거래 대상이 아님(연속 계약·지수). 엔진은 체결에 쓰지 않음 |

검사: R001(다른 표의 id가 여기 없음), V020(`asset_class`별 필수 칼럼: option은 underlying·strike·right·style·expiry·multiplier·settlement 필수; future는 root·expiry·multiplier·settlement 필수; crypto는 base·quote 필수), T010(`last_session < listed_on`), R002(달력 없음).

**사후 정적 표** [v1.1, RV-C08]: `instruments`는 시점 없는 "지금 아는 값" 표다. `name`, `last_session`, `delisted_on`은 사후 정보이므로 소비자는 판단 입력으로 쓰면 안 된다(상장 기간 마스크·표시·폐지 처리에만). 바뀔 수 있는 속성(`category`, `venue_mic`, `currency`, `lot_size`, `tick_size`)이 실제로 바뀐 종목이 있으면 생산자는 그 이력을 `classifications`의 같은 이름 scheme(`category`, `venue_mic` …, 두 시간축)으로 함께 내보내고, 소비자는 그 scheme이 있으면 그것을 읽는다. `asset_class`, `market`, `calendar_id`는 한 id 안에서 바뀌지 않는다(바뀌면 새 id, K1(d)).

### 5.2 `instrument_symbols` (기호 이력)

열쇠 (`instrument_id`, `symbol_type`, `venue_mic`, `valid_from`, `ts_known_from`)(v1.1: 앎 축·장소 추가). 정렬 같음.

| 칼럼 | 형 | null | 뜻 |
|---|---|---|---|
| instrument_id | id | 아니오 | |
| symbol_type | code(열림) | 아니오 | `ticker`(거래소 기호), `local_code`(한국 단축코드 등), `name`, `vendor:<이름>`(예 `vendor:sharadar`, `vendor:lean`, `vendor:databento_raw`) |
| symbol | string | 아니오 | |
| venue_mic | code | 예 | |
| valid_from | date | 아니오 | 효력 시작(포함) |
| valid_to | date | 예 | 효력 끝(제외), null = 지금도 |
| ts_known_from | ts_us | 예 | 이 대응을 알게 된 순간(null = valid_from의 세션 개장과 같다고 봄) |
| ts_known_to | ts_us | 예 | 이 기록을 믿던 끝(제외), null = 지금도. 정정된 기호 대응은 옛 행의 `ts_known_to`를 닫고 새 행을 둔다 [v1.1] |
| source | string | 예 | |

- 같은 `(symbol_type, symbol, venue_mic)`이 기간을 달리해 다른 id를 가리킬 수 있다(재사용). **같은 앎 시점·같은 효력 기간에 두 id를 가리키면 오류** K010.
- 조회는 두 시간축 직사각형(6.3).
- 한 id의 같은 `symbol_type` 구간은 겹치지 않는다(T003).

### 5.3 `instrument_xref` (외부 식별자 연결)

열쇠 (`instrument_id`, `id_type`, `id_value`, `valid_from`). 칼럼: `instrument_id`, `id_type`(열림: `figi`, `figi_composite`, `figi_share_class`, `isin`, `cusip`, `sedol`, `permno`, `permco`, `gvkey_iid`, `cik`, `lei`, `sharadar_permaticker`, `lean_sid`, `nautilus_instrument_id`, `databento_instrument_id`, `occ_osi`, `dart_corp_code` …), `id_value` string, `valid_from` date null(모름), `valid_to` date null, `link_quality` code(`primary`/`secondary`/`inferred`), `source`.
- Databento처럼 날마다 바뀌는 게시자 id는 `valid_from = valid_to − 1일`의 하루 구간으로 적는다. 64비트 부호 없는 게시자 id는 `id_value`에 10진 문자열로(정밀도 손실 없음) [v1.1].
- 앎 축: `instrument_xref`는 v1에서 앎 시각이 없다. 그래서 K6의 두 시간축 약속은 이 표에 **적용하지 않는다**(설명·대응용, 판단 입력 아님). 앎 시각이 필요한 연결은 다음 MINOR에서 `ts_known_from/to`를 선택 칼럼으로 더한다 [v1.1].
- CRSP CCM 같은 회사 단위 연결(GVKEY ↔ PERMNO)은 `id_type = gvkey_iid`, `link_quality`에 LINKPRIM의 뜻을 옮긴다.

### 5.4 `calendar_sessions` (세션) — 일봉 이상 프로필 필수

열쇠 (`calendar_id`, `session_date`). 정렬 같음.

| 칼럼 | 형 | null | 뜻 |
|---|---|---|---|
| calendar_id | id | 아니오 | MIC 우선(`XKRX`, `XNYS`), 그 밖 `CRYPTO-UTC`, `CME-GLOBEX-EQ` 등 |
| session_date | date | 아니오 | 거래일(선물은 결제 기준 거래일) |
| ts_open | ts_us | 아니오 | 정규장 시작 순간 |
| ts_close | ts_us | 아니오 | 정규장 마감 순간(반일장·시간 변경 반영) |
| session_ord | i32 | 예 | 달력 안 0부터 연속 번호(있으면 검사 K011) |
| is_half_day | bool | 예 | |
| session_kind | code | 아니오 | `regular`, `continuous_24h`(코인 UTC 하루), `special` |
| calendar_version | string | 예 | 세션 표 판 |
| source | string | 예 | 예 `exchange_calendars+prices` |

- 세션 표는 일정 자료와 가격을 대조해 만든다. 어떤 종목 가격이 없다고 세션을 지우지 않는다(명세서 4.6).
- 24/7: `session_date` = UTC 날짜, `ts_open` = 00:00Z, `ts_close` = 다음 날 00:00Z.
- 선물 야간 거래: 거래일 D의 세션은 D−1 저녁에 시작할 수 있다(`ts_open < session_date 00:00 현지`). 정상이다.

`calendar_segments`(선택, 장중 구간): 열쇠 (`calendar_id`, `session_date`, `segment`, `ts_start`). `segment` code: `pre`, `opening_auction`, `continuous`, `break`, `closing_auction`, `post`, `single_price_period` 등. 장중 체결 모형(E4)과 한국 단일가 구간에 쓴다.

### 5.5 `bars` (봉, 모든 주기)

파티션: 일봉 `freq=1d/market=/year=`, 분·시봉 `freq=/market=/date=`(하루 한 폴더). 열쇠: 일봉 (`instrument_id`, `session_date`), 장중 (`instrument_id`, `ts_start`, `price_type`). 정렬: 일봉 (`session_date`, `instrument_id`) — 단면 읽기용; 장중 (`instrument_id`, `ts_start`).

매개변수(`params`): `freq`(`1d`, `1w`, `1mo`, `1h`, `30m`, `5m`, `1m`, `1s` …), `price_basis`(`raw` 기본 / `split_adjusted` / `total_adjusted` — 뒤 둘은 `tds:minimal-daily`에서만), `density`(`dense` = 종목 수명 동안 모든 구간에 행 / `sparse` = 거래 있는 구간만), `bar_time`(`session` = 세션 경계 일봉 / `utc_day` = UTC 날짜 일봉 / `interval`), `aggregation`(`time` 기본; `tick`, `volume`, `value` 봉도 허용 — 그때 `ts_start/ts_end`가 가변), `source_kind`(`external` 공급사 봉 / `internal` 체결에서 만든 봉), `ready_delay`(ISO 8601 기간, 선택; 공개 규칙이 `column`일 때 시장 축 행이 굳는 지연 — 소비자는 `ts_close + ready_delay` 뒤에 공개된 봉을 그 행에서 결측으로 본다; 규칙 `ts_end+P`면 P와 같다고 봄) [v1.1]. `price_basis`가 `raw`가 아니면 그 패키지의 봉으로는 원가격 회계를 할 수 없다(7장 `minimal-daily`).

| 칼럼 | 형 | null | 뜻 |
|---|---|---|---|
| instrument_id | id | 아니오 | |
| session_date | date | 아니오 | 거래일. 장중 봉도 필수(선물 야간 → 다음 거래일) |
| ts_start | ts_us/ns | 일봉 예 / 장중 아니오 | 구간 시작(포함). 일봉에서 null이면 세션 `ts_open` |
| ts_end | ts_us/ns | 일봉 예 / 장중 아니오 | 구간 끝(제외). 일봉에서 null이면 세션 `ts_close`. **봉은 `ts_end`에 다 만들어진다** |
| price_type | code | 예 | `last`(기본, 체결가) / `bid` / `ask` / `mid` (Nautilus price_type) |
| open, high, low, close | f64 | 예 | 원가격(현지 통화). `obs_status ∈ {halted, missing, no_trade}`이면 null 허용 |
| volume | f64 | 예 | 원 거래량(주·계약·코인) |
| value_traded | f64 | 예 | 거래대금(현지 통화) |
| trade_count | i64 | 예 | 체결 수(Massive `transactions`) |
| vwap | f64 | 예 | |
| open_interest | f64 | 예 | 선물·옵션 미결제약정(그 봉 끝 기준; 공식 값은 `market_statistics`) |
| obs_status | code(닫힘) | dense면 아니오 | `traded` / `no_trade`(거래 없음) / `halted`(정지) / `missing`(자료 없음 이유 모름) |
| cum_factor_split | f64 | 예 | K4. 상장 첫 세션 1.0 (일봉에만) |
| cum_factor_total | f64 | 예 | 현금 분배까지 넣은 누적 계수 (일봉에만) |
| ts_available | ts_us | 예 | 칼럼 또는 규칙(기본 규칙 `ts_end`; 일봉 공급사 자료가 늦게 나오면 그 지연을 넣어 규칙 `ts_end+P`) |
| source | code | 예 | |

- 일봉 `dense`: 종목마다 `listed_on`부터 `last_session`(없으면 시장 워터마크)까지 그 달력의 모든 세션에 행이 하나(D001). 세션 밖 날짜 행 금지(D002).
- 가격 검사 V001: `low <= min(open, close)`, `high >= max(open, close)`, `low <= high`(값이 모두 있을 때). 원가격은 가격 격자 위(5.27 격자 규범, V012 W) [v1.2, V31-05]. `volume` 단위는 3.4(V011 W) [v1.2, V31-16]. V002 음수 가격·거래량 금지(지수·스프레드 계약 같은 음수 허용 종목은 `instruments.category`로 예외 선언). V004: `obs_status = traded`면 `close` 필수.
- 일봉 종가 = 공식 종가(한국 종가 단일가, 미국 공식 종가). 다르면 `x_` 칼럼으로.
- `shares_out`(명세서 4.7)은 봉에서 빼고 `share_counts`로 옮긴다(공개 시각이 가격과 다르기 때문; 12장 D9). 만든 쪽 편의 칼럼 `x_<ns>_shares_out`은 허용.
- 연속 계약 봉: `instrument_id`가 `is_synthetic = true`인 연속 종목이고 `params.roll_rule`을 밝힌다(5.22).

### 5.6 `trades` (체결 틱) — `status: experimental` [v1.1]

> 5.6~5.9, 5.22~5.24의 스키마는 **실험 판**이다: 무손실 가져오기와 재생 고정 사례가 생길 때까지 1.x 호환 약속(10.2) 밖이고 다음 MINOR에서 바뀔 수 있다. 스키마 파일은 `status: experimental`, 검사기는 이 데이터셋을 담은 패키지에 W(M015)를 낸다. 일봉 주식 데이터셋(5.1~5.5, 5.10~5.21, 5.25~5.26)만 `stable`이다 [RV-I07].

파티션 `venue=/date=`(date = `session_date`). 열쇠 (`instrument_id`, `ts_event`, `sequence`, `trade_id`)(trade_id null 허용이면 열쇠에서 빠지고 `sequence`가 유일해야 함). 정렬 (`instrument_id`, `ts_event`, `sequence`). 시각 단위 ns. 매개변수 `price_exponent`, `size_exponent`.

| 칼럼 | 형 | null | 뜻 |
|---|---|---|---|
| instrument_id | id | 아니오 | |
| session_date | date | 아니오 | |
| ts_event | ts_ns | 아니오 | 거래소 체결 순간 |
| ts_recv | ts_ns | 예 | 받은 순간(수집 시스템) |
| sequence | i64 | 아니오 | 거래소·공급사 순번(없으면 파일 안 순서 번호) |
| price | fixed | 아니오 | |
| size | fixed | 아니오 | |
| aggressor_side | code | 아니오 | `buy` / `sell` / `none` (Databento B/A/N, Nautilus AggressorSide) |
| trade_id | string | 예 | |
| venue_mic | code | 예 | 통합 체결 자료의 실제 거래 장소 |
| conditions | list<code> | 예 | 거래 조건 코드(원 공급사 코드, `dictionary/codes`) |
| action | code | 아니오 | `new` / `cancel` / `correct` (정정·취소 체결) |
| flags | i32 | 예 | 공급사 플래그 비트(Databento 값 그대로 두려면) |

공개 시각 규칙 기본: `ts_recv`가 있으면 `ts_recv`, 없으면 `ts_event + params.assumed_latency`(필수 선언). T008: `ts_recv < ts_event − 허용치`이면 경고(hftbacktest의 음수 지연).

### 5.7 `quotes` (호가 L1 / BBO) — `experimental`

파티션·정렬은 `trades`와 같다. 열쇠 (`instrument_id`, `ts_event`, `sequence`).

칼럼: `instrument_id`, `session_date`, `ts_event`, `ts_recv`, `sequence`, `bid_px` fixed null, `bid_sz` fixed null, `ask_px` fixed null, `ask_sz` fixed null, `bid_ct` i32 null, `ask_ct` i32 null, `venue_mic`, `conditions`, `flags`.
- 행은 "그 순간 이후의 양쪽 최우선 호가 상태"다. 한쪽 호가가 비면 그쪽은 null. LEAN처럼 한쪽만 바뀐 틱은 가져올 때 다른 쪽을 직전 값으로 채운다(9장).
- V030: `bid_px >= ask_px`(잠김·교차)는 경고(시장에 따라 정상일 수 있음).

### 5.8 `book_deltas`, `book_snapshots` (호가 L2/L3) — `experimental`

`book_deltas` — 파티션 `venue=/date=`, 정렬 (`instrument_id`, `ts_event`, `sequence`), 시각 ns. 매개변수 `depth_kind`(`mbp` 가격 수준별 L2 / `mbo` 주문별 L3), `max_depth`(mbp일 때).

| 칼럼 | 형 | null | 뜻 |
|---|---|---|---|
| instrument_id, session_date | | 아니오 | |
| ts_event, ts_recv | ts_ns | 아니오 / 예 | |
| sequence | i64 | 아니오 | |
| action | code(닫힘) | 아니오 | `add`, `modify`, `cancel`, `clear`, `trade`, `fill`, `none` (Databento A/M/C/R/T/F/N) |
| side | code | 아니오 | `bid` / `ask` / `none` |
| price | fixed | 예 | `clear`는 null |
| size | fixed | 예 | mbp: 그 수준의 새 총 수량(0 = 수준 삭제). mbo: 그 주문의 수량 |
| order_id | i64 | 예 | mbo 필수 |
| level | i16 | 예 | mbp에서 수준 번호(선택) |
| is_snapshot | bool | 아니오 | 재생·스냅숏에서 온 행(Databento F_SNAPSHOT) |
| is_last | bool | 아니오 | 같은 사건 묶음의 마지막 행(F_LAST; 이 행 뒤에만 호가가 일관됨) |
| flags | i32 | 예 | 원 비트 |

- 재구성 규칙: 파일(또는 날짜) 첫머리는 `clear` 뒤 `is_snapshot = true` 행 묶음이거나, 이전 날짜 마지막 상태를 이어받는다고 `params.continuity = "carry"`로 선언.
- 엔진은 `is_last = true`인 행 뒤에서만 호가를 읽는다. V031: 재구성 뒤 교차 호가 발생 시 경고, V032: `sequence` 빈칸(공급사가 연속 순번을 약속한 경우) 경고.

`book_snapshots` — 일정 간격 또는 사건마다의 깊이 N 상태. 긴 모양: 열쇠 (`instrument_id`, `ts_event`, `side`, `level`). 칼럼 `ts_event`, `ts_recv`, `side`, `level`(0 = 최우선), `price`, `size`, `order_count`. Databento MBP-10·Nautilus OrderBookDepth를 행으로 편 모양.

### 5.9 `market_statistics` (공식 통계) — `experimental`

열쇠 (`instrument_id`, `stat_type`, `ts_event`). 칼럼: `instrument_id`, `session_date`, `stat_type`(열림: `settlement_price`, `open_interest`, `official_open`, `official_close`, `auction_price`, `auction_volume`, `high_limit`, `low_limit`, `vwap`, `reference_price` …), `value` f64, `unit`, `ts_event`, `ts_available`, `is_final` bool(잠정/확정), `source`. Databento Statistics·Nautilus InstrumentClose에 해당. 선물 정산가·미결제약정의 공개 시각(보통 다음 날 아침)을 여기서 정확히 적는다.

### 5.10 거래 가능 상태: `tradability_daily`, `trading_status_events`

`tradability_daily` — 파티션·열쇠·정렬은 일봉과 같다.

| 칼럼 | 형 | null | 뜻 |
|---|---|---|---|
| instrument_id, session_date | | 아니오 | |
| status_known | bool | 아니오 | 거짓 = 그날 상태를 모름(미국 2019-08-23 전) |
| halted_full_day | bool | 예 | 하루 종일 정지 |
| halt_count | i32 | 예 | 장중 정지 건수 |
| limit_up_close, limit_down_close | bool | 예 | 종가가 상·하한가 |
| locked_up, locked_down | bool | 예 | 하루 종일 그 가격에 묶임 |
| price_limit_ratio | f64 | 예 | 그날 제한폭(0.30 = 30%) |
| up_limit_price, down_limit_price | f64 | 예 | 호가 단위 반올림 뒤 상·하한 가격 |
| reference_price | f64 | 예 | 제한폭 기준가 |
| admin_status | code | 예 | 관리종목·투자주의 등(열림: `normal`, `administrative`, `caution`, `warning`, `liquidation_trading`) |
| ts_available | ts_us | 예 | 칼럼 묶음별 규칙 **`params.availability_by_column` 필수**(v1.1): 사전 정보(`price_limit_ratio`, `up/down_limit_price`, `reference_price`, `admin_status`)는 `session_open`, 하루 결과(`halted_full_day`, `halt_count`, `limit_up_close`, `limit_down_close`, `locked_up`, `locked_down`)는 `session_close` [RV-Q10] |
| source | code | 예 | |

`trading_status_events` — 장중 상태 변화. 열쇠 (`instrument_id`, `ts_event`, `sequence`). 칼럼 `ts_event`(ns), `ts_recv`, `status`(`halted`, `resumed`, `auction`, `pre_open`, `closed`, `luld_pause` …), `reason`(원 코드), `reason_group`, `source`, `source_record_id`. Databento Status, Nautilus InstrumentStatus에 해당.

### 5.11 `corporate_actions` (기업행동 사건, 배당 포함)

열쇠 `event_id`. 정렬 (`instrument_id`, `ex_date`, `event_id`). 파티션 없음(크면 `market=`).

| 칼럼 | 형 | null | 뜻 |
|---|---|---|---|
| event_id | id | 아니오 | 안정 사건 id. 정정은 새 id + `revision_of` |
| instrument_id | id | 아니오 | 영향받는 종목(옛 주식) |
| kind | code(닫힘) | 아니오 | `split`, `reverse_split`, `stock_dividend`, `bonus_issue`(무상증자), `capital_reduction`(감자·병합), `cash_dividend`, `special_dividend`, `return_of_capital`, `rights_issue`, `spinoff`, `stock_merger`, `cash_merger`, `mixed_merger`, `exchange_offer`, `symbol_change`, `name_change`, `par_change`, `other` |
| ex_date | date | 아니오 | 권리락·배당락 세션(효력 세션). 세션이어야 함(A005) |
| ts_effective | ts_us | 아니오 | 효력 순간 = 그 세션 `ts_open`(기본) |
| record_date | date | 예 | 기준일 |
| declared_date | date | 예 | 이사회 결의·공표일 |
| pay_date | date | 예 | 현금 지급·새 주식 상장일 |
| pay_date_status | code | 아니오 | `observed` / `estimated` / `missing` |
| ts_announced | ts_us | 예 | 사건이 공개된 순간(공시 접수) |
| ts_terms_available | ts_us | 예 | 금액·비율이 확정 공개된 순간(한국 옛 배당은 배당락 뒤). null = `ts_announced`와 같음 |
| ratio_num, ratio_den | i64 | 예 | [v1.2, V31-01] 수량 비율의 **정확한 유리수 꼴**(양의 정수 둘, 둘 다 있거나 둘 다 null): 분할류는 `share_factor = num/den`(1:8 역분할 = 1/8, 7:1 = 7/1, 5% 주식배당 = 21/20, 주식배당 0.29 = 129/100), 합병·분할설립은 `ratio_new_per_old = num/den`(교환비율 0.4237 = 4237/10000). 소비자는 이것을 정본으로 정수 산술 `q' = (q·num) div den`을 한다. f64 칼럼은 그 몫(보조). **[v1.4, R4F-01] 보유 주식 수를 바꾸는 모든 사건**(`split`, `reverse_split`, `stock_dividend`, `bonus_issue`, 주식 병합인 `capital_reduction`, `spinoff`, `stock_merger`, `mixed_merger`, 주식 교환이 있는 `exchange_offer`, 배정 비율이 있는 `rights_issue`)**은 `ratio_num/ratio_den`을 반드시(MUST) 채운다.** 검사 A010(**E**, v1.4에서 W → E): 그런 사건에 둘 다 null, 한쪽만 있음, 0 이하, f64 칼럼과 상대 1e-12 넘게 다름. 소비자는 f64 칼럼에서 유리수를 추론하지 않는다(v1.3의 "추론하면 기록" 허용을 없앰 — f64만으로는 0.333이 1/3인지 333/1000인지 정할 수 없다). 정확 비율이 없는 외부 자료는 사용자가 소비자 설정으로 명시적으로 고른 경우에만(NexusBT `[corporate_actions] decimal_ratio = "literal"`) f64의 최단 왕복 십진 표기를 정확한 십진 분수로 쓸 수 있고(0.333 → 333/1000), 그때 A010은 경고로 낮아지며 소비자는 건수를 보고서에 남긴다 |
| ratio_new_per_old | f64 | 예 | 옛 1주당 받는 새 주식 수(분할 2:1 → 2.0, 1:10 역분할 → 0.1, 주식배당 b → b, 합병 교환비율, 분할설립 배정비율) |
| new_instrument_id | id | 예 | 받는 종목(stock_merger·spinoff·exchange_offer) |
| cash_per_share | f64 | 예 | 옛 1주당 현금(배당, 현금 합병, 단주 대금 기준) — **원금액(그날 주식 기준)** |
| currency | code | 예 | cash_per_share 통화 |
| gross_or_net | code | 예 | `gross` / `net` (원천징수 전/후) |
| subscription_price | f64 | 예 | 유상증자 청약가(권리) |
| price_factor | f64 | 예 | 이 사건의 가격 배수 m_e(아래). `factor_method ≠ unavailable`이면 필수(A003). 계산할 수 없으면 1.0이 아니라 null + `factor_method = unavailable` |
| share_factor | f64 | 예 | 옛 1주가 몇 주가 되나(보유 수량·거래량·주식 수 배수; 분할 r → r, 주식배당 b → 1 + b, 현금·권리 사건 1.0). 분할류(`split`, `reverse_split`, `stock_dividend`, `bonus_issue`, `capital_reduction`)에서 null이면 `ratio_new_per_old` 규칙으로 만든다. **그 밖의 종류에서 가격 계수의 역수로 추론하지 않는다**(권리·분배·분할설립은 가격과 수량 효과가 다름) [v1.1] |
| affects | code | 아니오 | `split_and_total`(주식 수가 바뀌는 사건) / `total_only`(현금 분배) / `none`(이름 변경 등) |
| factor_method | code | 아니오 | `ratio`(분할류: 1/(r)), `cash_prev_close`(1 − D/종가[e−1]), `terp`(권리: 이론 권리락가/종가[e−1]), `spinoff_first_close`(1 − 배정비율×신설 첫 종가/종가[e−1]), `vendor`(공급사 계수 그대로), `unavailable` |
| factor_ref_price | f64 | 예 | 계수 계산에 쓴 기준 가격(종가[e−1] 등) |
| revision_of | id | 예 | |
| status | code | 아니오 | `announced` / `effective` / `cancelled` |
| source, evidence_id | string | 예 | 원문 문서 id |

**계수 규칙(m_e).** 분할·역분할·병합: `1 / ratio_new_per_old`(역분할은 ratio < 1 → m > 1). 주식배당·무상증자 b: `1 / (1 + b)`. 현금배당 D: `1 − D / close[e−1]`(zipline과 같은 식 [확인]). 권리 발행: `TERP / close[e−1]`, `TERP = (close[e−1] + n·S) / (1 + n)`(n = 옛 1주당 새 주식, S = 청약가). 분할설립: `1 − ratio × first_close(new) / close[e−1]`(또는 만든 쪽이 공시 기준가로 계산; `factor_method`로 밝힘). 합병으로 종목이 사라지는 경우는 계수가 아니라 `delistings` + 보유 전환으로 처리(`price_factor = 1.0`, `affects = none`).

**누적 계수와의 관계.** `bars.cum_factor_split[s] / cum_factor_split[s−1]` = 그 세션에 효력인 `affects = split_and_total` 사건들의 `price_factor` 곱(상대 1e-12, A001). total도 같은 방식으로 모든 사건. 사건 없는 세션은 정확히 1.0.

**시점.** 계수는 `ts_effective`부터 효력이지만, 소비자는 `ts_terms_available > 판단 시각`인 사건을 그 판단에서 넣지 않는다(명세서 5.3.4). 그래서 `cum_factor_*`는 "모든 사건을 안다고 가정한" 편의값이고, 미래 정보 없는 조정의 정답은 사건 표다. 이것을 표준 문구로 둔다. 분할설립 계수(`spinoff_first_close`)는 신설 종목 첫 종가가 있어야 계산되므로 `ts_terms_available >= ts_close(효력 세션)`이어야 한다(A009). 수량을 바꾸는 사건의 조건이 효력 뒤에 공개되면 W(A008) [v1.1].

**해석 절차 (기준 시각 c에서)** [v1.1, RV-C03] — 조정·회계·검사(A001)가 모두 이 절차 하나를 쓴다(참조 구현 `nexusbt_tds.actions.resolve(events, c)`):
1. `revision_of`를 따라 사슬로 묶는다(뿌리 = `revision_of` 없는 사건; 순환은 A007).
2. 판 r의 **존재 시각** `ts_known(r)` = `ts_announced`와 `ts_terms_available` 중 null이 아닌 것의 가장 이른 값(둘 다 null이면 `ts_effective`), **조건 시각** `ts_terms(r) = coalesce(ts_terms_available, ts_known(r))`. c에서 쓰는 판 = `ts_known(r) <= c`인 판 중 `ts_known` 최대(같으면 `event_id` 오름차순 마지막). 없으면 c에서 "모름". 고른 판의 `ts_terms(r) > c`이면 "존재는 알지만 조건 미공개": 가격 효과는 대기, 권리는 금액 모르는 권리이고 그 수량은 효력 세션 시작 보유로 고정된다(그 뒤 처분해도 남음). v1.2의 `ts_pub = coalesce(ts_terms_available, …)`는 조건이 늦은 판을 조건 공개 전에 통째로 숨겨 이 대기 상태에 닿을 수 없었다. `ts_effective`는 다른 두 시각이 모두 없을 때만 쓴다(효력보다 늦게 공시된 사건이 효력 순간부터 보이면 미래 정보) [v1.3, R3-01].
3. 고른 판이 `status = cancelled`면 효과 없음; `announced`이면서 `ts_effective <= c`면 효과 없음(소비자 경고); `effective`면 효과 있음.
4. 효과 넷: 가격 계수 `price_factor`(null이면 "없음" — 누적 계수도 그 경계에서 "없음"), 수량 계수 `share_factor`(위 규칙), 권리(현금·새 종목·비율), 결제(`pay_date`, `pay_date_status`).
5. 같은 사슬의 판이 c에 따라 바뀌면(정정·취소) 소비자는 이미 기입한 금액을 정정 기입으로 바로잡는다(과거 기입을 고치지 않음).
6. A001은 `c = +∞`(패키지 전체 지식)로 풀어, 사슬마다 최신판 하나만 곱하고 취소된 사슬은 1.0으로 대조한다. 같은 사건의 옛 판과 새 판을 둘 다 곱한 계수는 A001 오류다.

**배당 날짜 주의.** 한국은 기준일(record) ≠ 배당락일(ex). 결제 주기 때문에 배당락은 보통 기준일 전 영업일이다 [미확인: 시기별 규칙]. 기준일만 아는 자료는 `ex_date`를 규칙으로 유도하고 `x_<ns>_ex_date_method = 'record_minus_1_session'` 같은 칼럼을 남긴다.

### 5.12 (계수만 있는 자료의 처리)

LEAN 계수 파일·Qlib `factor`·공급사 조정 종가만 있는 사용자는 가져오기 때 계수 변화에서 사건을 거꾸로 만든다: 연속 세션 계수 비가 1이 아닌 곳마다 `kind = other`, `factor_method = vendor`, `price_factor = 비`, `ts_terms_available = null`(=효력 순간에 알려진 것으로 가정)인 사건 하나. 매니페스트에 `pit_quality: "backfilled"`. 엔진은 이 사건으로 가격 조정은 하지만 현금배당 계좌 처리는 하지 못한다고 경고한다. `kind = other`는 실행에 영향이 있는 닫힌 열거의 "모름" 값이라 소비자는 보유 중이면 "지원 안 하는 사건"으로 다룬다(조용히 회계하지 않음) [v1.1].

### 5.13 `delistings` (상장폐지·종료 사건)

열쇠 `delisting_id`. 정렬 (`instrument_id`, `exit_date`). 명세서 4.11과 생산자 정책 `exit-value-v1`의 뜻을 그대로 옮기고 이름만 TDS 규칙으로.

| 칼럼 | 형 | null | 뜻 |
|---|---|---|---|
| delisting_id, instrument_id | id | 아니오 | |
| last_trading_date | date | 아니오 | 마지막 가격 세션 |
| exit_date | date | 아니오 | 원장 퇴출일 |
| ts_exit_known | ts_us | 예 | 퇴출 사실 공개 순간. v1.1에서 null 허용(사후에만 아는 생산자가 많음): null이면 종료 세션 개장 순간으로 보고 그 데이터셋 `pit_quality`는 `backfilled`/`mixed` [RV-Q09] |
| delist_type | code(열림) | 아니오 | `merger`, `spac_merger`, `acquisition_cash`, `exchange_transfer`, `liquidation`, `performance`, `voluntary`, `expiry`(파생·펀드 만기), `unknown` |
| crsp_dlstcd_equiv | i16 | 예 | CRSP 상장폐지 코드 대응(선택, 비교용) [미확인 코드표] |
| ref_date | date | 아니오 | 종료가치 기준 가격 날짜 |
| ref_price | f64 | 아니오 | 기준 원가격(한국 정리매매면 그 가격) |
| exit_value_status | code(닫힘) | 아니오 | `observed` / `estimated` / `unobserved` |
| ret_observed | f64 | 예 | 기준가(`ref_price`, 주식 수 단위만 맞춤) 대비 관측 종료 수익률 |
| ret_observed_includes_distributions | bool | 예 | [v1.2, V31-04; v1.3, R3-05] 참 = `ret_observed`가 `last_trading_date` 뒤 배당락인 현금 분배(청산 분배 등)를 이미 담음(CRSP DLRET식) → 관측 총액 = `q·ref_units·(1 + r)`이고, 배당락 때 이미 기입한 그 분배를 빼서 남은 종료 금액을 정한다(배당락 때 아직 몰랐던 플래그로 과거 기입을 지우지 않음); 거짓 = 담지 않음 → 분배는 따로 기입하고 종료 = `q·ref_units·(1 + r)`(관측 금액은 분배를 뺀 값이므로 분배 계수를 **곱하지 않는다**; v1.2의 "분배만큼 계수를 곱한 기준"은 분배를 두 번 줄였다); null = 모름(그런 분배가 있으면 A011 W). 모름이면 소비자는 참·거짓 두 해석의 총 회수액(분배 + 종료) 가운데 **작은 쪽**을 쓰고 경고한다 — 분배를 두 번 세지 않는다(v1.3의 "거짓으로 봄"은 `r = 0` 관측에서 분배를 두 번 셈) [v1.4, R4F-05]. 정책값(`ret_policy`·`ret_lo`·`ret_hi`)에는 분배 뒤 남은 자본 기준(분배 계수를 곱한 기준)을 쓴다. `ref_units` = `ref_price` × 그 뒤 주식 수 단위 사건의 가격 계수 |
| ts_value_available | ts_us | 예 | 관측 대가 공개 순간. 소비자는 이 순간 전에는 관측 대가를 판단 크기·현금에 쓰지 않는다(금액 모르는 권리) — null이면 `ts_exit_known`, 그것도 null이면 종료 세션 개장 [v1.1, RV-C01] |
| ret_policy | f64 | 예 | 정책값(만든 쪽 규칙, `policy_id`) |
| ret_lo, ret_hi | f64 | 아니오 | 손실 시나리오(상·하한 아님 — 소비자는 이것을 "가장 큰 부담"으로 부르지 않는다 [v1.3, R3-09]) |
| policy_id | id | 아니오 | |
| pay_date | date | 예 | 대가 지급일 |
| handled_by_event_id | id | 예 | 주식 합병 등 `corporate_actions`가 처리하면 그 id(그때 종료가치 적용 안 함) |
| reason_code | string | 예 | 원 사유 코드 |
| evidence_id | string | 예 | |

검사: A011(W, v1.2: `last_trading_date` 뒤 배당락 분배가 있는데 `ret_observed_includes_distributions`가 null), R008(`instruments.delisted_on`과 `exit_date` 일치), V040(`ret_lo <= ret_hi`), T011(`ts_value_available < ts_exit_known`이면 경고).

### 5.14 `share_counts` (주식 수, PIT)

열쇠 (`instrument_id`, `count_kind`, `as_of_date`, `ts_available`). 칼럼 `instrument_id`, `count_kind`(`listed`(상장주식수), `outstanding`(발행 유통), `float`, `treasury`), `as_of_date` date(그 수가 맞는 날짜), `shares` f64, `ts_available`, `source`, `evidence_id`. 한국 상장주식수(거래소 일별)는 `as_of_date = 세션, ts_available = 세션 마감`, 미국 SEC dei 주식 수는 `as_of_date = 표지 기준일, ts_available = 제출 순간`.

### 5.15 `fx_rates` (환율)

열쇠 (`base`, `quote`, `rate_kind`, `ts_event`, `source`). 정렬 같음.

| 칼럼 | 형 | null | 뜻 |
|---|---|---|---|
| base, quote | code | 아니오 | 1 base = rate quote |
| rate_kind | code | 아니오 | `fixing`(고시·기준율), `mid`, `bid`, `ask`, `close` |
| obs_date | date | 아니오 | 고시 날짜 |
| ts_event | ts_us | 아니오 | 관측 순간(예 FRED H.10은 뉴욕 정오 매입률 [미확인: 정확한 정의]) |
| ts_available | ts_us | 아니오 | 발표 순간(H.10처럼 늦게 나오면 그 순간) |
| rate | f64 | 아니오 | > 0 (V005) |
| source | code | 아니오 | |

반대 방향은 엔진이 `1/rate`로. 외환을 거래 대상으로 쓸 때는 `instruments(asset_class = fx_spot)` + `bars`/`quotes`.

### 5.16 `rates` (금리 곡선, 옵션 그릭 입력)

열쇠 (`curve_id`, `tenor_days`, `ts_event`). 칼럼 `curve_id`(예 `USD-SOFR`, `USD-TBILL`, `KRW-CD91`), `currency`, `tenor_days` i32, `rate` f64(연율, ratio), `compounding` code(`simple`/`annual`/`continuous`), `day_count` code(`ACT/360` 등), `ts_event`, `ts_available`, `source`.

### 5.17 `fundamentals_events` (재무 사실, 원 PIT 사건)

파티션 `market=`. 열쇠 `fact_id`. 정렬 (`instrument_id`, `item`, `period_end`, `ts_available`, `fact_id`).

| 칼럼 | 형 | null | 뜻 |
|---|---|---|---|
| fact_id | id | 아니오 | 안정 사실 id |
| instrument_id | id | 아니오 | 재무가 회사 단위면 대표 종목(우선주 등은 `issuer_id`로 묶음) |
| issuer_id | id | 예 | |
| item | code | 아니오 | `dictionary/items`의 항목 |
| period_start | date | 예 | 흐름 항목의 기간 시작 |
| period_end | date | 아니오 | 기간 끝(잔액은 그날) |
| period_kind | code | 아니오 | `Q`, `H`, `9M`, `A`, `TTM`, `POINT`(잔액) |
| fiscal_year | i16 | 예 | |
| fiscal_period | code | 예 | `Q1`..`Q4`, `H1`, `FY` |
| statement_basis | code | 아니오 | `consolidated` / `separate` / `unspecified` |
| accounting_standard | code | 예 | `K-IFRS`, `K-GAAP`, `US-GAAP`, `IFRS` … |
| value | f64 | 아니오 | |
| unit | code | 아니오 | 3.4 |
| currency | code | 예 | |
| scale | i8 | 아니오 | |
| known_on | date | 예 | 공개 날짜(원자료가 날짜뿐일 때) |
| ts_available | ts_us | 아니오 | 공개 순간(K3; `known_on`만 있으면 규칙으로 유도) |
| ts_recorded | ts_us | 예 | 만든 쪽이 처음 기록한 순간(시스템 시각) |
| version | i32 | 예 | 같은 (종목, 항목, 기간, 기준, 출처)의 정정 순번 |
| supersedes_fact_id | id | 예 | 정정 대상 |
| source | code | 아니오 | 출처 |
| source_rank | i16 | 예 | 만든 쪽 우선순위 |
| doc_id | string | 예 | 원문 문서 id(DART 접수번호, SEC accession) |
| value_how | code | 예 | `reported`, `derived`(차감·합산), `vendor`, `preliminary`(잠정 실적; v1.1 추가 — 열린 열거라 MINOR) |
| strict_eligible | bool | 아니오 | 엄격 자격(전이적 계보) |
| vendor_input | bool | 아니오 | 계보에 공급사 값 |
| pit_quality | code | 아니오 | `native`(원래 공개 시각) / `backfilled`(나중에 모아 시각을 추정) |

- T007: `ts_available < period_end`면 오류. 단 `value_how = preliminary`인 행은 경고(W)로 낮춘다(잠정 공시는 기간 끝 전에 나올 수 있음) [v1.1, RV-I06].
- **TDS 핵심 항목**(`std_item`, 선택 매핑): `revenue`, `gross_profit`, `operating_income`, `pretax_income`, `net_income`, `net_income_parent`, `eps_basic`, `eps_diluted`, `dps`, `ocf`, `capex`, `fcf`, `da`, `interest_expense`, `total_assets`, `current_assets`, `cash`, `total_liabilities`, `current_liabilities`, `total_debt`, `equity`, `equity_parent`, `shares_outstanding`, `shares_weighted_basic`, `shares_weighted_diluted`, `inventory`, `receivables`, `payables`, `dividends_paid`, `buyback`. **이 목록은 잠정 매핑(provisional)이고 상호운용을 보장하지 않는다**: 연결/별도 범위, 지배주주 몫, 흐름 기간, 통화, 축척, 부호(예 capex)의 정의 문장은 다음 판 부록에서 정한다. 그때까지 서로 다른 생산자의 같은 `std_item`이 같은 뜻이라고 가정하지 말 것 [v1.1, RV-I06]. 만든 쪽 항목은 자유이고 `std_item`으로만 대응한다.

### 5.18 `fundamentals_state` (재무 해석 상태 구간) — 엔진이 읽는 재무

파티션 `edition=/market=`. 열쇠 (`instrument_id`, `item`, `ts_known_from`). 정렬 같음.

| 칼럼 | 형 | null | 뜻 |
|---|---|---|---|
| instrument_id | id | 아니오 | |
| item | code | 아니오 | |
| ts_known_from | ts_us | 아니오 | 이 상태를 쓸 수 있게 된 순간 |
| ts_known_to | ts_us | 예 | 다음 상태로 바뀐 순간(null = 지금도) |
| period_end | date | 아니오 | 선택된 보고 기간 끝 |
| period_kind | code | 아니오 | 5.17 |
| statement_basis | code | 아니오 | |
| value | f64 | 아니오 | |
| unit, currency, scale | | | 5.17 |
| strict_eligible | bool | 아니오 | |
| vendor_input | bool | 아니오 | |
| selected_fact_id | id | 예 | 고른 사실 |
| lineage_id | id | 예 | 계보(TTM이면 구성 사실 목록; `x_` 확장 표나 `fundamentals_events`로 펼침) |
| resolution_policy | id | 아니오 | 해석 규칙 판 |

- 구간은 반열림이고 `(edition, instrument_id, item)`마다 겹치지 않는다(T003). `ts_known_to > ts_known_from`(T004).
- strict 판에는 `strict_eligible = true`인 상태만. 공백은 구간 없음(엔진 NaN). 엔진은 다른 판으로 채우지 않는다.
- 판단 시각 t의 값: `ts_known_from <= t < ts_known_to`인 구간 하나. 오래된 값 거르기(`max_age_days`)는 엔진 설정(명세서 5.3.5).
- 작은 사용자: `fundamentals_events` 없이 이 표만 내도 된다(사건 → 상태 변환은 만든 쪽 일). 반대로 사건만 있는 사용자를 위해 참조 변환기 `tds derive fundamentals-state --policy latest-available`(가장 늦게 공개된 최신 기간 값; 정정 반영)를 제공한다(8.4).

### 5.19 `classifications` (분류, 두 시간축)

열쇠 (`instrument_id`, `scheme`, `level`, `edition`, `effective_from`, `ts_known_from`)(v1.1: `level`·`edition` 추가 — v1 열쇠로는 GICS 섹터·산업 행이나 strict/compare 행이 같은 날 오면 K001 중복이었다) [RV-C08]. 정렬 같음.

칼럼: `instrument_id`, `scheme`(예 `gics`, `krx_sector`, `sic`, `industry_pit`, `market_segment`, `is_financial`, `category`, `venue_mic`), `level` i8 **null 금지**(단일 수준 체계는 0, 다단계는 1 = 가장 굵은 수준), `code` string, `label` string null, `effective_from` date, `effective_to` date null, `ts_known_from` ts_us, `ts_known_to` ts_us null, `edition` code(`strict`/`compare`/`both`, 기본 both), `pit_quality` code(행 단위), `source`.
- 조회: 직사각형(6.3) — `ts_known_from <= t < ts_known_to` 그리고 `effective_from <= date(t) < effective_to`, 판 필터(strict = `strict`+`both`, compare = `compare`+`both`), strict는 행 단위 `backfilled` 제외. 같은 (종목, 체계, 수준, 판 필터)에서 이 조건을 만족하는 행은 하나(T012).
- `dictionary/columns.alias_of`로 소비자 이름(예 `sector`)을 `"<scheme>@<level>"`에 대응할 수 있다.
- 명세서 4.13의 `valid_from_utc/valid_to_utc/known_at_utc`를 이 두 축으로 바꾼다(12장 D12).

### 5.20 유니버스: `universe_membership`, `eligibility_daily`

`universe_membership`(지수 편입 등 기간): 열쇠 (`universe_id`, `instrument_id`, `effective_from`, `ts_known_from`), 조회는 직사각형(6.3). 칼럼 `universe_id`(예 `index:KOSPI200`, `index:SP500`), `instrument_id`, `effective_from` date, `effective_to` date null, `ts_known_from`, `ts_known_to`, `weight` f64 null, `source`. 지수 변경은 발표가 효력보다 앞서므로 두 축이 모두 필요하다.

`eligibility_daily`(만든 쪽의 투자 대상 판정): 파티션 `market=/year=`, 열쇠 (`rule_id`, `instrument_id`, `session_date`). 칼럼 `rule_id`(예 `investable-v1`), `is_eligible` bool, `reason` code null(열림: `not_common`, `administrative`, `unit`, `preferred`, `fund`, `no_price`, `no_mcap` …), `ts_available`(v1.1 **기본 `session_close`** — 판정이 그날 정보를 쓰는 경우가 보통이라 보수적 기본; 판정이 개장 전 정보만 쓴다고 생산자가 선언할 때만 `session_open`) [RV-C09]. dense일 필요 없음. **읽는 규칙**(v1.1): 판단 세션 s에서는 그 세션의 행 하나만 본다; 행이 없거나 `ts_available > 판단 시각`이면 **대상 아님(거짓)**이다 — 앞 세션의 참을 이어 쓰지 않는다(`params.missing_means = false`는 이 뜻의 선언이고 다른 값은 v1.1에 없음). 이월 상태가 필요한 생산자는 이월을 미리 풀어 dense로 내보낸다.

### 5.21 사건·대체 자료: `events`, `series_observations`

`events`(일반 사건: 실적 발표, 공시, 내부자 거래, 뉴스 점수, 전망치 스냅숏 …): 열쇠 `event_id`. 파티션 `event_type=`(이름공간 있는 문자열, 예 `filing.kr_dart`, `earnings.announcement`, `estimate.snapshot`). 칼럼 `event_id`, `event_type`, `instrument_id` null, `issuer_id` null, `series_id` null [v1.4: 거시 발표 같은 시장 수준 사건 — 셋 중 적어도 하나는 있어야 함, 아니면 검사 V041(W)], `ts_event`(사건이 일어난 순간), `ts_available`(필수, 내용이 공개된 순간 — 소비자는 이 시각 전에 사건을 보이지 않아야 함), `ts_recorded` null, `value` f64 null, `consensus` f64 null [v1.4: 발표 전 시장 예상치, 있으면 서프라이즈 = value − consensus], `unit` null, `payload` json null, `source`, `doc_id`. 같은 사건의 정정은 새 `event_id` + `payload.revision_of` [v1.4, R4F-EV-02]. 자주 쓰는 사건은 `params.columns`로 정한 형 있는 칼럼을 더할 수 있다(그 경우 사건 종류별 데이터셋 `name`을 따로 주고 `kind = events`).

`series_observations`(거시·대체 시계열, 판(vintage) 포함): 열쇠 (`series_id`, `obs_period_end`, `ts_available`). 칼럼 `series_id`, `obs_period_start` date null, `obs_period_end` date, `value` f64, `unit`, `ts_available`(그 판 발표 순간 — 관측 기간 끝이 아님: 9월 CPI는 10월 발표 순간), `is_revision` bool, `consensus` f64 null [v1.4], `frequency` code null(`D`/`W`/`M`/`Q`/`A`) [v1.4], `source`. ALFRED식 판 저장: 같은 기간 값의 정정은 새 행; 첫 발표 판 = 그 기간에서 `ts_available`이 가장 이른 행 [v1.4, R4F-EV-01].

### 5.22 선물: 계약, 롤 일정, 연속 계약 — `experimental`

- 계약 = `instruments`(asset_class `future`) 행. 계약 id 권장 `CME:ESZ2024`(연도 4자리; `ESZ4`는 10년마다 재사용되므로 id로 쓰지 않음, 기호 이력에는 남김).
- `roll_calendar`: 열쇠 (`roll_rule_id`, `root`, `session_date`, `rank`). 칼럼 `roll_rule_id`, `root`, `session_date`, `rank` i16(0 = 앞), `instrument_id`, `ts_available`(OI·거래량 기준 롤은 **전날** 자료로 정해지므로 전날 통계 공개 순간; Databento `.n.`·`.v.`도 전날 기준 [확인]).
- 매니페스트 `roll_rules`: `{"ES-c": {"mapping": "calendar", "offset_sessions": -5, "anchor": "last_trade"}, "CL-n": {"mapping": "open_interest"}}`. `mapping` ∈ {`calendar`, `last_trade`, `first_notice`, `open_interest`, `volume`}; `normalization` ∈ {`none`, `ratio`, `difference`}(연속 봉을 낼 때만).
- 연속 계약 봉은 선택 파생물: `instruments(is_synthetic = true, asset_class = future, root, x_roll_rule)` + `bars`. **신호용**이며 체결·손익은 실제 계약으로(명세서 11.3).
- 정산가·미결제약정은 `market_statistics`.

### 5.23 옵션: 계약, 체인 스냅숏, 그릭 입력 — `experimental`

- 계약 = `instruments`(asset_class `option`; underlying·strike·right·exercise_style·ts_expiry·multiplier·settlement_type 필수). 미국 상장 옵션은 OCC 기호(OSI)를 `instrument_xref.occ_osi`에. id 권장 `OPRA:AAPL240621C00190000`.
- `option_chain_snapshots`: 파티션 `underlying=/date=`. 열쇠 (`instrument_id`, `ts_snapshot`). 칼럼 `instrument_id`, `underlying_instrument_id`, `session_date`, `ts_snapshot`(ts_us), `ts_available`, `bid`, `ask`, `bid_size`, `ask_size`, `last`, `volume`, `open_interest`, `underlying_price`, `underlying_price_kind`(`mid`/`last`/`close`), `iv_vendor`, `delta_vendor`, `gamma_vendor`, `vega_vendor`, `theta_vendor`, `rho_vendor`, `greeks_model`(공급사 모형 이름) — **공급사 값만 저장**한다. 엔진이 다시 계산한 값은 입력이 아니다(명세서 11.3 "공급자 값과 재계산 값 구분").
- 그릭 재계산 입력: 기초 가격(위 칼럼 또는 기초 `bars`/`quotes`), 금리 `rates`, 배당 `corporate_actions`(발표된 미래 배당) + 선택 `dividend_forecasts`(`events` 종류), 대차 비용(선택 `series_observations`).
- 틱 단위 옵션 호가는 `quotes`를 그대로 쓴다.

### 5.24 코인: 24/7, 무기한 계약 — `experimental`

- 달력 `CRYPTO-UTC`(5.4). 종목 id 권장 `<거래소>:<기호>`(`BINANCE:BTCUSDT`, `BINANCE:BTCUSDT-PERP`).
- `funding_rates`: 열쇠 (`instrument_id`, `ts_event`). 칼럼 `ts_event`(지급 순간), `rate` f64(그 구간 비율), `interval_hours` f64, `is_predicted` bool(예측치), `ts_available`, `source`. Nautilus FundingRateUpdate.
- `reference_prices`: 열쇠 (`instrument_id`, `price_kind`, `ts_event`). `price_kind` ∈ {`mark`, `index`, `settlement`}. Nautilus MarkPriceUpdate.
- 수량은 소수: `size_exponent`(틱), 봉 `volume` f64.

### 5.25 `feature_panels`, `label_panels` (만든 쪽이 계산한 넓은 표)

`feature_panels` — 파티션 `name=/edition=/year=`. 열쇠 (`instrument_id`, `period`). 칼럼 `instrument_id`, `period` date(그 기간 첫날, 예 월 = 1일), `as_of_date` date(경제적 기준일), `ts_available`(행 단위 필수; 예: 월간 패널은 `as_of_date` 다음 세션 개장), 그리고 특징 칼럼들(각각 `dictionary/columns`에 단위·뜻·`is_label = false`). 계보 표시 칼럼(`x_ex_fin_strict_row` 등)은 확장 칼럼.

`label_panels` — 같은 모양 + `entry_date`, `entry_price_basis`, `exit_date`, `horizon`, `return_definition`(예 `econ_reinvest_ex_close`, `adj_ratio`), `terminal_policy_id`, 그리고 선택 시각 칼럼 `ts_label_start`, `ts_label_end`(결과의 끝), `ts_label_available`(그 정답 값을 처음 계산할 수 있던 순간 — 늦게 공개된 폐지 회수액·배당 금액을 포함) [v1.1, RV-C04]. 시각 칼럼이 없으면 소비자는 `entry/exit_date`와 `entry_price_basis`로 앞의 둘을 만들고 `ts_label_available = ts_label_end`로 가정한다(가정 기록). 모든 값 칼럼은 `is_label = true`. **엔진은 판단 입력으로 읽지 않는다**(명세서 R-16). 검사 V050: `label_panels` 칼럼 이름이 `feature_panels`에 있으면 오류(이름 충돌로 새는 것 막기).

### 5.26 벤치마크

별도 표를 두지 않는다. 지수는 `instruments(asset_class = index, index_kind = TR|PR, is_synthetic = true)` + `bars`(`close` = 지수 값, `volume` null). 명세서 4.16 `benchmarks_1d`는 이 모양으로 바뀐다(12장 D15). 없으면 엔진은 "n/a: not in snapshot"(R-59 그대로).

---

### 5.27 `market_rules` (시장 규칙: 호가 단위·가격제한폭) — 선택, stable [v1.2, V31-05]

열쇠 (`rule_id`, `rule_kind`, `venue_group`, `valid_from`, `price_from`). 정렬 같음. 파티션 없음. 13장 Q15를 닫는다(v1.1에서 "다음 판"으로 미뤘던 것).

| 칼럼 | 형 | null | 뜻 |
|---|---|---|---|
| rule_id | id | 아니오 | 규칙 묶음 id(예 `krx-tick-2023`). `instruments.tick_rule_id`가 이것을 가리킨다 |
| market | code | 아니오 | 매니페스트 `markets` 키 |
| rule_kind | code(닫힘) | 아니오 | `tick_band`(가격대별 호가 단위) / `price_limit`(하루 가격제한폭) |
| venue_group | code(열림) | 아니오 | `*`, `KOSPI`, `KOSDAQ`, `NYSE` 등(가격 정책 묶음 이름) |
| valid_from | date | 아니오 | 효력 시작(포함) |
| valid_to | date | 예 | 효력 끝(제외), null = 지금도 |
| price_from | f64 | 예 | 가격대 하한(포함, `tick_band`만; null = 0) |
| price_to | f64 | 예 | 가격대 상한(제외; null = 끝없음) |
| tick_size | f64 | 예 | 그 가격대 호가 단위(`tick_band`면 필수, 0보다 큼) |
| limit_ratio | f64 | 예 | 기준가 대비 제한폭(`price_limit`면 필수, 0.30 = 30%) |
| source | string | 아니오 | 거래소 규정·공고 URL |
| verified | bool | 아니오 | 사람이 원문으로 확인했는가 |

- **가격 격자 규범**: 원가격 칼럼(`bars.open/high/low/close`, `tradability_daily.*_limit_price`)은 그 종목·그 날짜의 격자 위 값이어야 하지만, f64 표현 때문에 1e-9 상대 안의 흔들림은 허용한다(`0.6768000000000001`). 소비자는 비교 전에 **시장 최소 단위 정수**(KR 1원, US 0.0001달러 같은 한 좌표)로 바꾼다 — 가격대마다 다른 호가 단위의 틱 수로 비교하면 경계를 넘는 두 가격의 순서가 뒤집힌다(4,995/5 = 999 > 5,000/10 = 500). 호가 단위 표는 격자 소속 확인과 주문 가격 맞춤에 쓴다. 최소 단위 정수에 맞지 않는 관측 가격은 소비자가 옮기지 않는다(그 행만 실수 비교) [v1.3, R3-02]. 격자 원천 순서: `instruments.tick_size`(고정) → `tick_rule_id`의 `market_rules` → 소비자 자원. 검사 V012(W): 격자 정보가 있는데 원가격이 격자에서 1e-9 상대 넘게 벗어난 행(조정가를 원가격으로 잘못 선언한 패키지를 잡음).
- 가격대 구간은 맞추기 전 값으로 정한다. 같은 (`rule_id`, `venue_group`, 날짜)에서 가격대 구간이 겹치면 T003.
- 공매도 금지 기간·대차 자료는 이 표준에 두지 않는다(엔진 시장 규칙 팩의 일; 대차 가능 수량·수수료 데이터셋은 다음 MINOR 후보) [V31-LS-07].

## 6. 시점(PIT) 의미 규범

### 6.1 시각 칼럼의 뜻 (모든 표 공통)

| 칼럼 | 뜻 | 누가 정하나 |
|---|---|---|
| `ts_event` | 세상에서 일이 일어난 순간(체결, 봉 끝, 효력) | 원자료 |
| `ts_recv` | 수집 시스템이 받은 순간(틱) | 수집기 |
| `ts_available` | 전략이 그 판단에서 쓸 수 있게 된 가장 이른 순간. **엔진 관문은 이것 하나** | 만든 쪽(규칙 또는 칼럼) |
| `ts_known_from` / `ts_known_to` | 상태·기록을 믿고 쓸 수 있던 앎 기간 | 만든 쪽 |
| `effective_from` / `effective_to` | 세상에서 그 상태였던 효력 기간 | 원자료 |
| `ts_recorded` | 만든 쪽 시스템이 처음 기록한 순간(시스템 시간) | 만든 쪽 |
| `known_on` | 공개 날짜(날짜만 있을 때의 원 값) | 원자료 |

### 6.2 공개 시각 유도 규칙 (매니페스트 `availability.rule`)

| 규칙 | 뜻 |
|---|---|
| `column` | `ts_available` 칼럼을 그대로 |
| `ts_end` | 봉의 `ts_end`(일봉에서 null이면 세션 `ts_close`) |
| `ts_end+<ISO 8601 기간>` | 예 `ts_end+PT15M`(공급사 지연) |
| `session_open` / `session_close` | 행의 `session_date` 세션 개장/마감 |
| `next_session_open(<날짜 칼럼>)` | 그 날짜 **다음** 첫 세션의 `ts_open`(종목 달력 기준). 기본 날짜 칼럼 `known_on` |
| `ts_recv` | 틱 받은 순간 |
| `ts_recv_else(<칼럼>+<기간>)` | `ts_recv`가 null이면 다른 시각 + 지연 |
| `ts_recv+<기간>` | `ts_recv` + 사용자 쪽 수신 지연 가정(예 Databento `ts_recv`는 게이트웨이 수신이라 사용자 수신보다 이르다) [v1.1] |

- 규칙으로 표현 못 하는 것(예: "다음 날 동부 11시 배포")은 칼럼으로 낸다.
- 칼럼과 규칙을 함께 선언하면 검사기가 둘이 같은지 본다(T002).
- 칼럼별로 다른 공개 시각(예 `tradability_daily`의 개장 전 정보와 종가 결과)은 `params.availability_by_column`로 묶음마다 규칙을 준다(`tradability_daily`에는 필수, 5.10).
- 규칙 이름은 **필수 해석 규칙**이다: 소비자가 모르는 규칙 이름을 만나면 무시하지 말고 거절해야 한다(검사기 M014, 10.3) [v1.1].
- `corporate_actions`의 공개 시각은 두 개다: 효력 `ts_effective`, 조건 `ts_terms_available`(null이면 `ts_announced`, 둘 다 null이면 `ts_effective`). 매니페스트 `availability`는 `{"effect": "ts_effective", "terms": "ts_terms_available"}`로 적는다(T002가 확인) [v1.1].

### 6.3 조회 의미 (엔진·참조 구현이 지켜야 하는 것)

1. **점 관측**(봉·사건·환율·패널): 판단 t에서 `ts_available <= t`인 행만. 같은 열쇠 대상의 "최신"은 `ts_event`(또는 `period`) 최대.
2. **상태 구간**(`fundamentals_state`): `ts_known_from <= t < ts_known_to`인 한 행(한 축; 겹침 없음이 T003으로 보장).
3. **두 시간축 — 직사각형 조회**(`classifications`, `universe_membership`, `instrument_symbols`): 판별 열쇠마다 `ts_known_from <= t < ts_known_to` **그리고** 효력 기간이 질의 날짜 포함인 행. 두 조건을 **함께** 거른다: 앎 시각 최대 행 하나를 먼저 고르면 미리 발표된 미래 효력 행이 현재 효력 행을 가린다. 고정 예시(명세서 5.3.6 표와 같음, 검사기 T012 conformance): ① 미리 발표: A 효력 [2019-01-01, ∞)·앎 [2018-12-01, 2020-03-06), A′(같은 코드, 효력 [2019-01-01, 2020-03-20))·앎 [2020-03-06, ∞), B 효력 [2020-03-20, ∞)·앎 [2020-03-06, ∞) → (t = 2020-03-10, q = 2020-03-10)의 답 A′; ② 늦은 발견: 효력은 지났지만 앎 전 → 옛 행; ③ 정정: 앎 구간이 닫힌 옛 행 대신 새 행; ④ 수준: level마다 하나; ⑤ 판: strict/compare 필터마다 하나.
4. **사건 효력과 조건 공개가 다른 기업행동**: 5.11 해석 절차. 판단에서는 효력과 조건 공개가 둘 다 `<= t`일 때 조정에 넣는다(명세서 5.3.3·5.3.4).
5. **세션 마감 기준**: 시장 축 행 s의 값은 `ts_close(s)`까지 쓸 수 있는 정보만(명세서 5.1.2). 이건 엔진 규칙이고 자료 형식은 `ts_available`만 제공한다.

### 6.4 이력 방식 두 가지

- **경제 이력**(`history_mode = economic`, 기본): 나중에 모은 옛 공시도 원래 공개 시각으로 쓴다. `ts_available`만 본다.
- **시스템 이력**(`history_mode = system`): "그때 만든 쪽 시스템이 실제로 알던 것"을 재생한다. 판단 t에서 `ts_recorded <= t`도 요구한다. `tds:bitemporal` 프로필이 `ts_recorded`를 필수로 만든다.

### 6.5 `pit_quality`

데이터셋(또는 행)마다 `native`(원자료가 준 공개 시각) / `backfilled`(나중에 모아 추정) / `mixed`. **strict 처리(v1.1, K6과 하나로 맞춤)**: 행 단위 `pit_quality` 칼럼이 있는 표(두 시간축 표)는 strict 조회에서 `backfilled` 행을 뺀다; 행 단위 품질이 없는 데이터셋 단위 `backfilled`/`mixed`는 소비자가 strict 실행에서 경고한다(전체를 빼면 가격·사건처럼 필수 자료가 사라지므로). `mixed`는 "일부 행이 backfilled"라는 선언이고 어떤 행인지 숨기지 않으려면 행 칼럼을 두는 것을 권한다. 검사기는 값을 판단하지 않고 선언만 확인한다 [RV-C09].

---

## 7. 프로필

패키지는 지키는 프로필을 판과 함께 `profiles`에 적는다(`tds:<이름>@<MAJOR.MINOR>`; v1.1의 모든 프로필은 `@1.0`). 프로필은 겹쳐 쓸 수 있다. 아래 "필수"는 그 프로필에서 데이터셋과 칼럼이 반드시 있어야 한다는 뜻이다. **프로필은 적합성 주장이고 소비자 지원과 다르다** [v1.1, RV-I01]: 검사 결과는 프로필마다 세 가지 — **선언됨**(`profiles`에 있음), **검사됨**(어느 단계 `manifest`/`schema`/`full`까지 확인; 그 단계가 볼 수 없는 규칙은 `not_checked`이고 통과가 아님), 그리고 소비자(엔진)의 **지원 여부**는 소비자 문서가 따로 밝힌다(아래 표의 마지막 열은 참고). 새 오류 검사는 새 프로필 판(`@1.1`)에만 걸어 표준 MAJOR를 올리지 않게 한다(10.2). `cum_factor_*`는 어느 프로필에서도 필수가 아니다(사건이 원본).

| 프로필 | 필수 데이터셋 | 추가 필수 칼럼·조건 | 엔진이 할 수 있는 것 |
|---|---|---|---|
| `tds:minimal-daily@1.0` | `instruments`, `bars(freq=1d)` | bars: `close`만 필수. `price_basis` 아무거나(선언 필수). `calendar_sessions` 없으면 소비자가 bars 날짜로 만들고 경고 | **분석 경로만**(NexusBT v1: `run_pipeline`, `screen(factor)`, `evaluate(target="fwd_return_adj")`). 조정가로는 배당·수량·종료가치 회계가 정의되지 않으므로 경제 백테스트·경제 정답은 지원하지 않는다(v1의 "종가 체결 backtest" 약속은 뺐다) [v1.1, RV-I03] |
| `tds:equity-daily-core@1.0` | 위 + `calendar_sessions`, `corporate_actions`(빈 표 허용), `delistings`(빈 표 허용) | bars `price_basis = raw`, `density = dense`, OHLCV, `obs_status`; corporate_actions 계수 칼럼 | 명세서 v1의 `backtest`·`screen` 전부(OHLC 체결 규칙, 분할·배당·상장폐지) |
| `tds:equity-daily-research@1.0` | 위 + `tradability_daily`, `eligibility_daily`, `instrument_symbols`, `fx_rates`(시장이 둘 이상이면), `fundamentals_state`, `classifications`, `dictionary/columns`, `dictionary/items` (선택 `market_rules`, v1.2) | `ts_available` 규칙 명시(`tradability_daily.availability_by_column` 포함). (v1의 `cum_factor_*` 필수는 뺐다) | v1 전체(Fund.*, Universe, 다중 통화 슬리브) — **기준 생산자 목표** |
| `tds:panels@1.0` | `feature_panels`, `label_panels`, `dictionary/columns` | 행 단위 `ts_available` | `Panel.*`, `evaluate(target=Label.*)` |
| `tds:pit-fundamentals@1.0` | `fundamentals_events` + `fundamentals_state` | `fact_id`, `doc_id`, `lineage_id` | `nx.explain` 계보 |
| `tds:bitemporal@1.0` | (다른 프로필 위에) | `ts_recorded`가 events·classifications·state에 | 시스템 이력 재생 |
| `tds:intraday-bars@1.0` (experimental) | `instruments`, `calendar_sessions`, `bars(freq<1d)` | `ts_start`, `ts_end`, `session_date`, `density` 선언 | E4 장중 경로 체결 |
| `tds:l1-ticks@1.0` (experimental) | `trades`, `quotes` | `ts_event`, `sequence`, 공개 시각 규칙 | E4 |
| `tds:l2-book@1.0` (experimental) | `book_deltas(mbp)` 또는 `book_snapshots` | `is_last`, 시작 스냅숏 | E4 |
| `tds:l3-book@1.0` (experimental) | `book_deltas(mbo)` | `order_id` | E4 대기열 모형 |
| `tds:futures@1.0` (experimental) | `instruments(future)`, `market_statistics`, `roll_calendar`(연속 계약을 쓰면) | 계약 필수 칼럼 | E4·E5 |
| `tds:options@1.0` (experimental) | `instruments(option)`, `option_chain_snapshots` 또는 `quotes`, `rates` | 계약 필수 칼럼 | E5 |
| `tds:crypto@1.0` (experimental) | `instruments(crypto_*)`, `bars` 또는 틱, `funding_rates`(perp가 있으면) | `CRYPTO-UTC` 달력, 통화 선언 | E4 |
| `tds:fx` | `fx_rates` 또는 `instruments(fx_spot)` + bars | | |
| `tds:alt-events` | `events` 또는 `series_observations` | `ts_available` 필수(규칙 불가, 칼럼만) | 사용자 항(term) 입력 |

**가장 작은 예** (`tds:minimal-daily`, 손으로 만든 CSV 두 개 → `tds import csv`):

```
instruments.csv:  instrument_id,asset_class,market,calendar_id,currency,listed_on
                  XNYS:AAPL,equity,US,XNYS,USD,1980-12-12
bars.csv:         instrument_id,session_date,close,volume
                  XNYS:AAPL,2024-01-02,185.64,82488700
```
+ `tds import csv --profile tds:minimal-daily@1.0 --price-basis total_adjusted --market US:XNYS:USD:America/New_York`이 `tds.json`을 만든다(id는 K1 권장대로 `XNYS:AAPL_19801212` 꼴이 더 안전).

---

## 8. 적합성 검사기

### 8.1 명령

```
tds check PATH [--profile P ...] [--level manifest|schema|full] [--datasets a,b]
               [--max-errors N] [--format text|json] [--strict] [--sample-rows N]
tds hash PATH [--write]            # 파일·데이터셋·패키지 해시(물리·값·의미) 계산(--write면 tds.json 갱신)
tds manifest build PATH            # 폴더를 훑어 tds.json 초안 생성(규칙·설명은 사람이 채움)
tds describe PATH [DATASET]        # 적용 범위·칼럼·프로필 요약
tds derive fundamentals-state ...  # 5.18 참조 변환
tds import {csv|zipline|lean|nautilus|dbn|qlib|massive} ...   # 9장
tds export {zipline-bundle|nautilus-catalog|wide-parquet} ... # 9.8
```

- 종료 코드: `0` 통과, `1` 오류 있음, `2` 경고만 있고 `--strict`, `64` 사용법 오류, `66` 입력 없음, `70` 검사기 내부 오류.
- `--profile`을 주지 않으면 `tds.json`의 `profiles` 전부를 검사한다. 선언하지 않은 프로필을 주면 "이 패키지가 그 프로필을 지키나"만 본다(선언과 무관).
- 엔진은 스냅숏을 열 때 같은 검사기를 라이브러리로 부른다: 기본 `manifest`, `verify="full"`/`nexusbt doctor --full`이면 `full`(명세서 v3 4.4). 실패하면 `SnapshotError`(E14)에 TDS 코드 목록과 `producer.hints`의 문장을 싣는다.
- **명령별 상태** [v1.1, RV-I03] — 표준 문서가 광고한 명령이 실제로 있는지:

| 명령 | 상태(검사기 `nexusbt-tds` 1.0.x) |
|---|---|
| `tds check`, `tds hash`, `tds describe` | 구현(엔진 M0~M1) |
| `tds import csv`, `tds manifest build` | 구현(엔진 M1) |
| `tds export zipline-bundle` | 시험 쪽 구현(대조용, `tests/parity`), 공개 명령은 예정 |
| `tds derive fundamentals-state` | 예정(참조 변환, 5.18) |
| `tds import zipline|lean|nautilus|dbn|qlib|massive` | 예정(9장 대응표는 설계 메모; 구현되면 각 어댑터가 변환 보고서를 낸다) |
| `tds export nautilus-catalog|wide-parquet` | 예정(E4) |

### 8.2 검사 단계

| 단계 | 읽는 것 | 하는 검사 |
|---|---|---|
| `manifest` | `tds.json`, 파일 크기 | M*, 프로필 데이터셋 존재, 파일 존재·바이트 |
| `schema` | + Parquet 바닥글(footer)·통계 | S*, 파티션 경로 값, 파일 통계로 할 수 있는 범위 검사(T006 워터마크, D002 일부) |
| `full` | + 모든 행 | K*, R*, T*, D*, A*, V*, H*(sha256·값·의미 해시) |

- **세 결과** [v1.1, RV-I01]: 요약은 프로필마다 `{"declared": bool, "verified_level": "none|manifest|schema|full", "result": "pass|fail|not_checked"}`. 그 단계가 볼 수 없는 규칙(예 `manifest` 단계에서 행 규칙)은 `not_checked`이고 "pass"라고 쓰지 않는다. `unchecked` 목록에 검사하지 않은 규칙 코드를 적는다.
- 유효한 하위 프로필 패키지(더 작은 프로필만 선언하고 그것을 지킴)와 선언을 어긴 패키지는 다르다: 후자는 오류이고 소비자가 대체 동작으로 고치지 않는다. 오래된 형식 고치기는 가져오기 단계가 새 패키지를 만드는 일이다.

### 8.3 오류 코드

심각도: E = 오류(프로필 불합격), W = 경고.

| 코드 | 심각도 | 뜻 |
|---|---|---|
| TDS-M001 | E | `tds.json` 없음·읽을 수 없음·JSON 스키마 위반 |
| TDS-M002 | E | `tds_version` MAJOR를 지원하지 않음 |
| TDS-M003 | E | 필수 매니페스트 칼럼 없음 |
| TDS-M004 | E | 목록에 있는 파일이 없음 |
| TDS-M005 | W | 폴더에 있는데 목록에 없는 파일 |
| TDS-M006 | E | 파일 바이트 수 다름 |
| TDS-M007 | E | 모르는 프로필 |
| TDS-M008 | E | 프로필 필수 데이터셋 없음 |
| TDS-M009 | E | 데이터셋 `schema_version` MAJOR를 지원하지 않음 |
| TDS-M010 | E | `markets`·`id_namespaces`·`editions` 선언과 자료가 다름(선언 안 된 시장·이름공간·판 사용) |
| TDS-M011 | W | 데이터셋 `schema_version` MINOR가 검사기보다 새로움(모르는 칼럼은 무시하고 진행) |
| TDS-M012 | E | 경로가 패키지 폴더 밖을 가리킴(`..`, 절대 경로, 밖으로 나가는 심볼릭 링크) [v1.1] |
| TDS-M013 | E | 같은 파일 경로가 두 번 나옴 [v1.1] |
| TDS-M014 | E | 모르는 **필수 해석 규칙**(공개 규칙 이름, 실행에 영향이 있는 닫힌 열거의 새 값, 모르는 `hash_spec`) — 무시하면 뜻이 달라지므로 거절 [v1.1] |
| TDS-M015 | W | `experimental` 스키마 데이터셋이 있음(1.x 호환 약속 밖) [v1.1] |
| TDS-S001 | E | 필수 칼럼 없음 |
| TDS-S002 | E | 칼럼 형 다름 |
| TDS-S003 | E | null 금지 칼럼에 null |
| TDS-S004 | E | 순간 칼럼이 UTC tz가 아니거나 단위가 그 데이터셋 규정과 다름, INT96 |
| TDS-S005 | W | 모르는 칼럼(`x_` 접두 없음) |
| TDS-S006 | E | 닫힌 열거에 없는 값 |
| TDS-S007 | W | 열린 열거에 없는 값(`dictionary/codes`에도 없음) |
| TDS-S008 | E | 파티션 경로 값이 형에 안 맞거나 파일 안에 파티션 칼럼이 또 있음 |
| TDS-S009 | E | float 칼럼에 NaN·±Inf |
| TDS-S010 | E | Parquet 키-값 메타 `tds.dataset`/`tds.schema_version` 없음·다름 |
| TDS-K001 | E | 열쇠 중복 |
| TDS-K002 | E | 정렬 위반(파일 안 또는 파일 이어 붙임) |
| TDS-K003 | E | 행이 자기 파티션 범위 밖(예 year=2024 폴더에 2023 행) |
| TDS-K004 | E | 같은 파티션 파일들의 시간 범위가 겹침 |
| TDS-K010 | E | 같은 기간에 같은 기호가 두 id를 가리킴 |
| TDS-K011 | E | `session_ord`가 0부터 연속이 아님 |
| TDS-R001 | E | `instrument_id`가 `instruments`에 없음 |
| TDS-R002 | E | `calendar_id`가 `calendar_sessions`에 없음 |
| TDS-R003 | E | `session_date`가 그 종목 달력의 세션이 아님 |
| TDS-R004 | E | 통화 코드가 ISO 4217도 선언 통화도 아님 |
| TDS-R005 | W | MIC 형식(4자리 대문자·숫자) 위반 |
| TDS-R006 | E | `new_instrument_id`·`underlying_instrument_id`·`handled_by_event_id` 등 참조 대상 없음 |
| TDS-R007 | W | `selected_fact_id`·`lineage_id`를 `fundamentals_events`에서 찾을 수 없음(사건 표가 있을 때만) |
| TDS-R008 | E | `instruments.delisted_on` ≠ `delistings.exit_date` |
| TDS-R009 | E | `item`이 `dictionary/items`에 없음, 패널 칼럼이 `dictionary/columns`에 없음 |
| TDS-T001 | E | `ts_available < ts_event`(봉·사건; 규칙상 늦을 수 없는 곳) |
| TDS-T002 | E | `ts_available` 칼럼과 선언 규칙의 값이 다름 |
| TDS-T003 | E | 상태·이력 구간 겹침 |
| TDS-T004 | E | 구간 끝 ≤ 시작 |
| TDS-T005 | E | 일봉 `ts_start/ts_end`가 세션 개장·마감과 다름(값이 있을 때) |
| TDS-T006 | E | 시장 워터마크 `complete_through` 뒤의 자료 |
| TDS-T007 | E | 재무 `ts_available < period_end`(잠정치 표시 없음) |
| TDS-T008 | W | `ts_recv < ts_event − 허용치` |
| TDS-T010 | E | `last_session < listed_on` |
| TDS-T011 | W | 종료 대가 공개가 퇴출 공개보다 이름 |
| TDS-T012 | E | 두 시간축 **직사각형** 조회 결과가 한 시점·한 판별 열쇠(분류는 scheme·level·판 필터 포함)에 둘 이상 |
| TDS-D001 | E | dense 일봉에 세션 행 빠짐 |
| TDS-D002 | E | 세션이 아닌 날 행, 또는 상장 기간 밖 행 |
| TDS-D004 | E | 매니페스트 `rows`·`coverage`가 실제와 다름 |
| TDS-A001 | E | 누적 계수 비 ≠ 그 세션 사건 계수 곱(상대 1e-12; 5.11 해석 절차로 정정 사슬마다 최신판 하나, 취소 사슬은 1.0, 계수 "없음" 경계는 대조하지 않음) |
| TDS-A002 | E | 첫 세션 누적 계수 ≠ 1.0 |
| TDS-A003 | E | `price_factor ≤ 0`·null인데 `factor_method ≠ unavailable` |
| TDS-A004 | W | 현금배당 계수가 `1 − D/ref_price`와 다름(상대 1e-9) |
| TDS-A005 | E | `ex_date`가 세션이 아님 |
| TDS-A006 | E | 합병·분할설립·교환인데 `new_instrument_id`·비율 없음(현금 합병 제외) |
| TDS-A007 | E | `revision_of` 순환 |
| TDS-A008 | W | 수량을 바꾸는 사건(`affects = split_and_total`)의 조건 공개(`ts_terms_available`)가 효력(`ts_effective`) 뒤 [v1.1] |
| TDS-A010 | E | 주식 수를 바꾸는 사건(5.11)에 `ratio_num/ratio_den` 없음, 한쪽만, 0 이하, 또는 f64 비율 칼럼과 상대 1e-12 넘게 다름 [v1.2, V31-01; v1.4 W → E, R4F-01]. 소비자 설정으로 십진 리터럴을 고른 경우만 소비자가 W로 낮춤(5.11) |
| TDS-A011 | W | 마지막 거래일 뒤 배당락 현금 분배가 있는데 `delistings.ret_observed_includes_distributions`가 null [v1.2, V31-04] |
| TDS-A009 | E | `factor_method = spinoff_first_close`인데 `ts_terms_available < ts_close(효력 세션)`(신설 첫 종가 전에 계수를 알 수 없음) [v1.1] |
| TDS-V001 | E | OHLC 모순 |
| TDS-V002 | E | 음수 가격·거래량(허용 선언 없음) |
| TDS-V004 | E | `obs_status`와 가격 null이 모순 |
| TDS-V005 | E | 환율·금리 곡선 값이 0 이하(금리는 음수 허용; 환율만) |
| TDS-V010 | W | 주식 거래량이 정수가 아님 |
| TDS-V011 | W | 거래량 단위 의심: 종목·연도 중앙값 `value_traded / (volume × (H+L+C)/3)`가 [0.5, 2] 밖 [v1.2, V31-16] |
| TDS-V012 | W | 격자 정보가 있는데 원가격이 격자에서 1e-9 상대 넘게 벗어남 [v1.2, V31-05] |
| TDS-V020 | E | 자산 종류별 필수 칼럼 없음 |
| TDS-V030 | W | 교차·잠긴 BBO |
| TDS-V031 | W | 호가 재구성 뒤 교차 |
| TDS-V032 | W | 순번 빈칸 |
| TDS-V040 | E | `ret_lo > ret_hi` |
| TDS-V041 | W | `events` 행에 `instrument_id`·`issuer_id`·`series_id`가 모두 null [v1.4, R4F-EV-02] |
| TDS-V050 | E | 라벨 칼럼 이름이 특징 표에도 있음 |
| TDS-H001 | E | 파일 sha256 다름 |
| TDS-H002 | E | 데이터셋 값 해시 다름 |
| TDS-H003 | E | 패키지 물리·값·의미 해시 다름 |
| TDS-H004 | W | `files[].value_sha256`(선택)이 그 파일의 정규 값 해시와 다름 [v1.2, V31-12] |

### 8.4 출력

`--format json`은 한 줄에 하나(JSON Lines):

```json
{"code":"TDS-A001","severity":"error","dataset":"bars_1d","file":"bars/freq=1d/market=KR/year=2015/part-00000.parquet",
 "key":{"instrument_id":"KR:005930","session_date":"2015-05-08"},"count":3,
 "message":"cum_factor_split ratio 0.0200 != product of event factors 0.0201",
 "hint":"check corporate_actions event KR-CA-… (split 50:1, ex 2018-05-04)"}
```

마지막 줄은 요약 `{"summary": {"errors": n, "warnings": m, "level": "manifest", "profiles": {"tds:equity-daily-core@1.0": {"declared": true, "verified_level": "manifest", "result": "not_checked"}}, "unchecked": ["TDS-K001", …]}}`. 엔진의 `SnapshotError` 문장은 이 첫 오류 + 개수 + 힌트(`producer.hints`)를 쓴다.

### 8.5 검사기 구현 메모

- 참조 구현은 Python + pyarrow만(배포 `nexusbt-tds`, import `nexusbt_tds`; v1의 DuckDB 메모는 엔진 저장소 규칙으로 뺐다). 순수 함수로 두어 엔진과 모든 생산자가 같은 코드를 쓴다(생산자는 내보내기 직후 `full`, 엔진은 열 때 `manifest`). 값 해시는 pyarrow를 쓰지 않는 순수 Python 참조 인코더로도 교차 확인한다(4.5 시험 벡터).
- 검사 하나 = 코드 하나 = 시험 하나. 고의로 깨뜨린 작은 패키지 모음 `conformance/` (코드마다 실패 예 하나, 통과 예 하나)를 표준과 함께 배포한다.

---

## 9. 가져오기 어댑터 (다른 형식 → TDS)

공통: 어댑터는 원자료에 없는 공개 시각을 **꾸며 내지 않는다**. 기본 규칙(예 `ts_end`)을 쓰고 데이터셋 `pit_quality = backfilled`로 표시한다. 대응 표의 [손실]은 TDS로 옮길 때 잃는 것, [보충]은 사용자가 따로 줘야 하는 것. **대응표는 상호운용 보장이 아니다** [v1.1, RV-Q08]: 구현된 어댑터는 패키지 옆에 **변환 보고서** `import_report.json`(보존한 필드, 들인 가정, 버린·지원 안 한 레코드 수, 정밀도 손실, 식별자 대응, 통과한 의미 시험)을 쓴다. 원자료의 알 수 없는 사건은 `kind = other`로 보존하고(지원 안 함으로 다뤄짐) 다른 종류로 추측하지 않는다. 8.1의 명령 상태 표가 어떤 어댑터가 구현됐는지 말한다.

### 9.1 zipline 묶음 → TDS

| zipline | TDS | 메모 |
|---|---|---|
| asset DB `equities`(sid, symbol, asset_name, start_date, end_date, first_traded, auto_close_date, exchange) | `instruments`(`instrument_id = <이름공간>:<sid 또는 첫 symbol>`), `instrument_symbols`(`equity_symbol_mappings`의 기간) | sid는 `instrument_xref(id_type = zipline_sid)`로 남김 |
| `futures_contracts`, `root_symbols` | `instruments(future)` | notice_date → first_notice_date, expiration_date → ts_expiry(시각 [보충]) |
| `exchanges(exchange, canonical_name, country_code)` | `markets` + `venue_mic` | MIC 대응 [보충] |
| daily bars(bcolz, 가격 ×1000 uint32) | `bars(freq=1d)` 원가격 = 값/1000 | 0 = 결측이었으므로 null + `obs_status = missing`. 거래량 0과 결측 구분 불가 [손실] |
| minute bars(세션 사이 0 채움) | `bars(freq=1m, density=dense)` | 0 채움 행은 `no_trade` |
| `splits`(sid, effective_date, ratio) | `corporate_actions(kind = split/reverse_split, price_factor = ratio)` | zipline ratio는 **가격 배수**(2:1 분할 = 0.5; 3자 검토 중 두 검토가 관례로 확인, 왕복 시험 L3로 최종 확인). `ratio_new_per_old = 1/ratio` |
| `mergers`(sid, effective_date, ratio) | `corporate_actions(kind = other, factor_method = vendor, price_factor = ratio)` | 가격 조정일 뿐 주식 전환의 증거가 아니므로 `split`·`stock_merger`로 만들지 않는다(보유 중이면 지원 안 함) [v1.1] |
| `dividend_payouts`(ex, record, declared, pay, amount) | `corporate_actions(cash_dividend)` | 계수는 TDS 식으로 다시 계산(zipline `dividends` 표의 비율과 대조, A004) |
| `stock_dividend_payouts`(payment_sid, ratio) | `corporate_actions(stock_dividend 또는 spinoff)` | payment_sid ≠ sid면 spinoff |
| 달력 이름(`XNYS`) | `calendar_sessions`(exchange_calendars로 생성) | |
| (없음) | `ts_announced`, `ts_terms_available`, `delistings` | [손실] 공개 시각·종료 가치. `auto_close_date`는 폐지 **뒤 처리일**이라 `last_session`이 아니라 `delistings.exit_date` 쪽에 가깝다 [v1.1] |
| 가격 ×1000 uint32 범위(약 429만) | – | 넘는 종목은 반대 방향(`tds export zipline-bundle`)에서 종목별 가격 축척으로 담고 목록을 보고한다 |

### 9.2 LEAN 자료 폴더 → TDS

| LEAN | TDS | 메모 |
|---|---|---|
| `equity/usa/daily/<t>.zip`(`YYYYMMDD HH:mm`, OHLC deci-cents, volume) | `bars(freq=1d)` | ÷10,000. 시각은 data time zone 현지 → 날짜만 `session_date`로. LEAN 일봉 가격이 원가격인지(계수로 조정해 읽는지) [미확인: 원가격 저장으로 알고 있음] |
| `minute/<t>/<date>_trade.zip`(자정부터 ms) | `bars(freq=1m)`: `ts_start = 현지 자정 + ms`를 시간대로 UTC 변환, `ts_end = ts_start + 1분` | LEAN 봉 시각 = 시작 [확인]. 거래 없는 분은 행 없음 → `density = sparse` |
| `_quote.zip`(bid OHLC, bid size, ask OHLC, ask size) | `bars(price_type = bid/ask)` 두 줄 | |
| 틱 trade(시각, 가격, 수량, 거래소, 조건 hex, suspicious) | `trades`(`conditions = [hex]`, suspicious → `x_lean_suspicious`) | 가격 deci-cents → `price_exponent = -4`로 정수 그대로 |
| 틱 quote(한쪽만) | `quotes`(직전 상태로 다른 쪽 채움) | |
| `factor_files/<t>.csv`(날짜, 가격 계수, 분할 계수, 기준 가격) | 가격 계수와 분할 계수를 **따로 해독**: 분할 계수 변화 → `split/reverse_split`(`share_factor` 명시), 가격 계수만의 변화 → `cash_dividend`(기준 가격으로 `D` 역산이 맞을 때) 또는 `other`(`factor_method = vendor`), 기준 가격 → `factor_ref_price`; `bars.cum_factor_*`는 앞으로 누적으로 다시 계산 | LEAN 계수는 최근 = 1의 뒤로 누적이고 효력 날짜 관례가 다를 수 있다 — 정규화 모드 시험으로 확인 [v1.1, RV-Q08] |
| `map_files/<t>.csv`(날짜, 티커, 거래소) | `instrument_symbols`; 마지막 날짜가 과거면 `last_session`·`delistings(unknown)` — 단 티커 변경도 같은 모양이므로 `instrument_symbols`의 다음 행과 함께 판별 | 상장폐지 가치 [손실]. 지도 행의 날짜가 TDS 구간 시작인지 끝인지 관례 확인 [v1.1] |
| `market-hours-database.json` | `calendar_sessions`, `calendar_segments` | |
| 옵션 경로(style, right, strike×10,000, expiry) | `instruments(option)` | |

### 9.3 Nautilus 카탈로그 → TDS (그리고 반대)

| Nautilus | TDS |
|---|---|
| `Equity`, `FuturesContract`, `OptionContract`, `CryptoPerpetual`, `CurrencyPair` | `instruments`(asset_class별), `InstrumentId`(예 `AAPL.XNAS`) → `instrument_xref(nautilus_instrument_id)`. TDS id는 K1 문법(`이름공간:지역 id`)을 지켜야 하므로 그대로 쓸 수 없다: 권장 `XNAS:AAPL:<첫 상장일>` 또는 `NT:AAPL.XNAS` [v1.1, RV-Q08] |
| `Bar` + `BarType` | `bars`: step·aggregation → `freq`/`aggregation`, price_type → `price_type`, INTERNAL/EXTERNAL → `source_kind`; `ts_event`(닫는 시각 기본) → `ts_end`, 시간 봉만 `ts_start = ts_end − 주기`(틱·거래량 봉은 원자료에 시작이 없으면 null [보충]); `ts_init` → `ts_recv` 아님(만든 시각)이라 `x_nt_ts_init`으로 보존하고 재생 순서 규칙은 매니페스트 `params.replay_order`에 따로 선언. 가격·수량은 float를 거치지 않고 고정소수로 정확히 옮긴다; 정밀도는 Nautilus에서 **종목별**이므로 데이터셋 지수(K7)는 그 파일의 가장 작은 지수(예 −9)로 맞춰 담는다 [v1.1] |
| `QuoteTick` | `quotes`(bid_price → bid_px …) |
| `TradeTick` | `trades`(aggressor_side, trade_id 그대로) |
| `OrderBookDelta` | `book_deltas`(action, side, price, size, order_id, flags, sequence 1:1) |
| `OrderBookDepth` | `book_snapshots` |
| `InstrumentStatus` | `trading_status_events` |
| `InstrumentClose` | `market_statistics(official_close / settlement_price)` |
| `MarkPriceUpdate`, `FundingRateUpdate` | `reference_prices`, `funding_rates` |

반대 방향(`tds export nautilus-catalog`)이 E4의 기본 경로다(명세서 11.2). 가격은 `price_precision`으로 Nautilus `Price`를 만든다.

### 9.4 Databento DBN → TDS

| DBN 스키마 | TDS | 메모 |
|---|---|---|
| `definition` | `instruments` + `instrument_xref(databento_instrument_id, 하루 구간)` + `instrument_symbols(vendor:databento_raw)` | 만기·호가 단위·행사가·승수 |
| `mbo` | `book_deltas(depth_kind = mbo)` | action A/M/C/R/T/F/N → add/modify/cancel/clear/trade/fill/none; side A/B/N → ask/bid/none(**T/F의 side는 공격자 쪽**이므로 trade 행은 `trades.aggressor_side`로도 복사); F_LAST → `is_last`; F_SNAPSHOT → `is_snapshot`; 가격 1e-9 정수 그대로(`price_exponent = -9`); `INT64_MAX` → null |
| `mbp-10`, `mbp-1` | `book_snapshots` 또는 `book_deltas(mbp)` + `quotes` | |
| `tbbo`, `trades` | `trades`(+ `quotes`) | |
| `ohlcv-1s/1m/1h` | `bars`: `ts_event` = **구간 시작** [확인] → `ts_start`; `density = sparse` | |
| `ohlcv-1d` | `bars(bar_time = utc_day)` | UTC 날짜 일봉 [확인] → 세션 일봉으로 쓰지 않도록 `freq = 1d`이지만 `bar_time = utc_day`; 엔진은 세션 일봉이 필요한 기능에서 거절. 레코드·스키마 형을 보고 판단하고(세션 끝 일봉 변형이 있으면 `bar_time = session`) 날짜를 다시 이름 붙이지 않는다 [v1.1] |
| `statistics` | `market_statistics` | |
| `status` | `trading_status_events` | |
| `imbalance` | `events(event_type = auction.imbalance)` | |
| 시각 `ts_recv` | 공개 시각 규칙 `ts_recv` 또는 `ts_recv+<지연>`(게이트웨이 수신은 사용자 수신보다 이르다) | [v1.1] |
| `publisher_id`, 채널·데이터셋, 레코드 순서 | `x_dbn_publisher_id`, `x_dbn_dataset`, `x_dbn_channel_id`, 안정 정렬 순번 `sequence`(채널 범위 안에서만 유일) | 원 순서·출처를 잃지 않게 보존 [v1.1, RV-Q08] |
| uint64 `order_id` 등 | 10진 문자열 칼럼(`x_dbn_order_id`) + int64가 넘치지 않을 때만 정수 칼럼 | 부호 있는 int64로는 모든 값을 무손실로 담을 수 없음 [v1.1] |
| continuous 기호(`ES.c.0`) | `roll_calendar(roll_rule_id = "databento:c")` | 가격 조정 안 함 [확인] |

### 9.5 CSV → TDS

- 머리줄 있는 UTF-8 CSV. 칼럼 이름이 TDS 이름과 같으면 그대로, 다르면 대응 파일:

```yaml
# mapping.yaml
dataset: bars
params: {freq: 1d, price_basis: raw, density: sparse}
market: {code: KR, calendar_id: XKRX, currency: KRW, timezone: Asia/Seoul}
columns:
  instrument_id: {from: code, template: "KR:{value}"}
  session_date: {from: date, format: "%Y%m%d"}
  close: {from: 종가}
  volume: {from: 거래량}
availability: {rule: ts_end}
```

- 시각 글은 RFC 3339(`Z` 또는 오프셋 필수). 오프셋 없는 시각은 `timezone`을 지정해야 하고, 서머타임 겹침 시각은 오류(`TDS-S004`)로 거절.
- 숫자 결측은 빈칸. `NaN`, `-`, `0` 결측 표시는 대응 파일의 `missing_values`로만.

### 9.6 Qlib → TDS

`instruments/all.txt` → `instruments`(listed_on/last_session), `calendars/day.txt` → `calendar_sessions`(개장·마감 [보충]), `features/<s>/<f>.day.bin`(첫 값 = 달력 위치, float32) → `bars`(price_basis = total_adjusted가 아니라 **Qlib factor로 원가 복원**: `raw = adj / factor`), `factor` 변화 → 5.12 사건 역산. PIT `*_q.data`(date, period, value, _next) → `fundamentals_events`(`known_on = date`, period 정수 → period_end) [손실: 원 정밀도는 float32].

### 9.7 Massive(구 Polygon) 평면 파일 → TDS

`day_aggs_v1`(ticker, volume, open, close, high, low, window_start ns, transactions) → `bars(freq=1d)`: `window_start` → `session_date`(뉴욕 현지 날짜), `transactions → trade_count`, 공개 시각 규칙 `column`(파일 배포 시각 = 다음 날 11:00 ET [확인]을 칼럼으로). 티커 → id 대응은 사용자 `instrument_symbols`가 필요 [보충].

### 9.8 내보내기 (TDS → 다른 형식)

| 대상 | 쓰임 |
|---|---|
| `zipline-bundle` | **대조 시험(parity)용**: 같은 TDS 스냅숏에서 zipline 묶음을 만들어 엔진과 zipline에 같은 자료를 먹인다(명세서 8.1). uint32 밖 행 목록을 함께 낸다 |
| `nautilus-catalog` | E4 이벤트 엔진 |
| `wide-parquet` | vectorbt·pandas 사용자용 넓은 표(가격·계수 칼럼마다 한 표) |

---

## 10. 버전과 진화 규칙

### 10.1 버전 세 가지

| 대상 | 형식 | 예 |
|---|---|---|
| 표준 | `tds_version` = `MAJOR.MINOR` | `1.0` |
| 데이터셋 스키마 | 데이터셋 종류마다 `schema_version` = `MAJOR.MINOR` | `bars 1.0`, `fundamentals_state 1.1` |
| 패키지(자료) | `version` / `snapshot_id` (만든 쪽 마음, 정렬 가능한 문자열 권장) | `20261027-143144` |

표준 `1.x`는 모든 데이터셋 스키마 `1.x`를 묶는다. 데이터셋 스키마 MAJOR가 오르면 표준 MAJOR도 오른다.

### 10.2 무엇이 MINOR이고 무엇이 MAJOR인가 (읽는 쪽 기준)

| 변경 | 판 |
|---|---|
| 선택(null 허용) 칼럼 추가 | MINOR |
| 열린 열거에 값 추가 | MINOR |
| 새 데이터셋 종류, 새 프로필, 새 공개 시각 규칙 이름 | MINOR |
| 검사 경고(W) 추가 | MINOR |
| 필수 칼럼 추가, null 허용 → 금지 | MAJOR |
| 칼럼 이름·형·단위·뜻 변경, 칼럼 삭제 | MAJOR |
| 닫힌 열거에 값 추가 | MAJOR(옛 읽기가 거절하므로) |
| 열쇠·정렬·파티션 변경 | MAJOR |
| 새 오류(E) 검사 추가 | MAJOR. 단 "원래 표준 문장이 금지했는데 검사가 없었던 것"은 MINOR + 한 판 동안 W로 먼저 |
| 문장 고침(뜻 그대로) | 판 안 바꿈(문서 고침 기록만) |

### 10.3 읽는 쪽·쓰는 쪽 의무

- 읽는 쪽(엔진·검사기): 같은 MAJOR의 더 높은 MINOR 자료를 읽는다. 모르는 칼럼·데이터셋은 무시하고 M011 경고. 모르는 열린 열거값은 `other`로.
- 쓰는 쪽: 선언한 판의 필수 칼럼을 모두 쓴다. 새 MINOR 칼럼은 선택이므로 안 써도 그 MINOR라고 선언할 수 있다.
- 폐기: 칼럼을 없애려면 한 MINOR 동안 `deprecated: true`(사전·스키마 문서) → 다음 MAJOR에서 삭제.
- 표준 스키마 파일(`tds-schemas/<kind>/<MAJOR.MINOR>.json`: 칼럼·형·null·열쇠·정렬)을 기계가 읽는 원본으로 둔다. 이 문서의 표는 그 파일을 사람이 읽게 쓴 것이다(구현 때 표에서 생성).

### 10.3a 모르는 기능의 처리 (v1.1) [RV-I01]

- 같은 MAJOR의 더 높은 MINOR 패키지를 읽을 때 소비자는 **모르는 기능을 쓰는지**로 나눈다: 모르는 선택 칼럼·선택 데이터셋 → 무시(M011); 모르는 서술용 열린 열거값 → `other`; 실행·해석에 영향이 있는 것(공개 규칙 이름, 닫힌 열거의 새 값, `hash_spec`) → 거절(M014). 그래서 "모든 미래 1.x 패키지를 받는다"고 약속하지 않는다.
- **닫힌 열거에 값 추가는 MAJOR 그대로**(옛 소비자가 뜻을 모른 채 회계할 수 없으므로). 서술용 열거(`category`, `delist_type`, `reason`)는 열린 열거로 두어 MINOR로 늘린다.
- `experimental` 스키마(5.6~5.9, 5.22~5.24)는 이 호환 약속 밖이다.

### 10.4 확장과 등록

- 만든 쪽 확장: `x_<ns>_` 칼럼, `<ns>:` 접두 열거값(예 `delist_type = "ex:spac_warrant_expiry"`), `event_type`의 이름공간. 여러 만든 쪽이 같은 확장을 쓰면 다음 MINOR에서 표준으로 올린다.
- 표준 이름공간 예약: `tds`, `x`, 그리고 `KR`/`US` 같은 나라 코드는 id 이름공간으로 누구나 쓸 수 있다(패키지 안에서만 뜻이 있으므로 충돌 없음). 여러 스냅숏에 걸친 id 안정성은 같은 `id_namespaces` 설명(생산자 권한)을 가진 패키지 사이에서만 약속된다.

### 10.5 배포 상태와 1.0 졸업 조건 (v1.1) [RV-I07]

- 상태: **초안(draft)** → **후보(RC)** → **1.0**. `tds_version` 문자열은 상태와 무관하게 `"1.0"`이고(문법 `MAJOR.MINOR` 그대로), 상태는 저장소 태그(`tds-v1.0.0-rc.N`, `tds-v1.0.0`)와 문서 머리로만 표시한다.
- 초안 → RC: 검사기 `manifest`·`schema`·`full` 단계와 해시 시험 벡터가 구현되고, 합성 패키지가 모든 stable 프로필을 통과.
- RC → 1.0(모두 필요): (1) **독립 생산자** 패키지 1개(가져오기 도구 경유도 됨, 예 CSV 가져오기)가 `full` 통과, (2) 생산자 내보내기 1개(예 기준 생산자의 빌드)가 `full` 통과, (3) 소비자(엔진)가 둘을 읽어 같은 예제가 돎, (4) 값·의미 해시 시험 벡터가 두 독립 구현(pyarrow 경로와 순수 Python 참조 인코더, 또는 다른 언어)에서 일치, (5) 영어 정본 문서(공개 문서 언어 결정 뒤).
- 1.0 뒤 stable 스키마의 바뀜은 10.2 규칙을 따른다.

---

## 11. (공개판에서 뺌)

이 장은 특정 생산자의 내보내기 계획이라 표준의 규범이 아니며 공개판에 넣지 않는다. 다른 장의 참조를 지키려고 장 번호만 남긴다.

---

## 12. 엔진 명세서 4장과 맞춤 (차이 목록)

> 이 표는 TDS v1 초안이 명세서 **v1** 4장과 달랐던 점의 기록이다(명세서 v2·v3는 이것을 모두 반영했다). v1.1에서 바뀐 것은 15장.

**원칙: TDS가 4장을 대신한다.** 4장의 뜻(무엇을 담나)은 대부분 그대로이고 이름·모양이 바뀐다. 명세서 다른 장(3·5·8·10)에서 4장 이름을 쓰는 곳은 구현 때 이 표로 바꿔 읽는다. 명세서 본문 고침은 사용자 확인 뒤 한 번에.

| # | 명세서 4장 | TDS | 이유 |
|---|---|---|---|
| D1 | `security_id` | `instrument_id`(v1.1: 별칭 없음) | 자산 종류 무관 이름 (13장 Q1) |
| D2 | `*_utc` 칼럼 이름(`open_utc`, `available_at_utc`, `valid_from_utc` …) | `ts_*`(`ts_open`, `ts_available`, `ts_known_from` …) | 형이 UTC를 보장하므로 이름에서 뺌; Nautilus·Databento 관례 |
| D3 | `manifest.json`(`schema_version: "nexusbt-export/1"`) + `columns.json` | `tds.json`(`tds_version`, 데이터셋별 `schema_version`, profiles, coverage) + `dictionary/` 데이터셋 | 공개 표준, 프로필, 적용 범위 |
| D4 | 시각 단위 us 하나 | 일봉·재무 등 us(그대로), 틱·호가 ns | 틱 정밀도 |
| D5 | 파티션 `country=` | `market=`(매니페스트 `markets` 키) | 코인·선물 시장 |
| D6 | `instrument_master.parquet` | `instruments/` (+ `issuer_id`, `venue_mic`·`operating_mic`, `is_synthetic`, `index_kind`, `listed_on_censored`, `tick_size`, 파생 칼럼 이름 `ts_expiry` 등) | |
| D7 | `symbol_history.parquet`(symbol, name, valid_from, valid_to) | `instrument_symbols/`(`symbol_type`로 이름·티커·공급사 기호를 한 표에, `ts_known_from`) + 새 `instrument_xref/` | |
| D8 | `calendar_sessions`의 `rule_version`, `price_limit_pct` | 세션 표에서 뺌. 제한폭은 `tradability_daily.price_limit_ratio`, 규칙 판은 1.1 `market_rules`(Q15); `session_ord`는 선택 | 세션 표는 시간만 |
| D9 | `bars_1d` 칼럼 `shares_out`, `adj_split_cum`, `adj_total_cum`, `available_at_utc` | `shares_out` → `share_counts/`(PIT); 계수 → `cum_factor_split`, `cum_factor_total`(뜻 같음: 첫 세션 1.0, 앞으로 누적); `ts_start`/`ts_end`/`price_type`/`trade_count`/`vwap` 선택 추가; 공개 시각은 규칙 `ts_end` | 주식 수는 공개 시각이 가격과 다름. 엔진 `weight=value`는 `share_counts` 시점 조회로 시총 계산(Q4) |
| D10 | `tradability_1d` | `tradability_daily`(`price_limit_pct` → `price_limit_ratio`(0.30), `halted` → `halted_full_day` + `halt_count`, `admin_status`, `reference_price` 추가) + 새 `trading_status_events` | 비율 단위 통일, US 정지 기록 |
| D11 | `corp_actions.parquet`(`ratio`, `cash_amount`, `effective_ts_utc`, `announced_available_at_utc`, `amount_available_at_utc`) | `corporate_actions/`(`ratio_new_per_old`, `cash_per_share`, `ts_effective`, `ts_announced`, `ts_terms_available`, + `declared_date`, `share_factor`, `factor_method`, `factor_ref_price`, `subscription_price`, `gross_or_net`, `status`; kind에 `bonus_issue`, `capital_reduction`, `rights_issue`, `return_of_capital`, `mixed_merger`, `exchange_offer`, `par_change` 추가) | 권리·분할설립 자료 표현(엔진 처리는 v1 범위 그대로: 지원 안 하는 사건은 명세서 5.6.12대로 실패·정책) |
| D12 | `classif_pit`(`valid_from_utc`, `valid_to_utc`, `known_at_utc`, `edition` 칼럼) | `classifications/`(효력 `effective_from/to` date + 앎 `ts_known_from/to`, `pit_quality`; `edition` 칼럼 유지) | 두 시간축을 대칭으로 |
| D13 | `exits.parquet` | `delistings/`(`exit_available_at_utc` → `ts_exit_known`, `value_available_at_utc` → `ts_value_available`, `crsp_dlstcd_equiv` 선택 추가; 나머지 같음) | |
| D14 | `fund_state/`(`valid_from_utc`, `valid_to_utc`) + `facts_pit/` | `fundamentals_state/`(`ts_known_from`, `ts_known_to`, 나머지 같음) + `fundamentals_events/`(`ts_recorded`, `supersedes_fact_id`, `pit_quality`, `accounting_standard` 추가) | 이름; 시스템 이력 준비 |
| D15 | `benchmarks_1d.parquet` | 지수 = `instruments(asset_class=index)` + `bars` | 표 종류 줄이기 |
| D16 | `universe_1d/`(`is_investable`, `exclusion_reason`) | `eligibility_daily/`(`rule_id`, `is_eligible`, `reason`) + 새 `universe_membership/` | 규칙 여러 개, 지수 편입 |
| D17 | `fx_1d`(`observed_date`, `observed_at_utc`) | `fx_rates/`(`obs_date`, `ts_event`, `rate_kind`) | 주기 무관 |
| D18 | `panel_monthly/`, `labels_monthly/`(`month`, `lineage_flags`) | `feature_panels/name=…`, `label_panels/name=…`(`period`, 계보 칼럼은 `x_ex_*`) | 여러 패널 |
| D19 | 논리 해시 정의 | 같음 + "파티션 칼럼을 경로 값으로 포함"을 명시(v1.1: 값 해시로 다시 정의, 4.5) | 모호함 제거 |
| D20 | 파일 안에 파티션 칼럼 여부 미정 | 파일에 넣지 않음(Hive) | 3.6 |
| D21 | 4.18 검사표(`SnapshotError` E14) | 8장 검사기 단계·코드를 그대로 씀. E14 메시지에 TDS 코드 | 한 검사기 |
| D22 | `LATEST`, `PINS`, 보관 규칙 | 표준 밖(생산자 배포 관례)으로 그대로; v1.2: 스냅숏 폴더가 곧 패키지(따로 내보내기 폴더 없음) [V31-PUB-02] | |
| D23 | 4.17 엔진 자원 `kr_price_limits_v1.csv` | 그대로 엔진 자원(자료가 null일 때 대체). 1.1 `market_rules`가 생기면 자료 쪽으로 | |
| D24 | 4.19 합성 생성기 | 같은 생성기가 TDS 패키지를 쓰고 `tds check --level full`을 통과해야 함(시험 `test_synth_conforms`) | 형식 하나 |

바뀌지 않는 것: 원가격 + 사건 + 계수 정의(m_e 식), 반열림 구간, strict 판에서 compare로 채우지 않음, `known_on → 다음 세션 개장` 기본 규칙, 결측 = null, 결정적 쓰기, 시장별 완결 워터마크, 표 정렬 원칙(일봉은 날짜 먼저).

---

## 13. 열린 질문 (추천 기본값으로 일은 멈추지 않는다)

| # | 질문 | 추천 기본값 |
|---|---|---|
| Q1 | 엔진 공개 API에서도 `security_id`를 `instrument_id`로 바꿀까? | **닫힘(v1.1)**: 별칭 없이 `instrument_id` 하나(3자 검토 만장일치). 외부 이름은 가져오기 대응에서만 |
| Q2 | 틱 ns 시각을 DuckDB 기반 생산자(DuckDB 1.5.6)가 다룰 수 있나? DuckDB TIMESTAMPTZ는 us라 ns를 잘라먹을 수 있음(Nautilus 문서 경고 [확인]) | 틱 자료는 생산자 DB가 아니라 별도 수집 경로에서 pyarrow로 직접 씀. 일봉은 us라 문제 없음 |
| Q3 | 재무 공개 시각을 SEC 접수 순간으로 정밀하게 쓸까, `known_on` 다음 세션 개장으로 보수적으로 둘까? | v1은 보수적 규칙(명세서와 같음). 접수 순간은 `fundamentals_events.x_ex_ts_accepted`로 함께 내고 정책 판을 올릴 때 바꿈 |
| Q4 | `shares_out`을 봉에서 빼면 엔진 `weight=value`가 `share_counts` 조회를 새로 해야 함 | 뺀다(시점이 다름). 엔진은 `share_counts`(listed) 시점 조회 × 종가. 생산자 패널의 시가총액과 대조 시험 |
| Q5 | 표준 문서 공개와 생산자 자료 비공개의 관계 | **닫힘**: 비공개일 수 있는 것은 **자료**뿐이고, 형식 명세와 검사기 코드는 공개(Apache-2.0) |
| Q6 | 표준 이름과 스키마 URL(`nx.dev`는 자리표시) | 엔진 이름 확정(N1) 뒤(공개 저장소를 만들기 전 — 3자 검토 권고). 그때까지 `$schema`는 상대 경로 `tds/schemas/1.0/tds.schema.json`. 검사기 import 이름은 `nexusbt_tds`(`tds`는 너무 흔함) |
| Q7 | 논리 해시를 Arrow IPC 바이트로 정의하면 Arrow 판에 따라 달라질 수 있음 | **닫힘(v1.1)**: 4.5의 정규 값 직렬화(값 해시) + 해석 메타(의미 해시) + 시험 벡터로 1.0 전에 확정(3자 검토 만장일치) |
| Q8 | float64로 충분한가(미국 센트 단위 가격의 이진 오차, 한국 재무 2e15원) | 일봉·재무 float64(2^53 ≈ 9e15 > 2e15). 정확한 금액이 필요한 계좌 계산은 엔진이 통화 최소 단위 정수로 바꿈(명세서 INV-06) |
| Q9 | 파티션 칼럼을 파일에 넣지 않으면 파일 하나만 떼어 읽을 때 값이 없음 | 넣지 않는다(도구 기본과 충돌 적음). 대신 Parquet 키-값 메타 `tds.partition`에 경로 값 기록(선택) |
| Q10 | `classifications`의 판: 칼럼(`edition`)인가 파티션인가 | 칼럼(행 수가 작음). 큰 표(`fundamentals_state`, 패널)만 파티션 |
| Q11 | `eligibility_daily` 공개 시각: 그날 개장 전 정보만으로 판정 가능한가? 생산자 규칙(예 `investable-v1`)이 그날 종가·시총을 쓰면 `session_close` | 만든 쪽이 규칙을 선언. 엔진은 선언대로(종가 판정이면 그날 판단 시각 = 종가 이후에만 씀) |
| Q12 | 한국 배당락일 유도 규칙(결제 주기 변천) | 조사 후 계약으로 등록. 그때까지 `record_date`만 확실, `ex_date_method` 표시 |
| Q13 | 누적 계수를 봉 칼럼에 둘까, 별도 데이터셋으로 둘까(늦게 발견된 옛 사건이 뒤 파티션 전체를 다시 쓰게 함) | 봉 칼럼, **모든 프로필에서 선택**(v1.1). 사건이 원본이고 계수는 편의값. 별도 `adjustment_factors` 데이터셋은 다시 쓰기 비용을 잰 뒤(3자 검토 합의) |
| Q14 | TDS 핵심 재무 항목(`std_item`)의 정의 문장은 누가 쓰나 | v1.1은 "잠정 매핑" 표시(5.17). 생산자의 표준 칼럼 목록을 씨앗으로 다음 판 부록 |
| Q15 | 호가 단위·가격제한 규칙 변천을 자료(`market_rules`)로 둘까 엔진 자원으로 둘까 | **닫힘(v1.2)**: 5.27 `market_rules`(선택, stable). 자료에 있으면 자료가 엔진 자원보다 먼저 [V31-05] |
| Q16 | 3자 토의(Opus 5.5 + Fable 5.1 + GPT-6.1 Sol xhigh) 검토를 이 초안에 돌릴까 | **했다**(2026-10-28, 명세 v2와 함께; `review/`). 결과가 v1.1. TDS만 따로 한 번 더는 1.0 졸업 전 선택 |
| Q17 | 엔진 쪽 "지원 매트릭스"를 표준에 둘까 | 두지 않는다(v1.1). 표준은 적합성만 정하고, 소비자 지원은 소비자 문서(엔진 명세 4.3)가 판마다 밝힌다 |

---

## 14. 출처

이번에 열어 확인한 것 [확인]:
- zipline 묶음: https://zipline.ml4trading.io/bundles.html
- zipline 조정 기록기: https://raw.githubusercontent.com/stefan-jansen/zipline-reloaded/main/src/zipline/data/adjustments.py
- zipline 종목 DB 기록기: https://raw.githubusercontent.com/stefan-jansen/zipline-reloaded/main/src/zipline/assets/asset_writer.py
- LEAN 자료 형식 개념: https://www.quantconnect.com/docs/v2/lean-engine/data-format/key-concepts
- LEAN 미국 주식 형식: https://www.quantconnect.com/docs/v2/lean-engine/data-format/us-equity , https://raw.githubusercontent.com/QuantConnect/Lean/master/Data/equity/readme.md
- NautilusTrader 자료: https://nautilustrader.io/docs/latest/concepts/data
- NautilusTrader 카탈로그: https://nautilustrader.io/docs/latest/concepts/data/catalog/
- Databento 스키마 목록: https://databento.com/docs/schemas-and-data-formats
- Databento DBN: https://databento.com/docs/standards-and-conventions/databento-binary-encoding
- Databento 공통 필드: https://databento.com/docs/standards-and-conventions/common-fields-enums-types
- Databento 기호 체계: https://databento.com/docs/standards-and-conventions/symbology
- Databento OHLCV: https://databento.com/docs/schemas-and-data-formats/ohlcv
- Qlib 자료: https://qlib.readthedocs.io/en/latest/component/data.html
- Qlib PIT: https://qlib.readthedocs.io/en/latest/advanced/PIT.html
- Qlib dump_bin: https://raw.githubusercontent.com/microsoft/qlib/main/scripts/dump_bin.py
- hftbacktest 자료: https://hftbacktest.readthedocs.io/en/latest/data.html
- Massive 평면 파일(일봉): https://massive.com/docs/flat-files/stocks/day-aggregates.md , https://massive.com/docs/flat-files/quickstart
- Parquet 논리형: https://github.com/apache/parquet-format/blob/master/LogicalTypes.md
- Parquet 설정 권고: https://parquet.apache.org/docs/file-format/configurations/
- Frictionless Data Package v2: https://datapackage.org/standard/data-package/
- SchemaVer: https://docs.snowplow.io/docs/api-reference/iglu/common-architecture/schemaver , https://snowplow.io/blog/introducing-schemaver-for-semantic-versioning-of-schemas
- MIC (ISO 10383): https://en.wikipedia.org/wiki/Market_Identifier_Code , https://www.iso20022.org/sites/default/files/media/file/FAQ_ISO_10383_January2023.pdf
- CRSP CIZ 이전: https://wrds-www.wharton.upenn.edu/pages/data-announcements/changes-to-crsp-data , https://www.crsp.org/crsp_pdf/crsp-us-stock-indexes-databases-fiz-to-ciz-executive-summary
- CCM 연결(2차 자료): https://docs.nuvolos.cloud/user-guides/data-guides/working-with-crsp-and-compustat , https://crsp.org/crsp_pdf/january-2009-monthly-release-notes-1-2
- Sharadar 차원(2차 자료): https://www.quantrocket.com/codeload/fundamental-factors/fundamental_factors/Lesson03-Basic-Usage.ipynb.html
- OpenFIGI 단계(2차 자료): https://docs.cybersyn.com/free-public-data-products/sec-filings/data-dictionary/openfigi-security-index , https://openfigi.com/about/features

열지 않았거나 원문 확인이 남은 것 [미확인]:
- vectorbt: https://vectorbt.dev/ (엔진 조사 문서 출처)
- backtrader 피드: https://www.backtrader.com/docu/datafeed/
- ArcticDB: https://github.com/man-group/ArcticDB
- kdb+/tick: https://code.kx.com/q/kb/kdb-tick/
- LEAN 계수·맵 파일 칼럼, 최신 형식
- FIGI 문자 구조: https://www.openfigi.com/about/figi
- ISIN ISO 6166, ISO 4217 보조 단위 표, XKRX·XNYS·XKOS 목록 대조: https://www.iso20022.org/market-identifier-codes
- Arrow 스키마의 tz 의미: https://github.com/apache/arrow/blob/main/format/Schema.fbs
- Avro 스키마 해석 / Confluent 호환 규칙: https://avro.apache.org/docs/ , https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html
- Frictionless Data Resource의 `hash` 문법: https://datapackage.org/standard/data-resource/
- CRSP 상장폐지 코드표, CIZ 필드 이름
- FRED H.10 발표 일정, 한국 배당락·결제 주기 변천, 한국 거래시간 연장 시행일

로컬 근거:
- 엔진 명세서 `engine-spec-v1-2026-10-27.md` 1·4·5·10·11장, 설계 문서 `engine-design-2026-10-27.md` 4.2·4.3·9.0·11.5

## 15. v1 → v1.1 변경 요약 (3자 검토 반영, 2026-10-28)

`tds_version`은 `"1.0"` 그대로다(아직 초안이라 호환 약속 전; 아래는 1.0 졸업 전에 정의를 바로잡은 것). 근거 번호는 `review/consensus.md`.

| 영역 | v1 | v1.1 | 근거 |
|---|---|---|---|
| 해시 | 논리 해시 = Arrow IPC 바이트(판·구현에 따라 다름) | 물리·값(언어 무관 정규 직렬화, `hash_spec = tds-hash-1`)·의미(값 + 해석 메타) 셋, 시험 벡터 공개 | C10a, Q7 |
| 두 시간축 | 분류 열쇠에 `level` 없음, 기호 표에 `ts_known_to` 없음, 조회 방법 모호 | 분류 열쇠 `(instrument_id, scheme, level, edition, effective_from, ts_known_from)`, `level` null 금지, `instrument_symbols.ts_known_to`, 직사각형 조회와 예시 5개, `instrument_xref`는 두 시간축 약속 밖으로 명시 | C08 |
| strict 품질 | K6 "넣지 않음" vs 6.5 "경고" 모순 | 행 단위 backfilled는 strict 조회에서 제외, 데이터셋 단위는 경고 | C09 |
| 자격 | 기본 `session_open`, 결측 의미 모호(소비자 이월 가능) | 기본 `session_close`, 그 세션 행 없음·미공개 = 대상 아님, 이월 없음 | C09 |
| 기업행동 | 해석 절차 없음, `share_factor` 기본 = 1/price_factor, `ts_amount_available` 오기 | 해석 절차(5.11: 사슬·기준 시각의 판·상태·네 효과·정정), `share_factor`는 분할류 밖에서 추론 금지, `ts_terms_available` 통일, A008·A009 | C03, Q03 |
| 폐지 | `ts_exit_known` 필수 | null 허용(backfilled), `ts_value_available` 전에는 회수액을 판단에 쓰지 않는다는 소비자 문장 | Q09, C01 |
| 정답 표 | 시각 칼럼 없음 | 선택 `ts_label_start/end/available`, `return_definition` 예 | C04 |
| 프로필 | 판 없음, "pass" 하나, `minimal-daily`에 종가 백테스트 약속, research에 `cum_factor_*` 필수 | `@1.0` 판, 세 결과(선언·검사 단계·결과, `not_checked`), `minimal-daily`는 분석만, `cum_factor_*`는 모든 프로필에서 선택, 엔진 지원 매트릭스는 표준 밖 | I01, I03 |
| 호환 | 모르는 열거값은 `other`, 모든 MINOR를 읽음 | 모르는 필수 해석 규칙·닫힌 열거 새 값은 거절(M014), 서술용만 `other`, experimental 스키마는 약속 밖 | I01, Q11 |
| 매니페스트 | `$schema` = 소유하지 않은 도메인, 생산자 힌트 없음, 경로 안전 없음 | 상대 경로 `$schema`, `producer.hints`, 경로 안전(M012·M013), 프로필 판 | Q04, I09, I01 |
| 실험 판 | 틱·호가·선물·옵션·코인이 1.0 안 | `experimental`(M015 경고), 일봉 주식만 stable | I07 |
| 재무 | `preliminary`가 열거에 없음(T007과 모순), `std_item`이 정의 없이 표준처럼 | `preliminary` 추가·T007 경고로, `std_item`은 잠정 매핑 | I06 |
| 상호운용 | 대응표만 | 변환 보고서, zipline `mergers`를 전환으로 보지 않음, LEAN 계수 성분 해독, Nautilus id 문법·정밀도, DBN 게시자·채널·uint64, `ts_recv+<기간>` | Q08 |
| 식별자 | 작은 사용자 `<MIC>:<티커>` 권장, `security_id` 별칭 가능 | `<MIC>:<티커>:<첫 상장일>` 또는 FIGI, 별칭 없음 | Q04, Q01 |
| 배포 | 1.0 선언 | 초안 → RC → 1.0, 졸업 조건 10.5 | I07 |
| 공개판 | 생산자 대응 장(11장) 포함 | 11장은 공개판에서 뺌, 검사기 import `nexusbt_tds` | Q04 |

---

## 16. v1.1 → v1.2 변경 요약 (시중 엔진 해부 반영, 2026-10-28)

근거 번호는 `teardown/MATRIX.md`의 `V31-NN`(명세 v3.1과 같은 번호). **`tds_version`은 `"1.0"` 그대로다.** 이유: 바뀐 것은 모두 (1) 선택(null 허용) 칼럼 추가, (2) 선택 데이터셋 추가, (3) 경고(W) 검사 추가, (4) 매니페스트 선택 필드 추가뿐이다 — 10.2 표에서 모두 MINOR이고, 아직 초안이라 호환 약속 전이다. 옛(v1.1 모양) 패키지는 그대로 유효하고, 새 칼럼을 모르는 v1.1 검사기도 v1.2 패키지를 읽는다(M011 경고). 오류(E) 검사는 하나도 더하지 않았다(H004도 W로 시작, 10.2 "한 판 동안 W" 규칙).

| 영역 | v1.1 | v1.2 | 근거 |
|---|---|---|---|
| 기업행동 비율 | f64 `ratio_new_per_old`·`share_factor`만(1:3, 0.29가 2진 소수로 정확하지 않아 소비자가 한 주를 잃음) | 선택 `ratio_num`, `ratio_den`(정수, 정본), 검사 A010(W) | V31-01 |
| 폐지 | `ret_observed`가 마지막 거래일 뒤 분배를 담는지 모름(두 번 셈 위험, LEAN#9819) | 선택 `ret_observed_includes_distributions`, 검사 A011(W) | V31-04 |
| 거래량 단위 | "원 거래량(주)" 문장만, 검사는 정수 여부(V010)뿐 | 묶음 단위 금지 문장 + V011(W: 거래대금/(거래량 × 대표가) 중앙값이 [0.5, 2] 밖; qlib#2362) | V31-16 |
| 가격 격자 | `tick_rule_id`가 가리킬 `market_rules`가 없음(Q15 열림) | 5.27 `market_rules`(선택, stable), 격자 규범과 V012(W) | V31-05 |
| 해시 | 데이터셋·패키지 값 해시만 | 선택 `files[].value_sha256`(파일 단위 정규 값 해시, 소비자 증분 캐시용), H004(W) | V31-12 |
| 지수 | `index_kind`만 | 선택 `instruments.index_weighting`(가중 방식 표시) | V31-15 |
| 생산자 | 내보내기 층 전제(`export/<id>/`) | 생산자 빌드가 패키지를 직접 써도 됨, 스냅숏 폴더마다 불변, 하드 링크·내용 주소 파티션 허용(해시가 내용을 정함), 소비자는 쓰기 권한 요구 안 함 | V31-PUB-01 |
| 공매도 | – | 데이터 바꿈 없음. 금지 기간은 엔진 규칙 팩, 대차 자료는 다음 MINOR 후보(5.27 끝) | V31-LS-07 |

## 17. v1.2 → v1.3 변경 요약 (3자 검토 3라운드 반영, 2026-10-28)

근거 번호는 `review/consensus-r3.md`의 `R3-NN`(명세 v3.2와 같은 번호). **`tds_version`은 `"1.0"` 그대로다.** 이유: 바뀐 것은 (1) 소비자가 기존 칼럼을 해석하는 문장의 고침(5.11 판 고르기, 5.13 종료가치 기준, 5.27 비교 좌표) — 생산자가 쓰는 칼럼·형·필수 여부는 그대로이고, v1.2 문장은 자기 모순(5.11의 대기 상태에 닿을 수 없음, 5.13이 분배를 두 번 줄임)이라 고침이 곧 원래 뜻이다, (2) 권고·SHOULD(복제 우선, 읽기 전용, 원자 게시, 파일 신원, `value_sha256` 조언용, 워터마크를 캐시 열쇠에서 빼기), (3) 예시 고침(K1)뿐이다. MUST는 이미 있던 "게시 파일을 제자리에서 고치지 않음"을 분명히 했을 뿐이다. 검사 코드는 더하거나 심각도를 바꾸지 않았다(A010은 W 그대로; 소비자 거절은 허용으로 적음). 아직 초안이라 호환 약속 전이고, 옛 패키지는 그대로 유효하다.

| 영역 | v1.2 | v1.3 | 근거 |
|---|---|---|---|
| 기업행동 판 고르기 | `ts_pub = coalesce(terms, announced, effective)` — 조건이 늦은 판이 통째로 숨음 | 존재 시각 `ts_known`으로 고르고 조건 시각 `ts_terms`로 대기, 권리 수량은 효력 세션 보유로 고정 | R3-01 |
| 종료가치 | 포함 거짓 → "분배만큼 계수를 곱한 기준" | 관측(포함·제외)은 `ref_units`, 정책은 분배 뒤 기준; 포함이면 이미 기입한 분배를 뺌; `ret_hi`는 상한 아님 | R3-05, R3-09 |
| 가격 비교 | 격자 정수(틱 수) | 시장 최소 단위 정수 한 좌표, 격자 밖 관측 가격은 옮기지 않음 | R3-02 |
| 정확 비율 | A010(W) | A010 그대로(W), 소비자가 잘못된 정본을 거절해도 됨, f64 추론은 기록 | R3-06 |
| 패키지 불변성 | 하드 링크·내용 주소 허용, 제자리 수정 금지 문장 | 복제 우선·하드 링크 대체, 게시 = 준비 → 검사 → 원자 교체, 읽기 전용(SHOULD), 공유 파일 대조, 소비자 파일 신원(권고), DuckLake 이유 고침 | R3-16 |
| 해시·캐시 | `files[].value_sha256`은 증분 캐시 열쇠용 | 조언용 — 캐시 신원은 파일 sha256, 워터마크는 열쇠에서 빼기를 권고 | R3-04 |
| K1 예시 | `XNAS:AAPL:19801212`(자기 정규식 위반) | `XNAS:AAPL_19801212` | R3-28 |

## 18. v1.3 → v1.4 변경 요약 (3자 검토 4라운드 + 사용자 결정, 2026-10-28)

근거 번호는 명세 v3.4의 `R4F-NN`(부록 I). **`tds_version`은 `"1.0"` 그대로다.** 이유: 표준이 아직 초안이라 호환 약속 전이고(10.5), 기준 생산자는 이미 `tds.corporate_actions`에 `ratio_num/ratio_den`을 쓴다. 1.0 확정 뒤라면 선택 → 필수는 MAJOR다(10.2).

| 영역 | v1.3 | v1.4 | 근거 |
|---|---|---|---|
| 정확 비율 | 선택 칼럼, A010(W), 소비자 f64 추론은 기록하면 허용 | 주식 수를 바꾸는 사건에 **필수**, A010(E); f64 추론 금지; 사용자 설정의 십진 리터럴만 예외(경고·건수) | R4F-01 (사용자 결정 2026-10-28) |
| 폐지 분배 포함 여부 null | 거짓으로 봄 + 경고 | 두 해석 가운데 총 회수액이 작은 쪽 + 경고(두 번 세지 않음) | R4F-05 |
| `events` | 종목·발행사 사건만 | 선택 `series_id`(시장 수준 사건), `consensus`, `ts_available` 필수 문장, 정정 = 새 id, 검사 V041(W) | R4F-EV-02 |
| `series_observations` | 판 칼럼 | 선택 `consensus`·`frequency`, 첫 발표 판 정의, 발표 시각 ≠ 관측 기간 끝 문장 | R4F-EV-01 |

---

## 갱신 기록
- 2026-10-27: 초안 작성(조사 + TDS v1 + 생산자 대응 + 명세서 4장 차이).
- 2026-10-28: **v1.1**. 3자 검토 합의 반영(15장).
- 2026-10-28: **v1.2**. 시중 엔진 해부 반영(16장, `[V31-NN]`): 선택 칼럼 `ratio_num/ratio_den`·`ret_observed_includes_distributions`·`index_weighting`·`files[].value_sha256`, 선택 데이터셋 `market_rules`(5.27), 경고 A010·A011·V011·V012·H004. `tds_version` `"1.0"` 그대로(MINOR 성격 + 초안). 표준 판 문자열은 `"1.0"` 유지, 상태 = 초안.
- 2026-10-28: **v1.4**. 3자 검토 4라운드 + 사용자 결정 반영(18장, `[R4F-NN]`): 주식 수를 바꾸는 기업행동의 `ratio_num/ratio_den` 필수·A010 E·f64 추론 금지(십진 리터럴은 사용자 설정만), 폐지 분배 포함 여부 null = 작은 쪽. `tds_version` `"1.0"` 그대로(초안).
- 2026-10-28: **v1.3**. 3자 검토 3라운드 반영(17장, `[R3-NN]`): 5.11 존재/조건 시각 분리, 5.13 종료가치 기준 고침, 5.27 최소 단위 정수 비교, 4.1 복제 우선·원자 게시·읽기 전용·파일 신원, 4.2 `value_sha256` 조언용·워터마크, A010 소비자 거절 허용, K1 예시. `tds_version` `"1.0"` 그대로(해석 문장 고침·권고·예시뿐, 초안).
