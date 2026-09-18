# Architecture

> The stack, the package map, how one request flows, the async worker pattern that every long-running feature reuses, and the on-disk layout under `data-root`.

## Stack

| Layer | Choice |
|---|---|
| Language / runtime | Java 17 |
| Framework | Spring Boot 3.5.9 (`spring-boot-starter-web`) |
| View | Thymeleaf + `thymeleaf-extras-springsecurity6`, server-rendered |
| Security | Spring Security, form login |
| Persistence | **MyBatis** 3.0.4 over `spring-boot-starter-jdbc`. No JPA — all data access moved to MyBatis on 2026-08-15 |
| Schema | Flyway (`flyway-core` + `flyway-database-postgresql`), schema `builder` |
| Database | PostgreSQL 17 target. **Tests run on zonky embedded PostgreSQL 14.22** — 15+ syntax breaks tests only |
| HTML processing | jsoup 1.23.1 |
| Screen capture | Playwright Java 1.62.0 with **full Chromium** (not `--only-shell`) |
| AI | **Two providers.** The `claude` CLI, executed as a subprocess, for everything in the work flow; **Gemini over HTTP** (`builder.document-understanding`) for transcribing uploaded files a server cannot read — see [intake & doc reading](24-document-intake.html) |
| Build | Maven wrapper (`./mvnw`), artifact `builder-<version>.jar` |

There is no SPA build step and no JavaScript bundler. The front end is Thymeleaf templates plus hand-written CSS and small ES5-compatible scripts under `src/main/resources/static/`.

## Package map

All production code lives under `com.bizplay.builder`. Package = feature area; the reference page for each is linked.

| Package | Files | What it owns | Page |
|---|---|---|---|
| `frd` | 101 | FRD lifecycle: wizard, interview, workbench, screens, markers, history, completion | [wizard](06-frd-wizard.html) · [workbench](07-frd-workbench.html) · [completion](08-frd-completion.html) |
| `devrequest` | 59 | DR package build, pre-check, GitLab delivery, status sync, result apply | [dev request](10-dev-request.html) · [dev result](11-dev-result.html) |
| `businesslanguage` | 34 | Business policy + standard terminology documents, seeding, revisions | [policy & terms](15-business-language.html) |
| `intake` | 28 | Received documents and requirement drafts (**retired chain**) — but also the **live** file-reading and multimodal transcription path | [intake & doc reading](24-document-intake.html) |
| `project` | 25 | Project registration, clone, systems, facets, repository refresh, paths | [project setup](04-project-setup.html) |
| `ai` | 24 | The Claude runner, isolation, common rules, AI-run records and worker | [Claude CLI runtime](05-claude-cli-runtime.html) |
| `screendesign` | 16 | Screen-design document generation + Playwright capture | [green zone](16-green-zone.html) |
| `featurespec` | 14 | Feature-spec generation, revisions, rendering | [green zone](16-green-zone.html) |
| `design` | 14 | Design guide, design index, style vocabulary, curation | [design guide](14-design-guide.html) |
| `claude` | 13 | Per-account Claude credentials, auth gateway, identity, locks | [Claude CLI runtime](05-claude-cli-runtime.html) |
| `solution` | 12 | Solution templates (mockups), preview, skin rewriting, mismatch flags | [solution templates](13-solution-mockup.html) |
| `screenid` | 12 | Standard screen-ID numbering | [screen IDs](18-screen-id.html) |
| `ia` | 12 | Menu tree / information architecture | [IA](12-ia.html) |
| `config` | 12 | Properties, security, async executors, interceptor registration, static resources | this page |
| `usermanual` | 10 | User-manual generation and capture | [green zone](16-green-zone.html) |
| `srt` | 10 | SRT fast track | [SRT](09-srt.html) |
| `notification` | 10 | In-app notifications, screen-draft batches | [notifications](20-notification.html) |
| `account` | 10 | Accounts, login, password, super-account bootstrap | [accounts & security](03-accounts-security.html) |
| `checker` | 9 | Running the planning repository's checker, diffing findings | [spec checker](19-checker.html) |
| `integrationtest` / `unittest` | 6 / 4 | Reading returned test result documents | [tests](17-tests.html) |
| `git` | 4 | `GitCommand`, `RepoProbe` — every git call goes through here | [git layer](git.html) |
| `flow` | 4 | Flow API key administration | [project setup](04-project-setup.html) |
| `secret` | 3 | `SecretSealer`, `Sealed`, temporary passwords | [accounts & security](03-accounts-security.html) |
| `web` | 2 | `FirstLoginFilter`, `ProjectContextInterceptor` | this page |
| `shell` | 1 | `ShellContract` — the layout fragment's argument contract | this page |
| `id` | 1 | `IdSequence` — artifact numbering | [data model](02-data-model.html) |
| `artifact` | 1 | `ArtifactListController` — the generic artifact landing screens | this page |

## How one request flows

```text
browser
  → Spring Security filter chain        (form login; /login and static are public)
  → FirstLoginFilter                    (forces password change before anything else)
  → ProjectContextInterceptor           (/projects/** — resolves the project, puts it in the model)
  → FrdWriteInterceptor                 (/projects/** — refuses writes while an FRD is locked)
  → NotificationInterceptor             (/** — puts the unread notification list in the model)
  → @Controller
      → @Service  (transaction boundary)
          → MyBatis mapper  → PostgreSQL `builder` schema
          → ProjectPaths    → the clone / worktrees on disk
          → an @Async worker → the `claude` CLI subprocess
  → Thymeleaf template
      → fragments/shell :: layout       (ShellContract.check() validates the arguments)
```

### The shell contract

`fragments/shell.html` is the single layout. Because Thymeleaf fragment arguments are plain strings, a typo produces **a normal-looking page with the menu and project name missing** rather than a 500 — the hardest failure for a human to notice. So `ShellContract.check()` throws on any unknown value.

| Argument | Allowed values |
|---|---|
| `shape` | `산출물` (artifact, has left menu) · `관리` (admin, has left menu) · `카드` (card, login family) · `꽉` (full, no menu) |
| `current` | For `산출물`: one of `ARTIFACT_KEYS`. For `관리`: `projects` · `accounts` · `system`. For the other two: must be `null` |
| `projectName`, `projectId` | Required whenever `shape` is `산출물` or `꽉` — an empty `projectId` produces links like `/projects//artifacts/brd` |

> Changing the menu means changing **three** files together: `ShellContract.java`, `fragments/parts.html`, and `_shell.js`. `ShellContractTest` compares the table against the rendered menu text and fails if they drift.

## The async worker pattern

Every long-running feature (AI analysis, cloning, package building, document generation) uses the same shape. Learn it once and the other 20 read themselves.

```text
Controller               → Service                 → Worker (@Async)      → external process
  accepts the POST          claims the row            runs `claude` / git      claude, git, Playwright
  returns immediately       in one transaction        parses the result
  the page polls a          (state = RUNNING,         writes the outcome
  /status endpoint           owner, started_at)       in a new transaction
```

Rules that hold across all of them:

- **The worker is always a separate bean from the service.** Calling an `@Async` method from inside the same class skips the Spring proxy, so the annotation *silently does nothing*. `ScreenPickWorker` carries this warning in its javadoc because it was learned the hard way.
- **The claim is a conditional update.** State moves `WAITING → RUNNING` only if the row is still `WAITING`; that is what prevents two workers doing the same job.
- **The result lands in a new transaction**, so a failure while recording the outcome cannot roll back the work itself. `NotificationPublisher` follows the same rule and swallows its own exceptions — a notification failure must never fail the real work.
- **Long input never goes on the command line.** Pasted source text is written to a run-only file and the instruction carries the path. Two reasons: the Windows argv limit (~32 KB), and imperative sentences inside pasted text being read as instructions.
- **The page polls a `/status` endpoint** and re-renders a fragment. There is no websocket.

### Thread pools

Defined in `AsyncConfig`:

| Executor | Size | Used by |
|---|---|---|
| `aiExecutor` | `builder.ai-concurrency` core = max, queue `builder.ai-queue-capacity` | every Claude run |
| `cloneExecutor` | core 2, max 4, queue 50 | repository clone and refresh |
| `deliveryExecutor` | core 1, max 1, queue `builder.delivery.queue-capacity` (default 20) | development-request delivery — deliberately serial |

## On-disk layout

`builder.data-root` (for example `/var/lib/we-adk-builder`) holds everything that is not in the database. `ProjectPaths` is the only class that composes these paths, and it validates every ID before using it in a path.

```text
<data-root>/
├── claude/
│   └── common-rules.md              unpacked from the jar at every boot; the jar always wins
├── credentials/                     per-account CLAUDE_CONFIG_DIR (sealed)
└── projects/<projectId>/
    ├── clone/                       the planning repository clone (read-mostly)
    │   └── core/<systemCode>/ia.md
    ├── worktrees/
    │   ├── frd-<frdId>/             one per FRD  → branch frd/<frdId>
    │   ├── srt-<srtId>/             one per SRT  → branch srt/<srtId>
    │   └── dev-request-merge-<id>/  transient, for applying returned results
    ├── received/                    uploaded source documents
    ├── dev-request-attachments/
    └── dev-request-packages/<requestId>/
        └── DR-NNN.zip
```

> **Back up the database and `data-root` together.** Restoring one without the other leaves the DB state and the on-disk clone/worktree state disagreeing.

## Where state lives — DB or git?

This split is the single most important thing to internalise:

| Kind of thing | Source of truth |
|---|---|
| Screens, screen markdown, domain documents, IA snapshot, design derivatives | **The planning repository** (the clone). Builder mostly reads. |
| FRD state, interview transcript, screen work status, markers, memos, history | **Builder's database** |
| IA rows being edited | **Builder's database**; the repo `ia.md` gets a read-only snapshot on confirm |
| Mockup "differs from production" flags | **Builder's database** (the screen itself is the repo's) |
| Work in progress on screens | **The FRD's git worktree**, committed on that FRD's branch |

## Testing

`./mvnw test` is the finish line for behaviour and logic changes. Tests run on the JDK 17 pinned by the repository and on zonky embedded PostgreSQL. Verification effort is tiered by risk — see [Conventions](22-conventions.html).
