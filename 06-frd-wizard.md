# FRD wizard

> The three steps that turn a typed requirement into a confirmed development scope: direct input, AI interview, scope review. This is where an FRD is born and where the worktree is created.

Package: `com.bizplay.builder.frd` — `FrdWizardController`, `FrdInterviewService`, `ScreenPickService` / `ScreenPickWorker`, `FrdRunSpace`
Screens: `templates/artifacts/frd-wizard.html`, routes under `/projects/{projectId}/artifacts/frds`
Canonical design: `docs/frd-requirement-interview-design.md`, `docs/superpowers/specs/2026-08-18-frd-fast-track-design.md`

## The unit of work

```text
FRD 1 = one work item = one git worktree = one person
```

An FRD is **independent**. It does **not** hold a foreign key to any upstream artifact — it copies the input text into its own `source_text`.

`Frd.SourceKind` has four values, and **two of them are live**:

| Value | Status |
|---|---|
| `PASTED` | An FRD a planner created through the wizard — the normal case |
| `SRT` | A **bridge FRD**, created automatically so an SRT can travel on the FRD machinery. It never appears in the UI and is born at `SCOPE_REVIEW`. See [SRT fast track](09-srt.html) |
| `REQUIREMENT`, `BRD` | Read only, for old data from the retired chain |

⚠ **Not every row in `adk_builder_frd` is FRD work a planner did.** A query that counts FRDs without filtering `source_kind` also counts every SRT's hidden bridge.

⭐ Why a copy rather than an FK: the upstream chain (received document → REQ → RD → BRD) was retired, so there may be nothing to point at. An FRD created by pasting text has no upstream row at all.

## The three steps are inside one wizard

```text
FRD 작업하기 ─┬ step 1  요구사항 직접 입력   (enter the requirement directly)
              ├ step 2  AI 인터뷰            (AI interview)
              └ step 3  개발 범위 확인        (confirm the development scope)
```

⛔ **Do not draw these as siblings of the workbench and the DR.** They are the inside of the wizard. The canonical definition is `FrdWizardController` plus the three progress markers in `frd-wizard.html`. The reason the left menu does not list them is that they live inside the wizard, not that they were removed.

## States

`Frd.State` — eight values:

| State | Screen label | What Builder is doing | What the user does |
|---|---|---|---|
| `ANALYZING` | 요구사항 분석 중 | Investigating the requirement and the planning repository; preparing the next question or the result | Wait. Closing the browser does not stop it |
| `WAITING_ANSWER` | 답변 필요 | The AI run has ended; the question and the transcript so far are saved | Answer, or finish the analysis with what is there |
| `ANALYSIS_FAILED` | 분석 오류 | The failure reason is recorded and auto-progress has stopped | Read the message and press `다시 분석하기`. If it repeats, check the Claude connection and the server log |
| `PICKED` | 분석 결과 확인 | Showing the interview result, the target screens, the out-of-screen scope and completion criteria | Confirm, or `다시 인터뷰하기` to fill gaps |
| `SCOPE_REVIEW` | 개발 범위 확인 | Showing the confirmed analysis as the work scope. **No worktree yet** | `FRD 작업하기`, or `개발요청서 바로 만들기` for qualifying backend-only work |
| `DRAFTING` | 수정 중 | Editing screens and documents in the FRD's own worktree, saving history | Review the result, finish the edits, request completion |
| `REVIEW` | — | Completion is running / prepared | — |
| `DONE` | 완료 | The DR content is fixed and the FRD opens read-only | Review the development request |

## Step 1 — enter the requirement directly

The user writes, in business language, what should be built or changed, and selects what it applies to (the facet axis, if the project has one).

**Selecting a screen is optional.** Backend, permission, batch and policy work with no screen at all starts the same way and runs in the same FRD and worktree.

A good input names the actor, the purpose, the starting condition and the expected outcome:

```text
경비 담당자가 법인카드 사용 내역을 확인할 때 미제출 영수증만 모아 보고,
선택한 직원에게 제출 요청을 보낼 수 있어야 한다.
```

## Step 2 — the AI interview

This is **not** one-shot analysis producing screen candidates. It is an interview: the AI investigates the evidence, asks **one question at a time** about judgements it cannot ground, and only then fixes a result.

```text
requirement entered
  → AI investigates
  → is there a judgement that needs an answer?
      ├─ yes: one question → user answers → AI keeps investigating
      └─ no : write up the analysis result
  → the user checks the front/back scope and the screens
  → confirm the analysis
```

The AI asks when it lacks the evidence to be confident about:

- whether this changes an existing screen or adds a new one
- whether the screen change needs API, batch, permission or data changes with it
- whether this is operating an existing feature or new development
- which of several systems the scope reaches
- conditions that affect the completion criteria — errors, permissions, retention periods

Default maximum **five** questions, one at a time. The user can end the interview at any point with `현재 내용으로 범위 정리`.

### Why turn-based execution, not a long-lived process

The first implementation chose **one Claude run per turn** rather than a bidirectional process held open:

1. The AI investigates the requirement and the planning repository.
2. If it needs an answer, it returns **one question as structured JSON** instead of a final result, and the run ends.
3. The server saves the question and the investigation summary, and moves the FRD to `WAITING_ANSWER`.
4. The user answers; the answer is saved and the next run starts.
5. The next run receives the original requirement plus every question and answer so far.
6. When there are no questions left, the analysis result is saved and the FRD moves to `PICKED`.

This survives a closed browser and a server restart. **While waiting for a human, no Claude process, no credential file and no account lock is held.**

> ⚠ **Revised 2026-08-19.** Measurement showed 220 of 350 seconds per run were exploration, and every one-line answer paid that 220 seconds again. Successful runs now remember their session and continue with `--resume` (`FrdRunSpace`). Continuation runs send only a short instruction and do **not** reload the policy/terminology blocks or the codebase MCP. Sessions from runs the reader rejected are not remembered (2026-09-10). The canonical description is the comment in `ScreenPickWorker`.

### Screen picking

`ScreenPickWorker` reads the requirement and picks **the screens in this business that must change**.

- ★ It is a **separate bean** from `ScreenPickService`. ⛔ Putting it inside the service would make the call self-invoking, skip the Spring proxy, and stop `@Async` from firing at all.
- It is **read-only**: `claude` takes the cloned planning repository as its working directory and reads the index and screen documents without modifying them.
- ⛔ **Pasted source text is never inlined into the instruction** (2026-08-18 review). `source_text` has no length limit, so "it is short enough to fit" was unfounded: inlining can exceed the Windows argv limit (~32 KB), and imperative sentences inside the pasted text get a place to be read as instructions. The text is written to a run-only file and the instruction carries only its path.
- `ScreenPickService` is **the DB half**. ⛔ No process-spawning code goes in it.

Prompt fragments live under `src/main/resources/claude/prompts/screen-pick/`, with `mode-grep/` and `mode-mcp/` variants depending on whether `codebase-memory-mcp` is configured.

### What the interview records

| Table | Content |
|---|---|
| `adk_builder_frd_interview_message` | The ordered conversation — AI questions and analysis summaries, user answers |
| `adk_builder_frd_screen` | Screens to change — existing and new together |
| `adk_builder_frd_backend_change` | Per API / data / permission / batch / notification: needs change, or confirmed no change |
| `adk_builder_frd_analysis_note` | Completion criteria and items needing confirmation |

`FrdInterviewService` saves questions, answers and the final result **as one state transition**. `FrdInterviewRecovery` repairs runs that died mid-flight.

## Step 3 — confirm the development scope

`SCOPE_REVIEW` shows the confirmed analysis as the work scope: which screens change, what is implemented outside a screen, the completion criteria, and what is excluded. If something is missing or a screen is wrong, the user goes back and fills the gap.

**No worktree exists yet.** `다시 인터뷰하기` re-scopes without creating one.

Two exits:

### `FRD 작업하기` — the normal path

Pressing it is the **first write**, so this is where the worktree is created.

| Item | Rule |
|---|---|
| Branch | `frd/{FRD DB id}` — e.g. `frd/0000025` |
| Folder | `{worktreeRoot(projectId)}/frd-{FRD DB id}` |
| Cut from | The project clone's `HEAD` at the moment the button is pressed |
| Owner | The FRD's `owner_account_id` |

The **DB id**, not the display number `FRD-025`, is used — the display number is for humans; the DB id is the recovery key that recomputes the URL, the branch and the folder to the same values.

Creation contract:

1. Verify the FRD is in `SCOPE_REVIEW`.
2. Verify the clone and the default branch are healthy.
3. Handle only one creation request per FRD at a time.
4. Create the branch and worktree if they do not exist.
5. **Reuse** them if the same pair already exists.
6. Only after the worktree is confirmed, move the FRD to `DRAFTING`.
7. On failure, leave the FRD in `SCOPE_REVIEW` and tell the user why and what to retry.

⭐ Git file operations and a DB state change cannot be one transaction, hence the order **worktree first, state second**. If the state change fails after a *new* worktree was created, only that empty worktree is cleaned up. An existing worktree is never auto-deleted — it may contain the user's work.

Reopening a `DRAFTING` FRD reuses the same worktree; the branch and folder are recomputed from the DB id after any restart. If the branch exists without a worktree, the worktree is re-attached. If the folder is not registered with git or points at a different branch, Builder **reports that recovery is needed** rather than overwriting or deleting.

### `개발요청서 바로 만들기` — backend-only fast track

Shown **only** when no screen is selected and there are no open questions. It skips the workbench and the screen worktree, but the entered requirement and the AI's analysis evidence still go into the development request.

> **Revised 2026-09-02.** Fast track (`FAST_TRACK`) is now **backend-only changes, and nothing else**. The old "simple change to one existing screen" fast track was replaced by the **SRT** menu outside the FRD flow — see [SRT fast track](09-srt.html).

## Related

- [FRD workbench](07-frd-workbench.html) — what `DRAFTING` actually looks like
- [FRD completion](08-frd-completion.html) — what `FRD 작업 완료` does
- [Claude CLI runtime](05-claude-cli-runtime.html) — how each interview turn is executed
- [Solution templates](13-solution-mockup.html) — the screens the interview picks from
