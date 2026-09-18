# Unit & integration tests

> The two green-zone screens that read what development returns. Builder never runs a test — it reads the result documents and lines them up against what it asked for.

Packages: `com.bizplay.builder.unittest`, `com.bizplay.builder.integrationtest`
Canonical designs: `docs/superpowers/specs/2026-09-08-unit-test-result-screen-design.md`, `2026-09-08-integration-test-screen-design.md`

## Why tests arrive as documents

**Builder cannot read development source — it does not know `g2c`.** So tests never come back as code.

| Artifact | Shape | Keyed to |
|---|---|---|
| Unit test | **A result document (MD).** One line per "out-of-screen implementation" item in the development request — what was verified, how, and the outcome. It answers the `판정 방법` column Builder sent | The DR |
| Integration test | **A scenario document (MD).** Per completion criterion — scenario, steps, expected result, outcome. A requirement → completion criterion → scenario trace falls out of it for free | The DR |

⭐ **Builder writes what is to be verified first.** TC numbers, conditions, actions and expected results go out in the package's `expected-back.md` (2026-08-27). Development fills in only the actual result, the verdict and the evidence. That is what makes the returned MD countable **per TC** on screen.

## Unit test screen

`UnitTestController`, `UnitTestResultReader`, `UnitTestResultParser`
Route: `/projects/{projectId}/artifacts/unit-tests`

**This is not a screen where Builder runs tests.** It reads the `artifacts/unit-test.md` that development returned for each development request.

### Where the data is read from — and where it is not

The source of truth is the **latest received result ZIP** satisfying **both**:

1. The batch that the development request row's `received_batch_id` points at, and
2. the file at `received/<devRequestId>-<batchId>.zip` in Builder's data area.

Inside the ZIP, `artifacts/unit-test.md` is read from the root **or** from one wrapper folder down (`<wrapper>/artifacts/unit-test.md`). **If it is missing, or there are two, the result is not used.**

⛔ **Never use the `artifacts/unit-test.md` copied into the planning-repository clone or an FRD worktree as the list's source.** Several development requests' results land in that same path in turn and can overwrite each other, so it cannot guarantee whose result it is. Pairing the DB receipt history with that batch's original ZIP is what keeps the request and the result from separating.

### When results appear

The `단위테스트` menu always opens; actual results appear only after this sequence:

```text
development request sent
  → the development team runs the tests
  → result ZIP returned
  → manifest, required files, targets, TCs and result fields validated
  → development result applied successfully and the receipt recorded
  → the unit-test list becomes visible
```

The receiver writes `received_batch_id`, `received_zip_sha256` and `received_at` only after both ZIP validation **and** application succeed.

### Parsing

`UnitTestResultParser` reads the validated markdown into a screen structure:

| Pattern | Meaning |
|---|---|
| `^### N. <target>` | A target |
| `^#### TC-NNN — <title>` | A test case |
| `^- <field>: <value>` | A field within the case |

## Integration test screen

`IntegrationTestController`, `IntegrationTestService`, `IntegrationTestResultReader`, `IntegrationTestResultParser`, `IntegrationTestView`
Route: `/projects/{projectId}/artifacts/integration-tests`

⭐ **An integration test is not an artifact that first appears after development finishes.** When the development request is prepared, integration-test scenarios are generated from the completion criteria (`DevRequestTestScenarioWorker`) and are immediately visible in this menu.

Before development replies, the same scenarios show as `결과 대기`. After the reply, **the scenarios are not replaced** — the actual result, verdict and evidence are merged in **by TC number**.

### Two separate sources of truth

```text
development_request.content_json
  ├─ completion criteria notes
  └─ INTEGRATION testScenarios
       ↓ displayed from before development completes

development_request.received_batch_id
  + received/<devRequestId>-<batchId>.zip
  + artifacts/integration-test.md
       ↓ joined by TC number: actual result, verdict, evidence
```

**Builder is not a tool for running integration tests, nor for editing or approving results.** It provides only the screen where a planner reads the link between completion criteria and outcomes.

## Validation of what comes back

`DevTestResultValidator` (in `devrequest`) checks the returned documents against the contract that was sent — `specVersion` 3 only, verdicts restricted to `성공` / `실패` / `미수행`, and every `<placeholder>` replaced. See [Development result](11-dev-result.html).

## Related

- [Development request](10-dev-request.html) — `expected-back.md`, where the TCs are written
- [Development result](11-dev-result.html) — receipt and validation
- [Green-zone artifacts](16-green-zone.html) — the other three green-zone keys
