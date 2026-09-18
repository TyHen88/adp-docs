# Glossary

> Korean ↔ English for every domain term in the code, the UI and these documents — plus the places where the screen name and the code name deliberately differ.

## Where the screen and the code disagree

These are the ones that cost reading time. They are not leftovers to clean up.

| On screen | In code | Note |
|---|---|---|
| **그룹** / 작업그룹 (Group) | `project` — `adk_builder_project`, `ProjectService`, `/admin/projects`, `ProjectPaths` | The rename happened in the UI only; every route, table and class still says `project` |
| **FRD 작업** | `frds` menu key, `Frd`, `FrdController` | |
| **IA** | `menu-tree` menu key, `Ia*` classes | Three names for one thing: 메뉴구조도 / IA / `menu-tree` |
| **솔루션 템플릿** | `solution-mockups` menu key, `SolutionMockup*` | 목업 in older documents |
| **기능명세서** | `functional-specs` menu key, `FeatureSpec*` | |
| **정책·표준용어** | `business-language` menu key, `businesslanguage` package | |

## Core domain terms

| Korean | English | Meaning |
|---|---|---|
| 기획자 | planner | The primary user. Not a developer |
| 기획 저장소 / 기획 레포 | planning repository | Owned by the planning team, on GitLab. Builder keeps a clone |
| 산출물 | artifact | Anything Builder manages the life of. Canonical list: `docs/artifacts.md` |
| 작업 | work item | The general noun. ⛔ Not 과업 — see [Conventions](22-conventions.html) |
| 적용 구분 | facet | The institution/region axis within one project |
| 시스템 | system | Webview, back-office, … Several per project |
| 화면ID | screen ID | The planning repository's key — `wv-card-list` |
| 표준 화면ID | standard screen ID | Builder's label — `PS-WV-MRC-010-L01-S` |
| 그린존 | green zone | The five green-block menu items |
| 워크트리 | worktree | One git worktree per FRD or SRT |
| 정본 | source of truth | Which document or table wins a disagreement |
| 실측 | measured | A fact obtained by running something, not by reasoning about it |

## The work flow

| Korean | English | Page |
|---|---|---|
| FRD 작업하기 | Start FRD work | [wizard](06-frd-wizard.html) |
| 요구사항 직접 입력 | Enter the requirement directly | step 1 |
| AI 인터뷰 | AI interview | step 2 |
| 개발 범위 확인 | Confirm the development scope | step 3 |
| FRD 작업대 | FRD workbench | [workbench](07-frd-workbench.html) |
| 상태 추가 | Add a state case | |
| 실행 되돌리기 | Undo the run | |
| FRD 작업 완료 | Complete the FRD work | [completion](08-frd-completion.html) |
| 개발요청서 (DR) | Development request | [dev request](10-dev-request.html) |
| 개발요청서 바로 만들기 | Create the DR directly (backend-only fast track) | |
| 개발요청 보내기 | Send the development request | |
| 전송 전 확인 | Pre-send check | |
| 개발 결과 반영 | Apply the development result | [dev result](11-dev-result.html) |
| SRT / 빠른 개발요청 | SRT fast track | [SRT](09-srt.html) |
| as-is 재동기 | as-is resync | [dev result](11-dev-result.html) |

## States

### FRD — `Frd.State`

| Code | Screen label | English |
|---|---|---|
| `ANALYZING` | 요구사항 분석 중 | Analysing |
| `WAITING_ANSWER` | 답변 필요 | Waiting for an answer |
| `ANALYSIS_FAILED` | 분석 오류 | Analysis failed |
| `PICKED` | 분석 결과 확인 | Review the analysis |
| `SCOPE_REVIEW` | 개발 범위 확인 | Review the scope |
| `DRAFTING` | 수정 중 | Drafting |
| `REVIEW` | — | In review |
| `DONE` | 완료 | Done |

### FRD screen — `FrdScreen.State`

`WAITING` 대기 · `GENERATING` 초안 생성 중 · `GENERATED` 완료 · `FAILED` 실패

### AI run — `AiRunState`

`RUNNING` 돌고 있다 · `SUCCEEDED` 다 됐다 · `FAILED` 실패했다 · `TIMED_OUT` 시간 상한을 넘겼다 · `CANCELLED` 그만뒀다 · `CREDENTIAL_LOST` Claude 연결이 끊겼다

### Project — `ProjectState`

`RECEIVING` 받는 중 · `READY` 준비됨 · `FAILED` 실패

### Delivery / development

Delivery: `대기` waiting · `전송중` sending · `전송완료` sent · `취소` cancelled
Development: `대기` · `개발 접수` received · `개발 진행 중` in progress · `개발 완료` complete

### SRT — `Srt.AnalysisState`

`READY` · `ANALYZING` 분석 중 · `COMPLETE` 생성 대기 / 완료 · `REJECTED` 확인 필요 · `FAILED`

### Green zone

`RUNNING` 만드는 중 · `DONE` 최신 · `FAILED` 생성 실패

## Shell contract values

`shape`: `산출물` (artifact, has menu) · `관리` (admin, has menu) · `카드` (card, login family) · `꽉` (full, no menu)

Menu keys and labels (`ShellContract.ARTIFACT_NAMES`):

| Key | Label |
|---|---|
| `frds` | FRD 작업 |
| `srts` | SRT |
| `dev-requests` | 개발요청서 |
| `menu-tree` | IA |
| `design-guide` | 디자인가이드 |
| `business-language` | 정책·표준용어 |
| `solution-mockups` | 솔루션 템플릿 |
| `functional-specs` | 기능명세서 |
| `screen-designs` | 화면설계서 |
| `unit-tests` | 단위테스트 |
| `integration-tests` | 통합테스트 |
| `user-manual` | 사용자 매뉴얼 |

Keys that exist but are **not** in the menu (retired chain, still directly openable): `received-docs` 받은 문서 · `requirements` 요구사항 · `definitions` 요구사항정의서 · `brd` BRD

Admin keys: `projects` · `accounts` · `system`

## Marker kinds — `FrdScreenMarkerKind`

`FUNCTION` 기능 · `POLICY` 정책 · `EXCEPTION` 예외 · `PERMISSION` 권한 · `QUESTION` 확인 요청

## Retired vocabulary

Do not build on these. They appear in old documents and in tables kept for data compatibility.

| Term | Status |
|---|---|
| 받은 문서 / `received-docs` | Removed from the flow 2026-08-20 |
| 요구사항 `REQ-` / `requirements` | Removed from the flow 2026-08-20 |
| 요구사항정의서 `RD-` / `definitions` | Removed from the flow 2026-08-20 |
| BRD `BRD-` / `brd` | Removed from the flow 2026-08-20 |
| 요구사항 추적 매트릭스 / `matrix` | **Deleted** 2026-08-27. ⛔ Do not revive the key, the `09-matrix.html` mockup, or roadmap step 6 |
| `MOCK-` numbering | Retired 2026-08-18 — FRD has its own sequence |
| 과업 | Use 작업, except for the three quoted exceptions |

## Document markers

Used throughout the repository's Korean documents and Javadoc:

| Marker | Means |
|---|---|
| ⛔ | Do not do this. Usually because it was done and it broke something |
| ⚠ | Watch out — a real constraint or an unmeasured area |
| ⭐ | This is the point. The reason the design is shaped this way |
| ★ | An important mechanical detail |
| 확정 | Decided |
| 초안 | Draft — **nothing has been built this way yet** |
| 미결 | Open. **Do not invent an answer** |

## Related

- [Overview](00-overview.html) — where these terms sit in the product
- [Conventions](22-conventions.html) — the naming law that produces this split
