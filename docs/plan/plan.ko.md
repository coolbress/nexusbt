## 10. 마일스톤과 티켓

### 10.0 마일스톤 표 [Codex 11.8, 설계 6, R-44]

v3는 3자 검토 합의대로 **M0을 계약만으로 줄이고**, 검사기 full 단계·합성 small/full·손계산은 그것을 쓰는 마일스톤 **바로 앞**으로 옮겼다. M3은 **M3a(시장가 끝-끝 얇은 조각)** 와 **M3b(9.0의 주문 종류 전부)** 로 나눴다. 출시 정의는 9.0 그대로(M6 끝, 모든 주문 종류). 성능 측정 장치는 M1로 당겼다. "사용자가 바로 쓰는 것" 칸은 마일스톤마다의 조기 사용 경로다; 최종 v1 범위는 9.0의 출시와 M6 뒤의 출시 관문(OI-46)이고, 한 마일스톤의 조기 사용이 그 일부를 앞당겨 약속하지 않는다(설계 검수 D15, 2026-11-04).

**M1b, 팩터 평가 앞의 얇은 백테스트**(소유자, 2026-11-28, #858; 첫 끝-끝 실행을 M3a에 둔 #43의 2026-11-04 결정을 대신한다): M1과 M2 사이의 M1b가 처음부터 끝까지 도는 백테스트를 만들고, 뒤의 마일스톤이 한 조각씩 더한다. 이 때문에 나뉜 티켓은 남는 반쪽이 원래 id를 지키고 M1b의 반쪽이 새 글자를 받는다; 아래 v3.1~v3.4 문단이 M3a에 준 끝 조건 가운데 옮겨 간 부분의 것은 M1b의 것이다.

| M | 단계(E) | 사용자가 바로 쓰는 것 [R-44] | 끝 조건 (모두 필요) | 보여 줄 명령 (`/run`) |
|---|---|---|---|---|
| M0 규범 계약 | E1 (엔진 쪽) | 없음(바탕) — `tds check --level manifest|schema`, `tds hash` | 명세 v3.4·TDS v1.4 공개판·CONTEXT·`docs/adr/`의 첫 결정 기록·LICENSE 병합; 모든 R·SC·TDS-D·RV·V31·R3·R4 항목이 부록 B에 매핑(R4F·R4G·R4H·R5·R6·R7은 매핑하지 않음); 티켓 그래프 시험 통과; TDS 검사기 manifest·schema 단계 + 세 결과 + 경로 안전 + 해시 시험 벡터; 손으로 정한 `tiny` 합성이 `schema` 통과; golden 틀 + G-01 | `uv run python -m nexusbt.testing.synth --preset tiny --out .scratch/snap --validate` → 데이터셋별 행 수, `value_sha256`·`semantic_sha256`, 프로필 세 결과(검사 안 한 것은 `not_checked`); `uv run tds check .scratch/snap --level schema` → 종료 코드 0 |
| M1 스냅숏 + Pipeline 조각 + 공개 첫 경로 | E2 | `run_pipeline`, 팩터 스크리닝, 실행 기록·재실행, `tds import csv`, 영어 빠른 시작(분석) | 검사기 full(K·R·T·D·A·V·H) + 해석기(결정 2026-11-10, #356: "검사기 full"은 `full` 단계가 TDS 8.3의 K, R, T, D, A, V, H 코드를 모두 판정한다는 뜻이다. 그 날짜에 아직 `unchecked`인 코드는 M1 티켓 T0.14b(T·D), T0.15c(A010·A011), T0.15d(V011·V012·H004)의 것이다); 합성 small(사건·정정 포함)과 core `degrade`가 `full` 통과; T-07, T-09~T-12, T-15, T-20, T-23; P-CHUNK(1년 미만 묶음 포함)·P-PERM·P-FUT·P-DET·P-KERNEL(참조)·P-START·M-SCALE·M-DUMMY·M-SPLIT-NEUTRAL(전제·반례 포함); L1-a(기본 입력끼리)·L1-b·L1-d; F-02~F-04 시험; 단계별 첫 측정(열기·블록·조정·창 커널·단면)이 `bench/results`에; **요구사항 증거**(사용자 결정 2026-11-03, 이 줄과 아래 모든 줄; R1~R5는 소유자의 다섯 요구사항: R1 현실성, R2 규모와 타당성, R3 전략 작성, R4 실운용 이어 가기, R5 출력): R2 — 7장의 M1 조기 측정(T1.24). T1.19(P-CHUNK, P-FUT)와 T1.21(P-START)이 늦은 봉 합성 변형(#354)에서 통과한 뒤에만 증거로 세고, 그 전에는 프로파일링이다(결정 2026-11-10, #356) | `uv run python examples/m1_screen.py` → 기준일 시장별 모멘텀 상위 10; `uv run nexusbt rerun <id>` → "outputs identical"; `uv run nexusbt doctor` → 프로필 세 결과·대체 목록·규칙 팩; `uv run python bench/run.py --stages m1 --snapshot synth-small` |
| M1b 첫 백테스트 끝-끝 (얇은 조각) | E3(첫 부분) | 한 시장·롱온리·`top(n)` 동일 가중·다음 시가 시장가·비용 없는 `backtest`; 첫 화면; 저장된 실행·`rerun`; `init --demo` | G-01, G-12, G-15~G-19, G-22(관측), G-30, G-34, G-45, G-46, G-48, G-53, G-54, G-55(T3.22a의 부분), G-61 (a); P-NAV, P-BRIDGE, P-QTY; L2-a·L2-c; 사람이 데모 데이터로 첫 백테스트를 돌리고(`init --demo` 다음 `examples/strategies/mom_kr.py`) 3.9의 첫 화면에 대어 읽음: 여섯 지표, 비용이 포함되지 않았다는 줄, 모의 결과 줄, 아직 만들어지지 않은 줄마다 기다리는 티켓 이름 | `uv run nexusbt init --demo` 다음 `uv run nexusbt backtest examples/strategies/mom_kr.py` → 첫 화면(수익률, CAGR, 변동성, Sharpe, 최대 낙폭, 회전율; 비용 미포함; `family: n/a (not built yet; available after ticket T2.9)`); `uv run nexusbt rerun <id>` → "outputs identical" |
| M2 PIT + 팩터 평가 | E2 | `evaluate`(경제 정답·정답 시각 셋·단순 폭·집단 BHY), `explain`(값), 구간, `preregister` | T-08, T-16, T-18, T-21, T-22 (T-01~T-06, T-13, T-14, T-17, T-19, 엄격판 계보, L1-c, F-06~F-08·F-11, 월간 패널은 2026-11-24에 뺐다, #752); 구간 넘는 정답 제외(`ts_label_available`); 후보·관측·집단; F-14 시험; P3 측정; 영어 빠른 시작 시험; 사람이 대표 팩터 결과(`examples/factors/momentum.py`)의 `report.html`을 열어 3.9 FactorReport 목록과 2초 예산에 대어 읽음; **요구사항 증거**: R2 — 7장의 M2 끝 조기 측정(T2.14, 그리고 T2.24의 축소 P11 (a)); R5 — `report.html`(T2.10b)이 3.9의 FactorReport 칸과 시각 규칙을 담고, 눈 확인은 팩터 결과를 3.9 전략 형태별 지표로 읽음(대표 결과 셋: 여기서 팩터, 이 팩터는 M1b의 전략이 이미 거래함; M3a에서 롱온리, 그 첫 화면은 M1b가 먼저 보임; M4에서 롱숏) | `uv run nexusbt evaluate examples/factors/momentum.py` → FactorReport(정답 정의 줄·naive breadth·BHY(cohort) 줄) |
| M3a 한 시장 시장가 백테스트 완성 | E3 | 비용·거래량 상한·가격 제한·모든 기업 행위를 갖춘 `backtest`(한 시장, 시장가), 전략 `screen` | G-10, G-11, G-13, G-14, G-20, G-21, G-22(정책, lo, hi), G-23~G-26, G-31, G-35, G-41~G-44, G-47, G-49, G-60; P-RESUME, P-STATE, P-PARITY13, P-DERIVED; L2-b; F-05·F-09·F-13 시험; 상태 기계 단계 측정(`full_ci`, 계산 기계 `full`); 사람이 대표 롱온리 결과(`examples/strategies/mom_kr.py`)의 `report.html`을 열어 3.9 Run 목록과 2초 예산에 대어 읽음(롱숏 결과는 공매도가 들어오는 M4에서 봄); **요구사항 증거**: R1 — 롱온리 보고서를 읽기 전에 소유자의 `nexusbt.toml` `[costs]`에 자기 증권사의 수수료가 들어 있음, 사용자가 정하지 않은 사용자 자신의 비용은 실행이 기록하지 않으므로(#841); R2 — 7장의 M3a 끝 조기 측정(T3.18, P5-daily와 전체 P11 (a) 포함); R5 — 눈 확인은 3.9의 Run 칸을 그 순서대로(질문 1~7) 전략 형태별 지표로 읽음; **한 시장 경로**(설계 검수 D15, 2026-11-04): `examples/strategies/mom_kr.py`는 `examples/factors/momentum.py`의 팩터로 순위를 매기므로(복사가 아니라 가져옴; 둘 다 M1b, T3.37에서 씀) M1b가 처음 거래하고 M2가 평가한 팩터가 M3a가 거래하는 팩터이고, 그 전략을 한 판단일에 `screen`하면 백테스트가 그날 가진 정규 목표가 나온다(P-PARITY13, INV-08). 이것은 목표의 일치일 뿐이다: 그 목표로 계좌가 만드는 주문·체결의 일치는 M5의 증거다(T5.17 `test_as_backtest_equals_backtest_account`, P-RECON) | `uv run nexusbt backtest examples/strategies/mom_kr.py` → Run 요약(가정 줄·직접 비용/경로 효과·reconciled: yes) |
| M3b 주문 종류 | E3 | 지정가·손절·손절지정가·탈출 주문, `explain(strategy)`, MinTRL·신호-비중 상관 | G-02~G-09, G-32, G-33, G-37~G-40; P-STATE(탈출 만료 금지)·P-QTY; L2-d(프리셋 의미); (선택) 사용자가 한 전략 3개월을 손으로 재현한 요약 증거 | `uv run nexusbt explain examples/strategies/mom_kr_exits.py KR:T00007 2019-06-28` → 판단 경로와 탈출 주문 사건 |
| M4 다중 시장 | E3 | 여러 슬리브 백테스트·스크리닝, 통화 귀속, 시장 규칙 팩 | G-27~G-29, G-36, G-50~G-52; M-CCY·M-SLEEVE(전제·반례); 한국 판단이 나중 미국 종가를 못 씀; 환율 방향·묵음; 규칙 경계; `ZZ` 시장 E18/팩 넣으면 돎; 두 슬리브 단계 측정; 사람이 대표 롱숏 결과(`examples/strategies/long_short_kr.py --set shorting.enabled=true`)의 `report.html`을 열어 3.9 Run 목록에 대어 읽음; **요구사항 증거**: R2 — 7장의 M4 끝 조기 측정(T4.9); R5 — 그 눈 확인은 롱숏 결과를 3.9 전략 형태별 지표로 읽음, 대표 결과 셋 가운데 마지막 | `uv run nexusbt backtest examples/strategies/value_mom.py` → 시장별 열과 `fx contribution` 줄이 있는 Run 요약 |
| M5 모의 운용 | E3 뒤(live) | `live`, 모의 장부(트랜잭션), `reconcile`(재생/재진술), `status.json`, `compare`, `Run.why`, 어댑터, CLI 전체 | 같은 판단·장부 → 같은 멱등 열쇠; `live → fill → live`에서 주문 한 번; 커밋 경계 강제 종료 복구(P-BOOK); 동시 작성자 E35; 자료 전 미래 시가 체결 없음; P-RECON; **요구사항 증거**: R1 — 설정 견본의 `[costs]` 부분(3.11, T5.21)에 증권사 US 수수료 줄이 있고 KR `provisional` 매수 5 bp(3.11)가 KR 증권사 수수료 7~25 bp에 비해 낙관적이라고 적음; R3 — T5.18의 전략 작성 시험(전략 셋, 단계마다 시간·도움·결과)이 M5 끝 증거에; R4 — P-LIVE(8.3), E19, `status.json`의 `last_reconcile`과 `first_divergence`(5.9.6), 수동 실운용 예외 규칙(5.9.6 규칙 1~4), 그리고 잰 대표 주문일 하루(주문, 주문 종류, 걸린 시간, 예외, 재진입; 5.9.7 (5)의 기록)가 M5 끝 증거에 | `uv run nexusbt live examples/strategies/value_mom.py --book paper:demo --fill next_open` 두 번 → 두 번째는 IdempotencyNotice; `uv run nexusbt reconcile --book paper:demo` → `reconciled: yes (replay)` |
| M6 성능·연구 도구·출시 관문 | E3 성능 | `sweep`, DSR·PBO(집단), 탐침, 시작일 탐침, L0·L1 캐시, 용량 시나리오, 깨끗한 설치 | 빠른 커널 = 참조(같은 환경 비트); P-CACHE(L0·L1, 해석 메타·잡힌 상수); 프로세스 트리 RSS·USS를 4 GB에 견주어 잼(알림, 7장); P-STAT; 7장 측정 JSON(앞 측정과 견줌; 성능 관문 없음, #725 결정 257); `engine / release` 통과(깨끗한 wheel + 독립 생산자); **요구사항 증거**: R2 — T6.11 JSON에서 cold와 warm 출력 해시가 같음, P-CACHE-INCR 통과(8.3), 6.3a hygiene 칸의 시도 줄이 기록된 시도의 범위를 적음; R5 — `hygiene` 칸(3.9 질문 8, T6.22)과 대표 결과 셋을 모든 칸과 함께 눈으로 확인. M6은 아래 것 없이 합성 적합성에서 끝나고, 아래 것은 그 뒤의 출시 관문에 속함(OI-46): R1 — 실제 스냅숏 백테스트의 첫 화면이 비용 0×/1×/2×(5.7), 상장폐지 lo/hi(3.8 `scenarios`), `offsets=3`의 CAGR 범위를 보이고, 사건별 장부 검증 표가 체결 대 판단 bp를 모형의 기준(다음 시가, 맞춘 주문 시각·종류·수량)에 대어 잼(T6.28, T6.29와 8.4 표, #162); R2 — 그 스냅숏에서 보고서의 `skipped:` 줄(6.6)과 커버리지 출력(#160)이 연도별 빠짐을 보임 | `uv run nexusbt sweep examples/strategies/value_mom.py` → 후보 표 + PBO + DSR(cohort) + 최종 후보 capacity 줄 |
| v1.x | v1 직후 | N_eff, Brinson·`first_divergence` | T7.x 각 티켓의 시험 | 티켓별 |
| (M7) 이벤트 다리 | E4 | – | 11장 설계만, v1 티켓 없음 | – |
| (M8) 옵션 | E5 | – | 11장 설계만 | – |

**v3.1 끝 조건 추가** [V31, V31-LS]: M1 — T-24·T-25, P-DET(새 프로세스 둘), TDS-A010·A011·V011·V012·H004 pass/fail, F-15·F-16; M2 — T-26~T-28; M3a — G-53~G-56, G-58~G-60, G-66, P-FILLCAUSAL, P-QTY(정수 비율), P-BRIDGE(정지일 사건); M3b — G-57, G-61, P-GRID; M4 — G-62, G-67~G-75, P-SLEEVE-ISO, P-SHORT-OFF, L2-e, 공매도 금지 기간 시험 팩; M5 — G-64, G-65, P-TRADES, 사전 점검 E36, override·사람 장부 재생; M6 — P-CACHE-INCR, 작업 P2b, G-63(T7.1). 보여 줄 명령 추가: M4 `uv run nexusbt backtest examples/strategies/long_short_kr.py --set shorting.enabled=true` → 노출 줄·대차 비용·`reconciled: yes`; M5 `uv run nexusbt screen examples/strategies/value_mom.py --show held+near --html`.

**v3.2 끝 조건 추가** [R3]: M0 — 해석된 기본값 고정(코드포인트 첫 시장), 팩 `base_unit`·`day_count`·KR 끝수 `down`·ETF/분수 시대 씨앗·금지 표 문법(T0.5a·T0.5b); M1 — 해석기 존재/조건 시각(`test_late_terms_revision_visible_at_ex_date`), 3값 연산 넷, 동률 고정 소금(T-27 새 값), 잘못된 정확 비율 E13, 도장 파일 신원·핀 기본 `index+root`; M2 — E39·잎별 모름 건수(T2.22); M3a — G-20 변형, G-53 (e)(g)~(j), G-55 (a)~(f), P-FILLCAUSAL 두 성질, `daily` 다리 칼럼 둘; M3b — 최소 단위 정수 비교 G-57 (f)~(h); M4 — 숏 회계·생애(G-67 다시 씀, G-68 (b)~(d), G-70 (b), G-72 (b)(c), G-73 변형, G-75 (b), G-76, G-77), P-SHORT-OFF 차등 + 기준선, 현금 이자; M5 — 장부 TWR CAGR(G-65 (b)), 수동 사건 규약, `book=` X-Ray, `TargetState` 배관(T5.16); M6 — P-CACHE-INCR 새 사례, 공유 L0 보존, PBO 공통 기간, G-63 (c)(d), T7.V 출시 재검증.

**v3.3 끝 조건 추가** [R4]: M0 — 오류 층 표·층 사례 틀·내부 용어 금지 시험(T0.4b), E40~E46 클래스; M3a — 자금 관리 칸·내장 사이저·ERC 대체(G-78~G-83), 위험 규칙 목록·순서(G-82·G-85·G-86), 계좌 층·`final_weight`·`risk_state`·낙폭 브레이크 왕복(G-84·G-87), P-RISK-OFF·P-SIZE-PURE·P-RISK-SHRINK·P-SKIP, `waterfall.parquet`·`skips.parquet`, `strategy.replace`·`--preview`; M3b — `exits.time_stop` OCO, `risk.no_reentry`; M5 — screen 계좌 셋(`--ledger`·`--as-backtest`·not evaluated), 템플릿 20개·`init --demo`·30분 길 시험, zipline 대응표 문서, `compare` 변형 표; M6 — 분할기·정화(G-88·G-89, P-SPLIT-DET), `backtest(method=…)` 계좌 규칙(G-90·G-91, P-WF-STITCH), CPCV·CSCV·hygiene 첫 화면, `ml.factor`(G-92, P-ML-REPRO), 삼중 장벽(G-93), P11 측정 JSON. 보여 줄 명령 추가: M3a `uv run nexusbt backtest examples/strategies/erc_brake.py --preview` → "PREVIEW" 줄 + risk waterfall 줄; M6 `uv run nexusbt backtest examples/strategies/value_mom.py --method cpcv` → linear 결과와 경로 5개 분포·PBO·DSR 줄.

**v3.4 끝 조건 추가** [R4F]: M1 — TDS A010 오류(정확 비율 필수, T0.15c), 정확 비율 없는 사건은 `decimal_ratio`를 따름(기본 `exclude_instrument`는 그 종목을 사건이 보이는 때부터 뺌), 잘못된 비율은 E13 그대로(T1.1a); M2 — 공용 `terminal_value`(T2.7), `Macro.series`·`Events`·`from_parquet(shape=)`·E47(T2.Ge, T2.23; G-96·G-98; 2026-11-24 대체, #752); M3a — `vol_target` 넷째 항(G-81 (c)(d)), 사이저 손계산(G-95), INV-23 제외 목록·−0.0, 그림자 지수 폐지 반영(G-84 (b)), 계좌 규칙 순서 E16, preview 셈·기간(T3.34), 포함 여부 모름 보수 쪽(G-55 (g)(h)); M3b — `on_event`(T3.35; G-97, 템플릿 둘; 2026-11-24 대체, #752); M4 — 탈출 주문 `blocked(cash)`(G-94); M5 — 30분 길 첫 줄 `uv init`(T5.18, 템플릿 16개); M6 — 앞쪽만 ML 학습(T6.24), grid IS 자르기·`backtest(start=t_1)` 비교(T6.20), G-90 숫자, P11 fixture·단계 예산·출력 해시(T1.24, T6.26), `[ml]` 설치 검사(T6.15), `buffer-hold` 템플릿 시험(T7.1). 티켓 210 → **213**(새 T2.Ge·T2.23·T3.35), golden 93 → **98**(G-94~G-98), 오류 E47.

**v3.4 최종 수정 끝 조건 추가** [R4G]: M2 — `from_parquet` 모양별 서명·E47 fix 줄 실행(T2.23); M3b — 시장 사건 대상 = 전체(가정 기록)·명시 `event_instruments` E16, 쪽별 예산 + 합친 책 `k` 축소, 수명 끝 청산 전용 판단·screen "scheduled exit", 수명 끝·`time_stop` 한 주문(T3.35; G-97 (c)~(e)) (둘 다 2026-11-24 대체, #752); M4 — 증거금 계좌(T4.Gm, T4.20; G-99~G-102, P-MARGIN-OFF); M5 — 두 층 설정 틀·`config check`·`config show`·보고서 1부 값(T5.21). 티켓 213 → **216**(T4.Gm·T4.20·T5.21), golden 98 → **102**(G-99~G-102), 성질 시험 + P-MARGIN-OFF.

**명세 변경 반영 시점**: v3는 청사진 SC-01~SC-27과 3자 검토 합의의 P0·P1(그리고 값싼 P2)을 본문에 반영했다. 구현 중 명세 빈틈이 나오면 9.5의 "spec deviation" 절차로 고치고 이 문서를 개정한다 — v2의 "마일스톤 시작 전에 명세를 다시 고칠 일은 없다"는 3자 검토가 반박해 뺐다. 각 SC가 처음 구현·시험되는 티켓은 부록 B.2, RV 항목은 부록 B.4.

**티켓 규칙**: 한 세션은 한 티켓만 다루고, 한 티켓은 PR 하나 또는 여럿으로 들어간다(결정 2026-11-10, #356, "한 티켓 = 한 세션 = 한 PR"을 대신한다. 실제 진행과 저장소의 나누기 규칙이 그 문장과 어긋났다): PR마다 바뀐 줄 ≤ 400(문서·잠금 제외; plinth `ci / diff-size`)이고, 앞 PR이 병합된 뒤의 `main`에서 가지를 내며(병합 안 된 PR 위에 쌓지 않는다), 어느 수용 기준을 채우고 어느 것을 뒤 PR에 남기는지 적는다. 마지막 PR이 모든 기준을 그것을 채운 PR과 함께 적고 이슈를 닫는다. 크기 S ≤ 150줄, M ≤ 400줄. 제목은 PR 제목으로도 쓰는 Conventional Commits. "Context"는 할 일, "Done means"는 사람이 보고 확인할 것, "Acceptance"는 만들 시험 이름(tdd로 먼저 실패시킴), "Blocked by"는 티켓 번호(이슈로 만들면 이슈 번호로 바꿈). **golden 티켓**(`T<m>.G…`)은 손으로 쓴 세션별 산수(8.2)이고 그것을 쓰는 구현 티켓보다 먼저, 다른 세션에서 병합한다. **엔진 티켓 수(지금 기준 = v3.4 최종 + R5 + R7, `tools/spec_lint.py`로 셈): M0 16, M1 41(M1 벤치용 T0.8d 추가), M2 31(축소 P11 (a)용 T2.24 추가), M3a 37, M3b 12(T3.35가 상태 기록을 갖도록 T5.16에서 T5.16a를 나눔, #152), M4 28, M5 24, M6 31(T7.G·T7.1·T7.V 포함), v1.x 2(T7.2·T7.5) = 222.** 2026-11-24부터(#752) T0.8a, T2.2, T2.13, T2.Ge, T2.23(M2)과 T3.35(M3b)는 빠졌고 그 번호는 다시 쓰지 않는다: M2 26, M3b 11, 모두 216. 이 셈은 M1b(#858) 이전의 것이다. 같은 셈의 시험·결정 id: 손계산 정답 G-01~G-107(107개), 성질 시험 36개(8.3 표), 오류 E1~E49(49개, 6.6), ADR 0001~0041(41개, 9.3). 이 문단과 아래의 다른 숫자는 그 판 때 기록이다. **엔진 티켓 수: M0 16, M1 40, M2 28, M3a 36, M3b 10, M4 26, M5 22, M6 27, v1.x 절 5(T7.G·T7.1은 M6 끝, T7.V는 T7.1 뒤 확인 단계, T7.2·T7.5는 v1.x) = 210**(v3.2의 188에서 새 24, v1.x에서 v1로 옮긴 T7.3·T7.4는 새 티켓 T3.29·T3.33에 흡수). 아래 v3.2 문장의 숫자는 v3.2 때 기록이다. 엔진 티켓 수: M0 15, M1 40, M2 28, M3a 28, M3b 9, M4 26, M5 18, M6 17, v1.x 절 7(T7.G·T7.1은 M6 끝, T7.V는 T7.1 뒤 확인 단계, T7.2~T7.5는 v1.x) = 188(v3.1의 176에서 나눔 8·새 4, 아래 대응 표). 아래 v3.1 문장의 숫자는 v3.1 때 기록이다. 엔진 티켓 수: M0 13, M1 39, M2 27, M3a 28, M3b 9, M4 21, M5 16, M6 17, v1.x 절 6(T7.G·T7.1은 M6 끝에 들어가고 T7.2~T7.5는 v1.x) = **176**(v3의 142 = 141 + 세금 T4.5b에서 새 34) [V31, V31-LS]. 아래 v3 문장의 숫자는 v3 때 기록이다: M0 13, M1 34, M2 23, M3a 22, M3b 7, M4 12, M5 9, M6 16, v1.x 5 = **141**(v2의 112에서 나눔·새 티켓·golden 티켓으로 늘고, v2의 T0.11·T0.17은 golden 티켓으로 흩어져 없어지고 T6.1은 T1.24로 옮김). 의존 그래프는 비순환이고 모든 "Blocked by"가 같거나 앞 마일스톤에 있다(v3 작성 때 스크립트로 확인; 저장소에서는 T0.12의 `test_ticket_graph`).

티켓 전체에 걸친 규칙, 한 줄씩(이 폴더의 `README.md`가 정한 꼴):

- decided (#43 Decisions, 2026-11-04): M1을 자른 때부터, M1 티켓이 구현하는 절(4장, 5.1~5.3, 5.9.5, 7장의 M1 행, 10.1의 T0·T1 항목)은 결함(모순, 적힌 대로 구현할 수 없는 규칙, 반례)일 때만, 그것을 찾은 티켓이 스펙 PR로 내어 바꾼다. 그 절에 닿는 새 기능, 안내 문구, 시나리오는 M1 끝까지 기다린다. 규칙을 고칠 때는 #764 조각 6의 길로 한다: 주인에게 묻고, 따로 PR로.
- decided (#43 Decisions, 2026-11-18): 스펙은 규칙을 자기 말로 적고, plinth의 명령이나 파일을 뜻할 때만 plinth를 이름 댄다. 지난 기록은 고쳐 쓰지 않는다.

**v2 → v3 티켓 대응** (이슈를 만들 때 이 표로 확인):

| v2 | v3 | 이유 |
|---|---|---|
| T0.2 | T0.2a(뼈대·금지 규칙), T0.2b(위생·공개 이름 시험) | 크기 |
| T0.7 | T0.7 (M1로) | M0 축소 |
| T0.8 | T0.8a(재무·분류, M2), T0.8b(환율·지수·패널, M2), T0.8c(`full`·`full_ci` 프리셋, M3a) | 크기, 소비 마일스톤 앞으로 |
| T0.9, T0.11, T0.17 | T0.9(golden 틀 + G-01, M0) + T1.G, T2.G, T3.Ga, T3.Gb, T3.Gc, T4.G | 두 번째 엔진 금지, 소비 티켓 앞으로 |
| T0.13 | T0.13a(manifest·세 결과·경로 안전·CLI), T0.13b(schema 단계·스키마 파일) | 크기 |
| T0.14 | T0.14a(K·R, M1), T0.14b(T·D, M1), T0.14c(값·의미 해시 + 시험 벡터, M0) | 크기, 해시는 1.0 전 |
| T0.15 | T0.15a(기업행동 해석기, `nexusbt_tds.actions`, M1), T0.15b(A·V 검사, M1) | 해석기 하나, 크기 |
| T0.16 | T0.16a(core `degrade`, M1), T0.16b(research `degrade`, M2) | M1이 M0 전체를 기다리지 않게 |
| T1.1 | T1.1a(열기·검사·E14·규칙 팩), T1.1b(능력·세 결과·대체 F-02~F-04(F-04는 2026-11-22, F-02는 2026-11-23 은퇴, #705)·핀) | 크기 |
| T1.7 | T1.7a(계획·창·shift 전파), T1.7b(참조 실행기·고정 합 순서·묶음 크기) | 크기 |
| T1.14 | T1.14a(봉인 폴더·복구·소스 잡기), T1.14b(색인: 후보·관측·집단·핀, 수치 환경) | 크기 |
| T2.10 | T2.10a(evaluate API·FactorReport), T2.10b(report.html 구조 시험) | 크기, 눈 확인을 구조 시험으로 |
| T3.5 | T3.5a(시가 시장가·거래 가능), T3.5b(상한·실제 비용 함수 현금 배분) | 크기, 비용 함수 의존 |
| T3.13 | T3.13a(backtest API·지표), T3.13b(시나리오: gross 한 번) | 크기 |
| T6.1 | T1.24 (M1로) | 이른 측정 |
| (없음) | T1.22 `tds import csv`, T1.23 `tds manifest build`, T2.17 영어 빠른 시작, T2.18 `preregister`, T3.21 E6·E25 경고, T4.11 `ZZ` 시장, T6.15 출시 관문, T6.16 배포 워크플로, T6.17 `bridge` 능력 시험 | 빠진 티켓 |

**v3.1 → v3.2 티켓 대응** (400줄 규칙과 의미 경계로 나눔):

| v3.1 | v3.2 | 이유 |
|---|---|---|
| T0.5 | T0.5a(설정 키·해석된 기본값), T0.5b(시장 규칙 팩·씨앗 표) | 크기; 팩 씨앗이 늘어남 |
| T0.13b | T0.13b(스키마 파일·검증), T0.13c(schema 단계 검사) | 크기 |
| T0.15c | T0.15c(A010·A011), T0.15d(V011·V012·H004·`market_rules`) | 크기 |
| T2.Gb의 T-27 | T1.Gb로 옮김 | T1.11(M1)이 T-27을 씀 |
| T4.Gs | T4.Gs(숏 회계·발생·파산·현금 이자), T4.Gt(롱숏 목표·숏 주문·금지) | 크기(새 사례 G-76·G-77, 변형) |
| T4.15 | T4.15a(상태·담보·발생·의무·파산), T4.15b(배당·기업행동·폐지·추정 교체), T4.15c(숏 세금) | 크기 |
| T4.16 | T4.16a(순서·반전·거울·용량), T4.16b(탈출·금지) | 크기 |
| T5.11 | T5.11a(수동 사건 규약·가져오기), T5.11b(수동 장부 대조) | 크기 |
| (없음) | T2.22 `Filter.fillna`·E39, T4.19 현금 이자, T5.16 `TargetState` 배관, T7.V T7.1 뒤 출시 재검증 | |

**v3.2 → v3.3 티켓 대응**:

| v3.2 | v3.3 | 이유 |
|---|---|---|
| T7.3 `risk.group_caps`(v1.x) | T3.29(M3a) | 그룹 상한을 v1로 |
| T7.4 `exits.time_stop`(v1.x) | T3.33(M3b, + `risk.no_reentry`) | 시간 손절을 v1로 |
| T0.4 | T0.4 + T0.4b(층 줄·E40~E46) | 크기 |
| (없음) | T3.Gr, T3.27, T3.28, T3.30, T3.31, T3.32, T3.34, T5.17, T5.18, T5.19, T5.20, T6.Gv, T6.19~T6.27 | |

### 10.1 엔진 티켓 (GitHub 이슈로 그대로)

#### M0 — 규범 계약

**T0.1 `docs: add spec v3.4, TDS v1.4, CONTEXT.md, ADRs, license and contributor files`** · `M0` `docs` · S(문서) · Blocked by: 없음 · §2.1, §9.1~9.3
- Context: 이 명세를 `docs/spec/engine-spec-v3.4.md`로, TDS v1.4을 `tds/spec/tds-v1.md`로(둘 다 2.7 공개판: 비공개 주석·TDS 11장·개인 경로·호스트를 뺌), 9.2를 `CONTEXT.md`로, 명세의 첫 결정 기록을 `docs/adr/`에 한 파일씩(영어 정본 초안 = 엔진 폴더 `handoff/`의 `CONTEXT.md`·`CONTEXT.ko.md`·`docs/adr/*.md`·`README.md`·`README.ko.md`·`SPEC-INDEX.md`, 그대로 복사), `LICENSE`(Apache-2.0 전문)·`NOTICE`, `CONTRIBUTING.md`·`SECURITY.md`·`CODE_OF_CONDUCT.md`(짧은 틀), 영어 `README.md` 틀(공개 문서 언어는 12장 OI-45).
- Done means: GitHub에서 `CONTEXT.md`, `docs/adr/`의 파일들, `tds/spec/tds-v1.md`, `LICENSE`, `CONTRIBUTING.md`가 보이고, ADR마다 "Status: accepted, Date, Context/Decision/Consequences" 세 절이 있다(ADR-0021도 accepted — OI-20 사용자 결정 2026-10-28). 공개판 문서에 금지 낱말 목록(`.hygiene-private.txt`)의 생산자 이름이 없다.
- Acceptance: (문서 PR) `grep -c "Apache License" LICENSE` ≥ 1; `grep -riFf .hygiene-private.txt docs/spec tds/spec docs/adr CONTEXT.md CONTEXT.ko.md README.md README.ko.md | wc -l` = 0.

**T0.2a `chore: workspace skeleton with layer and ban rules`** · `M0` `infra` · M · Blocked by: T0.1 · §2.3–2.6
- Context: 2.3 트리의 빈 패키지(`src/nexusbt/*`, `tds/src/nexusbt_tds`), 각 `__init__`에 2.4 공개 이름(본문 `NotImplementedError`), ruff banned-api(2.5 목록), pytest 표시·hypothesis 프로필(`ci`, `deep`), `[project.scripts] nexusbt`, `tds`.
- Done means: `uv run nexusbt --help`와 `uv run tds --help`가 하위 명령 목록을 출력하고, `uv run pytest`가 import 시험을 통과한다.
- Acceptance: `tests/unit/test_import_rules.py::test_layer_graph_respected`, `::test_banned_imports_absent_in_src`(pickle·duckdb·zipline 포함), `::test_tds_does_not_import_nexusbt`.

**T0.2b `test(repo): public hygiene and public-name tests`** · `M0` `repo` · S · Blocked by: T0.2a · §2.7, §3.1
- Context: `tests/repo/test_public_hygiene.py`의 2.7 시험 전부, `test_public_names_match_spec_3_1`.
- Done means: 일부러 `/Users` 홈 경로나 금지 낱말 목록의 생산자 이름 + 티켓 번호 문장을 넣은 파일을 만들면 시험이 실패하고, "10.2절"이 든 문서는 통과한다.
- Acceptance: `tests/repo/test_public_hygiene.py::test_no_private_paths`, `::test_section_numbers_not_ip`, `::test_no_producer_internal_refs`, `::test_no_data_files`, `::test_license_headers`, `::test_tds_public_has_no_producer_names`; `tests/unit/test_import_rules.py::test_public_names_match_spec_3_1`.

**T0.3 `feat(contracts): id constant, engine column sets, phases and artifact schema versions`** · `M0` `contracts` · M · Blocked by: T0.2a · §2.4, §4.6, §5.6.3, 머리말 "식별자 이름"
- Context: `ID_COLUMN`, `ENGINE_COLUMNS`(4.6 표의 데이터셋별 칼럼·TDS 형), `Unit`, `Currency`, `Phase`(5.6.3 순서), 2.4의 정책 열거형 26개(`DelistingPolicy` … `RoundingModePolicy`), `RUN_SCHEMA`·`EVENTS_SCHEMA`·`CHECKPOINT_SCHEMA`.
- Done means: `uv run python -c "from nexusbt.contracts import ENGINE_COLUMNS, Phase; print(sorted(ENGINE_COLUMNS)); print(list(Phase))"`가 4.6 표의 데이터셋 이름과 단계 순서 일곱 개를 출력한다.
- Acceptance: `tests/unit/contracts/test_contracts.py::test_engine_columns_subset_of_tds_schemas`, `::test_no_id_alias_public`, `::test_phase_order_matches_5_6_3`.

**T0.4 `feat(contracts): teaching error classes E1..E39 and message format`** · `M0` `contracts` · M · Blocked by: T0.2a · §6.6
- Context: `NexusBTError`와 E1~E39 클래스, 다섯 부분 메시지 서식기, 막음/실패/경고/알림 분류, E14가 TDS 코드 목록과 `producer.hints`를 싣는 형식.
- Done means: `uv run python -c "import nexusbt as nx; raise nx.ColumnNameError.example()"`이 6.6 모양(what/where/why/fix/more)으로 출력된다.
- Acceptance: `tests/unit/contracts/test_errors.py::test_all_codes_present_E1_to_E39`, `::test_message_has_five_parts`, `::test_blocking_classification_matches_table`, `::test_snapshot_error_carries_tds_codes_and_hints`, `::test_messages_have_no_producer_tickets`.

**T0.4b `feat(contracts): error layer line, layer table, internal-term ban and engine-bug report`** · `M0` `contracts` · M · Blocked by: T0.4 · §6.6, §8.4b
- Context: 6.6 서식에 `layer` 둘째 줄과 층별 꼬리, `tests/errors/layers.toml`(코드·조건 → 층), E40~E49 클래스(E47 `DatasetShapeError` v3.4; E48 `PretrainedLeakError`·E49 `PretrainedOverlapWarning` R5), `EngineBugError`(종료 코드 2)와 `nexusbt bugreport RUN_ID`(재현 명령·매니페스트·판 묶음), 사용자 함수 예외에 `add_note`로 layer·fix 줄을 붙이는 도우미와 `errors/hints.toml`.
- Done means: `uv run python -c "import nexusbt as nx; raise nx.ColumnNameError.example()"`이 `layer  your code — …` 줄이 든 여섯 부분으로 출력되고, `nexusbt bugreport demo`가 묶음 파일 경로를 출력한다.
- Acceptance: `tests/errors/test_layers.py::test_every_code_has_layer_case`, `::test_layer_line_matches_table`, `::test_layer_tail_fields`, `::test_fix_line_present`, `tests/errors/test_no_internal_terms.py::test_public_layers_have_no_internal_names`, `tests/errors/test_user_exception_note.py::test_original_class_and_traceback_kept`, `tests/unit/contracts/test_errors.py::test_codes_E40_to_E49_present`.

**T0.5a `feat(config): load and validate nexusbt.toml keys with resolved defaults`** · `M0` `config` · M · Blocked by: T0.3 · §3.11, §2.6, §5.1.3
- Context: 3.11의 모든 키·기본값·검증, `nx.config()`, 알 수 없는 키 제안, 비밀 키 이름 금지, 예약 키, 시장 이름이 들어가는 키를 스냅숏 `markets`로 검증(`load_config(markets=)`), 해석된 기본값(첫 시장 = `markets` 키 UTF-8 바이트 순 첫째 → `clock`·`base_ccy`·`sleeves`)을 매니페스트용으로 돌려줌, `max_net` 닫힌 구간 ∋ 0 검사, 롱숏 가능 영역 검사 함수(3.7; 호출은 T4.14).
- Done means: 빈 `nexusbt.toml` + 시장 `KR`,`US`로 `nx.config()`가 3.11 기본값을 출력하고 `markets` 객체 순서를 `US, KR`로 바꿔도 해석된 `clock = KR_close`·`base_ccy = KRW`가 같다; `[sleeves] weights = {JP = 1}`이면 E16 "unknown market JP; snapshot markets: KR, US"; `[broker] api_key = "x"`면 E16 "secrets do not belong in nexusbt.toml"; `[shorting] max_net = [0.2, 0.8]`이면 E16.
- Acceptance: `tests/unit/config/test_config.py::test_defaults_match_spec_table`, `::test_unknown_key_suggests`, `::test_sleeve_weights_must_sum_to_one`, `::test_markets_from_manifest`, `::test_segments_must_not_overlap`, `::test_preset_zipline_forbidden_in_toml`, `::test_secret_like_keys_rejected`, `::test_reserved_keys_accept_only_v1_value`, `::test_data_root_from_env`, `::test_shorting_disabled_by_default`, `::test_market_object_reordering_preserves_resolved_defaults`, `::test_net_interval_must_contain_zero`, `::test_pins_default_index_root`, `::test_cash_rate_default_zero`.

**T0.5b `feat(config): market rules packs, grid units and seed tables with verification flags`** · `M0` `config` · M · Blocked by: T0.5a · §4.7
- Context: `resources/markets/{KR,US,_generic}.toml`과 그 스키마 검사(`[grid]`·`[rounding]`·`[shorting]` 절), `ticks/{kr,us}_tick_table_v1.csv`(`venue_group` 포함), `shorting/kr_short_bans_v1.csv`(반열림 구간, `scope` 문법, `except_universe_ids`), `limits/`·`costs/` 씨앗, 모든 씨앗 행의 `source`·`verified`, 출시 증거용 규칙 목록 함수(적용된 행의 출처·경계·`verified`).
- Done means: `uv run python -m nexusbt.config.packs --describe KR`가 팩 판·`base_unit`·끝수 규칙·`day_count`·씨앗 표 행 수와 `verified = false` 행 수(분자/분모)를 출력.
- Acceptance: `tests/unit/config/test_rules_packs.py::test_kr_us_generic_packs_valid`, `::test_grid_rounding_shorting_sections`, `::test_seed_tables_marked_unverified`, `::test_base_unit_per_market`, `::test_kr_rounding_default_down`, `::test_etf_venue_group_tick`, `::test_us_pre_decimal_rows`, `::test_ban_table_scope_grammar`, `::test_ban_intervals_half_open`, `::test_rule_listing_has_source_and_verified`.

**T0.10 `ci: add engine and tds check jobs`** · `M0` `infra` · S · Blocked by: T0.2a · §9.1 — **사용자가 푸시**(워크플로 권한)
- Context: `engine / parity`, `engine / property-deep`, `engine / perf-smoke`, `engine / docs-examples`, `engine / golden-guard`, `engine / release`, `tds / conformance`, `tds / schemas` job. 아직 시험이 없는 job은 "no tests yet"으로 통과하되, **각 job이 필수 목록에 들어가는 마일스톤(9.1 표) 끝 조건에 "그 job이 시험 ≥ 1개를 실제로 돈다"를 둔다**.
- Done means: PR의 Checks 탭에 여덟 job이 초록으로 보인다. 필수 목록 추가는 각 마일스톤 끝에 사용자가 한다(`tds / *`·`engine / golden-guard`는 M0 끝).
- Acceptance: 각 job 로그에 실행 명령(9.1 표)이 보인다.

**T0.12 `docs: requirement status map and ticket graph check`** · `M0` `docs` · S · Blocked by: T0.1 · 부록 B, §10
- Context: `tests/repo/test_ticket_graph.py`(계획의 티켓 줄을 읽어 "Blocked by" 그래프가 비순환이고, 각 의존이 같거나 앞 마일스톤에 있는지 확인).
- Done means: 그래프 시험이 통과하고, 부록 B가 이름 대는 티켓이 모두 계획의 티켓인지 보는 시험도 통과한다.
- Acceptance: `tests/repo/test_ticket_graph.py::test_acyclic_and_milestone_order`, `::test_every_ticket_appendix_b_names_is_a_ticket_of_the_plan`.

**T0.13a `feat(tds): manifest-level checker, profile results, path safety and CLI`** · `M0` `tds` · M · Blocked by: T0.2a · §2.6, §4.3, §4.4, §8.4a, TDS 4·7·8·10
- Context: `read_manifest`, `check(level="manifest")`(M001~M014: 경로 안전 M012·중복 경로 M013·모르는 필수 해석 규칙 M014 포함), `PROFILES`(TDS 7장, `@판`), 프로필 **세 결과**(`ProfileStatus`: declared / verified_level / result, 그 단계가 못 보는 규칙은 `not_checked`), `producer.hints` 읽기, CLI `tds check/describe`, JSON Lines 출력, 종료 코드, `tds/conformance/build.py`의 M 코드 pass/fail 패키지.
- Done means: `uv run tds check tds/conformance/TDS-M012/fail --format json`이 `TDS-M012` 한 줄과 요약 줄(프로필 세 결과)을 내고 종료 코드 1; 프로필을 선언만 한 패키지를 `manifest`로 검사하면 행 규칙은 `not_checked`로 나온다.
- Acceptance: `tds/tests/test_conformance.py::test_M_codes`, `::test_M012_path_escape`, `::test_M013_duplicate_path`, `::test_M014_unknown_required_rule`; `tds/tests/test_profiles.py::test_profile_three_results`, `::test_manifest_level_never_reports_unchecked_as_pass`; `tds/tests/test_cli.py::test_exit_codes`, `::test_jsonl_output_schema`.

**T0.13b `feat(tds): schema files with stability status and table verification`** · `M0` `tds` · S · Blocked by: T0.13a · TDS 5·10
- Context: `tds/schemas/<kind>/1.0.json`(TDS 5장 데이터셋, 각 파일에 `status: stable|experimental`; 일봉 주식 데이터셋만 stable), `tds.schemas.verify`(문서 표 = 스키마 파일).
- Done means: `uv run python -m nexusbt_tds.schemas.verify`가 stable/experimental 목록과 "doc tables match schema files"를 출력.
- Acceptance: `tds/tests/test_schemas.py::test_schema_files_cover_stable_datasets`, `::test_experimental_schemas_flagged`, `::test_doc_tables_match_schema_files`.

**T0.13c `feat(tds): schema-level checks with S-code conformance packages`** · `M0` `tds` · M · Blocked by: T0.13b · TDS 8
- Context: `check(level="schema")`(S001~S010: Parquet 바닥글·통계·파티션 경로·형), S 코드 pass/fail 패키지(`tds/conformance/build.py`).
- Done means: `uv run tds check tds/conformance/TDS-S002/fail --format json`이 `TDS-S002`와 종료 코드 1; `schema` 단계로 검사한 프로필의 행 규칙은 `not_checked`.
- Acceptance: `tds/tests/test_conformance.py::test_S_codes`, `::test_schema_level_reports_rows_not_checked`.

**T0.14c `feat(tds): canonical value hash, semantic hash and published test vectors`** · `M0` `tds` · M · Blocked by: T0.13b · TDS 4.5, §4.2, §5.9.4
- Context: TDS 4.5의 정규 값 직렬화(형별 바이트 규칙, null 태그, −0.0 정규화, 열쇠 정렬, 파티션 칼럼 포함) → `value_hash`, 패키지 `value_sha256`, 해석 메타 정규 JSON + 값 해시 → `semantic_sha256`, `physical_sha256`, `tds hash [--write]`, `tds/conformance/hash-vectors.json`(손으로 쓴 작은 표 11개와 기대 바이트 열·sha256; pyarrow를 쓰지 않는 순수 Python 참조 인코더 `tds/tests/ref_encoder.py`로 교차 확인), H001~H003.
- Done means: `uv run tds hash PKG`가 같은 내용을 압축·row group만 바꿔 쓴 두 패키지에 같은 값·의미 해시를 내고, `availability` 규칙 하나만 바꾼 패키지는 값 해시는 같고 의미 해시가 다르다.
- Acceptance: `tds/tests/test_hash.py::test_file_value_hash_written`, `::test_vectors_match_published`, `::test_reference_encoder_matches_pyarrow_path`, `::test_value_hash_ignores_physical_choices`, `::test_recompress_same_semantic`, `::test_availability_change_changes_semantic`, `::test_partition_columns_from_path`; `tds/tests/test_conformance.py::test_H_codes`.

**T0.6 `feat(testing): synthetic TDS package part 1 - hand-authored tiny and small calendars, instruments, symbols, bars`** · `M0` `testing` · M · Blocked by: T0.3, T0.13c, T0.14c · §4.8 (1)(2)(3)
- Context: `make_snapshot` 뼈대, `tiny`(사례 yaml이 그대로 행이 되는 손으로 정한 표, 무작위 없음)와 `small`의 `calendar_sessions`(`session_ord` 포함)·`instruments`·`instrument_symbols`(`ts_known_to` 포함)·조밀 `bars`(cum factor 1.0), `markets=("KR","US","ZZ")` 선택, `tds.json`(해시는 `tds.hash`, `producer.hints` 몇 줄).
- Done means: `uv run python -m nexusbt.testing.synth --preset tiny --out .scratch/snap --validate`가 데이터셋별 행 수와 `value_sha256`·`semantic_sha256`을 출력하고 두 번 돌려도 같다; `tds check --level schema` 통과.
- Acceptance: `tests/unit/testing/test_synth.py::test_deterministic_bytes`, `::test_tiny_is_hand_authored_no_rng`, `::test_bars_dense_per_listing`, `::test_sessions_have_utc_open_close_with_dst`, `::test_symbol_reuse_present`, `::test_zz_market_generated`.

**T0.9 `test(golden): golden case format, literal-arithmetic checks, guard and G-01`** · `M0` `golden` · S · Blocked by: T0.6 · §8.2
- Context: `tests/golden/cases/<id>.yaml` 형식(세션·단계별 기대 숫자), `tests/golden/check/<id>.py` 검산 규칙(사칙연산·반올림만), `test_handcalc_self.py`(AST: 루프·클래스·엔진 import 금지), `tests/repo/test_golden_guard.py`, `.github/CODEOWNERS`(`tests/golden/**` = 사용자), 사례 G-01(시가 시장가 매수, 임시 비용, 정수 최소 단위).
- Done means: `uv run python tests/golden/check/G-01.py`가 세션별 현금(최소 단위)·체결 수량 표를 출력하고 yaml 주석의 손 확인 숫자와 같다; 구현 브랜치에서 `cases/G-01.yaml`을 고치면 guard 시험이 실패한다.
- Acceptance: `tests/golden/test_handcalc_self.py::test_no_general_loops`, `::test_checks_import_no_engine`, `::test_case_G01_expected_present`; `tests/repo/test_golden_guard.py::test_impl_pr_cannot_edit_expected`.

#### M1 — 스냅숏 + Pipeline 조각 + 공개 첫 경로

**T0.7 `feat(testing): synthetic TDS package part 2 - corporate actions with revisions, delistings, tradability, eligibility, share counts`** (eligibility, share counts: #752의 R3에서 코드와 함께 빠짐) · `M1` `testing` · M · Blocked by: T0.6 · §4.8 (4)~(6) *(M1로, 정정·취소 사건, 늦은 회수 공개; 자격과 주식 수는 2026-11-24에 뺐다, #752)*
- Context: 사건 생성과 `EventSpec` 주입, 정정판(`revision_of`)·취소, `price_factor`·`share_factor`·`factor_method`, 사건이 가격에 적용한 것이 해석기 최신판과 맞음(2026-11-22까지는 `cum_factor_*`로, #705), `delistings`(일부 `ts_value_available` 늦음), `tradability_daily`(`availability_by_column`).
- Done means: `--preset small --validate` 출력에 정정·취소 사건 수 줄이 있고, 사건이 적용한 것에 대한 생성기의 기록이 검사기의 해석기와 맞는다(`test_factor_event_reconciliation`; 2026-11-22까지는 출력의 "TDS-A001: 0", #705).
- Acceptance: `test_synth.py::test_factor_event_reconciliation`, `::test_reverse_split_makes_factor_non_monotonic`, `::test_revisions_and_cancellations_present`, `::test_injected_event_overrides_random`, `::test_delisted_on_matches_delistings`.

**T0.8d `feat(testing): full-scale synthetic preset of the m1 datasets for the bench`** · `M1` `testing` · S · Blocked by: T0.7 · §4.8, §7
- Context: 4.8 표의 규모(상장 이력 KR 5,500 + US 22,100 종목, 1995-01-02 → 2024-12-31)로 `--preset full`을 만들되, 7장 M1 워크로드가 읽는 T0.6·T0.7의 데이터셋만 생성한다; 스냅숏 id는 `synth-full-m1-0001`. M2 데이터셋과 `full_ci`는 나중에 T0.8c가 더한다.
- Done means: 사람이 계산 기계에서 돌린 `python -m nexusbt.testing.synth --preset full --out DIR --validate`가 통과하고 행 수·시간·크기를 출력(수치는 마일스톤 추적 이슈에).
- Acceptance: `test_synth.py::test_full_preset_parameters_match_table`, `::test_full_is_small_rules_at_full_scale`(둘 다 CI에서 `full`을 만들지 않고 프리셋의 매개변수와 규칙만 확인).

**T0.14a `feat(tds): full-level key and reference checks`** · `M1` `tds` · M · Blocked by: T0.13c · TDS 8.3
- Context: `level="full"`의 K001~K011, R001~R009(판 열쇠 포함), 코드마다 pass/fail 패키지.
- Done means: 손으로 만든 conformance 패키지에서 각 코드가 정확히 하나씩; GICS level 1·3 행이 같은 효력·앎이어도 K001이 나지 않는다.
- Acceptance: `tds/tests/test_conformance.py::test_K_codes`, `::test_R_codes`, `::test_classification_levels_not_duplicate`.

**T0.14b `feat(tds): full-level time and density checks with rectangle lookup`** · `M1` `tds` · M · Blocked by: T0.14a · TDS 6.3, 8.3
- Context: T001~T013(T012 = 직사각형 두 시간축 조회의 유일성, 수준·판 사례), D001~D004, 참조 구현 `nexusbt_tds.pit.rect_lookup`(엔진도 같은 함수를 씀, 5.3.6).
- Done means: 미리 발표된 미래 효력 행이 있는 패키지에서 T012가 나지 않고, 진짜로 겹치는 두 행에서만 난다.
- Acceptance: `tds/tests/test_conformance.py::test_T_codes`, `::test_D_codes`, `::test_T012_rectangle_examples_1_to_5`.

**T0.15a `feat(tds): corporate action resolver parameterized by knowledge cutoff`** · `M1` `tds` · M · Blocked by: T0.14a · §5.3.3a, TDS 5.11
- Context: `nexusbt_tds.actions.resolve(events: pa.Table, cutoff) -> ResolvedActions`(사슬, 존재 시각 `ts_known`으로 고른 판, 상태, 조건 시각 `ts_terms` 대기, 네 효과, 정정 차이 계산 도우미, 늦게 알게 된 사건 표시, L0 열쇠용 사슬 정규 해시 `chain_digest(market, year_end)`). pyarrow만, 순수 함수. 엔진(`Snapshot.actions`)과, 2026-11-22까지는(#705) 검사기(A001)가 같은 함수를 쓴다.
- Done means: 예제가 한 종목의 정정 사슬을 세 기준 시각에서 푼 결과(고른 판·가격 계수·수량 계수·권리)를 표로 출력.
- Acceptance: `tds/tests/test_actions.py::test_resolver_at_cutoffs`(정정 분할·취소 배당·지급 뒤 정정·분할 + 배당 같은 날·권리 소멸·계수 없음 × 3 기준 시각), `::test_share_factor_explicit_not_inferred`, `::test_revision_cycle_A007`, `::test_late_terms_revision_visible_at_ex_date`, `::test_existence_time_ignores_effective_when_announced`, `::test_late_discovered_event_flagged`, `::test_chain_digest_includes_all_revisions_and_times`.

**T0.15b `feat(tds): adjustment and value checks via the resolver`** · `M1` `tds` · M · Blocked by: T0.15a · TDS 5.11, 8.3
- Context: A001~A009(A001은 2026-11-22까지(#705) 해석기 `c = +∞`로 정정 사슬마다 최신판 하나만 곱했다; A008 수량 사건 조건이 효력 뒤 공개; A009 분할설립 계수 공개 시각 < 효력 세션 종가), V001~V050.
- Done means: 역분할이 있는 패키지에서 계수가 단조가 아니어도 A001이 나지 않고, 정정 사슬의 옛 판과 새 판을 둘 다 곱한 계수는 A001로 잡힌다(A001은 2026-11-22 `cum_factor_*`와 함께 은퇴, #705; 역분할 테스트는 이제 어느 A 코드도 나지 않음을 본다).
- Acceptance: `tds/tests/test_conformance.py::test_A_codes`, `::test_V_codes`, `::test_reverse_split_not_flagged`; 2026-11-22까지는 `::test_A001_multiplies_latest_revision_once`도.

**T0.16a `feat(testing): degraded synthetic packages for core fallbacks`** · `M1` `testing` · M · Blocked by: T0.7, T0.15b · §4.5, §4.8
- Context: `degrade=` 중 core 자료 값: `no_ohlc`, `kr_ex_is_record`, `us_div_split_adjusted_no_dates`, `no_delistings`(`no_cum_factors`는 2026-11-22에 빠짐: 생성기가 `cum_factor_*`를 쓰지 않는다, #705; `no_sessions`는 2026-11-23에 F-02와 함께 빠짐: `calendar_sessions` 없는 패키지는 열 때 E14, #705; `sparse_bars`는 2026-11-23에 F-03과 함께 빠짐: 일봉은 dense, TDS 5.5, #705); 각 값이 지키지 못하는 프로필을 선언에서 뺌(검사는 여전히 통과).
- Done means: `--preset small --degrade no_ohlc,kr_ex_is_record --validate`가 선언 프로필(core 없음)과 세 결과를 출력한다.
- Acceptance: `test_synth.py::test_synth_conforms_degraded_core[<각 값>]`(테스트의 `DROPS_CORE` 값마다 하나), `::test_degrade_drops_declared_profiles`.

**T1.G `test(golden): time and pipeline cases for M1 (T-07, T-09..T-12, T-15, T-20, T-23)`** · `M1` `golden` · M · Blocked by: T0.9, T0.7 · §8.2
- Context: 분할·역분할 앞뒤 창, 기호 재사용, 휴장 시작일, 동률, 12-1 모멘텀 세 식, null 계수 창, 늦은 봉 `ready_delay`, `every(n)` 달력 닻. 사례마다 yaml 숫자 + 검산 파일. 다른 세션에서 쓰고 소비 티켓(T1.3, T1.8, T1.9, T1.11) 전에 병합.
- Done means: `uv run python tests/golden/check/T-12.py`가 세 식의 같은 값을, `T-20.py`가 늦은 봉이 제 행에 머물고 판단이 `ready`가 그 `ts_available`에 이른 첫 행부터 쓰는 표를 출력.
- Acceptance: `test_handcalc_self.py::test_time_cases_M1_expected_present`.

**T1.1a `feat(data): open TDS snapshots with checker, producer-neutral errors and market rules packs`** · `M1` `data` · M · Blocked by: T0.3, T0.4, T0.5b, T0.13c, T0.14c, T0.6 · §4.1–4.4, §4.7
- Context: `open_snapshot`, `LATEST` 해석, 검사 단계, 경로 안전, E14(TDS 코드 + `producer.hints`), 판 규칙(M011 경고·M014 E14), 시장마다 규칙 팩 확인(없으면 E18, `allow_untested` 기록), `Snapshot.semantic_hash/value_hash/physical_hash`, `.markets`.
- Done means: 합성 small에서 `s.id, s.semantic_hash, s.markets`를 출력; `markets=("KR","ZZ")` 스냅숏에서 `nx.universe("ZZ")`가 E18("no market rules pack for ZZ"); `producer.hints`가 있는 깨진 패키지의 E14에 힌트 문장이 붙는다.
- Acceptance: `tests/unit/data/test_open_snapshot.py::test_latest_resolved_once`, `::test_E14_carries_tds_code_and_hint_not_ticket`, `::test_unknown_required_rule_E14`, `::test_market_without_pack_E18`, `::test_allow_untested_recorded`, `::test_semantic_hash_exposed`, `::test_open_path_and_latest_parent`(`nx.open`·`[data] path`), `::test_cloned_and_hardlinked_partitions_ok`, `::test_malformed_exact_ratio_E13`, `::test_missing_exact_ratio_excludes_instrument_from_event`(기본 `exclude_instrument`: 스냅숏은 열리고 그 종목만 사건이 보이는 시각부터 빠진다).

**T1.1b `feat(data): capabilities, profile results, core fallbacks and pins`** · `M1` `data` · M · Blocked by: T1.1a, T0.16a · §4.3–4.5, §4.2
- Context: `CapabilityRequest`(그래프가 쓰는 기능 → 필요 자료, 4.3 표), 프로필 세 결과, `capabilities`·`fallbacks`, F-02(세션 표 대체; 2026-11-23 은퇴, #705)·F-03(밀집화; 2026-11-23 은퇴, #705)·F-04(계수는 해석기에서; 2026-11-22 은퇴, #705), 선언 위반 패키지는 E14(대체 없음), 핀(색인 + 루트가 기본, 실패는 경고 + `retention: unmanaged`), `verify` 도장(`runs/.cache/verified/`, 파일마다 `(dev, inode, size, mtime_ns)`).
- Done means: `Price`만 쓰는 그래프가 core 데이터셋만 있는 패키지에서 돌고; 테스트되지 않은 시장 ZZ가 있는 `degrade=["no_tick_info"]` 스냅숏에서 E30 한 줄과 `s.fallbacks`에 F-15(은퇴 전에는 F-02의 `no_sessions`와 F-03의 `sparse_bars`, 2026-11-23, #705); 읽기 전용 자료 루트에서 실행이 되고 핀은 색인에 있다; 파일 하나를 바꾸면 `verify="full"`에서 E14(`TDS-H001`); 도장 뒤에 파일 하나를 제자리에서 고치면 다음 열기에서 신원이 달라 sha256을 다시 계산하고 E14.
- Acceptance: `test_open_snapshot.py::test_three_status_distinct`, `::test_price_only_graph_needs_core_only`, `::test_declared_but_broken_is_E14_not_fallback`, `::test_full_verify_detects_tamper`, `::test_readonly_root_runs`, `::test_pin_in_index`, `::test_a_package_without_calendar_sessions_is_e14_at_open`(`::test_fallback_F02_sessions` 대신, F-02는 2026-11-23 은퇴, #705), (`::test_fallback_F03_densify`는 F-03과 함께 빠짐, 2026-11-23, #705), `::test_fallback_F04_factors_from_resolver`, `::test_fallbacks_fail_mode_raises_E14`, `::test_volume_unit_warning_lifted_E30`, `::test_fallback_F15_grid_minor_unit`, `::test_verified_stamp_detects_later_tamper`, `::test_inplace_edit_invalidates_stamp_and_l0`, `::test_readonly_package_all_consumption_paths`, `::test_default_pins_written_to_root_or_warn`, `::test_default_pin_survives_three_publications`, `::test_bars_keep_ts_available` (G-TIME-LATE: 연 스냅숏이 봉마다 `ts_available`을 지님).

**T1.2 `feat(cli): nexusbt init and doctor`** · `M1` `cli` · S · Blocked by: T1.1b · §3.10
- Done means: `uv run nexusbt init --data-root .scratch/snap && uv run nexusbt doctor`가 스냅숏 id, 의미 해시, 판, 프로필 세 결과, 검사 안 한 항목, 대체 목록, 시장별 규칙 팩·기간·종목 수·일간 행 수, 칼럼 수, 디스크 여유를 출력; 루트에 `.publishing`이 있으면 "publishing in progress"; 루트 핀을 못 쓴 실행 수 줄 "pins not visible to producer".
- Acceptance: `tests/unit/cli/test_doctor.py::test_doctor_lists_markets_packs_and_counts`, `::test_doctor_lists_fallbacks_and_unchecked`, `::test_init_uses_env_root`, `::test_publishing_marker`, `::test_pins_not_visible_line`.

**T1.3 `feat(data): calendars, session rounding, ready times, phases and decision grids`** · `M1` `data` · M · Blocked by: T1.1b, T1.G · §5.1.2, §5.1.3, §5.1.6, §5.6.3, §3.7 일정
- Done means: 이 티켓이 만드는 `examples/dev/show_grid.py`(월간 일정, KR, 2019년)가 12개 월말 세션과 `decision_ts`(UTC)를 출력; 휴장 시작일에 E9 알림; `every(5)`의 판단 날짜가 시작일을 하루 옮겨도 같다.
- Acceptance: `tests/unit/data/test_calendar.py::test_monthly_last_session`, `::test_start_rounds_forward_end_backward` (T-10), `::test_weekly_quarterly`, `::test_T23_every_anchor_independent_of_start`, `::test_ready_delay_from_availability_rule`, `::test_default_clock_codepoint_first_market`, `tests/golden/test_time.py::test_T20_late_bar_ready_delay`, `::test_G_TIME_LATE_ready_and_late_bar` (G-TIME-LATE: 8.4 표의 `ready(t)`와 `LateBar` 개수; 결정 2026-11-10, #356: 이 티켓이 기대는 티켓에는 `SMA`·`top`·주문이 없으므로 표의 나머지는 뒤 단계가 시험 하나씩 맡는다. T1.4는 행, T1.9는 A의 `SMA(3)`, T1.11은 목표, T3.4는 주문 의도).

**T1.4 `feat(data): dense market blocks from daily bars`** · `M1` `data` · M · Blocked by: T1.3 · §5.3.1, §4.6, §5.3.9 L0 열쇠
- Context: `market_block`, 사전 색인 → 열 번호, `obs_status`, 존재 마스크, 꼬리 겹침, 매니페스트 통계로 파일 고르기, 지수·합성 종목 제외, `l0_key(...)` 함수(캐시 구현은 T6.12).
- Done means: `Snapshot.market_block("KR", ["close"], sessions)`의 모양·존재 마스크를 출력하는 예제가 정지 세션 NaN과 상장 전 False, 지수 종목 없음을 보여 줌.
- Acceptance: `tests/unit/data/test_market_block.py::test_obs_status_halted_is_nan`, `::test_existence_mask`, `::test_index_and_synthetic_not_in_block`, `::test_dictionary_index_mapping_matches_instrument_ids`, `::test_tail_overlap_rows`, `::test_partition_values_from_path`, `::test_l0_key_partition_scoped`, `::test_l0_key_ignores_watermark`, `::test_l0_key_ignores_advisory_value_hash`, `::test_late_bar_stays_in_its_row` (G-TIME-LATE: s의 봉은 그 `ts_available`과 함께 행 s에 있고 행 s+1에 가지 않음), `::test_l0_key_axis_rows_invalidation_table`(2026-11-04: 5.3.9 표의 네 행이 말한 연도의 열쇠만 정확히 바꿈), `::test_l0_key_ignores_axis_rows_outside_the_year`.

**T1.5 `feat(pipeline): term value objects, operators, graph hash and captured constants`** · `M1` `pipeline` · M · Blocked by: T0.2a · §3.3, §5.3.9, §6.5(6)
- Done means: `print(nx.describe(Returns(232).shift(21) + 1))`가 노드 트리와 구조 해시를 출력; 같은 식 두 번 → 같은 해시; 사용자 함수가 읽는 `THRESHOLD = 10`을 20으로 바꾸면 해시가 바뀐다.
- Acceptance: `tests/unit/pipeline/test_terms.py::test_operator_result_types`, `::test_negative_shift_raises_E1`, `::test_graph_hash_stable_and_order_sensitive`, `::test_pipeline_object_columns_screen`, `::test_captured_scalar_changes_hash`.

**T1.6 `feat(pipeline): datasets from TDS dictionaries and type stubs`** · `M1` `pipeline` · M · Blocked by: T1.1b, T1.5 · §3.2
- Done means: `uv run nexusbt stubs` 뒤 편집기에서 `Price.`·`Meta.` 자동 완성; `Price.clsoe` → E7 "Did you mean: close"; `Meta.country`가 `Meta.market` 별칭으로 동작; `Meta.delisted_on`은 없음(E7).
- Acceptance: `tests/unit/pipeline/test_datasets.py::test_price_columns_fixed`, `::test_typo_suggestions`, `::test_stub_file_generated`, `::test_meta_aliases`, `::test_meta_has_no_hindsight_columns`, `::test_is_label_columns_only_in_Label`, `::test_schema_registry_injected_at_binding`.

**T1.7a `feat(compute): planner with window and shift row propagation`** · `M1` `compute` · M · Blocked by: T1.4, T1.5 · §5.3.2
- Done means: `nx.run_pipeline(..., freq="monthly")` 디버그 로그가 "rows computed: X of Y"를 보여 월간이 일부 행만 계산함을 확인; 중첩 창 + shift가 묶음 경계를 넘어도 필요한 행이 맞다.
- Acceptance: `tests/unit/compute/test_planner.py::test_window_rows_propagate`, `::test_shift_rows_propagate`, `::test_nested_windows_across_chunks`, `::test_shared_node_computed_once`, `::test_daily_cross_section_feeding_window_computed`.

**T1.7b `feat(compute): reference executor with fixed summation order and budgeted chunking`** · `M1` `compute` · M · Blocked by: T1.7a · §5.3.8, §5.3.10
- Done means: 참조 합 함수가 `np.sum`과 다른 순서 사례에서 왼쪽 접기 값을 내고; `memory_budget_gb`가 작으면 묶음이 분기·월로 나뉘어도 결과가 같다.
- Acceptance: `tests/unit/compute/test_reference_numerics.py::test_left_fold_order_defined`, `::test_no_numpy_pairwise_in_reference`, `::test_transcendental_uses_compiled_elementwise`; `tests/unit/compute/test_chunking.py::test_sub_year_chunks_when_budget_small`; `tests/unit/test_import_rules.py::test_kernel_seam_signatures_arrow_only`(`nx.compute._kernels` 이음새); `tests/unit/compute/test_executor.py::test_chunk_boundary_values_equal_unchunked`, `::test_cutoff_hides_late_cells`(결정 2026-11-10, #356: P-CHUNK와 P-FUT 가운데 내장 팩터나 선택이 필요 없는 부분을 T1.19보다 먼저 실행기에서 시험).

**T1.8 `feat(compute): as-of adjustment reference and registered kernel classes`** · `M1` `compute` · M · Blocked by: T1.7b, T0.15a, T1.G · §5.3.3, §5.3.3a, §5.3.4, §4.6(null 계수)
- Done means: 분할·역분할 사건 앞뒤 창을 출력하는 예제가 T-07 사례와 같은 숫자; `price_factor` null 사건 앞 행이 NaN이고 `AdjustmentUnavailable` 건수가 출력됨; 정정된 분할 비율이 기준 시각에 따라 다른 창을 낸다.
- Acceptance: `tests/golden/test_time.py::test_T07_split_reverse_split_windows`, `::test_T15_unavailable_factor_masks_window`, `tests/unit/compute/test_adjust.py::test_revision_changes_window_by_cutoff`, `tests/property/test_adjust.py::test_P_ADJ_kernel_classes`.

**T1.9 `feat(factors): returns, moving averages, volatility and traded value`** · `M1` `factors` · M · Blocked by: T1.8, T1.Gb · §3.4, §5.3.10
- Context: Returns, DailyReturns, SMA, AverageDollarVolume, AverageTradedValue, AnnualizedVolatility, RollingStd(참조 구현, 왼쪽 접기 정의).
- Done means: 3.4 표의 행마다 기본 입력·결측·최소 관측·준비 규칙을 보여 주는 단위 시험이 통과; T-12 통과.
- Acceptance: `tests/unit/factors/test_conformance.py::test_<name>_nan_rule` (7개), `::test_returns_default_is_close_tr`, `tests/golden/test_time.py::test_T12_momentum_forms_equal`, `tests/golden/test_factors.py::test_T25_<name>`(7개, v3.1), `tests/golden/test_time.py::test_G_TIME_LATE_sma_values`(G-TIME-LATE: 늦은 봉이 s에서 NaN일 때 A의 `SMA(3)` 10.5, 12, 15, 앞 스냅숏과 뒤 스냅숏에서 행 s와 s+1이 같음; 결정 2026-11-10, #356).

**T1.10 `feat(factors): ewma, vwap, rsi, max drawdown and ops`** · `M1` `factors` · M · Blocked by: T1.9, T1.Gb · §3.3, §3.4
- Done means: `nx.describe(nx.factors)`가 12개 내장 팩터와 기본 입력·조정 등급·수치 등급을 표로 출력(2026-11-24의 수익 계열 커널 셋은 T2.19와 함께 표에 듦).
- Acceptance: `test_conformance.py::test_ewma/vwap/rsi/maxdd_*`, `::test_ewma_weights_precomputed`, `tests/unit/pipeline/test_ops.py::test_rolling_min_periods`, `::test_coalesce_explicit_fill`, `tests/golden/test_factors.py::test_T25_<name>`(5개, v3.1).

**T1.11 `feat(compute): cross-sectional operators with mask and groupby, sorted-index reductions`** · `M1` `compute` · M · Blocked by: T1.7b, T1.Gb · §5.4, §5.3.10, ADR-0019
- Done means: 동률 예제에서 `rank(method="ordinal")`가 `tiebreak="id"`면 `instrument_id` 순(T-11), 기본 hash면 T-27 순으로 1,2,3을 주는 출력; 메모리 열 순서를 섞어도 `zscore`가 비트 같음을 출력.
- Acceptance: `tests/unit/compute/test_crosssection.py::test_zscore_ddof0_zero_var_nan`, `::test_top_stable_ties`, `::test_unknown_group_counted`, `::test_quantiles_preserve_ties`, `::test_reduction_in_instrument_id_order`, `::test_rank_ordinal_uses_tiebreak_key`, `tests/golden/test_time.py::test_T11_ties`, `::test_G_TIME_LATE_target`(G-TIME-LATE: 표의 `SMA(3)` 값을 입력으로 준 목표 B, B, A; 결정 2026-11-10, #356).

**T1.12 `feat(pipeline): window-style user functions`** · `M1` `pipeline` · M · Blocked by: T1.8, T1.11 · §3.3, §5.3.7, §6.5 (5)(6)
- Done means: 3장 예제 `mom_12_1_custom`(253행)가 돌고, `close[-273]`을 쓰면 E8 "window=273" 제안이 나온다; 전역 배열을 읽으면 E24와 "L1 cache disabled for node".
- Acceptance: `tests/unit/pipeline/test_user_functions.py::test_window_is_asof_adjusted`, `::test_out_of_window_index_E8`, `::test_global_array_read_E24_disables_l1`, `::test_source_hash_includes_helpers`, `::test_user_exception_keeps_user_frame`.

**T1.14a `feat(artifacts): sealed run folders with crash recovery and source capture`** · `M1` `artifacts` · M · Blocked by: T0.5a · §5.9.1–5.9.3, §2.6
- Done means: 실행 뒤 `ls runs/<id>`에 `manifest.json`·`SEALED`·`source/`가 있고 파일이 읽기 전용; 실패 실행은 폴더 없이 색인에 aborted; 이름 바꾸기와 봉인 사이에 죽인 실행을 다시 열면 복구되거나 aborted로 옮겨진다.
- Acceptance: `tests/unit/artifacts/test_runstore.py::test_seal_only_on_success`, `::test_interrupted_seal_recovers`, `::test_sources_captured_with_helpers`, `::test_value_hash_ignores_created_at`, `::test_no_pickle_files_written`.

**T1.14b `feat(artifacts): run index with candidates, observations, cohorts, pins and environment numerics`** · `M1` `artifacts` · M · Blocked by: T1.14a · §5.9.2, §5.9.5
- Done means: `sqlite3 runs/index.sqlite '.tables'`가 `studies runs candidates observations cohorts exposures preregistrations pins books`를 보이고; `manifest.json`에 `environment.numerics`와 `machine_id`.
- Acceptance: `tests/unit/artifacts/test_index.py::test_append_only_triggers`, `::test_tables_match_spec`, `::test_pins_canonical_in_index`, `::test_preregistration_claim_and_look_columns`(5.9.5의 `preregistrations` 주장 열과 `runs.conditions_hash`, `runs.preregistration_id`, `runs.look_number`, #269), `tests/unit/artifacts/test_runstore.py::test_environment_numerics_recorded`.

**T1.13 `feat(api): run_pipeline and factor screen`** · `M1` `api` · M · Blocked by: T1.12, T1.14b · §3.5, §3.8 screen
- Done means: `uv run python examples/m1_screen.py`가 기준일 시장별 모멘텀 상위 10과 `run_id`를 출력.
- Acceptance: `tests/unit/api/test_run_pipeline.py::test_output_schema_and_sort`, `::test_screen_rows_filtered`, `::test_markets_from_snapshot`, `tests/unit/api/test_screen_factor.py::test_top_per_market`.

**T1.15 `feat(api): rerun in a fresh process with input stamp, replay failure and trust gate`** · `M1` `api` · S · Blocked by: T1.13 · §3.8 rerun, §5.9.3, §2.6
- Done means: `uv run nexusbt rerun <id>`가 "outputs identical (value, physical)"; 스냅숏 폴더 이름을 바꾸면 E15; Parquet 바이트를 바꾸면 E15(의미·물리 불일치); 작업 폴더의 도우미 모듈을 고쳐도 rerun은 잡은 소스로 같은 값; 매니페스트 `machine_id`를 바꾼 실행 폴더는 E31, `--trust`면 돈다.
- Acceptance: `tests/unit/api/test_rerun.py::test_rerun_identical`, `::test_missing_snapshot_E15`, `::test_tampered_parquet_detected`, `::test_archived_helpers_override_local`, `::test_new_snapshot_is_new_run`, `::test_foreign_run_requires_trust_E31`.

**T1.16 `feat(compat): zipline CustomFactor and USEquityPricing shim`** · `M1` `compat` · S · Blocked by: T1.12 · §3.4, 설계 3.4
- Done means: 설계 3.4의 zipline `Mom(CustomFactor)` 코드가 `from nexusbt.compat.zipline import ...`로 바뀐 import만으로 돈다.
- Acceptance: `tests/unit/compat/test_zipline_shim.py::test_compute_signature`, `::test_usequitypricing_close_is_close_tr`.

**T1.17 `test(parity): isolated zipline env, bundle writer from TDS, L1-a and L1-b`** · `M1` `parity` · M · Blocked by: T1.10, T1.16, T0.10 · §8.1
- Done means: `engine / parity` job 로그에 L1-a·L1-b 사례별 `max_rel`이 허용 오차 아래로 나오고(배당 낀 창 포함) 증거 JSON(요약만, "parity does not imply realism", 축척한 종목 수)이 생긴다.
- Acceptance: `tests/parity_compare/test_L1.py::test_L1a_price_terms_default_inputs`, `::test_L1b_adjustment_windows`, `::test_price_scale_for_uint32_overflow`.

**T1.18 `test(parity): L1-d masks and classifiers, known differences`** · `M1` `parity` · S · Blocked by: T1.17 · §8.1
- Done means: `tests/parity/KNOWN_DIFFERENCES.md`가 있고 L1-d 사례가 8.1 표대로 같음(집합·순위는 정확히, `zscore` 값은 L1-a의 허용 오차 안; ADR 0046).
- Acceptance: `test_L1.py::test_L1d_top_rank_zscore_percentile_quantiles`, `::test_L1d_known_differences_listed`.

**T1.19 `test(property): chunk, permutation, future-data, determinism and kernel invariants for pipelines`** · `M1` `property` · M · Blocked by: T1.13 · §8.3
- Done means: `uv run pytest -m property -k "CHUNK or PERM or FUT or DET or KERNEL"`가 통과하고 사례 수를 출력.
- Acceptance: `tests/property/test_pipeline_invariants.py::test_P_CHUNK`, `::test_P_PERM`, `::test_P_FUT_pipeline`, `::test_P_DET_pipeline`, `tests/property/test_kernels.py::test_P_KERNEL_reference_is_left_fold`; `test_P_CHUNK`와 `test_P_FUT_pipeline`은 `small`과 함께 늦은 봉 합성 변형(#354)에서도 돌린다(결정 2026-11-10, #356).

**T1.21 `test(property): start-date and metamorphic invariants with preconditions`** · `M1` `property` · M · Blocked by: T1.19 · §8.3, INV-14, INV-15 [SC-04]
- Context: P-START(1·21·252세션, `every(n)` 포함), M-SCALE, M-DUMMY, M-SPLIT-NEUTRAL — 각 성립 사례(전제를 만족하는 무작위 그래프)와 반례(가격 문턱, mask 없는 zscore) (M-CCY·M-SLEEVE는 T4.8).
- Done means: `uv run pytest -m property -k "START or SCALE or DUMMY or SPLIT_NEUTRAL"` 통과, 사례 수와 반례 수 출력.
- Acceptance: `tests/property/test_metamorphic.py::test_P_START`, `::test_M_SCALE`, `::test_M_SCALE_counterexample_threshold`, `::test_M_DUMMY`, `::test_M_DUMMY_counterexample_unmasked`, `::test_M_SPLIT_NEUTRAL`; `test_P_START`는 늦은 봉 합성 변형(#354)에서도 돌린다(결정 2026-11-10, #356).

**T1.22 `feat(tds): import csv with mapping.yaml and minimal-daily packages`** · `M1` `tds` · M · Blocked by: T0.14c, T0.13c · TDS 7·9.5, §4.3
- Context: `tds import csv MAPPING.yaml --out PKG`(TDS 9.5: 칼럼 대응, `template`, 날짜 형식, `missing_values`, 시장 선언, `price_basis`), 패키지 작성(정렬·파티션·해시·`pit_quality = backfilled` 기본), `tds:minimal-daily@1.0` 선언, 변환 보고서(`import_report.json`: 보존·가정·버린 행).
- Done means: TDS 7장의 CSV 두 개로 `tds import csv` → `tds check --level full`이 통과하고 프로필 세 결과를 출력.
- Acceptance: `tds/tests/test_import_csv.py::test_minimal_two_csv`, `::test_mapping_template_and_format`, `::test_offsetless_time_requires_timezone`, `::test_import_report_written`.

**T1.23 `feat(tds): manifest build for an existing folder`** · `M1` `tds` · S · Blocked by: T1.22 · TDS 8.1
- Context: `tds manifest build PKG`(폴더를 훑어 `tds.json` 초안: 데이터셋·파일·통계·해시; 파일에서 알 수 없는 필수 항목은 비워 두어 `tds check`가 M003로 알리고, 공개 규칙은 `"TODO"`로 적어 `tds check`가 M014로 알리며, 설명은 파일 맨 위 `TODO` 목록에만 적음).
- Done means: Parquet 몇 개가 든 폴더에서 `tds manifest build`가 초안을 쓰고, `TODO`를 채운 뒤 `tds check`가 통과.
- Acceptance: `tds/tests/test_manifest_build.py::test_draft_lists_files_and_stats`, `::test_todo_fields_flagged`.

**T1.24 `feat(bench): benchmark harness and early stage measurements`** · `M1` `bench` · M · Blocked by: T1.13, T0.8d · §7
- Context: `bench/run.py`(워크로드·반복·p50/p95/최대·프로세스 트리 RSS·USS 합·JIT 첫 지연·캐시 상태), `--stages m1`(P1·열기·블록 읽기·조정·`SMA(252)` 일간 전체 행(ADR-0019 정의 A)·단면) 측정, 단계마다 7장이 정한 cold와 warm, #144나 #148이 열려 있는 동안 warm 수치에 `provisional: true`, 결과 JSON(요약만).
- Done means: `uv run python bench/run.py --stages m1 --reps 3 --snapshot synth-small`가 단계별 p50/p95와 RSS/USS JSON을 출력; 사람이 계산 기계에서 돌린 `bench/run.py --stages m1 --reps 10 --snapshot synth-full-m1-0001`가 M1 단계마다 cold·warm p95와 프로세스 트리 USS 합을 출력(수치는 마일스톤 추적 이슈에); PR 설명에 ADR-0019 A 유지/B 전환 판단 근거 한 줄. 이 측정은 T1.19와 T1.21이 늦은 봉 합성 변형에서 통과한 뒤에만 M1 증거(R2, 10.0)로 세고, 그 전에 돌린 것은 프로파일링이며 그렇게 기록한다(결정 2026-11-10, #356).
- Acceptance: `tests/unit/bench/test_harness.py::test_result_schema`, `::test_no_paths_in_results`, `::test_process_tree_memory_summed`, `::test_output_value_hash_in_results`, `::test_cold_and_warm_p95_per_stage`, `::test_warm_marked_provisional_while_cache_keys_open`.

**T1.Gb `test(golden): v3.1 filter, builtin-factor and tie-break cases (T-24, T-25, T-27)`** · `M1` `golden` · S · Blocked by: T0.9 · §5.4.1, §3.4, §3.7, §8.2
- Context: T-24(3값 Filter 표), T-25(M1의 내장 팩터 12종마다 NaN 위치를 넣은 5행 손계산 사례; 2026-11-24의 수익 계열 커널 셋은 만들어지기 전에 자기 사례를 받음 `tests/golden/factors/<name>.yaml` + 검산 파일), T-27(고정 소금 해시 동률). 소비 티켓 T1.9·T1.10·T1.11·T1.25 전에 병합.
- Done means: `uv run python tests/golden/check/T-25.py`가 12종의 기대 값을 표로, `check/T-27.py`가 세 종목의 해시 열쇠와 순서(T00002, T00001, T00003)를 출력.
- Acceptance: `test_handcalc_self.py::test_cases_v31_M1_expected_present`.

**T1.25 `feat(pipeline): three-valued filters with validity masks`** · `M1` `pipeline` · M · Blocked by: T1.11, T1.Gb · §3.3, §5.4.1, §5.9.9
- Context: Filter 노드가 값과 유효 마스크를 든다; 비교의 결측 = 모름, `~` 유효 그대로, `&`·`|` Kleene, `if_else` 모름 → NaN, 최종 사용처(`universe`, 선택, `mask`, `screen`)에서 모름 = 거짓; `explain`의 "unknown (input NaN: …)".
- Done means: T-24 표가 그대로 출력되고 `~(Price.close.latest > 10_000)` 유니버스에 정지 종목이 없다.
- Acceptance: `tests/golden/test_time.py::test_T24_filter_unknown`, `tests/unit/pipeline/test_filters.py::test_kleene_and_or`, `::test_not_keeps_unknown`, `::test_isnan_always_valid`, `::test_final_use_unknown_is_false`, `::test_all_any_kleene`, `::test_as_factor_unknown_nan`, `::test_classifier_missing_is_unknown`, `::test_pipeline_screen_unknown_false`.

**T1.27 `test(repo): determinism source bans and cross-process hash-seed runs`** · `M1` `repo` · S · Blocked by: T1.19 · §2.5, INV-09
- Context: ruff `banned-api`에 결정 경로 모듈의 벽시계·난수·`uuid4`·`os.urandom` 추가, AST 시험(정렬 없는 `set`/`frozenset` 순회가 사건·출력 순서를 정하는 곳 탐지), P-DET를 `PYTHONHASHSEED` 다른 새 프로세스 둘로.
- Done means: 일부러 `datetime.now()`를 `accounting`에 넣은 가지에서 시험이 실패하고, 두 프로세스 실행의 출력 해시가 같다는 줄이 나온다.
- Acceptance: `tests/unit/test_determinism_rules.py::test_no_wallclock_or_rng_in_decision_modules`, `::test_no_unsorted_set_iteration_in_event_paths`, `tests/property/test_pipeline_invariants.py::test_P_DET_cross_process_hashseed`.

**T0.15c `feat(tds): v1.2 checks - exact ratios and delisting distributions`** · `M1` `tds` · S · Blocked by: T0.15b, T0.14c · TDS 5.11·5.13·8.3
- Context: TDS 오류 A010(v1.4 E: 주식 수를 바꾸는 사건에 `ratio_num/ratio_den` 없음·한쪽만·0 이하·f64 비율과 불일치), 경고 A011(분배 포함 여부 모름), 코드마다 pass/fail 패키지.
- Done means: `uv run tds check tds/conformance/TDS-A010/fail --format json --level full`(기본 단계 `schema`는 행을 읽지 않는다; 결정 2026-11-10, #229)이 빠진 행·한쪽만 있는 행·0 행·불일치 행 네 줄을 오류(E)로 내고 프로필 불합격을 출력한다.
- Acceptance: `tds/tests/test_conformance.py::test_A010`, `::test_A011`.

**T0.15d `feat(tds): v1.2 checks - volume unit, price grid and advisory file value hashes`** · `M1` `tds` · S · Blocked by: T0.15b, T0.14c · TDS 4.2·5.5·5.27·8.3
- Context: V011(거래량 단위 의심), V012(가격이 선언된 격자·최소 단위 정수에서 1e-9 상대 넘게 벗어남), H004(`files[].value_sha256` 불일치 — 조언용 필드), `market_rules` 스키마·키 검사(`verified` 칼럼 포함), 코드마다 pass/fail 패키지.
- Done means: `uv run tds check tds/conformance/TDS-V011/fail --format json --level full`(기본 단계 `schema`는 행을 읽지 않는다; 결정 2026-11-10, #229)이 `TDS-V011` 한 줄(종목·연도, R = 100)을 내고 pass 패키지(R = 1)는 경고 0.
- Acceptance: `tds/tests/test_conformance.py::test_V011`, `::test_V012`, `::test_H004`, `tds/tests/test_schemas.py::test_market_rules_schema_stable_optional`.

**T0.16c `feat(testing): v1.2 synthetic fields and degrades`** · `M1` `testing` · S · Blocked by: T0.7, T0.15c, T0.15d · §4.8
- Context: `ratio_num/ratio_den`과 그 f64 몫(1:3·1:7·0.29 포함), 폐지 직전 분배 + 플래그, 정지 기간 안 분할·배당, 원가격을 팩 격자에 맞추고 일부 1 ULP 흔들림, `market_rules` 씨앗, `degrade=["no_tick_info", "volume_in_lots"]`.
- Done means: `--preset small --validate`가 "exact ratios: n, distributions before delisting: k, off-grid rows: 0"을 출력하고 `--degrade volume_in_lots`는 V011 경고 수를 보인다.
- Acceptance: `test_synth.py::test_exact_ratios_present`, `::test_prices_on_grid_with_ulp_noise`, `::test_volume_in_lots_triggers_V011`, `::test_synth_conforms_degraded_core[no_tick_info]`.

#### M1b — 첫 백테스트 끝-끝 (얇은 조각)

얇은 백테스트(#858, 소유자, 2026-11-28): 한 실행에 한 시장(KR 또는 US), 롱온리, 그 시장의 통화; 일정(월간 또는 일간), M1 파이프라인이 계산하는 팩터 위의 `top(n)`, 동일 가중; 종가에서 판단, 다음 세션 시가에 체결되는 시장가 주문, 정수 주, 정지되거나 빠진 봉에서는 체결 없음, 거래량 상한과 가격 제한 논리 없음; 정수 최소 단위 원장과 일별 잔고; 현금 배당(배당락일에 권리, 지급일에 현금), 정확한 비율이 있는 주식 수 변경 사건, 관측된 종료 가치가 있는 상장 폐지를 거치는 보유; 비용 코드 없음, 그리고 비용이 포함되지 않았다고 말하는 줄(#841 Decisions, 2026-11-27). 그 밖의 것은 만들어지지 않은 기능처럼 E18로 멈춘다(6.6).

- decided (#858, 2026-11-28): T3.23(팩의 금액 반올림)과 T3.24(가격 격자)는 M1b에 없다: M1b가 기록하는 모든 항목(체결, 배당, 단주 현금, 종료 금액)은 모든 팩에서 최소 단위로 half_up이고(5.6.1), 격자는 주문 가격과 가격 제한 비교에만 쓰인다(5.6.4a); 0이 아닌 원천징수나 사용자의 `[rounding.<MARKET>]`는 T3.10·T3.23까지 E18이다.

**T3.Gg `test(golden): first-backtest cases (G-12, G-15..G-19, G-22, G-30, G-34, G-45, G-46, G-48, G-53..G-55, G-60, G-61)`** · `M1b` `golden` · M · Blocked by: T0.9, T0.15a · §5.6.3–5.6.13, §5.7, §8.2
- Context: M1b 티켓들이 쓰는 사례를 T3.Ga(G-12, G-15), T3.Gc(G-16~G-19, G-22, G-30, G-34, G-45, G-46, G-48), T3.Gd(G-53~G-55), T3.Ge(G-60, G-61)에서 가져오고 나머지는 그 티켓들에 남는다. 소비 티켓 T3.3·T3.4·T3.5d·T3.9·T3.10a·T3.11a·T3.12·T3.13c·T3.22a 전에 병합.
- Done means: `uv run python tests/golden/check/G-12.py`가 세션별 현금(최소 단위)·체결·`cancelled_qty`를 출력; `uv run python tests/golden/check/G-60.py`가 PSR 0.759233과 "excess-kurtosis value 0.915240 is wrong" 줄을 출력.
- Acceptance: `test_handcalc_self.py::test_cases_first_backtest_expected_present`.

**T2.4a `feat(pipeline): the basic universe of one market`** · `M1b` `pipeline` · S · Blocked by: T1.13 · §3.6
- Context: 한 시장의 `nx.universe("KR")`: 그 세션에 상장된 종목(`listed_on <= session <= last_session`), 시장 이름은 스냅숏에서. 소형주 스위치, 제외 이유, 고정 목록은 T2.4에 남는다.
- Done means: 합성 small에서 `nx.universe("KR")`의 세션별 종목 수를 같은 세션의 상장 종목 수와 나란히 출력; 스냅숏에 없는 시장 이름은 E16.
- Acceptance: `tests/unit/pipeline/test_universe.py::test_listed_that_session`, `::test_unknown_market_E16`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #249; #752 Decisions, 2026-11-26): `nx.screen(factor, top=n)`은 3.3 기본 영역의 상장된 칸에서 고르고 `universe: listed (the default universe comes with T2.4)`라고 말하며, 시험 하나가 그 줄을 지킨다. 이 티켓이 3.6의 기본 유니버스 안에서 고르게 하고 그 줄과 시험을 바꾼다.

**T2.7a `feat(accounting): the shared terminal value of a delisting`** · `M1b` `accounting` · S · Blocked by: T0.15a · §5.6.13
- Context: 5.6.13의 하나뿐인 함수 `terminal_value(q, held_path, delisting_row, policy, as_of) -> (amount, ts_known, basis)`: 기준 (a)~(d), 정책 표, 금액을 아는 시각. 정답과 정답 시각은 T2.7에 남는다.
- Done means: 예제가 합성 small의 보유 중 폐지 하나에 대해 표의 정책마다 금액·`ts_known`·기준을 출력.
- Acceptance: `tests/unit/accounting/test_terminal_value.py::test_bases_a_to_d`, `::test_policy_table`, `::test_amount_known_time`.

**T3.1a `feat(portfolio): top(n) with equal weights in one stage`** · `M1b` `portfolio` · S · Blocked by: T1.11, T1.9, T1.Gb · §3.7 포트폴리오, §5.5
- Context: 팩터 하나 위의 `nx.top(n)`과 동일 가중, 구성 단계 하나. 크기 슬롯, `hold`, 그룹 상한, 위험 슬롯은 T3.1에 남는다.
- Done means: 예제가 한 판단의 TargetFrame(선택 순위, 비중)을 출력하고 합 ≤ 1.
- Acceptance: `tests/unit/portfolio/test_targets.py::test_top_n_equal_weights`, `tests/golden/test_time.py::test_T27_hash_tiebreak`(새 값), `::test_n_tied_at_cutoff_counted`, `tests/unit/portfolio/test_targets.py::test_tiebreak_stable_across_decisions`, `::test_factor_top_matches_portfolio_top`, `::test_unrelated_output_does_not_reshuffle`.

**T3.2a `feat(api): Strategy object and schedules`** · `M1b` `api` · S · Blocked by: T3.1a, T1.13 · §3.7, §3.8
- Context: 매개변수와 일정(월간, 일간)을 가진 `Strategy` 객체. `--asof`를 가진 전략 `screen`은 T3.2에 남는다.
- Done means: 팩터 하나짜리 전략이 한 해의 판단일을 월간과 일간으로 출력.
- Acceptance: `tests/unit/api/test_strategy.py::test_param_name_inference`, `::test_strategy_hash_includes_risk`, `::test_decision_context_anchor_field`.

**T3.3 `feat(accounting): columnar account state, integer money, valuation and NAV bridge`** · `M1b` `accounting` · M · Blocked by: T0.3, T3.Gg · §5.6.1, §5.6.9, INV-06
- Done means: G-01 상태를 Arrow IPC 체크포인트로 쓰고 → 복원 → 같은 평가 값; G-48(거래 없는 평가 이익)에서 다리 행이 닫힘을 출력.
- Acceptance: `tests/unit/accounting/test_state.py::test_columnar_state_checkpoint_arrow`, `::test_money_is_integer_minor_units`, `::test_minor_unit_rounding_half_up`, `::test_decision_value_excludes_unknown_entitlements`, `::test_decision_value_uses_only_known_values`, `tests/golden/test_accounting.py::test_G48_appreciation_without_trades`, `tests/unit/test_import_rules.py::test_state_seam_signatures_arrow_only`(`nx.accounting._state` 이음새, `ruined`·`shortfall` 칸).

**T3.4 `feat(execution): order table, lifecycle, trigger state, quantity conservation, sizing and session loop skeleton`** · `M1b` `execution` · M · Blocked by: T3.3, T3.Gg · §5.6.2, §5.6.3, §5.6.7, 부록 C [SC-11]
- Context: 주문 표(5.6.1), 생애 상태·발동 상태·네 수량(INV-18), 수량 사건, `SimConfig`, 판단 시점 수량 고정, `step_session` 뼈대(단계 순서 7개, 시장가만, 비용 0) — 여러 세션 사례(G-10·G-14)를 다음 티켓들이 바로 쓸 수 있게.
- Done means: 상태 전이 표와 `SimConfig` 손잡이 표(부록 C와 같은 순서)를 출력하는 `nx.describe(nx.execution)`; G-15 통과; 무작위 수량 사건 뒤에도 수량 보존; 세션 시작 현금 발생이 5.6.3 (0)의 규칙으로 `[account] cash_rate` 시계열을 읽고, 없으면 `cash_rate_bps`(#313, 결정 2026-11-10).
- Acceptance: `tests/unit/execution/test_orders.py::test_allowed_transitions_only`, `::test_quantity_conservation`, `::test_partial_cancel_is_qty_event_not_status`, `::test_frozen_shares_from_decision_value`, `::test_decision_price_recorded`, `tests/unit/execution/test_simconfig.py::test_knobs_match_appendix_C`, `tests/unit/execution/test_loop.py::test_phase_order_skeleton`, `tests/golden/test_execution.py::test_G15`, `tests/unit/test_import_rules.py::test_step_seam_signatures_arrow_only`(`nx.execution._step` 이음새), `tests/golden/test_time.py::test_G_TIME_LATE_order_intents`(G-TIME-LATE: 8.4 표의 주문 의도, 그 목표에서, 각 행이 전제하는 보유는 계좌 상태에 넣어서; 결정 2026-11-10, #356).
- Notes:
  - owner decides at the cut (#705 Decisions 12, 2026-11-21; #752 Decisions, 2026-11-26): 비어 있는 `lot_size`(TDS 5.1: 모르면 비움)에 엔진이 무엇을 하는지. #705는 표시가 붙는 이름 있는 정책과, 규칙 팩이 아는 시장에서는 팩의 값을 제안했다(T3.5b도).

**T3.5c `feat(execution): market fills at the open, none on a halted or missing bar`** · `M1b` `execution` · S · Blocked by: T3.4 · §5.6.3–5.6.5
- Context: 다음 세션 시가에 체결되는 시장가 주문; `bars.obs_status`가 `traded`가 아닌 봉에서는 체결되지 않는다(5.6.5). 상·하한 잠김, 시가 null 변형, 만료와 이월은 T3.5a에 남는다.
- Done means: 세션별 표가 사례 G-01과 같다.
- Acceptance: `test_execution.py::test_G01`, `tests/unit/execution/test_tradability.py::test_halted_or_missing_bar_does_not_fill`.

**T3.5d `feat(execution): whole-share allocation from available cash`** · `M1b` `execution` · S · Blocked by: T3.5c, T3.Gg · §5.6.7
- Context: 체결 때 쓸 수 있는 현금에서 정수 주로 정하는 주문마다의 수량, 현금 부족의 축소와 부분 취소를 포함, 비용 0. 거래량 상한과 충격은 T3.5b에 남는다.
- Done means: 표가 사례 G-12와 같다; 현금이 음수가 되는 경우가 없음; orders 줄에 `insufficient_cash` 건수·금액.
- Acceptance: `test_execution.py::test_G12`, `tests/unit/execution/test_costs.py::test_trim_order_highest_fill_ratio_first`, `tests/unit/execution/test_sizing.py::test_floor_shares_no_lost_share`(G-53 (d)).

**T3.9 `feat(accounting): splits, reverse splits, stock dividends, bonus issues and capital reductions via the resolver`** · `M1b` `accounting` · M · Blocked by: T3.4, T0.15a, T3.Gg · §5.6.10, §5.3.3a, §4.6 종류 표
- Done means: G-16~G-18, G-34, G-45, G-46 통과.
- Acceptance: `tests/golden/test_accounting.py::test_G16`, `::test_G17`, `::test_G18`, `::test_G34`, `::test_G45_split_ratio_revised`, `::test_G46_split_and_dividend_same_day`, `::test_G53_exact_share_arithmetic`, `tests/unit/accounting/test_ratios.py::test_ratio_rule_examples`, `::test_ratio_product_overflow_checked`, `::test_invalid_exact_ratio_rejected_E13`.

**T3.10a `feat(accounting): cash dividends with the entitlement at the ex-date and cash at the pay date`** · `M1b` `accounting` · S · Blocked by: T3.9, T3.Gg · §5.6.11
- Context: 직전 종가 기준 보유로 배당락일에 만드는 권리와, 지급일에 기록하는 현금, 금액이 배당락일까지 알려진 경우. 늦은 금액, 정정, 지급일 선언, 데이터 경고는 T3.10에 남는다.
- Done means: G-19 통과.
- Acceptance: `test_accounting.py::test_G19`, `tests/unit/accounting/test_dividends.py::test_entitlement_from_previous_close_holding`.

**T3.11a `feat(accounting): delisting with an observed terminal value`** · `M1b` `accounting` · S · Blocked by: T3.10a, T2.7a, T3.Gg · §5.6.13
- Context: 행에 `ret_observed`가 있는 보유 종목의 폐지: 종료 세션에 주문 취소, 보유 제거, 금액은 T2.7a의 `terminal_value`에서, 알려진 때 기록. 정책 값, 합병, 권리, 지원 안 하는 행위는 T3.11에 남는다.
- Done means: G-22의 관측 행이 통과.
- Acceptance: `test_accounting.py::test_G22_observed`.

**T3.22a `feat(accounting): stale marks of a held name with no bar, and a distribution before delisting counted once`** · `M1b` `accounting` · M · Blocked by: T3.11a, T2.7a, T3.Gg · §5.6.3(6), §5.6.9, §5.6.13
- Context: 묵은 평가가 = 마지막 유효 종가 × Π 가격 계수(`stale_adjusted`), 같은 값을 `decision_value`·`P_i`·`ref*`가 씀; 폐지 직전 분배는 `ret_observed_includes_distributions`가 참이든 거짓이든 한 번만 기록. null 표시, `unknown_inclusion`, 정답 확인은 T3.22에 남는다.
- Done means: G-54 표와 G-55의 한 번 센 분배가 그대로 출력되고 v3 식이었으면 나왔을 값(2,000 / 1,100 / 302.30)과 나란히 보인다.
- Acceptance: `tests/golden/test_accounting.py::test_G54_stale_mark_after_action`, `::test_G55_distribution_counted_once`, `tests/unit/accounting/test_marks.py::test_exclusive_observed_has_no_distribution_factor`, `::test_stale_adjusted_status`, `::test_decision_value_uses_adjusted_mark`, `tests/property/test_execution_invariants.py::test_P_BRIDGE_events_on_no_trade_days`.

**T3.12 `feat(execution): single-sleeve simulation loop and session step`** · `M1b` `execution` · M · Blocked by: T3.5d, T3.11a, T3.22a · §5.6.3, §5.6.14
- Done means: G-30 통과, `simulate`와 `step_session` 반복 결과 동일, 체크포인트를 아무 단계 경계에서 끊고 이어도 같음.
- Acceptance: `test_execution.py::test_G30`, `tests/unit/execution/test_loop.py::test_simulate_equals_stepwise`, `::test_resume_at_phase_boundary`.

**T3.13c `feat(api): single-market backtest with the first screen and six metrics`** · `M1b` `api` · M · Blocked by: T3.12, T3.2a, T3.Gg · §5.7, §3.8, §3.9 Run
- Context: M1b의 얇은 백테스트를 위한 `nx.backtest`와 `nexusbt backtest`; 수익률, CAGR, 변동성, Sharpe, 최대 낙폭, 회전율을 담은 3.9의 첫 화면, 비용이 포함되지 않았다고 말하는 줄, 시뮬레이션 결과 줄(#764, 결정 2026-11-25), 원천이 아직 만들어지지 않은 줄마다 3.9가 말하는 대로 기다리는 티켓을 이름 붙여 출력. PSR, DSR, MinTRL, 폐지 시나리오, 비용 줄은 T3.13a에 남는다.
- Done means: 합성 small에서 `uv run nexusbt backtest <전략 파일>`이 `family: n/a (not built yet; available after ticket T2.9)`를 가진 그 첫 화면을 출력; Sharpe가 5.7의 초과 수익 `r_t − rf_t`로 계산됨; 얇은 백테스트 밖의 요청(둘째 시장, 비용 설정, 지정가 주문)은 E18.
- Acceptance: `tests/unit/api/test_backtest.py::test_first_screen_thin`, `::test_costs_not_included_line`, `::test_not_built_line_names_its_ticket`, `::test_outside_thin_backtest_E18`, `tests/unit/research/test_metrics.py::test_cagr_sharpe_mdd_turnover_known_values`, `::test_cagr_from_twr_index_equals_nav_ratio_without_flows`, `::test_turnover_long_only_unchanged`, `tests/golden/test_metrics.py::test_mdd_includes_inception_nav`(G-61 (a)).
- Notes:
  - carried (#43 Decisions, 2026-11-19, #445, #450 and #451): `rerun`, `reconcile`, `live`, `fill`이 필요로 하는 검증 표식과 함께 여는 `open_snapshot(cfg, sha256=True)`(4.4 1단계)를 부르는 곳이 없다. 백테스트의 입구는 아직 `NotImplementedError`를 내고, 이 티켓이 그 실행을 `api._begin_run`으로 시작한다.
  - carried (#725 Decisions 169, 2026-11-23): `backtest`에서 `minimal-daily` 패키지에 4.3의 E18을 주는 코드가 아직 없다.

**T3.14a `feat(artifacts): the saved run's orders, account events and daily table with the bridge`** · `M1b` `artifacts` · S · Blocked by: T3.13c · §5.9.1, INV-06
- Context: `runs/<id>/orders.parquet`, `account_events.parquet`, 다리 행을 가진 `daily.parquet`. 비용 귀속, `report.html`, 시나리오 표는 T3.14에 남는다.
- Done means: `runs/<id>/orders.parquet`·`account_events.parquet`를 polars로 열면 5.9.1 정규 칼럼; `daily.parquet`의 다리 행 합 = NAV 변화.
- Acceptance: `tests/unit/artifacts/test_backtest_outputs.py::test_orders_schema`, `::test_account_events_schema_v1`, `::test_pnl_bridge_closes`, `::test_daily_has_financing_and_flow_bridge_columns`.

**T3.16a `test(property): NAV, bridge and quantity invariants`** · `M1b` `property` · S · Blocked by: T3.13c, T3.14a · §8.3
- Done means: `uv run pytest -m property -k "NAV or BRIDGE or QTY"` 통과.
- Acceptance: `tests/property/test_execution_invariants.py::test_P_NAV`, `::test_P_BRIDGE`, `::test_P_QTY`, `::test_P_QTY_integer_ratios`.

**T3.15a `feat(execution): zipline parity preset (market orders, costs, sizing)`** · `M1b` `execution` · S · Blocked by: T3.12 · §5.6.15 [SC-12]
- Done means: `preset="zipline"` 실행 보고서 머리에 "parity preset (not a realistic model)".
- Acceptance: `tests/unit/execution/test_preset_zipline.py::test_knobs_table`, `::test_forbidden_in_toml`.
- Notes:
  - carried (#858, 2026-11-28): 프리셋의 수수료와 같은 봉 거래량 상한(5.6.15)은 T3.8·T3.5b가 들어온 뒤 작동한다; L2-a·L2-c는 비용 0으로 돌리고, T3.17a(L2-b)가 처음 그것을 쓴다.

**T3.17c `test(parity): L2-a and L2-c backtests against the zipline preset`** · `M1b` `parity` · M · Blocked by: T3.15a, T1.17 · §8.1 [SC-12]
- Context: 두 엔진이 비용 없이 돌리는 L2 단계; 비용과 거래량 상한을 켠 L2-b는 T3.17a에 남는다.
- Done means: L2-a·L2-c 증거 JSON이 커밋된다.
- Acceptance: `tests/parity_compare/test_L2.py::test_L2a_zero_cost`, `::test_L2c_corporate_actions`.

**T3.36 `test(api): rerun of a backtest run`** · `M1b` `api` · S · Blocked by: T3.14a, T1.15 · §3.8 rerun, §5.9.3
- Context: 저장된 백테스트 실행을 새 프로세스에서 `nexusbt rerun <id>`; #858 전에는 이 시험을 가진 티켓이 없었다.
- Done means: 백테스트 실행의 `uv run nexusbt rerun <id>`가 "outputs identical"을 출력.
- Acceptance: `tests/unit/api/test_rerun.py::test_backtest_run_reruns_identical`.

**T5.18a `feat(cli): init --demo and the demo snapshot`** · `M1b` `cli` · S · Blocked by: T1.2, T0.16c · §3.10, §8.5
- Context: 바퀴에 든 합성 `demo` 스냅숏과 함께 `nexusbt init --demo`. 전략 템플릿과 30분 경로는 T5.18에 남는다.
- Done means: 빈 폴더에서 `uv run nexusbt init --demo`가 `nexusbt.toml`과 데모 스냅숏을 쓰고, `uv run nexusbt doctor`가 그것을 연다.
- Acceptance: `tests/unit/cli/test_init.py::test_demo_writes_snapshot_that_opens`.

**T3.37 `docs(examples): the momentum factor and the mom_kr strategy`** · `M1b` `docs` · S · Blocked by: T3.13c, T5.18a · §8.5
- Context: `examples/factors/momentum.py`와, 그 팩터로 순위를 매기는(복사가 아니라 가져옴) `examples/strategies/mom_kr.py`; #858 전에는 이것을 가진 티켓이 없었다. M2가 팩터를 평가하고 M3a가 전략의 전체 보고서를 읽는다.
- Done means: 데모 스냅숏에서 `uv run nexusbt backtest examples/strategies/mom_kr.py`가 첫 화면을 출력.
- Acceptance: `tests/docs/test_examples.py::test_mom_kr_backtest_runs`.

**T1.20 `docs(examples): first five minutes around a first backtest`** · `M1b` `docs` · S · Blocked by: T1.15, T1.22, T3.36, T3.37, T5.18a · §8.5
- Done means: README "첫 5분" 절의 명령을 그대로 붙여 넣으면 `init --demo` → doctor → `examples/strategies/mom_kr.py`의 백테스트 → 그 첫 화면 → rerun이 된다; 합성 스냅숏 만들기나 CSV 가져오기, `tds check`, 스크리닝은 다음 걸음으로 이어진다.
- Acceptance: `tests/docs/test_examples.py::test_readme_m1`.
- Notes:
  - carried (#858, 2026-11-28): #260에 이 티켓의 예전 글(스크리닝으로 끝나는 M1 안내)이 있다; 이 티켓을 다음에 다룰 때 그 본문을 이 항목에 맞춘다.

#### M2 — PIT + 팩터 평가

**T0.8a `superseded`** · `M2` · Blocked by: none · `fundamentals_events`, `fundamentals_state`, `classifications`, `universe_membership`, `dictionary/items`와 함께 2026-11-24에 뺐다(#752) [#725 결정 250].

**T0.8b `feat(testing): synthetic TDS package part 3b - fx and indices`** · `M2` `testing` · M · Blocked by: T0.7 · §4.8 (12)~(13) *(T0.8을 나눔; 패널은 2026-11-24에 뺐다, #752)*
- Context: `fx_rates`(발표 지연, 시장 통화 쌍마다), 지수 종목, `dictionary/columns`.
- Done means: `--preset small --validate`가 core 프로필 세 결과 pass를 출력.
- Acceptance: `test_synth.py::test_synth_conforms[tiny]`, `::test_synth_conforms[small]`, `::test_fx_publication_lag`.

**T0.16b `feat(testing): degraded synthetic packages for research fallbacks`** · `M2` `testing` · S · Blocked by: T0.8b, T0.16a · §4.5, §4.8
- Context: `degrade=`의 남은 값: `no_benchmarks`, `no_dated_category`(F-14). 뺀 종류의 값은 2026-11-24에 빠졌다(#752).
- Done means: `--preset small --degrade no_benchmarks --validate`가 선언 프로필과 세 결과를 출력.
- Acceptance: `test_synth.py::test_synth_conforms_degraded_research[<각 값>]`(2개).

**T2.G `test(golden): PIT, label and lookup cases for M2 (T-08, T-16, T-18, T-21, T-22)`** · `M2` `golden` · M · Blocked by: T0.9 · §8.2 *(v2 T0.11·T0.17의 M2 몫; T-01~T-06, T-13, T-14, T-17, T-19는 2026-11-24에 뺐다, #752)*
- Context: 늦은 배당 `close_tr`, 정답 시각, 직사각형 조회 예시 1~3, 경제 정답 10%, 늦은 회수 정화. 소비 티켓(T2.1~T2.7) 전에 병합.
- Done means: `uv run python tests/golden/check/T-21.py`가 경제 정답 10%와 조정가 비율 11.1%를 나란히 출력하고, 8.2의 T-21 사례 (a)~(f)를 1주 회계 값과 함께 출력(2026-11-04).
- Acceptance: `test_handcalc_self.py::test_time_cases_M2_expected_present`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #583): 이 티켓이 T-08을 쓸 때 그 사례로 #583의 동작도 확인한다: 공개 `nx.run_pipeline`으로 읽은 `Price.close_tr`, 손으로 확인한 값, 5.3.4의 늦은 금액.
**T2.1 `feat(data): rectangle two-time-axis lookup of symbol periods`** · `M2` `data` · M · Blocked by: T1.4, T0.14b, T2.G · §5.3.6, §5.1.5 *(직사각형 조회(`nexusbt_tds.pit.rect_lookup`), strict 행 단위 backfilled 제외; 뺀 종류의 구간 조회는 2026-11-24에 빠졌다, #752)*
- Done means: 예제가 한 종목의 `instrument_symbols` 행들과 세션별 조회 결과를 나란히 출력; 미리 발표된 미래 효력 행은 현재 행을 가리지 않는다.
- Acceptance: `tests/unit/data/test_intervals.py::test_half_open_lookup`, `::test_two_axis_known_after_effective`, `::test_T18_future_effective_does_not_hide_current`, `::test_strict_skips_backfilled_rows`, `::test_no_daily_expansion_memory`, `::test_history_mode_system_E18`.

**T2.2 `superseded`** · `M2` · Blocked by: none · `Fund`, `fundamentals_state`와 함께 2026-11-24에 뺐다(#752) [#725 결정 251].

**T2.3 `feat(pipeline): Meta attributes and the hindsight warning`** · `M2` `pipeline` · S · Blocked by: T0.8b · §3.2, §4.5 F-14 *(F-14; `Panel`, `classifications`의 `Meta` 분류기, `index_members`는 2026-11-24에 뺐다, #752)*
- Done means: 종목마다 `Meta.market`, `Meta.currency`, `Meta.category`를 보이는 예제; `instruments`의 현재 `category`를 쓰면 E30(F-14).
- Acceptance: `tests/unit/pipeline/test_meta.py::test_hindsight_attribute_warned`.
- Notes:
  - carried (#43 Decisions, 2026-11-18, #245 and #542): 참조 실행기는 Classifier를 정수 코드로만 가진다. 이름이나 bool로 하는 `eq`, `element_of`는 `NotImplementedError`("Classifier names come with its code table")로 거절하고 `startswith`는 계산하지 않는다. `Meta.category`의 코드표를 읽는 이 티켓이 둘 다 계산하고 두 거절을 없앤다.

**T2.15 `feat(data): share-count items and market capitalisation`** · `M2` `data` · S · Blocked by: T2.1, T0.15a · §5.3.5a [TDS-D9, TDS-Q4] *(수량 계수 `Q`; `share_counts`, `shares_out`, `market_cap`은 2026-11-24에 뺐다, #752)*
- Done means: 주식 수 항목(5.3.5)을 분할 앞뒤로 분할 비율로 맞춰 출력하고 그것이 주는 시가총액을 보이는 예제; 그런 항목이 없으면 `weight="value"`가 E18.
- Acceptance: `tests/unit/data/test_items.py::test_share_count_item_scaled_by_splits_after_its_date`, `::test_market_cap_without_share_count_item_E18`.

**T2.4 `feat(pipeline): universes with microcap switch and exclusion reasons`** · `M2` `pipeline` · M · Blocked by: T2.4a, T2.15, T0.16b · §3.6 [SC-23] *(시장 이름은 스냅숏에서; 자격과 그 대체 동작은 2026-11-24에 뺐다, #752)*
- Done means: `nx.universe("KR", exclude_microcap=True)`의 세션별 종목 수가 같은 세션 `nx.universe("KR")` 종목 수의 약 80%임을 출력; `coverage` 표에 이유별 제외 수; 고정 목록 → E4.
- Acceptance: `tests/unit/pipeline/test_universe.py::test_microcap_bottom_20pct`, `::test_survivorship_warning`, `::test_exclusion_reason_counts`.

**T2.5 `feat(pipeline): units, currency conversion and cross-market terms`** · `M2` `pipeline` · M · Blocked by: T2.1, T1.11, T0.8b · §3.3, §5.3.2 (6), §5.1.5 fx, §3.11 `[fx] series`
- Done means: `Price.value_traded.latest.rank(across_markets=True)` → E5; `.to("USD")` 뒤에는 동작하고 환율 공개 지연이 반영된 값 출력; 계열이 둘이면 `[fx] series = "auto"`가 E16으로 목록을 보임.
- Acceptance: `tests/unit/pipeline/test_units.py::test_E5_cross_market_currency`, `::test_to_uses_available_fx`, `::test_E17_cross_market_into_window`, `::test_fx_series_auto_selection`.
- Notes:
  - carried (#43 Decisions, 2026-11-16, #482 and #486): 이 티켓과 T2.19가 둘 다 5.3.2 (6)을 들고, #482의 계획기는 시장 축 하나만 계획한다. 시장을 넘는 항에서 할 일은 #486의 Findings에 있다.
  - carried (#43 Decisions, 2026-11-20, #250): `nx.rerun`의 새 프로세스는 6.6 오류를 `kind` 없이 돌려보내므로, 저장된 실행이 `.to`로 통화를 바꾸게 되면 경고 종류의 E20 `FxStaleError`가 실패로 돌아온다. 다른 칸과 함께 `kind`를 쓰는 것이 고침이다(T3.13a도).

**T2.6 `feat(pipeline): label taint`** · `M2` `pipeline` · S · Blocked by: T1.6 · §6.5 *(외부 데이터셋, `from_parquet`, 사용자 정답 경로는 2026-11-24에 뺐다, #752)*
- Done means: 정답 노드(5.3.11)를 신호로 쓰면 E2.
- Acceptance: `tests/unit/test_leaks.py::test_label_taint_E2`.

**T2.9 `feat(research): segments, exposures and trial registry with candidates, observations and cohorts`** · `M2` `research` · M · Blocked by: T1.14b · §6.1, §6.2, §6.3 예약 [SC-19, SC-21]
- Done means: validation 구간을 처음 계산하면 E10 알림, `nx.runs(study=...)`가 노출·후보·관측 수를 보임; 같은 후보를 다른 스냅숏으로 다시 돌리면 관측이 하나 더 생기고 앞 관측은 그대로; `splits=` 값을 주면 E18.
- Acceptance: `tests/unit/research/test_segments.py::test_no_blocking`, `::test_exposure_logged`, `::test_splits_reserved_E18`, `tests/unit/research/test_trials.py::test_candidate_key_excludes_snapshot`, `::test_rerun_adds_observation_not_overwrite`, `::test_cohort_frozen_with_digest`, `::test_study_id_stable_on_rerun`, `tests/unit/research/test_segments.py::test_look_number_counts_family_exposures`, `::test_rerun_adds_no_look`, `::test_corrected_snapshot_continues_look_count`(6.2 확인, #269).
- Notes:
  - carried (#43 Decisions, 2026-11-19, #249): `nx.screen`(`kind="screen"`)과 `nx.run_pipeline(save=True)`(`kind="pipeline"`)는 실행 기록을 봉하고 `exposures` 행은 쓰지 않는다. 이 티켓이 두 종류 모두에 그 행을 쓰되(3.8 "exposure record only", 6.1) 후보도 관측도 더하지 않는다.
  - carried (#43 Decisions, 2026-11-16, #466 and #485): `nexusbt init`은 `nexusbt.toml`에 `[research] family_id`를 쓰고 실행 색인에는 행을 쓰지 않는다. 이 티켓이 첫 id의 `families` 행(5.9.5의 사유 `init`)과 `runs.family_id`를 쓰고, 색인이 모르는 id가 무슨 뜻인지 말한다.
  - owner decides at the cut (#43 Decisions, 2026-11-11, #386 and #305): 옮긴 색인의 family와 다른 `[research] family_id`가 무슨 뜻인지(지금 다른 id로 열면 아무 말이 없다, 5.9.5), 그리고 실행의 `warnings`가 manifest의 논리 해시에 드는지(지금은 든다).

**T2.7 `feat(research): economic and adjusted forward labels, three label times and purging`** · `M2` `research` · M · Blocked by: T2.7a, T1.13, T2.9, T0.15a, T2.G · §5.8, §5.6.13 [SC-20]
- Done means: 한 종목·한 달의 정답 계산 내역(진입·청산 가격, 배당 재투자 계수, 수량 계수, 종료가치, 세 정답 시각)을 출력하는 예제; 합성 small에서 두 정답의 IC 차이를 한 줄로 보고.
- Acceptance: `tests/unit/research/test_labels.py::test_econ_reinvest_at_ex_close`, `::test_adj_ratio_label`, `::test_delisting_terminal_policies`, `::test_terminal_uses_shared_resolver`, `::test_purge_uses_label_available`, `::test_no_entry_counted`, `tests/golden/test_time.py::test_T16_label_times`, `::test_T21_economic_label_10pct`, `::test_T22_purge_uses_label_available`, 그리고 (2026-11-04) `tests/unit/research/test_labels.py::test_econ_exit_on_ex_date_keeps_right_as_cash`(T-21 (b)·(d)), `::test_econ_ignores_unread_bars`(T-21 (c): e 종가를 바꿔도 `R` 그대로), `::test_label_available_covers_every_read_value`(T-21 (a)·(e)), `tests/golden/test_time.py::test_T21_cases`(8.2의 T-21 표).

**T2.8 `feat(research): IC, Newey-West, quantiles, turnover and coverage`** · `M2` `research` · M · Blocked by: T2.7 · §5.8
- Done means: 손으로 만든 IC 계열에서 NW t와 L이 시험 기대값과 같게 출력; 5.8의 순위 자기상관이 시장마다 이웃한 두 판단의 종목으로 계산됨(#764, 결정 2026-11-25).
- Acceptance: `tests/unit/research/test_factor_stats.py::test_spearman_min_pairs`, `::test_newey_west_known_value`, `::test_quantile_ties`, `::test_turnover`, `::test_coverage_counts`, `tests/docs/test_tool_cards.py::test_card[ic-newey-west]`, `::test_every_tool_has_a_card_row`(D19, #219).
- Notes:
  - owner decides at the cut (#43 Decisions, outside review of 2026-11-03): M2의 평가가 실현 회전율과 그룹 중립 IC도 내는지.

**T2.16 `feat(research): naive breadth, implied IR and cohort BHY-adjusted p`** · `M2` `research` · S · Blocked by: T2.8, T2.9 · §5.8 [SC-08, SC-09]
- Done means: 손으로 만든 후보 5개(NW t 주어짐)에서 BHY 보정 p를 출력하고 기대값과 같음; horizon이 다른 후보는 같은 집단에 들지 않음; 단순 폭·기대 IR 출력.
- Acceptance: `tests/unit/research/test_hygiene_stats.py::test_bhy_known_values`, `::test_bhy_cohort_excludes_other_horizon`, `::test_breadth_naive_definition`, `::test_implied_ir`, `::test_bhy_limit_sentence_present`, `tests/docs/test_tool_cards.py::test_card[bhy]`(D19, #219).

**T2.10a `feat(api): evaluate and FactorReport`** · `M2` `api` · M · Blocked by: T2.8, T2.9, T2.4, T2.16 · §3.8, §3.9
- Done means: `uv run nexusbt evaluate examples/factors/momentum.py`가 3.9 모양의 FactorReport(정답 정의·naive breadth·BHY(cohort) 줄, 그리고 3.9의 시뮬레이션 결과 줄 포함, #764, 결정 2026-11-25)와 `report.html` 경로를 출력.
- Acceptance: `tests/unit/api/test_evaluate.py::test_report_lines_match_template`, `::test_counts_next_to_rates`, `::test_saved_run_folder`, `::test_hygiene_block`, `::test_mapping_terms_are_separate_candidates`, `::test_minimal_daily_adj_label_only`.
- Notes:
  - decided (#314 Decision, 2026-11-10; #43 Decisions): 이 티켓을 자르기 전에, 평가한 팩터를 가져오는 전략에 따라붙는 팩터 선택 이력을 기록된 노드 해시와 `exposures`, `selection_events` 표에서 되찾을 수 있는지 보인다. 되찾을 수 없으면 이 티켓이 그 연결을 더한다. 빠진 선택 이력은 나중에 다시 만들 수 없기 때문이다.

**T2.10b `feat(artifacts): report.html template with structural test`** · `M2` `artifacts` · S · Blocked by: T2.10a · §3.9
- Context: FactorReport와 Run이 같이 쓰는 jinja2 한 장 템플릿(외부 파일 없음, 3.9 페이지 틀), 3.9 FactorReport 칸과 그 순서, 빠진 칸의 n/a 줄, 재어 보고 고른 뒤 ADR에 적는 그리는 수단(3.9 시각 규칙).
- Done means: 생성된 FactorReport HTML에 3.9 FactorReport 칸이 3.9 순서로 있고, 시험이 확인할 수 있는 3.9 시각 규칙을 지킨다(외부 자원 없음, 모든 축에 단위, 부호나 무늬가 붙은 손실, 크기 예산 안). 사람이 보는 일은 10.0의 M2 행이며, 목록 없는 눈 확인이 아니라 3.9 목록에 대어 본다.
- Acceptance: `tests/unit/artifacts/test_report_html.py::test_required_sections_present`, `::test_sections_in_3_9_order`, `::test_no_external_resources`, `::test_axes_have_units`, `::test_losses_not_by_colour_alone`, `::test_size_budget`.
- Notes:
  - decided (#43 Decisions, 2026-11-19, #249): 보고서의 질문 7은 항마다의 합계가 계산된 칸의 것이라고 말한다. 같은 항 위의 더 긴 창은 앞의 행과 그 개수를 더하기 때문이다(T3.14도).

**T2.11 `feat(api): explain values of price and item terms`** · `M2` `api` · S · Blocked by: none · §3.9 Explanation *(2026-11-24에 좁힘, #752: `fundamentals_events` 계보와 F-11은 뺐다 [#725 결정 251])*
- Done means: `nx.explain(Price.close.latest, "KR:T00003", "2020-02-28")`가 그 값이 나온 봉을 출력하고, `nx.Item` 항의 `nx.explain`은 그 항이 읽은 값 표 줄(날짜와 값)과 그 나이를 출력(5.3.5).
- Acceptance: `tests/unit/api/test_explain.py::test_not_usable_yet_message`.
- Notes:
  - builder's choice (#43 Decisions, 2026-11-19, #249; 추천: 저장된 파일은 기록된 꼴로 읽기, 이미 쓴 파일은 옛 `term`을 지니기 때문): 이 티켓이 `explain`이 노드를 쓰는 꼴을 정하면 `term_diagnostics.parquet`의 `term` 칼럼이 그 꼴로 바뀐다.
  - decided (#43 Decisions, 2026-11-19, #587): `explain`은 칸이 왜 비었는지 말한다.

**T2.12 `feat(api): static checks before heavy compute`** · `M2` `api` · M · Blocked by: T2.6, T2.5 · §6.5 정적 검사, P8
- Done means: `nx.check(strategy)`가 검사 10개 결과 표를 1초 안에 출력(시간 표시); mask 없는 `zscore` 위에 좁은 유니버스면 E34.
- Acceptance: `tests/unit/api/test_check.py::test_static_checks_list`, `::test_runs_before_compute`, `::test_capability_check_E18`, `::test_unmasked_cross_section_notice_E34`, `tests/perf/test_P8.py::test_static_under_1s` (`perf_smoke`).

**T2.18 `feat(api): preregister`** · `M2` `api` · M · Blocked by: T2.9 · §6.4, §6.2 *(#269: 주장 항목, 조건 해시, 확인 표시)*
- Done means: `nx.preregister(f, metric="ic_mean", threshold=0.02, segment="validation")` 뒤 그 구간 평가 보고서에 "preregistered ic_mean ≥ 0.02: pass/fail · registered before first validation exposure: yes/no"; `preregistrations`에 6.4의 주장 항목이 있고, 색인 행으로 계산한 표시(그것을 찍는 `backtest` 보고서는 T3.13a의 것)가 맞는 확인 하나에 "independent final test (look 1)", 종료일을 늘린 다음 확인에 "repeated look on preregistered data (look 2)", `rerun` 뒤에도 그대로, 비용 설정을 바꾸면 결코 "independent final test"가 아님.
- Acceptance: `tests/unit/research/test_preregister.py::test_record_and_report_line`, `::test_registered_after_exposure_flagged`, `::test_claim_fields_and_defaults_recorded`, `::test_conditions_hash_covers_claim_parameters`, `::test_snapshot_not_in_conditions_hash`, `::test_look_one_independent_final_test`, `::test_later_look_repeated_with_fixed_sample_line`, `::test_changed_conditions_not_independent`, `tests/property/test_research_record.py::test_P_LOOK`(8.3), `tests/docs/test_tool_cards.py::test_card[holdout]`(D19, #219).
- Notes:
  - owner decides at the cut (#43 Decisions, 2026-11-19, #274 and #269): 이 티켓이 만들기 전에 세 가지의 뜻: 어떤 규칙도 주장을 판정하는 데 쓰지 않는 `judge_at`; `nx.backtest`에 실행 쪽 짝이 없는 `nx.preregister`의 `benchmark=`(3.8); 6.4의 조건 해시 인자에 들지 않는 `select=`.

**T2.13 `superseded`** · `M2` · Blocked by: none · `Fund`, L1-c와 함께 2026-11-24에 뺐다(#752).

**T2.17 `docs: English quickstart from CSV to rerun`** · `M2` `docs` · S · Blocked by: T1.22, T2.10a, T1.15 · §8.5
- Context: `docs/quickstart.md`(영어): 손으로 쓴 CSV 두 개 → `tds import csv` → `tds check` → `nx.evaluate(Returns(252).shift(21), target="fwd_return_adj")` → 저장된 실행 → `nexusbt rerun`; minimal 패키지에서 `backtest`를 부르면 나오는 E18 문장과 고치는 법(원가격 + 사건).
- Done means: 깨끗한 폴더에서 문서 명령을 그대로 붙여 넣으면 끝까지 돈다.
- Acceptance: `tests/docs/test_examples.py::test_quickstart_csv_to_rerun_en`.
- Notes:
  - decided (#705 Decisions 23, 2026-11-22): 빠른 시작은 엔진이 다른 엔진의 장점을 가져오고 약점을 푼다는 것이 돌려서 보여지기 전까지는, 많아야 그렇게 설계되었다고만 말한다("아직 티켓이 없는 일", Stage (2)).
  - decided (#43 Decisions, 2026-11-19, #587): 빠른 시작은 빈 칸 하나와 그 까닭을 보인다.
  - decided (#725 Decisions 118, 2026-11-23): 사용자 문서는 `Returns(W)`가 종가 W개, 걸음 W−1개에 걸친다는 것을 숫자로 말한다. 그래서 "20세션 수익률"은 `Returns(21)`이다.
  - owner decides at the cut (#725 Decisions 118, 2026-11-23): `Returns`의 이름이나 기본값을 바꿀지.
  - carried (#43 Decisions, 2026-11-20, #250): 실행 폴더를 설명하는 안내는 `manifest.json`의 `source.outside`와 `source/`가 사람의 모듈 이름과 파일 이름을 적힌 그대로 담는다고 말한다. `manifest.json`은 사람이 남에게 건넬 수 있는 파일이기 때문이다(5.9.3).

**T2.14 `docs(examples): m2 factor research walkthrough and stage measurement`** · `M2` `docs` · S · Blocked by: T2.10a, T2.11, T2.12, T1.24 · §7, §8.5
- Done means: README "팩터 하나 평가" 절 명령이 그대로 돌고, 사람이 계산 기계에서 돌린 `bench/run.py --stages m2 --snapshot synth-full-m1-0001`가 P3, P8을 cold와 warm으로 출력(수치는 마일스톤 추적 이슈에).
- Acceptance: `tests/docs/test_examples.py::test_readme_m2`, `tests/docs/test_scenarios.py::test_scenario[2]`(8.5 사용 시나리오, D19, #219).
- Notes:
  - decided (#43 Decisions, 2026-11-19, #587): 길잡이는 `@nx.factor(..., adjustment="degree 0")`로 쓴 52주 고가 비율을 `Returns`로 쓴 같은 모멘텀 옆에 두고, 창 함수 안에서 종목을 가로질러 순위를 매기지 말라고 경고한다.
  - carried (#43 Decisions, 2026-11-20, #675): `@nx.factor`의 사용자 문서는 같은 값의 0의 부호를 읽는 사용자 함수가 x86에서 다른 값을 줄 수 있다고 경고한다.

**T2.Gb `test(golden): v3.1 ranking and market-series cases (T-26, T-28)`** · `M2` `golden` · S · Blocked by: T0.9 · §5.4.2, §3.2 [V31-13]
- Context: T-26 백분위 합성, T-28 시장 수준 계열의 행 선택. 소비 티켓 T2.19·T2.20 전에 병합.
- Done means: `uv run python tests/golden/check/T-26.py`가 백분위 합성 표를 출력.
- Acceptance: `test_handcalc_self.py::test_cases_v31_M2_expected_present`.

**T2.19 `feat(pipeline): market-level series terms`** · `M2` `pipeline` · M · Blocked by: T2.3, T1.8, T2.Gb · §3.2, §5.1.5, §5.3.2 (6) [V31-13]
- 또(2026-11-25에 더함, #725 결정 246): 3.4의 수익 계열 커널 셋(`SimpleBeta`, `RollingPearsonOfReturns`, `RollingLinearRegressionOfReturns`)과 먼저 쓰는 그 T-25 사례, 그리고 "0차 커널은 `Market.series` 항 위에서 0을 준다"는 3.4의 규칙을 그래프 빌드의 차수 판정에.
- Context: `Market.series(id, column)` 시장 수준 항(그 종목 시장 축, `ready` 그대로), 종목 항과 섞을 때 열 방향 방송, 다른 시장 계열은 판단에서 모으고 창 입력이면 E17, 내장 팩터·사용자 함수 `inputs=`, 없는 id E18, `explain` 표시.
- Done means: 예제 `examples/dev/regime_filter.py`가 "KOSPI TR이 200일선 위" Filter의 판단별 참/거짓과, 거짓인 판단에서 슬리브가 현금임을 출력.
- Acceptance: `tests/golden/test_time.py::test_T28_market_series_rows`, `tests/unit/pipeline/test_market_series.py::test_broadcast_to_instruments`, `::test_not_in_cross_section_denominator`, `::test_cross_market_series_window_E17`, `::test_missing_instrument_E18`.
- Notes:
  - carried (#43 Decisions, 2026-11-16, #482 and #486): 이 티켓과 T2.5가 둘 다 5.3.2 (6)을 든다. #482의 계획기는 시장 축 하나만 계획하고, 시장을 넘는 항에서 할 일은 #486의 Findings에 있다.

**T2.20 `feat(pipeline): percentile rank with explicit missing policy and weighted composites`** · `M2` `pipeline` · M · Blocked by: T1.11, T2.Gb · §3.3, §5.4.2
- Context: `pct_rank(higher_is_better, na=drop|bottom|middle)`, `nx.ops.composite`(중첩), 매니페스트 `na` 정책 기록, `coverage.n_na_filled`, `explain` 노드별 백분위·대체 여부.
- Done means: T-26 표가 그대로 출력되고 `explain`이 "C: na=middle → 50 (filled)"를 보인다.
- Acceptance: `tests/golden/test_time.py::test_T26_pct_rank_and_composite`, `tests/unit/compute/test_pct_rank.py::test_ties_average`, `::test_na_policies`, `::test_composite_nested`, `::test_na_filled_counted`.

**T2.21 `feat(pipeline): Trad dataset and universe exclusion toggles`** · `M2` `pipeline` · M · Blocked by: T2.4 · §3.2, §3.6, §4.3, §5.1.5
- Context: `Trad.admin_status/halted/limit_up_close/limit_down_close/price_limit_ratio`(칼럼 묶음별 공개 시각), `universe(exclude=[…])`와 `[universe] exclude`, 허용 이름 검증(E16), `coverage.n_excluded_by_reason`, `explain` 잎.
- Done means: `nx.universe("KR", exclude=["administrative", "spac"])`의 판단별 제외 수가 이유별로 출력되고, `exclude=["foo"]`는 허용 이름 목록과 E16.
- Acceptance: `tests/unit/pipeline/test_trad.py::test_column_availability_by_group`, `::test_missing_dataset_E18`, `tests/unit/pipeline/test_universe.py::test_exclude_admin_and_category`, `::test_exclude_unknown_name_E16`, `::test_default_excludes_nothing`.
- Notes:
  - carried (#43 Decisions, 2026-11-18, #245): `test_T24_filter_unknown`은 T-24의 `Trad.halted` 행을 커널로만 돌린다. 실행기가 거래 상태를 읽게 하는 이 티켓이 그 행을 실행기로 돌린다.

**T2.22 `feat(pipeline): explicit Filter.fillna, unknown counts per leaf and the unknown-universe notice (E39)`** · `M2` `pipeline` · S · Blocked by: T2.4, T1.25 · §3.3, §5.4.1, §6.6 E39, §5.9.1
- Context: `Filter.fillna(bool)`(명시적 대체, 매니페스트·`explain`에 기록), 실행 중 유니버스 모름 비율 > 50% → E39(판단 수·잎 이름·입력 칼럼), `coverage.n_unknown_by_leaf`(json).
- Done means: 합성 small에서 미국 2019-08-23 전 판단에 `nx.universe("US") & ~Trad.halted`를 쓰면 E39 한 줄과 fix 문장(`.fillna(True)`)이 나오고, `(~Trad.halted).fillna(True)`로 바꾸면 유니버스 크기가 되돌아온다.
- Acceptance: `tests/unit/pipeline/test_filters.py::test_fillna_bool_explicit`, `tests/unit/pipeline/test_universe.py::test_unknown_universe_notice_E39`, `::test_unknown_by_leaf_counted`.

**T2.Ge `superseded`** · `M2` · Blocked by: none · G-96~G-98과 함께 2026-11-24에 뺐다(#752).

**T2.23 `superseded`** · `M2` · Blocked by: none · `Macro`, `Events`, `from_parquet`, E47과 함께 2026-11-24에 뺐다(#752) [#725 결정 251].

**T2.24 `perf(bench): P11 fixture and factor-graph generator with the reduced P11 (a) on the m1 columns`** · `M2` `bench` · S · Blocked by: T1.24, T2.10a · §7 P11 [#175]
- Context: 합성 300팩터 그래프 생성기와 `bench/fixtures/p11.json`(7장 "P11 고정 fixture", T6.26에서 옮겨 옴; 기본 칼럼마다 나오는 데이터셋을 적음), 그리고 7장 이른 측정 표의 축소 P11 (a): 같은 씨앗·창 길이 분포·순위·합성 비율·노드 공유율로, 기본 칼럼을 M1 데이터셋에 있는 것(가격·거래량·달력에서 나온 것)으로 줄여 팩터 300개를 월간 판단에서 판단 행만으로(5.3.2) `nx.evaluate`. 결과 JSON에 쓴 기본 칼럼과 P11 보고 칼럼(읽은 칼럼 바이트·계산한 판단 행 수·노드 수·공유된 노드 수)을 적는다.
- Done means: `uv run python bench/run.py --workload P11 --part a --columns m1 --fixture bench/fixtures/p11.json --reps 3 --snapshot synth-small`이 시간·USS·`fixture_sha256`·출력 값 해시·쓴 기본 칼럼을 담은 JSON을 출력하고; 사람이 계산 기계에서 돌린 `bench/run.py --workload P11 --part a --columns m1 --fixture bench/fixtures/p11.json --snapshot synth-full-m1-0001`이 cold와 warm 시간과 P11 (a) 단계 예산에 견준 단계별 시간을 프로세스 트리 USS 합과 함께 출력(수치는 "축소, M1 칼럼"으로 마일스톤 추적 이슈에).
- Acceptance: `tests/unit/bench/test_p11_fixture.py::test_generator_same_seed_same_graph`, `::test_base_columns_carry_their_dataset`, `::test_m1_columns_keep_the_ratios`, `tests/perf/test_p11_smoke.py::test_fixture_hash_recorded`, `::test_m1_columns_variant_reports_columns_used`.

#### M3a — 한 시장 시장가, 백테스트 완성

**T0.8c `feat(testing): full and full_ci synthetic presets`** · `M3a` `testing` · S · Blocked by: T0.8b, T0.8d · §4.8
- Done means: `--preset full_ci --validate`가 CI에서 시간·크기를 출력하고 통과; `--preset full`은 계산 기계 수동 체크리스트(마일스톤 추적 이슈)에 시간·크기 기록.
- Acceptance: `test_synth.py::test_full_ci_conforms`, `::test_full_ci_is_fraction_of_full_rules`.

**T3.Ga `test(golden): market execution and cash cases (G-10, G-11, G-13, G-14, G-31, G-41, G-112..G-114)`** · `M3a` `golden` · M · Blocked by: T0.9 · §5.6.3–5.6.7, §8.2
- Context: 거래량 상한 3세션 이월, 신규 상장 ADV 모름, 한국 상·하한 막힘, 정지 이월·20세션 만료, 시가 null, 최소 수수료 + 충격 살 수 있는 수량; 현금 부족(G-12)과 새 판단 교체(G-15)는 T3.Gg의 것. 소비 티켓 T3.5a·T3.5b 전에 병합.
- Done means: `uv run python tests/golden/check/G-14.py`가 정지 동안의 세션별 주문 상태와 20세션 뒤의 만료를 출력.
- Acceptance: `test_handcalc_self.py::test_cases_market_execution_expected_present`.

**T3.Gc `test(golden): accounting cases (G-20, G-21, G-23..G-26, G-35, G-42..G-44, G-47, G-49, G-111, G-115)`** · `M3a` `golden` · M · Blocked by: T0.9, T0.15a · §5.3.3a, §5.6.9–5.6.14, §8.2
- Context: 금액 미공개·지급일 선언·긴 정지 뒤 폐지·합병·지원 안 함·권리 소멸·자본 반환, 늦은 회수(G-42), 정정·취소(G-43·G-44), 권리 수량 불변(G-47), 수수료가 있는 다리(G-49); M1b의 분할·배당·폐지·실행 끝·다리 사례는 T3.Gg의 것. 소비 티켓 T3.10·T3.11 전에 병합.
- Done means: `uv run python tests/golden/check/G-42.py`가 10·11월 `decision_value`(회수 제외)와 12월 미수금 전환을 출력.
- Acceptance: `test_handcalc_self.py::test_cases_accounting_expected_present`.

**T3.1 `feat(portfolio): pure target construction with stages and risk slot`** · `M3a` `portfolio` · M · Blocked by: T3.1a, T2.15 · §3.7 포트폴리오, §5.5 [SC-01, SC-02 문구]
- Done means: 예제가 한 판단의 TargetFrame(선택 순위, 두 단계 비중, capped 사유)을 출력하고 합 ≤ 1; `nx.top(10, hold=20)` → T7.1 전에는 E18 "available after ticket T7.1".
- Acceptance: `tests/unit/portfolio/test_targets.py::test_equal_cap_residual_cash`, `::test_value_weights`, `::test_inverse_vol_excludes_nan`, `::test_redistribute_converges`, `::test_per_group`, `::test_risk_none_identity_stage_columns`, `::test_hold_reserved_E18`, `::test_prior_state_returned_empty_in_v1`.

**T3.2 `feat(api): Strategy, schedules, params and strategy screen`** · `M3a` `api` · M · Blocked by: T3.2a, T3.1 · §3.7, §3.8 screen
- Done means: `uv run nexusbt screen examples/strategies/mom_kr.py --asof 2019-06-28`이 3.9 Screen 모양을 출력, 판단일이 아니면 "(preview)".
- Acceptance: `tests/unit/api/test_strategy.py::test_screen_scheduled_flag`.

**T3.8 `feat(execution): cost models, general impact form and cost table coverage`** · `M3a` `execution` · M · Blocked by: T3.4 · §5.6.8, §4.7 [SC-11]
- Done means: `nx.costs.realistic()`를 미검증 표로 고르면 E23이 빈 (시장, 기간, 구성요소)를 나열; provisional은 E22; a2=0.5·a3=1에서 제곱근 식과 같은 값; 충격은 세션 누적 수량에 대해 매겨 여러 체결로 나뉜 주문이 주문 하나와 최소 단위 반올림 전에 같은 충격을 냄(5.6.8; #311, 결정 2026-11-10); 비용 구성요소가 최소 단위 정수로 기입; 기본 프로필은 시장별 고정 bp인 `provisional`로 남고, ½스프레드와 충격은 `realistic`에만 있으며 반 호가 단위 하한은 없음(5.6.8; #764, 결정 2026-11-25).
- Acceptance: `tests/unit/execution/test_costs.py::test_provisional_bps_from_pack`, `::test_per_share_min`, `::test_abdi_ranaldo_known_value`, `::test_general_impact_equals_sqrt_default`, `::test_spread_floor_without_high_low`, `::test_coverage_E23`, `::test_components_rounded_to_minor_units`.

**T3.5a `feat(execution): market fills at open with tradability rules`** · `M3a` `execution` · M · Blocked by: T3.5c, T3.Ga · §5.6.3–5.6.5
- Done means: G-11, G-13, G-14, G-31, G-112, G-114(#310) 사례와 같은 세션별 표.
- Acceptance: `test_execution.py::test_G11`, `::test_G13`, `::test_G14`, `::test_G31`, `tests/unit/execution/test_tradability.py::test_price_limits_only_with_pack`.

**T3.5b `feat(execution): volume cap and affordable cash allocation with the actual cost function`** · `M3a` `execution` · M · Blocked by: T3.5d, T3.5a, T3.8, T3.Gd · §5.6.6, §5.6.7
- Done means: G-10, G-41, G-113(#310) 사례와 같은 표; 현금이 음수가 되는 경우가 없음; 배분은 충격을 그 세션의 `Q_before`로 계산(5.6.7, 5.6.8; #311, 결정 2026-11-10).
- Acceptance: `test_execution.py::test_G10`, `tests/unit/execution/test_costs.py::test_G41_affordable_lots_never_negative_cash`, `::test_cost_reserve_default_zero_recorded`, `test_execution.py::test_G56_bar_volume_cap`, `tests/unit/execution/test_capacity.py::test_bar_volume_bound_counted`(ψ 묶음 비율).
- Notes:
  - builder's choice (#43 Decisions, 2026-11-13, #436; 추천: 누적, "주문을 나눠도 합계가 줄지 않는다"를 지키기 때문): 한 배분 걸음에 같은 종목, 같은 방향의 후보가 둘일 때 `Q_before`를 걸음의 시작에서 잡는지 누적으로 잡는지. 슬리브는 종목마다 목표 하나를 가지므로 생기지 않을 수도 있다.

**T3.9b `feat(accounting): exclude instruments with share events lacking exact ratios (default policy)`** · `M3a` `accounting` · M · Blocked by: T3.9, T1.1a, T3.Gd, T3.13b, T2.10b · §5.6.1, §3.11, §6.6 E13·E30
- Context: 기본 `decimal_ratio = "exclude_instrument"` — 보이는 때 v(e)부터 유니버스에서 빼기(그 전에는 안 뺌), 보유분 목표 0, `ts_effective` 전 미체결이면 직전 유효 종가로 닫기(`ca_unverified_exit`), 사건을 가로지르는 창 NaN, 다시 들어오지 않음, 머리 줄·E30·skips·매니페스트; `require_exact`는 E13, `literal` 유지. 5.6.1 (8)의 보고 [#150]: `exit_reason = ca_unverified_exit`, `ca_exclusions.parquet`(들고 있지 않던 종목도 한 행), `hypothetical exits` 줄, 7절 연도별 표, `ca_exit_lo`/`ca_exit_hi` 쌍(`ca_exit_lo`는 n > 0일 때만 재생, `ca_exit_hi`는 기본 실행의 값; 아니면 줄 `ca sensitivity: n/a (0 hypothetical exits)`; 숏 보유분은 `bound open`으로 셈).
- Done means: 두 경우 모두 G-107의 숫자와 그 `ca_exclusions.parquet` 행, 첫 화면 `hypothetical exits` 줄을 출력하는 예제, 같은 스냅숏으로 스크린과 백테스트의 유니버스가 같음.
- Acceptance: `tests/golden/test_ca.py::test_G107`, `tests/unit/accounting/test_ca_exclude.py::test_not_before_visible`, `::test_exit_before_effective`, `::test_unverified_exit_close`, `::test_window_nan_across_event`, `::test_require_exact_E13`, `::test_exclusion_row_for_name_not_held`, `::test_hypothetical_exit_pnl_line`, `::test_ca_exit_lo_hi_bracket_long`, `::test_ca_exit_short_bound_open`, `::test_no_ca_exit_replay_without_exit`, `tests/property/test_screen_backtest.py::test_same_universe_with_exclusions`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #445, #450 and #451): 실행에서 `Snapshot.ca_exclusions`를 적용하는 일은 이 티켓의 것이다.

**T3.10 `feat(accounting): cash dividends with entitlements, late amounts, corrections, pay-date declaration and data warnings`** · `M3a` `accounting` · M · Blocked by: T3.10a, T3.Gc · §5.6.11, §5.3.3a(4)(7)(10), §4.5 F-05·F-09 *(지급일 추정은 2026-11-24에 사용자의 선언으로 바뀜, #752)*
- Done means: G-20, G-21, G-35, G-43, G-44, G-111(#310) 통과, 실행 경고에 E28 건수; `degrade=["kr_ex_is_record"]`에서 E30 건수, `degrade=["us_div_split_adjusted_no_dates"]`에서 "amounts unverified" 가정 줄.
- Acceptance: `test_accounting.py::test_G20`, `::test_G21`, `::test_G35`, `::test_G43_dividend_revised_after_payment`, `::test_G44_dividend_cancelled`, `::test_G20_entitlement_survives_exit_before_terms`, `tests/unit/accounting/test_actions_late.py::test_late_discovered_event_uses_effective_holding`, `tests/unit/accounting/test_dividend_data_warnings.py::test_F05_counted`, `::test_F09_assumption`.

**T3.11 `feat(accounting): delisting with knowledge-time proceeds, mergers, rights and unsupported actions`** · `M3a` `accounting` · M · Blocked by: T3.11a, T3.10 · §5.6.12, §5.6.13, §4.5 F-13
- Done means: G-22~G-26, G-42, G-47, G-115(#310) 통과(G-25는 E12 메시지); `degrade=["no_delistings"]`에서 보유 중 퇴출이 E13(fix 문장, 생산자 이름 없음).
- Acceptance: `test_accounting.py::test_G22` … `::test_G26`, `::test_G42_recovery_known_later`, `::test_G47_rights_lapse_quantity_unchanged`, `tests/unit/accounting/test_delisting_fallback.py::test_F13_unobserved_synthesized`, `::test_mixed_merger_cash_and_shares`, `::test_merger_exact_ratio`.
- Notes:
  - owner decides at the cut (#43 Decisions, outside review of 2026-11-03): Shumway 상장폐지 수익률 정책을 더할지(5.6.13).
  - carried (#752 Decisions, 2026-11-27): #747이 대가를 모르는 퇴출의 엔진 쪽 빈틈 둘을 갖고 있고(5.6.13), 이 티켓을 만들 때 답한다.

**T3.13a `feat(api): single-market backtest and metrics`** · `M3a` `api` · M · Blocked by: T3.13c, T3.5b, T3.22, T3.2, T2.9, T2.18, T3.Ge · §5.7, §3.8, §3.9 Run
- Done means: `uv run nexusbt backtest examples/strategies/mom_kr.py`가 3.9 Run 모양(net/gross, 가정 줄, 비용 직접/경로, 폐지 lo/hi, PSR)을 출력; 5.7의 Calmar 행이 G-110(#310)과 맞는다; PSR·DSR·MinTRL이 5.7의 초과 수익 `r_t − rf_t`로 계산되고 `assumptions` 줄이 3.9의 시계열 꼴이나 상수 꼴을 보인다(#313, 결정 2026-11-10).
- Acceptance: `tests/unit/api/test_backtest.py::test_run_summary_template`, `::test_assumption_lines_present`, `::test_observation_recorded`, `::test_evaluation_label_and_fixed_sample_line`(3.9 `evaluation` 줄과 확인 2에서 PSR·DSR 줄의 "fixed-sample statistic; n looks", #269), `tests/unit/research/test_metrics.py::test_cost_drag_direct_vs_path`, `tests/golden/test_metrics.py::test_G60_metrics_and_month_compounding`, `tests/unit/api/test_backtest.py::test_assumption_ex_post_volume_cap`, `tests/docs/test_tool_cards.py::test_card[linear]`, `tests/unit/report/test_next_line.py::test_entries_from_run_facts_not_values`(D19, #218, #219).
- Notes:
  - owner decides at the cut (#314 Findings, 2026-11-06; #314 Decision, 2026-11-10): 기준지수의 α와 β를 5.7의 "Relative to benchmark" 행에 두 줄로 둘지. 만드는 쪽의 추천은 더하는 것이고, 새 입력이 필요 없기 때문이다. 지금 계획 문서의 v1.x 밑 "Later (P3)" 문단은 α와 β를 뒤로 미룬 기준지수 회귀 지표에 넣고 있다.
  - owner decides at the cut (#43 Decisions, 2026-11-19, #437): #437의 Outcome이 열어 둔 네 가지(A1, A4~A6): 여러 통화 실행에서 `rf_t`의 `day_count`와 `date_t`, 두 시장이 한 통화를 나눌 때의 대체, `assumptions` 한 줄에 여러 통화, G-77 (b)의 시험 이름(T3.4, T3.Ge도).

**T3.13b `feat(api): named scenarios with a single zero-cost replay`** · `M3a` `api` · S · Blocked by: T3.13a · §3.8, §5.7 [SC-06 인자 모양]
- Done means: `--scenarios gross,cost0x,cost2x`가 재생 두 번(gross, cost2x)만 하고 결과 표에 cost0x가 gross와 같은 계열로 나옴; `capacity`는 T6.14 전 E18.
- Acceptance: `tests/unit/api/test_backtest.py::test_gross_replayed_once`, `::test_cost_sensitivity_rows`, `::test_scenarios_named_list`, `::test_capacity_not_yet_E18`, `tests/docs/test_tool_cards.py::test_card[scenarios]`(D19, #219).
- Notes:
  - decided (#725 Decisions 165, 2026-11-23; #725 Decisions 245): 백테스트는 끝을 모르는 보유 종목마다 마지막 유효 종가와 `ref*`를 찾아, 5.6.13대로 `delist_lo`와 `delist_hi` 범위에 넣고, 골든 사례 하나를 더한다.

**T3.14 `feat(artifacts): backtest outputs, event schemas, derived tables, NAV bridge and cost attribution`** · `M3a` `artifacts` · M · Blocked by: T3.14a, T3.13a · §5.9.1, INV-06, INV-16 [SC-07 비용, SC-23]
- Done means: `attribution.parquet`의 비용 행 합 = 주문 비용 칼럼 합(gross − net은 \"직접 + 경로\"로 표시); `report.html`에 비용 분해·시나리오·주문 상태 표, 그리고 3.9의 Run 칸이 3.9 순서로(나중 티켓이 표를 더하는 칸은 n/a 줄을 보임) 3.9 크기 예산 안에서.
- Acceptance: `tests/unit/artifacts/test_report_html.py::test_run_sections_in_3_9_order`, `::test_run_size_budget`, `tests/unit/artifacts/test_backtest_outputs.py::test_costs_equal_order_costs`, `::test_G49_fee_reduces_quantity`, `::test_coverage_columns`, `tests/property/test_execution_invariants.py::test_P_DERIVED`, `tests/repo/test_shareable_outputs.py::test_shareable_files_hold_no_local_values`.
- 공유 가능 산출물(5.9.3, #163): `test_shareable_files_hold_no_local_values`는 F-05가 나도록 `degrade=["kr_ex_is_record"]`로 만든 합성 `small` 스냅숏(4.8)으로 백테스트를 돌리며 다음 값을 심는다: `HOME`을 이름에 `nxplant-home`이 든 임시 폴더로; 프로젝트와 그 `runs/`, 이를 담은 임시 git 저장소를 `<HOME>/nxplant-project`에; `[data] root` = `<HOME>/nxplant-data-root`; git 사용자 이름 `nxplant-git-user`; `nexusbt.toml`의 주석과, 같은 `runs/` 아래 `manual:nxplant` 장부에 기록한 체결 행의 `note`에 계좌 번호 `NXPLANT-ACCT-90417`(지금 백테스트는 장부를 읽지 않으므로 이 부분은 나중 변경을 막는 장치); 그리고 생성기가 쓰는 `producer` 블록(4.8) 대신 이름 `nxplant-producer`, 버전 `nxplant-build`, `nxplant-hint`가 든 `fallback:F-05` hint 문장을 가진 블록. 먼저 실행 경고에 `fallback:F-05`가 있는지 본다. 그다음 5.9.3의 공유 가능 파일 전부를 텍스트로 읽어 — JSON과 HTML은 쓰인 그대로, Parquet은 페이지가 압축돼 있으므로 풀어서(모든 문자열 값과 키-값 메타데이터) — 다음이 하나도 없음을 본다: 쓰인 형태와 풀어 쓴 형태의 `HOME` 경로, `nxplant-project`, `nxplant-data-root`, `nxplant-git-user`, `NXPLANT-ACCT-90417`, `nxplant-producer`, `nxplant-build`, `nxplant-hint`, 그리고 호스트 이름(`socket.gethostname()`)과 로그인(`getpass.getuser()`)은 4글자 이상일 때(더 짧으면 확인 안 됨으로 보고). 또 `source/nexusbt.toml`에서 `nxplant-data-root`를 찾아, 심은 값이 실행에 닿았음을 보인다.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #249): 4.6의 `AdjustmentUnavailable` 수, 곧 (종목, 사건) 짝마다 하나를 종목과 해별로 coverage 표에 두고 사건 id는 보고서에 두는 일은 이 티켓의 것이다. `execute()`는 `adjusted_window`가 돌려준 짝을 버리므로, 이 티켓은 실행기가 그것을 부른 쪽에 넘기게도 한다.
  - owner decides at the cut (#43 Decisions, 2026-11-19, #401 and #420): 8.2가 "the M3 golden ticket that precedes T3.14"에 주었으나 T3.Ga, T3.Gc, T3.Gd, T3.Ge, T3.Gr 어느 것도 들지 않는 G-117과 G-118을 어느 골든 티켓이 쓰는지, 그리고 `survivorship.parquet`과 `coverage_fields.parquet`의 시험.
  - owner decides at the cut (#43 Decisions, 2026-11-20, #250): 키의 뜻을 바꾸는 첫 변경 전에 실행 manifest의 `schema_version`을 올리는 규칙(#250은 선택 칸 `source{entry, outside}`를 더하면서 `"nexusbt-run/2"`를 그대로 두었다).

**T3.16 `test(property): accounting and state-machine invariants`** · `M3a` `property` · M · Blocked by: T3.16a, T3.13a · §8.3
- Done means: `uv run pytest -m property -k "RESUME or STATE or PARITY13"` 통과.
- Acceptance: `tests/property/test_execution_invariants.py::test_P_RESUME`, `::test_P_STATE`, `::test_P_PARITY13_single_market`, `tests/property/test_fillcausal.py::test_P_FILLCAUSAL_open_independent_of_later_hlc`, `::test_bar_volume_cap_monotone_for_isolated_order`(두 성질).
- Notes:
  - carried (#43 Decisions, 2026-11-20, #254): M1의 P-FUT은 `decision_ts ≤ τ`인 행에서 `run_pipeline`의 표와 `term_diagnostics`를 비교한다. 목표와 주문을 만드는 티켓이 8.3의 행대로 P-FUT을 넓혀 그것들도 비교한다(T3.13a도).
  - carried (#43 Decisions, 2026-11-21, #255): M1의 P-START와 M-SCALE은 `run_pipeline`의 표와 `term_diagnostics`를 비교한다. 목표를 만드는 티켓이 둘을 8.3이 이름 댄 정규 목표와 목표 비중으로 넓힌다(T3.13a도).
  - carried (#43 Decisions, 2026-11-04, #207): 5.7은 계좌 층이 시나리오 안에서 다시 돈다고 하지만(예: `cost2x`에서만 걸리는 브레이크), 8.3에는 그것을 확인하는 성질 행이 없다. 자를 때 그 행을 더하고 그것을 시험하는 티켓을 이름 댄다(T3.13b도).

**T3.17a `test(parity): L2-b backtests with costs against the zipline preset`** · `M3a` `parity` · S · Blocked by: T3.17c, T3.8, T3.5b · §8.1 [SC-12]
- Done means: L2-b 증거 JSON이 커밋된다.
- Acceptance: `tests/parity_compare/test_L2.py::test_L2b_costs_and_volume_cap`.

**T3.21 `feat(api): coverage and stale-mark warnings (E6, E25)`** · `M3a` `api` · S · Blocked by: T3.13a · §6.6
- Done means: 유효/유니버스 < 50%인 판단이 5% 넘는 합성 실행에서 E6 한 줄(원인 칼럼별 NaN 수), 20세션 넘게 묵은 평가 보유에서 E25.
- Acceptance: `tests/unit/api/test_warnings.py::test_E6_coverage`, `::test_E25_stale_mark`.

**T3.18 `docs(examples): m3a strategy walkthrough, perf smoke and stage measurement`** · `M3a` `docs` · S · Blocked by: T3.14, T1.24, T0.8c, T2.24 · §7, §8.5 *(7장 표의 M3a 워크로드, 전체 P11 (a) 포함 [#175])*
- Done means: README "전략 하나 백테스트" 절이 돌고, `uv run pytest -m perf_smoke`가 P5-small 시간을, `bench/run.py --stages m3a --snapshot synth-full_ci`가 상태 기계 단계 시간을 출력; 계산 기계에서 `bench/run.py --stages m3a --snapshot synth-full-0001`가 한 시장 P5·P5-daily·P7을, `bench/run.py --workload P11 --part a --fixture bench/fixtures/p11.json --snapshot synth-full-0001`이 전체 P11 (a)와 단계별 시간을 cold와 warm으로 출력(수치는 마일스톤 추적 이슈에, 그리고 첫 P5-daily 수치로 사람이 7장의 P5-daily 예산과 목표를 정한다).
- Acceptance: `tests/docs/test_examples.py::test_readme_m3a`, `tests/perf/test_smoke.py::test_P5_small`, `tests/docs/test_lessons.py::test_lesson[cost-change]`, `tests/docs/test_scenarios.py::test_scenario[1]`, `::test_scenario[5]`(8.5 실습 예제와 사용 시나리오, D19, #219).

**T3.Gd `test(golden): v3.1 volume-cap, rounding, small-trade and target-gap cases (G-56, G-58, G-59, G-66)`** · `M3a` `golden` · M · Blocked by: T0.9, T0.15a · §5.6.1, §5.6.6, §5.6.7, §8.2
- Context: 8.2 표의 사례; 수량·묵은 평가가·폐지 분배 사례 G-53~G-55는 T3.Gg의 것. 소비 티켓 T3.5b·T3.23·T3.25·T3.26 전에 병합.
- Done means: `uv run python tests/golden/check/G-56.py`가 세션별 체결 수량과 이월 수량을 출력.
- Acceptance: `test_handcalc_self.py::test_cases_v31_M3a_expected_present`.

**T3.Ge `test(golden): v3.1 benchmark and Calmar cases (G-62, G-110)`** · `M3a` `golden` · S · Blocked by: T0.9 · §5.7, §8.2
- Context: 벤치마크 맞춤·상대 지표, Calmar; 지표와 낙폭 사례 G-60·G-61은 T3.Gg의 것. 소비 티켓 T3.13a·T3.20·T4.6·T4.12 전에 병합.
- Done means: `uv run python tests/golden/check/G-110.py`가 (a)의 Calmar 2.001499와 (b)의 "n/a (no drawdown)"을 출력; G-77 옆 사례(8.2): 금리가 0%, 4%, 2%인 세션 셋의 손계산 발생과 초과 수익, 숫자는 이 티켓이 계산(#313, 결정 2026-11-10).
- Acceptance: `test_handcalc_self.py::test_cases_v31_metrics_expected_present`.

**T3.22 `feat(accounting): stale marks adjusted for corporate actions and distributions before delisting counted once`** · `M3a` `accounting` · M · Blocked by: T3.22a, T3.11, T2.7 · · §5.6.3(6), §5.6.7, §5.6.9, §5.6.13
- Context: T3.22a 다음의 것: `distribution_in_terminal`, null이면 (d) 보수 쪽 + E30 또는 `unknown_inclusion = "error"`면 E13, 늦은 포함 표시, T2.7a의 공용 `terminal_value`로 정답의 종료 금액이 회계의 것과 같음.
- Done means: G-55 (g)·(h) 사례 표가 그대로 출력된다.
- Acceptance: `tests/golden/test_accounting.py::test_G55_late_inclusion_flag_preserves_prior_orders`, `::test_G55h_unknown_inclusion_conservative`, `::test_G55g_label_equals_accounting_terminal`.

**T3.23 `feat(accounting): per-component money rounding from market rules packs`** · `M3a` `accounting` · S · Blocked by: T3.8, T3.Gd · §5.6.1, §5.6.8, §4.7
- Context: 팩 `[rounding]`(구성요소별 mode·단위), 사용자 `[rounding.<MARKET>]` 덮어쓰기, 기본 KR 수수료·세금·원천징수 `down`·나머지 half_up, US half_up, `settings_hash`에 팩 판.
- Done means: G-58이 기본 KR 팩 23원·시험 팩(half_up) 24원을 출력하고 다리 `rounding` 행이 닫힌다.
- Acceptance: `tests/golden/test_execution.py::test_G58_component_rounding`, `tests/unit/accounting/test_rounding.py::test_kr_default_down_us_half_up`, `::test_user_override_recorded_in_settings_hash`.
- Notes:
  - carried (#43 Decisions, 2026-11-02, #95): 규칙 팩은 반올림 `mode`를 `RoundingModePolicy`의 값과 맞대어 본 그냥 문자열로 가진다. 팩의 `[rounding]`과 사용자의 `[rounding.<MARKET>]`을 합치는 이 티켓이 그것을 멤버로 바꾼다.
  - carried (#43 Decisions, 2026-11-02, #94): `load_config`는 규칙 팩의 기본값을 비교하지 않는다.

**T3.25 `feat(execution): minimum trade threshold and rebalance band at the order-intent stage`** · `M3a` `execution` · S · Blocked by: T3.5b, T3.Gd · §3.7, §5.6.7, §3.11
- Context: `min_trade_value`·`min_trade_weight`·`rebalance_band`·`band_mode`(인자와 toml), 새 진입·완전 청산·부호 바뀜 제외, `order_suppressed(small|band)`, 보고 줄, 프리셋 끔.
- Done means: G-59 세 사례 표가 출력되고 손잡이를 끈 실행은 v3와 바이트가 같다.
- Acceptance: `tests/golden/test_execution.py::test_G59_small_trades_and_band`, `tests/unit/execution/test_small_trades.py::test_entries_and_exits_exempt`, `::test_default_off_identical`, `::test_targets_unchanged`.

**T3.26 `feat(research): target gap, lot rounding drag and execution quality metrics`** · `M3a` `research` · M · Blocked by: T3.14, T3.Gd · §5.6.7, §5.6.8, §5.7, §5.9.1
- Context: `target_gap`·원인 분해, `rounding_gap`·`n_zero_lot_targets`(E37), 체결마다 `slip_vs_decision_bps`·`slip_vs_arrival_bps`·`effective_price`·`outside_range`, 첫 화면 "target gap" 줄, HTML "execution" 칸, 정본 사건에서 파생.
- Done means: G-66이 3.33%·1개·1.67%와 E37 사례를 출력하고 Run 첫 화면에 target gap 줄이 보인다.
- Acceptance: `tests/golden/test_execution.py::test_G66_target_gap_and_lot_rounding`, `tests/unit/research/test_exec_quality.py::test_slip_bps_sign`, `::test_outside_range_count`, `::test_gap_by_cause_sums`, `::test_intended_cash_not_reported_as_rounding_gap`, `tests/property/test_execution_invariants.py::test_P_DERIVED_quality_columns`.

**T3.Gr `test(golden): sizing and risk cases (G-78..G-87, G-95)`** · `M3a` `golden` · M · Blocked by: T0.9 · §5.5.1a, §5.5.2, §5.5.2a, §5.5.2b, §8.2
- Context: 해부 F의 G-R1~G-R10을 G-78~G-87로 옮겨 판단별 비중·배수·상태를 글자 그대로 적는 사례 yaml과 검산(사칙연산·제곱근만). 구현 PR 전에 다른 세션에서 병합.
- Done means: `uv run python tests/golden/check/G-84.py`가 판단별 NAV·그림자 지수·DD·상태·m을 표로 출력.
- Acceptance: `tests/golden/test_handcalc_self.py::test_case_G78_to_G87_expected_present`, `::test_case_G95_expected_present`(G-108은 2026-11-24에 뺐다, #752 [#151]).

**T3.27 `feat(portfolio): sizing slot with built-in sizers and @nx.sizer`** · `M3a` `portfolio` · M · Blocked by: T3.1, T3.Gr · §3.7, §3.8, §5.5.1a
- Context: `Strategy(sizing=)`, `top(weight=…)` 줄임과 두 번 주기 E16, `size.equal`·`value`·`inverse_vol`·`score`·`vol_parity`·`stop_risk`, 꾸밈 `cash_floor`(`size.kelly`는 예약 E18, v1.x [R4F-02]), 목록 순서, `SizingContext`(계좌 없음), `@nx.sizer`(units/weights, E41), 입력 없는 종목의 skips, `TargetFrame.stage = sizing`·`pre_risk_weight`.
- Done means: `examples/strategies/inverse_vol_kr.py`의 판단 하나에서 `explain`이 construction → sizing 비중을 보이고, 줄임과 명시 사이저 결과가 같다고 출력.
- Acceptance: `tests/golden/test_sizing.py::test_G78`, `::test_G83`, `::test_G95_score_vol_parity_cash_floor`, `tests/unit/portfolio/test_sizing.py::test_shorthand_equals_explicit_bit`, `::test_weight_given_twice_E16`, `::test_kelly_reserved_E18`, `::test_stop_risk_reads_exit_pct`, `::test_user_sizer_negative_E41`, `tests/property/test_risk_invariants.py::test_P_SIZE_PURE`.

**T3.28 `feat(portfolio): ERC by fixed-order coordinate descent with defined fallback, and vol_target`** · `M3a` `portfolio` · M · Blocked by: T3.27 · §5.5.1a
- Context: 목록 제거 공분산(`instrument_id` 순 왼쪽 접기, BLAS 없음), 수축 `shrink`, 좌표 하강(시작 1/σ, 500바퀴, 1e-14), 대체 a/b/c → `inverse_vol` + E43 + skips, 꾸밈 `vol_target`(네 항 최솟값 — 넷째 = 롱숏 가능 영역, 키우기 상한).
- Done means: 대체가 일어나는 합성 전략에서 보고서가 "erc did not converge on k of m decisions; inverse_vol used"와 이유별 건수를 출력.
- Acceptance: `tests/golden/test_sizing.py::test_G79`, `::test_G80`, `::test_G81`, `::test_G81d_long_short_bound`, `tests/unit/portfolio/test_erc.py::test_fixed_order_bit_stable`, `::test_fallback_reasons_counted`, `::test_no_blas_calls`.

**T3.29 `feat(risk): ordered risk rule list with market-only built-ins, user rules and waterfall`** · `M3a` `risk` · M · Blocked by: T3.27, T3.Gr · §5.5.2, §5.5.2a waterfall
- Context: `risk=[…]` 목록(적힌 순서, `graph_hash`), 배수 `m ∈ [0,1]` 적용·E41, `group_caps`(gross/net, `<unknown>`), `regime`(3값), `vol_cap`, `liquidity_cap(capital="notional")`, 노출 상한 맞춤을 목록 뒤에, `@nx.risk_rule(reads_account=False)`, `reason = risk:{rule}`, `waterfall.parquet`, 보고서 "risk waterfall"·"risk order" 줄.
- Done means: `risk=[nx.risk.group_caps(nx.Item.sector, max=0.3), nx.risk.vol_cap(0.15)]` 전략의 보고서가 칸별 평균 `Σ|w|`와 발동 판단 수(분자/분모)를 출력.
- Acceptance: `tests/golden/test_risk.py::test_G82`, `::test_G85`, `::test_G86`, `tests/unit/risk/test_group_caps.py::test_caps_and_cash`, `::test_no_account_state_input`, `tests/unit/risk/test_rules.py::test_mult_out_of_range_E41`, `::test_order_in_graph_hash`, `::test_account_rule_before_market_rule_E16`, `tests/unit/risk/test_liquidity_cap.py::test_adv_needs_half_lookback`, `tests/property/test_risk_invariants.py::test_P_RISK_SHRINK`.

**T3.30 `feat(risk): account layer with final targets, risk state, drawdown brake and portfolio stop`** · `M3a` `risk` · M · Blocked by: T3.29, T3.12, T3.5b, T3.22, T3.14 · §1.3 INV-23, §5.5.2a, §5.5.2b, §5.6.7
- Context: `final_weight` 칼럼과 계좌 층(규칙 없으면 부르지 않고 복사), 읽기 전용 계좌 보기, `risk_state.parquet`(체크포인트에 포함), `drawdown_brake`(brake/linear, 그림자 지수, 재진입 때 고점 다시 잡기), `portfolio_stop`, `liquidity_cap(capital="nav")`, `reads_account=True` 사용자 규칙, 파산 슬리브는 층 건너뜀, 5.6.7이 `final_weight`를 씀, 층 뒤 최종 제약 점검과 `constraint_residual` skips 행·보고서 머리 줄(5.5.2b) [#151].
- Done means: `examples/strategies/erc_brake.py` 실행 요약에 "drawdown brake: 2 of 120 decisions braked, 1 round trip"과 브레이크 구간이 보인다.
- Acceptance: `tests/golden/test_risk.py::test_G84`, `::test_G87_account_part`, `tests/property/test_risk_invariants.py::test_P_RISK_OFF`, `tests/unit/risk/test_account_layer.py::test_not_called_without_account_rules`, `::test_state_roundtrip_resume`, `::test_shadow_includes_delisting_loss`, `::test_ruined_writes_suspended_row`, `::test_negative_zero_normalized`, `::test_band_prior_uses_canonical`, `tests/property/test_execution_invariants.py::test_P_RESUME_with_risk_state`, `tests/unit/risk/test_final_check.py::test_residual_kept_never_E46`.

**T3.31 `feat(portfolio): @nx.portfolio user construction block`** · `M3a` `portfolio` · S · Blocked by: T3.1, T0.4b · §3.7 블록 계약, §3.8
- Context: `PortfolioContext`(점수·순위·유니버스·앞 `TargetState` 읽기만), 출력 = id → ±1, 순위 = 점수 순 + 동률 열쇠, 유니버스 밖·쪽 값 오류 E41, 공매도 꺼짐에서 −1은 E16.
- Done means: `custom-portfolio` 예제(점수 상위 중 업종별 1개)가 screen 목표를 출력.
- Acceptance: `tests/unit/portfolio/test_user_portfolio.py::test_selection_only`, `::test_out_of_universe_E41`, `::test_short_needs_shorting_E16`, `::test_side_both_E16_use_long_short`.

**T3.32 `feat(artifacts): skip ledger and no-silent-failure summary`** · `M3a` `artifacts` · S · Blocked by: T3.14, T0.4b · §6.6 조용한 실패 금지, §5.9.1
- Context: `skips.parquet`, 이유 코드 목록 `skips.toml`(이유마다 E 코드), E45, 보고서·CLI 첫 화면 "skipped:" 줄(0이면 none).
- Done means: 결측이 많은 합성 전략의 backtest 첫 화면에 "skipped: n rows in k reasons (top: …)"가 보인다.
- Acceptance: `tests/property/test_skips.py::test_P_SKIP`, `tests/unit/artifacts/test_skips.py::test_every_reason_has_code`, `::test_summary_line_always_present`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #246 and #570): `declaration_unchecked`(E45)는 6.6의 사유 목록에 있고 엔진은 실행 끝에 그것을 경고하지만, `skips.parquet`에는 행이 가지 않고 `skips.toml`은 없다. 이 티켓이 그 행을 쓴다.

**T3.34 `feat(api): strategy.replace and backtest preview`** · `M3a` `api` · S · Blocked by: T3.13a, T3.27 · §3.7, §3.8 preview, §3.10
- Context: `Strategy.replace(**slots)`(이름 표시 `~slot`), `backtest(preview=True)`·CLI `--preview`(선택 구간 안 마지막 1년·거래대금 상위 200·시나리오 끔·`kind="preview"`, 새 전략이면 후보 +1·관측 `fidelity="preview"`, hygiene `preview runs` 줄), `[preview]` 키.
- Done means: `uv run nexusbt backtest examples/strategies/mom_kr.py --preview`가 "PREVIEW — 1y (train segment), top 200 …" 줄과 걸린 시간을 출력하고, 처음 본 전략이면 study 후보 수가 1 늘고 hygiene에 `preview runs` 줄이 보인다.
- Acceptance: `tests/unit/api/test_replace.py::test_replace_changes_only_named_slots`, `tests/unit/api/test_preview.py::test_preview_new_strategy_counts_as_candidate`, `::test_preview_period_inside_segment`.

#### M3b — 주문 종류 (9.0의 지정가·손절·손절지정가·탈출)

**T3.15b `feat(execution): confirm zipline 3.2.1 trigger semantics for the parity preset`** · `M3b` `execution` · S · Blocked by: T3.15a, T3.5b, T3.22 · §5.6.15 [SC-12, OQ-9]
- Context: zipline 3.2.1 `finance/execution.py`·`finance/order.py`(발동 상태)·`finance/slippage.py`를 고정판에서 읽어 일봉 발동·체결 가격 규칙을 확인하고 5.6.15 표의 "[추]" 줄을 확정하거나 고친다(명세 고침은 PR 설명의 "spec deviation" + ADR-0021 갱신).
- Done means: PR 설명에 zipline 고정판 소스 줄 인용과 확정한 규칙.
- Acceptance: `tests/unit/execution/test_preset_zipline.py::test_trigger_on_close_only`.

**T3.Gb `test(golden): order-type cases (G-02..G-09, G-32, G-33, G-37..G-40)`** · `M3b` `golden` · M · Blocked by: T0.9 · §5.6.2a, §5.6.4, §8.2
- Context: 지정가 시가·through/touch, 손절 갭·장중, 손절지정가(`Lp = Sp` 경계 포함), OCO, 시가 진입 같은 봉 손절, 장중 진입 같은 봉 이익실현 없음, H/L null, 체결 기록 칼럼, 발동 지속(G-37), 부분 OCO 보호(G-38), 탈출 만료 없음(G-39), 장중 매도 대금(G-40). T3.6·T3.7 전에 병합.
- Done means: `uv run python tests/golden/check/G-37.py`가 세션별 발동 상태·`remaining_qty`를 출력.
- Acceptance: `test_handcalc_self.py::test_cases_order_types_expected_present`.

**T3.6 `feat(execution): limit, stop and stop-limit daily fill rules with persistent triggers and fill records`** · `M3b` `execution` · M · Blocked by: T3.5b, T3.15b, T3.Gb · §5.6.4, §5.6.3 [SC-11]
- Done means: G-02~G-06, G-32, G-33, G-37, G-40 통과, 실행 경고에 E11 한 줄과 "x/n fills judged on daily bars", 가정 문장 줄.
- Acceptance: `test_execution.py::test_G02` … `::test_G06`, `::test_G32`, `::test_G33`, `::test_G37_stop_stays_triggered_after_partial`, `::test_G40_intraday_sale_cannot_fund_same_bar_buy`, `tests/unit/execution/test_fill_rules.py::test_through_vs_touch_table`, `::test_stop_limit_equal_boundary`, `::test_fill_rule_names`.

**T3.7 `feat(execution): exit order lifecycle, resizing and OCO`** · `M3b` `execution` · M · Blocked by: T3.6 · §3.7 탈출, §5.6.2a, §5.6.4
- Done means: G-07~G-09, G-38, G-39 통과; 트레일링 손절가가 날마다 오르는 표 출력.
- Acceptance: `test_execution.py::test_G07`, `::test_G08`, `::test_G09`, `::test_G38_partial_oco_keeps_protection`, `::test_G39_exit_never_expires`, `tests/unit/execution/test_exits.py::test_created_after_entry_fill`, `::test_resized_on_position_change`, `::test_trailing_updates_at_close`, `::test_time_stop_reserved`, `::test_partial_adverse_oco_keeps_remaining_protection`.
- Notes:
  - owner decides at the cut (#43 Decisions, outside review of 2026-11-03): 경로를 정할 수 있을 때 같은 봉의 이익 실현 예외를 더할지(동작 변경, 골든 사례와 함께; 5.6.4).

**T3.17b `test(parity): L2-d order types against zipline semantics`** · `M3b` `parity` · S · Blocked by: T3.15b, T3.17a · §8.1 [SC-12]
- Done means: L2-d 증거 JSON이 커밋되고 `engine / parity`가 필수 검사로 추가됨(사용자).
- Acceptance: `tests/parity_compare/test_L2.py::test_L2d_order_types_preset`.

**T3.19 `feat(api): explain strategy decisions`** · `M3b` `api` · M · Blocked by: T3.13a, T3.7 · §3.8, §5.9.9 [SC-13]
- Done means: `uv run nexusbt explain examples/strategies/mom_kr_exits.py KR:T00007 2019-06-28`이 단계 1~4와 집행 세션 판정(6단계, 탈출 주문 사건 포함)을 5.9.9 모양으로 출력; 유니버스 Filter에서 떨어진 종목은 "dropped here" 줄.
- Acceptance: `tests/unit/api/test_explain_strategy.py::test_filter_tree_drop_point`, `::test_rank_and_selection`, `::test_stage_weights`, `::test_execution_session_blocked_reason`, `::test_needs_account_state_marked`.

**T3.20 `feat(research): MinTRL, Lo-adjusted Sharpe, drawdown durations and signal-weight correlation`** · `M3b` `research` · M · Blocked by: T3.13a, T3.Ge · §5.7 [SC-08, SC-09]
- Done means: 손으로 만든 수익 계열에서 MinTRL·ρ1·Lo Sharpe(lags ≤ 10)·낙폭 기간·회복 기간·최악 월이 기대값과 같게 출력; Run 첫 화면에 MinTRL·signal-weight corr 줄.
- Acceptance: `tests/unit/research/test_risk_stats.py::test_min_trl_known_value`, `::test_lo_sharpe_only_when_rho_large`, `::test_drawdown_and_recovery_durations`, `::test_worst_month`, `tests/golden/test_metrics.py::test_G61_drawdown_edges`, `::test_worst_month_compounds`, `::test_signal_weight_corr_definition`, `::test_stat_unavailable_cases`, `tests/docs/test_tool_cards.py::test_card[min-trl]`, `::test_card[lo-sharpe]`(D19, #219).
- Notes:
  - carried (#43 Decisions, 2026-11-19, #439): Sharpe, PSR, DSR, MinTRL은 초과 수익 `r_t − rf_t`로 계산하는데 5.7의 `ρ1`과 6.3의 Lo Sharpe 행은 아직 "daily net returns"라 한다. 이 티켓이 자기상관이 어느 수익을 쓰는지 말하고 행들이 따른다.

**T3.Gf `test(golden): price grid cases (G-57)`** · `M3b` `golden` · S · Blocked by: T0.9 · §5.6.4a, §8.2
- Context: G-57 (a)~(h)(US 1 ULP, KR 손절 내림, 지정가 매수 내림, 상하한 계산값, 숏 환매 손절 올림; 가격대를 넘는 비교, 분수 시대·격자 밖 봉, 경계 넘는 맞춤·GTC 재맞춤). T3.24 전에 병합.
- Done means: `uv run python tests/golden/check/G-57.py`가 여덟 사례 (a)~(h)의 원값·격자 값·체결을 출력.
- Acceptance: `test_handcalc_self.py::test_case_G57_expected_present`.

**T3.24 `feat(execution): market price grid for order prices and minimum-unit integer comparisons`** · `M3b` `execution` · M · Blocked by: T3.6, T3.Gf, T0.16c, T0.5b · §5.6.4a, §4.7, §4.5 F-15
- Context: 격자 원천 순서(종목 → `market_rules` → 팩 → 최소 단위), 주문 가격 보수적 맞춤(지정가·손절·탈출·재조정·분할 뒤; 가격대 경계를 넘는 맞춤), 규칙 날짜 GTC 재맞춤(`order_rebased(grid)`), `price_rounded` 사건·`price_unrounded`, 봉·주문 가격의 `base_unit` 정수 변환과 비교, 격자 밖 봉 `off_grid_bar`, F-15, 프리셋 끔.
- Done means: G-57 (a)~(h) 사례 표가 그대로 나오고 `degrade=["no_tick_info"]`에서 E30 "price grid = currency minor unit".
- Acceptance: `tests/golden/test_execution.py::test_G57_price_grid`, `tests/unit/execution/test_grid.py::test_source_order`, `::test_conservative_direction_table`, `::test_ulp_noise_compares_equal`, `::test_price_order_preserved_across_tick_bands`, `::test_snap_crosses_band_to_valid_price`, `::test_gtc_regridded_at_rule_date_boundary`, `::test_off_grid_bar_kept_and_counted`, `tests/property/test_execution_invariants.py::test_P_GRID`.
- Notes:
  - decided (#844 Decisions, 2026-11-27; #802): 거래소가 종목마다 배정하는 등급에 따르는 미국 호가 단위는, 2027-11-01부터의 종목별 단위를 포함해 시뮬레이션하지 않는다. 모든 종목은 그 시장의 일반 규칙을 따르고, 스펙과 규칙 팩이 그것을 문서로 적은 가정으로 말한다.
  - carried (#43 Decisions, 2026-11-20, #660): `_no_grid`는 시장에 어떤 종류의 규칙이 어느 날짜에든 있는지를 읽으므로, 뒤의 행이 앞선 결정의 격자 출처를 바꿀 수 있다. 이 티켓이 #660의 규칙(행은 `valid_from`부터 `valid_to`까지 적용, 앞질러 읽지 않음)으로 있음 검사를 정하고, 그러면 P-FUT이 `market_rules`를 `valid_from`으로 자른다.
  - carried (#43 Decisions, 2026-11-05, #287 and #303): 5.6.4a의 "`U` and `D` … are snapped to the grid too"는 조건 없이 읽히는데 5.6.5는 시장에 호가표가 없으면 반올림하지 않는다. 이 티켓이 5.6.4a가 호가표 없는 경우를 말하게 하되, 스펙 변경으로 주인에게 묻는다.
  - carried (#43 Decisions, 2026-11-16, #453): 격자 출처가 있는 시장에서 격자 출처가 없는 종목은 F-15가 아니라 결정 때 최소 단위로 떨어진다. 이 티켓은 가정 문장에 그 출처를 대고 그런 종목의 수를 준다.
  - owner decides at the cut (#43 Decisions, 2026-11-16, #453): `base_unit`만 있는 팩의 `[grid]`를 열 때 격자로 칠지.
  - carried (#43 Decisions, 2026-11-02, #104): `ticks/kr_tick_table_v1.csv`에서 ETF는 KOSPI, KOSDAQ, KONEX에 공통인 2023년 표(`venue_group = *`)와 `ETF` 행(모든 구간에서 5원) 둘 다에 맞는다. 이 티켓이 어느 것이 이기는지 말한다.
  - carried (#43 Decisions, 2026-11-02, #54): 스펙 4.7은 소수점 이전 미국의 1달러 미만 호가나 2010–2023년 한국 호가표의 KONEX 행 값을 주지 않으므로, 씨앗 표는 어느 행도 갖지 않는다.

**T3.33 `feat(execution): time stop exit in the OCO group and no-reentry rule`** · `M3b` `execution` · S · Blocked by: T3.7, T3.30 · §3.7 탈출, §5.5.2a
- Context: `exits.time_stop(n)`(첫 진입 세션 = 1, 시장 달력 세션·정지일 포함 [V31-52], 종가 뒤 생성·다음 시가), 손절·이익실현과 OCO, 부호 바뀌면 새로 셈; `risk.no_reentry(sessions, after)`(탈출 사건 읽기).
- Done means: `nx.exits.time_stop(5)`가 진입 5세션 뒤 다음 시가에 매도하고 이어지는 판단에서 `no_reentry(21)`이 그 종목을 0으로 둔 것을 `explain`이 보인다.
- Acceptance: `tests/unit/execution/test_exits.py::test_time_stop_oco`, `::test_time_stop_counts_sessions`, `::test_time_stop_resets_on_sign_flip`, `tests/unit/risk/test_no_reentry.py::test_blocks_after_stop_exit`.

**T5.16a `feat(portfolio): strategy state record with checkpoint save and restore`** **[2026-11-04]** · `M3b` `portfolio` · S · Blocked by: T3.12, T3.5b, T3.22 · §5.5.3, §5.6.1 [#152]
- Context: T5.16에서 나눴다(결정 2026-11-04, #152; T3.35 메모는 2026-11-24에 뺐다, #752). 5.5.3의 전략 상태 기록(`sleeve_id`·`instrument_id`를 열쇠로 `target_weight`, `set_by`, `missing_streak`를 가진 `target_state` 행; `risk_state` 행), 열쇠로 정렬한 Arrow 직렬화, 체크포인트(5.6.1)와 `targets.parquet` 옆에 쓰기, 복원, `build_targets(..., prior=)`가 그것을 받고 돌려주기(T7.1 전에는 일정만 쓰는 전략에서 빈 상태). 장부 매니페스트 부분은 T5.16에 남는다.
- Done means: 무작위 세션에서 체크포인트를 남기고 복원한 실행이 멈추지 않은 실행과 비트 같은 정규·최종 목표와 같은 상태 기록을 내고, `missing_streak`가 멈춤을 건너 이어진다.
- Acceptance: `tests/unit/portfolio/test_target_state.py::test_missing_counter_survives_checkpoint`, `::test_short_band_state_roundtrip`, `::test_risk_state_rows_roundtrip`(사건 목표 체크포인트 시험은 2026-11-24에 뺐다, #752).

**T3.35 `superseded`** · `M3b` · Blocked by: none · `on_event`, G-97, G-108과 함께 2026-11-24에 뺐다(#752) [#725 결정 224].

#### M4 — 다중 시장 (KR/US 합성, 시장 규칙 팩) + 공매도·롱숏 [V31-LS]

**T4.G `test(golden): sleeve, timing, currency and tax cases (G-27..G-29, G-36, G-50..G-52)`** · `M4` `golden` · S · Blocked by: T0.9 · §5.1.3, §5.6.3, §5.6.9, §5.6.11a, §8.2
- Context: 슬리브 자금 대기, 서머타임·휴장 어긋남, 환율 묵음, 통화 귀속, `KR_close` 같은 시각 종가 체결 → 판단, 세금 시나리오. T4.1·T4.2·T4.5b·T4.10 전에 병합.
- Done means: `uv run python tests/golden/check/G-50.py`가 종가 체결 `q_i`가 판단에 반영된 주문 수량을 출력.
- Acceptance: `test_handcalc_self.py::test_cases_sleeves_expected_present`.

**T4.1 `feat(execution): multi-sleeve event queue, phase order and clock modes`** · `M4` `execution` · M · Blocked by: T3.12, T3.5b, T3.22, T4.G · §5.1.3, §5.6.3
- Done means: `KR_close`·`market_local` 두 실행의 미국 체결 날짜·가격이 같음을 보여 주는 예제(시장 넘는 항 없음, G-27 일부); 같은 시각 종가 체결이 판단보다 먼저 처리됨을 보이는 사건 순서 표.
- Acceptance: `tests/unit/execution/test_clock.py::test_kr_close_us_uses_previous_close`, `::test_us_close_kr_same_day`, `::test_single_market_forces_local`, `::test_utc_clock_reserved_E18`, `::test_equal_time_close_fill_before_decision`, `::test_clock_name_from_snapshot_markets`, `tests/golden/test_sleeves.py::test_G50`.

**T4.2 `feat(accounting): sleeve funding, fx valuation and drift`** · `M4` `accounting` · M · Blocked by: T4.1, T2.5 · §5.6.9
- Done means: G-27·G-29 통과; daily.parquet에 sleeve_weight 흐름.
- Acceptance: `tests/golden/test_sleeves.py::test_G27`, `::test_G29`, `tests/unit/accounting/test_fx.py::test_direction_and_inverse`.

**T4.3 `feat(compute): cross-market terms gathered at decisions`** · `M4` `compute` · S · Blocked by: T4.1, T2.5 · §5.3.2 (6)
- Done means: `.to("USD").rank(across_markets=True)` 결과가 판단마다 한 순위표.
- Acceptance: `tests/unit/compute/test_cross_market.py::test_gather_uses_row_m_of_d`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #249): `nx.run_pipeline`과 실행기는 `across_markets=True`인 항을 T4.3을 이름 대는 `NotImplementedError`로 거절한다(`test_across_markets_not_supported_yet`). 이 티켓이 결정 때 시장들의 행을 모으고(5.3.1 6단계) 두 거절을 없앤다.

**T4.4 `feat(execution): price-limit history from market rules packs and unknown tradability policy`** · `M4` `execution` · S · Blocked by: T3.5a, T3.24 · §5.6.5, §4.7
- Done means: 2015-06-15 앞뒤 세션의 제한폭 0.15/0.30이 출력; US 팩(가격제한 없음)에서는 상·하한 막힘이 없음; `unknown_tradability="block"` 민감도 실행에서 E27.
- Acceptance: `tests/unit/execution/test_limits.py::test_resolution_order`, `::test_rule_boundary_2015_06_15`, `::test_limits_only_where_pack_defines`, `::test_unknown_tradability_block`, `::test_missing_tradability_dataset_E30`, `::test_computed_limits_on_grid`(G-57 (d)), `::test_market_rules_limit_source_order`.

**T4.5 `feat(execution): realistic dated cost profile end to end`** · `M4` `execution` · M · Blocked by: T3.8 · §5.6.8, §4.7
- Done means: 검증 표(시험용 `verified=true` 사본)로 KR 2014·2024 매도 세금이 표의 다른 값으로 기록됨.
- Acceptance: `tests/unit/execution/test_costs_dated.py::test_tax_by_date`, `::test_us_other_fees`, `::test_venue_group_mapping`.
- Notes:
  - owner decides at the cut (#43 Decisions, outside review of 2026-11-03): 한국 세금에 ETF 거래세 면제 축을 둘지.
  - carried (#43 Decisions, 2026-11-01, #38, #17 and #27): 검증 표는 KOSPI 행이 농어촌특별세(0.15%)를 담는지 말하고, 주는 해마다 1차 출처를 단다. 2014년과 2016년의 증권거래세는 대통령령 제24641호로 같으므로 이 티켓은 2014년과 2024년을 비교한다.
  - carried (#43 Decisions, 2026-11-19, #125 and #103): 비용 씨앗 표에는 KONEX 행, `commission` 행, FINRA TAF가 없고, 겹치는 증권거래세 행과 농어촌특별세 행을 다루는 스펙 규칙도 없다.

**T4.5b `feat(accounting): user-configured tax scenario`** · `M4` `accounting` · M · Blocked by: T4.G, T4.2, T3.13a · §5.6.11a, §3.11 *(사용자 결정 2026-10-28: 세금은 설정 파일에 사용자가 적음)*
- Done means: `[taxes] profile = "custom"` 예제 설정(US 묶음 22%, 공제 2,500,000원, average)으로 돌리면 `tax.parquet`의 해별 세금이 G-51 손계산과 같고, `pay = "cash"`에서 다음 해 5월 첫 세션 현금이 그만큼 줄어든다(G-52). `profile = "none"`이면 결과가 이 티켓 전과 비트 단위로 같다.
- Acceptance: `tests/golden/test_taxes.py::test_G51`, `::test_G52`, `tests/unit/accounting/test_tax_basis.py::test_average_vs_fifo`, `::test_fx_conversion_at_valuation_rate`, `::test_none_profile_unchanged`.

**T4.6 `feat(api): benchmarks from index instruments`** · `M4` `api` · S · Blocked by: T3.13a, T3.Ge · §5.7, §4.6, §4.5 F-12
- Done means: 합성 스냅숏에서 벤치마크 열(`auto`가 시장마다 TR 지수 하나를 고름); `degrade=["no_benchmarks"]`에서 "n/a: not in snapshot"; TR 지수가 둘이면 E16 목록.
- Acceptance: `tests/unit/api/test_benchmarks.py::test_combined_benchmark_sleeve_weighted`, `::test_missing_is_na`, `::test_auto_picks_single_tr_index`, `::test_auto_ambiguous_E16`, `tests/golden/test_metrics.py::test_G62_benchmark_alignment`, `::test_weighting_label_in_header`.

**T4.7 `feat(api): combined multi-market backtest and screen reports`** · `M4` `api` · M · Blocked by: T4.2, T4.3, T4.6, T4.10 · §3.9
- Done means: `uv run nexusbt backtest examples/strategies/value_mom.py`가 KR/US 열, 슬리브 비중 흐름, 비용 민감도, `fx contribution` 줄을 출력; `nexusbt screen`이 "KR {date} close · US {date} close"를 출력.
- Acceptance: `tests/unit/api/test_combined.py::test_combined_equals_sum_of_sleeves`, `::test_screen_two_markets_asof`, `::test_fx_contribution_line`, `::test_markets_header_line`.

**T4.8 `test(property): DST, holiday mismatch, timing and currency metamorphic cases with preconditions`** · `M4` `property` · S · Blocked by: T4.2, T4.10 · §8.2, §8.3
- Done means: G-28 통과; M-CCY·M-SLEEVE 통과(전제 안), `KR_close` + 시장 넘는 순위 반례는 관계가 깨짐을 확인.
- Acceptance: `tests/golden/test_sleeves.py::test_G28`, `tests/property/test_execution_invariants.py::test_P_FUT_two_markets`, `tests/property/test_metamorphic.py::test_M_CCY`, `::test_M_SLEEVE`, `::test_M_SLEEVE_counterexample_cross_market`, `tests/property/test_execution_invariants.py::test_P_SLEEVE_ISO`.

**T4.9 `docs(examples): m4 multi-market walkthrough and stage measurement`** · `M4` `docs` · S · Blocked by: T4.7, T1.24, T0.8c · §7, §8.5
- Done means: README "한국+미국 함께" 절이 돌고, 사람이 계산 기계에서 돌린 `bench/run.py --stages m4 --snapshot synth-full-0001`가 P5 전체(두 슬리브, 시나리오 5개), KR+US P5-daily, P7을 cold와 warm으로 출력(수치는 마일스톤 추적 이슈에).
- Acceptance: `tests/docs/test_examples.py::test_readme_m4`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #264): 7장의 P5 행과 M4 끝 행, 이 항목, A-51의 "five scenarios"는 주인의 요청으로 적힌 그대로 둔다. 다만 가정 퇴출이 있는 한국 실행은 `ca_exit_lo`를 하나 더 다시 돌린다.

**T4.10 `feat(artifacts): currency attribution and exposure tables`** · `M4` `artifacts` · M · Blocked by: T4.2, T3.14 · §5.6.9, §5.9.1 [SC-07, OQ-3]
- Done means: G-36 통과; `runs/<id>/attribution.parquet`의 현지+환율+교차 = 기준 통화 슬리브 수익(날짜별); `exposures.parquet`에 통화·업종(슬리브별)·크기·상위 10·현금 비중.
- Acceptance: `tests/golden/test_sleeves.py::test_G36`, `tests/unit/artifacts/test_attribution.py::test_fx_attribution_sums`, `::test_annual_linking_exact`, `::test_annual_fx_components_sum_G36`(교차 = `R − L − F`), `::test_exposures_columns`, `::test_sector_exposure_per_sleeve_only`.
- Notes:
  - owner decides at the cut (#752 Decisions, 2026-11-27; #725 Decisions 250): `exposures.parquet`(5.9.1)의 `sector` 칼럼이 무엇으로 묶는지. 그것이 읽던 분류 체계는 `classifications`와 함께 빠졌고, 칼럼은 새 규칙이나 설정 이름 없이 남는다.

**T4.11 `test(markets): market names from data with a synthetic third market ZZ`** · `M4` `markets` · S · Blocked by: T4.7, T0.5b · §4.7, §4.8, §3.11
- Context: 합성 `markets=("KR","ZZ")` 스냅숏(달력 `XZZZ`, 통화 `XTS`), 시험용 `tests/fixtures/ZZ.toml` 규칙 팩.
- Done means: 팩 없이 `nx.universe("ZZ")` 백테스트가 E18 문장을 내고, `allow_untested = true`면 "untested market rules: ZZ" 머리 줄과 함께 돌고, 시험 팩을 넣으면 같은 전략이 코드 변경 없이 돈다; `grep -rn '"KR"\|"US"\|XKRX\|XNYS' src/nexusbt`가 `resources/markets/`·문서 문자열 밖에서 0건.
- Acceptance: `tests/unit/markets/test_markets.py::test_zz_without_pack_E18`, `::test_allow_untested_stamped`, `::test_zz_with_pack_runs`, `tests/repo/test_no_hardcoded_markets.py::test_no_market_literals_in_src`.

**T4.12 `feat(research): benchmark-relative metrics and monthly return table`** · `M4` `research` · S · Blocked by: T4.6, T3.Ge · §5.7, §3.9
- Context: 초과 수익(산술·기하 이름 따로), 추적오차, IR, 초과 MDD, 달력 월 복리 표(HTML "monthly"), 첫 화면 "vs benchmark" 줄, 머리의 가중 방식 표시.
- Done means: G-62 숫자(추적오차 0.112250, IR 11.224972)가 출력되고 HTML에 월별 표가 있다.
- Acceptance: `tests/golden/test_metrics.py::test_G62_relative_metrics`, `tests/unit/research/test_benchmark_relative.py::test_arith_vs_geom_named`, `::test_monthly_compounds`, `::test_na_without_benchmark`.

**T4.13 `feat(execution): optional dated and liquidity-tiered provisional cost tables`** · `M4` `execution` · S · Blocked by: T3.8 · §3.7, §5.6.8, §4.7 [V31-27]
- Context: `provisional(table=)`·`[costs] provisional_table`(사용자 작성 CSV: 시장·쪽·기간·ADV 금액 구간·bp), 판단 시점 ADV로 행 찾기, 빈 곳 E23, HTML "cost tiers". 기본(표 없음)은 v3와 같음.
- Done means: 시험 표로 KR 2014·2024 매도와 ADV 하위·상위 종목이 다른 bp로 기록되고, 표 없는 실행은 바이트가 같다.
- Acceptance: `tests/unit/execution/test_provisional_table.py::test_dated_rows`, `::test_adv_tiers_use_lagged_adv`, `::test_gap_E23`, `::test_default_unchanged`.

**T4.Gs `test(golden): short accounting, financing, ruin and cash-interest cases (G-67..G-70, G-74..G-77, G-94)`** · `M4` `golden` · M · Blocked by: T0.9 · §5.6, §8.2
- Context: 숏 기본·대차 발생(주말·진입 전·장중 0), 숏 배당 지급·추정 교체·조건 늦음·net 복원, 숏 분할, 숏 폐지 이익·규칙 추정, 숏 합병, 숏 실현 이익 세금(진입 비용 한 번), 숏 파산, 현금 이자. T4.15a~c·T4.19 전에 병합.
- Done means: `uv run python tests/golden/check/G-67.py`가 세션별 대차 발생 일수·금액과 다리 행을 출력.
- Acceptance: `test_handcalc_self.py::test_cases_short_accounting_expected_present`.

**T4.Gt `test(golden): long-short targets, short orders and ban cases (G-71..G-73, G-109)`** · `M4` `golden` · S · Blocked by: T0.9 · §3.7, §5.5, §5.5.2b, §5.6.2a~5.6.7, §8.2
- Context: 공매도 금지 구간(반열림·범위 문법), 롱숏 책 다리·노출 상한·쪽 예산·가능 영역, 숏 탈출 거울(세 단계)·반전 대기. T4.14·T4.16a·T4.16b 전에 병합.
- Done means: `uv run python tests/golden/check/G-72.py`가 롱·숏 다리 행과 노출(총 1.0, 순 0), (b) 0.05, (c) E16 문장을 출력.
- Acceptance: `test_handcalc_self.py::test_cases_short_orders_expected_present`, `::test_case_G109_expected_present`(2026-11-04: 짝 거래 한 다리의 상한 [#151]).

**T4.17 `test(regression): long-only core-table value-hash baseline and the P-SHORT-OFF harness`** · `M4` `property` · S · Blocked by: T4.7, T4.5b, T4.13 · INV-22, §8.3
- Context: 예제 전략(M3a·M3b·M4 예제)과 무작위 롱 전략 몇 개를 합성 small로 돌려 핵심 표 넷(`targets`, `orders`, `account_events`, `daily`)의 **값 해시**를 `tests/regression/longonly_core_value_hashes.json`에 기록하는 스크립트, 같은 빌드 차등 시험 틀(`enabled=false` 대 `enabled=true` + 음수 없음 + 기본 노출), 꺼진 실행의 숏 사건 0건 시험. 기준선 파일은 golden 보호 경로이고, 스키마를 바꾸는 티켓만 PR 설명의 이유 + 사용자 승인 라벨 `baseline-update`로 고친다(guard가 라벨 없는 변경을 거절).
- Done means: `uv run pytest -k P_SHORT_OFF`가 "core tables n/n match baseline · differential runs identical"을 출력하고, 라벨 없는 기준선 변경 PR이 guard에서 실패한다.
- Acceptance: `tests/property/test_shorting.py::test_P_SHORT_OFF_differential`, `::test_P_SHORT_OFF_no_short_events_when_disabled`, `::test_P_SHORT_OFF_core_tables_baseline`, `tests/repo/test_golden_guard.py::test_baseline_update_needs_label`.

**T4.14 `feat(portfolio): signed targets, bottom(), long-short books and exposure limits`** · `M4` `portfolio` · M · Blocked by: T4.17, T3.1, T3.30, T4.Gt · §3.7, §5.5.1, §5.5.2, §5.5.2b, §3.11 `[shorting]`
- Context: 부호 있는 `target_weight`·`side`, `bottom`, `long_short`(쪽 예산 곱하기, 같은 종목 충돌 규칙), 가능 영역 `long_weight + c·short_weight ≤ 1` 실행 전 E16, 총·순 노출 상한 맞춤(켜졌을 때만, `math.fsum`, 0 쪽 축소만), 공매도 꺼짐이면 E16, 노출 칸.
- Done means: G-72의 목표 표(롱 +0.25 × 2, 숏 −0.25 × 2)와 `max_gross = 0.8`의 축소, (b) `top(1, max_weight=0.1)` 쪽의 0.05, (c) 130/30의 E16 문장이 출력되고, 꺼진 설정에서 `bottom`은 E16.
- Acceptance: `tests/golden/test_portfolio.py::test_G72_targets_and_caps`, `tests/unit/portfolio/test_long_short.py::test_bottom_mirrors_top`, `::test_conflict_long_kept`, `::test_scale_toward_zero_only`, `::test_disabled_E16`, `::test_side_budget_preserves_cap_residual`, `::test_empty_and_overlapping_sides`, `::test_infeasible_book_E16`, `tests/unit/portfolio/test_risk.py::test_exposure_cap_skipped_when_disabled`, `::test_equal_weight_ninths_not_rescaled`, `::test_net_interval_must_contain_zero`, `tests/property/test_shorting.py::test_P_SHORT_OFF_differential`, `::test_P_SHORT_OFF_core_tables_baseline`, `tests/golden/test_risk.py::test_G109_pair_leg_cap_residual` [#151].

**T4.15a `feat(accounting): short positions - signed state, collateral, financing accrual, mandatory debits and ruin`** · `M4` `accounting` · M · Blocked by: T4.14, T3.22, T4.5b, T4.Gs · §5.6.1, §5.6.3(1)(6), §5.6.7, §5.6.9
- Context: 부호 있는 `qty`, 평균 공매도 가격, 담보 `reserved`·`buying_power`(공매도 배분 비용 함수), 세션 시작 대차 비용·리베이트 발생, 다리 `financing` 행, 꼭 내야 하는 의무의 음수 현금 기입, 파산 확인(`T_i` 전)·`ruined` 상태·주문 멈춤·지표 n/a·머리 줄, E38(담보 부족·음수 현금·파산).
- Done means: G-67 (a)~(c)와 G-76 표가 출력되고 숏 보유 실행의 `reconciled: yes`; 파산 실행의 Run 머리에 "ruined KR on {date}".
- Acceptance: `tests/golden/test_short.py::test_G67`, `::test_G76_ruin`, `tests/unit/accounting/test_short.py::test_collateral_buying_power`, `::test_no_forced_buy_in_E38`, `::test_borrow_fee_weekend_cover`, `::test_new_short_not_charged_before_entry`, `::test_unfunded_short_obligation_books_negative_cash`, `::test_negative_V_never_flips_sides`, `::test_ruined_sleeve_stops_new_orders`, `tests/golden/test_short.py::test_G94_exit_blocked_cash_carried`, `tests/property/test_execution_invariants.py::test_P_BRIDGE_with_shorts`.
- Notes:
  - owner decides at the cut (#43 Decisions, 2026-11-13, #312): #312의 Decision이 기대던 `from_parquet` 입력 길, `known_on`, E3, E47이 빠진 지금 종목별 대주 수수료가 어떻게 들어오는지(예: 값 표의 항목), 그리고 #312 Decision (4)의 미국 공매도 유지 하한을 그와 함께 스펙에 넣을지.

**T4.15b `feat(accounting): short dividends, corporate actions and delistings on negative quantities with estimate replacement`** · `M4` `accounting` · M · Blocked by: T4.15a · §5.3.3a, §5.6.9~5.6.13
- Context: 숏 배당 의무(세전, net이면 복원 또는 E13, 원천징수는 q > 0만), 의무 수량은 효력 세션 보유로 고정, 분할·주식배당·합병·분할설립의 음수 수량(정수 산술), 숏 폐지 종료 의무(세 기준, 5.6.13)와 `decision_value`의 규칙 추정, `nav_economic` 추정 교체.
- Done means: G-68 (a)~(d)·G-69·G-70 (a)(b)·G-74 표가 출력된다.
- Acceptance: `tests/golden/test_short.py::test_G68`, `::test_G68c_short_obligation_survives_cover_before_terms`, `::test_G69`, `::test_G70`, `::test_G74`, `tests/unit/accounting/test_short.py::test_unknown_short_estimate_replaced_once`, `::test_short_net_dividend_gross_up_or_E13`, `tests/property/test_execution_invariants.py::test_P_QTY_with_shorts`.

**T4.15c `feat(accounting): short realized gains in the tax scenario`** · `M4` `accounting` · S · Blocked by: T4.15b · §5.6.11a
- Context: 숏 환매 실현 손익(공매도 대금 − 공매도 비용(비율만큼 한 번) − 환매 대금 − 환매 비용), 같은 묶음 합·손실 상계.
- Done means: G-75 (a)(b)가 출력된다.
- Acceptance: `tests/golden/test_short.py::test_G75`, `::test_G75b_short_entry_cost_allocated_once`.

**T4.16a `feat(execution): short-sale and cover orders - four-action priority in every phase, reversal gating and mirrored daily fills`** · `M4` `execution` · M · Blocked by: T4.15a, T3.7, T3.24, T4.Gt · §5.6.2, §5.6.3, §5.6.4, §5.6.6, §5.6.7
- Context: `sell_short`·`buy_to_cover`, 부호를 넘는 Δ 두 주문과 `blocked(closing_leg_pending)`, 세 체결 단계의 위험 줄이는 순서와 배분(장중 늘리는 주문은 같은 단계 대금·담보 해제 미사용), 물리 방향 용량 공유, 거울 체결 규칙, 환매 ≤ `|q|`(`qty_cancelled(over_cover)`), 단계별 담보 평가 시점.
- Done means: G-73 세 단계 변형 표가 출력되고, 롱 10주 → 숏 5주 의도에서 롱 매도가 상한으로 6주만 체결된 날 공매도가 체결되지 않는다.
- Acceptance: `tests/unit/execution/test_short_orders.py::test_split_crossing_zero`, `::test_four_action_priority_each_phase[open]`, `::test_four_action_priority_each_phase[intraday]`, `::test_four_action_priority_each_phase[close_fill]`, `::test_short_leg_waits_for_close_leg`, `::test_cover_capped_at_short_size`, `::test_capacity_shared_by_physical_direction`, `::test_collateral_mark_per_phase`, `tests/property/test_shorting.py::test_P_SHORT_OFF_differential`.

**T4.16b `feat(execution): short exits and ban periods from rules packs`** · `M4` `execution` · M · Blocked by: T4.16a, T4.4 · §3.7 탈출, §5.6.2a, §5.6.4, §5.6.5, §4.7
- Context: 숏 탈출 주문(손절·이익실현·트레일링)과 생애(진입 = 0 → 음수, 같은 봉 불리한 쪽, 트레일링 최소, OCO 형제는 남은 보유 0일 때만 취소), 팩 `[shorting] ban_table`(구간 반열림, `scope` = `all`/`index:`/`classification:`, `except_universe_ids` 합집합), `blocked(short_ban)`, 가정 문장(대차 가능 수량 없음, 업틱 규칙 없음).
- Done means: G-71·G-73 표가 출력되고 KR 시험 팩 금지 구간에 새 공매도 0건·환매 체결 n건이 Run 줄에 보인다.
- Acceptance: `tests/golden/test_short.py::test_G71_ban_period`, `::test_G73_short_exit_mirror`, `tests/unit/execution/test_short_orders.py::test_short_entry_creates_exit_immediately`, `::test_short_intraday_entry_adverse_exit`, `::test_short_trailing_low_water`, `::test_partial_adverse_oco_keeps_remaining_protection`, `::test_ban_allows_cover`, `::test_partial_reopening_union_membership`, `::test_ban_interval_endpoints`, `::test_ban_classification_scope`, `::test_assumption_lines`.
- Notes:
  - owner decides at the cut (#43 Decisions, outside review of 2026-11-03): 금지 표가 한국 공매도 과열 종목 지정을 받을지(KRX 문서는 얻었고, 다음 세션 금지는 2차 출처에만 있다).

**T4.18 `test(parity): L2-e long-short against the zipline preset`** · `M4` `parity` · S · Blocked by: T4.16b, T3.17a · §8.1, §5.6.15
- Context: zipline 프리셋의 음수 보유(담보 제약 없음, 대차 0, 숏 배당 지급)로 월말 top-N 롱 + bottom-N 숏을 zipline과 대조.
- Done means: L2-e 증거 JSON이 커밋된다.
- Acceptance: `tests/parity_compare/test_L2.py::test_L2e_long_short_preset`.

**T4.19 `feat(accounting): cash interest on positive cash balances`** · `M4` `accounting` · S · Blocked by: T4.15a, T4.Gs · §3.11 `[account]`, §5.6.3(1), §5.6.9, §5.7 [사용자 결정 2026-10-28]
- Context: `[account] cash_rate_bps`(float 또는 {MARKET: float}, 기본 0), 세션 시작 발생(앞 세션 끝 `cash_minor > 0`만, 음수 현금 0), 사건 `cash_interest`, 다리 `financing`, 보고서 머리 "cash earns {r}%", 금융 비용 대조에 포함.
- Done means: G-77이 출력되고 `cash_rate_bps = 0` 실행의 핵심 표 값 해시가 이 티켓 전과 같다.
- Acceptance: `tests/golden/test_accounting.py::test_G77_cash_interest`, `tests/unit/accounting/test_cash_interest.py::test_default_zero_identical`, `::test_no_interest_on_negative_cash`, `tests/property/test_execution_invariants.py::test_P_BRIDGE_with_cash_interest`.

**T4.Gm `test(golden): margin account cases (G-99..G-104)`** · `M4` `golden` · S · Blocked by: T0.9 · §5.6.7a, §8.2
- Context: 130/30 증거금·대출 이자(G-99), 마진 콜 다음 시가 비례 축소(G-100), `vol_target` 1.5배(G-101), 현금 계좌 거절 E16(G-102), 음수 자본 강제 청산·보유량 상한(G-104) [R4H]의 손계산 사례. 다른 세션에서 써서 T4.20 전에 병합(8.2).
- Done means: `uv run python tests/golden/check/G-100.py`가 콜 세션·부족액·강제 축소 수량·축소 뒤 E/MM을 표로 출력.
- Acceptance: `test_handcalc_self.py::test_cases_margin_expected_present`.

**T4.20 `feat(accounting): margin account type - buying power, debit interest, margin call and forced reduction`** · `M4` `accounting` · M · Blocked by: T4.19, T4.16a, T4.17, T4.Gm · §3.11 `[account]`, §5.6.7a, §5.5.1a, §5.6.3(1) [사용자 결정 2026-10-28]
- Context: `[account] type`(`"cash"` 기본)·`initial_margin`·`maintenance_margin`·`debit_rate_bps`(규칙 팩 씨앗 US 0.50/0.25 미검증, KR 없음), 요구액 식 하나 `R(ρ)`, `excess` 안 배분, 증거금 가능 영역 E16, 대출 이자 `margin_interest`·다리 `financing`, 종가 `margin_call` → 다음 시가 `forced_liquidation`(위험 줄이는 묶음 먼저), 파산 확인 그대로, `vol_target`의 증거금 `G_max`, 현금 계좌에서 증거금 키 E16, 매니페스트 `policies.account`, 보고서 머리 줄, P-MARGIN-OFF 기준선은 이 티켓 첫 커밋에서 기록.
- Done means: `uv run nexusbt backtest examples/strategies/long_short_130_30_margin.py`가 대출 이자 합·마진 콜 세션 수·강제 축소 금액을 출력하고, 같은 전략을 `type = "cash"`로 돌리면 E16을 낸다; 기본 설정 실행의 핵심 표 값 해시가 이 티켓 전과 같다.
- Acceptance: `tests/golden/test_accounting.py::test_G99_margin_130_30_interest`, `::test_G100_margin_call_next_open`, `::test_G101_vol_target_margin`, `::test_G102_cash_rejects_margin_keys`, `tests/unit/accounting/test_margin.py::test_single_requirement_formula`, `::test_debit_excludes_short_proceeds`, `::test_forced_reduction_order_risk_reducing_first`, `::test_ruin_check_with_debit`, `tests/property/test_margin.py::test_P_MARGIN_OFF_baseline`, `::test_P_MARGIN_OFF_differential`, `tests/property/test_execution_invariants.py::test_P_BRIDGE_with_margin_interest`.
- Notes:
  - carried (#43 Decisions, 2026-11-02, #54): 규칙 팩의 미국 증거금 씨앗은 이 티켓의 것이다.

#### M5 — 모의 운용

**T5.1 `feat(artifacts): paper book store with locked transactions, state versions and recovery`** · `M5` `artifacts` · M · Blocked by: T3.3, T1.14b · §5.9.6 [INV-19]
- Done means: `nx.book("paper:demo")` 뒤 `runs/books/demo/HEAD`·`book.json`(definition_sha256)·체크포인트 폴더가 생김; 커밋 경계마다 죽인 쓰기 뒤 다시 열면 이전 또는 다음 상태 하나이고 찌꺼기는 `orphans/`; 두 번째 작성자는 E35.
- Acceptance: `tests/unit/artifacts/test_books.py::test_atomic_head`, `::test_events_append_only`, `::test_book_json_definition`, `::test_P_BOOK_crash_at_each_boundary_recovers`, `::test_concurrent_writer_rejected_E35`, `::test_definition_change_E35`, `::test_snapshot_history_recorded`, `::test_book_pin_held_while_book_exists`.

**T5.2 `feat(api): live order preview with decision-level idempotency`** · `M5` `api` · M · Blocked by: T5.1, T4.7 · §3.8 live, §5.9.6
- Context: 5.9.6 규칙 1(`sheet_emitted`, `sheet_id`, 정정된 스냅숏이나 바뀐 장부면 새 주문표, `CANCELLED(superseded)`, 닫힌 주문표는 T5.3); `status.json` `current_sheets`와 규칙 3은 T5.7의 `reconcile`과 함께.
- Done means: `nexusbt live ... --book paper:demo` 두 번째 호출이 E26 알림과 같은 주문표; `live → fill → live`(같은 판단)에서도 새 주문이 나오지 않는다; 체결 전 정정된 스냅숏에서 `live`는 옛 것을 가리키는 새 `sheet_id`를 준다.
- Acceptance: `tests/unit/api/test_live.py::test_same_key_same_orders`, `::test_key_excludes_checkpoint_seq`, `::test_live_fill_live_same_decision_once`, `::test_non_rebalance_day_exits_only`, `::test_orders_csv_columns`, `::test_same_snapshot_same_sheet_id`, `::test_corrected_snapshot_supersedes_sheet`.

**T5.3 `feat(api): advance paper books with the backtest state machine`** · `M5` `api` · M · Blocked by: T5.2 · §5.9.6
- Done means: `nx.fill(book)`가 워터마크 밖이면 E19(종료 코드 3), 안이면 체결 표; 충돌 뒤 재시작 = 같은 장부.
- Acceptance: `tests/unit/api/test_fill.py::test_watermark_E19`, `::test_crash_recovery_same_book`, `::test_foreign_order_bundle_rejected_E35`, `tests/unit/api/test_live.py::test_closed_sheet_not_superseded`(5.9.6 규칙 1), `tests/property/test_live.py::test_P_LIVE`.

**T5.7 `feat(api): reconcile paper books by recorded-snapshot replay or explicit restatement, and write status.json`** · `M5` `api` · M · Blocked by: T5.3 · §5.9.6, §5.9.7 [SC-14]
- Context: 5.9.6 규칙 3(`first_divergence.id`, 마지막 `reconciled: NO`의 확인 기록이 없는 동안 `live`가 주문표를 내지 않음, E35, `--force` 없음, `nx.acknowledge`와 `nexusbt book acknowledge`, 사건 `divergence_acknowledged`), `status.json` 필드 `current_sheets`와 `first_divergence`, 5.9.7 (5)(`reconcile --day`, 주문일 기록).
- Done means: `uv run nexusbt reconcile --book paper:demo`가 `reconciled: yes (replay)`(종료 코드 0); 새 스냅숏에 정정 사건을 넣고 `--restate`면 "restatement" 표시와 첫 차이; 장부 사건 파일 하나를 손으로 바꾼 사본에서 첫 차이(날짜·종목·단계)와 종료 코드 4; `status.json`이 매 `live`·`fill`·`reconcile` 뒤 갱신.
- Acceptance: `tests/unit/api/test_reconcile.py::test_match_yes`, `::test_restate_distinct_from_replay`, `::test_first_divergence_reported`, `::test_exit_code_4`, `tests/unit/artifacts/test_status_json.py::test_atomic_and_fields`, `tests/property/test_live.py::test_P_RECON`, `tests/unit/api/test_reconcile.py::test_divergence_id_stable`, `::test_order_day_record`, `tests/unit/api/test_acknowledge.py::test_acknowledge_records_note_and_by`, `::test_acknowledge_not_current_divergence_E35`, `::test_empty_note_rejected`, `tests/unit/api/test_live.py::test_unacknowledged_divergence_refused_E35`, `::test_acknowledged_divergence_proceeds`.

**T5.4 `feat(cli): complete command set and exit codes`** · `M5` `cli` · M · Blocked by: T5.7 · §3.10
- Done means: `uv run nexusbt --help`의 명령 목록이 3.10 표와 같고, `nexusbt new strategy x`가 바로 도는 파일(유동성 문턱 줄이 보임)을 만든다.
- Acceptance: `tests/unit/cli/test_cli.py::test_commands_match_spec`, `::test_exit_codes`, `::test_new_strategy_runs`, `::test_new_strategy_has_visible_liquidity_filter`.

**T5.5 `feat(api): compare, runs table and html index`** · `M5` `api` · M · Blocked by: T3.14 · §3.8, §3.9
- Done means: `nx.compare(a, b)`가 같음/다름(자료·코드 줄·파라미터)과 지표 변화; `nexusbt runs --html`이 `runs/index.html` 생성.
- Acceptance: `tests/unit/api/test_compare.py::test_code_diff_lines`, `::test_data_vs_code_vs_params`, `tests/unit/cli/test_runs.py::test_prune_keeps_counts`.

**T5.8 `feat(compat): pyfolio and alphalens adapters, evaluate signal output`** · `M5` `compat` · S · Blocked by: T3.14, T2.10a · §5.9.8, §5.8 [SC-16]
- Done means: `run.to_pyfolio()`가 세 pandas 객체를, `report.to_alphalens()`가 MultiIndex 표를 돌려주는 예제; `evaluate(..., save_signal=True)`가 `signal.parquet`을 남김; pandas 없는 환경에서 E18.
- Acceptance: `tests/unit/compat/test_adapters.py::test_returns_series_shape`, `::test_pyfolio_triplet_shape`, `::test_alphalens_factor_data_shape`, `::test_no_pandas_E18`, `tests/unit/api/test_evaluate.py::test_signal_parquet_same_schema`.
- Notes:
  - decided (#43 Decisions, 2026-11-19, #251): 스펙 2.5의 화살표 `contracts ← pipeline ← compat`는 `compat.zipline`에만 정한 것이다. 어댑터가 다른 모듈을 필요로 하면 이 티켓은 화살표를 더하기 전에 주인에게 묻는다.

**T5.22 `feat(api): Arrow PyCapsule out (zero-copy result tables)`** · `M5` `api` · S · Blocked by: T5.8 · §5.9.8 *(들이는 쪽 `from_frame`과 G-105는 2026-11-24에 뺐다, #752)*
- Context: 결과 표 객체의 `__arrow_c_stream__`; 엔진은 받는 라이브러리를 import하지 않는다.
- Done means: `pl.from_arrow(run.trades)`·`pd.DataFrame.from_arrow(run.trades)`(pandas ≥ 3.0)가 표를 만들고, Arrow 표준 형 칼럼은 복사 없이 넘어간다(버퍼 주소 비교 시험).
- Acceptance: `tests/unit/api/test_pycapsule.py::test_results_export_stream`, `::test_no_import_of_frame_libs`.

**T5.9 `feat(api): Run.why from run artifacts`** · `M5` `api` · S · Blocked by: T3.19, T3.14 · §5.9.9 [SC-13]
- Done means: 저장된 실행에서 `run.why("KR:T00007", "2019-06-28")`가 다시 계산 없이 5.9.9 모양을 출력(계산 시간 0에 가까움, 표시); `save_signal=False` 실행은 단계 1·2를 안내 문장으로.
- Acceptance: `tests/unit/api/test_why.py::test_matches_explain_strategy_steps_3_to_6`, `::test_no_recompute`, `::test_signal_missing_message`.

**T5.6 `docs(examples): m5 daily paper runbook`** · `M5` `docs` · S · Blocked by: T5.4 · §8.5
- Done means: `docs/runbook-paper.md`의 launchd plist 예(설치하지 않음, `status.json`과 종료 코드 사용)와 수동 명령이 합성 스냅숏 두 개(어제·오늘)로 그대로 돈다.
- Acceptance: `tests/docs/test_examples.py::test_runbook_paper`, `tests/docs/test_lessons.py::test_lesson[daily-watch-vs-good-day]`(8.5 실습 예제, D19, #219).

**T5.G `test(golden): trades table, book cash-flow and frame-hash cases (G-64, G-65, G-105)`** *(R6: G-105 메모리 표 해시를 여기서 먼저 — golden 보호 규칙 8.2)* · `M5` `golden` · S · Blocked by: T0.9 · §5.9.1, §5.7, §8.2 [V31-19]
- Context: 왕복 거래(롱·숏·열린 거래), 장부 입출금 TWR. T5.13·T5.14 전에 병합.
- Done means: `uv run python tests/golden/check/G-64.py`가 거래 표 세 줄과 합계 대조를 출력.
- Acceptance: `test_handcalc_self.py::test_cases_v31_M5_expected_present`.

**T5.10 `feat(api): manual overrides as book events`** · `M5` `api` · M · Blocked by: T5.3 · §3.8, §5.6.5, §5.6.7, §5.9.6
- Context: `nx.override`·`nexusbt book override`, 사건 `override_set/cleared`(트랜잭션 안, 정의 해시 불변), 주문 의도 단계에서 자르기(`no_trade`/`reduce_only`/`close`), `reconcile` 재생 입력, 보고서 "manual overrides {n}".
- Done means: `override(book, id, "no_trade")` 뒤 `live`가 그 종목 주문을 내지 않고 `reconcile`이 `yes`, 지시를 지운 사본은 첫 차이를 그 날짜로 보인다.
- Acceptance: `tests/unit/api/test_override.py::test_no_trade_suppresses`, `::test_reduce_only`, `::test_close_reduces_only`, `::test_definition_hash_unchanged`, `::test_reconcile_replays_overrides`, `::test_override_existing_orders_policy`(대기·탈출 주문 규칙).

**T5.11a `feat(api): manual books - user event schema, CSV import and idempotent transactions`** · `M5` `api` · M · Blocked by: T5.3, T5.7 · §3.8, §5.9.6
- Context: `nx.book("manual:<name>")`, `nx.record_fills`(CSV 칼럼 `event_kind, idempotency_key, order_ref, sheet_id, corrects, instrument_id, side, qty, price, fees, ts, note` 검증), 사건 `user_fill`/`user_reject`/`user_correct`/`user_trade`, 한 트랜잭션, 같은 계좌 회계 코드; 5.9.6 규칙 1(대체된 주문표를 가리키는 CSV는 통째로 거절, E35가 새 주문표를 말함)과 규칙 2(`corrects`, 유도한 `superseded_by`, 정정된 체결은 한 번 셈, 없거나 이미 바뀐 행이면 E35).
- Done means: 주문표 3줄 중 2줄은 다른 가격으로(한 줄은 두 번 나눠) 체결, 1줄은 거절, 체결 하나를 정정, 추천에 없던 1건을 넣은 CSV를 두 번 넣어도 사건이 한 번만 생기고, 같은 열쇠에 다른 수량을 넣으면 E35.
- Acceptance: `tests/unit/api/test_manual_book.py::test_record_fills_idempotent`, `::test_manual_partial_fill_and_rejection`, `::test_user_correct_appends`, `::test_duplicate_fill_key_conflict_rejected_E35`, `::test_user_trade_outside_recommendation`, `::test_csv_column_validation`, `::test_superseded_sheet_fills_refused_E35`, `::test_correction_chain_superseded_by`, `::test_correct_unknown_or_replaced_E35`, `tests/property/test_live.py::test_P_LIVE_superseded_sheet_refused`, `::test_P_LIVE_corrected_fill_counts_once`.

**T5.11b `feat(api): manual-book reconcile report`** · `M5` `api` · S · Blocked by: T5.11a, T5.10 · §5.9.7
- Context: `manual:` 장부의 `reconcile` 보고(모형 목표 vs 실제 보유, 모형 체결가 vs 실제 체결가 bp, 재량 거래 목록, 지시 재생), 종료 코드 4 쓰지 않음; 5.9.6 규칙 2(그날의 정정을 개수와 목록으로)와 `manual:` 장부의 5.9.7 (5) 주문일 기록.
- Done means: T5.11a의 CSV로 `reconcile`이 세 칸과 정정 하나를 출력; `reconcile --day`가 그 세션의 주문일 기록을 출력.
- Acceptance: `tests/unit/api/test_manual_book.py::test_reconcile_manual_report`, `::test_manual_reconcile_exit_code_0`, `::test_reconcile_lists_day_corrections`, `::test_manual_order_day_record`.

**T5.12 `feat(api): live pre-trade sanity checks (E36)`** · `M5` `api` · M · Blocked by: T5.2 · §5.9.6, §3.9 Orders, §3.11 `[live]`
- Context: 점검 다섯(가격 튐·스파이크, 주문당 최대 금액, 보유 초과 매도·숏 초과 환매, 사건 계수와 맞지 않는 가치 변화, 유동성 문턱 없음), 주문표 `check` 칸, `status.json` `warnings`, E36, 막지 않음; 주문표 전에 5.9.6 규칙 4의 막는 최신 자료 점검(전략이 읽는 데이터셋마다, 못 미치는 데이터셋 모두를 담은 E19, 종료 코드 3).
- Done means: 종가를 1/100로 깎은 합성 스냅숏에서 `nexusbt live`가 주문을 내되 해당 줄 `check = price_jump`와 E36 한 줄을 출력; 8.4의 최신 자료 사례가 그 E19를 내고 주문표는 없음.
- Acceptance: `tests/unit/api/test_live_checks.py::test_price_jump_flagged`, `::test_order_value_cap`, `::test_oversell_flagged`, `::test_event_value_mismatch`, `::test_liquidity_floor`, `::test_not_blocking_exit_code_0`, `::test_newest_data_per_dataset_E19`, `::test_newest_data_names_every_missing_dataset`, `::test_newest_data_event_dataset_E19_names_its_items`, `::test_newest_data_event_dataset_current_without_an_event`, `::test_newest_data_without_processed_through_E30`.

**T5.13 `feat(accounting): external cash flows and time-weighted returns in books`** · `M5` `accounting` · M · Blocked by: T5.1, T5.G · §5.6.9, §5.7, §5.9.6, INV-06 [V31-19]
- Context: `nx.cash_flow`·`nexusbt book flow`, 사건 `external_flow`(세션 시작), 다리 `external_flows` 행, TWR 수익, 현금 넘는 출금 E16, `reconcile` 재생.
- Done means: G-65의 `r_1` 0.6667%와 다리 행이 출력되고, 입금만 있는 장부의 CAGR이 0·`account_growth` 50%(G-65 (b), v3.2).
- Acceptance: `tests/golden/test_books.py::test_G65_twr`, `tests/unit/accounting/test_flows.py::test_withdrawal_over_cash_E16`, `::test_flow_only_book_has_zero_cagr`, `::test_flow_boundary_replay_is_idempotent`, `tests/property/test_execution_invariants.py::test_P_BRIDGE_with_flows`.

**T5.14 `feat(artifacts): round-trip trades table derived from events`** · `M5` `artifacts` · M · Blocked by: T3.14, T4.15c, T5.G · §5.9.1, §3.9
- Context: `trades.parquet`(평균가 기준; 0 → 비0에서 열고 0에서 닫음, 부분 매도는 다리, 뒤집기는 닫는 몫 + 여는 몫, 숏 거래, 열린 거래 `status = open`), 청산 이유, MAE·MFE(진입·청산 봉 극값을 뺀 진입 뒤 H/L, "daily-bar approximation"), `derive_tables`에 포함, HTML "trades" 칸.
- Done means: G-64 세 거래가 그대로 나오고 HTML에 청산 이유별 건수·승률·평균 보유 기간.
- Acceptance: `tests/golden/test_trades.py::test_G64`, `tests/property/test_execution_invariants.py::test_P_TRADES`, `::test_P_DERIVED_includes_trades`, `tests/unit/artifacts/test_trades.py::test_flip_splits_legs`, `::test_intraday_entry_mae_excludes_entry_bar`.

**T5.15 `feat(api): screen x-ray over the whole universe`** · `M5` `api` · M · Blocked by: T3.19, T2.20, T2.21, T2.22, T5.1 · §3.8, §3.9 Screen, §5.9.9
- Context: `screen(show=…, near=)`, `Screen.xray()`(잎 Filter 참/거짓/모름, 신호 노드 값·백분위, 상태 칸), CLI `--show --html`, 새 계산 없이 노드 값 재사용.
- Done means: `uv run nexusbt screen examples/strategies/value_mom.py --show held+near --html`이 보유·매수·완충·매도·아깝게 빠진 종목 상태와 규칙별 참/거짓이 든 HTML을 쓴다.
- Acceptance: `tests/unit/api/test_xray.py::test_statuses`, `::test_leaf_filters_three_valued`, `::test_no_recompute`, `::test_matches_explain_rows`, `::test_xray_without_book_does_not_invent_holdings`.

**T5.16 `feat(portfolio): strategy state record in paper books and screens`** · `M5` `portfolio` · S · Blocked by: T5.1, T5.16a · §5.5.3, §5.9.6
- Context: 전략 상태 기록의 장부 부분(기록 타입·직렬화·체크포인트는 T5.16a; 결정 2026-11-04, #152): 커밋마다 기록과 기준점을 장부 매니페스트(5.9.6)에 쓰기, 장부를 다시 열 때 복원, `screen`이 장부에서 그것을 이어받기. 재귀 기능은 켜지 않는다(T7.1).
- Done means: 장부 매니페스트에 기준점과 상태 기록이 보이고, 커밋 뒤 장부를 다시 열면 멈추지 않았을 때와 같은 다음 목표가 나온다.
- Acceptance: `tests/unit/portfolio/test_target_state.py::test_book_manifest_records_state`, `::test_book_reopen_restores_state`.

**T5.17 `feat(api): screen account modes for account-reading risk rules`** · `M5` `api` · M · Blocked by: T3.30, T5.1, T5.4 · §3.8 screen, §3.10
- Context: `screen(account="auto"|"none"|"book"|"backtest")`, CLI `--ledger BOOK`·`--as-backtest`, not evaluated 줄·E42·skips, 장부 상태 판·스냅숏 해시를 매니페스트에, `--as-backtest` 걸린 시간.
- Done means: 같은 전략을 장부 없이·`--ledger paper:demo`·`--as-backtest`로 screen한 세 결과가 같은 정규 목표를 출력하고, `final_weight` 칸은 전략에 계좌를 읽는 위험 규칙이 있을 때만 다를 수 있다.
- Acceptance: `tests/golden/test_risk.py::test_G87_screen_part`, `tests/unit/api/test_screen_account.py::test_not_evaluated_line_and_E42`, `::test_ledger_reads_book_state`, `::test_as_backtest_equals_backtest_account`.

**T5.18 `feat(cli): strategy templates, demo snapshot and the 30-minute path`** · `M5` `cli` · M · Blocked by: T5.18a, T5.4, T3.34, T3.33, T5.17 · §3.10, §8.5 *(전략 작성 시험, 사용자 결정 2026-11-03; T3.35는 Blocked by에서 빠지고 그 사건 템플릿 둘은 2026-11-24에 여기로 왔다, #752)*
- Context: (`init --demo`와 데모 스냅숏은 T5.18a의 것) `nexusbt new strategy NAME --template T`·`--list`, 템플릿 22개(3.10) 가운데 18개(`event-driven-earnings`·`macro-regime`은 stage (2)가 `nx.Item`을 지을 때 켜지고(#752) 그때까지는 아직 못 쓰는 것으로 표시; 나머지 4개는 그 기능 티켓에서: 검증·ML 둘 T6.27, zipline T5.19, `buffer-hold` T7.1 — `--list`는 아직 못 쓰는 것을 "(available after T…)"로 표시), 템플릿마다 출력 대조 시험, `test_first_30_minutes.py`(첫 줄 `uv init quant && cd quant && uv add nexusbt`, CI는 `--find-links dist/`).
- Done means: 깨끗한 환경에서 다섯 명령(8.5, 첫 줄 `uv init quant && cd quant && uv add nexusbt`)이 차례로 돌고, 처음 쓰는 사람 한 명(사용자가 고름)이 30분 안에 첫 백테스트와 첫 스크린을 마친 기록이 PR에 있다. **전략 작성 시험**(R3, 사용자 결정 2026-11-03, M5 끝 조건): 소유자가 템플릿에서 전략 셋을 혼자 쓴다 — (a) 월간 KR 가치 상위 50, 롱온리, 잠정 비용(`monthly-topn`); (b) KR과 US의 12-1 모멘텀 롱숏, 공매도 켬, 총노출 상한(`momentum-12-1`, `long-short`); (c) 실적 발표 뒤 진입, 다섯 세션 시간 손절(`event-driven-earnings`, `nx.Item.<name>.age()`). 소유자는 M5 전에 셋 가운데 어느 것이든 바꿀 수 있다. 전략마다 세 단계 — 템플릿에서 쓰기, 규칙 하나 바꾸기, 오류 하나 읽기 — 가 있고 단계마다 기록 한 줄: 전략, 단계, 분, 받은 도움(없음, 문서, 사람, 그리고 무엇), 결과(마침, 또는 못 마침과 그 이유). 그 줄들은 M5 끝 증거에 들어가고, 전략 셋은 `examples/trial/` 파일로 남기고, `tests/docs/test_examples.py`(8.5)가 하나하나 합성 `small` 스냅숏에서 돌린다. 각 줄에는 안내서 `docs/guide/choose-by-question.md`(3.10)를 썼는지, 소유자가 출력이 보여 주는 것과 보여 주지 못하는 것을 말할 수 있었는지도 적는다(8.5 사용 시나리오, D19, #219).
- Acceptance: `tests/docs/test_templates.py::test_template_runs`, `tests/docs/test_first_30_minutes.py::test_five_commands`, `tests/unit/cli/test_new.py::test_list_templates`, `tests/docs/test_examples.py::test_trial_strategies_run`, `tests/docs/test_scenarios.py::test_scenario[6]`(D19, #219).

**T5.19 `docs: zipline to NexusBT mapping page and zipline-port template`** · `M5` `docs` · S · Blocked by: T5.18 · §8.5
- Context: `docs/migrate-from-zipline.md`(영어 + 한국어): bundle·`initialize`·`handle_data`·`context`·`schedule_function`·`order_target_percent`·`attach_pipeline`·`pipeline_output`·`run_algorithm`·`CustomFactor`가 각각 무엇이 되고 무엇이 달라지나(해부 G 3부 표), 코드 조각 모두 `<!-- test -->`·`<!-- output -->`, `zipline-port` 템플릿.
- Done means: 문서 페이지가 렌더되고 표의 모든 NexusBT 칸 코드가 시험에서 돈다.
- Acceptance: `tests/docs/test_examples.py::test_migrate_from_zipline`, `tests/docs/test_templates.py::test_template_runs[zipline-port]`.
- Notes:
  - decided (#43 Decisions, 2026-11-19, #587): 안내는 zipline의 `outputs`를 짝이 없는 것으로 적는다.
  - carried (#43 Decisions, 2026-11-19, #251): 안내는 심(shim)이 `window_safe`를 무시한다는 것(E17의 차수 규칙만 거절하므로, 그 표시 없는 비율 `CustomFactor`가 여기서는 지나가고 zipline에서는 거절된다)과, `outputs`, `params`, `domain`이나 기본값이 아닌 `dtype`, `missing_value`, `ndim`을 정한 클래스는 정의한 곳에서 멈춘다는 것을 말한다.
  - decided (#43 Decisions, 2026-11-19, #251): 심은 사용자가 필요로 할 때까지 `compute`에 실제 `today`와 `assets`를 넘기지 않으므로, 호환 층은 얇게 남는다(ADR 0001).
  - carried (#43 Decisions, 2026-11-19, #587): 스펙 3.3이나 12장은 사용자 함수가 종목마다 값 하나를 주고 zipline의 `outputs`는 v1에 없다고 말해, 그것이 선택으로 읽히게 한다. 스펙 변경으로 주인에게 묻는다.

**T5.20 `feat(api): compare strategy variants in one table`** · `M5` `api` · S · Blocked by: T5.5, T3.34 · §3.8 compare
- Context: `nx.compare(Strategy…)`가 각각 backtest(Pipeline 재사용) 후 변형 표(바뀐 칸 이름, 지표, waterfall 요약, DSR(집단)), CLI `nexusbt compare`.
- Done means: `nx.compare(base, base.replace(sizing=nx.size.erc()), base.replace(risk=[nx.risk.drawdown_brake()]))`가 세 줄 표를 출력하고 후보 셋이 기록된다.
- Acceptance: `tests/unit/api/test_compare.py::test_variant_table_columns`, `::test_variants_counted_as_candidates`, `::test_pipeline_values_reused`.

**T5.21 `feat(cli): commented two-tier nexusbt.toml template, config check and config show`** · `M5` `cli` · S · Blocked by: T1.2, T0.4b, T0.5a · §3.10, §3.11 [사용자 요청 2026-10-28]
- Context: `nexusbt init`이 1부 "꼭 확인할 것"·2부 "고급" 주석 틀을 씀(영어 정본 + `--lang ko`), `nexusbt config check`(형·범위·모순을 `layer config` 서식으로), `nexusbt config show [--all]`(해석된 값 + 출처 default/file/CLI/code, `load_config`와 같은 해석기), 보고서 머리 "settings (tier 1)" 블록.
- Done means: `uv run nexusbt init --lang ko && uv run nexusbt config check`가 "config ok"를 출력하고, `[account] type = "cash"`에 `debit_rate_bps = 300`을 넣으면 `config check`가 `layer  config` 줄과 fix 줄을 내며 종료 코드 1; `config show`가 `capital`의 출처를 `file`로, 전략 코드가 덮은 `start`를 `code`로 보인다.
- Acceptance: `tests/docs/test_config_template.py::test_template_keys_match_3_11`, `::test_en_ko_same_keys_and_values`, `::test_example_file_keys_exist`, `tests/unit/cli/test_config_check.py::test_margin_keys_on_cash_account_E16`, `::test_contradictions_listed_with_layer_config`, `tests/unit/cli/test_config_show.py::test_source_default_file_cli_code`, `::test_show_matches_manifest_config`, `tests/golden/test_report.py::test_header_lists_tier1_values`.

#### M6 — 성능·연구 도구·출시 관문

**T6.1** → v3에서 **T1.24**(M1)로 옮겼다(이른 측정). M6의 측정은 T1.24 장치를 쓴다.

**T6.2 `perf(compute): numba rolling kernels bit-equal to reference`** · `M6` `compute` · M · Blocked by: T1.24, T4.7 · §5.3.3, §5.3.10, ADR-0016, ADR-0019
- Done means: P3 측정이 전후로 기록된 PR 설명; 빠른 커널 = 참조(비트).
- Acceptance: `tests/property/test_kernels.py::test_P_KERNEL_rolling_bit_equal`, `::test_transcendental_same_function_both_paths`, `::test_py_func_covered`, `::test_no_fastmath_no_parallel`, `::test_kernel_swap_bit_equal`(이음새 안에서만 바꿔 끼움).
- Notes:
  - owner decides at the cut (#43 Decisions, 2026-11-20, #632): 내장 커널에서 제곱이나 곱이 0으로 밑넘침하는 칸(`[1e-200, −1e-200]`의 표준편차는 0)이 그 작은 수인지, 0인지, NaN인지.
  - owner decides at the cut (#43 Decisions, 2026-11-20, #632): `MaxDrawdown`을 양의 누적 최고점에서만 정의할지(`[-1.0, -2.0]`에서는 `-0.0`을 주어, 떨어짐을 낙폭 없음으로 읽는다).
  - owner decides at the cut (#725 Decisions 258, 2026-11-24): 스펙 0장의 "checked bit for bit against the reference implementation"과 조정 지름길의 "relative 1e-12"(INV-11, 5.3.3)가 어긋난다. 첫 측정 뒤 어느 약속이 서는지 주인이 정한다.

**T6.3 `perf(compute): numba cross-sectional kernels`** · `M6` `compute` · M · Blocked by: T6.2 · §5.4, §5.3.10
- Done means: P2·P3 측정 전후.
- Acceptance: `tests/property/test_kernels.py::test_P_KERNEL_crosssection_bit_equal`.

**T6.12 `feat(data): L0 raw block cache with memory mapping`** · `M6` `data` · M · Blocked by: T1.24, T1.4 · §5.3.9 L0, §7 P7 [SC-15]
- Done means: 같은 screen 두 번째에서 블록 읽기 시간이 줄어든 것(L0 hit)을 출력; L0 폴더를 지워도 결과 비트 동일; `nexusbt doctor`가 L0 크기를 보임.
- Acceptance: `tests/property/test_cache.py::test_P_CACHE_L0`, `::test_P_CACHE_INCR`(마지막 연도만 바뀐 새 스냅숏에서 과거 파티션 적중, 옛 정정은 미적중; 2026-11-04: 8.3의 축 사례와 L1 사례, 내일 세션 추가 뒤 L1 적중률 > 0), `tests/unit/data/test_l0.py::test_readonly_mmap`, `::test_key_changes_with_partition_file_sha256`, `::test_intermediate_action_revision_invalidates`, `::test_terms_availability_only_change_invalidates`, `::test_axis_row_changes_miss_only_the_table_years`, `::test_watermark_change_keeps_l0_hits`, `::test_bad_advisory_value_hash_never_reuses_wrong_block`, `::test_l0_shared_entry_survives_old_snapshot_removal`, `::test_l0_identity_mismatch_rehashes`.
- Notes:
  - owner decides at the cut (#725 Decisions 151, 2026-11-23): L0 캐시 열쇠를 파티션의 파일 sha256에서 파티션 값 해시로 옮길지(5.3.9, ADR 0025).
  - builder's choice (#43 Decisions, 2026-11-19, #233, #450 and #451; 추천: T1.1b의 시험을 L0 절반으로 넓힘, 그러면 시험 하나가 두 절반을 지니기 때문): `test_inplace_edit_invalidates_stamp_and_l0`는 표식 절반만 확인한다. 이 티켓이 L0 절반으로 넓히거나 `test_l0_identity_mismatch_rehashes`가 그 절반이라고 말한다.

**T6.4 `feat(compute): semantic term cache (L1)`** · `M6` `compute` · M · Blocked by: T6.2 · §5.3.9
- Done means: 같은 evaluate 두 번째가 P3 캐시 목표 안(시간 출력); 캐시 폴더를 지워도 결과 동일; `availability`만 바꾼 스냅숏·`THRESHOLD`만 바꾼 함수는 캐시를 쓰지 않는다.
- Acceptance: `tests/property/test_cache.py::test_P_CACHE`, `::test_key_changes_with_resolution_metadata`, `::test_key_changes_with_policy`(2026-11-04: 옛 이름 `::test_key_changes_with_policy_and_calendar`; L1 열쇠에 달력 판이 없음), `::test_l1_key_has_no_axis_file_hash`(2026-11-04: 입력 행 집합 밖의 새 `calendar_sessions` 행은 열쇠를 바꾸지 않고, L0가 해시하는 필드만 읽는 노드에는 새 `instruments` 행도 그렇다; `Meta.category`를 읽는 노드는 열쇠가 바뀜), `::test_l1_key_first_session_ord_for_absolute_schedule`(2026-11-04: 절대 `session_ord`를 읽는 노드는 앞 연도에 세션이 생기면 열쇠가 바뀜), `::test_captured_scalar_changes_key`, `::test_nonconst_global_disables_l1`, `::test_external_input_hash_in_key`, `::test_atomic_write`, `::test_budget_counts_L0_and_L1`, `::test_l1_key_from_input_l0_keys`, `::test_january_nested_window_depends_on_prior_year`, `::test_partial_l1_coverage_cannot_satisfy_missing_rows`, `::test_validity_mask_cache_roundtrip`, `::test_l1_learning_context_keys_learned_node_and_downstream`(2026-11-04: `fit_id`·seed·사전학습 식별이 학습 노드와 그 아래 노드의 열쇠를 바꾸고, 학습된 입력이 없는 노드의 열쇠는 바꾸지 않음).
- Notes:
  - builder's choice (#43 Decisions, 2026-11-04, #190 and #184; 추천: 축 표처럼 행 규칙을 둠, 그러지 않으면 그런 노드의 L1 항목이 날마다 모두 빗나가기 때문): 해 파티션이 없는 데이터셋을 다시 쓰는 일별 스냅숏은 그것을 읽는 노드의 L1 항목을 날마다 모두 빗나가게 한다. 이 티켓이 그것들에 행 규칙을 주거나, P2b의 따뜻한 `screen`이 그런 노드는 다시 계산된다고 말한다(T6.11도).

**T6.5 `feat(compute): process-tree memory budget, bounded workers and parallel scenarios`** · `M6` `compute` · M · Blocked by: T6.4 · §5.3.8
- Done means: `memory_budget_gb=1`, `workers=2`에서 P5-small 프로세스 트리 RSS 합이 1 GB 근처로 출력되고 결과 동일; 시나리오 결과 순서·값 동일.
- Acceptance: `tests/property/test_pipeline_invariants.py::test_P_CHUNK_budget`, `tests/perf/test_smoke.py::test_rss_bounded`, `tests/unit/compute/test_workers.py::test_parallel_scenarios_identical`.
- Notes:
  - carried (#43 Decisions, 2026-11-17, #240 and #497): 5.3.8의 E16 문장은 `compute._chunks.spans`가 하는 일(세션 행 하나가 그 되돌아보는 행과 함께 들어가지 않을 때 낸다)과 다르다. 같은 고침에서 `memory_budget_gb`가 코드가 읽듯 10^9 바이트인지 2^30인지, 추정의 `+ 2`가 무엇을 덮는지 말한다. 스펙 변경으로 주인에게 묻는다.

**T6.6 `perf(execution): numba session step over the columnar state (conditional)`** · `M6` `execution` · M · Blocked by: T1.24, T3.18, T4.7 · §5.6, §7 *(조건부 — M3a·M4 측정에서 P5 시간의 대부분이 세션 단계에 있고 주인이 P5가 쓰기에 너무 느리다고 판단할 때만(2026-11-24부터 P5 관문은 없음, ADR 0054); 아니면 이 티켓은 "측정으로 불필요"로 닫는다)*
- Done means: P5 측정 전후, 모든 golden 그대로(열 배열 상태 위의 `@njit`, 자료 구조 바꾸지 않음).
- Acceptance: `tests/property/test_kernels.py::test_fast_step_equals_reference`.

**T6.7 `feat(api): sweep with shared graph and candidate matrix`** · `M6` `api` · M · Blocked by: T6.4 · §3.8 sweep, §6.3
- Done means: `uv run nexusbt sweep examples/strategies/value_mom.py`가 후보 표를 출력하고 `candidates.parquet`가 생김.
- Acceptance: `tests/unit/api/test_sweep.py::test_shared_nodes_computed_once`, `::test_candidates_registered`.

**T6.14 `feat(api): capacity scenario`** · `M6` `api` · S · Blocked by: T6.7, T6.5 · §3.8, §5.7 [SC-06, OQ-4]
- Done means: `backtest(..., scenarios=[..., "capacity"])`가 ×10·×100 CAGR, 상한 걸린 비율, 평균 참여율과 "cap binds at ≈ K" 줄을 출력; `sweep` 최종 후보 보고에 자동으로 켜짐; 기본 프로필 `provisional`에서는 거래 단위당 비용(bp)이 주문 크기에 따라 늘지 않고 한계는 거래량 상한으로만 드러난다고 결과가 밝힘(5.7; #764, 결정 2026-11-25).
- Acceptance: `tests/unit/api/test_capacity.py::test_capacity_rows`, `::test_binds_at_definition`, `::test_sweep_final_candidates_have_capacity`.
- Notes:
  - owner decides at the cut (#43 Decisions, outside review of 2026-11-03): 수용량 시나리오가 처분에 걸리는 날수를 줄지.

**T6.8 `feat(research): PSR, DSR and PBO via CSCV over cohorts`** · `M6` `research` · M · Blocked by: T6.7, T2.9 · §5.7, §6.3
- Done means: sweep 출력에 PBO 줄, backtest에 DSR 줄(N, V[SR] 출처 = 집단, `cohort_sha256`); 입력 부족 시 "n/a (reason)"(6.3 목록). (2026-11-04, #197) hygiene 절의 `ρ1…ρ10` 띠, 그 검정의 p < 0.05이면 PSR 줄의 5.7 표시 "IID-based: dependence visible (Ljung–Box lags 1–10, p < 0.05; may also reflect changing volatility)", N > 1이면 SR*_N에 대한 MinTRL, reality-check 요청에는 "not supported in v1".
- Acceptance: `tests/property/test_stats.py::test_P_STAT_psr_dsr_known`, `::test_pbo_hand_matrix`, `::test_invalid_population_na`, `::test_dsr_uses_frozen_cohort`, `::test_pbo_zero_variance_rule`, `::test_psr_raw_kurtosis_convention`(G-60), `::test_pbo_common_dates_with_unequal_lookbacks`, `::test_purge_keeps_max_end_available`, `::test_iid_label_when_dependence_visible`(ρ1 = 0인 AR(2) 시계열에 표시), `::test_mintrl_selection_adjusted_reference`, `::test_reality_check_not_supported`(2026-11-04, #197), `tests/docs/test_tool_cards.py::test_card[psr]`, `::test_card[dsr]`, `::test_card[pbo]`(D19, #219).

**T6.9 `feat(research): truncation probes with prioritized dates and coverage report`** · `M6` `research` · M · Blocked by: T6.4 · §6.5 [SC-05]
- Done means: 스냅숏 전체 기간 배열을 클로저로 받는 함수에 `nx.check(f, probes=4)`가 E1과 한계 문단, "nodes compared x/y", "finite cells a/b", 날짜 이유를 출력; 창 안에서만 `np.roll`하는 함수는 E1이 없다.
- Acceptance: `tests/unit/test_leaks.py::test_probe_catches_injected_future_reader`, `::test_bounded_roll_not_flagged`, `::test_probe_clean_function_passes`, `::test_probe_cached_per_graph`, `::test_probe_date_priority`, `::test_probe_coverage_report`.

**T6.13 `feat(research): start-date probe in nx.check`** · `M6` `research` · S · Blocked by: T6.9 · §6.5 시작일 탐침 [SC-04]
- Done means: 전역 누적값을 쓰는 사용자 함수에 `nx.check(f, start_probe=True)`가 E32와 가장 아래 노드를 출력; 깨끗한 함수는 통과.
- Acceptance: `tests/unit/test_leaks.py::test_start_probe_catches_global_state_E32`, `::test_start_probe_clean_passes`, `::test_start_probe_skips_targets_with_recursion`.

**T6.10 `feat(api): progress display for long work`** · `M6` `api` · S · Blocked by: T6.5 · R-41
- Done means: 2초 넘는 backtest에서 표준 오류에 단계·날짜·남은 시간 줄(탐침·시나리오·용량은 단계 이름으로 따로).
- Acceptance: `tests/unit/api/test_progress.py::test_progress_after_2s`.

**T6.11 `perf: compute-host gate run and evidence`** · `M6` `bench` · S · Blocked by: T6.3, T6.5, T6.8, T6.12, T6.26 (T6.6을 했다면 그것도) · §7 — **사용자가 계산 기계에서 실행**
- Done means: `bench/results/<date>-<sha>-<machine>.json`(요약만; `<machine>`은 `8gb`처럼 측정 기계의 종류를 나타내는 짧은 이름이고 호스트 이름이 아님, 2.7; 2026-11-24까지는 `-m4`)이 커밋되고, 모든 워크로드의 p50/p95·USS를 앞 측정 옆에 둔 표와 나빠진 것마다의 알림이 PR에 있으며(7장 "숫자의 뜻"), P11 (a)(b)(c) 결과를 첫 숫자와 견주어 보고한다. 작업 P2b(어제 캐시 + 오늘 스냅숏 screen)의 시간·적중률과 열 묶음 켬/끔 두 값을 함께. P2b 적중률 > 0(워터마크가 열쇠에 없음, v3.2). 알림이 난 항목은 병목 프로파일을 받고 그 회귀를 고친다(Rust로 다시 쓰는 것은 ADR 0054의 발동 조건으로만). (#270) `ml-factor` 예제 실행이 `fits` 묶음을 보고하고, PR이 `hash_seconds` 합이 `fit_seconds` 합의 10%를 넘는지 말한다(5.3.11 비용의 대체 발동 조건).
- Acceptance: `tests/unit/bench/test_results_present.py::test_measurement_file_for_release`.
- Notes:
  - owner decides at the cut (#752 Decisions, 2026-11-25): 알림의 허용치와 측정을 무엇과 비교할지는 첫 측정 때 한 기계에서 되풀이한 실행의 퍼짐으로 정하고(처음 제안은 20%), 앞 측정과 함께 7장의 기준 숫자와도 비교할지 정한다.

**T6.15 `chore(release): clean-install gate, independent producer acceptance, changelog and contributor docs`** · `M6` `release` · M · Blocked by: T2.17, T4.11, T5.4 · §2.3, §9.1 `engine / release`, R-70
- Context: `tests/repo/release_check.py`(작업 폴더 밖 깨끗한 가상환경에 두 wheel만 설치 → 영어 빠른 시작·공개 예제 실행), 독립 생산자 시험 패키지 `tds/conformance/producers/csv-minimal`(T1.22로 만든 것)와 손으로 쓴 두 번째 생산자 패키지가 `full` 통과 + 소비 시험, `CHANGELOG.md`(엔진·TDS 따로), `CONTRIBUTING.md`·`SECURITY.md` 본문, 호환 정책 문단(TDS 10장·엔진 판 규칙), "KR/US 검증" 주장 조건 문장(실제 자료 증거 요약이 있을 때만). 출시 증거 `release_evidence.json`에 적용 규칙 목록(출처·경계·`verified`)·`verified = false` 행 수·`off_grid_bar` 분자/분모, 독립 생산자 예제 id는 TDS K1 권장 형식 `XNAS:AAPL_19801212`.
- Done means: `uv run python -m tests.repo.release_check`가 "clean install ok · quickstart ok · producers 2/2 full pass"를 출력.
- Acceptance: `tests/repo/test_release.py::test_clean_wheel_runs_example`, `::test_ml_extra_runs_ml_example`, `::test_independent_producer_package_passes`, `::test_changelogs_present`, `::test_release_market_rules_have_verified_coverage`, `::test_k1_example_ids_valid`.

**T6.16 `ci(release): trusted-publishing workflow (dry run until the user decides)`** · `M6` `infra` · S · Blocked by: T6.15 · §2.1 — **사용자가 푸시**(워크플로 권한)
- Context: 태그 `v*`·`tds-v*`에서 wheel·sdist를 만들고 TestPyPI로 dry run; 실제 PyPI 게시는 12장 OI-44 결정 뒤 사용자가 켬.
- Done means: 태그 dry run 로그에 두 배포물 업로드 시뮬레이션이 보인다.
- Acceptance: 워크플로 로그(수동 확인 체크리스트).

**T6.17 `test(bridge): capability errors for reserved extension points`** · `M6` `bridge` · S · Blocked by: T0.4 · §11
- Done means: `nx.backtest(..., engine="nautilus")`, `Capabilities` 비교로 모자란 기능(장중 순서 등)을 요구하는 전략이 실행 전에 E18.
- Acceptance: `tests/unit/bridge/test_capabilities.py::test_reserved_backends_E18`, `::test_capability_mismatch_E18`, `::test_backend_protocol_emits_fill_events_only`.

**T6.18 `feat(api): rebalance-date luck offsets and rolling-window table`** · `M6` `api` · M · Blocked by: T6.4, T4.12 · §3.8, §5.7, §6.2, §3.11 `[report]`
- Context: `backtest(offsets=k)`(같은 Pipeline 값, 목표·상태 기계만 다시), `offsets.parquet`, 첫 화면 줄, 시도 수·집단 밖, HTML "rolling"(1년·3년 창 초과 수익 분위).
- Done means: `uv run nexusbt backtest examples/strategies/mom_kr.py --offsets 5`가 "rebalance-date luck 5 offsets · CAGR min/median/max"와 걸린 시간을 출력하고 study 후보 수는 그대로.
- Acceptance: `tests/unit/api/test_offsets.py::test_reuses_pipeline_values`, `::test_not_counted_as_candidates`, `::test_schedule_offsets_per_kind`, `tests/unit/research/test_rolling.py::test_rolling_excess_quantiles`, `tests/docs/test_tool_cards.py::test_card[offsets]`(D19, #219).

**T6.Gv `test(golden): validation, ML window, triple-barrier and pretrained-cutoff cases (G-88..G-93, G-106, G-116)`** *(R6: G-106 사전학습 마감을 여기서 먼저)* *(2026-11-04: G-116, 엄격한 IS 점수와 근사 IS 점수, #215)* · `M6` `golden` · M · Blocked by: T0.9 · §5.3.11, §5.8, §6.3a, §8.2
- Context: 분할 셈, 정화·엠바고(늦은 공개 폐지 정답), 계좌 이어 감/새 자본, ML 학습 창, 삼중 장벽 네 경우의 손계산 사례. 구현 PR 전에 병합.
- Done means: `uv run python tests/golden/check/G-89.py`가 폴드별 정화·엠바고 표본을 출력.
- Acceptance: `tests/golden/test_handcalc_self.py::test_case_G88_to_G93_expected_present`, `::test_case_G116_expected_present`(#215).
- Notes:
  - owner decides at the cut (#314 Findings, 2026-11-06; #314 Decision, 2026-11-10): PSR과 MinTRL의 AR(1) 닫힌꼴 보정을, 이 티켓이 사례로 손계산할 수 있으면 진단 행 하나로 둘지, 12.1의 행으로 남길지.

**T6.19 `feat(research): split value objects with label-availability purge and AFML embargo`** · `M6` `research` · M · Blocked by: T2.9, T6.Gv · §6.3a, §5.8
- Context: `nx.splits.holdout`·`walk_forward`·`cpcv`·`cscv`, `Split`(folds, paths, `split_hash`, `plot()`, `summary()`), 정화(정답 구간 = 공개 시각까지)·엠바고, `n_purged`·`n_embargoed`, 길이 문자열 해석.
- Done means: `nx.splits.cpcv(6, 2).summary()`가 분할 15·경로 5와 묶음 표를 출력.
- Acceptance: `tests/golden/test_validation.py::test_G88`, `::test_G89`, `tests/property/test_validation.py::test_P_SPLIT_DET`, `tests/unit/research/test_splits.py::test_wf_step_less_than_test_E16`, `::test_embargo_differs_from_embargo_sessions`.

**T6.20 `feat(api): backtest(method="walk_forward") with a chained account, fold selection and linear side by side`** · `M6` `api` · M · Blocked by: T6.19, T6.7, T3.13a · §3.8, §6.3a, §6.2
- Context: `backtest(method=…, grid=, select=)`, CLI `--method`·`--method-opt`·`--grid`, 폴드 훈련 IS 선택(grid 점마다 D 전체 선형 실행 하나의 일간 수익을 훈련 보유 기간으로 잘라 정화·엠바고, `selection.parquet` 표본 수), 이어 감이면 `step == test`(E16), 비교 기준 `backtest(start=t_1)`(P-WF-STITCH), 선형 줄에 기간 표시, 계좌 하나 이어 감(보유·대기 주문·탈출·`risk_state`), 진단 `account="per_fold"`, 함께 도는 선형 실행, `Run.validation`·`validation/` 폴더, 셈(폴드 진단·grid 점 후보).
- Done means: `uv run nexusbt backtest examples/strategies/value_mom.py --method walk_forward --grid n=10,20,30`이 `primary` 줄과 `reference` 줄(3.9, #216), 폴드 표(고른 n, IS/OOS Sharpe)를 출력하고 후보 수가 grid 점 수만큼 는다.
- Acceptance: `tests/golden/test_validation.py::test_G90`, `tests/property/test_validation.py::test_P_WF_STITCH`, `tests/unit/api/test_method.py::test_folds_not_counted`, `::test_is_returns_sliced_from_full_run`, `::test_step_not_equal_test_E16`, `::test_linear_run_alongside`, `::test_scenarios_only_on_linear`, `tests/docs/test_tool_cards.py::test_card[walk-forward]`(D19, #219), `tests/unit/api/test_method.py::test_primary_and_reference_in_run_and_metrics_json`(기존 칸의 뜻이 바뀌지 않음; 6.3a, #216).

**T6.21 `feat(research): CPCV paths with fresh capital per path, CSCV and sweep as a shorthand`** · `M6` `research` · M · Blocked by: T6.20, T6.8 · §6.3a, §6.3
- Context: 경로마다 `TargetFrame` 이어 붙이기·새 자본 상태 기계, 경로 분포, CPCV PBO(IS 1등의 OOS 순위), `method="cscv"` = 6.3 절차, `sweep` = `backtest(method="cscv", grid=)` 줄임(`SweepResult` 호환), 고를 것 없는 CPCV E40, `[validate] max_fits` 사전 알림. (2026-11-04, #215) `splits.cpcv(is_scores=)`와 `ValidationResult.is_scores`: 학습 노드가 없는 `grid`의 조각(`slice`), 연속 훈련 블록마다 독립 계좌로 다시 돌리는 엄격한 방식(6.3a 규칙 2~5; 학습 노드는 T6.24에서 오므로 여기서는 명시적으로 요청), `selection.parquet.is_scores`와 `n_blocks`, E40 알림의 방식과 계획 실행 수.
- Done means: `--method cpcv`가 경로 5개 Sharpe 분포와 최악 MDD를 선형 `reference` 줄 위의 `primary` 줄에(3.9, #216), 그리고 PBO(분자/분모)를 출력.
- Acceptance: `tests/golden/test_validation.py::test_G91`, `tests/unit/research/test_cpcv.py::test_path_count_and_fresh_capital`, `::test_nothing_to_select_E40_one_path`, `::test_path_interpretation_line`, `tests/unit/api/test_sweep.py::test_sweep_equals_cscv_method`, `tests/docs/test_tool_cards.py::test_card[cpcv]`(D19, #219), `tests/unit/research/test_cpcv.py::test_best_path_never_representative`(6.3a, #216), `::test_is_scores_slice_without_learned_node`, `::test_strict_block_replay_equals_fresh_linear_run`(블록 시작마다 빈 장부와 K, 진입 비용은 IS 수익에, 블록 끝에는 아무것도 물리지 않음), `::test_is_scores_without_grid_E16`, `::test_E40_names_is_scores_mode_and_planned_passes`(6.3a, #215).
- Notes:
  - owner decides at the cut (#314 Decision, 2026-11-10): PBO 옆에 어떤 PBO 경고 줄을 낼지(T6.8도). 만드는 쪽의 추천(#314 Findings)은 경고로만 두 줄, 곧 OOS 손실 확률(IS 최고 후보의 OOS Sharpe가 0 아래인 조합의 몫)과 "N < 10 candidates: PBO is coarse"이며, 후보가 적으면 로짓 분포가 퇴화하기 때문이다.
  - owner decides at the cut (#43 Decisions, 2026-11-04, #202): CPCV 경로의 DSR이 코호트의 선형 관측에서 V[SR]를 가져올 수 있는지, 그리고 6.3a가 그렇다고 말할지(T6.8도).
  - owner decides at the cut (#43 Decisions, 2026-11-04, #205): `docs/design/statistics-verification-plan.md`의 B 단계를 8.3의 성질 행(같은 DGP를 합성 패키지로 만들어 `evaluate`와 `backtest(method=…)`로 돌림)으로 둘지, 어느 티켓이 시험할지(T6.8, T6.24도).

**T6.22 `feat(report): hygiene panel on the first screen and ValidationResult report`** · `M6` `report` · S · Blocked by: T6.21, T2.10b · §6.3a 보고서, §3.9
- Context: 첫 화면 hygiene 칸 일곱 줄(시도 줄, DSR/PSR/MinTRL, 경로 띠, PBO·기울기, 선택 안정성, 누설 장부, 사전 등록), 분자/분모 규칙, `ValidationResult.report()`.
- Done means: report.html 첫 화면에 일곱 줄이 있고 배지가 없다(구조 시험).
- Acceptance: `tests/unit/artifacts/test_report.py::test_hygiene_panel_lines`, `::test_ratios_have_counts`, `::test_no_pass_badges`, `tests/docs/test_tool_cards.py::test_report_explanations_match_cards`(D19, #219), `tests/unit/artifacts/test_report.py::test_primary_and_reference_lines`, `::test_failure_markers_not_nan`, `::test_csv_rows_carry_role`(6.3a, #216), `::test_is_scores_line`(`IS scores` 줄의 네 꼴, strict가 아니면 가정 문장과 함께, `cscv`이거나 `grid`가 없으면 줄 없음; 3.9, #215).
- Notes:
  - decided (#314 Decision, 2026-11-10): `N + m`은 보정된 독립 시행 수가 아니며 DSR에 몰래 넣지 않는다(6.2).
  - owner decides at the cut (#314 Decision, 2026-11-10): 평가한 팩터로 만든 합성 신호가 시도로 어떻게 세어지는지(T6.8도). 만드는 쪽의 추천(#314 Findings)은 위생 줄이 "candidates N = n; factors this graph reads that were evaluated in this family: k of m"을 내고 DSR을 N과 N + m에서 더 큰 감가를 먼저 보이되 새 N 규칙은 두지 않는 것, 그리고 가족 밖에서 평가한 팩터는 6.2가 이미 붙이는 표시로 읽히는 것이며, 선택 사건이 이미 그것을 기록하기 때문이다.

**T6.23 `feat(ml): ml.factor node with engine-enforced training window and fit/predict records`** · `M6` `ml` · M · Blocked by: T6.19, T2.10a, T1.12 · §5.3.11, §6.5 검사 8
- Context: `MLFactor` 노드, 표본 구성, `train=rolling|expanding`, `refit` 일정, 학습 창 규칙(공개 시각 + embargo ≤ τ), E2 포트, 새 객체 학습(2026-11-04, #195: 팩토리·`__sklearn_clone__`·`clone`, 아니면 E16), `classes_`로 맞춘 클래스 확률과 세 클래스의 필수 `score=`, 한 클래스뿐인 훈련 창은 학습하지 않음(`ml_single_class`), seed·스레드 고정, `fit_id` 재사용, `predictions.parquet`·`fits.parquet`·매니페스트 `ml`, sklearn 선택 의존(엔진 import 없음).
- Done means: `ml-factor` 예제의 evaluate가 IC 표와 "fits 24 · samples min 1,830"을 출력하고 모형 파일이 없다.
- Acceptance: `tests/golden/test_ml.py::test_G92`, `tests/property/test_ml.py::test_P_ML_REPRO`, `tests/unit/ml/test_factor.py::test_label_port_only_E2`, `::test_no_pickle_files`, `::test_engine_does_not_import_sklearn`, `::test_seed_from_run_seed_and_fit_id`, `::test_new_model_per_fit_factory_and_clone`, `::test_uncloneable_model_E16`, `::test_score_by_class_value_not_column`, `::test_three_classes_need_score_E16`, `::test_single_class_window_not_fitted`, `tests/unit/ml/test_sklearn_pipeline.py::test_pipeline_fit_ignores_held_out_features`(`nexusbt[ml]`로: 척도기와 모형이 든 `Pipeline` 하나; 훈련 표본 밖 판단의 특징을 바꿔도 척도기가 배운 평균이 같고, 두 학습이 단계 객체를 공유하지 않음), `tests/unit/ml/test_factor.py::test_provenance_level_per_fit_and_manifest_counts`(#216), `tests/property/test_ml.py::test_P_FUT_ml_fit_id`(τ 뒤 행을 같은 연도 파티션에 더함: τ 이전의 같은 `fit_id`·seed·예측·목표), `tests/unit/ml/test_factor.py::test_corrected_training_value_new_fit_id`(새 `fit_id`, 재사용 없음; 예측은 비교하지 않음), `::test_hash_seconds_beside_fit_seconds`(#270).
- Notes:
  - carried (#43 Decisions, 2026-11-20, #250): 5.9.4의 "tier (3) was not compared" 줄과 `--save-detail`은 만들어지지 않았다(`nexusbt rerun --save-detail`은 `NotImplementedError`를 낸다). 실행 종류가 처음 `detail/`을 쓰는 티켓이 둘을 더한다(T6.24도).

**T6.24 `feat(ml): ml.factor inside method folds, rerun refit hash check and determinism warnings`** · `M6` `ml` · S · Blocked by: T6.23, T6.21, T1.15 · §5.3.11, §6.3a
- Context: 모든 방법에서 앞쪽만 학습(τ 뒤 표본 없음; CPCV는 그 분할의 시험 묶음·정화·엠바고 제외; walk-forward는 폴드 범위로 자르지 않음), 누설 장부 `ml fits: forward-only` 줄, 겹칠 수 있는 설정 E29, `rerun` 재학습 `pred_sha256` 비교(E15/허용 오차), E44, 같은 `fit_id` 재사용(WF 겹침·CPCV 같은 조합).
- Done means: ML 전략을 `--method cpcv`로 돌리면 학습 수와 재사용 수를 출력하고 `rerun`이 "predictions identical (n fits)"를 출력. (2026-11-04, #197) 분류 팩터의 `evaluate`가 5.7의 로그 손실·Brier 줄을 채점 수/전체와 함께 출력.
- Acceptance: `tests/unit/ml/test_folds.py::test_forward_only_in_every_method`, `::test_cpcv_excludes_test_groups`, `::test_overlap_setting_E29`, `tests/unit/api/test_rerun.py::test_ml_refit_hash_equal`, `::test_threads_warning_E44`, `tests/property/test_cache.py::test_P_CACHE_FIT`(2026-11-04: CPCV 조합과 `run_seed`는 학습 L1 항목을 공유하지 않음, 캐시 켬 = 끔; #270: 찬 캐시와 데운 캐시가 같은 `fit_id`), `tests/unit/ml/test_scoring.py::test_multiclass_log_loss_over_declared_classes`, `::test_brier_on_chosen_score`, `::test_training_decision_not_scored`(2026-11-04, #197), `tests/docs/test_tool_cards.py::test_card[log-loss-brier]`(D19, #219), `tests/unit/ml/test_scoring.py::test_predict_proba_contract`(모양, [0, 1], 행 합, `classes_` 겹침 → E41; #310), `tests/unit/ml/test_folds.py::test_provenance_level_by_fold_use`(5.3.11, #216), `::test_online_refit_labelled`, `tests/property/test_validation.py::test_P_INCOMPLETE`(6.3a, #216; 둘 다 폴드 안의 ML 팩터가 필요), `tests/golden/test_validation.py::test_G116`, `tests/property/test_validation.py::test_P_IS_STRICT`(빼 둔 정답, 넘겨받은 계좌 상태 없음, 시험 기간 가격으로 만든 뒤쪽 시장 피처는 여전히 바뀜), `tests/unit/ml/test_folds.py::test_is_scores_strict_by_default_with_learned_node_and_grid`, `::test_approximate_is_labelled_and_caps_provenance_level`, `::test_strict_fits_counted_in_E40`(6.3a, 5.3.11, #215).
- Notes:
  - decided (#43 Decisions, 2026-11-18, #315): `nx.ml.factor(..., label_norm=)`은 결정일마다 그 적합의 학습 표본에 걸쳐 정규화하고, 얇은 날은 빼고 세며, `feature_norm=`은 없다. 고침은 5.3.11, 3.8의 서명, 6.3a, 12.1 V31-43, 이 티켓과 T6.Gv의 시험에 닿고, 일부만 있는 날은 이 티켓이 정한다. 스펙 변경으로 주인에게 묻는다.

**T6.24b `feat(ml): pretrained predict-only models with training cutoff leak guard`** · `M6` `ml` · S · Blocked by: T6.24, T6.Gv · §5.3.11, §6.2, §6.6
- Context: `nx.ml.pretrained(model, training_cutoff=, corpus=, allow_overlap=)`, `predict`만, cutoff + embargo 이전 판단 E48(실패)·`allow_overlap` E49 표시·보고서 줄·매니페스트 가정, 검증 경로 표시, `fit_id`에 모형 식별, 후보로 셈.
- Done means: 가짜 사전학습 모형(정해진 예측 함수)으로 G-106의 숫자(막힘 24, 분모 84)를 출력하고, `allow_overlap=True` 실행 보고서 머리에 겹침 줄이 보인다.
- Acceptance: `tests/golden/test_ml.py::test_G106`, `tests/unit/ml/test_pretrained.py::test_cutoff_required_E16`, `::test_leak_E48`, `::test_overlap_marked_E49`, `::test_counted_as_candidate`.

**T6.25 `feat(research): triple-barrier label sharing the exit fill rule`** · `M6` `research` · S · Blocked by: T3.33, T2.10a, T6.Gv · §5.8, §3.7 탈출
- Context: `labels.triple_barrier(take_profit, stop_loss, max_sessions)`, 5.6.4 판정 함수·`time_stop` 세션 셈 재사용, `tb_ret`·`tb_side`, 정답마다 다른 끝 시각과 정화, 폐지 종료가치.
- Done means: `nx.evaluate(f, target=nx.labels.triple_barrier(take_profit=0.05, stop_loss=0.03, max_sessions=10))`가 IC와 장벽별 건수(위/아래/시간)를 출력.
- Acceptance: `tests/golden/test_labels.py::test_G93`, `tests/unit/research/test_triple_barrier.py::test_same_fill_function_as_exits`, `::test_label_end_varies_and_purges`, `::test_dividend_on_end_session_is_cash`(2026-11-04: 배당락일 봉 안의 장벽 청산은 권리를 현금으로 더하고 그 봉의 이후 가격을 읽지 않음), `::test_time_exit_next_open_matches_time_stop`(#195: `time_exit="next_open"`이면 `tb_ret`이 같은 `exits` 전략의 비용 0 1주 수익과 같음, G-93 (e)).
- Notes:
  - owner decides at the cut (#43 Decisions, 2026-11-04, #201 and #200): 현금 배당이 삼중 장벽 경로의 장벽을 옮기는지(5.6.2a는 분할, 병합, 주식 배당 잠금 해제에 크기를 바꾸고 현금 배당에는 말이 없다). 골든 티켓은 배당락일 봉 안의 장벽 퇴출을 손계산 사례로 더한다(T6.Gv도).
  - carried (#752 Decisions, 2026-11-26): `Panel`이 빠진 뒤 어떤 엔진 코드도 E2 `LabelLeakError`를 내지 않는다. 그것은 `labels.triple_barrier`와 함께 돌아온다(6.5).

**T6.26 `perf: P11 high-dimensional workload with decision-date-only evaluation, column pruning and batched reductions`** · `M6` `bench` · M · Blocked by: T2.24, T6.4, T6.5 · §7 P11, §5.3.2, §5.3.8 *(생성기와 fixture는 T2.24로 옮김 [#175])*
- Context: T2.24의 생성기와 `bench/fixtures/p11.json` 위에서, 판단 행만 계산(행 마스크 거꾸로 전파), 칼럼 가지치기, `evaluate` 판단마다 줄이기(전체 값 행렬을 두지 않음), 합성 점수 판단 하나 행렬, (시장, 연도, 노드 묶음) 병렬; 측정 JSON(시간·USS·읽은 바이트·판단 행·공유 노드).
- Done means: `uv run python bench/run.py --workload P11 --fixture bench/fixtures/p11.json --snapshot synth-full-0001`이 (a)(b)(c) 시간·단계별 시간·USS·`fixture_sha256`·출력 값 해시를 출력하고(cold·warm 둘, 해시 같음) 잰 첫 숫자를 목표 옆에 적는다(측정 시제품; 사용자가 측정 기계에서; 2026-11-24부터 관문 없음, ADR 0054).
- Acceptance: `tests/perf/test_p11_smoke.py::test_small_p11_runs_and_reports`, `tests/property/test_pipeline_invariants.py::test_decision_rows_only_equals_full`, `tests/unit/compute/test_memory.py::test_evaluate_does_not_hold_full_matrix`, `tests/perf/test_p11_smoke.py::test_cold_warm_output_hash_equal`.

**T6.27 `docs(examples): walk-forward/CPCV and ML factor templates`** · `M6` `docs` · S · Blocked by: T6.24, T5.18, T6.8, T6.9, T6.20, T6.21, T6.24b, T6.22 · §3.10 템플릿, §8.5 *(2026-11-04: 8.5의 M6 실습 예제 넷과 사용 시나리오 3, 4, 7, 8, 9, D19, #219)*
- Context: 템플릿 `walk-forward-cpcv`, `ml-factor`(sklearn 선택 의존 없으면 시험용 선형 모형), 출력 대조; 8.5 실습 예제 `leaky-training`, `best-of-many`, `preprocessing-window`, `periodic-reselection`(스크립트, 영어·한국어 쪽, 분할마다의 결정일 표).
- Done means: 두 템플릿이 `init --demo`에서 돌고 출력 블록이 같다. 실습 예제 넷이 각자의 seed로 합성 `small` 스냅숏에서 돌고 8.5 행의 엔진 신호를 출력하며, 각 쪽이 출력 옆에 가정, seed, 자료, 예상 관찰을 적는다. 8.5의 사용 시나리오 3, 4, 7, 8, 9가 통과한다.
- Acceptance: `tests/docs/test_templates.py::test_template_runs[walk-forward-cpcv]`, `::test_template_runs[ml-factor]`, `tests/docs/test_lessons.py::test_lesson[leaky-training]`, `::test_lesson[best-of-many]`, `::test_lesson[preprocessing-window]`, `::test_lesson[periodic-reselection]`, `tests/docs/test_scenarios.py::test_scenario[3]`, `::test_scenario[4]`(바뀐 라벨을 훈련에 쓸 수 있게 되는 첫 순간까지의 불변, 엠바고 포함, 두 쪽 다; 6.3a, #271), `::test_scenario[7]`(기본이 엄격한 방식, `approximate` 줄; #215), `::test_scenario[8]`, `::test_scenario[9]`.

**T7.G `test(golden): hold-band edge cases (G-63)`** · `M6 (T7.1 앞)` `golden` · S · Blocked by: T0.9 · §5.5.3, §8.2
- Context: 결측 점수 유지·연속 상한, 보유 0인 완충대 종목의 매수 건너뛰기, 숏 쪽(`bottom(hold=)`) 거울 사례 하나. T7.1 전에 병합.
- Done means: `uv run python tests/golden/check/G-63.py`가 판단별 목표 집합·이유·주문을 출력.
- Acceptance: `test_handcalc_self.py::test_case_G63_expected_present`.

**T7.1 `feat(portfolio): target-state recursion and hold band`** · `M6 (마지막 티켓, v1에 포함 — 사용자 2026-10-28)` `portfolio` · M · Blocked by: T6.11, T6.18, T7.G, T4.14, T5.16, T6.22, T6.24, T6.25, T6.27 · §5.5.3 [SC-02, OQ-1]
- Context: `top(n, hold=m)`·`bottom(n, hold=m)` 구현, `on_missing`·`max_missing_decisions`, 집행 단계 `band_entries`(`order_suppressed(band_entry)`), 기준점(backtest·screen `anchor`·live 장부), `prior`/`target_state` 전달, screen이 같은 스냅숏 실행의 `targets.parquet`에서 이어 받기, 보고서 기준점 줄, "목표 집합 vs 보유 집합 차이 건수".
- Place: (2)단계가 티켓을 자를 때 다시 정한다(#725 결정 244); 그때까지 이 항목은 티켓 그래프에서 제자리를 지킨다.
- Done means: `hold=20, n=10` 전략의 회전율이 `hold=None`보다 낮게 출력되고, 같은 기준점의 screen 목표 = backtest 목표.
- Acceptance: `tests/unit/portfolio/test_hold_band.py::test_keep_within_m`, `::test_fill_to_n_by_rank`, `::test_anchor_screen_equals_backtest`, `::test_missing_score_drop_default`, `::test_missing_score_hold`, `::test_bottom_hold_mirrors`, `tests/golden/test_portfolio.py::test_G63_band_edges`, `tests/property/test_execution_invariants.py::test_P_PARITY13_with_hold`, `tests/unit/portfolio/test_hold_band.py::test_held_missing_weight_uses_median_u`, `::test_hold_equals_n_keeps_missing_score`, `tests/docs/test_templates.py::test_template_runs[buffer-hold]`.

**T7.V `verify: post-T7.1 release re-verification (no features)`** · `M6 (T7.1 뒤 확인 단계, 기능 아님)` `release` · S · Blocked by: T7.1 · §7, §8, §9.1 `engine / release`, R-70
- Context: T7.1이 목표 경로를 바꾼 뒤 출시 관문을 다시 돈다: `engine / release`(깨끗한 설치·빠른 시작·독립 생산자), 대조 L1·L2 전체, P-SHORT-OFF(차등 + 기준선), 성질 `deep` 프로필, 7장 측정을 앞 측정과 견줌(사용자가 측정 기계에서), 규칙 검증 증거. 새 기능·명세 변경 없음(실패면 그 원인 티켓을 다시 연다).
- Done means: `uv run python -m tests.repo.release_check --all`가 "release gate after T7.1: pass"와 각 묶음 통과 수를 출력하고 성능 JSON이 커밋된다.
- Acceptance: `tests/repo/test_release.py::test_release_rerun_after_last_feature`.
- Notes:
  - carried (#43 Decisions, 2026-11-19, #252 and #612): 스펙 8.1의 L1-b 행은 역분할을 이름 대고, 합성 `small` 패키지의 비교 범위에는 한국에 하나(KR:T00042), 미국에는 없다.

**T6.28 `perf: re-measure chapter 7 on a real snapshot (summary evidence)`** **[2026-11-11, #162]** · `M6 (T7.V 뒤 출시 증거, 기능 아님)` `bench` · S · Blocked by: T7.V, T6.15 · §7, §2.7, 12장 OI-46 — **사용자가 계산 기계에서 실행**
- Context: OI-46 출시 정의의 공개 절반 중 첫째; M6의 끝(합성 적합성, 10.0)은 이것을 기다리지 않는다. 7장의 작업 P1~P7과 P5-daily를 T6.11과 같은 `bench/run.py` 명령·측정 규칙으로, 저장소 밖에 두는 실제 스냅숏에서 잰다. 공개 규칙(2.7)을 다시 적는다: 요약 숫자만. 결과 JSON은 7장 측정 규칙의 그것(작업마다 p50/p95, RSS와 USS, 캐시 상태, 거기 적힌 나머지 필드)이되 `snapshot_id` 자리에 스냅숏의 해시를 담고, 스냅숏의 다른 것은 담지 않는다: 경로·호스트·계정·생산자·종목 이름도, 행도 없다. `release_evidence.json`(T6.15)이 `real_data.measurement` 아래에 이 파일을 가리킨다.
- Done means: `bench/results/<YYYYMMDD>-<git sha>-<machine>-real.json`(`<machine>`은 T6.11과 같음)이 커밋되고, PR에 작업마다 한 줄인 짧은 표가 있다: 합성 p50/p95와 USS(T7.V의 JSON) 옆에 실제 값.
- Acceptance: `tests/unit/bench/test_results_present.py::test_real_snapshot_result_has_summary_fields_only`(이름이 `-real.json`인 결과 파일은 스냅숏 해시가 있고 `snapshot_id`와 7장 목록 밖의 키가 없다), `tests/repo/test_release.py::test_release_summary_links_real_measurement`.
- Notes:
  - decided (#43 Decisions, 2026-11-01, #17): 문서는 한국 실자료 검증과 긴 한국 백테스트가 1999-01-04 이후에 시작한다고 말하고, 생산자는 그 전의 토요일 세션을 여전히 줄 수 있다. 엔진 규칙은 바뀌지 않는다.

**T6.29 `test(release): verify a real ledger event by event against the situation table`** **[2026-11-11, #162]** · `M6 (T7.V 뒤 출시 증거, 기능 아님)` `release` · S · Blocked by: T7.V, T6.15, T5.11b · §8.4 (LV-01..LV-08), §5.9.7, §2.7, 12장 OI-46 — **사용자가 자신의 장부로 실행**
- Context: OI-46 출시 정의의 공개 절반 중 둘째; T6.28처럼 M6의 끝은 이것을 기다리지 않는다. `manual:` 장부로 옮긴 소유자의 실제 장부와 실제 스냅숏, 둘 다 저장소 밖. 8.4 표의 LV-01~LV-08 줄마다 그 상황이 일어난 세션 하나를 `reconcile`(5.9.7)로 대조하고, "statement" 줄은 8.4가 말한 대로 소유자가 읽으며, 체결이 있으면 체결 대 판단 bp를 모형의 기준(다음 시가; 주문 시각·종류·수량을 맞춤)에 대어 잰다. 기준은 표이지 장부의 길이가 아니다: 장부가 덮지 못하는 줄은 사유와 함께 "not observed"다. 공개 규칙(2.7)을 다시 적는다: 요약 숫자만. `release_evidence.json`(T6.15)은 `real_data.ledger_situations` 아래에 줄마다 항목 하나를 담는다: 줄 id, `reconciled` 또는 `not observed`, 대조한 세션 수, 8.4 줄이 견주는 두 값이 같았는지(다르면 그 차이를 숫자로), bp 중앙값, 관찰되지 않았을 때의 사유; 날짜·종목·수량·가격·경로·이름은 없다.
- Done means: `uv run python -m tests.repo.release_check --all`이 "real-data evidence: measurement linked (또는 `missing`) · ledger situations a reconciled, b not observed (of 8)"를, 증거가 없으면 "real-data evidence: none (synthetic conformance)"를 출력하고, PR에 여덟 줄 표가 있다.
- Acceptance: `tests/repo/test_release.py::test_ledger_situation_entries_match_the_LV_rows`(8.4의 줄마다 항목 하나, 각각 세션이 하나 이상인 `reconciled`이거나 사유가 있는 `not observed`), `::test_ledger_situation_entries_have_summary_fields_only`, `::test_gate_summary_links_ledger_situations`, `::test_verified_claim_needs_measurement_and_ledger_situations`(T6.15의 "KR/US verified" 문장은 둘이 다 있을 때만); 시험은 커밋된 `release_evidence.json`에 `real_data`가 있으면 그것을, 없으면 합성 `small` 스냅숏(4.8)의 모의 장부로 쓴 것을 읽는다.

#### v1.x — v1 직후 (M6 뒤)

**T7.2 `feat(research): effective number of trials and DSR(N_eff)`** · `v1.x` `research` · S · Blocked by: T6.8 · §5.7 [SC-10, OQ-6]
- Done means: 상관 높은 후보 6개 + 독립 후보 2개 study에서 N = 8, N_eff ≈ 3을 출력, 방법 이름 기록. 5.7의 N_eff 행이 군집 수준 수익 시계열, 군집 사이 Sharpe 분산, 기간 정렬을 정의한 뒤에만 끊는다. 방법을 ONC라 부르지 않는다(2026-11-04, #197).
- Acceptance: `tests/unit/research/test_neff.py::test_clustered_candidates`, `::test_method_recorded`, `::test_dsr_default_still_uses_N`.

**T7.3** → v3.3에서 **T3.29**(M3a)로 옮겼다(그룹 상한을 v1로).

**T7.4** → v3.3에서 **T3.33**(M3b)로 옮겼다(`time_stop`을 v1로).

**T7.5 `feat(artifacts): Brinson sector attribution and first divergence`** · `v1.x` `artifacts` · M · Blocked by: T4.10, T5.5 · 청사진 11장 2·5번 [SC-07]
- Done means: 슬리브별 배분·선택·상호작용(비교 기준 `universe_ew`) 표; `Comparison.first_divergence()`가 처음 갈린 날짜·종목·원인.
- Acceptance: `tests/unit/artifacts/test_brinson.py::test_effects_sum_to_active_return`, `tests/unit/api/test_compare.py::test_first_divergence_cause`.

**나중(P3, 티켓은 의미 계약·고정 사례를 갖춘 뒤 만든다)** [RV 2.4]: 현금 이자의 `rates` 금리 자료 연결(고정 연율 `[account] cash_rate_bps`는 v3.2에서 v1에 넣음), T+n 결제 모형, 벤치마크 회귀 지표(α·β; 추적오차·IR은 v3.1 T4.12, 왕복 거래 표는 v3.1 T5.14), v3.1에서 미룬 것 12.1 전부, MDA 특징 중요도·묶음 MDA·표본 고유도 가중·Hansen SPA·메타 정답(v1.x), 상관 충격·VaR 덮개, `stop_limit_fill = close_confirmed` 선택 모형, 현금 보유(재투자 없음) 경제 정답 변형, 빠른 근사 모드(`fidelity="vector"`), Sharpe 부트스트랩 구간, 내장 팩터 넓히기(`Beta`·`Correlation`·`BollingerBands`), 별도 `adjustment_factors` 데이터셋(측정 뒤), 시장 규칙 팩 추가 시장, zipline·LEAN·Nautilus·DBN 가져오기(TDS 9장), 장부 정의 옮기기(`nexusbt book migrate`).

### 아직 티켓이 없는 일

아래 줄은 10.1에 아직 티켓이 없는 일을 묶는다. 각 줄은 이 폴더의 `README.md`가 정한 꼴로 쓴다. 그 가운데 하나의 티켓을 자르면, 그 줄들은 같은 PR에서 그 티켓 항목 밑이나 그 이슈로 옮기고 이 절에서 뺀다.

#### Stage (2)

쓰기 도구, 값 표를 읽는 쪽(`nx.Item`), 결과의 표시, 사용자가 만나는 이름.

- decided (#752 Decisions, 2026-11-27): N, 곧 사용자가 만나는 이름 `symbol`, `date`, `prices`와, 결과 표의 `symbol`을 그 행 날짜의 `instrument_symbols`에서 읽는 일이 2단계의 첫 조각이다. 저장 이름은 그대로 둔다(스펙 머리 "Identifier name", 3.1; #725 Decisions 248).
- owner decides at the cut (#752 Decisions, 2026-11-27): 그날 `instrument_symbols` 행이 없는 종목의 `symbol`; `latest_symbol`을 처음부터 두는지; `Market.series`, `explain`, `override`의 `instrument_id` 인자의 이름과 뜻; `Run.to_pyfolio()`의 `symbol`이 저장 열쇠인지 체결일에 쓰던 심볼인지.
- owner decides at the cut (#725 Decisions 96, 2026-11-23): 2단계의 첫 조각이 끝에서 끝까지 한 길도 담는지: 종가 표 하나로 첫 결과, 달력의 출처 표시, 두 번 적힌 열쇠를 파일과 줄로 보이기, 고친 뒤 같은 명령의 성공.
- decided (#705 Decisions A, 2026-11-21): 맞음, 쉬움, 가벼움이 부딪치면 맞음이 먼저, 다음이 쉬움, 다음이 가벼움이다. 쉬움은 도구가 일을 해서 오고, 도구는 사용자가 주지 않은 사실을 지어내지 않는다.
- decided (#705 Decisions E, 2026-11-21): 결과의 표시마다 그 사실을 도구가 확인했는지 생산자가 증언했는지 말하고, 기본은 "증언"이다.
- decided (#705 Decisions E, L1 and H, 2026-11-21): TDS는 논리 표를 먼저, 디스크 배치를 그다음에 적는다. 쓰기 부분 하나가 메모리의 표를 패키지로 바꾸며, 다른 생산자가 그대로 쓰도록 `nexusbt-tds`에 들어간다.
- decided (#705 Decisions E, I, 2026-11-21): 결과는 E30과 manifest의 `assumptions`, `fallbacks` 위에 세운 표시 한 벌을 가진다.
- decided (#705 Decisions 10, 2026-11-21): 표시 블록의 첫 줄들(가격, 달력, 행, 정체성, 유니버스, 대체 동작)은 쓰기 부분과 함께 만든다.
- decided (#705 Decisions picture 1, 2026-11-21): 들어오는 길 셋이 같은 검사를 하는 쓰기 부분 하나를 부른다: 가격 파일을 위한 한 줄 명령(파일, 시장, 가격 기준), 설정 파일, 표를 받는 Python 호출 하나.
- decided (#705 Decisions picture 2, 2026-11-21; #725 Decisions 205): 사용자는 시장을 한 번 적고(달력, 통화, 시간대가 따라온다), 가진 종류마다 그 파일을 아무 순서로 적는다.
- decided (#705 Decisions 9, 2026-11-21; #752 Decisions, 2026-11-26): 사용자는 자기만 아는 사실만 적는다. 도구가 주어진 종류에서 프로필을 고르고 종류마다 관례(주식 일봉의 `bar_time = session`, `ts_end` 규칙)를 적으며, 각각을 도구가 정한 것 목록에 올리고, 사용자가 적은 것이 이긴다.
- owner decides at the cut (#705 Decisions 14 and 17(9), 2026-11-21; #725 Decisions 94, 2026-11-23; #752 Decisions, 2026-11-26): 어떤 종류든 하나씩, 아무 순서로 더할 수 있도록 도구가 패키지의 선언 프로필(TDS 4.2, 7)을 어떻게 정하는지, #720이 어떻게 맞물리는지. 사용자는 프로필을 고르지 않는다.
- decided (#725 Decisions 95, 2026-11-23): 프로필의 답이 무엇이든 도구는 빈 틀을 만든다.
- builder's choice (#725 Decisions 95, 2026-11-23; 추천: 드물게 묻기, 너무 자주 물으면 읽지 않기 때문): 수상한 자료를 몇 퍼센트나 몇 배부터 묻는지, 사용자가 "확인함"을 어떻게 적는지.
- decided (#705 Decisions picture 3, 2026-11-21): 사용자만 아는 사실(가격이면 가격 기준)이 없으면 도구는 멈춘다. 흔한 값을 말할 수는 있으나 적용하지 않는다.
- decided (#705 Decisions picture 4, 2026-11-21): 도구는 스스로 알 수 없는 것(어느 칼럼이 무엇인지, 두 가지로 읽히는 날짜 꼴, 단위와 배율)만 묻고 멈추며, 오류가 무엇을 적을지 말한다.
- decided (#705 Decisions 16, 2026-11-21): 도구가 알 수 없는 것은 물어서 없으면 멈추거나, 모름으로 적고 조심스러운 쪽으로 읽어 표시하거나, 칼럼 이름으로 받는다. 가격 기준과 종류, 배당 금액이 그날의 주식 수 기준인지 뒤의 분할로 조정된 것인지, 환율의 하루 중 시각을 묻는다.
- decided (#705 Decisions picture 5, 2026-11-21): 가격 파일만 있으면 도구는 `listed_on` = 첫 봉, `listed_on_censored = true`로 `instruments`를 만들고, 정체성을 "티커에서, 이름 바뀜과 재사용은 풀지 않음"으로 표시하며, `last_session`이나 상장폐지를 쓰지 않는다. 주어진 종목 목록이 이긴다.
- decided (#705 Decisions picture 6, 2026-11-21): 파일을 받지 못한 종류는 결과의 표시에 나와, 결과가 할 수 있는 것과 없는 것, 까닭, 더할 것을 말한다.
- owner decides at the cut (#705 Decisions picture, 2026-11-21): 도구의 설정 키, 명령 인자, 함수 이름.
- decided (#705 Decisions 13, 2026-11-21; #725 Decisions 216): 도구는 가격 파일마다 `asset_class`(주식이나 ETF, 또는 지수 값)를 묻고 짐작하지 않는다. 섞인 파일은 종목 목록이 있어야 하고, 그 목록의 종류가 한 번 선언한 기본값을 이긴다.
- decided (#705 Decisions 15, 2026-11-21): 한 뜻으로 읽히는 칼럼이 둘이면 도구는 멈춘다.
- decided (#705 Decisions 16, 2026-11-21): 배당의 날짜는 `ex_date`나 `record_date`에, 상장폐지의 날짜는 `last_trading_date`나 `exit_date`에 대응시켜 선언한다. 대응이 없으면 도구는 멈춘다.
- owner decides at the cut (#752 Decisions and its user-file table, 2026-11-24): `corporate_actions`와 `delistings`의 사용자 파일 칼럼 이름. 표의 제안: `ex_date`; `split_to` → `ratio_num`, `split_from` → `ratio_den`, `ratio_new_per_old`는 도구가 씀; `kind`는 행이 온 파일과 비율의 방향에서; `amount` → `cash_per_share`, `currency`와 선언한 `gross_or_net`과 함께; `last_trading_date`; `reason` → `delist_type`; 선택인 `final_price`는 `ref_price`에 대한 수익률로 바꿈; `event_id`, `ts_effective`, `affects`, `factor_method`, `status`는 도구가 씀.
- decided (#705 Decisions 17(7), 2026-11-21; #725 Decisions 206, 249): K1의 꼴을 벗어난 id를 만들 심볼은 도구를 멈추고 오류에 고칠 길을 적는다. 도구는 심볼에 자기 접두어나 접미어를 붙이지 않는다.
- decided (#705 Decisions 17(8), 2026-11-21): 가격 파일 하나는 시장 하나다. 시장이 섞인 파일은 시장 칼럼이 있어야 하고, 없으면 도구는 멈춘다.
- decided (#705 Decisions 17, 2026-11-21; #725 Decisions 171, 2026-11-23): 도구는 언제나 빽빽한 일봉을 쓰고 `density`를 받으면 멈춘다. 도구가 생기기 전까지 `tds import csv`는 `density: dense`를 계속 받는다.
- decided (#705 Decisions 21, 2026-11-22): 사용자가 `index_kind`가 비어 있는 지수를 고르면 결과가 그렇다고 말한다.
- decided (#705 Decisions E, G2, 2026-11-21): 거래소 달력이 없는 시장에는 도구가 24시간 달력(`session_kind = continuous_24h`)을 주고, `calendar_id`를 비우지 않는다.
- decided (#725 Decisions 61, 2026-11-23): 시장 선언이 거래소 달력을 가져오면, 선언한 시간으로 봉 날짜에서 짐작한 달력은 거래소 달력을 쓸 수 없는 곳에서만 쓴다.
- owner decides at the cut (#705 Decisions, 2026-11-21; #725 Decisions 86): 도구의 거래소 달력 라이브러리를 `nexusbt-tds`의 선택 추가로 둘지. 도구는 pyarrow 말고 필수 의존성을 더하지 않는다(#508).
- decided (#725 Decisions 74 and 75, 2026-11-23): 도구는 종류마다 한 모양, 곧 모든 종목을 담고 행마다 `symbol`이 있는 긴 표를 CSV, Parquet, 메모리의 표에서 읽는다. 긴 표가 아니면 멈추고, 빠진 `symbol` 칼럼과 모양 바꾸는 법을 말한다.
- decided (#725 Decisions 76, 2026-11-23): 도구는 종목을 `symbol` 하나로 부르고 `ticker` 칼럼은 별칭으로도 받지 않는다. 분할과 배당은 사용자 파일 둘로 와서 `corporate_actions` 하나에 들어간다.
- decided (#725 Decisions 77, 2026-11-23): 문서에 적힌 이름의 칼럼은 대소문자와 앞뒤 공백만 무시하고 대응 없이 읽고, 그 밖의 칼럼은 사용자가 그 칼럼만 대응시킨다. 도구는 무엇을 무엇으로 읽었고 무엇을 쓰지 않았는지 알리고, 빠진 필수 칼럼의 이름을 대며 멈춘다.
- decided (#725 Decisions 78 and 120, 2026-11-23): 시장마다 다른 것(가격 기준, 거래량 단위, 배당 세금, 단위)은 칼럼이 아니라 시장에 한 번 선언한다. 보고는 대응 미리보기가 있는 곳에, 원본 값 하나가 몇 주로 저장되었는지 보인다.
- decided (#725 Decisions 81, 2026-11-23): 도구는 짐작한 이름으로 칼럼을 읽지 않고, 가격 기준을 정하지 않고, 수상한 값을 고치지 않고, 자료에서 시장을 짐작하지 않는다.
- decided (#725 Decisions 84, 2026-11-23): 한 종류가 같은 칼럼의 긴 파일 여럿으로 올 수 있고, 행의 날짜로 나뉘며, 파일 이름에서 사실을 읽지 않는다. 한 열쇠가 두 파일에 있으면 도구는 어느 것도 고르지 않고 멈춘다.
- decided (#725 Decisions 85 and 86, 2026-11-23): 도구는 8 GB 기계 한 대에서 수천 종목, 수십 년의 일봉을 받고, 조각으로 읽어 파티션(한 해)을 많아야 하나만 들며, 칼럼 형은 표준의 스키마에서 오고 열쇠와 순서는 파티션마다 검사한다. 문서는 작은 자료의 길로 메모리의 표를 곧바로 넘기는 것을 적는다.
- decided (#725 Decisions 87, 88 and 114, 2026-11-23): 갱신은 `parent_snapshot_id`를 가진 새 패키지로, sha256이 같은 파티션 파일을 함께 쓰고, 같은 입력과 설정으로 처음부터 만든 것과 값이 같다. 값이 바뀐 부모 행은 알리며(열쇠, 전, 후), 조정 가격만 있는 경우 도구는 갱신마다 과거가 바뀐다고 말한다.
- decided (#725 Decisions 114 and 115, 2026-11-23): 입력 파일은 그것과 설정(시장 선언, 가격 기준, 거래량 단위, 칼럼 대응, 달력)이 그대로일 때만 읽지 않고 건너뛴다. 가격 파일은 그대로인데 거래량 단위를 고치면 모든 파티션을 다시 쓰고, 시험이 그것을 지킨다.
- decided (#725 Decisions 92, 2026-11-23): 도구는 설정 없이 폴더의 정해진 파일 이름을 읽고, 작은 자료는 `run_pipeline`에 준 표를 곧바로 받으며(안에서 같은 패키지를 만들고 결과가 그렇다고 말함), 초안 대응은 사람이 확인한 줄에만 쓴다.
- decided (#725 Decisions 93 and 260, 2026-11-23): 도구는 수상한 가격 자료(분할 없는 급락, 단위가 바뀐 듯한 거래량, 마지막 날 전에 끝나는 종목이 하나도 없음)를 묻고 값을 고치지 않는다. 같은 열쇠의 행은 묻지 않고 멈춘다.
- decided (#725 Decisions 99, 2026-11-23; #705 Decisions 44 and 46, 2026-11-22): 도구는 쓰기와 검사를 한 번에 하고, 첫 줄은 "N block saving, N to look at"이며, 막는 것이 남아 있는 동안 패키지를 쓰지 않는다. 두 번 적힌 열쇠는 두 행의 파일, 줄, 값을 보인다. #715(종가만 있는 파일이 들어간 뒤 종목도 고칠 길도 말하지 않는 M008 줄들; H 코드에서만 까닭을 적는 건너뛴 검사)는 도구를 자를 때 읽는다.
- decided (#725 Decisions 100, 2026-11-23; #705 Decisions E, H3, 2026-11-21): 도구는 할 수 있는 것을 세 부분으로 말한다: 읽은 자료(행, 종류별 기간), 사건이 빠짐없는지 알 수 없다는 것, 이 엔진 판이 주는 계산. `nexusbt doctor`도 그 티켓을 자를 때 같은 식으로 넓힌다.
- decided (#725 Decisions 101, 2026-11-23; #764 Decisions, 2026-11-25): 대응 미리보기는 이름 옆에 원본 값 두세 개와 각각을 어떻게 읽었는지(형, 단위)를 보인다. 확인한 대응은 저장하고 새 칼럼이나 바뀐 칼럼만 다시 묻는다. 입력의 첫 행 미리보기는 따로 만들지 않는다.
- decided (#725 Decisions 104, 2026-11-23): 갱신을 만들기 전에 도구의 보고(읽은 것, 쓰지 않은 것, 기본값으로 채운 것)를 패키지마다 남기고, 마지막 세션이 같은 두 정정은 `snapshot_id`로도 가른다.
- decided (#725 Decisions 117, 2026-11-23): 패키지는 해시 전체로 가른다. 화면에 보이는 짧은 앞부분은 유일함을 약속하지 않고, 한 곳에서 두 앞부분이 겹치면 더 보인다(#733).
- decided (#725 Decisions 125, 2026-11-23): 사용자가 준 퇴출의 마지막 거래일이 그 종목의 `last_session`이고, 도구의 채우기는 거기서 멈춘다.
- decided (#764 Decisions, 2026-11-25): 도구는 만드는 동안 진행을 보인다.
- decided (#764 Decisions, 2026-11-25): 낡은 패키지는 기본으로 켜진 채 자동으로 지우되 네 가지를 지킨다: 저장된 실행이나 장부가 이름을 댄 패키지는 지우지 않음; 가장 새 몇 개(그 수는 설정)는 지우지 않음; 한 갱신에서 지울 수 있다고 알리고 다음 갱신에서 지움; 지울 때마다 실제로 비운 공간을 알리고, 미리 해 보기와 끄는 설정이 있음.
- carried (#764 Decisions, 2026-11-25): 엔진 기록이 이름을 댄 것을 도구가 어떻게 아는지, 남겨 둘 패키지의 기본 수, 파일을 나눠 쓰는 파일 시스템에서의 공간 셈은 티켓을 자를 때 만드는 쪽이 정한다.
- decided (#725 Decisions 106 and 107, 2026-11-23): 3단계는 같은 자료를 파일 하나, 파일 여럿, 메모리의 표로 주어도 같은 값 해시와 같은 발견이 나온다는 시험을 더한다. #621의 회귀 사례는 "늦게 정정된 배당이 지난 결정일의 수익률을 바꾸지 않는다"이다.
- decided (#725 Decisions 116, 2026-11-23): 도구의 done-means는 날짜가 여러 번 되돌아가는 종목 순서의 큰 CSV(다시 정렬하지 않음, 멀리 떨어진 조각에 두 번 적힌 열쇠를 두 곳과 함께 잡음, 날짜 순서 파일과 같은 값 해시)와 설정만 바꾼 갱신을 담는다.
- decided (#725 Decisions 133, 2026-11-23): `tds import csv`가 쓰는 것을 바꾸는 PR은 결과를 엔진으로 열어 값을 읽는 시험을 함께 낸다.
- decided (#725 Decisions 97, 2026-11-23): 결과의 표시는 달력의 출처를 댄다: `inferred_from_bar_dates`면 가격이 준 날짜 수, 거래소 달력과 비교하지 않았다는 것, 모든 종목에 없는 날은 알 수 없다는 것; 거래소의 것이면 기간의 세션 수와 봉이 하나도 없는 세션.
- decided (#705 Decisions 57, 2026-11-23): `close`만 가진 패키지, 어떤 파일이 한 칼럼을 모든 행에서 비워 둔 시장, 봉 날짜에서 짐작한 달력에서 나온 결과는 표시로 그렇다고 말한다.
- decided (#752 Decisions, 2026-11-26): 스냅숏의 칼럼이 바뀌었다는 `nexusbt doctor`의 알림(스펙 3.2)은 `nx.Item`을 만드는 단계와 함께 돌아온다.
- decided (#752 Decisions, 2026-11-26): 스냅숏 자기 칼럼의 틀린 이름에 대한 E7과 그 "Did you mean"(스펙 3.2, 6.6), 그리고 `test_schema_registry_injected_at_binding`이 지키던 검사는 `nx.Item`을 만들 때 돌아온다.
- decided (#752 Decisions, 2026-11-27): `nx.Item`을 읽는 쪽을 만들 때, P-FUT의 앞선 스냅숏(`tests/property/_future.py`의 `cut_after`)은 값 표를 시장마다의 워터마크에 대어 `date`로 자른다. 값 표는 공개 시각을 적지 않기 때문이다.
- carried (#43 Decisions, 2026-11-18; #752 Decisions, 2026-11-26): T-24의 `nx.Item.sector.eq(1)` 행은 `nx.Item`을 읽는 쪽이 생기면 실행기로 돌린다. 지금 `test_T24_filter_unknown`은 그 행을 커널로만 돌린다.
- decided (#725 Decisions 226, 2026-11-24): 값 표의 사용자 문서는 공급자가 이미 고쳐 낸 값에는 종류 선언이 필요 없음을 예와 함께 보인다(스펙 5.3.5).
- decided (#725 Decisions 105, 2026-11-23): 가격 기준의 사용자 쪽 이름은 TDS 5.5의 셋(`raw`, `split_adjusted`, `total_adjusted`)이다.
- decided (#705 Decisions 23, 2026-11-22; #708 Question, 2026-11-21): 엔진이 다른 엔진의 장점을 가져오고 약점을 푼다는 것이 돌려서 화면으로 보여지기 전까지는, 어떤 README나 문서도 그렇다고 말하지 않고 많아야 그렇게 설계되었다고 말한다(T2.17이 빠른 시작에 같은 것을 가진다).
- carried (#708 check table 1, 2026-11-21): 도구의 티켓들은 한 줄 명령과 Python으로 넘긴 표 두 길 모두에서 가격 파일 하나로 첫 결과까지를 세어 보인다(준비한 파일, 쓴 줄, 친 명령). 사용자는 시장, 가격 기준, 종류 세 가지를 쓴다.
- carried (#708 check table 2, 3 and 4, 2026-11-21): 가격 기준을 쓰지 않았을 때의 멈춤 화면; 가운데 하루가 빈 파일에서 그날이 `missing`으로 남고 표시되는 것; 시장 휴일이 든 자료가 오류 없이 돌고 달력의 출처가 기록되는 것을 보인다.
- carried (#708 check table 5 and 7, 2026-11-21): 분할이 있는 종목에서 엔진이 사건으로 계산한 값; 가격만 있는 자료와 다 갖춘 자료에서 같은 계산을 하여 표시 블록이 어떻게 다른지, 무엇을 할 수 없고 무엇을 더할지를 보인다.
- carried (#708 check table 8, 2026-11-21; #725 Decisions 77): 두 가지로 읽히는 날짜 꼴, 빠진 필수 칼럼, 모르는 단위가 각각 무엇을 쓸지와 함께 도구를 멈추는 것을 보인다.
- carried (#708 check table 11, 12 and 13, 2026-11-21): 같은 입력을 세 길로 넣어도 값 해시와 의미 해시가 같다는 것; 사용자가 말하지 않은 값은 모두 도구가 정한 것 목록에 있고 말한 값은 없다는 것; 가격 파일의 코드에서 만든 종목이 `listed_on` = 첫 봉, `listed_on_censored = true`를 갖고 `last_session`도 상장폐지도 없으며 `lot_size`가 비어 있다는 것(T3.4)을 보인다.
- carried (#708 check table 15, 2026-11-22; #705 Decisions 48): 종목 코드, 날짜, `close`만 든 지어낸 파일을 이 엔진과 다른 엔진에 같은 식으로 넣고, 각각이 무엇을 받고, 거절하고, 할 수 없다고 말하는지 적는다.
- carried (#708 To look at in step 3, 2026-11-21): 사용자의 입력에 `cum_factor_*` 같은 조정 계수 칼럼이 있으면, 도구는 그 칼럼을 쓰지 않으며 엔진이 분할과 배당 사건으로 조정을 계산한다고 말한다.
- carried (#738 Decision, 2026-11-23): 주식 배당, 무상 증자, 감자에는 분할 파일과 배당 파일이 담지 않는 `kind`가 필요하다.
- owner decides at the cut (#738 Findings 18, 2026-11-23): 사용자가 준 배당의 발표일이 `ts_announced`를 채우는지. 비워 두면 사건은 `ts_effective`부터 알려진다(TDS 5.11).
- carried (#738 Decision, 2026-11-23): 봉 날짜에서 짐작한 달력은 마지막 봉에서 끝나므로, 그 뒤의 배당락일이나 퇴출에는 세션이 없다. 도구는 그렇다고 말한다.
- carried (#738 Decision, 2026-11-23): 가격 파일만으로 `tradability_daily`에 줄 수 있는 정직한 내용은 `status_known = false`뿐이다.

#### The next TDS revision

- decided (#705 Decisions E, K, 2026-11-21): 시장은 상장폐지 자료가 언제부터 빠짐없는지 선언한다(없으면 모름). 경고는 "끝까지 모두 살아 있는" 패키지를 이름 대고, 검사는 "몇 해 동안 퇴출이 없다가 생김"을 이름 댄다. 종목이 적으면 어느 쪽도 판정하지 않고, 짐작한 시작 해는 추정으로 보이되 선언으로 쓰지 않는다. 새 manifest 칸은 `tds_draft`를 옮긴다.
- owner decides at the cut (#752 Decisions, 2026-11-27): 종목이 `market=` 파티션과 다른 시장에 속한 값 표 행을 검사기가 판정하는지. 그러려면 `full` 단계의 새 R 코드가 필요하고, 스펙 5.3.5의 다섯 멈춤에 들지 않는다.
- owner decides at the cut (#725 Decisions 177, 2026-11-23): 봉의 `params.ready_delay`가 없을 때 0으로 읽는 것이 표준의 기본값인지. TDS 5.5는 그 키를 선택으로 두고 엔진은 0으로 읽는다(스펙 5.1.2).
- owner decides at the cut (#705 Moved from #43, 2026-11-21): 미국 일 거래량이 통합인지 주 거래소인지를 기본값 없는 `bars`의 선택 선언으로 둘지.
- owner decides at the cut (#705 Moved from #43, 2026-11-21): 패키지가 `dictionary/columns` 데이터셋을 하나 가질지 여럿 가질 수 있을지 TDS 4.4가 정할지. 지금 검사기는 어느 쪽도 거절하지 않고, 엔진은 그 종류의 모든 데이터셋에서 표시를 읽는다.
- builder's choice (#705 Moved from #43, 2026-11-21; 추천: 저장된 칼럼마다 그 칼럼 묶음의 규칙과 비교, 칼럼마다 자기 규칙으로 공개되기 때문): 한 데이터셋이 `params.availability_by_column`에 규칙 여럿을 선언할 때 무엇을 비교하는지 TDS-T002의 행이 말한다.
- carried (#705 Moved from #43, 2026-11-21): #528의 빈틈에는 티켓이 없다: 통과로 보고되는 프로필 없음(#720), `full` 단계 시간의 내역 없음, 스냅숏 사이 비교 없음, 라이선스나 출처 칸 없음. 1장의 `[unverified]` 칸은 #528의 출처와 맞대어 볼 수 있다.
- carried (#705 Moved from #43, 2026-11-21): 값 해시를 다음에 바꾸기 전에 #57의 Outcome 3~5번(#116, #120, #123; #609는 주봉의 열쇠)을 읽는다.

#### v1.x

- decided (#43 v1.x follow-ups, 2026-11-01, from #30): 한국 신용 이자는 윤년에 366일 분모를 기간별로 쓴다.
- decided (#43 v1.x follow-ups, 2026-11-01, from #30): 미국 대주 수수료는 담보의 102%를 달러 단위로 올려 360일 해로 매긴다. 시장 전체의 1차 출처는 아직 찾아야 한다.
- decided (#43 v1.x follow-ups, 2026-11-01, from #32): 한국 팩은 세금마다 10원 아래를 버리고(`[rounding] tax`, `unit = 10`), 그 행은 주인이 주는 실제 증권사 체결 확인서로만 `verified = true`가 된다.
- carried (#43 v1.x follow-ups, 2026-11-01, from #30): 한국 `day_count = 365`는 주인이 쓰는 증권사의 약관을 주인이 줄 때 그것과 맞대어 본다.
- decided (#43 Decisions, 2026-11-19, #587): V31-42는 자를 때 칼럼 사이의 짝별 이동 상관, 공분산, 베타를 먼저, 다음에 시계열 순위, `argmax`/`argmin`, 선형 감쇠 평균으로 온다. `nx.ops.rolling`에는 이미 평균, 합, 표준편차, 최소, 최대, 중앙값이 있다(스펙 3.3).
- owner decides at the cut (#43 Decisions, outside review of 2026-11-03): 자료 지연 시나리오, 12.1 V31-65 `info_lag1`(메모의 이름: `exec_lag1`). 두 이름이 같은 시나리오인지는 그 티켓을 자를 때 확인한다.
- carried (#43 Decisions, 2026-11-20, #253): 분위수 손계산은 V31-58의 것이고, T7.V 전에 하기를 추천한다.

#### Other

- owner decides at the cut (#752 Decisions, 2026-11-25): `test(golden):` PR이 T-07과 T-15의 골든 입력에서 `cum_factor_split`을 뺄지. T-15의 입력은 패키지의 낡은 칼럼이 결과를 바꾸지 않음을 보인다.
- decided (#705 Decisions 33, 2026-11-22): 생성기의 봉을 기록의 누적 곱으로 나누면 사건 전의 경로와 1e-12 안에서 같음을 US와 ZZ에서 지키는 시험을 둔다. KR은 가격 제한과 거래 정지가 봉을 스스로 움직이므로 아니다.
- carried (#705 Decisions 51, 2026-11-22; #725 Decisions 182): 엔진의 `Price`는 `equity` 행만 읽는데 TDS는 `etf` 행의 OHLCV도 요구한다. #745가 B3의 엔진 쪽과 함께 만든다.
- builder's choice (#705 Not sure yet, 2026-11-22; 추천: 생성기가 그런 사건을 고치게 될 때만 다시 봄, 그 전에는 일어날 수 없기 때문): 생성기가 종목의 마지막 봉 뒤 날짜의 사건을 고치면 `_recut`이 해석기가 적용하지 않는 단계를 적는다.
- carried (#43 Decisions, 2026-11-05, #300): 생성기는 `tradability_daily`를 쓰지 않는 `tiny`에 넣은 거래 정지를 거절한다(4.8 (5)). 정지가 필요한 시험은 `small`을 쓴다.
- carried (#43 Decisions, 2026-11-19, #300 and #302): 4.8이 `tradability_daily`를 `EventSpec` 데이터셋에 넣고 있는데도, 생성기는 하루 전체의 한국 거래 정지만 넣고 가격 제한 마감이나 `admin_status` 행은 `NotImplementedError`로 거절한다. 그것이 필요한 시험은 그것을 만드는 티켓을 기다린다.
- owner decides at the cut (#43 Decisions, 2026-11-19, #299): 넣은 현금 배당에 대한 4.8의 생성기 값(`record_date`, `pay_date`, `resolution_body`)을 주인의 것으로 둘지. #299의 물음에는 기록된 답이 없다.
- owner decides at the cut (#43 Decisions, 2026-11-20, #625): 9.1의 행을 고칠지 `testpaths`를 고칠지. 그 행은 `tds`가 따로 있는 일 `tds / conformance`라 하는데, `testpaths`가 `tds/tests`를 `ci / test`에서도 돌린다.
- owner decides at the cut (#43 Decisions, 2026-11-18, #513): `shift`나 창을 거쳐 읽은 가격 수준의 순위, `demean`, `winsorize`를 거절할지. 지금 #499의 검사는 "알 수 없음"을 준다(스펙 5.3.3).
- owner decides at the cut (#43 Decisions, outside review of 2026-11-03): 결과가 일봉 경로 가정에 얼마나 기대는지 더 보이는 표시(E11의 확장, 5.6.4의 "x/n fills judged on daily bars" 옆), 그리고 0장의 경쟁 엔진 표를 vectorbt, Qlib, LEAN에 맞춰 고칠지.
- carried (#43 Decisions, 2026-11-02, #94): `[data] root`에 대한 E14가 두 경우에 출처를 잘못 댄다.
- owner decides at the cut (#43 Decisions, 2026-11-04, #247 and #281): 실행 id의 정규 JSON이 코드가 쓰는 `json.dumps(sort_keys=True, separators=(",", ":"))`인지 TDS 4.5의 RFC 8785 꼴인지, 다음에 실행 id를 건드리는 티켓이 말한다(스펙 5.9).
- builder's choice (#43 Decisions, 2026-11-19, #101; 추천: 공개 입구에 감싸개 하나, 사용자의 모든 호출이 그 가운데 하나를 지나기 때문): 엔진 코드의 뜻밖의 예외를 어디서 E46 `EngineBugError`로 바꾸는지. 지금 `src/`에는 그렇게 바꾸는 곳이 없고, `bugreport`의 저장된 실행 쪽 절반은 #607이다.
- carried (#43 Decisions, 2026-11-02, #101 and #52): 스펙 6.6의 버그 묶음은 재현 명령과 manifest를 이름 댄다. 묶음의 셋째 파일 `versions.json`은 6.6을 다음에 고칠 때 이름 댄다.
- carried (#43 Decisions, 2026-11-19, #248 and #306): 설치된 배포판에 `Name`이 없으면 `seal()`이 정렬하는 패키지 표에서 `TypeError`가 난다(재현하지 않음).
- carried (#43 Decisions, 2026-11-19, #252 and #595): M1 끝에 패리티 증거 파일 `tests/parity/evidence/<date>-<sha>-all-small.json`을 `main`에서 돈 `engine / parity`로 커밋한다. PR의 실행은 그것을 올리지 않는다.
- carried (#43 Decisions, 2026-11-20, #253): `percentile_between`과 `zscore`는 zipline과 다르고(ADR 0046) 골든 손계산이 없으며, 손으로 낸 숫자의 단위 시험만 있다.
- carried (#725 Decisions 150 and 151, 2026-11-23): 3단계의 후보는 값 해시의 정규 바이트를 위한 칼럼이나 묶음 단위 인코더이며, `hash_spec`과 값은 그대로 둔다. #732의 첫 `full` 검사가 빨라진다는 말은 재기 전에 하지 않는다.
- carried (#708 To look at in step 3, 2026-11-21): `tds check --level full`의 첫 줄은 `<profile>: declared, verified to schema, not_checked`라고 읽힌다. `full`을 물었는데 `schema`를 대고, 셋째 부분은 무엇을 확인하지 않았는지도 왜인지도 대지 않는다.
- carried (#708 To look at in step 3, 2026-11-21): numpy의 "generic" timedelta 단위에 대한 `DeprecationWarning`이 `nx.run_pipeline` 한 번에 사용자 화면에 두 번 나왔다(그날 본 것, 다시 확인하지 않음).
- carried (#708 To look at in step 3, 2026-11-21; #705 Decisions 28): 전체 자료를 서버에서 만드는 날 한 번, 생성기의 기록을 `full` 프리셋 전체에 걸쳐 해석기와 맞대어 돌린다(`NEXUSBT_SYNTH_FULL=<empty folder> uv run pytest tests/unit/testing/test_synth.py -k full_record`).
- carried (#43 Decisions, 2026-11-18, #492): `shift`로 읽은 늦은 칸의 골든 사례(T-12의 주제)를 ADR 0044의 시간 계약 아래에서 사람이 손으로 확인한다. 그것을 가진 티켓은 없다.
- owner decides at the cut (#705 Moved from #43, 2026-11-21, #500): `price_factor`와 `share_factor`가 서로 역수가 아닌 사건에 걸친 `AverageDollarVolume`에 대해 스펙 5.3.3에 문장을 더할지. 지금 커널은 정의대로, 원래 값으로 계산한다.
- carried (#43 Decisions, 2026-11-19, #277 and #323): 8.2의 T-25 줄은 3.4와 골든 팩터 파일이 `decay_rate`라 부르는 것을 `decay=`로 쓰고, T-20 줄은 사례가 `params.ready_delay = PT5M`의 칼럼 공개 규칙을 쓰는데도 "a late bar (`ts_end+PT5M`)"라 한다. 8.2를 다음에 고칠 때 값은 바꾸지 않고 둘을 사례에 맞춘다.

### 10.2 생산자 쪽 티켓 (공개판에서 뺌)

이 절은 비공개 생산자의 작업 계획이라 공개판에서 뺐다. 엔진 동작과 무관하고, 엔진 M0~M6은 합성 패키지(4.8)로 끝낼 수 있다. 생산자가 채우지 않은 칼럼·데이터셋에서 엔진이 하는 일은 4.5의 대체 동작이 정한다.
