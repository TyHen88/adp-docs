# Large repositories & performance

> What Builder does to stay safe and fast on a big planning repository, which limits actually exist in the code today, and — kept strictly separate — which improvements are still only proposed.

Canonical design: `docs/superpowers/specs/2026-09-12-large-repository-workspace-overview.md` (plus its verification, the screen-identifier review, the SERP performance reviews, and the delivery recheck — six documents in all)

> ⚠ **Read the split in this page before quoting any number from it.** The design document is a **staged proposal**, not a description of a finished system: *"이번 문서 변경은 수정 계획 수립이며, 운영 적용은 단계별 검증 결과를 확인한 뒤 진행한다."* Sections 1–3 below are measured from the code as it is. Section 4 is what has **not** been done.

## The problem

Several planners work independently on one large planning repository. Each FRD needs an isolated workspace, every completion needs a durable snapshot it can recover from, and none of that may cost so much memory, disk or waiting time that the product becomes unusable.

⛔ **The scope is the planning repository the extractor produced.** Builder is not being extended to read or extract the whole SERP production source. That boundary is restated in the design because performance pressure is exactly the argument someone would use to cross it.

⚠ **The real size and bottlenecks of the SERP planning repository have not been measured.** Every number below is a limit in the code, not an observation of production.

## 1. What the code does today

### Git-level economy

| Mechanism | Where | Effect |
|---|---|---|
| `fetch --no-tags` | `FrdCompletionMergeWorkspace:160` | Skips tag refs when pulling the latest into the merge candidate |
| `fetch --depth=1 --no-tags` | `FrdCompletionMergeWorkspace:517` | The final-file copy takes one commit deep, not the history |
| Worktrees share objects with the clone | `FrdWorkspace`, `CheckerWorkspace` | A new FRD workspace does not re-download the repository — the 148 MB is fetched once |
| `--detach` for check workspaces | `CheckerWorkspace` | Read-and-discard copies create no branch |
| Sparse-checkout **detection** | `FrdCompletionMergeWorkspace:358` | Reads `core.sparseCheckout` so that **a path omitted by a partial checkout is never mistaken for a deletion** |

⭐ That last one is the subtle one. Snapshot logic compares "what is on disk" against "what git tracks". Under a sparse checkout those legitimately differ, and without the check Builder would record absent-but-tracked files as deletions and carry that into a merge.

### Size limits that really exist

| Limit | Value | Where |
|---|---|---|
| Per file in a merge workspace | **64 MiB** | `FrdCompletionMergeWorkspace.MAX_FILE_BYTES` |
| Conflict material handed to the AI | **2 MiB** | `FrdCompletionConflictResolver.MAX_BYTES` |
| Per completion run | **8 GiB** | `builder.completion.max-run-bytes` |
| Across all completion runs | **32 GiB** | `builder.completion.max-total-bytes` |
| Refuse below free disk | **1 GiB** | `builder.completion.min-free-bytes` |
| Concurrent completions / queue | **2 / 20** | `builder.completion.concurrency`, `queue-capacity` |
| Delivery archive | **512 MB** | `builder.delivery.max-archive-bytes` |
| Development result archive | 2,000 entries · 10 MB per file · 100 MB total | `DevResultArchiveValidator` |

⭐ **The conflict limit and the file-preservation limit are deliberately separate numbers.** How much text an AI can usefully be given and how much data can be safely preserved are different questions; merging them would let one constraint silently set the other.

### Budget that survives a restart

`FrdCompletionDiskBudget` writes each run's reservation **to disk**, so after a server restart the budget for waiting runs is recomputed rather than lost. Rejections log the numbers and the configuration key name while the screen shows only a per-code message — the operator gets the detail, the planner gets a sentence.

### Journal and content are stored apart

`FrdCompletionJournalStore` + `FrdCompletionFileStore` split the completion journal from the file bytes it refers to. Legacy records that inlined bodies are split on read, leaving the original JSON untouched. This is stage 1 of the design's plan, and it is **done**.

### Work that moved out of the user's wait

[FRD completion](08-frd-completion.html) publishes success after only the cheap checks — path, readability, size, binary contamination, unresolved conflict markers. HTML/JSON quality analysis and external link checking run afterwards on a background worker. `WAIT_TOTAL` and `BACKGROUND_REVIEW` are logged separately so the two can be told apart.

## 2. Contracts that performance work may not break

The design pins these down precisely because they are what an optimisation would be tempted to trade away:

- `FRD 1개 = 작업 1개 = 워크트리 1개 = 한 사람`
- Move to `DRAFTING` **only after** the workspace is confirmed
- ⛔ Never automatically shrink, regenerate or delete a worktree someone is working in
- FRD completion, development-request delivery, and applying a development result are **three different jobs**
- Completion alone never overwrites the default branch's current production screens
- Exact file contents, additions/deletions/renames, staging state and permissions are all preserved
- ⛔ If recovery finds another user's change, **do not overwrite** — keep the recovery material and the lock
- ⛔ **Never shorten the wait by skipping safety checks, recovery records or remote confirmation, and never show success early**

## 3. Measured costs

⚠ These are single-method measurements on small synthetic data, **not** FRD completion times and **not** a predicted saving.

| Spot | Measured | Note |
|---|---|---|
| `replace` rewriting files | 200 temp files × 4 KiB, **one** changed → all 200 rewritten, 575 ms | The basis for "skip writes when content and permissions are identical" |
| Full planning-repo checker run | ~0.95 s over 263 screens | Which is why [the checker](19-checker.html) can afford to run twice and diff |
| An FRD interview turn | 220 s of 350 s was exploration | Which is why resumed sessions use `--resume` — see [FRD wizard](06-frd-wizard.html) |

⛔ **The "30 seconds to apply" figure in older code comments is a past observation and must not be quoted as a current measurement.**

## 4. Proposed and **not** implemented

⚠ **Nothing in this section is built.** It is recorded so that nobody re-derives it, and so nobody cites it as behaviour.

| Stage | Proposal | Status |
|---|---|---|
| P0 | Instrument the real user wait — receipt → execution start → success recorded → screen updated, with queue time included | **Not done.** `WAIT_TOTAL` still starts when the worker begins, so **queue time is invisible** |
| P1 | Skip rewriting files whose content and permissions are unchanged | Not done |
| Stage 1 | Separate stored content from the journal | **Done** — see §1 |
| Stage 2 | Reduce the number of full clones and checkouts in merge preparation | Not done |
| — | Separate executors so completion, document AI and post-completion quality checks stop competing for one `aiExecutor` | Not done; measure queue vs execution time first |

⭐ **The stated order is instrument → optimise, not the reverse.** The design refuses to fund an optimisation before the cost it removes has been measured — and notes plainly that the server logs it examined **contained no per-stage sample of a user completion**.

## 5. Where the pressure actually shows

| Symptom | Look at |
|---|---|
| Completion is slow | Queue time is not instrumented (§4 P0). `builder.completion.concurrency` is 2 |
| Completion refused on size | The budget in §1, and `FrdCompletionDiskBudget`'s log line for the real numbers |
| Conflict resolution refused | 2 MiB conflict material cap |
| Delivery refused | 512 MB archive cap, 256 MB free-disk floor |
| Everything AI is slow for everyone | `aiExecutor` is shared — 8 threads, per-account 3. See [Claude CLI runtime](05-claude-cli-runtime.html) |

## Related

- [FRD completion](08-frd-completion.html) — the merge workspace and what moved out of the wait
- [Git layer](git.html) — fetch, locks, worktrees
- [Install & operations](21-operations.html) — every limit as a configuration key
- [Concurrent editing](27-concurrent-edit.html) — who blocks whom when several people work at once
