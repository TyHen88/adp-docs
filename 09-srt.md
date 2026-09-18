# SRT fast track

> The short path for small, concrete changes: register a request — typed directly or pulled from Flow — and go straight to a development request, with no interview and no screen work. Every SRT quietly builds an internal FRD to travel on.

Package: `com.bizplay.builder.srt` (10 files), with `flow` for the API key and `intake.FlowPostGateway` for fetching.
Canonical design: `docs/superpowers/specs/2026-08-31-srt-fast-track-design.md`.
Screens: `artifacts/srts.html` (list), `artifacts/srt.html` (detail + registration layer).

## What SRT is for

```text
직접 입력 ─┐
           ├ AI tidies the request → create the development request
플로우 등록 ┘
```

SRT (빠른 개발요청) is for changes **simple and concrete enough not to need screen design work**. Either entry method **always** produces a development request; an SRT never converts into FRD work.

⛔ **Do not shrink a scope that needs an FRD interview or screen work so that it fits into an SRT.** That is the one misuse the design names explicitly.

> **Why this exists.** Until 2026-09-02 the FRD fast track covered "a simple change to one existing screen". That was moved out of the FRD flow entirely and became this menu. The FRD fast track now means **backend-only changes and nothing else** — see [FRD wizard](06-frd-wizard.html). The decision is recorded as the 2026-09-02 revision block in `docs/superpowers/specs/2026-08-18-frd-fast-track-design.md`, not in the SRT spec, which is where to look when the question is "how does this differ from the FRD fast track?".

## The bridge FRD — the mechanism everything rests on

**Registering an SRT creates two rows, not one.** Alongside the `adk_builder_srt` row, `SrtService.register` inserts a full `adk_builder_frd` row and links it as `bridge_frd_id`:

| Field on the bridge FRD | Value | Why |
|---|---|---|
| `sourceKind` | `Frd.SourceKind.SRT` | How every downstream reader tells an SRT apart from real FRD work |
| `sourceRef` | the SRT label, `SRT-003` | Traceability back to the SRT |
| `state` | `SCOPE_REVIEW` | It skips the wizard entirely — it is born past the interview |
| `noScreenReason` | "SRT는 화면 선택 없이 개발요청서로 전환합니다." | Recorded so a reader knows the absence of screens is intended, not missing work |
| `sourceText` | the SRT content | The analysis input |

Nothing in the UI shows this FRD. It exists so that **SRT reuses the FRD machinery instead of duplicating it** — the development request is built by `DevelopmentRequestService.createFromConfirmedScope(projectId, bridgeFrdId, …)`, the very call the FRD path uses, and the requirements and completion criteria live as ordinary `FrdItem` and `FrdAnalysisNote` rows against that FRD.

`adk_builder_srt.bridge_frd_id` carries a **UNIQUE** constraint, so one FRD can never back two SRTs.

> **This is why the SRT tables look thin.** There is no `srt_requirement` table and there never should be. Search for where an SRT's requirements are stored and the answer is `adk_builder_frd_item` keyed by the bridge FRD. `SrtService.storedAnalysisOf` reads them back and reassembles a `SrtAiAnalysis` from those rows.

## Registering

Claude must be connected — registration is refused without it, on both the page and the JSON route. Registration opens as a centred layer over the list.

| Method | Input | Server rule |
|---|---|---|
| `직접 입력` | Title + request body | Title ≤ 255, content ≤ 20000, neither blank after trimming |
| `플로우 등록` | Flow business number | **Digits only** (`^[0-9]+$`), ≤ 30 chars. Builder pulls title, body and attachments through the API |

⚠ **The Flow field takes a number, not a URL.** The input carries `pattern="[0-9]{4,12}" maxlength="12"`, but that is only the browser's hint — `SrtService.registerFlow` re-checks `^[0-9]+$` against a 30-character limit and rejects anything else. Pasting a Flow URL fails.

A Flow registration also **re-reads the fetched post and stores it as `source_json`**, deliberately dropping the comment list before saving. The stored copy is what the detail screen renders, so the user never has to go back to Flow to read the original.

If the project uses the facet axis, applicable facets are chosen here and written to the **bridge FRD** (`FrdFacet`), not to the SRT row. `chosenFacets` follows the same rule as FRD registration: an empty selection or the `__ALL__` marker expands to every facet on the project, and anything not registered on the project is rejected. Facet definition and its constraints are in [Project setup](04-project-setup.html).

The user does **not** re-enter development-request fields and does **not** choose a processing path.

## States

`Srt.AnalysisState` is `READY` · `ANALYZING` · `COMPLETE` · `REJECTED` · `FAILED`, constrained in the database as well as in Java.

```text
  register / update
        |
        v
     READY ──(SrtAnalysisService.request)──> ANALYZING
                                               |
                         eligible ─────────────┼───────────── not eligible
                                               |                     |
                                               v                     v
                                           COMPLETE              REJECTED
                                               |            (AI says: not a dev change)
                            개발요청서 만들기    |
                                               v                  FAILED
                                        dev_request_id set     (timeout, busy,
                                               |                unreadable output,
                                               v                queue full)
                                            완료
```

**The screen collapses five states into four**, and `devRequestId` wins over everything:

| Screen state | Condition | What the user does |
|---|---|---|
| `분석 중` | `READY` or `ANALYZING` | Wait. Closing the screen preserves the registration |
| `생성 대기` | `COMPLETE` | Review the requirements and criteria, then press `개발요청서 만들기` |
| `확인 필요` | `REJECTED` or `FAILED` | Revise a direct SRT and update it; for a thin Flow original, improve it in Flow and register a **new** SRT. A transient failure can just be retried |
| `완료` | `devRequestId != null` | Open the development request and review before sending |

`Srt.stateLabel()` checks `devRequestId` **before** the enum, which is what makes the completed state override the analysis state. A test pins this: *the development-request delivery state does not overwrite the SRT state*.

**Updating a direct SRT resets the analysis.** `SrtService.update` rewrites the SRT and the bridge FRD, deletes the FRD's items and notes, re-writes the source requirement, and sets the state back to `READY` — so the next status poll starts a fresh analysis. A Flow-registered SRT **cannot be edited at all**; the original belongs to Flow.

## The AI analysis

`SrtAnalysisService` owns the transitions; `SrtAiAnalyzer` runs Claude; `SrtAiAnalysisReader` parses the output.

| Setting | Value |
|---|---|
| Model | `sonnet`, hardcoded in `SrtAiAnalyzer.MODEL` |
| Effort | `low` |
| Tools | `Read(<inputDir>/**)` only |
| Timeout | `builder.ai-run-timeout` |
| Executor | `aiExecutor` — the shared AI pool, see [Claude CLI runtime](05-claude-cli-runtime.html) |

This is the cheapest AI call in the product: a small model at low effort, allowed to read one directory and nothing else. The job is to decide whether the text is a real development change and, if so, to restate it as requirements plus completion criteria against a fixed JSON schema.

**It asks twice at most.** If the reader rejects the first output as off-schema, the analyzer appends the rejection reason to the prompt and asks once more; a second failure raises `AnalysisException`. A test pins both halves: *the reader's rejection is fed back and asked once more*, and *the schema caps the reader's list limits first*.

**Claude's raw errors never reach the screen.** `AnalysisException` carries a written-for-humans message — Claude not connected, timed out, busy, credential lost, or "could not read the analysis result". A test pins exactly this: *Claude API error text is not exposed in the SRT screen exception*.

**Analysis runs isolated** — config, hooks and MCP are all cut, pinned by *SRT analysis runs with config, hooks and MCP disconnected*.

### Two guards against double-running

- `SrtAnalysisService` keeps a `ConcurrentHashMap.newKeySet()` of SRT ids. `running.add(srtId)` fails for a second caller, so a duplicate request returns the current status instead of launching a second Claude.
- `status()` is **self-healing**: if the row says `READY`/`ANALYZING` but the id is not in `running`, the analysis was lost — a restart, or a rejected submission — so it calls `request()` again rather than leaving the SRT stuck in "분석 중" forever.

If the executor queue is full, `TaskRejectedException` is caught, the id is removed from `running`, and the SRT is parked in `FAILED` with a retry message. It is never left claimed.

`completeAnalysis` refuses to store a result that is ineligible, has a blank comment, or has empty requirements or criteria — so `COMPLETE` always means there is something to build a request from.

## Creating the development request

Pressing `개발요청서 만들기` runs asynchronously through `SrtCompletionService`, which hands off to the same `FrdCompletionService` the FRD path uses.

```text
confirm the stored AI analysis
  → lock the SRT row (selectByIdForUpdate)
  → confirm the bridge FRD and that its sourceKind is SRT
  → confirm the SRT text has not changed since analysis
  → prepare the workspace         (worktrees/srt-<srtId>, branch srt/<srtId>)
  → create the development request (createFromConfirmedScope)
  → connect it                     (connectRequest)
  → generate documents and verification material
  → go to the development request detail
```

**The text is re-compared before anything is created.** `prepareDevelopmentRequest` takes the analysed title and content as arguments and throws if they no longer match the stored row — "AI 분석 중 SRT 내용이 변경됐습니다. 다시 생성해 주세요." Without it, an edit landing mid-analysis would produce a request describing text nobody approved.

**It is idempotent at the front.** If `devRequestId` is already set, the method returns the SRT untouched rather than creating a second request. `SrtCompletionService.request` is `synchronized` and keeps a per-SRT progress map, so a double click cannot start two runs.

**A failed creation rolls back the workspace it made.** Pinned by *if creating the development request fails, the worktree made this time is reverted*. The SRT content survives; the user reads the error and presses the button again.

⚠ **A development request number appearing does not mean the work is done.** A test states it directly: *even once the development-request number exists, it is still "분석 중" until the FRD preparation finishes*. The completion state comes from `SrtCompletionService`, not from the presence of an id.

## Routes

All under `/projects/{projectId}/artifacts/srts`, and the list and detail are one screen — the detail is a layer.

| Route | Purpose |
|---|---|
| `GET /` | List, with search over SRT number, title and Flow number |
| `POST /` (`Accept != application/json`) | Register from the form |
| `POST /` (`Accept = application/json`) | Register from the layer, returns `RegistrationStatus` |
| `GET /{srtId}/analysis-status` | Poll the analysis, returns `RegistrationStatus` |
| `POST /{srtId}/dev-request` (form / JSON) | Create the development request |
| `GET /{srtId}/dev-request-status` | Poll creation, returns `CompletionStatus` |
| `POST /{srtId}/update` | Edit a direct SRT before a request exists |
| `POST /{srtId}/delete` | Delete before a request exists |

The same path serves HTML and JSON, split on the `Accept` header, so the layer can post without a second endpoint.

## Ownership

**Whoever registers an SRT owns it.** Others can open and read the detail but cannot update, delete, or create its development request. Two tests cover both halves — *another worker's SRT renders in read-only mode*, and *another worker's change is refused at the server* — so the restriction is not merely a hidden button.

## Deleting

Only before a development request exists. `SrtService.delete` removes the SRT row and the bridge FRD together.

> **The worktree is cleaned before the rows are deleted, and the order is load-bearing.** `ArtifactWorktreePaths` resolves the `srt-` folder and the `srt/` branch by looking the SRT up through `selectByBridgeFrdId`. Delete the row first and that lookup fails, leaving an orphaned worktree nobody can name. The code carries a `⛔` saying exactly this.
>
> ⚠ **A failed cleanup does not block the delete** — it is logged and the deletion proceeds, pinned by *the SRT delete proceeds even when worktree cleanup fails*. An undeletable folder must not strand a row the user asked to remove.

## Flow integration

`FlowPostGateway` / `HttpFlowPostGateway` fetch the post. The key is sealed in `adk_builder_flow_api_key`, registered by a super administrator through `관리 → 시스템 관리`, and **never written into a configuration file**. Timeout is `builder.flow.timeout`, 20s.

If the key is missing or the fetch fails, registration returns to the layer **with the typed business number preserved** — pinned by *when the Flow original cannot be fetched, it returns to the registration layer with the business number kept*. Re-typing a number after a network blip is exactly the friction that makes people give up on a form.

## Disk footprint

An SRT gets its own worktree at `worktrees/srt-<srtId>` on branch `srt/<srtId>`, from `ProjectPaths.srtWorktree` and `ArtifactWorktreePaths`.

⛔ **The folder prefix and the branch prefix must agree.** `ArtifactWorktreePaths` carries a warning that a `srt-` folder on a `frd/` branch is a state nothing downstream can interpret. Both are decided from the same lookup for that reason.

This naming is also how `DevResultReceiver` tells an SRT-sourced return from an FRD-sourced one, using the same rule the sender applies in `DevRequestPackageBuilder.usesWorkspace`. See [development result](11-dev-result.html).

## The table

`adk_builder_srt` — measured against the live schema at v95.

| Column | Type | Notes |
|---|---|---|
| `id` | `varchar(7)` PK | `CHECK (id ~ '^[0-9]{7}$')`, allocated by `IdSequence` |
| `project_id` | `varchar(7)` | |
| `number` | `integer` | `CHECK (number > 0)`, UNIQUE per project, rendered as `SRT-%03d` |
| `source_kind` | `text` | `DIRECT` or `FLOW` |
| `flow_task_number` | `varchar(30)` | |
| `title` / `content` | `varchar(255)` / `text` | both `CHECK`-trimmed non-empty |
| `source_json` | `text` | The stored Flow post; null for a direct SRT |
| `owner_account_id` | `varchar(7)` | The owner |
| `bridge_frd_id` | `varchar(7)` | **UNIQUE**, FK to `adk_builder_frd` |
| `dev_request_id` | `varchar(7)` | **UNIQUE**, FK to `adk_builder_dev_request` |
| `analysis_state` | `text` | `CHECK` over the five states, default `READY` |
| `analysis_message` | `text` | The rejection reason or failure text shown on screen |

**One check constraint encodes the entry rule in the database**: `source_kind = 'DIRECT' AND flow_task_number IS NULL` **OR** `source_kind = 'FLOW' AND btrim(flow_task_number) <> ''`. A Flow SRT without a number, or a direct SRT carrying one, cannot be stored at all.

Both `bridge_frd_id` and `dev_request_id` being UNIQUE is what guarantees the one-to-one chain **SRT → bridge FRD → development request**.

## Code map

| File | Role |
|---|---|
| `srt/SrtService.java` | Registration, the bridge FRD, update, delete, analysis storage, request preparation |
| `srt/Srt.java` | The record, two enums, and the four screen labels |
| `srt/SrtAnalysisService.java` | Async analysis, the `running` guard, self-healing status |
| `srt/SrtAiAnalyzer.java` | The Claude call — model, isolation, one retry |
| `srt/SrtAiAnalysisReader.java` | Parses and validates the structured output |
| `srt/SrtAiAnalysis.java` | Eligibility, rejection reason, comment, requirements, criteria |
| `srt/SrtCompletionService.java` | Async development-request creation, progress map |
| `srt/SrtController.java` | The eight routes, HTML and JSON on the same paths |
| `srt/SrtMapper.java` | Including `selectByIdForUpdate` and `selectByBridgeFrdId` |
| `srt/SourceAttachment.java` | Flow attachment display, with a fallback name |

## What the tests guarantee

Test names here are Korean sentences stating the guarantee. Translated:

**`SrtServiceTest`** — a direct SRT waits after registration and the create request returns to the detail immediately · async registration returns analysis state and detail URL as JSON · facets chosen at registration are preserved on the internal FRD · an SRT can be edited and deleted before the development request exists · another worker can only read · a write request on an SRT-born development request still reaches the controller · the screen state collapses into four · the delivery state does not overwrite the SRT state · **delete cleans the worktree before deleting the row** · **delete proceeds even when worktree cleanup fails** · a Flow-registered SRT cannot be edited.

**`SrtAnalysisServiceTest`** — a registered SRT is analysed and the result stored · when it is not a development request, the "needs review" reason is stored.

**`SrtAiAnalyzerTest`** — the original is sent to Claude and a structured result read back · Claude API error text is not exposed in the screen exception · analysis runs with config, hooks and MCP disconnected · the instruction treats the whole input folder as material and states comment and language on rejection · a reader rejection is fed back and asked once more.

**`SrtAiAnalysisReaderTest`** — a development request yields tidied requirements and completion criteria · an unrelated request yields a rejection reason with empty definitions · claiming eligible while leaving criteria empty is rejected · the schema caps the reader's list limits first.

**`SrtCompletionServiceTest`** — an SRT also gets the same post-request AI preparation as an FRD · no request is created when the stored analysis cannot be confirmed · it stays "분석 중" until FRD preparation finishes even after a request number exists · a failed creation reverts the worktree made in that attempt.

**`SrtControllerTest`** — an empty list still renders the menu and the registration layer model · the layer does not open without a connected Claude · registration is refused without Claude, including the async route · a failed Flow fetch returns the layer with the number preserved · successful registration starts analysis and returns to the detail · pressing create prepares the request · an AI rejection returns to the detail with the reason preserved.

Plus `SrtFlowTest` and `SrtTemplateContractTest`.

## Traps

1. **Do not add SRT-specific requirement tables.** Requirements and criteria belong to the bridge FRD as `FrdItem` and `FrdAnalysisNote`. That is what lets the development request be built by the same call the FRD path uses.
2. **Do not delete the SRT row before cleaning its worktree.** Path and branch resolution reads the row; deleting first orphans the folder.
3. **Do not let the folder prefix and branch prefix diverge.** `srt-` folder with a `frd/` branch is uninterpretable downstream.
4. **Do not surface Claude's raw error text.** `AnalysisException` messages are written for the person reading the screen.
5. **Do not skip the text re-comparison before creating a request.** An edit landing mid-analysis would otherwise produce a request for text nobody approved.
6. **Do not treat a present `devRequestId` as "finished".** Preparation continues after the id exists.
7. **Do not accept a Flow URL where a business number is expected.** The server takes digits only; the browser pattern is a hint, not the rule.
8. **Do not let a rejected executor submission leave an SRT claimed.** `running.remove` in the failure path is why a queue-full SRT can be retried.

## Related

- [Development request](10-dev-request.html) — what an SRT produces
- [FRD wizard](06-frd-wizard.html) — the longer path, and the backend-only fast track
- [Claude CLI runtime](05-claude-cli-runtime.html) — the executor, isolation and timeouts
- [Project setup](04-project-setup.html) — registering the Flow API key, and facets
- [Development result](11-dev-result.html) — how an SRT-sourced return is recognised
