# FRD workbench

> What `DRAFTING` actually is: screen-by-screen AI chat, the preview, markers and memos, direct element edits, history and undo, state cases, and the whole-flow canvas.

Package: `com.bizplay.builder.frd` — `FrdController`, `FrdCanvasController`, `FrdScreenChatService` / `FrdScreenChatWorker`, `ScreenMockupWorker`, `FrdScreenMarkerService`, `FrdScreenHistoryService`, `FrdScreenDirectEditService`, `FrdScreenStateCaseService`
Screens: `artifacts/frd.html`, `artifacts/frd-chat.html`, `artifacts/frd-canvas*.html`, `fragments/frd-screen-dialog.html`

## The working loop

```text
1. pick a screen in the left list
2. look at the current result in the preview
3. ask for the change you need, specifically, in the AI chat panel
4. check the result — the screen and the explanation together
5. undo a bad run with 실행 되돌리기
6. save the screen's work and check the FRD's completion criteria
```

An FRD started with no screens selected works on out-of-screen implementation requirements and document scope instead. Saving runs the checker automatically and only reports back when something fails — see [Spec checker](19-checker.html).

## Screen work states

`FrdScreen.State` — independent of the FRD's own state:

| State | Label | Meaning |
|---|---|---|
| `WAITING` | 대기 | No AI draft yet. A new screen starts here; make the draft first, then work on detail |
| `GENERATING` | 초안 생성 중 | The AI is working on this screen. Other screens stay viewable; this one takes no new requests |
| `GENERATED` | 완료 | The current result is saved. Review the preview and the change list |
| `FAILED` | 실패 | Only this screen failed. Other screens and the FRD as a whole are unaffected |

## Drafting a screen — `ScreenMockupWorker`

The AI slot that produces a to-be mockup for each picked (or manually added) screen.

- Claude edits **one HTML file, directly, inside the FRD's own worktree**. The full resulting HTML is **not** returned in the response.
- Write permission is narrowed to a single path: `Edit(/<target>/<screen>.html)`.
- DB bookkeeping (`ScreenMockupService`) is separated from executor submission (`ScreenMockupWorker`); the reservation is taken under the same lock that guards completion start, then processed on the AI executor.
- `ScreenMockupBatchWorker` handles "draft them all", tracked as a `adk_builder_screen_draft_batch` with per-screen items — see [Notifications](20-notification.html).

> ⚠ Writing `pages/<screenId>.html` **inside the worktree branch is allowed and expected**. The prohibition is on merging that to the default branch, where `pages/` must stay as-is (fact). See [FRD completion](08-frd-completion.html).

## Per-screen chat — `FrdScreenChatWorker`

The chat answers questions about the selected screen, modifies it, or creates a new screen. Messages cap at 4,000 characters. One AI edit runs at a time per FRD (`FrdScreenChatService`).

Routing is decided by the **user's last message**, not by which button was pressed (`isDesignRequest`, `isWordingRequest`, `isGapRequest`, `isStateGapRequest`) — so typing the same sentence takes the same path as the menu item.

### The `AI 제안` menu

**Only items that produce an outcome are listed** (decision, 2026-09-10). Pressing one must change the screen or give something to choose. Items that only return a review comment are not listed — the planner then has to turn that comment back into a request, and that request was measured getting stuck: *"review the design rules"* → *"you are following the rules"* → *"fix what you pointed out"* → *"I did not say anything was a violation."* Design rules are read on every edit anyway.

| Item | Outcome |
|---|---|
| 디자인 시안 비교 | Two design proposals plus an apply button (`docs/frd-screen-design-proposals.md`) |
| 문구·용어 맞추기 | The screen with wording corrected against the policy/terminology documents, plus a `before → after (basis)` list |
| 요건 대비 누락 점검 | The screen with missing inputs, display items and buttons added, plus `missing: requirement N — what was added`; asks only about things that need a decision |
| 빠진 상태 화면 찾기 | Candidate state screens (empty list, error, no permission, done) with name, trigger condition and handling pre-filled, plus a `이 상태 만들기` button |

**Wording alignment** uses the policy and standard-terminology documents registered in the `정책·표준용어` menu. With none registered, the AI is not run at all and the user is told to register them. That context is reloaded even on resumed sessions (other requests load it only on a new session). Words with the same meaning but different spelling are corrected; words whose business meaning would change, and anything without a basis, are left as `확인 필요`.

**Gap check** uses the same material as the AI draft: the requirement text (`requirement.md`) and the screens linked to it.

### Design proposals and review

- `FrdScreenDesigns` / `design-proposal.md` produce the two-proposal comparison.
- `FrdDesignCritic` judges whether a result can be shown, by **reading the actual original and the proposal captures** — it deliberately does *not* reuse the generating conversation. Failures that are worth retrying get a bounded number of rounds; a timeout is not one of them.
- `FrdScreenVisualReview` gives the model a local tool to look at *only the current screen* while a request is in flight.
- `FrdChatReferenceImageService` accepts a reference image attached to a message.

## Markers — `FrdScreenMarkerService`

A marker is an **execution note pinned to an element** of the screen.

| Kind | Label |
|---|---|
| `FUNCTION` | 기능 |
| `POLICY` | 정책 |
| `EXCEPTION` | 예외 |
| `PERMISSION` | 권한 |
| `QUESTION` | 확인 요청 |

Limits: selector 2,000 characters, label 300, description 4,000. Markers carry author and element-anchored position, can be reordered, and are snapshotted into `adk_builder_frd_screen_marker_history` alongside each screen-history entry.

> Since 2026-09-11, a marker description on an ordinary screen is also written into the physical screen MD and into the completed screen history's `md`. The number, coordinates and author stay in the marker tables. No new table or column; the save/auto-update contract is `docs/frd-screen-description-sync.md`.

Markers are also fed into the AI conversation, which is why their text is worth writing carefully.

## Memos

`FrdScreenMemoService` — comment-style memos per screen, preserving the author's name **as it was at the time**, the timestamp and the content, in order (`adk_builder_frd_screen_memo_comment`). Memos are for people; markers are for the AI and the development request.

## Direct element edits — `FrdScreenDirectEditService`

Change the text or a restricted set of properties of **one selected element** in the preview, without an AI run, preserving the result as a new screen version.

Deliberately narrow:

| Property | Allowed values |
|---|---|
| `padding`, `gap` | `0`, `4px`, `8px`, `12px`, `16px`, `24px`, `32px`, `40px` |
| `font-size` | `12px`, `14px`, `16px`, `17px`, `20px`, `24px`, `28px`, `32px` |
| `font-weight` | `400`, `500`, `600`, `700` |
| `color`, `background-color` | Design tokens only — `var(--token-name)` |
| Text | Up to 1,000 characters |

`__RESET__` clears a property. Colours are restricted to token references so a direct edit cannot break the design system. There is also a direct image replacement route.

## History and undo

`FrdScreenHistoryService` restores a history entry into the current worktree and screen state (`adk_builder_frd_screen_history`).

- `실행 되돌리기` steps back one AI run (`/screens/{id}/history/step`).
- `POST /{frdId}/history/{historyId}/restore` restores a specific point.
- The history preview is served through a same-origin-framed URL — see the frame-options note in [Accounts & security](03-accounts-security.html).
- Restoring also restores the marker snapshot of that point.

## State cases

A screen often needs several conditional appearances. `상태 추가` creates a **sub-screen** under the base screen — for example `검색 결과 없음`, `권한 없음`, `저장 실패` — with a state name, a trigger condition and what the screen does.

Rules:

- A state screen **cannot nest another state screen**.
- A state cannot be added to a screen the AI is currently working on.
- `FrdScreenStateCaseService` builds it via `FrdScreenDuplicationService`, so it starts from the current screen.
- `FrdScreenStateProposals` generates the candidate list for the `빠진 상태 화면 찾기` menu item.

## Version comparison

`GET …/canvas/compare` → `FrdScreenComparisonService`, rendered by `frd-canvas-compare.html`.

It picks the comparison candidates for **the same screen and the same facet** as the currently applied history entry, so a comparison never silently lines up two different institutions' variants of a screen.

⛔ **It does not restore files.** Choosing a version to look at is not choosing a version to apply — restoring is `POST /{frdId}/history/{historyId}/restore`, a separate action. Keeping the two apart is what makes it safe to browse history while work is in progress.

The compare view is one of the same-origin-framed URL patterns (`FrdCanvasController.COMPARE_URL_PATTERN`) — see [accounts & security](03-accounts-security.html).

## The canvas

`FrdCanvasController` + `FrdCanvasService` draw the **whole-flow map** for an FRD: screens plus the navigation relationships between them.

Relationships are read from the screen MD's movement fields — `이동`, `이동modal`, `이동native`, `이동cross`. From the canvas a planner can exclude a screen, delete it, promote it, duplicate it into an independent new work screen, edit relationships, and add state cases in bulk. `frd-canvas-compare.html` is the before/after comparison layer, and `frd-canvas-chat.html` is a chat scoped to the whole flow rather than one screen.

`FrdScreenIaPlacementService` records where a new screen belongs in the menu tree — see [IA](12-ia.html).

## Write admission

`FrdWriteAdmission` serialises **completion start against user writes** on one server.

- `FrdWriteInterceptor` is registered on `/projects/**` and refuses writes while completion holds the FRD, with: *"FRD 완료 작업을 처리하고 있습니다. 진행 상태를 확인한 뒤 다시 수정해 주세요."*
- While an AI run is in flight it keeps a **reservation**, not a lock, so ordinary reads and other screens are unaffected.

## Related

- [FRD completion](08-frd-completion.html) — what `FRD 작업 완료` checks and commits
- [Claude CLI runtime](05-claude-cli-runtime.html) — the runner under every chat message
- [Solution templates](13-solution-mockup.html) — the as-is screen a draft starts from
- [Spec checker](19-checker.html) — what runs on save
