# Git

> Reference documentation — `docs/adp/`. Describes the system as built, not as planned.
> The code is the source of truth; this file points at it. Verified against the tree on 2026-09-17.

## 1. What this is

Git is not a screen. It is the layer every artifact feature stands on: the planning repository
arrives as a clone, each FRD gets its own worktree, finished work becomes a commit, and only four
places in the whole product are allowed to push.

Builder never reads the operational source system. It only ever touches **one repository per
Group** — the planning team's GitLab repository — and it touches it through exactly one Java class.

| Layer | What it is | Where |
|---|---|---|
| **Clone** | The server's copy of the planning repository, on its default branch. One per Group. | `<data-root>/projects/<id>/clone` |
| **Worktrees** | Checkouts sharing the clone's object store. One per FRD, SRT, merge or check. | `<data-root>/projects/<id>/worktrees/…` |
| **Refs** | Branches (`frd/…`, `srt/…`) and Builder's private refs (`refs/builder/…`) | inside the clone |
| **Remote** | GitLab. Reached only via a token-bearing URL, never a configured remote. | — |

**There is no configured `origin` in any of this.** Every `fetch` and `push` passes a full
authenticated URL as an argument. That is deliberate — see §3.

## 2. One runner: `GitCommand`

Every git process in the product starts in `git/GitCommand.java`. Sixteen classes call it; none of
them build a `ProcessBuilder` of their own.

```java
GitResult run(Path workingDir, Duration timeout, String... args)
GitResult runIsolated(Path workingDir, Duration timeout, String... args)   // §2.2
```

`GitResult` is `record(int exitCode, String stdout, String stderr)` with `succeeded()` meaning
`exitCode == 0`.

**A non-zero exit is not an exception.** It is a value the caller inspects. This matters because
several callers depend on *which* non-zero code came back: `git diff --cached --quiet` returns `1`
for "there are staged changes" and that is the success path, while anything other than `0` or `1`
is a real failure. `FrdWorkspace.commitChanges` and `IaPublisher` both branch on exactly this.

`GitException` is thrown for only three things: git could not be started, git exceeded its timeout,
or the waiting thread was interrupted.

### 2.1 Every invocation gets `-c credential.helper=`

`GitCommand.command(...)` prepends it to every single git call, no exceptions.

```text
git -c credential.helper= <args…>
```

**This was a real outage, not a precaution.** Windows git defaults to `credential.helper=manager`.
Because Builder puts the token in the URL, the helper has nothing to do — but git still runs
`git credential-manager store` *after authenticating successfully*, to save the token. When that
subprocess died it took the **already-successful clone** down with it as exit code 128. `GIT_TRACE`
caught the last line:

```text
trace: run_command: 'git credential-manager store'    ← ends here, exit 128
```

There is a second reason not to revert it: with the helper on, the planning repository's token is
**silently written into the server's credential store**. Nobody asked for that, and it contradicts
the point of sealing the token into the database.

Two traps in one line:

- **The empty value is the mechanism.** `-c credential.helper=` is git's documented way to clear
  every previously configured helper.
- **Do not name one.** `-c credential.helper=none` means "go find a helper called `none`", which
  fails harder than doing nothing.

`GIT_TERMINAL_PROMPT=0` is set on every invocation for the same family of reasons. There is no human
at the server. A git that decides to ask a question would hang until its timeout — 30 minutes in the
clone's case. Failing immediately is the only useful behaviour.

### 2.2 `runIsolated` — no ambient configuration

Used where a server-built candidate repository must not inherit anything from the machine it runs
on: `IaPublisher`, `FrdWorkspace`'s prepared-commit path, `FrdCompletionMergeWorkspace`.

| Variable | Value | Why |
|---|---|---|
| every `GIT_*` from the parent | *removed* | The parent process may carry a `GIT_DIR` or `GIT_WORK_TREE` that silently retargets the command |
| `GIT_CONFIG_NOSYSTEM` | `1` | ignore `/etc/gitconfig` |
| `GIT_CONFIG_GLOBAL` | `/dev/null`, or `NUL` on Windows | ignore `~/.gitconfig` |
| `GIT_CONFIG_SYSTEM` | same | belt and braces |
| `GIT_OPTIONAL_LOCKS` | `0` | a read must not take `index.lock` |

Callers that commit through an isolated path also pin the rest by hand: `core.hooksPath` to an empty
directory, `core.fsmonitor=false`, `core.autocrlf=false`, `commit.gpgsign=false`, and an explicit
identity.

### 2.3 Both output streams are drained concurrently

Each of stdout and stderr gets its own daemon thread (`StreamPump`) started **before** the wait.

Reading them one after the other breaks two things at once:

1. Reading to EOF blocks until the process ends, so the subsequent `waitFor(timeout)` always
   observes an already-finished process — **the timeout stops doing anything at all.** An earlier
   implementation had exactly this bug.
2. While stdout is being drained, the stderr pipe fills and both sides wait for each other — a
   deadlock. `git clone` writes its progress to stderr, so this is not theoretical.

The threads are daemons so a killed child's pump cannot hold the server open, and `text()` joins with
a 5-second cap rather than waiting forever.

### 2.4 A timeout kills the whole process tree

`destroyForcibly()` on the returned `Process` kills only the direct child. `git clone` and
`git fetch` spawn grandchildren — `git-remote-https`, and on Windows the `conhost.exe` that wraps a
console app. A surviving grandchild keeps file handles open on the working directory, and on Windows
an open handle makes deletion **fail**, not merely warn. That is what stopped JUnit `@TempDir`
cleanup from working.

The order is fixed and matters:

1. **Collect the descendants first.** `Process.descendants()` walks the live tree; kill the parent
   first and the OS reaps the tree before you can enumerate it.
2. Kill descendants, then the parent.
3. Wait on `onExit()` for all of them — capped at 5 seconds, best-effort.
4. **Then sleep a further fixed 50 ms.** Measured repeatedly on 2026-08-15: deleting immediately
   after `onExit()` still failed with "in use by another process" roughly half the time. The OS
   reports the exit before the process releases its directory handles, a gap of tens of
   milliseconds. The grace is bounded and taken once — it is not a retry loop.

## 3. A token must never be visible

| Mechanism | What it does |
|---|---|
| `authenticatedUrl(repoUrl, token)` | builds `https://oauth2:<url-encoded token>@host/path` |
| `GitCommand.mask(text)` | rewrites `://anything@` to `://***@` |
| `GitException(message)` | **masks in its own constructor** — a caller cannot forget |
| `StreamPump` on error | sets the captured text to `""` and logs nothing; credentials can be in it |
| `DevRequestBranchMerger` catch-all | wraps the message in `GitCommand.mask(...)` before returning it to the screen |

`GitCommandTest` pins three of these directly: *the token is embedded in the URL*, *masking hides the
token*, and *the token does not survive into the exception message*.

## 4. Timeouts actually in use

| Operation | Timeout | Where it comes from |
|---|---|---|
| `git ls-remote` reachability probe | 20 s | hardcoded in `RepoProbe` |
| Initial clone | 30 min | `CloneWorker.CLONE_TIMEOUT` |
| Nearly everything else | `builder.check-timeout` — **2 m** by default | `BuilderProperties.checkTimeout()` |
| IA publish, ordinary steps | 2 m | `IaPublisher.GIT_TIMEOUT` |
| IA publish, `push` and candidate `clone` | 10 min | `IaPublisher.PUSH_TIMEOUT` |
| Dev-result apply, `push` | 10 min | hardcoded in `DevResultApplyWorker` |

`check-timeout` is generous for a git call because it is shared with the planning-repository checker,
whose first run includes an `npm install`. **It deliberately does not inherit the clone's 30
minutes.**

## 5. What ends up on disk

```text
<data-root>/
  probe/                                        RepoProbe's working directory
  projects/<projectId>/
    clone/                                      the one real repository; every worktree's object store
    worktrees/
      frd-<frdId>/                              one FRD's persistent workspace   (branch frd/<frdId>)
      srt-<srtId>/                              an SRT's workspace               (branch srt/<srtId>)
      dev-request-merge-<requestId>/            detached; deleted in a finally block
      check/                                    detached; read-and-discard
      ia-publish-<sha256>/                      IA publish candidate + commit.txt receipt
    received/                                   uploaded documents — deliberately OUTSIDE clone/
    dev-request-attachments/
    dev-request-packages/<requestId>/DR-###.zip what was actually sent — also outside clone/
```

Every one of these paths is computed by `ProjectPaths`, which re-validates the 7-digit ID format on
the way in: a string ID (unlike the old `Long`) lets `..` or `a/b` resolve outside the root.

**Two things are outside `clone/` on purpose.** Received documents and outgoing packages are not
meant to reach the planning repository; anything inside the clone directory is something git can see.

**Worktrees share the clone's object store.** That is why a second workspace does not re-download the
repository — measured at 148 MB on the reference engagement.

## 6. Locking

Builder is a single-server product, so locks are in-process. This is a design decision, not an
oversight.

| Lock | Keyed by | Held by |
|---|---|---|
| `ProjectRepositoryLocks` | `projectId` | anything that touches the clone or the default branch |
| `FrdWorkspaceLocks` | absolute worktree path | anything that touches one FRD's files |

Both are a `ConcurrentHashMap` of `ReentrantLock`, and **the map entries are never removed** — a lock
with waiters must not be replaced by a fresh one.

**The order is project, then workspace.** `FrdWorkspaceLocks.acquire(projectId, workspace, shared)`
takes the project lock first when `shared` is true, and throws outright if a caller already holds the
workspace lock without the project lock:

```java
if (shared && lock.isHeldByCurrentThread() && !projects.isHeldByCurrentThread(projectId))
    throw new IllegalStateException("프로젝트 잠금보다 작업 잠금을 먼저 획득할 수 없습니다.");
```

`shared = false` means "this only touches one FRD's files" and skips the project lock — that is what
lets one person's FRD work proceed while another's runs.

**Lock timings are logged, but only when they mean something.** The workbench polls `hasChanges`
every 2 seconds and a single `git status` measured 120–190 ms on 2026-09-13, so hold time alone is
noise. Only waits ≥ 100 ms and holds ≥ 1000 ms are logged at INFO.

`ProjectRepositoryLocks.tryRun` exists for optional pre-warming: work that is worth doing if the
repository happens to be free and worth skipping if it is not.

`DevResultApplyWorker` splits the two deliberately: the AI extraction takes the **FRD** lock, and only
the merge that touches the clone takes the **project** lock. Holding the project lock for the several
minutes an AI run takes would stall every other FRD in the same Group.

## 7. Clone — how a repository arrives

Before anything is stored, `RepoProbe` runs one command:

```bash
git ls-remote --heads <authenticated-url> <branch>
```

It downloads nothing and validates URL, token and branch together. It distinguishes two failures:
*could not connect* (non-zero exit) versus *connected but the branch does not exist* (empty stdout).

Then `CloneWorker` — `@Async("cloneExecutor")`, 30-minute timeout, and emphatically **not**
`@Transactional`:

1. Short transaction: read the branch and unseal the token. **The token is unsealed before anything
   touches the disk** — the reverse order destroys the existing clone and only then discovers the
   token cannot be read.
2. Delete leftovers from the previous attempt.
3. `git clone --branch <branch> <authenticated-url> <dir>`, outside any transaction.
4. Short transaction: `markReady` or `markFailed`.

**Leftovers must be deleted first.** A clone killed at the 30-minute mark cannot clean up after
itself, and without the delete every later retry fails permanently with `destination path already
exists and is not an empty directory`.

**Deletion uses `FileTrees.deleteRecursively`, not Spring's `FileSystemUtils`.** Git marks pack files
read-only, and on Windows the Spring helper dies on them with `AccessDeniedException` — which leaves
the blocking directory in place. Unix never showed this, because deleting a file there checks the
*containing directory's* permissions.

**The failure reason always carries the exit code, and keeps the last 2000 characters rather than the
first.** An earlier version recorded only `stderr`, which in a real failure was the single line
`Cloning into '…'`. Git prints progress first and the error last. Exit 128 (git's own error) versus
143 (killed from outside) is the distinction that matters.

Full context: [Project setup](04-project-setup.html).

## 8. Updating the clone

`RepositoryUpdateWorker` refreshes in place. Five preconditions, checked in order, each with its own
message:

1. The Group is `READY`.
2. No update is already running — claimed atomically in the database, not in memory.
3. The clone directory contains `.git`.
4. `git status --porcelain` is clean.
5. `git symbolic-ref --short HEAD` equals the Group's default branch.

Then: record `HEAD` → `git fetch <url> <branch>` → `git merge --ff-only FETCH_HEAD` → record the new
`HEAD` and whether it moved.

**Fast-forward only.** Anything needing a real merge is refused and reported. The clone is a mirror,
not a place where work happens.

`PlanningRepositoryUpdater` wraps the same fast-forward for callers that need "bring the default
branch up to date, then do X, all under one lock" — FRD completion being the one that needs it.

## 9. The FRD worktree

`FrdWorkspace` is the largest git caller in the product: 26 invocations.

| | |
|---|---|
| Branch | `frd/<FRD DB id>`, e.g. `frd/0000025` — or `srt/<SRT id>` for an SRT's internal FRD |
| Directory | `<worktrees>/frd-<FRD DB id>` — or `srt-<SRT id>` |
| Branched from | the clone's `HEAD` at the moment the button is pressed |

**The DB id is used, not the display number.** `FRD-025` is for people; the DB id is the recovery key
that recomputes the same branch, directory and URL after a restart. There is no stored path column.

**Path and branch must be decided by the same code.** `ArtifactWorktreePaths` answers both
`forFrd(...)` and `branchFor(...)` from one `bridgeSrt` lookup, because a real failure on 2026-09-03
came from a workspace under `srt-` whose branch was still `frd/` — and the mismatch broke receiving.

### `ensure(projectId, frdId)`

Under the FRD lock:

1. Reject a malformed id.
2. Fail if `clone/.git` is missing.
3. If the directory exists → `verifyExisting` and **reuse it**. No second worktree is created.
4. Otherwise `git show-ref --verify --quiet refs/heads/<branch>` decides between
   `worktree add <dir> <branch>` (branch exists) and `worktree add -b <branch> <dir> HEAD`.
5. Verify the result; **roll back if verification fails**, but only the parts this call created —
   `Prepared` carries `workspaceCreated` and `branchCreated` separately for exactly that reason.

**Git work succeeds, then the database moves.** A git file operation and a DB transaction cannot be
one atomic unit, so the order is fixed: worktree confirmed → state becomes `DRAFTING`. If the state
change then fails, only a freshly created empty worktree is cleaned up. **An existing worktree is
never deleted automatically** — it may hold someone's work.

`reset` is the deliberate opposite: `verifyExisting` first (an unverified directory is never
recursively deleted), then `worktree remove --force`, then `branch -D`, then `ensure` again from the
clone's current `HEAD`.

### Reading state

| Question | Command |
|---|---|
| Is there uncommitted work? | `status --porcelain --untracked-files=all` |
| What is the base commit? | `rev-parse HEAD` |
| Is the worktree behind the clone? | `merge-base --is-ancestor <cloneHead> HEAD` |

**A missing worktree is not an error.** `isBehindClone` returns false and `syncWithCloneDetails`
returns `NO_WORKTREE` — a simple backend-only FRD legitimately has no worktree at all.

### Excluding a screen

`discardScreenFiles` **restores existing files from `HEAD` rather than deleting them.** Deleting a
file that exists in the operational baseline would be read downstream as "this screen was removed".
Only files that were never in `HEAD` — genuinely new screens — are actually deleted.

## 10. Commits Builder makes

| Message | Made by | Identity |
|---|---|---|
| `docs: <FRD label> 작업 완료` | `FrdWorkspace.completionMessage` | ambient |
| `docs: <DR label> 기능정의서 확정` | `FrdWorkspace.materializeTobeDocuments` | ambient |
| `chore: 기획 저장소 최신 반영` | `FrdWorkspace` sync merge | ambient |
| `docs: <system> IA <n>차 확정` | `IaPublisher` | `Builder <builder@localhost>` |
| `merge: <DR label> 개발 완료` | `DevRequestBranchMerger` | `빌더 개발완료 <builder@localhost>` |
| `apply: <DR label> 개발 결과 반영` | `DevResultApplyWorker` | `빌더 개발결과 <builder@localhost>` |
| `작업 보존 후보` | `FrdCompletionMergeWorkspace` (internal preservation) | `Builder <builder@localhost>` |

**The completion message is produced by one static method**, `FrdWorkspace.completionMessage(label)`,
because "undo completion" identifies Builder's own commit by matching that exact string. Two copies
of the format would make the undo silently stop finding it.

**The identity is pinned only on the isolated paths.** `FrdWorkspace.commitChanges` and the sync merge
run through plain `git.run` and therefore use whatever identity the environment supplies; the four
isolated writers pass `-c user.name` / `-c user.email` explicitly. Worth knowing before moving a call
from one helper to the other.

`commitChanges` refuses to make an empty commit: after `add -A` it runs `diff --cached --quiet` and
treats exit `0` as "there is nothing to complete", exit `1` as the success path, and anything else as
a failure to determine.

## 11. Bringing a worktree up to date

`syncWithCloneDetails` exists because of a measured failure on 2026-08-25: a worktree still carried
`manifest.json` at schema `/4` while the clone's checker had moved to `/5`, so the checker stopped at
its first gate and pre-send verification permanently reported "could not run the checker".

```text
merge-base --is-ancestor <cloneHead> HEAD ?  ──yes──▶  UP_TO_DATE
                   │ no
                   ▼
   merge-base HEAD <cloneHead>  →  diff --name-only  (what changed)
                   │
        merge --no-edit -m "chore: 기획 저장소 최신 반영" <cloneHead>
                   │
         ┌─────────┴─────────┐
      succeeds            fails
         │                   │
      MERGED        merge --abort  →  CONFLICT
```

**It runs even with uncommitted work in the tree.** Git merges around files the merge does not touch.
If they do overlap, git refuses, and Builder reads that as **the person's work wins**: abort, report
`CONFLICT`, and leave no half-merged state behind. Calling `merge --abort` when no merge started is
harmless.

`MERGED` with changed paths that touch a screen sets a **review marker** so the FRD cannot be
completed without someone looking. The marker is a file inside the git directory, located via
`git rev-parse --git-path builder-frd-latest-review` — so it travels with the worktree and is never
committed. It is cleared only when the confirmed head still equals the current clone head.

`Sync` has four values: `NO_WORKTREE`, `UP_TO_DATE`, `MERGED`, `CONFLICT`.

## 12. The completion merge workspace

`FrdCompletionMergeWorkspace` is the most defensive git code in the repository: it takes a durable,
independent copy of a worktree's state before FRD completion rewrites it, so a crash mid-completion
can be recovered.

The pieces worth knowing:

- `git clone --no-local --no-checkout` for the candidate copy, and `git init` plus a depth-1 `fetch`
  for the baseline. **The baseline deliberately keeps one commit with no history** — independent
  objects, isolated from garbage collection and from later changes to the candidate.
- A recorded fingerprint compares the **index file byte for byte**. It does not call
  `git write-tree`: that command rewrites the cache-tree into the index file, taking `index.lock` and
  changing the very bytes being measured.
- Sparse-checkout is detected (`config --bool core.sparseCheckout`) so that **a path omitted by a
  partial checkout is never mistaken for a deletion**.
- A boot-time `ApplicationReadyEvent` listener at `HIGHEST_PRECEDENCE` reclaims copies whose server
  died after a successful publish but before cleanup.
- Disk is budgeted up front (`FrdCompletionDiskBudget`); if the produced output exceeds the budget it
  is not applied to the original, and the reservation is returned even when cleanup is refused.

Its test class is the largest in the git area — 25 named guarantees, sampled in §18.

## 13. Pushes — all four of them

**Only four call sites in the entire product push.** If you are adding a fifth, that is a design
decision, not a detail.

| # | Where | What it pushes |
|---|---|---|
| 1 | `IaPublisher` | `<commit>:<defaultBranch>` — a confirmed IA revision |
| 2 | `DevRequestBranchMerger` | `HEAD:refs/heads/<defaultBranch>` — the dev-completion merge |
| 3 | `DevRequestBranchMerger.deleteRemoteFrdBranch` | `:refs/heads/<workBranch>` — deletes a merged branch |
| 4 | `DevResultApplyWorker` | `HEAD:refs/heads/<frd-or-srt branch>` — extracted dev results |

All four pass the authenticated URL as an argument and an explicit refspec. None uses a named remote.

**Ordinary FRD work is never pushed.** The FRD worktree commits and stays local until a development
request takes it further. Note also that closing a task removes the worktree but **keeps the
branch** — the branch is the only record of what changed and why.

## 14. IA publish

`IaPublisher.publish` is the most cautious of the four, because it writes to the default branch of a
repository the planning team owns, and a lost response must not produce a duplicate.

The scheme is a **receipt plus a reusable candidate directory**:

- The candidate lives at `worktrees/ia-publish-<sha256(systemCode + content)>/`. Keying on the content
  means a retry of *the same* publish finds *the same* directory.
- `commit.txt` holds the commit SHA and the candidate directory name, and is validated on read
  (40–64 hex characters, `candidate-…`) rather than trusted.
- Before committing, `refs/builder/ia-baseline` pins what the publish started from.

Guards, in order:

1. The clone must be clean and on the default branch.
2. The candidate is a `--no-local --no-checkout` clone of the clone, then fetched and
   `checkout --detach FETCH_HEAD` — publishing starts from the **remote's** current state.
3. `diff --quiet <original> FETCH_HEAD -- core/<system>/ia.md` — if the remote's IA changed, abort
   rather than overwrite.
4. After the push, verify by fetching again.
5. **A failed push is re-checked, not retried blindly.** If the remote turns out to contain the commit
   anyway, the response was simply lost and the publish is complete.
6. Finally the clone catches up with `merge --ff-only FETCH_HEAD`.

**A stale receipt is discarded, not obeyed.** If a later revision changed the remote IA after this
receipt was written, keeping it would make the same content impossible to publish ever again — so the
receipt is deleted and a fresh publish begins. That case has a test of its own.

The large candidate copy is only removed by `acknowledge(...)`, called **after** the database has
recorded success. The small receipt survives.

## 15. Dev-request delivery merge

`DevRequestBranchMerger` brings a finished FRD branch into the planning repository's default branch
once development reports completion.

```text
fetch  +refs/heads/<default>    → refs/builder/dev-request/<requestId>
       +refs/heads/<workBranch> → refs/builder/<workBranch>
   │
   ├─ finalHead already an ancestor of remoteHead ──▶ nothing to push; sync clone; done
   │
   ├─ worktree add --detach <dir> <remoteHead>
   ├─ merge --no-ff --no-edit -m "merge: <label> 개발 완료" <finalHead>
   │      └─ conflict → DevRequestMergeConflictResolver (AI) → still failing → merge --abort
   ├─ push HEAD:refs/heads/<default>
   ├─ fetch again and require BOTH finalHead and the DR's recorded base commit to be ancestors
   └─ finally: worktree remove --force · worktree prune --expire now · update-ref -d (both refs)
```

Five things here are each a fix for something that happened:

- **The generation is checked first.** If the development request has been re-sent since, the stale
  completion is not merged.
- **"Already merged" exits before pushing.** Re-pushing the same head turns a previously successful
  operation into a failure if the remote moved in the meantime.
- **Verification requires two ancestors, not one.** Both the FRD branch tip *and* the commit the
  development request actually delivered must be present — that catches a branch that was rewritten
  so the delivered commit never made it in.
- **Both temporary refs are deleted in `finally`.** Left behind, they accumulate (three were found on
  2026-09-11), pin old commits against garbage collection, and make `for-each-ref` report dead
  branches as live.
- **The conflict resolver returns `false`, never throws.** The caller's `merge --abort` is what
  restores the tree; an exception would skip it. An unresolved conflict is correctly a human's job.

## 16. Applying returned development results

`DevResultApplyWorker` takes what development sent back and pushes it onto the FRD branch.

- **The rules for reading the result are not in Builder.** The working directory is set to the
  worktree, which contains the extractor, and the prompt is one line: read those rules and follow
  them. Each engagement's clone supplies different rules.
- **The ZIP is unpacked outside the worktree.** Unpacking inside would mix implementation source into
  the commit — this is the actual defence behind "`changes/` is not a copy target".
- Test-result documents are **copied, not generated**. The AI does not write them.
- Commit is `apply: <label> 개발 결과 반영` as `빌더 개발결과`, skipped entirely when
  `diff --cached --quiet` shows nothing staged.
- Push is `HEAD:refs/heads/<branch>` with a 10-minute timeout.

## 17. Read-only worktrees

`CheckerWorkspace` takes a `worktree add --detach <worktrees>/check HEAD`. **No branch** — it is read
and discarded.

**Checks never run in the shared clone.** Every planner in a Group shares that clone; laying a
candidate file into it means two people saving at once mix each other's drafts, and the "before" state
includes someone else's work, which makes the whole diff judgement false.

Cleanup needs all three steps, learned on 2026-08-14:

```text
worktree remove --force                        may fail: not a registered worktree
worktree prune                                 registration left behind after the directory went
FileSystemUtils.deleteRecursively(workspace)   a bare directory git does not know about
```

If the server dies mid-check, a bare unregistered directory is left. Git refuses to `remove` it ("not
a worktree") and refuses to `add` over it (`already exists`) — which would permanently break saving
for that Group.

## 18. Code map

| File | Role |
|---|---|
| `git/GitCommand.java` | The only place a git process starts. Credentials, isolation, pumps, kill-tree |
| `git/GitResult.java` | `(exitCode, stdout, stderr)` |
| `git/GitException.java` | Masks the token in its constructor |
| `git/RepoProbe.java` | `ls-remote` reachability check, 20 s |
| `project/ProjectPaths.java` | Every path under `data-root`; re-validates ids |
| `project/ProjectRepositoryLocks.java` | Per-Group in-process serialization |
| `project/CloneWorker.java` | Async clone, leftover cleanup, failure description |
| `project/RepositoryUpdateWorker.java` | Fast-forward update behind five preconditions |
| `project/PlanningRepositoryUpdater.java` | "Fast-forward, then do X, under one lock" |
| `project/ArtifactWorktreePaths.java` | One decision for both path and branch (FRD vs SRT) |
| `frd/FrdWorkspace.java` | FRD worktrees, commits, sync, review marker, undo (26 git calls) |
| `frd/FrdWorkspaceLocks.java` | Workspace lock, ordered after the project lock |
| `frd/FrdCompletionMergeWorkspace.java` | Isolated preservation and recovery for completion |
| `frd/FrdCompletionConflictResolver.java` | Hands conflict material to a tool-less AI |
| `ia/IaPublisher.java` | The IA publish: candidate, receipt, push, ff-only catch-up |
| `devrequest/DevRequestBranchMerger.java` | Dev-completion merge into the default branch (21 git calls) |
| `devrequest/DevRequestMergeConflictResolver.java` | AI conflict resolution; returns false, never throws |
| `devrequest/DevResultApplyWorker.java` | Applies returned dev results and pushes the FRD branch |
| `devrequest/DevRequestPackageBuilder.java` | Reads as-is material and the originating commit |
| `checker/CheckerWorkspace.java` | Detached, branchless, read-and-discard worktree |

## 19. Guarantees covered by tests

Test method names in this project are Korean sentences stating what is guaranteed, by convention.
Translated:

**`GitCommandTest`** — the isolated environment strips the parent's git configuration and path
overrides · a real isolated git does not read global configuration · git runs and returns a result · a
failure yields a non-zero exit code · the token is embedded in the URL · masking hides the token ·
exceeding the limit kills the process and throws · the token does not survive into the exception
message · git is invoked with the credential helper disabled · the disabling value is empty, not a
name.

**`IaPublisherTest`** — a confirmed snapshot is published to the default branch as one commit · a
different file added remotely still publishes and the shared clone catches up · a failed push leaves
no commit in the shared clone and the same publish can be retried · a lost response after the remote
accepted does not create a duplicate commit · a remotely changed IA is not overwritten · a history
that diverged from an existing local-only commit is preserved and the update stops · re-confirming the
same content as a previous revision is not bound to the old receipt.

**`CloneWorkerTest`** — a successful clone becomes Ready · a failure records the state and the reason ·
an exit code survives even when git says nothing · a long reason keeps the tail, not the head ·
retrying returns to Receiving · a rejected numbering submission does not turn an already-successful
clone into a failure · each project clones to its own place · a malformed id creates no path · a
failure commits even when the token cannot be unsealed · a read-only file does not prevent wiping the
clone directory · nothing to delete does nothing.

**`ArtifactWorktreePathsTest`** — a plain FRD uses the `frd-` path and the `frd/` branch · an SRT's
internal FRD uses `srt-` and `srt/` · another project's SRT is excluded from the lookup.

**`DevRequestBranchMergerTest`** — the FRD's delivered base commit is merged into the default branch,
and re-running does not merge twice.

**`DevRequestMergeConflictResolverTest`** — when the AI fixes the conflicting files a merge commit is
made · leftover conflict markers mean nothing is applied · tool permissions are working-directory
relative globs with the isolation fragment first · no account means no attempt.

**`FrdCompletionMergeWorkspaceTest`** (25 guarantees) — among them: an external change is not
overwritten even when size and mtime match · a copy without a record is preserved by both recovery and
cleanup · a sparse-checkout omission is not applied as a deletion · a copy abandoned after a
successful publish is cleaned up on restart and its budget returned · an insufficient budget leaves the
original and the index untouched · two FRDs completing at once do not mix their preserved content ·
`git status` rewriting the index mid-finalization still recovers on restart · a changed index stage
blocks restart recovery · the fingerprint compares the index byte for byte.

Run the git-facing suites:

```bash
./mvnw test -Dtest='GitCommandTest,IaPublisherTest,CloneWorkerTest,ArtifactWorktreePathsTest,DevRequestBranchMergerTest,DevRequestMergeConflictResolverTest,FrdCompletionMergeWorkspaceTest'
```

## 20. Traps

Collected from the `⛔` and `⚠` markers in the source. Each one is a bug that actually happened.

1. **Do not remove `-c credential.helper=`.** A Windows credential helper took down an
   already-successful clone with exit 128, and leaves the planning token in the machine's credential
   store.
2. **Do not name a helper to disable one.** `credential.helper=none` searches for a helper called
   `none`. The empty value is the mechanism.
3. **Do not read the two output streams in sequence.** The timeout stops working, and `git clone`
   deadlocks on a full stderr pipe.
4. **Do not `destroyForcibly()` the parent alone.** Grandchildren keep directory handles open, and on
   Windows an open handle makes deletion fail outright.
5. **Do not collect descendants after killing the parent.** The tree is already reaped.
6. **Do not delete immediately after `onExit()`.** Take the bounded 50 ms grace.
7. **Do not add `@Transactional` to `CloneWorker.clone`.** Failures stop being recorded and a
   connection is pinned for 30 minutes.
8. **Do not use `FileSystemUtils.deleteRecursively` on a clone.** Windows read-only pack files. Use
   `FileTrees`.
9. **Do not skip deleting leftovers before a clone attempt.** Retry breaks permanently.
10. **Do not let path and branch be decided by different code.** A `srt-` directory on a `frd/` branch
    broke receiving on 2026-09-03.
11. **Do not delete a screen file to exclude it.** Restore it from `HEAD`; a deletion reads as
    "removed from the operational system".
12. **Do not change the FRD state before the worktree is confirmed.** And never auto-delete an existing
    worktree — it may hold someone's work.
13. **Do not take the workspace lock before the project lock.** `FrdWorkspaceLocks` throws on it.
14. **Do not hold the project lock while an AI run is in flight.** Every other FRD in the Group stalls.
15. **Do not remove entries from the lock maps.** A lock with waiters must not be replaced.
16. **Do not re-push when the merge is already an ancestor.** A previously successful operation turns
    into a failure if the remote moved.
17. **Do not leave `refs/builder/…` behind.** They accumulate, pin objects against gc, and make dead
    branches look alive.
18. **Do not throw from a conflict resolver.** The caller's `merge --abort` is what cleans up.
19. **Do not unpack a returned ZIP inside the worktree.** Implementation source would land in the
    commit.
20. **Do not run the checker in the shared clone.** Concurrent saves mix, and the diff judgement
    becomes false.
21. **Do not rely on `worktree remove` alone.** Prune, then delete the bare directory by hand.
22. **Do not use `git write-tree` to fingerprint an index.** It rewrites the bytes you are measuring.
23. **Do not add a fifth push site casually.** There are four, and that is the contract.
