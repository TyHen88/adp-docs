# Spec checker

> Builder does not judge spec compliance — the planning repository's own checker does. This page covers how it is invoked, why the whole repository is checked twice, and how blame is separated.

Package: `com.bizplay.builder.checker`

## The rule that shapes everything here

⛔ **Builder does not write its own checker.** The side that defines the spec (the extractor) owns the checker, and a copy of it ships inside the planning repository.

If Builder wrote a second one, **"what is correct" would exist in two copies** — the planning team green while Builder is red, with no way to decide who is right. What this package does is **call it**.

## Invocation — `NodeCheckerCommand`

```bash
node verify/run.mjs . --json
```

Contract, measured 2026-08-14 on a real 263-screen project repository and updated 2026-08-15 (extractor `37a25fb`, whose `spec/manifest.md` pinned the format as a promise):

- The arguments are **`[--json] [<root>]` and nothing else** — there is **no entry point for checking a single file**.
- A full check takes **~0.95 seconds** (measured 1021 / 949 / 896 ms).
- Output is `{toolchain, status, exitCode, counts, findings[], ratchet}`.
- ⚠ **Always look at `status`** — `incomplete` means **not one gate was run**, which is very different from "no findings".

`CheckerCommand` is the seam the tests substitute, so verdict logic can be measured without node installed.

## `Finding` — do not translate the fields

⛔ **Never rename the checker's output fields into our own words.** Diverging names make comparison impossible. The six confirmed on 2026-08-14 are `file`, `line`, `gate`, `level`, `what`, `fix`; `kind` appeared as a seventh in `we-adk-toolchain/13`.

| Field | Meaning |
|---|---|
| `gate` | Which check was hit — e.g. `A3-ANCHORS`, `DOMAIN-COVERAGE` |
| `what` | What is wrong. **Korean, and directly showable to a person** — the checker emits Korean |
| `fix` | How to fix it, supplied by the checker |
| `kind` | Violation, or not-measurable. ⚠ Older repositories without this field exist; treat those as `VIOLATION` |

## Why the whole repository is checked twice — `DraftChecker`

⭐ Measured 2026-08-14 against a real cloned planning repository: **26 red and 17 review findings were already there**. So "everything must be green to save" is **impossible by construction** — somebody else's red would block this planner forever. And the checker has no single-file entry point.

**So it compares before and after applying the draft, and blames the person only for what is newly introduced.** A full check is ~0.95 s, so running it twice costs two seconds (measured on 263 screens) — and no new feature has to be requested from the extractor.

⛔ **Do not change this to "look at that file only".** The complete-anchor-set check, the paired-file check and the index-consistency check all examine the file's **relationship to the whole repository**. Measuring the file's contents alone loses all three.

## The check workspace — `CheckerWorkspace`

⛔ **Never check inside the shared clone.** The clone is shared by every planner on that project. Putting a candidate file there means two simultaneous saves **mix each other's drafts**, and the "before" state then includes someone else's draft — which makes the whole difference verdict false.

So a check takes its own repository copy:

- A git worktree with **`--detach`** — no branch, because this one is **read and discard**.
- ⚠ It **shares objects with the clone**, so the 148 MB is not downloaded again.
- ⚠ This is not the FRD worktree machinery. That one has a branch and goes all the way to commit and push. When that machinery stands, this can be moved onto it — but **it is not built in advance**.

## Caching and async

`PlanningRepoCheckCache` holds the last verdict; `PlanningRepoCheckWorker` runs the checker behind it.

★ **The worker is a separate bean.** Inside the cache it would be self-invocation and `@Async` would never fire — the same lesson as `ScreenMockupWorker` and `ScreenTobeDocumentWorker`. Tests call it directly without the proxy, which runs synchronously and returns a completed future; that is the right shape for a test.

Timeout: `builder.check-timeout`.

## Where checks run

| Moment | What runs |
|---|---|
| Saving screen work | `DraftChecker` — before/after diff, reporting only what this save introduced |
| Pressing `개발요청 보내기` | `DevRequestPrecheck.checkForDelivery()` — translates checker findings into **blocking** or **warning** |
| Opening the DR detail | `DevRequestPrecheck.check()` — reports only what the DB already knows; **does not run the checker** |

⭐ Running the checker on every detail open made the same screen look different each time the cached result expired, so it was narrowed to the send action (instruction, 2026-08-25).

## Related

- [Development request](10-dev-request.html) — blocking vs. warning
- [Design guide](14-design-guide.html) — the `A-5` vocabulary fence and `DESIGN-1`
- [FRD workbench](07-frd-workbench.html) — what happens on save
