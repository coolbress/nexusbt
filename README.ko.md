# NexusBT

> **매매는 이벤트처럼 정확하게, 계산은 벡터처럼 빠르게. 사용자는 블록만 끼운다.**

NexusBT는 일봉으로 주식 팩터를 연구하는 오픈소스(Apache-2.0) 백테스트·스크리닝
엔진이다. [TDS](docs/tds/tds-v1.4.ko.md) 형식의 자료 묶음을 경로로 읽고, 모든
종목·모든 날짜의 팩터를 한 번에 계산하고, 계좌는 거래일마다 사건 순서대로
흉내 낸다: 주문, 체결, 비용, 세금, 기업행동, 배당, 상장폐지, 공매도, 환율.
전략 파일 하나로 팩터 평가, 백테스트, 오늘의 스크리닝, 모의 장부가 나온다.
정본은 영어 [README.md](README.md)이고 이 파일은 번역이다.

## 상태

설계는 끝났고 코드는 아직 없다. 출시판이 없고, PyPI의 `nexusbt`는 이름만
예약해 두었다. v1은 합성 자료로 개발하고 한국·미국 실자료 검증을 통과한 뒤
게시한다. 뒤 티켓들이 이 README에 더할 명령("첫 5분", 팩터 하나 평가, 전략
하나 백테스트, 한국+미국 함께)은 아직 돌릴 코드가 없어서 넣지 않았다.

## 문서

| 읽을 것 | 무엇을 위해 |
| --- | --- |
| [START-HERE.ko.md](START-HERE.ko.md) | 어디서 시작하나, 일하는 순서, 다시 열지 않을 결정 |
| [docs/spec/engine-spec-v3.4.ko.md](docs/spec/engine-spec-v3.4.ko.md) | 엔진 명세 한국어 번역(정본은 [영어 판](docs/spec/engine-spec-v3.4.md)). **유일한 기준**: 다른 문서와 다르면 명세가 이긴다 |
| [ARCHITECTURE.ko.md](ARCHITECTURE.ko.md) | 시스템 지도: 층, 예정된 코드 배치, 불변식 |
| [GLOSSARY.ko.md](GLOSSARY.ko.md) | 이 프로젝트의 낱말(명세가 쓰는 이름 `CONTEXT.ko.md`는 이 파일을 가리킨다) |
| [SPEC-INDEX.md](SPEC-INDEX.md) | 마일스톤과 티켓, 티켓마다 명세 절과 시험 |
| [docs/adr/](docs/adr/) | 받아들인 설계 결정 40개 |
| [docs/tds/tds-v1.4.ko.md](docs/tds/tds-v1.4.ko.md) | 입력 자료 표준과 [예시](docs/tds/tds-examples.ko.md) |
| [docs/design/prototype-results.md](docs/design/prototype-results.md) | 시제품 실측 증거 |

공개 문서는 영어가 정본이고 한국어 번역(`*.ko.md`)이 붙는다. 명세도
그렇다(명세 OI-45, 2026-10-31 개정).

## 공개와 비공개

엔진 코드, 명세, TDS, 문서, 시험은 공개다. 자료 생산자의 자료와 스냅숏,
판매사 자료로 만든 것은 이 저장소에 절대 들어오지 않는다. 시험 자료는 모두
합성 자료 생성기(명세 §4.8)에서 나온다.

## 시작하기

```bash
git clone https://github.com/coolbress/nexusbt
cd nexusbt
uv sync --locked   # 1. 의존성. CI와 같은 명령이고 lockfile을 그대로 쓴다
uv run pytest      # 2. 시험
```

## 개발하기

```bash
uv run ruff check . && uv run ruff format .   # 린트와 서식
uv run mypy .                                  # 타입
uv run pytest                                  # 시험
uv build                                       # 빌드
```

CI는 이 명령을 하나씩 따로 검사로 돌리고, 비밀 정보 검사와 CodeQL도 돌린다.
로컬에서 먼저 통과시킨다. 필수 검사 목록은 저장소의 ruleset이 정하므로 여기
되풀이하지 않는다.

## 출시하기

버전 태그(`v0.1.0`)를 올리면
[`.github/workflows/release.yml`](.github/workflows/release.yml)이 이 패키지를
PyPI에 게시하고 GitHub Release를 만든다. 비밀번호나 토큰은 저장하지 않는다:
PyPI가 워크플로 자체를 믿는다. 첫 태그 전에 사람이 웹 브라우저에서 한 번
설정할 것이 셋 있고, 그 단계는
[`docs/how-to/publish-a-release.md`](docs/how-to/publish-a-release.md)에 쉬운
말로 적혀 있다. v1이 실자료 검증을 통과하기 전에는 태그를 올리지 않는다(상태
절 참고).

## Claude Code와 일하기

`.claude/settings.json`은 이 저장소를 Claude Code로 여는 모든 사람에게
`Beginner or non-engineer` 출력 스타일을 켠다. 에이전트는 같은 엔지니어링
일을 하고 초보 엔지니어나 비엔지니어에게 맞게 설명한다: 변경마다 무엇이
바뀌었고 왜 그렇게 했고 다음에 무엇을 보면 되는지로 끝나고, 병합·템플릿
갱신·실패에는 무엇이 그것을 보여 주고 무엇이 아직 모르는지 보고하고, 결정마다
추천 하나를 붙인다. 글은 [`.claude/output-styles/`](.claude/output-styles/)에
있다.

자기만 끄려면 Claude Code에서 `/output-style default`를 입력한다. 그러면 아래
내용이 `.claude/settings.local.json`에 적힌다. 이 파일은 본인 것이고 커밋하지
않는다. 손으로 적어도 다음 세션부터 같다:

```json
{
  "outputStyle": "default"
}
```

그 줄을 지우면 스타일이 돌아온다.

자기 `~/.claude/settings.json`에서 고른 값으로는 꺼지지 않는다. 프로젝트
설정이 그보다 앞선다.

`skillListingBudgetFraction`은 에이전트가 고를 수 있는 스킬 목록에 모델
문맥의 1% 대신 1.5%를 준다. 문맥이 200k 토큰인 모델에서 1%로는 스킬 설명
몇 개가 이름 정도로 줄어 에이전트가 언제 써야 할지 알 수 없었다. 1.5%에서는
줄어든 것이 없었고 목록은 세션마다 약 200토큰 늘었다. 1M 모델에서는 바뀐
것이 없었다.

## 기여하기

[`CONTRIBUTING.md`](CONTRIBUTING.md), 특히 시험 정책. `main`은 보호되어 있고,
변경은 검사가 모두 통과한 pull request로 들어온다.

## 라이선스

[Apache-2.0](LICENSE).

## 이 저장소에 대해

[`coolbress/plinth-template`](https://github.com/coolbress/plinth-template)에서
만들었다. CI 검사는 [`coolbress/plinth`](https://github.com/coolbress/plinth)에서
온다.

## 첫날

- 병합이 CodeQL에 막혀 있으면 한 번 더 push한다: `git commit --allow-empty -m 'ci: trigger code scanning' && git push`.
- 평소 쓰는 gh 토큰이 저장소를 골라 쓰는 fine-grained 토큰이면 `nexusbt`를 더한다: https://github.com/settings/personal-access-tokens
- Dependabot은 첫 순간부터 pull request를 연다: 필수 검사가 모두 통과하면 병합하고, 아니면 닫는다. CodeQL은 Dependabot이 올린 head를 분석하지 않는다. 거기에는 `ci / deps`와 시험이 돌고, `main`은 병합 뒤에 분석된다. 첫 Dependabot PR은 보통 문이 CodeQL을 기다리는 사이에 들어오므로 문 자신의 pull request는 #2가 된다. "Update branch" 뒤 1~2분은 새 head에서 필수 검사와 CodeQL이 도는 동안 병합이 막히고, 그때 병합하면 "the base branch policy prohibits the merge"로 거절된다. 승인을 더하지 말고 상태가 clean이 될 때까지 기다린다. 본인이 직접 한 브랜치 갱신에는 승인이 필요 없었다.

[plinth](https://github.com/coolbress/plinth)로 만들었다.
