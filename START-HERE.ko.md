# 여기서 시작

**매매는 이벤트처럼 정확하게, 계산은 벡터처럼 빠르게. 사용자는 블록만 끼운다.**

이 저장소는 주식 팩터 연구용 오픈소스(Apache-2.0) 백테스트·스크리닝 엔진 **NexusBT**를 만든다. 설계는 끝났고 코드는 아직 없다. 인계 묶음을 복사하고 나면 에이전트에게 필요한 것은 모두 이 저장소 안에 있다. 따로 찾을 메모리는 없다. 정본은 영어 [START-HERE.md](START-HERE.md)이고 이 파일은 번역이다.

## 파일 위치 (복사한 뒤)

| 무엇 | 어디 | 메모 |
|---|---|---|
| 엔진 명세 v3.4 | [docs/spec/engine-spec-v3.4.md](docs/spec/engine-spec-v3.4.md)(영어 정본) · 한국어 번역 [engine-spec-v3.4.ko.md](docs/spec/engine-spec-v3.4.ko.md) | **유일한 기준.** 공개판. 다른 문서와 다르면 명세가 이긴다 |
| 명세 검사기 | `tools/spec_lint.py`(아직 저장소에 없음: 인계 묶음에 들어 있지 않았다) | `python3 tools/spec_lint.py`(표준 라이브러리만): § 참조, 티켓 그래프, 번호. 명세를 고칠 때마다 돌린다 |
| 티켓 색인 | [SPEC-INDEX.md](SPEC-INDEX.md) | 마일스톤 → 티켓 → 명세 절 → 시험 → 막는 티켓. 티켓 본문은 명세 10.1 |
| 자료 표준 TDS v1.4 | [docs/tds/tds-v1.4.md](docs/tds/tds-v1.4.md) (+ [한국어](docs/tds/tds-v1.4.ko.md)), [예시](docs/tds/tds-examples.md) | 명세 2.3과 T0.1은 `tds/spec/tds-v1.md` 자리를 쓴다. T0.1에서 옮기고 링크를 고친다 |
| 용어집 | [GLOSSARY.md](GLOSSARY.md) (+ [한국어](GLOSSARY.ko.md)) | 이 프로젝트의 낱말. 명세가 쓰는 이름 `CONTEXT.md`·`CONTEXT.ko.md`는 이 둘을 가리키는 심볼릭 링크 |
| ADR 0001–0040 | [docs/adr/](docs/adr/) | 모두 accepted. 짧은 판은 명세 9.3 |
| 구조 | [ARCHITECTURE.md](ARCHITECTURE.md) (+ [한국어](ARCHITECTURE.ko.md)) | 한눈에 보기, 층, 코드 지도(예정), 불변식, 명세에서 찾을 곳 |
| 시제품 증거 | [docs/design/prototype-results.md](docs/design/prototype-results.md) | P5·P11 실측, 손계산 32/32, 판단 행만 계산 = 전체 계산 |
| 공개 README | [README.md](README.md) (+ [한국어](README.ko.md)) | |

`/grill-with-docs` 면담 메모는 이 저장소에 **없다**. 관리자 기계의 인계 묶음 폴더에 `$PACK/GRILL-NOTES.md`로 남고, 커밋하지 않는다.

## 먼저 읽을 것

1. 이 파일.
2. [ARCHITECTURE.md](ARCHITECTURE.md) ([한국어](ARCHITECTURE.ko.md)): 시스템 지도와 불변식.
3. [GLOSSARY.md](GLOSSARY.md) ([한국어](GLOSSARY.ko.md)): 용어집.
4. [SPEC-INDEX.md](SPEC-INDEX.md), 그다음 티켓이 적은 명세 절만.

## 일하는 순서

### (a) 저장소 만들기와 묶음 복사

1. 저장소는 **공개 + Apache-2.0**으로 만든다. plinth 기본 라이선스는 MIT이므로 붙인다:
   `/plinth:new-project <owner>/nexusbt --archetype=library --license=apache-2.0` (GitHub에서는 공개가 plinth 기본이고, `--private`를 붙여야 비공개가 된다). 이미 MIT로 만들었다면 T0.1에서 `LICENSE`를 Apache-2.0 전문으로 바꾸고 `NOTICE`를 더한다.
2. 묶음을 저장소 맨 위에 복사한다. `-n`은 plinth가 만든 파일을 덮어쓰지 않는다. 건너뛴 파일이 있으면 종료 코드가 1인데, 오류가 아니다:

   ```bash
   PACK=<인계 묶음 폴더. 사용자가 경로를 알려 준다. 저장소에는 절대 적지 않는다>
   REPO=~/nexusbt
   cd "$REPO" && git switch -c docs/handoff-pack
   (cd "$PACK" && find . -type f ! -name .DS_Store) | while read -r f; do [ -e "$REPO/$f" ] && echo "plinth already has: $f"; done
   cp -Rn "$PACK/." "$REPO/"
   rm -f "$REPO/GRILL-NOTES.md"   # 면담 메모: $PACK/GRILL-NOTES.md에서 읽고, 커밋하지 않는다
   ```

3. 반복문이 출력한 파일은 합친다. plinth의 틀은 남기고 우리 것을 더한다. plinth의 절은 지우지 않는다:
   - plinth가 이미 만들었을 수 있는 것: `README.md`, `CONTEXT.md`, `AGENTS.md`(`CLAUDE.md`가 가리킴), `CONTRIBUTING.md`, `CHANGELOG.md`, `LICENSE`, `NOTICE`, `SECURITY.md`, `.gitignore`, `.github/`, `docs/agents/`, `docs/adr/`, 그 밖의 `docs/` 폴더.
   - `README.md`: 묶음의 글(제목, 표어, Documentation까지)을 앞에 두고, plinth의 절(첫날, 빌드·시험 명령, 배지)은 뒤에 남긴다. plinth가 `README.ko.md`를 만들었다면 그것도 같은 방식으로.
   - `CONTEXT.md`: 묶음의 용어집을 넣는다. plinth가 이 파일을 관리하는 방법에 대해 적은 머리말·메모가 있으면 남긴다.
   - `docs/adr/`: plinth의 ADR 파일은 남긴다. 번호가 0001~0040과 겹치면 `git mv`로 0040 뒤 번호로 바꾼다. T0.1 수용 시험 `ls docs/adr | wc -l` = 40은 T0.1 PR에서 그 수에 맞춘다.
   - `AGENTS.md`: 두 줄을 더한다. "명세 `docs/spec/engine-spec-v3.4.md`가 유일한 기준이다. 명세에 없는 규칙은 지어내지 않는다(12장 기본값, 없으면 멈추고 묻기)"와 아래 공개 규칙.
4. 사용자 기계에만 git이 무시하는 `.hygiene-private.txt`를 만든다. 비공개 낱말(계정, 호스트, 생산자 이름, 자료 경로)을 적는다. T0.2b 위생 시험이 이 파일을 읽는다. 커밋하지 않는다.
5. `python3 tools/spec_lint.py`가 아래 숫자와 함께 PASS를 내는지 본다. PR을 연다. 이것이 T0.1의 대부분이다.

### (b) `/grill-with-docs`

질문 목록은 면담 메모 `$PACK/GRILL-NOTES.md`(로컬 인계 묶음 폴더; 커밋하지 않고 저장소에 복사하지 않는다), 용어집은 [CONTEXT.md](CONTEXT.md)다. 메모에 물을 것이 적혀 있다: 미검증 시장 규칙 씨앗(A1~A9), 달력·자료 해석(B1~B4), 엔진 추정(C1~C5). 답은 `CONTEXT.md`, ADR, 또는 명세 PR로 남긴다. 아래 결정은 다시 열지 않는다.

### (c) `/to-spec`

명세 절을 가리키는 **계획 이슈 하나**를 만든다. 명세는 고쳐 쓰지 않는다. 마일스톤 표와 끝 조건(명세 10.0), 만드는 순서(명세 9장), 명세·`SPEC-INDEX.md`·ADR 링크를 넣는다.

### (d) `/to-tickets`

[SPEC-INDEX.md](SPEC-INDEX.md)에서 이슈를 만든다. 티켓은 219개이고 마일스톤 순서(M0 → M6, 그다음 v1.x)로 만든다. 이슈 본문은 명세 10.1의 티켓 글을 그대로 옮긴다: 제목, 크기, Done means, Acceptance, Blocked by, § 절. 이슈 자체의 제목은 티켓이 무엇을 하는지 한 문장으로 쓰고, 티켓의 커밋 꼴 제목(`T6.16 ci(release): …`)은 쓰지 않는다. 티켓 id와 그 제목은 본문 `## Parent`에 둔다. 정답 티켓(`T<m>.G…`)이 그것을 쓰는 티켓보다 먼저다. `Blocked by`의 티켓 번호는 만들면서 이슈 번호로 바꾸고, 티켓 번호 → 이슈 번호 대응은 계획 이슈에 둔다.

### (e) `/implement #N`

한 세션에 티켓 하나(사이에 `/clear`). 시험을 먼저 쓴다. 티켓의 수용 시험 이름이 처음 실패해야 할 시험이다. 정답 사례는 명세 8.2(`G-NN`, `tests/golden/`), 성질 시험은 8.3, 시점 사례는 8.4. 티켓이 적은 § 절만 연다. 명세가 틀렸거나 말이 없으면 멈추고 명세 PR을 제안한다. 코드에서 정하지 않는다.

## 다시 따지지 않는 결정

명세 머리말의 "사용자 결정" 묶음(2026-10-27/28):
- 이름 NexusBT: 배포 `nexusbt`, `import nexusbt as nx`, `nexusbt.toml`, CLI `nexusbt`, 환경 변수 `NEXUSBT_*`. 검사기는 `nexusbt-tds` / `nexusbt_tds` / CLI `tds`.
- 열쇠 이름은 `instrument_id` 하나이고 `security_id` 별칭은 없다. 다른 이름은 가져올 때만 바꾼다(`rename=`, `mapping.yaml`).
- 공개 문서(TDS, README, 빠른 시작, 오류 문장, CONTEXT)는 영어 정본 + 한국어 번역이다. 2026-10-31 개정(명세 OI-45): 명세도 그렇다. 영어 명세가 `docs/spec/engine-spec-v3.4.md`에서 정본이고 한국어 번역은 `docs/spec/engine-spec-v3.4.ko.md`이다. 영어 판은 한국어 판 옆에서 장마다 쌓였다가 한 번에 명세 경로를 넘겨받았다(#6).
- v1은 합성 자료로 만들고, KR/US 실자료 검증을 통과하면 출시한다. PyPI는 이름만 예약했고 게시는 v1 때.
- zipline 대조는 프리셋 범위만(ADR-0021). 완충대는 M6 마지막 티켓(T7.1).
- 공매도는 v1에 넣고 기본은 꺼 둔다. 부호 대칭이고, `enabled = false`면 롱 전용과 비트까지 같다(P-SHORT-OFF). 대차 비용은 사용자 설정이다. 대차 가능 자료는 없다. KR 공매도 금지는 시장 규칙 팩에 둔다.
- 생산자는 내보내기 층을 두지 않는다. 스냅숏 폴더가 곧 TDS 패키지이고, 엔진은 경로로만 연결한다.
- 현금 이자는 `[account] cash_rate_bps`(기본 0). 자기자본이 0 이하가 된 슬리브는 `ruined`로 표시한다. 현금 계좌는 강제 청산이 없다(증거금 계좌는 명세 5.6.7a).
- 스냅숏 재사용은 복제를 먼저 쓰고 안 되면 하드 링크를 쓴다. 파일 신원을 확인하고, 게시 파일은 읽기 전용이다.
- Python + numpy/Numba로 만들고, Rust로 바꿔 끼울 이음새를 둔다. Rust는 Numba가 예산을 못 지킨다는 측정이 나올 때만.
- 기본값: 핀 `index+root`. 현금 계좌는 롱 증거금 대출이 없다(130/30 → E16). 동률 소금은 `sha256("nexusbt-tiebreak-v1" ‖ instrument_id)`. 대차 비용은 달력일/`day_count`로 쌓인다. 종료가치 기준은 셋. KR 끝수는 `down`.
- 주식 수를 바꾸는 기업행동은 정확한 정수비가 있어야 한다(TDS A010 = 오류). f64에서 분수를 추론하지 않는다. `decimal_ratio = "literal"`은 사용자가 골라야 쓴다.
- `size.kelly`는 v1.x. 모든 검증 방법 안의 ML 학습은 앞쪽만 쓴다.
- CPCV·walk-forward·CSCV/PBO·DSR은 v1에 넣고, 진입점은 `backtest(method=…)` 하나다. `nx.validate`는 없다. 최소 `nx.ml.factor` 블록은 v1에 넣고, pickle은 쓰지 않는다.
- 경제 사건 투자도 같은 블록으로: `Macro.series`, `Events.<kind>`, `nx.on_event`, `from_parquet(shape=)`.
- 엔진·명세·TDS는 공개한다. 비공개는 생산자의 자료뿐이다(2026-10-27).

ADR(모두 accepted. 전문은 [docs/adr/](docs/adr/), 한 줄 목록은 [START-HERE.md](START-HERE.md)의 같은 절).

## 공개 / 비공개 규칙

- **공개(Apache-2.0):** 엔진 코드, 명세, TDS(형식·스키마·검사기), 문서, 시험.
- **비공개, 이 저장소에 절대 넣지 않음:** 생산자의 자료·스냅숏과 그 일부, 공급사 자료로 만든 fixture, 생산자 경로·호스트 이름·IP 주소·계정 이름·생산자 이름·생산자 내부 티켓 번호. 시험 자료는 모두 합성 생성기(명세 4.8)로 만든다. 실자료 증거에는 요약 숫자만 담는다(명세 2.7). 위생 시험(T0.2b)이 이것을 강제한다.

## 숫자 (명세에서 스크립트로 셈, 2026-10-29)

티켓 219(M0 16, M1 40, M2 30, M3a 37, M3b 11, M4 28, M5 24, M6 31, v1.x 2) · 정답 사례 107(G-01..G-107) · 성질 시험 34 · 오류 코드 49(E1..E49) · ADR 40 · 이름 붙은 수용 시험 950 · 제목 177. 티켓·정답·성질 시험은 `python3 tools/spec_lint.py`로 다시 센다. 오류 코드와 ADR은 명세 6.6과 9.3 표의 행 수다.

## 증거는 어디에

[docs/design/prototype-results.md](docs/design/prototype-results.md): M4 16 GB 기계에서 P5는 cold p50 5.8 s / p95 6.8 s였다(관문 30 s, 목표 10 s). P11 (a)/(b)/(c)는 예산의 5분의 1 아래로 돌았다. 회계 손계산은 32/32 통과했다. 판단 행만 계산한 값은 전체 계산과 비트까지 같았다. 출력 해시는 두 기계에서 같았다. 명세 7장이 [R4H-05]~[R4H-08]로 인용한다.

## 첫 세션을 위한 메모

- `review/…`, `teardown/…`, `sources/…`, `STORY.md` 같은 대괄호 근거는 저장소 밖 설계 기록을 가리킨다. 규칙이 왜 있는지를 말할 뿐이고, 규칙 자체는 명세에 다 적혀 있다.
- 명세는 plinth 2.7.1을 말하지만, 설치된 plinth를 쓴다. GRILL-NOTES C5(공개 플래그 이름)는 답이 났다: GitHub 저장소는 `--private`를 붙이지 않으면 공개다.
- 명세 [R6-11]: 면담 메모는 저장소에 넣지 않는다. `/grill-with-docs` 동안 `$PACK/GRILL-NOTES.md`에서 읽고, 답은 `CONTEXT.md`, ADR, 명세 PR로 남긴다.
