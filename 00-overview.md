# What ADP Builder is

> The product purpose, the three-repository topology it lives in, the boundaries it must not cross, and the stage it is currently at.

## The product in one paragraph

ADP Builder is a **web application installed on one server**. Planners open it in a browser. It clones a **planning repository** (owned by the planning team, hosted on GitLab) and manages the life of the planning artifacts inside it: an FRD is analysed with AI, screens are drafted in a dedicated git worktree, and the finished work is packaged into a **development request** that goes to the development organisation as a ZIP plus a GitLab issue. When development replies, Builder takes the returned material back into the planning repository and generates the downstream documents from it.

It is **100% new code**. Nothing was carried over from the frozen `we-adk-builder-v1` repository.

## The three repositories

```text
extractor ──▶ planning repo ──(a human pushes)──▶ GitLab ──▶ builder clones and uses it
            (carries the spec, the checker and the merge tool)        ▲
                                                                      └─ this repository
```

| Repository | What it is | Does it know `g2c`? |
|---|---|---|
| `we-adk-builder-extractor` | A Claude Code skill run once, at project kick-off. Production source → standard structure. | **Yes — that is where the original lives.** |
| planning repo × N | Owned by the planning team, on GitLab. Screens, requirements, domain docs + the **spec and the checker**. | **No** — the rules for reading source never ship there. |
| `we-adk-builder` ← **this one** | One server, browser access. Manages the life of the artifacts. | No. |

Build order is **extractor → planning repo → builder**. The extractor fixes the planning repository's structure, so the order cannot be reversed. Builder is last.

> "Does not know `g2c`" is about **the rules for reading source**. Where something came from is still recorded — `source-index.json` carries `dino-*` paths and commits.

## Hard boundaries

These are not style preferences. Crossing one makes the rebuild pointless.

- **Builder does not know `g2c`.** No code that reads the source system (Thymeleaf, `dino-*`) lives here. Extraction is run by a human in a Claude Code session with the `we-adk-builder-extractor` skill.
- **Institution skin folder names (`iks`, `tnj`) never appear in code.** Builder swaps skins at render time, but which institution maps to which CSS folder is *business knowledge*; the single source is the clone's `manifest.json` → `systems[].skins`. The moment that string is held in code, Builder knows `g2c`. Design: `docs/superpowers/specs/2026-08-22-preview-skin-design.md`.
- **The planning repository belongs to the planning team.** Only a clone arrives here. The spec and the checker live inside the planning repository, not here.
- **No cross-repository section references.** If another repository's document is needed, copy the text. References are what grew the previous 15 documents to 6,695 lines.

## The current product flow

Revised 2026-08-20: received documents, requirements (REQ), requirement definitions (RD) and BRD were **removed** from the Builder flow.

```text
FRD 작업하기 ─┬ step 1  enter the requirement directly
              ├ step 2  AI interview          → FRD workbench → development request (DR)
              └ step 3  confirm the dev scope
```

> The three steps are **not siblings of the workbench** — they are the inside of the `FRD 작업하기` wizard. The canonical definition is `FrdWizardController` plus the three progress markers in `templates/artifacts/frd-wizard.html`. In state terms: `ANALYZING` · `WAITING_ANSWER` · `PICKED` (step 2) → `SCOPE_REVIEW` (step 3) → `DRAFTING` (workbench). Never draw five boxes in one row.

## What Builder handles — the artifacts

The count and the list are owned by `docs/artifacts.md`. Summary:

| Group | Artifact | Who owns it |
|---|---|---|
| Builder creates and manages | **FRD work** (`FRD-`), **development request** (`DR-`) | Builder |
| The planner manages | **IA / menu tree** | Planner, one per system |
| Shows current production | **Solution template (mockup)** | Extractor produces, Builder reads |
| Arrives from development | as-is resync, **unit test** results, **integration test** scenarios | Development returns them |
| Builder generates from returned material | **Feature spec**, **screen design**, **user manual** | Builder |

**The green zone** — opened 2026-08-27 — is the five artifacts `기능명세서` · `화면설계서` · `단위테스트` · `통합테스트` · `사용자 매뉴얼`, shown as the green block in the left menu. The requirements traceability matrix was **deleted the same day**; do not revive the `matrix` menu key.

## What Builder is explicitly not responsible for

| What | Whose job |
|---|---|
| Extracting screens from the production source | `we-adk-builder-extractor`, run by a human in a separate Claude Code session |
| Judging planning-repository spec compliance | The checker carried inside the planning repository |
| Knowing `g2c` and the original system | `we-adk-builder-extractor` |

## Current stage

**Stage 3.** It starts only once the first two (extractor → planning repo) stand. The finish condition is: **a planner fixes one screen through the browser.**

## Retired chains — do not build on them

The `received document → requirement (REQ) → requirement definition (RD) → BRD` chain was retired on 2026-08-20. Tables and screen addresses may still exist for data compatibility, but they are **not a prerequisite step for any new work**, and must not be used as justification for new code, screens or DB design.

Likewise, the old v1 decision IDs (`AR*`, `RQ*`, `IM*`, `AN*`, `D*`) came from a "one repository + locally installed tool" premise that has been discarded. `we-adk-builder-v1` may be read as reference, never as authority.

## Where to go next

- How it is built: [Architecture](01-architecture.html)
- What the database holds: [Data model](02-data-model.html)
- How the AI actually runs: [Claude CLI runtime](05-claude-cli-runtime.html)
- The main user loop: [FRD wizard](06-frd-wizard.html)
