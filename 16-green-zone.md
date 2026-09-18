# Green-zone artifacts

> The five artifacts in the green block of the left menu, and the three of them Builder generates itself: the feature spec, the screen design and the user manual.

Packages: `com.bizplay.builder.featurespec`, `screendesign`, `usermanual`
Canonical designs: `docs/superpowers/specs/2026-08-27-feature-spec-generation-design.md`, `2026-08-27-screen-design-generation-design.md`

## What the green zone is

Opened 2026-08-27. `ShellContract.GREEN_ZONE_KEYS`:

`functional-specs` · `screen-designs` · `unit-tests` · `integration-tests` · `user-manual`

Until a screen stands, `list.html` shows `준비 중` for its key.

The intended order of work was: feature spec (the screen-MD viewer) → user manual → screen design. The unit- and integration-test screens come **after** the return flow from development stands — see [Unit & integration tests](17-tests.html).

⛔ **The requirements traceability matrix was deleted the same day.** Do not revive the `matrix` menu key, the `09-matrix.html` mockup, or roadmap step 6.

## Two arrive, three are generated

| Artifact | Origin |
|---|---|
| Unit test results | **Development returns them** |
| Integration test scenarios | **Development returns them** |
| **Feature spec** (기능명세서) | **Builder generates it** |
| **Screen design** (화면설계서) | **Builder generates it** |
| **User manual** (사용자 매뉴얼) | **Builder generates it** |

All three generated ones use the same material: the screen HTML and screen MD **refreshed by the as-is resync**, plus the menu tree. **The as-is resync must arrive first, or there is nothing to generate from.**

## The shared generation shape

All three follow one pattern:

```text
detail screen is opened
  → is there a current document, and did its inputs change?
      ├─ no change  → show the existing revision
      └─ changed / missing → claim it (state = RUNNING) and hand off to an @Async worker
  → the worker runs claude with a JSON schema
  → a valid result is promoted to a new revision (state = DONE)
  → a failure records FAILED and retries a bounded number of times
```

Common constants across the workers: `GENERATOR_VERSION`, `SCHEMA_VERSION`, `STALE_MARGIN` (5 minutes), `RETRY_DELAY` (2 minutes), `MAX_ATTEMPTS` (2).

⭐ **Shape rules are enforced by the JSON schema first**, and the reader keeps only the *meaning* checks — evidence IDs actually existing, move targets actually existing, duplicate items. Splitting it that way keeps the reader small and makes malformed output fail before it is parsed.

States: `FeatureSpecState` / `ScreenDesignState` are `RUNNING`, `DONE`, `FAILED`; `UserManualState` is the same three with Korean labels `만드는 중`, `최신`, `생성 실패`.

## Feature spec (기능명세서)

`FeatureSpecService`, `FeatureSpecWorker`, `FeatureSpecMaterialService`, `FeatureSpecContentReader`, `FeatureSpecRenderer`, `FeatureSpecStorage`
Routes: `/functional-specs/{systemCode}/{screenId}`, `/status`, `/print`

It is **not a new artifact type** — it is the place that shows the as-is screen MD (the 2026-08-25 absorption decision, unchanged). It is generated **only when there is no current document or the inputs changed**, on entering the screen detail.

- ⛔ **It does not re-read the screen list.** `SolutionMockupService` already sweeps the index, the MDs and the git history in one pass and caches it — reading again would read the same 274 screens twice.
- ⛔ **It writes nothing to the planning repository.** The source of truth is the repository and Builder only reads.
- `FeatureSpecMaterialService` freezes the material into **fixed inputs plus an evidence list at generation time**, which is what makes the evidence-ID check meaningful later.

Schema limits (`feature-spec-schema-1`): sentences ≤ 6,000 characters, arrays ≤ 150, 1–20 evidence items per statement; the `fields[].type` and `required` enumerations come from §10 of the design.

Managed as **structured DB documents plus successful revisions**. The user-facing screen deliberately does **not** expose the MD source, the extraction location, or the generation method.

## Screen design (화면설계서)

`ScreenDesignWorker`, `ScreenDesignContentAssembler`, `ScreenCaptureRunner`, `ScreenDesignBundleStore`, `ScreenDesignMarkerReader`
Routes: `/screen-designs/{systemCode}/{screenId}`, `/status`, `/revisions/{revisionId}/captures/{name}`, `/download`

`GENERATOR_VERSION = screen-design-3`. Only the screen being opened is generated, asynchronously, and only a valid result is promoted to a revision.

### Capture — `ScreenCaptureRunner`

Playwright Chromium captures the default screen and explicit variants to PNG and PDF.

| Limit | Value |
|---|---|
| Callout targets | `button, a, input, select, textarea, [role=button], [role=tab]` |
| Max callouts | 40 |
| Screen viewport width | 1600 |
| Max capture height | 16,000 px |
| Max single capture | 12 MB |
| Max bundle | 60 MB |
| Max variants | 12 |
| Manual viewport | 1440 × 1000 |

⚠ **Full Chromium is required** — install with `--with-deps chromium` and **without** `--only-shell`. Without it, everything else still works and existing revisions remain readable; only new screen-design and user-manual revisions fail.

`ScreenDesignMarkerReader` pulls the FRD markers into the document, which is why marker text written in the workbench is worth writing well.

## User manual (사용자 매뉴얼)

`UserManualWorker`, `UserManualReader`, `UserManualCapture`, `UserManualCaptureStore`
Routes: `/user-manual/{systemCode}/{screenId}`, `/preview/{systemCode}/{screenId}`, `/download`, `/download/{systemCode}/{screenId}`

Model: `sonnet`. Schema limits: title ≤ 200 characters, sentences ≤ 4,000, arrays ≤ 100, at least one step. The 60,000-character whole-response cap cannot be expressed in the schema, so it lives in the reader — along with the meaning check that evidence actually exists.

The manual view is one of the same-origin-framed URL patterns (`UserManualController.URL_PATTERN`) — see [Accounts & security](03-accounts-security.html). `V70__user_manual_capture_pointer.sql` added the capture pointer.

## Related

- [Development result](11-dev-result.html) — the as-is resync these depend on
- [Solution templates](13-solution-mockup.html) — the cached sweep they reuse
- [Unit & integration tests](17-tests.html) — the other two green-zone keys
- [Install & operations](21-operations.html) — Chromium installation
