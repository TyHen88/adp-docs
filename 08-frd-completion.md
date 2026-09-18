# FRD completion

> What `FRD 작업 완료` actually does: what it checks, what it refuses to check, how it merges the latest planning repository, how it resolves conflicts with AI, and what it leaves behind for the development request.

Package: `com.bizplay.builder.frd` — `FrdCompletionRunService`, `FrdCompletionWorker`, `FrdCompletionService`, `FrdCompletionMergeWorkspace`, `FrdCompletionConflictResolver`, `FrdCompletionMergeValidator`, `FrdCompletionPreparation`
Canonical design: `docs/superpowers/specs/2026-09-09-frd-completion-progress-design.md`
Screens: `fragments/frd-completion-dialog.html`, `dev-delivery-progress.html`

## What completion is for

**FRD completion is not a development quality gate. It is the safe saving and handing over of planning content** (confirmed 2026-09-09).

| Blocks completion | Does **not** block completion |
|---|---|
| Save / read / recovery failure | Missing screen links or references |
| An unsafe real file path | HTML structure problems |
| An unresolved merge conflict | Design issues, review counts |
| | External quality-check failures |

Builder's screen-ID assignment and derived-document generation continue regardless. Final non-blocking diagnostics are pinned into the development request's `확인 사항` (items to confirm). Thresholds are never raised automatically, and tool-operations items (RATCHET, original-source hints) stay in the server log only.

## The processing window

Pressing completion opens **the same processing window the AI draft uses** — real steps and real logs, not a generic spinner, not a fake progress bar, and it does not substitute by auto-opening the comparison view. The completion buttons on `frd.html` and `frd-canvas.html` use the same window.

Only **genuinely contradictory business requirements** are asked about in that window; once answered, completion continues automatically. Git problems are never handed to the planner.

## The run

`adk_builder_frd_completion_run` + `adk_builder_frd_completion_event`, driven by `FrdCompletionRunService` (short row locks plus conditional updates) and executed by `FrdCompletionWorker`.

Routes: `POST …/completion-runs/{runId}/observed | answers | cancel | retry`.

```text
FRD 작업 완료 pressed
  → ClaudeConnectionProbe    (fail fast before a 4-minute job — FRD-029's lesson)
  → take the write lock      (FrdWriteAdmission; user writes are refused meanwhile)
  → check in-flight AI runs, required screen drafts, unsaved changes
  → fetch the latest planning repository and merge in an isolated workspace
      ├─ clean merge  → continue
      └─ conflict     → FrdCompletionConflictResolver (AI) → FrdCompletionMergeValidator
  → wait-phase checks only: path, readability, size, binary contamination,
    unresolved-conflict markers
  → publish success, make the delivery-baseline commit
  → prepare development-request material (feature definitions, test scenarios) asynchronously
  → background review continues (HTML/JSON quality, external link checks)
```

### Speed: what moved out of the wait

First speed pass, 2026-09-09. During the wait, **only** path, readability, size, binary contamination and unresolved-conflict markers are checked. HTML/JSON quality analysis and external link checking run **after** success is published, on the existing async worker.

Consequences that are part of the contract:

- The final derived-file copies and the latest baseline copies are kept until that background review finishes; originals modified afterwards are not re-checked.
- The development request records a **"priority check result not yet confirmed"** notice; when the result arrives, **only that notice** in the pre-send document is replaced. Existing confirmation items and test scenarios are preserved.
- A document that has already started delivery, or was deleted, is not modified.
- On restart or check failure the unconfirmed notice stays and **completion is not rolled back**. Automatic re-check scheduling is out of scope.
- `FRD 완료 구간 시간` logs separate `WAIT_TOTAL` from `BACKGROUND_REVIEW` so wait time and follow-up time are measured apart.

## Merging the latest planning repository

`FrdCompletionMergeWorkspace` — *isolated merge and durable original preservation. AI and the DB are not this class's responsibility.*

- Merges in a workspace separate from the FRD worktree, so a failed merge never leaves the user's working tree damaged.
- `MAX_FILE_BYTES` = 64 MB per file.
- `FrdCompletionDiskBudget` writes the reservation **to disk**, so the budget for waiting runs is recomputed correctly after a server restart. Rejections log the numbers and the configuration key name, while the screen shows only a per-code message.
- `FrdCompletionJournalStore` + `FrdCompletionFileStore` keep the journal; legacy records that inlined bodies are split first, leaving the original JSON untouched.
- If the server dies after success is published, the terminated copy is recovered from the follow-up-review queue.

### AI conflict resolution

`FrdCompletionConflictResolver` — *hands only the conflict material to a tool-less AI and accepts only the defined result. It does not modify files.*

| Property | Value |
|---|---|
| Input cap | 2 MB |
| Tools | none |
| JSON parsing | `STRICT_DUPLICATE_DETECTION` + `FAIL_ON_TRAILING_TOKENS` |

`FrdCompletionMergeValidator` then verifies the result. Minimum result validation (added 2026-09-12): an empty result, generic prose, or comments-only output is **rejected** as a correction candidate; ordinary partial HTML is accepted. Structure and design quality checks on existing screens are **not** raised to blocking.

## MD readiness

"The MD exists" and "the MD is ready" are different judgements. A document containing only marker descriptions or empty scaffolding is **not** ready.

- An existing history's HTML and MD may be reused for the completion history **only when they match the merged HTML**. Otherwise the existing file and the pre-edit history are preserved and document generation is requested again.
- Generated results fill only that same latest history; **a human-written ready document is never overwritten**.
- **Generation failure does not cancel FRD completion.**
- The readiness judgement is shared by generation, send confirmation and the checks.
- State screens and screen-less FRDs do not require a separate MD — that contract is unchanged.

## What completion does and does not commit

⛔ **Completion does not merge to-be into the default branch's `core/<system>/pages/`.** That folder holds **as-is (fact)**, and the thing that carries fact into it is development's return flow (`docs/superpowers/specs/2026-08-07-dev-feedback-design.md`). Merging would make `pages/` hold *what planning drew*, and **the next FRD would read that as as-is**.

⚠ Writing `pages/<screenId>.html` **inside the worktree branch is not forbidden** — `ScreenMockupWorker` does exactly that and the DR package takes its material from there. The one thing blocked is crossing to the default branch.

⛔ **Removing a worktree is not deleting a branch** (confirmed 2026-08-24). When work closes, **the branch stays** — it is the only evidence of what was changed and why. Old phrasing like "closing = push, delete the worktree, release the lock" survives in several places; do not add branch deletion to it.

So: **`FRD 작업 완료` does "close the work + keep the branch", and stops there.**

The worktree is kept during `REVIEW` and is not removed merely because the FRD is marked `DONE`. It is removed only after the planning-repository commit and remote push succeed, and only after confirming there are no uncommitted changes.

## Failure

On failure the work result is preserved and the cause is reported. `FrdCompletionRunService` supports `retry` and `cancel` on the run, and `FrdInterviewRecovery` / the boot sweep pick up runs abandoned by a restart.

## Related

- [FRD workbench](07-frd-workbench.html) — what is being completed
- [Development request](10-dev-request.html) — what the prepared material becomes
- [Claude CLI runtime](05-claude-cli-runtime.html) — the connection probe and run mechanics
- [Green-zone artifacts](16-green-zone.html) — the feature definitions generated during preparation
