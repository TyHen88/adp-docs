# Policy & standard terms

> The two business documents a project defines for itself — the policy document and the standard terminology — how a first draft is generated in batches rather than one long run, and how they reach the AI without being pasted into every prompt.

Package: `com.bizplay.builder.businesslanguage` (34 files).
Screens: `artifacts/business-language.html`, `business-language-history.html`.
Routes: `/projects/{projectId}/artifacts/business-language`.
Menu: `정책·표준용어`.

## The two documents

`BusinessDocumentKind`:

| Kind | What |
|---|---|
| `POLICY` | The business policy document — rules the screens must obey |
| `STANDARD_TERMS` | Standard terminology — the agreed word for each concept |

Both are **owned by the project and edited in Builder** (`adk_builder_business_document`), with full revision history (`adk_builder_business_document_revision`).

## Why they exist

They are what makes `문구·용어 맞추기` in the [FRD workbench](07-frd-workbench.html) possible. Without them registered, that AI action **is not run at all** — the user is told to register the documents first, rather than the AI inventing a standard.

The rule it applies: words with the same meaning but different spelling get corrected; words whose business meaning would change, and anything with no basis in these documents, are left as `확인 필요`.

## Getting them to the AI — `BusinessLanguageContextWriter`

⭐ The database is the source of truth, but a prompt cannot carry a whole policy document. So the writer turns both documents into **an index plus fragments the AI reads only where it needs to**, under `<inputDir>/business-language`:

| Writer | Produces |
|---|---|
| `BusinessPolicyIndexWriter` | A policy index plus a sections directory |
| `BusinessTermIndexWriter` | A term index plus a sections directory |

**The term index carries every term name and synonym on one page.** That is the point of it: one read tells the AI whether a word is governed at all, and only then does it open the one batch that defines it.

⛔ **If either document is missing, the writer returns empty** rather than writing a partial context. A run then proceeds without business language instead of with half of it.

That context is loaded on a **new** session. ⚠ For `문구·용어 맞추기` it is reloaded even on a **resumed** session, because that is the one request that cannot work without it — every other request loads it only on a new session. See the `--system-prompt-snapshot` note in [Claude CLI runtime](05-claude-cli-runtime.html) for why resumed sessions differ.

> ⛔ **The instruction block has two forms, and the reason is a real collision.** `ContextFiles.instruction(grepAvailable)` exists because the screen-picking run using the codebase MCP **strips `Grep` and instructs the model not to grep**, while this block was telling it to grep — two contradictory orders in one prompt (2026-09-10). Policy sections and term batches live in the input folder, **outside the clone**, so the MCP index cannot see them either. That run therefore picks from the index and uses `Read` only.

## Seeding a first draft

A project rarely starts with these documents written, so seeding generates a first draft from the `domains` material already in the planning repository.

`POST /seed` refuses in three distinct ways before any AI runs:

| Guard | Message |
|---|---|
| Documents already exist | "이미 초안이 만들어져 있습니다." |
| No `domains` documents in the clone | "저장소의 domains 문서를 찾지 못했습니다…" |
| `seeds.begin(...)` did not claim the row | "초안을 이미 만들고 있습니다." |

The third is the atomic one — the claim is a single-row update, so two people pressing at once cannot both start.

### Why it is split into parts — measured, not assumed

⭐ **One run doing the whole thing fails in two different ways, and the numbers are recorded** (2026-09-02):

| Attempt | Result |
|---|---|
| Finished in 7m38s | Compressed 4,938 lines of domain rules into 94 policy bullets — roughly 78:1 |
| Re-run of the same input | Hit the 20-minute wall and produced **nothing at all** |

Worse, the relationship was **inverse** — the larger the file, the less came back. A 461KB file yielded 3 bullets; a 192KB file yielded **zero**. So the split is not about speed. A single run silently under-reads large input, and a failure costs the entire draft rather than one piece.

### How the batches are decided — `BusinessLanguageBatches`

Domain markdown is grouped by **byte total**, largest-first, first-fit, against `POLICY_BATCH_LIMIT_BYTES` = 250,000.

⚠ **The limit is a target, not a wall.** A single file larger than the limit cannot be split, so it becomes its own batch.

⛔ **The sort is size descending, then path ascending — and the second key is not decoration.** Two files of equal size would otherwise order arbitrarily, so a retry could group the batches differently and lose the correspondence with the parts already stored.

⚠ **Batching does not read the files, only their sizes.** Keeping it pure is what makes it unit-testable and deterministic: the same clone always yields the same batches, so a retry inherits the previous run's part numbering.

## The three state machines

Seeding tracks a run, its parts, and its merges **separately**, because they fail separately.

```text
BusinessDocumentSeedState        RUNNING → DONE | FAILED          the run as a whole
BusinessDocumentSeedPartState    PENDING → RUNNING → DONE | FAILED   one batch
BusinessDocumentSeedMergeState   PENDING → RUNNING → DONE | FAILED   parts → one document
```

`BusinessDocumentSeedDispatcher` drives it:

- **Dispatch happens `AFTER_COMMIT`** (`@TransactionalEventListener`), so the worker never starts against a row that has not landed.
- **A full queue is a recorded failure**, not a dropped request — `TaskRejectedException` becomes `fail(projectId, "QUEUE_REJECTED")`.
- ⭐ **On boot, every run still marked `RUNNING` is closed as `SERVER_RESTARTED`** (`@EventListener(ApplicationReadyEvent)`). Without this, a restart mid-seed would leave the project permanently unable to start another draft, because the "already generating" guard would keep matching.

Failure reasons are short codes in an 80-character column, which is why they read like `QUEUE_REJECTED` and `SERVER_RESTARTED` rather than sentences.

### What the parts guarantee

From `BusinessDocumentBatchedSeedRunner` and the part mapper:

- **Only unfinished batches run.** A finished batch is never redone, and a retry picks up only `FAILED` ones.
- **Two workers cannot claim the same batch** — the claim is atomic.
- **One batch failing does not stop the others**, and does not delete their fragments.
- **Merging waits for every batch.** If even one is unfinished, nothing merges.
- **A failed merge does not delete the fragments** — it closes and leaves them for a retry.
- **Policy and terms have independent part numbering**, which the primary key `(project_id, kind, part_no)` enforces.
- **The two merges are independent.** A successful policy merge survives a failed terms merge and is not re-run.
- **Source references are collected without duplication** across fragments before the document is written.

⭐ **Standard terms are extracted from the completed policy fragment of the same number**, not from the raw domain files. Terms therefore describe the policy that was actually produced, rather than a second independent reading of the same input.

⚠ **If the input fingerprint changes, a previous merge result is discarded and prepared again** — otherwise a merge would combine fragments from two different readings of the repository.

⛔ **A draft with no term rows is rejected with a specific failure code**, not saved as an empty document. And a single-batch draft still **excludes generic UI operation words**, so "저장", "취소" and the like do not become business terminology.

When a seed closes, its parts for that project are deleted; the documents and their revisions are what remain.

## Editing, revisions and restore

| Route | Action |
|---|---|
| `GET /` | The document screen |
| `POST /policy` | Save the policy document |
| `POST /terms/new` | Add a term |
| `POST /terms/{termIndex}` | Update one term row |
| `POST /terms/{termIndex}/delete` | Delete one term row |
| `POST /upload` | Upload a document |
| `POST /seed` | Start seeding |
| `GET /policy/download` | Download the policy |
| `GET /history` | Revision history |
| `POST /history/restore` | Restore a revision |

**Every save writes two things** — the current document and a new revision row. `BusinessDocumentRevisionType` records why a revision exists: `INITIAL_DRAFT`, `EDIT` or `RESTORE`.

⭐ **Restoring an old revision creates a new `RESTORE` revision; it does not rewind history.** The document returns to the earlier content while the record of every step, including the restore, stays intact.

**A term edit touches one row.** Updating a single term rewrites just that row and leaves a new revision, rather than rewriting the whole terminology document.

### The history view compares in human units

`BusinessDocumentHistoryService` diffs in units a person can check — **policy items** for `POLICY`, **term rows** for `STANDARD_TERMS` — not as raw text. `BusinessDocumentChangeType` marks each as `ADDED`, `MODIFIED` or `REMOVED`, which `business-language.css` colours green, yellow and red.

**Per-term "last modified" comes from the revision in which that row actually changed** (`StandardTermAudit`), not from the document's `updated_at`. Editing one term therefore does not restamp every other term as recently changed. ⚠ **When there is nothing to audit, the revision history is not read at all** — the audit is skipped rather than scanning the whole history to produce an empty answer.

## Tables

Measured against the live schema at v95.

**`adk_builder_business_document`** — primary key `(project_id, kind)`, so **one row per kind per project**. This is the current document, not a history.

| Column | Type | Notes |
|---|---|---|
| `project_id` / `kind` | `varchar(7)` / `varchar(30)` | PK. `kind` CHECK-constrained to the two values |
| `content` | `text` | `CHECK (length(trim(content)) > 0)` — an empty document cannot be stored |
| `source_refs` | `text` | JSON list, default `[]`, via `JsonStringListTypeHandler` |
| `updated_at` / `updated_by` | `timestamptz` / `varchar(7)` | `updated_by` FK to the account |

`adk_builder_business_document_revision` references `(project_id, kind)` as a **composite FK with `ON DELETE CASCADE`** — revisions cannot outlive their document.

**`adk_builder_business_document_seed_part`** — primary key `(project_id, kind, part_no)`, which is what keeps policy and term numbering from colliding.

| Column | Notes |
|---|---|
| `part_no` | `CHECK (part_no > 0)` |
| `scope` | The batch's assigned input |
| `state` | CHECK-constrained to the four part states |
| `content` | Nullable while pending |
| `failed_reason` | `varchar(80)` — short codes |
| `started_at` / `finished_at` | |

⭐ **One CHECK constraint enforces the invariant that matters**: `state <> 'DONE' OR length(trim(coalesce(content,''))) > 0`. A batch **cannot be marked done with nothing in it** — the database refuses, so an empty fragment can never be merged into a document.

Plus `adk_builder_business_document_seed` (the run) and `adk_builder_business_document_seed_merge` (the merge per kind).

## Code map

| File | Role |
|---|---|
| `BusinessLanguageController.java` | The eleven routes |
| `BusinessDocumentService.java` | Save, term CRUD, restore, `hasDomainDocuments` |
| `BusinessDocumentSeedService.java` | Start guards, part planning, closing a run |
| `BusinessDocumentSeedDispatcher.java` | After-commit dispatch, queue-full failure, boot cleanup |
| `BusinessDocumentBatchedSeedRunner.java` | Runs the unfinished batches, then merges |
| `BusinessDocumentSeedWorker.java` | One batch's AI run |
| `BusinessLanguageBatches.java` | The size-based grouping, with the measurements in its javadoc |
| `BusinessLanguageContextWriter.java` | Index plus fragments for a run |
| `BusinessPolicyIndexWriter.java` · `BusinessTermIndexWriter.java` | The two indexes |
| `BusinessDocumentHistoryService.java` | Revision comparison in human units |
| `BusinessLanguageMarkdown.java` | Parses and renders the markdown form |
| `StandardTerm.java` · `StandardTermAudit.java` | The term model and per-row change provenance |
| `JsonStringListTypeHandler.java` | MyBatis handler for the JSON list columns |
| `BusinessLanguagePartAiGateway.java` · `BusinessLanguageAiGateway.java` | The AI call sites |

Canonical plan: `docs/superpowers/plans/2026-08-31-plan-business-language.md`.

## What the tests guarantee

Nineteen test classes. Translated from their Korean names:

**Batching** (`BusinessLanguageBatchesTest`) — a file over the limit becomes its own batch · small files gather into one batch within the limit.

**Parts** (`BusinessDocumentSeedPartMapperTest`) — a stored batch returns its assigned input unchanged · two workers cannot claim the same batch · a finished batch is never claimed again · only failed batches are re-claimed · one batch's failure does not delete a neighbour's fragment · policy and term numbering do not collide · re-inserting does not overwrite a finished batch · closing a draft deletes that project's batches.

**Runner** (`BusinessDocumentBatchedSeedRunnerTest`) — finished batches are not re-run · only unfinished ones run · one failure still lets the rest run · nothing merges until every batch is done · a failed merge closes without deleting fragments · source references are collected without overlap · only fragment bodies go to the merge step · term batches are drawn from the completed policy fragment of the same number · a failed terms merge does not re-run a successful policy merge.

**Merge** (`BusinessDocumentSeedMergeMapperTest`) — a successful policy merge survives a terms-merge failure · a changed input fingerprint discards the previous merge result and prepares again.

**Seed service** (`BusinessDocumentSeedServiceTest`) — policy and terms are planned from the same domain batches · a draft with no term rows is rejected with a specific failure code · a project already generating does not start twice · no AI work starts without `domains` documents · saving a draft also records the first revision of both documents · a single-batch draft still excludes generic UI operation words · a whole-run failure makes running batches and merges retryable · validation failure codes are recorded on the run state.

**Documents** (`BusinessDocumentServiceTest`) — saving the policy stores both the current version and a new revision · restoring an old revision leaves a new restore revision · editing one term row updates only that row and leaves a new revision · a term's last-modified comes from the revision where that row changed · only the selected term is audited · no audit means the revision history is not read.

**History** (`BusinessDocumentHistoryServiceTest`) — the policy distinguishes added, modified and removed per item · terms distinguish them per term.

Plus `BusinessLanguageContextWriterTest`, `BusinessPolicyIndexWriterTest`, `BusinessTermIndexWriterTest`, `BusinessLanguageMarkdownTest`, `BusinessDocumentSeedWorkerTest`, and the screen/view tests.

## Traps

1. ⛔ **Do not generate the draft in one run.** Measured: large input silently yields less, and a single failure costs the whole draft.
2. ⛔ **Do not sort batches by size alone.** Equal sizes reorder, and a retry then regroups and loses the stored parts' correspondence.
3. ⛔ **Do not make batching read file contents.** Purity is what makes it deterministic across retries.
4. ⛔ **Do not delete fragments when a merge fails.** The retry needs them.
5. ⛔ **Do not let a part reach `DONE` empty.** The database check prevents it; do not work around it.
6. ⛔ **Do not leave `RUNNING` runs after a restart.** The boot listener closes them, otherwise the project can never start another draft.
7. ⛔ **Do not write a partial AI context.** If either document is missing, write none.
8. ⛔ **Do not instruct a run to grep when its tools exclude `Grep`.** That contradiction shipped once; `instruction(grepAvailable)` exists to prevent it.
9. ⛔ **Do not make restore rewind history.** It appends a `RESTORE` revision.
10. ⚠ **Do not take a term's last-modified from the document timestamp.** It comes from the revision where that row changed.

## Related

- [FRD workbench](07-frd-workbench.html) — `문구·용어 맞추기`, the main consumer
- [Claude CLI runtime](05-claude-cli-runtime.html) — how context reaches a run, and resumed sessions
- [Green-zone artifacts](16-green-zone.html) — generated documents that should also obey these terms
- [Project setup](04-project-setup.html) — the clone whose `domains` material seeds the draft
