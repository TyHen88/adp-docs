# Screen IDs

> Two identifiers live side by side: the planning repository's key (`wv-card-list`) and Builder's standard label (`PS-WV-MRC-010-L01-S`). This page explains why both exist and how the label is assigned.

Package: `com.bizplay.builder.screenid`
Canonical design: `docs/superpowers/specs/2026-08-20-screen-standard-id-design.md`, `2026-08-22-new-screen-id-design.md`

## It is a mapping, not a replacement

**The standard ID does not replace the existing screen ID.** It stands next to it.

| | Key | Label |
|---|---|---|
| Value | `bo-usag-list` · `wv-card-list` | `PS-WB-MRC-010-L01-S` |
| Source of truth | **The planning repository** — `index.json`, `pages/<screenId>.html` / `.md` | **Builder's DB** — the mapping table |
| Used for | File paths · concurrent-edit locks · FRD target screens · work-mockup paths · IA links | Screen list display · reports · development requests |
| Nature | Came from outside. Builder cannot change it | Builder made it. Five segments are immutable |

⭐ **Why a mapping.** Replacing would force the extractor to renumber 508 screens in bulk, with the checker, the spec and every existing document following. A mapping **asks nothing of the extractor**.

## The format — `StandardScreenIdFormat`

```text
PS  -  WV  -  MRC  -  010  -  L01  -  S
│      │      │       │       │  │    └ origin
│      │      │       │       │  └ sequence within the group (2 digits)
│      │      │       │       └ letter (screen kind/type)
│      │      │       └ group number (3 digits)
│      │      └ business area code
│      └ system code (2 letters)
└ platform code
```

```java
"%s-%s-%s-%03d-%s%02d".formatted(platform, systemCode2, areaCode, groupNo, letter, seq)
```

The letter, from `letterOf(kind, screenType)`:

| Condition | Letter |
|---|---|
| kind is `팝업` | `P` |
| kind is `모달` | `M` |
| screen type `목록` / `상세` / `등록` / `수정` / `안내` | `L` / `D` / `R` / `U` / `G` |
| anything else, or no type | `X` |

The display form appends the origin: `display(core, origin)` → `<core>-<ORIGIN>`.

> The **platform code** is fixed when the project is registered (`^[A-Z0-9]{2,4}$`) and **cannot be corrected later** — it is the first segment of every assigned ID, numbering starts as soon as the clone lands, and assigned IDs are never rewritten. A later edit would only split the project's IDs into two generations. See [Project setup](04-project-setup.html).

## Assignment — `ScreenStandardIdService`

⭐ **Initial and incremental assignment use the same algorithm.** Line up the screens that have no ID, ordered by `(pathKey, screenId)`, and number each group **starting from its current max + 1**. Initially the max is 0, so it produces `1..N`; incrementally it appends.

⛔ **Do not split it into two branches.** Re-sorting on the incremental path would push every existing number down by one whenever a screen lands in the middle alphabetically.

⛔ **A row that is already assigned is never updated.** The absence of an `update` statement in this class is deliberate — a number already printed into a development request would start pointing at a different screen.

Tables: `adk_builder_screen_standard_id`, `adk_builder_screen_id_group`. `V94__development_screen_name_unique.sql` enforces uniqueness on the development-side name.

`ScreenStandardIdWorker` runs the assignment asynchronously; `ScreenIdMaterialReader` gathers the material from the clone.

## The business area code

`BusinessAreaCoder` / `ClaudeBusinessAreaCoder` / `BusinessAreaCodes` — the `MRC` segment. The AI proposes the area code from the screen material; `BusinessAreaCodes` holds the agreed set so the AI cannot invent a new one silently.

## New screens

A screen created inside an FRD has no repository key yet — it carries a `TemporaryScreenId` while the work is in progress. `V80__frd_screen_slug.sql` added the slug that makes that temporary identity stable.

⚠ **Only the new-screen delivery copies rewrite the internal `tmp` identifier into a development-facing screen ID** when the package is built. Existing screens' mockup HTML is not touched by one character — see [Development request](10-dev-request.html).

> ⛔ **Who assigns the key (`bo-usag-list` shape) for a new screen is a separate open question**, tracked in `docs/requests-to-planning-repo.md` §5. The standard-ID design deliberately does not close it. The `C` (change) segment rule is likewise deferred.

## Related

- [Solution templates](13-solution-mockup.html) — where the key comes from
- [IA](12-ia.html) — the tree built around these identifiers
- [Development request](10-dev-request.html) — where the label is printed and becomes permanent
