# Concurrent editing

> Several planners work in one project at the same time. This page answers the one question the locks exist for: **who is blocked by whom, and who is merely warned.**

Canonical design: `docs/superpowers/specs/2026-08-07-concurrent-edit-design.md` — **read its retraction block first**

> ⚠ Running AI at the same time is a different subject — that is the AI execution queue, in [Claude CLI runtime](05-claude-cli-runtime.html).

## The principle: show, do not block

⛔ **Screen locking was abandoned on 2026-08-24.** Two FRDs **can** hold the same screen. When they collide, **the people resolve it**. Builder's job is to make it visible — *"FRD-027 is also holding this screen"* — not to prevent it.

⭐ **What reversed the decision was not a better argument — it was that the premises died.** The original reasoning ("a warning cannot block; if a human can press *open anyway*, it will be pressed") is still sound *in itself*. But it rested on two things that stopped being true:

| The premise it rested on | Now |
|---|---|
| "A BRD names its target screens by screen ID, and that screen ID is the locking key" | **BRD was retired.** The work unit is the FRD |
| "The mockup path contains the BRD number, so versions of one screen are separated as files" | **False.** An FRD writes `core/<system>/pages/<screenId>.html` |

There was already precedent: the new-screen-ID design does not stop two people creating the same new screen — it shows it as a second tab. "Naming cannot prevent duplication" had been settled once already.

⛔ **The design document lists, line by line, every sentence its retraction overturns** — specifically so the old rule cannot creep back in from a paragraph someone missed. If you are about to add a screen-level lock, read that list first.

⚠ **One lock survived the retraction: the menu tree (IA).** Its reasoning is different — it is a **single document**, not a set of independently editable screens.

## What is actually blocked

Everything below is per server. Builder is a single-server product.

| Lock | Scope | Who waits | Why |
|---|---|---|---|
| `ProjectRepositoryLocks` | One project's clone | Any git operation that moves the default branch | Two pushes or merges to one clone cannot interleave |
| `FrdWorkspaceLocks` | One worktree path | Work on that FRD's files | Per-FRD, so two FRDs never wait on each other |
| `FrdWriteAdmission` | One FRD | User writes, while completion holds it | *"FRD 완료 작업을 처리하고 있습니다."* |
| `ClaudeAccountLocks` | One account | The **N+1**-th concurrent `claude` for that person | Bounded, not serialised — see below |
| `WorkKey` uniqueness | One unit of work | The same work opened in a second tab | One AI run per piece of work |
| `deliveryExecutor` | Whole server | The second delivery | Core 1 / max 1, deliberately serial |
| `builder.completion.concurrency` | Whole server | The third completion | Default 2 |

## Three layers, not one

Mixing these up makes the whole picture look arbitrary. They fail differently and survive differently.

| Layer | Mechanism | Survives a restart? | Example |
|---|---|---|---|
| **JVM lock** | `ReentrantLock` in a `ConcurrentHashMap` | **No** — dies with the process | `ProjectRepositoryLocks`, `FrdWorkspaceLocks` |
| **In-process de-duplication** | A `ConcurrentHashMap.newKeySet()` of ids in flight | **No** | `SrtAnalysisService.running` — `if (!running.add(srtId)) return` |
| **Database claim** | Conditional `UPDATE`, or `SELECT … FOR UPDATE` | **Yes** — state is a row | `AiRunService`, seed part claims, `SrtService.selectByIdForUpdate` |

⭐ **The JVM locks being in-process is a design decision, not an oversight.** Builder is a one-server product, so a map of `ReentrantLock` is sufficient and far cheaper than a distributed lock. ⚠ **That assumption is load-bearing** — the moment a second instance is put behind a load balancer, every JVM-level lock on this page silently stops protecting anything, while the database claims keep working.

### Lock ordering — project, then workspace

`FrdWorkspaceLocks` states it explicitly: *"the lock order is project, then FRD."* Shared git is protected by the project key and working files by the actual worktree path.

⛔ **Never take them in the other order.** Two callers acquiring the same two locks in opposite orders is the textbook deadlock, and here it would freeze a planner's work with no error at all.

⭐ **The order is enforced, not merely documented** — taking the workspace lock while holding no project lock throws:

> `프로젝트 잠금보다 작업 잠금을 먼저 획득할 수 없습니다.`

A loud failure at development time instead of a hang in production.

The map holds the **same lock object for the life of the server**, so a lock with waiters on it is never swapped out from under them. Slow (100 ms) and long-held (1,000 ms) acquisitions are logged — contention is observable rather than guessed at.

### Per-account AI is bounded, not serialised

⭐ Changed 2026-08-26. Strict serialisation made FRD completion take N× longer for N screens, and batch mockup generation ran one at a time.

The accident the lock originally prevented — a later run overwriting the credential a earlier run refreshed — is now prevented at the source: `ClaudeCredentialRunner#persistRefreshedCredential` **re-reads the database immediately before writing**.

⚠ One residual risk remains: two processes on one account refreshing OAuth at the same instant can fail one of them, because a refresh token is single-use. That run fails visibly and the stored credential stays correct. If it happens often, set `builder.ai-account-concurrency: 1`.

## The database is the arbiter

Most "who goes first" questions are not settled by a Java lock at all, but by a **conditional update**. The pattern is everywhere:

```sql
UPDATE ... SET state = 'RUNNING', owner = ?, started_at = ?
 WHERE id = ? AND state = 'WAITING'
```

Zero rows updated means somebody else already claimed it. Examples:

| Place | Claim |
|---|---|
| `AiRunService` | Start / cancel / finish — *"the DB is the referee"* when a worker and restart-sweep overlap |
| `FrdCompletionRunService` | Short row locks plus conditional updates for the completion run's lifetime |
| `BusinessDocumentSeedService` | `seeds.begin(...)` — two people pressing seed at once, only one starts |
| Seed parts | Two workers cannot claim the same batch |
| `SrtService` | `selectByIdForUpdate` around SRT transitions |

⭐ **This is why it works across a restart.** A Java lock dies with the process; a row's state does not. That is also why boot sweeps exist — a run still marked `RUNNING` after a restart is closed as `SERVER_RESTARTED`, otherwise the "already running" guard would match forever and the project could never start another.

## What collides in files, not in locks

Two FRDs editing the same screen produce two branches that both touch `core/<system>/pages/<screenId>.html`. Nothing stops that. It is resolved later, by git, when each FRD completes:

```text
FRD-027 completes  → fetch latest → merge in an isolated workspace → conflict?
                                                                      ├─ no  → continue
                                                                      └─ yes → AI resolves,
                                                                               validator checks
```

⛔ Git problems are never handed to the planner — see [FRD completion](08-frd-completion.html). And the merge happens in a **separate workspace**, so a failed merge never damages the working tree someone has open.

⚠ The checker follows the same discipline for the same reason: ⛔ **never run a check inside the shared clone.** Two simultaneous saves would mix each other's drafts and make the before/after verdict false — see [Spec checker](19-checker.html).

## What a planner actually experiences

| Situation | What they see |
|---|---|
| Another FRD holds the same screen | A notice saying so. **They can still work** |
| Their FRD is completing | Writes refused with the completion message; progress is visible |
| They opened the same work in two tabs | The second is refused — one run per `WorkKey` |
| Their account already has 3 AI runs | The next one waits its turn |
| Someone else is delivering a request | Theirs queues behind it |
| The clone has commits the remote lacks | *"공용 사본에 원격에 없는 커밋이 있습니다"* — work preserved, administrator needed |

## Related

- [Claude CLI runtime](05-claude-cli-runtime.html) — `WorkKey`, per-account concurrency, the AI queue
- [FRD completion](08-frd-completion.html) — write admission and the isolated merge
- [Git layer](git.html) — the lock order in the git calls themselves
- [Large repositories & performance](26-large-repository.html) — the contracts optimisation may not break
