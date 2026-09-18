# Development result

> What comes back from development, how the archive is validated before it touches disk, and how `개발 결과 반영` applies it to the planning repository.

Package: `com.bizplay.builder.devrequest` — `DevResultReceiver`, `DevResultArchiveValidator`, `DevTestResultValidator`, `DevResultApplyService` / `DevResultApplyWorker`, `DevelopmentRequestMergeService`, `DevRequestBranchMerger`
Canonical design: `docs/superpowers/specs/2026-08-07-dev-feedback-design.md`, `2026-09-11-dev-result-incremental-extraction-design.md`

## Three things come back

Development returns three kinds of material against one development request:

| What | Keyed by | Shape |
|---|---|---|
| **as-is resync** | DR + screen ID + domain module | Screen HTML, screen MD, an `index.json` fragment, domain MD, or "checked, no change". **Top priority** — it is the only material that updates the planning repository. ⚠ Not counted as an artifact; it is an update of something that already exists |
| **Unit test** | DR | **A result document (MD), not code.** One line per "out-of-screen implementation" item — what was verified, how, and the outcome |
| **Integration test** | DR | **A scenario document (MD).** Per completion criterion — scenario, steps, expected result, outcome |

**Builder cannot read development source (it does not know `g2c`), so tests never arrive as code.**

⭐ For both, **Builder writes what is to be verified first** — TC number, condition, action, expected result — into the package's `expected-back.md` (2026-08-27). Development fills in only the actual result, the verdict and the evidence. That is what lets the screens count returned MDs per TC.

## Why as-is resync exists

`core/<system>/pages/` holds **as-is: fact**. FRD work never merges to-be there. The only thing that carries fact into it is this return flow.

If planning's drawings were merged in, `pages/` would hold *what planning drew*, and **the next FRD would read that as production reality**. That is why [FRD completion](08-frd-completion.html) stops at "close the work, keep the branch".

## Archive validation — before anything touches disk

`DevResultArchiveValidator` validates the contract, the paths and the size **before extracting**:

| Limit | Value |
|---|---|
| `MAX_ENTRIES` | 2,000 |
| `MAX_FILE_BYTES` | 10 MB |
| `MAX_TOTAL_BYTES` | 100 MB |

The manifest's `devRequestId` accepts **either the id or the label** — development sees the label (`DR-007`), so demanding the internal id would reject correct replies.

### Test result validation

`DevTestResultValidator` checks the returned unit/integration test documents against the contract that was sent. It applies only to `specVersion` **3** (spec 2 packages had no `expectedBack.testArtifacts`).

It parses:

- `### N. <target>` — target headings
- `#### TC-NNN …` — test case headings
- verdicts restricted to `성공` · `실패` · `미수행`
- `<placeholder>` patterns, which must have been replaced

A spec-3 result with no return contract to compare against is rejected: *"규격 3 개발결과를 대조할 테스트 반환 계약이 없습니다."*

## Applying the result

`POST /projects/{projectId}/artifacts/dev-requests/{requestId}/merge`.

`DevResultApplyService` is the **synchronous gate**: it decides whether the button may be pressed, marks the state as running, and hands the actual work to the AI executor.

> ★ **Why the gate and the worker are separate classes.** `@Async` only applies through the Spring proxy. With the gate and the async body in the **same class**, the call is self-invocation, the proxy is skipped, and **the work runs on the request thread** — in production one apply ran for six minutes on `nio-8080-exec-2` (2026-09-11, DR-010). `ScreenTobeDocumentWorker` carries the same warning, and `DevelopmentRequestService` likewise splits "mark" from "run".

### Where it is applied

`DevResultReceiver` validates the reply and applies it **as one batch**:

- A request with a delivery baseline (`workspaceHeadSha`) is applied to the matching worktree — `frd-` for FRD-sourced, `srt-` for SRT-sourced.
- A request with none (created without a worktree) is applied **directly to the clone** and pushed to the default branch.

The discriminator is the same one the sending side uses: `DevRequestPackageBuilder.usesWorkspace`.

Then `DevelopmentRequestMergeService` + `DevRequestBranchMerger` merge the **delivery-baseline commit** of the development-complete FRD into the planning repository's default branch, under `ProjectRepositoryLocks`, with `DevRequestMergeConflictResolver` for conflicts. `ScreenStandardIdService` is called so newly real screens get their standard IDs — see [Screen IDs](18-screen-id.html).

## It is never automatic

**`개발 완료` is not merge approval.** Builder confirms the `done` label from GitLab and records `DONE` on the development request — nothing more. The user must explicitly press `개발 결과 반영`, and the button is hidden if the result was already applied or the state is not complete.

If the merge fails, `DONE` is kept, the user reads the cause, and can merge again.

`DevResultSchedule` and `DevResultGateway` handle the polling and transport; `DeveloperClient` / `DeveloperGateway` / `DeveloperRegistrationService` cover the DEVELOPER-target delivery channel (`builder.developer.intake-path`, `withdrawal-path`).

## After it lands

Once as-is resync has arrived, the green-zone artifacts have material to be generated from:

```text
as-is resync updates the planning repo
  → feature spec · screen design · user manual can be (re)generated
```

See [Green-zone artifacts](16-green-zone.html) and [Unit & integration tests](17-tests.html).

## Related

- [Development request](10-dev-request.html) — what was sent, and `expected-back.md`
- [FRD completion](08-frd-completion.html) — why to-be never reaches `pages/`
- [Project setup](04-project-setup.html) — repository refresh and locks
