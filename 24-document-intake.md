# Intake & document reading

> Reference documentation — `docs/adp/`. Describes the system as built, not as planned.
> The code is the source of truth; this file points at it. Verified against the tree on 2026-09-17.
> **This page covers two things, and only one of them is retired.** Read §1 before acting on anything here.

## 1. Two halves — read this first

The `intake` package holds a **retired workflow** and a **live capability**, in the same 28 files.
Confusing them in either direction causes a real mistake, so the split is the first thing on the page.

| | Status | What it is |
|---|---|---|
| **The requirement chain** — received document → requirement → requirement definition → BRD | **Retired 2026-08-20** | The old front end of the product. Removed from the work flow. Data, routes and tables survive. |
| **Reading an uploaded file** — read check, text extraction, multimodal transcription | **Live** | Still runs today. It is how a file that a server cannot read becomes text at all. |

⛔ **Do not make the requirement chain a precondition for anything new.** The current work flow starts
at the FRD wizard, where a planner types the requirement directly. Nothing downstream waits on a
received document. Canonical: `docs/artifacts.md`, and [What ADP Builder is](00-overview.html).

⛔ **Do not read that as "document reading is dead."** The read check and the multimodal path are
wired, tested and reachable. They are the live half, and §3–§5 are about them.

⚠ **The word "intake" means three different things in this codebase.** Only the first is this page:

| Where you see it | What it means |
|---|---|
| `com.bizplay.builder.intake` | this package — received documents and requirements |
| `builder.developer.intake-path` | the DEVELOPER delivery channel's endpoint — see [Development request](10-dev-request.html) |
| `intake.FlowPostGateway` | fetching a Flow post, used by SRT — see [SRT fast track](09-srt.html) |

## 2. What the chain was, and why it went

The original product started from documents the planning team received: minutes, work requests,
proposals. A planner uploaded one, AI extracted candidate requirements from it, the planner confirmed
or excluded each, and those fed a requirement definition and then a BRD.

That chain was removed from the flow on **2026-08-20**. The work unit became the FRD, and the
requirement became something a planner writes directly.

**The code was not deleted, and that is deliberate** — existing engagements have rows in these tables,
and the screens still render them. What changed is that nothing new begins here.

**The screens are unreachable from the menu but reachable by URL.** `ShellContract` keeps
`received-docs` and `requirements` in `ARTIFACT_KEYS` while leaving them out of `ARTIFACT_MENU_KEYS`,
with the reason stated in the field's own comment: a hidden screen can still be opened directly, so
the key has to stay valid or the shell contract rejects the render. `definitions` and `brd` remain in
`ARTIFACT_KEYS` for the same reason.

**Two removals inside the chain are worth knowing, because both were reversals of "AI always helps":**

- **2026-08-15 — AI no longer tidies every document.** Previously every received document was passed
  through `claude` for a first pass. ⛔ `normalize()` is not to be restored: a person's typed text was
  being rewritten by AI, which collided head-on with the rule that the original is preserved verbatim.
  The `NORMALIZE` value survives in `run_kind` as history.
- **2026-08-15 — the content-review step went.** `REVIEW_REQUIRED` was folded into `READY`, and
  `adk_builder_intake.process_type` was dropped outright (`V10`).

## 3. What still runs — deciding how a file can be read

`DocumentReadCheck` answers one question about an uploaded file: **how can this be read?**

```text
직접 입력 (typed)                      →                                    READY
attachment · server extracts text      →                                    READY
attachment · no text, human-readable   → QUEUED → PROCESSING →              READY
attachment · unreadable either way     →                                    FAILED
```

`Readability` has three values, and the middle one is the 2026-08-15 addition:

| Value | Meaning |
|---|---|
| `READABLE` | The server can extract the text itself. No AI is called. |
| `NEEDS_UNDERSTANDING` | The server cannot, **but a human eye could** — scanned PDFs and images. Goes to multimodal. |
| `UNREADABLE` | Neither path works. The original is still kept; the next step closes. |

⛔ **The test is "did text actually come out", not "did the read succeed".** The reason is a measured
failure from 2026-08-09 (issue `#7`): **a Hancom document returns its compressed bytes as text with no
error at all.** The absence of an exception is what makes it dangerous — AI then reads garbage and
invents plausible-looking requirements, and nobody notices.

⛔ **Compressed office formats do not go to multimodal.** Hancom and OOXML files are zip containers;
a multimodal model cannot read the XML inside a zip either. Only scans and images qualify.

⚠ **The verdict never blocks the upload.** Preserving the received original is the rule. What the
verdict gates is the *next step*.

⚠ **`NEEDS_UNDERSTANDING` is not a failure** and must not be rendered as an error.

## 4. Extracting the text

`DocumentTextExtractor` is the other half of the pair — the read check *measures*, this one *extracts*.
They are not split by layer; they are together because deciding requires attempting, so **the knowledge
of how to run the PDF tool had to live in exactly one place.**

⚠ **Extensions are not trusted. The leading bytes are.** A Hancom file arrives renamed to `.txt`. The
extractor reads `HEAD_BYTES = 4096` and matches magic bytes: `%PDF-`, PNG, JPEG, GIF, BMP, TIFF
(both byte orders), RIFF, and zip.

⛔ **It throws rather than returning an empty string.** This repository was burned here twice — the
Hancom case above, and a scanned PDF that ran the tool cleanly and produced zero characters. **An empty
string passed off as success is what lets AI invent requirements out of nothing.** So: when in doubt,
fail. `MIN_TEXT_LENGTH = 1`; an empty file fails too.

⚠ **Images are rejected explicitly rather than falling through to the plain-text branch.** PNG and JPEG
headers contain literal strings such as `PNG` and `IHDR`, so a byte-ratio check would see **more than
zero characters and call it readable.**

⚠ **The PDF tool's presence is probed once and cached.** Development machines lack `poppler-utils`
while production Linux can install it (`apt-get install poppler-utils`), so refusing PDFs by extension
would mean installing the tool on the server changes nothing. The cache is re-evaluated on restart.

A plausible-UTF-8 floor of `MIN_TEXT_RATIO = 0.9` catches binary files with neither magic bytes nor a
recognisable extension.

## 5. The multimodal path — the live AI route

This is the **second AI provider in the product.** The first is the `claude` CLI — see
[Claude CLI runtime](05-claude-cli-runtime.html). This one is an HTTP call to Gemini.

`DocumentUnderstandingClient` is the interface; `GeminiDocumentUnderstanding` is the implementation.

⛔ **Callers must not know the implementation class.** The single swap point is the whole reason the
interface exists.

⛔ **API key, model name and endpoint are never in code** — all of them come from
`DocumentUnderstandingProperties`. If the key is absent, `available()` is false and the class does
nothing at all.

### What it is told to do

⛔ **It is told to transcribe, not to summarise.** The output of this layer is *the document's text*,
not its gist — anything invented here becomes the foundation every later requirement stands on. The
instruction spells out: do not summarise, do not fill gaps, rebuild tables as Markdown tables, carry
information out of diagrams, leave names/dates/numbers exactly as written, and **mark anything
illegible as `[확인 필요]` rather than guessing.** Without that last rule, a blurry scan's blank spots
get filled with plausible sentences and nobody can tell.

### Operating it

| Setting | Value | Note |
|---|---|---|
| `builder.document-understanding.model` | `gemini-3.6-flash` | see the expiry trap below |
| `timeout` | `3m` | |
| `max-inline-bytes` | `15728640` (15 MB) | Base64 inflates payloads by 4/3, so the 20 MB upload cap would otherwise exceed the provider's limit |
| retries when busy | 3 attempts, 3 s backoff doubling to 6 s | ⛔ do not raise — each attempt re-uploads the whole file |

⛔ **Model names expire, and picking the newest is wrong.** Both halves are measured:

- The default first written on 2026-08-16, `gemini-2.5-flash`, **was already a dead name the day it was
  typed** — 2.0 closed on 2026-06-01 and 2.5 returns 404 to newly issued keys.
- The freshly released `gemini-3.7-flash` returned **503 (`experiencing high demand`) on both attempts**
  with the same document, while `gemini-3.6-flash` returned **200 on both.** This layer transcribes
  characters; it does not need the newest intelligence, it needs the model that is not busy.

⚠ **If attachments fail with nothing but "내용 분석 오류", suspect this setting first.** The provider's
own deprecations page is canonical for which names are alive. The point of holding the name in
configuration rather than code is that the next expiry needs no code change.

⛔ **These properties are deliberately separate from `BuilderProperties`.** That record holds values
whose absence stops the server booting. Multimodal reading applies only to scanned PDFs and images, so
making the key mandatory would ground an entire engagement that never uploads one. **Missing key closes
that one path; the server still starts.**

⚠ **Not yet measured against the live API.** Sending internal documents to an external provider was
approved on 2026-08-16, but the key has not been issued, so the request body shape and response parsing
are written from documentation only. **Do not read "will work" as "does work."**

### The worker

`DocumentProcessingWorker` is `@Async`, and ★ **it is a separate bean on purpose.** ⛔ Do not fold it
into `IntakeService` or `DocumentProcessingService`: a self-invocation skips the Spring proxy, so
`@Async` **never activates at all** and a multi-minute job blocks the upload request. `AiRunWorker`
records the identical trap.

⛔ **What the model returns is not written straight into the document-content field.** That field holds
**text a person has confirmed.** Skipping confirmation puts a misread table directly into requirement
analysis.

## 6. States

| Enum | Values |
|---|---|
| `ReceivedDocument.ContentState` | `QUEUED` · `PROCESSING` · `READY` · `FAILED` |
| `ReceivedDocument.DocumentType` | `FLOW` · `MEETING_MINUTES` · `OTHER` |
| `Intake.RequirementState` | `NOT_STARTED` · `RUNNING` · `REVIEW_REQUIRED` · `COMPLETED` · `FAILED` |
| `Requirement.ReviewState` | `DRAFTED` · `CONFIRMED` · `EXCLUDED` |
| `DocumentProcessingRun.State` | `WAITING` · `RUNNING` · `SUCCEEDED` · `FAILED` |
| `DocumentProcessingRun.Kind` | `EXTRACT` · `NORMALIZE` (the second is retired) |

⛔ **`NOT_STARTED` is neither an error nor a to-do.** A document kept purely for reference sits there
permanently. Do not colour it red or label it "pending" — the enum's own comment says so.

⛔ **Do not restore `PENDING`, `EXTRACTING` or `NORMALIZING` to `ContentState`.** All three assumed
"AI always does something", which is the assumption that was removed.

⚠ Both `ContentState` and `DocumentType` are nested enums, so mapper XML refers to them with `$`.

## 7. Requirement analysis — the retired half

`RequirementAnalysisWorker` draws requirement drafts out of confirmed document content. **It runs only
when a person presses the button** — never automatically. ★ It is a separate bean for the same
`@Async` proxy reason as above.

`RequirementReviewService` handles the three human judgements: **confirm, exclude, edit the text.**

⭐ Its heart is `rollUpIntake`: when every requirement in one intake has been decided, the intake flips
to `COMPLETED`. Both screens exist to let a person reach that moment.

⛔ **No AI calls belong in that class.** Confirming and "generate the definition" were deliberately
separated — confirmation does not produce the next artifact.

⚠ **No repository commit happens there either.** The "requirement confirmed" commit belongs to the
frozen push design; if it is ever thawed, this is where it would be called.

Re-analysis is guarded: ⛔ not while a run is in flight (two overlapping attempts would have the later
one overwrite the earlier), and ⛔ not once analysis has completed (confirmed results would be lost).

## 8. Screens and routes

| Screen | Method + route | Template |
|---|---|---|
| Received documents | `GET /projects/{projectId}/artifacts/received-docs` | `artifacts/received-docs.html` |
| Register form | `GET …/received-docs/register` | `artifacts/received-doc-register.html` |
| Register | `POST …/received-docs` | |
| Detail | `GET …/received-docs/{intakeId}` | `artifacts/received-doc.html` |
| Retry content analysis | `POST …/{intakeId}/reprocess` | |
| Analyse requirements | `POST …/{intakeId}/analyze-requirements` | |
| Delete requirements | `POST …/{intakeId}/delete-requirements` | |
| Delete intake | `POST …/{intakeId}/delete` | |
| Download original | `GET …/{intakeId}/file` | |
| Requirements | `GET …/artifacts/requirements` | `artifacts/requirements.html` |
| Requirement detail | `GET …/requirements/{requirementId}` | `artifacts/requirement.html` |
| Confirm | `POST …/{requirementId}/confirm` | |
| Exclude | `POST …/{requirementId}/exclude` | |
| Edit text | `POST …/{requirementId}/content` | |

⚠ Retry is offered only for documents that **failed while multimodal was running** — not for every
error. ⛔ Do not widen it: a button that changes nothing when pressed is worse than no button.

## 9. Data model

| Table | Notes |
|---|---|
| `adk_builder_intake` | One receipt. `step`, `requirement_state`. ⚠ `process_type` was **dropped** in `V10` |
| `adk_builder_received_document` | `intake_id` is **unique** — one document per intake. `document_type`, `content_state`, `typed_content`, `extracted_content`, `server_path`, `byte_size`, `meeting_at`, `attendees`, `content_confirmed_at` |
| `adk_builder_requirement` | `number` per project, `unique (project_id, number)`, `title`, `body`, `screen_hints`, `review_state` |
| `adk_builder_document_processing_run` | `run_kind`, `state`, `provider_run_id`, `error_message`, `input_tokens`, `output_tokens`, `cost_amount`, timings |
| `adk_builder_intake_facet` | PK `(intake_id, name)`, with a composite FK to `(project_id, name)` on `adk_builder_project_facet` |

⚠ **A received document holding an application facet is what stops that facet being deleted.** The
constraint is described from the side that enforces it, with its measured details, in
[Project setup](04-project-setup.html) — deliberately not restated here, because one rule written in
two places ages in two directions.

The `CHECK` constraints were narrowed as the design shrank: `document_type` went
`MEETING_MINUTES/WORK_REQUEST/PROPOSAL/OTHER` → `+FLOW` (`V9`) → `FLOW/MEETING_MINUTES/OTHER` (`V12`),
and `content_state` lost `REVIEW_REQUIRED` in `V10`. Canonical ERD: [Data model](02-data-model.html).

## 10. Files on disk

Originals are stored at `<data-root>/projects/<projectId>/received/`, named
`<intakeId>-<safeFileName(originalName)>`.

⛔ **Outside `clone/`, deliberately.** A received document is not something to push to the planning
repository — see [Git layer](git.html).

⛔ **The original filename never reaches the path unsanitised.** `IntakeService.safeFileName` strips
path separators and `..`.

Multimodal runs get their own tree at `<data-root>/doc-runs/<runId>/`, separate from `runs/<runId>/`
for AI runs, because both sequences are 7 digits and would otherwise collide.

Upload limits are Spring's: `max-file-size: 20MB`, `max-request-size: 25MB`.

## 11. Code map

| File | Role |
|---|---|
| `intake/IntakeController.java` | Nine routes for received documents |
| `intake/RequirementController.java` | Five routes for requirements |
| `intake/IntakeService.java` | Registration, storage, deletion, re-analysis guards |
| `intake/DocumentReadCheck.java` | The three-way readability verdict |
| `intake/DocumentTextExtractor.java` | Magic bytes, extraction, "never return empty" |
| `intake/DocumentProcessingWorker.java` | Async multimodal run — separate bean by necessity |
| `intake/DocumentProcessingService.java` | Run bookkeeping |
| `intake/DocumentProcessingBootSweep.java` | Reclaims runs interrupted by a restart |
| `intake/RequirementAnalysisWorker.java` | Async requirement extraction — separate bean |
| `intake/RequirementReviewService.java` | Confirm / exclude / edit, and `rollUpIntake` |
| `intake/FlowPostGateway.java`, `HttpFlowPostGateway.java` | Flow post fetch — also used by [SRT](09-srt.html) |
| `ai/DocumentUnderstandingClient.java` | The provider-neutral interface |
| `ai/GeminiDocumentUnderstanding.java` | The only place that knows the provider |
| `config/DocumentUnderstandingProperties.java` | Key, model, timeout, inline cap |

## 12. Guarantees covered by tests

Test method names in this project are Korean sentences stating what is guaranteed, by convention.
Translated:

**`DocumentReadCheckTest`** — a Hancom document is compressed bytes, so no text comes out and it is
marked unreadable · plain text reads · a PDF on a machine without the tool is marked unreadable, not
"unknown" · a Hancom file merely named `.txt` is caught by its leading bytes · a binary file with
neither magic bytes nor an extension is caught by its character ratio · an empty file is not marked
readable.

**`DocumentTextExtractorTest`** — plain text comes out intact · a compressed document reaching this
point is rejected rather than passed through silently · a PDF with no text is not passed off as success
whether or not the tool is present · an empty file is not passed off as success.

**`DocumentProcessingWorkerTest`** — typed input is not picked up by the worker · an attachment the
server can extract is not picked up either · a PDF with no text is read by multimodal and requirement
analysis opens immediately afterwards · a missing multimodal configuration is reported as a
configuration problem · failure to reach the provider is not blamed on the document · a busy provider
does not tell the user to change the document · a failed analysis settles as an error and can be
retried · compressed documents are not sent to multimodal either · only documents that failed *during*
multimodal get the retry.

Others: `IntakeUploadTest`, `RequirementAnalysisTest`, `RequirementScreenTest`,
`HttpFlowPostGatewayTest`, `V7LegacyDataMigrationTest`.

```bash
./mvnw test -Dtest='Document*Test,Intake*Test,Requirement*Test'
```

## 13. Traps

Each one is a bug that actually happened.

1. **Do not treat "the read succeeded" as "text came out."** Hancom returns compressed bytes with no
   exception, and AI then invents requirements from garbage.
2. **Do not return an empty string from extraction.** Throw. An empty success is indistinguishable from
   a real document downstream.
3. **Do not trust file extensions.** Hancom files arrive renamed to `.txt`.
4. **Do not let images fall through to the text branch.** PNG/JPEG headers contain enough literal
   characters to pass a ratio check.
5. **Do not send zip-based office documents to multimodal.** It cannot read XML inside a zip.
6. **Do not block the upload on an unreadable verdict.** Preserving the original is the rule; the
   verdict gates the next step only.
7. **Do not render `NEEDS_UNDERSTANDING` as an error.** It is a routing decision.
8. **Do not colour `NOT_STARTED` as pending or failed.** Reference-only documents live there.
9. **Do not put the async workers inside `IntakeService`.** Self-invocation bypasses the proxy and
   `@Async` silently never fires.
10. **Do not write the model's output straight into the confirmed-content field.** A misread table
    would flow into requirement analysis unreviewed.
11. **Do not ask the model to summarise.** This layer transcribes; invention poisons everything built
    on it.
12. **Do not pick the newest model.** Measured: `3.7-flash` 503 twice, `3.6-flash` 200 twice.
13. **Do not hardcode the model name or API key.** Names expire; configuration is the fix.
14. **Do not merge `DocumentUnderstandingProperties` into `BuilderProperties`.** A missing key must
    close one path, not stop the server.
15. **Do not raise the busy-retry count.** Each attempt re-uploads the entire file.
16. **Do not restore `normalize()`,** or `PENDING`/`EXTRACTING`/`NORMALIZING`. They encoded "AI always
    does something", which was removed for rewriting people's own words.
17. **Do not reopen re-analysis while a run is active or after it completed.** Overwrites and lost
    confirmations respectively.
18. **Do not add AI calls to `RequirementReviewService`.** Confirming is not generating.
19. **Do not use the raw filename in a path.** `safeFileName` exists for `..` and separators.
20. **Do not build new features on the requirement chain.** It is history. The FRD wizard is the entry
    point.
