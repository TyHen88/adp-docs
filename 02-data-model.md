# Data model

> What the database holds, under what names, and the rules that keep migrations from breaking the build. The canonical document is `docs/data-model.md`; this page is the orientation layer above it.

## Ground rules

| Rule | Detail |
|---|---|
| Schema | **`builder`**, inside database `we_adk`. The `public` schema of the same database belongs to the neighbouring `we-adk-admin` repository and Builder never reads it. |
| Managed by | **Flyway alone.** 93 migrations, `V1` … `V95`, under `src/main/resources/db/migration/`. |
| Access | **MyBatis only.** JPA and `ddl-auto: validate` were removed on 2026-08-15. Mapper XML lives in `src/main/resources/mapper/<package>/`. |
| Table prefix | `adk_builder_*` |
| Column naming | **Column names in English, meaning in a Korean `COMMENT ON COLUMN`.** The ERD generator copies those comments, so a column with no comment shows up in the diagram as an unexplained column. |
| DB version | PostgreSQL 17 in production; **tests run on zonky embedded PostgreSQL 14.22** — using 15+ syntax breaks the tests only, which is the worst way to find out. |

## Table groups

**55 domain tables**, plus Flyway's own `flyway_schema_history` — which lives in the `builder` schema too, so `information_schema.tables` reports **56**. No migration drops a table, so the two numbers stay one apart.

The grouping below is the one `docs/tools/erd_from_migrations.py` uses; a new table that is not added to its `GROUPS` list falls out at the bottom of the ERD as "ungrouped", on purpose, so it is noticed.

### Foundation — people and projects

`adk_builder_account` · `adk_builder_claude_credential` · `adk_builder_project` · `adk_builder_project_facet` · `adk_builder_project_system` · `adk_builder_repository_update` · `adk_builder_dev_issue_target` · `adk_builder_design_system_curation` · `adk_builder_screen_id_group` · `adk_builder_screen_standard_id`

### FRD — the work unit

`adk_builder_frd` · `adk_builder_frd_item` · `adk_builder_frd_facet` · `adk_builder_frd_analysis_note` · `adk_builder_frd_backend_change` · `adk_builder_frd_interview_message`

| Table | Responsibility |
|---|---|
| `adk_builder_frd_interview_message` | The ordered conversation — AI questions and analysis summaries, user answers |
| `adk_builder_frd_backend_change` | Per API / data / permission / batch / notification: needs change, or confirmed no change |
| `adk_builder_frd_analysis_note` | Completion criteria and items needing confirmation |

> ⚠ **Known inconsistency — the two facet children disagree.** Both `adk_builder_frd_facet` (`V25`) and `adk_builder_intake_facet` (`V18`) carry the composite FK `(project_id, name)` into `adk_builder_project_facet`, but **only the intake one declares `on update cascade`**. So renaming or deleting a facet that an FRD holds hits a `NO ACTION` violation, while the same situation on the intake side is either cascaded or refused with a readable message. `ProjectService` checks `IntakeFacetMapper` only. Not fixed here — a fix is either a migration adding the cascade or a `FrdFacetMapper` check in the service.

### FRD screen work

`adk_builder_frd_screen` · `adk_builder_frd_screen_history` · `adk_builder_frd_screen_ia_placement` · `adk_builder_frd_screen_chat_message` · `adk_builder_frd_screen_marker` · `adk_builder_frd_screen_marker_history` · `adk_builder_frd_screen_memo_comment`

| Table | Responsibility |
|---|---|
| `adk_builder_frd_screen` | Front-end screens to change — existing and new screens together |
| `adk_builder_frd_screen_memo_comment` | Comment-style memos per screen, preserving author name at the time, timestamp, content |
| `adk_builder_frd_screen_marker` | Per-element execution markers: description, author, element-anchored position |
| `adk_builder_frd_screen_marker_history` | Marker snapshot taken alongside each screen-history entry |

### Development request and delivery

`adk_builder_dev_request` · `adk_builder_dev_request_delivery` · `adk_builder_developer_target` · `adk_builder_developer_delivery`

### IA (menu tree)

`adk_builder_ia_structure` · `adk_builder_ia_row` · `adk_builder_ia_revision` · `adk_builder_ia_screen_profile`

### AI execution

`adk_builder_ai_run` — one row per Claude run: kind, state, owner, timings, failure.

### Green zone — artifacts Builder generates

`adk_builder_feature_spec` · `adk_builder_feature_spec_revision` · `adk_builder_screen_design` · `adk_builder_screen_design_revision` · `adk_builder_user_manual`

### Business language

`adk_builder_business_document` · `adk_builder_business_document_revision` · `adk_builder_business_document_seed` · `adk_builder_business_document_seed_part` · `adk_builder_business_document_seed_merge`

### Other current tables

`adk_builder_srt` · `adk_builder_frd_completion_run` · `adk_builder_frd_completion_event` · `adk_builder_screen_draft_batch` · `adk_builder_screen_draft_batch_item` · `adk_builder_notification` · `adk_builder_flow_api_key`

> ⚠ **`adk_builder_srt` looks thinner than it is.** It holds no requirements of its own — `bridge_frd_id` (UNIQUE) points at an auto-created `adk_builder_frd` row with `source_kind = 'SRT'`, and the requirements and completion criteria live there as ordinary `adk_builder_frd_item` and `adk_builder_frd_analysis_note` rows. `dev_request_id` is UNIQUE too, so SRT → bridge FRD → development request is fixed 1:1. A `CHECK` also enforces the entry method: `DIRECT` must have a null `flow_task_number`, `FLOW` must have a non-blank one. Detail: [SRT fast track](09-srt.html).

### Retired front-stage — tables only

`adk_builder_intake` · `adk_builder_intake_facet` · `adk_builder_received_document` · `adk_builder_document_processing_run` · `adk_builder_requirement` · `adk_builder_mockup_mismatch`

These belong to the retired `received document → REQ → RD → BRD` chain. They exist for data compatibility. **Do not use them as the basis for new code, screens or DB design.**

## Artifact ID numbering

Rules, all settled:

| # | Rule |
|---|---|
| 1 | Format is `{kind}-{3-digit zero-padded}` — `FRD-025`, `DR-009` |
| 2 | **Restarts at 1 per project**, ignoring the system axis (webview / back-office). Per-system numbering would make two people's lock keys collide |
| 3 | Assigned **at the moment of creation** — humans never type a number, so collisions cannot arise |
| 4 | **Immutable, never reused, gaps allowed.** Reuse would make a number development already received point at something else |
| 5 | **Never sort by this string.** Past 999 it grows to `FRD-1000`, which sorts before `FRD-002`. Sort by the numeric sequence column |

**Only two things carry a number today: FRD (`FRD-`) and development request (`DR-`).** `REQ-`, `RD-` and `BRD-` left the flow on 2026-08-20. IA has no number (one per project + system). The two returning artifacts — unit test results and integration test scenarios — are identified by *development request number + kind*, because they arrive attached to a DR.

An FRD with zero screens still gets an `FRD-` number. "Has no number" and "has no screens" are deliberately not conflated.

## Identifiers in paths

`IdSequence.isValidId()` guards every ID before it becomes a filesystem path. `ProjectPaths` refuses anything that is not a valid ID, which is what keeps `frd-<id>` worktree names and `DR-NNN.zip` archive names from becoming a path-traversal surface.

## Migration rules — the six-times-burned list

**Read this before adding a migration.**

Measure the next number immediately before creating the file:

```bash
ls src/main/resources/db/migration/ | sed 's/__.*//' | sort -V | tail -1
```

- ⛔ **Never write a migration number into a document or a plan.** The same spot has been hit six times: `V21`, `V46`, `V50`, `V52`, `V79` (duplicate) and `V81`. Two of them happened within one day, and one of those was after the plan itself said "re-measure at the moment you start".
- ⛔ **Never edit an applied migration — not even one character of a comment.** Flyway checksums it and refuses to start with `Migration checksum mismatch`. Add a new migration instead.
- ⭐ **"Be careful" does not work here.** An untracked migration file is invisible to `git log`, to the `git status` summary and to the worktree — only `ls` shows it. If the names differ, the git merge succeeds silently and Flyway rejects the whole context at runtime with `Found more than one migration with version N`.
- On a collision, **move your own file.** Never touch someone else's uncommitted or untracked file.
- `V81` is the worst case seen: an untracked file was applied to the DB and then disappeared, so startup died with "applied migration not resolved locally". It was recovered by deleting the history row.

## Redraw the ERD before committing

```bash
python docs/tools/erd_from_migrations.py            # rewrite §2 of docs/data-model.md
python docs/tools/erd_from_migrations.py --check    # exits 1 if stale
```

Section §2 of `docs/data-model.md` is **never written by hand** — the script replays every migration in version order and redraws tables, columns and relationships. New tables must be added to the script's `GROUPS`. Column meanings come from `COMMENT ON COLUMN`; if it is not in the database, it is not in the diagram.
