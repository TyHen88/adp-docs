# Project setup

> Registering a planning repository and keeping it usable: the clone, the repository refresh, the reset, systems and facets, the delivery channel, and how a planner ends up inside one project. Owns `project` (25 files) and `git` (4).

## Group or project?

The screen says **Group**. The code says **project** — `adk_builder_project`, `ProjectService`, `/admin/projects`, `ProjectPaths`. The rename happened in the UI only and nothing underneath followed it, so every route, table and class still reads `project`. Expect to translate between the two while reading code; this page uses *project* except when quoting a screen.

One project = one planning repository = one clone on disk = one set of artifacts. Everything a planner produces hangs off it.

## Who can reach it

| | |
|---|---|
| Menu | Admin → Group Management (first of three: Group / User / System) |
| Route prefix | `/admin/projects` |
| Authorization | `@PreAuthorize("hasRole('SUPER')")` on the whole controller |
| Planners | Cannot open any of it. They only *select* a ready project at `/projects` |

Roles and the login flow are on [accounts & security](03-accounts-security.html).

## Screens and routes

| Screen | Method + route | Template |
|---|---|---|
| Project list | `GET /admin/projects` | `admin/projects.html` |
| Register dialog | `GET /admin/projects/new` | `admin/project-register.html`, a fragment over the list |
| Register | `POST /admin/projects` | redirect to list |
| Project detail | `GET /admin/projects/{id}` | `admin/project-detail.html` |
| Re-clone after failure | `POST /admin/projects/{id}/retry` | redirect to detail |
| Update repository | `POST /admin/projects/{id}/repository/update` | redirect to detail |
| Reset project | `POST /admin/projects/{id}/reset` | redirect to detail |
| Replace token | `POST /admin/projects/{id}/token` | redirect to detail |
| Replace facets | `POST /admin/projects/{id}/facets` | redirect to detail |
| Rename systems | `POST /admin/projects/{id}/systems` | redirect to detail |
| Register DEVELOPER delivery | `POST /admin/projects/{id}/developer-target` | redirect to detail |
| Register GitLab-issue delivery | `POST /admin/projects/{id}/dev-issue-target` | redirect to detail |
| Project picker | `GET /projects` | `projects.html` / `project-empty.html` |

**The register dialog is a URL, not a toggle.** `GET /admin/projects/new` renders the list with `registerDialogOpen=true`, and the dialog's own close handler rewrites history back to `/admin/projects`. That keeps it linkable and back-button-safe.

**Every failing POST returns the detail template directly, never a redirect.** Each handler catches `IllegalArgumentException`, re-adds `view`, sets an `editingX` flag and returns `admin/project-detail`. The flag tells the template which dialog to reopen and where to print the error, so the operator's typed input survives the round trip. A redirect would lose it.

## The three states

```text
                    register (probe OK)
                            |
                            v
                     +-------------+   clone succeeds   +---------+
              +----> |  RECEIVING  | -----------------> |  READY  |
              |      +-------------+                    +---------+
              |            |                              |     |
        retry |            | clone fails                  |     | reset
              |            v                              |     |
              |      +-------------+  reset cannot start  |     |
              +----- |   FAILED    | <--------------------+     |
                     +-------------+                            |
                            ^                                   |
                            +-----------------------------------+
                                     back to RECEIVING
```

| State | Screen label | Meaning |
|---|---|---|
| `RECEIVING` | Receiving | Clone running in the background. Not open to planners yet |
| `READY` | Ready | Clone finished. Planners can select it |
| `FAILED` | Failed | Clone failed. `failure_reason` is set and retry is offered |

**Only `READY` counts as existing to a planner.** `ProjectService.findReady` filters the rest out. A `RECEIVING` project has no worktree yet and a `FAILED` one is half-downloaded — opening either renders a screen with nothing inside it. Explaining *why* is the admin screen's job, not the planner's.

> **State changes go through exactly one method.** `ProjectService.changeState` is the only writer and it throws when zero rows change. `Project` deliberately has no setters and no `markReady`-style mutators: MyBatis replaced JPA on 2026-08-15 and there is no dirty checking any more, so a mutator would let callers believe they saved while the database never moved — silently, with no exception.

## Registering

| Field | Form name | Rule |
|---|---|---|
| Group name | `name` | Trimmed, non-empty after trimming, unique across all projects |
| Application facets | `facetCodes[]` / `facetNames[]` | Optional. See below |
| Repository URL | `repoUrl` | GitLab repository |
| Platform code | `platformCode` | `^[A-Z0-9]{2,4}$`, **frozen at registration** |
| Default branch | `defaultBranch` | Defaults to `main` |
| Access token | `token` | Project access token with read and write on the repository |

**The server re-validates everything the form validates.** The HTML `required` attribute happily passes a name made only of spaces, and the `pattern` on the platform code is a hint the browser can be told to skip. Both are re-checked in `registerConfigured`. A whitespace-only name that reaches the database causes a 500 on every artifact screen afterwards, because `ShellContract` forbids a blank project name inside a project-scoped shell, and repairing it after storage is the expensive case.

> **The platform code cannot be corrected later.** It is the first segment of every standard screen ID — the `PS` in `PS-WV-MRC-010-L01-S`. Numbering starts the moment the clone lands and assigned IDs are never rewritten, so a later edit only splits the project's IDs into two generations. See [screen IDs](18-screen-id.html).

`ProjectService.registerConfigured` runs in one transaction:

1. Trim and validate the name; reject if empty.
2. Validate the platform code.
3. Reject a duplicate name.
4. **Probe the repository.** `RepoProbe` runs `git ls-remote --heads <authenticated-url> <branch>` with a 20-second timeout. It downloads nothing and still verifies URL, token and branch together. It reports two distinct failures: could not connect, versus connected but branch not found.
5. Seal the token — `SecretSealer` produces `sealed_token` plus `token_nonce`.
6. **Allocate the ID** with `IdSequence.next(PROJECT)`, a 7-digit zero-padded string.
7. Insert the row with state `RECEIVING`.
8. Re-read the row to pick up `created_at`, a database `default now()` the Java object never saw.
9. Insert the normalized facet rows.

**The ID is allocated after the probe, not before.** A sequence does not roll back, so allocating first burns a number on every failed connection attempt. **A failed probe saves nothing** — not the project, not the facets.

The controller then calls `cloneWorker.clone(...)` and redirects immediately. The clone runs behind the screen.

## Cloning

`CloneWorker`, `@Async("cloneExecutor")`, 30-minute timeout. It follows the standard async-worker shape described in [architecture](01-architecture.html).

> **Never put `@Transactional` on `CloneWorker.clone`.** Two things break at once. First, *failures stop being recorded*: the nested `projects.tokenOf()` would join the same transaction, and when unsealing throws, Spring marks it rollback-only — catching the exception and calling `markFailed(...)` then dies at commit with `UnexpectedRollbackException` and the project freezes on Receiving forever. Catching is not enough. Second, *a database connection is pinned for 30 minutes*.

So the work is cut into three segments, **short read / file work / short write**, and the result write commits in `ProjectService`'s own transaction:

1. Read the clone materials: default branch, and the URL with the unsealed token embedded. **The token is unsealed before anything touches the disk** — the reverse order destroys an existing clone and only then discovers the token cannot be read.
2. Delete leftovers from the previous attempt.
3. `git clone --branch <branch> <authenticated-url> <dir>`, outside any transaction.
4. On success `markReady`, sync systems, start screen-ID numbering, notify. On failure `markFailed(describeFailure(result))`, notify.

**Leftovers are deleted before every attempt.** A clone killed at the timeout cannot clean up after itself and leaves a half-built directory; without the delete every later retry fails with `destination path already exists and is not an empty directory`, permanently. The promise that retrying just works was broken exactly here.

> **Deletion uses `FileTrees.deleteRecursively`, not `FileSystemUtils.deleteRecursively`.** Git marks pack files read-only on Windows, and the Spring helper dies on them with `AccessDeniedException`. That is unrecoverable rather than merely noisy, because the surviving directory then blocks the next clone too. Unix never showed it: deleting a file there checks the containing directory's permissions, not the file's.

**The failure reason always carries the exit code.** An earlier version recorded only `stderr`, and in a real failure that was the single line `Cloning into '…'` — the cause was absent from every record. Exit code 128, git's own error, versus 143, killed from outside, is the distinction that matters. The reason keeps the **last** 2000 characters, because git prints progress first and the error last.

### After a successful clone

Two follow-ups run, and both are swallowed on failure because the clone already succeeded and must not be flipped back:

- **System sync** — `ProjectSystemService.syncQuietly` reads `manifest.json` and seeds the system codes.
- **Screen-ID numbering** — `ScreenStandardIdWorker.assignQuietly`.

The *submission* of the numbering job is separately wrapped. `@Async` rejection is thrown synchronously in the calling thread by the proxy, so the `try/catch` inside `assignQuietly` never runs; without the outer wrap the enclosing `catch` calls `cloneFailed` and turns a successful clone into a failure. The next repository update is the retry for both.

## Repository update

Refreshes the existing clone in place instead of downloading it again. `RepositoryUpdateWorker` checks five preconditions in order, each with its own message:

1. The project is `READY`.
2. No update is already running — `repositoryUpdates.tryStart(projectId)` claims the attempt atomically in the database and the worker proceeds only if it won.
3. The clone directory contains `.git`.
4. `git status --porcelain` is clean; uncommitted changes abort the update.
5. `git symbolic-ref --short HEAD` equals the default branch.

Then it records `HEAD` as `from_commit`, runs `git fetch <url> <branch>` and `git merge --ff-only FETCH_HEAD`, and records the new `HEAD` plus whether it moved. **Fast-forward only** — anything needing a real merge is refused and reported, never resolved. Afterwards the same two follow-ups run as after a clone.

> **Git work on one project is serialized in-process** by `ProjectRepositoryLocks`, a `ConcurrentHashMap<String, ReentrantLock>`. Per-JVM, not a database lock — Builder is a single-server product, so this is sufficient by design rather than by accident.

The detail screen reads the outcome from `adk_builder_repository_update`: running, updated, already current, or failed, with the finish time.

## Reset

Wipes everything the project produced and re-clones, keeping the registration. Guarded three ways in `ProjectService.reset`: only a `READY` project, never while an update is `RUNNING`, and the operator must retype the **exact** project name. The dialog is labelled a stabilization temporary feature and its submit button stays disabled until the typed name matches.

| Deleted, one transaction, ~21 tables | Kept |
|---|---|
| SRTs · dev-request deliveries and requests · FRDs · intakes · AI runs · mockup mismatches · IA structures · the repository-update row · screen standard IDs and ID groups · design-system curations · user manuals · business-document seeds, parts, merges and documents · feature-spec revisions and specs · screen-design revisions and designs | Accounts · the project registration · facets · systems · delivery settings |

The state then returns to `RECEIVING`. AI-run and document-run IDs are read out **before** the deletes and handed to `ProjectResetWorker`, which needs them to locate credential directories on disk. That worker deletes the project directory and those run directories under the repository lock, then re-clones. If it cannot even start, the controller marks the project failed rather than leaving it mid-reset.

## Application facets

An optional axis for splitting screens by institution or service; the register dialog's example is code `jeju`, display name `Jeju`. **Zero facets is normal** — there is no implicit "common" value. Each facet carries a **code**, the stable key that links to the extractor's index, and a **display name** shown on screen. Both are required, both must be unique within the project, and the code must match `[\p{L}\p{N}][\p{L}\p{N}-]*`.

> **Editing computes a diff; it never deletes all and reinserts.** `adk_builder_intake_facet` references facet names, so a blanket delete raises a foreign-key violation on any project that has ever received a document. `replaceFacetSettings` matches wanted against current by code first and then by name, removing only what fell out, renaming what changed, inserting what is new.

**If a facet being removed is still used by a received document the whole edit is rejected**, and the message names the offending facets. Silently skipping that one facet would leave the screen disagreeing with storage; deleting it would throw a 500. Both are worse than a refusal the operator can read.

### The facet key is the pair, and the database enforces it

`adk_builder_project_facet` has primary key `(project_id, name)`, with a separate unique constraint on `(project_id, code)`. Child tables carry **both columns and reference the pair**:

| Child | Foreign key | On update |
|---|---|---|
| `adk_builder_intake_facet` | `(project_id, name)` → `adk_builder_project_facet` | `ON UPDATE CASCADE` |
| `adk_builder_frd_facet` | `(project_id, name)` → `adk_builder_project_facet` | none — plain `NO ACTION` |

The `project_id` column in a child is **not redundant**; it exists so the pair can be the foreign key. That buys two guarantees no application check could give: a facet value that is not on the project's list cannot enter an artifact, and **one project cannot borrow another project's facet**. It is also why the column is not a `text[]` — an array cannot be constrained by the database, and renaming would mean rewriting every array. Canonical: `docs/data-model.md` §6.

> **The two children do not behave the same, and only one of them is guarded.** `ON UPDATE CASCADE` on the intake side is what makes renaming a display name carry through to already-received documents, and `ProjectFacetMapper.updateName` is written around exactly that. `adk_builder_frd_facet` has no such cascade, and `ProjectService` holds only `IntakeFacetMapper` — it never consults FRD facets, on rename or on removal. So a facet name that an FRD references will refuse to be renamed or removed at the database, as a foreign-key error rather than the readable refusal the intake path produces. Measured against the live schema on 2026-09-17, not inferred.

## Systems

A project's systems carry **two different sources of truth in one row**:

| Column | Source | Editable |
|---|---|---|
| `system_code` | `manifest.json` in the clone, `systems[].id` | No, read-only in the UI |
| `display_name` | Typed by the administrator | Yes |

That split is the whole point. Codes an operator invents would meet data on no other screen — they would sit in the admin screen alone, looking registered while doing nothing. So `replaceNames` **silently drops unknown codes instead of inserting rows**, and the code input is rendered read-only. `PlanningManifestReader` is the single parser for that file, and it **returns an empty list instead of throwing** when the file is missing or unreadable — a missing manifest must never flip a finished clone to failed or break a screen, so the caller gets to choose "do nothing". The same file's `systems[].skins` is the only source of truth for which CSS folder belongs to which institution; that is [solution templates](13-solution-mockup.html), not this page.

Rules in `ProjectSystemService`:

- **An unreadable `manifest.json` changes nothing.** Pushing zero rows would erase every typed display name because of one unreadable file.
- **Codes that vanished from the repo are deleted.** `system_code` is a bare string elsewhere, not a foreign key.
- **Re-syncing never touches display names.**
- **Two systems cannot share a display name.** The solution-template filter matches on *name*, so a duplicate makes one value select two systems and the counts stop being trustworthy. See [solution templates](13-solution-mockup.html).
- **A missing name is normal.** `ProjectSystem.label()` falls back to the code, because a blank reads as "a screen with no system". `SystemLabels` does the same for unknown codes.

An earlier version hardcoded three system names as Java constants. When a repository grew to six systems the other three rendered as raw codes. Those constants are not to be restored — the system list differs per engagement.

## Delivery channel

Each project chooses where finished development requests go. The screen is the **개발요청 전송 방식** card on the project detail, and the two choices are **Developer 연결** and **GitLab 이슈로 전송**.

`deliveryChannel` is **derived, not stored as a flag**: `DEVELOPER` when `developerTargets.current(id)` is non-null, otherwise `GITLAB`. There is no third value and no "unset" — a project with nothing registered reads as `GITLAB`.

### The card tells you whether it is usable, not which one is picked

```text
개발요청 전송 방식                        [ 설정 필요 ]  ← or [ 설정 완료 ]
Developer 환경이 준비되지 않은 곳은 개발요청을 GitLab 이슈로 보냅니다.
GitLab 주소와 개발 저장소, 토큰을 등록해 주세요.
                                          [ 전송 설정 ]  ← or [ 설정 변경 ]
```

The badge comes from `deliveryReady`, which checks **the target for the channel currently selected**:

| Selected channel | `deliveryReady` when |
|---|---|
| `DEVELOPER` | `developerTarget != null` |
| `GITLAB` | `devIssueTarget != null` |

⚠ **A fresh project shows `설정 필요` with both options marked "connection information required", and that is the normal starting state.** Neither channel has a target yet, the derived channel is `GITLAB`, and the card asks for the GitLab address, repository and token. Nothing about a development request works until one side is filled in — but the project is otherwise complete, so this is not a failure state.

### Developer 연결

| Field | Rule |
|---|---|
| Developer 주소 | Trailing slashes stripped, then must parse as an `http`/`https` base URL (checked through `DeveloperClient.endpoint`) |
| 그룹 ID | `\S{1,255}` — no whitespace, at most 255 characters |

⭐ **Registering does not test the connection.** The token round-trip was removed on 2026-09-08; whether the address and group actually work is proven by **the first real development request**. So `설정 완료` means "values are stored", not "the far side answered".

`register` retires every existing row first, then either **reactivates the previous row** when the address and group are unchanged, or inserts a new one. Re-entering identical values therefore does not grow the history.

### GitLab 이슈로 전송

| Field | Rule |
|---|---|
| GitLab 주소 | Must start with `http://` or `https://` |
| 개발 저장소 | `group/project` path, required |
| GitLab 토큰 | Required on first save; printable ASCII only (`0x21`–`0x7E`) |

⛔ **The token is never shown back.** The screen displays "등록됨" and nothing else. Leaving the field blank on a later save keeps the stored token — the same rule as the project access token.

> ⭐ **The ASCII check exists because of where the token travels.** It rides in the `PRIVATE-TOKEN` HTTP header. A pasted token carrying a space or Korean text throws at the moment of transmission, and that attempt then **freezes in `전송중` with no readable cause** — the person ends up asking the development team why nothing arrived. Rejecting it at the input is the only place where the person who pasted it can still fix it.

Saving GitLab settings also calls `developerTargets.selectGitLab(id)`, which retires every Developer row. Choosing Developer again calls `selectDeveloper(id)`, which **requires a stored row** and otherwise refuses with "먼저 DEVELOPER 주소와 그룹 ID를 입력해 주세요."

### Why the history is kept

`adk_builder_developer_target` never overwrites. `retire` sets every row for the project to `current_target=false`; `activate` sets one back to true, and a partial unique index allows only one true per project. **All rows false is how GitLab is represented.**

Two things depend on keeping the old rows:

- A request already sent must keep querying status and results **against the address it was sent to**. See the per-request binding in [development request](10-dev-request.html) — the channel is frozen onto the request at first send, so changing this setting never moves work already in flight.
- Switching back to Developer reuses the previous address and group instead of asking for them again.

The wire contract is `docs/developer-api-contract.md`; the sending side is [development request](10-dev-request.html).

## How a planner lands in a project

`ProjectPickController` at `GET /projects`, outside the admin area:

- Ready projects exist → **redirect straight to the first one**, `/projects/{id}/artifacts/frds`, ordered by ID. The switcher in the left navigation is how a planner changes projects afterwards.
- None ready and the visitor is a super account → send them to `/admin/projects` to register one, with `?builderUnavailable` when they came from the admin area, which raises a banner on the list.
- None ready and the visitor is a planner → the `project-empty` page. A guidance card only means something to someone who cannot fix the situation.
- `?gone` is present, meaning they followed a stale URL → **always show the picker, even when only one project is ready.** Skipping it drops them into a different project without a word.

`ProjectContextInterceptor` resolves the project for every `/projects/**` request and puts it in the model.

## Tables

`adk_builder_project`

| Column | Type | Notes |
|---|---|---|
| `id` | `varchar(7)` PK | `CHECK (id ~ '^[0-9]{7}$')`. Written by `IdSequence`, not by the column default |
| `name` | `varchar(128)` UNIQUE | |
| `repo_url` | `varchar(1024)` | |
| `default_branch` | `varchar(128)` | |
| `sealed_token` / `token_nonce` | `bytea` | Meaningless apart from each other |
| `state` | `varchar(16)` | `RECEIVING` / `READY` / `FAILED` |
| `failure_reason` | `text` | Set only while `FAILED`, cleared on retry and on success |
| `created_at` | `timestamptz` | `default now()` |
| `platform_code` | `varchar(4)` | `CHECK (~ '^[A-Z0-9]{2,4}$')`, default `PS` |
| `requirement_seq` `frd_seq` `dev_request_seq` `srt_seq` | `integer` | Per-project counters, default 0 |

The column default `lpad(nextval(...), 7, '0')` exists but **is not relied on**; numbering happens in Java. See [data model](02-data-model.html).

| Table | Shape |
|---|---|
| `adk_builder_project_facet` | PK `(project_id, name)`, UNIQUE `(project_id, code)`, both `varchar(64)` and both `CHECK`-trimmed and non-empty. Children reference the pair, not just the id |
| `adk_builder_project_system` | PK `(project_id, system_code)`, `display_name` nullable, `ON DELETE CASCADE` |
| `adk_builder_repository_update` | PK `project_id`, so **one row per project** — the last attempt, not a history. `state` constrained to `RUNNING` / `SUCCEEDED` / `FAILED`, plus `from_commit`, `current_commit`, `changed`, `started_at`, `finished_at`, `failure_reason varchar(2000)` |

> **23 tables carry a foreign key to `adk_builder_project`.** That is the practical reason project deletion does not exist as a feature, and why reset enumerates its deletes by hand.

## On disk

`ProjectPaths` computes every path from `builder.data-root`, and `projectDir` re-validates the ID format because a string ID, unlike the old `Long`, lets `..` or `a/b` resolve outside the root.

```text
<data-root>/
  probe/                                         RepoProbe working directory
  projects/<projectId>/
    clone/                                       the server clone — root of all worktrees
    worktrees/
      frd-<frdId>/                               one FRD's persistent workspace
      srt-<srtId>/
      dev-request-merge-<requestId>/             temporary, deleted after the merge
    received/                                    uploaded source documents — NOT in the clone
    dev-request-attachments/
    dev-request-packages/<requestId>/DR-###.zip  what was actually sent out
    business-language-run/<slot>/
  runs/<runId>/credentials/                      CLAUDE_CONFIG_DIR, one per AI run
  doc-runs/<runId>/                              document-processing runs
```

Two placement rules that look arbitrary and are not:

- **Received documents and outgoing packages live outside `clone/`.** Anything inside the clone directory is something git can see, and neither is meant to be pushed to the planning repository.
- **Credential directories are per run, not per person.** One person can run two jobs at once, so keying by person lets the first job's `finally` delete the credentials of a job still running. For the same reason AI runs and document runs use separate trees: both sequences are 7 digits, so `runs/0000001` would otherwise collide with a different `0000001`. See [Claude CLI runtime](05-claude-cli-runtime.html).

## What this page assumes about git

Every git call in the product goes through one runner. That layer — `GitCommand`, the timeouts, token masking, the locks, worktrees, and the only four places allowed to push — is documented on its own page: **[git](git.html)**. Two pieces of it are load-bearing here and are worth stating where registration is explained.

**`RepoProbe` is the gate on registration.** One `git ls-remote --heads <authenticated-url> <branch>` with a 20-second timeout, downloading nothing, checking URL, token and branch together. Registration and token replacement both refuse to store anything unless it succeeds, which is why a bad token can never reach the database in the first place.

**Never log or store raw git output.** `GitCommand.mask()` rewrites `://anything@` to `://***@`, and it matters on this page specifically because the clone failure reason is written straight into `failure_reason` and rendered on the project detail screen. The authenticated URL carries the access token, so an unmasked failure would put a live credential on an admin page and in the database.

> **Both streams are drained at once, and the clone is where that first mattered.** `StreamPump` gives stdout and stderr a thread each. Draining one to the end first lets the other pipe fill, and the two sides then wait on each other — a deadlock in which **the timeout does nothing**, because the process never exits and the reader never returns. `git clone` pours its progress into stderr, so this path is taken rather than theoretical. [Claude CLI runtime](05-claude-cli-runtime.html) hit the identical trap later and fixed it the same way; [git](git.html) §2.3 has the mechanism.

## Replacing the token

`POST /admin/projects/{id}/token` probes with the stored URL and branch plus the **new** token and only writes on success. Name, URL and branch are untouched: retrying cures a dropped network but cannot cure an expired token, which is why the token has its own field and its own form.

## Flow API key

Registered on a **different screen** — Admin → System Management at `/admin/system`, not part of project registration. See [Flow integration](25-flow.html).

## Code map

| File | Role |
|---|---|
| `project/AdminProjectController.java` | The 12 admin routes, SUPER-only, error-path model rebuilding |
| `project/ProjectService.java` | Every business rule and every state transition |
| `project/Project.java` | Immutable row, no setters, deliberately |
| `project/ProjectState.java` | The three states and their labels |
| `project/ProjectDetailView.java` | Read-only bundle for the detail screen. **Never carries the token** |
| `project/CloneWorker.java` | Async clone, leftover cleanup, failure description |
| `project/RepositoryUpdateWorker.java` | Async fast-forward update, five preconditions |
| `project/ProjectResetWorker.java` | Async file deletion then re-clone |
| `project/ProjectRepositoryLocks.java` | Per-project in-process git serialization |
| `project/ProjectSystemService.java` | Code sync from the manifest plus name editing |
| `project/PlanningManifestReader.java` | The single parser for the clone's `manifest.json` |
| `project/ProjectPaths.java` | Every path under `data-root` |
| `project/ProjectPickController.java` | Planner-side project selection |
| `project/SystemLabels.java` | Code to display name, per project |
| `git/RepoProbe.java` | `git ls-remote` reachability check |
| `templates/admin/projects.html` | List and empty state |
| `templates/admin/project-register.html` | Register dialog fragment |
| `templates/admin/project-detail.html` | Detail plus five dialogs — reset, delivery, facets, systems, token |

Specs the code points at: `docs/superpowers/specs/2026-08-10-project-context-design.md`, `2026-08-20-screen-standard-id-design.md`, `2026-08-09-screen-shell-design.md`.

## What the tests guarantee

Test method names in this repository are Korean sentences stating the guarantee. Translated:

**`ProjectRegisterTest`** — four valid fields save and set Receiving · a failed probe saves nothing · the token is stored sealed · a whitespace-only name is rejected and outer spaces trimmed · the same name cannot be registered twice · facets are split, trimmed and stored individually · no facet rows when none were given · a failed probe leaves no facet rows · code and display name are stored separately · the register screen opens for a super account · the platform code is stored as submitted · a malformed platform code returns to the register screen without saving.

**`ProjectDetailTest`** — the detail shows repository, branch and facets · delivery settings appear separately from project information · saving a GitLab issue target selects it as the channel · a rejected delivery setting redisplays the dialog with the error and the typed values · the platform code is shown · a ready project shows only management actions · an update can be started from the detail · reset requires the name and keeps management settings · a mismatched name is refused and the work survives · renaming a facet also updates registered documents · a failed project shows the reason and a retry and does not offer "open" · the list has no recovery actions · resubmitting a depended-on facet passes · adding a facet succeeds · removing an unused facet succeeds · removing a depended-on facet is refused and nothing changes · a row not created through the register screen still shows a registration time · a planner cannot open the admin detail.

**`ProjectSystemTest`** — every manifest system lands unnamed · a missing name renders as the code · an unreadable manifest leaves names alone · systems removed from the repo leave the list · re-syncing preserves typed names · the detail shows codes with names and saves names · a code absent from the repo creates no row · a duplicate display name is rejected · clearing a name falls back to the code.

**`TokenReplaceTest`** — a correct new token returns to the detail · a wrong one is not stored and the reason appears there.

Also `CloneWorkerTest`, `RepositoryUpdateWorkerTest`, `ProjectResetWorkerTest`, `ProjectPickTest`, `ProjectContextTest`, `ArtifactWorktreePathsTest`, `PlanningRepositoryUpdaterTest`.

```text
./mvnw test -Dtest='Project*Test,TokenReplaceTest,CloneWorkerTest,RepositoryUpdateWorkerTest'
```

## Traps

Every one of these is a bug that actually happened, collected from the `⛔` and `⚠` markers in the source.

1. **No `@Transactional` on `CloneWorker.clone`.** Failures stop being recorded and a connection is pinned for 30 minutes.
2. **No setters or mutators on `Project`.** MyBatis has no dirty checking; the caller believes it saved and the database never moves, with no exception.
3. **Do not reorder the `Project` constructor arguments.** The mapper XML binds by position; five fields are strings and two are `byte[]`, so a swap compiles, runs, and surfaces only as a token that will not unseal.
4. **Do not delete-all-and-reinsert facets.** Foreign keys from `adk_builder_intake_facet`.
5. **Do not let operators type system codes.** `manifest.json` is the source of truth; invented codes meet no data anywhere.
6. **Do not hardcode system names in Java or YAML.** The list differs per engagement, and this already failed once when a repository grew from three systems to six.
7. **Do not wipe systems when `manifest.json` cannot be read.** One unreadable file would erase every typed name.
8. **Do not put received documents or outgoing packages inside `clone/`.** Git would see them.
9. **Do not key credential directories by person.** Key them by run.
10. **Do not put the token in `ProjectDetailView`.** The screen shows only that one is registered; an unsealed token in the model is a leak waiting to be rendered.
11. **Do not allocate the ID before the probe.** Sequences do not roll back.
12. **Do not use `FileSystemUtils.deleteRecursively` on a clone.** Windows read-only pack files.
