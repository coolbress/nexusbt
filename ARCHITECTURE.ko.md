# 구조 (Architecture)

**Event-driven where it matters, vectorized where it scales. You just snap the blocks together.**
(매매는 이벤트처럼 정확하게, 계산은 벡터처럼 빠르게. 사용자는 블록만 끼운다.)

이 문서는 NexusBT의 큰 구조를 설명한다. 코드에서 길을 찾고, 어디서나 지켜지는 규칙을 알기 위해 읽는다. 이 문서는 지도이고 규칙은 아니다. 규칙은 [엔진 명세](docs/spec/engine-spec-v3.4.md)(영어, 유일한 정본; 한국어 번역 [engine-spec-v3.4.ko.md](docs/spec/engine-spec-v3.4.ko.md))에 있다. 아래 절 번호(§)는 명세를 가리킨다. 영어 정본: [ARCHITECTURE.md](ARCHITECTURE.md).

> 상태: 설계는 끝났고 코드는 아직 없다. 여기 나오는 패키지·모듈은 모두 **예정**이다(명세 §2.3, 티켓 T0.2a).

## 한눈에 보기

NexusBT는 일봉 주식 팩터 연구를 위한 백테스트·스크리닝 엔진이다. [TDS](docs/tds/tds-v1.4.md) 패키지(Parquet 파일 + `tds.json` 목록)를 경로로 읽고, 전 종목 × 전 날짜의 팩터를 한 번에 계산하고, 아홉 칸 전략 블록으로 점수를 목표 비중으로 바꾼 다음, 계좌를 거래일마다 사건 순서대로 시뮬레이션한다: 주문, 체결, 비용, 세금, 기업행동, 배당, 상장폐지, 공매도, 환율. 같은 전략 파일 하나로 팩터 평가, 백테스트, 오늘의 스크린, 모의 장부가 나온다. 검증(walk-forward, CPCV, CSCV/PBO, DSR)은 엔진 안에서 입구 하나 `backtest(method=…)`로 돈다.

설계의 핵심은 이 나눔이다. 무겁고 병렬로 나누기 쉬운 부분(패널 위의 항)은 벡터로 계산하고, 순서가 중요한 부분(계좌)은 이벤트 방식이되 한 세션 안의 전 종목은 배열로 처리한다. 사용자는 블록이 어느 쪽에서 도는지 몰라도 된다(§0).

```
 스냅숏 경로 (TDS 패키지)
        │  열기 + 검사 (nexusbt_tds), 능력 판정, 대체 동작                 data
        ▼
 시장 블록 · 구간 조회 (PIT) · 달력 · 환율 · 해석된 기업행동
        │  L0 캐시: 시장 × 칼럼 × 연도, Arrow IPC
        ▼
 Pipeline 그래프: 팩터 · 필터 · 분류자                                 pipeline / compute
        │  계획 → 벡터 커널 (numpy / Numba) → L1 항 캐시
        ▼
 아홉 칸: 일정 · 유니버스 · 신호 · 구성 ·                               portfolio / risk / ml
          자금 관리 · 위험 관리 · (집행 · 탈출 · 비용)
        │  정규 목표 (TargetFrame) → 계좌 층 → 최종 목표
        ▼
 일간 상태 기계, 세션마다, 전 종목은 배열로:                             execution / accounting
   기업행동 → 주문 → 체결 → 비용·세금 → 평가 → NAV 다리
        │  사건 (orders, account_events) 이 정본
        ▼
 실행 폴더: Parquet 표 + 매니페스트 + 해시 · 보고서 · 스크린 · 모의 장부   artifacts / api
 (결과 표는 Arrow PyCapsule 인터페이스로 내보냄)
```

## 층

- **자료** (§4, §5.1, §5.3.3a, §5.3.6). `open_snapshot`은 선언된 단계로 TDS 검사기를 돌리고, 그래프가 쓰는 능력을 계산하고, 정해진 대체 동작(알리고 기록, §4.5)을 적용하고, 직사각형 시점 정확 구간 조회를 준다. 원 시장 블록은 압축 없는 Arrow IPC 파일로 캐시한다(L0, §5.3.9). 기업행동 해석기 하나가 조정과 회계 양쪽에 쓰인다.
- **Pipeline** (§3.3–3.6, §5.3). 항은 해시가 있는 값 객체이고, `pipeline`은 자료를 읽지 않는다. `compute`가 그래프를 계획하고, 필요한 칼럼·날짜·판단 행만 계산하며, 등록 커널을 Python + numpy/Numba로 돌린다. 뜨거운 커널은 배열 입력 → 배열 출력의 좁은 이음새(`compute._kernels`, `execution._step`, `accounting._state`) 뒤에 있고, Rust 빌드는 비트 단위로 같을 때만 바꿔 끼울 수 있다(§2.4, ADR-0016).
- **판단과 블록** (§3.7, §5.5). `Strategy`는 아홉 칸이다: 일정, 유니버스, 신호, 구성, 자금 관리, 위험 관리, 집행, 탈출, 비용. 점수는 구성 → 자금 관리 → 위험 관리를 거쳐 정규 `TargetFrame`이 되고, 계좌를 읽는 위험 규칙은 마지막 계좌 층에서만 돈다(§5.5.2a). 내 팩터·자금 관리·위험 규칙은 장식자 붙은 함수 하나다. `nx.ml.factor`는 엔진 안에서 앞쪽으로만 학습한다(§5.3.11).
- **집행과 회계** (§5.6). 슬리브마다 일간 상태 기계: 다음 세션 체결, 일봉 안 순서를 모르면 불리한 쪽, 거래량 상한, 상·하한가, 정지, 호가 격자(§5.6.4a), 현금 차감인 비용, 분할·배당, 합병, 상장폐지, 부호 있는 롱·숏(기본 꺼짐), 현금·증거금 계좌(§5.6.7a). 돈은 정수 최소 단위이고 매일 NAV·손익 다리를 닫는다.
- **연구** (§5.7, §5.8, §6). `evaluate`(IC, 분위, 회전율, 커버리지, BHY), 정화와 모든 접힘의 실제 체결이 있는 `backtest(method="linear" | "walk_forward" | "cpcv" | "cscv")`(§6.3a), 미래 잠금 없는 구간 나누기(§6.1), PSR/DSR/PBO가 붙는 시도 기록(§6.2–6.3), 미래 정보 탐침(§6.5).
- **출력** (§3.9, §5.9). 실행마다 트랜잭션으로 봉인된 실행 폴더를 쓴다(Parquet 표, `manifest.json`, 잡은 소스, 해시 셋, SQLite 색인). 파생 표(`positions`, `daily`, `metrics`, `attribution`, `exposures`)는 사건에서 다시 만든다. 결과 표는 `__arrow_c_stream__`을 구현하고, 정적 HTML 보고서·스크린·모의 장부가 같은 기록에서 나온다.

## 코드 지도 (예정)

저장소는 배포물이 둘인 uv workspace다: 엔진 `nexusbt`(`import nexusbt as nx`)과 자료 표준 검사기 `nexusbt-tds`(`import nexusbt_tds`, CLI `tds`). 구조는 §2.3, 공개 인터페이스는 §2.4, import 규칙은 §2.5.

| 경로 | 들어 있는 것 |
|---|---|
| `tds/` | 따로 판을 매기는 TDS 표준: `spec/tds-v1.md`, `schemas/`, `conformance/`, `src/nexusbt_tds/`(check, hash, manifest, describe, import_csv). pyarrow만 의존, `nexusbt`를 import하지 않음. |
| `src/nexusbt/contracts/` | ID 상수, 엔진 칼럼 집합, 단위, 정책, 오류 계층(§6.6). 의존 없음. |
| `src/nexusbt/config/` | `nexusbt.toml` 읽기·검증(§3.11), 비밀 키 거절. |
| `src/nexusbt/data/` | 스냅숏 열기(검사기 호출), 능력·대체 동작, 시장 블록, L0 캐시, 구간 조회, 달력, 환율, 기업행동 해석기. |
| `src/nexusbt/pipeline/` | 항, 데이터셋, 연산자, 내장 팩터, `Pipeline`, 그래프 해시, 정적 검사. |
| `src/nexusbt/compute/` | 계획, 참조 커널, 빠른 커널, 조정, 단면, L1 캐시, 실행기. |
| `src/nexusbt/portfolio/` | 점수 → 정규 목표(구성 → 자금 관리 → 위험 관리)와 계좌 층. |
| `src/nexusbt/risk/` | 자금 관리 `size.*`, 위험 규칙 `risk.*`. |
| `src/nexusbt/ml/` | `ml.factor` 학습 노드, 학습 창, `fits`·`predictions` 기록. sklearn을 import하지 않음. |
| `src/nexusbt/execution/` | 열 배열 주문 표, 체결 모형, 비용, 주식 수 정하기, 일간 상태 기계, 프리셋. |
| `src/nexusbt/accounting/` | 열 배열 계좌 상태, 정수 최소 단위 기입, 권리, 종료 가치, 평가, NAV 다리. |
| `src/nexusbt/research/` | 정답, IC·분위, 통계(NW, PSR, DSR, PBO, MinTRL, BHY, Lo), 구간, 분할기·검증 방법, 시도 기록, 탐침. |
| `src/nexusbt/artifacts/` | 실행 트랜잭션, 매니페스트, 해시, SQLite 색인, 소스 잡기, 모의 장부, 대조, 귀속, 보고서. |
| `src/nexusbt/api/`, `cli/` | `evaluate`, `backtest`, `screen`, `live`, `reconcile`, `sweep`, `compare`, `explain`, `check`, …; CLI는 `api` 위의 얇은 argparse 층. |
| `src/nexusbt/compat/` | `zipline.py`(zipline 이름, zipline import 없음), `adapters.py`(pyfolio·alphalens 모양, pandas 선택). |
| `src/nexusbt/bridge/` | 나중 장중 작업용 이벤트 엔진 경계: Protocol과 자료형만(§11). |
| `src/nexusbt/testing/` | 합성 TDS 패키지 생성기(§4.8)와 손계산 도우미. |
| `src/nexusbt/resources/` | 시장 규칙 팩 `markets/{KR,US,_generic}.toml`, 비용·가격 제한·호가·공매도 금지 표(§4.7). |
| `tests/` | `unit/`, `property/`, `golden/`(구현 PR이 고칠 수 없는 기대값), `docs/`, `perf/`, `repo/`, `parity/`(격리된 zipline-reloaded 3.2.1 환경). |
| `bench/` | 측정 스크립트와 요약 JSON. |

의존 방향(AST 시험으로 강제): `contracts ← config ← data ← compute ← api ← cli`, `contracts ← pipeline ← compute`, `contracts ← risk ← portfolio ← api`, `contracts ← accounting ← execution ← api`, `contracts ← research ← api`, `contracts ← artifacts ← api`, `nexusbt_tds ← data`. 모듈을 조합하는 것은 `api`뿐이다.

## 불변식

모두 모든 마일스톤에서 시험한다(§1.3). 구조를 가장 많이 정하는 것:

- **시점 정확** (INV-01, INV-02): 판단은 `ts_available <= decision_ts`인 관측만 쓴다. 주문 크기를 정하는 계좌 입력도 같다. 뒤 자료를 더해도 앞 목표는 바뀌지 않는다.
- **결정성** (INV-03, INV-04, INV-09, INV-13): 같은 고정 환경·입력이면 묶음, 색인 순서, 프로세스, `PYTHONHASHSEED`와 무관하게 Parquet 바이트가 같다. 줄이기는 고정된 합 순서, BLAS·`fastmath` 없음.
- **캐시는 보이지 않음** (INV-05): 캐시 적중과 미적중의 결과가 비트 단위로 같다.
- **screen = backtest** (INV-08): 같은 전략·스냅숏·정책·기준점·문맥이면 같은 정규 목표. 목표는 계좌 상태를 읽지 않는다.
- **숨은 대체 없음** (INV-12): 결측은 퍼지고, 채우기는 명시적 연산뿐이며, 자료 대체 동작은 알리고 기록한다.
- **정수 돈과 주식 수** (INV-06, INV-18): 돈은 int64 최소 단위이고 NAV 다리는 매일 0 차이로 닫힌다. 주식 수는 정수 산술이고 `requested = filled + cancelled + remaining`.
- **정확 비율, 기본 `exclude_instrument`** (INV-18, §5.6.1, §3.11): 주식 수를 바꾸는 기업행동은 정확한 정수 비율이 필요하다. 비율이 정확하지 않은 종목은 사건이 보이는 때부터 뺀다(`[corporate_actions] decimal_ratio = "exclude_instrument"`). 실수에서 추정하지 않는다.
- **사건이 정본** (INV-16): 모든 파생 표는 `orders`와 `account_events`에서 다시 만들 수 있다.
- **꺼진 스위치 = 기준선** (INV-22, INV-23): 공매도 꺼짐은 롱 전용과 비트 단위로 같고, 계좌를 읽는 위험 규칙이 없으면 최종 목표 = 정규 목표.

## 여러 곳에 걸친 관심사

- **가르치는 오류** (§6.6): 모든 오류는 무엇이·어디서·왜·어떻게 고치나와 층(자료, 내 코드, 설정, 엔진 버그)을 말한다. 오류 코드 E1–E49.
- **연구 위생** (§6): 시도 수, 사전 등록, 계산 전에 막는 미래 정보.
- **보안과 공개 위생** (§2.6, §2.7): 어디서도 pickle 없음(Parquet, Arrow IPC, JSON만), 설정에 비밀 없음, 저장소 위생 시험이 비공개 자료를 막는다.
- **시장 규칙은 팩에서** (§4.7, ADR-0029, ADR-0035): 시장 이름은 자료에서, 호가 격자·가격 제한·반올림·공매도 금지는 판이 있는 규칙 팩에서 온다.
- **시험** (§8): 손계산 정답, 성질·변형 시험, 미래 정보 시험, TDS 적합성, 좁힌 zipline 대조 묶음(ADR-0021). 측정한 시제품 근거: [docs/design/prototype-results.md](docs/design/prototype-results.md).
- **성능** (§7): 작업 부하별 예산. v1 병렬은 프로세스(ADR-0040).

## 명세에서 찾을 곳

| 영역 | 명세 절 |
|---|---|
| 범위, 용어, 불변식 | §1.1–1.3 (용어는 [GLOSSARY.ko.md](GLOSSARY.ko.md)에도) |
| 패키지, 인터페이스, import 규칙, 보안 | §2.3–2.7 |
| 공개 API, 전략 칸, 결과, CLI, 설정 | §3.1–3.11 |
| 입력 자료(TDS), 대체 동작, 규칙 팩, 합성 자료 | §4 |
| 시간과 쓸 수 있음, Pipeline 계산, 캐시, 결정성 | §5.1–5.4 |
| 목표, 자금 관리, 위험 관리, 완충대 | §5.5 |
| 일간 상태 기계, 체결, 비용, 기업행동, 증거금 | §5.6 |
| 지표, evaluate, 실행 기록, 모의 장부 | §5.7–5.9 |
| 연구 위생, 검증 방법, 오류 | §6 |
| 성능, 시험 | §7, §8 |
| 마일스톤과 티켓 | §10과 [SPEC-INDEX.md](SPEC-INDEX.md) |
| 확장 지점 | §11 |
| 결정 | [docs/adr/](docs/adr/) (짧은 형태는 §9.3) |

## v1에 넣지 않는 것 (일부러)

§1.1과 §12.1에서. 각각의 목표 판은 거기에 있다.

- 장중·틱·호가 자료, 코인, 선물, 옵션 (E4/E5; §11에는 경계만).
- 엔진 쪽 자료 넣기 단계, DuckDB 직접 읽기, zipline/LEAN/Nautilus/DBN 가져오기 (v1.x).
- `engine="auto"` 전환과 zipline 포크. zipline은 대조 기준일 뿐.
- 증권사 주문 전송, 실거래 보정 비용(TCA).
- 패널 방식 사용자 함수, 기간 창("30d"), 상관·회귀·`Beta`·`Illiquidity` 내장 팩터, 더 많은 시계열 커널.
- `size.kelly`, ERC `fallback="fail"`, 양쪽 ML 학습.
- 사기·들고 있기·팔기 비대칭(`min_hold`, `cooldown`, `max_replace`), 비중 이탈 리밸런싱, 전략 묶기, 나눠 파는 이익실현.
- VWAP 체결, T+n 결제 달력, 증권사 가산 증거금, 포트폴리오 마진, 장중 마진 콜.
- 부트스트랩 Sharpe 구간, 무작위 귀무 대조, sweep 지형도.
- Brinson·요인 귀속.
- 웹 서버, 로그인, 작업 큐, 브라우저 편집기.
- 실데이터 검증을 통과하기 전의 PyPI 게시.
